"""A rodada 1 refeita contra a guardada (Parte 0.6) e a rodada 2 ao lado da rodada 1 (Parte D.4 e C).

Tudo aqui so le as saidas das rodadas (`data/ml/modelo2/` e as pastas de cada
rodada); nada e recalculado nas voltas.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .detectores import APLICA, NC

TOL = 1e-6


def _json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _estados(folder: Path) -> pd.DataFrame:
    frame = pd.DataFrame(_json(folder / "tecnicas.json")["estados"])
    return frame[frame["curva"] != "volta"]


def conferir_rodada1(original: Path, refeita: Path) -> Dict[str, object]:
    """A rodada 1 refeita reproduz a guardada? (Parte 0.6)"""
    out: Dict[str, object] = {"original": str(original), "refeita": str(refeita)}
    a = pd.read_parquet(original / "passagens.parquet").set_index(["lap_id", "curva"]).sort_index()
    b = pd.read_parquet(refeita / "passagens.parquet").set_index(["lap_id", "curva"]).sort_index()
    out["passagens"] = {"original": len(a), "refeita": len(b),
                        "so_na_original": len(a.index.difference(b.index)), "so_na_refeita": len(b.index.difference(a.index))}
    common = a.index.intersection(b.index)
    diffs = {}
    for column in sorted(set(a.columns) & set(b.columns)):
        x, y = a.loc[common, column], b.loc[common, column]
        if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y) and not pd.api.types.is_bool_dtype(x):
            xv, yv = x.to_numpy(dtype=float), y.to_numpy(dtype=float)
            both_nan = np.isnan(xv) & np.isnan(yv)
            bad = ~both_nan & ~(np.abs(xv - yv) <= TOL * np.maximum(1.0, np.abs(xv)))
        else:
            bad = ~((x.astype(str) == y.astype(str)).to_numpy())
        if bad.any():
            diffs[column] = int(bad.sum())
    out["colunas_diferentes"] = diffs
    out["colunas_novas_na_refeita"] = sorted(set(b.columns) - set(a.columns))
    sa, sb = _estados(original), _estados(refeita)
    m = sa.merge(sb, on=["lap_id", "curva", "detector"], how="outer", suffixes=("_o", "_r"), indicator=True)
    out["estados"] = {"original": len(sa), "refeita": len(sb), "sem_par": int((m["_merge"] != "both").sum()),
                      "estado_diferente": int(((m["_merge"] == "both") & (m["estado_o"] != m["estado_r"])).sum())}
    fa, fb = _json(original / "fases.json"), _json(refeita / "fases.json")
    keys = ("b", "a", "m1", "apice", "m2", "e", "b_seguinte", "tipo", "sem_frenagem")
    out["fases_iguais"] = all(
        all((abs(x[k] - y[k]) <= TOL) if isinstance(x[k], float) else x[k] == y[k] for k in keys)
        for x, y in zip(fa["curvas"], fb["curvas"])) and len(fa["curvas"]) == len(fb["curvas"])
    ea, eb = _json(original / "erros_por_sessao.json"), _json(refeita / "erros_por_sessao.json")
    def top(e):
        return {s["sessao"]: [(i.get("item"), i.get("curva"), i.get("fase_sintoma"), i.get("perda_mediana_s"))
                              for i in s.get("itens", [])] for s in e["sessoes"]}
    ta, tb = top(ea), top(eb)
    out["ranking"] = {"sessoes": len(ta), "sessoes_iguais": sum(ta.get(k) == tb.get(k) for k in ta),
                      "diferentes": sorted(k for k in set(ta) | set(tb) if ta.get(k) != tb.get(k))}
    out["fechamento"] = {"original": ea["fechamento_soma_das_fases_s"], "refeita": eb["fechamento_soma_das_fases_s"]}
    la, lb = _json(original / "modelo_leve.json"), _json(refeita / "modelo_leve.json")
    key = "r2_deixando_uma_sessao_de_fora"
    out["modelo_leve_r2_iguais"] = all(
        (x.get(key) == y.get(key)) or (x.get(key) is not None and y.get(key) is not None and abs(x[key] - y[key]) <= 1e-3)
        for x, y in zip(la, lb))
    out["reproduz"] = (not diffs and out["passagens"]["so_na_original"] == 0 and out["passagens"]["so_na_refeita"] == 0
                       and out["estados"]["sem_par"] == 0 and out["estados"]["estado_diferente"] == 0
                       and out["fases_iguais"] and not out["ranking"]["diferentes"] and out["modelo_leve_r2_iguais"])
    return out


def _fractions(states: pd.DataFrame, detector: str) -> pd.DataFrame:
    d = states[states["detector"] == detector].copy()
    d["quem"] = np.where(d["origem"] == "ia", "ia", "piloto")
    rows = []
    for (curva, quem), g in d.groupby(["curva", "quem"]):
        c = g[g["estado"] != NC]
        rows.append({"curva": curva, "quem": quem, "passagens": len(g), "conclusivas": len(c),
                     "fracao_aplica": None if c.empty else round(float((c["estado"] == APLICA).mean()), 3)})
    return pd.DataFrame(rows)


def _side(r1: pd.DataFrame, r2: pd.DataFrame, detector: str) -> List[Dict[str, object]]:
    a, b = _fractions(r1, detector), _fractions(r2, detector)
    m = a.merge(b, on=["curva", "quem"], how="outer", suffixes=("_r1", "_r2"))
    return json.loads(m.sort_values(["curva", "quem"]).to_json(orient="records"))


def _top3(e: Dict[str, object]) -> Dict[str, List[str]]:
    out = {}
    for s in e["sessoes"]:
        items = []
        for i in s.get("itens", []):
            if i.get("item") == "consistencia":
                items.append("consistencia")
            else:
                items.append(f'{i["curva"]} {i["fase_sintoma"]} ({i["perda_mediana_s"]:+.3f} s)')
        out[s["sessao"]] = items
    return out


def _keys(items: List[str]) -> set:
    return {i.split(" (")[0] for i in items}


def comparar(r1_dir: Path, r1_refeita: Path, r2_dir: Path) -> Dict[str, object]:
    """A rodada 2 ao lado da rodada 1 (Parte D.4) e o E2 antes e depois (Parte C)."""
    s1, s2 = _estados(r1_dir), _estados(r2_dir)
    p1 = pd.read_parquet(r1_refeita / "passagens.parquet").set_index(["lap_id", "curva"])
    p2 = pd.read_parquet(r2_dir / "passagens.parquet").set_index(["lap_id", "curva"])
    out: Dict[str, object] = {}

    e1, e2 = _json(r1_dir / "erros_por_sessao.json"), _json(r2_dir / "erros_por_sessao.json")
    c2 = _json(r2_dir / "erros_por_sessao_so_comparacao_0013.json")
    t1, t2, t0 = _top3(e1), _top3(e2), _top3(c2)
    sessions = []
    for k in sorted(set(t1) | set(t2)):
        a, b, c = t1.get(k, []), t2.get(k, []), t0.get(k, [])
        sessions.append({"sessao": k, "rodada1": a, "rodada2_volta_do_modelo": b, "rodada2_so_comparacao_0013": c,
                         "entrou": sorted(_keys(b) - _keys(a)), "saiu": sorted(_keys(a) - _keys(b))})
    out["tres_maiores_por_sessao"] = sessions
    out["referencias"] = {"rodada1": e1["referencia"], "rodada2": {k: v for k, v in e2["referencia"].items()
                                                                  if k != "pontos_da_volta_de_referencia"}}

    out["M6_M7_M8"] = {d: _side(s1, s2, d) for d in ("M6", "M7", "M8")}
    out["E1_F5"] = {d: _side(s1, s2, d) for d in ("E1", "F5")}
    out["E2_antes_e_depois"] = _side(s1, s2, "E2")
    out["E4"] = {"por_curva": _side(s1, s2, "E4")}
    m = s1[s1["detector"] == "E4"].merge(s2[s2["detector"] == "E4"], on=["lap_id", "curva"], suffixes=("_r1", "_r2"))
    gained = m[(m["estado_r2"] == APLICA) & (m["estado_r1"] != APLICA)]
    before = p2["contra_antes_apice_s"].reindex(list(zip(gained["lap_id"], gained["curva"]))) if "contra_antes_apice_s" in p2 else None
    before1 = p1["contra_antes_apice_s"].reindex(list(zip(gained["lap_id"], gained["curva"]))) if "contra_antes_apice_s" in p1 else None
    out["E4"]["ganharam_aplica"] = int(len(gained))
    out["E4"]["ganharam_com_contraesterco_antes_do_apice"] = (
        None if before is None else int(((before.to_numpy() >= 0.10) & ~(np.nan_to_num(before1.to_numpy()) >= 0.10)).sum()))
    out["E4"]["por_origem"] = gained.assign(quem=np.where(gained["origem_r1"] == "ia", "ia", "piloto"))["quem"].value_counts().to_dict()

    both = p1.index.intersection(p2.index)
    move = (p2.loc[both, "s_ti_rel"] - p1.loc[both, "s_ti_rel"]).dropna()
    rows = []
    for curva, g in move.groupby(level="curva"):
        rows.append({"curva": curva, "passagens": int(len(g)), "mudaram": int((g.abs() > 1e-9).sum()),
                     "mediana_m": round(float(g.median()), 2), "p10_m": round(float(g.quantile(0.1)), 2),
                     "p90_m": round(float(g.quantile(0.9)), 2)})
    out["entrada_moveu"] = rows
    pu = (p2.loc[both, "retomada_s"] - p1.loc[both, "retomada_s"]).dropna()
    out["retomada_moveu_s"] = [{"curva": c, "mediana_s": round(float(g.median()), 3), "p10_s": round(float(g.quantile(0.1)), 3),
                                "p90_s": round(float(g.quantile(0.9)), 3)} for c, g in pu.groupby(level="curva")]
    changes = {}
    for d in ("E1", "F5", "M6", "M7", "M8", "E4", "E2"):
        mm = s1[s1["detector"] == d].merge(s2[s2["detector"] == d], on=["lap_id", "curva"], suffixes=("_r1", "_r2"))
        changes[d] = {"passagens": int(len(mm)), "estado_mudou": int((mm["estado_r1"] != mm["estado_r2"]).sum())}
    out["estados_que_mudaram"] = changes

    ml1, ml2 = _json(r1_dir / "modelo_leve.json"), _json(r2_dir / "modelo_leve.json")
    def stable(m):
        return sorted(c["entrada"] for c in m.get("coeficientes") or [] if c.get("sinal_estavel"))
    out["modelo_leve"] = [{"curva": a["curva"], "r2_fora_r1": a.get("r2_deixando_uma_sessao_de_fora"),
                           "r2_fora_r2": b.get("r2_deixando_uma_sessao_de_fora"),
                           "estaveis_r1": stable(a), "estaveis_r2": stable(b)} for a, b in zip(ml1, ml2)]

    em = p2["freio_emendado"].groupby(level="curva").sum() if "freio_emendado" in p2 else pd.Series(dtype=int)
    out["frenagem_emendada_por_curva"] = {k: int(v) for k, v in em.items()}
    out["conferencia_das_fases"] = {"rodada1_fechamento_s": e1["fechamento_soma_das_fases_s"],
                                    "rodada2_fechamento_s": e2["fechamento_soma_das_fases_s"],
                                    "rodada2_so_comparacao_0013_fechamento_s": c2["fechamento_soma_das_fases_s"],
                                    "metros_cobertos_r2": _json(r2_dir / "fases.json")["metros_cobertos"]}
    out["e3_saidas_de_traseira"] = {"rodada1": _json(r1_refeita / "e3_saidas_de_traseira.json"),
                                    "rodada2": _json(r2_dir / "e3_saidas_de_traseira.json")}
    path = r2_dir / "erros_depois_do_kit.json"
    if path.exists():
        after = _json(path)
        out["depois_do_kit"] = {"voltas": after["voltas"], "fora_da_selecao": after["fora_da_selecao"],
                                "fechamento_s": after["fechamento_soma_das_fases_s"],
                                "tres_maiores_por_sessao": _top3(after),
                                "sessao_com_margem": {s["sessao"]: s.get("sessao_com_margem") for s in after["sessoes"]}}
    return out


AFFECTED = ("C01", "C04", "C07", "C12", "C14")
ENTRY_DETECTORS = ("E1", "F5", "E5", "E6")
ENTRY_MEASURES = ("s_ti_rel", "taxa_entrada", "guinada_por_roda", "beta_entrada")


def comparar_r3(r1_refeita: Path, r2_dir: Path, r3_dir: Path) -> Dict[str, object]:
    """A rodada 3 (a emenda da entrada, secao 5) ao lado da rodada 2."""
    s2, s3 = _estados(r2_dir), _estados(r3_dir)
    p1 = pd.read_parquet(r1_refeita / "passagens.parquet").set_index(["lap_id", "curva"])
    p2 = pd.read_parquet(r2_dir / "passagens.parquet").set_index(["lap_id", "curva"])
    p3 = pd.read_parquet(r3_dir / "passagens.parquet").set_index(["lap_id", "curva"])
    both = p1.index.intersection(p2.index).intersection(p3.index)
    out: Dict[str, object] = {}

    rows = []
    for curva in sorted({c for _, c in both}):
        idx = [i for i in both if i[1] == curva]
        d2 = (p2.loc[idx, "s_ti_rel"] - p1.loc[idx, "s_ti_rel"]).dropna()
        d3 = (p3.loc[idx, "s_ti_rel"] - p1.loc[idx, "s_ti_rel"]).dropna()
        d32 = (p3.loc[idx, "s_ti_rel"] - p2.loc[idx, "s_ti_rel"]).dropna()

        def q(x, p):
            return None if x.empty else round(float(x.quantile(p)), 1)
        rows.append({"curva": curva, "passagens": len(idx),
                     "recuo_r2_mediana_m": q(d2, 0.5), "recuo_r2_p10_m": q(d2, 0.1), "recuo_r2_p90_m": q(d2, 0.9),
                     "recuo_r3_mediana_m": q(d3, 0.5), "recuo_r3_p10_m": q(d3, 0.1), "recuo_r3_p90_m": q(d3, 0.9),
                     "mudaram_de_r2_para_r3": int((d32.abs() > 1e-9).sum()),
                     "voltaram_a_rodada1": int(((d3.abs() <= 1e-9) & (d2.abs() > 1e-9)).sum())})
    out["recuo_da_entrada"] = rows

    def side(det):
        a, b = _fractions(s2, det), _fractions(s3, det)
        m = a.merge(b, on=["curva", "quem"], how="outer", suffixes=("_r2", "_r3"))
        return json.loads(m.sort_values(["curva", "quem"]).to_json(orient="records"))
    out["cinco_curvas"] = {d: [r for r in side(d) if r["curva"][:3] in AFFECTED] for d in ENTRY_DETECTORS}
    out["por_curva"] = {d: side(d) for d in ENTRY_DETECTORS + ("E4",)}
    medidas = []
    for curva in sorted({c for _, c in both if c[:3] in AFFECTED}):
        idx = [i for i in both if i[1] == curva]
        row = {"curva": curva}
        for m in ENTRY_MEASURES[1:]:
            for tag, frame in (("r2", p2), ("r3", p3)):
                v = frame.loc[idx, m].dropna() if m in frame else pd.Series(dtype=float)
                row[f"{m}_{tag}"] = None if v.empty else round(float(v.median()), 4)
        medidas.append(row)
    out["cinco_curvas_medidas_da_entrada"] = medidas

    m = s2.merge(s3, on=["lap_id", "curva", "detector"], suffixes=("_r2", "_r3"))
    m["code"] = m["curva"].str[:3]
    changed = m[m["estado_r2"] != m["estado_r3"]]
    out["estados_que_mudaram"] = {
        "cinco_curvas": changed[changed["code"].isin(AFFECTED)].groupby("detector").size().to_dict(),
        "outras_nove": changed[~changed["code"].isin(AFFECTED)].groupby(["curva", "detector"]).size().reset_index(name="n").to_dict("records"),
        "total": int(len(changed))}
    other = [r for r in rows if r["curva"][:3] not in AFFECTED]
    out["outras_nove_entrada_mudou"] = [{"curva": r["curva"], "mudaram_de_r2_para_r3": r["mudaram_de_r2_para_r3"]}
                                        for r in other if r["mudaram_de_r2_para_r3"]]

    def dims(folder):
        e = _json(folder / "estilo.json")["total"]
        return {(x["tipo"], x["quem"]): {d: {k: v.get("z") for k, v in x["dimensoes"].get(d, {}).items()}
                                         for d in ("resposta_na_entrada", "aplicacao_do_volante")} for x in e}
    e2, e3 = dims(r2_dir), dims(r3_dir)
    out["estilo_da_entrada"] = [{"tipo": k[0], "quem": k[1], "rodada2": e2[k], "rodada3": e3.get(k)} for k in sorted(e2)]

    ml2, ml3 = _json(r2_dir / "modelo_leve.json"), _json(r3_dir / "modelo_leve.json")
    out["modelo_leve"] = [{"curva": a["curva"], "r2_fora_r2": a.get("r2_deixando_uma_sessao_de_fora"),
                           "r2_fora_r3": b.get("r2_deixando_uma_sessao_de_fora")} for a, b in zip(ml2, ml3)]
    e2r, e3r = _json(r2_dir / "erros_por_sessao.json"), _json(r3_dir / "erros_por_sessao.json")
    t2, t3 = _top3(e2r), _top3(e3r)
    out["tres_maiores_por_sessao"] = [{"sessao": k, "rodada2": t2.get(k), "rodada3": t3.get(k),
                                       "mudou": t2.get(k) != t3.get(k)} for k in sorted(set(t2) | set(t3))]
    out["fechamento"] = {"rodada2_s": e2r["fechamento_soma_das_fases_s"], "rodada3_s": e3r["fechamento_soma_das_fases_s"],
                         "metros_cobertos_r3": _json(r3_dir / "fases.json")["metros_cobertos"]}
    return out
