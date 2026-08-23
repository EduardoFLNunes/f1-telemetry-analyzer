"""A LSTM, montada por configuracao.

Uma classe so serve as duas tarefas do sistema porque as duas tem a mesma forma:
entra uma sequencia de pontos de pista, sai um valor por ponto. O que muda e o
que entra, o que sai e o tamanho -- e isso e configuracao, nao codigo novo.

Decisoes que valem explicacao:

* **bidirecional por padrao no gerador.** O tracado ideal num ponto depende do
  que vem *depois* dele: onde frear e funcao da curva que ainda nao chegou. Uma
  LSTM causal nao tem essa informacao e produz uma referencia que freia tarde
  sistematicamente. Isto e possivel aqui porque a inferencia e sobre uma volta
  inteira ja conhecida, e nao em tempo real.
* **saida com ativacao por canal.** `brake` e `throttle` vivem em [0, 1] e uma
  saida linear os leva para -0,2 e 1,3; sigmoid neles poe o limite na
  arquitetura em vez de esperar que a perda o descubra. Os demais canais saem
  lineares e ja normalizados -- quem cuida da escala e o `TargetTransform`, e
  nao a ativacao, porque uma `softplus` para forcar positividade em velocidade
  comeca em 0,69 km/h e leva epocas so para alcancar a ordem de grandeza.
* **dropout entre camadas, nunca depois da ultima.** Aplicado na saida, ele
  vira ruido no proprio alvo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

try:  # pragma: no cover - depende do ambiente
    import torch
    from torch import nn

    TORCH_AVAILABLE = True
except ImportError:  # pragma: no cover
    torch = None
    nn = None
    TORCH_AVAILABLE = False


UNIT_INTERVAL_TARGETS = ("brake", "throttle", "clutch")


@dataclass
class LSTMConfig:
    """Tudo que define a arquitetura. Serializavel junto com os pesos."""

    input_size: int
    output_size: int
    hidden_size: int = 96
    layers: int = 2
    dropout: float = 0.15
    bidirectional: bool = True
    target_columns: Tuple[str, ...] = ()
    input_columns: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, object]:
        return {
            "input_size": self.input_size,
            "output_size": self.output_size,
            "hidden_size": self.hidden_size,
            "layers": self.layers,
            "dropout": self.dropout,
            "bidirectional": self.bidirectional,
            "target_columns": list(self.target_columns),
            "input_columns": list(self.input_columns),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "LSTMConfig":
        return cls(
            input_size=int(payload["input_size"]),
            output_size=int(payload["output_size"]),
            hidden_size=int(payload.get("hidden_size", 96)),
            layers=int(payload.get("layers", 2)),
            dropout=float(payload.get("dropout", 0.15)),
            bidirectional=bool(payload.get("bidirectional", True)),
            target_columns=tuple(payload.get("target_columns", ())),
            input_columns=tuple(payload.get("input_columns", ())),
        )


def _require_torch() -> None:
    if not TORCH_AVAILABLE:  # pragma: no cover
        raise ImportError(
            "PyTorch nao esta instalado nesta venv. "
            "Instale com: pip install --index-url https://download.pytorch.org/whl/cpu torch"
        )


if TORCH_AVAILABLE:

    class TrackSequenceLSTM(nn.Module):
        """Sequencia de pontos de pista -> sequencia de valores por ponto."""

        def __init__(self, config: LSTMConfig):
            super().__init__()
            self.config = config
            self.lstm = nn.LSTM(
                input_size=config.input_size,
                hidden_size=config.hidden_size,
                num_layers=config.layers,
                batch_first=True,
                dropout=config.dropout if config.layers > 1 else 0.0,
                bidirectional=config.bidirectional,
            )
            width = config.hidden_size * (2 if config.bidirectional else 1)
            self.head = nn.Linear(width, config.output_size)

            # Quais saidas passam por sigmoid e quais ficam lineares. Guardado
            # como buffer para viajar junto com o modelo salvo.
            unit = [
                1.0 if name in UNIT_INTERVAL_TARGETS else 0.0
                for name in config.target_columns
            ] or [0.0] * config.output_size
            self.register_buffer("unit_mask", torch.tensor(unit).view(1, 1, -1))

        def forward(self, inputs):
            sequence, _ = self.lstm(inputs)
            raw = self.head(sequence)
            return raw * (1.0 - self.unit_mask) + torch.sigmoid(raw) * self.unit_mask

        @torch.no_grad()
        def predict(self, inputs: np.ndarray, batch_size: int = 256) -> np.ndarray:
            """Inferencia em lotes.

            Em um lote so, avaliar as 9112 janelas do conjunto de treino aloca
            as ativacoes de todas elas ao mesmo tempo -- 9112 x 128 x 192
            floats por camada, alguns gigabytes -- e o processo morre com
            segmentation fault, sem traceback de Python que ajude.
            """
            self.eval()
            values = np.asarray(inputs, dtype=np.float32)
            if values.ndim == 2:
                values = values[None, :, :]
            chunks = [
                self.forward(torch.as_tensor(values[start : start + batch_size])).cpu().numpy()
                for start in range(0, values.shape[0], max(int(batch_size), 1))
            ]
            return np.concatenate(chunks, axis=0)

else:  # pragma: no cover

    class TrackSequenceLSTM:  # type: ignore[no-redef]
        def __init__(self, *_args, **_kwargs):
            _require_torch()


def build_model(config: LSTMConfig) -> "TrackSequenceLSTM":
    _require_torch()
    return TrackSequenceLSTM(config)


def count_parameters(model) -> int:
    _require_torch()
    return int(sum(p.numel() for p in model.parameters() if p.requires_grad))
