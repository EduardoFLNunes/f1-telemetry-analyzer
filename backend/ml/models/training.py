"""Treino e avaliacao da LSTM.

O laco e comum; o que merece explicacao sao as escolhas.

* **parada por validacao, com o melhor estado guardado.** Com 71 voltas de
  treino a rede decora rapido. O criterio de parada olha a validacao, e o modelo
  devolvido e o do melhor epoch, nao o do ultimo.
* **erro absoluto e nao quadratico.** A telemetria tem trechos com buraco de
  amostragem que a interpolacao alisa; sob erro quadratico esses pontos puxam o
  treino inteiro. `SmoothL1` se comporta como quadratico perto do acerto e como
  absoluto longe dele, que e o que se quer de um outlier.
* **a escala das saidas vem do `TargetTransform`.** Sem isso a perda somaria
  metros de deslocamento lateral com quilometros por hora, e o canal de maior
  variancia treinaria sozinho.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..features.scaling import StandardScaler, TargetTransform, fit_scaler, fit_target_transform
from .lstm import LSTMConfig, TrackSequenceLSTM, TORCH_AVAILABLE, _require_torch
from .sequences import SequenceSet, TaskSpec

if TORCH_AVAILABLE:  # pragma: no cover - depende do ambiente
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset


@dataclass
class TrainConfig:
    epochs: int = 60
    batch_size: int = 64
    learning_rate: float = 2e-3
    weight_decay: float = 1e-4
    patience: int = 10
    seed: int = 20260823
    grad_clip: float = 1.0

    def to_dict(self) -> Dict[str, object]:
        return {
            "epochs": self.epochs,
            "batch_size": self.batch_size,
            "learning_rate": self.learning_rate,
            "weight_decay": self.weight_decay,
            "patience": self.patience,
            "seed": self.seed,
            "grad_clip": self.grad_clip,
        }


@dataclass
class TrainedModel:
    """O modelo e tudo que e preciso para usa-lo de novo."""

    model: object
    config: LSTMConfig
    scaler: StandardScaler
    transform: TargetTransform
    task_name: str
    history: List[Dict[str, float]] = field(default_factory=list)
    best_epoch: int = 0
    best_validation: float = float("nan")

    def predict(self, inputs: np.ndarray, batch_size: int = 256) -> np.ndarray:
        """(n, passos, n_in) cru -> (n, passos, n_out) nas unidades originais."""
        scaled = self.scaler.transform(np.asarray(inputs, dtype=np.float32))
        raw = self.model.predict(scaled, batch_size=batch_size)
        return self.transform.inverse(raw)


def _loaders(train: SequenceSet, validation: Optional[SequenceSet], scaler, transform, config):
    _require_torch()
    inputs = torch.as_tensor(scaler.transform(train.inputs).astype(np.float32))
    targets = torch.as_tensor(transform.forward(train.targets).astype(np.float32))
    train_loader = DataLoader(
        TensorDataset(inputs, targets),
        batch_size=config.batch_size,
        shuffle=True,
        drop_last=False,
    )
    validation_loader = None
    if validation is not None and len(validation):
        validation_loader = DataLoader(
            TensorDataset(
                torch.as_tensor(scaler.transform(validation.inputs).astype(np.float32)),
                torch.as_tensor(transform.forward(validation.targets).astype(np.float32)),
            ),
            batch_size=config.batch_size,
            shuffle=False,
        )
    return train_loader, validation_loader


def train_model(
    task: TaskSpec,
    train: SequenceSet,
    validation: Optional[SequenceSet] = None,
    model_config: Optional[LSTMConfig] = None,
    config: Optional[TrainConfig] = None,
    verbose: bool = True,
) -> TrainedModel:
    """Treina a rede da tarefa e devolve o melhor estado visto na validacao."""
    _require_torch()
    settings = config or TrainConfig()
    torch.manual_seed(settings.seed)
    np.random.seed(settings.seed)

    scaler = fit_scaler(train.inputs, train.input_columns)
    transform = fit_target_transform(train.targets, train.target_columns)

    architecture = model_config or LSTMConfig(
        input_size=train.inputs.shape[-1],
        output_size=train.targets.shape[-1],
        target_columns=tuple(train.target_columns),
        input_columns=tuple(train.input_columns),
    )
    model = TrackSequenceLSTM(architecture)
    optimiser = torch.optim.AdamW(
        model.parameters(), lr=settings.learning_rate, weight_decay=settings.weight_decay
    )
    schedule = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimiser, mode="min", factor=0.5, patience=max(settings.patience // 3, 2)
    )
    criterion = nn.SmoothL1Loss(beta=0.5)

    train_loader, validation_loader = _loaders(train, validation, scaler, transform, settings)

    history: List[Dict[str, float]] = []
    best_state = None
    best_score = float("inf")
    best_epoch = 0
    started = time.time()

    for epoch in range(1, settings.epochs + 1):
        model.train()
        running = 0.0
        seen = 0
        for batch_inputs, batch_targets in train_loader:
            optimiser.zero_grad()
            prediction = model(batch_inputs)
            loss = criterion(prediction, batch_targets)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), settings.grad_clip)
            optimiser.step()
            running += float(loss.item()) * batch_inputs.shape[0]
            seen += batch_inputs.shape[0]
        train_loss = running / max(seen, 1)

        validation_loss = float("nan")
        if validation_loader is not None:
            model.eval()
            running, seen = 0.0, 0
            with torch.no_grad():
                for batch_inputs, batch_targets in validation_loader:
                    loss = criterion(model(batch_inputs), batch_targets)
                    running += float(loss.item()) * batch_inputs.shape[0]
                    seen += batch_inputs.shape[0]
            validation_loss = running / max(seen, 1)
            schedule.step(validation_loss)

        score = validation_loss if validation_loader is not None else train_loss
        history.append(
            {
                "epoch": epoch,
                "train_loss": train_loss,
                "validation_loss": validation_loss,
                "learning_rate": float(optimiser.param_groups[0]["lr"]),
            }
        )
        if score < best_score - 1e-5:
            best_score, best_epoch = score, epoch
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        if verbose:
            print(
                f"  epoch {epoch:3d}  treino={train_loss:.5f}  validacao={validation_loss:.5f}"
                f"  (melhor: {best_epoch})",
                flush=True,
            )
        if epoch - best_epoch >= settings.patience:
            if verbose:
                print(f"  parada antecipada: {settings.patience} epocas sem melhora")
            break

    if best_state is not None:
        model.load_state_dict(best_state)
    if verbose:
        print(f"  treino concluido em {time.time() - started:.0f}s, melhor epoch {best_epoch}")

    return TrainedModel(
        model=model,
        config=architecture,
        scaler=scaler,
        transform=transform,
        task_name=task.name,
        history=history,
        best_epoch=best_epoch,
        best_validation=best_score,
    )


def evaluate(trained: TrainedModel, dataset: SequenceSet) -> Dict[str, float]:
    """Erro por canal, nas unidades originais -- que e como se julga o modelo.

    A perda de treino esta em espaco normalizado e nao diz nada a ninguem. Aqui
    sai "erro medio de X metros no deslocamento lateral", que da para comparar
    com a largura da pista.
    """
    predicted = trained.predict(dataset.inputs)
    actual = np.asarray(dataset.targets, dtype=float)
    metrics: Dict[str, float] = {"windows": float(len(dataset))}
    for index, name in enumerate(dataset.target_columns):
        residual = predicted[..., index] - actual[..., index]
        finite = np.isfinite(residual)
        metrics[f"mae_{name}"] = float(np.mean(np.abs(residual[finite])))
        metrics[f"rmse_{name}"] = float(np.sqrt(np.mean(residual[finite] ** 2)))
        spread = float(np.std(actual[..., index][finite]))
        metrics[f"skill_{name}"] = (
            float(1.0 - metrics[f"rmse_{name}"] / spread) if spread > 1e-9 else float("nan")
        )
    return metrics


def save_model(trained: TrainedModel, directory: Path) -> Path:
    """Grava pesos, arquitetura, escalas e historico no mesmo lugar."""
    _require_torch()
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    torch.save(trained.model.state_dict(), directory / "weights.pt")
    (directory / "model.json").write_text(
        json.dumps(
            {
                "task": trained.task_name,
                "config": trained.config.to_dict(),
                "scaler": trained.scaler.to_dict(),
                "transform": trained.transform.to_dict(),
                "best_epoch": trained.best_epoch,
                "best_validation": trained.best_validation,
                "history": trained.history,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return directory


def load_model(directory: Path) -> TrainedModel:
    _require_torch()
    directory = Path(directory)
    payload = json.loads((directory / "model.json").read_text(encoding="utf-8"))
    architecture = LSTMConfig.from_dict(payload["config"])
    model = TrackSequenceLSTM(architecture)
    model.load_state_dict(torch.load(directory / "weights.pt", map_location="cpu"))
    model.eval()
    return TrainedModel(
        model=model,
        config=architecture,
        scaler=StandardScaler.from_dict(payload["scaler"]),
        transform=TargetTransform.from_dict(payload["transform"]),
        task_name=str(payload.get("task", "")),
        history=list(payload.get("history", [])),
        best_epoch=int(payload.get("best_epoch", 0)),
        best_validation=float(payload.get("best_validation", float("nan"))),
    )
