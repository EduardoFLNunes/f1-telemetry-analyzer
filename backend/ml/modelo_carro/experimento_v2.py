"""As 5 rodadas da M1 v2 (pedido 46, Partes B e C; ADR 0028 e ADR 0022).

Duas fases, nesta ordem, como no pedido 39:

* **treino** -- em cada rodada, so com as 4 sessoes de treino: as cargas (as da
  v1 e a lateral), o envelope, a geometria medida, o ajuste da fisica v2, o erro
  da carga prevista e a fisica v2 contra a persistencia e contra a fisica v1 nas
  proprias sessoes de treino. Nada da sessao de teste e lido;
* **teste** -- a correcao (amostra proporcional), o corte de "nao conclusivo"
  pela vizinhanca e a previsao em malha aberta na sessao de fora, com R0, R1
  (a fisica v2), a M1 v2 e a fisica v1 (so relatada).
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from . import cargas_v2 as CG
from . import convencoes as C
from . import correcao as K
from . import correcao_v2 as K2
from . import fisica as F
from . import fisica_v2 as F2
from . import geometria as Ge
from . import validacao as V
from .dados import SESSOES_M1
from .experimento import envelope_da_rodada, levar_ao_centro, no_modelo, parametros as parametros_v1

A_CADA_CORTE = 10     # inicios a cada 0,5 s nas sessoes de treino, para o corte


def _erros(pred: np.ndarray, cs: V.Casos, sigma: np.ndarray, mask: Optional[np.ndarray] = None) -> Dict[str, object]:
    out = {}
    for name, h in V.HORIZONTES.items():
        out[name] = {"erro": V.erro_combinado(pred, cs.S, sigma, h, mask), "por_grandeza": V.por_grandeza(pred, cs.S, h, mask)}
    return out


def fase_treino(test: str, grades: Dict[str, pd.DataFrame], conv: C.Convencoes, geo: Dict[str, float],
                store: pd.DataFrame, rodada_v1: Dict[str, object], log=print) -> Dict[str, object]:
    """A rodada sem a sessao `test`, so com as 4 de treino."""
    started = time.time()
    train_ids = [s for s in SESSOES_M1 if s != test]
    train = no_modelo(grades, train_ids, conv)
    loads = Ge.medir(train)
    L, k_delta, x_v, h_L = geo["L"], geo["k_delta"], geo["x_v"], geo["h_L"]
    t_f, t_r = geo["bitola_dianteira"], geo["bitola_traseira"]
    b = loads["w_f"] * L
    train = levar_ao_centro(train, b, x_v)
    lateral = CG.medir_lateral(train, loads["m"], t_f, t_r)
    log(f"  carga lateral: lam={lateral['lam']:.3f} h_y={lateral['h_y']:.3f} m "
        f"(IC lam {lateral['incerteza_bootstrap']['lam']['p2_5']:.3f} a {lateral['incerteza_bootstrap']['lam']['p97_5']:.3f})")
    sigma = train[list(V.ESTADO)].std().to_numpy()
    env = envelope_da_rodada(store, train["lap_id"].unique())
    base = F2.ParametrosV2(m=loads["m"], kappa_L=loads["kappa_L"], w_f=loads["w_f"], f_aero=loads["f_aero"], h_L=h_L,
                           b=b, L=L, k_delta=k_delta, brake_bias=loads["brake_bias"],
                           lam=lateral["usado"]["lam"], h_y=lateral["usado"]["h_y"], t_f=t_f, t_r=t_r,
                           env_speed=env.speed_mps, env_traction=env.traction)
    erro_carga = CG.erro_da_carga(train, base)
    P = V.passos(train)
    fit = F2.ajustar_fisica(base, P.S0, P.U, P.S1, sigma)
    log(f"  fisica v2 ajustada em {time.time() - started:.0f} s; no limite: {fit.no_limite}")

    # A fisica v2 contra a persistencia e contra a fisica v1, nas proprias sessoes de treino.
    p1 = parametros_v1(rodada_v1["params"])
    cs = V.casos(train, conv)
    r2 = F2.malha_aberta(cs.S0, cs.U, fit.params)
    r1v1, _ = F.malha_aberta(cs.S0, cs.U, p1)
    r0 = F.persistencia(cs.S0, V.H_MAX)
    e2, e1, e0 = _erros(r2, cs, sigma), _erros(r1v1, cs, sigma), _erros(r0, cs, sigma)
    curva = cs.regime == "curva"
    diag = {
        "um_passo": {"fisica_v2": fit.erro_um_passo, "fisica_v1": F.erro_um_passo(p1, P.S0, P.U, P.S1, sigma),
                     "R0": float(np.sqrt(np.mean(((P.S0 - P.S1) / sigma) ** 2)))},
        "casos": len(cs), "fisica_v2": e2, "fisica_v1": e1, "R0": e0,
        "skill_v2_contra_R0": {h: V.skill(e2[h]["erro"], e0[h]["erro"]) for h in V.HORIZONTES},
        "skill_v2_contra_v1": {h: V.skill(e2[h]["erro"], e1[h]["erro"]) for h in V.HORIZONTES},
        "skill_v1_contra_R0": {h: V.skill(e1[h]["erro"], e0[h]["erro"]) for h in V.HORIZONTES},
        "curvas_0_5s": {"casos": int(curva.sum()),
                        "fisica_v2": V.erro_combinado(r2, cs.S, sigma, V.H_PRINCIPAL, curva),
                        "fisica_v1": V.erro_combinado(r1v1, cs.S, sigma, V.H_PRINCIPAL, curva),
                        "R0": V.erro_combinado(r0, cs.S, sigma, V.H_PRINCIPAL, curva)},
    }
    theta = fit.params.ajustados()
    return {
        "sessao_de_teste": test, "sessoes_de_treino": train_ids, "voltas_de_treino": int(train["lap_id"].nunique()),
        "passos_de_treino": len(P), "sigma": sigma.tolist(),
        "cargas": {k: loads[k] for k in ("m", "kappa_L", "w_f", "f_aero", "h_L", "brake_bias")},
        "cargas_amostras": loads["amostras"], "carga_lateral": lateral, "erro_da_carga": erro_carga,
        "geometria": {"L": L, "b": b, "a": L - b, "k_delta": k_delta, "x_v": x_v, "h_L": h_L, "t_f": t_f, "t_r": t_r},
        "ajustados": {name: float(v) for (name, *_), v in zip(F2.AJUSTADOS, theta)},
        "no_limite": list(fit.no_limite), "iteracoes": fit.iteracoes, "ajuste": fit.detalhes,
        "params": fit.params.to_dict(), "treino": diag, "tempo_s": round(time.time() - started, 1),
    }


def fase_teste(rodada: Dict[str, object], grades: Dict[str, pd.DataFrame], conv: C.Convencoes,
               geo: Dict[str, float], rodada_v1: Dict[str, object], n_amostra: int = K2.N_AMOSTRA,
               log=print) -> Dict[str, object]:
    """A correcao, o corte e a previsao na sessao de teste, com os parametros da fase de treino."""
    started = time.time()
    test = rodada["sessao_de_teste"]
    p = F2.ParametrosV2.from_dict(rodada["params"])
    p1 = parametros_v1(rodada_v1["params"])
    sigma = np.asarray(rodada["sigma"], dtype=float)
    b = rodada["geometria"]["b"]
    train = levar_ao_centro(no_modelo(grades, rodada["sessoes_de_treino"], conv), b, geo["x_v"])
    P = V.passos(train)

    # A correcao: a proporcao dos regimes, o residuo de um passo da fisica v2.
    idx, counts = K2.subconjunto(P.regime, n_amostra)
    X = np.column_stack([P.S0[idx], P.U[idx]])
    R = P.S1[idx] - F2.passo(P.S0[idx], P.U[idx], p)
    corr = K.Correcao().ajustar(X, R)
    log(f"  correcao ajustada em {time.time() - started:.0f} s ({len(idx)} passos: {counts})")

    # O corte de "nao conclusivo", nas sessoes de treino, sem os vizinhos da mesma volta.
    viz = K2.Vizinhanca(np.column_stack([P.S0, P.U]), P.lap)
    ct = V.casos(train, conv, a_cada=A_CADA_CORTE)
    idx_train = viz.indice_sem_a_volta(np.column_stack([ct.S0, ct.U[:, 0]]), ct.lap)
    cut = float(np.percentile(idx_train, K2.PERCENTIL_CORTE))

    # A sessao de teste: so agora ela e lida.
    test_frame = levar_ao_centro(no_modelo(grades, [test], conv), b, geo["x_v"])
    cs = V.casos(test_frame, conv)
    r0 = F.persistencia(cs.S0, V.H_MAX)
    r1 = F2.malha_aberta(cs.S0, cs.U, p)
    m1 = F2.malha_aberta(cs.S0, cs.U, p, corr)
    r1v1, _ = F.malha_aberta(cs.S0, cs.U, p1)
    index = viz.indice(np.column_stack([cs.S0, cs.U[:, 0]]))
    phys1 = F2.passo(cs.S0, cs.U[:, 0], p)
    mean1, std1, _ = corr.prever(cs.S0, cs.U[:, 0])
    resid = cs.S[:, 1] - phys1
    log(f"  teste: {len(cs)} casos em {time.time() - started:.0f} s; corte {cut:.3f}; "
        f"nao conclusivo {np.mean(index > cut):.3%}")

    per_case = {
        "sessao": np.full(len(cs), test, dtype=object), "volta": cs.lap, "regime": cs.regime,
        "faixa": V.faixa_de_velocidade(cs.vx_kmh), "vx_kmh": cs.vx_kmh, "pneu": cs.pneu,
        "indice": index, "nao_conclusivo": index > cut,
        "dentro_90": V.cobertura(resid, mean1, std1),
        "residuo_m1_um_passo": resid - mean1,
    }
    for model, pred in (("M1", m1), ("R1", r1), ("R0", r0), ("R1v1", r1v1)):
        pos = F.posicoes(pred)
        for name, h in V.HORIZONTES.items():
            per_case[f"sq_{model}_{h}"] = V.erro_quadrado(pred, cs.S, sigma, h)
            per_case[f"err_{model}_{h}"] = pred[:, h] - cs.S[:, h]
            per_case[f"pos_{model}_{h}"] = np.hypot(*(pos[:, h] - cs.P[:, h]).T)
    info = {"sessao_de_teste": test, "casos": len(cs), "corte": cut, "corte_casos_de_treino": int(len(ct)),
            "indice_treino_p50_p99": [float(np.percentile(idx_train, 50)), cut],
            "subconjunto": counts, "correcao": corr.info, "tempo_s": round(time.time() - started, 1)}
    return {"info": info, "casos": per_case, "_modelos": (p, p1, corr, sigma, test_frame, train)}


# ---------------------------------------------------------- relatorios ---

def _erro(sq: np.ndarray, mask: Optional[np.ndarray] = None) -> float:
    sq = sq if mask is None else sq[mask]
    return float(np.sqrt(np.mean(sq) / 3.0)) if sq.size else float("nan")


def lado_a_lado(cases: Dict[str, np.ndarray], v1: Optional[pd.DataFrame], key: Optional[str] = None,
                h: int = V.H_PRINCIPAL) -> List[Dict[str, object]]:
    """Erros e skills da v2 (M1 e fisica), da fisica v1 e da M1 v1 (pedido 39), por grupo."""
    groups = [("todos", np.ones(len(cases["volta"]), dtype=bool))] if key is None else \
        [(str(g), cases[key] == g) for g in pd.unique(cases[key])]
    rows = []
    for name, m in groups:
        e = {model: _erro(cases[f"sq_{model}_{h}"], m) for model in ("M1", "R1", "R0", "R1v1")}
        row = {"grupo": name, "casos": int(m.sum()), "erro_M1_v2": e["M1"], "erro_fisica_v2": e["R1"],
               "erro_fisica_v1": e["R1v1"], "erro_R0": e["R0"],
               "skill_M1_v2_contra_R0": V.skill(e["M1"], e["R0"]), "skill_M1_v2_contra_fisica_v2": V.skill(e["M1"], e["R1"]),
               "skill_fisica_v2_contra_R0": V.skill(e["R1"], e["R0"]),
               "skill_fisica_v2_contra_fisica_v1": V.skill(e["R1"], e["R1v1"]),
               "skill_M1_v2_contra_fisica_v1": V.skill(e["M1"], e["R1v1"]),
               "nao_conclusivo": float(np.mean(cases["nao_conclusivo"][m]))}
        if v1 is not None:
            e_m1v1 = _erro(v1[f"sq_M1_{h}"].to_numpy(dtype=float), m)
            row["erro_M1_v1"] = e_m1v1
            row["skill_M1_v1_contra_R0"] = V.skill(e_m1v1, e["R0"])
            row["skill_M1_v2_contra_M1_v1"] = V.skill(e["M1"], e_m1v1)
        rows.append(row)
    return rows


def por_grandeza(cases: Dict[str, np.ndarray], v1: Optional[pd.DataFrame], h: int,
                 mask: Optional[np.ndarray] = None) -> Dict[str, Dict[str, Dict[str, float]]]:
    sel = slice(None) if mask is None else mask
    out = {}
    models = [("M1 v2", cases[f"err_M1_{h}"]), ("fisica v2", cases[f"err_R1_{h}"]),
              ("fisica v1", cases[f"err_R1v1_{h}"]), ("R0", cases[f"err_R0_{h}"])]
    if v1 is not None:
        models.append(("M1 v1", np.stack(v1[f"err_M1_{h}"].to_numpy())))
    for label, err in models:
        err = np.asarray(err, dtype=float)[sel]
        out[label] = {q: {"rmse": float(np.sqrt(np.mean(err[:, i] ** 2))), "vies": float(np.mean(err[:, i]))}
                      for i, q in enumerate(V.ESTADO)}
    return out


def nao_conclusivo(cases: Dict[str, np.ndarray]) -> Dict[str, object]:
    nc = cases["nao_conclusivo"]
    out = {"total": {"casos": int(nc.size), "marcados": int(nc.sum()), "fracao": float(np.mean(nc))}}
    for key in ("regime", "sessao"):
        out[key] = {str(g): {"casos": int((cases[key] == g).sum()), "marcados": int(nc[cases[key] == g].sum()),
                             "fracao": float(np.mean(nc[cases[key] == g]))} for g in pd.unique(cases[key])}
    return out
