"""Debug, diagnostics, KN5 inventory, and simulation endpoints."""
import asyncio
import logging

from fastapi import APIRouter, HTTPException

import main
from core.debug.ac_shared_memory_full_inventory import build_ac_shared_memory_full_inventory
from core.debug.spatial_debug import projection_debug_payload
from core.kn5.kn5_inventory import build_kn5_inventory_from_manifest
from core.kn5.kn5_surface_extraction import build_kn5_surface_extraction_from_manifest
from core.kn5.track_edges_from_surface import build_track_edges_from_surface_from_manifest
from core.kn5.track_surface_polygon import build_track_surface_polygon_from_manifest
from core.track_file_resolver import TrackFileResolver

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/debug/performance")
async def get_performance_metrics():
    recording_status = main.recording_runtime.status().to_api() if main.recording_runtime else {}
    metrics = main.performance_metrics.snapshot()
    return {
        "status": "success",
        **metrics,
        "recordingQueueSize": recording_status.get("queueSize", 0),
        "recordingDroppedFrames": recording_status.get("droppedFrames", 0),
        "eventBusQueueSize": main.event_bus.snapshot().get("pendingTasks", 0),
        "websocketConnections": len(main.ws_manager.active_connections),
        "websocketPendingTasks": main.ws_manager.pending_tasks(),
    }


@router.get("/api/debug/projection")
async def get_projection_debug():
    if not main.runtime_state.car_projected_state:
        raise HTTPException(status_code=404, detail="No projected car state available")
    return {"status": "success", "debug": projection_debug_payload(main.runtime_state.car_projected_state)}


@router.get("/api/debug/ac-shared-memory-full-inventory")
async def get_ac_shared_memory_full_inventory():
    return {"status": "success", "inventory": build_ac_shared_memory_full_inventory()}


@router.get("/api/debug/track-file-manifest")
async def get_track_file_manifest():
    if main.source_manager.get_active_source_name() == "assetto_corsa" and not main.source_manager.current_track_name():
        main.ingest_one_active_sample()

    track_name = main.source_manager.current_track_name()
    track_config = main.source_manager.current_track_config()
    ac_install_path = main.source_manager.current_ac_install_path()
    game_code = main.source_manager.current_game_code() or "assetto_corsa"
    source = main.source_manager.get_active_source_name()

    logger.info(
        "Track file manifest requested: source=%s game=%s track=%s config=%s acInstallPath=%s",
        source,
        game_code,
        track_name,
        track_config,
        ac_install_path,
    )
    resolver = TrackFileResolver(ac_root=ac_install_path)
    manifest = resolver.build_track_file_manifest(
        track_name or "",
        track_config,
        source=source,
        game_code=game_code,
    )
    return {
        "status": "success",
        "source": source,
        "gameCode": game_code,
        "trackName": track_name,
        "trackConfig": track_config,
        "acInstallPath": ac_install_path,
        "manifest": manifest.to_dict(),
    }


@router.get("/api/debug/kn5-inventory")
async def get_kn5_inventory():
    if main.source_manager.get_active_source_name() == "assetto_corsa" and not main.source_manager.current_track_name():
        main.ingest_one_active_sample()

    resolver = TrackFileResolver(ac_root=main.source_manager.current_ac_install_path())
    manifest = resolver.build_track_file_manifest(
        main.source_manager.current_track_name() or "",
        main.source_manager.current_track_config(),
        source=main.source_manager.get_active_source_name(),
        game_code=main.source_manager.current_game_code() or "assetto_corsa",
    )
    inventory = build_kn5_inventory_from_manifest(manifest.to_dict())
    return {"status": "success", **inventory.to_dict()}


@router.get("/api/debug/kn5-surface-candidates")
async def get_kn5_surface_candidates(include_pitlane: bool = False):
    if main.source_manager.get_active_source_name() == "assetto_corsa" and not main.source_manager.current_track_name():
        main.ingest_one_active_sample()

    resolver = TrackFileResolver(ac_root=main.source_manager.current_ac_install_path())
    manifest = resolver.build_track_file_manifest(
        main.source_manager.current_track_name() or "",
        main.source_manager.current_track_config(),
        source=main.source_manager.get_active_source_name(),
        game_code=main.source_manager.current_game_code() or "assetto_corsa",
    )
    extraction = build_kn5_surface_extraction_from_manifest(
        manifest.to_dict(),
        include_pitlane=include_pitlane,
    )
    return {"status": "success", **extraction.to_dict()}


@router.get("/api/debug/track-surface-polygon")
async def get_track_surface_polygon():
    if main.source_manager.get_active_source_name() == "assetto_corsa" and not main.source_manager.current_track_name():
        main.ingest_one_active_sample()

    resolver = TrackFileResolver(ac_root=main.source_manager.current_ac_install_path())
    manifest = resolver.build_track_file_manifest(
        main.source_manager.current_track_name() or "",
        main.source_manager.current_track_config(),
        source=main.source_manager.get_active_source_name(),
        game_code=main.source_manager.current_game_code() or "assetto_corsa",
    )
    surface = build_track_surface_polygon_from_manifest(manifest.to_dict())
    return {"status": "success", **surface}


@router.get("/api/debug/track-edges-from-surface")
async def get_track_edges_from_surface():
    if main.source_manager.get_active_source_name() == "assetto_corsa" and not main.source_manager.current_track_name():
        main.ingest_one_active_sample()

    resolver = TrackFileResolver(ac_root=main.source_manager.current_ac_install_path())
    manifest = resolver.build_track_file_manifest(
        main.source_manager.current_track_name() or "",
        main.source_manager.current_track_config(),
        source=main.source_manager.get_active_source_name(),
        game_code=main.source_manager.current_game_code() or "assetto_corsa",
    )
    result = build_track_edges_from_surface_from_manifest(manifest.to_dict())
    return {"status": "success", **result}


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
