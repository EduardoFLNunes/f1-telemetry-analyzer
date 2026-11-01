"""As voltas do Modelo 2 e as taxas no tempo original (secoes 1.1 e 1.2).

* **Store v2:** as voltas `humano` com o equipamento atual (o filtro do
  relatorio de evolucao) e as `ia` de sessoes a partir de 04/10.
* **Fora do store:** as gravacoes posteriores a construcao dele, lidas com as
  mesmas funcoes do store, sem escrever nele. A origem sai do indicador
  `isAIControlled` (tudo `true` ou tudo `false`; mistura fica fora) e o relogio
  e conferido contra o tempo do jogo costurado na troca de volta.
* **As taxas** (freio, acelerador, volante, fracao de carga dianteira) sao
  diferencas centradas de +-0,05 s no cronometro do jogo, sem as amostras em
  que ele nao andou; as medias moveis do volante tambem. Depois, cada canal e
  levado a grade pelo `s` das amostras originais.

As gravacoes so sao lidas.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from .. import config
from ..comparison.evolution import driver_laps as evolution_driver_laps
from ..comparison.evolution import group_sessions
from ..data.ai_detector import pit_lap
from ..data.coach_references import AI_SINCE
from ..data.origin import AI, CURRENT_EQUIPMENT, HUMAN
from ..data.recordings import RawLap, Session, iter_laps, list_all_sessions
from ..data.store_v2 import PHYSICAL_COLUMNS, game_lap_time, load_store_v2, store_v2_meta
from ..preprocessing.alignment import align_lap
from ..preprocessing.cleaning import clean_lap
from ..preprocessing.quality import evaluate_lap
from ..preprocessing.resampling import lap_time_from_grid, resample_lap
from ..track.geometry import TrackGeometry
from ..track.microsectors import build_microsectors

# Gravacoes posteriores ao store v2 (construido em 22/10, 03:34).
FORA_DO_STORE = (
    "2026-10-22_09-46-01_vhe_interlagos",
    "2026-10-24_13-26-12_vhe_interlagos",
    "2026-10-24_13-43-32_vhe_interlagos",
)
CLOCK_TOLERANCE_S = 0.05      # tempo da grade contra o tempo do jogo, voltas de fora do store
EQUIPMENT_SINCE = "2026-10-01"

RATE_HALF_S = 0.05            # diferenca centrada de +-0,05 s
HOLE_S = 0.20                 # buraco no cronometro que torna a taxa nao confiavel
MA_LONG_S = 0.5               # media movel da suavidade do volante
MA_SHORT_S = 0.1              # media movel das reversoes
MA_STEER_S = 0.2              # media movel do volante crescendo depois da retomada

DERIVED = ("brake_rate", "throttle_rate", "steer_rate", "steer_ma01", "steer_ma02", "steer_dev05",
           "front_share", "front_share_rate", "raw_dt", "t_raw")

AI_LEVELS_FILE = config.repo_root() / "docs" / "experimentos" / "ia_niveis.csv"


def raiz() -> Path:
    return config.artifacts_root() / "modelo2"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


# ------------------------------------------------------------ taxas ---

def dedupe_clock(frame: pd.DataFrame, clock: str = "lap_time_s") -> pd.DataFrame:
    """So as amostras em que o cronometro andou (maior que o maximo anterior)."""
    t = pd.to_numeric(frame[clock], errors="coerce").to_numpy(dtype=float)
    finite = np.isfinite(t)
    before = np.concatenate([[-np.inf], np.fmax.accumulate(np.where(finite, t, -np.inf))[:-1]])
    return frame.loc[finite & (t > before)].reset_index(drop=True)


def centred_rate(t: np.ndarray, v: np.ndarray, half: float = RATE_HALF_S) -> np.ndarray:
    """(v(t + h) - v(t - h)) / 2h, com interpolacao linear e as pontas cortadas."""
    good = np.isfinite(v)
    if good.sum() < 2:
        return np.full(t.size, np.nan)
    tg, vg = t[good], v[good]
    lo = np.clip(t - half, tg[0], tg[-1])
    hi = np.clip(t + half, tg[0], tg[-1])
    span = hi - lo
    out = (np.interp(hi, tg, vg) - np.interp(lo, tg, vg)) / np.where(span > 0, span, np.nan)
    return out


def moving_average(t: np.ndarray, v: np.ndarray, width: float) -> np.ndarray:
    """Media movel centrada de largura `width` segundos, pela integral (amostragem irregular)."""
    good = np.isfinite(v)
    if good.sum() < 2:
        return np.full(t.size, np.nan)
    tg, vg = t[good], v[good]
    integral = np.concatenate([[0.0], np.cumsum(np.diff(tg) * (vg[1:] + vg[:-1]) / 2.0)])
    lo = np.clip(t - width / 2.0, tg[0], tg[-1])
    hi = np.clip(t + width / 2.0, tg[0], tg[-1])
    span = hi - lo
    return (np.interp(hi, tg, integral) - np.interp(lo, tg, integral)) / np.where(span > 0, span, np.nan)


def raw_derived(aligned: pd.DataFrame) -> pd.DataFrame:
    """As colunas derivadas no tempo original, uma linha por amostra mantida."""
    raw = dedupe_clock(aligned)
    t = raw["lap_time_s"].to_numpy(dtype=float)
    out = pd.DataFrame({"s_unwrapped": raw["s_unwrapped"].to_numpy(dtype=float), "t_raw": t})

    def col(name):
        return pd.to_numeric(raw[name], errors="coerce").to_numpy(dtype=float) if name in raw else np.full(t.size, np.nan)

    steer = col("steer_angle")
    if not np.isfinite(steer).any():
        steer = col("steering")
    out["brake_rate"] = centred_rate(t, col("brake"))
    out["throttle_rate"] = centred_rate(t, col("throttle"))
    out["steer_rate"] = centred_rate(t, steer)
    out["steer_ma01"] = moving_average(t, steer, MA_SHORT_S)
    out["steer_ma02"] = moving_average(t, np.abs(steer), MA_STEER_S)
    out["steer_dev05"] = np.abs(steer - moving_average(t, steer, MA_LONG_S))
    loads = [col(f"wheel_load_{w}") for w in ("fl", "fr", "rl", "rr")]
    total = loads[0] + loads[1] + loads[2] + loads[3]
    share = np.where(total > 0, (loads[0] + loads[1]) / total, np.nan)
    out["front_share"] = share
    out["front_share_rate"] = centred_rate(t, share)
    dt = np.diff(t)
    out["raw_dt"] = np.concatenate([dt, [np.nan]])
    return out


def to_grid(raw: pd.DataFrame, track: TrackGeometry) -> pd.DataFrame:
    """Leva as colunas de `raw_derived` a grade, pela posicao de cada amostra."""
    s = np.maximum.accumulate(raw["s_unwrapped"].to_numpy(dtype=float))
    if s.size:
        s = s - track.length * np.round(s[0] / track.length)
    s, first = np.unique(s, return_index=True)
    grid = {"grid_index": np.arange(track.size)}
    for column in DERIVED:
        values = raw[column].to_numpy(dtype=float)[first]
        good = np.isfinite(values)
        if column == "raw_dt":
            # O intervalo que contem cada ponto da grade (degrau, nao interpolacao).
            pos = np.clip(np.searchsorted(s, track.s, side="right") - 1, 0, max(s.size - 1, 0))
            grid[column] = values[pos] if s.size else np.full(track.size, np.nan)
        elif good.sum() >= 2:
            grid[column] = np.interp(track.s, s[good], values[good])
        else:
            grid[column] = np.full(track.size, np.nan)
    return pd.DataFrame(grid)


# ------------------------------------------------------------ voltas ---

@dataclass
class Volta:
    lap_id: str
    gravacao: str
    origem: str
    tempo_s: float
    grid: pd.DataFrame
    fora_do_store: bool = False
    sessao: Optional[str] = None
    canais: Tuple[str, ...] = ()
    nivel_ia: Optional[Dict[str, object]] = None

    @property
    def ia(self) -> bool:
        return self.origem == AI


def store_selection(laps: pd.DataFrame) -> pd.DataFrame:
    """As voltas rotuladas do store v2: as do piloto (filtro da evolucao) e as da IA."""
    human = evolution_driver_laps(laps)
    ai = laps[(laps["origem"] == AI) & laps["relogio_verificado"].fillna(False).astype(bool)
              & ~laps["relogio_suspeito"].fillna(True).astype(bool)
              & (laps["session_id"].str[:10] >= AI_SINCE)]
    return pd.concat([human, ai]).drop_duplicates("lap_id")


def _origin_from_indicator(raw: pd.DataFrame) -> Tuple[str, float]:
    if "ai_controlled" not in raw.columns:
        return "desconhecida", float("nan")
    flags = raw["ai_controlled"].dropna()
    if flags.empty:
        return "desconhecida", float("nan")
    share = float(flags.astype(bool).mean())
    if share == 1.0:
        return AI, share
    if share == 0.0:
        return HUMAN, share
    return "misturada", share


def read_outside(session: Session, track: TrackGeometry) -> Tuple[List[Volta], List[Dict[str, object]], Dict[str, pd.DataFrame]]:
    """As voltas de uma gravacao de fora do store, pelas regras de 1.1. Devolve (voltas, relatorio, derivados)."""
    sectors = build_microsectors(track)
    kept: List[Volta] = []
    report: List[Dict[str, object]] = []
    derived: Dict[str, pd.DataFrame] = {}
    pending = None
    for lap in iter_laps(session):
        if pending is not None:
            prev_lap, entry, volta = pending
            game = game_lap_time(prev_lap, lap, track)
            entry["tempo_jogo_s"] = game
            if volta is not None:
                ok = game is not None and abs(volta.tempo_s - game) <= CLOCK_TOLERANCE_S
                entry["relogio_ok"] = bool(ok)
                if ok:
                    kept.append(volta)
                else:
                    entry["motivo"] = "relogio: tempo da grade contra o do jogo"
            pending = None
        cleaned, _ = clean_lap(lap.frame)
        aligned, alignment = align_lap(cleaned, track)
        quality = evaluate_lap(aligned, track, alignment)
        origin, share = _origin_from_indicator(lap.frame)
        entry = {"lap_id": lap.lap_id, "amostras": lap.sample_count, "valida": bool(quality.valid),
                 "motivos_portao": list(quality.reasons), "origem": origin, "fracao_ia": share}
        volta = None
        if quality.valid:
            grid = resample_lap(aligned, track, line_clock=True)
            if pit_lap(grid, sectors):
                entry["motivo"] = "box"
            elif origin not in (AI, HUMAN):
                entry["motivo"] = f"origem {origin}"
            else:
                grid = grid.reset_index(drop=True)
                channels = tuple(c for c in PHYSICAL_COLUMNS if c in grid and np.isfinite(grid[c].to_numpy(dtype=float)).any())
                volta = Volta(lap_id=lap.lap_id, gravacao=session.session_id, origem=origin,
                              tempo_s=float(lap_time_from_grid(grid)), grid=grid, fora_do_store=True,
                              canais=channels)
                entry["tempo_grade_s"] = volta.tempo_s
                derived[lap.lap_id] = to_grid(raw_derived(aligned), track)
        else:
            entry["motivo"] = "portoes de qualidade"
        report.append(entry)
        pending = (lap, entry, volta)
    if pending is not None and pending[2] is not None:
        pending[1]["relogio_ok"] = False
        pending[1]["motivo"] = "ultima volta: sem a seguinte para o tempo do jogo"
    return kept, report, derived


def derived_for_session(session: Session, sequences: Mapping[int, int], track: TrackGeometry) -> Dict[str, pd.DataFrame]:
    """As taxas de cada volta pedida de uma gravacao do store. `sequences[seq] = raw_samples` do store."""
    out: Dict[str, pd.DataFrame] = {}
    for lap in iter_laps(session):
        expected = sequences.get(lap.sequence)
        if expected is None:
            continue
        if int(expected) != lap.sample_count:
            raise ValueError(f"{lap.lap_id}: {lap.sample_count} amostras, o store tem {expected}")
        cleaned, _ = clean_lap(lap.frame)
        aligned, _ = align_lap(cleaned, track)
        out[lap.lap_id] = to_grid(raw_derived(aligned), track)
    missing = set(f"{session.session_id}#{q:04d}" for q in sequences) - set(out)
    if missing:
        raise ValueError(f"voltas do store nao encontradas na gravacao: {sorted(missing)}")
    return out


def ai_levels(path: Path = AI_LEVELS_FILE) -> pd.DataFrame:
    """Os blocos da IA em niveis de forca: gravacao, volta_de, volta_ate, nivel, agressividade, variacao."""
    if not Path(path).exists():
        return pd.DataFrame(columns=["gravacao", "volta_de", "volta_ate", "nivel", "agressividade", "variacao"])
    return pd.read_csv(path, dtype={"gravacao": str})


def recording_period(session_id: str, laps: pd.DataFrame) -> Dict[str, object]:
    start = datetime.strptime(session_id[:19], "%Y-%m-%d_%H-%M-%S")
    return {"inicio": start.isoformat(), "duracao_s": None}


@dataclass
class Conjunto:
    voltas: Dict[str, Volta]
    store_meta: Dict[str, object]
    fora_relatorio: Dict[str, List[Dict[str, object]]] = field(default_factory=dict)
    lidos: List[Dict[str, object]] = field(default_factory=list)

    def da_ia(self) -> List[Volta]:
        return [v for v in self.voltas.values() if v.ia]

    def do_piloto(self) -> List[Volta]:
        return [v for v in self.voltas.values() if not v.ia]


def carregar(track: TrackGeometry, cache: bool = True, progress=print) -> Conjunto:
    """Todas as voltas rotuladas, com a grade do store (ou a de fora) e as taxas derivadas."""
    meta = store_v2_meta()
    if not meta or not meta.get("aprovado"):
        raise SystemExit("PARADO: store v2 ausente ou nao aprovado.")
    store = load_store_v2(track=track)
    selected = store_selection(store.laps)
    root = raiz()
    root.mkdir(parents=True, exist_ok=True)
    derived_cache = root / "derivados.parquet"
    outside_cache = root / "fora_do_store.parquet"
    outside_meta = root / "fora_do_store.json"

    sessions = {s.session_id: s for s in list_all_sessions()}
    derived: Dict[str, pd.DataFrame] = {}
    if cache and derived_cache.exists():
        frame = pd.read_parquet(derived_cache)
        derived = {k: g.drop(columns="lap_id").reset_index(drop=True) for k, g in frame.groupby("lap_id")}
    wanted = selected[~selected["lap_id"].isin(derived)]
    for position, (sid, rows) in enumerate(sorted(wanted.groupby("session_id")), start=1):
        progress(f"  taxas [{position}] {sid}: {len(rows)} voltas")
        derived.update(derived_for_session(sessions[sid], dict(zip(rows["sequence"].astype(int), rows["raw_samples"].astype(int))), track))

    outside_laps: List[Volta] = []
    outside_report: Dict[str, List[Dict[str, object]]] = {}
    if cache and outside_cache.exists() and outside_meta.exists():
        info = json.loads(outside_meta.read_text(encoding="utf-8"))
        frame = pd.read_parquet(outside_cache)
        grids = {k: g.drop(columns="lap_id").reset_index(drop=True) for k, g in frame.groupby("lap_id")}
        for entry in info["voltas"]:
            outside_laps.append(Volta(lap_id=entry["lap_id"], gravacao=entry["gravacao"], origem=entry["origem"],
                                      tempo_s=entry["tempo_s"], grid=grids[entry["lap_id"]], fora_do_store=True,
                                      canais=tuple(entry["canais"])))
        outside_report = info["relatorio"]
    else:
        for sid in FORA_DO_STORE:
            if sid not in sessions:
                outside_report[sid] = [{"motivo": "gravacao nao encontrada"}]
                continue
            progress(f"  fora do store: {sid}")
            laps, report, extra = read_outside(sessions[sid], track)
            outside_laps.extend(laps)
            outside_report[sid] = report
            derived.update(extra)
        if outside_laps:
            pd.concat([v.grid.assign(lap_id=v.lap_id) for v in outside_laps]).to_parquet(outside_cache)
        outside_meta.write_text(json.dumps({
            "voltas": [{"lap_id": v.lap_id, "gravacao": v.gravacao, "origem": v.origem, "tempo_s": v.tempo_s,
                        "canais": list(v.canais)} for v in outside_laps],
            "relatorio": outside_report}, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    pd.concat([g.assign(lap_id=k) for k, g in derived.items()]).to_parquet(derived_cache)

    channels = meta.get("canais_por_volta", {})
    voltas: Dict[str, Volta] = {}
    grouped = {k: g.reset_index(drop=True) for k, g in store.frame[store.frame["lap_id"].isin(selected["lap_id"])].groupby("lap_id")}
    for _, row in selected.iterrows():
        grid = grouped[row["lap_id"]].sort_values("grid_index").reset_index(drop=True)
        voltas[row["lap_id"]] = Volta(lap_id=row["lap_id"], gravacao=row["session_id"], origem=row["origem"],
                                      tempo_s=float(row["lap_time_s"]), grid=grid,
                                      canais=tuple(channels.get(row["lap_id"], [])))
    for v in outside_laps:
        voltas[v.lap_id] = v
    for lap_id, volta in voltas.items():
        extra = derived[lap_id]
        base = volta.grid.drop(columns=[c for c in DERIVED if c in volta.grid.columns])
        volta.grid = pd.concat([base.reset_index(drop=True), extra.drop(columns="grid_index").reset_index(drop=True)], axis=1)

    periods = dict(meta.get("periodos_das_gravacoes") or {})
    for v in outside_laps:
        periods.setdefault(v.gravacao, recording_period(v.gravacao, pd.DataFrame()))
    sessions_of = group_sessions({v.gravacao: periods[v.gravacao] for v in voltas.values()})
    levels = ai_levels()
    for v in voltas.values():
        v.sessao = sessions_of[v.gravacao]
        if not levels.empty:
            number = int(v.lap_id.split("#")[1])
            match = levels[(levels["gravacao"] == v.gravacao) & (levels["volta_de"] <= number) & (levels["volta_ate"] >= number)]
            if len(match):
                v.nivel_ia = match.iloc[0].to_dict()

    read = [config.artifacts_root() / "laps_grid_v2.parquet", config.artifacts_root() / "laps_grid_v2_meta.json"]
    for sid in sorted({v.gravacao for v in voltas.values()} | (set(FORA_DO_STORE) & set(sessions))):
        read.append(sessions[sid].player_stream)
    return Conjunto(voltas=voltas, store_meta=meta, fora_relatorio=outside_report,
                    lidos=[{"arquivo": str(p), "bytes": p.stat().st_size} for p in read])
