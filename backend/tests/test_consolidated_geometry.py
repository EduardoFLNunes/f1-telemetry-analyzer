import json
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.geometry import interlagos_track_only_fixed as fx  # noqa: E402
from core.telemetry.telemetry_models import TrackPoint  # noqa: E402


def make_geometry():
    return {
        "provider": "InterlagosPitAccessAsphaltMergeFix",
        "trackName": "vhe_interlagos",
        "trackLength": 4345.875714780727,
        "closedLoop": True,
        "centerline": [
            TrackPoint(
                x=-411.939467,
                y=1.5,
                z=220.588081,
                distance=0.0,
                spline_t=0.0,
                curvature=1.2482831860241281e-06,
                tangent=(0.248085, 0.968738),
                normal=(0.968738, -0.248085),
            ),
            TrackPoint(x=1.0, y=-2.25, z=3.0, distance=4.0, spline_t=0.5),
        ],
        "boundsLeft": [{"x": 1.0, "y": 2.0, "z": 3.0}],
        "boundsRight": [{"x": 4.0, "y": 5.0, "z": 6.0}],
        "localWidth": [12.5],
        "pitVisualGeometry": {"name": "InterlagosPitAccessAsphaltMergeFix", "geometries": {"a": {"leftEdge": {"points": [[1.0, 2.0]]}}}},
        "metadata": {"pitVisualGeometry": "InterlagosPitAccessAsphaltMergeFix"},
    }


class ConsolidatedGeometryTests(unittest.TestCase):
    """The 13-file precedence cascade collapses into one file.

    The cascade let a candidate missing from a package silently fall through to a
    different fix, changing the rendered map with no signal. Consolidation only
    holds if the single file round-trips the resolved geometry exactly.
    """

    def test_round_trip_preserves_every_key(self):
        original = make_geometry()

        restored = fx.deserialize_consolidated_geometry(
            fx.serialize_consolidated_geometry(original)
        )

        # cachePath is deliberately normalized to None on write and stamped by the
        # loader, so it may appear even when the input had none.
        self.assertTrue(set(original.keys()) <= set(restored.keys()))
        self.assertEqual(set(restored.keys()) - set(original.keys()), {"cachePath"})

    def test_round_trip_preserves_pit_visual_geometry(self):
        original = make_geometry()

        restored = fx.deserialize_consolidated_geometry(
            fx.serialize_consolidated_geometry(original)
        )

        self.assertEqual(restored["pitVisualGeometry"], original["pitVisualGeometry"])

    def test_round_trip_preserves_track_point_fields_exactly(self):
        original = make_geometry()

        restored = fx.deserialize_consolidated_geometry(
            fx.serialize_consolidated_geometry(original)
        )

        for before, after in zip(original["centerline"], restored["centerline"]):
            self.assertEqual(asdict(before), asdict(after))

    def test_vertical_coordinate_survives(self):
        """TrackPoint.to_dict() renames y to worldY and puts mapY in "y"; using it
        as the on-disk encoding would silently overwrite y with z."""
        original = make_geometry()

        restored = fx.deserialize_consolidated_geometry(
            fx.serialize_consolidated_geometry(original)
        )

        self.assertEqual(restored["centerline"][0].y, 1.5)
        self.assertEqual(restored["centerline"][1].y, -2.25)
        self.assertNotEqual(restored["centerline"][0].y, restored["centerline"][0].z)

    def test_encoded_payload_is_plain_json(self):
        payload = json.loads(fx.serialize_consolidated_geometry(make_geometry()))

        self.assertIsInstance(payload["centerline"], list)
        self.assertIn("pitVisualGeometry", payload)

    def test_consolidated_file_is_preferred_over_the_cascade(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            target = fx.consolidated_geometry_path(repo)
            target.parent.mkdir(parents=True, exist_ok=True)
            marker = make_geometry()
            marker["provider"] = "ConsolidatedMarker"
            target.write_text(fx.serialize_consolidated_geometry(marker), encoding="utf-8")

            loaded = fx.load_fixed_geometry(repo)

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["provider"], "ConsolidatedMarker")

    def test_no_machine_specific_path_is_baked_into_the_asset(self):
        """The file is shipped to other machines; an absolute path from the
        machine that resolved the cascade would name a file that is not there."""
        geometry = make_geometry()
        geometry["cachePath"] = r"C:\somewhere\data\debug\a_candidate.json"
        geometry["metadata"] = {"cachePath": r"C:\somewhere\data\debug\a_candidate.json"}

        payload = json.loads(fx.serialize_consolidated_geometry(geometry))

        self.assertIsNone(payload["cachePath"])
        self.assertNotIn("cachePath", payload["metadata"])

    def test_loader_stamps_the_path_it_actually_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            target = fx.consolidated_geometry_path(repo)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(fx.serialize_consolidated_geometry(make_geometry()), encoding="utf-8")

            loaded = fx.load_fixed_geometry(repo)

        self.assertEqual(loaded["cachePath"], str(target))
        self.assertEqual(loaded["metadata"]["cachePath"], str(target))

    def test_missing_consolidated_file_falls_back_to_the_cascade(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            # Neither the consolidated file nor the cascade base exists here.
            self.assertIsNone(fx.load_fixed_geometry(repo))


if __name__ == "__main__":
    unittest.main()
