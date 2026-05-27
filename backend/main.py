"""
Telemetry-driven spatial backend for F1 Telemetry Analyzer.

The backend owns reconstruction, projection, boundaries, caching, and live car
state. CSV track maps are deliberately not used as a source of truth.
"""
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional
import asyncio
import io
import logging
import re

import pandas as pd
from fastapi import Body, FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from core.debug.ac_shared_memory_full_inventory import build_ac_shared_memory_full_inventory
from core.cache.track_cache import TrackCache
from core.debug.spatial_debug import projection_debug_payload
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
from core.opponents import OpponentsRuntime, OpponentsStateBuffer, SOURCE_NAME as OPPONENTS_SOURCE_NAME
from core.performance_metrics import performance_metrics
from core.recording.recording_runtime import RecordingRuntime, config_from_env as recording_config_from_env
from core.reconstruction.track_reconstruction import TrackReconstructor
from core.telemetry.telemetry_buffer import TelemetryBuffer
from core.telemetry.telemetry_models import TelemetrySample
from core.telemetry.telemetry_reader_impl import TelemetrySourceManager, telemetry_samples_from_dataframe
from core.track_file_resolver import TrackFileResolver
from core.telemetry_events import event_bus
from core.websocket_server import manager as ws_manager


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
REPLAY_TRACK_CACHE_NAME = "telemetry_reconstructed_multilap_v1"
LIVE_TRACK_CACHE_PREFIX = "assetto_corsa"
TRACK_CACHE_DIR = REPO_ROOT / "data" / "cache" / "tracks"
PRIMARY_TELEMETRY_FIXTURE = REPO_ROOT / "data" / "example_telemetry.csv"
DEBUG_TELEMETRY_FIXTURE = REPO_ROOT / "data" / "example_telemetryOld.csv"

runtime_state = RuntimeState()
telemetry_buffer = TelemetryBuffer(max_size=20000)
track_cache = TrackCache(cache_dir=str(TRACK_CACHE_DIR))
reconstructor = TrackReconstructor()
source_manager = TelemetrySourceManager.from_env((PRIMARY_TELEMETRY_FIXTURE, DEBUG_TELEMETRY_FIXTURE))
telemetry_runtime: Optional[TelemetryRuntime] = None
opponents_buffer = OpponentsStateBuffer()
opponents_runtime: Optional[OpponentsRuntime] = None
recording_runtime: Optional[RecordingRuntime] = None


def _safe_cache_fragment(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "_", value.strip())
    return cleaned.strip("_") or "live"


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
    runtime_state.last_sample = None
    runtime_state.car_projected_state = None
    runtime_state.last_distance_along_track = None


def ingest_one_active_sample() -> Optional[Dict[str, Any]]:
    sample = source_manager.read_sample()
    if not sample:
        return None
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
    )


def build_opponents_runtime() -> OpponentsRuntime:
    return OpponentsRuntime(buffer=opponents_buffer)


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
        config=recording_config_from_env(REPO_ROOT),
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    global telemetry_runtime, opponents_runtime, recording_runtime

    source_manager.select_source()
    prime_active_source()
    initialize_spatial_state()
    recording_runtime = build_recording_runtime()
    recording_runtime.start()
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
async def get_live_telemetry():
    car = runtime_state.car_projected_state
    track = runtime_state.api_track()
    if not car:
        car = ingest_one_active_sample()
    status = telemetry_status_payload()
    return {
        "status": "success",
        "source": source_manager.get_active_source_name(),
        **status,
        "track": track if status["activeTrackReady"] else None,
        "centerline": track["centerline"] if track and status["activeTrackReady"] else None,
        "liveTrajectory": live_trajectory_api(),
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
        "count": len(opponents),
        "track": metadata["track"],
        "sessionTime": metadata["sessionTime"],
        "lastUpdateTimestamp": metadata["lastUpdateTimestamp"],
        "staleAfterSeconds": metadata["staleAfterSeconds"],
        "opponents": opponents,
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


@app.get("/api/debug/performance")
async def get_performance_metrics():
    recording_status = recording_runtime.status().to_api() if recording_runtime else {}
    metrics = performance_metrics.snapshot()
    return {
        "status": "success",
        **metrics,
        "recordingQueueSize": recording_status.get("queueSize", 0),
        "recordingDroppedFrames": recording_status.get("droppedFrames", 0),
        "eventBusQueueSize": None,
        "websocketConnections": len(ws_manager.active_connections),
    }


@app.get("/api/live/source")
async def get_live_source():
    return {"status": "success", **telemetry_status_payload()}


@app.post("/api/live/source/{source}")
async def set_live_source(source: str):
    global telemetry_runtime

    try:
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
