"""As 5 rodadas da M1 com a geometria medida (pedido 39, Parte E; ADR 0022 e ADR 0024).

Duas fases, nesta ordem:

* **treino** -- em cada rodada, so com as 4 sessoes de treino: os parametros das
  cargas, o envelope, a geometria medida (com `b = w_f * L`), a velocidade
  lateral levada ao centro de massa, o desvio-padrao de normalizacao, o ajuste
  da fisica e o erro dela contra a persistencia nas proprias sessoes de treino.
  Nada da sessao de teste e lido;
* **teste** -- a correcao aprendida (Processo Gaussiano), o corte de "nao
  conclusivo" e a previsao em malha aberta na sessao de fora, com R0, R1 e a M1.

Tudo o que e ajustado usa so as sessoes de treino da rodada (ADR 0022, item 2).
"""

from __future__ import annotations

import json
import time
from dataclasses import replace
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from . import convencoes as C
from . import correcao as K
from . import fisica as F
from . import geometria as Ge
from . import geometria_medida as GM
from . import validacao as V
from .dados import SESSOES_M1

H_CORTE = 10          # o indice de "fora dos dados" olha o caminho ate 0,5 s
A_CADA_CORTE = 10     # inicios a cada 0,5 s nas sessoes de treino, para o corte
PERCENTIL_CORTE = 99.0


def no_modelo(grades: Dict[str, pd.DataFrame], sessions: Sequence[str], conv: C.Convencoes) -> pd.DataFrame:
    return C.no_modelo(pd.concat([grades[s] for s in sessions], ignore_index=True), conv)


def levar_ao_centro(frame: pd.DataFrame, b: float, x_v: Optional[float]) -> pd.DataFrame:
    out = frame.copy()
    out["vy_gravada"] = out["vy"]
    out["vy"] = GM.vy_no_centro(out["vy"].to_numpy(dtype=float), out["r"].to_numpy(dtype=float), b, x_v)
    return out


def envelope_da_rodada(store: pd.DataFrame, laps: Sequence[str]):
    from ..optimization.vehicle_model import fit_envelope
    return fit_envelope(store[store["lap_id"].isin(laps)], source_laps=len(laps))


def parametros(params: Dict[str, object]) -> F.Parametros:
    """De volta do `to_dict` para `Parametros`."""
    values = {k: v for k, v in params.items() if k != "a"}
    values["env_speed"] = np.asarray(values["env_speed"], dtype=float)
    values["env_traction"] = np.asarray(values["env_traction"], dtype=float)
    return F.Parametros(**values)


def _erros(pred: np.ndarray, cs: V.Casos, sigma: np.ndarray) -> Dict[str, object]:
    out = {}
    for name, h in V.HORIZONTES.items():
        out[name] = {"erro": V.erro_combinado(pred, cs.S, sigma, h), "por_grandeza": V.por_grandeza(pred, cs.S, h)}
    return out


