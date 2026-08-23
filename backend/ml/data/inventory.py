"""Inventario de voltas: o que existe no disco e o que serve.

Varre `data/recordings/` uma vez, limpa, alinha e julga cada volta, e escreve
uma tabela onde cada linha e uma volta com seu veredito e os numeros que o
produziram. A varredura completa leva alguns minutos sobre 11 GB, entao o
resultado e persistido -- todo o resto do pipeline le a tabela, nao os JSONL.

A tabela e a analise exploratoria. Ela responde, sem abrir um unico arquivo de
novo: quantas voltas utilizaveis existem, de quantas sessoes, com que
frequencia de amostragem, e quanto tempo separa a melhor da mediana.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

from .. import config
from ..preprocessing.alignment import align_lap
from ..preprocessing.cleaning import clean_lap
from ..preprocessing.quality import evaluate_lap
from ..track.geometry import TrackGeometry, load_geometry
from .recordings import RawLap, Session, iter_laps, list_sessions

INVENTORY_FILENAME = "lap_inventory.parquet"
INVENTORY_SUMMARY = "lap_inventory_summary.json"


def _record(lap: RawLap, quality, cleaning, alignment) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "lap_id": lap.lap_id,
        "session_id": lap.session_id,
        "sequence": lap.sequence,
        "lap_number": lap.lap_number,
        "driver_id": lap.driver_id,
        "track": lap.track,
        "raw_samples": lap.sample_count,
        "corrupt_lines": lap.corrupt_lines,
        "valid": bool(quality.valid),
        "reasons": "; ".join(quality.reasons),
        "cleaned_samples": cleaning.output_rows,
        "dropped_missing": cleaning.dropped_missing,
        "dropped_duplicate_time": cleaning.dropped_duplicate_time,
    }
    row.update({key: float(value) for key, value in quality.metrics.items()})
    return row


def scan_sessions(
    sessions: Optional[Sequence[Session]] = None,
    track: Optional[TrackGeometry] = None,
    gates: config.LapQualityGates = config.DEFAULT_GATES,
    progress: Optional[Callable[[str], None]] = None,
) -> pd.DataFrame:
    """Percorre as sessoes e devolve uma linha por volta."""
    geometry = track or load_geometry()
    available = list(sessions) if sessions is not None else list_sessions()

    rows: List[Dict[str, Any]] = []
    for position, session in enumerate(available, start=1):
        count = 0
        for lap in iter_laps(session):
            cleaned, cleaning = clean_lap(lap.frame)
            if cleaned.empty or len(cleaned) < 4:
                rows.append(
                    {
                        "lap_id": lap.lap_id,
                        "session_id": lap.session_id,
                        "sequence": lap.sequence,
                        "lap_number": lap.lap_number,
                        "driver_id": lap.driver_id,
                        "track": lap.track,
                        "raw_samples": lap.sample_count,
                        "corrupt_lines": lap.corrupt_lines,
                        "valid": False,
                        "reasons": "amostras insuficientes apos limpeza",
                        "cleaned_samples": int(len(cleaned)),
                    }
                )
                count += 1
                continue
            aligned, alignment = align_lap(cleaned, geometry)
            quality = evaluate_lap(aligned, geometry, alignment, gates)
            rows.append(_record(lap, quality, cleaning, alignment))
            count += 1
        if progress:
            progress(f"[{position}/{len(available)}] {session.session_id}: {count} voltas")

    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.sort_values(["session_id", "sequence"]).reset_index(drop=True)
    return frame


def summarise(inventory: pd.DataFrame) -> Dict[str, Any]:
    """Resumo legivel do inventario -- a analise exploratoria em numeros."""
    if inventory.empty:
        return {"laps": 0}

    valid = inventory[inventory["valid"]]
    summary: Dict[str, Any] = {
        "laps_total": int(len(inventory)),
        "laps_valid": int(len(valid)),
        "sessions_total": int(inventory["session_id"].nunique()),
        "sessions_with_valid_laps": int(valid["session_id"].nunique()) if len(valid) else 0,
        "drivers": sorted(inventory["driver_id"].dropna().unique().tolist()),
    }

    rejected = inventory[~inventory["valid"]]
    causes: Dict[str, int] = {}
    for text in rejected["reasons"].fillna(""):
        for reason in (part.strip() for part in str(text).split(";") if part.strip()):
            # Agrupa pelo motivo, sem os numeros que variam de volta para volta.
            key = reason.split("(")[0].strip()
            causes[key] = causes.get(key, 0) + 1
    summary["rejection_causes"] = dict(sorted(causes.items(), key=lambda kv: -kv[1]))

    if len(valid):
        for column, label in (
            ("duration_s", "lap_time_s"),
            ("sample_hz", "sample_hz"),
            ("speed_mean_kmh", "speed_mean_kmh"),
            ("coverage", "coverage"),
        ):
            if column not in valid.columns:
                continue
            values = valid[column].dropna().to_numpy(dtype=float)
            if values.size == 0:
                continue
            summary[label] = {
                "min": float(values.min()),
                "p10": float(np.percentile(values, 10)),
                "median": float(np.median(values)),
                "p90": float(np.percentile(values, 90)),
                "max": float(values.max()),
            }
        best = valid.loc[valid["duration_s"].idxmin()]
        summary["best_lap"] = {
            "lap_id": str(best["lap_id"]),
            "lap_time_s": float(best["duration_s"]),
            "sample_hz": float(best["sample_hz"]),
        }
        summary["valid_laps_per_session"] = (
            valid.groupby("session_id").size().sort_values(ascending=False).to_dict()
        )
    return summary


def inventory_path(root: Optional[Path] = None) -> Path:
    return (Path(root) if root else config.artifacts_root()) / INVENTORY_FILENAME


def save_inventory(inventory: pd.DataFrame, root: Optional[Path] = None) -> Path:
    path = inventory_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    inventory.to_parquet(path, index=False)
    summary_path = path.parent / INVENTORY_SUMMARY
    summary_path.write_text(
        json.dumps(summarise(inventory), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return path


def load_inventory(root: Optional[Path] = None) -> pd.DataFrame:
    path = inventory_path(root)
    if not path.exists():
        raise FileNotFoundError(
            f"inventario nao encontrado em {path}. Rode `python -m ml.scripts.build_inventory`."
        )
    return pd.read_parquet(path)
