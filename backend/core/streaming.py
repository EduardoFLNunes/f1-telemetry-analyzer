"""
Asynchronous Telemetry Ingestion Layer
Captures high-frequency UDP telemetry and dispatches frames to the event bus.
"""
import asyncio
import socket
from typing import Optional, Dict, Any
import logging
import numpy as np

from core.telemetry_events import event_bus
from core.parsers import F125Parser
from core.assetto_adapter import AssettoAdapter

logger = logging.getLogger(__name__)

class TelemetryIngestProtocol(asyncio.DatagramProtocol):
    """
    Async UDP protocol for capturing simulator packets.
    Pushes raw bytes into a queue for background parsing.
    """
    def __init__(self, queue: asyncio.Queue, sim_type: str = "F1-25"):
        self.sim_type = sim_type
        self.queue = queue
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        logger.info(f"Telemetry ingest connected for {self.sim_type}")

    def datagram_received(self, data: bytes, addr):
        # Push to queue to keep ingestion lightning fast
        try:
            self.queue.put_nowait((self.sim_type, data))
        except asyncio.QueueFull:
            logger.warning("Ingestion queue full, dropping packet")

class StreamingIngest:
    """
    Manages the lifecycle of real-time telemetry capture and parsing.
    Supports UDP (F1-25) and Shared Memory (AC1).
    """
    def __init__(self, host: str = "0.0.0.0", port: int = 20777):
        self.host = host
        self.port = port
        self.queue = asyncio.Queue(maxsize=1000)
        self.parser_f125 = F125Parser()
        self.ac_adapter = AssettoAdapter()
        
        self.transport = None
        self.protocol = None
        self._worker_task: Optional[asyncio.Task] = None
        self._ac_poll_task: Optional[asyncio.Task] = None

    async def start(self, sim_type: str = "F1-25"):
        """Starts the capture server and worker."""
        if sim_type == "AC1":
            self._ac_poll_task = asyncio.create_task(self._ac_polling_loop())
            logger.info("Assetto Corsa Shared Memory polling started")
        else:
            loop = asyncio.get_running_loop()
            logger.info(f"Starting async ingest on {self.host}:{self.port} ({sim_type})")
            
            listen = loop.create_datagram_endpoint(
                lambda: TelemetryIngestProtocol(self.queue, sim_type=sim_type),
                local_addr=(self.host, self.port)
            )
            self.transport, self.protocol = await listen
            self._worker_task = asyncio.create_task(self._parser_worker())

    async def stop(self):
        """Stops all capture tasks."""
        if self.transport:
            self.transport.close()
            
        if self._worker_task:
            self._worker_task.cancel()
            
        if self._ac_poll_task:
            self._ac_poll_task.cancel()
            self.ac_adapter.close()
        
        logger.info("Ingest and workers stopped")

    async def _ac_polling_loop(self):
        """High-frequency polling loop for Assetto Corsa Shared Memory with auto-reconnect."""
        interval = 1.0 / 60.0
        was_connected = False
        
        while True:
            try:
                if not self.ac_adapter.is_connected:
                    if was_connected:
                        logger.info("AC Disconnected - Attempting to reconnect...")
                        was_connected = False
                    
                    if not self.ac_adapter.connect():
                        await asyncio.sleep(2.0) # Wait before retry
                        continue
                    else:
                        logger.info("AC Telemetry Active - Connection established")
                        was_connected = True
                
                frame = self.ac_adapter.poll()
                if frame:
                    frame["is_pre_parsed"] = True
                    await event_bus.emit("raw_packet", frame)
                
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"AC Polling Error: {e}")
                self.ac_adapter.is_connected = False
                await asyncio.sleep(1.0)

    async def _parser_worker(self):
        """Processes packets from the queue and emits standardized events."""
        logger.info("Parser worker started")
        while True:
            sim_type, data = await self.queue.get()
            
            try:
                parsed = None
                if sim_type == "F1-25":
                    parsed = self.parser_f125.parse(data)
                
                if parsed:
                    # Dispatch to the event bus
                    # The processor will listen for 'raw_packet' and aggregate them
                    await event_bus.emit("raw_packet", parsed)
            except Exception as e:
                logger.error(f"Worker error parsing {sim_type} packet: {e}")
            finally:
                self.queue.task_done()
