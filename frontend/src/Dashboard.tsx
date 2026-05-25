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
import { ReplayControls } from './components/ReplayControls';
import { SessionTimeline } from './components/SessionTimeline';
import { CognitiveDashboard } from './components/CognitiveDashboard';
import { Header } from './components/Header';
import { useTelemetryStore } from './store/useTelemetryStore';
import { ErrorBoundary } from './components/ErrorBoundary';
import { api } from './api/client';

/* ─── Safe number formatter ───────────────────────────────────── */
const sf = (v: any, fb = 0, d = 0) => {
  const n = parseFloat(v);
  if (isNaN(n) || !isFinite(n)) return fb.toFixed(d);
  return d > 0 ? n.toFixed(d) : String(Math.round(n));
};

/* ─── Metric Block ────────────────────────────────────────────── */
const Metric = ({
  label, value, unit, color = 'text-white', size = 'md'
}: { label: string; value: string; unit?: string; color?: string; size?: 'xs'|'sm'|'md'|'lg'|'xl' }) => {
  const sizeClass = { xs: 'text-xs', sm: 'text-sm', md: 'text-xl', lg: 'text-3xl', xl: 'text-[38px]' }[size];
  return (
    <div className="flex flex-col gap-0.5">
      <div className="label">{label}</div>
      <div className={`num font-bold ${sizeClass} ${color} leading-none tracking-tight`}>
        {value}
        {unit && <span className="text-[7px] font-normal text-slate-700 ml-1">{unit}</span>}
      </div>
    </div>
  );
};

/* ─── Gauge Bar ───────────────────────────────────────────────── */
const GaugeBar = ({
  value, color, label, labelRight
}: { value: number; color: string; label: string; labelRight?: string }) => (
  <div className="flex flex-col gap-[3px]">
    <div className="flex justify-between">
      <span className="label" style={{ fontSize: 6 }}>{label}</span>
      {labelRight && <span className="num text-[7px] text-slate-600">{labelRight}</span>}
    </div>
    <div className="h-[3px] rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.06)' }}>
      <div
        className={`h-full rounded-full transition-all duration-75 ${color}`}
        style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }}
      />
    </div>
  </div>
);

/* ─── Stability Viz ───────────────────────────────────────────── */
const StabilityViz = ({ value }: { value: number }) => (
  <div className="flex gap-[2px]">
    {Array.from({ length: 20 }, (_, i) => {
      const lit = i < Math.round(value * 20);
      const color = value > 0.8 ? '#22d3ee' : value > 0.5 ? '#fbbf24' : '#fb7185';
      return (
        <div
          key={i}
          className="flex-1 h-[3px] rounded-sm transition-all duration-100"
          style={{ background: lit ? color : 'rgba(255,255,255,0.05)' }}
        />
      );
    })}
  </div>
);

