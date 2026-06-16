import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

import pandas as pd

from .telemetry_reader import TelemetryReader
from .telemetry_models import TelemetrySample
from ..assetto_shared_memory_gate import shared_memory_gate_status
from ..assetto_adapter import AssettoAdapter


logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _safe_float(value: Any, fallback: float = 0.0) -> float:
    try:
        number = float(value)
        if number == number and number not in (float("inf"), float("-inf")):
            return number
    except Exception:
        pass
    return fallback


def _canonical_source_name(source: str) -> str:
    normalized = (source or "auto").strip().lower().replace("-", "_")
    aliases = {
        "ac": "assetto_corsa",
        "assetto": "assetto_corsa",
        "assetto_corsa_shared_memory": "assetto_corsa",
        "csv": "replay",
        "fixture": "replay",
        "debug": "replay",
    }
    return aliases.get(normalized, normalized)


def _normalize_telemetry_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.str.strip().str.lower()
    rename = {
        "time": "session_time",
        "t": "session_time",
        "x": "pos_x",
        "y": "pos_y",
        "z": "pos_z",
        "worldpositionx": "pos_x",
        "worldpositiony": "pos_y",
        "worldpositionz": "pos_z",
        "normalizedsplineposition": "normalized_spline_pos",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    if "pos_x" not in df.columns or "pos_z" not in df.columns:
        raise ValueError("Telemetry must contain world X/Z columns: pos_x/pos_z or worldPositionX/worldPositionZ")

    if "pos_y" not in df.columns:
        df["pos_y"] = 0.0
    if "session_time" not in df.columns:
        df["session_time"] = range(len(df))
    if "speed" not in df.columns:
        df["speed"] = 0.0
    return df


def _lap_distance(lap_df: pd.DataFrame) -> float:
    if len(lap_df) < 2:
        return 0.0

    x = lap_df["pos_x"].astype(float).to_numpy()
    z = lap_df["pos_z"].astype(float).to_numpy()
    return float((((x[1:] - x[:-1]) ** 2 + (z[1:] - z[:-1]) ** 2) ** 0.5).sum())


def _lap_closure_gap(lap_df: pd.DataFrame) -> float:
    if len(lap_df) < 2:
        return 0.0

    start_x = _safe_float(lap_df.iloc[0].get("pos_x"))
    start_z = _safe_float(lap_df.iloc[0].get("pos_z"))
    end_x = _safe_float(lap_df.iloc[-1].get("pos_x"))
    end_z = _safe_float(lap_df.iloc[-1].get("pos_z"))
    return float(((end_x - start_x) ** 2 + (end_z - start_z) ** 2) ** 0.5)


def _valid_lap_frames(df: pd.DataFrame) -> List[Tuple[int, float, float, pd.DataFrame]]:
    if "lap" not in df.columns:
        distance = _lap_distance(df)
        return [(0, distance, _lap_closure_gap(df), df.copy())] if distance > 500.0 else []

    candidates: List[Tuple[int, float, float, pd.DataFrame]] = []
    for lap, lap_df in df.groupby("lap", sort=True):
        if len(lap_df) < 20:
            continue
        distance = _lap_distance(lap_df)
        if distance > 500.0:
            candidates.append((int(_safe_float(lap)), distance, _lap_closure_gap(lap_df), lap_df.copy()))

    if not candidates:
        distance = _lap_distance(df)
        return [(0, distance, _lap_closure_gap(df), df.copy())] if distance > 500.0 else []

    distances = sorted(distance for _, distance, _, _ in candidates)
    median_distance = distances[len(distances) // 2]
    max_distance_error = max(0.12 * median_distance, 250.0)
    max_closure_gap = max(50.0, 0.03 * median_distance)
    valid = [
        item for item in candidates
        if abs(item[1] - median_distance) <= max_distance_error and item[2] <= max_closure_gap
    ]
    return valid if valid else candidates


def telemetry_samples_from_dataframe(
    df: pd.DataFrame,
    source_name: str = "recorded",
    lap_mode: str = "representative",
) -> List[TelemetrySample]:
    if df.empty:
        return []

    df = _normalize_telemetry_dataframe(df)
    if lap_mode == "all":
        lap_frames = [lap_df.copy() for _, _, _, lap_df in _valid_lap_frames(df)]
        lap_df = pd.concat(lap_frames, ignore_index=True) if lap_frames else df
    elif lap_mode == "representative":
        candidates = _valid_lap_frames(df)
        if candidates:
            distances = sorted(distance for _, distance, _, _ in candidates)
            median_distance = distances[len(distances) // 2]
            _, _, _, lap_df = min(candidates, key=lambda item: abs(item[1] - median_distance))
            lap_df = lap_df.copy()
        else:
            lap_df = df
    else:
        lap_df = df

    samples: List[TelemetrySample] = []
    for _, row in lap_df.iterrows():
        session_time = _safe_float(row.get("session_time"))
        samples.append(
            TelemetrySample(
                timestamp=session_time,
                worldPositionX=_safe_float(row.get("pos_x")),
                worldPositionY=_safe_float(row.get("pos_y")),
                worldPositionZ=_safe_float(row.get("pos_z")),
                speed=_safe_float(row.get("speed")),
                yaw=_safe_float(row.get("yaw", row.get("heading", 0.0))),
                normalizedSplinePosition=_safe_float(row.get("normalized_spline_pos", 0.0)),
                carId=int(_safe_float(row.get("car_id", 0))),
                sector=int(_safe_float(row.get("sector", 0))),
                sessionTime=session_time,
                lap=int(_safe_float(row.get("lap", 1))),
                throttle=_safe_float(row.get("throttle", 0.0)),
                brake=_safe_float(row.get("brake", 0.0)),
                steering=_safe_float(row.get("steering", 0.0)),
                gear=int(_safe_float(row.get("gear", 0))),
                rpm=int(_safe_float(row.get("rpm", 0))),
                accelX=_safe_float(row.get("accel_x", 0.0)),
                accelY=_safe_float(row.get("accel_y", 0.0)),
                accelZ=_safe_float(row.get("accel_z", 0.0)),
            )
        )

    logger.info("Loaded %s telemetry samples from %s (%s)", len(samples), source_name, lap_mode)
    return samples


class PollingTelemetryReader(TelemetryReader):
    source_name = "mock"
    active_reader_name = "PollingTelemetryReader"

    def read_sample(self) -> Optional[TelemetrySample]:
        return None

    def read_samples(self) -> Iterator[TelemetrySample]:
        while True:
            sample = self.read_sample()
            if sample:
                yield sample
            time.sleep(1 / 60)

    def stop(self):
        pass


class ACSharedMemoryReader(PollingTelemetryReader):
    source_name = "assetto_corsa"
    active_reader_name = "ACSharedMemoryReader"

    def __init__(self):
        self.adapter = AssettoAdapter()
        self.connected = False
        self.latest_track_name: Optional[str] = None
        self.latest_track_config: Optional[str] = None
        self.latest_car_model: Optional[str] = None
        self.latest_track_length: Optional[float] = None
        self.latest_game_code: Optional[str] = "assetto_corsa"
        self.latest_ac_install_path: Optional[str] = None
        self.latest_shared_memory_gate_status: Dict[str, Any] = {}
        self._next_connect_attempt_at = 0.0
        self._last_gate_log_at = 0.0

    def connect(self) -> bool:
        if self.connected and self.adapter.is_connected:
            return True
        if time.monotonic() < self._next_connect_attempt_at:
            return False

        gate_status = shared_memory_gate_status()
        self.latest_shared_memory_gate_status = gate_status
        if not gate_status.get("allowed", True):
            self.connected = False
            self._next_connect_attempt_at = time.monotonic() + 2.0
            if time.monotonic() - self._last_gate_log_at > 10.0:
                logger.info(
                    "Assetto Corsa shared memory gate is waiting for process: %s",
                    ", ".join(gate_status.get("processNames") or []),
                )
                self._last_gate_log_at = time.monotonic()
            return False

        self.connected = self.adapter.connect()
        if not self.connected:
            self._next_connect_attempt_at = time.monotonic() + 1.0
        return self.connected

    def read_sample(self) -> Optional[TelemetrySample]:
        if not self.connect():
            return None

        data = self.adapter.poll()
        if not data:
            return None

        self.latest_track_name = str(data.get("track_name") or "").strip() or self.latest_track_name
        self.latest_track_config = str(data.get("track_config") or "").strip() or self.latest_track_config
        self.latest_car_model = str(data.get("car_model") or "").strip() or self.latest_car_model
        self.latest_game_code = str(data.get("game_code") or "").strip() or self.latest_game_code
        self.latest_ac_install_path = str(data.get("ac_install_path") or "").strip() or self.latest_ac_install_path
        track_length = _safe_float(data.get("track_length"))
        if track_length > 0:
            self.latest_track_length = track_length

        x = _safe_float(data.get("x"))
        z = _safe_float(data.get("z"))
        if abs(x) + abs(z) < 1e-6:
            return None

        return TelemetrySample.from_dict(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "x": x,
                "y": _safe_float(data.get("y")),
                "z": z,
                "speed": _safe_float(data.get("speed")) * 3.6,
                "heading": _safe_float(data.get("heading")),
                "normalized_spline_pos": _safe_float(data.get("lap_dist_pct")),
                "throttle": _safe_float(data.get("throttle")),
                "brake": _safe_float(data.get("brake")),
                "steering": _safe_float(data.get("steer")),
                "gear": int(_safe_float(data.get("gear", 0))),
                "rpm": int(_safe_float(data.get("rpm", 0))),
                "lap": int(_safe_float(data.get("lap_number", 0))),
                "sector": int(_safe_float(data.get("sector", 0))),
                "session_time": _safe_float(data.get("lap_time")),
                "lap_time": _safe_float(data.get("lap_time")),
                "accel_x": _safe_float(data.get("lat_g")),
                "accel_y": _safe_float(data.get("vertical_g")),
                "accel_z": _safe_float(data.get("accel_g")),
                "velocity": data.get("velocity"),
                "clutch": data.get("clutch"),
                "fuel": data.get("fuel"),
                "max_fuel": data.get("max_fuel"),
                "ballast": data.get("ballast"),
                "abs": data.get("abs"),
                "tc": data.get("tc"),
                "drs": data.get("drs"),
                "turbo_boost": data.get("turbo_boost"),
                "air_temp": data.get("air_temp"),
                "road_temp": data.get("road_temp"),
                "surface_grip": data.get("surface_grip"),
                "air_density": data.get("air_density"),
                "wheel_slip": data.get("wheel_slip"),
                "wheel_load": data.get("wheel_load"),
                "wheels_pressure": data.get("wheels_pressure"),
                "tyre_wear": data.get("tyre_wear"),
                "tyre_dirty_level": data.get("tyre_dirty_level"),
                "tyre_core_temperature": data.get("tyre_core_temperature"),
                "suspension_travel": data.get("suspension_travel"),
                "ride_height": data.get("ride_height"),
                "camber_rad": data.get("camber_rad"),
                "car_damage": data.get("car_damage"),
            }
        )

    def stop(self):
        self.adapter.close()
        self.connected = False


class ReplayCSVReader(PollingTelemetryReader):
    source_name = "replay"
    active_reader_name = "ReplayCSVReader"

    def __init__(self, replay_paths: Sequence[Path]):
        self.replay_paths = [Path(path) for path in replay_paths]
        self.reconstruction_samples: List[TelemetrySample] = []
        self.replay_samples: List[TelemetrySample] = []
        self.index = 0
        self.loaded_from: Optional[Path] = None
        self.load()

    def load(self):
        for path in self.replay_paths:
            if path.exists():
                df = pd.read_csv(path)
                self.reconstruction_samples = telemetry_samples_from_dataframe(df, source_name=str(path), lap_mode="all")
                self.replay_samples = telemetry_samples_from_dataframe(df, source_name=str(path), lap_mode="representative")
                self.loaded_from = path
                return
        raise FileNotFoundError(f"No replay telemetry CSV found in: {', '.join(str(path) for path in self.replay_paths)}")

    def read_sample(self) -> Optional[TelemetrySample]:
        if not self.replay_samples:
            return None
        source = self.replay_samples[self.index % len(self.replay_samples)]
        self.index += 1
        return TelemetrySample(
            **{
                **source.__dict__,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    def replace_samples(self, reconstruction_samples: List[TelemetrySample], replay_samples: List[TelemetrySample]):
        self.reconstruction_samples = list(reconstruction_samples)
        self.replay_samples = list(replay_samples or reconstruction_samples)
        self.index = 0
        self.loaded_from = None


class MockTelemetryReader(PollingTelemetryReader):
    source_name = "mock"
    active_reader_name = "MockTelemetryReader"


@dataclass
class TelemetrySourceConfig:
    requested_source: str = "auto"
    allow_replay_fallback: bool = False
    debug_replay_enabled: bool = False
    replay_paths: Tuple[Path, ...] = ()

    @classmethod
    def from_env(cls, replay_paths: Sequence[Path]) -> "TelemetrySourceConfig":
        return cls(
            requested_source=_canonical_source_name(os.getenv("TELEMETRY_SOURCE", "auto")),
            allow_replay_fallback=_env_bool("ALLOW_REPLAY_FALLBACK", False),
            debug_replay_enabled=_env_bool("TELEMETRY_DEBUG_REPLAY", False),
            replay_paths=tuple(Path(path) for path in replay_paths),
        )


class TelemetrySourceManager:
    def __init__(self, config: TelemetrySourceConfig):
        self.config = config
        self.reader: PollingTelemetryReader = MockTelemetryReader()
        self.active_source_name = "mock"
        self.ac_available = False
        self.sample_count = 0
        self.last_sample_time: Optional[str] = None
        self.last_world_position: Optional[List[float]] = None
        self.last_shared_memory_gate_status: Dict[str, Any] = {}
        self._next_ac_autoselect_at = 0.0

    @staticmethod
    def detect_ac_available() -> bool:
        gate_status = shared_memory_gate_status()
        if not gate_status.get("allowed", True):
            return False
        reader = ACSharedMemoryReader()
        try:
            return reader.connect()
        finally:
            reader.stop()

    @classmethod
    def from_env(cls, replay_paths: Sequence[Path]) -> "TelemetrySourceManager":
        return cls(TelemetrySourceConfig.from_env(replay_paths))

    def select_source(self, requested_source: Optional[str] = None) -> str:
        requested = _canonical_source_name(requested_source or self.config.requested_source)
        self.reader.stop()
        self.sample_count = 0
        self.last_sample_time = None
        self.last_world_position = None

        if requested == "assetto_corsa":
            return self._select_assetto_corsa(fail_loudly=True)
        if requested == "replay":
            return self._select_replay()
        if requested == "mock":
            return self._select_mock(ac_available=self.detect_ac_available())
        if requested != "auto":
            raise ValueError("TELEMETRY_SOURCE must be one of: auto, assetto_corsa, replay, mock")

        ac_reader = ACSharedMemoryReader()
        self.ac_available = ac_reader.connect()
        self.last_shared_memory_gate_status = dict(ac_reader.latest_shared_memory_gate_status)
        if self.ac_available:
            self.reader = ac_reader
            self.active_source_name = "assetto_corsa"
            logger.info("Telemetry source selected: assetto_corsa")
            return self.active_source_name

        ac_reader.stop()
        if self.config.allow_replay_fallback or self.config.debug_replay_enabled:
            return self._select_replay()

        return self._select_mock(ac_available=False)

    def _select_assetto_corsa(self, fail_loudly: bool) -> str:
        ac_reader = ACSharedMemoryReader()
        self.ac_available = ac_reader.connect()
        self.last_shared_memory_gate_status = dict(ac_reader.latest_shared_memory_gate_status)
        if not self.ac_available:
            ac_reader.stop()
            if fail_loudly:
                if self.last_shared_memory_gate_status.get("reason") == "waiting_for_assetto_corsa_process":
                    raise RuntimeError(
                        "TELEMETRY_SOURCE=assetto_corsa requested, but Assetto Corsa is not running. "
                        "Open Assetto Corsa first, then the backend will connect to shared memory."
                    )
                raise RuntimeError("TELEMETRY_SOURCE=assetto_corsa requested, but Assetto Corsa shared memory is unavailable")
            return self._select_mock(ac_available=False)

        self.reader = ac_reader
        self.active_source_name = "assetto_corsa"
        logger.info("Telemetry source selected: assetto_corsa")
        return self.active_source_name

    def _select_replay(self) -> str:
        self.ac_available = self.detect_ac_available()
        self.reader = ReplayCSVReader(self.config.replay_paths)
        self.active_source_name = "replay"
        logger.warning("Telemetry source selected: replay CSV fixture (%s)", getattr(self.reader, "loaded_from", None))
        return self.active_source_name

    def _select_mock(self, ac_available: bool) -> str:
        self.ac_available = ac_available
        self.last_shared_memory_gate_status = shared_memory_gate_status()
        self.reader = MockTelemetryReader()
        self.active_source_name = "mock"
        logger.warning("Telemetry source selected: mock; replay fallback is disabled")
        return self.active_source_name

    def _promote_assetto_corsa_when_ready(self):
        if self.active_source_name != "mock" or self.config.requested_source != "auto":
            return
        now = time.monotonic()
        if now < self._next_ac_autoselect_at:
            return
        self._next_ac_autoselect_at = now + 2.0

        gate_status = shared_memory_gate_status()
        self.last_shared_memory_gate_status = gate_status
        if not gate_status.get("allowed", True):
            self.ac_available = False
            return

        ac_reader = ACSharedMemoryReader()
        self.ac_available = ac_reader.connect()
        self.last_shared_memory_gate_status = dict(ac_reader.latest_shared_memory_gate_status)
        if not self.ac_available:
            ac_reader.stop()
            return

        self.reader.stop()
        self.reader = ac_reader
        self.active_source_name = "assetto_corsa"
        self.sample_count = 0
        self.last_sample_time = None
        self.last_world_position = None
        logger.info("Telemetry source auto-promoted to assetto_corsa after Assetto Corsa process became available")

    def read_sample(self) -> Optional[TelemetrySample]:
        self._promote_assetto_corsa_when_ready()
        sample = self.reader.read_sample()
        if not sample:
            return None

        self.sample_count += 1
        self.last_sample_time = str(sample.timestamp)
        self.last_world_position = sample.worldPosition
        return sample

    def stop(self):
        self.reader.stop()

    def get_active_source_name(self) -> str:
        return self.active_source_name

    def player_source_name(self) -> str:
        if self.active_source_name == "assetto_corsa":
            return "shared_memory"
        return self.active_source_name

    def active_reader_name(self) -> str:
        return self.reader.active_reader_name

    def current_track_name(self) -> Optional[str]:
        return getattr(self.reader, "latest_track_name", None)

    def current_track_config(self) -> Optional[str]:
        return getattr(self.reader, "latest_track_config", None)

    def current_car_model(self) -> Optional[str]:
        return getattr(self.reader, "latest_car_model", None)

    def current_track_length(self) -> Optional[float]:
        return getattr(self.reader, "latest_track_length", None)

    def current_game_code(self) -> Optional[str]:
        return getattr(self.reader, "latest_game_code", None)

    def current_ac_install_path(self) -> Optional[str]:
        return getattr(self.reader, "latest_ac_install_path", None)

    def get_reconstruction_samples(self) -> List[TelemetrySample]:
        return list(getattr(self.reader, "reconstruction_samples", []))

    def get_replay_samples(self) -> List[TelemetrySample]:
        return list(getattr(self.reader, "replay_samples", []))

    def replace_replay_samples(self, reconstruction_samples: List[TelemetrySample], replay_samples: List[TelemetrySample]):
        if not isinstance(self.reader, ReplayCSVReader):
            self.reader.stop()
            self.reader = ReplayCSVReader(self.config.replay_paths)
        self.reader.replace_samples(reconstruction_samples, replay_samples)
        self.active_source_name = "replay"
        self.ac_available = self.detect_ac_available()
        self.sample_count = 0
        self.last_sample_time = None
        self.last_world_position = None

    def status(self) -> Dict[str, Any]:
        gate_status = getattr(self.reader, "latest_shared_memory_gate_status", None) or self.last_shared_memory_gate_status
        if self.active_source_name != "assetto_corsa":
            gate_status = shared_memory_gate_status()
            self.last_shared_memory_gate_status = gate_status
        return {
            "source": self.active_source_name,
            "player_source": self.player_source_name(),
            "ac_available": self.ac_available,
            "ac_process_running": gate_status.get("processRunning"),
            "shared_memory_allowed": gate_status.get("allowed"),
            "shared_memory_gate": gate_status,
            "active_reader": self.active_reader_name(),
            "sample_count": self.sample_count,
            "last_sample_time": self.last_sample_time,
            "last_world_position": self.last_world_position,
            "track_name": self.current_track_name(),
            "track_config": self.current_track_config(),
            "car_model": self.current_car_model(),
            "track_length": self.current_track_length(),
            "game_code": self.current_game_code(),
            "ac_install_path": self.current_ac_install_path(),
        }


__all__ = [
    "ACSharedMemoryReader",
    "ReplayCSVReader",
    "MockTelemetryReader",
    "TelemetrySourceConfig",
    "TelemetrySourceManager",
    "telemetry_samples_from_dataframe",
]
