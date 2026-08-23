"""Janelas sequenciais para a LSTM.

Duas tarefas, e a diferenca entre elas e o desenho central do sistema.

**Gerador (`REFERENCE_TASK`)** — entra o que a pista e mais o nivel de
desempenho; sai o que o piloto faz. A pilotagem *nao* entra na entrada: se
entrasse, prever velocidade a partir de velocidade e copiar, e o modelo
aprenderia a identidade em vez de aprender pilotagem. E o condicionamento por
desempenho que impede o resto -- sem ele, o unico jeito de a rede acertar todas
as voltas de uma vez e responder a media delas, que e exatamente o que nao se
quer. Com ele, pede-se a rede a pilotagem correspondente a perda zero.

**Substituto (`SURROGATE_TASK`)** — entra a forma da trajetoria; sai o tempo. A
velocidade tambem nao entra, e por outra razao: tempo e distancia dividida por
velocidade, entao um modelo que recebe velocidade nao aprende nada sobre
tracado. Recebendo so a forma da linha, ele aprende quanto tempo *este piloto
neste carro* faz por aqui passando por ali -- que e o termo com que o algoritmo
evolutivo corrige a fisica.

As janelas dao a volta na pista. A grade e circular, entao a janela que comeca
100 m antes da linha de chegada termina 100 m depois dela, e o trecho mais
importante da volta -- saida da ultima curva e entrada da primeira -- deixa de
ser um pedaco que nenhuma janela cobre inteiro.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from ..features.engineering import PERFORMANCE_FEATURES, TRACK_FEATURES

# Forma da trajetoria: o que descreve por onde a linha passa, sem dizer a que
# velocidade.
SHAPE_FEATURES = (
    "lateral",
    "lateral_rate",
    "path_curvature",
    "distance_to_left_edge",
    "distance_to_right_edge",
)

# Contexto da volta que explica diferenca de desempenho sem ser pilotagem.
CONTEXT_FEATURES = ("fuel", "tyre_wear", "grip_index")


@dataclass(frozen=True)
class TaskSpec:
    """O que entra, o que sai, e em que tamanho de janela."""

    name: str
    inputs: Tuple[str, ...]
    targets: Tuple[str, ...]
    window: int = 128
    stride: int = 16

    @property
    def window_meters(self) -> float:
        return self.window * 2.0


REFERENCE_TASK = TaskSpec(
    name="reference",
    inputs=TRACK_FEATURES + PERFORMANCE_FEATURES + CONTEXT_FEATURES,
    targets=("lateral", "speed_kmh", "brake", "throttle"),
)

SURROGATE_TASK = TaskSpec(
    name="surrogate",
    inputs=TRACK_FEATURES + SHAPE_FEATURES + CONTEXT_FEATURES,
    targets=("step_time_s",),
)


@dataclass
class SequenceSet:
    """Janelas prontas para o modelo, com de onde cada uma veio."""

    inputs: np.ndarray            # (n, window, n_in)
    targets: np.ndarray           # (n, window, n_out)
    lap_ids: np.ndarray           # (n,)
    start_index: np.ndarray       # (n,) ponto da grade onde a janela comeca
    input_columns: Tuple[str, ...]
    target_columns: Tuple[str, ...]

    def __len__(self) -> int:
        return int(self.inputs.shape[0])

    def describe(self) -> Dict[str, object]:
        return {
            "windows": len(self),
            "window_length": int(self.inputs.shape[1]),
            "inputs": list(self.input_columns),
            "targets": list(self.target_columns),
            "laps": int(np.unique(self.lap_ids).size),
        }


def step_time(frame: pd.DataFrame) -> np.ndarray:
    """Tempo gasto em cada passo da grade, em segundos.

    Diferenca do tempo acumulado, com o ultimo passo fechando na linha. Um passo
    nao positivo aparece onde a volta tem buraco de amostragem e a interpolacao
    achatou o tempo; ele vira NaN em vez de zero, porque zero segundo por 2 m e
    velocidade infinita e o modelo aprenderia isso.
    """
    elapsed = frame["elapsed_s"].to_numpy(dtype=float)
    delta = np.diff(elapsed)
    total = (
        float(frame["lap_time_s"].iloc[0])
        if "lap_time_s" in frame.columns
        else float(np.nanmax(elapsed))
    )
    delta = np.concatenate([delta, [max(total - elapsed[-1], float(np.nanmedian(delta)))]])
    return np.where(delta > 1e-4, delta, np.nan)


def _circular_windows(size: int, window: int, stride: int) -> np.ndarray:
    """(n, window) com os indices de cada janela, dando a volta na pista."""
    starts = np.arange(0, size, stride)
    offsets = np.arange(window)
    return (starts[:, None] + offsets[None, :]) % size


def build_sequences(
    frames: Dict[str, pd.DataFrame],
    task: TaskSpec,
    lap_ids: Optional[Sequence[str]] = None,
) -> SequenceSet:
    """Transforma tabelas de atributos em janelas."""
    wanted = [lap for lap in (lap_ids or frames.keys()) if lap in frames]
    if not wanted:
        raise ValueError("nenhuma volta para gerar sequencias")

    inputs: List[np.ndarray] = []
    targets: List[np.ndarray] = []
    origins: List[np.ndarray] = []
    starts: List[np.ndarray] = []

    for lap_id in wanted:
        frame = frames[lap_id].copy()
        if "step_time_s" in task.targets and "step_time_s" not in frame.columns:
            frame["step_time_s"] = step_time(frame)

        missing = [c for c in task.inputs + task.targets if c not in frame.columns]
        if missing:
            raise KeyError(f"volta {lap_id} nao tem as colunas {missing}")

        source = np.nan_to_num(
            frame.reindex(columns=list(task.inputs)).to_numpy(dtype=np.float32),
            nan=0.0, posinf=0.0, neginf=0.0,
        )
        target = frame.reindex(columns=list(task.targets)).to_numpy(dtype=np.float32)

        index = _circular_windows(len(frame), task.window, task.stride)
        window_targets = target[index]
        # Uma janela com alvo ausente nao ensina nada e polui a perda.
        usable = np.isfinite(window_targets).all(axis=(1, 2))
        if not usable.any():
            continue

        inputs.append(source[index][usable])
        targets.append(window_targets[usable])
        origins.append(np.full(int(usable.sum()), lap_id, dtype=object))
        starts.append(index[usable, 0])

    if not inputs:
        raise ValueError("nenhuma janela utilizavel")

    return SequenceSet(
        inputs=np.concatenate(inputs, axis=0),
        targets=np.concatenate(targets, axis=0),
        lap_ids=np.concatenate(origins, axis=0),
        start_index=np.concatenate(starts, axis=0),
        input_columns=task.inputs,
        target_columns=task.targets,
    )


def with_warmup(inputs: np.ndarray, pad: int) -> np.ndarray:
    """(n, N, d) -> (n, N + 2*pad, d), costurando a volta nela mesma.

    A rede comeca cada sequencia com estado oculto zerado, e leva algumas
    dezenas de passos para que ele signifique alguma coisa. Numa janela de
    treino isso e irrelevante -- as janelas se sobrepoem e todo ponto e visto
    tambem no meio de alguma. Na inferencia sobre a volta inteira, nao: os
    primeiros metros depois da linha de chegada sao vistos uma vez so, e com a
    rede ainda fria.

    Medido na linha de referencia: 10 m de erro lateral em s < 200 m e 4 m no
    fim da volta, contra menos de 3 m no resto da pista. Sao as duas pontas da
    sequencia, e a rede e bidirecional, entao as duas sofrem.

    A pista e fechada, entao o aquecimento e de graca: antes do inicio vem o
    fim da propria volta, e depois do fim vem o inicio. O trecho acrescentado e
    descartado com `drop_warmup`.
    """
    if pad <= 0:
        return inputs
    return np.concatenate([inputs[:, -pad:], inputs, inputs[:, :pad]], axis=1)


def drop_warmup(outputs: np.ndarray, pad: int) -> np.ndarray:
    """Descarta o aquecimento das duas pontas."""
    return outputs if pad <= 0 else outputs[:, pad:-pad]


def full_lap_sequence(frame: pd.DataFrame, task: TaskSpec) -> np.ndarray:
    """(1, grid, n_in) — a volta inteira como uma sequencia so.

    Usado na inferencia: a rede treinada em janelas de 128 passos roda sobre os
    2167 pontos de uma vez, o que da uma referencia continua em vez de 136
    pedacos costurados.
    """
    source = frame.reindex(columns=list(task.inputs)).to_numpy(dtype=np.float32)
    return np.nan_to_num(source, nan=0.0, posinf=0.0, neginf=0.0)[None, :, :]