def fase_treino(test: str, grades: Dict[str, pd.DataFrame], conv: C.Convencoes, geo: Dict[str, float],
                store: pd.DataFrame, log=print) -> Dict[str, object]:
    """A rodada sem a sessao `test`, so com as 4 de treino."""
    started = time.time()
    train_ids = [s for s in SESSOES_M1 if s != test]
    train = no_modelo(grades, train_ids, conv)
    loads = Ge.medir(train)
    L, k_delta, x_v, h_L = geo["L"], geo["k_delta"], geo["x_v"], geo["h_L"]
    b = loads["w_f"] * L
    train = levar_ao_centro(train, b, x_v)
    sigma = train[list(V.ESTADO)].std().to_numpy()
    env = envelope_da_rodada(store, train["lap_id"].unique())
    base = F.Parametros(m=loads["m"], kappa_L=loads["kappa_L"], w_f=loads["w_f"], f_aero=loads["f_aero"], h_L=h_L,
                        b=b, L=L, k_delta=k_delta, brake_bias=loads["brake_bias"],
                        env_speed=env.speed_mps, env_traction=env.traction)
    P = V.passos(train)
    fit = F.ajustar_fisica(base, P.S0, P.U, P.S1, sigma)
    log(f"  fisica ajustada em {time.time() - started:.0f} s; transferencia={fit.params.transferencia}; no limite: {fit.no_limite}")

    # A fisica contra a persistencia nas proprias sessoes de treino (inicios a cada 0,1 s).
    cs = V.casos(train, conv)
    r1, _ = F.malha_aberta(cs.S0, cs.U, fit.params)
    r0 = F.persistencia(cs.S0, V.H_MAX)
    e1, e0 = _erros(r1, cs, sigma), _erros(r0, cs, sigma)
    diag = {"um_passo": {"R1": fit.erro_um_passo, "R0": float(np.sqrt(np.mean(((P.S0 - P.S1) / sigma) ** 2)))},
            "casos": len(cs), "R1": e1, "R0": e0,
            "skill_R1_contra_R0": {h: V.skill(e1[h]["erro"], e0[h]["erro"]) for h in V.HORIZONTES}}
    theta = fit.params.ajustados()
    return {
        "sessao_de_teste": test, "sessoes_de_treino": train_ids, "voltas_de_treino": int(train["lap_id"].nunique()),
        "passos_de_treino": len(P), "sigma": sigma.tolist(),
        "cargas": {k: loads[k] for k in ("m", "kappa_L", "w_f", "f_aero", "h_L", "brake_bias")},
        "geometria": {"L": L, "b": b, "a": L - b, "k_delta": k_delta, "x_v": x_v, "b_menos_x_v": b - x_v, "h_L": h_L},
        "ajustados": {name: float(v) for (name, *_), v in zip(F.AJUSTADOS, theta)},
        "no_limite": list(fit.no_limite), "transferencia": bool(fit.params.transferencia),
        "erro_um_passo_sem_transferencia": fit.sem_transferencia, "erro_um_passo_com_transferencia": fit.com_transferencia,
        "iteracoes": fit.iteracoes, "params": fit.params.to_dict(), "treino": diag,
        "tempo_s": round(time.time() - started, 1),
    }


def fase_teste(rodada: Dict[str, object], grades: Dict[str, pd.DataFrame], conv: C.Convencoes,
               geo: Dict[str, float], log=print) -> Dict[str, object]:
    """A correcao, o corte e a previsao na sessao de teste, com os parametros da fase de treino."""
    started = time.time()
    test = rodada["sessao_de_teste"]
    p = parametros(rodada["params"])
    sigma = np.asarray(rodada["sigma"], dtype=float)
    b = rodada["geometria"]["b"]
    train = levar_ao_centro(no_modelo(grades, rodada["sessoes_de_treino"], conv), b, geo["x_v"])
    P = V.passos(train)

    # A correcao: 400 passos por regime, o residuo de um passo da fisica.
    idx, counts = K.subconjunto(P.regime)
    X = np.column_stack([P.S0[idx], P.U[idx]])
    R = P.S1[idx] - F.passo(P.S0[idx], P.U[idx], p)
    corr = K.Correcao().ajustar(X, R)
    log(f"  correcao ajustada em {time.time() - started:.0f} s ({len(idx)} passos)")

    # O corte de "nao conclusivo", nas sessoes de treino.
    ct = V.casos(train, conv, a_cada=A_CADA_CORTE)
    _, idx_train = F.malha_aberta(ct.S0, ct.U[:, :H_CORTE], p, corr, com_indice=H_CORTE)
    cut = float(np.percentile(idx_train.max(axis=1), PERCENTIL_CORTE))

    # A sessao de teste: so agora ela e lida.
    test_frame = levar_ao_centro(no_modelo(grades, [test], conv), b, geo["x_v"])
    cs = V.casos(test_frame, conv)
    r0 = F.persistencia(cs.S0, V.H_MAX)
    r1, _ = F.malha_aberta(cs.S0, cs.U, p)
    m1, idx_test = F.malha_aberta(cs.S0, cs.U, p, corr, com_indice=H_CORTE)
    index = idx_test.max(axis=1)
    phys1 = F.passo(cs.S0, cs.U[:, 0], p)
    mean1, std1, _ = corr.prever(cs.S0, cs.U[:, 0])
    resid = cs.S[:, 1] - phys1
    log(f"  teste: {len(cs)} casos em {time.time() - started:.0f} s")

    per_case = {
        "sessao": np.full(len(cs), test, dtype=object), "volta": cs.lap, "regime": cs.regime,
        "faixa": V.faixa_de_velocidade(cs.vx_kmh), "vx_kmh": cs.vx_kmh, "pneu": cs.pneu,
        "indice": index, "nao_conclusivo": index > cut,
        "dentro_90": V.cobertura(resid, mean1, std1),
        "residuo_m1_um_passo": resid - mean1,
    }
    for model, pred in (("M1", m1), ("R1", r1), ("R0", r0)):
        pos = F.posicoes(pred)
        for name, h in V.HORIZONTES.items():
            per_case[f"sq_{model}_{h}"] = V.erro_quadrado(pred, cs.S, sigma, h)
            per_case[f"err_{model}_{h}"] = pred[:, h] - cs.S[:, h]
            per_case[f"pos_{model}_{h}"] = np.hypot(*(pos[:, h] - cs.P[:, h]).T)
    info = {"sessao_de_teste": test, "casos": len(cs), "corte": cut,
            "corte_casos_de_treino": int(len(ct)), "subconjunto": counts, "correcao": corr.info,
            "tempo_s": round(time.time() - started, 1)}
    return {"info": info, "casos": per_case, "_modelos": (p, corr, sigma, test_frame)}


