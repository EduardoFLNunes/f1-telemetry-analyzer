import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.geometry.width_continuity import enforce_width_continuity  # noqa: E402
from core.telemetry.telemetry_models import TrackPoint  # noqa: E402

SAMPLES = 200


def track(widths):
    centerline = [
        TrackPoint(x=float(i), y=0.0, z=0.0, distance=float(i), spline_t=i / SAMPLES,
                   tangent=(1.0, 0.0), normal=(0.0, 1.0))
        for i in range(SAMPLES)
    ]
    left = [{"x": float(i), "y": -w / 2, "z": -w / 2} for i, w in enumerate(widths)]
    right = [{"x": float(i), "y": w / 2, "z": w / 2} for i, w in enumerate(widths)]
    return {
        "centerline": centerline,
        "localWidth": list(widths),
        "boundsLeft": left,
        "boundsRight": right,
    }


class WidthContinuityTests(unittest.TestCase):
    """The interval raycast decides the width one sample at a time, and where it
    picks the wrong interval the width jumps. A track does not change width at
    1.8 m per metre; on the map that reads as the band breaking apart."""

    def test_a_spike_is_replaced_by_what_the_track_around_it_says(self):
        widths = [13.0] * SAMPLES
        widths[100] = 5.0

        report = enforce_width_continuity(track(widths))

        self.assertEqual(report["status"], "SMOOTHED")
        self.assertGreaterEqual(report["outliers"], 1)

    def test_the_corrected_width_no_longer_steps(self):
        widths = [13.0] * SAMPLES
        for index in range(100, 104):
            widths[index] = 5.0
        data = track(widths)

        enforce_width_continuity(data)

        result = data["localWidth"]
        rates = [abs(b - a) for a, b in zip(result, result[1:])]  # samples 1 m apart
        self.assertLessEqual(max(rates), 0.26)

    def test_a_real_narrowing_survives(self):
        """A chicane genuinely narrows. Gradual change is the track; a step is a
        misread, and only the step is removed."""
        widths = [13.0 - 4.0 * min(index, 60) / 60 for index in range(SAMPLES)]
        data = track(widths)

        enforce_width_continuity(data)

        self.assertAlmostEqual(data["localWidth"][80], 9.0, delta=0.3)

    def test_a_smooth_track_is_left_alone(self):
        data = track([13.0] * SAMPLES)

        report = enforce_width_continuity(data)

        self.assertEqual(report["status"], "NO_CHANGE")

    def test_the_edges_follow_the_corrected_width(self):
        widths = [13.0] * SAMPLES
        widths[100] = 5.0
        data = track(widths)

        enforce_width_continuity(data)

        left = data["boundsLeft"][100]
        right = data["boundsRight"][100]
        self.assertAlmostEqual(abs(left["z"]) + abs(right["z"]), data["localWidth"][100], places=3)
        self.assertGreater(abs(left["z"]) + abs(right["z"]), 10.0)

    def test_geometry_without_edges_is_reported_not_guessed(self):
        data = track([13.0] * SAMPLES)
        data["boundsLeft"] = []
        data["left_edge"] = []

        report = enforce_width_continuity(data)

        self.assertEqual(report["status"], "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
