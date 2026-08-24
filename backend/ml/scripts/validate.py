"""Executa a validacao completa e escreve as evidencias em disco.

    python -m ml.scripts.validate [--quick] [--generations N]

Nao assume nada: mede o que os modelos treinados e a busca fazem sobre os dados
reais, e grava tudo em `data/ml/validation/` -- JSON com os numeros, um grafico
de custo por geracao e um relatorio legivel.
"""

from __future__ import annotations

import argparse
import json
import platform
import time
from pathlib import Path
from typing import Dict

import numpy as np

from ml import config
from ml.data.lap_store import load_store
from ml.features.engineering import build_feature_frames
from ml.features.performance import build_reference
from ml.models.reference_line import build_inputs, generate
from ml.models.sequences import REFERENCE_TASK, SURROGATE_TASK, build_sequences
from ml.models.training import load_model
from ml.optimization.evolution import EvolutionConfig
from ml.optimization.fitness import FitnessEvaluator, FitnessWeights, fit_shape_reference
from ml.optimization.representation import build_encoding
from ml.optimization.seed import build_population, composite_best_segments, lateral_by_lap
from ml.optimization.surrogate import SurrogateFeatures
from ml.optimization.vehicle_model import load_envelope
from ml.preprocessing.splits import split_by_session
from ml.track.corners import detect_corners
from ml.track.geometry import load_geometry
from ml.track.microsectors import build_microsectors
from ml.validation import gather, holdout, per_lap_error, responds_to_input, unknown_lap
from ml.validation.search import compare
from ml.visualization.telemetry_plots import plot_evolution_history


