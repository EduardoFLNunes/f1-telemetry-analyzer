"""Session recording, persisted sessions, and offline lap replay endpoints."""
import asyncio
from typing import Any, Dict, Tuple

from fastapi import APIRouter, HTTPException, Query

import main

router = APIRouter()


def _recording_lap_id(session_id: str, lap_number: int) -> str:
    return f"rec__{main._safe_cache_fragment(session_id)}__{int(lap_number)}"


def _parse_recording_lap_id(lap_id: str) -> Tuple[str, int]:
    if not isinstance(lap_id, str) or not lap_id.startswith("rec__"):
        raise ValueError("Offline lap id must use the rec__<session>__<lap> format")
    body = lap_id[len("rec__"):]
    if "__" not in body:
        raise ValueError("Offline lap id must include a session id and lap number")
    session_id, lap_number_text = body.rsplit("__", 1)
    if not session_id:
        raise ValueError("Offline lap id is missing the session id")
    try:
        lap_number = int(lap_number_text)
    except (TypeError, ValueError) as exc:
        raise ValueError("Offline lap id has an invalid lap number") from exc
    return session_id, lap_number


def _has_assisted_analysis(lap_id: str) -> bool:
    try:
        return main.assisted_analysis_service.has_cached_analysis(lap_id)
    except Exception:
        return False


def _enrich_recorded_lap(lap: Dict[str, Any], session: Dict[str, Any]) -> Dict[str, Any]:
    lap_number = int(lap.get("lapNumber") or 0)
    lap_id = str(lap.get("lapId") or _recording_lap_id(session["sessionId"], lap_number))
    accepted = bool(lap.get("acceptedByPhase13", lap.get("valid", False)))
    best_lap_time = session.get("bestLapTime")
    lap_time = lap.get("lapTime", lap.get("duration"))
    try:
        best_candidate = accepted and lap_time is not None and best_lap_time is not None and abs(float(lap_time) - float(best_lap_time)) <= 0.001
    except (TypeError, ValueError):
        best_candidate = False
    has_analysis = _has_assisted_analysis(lap_id) if accepted else False
    return {
        **lap,
        "lapId": lap_id,
        "sessionId": session.get("sessionId"),
        "track": session.get("track"),
        "car": session.get("car"),
        "startedAt": session.get("startedAt"),
        "completedAt": session.get("endedAt") if lap.get("completed") else None,
        "lapTime": lap_time,
        "reliabilityStatus": lap.get("reliabilityStatus") or lap.get("validationStatus"),
        "acceptedByPhase13": accepted,
        "hasAssistedAnalysis": has_analysis,
        "analysisStatus": "AVAILABLE" if has_analysis else ("NOT_GENERATED" if accepted else "NOT_ELIGIBLE"),
        "canAnalyze": accepted,
        "bestLapCandidate": best_candidate,
        "referenceCandidate": accepted and int(lap.get("sampleCount") or 0) >= 40,
    }


