"""Data-quality and validation endpoints."""
from fastapi import APIRouter

import main

router = APIRouter()


@router.get("/api/validation/data-quality")
async def get_data_quality():
    return await main.data_quality_payload()


@router.get("/api/validation/laps")
async def get_lap_validation():
    return {
        "status": "success",
        "laps": (await main.data_quality_payload())["laps"],
    }


@router.get("/api/validation/udp")
async def get_udp_validation():
    return {
        "status": "success",
        "opponents": (await main.data_quality_payload())["opponents"],
    }


@router.get("/api/validation/track")
async def get_track_validation():
    return {
        "status": "success",
        "track": (await main.data_quality_payload())["track"],
    }
