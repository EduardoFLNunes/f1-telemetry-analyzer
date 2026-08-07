"""
Telemetry-driven spatial backend for F1 Telemetry Analyzer.

The backend owns reconstruction, projection, boundaries, caching, and live car
state. CSV track maps are deliberately not used as a source of truth.

Endpoints are grouped by domain into `routers/` (health, live telemetry,
recording, assisted analysis, etc). This module is the composition root: it
owns the shared runtime state/singletons, the cross-domain payload builders
that more than one router depends on, and app/lifespan wiring. Router modules
reach back into this module's state via `import main; main.<name>` rather
than `from main import <name>`, so state reassigned here (or monkeypatched by
tests as `backend_main.<name> = ...`) stays a single source of truth.
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import asyncio
import logging
import math
import os
import re
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.assisted_analysis import AssistedAnalysisService
from core.assetto_shared_memory_gate import shared_memory_gate_status
from core.cache.track_cache import TrackCache
from core.data_quality import (
    DataQualityReporter,
    TelemetryReliabilityMonitor,
    UdpReliabilityMonitor,
    validate_track,
)
from core.external_references import ExternalReferenceRepository, FastF1ReferenceProvider
from core.geometry.track_geometry_provider import (
    CacheTrackGeometryProvider,
    DebugTrajectoryTrackGeometryProvider,
    Kn5SurfaceTrackGeometryProvider,
)
from core.live.lap_collector import TrackBuildState
from core.live.runtime_state import RuntimeState
from core.live.telemetry_runtime import TelemetryRuntime
from core.opponents import (
    OpponentsRuntime,
    OpponentsRuntimeConfig,
    OpponentsStateBuffer,
    SOURCE_NAME as OPPONENTS_SOURCE_NAME,
)
from core.performance_metrics import performance_metrics
from core.recording.recording_runtime import RecordingRuntime, config_from_env as recording_config_from_env
from core.recording.session_repository import SessionRepository
from core.reconstruction.track_reconstruction import TrackReconstructor
from core.telemetry.telemetry_buffer import TelemetryBuffer
from core.telemetry.telemetry_models import TelemetrySample
from core.telemetry.telemetry_reader_impl import TelemetrySourceManager, telemetry_samples_from_dataframe
from core.telemetry_events import COACHING_EVENT, event_bus
from core.websocket_server import broadcaster as ws_broadcaster
from core.websocket_server import manager as ws_manager


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent
RESOURCE_ROOT = Path(
    os.environ.get("AT_BACKEND_RESOURCE_ROOT")
    or os.environ.get("AT_BACKEND_REPO_ROOT", BACKEND_DIR.parent)
).resolve()
RUNTIME_ROOT = Path(
    os.environ.get("AT_BACKEND_RUNTIME_ROOT")
    or os.environ.get("AT_BACKEND_REPO_ROOT")
    or RESOURCE_ROOT
).resolve()
REPO_ROOT = RESOURCE_ROOT
REPLAY_TRACK_CACHE_NAME = "telemetry_reconstructed_multilap_v1"
LIVE_TRACK_CACHE_PREFIX = "assetto_corsa"
TRACK_CACHE_DIR = RUNTIME_ROOT / "data" / "cache" / "tracks"
PRIMARY_TELEMETRY_FIXTURE = RESOURCE_ROOT / "data" / "example_telemetry.csv"
DEBUG_TELEMETRY_FIXTURE = RESOURCE_ROOT / "data" / "example_telemetryOld.csv"
BACKEND_SERVICE_NAME = "automobilista-telemetria-backend"
BACKEND_PHASE_VERSION = "phase-15-1-runtime-sampling-diagnostics"

runtime_state = RuntimeState()
telemetry_buffer = TelemetryBuffer(max_size=20000)
player_reliability = TelemetryReliabilityMonitor(target_hz=60.0)
udp_reliability = UdpReliabilityMonitor()
data_quality_reporter = DataQualityReporter()
track_cache = TrackCache(cache_dir=str(TRACK_CACHE_DIR))
reconstructor = TrackReconstructor()
source_manager = TelemetrySourceManager.from_env((PRIMARY_TELEMETRY_FIXTURE, DEBUG_TELEMETRY_FIXTURE))
telemetry_runtime: Optional[TelemetryRuntime] = None
opponents_buffer = OpponentsStateBuffer()
opponents_config = OpponentsRuntimeConfig.from_env()
opponents_runtime: Optional[OpponentsRuntime] = None
recording_runtime: Optional[RecordingRuntime] = None
recent_coaching_events: List[Dict[str, Any]] = []
session_repository = SessionRepository(recording_config_from_env(RUNTIME_ROOT).output_root)
_validation_sessions_cache: List[Dict[str, Any]] = []
_validation_sessions_cache_at = 0.0
external_reference_repository = ExternalReferenceRepository(REPO_ROOT)
fastf1_reference_provider = FastF1ReferenceProvider(REPO_ROOT, external_reference_repository)
assisted_analysis_service = AssistedAnalysisService(
    REPO_ROOT,
    telemetry_buffer,
    runtime_state,
    track_cache,
    external_reference_repository=external_reference_repository,
    runtime_root=RUNTIME_ROOT,
)


async def remember_coaching_event(event: Dict[str, Any]):
    recent_coaching_events.insert(0, event)
    del recent_coaching_events[50:]


def _safe_cache_fragment(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "_", value.strip())
    return cleaned.strip("_") or "live"


def _finite_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _first_finite_float(*values: Any) -> Optional[float]:
    for value in values:
        number = _finite_float(value)
        if number is not None:
            return number
    return None


def _world_to_map_position(sample: Dict[str, Any]) -> Optional[Dict[str, float]]:
    world = sample.get("worldPosition") or sample.get("world_position")
    if isinstance(world, (list, tuple)) and len(world) >= 3:
        x = _finite_float(world[0])
        z = _finite_float(world[2])
    elif isinstance(world, dict):
        x = _first_finite_float(
            world.get("x"),
            sample.get("worldPositionX"),
            sample.get("world_x"),
            sample.get("worldX"),
        )
        z = _first_finite_float(
            world.get("z"),
            sample.get("worldPositionZ"),
            sample.get("world_z"),
            sample.get("worldZ"),
        )
    else:
        x = _first_finite_float(sample.get("worldPositionX"), sample.get("world_x"), sample.get("worldX"))
        z = _first_finite_float(sample.get("worldPositionZ"), sample.get("world_z"), sample.get("worldZ"))
    if x is None or z is None:
        return None
    return {"x": x, "y": -z}


def _replay_map_position(sample: Dict[str, Any]) -> Dict[str, float]:
    world_position = _world_to_map_position(sample)
    if world_position is not None:
        return world_position

    map_position = sample.get("mapPosition") if isinstance(sample.get("mapPosition"), dict) else {}
    x = _first_finite_float(map_position.get("x"), sample.get("x"))
    y = _first_finite_float(map_position.get("y"), sample.get("y"), sample.get("z"))
    return {"x": x or 0.0, "y": y or 0.0}


def _normalize_replay_sample(sample: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(sample)
    lap_time = _finite_float(sample.get("lap_time") or sample.get("lapTime") or sample.get("currentLapTime"))
    speed_kmh = _finite_float(sample.get("speedKmh"))
    speed_ms = _finite_float(sample.get("speed"))
    if speed_kmh is None and speed_ms is not None:
        speed_kmh = speed_ms * 3.6
    if speed_ms is None and speed_kmh is not None:
        speed_ms = speed_kmh / 3.6
    progress = _finite_float(
        sample.get("lapProgress")
        or sample.get("p")
        or sample.get("spline_t")
        or sample.get("normalizedSplinePosition")
        or sample.get("splinePosition")
    )
    if progress is not None:
        progress = max(0.0, min(1.0, progress))
    map_position = _replay_map_position(sample)
    accel_g = sample.get("accel_g") if isinstance(sample.get("accel_g"), dict) else {}
    acceleration = {
        "lateralG": _finite_float(sample.get("lateral_g") or accel_g.get("x")),
        "longitudinalG": _finite_float(sample.get("longitudinal_g") or accel_g.get("z")),
    }
    normalized.update({
        "source": "persisted_lap",
        "lapTime": lap_time,
        "lap_time": lap_time,
        "timestamp": sample.get("timestamp"),
        "sessionTime": sample.get("sessionTime") or sample.get("session_time"),
        "mapPosition": map_position,
        "worldX": _first_finite_float(sample.get("world_x"), sample.get("worldPositionX"), sample.get("worldX"), sample.get("x")),
        "worldY": _first_finite_float(sample.get("world_y"), sample.get("worldPositionY"), sample.get("worldY")),
        "worldZ": _first_finite_float(sample.get("world_z"), sample.get("worldPositionZ"), sample.get("worldZ"), sample.get("z")),
        "x": map_position["x"],
        "z": map_position["y"],
        "lapProgress": progress,
        "splinePosition": progress,
        "trackProgress": progress,
        "lapDistance": _finite_float(sample.get("s") or sample.get("distanceAlongTrack")),
        "speed": speed_ms,
        "speedKmh": speed_kmh,
        "throttle": _finite_float(sample.get("throttle")) or 0.0,
        "brake": _finite_float(sample.get("brake")) or 0.0,
        "steering": _finite_float(sample.get("steering")) or 0.0,
        "gear": sample.get("gear"),
        "rpm": sample.get("rpm"),
        "acceleration": acceleration,
        "accel_g": {
            "x": acceleration["lateralG"] or 0.0,
            "y": _finite_float(accel_g.get("y")) or 0.0,
            "z": acceleration["longitudinalG"] or 0.0,
        },
    })
    return normalized


def active_track_cache_name() -> str:
    source = source_manager.get_active_source_name()
    if source == "assetto_corsa":
        track_name = source_manager.current_track_name() or "live"
        return f"{LIVE_TRACK_CACHE_PREFIX}_{_safe_cache_fragment(track_name)}"
    if source == "replay":
        return REPLAY_TRACK_CACHE_NAME
    return "mock_live"


def clear_loaded_track():
    runtime_state.current_track_name = None
    runtime_state.track_data = None
    runtime_state.api_track_cache = None
    runtime_state.projection_engine = None
    runtime_state.last_distance_along_track = None
    runtime_state.track_build_state = TrackBuildState.NO_TRACK
    runtime_state.build_method = "none"
    runtime_state.lap_complete = False


def reconstruct_track_from_samples(
    samples: List[TelemetrySample],
    track_name: Optional[str] = None,
    closed_loop: Optional[bool] = None,
) -> Dict[str, Any]:
    track_name = track_name or active_track_cache_name()
    if closed_loop is None:
        closed_loop = True
    reconstructor.reset()
    reconstructor.add_telemetry_samples(samples)
    track = reconstructor.reconstruct(track_name=track_name, closed_loop=closed_loop)
    if "error" in track:
        raise ValueError(track["error"])
    track_cache.save_track(track_name, track)
    runtime_state.update_track(track_name, track)
    return track


def initialize_spatial_state():
    clear_loaded_track()
    cache_name = active_track_cache_name()

    if source_manager.get_active_source_name() == "assetto_corsa":
        track_name = source_manager.current_track_name()
        if track_name:
            try:
                kn5_provider = Kn5SurfaceTrackGeometryProvider(
                    track_cache,
                    ac_root=source_manager.current_ac_install_path(),
                )
                result = kn5_provider.load_or_build(
                    track_name,
                    source_manager.current_track_config(),
                    source=source_manager.get_active_source_name(),
                    game_code=source_manager.current_game_code() or "assetto_corsa",
                )
                if result:
                    runtime_state.update_track(result.track_name, result.track_data)
                    runtime_state.track_build_state = TrackBuildState.TRACK_READY
                    runtime_state.build_method = result.provider
                    logger.info(
                        "Loaded fixed ActiveTrackGeometry via %s from %s",
                        result.provider,
                        result.cache_path,
                    )
                    return
            except Exception as exc:
                logger.warning("KN5 surface geometry provider failed; falling back to cache: %s", exc)

    cached_result = CacheTrackGeometryProvider(track_cache).load(cache_name)
    cached = cached_result.track_data if cached_result else None
    if cached:
        length = float(cached.get("trackLength", cached.get("track_length", 0.0)))
        method = cached.get("reconstruction", {}).get("method")
        expected_length = source_manager.current_track_length() or 0.0
        incomplete_live_cache = (
            source_manager.get_active_source_name() == "assetto_corsa"
            and (
                not cached.get("closedLoop", True)
                or method in {"single_path", "live_open_path"}
                or (expected_length > 1000.0 and length < expected_length * 0.8)
                or (expected_length <= 1000.0 and length < 3000.0)
            )
        )
        if not incomplete_live_cache:
            cached.setdefault("reconstruction", {})["method"] = "cached_closed_loop"
            runtime_state.update_track(cache_name, cached)
            runtime_state.track_build_state = TrackBuildState.TRACK_READY
            runtime_state.build_method = "cached_closed_loop"
            logger.info("Loaded reconstructed track cache: %s", cache_name)
            return
        logger.warning("Ignoring incomplete live track cache %s (%.1fm, %s)", cache_name, length, method)

    if source_manager.get_active_source_name() == "replay":
        reconstruction = source_manager.get_reconstruction_samples()
        if reconstruction:
            track = reconstruct_track_from_samples(reconstruction, cache_name)
            telemetry_buffer.add_samples(reconstruction)
            runtime_state.track_build_state = TrackBuildState.TRACK_READY
            runtime_state.build_method = "reconstructed_closed_loop"
            logger.info("Generated debug replay track cache: %.1fm", track["trackLength"])
            return

    if source_manager.get_active_source_name() == "mock":
        fixed_interlagos = Kn5SurfaceTrackGeometryProvider(track_cache).load_or_build("vhe_interlagos", "gp")
        if fixed_interlagos:
            runtime_state.update_track(fixed_interlagos.track_name, fixed_interlagos.track_data)
            runtime_state.track_build_state = TrackBuildState.TRACK_READY
            runtime_state.build_method = fixed_interlagos.provider
            logger.info(
                "Loaded default Interlagos track-only geometry via %s from %s",
                fixed_interlagos.provider,
                fixed_interlagos.cache_path,
            )
            return

    if source_manager.get_active_source_name() == "assetto_corsa" and not DebugTrajectoryTrackGeometryProvider.enabled():
        runtime_state.track_build_state = TrackBuildState.COLLECTING_LAP
        runtime_state.build_method = "waiting_for_kn5_or_cache"
        logger.warning("No fixed KN5/cache TrackGeometry loaded; driver trajectory fallback is disabled")
        return

    runtime_state.track_build_state = TrackBuildState.COLLECTING_LAP
    runtime_state.build_method = "live_open_path"
    logger.warning("No %s track cache loaded; waiting for live telemetry samples to reconstruct the track", cache_name)


def reset_runtime_state():
    telemetry_buffer.clear()
    player_reliability.reset()
    runtime_state.last_sample = None
    runtime_state.car_projected_state = None
    runtime_state.last_distance_along_track = None


def ingest_one_active_sample() -> Optional[Dict[str, Any]]:
    sample = source_manager.read_sample()
    if not sample:
        return None
    player_reliability.observe(sample)
    telemetry_buffer.add_sample(sample)
    return runtime_state.update_car(sample)


def prime_active_source():
    if source_manager.get_active_source_name() != "assetto_corsa":
        return
    ingest_one_active_sample()


def build_telemetry_runtime() -> TelemetryRuntime:
    return TelemetryRuntime(
        source_manager=source_manager,
        state=runtime_state,
        buffer=telemetry_buffer,
        cache=track_cache,
        reconstructor=reconstructor,
        track_name=active_track_cache_name(),
        allow_debug_trajectory_track=DebugTrajectoryTrackGeometryProvider.enabled(),
        reliability_monitor=player_reliability,
    )


def build_opponents_runtime() -> OpponentsRuntime:
    return OpponentsRuntime(
        buffer=opponents_buffer,
        host=opponents_config.host,
        port=opponents_config.port,
        enabled=opponents_config.enabled,
        reliability_monitor=udp_reliability,
    )


def current_recording_track() -> Optional[str]:
    return source_manager.current_track_name() or runtime_state.current_track_name


def recording_metadata() -> Dict[str, Any]:
    return {
        "source": source_manager.get_active_source_name(),
        "trackCache": runtime_state.current_track_name,
        "trackState": runtime_state.track_build_state.value,
        "buildMethod": runtime_state.build_method,
    }


def capture_gate_status() -> Dict[str, Any]:
    """Whether telemetry capture/recording is allowed right now.

    Capture requires a real Assetto Corsa session: the shared-memory gate must be open
    (game process running, pages mapped, static data populated) and the active player
    source must actually be Assetto Corsa. Without this, the mock/replay fallbacks would
    happily produce recordings with no game running.
    """
    gate = shared_memory_gate_status()
    if not gate.get("allowed", False):
        return {
            "allowed": False,
            "reason": gate.get("reason") or "waiting_for_assetto_corsa_process",
            "sharedMemoryGate": gate,
        }
    active_source = source_manager.get_active_source_name()
    if active_source != "assetto_corsa":
        return {
            "allowed": False,
            "reason": "telemetry_source_is_not_assetto_corsa",
            "activeSource": active_source,
            "sharedMemoryGate": gate,
        }
    return {"allowed": True, "reason": None, "activeSource": active_source, "sharedMemoryGate": gate}


def build_recording_runtime() -> RecordingRuntime:
    return RecordingRuntime(
        config=recording_config_from_env(RUNTIME_ROOT),
        track_provider=current_recording_track,
        metadata_provider=recording_metadata,
        capture_gate=capture_gate_status,
    )


def live_trajectory_api() -> List[Dict[str, Any]]:
    if telemetry_runtime:
        return telemetry_runtime.live_trajectory_api()
    samples = telemetry_buffer.get_samples()[-800:]
    return [
        {
            "x": float(sample.worldPositionX),
            "y": float(-sample.worldPositionZ),
            "worldPosition": sample.worldPosition,
            "spline_t": float(sample.normalizedSplinePosition),
            "timestamp": sample.timestamp,
        }
        for sample in samples[::3]
    ]


def telemetry_status_payload() -> Dict[str, Any]:
    if telemetry_runtime:
        status = telemetry_runtime.status()
    else:
        status = {
            **source_manager.status(),
            "trackState": runtime_state.track_build_state.value,
            "method": runtime_state.build_method,
            "sampleCount": source_manager.sample_count,
            "lapComplete": runtime_state.lap_complete,
            "activeTrackReady": runtime_state.track_build_state == TrackBuildState.TRACK_READY,
            "candidateLapSampleCount": 0,
            "liveTrajectoryCount": len(telemetry_buffer.get_samples()),
        }
    track = runtime_state.track_data or {}
    widths = track.get("localWidth") or []
    width_min = track.get("widthMin")
    width_avg = track.get("widthAvg")
    width_max = track.get("widthMax")
    if widths and (width_min is None or width_avg is None or width_max is None):
        width_min = min(widths)
        width_avg = sum(widths) / len(widths)
        width_max = max(widths)
    return {
        "trackCache": runtime_state.current_track_name,
        "trackGeometryProvider": track.get("provider", track.get("reconstruction", {}).get("provider")),
        "geometryName": track.get("geometryName"),
        "visualGeometryName": track.get("visualGeometryName"),
        "renderMode": track.get("renderMode"),
        "updatedAt": track.get("updatedAt"),
        "providerSource": track.get("providerSource", track.get("source")),
        "centerlineCount": len(track.get("centerline", [])),
        "widthMin": width_min,
        "widthAvg": width_avg,
        "widthMax": width_max,
        "closedLoop": track.get("closedLoop"),
        "cachePath": track.get("cachePath") or (track.get("metadata") or {}).get("cachePath"),
        **status,
    }


def iso_from_epoch(timestamp: Optional[float]) -> Optional[str]:
    if timestamp is None:
        return None
    try:
        return datetime.fromtimestamp(float(timestamp), timezone.utc).isoformat()
    except (OSError, OverflowError, TypeError, ValueError):
        return None


def seconds_since(timestamp: Optional[float]) -> Optional[float]:
    if timestamp is None:
        return None
    try:
        return round(max(0.0, time.time() - float(timestamp)), 3)
    except (TypeError, ValueError):
        return None


def stream_status_from_age(
    timestamp: Optional[float],
    stale_after_seconds: float = 5.0,
    *,
    unknown_when_missing: bool = False,
) -> str:
    age = seconds_since(timestamp)
    if age is None:
        return "unknown" if unknown_when_missing else "waiting"
    return "receiving" if age <= stale_after_seconds else "stale"


def runtime_status_payload() -> Dict[str, Any]:
    telemetry_status = telemetry_runtime.status() if telemetry_runtime else {
        **source_manager.status(),
        "trackState": runtime_state.track_build_state.value,
        "method": runtime_state.build_method,
        "sampleCount": source_manager.sample_count,
        "playerStatus": "unknown",
        "lastPlayerSampleAt": None,
        "secondsSinceLastPlayerSample": None,
        "lapComplete": runtime_state.lap_complete,
        "activeTrackReady": runtime_state.track_build_state == TrackBuildState.TRACK_READY,
        "candidateLapSampleCount": 0,
        "liveTrajectoryCount": len(telemetry_buffer.get_samples()),
    }
    opponents_meta = opponents_buffer.metadata()
    opponents_transport = opponents_runtime.status() if opponents_runtime else {
        "source": OPPONENTS_SOURCE_NAME,
        "enabled": opponents_config.enabled,
        "running": False,
        "host": opponents_config.host,
        "port": opponents_config.port,
        "acceptedSnapshots": 0,
        "invalidPackets": 0,
        "discardedOutOfOrder": 0,
    }
    last_opponent_timestamp = opponents_meta.get("lastUpdateTimestamp")
    opponents_status = stream_status_from_age(
        last_opponent_timestamp,
        float(opponents_meta.get("staleAfterSeconds") or 5.0),
    )
    racing_line_status = "READY" if runtime_state.track_build_state == TrackBuildState.TRACK_READY else "INSUFFICIENT_DATA"
    coach_status = "READY" if recent_coaching_events else "INSUFFICIENT_DATA"
    telemetry_player_status = telemetry_status.get("playerStatus")
    if not telemetry_player_status:
        telemetry_player_status = "receiving" if telemetry_status.get("sampleCount", 0) else "waiting"

    return {
        "status": "ok",
        "service": BACKEND_SERVICE_NAME,
        "version": BACKEND_PHASE_VERSION,
        "backend": {
            "online": True,
            "trackState": runtime_state.track_build_state.value,
            "buildMethod": runtime_state.build_method,
            "trackCache": runtime_state.current_track_name,
            "resourceRoot": str(RESOURCE_ROOT),
            "runtimeRoot": str(RUNTIME_ROOT),
        },
        "telemetry": {
            "online": telemetry_runtime is not None,
            "source": telemetry_status.get("source"),
            "playerSource": telemetry_status.get(
                "player_source",
                source_manager.player_source_name(),
            ),
            "assettoProcessRunning": telemetry_status.get("ac_process_running"),
            "sharedMemoryAllowed": telemetry_status.get("shared_memory_allowed"),
            "sharedMemoryGate": telemetry_status.get("shared_memory_gate"),
            "activeReader": telemetry_status.get("active_reader"),
            "sampleCount": telemetry_status.get("sampleCount", telemetry_status.get("sample_count")),
            "liveTrajectoryCount": telemetry_status.get("liveTrajectoryCount"),
            "activeTrackReady": telemetry_status.get("activeTrackReady"),
            "playerStatus": telemetry_player_status,
            "lastPlayerSampleAt": telemetry_status.get("lastPlayerSampleAt"),
            "secondsSinceLastPlayerSample": telemetry_status.get("secondsSinceLastPlayerSample"),
            "targetHz": telemetry_status.get("targetHz"),
            "estimatedHz": telemetry_status.get("estimatedHz"),
            "stableHz": telemetry_status.get("stableHz"),
            "frequencyStatus": telemetry_status.get("frequencyStatus"),
            "adaptivePollMode": telemetry_status.get("adaptivePollMode"),
            "adaptivePollHz": telemetry_status.get("adaptivePollHz"),
            "droppedSamplesEstimate": telemetry_status.get("droppedSamplesEstimate"),
            "sampleValidation": telemetry_status.get("sampleValidation"),
        },
        "opponents": {
            "source": OPPONENTS_SOURCE_NAME,
            "enabled": opponents_transport.get("enabled", opponents_config.enabled),
            "online": opponents_transport.get("running", False),
            "count": len(opponents_buffer.latest()),
            "track": opponents_meta.get("track"),
            "lastUpdateTimestamp": opponents_meta.get("lastUpdateTimestamp"),
            "staleAfterSeconds": opponents_meta.get("staleAfterSeconds"),
            "status": opponents_status,
            "lastOpponentSampleAt": iso_from_epoch(last_opponent_timestamp),
            "secondsSinceLastOpponentSample": seconds_since(last_opponent_timestamp),
            "udpHost": opponents_transport.get("host", opponents_config.host),
            "udpPort": opponents_transport.get("port", opponents_config.port),
            "acceptedSnapshots": opponents_transport.get("acceptedSnapshots", 0),
            "invalidPackets": opponents_transport.get("invalidPackets", 0),
            "discardedOutOfOrder": opponents_meta.get(
                "discardedOutOfOrderCount",
                opponents_transport.get("discardedOutOfOrder", 0),
            ),
            "packetsReceived": opponents_transport.get("packetsReceived", 0),
            "packetsAccepted": opponents_transport.get("packetsAccepted", 0),
            "packetsDropped": opponents_transport.get("packetsDropped", 0),
            "playerFilteredCount": opponents_transport.get("playerFilteredCount", 0),
            "estimatedHz": opponents_transport.get("estimatedHz"),
        },
        "capture": capture_gate_status(),
        "racingLine": {
            "available": runtime_state.track_build_state == TrackBuildState.TRACK_READY,
            "status": racing_line_status,
        },
        "coach": {
            "online": True,
            "status": coach_status,
        },
        "websocket": {
            "path": "/ws",
            "connections": len(ws_manager.active_connections),
        },
    }


def runtime_performance_payload() -> Dict[str, Any]:
    runtime = runtime_status_payload()
    telemetry = runtime.get("telemetry", {})
    recording_status = recording_runtime.status().to_api() if recording_runtime else {}
    last_age_seconds = telemetry.get("secondsSinceLastPlayerSample")
    last_age_ms = (
        round(float(last_age_seconds) * 1000.0, 3)
        if isinstance(last_age_seconds, (int, float))
        else None
    )
    sampling = performance_metrics.runtime_snapshot(
        target_hz=float(telemetry.get("targetHz") or 60.0),
        source=telemetry.get("source"),
        player_source=telemetry.get("playerSource"),
        player_status=telemetry.get("playerStatus"),
        last_sample_age_ms=last_age_ms,
        recording_queue_depth=recording_status.get("queueSize"),
        recording_dropped_frames=recording_status.get("droppedFrames"),
        recorder_dropped_samples=recording_status.get("playerSamplesDropped"),
        recorder_downsampling_enabled=recording_status.get("playerDownsamplingEnabled"),
        recorder_configured_hz=(
            recording_runtime.config.player_record_hz if recording_runtime else None
        ),
        last_persisted_lap_sample_count=recording_status.get("lastPersistedLapSampleCount"),
        last_persisted_lap_duration_seconds=recording_status.get("lastPersistedLapDurationSeconds"),
        last_persisted_lap_effective_hz=recording_status.get("lastPersistedLapEffectiveHz"),
        websocket_queue_depth=ws_broadcaster.pending_depth(),
    )
    sampling["adaptivePollMode"] = telemetry.get("adaptivePollMode")
    sampling["adaptivePollHz"] = telemetry.get("adaptivePollHz")
    event_bus_status = event_bus.snapshot()
    websocket_pending_tasks = ws_manager.pending_tasks()
    sampling["sharedMemoryReadHz"] = sampling.get("rawReadHz")
    sampling["collectorSampleHz"] = sampling.get("lapCollectorSampleHz")
    sampling["eventBusPendingTasks"] = event_bus_status.get("pendingTasks", 0)
    sampling["eventBusPendingByTopic"] = event_bus_status.get("pendingByTopic", {})
    sampling["websocketPendingTasks"] = websocket_pending_tasks
    sampling["websocketBackpressureRecent"] = bool(sampling.get("websocketRecentSendFailures"))
    sampling["resources"] = process_resource_snapshot()
    return {
        "status": "success",
        "source": telemetry.get("source"),
        "playerSource": telemetry.get("playerSource"),
        "targetHz": sampling.get("targetHz"),
        "windows": sampling.get("windows"),
        "durationsMs": sampling.get("durationsMs"),
        "counters": sampling.get("counters"),
        "queues": sampling.get("queues"),
        "bottleneck": sampling.get("bottleneckDetails"),
        "bottleneckReason": sampling.get("bottleneckReason"),
        "sourceLimited": sampling.get("sourceLimited"),
        "backpressureDetected": sampling.get("backpressureDetected"),
        "sampling": sampling,
        "telemetry": {
            "source": telemetry.get("source"),
            "playerSource": telemetry.get("playerSource"),
            "playerStatus": telemetry.get("playerStatus"),
            "sampleCount": telemetry.get("sampleCount"),
            "targetHz": telemetry.get("targetHz"),
            "estimatedHz": telemetry.get("estimatedHz"),
            "stableHz": telemetry.get("stableHz"),
            "frequencyStatus": telemetry.get("frequencyStatus"),
            "adaptivePollMode": telemetry.get("adaptivePollMode"),
            "adaptivePollHz": telemetry.get("adaptivePollHz"),
            "sharedMemoryAllowed": telemetry.get("sharedMemoryAllowed"),
            "assettoProcessRunning": telemetry.get("assettoProcessRunning"),
            "sharedMemoryGate": telemetry.get("sharedMemoryGate"),
        },
        "recording": {
            "recording": recording_status.get("recording", False),
            "queueSize": recording_status.get("queueSize", 0),
            "droppedFrames": recording_status.get("droppedFrames", 0),
            "playerSamplesWritten": recording_status.get("playerSamplesWritten", 0),
            "playerSamplesReceived": recording_status.get("playerSamplesReceived", 0),
            "playerSamplesEnqueued": recording_status.get("playerSamplesEnqueued", 0),
            "playerSamplesDownsampled": recording_status.get("playerSamplesDownsampled", 0),
            "playerSamplesDropped": recording_status.get("playerSamplesDropped", 0),
            "playerDownsamplingEnabled": recording_status.get("playerDownsamplingEnabled", False),
            "recorderDownsampleRatio": recording_status.get("recorderDownsampleRatio", 1.0),
            "lastPersistedLapSampleCount": recording_status.get("lastPersistedLapSampleCount"),
            "lastPersistedLapDurationSeconds": recording_status.get("lastPersistedLapDurationSeconds"),
            "lastPersistedLapEffectiveHz": recording_status.get("lastPersistedLapEffectiveHz"),
        },
        "websocket": {
            "connections": len(ws_manager.active_connections),
            "pendingDepth": ws_broadcaster.pending_depth(),
            "pendingTasks": websocket_pending_tasks,
            "backpressureRecent": sampling.get("websocketBackpressureRecent", False),
        },
        "eventBus": event_bus_status,
        "runtime": {
            "backend": runtime.get("backend", {}),
            "racingLine": runtime.get("racingLine", {}),
        },
    }


def process_resource_snapshot() -> Dict[str, Optional[float]]:
    try:
        import psutil

        process = psutil.Process(os.getpid())
        return {
            "cpuPercent": round(float(process.cpu_percent(interval=None)), 2),
            "memoryRssMb": round(float(process.memory_info().rss) / (1024.0 * 1024.0), 2),
        }
    except Exception:
        return {"cpuPercent": None, "memoryRssMb": None}


async def validation_sessions_payload(force: bool = False) -> List[Dict[str, Any]]:
    global _validation_sessions_cache, _validation_sessions_cache_at
    now = time.monotonic()
    if not force and now - _validation_sessions_cache_at < 5.0:
        return list(_validation_sessions_cache)
    sessions = await asyncio.to_thread(session_repository.list_sessions, 200)
    _validation_sessions_cache = sessions
    _validation_sessions_cache_at = now
    return list(sessions)


async def data_quality_payload(force_sessions: bool = False) -> Dict[str, Any]:
    player = player_reliability.snapshot()
    latest_validation = player.get("latestSampleValidation")
    opponents = udp_reliability.snapshot(opponents_count=len(opponents_buffer.latest()))
    sessions = await validation_sessions_payload(force=force_sessions)
    track = validate_track(
        runtime_state.track_build_state.value,
        runtime_state.track_data,
        runtime_state.current_track_name or source_manager.current_track_name(),
        runtime_state.build_method,
    )
    comparison = {
        "status": (
            "READY"
            if telemetry_runtime
            and bool(telemetry_runtime.lap_collector.completed_lap_samples)
            else "INSUFFICIENT_DATA"
        ),
        "selectedReferenceLapId": None,
        "selectedComparisonLapId": None,
        "issues": [],
    }
    current_lap_valid = None
    if latest_validation:
        current_lap_valid = latest_validation.get("status") != "INVALID"
    return data_quality_reporter.build(
        player=player,
        opponents=opponents,
        sessions=sessions,
        track=track,
        comparison=comparison,
        current_lap_valid=current_lap_valid,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global telemetry_runtime, opponents_runtime, recording_runtime

    source_manager.select_source()
    prime_active_source()
    initialize_spatial_state()
    recording_runtime = build_recording_runtime()
    recording_runtime.start()
    event_bus.subscribe(COACHING_EVENT, remember_coaching_event)
    telemetry_runtime = build_telemetry_runtime()
    loop = asyncio.get_running_loop()
    telemetry_runtime.start(loop)
    opponents_runtime = build_opponents_runtime()
    opponents_runtime.start(loop)
    yield

    if opponents_runtime:
        opponents_runtime.stop()
        opponents_runtime = None
    if telemetry_runtime:
        telemetry_runtime.stop()
        telemetry_runtime = None
    if recording_runtime:
        recording_runtime.stop()
        recording_runtime = None
    event_bus.unsubscribe(COACHING_EVENT, remember_coaching_event)


app = FastAPI(
    title="F1 Telemetry Analyzer API",
    version="3.0.0-telemetry-reconstruction",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Domain routers. Each router module does `import main` and reaches shared
# state via `main.<name>` (never `from main import <name>`), so this import
# must happen after all the state/helpers/app above are already defined.
from routers import (  # noqa: E402
    assisted_analysis,
    debug,
    external_references,
    health,
    legacy,
    live,
    recording as recording_router,
    track,
    validation,
    websocket,
)

app.include_router(health.router)
app.include_router(validation.router)
app.include_router(websocket.router)
app.include_router(track.router)
app.include_router(live.router)
app.include_router(recording_router.router)
app.include_router(assisted_analysis.router)
app.include_router(external_references.router)
app.include_router(debug.router)
app.include_router(legacy.router)

# Re-exported so existing tests that call `backend_main.<name>(...)` directly
# (bypassing HTTP) keep working after the endpoint bodies moved into routers.
from routers.live import get_live_telemetry, get_live_opponents, set_live_source  # noqa: E402,F401
from routers.recording import (  # noqa: E402,F401
    list_recorded_sessions,
    get_recorded_session_laps,
    get_offline_recorded_lap_summary,
    get_offline_recorded_lap_samples,
    get_offline_recorded_lap_replay,
)
from routers.assisted_analysis import (  # noqa: E402,F401
    request_phase14_assisted_analysis,
    get_phase14_assisted_analysis,
    get_phase14_assisted_lap_telemetry,
)
from routers.external_references import import_external_fastf1_reference  # noqa: E402,F401
from routers.health import get_runtime_performance  # noqa: E402,F401


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
