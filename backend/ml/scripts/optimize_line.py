"""Otimiza o tracado com o algoritmo evolutivo.

    python -m ml.scripts.optimize_line [--generations N] [--population N]
                                       [--surrogate-weight 0.25] [--no-lstm]

Depende do store, do envelope (`ml.scripts.fit_envelope`) e, opcionalmente, dos
modelos treinados (`ml.scripts.train_models`). Sem os modelos a busca roda so
com a fisica medida, e diz isso.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from ml import config
from ml.data.lap_store import load_store
from ml.features.performance import build_reference
from ml.optimization.evolution import EvolutionConfig, evolve
from ml.optimization.fitness import (
    FitnessEvaluator,
    FitnessWeights,
    ShapeReference,
    fit_shape_reference,
)
from ml.optimization.lap_time_model import simulate
from ml.optimization.representation import DEFAULT_CONTROL_SPACING_M, build_encoding
from ml.optimization.seed import build_population, composite_best_segments, lateral_by_lap
from ml.optimization.surrogate import SurrogateFeatures
from ml.optimization.vehicle_model import load_envelope
from ml.preprocessing.splits import split_by_session
from ml.track.corners import detect_corners
from ml.track.geometry import load_geometry
from ml.track.microsectors import build_microsectors
from ml.visualization.telemetry_plots import plot_evolution_history
from ml.visualization.track_plots import plot_trajectories


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Otimizacao evolutiva do tracado")
    parser.add_argument("--generations", type=int, default=120)
    parser.add_argument("--population", type=int, default=80)
    parser.add_argument("--surrogate-weight", type=float, default=0.25)
    parser.add_argument(
        "--control-spacing", type=float, default=DEFAULT_CONTROL_SPACING_M
    )
    parser.add_argument("--no-lstm", action="store_true", help="so fisica na aptidao")
    parser.add_argument("--seed", type=int, default=config.SPLIT_SEED)
    args = parser.parse_args(argv)

    started = time.time()
    track = load_geometry()
    sectors = build_microsectors(track)
    corners = detect_corners(track)
    store = load_store()
    envelope = load_envelope()
    split = split_by_session(store.laps)
    reference = build_reference(store, track, sectors, split.train)

    print(f"pista: {track.name} | {len(store.laps)} voltas | {len(corners)} curvas")
    print(
        f"referencia do piloto: melhor {reference.best_lap_time:.3f}s, "
        f"ideal {reference.theoretical_best_time:.3f}s"
    )

    laterals = lateral_by_lap(store)
    shape = fit_shape_reference(track, np.vstack(list(laterals.values())))

    # ---------------------------------------------------------- sementes ---
    composite = composite_best_segments(
        track, sectors, laterals, reference.best_lap_per_sector
    )
    extra = [composite]
    labels = ["melhores trechos"]

    surrogate = None
    surrogate_features = None
    model_root = config.artifacts_root() / "models"
    if not args.no_lstm and (model_root / "reference" / "model.json").exists():
        from ml.models.reference_line import generate
        from ml.models.training import load_model

        generator_model = load_model(model_root / "reference")
        lstm_line = generate(generator_model, track, corners)
        extra.append(lstm_line.lateral)
        labels.append("referencia LSTM")
        print("semente da LSTM: carregada")
    else:
        print("semente da LSTM: ausente (rodando so com a fisica)")

    if not args.no_lstm and (model_root / "surrogate" / "model.json").exists():
        from ml.models.training import load_model

        surrogate = load_model(model_root / "surrogate")
        surrogate_features = SurrogateFeatures(track, corners, trained=surrogate)
        print("rede substituta: carregada")
    else:
        print("rede substituta: ausente (aptidao 100% fisica)")

    encoding = build_encoding(track, spacing_m=args.control_spacing)
    print(f"codificacao: {encoding.genes} pontos de controle a cada {args.control_spacing:.0f} m")

    population = build_population(
        encoding,
        size=args.population,
        laterals={k: laterals[k] for k in split.train if k in laterals},
        extra=extra,
        seed=args.seed,
    )

    weights = FitnessWeights(
        surrogate_weight=0.0 if surrogate is None else args.surrogate_weight
    )
    evaluator = FitnessEvaluator(
        track, encoding, envelope, shape, weights, surrogate, surrogate_features
    )

    # ------------------------------------------------------- referencias ---
    best_lap_lateral = laterals[reference.best_lap_id]
    baseline = simulate(track, best_lap_lateral, envelope)
    composite_sim = simulate(track, composite, envelope)

    # A mesma volta, passada pela codificacao. E ela, e nao a volta crua, que e
    # a linha de base honesta: o algoritmo evolutivo so consegue produzir
    # trajetorias representaveis pelos pontos de controle, entao comparar o
    # resultado dele com uma trajetoria que ele nao poderia gerar mistura ganho
    # de tracado com custo de representacao.
    encoded_baseline = simulate(
        track, encoding.decode(encoding.encode(best_lap_lateral)), envelope
    )
    print(
        f"\nmelhor volta real:      medido {reference.best_lap_time:.3f}s | "
        f"simulado {baseline.lap_time_s:.3f}s | {baseline.path_length_m:.0f} m"
    )
    print(
        f"  a mesma, codificada:  simulado {encoded_baseline.lap_time_s:.3f}s "
        f"({encoded_baseline.lap_time_s - baseline.lap_time_s:+.3f}s de custo de representacao)"
    )
    print(
        f"melhores trechos:       simulado {composite_sim.lap_time_s:.3f}s | "
        f"{composite_sim.path_length_m:.0f} m"
    )

    # ----------------------------------------------------------- evolucao ---
    print(f"\nevoluindo {args.population} individuos por ate {args.generations} geracoes...")
    result = evolve(
        evaluator,
        encoding,
        population,
        EvolutionConfig(
            generations=args.generations, population_size=args.population, seed=args.seed
        ),
        progress=lambda text: print(text, flush=True),
    )

    optimised = simulate(track, result.best_lateral, envelope)
    detail = evaluator.report(result.best_genome)
    print(f"\nparada por {result.stopped_by} apos {result.generations_run} geracoes")
    print(f"custo inicial {result.initial_cost:.3f}s -> final {result.best_cost:.3f}s")
    print(
        f"tracado otimizado: simulado {optimised.lap_time_s:.3f}s | "
        f"{optimised.path_length_m:.0f} m | penalizacoes {detail.penalty_total:.4f}s"
    )
    print(
        f"ganho sobre a melhor volta real codificada (mesma representacao): "
        f"{encoded_baseline.lap_time_s - optimised.lap_time_s:+.3f}s"
    )
    print(
        f"ganho sobre a melhor volta real crua:               "
        f"{baseline.lap_time_s - optimised.lap_time_s:+.3f}s"
    )

    # ------------------------------------------------------------ saidas ---
    output_root = config.artifacts_root() / "optimization"
    output_root.mkdir(parents=True, exist_ok=True)
    np.save(output_root / "optimised_lateral.npy", result.best_lateral)
    np.save(output_root / "optimised_speed_mps.npy", optimised.speed_mps)
    (output_root / "result.json").write_text(
        json.dumps(
            {
                "seed": args.seed,
                "generations_run": result.generations_run,
                "evaluations": result.evaluations,
                "stopped_by": result.stopped_by,
                "initial_cost": result.initial_cost,
                "best_cost": result.best_cost,
                "weights": weights.to_dict(),
                "shape_reference": shape.to_dict(),
                "baseline": {
                    "lap_id": reference.best_lap_id,
                    "measured_s": reference.best_lap_time,
                    "simulated_s": baseline.lap_time_s,
                    "simulated_encoded_s": encoded_baseline.lap_time_s,
                    "path_length_m": baseline.path_length_m,
                },
                "composite": {
                    "simulated_s": composite_sim.lap_time_s,
                    "path_length_m": composite_sim.path_length_m,
                },
                "optimised": {
                    "simulated_s": optimised.lap_time_s,
                    "path_length_m": optimised.path_length_m,
                    "penalties": detail.penalties,
                },
                "history": result.history,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    plot_evolution_history(result.history, output_root / "evolucao.png")
    trajectories = [
        (f"melhor volta real ({reference.best_lap_time:.3f}s)", track.s, best_lap_lateral),
        (f"melhores trechos ({composite_sim.lap_time_s:.3f}s sim.)", track.s, composite),
        (f"tracado otimizado ({optimised.lap_time_s:.3f}s sim.)", track.s, result.best_lateral),
    ]
    for label, lateral in zip(labels[1:], extra[1:]):
        trajectories.insert(2, (label, track.s, lateral))
    image = plot_trajectories(
        track, trajectories, output_root / "optimised_line.png", title="Interlagos — tracado otimizado"
    )
    print(f"\nresultados -> {output_root}\nmapa -> {image}")
    print(f"concluido em {time.time() - started:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
