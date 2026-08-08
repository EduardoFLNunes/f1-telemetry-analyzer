from typing import Any, Dict, Mapping, Optional

from ..geometry.paint_agreement import evaluate_paint_agreement_cached


def validate_track(
    track_state: Optional[str],
    track_data: Optional[Mapping[str, Any]],
    track_name: Optional[str] = None,
    build_method: Optional[str] = None,
) -> Dict[str, Any]:
    track = track_data or {}
    centerline = track.get("centerline") or []
    left = track.get("boundsLeft") or track.get("left_edge") or []
    right = track.get("boundsRight") or track.get("right_edge") or []
    sectors = track.get("sectors") or []
    sector_count = track.get("sectorCount")
    has_centerline = len(centerline) >= 2
    has_bounds = len(left) >= 2 and len(right) >= 2
    has_sectors = bool(sectors) or bool(sector_count and int(sector_count) > 0)
    issues = []

    if not track:
        status = "TRACK_MISSING" if track_state in {"NO_TRACK", "TRACK_INVALID"} else "UNKNOWN"
        issues.append("track geometry is unavailable")
    elif not has_centerline or not has_bounds:
        status = "TRACK_PARTIAL"
        if not has_centerline:
            issues.append("centerline is missing or too short")
        if not has_bounds:
            issues.append("track bounds are missing or too short")
    elif track_state == "TRACK_READY":
        status = "TRACK_READY"
    else:
        status = "TRACK_PARTIAL"
        issues.append(f"runtime track state is {track_state or 'UNKNOWN'}")

    if track and not has_sectors:
        issues.append("sector metadata is unavailable")

    # The painted limit lines come from the track files, independent of the
    # raycast that produced the edges, so they can say whether the edges landed
    # where the circuit says they should. Reported alongside the structural
    # checks -- it never downgrades status, because paint covers under 20% of a
    # lap and absent paint is not a defect.
    paint = evaluate_paint_agreement_cached(track) if track else {"status": "UNAVAILABLE"}
    for issue in paint.get("issues", []):
        issues.append(f"paint check: {issue}")

    method = build_method or track.get("reconstruction", {}).get("method")
    return {
        "status": status,
        "paintAgreement": paint,
        "trackName": track_name or track.get("trackName") or track.get("name"),
        "sampleCount": len(centerline),
        "hasCenterline": has_centerline,
        "hasBounds": has_bounds,
        "hasSectors": has_sectors,
        "fallbackActive": method in {"live_open_path", "waiting_for_kn5_or_cache"},
        "buildMethod": method,
        "issues": issues,
    }
