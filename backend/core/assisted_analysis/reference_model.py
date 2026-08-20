"""
The driver's own reference, fitted from every lap he has driven.

The analysis engine used to measure a lap against whichever lap came before it.
That is adjacency, not quality: lap 349 (85.740s) was scored against lap 348
(85.845s), a slower lap, and the whole opportunity for the lap came out as
eleven milliseconds. The classifier was right about *what* the driver did and
the number beside it meant nothing.

This is what it is measured against instead. The lap is cut into microsectors,
every usable lap in the library is timed through each of them, and the model
keeps the quickest the driver has ever been in each -- plus how he did it, so
the engine can say more than "you were slow here".

Two properties matter, and both come from the data rather than from a rule:

* The target is *achieved*, not theoretical. Every microsector time in here is
  one the driver has actually driven, so "you can gain 0.4s in T4" means "you
  have already done T4 0.4s quicker than this".
* The ideal lap is the sum of those bests. It is faster than his best lap and
  he has never driven it end to end; that difference is the honest headline of
  how much is on the table.

Laps get in only if their sampling holds up. A lap of 937 samples over 74
seconds is 13 Hz of a 57 Hz signal, and it was ranking as the driver's personal
best -- a corrupt recording is not a lap record.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MODEL_VERSION = "driver_reference_model.v1"

# 60 microsectors puts a boundary every ~72 m at Interlagos: short enough that a
# single corner does not hide inside one, long enough that the crossing time is
# not dominated by the sampling interval.
DEFAULT_MICROSECTORS = 60

# What a lap has to look like to be allowed to teach the model.
MIN_SAMPLE_HZ = 40.0
MAX_SAMPLE_HZ = 70.0
MIN_LAP_SECONDS = 40.0
MAX_LAP_SECONDS = 400.0
MIN_COVERAGE = 0.90          # fraction of microsectors the lap actually visits


@dataclass
class MicrosectorTarget:
    """The quickest the driver has been through one slice of the lap."""

    index: int
    start_p: float
    end_p: float
    best_seconds: float
    best_lap_id: str
    median_seconds: float
    sample_count: int
    entry_speed_kmh: Optional[float] = None
    min_speed_kmh: Optional[float] = None
    exit_speed_kmh: Optional[float] = None
    brake_point_p: Optional[float] = None
    throttle_point_p: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DriverReferenceModel:
    version: str
    track: str
    microsectors: int
    lap_count: int
    rejected_count: int
    best_lap_id: Optional[str]
    best_lap_seconds: Optional[float]
    ideal_lap_seconds: Optional[float]
    targets: List[MicrosectorTarget] = field(default_factory=list)
    rejected_reasons: Dict[str, int] = field(default_factory=dict)
    built_at: Optional[str] = None

    # ── what the analysis asks it ────────────────────────────────────────

    def target_at(self, progress: float) -> Optional[MicrosectorTarget]:
        """The target covering a point of the lap, 0 to 1."""
        if not self.targets:
            return None
        index = min(int(max(0.0, min(1.0, progress)) * self.microsectors), self.microsectors - 1)
        for target in self.targets:
            if target.index == index:
                return target
        return None

    def loss_against_ideal(self, splits: Sequence[Optional[float]]) -> List[Optional[float]]:
        """Per-microsector time the lap gave away against the driver's best."""
        losses: List[Optional[float]] = []
        by_index = {target.index: target for target in self.targets}
        for index, split in enumerate(splits):
            target = by_index.get(index)
            if split is None or target is None:
                losses.append(None)
                continue
            losses.append(round(split - target.best_seconds, 4))
        return losses

    @property
    def gap_best_to_ideal(self) -> Optional[float]:
        if self.best_lap_seconds is None or self.ideal_lap_seconds is None:
            return None
        return round(self.best_lap_seconds - self.ideal_lap_seconds, 3)

    # ── persistence ──────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["targets"] = [target.to_dict() for target in self.targets]
        payload["gapBestToIdeal"] = self.gap_best_to_ideal
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "DriverReferenceModel":
        targets = [MicrosectorTarget(**target) for target in payload.get("targets", [])]
        return cls(
            version=payload.get("version", MODEL_VERSION),
            track=payload.get("track", ""),
            microsectors=int(payload.get("microsectors", DEFAULT_MICROSECTORS)),
            lap_count=int(payload.get("lap_count", 0)),
            rejected_count=int(payload.get("rejected_count", 0)),
            best_lap_id=payload.get("best_lap_id"),
            best_lap_seconds=payload.get("best_lap_seconds"),
            ideal_lap_seconds=payload.get("ideal_lap_seconds"),
            targets=targets,
            rejected_reasons=payload.get("rejected_reasons", {}),
            built_at=payload.get("built_at"),
        )

    def save(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> Optional["DriverReferenceModel"]:
        path = Path(path)
        if not path.exists():
            return None
        try:
            return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except Exception as error:  # a corrupt model must not take the app down
            logger.warning("Driver reference model unreadable at %s: %s", path, error)
            return None


# ── fitting ──────────────────────────────────────────────────────────────


def lap_is_usable(lap_seconds: Optional[float], sample_count: Optional[int]) -> Tuple[bool, str]:
    """Whether a lap is solid enough to teach the model, and why not."""
    if lap_seconds is None or not math.isfinite(lap_seconds):
        return False, "no_lap_time"
    if not (MIN_LAP_SECONDS <= lap_seconds <= MAX_LAP_SECONDS):
        return False, "implausible_duration"
    if not sample_count:
        return False, "no_samples"
    hz = sample_count / lap_seconds
    if hz < MIN_SAMPLE_HZ:
        return False, "sampling_too_sparse"
    if hz > MAX_SAMPLE_HZ:
        return False, "sampling_too_dense"
    return True, ""


def microsector_splits(df: pd.DataFrame, microsectors: int = DEFAULT_MICROSECTORS) -> List[Optional[float]]:
    """
    Time through each slice of the lap, interpolated at the boundaries.

    Taking the first sample past a boundary instead would fold the sampling
    interval into the split, which at 57 Hz is up to 18 ms per boundary -- more
    than the differences this model exists to measure.
    """
    splits: List[Optional[float]] = [None] * microsectors
    if df is None or df.empty or "p" not in df.columns or "elapsed_s" not in df.columns:
        return splits

    progress = pd.to_numeric(df["p"], errors="coerce").to_numpy(dtype=float)
    elapsed = pd.to_numeric(df["elapsed_s"], errors="coerce").to_numpy(dtype=float)
    good = np.isfinite(progress) & np.isfinite(elapsed)
    progress, elapsed = progress[good], elapsed[good]
    if progress.size < microsectors:
        return splits

    # Crossing time for every boundary, including the flag at 1.0.
    #
    # The two ends are not observed. A recorded lap does not start exactly on
    # the line -- its first sample lands somewhere inside the first microsector
    # -- and it does not end exactly on it either. Taking the first sample's
    # clock as the crossing therefore makes the first sector short by however
    # late the recording began, which is not a lap record, it is a recording
    # offset: sector 0 came out with eight times the spread of any other sector
    # and its target was set by whichever lap happened to start latest. The last
    # sector had the mirror problem and simply never got a target at all, which
    # left the ideal lap missing a slice and the gap to it overstated.
    #
    # So both ends are extrapolated from the rate at the ends, and only when the
    # gap is small enough for that rate to mean anything.
    crossings: List[Optional[float]] = [None] * (microsectors + 1)
    crossings[0] = _edge_crossing(progress, elapsed, at=0.0, microsectors=microsectors)
    boundary = 1
    for index in range(1, progress.size):
        while boundary <= microsectors and progress[index] >= boundary / microsectors:
            previous_p, current_p = progress[index - 1], progress[index]
            at = elapsed[index]
            if current_p > previous_p:
                t = ((boundary / microsectors) - previous_p) / (current_p - previous_p)
                if 0.0 <= t <= 1.0:
                    at = elapsed[index - 1] + (elapsed[index] - elapsed[index - 1]) * t
            crossings[boundary] = float(at)
            boundary += 1
        if boundary > microsectors:
            break

    # The flag. The walk above can never reach it: a recorded lap ends a sample
    # or two past the line, so its progress has already wrapped to nearly zero
    # and `progress >= 1.0` is never true. Left like that the last microsector
    # never closes, and the ideal lap is the sum of 59 slices out of 60.
    if crossings[microsectors] is None:
        crossings[microsectors] = _edge_crossing(progress, elapsed, at=1.0, microsectors=microsectors)

    for index in range(microsectors):
        start, end = crossings[index], crossings[index + 1]
        if start is None or end is None:
            continue
        split = end - start
        if split > 0:
            splits[index] = round(split, 4)
    return splits


def _edge_crossing(progress, elapsed, *, at: float, microsectors: int) -> Optional[float]:
    """
    When the lap crossed `at` (0.0 or 1.0), which no sample sits exactly on.

    Extrapolated from the rate at that end of the lap, and only when the sample
    is within a fifth of a microsector of the line -- past that the rate is a
    guess and no target is better than a wrong one.
    """
    tolerance = 0.2 / microsectors
    if at <= 0.0:
        if progress.size < 2 or progress[0] > tolerance:
            return None
        span = progress[1] - progress[0]
        if span <= 0:
            return float(elapsed[0])
        rate = (elapsed[1] - elapsed[0]) / span
        return float(elapsed[0] - progress[0] * rate)

    if progress.size < 2:
        return None

    # A recorded lap usually ends *past* the line, with anything from one to a
    # dozen samples already into the next lap and their progress back near zero.
    # Read literally that is a lap that stopped at the start, and the final
    # microsector never closes -- which is why the ideal lap was the sum of 59
    # slices out of 60. So find where progress actually fell off the cliff and
    # interpolate the crossing there, wherever in the tail it happened.
    for index in range(progress.size - 1, max(0, progress.size - 60), -1):
        before, after = float(progress[index - 1]), float(progress[index])
        if after >= before - 0.5:
            continue
        span = (after + 1.0) - before
        if span <= 0:
            return float(elapsed[index])
        t = (1.0 - before) / span
        return float(elapsed[index - 1] + (elapsed[index] - elapsed[index - 1]) * t)

    # No wrap in the tail: the lap simply stops, and only counts if it stopped
    # on the line.
    last, previous = float(progress[-1]), float(progress[-2])
    if last < 1.0 - tolerance:
        return None
    span = last - previous
    if span <= 0:
        return float(elapsed[-1])
    rate = (elapsed[-1] - elapsed[-2]) / span
    return float(elapsed[-1] + (1.0 - last) * rate)


def _channel_summary(df: pd.DataFrame, start_p: float, end_p: float) -> Dict[str, Optional[float]]:
    """How the driver drove one slice: speeds, and where he braked and picked up."""
    if df is None or df.empty or "p" not in df.columns:
        return {}
    progress = pd.to_numeric(df["p"], errors="coerce")
    window = df[(progress >= start_p) & (progress < end_p)]
    if window.empty:
        return {}

    def channel(name: str) -> Optional[pd.Series]:
        if name not in window.columns:
            return None
        series = pd.to_numeric(window[name], errors="coerce").dropna()
        return series if not series.empty else None

    summary: Dict[str, Optional[float]] = {}
    speed = channel("speed_kmh")
    if speed is not None:
        summary["entry_speed_kmh"] = round(float(speed.iloc[0]), 2)
        summary["min_speed_kmh"] = round(float(speed.min()), 2)
        summary["exit_speed_kmh"] = round(float(speed.iloc[-1]), 2)

    window_p = pd.to_numeric(window["p"], errors="coerce")
    brake = channel("brake")
    if brake is not None:
        pressed = window_p[brake > 0.08]
        if not pressed.empty:
            summary["brake_point_p"] = round(float(pressed.iloc[0]), 5)
    throttle = channel("throttle")
    if throttle is not None:
        opened = window_p[throttle > 0.20]
        if not opened.empty:
            summary["throttle_point_p"] = round(float(opened.iloc[-1]), 5)
    return summary


def build_reference_model(
    laps: Sequence[Tuple[str, Optional[float], Optional[int], pd.DataFrame]],
    *,
    track: str = "",
    microsectors: int = DEFAULT_MICROSECTORS,
    built_at: Optional[str] = None,
) -> DriverReferenceModel:
    """
    Fit the model from `(lap_id, lap_seconds, sample_count, dataframe)` laps.

    Every lap that survives the sanity filter contributes its splits; the model
    keeps the best of each slice and remembers which lap set it.
    """
    best: Dict[int, Tuple[float, str, pd.DataFrame]] = {}
    observed: Dict[int, List[float]] = {}
    rejected: Dict[str, int] = {}
    accepted = 0
    best_lap_id: Optional[str] = None
    best_lap_seconds: Optional[float] = None

    for lap_id, lap_seconds, sample_count, df in laps:
        usable, reason = lap_is_usable(lap_seconds, sample_count)
        if not usable:
            rejected[reason] = rejected.get(reason, 0) + 1
            continue

        splits = microsector_splits(df, microsectors)
        covered = sum(1 for split in splits if split is not None)
        if covered < microsectors * MIN_COVERAGE:
            rejected["incomplete_lap"] = rejected.get("incomplete_lap", 0) + 1
            continue

        accepted += 1
        if best_lap_seconds is None or (lap_seconds or 0) < best_lap_seconds:
            best_lap_seconds, best_lap_id = float(lap_seconds or 0.0), lap_id

        for index, split in enumerate(splits):
            if split is None:
                continue
            observed.setdefault(index, []).append(split)
            if index not in best or split < best[index][0]:
                best[index] = (split, lap_id, df)

    targets: List[MicrosectorTarget] = []
    for index in sorted(best):
        split, lap_id, df = best[index]
        start_p, end_p = index / microsectors, (index + 1) / microsectors
        seen = observed.get(index, [])
        target = MicrosectorTarget(
            index=index,
            start_p=round(start_p, 5),
            end_p=round(end_p, 5),
            best_seconds=round(split, 4),
            best_lap_id=lap_id,
            median_seconds=round(float(np.median(seen)), 4) if seen else round(split, 4),
            sample_count=len(seen),
            **_channel_summary(df, start_p, end_p),  # type: ignore[arg-type]
        )
        targets.append(target)

    ideal = round(sum(target.best_seconds for target in targets), 3) if targets else None
    return DriverReferenceModel(
        version=MODEL_VERSION,
        track=track,
        microsectors=microsectors,
        lap_count=accepted,
        rejected_count=sum(rejected.values()),
        best_lap_id=best_lap_id,
        best_lap_seconds=round(best_lap_seconds, 3) if best_lap_seconds else None,
        ideal_lap_seconds=ideal,
        targets=targets,
        rejected_reasons=rejected,
        built_at=built_at,
    )


def model_path(runtime_root: Path, track: str) -> Path:
    safe = "".join(char if char.isalnum() or char in "._-" else "_" for char in (track or "unknown"))
    return Path(runtime_root) / "data" / "reference_models" / f"{safe}.json"
