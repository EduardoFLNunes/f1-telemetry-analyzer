import React, { useState } from 'react';
import { useTelemetryStore } from '../store/useTelemetryStore';
import { deltaTone, formatDelta, formatLapTime } from '../utils/lapFormat';

const Stat = ({
  label,
  value,
  color = 'text-slate-400',
}: {
  label: string;
  value: string;
  color?: string;
}) => (
  <div className="flex flex-col justify-center" style={{ minWidth: 62 }}>
    <span className="num text-[6px] text-slate-700 uppercase">{label}</span>
    <span className={`num text-[9px] font-bold leading-none ${color}`}>{value}</span>
  </div>
);

export const ReplayControls: React.FC = () => {
  const { isStreaming, clearHistory } = useTelemetryStore();
  const history = useTelemetryStore(s => s.history);
  const lapMetrics = useTelemetryStore(s => s.lapMetrics);
  const [simType, setSimType] = useState('F1-25');

  const startStreaming = async () => {
    try {
      await fetch(`http://localhost:8000/api/streaming/start?sim_type=${simType}`, { method: 'POST' });
    } catch {}
  };

  const stopStreaming = async () => {
    try {
      await fetch('http://localhost:8000/api/streaming/stop', { method: 'POST' });
    } catch {}
    clearHistory();
  };

  const frameCount = history.length;
  const progress = lapMetrics.progress !== null ? `${(lapMetrics.progress * 100).toFixed(1)}%` : 'N/A';

  return (
    <div className="flex items-center gap-3 h-full w-full min-w-0">
      <div
        className="flex items-center gap-2 px-3 h-8 rounded-sm"
        style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)' }}
      >
        <span className="num text-[7px] text-slate-700 uppercase">SRC</span>
        <select
          value={simType}
          onChange={e => setSimType(e.target.value)}
          className="bg-transparent num text-[9px] text-slate-400 focus:outline-none cursor-pointer uppercase font-bold"
          style={{ WebkitAppearance: 'none' }}
        >
          <option value="F1-25" style={{ background: '#0c0c16' }}>F1-25 UDP</option>
          <option value="AC1" style={{ background: '#0c0c16' }}>AC SHARED MEM</option>
          <option value="IRACING" style={{ background: '#0c0c16' }}>IRACING SDK</option>
        </select>
      </div>

      {isStreaming ? (
        <button
          onClick={stopStreaming}
          className="flex items-center gap-2 px-3 h-8 rounded-sm transition-all hover:opacity-80"
          style={{ background: 'rgba(251,113,133,0.08)', border: '1px solid rgba(251,113,133,0.2)' }}
        >
          <div className="w-2 h-2 rounded-sm" style={{ background: '#fb7185' }} />
          <span className="num text-[9px] text-rose-400 font-bold uppercase tracking-wide">Stop Session</span>
        </button>
      ) : (
        <button
          onClick={startStreaming}
          className="flex items-center gap-2 px-3 h-8 rounded-sm transition-all hover:opacity-80"
          style={{ background: 'rgba(52,211,153,0.07)', border: '1px solid rgba(52,211,153,0.2)' }}
        >
          <div
            className="w-0 h-0"
            style={{ borderStyle: 'solid', borderWidth: '4px 0 4px 8px', borderColor: 'transparent transparent transparent #34d399' }}
          />
          <span className="num text-[9px] text-emerald-400 font-bold uppercase tracking-wide">Start Session</span>
        </button>
      )}

      <div style={{ width: 1, height: 24, background: 'rgba(255,255,255,0.06)', flexShrink: 0 }} />

      <div className="flex items-center gap-5 min-w-0" style={{ flex: 1 }}>
        <Stat label="Lap Time" value={formatLapTime(lapMetrics.currentLapTime)} color="text-white" />
        <Stat label="Delta" value={formatDelta(lapMetrics.delta)} color={deltaTone(lapMetrics.delta)} />
        <Stat label="Lap Delta" value={formatDelta(lapMetrics.lapDelta)} color={deltaTone(lapMetrics.lapDelta)} />
        <Stat label="Lap" value={String(lapMetrics.currentLapNumber ?? '--')} />
        <Stat label="Ref Lap" value={lapMetrics.hasPreviousLap ? String(lapMetrics.previousLapNumber ?? '--') : 'None'} />
        <Stat label="Progress" value={progress} />
        <Stat label="Frames" value={frameCount.toLocaleString()} />
      </div>

      <div className="flex items-center gap-1.5" style={{ flexShrink: 0 }}>
        <div className={`w-1.5 h-1.5 rounded-full ${isStreaming ? 'bg-emerald-400 status-live' : 'bg-slate-800'}`} />
        <span className={`num text-[8px] font-bold uppercase tracking-wide ${isStreaming ? 'text-emerald-400' : 'text-slate-700'}`}>
          {isStreaming ? 'LIVE' : 'STANDBY'}
        </span>
      </div>

      <button
        onClick={() => clearHistory()}
        className="num text-[7px] text-slate-700 hover:text-slate-500 uppercase tracking-wider transition-colors"
        style={{ flexShrink: 0 }}
      >
        CLR
      </button>
    </div>
  );
};
