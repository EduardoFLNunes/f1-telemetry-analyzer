"""Populacao inicial do algoritmo evolutivo.

Comecar com trajetorias aleatorias e jogar fora o que ja se sabe. O dataset tem
128 voltas reais dentro dos limites da pista, e a LSTM produz uma referencia
condicionada ao melhor desempenho -- essas sao as sementes.

Tres origens, e cada uma cobre uma fraqueza das outras:

* **voltas reais** — fisicamente possiveis por construcao, porque alguem as
  dirigiu. Dao ao algoritmo o formato geral do tracado de graca.
* **composicao dos melhores trechos** — cada microsetor vem da volta que foi
  mais rapida nele. E a "volta ideal" do enunciado, agora como trajetoria e nao
  so como soma de tempos. Nenhuma volta real e assim.
* **referencia da LSTM** — o que o modelo diz que a pilotagem de perda zero faz.
  Pode conter trechos que nenhuma volta do dataset tem.

Mais uma fracao pequena de individuos aleatorios, para o algoritmo nao ficar
preso ao subespaco que o piloto ja explorou.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import numpy as np

from ..track.geometry import TrackGeometry
from ..track.microsectors import Microsectors
from ..track.trajectory import clip_to_corridor
from .representation import TrajectoryEncoding

# Comprimento da transicao entre dois trechos de voltas diferentes. 40 m a 150
# km/h e menos de um segundo -- longo o bastante para a costura nao virar um
# degrau de curvatura, curto o bastante para nao apagar o trecho.
DEFAULT_BLEND_M = 40.0


def lateral_by_lap(store, lap_ids: Optional[Sequence[str]] = None) -> Dict[str, np.ndarray]:
    """{lap_id: deslocamento lateral na grade}."""
    wanted = list(lap_ids) if lap_ids is not None else list(store.lap_ids)
    pivot = store.frame.pivot(index="lap_id", columns="grid_index", values="lateral")
    return {
        lap_id: pivot.loc[lap_id].to_numpy(dtype=float)
        for lap_id in wanted
        if lap_id in pivot.index
    }


def composite_best_segments(
    track: TrackGeometry,
    sectors: Microsectors,
    laterals: Dict[str, np.ndarray],
    best_lap_per_sector: Sequence[str],
    blend_m: float = DEFAULT_BLEND_M,
) -> np.ndarray:
    """Costura, microsetor a microsetor, a trajetoria de quem foi mais rapido ali.

    A costura e um crossfade e nao um corte. Trocar de volta na fronteira do
    microsetor produz um degrau lateral de ate um metro entre dois pontos da
    grade, e um degrau de um metro em 2 m de pista e uma curvatura de raio 2 m --
    o simulador leria isso como uma freada, e a "melhor composicao possivel"
    sairia mais lenta que qualquer volta que a compoe.
    """
    available = {lap: values for lap, values in laterals.items()}
    fallback = next(iter(available.values()))
    chosen = np.vstack(
        [available.get(str(lap), fallback) for lap in best_lap_per_sector]
    )                                                   # (setores, grade)

    positions = np.arange(track.size)
    sector = sectors.index
    primary = chosen[sector, positions]
    previous = chosen[(sector - 1) % sectors.count, positions]
    following = chosen[(sector + 1) % sectors.count, positions]

    distance_from_start = track.s - sectors.edges_s[sector]
    distance_to_end = sectors.edges_s[sector + 1] - track.s
    half = float(blend_m) / 2.0

    out = primary.copy()
    entering = distance_from_start < half
    weight = 0.5 + distance_from_start[entering] / float(blend_m)
    out[entering] = weight * primary[entering] + (1.0 - weight) * previous[entering]

    leaving = distance_to_end < half
    weight = 0.5 + distance_to_end[leaving] / float(blend_m)
    out[leaving] = weight * primary[leaving] + (1.0 - weight) * following[leaving]

    return clip_to_corridor(track, out)


def build_population(
    encoding: TrajectoryEncoding,
    size: int,
    laterals: Dict[str, np.ndarray],
    extra: Optional[Sequence[np.ndarray]] = None,
    random_fraction: float = 0.1,
    jitter_m: float = 0.5,
    seed: int = 20260823,
) -> np.ndarray:
    """(size, genes) — genomas iniciais.

    `extra` recebe trajetorias privilegiadas (a composicao dos melhores trechos,
    a referencia da LSTM). Elas entram inteiras e tambem como base das copias
    perturbadas, porque comecar com 128 copias de voltas medianas e uma copia da
    melhor ideia desperdica a melhor ideia.
    """
    generator = np.random.default_rng(seed)
    seeds: List[np.ndarray] = []

    for candidate in extra or []:
        seeds.append(encoding.encode(np.asarray(candidate, dtype=float)))
    for values in laterals.values():
        seeds.append(encoding.encode(values))

    if not seeds:
        raise ValueError("nenhuma semente para a populacao inicial")

    population = [seeds[index % len(seeds)] for index in range(size)]
    population = np.vstack(population)

    # Depois de esgotadas as sementes distintas, as repetidas entram perturbadas
    # -- uma populacao com clones nao tem o que selecionar.
    duplicated = np.arange(size) >= len(seeds)
    if duplicated.any():
        noise = generator.normal(0.0, jitter_m, size=(int(duplicated.sum()), encoding.genes))
        population[duplicated] += noise

    random_count = int(round(size * float(random_fraction)))
    if random_count > 0:
        population[-random_count:] = encoding.random(generator, random_count)

    return encoding.clip(population)
