from typing import List, Optional
from .telemetry_models import TelemetrySample
import threading

class TelemetryBuffer:
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self.samples: List[TelemetrySample] = []
        self._lock = threading.Lock()

    def add_sample(self, sample: TelemetrySample):
        with self._lock:
            self.samples.append(sample)
            if len(self.samples) > self.max_size:
                self.samples.pop(0)

    def add_samples(self, samples: List[TelemetrySample]):
        with self._lock:
            self.samples.extend(samples)
            if len(self.samples) > self.max_size:
                self.samples = self.samples[-self.max_size:]

    def get_samples(self) -> List[TelemetrySample]:
        with self._lock:
            return list(self.samples)

    def clear(self):
        with self._lock:
            self.samples = []

    def get_latest_sample(self) -> Optional[TelemetrySample]:
        with self._lock:
            return self.samples[-1] if self.samples else None

    def get_lap_samples(self, lap: Optional[int] = None) -> List[TelemetrySample]:
        with self._lock:
            if lap is None:
                return list(self.samples)
            return [sample for sample in self.samples if sample.lap == lap]
