/**
 * Global Telemetry State Store (Zustand)
 * Manages live frames, ring buffers, and intelligence events.
 */
import { create } from 'zustand';

export interface TelemetryFrame {
  driver_id: string;
  lap_number: number;
  lap?: number;
  lap_time: number;
  s: number; // Distance into lap
  L: number | null; // Lateral offset
  speed: number;
  speedKmh?: number;
  throttle: number;
  brake: number;
  steering: number;
  gear: number;
  p?: number | null;
  spline_t?: number | null;
  splinePosition?: number | null;
  normalizedSplinePosition?: number | null;
  distanceAlongTrack?: number | null;
  sessionTime?: number | null;
  session_time?: number | null;
  lapProgress?: number | null;
  lapSampleTime?: number | null;
  heading?: number; // Car yaw/heading in radians
  slip_angle?: number;
  lateral_g?: number;
  yaw_rate?: number;
  accel_g: { 
    x: number; // Lateral G
    y: number; // Vertical G
    z: number; // Longitudinal G
  };
  delta: number;
  x: number;
  y?: number;
  z: number;
  world_x?: number;
  world_y?: number;
  world_z?: number;
  mapPosition?: { x: number; y: number };
  projectedPosition?: { x: number; y: number } | null;
  projectedWorldPosition?: [number, number, number];
  projected_x?: number;
  projected_y?: number;
  projected_z?: number;
  dx?: number;
  dz?: number;
  alignment_drift?: number | null;
  bootstrap_conf?: number;
  is_pitlane?: boolean;
  bootstrap_src?: string;
  timestamp: number;
  corner_id?: number;
  corner_type?: string;
  predicted_lap_time?: number;
  tire_slip?: number;
  yaw_rate?: number;
  drs?: boolean;
}

export interface OpponentWorldPosition {
  x: number | null;
  y: number | null;
  z: number | null;
}

export interface OpponentCarState {
  carId: number;
  driverName?: string | null;
  carModel?: string | null;
  isPlayer: boolean;
  isAI?: boolean | null;
  worldPosition?: OpponentWorldPosition | null;
  mapPosition?: { x: number; y: number } | null;
  speedKmh?: number | null;
  yaw?: number | null;
  splinePosition?: number | null;
  lap?: number | null;
  lapTime?: number | null;
  racePosition?: number | null;
  status?: string | null;
  timestamp?: number | null;
  sessionTime?: number | null;
  lastSeenTimestamp?: number | null;
}

export interface OpponentsSnapshot {
  source?: string;
  count?: number;
  track?: string | null;
  sessionTime?: number | null;
  timestamp?: number | null;
  lastUpdateTimestamp?: number | null;
  staleAfterSeconds?: number | null;
  opponents?: OpponentCarState[];
  cars?: OpponentCarState[];
}

export interface CoachingEvent {
  type: string;
  event: string;
  severity: number;
  evidence: any;
  driver_id: string;
  lap_number: number;
  s: number;
  timestamp: number;
  corner_id?: number;
}

export interface EngineerSpeech {
  message: string;
  priority: 'low' | 'medium' | 'high';
  timestamp: number;
  category?: 'physics' | 'strategy' | 'driver' | 'system';
}

export interface CognitiveState {
  metrics: {
    confidence: number;
    aggression: number;
    smoothness: number;
    consistency: number;
    fatigue?: number;
    focus?: number;
  };
  state: 'steady' | 'pushing' | 'overdriving' | 'recovering' | 'fatigued';
  timestamp: number;
}

export interface SectorData {
  id: number;
  start_s: number;
  end_s: number;
  best_time?: number;
  current_time?: number;
}

export interface LapMetrics {
  currentLapNumber: number | null;
  previousLapNumber: number | null;
  referenceLapNumber: number | null;
  currentLapTime: number | null;
  delta: number | null;
  lapDelta: number | null;
  progress: number | null;
  hasPreviousLap: boolean;
}

export interface CompletedLap {
  lapNumber: number;
  samples: TelemetryFrame[];
  valid: boolean;
  progressStart: number | null;
  progressEnd: number | null;
  duration: number | null;
  transitionReason: string;
  rejectedReason: string | null;
}

