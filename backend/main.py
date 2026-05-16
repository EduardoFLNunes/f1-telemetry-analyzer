"""
F1 Telemetry Analyzer — Backend FastAPI
Integra telemetria do jogador + FastF1 (referência real de F1) + IA de raceline.

PHASE 2 UPDATE (2026-05-10):
- Full async streaming architecture integrated
- WebSocket support for real-time telemetry
- DuckDB + Parquet persistence
- Replay Engine for historical data
- Physics Integrity Validation
"""
from fastapi import FastAPI, File, UploadFile, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
import io
import logging
import asyncio
import time
import random
from pathlib import Path

from core.state import AppState
from core.trackmap    import TrackMapGenerator, AssettoCorsaTrackParser
from core.ac_shared_memory import AssettoCorsaTelemetryReader
from core.raceline_ai import RacelineAI
from core.trajectory  import TrajectoryAI
from core.fastf1_integration import FastF1Integration
from core.telemetry_events import event_bus
from core.streaming import StreamingIngest
from core.streaming_processor import RealTimeProcessor
from core.session_manager import SessionManager
from core.websocket_server import manager as ws_manager
from core.replay_engine import ReplayEngine
from core.spatial import TrackSpline
from core.telemetry_store import telemetry_store

# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifespan context manager
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global streaming_ingest, rt_processor, session_manager
    # Startup
    logger.info("🚀 Starting F1 Telemetry Analyzer (Streaming Ready) ...")
    
    # Auto-initialize Ingest for AC1
    try:
        from pathlib import Path
        track_csv = Path("data/SaoPaulo.csv")
        if not track_csv.exists():
            track_csv = Path("../data/SaoPaulo.csv")
            
        if track_csv.exists():
            df_track = pd.read_csv(track_csv)
            app_state["track_data"] = TrackMapGenerator().generate_from_csv(df_track)
            logger.info(f"✅ Pista padrão carregada: {app_state['track_data']['name']}")
            
            # Initialize streaming autonomously
            track = app_state["track_data"]
            tx = track["centerline"]["x"]
            tz = track["centerline"].get("z", track["centerline"].get("y"))
            spline = TrackSpline(tx, tz)
            
            session_manager = SessionManager(track_length=track["length_meters"])
            rt_processor = RealTimeProcessor(track_spline=spline, reference_lap=app_state.get("f1_reference"), sim_type="AC1")
            streaming_ingest = StreamingIngest()
            
            await streaming_ingest.start(sim_type="AC1")
            logger.info("📡 Autonomous Telemetry Streaming initialized for AC1")
    except Exception as e:
        logger.warning(f"Erro ao inicializar streaming autônomo: {e}")
        
    yield
    # Shutdown
    logger.info("🛑 Shutting down backend and closing database connections...")
    if streaming_ingest: await streaming_ingest.stop()
    telemetry_store.close()

