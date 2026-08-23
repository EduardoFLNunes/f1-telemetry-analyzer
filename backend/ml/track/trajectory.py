"""Uma trajetoria e um deslocamento lateral ao longo da pista.

Toda trajetoria neste sistema -- a volta do piloto, a referencia da LSTM, cada
individuo do algoritmo evolutivo -- e o mesmo objeto: um vetor `lateral` com um
valor por ponto da grade da pista. Isso da tres coisas de graca:

* duas trajetorias sao comparaveis ponto a ponto, sem realinhar nada;
* cruzar duas trajetorias e cruzar dois vetores do mesmo tamanho;
* respeitar os limites da pista e um `clip` contra o corredor, e nao uma
  verificacao geometrica a cada avaliacao.

O que este modulo calcula sao as grandezas que dependem da forma da trajetoria e
nao da pilotagem: comprimento, curvatura e o quanto ela sai dos limites.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
from scipy.interpolate import CubicSpline

from .. import config
from .geometry import TrackGeometry, _closed_derivative, _smoothing_window, _unit


def world_path(track: TrackGeometry, lateral: np.ndarray) -> np.ndarray:
    """(N, 2) — a trajetoria no plano world X/Z."""
    lateral = np.asarray(lateral, dtype=float)
    return track.points + track.normal * lateral[:, None]


def lateral_derivative(
    track: TrackGeometry, lateral: np.ndarray, smoothing_m: Optional[float] = None
) -> np.ndarray:
    """dL/ds — o quanto a trajetoria cruza a pista por metro percorrido.

    E a medida direta de "movimento de direcao": uma trajetoria que serpenteia
    tem |dL/ds| alto sem que ninguem precise olhar o volante.
    """
    window = _smoothing_window(smoothing_m or config.CURVATURE_SMOOTHING_M, track.step)
    return _closed_derivative(np.asarray(lateral, dtype=float), track.step, window, order=3)


def step_lengths(track: TrackGeometry, lateral: np.ndarray) -> np.ndarray:
    """Comprimento real percorrido por passo da grade, em metros.

    Vem da forma fechada e nao de diferenca de pontos: com
    `r(s) = c(s) + L(s)·n(s)` e a centerline parametrizada por comprimento de
    arco, `|dr/ds| = sqrt((1 - L·k)^2 + (dL/ds)^2)`. O termo `(1 - L·k)` e o
    que faz a linha por dentro de uma curva ser mais curta que a centerline, e
    a de fora, mais longa.
    """
    lateral = np.asarray(lateral, dtype=float)
    derivative = lateral_derivative(track, lateral)
    scale = np.sqrt((1.0 - lateral * track.curvature) ** 2 + derivative**2)
    return scale * track.step


def path_length(track: TrackGeometry, lateral: np.ndarray) -> float:
    """Comprimento total da trajetoria, em metros."""
    return float(np.sum(step_lengths(track, lateral)))


def curvature(
    track: TrackGeometry, lateral: np.ndarray, smoothing_m: Optional[float] = None
) -> np.ndarray:
    """Curvatura da trajetoria, 1/m, positivo virando para a esquerda.

    Calculada derivando a propria trajetoria no plano, com a mesma janela que
    derivou a centerline. Usar o mesmo metodo nos dois lados e o que permite
    dizer "esta trajetoria e mais fechada que a centerline aqui" e que o numero
    signifique isso, e nao uma diferenca de estimador.
    """
    window = _smoothing_window(smoothing_m or config.CURVATURE_SMOOTHING_M, track.step)
    path = world_path(track, lateral)
    first = _closed_derivative(path, track.step, window, order=3)
    speed = np.linalg.norm(first, axis=1)
    tangent = _unit(first)
    normal = np.column_stack([tangent[:, 1], -tangent[:, 0]])
    second = _closed_derivative(tangent, track.step, window, order=3)
    # `first` nao e unitario quando a trajetoria e mais longa que a centerline,
    # entao a divisao por |dr/ds| converte de "por metro de centerline" para
    # "por metro de trajetoria".
    return np.sum(second * normal, axis=1) / np.maximum(speed, 1e-9)


def corridor_violation(
    track: TrackGeometry,
    lateral: np.ndarray,
    car_half_width: float = config.CAR_HALF_WIDTH_M,
    kerb_allowance: float = config.KERB_ALLOWANCE_M,
) -> np.ndarray:
    """Quantos metros a trajetoria passa dos limites, ponto a ponto (0 se dentro)."""
    low, high = track.corridor(car_half_width, kerb_allowance)
    lateral = np.asarray(lateral, dtype=float)
    return np.maximum(np.maximum(low - lateral, lateral - high), 0.0)


def clip_to_corridor(
    track: TrackGeometry,
    lateral: np.ndarray,
    car_half_width: float = config.CAR_HALF_WIDTH_M,
    kerb_allowance: float = config.KERB_ALLOWANCE_M,
) -> np.ndarray:
    """Traz a trajetoria para dentro da pista.

    E o que garante que todo individuo do algoritmo evolutivo nasce valido: o
    cruzamento de duas trajetorias dentro da pista pode sair fora dela em uma
    curva estreita, e clipar e mais barato -- e mais estavel -- do que descartar
    e sortear de novo.
    """
    low, high = track.corridor(car_half_width, kerb_allowance)
    return np.clip(np.asarray(lateral, dtype=float), low, high)


def resample_control_points(
    track: TrackGeometry, control_s: np.ndarray, control_lateral: np.ndarray
) -> np.ndarray:
    """Interpola pontos de controle esparsos para a grade inteira.

    O algoritmo evolutivo trabalha com poucas dezenas de pontos de controle e
    nao com os 2167 pontos da grade: um genoma de 2167 numeros muta em ruido de
    alta frequencia, que e justamente a trajetoria fisicamente impossivel.

    Spline cubica periodica, e nao interpolacao linear: entre dois pontos de
    controle a reta tem segunda derivada zero e, no ponto de controle, infinita.
    Como a curvatura da trajetoria e essa segunda derivada, uma trajetoria
    linear por partes tem um pico de curvatura em cada gene -- o carro simulado
    frearia em cada um deles.
    """
    control_s = np.mod(np.asarray(control_s, dtype=float), track.length)
    control_lateral = np.asarray(control_lateral, dtype=float)
    order = np.argsort(control_s)
    control_s, control_lateral = control_s[order], control_lateral[order]

    extended_s = np.concatenate([control_s, [control_s[0] + track.length]])
    extended_l = np.concatenate([control_lateral, control_lateral[:1]])
    spline = CubicSpline(extended_s, extended_l, bc_type="periodic")

    start = float(control_s[0])
    return spline(start + np.mod(track.s - start, track.length))
