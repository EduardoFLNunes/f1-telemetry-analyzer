/**
 * F1 Motorsport Intelligence Workstation — Master Layout
 * Complete 9-Phase reformulation
 */
import React, { useEffect, useState } from 'react';
import { TrackRenderer } from './components/map/TrackRenderer.jsx';
import { TelemetryTraces } from './components/TelemetryTraces';
import { AssistedLapTraces } from './components/AssistedLapTraces';
import { GGDiagram } from './components/GGDiagram';
import { CoachingFeed } from './components/CoachingFeed';
import { AIDebriefPanel } from './components/AIDebriefPanel';
import { AIEngineerPanel } from './components/AIEngineerPanel';
import { AssistedAnalysisPanel } from './components/AssistedAnalysisPanel';
import { CarPhysicsDebugPanel } from './components/CarPhysicsDebugPanel';
import { LiveComparisonPanel } from './components/LiveComparisonPanel';
import { RacingLineAnalysisPanel } from './components/RacingLineAnalysisPanel';
import { DesktopRuntimePanel } from './components/DesktopRuntimePanel';
import { SessionLapsPanel } from './components/SessionLapsPanel';
import { LiveSessionStrip } from './components/LiveSessionStrip';
import { DataQualityPanel } from './components/DataQualityPanel';
import { ReplayControls } from './components/ReplayControls';
import { CognitiveDashboard } from './components/CognitiveDashboard';
import { Header } from './components/Header';
import { VehicleStatePanel, LapTimingPanel, StabilityPanel } from './components/LiveTelemetryPanels';
import { useRenderCounter } from './hooks/useRenderCounter';
import { ErrorBoundary } from './components/ErrorBoundary';
import { api } from './api/client';

