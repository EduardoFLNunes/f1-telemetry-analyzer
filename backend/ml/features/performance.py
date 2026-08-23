"""Desempenho por microsetor: quem foi rapido, onde, e quanto sobrou.

Esta e a etapa de "identificacao das melhores referencias". Ela responde tres
perguntas que o resto do sistema consome:

* qual e o melhor tempo ja feito em cada microsetor (o alvo *alcancado*, e nao
  um alvo teorico tirado de formula);
* quanto cada volta perdeu para esse alvo em cada microsetor (o sinal de
  condicionamento que impede a LSTM de aprender a media);
* quanto a volta ideal -- a soma dos melhores microsetores -- e mais rapida que
  a melhor volta inteira (a resposta honesta a "quanto tem sobrando").

A referencia sai **so das voltas de treino**. Construida sobre o dataset inteiro,
ela carregaria para dentro do atributo de condicionamento o desempenho das
voltas de teste, e a avaliacao passaria a medir memoria em vez de generalizacao.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from ..data.lap_store import StoredLaps
from ..track.geometry import TrackGeometry
from ..track.microsectors import Microsectors, split_times


@dataclass
class DriverReference:
    """O que o piloto ja provou ser capaz de fazer em cada trecho."""

    sector_count: int
    best_splits: np.ndarray            # (setores,) melhor tempo por microsetor
    median_splits: np.ndarray
    best_lap_per_sector: List[str]     # de que volta veio cada melhor tempo
    best_lap_id: str
    best_lap_time: float
    theoretical_best_time: float
    lap_count: int

    @property
    def available_gain(self) -> float:
        """Quanto a volta ideal e mais rapida que a melhor volta real."""
        return float(self.best_lap_time - self.theoretical_best_time)

    def to_dict(self) -> Dict[str, object]:
        return {
            "sector_count": self.sector_count,
            "best_splits": self.best_splits.tolist(),
            "median_splits": self.median_splits.tolist(),
            "best_lap_per_sector": list(self.best_lap_per_sector),
            "best_lap_id": self.best_lap_id,
            "best_lap_time": self.best_lap_time,
            "theoretical_best_time": self.theoretical_best_time,
            "available_gain": self.available_gain,
            "lap_count": self.lap_count,
        }


def lap_split_matrix(
    store: StoredLaps,
    track: TrackGeometry,
    sectors: Microsectors,
    lap_ids: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    """(voltas x microsetores) com o tempo de cada volta em cada trecho."""
    wanted = list(lap_ids) if lap_ids is not None else store.lap_ids
    elapsed = store.frame.pivot(index="lap_id", columns="grid_index", values="elapsed_s")
    elapsed = elapsed.loc[[lap for lap in wanted if lap in elapsed.index]]
    totals = store.laps.set_index("lap_id")["lap_time_s"]

    rows = {
        lap_id: split_times(
            values.to_numpy(dtype=float), sectors, track, total=float(totals.get(lap_id, np.nan))
        )
        for lap_id, values in elapsed.iterrows()
    }
    return pd.DataFrame.from_dict(rows, orient="index", columns=range(sectors.count))


def build_reference(
    store: StoredLaps,
    track: TrackGeometry,
    sectors: Microsectors,
    lap_ids: Optional[Sequence[str]] = None,
) -> DriverReference:
    """Monta a referencia do piloto a partir das voltas indicadas."""
    splits = lap_split_matrix(store, track, sectors, lap_ids)
    if splits.empty:
        raise ValueError("nenhuma volta para construir a referencia")

    values = splits.to_numpy(dtype=float)
    # Um microsetor com tempo nao positivo e artefato de reamostragem numa volta
    # com buraco, e nao um recorde.
    values = np.where(values > 1e-3, values, np.nan)

    best_index = np.nanargmin(values, axis=0)
    best_splits = np.nanmin(values, axis=0)
    median_splits = np.nanmedian(values, axis=0)

    lap_times = store.laps.set_index("lap_id")["lap_time_s"]
    considered = lap_times.loc[[lap for lap in splits.index if lap in lap_times.index]]
    best_lap_id = str(considered.idxmin())

    return DriverReference(
        sector_count=sectors.count,
        best_splits=best_splits,
        median_splits=median_splits,
        best_lap_per_sector=[str(splits.index[i]) for i in best_index],
        best_lap_id=best_lap_id,
        best_lap_time=float(considered.min()),
        theoretical_best_time=float(np.nansum(best_splits)),
        lap_count=int(len(splits)),
    )


def sector_losses(splits: pd.DataFrame, reference: DriverReference) -> pd.DataFrame:
    """Quanto cada volta perdeu para a referencia, por microsetor."""
    return splits.subtract(pd.Series(reference.best_splits, index=splits.columns), axis=1)


def describe_reference(reference: DriverReference, sectors: Microsectors) -> pd.DataFrame:
    """Tabela por microsetor: melhor, mediana, e de que volta veio o melhor."""
    return pd.DataFrame(
        {
            "microsetor": [sectors.label(i) for i in range(reference.sector_count)],
            "melhor_s": np.round(reference.best_splits, 3),
            "mediana_s": np.round(reference.median_splits, 3),
            "sobra_s": np.round(reference.median_splits - reference.best_splits, 3),
            "volta": reference.best_lap_per_sector,
        }
    )
