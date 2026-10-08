"""Traçado de referência único da F1 na época 2023–25 (pedido 24; ADR 0019).

A posição pública do FastF1 se comporta como um traçado de referência por
época, e não como a linha de cada carro (pedido 23). A F1 entra no Modelo 1
como uma trajetória só: a mediana, ponto a ponto da grade de 2.167 pontos,
das voltas secas aceitas das sessões de 2023 a 2025.

* **Seleção:** voltas escolhidas e aceitas pelo critério do pedido 23, de 2023,
  2024 e 2025. 2019, 2021 e 2022 são outras épocas; a volta de chuva nunca entra.
* **Coerência da época, fixada antes de rodar:** uma sessão só entra se a
  mediana dela fica perto da referência das outras sessões da época
  (`|sessão - referência sem ela|`: mediana <= 0,10 m e p90 <= 0,30 m). Cada
  sessão é medida contra todas as outras candidatas, numa passada só.
* **Referência:** a mediana por ponto das voltas das sessões coerentes, cada
  volta pesando igual.

Ela não representa a linha de um piloto nem uma faixa de variação. Só a posição
da F1 entra (ADR 0018).
"""

from __future__ import annotations

import re
from typing import Dict, List, Sequence

import numpy as np

ERA_YEARS = (2023, 2024, 2025)
# Coerência da época, fixada antes de rodar (pedido 24, Parte C, item 2).
MAX_SESSION_MEDIAN_M = 0.10
MAX_SESSION_P90_M = 0.30


def session_key(record: Dict[str, object]) -> str:
    return f"{int(record['ano'])} {record['sessao']}"


def era_laps(records: Sequence[Dict[str, object]], years: Sequence[int] = ERA_YEARS) -> List[Dict[str, object]]:
    """As voltas do manifesto do pedido 23 que podem entrar na referência.

    Entram só as voltas escolhidas e aceitas pelo critério por volta, dos anos
    da época. Fica fora a volta registrada à parte (a de chuva), mesmo que o
    alinhamento dela tenha passado no critério.
    """
    out = []
    for record in records:
        if int(record["ano"]) not in tuple(int(y) for y in years):
            continue
        if record.get("a_parte"):
            continue
        if record.get("etapa") != "escolhida":
            continue
        if not (record.get("criterio") or {}).get("aceita"):
            continue
        out.append(record)
    return out


def reference_line(laterals: np.ndarray) -> np.ndarray:
    """Mediana por ponto da grade, cada volta pesando igual. `laterals`: (voltas, grade)."""
    return np.median(np.atleast_2d(np.asarray(laterals, dtype=float)), axis=0)


def coherence_verdict(median_m: float, p90_m: float) -> Dict[str, object]:
    """A sessão entra só se as duas condições valem; as bordas passam."""
    median_ok = float(median_m) <= MAX_SESSION_MEDIAN_M
    p90_ok = float(p90_m) <= MAX_SESSION_P90_M
    return {
        "mediana_m": float(median_m),
        "p90_m": float(p90_m),
        "mediana_ok": bool(median_ok),
        "p90_ok": bool(p90_ok),
        "entra": bool(median_ok and p90_ok),
    }


def coherence(laterals: np.ndarray, sessions: Sequence[str]) -> Dict[str, Dict[str, object]]:
    """Por sessão: |mediana da sessão - referência das outras sessões|, resumido sobre os pontos da grade.

    A referência sem a sessão é a mediana por ponto das voltas de todas as
    outras sessões candidatas. Uma sessão sozinha na época não tem com quem ser
    comparada e fica fora.
    """
    laterals = np.atleast_2d(np.asarray(laterals, dtype=float))
    labels = np.asarray(list(sessions))
    out: Dict[str, Dict[str, object]] = {}
    for key in dict.fromkeys(sessions):
        own = labels == key
        if own.all():
            out[key] = {"voltas": int(own.sum()), "entra": False, "motivo": "nenhuma outra sessao na epoca"}
            continue
        difference = np.abs(reference_line(laterals[own]) - reference_line(laterals[~own]))
        out[key] = {
            "voltas": int(own.sum()),
            "voltas_das_outras": int((~own).sum()),
            "max_m": float(difference.max()),
            **coherence_verdict(float(np.median(difference)), float(np.percentile(difference, 90))),
        }
    return out


def session_amplitude(laterals: np.ndarray, sessions: Sequence[str]) -> np.ndarray:
    """Por ponto da grade, max - min entre as medianas das sessões."""
    laterals = np.atleast_2d(np.asarray(laterals, dtype=float))
    labels = np.asarray(list(sessions))
    medians = np.vstack([reference_line(laterals[labels == key]) for key in dict.fromkeys(sessions)])
    return medians.max(axis=0) - medians.min(axis=0)


def unreliable_flags(labels: Sequence[str], count: int) -> np.ndarray:
    """Marca por microssetor a partir dos rótulos `MSnn (...)` do pedido 23."""
    flags = np.zeros(int(count), dtype=bool)
    for label in labels:
        match = re.match(r"MS(\d+)", str(label))
        if not match:
            raise ValueError(f"rotulo de microssetor inesperado: {label!r}")
        flags[int(match.group(1)) - 1] = True
    return flags
