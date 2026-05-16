/**
 * Driver Cognitive Dashboard — Mental state visualization
 */
import React from 'react';
import { useTelemetryStore } from '../store/useTelemetryStore';

const StateColor: Record<string, string> = {
  steady:      '#22d3ee',
  pushing:     '#34d399',
  overdriving: '#fb7185',
  recovering:  '#fbbf24',
  fatigued:    '#a78bfa',
};

export const CognitiveDashboard: React.FC = () => {
  const cognitive = useTelemetryStore(s => s.cognitiveState);

  if (!cognitive) {
    return (
      <div className="panel flex flex-col h-full items-center justify-center opacity-25">
        <span className="num text-[7px] text-slate-700 uppercase tracking-wider">Cognitive Model Offline</span>
      </div>
    );
  }

  const { metrics, state } = cognitive;
  const stateColor = StateColor[state] ?? '#94a3b8';

  return (
    <div className="panel flex flex-col h-full overflow-hidden">
      <div className="flex items-center justify-between px-2 py-1.5 shrink-0"
        style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
        <span className="num text-[7px] text-slate-600 uppercase tracking-wider">Cognitive</span>
        <span className="num text-[7px] font-bold uppercase" style={{ color: stateColor }}>{state}</span>
      </div>
      <div className="flex-1 px-2 py-2 flex flex-col gap-1.5">
        {[
          ['Conf', metrics.confidence, '#22d3ee'],
          ['Aggr', metrics.aggression, '#fb923c'],
          ['Smth', metrics.smoothness, '#34d399'],
          ['Focs', metrics.focus ?? 0.85, '#a78bfa'],
        ].map(([label, value, color]) => (
          <div key={String(label)} className="flex items-center gap-2">
            <span className="num text-[6px] text-slate-700 uppercase w-6 shrink-0">{label}</span>
            <div className="flex-1 h-[3px] rounded-full" style={{ background: 'rgba(255,255,255,0.06)' }}>
              <div className="h-full rounded-full transition-all duration-300"
                style={{ width: `${Number(value) * 100}%`, background: String(color) }} />
            </div>
            <span className="num text-[7px] text-slate-600 w-5 text-right">{(Number(value) * 100).toFixed(0)}</span>
          </div>
        ))}
      </div>
    </div>
  );
};
