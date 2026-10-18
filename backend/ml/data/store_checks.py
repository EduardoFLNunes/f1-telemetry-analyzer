"""Checagens do store v2, registradas antes de construir (pedido 16).

`docs/store_v2_e_evolucao.md`, secao 1.3:

* **principal** -- o periodo de s = 0 a s = 0 bate com o cronometro do jogo:
  p99 de |periodo - tempo do jogo| <= 5 ms nas voltas com o fechamento medido,
  com o tempo do jogo levado ao s = 0 desde o pedido 34 (`game_time_at_zero`);
* **a linha do jogo** (pedido 34) -- fica onde foi medida, sessao a sessao;
* nenhuma volta passa pelo box;
* nenhuma volta aparece duas vezes;
* uma geometria so.

E os efeitos esperados contra o store antigo (secao 1.2), que sao relatados
mas nao travam: toda volta e o microsetor 0 sobem ~26 ms, o resto quase nao muda.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..track.geometry import TrackGeometry
from ..track.microsectors import Microsectors, split_times
from .ai_detector import pit_lap
from .lap_store import StoredLaps

PERIOD_LIMIT_MS = 5.0
OVERLAP_LIMIT = 0.5

# Pedido 34: a regua da checagem principal. O periodo vai de s = 0 a s = 0 da
# geometria oficial; o tempo do jogo, de linha do jogo a linha do jogo, e a linha
# do jogo fica uns metros depois do s = 0. A checagem leva o tempo do jogo ao
# s = 0, somando a travessia dessa distancia nas duas pontas da volta:
#
#     tempo do jogo no s = 0 = tempo do jogo + d x (1/v no comeco - 1/v no fim)
#
# A distancia `d` usada e a medida nas proprias gravacoes (`linha_do_jogo_m` de
# cada volta, a mediana de todas). A checagem `linha_do_jogo` confere, sessao a
# sessao, que a medida fica perto da registrada no pedido 33 (1,463 m em 138
# voltas, desvio de 0,067 m por volta); se a geometria oficial ou a linha do jogo
# mudarem, ela reprova com o motivo. A tolerancia de 0,10 m foi fixada antes de
# rodar: as sessoes de jun a out ficam entre 1,425 e 1,505 m, e um erro de 0,10 m
# na distancia move a regua em no maximo 1,5 ms na pior volta vista (127 contra
# 264 km/h nas duas pontas).
GAME_LINE_REGISTERED_M = 1.463
GAME_LINE_TOLERANCE_M = 0.10
GAME_LINE_MIN_LAPS = 3
EXPECTED_SHIFT_MS = (20.0, 35.0)
OTHER_SECTORS_LIMIT_MS = 5.0


def _stats(values: np.ndarray) -> Dict[str, float]:
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return {}
    return {
        "n": int(values.size),
        "min": round(float(values.min()), 2),
        "p1": round(float(np.percentile(values, 1)), 2),
        "mediana": round(float(np.median(values)), 2),
        "p99": round(float(np.percentile(values, 99)), 2),
        "max": round(float(values.max()), 2),
    }


def game_line_m(laps: pd.DataFrame) -> Optional[float]:
    """A distancia medida entre o s = 0 e a linha do jogo: a mediana das voltas, ou None."""
    if "linha_do_jogo_m" not in laps.columns:
        return None
    values = pd.to_numeric(laps["linha_do_jogo_m"], errors="coerce").dropna()
    return float(values.median()) if len(values) else None


def game_time_at_zero(laps: pd.DataFrame, line_m: Optional[float]) -> pd.Series:
    """O tempo do jogo levado ao s = 0 (pedido 34), por volta; NaN onde nao da para levar.

    `tempo do jogo + line_m x (1/v no comeco - 1/v no fim)`, com a velocidade
    gravada nas duas passagens. Sem a distancia ou sem as duas velocidades, NaN.
    """
    game = pd.to_numeric(laps["tempo_jogo_s"], errors="coerce").astype(float)
    if line_m is None or "v_linha_inicio_kmh" not in laps.columns or "v_linha_fim_kmh" not in laps.columns:
        return pd.Series(np.nan, index=laps.index)
    start = pd.to_numeric(laps["v_linha_inicio_kmh"], errors="coerce").astype(float) / 3.6
    end = pd.to_numeric(laps["v_linha_fim_kmh"], errors="coerce").astype(float) / 3.6
    start = start.where(start > 0)
    end = end.where(end > 0)
    return game + line_m * (1.0 / start - 1.0 / end)


def period_differences_ms(laps: pd.DataFrame, line_m: Optional[float] = None) -> pd.Series:
    """Periodo (lap_time_s) menos o tempo do jogo levado ao s = 0, em ms, das voltas medidas.

    Sem `line_m`, a distancia e a medida nas proprias voltas (`game_line_m`).
    """
    line_m = game_line_m(laps) if line_m is None else line_m
    game = game_time_at_zero(laps, line_m)
    measured = game.notna()
    return pd.Series(
        1000.0 * (laps.loc[measured, "lap_time_s"].astype(float) - game[measured]).to_numpy(),
        index=laps.loc[measured, "lap_id"].to_numpy(),
    )


def raw_period_differences_ms(laps: pd.DataFrame) -> pd.Series:
    """A regua de antes do pedido 34: periodo menos o tempo do jogo na linha do jogo, em ms."""
    measured = laps.dropna(subset=["tempo_jogo_s"])
    return pd.Series(
        1000.0 * (measured["lap_time_s"].astype(float) - measured["tempo_jogo_s"].astype(float)).to_numpy(),
        index=measured["lap_id"].to_numpy(),
    )


def check_period(laps: pd.DataFrame, limit_ms: float = PERIOD_LIMIT_MS) -> Dict[str, object]:
    """Checagem principal: p99 de |periodo - tempo do jogo no s = 0| <= `limit_ms`.

    O que ela prova nao mudou no pedido 34: o periodo de uma volta bate com o
    cronometro do jogo. So a regua mudou: o tempo do jogo e levado a mesma linha
    do periodo (`game_time_at_zero`).
    """
    line_m = game_line_m(laps)
    diffs = period_differences_ms(laps, line_m)
    absolute = diffs.abs()
    p99 = float(np.percentile(absolute, 99)) if len(absolute) else float("nan")
    worst = absolute.sort_values(ascending=False).head(5)
    above = absolute[absolute > limit_ms].sort_values(ascending=False)
    without_game = laps["tempo_jogo_s"].isna()
    raw = raw_period_differences_ms(laps).abs()
    return {
        "checagem": "periodo de s = 0 a s = 0 contra o cronometro do jogo, na mesma linha",
        "regua": "tempo do jogo levado ao s = 0: tempo do jogo + linha x (1/v no comeco - 1/v no fim) (pedido 34)",
        "linha_do_jogo_m": round(line_m, 4) if line_m is not None else None,
        "limite_ms": limit_ms,
        "voltas_medidas": int(len(diffs)),
        "voltas_sem_fechamento_medido": int(without_game.sum()),
        "voltas_sem_velocidade_na_linha": int((~without_game).sum() - len(diffs)),
        "diferenca_ms": _stats(diffs.to_numpy()),
        "abs_diferenca_ms": _stats(absolute.to_numpy()),
        "piores": [{"volta": k, "diferenca_ms": round(float(diffs[k]), 2)} for k in worst.index],
        "acima_do_limite": [{"volta": k, "diferenca_ms": round(float(diffs[k]), 2)} for k in above.index],
        "regua_antiga (informativo)": {
            "abs_diferenca_ms": _stats(raw.to_numpy()),
            "acima_do_limite": int((raw > limit_ms).sum()),
        },
        "passou": bool(len(diffs) > 0 and p99 <= limit_ms),
    }


def check_game_line(laps: pd.DataFrame, registered_m: float = GAME_LINE_REGISTERED_M,
                    tolerance_m: float = GAME_LINE_TOLERANCE_M,
                    min_laps: int = GAME_LINE_MIN_LAPS) -> Dict[str, object]:
    """A linha do jogo fica onde foi medida no pedido 33, sessao a sessao (pedido 34).

    Cada sessao com pelo menos `min_laps` voltas medidas tem de ficar a ate
    `tolerance_m` de `registered_m`, e a mediana de todas tambem. Se a geometria
    oficial ou a linha do jogo mudarem, a checagem reprova e diz onde.
    """
    column = laps["linha_do_jogo_m"] if "linha_do_jogo_m" in laps.columns else pd.Series(np.nan, index=laps.index)
    values = pd.to_numeric(column, errors="coerce")
    sessions: Dict[str, Dict[str, object]] = {}
    reasons: List[str] = []
    for session_id, group in values.groupby(laps["session_id"]):
        measured = group.dropna()
        entry: Dict[str, object] = {"voltas_medidas": int(len(measured))}
        if len(measured) >= min_laps:
            median = float(measured.median())
            inside = abs(median - registered_m) <= tolerance_m
            entry.update({"mediana_m": round(median, 3), "desvio_m": round(float(measured.std(ddof=0)), 3),
                          "dentro": bool(inside)})
            if not inside:
                reasons.append(f"{session_id}: a linha do jogo ficou a {median:.3f} m do s = 0, e a registrada e "
                               f"{registered_m:.3f} m (tolerancia {tolerance_m:.2f} m): a geometria oficial ou a "
                               f"linha do jogo mudaram")
        else:
            entry["dentro"] = None                      # poucas voltas medidas: sem veredito
        sessions[str(session_id)] = entry
    pooled = game_line_m(laps)
    if pooled is None:
        reasons.append("nenhuma volta tem a medida da linha do jogo")
    elif abs(pooled - registered_m) > tolerance_m:
        reasons.append(f"a mediana de todas as voltas ficou a {pooled:.3f} m do s = 0, e a registrada e "
                       f"{registered_m:.3f} m (tolerancia {tolerance_m:.2f} m)")
    return {
        "checagem": "a linha do jogo fica onde foi medida (pedido 34)",
        "registrada_m": registered_m,
        "tolerancia_m": tolerance_m,
        "medida_m": round(pooled, 4) if pooled is not None else None,
        "voltas_medidas": int(values.notna().sum()),
        "sessoes": sessions,
        "sessoes_sem_veredito": sorted(k for k, v in sessions.items() if v["dentro"] is None),
        "motivos": reasons,
        "passou": not reasons,
    }


def check_no_box(store: StoredLaps, sectors: Microsectors) -> Dict[str, object]:
    flagged = [lap_id for lap_id in store.lap_ids if pit_lap(store.lap(lap_id), sectors)]
    return {"checagem": "nenhuma volta passa pelo box", "voltas_com_box": flagged, "passou": not flagged}


def overlapping_pairs(laps: pd.DataFrame, limit: float = OVERLAP_LIMIT) -> List[Dict[str, object]]:
    """Pares de voltas de sessoes diferentes com mais de `limit` do intervalo em comum."""
    rows = laps.dropna(subset=["inicio_epoch_s", "fim_epoch_s"]).sort_values("inicio_epoch_s")
    start = rows["inicio_epoch_s"].to_numpy(dtype=float)
    end = rows["fim_epoch_s"].to_numpy(dtype=float)
    ids = rows["lap_id"].to_numpy()
    sessions = rows["session_id"].to_numpy()
    folders = rows["pasta"].to_numpy() if "pasta" in rows else np.array([None] * len(rows))
    out = []
    for i in range(len(rows)):
        j = i + 1
        while j < len(rows) and start[j] < end[i]:
            if sessions[i] != sessions[j]:
                overlap = min(end[i], end[j]) - max(start[i], start[j])
                shorter = min(end[i] - start[i], end[j] - start[j])
                if shorter > 0 and overlap / shorter > limit:
                    out.append({"a": ids[i], "b": ids[j], "pastas_diferentes": bool(folders[i] != folders[j]),
                                "fracao_em_comum": round(float(overlap / shorter), 3)})
            j += 1
    return out


def check_no_duplicates(laps: pd.DataFrame) -> Dict[str, object]:
    repeated = laps["lap_id"][laps["lap_id"].duplicated()].tolist()
    marked = laps["lap_id"][laps["duplicada_de"].notna()].tolist() if "duplicada_de" in laps else []
    pairs = overlapping_pairs(laps)
    across = [p for p in pairs if p["pastas_diferentes"]]
    return {
        "checagem": "nenhuma volta aparece duas vezes",
        "lap_id_repetido": repeated,
        "com_duplicada_de": marked,
        "pares_de_pastas_diferentes_sobrepostos": across,
        "pares_da_mesma_pasta_sobrepostos (informativo)": [p for p in pairs if not p["pastas_diferentes"]],
        "passou": not repeated and not marked and not across,
    }


def check_single_geometry(laps: pd.DataFrame, track: TrackGeometry) -> Dict[str, object]:
    ids = sorted(laps["geometry_id"].dropna().astype(str).unique())
    return {
        "checagem": "uma geometria so",
        "geometry_ids": ids,
        "geometria_carregada": track.geometry_id,
        "passou": ids == [track.geometry_id],
    }


def expected_effects(new: StoredLaps, old: StoredLaps, sectors: Microsectors, track: TrackGeometry) -> Dict[str, object]:
    """Contra o store antigo, nas voltas dos dois: volta e microsetor 0 (~ +26 ms) e o resto."""
    common = sorted(set(new.lap_ids) & set(old.lap_ids))
    new_laps = new.laps.set_index("lap_id")
    old_laps = old.laps.set_index("lap_id")
    lap_ms, first_ms, others = [], [], []
    for lap_id in common:
        a_total, b_total = float(old_laps.at[lap_id, "lap_time_s"]), float(new_laps.at[lap_id, "lap_time_s"])
        a = split_times(old.lap(lap_id)["elapsed_s"].to_numpy(dtype=float), sectors, track, total=a_total)
        b = split_times(new.lap(lap_id)["elapsed_s"].to_numpy(dtype=float), sectors, track, total=b_total)
        lap_ms.append(1000.0 * (b_total - a_total))
        first_ms.append(1000.0 * (b[0] - a[0]))
        others.append(np.abs(1000.0 * (b[1:] - a[1:])))
    other_values = np.concatenate(others) if others else np.array([])
    lap_stats, first_stats = _stats(np.array(lap_ms)), _stats(np.array(first_ms))
    low, high = EXPECTED_SHIFT_MS
    return {
        "voltas_nos_dois_stores": len(common),
        "voltas_so_no_antigo": len(set(old.lap_ids) - set(new.lap_ids)),
        "volta_v2_menos_antigo_ms": lap_stats,
        "microsetor_0_v2_menos_antigo_ms": first_stats,
        "outros_microsetores_abs_ms": _stats(other_values),
        "como_esperado": bool(
            common
            and low <= lap_stats["mediana"] <= high
            and low <= first_stats["mediana"] <= high
            and float(np.percentile(other_values, 99)) < OTHER_SECTORS_LIMIT_MS
        ),
    }


def control_old_period(old: StoredLaps, new_laps: pd.DataFrame) -> Dict[str, object]:
    """Controle: a checagem principal aplicada ao store antigo (espera-se ~ -26 ms).

    Com a mesma regua da checagem: o tempo do jogo levado ao s = 0 (pedido 34).
    """
    game = pd.Series(game_time_at_zero(new_laps, game_line_m(new_laps)).to_numpy(),
                     index=new_laps["lap_id"].to_numpy()).dropna()
    old_laps = old.laps.set_index("lap_id")
    common = [i for i in old_laps.index if i in game.index]
    diffs = np.array([1000.0 * (float(old_laps.at[i, "lap_time_s"]) - float(game[i])) for i in common])
    return {
        "controle": "store antigo contra o mesmo cronometro do jogo",
        "voltas": len(common),
        "diferenca_ms": _stats(diffs),
        "passaria": bool(diffs.size and float(np.percentile(np.abs(diffs), 99)) <= PERIOD_LIMIT_MS),
    }


def run_checks(store: StoredLaps, track: TrackGeometry, sectors: Microsectors,
               old: Optional[StoredLaps] = None) -> Dict[str, object]:
    laps = store.laps
    checks = {
        "principal_periodo": check_period(laps),
        "linha_do_jogo": check_game_line(laps),
        "sem_box": check_no_box(store, sectors),
        "sem_duplicatas": check_no_duplicates(laps),
        "uma_geometria": check_single_geometry(laps, track),
    }
    out: Dict[str, object] = {
        "checagens": checks,
        "todas_passaram": all(c["passou"] for c in checks.values()),
        "principal_passou": checks["principal_periodo"]["passou"],
    }
    if old is not None:
        out["efeitos_esperados"] = expected_effects(store, old, sectors, track)
        out["controle_store_antigo"] = control_old_period(old, laps)
    return out


def counts_by(laps: pd.DataFrame) -> Dict[str, object]:
    """Voltas por origem, equipamento e pasta (e combinadas)."""
    out: Dict[str, object] = {"voltas": int(len(laps))}
    for column in ("origem", "equipamento", "pasta"):
        out[f"por_{column}"] = {str(k): int(v) for k, v in laps[column].fillna("-").value_counts().items()}
    combo = laps.groupby([laps["origem"].fillna("-"), laps["equipamento"].fillna("-"), laps["pasta"].fillna("-")]).size()
    out["por_origem_equipamento_pasta"] = {" / ".join(map(str, k)): int(v) for k, v in combo.items()}
    return out
