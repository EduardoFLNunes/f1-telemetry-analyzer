export type TelemetryDataSource = 'ASSETTO_REAL' | 'INFERRED' | 'UNAVAILABLE';
export type DataCompleteness = 'FULL' | 'PARTIAL' | 'MINIMAL';
export type AccelerationState = 'BRAKING' | 'ACCELERATING' | 'COASTING' | 'UNKNOWN';
export type GripLevel = 'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN';

export interface CarPhysicsTelemetry {
  source: {
    playerPhysicsAvailable: boolean;
    opponentPhysicsAvailable: boolean;
    dataCompleteness: DataCompleteness;
  };
  motion: {
    speedKmh: number | null;
    velocity?: {
      x: number | null;
      y: number | null;
      z: number | null;
    };
    accG?: {
      lateral: number | null;
      longitudinal: number | null;
      vertical: number | null;
    };
  };
  controls: {
    throttle: number | null;
    brake: number | null;
    clutch?: number | null;
    steerAngle?: number | null;
    gear: number | null;
    rpm: number | null;
  };
  tyres: {
    tyreCoreTemperature: Array<number | null>;
    tyrePressure: Array<number | null>;
    tyreWear: Array<number | null>;
    tyreDirtyLevel: Array<number | null>;
    wheelSlip: Array<number | null>;
    wheelLoad: Array<number | null>;
    estimatedGripIndex?: Array<number | null>;
  };
  suspension: {
    suspensionTravel: Array<number | null>;
    rideHeight: Array<number | null>;
    camberRad?: Array<number | null>;
  };
  carState: {
    fuel: number | null;
    maxFuel?: number | null;
    ballast?: number | null;
    carDamage?: Array<number | null>;
    abs?: number | null;
    tc?: number | null;
    drs?: boolean | null;
    turboBoost?: number | null;
  };
  environment: {
    airTemp: number | null;
    roadTemp: number | null;
    surfaceGrip: number | null;
    airDensity?: number | null;
  };
  inferred: {
    estimatedAccelerationState: AccelerationState;
    estimatedGripLevel: GripLevel;
    estimatedMassKg?: number | null;
    estimatedDragState?: 'LOW' | 'MEDIUM' | 'HIGH' | 'UNKNOWN';
  };
  availability: {
    hasRealThrottle: boolean;
    hasRealBrake: boolean;
    hasRealTyreData: boolean;
    hasRealSuspensionData: boolean;
    hasRealEnvironmentData: boolean;
    hasInferredGrip: boolean;
    hasInferredAccelerationState: boolean;
  };
}

export interface CarPhysicsDebug {
  playerPhysicsSamples: number;
  opponentPhysicsSamples: number;
  playerDataCompleteness: DataCompleteness;
  opponentDataCompleteness: DataCompleteness;
  missingPlayerFields: string[];
  missingOpponentFields: string[];
  inferredFields: string[];
  unavailableFields: string[];
}

export interface CarPhysicsResponse {
  status: string;
  source: string;
  track: string | null;
  generatedAt: string;
  player: CarPhysicsTelemetry;
  opponents: Array<{ carId: number; physics: CarPhysicsTelemetry }>;
  carPhysicsDebug: CarPhysicsDebug;
}
