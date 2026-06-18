import axios from 'axios'
import { API_BASE_URL } from '../config/runtime'

const BASE_URL = API_BASE_URL

const client = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

function perfTarget() {
  if (typeof window === 'undefined') return null
  window.__telemetryPerf = window.__telemetryPerf || {}
  return window.__telemetryPerf
}

function nowMs() {
  return typeof performance !== 'undefined' && performance.now ? performance.now() : Date.now()
}

function payloadKbFromResponse(response) {
  const headerValue = response?.headers?.['content-length']
  const headerNumber = Number(headerValue)
  if (Number.isFinite(headerNumber) && headerNumber >= 0) {
    return headerNumber / 1024
  }
  try {
    return JSON.stringify(response?.data ?? '').length / 1024
  } catch {
    return 0
  }
}

function recordHttpPerf(config, status = 'success', response = null) {
  const metrics = perfTarget()
  if (!metrics || !config?.metadata?.startedAt) return
  const duration = nowMs() - config.metadata.startedAt
  const payloadKb = response ? payloadKbFromResponse(response) : 0
  metrics.httpRequests = (metrics.httpRequests || 0) + 1
  metrics.httpDurationMs = (metrics.httpDurationMs || 0) + duration
  metrics.httpPayloadKb = (metrics.httpPayloadKb || 0) + payloadKb
  metrics.httpErrors = (metrics.httpErrors || 0) + (status === 'error' ? 1 : 0)
  metrics.httpEndpoints = metrics.httpEndpoints || {}
  const key = config.url || 'unknown'
  const endpoint = metrics.httpEndpoints[key] || { count: 0, durationMs: 0, errors: 0, payloadKb: 0, lastPayloadKb: 0 }
  endpoint.count += 1
  endpoint.durationMs += duration
  endpoint.payloadKb += payloadKb
  endpoint.lastPayloadKb = payloadKb
  endpoint.errors += status === 'error' ? 1 : 0
  metrics.httpEndpoints[key] = endpoint
  if (key.includes('/api/live/telemetry')) metrics.telemetryPayloadKb = payloadKb
  if (key.includes('/api/live/racing-line')) metrics.racingLinePayloadKb = payloadKb
}

client.interceptors.request.use((config) => {
  config.metadata = { ...(config.metadata || {}), startedAt: nowMs() }
  return config
})

client.interceptors.response.use(
  (response) => {
    recordHttpPerf(response.config, 'success', response)
    return response
  },
  (error) => {
    recordHttpPerf(error.config, 'error')
    return Promise.reject(error)
  },
)

