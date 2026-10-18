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

Since ADR 0012 the default is the *reference lap*: every microsector is compared
with one real, complete lap of the driver's, and what the coach says is a
measured difference ("0.12 s behind your reference lap here"), never a promised
gain or an "ideal lap". The old comparison -- the best ever done in each slice --
is still here as `best_per_microsector`, off unless the model asks for it.

Since ADR 0016 (the learning phase) the reference is either the AI's lap
(`volta_ia`, the default) or the driver's best (`minha_melhor`), and every
phrase names it: "0.60s atras da volta da IA neste trecho". Braking is said
relative to the reference ("a IA freia 12 m depois de voce"), at most three
phrases a lap -- the first that clear the bar -- and the lap closes with the
three slices furthest from the reference.

Since pedido 15 the coach speaks only in three *focus* slices, chosen before
each lap: the microsectors with the largest median difference to the active
reference over the session's last five valid laps -- or, until the session has
five, over the driver's laps in the model. One phrase per focus slice, so three
a lap at most, and a short line in the feed when the focus changes. ADR 0016
asked for the slices with the largest difference; the first slices to clear the
bar were mostly the opening corner.

Since ADR 0013 a model carries the `geometry_id` of the official geometry it was
measured on. The coach then works out where the car is from its world position,
projected on that same geometry (`official_geometry.CoachProjector`), instead of
the runtime's `p`: same ruler, same 60 microsectors as the analysis. If the
geometry file is missing, or is another geometry, the coach says nothing and
logs it once. A model without `geometry_id` keeps the old `p` path.

