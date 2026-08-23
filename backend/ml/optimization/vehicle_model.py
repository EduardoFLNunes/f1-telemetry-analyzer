"""Envelope dinamico do carro, medido nas voltas do proprio piloto.

O algoritmo evolutivo precisa saber quanto o carro aguenta antes de poder dizer
que uma trajetoria e mais rapida que outra. Esse limite nao e digitado aqui: ele
e ajustado a partir das voltas gravadas.

**Demanda nao e capacidade.** Esta e a armadilha central deste ajuste, e ela
custou uma versao inteira do modelo. Tomar o percentil 98 do g lateral em cada
faixa de velocidade parece medir o limite do carro, e nao mede: mede o que o
piloto *pediu* naquela faixa. A 272 km/h o carro esta em reta, entao o g lateral
observado e 0,41 -- e o simulador, lendo isso como limite, concluia que o carro
nao pode fazer curva rapida e devolvia voltas de 131 s onde o piloto faz 88.

O conserto e separar as duas coisas:

* **lateral e frenagem** so sao medidos onde estao sendo exigidos (curva de
  verdade, freio pisado de verdade), e o que sai dessas faixas e ajustado por
  `a = a0 + k*v^2` -- a forma que a fisica preve, porque a carga aerodinamica
  cresce com o quadrado da velocidade. Ai da para extrapolar para as faixas em
  que o piloto nunca precisou do limite.
* **tracao** e medida so com o acelerador no fundo, e nao segue forma
  parametrica nenhuma: ela cai com a velocidade porque potencia e arrasto
  mandam, e isso e uma curva de motor, nao uma parabola.

O quantil e 98% e nao o maximo: o maximo de um canal de telemetria e o pico de
um quadro, e um pico nao e um limite sustentavel.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Sequence

import numpy as np
import pandas as pd

from .. import config

G = 9.80665

# Faixas de velocidade do ajuste. 12 faixas entre 50 e 300 km/h dao ~20 km/h
# cada, largo o bastante para ter amostras e estreito o bastante para a
# aerodinamica aparecer.
DEFAULT_BINS = 12
MIN_SPEED_KMH = 50.0
DEFAULT_QUANTILE = 0.98

# Uma faixa com poucas amostras nao ajusta nada; ela e preenchida pelas vizinhas.
MIN_SAMPLES_PER_BIN = 200

# Quantas amostras de exigencia real uma faixa precisa para o limite dela contar.
MIN_DEMAND_SAMPLES = 100

# A partir de quanto o carro esta fazendo curva de verdade, e nao seguindo a
# reta. 1,0 g lateral e menos de um terco do que este carro entrega -- serve
# para separar reta de curva, nao para achar o limite.
CORNERING_THRESHOLD_G = 1.0

# Pedal pisado o bastante para a leitura valer como exigencia do limite.
BRAKE_PEDAL_THRESHOLD = 0.5
THROTTLE_PEDAL_THRESHOLD = 0.9


@dataclass
class VehicleEnvelope:
    """Aceleracao maxima disponivel em cada eixo, por velocidade."""

    speed_mps: np.ndarray        # (bins,) centro de cada faixa
    lateral: np.ndarray          # (bins,) m/s^2 lateral sustentavel
    braking: np.ndarray          # (bins,) m/s^2 de frenagem
    traction: np.ndarray         # (bins,) m/s^2 de aceleracao
    top_speed_mps: float
    samples: np.ndarray          # (bins,) quantas amostras sustentam cada faixa
    source_laps: int = 0

    def _interp(self, table: np.ndarray, speed) -> np.ndarray:
        speed = np.atleast_1d(np.asarray(speed, dtype=float))
        return np.interp(speed, self.speed_mps, table)

    def lateral_limit(self, speed) -> np.ndarray:
        return self._interp(self.lateral, speed)

    def braking_limit(self, speed) -> np.ndarray:
        return self._interp(self.braking, speed)

    def traction_limit(self, speed) -> np.ndarray:
        return self._interp(self.traction, speed)

    def cornering_speed(self, curvature) -> np.ndarray:
        """Velocidade maxima sustentavel numa curva de dada curvatura.

        `v = sqrt(a_lat / k)`, so que `a_lat` depende de `v` -- entao a solucao
        e um ponto fixo. Tres iteracoes bastam: o envelope e monotono e suave, e
        a correcao da terceira ja esta abaixo de 0,1 km/h.
        """
        curvature = np.abs(np.asarray(curvature, dtype=float))
        speed = np.full(curvature.shape, self.top_speed_mps)
        for _ in range(3):
            limit = self.lateral_limit(speed)
            with np.errstate(divide="ignore", invalid="ignore"):
                candidate = np.sqrt(np.where(curvature > 1e-9, limit / np.maximum(curvature, 1e-9), np.inf))
            speed = np.minimum(candidate, self.top_speed_mps)
        return speed

    def longitudinal_available(self, speed, lateral_used, braking: bool) -> np.ndarray:
        """Quanto sobra no eixo longitudinal dado o quanto o lateral ja usa.

        Elipse de atrito: os dois eixos dividem a mesma aderencia, entao pedir
        aceleracao maxima no meio de uma curva de 3 g e pedir o que o pneu nao
        tem. Sem este termo o simulador acelera na tangencia e o tempo de volta
        sai fisicamente impossivel.
        """
        speed = np.asarray(speed, dtype=float)
        limit = self.braking_limit(speed) if braking else self.traction_limit(speed)
        usage = np.clip(np.abs(lateral_used) / np.maximum(self.lateral_limit(speed), 1e-6), 0.0, 1.0)
        return limit * np.sqrt(np.maximum(1.0 - usage**2, 0.0))

    def to_dict(self) -> Dict[str, object]:
        return {
            "speed_mps": self.speed_mps.tolist(),
            "lateral": self.lateral.tolist(),
            "braking": self.braking.tolist(),
            "traction": self.traction.tolist(),
            "top_speed_mps": self.top_speed_mps,
            "samples": self.samples.tolist(),
            "source_laps": self.source_laps,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "VehicleEnvelope":
        return cls(
            speed_mps=np.asarray(payload["speed_mps"], dtype=float),
            lateral=np.asarray(payload["lateral"], dtype=float),
            braking=np.asarray(payload["braking"], dtype=float),
            traction=np.asarray(payload["traction"], dtype=float),
            top_speed_mps=float(payload["top_speed_mps"]),
            samples=np.asarray(payload.get("samples", []), dtype=float),
            source_laps=int(payload.get("source_laps", 0)),
        )

    def describe(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "v_kmh": np.round(self.speed_mps * 3.6, 1),
                "lateral_g": np.round(self.lateral / G, 2),
                "frenagem_g": np.round(self.braking / G, 2),
                "tracao_g": np.round(self.traction / G, 2),
                "amostras": self.samples.astype(int),
            }
        )


def _fill_gaps(values: np.ndarray, counts: np.ndarray) -> np.ndarray:
    """Faixas sem amostras suficientes herdam das vizinhas que tem."""
    usable = (counts >= MIN_SAMPLES_PER_BIN) & np.isfinite(values) & (values > 0)
    if not usable.any():
        raise ValueError("nenhuma faixa de velocidade tem amostras suficientes")
    index = np.arange(values.size)
    return np.interp(index, index[usable], values[usable])


def _aero_fit(speed_mps: np.ndarray, observed: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Ajusta `a = a0 + k*v^2` e devolve o valor em todas as velocidades.

    A forma vem da fisica: a aderencia disponivel e proporcional a carga, e a
    carga e peso mais downforce, que cresce com o quadrado da velocidade. Ajustar
    isso com as faixas em que o limite foi realmente exigido permite extrapolar
    para as faixas em que nao foi -- que e o caso de toda faixa acima de 220
    km/h em Interlagos, onde o carro esta em reta.

    `k` e forcado a nao ser negativo: aderencia caindo com a velocidade nao e
    algo que o carro faz, e um ajuste em cima de faixas ruidosas.
    """
    usable = np.isfinite(observed) & (weights > 0)
    if usable.sum() < 2:
        return _fill_gaps(observed, weights)

    basis = np.column_stack([np.ones(usable.sum()), speed_mps[usable] ** 2])
    scale = np.sqrt(weights[usable])
    solution, *_ = np.linalg.lstsq(basis * scale[:, None], observed[usable] * scale, rcond=None)
    intercept, slope = float(solution[0]), max(float(solution[1]), 0.0)
    if intercept <= 0.0:
        intercept = float(np.min(observed[usable]))
    fitted = intercept + slope * speed_mps**2
    # Onde o dado observado supera o ajuste, o dado manda: ele e uma medida, e o
    # ajuste e so a forma que preenche o que nao foi medido.
    return np.maximum(fitted, np.nan_to_num(observed, nan=0.0))


