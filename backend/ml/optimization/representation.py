"""Como uma trajetoria vira um individuo do algoritmo evolutivo.

O genoma e o deslocamento lateral em pontos de controle espacados ao longo da
pista, e nao nos 2167 pontos da grade. A razao e concreta: mutar 2167 numeros
independentes produz ruido de alta frequencia, e ruido de alta frequencia numa
trajetoria e curvatura enorme -- o simulador freia em cada oscilacao e o
individuo morre por um defeito de representacao, nao por ser uma linha ruim.

Com um ponto de controle a cada 40 m e spline cubica periodica entre eles, toda
trajetoria representavel ja e suave. E o espaco de busca cai de 2167 para 108
dimensoes.

Os limites sao por gene: cada ponto de controle tem seu proprio intervalo, dado
pela largura da pista naquele ponto menos a meia-bitola do carro. Assim um
individuo sorteado dentro dos limites ja nasce dentro da pista, e o cruzamento
de dois individuos validos so pode sair fora nas curvas onde a spline
extrapola -- que e o que o `decode` corrige clipando.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from .. import config
from ..track.geometry import TrackGeometry
from ..track.trajectory import clip_to_corridor, resample_control_points

# Espacamento entre pontos de controle. A curva mais curta de Interlagos tem
# ~44 m de arco, entao 25 m garante pelo menos dois genes por curva -- o minimo
# para descrever entrada, apice e saida como coisas distintas.
DEFAULT_CONTROL_SPACING_M = 25.0

# Peso da regularizacao no `encode`. Calibrado abaixo.
SMOOTHNESS = 1.0


@dataclass(frozen=True)
class TrajectoryEncoding:
    """A ponte entre genoma (pontos de controle) e trajetoria (grade).

    A ponte e uma matriz. A spline e linear nos valores de controle, entao
    decodificar e multiplicar o genoma pela base `(grade x genes)` em que cada
    coluna e a spline de um ponto de controle sozinho. Duas consequencias:

    * decodificar uma populacao inteira e um unico produto de matrizes, e nao um
      laco de splines -- e a busca passa a gastar o tempo na fisica, que e onde
      deve gastar;
    * codificar deixa de ser "amostrar nos pontos de controle" e passa a ser
      **ajustar por minimos quadrados**, que e o que preserva a trajetoria.

    A diferenca entre os dois nao e sutil. Amostrando, a melhor volta real --
    que simula em 92,2 s -- voltava da codificacao valendo 115 s: os pontos de
    controle acertam a linha a cada 40 m e a spline entre eles inventa o resto,
    com oscilacao suficiente para o simulador frear. Ajustando, o genoma e a
    melhor representacao possivel daquela trajetoria naquele numero de genes.
    """

    track: TrackGeometry
    control_s: np.ndarray        # (genes,) posicao de cada ponto de controle
    lower: np.ndarray            # (genes,) limite direito, negativo
    upper: np.ndarray            # (genes,) limite esquerdo, positivo
    basis: np.ndarray            # (grade, genes) spline de cada gene isolado

    @property
    def genes(self) -> int:
        return int(self.control_s.size)

    def decode(self, genome: np.ndarray) -> np.ndarray:
        """Genoma -> deslocamento lateral em toda a grade, dentro da pista."""
        genome = np.clip(np.asarray(genome, dtype=float), self.lower, self.upper)
        return clip_to_corridor(self.track, self.basis @ genome)

    def decode_many(self, population: np.ndarray) -> np.ndarray:
        genomes = self.clip(np.atleast_2d(np.asarray(population, dtype=float)))
        return clip_to_corridor(self.track, genomes @ self.basis.T)

    def encode(self, lateral: np.ndarray, smoothness: Optional[float] = None) -> np.ndarray:
        """Trajetoria na grade -> genoma que melhor a reproduz.

        Minimos quadrados **regularizados**: alem de aproximar a trajetoria, a
        solucao paga um preco pela segunda diferenca entre genes vizinhos.

        Sem esse termo o ajuste oscila. E a oscilacao classica de aproximar por
        base suave um sinal que tem transicao rapida -- e a trajetoria real tem
        varias, porque em alguns trechos ela cruza a pista compensando um
        pequeno defeito da propria centerline. Medido na melhor volta: sem
        regularizacao o ajuste tinha erro RMS de so 0,14 m e mesmo assim
        simulava 12 s mais lento, porque o toco de oscilacao que sobrava valia,
        depois de duas derivadas, um raio de 45 m a 265 km/h.
        """
        lateral = np.asarray(lateral, dtype=float)
        weight = float(SMOOTHNESS if smoothness is None else smoothness)
        if weight <= 0:
            genome, *_ = np.linalg.lstsq(self.basis, lateral, rcond=None)
            return np.clip(genome, self.lower, self.upper)

        # Segunda diferenca circular: a pista fecha, entao o primeiro gene tem
        # vizinho anterior.
        genes = self.genes
        index = np.arange(genes)
        penalty = np.zeros((genes, genes))
        penalty[index, index] = -2.0
        penalty[index, (index + 1) % genes] += 1.0
        penalty[index, (index - 1) % genes] += 1.0

        design = np.vstack([self.basis, math.sqrt(weight) * penalty])
        target = np.concatenate([lateral, np.zeros(genes)])
        genome, *_ = np.linalg.lstsq(design, target, rcond=None)
        return np.clip(genome, self.lower, self.upper)

    def random(self, generator: np.random.Generator, count: int = 1) -> np.ndarray:
        """Individuos uniformes dentro dos limites -- usados so como diversidade."""
        spread = self.upper - self.lower
        return self.lower + generator.random((count, self.genes)) * spread

    def clip(self, population: np.ndarray) -> np.ndarray:
        return np.clip(np.asarray(population, dtype=float), self.lower, self.upper)


def build_encoding(
    track: TrackGeometry,
    spacing_m: float = DEFAULT_CONTROL_SPACING_M,
    car_half_width: float = config.CAR_HALF_WIDTH_M,
    kerb_allowance: float = config.KERB_ALLOWANCE_M,
) -> TrajectoryEncoding:
    """Monta a codificacao para uma pista."""
    count = max(int(round(track.length / float(spacing_m))), 8)
    control_s = np.linspace(0.0, track.length, count, endpoint=False)

    # Base da spline: a coluna `j` e o que sai na grade quando so o gene `j`
    # vale 1. Como a spline e linear nos valores de controle, essa matriz
    # descreve a codificacao inteira.
    basis = np.column_stack(
        [
            resample_control_points(track, control_s, np.eye(count)[j])
            for j in range(count)
        ]
    )

    low, high = track.corridor(car_half_width, kerb_allowance)
    index = track.index_of(control_s)
    # O limite de cada gene e o mais apertado da vizinhanca que ele governa, e
    # nao o do proprio ponto: a spline entre dois genes passa por pontos que
    # nenhum dos dois representa, e num estreitamento e justamente ali que ela
    # sai da pista.
    span = max(int(round(spacing_m / track.step)), 1)
    offsets = np.arange(-span // 2, span // 2 + 1)
    neighbourhood = (index[:, None] + offsets[None, :]) % track.size
    return TrajectoryEncoding(
        track=track,
        control_s=control_s,
        lower=low[neighbourhood].max(axis=1),
        upper=high[neighbourhood].min(axis=1),
        basis=basis,
    )
