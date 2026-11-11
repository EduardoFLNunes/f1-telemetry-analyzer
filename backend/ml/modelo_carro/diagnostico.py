"""As contas do diagnostico da M1 v2 (pedido 48; secao 7.5 da M1). So analise, nenhum modelo novo.

As regras foram registradas antes das contas (secao 7.5.1). Aqui ficam as
funcoes puras, testadas com dados sinteticos em `tests/test_m1_diagnostico.py`:

* a deriva estimada de cada roda, pela formula do ADR 0028, item 3;
* o skill e o bootstrap agrupado por volta;
* a parte de cada grupo no erro e o skill que as curvas precisariam ter;
* o atraso pelo pico da correlacao, com o pico refinado por parabola;
* a regressao do ganho efetivo da direcao;
* a razao de acumulo e a autocorrelacao por pares dentro do trecho;
* o pico de um episodio de saida de traseira.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

VX_MIN = 5.0
FAIXAS_STEER = ((0.0, 0.1, "0 a 0,1"), (0.1, 0.2, "0,1 a 0,2"), (0.2, 0.4, "0,2 a 0,4"),
                (0.4, 0.6, "0,4 a 0,6"), (0.6, np.inf, "acima de 0,6"))
FAIXAS_DERIVA = ((0.0, 3.0, "abaixo de 3°"), (3.0, 6.0, "3° a 6°"), (6.0, 8.0, "6° a 8°"),
                 (8.0, 10.0, "8° a 10°"), (10.0, np.inf, "acima de 10°"))
FAIXAS_AY_G = ((0.0, 0.5, "abaixo de 0,5 g"), (0.5, 1.0, "0,5 a 1,0 g"), (1.0, 1.5, "1,0 a 1,5 g"),
               (1.5, 2.0, "1,5 a 2,0 g"), (2.0, np.inf, "acima de 2,0 g"))


def faixa(values: np.ndarray, faixas) -> np.ndarray:
    """O rotulo da faixa de cada valor (o modulo ja tirado por quem chama); '' fora de todas."""
    values = np.asarray(values, dtype=float)
    out = np.full(values.shape, "", dtype=object)
    for low, high, name in faixas:
        out[(values >= low) & (values < high)] = name
    return out


# --------------------------------------------------------------- deriva ---

def deriva_rodas(vx: np.ndarray, vy: np.ndarray, r: np.ndarray, steer: np.ndarray,
                 a: float, b: float, t_f: float, t_r: float, k_delta: float) -> np.ndarray:
    """A deriva de cada roda (n, 4), em rad, na ordem fl, fr, rl, rr (ADR 0028, item 3).

    `alpha_i = delta_i - atan2(vy + x_i*r, vx - y_i*r)`, com `delta = -k_delta*steer`
    na frente e zero atras, `y` positivo a esquerda e `vx` de pelo menos 5 m/s.
    """
    vx = np.maximum(np.asarray(vx, dtype=float), VX_MIN)
    vy, r, steer = (np.asarray(v, dtype=float) for v in (vy, r, steer))
    x = np.array([a, a, -b, -b])
    y = np.array([t_f / 2.0, -t_f / 2.0, t_r / 2.0, -t_r / 2.0])
    delta = -k_delta * steer
    d = np.column_stack([delta, delta, np.zeros_like(delta), np.zeros_like(delta)])
    return d - np.arctan2(vy[:, None] + x[None, :] * r[:, None], vx[:, None] - y[None, :] * r[:, None])


def deriva_eixos(alpha: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """(dianteira, traseira): a media das duas rodas de cada eixo, em rad."""
    return 0.5 * (alpha[:, 0] + alpha[:, 1]), 0.5 * (alpha[:, 2] + alpha[:, 3])


# ---------------------------------------------------------------- skill ---

def erro(sq: np.ndarray, mask: Optional[np.ndarray] = None) -> float:
    """O erro combinado: a raiz da media dos quadrados, sobre os casos e as 3 grandezas."""
    sq = np.asarray(sq, dtype=float)
    if mask is not None:
        sq = sq[mask]
    return float(np.sqrt(np.mean(sq) / 3.0)) if sq.size else float("nan")


def skill(sq_model: np.ndarray, sq_ref: np.ndarray, mask: Optional[np.ndarray] = None) -> float:
    e_m, e_r = erro(sq_model, mask), erro(sq_ref, mask)
    return float(1.0 - e_m / e_r) if e_r > 0 else float("nan")


def bootstrap_por_volta(sq_model: np.ndarray, sq_ref: np.ndarray, lap: np.ndarray, n: int = 10000,
                        seed: int = 48, bloco: int = 1000) -> Dict[str, float]:
    """IC 95% do skill, reamostrando voltas inteiras com reposicao (percentis 2,5 e 97,5)."""
    laps, inverse = np.unique(np.asarray(lap), return_inverse=True)
    sum_m = np.bincount(inverse, weights=np.asarray(sq_model, dtype=float), minlength=laps.size)
    sum_r = np.bincount(inverse, weights=np.asarray(sq_ref, dtype=float), minlength=laps.size)
    rng = np.random.default_rng(seed)
    skills = np.empty(n)
    for a in range(0, n, bloco):
        b = min(a + bloco, n)
        draws = rng.integers(0, laps.size, size=(b - a, laps.size))
        weights = np.zeros((b - a, laps.size))
        np.add.at(weights, (np.repeat(np.arange(b - a), laps.size), draws.ravel()), 1.0)
        skills[a:b] = 1.0 - np.sqrt(weights @ sum_m) / np.sqrt(weights @ sum_r)
    point = 1.0 - np.sqrt(sum_m.sum()) / np.sqrt(sum_r.sum())
    return {"skill": float(point), "p2_5": float(np.percentile(skills, 2.5)),
            "p97_5": float(np.percentile(skills, 97.5)), "voltas": int(laps.size), "reamostragens": int(n),
            "semente": int(seed)}


def partes(sq: np.ndarray, grupos: np.ndarray, mask: Optional[np.ndarray] = None) -> Dict[str, float]:
    """A parte de cada grupo na soma do erro quadratico (em %). Somam 100."""
    sq = np.asarray(sq, dtype=float)
    grupos = np.asarray(grupos)
    if mask is not None:
        sq, grupos = sq[mask], grupos[mask]
    total = sq.sum()
    return {str(g): float(100.0 * sq[grupos == g].sum() / total) for g in np.unique(grupos)}


def skill_necessario(sq_m1: np.ndarray, sq_r0: np.ndarray, grupo: np.ndarray, alvo: float = 0.5) -> Dict[str, float]:
    """Com o resto igual, que skill o `grupo` precisaria ter para o total chegar a `alvo`.

    `Sigma*_grupo = (1 - alvo)^2 * Sigma_R0,todos - Sigma_M1,resto` e o skill do
    grupo vira `1 - sqrt(Sigma*_grupo / Sigma_R0,grupo)`.
    """
    sq_m1, sq_r0, grupo = np.asarray(sq_m1, float), np.asarray(sq_r0, float), np.asarray(grupo, bool)
    alvo_soma = (1.0 - alvo) ** 2 * sq_r0.sum() - sq_m1[~grupo].sum()
    atual = 1.0 - np.sqrt(sq_m1[grupo].sum() / sq_r0[grupo].sum())
    if alvo_soma <= 0:
        return {"skill_atual": float(atual), "skill_necessario": float("nan"), "possivel": False}
    need = 1.0 - np.sqrt(alvo_soma / sq_r0[grupo].sum())
    return {"skill_atual": float(atual), "skill_necessario": float(need), "possivel": True,
            "soma_necessaria": float(alvo_soma), "soma_atual": float(sq_m1[grupo].sum())}


# --------------------------------------------------------------- atraso ---

def correlacao_cruzada(x: np.ndarray, y: np.ndarray, lags: np.ndarray, janela: slice) -> Tuple[np.ndarray, float, np.ndarray]:
    """Para um episodio: (soma de x*y deslocado em cada atraso, soma de x^2, soma de y^2 em cada atraso).

    `x` e `y` estao na mesma grade; `y` deslocado de `L` amostras e `y[i + L]`.
    A janela e aplicada em `x`; quem chama garante que `y` cobre a janela deslocada.
    """
    idx = np.arange(janela.start, janela.stop)
    xs = x[idx]
    cxy = np.array([np.dot(xs, y[idx + L]) for L in lags])
    cyy = np.array([np.dot(y[idx + L], y[idx + L]) for L in lags])
    return cxy, float(np.dot(xs, xs)), cyy


def pico_parabola(values: np.ndarray, step: float, first: float) -> float:
    """O argumento do maximo, refinado pela parabola nos tres pontos em volta."""
    i = int(np.nanargmax(values))
    if 0 < i < values.size - 1:
        y0, y1, y2 = values[i - 1], values[i], values[i + 1]
        den = y0 - 2.0 * y1 + y2
        off = 0.5 * (y0 - y2) / den if den != 0 else 0.0
        off = float(np.clip(off, -0.5, 0.5))
    else:
        off = 0.0
    return float(first + (i + off) * step)


def atraso_somado(cxy: np.ndarray, cxx: np.ndarray, cyy: np.ndarray, lags_s: np.ndarray) -> Tuple[float, np.ndarray]:
    """O atraso no pico da correlacao somada em varios episodios. Linhas = episodios."""
    rho = cxy.sum(axis=0) / np.sqrt(cxx.sum() * cyy.sum(axis=0))
    step = float(lags_s[1] - lags_s[0])
    return pico_parabola(rho, step, float(lags_s[0])), rho


def segmentos(t: np.ndarray, max_gap: float = 0.02) -> List[Tuple[int, int]]:
    """Os trechos das amostras cruas com intervalos de ate `max_gap`, como (inicio, fim exclusivo)."""
    t = np.asarray(t, dtype=float)
    if t.size == 0:
        return []
    cuts = np.flatnonzero(np.diff(t) > max_gap + 1e-9) + 1
    edges = np.concatenate([[0], cuts, [t.size]])
    return [(int(a), int(b)) for a, b in zip(edges[:-1], edges[1:]) if b - a >= 2]


def reamostrar_fino(t: np.ndarray, colunas: Dict[str, np.ndarray], dt: float = 0.005) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    """Interpolacao linear em `t0 + k*dt` ate a ultima amostra."""
    t = np.asarray(t, dtype=float)
    grid = t[0] + dt * np.arange(int(np.floor((t[-1] - t[0]) / dt + 1e-9)) + 1)
    return grid, {k: np.interp(grid, t, np.asarray(v, dtype=float)) for k, v in colunas.items()}


def entradas_de_curva(steer_abs: np.ndarray, limiar: float = 0.1, passo: int = 10, subidas: int = 4,
                      antes: int = 100, depois: int = 240) -> np.ndarray:
    """Os indices em que |steer| passa de `limiar` para cima e sobe nos `subidas` intervalos de `passo` seguintes.

    So entram os que tem `antes` amostras antes e `depois` amostras depois no trecho.
    Na grade de 5 ms, `passo=10` sao 50 ms, e 4 subidas sao 0,2 s.
    """
    a = np.asarray(steer_abs, dtype=float)
    cross = np.flatnonzero((a[:-1] < limiar) & (a[1:] >= limiar)) + 1
    out = []
    for i in cross:
        if i - antes < 0 or i + depois >= a.size:
            continue
        marks = a[i + passo * np.arange(subidas + 1)]
        if np.all(np.diff(marks) > 0):
            out.append(i)
    return np.asarray(out, dtype=int)


# ------------------------------------------------------------- direcao ---

def ganho_direcao(y: np.ndarray, menos_steer: np.ndarray, menos_a_y: np.ndarray, grupos: np.ndarray,
                  min_amostras: int = 200) -> Dict[str, object]:
    """`y = k_ef[grupo]*(-steer) + K*(-a_y)`: um `k_ef` por grupo, um `K` comum, sem intercepto.

    Grupos com menos de `min_amostras` ficam de fora da regressao.
    """
    y, s, ay, grupos = (np.asarray(v) for v in (y, menos_steer, menos_a_y, grupos))
    names = [g for g in dict.fromkeys(grupos.tolist()) if g != "" and (grupos == g).sum() >= min_amostras]
    sel = np.isin(grupos, names) & np.isfinite(y) & np.isfinite(s) & np.isfinite(ay)
    X = np.column_stack([*(np.where(grupos[sel] == g, s[sel], 0.0) for g in names), ay[sel]])
    coef, *_ = np.linalg.lstsq(X, y[sel], rcond=None)
    pred = X @ coef
    ss = float(np.sum((y[sel] - y[sel].mean()) ** 2))
    return {"k_ef": {g: float(c) for g, c in zip(names, coef[:-1])}, "K": float(coef[-1]),
            "amostras": {g: int(((grupos == g) & sel).sum()) for g in names},
            "r2": float(1.0 - np.sum((y[sel] - pred) ** 2) / ss) if ss > 0 else float("nan")}


def media_pesada(valores: Dict[str, float], pesos: Dict[str, int], chaves: Iterable[str]) -> float:
    chaves = [k for k in chaves if k in valores]
    if not chaves:
        return float("nan")
    w = np.array([pesos[k] for k in chaves], dtype=float)
    return float(np.dot(w, [valores[k] for k in chaves]) / w.sum())


# --------------------------------------------------- acumulo e memoria ---

def soma_de_incrementos(S: np.ndarray, um_passo: np.ndarray) -> np.ndarray:
    """O caminho previsto somando os incrementos de um passo, cada um a partir do gravado.

    `S` (n, H+1, 3) e o gravado; `um_passo` (n, H, 3) e a previsao de um passo a
    partir de `S[:, j]`. Devolve (n, H+1, 3), com o inicio igual ao gravado.
    """
    inc = um_passo - S[:, :-1]
    out = np.empty_like(S)
    out[:, 0] = S[:, 0]
    out[:, 1:] = S[:, :1] + np.cumsum(inc, axis=1)
    return out


def razao_acumulo(sq_malha_aberta: np.ndarray, sq_incrementos: np.ndarray, mask: Optional[np.ndarray] = None) -> float:
    e_inc = erro(sq_incrementos, mask)
    return float(erro(sq_malha_aberta, mask) / e_inc) if e_inc > 0 else float("nan")


def autocorrelacao_pares(res: np.ndarray, trecho: np.ndarray, k: np.ndarray, ok: np.ndarray,
                         lags: Sequence[int]) -> Dict[int, float]:
    """A correlacao de Pearson entre `res[k]` e `res[k+j]`, nos pares do mesmo trecho com os dois em `ok`."""
    res = np.asarray(res, dtype=float)
    trecho, k, ok = np.asarray(trecho), np.asarray(k), np.asarray(ok, dtype=bool)
    out = {}
    for j in lags:
        a = np.arange(res.size - j)
        b = a + j
        sel = (trecho[a] == trecho[b]) & (k[b] == k[a] + j) & ok[a] & ok[b] & np.isfinite(res[a]) & np.isfinite(res[b])
        out[int(j)] = float(np.corrcoef(res[a[sel]], res[b[sel]])[0, 1]) if sel.sum() >= 3 else float("nan")
    return out


def pares(n: int, trecho: np.ndarray, k: np.ndarray, j: int) -> Tuple[np.ndarray, np.ndarray]:
    """Os indices (a, a+j) do mesmo trecho com `k` andando exatamente `j` (as linhas estao em ordem)."""
    a = np.arange(max(n - j, 0))
    b = a + j
    sel = (np.asarray(trecho)[a] == np.asarray(trecho)[b]) & (np.asarray(k)[b] == np.asarray(k)[a] + j)
    return a[sel], b[sel]


def correlacao_parcial(y: np.ndarray, x: np.ndarray, Z: np.ndarray) -> float:
    """A correlacao de `y` com `x`, descontada a parte linear de `Z` (com intercepto) dos dois."""
    good = np.isfinite(y) & np.isfinite(x) & np.isfinite(Z).all(axis=1)
    y, x, Z = y[good], x[good], Z[good]
    A = np.column_stack([np.ones(len(y)), Z])
    ry = y - A @ np.linalg.lstsq(A, y, rcond=None)[0]
    rx = x - A @ np.linalg.lstsq(A, x, rcond=None)[0]
    return float(np.corrcoef(ry, rx)[0, 1])


# ------------------------------------------------------------ episodio ---

def indice_do_pico(s: np.ndarray, vx: np.ndarray, vy: np.ndarray, start_s: float, end_s: float,
                   length: float, depois_m: float = 50.0) -> Optional[int]:
    """A amostra de maior |atan2(vy, vx)| entre o inicio da curva e `depois_m` depois do fim."""
    s = np.asarray(s, dtype=float)
    span = np.mod(end_s - start_s, length) + depois_m
    inside = np.mod(s - start_s, length) <= span
    if not inside.any():
        return None
    beta = np.abs(np.arctan2(np.asarray(vy, float), np.asarray(vx, float)))
    beta = np.where(inside, beta, -np.inf)
    return int(np.argmax(beta))
