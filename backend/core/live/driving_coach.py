"""
The voice the two AI panels were built for and never got.

`CoachingFeed` and `AIEngineerPanel` read `coachingEvents` and `engineerSpeech`
from the store, the store fills them from the socket, the socket forwards
`coaching_event` from the bus, and `main` keeps the last fifty for
`/api/live/coach`. Every link of that chain existed except the first one:
nothing in the backend ever published either topic, so both panels were
permanently empty and the coach endpoint answered INSUFFICIENT_DATA forever.

This is that producer. It measures the lap as it happens against the reference
model fitted from the driver's own laps, and speaks when a microsector costs
real time.

It runs on every frame at ~57 Hz, so it does almost nothing per frame: read the
progress, and only when a microsector boundary is crossed does it look up a
target and compare. Anything heavier here shows up as a hole in the recording --
this backend has already lost 4.6% of a session to a one-second endpoint on the
event loop, and the coach must not become the second one.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, Optional

from ..telemetry_events import COACHING_EVENT, ENGINEER_SPEECH

logger = logging.getLogger(__name__)

# What is worth interrupting the driver for.
#
# A fixed threshold assumes mistakes arrive in lumps. A consistent driver loses
# his lap in slivers instead: the best clean lap in this library is 1.47s off
# its own ideal with no single microsector worse than 0.14s, so a 0.15s bar
# reports nothing at all and the feed stays empty on a lap that had a second and
# a half in it.
#
# So the bar is the driver's own spread through that microsector, which the
# model already measures as the distance between his median and his best there.
# Twice that is him being unusually slow *for him*, which is the thing worth
# hearing. The floor keeps it from firing on rounding in a sector he never
# varies in.
MIN_LOSS_SECONDS = 0.06
LOSS_SPREAD_MULTIPLE = 2.0
# And even above it, not more often than this -- a coach talking every corner is
# a coach nobody listens to.
MIN_SECONDS_BETWEEN_EVENTS = 3.0


def _number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


class LiveDrivingCoach:
    """Turns the reference model into events while the driver is on track."""

    def __init__(
        self,
        event_bus: Any,
        model_provider: Callable[[Optional[str]], Any],
        loop_ref_provider: Callable[[], Any] = lambda: None,
        *,
        min_loss_seconds: float = MIN_LOSS_SECONDS,
        min_gap_seconds: float = MIN_SECONDS_BETWEEN_EVENTS,
    ):
        self.event_bus = event_bus
        self.model_provider = model_provider
        self.loop_ref_provider = loop_ref_provider
        self.min_loss_seconds = min_loss_seconds
        self.min_gap_seconds = min_gap_seconds

        self._track: Optional[str] = None
        self._model: Any = None
        self._lap_number: Optional[int] = None
        self._sector_index: Optional[int] = None
        self._sector_entry_clock: Optional[float] = None
        self._last_progress: Optional[float] = None
        self._last_clock: Optional[float] = None
        self._last_event_at: float = 0.0
        self._lap_loss: float = 0.0
        self._lap_loss_optimal: float = 0.0
        self._lap_worst: Optional[Dict[str, Any]] = None

    # ── the hot path ─────────────────────────────────────────────────────

    def on_frame(self, frame: Dict[str, Any]) -> None:
        if not isinstance(frame, dict):
            return
        progress = _number(frame.get("p") if frame.get("p") is not None else frame.get("lapProgress"))
        clock = _number(frame.get("lap_time"))
        if progress is None or clock is None or not (0.0 <= progress <= 1.0):
            return

        model = self._model_for(frame.get("track") or frame.get("trackName"))
        if model is None or not model.targets:
            return

        lap_number = _number(frame.get("lap_number") or frame.get("lap"))
        index = min(int(progress * model.microsectors), model.microsectors - 1)

        # A new lap, or the first frame we have seen: start counting, say nothing.
        if self._lap_number != lap_number or self._sector_index is None:
            if self._lap_number is not None and lap_number is not None and lap_number != self._lap_number:
                self._speak_lap_summary(frame, model)
            self._lap_number = lap_number
            self._sector_index = index
            self._sector_entry_clock = clock
            self._last_progress = progress
            self._last_clock = clock
            self._lap_loss = 0.0
            self._lap_loss_optimal = 0.0
            self._lap_worst = None
            return

        # Still inside the same slice: nothing to do. This is the branch almost
        # every frame takes.
        if index == self._sector_index:
            self._last_progress = progress
            self._last_clock = clock
            return

        # The lap wrapped; the finish line is handled as a new lap above.
        if progress < (self._last_progress or 0.0) - 0.5:
            self._sector_index = index
            self._sector_entry_clock = clock
            self._last_progress = progress
            self._last_clock = clock
            return

        # The boundary falls between two frames. Taking the clock of the frame
        # after it charges the sector up to one sampling interval it did not
        # take -- 17 ms at 57 Hz, on every one of sixty microsectors, which is a
        # second of loss per lap that the driver never actually lost. The model
        # interpolates its targets, so the measurement has to interpolate too.
        entry = self._sector_entry_clock
        finished = self._sector_index
        crossing = clock
        last_progress, last_clock = self._last_progress, self._last_clock
        if last_progress is not None and last_clock is not None and progress > last_progress:
            line = index / model.microsectors
            t = (line - last_progress) / (progress - last_progress)
            if 0.0 <= t <= 1.0:
                crossing = last_clock + (clock - last_clock) * t

        self._sector_index = index
        self._sector_entry_clock = crossing
        self._last_progress = progress
        self._last_clock = clock
        if entry is None or finished is None:
            return

        split = crossing - entry
        if split <= 0:
            return
        target = model.target_at((finished + 0.5) / model.microsectors)
        if target is None:
            return

        # Against the optimised line this is counted whether or not he beat his
        # own best here: the two targets answer different questions, and a slice
        # where he set a personal best can still be half a second off the line.
        optimal = getattr(target, "optimal_seconds", None)
        if optimal is not None:
            self._lap_loss_optimal += max(0.0, split - float(optimal))

        loss = split - target.best_seconds
        if loss <= 0:
            return
        self._lap_loss += loss
        if self._lap_worst is None or loss > self._lap_worst["lossS"]:
            self._lap_worst = {"index": finished, "lossS": round(loss, 3)}
        if loss < self._threshold_for(target):
            return

        now = time.monotonic()
        if now - self._last_event_at < self.min_gap_seconds:
            return
        self._last_event_at = now
        self._emit_coaching_event(frame, target, split, loss)

    def _threshold_for(self, target: Any) -> float:
        """How far off his own best this driver has to be, here, to hear about it."""
        spread = None
        median = getattr(target, "median_seconds", None)
        best = getattr(target, "best_seconds", None)
        if median is not None and best is not None:
            spread = max(0.0, median - best)
        if not spread:
            return self.min_loss_seconds
        return max(self.min_loss_seconds, spread * LOSS_SPREAD_MULTIPLE)

    # ── what it says ─────────────────────────────────────────────────────

    def _emit_coaching_event(self, frame: Dict[str, Any], target: Any, split: float, loss: float) -> None:
        evidence: Dict[str, Any] = {
            "microsector": target.index,
            "yourSeconds": round(split, 3),
            "bestSeconds": round(target.best_seconds, 3),
            "lossSeconds": round(loss, 3),
            "bestLapId": target.best_lap_id,
        }
        if target.min_speed_kmh is not None:
            evidence["bestMinSpeedKmh"] = target.min_speed_kmh
            speed = _number(frame.get("speedKmh"))
            if speed is not None:
                evidence["yourSpeedKmh"] = round(speed, 1)
        if target.brake_point_p is not None:
            evidence["bestBrakePointP"] = target.brake_point_p
        # Where in the lap this happened, so a replay can say it at the moment
        # the car reaches the corner instead of dumping the lap at once.
        at_lap_time = _number(frame.get("lap_time"))
        if at_lap_time is not None:
            evidence["atLapTimeSeconds"] = round(at_lap_time, 3)

        # The optimised line, when this track has one. It is a second opinion,
        # not a replacement: the driver's own best is what decided that this was
        # worth saying, and it stays the headline. The line says how much of the
        # corner is still there after he matches himself.
        optimal = getattr(target, "optimal_seconds", None)
        if optimal is not None:
            optimal = float(optimal)
            evidence["optimalSeconds"] = round(optimal, 3)
            evidence["optimalLossSeconds"] = round(split - optimal, 3)
            optimal_speed = getattr(target, "optimal_min_speed_kmh", None)
            if optimal_speed is not None:
                evidence["optimalMinSpeedKmh"] = round(float(optimal_speed), 1)

        message = (
            f"Setor {target.index}: {loss:.2f}s atras do seu melhor "
            f"({split:.2f}s contra {target.best_seconds:.2f}s)."
        )
        if target.min_speed_kmh is not None:
            message += f" No melhor, minima de {target.min_speed_kmh:.0f} km/h."
        if optimal is not None:
            message += f" O tracado otimo faz em {optimal:.2f}s."

        self._publish(COACHING_EVENT, {
            "type": "coaching_event",
            "event": message,
            # Half a second lost in one microsector is already a lot; the scale
            # saturates there rather than pretending to measure catastrophe.
            "severity": round(min(1.0, loss / 0.5), 2),
            "evidence": evidence,
            "driver_id": str(frame.get("driver_id") or "player_1"),
            "lap_number": int(_number(frame.get("lap_number") or frame.get("lap")) or 0),
            "s": _number(frame.get("s")) or 0.0,
            "timestamp": time.time(),
            "corner_id": _number(frame.get("corner_id")),
        })

    def _speak_lap_summary(self, frame: Dict[str, Any], model: Any) -> None:
        """The radio call at the line: what the lap cost and where."""
        optimal_lap = getattr(model, "optimal_lap_seconds", None)
        if self._lap_loss <= 0.0 and not (optimal_lap and self._lap_loss_optimal > 0.0):
            return
        worst = self._lap_worst or {}
        message = f"Volta fechada. {self._lap_loss:.2f}s acima do seu ideal"
        if worst:
            message += f", a maior perda no setor {worst['index']} ({worst['lossS']:.2f}s)"
        message += "."
        if model.ideal_lap_seconds and model.best_lap_seconds:
            message += (
                f" Ideal {model.ideal_lap_seconds:.2f}s, seu melhor {model.best_lap_seconds:.2f}s."
            )
        # The second target: how far the lap was from the line the search found,
        # and how much of that his own ideal would still not reach.
        if optimal_lap:
            message += f" Contra o tracado otimo, {self._lap_loss_optimal:.2f}s."
            remaining = getattr(model, "gap_ideal_to_optimal", None)
            if remaining and remaining > 0.0:
                message += f" Mesmo no seu ideal sobrariam {remaining:.2f}s."

        self._publish(ENGINEER_SPEECH, {
            "message": message,
            "priority": "high" if self._lap_loss > 1.0 else "medium",
            "timestamp": time.time(),
            "category": "driver",
        })

    # ── plumbing ─────────────────────────────────────────────────────────

    def _model_for(self, track: Optional[str]) -> Any:
        key = (track or "").strip() or self._track
        if key and key != self._track:
            self._track = key
            self._model = None
        if self._model is None:
            try:
                self._model = self.model_provider(self._track)
            except Exception as error:
                logger.warning("Reference model unavailable for coaching: %s", error)
                self._model = None
        return self._model

    def _publish(self, topic: str, payload: Dict[str, Any]) -> None:
        try:
            self.event_bus.schedule(topic, payload, self.loop_ref_provider())
        except Exception as error:
            logger.warning("Could not publish %s: %s", topic, error)


# ── the same coach, over a lap that is already in the past ───────────────


class _CollectingBus:
    """Keeps what the coach says instead of broadcasting it."""

    def __init__(self) -> None:
        self.events: list[Dict[str, Any]] = []
        self.speech: list[Dict[str, Any]] = []

    def schedule(self, topic: str, payload: Dict[str, Any], loop_ref: Any = None) -> None:
        if topic == COACHING_EVENT:
            self.events.append(payload)
        elif topic == ENGINEER_SPEECH:
            self.speech.append(payload)


def coach_recorded_lap(
    df: Any,
    model: Any,
    *,
    lap_number: int = 0,
    track: str = "",
    driver_id: str = "player_1",
    min_loss_seconds: float = MIN_LOSS_SECONDS,
) -> Dict[str, Any]:
    """
    Run a finished lap through the coach and collect everything it would say.

    The replay plays entirely in the browser -- the samples never pass through
    the backend, so `processed_frame` is never published and the live coach
    cannot see a recorded lap at all. This walks the lap through the same object
    instead, so the replay and the live session are commented by one
    implementation rather than two that drift.

    The wall-clock gate that stops the live coach talking over itself is off
    here: a lap replayed in twenty milliseconds would trip it once and go quiet
    for the rest of the lap. Spacing is the player's job; this returns
    everything, each tagged with the lap time it belongs to.
    """
    if df is None or getattr(df, "empty", True) or model is None or not getattr(model, "targets", None):
        return {"status": "UNAVAILABLE", "events": [], "speech": [], "lossSeconds": 0.0}

    bus = _CollectingBus()
    coach = LiveDrivingCoach(
        bus,
        model_provider=lambda _track: model,
        min_loss_seconds=min_loss_seconds,
        min_gap_seconds=0.0,
    )

    columns = set(df.columns)
    for row in df.itertuples(index=False):
        data = row._asdict()
        clock = data.get("elapsed_s")
        progress = data.get("p")
        if clock is None or progress is None:
            continue
        coach.on_frame({
            "p": float(progress),
            "lap_time": float(clock),
            "lap_number": lap_number,
            "lap": lap_number,
            "s": float(data.get("s") or 0.0),
            "speedKmh": float(data.get("speed_kmh")) if "speed_kmh" in columns and data.get("speed_kmh") == data.get("speed_kmh") else None,
            "driver_id": driver_id,
            "track": track,
        })

    # The radio call lands on the flag, which the walk above never crosses.
    coach._speak_lap_summary({"driver_id": driver_id}, model)   # noqa: SLF001

    for event in bus.events:
        event["lapTimeSeconds"] = event.get("evidence", {}).get("atLapTimeSeconds")
    return {
        "status": "READY",
        "events": bus.events,
        "speech": bus.speech,
        "lossSeconds": round(coach._lap_loss, 3),   # noqa: SLF001
        "worst": coach._lap_worst,                  # noqa: SLF001
    }
