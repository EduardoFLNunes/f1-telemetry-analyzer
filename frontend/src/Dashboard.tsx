/**
 * Live driving view, in three.
 *
 * Left is what the car is doing: how the lap is going by sector, the clock, and
 * the state of the car itself, which stretches to fill whatever the first two
 * leave behind. Centre is the track -- the follow map with its four corners,
 * and the lap comparison under it. Right is the assisted analysis.
 *
 * The proportions are 20/60/20 and hold at every width. The map is the point of
 * the screen, so it gets three times either side.
 */
import React, { useEffect, useState } from 'react';
import { TrackRenderer } from './components/map/TrackRenderer';
import { TelemetryTraces } from './components/TelemetryTraces';
import { SectorComparison } from './components/SectorComparison';
import { CoachingFeed } from './components/CoachingFeed';
import { AIDebriefPanel } from './components/AIDebriefPanel';
import { AIEngineerPanel } from './components/AIEngineerPanel';
import { LiveComparisonPanel } from './components/LiveComparisonPanel';
import { RacingLineAnalysisPanel } from './components/RacingLineAnalysisPanel';
import { LiveSessionStrip } from './components/LiveSessionStrip';
import { ReplayControls } from './components/ReplayControls';
import { Header } from './components/Header';
import { VehicleStatePanel, LapTimingPanel } from './components/LiveTelemetryPanels';
import { useRenderCounter } from './hooks/useRenderCounter';
import { ErrorBoundary } from './components/ErrorBoundary';
import { api } from './api/client';

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
          {/* ═══ ESQUERDA — o carro ═══ */}
          <div className="dashboard-column">
            <SectorComparison />
            <LapTimingPanel />
            <VehicleStatePanel />
          </div>

          {/* ═══ CENTRO — a pista ═══ */}
          <div className="dashboard-column">
            <div className="panel map-stage">
              <TrackRenderer trackData={trackData} />
            </div>

            <div className="panel lap-comparison-stage">
              <TelemetryTraces />
            </div>
          </div>

          {/* ═══ DIREITA — analise assistida ═══ */}
          <div className="dashboard-column col-right">
            <div className="panel intelligence-tabs">
              {LIVE_PANELS.map(([tab, label]) => (
                <button
                  key={tab}
                  onClick={() => setRightPanel(tab)}
                  className="num"
                  style={{
                    padding: '7px 0',
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

            <div style={{ height: 168, overflow: 'hidden' }}>
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
