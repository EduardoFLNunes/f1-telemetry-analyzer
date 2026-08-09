import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.geometry.width_continuity import enforce_width_continuity  # noqa: E402
from core.telemetry.telemetry_models import TrackPoint  # noqa: E402

SAMPLES = 600  # 600 m of track at 1 m spacing, longer than the 180 m window


def track(left_offsets, right_offsets):
    """A straight along +x. boundsLeft sits at +normal, as the real geometry does."""
    centerline = [
        TrackPoint(x=float(i), y=0.0, z=0.0, distance=float(i), spline_t=i / SAMPLES,
                   tangent=(1.0, 0.0), normal=(0.0, 1.0))
        for i in range(SAMPLES)
    ]
    # map normal is (0,-1) here, so +offset lands at map y = -offset, world z = +offset
    left = [{"x": float(i), "y": float(o), "z": float(o)} for i, o in enumerate(left_offsets)]
    right = [{"x": float(i), "y": float(-o), "z": float(-o)} for i, o in enumerate(right_offsets)]
    return {
        "centerline": centerline,
        "localWidth": [a + b for a, b in zip(left_offsets, right_offsets)],
        "boundsLeft": left,
        "boundsRight": right,
    }


class WidthContinuityTests(unittest.TestCase):
    """The raycast loses the edge for a stretch and catches the run-off beside
    the road, which draws as a block glued to the side of the band."""

    def test_a_one_sided_block_is_trimmed(self):
        """Total width dilutes it: 6 m of protrusion on a 13 m track is 46% of
        the width but 92% of that edge's offset. Judging per side is what
        finds it."""
        left = [6.5] * SAMPLES
        right = [6.5] * SAMPLES
        for index in range(300, 325):     # 25 m block, one side only
            left[index] = 12.5
        data = track(left, right)

        report = enforce_width_continuity(data)

        self.assertEqual(report["status"], "SMOOTHED")
        self.assertGreater(report["blocksLeft"], 0)
        self.assertEqual(report["blocksRight"], 0)
        self.assertAlmostEqual(data["localWidth"][312], 13.0, delta=0.6)

    def test_a_wide_stretch_that_lasts_is_the_track(self):
        """A protrusion persisting for 100 m is a wide corner, not a misread."""
        left = [6.5] * SAMPLES
        right = [6.5] * SAMPLES
        for index in range(200, 340):     # 140 m, past the block limit
            left[index] = 10.0
        data = track(left, right)

        enforce_width_continuity(data)

        self.assertAlmostEqual(data["localWidth"][270], 16.5, delta=0.6)

    def test_a_smooth_track_is_left_alone(self):
        data = track([6.5] * SAMPLES, [6.5] * SAMPLES)

        report = enforce_width_continuity(data)

        self.assertEqual(report["status"], "NO_CHANGE")

    def test_the_block_cannot_move_the_reference_it_is_judged_against(self):
        """At a 45 m window a 30 m block is most of the window and drags the
        median with it, which is how the first version missed these."""
        left = [6.5] * SAMPLES
        right = [6.5] * SAMPLES
        for index in range(300, 330):
            left[index] = 11.0
        data = track(left, right)

        enforce_width_continuity(data)

        self.assertAlmostEqual(data["localWidth"][315], 13.0, delta=0.6)

    def test_edges_keep_their_own_side(self):
        left = [6.5] * SAMPLES
        right = [6.5] * SAMPLES
        for index in range(300, 325):
            left[index] = 12.5
        data = track(left, right)

        enforce_width_continuity(data)

        self.assertGreater(data["boundsLeft"][312]["z"], 0)
        self.assertLess(data["boundsRight"][312]["z"], 0)

    def test_geometry_without_edges_is_reported_not_guessed(self):
        data = track([6.5] * SAMPLES, [6.5] * SAMPLES)
        data["boundsLeft"] = []
        data["left_edge"] = []

        report = enforce_width_continuity(data)

        self.assertEqual(report["status"], "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
