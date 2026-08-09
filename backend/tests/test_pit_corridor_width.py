import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.geometry.pit_corridor_width import correct_pit_corridor_from_markings  # noqa: E402

SAMPLES = 120


def corridor_track(width=7.5, paint_offset=2.65, varying=False):
    """A straight corridor along +x, painted at a narrower spacing than assumed."""
    center = [[float(i), 0.0] for i in range(SAMPLES)]
    widths = ([width + (i % 7) * 0.1 for i in range(SAMPLES)] if varying
              else [width] * SAMPLES)
    lines = []
    if paint_offset is not None:
        for sign in (1, -1):
            lines.append({"rings": [[[float(i), sign * paint_offset] for i in range(SAMPLES)]]})
    return {
        "markingGeometry": {"polygons": lines},
        "pitVisualGeometry": {
            "geometries": {
                "PitLaneCorridorBifurcationGeometry": {
                    "centerline": {"x": [p[0] for p in center], "y": [p[1] for p in center]},
                    "width": widths,
                    "leftEdge": {"x": [p[0] for p in center], "y": [width / 2] * SAMPLES},
                    "rightEdge": {"x": [p[0] for p in center], "y": [-width / 2] * SAMPLES},
                    "polygon": {"x": [], "y": []},
                }
            }
        },
    }


def corridor(track):
    return track["pitVisualGeometry"]["geometries"]["PitLaneCorridorBifurcationGeometry"]


class PitCorridorWidthTests(unittest.TestCase):
    """The builder writes a flat 7.5 m for the whole corridor because the width
    is a constant in the code, not something read off the track. The circuit
    paints the lane it means."""

    def test_the_corridor_takes_the_width_the_paint_shows(self):
        track = corridor_track(width=7.5, paint_offset=2.65)

        report = correct_pit_corridor_from_markings(track)

        self.assertEqual(report["status"], "CORRECTED")
        widths = corridor(track)["width"]
        self.assertAlmostEqual(widths[SAMPLES // 2], 5.3, delta=0.2)

    def test_a_width_that_already_varies_is_left_alone(self):
        """A constant width is the signature of an assumed one. A measured width
        has a distribution, and this must not second-guess it -- the entry and
        exit accesses taper, and the asphalt merge fills reuse their edges."""
        track = corridor_track(width=7.5, paint_offset=2.65, varying=True)

        report = correct_pit_corridor_from_markings(track)

        self.assertEqual(report["status"], "NO_CHANGE")
        self.assertIn("PitLaneCorridorBifurcationGeometry", report["skipped"])

    def test_paint_that_agrees_with_the_builder_changes_nothing(self):
        track = corridor_track(width=7.5, paint_offset=3.75)

        report = correct_pit_corridor_from_markings(track)

        self.assertEqual(report["status"], "NO_CHANGE")
        self.assertEqual(corridor(track)["width"][0], 7.5)

    def test_a_corridor_with_no_paint_keeps_its_assumed_width(self):
        track = corridor_track(paint_offset=None)

        report = correct_pit_corridor_from_markings(track)

        self.assertEqual(report["status"], "NO_MARKINGS")
        self.assertEqual(corridor(track)["width"][0], 7.5)

    def test_edges_and_polygon_are_rebuilt_together(self):
        track = corridor_track(width=7.5, paint_offset=2.65)

        correct_pit_corridor_from_markings(track)
        geometry = corridor(track)

        self.assertEqual(len(geometry["polygon"]["x"]), SAMPLES * 2)
        self.assertAlmostEqual(max(geometry["leftEdge"]["y"]), 2.65, delta=0.2)
        self.assertAlmostEqual(min(geometry["rightEdge"]["y"]), -2.65, delta=0.2)

    def test_the_rebuilt_width_does_not_step(self):
        track = corridor_track(width=7.5, paint_offset=2.65)
        # Paint that jumps halfway along, as a stray marking would.
        stepped = [[float(i), 2.65 if i < 60 else 6.0] for i in range(SAMPLES)]
        track["markingGeometry"]["polygons"].append({"rings": [stepped]})

        correct_pit_corridor_from_markings(track)
        widths = corridor(track)["width"]

        steps = [abs(b - a) for a, b in zip(widths, widths[1:])]  # samples 1 m apart
        self.assertLess(max(steps), 0.30)

    def test_running_twice_does_not_walk_the_corridor(self):
        track = corridor_track(width=7.5, paint_offset=2.65)

        correct_pit_corridor_from_markings(track)
        first = list(corridor(track)["width"])
        report = correct_pit_corridor_from_markings(track)

        self.assertEqual(report["status"], "ALREADY_APPLIED")
        self.assertEqual(first, corridor(track)["width"])

    def test_a_track_with_no_pit_geometry_is_untouched(self):
        report = correct_pit_corridor_from_markings({"markingGeometry": {"polygons": []}})

        self.assertEqual(report["status"], "NO_PIT_GEOMETRY")


if __name__ == "__main__":
    unittest.main()
