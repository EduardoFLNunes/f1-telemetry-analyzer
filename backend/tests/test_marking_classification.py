import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.geometry.marking_classification import (  # noqa: E402
    classify_marking_rings,
    pit_corridor,
)


def lane(points):
    return {"points": [{"mapPosition": [float(x), float(y)]} for x, y in points]}


def straight_lane(y=0.0, start=0.0, end=400.0, step=5.0):
    x = start
    points = []
    while x <= end:
        points.append((x, y))
        x += step
    return lane(points)


def stroke(y, start, end, width=0.25, step=5.0):
    """A thin painted line as the closed contour of its own stroke."""
    top, bottom = [], []
    x = start
    while x <= end:
        top.append([x, y])
        bottom.append([x, y + width])
        x += step
    return top + list(reversed(bottom))


def geometry(*rings):
    return {"polygons": [{"rings": [ring]} for ring in rings]}


def pit_lane_leaving_the_track():
    """Starts on the racing line, peels off, runs parallel 30 m away."""
    points = [(x, 0.0) for x in range(0, 60, 5)]
    points += [(60.0 + index * 5.0, -3.0 * index) for index in range(1, 11)]
    points += [(x, -30.0) for x in range(110, 360, 5)]
    return lane(points)


class PitCorridorTests(unittest.TestCase):
    def test_corridor_is_only_the_part_that_left_the_track(self):
        corridor = pit_corridor(pit_lane_leaving_the_track(), straight_lane())
        self.assertGreater(len(corridor), 2)
        # nothing in the corridor may still be sitting on the racing line
        self.assertGreater(min(abs(point[1]) for point in corridor), 10.0)

    def test_no_pit_lane_gives_no_corridor(self):
        self.assertEqual(len(pit_corridor(None, straight_lane())), 0)


class ClassifyMarkingRingsTests(unittest.TestCase):
    def setUp(self):
        self.fast = straight_lane()
        self.pit = pit_lane_leaving_the_track()

    def classify(self, *rings):
        result = classify_marking_rings(geometry(*rings), self.fast, self.pit)
        return {feature["id"]: feature for feature in result["features"]}, result["classification"]

    def test_paint_beside_the_racing_line_is_the_track_limit(self):
        features, _ = self.classify(stroke(6.0, 150.0, 350.0))
        self.assertEqual(features["0.0"]["kind"], "limite")
        self.assertTrue(features["0.0"]["closed"])

    def test_paint_inside_the_pit_corridor_is_pit_paint(self):
        features, report = self.classify(stroke(-27.0, 150.0, 340.0))
        self.assertEqual(features["0.0"]["kind"], "boxes")
        self.assertGreater(report["pitCorridorLengthM"], 100.0)

    def test_paint_far_from_both_is_service(self):
        features, _ = self.classify(stroke(45.0, 150.0, 340.0))
        self.assertEqual(features["0.0"]["kind"], "servico")

    def test_paint_beyond_the_pit_lane_edge_is_not_pit_paint(self):
        """The track limit runs parallel past the pit wall and must stay track."""
        features, _ = self.classify(stroke(-38.0, 150.0, 340.0))
        self.assertNotEqual(features["0.0"]["kind"], "boxes")

    def test_a_contour_that_is_part_track_part_pit_is_cut(self):
        # Runs along the track, crosses over, then runs along the pit lane.
        along_track = [[x, 6.0] for x in range(150, 350, 5)]
        crossing = [[350.0, 6.0 - index * 3.0] for index in range(1, 12)]
        along_pit = [[x, -28.0] for x in range(345, 145, -5)]
        back = [[150.0, -28.0 + index * 3.0] for index in range(1, 12)]
        features, report = self.classify(along_track + crossing + along_pit + back)

        kinds = {feature["kind"] for feature in features.values()}
        self.assertIn("limite", kinds)
        self.assertIn("boxes", kinds)
        self.assertGreater(report["cutCount"], 0)
        for feature in features.values():
            self.assertFalse(feature["closed"], "cut pieces are open polylines")
            self.assertEqual(feature["cutFrom"], "0.0")

    def test_a_sliver_of_pit_does_not_reclassify_a_long_track_line(self):
        """Near the pit exit the limit line grazes the corridor; that is noise."""
        long_line = [[x, 6.0] for x in range(0, 400, 2)]
        graze = [[400.0, 6.0], [402.0, -26.0], [404.0, -26.0], [406.0, 6.0]]
        back = [[x, 6.25] for x in range(400, 0, -2)]
        features, _ = self.classify(long_line + graze + back)
        self.assertEqual({feature["kind"] for feature in features.values()}, {"limite"})

    def test_missing_fast_lane_is_reported_instead_of_guessed(self):
        result = classify_marking_rings(geometry(stroke(6.0, 10.0, 90.0)), {"points": []}, self.pit)
        self.assertEqual(result["classification"]["status"], "MISSING_FAST_LANE")
        self.assertEqual(result["features"], [])

    def test_polygons_are_left_untouched_for_the_measuring_side(self):
        source = geometry(stroke(6.0, 150.0, 350.0))
        before = [list(ring) for polygon in source["polygons"] for ring in polygon["rings"]]
        classify_marking_rings(source, self.fast, self.pit)
        after = [list(ring) for polygon in source["polygons"] for ring in polygon["rings"]]
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
