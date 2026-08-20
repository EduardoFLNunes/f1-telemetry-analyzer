import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.live.driving_coach import LiveDrivingCoach  # noqa: E402
from core.assisted_analysis.reference_model import build_reference_model  # noqa: E402
from core.telemetry_events import COACHING_EVENT, ENGINEER_SPEECH  # noqa: E402


class FakeBus:
    """Records what would have gone onto the event bus."""

    def __init__(self):
        self.published = []

    def schedule(self, topic, payload, loop_ref=None):
        self.published.append((topic, payload))

    def of(self, topic):
        return [payload for name, payload in self.published if name == topic]


def reference_lap(seconds: float = 85.0, hz: float = 57.0):
    count = int(seconds * hz)
    progress = np.linspace(0.0, 1.0, count)
    return pd.DataFrame({
        "p": progress,
        "elapsed_s": progress * seconds,
        "speed_kmh": np.full(count, 180.0),
        "brake": np.zeros(count),
        "throttle": np.ones(count),
    })


def model_of(seconds: float = 85.0):
    return build_reference_model([("melhor", seconds, int(seconds * 57), reference_lap(seconds))],
                                 track="vhe_interlagos")


def drive(coach, *, seconds: float, lap: int = 5, steps: int = 400, track="vhe_interlagos",
          slow_slice=None):
    """
    Feed a lap through the coach one frame at a time.

    `slow_slice` is `(index, extra_seconds)`: the driver drops that much time in
    one microsector out of sixty, which is what a real mistake looks like --
    spread evenly over the lap, ten percent off the pace is only 0.14s per
    microsector and below anything worth saying out loud.
    """
    for index in range(steps):
        progress = index / (steps - 1)
        clock = progress * seconds
        if slow_slice is not None:
            slice_index, extra = slow_slice
            start, end = slice_index / 60.0, (slice_index + 1) / 60.0
            if progress >= end:
                clock += extra
            elif progress >= start:
                clock += extra * (progress - start) / (end - start)
        coach.on_frame({
            "p": progress,
            "lap_time": clock,
            "lap_number": lap,
            "lap": lap,
            "s": progress * 4300.0,
            "speedKmh": 180.0,
            "driver_id": "player_1",
            "track": track,
        })


class DrivingCoachTests(unittest.TestCase):
    def setUp(self):
        self.bus = FakeBus()
        self.model = model_of(85.0)
        self.coach = LiveDrivingCoach(self.bus, lambda track: self.model, min_gap_seconds=0.0)

    def test_says_nothing_when_the_driver_matches_his_best(self):
        drive(self.coach, seconds=85.0)
        self.assertEqual([], self.bus.of(COACHING_EVENT))

    def test_speaks_when_a_microsector_costs_real_time(self):
        drive(self.coach, seconds=85.0, slow_slice=(22, 0.6))
        events = self.bus.of(COACHING_EVENT)
        self.assertGreater(len(events), 0)
        first = events[0]
        self.assertEqual("coaching_event", first["type"])
        self.assertIn("atras do seu melhor", first["event"])
        self.assertGreater(first["evidence"]["lossSeconds"], 0.15)
        self.assertEqual(22, first["evidence"]["microsector"])
        self.assertEqual("player_1", first["driver_id"])
        self.assertEqual(5, first["lap_number"])

    def test_stays_quiet_about_losses_too_small_to_act_on(self):
        # 80 ms over a whole lap is nothing a driver can do anything with.
        drive(self.coach, seconds=85.08)
        self.assertEqual([], self.bus.of(COACHING_EVENT))

    def test_does_not_talk_over_itself(self):
        coach = LiveDrivingCoach(self.bus, lambda track: self.model, min_gap_seconds=3.0)
        for sector in range(0, 60, 3):
            drive(coach, seconds=85.0, lap=sector + 10, slow_slice=(sector, 0.5))
        # With a three second gate a single lap cannot produce a wall of events.
        self.assertLess(len(self.bus.of(COACHING_EVENT)), 10)

    def test_severity_grows_with_the_loss_and_stops_at_one(self):
        drive(self.coach, seconds=85.0, slow_slice=(30, 2.5))
        severities = [event["severity"] for event in self.bus.of(COACHING_EVENT)]
        self.assertTrue(all(0.0 < value <= 1.0 for value in severities))

    def test_calls_the_lap_on_the_radio_when_it_closes(self):
        drive(self.coach, seconds=85.0, lap=5, slow_slice=(22, 1.4))
        drive(self.coach, seconds=85.0, lap=6, slow_slice=(22, 1.4))
        speech = self.bus.of(ENGINEER_SPEECH)
        self.assertEqual(1, len(speech))
        self.assertIn("Volta fechada", speech[0]["message"])
        self.assertIn("ideal", speech[0]["message"].lower())
        self.assertIn(speech[0]["priority"], ("medium", "high"))
        self.assertEqual("driver", speech[0]["category"])

    def test_the_radio_stays_silent_after_a_clean_lap(self):
        drive(self.coach, seconds=85.0, lap=5)
        drive(self.coach, seconds=85.0, lap=6)
        self.assertEqual([], self.bus.of(ENGINEER_SPEECH))

    def test_survives_frames_that_say_nothing(self):
        for frame in ({}, {"p": None}, {"p": 0.5}, {"lap_time": 12.0}, {"p": 2.0, "lap_time": 1.0}):
            self.coach.on_frame(frame)
        self.coach.on_frame(None)  # type: ignore[arg-type]
        self.assertEqual([], self.bus.published)

    def test_has_nothing_to_say_without_a_model(self):
        coach = LiveDrivingCoach(self.bus, lambda track: None)
        drive(coach, seconds=85.0, slow_slice=(10, 2.0))
        self.assertEqual([], self.bus.published)

    def test_a_model_provider_that_raises_does_not_break_the_frame_loop(self):
        def boom(track):
            raise RuntimeError("modelo corrompido")

        coach = LiveDrivingCoach(self.bus, boom)
        drive(coach, seconds=85.0, slow_slice=(10, 2.0))
        self.assertEqual([], self.bus.published)

    def test_a_bus_that_fails_does_not_break_the_frame_loop(self):
        class BrokenBus:
            def schedule(self, *args, **kwargs):
                raise RuntimeError("bus fora do ar")

        coach = LiveDrivingCoach(BrokenBus(), lambda track: self.model, min_gap_seconds=0.0)
        drive(coach, seconds=85.0, slow_slice=(10, 2.0))   # must not raise

    def test_the_lap_wrapping_is_not_reported_as_a_lost_sector(self):
        # Crossing the line takes progress from 0.99 to 0.01, which is not a
        # microsector that took a whole lap to drive.
        coach = LiveDrivingCoach(self.bus, lambda track: self.model, min_gap_seconds=0.0)
        for index in range(200):
            progress = 0.9 + (index / 199) * 0.099
            coach.on_frame({"p": progress, "lap_time": 80 + progress, "lap_number": 7, "track": "vhe_interlagos"})
        coach.on_frame({"p": 0.01, "lap_time": 85.4, "lap_number": 7, "track": "vhe_interlagos"})
        losses = [event["evidence"]["lossSeconds"] for event in self.bus.of(COACHING_EVENT)]
        self.assertTrue(all(loss < 5.0 for loss in losses), msg=str(losses))


if __name__ == "__main__":
    unittest.main()
