"""A fisica simples da M1: o modelo de bicicleta dinamico (a referencia R1; pedido 37, Parte C).

Por unidade de massa: as forcas sao divididas pela massa e ficam em m/s^2. As
rodas de cada eixo viram uma so. A forma e os parametros foram registrados
antes de construir (`docs/modelo_fisico_m1.md`, 1.4):

    alpha_f = delta - atan2(vy + a*r, vx)          alpha_r = -atan2(vy - b*r, vx)
    n_f = g*w_f + kL*f_aero*vx^2 - (h/L)*a_x       n_r = g*(1 - w_f) + kL*(1 - f_aero)*vx^2 + (h/L)*a_x
    tracao (traseira)   F_xr = s_T * T * (A_env(vx) + kD*vx^2 + c0)
    freio               F_x,i = -min(beta_B * B * bias_i, 0,99*mu*n_i)
    resistencia         R = kD*vx^2 + c0*(1 - T)
    lateral             F_y,i = F_max,i * tanh(C_alpha*n_i*alpha_i / F_max,i),  F_max,i = sqrt((mu*n_i)^2 - F_x,i^2)
    dvx/dt = F_xr + F_xf cos d - F_yf sin d - R + vy*r
    dvy/dt = F_yr + F_yf cos d + F_xf sin d - vx*r
    dr/dt  = (a*(F_yf cos d + F_xf sin d) - b*F_yr) / k2

Integrada em 5 subpassos de 10 ms por passo de 50 ms, pelo metodo de Heun,
com a entrada do passo constante.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, Optional, Sequence, Tuple

import numpy as np
from scipy.optimize import least_squares

from .dados import DT, G

SUBPASSOS = 5
VX_MIN = 5.0
EPS = 1e-6

# Os parametros ajustados por minimos quadrados: (nome, unidade, limite inferior, superior, inicio).
AJUSTADOS = (
    ("C_alpha", "1/rad", 5.0, 60.0, 20.0),
    ("mu", "-", 1.0, 2.5, 1.6),
    ("k2", "m^2", 0.5, 4.0, 1.5),
    ("kappa_D", "1/m", 0.0003, 0.003, 0.001),
    ("c0", "m/s^2", 0.0, 3.0, 1.0),
    ("s_T", "-", 0.5, 1.5, 1.0),
    ("beta_B", "m/s^2", 10.0, 60.0, 30.0),
)

# Regra da transferencia de carga (1.4): entra se reduzir o erro de um passo no treino em >= 2%.
GANHO_MIN_TRANSFERENCIA = 0.02


@dataclass
class Parametros:
    # Medidos por conta direta (`geometria`).
    m: float
    kappa_L: float
    w_f: float
    f_aero: float
    h_L: float
    b: float
    L: float
    k_delta: float
    brake_bias: float
    # O envelope de tracao da rodada (velocidade em m/s, aceleracao em m/s^2).
    env_speed: np.ndarray
    env_traction: np.ndarray
    # Ajustados.
    C_alpha: float = 20.0
    mu: float = 1.6
    k2: float = 1.5
    kappa_D: float = 0.001
    c0: float = 1.0
    s_T: float = 1.0
    beta_B: float = 30.0
    transferencia: bool = False

    @property
    def a(self) -> float:
        return self.L - self.b

    def ajustados(self) -> np.ndarray:
        return np.array([getattr(self, name) for name, *_ in AJUSTADOS], dtype=float)

    def com(self, theta: Sequence[float], **extra) -> "Parametros":
        values = {name: float(v) for (name, *_), v in zip(AJUSTADOS, theta)}
        values.update(extra)
        return replace(self, **values)

    def to_dict(self) -> Dict[str, object]:
        out = {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in self.__dict__.items()}
        out["a"] = self.a
        return out


def derivadas(state: np.ndarray, u: np.ndarray, p: Parametros) -> np.ndarray:
    """d(vx, vy, r)/dt para cada linha. `state` (n, 3) e `u` (n, 3) = (steer, T, B)."""
    vx, vy, r = state[:, 0], state[:, 1], state[:, 2]
    steer, T, B = u[:, 0], np.clip(u[:, 1], 0.0, 1.0), np.clip(u[:, 2], 0.0, 1.0)
    vxc = np.maximum(vx, VX_MIN)
    delta = -p.k_delta * steer
    alpha_f = delta - np.arctan2(vy + p.a * r, vxc)
    alpha_r = -np.arctan2(vy - p.b * r, vxc)
    v2 = vxc ** 2
    a_env = np.interp(vxc, p.env_speed, p.env_traction)
    drive = np.maximum(p.s_T * T * (a_env + p.kappa_D * v2 + p.c0), 0.0)
    resist = p.kappa_D * v2 + p.c0 * (1.0 - T)
    demand = p.beta_B * B
    cos_d, sin_d = np.cos(delta), np.sin(delta)
    n_f0 = G * p.w_f + p.kappa_L * p.f_aero * v2
    n_r0 = G * (1.0 - p.w_f) + p.kappa_L * (1.0 - p.f_aero) * v2

    def forces(n_f, n_r):
        n_f, n_r = np.maximum(n_f, 0.1), np.maximum(n_r, 0.1)
        lim_f, lim_r = 0.99 * p.mu * n_f, 0.99 * p.mu * n_r
        fxf = -np.minimum(demand * p.brake_bias, lim_f)
        fxr = np.minimum(drive, lim_r) - np.minimum(demand * (1.0 - p.brake_bias), lim_r)
        fxr = np.clip(fxr, -lim_r, lim_r)
        fmax_f = np.sqrt(np.maximum((p.mu * n_f) ** 2 - fxf ** 2, EPS))
        fmax_r = np.sqrt(np.maximum((p.mu * n_r) ** 2 - fxr ** 2, EPS))
        fyf = fmax_f * np.tanh(p.C_alpha * n_f * alpha_f / fmax_f)
        fyr = fmax_r * np.tanh(p.C_alpha * n_r * alpha_r / fmax_r)
        ax = fxr + fxf * cos_d - fyf * sin_d - resist
        return fxf, fxr, fyf, fyr, ax

    fxf, fxr, fyf, fyr, ax = forces(n_f0, n_r0)
    if p.transferencia:
        fxf, fxr, fyf, fyr, ax = forces(n_f0 - p.h_L * ax, n_r0 + p.h_L * ax)
    dvx = ax + vy * r
    dvy = fyr + fyf * cos_d + fxf * sin_d - vx * r
    dr = (p.a * (fyf * cos_d + fxf * sin_d) - p.b * fyr) / p.k2
    return np.column_stack([dvx, dvy, dr])


def passo(state: np.ndarray, u: np.ndarray, p: Parametros, dt: float = DT, subpassos: int = SUBPASSOS) -> np.ndarray:
    """O estado depois de um passo de `dt`, com a entrada constante (Heun)."""
    h = dt / subpassos
    x = np.asarray(state, dtype=float)
    for _ in range(subpassos):
        k1 = derivadas(x, u, p)
        k2 = derivadas(x + h * k1, u, p)
        x = x + 0.5 * h * (k1 + k2)
    return x


def malha_aberta(state0: np.ndarray, U: np.ndarray, p: Parametros, correcao=None,
                 com_indice: int = 0) -> Tuple[np.ndarray, Optional[np.ndarray]]:
    """Anda `U.shape[1]` passos com as entradas gravadas, sem olhar o estado gravado.

    `correcao`, se dada, soma a media do residuo previsto a cada passo (a M1).
    Devolve (estados (n, H+1, 3), indice de "fora dos dados" (n, com_indice) nos
    `com_indice` primeiros pontos do caminho, ou None).
    """
    n, steps, _ = U.shape
    out = np.empty((n, steps + 1, 3))
    out[:, 0] = state0
    index = np.empty((n, com_indice)) if (correcao is not None and com_indice) else None
    x = np.asarray(state0, dtype=float)
    for k in range(steps):
        nxt = passo(x, U[:, k], p)
        if correcao is not None:
            mean, _, idx = correcao.prever(x, U[:, k], com_desvio=(index is not None and k < com_indice))
            nxt = nxt + mean
            if index is not None and k < com_indice:
                index[:, k] = idx
        out[:, k + 1] = nxt
        x = nxt
    return out, index


def persistencia(state0: np.ndarray, steps: int) -> np.ndarray:
    """R0: o estado fica igual."""
    return np.repeat(np.asarray(state0, dtype=float)[:, None, :], steps + 1, axis=1)


def posicoes(states: np.ndarray, dt: float = DT) -> np.ndarray:
    """(X, Y) no referencial do inicio, integrando (vx, vy, r) pelos trapezios. (n, H+1, 2)."""
    vx, vy, r = states[..., 0], states[..., 1], states[..., 2]
    psi = np.concatenate([np.zeros(states.shape[:-2] + (1,)), np.cumsum(0.5 * dt * (r[..., 1:] + r[..., :-1]), axis=-1)], axis=-1)
    gx = vx * np.cos(psi) - vy * np.sin(psi)
    gy = vx * np.sin(psi) + vy * np.cos(psi)
    zero = np.zeros(states.shape[:-2] + (1,))
    X = np.concatenate([zero, np.cumsum(0.5 * dt * (gx[..., 1:] + gx[..., :-1]), axis=-1)], axis=-1)
    Y = np.concatenate([zero, np.cumsum(0.5 * dt * (gy[..., 1:] + gy[..., :-1]), axis=-1)], axis=-1)
    return np.stack([X, Y], axis=-1)


# --------------------------------------------------------------- ajuste ---

@dataclass
class Ajuste:
    params: Parametros
    erro_um_passo: float
    sem_transferencia: float
    com_transferencia: float
    no_limite: Tuple[str, ...]
    custo: float
    iteracoes: int
    detalhes: Dict[str, object] = field(default_factory=dict)


def erro_um_passo(p: Parametros, S0: np.ndarray, U: np.ndarray, S1: np.ndarray, sigma: np.ndarray) -> float:
    """Raiz da media dos quadrados do erro de um passo, cada grandeza dividida por `sigma`."""
    pred = passo(S0, U, p)
    return float(np.sqrt(np.mean(((pred - S1) / sigma) ** 2)))


def _ajustar(base: Parametros, S0, U, S1, sigma) -> Tuple[Parametros, object]:
    lower = np.array([lo for _, _, lo, _, _ in AJUSTADOS])
    upper = np.array([hi for _, _, _, hi, _ in AJUSTADOS])
    start = np.array([s for *_, s in AJUSTADOS])

    def residuals(theta):
        pred = passo(S0, U, base.com(theta))
        return ((pred - S1) / sigma).ravel()

    result = least_squares(residuals, start, bounds=(lower, upper), x_scale=np.maximum(np.abs(start), 1e-3),
                           method="trf", loss="linear", max_nfev=400)
    return base.com(result.x), result


def ajustar_fisica(base: Parametros, S0: np.ndarray, U: np.ndarray, S1: np.ndarray, sigma: np.ndarray) -> Ajuste:
    """Ajusta os 7 parametros nos passos de treino, com e sem a transferencia de carga, e aplica a regra."""
    without, res_without = _ajustar(replace(base, transferencia=False), S0, U, S1, sigma)
    with_, res_with = _ajustar(replace(base, transferencia=True), S0, U, S1, sigma)
    e_without = erro_um_passo(without, S0, U, S1, sigma)
    e_with = erro_um_passo(with_, S0, U, S1, sigma)
    use = (e_without - e_with) / e_without >= GANHO_MIN_TRANSFERENCIA
    chosen, result = (with_, res_with) if use else (without, res_without)
    theta = chosen.ajustados()
    at_bound = tuple(name for (name, _, lo, hi, _), v in zip(AJUSTADOS, theta)
                     if abs(v - lo) <= 1e-3 * max(abs(lo), 1e-3) or abs(v - hi) <= 1e-3 * max(abs(hi), 1e-3))
    return Ajuste(params=chosen, erro_um_passo=e_with if use else e_without, sem_transferencia=e_without,
                  com_transferencia=e_with, no_limite=at_bound, custo=float(result.cost), iteracoes=int(result.nfev),
                  detalhes={"sem": without.to_dict(), "com": with_.to_dict()})