app = FastAPI(
    title="F1 Telemetry Analyzer API",
    version="2.2.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app_state = AppState()
f1_integration = FastF1Integration(cache_dir="data/fastf1_cache")
replay_engine = ReplayEngine()

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Backend is running"}

# ---------------------------------------------------------------------------
# WebSockets
# ---------------------------------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WS Error: {e}")
        ws_manager.disconnect(websocket)

@app.post("/api/test/simulate")
async def start_simulation():
    """Simulates 60Hz telemetry stream for stress testing."""
    async def simulate():
        from core.telemetry_events import event_bus
        for _ in range(3600): # 1 minute at 60Hz
            data = {
                "type": "telemetry",
                "data": {
                    "speed": random.uniform(100, 300),
                    "gear": random.randint(1, 8),
                    "throttle": random.uniform(0, 1),
                    "brake": random.uniform(0, 1)
                }
            }
            await ws_manager.broadcast(data)
            await asyncio.sleep(1/60)
            
    asyncio.create_task(simulate())
    return {"status": "success", "message": "Simulation started"}

# ---------------------------------------------------------------------------
# Streaming & Replay Control
# ---------------------------------------------------------------------------
streaming_ingest: Optional[StreamingIngest] = None
rt_processor: Optional[RealTimeProcessor] = None
session_manager: Optional[SessionManager] = None
ac_reader: Optional[AssettoCorsaTelemetryReader] = None

def on_track_change(track_name):
    """Callback triggered when Assetto Corsa track changes."""
    logger.info(f"🔄 Track change detected in AC: {track_name}")
    # Assume track name is the directory name
    track_dir = Path("data/tracks") / track_name 
    if track_dir.exists():
        parser = AssettoCorsaTrackParser()
        try:
            track_data = parser.parse_track(track_dir)
            app_state["track_data"] = track_data
            logger.info(f"✅ Auto-loaded track: {track_name}")
        except Exception as e:
            logger.error(f"Failed to auto-load track {track_name}: {e}")
    else:
        logger.warning(f"Track directory not found for: {track_name}")

ac_reader = AssettoCorsaTelemetryReader(track_parser_callback=on_track_change)

@app.post("/api/streaming/start")
async def start_streaming(sim_type: str = "F1-25"):
    global streaming_ingest, rt_processor, session_manager, ac_reader
    
    if sim_type == "AC1":
        if ac_reader and not ac_reader.running:
            ac_reader.start()
            logger.info("📡 AC Shared Memory reader started.")

    if app_state["track_data"] is None:
        raise HTTPException(status_code=400, detail="Carregue a pista antes de iniciar o streaming.")
        
    try:
        # Stop existing session components if they exist
        if rt_processor: rt_processor.stop()
        if session_manager: session_manager.stop()
        if streaming_ingest: await streaming_ingest.stop()

        track = app_state["track_data"]
        tx = track["centerline"]["x"]
        tz = track["centerline"].get("z", track["centerline"].get("y"))
        spline = TrackSpline(tx, tz)
        
        session_manager = SessionManager(track_length=track["length_meters"])
        rt_processor = RealTimeProcessor(track_spline=spline, reference_lap=app_state.get("f1_reference"), sim_type=sim_type)
        streaming_ingest = StreamingIngest()
        
        await streaming_ingest.start(sim_type=sim_type)
        return {"status": "success", "message": f"Streaming iniciado para {sim_type}"}
    except Exception as e:
        logger.error(f"Failed to start streaming: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/streaming/stop")
async def stop_streaming():
    global streaming_ingest
    if streaming_ingest:
        await streaming_ingest.stop()
        streaming_ingest = None
        return {"status": "success", "message": "Streaming parado"}
    return {"status": "error", "message": "Nenhum streaming ativo"}

# ---------------------------------------------------------------------------
# Telemetry Data & Persistence
# ---------------------------------------------------------------------------
@app.get("/api/telemetry/laps")
async def get_saved_laps(driver_id: Optional[str] = None):
    try:
        laps_df = telemetry_store.query_laps(driver_id)
        return {"status": "success", "data": laps_df.to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/telemetry/lap/{driver_id}/{lap_number}")
async def get_lap_telemetry(driver_id: str, lap_number: int):
    try:
        df = telemetry_store.load_lap_telemetry(driver_id, lap_number)
        return {"status": "success", "data": df.to_dict(orient="list")}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

from core.telemetry import calculate_map_matching
from core.spatial_registration import registrar

@app.get("/api/telemetry/live")
async def get_live_telemetry(sim_type: str = "AC1"):
    """Returns real-time telemetry with map matching."""
    if sim_type == "AC1":
        if not ac_reader:
            raise HTTPException(status_code=404, detail="AC Telemetry Reader não iniciado.")
        
        raw_data = ac_reader.get_latest_data()
        
        # Transform raw coordinates to Canonical Space
        car_x_canon, car_z_canon = registrar.transform_track(raw_data["x"], raw_data["z"])
        
        # Map matching
        track = app_state.get("track_data")
        if track:
            cx = track["centerline"]["x"]
            cz = track["centerline"]["y"] # assuming 'y' is Z-coord for trackmap
            snapped_x, snapped_z, offset = calculate_map_matching(car_x_canon, car_z_canon, cx, cz)
            
            return {
                "car_x": float(car_x_canon),
                "car_z": float(car_z_canon),
                "snapped_x": float(snapped_x),
                "snapped_z": float(snapped_z),
                "heading": float(raw_data["heading"]),
                "lateral_offset": float(offset)
            }
        else:
            return {
                "car_x": float(car_x_canon),
                "car_z": float(car_z_canon),
                "snapped_x": float(car_x_canon),
                "snapped_z": float(car_z_canon),
                "heading": float(raw_data["heading"]),
                "lateral_offset": 0.0
            }
    
    # Handle other sim types or fallback
    raise HTTPException(status_code=400, detail="Simulador não suportado ou sem streaming.")

from core.schemas import ComparisonResponse
from utils.serialization import sanitize_json
...
@app.get("/api/data/comparison", response_model=ComparisonResponse)
async def get_comparison():
    if not app_state["track_data"]:
        raise HTTPException(status_code=404, detail="Dados não carregados")
    
    return {
        "track": sanitize_json(app_state["track_data"]),
        "player": sanitize_json(app_state["telemetry_data"]),
        "ai": sanitize_json(app_state.get("ai_raceline")),
        "f1_loaded": app_state.get("f1_raw") is not None,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
