"""O laco evolutivo.

Geracional com elitismo: os melhores passam intactos, o resto e reposto por
filhos de torneio, cruzamento e mutacao. Nada exotico -- o que decide a
qualidade do resultado aqui e a representacao (spline em pontos de controle,
clipada na pista) e a aptidao (fisica medida + rede substituta), nao a variante
do algoritmo genetico.

Duas escolhas com consequencia:

* **elitismo com o melhor sempre preservado.** Sem ele o algoritmo perde o
  melhor individuo para a mutacao e o historico de custo sobe -- o que ja e ruim
  e fica pior de diagnosticar.
* **amplitude de mutacao decrescente.** Comeca em 0,6 m para explorar e cai ate
  0,15 m no fim para refinar. Amplitude fixa alta nunca converge; fixa baixa
  nunca sai da vizinhanca das sementes, que sao as voltas do proprio piloto --
  e o objetivo e justamente sair delas.

Criterios de parada: numero de geracoes, ou estagnacao (nenhuma melhora do
melhor custo acima de um limiar por N geracoes).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import numpy as np

from .fitness import FitnessEvaluator
from .operators import crossover, elitism, mutate, tournament_selection
from .representation import TrajectoryEncoding


@dataclass
class EvolutionConfig:
    generations: int = 120
    population_size: int = 80
    elite: int = 4
    tournament_pressure: int = 3
    crossover_rate: float = 0.9
    mutation_rate: float = 0.3
    mutation_amplitude_m: float = 0.6
    mutation_amplitude_final_m: float = 0.15
    stagnation_patience: int = 25
    stagnation_tolerance_s: float = 1e-3
    seed: int = 20260823

    def to_dict(self) -> Dict[str, object]:
        return {
            "generations": self.generations,
            "population_size": self.population_size,
            "elite": self.elite,
            "tournament_pressure": self.tournament_pressure,
            "crossover_rate": self.crossover_rate,
            "mutation_rate": self.mutation_rate,
            "mutation_amplitude_m": self.mutation_amplitude_m,
            "mutation_amplitude_final_m": self.mutation_amplitude_final_m,
            "stagnation_patience": self.stagnation_patience,
            "stagnation_tolerance_s": self.stagnation_tolerance_s,
            "seed": self.seed,
        }


@dataclass
class EvolutionResult:
    """O melhor individuo e como a busca chegou nele."""

    best_genome: np.ndarray
    best_lateral: np.ndarray
    best_cost: float
    history: List[Dict[str, float]] = field(default_factory=list)
    generations_run: int = 0
    evaluations: int = 0
    stopped_by: str = "geracoes"
    initial_cost: float = float("nan")

    @property
    def improvement(self) -> float:
        return float(self.initial_cost - self.best_cost)


def evolve(
    evaluator: FitnessEvaluator,
    encoding: TrajectoryEncoding,
    population: np.ndarray,
    config: Optional[EvolutionConfig] = None,
    progress: Optional[Callable[[str], None]] = None,
) -> EvolutionResult:
    """Roda o algoritmo evolutivo a partir de uma populacao inicial."""
    settings = config or EvolutionConfig()
    generator = np.random.default_rng(settings.seed)

    current = encoding.clip(np.asarray(population, dtype=float))
    if current.shape[0] != settings.population_size:
        # Repete ou corta para o tamanho pedido, preservando a ordem: as
        # primeiras sementes sao as privilegiadas.
        index = np.arange(settings.population_size) % current.shape[0]
        current = current[index]

    scores = evaluator.evaluate(current)
    cost = scores["cost"]
    best_index = int(np.argmin(cost))
    best_genome, best_cost = current[best_index].copy(), float(cost[best_index])
    initial_cost = best_cost

    history: List[Dict[str, float]] = []
    last_improvement = 0
    stopped_by = "geracoes"

    for generation in range(1, settings.generations + 1):
        fraction = generation / max(settings.generations, 1)
        amplitude = (
            settings.mutation_amplitude_m
            + (settings.mutation_amplitude_final_m - settings.mutation_amplitude_m) * fraction
        )

        elite, elite_cost = elitism(current, cost, settings.elite)
        children_needed = settings.population_size - elite.shape[0]

        parents_a = tournament_selection(
            current, cost, children_needed, generator, settings.tournament_pressure
        )
        parents_b = tournament_selection(
            current, cost, children_needed, generator, settings.tournament_pressure
        )
        children = crossover(parents_a, parents_b, generator, settings.crossover_rate)
        children = mutate(
            children, encoding, generator, settings.mutation_rate, amplitude
        )

        current = np.vstack([elite, encoding.clip(children)])
        scores = evaluator.evaluate(current)
        cost = scores["cost"]

        generation_best = int(np.argmin(cost))
        if cost[generation_best] < best_cost - settings.stagnation_tolerance_s:
            best_cost = float(cost[generation_best])
            best_genome = current[generation_best].copy()
            last_improvement = generation

        history.append(
            {
                "generation": generation,
                "best_cost": float(cost.min()),
                "mean_cost": float(cost.mean()),
                "best_physical_s": float(scores["physical_time_s"][generation_best]),
                "best_penalty_s": float(scores["penalty_total"][generation_best]),
                "diversity_m": float(np.mean(np.std(current, axis=0))),
                "mutation_amplitude_m": float(amplitude),
            }
        )
        if progress and (generation % 10 == 0 or generation == 1):
            entry = history[-1]
            progress(
                f"  geracao {generation:4d}  melhor={entry['best_cost']:.3f}s"
                f"  medio={entry['mean_cost']:.3f}s"
                f"  diversidade={entry['diversity_m']:.2f}m"
            )

        if generation - last_improvement >= settings.stagnation_patience:
            stopped_by = "estagnacao"
            break

    return EvolutionResult(
        best_genome=best_genome,
        best_lateral=encoding.decode(best_genome),
        best_cost=best_cost,
        history=history,
        generations_run=len(history),
        evaluations=evaluator.evaluations,
        stopped_by=stopped_by,
        initial_cost=initial_cost,
    )