It runs on every frame at ~57 Hz, so it does almost nothing per frame: read the
progress, and only when a microsector boundary is crossed does it look up a
target and compare. Anything heavier here shows up as a hole in the recording --
this backend has already lost 4.6% of a session to a one-second endpoint on the
event loop, and the coach must not become the second one.
"""

from __future__ import annotations

import logging
import statistics
import time
from collections import deque
from typing import Any, Callable, Dict, Optional, Tuple

from ..telemetry.channels import ai_controlled
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
# On the official geometry the lap turns at `s = 0`: a wrap from the last 5 % of
# the lap into the first 5 % is the finish line; any other wrap, or a jump of
# more than 5 % of the lap between two frames, is the car being moved (pits
# from the menu, a reset), and the count starts again without a word.
LINE_WINDOW = 0.05
JUMP_PROGRESS = 0.05
# ADR 0016: against the AI the gap shows up in nearly every slice, so the coach
# speaks at most this often a lap -- the first slices that clear the bar -- and
# sums up the worst ones at the line.
MAX_PHRASES_PER_LAP = 3
# Pedido 15: the focus. The slices with the largest median difference to the
# reference, over the session's last laps that count -- started at the line,
# every slice compared, no AI at the wheel.
FOCUS_SECTORS = 3
FOCUS_LAPS = 5
FOCUS_EVENT = "coaching_focus"
SUMMARY_SECTORS = 3
SUMMARY_MIN_LOSS = 0.005
# A braking point of the lap is compared with the reference's only within this.
BRAKE_MATCH_M = 60.0
BRAKE_ONSET = 0.15
# A slice is not compared when the car stopped in it, or went through the pit
# lane (far off the line and slow, the rule `ml` uses to spot a pit lap):
# measured on 2026-10-04, starting from the box gave "52.84s behind ... yours
# 0 km/h".
STOPPED_KMH = 5.0
PIT_LATERAL_M = 10.0
PIT_SPEED_KMH = 90.0


def _legacy(model: Any) -> bool:
    """The model asked for the old comparison against the best of each slice."""
    return getattr(model, "mode", None) == "best_per_microsector"


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
        geometry_provider: Callable[[Optional[str]], Any] = lambda track: None,
        *,
        min_loss_seconds: float = MIN_LOSS_SECONDS,
        min_gap_seconds: float = MIN_SECONDS_BETWEEN_EVENTS,
    ):
        self.event_bus = event_bus
        self.model_provider = model_provider
        self.loop_ref_provider = loop_ref_provider
        self.geometry_provider = geometry_provider
        self._projector: Any = None
        self._projector_geometry_id: Optional[str] = None
        self._warned_geometry: Optional[str] = None
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
        self._warned_missing_reference = False
        self._last_lap_clock: Optional[float] = None
        self._last_clock_s: Optional[float] = None
        self._clock_offset = 0.0
        # What the lap has done so far (ADR 0016): phrases said, loss per slice,
        # where it started braking, and the lowest speed in the current slice.
        self._lap_phrases = 0
        self._lap_losses: Dict[int, float] = {}
        self._lap_onsets: list = []
        self._last_brake: Optional[float] = None
        self._sector_min_speed: Optional[float] = None
        self._closing_min_speed: Optional[float] = None
        self._last_lateral: Optional[float] = None
        self._sector_max_lateral: Optional[float] = None
        self._closing_max_lateral: Optional[float] = None
        # The slice the count started in is partial: never compared.
        self._partial_sector: Optional[int] = None
        # Pedido 15: what this lap measured (every slice, either sign), whether
        # it counts for the focus, and the focus itself.
        self._lap_diffs: Dict[int, float] = {}
        self._lap_started_at_line = False
        self._lap_had_ai = False
        self._spoken_sectors: set = set()
        self._session_laps: deque = deque(maxlen=FOCUS_LAPS)
        self._focus: Optional[Tuple[int, ...]] = None
        self._focus_source: Optional[str] = None
        self._focus_key: Optional[tuple] = None
        # Pedido 31 (o radio): o que o coach ja sabe, guardado para quem so le.
        # Nao muda nenhuma regra: o horario da linha em que a volta comecou e o
        # periodo da ultima volta completa (de s = 0 a s = 0, como o store v2).
        self._lap_line_clock: Optional[float] = None
        self._volta_do_jogo: Optional[float] = None
        self.ultima_volta: Optional[Dict[str, Any]] = None

    # ── the hot path ─────────────────────────────────────────────────────

    def on_frame(self, frame: Dict[str, Any]) -> None:
        if not isinstance(frame, dict):
            return
        lap_clock = _number(frame.get("lap_time"))
        if lap_clock is None:
            return

        model = self._model_for(frame.get("track") or frame.get("trackName"))
        if model is None or not model.targets:
            return
        if not self._usable(model):
            return
        on_geometry = bool(getattr(model, "geometry_id", None))
        if on_geometry:
            # The game's lap timer is the physics clock; the recorder's wall-clock
            # `timestamp` stutters (measured: +357 ms on one sample, +2 ms on the
            # next, while the car moved 21 m). It sizes the projection's hard
            # continuity, and it times the slices.
            dt = (
                lap_clock - self._last_lap_clock
                if self._last_lap_clock is not None and lap_clock >= self._last_lap_clock else None
            )
            progress = self._progress(frame, model, dt)
            if progress is None or not (0.0 <= progress <= 1.0):
                return
            # The lap turns at `s = 0`, a few metres before the game resets its
            # timer, so the clock has to run through the line (pedido 14).
            clock = self._physics_clock(frame, lap_clock, progress)
        else:
            clock = lap_clock
            progress = self._progress(frame, model)
            if progress is None or not (0.0 <= progress <= 1.0):
                return

        lap_number = _number(frame.get("lap_number") or frame.get("lap"))
        self._volta_do_jogo = lap_number  # pedido 31: so para quem le a posicao
        index = min(int(progress * model.microsectors), model.microsectors - 1)
        if not _legacy(model):
            if ai_controlled(frame) is True:
                self._lap_had_ai = True
            key = (id(model), getattr(model, "reference_kind", None), getattr(model, "reference_lap_id", None))
            if self._focus_key != key:
                self._focus_key = key
                self._session_laps.clear()
                self._update_focus(frame, model)
        position_m = self._position_m(frame, progress)
        brake = _number(frame.get("brake"))
        if brake is not None and position_m is not None:
            if self._last_brake is not None and self._last_brake < BRAKE_ONSET <= brake:
                self._lap_onsets.append(position_m)
            self._last_brake = brake
        speed_now = _number(frame.get("speedKmh"))
        # The lowest speed of the slice being closed excludes this frame, which
        # already lies in the next one.
        self._closing_min_speed = self._sector_min_speed
        self._closing_max_lateral = self._sector_max_lateral
        lateral_now = abs(self._last_lateral) if on_geometry and self._last_lateral is not None else None
        if self._sector_index is not None and index != self._sector_index:
            self._sector_min_speed = speed_now
            self._sector_max_lateral = lateral_now
        else:
            if speed_now is not None:
                self._sector_min_speed = speed_now if self._sector_min_speed is None else min(self._sector_min_speed, speed_now)
            if lateral_now is not None:
                self._sector_max_lateral = lateral_now if self._sector_max_lateral is None else max(self._sector_max_lateral, lateral_now)

        if on_geometry:
            if self._sector_index is None or self._last_progress is None:
                self._start_lap(lap_number, index, clock, progress)
                return
            last_progress = self._last_progress
            if last_progress - progress > 0.5:
                if last_progress >= 1.0 - LINE_WINDOW and progress <= LINE_WINDOW:
                    # The finish line, between two frames: interpolated, like any
                    # other boundary. It closes the last slice and opens the next lap.
                    t = (1.0 - last_progress) / ((progress + 1.0) - last_progress)
                    crossing = self._last_clock + (clock - self._last_clock) * t
                    self._close_sector(frame, model, self._sector_index, self._sector_entry_clock, crossing)
                    self._end_lap(frame, model)
                    if self._lap_started_at_line and self._lap_line_clock is not None:
                        # O s = 0 fica alguns metros antes da linha do jogo: no quadro da passagem,
                        # o jogo ainda conta a volta que acabou.
                        self.ultima_volta = {"volta": lap_number, "tempoS": crossing - self._lap_line_clock,
                                             "teveIA": self._lap_had_ai, "momento": time.time()}
                    self._start_lap(lap_number, 0, crossing, 0.0, at_line=True)
                    self._last_progress, self._last_clock = progress, clock
                    if index == 0:
                        return
                    # Already past the first boundary in the same frame: fall
                    # through and close slice 0 too.
                    last_progress = 0.0
                else:
                    # Not the line: the car was moved (pits from the menu, a reset).
                    self._start_lap(lap_number, index, clock, progress)
                    return
            elif abs(progress - last_progress) > JUMP_PROGRESS:
                self._start_lap(lap_number, index, clock, progress)
                return
        # A new lap, or the first frame we have seen: start counting, say nothing.
        elif self._lap_number != lap_number or self._sector_index is None:
            if self._lap_number is not None and lap_number is not None and lap_number != self._lap_number:
                self._end_lap(frame, model)
            self._start_lap(lap_number, index, clock, progress)
            return

        # Still inside the same slice: nothing to do. This is the branch almost
        # every frame takes.
        if index == self._sector_index:
            self._last_progress = progress
            self._last_clock = clock
            return

        # The lap wrapped; the finish line is handled as a new lap above.
        if not on_geometry and progress < (self._last_progress or 0.0) - 0.5:
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
        self._close_sector(frame, model, finished, entry, crossing)

    def _start_lap(self, lap_number: Optional[float], index: int, clock: float, progress: float,
                   at_line: bool = False) -> None:
        """Start counting from here; nothing is said about the slice it starts in."""
        self._partial_sector = None if at_line else index
        self._lap_number = lap_number
        self._sector_index = index
        self._sector_entry_clock = clock
        self._last_progress = progress
        self._last_clock = clock
        self._lap_loss = 0.0
        self._lap_loss_optimal = 0.0
        self._lap_worst = None
        self._lap_phrases = 0
        self._lap_losses = {}
        self._lap_onsets = [onset for onset in self._lap_onsets[-1:] if progress < LINE_WINDOW]
        self._lap_diffs = {}
        self._lap_started_at_line = at_line
        self._lap_line_clock = clock if at_line else None
        self._lap_had_ai = False
        self._spoken_sectors = set()

    def _end_lap(self, frame: Dict[str, Any], model: Any) -> None:
        """The line: the summary, then the lap joins the session (if it counts) and the focus is redone."""
        self._speak_lap_summary(frame, model)
        if _legacy(model):
            return
        complete = len(self._lap_diffs) == model.microsectors
        if self._lap_started_at_line and complete and not self._lap_had_ai:
            self._session_laps.append(dict(self._lap_diffs))
        self._update_focus(frame, model)

    def focus_sectors(self, model: Any) -> Tuple[Tuple[int, ...], str]:
        """The three slices furthest behind the reference, by median, and where that came from.

        The session's last `FOCUS_LAPS` laps that count once there are that many
        (only slices measured in all of them); before that, the driver's laps in
        the model -- his median through each slice against the reference.
        """
        if len(self._session_laps) >= FOCUS_LAPS:
            by_sector: Dict[int, list] = {}
            for lap in self._session_laps:
                for index, diff in lap.items():
                    by_sector.setdefault(index, []).append(diff)
            medians = {k: statistics.median(v) for k, v in by_sector.items() if len(v) == len(self._session_laps)}
            source = "sessao"
        else:
            medians = {
                t.index: float(t.median_seconds) - float(t.reference_seconds)
                for t in getattr(model, "targets", [])
                if getattr(t, "reference_seconds", None) is not None and getattr(t, "median_seconds", None) is not None
            }
            source = "modelo"
        # Only slices he is actually behind in: a model of one lap (or the
        # reference against itself) has no difference to listen for.
        behind = [k for k in medians if medians[k] >= SUMMARY_MIN_LOSS]
        ranked = sorted(behind, key=lambda k: (-medians[k], k))[:FOCUS_SECTORS]
        return tuple(sorted(ranked)), source

    def _update_focus(self, frame: Dict[str, Any], model: Any) -> None:
        focus, source = self.focus_sectors(model)
        changed = focus != self._focus
        self._focus, self._focus_source = focus, source
        if changed and focus:
            self._emit_focus_event(frame, model, focus, source)

    def _emit_focus_event(self, frame: Dict[str, Any], model: Any, focus: Tuple[int, ...], source: str) -> None:
        """A short line in the feed: where the coach will listen in the next laps."""
        label = getattr(model, "reference_label", "sua volta de referencia")
        listed = ", ".join(str(k) for k in focus[:-1]) + (" e " if len(focus) > 1 else "") + str(focus[-1])
        where = (
            f"nas ultimas {FOCUS_LAPS} voltas validas da sessao" if source == "sessao" else "nas suas voltas do modelo"
        )
        self._publish(COACHING_EVENT, {
            "type": FOCUS_EVENT,
            "event": f"Foco nas proximas voltas: {'setor' if len(focus) == 1 else 'setores'} {listed}",
            "severity": 0.0,
            "evidence": f"Maior diferenca mediana para a {label} {where}.",
            "focusSectors": list(focus),
            "focusSource": source,
            "driver_id": str(frame.get("driver_id") or "player_1"),
            "lap_number": int(_number(frame.get("lap_number") or frame.get("lap")) or 0),
            "s": 0.0,
            "timestamp": time.time(),
        })

    def posicao_oficial(self) -> Optional[Dict[str, Any]]:
        """Pedido 31: onde o carro esta, na projecao da geometria oficial que o coach ja faz.

        So leitura: `s` em metros, a lateral (positiva para a esquerda) e a volta
        do jogo. None sem projecao (modelo antigo, sem geometria ou antes do
        primeiro quadro).
        """
        if self._projector is None or self._last_progress is None:
            return None
        length = float(self._projector.geometry.length)
        tempo = (self._last_clock - self._lap_line_clock
                 if self._lap_line_clock is not None and self._last_clock is not None else None)
        return {"s": float(self._last_progress) * length, "comprimento": length,
                "lateral": self._last_lateral, "volta": self._volta_do_jogo,
                "tempoDaVolta": tempo, "desdeALinha": self._lap_line_clock is not None}

    def _position_m(self, frame: Dict[str, Any], progress: float) -> Optional[float]:
        """Where the car is along the lap, in metres, on the model's ruler."""
        if self._projector is not None:
            return progress * self._projector.geometry.length
        return _number(frame.get("s"))

    def _close_sector(self, frame: Dict[str, Any], model: Any, finished: Optional[int],
                      entry: Optional[float], crossing: float) -> None:
        """A slice was completed: compare it with the model and speak if it is worth it."""
        if entry is None or finished is None:
            return
        if finished == self._partial_sector:
            self._partial_sector = None
            return
        stopped = self._closing_min_speed is not None and self._closing_min_speed < STOPPED_KMH
        in_pits = (
            self._closing_max_lateral is not None and self._closing_max_lateral > PIT_LATERAL_M
            and self._closing_min_speed is not None and self._closing_min_speed < PIT_SPEED_KMH
        )
        if stopped or in_pits:
            return

        split = crossing - entry
        if split <= 0:
            return
        target = model.target_at((finished + 0.5) / model.microsectors)
        if target is None:
            return

        legacy = _legacy(model)
        # Against the optimised line this is counted whether or not he beat his
        # own best here: the two targets answer different questions, and a slice
        # where he set a personal best can still be half a second off the line.
        # Only in the old mode: the line's seconds come from the simulator, and
        # ADR 0004 keeps those out of what the driver hears.
        optimal = getattr(target, "optimal_seconds", None)
        if legacy and optimal is not None:
            self._lap_loss_optimal += max(0.0, split - float(optimal))

        compared = target.best_seconds if legacy else getattr(target, "reference_seconds", None)
        if compared is None:
            return
        loss = split - float(compared)
        if not legacy:
            self._lap_diffs[finished] = loss
        if loss <= 0:
            return
        self._lap_loss += loss
        self._lap_losses[finished] = loss
        if self._lap_worst is None or loss > self._lap_worst["lossS"]:
            self._lap_worst = {"index": finished, "lossS": round(loss, 3)}
        if loss < self._threshold_for(target):
            return
        if not legacy:
            # Pedido 15: only in the focus slices, once each.
            if finished not in (self._focus or ()) or finished in self._spoken_sectors:
                return
            if self._lap_phrases >= MAX_PHRASES_PER_LAP:
                return

        now = time.monotonic()
        if now - self._last_event_at < self.min_gap_seconds:
            return
        self._last_event_at = now
        if legacy:
            self._emit_coaching_event(frame, target, split, loss)
        else:
            self._lap_phrases += 1
            self._spoken_sectors.add(finished)
            self._emit_reference_event(frame, model, target, split, loss)

    def _physics_clock(self, frame: Dict[str, Any], lap_clock: float, progress: float) -> float:
        """The game's lap timer, stitched across its resets into one clock.

        Where the timer resets, the time between the last sample of the old lap
        and the first of the new one is the distance between them over the
        speed: the line sits somewhere in between, and the two samples are a
        metre or so apart.
        """
        length = self._projector.geometry.length if self._projector is not None else 1.0
        s = progress * length
        if self._last_lap_clock is not None and self._last_clock_s is not None and lap_clock < self._last_lap_clock - 1.0:
            travelled = (s - self._last_clock_s) % length
            speed_kmh = _number(frame.get("speedKmh"))
            speed = speed_kmh / 3.6 if speed_kmh is not None else _number(frame.get("speed"))
            between = travelled / speed if speed is not None and speed > 1.0 else 0.0
            self._clock_offset += self._last_lap_clock + between - lap_clock
        self._last_lap_clock = lap_clock
        self._last_clock_s = s
        return lap_clock + self._clock_offset

    def _progress(self, frame: Dict[str, Any], model: Any, dt: Optional[float] = None) -> Optional[float]:
        """Where in the lap the car is, 0 to 1, on the ruler the model was fitted on."""
        if not getattr(model, "geometry_id", None):
            return _number(frame.get("p") if frame.get("p") is not None else frame.get("lapProgress"))
        projector = self._projector_for(model)
        if projector is None:
            return None
        x = _number(frame.get("world_x") if frame.get("world_x") is not None else frame.get("worldX"))
        z = _number(frame.get("world_z") if frame.get("world_z") is not None else frame.get("worldZ"))
        if x is None or z is None:
            return None
        # Speed and interval size the projection's hard continuity (pedido 14).
        speed_kmh = _number(frame.get("speedKmh"))
        speed = speed_kmh / 3.6 if speed_kmh is not None else _number(frame.get("speed"))
        s, lateral = projector.project(x, z, speed_mps=speed, dt_s=dt)
        self._last_lateral = lateral
        return s / projector.geometry.length

    def _projector_for(self, model: Any) -> Any:
        """The projector on the model's geometry, or None (and one log line) if it cannot be had."""
        wanted = model.geometry_id
        if self._projector is not None and self._projector_geometry_id == wanted:
            return self._projector
        geometry = None
        try:
            geometry = self.geometry_provider(self._track)
        except Exception as error:
            logger.warning("Official geometry unavailable for coaching: %s", error)
        if geometry is None or geometry.geometry_id != wanted:
            reason = "missing" if geometry is None else f"is {geometry.geometry_id}"
            if self._warned_geometry != f"{wanted}:{reason}":
                logger.warning(
                    "Coach model was measured on geometry %s, but the official geometry file %s; coach is silent",
                    wanted,
                    reason,
                )
                self._warned_geometry = f"{wanted}:{reason}"
            self._projector = None
            return None
        self._projector = geometry.projector()
        self._projector_geometry_id = wanted
        return self._projector

    def _usable(self, model: Any) -> bool:
        """In the reference mode, a model without a reference lap says nothing.

        A model saved before ADR 0012 has no reference lap. Falling back to the
        best-per-microsector comparison would bring back the "ideal lap" the
        driver was told is gone, so the coach stays quiet and logs once that the
        model needs refitting (`tools/train_reference_model.py`).
        """
        if _legacy(model) or getattr(model, "has_reference", False):
            return True
        if not self._warned_missing_reference:
            logger.warning(
                "Reference model for %s has no reference lap; coach is silent until it is refitted",
                getattr(model, "track", "?"),
            )
            self._warned_missing_reference = True
        return False

    def _threshold_for(self, target: Any) -> float:
        """How far off his own best this driver has to be, here, to hear about it.

        The same in both modes (ADR 0012): the driver's own spread through the
        slice, median minus best, measured over every lap in the model.
        """
        spread = None
        median = getattr(target, "median_seconds", None)
        best = getattr(target, "best_seconds", None)
        if median is not None and best is not None:
            spread = max(0.0, median - best)
        if not spread:
            return self.min_loss_seconds
        return max(self.min_loss_seconds, spread * LOSS_SPREAD_MULTIPLE)

    # ── what it says ─────────────────────────────────────────────────────

    def _your_brake_onset(self, reference_onset: Optional[float]) -> Optional[float]:
        """The lap's start of braking nearest the reference's, within `BRAKE_MATCH_M`."""
        if reference_onset is None or not self._lap_onsets:
            return None
        length = self._projector.geometry.length if self._projector is not None else None

        def gap(onset: float) -> float:
            d = onset - reference_onset
            if length:
                d = (d + length / 2.0) % length - length / 2.0
            return d

        nearest = min(self._lap_onsets, key=lambda onset: abs(gap(onset)))
        return nearest if abs(gap(nearest)) <= BRAKE_MATCH_M else None

    def _emit_reference_event(self, frame: Dict[str, Any], model: Any, target: Any, split: float, loss: float) -> None:
        """A measured difference to the reference, which is named, and what it did here."""
        reference = float(target.reference_seconds)
        kind = getattr(model, "reference_kind", None)
        label = getattr(model, "reference_label", "sua volta de referencia")
        evidence: Dict[str, Any] = {
            "microsector": target.index,
            "yourSeconds": round(split, 3),
            "referenceSeconds": round(reference, 3),
            "lossSeconds": round(loss, 3),
            "referenceLapId": getattr(model, "reference_lap_id", None),
            "referenceKind": kind,
            "referenceLabel": label,
        }
        at_lap_time = _number(frame.get("lap_time"))
        if at_lap_time is not None:
            evidence["atLapTimeSeconds"] = round(at_lap_time, 3)

        message = f"Setor {target.index}: {loss:.2f}s atras da {label} neste trecho ({split:.2f}s contra {reference:.2f}s)."
        clauses = []
        reference_onset = getattr(target, "reference_brake_onset_m", None)
        your_onset = self._your_brake_onset(reference_onset)
        if reference_onset is not None and your_onset is not None:
            delta = reference_onset - your_onset
            if self._projector is not None:
                length = self._projector.geometry.length
                delta = (delta + length / 2.0) % length - length / 2.0
            evidence["referenceBrakeOnsetM"] = round(reference_onset, 1)
            evidence["yourBrakeOnsetM"] = round(your_onset, 1)
            evidence["brakeDeltaM"] = round(delta, 1)
            clauses.append(_braking_clause(kind, delta))
        reference_min = getattr(target, "reference_min_speed_kmh", None)
        your_min = self._closing_min_speed
        if reference_min is not None and your_min is not None:
            evidence["referenceMinSpeedKmh"] = round(float(reference_min), 1)
            evidence["yourMinSpeedKmh"] = round(float(your_min), 1)
            clauses.append(_min_speed_clause(kind, float(reference_min), float(your_min)))
        if clauses:
            sentence = "; ".join(clauses)
            message += " " + sentence[0].upper() + sentence[1:] + "."

        self._publish(COACHING_EVENT, {
            "type": "coaching_event",
            "event": message,
            "severity": round(min(1.0, loss / 0.5), 2),
            "evidence": evidence,
            "driver_id": str(frame.get("driver_id") or "player_1"),
            "lap_number": int(_number(frame.get("lap_number") or frame.get("lap")) or 0),
            "s": _number(frame.get("s")) or 0.0,
            "timestamp": time.time(),
            "corner_id": _number(frame.get("corner_id")),
        })

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
        if not _legacy(model):
            if self._lap_loss <= 0.0 or not getattr(model, "has_reference", False) or not self._lap_losses:
                return
            label = getattr(model, "reference_label", "sua volta de referencia")
            # Differences that round to 0.00 s are not differences worth naming
            # (measured: the reference lap against itself listed "setor 0 (0.00s)").
            worst = [item for item in sorted(self._lap_losses.items(), key=lambda item: item[1], reverse=True)
                     if item[1] >= SUMMARY_MIN_LOSS][:SUMMARY_SECTORS]
            if not worst:
                return
            parts = [f"setor {index} ({loss:.2f}s)" for index, loss in worst]
            listed = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " e " + parts[-1]
            message = f"Volta fechada. Maiores diferencas para a {label}: {listed}."
            if getattr(model, "reference_lap_seconds", None):
                message += f" {label[0].upper() + label[1:]}: {model.reference_lap_seconds:.2f}s."
            self._publish(ENGINEER_SPEECH, {
                "message": message,
                "priority": "high" if self._lap_loss > 1.0 else "medium",
                "timestamp": time.time(),
                "category": "driver",
            })
            return

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

    def reset_model(self) -> None:
        """Drop the model and the projector; the next frame asks the providers again.

        Called when the app configuration changes where the model is read from,
        or which reference it uses (pedido 28). The coach rules are untouched: a
        new model or reference restarts the focus count, as before.
        """
        self._model = None
        self._projector = None
        self._projector_geometry_id = None
        self._warned_geometry = None

    def _model_for(self, track: Optional[str]) -> Any:
        key = (track or "").strip() or self._track
        if key and key != self._track:
            self._track = key
            self._model = None
            self._projector = None
            self._projector_geometry_id = None
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


