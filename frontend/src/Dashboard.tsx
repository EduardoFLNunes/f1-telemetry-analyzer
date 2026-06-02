import React, { useEffect, useState } from 'react';
import { PanelLeftClose, PanelLeftOpen } from 'lucide-react';
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
import { useRenderCounter } from './hooks/useRenderCounter';
import { ErrorBoundary } from './components/ErrorBoundary';
import { api } from './api/client';

type RightPanel = 'engineer' | 'debrief' | 'comparison' | 'racingLine' | 'physics';

const RIGHT_TABS: RightPanel[] = ['engineer', 'debrief', 'comparison', 'racingLine', 'physics'];

const tabLabel = (tab: RightPanel) => {
  if (tab === 'engineer') return 'Engineer';
  if (tab === 'debrief') return 'Debrief';
  if (tab === 'comparison') return 'Compare';
  if (tab === 'racingLine') return 'Line';
  return 'Physics';
};

const LeftTelemetryStack = () => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 2, height: '100%', overflow: 'hidden' }}>
    <VehicleStatePanel />
    <LapTimingPanel />
    <div className="panel" style={{ padding: 10, minHeight: 260, flex: 1, display: 'flex', flexDirection: 'column', gap: 8, overflow: 'hidden' }}>
      <div className="label" style={{ fontSize: 8, paddingLeft: 4 }}>G-G Diagram</div>
      <div style={{ flex: 1, minHeight: 0 }}>
        <GGDiagram />
      </div>
    </div>
    <StabilityPanel />
    <div style={{ minHeight: 120, overflow: 'hidden' }}>
      <CognitiveDashboard />
    </div>
  </div>
);

const Dashboard: React.FC = () => {
  useRenderCounter('Dashboard');
  const [trackData, setTrackData] = useState<any>(null);
  const [rightPanel, setRightPanel] = useState<RightPanel>('engineer');
  const [leftPanelOpen, setLeftPanelOpen] = useState(false);
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
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <ErrorBoundary>
      <div
        className="flex flex-col select-none"
        style={{ width: '100vw', height: '100vh', background: '#06060d', color: '#f1f5f9', overflow: 'hidden' }}
      >
        <Header time={time} />

        <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
          {!leftPanelOpen && (
            <button
              type="button"
              onClick={() => setLeftPanelOpen(true)}
              className="num"
              title="Abrir telemetria"
              style={{
                position: 'absolute',
                top: 8,
                left: 8,
                zIndex: 35,
                height: 34,
                display: 'flex',
                alignItems: 'center',
                gap: 7,
                padding: '0 11px',
                borderRadius: 4,
                border: '1px solid rgba(34,211,238,0.35)',
                background: 'rgba(8,13,24,0.92)',
                color: '#22d3ee',
                fontSize: 9,
                fontWeight: 900,
                letterSpacing: '0.08em',
                cursor: 'pointer',
              }}
            >
              <PanelLeftOpen size={14} />
              TELEMETRY
            </button>
          )}

          {leftPanelOpen && (
            <div
              style={{
                position: 'absolute',
                inset: '0 auto 0 0',
                width: 'clamp(330px, 28vw, 460px)',
                zIndex: 34,
                background: '#06060d',
                borderRight: '1px solid rgba(255,255,255,0.08)',
                boxShadow: '18px 0 36px rgba(0,0,0,0.42)',
                padding: 2,
                display: 'flex',
                flexDirection: 'column',
                gap: 2,
              }}
            >
              <div className="panel" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '7px 9px', flexShrink: 0 }}>
                <span className="num" style={{ fontSize: 10, color: '#22d3ee', fontWeight: 900, letterSpacing: '0.12em' }}>TELEMETRY</span>
                <button
                  type="button"
                  onClick={() => setLeftPanelOpen(false)}
                  title="Ocultar telemetria"
                  style={{
                    width: 28,
                    height: 26,
                    display: 'grid',
                    placeItems: 'center',
                    borderRadius: 4,
                    border: '1px solid rgba(255,255,255,0.08)',
                    background: 'rgba(255,255,255,0.03)',
                    color: '#94a3b8',
                    cursor: 'pointer',
                  }}
                >
                  <PanelLeftClose size={15} />
                </button>
              </div>
              <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
                <LeftTelemetryStack />
              </div>
            </div>
          )}

          <div style={{ height: '100%', display: 'grid', gridTemplateColumns: 'minmax(0, 1.28fr) minmax(420px, 1fr)', gap: 1, padding: 1, overflow: 'hidden' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 1, overflow: 'hidden' }}>
              <div className="panel" style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
                <TrackRenderer trackData={trackData} />
              </div>

              <div className="panel" style={{ height: 200, overflow: 'hidden' }}>
                <TelemetryTraces />
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 1, overflow: 'hidden' }}>
              <div className="panel" style={{ display: 'flex', gap: 1, padding: 1 }}>
                {RIGHT_TABS.map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setRightPanel(tab)}
                    className="num"
                    style={{
                      flex: 1,
                      padding: '8px 0',
                      fontSize: 9,
                      fontWeight: 800,
                      textTransform: 'uppercase',
                      letterSpacing: '0.08em',
                      borderRadius: 2,
                      border: 'none',
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                      background: rightPanel === tab ? 'rgba(34,211,238,0.08)' : 'transparent',
                      color: rightPanel === tab ? '#22d3ee' : '#475569',
                      outline: rightPanel === tab ? '1px solid rgba(34,211,238,0.2)' : '1px solid transparent',
                    }}
                  >
                    {tabLabel(tab)}
                  </button>
                ))}
              </div>

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

              <div style={{ height: 150, overflow: 'hidden' }}>
                <CoachingFeed />
              </div>
            </div>
          </div>
        </div>

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
