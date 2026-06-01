/**
 * Session Debrief Panel — Post-session performance intelligence
 */
import React, { useMemo } from 'react';
import { CoachingEvent, TelemetryFrame, useTelemetryStore } from '../store/useTelemetryStore';
import { useRenderCounter } from '../hooks/useRenderCounter';

const EMPTY_HISTORY: TelemetryFrame[] = [];
const EMPTY_EVENTS: CoachingEvent[] = [];

const StatRow = ({ label, value, sub, color = 'text-slate-300' }: any) => (
  <div className="flex items-center justify-between py-1.5" style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
    <span className="num text-[8px] text-slate-600 uppercase tracking-wider">{label}</span>
    <div className="flex flex-col items-end">
      <span className={`num text-[10px] font-bold ${color}`}>{value}</span>
      {sub && <span className="num text-[7px] text-slate-700">{sub}</span>}
    </div>
  </div>
);

const ScoreBar = ({ label, value, color }: { label: string; value: number; color: string }) => (
  <div className="flex flex-col gap-1">
    <div className="flex justify-between items-center">
      <span className="num text-[7px] text-slate-600 uppercase">{label}</span>
      <span className="num text-[8px] font-bold text-slate-400">{(value * 100).toFixed(0)}</span>
    </div>
    <div className="h-[3px] rounded-full" style={{ background: 'rgba(255,255,255,0.06)' }}>
      <div className="h-full rounded-full transition-all duration-500"
        style={{ width: `${value * 100}%`, background: color }} />
    </div>
  </div>
);

export const AIDebriefPanel = React.memo(function AIDebriefPanel({ active = true }: { active?: boolean }) {
  useRenderCounter('AIDebriefPanel');
  const history = useTelemetryStore(s => active ? s.history : EMPTY_HISTORY);
  const events  = useTelemetryStore(s => active ? s.coachingEvents : EMPTY_EVENTS);
  const cognitive = useTelemetryStore(s => active ? s.cognitiveState : null);

  const metrics = useMemo(() => {
    if (!active || history.length < 10) return null;
    const speeds = history.map(f => f.speed * 3.6);
    const avgSpeed = speeds.reduce((a, b) => a + b, 0) / speeds.length;
    const maxSpeed = Math.max(...speeds);
    const avgThrottle = history.reduce((a, f) => a + f.throttle, 0) / history.length;
    const avgBrake    = history.reduce((a, f) => a + f.brake, 0) / history.length;
    const severe = events.filter(e => e.severity > 0.8).length;
    return { avgSpeed, maxSpeed, avgThrottle, avgBrake, mistakes: events.length, severe };
  }, [active, history, events]);

  if (!metrics) {
    return (
      <div className="panel flex flex-col h-full items-center justify-center gap-3">
        <div className="w-10 h-10 rounded-full border border-slate-800 flex items-center justify-center opacity-30">
          <span className="num text-[9px] text-slate-600">DBF</span>
        </div>
        <span className="num text-[8px] text-slate-700 uppercase tracking-wider text-center">
          Awaiting session<br />completion...
        </span>
      </div>
    );
  }

  return (
    <div className="panel flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 shrink-0"
        style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
        <div style={{ width: 3, height: 16, background: '#34d399', borderRadius: 2 }} />
        <span className="num text-[8px] font-bold text-slate-300 uppercase tracking-widest">Session Debrief</span>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-2 flex flex-col gap-3">
        {/* Core metrics */}
        <div>
          <span className="label block mb-1" style={{ fontSize: 6 }}>PERFORMANCE METRICS</span>
          <StatRow label="Avg Speed" value={`${metrics.avgSpeed.toFixed(1)} km/h`} color="text-cyan-400" />
          <StatRow label="Max Speed" value={`${metrics.maxSpeed.toFixed(0)} km/h`} color="text-white" />
          <StatRow label="Throttle Avg" value={`${(metrics.avgThrottle * 100).toFixed(1)}%`} color="text-emerald-400" />
          <StatRow label="Brake Avg" value={`${(metrics.avgBrake * 100).toFixed(1)}%`} color="text-rose-400" />
          <StatRow
            label="Events"
            value={`${metrics.mistakes} total`}
            sub={`${metrics.severe} critical`}
            color={metrics.severe > 3 ? 'text-rose-400' : 'text-amber-400'}
          />
        </div>

        {/* Driving scores */}
        {cognitive && (
          <div>
            <span className="label block mb-2" style={{ fontSize: 6 }}>DRIVER COGNITIVE ARRAY</span>
            <div className="flex flex-col gap-2">
              <ScoreBar label="Confidence" value={cognitive.metrics.confidence} color="#22d3ee" />
              <ScoreBar label="Smoothness" value={cognitive.metrics.smoothness} color="#34d399" />
              <ScoreBar label="Aggression" value={cognitive.metrics.aggression} color="#fb923c" />
              <ScoreBar label="Consistency" value={cognitive.metrics.consistency} color="#a78bfa" />
            </div>
            <div className="mt-2 px-2 py-1.5 rounded-sm"
              style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <span className="num text-[8px] font-bold text-slate-300 uppercase">{cognitive.state}</span>
            </div>
          </div>
        )}

        {/* Recommendations */}
        <div>
          <span className="label block mb-2" style={{ fontSize: 6 }}>AI RECOMMENDATIONS</span>
          <div className="flex flex-col gap-1.5">
            {[
              { icon: '⟩', color: '#22d3ee', text: 'Focus on corner exit speed — consistent throttle application point needed.' },
              { icon: '⟩', color: '#fbbf24', text: 'Brake variability detected. Single reference point per braking zone.' },
              { icon: '⟩', color: '#a78bfa', text: 'Understeer signature in medium-speed corners. Evaluate front setup.' },
            ].map((r, i) => (
              <div key={i} className="flex gap-2 items-start text-[9px] px-2 py-1.5 rounded-sm leading-relaxed"
                style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)' }}>
                <span style={{ color: r.color, fontSize: 10, lineHeight: 1.2 }}>{r.icon}</span>
                <span className="text-slate-400 font-sans">{r.text}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
});