/* ─── Dashboard ───────────────────────────────────────────────── */
const Dashboard: React.FC = () => {
  const [trackData, setTrackData] = useState<any>(null);
  const latestFrame  = useTelemetryStore(s => s.latestFrame);
  const isStreaming  = useTelemetryStore(s => s.isStreaming);
  const [rightPanel, setRightPanel] = useState<'engineer'|'debrief'>('engineer');
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

  /* Live telemetry values */
  const speed    = latestFrame ? latestFrame.speed * 3.6 : 0;
  const gear     = latestFrame ? (latestFrame.gear ?? 'N') : 'N';
  const throttle = latestFrame ? latestFrame.throttle : 0;
  const brake    = latestFrame ? latestFrame.brake : 0;
  const delta    = latestFrame ? (latestFrame.delta ?? 0) : 0;
  const latG     = latestFrame ? (latestFrame.accel_g?.x ?? 0) : 0;
  const lonG     = latestFrame ? (latestFrame.accel_g?.z ?? 0) : 0;
  const rpm      = latestFrame ? ((latestFrame as any).rpm ?? 0) : 0;
  const steering = latestFrame ? (latestFrame.steering ?? 0) : 0;
  const stability = 1 - Math.min(1, Math.abs(latestFrame?.yaw_rate ?? 0) / 0.5);

  const deltaColor = delta <= 0 ? 'text-emerald-400' : 'text-rose-400';
  const deltaStr   = delta === 0 ? '0.000' : `${delta > 0 ? '+' : ''}${delta.toFixed(3)}`;

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
        <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '176px 1fr 252px', gap: 1, padding: 1, overflow: 'hidden' }}>

          {/* ═══ LEFT COLUMN — Engineering Metrics ═══ */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 1, overflow: 'hidden' }}>

            {/* Primary vehicle state block */}
            <div className="panel corner-accent" style={{ padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div className="label" style={{ color: 'var(--cyan)', fontSize: 6 }}>Vehicle State</div>

              {/* Speed — hero number */}
              <Metric label="SPEED" value={sf(speed, 0, 1)} unit="KM/H" color="text-cyan-300" size="xl" />

              <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end' }}>
                {/* Gear */}
                <Metric label="GEAR" value={String(gear)} color="text-white" size="lg" />
                {/* Gauges */}
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <GaugeBar label="THROTTLE" value={throttle}
                    labelRight={`${(throttle * 100).toFixed(0)}%`} color="bg-emerald-400" />
                  <GaugeBar label="BRAKE" value={brake}
                    labelRight={`${(brake * 100).toFixed(0)}%`} color="bg-rose-400" />
                  <GaugeBar label="STEER" value={(steering + 1) / 2} color="bg-amber-400" />
                </div>
              </div>
            </div>

            {/* Timing & G-forces */}
            <div className="panel" style={{ padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div className="label" style={{ fontSize: 6 }}>Lap Delta</div>
              <Metric label="DELTA_T" value={deltaStr} unit="SEC" color={deltaColor} size="md" />

              <div style={{ height: 1, background: 'rgba(255,255,255,0.05)' }} />

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                <Metric label="LAT_G"  value={sf(latG, 0, 2)}  color="text-pink-400"   size="xs" />
                <Metric label="LON_G"  value={sf(lonG, 0, 2)}  color="text-amber-400"  size="xs" />
                <Metric label="RPM_K"  value={sf(rpm / 1000, 0, 1)} unit="K" color="text-slate-300" size="xs" />
                <Metric label="YAW"    value={sf((latestFrame?.yaw_rate ?? 0), 0, 2)} color="text-violet-300" size="xs" />
              </div>
            </div>

            {/* G-G Diagram */}
            <div className="panel" style={{ padding: '8px', flex: 1, display: 'flex', flexDirection: 'column', gap: 6, overflow: 'hidden' }}>
              <div className="label" style={{ fontSize: 6, paddingLeft: 4 }}>G-G Diagram</div>
              <div style={{ flex: 1 }}>
                <GGDiagram />
              </div>
            </div>

            {/* Stability + Cognitive */}
            <div className="panel" style={{ padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="label" style={{ fontSize: 6 }}>Stability</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <div
                    className={isStreaming ? 'status-live' : ''}
                    style={{
                      width: 6, height: 6, borderRadius: '50%',
                      background: isStreaming ? '#34d399' : '#1e293b',
                    }}
                  />
                  <span className="num" style={{ fontSize: 7, color: isStreaming ? '#34d399' : '#334155', fontWeight: 700 }}>
                    {isStreaming ? 'LIVE' : 'OFFLINE'}
                  </span>
                </div>
              </div>
              <StabilityViz value={stability} />
            </div>

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

            {/* Telemetry multi-trace panel */}
            <div className="panel" style={{ height: 200, overflow: 'hidden' }}>
              <TelemetryTraces />
            </div>

          </div>

          {/* ═══ RIGHT COLUMN — Intelligence Hub ═══ */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 1, overflow: 'hidden' }}>

            {/* Panel selector tabs */}
            <div className="panel" style={{ display: 'flex', gap: 1, padding: 1 }}>
              {(['engineer', 'debrief'] as const).map(tab => (
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
                  {tab === 'engineer' ? 'AI Engineer' : 'Debrief'}
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
                <AIEngineerPanel />
              </div>
              <div style={{
                position: 'absolute', inset: 0,
                opacity: rightPanel === 'debrief' ? 1 : 0,
                pointerEvents: rightPanel === 'debrief' ? 'auto' : 'none',
                transition: 'opacity 0.3s',
              }}>
                <AIDebriefPanel />
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
          {/* Replay controls take ~60% */}
          <div style={{ flex: '0 0 auto', display: 'flex', alignItems: 'center', height: '100%' }}>
            <ReplayControls />
          </div>

          {/* Divider */}
          <div style={{ width: 1, height: 24, background: 'rgba(255,255,255,0.06)', margin: '0 12px', flexShrink: 0 }} />

          {/* Session timeline takes remaining */}
          <div style={{ flex: 1, height: '100%', display: 'flex', alignItems: 'center', overflow: 'hidden' }}>
            <SessionTimeline />
          </div>
        </div>

      </div>
    </ErrorBoundary>
  );
};

export default Dashboard;
