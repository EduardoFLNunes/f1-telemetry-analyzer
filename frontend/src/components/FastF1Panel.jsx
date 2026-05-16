import React, { useState } from 'react'
import { api } from '../api/client'
import './FastF1Panel.css'

const GP_OPTIONS = [
  'Bahrain', 'Saudi Arabia', 'Australia', 'Japan', 'China',
  'Miami', 'Emilia Romagna', 'Monaco', 'Canada', 'Spain',
  'Austria', 'Britain', 'Hungary', 'Belgium', 'Netherlands',
  'Italy', 'Azerbaijan', 'Singapore', 'United States', 'Mexico',
  'Brazil', 'Las Vegas', 'Qatar', 'Abu Dhabi',
]

const SESSION_OPTIONS = [
  { value: 'Q',   label: 'Qualifying' },
  { value: 'R',   label: 'Race' },
  { value: 'FP1', label: 'FP1' },
  { value: 'FP2', label: 'FP2' },
  { value: 'FP3', label: 'FP3' },
]

export default function FastF1Panel({
  f1Data,         // null | { driver, team, lap_time, year, gp, session, alignment }
  playerLapTime,  // number | null
  aiEstimatedTime,// number | null
  onF1Loaded,     // (f1TrajectoryData) => void
  showF1OnMap,
  onToggleF1OnMap,
}) {
  const [year,    setYear]    = useState(2024)
  const [gp,      setGp]      = useState('Brazil')
  const [session, setSession] = useState('Q')
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)

  const handleFetch = async () => {
    setLoading(true)
    setError(null)
    try {
      await api.fetchF1FastestLap(year, gp, session)
      const traj = await api.getF1Trajectory()
      onF1Loaded(traj)
    } catch (e) {
      const msg = e.response?.data?.detail || e.message || 'Erro ao buscar dados FastF1'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const formatTime = (s) => {
    if (!s) return '–'
    const m = Math.floor(s / 60)
    const sec = (s % 60).toFixed(3).padStart(6, '0')
    return `${m}:${sec}`
  }

  const gapToF1 = f1Data && playerLapTime
    ? (playerLapTime - f1Data.lap_time).toFixed(3)
    : null

  const aiVsPlayer = aiEstimatedTime && playerLapTime
    ? (playerLapTime - aiEstimatedTime).toFixed(3)
    : null

  return (
    <div className="f1-panel">
      {/* Header */}
      <div className="f1-panel-header">
        <div className="f1-panel-title">
          <span className="f1-logo">F1</span>
          <h3>Referência FastF1</h3>
        </div>
        {f1Data
          ? <span className="f1-status-badge loaded">✓ Carregado</span>
          : <span className="f1-status-badge not-loaded">Não carregado</span>
        }
      </div>

      {/* Search form */}
      <div className="f1-search">
        <div className="f1-search-row three">
          <div className="f1-field">
            <label>GP</label>
            <select value={gp} onChange={e => setGp(e.target.value)}>
              {GP_OPTIONS.map(g => <option key={g} value={g}>{g}</option>)}
            </select>
          </div>
          <div className="f1-field">
            <label>Ano</label>
            <input
              type="number"
              value={year}
              min={2018} max={2024}
              onChange={e => setYear(+e.target.value)}
            />
          </div>
          <div className="f1-field">
            <label>Sessão</label>
            <select value={session} onChange={e => setSession(e.target.value)}>
              {SESSION_OPTIONS.map(s => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
        </div>

        <button
          className="btn-f1-fetch"
          onClick={handleFetch}
          disabled={loading}
        >
          {loading
            ? <><span className="f1-spinner" /> Baixando dados…</>
            : '⬇ Buscar Volta Mais Rápida'}
        </button>
      </div>

      {/* Error */}
      {error && <div className="f1-error">⚠ {error}</div>}

      {/* Info card */}
      {f1Data && (
        <>
          <div className="f1-info-card">
            <div className="f1-driver-row">
              <div>
                <div className="f1-driver-name">{f1Data.driver}</div>
                <div className="f1-team-name">{f1Data.team}</div>
              </div>
              <div className="f1-lap-time">{formatTime(f1Data.lap_time)}</div>
            </div>
            <div className="f1-meta-row">
              <div className="f1-meta-item">
                <span className="f1-meta-label">GP</span>
                <span className="f1-meta-value">{f1Data.gp}</span>
              </div>
              <div className="f1-meta-item">
                <span className="f1-meta-label">Ano</span>
                <span className="f1-meta-value">{f1Data.year}</span>
              </div>
              <div className="f1-meta-item">
                <span className="f1-meta-label">Sessão</span>
                <span className="f1-meta-value">{f1Data.session}</span>
              </div>
              {f1Data.alignment?.scale && (
                <div className="f1-meta-item">
                  <span className="f1-meta-label">Escala</span>
                  <span className="f1-meta-value">{f1Data.alignment.scale.toFixed(3)}</span>
                </div>
              )}
            </div>
          </div>

          {/* Deltas */}
          <div className="f1-delta-section">
            {gapToF1 !== null && (
              <div className="f1-delta-card gap">
                <span className="f1-delta-label">Gap Player → F1</span>
                <span className="f1-delta-value">+{gapToF1}s</span>
              </div>
            )}
            {aiVsPlayer !== null && +aiVsPlayer > 0 && (
              <div className="f1-delta-card ai-gain">
                <span className="f1-delta-label">Ganho estimado pela IA</span>
                <span className="f1-delta-value">-{aiVsPlayer}s</span>
              </div>
            )}
          </div>

          {/* Toggle F1 on map */}
          <div className="f1-toggle">
            <button
              className={`btn-f1-toggle ${showF1OnMap ? 'active' : ''}`}
              onClick={onToggleF1OnMap}
            >
              {showF1OnMap ? '👁 Ocultar traçado F1 no mapa' : '👁 Mostrar traçado F1 no mapa'}
            </button>
          </div>
        </>
      )}
    </div>
  )
}