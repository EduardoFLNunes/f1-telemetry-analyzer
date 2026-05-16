"""
Real-Time Session Manager for F1 Telemetry Analyzer
Tracks active drivers, lap lifecycles, and s-progress.
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import time
import logging
import asyncio

from core.telemetry_events import event_bus
from core.telemetry_store import telemetry_store

# Phase 3 Imports
from core.driver_embedding import DriverEmbedding
from core.feature_store import FeatureStore
from core.session_intelligence import SessionIntelligence

logger = logging.getLogger(__name__)

@dataclass
class ActiveLap:
    """State for a driver's current active lap."""
    driver_id: str
    lap_number: int = 0
    start_time: float = field(default_factory=time.time)
    current_s: float = 0.0
    current_L: float = 0.0
    frames: List[Dict[str, Any]] = field(default_factory=list)
    sector: int = 1
    
    def add_frame(self, frame: Dict[str, Any]):
        self.frames.append(frame)
        self.current_s = frame["s"]
        self.current_L = frame["L"]
        # Limit buffer size for memory safety (~10 mins of telemetry at 60Hz)
        if len(self.frames) > 36000:
            self.frames.pop(0)

class SessionManager:
    """
    Manages active drivers and their telemetry states.
    Keyed by driver_id.
    Now supports Phase 3 Intelligence features.
    """
    def __init__(self, track_length: float):
        self.track_length = track_length
        self.active_laps: Dict[str, ActiveLap] = {}
        self.store = telemetry_store
        
        # Phase 3 Components
        self.embedding_gen = DriverEmbedding()
        self.feature_store = FeatureStore()
        self.session_intel = SessionIntelligence()
        
        # Subscribe to normalized frames
        event_bus.subscribe("normalized_frame", self.on_frame_received)

    def stop(self):
        """Cleanup and unsubscribe."""
        event_bus.unsubscribe("normalized_frame", self.on_frame_received)
        logger.info("SessionManager stopped and unsubscribed")

    async def on_frame_received(self, frame: Dict[str, Any]):
        driver_id = frame.get("driver_id", "default")
        sim_lap = frame.get("lap_number", 0)
        
        if driver_id not in self.active_laps:
            logger.info(f"New driver detected: {driver_id}")
            self.active_laps[driver_id] = ActiveLap(driver_id=driver_id, lap_number=sim_lap)
            
        active = self.active_laps[driver_id]
        
        # Check for lap change via simulator lap counter
        if sim_lap > active.lap_number:
            await self._finalize_lap(active)
            active.lap_number = sim_lap
            active.frames = []
            active.sector = 1
            active.start_time = time.time()
        
        # Fallback: spatial wrap-around detection
        prev_s = active.current_s
        now_s = frame["s"]
        if sim_lap == active.lap_number and prev_s > self.track_length * 0.9 and now_s < self.track_length * 0.1:
            await self._finalize_lap(active)
            active.lap_number += 1
            active.frames = []
            active.sector = 1
            active.start_time = time.time()
            
        active.add_frame(frame)
        
        # Sector triggers
        s1_trigger = self.track_length / 3.0
        s2_trigger = 2.0 * self.track_length / 3.0
        
        if active.sector == 1 and now_s >= s1_trigger:
            active.sector = 2
            await event_bus.emit("sector_split", {"driver_id": driver_id, "sector": 1, "lap": active.lap_number, "time": time.time()})
        elif active.sector == 2 and now_s >= s2_trigger:
            active.sector = 3
            await event_bus.emit("sector_split", {"driver_id": driver_id, "sector": 2, "lap": active.lap_number, "time": time.time()})

    async def _finalize_lap(self, active_lap: ActiveLap):
        """Dispatches a completed lap for storage and analytical analysis."""
        if not active_lap.frames:
            return
            
        lap_time = active_lap.frames[-1].get("lap_time", time.time() - active_lap.start_time)
        logger.info(f"Lap Finalized: {active_lap.driver_id} | Lap {active_lap.lap_number} | Time: {lap_time:.3f}s")
        
        # 1. Background persistence and Intelligence analysis
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._run_lap_analytics, active_lap, lap_time)

        await event_bus.emit("lap_finalized", {
            "driver_id": active_lap.driver_id,
            "lap_number": active_lap.lap_number,
            "lap_time": lap_time,
            "frames": active_lap.frames
        })

    def _run_lap_analytics(self, active_lap: ActiveLap, lap_time: float):
        """Blocking analytics executed in thread pool."""
        try:
            # A. Core Persistence
            self.store.save_lap(
                active_lap.driver_id, 
                active_lap.lap_number, 
                lap_time, 
                active_lap.frames
            )
            
            # B. Phase 3: Driver Embedding
            df = pd.DataFrame(active_lap.frames)
            embedding = self.embedding_gen.generate_lap_embedding(df)
            labels = self.embedding_gen.get_style_labels(embedding)
            
            # C. Phase 3: Feature Persistence
            self.feature_store.save_embedding(active_lap.driver_id, active_lap.lap_number, embedding, labels)
            
            # D. Phase 3: Session Intelligence
            self.session_intel.add_lap_summary({
                "driver_id": active_lap.driver_id,
                "lap_number": active_lap.lap_number,
                "lap_time": lap_time,
                "embedding": embedding
            })
            
            logger.info(f"Intelligence analysis complete for {active_lap.driver_id} L{active_lap.lap_number}")
            
        except Exception as e:
            logger.error(f"Error in lap analytics: {e}", exc_info=True)
