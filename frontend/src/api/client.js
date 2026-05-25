import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const client = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

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
  getLiveTelemetry:async () => (await client.get('/api/live/telemetry')).data,
  getTelemetryData:async () => (await client.get('/api/data/telemetry')).data,
  getAiRaceline:   async () => (await client.get('/api/data/ai-raceline')).data,
  getComparison:   async () => (await client.get('/api/data/comparison')).data,
  getTrackLimits:  async () => (await client.get('/api/data/track-limits')).data,

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
