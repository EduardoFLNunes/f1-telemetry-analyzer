import React from 'react';
import { useTelemetryStore } from '../store/useTelemetryStore';
import { deltaTone, formatDelta, formatLapTime } from '../utils/lapFormat';
import { useRenderCounter } from '../hooks/useRenderCounter';

/* ─── Safe number formatter ───────────────────────────────────── */
const sf = (v: any, fb = 0, d = 0) => {
  const n = parseFloat(v);
  if (isNaN(n) || !isFinite(n)) return fb.toFixed(d);
  return d > 0 ? n.toFixed(d) : String(Math.round(n));
};

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

/**
 * Vehicle State, filling the column.
 *
 * Each reading is a band that grows with whatever height is left, rather than a
 * fixed block with dead space under it. The panel is the last thing in the left
 * column, so anything it does not use is empty screen at the bottom.
 */
export const VehicleStatePanel: React.FC = () => {
  useRenderCounter('VehicleStatePanel');
  const latestFrame = useTelemetryStore(s => s.latestFrame);
  const isStreaming = useTelemetryStore(s => s.isStreaming);

  const speed    = latestFrame ? ((latestFrame as any).speedKmh ?? latestFrame.speed * 3.6) : 0;
  const gear     = latestFrame ? (latestFrame.gear ?? 'N') : 'N';
  const rpm      = latestFrame ? ((latestFrame as any).rpm ?? 0) : 0;
  const throttle = latestFrame ? latestFrame.throttle : 0;
  const brake    = latestFrame ? latestFrame.brake : 0;
  const steering = latestFrame ? (latestFrame.steering ?? 0) : 0;
  const steerPercent = Math.max(-1, Math.min(1, steering));

  return (
    <div className="panel corner-accent vehicle-state">
      <div className="vs-head">
        <span className="label" style={{ color: 'var(--cyan)' }}>Vehicle State</span>
        <span className="vs-status">
          <i
            className={isStreaming ? 'status-live' : ''}
            style={{ background: isStreaming ? '#34d399' : '#1e293b' }}
          />
          <span className="num" style={{ color: isStreaming ? '#34d399' : '#334155' }}>
            {isStreaming ? 'LIVE' : 'OFFLINE'}
          </span>
        </span>
      </div>

      <div className="vs-row">
        <span className="label">Speed</span>
        <div className="vs-top">
          <span className="num vs-speed">{sf(speed, 0, 1)}</span>
          <span className="vs-unit">KM/H</span>
        </div>
      </div>

      <div className="vs-row">
        <span className="label">Gear</span>
        <div className="vs-top">
          <span className="num vs-gear">{String(gear)}</span>
          <span className="vs-unit">{sf(rpm, 0, 0)} RPM</span>
        </div>
      </div>

      <div className="vs-row">
        <div className="vs-top">
          <span className="label">Throttle</span>
          <span className="num vs-pct">{(throttle * 100).toFixed(0)}%</span>
        </div>
        <div className="vs-bar">
          <i style={{ width: `${Math.max(0, Math.min(1, throttle)) * 100}%`, background: 'var(--emerald, #34d399)' }} />
        </div>
      </div>

      <div className="vs-row">
        <div className="vs-top">
          <span className="label">Brake</span>
          <span className="num vs-pct">{(brake * 100).toFixed(0)}%</span>
        </div>
        <div className="vs-bar">
          <i style={{ width: `${Math.max(0, Math.min(1, brake)) * 100}%`, background: '#fb7185' }} />
        </div>
      </div>

      <div className="vs-row">
        <div className="vs-top">
          <span className="label">Steer</span>
          <span className="num vs-pct">{(steering * 90).toFixed(0)}&deg;</span>
        </div>
        {/* Grows from the middle, the way the wheel turns from centre. */}
        <div className="vs-steer">
          <i
            style={{
              width: `${Math.abs(steerPercent) * 50}%`,
              [steerPercent < 0 ? 'right' : 'left']: '50%',
            } as React.CSSProperties}
          />
        </div>
      </div>
    </div>
  );
};

/** Lap Timing: the clock and the delta, and nothing else. */
export const LapTimingPanel: React.FC = () => {
  useRenderCounter('LapTimingPanel');
  const lapMetrics = useTelemetryStore(s => s.lapMetrics);
  const delta = lapMetrics.delta;

  return (
    <div className="panel lap-timing">
      <span className="label">Lap Timing</span>
      <div className="lt-row">
        <span className="label">Lap Time</span>
        <span className="num lt-time">{formatLapTime(lapMetrics.currentLapTime)}</span>
      </div>
      <div className="lt-row">
        <span className="label">Delta</span>
        <span className={`num lt-delta ${deltaTone(delta)}`}>
          {formatDelta(delta)}
          {delta !== null && <span className="vs-unit" style={{ marginLeft: 5 }}>SEC</span>}
        </span>
      </div>
    </div>
  );
};

export const StabilityPanel: React.FC = () => {
  useRenderCounter('StabilityPanel');
  const latestFrame = useTelemetryStore(s => s.latestFrame);
  const isStreaming = useTelemetryStore(s => s.isStreaming);
  const stability = 1 - Math.min(1, Math.abs(latestFrame?.yaw_rate ?? 0) / 0.5);

  return (
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
  );
};
