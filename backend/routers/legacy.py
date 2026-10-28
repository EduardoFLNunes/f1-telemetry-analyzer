"""Legacy data endpoint, kept because `backend/test_api_comparison.py` still calls it."""
from fastapi import APIRouter, HTTPException

import main

router = APIRouter()


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