def _sanity_fast_vs_slow(generator, surrogate, features, track, corners, store, split) -> Dict[str, object]:
    """Entrada A (volta rapida) contra entrada B (volta lenta).

    Feito nas duas redes, porque "entrada" quer dizer coisas diferentes em cada
    uma: na geradora e o nivel de desempenho pedido, na substituta e a forma da
    linha.
    """
    fast = generate(generator, track, corners, sector_loss=0.0, lap_loss=0.0)
    slow = generate(generator, track, corners, sector_loss=0.5, lap_loss=8.0)

    inputs_fast = build_inputs(track, corners, sector_loss=0.0, lap_loss=0.0, trained=generator)[0]
    inputs_slow = build_inputs(track, corners, sector_loss=0.5, lap_loss=8.0, trained=generator)[0]
    generator_response = responds_to_input(generator, inputs_fast, inputs_slow)

    laps = store.laps.set_index("lap_id")
    known = [lap for lap in split.test if lap in laps.index] or list(laps.index)
    quickest = min(known, key=lambda lap: laps.loc[lap, "lap_time_s"])
    slowest = max(known, key=lambda lap: laps.loc[lap, "lap_time_s"])

    shapes = np.vstack(
        [store.lap(quickest)["lateral"].to_numpy(dtype=float), store.lap(slowest)["lateral"].to_numpy(dtype=float)]
    )
    from ml.models.sequences import drop_warmup, with_warmup

    pad = SURROGATE_TASK.window
    predicted = drop_warmup(surrogate.predict(with_warmup(features(shapes), pad)), pad)
    times = np.asarray(predicted, dtype=float)[..., 0].sum(axis=1)

    return {
        "geradora": {
            "entrada_A": "perda 0,0 s (volta rapida)",
            "entrada_B": "perda 0,5 s por microsetor, 8 s na volta (volta lenta)",
            **generator_response,
            "velocidade_media_A_kmh": float(fast.speed_kmh.mean()),
            "velocidade_media_B_kmh": float(slow.speed_kmh.mean()),
            "desvio_lateral_medio_m": float(np.mean(np.abs(fast.lateral - slow.lateral))),
            "saidas_diferentes": bool(not generator_response["identical"]),
        },
        "substituta": {
            "entrada_A": f"{quickest} ({laps.loc[quickest, 'lap_time_s']:.3f} s medidos)",
            "entrada_B": f"{slowest} ({laps.loc[slowest, 'lap_time_s']:.3f} s medidos)",
            "tempo_previsto_A_s": float(times[0]),
            "tempo_previsto_B_s": float(times[1]),
            "diferenca_s": float(times[1] - times[0]),
            "ordem_correta": bool(times[1] > times[0]),
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validacao do subsistema de ML")
    parser.add_argument("--generations", type=int, default=150)
    parser.add_argument("--population", type=int, default=80)
    parser.add_argument("--control-spacing", type=float, default=12.0)
    parser.add_argument("--quick", action="store_true", help="busca curta, so para fumaca")
    args = parser.parse_args(argv)
    if args.quick:
        args.generations, args.population = 20, 30

    started = time.time()
    output = config.artifacts_root() / "validation"
    output.mkdir(parents=True, exist_ok=True)
    evidence: Dict[str, object] = {
        "ambiente": {
            "python": platform.python_version(),
            "plataforma": platform.platform(),
            "processador": platform.processor(),
        }
    }

    print("carregando pista, store e modelos...", flush=True)
    track = load_geometry()
    sectors = build_microsectors(track)
    corners = detect_corners(track)
    store = load_store()
    envelope = load_envelope()
    split = split_by_session(store.laps)
    reference = build_reference(store, track, sectors, split.train)

    import torch

    evidence["ambiente"]["torch"] = torch.__version__
    evidence["ambiente"]["threads"] = torch.get_num_threads()
    evidence["dataset"] = {
        "voltas_utilizaveis": int(len(store.laps)),
        "sessoes": int(store.laps["session_id"].nunique()),
        "pontos_por_volta": int(store.grid_size),
        "linhas_no_store": int(len(store.frame)),
        "divisao": split.summary(),
    }

    print("montando atributos...", flush=True)
    frames = build_feature_frames(store, track, sectors, corners, reference)

    generator = load_model(config.artifacts_root() / "models" / "reference")
    surrogate = load_model(config.artifacts_root() / "models" / "surrogate")
    features = SurrogateFeatures(track, corners, trained=surrogate)

    # ------------------------------------------------ 2. a rede aprendeu? ---
    print("\n[2] a rede aprendeu?", flush=True)
    evidence["aprendizado"] = {}
    evidence["generalizacao"] = {}
    for task, trained in ((REFERENCE_TASK, generator), (SURROGATE_TASK, surrogate)):
        sets = {
            name: build_sequences(frames, task, getattr(split, name))
            for name in ("train", "validation", "test")
        }
        learning = gather(trained, task, sets["train"], sets["validation"], sets["test"])
        evidence["aprendizado"][task.name] = learning.to_dict()
        problems = learning.verdict()
        print(
            f"  {task.name:<10} perda {learning.first_train_loss:.5f} -> {learning.final_train_loss:.5f}"
            f"  ({learning.loss_reduction:.1%})   validacao {learning.best_validation_loss:.5f}"
            f"   {'OK' if not problems else 'PROBLEMAS: ' + '; '.join(problems)}"
        )

        report = holdout(trained, sets, task.name)
        report.lap_errors = per_lap_error(trained, sets["test"])
        payload = report.to_dict()
        worst = max(report.lap_errors, key=report.lap_errors.get)
        payload["volta_desconhecida"] = unknown_lap(trained, sets["test"], worst)
        evidence["generalizacao"][task.name] = payload

    # --------------------------------------- 2b. sanidade entrada A vs B ----
    print("\n[2b] sanidade: entrada A (rapida) contra entrada B (lenta)", flush=True)
    sanity = _sanity_fast_vs_slow(generator, surrogate, features, track, corners, store, split)
    evidence["sanidade"] = sanity
    print(
        f"  geradora   saidas diferentes: {sanity['geradora']['saidas_diferentes']}"
        f"   ({sanity['geradora']['velocidade_media_A_kmh']:.1f} vs "
        f"{sanity['geradora']['velocidade_media_B_kmh']:.1f} km/h)"
    )
    print(
        f"  substituta ordem correta: {sanity['substituta']['ordem_correta']}"
        f"   ({sanity['substituta']['tempo_previsto_A_s']:.2f} vs "
        f"{sanity['substituta']['tempo_previsto_B_s']:.2f} s)"
    )

    # ------------------------------------------ 2c. tempo de inferencia -----
    sample = build_sequences(frames, REFERENCE_TASK, split.test[:1]).inputs[:32]
    full_lap = build_inputs(track, corners, trained=generator)
    for label, batch, repeats in (("janela de 128 passos", sample, 5), ("volta inteira", full_lap, 5)):
        clock = time.time()
        for _ in range(repeats):
            generator.predict(batch)
        elapsed = (time.time() - clock) / repeats
        evidence.setdefault("inferencia", {})[label] = {
            "amostras": int(batch.shape[0]),
            "segundos": elapsed,
            "ms_por_amostra": 1000.0 * elapsed / batch.shape[0],
        }
        print(f"  inferencia {label:<22} {elapsed * 1000:7.1f} ms para {batch.shape[0]} amostra(s)")

    # ------------------------------------------- 4. a busca evoluiu? --------
    print("\n[4] a busca evoluiu, ou sorteou?", flush=True)
    laterals = lateral_by_lap(store)
    shape = fit_shape_reference(track, np.vstack(list(laterals.values())))
    encoding = build_encoding(track, spacing_m=args.control_spacing)
    lstm_line = generate(generator, track, corners, encoding=encoding)
    population = build_population(
        encoding,
        size=args.population,
        laterals={k: laterals[k] for k in split.train if k in laterals},
        extra=[composite_best_segments(track, sectors, laterals, reference.best_lap_per_sector), lstm_line.lateral],
        seed=config.SPLIT_SEED,
    )
    evaluator = FitnessEvaluator(track, encoding, envelope, shape, FitnessWeights(), surrogate, features)
    comparison = compare(
        evaluator,
        encoding,
        population,
        EvolutionConfig(generations=args.generations, population_size=args.population, seed=config.SPLIT_SEED),
        progress=lambda text: print(text, flush=True),
    )
    evidence["busca"] = comparison.to_dict()
    evidence["busca"]["genes"] = encoding.genes
    print(
        f"  cenario A {comparison.initial_cost:.3f} s -> cenario B {comparison.final_cost:.3f} s"
        f"   ({comparison.improvement:+.3f} s em {comparison.generations} geracoes)"
    )
    print(f"  com as mesmas {comparison.random_evaluations} avaliacoes:")
    print(
        f"    amostragem uniforme  {comparison.random_best_cost:9.3f} s"
        f"   (busca ganha {comparison.beats_random:+.3f} s)"
    )
    print(
        f"    perturbacao cega     {comparison.perturbation_best_cost:9.3f} s"
        f"   (busca ganha {comparison.beats_perturbation:+.3f} s)"
        f"   -> evolucao real: {comparison.real_evolution}"
    )

    chart = plot_evolution_history(
        comparison.history,
        output / "fitness_por_geracao.png",
        baseline=comparison.perturbation_best_cost,
        baseline_label="perturbacao cega das mesmas sementes",
    )

    # ------------------------------------------------------------ saidas ----
    evidence["segundos_totais"] = time.time() - started
    (output / "evidencias.json").write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nevidencias -> {output / 'evidencias.json'}")
    print(f"grafico    -> {chart}")
    print(f"concluido em {evidence['segundos_totais']:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
