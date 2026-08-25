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

const finiteNumber = (value: unknown, fallback = 0): number => {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
};

const boundedSeverity = (value: unknown): number => Math.max(0, Math.min(1, finiteNumber(value)));

/**
 * A real number, or null.
 *
 * `Number.isFinite(Number(x))` is not enough on its own: `Number(null)` and
 * `Number('')` are both 0, so a missing value would render as a confident
 * `0.00s` target. Anything the driver reads as a time has to come through here.
 */
const finiteOrNull = (value: unknown): number | null => {
  if (value === null || value === undefined || value === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};

function getEventMeta(type: unknown) {
  const key = typeof type === 'string' && type.trim() ? type.trim() : 'unknown_event';
  return EVENT_META[key] ?? { label: key.replace(/_/g, ' ').toUpperCase(), color: 'text-slate-400', dot: '#64748b' };
}

/** The microsector events carry `microsector`; nothing else the feed shows does. */
export function microsectorEvidence(event: Partial<CoachingEvent>): Record<string, unknown> | null {
  const e = event.evidence;
  if (!e || typeof e !== 'object' || Array.isArray(e)) return null;
  const evidence = e as Record<string, unknown>;
  return finiteOrNull(evidence.microsector) === null ? null : evidence;
}

export function renderEvidence(event: Partial<CoachingEvent>): string {
  const e = event.evidence;
  if (!e) return 'Physical anomaly detected.';
  if (typeof e === 'string') return e;
  const evidence = typeof e === 'object' && !Array.isArray(e) ? e as Record<string, unknown> : {};
  const eventName = typeof event.event === 'string' ? event.event : 'unknown_event';

  // The driving coach's own events. Two targets side by side: his own best
  // through this slice, and the optimised line when the track has one. Dumping
  // the raw JSON here was unreadable, and the second target made it worse.
  const microsector = microsectorEvidence(event);
  if (microsector) {
    const parts = [`VOCE ${finiteNumber(microsector.yourSeconds).toFixed(2)}s`];
    parts.push(`MELHOR ${finiteNumber(microsector.bestSeconds).toFixed(2)}s`);
    const optimal = finiteOrNull(microsector.optimalSeconds);
    if (optimal !== null) {
      parts.push(`OTIMO ${optimal.toFixed(2)}s`);
    }
    return parts.join('   ');
  }

  if (eventName === 'late_brake' || eventName === 'early_brake') {
    return `BRAKE_DELTA: ${finiteNumber(evidence.delta_m).toFixed(1)}m  REF_S: ${finiteNumber(evidence.ref_s).toFixed(0)}m`;
  }
  if (eventName === 'throttle_hesitation') {
    return `TPS: ${(finiteNumber(evidence.curr_throttle) * 100).toFixed(0)}% @ APEX_EXIT`;
  }
  if (eventName === 'poor_apex') {
    return `APEX_OFFSET: ${finiteNumber(evidence.l_offset).toFixed(2)}m  CORNER_T${finiteNumber(evidence.corner_id).toFixed(0)}`;
  }
  return Object.keys(evidence).length ? JSON.stringify(evidence).slice(0, 60) : 'Physical anomaly detected.';
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
          <span className="num text-[11px] font-bold text-slate-400 uppercase tracking-widest">AI Coaching</span>
        </div>
        <span className="num text-[10px] text-slate-700">{events.length} EVENTS</span>
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
                <span className="text-[12px] text-slate-200 leading-snug">{s.message}</span>
                <span className="num text-[10px] text-slate-600 uppercase">{s.category ?? 'strategy'} // {s.priority}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Events list */}
      <div className="flex-1 overflow-y-auto px-2 py-1.5 flex flex-col gap-1">
        {events.length === 0 ? (
          <div className="flex-1 flex items-center justify-center">
            <span className="num text-[11px] text-slate-800 uppercase tracking-wider">Awaiting events...</span>
          </div>
        ) : (
          events.slice(0, 20).map((ev, i) => {
            const eventName = typeof ev.event === 'string' ? ev.event : 'unknown_event';
            const severity = boundedSeverity(ev.severity);
            const distance = finiteNumber(ev.s);
            const timestamp = finiteNumber(ev.timestamp, Date.now());
            const microsector = microsectorEvidence(ev);
            // A whole Portuguese sentence uppercased made a useless label; the
            // slice number is what the driver needs to place the loss.
            const meta = microsector
              ? {
                  label: `SETOR ${finiteNumber(microsector.microsector).toFixed(0)}`,
                  color: 'text-cyan-400',
                  dot: '#22d3ee',
                }
              : getEventMeta(eventName);
            return (
              <div
                key={`${timestamp}-${i}`}
                className="flex flex-col gap-1 px-2 py-1.5 rounded-sm transition-all cursor-pointer hover:opacity-90"
                style={{
                  background: i === 0 ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.02)',
                  border: `1px solid rgba(255,255,255,${severity > 0.8 ? 0.08 : 0.04})`,
                  opacity: Math.max(0.35, 1 - i * 0.08)
                }}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <div className="w-1.5 h-1.5 rounded-full" style={{ background: meta.dot }} />
                    <span className={`num text-[11px] font-bold uppercase ${meta.color}`}>{meta.label}</span>
                  </div>
                  <span className="num text-[10px] text-slate-700">S:{distance.toFixed(0)}m</span>
                </div>

                <div className="num text-[10px] text-slate-600 pl-3 leading-snug">
                  {renderEvidence(ev)}
                </div>

                {/* Severity bar */}
                <div className="h-[2px] rounded-full mx-3 mt-0.5" style={{ background: 'rgba(255,255,255,0.06)' }}>
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${severity * 100}%`,
                      background: severity > 0.8 ? '#fb7185' : severity > 0.5 ? '#fbbf24' : '#60a5fa',
                      boxShadow: severity > 0.8 ? '0 0 6px rgba(251,113,133,0.5)' : 'none'
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
