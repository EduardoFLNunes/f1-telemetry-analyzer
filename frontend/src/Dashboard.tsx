/**
 * F1 Motorsport Intelligence Workstation — Master Layout
 * Complete 9-Phase reformulation
 */
import React, { useEffect, useState } from 'react';
import { TrackRenderer } from './components/map/TrackRenderer.jsx';
import { TelemetryTraces } from './components/TelemetryTraces';
import { GGDiagram } from './components/GGDiagram';
import { CoachingFeed } from './components/CoachingFeed';
import { AIDebriefPanel } from './components/AIDebriefPanel';
import { AIEngineerPanel } from './components/AIEngineerPanel';
import { CarPhysicsDebugPanel } from './components/CarPhysicsDebugPanel';
import { LiveComparisonPanel } from './components/LiveComparisonPanel';
import { RacingLineAnalysisPanel } from './components/RacingLineAnalysisPanel';
import { ReplayControls } from './components/ReplayControls';
import { CognitiveDashboard } from './components/CognitiveDashboard';
import { Header } from './components/Header';
import { VehicleStatePanel, LapTimingPanel, StabilityPanel } from './components/LiveTelemetryPanels';
import { useTelemetryStore } from './store/useTelemetryStore';
import { useRenderCounter } from './hooks/useRenderCounter';
import { ErrorBoundary } from './components/ErrorBoundary';
import { api } from './api/client';
import { deltaTone, formatDelta, formatLapTime } from './utils/lapFormat';

