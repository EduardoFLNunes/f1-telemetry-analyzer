import React from 'react';
import { mirrorMode } from '../map/renderTransform.js';

export function ProjectionDebugOverlay({ frame, renderOptions = {} }) {
  if (!frame) return null;

  return (
    <div className="panel absolute bottom-3 left-3 px-2 py-1.5" style={{ minWidth: 226 }}>
      <div className="label" style={{ color: '#38bdf8', marginBottom: 4 }}>Projection</div>
      <div className="num text-[8px] text-slate-400">s {Number(frame.s || 0).toFixed(2)} m</div>
      <div className="num text-[8px] text-slate-400">L {Number.isFinite(frame.L) ? Number(frame.L).toFixed(2) : 'pending'} m</div>
      <div className="num text-[8px] text-slate-400">drift {Number.isFinite(frame.alignment_drift) ? Number(frame.alignment_drift).toFixed(3) : 'pending'} m</div>
      <div className="num text-[8px] text-slate-400">segment {frame.projectionDebug?.nearestSegmentIndex ?? '-'}</div>
      <div className="num text-[8px] text-slate-500">mirrorMode {mirrorMode(renderOptions)}</div>
    </div>
  );
}