export interface LapDebugState {
  currentLapNumber: number | null;
  referenceLapNumber: number | null;
  currentLapSamplesLength: number;
  previousLapSamplesLength: number;
  currentLapIsPartial: boolean;
  lastCompletedLapNumber: number | null;
  lastLapTransitionReason: string | null;
  lastRejectedLapReason: string | null;
  previousLapValid: boolean;
  finalizedProgressStart: number | null;
  finalizedProgressEnd: number | null;
  finalizedLapDuration: number | null;
}

interface TelemetryState {
  // Live Data
  latestFrame: TelemetryFrame | null;
  history: TelemetryFrame[];
  ghostHistory: TelemetryFrame[]; // For comparison
  currentLapSamples: TelemetryFrame[];
  previousLapSamples: TelemetryFrame[];
  completedLapsByNumber: Record<number, CompletedLap>;
  completedLapsHistory: CompletedLap[];
  currentLapStartTime: number | null;
  currentLapIsPartial: boolean;
  lastLapTransitionAtTime: number | null;
  lapMetrics: LapMetrics;
  lapDebug: LapDebugState;
  opponents: OpponentCarState[];
  opponentsMeta: {
    source: string;
    count: number;
    track: string | null;
    sessionTime: number | null;
    lastUpdateTimestamp: number | null;
    staleAfterSeconds: number | null;
  };
  lastOpponentsUpdateAt: number | null;
  coachingEvents: CoachingEvent[];
  engineerSpeech: EngineerSpeech[];
  cognitiveState: CognitiveState | null;
  sectors: SectorData[];
  
  // UI State
  isStreaming: boolean;
  globalCursorS: number | null;
  selectedLap: number | null;
  viewMode: 'live' | 'analysis' | 'replay';
  
  // Actions
  addFrame: (frame: TelemetryFrame) => void;
  setOpponentsSnapshot: (snapshot: OpponentsSnapshot) => void;
  clearOpponents: () => void;
  setGhostHistory: (history: TelemetryFrame[]) => void;
  addCoachingEvent: (event: CoachingEvent) => void;
  addEngineerSpeech: (speech: EngineerSpeech) => void;
  setCognitiveState: (state: CognitiveState) => void;
  setStreaming: (status: boolean) => void;
  setGlobalCursor: (s: number | null) => void;
  setSectors: (sectors: SectorData[]) => void;
  setViewMode: (mode: 'live' | 'analysis' | 'replay') => void;
  clearHistory: () => void;
}

// Increased for professional analysis (approx 2 minutes of 60Hz data)
export const MAX_HISTORY = 7200; 
const MAX_LAP_SAMPLES = 5000;
const MAX_COMPLETED_LAPS = 10;
const MIN_VALID_LAP_SAMPLES = 40;
const MIN_VALID_LAP_DURATION = 20;
const MAX_VALID_LAP_DURATION = 900;
const INITIAL_LAP_PARTIAL_PROGRESS = 0.12;
const VALID_LAP_START_PROGRESS = 0.18;
const VALID_LAP_END_PROGRESS = 0.82;
const MIN_TRANSITION_INTERVAL_SECONDS = 5;

const EMPTY_LAP_METRICS: LapMetrics = {
  currentLapNumber: null,
  previousLapNumber: null,
  referenceLapNumber: null,
  currentLapTime: null,
  delta: null,
  lapDelta: null,
  progress: null,
  hasPreviousLap: false,
};

const EMPTY_LAP_DEBUG: LapDebugState = {
  currentLapNumber: null,
  referenceLapNumber: null,
  currentLapSamplesLength: 0,
  previousLapSamplesLength: 0,
  currentLapIsPartial: false,
  lastCompletedLapNumber: null,
  lastLapTransitionReason: null,
  lastRejectedLapReason: null,
  previousLapValid: false,
  finalizedProgressStart: null,
  finalizedProgressEnd: null,
  finalizedLapDuration: null,
};

const finiteNumberOrNull = (value: unknown): number | null => {
  if (typeof value !== 'number') return null;
  return Number.isFinite(value) ? value : null;
};

const numericOrNull = (value: unknown): number | null => {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};

const clamp01 = (value: number): number => Math.max(0, Math.min(1, value));

const nullableString = (value: unknown): string | null => {
  if (value === null || value === undefined) return null;
  const text = String(value).trim();
  return text || null;
};

