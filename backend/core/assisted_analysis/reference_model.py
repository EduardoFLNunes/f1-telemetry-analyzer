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

Two modes, since ADR 0012:

* ``reference_lap`` (the default): every microsector is measured against one
  real, complete lap -- by default the best valid one. "0.12 s behind your
  reference lap here" is a measured fact.
* ``best_per_microsector`` (the original, off by default): against the best
  ever done in each slice. The sum of those bests -- the "ideal lap" -- is
  optimistic by construction: the best of 150 noisy attempts is lower than what
  the driver can repeat, and stitching slices ignores what one slice cost the
  next. Measured on recorded sessions (tools/measure_reference_optimism.py):
  the second half of a session realised none of the "time on the table" fitted
  on the first half, and each microsector best was matched by 3-5 % of laps.

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

MODE_REFERENCE_LAP = "reference_lap"
MODE_BEST_PER_MICROSECTOR = "best_per_microsector"
MODES = (MODE_REFERENCE_LAP, MODE_BEST_PER_MICROSECTOR)

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

    # What the optimised racing line does through the same slice. Not fitted
    # from anything the driver did -- it comes from `optimal_line.attach`, which
    # reads an artefact the ML pipeline produced offline. Stays None for tracks
    # the search has never been run on, and the coach carries on without it.
    optimal_seconds: Optional[float] = None
    optimal_min_speed_kmh: Optional[float] = None

    # The reference lap through the same slice (ADR 0012): one real, complete
    # lap, not the best of many. Brake and throttle points also in metres of the
    # runtime's own `s`, which is what the coach says out loud.
    reference_seconds: Optional[float] = None
    reference_min_speed_kmh: Optional[float] = None
    reference_brake_point_p: Optional[float] = None
    reference_brake_point_m: Optional[float] = None
    reference_throttle_point_p: Optional[float] = None
    reference_throttle_point_m: Optional[float] = None

    @property
    def gap_best_to_optimal(self) -> Optional[float]:
        """How much the driver's own best still gives away here."""
        if self.optimal_seconds is None:
            return None
        return round(self.best_seconds - self.optimal_seconds, 4)

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

    # Filled by `optimal_line.attach` after loading, when the track has one.
    optimal_lap_seconds: Optional[float] = None
    optimal_source: Optional[str] = None

    # ADR 0012. A model saved before the reference lap existed loads with
    # `reference_lap_id = None`: `has_reference` is then False and the coach
    # stays quiet rather than falling back to the old mode unasked.
    mode: str = MODE_REFERENCE_LAP
    reference_lap_id: Optional[str] = None
    reference_lap_seconds: Optional[float] = None

    # ADR 0013. The official geometry the model was measured on. When set, the
    # coach projects the live position on that same geometry and stays quiet if
    # it cannot load it or finds another one; when absent (a model fitted on the
    # runtime's `p`), the coach keeps the old behaviour.
    geometry_id: Optional[str] = None
    # The quickest valid laps and why each was or was not the reference.
    reference_candidates: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def has_reference(self) -> bool:
        return bool(self.reference_lap_id) and any(t.reference_seconds is not None for t in self.targets)

    def target_seconds(self, target: "MicrosectorTarget") -> Optional[float]:
        """What a split is measured against, in the active mode."""
        if self.mode == MODE_BEST_PER_MICROSECTOR:
            return target.best_seconds
        return target.reference_seconds

    def loss_against_reference(self, splits: Sequence[Optional[float]]) -> List[Optional[float]]:
        """Per-microsector difference to the reference lap (positive = behind it)."""
        losses: List[Optional[float]] = []
        by_index = {target.index: target for target in self.targets}
        for index, split in enumerate(splits):
            target = by_index.get(index)
            if split is None or target is None or target.reference_seconds is None:
                losses.append(None)
                continue
            losses.append(round(split - target.reference_seconds, 4))
        return losses

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

    @property
    def gap_ideal_to_optimal(self) -> Optional[float]:
        """What is left after stitching his best microsectors together.

        `ideal_lap_seconds` is the driver's ceiling under his current line -- the
        best he has done in every slice, added up. The optimal line is a
        different line entirely, so this gap is the part of the lap he cannot
        reach by driving his own way better.
        """
        if self.ideal_lap_seconds is None or self.optimal_lap_seconds is None:
            return None
        return round(self.ideal_lap_seconds - self.optimal_lap_seconds, 3)

    def loss_against_optimal(self, splits: Sequence[Optional[float]]) -> List[Optional[float]]:
        """Per-microsector time the lap gave away against the optimised line."""
        losses: List[Optional[float]] = []
        by_index = {target.index: target for target in self.targets}
        for index, split in enumerate(splits):
            target = by_index.get(index)
            if split is None or target is None or target.optimal_seconds is None:
                losses.append(None)
                continue
            losses.append(round(split - target.optimal_seconds, 4))
        return losses

    # ── persistence ──────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["targets"] = [target.to_dict() for target in self.targets]
        payload["gapBestToIdeal"] = self.gap_best_to_ideal
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "DriverReferenceModel":
        known = set(MicrosectorTarget.__dataclass_fields__)
        targets = [
            MicrosectorTarget(**{k: v for k, v in target.items() if k in known})
            for target in payload.get("targets", [])
        ]
        mode = payload.get("mode", MODE_REFERENCE_LAP)
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
            mode=mode if mode in MODES else MODE_REFERENCE_LAP,
            reference_lap_id=payload.get("reference_lap_id"),
            reference_lap_seconds=payload.get("reference_lap_seconds"),
            geometry_id=payload.get("geometry_id"),
            reference_candidates=list(payload.get("reference_candidates") or []),
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

    The finish line follows the ML convention (pedido 14): the lap is timed from
    `s = 0` to `s = 0`, interpolated. A recorded lap starts a few metres *past*
    the line -- the game resets the lap timer a little after `s = 0`, and the
    lap counter a few frames after that -- and ends a few metres past it again,
    with the line itself crossed in its tail. So the flag is interpolated in the
    tail, and the start is the flag minus one period: the time between two
    passages over the lap's first sample. Measured on five laps: that period is
    the game's lap time to the millisecond.

    The old version extrapolated the start backwards from the first sample
    instead, which put the sum of the slices 26 ms over the store's lap time --
    and the store turned out to be the one that is short (one grid step at the
    line, see docs/coach_aprendizado.md).
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

    crossings = _line_crossings(progress, elapsed, microsectors)
    for index in range(microsectors):
        start, end = crossings[index], crossings[index + 1]
        if start is None or end is None:
            continue
        split = end - start
        if split > 0:
            splits[index] = round(split, 4)
    return splits


