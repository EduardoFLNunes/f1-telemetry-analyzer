"""A trajetoria de referencia que a LSTM produz.

O gerador foi treinado com o quanto cada volta perdeu para a melhor do piloto
entrando como atributo. Perguntar a ele o que acontece quando essa perda e zero
e perguntar como se dirige quando se e o mais rapido que ja se foi -- em todos
os microsetores ao mesmo tempo, que e uma volta que o piloto nunca deu.

E o que separa isto de uma media. A media das voltas responderia "o que costuma
acontecer aqui"; a rede condicionada responde "o que acontece aqui quando aqui
vai bem".

A saida passa por dois ajustes, ambos por razao fisica e nao estetica:

* **clipe no corredor** — a rede nao conhece os limites da pista, so os viu.
  Onde ela extrapola para fora, a pista manda.
* **projecao no espaco de trajetorias** — a rede produz `lateral` ponto a ponto
  e nao garante continuidade de curvatura. A saida e reajustada nos mesmos
  pontos de controle que o algoritmo evolutivo usa, o que remove o ruido sem
  mexer na forma.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Sequence

import numpy as np
import pandas as pd

from .. import config
from ..features.engineering import track_features
from ..track.corners import Corner
from ..track.geometry import TrackGeometry
from ..track.microsectors import Microsectors
from ..track.trajectory import clip_to_corridor
from .sequences import REFERENCE_TASK, TaskSpec, drop_warmup, with_warmup

# Contexto de reserva, usado so quando nao ha modelo de onde tirar o real.
#
# O contexto neutro de verdade e a **media com que o modelo foi treinado**, e ela
# sai do proprio `StandardScaler` do modelo. Numeros "ideais" escolhidos a mao
# quebram a inferencia: pedir a linha com `grip_index = 1.0` quando toda volta
# do dataset tem 0,77 e pedir uma extrapolacao de cinco desvios-padrao, e o que
# voltava era uma volta inteira a fundo, sem frear em lugar nenhum e com
# velocidade minima de 233 km/h numa pista onde o carro faz 80.
FALLBACK_CONTEXT = {"fuel": 20.0, "tyre_wear": 100.0, "grip_index": 0.78}


@dataclass
class ReferenceLine:
    """Trajetoria e pilotagem de referencia, ponto a ponto na grade."""

    lateral: np.ndarray
    speed_kmh: np.ndarray
    brake: np.ndarray
    throttle: np.ndarray
    source: str = "lstm"

    def to_frame(self, track: TrackGeometry) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "s": track.s,
                "lateral": self.lateral,
                "speed_kmh": self.speed_kmh,
                "brake": self.brake,
                "throttle": self.throttle,
            }
        )


def _as_trajectory(values: np.ndarray, track: TrackGeometry, encoding=None) -> np.ndarray:
    """Projeta a saida da rede no espaco de trajetorias suaves.

    A rede prediz `lateral` ponto a ponto e nao tem nocao de que a sequencia
    dela e um caminho que um carro percorre: um erro de 20 cm num ponto e
    irrelevante como numero e enorme como curvatura. Medido: a linha crua
    simulava em 98,0 s, mais lenta que dirigir pelo meio da pista (92,9 s);
    projetada no espaco de splines do otimizador, a **mesma** linha simula em
    90,3 s. O que estava ruim era o ruido, nao a forma.

    A projecao e a mesma que o algoritmo evolutivo usa, e nao um filtro
    qualquer, por dois motivos: e um ajuste global (um passa-baixa local a 40 m
    so chegava a 94,5 s), e deixa a referencia expressa exatamente no conjunto
    de trajetorias que a busca consegue produzir.
    """
    from ..optimization.representation import build_encoding

    projection = encoding or build_encoding(track)
    return projection.decode(projection.encode(np.asarray(values, dtype=float)))


def neutral_context(trained=None, task: TaskSpec = REFERENCE_TASK) -> Dict[str, float]:
    """Contexto no centro da distribuicao com que o modelo foi treinado.

    Sai do `StandardScaler`: a media de cada canal de entrada e, por definicao,
    o ponto em que o modelo esta mais bem calibrado. Consultar a rede ali e
    perguntar "como se dirige nesta pista, nas condicoes usuais"; consultar fora
    da faixa e perguntar sobre um carro que ela nunca viu.
    """
    context = dict(FALLBACK_CONTEXT)
    if trained is None or not getattr(trained, "scaler", None):
        return context
    columns = list(trained.scaler.columns)
    for name in context:
        if name in columns:
            context[name] = float(trained.scaler.mean[columns.index(name)])
    return context


def build_inputs(
    track: TrackGeometry,
    corners: Optional[Sequence[Corner]] = None,
    context: Optional[Dict[str, float]] = None,
    sector_loss: float = 0.0,
    lap_loss: float = 0.0,
    task: TaskSpec = REFERENCE_TASK,
    trained=None,
) -> np.ndarray:
    """(1, grade, n_in) — a pista mais a condicao de desempenho pedida."""
    frame = track_features(track, corners).copy()
    frame["sector_loss_s"] = float(sector_loss)
    frame["lap_loss_s"] = float(lap_loss)
    for name, value in {**neutral_context(trained, task), **(context or {})}.items():
        frame[name] = float(value)

    missing = [column for column in task.inputs if column not in frame.columns]
    if missing:
        raise KeyError(f"faltam atributos para consultar o modelo: {missing}")
    matrix = frame.reindex(columns=list(task.inputs)).to_numpy(dtype=np.float32)
    return np.nan_to_num(matrix, nan=0.0)[None, :, :]


def generate(
    trained,
    track: TrackGeometry,
    corners: Optional[Sequence[Corner]] = None,
    context: Optional[Dict[str, float]] = None,
    sector_loss: float = 0.0,
    lap_loss: float = 0.0,
    task: TaskSpec = REFERENCE_TASK,
    encoding=None,
    warmup: Optional[int] = None,
) -> ReferenceLine:
    """Consulta o gerador no nivel de desempenho pedido.

    `warmup` e quantos pontos da propria volta entram antes e depois da grade
    para a rede chegar aquecida nas duas pontas; o padrao e a janela de treino.
    """
    pad = task.window if warmup is None else int(warmup)
    inputs = build_inputs(track, corners, context, sector_loss, lap_loss, task, trained)
    predicted = drop_warmup(trained.predict(with_warmup(inputs, pad)), pad)[0]
    columns = {name: predicted[:, index] for index, name in enumerate(task.targets)}

    lateral = clip_to_corridor(track, _as_trajectory(columns["lateral"], track, encoding))
    return ReferenceLine(
        lateral=lateral,
        speed_kmh=np.maximum(columns.get("speed_kmh", np.zeros(track.size)), 0.0),
        brake=np.clip(columns.get("brake", np.zeros(track.size)), 0.0, 1.0),
        throttle=np.clip(columns.get("throttle", np.zeros(track.size)), 0.0, 1.0),
    )


def sweep_performance(
    trained,
    track: TrackGeometry,
    corners: Optional[Sequence[Corner]] = None,
    losses: Sequence[float] = (0.0, 0.1, 0.3, 0.6),
    **kwargs,
) -> Dict[float, ReferenceLine]:
    """A referencia em varios niveis de perda.

    Serve de conferencia de que o condicionamento faz alguma coisa: se as linhas
    de perda 0,0 s e 0,6 s saem iguais, o modelo ignorou o atributo e o que ele
    aprendeu foi a media -- exatamente o que o desenho tenta evitar.
    """
    return {
        float(loss): generate(trained, track, corners, sector_loss=loss, lap_loss=loss, **kwargs)
        for loss in losses
    }