const frameLapNumber = (frame: Partial<TelemetryFrame>): number | null => {
  const lapNumber = numericOrNull(frame.lap_number);
  if (lapNumber !== null) return lapNumber;
  return numericOrNull(frame.lap);
};

const frameTimeSeconds = (frame: Partial<TelemetryFrame>): number | null => {
  const timestamp = numericOrNull(frame.timestamp);
  if (timestamp !== null) {
    return timestamp > 100_000_000_000 ? timestamp / 1000 : timestamp;
  }

  const sessionTime = numericOrNull(frame.sessionTime ?? frame.session_time);
  if (sessionTime !== null) return sessionTime;
  return null;
};

const frameLapTimeSeconds = (frame: Partial<TelemetryFrame>): number | null => {
  const explicitLapTime = numericOrNull(frame.lap_time);
  if (explicitLapTime !== null && explicitLapTime > 0) return explicitLapTime;

  const sessionTime = numericOrNull(frame.sessionTime ?? frame.session_time);
  if (sessionTime !== null && sessionTime >= 0 && sessionTime < 1800) return sessionTime;
  return null;
};

const frameProgress = (frame: Partial<TelemetryFrame>): number | null => {
  const candidates = [
    frame.lapProgress,
    frame.p,
    frame.normalizedSplinePosition,
    frame.splinePosition,
    frame.spline_t,
  ];
  for (const candidate of candidates) {
    const value = numericOrNull(candidate);
    if (value !== null && value >= 0 && value <= 1) return clamp01(value);
  }
  return null;
};

const lapElapsedForSample = (sample: TelemetryFrame, lapStartTime: number | null): number | null => {
  const lapTime = frameLapTimeSeconds(sample);
  if (lapTime !== null) return lapTime;

  const sampleTime = numericOrNull(sample.lapSampleTime);
  if (sampleTime === null || lapStartTime === null) return null;
  return Math.max(0, sampleTime - lapStartTime);
};

const elapsedSeriesForLap = (samples: TelemetryFrame[]) => {
  if (samples.length < 2) return [];
  const firstTime = numericOrNull(samples[0].lapSampleTime);
  const startTime = firstTime ?? 0;
  return samples
    .map((sample) => {
      const progress = numericOrNull(sample.lapProgress);
      if (progress === null) return null;
      const lapTime = frameLapTimeSeconds(sample);
      const sampleTime = numericOrNull(sample.lapSampleTime);
      const elapsed = lapTime !== null
        ? lapTime
        : (sampleTime !== null ? Math.max(0, sampleTime - startTime) : null);
      if (elapsed === null) return null;
      return { progress: clamp01(progress), elapsed };
    })
    .filter((item): item is { progress: number; elapsed: number } => Boolean(item))
    .sort((a, b) => a.progress - b.progress);
};

const elapsedDistanceSeriesForLap = (samples: TelemetryFrame[]) => {
  if (samples.length < 2) return [];
  const firstTime = numericOrNull(samples[0].lapSampleTime);
  const startTime = firstTime ?? 0;
  return samples
    .map((sample) => {
      const distance = numericOrNull(sample.s ?? sample.distanceAlongTrack);
      if (distance === null) return null;
      const lapTime = frameLapTimeSeconds(sample);
      const sampleTime = numericOrNull(sample.lapSampleTime);
      const elapsed = lapTime !== null
        ? lapTime
        : (sampleTime !== null ? Math.max(0, sampleTime - startTime) : null);
      if (elapsed === null) return null;
      return { distance, elapsed };
    })
    .filter((item): item is { distance: number; elapsed: number } => Boolean(item))
    .sort((a, b) => a.distance - b.distance);
};

const previousElapsedAtProgress = (samples: TelemetryFrame[], progress: number | null): number | null => {
  if (progress === null) return null;
  const points = elapsedSeriesForLap(samples);
  if (points.length < 2) return null;

  let before = points[0];
  let after = points[points.length - 1];
  for (let i = 1; i < points.length; i += 1) {
    if (points[i].progress >= progress) {
      before = points[i - 1];
      after = points[i];
      break;
    }
  }

  if (progress < before.progress || progress > after.progress) {
    const nearest = points.reduce((best, point) => (
      Math.abs(point.progress - progress) < Math.abs(best.progress - progress) ? point : best
    ), points[0]);
    return Math.abs(nearest.progress - progress) <= 0.02 ? nearest.elapsed : null;
  }

  const range = after.progress - before.progress;
  if (range <= 0) return before.elapsed;
  const t = (progress - before.progress) / range;
  return before.elapsed + (after.elapsed - before.elapsed) * t;
};

