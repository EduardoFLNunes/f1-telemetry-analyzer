"""A fisica da M1 v2: quatro rodas, o pneu com sensibilidade a carga e pico (pedido 46; ADR 0028).

Por unidade de massa, como a v1 (`fisica.py`). Registrado antes de rodar
(ADR 0028, itens 2 a 5):

* **a carga de cada roda:** o peso parado, o downforce e a transferencia
  longitudinal por eixo, como na v1, e a transferencia lateral
  `dN_f = lam*h_y*a_y/t_f`, `dN_r = (1 - lam)*h_y*a_y/t_r`. Numa curva a
  esquerda (`a_y > 0`) a carga vai para as rodas da direita. Com a bitola em
  zero nao ha lados nem transferencia lateral;
* **o modelo de quatro rodas:** cada roda com o seu angulo de deriva, a sua
  carga e a sua forca; o momento de guinada inclui os lados;
* **o pneu lateral (v2):** `mu(n) = mu_ref*(n/n_ref)^(q-1)`, `n_ref = g/4`, e a
  Formula Magica de Pacejka sem deslocamentos, com `B`, `C`, `D`, `E` tirados
  da rigidez `C_alpha*n`, de `D = mu(n)*n` (menos a forca longitudinal, pela
  elipse), do angulo do pico e do nivel `f` depois dele;
* **o pneu da v1** (`tanh`, sem sensibilidade a carga) fica disponivel para o
  teste de que, com a bitola em zero, as quatro rodas sao a bicicleta da v1.

A ordem das rodas e `fl, fr, rl, rr`. `y` e positivo a esquerda.
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
N_MIN = 0.05          # carga minima de uma roda na conta (m/s^2): a roda nao puxa o chao
N_REF = G / 4.0       # a carga de referencia do pneu (ADR 0028, item 4)
F_MAX_CONTA = 0.999   # o nivel depois do pico vai no maximo a isto na conta, para o pico existir

# Os 10 parametros ajustados: (nome, unidade, limite inferior, superior, inicio). ADR 0028, item 5.
AJUSTADOS = (
    ("C_alpha", "1/rad", 5.0, 60.0, 20.0),
    ("mu_ref", "-", 1.0, 2.5, 1.6),
    ("q", "-", 0.6, 1.0, 0.85),
    ("alpha_pico", "rad", np.radians(3.0), np.radians(12.0), np.radians(6.0)),
    ("f", "-", 0.7, 1.0, 0.85),
    ("k2", "m^2", 0.5, 4.0, 1.5),
    ("kappa_D", "1/m", 0.0003, 0.003, 0.001),
    ("c0", "m/s^2", 0.0, 3.0, 1.0),
    ("s_T", "-", 0.5, 1.5, 1.0),
    ("beta_B", "m/s^2", 10.0, 60.0, 30.0),
)

# As faixas da carga lateral (ADR 0028, item 2).
FAIXA_LAMBDA = (0.30, 0.70)
FAIXA_H_Y = (0.15, 0.45)


@dataclass
class ParametrosV2:
    # Medidos (cargas da rodada e geometria medida).
    m: float
    kappa_L: float
    w_f: float
    f_aero: float
    h_L: float
    b: float
    L: float
    k_delta: float
    brake_bias: float
    lam: float
    h_y: float
    t_f: float
    t_r: float
    env_speed: np.ndarray
    env_traction: np.ndarray
    # Ajustados.
    C_alpha: float = 20.0
    mu_ref: float = 1.6
    q: float = 0.85
    alpha_pico: float = float(np.radians(6.0))
    f: float = 0.85
    k2: float = 1.5
    kappa_D: float = 0.001
    c0: float = 1.0
    s_T: float = 1.0
    beta_B: float = 30.0
    # "v2" (Pacejka com pico e sensibilidade a carga) ou "v1" (tanh, so para o teste da bicicleta).
    pneu: str = "v2"
    n_ref: float = N_REF

    @property
    def a(self) -> float:
        return self.L - self.b

    def ajustados(self) -> np.ndarray:
        return np.array([getattr(self, name) for name, *_ in AJUSTADOS], dtype=float)

    def com(self, theta: Sequence[float], **extra) -> "ParametrosV2":
        values = {name: float(v) for (name, *_), v in zip(AJUSTADOS, theta)}
        values.update(extra)
        return replace(self, **values)

    def to_dict(self) -> Dict[str, object]:
        out = {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in self.__dict__.items()}
        out["a"] = self.a
        return out

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "ParametrosV2":
        values = {k: v for k, v in payload.items() if k != "a"}
        values["env_speed"] = np.asarray(values["env_speed"], dtype=float)
        values["env_traction"] = np.asarray(values["env_traction"], dtype=float)
        return cls(**values)

    def rodas(self) -> Tuple[np.ndarray, np.ndarray]:
        """(x, y) de cada roda a partir do centro de massa, na ordem fl, fr, rl, rr."""
        x = np.array([self.a, self.a, -self.b, -self.b])
        y = np.array([self.t_f / 2.0, -self.t_f / 2.0, self.t_r / 2.0, -self.t_r / 2.0])
        return x, y


# ---------------------------------------------------------------- cargas ---

def cargas_por_eixo(vx: np.ndarray, a_x: np.ndarray, p) -> Tuple[np.ndarray, np.ndarray]:
    """(n_f, n_r) por unidade de massa: o peso parado, o downforce e a transferencia longitudinal."""
    v2 = np.asarray(vx, dtype=float) ** 2
    n_f = G * p.w_f + p.kappa_L * p.f_aero * v2 - p.h_L * a_x
    n_r = G * (1.0 - p.w_f) + p.kappa_L * (1.0 - p.f_aero) * v2 + p.h_L * a_x
    return n_f, n_r


def transferencia_lateral(a_y: np.ndarray, p) -> Tuple[np.ndarray, np.ndarray]:
    """(dN_f, dN_r) por roda; zero num eixo sem bitola."""
    a_y = np.asarray(a_y, dtype=float)
    d_f = p.lam * p.h_y * a_y / p.t_f if p.t_f > 0 else np.zeros_like(a_y)
    d_r = (1.0 - p.lam) * p.h_y * a_y / p.t_r if p.t_r > 0 else np.zeros_like(a_y)
    return d_f, d_r


def cargas(vx: np.ndarray, a_x: np.ndarray, a_y: np.ndarray, p) -> np.ndarray:
    """A carga de cada roda (n, 4), por unidade de massa, sem o piso de `N_MIN`."""
    n_f, n_r = cargas_por_eixo(vx, a_x, p)
    d_f, d_r = transferencia_lateral(a_y, p)
    return np.column_stack([n_f / 2.0 - d_f, n_f / 2.0 + d_f, n_r / 2.0 - d_r, n_r / 2.0 + d_r])


# ------------------------------------------------------------------ pneu ---

def mu_de(n: np.ndarray, p) -> np.ndarray:
    """O atrito de cada roda: sensivel a carga no pneu da v2, constante no da v1."""
    if p.pneu == "v1":
        return np.full_like(np.asarray(n, dtype=float), p.mu_ref)
    return p.mu_ref * np.power(np.maximum(n, N_MIN) / p.n_ref, p.q - 1.0)


def coef_pacejka(f: float) -> Tuple[float, float]:
    """(C, tan(pi/(2C))) a partir do nivel `f` depois do pico."""
    C = 2.0 - (2.0 / np.pi) * np.arcsin(min(float(f), F_MAX_CONTA))
    return C, float(np.tan(np.pi / (2.0 * C)))


def forca_lateral(alpha: np.ndarray, n: np.ndarray, D: np.ndarray, p) -> np.ndarray:
    """A forca lateral de cada roda (mesma forma que `alpha`)."""
    if p.pneu == "v1":
        return D * np.tanh(p.C_alpha * n * alpha / D)
    C, T = coef_pacejka(p.f)
    B = p.C_alpha * n / (C * D)
    xp = B * p.alpha_pico
    E = (xp - T) / np.maximum(xp - np.arctan(xp), 1e-12)
    x = B * alpha
    phi = x - E * (x - np.arctan(x))
    return D * np.sin(C * np.arctan(phi))


# -------------------------------------------------------------- dinamica ---

def _forcas(n: np.ndarray, alpha: np.ndarray, sin_d: np.ndarray, cos_d: np.ndarray,
            drive: np.ndarray, demand: np.ndarray, resist: np.ndarray, p):
    """Forcas de cada roda nos eixos do carro, dadas as cargas (n, 4)."""
    n = np.maximum(n, N_MIN)
    mu = mu_de(n, p)
    lim = 0.99 * mu * n
    fx = np.empty_like(n)
    fx[:, 0] = -np.minimum(0.5 * demand * p.brake_bias, lim[:, 0])
    fx[:, 1] = -np.minimum(0.5 * demand * p.brake_bias, lim[:, 1])
    for w in (2, 3):
        rear = np.minimum(0.5 * drive, lim[:, w]) - np.minimum(0.5 * demand * (1.0 - p.brake_bias), lim[:, w])
        fx[:, w] = np.clip(rear, -lim[:, w], lim[:, w])
    D = np.sqrt(np.maximum((mu * n) ** 2 - fx ** 2, EPS))
    fy = forca_lateral(alpha, n, D, p)
    FX = fx * cos_d - fy * sin_d
    FY = fx * sin_d + fy * cos_d
    ax = FX.sum(axis=1) - resist
    ay = FY.sum(axis=1)
    return FX, FY, ax, ay


def derivadas(state: np.ndarray, u: np.ndarray, p: ParametrosV2) -> np.ndarray:
    """d(vx, vy, r)/dt para cada linha. `state` (n, 3) e `u` (n, 3) = (steer, T, B)."""
    vx, vy, r = state[:, 0], state[:, 1], state[:, 2]
    steer, T, B = u[:, 0], np.clip(u[:, 1], 0.0, 1.0), np.clip(u[:, 2], 0.0, 1.0)
    vxc = np.maximum(vx, VX_MIN)
    delta = -p.k_delta * steer
    xw, yw = p.rodas()
    zero = np.zeros_like(delta)
    d = np.column_stack([delta, delta, zero, zero])
    sin_d, cos_d = np.sin(d), np.cos(d)
    alpha = d - np.arctan2(vy[:, None] + xw[None, :] * r[:, None], vxc[:, None] - yw[None, :] * r[:, None])
    v2 = vxc ** 2
    a_env = np.interp(vxc, p.env_speed, p.env_traction)
    drive = np.maximum(p.s_T * T * (a_env + p.kappa_D * v2 + p.c0), 0.0)
    resist = p.kappa_D * v2 + p.c0 * (1.0 - T)
    demand = p.beta_B * B

    # Ponto fixo de uma iteracao (ADR 0028, item 2): sem transferencia, depois com a do proprio a_x e a_y.
    n0 = cargas(vxc, zero, zero, p)
    _, _, ax, ay = _forcas(n0, alpha, sin_d, cos_d, drive, demand, resist, p)
    n1 = cargas(vxc, ax, ay, p)
    FX, FY, ax, _ = _forcas(n1, alpha, sin_d, cos_d, drive, demand, resist, p)
    dvx = ax + vy * r
    dvy = FY.sum(axis=1) - vx * r
    dr = ((FY * xw[None, :]).sum(axis=1) - (FX * yw[None, :]).sum(axis=1)) / p.k2
    return np.column_stack([dvx, dvy, dr])


def passo(state: np.ndarray, u: np.ndarray, p: ParametrosV2, dt: float = DT, subpassos: int = SUBPASSOS) -> np.ndarray:
    """O estado depois de um passo de `dt`, com a entrada constante (Heun)."""
    h = dt / subpassos
    x = np.asarray(state, dtype=float)
    for _ in range(subpassos):
        k1 = derivadas(x, u, p)
        k2 = derivadas(x + h * k1, u, p)
        x = x + 0.5 * h * (k1 + k2)
    return x


def malha_aberta(state0: np.ndarray, U: np.ndarray, p: ParametrosV2, correcao=None) -> np.ndarray:
    """Anda `U.shape[1]` passos com as entradas gravadas; com `correcao`, soma a media do residuo (a M1 v2)."""
    n, steps, _ = U.shape
    out = np.empty((n, steps + 1, 3))
    out[:, 0] = state0
    x = np.asarray(state0, dtype=float)
    for k in range(steps):
        nxt = passo(x, U[:, k], p)
        if correcao is not None:
            mean, _, _ = correcao.prever(x, U[:, k], com_desvio=False)
            nxt = nxt + mean
        out[:, k + 1] = nxt
        x = nxt
    return out


# ---------------------------------------------------------------- ajuste ---

@dataclass
class AjusteV2:
    params: ParametrosV2
    erro_um_passo: float
    no_limite: Tuple[str, ...]
    custo: float
    iteracoes: int
    detalhes: Dict[str, object] = field(default_factory=dict)


def erro_um_passo(p: ParametrosV2, S0: np.ndarray, U: np.ndarray, S1: np.ndarray, sigma: np.ndarray) -> float:
    pred = passo(S0, U, p)
    return float(np.sqrt(np.mean(((pred - S1) / sigma) ** 2)))


def ajustar_fisica(base: ParametrosV2, S0: np.ndarray, U: np.ndarray, S1: np.ndarray, sigma: np.ndarray,
                   max_nfev: int = 400) -> AjusteV2:
    """Os 10 parametros por minimos quadrados no estado depois de um passo (ADR 0028, item 5)."""
    lower = np.array([lo for _, _, lo, _, _ in AJUSTADOS])
    upper = np.array([hi for _, _, _, hi, _ in AJUSTADOS])
    start = np.array([s for *_, s in AJUSTADOS])

    def residuals(theta):
        pred = passo(S0, U, base.com(theta))
        return ((pred - S1) / sigma).ravel()

    result = least_squares(residuals, start, bounds=(lower, upper), x_scale=np.maximum(np.abs(start), 1e-3),
                           method="trf", loss="linear", max_nfev=max_nfev)
    chosen = base.com(result.x)
    theta = chosen.ajustados()
    at_bound = tuple(name for (name, _, lo, hi, _), v in zip(AJUSTADOS, theta)
                     if abs(v - lo) <= 1e-3 * max(abs(lo), 1e-3) or abs(v - hi) <= 1e-3 * max(abs(hi), 1e-3))
    return AjusteV2(params=chosen, erro_um_passo=erro_um_passo(chosen, S0, U, S1, sigma), no_limite=at_bound,
                    custo=float(result.cost), iteracoes=int(result.nfev),
                    detalhes={"status": int(result.status), "mensagem": str(result.message)})


# ------------------------------------------------- envelope (Parte D.1) ---

def _bissecao(feasible, low: float, high: float, iters: int = 60) -> float:
    for _ in range(iters):
        mid = 0.5 * (low + high)
        if feasible(mid):
            low = mid
        else:
            high = mid
    return low


def envelope(p: ParametrosV2, speeds_mps: np.ndarray, top_speed_mps: float, samples: Optional[np.ndarray] = None,
             source_laps: int = 0):
    """O envelope de aceleracao da M1 v2 em regime permanente (ADR 0028, item 10)."""
    from ..optimization.vehicle_model import VehicleEnvelope
    speeds = np.asarray(speeds_mps, dtype=float)
    lateral, braking, traction = [], [], []
    for v in speeds:
        vv = np.array([max(v, VX_MIN)])

        def axle_max(a_y: float) -> Tuple[float, float]:
            n = np.maximum(cargas(vv, np.zeros(1), np.array([a_y]), p)[0], N_MIN)
            grip = mu_de(n, p) * n
            return float(grip[0] + grip[1]), float(grip[2] + grip[3])

        def lat_ok(a_y: float) -> bool:
            f_f, f_r = axle_max(a_y)
            return a_y * p.b / p.L <= f_f and a_y * p.a / p.L <= f_r

        lateral.append(_bissecao(lat_ok, 0.0, 10.0 * G))

        drag = p.kappa_D * vv[0] ** 2
        dec = 0.0
        for _ in range(50):
            n = np.maximum(cargas(vv, np.array([-dec]), np.zeros(1), p)[0], N_MIN)
            lim = 0.99 * mu_de(n, p) * n
            share = np.array([p.brake_bias, p.brake_bias, 1.0 - p.brake_bias, 1.0 - p.brake_bias]) * 0.5
            dec = float(np.minimum(p.beta_B * share, lim).sum() + drag + p.c0)
        braking.append(dec)

        a_env = float(np.interp(vv[0], p.env_speed, p.env_traction))
        acc = 0.0
        for _ in range(50):
            n = np.maximum(cargas(vv, np.array([acc]), np.zeros(1), p)[0], N_MIN)
            lim = 0.99 * mu_de(n, p) * n
            drive = min(p.s_T * (a_env + drag + p.c0), float(lim[2] + lim[3]))
            acc = max(drive - drag, 0.0)
        traction.append(acc)
    counts = np.asarray(samples, dtype=float) if samples is not None else np.zeros(speeds.size)
    return VehicleEnvelope(speed_mps=speeds, lateral=np.asarray(lateral), braking=np.asarray(braking),
                           traction=np.asarray(traction), top_speed_mps=float(top_speed_mps), samples=counts,
                           source_laps=source_laps)
