import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.geometry.paint_agreement import evaluate_paint_agreement  # noqa: E402
from core.telemetry.telemetry_models import TrackPoint  # noqa: E402


def straight_track(width=12.0, points=400):
    """A straight running along +x, so the normal points along y and the maths is checkable by hand."""
    centerline = [
        TrackPoint(x=float(i), y=0.0, z=0.0, distance=float(i), spline_t=i / points,
                   tangent=(1.0, 0.0), normal=(0.0, 1.0))
        for i in range(points)
    ]
    return {"centerline": centerline, "localWidth": [width] * points}


def painted_line(offset, points=400, step=1):
    """Paint at a fixed lateral offset. Map y is -z, and the normal is (0, -1) in map
    space for this centreline, so a positive map-y offset reads as the left side."""
    return {"rings": [[[float(i), float(offset)] for i in range(0, points, step)]]}


class PaintAgreementTests(unittest.TestCase):
    """The painted limit line is a source of truth independent of the extraction.

    It cannot rebuild an edge -- real coverage is under 20% of a lap -- but it can
    say whether the extracted edge is where the paint says it should be.
    """

    def test_edges_matching_the_paint_report_ok(self):
        track = straight_track(width=12.0)
        track["markingGeometry"] = {"polygons": [painted_line(6.0), painted_line(-6.0)]}

        result = evaluate_paint_agreement(track)

        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["measuredSides"], 2)
        self.assertEqual(result["issues"], [])

    def test_track_narrower_than_the_paint_is_flagged(self):
        track = straight_track(width=9.0)  # paint at 6 m, so half-width is 4.5
        track["markingGeometry"] = {"polygons": [painted_line(6.0), painted_line(-6.0)]}

        result = evaluate_paint_agreement(track)

        self.assertEqual(result["status"], "DIVERGENT")
        self.assertTrue(result["issues"])

    def test_a_little_asphalt_past_the_line_is_not_a_defect(self):
        """The band draws asphalt, and asphalt continues past the white line out
        to the kerb -- a median 1.8 m of it on one side of Interlagos."""
        track = straight_track(width=15.0)  # paint at 12 m
        track["markingGeometry"] = {"polygons": [painted_line(6.0), painted_line(-6.0)]}

        result = evaluate_paint_agreement(track)

        self.assertEqual(result["status"], "OK")

    def test_a_track_far_wider_than_its_paint_is_still_flagged(self):
        track = straight_track(width=20.0)
        track["markingGeometry"] = {"polygons": [painted_line(6.0), painted_line(-6.0)]}

        result = evaluate_paint_agreement(track)

        self.assertEqual(result["status"], "DIVERGENT")

    def test_identification_does_not_swallow_a_wrong_edge(self):
        """Judging agreement with the same range used to find boundaries would let a
        badly placed edge be reclassified as "not a boundary" and pass silently."""
        track = straight_track(width=9.0)
        track["markingGeometry"] = {"polygons": [painted_line(6.0), painted_line(-6.0)]}

        result = evaluate_paint_agreement(track)

        self.assertNotEqual(result["status"], "INSUFFICIENT_PAINT")
        self.assertGreater(result["boundaryGroups"], 0)

    def test_pit_markings_are_not_treated_as_boundaries(self):
        track = straight_track(width=12.0)
        # Far off to one side, like the pit paint at 2.7 to 12.4 half-widths.
        track["markingGeometry"] = {"polygons": [painted_line(70.0)]}

        result = evaluate_paint_agreement(track)

        self.assertEqual(result["boundaryGroups"], 0)
        self.assertEqual(result["status"], "INSUFFICIENT_PAINT")

    def test_paint_with_a_plausible_median_but_wandering_offset_is_rejected(self):
        track = straight_track(width=12.0)
        # Alternates between one and two half-widths: median 1.5 passes the range
        # check, so only the spread can reject it.
        wandering = {"rings": [[[float(i), 6.0 if i % 2 else 12.0] for i in range(400)]]}
        track["markingGeometry"] = {"polygons": [wandering]}

        result = evaluate_paint_agreement(track)

        self.assertEqual(result["boundaryGroups"], 0, "spread is what separates a lane line from noise")

    def test_too_little_paint_reports_insufficient_rather_than_ok(self):
        track = straight_track(width=12.0, points=400)
        # 24 points, but packed into 10 m of a 400 m lap -- under the coverage floor.
        sparse = {"rings": [[[i * 0.4, 6.0] for i in range(24)]]}
        track["markingGeometry"] = {"polygons": [sparse]}

        result = evaluate_paint_agreement(track)

        self.assertEqual(result["status"], "INSUFFICIENT_PAINT")

    def test_missing_marking_geometry_is_unavailable_not_ok(self):
        track = straight_track()

        result = evaluate_paint_agreement(track)

        self.assertEqual(result["status"], "UNAVAILABLE")

    def test_missing_centerline_is_unavailable(self):
        result = evaluate_paint_agreement({"markingGeometry": {"polygons": [painted_line(6.0)]}})

        self.assertEqual(result["status"], "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