const previousElapsedAtDistance = (samples: TelemetryFrame[], distance: number | null): number | null => {
  if (distance === null) return null;
  const points = elapsedDistanceSeriesForLap(samples);
  if (points.length < 2) return null;

  let before = points[0];
  let after = points[points.length - 1];
  for (let i = 1; i < points.length; i += 1) {
    if (points[i].distance >= distance) {
      before = points[i - 1];
      after = points[i];
      break;
    }
  }

  if (distance < before.distance || distance > after.distance) return null;
  const range = after.distance - before.distance;
  if (range <= 0) return before.elapsed;
  const t = (distance - before.distance) / range;
  return before.elapsed + (after.elapsed - before.elapsed) * t;
};

const lapProgressRange = (samples: TelemetryFrame[]) => {
  const progressValues = samples
    .map((sample) => numericOrNull(sample.lapProgress))
    .filter((value): value is number => value !== null);
  if (!progressValues.length) {
    return { start: null, end: null, min: null, max: null };
  }
  return {
    start: progressValues[0],
    end: progressValues[progressValues.length - 1],
    min: Math.min(...progressValues),
    max: Math.max(...progressValues),
  };
};

const lapDuration = (samples: TelemetryFrame[]): number | null => {
  if (samples.length < 2) return null;
  const firstElapsed = lapElapsedForSample(samples[0], numericOrNull(samples[0].lapSampleTime));
  const lastElapsed = lapElapsedForSample(samples[samples.length - 1], numericOrNull(samples[0].lapSampleTime));
  if (firstElapsed !== null && lastElapsed !== null && lastElapsed >= firstElapsed) {
    return lastElapsed - firstElapsed;
  }

  const firstTime = numericOrNull(samples[0].lapSampleTime);
  const lastTime = numericOrNull(samples[samples.length - 1].lapSampleTime);
  if (firstTime === null || lastTime === null || lastTime < firstTime) return null;
  return lastTime - firstTime;
};

const isInitialPartialLap = (frame: TelemetryFrame): boolean => {
  const progress = numericOrNull(frame.lapProgress);
  if (progress !== null) return progress > INITIAL_LAP_PARTIAL_PROGRESS;

  const lapTime = frameLapTimeSeconds(frame);
  if (lapTime !== null) return lapTime > 8;

  const distance = numericOrNull(frame.s ?? frame.distanceAlongTrack);
  return distance !== null && distance > 250;
};

const detectLapTransition = (
  frame: TelemetryFrame,
  currentLapSamples: TelemetryFrame[],
  currentLapNumber: number | null,
  lastTransitionAtTime: number | null,
): string | null => {
  if (!currentLapSamples.length) return null;

  const sampleTime = numericOrNull(frame.lapSampleTime);
  if (
    sampleTime !== null &&
    lastTransitionAtTime !== null &&
    sampleTime - lastTransitionAtTime < MIN_TRANSITION_INTERVAL_SECONDS
  ) {
    return null;
  }

  const nextLapNumber = frameLapNumber(frame);
  if (nextLapNumber !== null && currentLapNumber !== null && nextLapNumber > currentLapNumber) {
    return "lap_number_changed";
  }

  const previous = currentLapSamples[currentLapSamples.length - 1];
  const previousProgress = numericOrNull(previous.lapProgress);
  const nextProgress = numericOrNull(frame.lapProgress);
  if (previousProgress !== null && nextProgress !== null && previousProgress > 0.82 && nextProgress < 0.18) {
    return "progress_wrap";
  }

  return null;
};

