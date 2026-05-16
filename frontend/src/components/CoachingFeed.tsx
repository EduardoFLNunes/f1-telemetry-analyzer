/**
 * AI Coaching Feed — Real-time physics-based event analysis
 * Phase 9: Tactical coaching intelligence with severity visualization.
 */
import React from 'react';
import { useTelemetryStore, CoachingEvent, EngineerSpeech } from '../store/useTelemetryStore';

const EVENT_META: Record<string, { label: string; color: string; dot: string }> = {
  late_brake:           { label: 'LATE BRAKE',      color: 'text-rose-400',    dot: '#fb7185' },
  early_brake:          { label: 'EARLY BRAKE',     color: 'text-amber-400',   dot: '#fbbf24' },
  throttle_hesitation:  { label: 'THROTTLE HESIT',  color: 'text-orange-400',  dot: '#fb923c' },
  poor_apex:            { label: 'APEX MISS',        color: 'text-violet-400',  dot: '#a78bfa' },
  oversteer:            { label: 'OVERSTEER',        color: 'text-rose-500',    dot: '#f43f5e' },
  understeer:           { label: 'UNDERSTEER',       color: 'text-blue-400',    dot: '#60a5fa' },
  lockup:               { label: 'LOCKUP',           color: 'text-red-400',     dot: '#ef4444' },
  predictive_warning:   { label: 'PREDICTIVE WARN',  color: 'text-amber-300',   dot: '#fcd34d' },
};

function getEventMeta(type: string) {
  return EVENT_META[type] ?? { label: type.replace(/_/g, ' ').toUpperCase(), color: 'text-slate-400', dot: '#64748b' };
}

function renderEvidence(event: CoachingEvent): string {
  const e = event.evidence;
  if (!e) return 'Physical anomaly detected.';
  if (event.event === 'late_brake' || event.event === 'early_brake') {
    return `BRAKE_DELTA: ${(e.delta_m ?? 0).toFixed(1)}m  REF_S: ${(e.ref_s ?? 0).toFixed(0)}m`;
  }
  if (event.event === 'throttle_hesitation') {
    return `TPS: ${((e.curr_throttle ?? 0) * 100).toFixed(0)}% @ APEX_EXIT`;
  }
  if (event.event === 'poor_apex') {
    return `APEX_OFFSET: ${(e.l_offset ?? 0).toFixed(2)}m  CORNER_T${e.corner_id ?? 0}`;
  }
  return typeof e === 'string' ? e : JSON.stringify(e).slice(0, 60);
}

export const CoachingFeed: React.FC = () => {
  const events = useTelemetryStore(s => s.coachingEvents);
  const speech = useTelemetryStore(s => s.engineerSpeech);

  return (
    <div className="panel flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-1.5 shrink-0"
        style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-rose-400 status-live" />
          <span className="num text-[8px] font-bold text-slate-400 uppercase tracking-widest">AI Coaching</span>
        </div>
        <span className="num text-[7px] text-slate-700">{events.length} EVENTS</span>
      </div>

      {/* Engineer speech */}
      {speech.length > 0 && (
        <div className="px-2 pt-2 pb-1 shrink-0 flex flex-col gap-1.5"
          style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
          {speech.slice(0, 2).map((s, i) => (
            <div key={i} className="flex gap-2 items-start px-2 py-1.5 rounded"
              style={{ background: 'rgba(34,211,238,0.04)', border: '1px solid rgba(34,211,238,0.1)' }}>
              <div style={{ width: 3, alignSelf: 'stretch', background: '#22d3ee', borderRadius: 2, opacity: i === 0 ? 1 : 0.3 }} />
              <div className="flex flex-col gap-0.5 flex-1">
                <span className="text-[9px] text-slate-200 leading-snug">{s.message}</span>
                <span className="num text-[7px] text-slate-600 uppercase">{s.category ?? 'strategy'} // {s.priority}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Events list */}
      <div className="flex-1 overflow-y-auto px-2 py-1.5 flex flex-col gap-1">
        {events.length === 0 ? (
          <div className="flex-1 flex items-center justify-center">
            <span className="num text-[8px] text-slate-800 uppercase tracking-wider">Awaiting events...</span>
          </div>
        ) : (
          events.slice(0, 20).map((ev, i) => {
            const meta = getEventMeta(ev.event);
            return (
              <div
                key={`${ev.timestamp}-${i}`}
                className="flex flex-col gap-1 px-2 py-1.5 rounded-sm transition-all cursor-pointer hover:opacity-90"
                style={{
                  background: i === 0 ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.02)',
                  border: `1px solid rgba(255,255,255,${ev.severity > 0.8 ? 0.08 : 0.04})`,
                  opacity: Math.max(0.35, 1 - i * 0.08)
                }}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <div className="w-1.5 h-1.5 rounded-full" style={{ background: meta.dot }} />
                    <span className={`num text-[8px] font-bold uppercase ${meta.color}`}>{meta.label}</span>
                  </div>
                  <span className="num text-[7px] text-slate-700">S:{ev.s.toFixed(0)}m</span>
                </div>

                <div className="num text-[7px] text-slate-600 pl-3 leading-snug">
                  {renderEvidence(ev)}
                </div>

                {/* Severity bar */}
                <div className="h-[2px] rounded-full mx-3 mt-0.5" style={{ background: 'rgba(255,255,255,0.06)' }}>
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${ev.severity * 100}%`,
                      background: ev.severity > 0.8 ? '#fb7185' : ev.severity > 0.5 ? '#fbbf24' : '#60a5fa',
                      boxShadow: ev.severity > 0.8 ? '0 0 6px rgba(251,113,133,0.5)' : 'none'
                    }}
                  />
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
