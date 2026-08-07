import axios, { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { API_BASE_URL } from '../config/runtime';

type RequestMetadata = { startedAt: number };
type ConfigWithMetadata = InternalAxiosRequestConfig & { metadata?: RequestMetadata };

const BASE_URL = API_BASE_URL;

const client = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

function perfTarget(): Record<string, any> | null {
  if (typeof window === 'undefined') return null;
  window.__telemetryPerf = window.__telemetryPerf || {};
  return window.__telemetryPerf;
}

function nowMs(): number {
  return typeof performance !== 'undefined' && performance.now ? performance.now() : Date.now();
}

function payloadKbFromResponse(response?: AxiosResponse | null): number {
  const headerValue = response?.headers?.['content-length'];
  const headerNumber = Number(headerValue);
  if (Number.isFinite(headerNumber) && headerNumber >= 0) {
    return headerNumber / 1024;
  }
  try {
    return JSON.stringify(response?.data ?? '').length / 1024;
  } catch {
    return 0;
  }
}

function recordHttpPerf(config?: ConfigWithMetadata, status: 'success' | 'error' = 'success', response: AxiosResponse | null = null) {
  const metrics = perfTarget();
  if (!metrics || !config?.metadata?.startedAt) return;
  const duration = nowMs() - config.metadata.startedAt;
  const payloadKb = response ? payloadKbFromResponse(response) : 0;
  metrics.httpRequests = (metrics.httpRequests || 0) + 1;
  metrics.httpDurationMs = (metrics.httpDurationMs || 0) + duration;
  metrics.httpPayloadKb = (metrics.httpPayloadKb || 0) + payloadKb;
  metrics.httpErrors = (metrics.httpErrors || 0) + (status === 'error' ? 1 : 0);
  metrics.httpEndpoints = metrics.httpEndpoints || {};
  const key = config.url || 'unknown';
  const endpoint = metrics.httpEndpoints[key] || { count: 0, durationMs: 0, errors: 0, payloadKb: 0, lastPayloadKb: 0 };
  endpoint.count += 1;
  endpoint.durationMs += duration;
  endpoint.payloadKb += payloadKb;
  endpoint.lastPayloadKb = payloadKb;
  endpoint.errors += status === 'error' ? 1 : 0;
  metrics.httpEndpoints[key] = endpoint;
  if (key.includes('/api/live/telemetry')) metrics.telemetryPayloadKb = payloadKb;
  if (key.includes('/api/live/racing-line')) metrics.racingLinePayloadKb = payloadKb;
}

client.interceptors.request.use((config: ConfigWithMetadata) => {
  config.metadata = { ...(config.metadata || {}), startedAt: nowMs() };
  return config;
});

client.interceptors.response.use(
  (response: AxiosResponse) => {
    recordHttpPerf(response.config as ConfigWithMetadata, 'success', response);
    return response;
  },
  (error: AxiosError) => {
    recordHttpPerf(error.config as ConfigWithMetadata | undefined, 'error');
    return Promise.reject(error);
  },
);

type AssistedAnalysisOptions = {
  includeExternalReference?: boolean;
  externalReferenceId?: string | null;
};

type RequestAssistedAnalysisOptions = {
  referenceLapId?: string | null;
  force?: boolean;
  includeExternalReference?: boolean;
  externalReferenceId?: string | null;
};

type LiveTelemetryOptions = {
  includeTrack?: boolean;
  includeTrajectory?: boolean;
};

type RacingLineOptions = {
  includeVisualLine?: boolean;
  includeComparison?: boolean;
};

export const api = {
  // ─── Track / Telemetry ───────────────────────────────────────────────────
  uploadTrack: async (file: File): Promise<any> => {
    const fd = new FormData();
    fd.append('file', file);
    const res = await client.post('/api/upload/track', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },

  uploadTelemetry: async (file: File): Promise<any> => {
    const fd = new FormData();
    fd.append('file', file);
    const res = await client.post('/api/upload/telemetry', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },

  getTrackData: async (): Promise<any> => (await client.get('/api/data/track')).data,
  getCurrentTrack: async (): Promise<any> => (await client.get('/api/track/current')).data,
  getTrackGeometry: async (): Promise<any> => (await client.get('/api/track/geometry')).data,
  getTrackCache: async (): Promise<any> => (await client.get('/api/track/cache')).data,
  getCarState: async (): Promise<any> => (await client.get('/api/car/state')).data,
  getHealth: async (): Promise<any> => (await client.get('/api/health')).data,
  getRuntimeStatus: async (): Promise<any> => (await client.get('/api/runtime/status')).data,
  getDataQuality: async (): Promise<any> => (await client.get('/api/validation/data-quality')).data,
  getLiveTelemetry: async (options: LiveTelemetryOptions = {}): Promise<any> => (
    await client.get('/api/live/telemetry', {
      params: {
        includeTrack: options.includeTrack,
        includeTrajectory: options.includeTrajectory,
      },
    })
  ).data,
  getLiveComparison: async (microSectors = 50): Promise<any> => (
    await client.get('/api/live/comparison', { params: { microSectors } })
  ).data,
  getRacingLine: async (microSectors = 50, options: RacingLineOptions = {}): Promise<any> => (
    await client.get('/api/live/racing-line', {
      params: {
        microSectors,
        includeVisualLine: options.includeVisualLine,
        includeComparison: options.includeComparison,
      },
    })
  ).data,
  getPlayerPhysics: async (): Promise<any> => (await client.get('/api/live/player-physics')).data,
  getRecordingStatus: async (): Promise<any> => (await client.get('/api/recording/status')).data,
  getSessions: async (limit = 30): Promise<any> => (await client.get('/api/sessions', { params: { limit } })).data,
  getSession: async (sessionId: string): Promise<any> => (
    await client.get(`/api/sessions/${encodeURIComponent(sessionId)}`)
  ).data,
  getSessionLaps: async (sessionId: string): Promise<any> => (
    await client.get(`/api/sessions/${encodeURIComponent(sessionId)}/laps`)
  ).data,
  getSessionLap: async (sessionId: string, lapNumber: number): Promise<any> => (
    await client.get(`/api/sessions/${encodeURIComponent(sessionId)}/laps/${lapNumber}`)
  ).data,
  getOfflineLap: async (lapId: string): Promise<any> => (
    await client.get(`/api/laps/${encodeURIComponent(lapId)}`)
  ).data,
  getOfflineLapSummary: async (lapId: string): Promise<any> => (
    await client.get(`/api/laps/${encodeURIComponent(lapId)}/summary`)
  ).data,
  getOfflineLapSamples: async (lapId: string, limit = 10_000): Promise<any> => (
    await client.get(`/api/laps/${encodeURIComponent(lapId)}/samples`, { params: { limit } })
  ).data,
  getOfflineLapReplay: async (lapId: string, maxSamples = 36_000): Promise<any> => (
    await client.get(`/api/laps/${encodeURIComponent(lapId)}/replay`, { params: { maxSamples } })
  ).data,
  getTelemetryData: async (): Promise<any> => (await client.get('/api/data/telemetry')).data,
  getAiRaceline: async (): Promise<any> => (await client.get('/api/data/ai-raceline')).data,
  getComparison: async (): Promise<any> => (await client.get('/api/data/comparison')).data,
  getTrackLimits: async (): Promise<any> => (await client.get('/api/data/track-limits')).data,

  listAssistedAnalysisLaps: async (): Promise<any> => (await client.get('/api/assisted-analysis/laps')).data,
  getAssistedLapTelemetry: async (lapId: string, maxSamples = 36_000): Promise<any> => (
    await client.get(`/api/analysis/assisted/lap/${encodeURIComponent(lapId)}/telemetry`, {
      params: { maxSamples },
    })
  ).data,
  getAssistedAnalysis: async (lapId: string, referenceLapId: string | null = null, options: AssistedAnalysisOptions = {}): Promise<any> => {
    const res = await client.get(`/api/analysis/assisted/lap/${encodeURIComponent(lapId)}`, {
      params: {
        ...(referenceLapId ? { reference_lap_id: referenceLapId } : {}),
        ...(options.includeExternalReference ? { includeExternalReference: true } : {}),
        ...(options.externalReferenceId ? { externalReferenceId: options.externalReferenceId } : {}),
      },
    });
    return res.data;
  },
  requestAssistedAnalysis: async (lapId: string, {
    referenceLapId = null,
    force = false,
    includeExternalReference = false,
    externalReferenceId = null,
  }: RequestAssistedAnalysisOptions = {}): Promise<any> => {
    const res = await client.post(
      `/api/analysis/assisted/lap/${encodeURIComponent(lapId)}`,
      { referenceLapId, force, includeExternalReference, externalReferenceId },
      { timeout: 120_000 },
    );
    return res.data;
  },
  listExternalReferences: async (): Promise<any> => (await client.get('/api/references/external')).data,
  importFastF1Reference: async (payload: Record<string, unknown>): Promise<any> => (
    await client.post('/api/references/external/fastf1/import', payload, { timeout: 180_000 })
  ).data,
};

export default client;
