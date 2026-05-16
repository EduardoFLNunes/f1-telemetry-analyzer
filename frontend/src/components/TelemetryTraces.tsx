/**
 * Professional Multi-Channel Telemetry Traces
 * Phase 6: Synchronized multi-trace viewer with event markers and cursor.
 */
import React, { useRef, useEffect, useCallback } from 'react';
import { useTelemetryStore } from '../store/useTelemetryStore';

interface TraceConfig {
  id: string;
  label: string;
  color: string;
  fillColor?: string;
  min: number;
  max: number;
  unit: string;
  heightRatio: number;
  getValue: (f: any) => number;
  zeroLine?: boolean;
  ribbonFill?: boolean;
}

const TRACES: TraceConfig[] = [
  {
    id: 'speed', label: 'SPD', color: '#22d3ee', fillColor: 'rgba(34,211,238,0.06)',
    min: 0, max: 350, unit: 'km/h', heightRatio: 0.28,
    getValue: f => f.speed * 3.6,
  },
  {
    id: 'throttle', label: 'TPS', color: '#34d399', fillColor: 'rgba(52,211,153,0.08)',
    min: 0, max: 1, unit: '%', heightRatio: 0.12,
    getValue: f => f.throttle,
  },
  {
    id: 'brake', label: 'BRK', color: '#fb7185', fillColor: 'rgba(251,113,133,0.08)',
    min: 0, max: 1, unit: '%', heightRatio: 0.12,
    getValue: f => f.brake,
  },
  {
    id: 'steering', label: 'STR', color: '#fbbf24',
    min: -1, max: 1, unit: 'norm', heightRatio: 0.10,
    getValue: f => f.steering, zeroLine: true,
  },
  {
    id: 'latg', label: 'LAT_G', color: '#f472b6',
    min: -4, max: 4, unit: 'G', heightRatio: 0.12,
    getValue: f => f.accel_g?.x ?? 0, zeroLine: true,
  },
  {
    id: 'delta', label: 'Δ', color: '#a78bfa', fillColor: undefined,
    min: -1, max: 1, unit: 's', heightRatio: 0.10,
    getValue: f => f.delta, zeroLine: true, ribbonFill: true,
  },
  {
    id: 'rpm', label: 'RPM', color: '#94a3b8',
    min: 0, max: 15000, unit: 'rpm', heightRatio: 0.10,
    getValue: f => (f as any).rpm ?? 0,
  },
];

const PAD_LEFT   = 34;
const PAD_RIGHT  = 6;
const PAD_TOP    = 4;
const PAD_BOTTOM = 4;
const GAP        = 3;

