"""A aptidao da busca da L2 (pedido 50; ADR 0031, itens 6 e 7).

O custo e o tempo do medidor escolhido (com o peso do trecho de cada passo,
quando o medidor e o calibrado), mais:

* as penalizacoes de forma e de corredor do pedido 46 (`FitnessEvaluator`, sem a
  rede substituta);
* **as restricoes por trecho** (o raio minimo e a taxa maxima de variacao da
  curvatura, item 4.4) e **a regiao de confianca** (1,0 m da L1, item 6), como
  barreira: 5 s por violacao mais 100 s vezes o excesso.

A classe tem a mesma interface do `FitnessEvaluator`, para rodar no `evolve`.
"""

from __future__ import annotations

from typing import Dict, Optional, Sequence

import numpy as np

from ..track.trajectory import corridor_violation
from . import codificacao_nova as CN
from .fitness import FitnessWeights, ShapeReference, shape_metrics
from .lap_time_model import prepare, solve_speed, step_times

BARREIRA_FIXA_S = 5.0
BARREIRA_POR_EXCESSO_S = 100.0
REGIAO_DE_CONFIANCA_M = 1.0


def penalizacao_da_regiao(laterais: np.ndarray, lateral_l1: np.ndarray, raio_m: float = REGIAO_DE_CONFIANCA_M) -> np.ndarray:
    """Por linha: 0 dentro da regiao; senao 5 s + 100 s por metro alem do limite."""
    excesso = np.max(np.abs(np.atleast_2d(laterais) - np.asarray(lateral_l1, float)[None, :]), axis=1) - raio_m
    return np.where(excesso > 1e-9, BARREIRA_FIXA_S + BARREIRA_POR_EXCESSO_S * excesso, 0.0)


def penalizacao_das_restricoes(excesso: Dict[str, np.ndarray]) -> float:
    """Para uma linha: 5 s por trecho com excesso, mais 100 s vezes a soma dos excessos relativos."""
    total = 0.0
    for nome in ("raio", "taxa"):
        e = np.asarray(excesso[nome], float)
        total += BARREIRA_FIXA_S * float((e > 1e-9).sum()) + BARREIRA_POR_EXCESSO_S * float(e.sum())
    return total


def regiao_nos_genes(codificacao, genes_l1: np.ndarray, raio_m: float = REGIAO_DE_CONFIANCA_M):
    """Item 6: os genes entre os da L1 -1,0 m e +1,0 m (e dentro do corredor)."""
    g = np.asarray(genes_l1, float)
    return codificacao.com_limites(g - raio_m, g + raio_m)


class AptidaoDoProjeto:
    def __init__(self, track, codificacao, envelope, shape: ShapeReference, trechos, limites: Dict[str, np.ndarray],
                 lateral_l1: np.ndarray, pesos_por_passo: Optional[np.ndarray] = None,
                 base_por_passo: Optional[np.ndarray] = None, weights: Optional[FitnessWeights] = None):
        self.track = track
        self.encoding = codificacao
        self.envelope = envelope
        self.shape = shape
        self.trechos = trechos
        self.limites = limites
        self.lateral_l1 = np.asarray(lateral_l1, float)
        self.pesos = None if pesos_por_passo is None else np.asarray(pesos_por_passo, float)
        self.base = None if base_por_passo is None else np.asarray(base_por_passo, float)
        self.weights = weights or FitnessWeights(surrogate_weight=0.0)
        self.evaluations = 0

    def tempo(self, per_step: np.ndarray) -> np.ndarray:
        """O tempo do medidor. Com pesos (o M-cal): T(C0) + soma de beta * (passo - passo do C0)."""
        if self.pesos is None:
            return per_step.sum(axis=1)
        return self.base.sum() + np.sum(self.pesos[None, :] * (per_step - self.base[None, :]), axis=1)

    def evaluate(self, population: np.ndarray) -> Dict[str, np.ndarray]:
        genomes = np.atleast_2d(np.asarray(population, float))
        laterais = self.encoding.decode_many(genomes)
        self.evaluations += genomes.shape[0]
        curvature, lengths = prepare(self.track, laterais)
        speed = solve_speed(curvature, lengths, self.envelope)
        per_step = step_times(speed, lengths)
        fisico = self.tempo(per_step)
        metrics = shape_metrics(self.track, laterais)
        violation = np.array([float(np.mean(corridor_violation(self.track, row))) for row in laterais])
        restricoes = np.array([penalizacao_das_restricoes(CN.excesso_das_restricoes(
            CN.medidas_por_trecho(self.track, row, self.trechos), self.limites)) for row in laterais])
        penalties = {
            "corridor": self.weights.corridor * violation,
            "weaving": self.weights.weaving * np.maximum(metrics["weaving"] - self.shape.weaving, 0.0),
            "curvature_jerk": self.weights.curvature_jerk * np.maximum(metrics["curvature_jerk"] - self.shape.curvature_jerk, 0.0)
            / max(self.shape.curvature_jerk, 1e-9),
            "restricoes": restricoes,
            "regiao": penalizacao_da_regiao(laterais, self.lateral_l1),
        }
        total = np.sum(np.vstack(list(penalties.values())), axis=0)
        return {"cost": fisico + total, "physical_time_s": fisico, "surrogate_time_s": np.full(len(fisico), np.nan),
                "blended_time_s": fisico, "path_length_m": lengths.sum(axis=1), "penalty_total": total,
                **{f"penalty_{k}": v for k, v in penalties.items()}}
