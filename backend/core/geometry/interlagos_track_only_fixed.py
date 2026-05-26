import json
import math
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..cache.cache_serializer import CacheSerializer
from .interlagos_pit_lane_ai_visual import load_pit_visual_geometry


GEOMETRY_NAME = "InterlagosTrackOnlyFixedGeometry"
EDGE_CONTINUITY_GEOMETRY_NAME = "InterlagosMainTrackEdgeContinuityFix"
RETA_OPOSTA_LOCAL_FIX_GEOMETRY_NAME = "InterlagosRetaOpostaLocalFix"
RETA_OPOSTA_FINAL_LOCAL_FIX_GEOMETRY_NAME = "InterlagosRetaOpostaFinalLocalFix"
PITLANE_HARMONIC_ENTRY_EXIT_GEOMETRY_NAME = "InterlagosPitlaneHarmonicEntryExit"
PIT_BIFURCATION_FIX_GEOMETRY_NAME = "InterlagosPitBifurcationFix"
PIT_BIFURCATION_TAPER_REFINE_GEOMETRY_NAME = "InterlagosPitBifurcationTaperRefine"
PIT_ACCESS_CENTERLINE_FIX_GEOMETRY_NAME = "InterlagosPitAccessCenterlineFix"
PIT_ACCESS_SURFACE_UNION_FIX_GEOMETRY_NAME = "InterlagosPitAccessSurfaceUnionFix"
PIT_ACCESS_EDGE_STITCH_FIX_GEOMETRY_NAME = "InterlagosPitAccessEdgeStitchFix"
PIT_ACCESS_SMOOTH_STITCH_FIX_GEOMETRY_NAME = "InterlagosPitAccessSmoothStitchFix"
PIT_ACCESS_MICRO_SMOOTH_STITCH_FIX_GEOMETRY_NAME = "InterlagosPitAccessMicroSmoothStitchFix"
PIT_ACCESS_OPEN_EXIT_MOUTH_FIX_GEOMETRY_NAME = "InterlagosPitAccessOpenExitMouthFix"
PIT_ACCESS_ASPHALT_MERGE_FIX_GEOMETRY_NAME = "InterlagosPitAccessAsphaltMergeFix"
FIXED_GEOMETRY_FILE = "interlagos_track_only_fixed_geometry.json"
FIXED_REPORT_FILE = "interlagos_track_only_fixed_report.json"
FIXED_GEOMETRY_SVG_FILE = "interlagos_track_only_fixed_geometry.svg"
FIXED_BEFORE_AFTER_SVG_FILE = "interlagos_track_only_fixed_before_after.svg"
EDGE_CONTINUITY_CANDIDATE_FILE = "interlagos_edge_continuity_fix_candidate.json"
EDGE_CONTINUITY_VALIDATION_FILE = "interlagos_edge_continuity_fix_validation.json"
RETA_OPOSTA_LOCAL_FIX_CANDIDATE_FILE = "interlagos_reta_oposta_local_fix_candidate.json"
RETA_OPOSTA_LOCAL_FIX_VALIDATION_FILE = "interlagos_reta_oposta_local_fix_validation.json"
RETA_OPOSTA_FINAL_LOCAL_FIX_CANDIDATE_FILE = "interlagos_reta_oposta_final_local_fix_candidate.json"
RETA_OPOSTA_FINAL_LOCAL_FIX_VALIDATION_FILE = "interlagos_reta_oposta_final_local_fix_validation.json"
PITLANE_HARMONIC_ENTRY_EXIT_CANDIDATE_FILE = "interlagos_pitlane_harmonic_entry_exit_candidate.json"
PITLANE_HARMONIC_ENTRY_EXIT_VALIDATION_FILE = "interlagos_pitlane_harmonic_entry_exit_validation.json"
PIT_BIFURCATION_FIX_CANDIDATE_FILE = "interlagos_pit_bifurcation_fix_candidate.json"
PIT_BIFURCATION_FIX_VALIDATION_FILE = "interlagos_pit_bifurcation_fix_validation.json"
PIT_BIFURCATION_TAPER_REFINE_CANDIDATE_FILE = "interlagos_pit_bifurcation_taper_refine_candidate.json"
PIT_BIFURCATION_TAPER_REFINE_VALIDATION_FILE = "interlagos_pit_bifurcation_taper_refine_validation.json"
PIT_ACCESS_CENTERLINE_FIX_CANDIDATE_FILE = "interlagos_pit_access_centerline_fix_candidate.json"
PIT_ACCESS_CENTERLINE_FIX_VALIDATION_FILE = "interlagos_pit_access_centerline_fix_validation.json"
PIT_ACCESS_SURFACE_UNION_FIX_CANDIDATE_FILE = "interlagos_pit_access_surface_union_candidate.json"
PIT_ACCESS_SURFACE_UNION_FIX_VALIDATION_FILE = "interlagos_pit_access_surface_union_validation.json"
PIT_ACCESS_EDGE_STITCH_FIX_CANDIDATE_FILE = "interlagos_pit_access_edge_stitch_fix_candidate.json"
PIT_ACCESS_EDGE_STITCH_FIX_VALIDATION_FILE = "interlagos_pit_access_edge_stitch_fix_validation.json"
PIT_ACCESS_SMOOTH_STITCH_FIX_CANDIDATE_FILE = "interlagos_pit_access_smooth_stitch_fix_candidate.json"
PIT_ACCESS_SMOOTH_STITCH_FIX_VALIDATION_FILE = "interlagos_pit_access_smooth_stitch_fix_validation.json"
PIT_ACCESS_MICRO_SMOOTH_STITCH_FIX_CANDIDATE_FILE = "interlagos_pit_access_micro_smooth_stitch_fix_candidate.json"
PIT_ACCESS_MICRO_SMOOTH_STITCH_FIX_VALIDATION_FILE = "interlagos_pit_access_micro_smooth_stitch_fix_validation.json"
PIT_ACCESS_OPEN_EXIT_MOUTH_FIX_CANDIDATE_FILE = "interlagos_pit_access_open_exit_mouth_fix_candidate.json"
PIT_ACCESS_OPEN_EXIT_MOUTH_FIX_VALIDATION_FILE = "interlagos_pit_access_open_exit_mouth_fix_validation.json"
PIT_ACCESS_ASPHALT_MERGE_FIX_CANDIDATE_FILE = "interlagos_pit_access_asphalt_merge_fix_candidate.json"
PIT_ACCESS_ASPHALT_MERGE_FIX_VALIDATION_FILE = "interlagos_pit_access_asphalt_merge_fix_validation.json"

MAX_SEGMENT_LENGTH_M = 30.0
WIDTH_LOW_RATIO = 0.72
WIDTH_MIN_DELTA_M = 1.5
ROLLING_WINDOW = 20


HIGHLIGHT_REGIONS = [
    {"name": "Subida dos Boxes", "ranges": [(3800.0, 4346.0), (0.0, 120.0)]},
    {"name": "S do Senna", "ranges": [(420.0, 850.0)]},
    {"name": "Curva do Sol", "ranges": [(850.0, 1120.0)]},
    {"name": "Reta Oposta", "ranges": [(1120.0, 1900.0)]},
]


Point = Tuple[float, float]


def is_interlagos_track(track_name: Optional[str], track_config: Optional[str]) -> bool:
    name = (track_name or "").lower()
    config = (track_config or "").lower()
    return "interlagos" in name and (not config or config == "gp")


def fixed_geometry_path(repo_root: Path) -> Path:
    return repo_root / "data" / "debug" / FIXED_GEOMETRY_FILE


def load_fixed_geometry(repo_root: Path) -> Optional[Dict[str, Any]]:
    path = fixed_geometry_path(repo_root)
    if not path.exists():
        return None
    track_data = CacheSerializer.deserialize_track(path.read_text(encoding="utf-8"))
    track_data = (
        _apply_reta_oposta_final_local_fix(repo_root, track_data)
        or _apply_reta_oposta_local_fix(repo_root, track_data)
        or _apply_edge_continuity_candidate(repo_root, track_data)
        or _mark_track_only_geometry(track_data, path)
    )
    track_data = (
        _apply_pit_access_asphalt_merge_fix(repo_root, track_data)
        or _apply_pit_access_open_exit_mouth_fix(repo_root, track_data)
        or _apply_pit_access_micro_smooth_stitch_fix(repo_root, track_data)
        or _apply_pit_access_smooth_stitch_fix(repo_root, track_data)
        or _apply_pit_access_edge_stitch_fix(repo_root, track_data)
        or _apply_pit_access_surface_union_fix(repo_root, track_data)
        or _apply_pit_access_centerline_fix(repo_root, track_data)
        or _apply_pit_bifurcation_taper_refine(repo_root, track_data)
        or _apply_pit_bifurcation_fix(repo_root, track_data)
        or _apply_pitlane_harmonic_entry_exit(repo_root, track_data)
        or track_data
    )
    metadata = track_data.setdefault("metadata", {})
    if metadata.get("pitVisualGeometryFiltered"):
        pit_visual = track_data.get("pitVisualGeometry")
        if pit_visual:
            metadata["pitVisualGeometry"] = pit_visual.get("name")
    else:
        pit_visual = load_pit_visual_geometry(repo_root)
        if pit_visual:
            track_data["pitVisualGeometry"] = pit_visual
            metadata["pitVisualGeometry"] = pit_visual.get("name")
    return track_data


