"""O modelo supervisionado leve (secao 1.8): o tempo do trecho contra os indicadores, por curva.

Ridge com o alvo e as entradas centrados pela media de cada sessao (a sessao
como efeito fixo), validado deixando uma sessao de fora. Descritivo: mostra
associacao, nao causa, e nao vira ganho estimado (ADR 0004).
"""

from __future__ import annotations

from typing import Dict, List, Sequence

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

ALPHAS = (0.3, 1.0, 3.0, 10.0, 30.0, 100.0)
MIN_PASSES = 30
MIN_SESSIONS = 3
COVERAGE = 0.80
BOOTSTRAP = 500
SEED = 38


def _prepare(train: pd.DataFrame, test: pd.DataFrame, features: Sequence[str]):
    med = train[list(features)].median()
    def centred(frame):
        X = frame[list(features)].fillna(med)
        X = X - X.groupby(frame["sessao"]).transform("mean")
        y = frame["tempo_trecho_s"] - frame.groupby("sessao")["tempo_trecho_s"].transform("mean")
        return X, y
    Xtr, ytr = centred(train)
    Xte, yte = centred(test)
    sd = Xtr.std(ddof=0).replace(0, 1.0)
    return (Xtr / sd).to_numpy(), ytr.to_numpy(), (Xte / sd).to_numpy(), yte.to_numpy()


def _loso(frame: pd.DataFrame, features: Sequence[str], alpha: float) -> tuple:
    sse = sst = 0.0
    for s in frame["sessao"].unique():
        tr, te = frame[frame["sessao"] != s], frame[frame["sessao"] == s]
        Xtr, ytr, Xte, yte = _prepare(tr, te, features)
        model = Ridge(alpha=alpha, fit_intercept=False).fit(Xtr, ytr)
        sse += float(((yte - model.predict(Xte)) ** 2).sum())
        sst += float((yte ** 2).sum())
    return sse, sst


def choose_alpha(frame: pd.DataFrame, features: Sequence[str]) -> float:
    best, best_sse = ALPHAS[0], np.inf
    if frame["sessao"].nunique() < 3:
        return 10.0
    for alpha in ALPHAS:
        sse, _ = _loso(frame, features, alpha)
        if sse < best_sse:
            best, best_sse = alpha, sse
    return best


def fit_corner(frame: pd.DataFrame, candidates: Sequence[str]) -> Dict[str, object]:
    frame = frame.dropna(subset=["tempo_trecho_s"])
    features = [c for c in candidates if c in frame and frame[c].notna().mean() >= COVERAGE and frame[c].nunique() > 2]
    out = {"passagens": int(len(frame)), "sessoes": int(frame["sessao"].nunique()), "entradas": features}
    if len(frame) < MIN_PASSES or frame["sessao"].nunique() < MIN_SESSIONS or not features:
        out["situacao"] = "poucos dados"
        return out
    sse = sst = 0.0
    alphas = []
    for s in frame["sessao"].unique():
        tr, te = frame[frame["sessao"] != s], frame[frame["sessao"] == s]
        alpha = choose_alpha(tr, features)
        alphas.append(alpha)
        Xtr, ytr, Xte, yte = _prepare(tr, te, features)
        model = Ridge(alpha=alpha, fit_intercept=False).fit(Xtr, ytr)
        sse += float(((yte - model.predict(Xte)) ** 2).sum())
        sst += float((yte ** 2).sum())
    out["r2_deixando_uma_sessao_de_fora"] = round(1.0 - sse / sst, 3) if sst > 0 else None
    alpha = choose_alpha(frame, features)
    X, y, _, _ = _prepare(frame, frame.iloc[:1], features)
    coef = Ridge(alpha=alpha, fit_intercept=False).fit(X, y).coef_
    rng = np.random.default_rng(SEED)
    boots = []
    groups = [g.index.to_numpy() for _, g in frame.groupby("sessao")]
    for _ in range(BOOTSTRAP):
        pick = np.concatenate([rng.choice(g, size=g.size, replace=True) for g in groups])
        sample = frame.loc[pick].reset_index(drop=True)
        Xb, yb, _, _ = _prepare(sample, sample.iloc[:1], features)
        boots.append(Ridge(alpha=alpha, fit_intercept=False).fit(Xb, yb).coef_)
    boots = np.array(boots)
    lo, hi = np.percentile(boots, [5, 95], axis=0)
    out["alfa"] = alpha
    out["alfas_por_rodada"] = alphas
    out["coeficientes"] = sorted([
        {"entrada": f, "s_por_desvio": round(float(c), 4), "intervalo_90": [round(float(a), 4), round(float(b), 4)],
         "sinal_estavel": bool(a > 0 or b < 0)}
        for f, c, a, b in zip(features, coef, lo, hi)], key=lambda d: -abs(d["s_por_desvio"]))
    out["situacao"] = "ajustado"
    return out