export const api = {
  // ─── Track / Telemetry ───────────────────────────────────────────────────
  uploadTrack: async (file) => {
    const fd = new FormData()
    fd.append('file', file)
    const res = await client.post('/api/upload/track', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data
  },

  uploadTelemetry: async (file) => {
    const fd = new FormData()
    fd.append('file', file)
    const res = await client.post('/api/upload/telemetry', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data
  },

  getTrackData:    async () => (await client.get('/api/data/track')).data,
  getCurrentTrack: async () => (await client.get('/api/track/current')).data,
  getTrackGeometry: async () => (await client.get('/api/track/geometry')).data,
  getTrackCache:   async () => (await client.get('/api/track/cache')).data,
  getCarState:     async () => (await client.get('/api/car/state')).data,
  getHealth:       async () => (await client.get('/api/health')).data,
  getRuntimeStatus: async () => (await client.get('/api/runtime/status')).data,
  getDataQuality: async () => (await client.get('/api/validation/data-quality')).data,
  getLiveTelemetry: async (options = {}) => (
    await client.get('/api/live/telemetry', {
      params: {
        includeTrack: options.includeTrack,
        includeTrajectory: options.includeTrajectory,
      },
    })
  ).data,
  getLiveComparison: async (microSectors = 50) => (await client.get('/api/live/comparison', { params: { microSectors } })).data,
  getRacingLine: async (microSectors = 50, options = {}) => (
    await client.get('/api/live/racing-line', {
      params: {
        microSectors,
        includeVisualLine: options.includeVisualLine,
        includeComparison: options.includeComparison,
      },
    })
  ).data,
  getPlayerPhysics: async () => (await client.get('/api/live/player-physics')).data,
  getRecordingStatus: async () => (await client.get('/api/recording/status')).data,
  getSessions: async (limit = 30) => (await client.get('/api/sessions', { params: { limit } })).data,
  getSession: async (sessionId) => (
    await client.get(`/api/sessions/${encodeURIComponent(sessionId)}`)
  ).data,
  getSessionLaps: async (sessionId) => (
    await client.get(`/api/sessions/${encodeURIComponent(sessionId)}/laps`)
  ).data,
  getSessionLap: async (sessionId, lapNumber) => (
    await client.get(`/api/sessions/${encodeURIComponent(sessionId)}/laps/${lapNumber}`)
  ).data,
  getOfflineLap: async (lapId) => (
    await client.get(`/api/laps/${encodeURIComponent(lapId)}`)
  ).data,
  getOfflineLapSummary: async (lapId) => (
    await client.get(`/api/laps/${encodeURIComponent(lapId)}/summary`)
  ).data,
  getOfflineLapSamples: async (lapId, limit = 10_000) => (
    await client.get(`/api/laps/${encodeURIComponent(lapId)}/samples`, { params: { limit } })
  ).data,
  getOfflineLapReplay: async (lapId, maxSamples = 36_000) => (
    await client.get(`/api/laps/${encodeURIComponent(lapId)}/replay`, { params: { maxSamples } })
  ).data,
  getTelemetryData:async () => (await client.get('/api/data/telemetry')).data,
  getAiRaceline:   async () => (await client.get('/api/data/ai-raceline')).data,
  getComparison:   async () => (await client.get('/api/data/comparison')).data,
  getTrackLimits:  async () => (await client.get('/api/data/track-limits')).data,

  listAssistedAnalysisLaps: async () => (await client.get('/api/assisted-analysis/laps')).data,
  getAssistedLapTelemetry: async (lapId, maxSamples = 36_000) => (
    await client.get(`/api/analysis/assisted/lap/${encodeURIComponent(lapId)}/telemetry`, {
      params: { maxSamples },
    })
  ).data,
  getAssistedAnalysis: async (lapId, referenceLapId = null, options = {}) => {
    const res = await client.get(`/api/analysis/assisted/lap/${encodeURIComponent(lapId)}`, {
      params: {
        ...(referenceLapId ? { reference_lap_id: referenceLapId } : {}),
        ...(options.includeExternalReference ? { includeExternalReference: true } : {}),
        ...(options.externalReferenceId ? { externalReferenceId: options.externalReferenceId } : {}),
      },
    })
    return res.data
  },
  requestAssistedAnalysis: async (lapId, {
    referenceLapId = null,
    force = false,
    includeExternalReference = false,
    externalReferenceId = null,
  } = {}) => {
    const res = await client.post(
      `/api/analysis/assisted/lap/${encodeURIComponent(lapId)}`,
      { referenceLapId, force, includeExternalReference, externalReferenceId },
      { timeout: 120_000 },
    )
    return res.data
  },
  listExternalReferences: async () => (await client.get('/api/references/external')).data,
  importFastF1Reference: async (payload) => (
    await client.post('/api/references/external/fastf1/import', payload, { timeout: 180_000 })
  ).data,

  // ─── FastF1 ──────────────────────────────────────────────────────────────
  /**
   * Busca a volta mais rápida via FastF1 e regenera a IA com referência real.
   * @param {number} year  ex: 2024
   * @param {string} gp    ex: "Brazil"
   * @param {string} session ex: "Q"
   */
  fetchF1FastestLap: async (year = 2024, gp = 'Brazil', session = 'Q') => {
    const res = await client.post('/api/fastf1/fetch', null, {
      params: { year, gp, session_type: session },
      timeout: 120_000, // pode demorar na primeira vez (download de dados)
    })
    return res.data
  },

  getF1Trajectory: async () => (await client.get('/api/fastf1/trajectory')).data,
  getF1Status:     async () => (await client.get('/api/fastf1/status')).data,
  getF1Comparison: async () => (await client.get('/api/fastf1/comparison')).data,
}

export default client
