"""Gera os graficos de comparacao entre volta real, prevista e otimizada.

    python -m ml.scripts.plot_comparison [--lap LAP_ID] [--insets 300 2300 2700]

Depende do store, do envelope, dos modelos treinados e do resultado da
otimizacao. Escreve em `data/ml/comparison/`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml import config
from ml.data.lap_store import load_store
from ml.models.reference_line import generate
from ml.models.training import load_model
from ml.optimization.lap_time_model import simulate
from ml.optimization.representation import build_encoding
from ml.optimization.vehicle_model import load_envelope
from ml.track.corners import detect_corners
from ml.track.geometry import load_geometry
from ml.track.microsectors import build_microsectors, split_times
from ml.visualization.comparison_plots import (
    TrajectorySeries,
    plot_lateral_separation,
    plot_microsector_delta,
    plot_profiles,
    plot_track_map,
)

REAL = "#06d6a0"
PREVISTA = "#ffd166"
OTIMIZADA = "#4cc9f0"


def _simulated(track, envelope, sectors, lateral):
    """Perfil e tempos por microsetor de uma trajetoria, pela fisica."""
    result = simulate(track, lateral, envelope)
    elapsed = result.cumulative_time()
    splits = split_times(elapsed, sectors, track, total=result.lap_time_s)
    return result, elapsed, splits


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Graficos de comparacao de tracado")
    parser.add_argument("--lap", default=None, help="lap_id da volta real (padrao: a mais rapida)")
    parser.add_argument(
        "--insets",
        type=float,
        nargs="*",
        default=None,
        help="distancias em metros para ampliar no mapa",
    )
    args = parser.parse_args(argv)

    track = load_geometry()
    sectors = build_microsectors(track)
    corners = detect_corners(track)
    store = load_store()
    envelope = load_envelope()

    # ------------------------------------------------------------ volta real --
    laps = store.laps
    lap_id = args.lap or str(laps.loc[laps["lap_time_s"].idxmin(), "lap_id"])
    lap = store.lap(lap_id)
    measured = float(laps.set_index("lap_id").loc[lap_id, "lap_time_s"])
    real_lateral = lap["lateral"].to_numpy(dtype=float)
    real_result, real_elapsed, real_splits = _simulated(track, envelope, sectors, real_lateral)

    # -------------------------------------------------------- volta prevista --
    generator = load_model(config.artifacts_root() / "models" / "reference")
    predicted = generate(generator, track, corners)
    pred_result, pred_elapsed, pred_splits = _simulated(track, envelope, sectors, predicted.lateral)

    # ------------------------------------------------------ linha otimizada ---
    optimised_path = config.artifacts_root() / "optimization" / "optimised_lateral.npy"
    if not optimised_path.exists():
        raise SystemExit(
            f"tracado otimizado nao encontrado em {optimised_path}. "
            "Rode `python -m ml.scripts.optimize_line` antes."
        )
    optimised_lateral = np.load(optimised_path)
    opt_result, opt_elapsed, opt_splits = _simulated(track, envelope, sectors, optimised_lateral)

    real = TrajectorySeries(
        label="volta real",
        lateral=real_lateral,
        colour=REAL,
        speed_kmh=lap["speed_kmh"].to_numpy(dtype=float),
        elapsed_s=real_elapsed,
        splits=real_splits,
        lap_time_s=real_result.lap_time_s,
        measured_time_s=measured,
    )
    prevista = TrajectorySeries(
        label="volta prevista (LSTM)",
        lateral=predicted.lateral,
        colour=PREVISTA,
        speed_kmh=predicted.speed_kmh,
        elapsed_s=pred_elapsed,
        splits=pred_splits,
        lap_time_s=pred_result.lap_time_s,
        linestyle="--",
    )
    otimizada = TrajectorySeries(
        label="linha otimizada",
        lateral=optimised_lateral,
        colour=OTIMIZADA,
        speed_kmh=opt_result.speed_kmh,
        elapsed_s=opt_elapsed,
        splits=opt_splits,
        lap_time_s=opt_result.lap_time_s,
    )
    series = [real, prevista, otimizada]

    # ----------------------------------------------------------- onde diferem --
    # Os recortes vao para as **curvas** em que as linhas mais divergem, e nao
    # para os microsetores de maior separacao: os maiores afastamentos caem em
    # reta, onde a posicao lateral quase nao custa tempo, e um recorte de reta
    # nao mostra nada que valha ampliar.
    separation = np.abs(otimizada.lateral - real.lateral) + np.abs(prevista.lateral - real.lateral)
    if args.insets is not None:
        insets = args.insets
    else:
        scored = []
        for corner in corners:
            span = int(round(corner.length_m / track.step))
            index = (track.index_of(corner.start_s) + np.arange(span)) % track.size
            scored.append((float(separation[index].mean()), corner.apex_s))
        insets = [apex for _, apex in sorted(scored, reverse=True)[:3]]

    # --------------------------------------------------------------- saidas ---
    output = config.artifacts_root() / "comparison"
    output.mkdir(parents=True, exist_ok=True)

    files = [
        plot_track_map(
            track, series, output / "mapa_xy.png", corners=corners, insets=insets,
            title=f"Interlagos — volta real, prevista e otimizada",
        ),
        plot_microsector_delta(
            track, sectors, series, real, output / "microsetores.png", corners=corners,
            title="diferença por microsetor, contra a volta real (mesma física)",
        ),
        plot_profiles(track, series, output / "perfis.png", corners=corners),
        plot_lateral_separation(
            track, series, real, output / "separacao.png", corners=corners
        ),
    ]

    # ---------------------------------------------------------- resumo ---------
    print(f"volta real: {lap_id}")
    print(f"  medida    {measured:8.3f} s")
    print(f"  simulada  {real.lap_time_s:8.3f} s   ({real.lap_time_s - measured:+.3f} s de viés do modelo)\n")
    print("todas as trajetórias na mesma física:")
    for item in series:
        delta = item.lap_time_s - real.lap_time_s
        print(f"  {item.label:22s} {item.lap_time_s:8.3f} s   {delta:+7.3f} s   "
              f"percurso {np.sum(np.abs(np.diff(item.lateral))):6.0f} m de movimento lateral")

    table = pd.DataFrame(
        {
            "microsetor": [sectors.label(i) for i in range(sectors.count)],
            "real_s": np.round(real.splits, 4),
            "prevista_s": np.round(prevista.splits, 4),
            "otimizada_s": np.round(otimizada.splits, 4),
            "delta_prevista": np.round(prevista.splits - real.splits, 4),
            "delta_otimizada": np.round(otimizada.splits - real.splits, 4),
        }
    )
    table.to_csv(output / "microsetores.csv", index=False)

    print("\nmicrosetores em que a linha otimizada mais ganha:")
    for _, row in table.nsmallest(5, "delta_otimizada").iterrows():
        print(f"  {row['microsetor']:22s} {row['delta_otimizada']:+.3f} s")
    print("\nmicrosetores em que ela mais perde:")
    for _, row in table.nlargest(3, "delta_otimizada").iterrows():
        print(f"  {row['microsetor']:22s} {row['delta_otimizada']:+.3f} s")

    print(f"\ngráficos -> {output}")
    for item in files:
        print(f"  {item.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