# ------------------------------------------------------------ agregado ---

def juntar(partes: List[Dict[str, np.ndarray]]) -> Dict[str, np.ndarray]:
    keys = partes[0].keys()
    return {k: np.concatenate([p[k] for p in partes]) for k in keys}


def erro(sq: np.ndarray, mask: Optional[np.ndarray] = None) -> float:
    sq = sq if mask is None else sq[mask]
    return float(np.sqrt(np.mean(sq) / 3.0)) if sq.size else float("nan")


def tabela(cases: Dict[str, np.ndarray], key: str, h: int = V.H_PRINCIPAL) -> List[Dict[str, object]]:
    """Por grupo (sessao, regime ou faixa): casos, erros, skills e a fracao de nao conclusivo."""
    rows = []
    for group in pd.unique(cases[key]):
        m = cases[key] == group
        e = {model: erro(cases[f"sq_{model}_{h}"], m) for model in ("M1", "R1", "R0")}
        rows.append({key: str(group), "casos": int(m.sum()), "erro_M1": e["M1"], "erro_R1": e["R1"], "erro_R0": e["R0"],
                     "skill_M1_contra_R0": V.skill(e["M1"], e["R0"]), "skill_M1_contra_R1": V.skill(e["M1"], e["R1"]),
                     "skill_R1_contra_R0": V.skill(e["R1"], e["R0"]),
                     "nao_conclusivo": float(np.mean(cases["nao_conclusivo"][m]))})
    return rows


