"""Simulation endpoint used by `backend/stress_test.py`."""
import asyncio
import logging

from fastapi import APIRouter

import main

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/test/simulate")
async def start_simulation():
    async def simulate():
        previous_source = main.source_manager.get_active_source_name()
        if previous_source != "replay":
            main.source_manager.select_source("replay")
        try:
            for _ in range(900):
                frame = main.ingest_one_active_sample()
                if not frame:
                    return
                await main.event_bus.emit("processed_frame", frame)
                await asyncio.sleep(1 / 30)
        finally:
            if previous_source != "replay":
                main.source_manager.select_source(previous_source)

    asyncio.create_task(simulate())
    return {"status": "success", "message": "Telemetry replay simulation started", **main.source_manager.status()}