/* ─── Dashboard ───────────────────────────────────────────────── */
const Dashboard: React.FC = () => {
  useRenderCounter('Dashboard');
  const [trackData, setTrackData] = useState<any>(null);
  const [rightPanel, setRightPanel] = useState<'laps'|'quality'|'assisted'|'engineer'|'debrief'|'comparison'|'racingLine'|'physics'>('laps');
  const [tracePanel, setTracePanel] = useState<'lapComparison'|'assistTraces'>('lapComparison');
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
      <div className="workstation-shell">
        {/* ─ Header ─ */}
        <Header time={time} />
        <LiveSessionStrip />

        {/* ─ Main Content ─ */}
        <div className="dashboard-grid">

          {/* ═══ LEFT COLUMN — Engineering Metrics ═══ */}
          <div className="dashboard-column">

            {/* Primary vehicle state block */}
            <VehicleStatePanel />

            {/* Timing & G-forces */}
            <LapTimingPanel />

            {/* G-G Diagram */}
            <div className="panel dashboard-flex-panel" style={{ padding: '8px' }}>
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
          <div className="dashboard-column">

            {/* Track map — primary viewport */}
            <div className="panel track-stage">
              <TrackRenderer trackData={trackData} />
            </div>

            {/* Lap comparison panel */}
            <div className="panel telemetry-stage" style={{ position: 'relative' }}>
              <div
                className="panel px-1 py-0.5 flex gap-0.5"
                style={{
                  position: 'absolute',
                  top: 3,
                  left: '50%',
                  transform: 'translateX(-50%)',
                  zIndex: 10,
                  background: 'rgba(8,12,22,0.9)',
                  borderColor: 'rgba(148,163,184,0.12)',
                }}
              >
                {([
                  ['lapComparison', 'Lap Comparison'],
                  ['assistTraces', 'Lap Traces'],
                ] as const).map(([mode, label]) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => setTracePanel(mode)}
                    className="num"
                    style={{
                      height: 17,
                      padding: '0 7px',
                      borderRadius: 2,
                      border: '1px solid transparent',
                      background: tracePanel === mode ? 'rgba(34,211,238,0.1)' : 'transparent',
                      color: tracePanel === mode ? '#67e8f9' : '#64748b',
                      cursor: 'pointer',
                      fontSize: 7,
                      fontWeight: 800,
                      textTransform: 'uppercase',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {tracePanel === 'lapComparison'
                ? <TelemetryTraces />
                : <AssistedLapTraces active={tracePanel === 'assistTraces'} />}
            </div>

          </div>

          {/* ═══ RIGHT COLUMN — Intelligence Hub ═══ */}
          <div className="dashboard-column">

            {/* Panel selector tabs */}
            <div className="panel intelligence-tabs">
              {(['laps', 'quality', 'assisted', 'engineer', 'debrief', 'comparison', 'racingLine', 'physics'] as const).map(tab => (
                <button
                  key={tab}
                  onClick={() => setRightPanel(tab)}
                  className="num"
                  style={{
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
                  {tab === 'laps' ? 'Voltas' : (tab === 'quality' ? 'Qualidade' : (tab === 'assisted' ? 'Assist' : (tab === 'engineer' ? 'Engineer' : (tab === 'debrief' ? 'Debrief' : (tab === 'comparison' ? 'Compare' : (tab === 'racingLine' ? 'Line' : 'Physics'))))))}
                </button>
              ))}
            </div>

            {/* Keep panel state mounted; active props suspend hidden polling and subscriptions. */}
            <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
              <div style={{
                position: 'absolute', inset: 0,
                opacity: rightPanel === 'laps' ? 1 : 0,
                pointerEvents: rightPanel === 'laps' ? 'auto' : 'none',
                transition: 'opacity 0.3s',
              }}>
                <SessionLapsPanel
                  active={rightPanel === 'laps'}
                  onOpenAssistedAnalysis={() => setRightPanel('assisted')}
                />
              </div>
              <div style={{
                position: 'absolute', inset: 0,
                opacity: rightPanel === 'quality' ? 1 : 0,
                pointerEvents: rightPanel === 'quality' ? 'auto' : 'none',
                transition: 'opacity 0.3s',
              }}>
                <DataQualityPanel active={rightPanel === 'quality'} />
              </div>
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
              <div style={{
                position: 'absolute', inset: 0,
                opacity: rightPanel === 'assisted' ? 1 : 0,
                pointerEvents: rightPanel === 'assisted' ? 'auto' : 'none',
                transition: 'opacity 0.3s',
              }}>
                <AssistedAnalysisPanel active={rightPanel === 'assisted'} />
              </div>
            </div>

            {/* Coaching feed */}
            <div style={{
              height: rightPanel === 'laps' || rightPanel === 'quality' || rightPanel === 'assisted' ? 0 : 150,
              overflow: 'hidden',
              opacity: rightPanel === 'laps' || rightPanel === 'quality' || rightPanel === 'assisted' ? 0 : 1,
              transition: 'height 0.25s ease, opacity 0.2s ease',
            }}>
              {rightPanel !== 'laps' && rightPanel !== 'quality' && rightPanel !== 'assisted' && <CoachingFeed />}
            </div>

            <div style={{
              height: rightPanel === 'laps' || rightPanel === 'quality' || rightPanel === 'assisted' ? 0 : 160,
              overflow: 'hidden',
              opacity: rightPanel === 'laps' || rightPanel === 'quality' || rightPanel === 'assisted' ? 0 : 1,
              transition: 'height 0.25s ease, opacity 0.2s ease',
            }}>
              <DesktopRuntimePanel active={rightPanel !== 'laps' && rightPanel !== 'quality' && rightPanel !== 'assisted'} />
            </div>

          </div>
        </div>

        {/* ─ Bottom Bar — Controls + Timeline ─ */}
        <div className="panel dashboard-bottom-bar">
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', height: '100%', minWidth: 0 }}>
            <ReplayControls />
          </div>
        </div>

      </div>
    </ErrorBoundary>
  );
};

export default Dashboard;
