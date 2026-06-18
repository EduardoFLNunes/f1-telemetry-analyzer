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
  const offlineReplay = useTelemetryStore(s => s.offlineReplay);
  const setOfflineReplayIndex = useTelemetryStore(s => s.setOfflineReplayIndex);
  const setOfflineReplayTime = useTelemetryStore(s => s.setOfflineReplayTime);
  const setOfflineReplayPlaying = useTelemetryStore(s => s.setOfflineReplayPlaying);
  const setOfflineReplayPlaybackRate = useTelemetryStore(s => s.setOfflineReplayPlaybackRate);
  const clearOfflineReplay = useTelemetryStore(s => s.clearOfflineReplay);
  const [simType, setSimType] = useState('F1-25');

  const startStreaming = async () => {
    clearOfflineReplay();
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
  const replaySample = offlineReplay.currentSample;
  const replaySpeed = replaySample?.speedKmh ?? (replaySample?.speed !== undefined ? replaySample.speed * 3.6 : null);
  const replayProgress = lapMetrics.progress !== null ? `${(lapMetrics.progress * 100).toFixed(1)}%` : '--';
  const handleReplayScrub = (value: string) => {
    setOfflineReplayTime(Number(value));
  };

  if (offlineReplay.active) {
    return (
      <div className="flex items-center gap-3 h-full w-full min-w-0">
        <div
          className="flex items-center gap-2 px-3 h-8 rounded-sm"
          style={{ background: 'rgba(250,204,21,0.07)', border: '1px solid rgba(250,204,21,0.22)' }}
        >
          <span className="num text-[7px] text-yellow-200 uppercase">Replay offline</span>
          <span className="num text-[8px] text-slate-400">L{offlineReplay.lapNumber ?? '--'}</span>
          <span className="num text-[7px] text-slate-600">Fonte: persisted lap</span>
        </div>

        <button
          type="button"
          onClick={() => setOfflineReplayIndex(0)}
          className="num text-[7px] uppercase rounded-sm transition-all"
          style={{
            height: 24,
            minWidth: 38,
            border: '1px solid rgba(255,255,255,0.06)',
            background: 'rgba(255,255,255,0.02)',
            color: '#94a3b8',
            cursor: 'pointer',
          }}
          title="Voltar ao inicio do replay"
        >
          START
        </button>

        <button
          type="button"
          onClick={() => setOfflineReplayPlaying(!offlineReplay.playing)}
          className="flex items-center gap-2 px-3 h-8 rounded-sm transition-all hover:opacity-80"
          style={{ background: 'rgba(250,204,21,0.08)', border: '1px solid rgba(250,204,21,0.25)' }}
        >
          <span className="num text-[9px] text-yellow-200 font-bold uppercase tracking-wide">
            {offlineReplay.playing ? 'Pause' : 'Play'}
          </span>
        </button>

        <div className="flex items-center gap-1" style={{ flexShrink: 0 }}>
          {[0.5, 1, 2].map((rate) => (
            <button
              key={rate}
              type="button"
              onClick={() => setOfflineReplayPlaybackRate(rate)}
              className="num text-[7px] uppercase rounded-sm"
              style={{
                height: 24,
                minWidth: 34,
                border: offlineReplay.playbackRate === rate ? '1px solid rgba(250,204,21,0.42)' : '1px solid rgba(255,255,255,0.06)',
                background: offlineReplay.playbackRate === rate ? 'rgba(250,204,21,0.12)' : 'rgba(255,255,255,0.02)',
                color: offlineReplay.playbackRate === rate ? '#fde68a' : '#64748b',
                cursor: 'pointer',
              }}
            >
              {rate}x
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 min-w-0" style={{ flex: 1 }}>
          <span className="num text-[8px] text-slate-500" style={{ minWidth: 54 }}>{formatLapTime(offlineReplay.currentTime)}</span>
          <input
            type="range"
            min={0}
            max={Math.max(offlineReplay.duration, 0.01)}
            step={0.01}
            value={Math.min(offlineReplay.currentTime, Math.max(offlineReplay.duration, 0.01))}
            onInput={(event) => handleReplayScrub(event.currentTarget.value)}
            onChange={(event) => handleReplayScrub(event.target.value)}
            style={{ width: '100%' }}
            aria-label="Offline replay timeline"
          />
          <span className="num text-[8px] text-slate-500" style={{ minWidth: 54, textAlign: 'right' }}>{formatLapTime(offlineReplay.duration)}</span>
        </div>

        <button
          type="button"
          onClick={() => setOfflineReplayTime(offlineReplay.duration)}
          className="num text-[7px] uppercase rounded-sm transition-all"
          style={{
            height: 24,
            minWidth: 34,
            border: '1px solid rgba(255,255,255,0.06)',
            background: 'rgba(255,255,255,0.02)',
            color: '#94a3b8',
            cursor: 'pointer',
          }}
          title="Ir para o fim do replay"
        >
          END
        </button>

        <div className="flex items-center gap-4 min-w-0" style={{ flexShrink: 0 }}>
          <Stat label="Speed" value={replaySpeed === null || replaySpeed === undefined ? '--' : `${replaySpeed.toFixed(0)} km/h`} color="text-white" />
          <Stat label="Throttle" value={`${((replaySample?.throttle ?? 0) * 100).toFixed(0)}%`} color="text-emerald-300" />
          <Stat label="Brake" value={`${((replaySample?.brake ?? 0) * 100).toFixed(0)}%`} color="text-rose-300" />
          <Stat label="Gear/RPM" value={`${replaySample?.gear ?? '--'} / ${replaySample?.rpm ?? '--'}`} />
          <Stat label="Progress" value={replayProgress} />
        </div>

        <button
          type="button"
          onClick={clearOfflineReplay}
          className="num text-[7px] text-slate-600 hover:text-yellow-200 uppercase tracking-wider transition-colors"
          style={{ flexShrink: 0 }}
        >
          EXIT
        </button>
      </div>
    );
  }

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
