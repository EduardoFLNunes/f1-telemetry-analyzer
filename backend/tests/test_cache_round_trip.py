import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.cache.cache_serializer import CacheSerializer  # noqa: E402
from core.telemetry.telemetry_models import TrackPoint  # noqa: E402


def full_track():
    """Every field a built track carries, so an omission on either side shows up."""
    centerline = [
        TrackPoint(x=float(i), y=3.5 + i, z=float(-i), distance=float(i), spline_t=i / 4,
                   curvature=0.01 * i, tangent=(1.0, 0.0), normal=(0.0, 1.0))
        for i in range(4)
    ]
    edge = [{"x": float(i), "y": float(-i), "z": float(-i)} for i in range(4)]
    return {
        "trackName": "vhe_interlagos",
        "name": "vhe_interlagos",
        "trackLength": 4345.9,
        "version": 2,
        "source": "assetto_corsa_track_files",
        "provider": "kn5_surface_interval",
        "providerSource": "assetto_corsa_track_files",
        "game_code": "AssettoCorsa",
        "geometryName": "SomeGeometry",
        "visualGeometryName": "SomeVisualGeometry",
        "renderMode": "visual_pit_access_asphalt_merge_fix",
        "updatedAt": "2026-08-09T00:00:00",
        "trackConfig": "gp",
        "cachePath": "C:/cache/track.json",
        "closedLoop": True,
        "reconstruction": {"method": "kn5_surface_interval"},
        "metadata": {"widthSource": "kn5_surface_interval.localWidth"},
        "validation": {"passed": True},
        "asphaltPolygon": {"points": [[0.0, 0.0]], "x": [0.0], "y": [0.0]},
        "pitVisualGeometry": {"name": "PitVisual", "geometries": {"corridor": {"width": [7.5]}}},
        "visualCenterline": {"points": [[0.0, 0.0]], "x": [0.0], "y": [0.0]},
        "kerbGeometry": {"polygons": [{"rings": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]]]}]},
        "markingGeometry": {"polygons": [{"rings": [[[0.0, 6.0], [1.0, 6.0]]]}]},
        "centerline": centerline,
        "boundsLeft": edge,
        "boundsRight": edge,
        "localWidth": [12.0, 12.5, 13.0, 12.2],
        "p": [0.0, 0.25, 0.5, 0.75],
        "bounds": {"minX": 0.0, "maxX": 3.0},
        "widthMin": 12.0,
        "widthAvg": 12.425,
        "widthMax": 13.0,
    }


class CacheRoundTripTests(unittest.TestCase):
    """to_cache_dict and deserialize_track are two halves of one contract.

    A key the writer omits is gone after the next restart, and silently, because
    the reader still has a default for it.
    """

    def round_trip(self, track):
        return CacheSerializer.deserialize_track(CacheSerializer.serialize_track(track))

    def test_decoration_survives_a_restart(self):
        """Kerbs and markings reached the geometry and the renderer but never the
        cache file, so on every track but Interlagos they were drawn once and
        vanished on reload."""
        original = full_track()

        restored = self.round_trip(original)

        self.assertEqual(restored["kerbGeometry"], original["kerbGeometry"])
        self.assertEqual(restored["markingGeometry"], original["markingGeometry"])

    def test_every_field_the_reader_understands_is_written(self):
        original = full_track()

        restored = self.round_trip(original)

        # generatedAt is stamped at write time and sourceHash is an argument, so
        # neither can come from the input.
        skip = {"generatedAt", "sourceHash", "name", "game_code", "centerline",
                "boundsLeft", "boundsRight"}
        for key, value in original.items():
            if key in skip:
                continue
            self.assertIn(key, restored, f"{key} is not read back")
            self.assertEqual(restored[key], value, f"{key} did not survive the round trip")

    def test_visual_geometry_survives(self):
        original = full_track()

        restored = self.round_trip(original)

        self.assertEqual(restored["pitVisualGeometry"], original["pitVisualGeometry"])
        self.assertEqual(restored["asphaltPolygon"], original["asphaltPolygon"])
        self.assertEqual(restored["renderMode"], original["renderMode"])

    def test_centerline_vertical_coordinate_survives(self):
        """to_dict renames y to worldY and puts map y in y; reading the wrong one
        silently flattens every elevation in the track."""
        original = full_track()

        restored = self.round_trip(original)

        self.assertEqual([p.y for p in restored["centerline"]],
                         [p.y for p in original["centerline"]])
        self.assertEqual([p.z for p in restored["centerline"]],
                         [p.z for p in original["centerline"]])

    def test_a_cache_written_before_the_fix_is_rebuilt(self):
        """Fixing the writer does not fix files already on disk: they load with
        the keys missing and the map stays bare until the track is rebuilt."""
        from core.geometry.track_geometry_provider import _cache_predates_decoration

        old = dict(full_track())
        old.pop("kerbGeometry")
        old.pop("markingGeometry")

        self.assertTrue(_cache_predates_decoration(self.round_trip(old)))
        self.assertFalse(_cache_predates_decoration(self.round_trip(full_track())))

    def test_a_track_with_nothing_painted_is_not_mistaken_for_an_old_cache(self):
        from core.geometry.track_geometry_provider import _cache_predates_decoration

        bare = dict(full_track())
        bare["kerbGeometry"] = {"polygons": []}
        bare["markingGeometry"] = {"polygons": []}

        self.assertFalse(_cache_predates_decoration(self.round_trip(bare)))

    def test_api_payload_carries_the_decoration_too(self):
        """The API whitelist is a third place the same omission can happen."""
        original = full_track()

        payload = CacheSerializer.to_api_track(self.round_trip(original))

        self.assertEqual(payload["kerbGeometry"], original["kerbGeometry"])
        self.assertEqual(payload["markingGeometry"], original["markingGeometry"])


if __name__ == "__main__":
    unittest.main()
