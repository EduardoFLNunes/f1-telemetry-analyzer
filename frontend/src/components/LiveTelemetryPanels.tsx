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

/* ─── Metric Block ────────────────────────────────────────────── */
const Metric = ({
  label, value, unit, color = 'text-white', size = 'md'
}: { label: string; value: string; unit?: string; color?: string; size?: 'xs'|'sm'|'md'|'lg'|'xl' }) => {
  const sizeClass = { xs: 'text-xs', sm: 'text-sm', md: 'text-xl', lg: 'text-3xl', xl: 'text-[38px]' }[size];
  return (
    <div className="flex flex-col gap-0.5">
      <div className="label" style={{ fontSize: 8 }}>{label}</div>
      <div className={`num font-bold ${sizeClass} ${color} leading-none tracking-tight`}>
        {value}
        {unit && <span className="text-[9px] font-normal text-slate-600 ml-1">{unit}</span>}
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
      <span className="label" style={{ fontSize: 8 }}>{label}</span>
      {labelRight && <span className="num text-[9px] text-slate-500">{labelRight}</span>}
    </div>
    <div className="h-[4px] rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.06)' }}>
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

export const VehicleStatePanel: React.FC = () => {
  useRenderCounter('VehicleStatePanel');
  const latestFrame = useTelemetryStore(s => s.latestFrame);
  
  const speed    = latestFrame ? ((latestFrame as any).speedKmh ?? latestFrame.speed * 3.6) : 0;
  const gear     = latestFrame ? (latestFrame.gear ?? 'N') : 'N';
  const throttle = latestFrame ? latestFrame.throttle : 0;
  const brake    = latestFrame ? latestFrame.brake : 0;
  const steering = latestFrame ? (latestFrame.steering ?? 0) : 0;

  return (
    <div className="panel corner-accent" style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="label" style={{ color: 'var(--cyan)', fontSize: 8 }}>Vehicle State</div>

      {/* Speed — hero number */}
      <Metric label="SPEED" value={sf(speed, 0, 1)} unit="KM/H" color="text-cyan-300" size="xl" />

      <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end' }}>
        {/* Gear */}
        <Metric label="GEAR" value={String(gear)} color="text-white" size="lg" />
        {/* Gauges */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <GaugeBar label="THROTTLE" value={throttle}
            labelRight={`${(throttle * 100).toFixed(0)}%`} color="bg-emerald-400" />
          <GaugeBar label="BRAKE" value={brake}
            labelRight={`${(brake * 100).toFixed(0)}%`} color="bg-rose-400" />
          <GaugeBar label="STEER" value={(steering + 1) / 2} color="bg-amber-400" />
        </div>
      </div>
    </div>
  );
};

export const LapTimingPanel: React.FC = () => {
  useRenderCounter('LapTimingPanel');
  const latestFrame = useTelemetryStore(s => s.latestFrame);
  const lapMetrics = useTelemetryStore(s => s.lapMetrics);
  
  const delta    = lapMetrics.delta;
  const lapDelta = lapMetrics.lapDelta;
  const latG     = latestFrame ? (latestFrame.accel_g?.x ?? 0) : 0;
  const lonG     = latestFrame ? (latestFrame.accel_g?.z ?? 0) : 0;
  const rpm      = latestFrame ? ((latestFrame as any).rpm ?? 0) : 0;
  const deltaColor = deltaTone(delta);

  return (
    <div className="panel" style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 11 }}>
      <div className="label" style={{ fontSize: 8 }}>Lap Timing</div>
      <Metric label="LAP TIME" value={formatLapTime(lapMetrics.currentLapTime)} color="text-white" size="md" />
      <Metric label="DELTA" value={formatDelta(delta)} unit={delta === null ? undefined : 'SEC'} color={deltaColor} size="sm" />
      <Metric label="LAP DELTA" value={formatDelta(lapDelta)} unit={lapDelta === null ? undefined : 'SEC'} color={deltaTone(lapDelta)} size="sm" />

      <div style={{ height: 1, background: 'rgba(255,255,255,0.05)' }} />

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <Metric label="LAT_G"  value={sf(latG, 0, 2)}  color="text-pink-400"   size="xs" />
        <Metric label="LON_G"  value={sf(lonG, 0, 2)}  color="text-amber-400"  size="xs" />
        <Metric label="RPM_K"  value={sf(rpm / 1000, 0, 1)} unit="K" color="text-slate-300" size="xs" />
        <Metric label="YAW"    value={sf((latestFrame?.yaw_rate ?? 0), 0, 2)} color="text-violet-300" size="xs" />
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
    <div className="panel" style={{ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 9 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span className="label" style={{ fontSize: 8 }}>Stability</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <div
            className={isStreaming ? 'status-live' : ''}
            style={{
              width: 6, height: 6, borderRadius: '50%',
              background: isStreaming ? '#34d399' : '#1e293b',
            }}
          />
          <span className="num" style={{ fontSize: 9, color: isStreaming ? '#34d399' : '#334155', fontWeight: 700 }}>
            {isStreaming ? 'LIVE' : 'OFFLINE'}
          </span>
        </div>
      </div>
      <StabilityViz value={stability} />
    </div>
  );
};
