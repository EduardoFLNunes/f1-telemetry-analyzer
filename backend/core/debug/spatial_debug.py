from typing import Any, Dict


def projection_debug_payload(car_state: Dict[str, Any]) -> Dict[str, Any]:
    """Extract deterministic projection diagnostics for debug overlays."""
    debug = car_state.get("projectionDebug", {})
    return {
        "worldPosition": car_state.get("worldPosition"),
        "mapPosition": car_state.get("mapPosition"),
        "projectedWorldPosition": car_state.get("projectedWorldPosition"),
        "projectedPosition": car_state.get("projectedPosition"),
        "distanceAlongTrack": car_state.get("s"),
        "lateralOffset": car_state.get("L"),
        "alignmentDrift": car_state.get("alignment_drift"),
        "nearestSegmentIndex": debug.get("nearestSegmentIndex"),
        "tangentVector": debug.get("tangentVector"),
        "normalVector": debug.get("normalVector"),
        "projectionLine": debug.get("projectionLine"),
    }
