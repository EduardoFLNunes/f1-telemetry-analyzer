"""A rede aprendeu, ou so parece que aprendeu?

Existir codigo de treino nao prova que houve treino, e uma perda que cai nao
prova que o modelo serve. Cada funcao aqui responde uma pergunta que pode ser
respondida com **nao**, e devolve o numero que sustenta a resposta.

As quatro maneiras de uma LSTM parecer treinada sem estar:

* a perda cai porque o modelo aprendeu a media do alvo e nada mais;
* a saida e praticamente constante, e o erro medio fica parecido com o desvio
  do alvo;
* os pesos treinados nao sao melhores que pesos sorteados;
* entradas diferentes produzem a mesma saida -- o modelo ignora a entrada.

Todas sao medidas abaixo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np

from ..models.lstm import LSTMConfig, TrackSequenceLSTM
from ..models.sequences import SequenceSet, TaskSpec
from ..models.training import TrainedModel, evaluate

# Abaixo disto a saida de um canal e constante para efeitos praticos: o desvio
# previsto e menos de 1% do desvio do alvo.
CONSTANT_OUTPUT_RATIO = 0.01


@dataclass
class LearningEvidence:
    """O que foi medido sobre o treino de uma rede."""

    task: str
    parameters: int
    epochs_run: int
    best_epoch: int
    first_train_loss: float
    final_train_loss: float
    best_validation_loss: float
    final_validation_loss: float
    train_windows: int
    validation_windows: int
    channels: Dict[str, Dict[str, float]] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    @property
    def loss_fell(self) -> bool:
        return self.final_train_loss < self.first_train_loss

    @property
    def loss_reduction(self) -> float:
        """Quanto a perda de treino caiu, como fracao da inicial."""
        if self.first_train_loss <= 0:
            return float("nan")
        return 1.0 - self.final_train_loss / self.first_train_loss

    @property
    def overfitting_ratio(self) -> float:
        """Validacao dividida por treino no melhor epoch.

        Perto de 1 as duas curvas andam juntas. Bem acima de 1 o modelo esta
        decorando -- com 60 voltas de treino isso e o desfecho esperado se nada
        o impedir, e por isso o numero e reportado em vez de assumido.
        """
        if self.final_train_loss <= 0:
            return float("nan")
        return self.best_validation_loss / self.final_train_loss

    def verdict(self) -> List[str]:
        """Os problemas encontrados. Lista vazia quer dizer que passou."""
        problems: List[str] = []
        if not self.loss_fell:
            problems.append("a perda de treino nao caiu")
        for channel, values in self.channels.items():
            if values.get("mae_trained", 0) >= values.get("mae_untrained", 0):
                problems.append(f"{channel}: nao bate pesos aleatorios")
            if values.get("mae_trained", 0) >= values.get("mae_mean_predictor", 0):
                problems.append(f"{channel}: nao bate o preditor da media")
            if values.get("output_std_ratio", 1.0) < CONSTANT_OUTPUT_RATIO:
                problems.append(f"{channel}: saida praticamente constante")
        return problems

    def to_dict(self) -> Dict[str, object]:
        return {
            "task": self.task,
            "parameters": self.parameters,
            "epochs_run": self.epochs_run,
            "best_epoch": self.best_epoch,
            "first_train_loss": self.first_train_loss,
            "final_train_loss": self.final_train_loss,
            "best_validation_loss": self.best_validation_loss,
            "final_validation_loss": self.final_validation_loss,
            "loss_reduction": self.loss_reduction,
            "overfitting_ratio": self.overfitting_ratio,
            "train_windows": self.train_windows,
            "validation_windows": self.validation_windows,
            "channels": self.channels,
            "problems": self.verdict(),
            "notes": self.notes,
        }


def untrained_twin(trained: TrainedModel, seed: int = 0) -> TrainedModel:
    """A mesma arquitetura com pesos nunca treinados.

    Guarda o mesmo `scaler` e a mesma transformacao de saida de proposito: o
    que se quer isolar e o efeito dos pesos, e nao o da normalizacao.
    """
    import torch

    torch.manual_seed(seed)
    return TrainedModel(
        model=TrackSequenceLSTM(trained.config),
        config=trained.config,
        scaler=trained.scaler,
        transform=trained.transform,
        task_name=f"{trained.task_name}_sem_treino",
    )


def mean_predictor_error(train: SequenceSet, test: SequenceSet, channel: int) -> float:
    """Erro de responder sempre a media do canal vista no treino."""
    mean_value = float(np.mean(train.targets[..., channel]))
    return float(np.mean(np.abs(test.targets[..., channel] - mean_value)))


def output_spread(trained: TrainedModel, dataset: SequenceSet, limit: int = 256) -> Dict[str, Dict[str, float]]:
    """Desvio da saida contra o desvio do alvo, canal a canal."""
    predicted = trained.predict(dataset.inputs[:limit])
    out: Dict[str, Dict[str, float]] = {}
    for index, channel in enumerate(dataset.target_columns):
        values = predicted[..., index]
        target = dataset.targets[:limit, ..., index]
        target_std = float(np.std(target))
        out[channel] = {
            "output_std": float(np.std(values)),
            "target_std": target_std,
            "output_std_ratio": float(np.std(values) / target_std) if target_std > 0 else 0.0,
            "output_min": float(np.min(values)),
            "output_max": float(np.max(values)),
        }
    return out


def gather(
    trained: TrainedModel,
    task: TaskSpec,
    train: SequenceSet,
    validation: SequenceSet,
    test: SequenceSet,
) -> LearningEvidence:
    """Junta todas as evidencias sobre uma rede treinada."""
    from ..models.lstm import count_parameters

    history = trained.history or []
    trained_metrics = evaluate(trained, test)
    untrained_metrics = evaluate(untrained_twin(trained), test)
    spread = output_spread(trained, test)

    channels: Dict[str, Dict[str, float]] = {}
    for index, channel in enumerate(task.targets):
        channels[channel] = {
            "mae_trained": trained_metrics[f"mae_{channel}"],
            "mae_untrained": untrained_metrics[f"mae_{channel}"],
            "mae_mean_predictor": mean_predictor_error(train, test, index),
            "rmse_trained": trained_metrics[f"rmse_{channel}"],
            "skill": trained_metrics[f"skill_{channel}"],
            **spread[channel],
        }

    return LearningEvidence(
        task=task.name,
        parameters=count_parameters(trained.model),
        epochs_run=len(history),
        best_epoch=trained.best_epoch,
        first_train_loss=float(history[0]["train_loss"]) if history else float("nan"),
        final_train_loss=float(history[-1]["train_loss"]) if history else float("nan"),
        best_validation_loss=float(trained.best_validation),
        final_validation_loss=float(history[-1]["validation_loss"]) if history else float("nan"),
        train_windows=len(train),
        validation_windows=len(validation),
        channels=channels,
    )


def responds_to_input(
    trained: TrainedModel, first: np.ndarray, second: np.ndarray
) -> Dict[str, float]:
    """Entradas diferentes produzem saidas diferentes?

    O teste que pega o modo de falha mais silencioso de todos: uma rede que
    ignora a entrada e responde sempre a mesma coisa acerta a media, tem perda
    baixa e nao serve para nada.
    """
    output_a = trained.predict(np.asarray(first, dtype=np.float32)[None, ...])[0]
    output_b = trained.predict(np.asarray(second, dtype=np.float32)[None, ...])[0]
    difference = np.abs(output_a - output_b)
    return {
        "input_difference_mean": float(np.mean(np.abs(np.asarray(first) - np.asarray(second)))),
        "output_difference_mean": float(np.mean(difference)),
        "output_difference_max": float(np.max(difference)),
        "identical": bool(np.allclose(output_a, output_b)),
    }
