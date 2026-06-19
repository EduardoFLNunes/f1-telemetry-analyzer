from collections import deque
import threading
from typing import Deque, Iterable, List, Optional

from .telemetry_models import TelemetrySample

class TelemetryBuffer:
    def __init__(self, max_size: int = 10000):
        self.max_size = max(int(max_size), 1)
        self.samples: Deque[TelemetrySample] = deque(maxlen=self.max_size)
        self._lock = threading.Lock()

    def add_sample(self, sample: TelemetrySample):
        with self._lock:
            self.samples.append(sample)

    def add_samples(self, samples: Iterable[TelemetrySample]):
        with self._lock:
            self.samples.extend(samples)

    def get_samples(self) -> List[TelemetrySample]:
        with self._lock:
            return list(self.samples)

    def clear(self):
        with self._lock:
            self.samples.clear()

    def get_latest_sample(self) -> Optional[TelemetrySample]:
        with self._lock:
            return self.samples[-1] if self.samples else None

    def get_lap_samples(self, lap: Optional[int] = None) -> List[TelemetrySample]:
        with self._lock:
            if lap is None:
                return list(self.samples)
            return [sample for sample in self.samples if sample.lap == lap]
