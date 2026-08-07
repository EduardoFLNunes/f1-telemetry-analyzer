"""External reference telemetry (e.g., FastF1) endpoints."""
import asyncio
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException

import main
from core.external_references import ExternalReferenceError

router = APIRouter()


@router.post("/api/references/external/fastf1/import")
async def import_external_fastf1_reference(payload: Optional[Dict[str, Any]] = Body(None)):
    body = payload or {}
    try:
        reference = await asyncio.to_thread(
            main.fastf1_reference_provider.import_reference,
            year=int(body.get("year", 2024)),
            event=str(body.get("event") or "Brazil"),
            session=str(body.get("session") or "Q"),
            driver=body.get("driver"),
            force=bool(body.get("force", False)),
        )
        return {"status": "success", "reference": reference.to_api(include_samples=False)}
    except ExternalReferenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/api/references/external")
async def list_external_references(include_samples: bool = False):
    return {
        "status": "success",
        "references": main.external_reference_repository.list_references(include_samples=include_samples),
    }


@router.get("/api/references/external/{reference_id}")
async def get_external_reference(reference_id: str, include_samples: bool = True):
    reference = main.external_reference_repository.get(reference_id)
    if not reference:
        raise HTTPException(status_code=404, detail="External reference not found")
    return {"status": "success", "reference": reference.to_api(include_samples=include_samples)}
