"""The optimised racing line, as a target the coach can hold the driver to.

The driver reference model answers "how fast have *you* been through here". This
answers "how fast is this corner", which is a different question and needs a
different source: the LSTM proposes a line, an evolutionary search improves it,
and a quasi-steady-state simulator times it. None of that runs here. All of it
ran offline, and what lands in this file is the arithmetic result -- sixty
numbers and a lap time.

That separation is the point. The packaged backend never imports `ml`, never
loads PyTorch, and never spends thirty milliseconds on inference inside a 57 Hz
frame loop. It reads a small JSON written by `ml.scripts.export_coaching`.

The two models are kept in separate files on purpose. They are rebuilt by
different things on different schedules -- the driver model every time he
records laps, the optimal line only when the search is run again -- and merging
them would mean refitting one silently discards the other.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

SUPPORTED_VERSIONS = {"optimal-line-1"}


def optimal_line_path(runtime_root: Path, track: str) -> Path:
    """Next to the driver model, with the same sanitising, plus a suffix."""
    safe = "".join(
        char if char.isalnum() or char in "._-" else "_" for char in (track or "unknown")
    )
    return Path(runtime_root) / "data" / "reference_models" / f"{safe}.optimal.json"


def find_optimal_line(roots: Iterable[Path], track: str) -> Optional["OptimalLine"]:
    """First line found for this track, searching the roots in order.

    The packaged app has two: a writable runtime root, and the read-only
    resource root the installer laid down. The shipped line lives in the second
    one, but a line regenerated on this machine belongs to the first -- so
    runtime is searched first and wins, the same order the recordings use.
    """
    for root in roots:
        if root is None:
            continue
        line = OptimalLine.load(optimal_line_path(Path(root), track))
        if line is not None:
            return line
    return None


@dataclass
class OptimalLine:
    """Per-microsector time of the optimised line, on the coach's progress axis."""

    version: str
    track: str
    microsectors: int
    lap_seconds: float
    seconds: List[float] = field(default_factory=list)
    min_speed_kmh: List[Optional[float]] = field(default_factory=list)
    entry_speed_kmh: List[Optional[float]] = field(default_factory=list)
    exit_speed_kmh: List[Optional[float]] = field(default_factory=list)
    source: str = ""
    built_at: Optional[str] = None

    def seconds_at(self, index: int) -> Optional[float]:
        if 0 <= index < len(self.seconds):
            value = self.seconds[index]
            return float(value) if value is not None else None
        return None

    def min_speed_at(self, index: int) -> Optional[float]:
        if 0 <= index < len(self.min_speed_kmh):
            value = self.min_speed_kmh[index]
            return float(value) if value is not None else None
        return None

    def to_api(self) -> Dict[str, Any]:
        return {
            "status": "READY",
            "lapSeconds": round(self.lap_seconds, 3),
            "microsectors": self.microsectors,
            "source": self.source,
            "builtAt": self.built_at,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> Optional["OptimalLine"]:
        version = str(payload.get("version", ""))
        if version not in SUPPORTED_VERSIONS:
            logger.warning("Optimal line format %r not supported; ignoring", version)
            return None
        seconds = [float(value) for value in payload.get("seconds", [])]
        microsectors = int(payload.get("microsectors", len(seconds)))
        if not seconds or len(seconds) != microsectors:
            logger.warning(
                "Optimal line has %d splits for %d microsectors; ignoring",
                len(seconds),
                microsectors,
            )
            return None
        # A line that claims a lap time nowhere near the sum of its own splits is
        # a file that was assembled wrong, and holding a driver to it would be
        # worse than holding him to nothing.
        lap_seconds = float(payload.get("lap_seconds") or sum(seconds))
        if abs(lap_seconds - sum(seconds)) > 0.5:
            logger.warning(
                "Optimal line lap time %.3fs disagrees with its splits %.3fs; ignoring",
                lap_seconds,
                sum(seconds),
            )
            return None

        def optional_list(key: str) -> List[Optional[float]]:
            raw = payload.get(key) or []
            return [None if value is None else float(value) for value in raw]

        return cls(
            version=version,
            track=str(payload.get("track", "")),
            microsectors=microsectors,
            lap_seconds=lap_seconds,
            seconds=seconds,
            min_speed_kmh=optional_list("min_speed_kmh"),
            entry_speed_kmh=optional_list("entry_speed_kmh"),
            exit_speed_kmh=optional_list("exit_speed_kmh"),
            source=str(payload.get("source", "")),
            built_at=payload.get("built_at"),
        )

    @classmethod
    def load(cls, path: Path) -> Optional["OptimalLine"]:
        path = Path(path)
        if not path.exists():
            return None
        try:
            return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except Exception as error:  # a bad artefact must not take the app down
            logger.warning("Optimal line unreadable at %s: %s", path, error)
            return None


def attach(model: Any, line: Optional[OptimalLine]) -> Any:
    """Hang the optimal times on a driver model's targets, in place.

    Silently does nothing when there is no line for this track, which is the
    common case: the search has only been run for Interlagos. The coach then
    behaves exactly as it did before -- the driver's own best is still there,
    and it is still the thing that decides when to speak.
    """
    if model is None or line is None or not getattr(model, "targets", None):
        return model
    if line.microsectors != getattr(model, "microsectors", None):
        # Different slicing of the same lap: the numbers would not line up with
        # the asphalt, and a target on the wrong corner is worse than none.
        logger.warning(
            "Optimal line has %d microsectors, driver model has %d; not attaching",
            line.microsectors,
            model.microsectors,
        )
        return model

    for target in model.targets:
        target.optimal_seconds = line.seconds_at(target.index)
        target.optimal_min_speed_kmh = line.min_speed_at(target.index)
    model.optimal_lap_seconds = round(line.lap_seconds, 3)
    model.optimal_source = line.source or None
    return model
