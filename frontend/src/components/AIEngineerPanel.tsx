/**
 * AI Race Engineer Panel — Neural-linked coaching console
 */
import React from 'react';
import { useTelemetryStore } from '../store/useTelemetryStore';

export const AIEngineerPanel: React.FC = () => {
  const speech = useTelemetryStore(s => s.engineerSpeech);
  const isStreaming = useTelemetryStore(s => s.isStreaming);

  const priorityStyle = (p: string) => {
    if (p === 'high')   return { bg: 'rgba(251,113,133,0.08)', border: 'rgba(251,113,133,0.2)',  text: '#fb7185' };
    if (p === 'medium') return { bg: 'rgba(251,191,36,0.06)',  border: 'rgba(251,191,36,0.2)',   text: '#fbbf24' };
    return                     { bg: 'rgba(34,211,238,0.05)',  border: 'rgba(34,211,238,0.15)',  text: '#22d3ee' };
  };

  return (
    <div className="panel flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 shrink-0"
        style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
        <div className="flex items-center gap-2">
          <div style={{ width: 3, height: 16, background: '#22d3ee', borderRadius: 2 }} />
          <span className="num text-[8px] font-bold text-slate-300 uppercase tracking-widest">AI Race Engineer</span>
        </div>
        <div className="flex items-center gap-1.5">
          {isStreaming && (
            <div className="flex items-center gap-1">
              <div className="w-1 h-1 rounded-full bg-emerald-400 status-live" />
              <span className="num text-[7px] text-emerald-400 uppercase">Active</span>
            </div>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-2 py-2 flex flex-col gap-2">
        {speech.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-2 opacity-30">
            <div className="w-8 h-8 rounded-full border border-slate-700 flex items-center justify-center">
              <span className="num text-[10px] text-slate-600">AI</span>
            </div>
            <span className="num text-[8px] text-slate-700 uppercase tracking-wider text-center leading-relaxed">
              Awaiting driver<br />feedback sequences
            </span>
          </div>
        ) : (
          speech.map((msg, i) => {
            const s = priorityStyle(msg.priority);
            return (
              <div
                key={`${msg.timestamp}-${i}`}
                className="flex flex-col gap-1.5 rounded-sm px-2 py-2 slide-in"
                style={{
                  background: s.bg,
                  border: `1px solid ${s.border}`,
                  opacity: i === 0 ? 1 : Math.max(0.25, 1 - i * 0.18)
                }}
              >
                <div className="flex items-center justify-between">
                  <span className="num text-[7px] font-bold uppercase tracking-wider" style={{ color: s.text }}>
                    {msg.priority}
                  </span>
                  <span className="num text-[7px] text-slate-700">
                    {new Date((msg.timestamp ?? 0) * 1000).toLocaleTimeString('en', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>
                </div>
                <p className="text-[10px] text-slate-200 leading-relaxed font-sans font-medium">
                  {msg.message}
                </p>
                {msg.category && (
                  <span className="num text-[6px] text-slate-700 uppercase tracking-widest">{msg.category}</span>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Footer */}
      <div className="px-3 py-1.5 shrink-0 flex items-center gap-2"
        style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
        <div className="w-1 h-1 rounded-full bg-blue-400 blink" />
        <span className="num text-[7px] text-slate-700 uppercase tracking-wider">Neural-linked coaching // Priority enabled</span>
      </div>
    </div>
  );
};
