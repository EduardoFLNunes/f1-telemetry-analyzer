"""Compara uma volta do piloto com o tracado de referencia.

    python -m ml.scripts.compare_lap [--lap LAP_ID] [--reference otimizado|lstm|melhor]

Sem `--lap`, compara a volta mais lenta do conjunto de teste -- que e onde ha
mais o que dizer.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml import config
from ml.comparison.lap_vs_reference import compare_lap
from ml.comparison.reference_frame import reference_lap_frame, rescale_to_measured
from ml.data.lap_store import load_store
from ml.optimization.vehicle_model import load_envelope
from ml.preprocessing.splits import split_by_session
from ml.track.corners import detect_corners
from ml.track.geometry import load_geometry
from ml.track.microsectors import build_microsectors
from ml.visualization.telemetry_plots import plot_lap_comparison, plot_time_delta
from ml.visualization.track_plots import plot_trajectories


def _reference_lateral(track, store, kind: str) -> tuple:
    """Trajetoria de referencia pedida, e de onde ela veio."""
    if kind == "otimizado":
        path = config.artifacts_root() / "optimization" / "optimised_lateral.npy"
        if path.exists():
            return np.load(path), "tracado otimizado"
        print("tracado otimizado nao encontrado; usando a melhor volta real")
    if kind == "lstm":
        directory = config.artifacts_root() / "models" / "reference"
        if (directory / "model.json").exists():
            from ml.models.reference_line import generate
            from ml.models.training import load_model

            corners = detect_corners(track)
            return generate(load_model(directory), track, corners).lateral, "referencia LSTM"
        print("modelo de referencia nao encontrado; usando a melhor volta real")

    best = store.laps.iloc[0]["lap_id"]
    return store.lap(best)["lateral"].to_numpy(dtype=float), f"melhor volta real ({best})"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Comparacao com o tracado de referencia")
    parser.add_argument("--lap", default=None, help="lap_id a comparar")
    parser.add_argument(
        "--reference", choices=("otimizado", "lstm", "melhor"), default="otimizado"
    )
    args = parser.parse_args(argv)

    track = load_geometry()
    sectors = build_microsectors(track)
    corners = detect_corners(track)
    store = load_store()
    envelope = load_envelope()

    if args.lap:
        lap_id = args.lap
    else:
        split = split_by_session(store.laps)
        candidates = store.laps[store.laps["lap_id"].isin(split.test)]
        lap_id = str(candidates.loc[candidates["lap_time_s"].idxmax(), "lap_id"])

    lap = store.lap(lap_id)
    lap_time = float(store.laps.set_index("lap_id").loc[lap_id, "lap_time_s"])

    lateral, source = _reference_lateral(track, store, args.reference)
    reference = reference_lap_frame(track, lateral, envelope)
    simulated_time = float(reference["lap_time_s"].iloc[0])

    # A referencia e reescalada para o tempo da melhor volta real: o simulador e
    # conservador em ~7,5%, e comparar contra um relogio 7,5% lento faria toda
    # volta parecer boa.
    target_time = float(store.laps["lap_time_s"].min())
    reference = rescale_to_measured(reference, target_time)

    comparison = compare_lap(
        lap_id, lap, reference, track, sectors, corners, lap_time, target_time
    )

    print(f"volta:      {lap_id}  ({lap_time:.3f} s)")
    print(f"referencia: {source}  (simulada {simulated_time:.3f} s, reescalada para {target_time:.3f} s)")
    print(f"diferenca:  {comparison.delta_s:+.3f} s\n")

    print("microsetores em que mais se perdeu:")
    for sector in comparison.worst_sectors(6):
        print(
            f"  {sector.label:22s} {sector.delta_s:+6.3f} s   "
            f"desvio medio {sector.lateral_deviation_mean_m:4.1f} m   "
            f"delta v {sector.speed_delta_mean_kmh:+6.1f} km/h"
        )

    print("\npor curva:")
    for corner in comparison.corners:
        notes = corner.notes()
        detail = "; ".join(notes) if notes else "dentro da referencia"
        print(f"  {corner.label:9s} (s={corner.start_s:6.0f})  {detail}")

    output = config.artifacts_root() / "comparison"
    output.mkdir(parents=True, exist_ok=True)
    comparison.to_frame().to_csv(output / f"{lap_id.replace('#', '_')}_setores.csv", index=False)

    plot_lap_comparison(
        track,
        lap,
        reference,
        output / "telemetria.png",
        corners=corners,
        lap_label=f"{lap_id} ({lap_time:.3f}s)",
        reference_label=f"{source} ({target_time:.3f}s)",
        title="volta do piloto contra a referencia",
    )
    plot_time_delta(
        track,
        lap["elapsed_s"].to_numpy(dtype=float),
        reference["elapsed_s"].to_numpy(dtype=float),
        output / "delta.png",
        corners=corners,
        title=f"{lap_id}: {comparison.delta_s:+.3f} s contra a referencia",
    )
    plot_trajectories(
        track,
        [
            (f"{lap_id}", track.s, lap["lateral"].to_numpy(dtype=float)),
            (source, track.s, lateral),
        ],
        output / "trajetorias.png",
        title="trajetoria do piloto contra a referencia",
    )
    print(f"\ngraficos -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