const finalizeLap = (
  lapNumber: number | null,
  samples: TelemetryFrame[],
  currentLapIsPartial: boolean,
  transitionReason: string,
): CompletedLap => {
  const progress = lapProgressRange(samples);
  const duration = lapDuration(samples);
  let rejectedReason: string | null = null;

  if (lapNumber === null) {
    rejectedReason = "missing_lap_number";
  } else if (currentLapIsPartial) {
    rejectedReason = "initial_partial_lap";
  } else if (samples.length < MIN_VALID_LAP_SAMPLES) {
    rejectedReason = "too_few_samples";
  } else if (duration === null) {
    rejectedReason = "missing_lap_duration";
  } else if (duration < MIN_VALID_LAP_DURATION) {
    rejectedReason = "lap_too_short";
  } else if (duration > MAX_VALID_LAP_DURATION) {
    rejectedReason = "lap_too_long";
  } else if (
    progress.min !== null &&
    progress.max !== null &&
    (progress.min > VALID_LAP_START_PROGRESS || progress.max < VALID_LAP_END_PROGRESS)
  ) {
    rejectedReason = "insufficient_progress_coverage";
  }

  return {
    lapNumber: lapNumber ?? -1,
    samples,
    valid: rejectedReason === null,
    progressStart: progress.start,
    progressEnd: progress.end,
    duration,
    transitionReason,
    rejectedReason,
  };
};

const pruneCompletedLapsByNumber = (
  lapsByNumber: Record<number, CompletedLap>,
  history: CompletedLap[],
  keepLapNumbers: Array<number | null | undefined>,
): Record<number, CompletedLap> => {
  const keep = new Set<number>();
  history.slice(-MAX_COMPLETED_LAPS).forEach((lap) => keep.add(lap.lapNumber));
  keepLapNumbers.forEach((lapNumber) => {
    if (typeof lapNumber === 'number' && Number.isFinite(lapNumber)) {
      keep.add(lapNumber);
    }
  });

  let changed = false;
  const next: Record<number, CompletedLap> = {};
  Object.entries(lapsByNumber).forEach(([key, lap]) => {
    const lapNumber = Number(key);
    if (keep.has(lapNumber)) {
      next[lapNumber] = lap;
    } else {
      changed = true;
    }
  });

  return changed ? next : lapsByNumber;
};

const calculateLapMetrics = (
  currentLapSamples: TelemetryFrame[],
  previousLapSamples: TelemetryFrame[],
  currentLapNumber: number | null,
  referenceLapNumber: number | null,
  currentLapStartTime: number | null,
): LapMetrics => {
  const latest = currentLapSamples[currentLapSamples.length - 1];
  if (!latest) return EMPTY_LAP_METRICS;

  const progress = numericOrNull(latest.lapProgress);
  const currentLapTime = lapElapsedForSample(latest, currentLapStartTime);
  const previousElapsed = previousElapsedAtProgress(previousLapSamples, progress)
    ?? previousElapsedAtDistance(previousLapSamples, numericOrNull(latest.s ?? latest.distanceAlongTrack));
  const delta = currentLapTime !== null && previousElapsed !== null
    ? currentLapTime - previousElapsed
    : null;

  return {
    currentLapNumber,
    previousLapNumber: referenceLapNumber,
    referenceLapNumber,
    currentLapTime,
    delta,
    lapDelta: delta,
    progress,
    hasPreviousLap: referenceLapNumber !== null && previousLapSamples.length > 1,
  };
};

const normalizeOpponent = (raw: any): OpponentCarState | null => {
  const carId = Number(raw?.carId);
  if (!Number.isFinite(carId)) return null;
  if (raw?.isPlayer === true) return null;

  const world = raw?.worldPosition && typeof raw.worldPosition === 'object'
    ? raw.worldPosition
    : null;
  const worldPosition = world
    ? {
        x: finiteNumberOrNull(world.x),
        y: finiteNumberOrNull(world.y),
        z: finiteNumberOrNull(world.z),
      }
    : null;
  const hasWorldPosition =
    worldPosition?.x !== null &&
    worldPosition?.z !== null;

  return {
    carId,
    driverName: nullableString(raw?.driverName),
    carModel: nullableString(raw?.carModel),
    isPlayer: false,
    isAI: typeof raw?.isAI === 'boolean' ? raw.isAI : null,
    worldPosition,
    mapPosition: hasWorldPosition
      ? { x: worldPosition.x as number, y: -(worldPosition.z as number) }
      : null,
    speedKmh: finiteNumberOrNull(raw?.speedKmh),
    yaw: finiteNumberOrNull(raw?.yaw),
    splinePosition: finiteNumberOrNull(raw?.splinePosition),
    lap: finiteNumberOrNull(raw?.lap),
    lapTime: finiteNumberOrNull(raw?.lapTime),
    racePosition: finiteNumberOrNull(raw?.racePosition),
    status: nullableString(raw?.status),
    timestamp: finiteNumberOrNull(raw?.timestamp),
    sessionTime: finiteNumberOrNull(raw?.sessionTime),
    lastSeenTimestamp: finiteNumberOrNull(raw?.lastSeenTimestamp),
  };
};