def _line_crossings(progress: np.ndarray, elapsed: np.ndarray, microsectors: int) -> List[Optional[float]]:
    """When the lap crossed every boundary, the start line included (one period before the flag).

    Progress is unwrapped where it falls back near zero -- the line crossed in
    the tail -- so the lap runs on one increasing axis from its first sample to
    one lap past it. An end that no sample reaches is extrapolated from the rate
    at that end, but only within a fifth of a microsector: past that the rate is
    a guess and no target is better than a wrong one.
    """
    tolerance = 0.2 / microsectors
    unwrapped = progress.astype(float).copy()
    drops = np.flatnonzero(np.diff(unwrapped) < -0.5)
    if drops.size:
        unwrapped[drops[0] + 1:] += 1.0
        if drops.size > 1:
            # A second wrap is the next lap: stop there.
            cut = drops[1] + 1
            unwrapped, elapsed = unwrapped[:cut], elapsed[:cut]
    unwrapped = np.maximum.accumulate(unwrapped)
    keep = np.r_[True, np.diff(unwrapped) > 0]
    unwrapped, elapsed = unwrapped[keep], elapsed[keep]
    if unwrapped.size < 2:
        return [None] * (microsectors + 1)

    def at(position: float) -> Optional[float]:
        if position < unwrapped[0]:
            return None
        if position <= unwrapped[-1]:
            return float(np.interp(position, unwrapped, elapsed))
        if position - unwrapped[-1] > tolerance:
            return None
        rate = (elapsed[-1] - elapsed[-2]) / (unwrapped[-1] - unwrapped[-2])
        return float(elapsed[-1] + (position - unwrapped[-1]) * rate)

    crossings: List[Optional[float]] = [None] * (microsectors + 1)
    for boundary in range(1, microsectors + 1):
        crossings[boundary] = at(boundary / microsectors)
    first = float(unwrapped[0])
    lap_end = at(1.0 + first)
    if crossings[microsectors] is not None and lap_end is not None and first <= tolerance + 1.0 / microsectors:
        period = lap_end - float(elapsed[0])
        crossings[0] = crossings[microsectors] - period
    return crossings


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