def _braking_clause(kind: Optional[str], delta_m: float) -> str:
    """Where the reference starts braking, relative to the driver (positive = later)."""
    metres = abs(round(delta_m))
    if kind == "minha_melhor":
        if metres < 1:
            return "na sua melhor volta voce freou no mesmo ponto"
        return f"na sua melhor volta voce freou {metres:.0f} m {'depois' if delta_m > 0 else 'antes'}"
    subject = "a IA" if kind == "volta_ia" else "a referencia"
    if metres < 1:
        return f"{subject} freia no mesmo ponto que voce"
    return f"{subject} freia {metres:.0f} m {'depois' if delta_m > 0 else 'antes'} de voce"


def _min_speed_clause(kind: Optional[str], reference_kmh: float, yours_kmh: float) -> str:
    if kind == "volta_ia":
        return f"minima da IA {reference_kmh:.0f} km/h, a sua {yours_kmh:.0f} km/h"
    if kind == "minha_melhor":
        return f"minima na sua melhor volta {reference_kmh:.0f} km/h, agora {yours_kmh:.0f} km/h"
    return f"minima na referencia {reference_kmh:.0f} km/h, a sua {yours_kmh:.0f} km/h"


def coach_recorded_lap(
    df: Any,
    model: Any,
    *,
    lap_number: int = 0,
    track: str = "",
    driver_id: str = "player_1",
    min_loss_seconds: float = MIN_LOSS_SECONDS,
    geometry: Any = None,
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
        geometry_provider=lambda _track: geometry,
        min_loss_seconds=min_loss_seconds,
        min_gap_seconds=0.0,
    )

    columns = set(df.columns)
    for row in df.itertuples(index=False):
        data = row._asdict()
        clock = data.get("elapsed_s")
        progress = data.get("p")
        if clock is None:
            continue
        coach.on_frame({
            "p": float(progress) if progress is not None and progress == progress else None,
            "lap_time": float(clock),
            "lap_number": lap_number,
            "lap": lap_number,
            "s": float(data.get("s") or 0.0),
            "world_x": float(data["x"]) if "x" in columns and data.get("x") == data.get("x") else None,
            "world_z": float(data["z"]) if "z" in columns and data.get("z") == data.get("z") else None,
            "speedKmh": float(data.get("speed_kmh")) if "speed_kmh" in columns and data.get("speed_kmh") == data.get("speed_kmh") else None,
            "brake": float(data.get("brake")) if "brake" in columns and data.get("brake") == data.get("brake") else None,
            "driver_id": driver_id,
            "track": track,
        })

    # The radio call lands on the flag, which the walk above never crosses.
    coach._speak_lap_summary({"driver_id": driver_id}, model)   # noqa: SLF001

    focus = [event for event in bus.events if event.get("type") == FOCUS_EVENT]
    events = [event for event in bus.events if event.get("type") != FOCUS_EVENT]
    for event in events:
        event["lapTimeSeconds"] = event.get("evidence", {}).get("atLapTimeSeconds")
    return {
        "status": "READY",
        "events": events,
        "focus": focus[-1]["focusSectors"] if focus else [],
        "speech": bus.speech,
        "lossSeconds": round(coach._lap_loss, 3),   # noqa: SLF001
        "worst": coach._lap_worst,                  # noqa: SLF001
    }
