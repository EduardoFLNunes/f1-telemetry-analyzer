"""Health, readiness, and runtime status/performance endpoints."""
from fastapi import APIRouter

import main

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "message": "Backend is running",
        "spatial_source": "telemetry_reconstruction",
        "track_loaded": main.runtime_state.track_data is not None,
        "track_cache": main.runtime_state.current_track_name,
        "telemetry": main.telemetry_status_payload(),
    }


@router.get("/api/health")
async def api_health_check():
    return {
        "status": "ok",
        "service": main.BACKEND_SERVICE_NAME,
        "version": main.BACKEND_PHASE_VERSION,
    }


@router.get("/api/runtime/status")
async def get_runtime_status():
    return main.runtime_status_payload()


@router.get("/api/runtime/performance")
async def get_runtime_performance():
    return main.runtime_performance_payload()
