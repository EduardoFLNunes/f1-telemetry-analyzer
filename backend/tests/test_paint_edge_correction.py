import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.geometry.paint_boundary_rings import (  # noqa: E402
    build_track_frame,
    identify_boundary_rings,
    painted_limit_profile,
)
from core.geometry.paint_edge_correction import (  # noqa: E402
    MAX_CORRECTION_METERS,
    correct_edges_from_paint,
)
from core.telemetry.telemetry_models import TrackPoint  # noqa: E402

POINTS = 400


def _sign(value):
    return 1 if value > 0 else (-1 if value < 0 else 0)


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

    def test_each_edge_stays_on_its_own_side(self):
        """Nothing guarantees boundsLeft sits at +normal. Assuming the wrong sign
        rebuilt each edge on the opposite side: every point moved by about a full
        track width, the band crossed itself, and the map broke worst where the
        track is widest."""
        track = straight_track(width=9.0)
        track["markingGeometry"] = {"polygons": [line(6.0), line(-6.0)]}
        before_left = [dict(p) for p in track["boundsLeft"]]
        before_right = [dict(p) for p in track["boundsRight"]]

        correct_edges_from_paint(track)

        for before, after in zip(before_left, track["boundsLeft"]):
            self.assertEqual(_sign(after["z"]), _sign(before["z"]), "left edge changed sides")
        for before, after in zip(before_right, track["boundsRight"]):
            self.assertEqual(_sign(after["z"]), _sign(before["z"]), "right edge changed sides")

    def test_no_edge_moves_further_than_a_correction_may(self):
        track = straight_track(width=9.0)
        track["markingGeometry"] = {"polygons": [line(6.0), line(-6.0)]}
        before = [(p["x"], p["z"]) for p in track["boundsLeft"] + track["boundsRight"]]

        correct_edges_from_paint(track)

        after = [(p["x"], p["z"]) for p in track["boundsLeft"] + track["boundsRight"]]
        moves = [math.hypot(bx - ax, bz - az) for (bx, bz), (ax, az) in zip(before, after)]
        self.assertLessEqual(max(moves), MAX_CORRECTION_METERS,
                             "a correction that moves an edge further than its own cap is a rewrite")

    def test_a_geometry_with_the_other_sign_convention_is_honoured(self):
        track = straight_track(width=9.0)
        track["markingGeometry"] = {"polygons": [line(6.0), line(-6.0)]}
        # Same track, edges stored the other way round.
        track["boundsLeft"], track["boundsRight"] = track["boundsRight"], track["boundsLeft"]
        track["left_edge"], track["right_edge"] = track["boundsLeft"], track["boundsRight"]
        before_left_sign = _sign(track["boundsLeft"][0]["z"])

        correct_edges_from_paint(track)

        self.assertEqual(_sign(track["boundsLeft"][0]["z"]), before_left_sign)
        self.assertAlmostEqual(widths(track)[POINTS // 2], 12.0, delta=0.2)

    def test_a_guide_that_steps_produces_a_ramp_not_a_notch(self):
        """A kerb reading may sit up to 1.5 m from its neighbourhood median, so
        two adjacent samples can differ by 3 m. Applied straight, that cut four
        notches into the edge -- one gained 1.72 m of width in a single 1.6 m
        step, which reads as a break in the track."""
        track = straight_track(width=9.0)
        stepped = [[float(i), 6.0 if i < 200 else 9.0] for i in range(0, POINTS, 2)]
        track["markingGeometry"] = {"polygons": [{"rings": [stepped]}]}

        correct_edges_from_paint(track)
        values = widths(track)

        rates = [abs(b - a) for a, b in zip(values, values[1:])]  # samples are 1 m apart
        self.assertLess(max(rates), 0.30, "the corrected width steps between neighbouring samples")

    def test_widening_survives_the_rate_limit(self):
        track = straight_track(width=9.0)
        track["markingGeometry"] = {"polygons": [line(6.0), line(-6.0)]}

        correct_edges_from_paint(track)

        self.assertAlmostEqual(widths(track)[POINTS // 2], 12.0, delta=0.2)

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