def _enrich_recorded_session(session: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(session)
    enriched["offlineAvailable"] = True
    enriched["storageMode"] = "recordings"
    enriched["liveDependency"] = False
    enriched["recordingRoot"] = str(main.session_repository.root)
    enriched["laps"] = [
        _enrich_recorded_lap(lap, enriched)
        for lap in (session.get("laps") or [])
        if isinstance(lap, dict)
    ]
    return enriched


def _offline_lap_summary_from_id(lap_id: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    session_id, lap_number = _parse_recording_lap_id(lap_id)
    session = main.session_repository.session_summary(session_id, allow_large_scan=True)
    if not session:
        raise FileNotFoundError("Recorded session not found")
    enriched_session = _enrich_recorded_session(session)
    lap = next(
        (item for item in enriched_session.get("laps", []) if int(item.get("lapNumber") or -1) == lap_number),
        None,
    )
    if not lap:
        raise FileNotFoundError("Recorded lap not found")
    return enriched_session, lap


@router.get("/api/recording/status")
async def get_recording_status():
    if not main.recording_runtime:
        return {
            "enabled": False,
            "recording": False,
            "sessionId": None,
            "directory": None,
            "playerSamplesWritten": 0,
            "opponentSnapshotsWritten": 0,
            "eventsWritten": 0,
            "queueSize": 0,
            "droppedFrames": 0,
        }
    return main.recording_runtime.status().to_api()


@router.post("/api/recording/start")
async def start_recording():
    if not main.recording_runtime:
        raise HTTPException(status_code=503, detail="Recording runtime is not available")
    return main.recording_runtime.start_recording().to_api()


@router.post("/api/recording/stop")
async def stop_recording():
    if not main.recording_runtime:
        raise HTTPException(status_code=503, detail="Recording runtime is not available")
    return main.recording_runtime.stop_recording().to_api()


@router.get("/api/sessions")
async def list_recorded_sessions(limit: int = Query(30, ge=1, le=200)):
    active_session_id = main.recording_runtime.status().sessionId if main.recording_runtime else None
    sessions = await asyncio.to_thread(main.session_repository.list_sessions, limit)
    sessions = [_enrich_recorded_session(session) for session in sessions]
    for session in sessions:
        session["active"] = session["sessionId"] == active_session_id
    return {
        "status": "success",
        "recordingRoot": str(main.session_repository.root),
        "activeSessionId": active_session_id,
        "offlineAvailable": True,
        "liveDependency": False,
        "sessions": sessions,
    }


@router.get("/api/sessions/{session_id}")
async def get_recorded_session(session_id: str):
    try:
        session = await asyncio.to_thread(main.session_repository.session_summary, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not session:
        raise HTTPException(status_code=404, detail="Recorded session not found")
    session = _enrich_recorded_session(session)
    return {"status": "success", "session": session}


@router.get("/api/sessions/{session_id}/laps")
async def get_recorded_session_laps(session_id: str):
    try:
        session = await asyncio.to_thread(main.session_repository.session_summary, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not session:
        raise HTTPException(status_code=404, detail="Recorded session not found")
    enriched = _enrich_recorded_session(session)
    return {
        "status": "success",
        "sessionId": enriched["sessionId"],
        "track": enriched.get("track"),
        "car": enriched.get("car"),
        "recordingRoot": str(main.session_repository.root),
        "offlineAvailable": True,
        "liveDependency": False,
        "laps": enriched.get("laps", []),
    }


@router.get("/api/sessions/{session_id}/laps/{lap_number}")
async def get_recorded_lap(
    session_id: str,
    lap_number: int,
    max_samples: int = Query(36_000, alias="maxSamples", ge=1_000, le=100_000),
):
    try:
        lap = await asyncio.to_thread(
            main.session_repository.lap_detail,
            session_id,
            lap_number,
            max_samples,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not lap:
        raise HTTPException(status_code=404, detail="Recorded lap not found")
    return {"status": "success", **lap}


@router.get("/api/laps/{lap_id}")
async def get_offline_recorded_lap(lap_id: str):
    try:
        session, lap = await asyncio.to_thread(_offline_lap_summary_from_id, lap_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "status": "success",
        "recordingRoot": str(main.session_repository.root),
        "offlineAvailable": True,
        "liveDependency": False,
        "session": {
            "sessionId": session.get("sessionId"),
            "track": session.get("track"),
            "car": session.get("car"),
            "startedAt": session.get("startedAt"),
            "endedAt": session.get("endedAt"),
            "bestLapTime": session.get("bestLapTime"),
        },
        "lap": lap,
    }


@router.get("/api/laps/{lap_id}/summary")
async def get_offline_recorded_lap_summary(lap_id: str):
    try:
        _, lap = await asyncio.to_thread(_offline_lap_summary_from_id, lap_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "status": "success",
        "recordingRoot": str(main.session_repository.root),
        "offlineAvailable": True,
        "liveDependency": False,
        "lap": lap,
    }


@router.get("/api/laps/{lap_id}/replay")
async def get_offline_recorded_lap_replay(
    lap_id: str,
    max_samples: int = Query(36_000, alias="maxSamples", ge=100, le=100_000),
):
    try:
        session_id, lap_number = _parse_recording_lap_id(lap_id)
        session = await asyncio.to_thread(main.session_repository.session_summary, session_id, True)
        lap = await asyncio.to_thread(
            main.session_repository.lap_detail,
            session_id,
            lap_number,
            max_samples,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not session or not lap:
        raise HTTPException(status_code=404, detail="Recorded lap not found")

    enriched_session = _enrich_recorded_session(session)
    summary = dict(lap.get("summary") or {})
    if summary:
        summary = _enrich_recorded_lap(summary, enriched_session)
    samples = [
        main._normalize_replay_sample(sample)
        for sample in (lap.get("samples") or [])
        if isinstance(sample, dict)
    ]
    return {
        "status": "success",
        "mode": "offline_lap_replay",
        "source": "persisted_lap",
        "recordingRoot": str(main.session_repository.root),
        "offlineAvailable": True,
        "liveDependency": False,
        "sharedMemoryDependency": False,
        "lapId": lap_id,
        "session": {
            "sessionId": enriched_session.get("sessionId"),
            "track": enriched_session.get("track"),
            "car": enriched_session.get("car"),
            "startedAt": enriched_session.get("startedAt"),
            "endedAt": enriched_session.get("endedAt"),
        },
        "summary": summary or lap.get("summary"),
        "totalSampleCount": lap.get("totalSampleCount"),
        "returnedSampleCount": len(samples),
        "sampleStride": lap.get("sampleStride"),
        "truncated": lap.get("truncated"),
        "samples": samples,
    }


@router.get("/api/laps/{lap_id}/samples")
async def get_offline_recorded_lap_samples(
    lap_id: str,
    limit: int = Query(10_000, ge=100, le=100_000),
):
    try:
        session_id, lap_number = _parse_recording_lap_id(lap_id)
        lap = await asyncio.to_thread(
            main.session_repository.lap_detail,
            session_id,
            lap_number,
            limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not lap:
        raise HTTPException(status_code=404, detail="Recorded lap not found")
    summary = dict(lap.get("summary") or {})
    if summary:
        summary = _enrich_recorded_lap(summary, {"sessionId": session_id, "track": None, "car": None, "bestLapTime": None})
    return {
        "status": "success",
        "recordingRoot": str(main.session_repository.root),
        "offlineAvailable": True,
        "liveDependency": False,
        "lapId": lap_id,
        "sessionId": session_id,
        "lapNumber": lap_number,
        "summary": summary or lap.get("summary"),
        "totalSampleCount": lap.get("totalSampleCount"),
        "returnedSampleCount": lap.get("returnedSampleCount"),
        "sampleStride": lap.get("sampleStride"),
        "truncated": lap.get("truncated"),
        "samples": lap.get("samples", []),
    }
