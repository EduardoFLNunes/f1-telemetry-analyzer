"""Materializa as voltas validas na grade da pista.

    python -m ml.scripts.build_lap_store [--origem humano ...|todas] [--incluir-relogio-suspeito]

Depende do inventario (`ml.scripts.build_inventory`). Por padrao entram so
voltas `humano` com relogio conferido e sem `relogio_suspeito` (ADR 0014).
"""

from __future__ import annotations

import argparse
import time

import numpy as np

from ml.data.lap_store import build_store, save_store
from ml.data.origin import ORIGINS, parse_equipment, parse_origins
from ml.track.geometry import load_geometry


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Store de voltas na grade")
    parser.add_argument("--origem", nargs="*", default=None, choices=list(ORIGINS) + ["todas"],
                        help="origens aceitas (padrao: humano; 'todas' = sem filtro)")
    parser.add_argument("--incluir-relogio-suspeito", action="store_true",
                        help="aceita voltas com relogio suspeito ou nao conferido")
    parser.add_argument("--equipamento", nargs="*", default=None, choices=["atual", "anterior", "todos"],
                        help="equipamento das voltas humano (padrao: atual, ADR 0015)")
    args = parser.parse_args(argv)

    started = time.time()
    track = load_geometry()
    origins = parse_origins(args.origem)
    print(f"origens: {origins if origins is not None else 'todas'}"
          f"{'' if args.incluir_relogio_suspeito else ' | so relogio conferido e nao suspeito'}")
    store = build_store(
        track=track,
        progress=lambda text: print(text, flush=True),
        origins=origins,
        include_clock_suspect=args.incluir_relogio_suspeito,
        equipment=parse_equipment(args.equipamento),
    )
    path = save_store(store)

    laps = store.laps
    print(f"\nstore -> {path}  ({time.time() - started:.0f}s)")
    print(f"voltas: {len(laps)} de {laps['session_id'].nunique()} sessoes")
    print(f"grade: {store.grid_size} pontos de {store.track_length / store.grid_size:.2f} m")
    times = laps["lap_time_s"].to_numpy(dtype=float)
    print(
        "tempo de volta: melhor=%.3f  p25=%.2f  mediana=%.2f  p75=%.2f  pior=%.2f"
        % (
            times.min(),
            np.percentile(times, 25),
            np.median(times),
            np.percentile(times, 75),
            times.max(),
        )
    )
    print("\nmelhores voltas:")
    for _, row in laps.head(8).iterrows():
        print(
            "  %-42s %7.3f s  %5.1f Hz  %5.0f amostras"
            % (row["lap_id"], row["lap_time_s"], row["sample_hz"], row["raw_samples"])
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
