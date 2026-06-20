import json
import math
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from ..data_quality.lap_validation import validate_lap


MAX_EAGER_INDEX_BYTES = 8 * 1024 * 1024
INDEX_FILENAME = "session-index.json"
INDEX_VERSION = 3


def _safe_fragment(value: Any) -> str:
    text = str(value or "").strip()
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("._") or "session"


def _number(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _seconds(value: Any) -> Optional[float]:
    number = _number(value)
    if number is None:
        return None
    return number / 1000.0 if number > 10_000.0 else number


def _lap_number(sample: Dict[str, Any]) -> Optional[int]:
    value = _number(sample.get("lap_number", sample.get("lap")))
    return int(value) if value is not None else None


def _lap_elapsed(sample: Dict[str, Any]) -> Optional[float]:
    for key in ("lap_time", "lapTime", "currentLapTime"):
        value = _seconds(sample.get(key))
        if value is not None and value >= 0.0:
            return value
    return None


def _session_time(sample: Dict[str, Any]) -> Optional[float]:
    for key in ("sessionTime", "session_time"):
        value = _number(sample.get(key))
        if value is not None:
            return value
    return None


def _timestamp(sample: Dict[str, Any]) -> Optional[float]:
    value = _number(sample.get("timestamp"))
    if value is None:
        return None
    return value / 1000.0 if value > 100_000_000_000.0 else value


def _speed_kmh(sample: Dict[str, Any]) -> Optional[float]:
    value = _number(sample.get("speedKmh"))
    if value is not None:
        return value
    value = _number(sample.get("speed"))
    return value * 3.6 if value is not None else None


def _progress(sample: Dict[str, Any]) -> Optional[float]:
    for key in ("lapProgress", "p", "spline_t", "normalizedSplinePosition", "splinePosition"):
        value = _number(sample.get(key))
        if value is not None:
            return max(0.0, min(1.0, value))
    return None


def is_assetto_lap_counter_lag_frame(
    sample: Dict[str, Any],
    previous_lap_elapsed: Optional[float],
) -> bool:
    lap_elapsed = _lap_elapsed(sample)
    progress = _progress(sample)
    return bool(
        previous_lap_elapsed is not None
        and previous_lap_elapsed >= 10.0
        and lap_elapsed is not None
        and lap_elapsed <= 1.0
        and progress is not None
        and progress <= 0.02
    )


@dataclass
class _LapAggregate:
    lap_number: int
    sample_count: int = 0
    lap_elapsed_max: Optional[float] = None
    session_time_min: Optional[float] = None
    session_time_max: Optional[float] = None
    timestamp_min: Optional[float] = None
    timestamp_max: Optional[float] = None
    speed_sum: float = 0.0
    speed_count: int = 0
    speed_max: Optional[float] = None
    progress_start: Optional[float] = None
    progress_end: Optional[float] = None
    progress_min: Optional[float] = None
    progress_max: Optional[float] = None
    max_gap_seconds: Optional[float] = None
    timestamp_inversions: int = 0
    previous_order_time: Optional[float] = None
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None

    def add(self, sample: Dict[str, Any], start_offset: Optional[int] = None, end_offset: Optional[int] = None) -> bool:
        lap_elapsed = _lap_elapsed(sample)
        progress = _progress(sample)
        if self.sample_count > 0 and is_assetto_lap_counter_lag_frame(sample, self.lap_elapsed_max):
            return False

        self.sample_count += 1
        if start_offset is not None and self.start_offset is None:
            self.start_offset = start_offset
        if end_offset is not None:
            self.end_offset = end_offset

        if lap_elapsed is not None:
            self.lap_elapsed_max = max(self.lap_elapsed_max or lap_elapsed, lap_elapsed)

        session_time = _session_time(sample)
        if session_time is not None:
            self.session_time_min = min(
                self.session_time_min if self.session_time_min is not None else session_time,
                session_time,
            )
            self.session_time_max = max(
                self.session_time_max if self.session_time_max is not None else session_time,
                session_time,
            )

        timestamp = _timestamp(sample)
        if timestamp is not None:
            self.timestamp_min = min(
                self.timestamp_min if self.timestamp_min is not None else timestamp,
                timestamp,
            )
            self.timestamp_max = max(
                self.timestamp_max if self.timestamp_max is not None else timestamp,
                timestamp,
            )

        order_time = session_time if session_time is not None else timestamp
        if order_time is not None and self.previous_order_time is not None:
            gap = order_time - self.previous_order_time
            if gap < -1e-3:
                self.timestamp_inversions += 1
            elif gap >= 0.0:
                self.max_gap_seconds = max(self.max_gap_seconds or 0.0, gap)
        if order_time is not None:
            self.previous_order_time = order_time

        speed = _speed_kmh(sample)
        if speed is not None:
            self.speed_sum += speed
            self.speed_count += 1
            self.speed_max = max(self.speed_max or speed, speed)

        if progress is not None:
            if self.progress_start is None:
                self.progress_start = progress
            self.progress_end = progress
            self.progress_min = min(
                self.progress_min if self.progress_min is not None else progress,
                progress,
            )
            self.progress_max = max(
                self.progress_max if self.progress_max is not None else progress,
                progress,
            )
        return True

    def summary(self, completed: bool, session_id: Optional[str] = None) -> Dict[str, Any]:
        duration = self.lap_elapsed_max
        if duration is None and self.session_time_min is not None and self.session_time_max is not None:
            duration = self.session_time_max - self.session_time_min
        if duration is None and self.timestamp_min is not None and self.timestamp_max is not None:
            duration = self.timestamp_max - self.timestamp_min

        progress_span = (
            self.progress_max - self.progress_min
            if self.progress_min is not None and self.progress_max is not None
            else None
        )
        validation = validate_lap(
            {
                "lapId": f"{session_id or 'session'}:{self.lap_number}",
                "lapNumber": self.lap_number,
                "sampleCount": self.sample_count,
                "durationSeconds": duration,
                "progressStart": self.progress_start,
                "progressEnd": self.progress_end,
                "progressMin": self.progress_min,
                "progressMax": self.progress_max,
                "maxGapSeconds": self.max_gap_seconds,
                "timestampInversions": self.timestamp_inversions,
                "completed": completed,
            }
        )
        canonical_lap_id = f"rec__{_safe_fragment(session_id or 'session')}__{self.lap_number}"
        duration_api = round(duration, 3) if duration is not None else None
        return {
            "lapNumber": self.lap_number,
            "sampleCount": self.sample_count,
            "duration": duration_api,
            "durationSeconds": validation.durationSeconds,
            "lapTime": duration_api,
            "maxSpeedKmh": round(self.speed_max, 2) if self.speed_max is not None else None,
            "avgSpeedKmh": round(self.speed_sum / self.speed_count, 2) if self.speed_count else None,
            "progressStart": self.progress_start,
            "progressEnd": self.progress_end,
            "coveragePercent": validation.coveragePercent,
            "completed": completed,
            "valid": validation.status == "VALID",
            "lapId": canonical_lap_id,
            "sessionLapKey": validation.lapId,
            "validationStatus": validation.status,
            "reliabilityStatus": validation.status,
            "acceptedByPhase13": validation.status == "VALID",
            "issues": list(validation.issues),
            "maxGapSeconds": self.max_gap_seconds,
            "timestampInversions": self.timestamp_inversions,
        }


@dataclass
class _SessionIndex:
    offset: int = 0
    sample_count: int = 0
    track: Optional[str] = None
    timestamp_min: Optional[float] = None
    timestamp_max: Optional[float] = None
    laps: Dict[int, _LapAggregate] = field(default_factory=dict)


class SessionRepository:
    """Incremental, read-only index over player JSONL recordings."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._indexes: Dict[str, _SessionIndex] = {}
        self._lock = threading.RLock()

    def list_sessions(self, limit: int = 30) -> List[Dict[str, Any]]:
        max_items = max(1, min(int(limit), 200))
        directories = sorted(
            (directory for directory in self.root.iterdir() if directory.is_dir()),
            key=lambda directory: directory.name,
            reverse=True,
        )[:max_items]
        sessions = [
            summary
            for directory in directories
            for summary in [self.session_summary(directory.name, allow_large_scan=False)]
            if summary is not None
        ]
        sessions.sort(key=lambda item: item.get("startedAt") or item["sessionId"], reverse=True)
        return sessions[:max_items]

    def session_summary(self, session_id: str, allow_large_scan: bool = True) -> Optional[Dict[str, Any]]:
        directory = self._session_dir(session_id)
        if not directory.exists():
            return None

        player_path = directory / "player.jsonl"
        with self._lock:
            index = self._indexes.get(session_id)
            if index is None:
                index = self._load_index(directory) or _SessionIndex()
                self._indexes[session_id] = index
            file_size = player_path.stat().st_size if player_path.exists() else 0
            if file_size < index.offset:
                index = _SessionIndex()
                self._indexes[session_id] = index
            can_scan = allow_large_scan or file_size <= MAX_EAGER_INDEX_BYTES or index.offset > 0
            if can_scan and self._update_index(player_path, index):
                self._persist_index(directory, index)

            metadata = self._read_json(directory / "metadata.json") or {}
            lap_numbers = sorted(index.laps)
            last_lap_number = lap_numbers[-1] if lap_numbers else None
            recording_ended = bool(metadata.get("endedAt"))
            laps = []
            for lap_number in lap_numbers:
                aggregate = index.laps[lap_number]
                completed = (
                    last_lap_number is not None
                    and lap_number < last_lap_number
                ) or (
                    recording_ended
                    and lap_number == last_lap_number
                    and aggregate.progress_end is not None
                    and aggregate.progress_end >= 0.98
                )
                laps.append(aggregate.summary(completed=completed, session_id=session_id))

            valid_durations = [
                lap["duration"]
                for lap in laps
                if lap["valid"] and lap["duration"] is not None
            ]
            duration = None
            if index.timestamp_min is not None and index.timestamp_max is not None:
                duration = max(0.0, index.timestamp_max - index.timestamp_min)

            nested_metadata = metadata.get("metadata") or {}
            car = (
                metadata.get("car")
                or metadata.get("carModel")
                or nested_metadata.get("car")
                or nested_metadata.get("carModel")
                or nested_metadata.get("car_model")
            )
            return {
                "sessionId": session_id,
                "track": metadata.get("track") or index.track,
                "car": car,
                "startedAt": metadata.get("startedAt"),
                "endedAt": metadata.get("endedAt"),
                "source": nested_metadata.get("source"),
                "sampleRateHz": metadata.get("playerRecordHz"),
                "sampleCount": index.sample_count or int(metadata.get("playerSamplesWritten") or 0),
                "duration": round(duration, 3) if duration is not None else None,
                "lapCount": len(laps),
                "completedLapCount": sum(1 for lap in laps if lap["completed"]),
                "validLapCount": sum(1 for lap in laps if lap["valid"]),
                "invalidLapCount": sum(
                    1 for lap in laps if lap["validationStatus"] == "INVALID"
                ),
                "partialLapCount": sum(
                    1 for lap in laps if lap["validationStatus"] == "PARTIAL"
                ),
                "bestLapTime": min(valid_durations, default=None),
                "indexed": file_size == 0 or index.offset > 0,
                "laps": laps,
            }

    def lap_detail(
        self,
        session_id: str,
        lap_number: int,
        max_samples: int = 36_000,
    ) -> Optional[Dict[str, Any]]:
        summary = self.session_summary(session_id, allow_large_scan=True)
        if summary is None:
            return None

        player_path = self._session_dir(session_id) / "player.jsonl"
        aggregate = self._indexes.get(session_id, _SessionIndex()).laps.get(int(lap_number))
        total_sample_count = aggregate.sample_count if aggregate else 0
        sample_stride = max(1, math.ceil(total_sample_count / max(1, int(max_samples))))
        samples = []
        last_sample = None
        matched_index = 0
        for row in self._iter_player_rows(
            player_path,
            start_offset=aggregate.start_offset if aggregate else None,
            end_offset=aggregate.end_offset if aggregate else None,
        ):
            sample = row["sample"]
            if _lap_number(sample) != int(lap_number):
                continue
            last_sample = sample
            if matched_index % sample_stride == 0:
                samples.append(sample)
            matched_index += 1
        if last_sample is not None and (not samples or samples[-1] is not last_sample):
            samples.append(last_sample)
        if not samples:
            return None

        lap_summary = next(
            (lap for lap in summary["laps"] if lap["lapNumber"] == int(lap_number)),
            None,
        )
        return {
            "sessionId": session_id,
            "lapNumber": int(lap_number),
            "summary": lap_summary,
            "totalSampleCount": matched_index,
            "returnedSampleCount": len(samples),
            "sampleStride": sample_stride,
            "truncated": sample_stride > 1,
            "samples": samples,
        }

    def _session_dir(self, session_id: str) -> Path:
        if not session_id or Path(session_id).name != session_id:
            raise ValueError("Invalid session id")
        candidate = (self.root / session_id).resolve()
        root = self.root.resolve()
        if candidate.parent != root:
            raise ValueError("Invalid session path")
        return candidate

    @staticmethod
    def _update_index(path: Path, index: _SessionIndex) -> bool:
        if not path.exists():
            return False
        changed = False
        with path.open("rb") as handle:
            handle.seek(index.offset)
            while True:
                line_start = handle.tell()
                line = handle.readline()
                if not line:
                    break
                if not line.endswith(b"\n"):
                    handle.seek(line_start)
                    break
                index.offset = handle.tell()
                try:
                    payload = json.loads(line.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                sample = payload.get("sample")
                if not isinstance(sample, dict):
                    continue
                lap_number = _lap_number(sample)
                if lap_number is None:
                    continue
                index.laps.setdefault(lap_number, _LapAggregate(lap_number)).add(
                    sample,
                    start_offset=line_start,
                    end_offset=index.offset,
                )
                index.sample_count += 1
                changed = True

                timestamp = _timestamp(sample)
                if timestamp is not None:
                    index.timestamp_min = min(
                        index.timestamp_min if index.timestamp_min is not None else timestamp,
                        timestamp,
                    )
                    index.timestamp_max = max(
                        index.timestamp_max if index.timestamp_max is not None else timestamp,
                        timestamp,
                    )
                track = payload.get("track")
                if isinstance(track, str) and track.strip():
                    index.track = track.strip()
        return changed

    @staticmethod
    def _load_index(directory: Path) -> Optional[_SessionIndex]:
        payload = SessionRepository._read_json(directory / INDEX_FILENAME)
        if not payload:
            return None
        if int(payload.get("version") or 0) != INDEX_VERSION:
            return None
        try:
            laps = {
                int(number): _LapAggregate(**lap)
                for number, lap in (payload.get("laps") or {}).items()
            }
            return _SessionIndex(
                offset=int(payload.get("offset") or 0),
                sample_count=int(payload.get("sampleCount") or 0),
                track=payload.get("track"),
                timestamp_min=_number(payload.get("timestampMin")),
                timestamp_max=_number(payload.get("timestampMax")),
                laps=laps,
            )
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _persist_index(directory: Path, index: _SessionIndex):
        path = directory / INDEX_FILENAME
        temp_path = directory / f"{INDEX_FILENAME}.tmp"
        payload = {
            "version": INDEX_VERSION,
            "offset": index.offset,
            "sampleCount": index.sample_count,
            "track": index.track,
            "timestampMin": index.timestamp_min,
            "timestampMax": index.timestamp_max,
            "laps": {
                str(number): vars(aggregate)
                for number, aggregate in index.laps.items()
            },
        }
        try:
            temp_path.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            temp_path.replace(path)
        except OSError:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _read_json(path: Path) -> Optional[Dict[str, Any]]:
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    @staticmethod
    def _iter_player_rows(
        path: Path,
        start_offset: Optional[int] = None,
        end_offset: Optional[int] = None,
    ) -> Iterable[Dict[str, Any]]:
        if not path.exists():
            return []

        def rows():
            with path.open("rb") as handle:
                if start_offset is not None:
                    handle.seek(start_offset)
                while True:
                    if end_offset is not None and handle.tell() >= end_offset:
                        break
                    line = handle.readline()
                    if not line:
                        break
                    try:
                        payload = json.loads(line.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        continue
                    sample = payload.get("sample")
                    if isinstance(sample, dict):
                        yield payload

        return rows()
