import asyncio
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional

from .lap_collector import LapCollector, TrackBuildState
from .runtime_state import RuntimeState
from ..cache.track_cache import TrackCache
from ..data_quality.telemetry_reliability import TelemetryReliabilityMonitor
from ..performance_metrics import performance_metrics
from ..reconstruction.track_reconstruction import TrackReconstructor
from ..telemetry.telemetry_buffer import TelemetryBuffer
from ..telemetry.telemetry_reader_impl import TelemetrySourceManager
from ..telemetry_events import event_bus


logger = logging.getLogger(__name__)


def _iso_from_timestamp(timestamp: Optional[float]) -> Optional[str]:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def _stream_status(last_sample_at: Optional[float], stale_after_seconds: float = 5.0) -> str:
    if last_sample_at is None:
        return "waiting"
    age = time.time() - last_sample_at
    return "receiving" if age <= stale_after_seconds else "stale"


class TelemetryRuntime:
    def __init__(
        self,
        source_manager: TelemetrySourceManager,
        state: Optional[RuntimeState] = None,
        buffer: Optional[TelemetryBuffer] = None,
        cache: Optional[TrackCache] = None,
        reconstructor: Optional[TrackReconstructor] = None,
        track_name: str = "telemetry_reconstructed_live",
        poll_hz: float = 60.0,
        idle_poll_hz: float = 15.0,
        stale_poll_hz: float = 5.0,
        error_poll_hz: float = 2.0,
        allow_debug_trajectory_track: bool = False,
        reliability_monitor: Optional[TelemetryReliabilityMonitor] = None,
    ):
        self.source_manager = source_manager
        self.state = state or RuntimeState()
        self.buffer = buffer or TelemetryBuffer()
        self.cache = cache or TrackCache()
        self.reconstructor = reconstructor or TrackReconstructor()
        self.track_name = track_name
        self.poll_interval = 1.0 / max(poll_hz, 1.0)
        self.idle_poll_interval = 1.0 / max(min(idle_poll_hz, poll_hz), 1.0)
        self.stale_poll_interval = 1.0 / max(min(stale_poll_hz, poll_hz), 1.0)
        self.error_poll_interval = 1.0 / max(min(error_poll_hz, poll_hz), 1.0)
        self._fresh_sample_grace_seconds = max(self.poll_interval * 6.0, 0.1)
        self._stale_after_seconds = 5.0
        self._current_poll_interval = self.stale_poll_interval
        self._poll_mode = "waiting"
        self._last_fresh_read_monotonic: Optional[float] = None
        self.reliability_monitor = reliability_monitor or TelemetryReliabilityMonitor(
            target_hz=poll_hz
        )
        self.lap_collector = LapCollector()
        self.allow_debug_trajectory_track = allow_debug_trajectory_track

        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._loop_ref: Optional[asyncio.AbstractEventLoop] = None
        self.last_sample_wall_time: Optional[float] = None

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        if self.running:
            return

        self._loop_ref = loop or asyncio.get_event_loop()
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        self.source_manager.stop()

    def _loop(self):
        next_tick = time.perf_counter()
        while self.running:
            frame_started = time.perf_counter()
            performance_metrics.mark_read_loop_start(frame_started)
            try:
                read_started = time.perf_counter()
                sample = self.source_manager.read_sample()
                performance_metrics.mark_read_attempt(time.perf_counter() - read_started)
                if not sample:
                    if (
                        self.last_sample_wall_time is not None
                        and time.time() - self.last_sample_wall_time > max(self.poll_interval * 3.0, 0.25)
                    ):
                        performance_metrics.mark_stale_sample()
                    self._set_adaptive_poll_interval()
                    next_tick = self._sleep_until_next_tick(next_tick, self._current_poll_interval)
                    continue

                performance_metrics.mark_raw_read(sample)
                self.last_sample_wall_time = time.time()
                validation_started = time.perf_counter()
                validation = self.reliability_monitor.observe(
                    sample,
                    received_at=self.last_sample_wall_time,
                )
                performance_metrics.mark_sample_validation(
                    validation.status,
                    time.perf_counter() - validation_started,
                )
                if validation.status != "INVALID":
                    self._activate_polling()
                self.buffer.add_sample(sample)
                lap_wrapped = self.lap_collector.add_sample(sample)

                if self.state.track_build_state != TrackBuildState.TRACK_READY:
                    self.state.track_build_state = TrackBuildState.COLLECTING_LAP
                    self.state.build_method = "live_open_path"

                if lap_wrapped and self.state.track_build_state != TrackBuildState.TRACK_READY:
                    self._try_finalize_lap()

                frame = self.state.update_car(sample)
                if frame and self._loop_ref:
                    asyncio.run_coroutine_threadsafe(event_bus.emit("processed_frame", frame), self._loop_ref)
                performance_metrics.mark_player_frame(time.perf_counter() - frame_started)
            except Exception as exc:
                logger.warning("Telemetry runtime loop error: %s", exc)
                self.state.track_build_state = TrackBuildState.TRACK_INVALID
                self._activate_error_backoff()

            next_tick = self._sleep_until_next_tick(next_tick, self._current_poll_interval)

    def _set_adaptive_poll_interval(self, now: Optional[float] = None):
        current = time.monotonic() if now is None else float(now)
        if self._last_fresh_read_monotonic is None:
            self._current_poll_interval = self.stale_poll_interval
            self._poll_mode = "waiting"
            return

        age = max(0.0, current - self._last_fresh_read_monotonic)
        if age >= self._stale_after_seconds:
            self._current_poll_interval = self.stale_poll_interval
            self._poll_mode = "stale"
        elif age >= self._fresh_sample_grace_seconds:
            self._current_poll_interval = self.idle_poll_interval
            self._poll_mode = "idle"
        else:
            self._current_poll_interval = self.poll_interval
            self._poll_mode = "active"

    def _activate_polling(self, now: Optional[float] = None):
        self._last_fresh_read_monotonic = time.monotonic() if now is None else float(now)
        self._current_poll_interval = self.poll_interval
        self._poll_mode = "active"

    def _activate_error_backoff(self):
        self._current_poll_interval = self.error_poll_interval
        self._poll_mode = "error"

    def _sleep_until_next_tick(self, next_tick: float, interval: Optional[float] = None) -> float:
        active_interval = self.poll_interval if interval is None else max(float(interval), 0.001)
        next_tick += active_interval
        now = time.perf_counter()
        sleep_for = next_tick - now
        if sleep_for > 0:
            time.sleep(sleep_for)
            return next_tick
        if now - next_tick > active_interval * 3.0:
            return now
        return next_tick

    def _try_finalize_lap(self) -> bool:
        expected_length = self.source_manager.current_track_length()
        validation = self.lap_collector.validate_completed_lap(expected_length=expected_length)
        self.state.lap_complete = validation.valid
        if not validation.valid:
            self.state.track_build_state = TrackBuildState.TRACK_INVALID
            self.state.build_method = "live_open_path"
            logger.warning("Candidate lap rejected: %s", validation.reason)
            return False

        if self.source_manager.get_active_source_name() == "assetto_corsa" and not self.allow_debug_trajectory_track:
            self.state.track_build_state = TrackBuildState.COLLECTING_LAP
            self.state.build_method = "driver_trajectory_debug_disabled"
            logger.info("Complete lap collected, but driver-trajectory TrackGeometry is disabled")
            return False

        return self.trigger_reconstruction(
            track_name=self.track_name,
            save_to_cache=True,
            samples=self.lap_collector.completed_lap_samples,
        )

    def trigger_reconstruction(
        self,
        track_name: Optional[str] = None,
        save_to_cache: bool = True,
        samples=None,
        force: bool = False,
    ) -> bool:
        if self.source_manager.get_active_source_name() == "assetto_corsa" and not self.allow_debug_trajectory_track:
            logger.info("Driver-trajectory TrackGeometry reconstruction is disabled for Assetto Corsa")
            return False

        if self.state.track_build_state == TrackBuildState.TRACK_READY and not force:
            logger.info("Active TrackGeometry is already ready; keeping immutable geometry")
            return False

        samples = list(samples or self.lap_collector.completed_lap_samples)
        if len(samples) < self.lap_collector.min_samples:
            return False

        self.reconstructor.reset()
        self.reconstructor.add_telemetry_samples(samples)
        track_data = self.reconstructor.reconstruct(track_name or self.track_name, closed_loop=True)
        if "error" in track_data:
            logger.warning("Track reconstruction skipped: %s", track_data["error"])
            self.state.track_build_state = TrackBuildState.TRACK_INVALID
            return False

        track_data["source"] = "telemetry_reconstruction_live_lap"
        track_data["reconstruction"]["method"] = "reconstructed_closed_loop"
        track_data["closedLoop"] = True
        if save_to_cache:
            self.cache.save_track(track_name or self.track_name, track_data)
        self.state.update_track(track_name or self.track_name, track_data)
        self.state.build_method = "reconstructed_closed_loop"
        self.state.track_build_state = TrackBuildState.TRACK_READY
        self.state.lap_complete = True
        logger.info("Live lap reconstructed as fixed track: %.1fm", track_data["trackLength"])
        return True

    def load_track(self, track_name: Optional[str] = None) -> bool:
        track_data = self.cache.load_track(track_name or self.track_name)
        if track_data and track_data.get("closedLoop", True):
            track_data.setdefault("reconstruction", {})["method"] = "cached_closed_loop"
            self.state.update_track(track_name or self.track_name, track_data)
            self.state.build_method = "cached_closed_loop"
            self.state.track_build_state = TrackBuildState.TRACK_READY
            return True
        return False

    def status(self):
        reliability = self.reliability_monitor.snapshot()
        seconds_since_sample = None
        if self.last_sample_wall_time is not None:
            seconds_since_sample = round(max(0.0, time.time() - self.last_sample_wall_time), 3)
        return {
            **self.source_manager.status(),
            "trackState": self.state.track_build_state.value,
            "method": self.state.build_method,
            "sampleCount": self.source_manager.sample_count,
            "playerStatus": _stream_status(self.last_sample_wall_time),
            "lastPlayerSampleAt": _iso_from_timestamp(self.last_sample_wall_time),
            "secondsSinceLastPlayerSample": seconds_since_sample,
            "lapComplete": self.state.lap_complete,
            "activeTrackReady": self.state.track_build_state == TrackBuildState.TRACK_READY,
            "candidateLapSampleCount": len(self.lap_collector.candidate_lap_samples),
            "liveTrajectoryCount": len(self.lap_collector.live_trajectory),
            "targetHz": reliability["targetHz"],
            "estimatedHz": reliability["estimatedHz"],
            "stableHz": reliability["stableHz"],
            "frequencyStatus": reliability["frequencyStatus"],
            "droppedSamplesEstimate": reliability["droppedSamplesEstimate"],
            "sampleValidation": reliability["latestSampleValidation"],
            "adaptivePollMode": self._poll_mode,
            "adaptivePollHz": round(1.0 / self._current_poll_interval, 2),
        }

    def live_trajectory_api(self):
        return self.lap_collector.live_trajectory_api()
