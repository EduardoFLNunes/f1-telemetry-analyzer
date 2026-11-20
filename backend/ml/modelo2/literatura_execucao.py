"""Quem chama os rotulos da literatura (pedido 42, atualizacao de 20/11; secao 7.2).

Corta os tracos de cada passagem na grade, com os marcos geometricos da curva, e
passa ao modulo `rotulos_literatura` so isso. Do gabarito do kit do 38, le so o
endereco de cada passagem (id, pergunta, volta e curva), sem o estado nem a
origem. Nao importa os detectores.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from ..data.recordings import iter_laps, list_all_sessions
from ..preprocessing.alignment import align_lap
from ..preprocessing.cleaning import clean_lap
from ..preprocessing.resampling import lap_time_from_grid, resample_lap
from ..track.geometry import TrackGeometry
from . import rotulos_literatura as RL
from .dados import Volta, raw_derived, to_grid
from .fases import ahead, window

CANAIS = ("brake", "throttle", "yaw_rate", "velocity_long", "velocity_lat", "lateral_g", "speed_kmh")
SAIDAS_0111 = "2026-11-01_19-47-03_vhe_interlagos"
RELATO_0111 = ((3, 285.743, ("C05", "C06", "C13")), (4, 224.219, ("C02", "C06")),
               (10, 145.948, ("C05",)), (11, 159.678, ("C01",)))


def _col(grid: pd.DataFrame, name: str) -> Optional[np.ndarray]:
    if name not in grid.columns:
        return None
    v = pd.to_numeric(grid[name], errors="coerce").to_numpy(dtype=float)
    return v if np.isfinite(v).any() else None


def _steer(grid: pd.DataFrame) -> Optional[np.ndarray]:
    s = _col(grid, "steer_angle")
    return s if s is not None else _col(grid, "steering")


def _dt(grid: pd.DataFrame, total: float) -> np.ndarray:
    el = _col(grid, "elapsed_s")
    dt = np.append(np.diff(el), total - el[-1] + el[0])
    return np.where(np.isfinite(dt) & (dt >= 0), dt, 0.0)


def janela(volta: Volta, track: TrackGeometry, cp: Dict[str, object], prev: Dict[str, object]) -> RL.Janela:
    """Do apice anterior ate 100 m depois do fim da curva, como no kit."""
    start, end = float(prev["apice"]), float(np.mod(cp["e"] + 100.0, track.length))
    idx = window(track, start, end)
    g = volta.grid
    dt = _dt(g, float(volta.tempo_s))
    t = np.concatenate([[0.0], np.cumsum(dt[idx[:-1]])])

    def off(s):
        return int(min(round(ahead(track, start, s) / track.step), idx.size - 1))
    marcos = {"a": off(cp["a"]), "apice": off(cp["apice"]), "m1": off(cp["m1"]), "m2": off(cp["m2"]),
              "e": off(cp["e"]), "e60": off(np.mod(cp["e"] + RL.E3_DEPOIS_DO_FIM_M, track.length))}
    canais = {n: (None if _col(g, n) is None else _col(g, n)[idx]) for n in CANAIS}
    st = _steer(g)
    canais["steer"] = None if st is None else st[idx]
    return RL.Janela(canais=canais, t=t, marcos=marcos, direcao=int(cp["direcao"]), passo_m=track.step)


def referencia(voltas_do_piloto: Sequence[Volta], L: float, k: float) -> RL.ReferenciaDoCarro:
    arrays = [{"steer": _steer(v.grid), "lateral_g": _col(v.grid, "lateral_g"), "speed_kmh": _col(v.grid, "speed_kmh")}
              for v in voltas_do_piloto]
    return RL.referencia_do_carro(arrays, L, k)


def _grade_da_gravacao(lap, track: TrackGeometry) -> Volta:
    cleaned, _ = clean_lap(lap.frame)
    aligned, _ = align_lap(cleaned, track)
    grid = resample_lap(aligned, track, line_clock=True).reset_index(drop=True)
    derived = to_grid(raw_derived(aligned), track)
    base = grid.drop(columns=[c for c in derived.columns if c in grid.columns and c != "grid_index"])
    grid = pd.concat([base.reset_index(drop=True), derived.drop(columns="grid_index").reset_index(drop=True)], axis=1)
    return Volta(lap_id=lap.lap_id, gravacao=lap.session_id, origem="humano", tempo_s=float(lap_time_from_grid(grid)),
                 grid=grid, sessao="2026-11-01")


def e3_nas_saidas(track: TrackGeometry, fases: List[Dict[str, object]], ref: RL.ReferenciaDoCarro) -> List[Dict[str, object]]:
    """O E3 da literatura nas 7 saidas de traseira de 01/11 (as voltas achadas pelo numero e pelo tempo)."""
    sessions = {s.session_id: s for s in list_all_sessions()}
    raw = list(iter_laps(sessions[SAIDAS_0111]))
    by_code = {f["curva"][:3]: (f, fases[k - 1]) for k, f in enumerate(fases)}
    out = []
    for number, time_s, codes in RELATO_0111:
        def tmax(l):
            v = pd.to_numeric(l.frame["lap_time_s"], errors="coerce")
            return float(v.max()) if v.notna().any() else float("nan")
        match = [l for l in raw if l.lap_number == number and abs(tmax(l) - time_s) <= 0.5] \
            or [l for l in raw if abs(tmax(l) - time_s) <= 0.5]
        if not match:
            out += [{"volta_relatada": number, "curva": c, "rotulo": RL.NAO_SEI, "criterio": "volta nao encontrada"} for c in codes]
            continue
        volta = _grade_da_gravacao(match[0], track)
        for code in codes:
            cp, prev = by_code[code]
            r = RL.rotulo_e3(janela(volta, track, cp, prev), ref)
            out.append({"volta_relatada": number, "lap_id": volta.lap_id, "curva": cp["curva"], **r})
    return out


def enderecos_do_kit(key_38: Path) -> List[Dict[str, str]]:
    """Do gabarito do kit do 38, so o endereco: o id, a pergunta, a volta e a curva (nem o estado nem a origem)."""
    key = json.loads(Path(key_38).read_text(encoding="utf-8"))
    return [{"id": k["id"], "pergunta": k["detector"], "lap_id": k["lap_id"], "curva": k["curva"]} for k in key]


def rotular_o_kit(enderecos: List[Dict[str, str]], voltas: Dict[str, Volta], track: TrackGeometry,
                  fases: List[Dict[str, object]], ref: RL.ReferenciaDoCarro) -> List[Dict[str, object]]:
    by_name = {f["curva"]: (f, fases[k - 1]) for k, f in enumerate(fases)}
    out = []
    for e in enderecos:
        cp, prev = by_name[e["curva"]]
        r = RL.rotular(e["pergunta"], janela(voltas[e["lap_id"]], track, cp, prev), ref)
        out.append({"id": e["id"], "pergunta": e["pergunta"], "curva": e["curva"], **r})
    return out


def gravar_csv(rows: List[Dict[str, object]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=["id", "pergunta", "curva", "rotulo", "criterio", "valor", "margem"])
        w.writeheader()
        for r in rows:
            w.writerow({**{k: r.get(k) for k in ("id", "pergunta", "curva", "rotulo", "criterio", "margem")},
                        "valor": json.dumps(r.get("valor"), ensure_ascii=False)})
    return path
