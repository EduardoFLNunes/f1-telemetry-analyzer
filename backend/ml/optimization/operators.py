"""Selecao, cruzamento e mutacao sobre genomas de trajetoria.

Os operadores sao escolhidos pelo que o genoma significa, e nao por serem os
mais citados. O genoma aqui e uma curva amostrada: genes vizinhos descrevem
metros vizinhos de pista e sao fortemente correlacionados. Isso muda o que
funciona.

* **cruzamento por trechos contiguos**, e nao gene a gene. Um cruzamento
  uniforme sorteia cada ponto de controle de um pai diferente e produz uma linha
  que oscila entre as duas -- pior que os dois. Herdar trechos inteiros herda
  *decisoes* (como fazer aquela curva), que e o que se quer recombinar.
* **cruzamento aritmetico** como segunda opcao: a media entre duas trajetorias
  validas e uma trajetoria valida, e ela explora o meio do caminho que nenhum
  corte por trecho alcanca.
* **mutacao correlacionada**: o ruido e suavizado ao longo da pista antes de ser
  somado. Ruido branco em pontos de controle vizinhos e exatamente a oscilacao
  de alta frequencia que o simulador pune -- a mutacao sairia sempre pior, e a
  busca pararia de explorar.
* **torneio** em vez de roleta: os custos aqui sao todos proximos (85 s contra
  86 s), e a roleta sobre valores proximos e quase um sorteio uniforme.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

from .representation import TrajectoryEncoding


def tournament_selection(
    population: np.ndarray,
    cost: np.ndarray,
    count: int,
    generator: np.random.Generator,
    pressure: int = 3,
) -> np.ndarray:
    """Escolhe `count` individuos por torneio de `pressure` participantes."""
    size = population.shape[0]
    contenders = generator.integers(0, size, size=(count, int(pressure)))
    winners = contenders[np.arange(count), np.argmin(cost[contenders], axis=1)]
    return population[winners].copy()


def segment_crossover(
    parents_a: np.ndarray,
    parents_b: np.ndarray,
    generator: np.random.Generator,
    min_segment: int = 3,
) -> np.ndarray:
    """Filho = pai A, com um trecho contiguo de pista vindo do pai B.

    O trecho pode dar a volta pelo fim do genoma, porque a pista e fechada e a
    linha de chegada nao e uma fronteira fisica.
    """
    count, genes = parents_a.shape
    children = parents_a.copy()
    starts = generator.integers(0, genes, size=count)
    lengths = generator.integers(min_segment, max(genes // 2, min_segment + 1), size=count)
    for index in range(count):
        span = (starts[index] + np.arange(lengths[index])) % genes
        children[index, span] = parents_b[index, span]
    return children


def arithmetic_crossover(
    parents_a: np.ndarray, parents_b: np.ndarray, generator: np.random.Generator
) -> np.ndarray:
    """Filho = combinacao convexa dos dois pais, com peso sorteado por individuo."""
    weight = generator.random((parents_a.shape[0], 1))
    return weight * parents_a + (1.0 - weight) * parents_b


def crossover(
    parents_a: np.ndarray,
    parents_b: np.ndarray,
    generator: np.random.Generator,
    rate: float = 0.9,
    segment_share: float = 0.6,
) -> np.ndarray:
    """Aplica um dos dois cruzamentos, ou nenhum."""
    children = parents_a.copy()
    active = generator.random(parents_a.shape[0]) < rate
    if not active.any():
        return children
    by_segment = active & (generator.random(parents_a.shape[0]) < segment_share)
    by_average = active & ~by_segment
    if by_segment.any():
        children[by_segment] = segment_crossover(
            parents_a[by_segment], parents_b[by_segment], generator
        )
    if by_average.any():
        children[by_average] = arithmetic_crossover(
            parents_a[by_average], parents_b[by_average], generator
        )
    return children


def _smooth_circular(values: np.ndarray, width: int) -> np.ndarray:
    """Media movel circular ao longo dos genes."""
    if width <= 1:
        return values
    kernel = np.ones(width) / width
    padded = np.concatenate([values[:, -width:], values, values[:, :width]], axis=1)
    smoothed = np.apply_along_axis(lambda row: np.convolve(row, kernel, mode="same"), 1, padded)
    return smoothed[:, width : width + values.shape[1]]


def mutate(
    population: np.ndarray,
    encoding: TrajectoryEncoding,
    generator: np.random.Generator,
    rate: float = 0.25,
    amplitude_m: float = 0.6,
    correlation_genes: int = 3,
) -> np.ndarray:
    """Perturba o genoma com ruido correlacionado ao longo da pista.

    `rate` e a fracao de individuos que sofre mutacao; `amplitude_m` e o desvio
    do deslocamento em metros. 0,6 m e da ordem de meia largura de carro: grande
    o bastante para mudar uma trajetoria, pequeno o bastante para nao jogar o
    individuo para a grama a cada geracao.
    """
    mutated = population.copy()
    chosen = generator.random(population.shape[0]) < rate
    if not chosen.any():
        return mutated

    noise = generator.normal(0.0, amplitude_m, size=(int(chosen.sum()), encoding.genes))
    noise = _smooth_circular(noise, int(correlation_genes))
    # A suavizacao reduz a variancia; devolve-la mantem a amplitude pedida.
    spread = noise.std(axis=1, keepdims=True)
    noise = noise * (amplitude_m / np.maximum(spread, 1e-9))

    mutated[chosen] += noise
    return encoding.clip(mutated)


def elitism(
    population: np.ndarray, cost: np.ndarray, count: int
) -> Tuple[np.ndarray, np.ndarray]:
    """Os `count` melhores individuos, e seus custos."""
    order = np.argsort(cost)[: max(int(count), 0)]
    return population[order].copy(), cost[order].copy()
