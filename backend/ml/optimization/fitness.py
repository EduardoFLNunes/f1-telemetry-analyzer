"""Funcao de aptidao: o que faz uma trajetoria ser melhor que outra.

O custo e em segundos, e todo termo e convertido para segundos antes de somar.
Isso nao e cosmetico: pesos em unidades diferentes so podem ser escolhidos por
tentativa, e pesos escolhidos por tentativa escondem o que a busca esta
otimizando de verdade.

    custo = (1 - a)*tempo_fisico + a*tempo_da_LSTM + penalizacoes

**Por que dois tempos.** A simulacao fisica nao sabe nada deste piloto: ela diz
o que o carro aguenta. A LSTM nao sabe nada de trajetorias que ninguem dirigiu:
ela diz o que este piloto costuma extrair de uma linha com esta forma. Usar so
a fisica produz um tracado que ninguem consegue seguir; usar so a rede produz um
tracado que nunca supera a melhor volta ja gravada, porque e dela que a rede
aprendeu. `a` regula quanto de cada um, e o valor padrao pende para a fisica.

**Por que os limites nao aparecem como penalizacao dominante.** Trajetoria fora
da pista nao e penalizada, e impedida: o `decode` da codificacao clipa contra o
corredor antes de qualquer avaliacao. A penalizacao continua existindo como
rede de seguranca, e o valor dela num individuo saudavel e exatamente zero.

**Por que as penalizacoes de forma sao calibradas nas voltas reais.** "Volante
demais" e "curvatura brusca demais" nao tem valor absoluto -- dependem da pista
e do carro. Os limiares saem do p95 das 125 voltas gravadas: o que o piloto faz
de verdade nao e penalizado, e o que passa disso e.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np

from ..track.geometry import TrackGeometry, _closed_derivative, _smoothing_window
from ..track.trajectory import corridor_violation, lateral_derivative
from ..track.trajectory import curvature as trajectory_curvature
from .lap_time_model import prepare, solve_speed, step_times
from .representation import TrajectoryEncoding
from .vehicle_model import VehicleEnvelope


@dataclass
class FitnessWeights:
    """Quanto cada termo pesa, tudo em segundos."""

    # 0 = so fisica, 1 = so LSTM. O padrao pende para a fisica porque e ela que
    # pode apontar algo melhor do que o piloto ja fez.
    surrogate_weight: float = 0.25

    # Segundos de penalizacao por metro-medio fora dos limites da pista.
    corridor: float = 30.0

    # Segundos por unidade de excesso de serpenteio (percurso lateral total
    # acima do que as voltas reais fazem).
    weaving: float = 8.0

    # Segundos por unidade de excesso de variacao de curvatura.
    curvature_jerk: float = 6.0

    # Bonus por velocidade de saida de curva, em segundos por m/s ganho.
    # Negativo porque reduz o custo.
    exit_speed: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "surrogate_weight": self.surrogate_weight,
            "corridor": self.corridor,
            "weaving": self.weaving,
            "curvature_jerk": self.curvature_jerk,
            "exit_speed": self.exit_speed,
        }


@dataclass
class ShapeReference:
    """O que uma trajetoria dirigida de verdade parece, em numeros.

    Calibrado nas voltas do dataset. Serve de limiar: penaliza-se o que passa
    disso, e nao o que se parece com pilotagem real.
    """

    weaving: float           # percurso lateral por metro de pista
    curvature_jerk: float    # |dk/ds| medio

    def to_dict(self) -> Dict[str, float]:
        return {"weaving": self.weaving, "curvature_jerk": self.curvature_jerk}


@dataclass
class FitnessReport:
    """Custo de um individuo e de onde ele veio."""

    cost: float
    physical_time_s: float
    surrogate_time_s: float
    blended_time_s: float
    penalties: Dict[str, float] = field(default_factory=dict)
    path_length_m: float = 0.0

    @property
    def penalty_total(self) -> float:
        return float(sum(self.penalties.values()))


def shape_metrics(track: TrackGeometry, laterals: np.ndarray) -> Dict[str, np.ndarray]:
    """Serpenteio e variacao de curvatura de cada trajetoria."""
    batch = np.atleast_2d(np.asarray(laterals, dtype=float))
    window = _smoothing_window(12.0, track.step)

    weaving = np.empty(batch.shape[0])
    jerk = np.empty(batch.shape[0])
    for index, row in enumerate(batch):
        derivative = lateral_derivative(track, row)
        weaving[index] = float(np.mean(np.abs(derivative)))
        curvature = trajectory_curvature(track, row)
        rate = _closed_derivative(curvature, track.step, window, order=3)
        jerk[index] = float(np.mean(np.abs(rate)))
    return {"weaving": weaving, "curvature_jerk": jerk}


def fit_shape_reference(
    track: TrackGeometry, laterals: np.ndarray, quantile: float = 0.95
) -> ShapeReference:
    """Calibra os limiares de forma nas voltas reais."""
    metrics = shape_metrics(track, laterals)
    return ShapeReference(
        weaving=float(np.quantile(metrics["weaving"], quantile)),
        curvature_jerk=float(np.quantile(metrics["curvature_jerk"], quantile)),
    )


class FitnessEvaluator:
    """Avalia populacoes inteiras de uma vez."""

    def __init__(
        self,
        track: TrackGeometry,
        encoding: TrajectoryEncoding,
        envelope: VehicleEnvelope,
        shape_reference: ShapeReference,
        weights: Optional[FitnessWeights] = None,
        surrogate=None,
        surrogate_features=None,
    ):
        self.track = track
        self.encoding = encoding
        self.envelope = envelope
        self.shape = shape_reference
        self.weights = weights or FitnessWeights()
        self.surrogate = surrogate
        # Callable (laterals (n, grade)) -> (n, grade, n_in) para a rede
        # substituta. Fica de fora desta classe porque montar os atributos
        # depende do que a tarefa da LSTM pediu, e nao da aptidao.
        self.surrogate_features = surrogate_features
        self.evaluations = 0

    def surrogate_times(self, laterals: np.ndarray) -> np.ndarray:
        """Tempo de volta segundo a rede substituta, ou NaN se nao houver rede."""
        if self.surrogate is None or self.surrogate_features is None:
            return np.full(np.atleast_2d(laterals).shape[0], np.nan)
        from ..models.sequences import SURROGATE_TASK, drop_warmup, with_warmup

        # Mesmo aquecimento circular da rede geradora, e pela mesma razao: sem
        # ele as duas pontas da volta sao avaliadas com a rede fria, e o
        # algoritmo evolutivo passaria a otimizar contra esse artefato.
        pad = SURROGATE_TASK.window
        inputs = with_warmup(self.surrogate_features(laterals), pad)
        predicted = drop_warmup(self.surrogate.predict(inputs), pad)
        # A rede devolve tempo por passo; o tempo de volta e a soma deles.
        return np.asarray(predicted, dtype=float)[..., 0].sum(axis=1)

    def evaluate(self, population: np.ndarray) -> Dict[str, np.ndarray]:
        """Custo e componentes de cada individuo da populacao."""
        genomes = np.atleast_2d(np.asarray(population, dtype=float))
        laterals = self.encoding.decode_many(genomes)
        self.evaluations += genomes.shape[0]

        curvature, lengths = prepare(self.track, laterals)
        speed = solve_speed(curvature, lengths, self.envelope)
        per_step = step_times(speed, lengths)
        physical = per_step.sum(axis=1)

        surrogate = self.surrogate_times(laterals)
        blend = float(self.weights.surrogate_weight)
        blended = np.where(
            np.isfinite(surrogate), (1.0 - blend) * physical + blend * surrogate, physical
        )

        metrics = shape_metrics(self.track, laterals)
        violation = np.array(
            [float(np.mean(corridor_violation(self.track, row))) for row in laterals]
        )

        penalties = {
            "corridor": self.weights.corridor * violation,
            "weaving": self.weights.weaving
            * np.maximum(metrics["weaving"] - self.shape.weaving, 0.0),
            "curvature_jerk": self.weights.curvature_jerk
            * np.maximum(metrics["curvature_jerk"] - self.shape.curvature_jerk, 0.0)
            / max(self.shape.curvature_jerk, 1e-9),
        }
        if self.weights.exit_speed:
            # Velocidade nos pontos em que o carro volta a acelerar: e a saida
            # de curva, que e o que paga a reta seguinte.
            accelerating = np.diff(speed, append=speed[:, :1], axis=1) > 0
            exit_speed = np.array(
                [
                    float(np.mean(row[mask])) if mask.any() else 0.0
                    for row, mask in zip(speed, accelerating)
                ]
            )
            penalties["exit_speed"] = -self.weights.exit_speed * exit_speed

        total_penalty = np.sum(np.vstack(list(penalties.values())), axis=0)
        return {
            "cost": blended + total_penalty,
            "physical_time_s": physical,
            "surrogate_time_s": surrogate,
            "blended_time_s": blended,
            "path_length_m": lengths.sum(axis=1),
            "penalty_total": total_penalty,
            **{f"penalty_{name}": values for name, values in penalties.items()},
        }

    def report(self, genome: np.ndarray) -> FitnessReport:
        """Detalhe de um individuo so."""
        values = self.evaluate(np.atleast_2d(genome))
        penalties = {
            key.replace("penalty_", ""): float(value[0])
            for key, value in values.items()
            if key.startswith("penalty_") and key != "penalty_total"
        }
        return FitnessReport(
            cost=float(values["cost"][0]),
            physical_time_s=float(values["physical_time_s"][0]),
            surrogate_time_s=float(values["surrogate_time_s"][0]),
            blended_time_s=float(values["blended_time_s"][0]),
            penalties=penalties,
            path_length_m=float(values["path_length_m"][0]),
        )
