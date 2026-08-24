"""A busca evoluiu, ou so sorteou muitas vezes?

Um algoritmo evolutivo quase sempre "melhora": a cada geracao ele guarda o
melhor que viu, e o melhor de mais amostras e melhor por construcao. Um
grafico de custo caindo, sozinho, nao distingue evolucao de sorteio com
memoria.

Dois controles, com o mesmo orcamento de avaliacoes que a busca gastou:

* **amostragem uniforme** no corredor da pista -- mede o quanto o espaco e
  dificil, e portanto o quanto vale semear a populacao com voltas reais;
* **perturbacao cega** das mesmas sementes -- mesma mutacao, sem selecao, sem
  cruzamento, sem elitismo dirigido. E este que decide a pergunta, porque parte
  do mesmo lugar e so nao evolui.

Semear com 60 voltas reais ja entrega um bom individuo antes da primeira
geracao; o ganho honesto da busca e o que ela acrescenta a isso, e nao a
distancia ate uma trajetoria sorteada do nada.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import numpy as np

from ..optimization.evolution import EvolutionConfig, EvolutionResult, evolve
from ..optimization.fitness import FitnessEvaluator
from ..optimization.representation import TrajectoryEncoding


@dataclass
class SearchComparison:
    """Cenario A (sem otimizacao) contra cenario B (depois da busca)."""

    initial_cost: float
    initial_physical_s: float
    final_cost: float
    final_physical_s: float
    generations: int
    evaluations: int
    stopped_by: str
    seconds: float
    random_best_cost: float
    random_evaluations: int
    perturbation_best_cost: float
    history: List[Dict[str, float]] = field(default_factory=list)

    @property
    def improvement(self) -> float:
        return self.initial_cost - self.final_cost

    @property
    def beats_random(self) -> float:
        """Quanto a busca ganha da amostragem uniforme de mesmo orcamento."""
        return self.random_best_cost - self.final_cost

    @property
    def beats_perturbation(self) -> float:
        """Quanto ela ganha da perturbacao cega das mesmas sementes.

        E este o numero que separa evolucao de sorteio: os dois partem da mesma
        populacao e gastam o mesmo orcamento, e so um deles seleciona.
        """
        return self.perturbation_best_cost - self.final_cost

    @property
    def real_evolution(self) -> bool:
        return self.beats_perturbation > 0.0

    @property
    def convergence_generation(self) -> Optional[int]:
        """Geracao a partir da qual o melhor custo nao melhora mais que 1 ms."""
        if not self.history:
            return None
        best = min(entry["best_cost"] for entry in self.history)
        for entry in self.history:
            if entry["best_cost"] <= best + 1e-3:
                return int(entry["generation"])
        return None

    def to_dict(self) -> Dict[str, object]:
        return {
            "cenario_a_sem_otimizacao": {
                "cost": self.initial_cost,
                "physical_s": self.initial_physical_s,
            },
            "cenario_b_apos_evolucao": {
                "cost": self.final_cost,
                "physical_s": self.final_physical_s,
            },
            "improvement": self.improvement,
            "generations": self.generations,
            "evaluations": self.evaluations,
            "stopped_by": self.stopped_by,
            "seconds": self.seconds,
            "convergence_generation": self.convergence_generation,
            "controle_uniforme": {
                "best_cost": self.random_best_cost,
                "evaluations": self.random_evaluations,
                "evolucao_ganha_por": self.beats_random,
            },
            "historico": self.history,
            "controle_perturbacao_cega": {
                "best_cost": self.perturbation_best_cost,
                "evaluations": self.random_evaluations,
                "evolucao_ganha_por": self.beats_perturbation,
                "evolucao_real": self.real_evolution,
            },
        }


def random_search(
    evaluator: FitnessEvaluator,
    encoding: TrajectoryEncoding,
    evaluations: int,
    seed: int,
    batch: int = 100,
) -> Dict[str, float]:
    """Amostragem uniforme dentro dos limites da pista, mesmo orcamento.

    Diz o quanto o espaco de busca e dificil, e portanto o quanto a populacao
    semeada com voltas reais ja vale. **Nao** isola o efeito dos operadores:
    sortear 361 deslocamentos independentes produz uma trajetoria que serpenteia
    de borda a borda, e perder disso nao prova quase nada.
    """
    generator = np.random.default_rng(seed)
    best = float("inf")
    spent = 0
    while spent < evaluations:
        size = min(batch, evaluations - spent)
        population = encoding.random(generator, size)
        cost = evaluator.evaluate(population)["cost"]
        best = min(best, float(cost.min()))
        spent += size
    return {"best_cost": best, "evaluations": spent}


def random_perturbation(
    evaluator: FitnessEvaluator,
    encoding: TrajectoryEncoding,
    population: np.ndarray,
    evaluations: int,
    seed: int,
    amplitude_m: float = 0.6,
) -> Dict[str, float]:
    """Perturbacao cega da mesma populacao inicial, mesmo orcamento.

    Este e o controle que decide a pergunta. Parte exatamente das mesmas
    sementes e gasta exatamente as mesmas avaliacoes, mas **sem selecao, sem
    cruzamento e sem elitismo dirigido**: sorteia uma semente, aplica a mesma
    mutacao correlacionada do algoritmo, avalia, guarda se for a melhor ate
    agora. E o que sobra do algoritmo evolutivo quando se tira dele a evolucao.

    Se a busca nao ganhar deste controle, o que o grafico de custo mostra e
    apenas o efeito de guardar o melhor de muitas amostras.
    """
    from ..optimization.operators import mutate

    generator = np.random.default_rng(seed)
    scores = evaluator.evaluate(population)
    best = float(scores["cost"].min())
    spent = population.shape[0]
    size = population.shape[0]

    while spent < evaluations:
        take = min(size, evaluations - spent)
        parents = population[generator.integers(0, population.shape[0], take)]
        children = mutate(parents, encoding, generator, rate=1.0, amplitude_m=amplitude_m)
        cost = evaluator.evaluate(children)["cost"]
        best = min(best, float(cost.min()))
        spent += take
    return {"best_cost": best, "evaluations": spent}


def compare(
    evaluator: FitnessEvaluator,
    encoding: TrajectoryEncoding,
    population: np.ndarray,
    config: EvolutionConfig,
    control_seed: int = 99,
    progress: Optional[Callable[[str], None]] = None,
) -> SearchComparison:
    """Roda os dois cenarios e o controle aleatorio, e devolve a comparacao."""
    scores = evaluator.evaluate(population)
    best_start = int(np.argmin(scores["cost"]))
    initial_cost = float(scores["cost"][best_start])
    initial_physical = float(scores["physical_time_s"][best_start])

    started = time.time()
    before = evaluator.evaluations
    result = evolve(evaluator, encoding, population, config, progress=progress)
    seconds = time.time() - started
    spent = evaluator.evaluations - before

    final = evaluator.evaluate(result.best_genome[None, :])
    if progress:
        progress(f"  controle uniforme: {spent} avaliacoes sorteadas...")
    control = random_search(evaluator, encoding, spent, control_seed)
    if progress:
        progress(f"  controle de perturbacao cega: {spent} avaliacoes...")
    blind = random_perturbation(
        evaluator, encoding, population, spent, control_seed + 1,
        amplitude_m=config.mutation_amplitude_m,
    )

    return SearchComparison(
        initial_cost=initial_cost,
        initial_physical_s=initial_physical,
        final_cost=float(final["cost"][0]),
        final_physical_s=float(final["physical_time_s"][0]),
        generations=result.generations_run,
        evaluations=spent,
        stopped_by=result.stopped_by,
        seconds=seconds,
        random_best_cost=control["best_cost"],
        random_evaluations=control["evaluations"],
        perturbation_best_cost=blind["best_cost"],
        history=result.history,
    )
