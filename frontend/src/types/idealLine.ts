export type IdealLineSource =
  | 'REFERENCE_LAP'
  | 'BEST_PLAYER_LAP'
  | 'BEST_OPPONENT_LAP'
  | 'PHYSICS_SIMULATION'
  | 'UNKNOWN';

export interface IdealLineVisualPoint {
  x: number | null;
  y: number | null;
  z: number | null;
  splinePosition: number | null;
  speedKmh: number | null;
  lapTime?: number | null;
  position?: {
    x: number | null;
    y: number | null;
    z: number | null;
  };
}

export interface IdealLineOverlayData {
  source: IdealLineSource;
  referenceLapNumber: number | null;
  points: IdealLineVisualPoint[];
  minSpeedKmh: number | null;
  maxSpeedKmh: number | null;
  generatedAt: string;
}

export type LineOverlayMode =
  | 'OFF'
  | 'LINE'
  | 'DIAG'
  | 'PEDAL';
