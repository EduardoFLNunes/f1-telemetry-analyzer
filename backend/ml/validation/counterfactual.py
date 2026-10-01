"""A diferenca de tempo entre duas trajetorias e previsivel?

A camada de autocorrecao vai dizer "mude a linha aqui e voce ganha X s". Esse X
sai de comparar duas trajetorias no simulador -- e o erro do tempo *absoluto*
do simulador (1,36 s por volta) nao diz nada sobre o erro da *diferenca*: um
vies constante cancela, e um erro que depende da forma da linha nao.

Nao existe a volta corrigida dirigida de verdade. Existem pares de voltas reais
do mesmo piloto, na mesma sessao, que passaram por linhas diferentes -- e para
elas a diferenca de tempo e medida. Este modulo pega cada par (A = a mais
lenta, a volta "observada"; B = a mais rapida, a "alternativa"), preve
`t_B - t_A` usando so o que um estimador saberia na hora de recomendar (a linha
de B, e a linha *e* a pilotagem de A), e compara com o cronometro.

Estimadores, todos sobre o simulador existente (`lap_time_model`):

* `zero`         -- preve ganho zero. A referencia que qualquer outro tem de bater.
* `physics`      -- `T_sim(B) - T_sim(A)`: a diferenca crua no simulador.
* `physics_cal`  -- a mesma, vezes uma inclinacao `k` ajustada nas sessoes de treino.
* `efficiency`   -- a linha de B percorrida com a eficiencia de A:
  `eta_A(s) = v_obs_A(s) / v_sim_A(s)`, suavizada numa janela `w` ajustada nas
  sessoes de treino; `t = sum(len / (eta_A * v_sim))` nas duas linhas.
* `surrogate`    -- a LSTM substituta existente, so nas sessoes que ela nunca viu.

Validacao: deixa uma sessao de fora por vez. O envelope do carro, `k` e `w` sao
ajustados so com as outras sessoes; a sessao de fora so fornece os pares de
teste. Nada aqui treina rede.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from ..models.sequences import step_time
from ..optimization.lap_time_model import prepare, solve_speed, step_times
from ..optimization.vehicle_model import VehicleEnvelope, fit_envelope
from ..track.geometry import TrackGeometry
from ..track.microsectors import Microsectors

# ------------------------------------------------------------- comparabilidade ---
#
# Fixados antes de olhar qualquer erro de previsao. Saem de grandezas fisicas e
# do consumo medido, nao do resultado.

# Combustivel: ~0,03 s por kg em carros deste tipo; 5 L ~ 3,7 kg ~ 0,1 s de volta.
MAX_FUEL_DIFF_L = 5.0
# Desgaste de pneu, em pontos percentuais do `tyreWear` do jogo.
MAX_TYRE_WEAR_DIFF = 1.0
# Microsetor so e comparavel se os dois carros entram nele na mesma velocidade:
# senao a diferenca vem de antes, nao da linha dentro dele.
MAX_ENTRY_SPEED_DIFF_KMH = 3.0
# Microsetor com incidente (rodada, tirada de pe longa, saida de pista): a
# velocidade observada cai abaixo desta fracao do que o carro faria na linha.
MIN_EFFICIENCY = 0.6

# Faixas de ritmo, pelo tempo da volta mais lenta do par.
PACE_BANDS: Tuple[Tuple[str, float, float], ...] = (
    ("< 86 s", 0.0, 86.0),
    ("86-88 s", 86.0, 88.0),
    (">= 88 s", 88.0, float("inf")),
)

# Quanto as linhas diferem dentro do microsetor (media de |L_B - L_A|).
LINE_BINS: Tuple[Tuple[str, float, float], ...] = (
    ("< 0,5 m", 0.0, 0.5),
    ("0,5-1,5 m", 0.5, 1.5),
    (">= 1,5 m", 1.5, float("inf")),
)

# Janelas de suavizacao da eficiencia, em pontos da grade (2 m). 0 = ponto a
# ponto; None = uma eficiencia so para a volta inteira.
EFFICIENCY_WINDOWS: Tuple[Optional[int], ...] = (0, 5, 18, 36, 100, None)


# ------------------------------------------------------------ dados da volta ---

@dataclass
class LapProfile:
    """O que o estimador precisa de uma volta, na grade da pista."""

    lap_id: str
    session_id: str
    lap_time_s: float
    lateral: np.ndarray            # (N,)
    observed_step_s: np.ndarray    # (N,) tempo real por passo
    speed_kmh: np.ndarray          # (N,) velocidade observada
    brake: np.ndarray
    throttle: np.ndarray
    fuel: float
    tyre_wear: float
    off_track: float               # fracao de pontos fora de pista
    sector_time_s: np.ndarray      # (setores,) tempo real
    # Preenchidos por `simulate_profiles`:
    step_length_m: Optional[np.ndarray] = None
    sim_speed_mps: Optional[np.ndarray] = None

    @property
    def efficiency(self) -> np.ndarray:
        """v_obs / v_sim ponto a ponto, com v_obs = passo / tempo do passo."""
        observed = self.step_length_m / self.observed_step_s
        return observed / self.sim_speed_mps


def lap_profiles(store, track: TrackGeometry, sectors: Microsectors) -> Dict[str, LapProfile]:
    """Uma `LapProfile` por volta do store."""
    out: Dict[str, LapProfile] = {}
    for _, row in store.laps.iterrows():
        lap_id = str(row["lap_id"])
        frame = store.lap(lap_id)
        observed = step_time(frame)
        # Um passo sem tempo (NaN) vira o passo mediano, para a soma por
        # microsetor nao perder o trecho inteiro; e raro depois dos gates.
        observed = np.where(np.isfinite(observed), observed, np.nanmedian(observed))
        sector_time = np.bincount(sectors.index, weights=observed, minlength=sectors.count)
        out[lap_id] = LapProfile(
            lap_id=lap_id,
            session_id=str(row["session_id"]),
            lap_time_s=float(row["lap_time_s"]),
            lateral=frame["lateral"].to_numpy(dtype=float),
            observed_step_s=observed,
            speed_kmh=frame["speed_kmh"].to_numpy(dtype=float),
            brake=np.nan_to_num(frame["brake"].to_numpy(dtype=float)),
            throttle=np.nan_to_num(frame["throttle"].to_numpy(dtype=float)),
            fuel=float(np.nanmean(frame["fuel"])) if "fuel" in frame else float("nan"),
            tyre_wear=float(np.nanmean(frame["tyre_wear"])) if "tyre_wear" in frame else float("nan"),
            off_track=float(np.nanmean(frame["off_track"].astype(float))) if "off_track" in frame else 0.0,
            sector_time_s=sector_time,
        )
    return out


def simulate_profiles(
    track: TrackGeometry, envelope: VehicleEnvelope, profiles: Sequence[LapProfile]
) -> None:
    """Roda o simulador existente sobre a linha de cada volta, em lote."""
    if not profiles:
        return
    laterals = np.vstack([p.lateral for p in profiles])
    curvature, lengths = prepare(track, laterals)
    speed = solve_speed(curvature, lengths, envelope)
    for index, profile in enumerate(profiles):
        profile.step_length_m = lengths[index]
        profile.sim_speed_mps = speed[index]


def envelope_from(store, lap_ids: Sequence[str]) -> VehicleEnvelope:
    """Envelope ajustado so nas voltas dadas -- as das sessoes de treino."""
    frame = store.frame[store.frame["lap_id"].isin(list(lap_ids))]
    return fit_envelope(frame, source_laps=len(set(lap_ids)))


# ----------------------------------------------------------------- pares ---

@dataclass
class PairSet:
    """Pares de voltas e, por par e microsetor, o observado e o comparavel."""

    slow: List[str]                    # A, a volta "observada"
    fast: List[str]                    # B, a "alternativa"
    session: List[str]
    lap_reason: List[str]              # "" quando o par e comparavel
    observed: np.ndarray               # (pares, setores) t_B - t_A real
    sector_reason: np.ndarray          # (pares, setores) "" quando comparavel
    line_diff_m: np.ndarray            # (pares, setores) media |L_B - L_A|
    pace_s: np.ndarray                 # (pares,) tempo da volta mais lenta

    def __len__(self) -> int:
        return len(self.slow)


def _smooth_circular(values: np.ndarray, window: Optional[int]) -> np.ndarray:
    if window is None:
        return np.full_like(values, float(np.nanmean(values)))
    if window <= 1:
        return values
    kernel = np.ones(int(window)) / float(window)
    pad = int(window)
    extended = np.concatenate([values[-pad:], values, values[:pad]])
    return np.convolve(extended, kernel, mode="same")[pad:-pad]


def lap_compatibility(a: LapProfile, b: LapProfile) -> str:
    """Motivo pelo qual o par nao e comparavel como volta, ou ""."""
    if a.session_id != b.session_id:
        return "sessoes diferentes"
    if a.off_track > 0 or b.off_track > 0:
        return "volta com amostra fora de pista"
    if np.isfinite(a.fuel) and np.isfinite(b.fuel) and abs(a.fuel - b.fuel) > MAX_FUEL_DIFF_L:
        return f"combustivel difere mais de {MAX_FUEL_DIFF_L:.0f} L"
    if (
        np.isfinite(a.tyre_wear)
        and np.isfinite(b.tyre_wear)
        and abs(a.tyre_wear - b.tyre_wear) > MAX_TYRE_WEAR_DIFF
    ):
        return f"desgaste de pneu difere mais de {MAX_TYRE_WEAR_DIFF:.0f} p.p."
    return ""


def build_pairs(profiles: Dict[str, LapProfile], sectors: Microsectors) -> PairSet:
    """Todos os pares dentro de cada sessao; A e sempre a volta mais lenta.

    Pares entre sessoes nao sao formados (setup, pista e pneu mudam); a
    quantidade deles entra no relatorio como exclusao.
    """
    by_session: Dict[str, List[LapProfile]] = {}
    for profile in profiles.values():
        by_session.setdefault(profile.session_id, []).append(profile)

    entry_index = np.array([int(np.argmax(sectors.index == k)) for k in range(sectors.count)])

    slow, fast, session, lap_reason = [], [], [], []
    observed, sector_reason, line_diff, pace = [], [], [], []
    for session_id, laps in sorted(by_session.items()):
        laps = sorted(laps, key=lambda p: p.lap_time_s)
        for j in range(len(laps)):
            for i in range(j):
                b, a = laps[i], laps[j]                    # b mais rapida, a mais lenta
                slow.append(a.lap_id)
                fast.append(b.lap_id)
                session.append(session_id)
                reason = lap_compatibility(a, b)
                lap_reason.append(reason)
                observed.append(b.sector_time_s - a.sector_time_s)
                pace.append(a.lap_time_s)

                per_sector = np.full(sectors.count, "", dtype=object)
                if reason:
                    per_sector[:] = reason
                else:
                    entry_gap = np.abs(b.speed_kmh[entry_index] - a.speed_kmh[entry_index])
                    per_sector[entry_gap > MAX_ENTRY_SPEED_DIFF_KMH] = (
                        f"velocidade de entrada difere mais de {MAX_ENTRY_SPEED_DIFF_KMH:.0f} km/h"
                    )
                    for lap in (a, b):
                        low = np.zeros(sectors.count, dtype=bool)
                        np.logical_or.at(low, sectors.index, lap.efficiency < MIN_EFFICIENCY)
                        per_sector[(per_sector == "") & low] = "incidente (eficiencia < 0,6)"
                sector_reason.append(per_sector)
                line_diff.append(
                    np.bincount(sectors.index, weights=np.abs(b.lateral - a.lateral), minlength=sectors.count)
                    / np.bincount(sectors.index, minlength=sectors.count)
                )

    count = len(slow)
    empty = (0, sectors.count)
    return PairSet(
        slow=slow,
        fast=fast,
        session=session,
        lap_reason=lap_reason,
        observed=np.vstack(observed) if count else np.zeros(empty),
        sector_reason=np.vstack(sector_reason) if count else np.zeros(empty, dtype=object),
        line_diff_m=np.vstack(line_diff) if count else np.zeros(empty),
        pace_s=np.asarray(pace, dtype=float),
    )


# ----------------------------------------------------------- estimadores ---

def _sector_sum(values: np.ndarray, sectors: Microsectors) -> np.ndarray:
    return np.bincount(sectors.index, weights=values, minlength=sectors.count)


def modelled_sector_time(
    line: LapProfile, execution: LapProfile, window: Optional[int], sectors: Microsectors
) -> np.ndarray:
    """Tempo por microsetor da linha de `line` com a eficiencia de `execution`.

    Com `window = 0` e `line is execution` isto reproduz o tempo observado
    exatamente -- e a definicao de eficiencia.
    """
    eta = _smooth_circular(execution.efficiency, window)
    eta = np.clip(eta, 1e-3, None)
    return _sector_sum(line.step_length_m / (eta * line.sim_speed_mps), sectors)


def predict(
    pairs: PairSet,
    profiles: Dict[str, LapProfile],
    sectors: Microsectors,
    window: Optional[int],
    slope: float,
    surrogate_sector: Optional[Dict[str, np.ndarray]] = None,
) -> Dict[str, np.ndarray]:
    """Previsao de `t_B - t_A` por par e microsetor, para cada estimador."""
    count = len(pairs)
    out = {
        "zero": np.zeros((count, sectors.count)),
        "physics": np.zeros((count, sectors.count)),
        "efficiency": np.zeros((count, sectors.count)),
    }
    sim_sector: Dict[str, np.ndarray] = {}
    for lap_id in set(pairs.slow) | set(pairs.fast):
        lap = profiles[lap_id]
        sim_sector[lap_id] = _sector_sum(
            step_times(lap.sim_speed_mps[None, :], lap.step_length_m[None, :])[0], sectors
        )
    own: Dict[str, np.ndarray] = {}
    for index, (a_id, b_id) in enumerate(zip(pairs.slow, pairs.fast)):
        a, b = profiles[a_id], profiles[b_id]
        out["physics"][index] = sim_sector[b_id] - sim_sector[a_id]
        if a_id not in own:
            own[a_id] = modelled_sector_time(a, a, window, sectors)
        out["efficiency"][index] = modelled_sector_time(b, a, window, sectors) - own[a_id]
    out["physics_cal"] = slope * out["physics"]
    if surrogate_sector is not None:
        surrogate = np.full((count, sectors.count), np.nan)
        for index, (a_id, b_id) in enumerate(zip(pairs.slow, pairs.fast)):
            if a_id in surrogate_sector and b_id in surrogate_sector:
                surrogate[index] = surrogate_sector[b_id] - surrogate_sector[a_id]
        out["surrogate"] = surrogate
    return out


def fit_slope(predicted: np.ndarray, observed: np.ndarray) -> float:
    """Inclinacao sem intercepto por minimos quadrados."""
    usable = np.isfinite(predicted) & np.isfinite(observed)
    denominator = float(np.sum(predicted[usable] ** 2))
    return float(np.sum(predicted[usable] * observed[usable]) / denominator) if denominator > 0 else 1.0


# -------------------------------------------------------------- metricas ---

def error_metrics(predicted: np.ndarray, observed: np.ndarray) -> Dict[str, float]:
    usable = np.isfinite(predicted) & np.isfinite(observed)
    p, o = predicted[usable], observed[usable]
    if p.size == 0:
        return {"n": 0}
    error = p - o
    mae_zero = float(np.mean(np.abs(o)))
    mae = float(np.mean(np.abs(error)))
    meaningful = np.abs(o) > 0.02
    sign = (
        float(np.mean(np.sign(p[meaningful]) == np.sign(o[meaningful])))
        if meaningful.any()
        else float("nan")
    )
    spearman = (
        float(pd.Series(p).corr(pd.Series(o), method="spearman"))
        if p.size > 2 and np.std(p) > 0
        else float("nan")
    )
    return {
        "n": int(p.size),
        "mae_s": mae,
        "bias_s": float(np.mean(error)),
        "std_error_s": float(np.std(error)),
        "rmse_s": float(np.sqrt(np.mean(error**2))),
        "median_ae_s": float(np.median(np.abs(error))),
        "p95_ae_s": float(np.percentile(np.abs(error), 95)),
        "mae_zero_s": mae_zero,
        "skill": float(1.0 - mae / mae_zero) if mae_zero > 0 else float("nan"),
        "spearman": spearman,
        "sign_agreement": sign,
    }


def cluster_bootstrap_skill(
    predicted: np.ndarray,
    observed: np.ndarray,
    clusters: np.ndarray,
    repetitions: int = 2000,
    seed: int = 20260930,
) -> Tuple[float, float]:
    """IC 95 % da perícia, reamostrando sessoes inteiras.

    Os pares nao sao independentes -- cada volta entra em dezenas deles, e as
    voltas de uma sessao se parecem. A sessao e a unidade independente.
    """
    usable = np.isfinite(predicted) & np.isfinite(observed)
    predicted, observed, clusters = predicted[usable], observed[usable], clusters[usable]
    names = np.unique(clusters)
    if names.size < 2:
        return float("nan"), float("nan")
    groups = {name: np.flatnonzero(clusters == name) for name in names}
    generator = np.random.default_rng(seed)
    values = []
    for _ in range(repetitions):
        chosen = generator.choice(names, size=names.size, replace=True)
        index = np.concatenate([groups[name] for name in chosen])
        mae = np.mean(np.abs(predicted[index] - observed[index]))
        mae_zero = np.mean(np.abs(observed[index]))
        if mae_zero > 0:
            values.append(1.0 - mae / mae_zero)
    low, high = np.percentile(values, [2.5, 97.5])
    return float(low), float(high)


# ------------------------------------------------------- decomposicao ---

def decompose(
    pairs: PairSet, profiles: Dict[str, LapProfile], sectors: Microsectors
) -> Dict[str, np.ndarray]:
    """Linha x execucao x interacao, por par e microsetor.

    Modelo: `t = sum(len(L) / (eta * v_sim(L)))`, com `eta` ponto a ponto. Com
    ele, as quatro combinacoes (linha de A ou B) x (eficiencia de A ou B) tem
    tempo calculavel, e as duas "puras" reproduzem o cronometro:

        linha     = t(L_B, eta_A) - t(L_A, eta_A)
        execucao  = t(L_A, eta_B) - t(L_A, eta_A)
        interacao = total - linha - execucao

    Se a interacao for pequena, somar linha e execucao e legitimo **neste
    modelo**. O modelo em si -- execucao como um fator que multiplica a
    velocidade que a linha permite -- e uma hipotese, nao uma medida.
    """
    count = len(pairs)
    shape = (count, sectors.count)
    out = {name: np.zeros(shape) for name in ("total", "line", "execution", "interaction")}
    for index, (a_id, b_id) in enumerate(zip(pairs.slow, pairs.fast)):
        a, b = profiles[a_id], profiles[b_id]
        aa = modelled_sector_time(a, a, 0, sectors)
        bb = modelled_sector_time(b, b, 0, sectors)
        ba = modelled_sector_time(b, a, 0, sectors)   # linha de B, execucao de A
        ab = modelled_sector_time(a, b, 0, sectors)   # linha de A, execucao de B
        out["total"][index] = bb - aa
        out["line"][index] = ba - aa
        out["execution"][index] = ab - aa
        out["interaction"][index] = out["total"][index] - out["line"][index] - out["execution"][index]
    return out


# ------------------------------------------------------- criterios ---

@dataclass(frozen=True)
class AcceptanceCriteria:
    """O que o estimador precisa mostrar para sustentar recomendacoes.

    Fixados antes da primeira execucao. Avaliados nos microsetores comparaveis
    em que as linhas diferem pelo menos 0,5 m -- e onde uma recomendacao de
    linha existiria --, com as previsoes de teste de todas as dobras juntas.
    """

    min_skill: float = 0.20                 # erro pelo menos 20 % menor que prever zero
    min_skill_ci_low: float = 0.0           # e o IC 95 % por sessao acima de zero
    max_abs_bias_fraction: float = 0.25     # |vies| ate 25 % do erro de prever zero
    min_spearman: float = 0.30
    min_sign_agreement: float = 0.65
    min_session_share_positive: float = 0.70  # pericia > 0 em 70 % das sessoes testaveis
    min_sessions: int = 5

    def to_dict(self) -> Dict[str, float]:
        return dict(self.__dict__)

    def evaluate(self, pooled: Dict[str, float], ci_low: float, per_session: Dict[str, Dict[str, float]]) -> Dict[str, object]:
        skills = [m.get("skill") for m in per_session.values() if m.get("n", 0) > 0]
        positive = float(np.mean([s > 0 for s in skills])) if skills else float("nan")
        checks = {
            "pericia": (pooled.get("skill", float("nan")), pooled.get("skill", -1) >= self.min_skill),
            "ic95_pericia_inferior": (ci_low, np.isfinite(ci_low) and ci_low > self.min_skill_ci_low),
            "vies_relativo": (
                abs(pooled.get("bias_s", np.nan)) / max(pooled.get("mae_zero_s", np.nan), 1e-9),
                abs(pooled.get("bias_s", np.inf)) <= self.max_abs_bias_fraction * pooled.get("mae_zero_s", 0.0),
            ),
            "spearman": (pooled.get("spearman", float("nan")), pooled.get("spearman", -1) >= self.min_spearman),
            "concordancia_de_sinal": (
                pooled.get("sign_agreement", float("nan")),
                pooled.get("sign_agreement", -1) >= self.min_sign_agreement,
            ),
            "sessoes_com_pericia_positiva": (positive, positive >= self.min_session_share_positive),
            "sessoes_testaveis": (len(skills), len(skills) >= self.min_sessions),
        }
        return {
            "checks": {k: {"valor": v, "passou": bool(ok)} for k, (v, ok) in checks.items()},
            "aprovado": bool(all(ok for _, ok in checks.values())),
        }
