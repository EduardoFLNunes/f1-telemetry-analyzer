"""Deprecated CSV-upload and legacy data endpoints, kept for backward compatibility."""
import io

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile

import main
from routers.track import get_car_state, get_current_track

router = APIRouter()


@router.get("/api/telemetry/live")
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


@router.post("/api/upload/telemetry")
async def upload_telemetry(file: UploadFile = File(...)):
    contents = await file.read()
    try:
        filename = file.filename or "telemetry_upload"
        if filename.lower().endswith(".json"):
            df = pd.read_json(io.BytesIO(contents))
        else:
            df = pd.read_csv(io.BytesIO(contents))
        samples = main.telemetry_samples_from_dataframe(df, source_name=filename, lap_mode="all")
        replay = main.telemetry_samples_from_dataframe(df, source_name=filename, lap_mode="representative")
        if not samples:
            raise ValueError("No telemetry samples found")
        main.telemetry_buffer.clear()
        main.telemetry_buffer.add_samples(samples)
        main.source_manager.replace_replay_samples(samples, replay or samples)
        track = main.reconstruct_track_from_samples(samples, filename.rsplit(".", 1)[0] or main.active_track_cache_name(), closed_loop=True)
        return {"status": "success", "track": main.runtime_state.api_track(), "trackLength": track["trackLength"]}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/api/upload/track")
async def upload_track_deprecated(file: UploadFile = File(...)):
    raise HTTPException(
        status_code=410,
        detail="Static track CSV upload is deprecated. Upload telemetry samples so the backend can reconstruct the track.",
    )


@router.get("/api/data/track")
async def get_track_data():
    return await get_current_track()


@router.get("/api/data/comparison")
async def get_comparison():
    track = main.runtime_state.api_track()
    if not track:
        raise HTTPException(status_code=404, detail="No reconstructed track available yet")
    return {
        "track": track,
        "player": None,
        "ai": None,
        "f1_loaded": False,
        "spatial_source": "telemetry_reconstruction",
    }


@router.get("/api/data/telemetry")
async def get_telemetry_data():
    samples = main.telemetry_buffer.get_samples()
    return {"status": "success", "samples": len(samples)}


@router.get("/api/data/ai-raceline")
async def get_ai_raceline():
    return {"status": "not_ready", "message": "Raceline generation will consume reconstructed track-space in a later phase"}


@router.get("/api/data/track-limits")
async def get_track_limits():
    track = main.runtime_state.api_track()
    if not track:
        raise HTTPException(status_code=404, detail="No reconstructed track available yet")
    return {"status": "success", "left": track["boundsLeft"], "right": track["boundsRight"]}
