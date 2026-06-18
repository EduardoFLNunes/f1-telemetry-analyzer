from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import duckdb
import pandas as pd

from ..live.runtime_state import RuntimeState
from ..telemetry.telemetry_buffer import TelemetryBuffer
from ..telemetry.telemetry_models import TelemetrySample
from ..data_quality.lap_validation import validate_lap
from .models import LapDescriptor
from .utils import finite_float, finite_int, normalize_lap_dataframe


logger = logging.getLogger(__name__)
MAX_UNINDEXED_RECORDING_SCAN_BYTES = 8 * 1024 * 1024


def safe_fragment(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(value).strip())
    return cleaned.strip("_") or "unknown"


class LapDataLoader:
    def __init__(
        self,
        repo_root: Path,
        buffer_provider: Callable[[], TelemetryBuffer],
        runtime_state_provider: Callable[[], RuntimeState],
        recordings_roots: Optional[Sequence[Path]] = None,
    ):
        self.repo_root = Path(repo_root)
        self.buffer_provider = buffer_provider
        self.runtime_state_provider = runtime_state_provider
        self.recordings_roots = self._unique_paths(
            recordings_roots or [self.repo_root / "data" / "recordings"]
        )
        self.recordings_root = self.recordings_roots[0]
        self._recorded_lap_paths: Dict[str, Path] = {}
        self.telemetry_db_paths = [
            self.repo_root / "data" / "telemetry_db" / "telemetry.duckdb",
            self.repo_root / "backend" / "data" / "telemetry_db" / "telemetry.duckdb",
        ]

    def list_laps(self, include_buffer: bool = True) -> List[LapDescriptor]:
        laps: List[LapDescriptor] = []
        laps.extend(self._list_duckdb_laps())
        laps.extend(self._list_recorded_laps())
        if include_buffer:
            laps.extend(self._list_buffer_laps())

        unique: Dict[str, LapDescriptor] = {}
        for lap in laps:
            unique[lap.lap_id] = lap
        return sorted(
            unique.values(),
            key=lambda item: (
                item.source != "buffer",
                item.started_at or "",
                item.session_id or "",
                item.lap_number,
                item.lap_id,
            ),
            reverse=True,
        )

    def load_lap(self, lap_id: str) -> Tuple[LapDescriptor, pd.DataFrame]:
        if lap_id.startswith("db__"):
            return self._load_duckdb_lap(lap_id)
        if lap_id.startswith("rec__"):
            return self._load_recorded_lap(lap_id)
        if lap_id.startswith("buffer__"):
            return self._load_buffer_lap(lap_id)
        raise ValueError(f"Unknown assisted analysis lap id: {lap_id}")

    def _list_duckdb_laps(self) -> List[LapDescriptor]:
        result: List[LapDescriptor] = []
        for db_path in self.telemetry_db_paths:
            if not db_path.exists():
                continue
            try:
                con = duckdb.connect(str(db_path), read_only=True)
                rows = con.execute("SELECT driver_id, lap_number, lap_time, timestamp, parquet_path FROM laps").fetchall()
                con.close()
            except Exception as exc:
                logger.warning("Assisted analysis DuckDB lap listing failed for %s: %s", db_path, exc)
                continue

            for driver_id, lap_number, lap_time, timestamp, parquet_path in rows:
                path = self._resolve_path(parquet_path)
                stem = safe_fragment(path.stem if path else str(parquet_path))
                lap_num = finite_int(lap_number, 0)
                validation_api = self._validate_parquet_lap_for_listing(path, lap_num, finite_float(lap_time)) if path else None
                if not validation_api:
                    continue
                sample_count = int(validation_api.get("sampleCount") or 0)
                driver = str(driver_id or "player_1")
                result.append(
                    LapDescriptor(
                        lap_id=f"db__{safe_fragment(driver)}__{lap_num}__{stem}",
                        source="telemetry_db",
                        driver_id=driver,
                        lap_number=lap_num,
                        lap_time=finite_float(lap_time),
                        sample_count=sample_count,
                        parquet_path=str(path) if path else str(parquet_path),
                        started_at=str(timestamp) if timestamp is not None else None,
                        metadata={"dbPath": str(db_path), "validation": validation_api},
                    )
                )
        return result

    def _load_duckdb_lap(self, lap_id: str) -> Tuple[LapDescriptor, pd.DataFrame]:
        parts = lap_id.split("__", 3)
        if len(parts) != 4:
            raise ValueError(f"Invalid DuckDB lap id: {lap_id}")
        _, driver, lap_number_text, stem = parts
        lap_number = finite_int(lap_number_text, 0)

        candidates = [
            lap for lap in self._list_duckdb_laps()
            if lap.driver_id == driver and lap.lap_number == lap_number and lap.parquet_path and safe_fragment(Path(lap.parquet_path).stem) == stem
        ]
        if not candidates:
            candidates = [lap for lap in self._list_duckdb_laps() if lap.lap_id == lap_id]
        if not candidates:
            raise FileNotFoundError(f"DuckDB lap not found: {lap_id}")

        descriptor = candidates[0]
        parquet_path = Path(descriptor.parquet_path or "")
        if not parquet_path.exists():
            raise FileNotFoundError(f"Lap parquet not found: {parquet_path}")
        raw = pd.read_parquet(parquet_path)
        track_length = self._active_track_length()
        df = normalize_lap_dataframe(raw, track_length=track_length)
        descriptor.sample_count = len(df)
        descriptor.lap_time = descriptor.lap_time or self._duration(df)
        descriptor.track = descriptor.track or self._active_track_name()
        return descriptor, df

    def _list_recorded_laps(self) -> List[LapDescriptor]:
        laps: List[LapDescriptor] = []
        self._recorded_lap_paths = {}
        for recordings_root in self.recordings_roots:
            laps.extend(self._list_recorded_laps_from_root(recordings_root))
        return laps

    def _list_recorded_laps_from_root(self, recordings_root: Path) -> List[LapDescriptor]:
        if not recordings_root.exists():
            return []

        laps: List[LapDescriptor] = []
        for session_dir in sorted(recordings_root.iterdir(), reverse=True):
            if not session_dir.is_dir():
                continue
            player_path = session_dir / "player.jsonl"
            if not player_path.exists():
                continue
            metadata = self._read_json(session_dir / "metadata.json")
            index = self._read_json(session_dir / "session-index.json")
            if isinstance(index, dict) and isinstance(index.get("laps"), dict):
                lap_numbers = sorted(finite_int(number, 0) for number in index["laps"].keys())
                last_lap_number = lap_numbers[-1] if lap_numbers else None
                recording_ended = bool(metadata.get("endedAt"))
                for lap_key, lap_info in index["laps"].items():
                    lap_number = finite_int(lap_info.get("lap_number", lap_key), 0)
                    duration = finite_float(lap_info.get("lap_elapsed_max"))
                    if duration is None:
                        min_t = finite_float(lap_info.get("session_time_min"))
                        max_t = finite_float(lap_info.get("session_time_max"))
                        duration = (max_t - min_t) if min_t is not None and max_t is not None and max_t >= min_t else None
                    completed = (
                        last_lap_number is not None and lap_number < last_lap_number
                    ) or (
                        recording_ended
                        and lap_number == last_lap_number
                        and finite_float(lap_info.get("progress_end")) is not None
                        and finite_float(lap_info.get("progress_end")) >= 0.98
                    )
                    validation = validate_lap(
                        {
                            "lapId": f"{session_dir.name}:{lap_number}",
                            "lapNumber": lap_number,
                            "sampleCount": finite_int(lap_info.get("sample_count"), 0),
                            "durationSeconds": duration,
                            "progressStart": lap_info.get("progress_start"),
                            "progressEnd": lap_info.get("progress_end"),
                            "progressMin": lap_info.get("progress_min"),
                            "progressMax": lap_info.get("progress_max"),
                            "maxGapSeconds": lap_info.get("max_gap_seconds"),
                            "timestampInversions": lap_info.get("timestamp_inversions"),
                            "completed": completed,
                        }
                    )
                    if validation.status != "VALID":
                        continue
                    laps.append(
                        LapDescriptor(
                            lap_id=self._recording_lap_id(session_dir.name, lap_number),
                            source="recording_jsonl",
                            driver_id="player_1",
                            lap_number=lap_number,
                            track=metadata.get("track"),
                            lap_time=duration,
                            sample_count=finite_int(lap_info.get("sample_count"), 0),
                            session_id=session_dir.name,
                            started_at=metadata.get("startedAt"),
                            metadata={
                                "sessionMetadata": metadata.get("metadata", {}),
                                "playerPath": str(player_path),
                                "progressStart": lap_info.get("progress_start"),
                                "progressEnd": lap_info.get("progress_end"),
                                "progressMin": lap_info.get("progress_min"),
                                "progressMax": lap_info.get("progress_max"),
                                "recordingRoot": str(recordings_root),
                                "validation": validation.to_api(),
                            },
                        )
                    )
                    self._recorded_lap_paths[laps[-1].lap_id] = session_dir
                continue

            try:
                if player_path.stat().st_size > MAX_UNINDEXED_RECORDING_SCAN_BYTES:
                    logger.debug("Skipping unindexed recording in assisted analysis lap list: %s", player_path)
                    continue
            except OSError:
                continue
            scanned_laps = self._scan_recording_laps(session_dir, player_path, metadata, recordings_root)
            laps.extend(scanned_laps)
            for lap in scanned_laps:
                self._recorded_lap_paths[lap.lap_id] = session_dir
        return laps

    def _load_recorded_lap(self, lap_id: str) -> Tuple[LapDescriptor, pd.DataFrame]:
        parts = lap_id.split("__", 2)
        if len(parts) != 3:
            raise ValueError(f"Invalid recording lap id: {lap_id}")
        _, session_id, lap_text = parts
        session_dir = self._recorded_lap_paths.get(lap_id) or self._find_recording_session_dir(session_id)
        player_path = session_dir / "player.jsonl"
        if not player_path.exists():
            raise FileNotFoundError(f"Recording player stream not found: {player_path}")

        rows = []
        lap_number = finite_int(lap_text, 0)
        metadata = self._read_json(session_dir / "metadata.json")
        for payload in self._read_jsonl(player_path):
            sample = payload.get("sample", payload)
            sample_lap = finite_int(sample.get("lap_number", sample.get("lap")), 0)
            if sample_lap != lap_number:
                continue
            rows.append(self._flatten_recording_sample(payload))
        if not rows:
            raise FileNotFoundError(f"Lap {lap_number} not found in recording {session_id}")

        descriptor = self._recording_descriptor_from_session(session_dir, lap_number, metadata) or LapDescriptor(
            lap_id=lap_id,
            source="recording_jsonl",
            driver_id="player_1",
            lap_number=lap_number,
            track=metadata.get("track"),
            session_id=session_id,
            started_at=metadata.get("startedAt"),
            metadata={"playerPath": str(player_path)},
        )
        df = normalize_lap_dataframe(pd.DataFrame(rows), track_length=self._active_track_length())
        descriptor.sample_count = len(df)
        descriptor.lap_time = descriptor.lap_time or self._duration(df)
        descriptor.track = descriptor.track or metadata.get("track") or self._active_track_name()
        return descriptor, df

    def _recording_descriptor_from_session(self, session_dir: Path, lap_number: int, metadata: Dict) -> Optional[LapDescriptor]:
        index = self._read_json(session_dir / "session-index.json")
        lap_info = None
        if isinstance(index, dict) and isinstance(index.get("laps"), dict):
            lap_info = index["laps"].get(str(lap_number))
        if not isinstance(lap_info, dict):
            return None

        duration = finite_float(lap_info.get("lap_elapsed_max"))
        if duration is None:
            min_t = finite_float(lap_info.get("session_time_min"))
            max_t = finite_float(lap_info.get("session_time_max"))
            duration = (max_t - min_t) if min_t is not None and max_t is not None and max_t >= min_t else None
        player_path = session_dir / "player.jsonl"
        return LapDescriptor(
            lap_id=f"rec__{safe_fragment(session_dir.name)}__{lap_number}",
            source="recording_jsonl",
            driver_id="player_1",
            lap_number=lap_number,
            track=metadata.get("track"),
            lap_time=duration,
            sample_count=finite_int(lap_info.get("sample_count"), 0),
            session_id=session_dir.name,
            started_at=metadata.get("startedAt"),
            metadata={
                "sessionMetadata": metadata.get("metadata", {}),
                "playerPath": str(player_path),
                "progressStart": lap_info.get("progress_start"),
                "progressEnd": lap_info.get("progress_end"),
                "progressMin": lap_info.get("progress_min"),
                "progressMax": lap_info.get("progress_max"),
            },
        )

    def _list_buffer_laps(self) -> List[LapDescriptor]:
        samples = self.buffer_provider().get_samples()
        grouped: Dict[int, List[TelemetrySample]] = {}
        for sample in samples:
            grouped.setdefault(int(sample.lap), []).append(sample)

        laps: List[LapDescriptor] = []
        for lap_number, lap_samples in grouped.items():
            if len(lap_samples) < 5:
                continue
            rows = self._samples_to_projected_rows(lap_samples)
            df = normalize_lap_dataframe(pd.DataFrame(rows), track_length=self._active_track_length())
            laps.append(
                LapDescriptor(
                    lap_id=f"buffer__{lap_number}",
                    source="buffer",
                    driver_id="player_1",
                    lap_number=lap_number,
                    track=self._active_track_name(),
                    lap_time=self._duration(df),
                    sample_count=len(df),
                    metadata={"volatile": True},
                )
            )
        return laps

    def _load_buffer_lap(self, lap_id: str) -> Tuple[LapDescriptor, pd.DataFrame]:
        parts = lap_id.split("__", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid buffer lap id: {lap_id}")
        lap_number = finite_int(parts[1], 0)
        samples = [sample for sample in self.buffer_provider().get_samples() if int(sample.lap) == lap_number]
        if not samples:
            raise FileNotFoundError(f"Buffer lap not found: {lap_id}")
        rows = self._samples_to_projected_rows(samples)
        df = normalize_lap_dataframe(pd.DataFrame(rows), track_length=self._active_track_length())
        descriptor = LapDescriptor(
            lap_id=lap_id,
            source="buffer",
            driver_id="player_1",
            lap_number=lap_number,
            track=self._active_track_name(),
            lap_time=self._duration(df),
            sample_count=len(df),
            metadata={"volatile": True},
        )
        return descriptor, df

    def _scan_recording_laps(
        self,
        session_dir: Path,
        player_path: Path,
        metadata: Dict,
        recordings_root: Optional[Path] = None,
    ) -> List[LapDescriptor]:
        grouped: Dict[int, Dict[str, object]] = {}
        for payload in self._read_jsonl(player_path):
            sample = payload.get("sample", payload)
            lap_number = finite_int(sample.get("lap_number", sample.get("lap")), 0)
            item = grouped.setdefault(
                lap_number,
                {
                    "count": 0,
                    "session_min": None,
                    "session_max": None,
                    "progress_start": None,
                    "progress_end": None,
                    "progress_min": None,
                    "progress_max": None,
                },
            )
            item["count"] = int(item["count"]) + 1
            session_time = finite_float(sample.get("sessionTime", payload.get("sessionTime")))
            if session_time is not None:
                item["session_min"] = session_time if item["session_min"] is None else min(float(item["session_min"]), session_time)
                item["session_max"] = session_time if item["session_max"] is None else max(float(item["session_max"]), session_time)
            progress = finite_float(
                sample.get(
                    "lapProgress",
                    sample.get("p", sample.get("spline_t", sample.get("normalizedSplinePosition", sample.get("splinePosition")))),
                )
            )
            if progress is not None:
                progress = max(0.0, min(1.0, progress))
                if item["progress_start"] is None:
                    item["progress_start"] = progress
                item["progress_end"] = progress
                item["progress_min"] = progress if item["progress_min"] is None else min(float(item["progress_min"]), progress)
                item["progress_max"] = progress if item["progress_max"] is None else max(float(item["progress_max"]), progress)

        laps = []
        last_lap_number = max(grouped) if grouped else None
        for lap_number, item in grouped.items():
            duration = None
            if item["session_min"] is not None and item["session_max"] is not None:
                duration = float(item["session_max"]) - float(item["session_min"])
            completed = last_lap_number is not None and lap_number < last_lap_number
            validation = validate_lap(
                {
                    "lapId": f"{session_dir.name}:{lap_number}",
                    "lapNumber": lap_number,
                    "sampleCount": int(item["count"]),
                    "durationSeconds": duration,
                    "progressStart": item["progress_start"],
                    "progressEnd": item["progress_end"],
                    "progressMin": item["progress_min"],
                    "progressMax": item["progress_max"],
                    "completed": completed,
                }
            )
            if validation.status != "VALID":
                continue
            laps.append(
                LapDescriptor(
                    lap_id=self._recording_lap_id(session_dir.name, lap_number),
                    source="recording_jsonl",
                    driver_id="player_1",
                    lap_number=lap_number,
                    track=metadata.get("track"),
                    lap_time=duration,
                    sample_count=int(item["count"]),
                    session_id=session_dir.name,
                    started_at=metadata.get("startedAt"),
                    metadata={
                        "playerPath": str(player_path),
                        "sessionMetadata": metadata.get("metadata", {}),
                        "recordingRoot": str(recordings_root) if recordings_root else None,
                        "validation": validation.to_api(),
                    },
                )
            )
        return laps

    def _find_recording_session_dir(self, session_fragment: str) -> Path:
        for recordings_root in reversed(self.recordings_roots):
            direct = recordings_root / session_fragment
            if (direct / "player.jsonl").exists():
                return direct
            if not recordings_root.exists():
                continue
            for session_dir in recordings_root.iterdir():
                if (
                    session_dir.is_dir()
                    and safe_fragment(session_dir.name) == session_fragment
                    and (session_dir / "player.jsonl").exists()
                ):
                    return session_dir
        return self.recordings_root / session_fragment

    def _flatten_recording_sample(self, payload: Dict) -> Dict:
        sample = dict(payload.get("sample", payload))
        sample.setdefault("timestamp", payload.get("timestamp"))
        sample.setdefault("sessionTime", payload.get("sessionTime"))
        sample.setdefault("track", payload.get("track"))
        return sample

    def _samples_to_projected_rows(self, samples: Iterable[TelemetrySample]) -> List[Dict]:
        runtime_state = self.runtime_state_provider()
        projection = runtime_state.projection_engine
        previous_s = None
        rows = []
        for sample in samples:
            row = {
                "timestamp": sample.timestamp_ms,
                "world_x": sample.worldPositionX,
                "world_y": sample.worldPositionY,
                "world_z": sample.worldPositionZ,
                "speedKmh": sample.speed,
                "throttle": sample.throttle,
                "brake": sample.brake,
                "steering": sample.steering,
                "gear": sample.gear,
                "rpm": sample.rpm,
                "yaw": sample.yaw,
                "sessionTime": sample.sessionTime,
                "lap_number": sample.lap,
                "lateral_g": sample.accelX,
                "longitudinal_g": sample.accelZ,
                "p": sample.normalizedSplinePosition,
            }
            if projection:
                projected = projection.project_car(sample.worldPositionX, sample.worldPositionZ, previous_s=previous_s)
                previous_s = projected.get("distanceAlongTrack")
                row.update(
                    {
                        "s": projected.get("distanceAlongTrack"),
                        "L": projected.get("lateralOffset"),
                        "x": projected.get("mapPosition", {}).get("x"),
                        "z": sample.worldPositionZ,
                    }
                )
            else:
                row.update({"s": sample.normalizedSplinePosition * max(self._active_track_length() or 0.0, 1.0)})
            rows.append(row)
        return rows

    def _resolve_path(self, path_value) -> Optional[Path]:
        if not path_value:
            return None
        path = Path(str(path_value))
        if path.is_absolute():
            return path
        return (self.repo_root / path).resolve()

    @staticmethod
    def _recording_lap_id(session_name: str, lap_number: int) -> str:
        return f"rec__{safe_fragment(session_name)}__{lap_number}"

    @staticmethod
    def _unique_paths(paths: Sequence[Path]) -> List[Path]:
        unique: List[Path] = []
        seen = set()
        for path in paths:
            resolved = Path(path).resolve()
            key = str(resolved).lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(resolved)
        return unique

    def _active_track_length(self) -> Optional[float]:
        track = self.runtime_state_provider().track_data or {}
        return finite_float(track.get("trackLength", track.get("track_length")))

    def _active_track_name(self) -> Optional[str]:
        state = self.runtime_state_provider()
        track = state.track_data or {}
        return track.get("trackName") or track.get("name") or state.current_track_name

    @staticmethod
    def _duration(df: pd.DataFrame) -> Optional[float]:
        if df.empty or "elapsed_s" not in df:
            return None
        value = float(df["elapsed_s"].max() - df["elapsed_s"].min())
        return value if value >= 0 else None

    @staticmethod
    def _read_json(path: Path) -> Dict:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    @staticmethod
    def _read_jsonl(path: Path):
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    @staticmethod
    def _parquet_sample_count(path: Optional[Path]) -> int:
        if not path or not path.exists():
            return 0
        try:
            import pyarrow.parquet as pq

            return int(pq.ParquetFile(path).metadata.num_rows)
        except Exception:
            return 0

    def _validate_parquet_lap_for_listing(self, path: Optional[Path], lap_number: int, lap_time: Optional[float]) -> Optional[Dict]:
        if not path or not path.exists():
            return None
        try:
            raw = pd.read_parquet(path)
            df = normalize_lap_dataframe(raw, track_length=self._active_track_length())
        except Exception as exc:
            logger.debug("Assisted analysis DuckDB lap validation failed for %s: %s", path, exc)
            return None

        progress = df["p"] if "p" in df else pd.Series(dtype=float)
        duration = lap_time or self._duration(df)
        validation = validate_lap(
            {
                "lapId": str(path),
                "lapNumber": lap_number,
                "sampleCount": len(df),
                "durationSeconds": duration,
                "progressStart": float(progress.iloc[0]) if len(progress) else None,
                "progressEnd": float(progress.iloc[-1]) if len(progress) else None,
                "progressMin": float(progress.min()) if len(progress) else None,
                "progressMax": float(progress.max()) if len(progress) else None,
                "completed": True,
            }
        )
        return validation.to_api() if validation.status == "VALID" else None
