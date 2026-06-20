from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
import re
from datetime import datetime


def safe_track_fragment(track: Optional[str]) -> str:
    value = (track or "unknown_track").strip() or "unknown_track"
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "_", value)
    return cleaned.strip("_") or "unknown_track"


def build_session_id(track: Optional[str], now: Optional[datetime] = None) -> str:
    current = now or datetime.now()
    return f"{current.strftime('%Y-%m-%d_%H-%M-%S')}_{safe_track_fragment(track)}"


@dataclass(frozen=True)
class RecordingConfig:
    output_root: Path
    enabled: bool = True
    auto_start: bool = True
    player_record_hz: float = 20.0
    source_sample_hz: float = 60.0
    opponents_record_hz: float = 20.0
    batch_size: int = 128
    flush_interval_seconds: float = 1.0
    max_queue_size: int = 20000


@dataclass
class RecordingStatus:
    enabled: bool
    recording: bool
    sessionId: Optional[str]
    directory: Optional[str]
    playerSamplesWritten: int
    opponentSnapshotsWritten: int
    eventsWritten: int
    queueSize: int
    droppedFrames: int
    playerSamplesReceived: int
    playerSamplesEnqueued: int
    playerSamplesDownsampled: int
    playerSamplesDropped: int
    playerDownsamplingEnabled: bool
    recorderDownsampleRatio: float
    lastPersistedLapSampleCount: Optional[int]
    lastPersistedLapDurationSeconds: Optional[float]
    lastPersistedLapEffectiveHz: Optional[float]

    def to_api(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "recording": self.recording,
            "sessionId": self.sessionId,
            "directory": self.directory,
            "playerSamplesWritten": self.playerSamplesWritten,
            "opponentSnapshotsWritten": self.opponentSnapshotsWritten,
            "eventsWritten": self.eventsWritten,
            "queueSize": self.queueSize,
            "droppedFrames": self.droppedFrames,
            "playerSamplesReceived": self.playerSamplesReceived,
            "playerSamplesEnqueued": self.playerSamplesEnqueued,
            "playerSamplesDownsampled": self.playerSamplesDownsampled,
            "playerSamplesDropped": self.playerSamplesDropped,
            "playerDownsamplingEnabled": self.playerDownsamplingEnabled,
            "recorderDownsampleRatio": self.recorderDownsampleRatio,
            "lastPersistedLapSampleCount": self.lastPersistedLapSampleCount,
            "lastPersistedLapDurationSeconds": self.lastPersistedLapDurationSeconds,
            "lastPersistedLapEffectiveHz": self.lastPersistedLapEffectiveHz,
        }