export const TelemetryTraces: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef    = useRef<HTMLCanvasElement>(null);
  const animRef      = useRef<number>();

  /* ── Persistent RAF render loop ──────────────────────────────── */
  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const loop = () => {
      const { history, globalCursorS } = useTelemetryStore.getState();

      const dpr  = window.devicePixelRatio || 1;
      const rect = container.getBoundingClientRect();
      const W = rect.width, H = rect.height;

      if (canvas.width !== W * dpr || canvas.height !== H * dpr) {
        canvas.width  = W * dpr;
        canvas.height = H * dpr;
        ctx.scale(dpr, dpr);
      }

      ctx.clearRect(0, 0, W, H);

      if (history.length < 2) {
        ctx.fillStyle = 'rgba(255,255,255,0.03)';
        ctx.font = 'bold 9px "JetBrains Mono"';
        ctx.textAlign = 'center';
        ctx.fillStyle = 'rgba(255,255,255,0.08)';
        ctx.fillText('WAITING FOR TELEMETRY DATA', W / 2, H / 2);
        animRef.current = requestAnimationFrame(loop);
        return;
      }

      const minS = history[0].s;
      const maxS = history[history.length - 1].s;
      const sRange = maxS - minS || 1;

      const graphW = W - PAD_LEFT - PAD_RIGHT;
      const totalH = H - PAD_TOP - PAD_BOTTOM;
      const totalRatio = TRACES.reduce((s, t) => s + t.heightRatio, 0);
      const gapTotal = (TRACES.length - 1) * GAP;
      const availH = totalH - gapTotal;

      let currentY = PAD_TOP;

      const sToX = (s: number) => PAD_LEFT + ((s - minS) / sRange) * graphW;

      TRACES.forEach((trace, ti) => {
        const th = (trace.heightRatio / totalRatio) * availH;
        const baseline = currentY + th;

        const valToY = (v: number) =>
          baseline - ((v - trace.min) / (trace.max - trace.min)) * th;

        // Track boundary (subtle)
        ctx.fillStyle = 'rgba(255,255,255,0.02)';
        ctx.fillRect(PAD_LEFT, currentY, graphW, th);

        // Border top
        ctx.fillStyle = 'rgba(255,255,255,0.05)';
        ctx.fillRect(PAD_LEFT, currentY, graphW, 1);

        // Zero line
        if (trace.zeroLine) {
          const zy = valToY(0);
          ctx.setLineDash([3, 6]);
          ctx.strokeStyle = 'rgba(255,255,255,0.07)';
          ctx.lineWidth = 0.8;
          ctx.beginPath(); ctx.moveTo(PAD_LEFT, zy); ctx.lineTo(PAD_LEFT + graphW, zy); ctx.stroke();
          ctx.setLineDash([]);
        }

        // Label + last-value
        const lastFrame = history[history.length - 1];
        const lastVal = trace.getValue(lastFrame);
        ctx.fillStyle = trace.color;
        ctx.font = `bold 6.5px "JetBrains Mono"`;
        ctx.textAlign = 'right';
        ctx.fillText(trace.label, PAD_LEFT - 4, currentY + 8);
        ctx.fillStyle = 'rgba(255,255,255,0.5)';
        ctx.font = `500 6px "JetBrains Mono"`;
        ctx.fillText(lastVal.toFixed(trace.id === 'speed' || trace.id === 'rpm' ? 0 : 2), PAD_LEFT - 4, baseline - 2);

        // Fill area under trace
        if (trace.fillColor && history.length > 1) {
          ctx.beginPath();
          history.forEach((f, i) => {
            const x = sToX(f.s);
            const y = valToY(trace.getValue(f));
            i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
          });
          ctx.lineTo(sToX(history[history.length - 1].s), baseline);
          ctx.lineTo(sToX(history[0].s), baseline);
          ctx.closePath();
          ctx.fillStyle = trace.fillColor;
          ctx.fill();
        }

        // Ribbon fill (delta)
        if (trace.ribbonFill) {
          const zeroY = valToY(0);
          for (let i = 1; i < history.length; i++) {
            const f1 = history[i - 1], f2 = history[i];
            const x1 = sToX(f1.s), x2 = sToX(f2.s);
            const v2 = trace.getValue(f2);
            const y1 = valToY(trace.getValue(f1)), y2 = valToY(v2);
            const color = v2 < 0 ? 'rgba(52,211,153,0.15)' : 'rgba(251,113,133,0.15)';
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.moveTo(x1, zeroY); ctx.lineTo(x1, y1);
            ctx.lineTo(x2, y2); ctx.lineTo(x2, zeroY);
            ctx.closePath(); ctx.fill();
          }
        }

        // Trace line
        ctx.beginPath();
        ctx.strokeStyle = trace.color;
        ctx.lineWidth = 1.1;
        ctx.lineJoin = 'round';
        ctx.lineCap  = 'round';
        let firstPoint = true;
        history.forEach(f => {
          const x = sToX(f.s);
          const y = valToY(Math.max(trace.min, Math.min(trace.max, trace.getValue(f))));
          if (firstPoint) { ctx.moveTo(x, y); firstPoint = false; }
          else ctx.lineTo(x, y);
        });
        ctx.stroke();

        // Event markers: lockup (brake > 0.85 + ABS), instability
        if (trace.id === 'brake') {
          history.forEach(f => {
            if (f.brake > 0.88 && f.speed * 3.6 < 5) {
              const x = sToX(f.s);
              ctx.fillStyle = '#fb7185';
              ctx.fillRect(x - 1, currentY, 2, 5);
            }
          });
        }

        // Cursor line + value tooltip
        if (globalCursorS !== null) {
          const cx = sToX(globalCursorS);
          if (cx >= PAD_LEFT && cx <= PAD_LEFT + graphW) {
            ctx.strokeStyle = 'rgba(255,255,255,0.25)';
            ctx.lineWidth = 1;
            ctx.setLineDash([2, 3]);
            ctx.beginPath(); ctx.moveTo(cx, currentY); ctx.lineTo(cx, baseline); ctx.stroke();
            ctx.setLineDash([]);

            // Dot at cursor intersection
            const nearFrame = history.reduce((prev, cur) =>
              Math.abs(cur.s - globalCursorS!) < Math.abs(prev.s - globalCursorS!) ? cur : prev);
            if (nearFrame) {
              const vy = valToY(Math.max(trace.min, Math.min(trace.max, trace.getValue(nearFrame))));
              ctx.beginPath();
              ctx.arc(cx, vy, 2.5, 0, Math.PI * 2);
              ctx.fillStyle = trace.color;
              ctx.fill();

              // Value badge
              const val = trace.getValue(nearFrame);
              const label = val.toFixed(trace.id === 'speed' || trace.id === 'rpm' ? 0 : 3);
              const textW = ctx.measureText(label).width + 6;
              const bx = Math.min(cx + 3, PAD_LEFT + graphW - textW);
              ctx.fillStyle = 'rgba(12,12,20,0.9)';
              ctx.fillRect(bx, vy - 8, textW, 10);
              ctx.fillStyle = trace.color;
              ctx.font = `bold 6px "JetBrains Mono"`;
              ctx.textAlign = 'left';
              ctx.fillText(label, bx + 3, vy);
            }
          }
        }

        // High-value markers (sector separators, etc.)
        // TODO: sector boundary lines

        currentY += th + GAP;
      });

      // Cursor S-distance label
      if (globalCursorS !== null) {
        const cx = sToX(globalCursorS);
        ctx.fillStyle = 'rgba(255,255,255,0.6)';
        ctx.font = `bold 7px "JetBrains Mono"`;
        ctx.textAlign = 'center';
        ctx.fillText(`${globalCursorS.toFixed(0)}m`, cx, H - 1);
      }

      animRef.current = requestAnimationFrame(loop);
    };

    animRef.current = requestAnimationFrame(loop);
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
  }, []);

  /* ── Cursor interaction ───────────────────────────────────────── */
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current!.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const { history } = useTelemetryStore.getState();
    if (history.length === 0) return;
    const graphW = rect.width - PAD_LEFT - PAD_RIGHT;
    if (x < PAD_LEFT || x > PAD_LEFT + graphW) return;
    const minS = history[0].s, maxS = history[history.length - 1].s;
    const s = minS + ((x - PAD_LEFT) / graphW) * (maxS - minS);
    useTelemetryStore.getState().setGlobalCursor(s);
  }, []);

  const handleMouseLeave = useCallback(() => {
    useTelemetryStore.getState().setGlobalCursor(null);
  }, []);

  return (
    <div ref={containerRef} className="w-full h-full" style={{ background: '#08080f' }}>
      <canvas
        ref={canvasRef}
        style={{ width: '100%', height: '100%', display: 'block', cursor: 'crosshair' }}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      />
    </div>
  );
};
