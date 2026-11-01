"""As dimensoes de estilo por tipo de curva (secao 1.7).

Escore-z = (mediana da medida - mediana de todas as passagens rotuladas daquele
tipo de curva) / desvio robusto dessas passagens. A incerteza e o intervalo de
90% da mediana por bootstrap das voltas. A consistencia fica fora do vetor.
"""

from __future__ import annotations

from typing import Dict, List, Sequence

import numpy as np
import pandas as pd

from .detectores import robust_sd

DIMENSIONS = {
    "forma_v_ou_u": ("plato_s", "vmin_sobre_ventrada", "vmin_posicao"),
    "perfil_de_frenagem": ("pico_rel", "pico_fracao", "taxa_soltura"),
    "uso_dos_pedais": ("acelerador_min_antes", "pedais_juntos_s"),
    "resposta_na_entrada": ("guinada_por_roda", "beta_entrada", "contra_s"),
    "aplicacao_do_volante": ("taxa_entrada", "reversoes", "delta_pk"),
    "perfil_do_acelerador": ("apice_ao_pleno_s", "f20_60_saida"),
}
CONSISTENCY = ("s_b_rel", "v_min", "retomada_s")
RESAMPLES = 1000
SEED = 38


def with_relative_peak(passages: pd.DataFrame) -> pd.DataFrame:
    ai_peak = passages[passages["origem"] == "ia"].groupby("curva")["pico_freio"].median()
    out = passages.copy()
    out["pico_rel"] = out["pico_freio"] / out["curva"].map(ai_peak)
    return out


def _median_ci(frame: pd.DataFrame, measure: str, rng: np.random.Generator) -> tuple:
    values = frame[["lap_id", measure]].dropna()
    if values.empty:
        return None, None, None, 0
    by_lap = [g[measure].to_numpy(dtype=float) for _, g in values.groupby("lap_id")]
    median = float(np.median(values[measure]))
    if len(by_lap) < 2:
        return median, None, None, len(values)
    meds = []
    for _ in range(RESAMPLES):
        pick = rng.integers(0, len(by_lap), size=len(by_lap))
        meds.append(np.median(np.concatenate([by_lap[i] for i in pick])))
    lo, hi = np.percentile(meds, [5, 95])
    return median, float(lo), float(hi), len(values)


def signatures(passages: pd.DataFrame, group_cols: Sequence[str]) -> List[Dict[str, object]]:
    """Uma assinatura por (tipo de curva, grupo), com o escore-z e o intervalo de cada medida."""
    rng = np.random.default_rng(SEED)
    out = []
    for tipo, typed in passages.groupby("tipo"):
        pooled = {m: (float(np.nanmedian(typed[m])), robust_sd(typed[m].tolist()))
                  for dims in DIMENSIONS.values() for m in dims if m in typed}
        for key, g in typed.groupby(list(group_cols)):
            key = key if isinstance(key, tuple) else (key,)
            entry = {"tipo": tipo, **dict(zip(group_cols, key)), "passagens": int(len(g)), "voltas": int(g["lap_id"].nunique()),
                     "dimensoes": {}}
            for dim, measures in DIMENSIONS.items():
                block = {}
                for m in measures:
                    if m not in g:
                        continue
                    med, lo, hi, n = _median_ci(g, m, rng)
                    centre, sd = pooled.get(m, (np.nan, np.nan))
                    z = None if med is None or not np.isfinite(sd) or sd <= 0 else (med - centre) / sd
                    zlo = None if lo is None or z is None else (lo - centre) / sd
                    zhi = None if hi is None or z is None else (hi - centre) / sd
                    block[m] = {"mediana": None if med is None else round(med, 4), "n": n,
                                "z": None if z is None else round(z, 2),
                                "z_intervalo_90": None if zlo is None else [round(zlo, 2), round(zhi, 2)]}
                entry["dimensoes"][dim] = block
            cons = {}
            for m in CONSISTENCY:
                per = g.groupby("curva")[m].agg(lambda s: float(np.std(s.dropna(), ddof=1)) if s.notna().sum() >= 3 else np.nan)
                cons[m] = None if per.dropna().empty else round(float(per.dropna().median()), 3)
            entry["consistencia_a_parte"] = cons
            out.append(entry)
    return out
