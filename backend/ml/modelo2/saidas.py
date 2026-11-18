"""O E3 nas saidas de traseira relatadas pelo Eduardo em 01/11 (pedido 42, Parte D.6).

E uma revocacao so sobre os casos relatados: a lista nao tem "nao aplica" e nao
da precisao. As voltas sao achadas pelo numero do relato e conferidas pelo tempo
da volta no `session-index.json`; se o numero nao bater, vale o tempo. O portao
do Modelo 2 nao muda: uma volta recusada (rodada, box) e relatada com o motivo, e
o E3 roda so nas passagens citadas. As gravacoes so sao lidas.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from ..data.ai_detector import pit_lap
from ..data.recordings import iter_laps, list_all_sessions
from ..preprocessing.alignment import align_lap
from ..preprocessing.cleaning import clean_lap
from ..preprocessing.quality import evaluate_lap
from ..preprocessing.resampling import lap_time_from_grid, resample_lap
from ..track.geometry import TrackGeometry
from ..track.microsectors import build_microsectors
from .dados import Volta, raw_derived, to_grid
from .detectores import NC, Lap, Ref, measure_passage, state_of
from .fases import CornerPhases

SESSION = "2026-11-01_19-47-03_vhe_interlagos"
TIME_TOLERANCE_S = 0.05
# O relato do Eduardo (pedido 42, contexto, item 7): volta -> (tempo no session-index, curvas).
# "A saida do S do Senna" e a C02, a segunda perna do S (a C01 e a primeira).
REPORTED = (
    (3, 285.743, ("C05", "C06", "C13")),
    (4, 224.219, ("C02", "C06")),
    (10, 145.948, ("C05",)),
    (11, 159.678, ("C01",)),
)


def _index_times(session) -> Dict[int, float]:
    path = session.index_path
    data = json.loads(path.read_text(encoding="utf-8"))
    return {int(v["lap_number"]): float(v["lap_elapsed_max"]) for v in data["laps"].values()}


def find_laps(session) -> List[Dict[str, object]]:
    """Cada volta relatada: pelo numero, conferido pelo tempo; se nao bater, pelo tempo."""
    index = _index_times(session)
    out = []
    for number, time_s, corners in REPORTED:
        by_number = index.get(number)
        if by_number is not None and abs(by_number - time_s) <= TIME_TOLERANCE_S:
            found, how = number, "pelo numero (o tempo confere)"
        else:
            close = [n for n, t in index.items() if abs(t - time_s) <= TIME_TOLERANCE_S]
            found, how = (close[0], "pelo tempo (o numero nao bateu)") if close else (None, "nao encontrada")
        out.append({"volta_relatada": number, "tempo_relatado_s": time_s, "lap_number": found, "como": how,
                    "curvas": list(corners)})
    return out


def run_e3(track: TrackGeometry, phases: Sequence[CornerPhases], refs: Dict[str, Dict[str, Ref]], envelope,
           rodada: int, geometria: Tuple[float, float]) -> Dict[str, object]:
    sessions = {s.session_id: s for s in list_all_sessions()}
    if SESSION not in sessions:
        return {"situacao": f"gravacao {SESSION} nao encontrada", "passagens": []}
    session = sessions[SESSION]
    wanted = find_laps(session)
    cp_by = {cp.curva[:3]: cp for cp in phases}
    sectors = build_microsectors(track)
    passages = []
    raw = list(iter_laps(session))
    picked = []
    for w in wanted:
        def tmax(l):
            v = pd.to_numeric(l.frame["lap_time_s"], errors="coerce") if "lap_time_s" in l.frame else pd.Series(dtype=float)
            return float(v.max()) if v.notna().any() else float("nan")
        match = [l for l in raw if l.lap_number == w["lap_number"] and abs(tmax(l) - w["tempo_relatado_s"]) <= 0.5]
        if not match:
            match = [l for l in raw if abs(tmax(l) - w["tempo_relatado_s"]) <= 0.5]
            if match:
                w["como"] = "pelo tempo das amostras (o numero da gravacao nao bateu)"
        w["lap_id"] = match[0].lap_id if match else None
        if match:
            picked.append((match[0], w))
    for lap, w in picked:
        number = lap.lap_number
        cleaned, _ = clean_lap(lap.frame)
        aligned, alignment = align_lap(cleaned, track)
        quality = evaluate_lap(aligned, track, alignment)
        gate = {"valida": bool(quality.valid), "motivos_portao": list(quality.reasons)}
        try:
            grid = resample_lap(aligned, track, line_clock=True).reset_index(drop=True)
            gate["box"] = bool(pit_lap(grid, sectors))
            derived = to_grid(raw_derived(aligned), track)
            base = grid.drop(columns=[c for c in derived.columns if c in grid.columns and c != "grid_index"])
            grid = pd.concat([base.reset_index(drop=True), derived.drop(columns="grid_index").reset_index(drop=True)], axis=1)
            volta = Volta(lap_id=lap.lap_id, gravacao=SESSION, origem="humano", tempo_s=float(lap_time_from_grid(grid)),
                          grid=grid, sessao="2026-11-01")
            built = Lap.build(volta)
        except Exception as error:  # a volta com rodada ou box pode nao reamostrar
            built = None
            gate["erro_na_grade"] = f"{type(error).__name__}: {error}"
        for code in w["curvas"]:
            cp = cp_by[code]
            entry = {"volta_relatada": w["volta_relatada"], "lap_number": number, "lap_id": lap.lap_id,
                     "como_achada": w["como"], "curva": cp.curva, "portao": gate,
                     "recusada_pelo_portao": (not gate["valida"]) or gate.get("box", False) or built is None}
            if built is None:
                entry.update({"estado_e3": NC, "motivo": "sem a grade da volta", "beta_p95": None})
            else:
                row = measure_passage(built, track, cp, phases[cp.k - 1], envelope, rodada=rodada, geometria=geometria)
                state, why, value = state_of("E3", row, refs.get(cp.curva, {}))
                entry.update({"estado_e3": state, "motivo": why, "valor_regra": value, "beta_p95": row.get("beta_p95")})
            passages.append(entry)
    found = {(p["volta_relatada"], p["curva"][:3]) for p in passages}
    for w in wanted:
        for code in w["curvas"]:
            if (w["volta_relatada"], code) not in found:
                passages.append({"volta_relatada": w["volta_relatada"], "curva": code, "estado_e3": NC,
                                 "motivo": "volta nao encontrada na gravacao", "como_achada": w["como"]})
    aplica = sum(p["estado_e3"] == "aplica" for p in passages)
    return {"sessao": SESSION, "voltas": wanted, "passagens": passages,
            "aplica": aplica, "total": len(passages),
            "recusadas_pelo_portao": sum(bool(p.get("recusada_pelo_portao")) for p in passages),
            "nota": "revocacao so sobre os casos relatados; a lista nao tem nao aplica e nao da precisao"}
