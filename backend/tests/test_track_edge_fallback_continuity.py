import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.kn5.track_edges_from_surface import _reject_discontinuous_fallback_samples  # noqa: E402


def sample(index, left, right, reason=None, valid=True):
    return {
        "index": index,
        "valid": valid,
        "leftEdge": list(left) if left else None,
        "rightEdge": list(right) if right else None,
        "centerline": [0.0, 0.0],
        "localWidth": 10.0,
        "lateralReferenceOffset": 0.0,
        "correctionReason": reason,
    }


class FallbackContinuityTests(unittest.TestCase):
    """A track edge is continuous.

    When no inside interval contains the racing line the extraction falls back
    to the nearest interval, which near run-off and service asphalt can belong
    to a different strip entirely. Those samples leap sideways and back within a
    couple of points, drawing the boxy excursions seen when the extraction is
    overlaid on the KN5 surface. They are dropped so interpolation can rebuild
    them from their neighbours.
    """

    def test_fallback_that_jumps_far_is_rejected(self):
        samples = [
            sample(0, [0.0, 0.0], [10.0, 0.0]),
            sample(1, [0.0, 1.0], [10.0, 1.0]),
            sample(2, [40.0, 2.0], [50.0, 2.0], reason="corrected_from_nearest_interval"),
            sample(3, [0.0, 3.0], [10.0, 3.0]),
        ]

        rejected = _reject_discontinuous_fallback_samples(samples)

        self.assertEqual(rejected, 1)
        self.assertFalse(samples[2]["valid"])
        self.assertIsNone(samples[2]["leftEdge"])
        self.assertEqual(samples[2]["invalidReason"], "discontinuous_fallback_interval")

    def test_fallback_that_stays_continuous_is_kept(self):
        samples = [
            sample(0, [0.0, 0.0], [10.0, 0.0]),
            sample(1, [0.4, 1.0], [10.4, 1.0], reason="corrected_from_nearest_interval"),
        ]

        rejected = _reject_discontinuous_fallback_samples(samples)

        self.assertEqual(rejected, 0)
        self.assertTrue(samples[1]["valid"])
        self.assertIsNotNone(samples[1]["leftEdge"])

    def test_non_fallback_samples_are_never_touched(self):
        samples = [
            sample(0, [0.0, 0.0], [10.0, 0.0]),
            sample(1, [90.0, 1.0], [99.0, 1.0]),
        ]

        rejected = _reject_discontinuous_fallback_samples(samples)

        self.assertEqual(rejected, 0, "only nearest-interval fallbacks may be discarded")
        self.assertTrue(samples[1]["valid"])

    def test_leading_fallback_without_reference_is_kept(self):
        samples = [sample(0, [40.0, 0.0], [50.0, 0.0], reason="corrected_from_nearest_interval")]

        rejected = _reject_discontinuous_fallback_samples(samples)

        self.assertEqual(rejected, 0, "with no trustworthy neighbour there is nothing to compare against")
        self.assertTrue(samples[0]["valid"])

    def test_consecutive_fallbacks_compare_against_the_last_trusted_sample(self):
        samples = [
            sample(0, [0.0, 0.0], [10.0, 0.0]),
            sample(1, [40.0, 1.0], [50.0, 1.0], reason="corrected_from_nearest_interval"),
            sample(2, [41.0, 2.0], [51.0, 2.0], reason="corrected_from_nearest_interval"),
        ]

        rejected = _reject_discontinuous_fallback_samples(samples)

        self.assertEqual(rejected, 2, "a run of jumped fallbacks must not validate itself")


if __name__ == "__main__":
    unittest.main()
