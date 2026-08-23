"""Corte da pista em microsetores.

60 microsetores de ~72 m, o mesmo corte que
`core.assisted_analysis.reference_model` usa. Manter o numero identico nao e
detalhe: e o que permite pegar um resultado deste sistema e sobrepor ao painel
de analise assistida que o app ja mostra, sem traduzir indice de setor.

O corte e por distancia e nao por tempo. Um corte temporal poe mais fronteiras
onde o carro anda devagar, o que e exatamente onde as voltas mais diferem entre
si -- e ai a comparacao entre duas voltas passa a depender de qual delas foi
usada para definir os limites.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np

from .. import config
from .geometry import TrackGeometry


@dataclass(frozen=True)
class Microsectors:
    """Fronteiras dos microsetores e a que microsetor cada ponto da grade pertence."""

    count: int
    edges_s: np.ndarray       # (count + 1,) fronteiras em metros, de 0 a length
    index: np.ndarray         # (grid,) microsetor de cada ponto da grade
    track_length: float

    @property
    def lengths(self) -> np.ndarray:
        return np.diff(self.edges_s)

    def of(self, s_values) -> np.ndarray:
        """Microsetor de distancias arbitrarias."""
        wrapped = np.mod(np.asarray(s_values, dtype=float), self.track_length)
        return np.clip(
            np.searchsorted(self.edges_s, wrapped, side="right") - 1, 0, self.count - 1
        )

    def label(self, index: int) -> str:
        return f"MS{int(index) + 1:02d} ({self.edges_s[index]:.0f}-{self.edges_s[index + 1]:.0f} m)"

    def aggregate(self, values, how: str = "mean") -> np.ndarray:
        """Reduz um vetor da grade para um valor por microsetor."""
        values = np.asarray(values, dtype=float)
        out = np.full(self.count, np.nan)
        for sector in range(self.count):
            selected = values[self.index == sector]
            selected = selected[np.isfinite(selected)]
            if selected.size == 0:
                continue
            if how == "mean":
                out[sector] = selected.mean()
            elif how == "min":
                out[sector] = selected.min()
            elif how == "max":
                out[sector] = selected.max()
            elif how == "sum":
                out[sector] = selected.sum()
            else:
                raise ValueError(f"reducao desconhecida: {how}")
        return out


def build_microsectors(
    track: TrackGeometry, count: int = config.MICROSECTORS
) -> Microsectors:
    edges = np.linspace(0.0, track.length, int(count) + 1)
    index = np.clip(np.searchsorted(edges, track.s, side="right") - 1, 0, int(count) - 1)
    return Microsectors(
        count=int(count), edges_s=edges, index=index, track_length=track.length
    )


def split_times(
    elapsed: np.ndarray,
    sectors: Microsectors,
    track: TrackGeometry,
    total: Optional[float] = None,
) -> np.ndarray:
    """Tempo gasto em cada microsetor, em segundos.

    O tempo acumulado ja esta reamostrado na grade e zerado na origem dela,
    entao o tempo do microsetor e a diferenca entre o tempo na fronteira de
    saida e na de entrada -- e as fronteiras caem exatamente em pontos da grade
    porque a grade e uniforme.

    `total` e o tempo da volta inteira. A ultima fronteira e a linha de chegada,
    que fica alem do ultimo ponto da grade (a grade termina em `length - passo`);
    sem o total, a interpolacao repete o tempo do ultimo ponto e o microsetor
    final sai curto pelo passo que fecha o laco.
    """
    elapsed = np.asarray(elapsed, dtype=float)
    boundaries = np.interp(sectors.edges_s, track.s, elapsed, left=elapsed[0], right=elapsed[-1])
    boundaries[-1] = float(total) if total else float(np.nanmax(elapsed))
    return np.diff(boundaries)


def theoretical_best(splits: Sequence[np.ndarray]) -> np.ndarray:
    """O melhor tempo ja feito em cada microsetor, entre varias voltas.

    A soma disto e a volta ideal do piloto: mais rapida que a melhor volta dele
    e nunca dirigida de ponta a ponta. Essa diferenca e a resposta honesta a
    "quanto tem sobrando".
    """
    stacked = np.vstack([np.asarray(split, dtype=float) for split in splits])
    with np.errstate(invalid="ignore"):
        return np.nanmin(stacked, axis=0)
