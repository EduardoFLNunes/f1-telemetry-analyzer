import asyncio
from dataclasses import dataclass
import logging
import os
from typing import Optional

from ..data_quality.udp_reliability import UdpReliabilityMonitor
from .opponents_buffer import OpponentsStateBuffer
from .opponents_receiver import OpponentsTelemetryReceiver


logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class OpponentsRuntimeConfig:
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 8765

    @classmethod
    def from_env(cls) -> "OpponentsRuntimeConfig":
        return cls(
            enabled=_env_bool("AT_UDP_OPPONENTS_ENABLED", True),
            host=os.getenv("AT_UDP_OPPONENTS_HOST", "127.0.0.1").strip() or "127.0.0.1",
            port=int(os.getenv("AT_UDP_OPPONENTS_PORT", "8765")),
        )


class OpponentsRuntime:
    def __init__(
        self,
        buffer: OpponentsStateBuffer,
        host: str = "127.0.0.1",
        port: int = 8765,
        enabled: bool = True,
        receiver: Optional[OpponentsTelemetryReceiver] = None,
        reliability_monitor: Optional[UdpReliabilityMonitor] = None,
    ):
        self.buffer = buffer
        self.enabled = bool(enabled)
        self.receiver = receiver or OpponentsTelemetryReceiver(
            buffer,
            host=host,
            port=port,
            reliability_monitor=reliability_monitor,
        )

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        if not self.enabled:
            logger.info("UDP opponents receiver disabled by AT_UDP_OPPONENTS_ENABLED")
            return
        self.receiver.start(loop=loop)

    def stop(self):
        self.receiver.stop()

    def status(self):
        return {
            **self.receiver.status(),
            "enabled": self.enabled,
        }
