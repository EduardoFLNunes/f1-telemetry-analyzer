"""Divisao entre treino, validacao e teste.

A divisao e **por sessao**, e nao por ponto nem por volta solta. Duas razoes,
nesta ordem:

* pontos da mesma volta sao quase identicos entre si -- 2167 pontos por volta,
  um a cada 2 m. Sortear pontos poe o mesmo metro de pista dos dois lados da
  divisao e o modelo passa no teste por ter decorado;
* voltas da mesma sessao compartilham setup, desgaste de pneu, carga de
  combustivel e temperatura de pista. Uma volta de treino e uma de teste da
  mesma sessao ainda vazam desempenho, so que de um jeito mais dificil de ver.

A distribuicao e guloso-balanceada e nao aleatoria pura: com 11 sessoes, das
quais uma tem 53 voltas e cinco tem menos de 5, um sorteio uniforme manda
metade do dataset para o teste com facilidade.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from .. import config


@dataclass
class DataSplit:
    """Quais voltas ficam em cada parte."""

    train: List[str] = field(default_factory=list)
    validation: List[str] = field(default_factory=list)
    test: List[str] = field(default_factory=list)
    sessions: Dict[str, str] = field(default_factory=dict)   # sessao -> parte

    def part_of(self, lap_id: str) -> Optional[str]:
        for name in ("train", "validation", "test"):
            if lap_id in getattr(self, name):
                return name
        return None

    def to_dict(self) -> Dict[str, object]:
        return {
            "train": list(self.train),
            "validation": list(self.validation),
            "test": list(self.test),
            "sessions": dict(self.sessions),
        }

    def summary(self) -> Dict[str, int]:
        return {
            "train": len(self.train),
            "validation": len(self.validation),
            "test": len(self.test),
        }


def split_by_session(
    laps: pd.DataFrame,
    validation_fraction: float = config.VALIDATION_FRACTION,
    test_fraction: float = config.TEST_FRACTION,
    seed: int = config.SPLIT_SEED,
) -> DataSplit:
    """Distribui sessoes inteiras entre as tres partes.

    Sessoes vao para a parte que estiver mais atras da sua cota, da maior para a
    menor. Sessoes grandes primeiro porque sao elas que definem o desbalanco --
    encaixar as pequenas depois so ajusta.
    """
    if laps.empty:
        return DataSplit()

    counts = laps.groupby("session_id").size().sort_values(ascending=False)
    total = int(counts.sum())
    targets = {
        "train": total * (1.0 - validation_fraction - test_fraction),
        "validation": total * validation_fraction,
        "test": total * test_fraction,
    }
    assigned = {"train": 0, "validation": 0, "test": 0}
    membership: Dict[str, str] = {}

    generator = np.random.default_rng(seed)
    order = list(counts.items())
    # Desempate estavel entre sessoes do mesmo tamanho.
    generator.shuffle(order)
    order.sort(key=lambda item: -item[1])

    for session_id, size in order:
        deficit = {
            name: (targets[name] - assigned[name]) / max(targets[name], 1e-9)
            for name in targets
        }
        # A parte mais desabastecida leva; o treino desempata por ser a maior
        # cota e a que mais sofre com sessao faltando.
        part = max(deficit, key=lambda name: (deficit[name], name == "train"))
        membership[str(session_id)] = part
        assigned[part] += int(size)

    split = DataSplit(sessions=membership)
    for _, row in laps.iterrows():
        part = membership.get(str(row["session_id"]), "train")
        getattr(split, part).append(str(row["lap_id"]))
    return split


def describe(split: DataSplit, laps: pd.DataFrame) -> pd.DataFrame:
    """Tabela do que caiu em cada parte, para conferir antes de treinar."""
    rows = []
    for name in ("train", "validation", "test"):
        lap_ids = getattr(split, name)
        selected = laps[laps["lap_id"].isin(lap_ids)]
        if selected.empty:
            rows.append({"parte": name, "voltas": 0, "sessoes": 0})
            continue
        times = selected["lap_time_s"].to_numpy(dtype=float)
        rows.append(
            {
                "parte": name,
                "voltas": int(len(selected)),
                "sessoes": int(selected["session_id"].nunique()),
                "melhor_s": float(times.min()),
                "mediana_s": float(np.median(times)),
                "pior_s": float(times.max()),
            }
        )
    return pd.DataFrame(rows)
