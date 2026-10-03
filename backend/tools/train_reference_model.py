"""
Fit the driver's reference model from everything he has recorded.

    python tools/train_reference_model.py [--track vhe_interlagos] [--limit N]
        [--modo reference_lap|best_per_microsector] [--volta-referencia <lap_id>]

Modo padrao (ADR 0012): a volta de referencia e a melhor volta valida e completa
da pista -- ou a escolhida com --volta-referencia -- e o coach mede cada trecho
contra ela. So entram voltas gravadas com o mesmo cache de geometria da maioria
(`trackCache` da sessao); o carro nao e registrado nas gravacoes, e por isso nao
pode ser filtrado.

Walks the recorded laps, keeps the ones whose sampling holds up, times each
through every microsector, and writes the model the analysis engine measures
against. Prints what it learned and what it threw away.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.assisted_analysis.lap_loader import LapDataLoader  # noqa: E402
from core.assisted_analysis.reference_model import (  # noqa: E402
    DEFAULT_MICROSECTORS,
    MODE_REFERENCE_LAP,
    MODES,
    build_reference_model,
    lap_is_usable,
    model_path,
)
from core.live.runtime_state import RuntimeState  # noqa: E402
from core.telemetry.telemetry_buffer import TelemetryBuffer  # noqa: E402


def runtime_root() -> Path:
    configured = os.environ.get("AT_BACKEND_RUNTIME_ROOT")
    if configured:
        return Path(configured)
    appdata = os.environ.get("APPDATA")
    if appdata:
        packaged = Path(appdata) / "Automobilista Telemetria"
        if packaged.exists():
            return packaged
    return BACKEND_DIR.parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Treina o modelo de referencia do piloto")
    parser.add_argument("--track", default=None, help="pista (padrao: a mais gravada)")
    parser.add_argument("--limit", type=int, default=150,
                        help="usar as N voltas mais rapidas (0 = todas)")
    parser.add_argument("--microsectors", type=int, default=DEFAULT_MICROSECTORS)
    parser.add_argument("--dry-run", action="store_true", help="nao grava o modelo")
    parser.add_argument("--modo", default=MODE_REFERENCE_LAP, choices=MODES)
    parser.add_argument("--volta-referencia", default=None, help="lap_id da volta de referencia")
    parser.add_argument("--saida", type=Path, default=None, help="grava aqui em vez do caminho do runtime")
    parser.add_argument(
        "--geometria",
        default=None,
        help="trackCache das sessoes a usar; sem ele, usa o da maioria e avisa",
    )
    args = parser.parse_args()

    root = runtime_root()
    recordings = [root / "data" / "recordings", BACKEND_DIR.parent / "data" / "recordings"]
    print(f"lendo gravacoes de: {recordings[0]}")

    loader = LapDataLoader(
        repo_root=BACKEND_DIR.parent,
        buffer_provider=lambda: TelemetryBuffer(max_size=1),
        runtime_state_provider=RuntimeState,
        recordings_roots=recordings,
    )

    descriptors = loader.list_laps(include_buffer=False)
    print(f"voltas encontradas: {len(descriptors)}")

    track = args.track
    if not track:
        counts: dict[str, int] = {}
        for lap in descriptors:
            if lap.track:
                counts[lap.track] = counts.get(lap.track, 0) + 1
        track = max(counts, key=counts.get) if counts else ""
        print(f"pista escolhida   : {track or '(sem pista)'}")

    selected = [lap for lap in descriptors if not track or lap.track == track]

    # Mesma geometria: o cache com que a sessao foi gravada. Voltas de outra
    # versao da pista nao sao comparaveis trecho a trecho.
    def geometry_of(lap):
        return ((lap.metadata or {}).get("sessionMetadata") or {}).get("trackCache")

    caches: dict = {}
    for lap in selected:
        caches[geometry_of(lap)] = caches.get(geometry_of(lap), 0) + 1
    print("voltas por geometria gravada (trackCache):")
    for cache, count in sorted(caches.items(), key=lambda item: -item[1]):
        print(f"  {count:5d}  {cache}")
    if args.geometria:
        geometry = args.geometria
    else:
        geometry = max(caches, key=caches.get) if caches else None
        print("AVISO: --geometria nao informada; usando a da maioria. O coach compara o progresso ao vivo,")
        print("calculado com a geometria atual do app, com o do modelo: escolha a geometria de proposito.")
    other_geometry = sum(n for cache, n in caches.items() if cache != geometry)
    selected = [lap for lap in selected if geometry_of(lap) == geometry]
    print(f"geometria (trackCache) : {geometry}  ({other_geometry} voltas de outra geometria fora)")
    # Cheapest filter first: no point loading a lap the model will refuse.
    plausible = [lap for lap in selected if lap_is_usable(lap.lap_time, lap.sample_count)[0]]
    skipped_early = len(selected) - len(plausible)
    plausible.sort(key=lambda lap: float(lap.lap_time or 9e9))
    if args.limit:
        plausible = plausible[: args.limit]   # ja ordenadas por tempo

    print(f"voltas da pista   : {len(selected)}")
    print(f"reprovadas no filtro rapido: {skipped_early}")
    print(f"a carregar        : {len(plausible)}")

    laps = []
    started = time.monotonic()
    for index, descriptor in enumerate(plausible, start=1):
        try:
            _, df = loader.load_lap(descriptor.lap_id)
        except Exception as error:
            print(f"  ! {descriptor.lap_id}: {error}")
            continue
        laps.append((descriptor.lap_id, descriptor.lap_time, descriptor.sample_count, df))
        if index % 25 == 0 or index == len(plausible):
            elapsed = time.monotonic() - started
            print(f"  carregadas {index}/{len(plausible)}  ({elapsed:.0f}s)")

    model = build_reference_model(
        laps,
        track=track or "",
        microsectors=args.microsectors,
        built_at=datetime.now(timezone.utc).isoformat(),
        mode=args.modo,
        reference_lap_id=args.volta_referencia,
    )

    print()
    print("=" * 58)
    print(f"voltas no modelo   : {model.lap_count}")
    print(f"descartadas        : {model.rejected_count}  {model.rejected_reasons}")
    print(f"modo               : {model.mode}")
    print(f"volta de referencia: {model.reference_lap_seconds}s  ({model.reference_lap_id})")
    print(f"melhor volta real  : {model.best_lap_seconds}s  ({model.best_lap_id})")
    # A soma dos melhores trechos e um limite otimista, nao uma meta (ADR 0012).
    print(f"soma dos melhores trechos (limite otimista, nao meta): {model.ideal_lap_seconds}s")
    print("=" * 58)

    if model.targets:
        spread = sorted(
            model.targets,
            key=lambda target: target.median_seconds - target.best_seconds,
            reverse=True,
        )
        print("\nonde o piloto mais oscila (mediana - melhor):")
        for target in spread[:8]:
            delta = target.median_seconds - target.best_seconds
            print(
                f"  setor {target.index:2d} ({target.start_p:.2f}-{target.end_p:.2f} da volta): "
                f"{delta:+.3f}s   melhor {target.best_seconds:.3f}s em {target.best_lap_id}"
            )

    if args.dry_run:
        print("\n--dry-run: modelo nao gravado")
        return 0

    path = model.save(args.saida or model_path(root, track or "unknown"))
    print(f"\nmodelo gravado em: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
