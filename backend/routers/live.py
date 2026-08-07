"""Live telemetry, opponents, comparison, racing-line, and coach endpoints."""
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException, Query

import main
from core.car_physics import build_car_physics_debug, build_opponent_car_physics, build_player_car_physics
from core.comparison_analysis import build_live_comparison_payload
from core.opponents import SOURCE_NAME as OPPONENTS_SOURCE_NAME
from core.racing_line_analysis import build_live_racing_line_payload
from core.telemetry.telemetry_models import TelemetrySample

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/live/telemetry")
async def get_live_telemetry(
    includeTrack: bool = Query(False),
    includeTrajectory: bool = Query(False),
):
    car = main.runtime_state.car_projected_state
    if not car:
        car = main.ingest_one_active_sample()
    status = main.telemetry_status_payload()
    track = main.runtime_state.api_track() if includeTrack else None
    return {
        "status": "success",
        "source": main.source_manager.get_active_source_name(),
        "playerSource": main.source_manager.player_source_name(),
        **status,
        "track": track if includeTrack and status["activeTrackReady"] else None,
        "centerline": track["centerline"] if includeTrack and track and status["activeTrackReady"] else None,
        "liveTrajectory": main.live_trajectory_api() if includeTrajectory else [],
        "car": car,
    }


@router.get("/api/live/opponents")
async def get_live_opponents():
    latest = main.opponents_buffer.latest()
    metadata = main.opponents_buffer.metadata()
    opponents = [latest[car_id].to_api() for car_id in sorted(latest)]
    return {
        "status": "success",
        "source": OPPONENTS_SOURCE_NAME,
        "enabled": main.opponents_config.enabled,
        "receiverStatus": main.stream_status_from_age(
            metadata["lastUpdateTimestamp"],
            float(metadata["staleAfterSeconds"]),
        ),
        "count": len(opponents),
        "track": metadata["track"],
        "sessionTime": metadata["sessionTime"],
        "lastUpdateTimestamp": metadata["lastUpdateTimestamp"],
        "staleAfterSeconds": metadata["staleAfterSeconds"],
        "discardedOutOfOrderCount": metadata["discardedOutOfOrderCount"],
        "opponents": opponents,
    }


def live_comparison_payload(micro_sectors: int = 50) -> Dict[str, Any]:
    micro_sector_count = max(1, min(200, int(micro_sectors or 50)))
    payload = build_live_comparison_payload(
        telemetry_samples=main.telemetry_buffer.get_samples(),
        opponent_history=main.opponents_buffer.history(),
        track_data=main.runtime_state.track_data,
        track_name=main.runtime_state.current_track_name or main.source_manager.current_track_name(),
        micro_sector_count=micro_sector_count,
    )
    logger.debug(
        "Live comparison generated: player=%s reference=%s opponents=%s validMicroSectors=%s",
        payload.get("debug", {}).get("playerSamples"),
        payload.get("debug", {}).get("referenceSamples"),
        payload.get("debug", {}).get("opponentsAnalyzed"),
        payload.get("debug", {}).get("validMicroSectors"),
    )
    return payload


def live_racing_line_payload(
    micro_sectors: int = 50,
    *,
    include_visual_line: bool = True,
    include_comparison: bool = True,
) -> Dict[str, Any]:
    micro_sector_count = max(1, min(200, int(micro_sectors or 50)))
    completed_live_lap = (
        list(main.telemetry_runtime.lap_collector.completed_lap_samples)
        if main.telemetry_runtime and main.telemetry_runtime.lap_collector.completed_lap_samples
        else []
    )
    payload = build_live_racing_line_payload(
        telemetry_samples=main.telemetry_buffer.get_samples(),
        track_data=main.runtime_state.track_data,
        track_name=main.runtime_state.current_track_name or main.source_manager.current_track_name(),
        micro_sector_count=micro_sector_count,
        include_visual_line=include_visual_line,
        include_comparison=include_comparison,
        fallback_reference_samples=completed_live_lap,
    )
    logger.debug(
        "Racing Line generated: status=%s reference=%s player=%s validSegments=%s",
        payload.get("status"),
        payload.get("debug", {}).get("referenceSamples"),
        payload.get("debug", {}).get("currentLapSamples"),
        (payload.get("racingLine") or {}).get("debug", {}).get("validSegments"),
    )
    return payload


