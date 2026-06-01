export type RacingLineConfidence = 'HIGH' | 'MEDIUM' | 'LOW' | 'INSUFFICIENT_DATA';
export type RacingLineSource = 'REFERENCE_LAP' | 'BEST_LAP' | 'COMPOSITE' | 'IMPORTED' | 'UNKNOWN';
export type RacingLineStatus = 'READY' | 'INSUFFICIENT_DATA';
export type RacingLineIssue =
  | 'TRAJECTORY'
  | 'BRAKING_TOO_EARLY'
  | 'BRAKING_TOO_LATE'
  | 'ACCELERATING_TOO_LATE'
  | 'LOW_CORNER_SPEED'
  | 'LOW_EXIT_SPEED'
  | 'GOOD'
  | 'UNKNOWN'
  | 'INSUFFICIENT_DATA';

export interface RacingLinePoint {
  segmentIndex: number;
  splineStart: number;
  splineEnd: number;
  sector: 1 | 2 | 3;
  position: {
    x: number | null;
    y: number | null;
    z: number | null;
  };
  avgSpeedKmh: number | null;
  minSpeedKmh: number | null;
  maxSpeedKmh: number | null;
  brakingZone: boolean;
  accelerationZone: boolean;
  coastingZone: boolean;
  estimatedCurvature: number | null;
  confidence: RacingLineConfidence;
  sampleCount: number;
}

export interface RacingLineVisualPoint {
  splinePosition: number | null;
  position: {
    x: number | null;
    y: number | null;
    z: number | null;
  };
  speedKmh: number | null;
  brake: number | null;
  throttle: number | null;
  timestamp: number | null;
}

export interface RacingLineVisualLine {
  source: 'REFERENCE_LAP_SAMPLES';
  sampleCount: number;
  displayPointCount: number;
  downsampleStride: number;
  smoothingApplied: boolean;
  points: RacingLineVisualPoint[];
}

export interface RacingLineModel {
  track: string;
  source: RacingLineSource;
  referenceLapNumber: number | null;
  microSectorCount: number;
  generatedAt: string;
  points: RacingLinePoint[];
  visualLine?: RacingLineVisualLine;
  debug: {
    inputSamples: number;
    validSegments: number;
    rejectedSegments: number;
    missingPositionSamples: number;
    missingSpeedSamples: number;
    smoothingApplied: boolean;
    sourceLapWasPartial: boolean;
  };
}

export interface RacingLineComparisonSegment {
  segmentIndex: number;
  splineStart: number;
  splineEnd: number;
  sector: 1 | 2 | 3;
  playerSpeedKmh: number | null;
  racingLineSpeedKmh: number | null;
  speedDeltaKmh: number | null;
  trajectoryDeviationMeters: number | null;
  playerBraking: boolean | null;
  racingLineBraking: boolean | null;
  playerAccelerating: boolean | null;
  racingLineAccelerating: boolean | null;
  estimatedDeltaSeconds: number | null;
  mainIssue: RacingLineIssue;
  message: string;
}

export interface RacingLineComparison {
  track: string;
  generatedAt: string;
  comparedAgainst: 'REFERENCE_LAP' | 'BEST_LAP' | 'COMPOSITE';
  sectorSummary: Array<{
    sector: 1 | 2 | 3;
    estimatedDeltaSeconds: number | null;
    biggestIssue: string | null;
    worstSegmentIndex: number | null;
  }>;
  biggestLosses: RacingLineComparisonSegment[];
  biggestGains: RacingLineComparisonSegment[];
  segments: RacingLineComparisonSegment[];
  debug: {
    playerSamples: number;
    racingLinePoints: number;
    validComparisonSegments: number;
    rejectedComparisonSegments: number;
    reasonForRejectedSegments: string[];
  };
}

export interface RacingLinePayload {
  track: string;
  status: RacingLineStatus;
  racingLine: RacingLineModel | null;
  comparison: RacingLineComparison | null;
  debug: Record<string, any>;
}
