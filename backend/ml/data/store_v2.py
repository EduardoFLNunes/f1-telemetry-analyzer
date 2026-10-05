"""Store v2: as voltas na grade, uma vez so, com todas as correcoes (pedido 16).

O store antigo (`laps_grid.parquet`) continua como esta, para os resultados das
Fases 1, 2 e 2b continuarem reproduziveis. O v2 junta o que o pedido 12, o 13
e o 14 acharam:

* **o periodo da volta** -- o relogio da grade e zerado na linha com o periodo
  verdadeiro (`resample_lap(..., line_clock=True)`); o antigo encurtava toda
  volta e o microsetor 0 em um passo da grade (25,7 a 28,0 ms);
* **o portao do box** -- volta com passagem pelo box (`ai_detector.pit_lap`,
  a deteccao do pedido 12) deixa de entrar;
* **as duas pastas** de gravacoes, sem as copias marcadas com `duplicada_de`;
* **os rotulos** -- `origem`, `origem_fonte`, `equipamento`, o relogio, a
  `pasta` e o `carModel` de cada volta vao junto, e quem le filtra.

Cada volta leva tambem o tempo de volta do jogo (`tempo_jogo_s`), medido pelo
cronometro do jogo costurado na troca de volta (`game_lap_time`): e a regua
da checagem principal (`store_checks`).
"""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from .. import config
from ..preprocessing.alignment import align_lap
from ..preprocessing.cleaning import clean_lap
from ..preprocessing.quality import evaluate_lap
from ..preprocessing.resampling import lap_time_from_grid, resample_lap
from ..track.geometry import TrackGeometry, load_geometry
from ..track.microsectors import Microsectors, build_microsectors
from .ai_detector import pit_lap
from .lap_store import IDENTITY_COLUMNS, STORE_COLUMNS, StoredLaps, check_geometry, load_store, save_store
from .recordings import RawLap, Session, iter_laps, list_all_sessions
from .session_annotations import car_for, session_annotations

STORE_V2_FILENAME = "laps_grid_v2.parquet"
STORE_V2_METADATA = "laps_grid_v2_meta.json"
STORE_V2_VERSION = 2

# Copiados do inventario rotulado para cada volta.
CARRIED_COLUMNS = IDENTITY_COLUMNS + (
    "origem",
    "origem_fonte",
    "origem_indicador",
    "equipamento",
    "pasta",
    "relogio_verificado",
    "relogio_suspeito",
    "relogio_pior_s",
    "inicio_epoch_s",
    "fim_epoch_s",
)

# Tempo do jogo: amostras de cada lado da troca de volta, e a distancia e o
# intervalo maximos entre a ultima amostra de uma volta e a primeira da outra.
GAME_TIME_SAMPLES = 5
GAME_TIME_MAX_GAP_M = 50.0
GAME_TIME_MAX_GAP_S = 0.5


def default_inventory_path() -> Path:
    return config.artifacts_root() / "origem" / "lap_inventory.parquet"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


def file_entry(path: Path) -> Dict[str, object]:
    path = Path(path)
    return {"arquivo": str(path), "bytes": int(path.stat().st_size), "sha256": sha256(path)}


def git_commit() -> Optional[str]:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(config.repo_root()),
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


# ------------------------------------------------------------ selecao ---

def select_v2(inventory: pd.DataFrame) -> tuple:
    """Voltas validas e unicas do inventario, e quantas cada filtro tirou."""
    valid = inventory[inventory["valid"].astype(bool)]
    duplicated = valid["duplicada_de"].notna() if "duplicada_de" in valid else pd.Series(False, index=valid.index)
    wanted = valid[~duplicated]
    return wanted, {
        "voltas_no_inventario": int(len(inventory)),
        "validas": int(len(valid)),
        "duplicadas_tiradas": int(duplicated.sum()),
    }


# ------------------------------------------------------ tempo do jogo ---

def _game_side(frame: pd.DataFrame, track: TrackGeometry, tail: bool) -> Optional[pd.DataFrame]:
    """As amostras de uma ponta da volta crua com cronometro, posicao e velocidade."""
    needed = ["lap_time_s", "x", "z", "speed_kmh"]
    if any(c not in frame.columns for c in needed):
        return None
    side = frame.tail(GAME_TIME_SAMPLES * 3) if tail else frame.head(GAME_TIME_SAMPLES * 3)
    side = side.copy()
    for column in needed + (["timestamp_s"] if "timestamp_s" in side.columns else []):
        side[column] = pd.to_numeric(side[column], errors="coerce")
    side = side.dropna(subset=needed)
    side = side[side["speed_kmh"] > 3.6]
    side = side.tail(GAME_TIME_SAMPLES) if tail else side.head(GAME_TIME_SAMPLES)
    if side.empty:
        return None
    s_values, _ = track.project_sequence(side[["x", "z"]].to_numpy(dtype=float))
    side["s"] = s_values
    return side


