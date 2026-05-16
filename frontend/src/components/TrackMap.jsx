import React, { useEffect, useRef, useState } from 'react'
import Plot from 'react-plotly.js'
import './TrackMap.css'

export default function TrackMap({ trackData, playerData, aiData, f1Data, showF1 }) {
  const [selectedPoint, setSelectedPoint] = useState(0)
  const [animating, setAnimating]         = useState(false)
  const animRef = useRef(null)

  const playerX    = playerData?.best_lap_data?.x     || []
  const playerZ    = playerData?.best_lap_data?.z     || []
  const playerSpd  = playerData?.best_lap_data?.speed || []

  const aiX   = aiData?.trajectory?.x || []
  const aiZ   = aiData?.trajectory?.z || []
  const aiSpd = aiData?.speed         || []

  const f1X   = (showF1 && f1Data?.trajectory?.x) || []
  const f1Z   = (showF1 && f1Data?.trajectory?.z) || []
  const f1Spd = (showF1 && f1Data?.speed)         || []

  // Bounds
  const allX = [...trackData.centerline.x, ...trackData.left_edge.x, ...trackData.right_edge.x]
  const allZ = [...trackData.centerline.y, ...trackData.left_edge.y, ...trackData.right_edge.y]
  const margin = 60
  const xRange = [Math.min(...allX) - margin, Math.max(...allX) + margin]
  const zRange = [Math.min(...allZ) - margin, Math.max(...allZ) + margin]

  // Asphalt polygon
  const aspX = [...trackData.left_edge.x, ...trackData.right_edge.x.slice().reverse(), trackData.left_edge.x[0]]
  const aspZ = [...trackData.left_edge.y, ...trackData.right_edge.y.slice().reverse(), trackData.left_edge.y[0]]

  const safeIdx = (arr) => Math.min(selectedPoint, Math.max(0, arr.length - 1))

  const traces = [
    // Asphalt fill
    {
      x: aspX, y: aspZ,
      fill: 'toself', fillcolor: 'rgba(110,110,120,0.28)',
      line: { color: 'rgba(0,0,0,0)', width: 0 },
      mode: 'lines', hoverinfo: 'skip', showlegend: false,
    },
    // Centerline dash
    {
      x: trackData.centerline.x, y: trackData.centerline.y,
      mode: 'lines',
      line: { color: 'rgba(255,208,0,0.35)', width: 1, dash: 'dot' },
      hoverinfo: 'skip', showlegend: false,
    },
    // Track limits
    {
      x: trackData.left_edge.x, y: trackData.left_edge.y,
      mode: 'lines', line: { color: 'rgba(255,255,255,0.65)', width: 2 },
      hoverinfo: 'skip', showlegend: false,
    },
    {
      x: trackData.right_edge.x, y: trackData.right_edge.y,
      mode: 'lines', line: { color: 'rgba(255,255,255,0.65)', width: 2 },
      hoverinfo: 'skip', showlegend: false,
    },
    // F1 reference (below player so it doesn't dominate)
    ...(f1X.length > 0 ? [{
      x: f1X, y: f1Z,
      mode: 'lines',
      line: { color: 'rgba(231,0,9,0.7)', width: 2.5, dash: 'dot' },
      name: 'Ref F1',
      text: f1Spd.map(s => (s || 0).toFixed(0)),
      hovertemplate: 'F1: %{text} km/h<extra></extra>',
      showlegend: true,
    }] : []),
    // Player raceline
    {
      x: playerX, y: playerZ,
      mode: 'lines',
      line: { color: 'rgba(255,208,0,0.85)', width: 3 },
      name: 'Player',
      text: playerSpd.map(s => (s || 0).toFixed(0)),
      hovertemplate: 'Player: %{text} km/h<extra></extra>',
      showlegend: true,
    },
    // AI raceline
    {
      x: aiX, y: aiZ,
      mode: 'lines',
      line: { color: 'rgba(157,78,221,0.92)', width: 3 },
      name: 'IA Ideal',
      text: aiSpd.map(s => (s || 0).toFixed(0)),
      hovertemplate: 'IA: %{text} km/h<extra></extra>',
      showlegend: true,
    },
    // Player cursor
    ...(playerX.length > 0 ? [{
      x: [playerX[safeIdx(playerX)]],
      y: [playerZ[safeIdx(playerZ)]],
      mode: 'markers',
      marker: { size: 12, color: '#ffd000', symbol: 'circle', line: { color: '#fff', width: 2 } },
      hoverinfo: 'skip', showlegend: false,
    }] : []),
    // AI cursor
    ...(aiX.length > 0 ? [{
      x: [aiX[safeIdx(aiX)]],
      y: [aiZ[safeIdx(aiZ)]],
      mode: 'markers',
      marker: { size: 10, color: '#9d4edd', symbol: 'circle', line: { color: '#fff', width: 2 } },
      hoverinfo: 'skip', showlegend: false,
    }] : []),
    // F1 cursor
    ...(showF1 && f1X.length > 0 ? [{
      x: [f1X[safeIdx(f1X)]],
      y: [f1Z[safeIdx(f1Z)]],
      mode: 'markers',
      marker: { size: 10, color: '#e70009', symbol: 'diamond', line: { color: '#fff', width: 2 } },
      hoverinfo: 'skip', showlegend: false,
    }] : []),
  ]

  const layout = {
    autosize: true,
    paper_bgcolor: '#0b0c1a',
    plot_bgcolor:  '#0b0c1a',
    xaxis: {
      range: xRange, showgrid: false, zeroline: false,
      showticklabels: false, scaleanchor: 'y', scaleratio: 1,
    },
    yaxis: { range: zRange, showgrid: false, zeroline: false, showticklabels: false },
    margin: { l: 10, r: 10, t: 10, b: 10 },
    showlegend: true,
    legend: {
      x: 0.02, y: 0.98,
      bgcolor: 'rgba(11,12,26,0.85)',
      bordercolor: 'rgba(255,255,255,0.2)',
      borderwidth: 1,
      font: { color: '#eceef8', size: 11 },
    },
    hovermode: 'closest',
  }

  // Animation
  const stepRef = useRef(0)
  const toggleAnimation = () => {
    if (animating) {
      setAnimating(false)
      cancelAnimationFrame(animRef.current)
    } else {
      setAnimating(true)
      stepRef.current = selectedPoint
      const tick = () => {
        stepRef.current = stepRef.current >= playerX.length - 1 ? 0 : stepRef.current + 1
        setSelectedPoint(stepRef.current)
        animRef.current = requestAnimationFrame(tick)
      }
      animRef.current = requestAnimationFrame(tick)
    }
  }

  useEffect(() => () => cancelAnimationFrame(animRef.current), [])

  const curSpd = (arr, idx) => Number(arr[Math.min(idx, arr.length - 1)] ?? 0).toFixed(0)

  return (
    <div className="track-map">
      <div className="map-header">
        <div className="map-title">
          <h2>{trackData.name}</h2>
          <span className="map-subtitle">{trackData.total_points} pontos · {(trackData.length_meters/1000).toFixed(3)} km</span>
        </div>
        <div className="map-controls">
          <button className={`btn-animate ${animating ? 'active' : ''}`} onClick={toggleAnimation}>
            {animating ? '⏸ Pausar' : '▶ Animar'}
          </button>
          <button className="btn-reset-view" onClick={() => { setSelectedPoint(0); setAnimating(false); cancelAnimationFrame(animRef.current) }}>
            ↺ Reset
          </button>
        </div>
      </div>

      <div className="map-container">
        <Plot
          data={traces}
          layout={layout}
          config={{ responsive: true, displayModeBar: false }}
          style={{ width: '100%', height: '100%' }}
          useResizeHandler
        />
      </div>

      <div className="map-info">
        <div className="info-item">
          <span className="info-label">Progresso</span>
          <span className="info-value">
            {playerX.length ? ((selectedPoint / playerX.length) * 100).toFixed(1) : '0.0'}%
          </span>
        </div>
        <div className="info-item">
          <span className="info-label">Player</span>
          <span className="info-value player-color">{curSpd(playerSpd, selectedPoint)} km/h</span>
        </div>
        <div className="info-item">
          <span className="info-label">IA Ideal</span>
          <span className="info-value ai-color">{curSpd(aiSpd, selectedPoint)} km/h</span>
        </div>
        {showF1 && f1Spd.length > 0 && (
          <div className="info-item">
            <span className="info-label">Ref F1</span>
            <span className="info-value" style={{ color: '#e70009' }}>{curSpd(f1Spd, selectedPoint)} km/h</span>
          </div>
        )}
      </div>
    </div>
  )
}