def live_player_physics_payload() -> Dict[str, Any]:
    samples = main.telemetry_buffer.get_samples()
    player_samples = [sample for sample in samples if int(getattr(sample, "carId", 0) or 0) == 0]
    latest_sample = player_samples[-1] if player_samples else main.runtime_state.last_sample
    if latest_sample is None:
        main.ingest_one_active_sample()
        samples = main.telemetry_buffer.get_samples()
        player_samples = [sample for sample in samples if int(getattr(sample, "carId", 0) or 0) == 0]
        latest_sample = player_samples[-1] if player_samples else main.runtime_state.last_sample

    recent_player_samples = player_samples[-20:]
    player_physics = build_player_car_physics(latest_sample, recent_player_samples)

    opponent_history = main.opponents_buffer.history()
    latest_opponents = main.opponents_buffer.latest()
    opponent_physics = []
    opponent_sample_count = 0
    for car_id in sorted(latest_opponents):
        if car_id == 0:
            continue
        history = opponent_history.get(car_id, [])
        opponent_sample_count += len(history)
        opponent_physics.append(
            {
                "carId": car_id,
                "physics": build_opponent_car_physics(latest_opponents[car_id], history[-20:]),
            }
        )

    debug = build_car_physics_debug(
        player_physics,
        [item["physics"] for item in opponent_physics],
        player_sample_count=len(player_samples),
        opponent_sample_count=opponent_sample_count,
    )
    logger.debug(
        "Car physics generated: playerSamples=%s opponentSamples=%s completeness=%s",
        debug["playerPhysicsSamples"],
        debug["opponentPhysicsSamples"],
        debug["playerDataCompleteness"],
    )
    return {
        "status": "success",
        "source": main.source_manager.get_active_source_name(),
        "track": main.source_manager.current_track_name() or main.runtime_state.current_track_name,
        "generatedAt": datetime.utcnow().isoformat(),
        "player": player_physics,
        "opponents": opponent_physics,
        "carPhysicsDebug": debug,
    }


@router.get("/api/live/comparison")
async def get_live_comparison(microSectors: int = Query(50, ge=1, le=200)):
    return live_comparison_payload(microSectors)


@router.get("/api/analysis/comparison")
async def get_analysis_comparison(microSectors: int = Query(50, ge=1, le=200)):
    return live_comparison_payload(microSectors)


@router.get("/api/live/racing-line")
async def get_live_racing_line(
    microSectors: int = Query(50, ge=1, le=200),
    includeVisualLine: bool = Query(True),
    includeComparison: bool = Query(True),
):
    return live_racing_line_payload(
        microSectors,
        include_visual_line=includeVisualLine,
        include_comparison=includeComparison,
    )


@router.get("/api/analysis/racing-line")
async def get_analysis_racing_line(
    microSectors: int = Query(50, ge=1, le=200),
    includeVisualLine: bool = Query(False),
    includeComparison: bool = Query(True),
):
    return live_racing_line_payload(
        microSectors,
        include_visual_line=includeVisualLine,
        include_comparison=includeComparison,
    )


@router.get("/api/live/player-physics")
async def get_live_player_physics():
    return live_player_physics_payload()


@router.get("/api/live/coach")
async def get_live_coach():
    return {
        "status": "success",
        "source": "event_bus",
        "eventCount": len(main.recent_coaching_events),
        "events": main.recent_coaching_events[:20],
    }


@router.get("/api/live/source")
async def get_live_source():
    return {"status": "success", **main.telemetry_status_payload()}


@router.post("/api/live/source/{source}")
async def set_live_source(source: str):
    try:
        requested_source = (source or "").strip().lower().replace("-", "_")
        if requested_source in {"ac", "assetto", "assetto_corsa", "assetto_corsa_shared_memory"}:
            gate_status = main.shared_memory_gate_status()
            if not gate_status.get("allowed", True):
                reason = gate_status.get("reason")
                if reason == "stale_assetto_corsa_shared_memory_without_process":
                    raise RuntimeError(
                        "Stale Assetto Corsa shared memory pages exist without acs.exe. "
                        "Close the process that created them before opening Assetto Corsa."
                    )
                if reason == "waiting_for_assetto_corsa_shared_memory_pages":
                    raise RuntimeError(
                        "Assetto Corsa is running, but shared memory pages are not ready. "
                        "Load a driving session first, then the backend will connect."
                    )
                if reason == "waiting_for_assetto_corsa_static_data":
                    raise RuntimeError(
                        "Assetto Corsa is running, but static telemetry is not ready. "
                        "Wait until a car/track session is loaded."
                    )
                raise RuntimeError(
                    "Assetto Corsa is not running. Open Assetto Corsa first, then the backend will connect to shared memory."
                )

        if main.telemetry_runtime:
            main.telemetry_runtime.stop()
            main.telemetry_runtime = None
        selected = main.source_manager.select_source(source)
        main.reset_runtime_state()
        main.prime_active_source()
        main.initialize_spatial_state()
        main.telemetry_runtime = main.build_telemetry_runtime()
        main.telemetry_runtime.start(asyncio.get_running_loop())
        return {"status": "success", "source": selected, **main.telemetry_status_payload()}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/api/live/telemetry")
async def ingest_live_telemetry(payload: Any = Body(...)):
    raw_samples = payload if isinstance(payload, list) else payload.get("samples", payload)
    samples = [TelemetrySample.from_dict(item) for item in raw_samples] if isinstance(raw_samples, list) else [TelemetrySample.from_dict(raw_samples)]
    for sample in samples:
        main.player_reliability.observe(sample)
    main.telemetry_buffer.add_samples(samples)
    frame = main.runtime_state.update_car(samples[-1]) if samples else None
    if frame:
        await main.event_bus.emit("processed_frame", frame)
    return {"status": "success", "ingested": len(samples), "car": frame}
