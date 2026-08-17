/**
 * Live driving view.
 *
 * Only what is useful with a car on track lives here. Recorded-session browsing,
 * assisted analysis, data-quality and runtime diagnostics moved to their own
 * pages, which is what took the right rail from eight competing tabs down to
 * four and gave the track map room to breathe.
 */
import React, { useEffect, useState } from 'react';
import { TrackRenderer } from './components/map/TrackRenderer';
import { TrackElevationRibbon } from './components/map/TrackElevationRibbon';
import { TelemetryTraces } from './components/TelemetryTraces';
import { GGDiagram } from './components/GGDiagram';
import { CoachingFeed } from './components/CoachingFeed';
import { AIDebriefPanel } from './components/AIDebriefPanel';
import { AIEngineerPanel } from './components/AIEngineerPanel';
import { LiveComparisonPanel } from './components/LiveComparisonPanel';
import { RacingLineAnalysisPanel } from './components/RacingLineAnalysisPanel';
import { LiveSessionStrip } from './components/LiveSessionStrip';
import { ReplayControls } from './components/ReplayControls';
import { CognitiveDashboard } from './components/CognitiveDashboard';
import { Header } from './components/Header';
import { VehicleStatePanel, LapTimingPanel, StabilityPanel } from './components/LiveTelemetryPanels';
import { useRenderCounter } from './hooks/useRenderCounter';
import { ErrorBoundary } from './components/ErrorBoundary';
import { api } from './api/client';
import { useTelemetryStore } from './store/useTelemetryStore';

type LivePanel = 'comparison' | 'racingLine' | 'engineer' | 'debrief';

const LIVE_PANELS: Array<[LivePanel, string]> = [
  ['comparison', 'Compare'],
  ['racingLine', 'Linha'],
  ['engineer', 'Engineer'],
  ['debrief', 'Debrief'],
];

const Dashboard: React.FC = () => {
  useRenderCounter('Dashboard');
  const [trackData, setTrackData] = useState<any>(null);
  const [trackKey, setTrackKey] = useState<string | null>(null);
  const latestFrame = useTelemetryStore((state) => state.latestFrame);
  const [rightPanel, setRightPanel] = useState<LivePanel>('comparison');
  const [time, setTime] = useState(() => new Date());

  useEffect(() => {
    if (!trackKey) {
      setTrackData(null);
      return undefined;
    }
    let cancelled = false;
    let inFlight = false;
    let refreshTimer: number | undefined;
    const loadTrack = async () => {
      if (inFlight) return;
      inFlight = true;
      let loaded = false;
      try {
        const data = await api.getTrackGeometry();
        if (!cancelled && data.track) {
          setTrackData(data.track);
          loaded = true;
        } else if (!cancelled) {
          setTrackData(null);
        }
      } catch {
        if (!cancelled) setTrackData(null);
      } finally {
        inFlight = false;
        if (!cancelled && !loaded) {
          refreshTimer = window.setTimeout(loadTrack, 5000);
        }
      }
    };
    loadTrack();
    return () => {
      cancelled = true;
      if (refreshTimer !== undefined) window.clearTimeout(refreshTimer);
    };
  }, [trackKey]);

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <ErrorBoundary>
      <div className="workstation-shell">
        <Header time={time} />
        <LiveSessionStrip onTrackKeyChange={setTrackKey} />

        <div className="dashboard-grid">
          {/* ═══ LEFT — vehicle state ═══ */}
          <div className="dashboard-column">
            <VehicleStatePanel />
            <LapTimingPanel />

            <div className="panel dashboard-flex-panel" style={{ padding: '8px' }}>
              <div className="label" style={{ fontSize: 6, paddingLeft: 4 }}>G-G Diagram</div>
              <div style={{ flex: 1 }}>
                <GGDiagram />
              </div>
            </div>

            <StabilityPanel />

            <div style={{ flex: 1, overflow: 'hidden' }}>
              <CognitiveDashboard />
            </div>
          </div>

          {/* ═══ CENTER — track map, road relief, traces ═══ */}
          <div className="dashboard-column">
            {/* The map says where the car is; the ribbon under it says what the
                road is doing there -- climbing, dropping, leaning into a corner. */}
            <div className="panel track-stage" style={{ flex: '1 1 52%', minHeight: 0 }}>
              <TrackRenderer trackData={trackData} />
            </div>

            <div className="panel" style={{ flex: '1 1 34%', minHeight: 190, padding: 0, overflow: 'hidden' }}>
              <TrackElevationRibbon trackData={trackData} car={latestFrame} />
            </div>

            <div className="panel telemetry-stage" style={{ flex: '1 1 30%', minHeight: 0 }}>
              <TelemetryTraces />
            </div>
          </div>

          {/* ═══ RIGHT — live intelligence ═══ */}
          <div className="dashboard-column">
            <div className="panel intelligence-tabs">
              {LIVE_PANELS.map(([tab, label]) => (
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
                  {label}
                </button>
              ))}
            </div>

            {/* Panels stay mounted; `active` suspends polling on the hidden ones. */}
            <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
              {LIVE_PANELS.map(([tab]) => (
                <div
                  key={tab}
                  style={{
                    position: 'absolute',
                    inset: 0,
                    opacity: rightPanel === tab ? 1 : 0,
                    pointerEvents: rightPanel === tab ? 'auto' : 'none',
                    transition: 'opacity 0.3s',
                  }}
                >
                  {tab === 'comparison' && <LiveComparisonPanel active={rightPanel === 'comparison'} />}
                  {tab === 'racingLine' && <RacingLineAnalysisPanel active={rightPanel === 'racingLine'} />}
                  {tab === 'engineer' && <AIEngineerPanel active={rightPanel === 'engineer'} />}
                  {tab === 'debrief' && <AIDebriefPanel active={rightPanel === 'debrief'} />}
                </div>
              ))}
            </div>

            <div style={{ height: 150, overflow: 'hidden' }}>
              <CoachingFeed />
            </div>
          </div>
        </div>

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