export const useTelemetryStore = create<TelemetryState>((set) => ({
  latestFrame: null,
  history: [],
  ghostHistory: [],
  currentLapSamples: [],
  previousLapSamples: [],
  completedLapsByNumber: {},
  completedLapsHistory: [],
  currentLapStartTime: null,
  currentLapIsPartial: false,
  lastLapTransitionAtTime: null,
  lapMetrics: EMPTY_LAP_METRICS,
  lapDebug: EMPTY_LAP_DEBUG,
  opponents: [],
  opponentsMeta: {
    source: 'opponents_collector',
    count: 0,
    track: null,
    sessionTime: null,
    lastUpdateTimestamp: null,
    staleAfterSeconds: null,
  },
  lastOpponentsUpdateAt: null,
  coachingEvents: [],
  engineerSpeech: [],
  cognitiveState: null,
  sectors: [],
  isStreaming: false,
  globalCursorS: null,
  selectedLap: null,
  viewMode: 'live',

  addFrame: (frame) => set((state) => {
    const mapPosition = frame.mapPosition && isFinite(frame.mapPosition.x) && isFinite(frame.mapPosition.y)
      ? frame.mapPosition
      : { x: frame.x, y: frame.y ?? frame.z };
    const projectedPosition = frame.projectedPosition && isFinite(frame.projectedPosition.x) && isFinite(frame.projectedPosition.y)
      ? frame.projectedPosition
      : undefined;

    // Sanitization: Ensure coordinates and critical values are valid numbers
    const safeFrame: TelemetryFrame = {
      ...frame,
      mapPosition,
      projectedPosition,
      lap_number: numericOrNull(frame.lap_number) ?? numericOrNull(frame.lap) ?? state.lapMetrics.currentLapNumber ?? 0,
      x: isFinite(mapPosition.x) ? mapPosition.x : (state.latestFrame?.x || 0),
      y: isFinite(mapPosition.y) ? mapPosition.y : (state.latestFrame?.y || 0),
      z: isFinite(mapPosition.y) ? mapPosition.y : (state.latestFrame?.z || 0),
      projected_x: projectedPosition?.x ?? frame.projected_x,
      projected_y: projectedPosition?.y ?? frame.projected_y,
      projected_z: projectedPosition?.y ?? frame.projected_z,
      speed: isFinite(frame.speed) ? frame.speed : 0,
      steering: isFinite(frame.steering) ? frame.steering : 0,
      heading: isFinite(frame.heading as number) ? (frame.heading as number) : (state.latestFrame?.heading || 0),
      slip_angle: isFinite(frame.slip_angle || 0) ? (frame.slip_angle || 0) : 0,
      throttle: isFinite(frame.throttle) ? Math.max(0, Math.min(1, frame.throttle)) : 0,
      brake: isFinite(frame.brake) ? Math.max(0, Math.min(1, frame.brake)) : 0,
    };
    safeFrame.lapProgress = frameProgress(safeFrame);
    safeFrame.lapSampleTime = frameTimeSeconds(safeFrame);

    let currentLapSamples = state.currentLapSamples;
    let previousLapSamples = state.previousLapSamples;
    let completedLapsByNumber = state.completedLapsByNumber;
    let completedLapsHistory = state.completedLapsHistory;
    let currentLapNumber = state.lapMetrics.currentLapNumber;
    let referenceLapNumber = state.lapMetrics.referenceLapNumber;
    let currentLapStartTime = state.currentLapStartTime;
    let currentLapIsPartial = state.currentLapIsPartial;
    let lastLapTransitionAtTime = state.lastLapTransitionAtTime;
    let lastCompletedLapNumber = state.lapDebug.lastCompletedLapNumber;
    let lastLapTransitionReason = state.lapDebug.lastLapTransitionReason;
    let lastRejectedLapReason = state.lapDebug.lastRejectedLapReason;
    let finalizedProgressStart = state.lapDebug.finalizedProgressStart;
    let finalizedProgressEnd = state.lapDebug.finalizedProgressEnd;
    let finalizedLapDuration = state.lapDebug.finalizedLapDuration;
    const nextLapNumber = frameLapNumber(safeFrame);
    const lapReset = (
      nextLapNumber !== null &&
      currentLapNumber !== null &&
      nextLapNumber + 1 < currentLapNumber
    );

    if (!currentLapSamples.length || lapReset) {
      currentLapSamples = [safeFrame];
      previousLapSamples = lapReset ? [] : previousLapSamples;
      completedLapsByNumber = lapReset ? {} : completedLapsByNumber;
      completedLapsHistory = lapReset ? [] : completedLapsHistory;
      currentLapNumber = nextLapNumber;
      referenceLapNumber = lapReset ? null : referenceLapNumber;
      currentLapStartTime = safeFrame.lapSampleTime ?? null;
      currentLapIsPartial = isInitialPartialLap(safeFrame);
      lastLapTransitionAtTime = lapReset ? safeFrame.lapSampleTime ?? null : lastLapTransitionAtTime;
      if (lapReset) {
        lastLapTransitionReason = "lap_counter_reset";
        lastRejectedLapReason = "session_reset";
        lastCompletedLapNumber = null;
        finalizedProgressStart = null;
        finalizedProgressEnd = null;
        finalizedLapDuration = null;
      }
    } else {
      const transitionReason = detectLapTransition(
        safeFrame,
        currentLapSamples,
        currentLapNumber,
        lastLapTransitionAtTime,
      );

      if (transitionReason) {
        const finalizedLap = finalizeLap(
          currentLapNumber,
          currentLapSamples,
          currentLapIsPartial,
          transitionReason,
        );
        lastLapTransitionReason = transitionReason;
        lastRejectedLapReason = finalizedLap.rejectedReason;
        finalizedProgressStart = finalizedLap.progressStart;
        finalizedProgressEnd = finalizedLap.progressEnd;
        finalizedLapDuration = finalizedLap.duration;
        if (finalizedLap.valid) {
          completedLapsByNumber = {
            ...completedLapsByNumber,
            [finalizedLap.lapNumber]: finalizedLap,
          };
          completedLapsHistory = [...completedLapsHistory, finalizedLap].slice(-MAX_COMPLETED_LAPS);
          lastCompletedLapNumber = finalizedLap.lapNumber;
        }

        const newLapNumber = nextLapNumber ?? (currentLapNumber !== null ? currentLapNumber + 1 : null);
        const referenceLap = newLapNumber !== null ? completedLapsByNumber[newLapNumber - 1] : undefined;
        referenceLapNumber = referenceLap?.valid ? referenceLap.lapNumber : null;
        previousLapSamples = referenceLap?.valid ? referenceLap.samples : [];
        currentLapSamples = [safeFrame];
        currentLapNumber = newLapNumber;
        currentLapStartTime = safeFrame.lapSampleTime ?? null;
        currentLapIsPartial = false;
        lastLapTransitionAtTime = safeFrame.lapSampleTime ?? lastLapTransitionAtTime;
      } else {
        currentLapSamples = currentLapSamples.length >= MAX_LAP_SAMPLES
          ? [...currentLapSamples.slice(1), safeFrame]
          : [...currentLapSamples, safeFrame];
        currentLapNumber = currentLapNumber ?? nextLapNumber;
        currentLapStartTime = currentLapStartTime ?? safeFrame.lapSampleTime ?? null;
      }
    }

    if (currentLapNumber !== null && referenceLapNumber === null && completedLapsByNumber[currentLapNumber - 1]?.valid) {
      const referenceLap = completedLapsByNumber[currentLapNumber - 1];
      referenceLapNumber = referenceLap.lapNumber;
      previousLapSamples = referenceLap.samples;
    }
    completedLapsByNumber = pruneCompletedLapsByNumber(
      completedLapsByNumber,
      completedLapsHistory,
      [referenceLapNumber, currentLapNumber !== null ? currentLapNumber - 1 : null, lastCompletedLapNumber],
    );

    const lapMetrics = calculateLapMetrics(
      currentLapSamples,
      previousLapSamples,
      currentLapNumber,
      referenceLapNumber,
      currentLapStartTime,
    );
    const lapDebug: LapDebugState = {
      currentLapNumber,
      referenceLapNumber,
      currentLapSamplesLength: currentLapSamples.length,
      previousLapSamplesLength: previousLapSamples.length,
      currentLapIsPartial,
      lastCompletedLapNumber,
      lastLapTransitionReason,
      lastRejectedLapReason,
      previousLapValid: previousLapSamples.length > 1 && referenceLapNumber !== null,
      finalizedProgressStart,
      finalizedProgressEnd,
      finalizedLapDuration,
    };
    if (lapMetrics.delta !== null) {
      safeFrame.delta = lapMetrics.delta;
    }

    // ring buffer optimization
    const newHistory = state.history.length >= MAX_HISTORY 
      ? [...state.history.slice(1), safeFrame]
      : [...state.history, safeFrame];

    return {
      latestFrame: safeFrame,
      history: newHistory,
      currentLapSamples,
      previousLapSamples,
      completedLapsByNumber,
      completedLapsHistory,
      currentLapStartTime,
      currentLapIsPartial,
      lastLapTransitionAtTime,
      lapMetrics,
      lapDebug,
      globalCursorS: state.isStreaming ? safeFrame.s : state.globalCursorS
    };
  }),

  setOpponentsSnapshot: (snapshot) => set(() => {
    const rawOpponents = Array.isArray(snapshot.opponents)
      ? snapshot.opponents
      : (Array.isArray(snapshot.cars) ? snapshot.cars : []);
    const opponents = rawOpponents
      .map(normalizeOpponent)
      .filter((car): car is OpponentCarState => Boolean(car));

    return {
      opponents,
      opponentsMeta: {
        source: snapshot.source || 'opponents_collector',
        count: Number.isFinite(snapshot.count) ? Number(snapshot.count) : opponents.length,
        track: nullableString(snapshot.track),
        sessionTime: finiteNumberOrNull(snapshot.sessionTime),
        lastUpdateTimestamp: finiteNumberOrNull(snapshot.lastUpdateTimestamp ?? snapshot.timestamp),
        staleAfterSeconds: finiteNumberOrNull(snapshot.staleAfterSeconds),
      },
      lastOpponentsUpdateAt: Date.now(),
    };
  }),

  clearOpponents: () => set((state) => ({
    opponents: [],
    opponentsMeta: {
      ...state.opponentsMeta,
      count: 0,
      lastUpdateTimestamp: null,
    },
    lastOpponentsUpdateAt: Date.now(),
  })),

  setGhostHistory: (ghostHistory) => set({ ghostHistory }),

  addCoachingEvent: (event) => set((state) => ({
    coachingEvents: [event, ...state.coachingEvents].slice(0, 100)
  })),

  addEngineerSpeech: (speech) => set((state) => ({
    engineerSpeech: [speech, ...state.engineerSpeech].slice(0, 50)
  })),

  setCognitiveState: (state) => set({ cognitiveState: state }),

  setStreaming: (status) => set({ isStreaming: status }),
  
  setGlobalCursor: (s) => set({ globalCursorS: s }),

  setSectors: (sectors) => set({ sectors }),

  setViewMode: (viewMode) => set({ viewMode }),

  clearHistory: () => set({ 
    history: [], 
    currentLapSamples: [],
    previousLapSamples: [],
    completedLapsByNumber: {},
    completedLapsHistory: [],
    currentLapStartTime: null,
    currentLapIsPartial: false,
    lastLapTransitionAtTime: null,
    lapMetrics: EMPTY_LAP_METRICS,
    lapDebug: EMPTY_LAP_DEBUG,
    opponents: [],
    opponentsMeta: {
      source: 'opponents_collector',
      count: 0,
      track: null,
      sessionTime: null,
      lastUpdateTimestamp: null,
      staleAfterSeconds: null,
    },
    lastOpponentsUpdateAt: null,
    coachingEvents: [], 
    engineerSpeech: [], 
    cognitiveState: null, 
    latestFrame: null,
    ghostHistory: [],
    globalCursorS: null,
  })
}));
