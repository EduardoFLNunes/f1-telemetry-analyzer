import { useEffect, useMemo, useState } from 'react';

export interface PitLaneDebugPoint {
  x: number;
  y: number;
}

export interface PitLaneDebugGeometry {
  name: string;
  role: string;
  centerline: PitLaneDebugPoint[];
  leftEdge: PitLaneDebugPoint[];
  rightEdge: PitLaneDebugPoint[];
  width?: number[];
  pointCount: number;
  lengthMeters: number;
  start?: PitLaneDebugPoint | null;
  end?: PitLaneDebugPoint | null;
  removedStartMeters?: number;
  removedEndMeters?: number;
  widthStats?: { min?: number | null; avg?: number | null; max?: number | null };
  provider?: string;
  method?: string;
  transform?: Record<string, unknown>;
  confidence?: string;
  openLoop?: boolean;
  runtimeChanged?: boolean;
}

export interface PitAccessGeometry {
  name: string;
  kind: 'entry' | 'exit';
  coordinateSystem: string;
  centerline: PitLaneDebugPoint[];
  leftEdge?: PitLaneDebugPoint[];
  rightEdge?: PitLaneDebugPoint[];
  pointCount: number;
  lengthMeters: number;
  startPoint?: PitLaneDebugPoint;
  endPoint?: PitLaneDebugPoint;
  confidence?: string;
  usesPhysicalSurface?: boolean;
  edgesGenerated?: boolean;
  runtimeChanged?: boolean;
  authoritativeGeometryChanged?: boolean;
  readyForRuntimeIntegration?: boolean;
  surfaceFootprint?: {
    triangleCount?: number;
    sampleTriangles?: Array<{ meshName?: string; surface?: string; vertices: PitLaneDebugPoint[] }>;
  };
}

export interface PitAreaGeometry {
  active: boolean;
  name: string;
  method?: string;
  provider?: string;
  sourceMeshCount?: number;
  triangleCount?: number;
  corridorDetected?: boolean;
  entryAccessDetected?: boolean;
  exitAccessDetected?: boolean;
  confidence?: string;
  runtimeChanged?: boolean;
  authoritativeGeometryChanged?: boolean;
  readyForRuntimeIntegration?: boolean;
  surface?: {
    triangleCount?: number;
    sampleTriangles?: Array<{ meshName?: string; surfaceName?: string; component?: string; vertices: PitLaneDebugPoint[] }>;
    boundaryLoops?: Array<{ loopId?: number; points: PitLaneDebugPoint[] }>;
    sourceMeshes?: Record<string, number>;
    sourceSurfaces?: Record<string, number>;
  };
  components?: {
    components?: Array<{
      name: string;
      detected: boolean;
      triangleCount: number;
      confidence?: string;
      sampleTriangles?: Array<{ meshName?: string; surfaceName?: string; component?: string; vertices: PitLaneDebugPoint[] }>;
    }>;
  };
  centerlines?: {
    centerlines?: Record<string, { centerline: PitLaneDebugPoint[]; pointCount?: number; confidence?: string }>;
    aiReferences?: Record<string, { source?: string; usage?: string; centerline: PitLaneDebugPoint[]; pointCount?: number }>;
  };
  meshInventory?: Record<string, unknown>;
  overlayAlignmentCheck?: Record<string, unknown>;
  finalReport?: Record<string, unknown>;
}

export interface MainTrackZoneCandidate {
  suspectedStartIndex?: number;
  suspectedEndIndex?: number;
  anchorStartIndex?: number;
  anchorEndIndex?: number;
  originalSegment?: PitLaneDebugPoint[];
  candidateSegment?: PitLaneDebugPoint[];
  maxCorrectionDisplacement?: number;
  avgCorrectionDisplacement?: number;
  runtimeChanged?: boolean;
  readyForRuntimeIntegration?: boolean;
}

export interface PitTransitionCandidate {
  id: string;
  mainTrackIndex: number;
  startPoint: PitLaneDebugPoint;
  endPoint: PitLaneDebugPoint;
  centerline: PitLaneDebugPoint[];
  length: number;
  maxCurvature: number;
  directionDiffAtStart: number;
  directionDiffAtEnd: number;
  distanceToMain: number;
  source: string;
  score: number;
  selectedAutomatically: boolean;
}

