import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.cache.track_cache import TrackCache
from core.geometry.track_geometry_provider import (
    apply_track_visual_geometry,
    track_visual_geometry_config,
)


TRACK_CACHE_DIR = REPO_ROOT / "data" / "cache" / "tracks"
DEBUG_DIR = REPO_ROOT / "data" / "debug"
TRACK_CACHE_NAME = "vhe_interlagos_gp_kn5_surface_interval_cleaned_geometry"


Point = List[float]


def edge_to_map(edge: Sequence[Dict[str, Any]]) -> List[Point]:
    return [[float(point["x"]), -float(point.get("z", point.get("y", 0.0)))] for point in edge]


def track_to_map(track: Dict[str, Any]) -> Dict[str, Any]:
    centerline = [[float(point.x), -float(point.z)] for point in track.get("centerline", [])]
    return {
        "centerline": centerline,
        "leftEdge": edge_to_map(track.get("boundsLeft", [])),
        "rightEdge": edge_to_map(track.get("boundsRight", [])),
        "localWidth": [float(width) for width in track.get("localWidth", [])],
        "p": [float(value) for value in track.get("p", [])],
    }


def visual_to_map(visual: Dict[str, Any]) -> Dict[str, Any]:
    left = visual.get("leftEdge") or visual.get("left_edge") or {}
    right = visual.get("rightEdge") or visual.get("right_edge") or {}
    return {
        "centerline": list(zip(visual["centerline"]["x"], visual["centerline"]["y"])),
        "leftEdge": list(zip(left["x"], left["y"])),
        "rightEdge": list(zip(right["x"], right["y"])),
        "localWidth": visual.get("width") or visual.get("localWidth", []),
    }


def bounds_for(*series: Sequence[Sequence[float]]) -> Dict[str, float]:
    points = [point for points in series for point in points]
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return {
        "minX": min(xs),
        "maxX": max(xs),
        "minY": min(ys),
        "maxY": max(ys),
    }


def make_projector(bounds: Dict[str, float], width: int = 1400, height: int = 1000) -> Callable[[Sequence[float]], Point]:
    margin = 44
    span_x = max(bounds["maxX"] - bounds["minX"], 1)
    span_y = max(bounds["maxY"] - bounds["minY"], 1)
    scale = min((width - margin * 2) / span_x, (height - margin * 2) / span_y)
    offset_x = (width - span_x * scale) * 0.5
    offset_y = (height - span_y * scale) * 0.5

    def project(point: Sequence[float]) -> Point:
        return [
            offset_x + (float(point[0]) - bounds["minX"]) * scale,
            offset_y + (bounds["maxY"] - float(point[1])) * scale,
        ]

    return project


def polyline(points: Sequence[Sequence[float]], project: Callable[[Sequence[float]], Point], color: str, width: float, opacity: float = 1.0) -> str:
    if not points:
        return ""
    coords = " ".join(f"{project(point)[0]:.2f},{project(point)[1]:.2f}" for point in points)
    return f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="{width}" opacity="{opacity}" stroke-linecap="round" stroke-linejoin="round" />'


def polygon(left: Sequence[Sequence[float]], right: Sequence[Sequence[float]], project: Callable[[Sequence[float]], Point], fill: str, opacity: float = 1.0) -> str:
    points = list(left) + list(reversed(right))
    coords = " ".join(f"{project(point)[0]:.2f},{project(point)[1]:.2f}" for point in points)
    return f'<polygon points="{coords}" fill="{fill}" opacity="{opacity}" />'


def artifact_markers(artifacts: Sequence[Dict[str, Any]], physics: Dict[str, Any], project: Callable[[Sequence[float]], Point]) -> List[str]:
    markers = []
    for artifact in artifacts:
        index = int(artifact["index"])
        edge = physics["leftEdge"] if artifact["edge"] == "left" else physics["rightEdge"]
        if index >= len(edge):
            continue
        x, y = project(edge[index])
        color = "#ff3158" if artifact["edge"] == "left" else "#ffb000"
        markers.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4.2" fill="{color}" opacity="0.82"><title>{artifact["edge"]} {index} {artifact["reason"]}</title></circle>')
    return markers


