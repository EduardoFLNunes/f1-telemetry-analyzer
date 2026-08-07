"""Track geometry, track cache, and car-state endpoints."""
from fastapi import APIRouter, HTTPException

import main
from core.geometry.track_geometry_provider import DebugTrajectoryTrackGeometryProvider
from core.live.lap_collector import TrackBuildState

router = APIRouter()


@router.get("/api/track/current")
async def get_current_track():
    track = main.runtime_state.api_track()
    status = main.telemetry_status_payload()
    return {
        "status": "success",
        "source": main.source_manager.get_active_source_name(),
        "playerSource": main.source_manager.player_source_name(),
        **status,
        "track": track if status["activeTrackReady"] else None,
        "centerline": track["centerline"] if track and status["activeTrackReady"] else None,
        "liveTrajectory": main.live_trajectory_api(),
    }


@router.get("/api/track/geometry")
async def get_track_geometry():
    track = main.runtime_state.api_track()
    status = main.telemetry_status_payload()
    return {
        "status": "success",
        "source": main.source_manager.get_active_source_name(),
        **status,
        "track": track if status["activeTrackReady"] else None,
    }


@router.get("/api/track/cache")
async def get_track_cache():
    return {"status": "success", "tracks": main.track_cache.list_cached_tracks()}


@router.post("/api/track/cache")
async def rebuild_track_cache():
    samples = main.telemetry_buffer.get_samples()
    if not samples and main.source_manager.get_active_source_name() == "replay":
        samples = main.source_manager.get_reconstruction_samples()
    if not samples:
        raise HTTPException(status_code=400, detail="No telemetry samples available for reconstruction")
    if main.source_manager.get_active_source_name() == "assetto_corsa" and main.telemetry_runtime:
        if main.runtime_state.track_build_state == TrackBuildState.TRACK_READY:
            track = main.runtime_state.track_data
            return {
                "status": "success",
                "source": main.source_manager.get_active_source_name(),
                **main.telemetry_status_payload(),
                "trackCache": main.runtime_state.current_track_name,
                "track": main.runtime_state.api_track(),
                "trackLength": track["trackLength"] if track else 0,
            }
        if not DebugTrajectoryTrackGeometryProvider.enabled():
            raise HTTPException(
                status_code=400,
                detail="Driver trajectory TrackGeometry reconstruction is disabled. Set DEBUG_ALLOW_TRAJECTORY_TRACK=true for debug-only use.",
            )
        if not main.telemetry_runtime.lap_collector.completed_lap_samples:
            raise HTTPException(status_code=400, detail="A complete lap is required before building active TrackGeometry")
        ok = main.telemetry_runtime.trigger_reconstruction(main.active_track_cache_name(), save_to_cache=True)
        if not ok:
            raise HTTPException(status_code=400, detail="Candidate lap failed reconstruction")
        track = main.runtime_state.track_data
    else:
        track = main.reconstruct_track_from_samples(samples, main.active_track_cache_name(), closed_loop=True)
    return {
        "status": "success",
        "source": main.source_manager.get_active_source_name(),
        **main.telemetry_status_payload(),
        "trackCache": main.runtime_state.current_track_name,
        "track": main.runtime_state.api_track(),
        "trackLength": track["trackLength"] if track else 0,
    }


@router.post("/api/track/reconstruct")
async def reconstruct_current_track():
    return await rebuild_track_cache()


@router.get("/api/car/state")
async def get_car_state():
    if not main.runtime_state.car_projected_state:
        main.ingest_one_active_sample()
    if not main.runtime_state.car_projected_state:
        raise HTTPException(status_code=404, detail="No car state available yet")
    return {"status": "success", "car": main.runtime_state.car_projected_state}
