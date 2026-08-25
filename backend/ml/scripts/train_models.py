"""Treina as duas redes do sistema.

    python -m ml.scripts.train_models [--epochs N] [--task reference|surrogate|ambas]

Depende do store (`ml.scripts.build_lap_store`).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from ml import config
from ml.data.lap_store import load_store
from ml.features.engineering import build_feature_frames
from ml.features.performance import build_reference
from ml.models.sequences import REFERENCE_TASK, SURROGATE_TASK, build_sequences
from ml.models.training import TrainConfig, evaluate, save_model, train_model
from ml.preprocessing.splits import describe, split_by_session
from ml.track.corners import detect_corners
from ml.track.geometry import load_geometry
from ml.track.microsectors import build_microsectors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Treino das redes de tracado")
    parser.add_argument("--epochs", type=int, default=TrainConfig.epochs)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--hidden", type=int, default=96)
    parser.add_argument("--layers", type=int, default=2)
    parser.add_argument("--task", choices=("reference", "surrogate", "ambas"), default="ambas")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    started = time.time()
    track = load_geometry()
    sectors = build_microsectors(track)
    corners = detect_corners(track)
    store = load_store()
    print(f"pista: {track.name} | {store.laps.shape[0]} voltas | {len(corners)} curvas")

    split = split_by_session(store.laps)
    print("\n" + describe(split, store.laps).to_string(index=False))

    reference = build_reference(store, track, sectors, split.train)
    print(
        f"\nreferencia: melhor volta {reference.best_lap_time:.3f}s, "
        f"volta ideal {reference.theoretical_best_time:.3f}s "
        f"(sobrando {reference.available_gain:.3f}s)"
    )

    print("\nmontando atributos...", flush=True)
    frames = build_feature_frames(store, track, sectors, corners, reference)

    output_root = config.artifacts_root() / "models"
    results = {}
    tasks = (
        [REFERENCE_TASK, SURROGATE_TASK]
        if args.task == "ambas"
        else [REFERENCE_TASK if args.task == "reference" else SURROGATE_TASK]
    )

    for task in tasks:
        print(f"\n=== tarefa `{task.name}` ===", flush=True)
        train_set = build_sequences(frames, task, split.train)
        validation_set = build_sequences(frames, task, split.validation)
        test_set = build_sequences(frames, task, split.test)
        print(
            f"janelas: treino={len(train_set)} validacao={len(validation_set)} teste={len(test_set)}"
            f" | entradas={len(task.inputs)} saidas={len(task.targets)}"
            f" | janela={task.window} passos ({task.window_meters:.0f} m)"
        )

        from ml.models.lstm import LSTMConfig

        architecture = LSTMConfig(
            input_size=train_set.inputs.shape[-1],
            output_size=train_set.targets.shape[-1],
            hidden_size=args.hidden,
            layers=args.layers,
            target_columns=tuple(task.targets),
            input_columns=tuple(task.inputs),
        )
        trained = train_model(
            task,
            train_set,
            validation_set,
            model_config=architecture,
            config=TrainConfig(epochs=args.epochs, batch_size=args.batch_size),
            verbose=not args.quiet,
        )
        metrics = {
            "train": evaluate(trained, train_set),
            "validation": evaluate(trained, validation_set),
            "test": evaluate(trained, test_set),
        }
        results[task.name] = metrics
        print("\nerro nas unidades originais:")
        for part, values in metrics.items():
            summary = "  ".join(
                f"{key.split('_', 1)[1]}={value:.4f}"
                for key, value in values.items()
                if key.startswith("mae_")
            )
            print(f"  {part:11s} {summary}")

        directory = save_model(trained, output_root / task.name)
        print(f"modelo -> {directory}")

    (output_root / "metrics.json").write_text(
        json.dumps(
            {
                "split": split.to_dict(),
                "reference": reference.to_dict(),
                "metrics": results,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\nconcluido em {time.time() - started:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
