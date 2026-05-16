import React, { useState } from 'react'
import Plot from 'react-plotly.js'
import './TelemetryCharts.css'

export default function TelemetryCharts({ playerData, aiData, f1Data }) {
  const [activeChart, setActiveChart] = useState('speed')

  const pDist     = playerData.best_lap_data.distance
  const pSpeed    = playerData.best_lap_data.speed
  const pThrottle = playerData.best_lap_data.throttle
  const pBrake    = playerData.best_lap_data.brake

  const aDist     = aiData.trajectory.distance || []
  const aSpeed    = aiData.speed     || []
  const aThrottle = aiData.throttle  || []
  const aBrake    = aiData.brake     || []

  // F1 reference (optional)
  const f1Dist    = f1Data?.trajectory ? pDist : [] // same x-axis length
  const f1Speed   = f1Data?.speed      || []
  const f1Thr     = f1Data?.throttle   || []
  const f1Brk     = f1Data?.brake      || []

  // Interpolate F1 data to player distance axis
  const interpF1 = (srcArr, dstLen) => {
    if (!srcArr.length || !dstLen) return []
    const out = []
    for (let i = 0; i < dstLen; i++) {
      const t   = i / (dstLen - 1)
      const idx = t * (srcArr.length - 1)
      const lo  = Math.floor(idx)
      const hi  = Math.min(lo + 1, srcArr.length - 1)
      out.push(srcArr[lo] + (srcArr[hi] - srcArr[lo]) * (idx - lo))
    }
    return out
  }

  const f1SpeedInterp = interpF1(f1Speed, pDist.length)
  const f1ThrInterp   = interpF1(f1Thr,   pDist.length)
  const f1BrkInterp   = interpF1(f1Brk,   pDist.length)

  const commonLayout = {
    autosize: true,
    paper_bgcolor: '#0b0c1a',
    plot_bgcolor:  '#101225',
    margin: { l: 50, r: 20, t: 20, b: 40 },
    font: { color: '#eceef8', family: 'Inter, sans-serif', size: 11 },
    xaxis: { title: 'Distância (m)', gridcolor: 'rgba(255,255,255,0.05)', color: '#7a7d9a' },
    yaxis: { gridcolor: 'rgba(255,255,255,0.05)', color: '#7a7d9a' },
    hovermode: 'x unified',
    showlegend: true,
    legend: {
      x: 0.02, y: 0.98,
      bgcolor: 'rgba(11,12,26,0.8)',
      bordercolor: 'rgba(255,255,255,0.2)',
      borderwidth: 1,
    },
  }

  const f1SpeedTrace = f1SpeedInterp.length ? {
    x: pDist, y: f1SpeedInterp, name: 'Ref F1',
    type: 'scatter', mode: 'lines',
    line: { color: 'rgba(231,0,9,0.75)', width: 1.5, dash: 'dot' },
    hovertemplate: '%{y:.0f} km/h<extra></extra>',
  } : null

  const f1ThrTrace = f1ThrInterp.length ? {
    x: pDist, y: f1ThrInterp, name: 'Ref F1',
    type: 'scatter', mode: 'lines',
    line: { color: 'rgba(231,0,9,0.65)', width: 1.5, dash: 'dot' },
    hovertemplate: '%{y:.1f}%<extra></extra>',
  } : null

  const f1BrkTrace = f1BrkInterp.length ? {
    x: pDist, y: f1BrkInterp, name: 'Ref F1',
    type: 'scatter', mode: 'lines',
    line: { color: 'rgba(231,0,9,0.65)', width: 1.5, dash: 'dot' },
    hovertemplate: '%{y:.1f}%<extra></extra>',
  } : null

  // ── Charts ────────────────────────────────────────────────────────────────
  const speedChart = {
    data: [
      { x: pDist, y: pSpeed,  name: 'Player',   type: 'scatter', mode: 'lines', line: { color: '#ffd000', width: 2 }, hovertemplate: '%{y:.0f} km/h<extra></extra>' },
      { x: aDist, y: aSpeed,  name: 'IA Ideal', type: 'scatter', mode: 'lines', line: { color: '#9d4edd', width: 2 }, hovertemplate: '%{y:.0f} km/h<extra></extra>' },
      ...(f1SpeedTrace ? [f1SpeedTrace] : []),
    ],
    layout: { ...commonLayout, yaxis: { ...commonLayout.yaxis, title: 'Velocidade (km/h)' } },
  }

  const throttleChart = {
    data: [
      { x: pDist, y: pThrottle, name: 'Player',   type: 'scatter', mode: 'lines', fill: 'tozeroy', fillcolor: 'rgba(0,230,118,0.18)', line: { color: '#00e676', width: 2 }, hovertemplate: '%{y:.1f}%<extra></extra>' },
      { x: aDist, y: aThrottle, name: 'IA Ideal', type: 'scatter', mode: 'lines', line: { color: '#9d4edd', width: 2, dash: 'dot' }, hovertemplate: '%{y:.1f}%<extra></extra>' },
      ...(f1ThrTrace ? [f1ThrTrace] : []),
    ],
    layout: { ...commonLayout, yaxis: { ...commonLayout.yaxis, title: 'Acelerador (%)', range: [0, 105] } },
  }

  const brakeChart = {
    data: [
      { x: pDist, y: pBrake, name: 'Player',   type: 'scatter', mode: 'lines', fill: 'tozeroy', fillcolor: 'rgba(232,25,44,0.18)', line: { color: '#e8192c', width: 2 }, hovertemplate: '%{y:.1f}%<extra></extra>' },
      { x: aDist, y: aBrake, name: 'IA Ideal', type: 'scatter', mode: 'lines', line: { color: '#9d4edd', width: 2, dash: 'dot' }, hovertemplate: '%{y:.1f}%<extra></extra>' },
      ...(f1BrkTrace ? [f1BrkTrace] : []),
    ],
    layout: { ...commonLayout, yaxis: { ...commonLayout.yaxis, title: 'Freio (%)', range: [0, 105] } },
  }

  // Delta: Player vs IA vs F1
  const calcDelta = (refSpeed) => {
    const delta = []
    let cum = 0
    const len = Math.min(pDist.length, refSpeed.length)
    for (let i = 0; i < len; i++) {
      if (i > 0) {
        const ds   = pDist[i] - pDist[i - 1]
        const pMs  = pSpeed[i] / 3.6
        const rMs  = refSpeed[i] / 3.6
        const pT   = pMs  > 0 ? ds / pMs  : 0
        const rT   = rMs  > 0 ? ds / rMs  : 0
        cum += pT - rT
      }
      delta.push(cum)
    }
    return delta
  }

  const deltaVsAi = calcDelta(interpF1(aSpeed, pDist.length))
  const deltaVsF1 = f1SpeedInterp.length ? calcDelta(f1SpeedInterp) : []

  const finalDeltaAi = deltaVsAi[deltaVsAi.length - 1] ?? 0
  const finalDeltaF1 = deltaVsF1.length ? deltaVsF1[deltaVsF1.length - 1] : null

  const deltaChart = {
    data: [
      {
        x: pDist.slice(0, deltaVsAi.length), y: deltaVsAi, name: 'Player vs IA',
        type: 'scatter', mode: 'lines',
        fill: 'tozeroy',
        fillcolor: finalDeltaAi > 0 ? 'rgba(232,25,44,0.12)' : 'rgba(0,230,118,0.12)',
        line: { color: finalDeltaAi > 0 ? '#e8192c' : '#00e676', width: 2 },
        hovertemplate: '%{y:.3f}s<extra></extra>',
      },
      ...(deltaVsF1.length ? [{
        x: pDist.slice(0, deltaVsF1.length), y: deltaVsF1, name: 'Player vs F1',
        type: 'scatter', mode: 'lines',
        line: { color: 'rgba(231,0,9,0.8)', width: 1.5, dash: 'dot' },
        hovertemplate: '%{y:.3f}s<extra></extra>',
      }] : []),
    ],
    layout: {
      ...commonLayout,
      yaxis: { ...commonLayout.yaxis, title: 'Delta (s)', zeroline: true, zerolinecolor: 'rgba(255,255,255,0.3)', zerolinewidth: 1 },
    },
  }

  const charts = { speed: speedChart, throttle: throttleChart, brake: brakeChart, delta: deltaChart }
  const current = charts[activeChart]

  return (
    <div className="telemetry-charts">
      <div className="charts-header">
        <h3>Análise Detalhada {f1SpeedInterp.length ? '· incl. Ref F1' : ''}</h3>
        <div className="chart-tabs">
          {['speed', 'throttle', 'brake', 'delta'].map(k => (
            <button
              key={k}
              className={`chart-tab ${activeChart === k ? 'active' : ''}`}
              onClick={() => setActiveChart(k)}
            >
              {{ speed: 'Velocidade', throttle: 'Throttle', brake: 'Freio', delta: 'Delta' }[k]}
            </button>
          ))}
        </div>
      </div>
      <div className="chart-container">
        <Plot
          data={current.data}
          layout={current.layout}
          config={{ responsive: true, displayModeBar: false }}
          style={{ width: '100%', height: '100%' }}
          useResizeHandler
        />
      </div>
    </div>
  )
}