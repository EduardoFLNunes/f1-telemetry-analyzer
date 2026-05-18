/**
 * Global Telemetry State Store (Zustand)
 * Manages live frames, ring buffers, and intelligence events.
 */
import { create } from 'zustand';

export interface TelemetryFrame {
  driver_id: string;
  lap_number: number;
  lap_time: number;
  s: number; // Distance into lap
  L: number | null; // Lateral offset
  speed: number;
  throttle: number;
  brake: number;
  steering: number;
  gear: number;
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

interface TelemetryState {
  // Live Data
  latestFrame: TelemetryFrame | null;
  history: TelemetryFrame[];
  ghostHistory: TelemetryFrame[]; // For comparison
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

export const useTelemetryStore = create<TelemetryState>((set) => ({
  latestFrame: null,
  history: [],
  ghostHistory: [],
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

    // ring buffer optimization
    const newHistory = state.history.length >= MAX_HISTORY 
      ? [...state.history.slice(1), safeFrame]
      : [...state.history, safeFrame];

    return {
      latestFrame: safeFrame,
      history: newHistory,
      globalCursorS: state.isStreaming ? safeFrame.s : state.globalCursorS
    };
  }),

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
    coachingEvents: [], 
    engineerSpeech: [], 
    cognitiveState: null, 
    latestFrame: null,
    ghostHistory: []
  })
}));
