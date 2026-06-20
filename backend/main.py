"""
Telemetry-driven spatial backend for F1 Telemetry Analyzer.

The backend owns reconstruction, projection, boundaries, caching, and live car
state. CSV track maps are deliberately not used as a source of truth.
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import asyncio
import io
import logging
import math
import os
import re
import time

import pandas as pd
from fastapi import Body, FastAPI, File, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from core.assisted_analysis import AssistedAnalysisService
from core.assetto_shared_memory_gate import shared_memory_gate_status
from core.car_physics import build_car_physics_debug, build_opponent_car_physics, build_player_car_physics
from core.comparison_analysis import build_live_comparison_payload
from core.debug.ac_shared_memory_full_inventory import build_ac_shared_memory_full_inventory
from core.cache.track_cache import TrackCache
from core.data_quality import (
    DataQualityReporter,
    TelemetryReliabilityMonitor,
    UdpReliabilityMonitor,
    validate_track,
)
from core.debug.spatial_debug import projection_debug_payload
from core.external_references import ExternalReferenceError, ExternalReferenceRepository, FastF1ReferenceProvider
from core.geometry.track_geometry_provider import (
    CacheTrackGeometryProvider,
    DebugTrajectoryTrackGeometryProvider,
    Kn5SurfaceTrackGeometryProvider,
)
from core.live.lap_collector import TrackBuildState
from core.live.runtime_state import RuntimeState
from core.live.telemetry_runtime import TelemetryRuntime
from core.kn5.kn5_inventory import build_kn5_inventory_from_manifest
from core.kn5.kn5_surface_extraction import build_kn5_surface_extraction_from_manifest
from core.kn5.track_edges_from_surface import build_track_edges_from_surface_from_manifest
from core.kn5.track_surface_polygon import build_track_surface_polygon_from_manifest
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
from core.racing_line_analysis import build_live_racing_line_payload
from core.telemetry.telemetry_buffer import TelemetryBuffer
from core.telemetry.telemetry_models import TelemetrySample
from core.telemetry.telemetry_reader_impl import TelemetrySourceManager, telemetry_samples_from_dataframe
from core.track_file_resolver import TrackFileResolver
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
BACKEND_PHASE_VERSION = "phase-15-runtime-sampling-performance"

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


def _recording_lap_id(session_id: str, lap_number: int) -> str:
    return f"rec__{_safe_cache_fragment(session_id)}__{int(lap_number)}"


def _parse_recording_lap_id(lap_id: str) -> tuple[str, int]:
    if not isinstance(lap_id, str) or not lap_id.startswith("rec__"):
        raise ValueError("Offline lap id must use the rec__<session>__<lap> format")
    body = lap_id[len("rec__"):]
    if "__" not in body:
        raise ValueError("Offline lap id must include a session id and lap number")
    session_id, lap_number_text = body.rsplit("__", 1)
    if not session_id:
        raise ValueError("Offline lap id is missing the session id")
    try:
        lap_number = int(lap_number_text)
    except (TypeError, ValueError) as exc:
        raise ValueError("Offline lap id has an invalid lap number") from exc
    return session_id, lap_number


def _has_assisted_analysis(lap_id: str) -> bool:
    try:
        return assisted_analysis_service.has_cached_analysis(lap_id)
    except Exception:
        return False


def _enrich_recorded_lap(lap: Dict[str, Any], session: Dict[str, Any]) -> Dict[str, Any]:
    lap_number = int(lap.get("lapNumber") or 0)
    lap_id = str(lap.get("lapId") or _recording_lap_id(session["sessionId"], lap_number))
    accepted = bool(lap.get("acceptedByPhase13", lap.get("valid", False)))
    best_lap_time = session.get("bestLapTime")
    lap_time = lap.get("lapTime", lap.get("duration"))
    try:
        best_candidate = accepted and lap_time is not None and best_lap_time is not None and abs(float(lap_time) - float(best_lap_time)) <= 0.001
    except (TypeError, ValueError):
        best_candidate = False
    has_analysis = _has_assisted_analysis(lap_id) if accepted else False
    return {
        **lap,
        "lapId": lap_id,
        "sessionId": session.get("sessionId"),
        "track": session.get("track"),
        "car": session.get("car"),
        "startedAt": session.get("startedAt"),
        "completedAt": session.get("endedAt") if lap.get("completed") else None,
        "lapTime": lap_time,
        "reliabilityStatus": lap.get("reliabilityStatus") or lap.get("validationStatus"),
        "acceptedByPhase13": accepted,
        "hasAssistedAnalysis": has_analysis,
        "analysisStatus": "AVAILABLE" if has_analysis else ("NOT_GENERATED" if accepted else "NOT_ELIGIBLE"),
        "canAnalyze": accepted,
        "bestLapCandidate": best_candidate,
        "referenceCandidate": accepted and int(lap.get("sampleCount") or 0) >= 40,
    }


def _enrich_recorded_session(session: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(session)
    enriched["offlineAvailable"] = True
    enriched["storageMode"] = "recordings"
    enriched["liveDependency"] = False
    enriched["recordingRoot"] = str(session_repository.root)
    enriched["laps"] = [
        _enrich_recorded_lap(lap, enriched)
        for lap in (session.get("laps") or [])
        if isinstance(lap, dict)
    ]
    return enriched


def _offline_lap_summary_from_id(lap_id: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
    session_id, lap_number = _parse_recording_lap_id(lap_id)
    session = session_repository.session_summary(session_id, allow_large_scan=True)
    if not session:
        raise FileNotFoundError("Recorded session not found")
    enriched_session = _enrich_recorded_session(session)
    lap = next(
        (item for item in enriched_session.get("laps", []) if int(item.get("lapNumber") or -1) == lap_number),
        None,
    )
    if not lap:
        raise FileNotFoundError("Recorded lap not found")
    return enriched_session, lap


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


def build_recording_runtime() -> RecordingRuntime:
    return RecordingRuntime(
        config=recording_config_from_env(RUNTIME_ROOT),
        track_provider=current_recording_track,
        metadata_provider=recording_metadata,
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


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "message": "Backend is running",
        "spatial_source": "telemetry_reconstruction",
        "track_loaded": runtime_state.track_data is not None,
        "track_cache": runtime_state.current_track_name,
        "telemetry": telemetry_status_payload(),
    }


@app.get("/api/health")
async def api_health_check():
    return {
        "status": "ok",
        "service": BACKEND_SERVICE_NAME,
        "version": BACKEND_PHASE_VERSION,
    }


@app.get("/api/runtime/status")
async def get_runtime_status():
    return runtime_status_payload()


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


@app.get("/api/validation/data-quality")
async def get_data_quality():
    return await data_quality_payload()


@app.get("/api/validation/laps")
async def get_lap_validation():
    return {
        "status": "success",
        "laps": (await data_quality_payload())["laps"],
    }


@app.get("/api/validation/udp")
async def get_udp_validation():
    return {
        "status": "success",
        "opponents": (await data_quality_payload())["opponents"],
    }


@app.get("/api/validation/track")
async def get_track_validation():
    return {
        "status": "success",
        "track": (await data_quality_payload())["track"],
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error("WS Error: %s", e)
        ws_manager.disconnect(websocket)


@app.get("/api/track/current")
async def get_current_track():
    track = runtime_state.api_track()
    status = telemetry_status_payload()
    return {
        "status": "success",
        "source": source_manager.get_active_source_name(),
        "playerSource": source_manager.player_source_name(),
        **status,
        "track": track if status["activeTrackReady"] else None,
        "centerline": track["centerline"] if track and status["activeTrackReady"] else None,
        "liveTrajectory": live_trajectory_api(),
    }


@app.get("/api/track/geometry")
async def get_track_geometry():
    track = runtime_state.api_track()
    status = telemetry_status_payload()
    return {
        "status": "success",
        "source": source_manager.get_active_source_name(),
        **status,
        "track": track if status["activeTrackReady"] else None,
    }


@app.get("/api/track/cache")
async def get_track_cache():
    return {"status": "success", "tracks": track_cache.list_cached_tracks()}


@app.post("/api/track/cache")
async def rebuild_track_cache():
    samples = telemetry_buffer.get_samples()
    if not samples and source_manager.get_active_source_name() == "replay":
        samples = source_manager.get_reconstruction_samples()
    if not samples:
        raise HTTPException(status_code=400, detail="No telemetry samples available for reconstruction")
    if source_manager.get_active_source_name() == "assetto_corsa" and telemetry_runtime:
        if runtime_state.track_build_state == TrackBuildState.TRACK_READY:
            track = runtime_state.track_data
            return {
                "status": "success",
                "source": source_manager.get_active_source_name(),
                **telemetry_status_payload(),
                "trackCache": runtime_state.current_track_name,
                "track": runtime_state.api_track(),
                "trackLength": track["trackLength"] if track else 0,
            }
        if not DebugTrajectoryTrackGeometryProvider.enabled():
            raise HTTPException(
                status_code=400,
                detail="Driver trajectory TrackGeometry reconstruction is disabled. Set DEBUG_ALLOW_TRAJECTORY_TRACK=true for debug-only use.",
            )
        if not telemetry_runtime.lap_collector.completed_lap_samples:
            raise HTTPException(status_code=400, detail="A complete lap is required before building active TrackGeometry")
        ok = telemetry_runtime.trigger_reconstruction(active_track_cache_name(), save_to_cache=True)
        if not ok:
            raise HTTPException(status_code=400, detail="Candidate lap failed reconstruction")
        track = runtime_state.track_data
    else:
        track = reconstruct_track_from_samples(samples, active_track_cache_name(), closed_loop=True)
    return {
        "status": "success",
        "source": source_manager.get_active_source_name(),
        **telemetry_status_payload(),
        "trackCache": runtime_state.current_track_name,
        "track": runtime_state.api_track(),
        "trackLength": track["trackLength"] if track else 0,
    }


@app.post("/api/track/reconstruct")
async def reconstruct_current_track():
    return await rebuild_track_cache()


@app.get("/api/car/state")
async def get_car_state():
    if not runtime_state.car_projected_state:
        ingest_one_active_sample()
    if not runtime_state.car_projected_state:
        raise HTTPException(status_code=404, detail="No car state available yet")
    return {"status": "success", "car": runtime_state.car_projected_state}


@app.get("/api/live/telemetry")
async def get_live_telemetry(
    includeTrack: bool = Query(False),
    includeTrajectory: bool = Query(False),
):
    car = runtime_state.car_projected_state
    if not car:
        car = ingest_one_active_sample()
    status = telemetry_status_payload()
    track = runtime_state.api_track() if includeTrack else None
    return {
        "status": "success",
        "source": source_manager.get_active_source_name(),
        "playerSource": source_manager.player_source_name(),
        **status,
        "track": track if includeTrack and status["activeTrackReady"] else None,
        "centerline": track["centerline"] if includeTrack and track and status["activeTrackReady"] else None,
        "liveTrajectory": live_trajectory_api() if includeTrajectory else [],
        "car": car,
    }


@app.get("/api/live/opponents")
async def get_live_opponents():
    latest = opponents_buffer.latest()
    metadata = opponents_buffer.metadata()
    opponents = [latest[car_id].to_api() for car_id in sorted(latest)]
    return {
        "status": "success",
        "source": OPPONENTS_SOURCE_NAME,
        "enabled": opponents_config.enabled,
        "receiverStatus": stream_status_from_age(
            metadata["lastUpdateTimestamp"],
            float(metadata["staleAfterSeconds"]),
        ),
        "count": len(opponents),
        "track": metadata["track"],
        "sessionTime": metadata["sessionTime"],
        "lastUpdateTimestamp": metadata["lastUpdateTimestamp"],
        "staleAfterSeconds": metadata["staleAfterSeconds"],
        "discardedOutOfOrderCount": metadata["discardedOutOfOrderCount"],
        "opponents": opponents,
    }


def live_comparison_payload(micro_sectors: int = 50) -> Dict[str, Any]:
    micro_sector_count = max(1, min(200, int(micro_sectors or 50)))
    payload = build_live_comparison_payload(
        telemetry_samples=telemetry_buffer.get_samples(),
        opponent_history=opponents_buffer.history(),
        track_data=runtime_state.track_data,
        track_name=runtime_state.current_track_name or source_manager.current_track_name(),
        micro_sector_count=micro_sector_count,
    )
    logger.debug(
        "Live comparison generated: player=%s reference=%s opponents=%s validMicroSectors=%s",
        payload.get("debug", {}).get("playerSamples"),
        payload.get("debug", {}).get("referenceSamples"),
        payload.get("debug", {}).get("opponentsAnalyzed"),
        payload.get("debug", {}).get("validMicroSectors"),
    )
    return payload


def live_racing_line_payload(
    micro_sectors: int = 50,
    *,
    include_visual_line: bool = True,
    include_comparison: bool = True,
) -> Dict[str, Any]:
    micro_sector_count = max(1, min(200, int(micro_sectors or 50)))
    completed_live_lap = (
        list(telemetry_runtime.lap_collector.completed_lap_samples)
        if telemetry_runtime and telemetry_runtime.lap_collector.completed_lap_samples
        else []
    )
    payload = build_live_racing_line_payload(
        telemetry_samples=telemetry_buffer.get_samples(),
        track_data=runtime_state.track_data,
        track_name=runtime_state.current_track_name or source_manager.current_track_name(),
        micro_sector_count=micro_sector_count,
        include_visual_line=include_visual_line,
        include_comparison=include_comparison,
        fallback_reference_samples=completed_live_lap,
    )
    logger.debug(
        "Racing Line generated: status=%s reference=%s player=%s validSegments=%s",
        payload.get("status"),
        payload.get("debug", {}).get("referenceSamples"),
        payload.get("debug", {}).get("currentLapSamples"),
        (payload.get("racingLine") or {}).get("debug", {}).get("validSegments"),
    )
    return payload


def live_player_physics_payload() -> Dict[str, Any]:
    samples = telemetry_buffer.get_samples()
    player_samples = [sample for sample in samples if int(getattr(sample, "carId", 0) or 0) == 0]
    latest_sample = player_samples[-1] if player_samples else runtime_state.last_sample
    if latest_sample is None:
        ingest_one_active_sample()
        samples = telemetry_buffer.get_samples()
        player_samples = [sample for sample in samples if int(getattr(sample, "carId", 0) or 0) == 0]
        latest_sample = player_samples[-1] if player_samples else runtime_state.last_sample

    recent_player_samples = player_samples[-20:]
    player_physics = build_player_car_physics(latest_sample, recent_player_samples)

    opponent_history = opponents_buffer.history()
    latest_opponents = opponents_buffer.latest()
    opponent_physics = []
    opponent_sample_count = 0
    for car_id in sorted(latest_opponents):
        if car_id == 0:
            continue
        history = opponent_history.get(car_id, [])
        opponent_sample_count += len(history)
        opponent_physics.append(
            {
                "carId": car_id,
                "physics": build_opponent_car_physics(latest_opponents[car_id], history[-20:]),
            }
        )

    debug = build_car_physics_debug(
        player_physics,
        [item["physics"] for item in opponent_physics],
        player_sample_count=len(player_samples),
        opponent_sample_count=opponent_sample_count,
    )
    logger.debug(
        "Car physics generated: playerSamples=%s opponentSamples=%s completeness=%s",
        debug["playerPhysicsSamples"],
        debug["opponentPhysicsSamples"],
        debug["playerDataCompleteness"],
    )
    return {
        "status": "success",
        "source": source_manager.get_active_source_name(),
        "track": source_manager.current_track_name() or runtime_state.current_track_name,
        "generatedAt": datetime.utcnow().isoformat(),
        "player": player_physics,
        "opponents": opponent_physics,
        "carPhysicsDebug": debug,
    }


@app.get("/api/live/comparison")
async def get_live_comparison(microSectors: int = Query(50, ge=1, le=200)):
    return live_comparison_payload(microSectors)


@app.get("/api/analysis/comparison")
async def get_analysis_comparison(microSectors: int = Query(50, ge=1, le=200)):
    return live_comparison_payload(microSectors)


@app.get("/api/live/racing-line")
async def get_live_racing_line(
    microSectors: int = Query(50, ge=1, le=200),
    includeVisualLine: bool = Query(True),
    includeComparison: bool = Query(True),
):
    return live_racing_line_payload(
        microSectors,
        include_visual_line=includeVisualLine,
        include_comparison=includeComparison,
    )


@app.get("/api/analysis/racing-line")
async def get_analysis_racing_line(
    microSectors: int = Query(50, ge=1, le=200),
    includeVisualLine: bool = Query(False),
    includeComparison: bool = Query(True),
):
    return live_racing_line_payload(
        microSectors,
        include_visual_line=includeVisualLine,
        include_comparison=includeComparison,
    )


@app.get("/api/live/player-physics")
async def get_live_player_physics():
    return live_player_physics_payload()


@app.get("/api/live/coach")
async def get_live_coach():
    return {
        "status": "success",
        "source": "event_bus",
        "eventCount": len(recent_coaching_events),
        "events": recent_coaching_events[:20],
    }


@app.get("/api/recording/status")
async def get_recording_status():
    if not recording_runtime:
        return {
            "enabled": False,
            "recording": False,
            "sessionId": None,
            "directory": None,
            "playerSamplesWritten": 0,
            "opponentSnapshotsWritten": 0,
            "eventsWritten": 0,
            "queueSize": 0,
            "droppedFrames": 0,
        }
    return recording_runtime.status().to_api()


@app.post("/api/recording/start")
async def start_recording():
    if not recording_runtime:
        raise HTTPException(status_code=503, detail="Recording runtime is not available")
    return recording_runtime.start_recording().to_api()


@app.post("/api/recording/stop")
async def stop_recording():
    if not recording_runtime:
        raise HTTPException(status_code=503, detail="Recording runtime is not available")
    return recording_runtime.stop_recording().to_api()


@app.get("/api/sessions")
async def list_recorded_sessions(limit: int = Query(30, ge=1, le=200)):
    active_session_id = recording_runtime.status().sessionId if recording_runtime else None
    sessions = await asyncio.to_thread(session_repository.list_sessions, limit)
    sessions = [_enrich_recorded_session(session) for session in sessions]
    for session in sessions:
        session["active"] = session["sessionId"] == active_session_id
    return {
        "status": "success",
        "recordingRoot": str(session_repository.root),
        "activeSessionId": active_session_id,
        "offlineAvailable": True,
        "liveDependency": False,
        "sessions": sessions,
    }


@app.get("/api/sessions/{session_id}")
async def get_recorded_session(session_id: str):
    try:
        session = await asyncio.to_thread(session_repository.session_summary, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not session:
        raise HTTPException(status_code=404, detail="Recorded session not found")
    session = _enrich_recorded_session(session)
    return {"status": "success", "session": session}


@app.get("/api/sessions/{session_id}/laps")
async def get_recorded_session_laps(session_id: str):
    try:
        session = await asyncio.to_thread(session_repository.session_summary, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not session:
        raise HTTPException(status_code=404, detail="Recorded session not found")
    enriched = _enrich_recorded_session(session)
    return {
        "status": "success",
        "sessionId": enriched["sessionId"],
        "track": enriched.get("track"),
        "car": enriched.get("car"),
        "recordingRoot": str(session_repository.root),
        "offlineAvailable": True,
        "liveDependency": False,
        "laps": enriched.get("laps", []),
    }


@app.get("/api/sessions/{session_id}/laps/{lap_number}")
async def get_recorded_lap(
    session_id: str,
    lap_number: int,
    max_samples: int = Query(36_000, alias="maxSamples", ge=1_000, le=100_000),
):
    try:
        lap = await asyncio.to_thread(
            session_repository.lap_detail,
            session_id,
            lap_number,
            max_samples,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not lap:
        raise HTTPException(status_code=404, detail="Recorded lap not found")
    return {"status": "success", **lap}


@app.get("/api/laps/{lap_id}")
async def get_offline_recorded_lap(lap_id: str):
    try:
        session, lap = await asyncio.to_thread(_offline_lap_summary_from_id, lap_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "status": "success",
        "recordingRoot": str(session_repository.root),
        "offlineAvailable": True,
        "liveDependency": False,
        "session": {
            "sessionId": session.get("sessionId"),
            "track": session.get("track"),
            "car": session.get("car"),
            "startedAt": session.get("startedAt"),
            "endedAt": session.get("endedAt"),
            "bestLapTime": session.get("bestLapTime"),
        },
        "lap": lap,
    }


@app.get("/api/laps/{lap_id}/summary")
async def get_offline_recorded_lap_summary(lap_id: str):
    try:
        _, lap = await asyncio.to_thread(_offline_lap_summary_from_id, lap_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "status": "success",
        "recordingRoot": str(session_repository.root),
        "offlineAvailable": True,
        "liveDependency": False,
        "lap": lap,
    }


@app.get("/api/laps/{lap_id}/replay")
async def get_offline_recorded_lap_replay(
    lap_id: str,
    max_samples: int = Query(36_000, alias="maxSamples", ge=100, le=100_000),
):
    try:
        session_id, lap_number = _parse_recording_lap_id(lap_id)
        session = await asyncio.to_thread(session_repository.session_summary, session_id, True)
        lap = await asyncio.to_thread(
            session_repository.lap_detail,
            session_id,
            lap_number,
            max_samples,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not session or not lap:
        raise HTTPException(status_code=404, detail="Recorded lap not found")

    enriched_session = _enrich_recorded_session(session)
    summary = dict(lap.get("summary") or {})
    if summary:
        summary = _enrich_recorded_lap(summary, enriched_session)
    samples = [
        _normalize_replay_sample(sample)
        for sample in (lap.get("samples") or [])
        if isinstance(sample, dict)
    ]
    return {
        "status": "success",
        "mode": "offline_lap_replay",
        "source": "persisted_lap",
        "recordingRoot": str(session_repository.root),
        "offlineAvailable": True,
        "liveDependency": False,
        "sharedMemoryDependency": False,
        "lapId": lap_id,
        "session": {
            "sessionId": enriched_session.get("sessionId"),
            "track": enriched_session.get("track"),
            "car": enriched_session.get("car"),
            "startedAt": enriched_session.get("startedAt"),
            "endedAt": enriched_session.get("endedAt"),
        },
        "summary": summary or lap.get("summary"),
        "totalSampleCount": lap.get("totalSampleCount"),
        "returnedSampleCount": len(samples),
        "sampleStride": lap.get("sampleStride"),
        "truncated": lap.get("truncated"),
        "samples": samples,
    }


@app.get("/api/laps/{lap_id}/samples")
async def get_offline_recorded_lap_samples(
    lap_id: str,
    limit: int = Query(10_000, ge=100, le=100_000),
):
    try:
        session_id, lap_number = _parse_recording_lap_id(lap_id)
        lap = await asyncio.to_thread(
            session_repository.lap_detail,
            session_id,
            lap_number,
            limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not lap:
        raise HTTPException(status_code=404, detail="Recorded lap not found")
    summary = dict(lap.get("summary") or {})
    if summary:
        summary = _enrich_recorded_lap(summary, {"sessionId": session_id, "track": None, "car": None, "bestLapTime": None})
    return {
        "status": "success",
        "recordingRoot": str(session_repository.root),
        "offlineAvailable": True,
        "liveDependency": False,
        "lapId": lap_id,
        "sessionId": session_id,
        "lapNumber": lap_number,
        "summary": summary or lap.get("summary"),
        "totalSampleCount": lap.get("totalSampleCount"),
        "returnedSampleCount": lap.get("returnedSampleCount"),
        "sampleStride": lap.get("sampleStride"),
        "truncated": lap.get("truncated"),
        "samples": lap.get("samples", []),
    }


@app.get("/api/assisted-analysis/laps")
async def list_assisted_analysis_laps():
    return assisted_analysis_service.list_laps()


@app.get("/api/assisted-analysis/laps/{lap_id}/analysis")
async def get_assisted_analysis(lap_id: str, reference_lap_id: Optional[str] = None):
    return _get_assisted_analysis_or_404(lap_id, reference_lap_id)


@app.post("/api/assisted-analysis/laps/{lap_id}/analysis")
async def request_assisted_analysis(
    lap_id: str,
    reference_lap_id: Optional[str] = None,
    force: bool = False,
    payload: Optional[Dict[str, Any]] = Body(None),
):
    return _run_assisted_analysis(lap_id, reference_lap_id, force, payload)


@app.get("/api/analysis/assisted/lap/{lapId}")
async def get_phase14_assisted_analysis(
    lapId: str,
    reference_lap_id: Optional[str] = None,
    include_external_reference: bool = Query(False, alias="includeExternalReference"),
    external_reference_id: Optional[str] = Query(None, alias="externalReferenceId"),
):
    return _get_assisted_analysis_or_404(
        lapId,
        reference_lap_id,
        include_external_reference=include_external_reference,
        external_reference_id=external_reference_id,
    )


@app.post("/api/analysis/assisted/lap/{lapId}")
async def request_phase14_assisted_analysis(
    lapId: str,
    reference_lap_id: Optional[str] = None,
    include_external_reference: bool = Query(False, alias="includeExternalReference"),
    external_reference_id: Optional[str] = Query(None, alias="externalReferenceId"),
    force: bool = False,
    payload: Optional[Dict[str, Any]] = Body(None),
):
    return _run_assisted_analysis(
        lapId,
        reference_lap_id,
        force,
        payload,
        include_external_reference=include_external_reference,
        external_reference_id=external_reference_id,
    )


@app.get("/api/analysis/assisted/lap/{lapId}/telemetry")
async def get_phase14_assisted_lap_telemetry(
    lapId: str,
    max_samples: int = Query(36_000, alias="maxSamples", ge=100, le=100_000),
):
    try:
        return await asyncio.to_thread(
            assisted_analysis_service.lap_telemetry,
            lapId,
            max_samples,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _get_assisted_analysis_or_404(
    lap_id: str,
    reference_lap_id: Optional[str] = None,
    *,
    include_external_reference: bool = False,
    external_reference_id: Optional[str] = None,
):
    if not isinstance(include_external_reference, bool):
        include_external_reference = False
    if not isinstance(external_reference_id, str):
        external_reference_id = None
    cached = assisted_analysis_service.get_cached_analysis(
        lap_id,
        reference_lap_id=reference_lap_id,
        include_external_reference=include_external_reference,
        external_reference_id=external_reference_id,
    )
    if not cached:
        raise HTTPException(status_code=404, detail="Assisted analysis is not available for this lap yet")
    return cached


def _run_assisted_analysis(
    lap_id: str,
    reference_lap_id: Optional[str] = None,
    force: bool = False,
    payload: Optional[Dict[str, Any]] = None,
    include_external_reference: bool = False,
    external_reference_id: Optional[str] = None,
):
    try:
        body = payload or {}
        if not isinstance(include_external_reference, bool):
            include_external_reference = False
        if not isinstance(external_reference_id, str):
            external_reference_id = None
        reference = reference_lap_id or body.get("referenceLapId") or body.get("reference_lap_id")
        force_analysis = bool(force or body.get("force", False))
        external = bool(include_external_reference or body.get("includeExternalReference") or body.get("include_external_reference"))
        external_id = external_reference_id or body.get("externalReferenceId") or body.get("external_reference_id")
        return assisted_analysis_service.analyze_lap(
            lap_id,
            reference_lap_id=reference,
            include_external_reference=external,
            external_reference_id=external_id,
            force=force_analysis,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/references/external/fastf1/import")
async def import_external_fastf1_reference(payload: Optional[Dict[str, Any]] = Body(None)):
    body = payload or {}
    try:
        reference = await asyncio.to_thread(
            fastf1_reference_provider.import_reference,
            year=int(body.get("year", 2024)),
            event=str(body.get("event") or "Brazil"),
            session=str(body.get("session") or "Q"),
            driver=body.get("driver"),
            force=bool(body.get("force", False)),
        )
        return {"status": "success", "reference": reference.to_api(include_samples=False)}
    except ExternalReferenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/references/external")
async def list_external_references(include_samples: bool = False):
    return {
        "status": "success",
        "references": external_reference_repository.list_references(include_samples=include_samples),
    }


@app.get("/api/references/external/{reference_id}")
async def get_external_reference(reference_id: str, include_samples: bool = True):
    reference = external_reference_repository.get(reference_id)
    if not reference:
        raise HTTPException(status_code=404, detail="External reference not found")
    return {"status": "success", "reference": reference.to_api(include_samples=include_samples)}


@app.get("/api/debug/performance")
async def get_performance_metrics():
    recording_status = recording_runtime.status().to_api() if recording_runtime else {}
    metrics = performance_metrics.snapshot()
    return {
        "status": "success",
        **metrics,
        "recordingQueueSize": recording_status.get("queueSize", 0),
        "recordingDroppedFrames": recording_status.get("droppedFrames", 0),
        "eventBusQueueSize": event_bus.snapshot().get("pendingTasks", 0),
        "websocketConnections": len(ws_manager.active_connections),
        "websocketPendingTasks": ws_manager.pending_tasks(),
    }


@app.get("/api/runtime/performance")
async def get_runtime_performance():
    return runtime_performance_payload()


@app.get("/api/live/source")
async def get_live_source():
    return {"status": "success", **telemetry_status_payload()}


@app.post("/api/live/source/{source}")
async def set_live_source(source: str):
    global telemetry_runtime

    try:
        requested_source = (source or "").strip().lower().replace("-", "_")
        if requested_source in {"ac", "assetto", "assetto_corsa", "assetto_corsa_shared_memory"}:
            gate_status = shared_memory_gate_status()
            if not gate_status.get("allowed", True):
                reason = gate_status.get("reason")
                if reason == "stale_assetto_corsa_shared_memory_without_process":
                    raise RuntimeError(
                        "Stale Assetto Corsa shared memory pages exist without acs.exe. "
                        "Close the process that created them before opening Assetto Corsa."
                    )
                if reason == "waiting_for_assetto_corsa_shared_memory_pages":
                    raise RuntimeError(
                        "Assetto Corsa is running, but shared memory pages are not ready. "
                        "Load a driving session first, then the backend will connect."
                    )
                if reason == "waiting_for_assetto_corsa_static_data":
                    raise RuntimeError(
                        "Assetto Corsa is running, but static telemetry is not ready. "
                        "Wait until a car/track session is loaded."
                    )
                raise RuntimeError(
                    "Assetto Corsa is not running. Open Assetto Corsa first, then the backend will connect to shared memory."
                )

        if telemetry_runtime:
            telemetry_runtime.stop()
            telemetry_runtime = None
        selected = source_manager.select_source(source)
        reset_runtime_state()
        prime_active_source()
        initialize_spatial_state()
        telemetry_runtime = build_telemetry_runtime()
        telemetry_runtime.start(asyncio.get_running_loop())
        return {"status": "success", "source": selected, **telemetry_status_payload()}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/live/telemetry")
async def ingest_live_telemetry(payload: Any = Body(...)):
    raw_samples = payload if isinstance(payload, list) else payload.get("samples", payload)
    samples = [TelemetrySample.from_dict(item) for item in raw_samples] if isinstance(raw_samples, list) else [TelemetrySample.from_dict(raw_samples)]
    for sample in samples:
        player_reliability.observe(sample)
    telemetry_buffer.add_samples(samples)
    frame = runtime_state.update_car(samples[-1]) if samples else None
    if frame:
        await event_bus.emit("processed_frame", frame)
    return {"status": "success", "ingested": len(samples), "car": frame}


@app.get("/api/telemetry/live")
async def get_legacy_live_telemetry():
    car_response = await get_car_state()
    car = car_response["car"]
    return {
        "car_x": car["mapPosition"]["x"],
        "car_y": car["mapPosition"]["y"],
        "car_z": car["mapPosition"]["y"],
        "mapPosition": car["mapPosition"],
        "projectedPosition": car.get("projectedPosition"),
        "snapped_x": car.get("projected_x", car["mapPosition"]["x"]),
        "snapped_y": car.get("projected_y", car["mapPosition"]["y"]),
        "snapped_z": car.get("projected_y", car["mapPosition"]["y"]),
        "heading": car.get("heading", 0.0),
        "lateral_offset": car.get("L"),
        "distance_along_track": car.get("s"),
    }


@app.post("/api/upload/telemetry")
async def upload_telemetry(file: UploadFile = File(...)):
    contents = await file.read()
    try:
        filename = file.filename or "telemetry_upload"
        if filename.lower().endswith(".json"):
            df = pd.read_json(io.BytesIO(contents))
        else:
            df = pd.read_csv(io.BytesIO(contents))
        samples = telemetry_samples_from_dataframe(df, source_name=filename, lap_mode="all")
        replay = telemetry_samples_from_dataframe(df, source_name=filename, lap_mode="representative")
        if not samples:
            raise ValueError("No telemetry samples found")
        telemetry_buffer.clear()
        telemetry_buffer.add_samples(samples)
        source_manager.replace_replay_samples(samples, replay or samples)
        track = reconstruct_track_from_samples(samples, filename.rsplit(".", 1)[0] or active_track_cache_name(), closed_loop=True)
        return {"status": "success", "track": runtime_state.api_track(), "trackLength": track["trackLength"]}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/upload/track")
async def upload_track_deprecated(file: UploadFile = File(...)):
    raise HTTPException(
        status_code=410,
        detail="Static track CSV upload is deprecated. Upload telemetry samples so the backend can reconstruct the track.",
    )


@app.get("/api/data/track")
async def get_track_data():
    return await get_current_track()


@app.get("/api/data/comparison")
async def get_comparison():
    track = runtime_state.api_track()
    if not track:
        raise HTTPException(status_code=404, detail="No reconstructed track available yet")
    return {
        "track": track,
        "player": None,
        "ai": None,
        "f1_loaded": False,
        "spatial_source": "telemetry_reconstruction",
    }


@app.get("/api/data/telemetry")
async def get_telemetry_data():
    samples = telemetry_buffer.get_samples()
    return {"status": "success", "samples": len(samples)}


@app.get("/api/data/ai-raceline")
async def get_ai_raceline():
    return {"status": "not_ready", "message": "Raceline generation will consume reconstructed track-space in a later phase"}


@app.get("/api/data/track-limits")
async def get_track_limits():
    track = runtime_state.api_track()
    if not track:
        raise HTTPException(status_code=404, detail="No reconstructed track available yet")
    return {"status": "success", "left": track["boundsLeft"], "right": track["boundsRight"]}


@app.get("/api/debug/projection")
async def get_projection_debug():
    if not runtime_state.car_projected_state:
        raise HTTPException(status_code=404, detail="No projected car state available")
    return {"status": "success", "debug": projection_debug_payload(runtime_state.car_projected_state)}


@app.get("/api/debug/ac-shared-memory-full-inventory")
async def get_ac_shared_memory_full_inventory():
    return {"status": "success", "inventory": build_ac_shared_memory_full_inventory()}


@app.get("/api/debug/track-file-manifest")
async def get_track_file_manifest():
    if source_manager.get_active_source_name() == "assetto_corsa" and not source_manager.current_track_name():
        ingest_one_active_sample()

    track_name = source_manager.current_track_name()
    track_config = source_manager.current_track_config()
    ac_install_path = source_manager.current_ac_install_path()
    game_code = source_manager.current_game_code() or "assetto_corsa"
    source = source_manager.get_active_source_name()

    logger.info(
        "Track file manifest requested: source=%s game=%s track=%s config=%s acInstallPath=%s",
        source,
        game_code,
        track_name,
        track_config,
        ac_install_path,
    )
    resolver = TrackFileResolver(ac_root=ac_install_path)
    manifest = resolver.build_track_file_manifest(
        track_name or "",
        track_config,
        source=source,
        game_code=game_code,
    )
    return {
        "status": "success",
        "source": source,
        "gameCode": game_code,
        "trackName": track_name,
        "trackConfig": track_config,
        "acInstallPath": ac_install_path,
        "manifest": manifest.to_dict(),
    }


@app.get("/api/debug/kn5-inventory")
async def get_kn5_inventory():
    if source_manager.get_active_source_name() == "assetto_corsa" and not source_manager.current_track_name():
        ingest_one_active_sample()

    resolver = TrackFileResolver(ac_root=source_manager.current_ac_install_path())
    manifest = resolver.build_track_file_manifest(
        source_manager.current_track_name() or "",
        source_manager.current_track_config(),
        source=source_manager.get_active_source_name(),
        game_code=source_manager.current_game_code() or "assetto_corsa",
    )
    inventory = build_kn5_inventory_from_manifest(manifest.to_dict())
    return {"status": "success", **inventory.to_dict()}


@app.get("/api/debug/kn5-surface-candidates")
async def get_kn5_surface_candidates(include_pitlane: bool = False):
    if source_manager.get_active_source_name() == "assetto_corsa" and not source_manager.current_track_name():
        ingest_one_active_sample()

    resolver = TrackFileResolver(ac_root=source_manager.current_ac_install_path())
    manifest = resolver.build_track_file_manifest(
        source_manager.current_track_name() or "",
        source_manager.current_track_config(),
        source=source_manager.get_active_source_name(),
        game_code=source_manager.current_game_code() or "assetto_corsa",
    )
    extraction = build_kn5_surface_extraction_from_manifest(
        manifest.to_dict(),
        include_pitlane=include_pitlane,
    )
    return {"status": "success", **extraction.to_dict()}


@app.get("/api/debug/track-surface-polygon")
async def get_track_surface_polygon():
    if source_manager.get_active_source_name() == "assetto_corsa" and not source_manager.current_track_name():
        ingest_one_active_sample()

    resolver = TrackFileResolver(ac_root=source_manager.current_ac_install_path())
    manifest = resolver.build_track_file_manifest(
        source_manager.current_track_name() or "",
        source_manager.current_track_config(),
        source=source_manager.get_active_source_name(),
        game_code=source_manager.current_game_code() or "assetto_corsa",
    )
    surface = build_track_surface_polygon_from_manifest(manifest.to_dict())
    return {"status": "success", **surface}


@app.get("/api/debug/track-edges-from-surface")
async def get_track_edges_from_surface():
    if source_manager.get_active_source_name() == "assetto_corsa" and not source_manager.current_track_name():
        ingest_one_active_sample()

    resolver = TrackFileResolver(ac_root=source_manager.current_ac_install_path())
    manifest = resolver.build_track_file_manifest(
        source_manager.current_track_name() or "",
        source_manager.current_track_config(),
        source=source_manager.get_active_source_name(),
        game_code=source_manager.current_game_code() or "assetto_corsa",
    )
    result = build_track_edges_from_surface_from_manifest(manifest.to_dict())
    return {"status": "success", **result}


@app.post("/api/test/simulate")
async def start_simulation():
    async def simulate():
        previous_source = source_manager.get_active_source_name()
        if previous_source != "replay":
            source_manager.select_source("replay")
        try:
            for _ in range(900):
                frame = ingest_one_active_sample()
                if not frame:
                    return
                await event_bus.emit("processed_frame", frame)
                await asyncio.sleep(1 / 30)
        finally:
            if previous_source != "replay":
                source_manager.select_source(previous_source)

    asyncio.create_task(simulate())
    return {"status": "success", "message": "Telemetry replay simulation started", **source_manager.status()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
