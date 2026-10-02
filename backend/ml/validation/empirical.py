"""Estimador empirico de ganho numa janela de curva (Fase 2b, ADRs 0005 e 0010).

A Fase 2 mostrou que o simulador nao preve a diferenca de tempo entre duas
linhas proximas melhor que "ganho zero" (ADR 0004). Aqui a pergunta e outra:
usando so as voltas do proprio piloto, as diferencas de pilotagem que um coach
poderia pedir -- onde frear, por onde passar, quando acelerar -- explicam a
diferenca de tempo numa janela de curva?

Janela de curva
---------------
Do inicio de uma zona de frenagem ate o inicio da proxima: a curva **e** a reta
que vem depois dela, porque frear tarde parece ganhar na entrada e perde na
saida e na reta (ADR 0005). As janelas cobrem a volta inteira, entao a soma dos
tempos delas e o tempo da volta.

As zonas de frenagem saem das voltas de treino, nao da geometria: um limiar de
curvatura acha 14 curvas, mas o piloto freia em 7 lugares (curvas encadeadas
como o S do Senna compartilham uma frenagem). Uma zona e um aglomerado de
inicios de frenagem ao longo da pista feito por pelo menos metade das voltas.

Estimadores
-----------
E0 zero; E1 simulador calibrado por janela; E2 ridge; E3 KNN de regressao;
E4 Processo Gaussiano; E2-teto = E2 com velocidades minima e de saida (quase
tautologico, so como teto). E2, E3 e E4 sao ajustados por janela -- o efeito de
frear 5 m mais tarde nao e o mesmo na Juncao e no S do Senna.

Os pares de treino entram nas duas ordens, (A, B) e (B, A), com entradas e alvo
de sinal trocado. A relacao e antissimetrica por natureza (trocar as voltas
troca o sinal do ganho), e sem isso o modelo aprenderia a ordenacao dos pares
-- A e sempre a volta mais lenta -- em vez da pilotagem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..comparison.lap_vs_reference import (
    BRAKE_ONSET,
    THROTTLE_ONSET,
    _first_crossing,
    _signed_distance,
    _window,
)
from ..track.corners import Corner
from ..track.geometry import TrackGeometry
from . import counterfactual as cf

# ------------------------------------------------------------ janelas ---
#
# Fixados antes de rodar qualquer estimador, a partir da distribuicao dos
# inicios de frenagem (nenhum tempo olhado).

# Um inicio de frenagem conta quando o pedal fica abaixo do limiar por pelo
# menos 20 m antes e acima por pelo menos 10 m depois: um toque de 2 m no freio
# nao e frenagem.
ONSET_OFF_BEFORE_M = 20.0
ONSET_ON_AFTER_M = 10.0
# Inicios a menos de 30 m entre si pertencem ao mesmo aglomerado.
CLUSTER_GAP_M = 30.0
# Uma zona de frenagem existe quando pelo menos metade das voltas freia ali.
MIN_LAP_SHARE = 0.5
# Dois aglomerados a menos de 150 m (pela mediana) sao a mesma curva: o segundo
# toque no S do Senna e na Ferradura nao tem reta entre eles. A menor reta entre
# zonas distintas de Interlagos medida nas voltas e de 158 m.
MERGE_ZONES_M = 150.0
# A janela comeca um pouco antes do inicio de frenagem mais precoce (p5), para
# a frenagem de quase toda volta cair dentro dela.
START_MARGIN_M = 10.0
START_QUANTILE = 5.0
ROUND_TO_M = 10.0

# ------------------------------------------------------------ entradas ---

ACTIONABLE = (
    "braking_point_m",     # B freou x m depois de A (positivo = mais tarde)
    "lateral_entry_m",     # posicao lateral no inicio da curva, B - A
    "lateral_apex_m",
    "lateral_exit_m",
    "throttle_point_m",    # B acelerou x m depois de A
)
CEILING_EXTRA = ("min_speed_kmh", "exit_speed_kmh")

# Abstencao por entrada fora da distribuicao de treino (ADR 0010).
OOD_LOW, OOD_HIGH = 2.5, 97.5
INTERVAL_LEVEL = 0.95


@dataclass
class Windows:
    """Janelas de curva na grade da pista. Compativel com o que `counterfactual`
    espera de um corte em setores (`index`, `count`)."""

    start_s: np.ndarray            # (n,) inicio de cada janela
    end_s: np.ndarray              # (n,) fim = inicio da seguinte
    corner: List[Corner]           # a curva que define entrada/apice/saida
    index: np.ndarray              # (grade,) janela de cada ponto
    entry_index: np.ndarray        # (n,) ponto da grade onde a janela comeca
    zone_median_s: np.ndarray      # (n,) mediana dos inicios de frenagem da zona
    track_length: float

    @property
    def count(self) -> int:
        return int(self.start_s.size)

    @property
    def lengths_m(self) -> np.ndarray:
        return np.mod(self.end_s - self.start_s, self.track_length)

    def labels(self) -> List[str]:
        return [f"J{k + 1}:{c.label}" for k, c in enumerate(self.corner)]

    def describe(self) -> List[Dict[str, object]]:
        return [
            {
                "janela": label,
                "inicio_m": float(s),
                "fim_m": float(e),
                "comprimento_m": float(length),
                "curva": c.label,
                "apice_m": float(c.apex_s),
                "mediana_inicio_frenagem_m": float(z),
            }
            for label, s, e, length, c, z in zip(
                self.labels(), self.start_s, self.end_s, self.lengths_m, self.corner, self.zone_median_s
            )
        ]


def brake_onsets(brake: np.ndarray, track: TrackGeometry) -> np.ndarray:
    """Distancias em que a frenagem comeca de verdade, numa volta na grade."""
    on = np.asarray(brake, dtype=float) >= BRAKE_ONSET
    before = int(round(ONSET_OFF_BEFORE_M / track.step))
    after = int(round(ONSET_ON_AFTER_M / track.step))
    out = []
    for i in np.flatnonzero(on & ~np.roll(on, 1)):
        previous = on[(i - before + np.arange(before)) % on.size]
        following = on[(i + np.arange(after)) % on.size]
        if not previous.any() and following.all():
            out.append(float(track.s[i]))
    return np.asarray(out)


def define_windows(
    brakes: Sequence[np.ndarray], track: TrackGeometry, corners: Sequence[Corner]
) -> Windows:
    """Zonas de frenagem a partir das voltas dadas (so as de treino, na validacao)."""
    laps = len(brakes)
    onsets = np.sort(np.concatenate([brake_onsets(b, track) for b in brakes]))
    if onsets.size == 0:
        raise ValueError("nenhum inicio de frenagem nas voltas dadas")

    clusters: List[np.ndarray] = []
    current = [onsets[0]]
    for value in onsets[1:]:
        if value - current[-1] > CLUSTER_GAP_M:
            clusters.append(np.asarray(current))
            current = []
        current.append(value)
    clusters.append(np.asarray(current))
    # O aglomerado que cruza a linha de chegada aparece partido nas duas pontas.
    if len(clusters) > 1 and clusters[0][0] + track.length - clusters[-1][-1] <= CLUSTER_GAP_M:
        clusters[0] = np.concatenate([clusters[-1] - track.length, clusters[0]])
        clusters.pop()

    zones = [c for c in clusters if c.size >= MIN_LAP_SHARE * laps]
    if not zones:
        raise ValueError("nenhuma zona de frenagem feita por metade das voltas")
    merged = [zones[0]]
    for zone in zones[1:]:
        if np.median(zone) - np.median(merged[-1]) < MERGE_ZONES_M:
            merged[-1] = np.concatenate([merged[-1], zone])
        else:
            merged.append(zone)
    if len(merged) > 1 and np.median(merged[0]) + track.length - np.median(merged[-1]) < MERGE_ZONES_M:
        merged[-1] = np.concatenate([merged[-1], merged[0] + track.length])
        merged.pop(0)

    starts, medians, chosen = [], [], []
    apexes = np.array([c.apex_s for c in corners])
    for zone in merged:
        start = np.floor((np.percentile(zone, START_QUANTILE) - START_MARGIN_M) / ROUND_TO_M) * ROUND_TO_M
        median = float(np.median(zone))
        ahead = np.mod(apexes - median, track.length)
        starts.append(float(np.mod(start, track.length)))
        medians.append(float(np.mod(median, track.length)))
        chosen.append(corners[int(np.argmin(ahead))])
    order = np.argsort(starts)
    starts = np.asarray(starts)[order]
    medians = np.asarray(medians)[order]
    chosen = [chosen[i] for i in order]
    ends = np.roll(starts, -1)

    index = np.empty(track.size, dtype=int)
    entry = np.empty(starts.size, dtype=int)
    for k, (start, end) in enumerate(zip(starts, ends)):
        points = _window(track, start, end)[:-1]
        index[points] = k
        entry[k] = points[0]
    return Windows(starts, ends, chosen, index, entry, medians, track.length)


# ---------------------------------------------------- entradas por volta ---

def lap_window_features(
    frame, windows: Windows, track: TrackGeometry
) -> List[Dict[str, Optional[float]]]:
    """Por janela: ponto de frenagem, lateral na entrada/apice/saida, retomada."""
    brake = frame["brake"].to_numpy(dtype=float)
    throttle = frame["throttle"].to_numpy(dtype=float)
    lateral = frame["lateral"].to_numpy(dtype=float)
    speed = frame["speed_kmh"].to_numpy(dtype=float)
    out = []
    for k in range(windows.count):
        corner = windows.corner[k]
        approach = _window(track, windows.start_s[k], corner.apex_s)
        after_apex = _window(track, corner.apex_s, windows.end_s[k])
        inside = _window(track, corner.start_s, corner.end_s)
        out.append(
            {
                "braking_point_s": _first_crossing(np.nan_to_num(brake), BRAKE_ONSET, approach, track),
                "throttle_point_s": _first_crossing(np.nan_to_num(throttle), THROTTLE_ONSET, after_apex, track),
                "lateral_entry_m": float(lateral[track.index_of(corner.start_s)]),
                "lateral_apex_m": float(lateral[track.index_of(corner.apex_s)]),
                "lateral_exit_m": float(lateral[track.index_of(corner.end_s)]),
                "min_speed_kmh": float(np.nanmin(speed[inside])),
                "exit_speed_kmh": float(speed[track.index_of(corner.end_s)]),
            }
        )
    return out


def pair_features(
    a: Dict[str, Optional[float]], b: Dict[str, Optional[float]], track: TrackGeometry
) -> Optional[Dict[str, float]]:
    """Diferencas B - A. None quando a frenagem ou a retomada nao foi achada."""
    if None in (a["braking_point_s"], b["braking_point_s"], a["throttle_point_s"], b["throttle_point_s"]):
        return None
    return {
        "braking_point_m": _signed_distance(track, b["braking_point_s"], a["braking_point_s"]),
        "throttle_point_m": _signed_distance(track, b["throttle_point_s"], a["throttle_point_s"]),
        "lateral_entry_m": b["lateral_entry_m"] - a["lateral_entry_m"],
        "lateral_apex_m": b["lateral_apex_m"] - a["lateral_apex_m"],
        "lateral_exit_m": b["lateral_exit_m"] - a["lateral_exit_m"],
        "min_speed_kmh": b["min_speed_kmh"] - a["min_speed_kmh"],
        "exit_speed_kmh": b["exit_speed_kmh"] - a["exit_speed_kmh"],
    }


# ---------------------------------------------------------- pares ---

@dataclass
class PairWindows:
    """Uma linha por (par, janela)."""

    session: List[str] = field(default_factory=list)
    slow: List[str] = field(default_factory=list)
    fast: List[str] = field(default_factory=list)
    window: List[int] = field(default_factory=list)
    pace_s: List[float] = field(default_factory=list)
    reason: List[str] = field(default_factory=list)       # "" = comparavel
    observed_s: List[float] = field(default_factory=list)  # t_B - t_A na janela
    physics_s: List[float] = field(default_factory=list)   # T_sim(B) - T_sim(A)
    features: List[Optional[Dict[str, float]]] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.session)


def window_sum(values: np.ndarray, windows: Windows) -> np.ndarray:
    return np.bincount(windows.index, weights=values, minlength=windows.count)


def build_pair_windows(
    profiles: Dict[str, "cf.LapProfile"],
    windows: Windows,
    lap_features: Dict[str, List[Dict[str, Optional[float]]]],
    track: TrackGeometry,
) -> PairWindows:
    """Pares dentro da sessao (A = mais lenta), com os filtros da Fase 2.

    Exige `profiles` ja simulados (`cf.simulate_profiles`): o filtro de
    incidente e o E1 dependem da velocidade simulada.
    """
    from ..optimization.lap_time_model import step_times

    sim_window: Dict[str, np.ndarray] = {}
    low: Dict[str, np.ndarray] = {}
    for lap_id, p in profiles.items():
        sim_window[lap_id] = window_sum(
            step_times(p.sim_speed_mps[None, :], p.step_length_m[None, :])[0], windows
        )
        flag = np.zeros(windows.count, dtype=bool)
        np.logical_or.at(flag, windows.index, p.efficiency < cf.MIN_EFFICIENCY)
        low[lap_id] = flag

    by_session: Dict[str, List] = {}
    for p in profiles.values():
        by_session.setdefault(p.session_id, []).append(p)

    out = PairWindows()
    for session_id, laps in sorted(by_session.items()):
        laps = sorted(laps, key=lambda p: p.lap_time_s)
        for j in range(len(laps)):
            for i in range(j):
                b, a = laps[i], laps[j]
                lap_reason = cf.lap_compatibility(a, b)
                observed = window_sum(b.observed_step_s, windows) - window_sum(a.observed_step_s, windows)
                physics = sim_window[b.lap_id] - sim_window[a.lap_id]
                for k in range(windows.count):
                    entry = windows.entry_index[k]
                    features = pair_features(lap_features[a.lap_id][k], lap_features[b.lap_id][k], track)
                    if lap_reason:
                        reason = lap_reason
                    elif abs(b.speed_kmh[entry] - a.speed_kmh[entry]) > cf.MAX_ENTRY_SPEED_DIFF_KMH:
                        reason = f"velocidade de entrada difere mais de {cf.MAX_ENTRY_SPEED_DIFF_KMH:.0f} km/h"
                    elif low[a.lap_id][k] or low[b.lap_id][k]:
                        reason = "incidente (eficiencia < 0,6)"
                    elif features is None:
                        reason = "frenagem ou retomada nao detectada"
                    else:
                        reason = ""
                    out.session.append(session_id)
                    out.slow.append(a.lap_id)
                    out.fast.append(b.lap_id)
                    out.window.append(k)
                    out.pace_s.append(a.lap_time_s)
                    out.reason.append(reason)
                    out.observed_s.append(float(observed[k]))
                    out.physics_s.append(float(physics[k]))
                    out.features.append(features)
    return out


def design(pairs: PairWindows, rows: np.ndarray, columns: Sequence[str]) -> np.ndarray:
    return np.array([[pairs.features[r][c] for c in columns] for r in rows], dtype=float)


def symmetrize(x: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """(A, B) e (B, A): entradas e alvo com o sinal trocado."""
    return np.vstack([x, -x]), np.concatenate([y, -y])


def ood_mask(train_x: np.ndarray, test_x: np.ndarray) -> np.ndarray:
    """True onde alguma entrada cai fora da faixa 2,5-97,5 % do treino."""
    if train_x.shape[0] == 0:
        return np.ones(test_x.shape[0], dtype=bool)
    low = np.percentile(train_x, OOD_LOW, axis=0)
    high = np.percentile(train_x, OOD_HIGH, axis=0)
    return np.any((test_x < low) | (test_x > high), axis=1)


# ------------------------------------------------------- estimadores ---

RIDGE_ALPHAS = (0.01, 0.1, 1.0, 10.0, 100.0, 1000.0)
KNN_KS = (3, 5, 10, 20, 40, 80)
# O GP e O(n^3): por janela e dobra, no maximo este numero de pontos de treino
# (sorteados com semente fixa) entra no ajuste.
GP_MAX_TRAIN = 600
GP_RESTARTS = 2
SEED = 20261002
MIN_WINDOW_RESIDUALS = 30


def _ridge(alpha: float):
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    # Sem intercepto: sem diferenca de pilotagem, a previsao e zero.
    return make_pipeline(StandardScaler(with_mean=False), Ridge(alpha=alpha, fit_intercept=False))


def _knn(k: int):
    from sklearn.neighbors import KNeighborsRegressor
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    return make_pipeline(StandardScaler(with_mean=False), KNeighborsRegressor(n_neighbors=k))


def _gp():
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel

    kernel = ConstantKernel(1.0, (1e-3, 1e3)) * RBF(
        length_scale=np.ones(len(ACTIONABLE)), length_scale_bounds=(1e-2, 1e3)
    ) + WhiteKernel(1.0, (1e-5, 1e2))
    return GaussianProcessRegressor(
        kernel=kernel, normalize_y=True, n_restarts_optimizer=GP_RESTARTS, random_state=SEED
    )


@dataclass
class Prediction:
    point: np.ndarray
    low: np.ndarray       # NaN quando o estimador nao tem incerteza
    high: np.ndarray


def _fit_predict_windowed(make, train, test, windows_train, windows_test, count):
    """Ajusta um modelo por janela e preve. `train`/`test` = (x, y)."""
    point = np.full(test[0].shape[0], np.nan)
    for k in range(count):
        tr = windows_train == k
        te = windows_test == k
        if not te.any() or tr.sum() < 2:
            continue
        x, y = symmetrize(train[0][tr], train[1][tr])
        model = make(int(x.shape[0]))
        model.fit(x, y)
        point[te] = model.predict(test[0][te])
    return point


def _inner_residuals(make, x, y, windows, sessions, count) -> np.ndarray:
    """Residuos fora da amostra: deixa uma sessao de treino de fora por vez."""
    residual = np.full(y.size, np.nan)
    for session in np.unique(sessions):
        held = sessions == session
        if held.all():
            continue
        predicted = _fit_predict_windowed(
            make, (x[~held], y[~held]), (x[held], y[held]), windows[~held], windows[held], count
        )
        residual[held] = y[held] - predicted
    return residual


def _quantile_interval(residual, windows, count, point, test_windows):
    """Faixa de 95 % pelos quantis dos residuos de treino, por janela."""
    alpha = (1.0 - INTERVAL_LEVEL) / 2.0
    finite = np.isfinite(residual)
    global_q = np.quantile(residual[finite], [alpha, 1.0 - alpha]) if finite.any() else (np.nan, np.nan)
    low = np.full(point.size, np.nan)
    high = np.full(point.size, np.nan)
    for k in range(count):
        te = test_windows == k
        own = residual[(windows == k) & finite]
        q = np.quantile(own, [alpha, 1.0 - alpha]) if own.size >= MIN_WINDOW_RESIDUALS else global_q
        low[te] = point[te] + q[0]
        high[te] = point[te] + q[1]
    return low, high


def choose(make_for, candidates, x, y, windows, sessions, count) -> Tuple[object, Dict[str, float]]:
    """Hiperparametro pelo menor MAE fora da amostra, so nas sessoes de treino."""
    scores = {}
    for value in candidates:
        residual = _inner_residuals(make_for(value), x, y, windows, sessions, count)
        scores[str(value)] = float(np.nanmean(np.abs(residual)))
    best = min(candidates, key=lambda v: scores[str(v)])
    return best, scores


def fit_ridge(x, y, windows, sessions, test_x, test_windows, count):
    alpha, scores = choose(lambda a: (lambda n: _ridge(a)), RIDGE_ALPHAS, x, y, windows, sessions, count)
    make = lambda n: _ridge(alpha)  # noqa: E731
    point = _fit_predict_windowed(make, (x, y), (test_x, None), windows, test_windows, count)
    residual = _inner_residuals(make, x, y, windows, sessions, count)
    low, high = _quantile_interval(residual, windows, count, point, test_windows)
    return Prediction(point, low, high), {"alpha": alpha, "inner_mae": scores}


def fit_knn(x, y, windows, sessions, test_x, test_windows, count):
    def make_for(k):
        return lambda n: _knn(max(1, min(int(k), n)))

    k, scores = choose(make_for, KNN_KS, x, y, windows, sessions, count)
    make = make_for(k)
    point = _fit_predict_windowed(make, (x, y), (test_x, None), windows, test_windows, count)
    residual = _inner_residuals(make, x, y, windows, sessions, count)
    low, high = _quantile_interval(residual, windows, count, point, test_windows)
    return Prediction(point, low, high), {"k": k, "inner_mae": scores}


def fit_gp(x, y, windows, test_x, test_windows, count):
    """Um GP por janela; hiperparametros pela verossimilhanca no treino."""
    rng = np.random.default_rng(SEED)
    z = 1.959963984540054
    point = np.full(test_x.shape[0], np.nan)
    sd = np.full(test_x.shape[0], np.nan)
    kernels = {}
    for k in range(count):
        tr = np.flatnonzero(windows == k)
        te = test_windows == k
        if not te.any() or tr.size < 2:
            continue
        if tr.size > GP_MAX_TRAIN // 2:
            tr = rng.choice(tr, GP_MAX_TRAIN // 2, replace=False)
        xs, ys = symmetrize(x[tr], y[tr])
        scale = np.std(xs, axis=0)
        scale = np.where(scale > 1e-9, scale, 1.0)
        model = _gp()
        model.fit(xs / scale, ys)
        mean, std = model.predict(test_x[te] / scale, return_std=True)
        point[te], sd[te] = mean, std
        kernels[str(k)] = str(model.kernel_)
    return Prediction(point, point - z * sd, point + z * sd), {"kernels": kernels, "max_train": GP_MAX_TRAIN}


# ------------------------------------------------------- avaliacao ---

COVERAGE_LEVELS = tuple(np.round(np.arange(0.1, 1.01, 0.1), 2))


def answered(prediction: Prediction) -> np.ndarray:
    """Responde quando a faixa de 95 % nao inclui zero."""
    return (prediction.low > 0) | (prediction.high < 0)


def risk_coverage(prediction: Prediction, observed: np.ndarray) -> List[Dict[str, float]]:
    """Erro nos casos mais confiantes, por cobertura.

    Confianca = quanto a faixa se afasta de zero, em meias-larguras: |centro| /
    meia-largura. Acima de 1 a faixa exclui zero e o estimador responde.
    """
    half = (prediction.high - prediction.low) / 2.0
    score = np.abs(prediction.point) / np.maximum(half, 1e-12)
    order = np.argsort(-score)
    out = []
    for level in COVERAGE_LEVELS:
        n = max(1, int(round(level * order.size)))
        chosen = order[:n]
        metrics = cf.error_metrics(prediction.point[chosen], observed[chosen])
        out.append(
            {
                "cobertura": float(level),
                "n": int(n),
                "limiar_confianca": float(score[order[n - 1]]),
                "mae_s": metrics.get("mae_s"),
                "mae_zero_s": metrics.get("mae_zero_s"),
                "skill": metrics.get("skill"),
            }
        )
    return out


def interval_coverage(prediction: Prediction, observed: np.ndarray) -> float:
    """Fracao dos ΔT reais dentro da faixa de 95 % (calibracao)."""
    inside = (observed >= prediction.low) & (observed <= prediction.high)
    return float(np.mean(inside)) if inside.size else float("nan")
