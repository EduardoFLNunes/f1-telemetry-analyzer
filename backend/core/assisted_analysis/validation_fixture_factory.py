from __future__ import annotations

import json
import math
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..data_quality.lap_validation import validate_lap


TRACK_NAME = "phase14_1_validation_track"
SESSION_ID = "phase14_1_assisted_validation"
TRACK_LENGTH_M = 1200.0
SAMPLE_COUNT = 361
CORNER_APEXES_M = (210.0, 560.0, 900.0)


@dataclass(frozen=True)
class Phase141Fixture:
    session_id: str
    session_dir: Path
    target_lap_id: str
    reference_lap_id: str
    invalid_lap_id: str
    track_name: str
    validations: Dict[int, Dict]


def write_phase14_1_validation_recording(
    repo_root: Path,
    *,
    session_id: str = SESSION_ID,
    overwrite: bool = True,
) -> Phase141Fixture:
    repo_root = Path(repo_root)
    safe_session = _safe_fragment(session_id)
    recordings_root = repo_root / "data" / "recordings"
    session_dir = recordings_root / safe_session
    resolved_root = recordings_root.resolve()
    resolved_session = session_dir.resolve()
    if resolved_session == resolved_root:
        raise ValueError("Fixture session directory must be below data/recordings")
    resolved_session.relative_to(resolved_root)
    if session_dir.exists() and overwrite:
        shutil.rmtree(session_dir)
    session_dir.mkdir(parents=True, exist_ok=True)

    reference = build_phase14_1_lap("reference", lap_number=1, duration_s=86.0, session_offset_s=0.0)
    target = build_phase14_1_lap("target", lap_number=2, duration_s=90.0, session_offset_s=100.0)
    invalid = build_phase14_1_invalid_lap(lap_number=3, session_offset_s=205.0)

    rows_by_lap = {1: reference, 2: target, 3: invalid}
    validations = {
        lap_number: _validation_payload(lap_number, rows, completed=lap_number in (1, 2), session_id=safe_session)
        for lap_number, rows in rows_by_lap.items()
    }

    started_at = datetime(2026, 6, 16, 12, 0, 0, tzinfo=timezone.utc).isoformat()
    metadata = {
        "track": TRACK_NAME,
        "startedAt": started_at,
        "endedAt": datetime(2026, 6, 16, 12, 4, 0, tzinfo=timezone.utc).isoformat(),
        "metadata": {
            "fixture": "phase14_1_assisted_analysis_validation",
            "trackLength": TRACK_LENGTH_M,
        },
    }
    (session_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    index = {
        "sessionId": safe_session,
        "track": TRACK_NAME,
        "createdAt": started_at,
        "laps": {
            str(lap_number): _index_lap_payload(lap_number, rows, completed=lap_number in (1, 2), session_id=safe_session)
            for lap_number, rows in rows_by_lap.items()
        },
    }
    (session_dir / "session-index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")

    with open(session_dir / "player.jsonl", "w", encoding="utf-8") as handle:
        for lap_number in (1, 2, 3):
            for row in rows_by_lap[lap_number].to_dict("records"):
                payload = {
                    "timestamp": row["timestamp"],
                    "sessionTime": row["sessionTime"],
                    "track": TRACK_NAME,
                    "sample": row,
                }
                handle.write(json.dumps(payload, separators=(",", ":")) + "\n")

    return Phase141Fixture(
        session_id=safe_session,
        session_dir=session_dir,
        target_lap_id=f"rec__{safe_session}__2",
        reference_lap_id=f"rec__{safe_session}__1",
        invalid_lap_id=f"rec__{safe_session}__3",
        track_name=TRACK_NAME,
        validations={lap_number: validate_lap(payload).to_api() for lap_number, payload in validations.items()},
    )


def build_phase14_1_lap(kind: str, *, lap_number: int, duration_s: float, session_offset_s: float) -> pd.DataFrame:
    distances, center_x, center_z, headings, curvature = _centerline_profile()
    rows: List[Dict] = []
    previous_speed: Optional[float] = None
    previous_time: Optional[float] = None

    for index, distance in enumerate(distances):
        progress = float(distance / TRACK_LENGTH_M)
        elapsed_s = float(duration_s * index / (len(distances) - 1))
        speed_kmh = _speed_profile(kind, distance)
        brake = _brake_profile(kind, distance)
        throttle = _throttle_profile(kind, distance, brake)
        lateral_offset = _lateral_offset(kind, distance)
        normal_x = -math.sin(float(headings[index]))
        normal_z = math.cos(float(headings[index]))
        world_x = float(center_x[index] + normal_x * lateral_offset)
        world_z = float(center_z[index] + normal_z * lateral_offset)
        steering = _steering(kind, distance, float(curvature[index]))

        if previous_speed is None or previous_time is None or elapsed_s <= previous_time:
            longitudinal_g = 0.0
        else:
            longitudinal_g = ((speed_kmh - previous_speed) / 3.6) / (elapsed_s - previous_time) / 9.81
        lateral_g = ((speed_kmh / 3.6) ** 2) * float(curvature[index]) / 9.81

        rows.append(
            {
                "timestamp": 1_700_000_000_000 + int((session_offset_s + elapsed_s) * 1000),
                "sessionTime": session_offset_s + elapsed_s,
                "lap_time": elapsed_s,
                "lap_number": lap_number,
                "lap": lap_number,
                "lapProgress": progress,
                "p": progress,
                "s": float(distance),
                "speedKmh": float(speed_kmh),
                "throttle": float(throttle),
                "brake": float(brake),
                "steering": float(steering),
                "gear": _gear(speed_kmh),
                "rpm": int(5200 + speed_kmh * 36),
                "yaw": float(headings[index]),
                "world_x": world_x,
                "world_y": 0.0,
                "world_z": world_z,
                "x": world_x,
                "z": world_z,
                "L": float(lateral_offset),
                "lateral_g": float(lateral_g),
                "longitudinal_g": float(longitudinal_g),
                "track_length": TRACK_LENGTH_M,
            }
        )
        previous_speed = speed_kmh
        previous_time = elapsed_s

    return pd.DataFrame(rows)


def build_phase14_1_invalid_lap(*, lap_number: int, session_offset_s: float) -> pd.DataFrame:
    valid = build_phase14_1_lap("target", lap_number=lap_number, duration_s=4.5, session_offset_s=session_offset_s)
    return valid.iloc[:24].copy().reset_index(drop=True)


def _centerline_profile():
    distances = np.linspace(0.0, TRACK_LENGTH_M * 0.995, SAMPLE_COUNT)
    curvature = np.asarray(
        [
            0.020 * _gauss(distance, 210.0, 38.0)
            - 0.017 * _gauss(distance, 560.0, 45.0)
            + 0.019 * _gauss(distance, 900.0, 42.0)
            for distance in distances
        ],
        dtype=float,
    )
    headings = []
    xs = []
    zs = []
    heading = 0.0
    x = 0.0
    z = 0.0
    previous_s = float(distances[0])
    for distance, curv in zip(distances, curvature):
        ds = float(distance - previous_s)
        heading += float(curv) * ds
        x += math.cos(heading) * ds
        z += math.sin(heading) * ds
        headings.append(heading)
        xs.append(x)
        zs.append(z)
        previous_s = float(distance)
    return distances, np.asarray(xs), np.asarray(zs), np.asarray(headings), curvature


def _speed_profile(kind: str, distance: float) -> float:
    speed = 248.0
    for apex, drop, width in ((210.0, 130.0, 48.0), (560.0, 118.0, 58.0), (900.0, 125.0, 52.0)):
        center = apex - 18.0 if kind == "target" and apex == 900.0 else apex
        speed -= drop * _gauss(distance, center, width)
    if kind == "target":
        speed -= 8.0 * _gauss(distance, 210.0, 95.0)
        speed -= 12.0 * _gauss(distance, 645.0, 80.0)
        speed -= 10.0 * _gauss(distance, 975.0, 80.0)
    return max(70.0, min(260.0, speed))


def _brake_profile(kind: str, distance: float) -> float:
    brake = 0.0
    for apex in CORNER_APEXES_M:
        if kind == "reference":
            start_s, release_s = apex - 88.0, apex - 16.0
        elif apex == 210.0:
            start_s, release_s = apex - 122.0, apex + 8.0
        elif apex == 560.0:
            start_s, release_s = apex - 92.0, apex - 12.0
        else:
            start_s, release_s = apex - 88.0, apex - 15.0
        if start_s <= distance <= release_s:
            midpoint = (start_s + release_s) / 2.0
            half_span = max(1.0, (release_s - start_s) / 2.0)
            brake = max(brake, 0.15 + 0.78 * (1.0 - abs(distance - midpoint) / half_span))
    return max(0.0, min(1.0, brake))


def _throttle_profile(kind: str, distance: float, brake: float) -> float:
    throttle = 1.0
    for apex in CORNER_APEXES_M:
        if kind == "reference":
            pickup_s, full_s = apex + 35.0, apex + 80.0
        elif apex == 210.0:
            pickup_s, full_s = apex + 43.0, apex + 90.0
        elif apex == 560.0:
            pickup_s, full_s = apex + 78.0, apex + 125.0
        else:
            pickup_s, full_s = apex + 12.0, apex + 24.0

        if apex - 40.0 < distance < pickup_s:
            throttle = min(throttle, 0.0)
        elif pickup_s <= distance <= full_s:
            throttle = min(throttle, (distance - pickup_s) / max(1.0, full_s - pickup_s))

    if brake > 0.08:
        throttle = 0.0
    if kind == "target" and 912.0 <= distance <= 924.0:
        throttle = 1.0
    return max(0.0, min(1.0, throttle))


def _lateral_offset(kind: str, distance: float) -> float:
    offset = 0.08 * math.sin(distance / 55.0)
    if kind == "target":
        offset += 0.70 * _gauss(distance, 605.0, 65.0)
        offset += 1.25 * _gauss(distance, 920.0, 70.0)
    return offset


def _steering(kind: str, distance: float, curvature: float) -> float:
    steering = curvature * 32.0
    if kind == "target" and abs(distance - 900.0) < 80.0:
        steering += 0.08
    return max(-0.7, min(0.7, steering))


def _gear(speed_kmh: float) -> int:
    if speed_kmh > 220.0:
        return 6
    if speed_kmh > 175.0:
        return 5
    if speed_kmh > 125.0:
        return 4
    return 3


def _validation_payload(lap_number: int, rows: pd.DataFrame, *, completed: bool, session_id: str = SESSION_ID) -> Dict:
    return {
        "sessionId": session_id,
        "lapId": f"{session_id}:{lap_number}",
        "lapNumber": lap_number,
        "sampleCount": len(rows),
        "durationSeconds": float(rows["sessionTime"].max() - rows["sessionTime"].min()),
        "progressStart": float(rows["p"].iloc[0]),
        "progressEnd": float(rows["p"].iloc[-1]),
        "progressMin": float(rows["p"].min()),
        "progressMax": float(rows["p"].max()),
        "maxGapSeconds": float(rows["sessionTime"].diff().dropna().max() if len(rows) > 1 else 0.0),
        "timestampInversions": 0,
        "completed": completed,
    }


def _index_lap_payload(lap_number: int, rows: pd.DataFrame, *, completed: bool, session_id: str = SESSION_ID) -> Dict:
    validation = _validation_payload(lap_number, rows, completed=completed, session_id=session_id)
    return {
        "lap_number": lap_number,
        "sample_count": validation["sampleCount"],
        "lap_elapsed_max": validation["durationSeconds"],
        "session_time_min": float(rows["sessionTime"].min()),
        "session_time_max": float(rows["sessionTime"].max()),
        "progress_start": validation["progressStart"],
        "progress_end": validation["progressEnd"],
        "progress_min": validation["progressMin"],
        "progress_max": validation["progressMax"],
        "max_gap_seconds": validation["maxGapSeconds"],
        "timestamp_inversions": validation["timestampInversions"],
    }


def _gauss(value: float, center: float, width: float) -> float:
    return math.exp(-0.5 * ((value - center) / width) ** 2)


def _safe_fragment(value: str) -> str:
    import re

    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(value).strip())
    if cleaned in {".", ".."}:
        return "unknown"
    return cleaned.strip("_") or "unknown"
