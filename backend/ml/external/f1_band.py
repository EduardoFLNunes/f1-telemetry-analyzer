"""Faixa de linhas reais da F1 na grade da pista (pedido 23; ADR 0018).

Cada volta seca escolhida em `f1_dry_laps` passa pelo mesmo alinhamento do
pedido 22 (`f1_line.align`: Procrustes e ICP contra a linha central, escala
unica livre, espelho permitido), vai para a grade de 2 m e e julgada por um
criterio fixado antes de rodar. Com as voltas aceitas:

* **incerteza do alinhamento**, por duas variantes que nunca escolhem volta:
  V1 com a escala presa no decimetro nominal; V2 com uma transformacao so por
  sessao;
* **faixa**: por ponto da grade, mediana, p10 e p90 do lateral (cada volta
  pesa igual), e por microsetor a mediana desses valores;
* **comparacao descritiva**: quanto de cada microsetor de uma linha cai dentro
  de [p10, p90].

A faixa mostra onde carros reais passam. Ela nao e alvo do Modelo 1: e outro
carro, em outra velocidade (ADR 0018).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import numpy as np

from ..track.geometry import TrackGeometry
from ..track.microsectors import Microsectors
from . import f1_line

# Criterio por volta do pedido 23, fixado antes de rodar.
MIN_COVERAGE = 0.99
MAX_GAP_M = 80.0
MAX_OUTSIDE_FRACTION = f1_line.MAX_OUTSIDE_FRACTION   # 10%, o mesmo do pedido 22
MAX_EXCESS_P95_M = f1_line.MAX_EXCESS_P95_M           # 1 m, o mesmo do pedido 22

# Faixa: minimo fixado antes de rodar.
MIN_BAND_LAPS = 20
MIN_BAND_SESSIONS = 3
BAND_PERCENTILES = (10.0, 50.0, 90.0)

# Incerteza: microsetor com p90 de |variante - principal| acima disto e "faixa pouco confiavel".
UNRELIABLE_P90_M = 1.0
# V1: o decimetro nominal do FastF1.
NOMINAL_M_PER_UNIT = 0.1

# Comparacao: o microsetor conta como "dentro" com pelo menos esta fracao dos pontos dentro.
INSIDE_SECTOR_FRACTION = 0.5


# ------------------------------------------------------------- por volta ---

@dataclass(frozen=True)
class LapFit:
    """Uma volta alinhada pelo metodo principal, com os numeros do criterio."""

    similarity: f1_line.Similarity
    fit: Dict[str, object]
    line: f1_line.GridLine
    excess: np.ndarray
    summary: Dict[str, float]
    max_gap_m: float
    verdict: Dict[str, object]


def max_gap_m(line: f1_line.GridLine, track_length: float) -> float:
    """O maior buraco entre amostras seguidas, em metros de `s`, contando o que fecha a volta."""
    positions = np.maximum.accumulate(line.s_unwrapped)
    steps = np.diff(positions)
    closing = float(positions[0] + track_length - positions[-1])
    return float(max(steps.max() if steps.size else 0.0, closing))


def lap_verdict(coverage: float, gap_m: float, summary: Dict[str, float]) -> Dict[str, object]:
    """Aceita so se as quatro condicoes valem. Nada e ajustado depois de ver o resultado."""
    checks = {
        "cobertura_ok": coverage >= MIN_COVERAGE,
        "buraco_ok": gap_m <= MAX_GAP_M,
        "fracao_ok": summary["fracao_fora"] <= MAX_OUTSIDE_FRACTION,
        "p95_ok": summary["p95_m"] <= MAX_EXCESS_P95_M,
    }
    accepted = all(checks.values())
    return {
        "aceita": bool(accepted),
        "veredito": "aceita" if accepted else "recusada",
        "cobertura": float(coverage),
        "maior_buraco_m": float(gap_m),
        "fracao_fora": float(summary["fracao_fora"]),
        "p95_excesso_m": float(summary["p95_m"]),
        "max_excesso_m": float(summary["max_m"]),
        **{key: bool(value) for key, value in checks.items()},
    }


def fit_lap(track: TrackGeometry, raw: np.ndarray) -> LapFit:
    """O metodo do pedido 22 numa volta: alinhamento, grade, excesso e criterio."""
    similarity, fit = f1_line.align(raw, track)
    line = f1_line.project_to_grid(track, similarity.apply(raw))
    excess = f1_line.excess_on_grid(track, line.grid_lateral)
    summary = f1_line.excess_summary(excess)
    gap = max_gap_m(line, track.length)
    return LapFit(similarity, fit, line, excess, summary, gap, lap_verdict(line.coverage, gap, summary))


def grid_lateral(track: TrackGeometry, raw: np.ndarray, similarity: f1_line.Similarity) -> np.ndarray:
    """Lateral na grade da volta `raw` levada por `similarity`."""
    return f1_line.project_to_grid(track, similarity.apply(raw)).grid_lateral


# ------------------------------------------------------------- incerteza ---

def transform_spread(similarities: Sequence[f1_line.Similarity], centroid: np.ndarray) -> Dict[str, object]:
    """Dispersao das transformacoes por volta de uma sessao.

    A translacao e medida no centroide (`centroid`, no sistema do FastF1): o
    vetor de translacao e a imagem da origem do FastF1, longe da pista, e ali
    qualquer fracao de grau vira metros sem a linha sair do lugar.
    """
    scales = np.array([sim.scale for sim in similarities])
    angles = np.array([sim.rotation_deg for sim in similarities])
    reference = float(np.median(angles))
    angles = (angles - reference + 180.0) % 360.0 - 180.0 + reference
    point = np.asarray(centroid, dtype=float).reshape(1, 2)
    images = np.vstack([sim.apply(point)[0] for sim in similarities])
    centre = np.median(images, axis=0)
    distance = np.linalg.norm(images - centre, axis=1)
    return {
        "voltas": int(len(similarities)),
        "espelhadas": int(sum(sim.mirrored for sim in similarities)),
        "escala_m_por_unidade": {
            "min": float(scales.min()), "mediana": float(np.median(scales)), "max": float(scales.max()),
            "amplitude_relativa": float(scales.max() / scales.min() - 1.0),
        },
        "rotacao_graus": {
            "min": float(angles.min()), "mediana": float(np.median(angles)), "max": float(angles.max()),
            "amplitude": float(angles.max() - angles.min()),
        },
        "centroide_m": {
            "distancia_mediana_a_mediana": float(np.median(distance)),
            "distancia_max_a_mediana": float(distance.max()),
        },
    }


def sector_abs_stats(sectors: Microsectors, differences: np.ndarray) -> Dict[str, np.ndarray]:
    """Mediana e p90 de |diferenca| por microsetor, com todos os pontos de todas as voltas juntos.

    `differences` tem forma (voltas, grade).
    """
    values = np.abs(np.atleast_2d(np.asarray(differences, dtype=float)))
    median = np.empty(sectors.count)
    p90 = np.empty(sectors.count)
    for k in range(sectors.count):
        pooled = values[:, sectors.index == k].ravel()
        median[k] = float(np.median(pooled))
        p90[k] = float(np.percentile(pooled, 90))
    return {"mediana": median, "p90": p90}


# ----------------------------------------------------------------- faixa ---

def band(laterals: np.ndarray) -> Dict[str, np.ndarray]:
    """p10, p50 e p90 do lateral por ponto da grade, cada volta pesando igual. `laterals`: (voltas, grade)."""
    laterals = np.atleast_2d(np.asarray(laterals, dtype=float))
    p10, p50, p90 = np.percentile(laterals, BAND_PERCENTILES, axis=0)
    return {"p10": p10, "p50": p50, "p90": p90, "n": np.full(laterals.shape[1], laterals.shape[0])}


def band_is_formed(laps: int, sessions: int) -> bool:
    return laps >= MIN_BAND_LAPS and sessions >= MIN_BAND_SESSIONS


def sector_median(sectors: Microsectors, values: np.ndarray) -> np.ndarray:
    """Mediana por microsetor de um vetor da grade."""
    values = np.asarray(values, dtype=float)
    return np.array([float(np.median(values[sectors.index == k])) for k in range(sectors.count)])


def session_spread(sectors: Microsectors, laterals: np.ndarray, sessions: Sequence[str]) -> Dict[str, object]:
    """Por microsetor, a amplitude entre as medianas das sessoes.

    A mediana de cada sessao e a mediana ponto a ponto das suas voltas, depois
    reduzida por microsetor pela mediana. A amplitude e max - min entre sessoes.
    """
    laterals = np.atleast_2d(np.asarray(laterals, dtype=float))
    keys = list(dict.fromkeys(sessions))
    labels = np.asarray(list(sessions))
    medians = {key: sector_median(sectors, np.median(laterals[labels == key], axis=0)) for key in keys}
    stacked = np.vstack([medians[key] for key in keys])
    return {
        "sessoes": keys,
        "voltas_por_sessao": {key: int((labels == key).sum()) for key in keys},
        "medianas_por_sessao": medians,
        "amplitude": stacked.max(axis=0) - stacked.min(axis=0),
    }


# ------------------------------------------------------------ comparacao ---

def signed_outside(line: np.ndarray, p10: np.ndarray, p90: np.ndarray) -> np.ndarray:
    """Distancia ate a borda da faixa, por ponto: positiva a esquerda de p90, negativa a direita de p10, 0 dentro."""
    line = np.asarray(line, dtype=float)
    above = np.maximum(line - np.asarray(p90, dtype=float), 0.0)
    below = np.maximum(np.asarray(p10, dtype=float) - line, 0.0)
    return above - below


def compare_to_band(sectors: Microsectors, line: np.ndarray, p10: np.ndarray, p90: np.ndarray,
                    top: int = 5) -> Dict[str, object]:
    """Quanto de cada microsetor de `line` fica dentro de [p10, p90].

    O microsetor conta como "dentro" com pelo menos 50% dos pontos dentro. Os
    "mais fora" sao os de maior distancia mediana ate a borda (positivo: a linha
    passa a esquerda da faixa, ADR 0003).
    """
    outside = signed_outside(line, p10, p90)
    inside = outside == 0.0
    rows: List[Dict[str, object]] = []
    for k in range(sectors.count):
        mask = sectors.index == k
        distance = float(np.median(outside[mask]))
        rows.append({
            "microsetor": k,
            "rotulo": sectors.label(k),
            "inicio_m": float(sectors.edges_s[k]),
            "fim_m": float(sectors.edges_s[k + 1]),
            "fracao_dentro": float(inside[mask].mean()),
            "dentro": bool(inside[mask].mean() >= INSIDE_SECTOR_FRACTION),
            "distancia_mediana_ate_a_borda_m": distance,
            "lado": None if distance == 0.0 else ("esquerda" if distance > 0 else "direita"),
        })
    ranked = sorted(rows, key=lambda row: (-abs(row["distancia_mediana_ate_a_borda_m"]), row["fracao_dentro"]))
    return {
        "microsetores_dentro": int(sum(row["dentro"] for row in rows)),
        "microsetores": int(sectors.count),
        "fracao_de_pontos_dentro": float(inside.mean()),
        "mais_fora": ranked[: int(top)],
        "por_microsetor": rows,
    }


def difference_table(sectors: Microsectors, reference: np.ndarray,
                     laps_lateral: np.ndarray) -> Dict[str, object]:
    """`reference - mediana das voltas`, por microsetor (a tabela "F1 - IA" do pedido 22)."""
    per_sector, median_line = f1_line.sector_median_difference(sectors, reference, laps_lateral)
    return {"por_microsetor": per_sector, "linha_mediana": median_line,
            "resumo": f1_line.difference_summary(per_sector)}


def unreliable_sectors(v1_p90: Optional[np.ndarray], v2_p90: Optional[np.ndarray]) -> List[int]:
    """Microsetores com p90 acima de 1 m em V1 ou em V2."""
    flags = np.zeros(len(v1_p90 if v1_p90 is not None else v2_p90), dtype=bool)
    for values in (v1_p90, v2_p90):
        if values is not None:
            flags |= np.asarray(values, dtype=float) > UNRELIABLE_P90_M
    return [int(k) for k in np.flatnonzero(flags)]
