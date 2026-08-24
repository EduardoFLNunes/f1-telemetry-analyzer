"""O fluxo completo, de ponta a ponta, num comando.

    python -m ml.scripts.run_pipeline [--from-scratch] [--stage ETAPA]

    dataset -> pre-processamento -> LSTM -> inferencia -> rede substituta
            -> algoritmo evolutivo -> resultado final

Cada etapa e cronometrada e diz o que produziu e onde escreveu. Por padrao as
duas primeiras etapas reaproveitam o que ja esta em `data/ml/`, porque varrer
os 11 GB leva minutos; `--from-scratch` refaz tudo desde o JSONL.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np

from ml import config

STAGES = (
    "dataset",
    "preprocessamento",
    "lstm",
    "inferencia",
    "substituta",
    "evolutivo",
    "resultado",
)


@dataclass
class Stage:
    """Uma etapa executada: o que ela consumiu, produziu e quanto demorou."""

    name: str
    seconds: float
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    facts: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "etapa": self.name,
            "segundos": round(self.seconds, 2),
            "entrada": self.inputs,
            "saida": self.outputs,
            "medidas": self.facts,
        }


class Pipeline:
    """Executa as etapas em ordem, guardando o que cada uma produziu."""

    def __init__(self, verbose: bool = True):
        self.stages: List[Stage] = []
        self.verbose = verbose
        self.state: Dict[str, object] = {}

    def run(self, name: str, action: Callable[[], Stage]) -> Stage:
        if self.verbose:
            print(f"\n[{len(self.stages) + 1}/{len(STAGES)}] {name}", flush=True)
        started = time.time()
        stage = action()
        stage.seconds = time.time() - started
        self.stages.append(stage)
        if self.verbose:
            for key, value in stage.facts.items():
                print(f"      {key}: {value}")
            for item in stage.outputs:
                print(f"      -> {item}")
            print(f"      {stage.seconds:.1f}s")
        return stage


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fluxo completo do subsistema")
    parser.add_argument("--from-scratch", action="store_true", help="refaz inventario e store do JSONL")
    parser.add_argument("--retrain", action="store_true", help="treina as redes em vez de carregar")
    parser.add_argument("--generations", type=int, default=150)
    parser.add_argument("--population", type=int, default=80)
    args = parser.parse_args(argv)

    from ml.data.lap_store import load_store
    from ml.features.engineering import build_feature_frames
    from ml.features.performance import build_reference
    from ml.models.reference_line import generate
    from ml.models.training import load_model
    from ml.optimization.evolution import EvolutionConfig, evolve
    from ml.optimization.fitness import FitnessEvaluator, FitnessWeights, fit_shape_reference
    from ml.optimization.lap_time_model import simulate
    from ml.optimization.representation import build_encoding
    from ml.optimization.seed import build_population, composite_best_segments, lateral_by_lap
    from ml.optimization.surrogate import SurrogateFeatures
    from ml.optimization.vehicle_model import load_envelope
    from ml.preprocessing.splits import split_by_session
    from ml.track.corners import detect_corners
    from ml.track.geometry import load_geometry
    from ml.track.microsectors import build_microsectors

    pipeline = Pipeline()
    root = config.artifacts_root()

    # ------------------------------------------------------- 1. dataset -----
    def dataset() -> Stage:
        if args.from_scratch:
            from ml.data.inventory import save_inventory, scan_sessions
            from ml.data.recordings import list_sessions

            sessions = list_sessions()
            inventory = scan_sessions(sessions)
            path = save_inventory(inventory)
            valid = int(inventory["valid"].sum())
            return Stage(
                "dataset",
                0.0,
                inputs=[str(config.recordings_root())],
                outputs=[str(path)],
                facts={"sessoes": len(sessions), "voltas brutas": len(inventory), "aprovadas": valid},
            )
        from ml.data.inventory import load_inventory

        inventory = load_inventory()
        return Stage(
            "dataset",
            0.0,
            inputs=[str(root / "lap_inventory.parquet")],
            outputs=[],
            facts={
                "voltas brutas": len(inventory),
                "aprovadas": int(inventory["valid"].sum()),
                "sessoes": int(inventory["session_id"].nunique()),
            },
        )

    pipeline.run("dataset — telemetria gravada e inventario de voltas", dataset)

    # ---------------------------------------------- 2. pre-processamento ----
    def preprocessing() -> Stage:
        if args.from_scratch:
            from ml.data.lap_store import build_store, save_store

            store = build_store()
            path = save_store(store)
            outputs = [str(path)]
        else:
            store = load_store()
            outputs = []
        track = load_geometry()
        pipeline.state["store"] = store
        pipeline.state["track"] = track
        pipeline.state["sectors"] = build_microsectors(track)
        pipeline.state["corners"] = detect_corners(track)
        pipeline.state["split"] = split_by_session(store.laps)
        return Stage(
            "preprocessamento",
            0.0,
            inputs=[str(root / "lap_inventory.parquet")],
            outputs=outputs,
            facts={
                "voltas na grade": len(store.laps),
                "pontos por volta": store.grid_size,
                "passo": f"{track.length / store.grid_size:.2f} m",
                "divisao": pipeline.state["split"].summary(),
            },
        )

    pipeline.run("pre-processamento — limpeza, alinhamento e reamostragem", preprocessing)

    store = pipeline.state["store"]
    track = pipeline.state["track"]
    sectors = pipeline.state["sectors"]
    corners = pipeline.state["corners"]
    split = pipeline.state["split"]

    # ---------------------------------------------------------- 3. LSTM ----
    def lstm() -> Stage:
        reference = build_reference(store, track, sectors, split.train)
        pipeline.state["reference"] = reference
        frames = build_feature_frames(store, track, sectors, corners, reference)
        pipeline.state["frames"] = frames

        if args.retrain:
            from ml.models.sequences import REFERENCE_TASK, SURROGATE_TASK, build_sequences
            from ml.models.training import TrainConfig, save_model, train_model

            trained = {}
            for task in (REFERENCE_TASK, SURROGATE_TASK):
                model = train_model(
                    task,
                    build_sequences(frames, task, split.train),
                    build_sequences(frames, task, split.validation),
                    config=TrainConfig(epochs=40),
                    verbose=False,
                )
                save_model(model, root / "models" / task.name)
                trained[task.name] = model
        else:
            trained = {
                "reference": load_model(root / "models" / "reference"),
                "surrogate": load_model(root / "models" / "surrogate"),
            }
        pipeline.state["models"] = trained

        from ml.models.lstm import count_parameters

        return Stage(
            "lstm",
            0.0,
            inputs=[str(root / "laps_grid.parquet")],
            outputs=[str(root / "models" / name) for name in trained],
            facts={
                "geradora": f"{count_parameters(trained['reference'].model)} parametros, "
                f"melhor epoch {trained['reference'].best_epoch}",
                "substituta": f"{count_parameters(trained['surrogate'].model)} parametros, "
                f"melhor epoch {trained['surrogate'].best_epoch}",
                "volta ideal do piloto": f"{pipeline.state['reference'].theoretical_best_time:.3f} s",
            },
        )

    pipeline.run("LSTM — referencia do piloto, atributos e as duas redes", lstm)

    models = pipeline.state["models"]

    # --------------------------------------------------- 4. inferencia -----
    def inference() -> Stage:
        encoding = build_encoding(track)
        pipeline.state["encoding"] = encoding
        line = generate(models["reference"], track, corners, encoding=encoding)
        pipeline.state["lstm_line"] = line
        envelope = load_envelope()
        pipeline.state["envelope"] = envelope
        simulated = simulate(track, line.lateral, envelope)
        return Stage(
            "inferencia",
            0.0,
            inputs=[str(root / "models" / "reference")],
            outputs=[],
            facts={
                "consulta": "perda 0 s em todos os microsetores",
                "velocidade prevista": f"{line.speed_kmh.min():.0f} a {line.speed_kmh.max():.0f} km/h",
                "linha simulada": f"{simulated.lap_time_s:.3f} s",
            },
        )

    pipeline.run("inferencia — a linha de referencia com perda zero", inference)

    # -------------------------------------------------- 5. substituta ------
    def surrogate_stage() -> Stage:
        features = SurrogateFeatures(track, corners, trained=models["surrogate"])
        pipeline.state["features"] = features
        laterals = lateral_by_lap(store)
        pipeline.state["laterals"] = laterals
        shape = fit_shape_reference(track, np.vstack(list(laterals.values())))
        pipeline.state["shape"] = shape
        evaluator = FitnessEvaluator(
            track,
            pipeline.state["encoding"],
            pipeline.state["envelope"],
            shape,
            FitnessWeights(),
            models["surrogate"],
            features,
        )
        pipeline.state["evaluator"] = evaluator
        probe = evaluator.evaluate(
            pipeline.state["encoding"].encode(pipeline.state["lstm_line"].lateral)[None, :]
        )
        return Stage(
            "substituta",
            0.0,
            inputs=[str(root / "models" / "surrogate")],
            outputs=[],
            facts={
                "peso na aptidao": FitnessWeights().surrogate_weight,
                "tempo pela fisica": f"{float(probe['physical_time_s'][0]):.3f} s",
                "tempo pela rede": f"{float(probe['surrogate_time_s'][0]):.3f} s",
            },
        )

    pipeline.run("rede substituta — o termo de aptidao vindo do modelo", surrogate_stage)

    # -------------------------------------------------- 6. evolutivo ------
    def evolution() -> Stage:
        encoding = pipeline.state["encoding"]
        population = build_population(
            encoding,
            size=args.population,
            laterals={k: pipeline.state["laterals"][k] for k in split.train if k in pipeline.state["laterals"]},
            extra=[
                composite_best_segments(
                    track, sectors, pipeline.state["laterals"], pipeline.state["reference"].best_lap_per_sector
                ),
                pipeline.state["lstm_line"].lateral,
            ],
            seed=config.SPLIT_SEED,
        )
        result = evolve(
            pipeline.state["evaluator"],
            encoding,
            population,
            EvolutionConfig(
                generations=args.generations, population_size=args.population, seed=config.SPLIT_SEED
            ),
        )
        pipeline.state["result"] = result
        return Stage(
            "evolutivo",
            0.0,
            inputs=["populacao semeada com voltas reais + melhores trechos + linha da LSTM"],
            outputs=[],
            facts={
                "genes": encoding.genes,
                "geracoes": result.generations_run,
                "avaliacoes": result.evaluations,
                "custo": f"{result.initial_cost:.3f} -> {result.best_cost:.3f} s",
                "parada": result.stopped_by,
            },
        )

    pipeline.run("algoritmo evolutivo — busca sobre pontos de controle", evolution)

    # --------------------------------------------------- 7. resultado ------
    def final() -> Stage:
        result = pipeline.state["result"]
        envelope = pipeline.state["envelope"]
        optimised = simulate(track, result.best_lateral, envelope)
        best_lap = store.laps.iloc[0]
        real = simulate(track, store.lap(best_lap["lap_id"])["lateral"].to_numpy(dtype=float), envelope)

        directory = root / "optimization"
        directory.mkdir(parents=True, exist_ok=True)
        np.save(directory / "optimised_lateral.npy", result.best_lateral)
        return Stage(
            "resultado",
            0.0,
            inputs=[],
            outputs=[str(directory / "optimised_lateral.npy")],
            facts={
                "tracado otimizado": f"{optimised.lap_time_s:.3f} s simulados, {optimised.path_length_m:.0f} m",
                "melhor volta real": f"{best_lap['lap_time_s']:.3f} s medidos, {real.lap_time_s:.3f} s simulados",
                "diferenca": f"{optimised.lap_time_s - real.lap_time_s:+.3f} s",
            },
        )

    pipeline.run("resultado final — tracado otimizado e comparacao", final)

    total = sum(stage.seconds for stage in pipeline.stages)
    payload = {"etapas": [stage.to_dict() for stage in pipeline.stages], "segundos_totais": total}
    destination = root / "pipeline_run.json"
    destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{'etapa':<20}{'segundos':>10}")
    for stage in pipeline.stages:
        print(f"{stage.name:<20}{stage.seconds:>10.1f}")
    print(f"{'TOTAL':<20}{total:>10.1f}")
    print(f"\nregistro -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