export interface PitLaneDebugPayload {
  trackName: string;
  trackConfig: string;
  canonicalMapSpace: string;
  debugOnly: boolean;
  runtimeChanged: boolean;
  activePitlaneDebugVersion?: string;
  mainTrack: PitLaneDebugGeometry;
  pitAreaGeometry?: PitAreaGeometry;
  pitLaneCorridorV2?: {
    active: boolean;
    geometry: PitLaneDebugGeometry;
    surface?: {
      bounds?: Record<string, number>;
      boundaryLoops: Array<{ loopId?: number; points: PitLaneDebugPoint[] }>;
      triangleCount?: number;
      sourceMeshNames?: string[];
    };
    provider?: string;
    method?: string;
    transform?: Record<string, unknown>;
    confidence?: string;
    openLoop?: boolean;
    runtimeChanged?: boolean;
    readyForRuntimeIntegration?: boolean;
    report?: Record<string, unknown>;
    assessment?: Record<string, unknown>;
  };
  pitlaneV2?: {
    active: boolean;
    geometry: PitLaneDebugGeometry;
    surface?: {
      bounds?: Record<string, number>;
      boundaryLoops: Array<{ loopId?: number; points: PitLaneDebugPoint[] }>;
      triangleCount?: number;
      sourceMeshNames?: string[];
    };
    provider?: string;
    method?: string;
    transform?: Record<string, unknown>;
    confidence?: string;
    openLoop?: boolean;
    runtimeChanged?: boolean;
    readyForRuntimeIntegration?: boolean;
    report?: Record<string, unknown>;
    assessment?: Record<string, unknown>;
  };
  pitEntryAccess?: PitAccessGeometry;
  pitExitAccess?: PitAccessGeometry;
  pitAccessLocalMeshInventory?: Record<string, unknown>;
  pitlaneOverlayAlignmentCheck?: Record<string, unknown>;
  pitAccessFinalReport?: Record<string, unknown>;
  pitlaneLegacy?: {
    active: boolean;
    geometry?: PitLaneDebugGeometry;
    raw?: PitLaneDebugGeometry;
    surface?: {
      bounds?: Record<string, number>;
      boundaryLoops: Array<{ loopId?: number; points: PitLaneDebugPoint[] }>;
      triangleCount?: number;
    };
    transformB?: Record<string, unknown>;
    runtimeChanged?: boolean;
    note?: string;
  };
  pitlaneSurface: {
    bounds?: Record<string, number>;
    boundaryLoops: Array<{ loopId?: number; points: PitLaneDebugPoint[] }>;
    triangleCount?: number;
  };
  pitlaneRaw: PitLaneDebugGeometry;
  pitlaneTrimmedManual: PitLaneDebugGeometry;
  selectedCandidate?: PitLaneDebugGeometry | null;
  trimCandidates: PitLaneDebugGeometry[];
  pitlaneTransformB?: {
    transformUsed: string;
    debugOnly: boolean;
    runtimeChanged: boolean;
    readyForRuntimeIntegration: boolean;
    surface?: {
      bounds?: Record<string, number>;
      boundaryLoops: Array<{ loopId?: number; points: PitLaneDebugPoint[] }>;
      triangleCount?: number;
    };
    raw?: PitLaneDebugGeometry;
    trimCandidates?: PitLaneDebugGeometry[];
    highlightedCandidate?: PitLaneDebugGeometry | null;
    spatialValidation?: Record<string, unknown>;
    regenerationReport?: Record<string, unknown>;
  };
  entryExitBreaksCombinedAnalysis?: Record<string, unknown>;
  mainTrackEntryZoneCandidate?: MainTrackZoneCandidate;
  mainTrackExitZoneCandidate?: MainTrackZoneCandidate;
  mainTrackExitZoneCandidateV2?: MainTrackZoneCandidate;
  pitEntryTransitionCandidates?: { candidates: PitTransitionCandidate[] };
  pitExitTransitionCandidatesV2?: { candidates: PitTransitionCandidate[] };
  entryExitBreaksFinalReport?: Record<string, unknown>;
  validationMetadata: {
    selectedManualTrim: string;
    aggressiveTrimRejected: boolean;
    runtimeChanged: boolean;
    readyForRuntimeIntegration: boolean;
    rawPointCount: number;
    trimmedPointCount: number;
    rawLengthMeters: number;
    trimmedLengthMeters: number;
    removedStartMeters: number;
    removedEndMeters: number;
  };
  exports?: Record<string, string>;
}

export interface PitLaneDebugState {
  data: PitLaneDebugPayload | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

export function usePitLaneDebugData(enabled: boolean): PitLaneDebugState {
  const [data, setData] = useState<PitLaneDebugPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    if (!enabled) return undefined;

    const controller = new AbortController();
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`http://${window.location.hostname}:8000/api/debug/pitlane/current`, {
          cache: 'no-store',
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const payload = await response.json();
        setData(payload.pitlane || payload);
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    };

    load();
    return () => controller.abort();
  }, [enabled, reloadToken]);

  return useMemo(
    () => ({
      data,
      loading,
      error,
      reload: () => setReloadToken((value) => value + 1),
    }),
    [data, loading, error],
  );
}
