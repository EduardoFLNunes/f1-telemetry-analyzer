"""
Fit the driver's reference model from everything he has recorded.

    python tools/train_reference_model.py [--track vhe_interlagos] [--limit N]

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
    )

    print()
    print("=" * 58)
    print(f"voltas no modelo   : {model.lap_count}")
    print(f"descartadas        : {model.rejected_count}  {model.rejected_reasons}")
    print(f"melhor volta real  : {model.best_lap_seconds}s  ({model.best_lap_id})")
    print(f"volta ideal        : {model.ideal_lap_seconds}s")
    print(f"na mesa            : {model.gap_best_to_ideal}s")
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

    path = model.save(model_path(root, track or "unknown"))
    print(f"\nmodelo gravado em: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
