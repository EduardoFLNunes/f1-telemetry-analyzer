"""Track geometry endpoint."""
from fastapi import APIRouter

import main

router = APIRouter()


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
