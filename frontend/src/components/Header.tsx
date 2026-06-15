/**
 * Professional Motorsport Engineering HUD Header
 * F1 pitwall-inspired tactical information bar.
 */
import React from 'react';
import { useTelemetryStore } from '../store/useTelemetryStore';
import { deltaTone, formatDelta, formatLapTime } from '../utils/lapFormat';

interface HeaderProps {
  time?: Date;
}

export const Header: React.FC<HeaderProps> = ({ time = new Date() }) => {
  const isStreaming  = useTelemetryStore(s => s.isStreaming);
  const latestFrame  = useTelemetryStore(s => s.latestFrame);
  const historyLen   = useTelemetryStore(s => s.history.length);
  const lapMetrics   = useTelemetryStore(s => s.lapMetrics);
  const isConnected  = isStreaming;

  const timeStr = time.toLocaleTimeString('en', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const lapStr = formatLapTime(lapMetrics.currentLapTime);
  const deltaValue = lapMetrics.delta;

  return (
    <header
      className="flex items-center justify-between px-4 shrink-0 select-none"
      style={{
        height: '38px',
        background: '#080810',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
      }}
    >
      {/* ── Left: Wordmark + build ── */}
      <div className="flex items-center gap-3">
        {/* Accent bar */}
        <div style={{ width: 3, height: 22, background: 'linear-gradient(to bottom, #22d3ee, #06b6d4)', borderRadius: 2 }} />

        <div className="flex flex-col justify-center -gap-0">
          <div className="flex items-baseline gap-2">
            <span className="font-eng font-black text-[11px] tracking-[0.22em] text-white uppercase">
              Motorsport
            </span>
            <span className="font-eng font-light text-[11px] tracking-[0.22em] text-cyan-400 uppercase">
              Intelligence
            </span>
            <span className="font-eng font-black text-[11px] tracking-[0.22em] text-slate-400 uppercase">
              Workstation
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="num text-[7px] text-slate-700 tracking-widest">BUILD v13.0 // DATA RELIABILITY</span>
            <div className="w-1 h-1 rounded-full bg-emerald-400 status-live" />
          </div>
        </div>
      </div>

      {/* ── Center: Session Info ── */}
      <div className="flex items-center gap-6">

        {/* Lap time */}
        <div className="flex flex-col items-center -gap-0">
          <span className="label" style={{ fontSize: 6 }}>LAP_TIME</span>
          <span className="num font-bold text-[13px] text-white tracking-tight leading-none">{lapStr}</span>
        </div>

        <div style={{ width: 1, height: 20, background: 'rgba(255,255,255,0.06)' }} />

        {/* Lap number */}
        <div className="flex flex-col items-center">
          <span className="label" style={{ fontSize: 6 }}>LAP</span>
          <span className="num font-bold text-[13px] text-slate-300 leading-none">
            {lapMetrics.currentLapNumber ?? latestFrame?.lap_number ?? '--'}
          </span>
        </div>

        <div style={{ width: 1, height: 20, background: 'rgba(255,255,255,0.06)' }} />

        {/* Delta */}
        <div className="flex flex-col items-center">
          <span className="label" style={{ fontSize: 6 }}>DELTA</span>
          <span className={`num font-bold text-[13px] leading-none ${deltaTone(deltaValue)}`}>
            {formatDelta(deltaValue)}
          </span>
        </div>

        <div style={{ width: 1, height: 20, background: 'rgba(255,255,255,0.06)' }} />

        {/* Frames */}
        <div className="flex flex-col items-center">
          <span className="label" style={{ fontSize: 6 }}>FRAMES</span>
          <span className="num font-bold text-[11px] text-slate-500 leading-none">{historyLen.toLocaleString()}</span>
        </div>
      </div>

      {/* ── Right: System status ── */}
      <div className="flex items-center gap-5">
        {/* Status indicators */}
        <div className="flex items-center gap-4 px-3 py-1 rounded-sm"
          style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)' }}>
          <StatusPill label="LINK" active={isConnected} color="cyan" />
          <StatusPill label="STREAM" active={isStreaming} color="emerald" />
          <StatusPill label="SPATIAL" active={true} color="cyan" />
          <StatusPill label="AI_CORE" active={true} color="violet" />
        </div>

        {/* Clock */}
        <div className="flex flex-col items-end -gap-0">
          <span className="label" style={{ fontSize: 6 }}>LOCAL_TIME</span>
          <span className="num font-bold text-[11px] text-slate-400 leading-none">{timeStr}</span>
        </div>
      </div>
    </header>
  );
};

const StatusPill = ({ label, active, color }: { label: string; active: boolean; color: 'cyan'|'emerald'|'violet' }) => {
  const colors = {
    cyan:    { dot: '#22d3ee', text: 'text-cyan-400',    dim: 'text-slate-700' },
    emerald: { dot: '#34d399', text: 'text-emerald-400', dim: 'text-slate-700' },
    violet:  { dot: '#a78bfa', text: 'text-violet-400',  dim: 'text-slate-700' },
  };
  const c = colors[color];
  return (
    <div className="flex items-center gap-1.5">
      <div
        className={active ? 'status-live' : ''}
        style={{
          width: 5, height: 5, borderRadius: '50%',
          background: active ? c.dot : '#1e293b',
          boxShadow: active ? `0 0 6px ${c.dot}80` : 'none',
          flexShrink: 0,
        }}
      />
      <span className={`num text-[7px] font-bold uppercase tracking-widest ${active ? c.text : 'text-slate-700'}`}>
        {label}
      </span>
    </div>
  );
};
