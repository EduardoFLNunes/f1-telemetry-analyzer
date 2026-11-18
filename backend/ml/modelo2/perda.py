"""A perda por fase, o ranking, a cadeia causal e a atribuicao do erro (secao 1.6).

"Erro" e sempre uma diferenca medida contra uma volta real, com o tempo que
custou (ADR 0012). Um trecho em que o piloto e mais rapido que a IA nao e erro.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from .detectores import APLICA, NAO_APLICA, NC, PHASE_DETECTORS, Lap, phase_time, robust_sd
from .fases import PHASES, CornerPhases
from ..track.geometry import TrackGeometry

LAST = 3
MIN_LOSS_S = 0.02
MIN_REPEATS = 2
LAP_SD_LIMIT_S = 1.0
BRAKE_SD_LIMIT_M = 15.0
CONSISTENCY_MIN_LAPS = 5
LATE_PICKUP_S = 0.20
LOW_VMIN_KMH = -2.0
TOP = 3

# Rodada 2 (pedido 42, secao 4.4): os detectores "de ponto", comparados com a volta do modelo.
POINT_DETECTORS = {"F1": "s_b_rel", "M2": "s_vmin_rel", "M4": "afastamento_m", "M6": "retomada_s"}


def phase_losses(lap: Lap, ref: Lap, track: TrackGeometry, phases: Sequence[CornerPhases]) -> List[Dict[str, object]]:
    """A perda de uma volta em cada uma das 70 fases contra a referencia."""
    out = []
    for cp in phases:
        for phase, (start, end) in cp.bounds().items():
            out.append({"curva": cp.curva, "k": cp.k, "fase": phase,
                        "perda_s": phase_time(lap, track, start, end) - phase_time(ref, track, start, end)})
    return out


def dentro_da_margem(perda_s, com_margem, margem_s: float):
    """Pedido 42 (secao 4.5): numa sessao aceita com margem, |perda| ate a margem nao e perda nem ganho."""
    perda = np.asarray(perda_s, dtype=float)
    return np.asarray(com_margem, dtype=bool) & np.isfinite(perda) & (np.abs(perda) <= margem_s)


def loss_table(laps: Sequence[Lap], ref: Lap, best: Lap, track: TrackGeometry,
               phases: Sequence[CornerPhases], margem_s: float = 0.0) -> pd.DataFrame:
    """A perda de cada volta em cada fase, com a marca da margem das sessoes aceitas com margem (4.5)."""
    rows = []
    for lap in laps:
        vs_ai = phase_losses(lap, ref, track, phases)
        vs_best = phase_losses(lap, best, track, phases)
        flagged = bool(getattr(lap.volta, "com_margem", False))
        for a, b in zip(vs_ai, vs_best):
            rows.append({"lap_id": lap.volta.lap_id, "sessao": lap.volta.sessao, "origem": lap.volta.origem,
                         **a, "perda_vs_melhor_s": b["perda_s"], "sessao_com_margem": flagged})
    out = pd.DataFrame(rows)
    if not out.empty:
        out["dentro_da_margem"] = dentro_da_margem(out["perda_s"], out["sessao_com_margem"], margem_s)
        out["dentro_da_margem_vs_melhor"] = dentro_da_margem(out["perda_vs_melhor_s"], out["sessao_com_margem"], margem_s)
    return out


def majority(states: Sequence[str], minimum: int) -> str:
    conclusive = [s for s in states if s != NC]
    if len(conclusive) < minimum:
        return NC
    yes = sum(s == APLICA for s in conclusive)
    no = len(conclusive) - yes
    return APLICA if yes > no else NAO_APLICA if no > yes else NC


def attribute(curva: str, origin_phases: Sequence[str], last_ids: Sequence[str], best_id: str,
              states: pd.DataFrame, session_ids: Sequence[str]) -> Dict[str, object]:
    """Que detector da fase de origem explica o item (regra de 1.6)."""
    corner = states[states["curva"] == curva]
    detectors = []
    for phase in origin_phases:
        detectors += [d for d in PHASE_DETECTORS[phase] if d not in detectors]
    explaining, never_shown, checked = [], [], []
    for det in detectors:
        d = corner[corner["detector"] == det]
        if d.empty:
            continue
        mine = d[d["lap_id"].isin(last_ids)]
        ai = d[d["origem"] == "ia"]
        best = d[d["lap_id"] == best_id]
        s_mine = majority(mine["estado"].tolist(), 2)
        s_ai = majority(ai["estado"].tolist(), 1)
        s_best = best["estado"].iloc[0] if len(best) else NC
        x_mine = mine["indicador"].dropna()
        x_ai = ai["indicador"].dropna()
        pool = d[d["lap_id"].isin(session_ids)]["indicador"].dropna()
        if len(pool) < 5:
            pool = d[d["origem"] != "ia"]["indicador"].dropna()
        sd = robust_sd(pool.tolist())
        diff = float(x_mine.median() - x_ai.median()) if len(x_mine) and len(x_ai) else None
        z = diff / sd if diff is not None and np.isfinite(sd) and sd > 0 else None
        entry = {"detector": det, "estado_piloto": s_mine, "estado_ia": s_ai, "estado_melhor_volta": s_best,
                 "diferenca": None if diff is None else round(diff, 4), "diferenca_em_desvios": None if z is None else round(z, 2)}
        checked.append(entry)
        if s_mine == NC or s_ai == NC or s_mine == s_ai:
            continue
        if s_best != NC and s_best != s_ai:
            never_shown.append(entry)
            continue
        if z is None or abs(z) <= 1.0:
            continue
        explaining.append(entry)
    explaining.sort(key=lambda e: -abs(e["diferenca_em_desvios"]))
    return {"explica": explaining[0] if explaining else None, "outros_que_explicam": explaining[1:],
            "tecnica_nunca_mostrada": never_shown, "conferidos": checked,
            "conclusao": "explicado" if explaining else "nao_conclusivo"}


def _value(frame: pd.DataFrame, lap_id: str, curva: str, column: str) -> Optional[float]:
    if frame is None or column not in frame:
        return None
    rows = frame[(frame["lap_id"] == lap_id) & (frame["curva"] == curva)]
    if rows.empty:
        return None
    v = rows[column].iloc[0]
    return None if v is None or not np.isfinite(v) else float(v)


def _ref_value(ref_points: pd.DataFrame, curva: str, column: str) -> Optional[float]:
    if ref_points is None or curva not in ref_points.index or column not in ref_points:
        return None
    v = ref_points.at[curva, column]
    return None if v is None or not np.isfinite(v) else float(v)


def attribute_r2(curva: str, origin_phases: Sequence[str], last_ids: Sequence[str], best_id: str,
                 states: pd.DataFrame, passages: pd.DataFrame, ref_points: pd.DataFrame,
                 session_ids: Sequence[str]) -> Dict[str, object]:
    """A atribuicao da rodada 2 (secao 4.4).

    * De ponto (F1, M2, M4 e a parte "atraso" do M6): a mediana do piloto contra o
      mesmo indicador na volta do modelo; explica se a diferenca passa do desvio
      robusto do piloto e a melhor volta fica mais perto da volta do modelo.
    * De forma (os outros): o estado do piloto contra o da "Sua melhor volta",
      nunca contra a volta do modelo.
    """
    corner = states[states["curva"] == curva]
    detectors = []
    for phase in origin_phases:
        detectors += [d for d in PHASE_DETECTORS[phase] if d not in detectors]
    explaining, ai_only, checked = [], [], []
    for det in detectors:
        d = corner[corner["detector"] == det]
        if d.empty:
            continue
        mine = d[d["lap_id"].isin(last_ids)]
        ai = d[d["origem"] == "ia"]
        best = d[d["lap_id"] == best_id]
        s_mine = majority(mine["estado"].tolist(), 2)
        s_ai = majority(ai["estado"].tolist(), 1)
        s_best = best["estado"].iloc[0] if len(best) else NC
        pool = d[d["lap_id"].isin(session_ids)]["indicador"].dropna()
        if len(pool) < 5:
            pool = d[d["origem"] != "ia"]["indicador"].dropna()
        sd = robust_sd(pool.tolist())
        entry = {"detector": det, "estado_piloto": s_mine, "estado_ia": s_ai, "estado_melhor_volta": s_best}
        if det in POINT_DETECTORS:
            column = POINT_DETECTORS[det]
            values = [v for v in (_value(passages, i, curva, column) for i in last_ids) if v is not None]
            ref = _ref_value(ref_points, curva, column)
            best_v = _value(passages, best_id, curva, column)
            diff = float(np.median(values)) - ref if len(values) >= 2 and ref is not None else None
            z = diff / sd if diff is not None and np.isfinite(sd) and sd > 0 else None
            entry.update({"tipo": "ponto", "comparado_com": "volta de referencia", "valor_referencia": ref,
                          "valor_melhor_volta": best_v, "diferenca": None if diff is None else round(diff, 4),
                          "diferenca_em_desvios": None if z is None else round(z, 2)})
            checked.append(entry)
            if z is None or abs(z) <= 1.0:
                continue
            if best_v is None or abs(best_v - ref) >= abs(diff):
                continue
            explaining.append(entry)
            continue
        x_mine = mine["indicador"].dropna()
        x_best = best["indicador"].dropna()
        diff = float(x_mine.median() - x_best.iloc[0]) if len(x_mine) and len(x_best) else None
        z = diff / sd if diff is not None and np.isfinite(sd) and sd > 0 else None
        entry.update({"tipo": "forma", "comparado_com": "sua melhor volta",
                      "diferenca": None if diff is None else round(diff, 4),
                      "diferenca_em_desvios": None if z is None else round(z, 2)})
        checked.append(entry)
        if s_mine != NC and s_ai != NC and s_ai != s_mine and s_best == s_mine:
            ai_only.append(entry)
        if s_mine == NC or s_best == NC or s_mine == s_best:
            continue
        if z is None or abs(z) <= 1.0:
            continue
        explaining.append(entry)
    explaining.sort(key=lambda e: -abs(e["diferenca_em_desvios"]))
    return {"explica": explaining[0] if explaining else None, "outros_que_explicam": explaining[1:],
            "tecnica_da_ia_que_nenhuma_volta_minha_mostra": ai_only, "conferidos": checked,
            "conclusao": "explicado" if explaining else "nao_conclusivo"}


def session_ranking(session: str, laps: Sequence[Lap], losses: pd.DataFrame, passages: pd.DataFrame,
                    states: pd.DataFrame, phases: Sequence[CornerPhases], best_id: str,
                    ai_passages: pd.DataFrame, rodada: int = 1, ref_points: Optional[pd.DataFrame] = None,
                    ref_label: str = "volta da IA do coach") -> Dict[str, object]:
    """Os 3 maiores erros da sessao (1.6; rodada 2, secoes 4.2 e 4.4).

    Na rodada 2, `ref_points` tem, por curva (indice), os pontos da referencia
    (s_b_rel, s_vmin_rel, v_min, retomada_s, afastamento_m), medidos com as regras
    da rodada 2; o falso ganho e a cadeia causal usam esses pontos, a pontuacao e
    a perda sem o peso, e a atribuicao e a da secao 4.4.
    """
    ordered = sorted(laps, key=lambda l: (l.volta.gravacao, int(l.volta.lap_id.split("#")[1])))
    ids = [l.volta.lap_id for l in ordered]
    last = ids[-LAST:]
    times = np.array([l.total for l in ordered])
    out: Dict[str, object] = {"sessao": session, "voltas": len(ids), "ultimas_3": last,
                              "tempos_ultimas_3_s": [round(float(t), 3) for t in times[-LAST:]]}
    if len(last) < LAST:
        out["situacao"] = "poucas voltas: menos de 3 validas"
        out["itens"] = []
        return out
    cp_by = {cp.curva: cp for cp in phases}
    sess = losses[losses["lap_id"].isin(last)].copy()
    # Secao 4.5: dentro da margem, a perda conta como zero (nem perda nem ganho).
    with_margin = bool(sess["sessao_com_margem"].any()) if "sessao_com_margem" in sess else False
    if "dentro_da_margem" in sess:
        sess.loc[sess["dentro_da_margem"].astype(bool), "perda_s"] = 0.0
    if "dentro_da_margem_vs_melhor" in sess:
        sess.loc[sess["dentro_da_margem_vs_melhor"].astype(bool), "perda_vs_melhor_s"] = 0.0
    out["sessao_com_margem"] = with_margin

    # consistencia primeiro
    consistency = None
    lap_sd = float(np.std(times, ddof=1)) if times.size > 1 else 0.0
    brake_sd = {}
    if len(ids) >= CONSISTENCY_MIN_LAPS:
        p = passages[passages["lap_id"].isin(ids)]
        for curva, g in p.groupby("curva"):
            v = g["s_b_rel"].dropna()
            if len(v) >= CONSISTENCY_MIN_LAPS:
                brake_sd[curva] = float(np.std(v, ddof=1))
    worst_brake = max(brake_sd.items(), key=lambda kv: kv[1]) if brake_sd else (None, 0.0)
    if lap_sd > LAP_SD_LIMIT_S or worst_brake[1] > BRAKE_SD_LIMIT_M:
        consistency = {"item": "consistencia", "desvio_volta_s": round(lap_sd, 3),
                       "curva_de_maior_desvio_da_frenagem": worst_brake[0],
                       "desvio_frenagem_m": round(worst_brake[1], 1),
                       "curvas_com_desvio_de_frenagem_acima_de_15_m": sorted(c for c, v in brake_sd.items() if v > BRAKE_SD_LIMIT_M)}

    # medianas por passagem para a cadeia causal
    p_last = passages[passages["lap_id"].isin(last)].set_index(["lap_id", "curva"])
    ai_by = ai_passages.groupby("curva")
    states_last = states[states["lap_id"].isin(last)]

    items = []
    for cp in phases:
        rows = sess[sess["curva"] == cp.curva]
        per_phase = {ph: rows[rows["fase"] == ph].set_index("lap_id").reindex(last) for ph in PHASES}
        # falso ganho
        f1 = states_last[(states_last["curva"] == cp.curva) & (states_last["detector"] == "F1")].set_index("lap_id")
        hits = 0
        ai_sb = ai_by.get_group(cp.curva)["s_b_rel"].dropna() if cp.curva in ai_by.groups else pd.Series(dtype=float)
        sdr_sb = robust_sd(ai_sb.tolist())
        T = max(10.0, 2.0 * sdr_sb) if np.isfinite(sdr_sb) else 10.0
        ref_sb = _ref_value(ref_points, cp.curva, "s_b_rel") if rodada >= 2 else None
        for lap_id in last:
            g_brake = per_phase["frenagem"].at[lap_id, "perda_s"]
            if rodada >= 2:
                mine_sb = _value(passages, lap_id, cp.curva, "s_b_rel")
                d = None if mine_sb is None or ref_sb is None else mine_sb - ref_sb
            else:
                d = f1.at[lap_id, "valor_regra"] if lap_id in f1.index else None
            later = d is not None and np.isfinite(d) and d > T
            entry_mid = per_phase["entrada"].at[lap_id, "perda_s"] + per_phase["meio"].at[lap_id, "perda_s"]
            if g_brake < 0 and later and entry_mid > -g_brake:
                hits += 1
        false_gain = hits >= MIN_REPEATS
        used = set()
        if false_gain:
            net = (per_phase["frenagem"]["perda_s"] + per_phase["entrada"]["perda_s"] + per_phase["meio"]["perda_s"]).to_numpy()
            net_best = (per_phase["frenagem"]["perda_vs_melhor_s"] + per_phase["entrada"]["perda_vs_melhor_s"]
                        + per_phase["meio"]["perda_vs_melhor_s"]).to_numpy()
            items.append(_item(cp, "frenagem+entrada+meio (falso ganho)", net, net_best, ["frenagem"], "frenagem", True,
                               rodada, ref_label))
            used = {"frenagem", "entrada", "meio"}
        for ph in PHASES:
            if ph in used:
                continue
            values = per_phase[ph]["perda_s"].to_numpy()
            if (values >= MIN_LOSS_S).sum() < MIN_REPEATS:
                continue
            origin = [ph]
            origin_label = ph
            if ph in ("saida", "reta"):
                late = []
                low = []
                for lap_id in last:
                    if rodada >= 2:
                        ref_pu = _ref_value(ref_points, cp.curva, "retomada_s")
                        ref_v = _ref_value(ref_points, cp.curva, "v_min")
                        mine_pu = _value(passages, lap_id, cp.curva, "retomada_s")
                        mine_v = _value(passages, lap_id, cp.curva, "v_min")
                        if ref_pu is not None and mine_pu is not None:
                            late.append(mine_pu - ref_pu)
                        if ref_v is not None and mine_v is not None:
                            low.append(mine_v - ref_v)
                        continue
                    if (lap_id, cp.curva) in p_last.index:
                        row = p_last.loc[(lap_id, cp.curva)]
                        ai = ai_by.get_group(cp.curva) if cp.curva in ai_by.groups else None
                        if ai is not None:
                            if row.get("retomada_s") is not None and np.isfinite(row.get("retomada_s", np.nan)):
                                late.append(row["retomada_s"] - ai["retomada_s"].median())
                            if row.get("v_min") is not None:
                                low.append(row["v_min"] - ai["v_min"].median())
                if late and low and np.median(late) > LATE_PICKUP_S and np.median(low) < LOW_VMIN_KMH:
                    origin = ["frenagem", "entrada", "meio"]
                    origin_label = "entrada (cadeia causal)"
            items.append(_item(cp, ph, values, per_phase[ph]["perda_vs_melhor_s"].to_numpy(), origin, origin_label, False,
                               rodada, ref_label))
    for item in items:
        if rodada >= 2:
            item["atribuicao"] = attribute_r2(item["curva"], item["_origem"], last, best_id, states, passages,
                                              ref_points, ids)
        else:
            item["atribuicao"] = attribute(item["curva"], item["_origem"], last, best_id, states, ids)
        del item["_origem"]
    items.sort(key=lambda i: -i["pontuacao"])
    out["consistencia"] = consistency
    top = ([consistency] if consistency else []) + items[: TOP - (1 if consistency else 0)]
    out["itens"] = top
    if rodada >= 2:
        # Secao 4.2: o ranking registrado e sem o peso; o ponderado fica como informativo.
        out["itens_com_peso_informativo"] = sorted(items, key=lambda i: -i["pontuacao_com_peso"])[:TOP]
    else:
        # Informativo, fora da regra registrada: os 3 de maior perda sem o peso da reta seguinte.
        out["itens_sem_peso_informativo"] = sorted(items, key=lambda i: -i["perda_mediana_s"])[:TOP]
    out["todos_os_itens"] = [{k: v for k, v in i.items() if k != "atribuicao"} for i in items]
    return out


def _item(cp: CornerPhases, phase: str, values: np.ndarray, vs_best: np.ndarray, origin: List[str],
          origin_label: str, false_gain: bool, rodada: int = 1, ref_label: str = "volta da IA do coach") -> Dict[str, object]:
    median = float(np.median(values))
    weighted = round(median * cp.peso, 4)
    out = {"item": "perda", "curva": cp.curva, "fase_sintoma": phase, "fase_origem": origin_label,
           "falso_ganho": false_gain, "perda_mediana_s": round(median, 3),
           "perdas_ultimas_3_s": [round(float(v), 3) for v in values],
           "perda_vs_melhor_volta_mediana_s": round(float(np.median(vs_best)), 3),
           "peso": round(cp.peso, 3), "pontuacao": weighted if rodada < 2 else round(median, 4),
           "referencia": ref_label, "_origem": origin}
    if rodada >= 2:
        out["pontuacao_com_peso"] = weighted
    return out
