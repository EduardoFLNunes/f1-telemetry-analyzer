"""Materializa as voltas validas na grade da pista.

    python -m ml.scripts.build_lap_store

Depende do inventario (`ml.scripts.build_inventory`).
"""

from __future__ import annotations

import time

import numpy as np

from ml.data.lap_store import build_store, save_store
from ml.track.geometry import load_geometry


def main() -> int:
    started = time.time()
    track = load_geometry()
    store = build_store(track=track, progress=lambda text: print(text, flush=True))
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
