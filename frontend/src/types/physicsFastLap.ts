export type PhysicsParameterSource = 'REAL_TELEMETRY' | 'ESTIMATED' | 'CONFIG_DEFAULT' | 'UNAVAILABLE';
export type PhysicsLimitingFactor =
  | 'CURVATURE'
  | 'BRAKING'
  | 'ACCELERATION'
  | 'STRAIGHT_SPEED'
  | 'DATA_LIMITED'
  | 'UNKNOWN';
export type PhysicsConfidence = 'HIGH' | 'MEDIUM' | 'LOW' | 'INSUFFICIENT_DATA';

export interface PhysicsParameterValue {
  value: number | null;
  source: PhysicsParameterSource;
}

export interface PhysicsModelParameters {
  massKg: PhysicsParameterValue;
  maxLateralG: PhysicsParameterValue;
  maxAccelerationMs2: PhysicsParameterValue;
  maxBrakingMs2: PhysicsParameterValue;
  surfaceGrip: PhysicsParameterValue;
  airTemp: PhysicsParameterValue;
  roadTemp: PhysicsParameterValue;
}

export interface PhysicsLapSegment {
  segmentIndex: number;
  sector: 1 | 2 | 3;
  splineStart: number;
  splineEnd: number;
  distanceStartMeters: number | null;
  distanceEndMeters: number | null;
  segmentLengthMeters: number | null;
  curvature: number | null;
  radiusMeters: number | null;
  playerAvgSpeedKmh: number | null;
  referenceAvgSpeedKmh: number | null;
  physicsTargetSpeedKmh: number | null;
  playerEstimatedTimeSeconds: number | null;
  referenceEstimatedTimeSeconds: number | null;
  physicsTargetTimeSeconds: number | null;
  playerVsPhysicsDeltaSeconds: number | null;
  referenceVsPhysicsDeltaSeconds: number | null;
  limitingFactor: PhysicsLimitingFactor;
  confidence: PhysicsConfidence;
}

export interface PhysicsFastLapReport {
  status: 'READY' | 'INSUFFICIENT_DATA';
  track: string | null;
  generatedAt: string;
  source: 'REFERENCE_RACING_LINE' | 'BEST_LAP' | 'UNKNOWN';
  referenceLapNumber: number | null;
  microSectorCount: number;
  parameters: PhysicsModelParameters;
  summary: {
    estimatedPhysicsLapTimeSeconds: number | null;
    referenceLapTimeSeconds: number | null;
    playerCurrentEstimatedLapTimeSeconds: number | null;
    playerLossToPhysicsSeconds: number | null;
    referenceLossToPhysicsSeconds: number | null;
    biggestLossSector: 1 | 2 | 3 | null;
    biggestLimitingFactor: PhysicsLimitingFactor | null;
  };
  sectors: Array<{
    sector: 1 | 2 | 3;
    physicsTargetTimeSeconds: number | null;
    playerEstimatedTimeSeconds: number | null;
    deltaSeconds: number | null;
    mainLimitingFactor: PhysicsLimitingFactor | null;
  }>;
  segments: PhysicsLapSegment[];
  debug: {
    visualLineSamples: number;
    validDistanceSamples: number;
    validCurvatureSegments: number;
    rejectedSegments: number;
    usedEstimatedParameters: string[];
    unavailableParameters: string[];
    warnings: string[];
    physicsTargetCacheHit?: boolean;
    physicsTargetCacheEntries?: number;
  };
}