/* ─── Dashboard ───────────────────────────────────────────────── */
const Dashboard: React.FC = () => {
  useRenderCounter('Dashboard');
  const [trackData, setTrackData] = useState<any>(null);
  const [rightPanel, setRightPanel] = useState<'engineer'|'debrief'|'comparison'|'racingLine'|'physics'>('engineer');
  const [time, setTime] = useState(() => new Date());

  useEffect(() => {
    let cancelled = false;
    let inFlight = false;
    const loadTrack = async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        const data = await api.getTrackGeometry();
        if (!cancelled && data.track) {
          setTrackData(data.track);
          return;
        }
        if (!cancelled) {
          setTrackData(null);
        }
      } catch {
        if (!cancelled) setTrackData(null);
      } finally {
        inFlight = false;
      }
    };
    loadTrack();
    const interval = setInterval(loadTrack, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <ErrorBoundary>
      {/* Full workstation shell */}
      <div
        className="flex flex-col select-none"
        style={{ width: '100vw', height: '100vh', background: '#06060d', color: '#f1f5f9', overflow: 'hidden' }}
      >
        {/* ─ Header ─ */}
        <Header time={time} />

        {/* ─ Main Content ─ */}
        <div style={{ flex: 1, display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 2fr) minmax(0, 1fr)', gap: 1, padding: 1, overflow: 'hidden' }}>

          {/* ═══ LEFT COLUMN — Engineering Metrics ═══ */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 1, overflow: 'hidden' }}>

            {/* Primary vehicle state block */}
            <VehicleStatePanel />

            {/* Timing & G-forces */}
            <LapTimingPanel />

            {/* G-G Diagram */}
            <div className="panel" style={{ padding: '8px', flex: 1, display: 'flex', flexDirection: 'column', gap: 6, overflow: 'hidden' }}>
              <div className="label" style={{ fontSize: 6, paddingLeft: 4 }}>G-G Diagram</div>
              <div style={{ flex: 1 }}>
                <GGDiagram />
              </div>
            </div>

            {/* Stability + Cognitive */}
            <StabilityPanel />

            {/* Cognitive dashboard */}
            <div style={{ flex: 1, overflow: 'hidden' }}>
              <CognitiveDashboard />
            </div>

          </div>

          {/* ═══ CENTER — Track Map + Telemetry Traces ═══ */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 1, overflow: 'hidden' }}>

            {/* Track map — primary viewport */}
            <div className="panel" style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
              <TrackRenderer trackData={trackData} />
            </div>

            {/* Lap comparison panel */}
            <div className="panel" style={{ height: 200, overflow: 'hidden' }}>
              <TelemetryTraces />
            </div>

          </div>

          {/* ═══ RIGHT COLUMN — Intelligence Hub ═══ */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 1, overflow: 'hidden' }}>

            {/* Panel selector tabs */}
            <div className="panel" style={{ display: 'flex', gap: 1, padding: 1 }}>
              {(['engineer', 'debrief', 'comparison', 'racingLine', 'physics'] as const).map(tab => (
                <button
                  key={tab}
                  onClick={() => setRightPanel(tab)}
                  className="num"
                  style={{
                    flex: 1,
                    padding: '6px 0',
                    fontSize: 8,
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.1em',
                    borderRadius: 2,
                    border: 'none',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    background: rightPanel === tab ? 'rgba(34,211,238,0.08)' : 'transparent',
                    color: rightPanel === tab ? '#22d3ee' : '#475569',
                    outline: rightPanel === tab ? '1px solid rgba(34,211,238,0.2)' : '1px solid transparent',
                  }}
                >
                  {tab === 'engineer' ? 'Engineer' : (tab === 'debrief' ? 'Debrief' : (tab === 'comparison' ? 'Compare' : (tab === 'racingLine' ? 'Line' : 'Physics')))}
                </button>
              ))}
            </div>

            {/* Panel content (stacked, toggled by opacity) */}
            <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
              <div style={{
                position: 'absolute', inset: 0,
                opacity: rightPanel === 'engineer' ? 1 : 0,
                pointerEvents: rightPanel === 'engineer' ? 'auto' : 'none',
                transition: 'opacity 0.3s',
              }}>
                <AIEngineerPanel active={rightPanel === 'engineer'} />
              </div>
              <div style={{
                position: 'absolute', inset: 0,
                opacity: rightPanel === 'debrief' ? 1 : 0,
                pointerEvents: rightPanel === 'debrief' ? 'auto' : 'none',
                transition: 'opacity 0.3s',
              }}>
                <AIDebriefPanel active={rightPanel === 'debrief'} />
              </div>
              <div style={{
                position: 'absolute', inset: 0,
                opacity: rightPanel === 'comparison' ? 1 : 0,
                pointerEvents: rightPanel === 'comparison' ? 'auto' : 'none',
                transition: 'opacity 0.3s',
              }}>
                <LiveComparisonPanel active={rightPanel === 'comparison'} />
              </div>
              <div style={{
                position: 'absolute', inset: 0,
                opacity: rightPanel === 'racingLine' ? 1 : 0,
                pointerEvents: rightPanel === 'racingLine' ? 'auto' : 'none',
                transition: 'opacity 0.3s',
              }}>
                <RacingLineAnalysisPanel active={rightPanel === 'racingLine'} />
              </div>
              <div style={{
                position: 'absolute', inset: 0,
                opacity: rightPanel === 'physics' ? 1 : 0,
                pointerEvents: rightPanel === 'physics' ? 'auto' : 'none',
                transition: 'opacity 0.3s',
              }}>
                <CarPhysicsDebugPanel active={rightPanel === 'physics'} />
              </div>
            </div>

            {/* Coaching feed */}
            <div style={{ height: 220, overflow: 'hidden' }}>
              <CoachingFeed />
            </div>

          </div>
        </div>

        {/* ─ Bottom Bar — Controls + Timeline ─ */}
        <div
          className="panel"
          style={{
            height: 48,
            display: 'flex',
            alignItems: 'center',
            gap: 0,
            padding: '0 12px',
            flexShrink: 0,
          }}
        >
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', height: '100%', minWidth: 0 }}>
            <ReplayControls />
          </div>
        </div>

      </div>
    </ErrorBoundary>
  );
};

export default Dashboard;
