import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.geometry.paint_boundary_rings import (  # noqa: E402
    build_track_frame,
    identify_boundary_rings,
    painted_limit_profile,
)
from core.geometry.paint_edge_correction import correct_edges_from_paint  # noqa: E402
from core.telemetry.telemetry_models import TrackPoint  # noqa: E402

POINTS = 400


def straight_track(width=12.0, points=POINTS):
    """A straight along +x. The normal is (0,-1) in map space, so paint at a
    positive map-y offset reads as the left side."""
    centerline = [
        TrackPoint(x=float(i), y=0.0, z=0.0, distance=float(i), spline_t=i / points,
                   tangent=(1.0, 0.0), normal=(0.0, 1.0))
        for i in range(points)
    ]
    return {
        "trackName": "straight",
        "centerline": centerline,
        "localWidth": [width] * points,
        "boundsLeft": [{"x": float(i), "y": -width / 2, "z": -width / 2} for i in range(points)],
        "boundsRight": [{"x": float(i), "y": width / 2, "z": width / 2} for i in range(points)],
    }


def line(offset, start=0, end=POINTS, step=2):
    return {"rings": [[[float(i), float(offset)] for i in range(start, end, step)]]}


def widths(track):
    return track["localWidth"]


class PaintedLimitProfileTests(unittest.TestCase):
    """Casting the normal onto the painted line, rather than binning painted
    points onto their nearest sample, is what makes sparse paint usable."""

    def test_ray_finds_the_limit_between_two_painted_points(self):
        track = straight_track(width=12.0)
        # 20 m between painted vertices: nearest-point binning would leave most
        # samples with no limit at all.
        track["markingGeometry"] = {"polygons": [line(6.0, step=20), line(-6.0, step=20)]}
        frame = build_track_frame(track)
        rings = identify_boundary_rings(track, frame)
        profile = painted_limit_profile(track, frame, rings)

        measured = sum(1 for value in profile["left"] if value == value)
        self.assertGreater(measured, POINTS * 0.8, "a sparse line still spans every sample it crosses")

    def test_outer_edge_of_the_painted_band_is_the_limit(self):
        track = straight_track(width=12.0)
        # A painted line is a band: inner edge at 6.0, outer at 6.25.
        track["markingGeometry"] = {"polygons": [line(6.0), line(6.25)]}
        frame = build_track_frame(track)
        profile = painted_limit_profile(track, frame, identify_boundary_rings(track, frame))

        mid = profile["left"][POINTS // 2]
        self.assertAlmostEqual(mid, 6.25, places=2)


class PaintEdgeCorrectionTests(unittest.TestCase):
    def test_narrow_track_is_widened_to_the_paint(self):
        track = straight_track(width=9.0)  # paint says 12 m
        track["markingGeometry"] = {"polygons": [line(6.0), line(-6.0)]}

        report = correct_edges_from_paint(track)

        self.assertEqual(report["status"], "CORRECTED")
        self.assertAlmostEqual(widths(track)[POINTS // 2], 12.0, delta=0.2)

    def test_paint_never_narrows_the_track(self):
        """A limit line proves the track reaches at least that far out. It does
        not prove the asphalt stops there -- Interlagos draws the pit access as
        part of the band on purpose, and narrowing to the paint cut 180 m of it
        from 11.9 m to 6.9 m wide."""
        track = straight_track(width=13.0)  # wider than the paint at 12 m
        track["markingGeometry"] = {"polygons": [line(6.0), line(-6.0)]}

        report = correct_edges_from_paint(track)

        self.assertEqual(report["status"], "NO_CHANGE")
        self.assertEqual(widths(track)[POINTS // 2], 13.0)

    def test_inner_markings_are_not_treated_as_the_limit(self):
        """The verification thresholds are loose on purpose and let a marking at
        0.56 half-widths through. Correcting to it would halve the track."""
        track = straight_track(width=12.0)
        track["markingGeometry"] = {"polygons": [line(3.4), line(-3.4)]}

        report = correct_edges_from_paint(track)

        self.assertEqual(report["status"], "NO_BOUNDARY_PAINT")
        self.assertEqual(widths(track)[POINTS // 2], 12.0)

    def test_correction_eases_back_where_the_paint_stops(self):
        track = straight_track(width=9.0)
        track["markingGeometry"] = {"polygons": [line(6.0, start=100, end=200)]}

        correct_edges_from_paint(track)
        values = widths(track)

        self.assertAlmostEqual(values[150], 10.5, delta=0.3)   # corrected (one side only)
        self.assertAlmostEqual(values[350], 9.0, delta=0.05)   # untouched, far away
        steps = [abs(b - a) for a, b in zip(values, values[1:])]
        self.assertLess(max(steps), 0.35, "a step in the edge reads worse than the error being fixed")

    def test_running_twice_does_not_walk_the_track_wider(self):
        track = straight_track(width=9.0)
        track["markingGeometry"] = {"polygons": [line(6.0), line(-6.0)]}

        correct_edges_from_paint(track)
        first = list(widths(track))
        second_report = correct_edges_from_paint(track)

        self.assertEqual(second_report["status"], "ALREADY_APPLIED")
        self.assertEqual(first, widths(track))

    def test_edges_and_asphalt_polygon_move_together(self):
        """The dash draws asphaltPolygon, not the edges. Correcting one without
        the other changes the numbers and nothing on screen."""
        track = straight_track(width=9.0)
        track["markingGeometry"] = {"polygons": [line(6.0), line(-6.0)]}
        track["asphaltPolygon"] = {"points": [], "x": [], "y": []}

        correct_edges_from_paint(track)

        left = track["boundsLeft"][POINTS // 2]
        self.assertAlmostEqual(abs(left["z"]), 6.0, delta=0.15)
        self.assertEqual(len(track["asphaltPolygon"]["x"]), POINTS * 2)
        self.assertAlmostEqual(max(track["asphaltPolygon"]["y"]), 6.0, delta=0.15)

    def test_track_without_paint_is_left_alone(self):
        track = straight_track(width=9.0)

        report = correct_edges_from_paint(track)

        self.assertEqual(report["status"], "NO_BOUNDARY_PAINT")
        self.assertEqual(widths(track)[0], 9.0)

    def test_absurd_paint_is_rejected_rather_than_applied(self):
        track = straight_track(width=12.0)
        track["markingGeometry"] = {"polygons": [line(40.0), line(-40.0)]}

        report = correct_edges_from_paint(track)

        self.assertEqual(report["status"], "NO_BOUNDARY_PAINT")
        self.assertEqual(widths(track)[POINTS // 2], 12.0)


if __name__ == "__main__":
    unittest.main()