def game_lap_time(lap: RawLap, following: RawLap, track: TrackGeometry) -> Optional[float]:
    """Tempo de volta pelo cronometro do jogo, costurado na troca de volta.

    O gravador so tem o cronometro da volta corrente, que zera na linha. Para
    cada par (uma das ultimas amostras da volta, uma das primeiras da seguinte)
    o tempo de volta e `t_antes + distancia / velocidade media - t_depois`; vale
    a mediana dos pares, que ignora uma amostra com o cronometro repetido. So
    quando a seguinte comeca logo depois (`GAME_TIME_MAX_GAP_*`).
    """
    if following is None or following.sequence != lap.sequence + 1:
        return None
    before = _game_side(lap.frame, track, tail=True)
    after = _game_side(following.frame, track, tail=False)
    if before is None or after is None:
        return None
    gap_m = float(np.mod(after["s"].iloc[0] - before["s"].iloc[-1], track.length))
    if gap_m > GAME_TIME_MAX_GAP_M:
        return None
    if "timestamp_s" in before.columns and "timestamp_s" in after.columns:
        gap_s = float(after["timestamp_s"].iloc[0] - before["timestamp_s"].iloc[-1])
        if np.isfinite(gap_s) and gap_s > GAME_TIME_MAX_GAP_S:
            return None
    estimates = []
    for _, a in before.iterrows():
        for _, b in after.iterrows():
            distance = float(np.mod(b["s"] - a["s"], track.length))
            speed = (float(a["speed_kmh"]) + float(b["speed_kmh"])) / 2.0 / 3.6
            if distance > GAME_TIME_MAX_GAP_M * 2 or speed <= 1.0:
                continue
            estimates.append(float(a["lap_time_s"]) + distance / speed - float(b["lap_time_s"]))
    return float(np.median(estimates)) if estimates else None


# ------------------------------------------------------------- build ---

@dataclass
class BuildDetails:
    """O que o build fez, para o relatorio."""

    selection: Dict[str, int] = field(default_factory=dict)
    box_removed: List[str] = field(default_factory=list)
    not_found: List[str] = field(default_factory=list)
    sessions: List[str] = field(default_factory=list)


