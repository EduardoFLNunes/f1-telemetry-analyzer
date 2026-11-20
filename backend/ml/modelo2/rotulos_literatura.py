"""Os rotulos pelos criterios da literatura (pedido 42, atualizacao de 20/11; secao 7 do documento do Modelo 2).

Independente dos detectores: este modulo nao importa `detectores.py` nem o codigo
da calibracao, e nao le o estado dos detectores nem os gabaritos. Ele recebe so
os tracos de uma passagem (na grade de 2 m, cortados por quem chama), os marcos
geometricos da curva, o `L` e o `k_delta` do pedido 39 e a referencia do proprio
carro (a reta da faixa linear, nas voltas do piloto). Nunca a mediana da IA.

Cada criterio devolve "aplica", "nao aplica" ou "nao sei", com o criterio que
decidiu, o valor medido e a margem.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

APLICA, NAO_APLICA, NAO_SEI = "aplica", "nao aplica", "nao sei"
G = 9.80665

# F4 (secao 7.4)
F4_SEM_FRENAGEM = 0.10
F4_TOPO = 0.90
F4_FIM = 0.02
F4_PENHASCO_S = 0.20
F4_GAGUEIRA = 0.04
F4_PONTOS = 30
F4_MARGEM = 0.80
F4_MIN_PONTOS = 4
# F5
F5_VIRAR = 0.25
F5_FREIO = 0.05            # Virtual Racing School: 5% a 10%
F5_FAIXA = 0.01
F5_FIM_DO_FREIO = 0.02
F5_CORRELACAO = -0.2
F5_MIN_PONTOS = 5
# M6
M6_SUBIDA = 0.08
M6_SEM_RETOMADA = 0.92
M6_QUEDA_SIM, M6_QUEDA_NAO = 0.08, 0.20
M6_VOLANTE_SIM, M6_VOLANTE_NAO = 0.05, 0.20
# E2
E2_LINEAR = (0.10, 0.35)    # g
E2_V_MIN_KMH = 50.0         # o corte do canal do MoTeC
E2_FORA_DA_LINEAR = 0.5     # g
E2_SIM, E2_NAO = 1.0, 0.4   # graus
E2_MIN_PONTOS = 5
# E3
E3_DEPOIS_DO_FIM_M = 60.0
E3_CONTRA_GRAUS = 0.5
E3_CONTRA_AY = 0.3          # g
E3_CONTRA_S = 0.15
E3_BETA = 10.0              # Bosch, citando Shibahata
E3_BETA_S = 0.10
E3_GUINADA = 0.10           # rad/s
E3_GUINADA_S = 0.20
E3_GUINADA_NAO = 0.05
E3_BETA_NAO = 5.0


@dataclass
class Janela:
    """Os tracos de uma passagem, do apice anterior ate 100 m depois do fim da curva, na grade de 2 m."""

    canais: Dict[str, Optional[np.ndarray]]
    t: np.ndarray                     # segundos desde o comeco da janela
    marcos: Dict[str, int]            # a, apice, m1, m2, e, e60 (indices na janela)
    direcao: int                      # +1 esquerda, -1 direita
    passo_m: float = 2.0

    def c(self, nome: str) -> Optional[np.ndarray]:
        v = self.canais.get(nome)
        return None if v is None or not np.isfinite(v).any() else v


@dataclass
class ReferenciaDoCarro:
    L: float
    k_delta: float
    k_us: float = float("nan")        # rad por g, a reta da faixa linear
    intercepto: float = float("nan")  # rad
    mu: float = float("nan")          # o percentil 99 de |a_y| / g nas voltas do piloto
    pontos: int = 0
    extra: Dict[str, object] = field(default_factory=dict)


def geometria_do_39(path: Path) -> Tuple[float, float]:
    used = json.loads(Path(path).read_text(encoding="utf-8"))["usados"]
    return float(used["L"]), float(used["k_delta"])


def _resultado(rotulo: str, criterio: str, valor=None, margem: str = "") -> Dict[str, object]:
    if isinstance(valor, float) and not np.isfinite(valor):
        valor = None
    return {"rotulo": rotulo, "criterio": criterio, "valor": valor, "margem": margem}


def _runs(mask: np.ndarray):
    if mask.size == 0 or not mask.any():
        return []
    padded = np.concatenate([[False], mask, [False]]).astype(int)
    d = np.diff(padded)
    return list(zip(np.flatnonzero(d == 1).tolist(), np.flatnonzero(d == -1).tolist()))


def _duracao_maxima(mask: np.ndarray, t: np.ndarray) -> float:
    best = 0.0
    for lo, hi in _runs(mask):
        best = max(best, float(t[min(hi, t.size - 1)] - t[lo]))
    return best


def _para_dentro(j: Janela) -> Optional[np.ndarray]:
    """O volante no sentido da curva (o volante e positivo a direita, pedido 39)."""
    steer = j.c("steer")
    return None if steer is None else -steer * j.direcao


# ------------------------------------------------------------------ F4 ---

def dtw(a: np.ndarray, b: np.ndarray) -> float:
    n, m = a.size, b.size
    cost = np.full((n + 1, m + 1), np.inf)
    cost[0, 0] = 0.0
    for i in range(1, n + 1):
        for k in range(1, m + 1):
            cost[i, k] = abs(a[i - 1] - b[k - 1]) + min(cost[i - 1, k], cost[i, k - 1], cost[i - 1, k - 1])
    return float(cost[n, m] / max(n, m))


def moldes_f4(n: int = F4_PONTOS) -> Tuple[np.ndarray, np.ndarray]:
    x = np.linspace(0.0, 1.0, n)
    return (1.0 - x) ** 2, np.where(x <= 0.5, 1.0, 0.0)


def rotulo_f4(j: Janela) -> Dict[str, object]:
    brake = j.c("brake")
    if brake is None:
        return _resultado(NAO_SEI, "sem o canal do freio")
    b = np.nan_to_num(brake)
    zona = b[:j.marcos["apice"] + 1]
    if zona.size == 0 or zona.max() < F4_SEM_FRENAGEM:
        return _resultado(NAO_SEI, "sem frenagem (freio < 0,10)", float(zona.max()) if zona.size else None)
    pico = int(np.argmax(zona))
    peak = float(zona[pico])
    depois = np.flatnonzero(b[pico:] < F4_FIM * peak)
    if not depois.size:
        return _resultado(NAO_SEI, "a descida nao acaba na janela")
    fim = pico + int(depois[0])
    # o topo: o ultimo ponto com freio >= 0,9 do maior antes do fim da descida
    acima = np.flatnonzero(b[pico:fim] >= F4_TOPO * peak)
    topo = pico + int(acima[-1]) if acima.size else pico
    descida = b[topo:fim + 1]
    dur = float(j.t[fim] - j.t[topo])
    if dur <= F4_PENHASCO_S:
        return _resultado(NAO_APLICA, "penhasco: a descida inteira em 0,20 s ou menos", round(dur, 3), "<= 0,20 s")
    subida = descida - np.minimum.accumulate(descida)
    if subida.max() >= F4_GAGUEIRA:
        return _resultado(NAO_APLICA, "gagueira: o freio volta a subir na descida", round(float(subida.max()), 3), ">= 0,04")
    t0 = j.t[topo] + 2.0 * dur / 3.0
    sel = np.flatnonzero((j.t >= t0) & (np.arange(j.t.size) >= topo) & (np.arange(j.t.size) <= fim))
    if sel.size < F4_MIN_PONTOS:
        return _resultado(NAO_SEI, "o ultimo terco tem menos de 4 pontos", int(sel.size))
    tt = (j.t[sel] - j.t[sel[0]]) / max(j.t[sel[-1]] - j.t[sel[0]], 1e-9)
    yy = b[sel] / max(b[sel[0]], 1e-9)
    x = np.linspace(0.0, 1.0, F4_PONTOS)
    curva = np.interp(x, tt, yy)
    rampa, degrau = moldes_f4()
    d_r, d_d = dtw(curva, rampa), dtw(curva, degrau)
    valor = {"dtw_rampa": round(d_r, 4), "dtw_degrau": round(d_d, 4)}
    if d_r < F4_MARGEM * d_d:
        return _resultado(APLICA, "mais perto da rampa curva (DTW)", valor, "rampa < 0,8 x degrau")
    if d_d < F4_MARGEM * d_r:
        return _resultado(NAO_APLICA, "mais perto do degrau (DTW)", valor, "degrau < 0,8 x rampa")
    return _resultado(NAO_SEI, "as duas distancias parecidas (DTW)", valor, "dentro de 20%")


# ------------------------------------------------------------------ F5 ---

def rotulo_f5(j: Janela) -> Dict[str, object]:
    brake, into = j.c("brake"), _para_dentro(j)
    if brake is None or into is None:
        return _resultado(NAO_SEI, "sem o freio ou o volante")
    b = np.nan_to_num(brake)
    a, apex, e = j.marcos["a"], j.marcos["apice"], j.marcos["e"]
    if b[:apex + 1].max() < F4_SEM_FRENAGEM:
        return _resultado(NAO_SEI, "curva sem frenagem nesta passagem (freio < 0,10)")
    maior = float(np.nanmax(into[a:e + 1])) if e >= a else float("nan")
    if not np.isfinite(maior) or maior <= 0:
        return _resultado(NAO_SEI, "sem volante para dentro da curva")
    acima = np.nan_to_num(into) >= F5_VIRAR * maior
    vira = None
    for i in range(1, apex + 1):
        if acima[i] and not acima[i - 1]:
            vira = i
    if vira is None:
        vira = int(np.flatnonzero(acima[:apex + 1])[0]) if acima[:apex + 1].any() else None
    if vira is None:
        return _resultado(NAO_SEI, "o volante nao passa de 0,25 do maior antes do apice")
    freio = float(b[vira])
    if freio < F5_FREIO - F5_FAIXA:
        return _resultado(NAO_APLICA, "freio abaixo de 5% quando o volante comeca a virar", round(freio, 3), "< 0,04")
    fim = apex
    solta = np.flatnonzero(b[vira:apex + 1] < F5_FIM_DO_FREIO)
    if solta.size:
        fim = vira + int(solta[0])
    xs, ys = b[vira:fim + 1], np.nan_to_num(into[vira:fim + 1])
    if freio < F5_FREIO + F5_FAIXA or xs.size < F5_MIN_PONTOS or np.std(xs) == 0 or np.std(ys) == 0:
        return _resultado(NAO_SEI, "o meio (freio perto de 5% ou sobreposicao curta)", round(freio, 3), "0,04 a 0,06")
    r = float(np.corrcoef(xs, ys)[0, 1])
    valor = {"freio_ao_virar": round(freio, 3), "correlacao": round(r, 3)}
    if r <= F5_CORRELACAO:
        return _resultado(APLICA, "freio >= 6% ao virar e o freio desce enquanto o volante sobe", valor, "r <= -0,2")
    return _resultado(NAO_SEI, "freio mantido, mas sem a correlacao negativa", valor, "r > -0,2")


# ------------------------------------------------------------------ M6 ---

def rotulo_m6(j: Janela) -> Dict[str, object]:
    thr, speed, into = j.c("throttle"), j.c("speed_kmh"), _para_dentro(j)
    if thr is None or speed is None:
        return _resultado(NAO_SEI, "sem o acelerador ou a velocidade")
    a, e = j.marcos["a"], j.marcos["e"]
    th = np.nan_to_num(thr)
    vmin = a + int(np.nanargmin(speed[a:e + 1]))
    seg = th[vmin:e + 1]
    if seg.size == 0 or seg.min() >= M6_SEM_RETOMADA:
        return _resultado(NAO_SEI, "o acelerador nao cai abaixo de 0,92: nada a retomar")
    low = np.minimum.accumulate(seg)
    sobe = np.flatnonzero(seg >= low + M6_SUBIDA)
    if not sobe.size:
        return _resultado(NAO_SEI, "sem subida do acelerador ate o fim da curva")
    i0 = vmin + int(sobe[0])
    resto = th[i0:e + 1]
    queda = float(np.clip(-np.diff(resto), 0.0, None).sum()) if resto.size > 1 else 0.0
    cresce = None
    if into is not None:
        maior = float(np.nanmax(into[a:e + 1]))
        if np.isfinite(maior) and maior > 0:
            cresce = float((np.nanmax(into[i0:e + 1]) - into[i0]) / maior)
    valor = {"queda_total": round(queda, 3), "volante_crescendo": None if cresce is None else round(cresce, 3)}
    if queda >= M6_QUEDA_NAO or (cresce is not None and cresce >= M6_VOLANTE_NAO):
        return _resultado(NAO_APLICA, "alivio claro ou o volante crescendo de novo", valor, "queda >= 0,20 ou volante >= 0,20")
    if queda <= M6_QUEDA_SIM and cresce is not None and cresce <= M6_VOLANTE_SIM:
        return _resultado(APLICA, "subida continua, sem alivio e sem o volante crescer", valor, "queda <= 0,08 e volante <= 0,05")
    return _resultado(NAO_SEI, "o meio", valor)


# ------------------------------------------------------------- E2 e E3 ---

def angulo_de_subesterco(steer: np.ndarray, ay_g: np.ndarray, v_kmh: np.ndarray, L: float, k_delta: float) -> np.ndarray:
    """UA = delta_roda - L*a_y/v^2, em rad; positivo e mais roda que a curva pede no sentido de a_y."""
    v = v_kmh / 3.6
    delta = -k_delta * steer
    with np.errstate(divide="ignore", invalid="ignore"):
        ua = delta - L * ay_g * G / (v * v)
    return np.sign(ay_g) * ua


def referencia_do_carro(voltas: Sequence[Dict[str, np.ndarray]], L: float, k_delta: float) -> ReferenciaDoCarro:
    """A reta da faixa linear (UA contra |a_y| em g) e o mu, nas voltas do piloto inteiras."""
    xs, ys, ay_all = [], [], []
    for v in voltas:
        steer, ay, vk = v.get("steer"), v.get("lateral_g"), v.get("speed_kmh")
        if steer is None or ay is None or vk is None:
            continue
        ok = np.isfinite(steer) & np.isfinite(ay) & np.isfinite(vk)
        ay_all.append(np.abs(ay[ok]))
        m = ok & (np.abs(ay) >= E2_LINEAR[0]) & (np.abs(ay) <= E2_LINEAR[1]) & (vk >= E2_V_MIN_KMH)
        if m.any():
            xs.append(np.abs(ay[m]))
            ys.append(angulo_de_subesterco(steer[m], ay[m], vk[m], L, k_delta))
    if not xs:
        return ReferenciaDoCarro(L=L, k_delta=k_delta)
    x, y = np.concatenate(xs), np.concatenate(ys)
    good = np.isfinite(y)
    k, c = np.polyfit(x[good], y[good], 1)
    mu = float(np.percentile(np.concatenate(ay_all), 99))
    return ReferenciaDoCarro(L=L, k_delta=k_delta, k_us=float(k), intercepto=float(c), mu=mu, pontos=int(good.sum()),
                             extra={"faixa_g": list(E2_LINEAR), "v_min_kmh": E2_V_MIN_KMH})


def rotulo_e2(j: Janela, ref: ReferenciaDoCarro) -> Dict[str, object]:
    steer, ay, vk, yaw = j.c("steer"), j.c("lateral_g"), j.c("speed_kmh"), j.c("yaw_rate")
    if yaw is None:
        return _resultado(NAO_SEI, "sem a guinada")
    if steer is None or ay is None or vk is None or not np.isfinite(ref.k_us):
        return _resultado(NAO_SEI, "sem o volante, a aceleracao lateral ou a reta do carro")
    m1, m2 = j.marcos["m1"], j.marcos["m2"]
    sl = slice(m1, max(m2, m1 + 1))
    ay_in = ay[sl] * j.direcao
    m = np.isfinite(ay_in) & (ay_in >= E2_FORA_DA_LINEAR) & (vk[sl] >= E2_V_MIN_KMH) & np.isfinite(steer[sl])
    if m.sum() < E2_MIN_PONTOS:
        return _resultado(NAO_SEI, "menos de 5 pontos com |a_y| >= 0,5 g e v >= 50 km/h no meio", int(m.sum()))
    ua = angulo_de_subesterco(steer[sl][m], ay[sl][m], vk[sl][m], ref.L, ref.k_delta)
    reta = ref.intercepto + ref.k_us * np.abs(ay[sl][m])
    excesso = float(np.degrees(np.nanmedian(ua - reta)))
    if excesso >= E2_SIM:
        return _resultado(APLICA, "o angulo de subesterco passa da reta do carro", round(excesso, 3), ">= 1,0 grau")
    if excesso <= E2_NAO:
        return _resultado(NAO_APLICA, "o angulo de subesterco fica dentro da reta do carro", round(excesso, 3), "<= 0,4 grau")
    return _resultado(NAO_SEI, "perto da margem", round(excesso, 3), "0,4 a 1,0 grau")


def rotulo_e3(j: Janela, ref: ReferenciaDoCarro) -> Dict[str, object]:
    steer, ay, vk = j.c("steer"), j.c("lateral_g"), j.c("speed_kmh")
    yaw, vx, vy = j.c("yaw_rate"), j.c("velocity_long"), j.c("velocity_lat")
    a = j.marcos["a"]
    fim = min(j.marcos.get("e60", j.marcos["e"]), j.t.size - 1)
    w = slice(a, fim + 1)
    t = j.t[w]
    sinais: Dict[str, object] = {}
    # (a) o contraesterco
    if steer is not None and ay is not None:
        roda = np.degrees(-ref.k_delta * steer[w]) * j.direcao
        contra = (roda <= -E3_CONTRA_GRAUS) & (ay[w] * j.direcao >= E3_CONTRA_AY)
        sinais["contraesterco_s"] = round(_duracao_maxima(contra, t), 3)
    # (b) a deriva
    if vx is not None and vy is not None:
        with np.errstate(invalid="ignore"):
            beta = np.degrees(np.arctan2(vy[w], np.where(vx[w] > 1.0, vx[w], np.nan)))
        b_abs = np.abs(beta)
        sinais["beta_max_graus"] = None if not np.isfinite(b_abs).any() else round(float(np.nanmax(b_abs)), 2)
        sinais["beta_10_s"] = round(_duracao_maxima(np.nan_to_num(b_abs) >= E3_BETA, t), 3)
    # (c) a guinada acima da referencia
    if yaw is not None and steer is not None and vk is not None and np.isfinite(ref.k_us):
        v = vk[w] / 3.6
        delta = -ref.k_delta * steer[w]
        with np.errstate(divide="ignore", invalid="ignore"):
            r_ref = v * delta / (ref.L + ref.k_us * v * v / G)
            teto = ref.mu * G / v
        r_ref = np.clip(r_ref, -teto, teto)
        excesso = (yaw[w] - r_ref) * j.direcao
        sinais["guinada_excesso_max"] = None if not np.isfinite(excesso).any() else round(float(np.nanmax(excesso)), 3)
        sinais["guinada_excesso_s"] = round(_duracao_maxima(np.nan_to_num(excesso) >= E3_GUINADA, t), 3)
    disparou = []
    if sinais.get("contraesterco_s", 0) >= E3_CONTRA_S:
        disparou.append("contraesterco")
    if sinais.get("beta_10_s", 0) >= E3_BETA_S:
        disparou.append("deriva >= 10 graus")
    if sinais.get("guinada_excesso_s", 0) >= E3_GUINADA_S:
        disparou.append("guinada acima da referencia")
    if disparou:
        return _resultado(APLICA, " + ".join(disparou), sinais, "qualquer um dos tres sinais")
    if "guinada_excesso_max" not in sinais or "beta_max_graus" not in sinais:
        return _resultado(NAO_SEI, "sem a guinada ou as velocidades no referencial do carro, e sem contraesterco", sinais)
    calmo = (sinais["guinada_excesso_max"] is not None and sinais["guinada_excesso_max"] <= E3_GUINADA_NAO
             and sinais["beta_max_graus"] is not None and sinais["beta_max_graus"] < E3_BETA_NAO)
    if calmo:
        return _resultado(NAO_APLICA, "guinada dentro da referencia e deriva abaixo de 5 graus", sinais,
                          "excesso <= 0,05 rad/s e |beta| < 5 graus")
    return _resultado(NAO_SEI, "o meio", sinais)


def rotular(pergunta: str, j: Janela, ref: ReferenciaDoCarro) -> Dict[str, object]:
    if pergunta == "F4":
        return rotulo_f4(j)
    if pergunta == "F5":
        return rotulo_f5(j)
    if pergunta == "M6":
        return rotulo_m6(j)
    if pergunta == "E2":
        return rotulo_e2(j, ref)
    if pergunta == "E3":
        return rotulo_e3(j, ref)
    raise KeyError(pergunta)
