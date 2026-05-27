import asyncio
from typing import Optional

from .opponents_buffer import OpponentsStateBuffer
from .opponents_receiver import OpponentsTelemetryReceiver


class OpponentsRuntime:
    def __init__(
        self,
        buffer: OpponentsStateBuffer,
        host: str = "127.0.0.1",
        port: int = 8765,
        receiver: Optional[OpponentsTelemetryReceiver] = None,
    ):
        self.buffer = buffer
        self.receiver = receiver or OpponentsTelemetryReceiver(buffer, host=host, port=port)

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        self.receiver.start(loop=loop)

    def stop(self):
        self.receiver.stop()