def _has_hole(df: pd.DataFrame, microsectors: int) -> bool:
    """A gap in the recording longer than half a microsector.

    `microsector_splits` interpolates every boundary, including the ones that
    fall inside a hole -- so a lap with 400 m missing still comes out with 60
    splits. Good enough to vote for the best of a slice among many laps; not
    good enough to be *the* reference lap the driver is measured against.
    """
    if df is None or "p" not in df.columns:
        return True
    progress = pd.to_numeric(df["p"], errors="coerce").to_numpy(dtype=float)
    progress = progress[np.isfinite(progress)]
    if progress.size < 2:
        return True
    steps = np.diff(progress)
    steps = steps[steps > -0.5]          # the wrap at the finish line is not a hole
    return bool(steps.size and steps.max() > 0.5 / microsectors)


def _meters_at(df: pd.DataFrame, progress: Optional[float]) -> Optional[float]:
    """The runtime's `s` where the lap was at `progress`."""
    if progress is None or df is None or "s" not in df.columns or "p" not in df.columns:
        return None
    p = pd.to_numeric(df["p"], errors="coerce").to_numpy(dtype=float)
    s = pd.to_numeric(df["s"], errors="coerce").to_numpy(dtype=float)
    good = np.isfinite(p) & np.isfinite(s)
    if not good.any():
        return None
    index = int(np.argmin(np.abs(p[good] - float(progress))))
    return round(float(s[good][index]), 1)


