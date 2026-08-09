import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.geometry.limit_corridor import (  # noqa: E402
    build_limit_corridor,
    identify_limit_rings,
    rebuild_edges_from_limit_corridor,
)
from core.geometry.paint_boundary_rings import build_track_frame  # noqa: E402
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
        "markingGeometry": {"polygons": []},
        "kerbGeometry": {"polygons": []},
    }


def line(offset, start=0, end=POINTS):
    return {"rings": [[[float(i), float(offset)] for i in range(start, end)]]}


class LimitRingTests(unittest.TestCase):
    """A line that is the boundary for part of a lap and something else for the
    rest was being discarded whole. Judging rings by where they sit rather than
    by how consistent they stay took Interlagos from 3 usable rings to 18."""

    def test_a_ring_that_is_only_partly_a_boundary_is_kept(self):
        track = straight()
        # Boundary for most of its length, then off to a pit wall. The spread
        # test rejected this outright; where it mostly sits is still the limit.
        partly = {"rings": [[[float(i), 6.0 if i < 240 else 30.0] for i in range(POINTS)]]}
        track["markingGeometry"]["polygons"] = [partly]
        frame = build_track_frame(track)

        rings = identify_limit_rings(track, frame)

        self.assertEqual(len(rings), 1)

    def test_paint_nowhere_near_the_edge_is_still_rejected(self):
        track = straight()
        track["markingGeometry"]["polygons"] = [line(40.0)]
        frame = build_track_frame(track)

        self.assertEqual(identify_limit_rings(track, frame), [])


class LimitCorridorTests(unittest.TestCase):
    def test_paint_and_kerb_together_cover_more_than_either(self):
        track = straight()
        track["markingGeometry"]["polygons"] = [line(6.0, 0, 150), line(-6.0, 0, 150)]
        track["kerbGeometry"]["polygons"] = [
            {"points": [[float(i), 7.0] for i in range(150, POINTS)] +
                       [[float(i), 7.4] for i in range(POINTS - 1, 149, -1)]},
            {"points": [[float(i), -7.0] for i in range(150, POINTS)] +
                       [[float(i), -7.4] for i in range(POINTS - 1, 149, -1)]},
        ]

        report = build_limit_corridor(track)

        self.assertEqual(report["status"], "OK")
        totals = {key: sum(side[key] for side in report["sides"].values())
                  for key in ("fromPaint", "fromKerb")}
        self.assertGreater(totals["fromPaint"], 0)
        self.assertGreater(totals["fromKerb"], 0, "the kerb has to cover what the paint does not")

    def test_gaps_are_filled_but_marked_as_estimated(self):
        track = straight()
        # A 100 m gap: bridged. Past 120 m the corridor refuses to guess.
        track["markingGeometry"]["polygons"] = [
            line(6.0, 0, 80), line(6.0, 180, POINTS),
            line(-6.0, 0, 80), line(-6.0, 180, POINTS),
        ]

        report = build_limit_corridor(track)
        side = next(s for s in report["sides"].values() if s.get("status") == "OK")

        self.assertGreater(side["estimated"], 0)
        self.assertEqual(side["source"][150], "estimated")
        self.assertEqual(side["source"][10], "paint")

    def test_the_outermost_source_wins_where_both_exist(self):
        """Paint marks the regulatory limit, the kerb where the asphalt ends.
        Both are floors, so the surface reaches the furthest either proves."""
        track = straight()
        track["markingGeometry"]["polygons"] = [line(6.0), line(-6.0)]
        track["kerbGeometry"]["polygons"] = [
            {"points": [[float(i), 7.5] for i in range(POINTS)] +
                       [[float(i), 7.9] for i in range(POINTS - 1, -1, -1)]},
        ]

        report = build_limit_corridor(track)

        # The kerb here sits on whichever side +7.5 in map space falls on.
        reached = max(side["limit"][150] for side in report["sides"].values()
                      if side.get("status") == "OK")
        self.assertAlmostEqual(reached, 7.5, delta=0.3)

    def test_a_track_with_nothing_painted_reports_it(self):
        report = build_limit_corridor(straight())

        self.assertIn(report["status"], {"UNAVAILABLE", "PARTIAL"})


class RebuildFromCorridorTests(unittest.TestCase):
    def test_edges_move_to_the_measured_limit(self):
        track = straight(width=9.0)          # paint puts the limit at 12 m
        track["markingGeometry"]["polygons"] = [line(6.0), line(-6.0)]

        report = rebuild_edges_from_limit_corridor(track)

        self.assertEqual(report["status"], "REBUILT")
        self.assertAlmostEqual(track["localWidth"][150], 12.0, delta=0.4)

    def test_an_estimated_stretch_keeps_the_extraction(self):
        """There is nothing to reconstruct from where nothing was measured, and
        an interpolated limit is not authority over a real reading."""
        track = straight(width=9.0)
        track["markingGeometry"]["polygons"] = [line(6.0, 0, 60), line(-6.0, 0, 60)]
        before = list(track["localWidth"])

        rebuild_edges_from_limit_corridor(track)

        self.assertAlmostEqual(track["localWidth"][280], before[280], delta=0.6)

    def test_running_twice_does_not_walk_the_edges(self):
        track = straight(width=9.0)
        track["markingGeometry"]["polygons"] = [line(6.0), line(-6.0)]

        rebuild_edges_from_limit_corridor(track)
        first = list(track["localWidth"])
        report = rebuild_edges_from_limit_corridor(track)

        self.assertEqual(report["status"], "ALREADY_APPLIED")
        self.assertEqual(first, track["localWidth"])

    def test_an_absurd_limit_is_refused(self):
        track = straight(width=9.0)
        track["markingGeometry"]["polygons"] = [line(6.0), line(-6.0)]
        # A limit 8 m out from a 4.5 m edge is past the rebuild cap.
        track["kerbGeometry"]["polygons"] = [
            {"points": [[float(i), 12.4] for i in range(POINTS)] +
                       [[float(i), 12.8] for i in range(POINTS - 1, -1, -1)]},
        ]

        rebuild_edges_from_limit_corridor(track)

        self.assertLess(max(track["localWidth"]), 9.0 + 2 * 6.0)


if __name__ == "__main__":
    unittest.main()