def fit_envelope(
    frame: pd.DataFrame,
    bins: int = DEFAULT_BINS,
    quantile: float = DEFAULT_QUANTILE,
    source_laps: int = 0,
) -> VehicleEnvelope:
    """Ajusta o envelope a partir do store de voltas.

    Usa `speed_kmh`, `lateral_g`, `longitudinal_g` e -- quando existirem --
    `throttle` e `brake`. Os pedais sao o que permite separar "o carro nao
    conseguiu" de "o piloto nao pediu".
    """
    speed_kmh = frame["speed_kmh"].to_numpy(dtype=float)
    lateral = np.abs(frame["lateral_g"].to_numpy(dtype=float)) * G
    longitudinal = frame["longitudinal_g"].to_numpy(dtype=float) * G
    throttle = (
        frame["throttle"].to_numpy(dtype=float)
        if "throttle" in frame.columns
        else np.full(speed_kmh.shape, np.nan)
    )
    brake = (
        frame["brake"].to_numpy(dtype=float)
        if "brake" in frame.columns
        else np.full(speed_kmh.shape, np.nan)
    )

    valid = np.isfinite(speed_kmh) & np.isfinite(lateral) & np.isfinite(longitudinal)
    valid &= speed_kmh >= MIN_SPEED_KMH
    speed_kmh = speed_kmh[valid]
    lateral, longitudinal = lateral[valid], longitudinal[valid]
    throttle, brake = throttle[valid], brake[valid]
    if speed_kmh.size < bins * MIN_SAMPLES_PER_BIN:
        raise ValueError(f"amostras insuficientes para ajustar o envelope ({speed_kmh.size})")

    top = float(np.percentile(speed_kmh, 99.9)) / 3.6
    edges = np.linspace(speed_kmh.min(), speed_kmh.max(), bins + 1)
    centres = 0.5 * (edges[:-1] + edges[1:])
    speed_mps = centres / 3.6
    index = np.clip(np.digitize(speed_kmh, edges) - 1, 0, bins - 1)

    # Onde cada limite esta sendo exigido de verdade.
    cornering = lateral > CORNERING_THRESHOLD_G * G
    braking = (brake > BRAKE_PEDAL_THRESHOLD) if np.isfinite(brake).any() else longitudinal < -G
    driving = (
        (throttle > THROTTLE_PEDAL_THRESHOLD)
        if np.isfinite(throttle).any()
        else longitudinal > 0
    )

    lateral_limit = np.full(bins, np.nan)
    braking_limit = np.full(bins, np.nan)
    traction_limit = np.full(bins, np.nan)
    counts = np.zeros(bins)
    lateral_support = np.zeros(bins)
    braking_support = np.zeros(bins)

    for position in range(bins):
        selected = index == position
        counts[position] = float(selected.sum())
        if counts[position] == 0:
            continue

        in_corner = selected & cornering
        lateral_support[position] = float(in_corner.sum())
        if in_corner.sum() >= MIN_DEMAND_SAMPLES:
            lateral_limit[position] = float(np.quantile(lateral[in_corner], quantile))

        on_brakes = selected & braking
        braking_support[position] = float(on_brakes.sum())
        if on_brakes.sum() >= MIN_DEMAND_SAMPLES:
            braking_limit[position] = float(np.quantile(-longitudinal[on_brakes], quantile))

        on_power = selected & driving
        if on_power.sum() >= MIN_DEMAND_SAMPLES:
            traction_limit[position] = float(np.quantile(longitudinal[on_power], quantile))

    return VehicleEnvelope(
        speed_mps=speed_mps,
        lateral=_aero_fit(speed_mps, lateral_limit, lateral_support),
        braking=_aero_fit(speed_mps, braking_limit, braking_support),
        # Tracao nao ganha forma parametrica: ela cai com a velocidade, e o que
        # descreve essa queda e a curva de potencia contra o arrasto.
        traction=_fill_gaps(traction_limit, counts),
        top_speed_mps=top,
        samples=counts,
        source_laps=source_laps,
    )


def envelope_path(root: Optional[Path] = None) -> Path:
    return (Path(root) if root else config.artifacts_root()) / "vehicle_envelope.json"


def save_envelope(envelope: VehicleEnvelope, root: Optional[Path] = None) -> Path:
    path = envelope_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(envelope.to_dict(), indent=2), encoding="utf-8")
    return path


def load_envelope(root: Optional[Path] = None) -> VehicleEnvelope:
    path = envelope_path(root)
    if not path.exists():
        raise FileNotFoundError(
            f"envelope nao encontrado em {path}. Rode `python -m ml.scripts.fit_envelope`."
        )
    return VehicleEnvelope.from_dict(json.loads(path.read_text(encoding="utf-8")))
