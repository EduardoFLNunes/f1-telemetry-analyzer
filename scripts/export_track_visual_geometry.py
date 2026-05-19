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
    build_visual_reference_track_from_manifest,
    track_geometry_cleanup_config,
    track_visual_geometry_config,
)
from core.geometry.track_visual_geometry import build_visual_geometry_v3_candidate
from core.track_file_resolver import TrackFileResolver


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


def ribbon_to_map(visual: Dict[str, Any]) -> Dict[str, Any]:
    ribbon = visual.get("visualRibbonGeometry") or {}
    center = ribbon.get("centerline") or {}
    return {
        "centerline": list(zip(center.get("x", []), center.get("y", []))),
        "width": float(ribbon.get("ribbonWidthMeters") or ribbon.get("width") or 0.0),
        "bounds": ribbon.get("bounds") or {},
        "metadata": ribbon.get("metadata") or {},
    }


def series_to_points(series: Dict[str, Any]) -> List[Point]:
    if not series:
        return []
    return [[float(x), float(y)] for x, y in zip(series.get("x", []), series.get("y", []))]


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

    project.scale = scale  # type: ignore[attr-defined]
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


def ribbon_stroke(
    centerline: Sequence[Sequence[float]],
    width_meters: float,
    project: Callable[[Sequence[float]], Point],
    color: str,
    *,
    opacity: float = 1.0,
    width_offset_meters: float = 0.0,
) -> str:
    if not centerline:
        return ""
    coords = " ".join(f"{project(point)[0]:.2f},{project(point)[1]:.2f}" for point in centerline)
    scale = float(getattr(project, "scale", 1.0))
    stroke_width = max(1.0, (float(width_meters) + float(width_offset_meters)) * scale)
    return (
        f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="{stroke_width:.2f}" '
        f'opacity="{opacity}" stroke-linecap="round" stroke-linejoin="round" />'
    )


def smooth_ribbon_stroke(
    centerline: Sequence[Sequence[float]],
    width_meters: float,
    project: Callable[[Sequence[float]], Point],
    color: str,
    *,
    opacity: float = 1.0,
    width_offset_meters: float = 0.0,
) -> str:
    if len(centerline) < 3:
        return ribbon_stroke(centerline, width_meters, project, color, opacity=opacity, width_offset_meters=width_offset_meters)
    points = [project(point) for point in centerline]
    tension = 0.72
    parts = [f"M {points[0][0]:.2f},{points[0][1]:.2f}"]
    count = len(points)
    for index in range(count):
        p0 = points[(index - 1) % count]
        p1 = points[index]
        p2 = points[(index + 1) % count]
        p3 = points[(index + 2) % count]
        cp1 = [p1[0] + (p2[0] - p0[0]) * tension / 6.0, p1[1] + (p2[1] - p0[1]) * tension / 6.0]
        cp2 = [p2[0] - (p3[0] - p1[0]) * tension / 6.0, p2[1] - (p3[1] - p1[1]) * tension / 6.0]
        parts.append(f"C {cp1[0]:.2f},{cp1[1]:.2f} {cp2[0]:.2f},{cp2[1]:.2f} {p2[0]:.2f},{p2[1]:.2f}")
    scale = float(getattr(project, "scale", 1.0))
    stroke_width = max(1.0, (float(width_meters) + float(width_offset_meters)) * scale)
    return (
        f'<path d="{" ".join(parts)} Z" fill="none" stroke="{color}" stroke-width="{stroke_width:.2f}" '
        f'opacity="{opacity}" stroke-linecap="round" stroke-linejoin="round" />'
    )


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


def centerline_artifact_markers(
    artifacts: Sequence[Dict[str, Any]],
    centerline: Sequence[Sequence[float]],
    project: Callable[[Sequence[float]], Point],
) -> List[str]:
    markers = []
    for artifact in artifacts[:80]:
        index = int(artifact["index"])
        if index >= len(centerline):
            continue
        x, y = project(centerline[index])
        markers.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4.4" fill="#f43f5e" opacity="0.92">'
            f'<title>centerline {index} {artifact.get("reason", "")}</title></circle>'
        )
    return markers


