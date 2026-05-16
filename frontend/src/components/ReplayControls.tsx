/**
 * Replay & Session Controls — F1 pitwall-style interface
 */
import React, { useState } from 'react';
import { useTelemetryStore } from '../store/useTelemetryStore';

export const ReplayControls: React.FC = () => {
  const { isStreaming, clearHistory } = useTelemetryStore();
  const history = useTelemetryStore(s => s.history);
  const [simType, setSimType] = useState('F1-25');
  const [speed, setSpeed] = useState(1.0);

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
  const lapDist = history.length > 0 ? history[history.length - 1].s.toFixed(0) : '0';

  return (
    <div className="flex items-center gap-4 h-full w-full">

      {/* ── Source selector ── */}
      <div className="flex items-center gap-2 px-3 h-8 rounded-sm"
        style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)' }}>
        <span className="num text-[7px] text-slate-700 uppercase">SRC</span>
        <select
          value={simType}
          onChange={e => setSimType(e.target.value)}
          className="bg-transparent num text-[9px] text-slate-400 focus:outline-none cursor-pointer uppercase font-bold"
          style={{ WebkitAppearance: 'none' }}
        >
          <option value="F1-25" style={{ background: '#0c0c16' }}>F1-25 UDP</option>
          <option value="AC1"   style={{ background: '#0c0c16' }}>AC SHARED MEM</option>
          <option value="IRACING" style={{ background: '#0c0c16' }}>IRACING SDK</option>
        </select>
      </div>

      {/* ── Start / Stop ── */}
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
          <div className="w-0 h-0"
            style={{ borderStyle: 'solid', borderWidth: '4px 0 4px 8px', borderColor: 'transparent transparent transparent #34d399' }}
          />
          <span className="num text-[9px] text-emerald-400 font-bold uppercase tracking-wide">Start Session</span>
        </button>
      )}

      {/* ── Playback speed ── */}
      <div className="flex items-center gap-2 px-3 h-8 rounded-sm"
        style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)' }}>
        <button
          className="num text-[8px] text-slate-600 hover:text-slate-400 transition-colors"
          onClick={() => setSpeed(s => Math.max(0.25, +(s - 0.25).toFixed(2)))}
        >◀</button>
        <div className="flex flex-col items-center" style={{ minWidth: 32 }}>
          <span className="num text-[6px] text-slate-700 uppercase">SPEED</span>
          <span className="num text-[10px] font-bold text-cyan-400 leading-none">{speed.toFixed(2)}×</span>
        </div>
        <button
          className="num text-[8px] text-slate-600 hover:text-slate-400 transition-colors"
          onClick={() => setSpeed(s => Math.min(4, +(s + 0.25).toFixed(2)))}
        >▶</button>
      </div>

      <div style={{ width: 1, height: 20, background: 'rgba(255,255,255,0.05)' }} />

      {/* ── Session stats ── */}
      <div className="flex items-center gap-5">
        <div className="flex flex-col">
          <span className="num text-[6px] text-slate-700 uppercase">FRAMES</span>
          <span className="num text-[9px] font-bold text-slate-500">{frameCount.toLocaleString()}</span>
        </div>
        <div className="flex flex-col">
          <span className="num text-[6px] text-slate-700 uppercase">LAP_DIST</span>
          <span className="num text-[9px] font-bold text-slate-500">{lapDist}m</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className={`w-1.5 h-1.5 rounded-full ${isStreaming ? 'bg-emerald-400 status-live' : 'bg-slate-800'}`} />
          <span className={`num text-[8px] font-bold uppercase tracking-wide ${isStreaming ? 'text-emerald-400' : 'text-slate-700'}`}>
            {isStreaming ? 'LIVE INGEST' : 'STANDBY'}
          </span>
        </div>
      </div>

      {/* ── Right spacer + clear button ── */}
      <div className="ml-auto">
        <button
          onClick={() => clearHistory()}
          className="num text-[7px] text-slate-700 hover:text-slate-500 uppercase tracking-wider transition-colors"
        >
          CLR
        </button>
      </div>
    </div>
  );
};