def build_reference_model(
    laps: Sequence[Tuple[str, Optional[float], Optional[int], pd.DataFrame]],
    *,
    track: str = "",
    microsectors: int = DEFAULT_MICROSECTORS,
    built_at: Optional[str] = None,
    mode: str = MODE_REFERENCE_LAP,
    reference_lap_id: Optional[str] = None,
    geometry: Any = None,
) -> DriverReferenceModel:
    """
    Fit the model from `(lap_id, lap_seconds, sample_count, dataframe)` laps.

    Every lap that survives the sanity filter contributes its splits; the model
    keeps the best of each slice and remembers which lap set it.

    The reference lap is the quickest lap that is valid and *complete* -- every
    microsector timed, so its slices add up to its lap time -- or the one named
    by `reference_lap_id`, which then has to be valid and complete too. The
    caller decides which laps are comparable (same track, car and geometry):
    this function sees only the laps it is given.

    With `geometry` (an `official_geometry.OfficialGeometry`, ADR 0013), every
    lap is projected from its world position onto the official grid before it
    is cut: the recorded `p` is ignored, so laps from any cache -- and laps that
    have no `p` at all -- are measured on one ruler, and the microsectors are
    the ML's equal-distance ones.
    """
    if geometry is not None:
        from .official_geometry import project_lap, projection_jumped

        microsectors = geometry.microsectors
        laps = [(lap_id, seconds, count, project_lap(df, geometry)) for lap_id, seconds, count, df in laps]
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")
    best: Dict[int, Tuple[float, str, pd.DataFrame]] = {}
    observed: Dict[int, List[float]] = {}
    rejected: Dict[str, int] = {}
    accepted = 0
    best_lap_id: Optional[str] = None
    best_lap_seconds: Optional[float] = None

    complete: Dict[str, Tuple[float, List[Optional[float]], pd.DataFrame]] = {}
    # Every lap the model accepted, and what kept it from being a reference.
    accepted_status: Dict[str, Tuple[float, str]] = {}

    for lap_id, lap_seconds, sample_count, df in laps:
        usable, reason = lap_is_usable(lap_seconds, sample_count)
        if not usable:
            rejected[reason] = rejected.get(reason, 0) + 1
            continue
        if geometry is not None and projection_jumped(df, geometry.length):
            rejected["projection_jump"] = rejected.get("projection_jump", 0) + 1
            continue

        splits = microsector_splits(df, microsectors)
        covered = sum(1 for split in splits if split is not None)
        if covered < microsectors * MIN_COVERAGE:
            rejected["incomplete_lap"] = rejected.get("incomplete_lap", 0) + 1
            continue
        if covered < microsectors:
            accepted_status[lap_id] = (float(lap_seconds or 0.0), f"incompleta: {microsectors - covered} microsetores sem tempo")
        elif _has_hole(df, microsectors):
            accepted_status[lap_id] = (float(lap_seconds or 0.0), "incompleta: buraco na gravacao maior que meio microsetor")
        else:
            accepted_status[lap_id] = (float(lap_seconds or 0.0), "completa")
            complete[lap_id] = (float(lap_seconds or 0.0), splits, df)

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

    reference_seconds: Optional[float] = None
    requested_reference = reference_lap_id
    if reference_lap_id is not None:
        if reference_lap_id not in complete:
            raise ValueError(
                f"reference lap {reference_lap_id!r} is not a valid, complete lap among the laps given"
            )
    elif complete:
        reference_lap_id = min(complete, key=lambda key: complete[key][0])
    if reference_lap_id is not None:
        reference_seconds, reference_splits, reference_df = complete[reference_lap_id]
        for target in targets:
            split = reference_splits[target.index]
            target.reference_seconds = round(split, 4) if split is not None else None
            summary = _channel_summary(reference_df, target.start_p, target.end_p)
            target.reference_min_speed_kmh = summary.get("min_speed_kmh")
            target.reference_brake_point_p = summary.get("brake_point_p")
            target.reference_brake_point_m = _meters_at(reference_df, summary.get("brake_point_p"))
            target.reference_throttle_point_p = summary.get("throttle_point_p")
            target.reference_throttle_point_m = _meters_at(reference_df, summary.get("throttle_point_p"))

    candidates = []
    for lap_id, (seconds, status) in sorted(accepted_status.items(), key=lambda item: item[1][0])[:5]:
        if lap_id == reference_lap_id:
            why = "escolhida: " + ("indicada por lap_id" if requested_reference else "a mais rapida valida e completa")
        elif status != "completa":
            why = status
        else:
            why = "valida e completa, mas mais lenta que a escolhida"
        candidates.append({"lap_id": lap_id, "lap_seconds": round(seconds, 3), "motivo": why})

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
        mode=mode,
        reference_lap_id=reference_lap_id,
        reference_lap_seconds=round(reference_seconds, 3) if reference_seconds else None,
        geometry_id=getattr(geometry, "geometry_id", None),
        reference_candidates=candidates,
    )


def model_path(runtime_root: Path, track: str) -> Path:
    safe = "".join(char if char.isalnum() or char in "._-" else "_" for char in (track or "unknown"))
    return Path(runtime_root) / "data" / "reference_models" / f"{safe}.json"
