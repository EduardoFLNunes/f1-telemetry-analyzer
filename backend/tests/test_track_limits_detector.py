import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.geometry.track_limits_detector import (  # noqa: E402
    TrackLimits,
    car_corners,
    measure_agreement,
)
from core.telemetry.telemetry_models import TrackPoint  # noqa: E402

POINTS = 300


def straight(width=12.0):
    centerline = [
        TrackPoint(x=float(i), y=0.0, z=0.0, distance=float(i), spline_t=i / POINTS,
                   tangent=(1.0, 0.0), normal=(0.0, 1.0))
        for i in range(POINTS)
    ]
    return {
        "centerline": centerline,
        "localWidth": [width] * POINTS,
        "boundsLeft": [{"x": float(i), "y": width / 2, "z": width / 2} for i in range(POINTS)],
        "boundsRight": [{"x": float(i), "y": -width / 2, "z": -width / 2} for i in range(POINTS)],
        # Paint at six metres each side: the limit is a 12 m corridor.
        "markingGeometry": {"polygons": [
            {"rings": [[[float(i), 6.0] for i in range(POINTS)]]},
            {"rings": [[[float(i), -6.0] for i in range(POINTS)]]},
        ]},
        "kerbGeometry": {"polygons": []},
    }


def sample(x, y, tyres_out, heading=0.0):
    return {"mapPosition": {"x": x, "y": y}, "heading": heading, "tyres_out": tyres_out}


class CarFootprintTests(unittest.TestCase):
    def test_four_corners_span_the_car(self):
        corners = car_corners(0.0, 0.0, 0.0)

        self.assertEqual(len(corners), 4)
        self.assertAlmostEqual(max(c[0] for c in corners) - min(c[0] for c in corners), 4.8, places=3)
        self.assertAlmostEqual(max(c[1] for c in corners) - min(c[1] for c in corners), 2.0, places=3)

    def test_the_footprint_turns_with_the_car(self):
        corners = car_corners(0.0, 0.0, math.pi / 2)

        self.assertAlmostEqual(max(c[1] for c in corners) - min(c[1] for c in corners), 4.8, places=2)


class TrackLimitsTests(unittest.TestCase):
    def test_the_centre_of_the_track_is_inside(self):
        limits = TrackLimits(straight())

        self.assertTrue(limits.available)
        self.assertFalse(limits.outside((150.0, 0.0))[0])

    def test_a_point_past_the_paint_is_outside(self):
        limits = TrackLimits(straight())

        self.assertTrue(limits.outside((150.0, 9.0))[0])

    def test_the_verdict_carries_where_the_limit_came_from(self):
        limits = TrackLimits(straight())

        self.assertEqual(limits.outside((150.0, 9.0))[1], "paint")

    def test_one_wheel_over_is_not_a_violation(self):
        """Four wheels is the rule; anything less is running wide."""
        limits = TrackLimits(straight())

        wheels, _ = limits.wheels_outside(150.0, 5.6, 0.0)

        self.assertLess(wheels, 4)

    def test_a_car_fully_off_has_all_four_wheels_out(self):
        limits = TrackLimits(straight())

        wheels, _ = limits.wheels_outside(150.0, 12.0, 0.0)

        self.assertEqual(wheels, 4)


class AgreementTests(unittest.TestCase):
    def test_agreement_is_scored_against_the_simulator(self):
        track = straight()
        samples = [sample(150.0, 0.0, 0), sample(150.0, 12.0, 4), sample(120.0, 0.0, 0)]

        report = measure_agreement(track, samples)

        self.assertEqual(report["status"], "MEASURED")
        self.assertEqual(report["samples"], 3)
        self.assertEqual(report["agreementPercent"], 100.0)

    def test_disagreements_are_split_by_direction(self):
        """A false alarm and a miss are different failures and must not cancel."""
        track = straight()
        samples = [sample(150.0, 0.0, 4), sample(150.0, 12.0, 0)]

        report = measure_agreement(track, samples)

        self.assertEqual(report["missed"], 1)
        self.assertEqual(report["falseAlarms"], 1)
        self.assertEqual(report["agreementPercent"], 0.0)

    def test_samples_without_the_simulator_field_are_skipped_not_assumed(self):
        track = straight()
        samples = [sample(150.0, 0.0, 0), {"mapPosition": {"x": 150.0, "y": 0.0}, "heading": 0.0}]

        report = measure_agreement(track, samples)

        self.assertEqual(report["samples"], 1)
        self.assertEqual(report["skipped"], 1)

    def test_agreement_is_reported_per_limit_source(self):
        """A violation called on interpolated limit is worth less than one
        called against paint, and averaging them hides that."""
        track = straight()

        report = measure_agreement(track, [sample(150.0, 0.0, 0)])

        self.assertIn("paint", report["bySource"])


if __name__ == "__main__":
    unittest.main()