def veredito(cases: Dict[str, np.ndarray]) -> Dict[str, object]:
    h = V.H_PRINCIPAL
    e = {model: erro(cases[f"sq_{model}_{h}"]) for model in ("M1", "R1", "R0")}
    s_r0, s_r1 = V.skill(e["M1"], e["R0"]), V.skill(e["M1"], e["R1"])
    ci = V.bootstrap_skill(cases[f"sq_M1_{h}"], cases[f"sq_R1_{h}"], cases["volta"])
    per_session = {r["sessao"]: r for r in tabela(cases, "sessao")}
    positive = sum(1 for r in per_session.values() if r["skill_M1_contra_R1"] > 0)
    bias = {}
    for q, name in enumerate(V.ESTADO):
        b_m1 = float(np.mean(cases[f"err_M1_{h}"][:, q]))
        rmse_r1 = float(np.sqrt(np.mean(cases[f"err_R1_{h}"][:, q] ** 2)))
        bias[name] = {"vies_M1": b_m1, "rmse_R1": rmse_r1, "razao": abs(b_m1) / rmse_r1, "passa": abs(b_m1) <= 0.25 * rmse_r1}
    coverage = float(np.mean(cases["dentro_90"]))
    testable = sum(1 for r in per_session.values() if r["casos"] >= 100)
    criterios = [
        {"n": 1, "criterio": "skill contra R0 >= 0,50", "valor": s_r0, "passa": s_r0 >= 0.50},
        {"n": 2, "criterio": "skill contra R1 >= 0,20", "valor": s_r1, "passa": s_r1 >= 0.20},
        {"n": 3, "criterio": "limite inferior do IC 95% do skill contra R1 > 0", "valor": ci["p2_5"], "ic": ci,
         "passa": ci["p2_5"] > 0},
        {"n": 4, "criterio": "skill contra R1 positivo em pelo menos 4 das 5 sessoes", "valor": positive,
         "passa": positive >= 4},
        {"n": 5, "criterio": "|vies| de cada grandeza <= 25% do erro de R1", "valor": bias,
         "passa": all(v["passa"] for v in bias.values())},
        {"n": 6, "criterio": "o intervalo de 90% cobre de 80% a 97% no passo de dt", "valor": coverage,
         "por_grandeza": {name: float(np.mean(cases["dentro_90"][:, q])) for q, name in enumerate(V.ESTADO)},
         "passa": 0.80 <= coverage <= 0.97},
        {"n": 7, "criterio": "pelo menos 5 sessoes testaveis (>= 100 casos)", "valor": testable, "passa": testable >= 5},
    ]
    return {"erro_0_5s": e, "criterios": criterios, "aprovada": all(c["passa"] for c in criterios)}


def resumo_horizontes(cases: Dict[str, np.ndarray], mask: Optional[np.ndarray] = None) -> Dict[str, object]:
    out = {}
    for name, h in V.HORIZONTES.items():
        e = {model: erro(cases[f"sq_{model}_{h}"], mask) for model in ("M1", "R1", "R0")}
        sel = slice(None) if mask is None else mask
        out[name] = {
            "erro": e, "skill_M1_contra_R0": V.skill(e["M1"], e["R0"]), "skill_M1_contra_R1": V.skill(e["M1"], e["R1"]),
            "skill_R1_contra_R0": V.skill(e["R1"], e["R0"]),
            "por_grandeza": {model: {name_q: {"rmse": float(np.sqrt(np.mean(cases[f"err_{model}_{h}"][sel][:, q] ** 2))),
                                              "vies": float(np.mean(cases[f"err_{model}_{h}"][sel][:, q]))}
                                     for q, name_q in enumerate(V.ESTADO)} for model in ("M1", "R1", "R0")},
            "posicao_m": {model: {"media": float(np.mean(cases[f"pos_{model}_{h}"][sel])),
                                  "mediana": float(np.median(cases[f"pos_{model}_{h}"][sel])),
                                  "p90": float(np.percentile(cases[f"pos_{model}_{h}"][sel], 90))} for model in ("M1", "R1", "R0")},
        }
    return out


def correlacao_pneus(cases: Dict[str, np.ndarray]) -> Dict[str, Dict[str, float]]:
    from scipy.stats import pearsonr, spearmanr
    out = {}
    temp = cases["pneu"]
    good = np.isfinite(temp)
    for q, name in enumerate(V.ESTADO):
        r = cases["residuo_m1_um_passo"][:, q]
        sel = good & np.isfinite(r)
        rho, p = spearmanr(temp[sel], r[sel])
        rp, pp = pearsonr(temp[sel], r[sel])
        out[name] = {"spearman": float(rho), "p_spearman": float(p), "pearson": float(rp), "p_pearson": float(pp),
                     "casos": int(sel.sum())}
    return out
