"""
Fit the driver's reference model from everything he has recorded.

    python tools/train_reference_model.py [--track vhe_interlagos] [--limit N]
        [--modo reference_lap|best_per_microsector] [--volta-referencia <lap_id>]
        [--geometria-arquivo <pista>.geometry.json] [--saida ARQUIVO]

Modo padrao (ADR 0012): a volta de referencia e a melhor volta valida e completa
da pista -- ou a escolhida com --volta-referencia -- e o coach mede cada trecho
contra ela.

Geometria (ADR 0013): toda volta e reprojetada pela posicao no mundo na
geometria oficial exportada por `python -m ml.scripts.export_geometry`, e o
modelo grava o `geometry_id` dela. Por isso entram voltas de qualquer cache,
inclusive as de 2026-08-09, que nao tem `p`. O carro nao e registrado nas
gravacoes e por isso nao pode ser filtrado.

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
from core.assisted_analysis.official_geometry import OfficialGeometry, find_official_geometry  # noqa: E402
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
    parser.add_argument("--limit", type=int, default=0,
                        help="usar as N voltas mais rapidas (0 = todas, o padrao)")
    parser.add_argument("--microsectors", type=int, default=DEFAULT_MICROSECTORS)
    parser.add_argument("--dry-run", action="store_true", help="nao grava o modelo")
    parser.add_argument("--modo", default=MODE_REFERENCE_LAP, choices=MODES)
    parser.add_argument("--volta-referencia", default=None, help="lap_id da volta de referencia")
    parser.add_argument("--saida", type=Path, default=None, help="grava aqui em vez do caminho do runtime")
    parser.add_argument(
        "--geometria-arquivo",
        type=Path,
        default=None,
        help="geometria oficial exportada (padrao: data/reference_models/<pista>.geometry.json)",
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

    geometry = (
        OfficialGeometry.load(args.geometria_arquivo)
        if args.geometria_arquivo
        else find_official_geometry([root, BACKEND_DIR.parent], track or "unknown")
    )
    if geometry is None:
        print("PARADO: geometria oficial nao encontrada. Rode antes: python -m ml.scripts.export_geometry")
        return 2
    print(f"geometria oficial : {geometry.geometry_id}  ({geometry.length:.2f} m, {geometry.microsectors} microsetores)")
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
    # Gravacoes em lote: cada sessao e lida uma vez (load_recorded_laps).
    recorded = [lap for lap in plausible if lap.lap_id.startswith("rec__")]
    frames = loader.load_recorded_laps([lap.lap_id for lap in recorded]) if recorded else {}
    for descriptor in plausible:
        if descriptor.lap_id in frames:
            df = frames[descriptor.lap_id][1]
        else:
            try:
                _, df = loader.load_lap(descriptor.lap_id)
            except Exception as error:
                print(f"  ! {descriptor.lap_id}: {error}")
                continue
        laps.append((descriptor.lap_id, descriptor.lap_time, descriptor.sample_count, df))
    print(f"  carregadas {len(laps)}/{len(plausible)}  ({time.monotonic() - started:.0f}s)")

    model = build_reference_model(
        laps,
        track=track or "",
        microsectors=args.microsectors,
        built_at=datetime.now(timezone.utc).isoformat(),
        mode=args.modo,
        reference_lap_id=args.volta_referencia,
        geometry=geometry,
    )

    print()
    print("=" * 58)
    print(f"voltas no modelo   : {model.lap_count}")
    print(f"descartadas        : {model.rejected_count}  {model.rejected_reasons}")
    print(f"modo               : {model.mode}")
    print(f"volta de referencia: {model.reference_lap_seconds}s  ({model.reference_lap_id})")
    print(f"geometria          : {model.geometry_id}")
    print(f"melhor volta real  : {model.best_lap_seconds}s  ({model.best_lap_id})")
    # A soma dos melhores trechos e um limite otimista, nao uma meta (ADR 0012).
    print(f"soma dos melhores trechos (limite otimista, nao meta): {model.ideal_lap_seconds}s")
    print("=" * 58)
    print("\nas 5 voltas validas mais rapidas:")
    for candidate in model.reference_candidates:
        print(f"  {candidate['lap_seconds']:.3f}s  {candidate['lap_id']}  -> {candidate['motivo']}")

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
