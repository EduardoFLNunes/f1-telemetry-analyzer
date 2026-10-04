"""Quais voltas viram referencia do coach (ADR 0016) e quais medem a oscilacao do piloto.

* `volta_ia`: voltas limpas com origem `ia`, de sessoes gravadas a partir de
  2026-10-04 (o gravador novo, com o comportamento atual da IA), no mesmo
  `carModel`. A IA de agosto fazia diferente no microsetor 41 e freava 6 a 8 m
  longe em duas zonas (pedido 13): volta da IA antiga nao serve.
* `minha_melhor` e a oscilacao (o limiar de fala): voltas limpas `humano` com
  equipamento `atual` (ADR 0015), no mesmo carro.

Volta limpa: valida, unica, relogio conferido e sem `relogio_suspeito`
(`origin.driver_mask`), e sem passagem pelo box (`ai_detector.pit_lap`).
"""

from __future__ import annotations

from typing import Dict, Iterable, Optional

import pandas as pd

from .origin import AI, CURRENT_EQUIPMENT, HUMAN, driver_mask

AI_SINCE = "2026-10-04"


def clean_laps(inventory: pd.DataFrame, pit_laps: Iterable[str] = ()) -> pd.DataFrame:
    pits = set(pit_laps)
    ok = inventory["valid"].astype(bool) & driver_mask(inventory, origins=None, equipment=None)
    return inventory[ok & ~inventory["lap_id"].isin(pits)]


def _with_car(laps: pd.DataFrame, cars: Dict[str, Optional[str]], car: Optional[str]) -> pd.DataFrame:
    if car is None:
        return laps
    return laps[laps["session_id"].map(lambda sid: cars.get(sid)) == car]


def driver_laps(inventory: pd.DataFrame, pit_laps: Iterable[str] = (), *,
                cars: Optional[Dict[str, Optional[str]]] = None, car: Optional[str] = None) -> pd.DataFrame:
    """Voltas do piloto de hoje: `humano`, equipamento `atual`, limpas, no carro dado."""
    laps = clean_laps(inventory, pit_laps)
    laps = laps[(laps["origem"] == HUMAN) & (laps["equipamento"] == CURRENT_EQUIPMENT)]
    return _with_car(laps, cars or {}, car)


def ai_laps(inventory: pd.DataFrame, pit_laps: Iterable[str] = (), *,
            cars: Optional[Dict[str, Optional[str]]] = None, car: Optional[str] = None,
            since: str = AI_SINCE) -> pd.DataFrame:
    """Voltas da IA de sessoes novas: origem `ia`, a partir de `since`, limpas, no carro dado."""
    laps = clean_laps(inventory, pit_laps)
    laps = laps[(laps["origem"] == AI) & (laps["session_id"].str[:10] >= since)]
    return _with_car(laps, cars or {}, car)


def most_common_car(laps: pd.DataFrame, cars: Dict[str, Optional[str]]) -> Optional[str]:
    """O carro das voltas dadas (o mais frequente), ou None se nenhuma sessao o registrou."""
    values = laps["session_id"].map(lambda sid: cars.get(sid)).dropna()
    return values.value_counts().idxmax() if not values.empty else None
