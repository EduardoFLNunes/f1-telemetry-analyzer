"""
Replay Engine for F1 Telemetry Analyzer
Streams historical telemetry laps through the real-time pipeline for analysis.
"""
import asyncio
import pandas as pd
import time
import logging
from typing import Optional

from core.telemetry_events import event_bus
from core.telemetry_store import telemetry_store

logger = logging.getLogger(__name__)

class ReplayEngine:
    """
    Simulates a live telemetry stream using historical data.
    Useful for testing, ML training, and post-session analysis.
    """
    def __init__(self, playback_rate: float = 1.0):
        self.playback_rate = playback_rate
        self.store = telemetry_store
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start_replay(self, driver_id: str, lap_number: int, loop: bool = False):
        """Starts streaming a specific lap."""
        try:
            df = self.store.load_lap_telemetry(driver_id, lap_number)
            logger.info(f"Starting replay for {driver_id} L{lap_number} ({len(df)} frames)")
            
            self._running = True
            self._task = asyncio.create_task(self._replay_loop(df, loop))
        except Exception as e:
            logger.error(f"Failed to start replay: {e}")

    async def stop(self):
        """Stops the replay."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Replay stopped")

    async def _replay_loop(self, df: pd.DataFrame, loop: bool):
        """Main loop that emits frames at the recorded frequency."""
        while self._running:
            # Calculate time between frames
            # Assuming 60Hz if timestamp is missing, else use timestamp delta
            timestamps = df["timestamp"].values if "timestamp" in df.columns else None
            
            for i in range(len(df)):
                if not self._running: break
                
                frame = df.iloc[i].to_dict()
                # Re-emit as processed_frame to trigger UI and validation
                await event_bus.emit("processed_frame", frame)
                await event_bus.emit("normalized_frame", frame)
                
                # Sleep to simulate real-time
                if timestamps is not None and i < len(df) - 1:
                    dt = (timestamps[i+1] - timestamps[i]) / self.playback_rate
                    await asyncio.sleep(max(dt, 0.001))
                else:
                    await asyncio.sleep(1.0 / (60.0 * self.playback_rate))
            
            if not loop:
                break
            logger.info("Replay looping...")
            
        self._running = False
        logger.info("Replay finished")
