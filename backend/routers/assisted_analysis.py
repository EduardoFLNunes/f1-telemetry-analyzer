"""Post-lap assisted driving analysis endpoints."""
import asyncio
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Query

import main

router = APIRouter()


def _get_assisted_analysis_or_404(
    lap_id: str,
    reference_lap_id: Optional[str] = None,
    *,
    include_external_reference: bool = False,
    external_reference_id: Optional[str] = None,
):
    if not isinstance(include_external_reference, bool):
        include_external_reference = False
    if not isinstance(external_reference_id, str):
        external_reference_id = None
    cached = main.assisted_analysis_service.get_cached_analysis(
        lap_id,
        reference_lap_id=reference_lap_id,
        include_external_reference=include_external_reference,
        external_reference_id=external_reference_id,
    )
    if not cached:
        raise HTTPException(status_code=404, detail="Assisted analysis is not available for this lap yet")
    return cached


def _run_assisted_analysis(
    lap_id: str,
    reference_lap_id: Optional[str] = None,
    force: bool = False,
    payload: Optional[Dict[str, Any]] = None,
    include_external_reference: bool = False,
    external_reference_id: Optional[str] = None,
):
    try:
        body = payload or {}
        if not isinstance(include_external_reference, bool):
            include_external_reference = False
        if not isinstance(external_reference_id, str):
            external_reference_id = None
        reference = reference_lap_id or body.get("referenceLapId") or body.get("reference_lap_id")
        force_analysis = bool(force or body.get("force", False))
        external = bool(include_external_reference or body.get("includeExternalReference") or body.get("include_external_reference"))
        external_id = external_reference_id or body.get("externalReferenceId") or body.get("external_reference_id")
        return main.assisted_analysis_service.analyze_lap(
            lap_id,
            reference_lap_id=reference,
            include_external_reference=external,
            external_reference_id=external_id,
            force=force_analysis,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/api/assisted-analysis/laps")
async def list_assisted_analysis_laps():
    return main.assisted_analysis_service.list_laps()


@router.get("/api/assisted-analysis/laps/{lap_id}/analysis")
async def get_assisted_analysis(lap_id: str, reference_lap_id: Optional[str] = None):
    return _get_assisted_analysis_or_404(lap_id, reference_lap_id)


@router.post("/api/assisted-analysis/laps/{lap_id}/analysis")
async def request_assisted_analysis(
    lap_id: str,
    reference_lap_id: Optional[str] = None,
    force: bool = False,
    payload: Optional[Dict[str, Any]] = Body(None),
):
    return _run_assisted_analysis(lap_id, reference_lap_id, force, payload)


@router.get("/api/analysis/assisted/lap/{lapId}")
async def get_phase14_assisted_analysis(
    lapId: str,
    reference_lap_id: Optional[str] = None,
    include_external_reference: bool = Query(False, alias="includeExternalReference"),
    external_reference_id: Optional[str] = Query(None, alias="externalReferenceId"),
):
    return _get_assisted_analysis_or_404(
        lapId,
        reference_lap_id,
        include_external_reference=include_external_reference,
        external_reference_id=external_reference_id,
    )


@router.post("/api/analysis/assisted/lap/{lapId}")
async def request_phase14_assisted_analysis(
    lapId: str,
    reference_lap_id: Optional[str] = None,
    include_external_reference: bool = Query(False, alias="includeExternalReference"),
    external_reference_id: Optional[str] = Query(None, alias="externalReferenceId"),
    force: bool = False,
    payload: Optional[Dict[str, Any]] = Body(None),
):
    return _run_assisted_analysis(
        lapId,
        reference_lap_id,
        force,
        payload,
        include_external_reference=include_external_reference,
        external_reference_id=external_reference_id,
    )


@router.get("/api/analysis/assisted/lap/{lapId}/telemetry")
async def get_phase14_assisted_lap_telemetry(
    lapId: str,
    max_samples: int = Query(36_000, alias="maxSamples", ge=100, le=100_000),
):
    try:
        return await asyncio.to_thread(
            main.assisted_analysis_service.lap_telemetry,
            lapId,
            max_samples,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/api/analysis/coach/lap/{lapId}")
async def get_lap_coaching(lapId: str):
    """
    Everything the coach would have said over a recorded lap.

    The replay plays in the browser and its samples never reach this process,
    so the live coach -- which listens for `processed_frame` -- cannot see a
    recorded lap. Rather than write a second coach in TypeScript that would
    drift from this one, the lap is walked through the same object here and the
    events come back tagged with the lap time they belong to, for the player to
    surface as the car reaches them.

    Walking a lap is CPU work, so it runs off the event loop: a second of
    blocking here costs the collector samples, which is how this backend already
    lost 4.6% of a session.
    """
    from core.live.driving_coach import coach_recorded_lap

    def work() -> Dict[str, Any]:
        try:
            descriptor, df = main.assisted_analysis_service.loader.load_lap(lapId)
        except Exception as error:
            raise HTTPException(status_code=404, detail=f"Lap not available: {error}")

        model = main.assisted_analysis_service._reference_model(descriptor.track)  # noqa: SLF001
        if model is None or not model.targets:
            return {
                "status": "NO_MODEL",
                "reason": "reference_model_not_trained_for_track",
                "track": descriptor.track,
                "events": [],
                "speech": [],
            }

        result = coach_recorded_lap(
            df,
            model,
            lap_number=descriptor.lap_number or 0,
            track=descriptor.track or "",
            driver_id=descriptor.driver_id or "player_1",
        )
        result.update({
            "lapId": lapId,
            "lapNumber": descriptor.lap_number,
            "lapTime": descriptor.lap_time,
            "track": descriptor.track,
            "model": {
                "lapsInModel": model.lap_count,
                "idealLapSeconds": model.ideal_lap_seconds,
                "bestLapSeconds": model.best_lap_seconds,
                "builtAt": model.built_at,
            },
        })
        return result

    return await asyncio.to_thread(work)
