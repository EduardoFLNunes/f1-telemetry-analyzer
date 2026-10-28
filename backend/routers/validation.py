"""Data-quality and validation endpoints."""
from fastapi import APIRouter

import main

router = APIRouter()


@router.get("/api/validation/data-quality")
async def get_data_quality():
    return await main.data_quality_payload()