def _clean_value(value):
    if isinstance(value, float) and np.isnan(value):
        return None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def build_store_v2(
    inventory: pd.DataFrame,
    track: Optional[TrackGeometry] = None,
    sessions: Optional[Sequence[Session]] = None,
    progress: Optional[Callable[[str], None]] = None,
    sectors: Optional[Microsectors] = None,
) -> tuple:
    """Le as voltas validas e unicas do inventario rotulado e devolve (store, detalhes)."""
    geometry = track or load_geometry()
    sectors = sectors or build_microsectors(geometry)
    wanted, counts = select_v2(inventory)
    if wanted.empty:
        raise ValueError("o inventario nao tem nenhuma volta valida e unica")
    recorded = wanted["geometry_id"].dropna().unique() if "geometry_id" in wanted else []
    check_geometry(recorded[0] if len(recorded) == 1 else None, geometry, "o inventario")

    by_session: Dict[str, set] = {}
    carried: Dict[str, Dict[str, object]] = {}
    for _, row in wanted.iterrows():
        by_session.setdefault(str(row["session_id"]), set()).add(int(row["sequence"]))
        carried[str(row["lap_id"])] = {k: _clean_value(row.get(k)) for k in CARRIED_COLUMNS if k in row}

    available = {s.session_id: s for s in (sessions if sessions is not None else list_all_sessions())}
    details = BuildDetails(selection=counts)
    notes = session_annotations()
    blocks: List[pd.DataFrame] = []
    records: List[Dict[str, object]] = []
    for position, (session_id, sequences) in enumerate(sorted(by_session.items()), start=1):
        session = available.get(session_id)
        if session is None:
            details.not_found.extend(f"{session_id}#{q:04d}" for q in sorted(sequences))
            continue
        details.sessions.append(session_id)
        car = car_for(session_id, (session.metadata().get("metadata") or {}).get("carModel"), notes)
        found = 0
        pending: Optional[tuple] = None          # (volta crua, registro) esperando a seguinte
        for lap in iter_laps(session):
            if pending is not None:
                previous, record = pending
                record["tempo_jogo_s"] = game_lap_time(previous, lap, geometry)
                pending = None
            if lap.sequence not in sequences:
                continue
            cleaned, _ = clean_lap(lap.frame)
            aligned, alignment = align_lap(cleaned, geometry)
            quality = evaluate_lap(aligned, geometry, alignment)
            grid = resample_lap(aligned, geometry, line_clock=True)
            if pit_lap(grid, sectors):
                details.box_removed.append(lap.lap_id)
                continue
            block = grid.reindex(columns=[c for c in STORE_COLUMNS if c in grid.columns]).copy()
            block.insert(0, "grid_index", np.arange(geometry.size))
            block.insert(0, "lap_id", lap.lap_id)
            blocks.append(block)
            record = {
                "lap_id": lap.lap_id,
                "session_id": session_id,
                "sequence": lap.sequence,
                "lap_number": lap.lap_number,
                "driver_id": lap.driver_id,
                "track": lap.track,
                "lap_time_s": lap_time_from_grid(grid),
                "tempo_jogo_s": None,
                "geometry_id": geometry.geometry_id,
                "carModel": car,
                "sample_hz": float(quality.metrics.get("sample_hz", np.nan)),
                "raw_samples": int(lap.sample_count),
                "coverage": float(alignment.coverage),
                "speed_mean_kmh": float(np.nanmean(grid["speed_kmh"])),
                "speed_min_kmh": float(np.nanmin(grid["speed_kmh"])),
                "speed_max_kmh": float(np.nanmax(grid["speed_kmh"])),
                **carried.get(lap.lap_id, {}),
            }
            records.append(record)
            pending = (lap, record)
            found += 1
        missing = sequences - {r["sequence"] for r in records if r["session_id"] == session_id} - {
            int(i.split("#")[1]) for i in details.box_removed if i.startswith(session_id + "#")
        }
        details.not_found.extend(f"{session_id}#{q:04d}" for q in sorted(missing))
        if progress:
            progress(f"[{position}/{len(by_session)}] {session_id}: {found} voltas")

    if not blocks:
        raise ValueError("nenhuma volta pode ser materializada")
    frame = pd.concat(blocks, ignore_index=True)
    laps = pd.DataFrame(records).sort_values("lap_time_s").reset_index(drop=True)
    store = StoredLaps(
        frame=frame,
        laps=laps,
        grid_size=geometry.size,
        track_length=geometry.length,
        geometry_id=geometry.geometry_id,
        source_hash=geometry.source_hash,
        selection={
            "versao": STORE_V2_VERSION,
            "regra": "validas, sem duplicada_de, sem passagem pelo box (pit_lap); todas as origens",
            "relogio": "zerado na linha com o periodo verdadeiro (line_clock)",
        },
    )
    return store, details


def recording_start(session_id: str):
    """Inicio da gravacao pelo nome (`2026-10-04_23-51-42_...`), no relogio do piloto.

    O nome e o relogio que o piloto ve (05/10: a sessao de 23:51 terminou as
    00:31 pelo relogio dele); o `timestamp` gravado tem outra defasagem, e dele
    so se usa a duracao.
    """
    from datetime import datetime

    return datetime.strptime(str(session_id)[:19], "%Y-%m-%d_%H-%M-%S")


def recording_periods(inventory: pd.DataFrame, session_ids) -> Dict[str, Dict[str, object]]:
    """Inicio (pelo nome) e duracao (pelos instantes gravados) de cada gravacao."""
    out: Dict[str, Dict[str, object]] = {}
    for session_id in sorted(set(session_ids)):
        laps = inventory[inventory["session_id"] == session_id]
        first = pd.to_numeric(laps.get("inicio_epoch_s"), errors="coerce").min() if len(laps) else np.nan
        last = pd.to_numeric(laps.get("fim_epoch_s"), errors="coerce").max() if len(laps) else np.nan
        out[session_id] = {
            "inicio": recording_start(session_id).isoformat(),
            "duracao_s": float(last - first) if np.isfinite(first) and np.isfinite(last) else None,
        }
    return out


def save_store_v2(store: StoredLaps, extra: Dict[str, object], root: Optional[Path] = None) -> Path:
    return save_store(store, root, filename=STORE_V2_FILENAME, metadata=STORE_V2_METADATA, extra=extra)


def load_store_v2(root: Optional[Path] = None, track: Optional[TrackGeometry] = None) -> StoredLaps:
    return load_store(root, track, filename=STORE_V2_FILENAME, metadata=STORE_V2_METADATA)


def store_v2_meta(root: Optional[Path] = None) -> Dict[str, object]:
    import json

    path = (Path(root) if root else config.artifacts_root()) / STORE_V2_METADATA
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