def local_deformation_markers(
    records: Sequence[Dict[str, Any]],
    points: Sequence[Sequence[float]],
    project: Callable[[Sequence[float]], Point],
    *,
    fill: str = "#facc15",
    radius: float = 4.2,
    limit: int = 120,
) -> List[str]:
    markers = []
    for record in records[:limit]:
        index = int(record["index"])
        if index >= len(points):
            continue
        x, y = project(points[index])
        markers.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius}" fill="{fill}" opacity="0.9">'
            f'<title>local deformation {index} {record.get("reason", "")}</title></circle>'
        )
    return markers


def local_repair_markers(
    records: Sequence[Dict[str, Any]],
    project: Callable[[Sequence[float]], Point],
    *,
    fill: str = "#facc15",
    radius: float = 4.8,
    limit: int = 220,
) -> List[str]:
    markers = []
    for record in records[:limit]:
        position = record.get("newPosition") or record.get("position")
        if not position:
            continue
        x, y = project(position)
        markers.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius}" fill="{fill}" stroke="#111827" stroke-width="1.2" opacity="0.95">'
            f'<title>repair {record.get("index")} displacement={record.get("displacement")}</title></circle>'
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
    cleanup_cfg = track_geometry_cleanup_config()
    visual_reference = None
    if visual_cfg.get("useRoadOnly", False):
        try:
            manifest = TrackFileResolver().build_track_file_manifest(
                track.get("trackName", "vhe_interlagos"),
                track.get("trackConfig", "gp"),
                source="assetto_corsa",
                game_code="assetto_corsa",
            )
            visual_reference = build_visual_reference_track_from_manifest(
                manifest.to_dict(),
                visual_config=visual_cfg,
                target_spacing=float(cleanup_cfg["targetSpacingMeters"]),
                smoothing_window=int(cleanup_cfg["smoothingWindow"]),
            )
        except Exception as exc:
            print(f"ROAD-only visual reference unavailable: {exc}", file=sys.stderr)
    track = apply_track_visual_geometry(track, config=visual_cfg, visual_reference_track=visual_reference)
    cache.save_track(TRACK_CACHE_NAME, track)

    physics = track_to_map(track)
    visual = visual_to_map(track["visualGeometry"])
    ribbon = ribbon_to_map(track["visualGeometry"])
    visual_v3_cfg = {
        **visual_cfg,
        "localRepairEnabled": True,
    }
    visual_v3_geometry = build_visual_geometry_v3_candidate(
        track["visualGeometry"],
        physics["p"],
        config=visual_v3_cfg,
    )
    visual_v3 = visual_to_map(visual_v3_geometry)
    local_deformation_report = visual_v3_geometry.get("localDeformationReport", {})
    local_repair_report = visual_v3_geometry.get("localRepairReport", {})
    local_deformation_artifacts = local_deformation_report.get("artifacts", [])
    local_deformation_top_suspects = local_deformation_report.get("topSuspects", [])
    local_repaired_points = local_repair_report.get("points", [])
    debug_geometry = track["visualGeometry"].get("debugGeometry") or {}
    pre_smoothing_centerline = series_to_points(debug_geometry.get("preSmoothingCenterline") or {})
    if not pre_smoothing_centerline:
        pre_smoothing_centerline = physics["centerline"]
    artifact_report = track["visualGeometry"]["artifactReport"]
    visual_artifact_report = track["visualGeometry"].get("visualArtifactReport", {})
    centerline_artifact_report = track["visualGeometry"].get("centerlineArtifactReport", {})
    centerline_artifact_report_after = track["visualGeometry"].get("centerlineArtifactReportAfter", {})
    artifacts = artifact_report.get("artifacts", [])
    centerline_artifacts = centerline_artifact_report.get("artifacts", [])
    removed_artifacts = track["visualGeometry"].get("artifactsRemoved", [])
    report = {
        "trackName": track.get("trackName"),
        "trackConfig": track.get("trackConfig"),
        "physicsSource": "kn5_surface_interval_physics",
        "visualGeometrySource": track["visualGeometry"].get("source"),
        "visualGeometrySourceMode": track["visualGeometry"].get("visualSource"),
        "visualMethod": track["visualGeometry"].get("method"),
        "visualVersion": track["visualGeometry"].get("visualVersion"),
        "visualRenderMode": track["visualGeometry"].get("visualRenderMode"),
        "ribbonWidthMeters": track["visualGeometry"].get("ribbonWidthMeters"),
        "centerlineMaxDisplacement": track["visualGeometry"].get("centerlineMaxDisplacement"),
        "physicsUnaffected": track["visualGeometry"].get("physicsUnaffected"),
        "visualArtifactFixEnabled": track["visualGeometry"].get("visualArtifactFixEnabled"),
        "falseCurveArtifactsRemoved": track["visualGeometry"].get("falseCurveArtifactsRemoved"),
        "centerlineSmoothingEnabled": track["visualGeometry"].get("centerlineSmoothingEnabled"),
        "normalRecomputed": track["visualGeometry"].get("normalRecomputed"),
        "centerlineArtifactsDetected": track["visualGeometry"].get("centerlineArtifactsDetected"),
        "centerlineArtifactsReduced": track["visualGeometry"].get("centerlineArtifactsReduced"),
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
        "falseCurveReport": track["visualGeometry"].get("falseCurveReport"),
        "falseCurveReportAfter": track["visualGeometry"].get("falseCurveReportAfter"),
        "centerlineArtifactReport": centerline_artifact_report,
        "centerlineArtifactReportAfter": centerline_artifact_report_after,
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
    (DEBUG_DIR / "track_visual_false_curves_report.json").write_text(
        json.dumps(
            {
                "trackName": track.get("trackName"),
                "trackConfig": track.get("trackConfig"),
                "visualSource": track["visualGeometry"].get("visualSource"),
                "visualArtifactFixEnabled": track["visualGeometry"].get("visualArtifactFixEnabled"),
                "falseCurveArtifactsRemoved": track["visualGeometry"].get("falseCurveArtifactsRemoved"),
                "before": track["visualGeometry"].get("falseCurveReport"),
                "after": track["visualGeometry"].get("falseCurveReportAfter"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (DEBUG_DIR / "track_visual_centerline_artifacts.json").write_text(
        json.dumps(
            {
                "trackName": track.get("trackName"),
                "trackConfig": track.get("trackConfig"),
                "visualVersion": track["visualGeometry"].get("visualVersion"),
                "centerlineSmoothingEnabled": track["visualGeometry"].get("centerlineSmoothingEnabled"),
                "normalRecomputed": track["visualGeometry"].get("normalRecomputed"),
                "centerlineArtifactsDetected": track["visualGeometry"].get("centerlineArtifactsDetected"),
                "centerlineArtifactsReduced": track["visualGeometry"].get("centerlineArtifactsReduced"),
                "before": centerline_artifact_report,
                "after": centerline_artifact_report_after,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (DEBUG_DIR / "track_visual_ribbon_metrics.json").write_text(
        json.dumps(
            {
                "trackName": track.get("trackName"),
                "trackConfig": track.get("trackConfig"),
                "visualVersion": track["visualGeometry"].get("visualVersion"),
                "visualRenderMode": track["visualGeometry"].get("visualRenderMode"),
                "renderMode": (track["visualGeometry"].get("visualRibbonGeometry") or {}).get("renderMode"),
                "ribbonWidthMeters": track["visualGeometry"].get("ribbonWidthMeters"),
                "centerlineMaxDisplacement": track["visualGeometry"].get("centerlineMaxDisplacement"),
                "physicsUnaffected": track["visualGeometry"].get("physicsUnaffected"),
                "ribbonPointCount": len(ribbon["centerline"]),
                "polygonPointCount": len(visual["centerline"]),
                "ribbonMetadata": ribbon.get("metadata"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (DEBUG_DIR / "track_visual_local_deformation_report.json").write_text(
        json.dumps(
            {
                "trackName": track.get("trackName"),
                "trackConfig": track.get("trackConfig"),
                "visualVersionBefore": track["visualGeometry"].get("visualVersion"),
                "visualVersionCandidate": visual_v3_geometry.get("visualVersion"),
                "localRepairEnabled": visual_v3_geometry.get("localRepairEnabled"),
                "localDeformationsDetected": visual_v3_geometry.get("localDeformationsDetected"),
                "localDeformationsRepaired": visual_v3_geometry.get("localDeformationsRepaired"),
                "localDeformationsRemaining": visual_v3_geometry.get("localDeformationsRemaining"),
                "maxRepairDisplacement": visual_v3_geometry.get("maxRepairDisplacement"),
                "avgRepairDisplacement": visual_v3_geometry.get("avgRepairDisplacement"),
                "config": visual_v3_geometry.get("config"),
                "report": local_deformation_report,
                "reportAfter": visual_v3_geometry.get("localDeformationReportAfter"),
                "repairReport": local_repair_report,
                "top100Suspects": local_deformation_top_suspects,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    all_bounds = bounds_for(
        physics["leftEdge"],
        physics["rightEdge"],
        visual["leftEdge"],
        visual["rightEdge"],
        visual_v3["leftEdge"],
        visual_v3["rightEdge"],
        ribbon["centerline"],
        pre_smoothing_centerline,
    )
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
        DEBUG_DIR / "track_visual_centerline_before_after.svg",
        "TrackVisualGeometry v2 centerline before/after",
        [
            polyline(physics["centerline"], project, "#94a3b8", 1.0, 0.45),
            polyline(pre_smoothing_centerline, project, "#ef4444", 1.2, 0.72),
            polyline(visual["centerline"], project, "#22c55e", 1.8, 0.95),
            *centerline_artifact_markers(centerline_artifacts, physics["centerline"], project),
        ],
    )
    write_svg(
        DEBUG_DIR / "track_visual_geometry_v2_preview.svg",
        "TrackVisualGeometry v2 preview",
        [
            polygon(visual["leftEdge"], visual["rightEdge"], project, "#202838", 0.94),
            polyline(physics["centerline"], project, "#94a3b8", 0.7, 0.28),
            polyline(visual["leftEdge"], project, "#38bdf8", 1.8, 0.94),
            polyline(visual["rightEdge"], project, "#36f3a5", 1.8, 0.94),
            polyline(visual["centerline"], project, "#f8fafc", 0.8, 0.32),
            *centerline_artifact_markers(centerline_artifacts, physics["centerline"], project),
        ],
    )
    write_svg(
        DEBUG_DIR / "track_physics_vs_visual_v2.svg",
        "Physics vs visual v2",
        [
            polygon(visual["leftEdge"], visual["rightEdge"], project, "#202838", 0.74),
            polyline(physics["leftEdge"], project, "#94a3b8", 0.8, 0.34),
            polyline(physics["rightEdge"], project, "#94a3b8", 0.8, 0.34),
            polyline(pre_smoothing_centerline, project, "#ef4444", 0.9, 0.48),
            polyline(visual["leftEdge"], project, "#38bdf8", 1.8, 0.96),
            polyline(visual["rightEdge"], project, "#36f3a5", 1.8, 0.96),
            polyline(visual["centerline"], project, "#f8fafc", 0.85, 0.38),
            *centerline_artifact_markers(centerline_artifacts, physics["centerline"], project),
        ],
    )
    write_svg(
        DEBUG_DIR / "track_visual_ribbon_preview.svg",
        "TrackVisualRibbon preview",
        [
            smooth_ribbon_stroke(ribbon["centerline"], ribbon["width"], project, "rgba(148,163,184,0.62)", opacity=0.82, width_offset_meters=1.35),
            smooth_ribbon_stroke(ribbon["centerline"], ribbon["width"], project, "#202838", opacity=0.96),
            polyline(ribbon["centerline"], project, "#38bdf8", 0.8, 0.55),
            polyline(physics["leftEdge"], project, "#94a3b8", 0.55, 0.18),
            polyline(physics["rightEdge"], project, "#94a3b8", 0.55, 0.18),
        ],
    )
    write_svg(
        DEBUG_DIR / "track_visual_polygon_vs_ribbon.svg",
        "TrackVisual polygon v2 vs ribbon",
        [
            polygon(visual["leftEdge"], visual["rightEdge"], project, "#ef4444", 0.24),
            polyline(visual["leftEdge"], project, "#ef4444", 0.8, 0.54),
            polyline(visual["rightEdge"], project, "#ef4444", 0.8, 0.54),
            smooth_ribbon_stroke(ribbon["centerline"], ribbon["width"], project, "rgba(34,197,94,0.38)", opacity=0.9, width_offset_meters=1.2),
            smooth_ribbon_stroke(ribbon["centerline"], ribbon["width"], project, "#202838", opacity=0.78),
            polyline(ribbon["centerline"], project, "#22c55e", 1.4, 0.92),
            polyline(physics["centerline"], project, "#94a3b8", 0.65, 0.32),
        ],
    )
    write_svg(
        DEBUG_DIR / "track_visual_local_deformation_report.svg",
        "TrackVisualGeometry local deformation report",
        [
            polygon(visual["leftEdge"], visual["rightEdge"], project, "#202838", 0.58),
            polyline(physics["leftEdge"], project, "#94a3b8", 0.8, 0.24),
            polyline(physics["rightEdge"], project, "#94a3b8", 0.8, 0.24),
            polyline(visual["centerline"], project, "#ef4444", 1.1, 0.74),
            polyline(visual_v3["centerline"], project, "#22c55e", 1.7, 0.96),
            *local_deformation_markers(local_deformation_top_suspects, visual["centerline"], project, fill="#fb7185", radius=3.6, limit=100),
            *local_repair_markers(local_repaired_points, project),
        ],
    )
    write_svg(
        DEBUG_DIR / "track_visual_geometry_v3_preview.svg",
        "TrackVisualGeometry v3 candidate preview",
        [
            polygon(visual_v3["leftEdge"], visual_v3["rightEdge"], project, "#202838", 0.94),
            polyline(physics["centerline"], project, "#94a3b8", 0.7, 0.24),
            polyline(visual_v3["leftEdge"], project, "#38bdf8", 1.8, 0.94),
            polyline(visual_v3["rightEdge"], project, "#36f3a5", 1.8, 0.94),
            polyline(visual_v3["centerline"], project, "#f8fafc", 0.8, 0.32),
            *local_repair_markers(local_repaired_points, project),
        ],
    )
    write_svg(
        DEBUG_DIR / "track_visual_v2_vs_v3.svg",
        "TrackVisualGeometry v2 vs v3 candidate",
        [
            polygon(visual_v3["leftEdge"], visual_v3["rightEdge"], project, "#202838", 0.54),
            polyline(visual["leftEdge"], project, "#ef4444", 1.0, 0.58),
            polyline(visual["rightEdge"], project, "#ef4444", 1.0, 0.58),
            polyline(visual["centerline"], project, "#f97316", 1.0, 0.7),
            polyline(visual_v3["leftEdge"], project, "#38bdf8", 1.7, 0.96),
            polyline(visual_v3["rightEdge"], project, "#36f3a5", 1.7, 0.96),
            polyline(visual_v3["centerline"], project, "#22c55e", 1.4, 0.96),
            *local_repair_markers(local_repaired_points, project),
        ],
    )
    write_svg(
        DEBUG_DIR / "track_physics_vs_visual_v3.svg",
        "Physics vs visual v3 candidate",
        [
            polygon(visual_v3["leftEdge"], visual_v3["rightEdge"], project, "#202838", 0.68),
            polyline(physics["leftEdge"], project, "#94a3b8", 0.85, 0.36),
            polyline(physics["rightEdge"], project, "#94a3b8", 0.85, 0.36),
            polyline(visual["centerline"], project, "#ef4444", 0.9, 0.42),
            polyline(visual_v3["leftEdge"], project, "#38bdf8", 1.8, 0.94),
            polyline(visual_v3["rightEdge"], project, "#36f3a5", 1.8, 0.94),
            polyline(visual_v3["centerline"], project, "#22c55e", 1.2, 0.96),
            *local_repair_markers(local_repaired_points, project),
        ],
    )
    write_svg(
        DEBUG_DIR / "track_visual_road_only_preview.svg",
        "TrackVisualGeometry ROAD-only visual preview",
        [
            polygon(visual["leftEdge"], visual["rightEdge"], project, "#202838", 0.94),
            polyline(visual["leftEdge"], project, "#38bdf8", 1.7, 0.9),
            polyline(visual["rightEdge"], project, "#36f3a5", 1.7, 0.9),
            polyline(visual["centerline"], project, "#f8fafc", 0.85, 0.38),
        ],
    )
    write_svg(
        DEBUG_DIR / "track_visual_fixed_false_curves.svg",
        "TrackVisualGeometry false-curve fix",
        [
            polygon(visual["leftEdge"], visual["rightEdge"], project, "#202838", 0.9),
            polyline(physics["leftEdge"], project, "#ff3158", 0.75, 0.22),
            polyline(physics["rightEdge"], project, "#ffb000", 0.75, 0.22),
            polyline(visual["leftEdge"], project, "#38bdf8", 1.8, 0.92),
            polyline(visual["rightEdge"], project, "#36f3a5", 1.8, 0.92),
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
        DEBUG_DIR / "track_physics_vs_visual_after_false_curve_fix.svg",
        "Physics vs visual after false-curve fix",
        [
            polygon(visual["leftEdge"], visual["rightEdge"], project, "#202838", 0.74),
            polyline(physics["leftEdge"], project, "#ff3158", 0.85, 0.38),
            polyline(physics["rightEdge"], project, "#ffb000", 0.85, 0.38),
            polyline(visual["leftEdge"], project, "#38bdf8", 1.8, 0.94),
            polyline(visual["rightEdge"], project, "#36f3a5", 1.8, 0.94),
            polyline(visual["centerline"], project, "#f8fafc", 0.8, 0.34),
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
                "falseCurvesReport": str(DEBUG_DIR / "track_visual_false_curves_report.json"),
                "centerlineArtifacts": str(DEBUG_DIR / "track_visual_centerline_artifacts.json"),
                "centerlineBeforeAfter": str(DEBUG_DIR / "track_visual_centerline_before_after.svg"),
                "visualV2Preview": str(DEBUG_DIR / "track_visual_geometry_v2_preview.svg"),
                "physicsVsVisualV2": str(DEBUG_DIR / "track_physics_vs_visual_v2.svg"),
                "ribbonPreview": str(DEBUG_DIR / "track_visual_ribbon_preview.svg"),
                "polygonVsRibbon": str(DEBUG_DIR / "track_visual_polygon_vs_ribbon.svg"),
                "ribbonMetrics": str(DEBUG_DIR / "track_visual_ribbon_metrics.json"),
                "localDeformationReport": str(DEBUG_DIR / "track_visual_local_deformation_report.json"),
                "localDeformationSvg": str(DEBUG_DIR / "track_visual_local_deformation_report.svg"),
                "visualV3Preview": str(DEBUG_DIR / "track_visual_geometry_v3_preview.svg"),
                "visualV2VsV3": str(DEBUG_DIR / "track_visual_v2_vs_v3.svg"),
                "physicsVsVisualV3": str(DEBUG_DIR / "track_physics_vs_visual_v3.svg"),
                "roadOnlyPreview": str(DEBUG_DIR / "track_visual_road_only_preview.svg"),
                "fixedFalseCurves": str(DEBUG_DIR / "track_visual_fixed_false_curves.svg"),
                "physicsVsVisualAfterFalseCurveFix": str(DEBUG_DIR / "track_physics_vs_visual_after_false_curve_fix.svg"),
                "artifactCount": len(artifacts),
                "removedSpikeCount": track["visualGeometry"].get("removedSpikeCount"),
                "falseCurveArtifactsRemoved": track["visualGeometry"].get("falseCurveArtifactsRemoved"),
                "centerlineArtifactsDetected": track["visualGeometry"].get("centerlineArtifactsDetected"),
                "centerlineArtifactsReduced": track["visualGeometry"].get("centerlineArtifactsReduced"),
                "maxWidthDeltaBefore": track["visualGeometry"].get("maxWidthDeltaBefore"),
                "maxWidthDeltaAfter": track["visualGeometry"].get("maxWidthDeltaAfter"),
                "visualWidthMin": track["visualGeometry"].get("widthMin"),
                "visualWidthAvg": track["visualGeometry"].get("widthAvg"),
                "visualWidthMax": track["visualGeometry"].get("widthMax"),
                "visualRenderMode": track["visualGeometry"].get("visualRenderMode"),
                "visualVersion": track["visualGeometry"].get("visualVersion"),
                "ribbonWidthMeters": track["visualGeometry"].get("ribbonWidthMeters"),
                "centerlineMaxDisplacement": track["visualGeometry"].get("centerlineMaxDisplacement"),
                "visualArtifactCountAfterBuild": track["visualGeometry"].get("visualArtifactReport", {}).get("artifactCount"),
                "v3LocalDeformationsDetected": visual_v3_geometry.get("localDeformationsDetected"),
                "v3LocalDeformationsRepaired": visual_v3_geometry.get("localDeformationsRepaired"),
                "v3MaxRepairDisplacement": visual_v3_geometry.get("maxRepairDisplacement"),
                "v3AvgRepairDisplacement": visual_v3_geometry.get("avgRepairDisplacement"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
