"""The optimised racing line, from artefact on disk to words in the panel.

Two halves. The first is the loader, which has to be suspicious: this file is
produced by a different subsystem on a different schedule, and a stale or
mangled one must degrade to "no second target" rather than hold the driver to
numbers that mean nothing. The second is the coach, which has to keep working
exactly as before when there is no line at all -- that is the common case for
every track but Interlagos.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
# O coach ja tem utilitarios de teste bons -- barramento falso, montagem de
# modelo, e um piloto que perde tempo num microsetor escolhido. Reusar e melhor
# do que manter duas versoes que divergem.
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.assisted_analysis.optimal_line import (  # noqa: E402
    OptimalLine,
    attach,
    find_optimal_line,
    optimal_line_path,
)
from core.live.driving_coach import LiveDrivingCoach  # noqa: E402
from core.telemetry_events import COACHING_EVENT, ENGINEER_SPEECH  # noqa: E402

from test_driving_coach import FakeBus, drive, model_of  # noqa: E402


def payload(microsectors: int = 60, seconds_each: float = 1.4, **overrides):
    body = {
        "version": "optimal-line-1",
        "track": "vhe_interlagos",
        "microsectors": microsectors,
        "lap_seconds": round(microsectors * seconds_each, 3),
        "seconds": [seconds_each] * microsectors,
        "min_speed_kmh": [120.0] * microsectors,
        "source": "teste",
    }
    body.update(overrides)
    return body


def write(root: Path, track: str = "vhe_interlagos", **overrides) -> Path:
    path = optimal_line_path(root, track)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload(**overrides)), encoding="utf-8")
    return path


class LoadingTest(unittest.TestCase):
    def setUp(self):
        import tempfile

        self._dir = tempfile.TemporaryDirectory()
        self.root = Path(self._dir.name)

    def tearDown(self):
        self._dir.cleanup()

    def test_a_well_formed_line_loads(self):
        line = OptimalLine.load(write(self.root))
        self.assertIsNotNone(line)
        self.assertEqual(line.microsectors, 60)
        self.assertAlmostEqual(line.lap_seconds, 84.0, places=3)
        self.assertAlmostEqual(line.seconds_at(0), 1.4, places=6)
        self.assertAlmostEqual(line.min_speed_at(59), 120.0, places=6)

    def test_an_index_outside_the_lap_is_none_not_an_error(self):
        line = OptimalLine.load(write(self.root))
        self.assertIsNone(line.seconds_at(60))
        self.assertIsNone(line.seconds_at(-1))

    def test_a_missing_file_is_none(self):
        self.assertIsNone(OptimalLine.load(self.root / "nada.json"))

    def test_an_unknown_format_is_refused(self):
        self.assertIsNone(OptimalLine.load(write(self.root, version="optimal-line-99")))

    def test_a_split_count_that_disagrees_with_the_header_is_refused(self):
        path = write(self.root)
        body = json.loads(path.read_text(encoding="utf-8"))
        body["seconds"] = body["seconds"][:50]
        path.write_text(json.dumps(body), encoding="utf-8")
        self.assertIsNone(OptimalLine.load(path))

    def test_a_lap_time_that_disagrees_with_its_own_splits_is_refused(self):
        # The number the panel shows and the numbers the coach compares against
        # have to come from the same lap.
        self.assertIsNone(OptimalLine.load(write(self.root, lap_seconds=70.0)))

    def test_corrupt_json_is_none_not_a_crash(self):
        path = optimal_line_path(self.root, "vhe_interlagos")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{ nao e json", encoding="utf-8")
        self.assertIsNone(OptimalLine.load(path))

    def test_the_runtime_root_wins_over_the_packaged_one(self):
        import tempfile

        with tempfile.TemporaryDirectory() as second:
            resource = Path(second)
            write(resource, seconds_each=2.0)  # a embarcada
            write(self.root, seconds_each=1.0)  # a regerada nesta maquina
            line = find_optimal_line([self.root, resource], "vhe_interlagos")
            self.assertAlmostEqual(line.seconds_at(0), 1.0, places=6)

    def test_the_packaged_one_is_used_when_the_runtime_has_none(self):
        import tempfile

        with tempfile.TemporaryDirectory() as second:
            resource = Path(second)
            write(resource, seconds_each=2.0)
            line = find_optimal_line([self.root, resource], "vhe_interlagos")
            self.assertAlmostEqual(line.seconds_at(0), 2.0, places=6)

    def test_no_line_anywhere_is_none(self):
        self.assertIsNone(find_optimal_line([self.root], "spa"))


class AttachTest(unittest.TestCase):
    def test_attaching_fills_every_target(self):
        model = model_of(85.0)
        line = OptimalLine.from_dict(payload(microsectors=model.microsectors, seconds_each=1.2))
        attach(model, line)
        self.assertTrue(all(t.optimal_seconds == 1.2 for t in model.targets))
        self.assertAlmostEqual(model.optimal_lap_seconds, 1.2 * model.microsectors, places=3)

    def test_no_line_leaves_the_model_untouched(self):
        model = model_of(85.0)
        attach(model, None)
        self.assertTrue(all(t.optimal_seconds is None for t in model.targets))
        self.assertIsNone(model.optimal_lap_seconds)

    def test_a_different_slicing_is_refused(self):
        # Sixty slices against thirty is the same lap cut two ways; the numbers
        # would land on the wrong asphalt.
        model = model_of(85.0)
        attach(model, OptimalLine.from_dict(payload(microsectors=30)))
        self.assertTrue(all(t.optimal_seconds is None for t in model.targets))

    def test_the_gap_from_the_drivers_best_is_reported(self):
        model = model_of(85.0)
        attach(model, OptimalLine.from_dict(payload(microsectors=model.microsectors, seconds_each=1.0)))
        target = model.targets[0]
        self.assertAlmostEqual(
            target.gap_best_to_optimal, round(target.best_seconds - 1.0, 4), places=4
        )


class CoachWithOptimalLineTest(unittest.TestCase):
    """The second target reaches the panels, and its absence changes nothing."""

    def _coach(self, model):
        bus = FakeBus()
        return bus, LiveDrivingCoach(bus, model_provider=lambda _t: model, min_gap_seconds=0.0)

    def test_events_carry_the_optimal_split(self):
        model = model_of(85.0)
        # Comfortably quicker than anything the driver did, which is what an
        # optimised line is.
        attach(model, OptimalLine.from_dict(
            payload(microsectors=model.microsectors, seconds_each=85.0 / model.microsectors * 0.9)
        ))
        bus, coach = self._coach(model)
        drive(coach, seconds=86.0, slow_slice=(20, 0.9))

        events = bus.of(COACHING_EVENT)
        self.assertTrue(events, "o coach nao falou")
        evidence = events[0]["evidence"]
        self.assertIn("optimalSeconds", evidence)
        self.assertIn("optimalLossSeconds", evidence)
        self.assertGreater(evidence["optimalLossSeconds"], evidence["lossSeconds"])
        self.assertIn("tracado otimo", events[0]["event"])

    def test_without_a_line_the_events_are_exactly_as_before(self):
        model = model_of(85.0)
        bus, coach = self._coach(model)
        drive(coach, seconds=86.0, slow_slice=(20, 0.9))

        events = bus.of(COACHING_EVENT)
        self.assertTrue(events)
        self.assertNotIn("optimalSeconds", events[0]["evidence"])
        self.assertNotIn("tracado otimo", events[0]["event"])

    def test_the_lap_summary_reports_the_gap_to_the_line(self):
        model = model_of(85.0)
        attach(model, OptimalLine.from_dict(
            payload(microsectors=model.microsectors, seconds_each=85.0 / model.microsectors * 0.9)
        ))
        bus, coach = self._coach(model)
        drive(coach, seconds=86.0, lap=5, slow_slice=(20, 0.9))
        drive(coach, seconds=86.0, lap=6)  # cruzar a linha dispara o resumo

        speech = bus.of(ENGINEER_SPEECH)
        self.assertTrue(speech, "nenhum resumo de volta")
        self.assertIn("tracado otimo", speech[0]["message"])


if __name__ == "__main__":
    unittest.main()
