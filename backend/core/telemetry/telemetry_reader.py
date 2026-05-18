from abc import ABC, abstractmethod
from typing import Iterator
from .telemetry_models import TelemetrySample

class TelemetryReader(ABC):
    @abstractmethod
    def read_samples(self) -> Iterator[TelemetrySample]:
        pass

    @abstractmethod
    def stop(self):
        pass