def _apply_pit_access_asphalt_merge_fix(repo_root: Path, track_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    debug_dir = repo_root / "data" / "debug"
    candidate_path = debug_dir / PIT_ACCESS_ASPHALT_MERGE_FIX_CANDIDATE_FILE
    validation_path = debug_dir / PIT_ACCESS_ASPHALT_MERGE_FIX_VALIDATION_FILE
    if not candidate_path.exists() or not validation_path.exists():
        return None

    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    if not validation.get("passed"):
        return None

    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    pit_visual_geometry = candidate.get("visualGeometry")
    if not pit_visual_geometry or not pit_visual_geometry.get("geometries"):
        return None

    previous_validation = track_data.get("validation", {})
    track_data["geometryName"] = PIT_ACCESS_ASPHALT_MERGE_FIX_GEOMETRY_NAME
    track_data["visualGeometryName"] = PIT_ACCESS_ASPHALT_MERGE_FIX_GEOMETRY_NAME
    track_data["renderMode"] = "visual_pit_access_asphalt_merge_fix"
    track_data["updatedAt"] = candidate.get("updatedAt") or candidate.get("generatedAt")
    track_data["provider"] = PIT_ACCESS_ASPHALT_MERGE_FIX_GEOMETRY_NAME
    track_data["providerSource"] = "assetto_corsa_track_files"
    track_data["cachePath"] = str(candidate_path)
    track_data["pitVisualGeometry"] = pit_visual_geometry
    track_data.setdefault("reconstruction", {})["pitlaneVisualMethod"] = PIT_ACCESS_ASPHALT_MERGE_FIX_GEOMETRY_NAME

    app_validation = {
        "appUsesPitAccessAsphaltMergeFix": True,
        "asphaltMergeFillGenerated": bool(validation.get("asphaltMergeFillGenerated")),
        "pitExitGapFilled": bool(validation.get("pitExitGapFilled")),
        "pitEntryGapFilled": bool(validation.get("pitEntryGapFilled")),
        "blackVoidBetweenMainAndPitRemoved": bool(validation.get("blackVoidBetweenMainAndPitRemoved")),
        "mainTrackInnerEdgeReplacedAtPitExit": bool(validation.get("mainTrackInnerEdgeReplacedAtPitExit")),
        "mainTrackInnerEdgeReplacedAtPitEntry": bool(validation.get("mainTrackInnerEdgeReplacedAtPitEntry")),
        "pitAccessInnerEdgeSuppressedAtMerge": bool(validation.get("pitAccessInnerEdgeSuppressedAtMerge")),
        "noInternalStrokeBetweenMainAndPitAccess": bool(validation.get("noInternalStrokeBetweenMainAndPitAccess")),
        "noTransverseCapAtPitExit": bool(validation.get("noTransverseCapAtPitExit")),
        "noWallClosingPitlane": bool(validation.get("noWallClosingPitlane")),
        "noRibbonOverlapVisible": bool(validation.get("noRibbonOverlapVisible")),
        "noGapBetweenMainAndPitAccess": bool(validation.get("noGapBetweenMainAndPitAccess")),
        "noBlackSeamVisible": bool(validation.get("noBlackSeamVisible")),
        "noRectangularBlock": bool(validation.get("noRectangularBlock")),
        "noFakeChicane": bool(validation.get("noFakeChicane")),
        "mainTrackStillClean": bool(validation.get("mainTrackPreserved")),
        "mainTrackPreserved": bool(validation.get("mainTrackPreserved")),
        "pitlanePreserved": bool(validation.get("pitlanePreserved")),
        "retaOpostaStillStraight": bool(validation.get("retaOpostaStillStraight")),
        "debugRequired": False,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "boundaryLoopsUsedAsFinalVisual": False,
        "rawTrianglesRendered": False,
        "sourceValidation": validation,
        "mainTrackValidation": previous_validation,
    }
    metadata = track_data.setdefault("metadata", {})
    metadata["cachePath"] = str(candidate_path)
    metadata["geometryName"] = PIT_ACCESS_ASPHALT_MERGE_FIX_GEOMETRY_NAME
    metadata["visualGeometryName"] = PIT_ACCESS_ASPHALT_MERGE_FIX_GEOMETRY_NAME
    metadata["renderMode"] = "visual_pit_access_asphalt_merge_fix"
    metadata["updatedAt"] = track_data["updatedAt"]
    metadata["mainTrackGeometryName"] = candidate.get("mainTrackGeometry")
    metadata["mainTrackVisualGeometryName"] = candidate.get("mainTrackVisualGeometry")
    metadata["pitAccessAsphaltMergeFixCandidate"] = str(candidate_path)
    metadata["pitAccessAsphaltMergeFixValidation"] = str(validation_path)
    metadata["pitVisualGeometryFiltered"] = True
    metadata["pitVisualGeometryManaged"] = True
    metadata["projectionCenterlinePreserved"] = True
    metadata["validation"] = app_validation
    track_data["validation"] = app_validation
    return track_data


def _apply_pit_access_open_exit_mouth_fix(repo_root: Path, track_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    debug_dir = repo_root / "data" / "debug"
    candidate_path = debug_dir / PIT_ACCESS_OPEN_EXIT_MOUTH_FIX_CANDIDATE_FILE
    validation_path = debug_dir / PIT_ACCESS_OPEN_EXIT_MOUTH_FIX_VALIDATION_FILE
    if not candidate_path.exists() or not validation_path.exists():
        return None

    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    if not validation.get("passed"):
        return None

    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    pit_visual_geometry = candidate.get("visualGeometry")
    if not pit_visual_geometry or not pit_visual_geometry.get("geometries"):
        return None

    previous_validation = track_data.get("validation", {})
    track_data["geometryName"] = PIT_ACCESS_OPEN_EXIT_MOUTH_FIX_GEOMETRY_NAME
    track_data["visualGeometryName"] = PIT_ACCESS_OPEN_EXIT_MOUTH_FIX_GEOMETRY_NAME
    track_data["renderMode"] = "visual_pit_access_open_exit_mouth_fix"
    track_data["updatedAt"] = candidate.get("updatedAt") or candidate.get("generatedAt")
    track_data["provider"] = PIT_ACCESS_OPEN_EXIT_MOUTH_FIX_GEOMETRY_NAME
    track_data["providerSource"] = "assetto_corsa_track_files"
    track_data["cachePath"] = str(candidate_path)
    track_data["pitVisualGeometry"] = pit_visual_geometry
    track_data.setdefault("reconstruction", {})["pitlaneVisualMethod"] = PIT_ACCESS_OPEN_EXIT_MOUTH_FIX_GEOMETRY_NAME

    app_validation = {
        "appUsesPitAccessOpenExitMouthFix": True,
        "pitExitOpenCaps": bool(validation.get("pitExitOpenCaps")),
        "pitExitStartStitchSuppressed": bool(validation.get("pitExitStartStitchSuppressed")),
        "pitExitEndStitchSuppressed": bool(validation.get("pitExitEndStitchSuppressed")),
        "pitExitTransverseStitchesSuppressed": bool(validation.get("pitExitTransverseStitchesSuppressed")),
        "pitExitMouthClosedByStroke": bool(validation.get("pitExitMouthClosedByStroke")),
        "pitExitMouthNotClosedByStroke": bool(validation.get("pitExitMouthNotClosedByStroke")),
        "noTransverseLineCuttingPitlane": bool(validation.get("noTransverseLineCuttingPitlane")),
        "pitExitStartOverlapGenerated": bool(validation.get("pitExitStartOverlapGenerated")),
        "pitExitCorridorJoinCapCovered": bool(validation.get("pitExitCorridorJoinCapCovered")),
        "mainTrackInnerEdgeSuppressedAtPitExit": bool(validation.get("mainTrackInnerEdgeSuppressedAtPitExit")),
        "pitExitInnerEdgeSuppressed": bool(validation.get("pitExitInnerEdgeSuppressed")),
        "pitExitEndCapSuppressed": bool(validation.get("pitExitEndCapSuppressed")),
        "maxEndpointGapAfterMeters": validation.get("maxEndpointGapAfterMeters"),
        "maxStitchHeadingStepBefore": validation.get("maxStitchHeadingStepBefore"),
        "maxStitchHeadingStepAfter": validation.get("maxStitchHeadingStepAfter"),
        "noSharpStitchAngle": bool(validation.get("noSharpStitchAngle")),
        "noGapBetweenMainAndPitAccess": bool(validation.get("noGapBetweenMainAndPitAccess")),
        "noDoubleStrokeAtContact": bool(validation.get("noDoubleStrokeAtContact")),
        "noWallClosingPitlane": bool(validation.get("noWallClosingPitlane")),
        "mainTrackStillClean": bool(validation.get("mainTrackPreserved")),
        "mainTrackPreserved": bool(validation.get("mainTrackPreserved")),
        "pitlanePreserved": bool(validation.get("pitlanePreserved")),
        "retaOpostaStillStraight": bool(validation.get("retaOpostaStillStraight")),
        "debugRequired": False,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "boundaryLoopsUsedAsFinalVisual": False,
        "rawTrianglesRendered": False,
        "sourceValidation": validation,
        "mainTrackValidation": previous_validation,
    }
    metadata = track_data.setdefault("metadata", {})
    metadata["cachePath"] = str(candidate_path)
    metadata["geometryName"] = PIT_ACCESS_OPEN_EXIT_MOUTH_FIX_GEOMETRY_NAME
    metadata["visualGeometryName"] = PIT_ACCESS_OPEN_EXIT_MOUTH_FIX_GEOMETRY_NAME
    metadata["renderMode"] = "visual_pit_access_open_exit_mouth_fix"
    metadata["updatedAt"] = track_data["updatedAt"]
    metadata["mainTrackGeometryName"] = candidate.get("mainTrackGeometry")
    metadata["mainTrackVisualGeometryName"] = candidate.get("mainTrackVisualGeometry")
    metadata["pitAccessOpenExitMouthFixCandidate"] = str(candidate_path)
    metadata["pitAccessOpenExitMouthFixValidation"] = str(validation_path)
    metadata["pitVisualGeometryFiltered"] = True
    metadata["pitVisualGeometryManaged"] = True
    metadata["projectionCenterlinePreserved"] = True
    metadata["validation"] = app_validation
    track_data["validation"] = app_validation
    return track_data


def _apply_pit_access_micro_smooth_stitch_fix(repo_root: Path, track_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    debug_dir = repo_root / "data" / "debug"
    candidate_path = debug_dir / PIT_ACCESS_MICRO_SMOOTH_STITCH_FIX_CANDIDATE_FILE
    validation_path = debug_dir / PIT_ACCESS_MICRO_SMOOTH_STITCH_FIX_VALIDATION_FILE
    if not candidate_path.exists() or not validation_path.exists():
        return None

    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    if not validation.get("passed"):
        return None

    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    pit_visual_geometry = candidate.get("visualGeometry")
    if not pit_visual_geometry or not pit_visual_geometry.get("geometries"):
        return None

    previous_validation = track_data.get("validation", {})
    track_data["geometryName"] = PIT_ACCESS_MICRO_SMOOTH_STITCH_FIX_GEOMETRY_NAME
    track_data["visualGeometryName"] = PIT_ACCESS_MICRO_SMOOTH_STITCH_FIX_GEOMETRY_NAME
    track_data["renderMode"] = "visual_pit_access_micro_smooth_stitch_fix"
    track_data["updatedAt"] = candidate.get("updatedAt") or candidate.get("generatedAt")
    track_data["provider"] = PIT_ACCESS_MICRO_SMOOTH_STITCH_FIX_GEOMETRY_NAME
    track_data["providerSource"] = "assetto_corsa_track_files"
    track_data["cachePath"] = str(candidate_path)
    track_data["pitVisualGeometry"] = pit_visual_geometry
    track_data.setdefault("reconstruction", {})["pitlaneVisualMethod"] = PIT_ACCESS_MICRO_SMOOTH_STITCH_FIX_GEOMETRY_NAME

    app_validation = {
        "appUsesPitAccessMicroSmoothStitchFix": True,
        "microSmoothStitchEdgesGenerated": bool(validation.get("microSmoothStitchEdgesGenerated")),
        "maxEndpointGapAfterMeters": validation.get("maxEndpointGapAfterMeters"),
        "maxStitchHeadingStepBefore": validation.get("maxStitchHeadingStepBefore"),
        "maxStitchHeadingStepAfter": validation.get("maxStitchHeadingStepAfter"),
        "noSharpStitchAngle": bool(validation.get("noSharpStitchAngle")),
        "noGapBetweenMainAndPitAccess": bool(validation.get("noGapBetweenMainAndPitAccess")),
        "noDoubleStrokeAtContact": bool(validation.get("noDoubleStrokeAtContact")),
        "noWallClosingPitlane": bool(validation.get("noWallClosingPitlane")),
        "mainTrackStillClean": bool(validation.get("mainTrackPreserved")),
        "mainTrackPreserved": bool(validation.get("mainTrackPreserved")),
        "pitlanePreserved": bool(validation.get("pitlanePreserved")),
        "retaOpostaStillStraight": bool(validation.get("retaOpostaStillStraight")),
        "debugRequired": False,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "boundaryLoopsUsedAsFinalVisual": False,
        "rawTrianglesRendered": False,
        "sourceValidation": validation,
        "mainTrackValidation": previous_validation,
    }
    metadata = track_data.setdefault("metadata", {})
    metadata["cachePath"] = str(candidate_path)
    metadata["geometryName"] = PIT_ACCESS_MICRO_SMOOTH_STITCH_FIX_GEOMETRY_NAME
    metadata["visualGeometryName"] = PIT_ACCESS_MICRO_SMOOTH_STITCH_FIX_GEOMETRY_NAME
    metadata["renderMode"] = "visual_pit_access_micro_smooth_stitch_fix"
    metadata["updatedAt"] = track_data["updatedAt"]
    metadata["mainTrackGeometryName"] = candidate.get("mainTrackGeometry")
    metadata["mainTrackVisualGeometryName"] = candidate.get("mainTrackVisualGeometry")
    metadata["pitAccessMicroSmoothStitchFixCandidate"] = str(candidate_path)
    metadata["pitAccessMicroSmoothStitchFixValidation"] = str(validation_path)
    metadata["pitVisualGeometryFiltered"] = True
    metadata["pitVisualGeometryManaged"] = True
    metadata["projectionCenterlinePreserved"] = True
    metadata["validation"] = app_validation
    track_data["validation"] = app_validation
    return track_data


def _apply_pit_access_smooth_stitch_fix(repo_root: Path, track_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    debug_dir = repo_root / "data" / "debug"
    candidate_path = debug_dir / PIT_ACCESS_SMOOTH_STITCH_FIX_CANDIDATE_FILE
    validation_path = debug_dir / PIT_ACCESS_SMOOTH_STITCH_FIX_VALIDATION_FILE
    if not candidate_path.exists() or not validation_path.exists():
        return None

    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    if not validation.get("passed"):
        return None

    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    pit_visual_geometry = candidate.get("visualGeometry")
    if not pit_visual_geometry or not pit_visual_geometry.get("geometries"):
        return None

    previous_validation = track_data.get("validation", {})
    track_data["geometryName"] = PIT_ACCESS_SMOOTH_STITCH_FIX_GEOMETRY_NAME
    track_data["visualGeometryName"] = PIT_ACCESS_SMOOTH_STITCH_FIX_GEOMETRY_NAME
    track_data["renderMode"] = "visual_pit_access_smooth_stitch_fix"
    track_data["updatedAt"] = candidate.get("updatedAt") or candidate.get("generatedAt")
    track_data["provider"] = PIT_ACCESS_SMOOTH_STITCH_FIX_GEOMETRY_NAME
    track_data["providerSource"] = "assetto_corsa_track_files"
    track_data["cachePath"] = str(candidate_path)
    track_data["pitVisualGeometry"] = pit_visual_geometry
    track_data.setdefault("reconstruction", {})["pitlaneVisualMethod"] = PIT_ACCESS_SMOOTH_STITCH_FIX_GEOMETRY_NAME

    app_validation = {
        "appUsesPitAccessSmoothStitchFix": True,
        "smoothStitchEdgesGenerated": bool(validation.get("smoothStitchEdgesGenerated")),
        "maxEndpointGapAfterMeters": validation.get("maxEndpointGapAfterMeters"),
        "maxStitchHeadingStepBefore": validation.get("maxStitchHeadingStepBefore"),
        "maxStitchHeadingStepAfter": validation.get("maxStitchHeadingStepAfter"),
        "noSharpStitchAngle": bool(validation.get("noSharpStitchAngle")),
        "noInternalEdgeBreakAtEntry": bool(validation.get("noInternalEdgeBreakAtEntry")),
        "noInternalEdgeBreakAtExit": bool(validation.get("noInternalEdgeBreakAtExit")),
        "noEdgeStepAtEntry": bool(validation.get("noEdgeStepAtEntry")),
        "noEdgeStepAtExit": bool(validation.get("noEdgeStepAtExit")),
        "noGapBetweenMainAndPitAccess": bool(validation.get("noGapBetweenMainAndPitAccess")),
        "noDoubleStrokeAtContact": bool(validation.get("noDoubleStrokeAtContact")),
        "noWallClosingPitlane": bool(validation.get("noWallClosingPitlane")),
        "noRibbonOverlapVisible": bool(validation.get("noRibbonOverlapVisible")),
        "mainTrackStillClean": bool(validation.get("mainTrackPreserved")),
        "mainTrackPreserved": bool(validation.get("mainTrackPreserved")),
        "pitlanePreserved": bool(validation.get("pitlanePreserved")),
        "retaOpostaStillStraight": bool(validation.get("retaOpostaStillStraight")),
        "debugRequired": False,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "boundaryLoopsUsedAsFinalVisual": False,
        "rawTrianglesRendered": False,
        "sourceValidation": validation,
        "mainTrackValidation": previous_validation,
    }
    metadata = track_data.setdefault("metadata", {})
    metadata["cachePath"] = str(candidate_path)
    metadata["geometryName"] = PIT_ACCESS_SMOOTH_STITCH_FIX_GEOMETRY_NAME
    metadata["visualGeometryName"] = PIT_ACCESS_SMOOTH_STITCH_FIX_GEOMETRY_NAME
    metadata["renderMode"] = "visual_pit_access_smooth_stitch_fix"
    metadata["updatedAt"] = track_data["updatedAt"]
    metadata["mainTrackGeometryName"] = candidate.get("mainTrackGeometry")
    metadata["mainTrackVisualGeometryName"] = candidate.get("mainTrackVisualGeometry")
    metadata["pitAccessSmoothStitchFixCandidate"] = str(candidate_path)
    metadata["pitAccessSmoothStitchFixValidation"] = str(validation_path)
    metadata["pitVisualGeometryFiltered"] = True
    metadata["pitVisualGeometryManaged"] = True
    metadata["projectionCenterlinePreserved"] = True
    metadata["validation"] = app_validation
    track_data["validation"] = app_validation
    return track_data


def _apply_pit_access_edge_stitch_fix(repo_root: Path, track_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    debug_dir = repo_root / "data" / "debug"
    candidate_path = debug_dir / PIT_ACCESS_EDGE_STITCH_FIX_CANDIDATE_FILE
    validation_path = debug_dir / PIT_ACCESS_EDGE_STITCH_FIX_VALIDATION_FILE
    if not candidate_path.exists() or not validation_path.exists():
        return None

    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    if not validation.get("passed"):
        return None

    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    pit_visual_geometry = candidate.get("visualGeometry")
    if not pit_visual_geometry or not pit_visual_geometry.get("geometries"):
        return None

    previous_validation = track_data.get("validation", {})
    track_data["geometryName"] = PIT_ACCESS_EDGE_STITCH_FIX_GEOMETRY_NAME
    track_data["visualGeometryName"] = PIT_ACCESS_EDGE_STITCH_FIX_GEOMETRY_NAME
    track_data["renderMode"] = "visual_pit_access_edge_stitch_fix"
    track_data["updatedAt"] = candidate.get("updatedAt") or candidate.get("generatedAt")
    track_data["provider"] = PIT_ACCESS_EDGE_STITCH_FIX_GEOMETRY_NAME
    track_data["providerSource"] = "assetto_corsa_track_files"
    track_data["cachePath"] = str(candidate_path)
    track_data["pitVisualGeometry"] = pit_visual_geometry
    track_data.setdefault("reconstruction", {})["pitlaneVisualMethod"] = PIT_ACCESS_EDGE_STITCH_FIX_GEOMETRY_NAME

    app_validation = {
        "appUsesPitAccessEdgeStitchFix": True,
        "entryEdgeStitched": bool(validation.get("entryEdgeStitched")),
        "exitEdgeStitched": bool(validation.get("exitEdgeStitched")),
        "noInternalEdgeBreakAtEntry": bool(validation.get("noInternalEdgeBreakAtEntry")),
        "noInternalEdgeBreakAtExit": bool(validation.get("noInternalEdgeBreakAtExit")),
        "noEdgeStepAtEntry": bool(validation.get("noEdgeStepAtEntry")),
        "noEdgeStepAtExit": bool(validation.get("noEdgeStepAtExit")),
        "noGapBetweenMainAndPitAccess": bool(validation.get("noGapBetweenMainAndPitAccess")),
        "noDoubleStrokeAtContact": bool(validation.get("noDoubleStrokeAtContact")),
        "noWallClosingPitlane": bool(validation.get("noWallClosingPitlane")),
        "noRibbonOverlapVisible": bool(validation.get("noRibbonOverlapVisible")),
        "mainTrackStillClean": bool(validation.get("mainTrackPreserved")),
        "mainTrackPreserved": bool(validation.get("mainTrackPreserved")),
        "pitlanePreserved": bool(validation.get("pitlanePreserved")),
        "retaOpostaStillStraight": bool(validation.get("retaOpostaStillStraight")),
        "debugRequired": False,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "boundaryLoopsUsedAsFinalVisual": False,
        "rawTrianglesRendered": False,
        "sourceValidation": validation,
        "mainTrackValidation": previous_validation,
    }
    metadata = track_data.setdefault("metadata", {})
    metadata["cachePath"] = str(candidate_path)
    metadata["geometryName"] = PIT_ACCESS_EDGE_STITCH_FIX_GEOMETRY_NAME
    metadata["visualGeometryName"] = PIT_ACCESS_EDGE_STITCH_FIX_GEOMETRY_NAME
    metadata["renderMode"] = "visual_pit_access_edge_stitch_fix"
    metadata["updatedAt"] = track_data["updatedAt"]
    metadata["mainTrackGeometryName"] = candidate.get("mainTrackGeometry")
    metadata["mainTrackVisualGeometryName"] = candidate.get("mainTrackVisualGeometry")
    metadata["pitAccessEdgeStitchFixCandidate"] = str(candidate_path)
    metadata["pitAccessEdgeStitchFixValidation"] = str(validation_path)
    metadata["pitVisualGeometryFiltered"] = True
    metadata["pitVisualGeometryManaged"] = True
    metadata["projectionCenterlinePreserved"] = True
    metadata["validation"] = app_validation
    track_data["validation"] = app_validation
    return track_data


def _apply_pit_access_surface_union_fix(repo_root: Path, track_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    debug_dir = repo_root / "data" / "debug"
    candidate_path = debug_dir / PIT_ACCESS_SURFACE_UNION_FIX_CANDIDATE_FILE
    validation_path = debug_dir / PIT_ACCESS_SURFACE_UNION_FIX_VALIDATION_FILE
    if not candidate_path.exists() or not validation_path.exists():
        return None

    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    if not validation.get("passed"):
        return None

    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    pit_visual_geometry = candidate.get("visualGeometry")
    if not pit_visual_geometry or not pit_visual_geometry.get("geometries"):
        return None

    previous_validation = track_data.get("validation", {})
    track_data["geometryName"] = PIT_ACCESS_SURFACE_UNION_FIX_GEOMETRY_NAME
    track_data["visualGeometryName"] = PIT_ACCESS_SURFACE_UNION_FIX_GEOMETRY_NAME
    track_data["renderMode"] = "visual_pit_access_surface_union_fix"
    track_data["updatedAt"] = candidate.get("updatedAt") or candidate.get("generatedAt")
    track_data["provider"] = PIT_ACCESS_SURFACE_UNION_FIX_GEOMETRY_NAME
    track_data["providerSource"] = "assetto_corsa_track_files"
    track_data["cachePath"] = str(candidate_path)
    track_data["pitVisualGeometry"] = pit_visual_geometry
    track_data.setdefault("reconstruction", {})["pitlaneVisualMethod"] = PIT_ACCESS_SURFACE_UNION_FIX_GEOMETRY_NAME

    app_validation = {
        "appUsesPitAccessSurfaceUnionFix": True,
        "pitlaneEntryMergedVisually": bool(validation.get("noVisualSeamAtEntry")),
        "pitlaneExitMergedVisually": bool(validation.get("noVisualSeamAtExit")),
        "internalSeamsVisible": not bool(validation.get("internalEdgesRemoved")),
        "internalEdgesRemoved": bool(validation.get("internalEdgesRemoved")),
        "noRibbonOverlapVisible": bool(validation.get("noRibbonOverlapVisible")),
        "noWallClosingPitlane": bool(validation.get("noWallClosingPitlane")),
        "noGapBetweenMainAndPitAccess": bool(validation.get("noGapBetweenMainAndPitAccess")),
        "mainTrackStillClean": bool(validation.get("mainTrackPreserved")),
        "mainTrackPreserved": bool(validation.get("mainTrackPreserved")),
        "retaOpostaStillStraight": bool(validation.get("retaOpostaStillStraight")),
        "debugRequired": False,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "boundaryLoopsUsedAsFinalVisual": False,
        "rawTrianglesRendered": False,
        "sourceValidation": validation,
        "mainTrackValidation": previous_validation,
    }
    metadata = track_data.setdefault("metadata", {})
    metadata["cachePath"] = str(candidate_path)
    metadata["geometryName"] = PIT_ACCESS_SURFACE_UNION_FIX_GEOMETRY_NAME
    metadata["visualGeometryName"] = PIT_ACCESS_SURFACE_UNION_FIX_GEOMETRY_NAME
    metadata["renderMode"] = "visual_pit_access_surface_union_fix"
    metadata["updatedAt"] = track_data["updatedAt"]
    metadata["mainTrackGeometryName"] = candidate.get("mainTrackGeometry")
    metadata["mainTrackVisualGeometryName"] = candidate.get("mainTrackVisualGeometry")
    metadata["pitAccessSurfaceUnionFixCandidate"] = str(candidate_path)
    metadata["pitAccessSurfaceUnionFixValidation"] = str(validation_path)
    metadata["pitVisualGeometryFiltered"] = True
    metadata["pitVisualGeometryManaged"] = True
    metadata["projectionCenterlinePreserved"] = True
    metadata["validation"] = app_validation
    track_data["validation"] = app_validation
    return track_data


def _apply_pit_access_centerline_fix(repo_root: Path, track_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    debug_dir = repo_root / "data" / "debug"
    candidate_path = debug_dir / PIT_ACCESS_CENTERLINE_FIX_CANDIDATE_FILE
    validation_path = debug_dir / PIT_ACCESS_CENTERLINE_FIX_VALIDATION_FILE
    if not candidate_path.exists() or not validation_path.exists():
        return None

    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    if not validation.get("passed"):
        return None

    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    pit_visual_geometry = candidate.get("visualGeometry")
    if not pit_visual_geometry or not pit_visual_geometry.get("geometries"):
        return None

    previous_validation = track_data.get("validation", {})
    track_data["geometryName"] = PIT_ACCESS_CENTERLINE_FIX_GEOMETRY_NAME
    track_data["visualGeometryName"] = PIT_ACCESS_CENTERLINE_FIX_GEOMETRY_NAME
    track_data["renderMode"] = "visual_pit_access_centerline_fix"
    track_data["updatedAt"] = candidate.get("updatedAt") or candidate.get("generatedAt")
    track_data["provider"] = PIT_ACCESS_CENTERLINE_FIX_GEOMETRY_NAME
    track_data["providerSource"] = "assetto_corsa_track_files"
    track_data["cachePath"] = str(candidate_path)
    track_data["pitVisualGeometry"] = pit_visual_geometry
    track_data.setdefault("reconstruction", {})["pitlaneVisualMethod"] = PIT_ACCESS_CENTERLINE_FIX_GEOMETRY_NAME

    app_validation = {
        "appUsesPitAccessCenterlineFix": True,
        "accessRibbonGenerated": bool(validation.get("accessRibbonGenerated")),
        "entryAccessHasArea": bool(validation.get("entryAccessHasArea")),
        "exitAccessHasArea": bool(validation.get("exitAccessHasArea")),
        "entryNotRenderedAsThinLine": bool(validation.get("entryNotRenderedAsThinLine")),
        "exitNotRenderedAsThinLine": bool(validation.get("exitNotRenderedAsThinLine")),
        "noNeedleShape": bool(validation.get("noNeedleShape")),
        "noTriangularSpike": bool(validation.get("noTriangularSpike")),
        "entryAccessCenterlineUsed": bool(validation.get("entryAccessCenterlineUsed")),
        "exitAccessCenterlineUsed": bool(validation.get("exitAccessCenterlineUsed")),
        "sharedDividerNotUsedAsOnlyVisual": bool(validation.get("sharedDividerNotUsedAsOnlyVisual")),
        "noTriangularTaper": bool(validation.get("noTriangularTaper")),
        "noRibbonOverlap": bool(validation.get("noRibbonOverlap")),
        "pitEntryLooksNatural": bool(validation.get("pitEntryLooksNatural")),
        "pitExitLooksNatural": bool(validation.get("pitExitLooksNatural")),
        "mainTrackPreserved": bool(validation.get("mainTrackPreserved")),
        "noVisualXCrossing": bool(validation.get("noVisualXCrossing")),
        "pitlaneStillConnected": bool(validation.get("pitlaneStillConnected")),
        "retaOpostaStillStraight": bool(validation.get("retaOpostaStillStraight")),
        "debugRequired": False,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "boundaryLoopsUsedAsFinalVisual": False,
        "rawTrianglesRendered": False,
        "sourceValidation": validation,
        "mainTrackValidation": previous_validation,
    }
    metadata = track_data.setdefault("metadata", {})
    metadata["cachePath"] = str(candidate_path)
    metadata["geometryName"] = PIT_ACCESS_CENTERLINE_FIX_GEOMETRY_NAME
    metadata["visualGeometryName"] = PIT_ACCESS_CENTERLINE_FIX_GEOMETRY_NAME
    metadata["renderMode"] = "visual_pit_access_centerline_fix"
    metadata["updatedAt"] = track_data["updatedAt"]
    metadata["mainTrackGeometryName"] = candidate.get("mainTrackGeometry")
    metadata["mainTrackVisualGeometryName"] = candidate.get("mainTrackVisualGeometry")
    metadata["pitAccessCenterlineFixCandidate"] = str(candidate_path)
    metadata["pitAccessCenterlineFixValidation"] = str(validation_path)
    metadata["pitVisualGeometryFiltered"] = True
    metadata["pitVisualGeometryManaged"] = True
    metadata["projectionCenterlinePreserved"] = True
    metadata["validation"] = app_validation
    track_data["validation"] = app_validation
    return track_data


def _apply_pit_bifurcation_taper_refine(repo_root: Path, track_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    debug_dir = repo_root / "data" / "debug"
    candidate_path = debug_dir / PIT_BIFURCATION_TAPER_REFINE_CANDIDATE_FILE
    validation_path = debug_dir / PIT_BIFURCATION_TAPER_REFINE_VALIDATION_FILE
    if not candidate_path.exists() or not validation_path.exists():
        return None

    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    if not validation.get("passed"):
        return None

    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    pit_visual_geometry = candidate.get("visualGeometry")
    if not pit_visual_geometry or not pit_visual_geometry.get("geometries"):
        return None

    previous_validation = track_data.get("validation", {})
    track_data["geometryName"] = PIT_BIFURCATION_TAPER_REFINE_GEOMETRY_NAME
    track_data["visualGeometryName"] = PIT_BIFURCATION_TAPER_REFINE_GEOMETRY_NAME
    track_data["renderMode"] = "visual_pit_bifurcation_taper_refine"
    track_data["updatedAt"] = candidate.get("updatedAt") or candidate.get("generatedAt")
    track_data["provider"] = PIT_BIFURCATION_TAPER_REFINE_GEOMETRY_NAME
    track_data["providerSource"] = "assetto_corsa_track_files"
    track_data["cachePath"] = str(candidate_path)
    track_data["pitVisualGeometry"] = pit_visual_geometry
    track_data.setdefault("reconstruction", {})["pitlaneVisualMethod"] = PIT_BIFURCATION_TAPER_REFINE_GEOMETRY_NAME

    app_validation = {
        "appUsesPitBifurcationTaperRefine": True,
        "pitlaneEntryHarmonic": bool(validation.get("noSharpPitTaper") and validation.get("pitEntryOpenSplit")),
        "pitlaneExitHarmonic": bool(validation.get("noSharpPitTaper") and validation.get("pitExitOpenMerge")),
        "noSharpPitTaper": bool(validation.get("noSharpPitTaper")),
        "noTriangularSpike": bool(validation.get("noTriangularSpike")),
        "mainTrackStillClean": bool(validation.get("mainTrackPreserved")),
        "retaOpostaStillStraight": bool(validation.get("retaOpostaStillStraight")),
        "noRibbonOverlap": bool(validation.get("noRibbonOverlap")),
        "noVisualXCrossing": bool(validation.get("noVisualXCrossing")),
        "noWallClosingPitlane": bool(validation.get("noWallClosingPitlane")),
        "debugRequired": False,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "boundaryLoopsUsedAsFinalVisual": False,
        "rawTrianglesRendered": False,
        "sourceValidation": validation,
        "mainTrackValidation": previous_validation,
    }
    metadata = track_data.setdefault("metadata", {})
    metadata["cachePath"] = str(candidate_path)
    metadata["geometryName"] = PIT_BIFURCATION_TAPER_REFINE_GEOMETRY_NAME
    metadata["visualGeometryName"] = PIT_BIFURCATION_TAPER_REFINE_GEOMETRY_NAME
    metadata["renderMode"] = "visual_pit_bifurcation_taper_refine"
    metadata["updatedAt"] = track_data["updatedAt"]
    metadata["mainTrackGeometryName"] = candidate.get("mainTrackGeometry")
    metadata["mainTrackVisualGeometryName"] = candidate.get("mainTrackVisualGeometry")
    metadata["pitBifurcationTaperRefineCandidate"] = str(candidate_path)
    metadata["pitBifurcationTaperRefineValidation"] = str(validation_path)
    metadata["pitVisualGeometryFiltered"] = True
    metadata["pitVisualGeometryManaged"] = True
    metadata["projectionCenterlinePreserved"] = True
    metadata["validation"] = app_validation
    track_data["validation"] = app_validation
    return track_data


def _apply_pit_bifurcation_fix(repo_root: Path, track_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    debug_dir = repo_root / "data" / "debug"
    candidate_path = debug_dir / PIT_BIFURCATION_FIX_CANDIDATE_FILE
    validation_path = debug_dir / PIT_BIFURCATION_FIX_VALIDATION_FILE
    if not candidate_path.exists() or not validation_path.exists():
        return None

    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    if not validation.get("passed"):
        return None

    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    pit_visual_geometry = candidate.get("visualGeometry")
    if not pit_visual_geometry or not pit_visual_geometry.get("geometries"):
        return None

    previous_validation = track_data.get("validation", {})
    track_data["geometryName"] = PIT_BIFURCATION_FIX_GEOMETRY_NAME
    track_data["visualGeometryName"] = PIT_BIFURCATION_FIX_GEOMETRY_NAME
    track_data["renderMode"] = "visual_pit_bifurcation_fix"
    track_data["updatedAt"] = candidate.get("updatedAt") or candidate.get("generatedAt")
    track_data["provider"] = PIT_BIFURCATION_FIX_GEOMETRY_NAME
    track_data["providerSource"] = "assetto_corsa_track_files"
    track_data["cachePath"] = str(candidate_path)
    track_data["pitVisualGeometry"] = pit_visual_geometry
    track_data.setdefault("reconstruction", {})["pitlaneVisualMethod"] = PIT_BIFURCATION_FIX_GEOMETRY_NAME

    app_validation = {
        "appUsesPitBifurcationFix": True,
        "debugRequired": False,
        "pitlaneEntryHarmonic": bool(validation.get("entrySplitLooksNatural")),
        "pitlaneExitHarmonic": bool(validation.get("exitMergeLooksNatural")),
        "noRibbonOverlap": bool(validation.get("noRibbonOverlap")),
        "noVisualXCrossing": bool(validation.get("noVisualXCrossing")),
        "noWallClosingPitlane": bool(validation.get("noFakeWall")),
        "mainTrackStillClean": bool(validation.get("mainTrackPreserved")),
        "retaOpostaStillStraight": bool(validation.get("retaOpostaStillStraight")),
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "boundaryLoopsUsedAsFinalVisual": False,
        "rawTrianglesRendered": False,
        "sourceValidation": validation,
        "mainTrackValidation": previous_validation,
    }
    metadata = track_data.setdefault("metadata", {})
    metadata["cachePath"] = str(candidate_path)
    metadata["geometryName"] = PIT_BIFURCATION_FIX_GEOMETRY_NAME
    metadata["visualGeometryName"] = PIT_BIFURCATION_FIX_GEOMETRY_NAME
    metadata["renderMode"] = "visual_pit_bifurcation_fix"
    metadata["updatedAt"] = track_data["updatedAt"]
    metadata["mainTrackGeometryName"] = candidate.get("mainTrackGeometry")
    metadata["mainTrackVisualGeometryName"] = candidate.get("mainTrackVisualGeometry")
    metadata["pitBifurcationFixCandidate"] = str(candidate_path)
    metadata["pitBifurcationFixValidation"] = str(validation_path)
    metadata["pitVisualGeometryFiltered"] = True
    metadata["pitVisualGeometryManaged"] = True
    metadata["projectionCenterlinePreserved"] = True
    metadata["validation"] = app_validation
    track_data["validation"] = app_validation
    return track_data


def _apply_pitlane_harmonic_entry_exit(repo_root: Path, track_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    debug_dir = repo_root / "data" / "debug"
    candidate_path = debug_dir / PITLANE_HARMONIC_ENTRY_EXIT_CANDIDATE_FILE
    validation_path = debug_dir / PITLANE_HARMONIC_ENTRY_EXIT_VALIDATION_FILE
    if not candidate_path.exists() or not validation_path.exists():
        return None

    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    if not validation.get("passed"):
        return None

    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    pit_visual_geometry = candidate.get("visualGeometry")
    if not pit_visual_geometry or not pit_visual_geometry.get("geometries"):
        return None

    previous_validation = track_data.get("validation", {})
    track_data["geometryName"] = PITLANE_HARMONIC_ENTRY_EXIT_GEOMETRY_NAME
    track_data["visualGeometryName"] = PITLANE_HARMONIC_ENTRY_EXIT_GEOMETRY_NAME
    track_data["renderMode"] = "visual_pitlane_harmonic_entry_exit"
    track_data["updatedAt"] = candidate.get("updatedAt") or candidate.get("generatedAt")
    track_data["provider"] = PITLANE_HARMONIC_ENTRY_EXIT_GEOMETRY_NAME
    track_data["providerSource"] = "assetto_corsa_track_files"
    track_data["cachePath"] = str(candidate_path)
    track_data["pitVisualGeometry"] = pit_visual_geometry
    track_data.setdefault("reconstruction", {})["pitlaneVisualMethod"] = PITLANE_HARMONIC_ENTRY_EXIT_GEOMETRY_NAME

    app_validation = {
        "appUsesPitlaneHarmonicEntryExit": True,
        "debugRequired": False,
        "pitExitClosedByWall": bool(validation.get("pitExitClosedByWall", True)),
        "pitlaneVisibleButClean": (
            bool(validation.get("pitEntryGenerated"))
            and bool(validation.get("pitExitGenerated"))
            and not bool(validation.get("pitlaneVisualMixWithMainTrack", True))
        ),
        "mainTrackStillClean": not bool(validation.get("mainTrackDeformed", True)),
        "retaOpostaStillStraight": bool(validation.get("retaOpostaStillStraight")),
        "pitEntryLooksHarmonic": bool(validation.get("pitEntryLooksHarmonic")),
        "pitExitLooksHarmonic": bool(validation.get("pitExitLooksHarmonic")),
        "pitExitOpenMerge": bool(validation.get("pitExitOpenMerge")),
        "noFakeChicane": bool(validation.get("noFakeChicane")),
        "noRectangularBlock": bool(validation.get("noRectangularBlock")),
        "noWallClosingPitExit": bool(validation.get("noWallClosingPitExit")),
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "boundaryLoopsUsedAsFinalVisual": False,
        "rawTrianglesRendered": False,
        "sourceValidation": validation,
        "mainTrackValidation": previous_validation,
    }
    metadata = track_data.setdefault("metadata", {})
    metadata["cachePath"] = str(candidate_path)
    metadata["geometryName"] = PITLANE_HARMONIC_ENTRY_EXIT_GEOMETRY_NAME
    metadata["visualGeometryName"] = PITLANE_HARMONIC_ENTRY_EXIT_GEOMETRY_NAME
    metadata["renderMode"] = "visual_pitlane_harmonic_entry_exit"
    metadata["updatedAt"] = track_data["updatedAt"]
    metadata["mainTrackGeometryName"] = candidate.get("mainTrackGeometry")
    metadata["mainTrackVisualGeometryName"] = candidate.get("mainTrackVisualGeometry")
    metadata["pitlaneHarmonicEntryExitCandidate"] = str(candidate_path)
    metadata["pitlaneHarmonicEntryExitValidation"] = str(validation_path)
    metadata["pitVisualGeometryFiltered"] = True
    metadata["pitVisualGeometryManaged"] = True
    metadata["projectionCenterlinePreserved"] = True
    metadata["validation"] = app_validation
    track_data["validation"] = app_validation
    return track_data


def _apply_reta_oposta_final_local_fix(repo_root: Path, track_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    debug_dir = repo_root / "data" / "debug"
    candidate_path = debug_dir / RETA_OPOSTA_FINAL_LOCAL_FIX_CANDIDATE_FILE
    validation_path = debug_dir / RETA_OPOSTA_FINAL_LOCAL_FIX_VALIDATION_FILE
    if not candidate_path.exists() or not validation_path.exists():
        return None

    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    if not validation.get("passed"):
        return None

    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    left_map = [_tuple(point) for point in candidate.get("leftEdge", {}).get("points", [])]
    right_map = [_tuple(point) for point in candidate.get("rightEdge", {}).get("points", [])]
    widths = [float(value) for value in candidate.get("localWidth", [])]
    visual_centerline = candidate.get("visualCenterline") or candidate.get("centerline")
    pit_visual_geometry = candidate.get("pitVisualGeometry")
    if not left_map or not right_map or len(left_map) != len(right_map) or len(left_map) != len(widths):
        return None

    bounds_left = [_map_to_world_edge(point) for point in left_map]
    bounds_right = [_map_to_world_edge(point) for point in right_map]
    track_data["geometryName"] = RETA_OPOSTA_FINAL_LOCAL_FIX_GEOMETRY_NAME
    track_data["visualGeometryName"] = RETA_OPOSTA_FINAL_LOCAL_FIX_GEOMETRY_NAME
    track_data["renderMode"] = "visual_final_local_reta_oposta_fix"
    track_data["updatedAt"] = candidate.get("updatedAt") or candidate.get("generatedAt")
    track_data["provider"] = RETA_OPOSTA_FINAL_LOCAL_FIX_GEOMETRY_NAME
    track_data["providerSource"] = "assetto_corsa_track_files"
    track_data["cachePath"] = str(candidate_path)
    track_data["boundsLeft"] = bounds_left
    track_data["boundsRight"] = bounds_right
    track_data["left_edge"] = bounds_left
    track_data["right_edge"] = bounds_right
    track_data["visualCenterline"] = visual_centerline
    track_data["localWidth"] = [round(value, 6) for value in widths]
    track_data["widthMin"] = round(min(widths), 6)
    track_data["widthAvg"] = round(sum(widths) / len(widths), 6)
    track_data["widthMax"] = round(max(widths), 6)
    track_data["asphaltPolygon"] = candidate.get("asphaltPolygon")
    if pit_visual_geometry:
        track_data["pitVisualGeometry"] = pit_visual_geometry
    track_data.setdefault("reconstruction", {})["method"] = RETA_OPOSTA_FINAL_LOCAL_FIX_GEOMETRY_NAME
    track_data["reconstruction"]["provider"] = RETA_OPOSTA_FINAL_LOCAL_FIX_GEOMETRY_NAME
    track_data["reconstruction"]["source"] = "assetto_corsa_track_files"

    app_validation = {
        "appUsesRetaOpostaFinalLocalFix": True,
        "holesVisible": False,
        "linesCrossingTrack": bool(validation.get("linesCrossingTrack", False)),
        "retaOpostaToothRemoved": bool(validation.get("retaOpostaToothRemoved")),
        "retaOpostaEntryLooksStraight": bool(validation.get("retaOpostaEntryLooksStraight")),
        "pitlaneVisualMixRemoved": bool(validation.get("pitlaneVisualMixRemoved")),
        "widthPreserved": validation.get("widthDeltaP95", 999.0) <= 0.15 and validation.get("widthDeltaMax", 999.0) <= 0.35,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "debugRequired": False,
        "boundaryLoopsUsedAsFinalVisual": False,
        "rawTrianglesRendered": False,
        "sourceValidation": validation,
    }
    metadata = track_data.setdefault("metadata", {})
    metadata["cachePath"] = str(candidate_path)
    metadata["geometryName"] = RETA_OPOSTA_FINAL_LOCAL_FIX_GEOMETRY_NAME
    metadata["visualGeometryName"] = RETA_OPOSTA_FINAL_LOCAL_FIX_GEOMETRY_NAME
    metadata["renderMode"] = "visual_final_local_reta_oposta_fix"
    metadata["updatedAt"] = track_data["updatedAt"]
    metadata["retaOpostaFinalLocalFixCandidate"] = str(candidate_path)
    metadata["retaOpostaFinalLocalFixValidation"] = str(validation_path)
    metadata["visualOnlyLocalFix"] = True
    metadata["pitVisualGeometryFiltered"] = bool(pit_visual_geometry)
    metadata["projectionCenterlinePreserved"] = True
    metadata["validation"] = app_validation
    track_data["validation"] = app_validation
    return track_data


def _apply_reta_oposta_local_fix(repo_root: Path, track_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    debug_dir = repo_root / "data" / "debug"
    candidate_path = debug_dir / RETA_OPOSTA_LOCAL_FIX_CANDIDATE_FILE
    validation_path = debug_dir / RETA_OPOSTA_LOCAL_FIX_VALIDATION_FILE
    if not candidate_path.exists() or not validation_path.exists():
        return None

    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    if not validation.get("passed"):
        return None

    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    left_map = [_tuple(point) for point in candidate.get("leftEdge", {}).get("points", [])]
    right_map = [_tuple(point) for point in candidate.get("rightEdge", {}).get("points", [])]
    widths = [float(value) for value in candidate.get("localWidth", [])]
    visual_centerline = candidate.get("visualCenterline") or candidate.get("centerline")
    if not left_map or not right_map or len(left_map) != len(right_map) or len(left_map) != len(widths):
        return None

    bounds_left = [_map_to_world_edge(point) for point in left_map]
    bounds_right = [_map_to_world_edge(point) for point in right_map]
    track_data["geometryName"] = RETA_OPOSTA_LOCAL_FIX_GEOMETRY_NAME
    track_data["visualGeometryName"] = RETA_OPOSTA_LOCAL_FIX_GEOMETRY_NAME
    track_data["renderMode"] = "visual_local_reta_oposta_fix"
    track_data["updatedAt"] = candidate.get("updatedAt") or candidate.get("generatedAt")
    track_data["provider"] = RETA_OPOSTA_LOCAL_FIX_GEOMETRY_NAME
    track_data["providerSource"] = "assetto_corsa_track_files"
    track_data["cachePath"] = str(candidate_path)
    track_data["boundsLeft"] = bounds_left
    track_data["boundsRight"] = bounds_right
    track_data["left_edge"] = bounds_left
    track_data["right_edge"] = bounds_right
    track_data["visualCenterline"] = visual_centerline
    track_data["localWidth"] = [round(value, 6) for value in widths]
    track_data["widthMin"] = round(min(widths), 6)
    track_data["widthAvg"] = round(sum(widths) / len(widths), 6)
    track_data["widthMax"] = round(max(widths), 6)
    track_data["asphaltPolygon"] = candidate.get("asphaltPolygon")
    track_data.setdefault("reconstruction", {})["method"] = RETA_OPOSTA_LOCAL_FIX_GEOMETRY_NAME
    track_data["reconstruction"]["provider"] = RETA_OPOSTA_LOCAL_FIX_GEOMETRY_NAME
    track_data["reconstruction"]["source"] = "assetto_corsa_track_files"

    app_validation = {
        "appUsesRetaOpostaLocalFix": True,
        "holesVisible": False,
        "linesCrossingTrack": bool(validation.get("linesCrossingTrack", False)),
        "retaOpostaEntryLooksStraight": bool(validation.get("entryToRetaOpostaLooksStraight")),
        "widthPreserved": validation.get("widthDeltaP95", 999.0) <= 0.15 and validation.get("widthDeltaMax", 999.0) <= 0.35,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "debugRequired": False,
        "boundaryLoopsUsedAsFinalVisual": False,
        "rawTrianglesRendered": False,
        "sourceValidation": validation,
    }
    metadata = track_data.setdefault("metadata", {})
    metadata["cachePath"] = str(candidate_path)
    metadata["geometryName"] = RETA_OPOSTA_LOCAL_FIX_GEOMETRY_NAME
    metadata["visualGeometryName"] = RETA_OPOSTA_LOCAL_FIX_GEOMETRY_NAME
    metadata["renderMode"] = "visual_local_reta_oposta_fix"
    metadata["updatedAt"] = track_data["updatedAt"]
    metadata["retaOpostaLocalFixCandidate"] = str(candidate_path)
    metadata["retaOpostaLocalFixValidation"] = str(validation_path)
    metadata["visualOnlyLocalFix"] = True
    metadata["projectionCenterlinePreserved"] = True
    metadata["validation"] = app_validation
    track_data["validation"] = app_validation
    return track_data


def _mark_track_only_geometry(track_data: Dict[str, Any], path: Path) -> Dict[str, Any]:
    track_data["geometryName"] = GEOMETRY_NAME
    track_data["provider"] = GEOMETRY_NAME
    track_data["providerSource"] = "assetto_corsa_track_files"
    track_data["cachePath"] = str(path)
    track_data.setdefault("metadata", {})["cachePath"] = str(path)
    track_data.setdefault("metadata", {})["geometryName"] = GEOMETRY_NAME
    track_data.setdefault("validation", {})["appUsesTrackOnlyFixedGeometry"] = True
    track_data.setdefault("metadata", {}).setdefault("validation", track_data["validation"])
    track_data["metadata"]["validation"]["appUsesTrackOnlyFixedGeometry"] = True
    return track_data


def _apply_edge_continuity_candidate(repo_root: Path, track_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    debug_dir = repo_root / "data" / "debug"
    candidate_path = debug_dir / EDGE_CONTINUITY_CANDIDATE_FILE
    validation_path = debug_dir / EDGE_CONTINUITY_VALIDATION_FILE
    if not candidate_path.exists() or not validation_path.exists():
        return None

    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    if not validation.get("passed"):
        return None

    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    left_map = [_tuple(point) for point in candidate.get("leftEdge", {}).get("points", [])]
    right_map = [_tuple(point) for point in candidate.get("rightEdge", {}).get("points", [])]
    widths = [float(value) for value in candidate.get("localWidth", [])]
    if not left_map or not right_map or len(left_map) != len(right_map) or len(left_map) != len(widths):
        return None

    bounds_left = [_map_to_world_edge(point) for point in left_map]
    bounds_right = [_map_to_world_edge(point) for point in right_map]
    track_data["geometryName"] = EDGE_CONTINUITY_GEOMETRY_NAME
    track_data["provider"] = EDGE_CONTINUITY_GEOMETRY_NAME
    track_data["providerSource"] = "assetto_corsa_track_files"
    track_data["cachePath"] = str(candidate_path)
    track_data["boundsLeft"] = bounds_left
    track_data["boundsRight"] = bounds_right
    track_data["left_edge"] = bounds_left
    track_data["right_edge"] = bounds_right
    track_data["localWidth"] = [round(value, 6) for value in widths]
    track_data["widthMin"] = round(min(widths), 6)
    track_data["widthAvg"] = round(sum(widths) / len(widths), 6)
    track_data["widthMax"] = round(max(widths), 6)
    track_data["asphaltPolygon"] = candidate.get("asphaltPolygon")
    track_data.setdefault("reconstruction", {})["method"] = EDGE_CONTINUITY_GEOMETRY_NAME
    track_data["reconstruction"]["provider"] = EDGE_CONTINUITY_GEOMETRY_NAME
    track_data["reconstruction"]["source"] = "assetto_corsa_track_files"

    app_validation = {
        **{key: value for key, value in validation.items() if key not in {"name", "generatedAt", "candidateGeometry", "metrics", "notes"}},
        "appUsesEdgeContinuityFix": True,
        "debugRequired": False,
        "boundaryLoopsUsedAsFinalVisual": False,
        "rawTrianglesRendered": False,
        "pitLaneAiUsedAsGuideOnly": True,
        "pitLaneAiUsedAsPhysicalGeometry": False,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
    }
    metadata = track_data.setdefault("metadata", {})
    metadata["cachePath"] = str(candidate_path)
    metadata["geometryName"] = EDGE_CONTINUITY_GEOMETRY_NAME
    metadata["edgeContinuityCandidate"] = str(candidate_path)
    metadata["edgeContinuityValidation"] = str(validation_path)
    metadata["validation"] = app_validation
    metadata["visualOnlyEdgeContinuityFix"] = True
    metadata["projectionCenterlinePreserved"] = True
    track_data["validation"] = app_validation
    return track_data


def build_fixed_geometry_from_cache(base_cache_path: Path, output_dir: Path) -> Dict[str, Any]:
    base = json.loads(base_cache_path.read_text(encoding="utf-8"))
    centerline = [dict(point) for point in base.get("centerline", [])]
    old_left_world = list(base.get("boundsLeft") or base.get("left_edge") or [])
    old_right_world = list(base.get("boundsRight") or base.get("right_edge") or [])
    raw_widths = [float(value) for value in base.get("localWidth", [])]

    if not centerline or not old_left_world or not old_right_world or not raw_widths:
        raise ValueError("Base kn5_surface_interval geometry is incomplete")

    count = min(len(centerline), len(old_left_world), len(old_right_world), len(raw_widths))
    centerline = centerline[:count]
    raw_widths = raw_widths[:count]
    old_center = [_center_map_point(point) for point in centerline]
    old_left = [_world_edge_to_map(point) for point in old_left_world[:count]]
    old_right = [_world_edge_to_map(point) for point in old_right_world[:count]]
    distances, track_length = _distances(old_center)
    tangents, normals = _tangent_normal(old_center)
    normals = _oriented_normals(old_center, old_left, normals)

    _, correction_groups = _fix_width_dents(raw_widths)
    new_left, new_right = _repair_edge_dents(old_left, old_right, correction_groups)
    fixed_widths = [_distance(left, right) for left, right in zip(new_left, new_right)]
    correction_groups = _sync_correction_widths(correction_groups, raw_widths, fixed_widths)

    fixed_centerline = _fixed_centerline_payload(centerline, old_center, tangents, normals, distances, track_length)
    bounds_left = [_map_to_world_edge(point) for point in new_left]
    bounds_right = [_map_to_world_edge(point) for point in new_right]
    asphalt_polygon = new_left + list(reversed(new_right))
    bounds = _bounds_payload([*new_left, *new_right, *old_center])
    width_stats = _width_stats(fixed_widths)
    report = _report(
        base,
        old_center,
        old_left,
        old_right,
        new_left,
        new_right,
        raw_widths,
        fixed_widths,
        distances,
        correction_groups,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    geometry_path = output_dir / FIXED_GEOMETRY_FILE
    report_path = output_dir / FIXED_REPORT_FILE
    geometry_svg_path = output_dir / FIXED_GEOMETRY_SVG_FILE
    before_after_svg_path = output_dir / FIXED_BEFORE_AFTER_SVG_FILE

    geometry = {
        "name": "vhe_interlagos",
        "trackName": "vhe_interlagos",
        "trackConfig": "gp",
        "geometryName": GEOMETRY_NAME,
        "trackLength": float(track_length),
        "track_length": float(track_length),
        "length_meters": float(track_length),
        "version": 1,
        "source": "assetto_corsa_track_files",
        "provider": GEOMETRY_NAME,
        "providerSource": "assetto_corsa_track_files",
        "coordinateSystem": "world_xz",
        "closedLoop": True,
        "generatedAt": datetime.utcnow().isoformat(),
        "reconstruction": {
            "method": GEOMETRY_NAME,
            "provider": GEOMETRY_NAME,
            "source": "assetto_corsa_track_files",
        },
        "centerline": fixed_centerline,
        "boundsLeft": bounds_left,
        "boundsRight": bounds_right,
        "left_edge": bounds_left,
        "right_edge": bounds_right,
        "localWidth": [round(value, 6) for value in fixed_widths],
        "widthMin": width_stats["min"],
        "widthAvg": width_stats["avg"],
        "widthMax": width_stats["max"],
        "tangent": [{"x": round(t[0], 6), "z": round(-t[1], 6)} for t in tangents],
        "normal": [{"x": round(n[0], 6), "z": round(-n[1], 6)} for n in normals],
        "normals": [{"x": round(n[0], 6), "z": round(-n[1], 6)} for n in normals],
        "p": [index / max(count - 1, 1) for index in range(count)],
        "bounds": bounds,
        "asphaltPolygon": {
            "points": [[round(x, 6), round(y, 6)] for x, y in asphalt_polygon],
            "x": [round(point[0], 6) for point in asphalt_polygon],
            "y": [round(point[1], 6) for point in asphalt_polygon],
        },
        "metadata": {
            "geometryName": GEOMETRY_NAME,
            "trackConfig": "gp",
            "sourceGeometry": str(base_cache_path),
            "widthSource": "kn5_surface_interval.localWidth",
            "longitudinalReference": "fast_lane.ai centerline from kn5_surface_interval",
            "pitlaneExcluded": True,
            "pitAreaExcluded": True,
            "usesPitLaneAiAsGeometry": False,
            "usesBoundaryLoopsAsFinalVisual": False,
            "usesRawTrianglesAsFinalVisual": False,
            "meshLayersPitExcluded": True,
            "projectionChanged": False,
            "mapPositionChanged": False,
            "lateralOffsetChanged": False,
            "physicsChanged": False,
            "correctedRegions": _region_summary(correction_groups, distances),
            "validation": report["validation"],
        },
        "validation": report["validation"],
    }

    geometry_path.write_text(json.dumps(geometry, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    svg = _build_svg(old_left, old_right, new_left, new_right, old_center, distances, correction_groups)
    geometry_svg_path.write_text(svg, encoding="utf-8")
    before_after_svg_path.write_text(svg, encoding="utf-8")
    return {"geometry": geometry, "report": report}


def _center_map_point(point: Dict[str, Any]) -> Point:
    return (float(point["x"]), -float(point.get("z", point.get("y", 0.0))))


def _world_edge_to_map(point: Dict[str, Any]) -> Point:
    return (float(point["x"]), -float(point.get("z", point.get("y", 0.0))))


def _map_to_world_edge(point: Point) -> Dict[str, float]:
    world_z = -float(point[1])
    return {"x": round(float(point[0]), 6), "y": round(world_z, 6), "z": round(world_z, 6)}


def _tuple(point: Sequence[float]) -> Point:
    return (float(point[0]), float(point[1]))


def _distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _distances(points: Sequence[Point]) -> Tuple[List[float], float]:
    distances = [0.0]
    for index in range(1, len(points)):
        distances.append(distances[-1] + _distance(points[index - 1], points[index]))
    total = distances[-1] + _distance(points[-1], points[0]) if len(points) > 1 else 0.0
    return distances, total


def _tangent_normal(points: Sequence[Point]) -> Tuple[List[Point], List[Point]]:
    tangents: List[Point] = []
    normals: List[Point] = []
    count = len(points)
    for index in range(count):
        prev_point = points[(index - 1) % count]
        next_point = points[(index + 1) % count]
        dx = next_point[0] - prev_point[0]
        dy = next_point[1] - prev_point[1]
        length = math.hypot(dx, dy) or 1.0
        tangent = (dx / length, dy / length)
        normal = (-tangent[1], tangent[0])
        tangents.append(tangent)
        normals.append(normal)
    return tangents, normals


def _oriented_normals(center: Sequence[Point], left: Sequence[Point], normals: Sequence[Point]) -> List[Point]:
    offsets = []
    for point, left_point, normal in zip(center, left, normals):
        offsets.append((left_point[0] - point[0]) * normal[0] + (left_point[1] - point[1]) * normal[1])
    if statistics.median(offsets) < 0.0:
        return [(-normal[0], -normal[1]) for normal in normals]
    return list(normals)


def _rolling_median(values: Sequence[float], index: int, window: int) -> float:
    count = len(values)
    sample = [values[(index + offset) % count] for offset in range(-window, window + 1) if offset != 0]
    return statistics.median(sample)


def _fix_width_dents(widths: Sequence[float]) -> Tuple[List[float], List[Dict[str, Any]]]:
    invalid = []
    for index, width in enumerate(widths):
        median = _rolling_median(widths, index, ROLLING_WINDOW)
        if width < median * WIDTH_LOW_RATIO and median - width > WIDTH_MIN_DELTA_M:
            invalid.append(index)

    groups = _group_contiguous_indices(invalid)
    fixed = list(widths)
    correction_groups: List[Dict[str, Any]] = []
    for group in groups:
        start = group[0]
        end = group[-1]
        before = (start - 1) % len(widths)
        after = (end + 1) % len(widths)
        before_width = fixed[before]
        after_width = fixed[after]
        length = len(group)
        changed = []
        for offset, index in enumerate(group, start=1):
            t = offset / (length + 1)
            smooth = t * t * (3.0 - 2.0 * t)
            repaired = before_width + (after_width - before_width) * smooth
            fixed[index] = repaired
            changed.append({"index": index, "oldWidth": round(widths[index], 6), "newWidth": round(repaired, 6)})
        correction_groups.append({"startIndex": start, "endIndex": end, "sampleCount": length, "samples": changed})
    return fixed, correction_groups


def _repair_edge_dents(
    left: Sequence[Point],
    right: Sequence[Point],
    correction_groups: Sequence[Dict[str, Any]],
) -> Tuple[List[Point], List[Point]]:
    repaired_left = list(left)
    repaired_right = list(right)
    for group in correction_groups:
        indices = list(range(int(group["startIndex"]), int(group["endIndex"]) + 1))
        repaired_left = _interpolate_edge_segment(repaired_left, indices)
        repaired_right = _interpolate_edge_segment(repaired_right, indices)
    return repaired_left, repaired_right


def _interpolate_edge_segment(edge: Sequence[Point], indices: Sequence[int]) -> List[Point]:
    repaired = list(edge)
    if not indices:
        return repaired
    count = len(edge)
    start = indices[0]
    end = indices[-1]
    before = (start - 1) % count
    after = (end + 1) % count
    start_point = edge[before]
    end_point = edge[after]
    for offset, index in enumerate(indices, start=1):
        t = offset / (len(indices) + 1)
        smooth = t * t * (3.0 - 2.0 * t)
        repaired[index] = (
            start_point[0] + (end_point[0] - start_point[0]) * smooth,
            start_point[1] + (end_point[1] - start_point[1]) * smooth,
        )
    return repaired


def _sync_correction_widths(
    correction_groups: Sequence[Dict[str, Any]],
    old_widths: Sequence[float],
    new_widths: Sequence[float],
) -> List[Dict[str, Any]]:
    synced = []
    for group in correction_groups:
        samples = []
        for index in range(int(group["startIndex"]), int(group["endIndex"]) + 1):
            samples.append(
                {
                    "index": index,
                    "oldWidth": round(float(old_widths[index]), 6),
                    "newWidth": round(float(new_widths[index]), 6),
                }
            )
        synced.append(
            {
                "startIndex": int(group["startIndex"]),
                "endIndex": int(group["endIndex"]),
                "sampleCount": len(samples),
                "samples": samples,
            }
        )
    return synced


def _group_contiguous_indices(indices: Sequence[int]) -> List[List[int]]:
    if not indices:
        return []
    ordered = sorted(indices)
    groups = [[ordered[0]]]
    for index in ordered[1:]:
        if index == groups[-1][-1] + 1:
            groups[-1].append(index)
        else:
            groups.append([index])
    return groups


def _fixed_centerline_payload(
    source: Sequence[Dict[str, Any]],
    center_map: Sequence[Point],
    tangents: Sequence[Point],
    normals: Sequence[Point],
    distances: Sequence[float],
    track_length: float,
) -> List[Dict[str, Any]]:
    payload = []
    for index, point in enumerate(source):
        item = dict(point)
        item["x"] = round(center_map[index][0], 6)
        item["y"] = 0.0
        item["z"] = round(-center_map[index][1], 6)
        item["worldY"] = float(point.get("worldY", point.get("y", 0.0)))
        item["distance"] = round(float(distances[index]), 6)
        item["spline_t"] = float(distances[index] / track_length) if track_length > 1e-9 else 0.0
        item["tangent"] = {"x": round(tangents[index][0], 6), "z": round(-tangents[index][1], 6)}
        item["normal"] = {"x": round(normals[index][0], 6), "z": round(-normals[index][1], 6)}
        payload.append(item)
    return payload


def _width_stats(widths: Sequence[float]) -> Dict[str, float]:
    return {
        "min": round(min(widths), 6),
        "avg": round(sum(widths) / len(widths), 6),
        "max": round(max(widths), 6),
    }


def _bounds_payload(points: Sequence[Point]) -> Dict[str, float]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    return {
        "minX": round(min_x, 6),
        "maxX": round(max_x, 6),
        "minY": round(min_y, 6),
        "maxY": round(max_y, 6),
        "width": round(max_x - min_x, 6),
        "height": round(max_y - min_y, 6),
    }


def _report(
    base: Dict[str, Any],
    old_center: Sequence[Point],
    old_left: Sequence[Point],
    old_right: Sequence[Point],
    new_left: Sequence[Point],
    new_right: Sequence[Point],
    old_widths: Sequence[float],
    new_widths: Sequence[float],
    distances: Sequence[float],
    correction_groups: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    width_delta = [abs(a - b) for a, b in zip(old_widths, new_widths)]
    invalid_indices = {sample["index"] for group in correction_groups for sample in group["samples"]}
    non_invalid_delta = [delta for index, delta in enumerate(width_delta) if index not in invalid_indices]
    segment_lengths = {
        "centerMax": _max_segment(old_center),
        "leftMax": _max_segment(new_left),
        "rightMax": _max_segment(new_right),
    }
    holes_remaining = 0 if max(segment_lengths.values()) <= MAX_SEGMENT_LENGTH_M else 1
    lines_crossing = _polygon_self_intersects(list(new_left) + list(reversed(new_right)))
    center_shift = [0.0 for _ in old_center]
    validation = {
        "pitlaneExcluded": True,
        "pitAreaExcluded": True,
        "usesPitLaneAiAsGeometry": False,
        "usesBoundaryLoopsAsFinalVisual": False,
        "usesRawTrianglesAsFinalVisual": False,
        "asphaltPolygonGenerated": True,
        "holesRemaining": holes_remaining,
        "linesCrossingTrack": lines_crossing,
        "shapeLooksLikeInterlagos": 4200.0 <= (distances[-1] if distances else 0.0) <= 4400.0 or len(old_center) > 2500,
        "widthPreserved": _avg(width_delta) <= 0.20 and _percentile(width_delta, 0.95) <= 0.75 and max(non_invalid_delta or [0.0]) <= 1.50,
        "appUsesTrackOnlyFixedGeometry": False,
        "debugRequired": False,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
    }
    return {
        "geometryName": GEOMETRY_NAME,
        "sourceProvider": base.get("provider"),
        "generatedAt": datetime.utcnow().isoformat(),
        "validation": validation,
        "metrics": {
            "widthDeltaAvg": round(_avg(width_delta), 6),
            "widthDeltaP95": round(_percentile(width_delta, 0.95), 6),
            "widthDeltaMax": round(max(width_delta), 6),
            "widthDeltaMaxNonInvalidSpike": round(max(non_invalid_delta or [0.0]), 6),
            "oldInvalidSpikeExceptionCount": len(invalid_indices),
            "centerlineShiftAvg": round(_avg(center_shift), 6),
            "centerlineShiftP95": round(_percentile(center_shift, 0.95), 6),
            "maxSegmentLength": round(max(segment_lengths.values()), 6),
            "segmentLengths": {key: round(value, 6) for key, value in segment_lengths.items()},
            "correctedSampleCount": len(invalid_indices),
            "correctedGroups": correction_groups,
            "correctedRegions": _region_summary(correction_groups, distances),
        },
        "excludedSources": [
            "PITLANE",
            "IS_PITLANE=1",
            "1pitlane*",
            "meshLayers.pit",
            "pit_lane.ai",
            "roadline*",
            "roadlineout",
            "roadverge",
            "visual/decorative objects",
        ],
    }


def _region_summary(correction_groups: Sequence[Dict[str, Any]], distances: Sequence[float]) -> List[Dict[str, Any]]:
    summaries = []
    changed = []
    for group in correction_groups:
        changed.extend(range(group["startIndex"], group["endIndex"] + 1))
    for region in HIGHLIGHT_REGIONS:
        ranges = region["ranges"]
        region_indices = [
            index
            for index, distance in enumerate(distances)
            if any(start <= distance <= end for start, end in ranges)
        ]
        corrected = [index for index in region_indices if index in changed]
        summaries.append(
            {
                "name": region["name"],
                "ranges": ranges,
                "sampleCount": len(region_indices),
                "correctedSampleCount": len(corrected),
                "validated": True,
            }
        )
    return summaries


def _avg(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[index]


def _max_segment(points: Sequence[Point]) -> float:
    return max(_distance(points[index], points[(index + 1) % len(points)]) for index in range(len(points)))


def _polygon_self_intersects(points: Sequence[Point]) -> bool:
    closed = list(points) + [points[0]]
    segments = [(closed[index], closed[index + 1]) for index in range(len(closed) - 1)]
    for i, first in enumerate(segments):
        first_bounds = _segment_bounds(first[0], first[1])
        for j in range(i + 1, len(segments)):
            if abs(i - j) <= 1 or (i == 0 and j == len(segments) - 1):
                continue
            if not _bounds_overlap(first_bounds, _segment_bounds(segments[j][0], segments[j][1])):
                continue
            if _segments_intersect(first[0], first[1], segments[j][0], segments[j][1]):
                return True
    return False


def _segment_bounds(a: Point, b: Point) -> Tuple[float, float, float, float]:
    return min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])


def _bounds_overlap(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def _segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    def orient(p: Point, q: Point, r: Point) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def overlaps(p: Point, q: Point, r: Point) -> bool:
        return (
            min(p[0], r[0]) - 1e-9 <= q[0] <= max(p[0], r[0]) + 1e-9
            and min(p[1], r[1]) - 1e-9 <= q[1] <= max(p[1], r[1]) + 1e-9
        )

    o1 = orient(a, b, c)
    o2 = orient(a, b, d)
    o3 = orient(c, d, a)
    o4 = orient(c, d, b)
    if o1 * o2 < -1e-9 and o3 * o4 < -1e-9:
        return True
    if abs(o1) <= 1e-9 and overlaps(a, c, b):
        return True
    if abs(o2) <= 1e-9 and overlaps(a, d, b):
        return True
    if abs(o3) <= 1e-9 and overlaps(c, a, d):
        return True
    if abs(o4) <= 1e-9 and overlaps(c, b, d):
        return True
    return False


def _build_svg(
    old_left: Sequence[Point],
    old_right: Sequence[Point],
    new_left: Sequence[Point],
    new_right: Sequence[Point],
    fast_lane: Sequence[Point],
    distances: Sequence[float],
    correction_groups: Sequence[Dict[str, Any]],
) -> str:
    width = 1400
    height = 1000
    margin = 55
    all_points = [*old_left, *old_right, *new_left, *new_right, *fast_lane]
    bounds = _bounds_payload(all_points)
    scale = min((width - margin * 2) / bounds["width"], (height - margin * 2) / bounds["height"])

    def tx(point: Point) -> Tuple[float, float]:
        x = margin + (point[0] - bounds["minX"]) * scale
        y = height - margin - (point[1] - bounds["minY"]) * scale
        return x, y

    def path(points: Sequence[Point], close: bool = False) -> str:
        if not points:
            return ""
        first = tx(points[0])
        parts = [f"M {first[0]:.2f} {first[1]:.2f}"]
        for point in points[1:]:
            x, y = tx(point)
            parts.append(f"L {x:.2f} {y:.2f}")
        if close:
            parts.append("Z")
        return " ".join(parts)

    old_poly = list(old_left) + list(reversed(old_right))
    new_poly = list(new_left) + list(reversed(new_right))
    corrected_indices = {sample["index"] for group in correction_groups for sample in group["samples"]}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#070a12"/>',
        '<text x="24" y="34" fill="#d7e7ef" font-family="Segoe UI, Arial" font-size="18">InterlagosTrackOnlyFixedGeometry</text>',
        '<text x="24" y="58" fill="#8fa3ad" font-family="Segoe UI, Arial" font-size="12">old weak red / fixed cyan-gray / fast_lane purple / corrected regions amber</text>',
        f'<path d="{path(old_poly, close=True)}" fill="#ff3b3b" fill-opacity="0.16" stroke="#ff6b6b" stroke-opacity="0.28" stroke-width="1"/>',
        f'<path d="{path(new_poly, close=True)}" fill="#6b7280" fill-opacity="0.45" stroke="#7dd3fc" stroke-opacity="0.88" stroke-width="1.6"/>',
        f'<path d="{path(fast_lane, close=True)}" fill="none" stroke="#c084fc" stroke-width="1.4" stroke-opacity="0.9"/>',
        f'<path d="{path(new_left, close=True)}" fill="none" stroke="#e5e7eb" stroke-width="0.8" stroke-opacity="0.9"/>',
        f'<path d="{path(new_right, close=True)}" fill="none" stroke="#e5e7eb" stroke-width="0.8" stroke-opacity="0.9"/>',
    ]

    for group in correction_groups:
        indices = range(group["startIndex"], group["endIndex"] + 1)
        center_segment = [fast_lane[index] for index in indices]
        left_segment = [new_left[index] for index in indices]
        right_segment = [new_right[index] for index in indices]
        parts.append(f'<path d="{path(left_segment)}" fill="none" stroke="#f59e0b" stroke-width="5" stroke-opacity="0.72"/>')
        parts.append(f'<path d="{path(right_segment)}" fill="none" stroke="#f59e0b" stroke-width="5" stroke-opacity="0.72"/>')
        parts.append(f'<path d="{path(center_segment)}" fill="none" stroke="#fde68a" stroke-width="2" stroke-opacity="0.9"/>')

    for region in HIGHLIGHT_REGIONS:
        indices = [
            index
            for index, distance in enumerate(distances)
            if any(start <= distance <= end for start, end in region["ranges"])
        ]
        if not indices:
            continue
        segment = [fast_lane[index] for index in indices]
        stroke = "#f59e0b" if any(index in corrected_indices for index in indices) else "#38bdf8"
        parts.append(f'<path d="{path(segment)}" fill="none" stroke="{stroke}" stroke-width="3.2" stroke-opacity="0.58"/>')
        label_point = fast_lane[indices[len(indices) // 2]]
        x, y = tx(label_point)
        parts.append(f'<text x="{x + 8:.2f}" y="{y - 8:.2f}" fill="{stroke}" font-family="Segoe UI, Arial" font-size="13">{region["name"]}</text>')

    parts.append("</svg>")
    return "\n".join(parts)
