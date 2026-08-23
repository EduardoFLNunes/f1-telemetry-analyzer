"""Voltas validas materializadas na grade da pista.

Varrer os 11 GB de JSONL leva ~3 minutos; treinar um modelo exige varrer o
dataset dezenas de vezes. Este modulo faz a varredura uma vez e escreve o
resultado ja limpo, alinhado e reamostrado: um arquivo colunar onde cada volta
ocupa exatamente `track.size` linhas, e a linha `i` de qualquer volta e o mesmo
ponto da pista.

Depois daqui nada mais abre um `player.jsonl` -- nem o treino, nem o algoritmo
evolutivo, nem a comparacao com o piloto.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

from .. import config
from ..preprocessing.alignment import align_lap
from ..preprocessing.cleaning import clean_lap
from ..preprocessing.quality import evaluate_lap
from ..preprocessing.resampling import lap_time_from_grid, resample_lap
from ..track.geometry import TrackGeometry, load_geometry
from .inventory import load_inventory
from .recordings import Session, iter_laps, list_sessions

STORE_FILENAME = "laps_grid.parquet"
STORE_METADATA = "laps_grid_meta.json"

# Colunas guardadas por ponto de grade. Tudo que nao esta aqui pode ser
# recalculado a partir do que esta, e guardar o derivavel so faz o arquivo
# crescer e as versoes divergirem.
STORE_COLUMNS = (
    "lateral",
    "elapsed_s",
    "lap_time_s",
    "speed_kmh",
    "throttle",
    "brake",
    "steering",
    "gear",
    "rpm",
    "lateral_g",
    "longitudinal_g",
    "wheel_slip",
    "x",
    "z",
    "off_track",
    "fuel",
    "tyre_wear",
    "grip_index",
)


@dataclass
class StoredLaps:
    """As voltas na grade, mais o que descreve cada uma."""

    frame: pd.DataFrame          # (n_laps * grid, colunas), com `lap_id`
    laps: pd.DataFrame           # uma linha por volta: tempo, sessao, Hz...
    grid_size: int
    track_length: float

    @property
    def lap_ids(self) -> List[str]:
        return self.laps["lap_id"].tolist()

    def lap(self, lap_id: str) -> pd.DataFrame:
        selected = self.frame[self.frame["lap_id"] == lap_id]
        if selected.empty:
            raise KeyError(f"volta {lap_id} nao esta no store")
        return selected.reset_index(drop=True)

    def matrix(self, column: str) -> np.ndarray:
        """(n_laps, grid) de um canal -- a forma em que voltas se comparam."""
        pivot = self.frame.pivot(index="lap_id", columns="grid_index", values=column)
        return pivot.loc[self.lap_ids].to_numpy(dtype=float)


def build_store(
    inventory: Optional[pd.DataFrame] = None,
    track: Optional[TrackGeometry] = None,
    sessions: Optional[Sequence[Session]] = None,
    progress: Optional[Callable[[str], None]] = None,
) -> StoredLaps:
    """Le as voltas marcadas como validas no inventario e devolve o store."""
    geometry = track or load_geometry()
    catalogue = inventory if inventory is not None else load_inventory()
    wanted = catalogue[catalogue["valid"]]
    if wanted.empty:
        raise ValueError("o inventario nao tem nenhuma volta valida")

    by_session: Dict[str, set] = {}
    for _, row in wanted.iterrows():
        by_session.setdefault(str(row["session_id"]), set()).add(int(row["sequence"]))

    available = {s.session_id: s for s in (sessions if sessions is not None else list_sessions())}

    blocks: List[pd.DataFrame] = []
    records: List[Dict[str, object]] = []
    for position, (session_id, sequences) in enumerate(sorted(by_session.items()), start=1):
        session = available.get(session_id)
        if session is None:
            continue
        found = 0
        for lap in iter_laps(session):
            if lap.sequence not in sequences:
                continue
            cleaned, _ = clean_lap(lap.frame)
            aligned, alignment = align_lap(cleaned, geometry)
            quality = evaluate_lap(aligned, geometry, alignment)
            grid = resample_lap(aligned, geometry)

            block = grid.reindex(columns=[c for c in STORE_COLUMNS if c in grid.columns]).copy()
            block.insert(0, "grid_index", np.arange(geometry.size))
            block.insert(0, "lap_id", lap.lap_id)
            blocks.append(block)

            elapsed = grid["elapsed_s"].to_numpy(dtype=float)
            lap_time = lap_time_from_grid(grid)
            records.append(
                {
                    "lap_id": lap.lap_id,
                    "session_id": session_id,
                    "sequence": lap.sequence,
                    "lap_number": lap.lap_number,
                    "driver_id": lap.driver_id,
                    "track": lap.track,
                    "lap_time_s": lap_time,
                    "sample_hz": float(quality.metrics.get("sample_hz", np.nan)),
                    "raw_samples": int(lap.sample_count),
                    "coverage": float(alignment.coverage),
                    "speed_mean_kmh": float(np.nanmean(grid["speed_kmh"])),
                    "speed_min_kmh": float(np.nanmin(grid["speed_kmh"])),
                    "speed_max_kmh": float(np.nanmax(grid["speed_kmh"])),
                }
            )
            found += 1
        if progress:
            progress(f"[{position}/{len(by_session)}] {session_id}: {found} voltas")

    if not blocks:
        raise ValueError("nenhuma volta pode ser materializada")

    frame = pd.concat(blocks, ignore_index=True)
    laps = pd.DataFrame(records).sort_values("lap_time_s").reset_index(drop=True)
    return StoredLaps(
        frame=frame, laps=laps, grid_size=geometry.size, track_length=geometry.length
    )


def store_path(root: Optional[Path] = None) -> Path:
    return (Path(root) if root else config.artifacts_root()) / STORE_FILENAME


def save_store(store: StoredLaps, root: Optional[Path] = None) -> Path:
    path = store_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    store.frame.to_parquet(path, index=False)
    meta = {
        "grid_size": store.grid_size,
        "track_length": store.track_length,
        "columns": [c for c in store.frame.columns if c not in ("lap_id", "grid_index")],
        "laps": store.laps.to_dict(orient="records"),
    }
    (path.parent / STORE_METADATA).write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return path


def load_store(root: Optional[Path] = None) -> StoredLaps:
    path = store_path(root)
    meta_path = path.parent / STORE_METADATA
    if not path.exists() or not meta_path.exists():
        raise FileNotFoundError(
            f"store nao encontrado em {path}. Rode `python -m ml.scripts.build_lap_store`."
        )
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return StoredLaps(
        frame=pd.read_parquet(path),
        laps=pd.DataFrame(meta["laps"]),
        grid_size=int(meta["grid_size"]),
        track_length=float(meta["track_length"]),
    )
