import json
from datetime import datetime
from typing import Dict, Any, List
from ..telemetry.telemetry_models import TrackPoint

class CacheSerializer:
    """Cache round-trip for track geometry.

    to_cache_dict and deserialize_track are two halves of one contract: a key
    the writer omits is gone after the next restart, silently, because the
    reader still has a default for it. That asymmetry has cost real features
    twice -- kerbs and markings reached the geometry but not the renderer
    through to_api_track, and reached the cache file not at all, so on every
    track but Interlagos they appeared once and vanished on reload.
    test_cache_round_trip pins the two halves together.
    """

    @staticmethod
    def to_cache_dict(track_data: Dict[str, Any], source_hash: str = "") -> Dict[str, Any]:
        centerline: List[TrackPoint] = track_data["centerline"]
        return {
            "trackName": track_data.get("trackName", track_data.get("name", "Unknown Track")),
            "trackLength": float(track_data.get("trackLength", track_data.get("track_length", 0.0))),
            "generatedAt": datetime.utcnow().isoformat(),
            "version": int(track_data.get("version", 1)),
            "source": track_data.get("source", "telemetry_reconstruction"),
            "provider": track_data.get("provider"),
            "providerSource": track_data.get("providerSource"),
            "gameCode": track_data.get("gameCode", track_data.get("game_code", "AssettoCorsa")),
            "geometryName": track_data.get("geometryName"),
            "visualGeometryName": track_data.get("visualGeometryName"),
            "renderMode": track_data.get("renderMode"),
            "updatedAt": track_data.get("updatedAt"),
            "trackConfig": track_data.get("trackConfig"),
            "cachePath": track_data.get("cachePath"),
            "sourceHash": source_hash,
            "coordinateSystem": "world_xz",
            "closedLoop": bool(track_data.get("closedLoop", True)),
            "reconstruction": track_data.get("reconstruction", {}),
            "metadata": track_data.get("metadata", {}),
            "validation": track_data.get("validation", {}),
            "asphaltPolygon": track_data.get("asphaltPolygon"),
            "pitVisualGeometry": track_data.get("pitVisualGeometry"),
            "visualCenterline": track_data.get("visualCenterline"),
            "kerbGeometry": track_data.get("kerbGeometry"),
            "markingGeometry": track_data.get("markingGeometry"),
            "centerline": [p.to_dict() for p in centerline],
            "normals": [{"x": float(p.normal[0]), "z": float(p.normal[1])} for p in centerline],
            "curvature": [float(p.curvature) for p in centerline],
            "boundsLeft": track_data.get("boundsLeft", track_data.get("left_edge", [])),
            "boundsRight": track_data.get("boundsRight", track_data.get("right_edge", [])),
            "localWidth": track_data.get("localWidth", []),
            "p": track_data.get("p", []),
            "bounds": track_data.get("bounds", {}),
            "widthMin": track_data.get("widthMin"),
            "widthAvg": track_data.get("widthAvg"),
            "widthMax": track_data.get("widthMax"),
        }

    @staticmethod
    def serialize_track(track_data: Dict[str, Any], source_hash: str = "") -> str:
        return json.dumps(CacheSerializer.to_cache_dict(track_data, source_hash), ensure_ascii=False, indent=2)

    @staticmethod
    def deserialize_track(raw_data: str) -> Dict[str, Any]:
        data = json.loads(raw_data)
        raw_centerline = data.get("centerline", data.get("Centerline", []))

        centerline = [
            TrackPoint(
                x=float(p["x"]),
                y=float(p.get("worldY", 0.0)),
                z=float(p.get("z", p.get("y", 0.0))),
                distance=float(p.get("distance", p.get("dist", 0.0))),
                spline_t=float(p.get("spline_t", p.get("p", 0.0))),
                curvature=float(p.get("curvature", p.get("curv", 0.0))),
                tangent=(
                    float(p.get("tangent", {}).get("x", p.get("tx", 1.0))),
                    float(p.get("tangent", {}).get("z", p.get("ty", 0.0))),
                ),
                normal=(
                    float(p.get("normal", {}).get("x", p.get("nx", 0.0))),
                    float(p.get("normal", {}).get("z", p.get("ny", 1.0))),
                ),
            ) for p in raw_centerline
        ]

        left = data.get("boundsLeft", data.get("BoundsLeft", []))
        right = data.get("boundsRight", data.get("BoundsRight", []))
        track_name = data.get("trackName", data.get("TrackDisplayName", "Unknown Track"))
        track_length = float(data.get("trackLength", data.get("ReportedTrackLength", 0.0)))

        return {
            "name": track_name,
            "trackName": track_name,
            "track_length": track_length,
            "trackLength": track_length,
            "length_meters": track_length,
            "total_points": len(centerline),
            "game_code": data.get("gameCode", data.get("GameCode", "AssettoCorsa")),
            "generatedAt": data.get("generatedAt", data.get("GeneratedAt")),
            "version": data.get("version", 1),
            "reconstruction": data.get("reconstruction", {}),
            "provider": data.get("provider"),
            "providerSource": data.get("providerSource"),
            "geometryName": data.get("geometryName"),
            "visualGeometryName": data.get("visualGeometryName"),
            "renderMode": data.get("renderMode"),
            "updatedAt": data.get("updatedAt"),
            "trackConfig": data.get("trackConfig"),
            "cachePath": data.get("cachePath"),
            "metadata": data.get("metadata", {}),
            "validation": data.get("validation", {}),
            "asphaltPolygon": data.get("asphaltPolygon"),
            "pitVisualGeometry": data.get("pitVisualGeometry"),
            "visualCenterline": data.get("visualCenterline"),
            "kerbGeometry": data.get("kerbGeometry"),
            "markingGeometry": data.get("markingGeometry"),
            "sourceHash": data.get("sourceHash", ""),
            "coordinate_system": data.get("coordinateSystem", "world_xz"),
            "closedLoop": bool(data.get("closedLoop", True)),
            "centerline": centerline,
            "left_edge": left,
            "right_edge": right,
            "boundsLeft": left,
            "boundsRight": right,
            "normals": data.get("normals", [{"x": p.normal[0], "z": p.normal[1]} for p in centerline]),
            "curvature": data.get("curvature", [p.curvature for p in centerline]),
            "source": data.get("source", "telemetry_reconstruction"),
            "localWidth": data.get("localWidth", []),
            "p": data.get("p", []),
            "bounds": data.get("bounds", {}),
            "widthMin": data.get("widthMin"),
            "widthAvg": data.get("widthAvg"),
            "widthMax": data.get("widthMax"),
        }

    @staticmethod
    def to_api_track(track_data: Dict[str, Any]) -> Dict[str, Any]:
        centerline: List[TrackPoint] = track_data.get("centerline", [])
        center = [p.to_dict() if isinstance(p, TrackPoint) else p for p in centerline]
        x = [float(p["x"]) for p in center]
        world_z = [float(p.get("z", p.get("y", 0.0))) for p in center]
        map_y = [-value for value in world_z]

        return {
            "name": track_data.get("name", track_data.get("trackName", "Unknown Track")),
            "trackName": track_data.get("trackName", track_data.get("name", "Unknown Track")),
            "trackLength": float(track_data.get("trackLength", track_data.get("track_length", 0.0))),
            "length_meters": float(track_data.get("length_meters", track_data.get("trackLength", track_data.get("track_length", 0.0)))),
            "total_points": len(center),
            "source": track_data.get("source", "telemetry_reconstruction"),
            "provider": track_data.get("provider"),
            "providerSource": track_data.get("providerSource"),
            "geometryName": track_data.get("geometryName"),
            "visualGeometryName": track_data.get("visualGeometryName"),
            "renderMode": track_data.get("renderMode"),
            "updatedAt": track_data.get("updatedAt"),
            "trackConfig": track_data.get("trackConfig"),
            "cachePath": track_data.get("cachePath"),
            "version": track_data.get("version", 1),
            "reconstruction": track_data.get("reconstruction", {}),
            "metadata": track_data.get("metadata", {}),
            "validation": track_data.get("validation", {}),
            "asphaltPolygon": track_data.get("asphaltPolygon"),
            "pitVisualGeometry": track_data.get("pitVisualGeometry"),
            "kerbGeometry": track_data.get("kerbGeometry"),
            "markingGeometry": track_data.get("markingGeometry"),
            "visualCenterline": CacheSerializer._visual_centerline_to_arrays(track_data.get("visualCenterline")),
            "generatedAt": track_data.get("generatedAt"),
            "coordinateSystem": "map_xy_from_world_x_negative_z",
            "closedLoop": bool(track_data.get("closedLoop", True)),
            "centerline": {
                "x": x,
                "y": map_y,
                "z": world_z,
                "distance": [float(p.get("distance", 0.0)) for p in center],
                "spline_t": [float(p.get("spline_t", 0.0)) for p in center],
                "curvature": [float(p.get("curvature", 0.0)) for p in center],
            },
            "points": center,
            "normals": track_data.get("normals", [{"x": p.normal[0], "z": p.normal[1]} for p in centerline]),
            "curvature": track_data.get("curvature", [p.curvature for p in centerline]),
            "left_edge": CacheSerializer._edge_to_arrays(track_data.get("left_edge", track_data.get("boundsLeft", []))),
            "right_edge": CacheSerializer._edge_to_arrays(track_data.get("right_edge", track_data.get("boundsRight", []))),
            "boundsLeft": track_data.get("boundsLeft", track_data.get("left_edge", [])),
            "boundsRight": track_data.get("boundsRight", track_data.get("right_edge", [])),
            "localWidth": track_data.get("localWidth", []),
            "p": track_data.get("p", []),
            "bounds": track_data.get("bounds", {}),
            "widthMin": track_data.get("widthMin"),
            "widthAvg": track_data.get("widthAvg"),
            "widthMax": track_data.get("widthMax"),
        }

    @staticmethod
    def _edge_to_arrays(edge: List[Dict[str, Any]]) -> Dict[str, List[float]]:
        x = [float(p["x"]) for p in edge]
        world_z = [float(p.get("z", p.get("y", 0.0))) for p in edge]
        return {
            "x": x,
            "y": [-value for value in world_z],
            "z": world_z,
        }

    @staticmethod
    def _visual_centerline_to_arrays(visual: Any) -> Any:
        if not visual:
            return None
        if isinstance(visual, dict) and "x" in visual:
            x = [float(value) for value in visual.get("x", [])]
            y = [float(value) for value in visual.get("y", [])]
            return {"x": x, "y": y, "z": [-value for value in y]}
        points = visual.get("points", []) if isinstance(visual, dict) else visual
        if not isinstance(points, list):
            return None
        x = [float(point[0]) for point in points]
        y = [float(point[1]) for point in points]
        return {"x": x, "y": y, "z": [-value for value in y]}
