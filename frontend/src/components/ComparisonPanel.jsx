import React from 'react'
import { TrendingUp, TrendingDown, Clock, Zap, Award } from 'lucide-react'
import './ComparisonPanel.css'

function ComparisonPanel({ telemetryData, aiData }) {
  const playerTime = telemetryData.best_lap_time
  const aiTime = aiData.estimated_time
  const timeDiff = playerTime - aiTime
  const timeGain = timeDiff > 0 ? timeDiff : 0

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toFixed(3).padStart(6, '0')}`
  }

  const formatDelta = (seconds) => {
    return seconds >= 0 ? `+${seconds.toFixed(3)}s` : `${seconds.toFixed(3)}s`
  }

  const metrics = telemetryData.metrics
  const improvements = aiData.improvements || []
  const insights = aiData.insights || []

  return (
    <div className="comparison-panel">
      {/* Lap Times Comparison */}
      <div className="comp-section lap-times">
        <div className="section-header">
          <Clock size={16} />
          <h3>Tempos de Volta</h3>
        </div>

        <div className="time-cards">
          <div className="time-card player-card">
            <span className="time-label">Player</span>
            <span className="time-value">{formatTime(playerTime)}</span>
            <span className="time-lap">Volta {telemetryData.best_lap_number}</span>
          </div>

          <div className="time-card ai-card">
            <span className="time-label">IA Ideal</span>
            <span className="time-value">{formatTime(aiTime)}</span>
            <span className="time-lap">Estimado</span>
          </div>
        </div>

        {timeGain > 0 && (
          <div className="time-diff">
            <div className="diff-badge">
              <TrendingDown size={16} />
              <span className="diff-label">Ganho Potencial</span>
            </div>
            <span className="diff-value">{formatDelta(timeGain)}</span>
          </div>
        )}
      </div>

      {/* Performance Metrics */}
      <div className="comp-section metrics">
        <div className="section-header">
          <Zap size={16} />
          <h3>Métricas de Performance</h3>
        </div>

        <div className="metrics-grid">
          <div className="metric-item">
            <span className="metric-label">Velocidade Média</span>
            <span className="metric-value">{metrics.avg_speed.toFixed(1)} km/h</span>
          </div>

          <div className="metric-item">
            <span className="metric-label">Velocidade Máxima</span>
            <span className="metric-value">{metrics.max_speed.toFixed(1)} km/h</span>
          </div>

          <div className="metric-item">
            <span className="metric-label">Full Throttle</span>
            <span className="metric-value">{metrics.full_throttle_pct.toFixed(1)}%</span>
          </div>

          <div className="metric-item">
            <span className="metric-label">Pontos de Freio</span>
            <span className="metric-value">{metrics.brake_points}</span>
          </div>

          <div className="metric-item">
            <span className="metric-label">Acelerador Médio</span>
            <span className="metric-value">{metrics.avg_throttle.toFixed(1)}%</span>
          </div>

          <div className="metric-item">
            <span className="metric-label">Freio Médio</span>
            <span className="metric-value">{metrics.avg_brake.toFixed(1)}%</span>
          </div>
        </div>
      </div>

      {/* AI Insights */}
      {insights.length > 0 && (
        <div className="comp-section insights">
          <div className="section-header">
            <Award size={16} />
            <h3>Insights da IA</h3>
          </div>

          <div className="insights-list">
            {insights.map((insight, idx) => (
              <div key={idx} className="insight-item">
                <span className="insight-icon">💡</span>
                <span className="insight-text">{insight}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Corner Improvements */}
      {improvements.length > 0 && (
        <div className="comp-section improvements">
          <div className="section-header">
            <TrendingUp size={16} />
            <h3>Oportunidades de Melhoria</h3>
          </div>

          <div className="improvements-list">
            {improvements.slice(0, 5).map((imp, idx) => (
              <div key={idx} className="improvement-item">
                <div className="imp-header">
                  <span className="imp-corner">Curva {imp.corner}</span>
                  <span className="imp-gain">+{imp.gain.toFixed(1)} km/h</span>
                </div>
                <div className="imp-details">
                  <span className="imp-current">{imp.current.toFixed(0)} km/h</span>
                  <span className="imp-arrow">→</span>
                  <span className="imp-target">{imp.target.toFixed(0)} km/h</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Driving Style */}
      <div className="comp-section driving-style">
        <div className="section-header">
          <h3>Estilo de Pilotagem</h3>
        </div>

        <div className="style-card">
          <div className="style-badge">
            {telemetryData.driving_style.classification.toUpperCase()}
          </div>
          <p className="style-description">
            {telemetryData.driving_style.description}
          </p>

          <div className="style-meters">
            <div className="style-meter-item">
              <span className="meter-label">Suavidade Throttle</span>
              <div className="meter-bar">
                <div 
                  className="meter-fill green"
                  style={{ width: `${telemetryData.driving_style.throttle_smoothness * 100}%` }}
                />
              </div>
              <span className="meter-value">
                {(telemetryData.driving_style.throttle_smoothness * 100).toFixed(0)}%
              </span>
            </div>

            <div className="style-meter-item">
              <span className="meter-label">Suavidade Freio</span>
              <div className="meter-bar">
                <div 
                  className="meter-fill red"
                  style={{ width: `${telemetryData.driving_style.brake_smoothness * 100}%` }}
                />
              </div>
              <span className="meter-value">
                {(telemetryData.driving_style.brake_smoothness * 100).toFixed(0)}%
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ComparisonPanel