def removed_artifact_markers(artifacts: Sequence[Dict[str, Any]], physics: Dict[str, Any], project: Callable[[Sequence[float]], Point]) -> List[str]:
    markers = []
    for artifact in artifacts:
        index = int(artifact["index"])
        edge = physics["leftEdge"] if artifact["edge"] == "left" else physics["rightEdge"]
        if index >= len(edge):
            continue
        x, y = project(edge[index])
        markers.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5.2" fill="none" stroke="#34d399" stroke-width="1.8" opacity="0.9">'
            f'<title>removed {artifact["edge"]} {index} {artifact["reason"]}</title></circle>'
        )
    return markers


def write_svg(path: Path, title: str, body: Sequence[str], width: int = 1400, height: int = 1000) -> None:
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#060911" />',
        f'<text x="32" y="34" fill="#d9e6f2" font-family="Segoe UI, Arial" font-size="16">{title}</text>',
        *body,
        "</svg>",
    ]
    path.write_text("\n".join(svg), encoding="utf-8")


def main() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    cache = TrackCache(cache_dir=str(TRACK_CACHE_DIR))
    track = cache.load_track(TRACK_CACHE_NAME)
    if not track:
        raise SystemExit(f"Missing cache: {TRACK_CACHE_NAME}")
    visual_cfg = track_visual_geometry_config()
    track = apply_track_visual_geometry(track, config=visual_cfg)
    cache.save_track(TRACK_CACHE_NAME, track)

    physics = track_to_map(track)
    visual = visual_to_map(track["visualGeometry"])
    artifact_report = track["visualGeometry"]["artifactReport"]
    visual_artifact_report = track["visualGeometry"].get("visualArtifactReport", {})
    artifacts = artifact_report.get("artifacts", [])
    removed_artifacts = track["visualGeometry"].get("artifactsRemoved", [])
    report = {
        "trackName": track.get("trackName"),
        "trackConfig": track.get("trackConfig"),
        "physicsSource": "kn5_surface_interval_physics",
        "visualGeometrySource": track["visualGeometry"].get("source"),
        "visualMethod": track["visualGeometry"].get("method"),
        "visualGeometryEnabled": True,
        "config": track["visualGeometry"].get("config"),
        "metadata": track["visualGeometry"].get("metadata"),
        "artifactCount": len(artifacts),
        "summary": artifact_report.get("summary", {}),
        "visualArtifactReport": visual_artifact_report,
        "removedSpikeCount": track["visualGeometry"].get("removedSpikeCount"),
        "maxWidthDeltaBefore": track["visualGeometry"].get("maxWidthDeltaBefore"),
        "maxWidthDeltaAfter": track["visualGeometry"].get("maxWidthDeltaAfter"),
        "artifacts": artifacts,
    }

    (DEBUG_DIR / "track_visual_edge_artifacts_vhe_interlagos.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (DEBUG_DIR / "track_visual_width_profile.json").write_text(
        json.dumps(
            {
                "trackName": track.get("trackName"),
                "trackConfig": track.get("trackConfig"),
                "physicsWidthStats": {
                    "min": track.get("widthMin"),
                    "avg": track.get("widthAvg"),
                    "max": track.get("widthMax"),
                },
                "visualWidthStats": {
                    "min": track["visualGeometry"].get("widthMin"),
                    "avg": track["visualGeometry"].get("widthAvg"),
                    "max": track["visualGeometry"].get("widthMax"),
                },
                "maxWidthDeltaBefore": track["visualGeometry"].get("maxWidthDeltaBefore"),
                "maxWidthDeltaAfter": track["visualGeometry"].get("maxWidthDeltaAfter"),
                "profile": track["visualGeometry"].get("widthProfile", []),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (DEBUG_DIR / "track_visual_artifacts_removed.json").write_text(
        json.dumps(
            {
                "trackName": track.get("trackName"),
                "trackConfig": track.get("trackConfig"),
                "removedSpikeCount": track["visualGeometry"].get("removedSpikeCount"),
                "maxWidthDeltaBefore": track["visualGeometry"].get("maxWidthDeltaBefore"),
                "maxWidthDeltaAfter": track["visualGeometry"].get("maxWidthDeltaAfter"),
                "artifactsRemoved": removed_artifacts,
                "artifactCountBefore": artifact_report.get("artifactCount"),
                "artifactCountAfter": visual_artifact_report.get("artifactCount"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    all_bounds = bounds_for(physics["leftEdge"], physics["rightEdge"], visual["leftEdge"], visual["rightEdge"])
    project = make_projector(all_bounds)

    write_svg(
        DEBUG_DIR / "track_visual_geometry_preview.svg",
        "TrackVisualGeometry preview",
        [
            polygon(visual["leftEdge"], visual["rightEdge"], project, "#202838", 0.94),
            polyline(physics["leftEdge"], project, "#94a3b8", 0.8, 0.28),
            polyline(physics["rightEdge"], project, "#94a3b8", 0.8, 0.28),
            polyline(visual["leftEdge"], project, "#38bdf8", 1.6, 0.9),
            polyline(visual["rightEdge"], project, "#36f3a5", 1.6, 0.9),
            polyline(visual["centerline"], project, "#f8fafc", 0.8, 0.34),
            *removed_artifact_markers(removed_artifacts, physics, project),
        ],
    )
    write_svg(
        DEBUG_DIR / "track_physics_vs_visual_geometry.svg",
        "Physics geometry vs visual geometry",
        [
            polygon(visual["leftEdge"], visual["rightEdge"], project, "#202838", 0.72),
            polyline(physics["leftEdge"], project, "#ff3158", 0.85, 0.42),
            polyline(physics["rightEdge"], project, "#ffb000", 0.85, 0.42),
            polyline(visual["leftEdge"], project, "#38bdf8", 1.7, 0.9),
            polyline(visual["rightEdge"], project, "#36f3a5", 1.7, 0.9),
            polyline(physics["centerline"], project, "#f8fafc", 0.75, 0.25),
            *removed_artifact_markers(removed_artifacts, physics, project),
        ],
    )
    write_svg(
        DEBUG_DIR / "track_visual_edge_artifacts.svg",
        "Detected visual edge artifacts on physics edges",
        [
            polygon(visual["leftEdge"], visual["rightEdge"], project, "#202838", 0.56),
            polyline(physics["leftEdge"], project, "#ff3158", 0.9, 0.46),
            polyline(physics["rightEdge"], project, "#ffb000", 0.9, 0.46),
            polyline(visual["leftEdge"], project, "#38bdf8", 1.4, 0.9),
            polyline(visual["rightEdge"], project, "#36f3a5", 1.4, 0.9),
            *artifact_markers(artifacts, physics, project),
        ],
    )

    print(
        json.dumps(
            {
                "artifactReport": str(DEBUG_DIR / "track_visual_edge_artifacts_vhe_interlagos.json"),
                "visualPreview": str(DEBUG_DIR / "track_visual_geometry_preview.svg"),
                "physicsVsVisual": str(DEBUG_DIR / "track_physics_vs_visual_geometry.svg"),
                "artifactsSvg": str(DEBUG_DIR / "track_visual_edge_artifacts.svg"),
                "widthProfile": str(DEBUG_DIR / "track_visual_width_profile.json"),
                "artifactsRemoved": str(DEBUG_DIR / "track_visual_artifacts_removed.json"),
                "artifactCount": len(artifacts),
                "removedSpikeCount": track["visualGeometry"].get("removedSpikeCount"),
                "maxWidthDeltaBefore": track["visualGeometry"].get("maxWidthDeltaBefore"),
                "maxWidthDeltaAfter": track["visualGeometry"].get("maxWidthDeltaAfter"),
                "visualWidthMin": track["visualGeometry"].get("widthMin"),
                "visualWidthAvg": track["visualGeometry"].get("widthAvg"),
                "visualWidthMax": track["visualGeometry"].get("widthMax"),
                "visualArtifactCountAfterBuild": track["visualGeometry"].get("visualArtifactReport", {}).get("artifactCount"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
