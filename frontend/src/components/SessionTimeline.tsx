/**
 * Session Timeline — Interactive telemetry scrubber with event markers
 * Phase 6: MoTeC-style session progress visualization.
 */
import React, { useRef, useEffect, useCallback } from 'react';
import { useTelemetryStore } from '../store/useTelemetryStore';

export const SessionTimeline: React.FC = () => {
  const canvasRef   = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const animRef     = useRef<number>();

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const loop = () => {
      const { history, globalCursorS, coachingEvents, sectors } = useTelemetryStore.getState();

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
        // Idle state: animated placeholder
        ctx.fillStyle = 'rgba(255,255,255,0.03)';
        ctx.fillRect(0, 4, W, H - 4);
        ctx.fillStyle = 'rgba(255,255,255,0.06)';
        ctx.font = `600 7px "JetBrains Mono"`;
        ctx.textAlign = 'center';
        ctx.fillText('NO TELEMETRY DATA', W / 2, H / 2 + 2);
        animRef.current = requestAnimationFrame(loop);
        return;
      }

      const minS  = history[0].s;
      const maxS  = Math.max(history[history.length - 1].s, 1);
      const sRange = maxS - minS || 1;

      const sToX = (s: number) => (s - minS) / sRange * W;

      // ── A. Delta ribbon (top strip, 4px) ───────────────────────
      const stripH = 4;
      const step = Math.max(1, Math.floor(history.length / W));
      for (let i = step; i < history.length; i += step) {
        const f = history[i];
        const x = sToX(f.s);
        const x0 = sToX(history[i - step].s);
        const color = f.delta <= 0 ? `rgba(52,211,153,0.7)` : `rgba(251,113,133,0.6)`;
        ctx.fillStyle = color;
        ctx.fillRect(x0, 0, Math.max(1, x - x0), stripH);
      }

      // ── B. Speed trace (mini sparkline) ────────────────────────
      const traceTop = stripH + 2, traceH = H - stripH - 2 - 6;
      const maxSpeed = Math.max(...history.map(f => f.speed * 3.6), 1);

      ctx.fillStyle = 'rgba(255,255,255,0.02)';
      ctx.fillRect(0, traceTop, W, traceH);

      // Fill gradient
      const grad = ctx.createLinearGradient(0, traceTop, 0, traceTop + traceH);
      grad.addColorStop(0, 'rgba(34,211,238,0.15)');
      grad.addColorStop(1, 'rgba(34,211,238,0)');

      ctx.beginPath();
      history.forEach((f, i) => {
        const x = sToX(f.s);
        const y = traceTop + traceH - (f.speed * 3.6 / maxSpeed) * traceH;
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      });
      ctx.lineTo(W, traceTop + traceH);
      ctx.lineTo(0, traceTop + traceH);
      ctx.closePath();
      ctx.fillStyle = grad;
      ctx.fill();

      // Line itself
      ctx.beginPath();
      ctx.strokeStyle = 'rgba(34,211,238,0.5)';
      ctx.lineWidth = 1;
      history.forEach((f, i) => {
        const x = sToX(f.s);
        const y = traceTop + traceH - (f.speed * 3.6 / maxSpeed) * traceH;
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      });
      ctx.stroke();

      // ── C. Coaching event markers ──────────────────────────────
      coachingEvents.forEach(ev => {
        const x = sToX(ev.s);
        const color = ev.severity > 0.8 ? '#fb7185' : ev.severity > 0.5 ? '#fbbf24' : '#60a5fa';
        ctx.fillStyle = color;
        ctx.fillRect(x - 1, traceTop, 2, traceH);
      });

      // ── D. Sector dividers ─────────────────────────────────────
      const sectorColors = ['#22d3ee', '#34d399', '#a78bfa'];
      sectors.forEach((s, i) => {
        const x = sToX(s.start_s);
        ctx.fillStyle = sectorColors[i % 3];
        ctx.fillRect(x, traceTop, 1, 3);
        ctx.font = `600 6px "JetBrains Mono"`;
        ctx.textAlign = 'left';
        ctx.fillStyle = sectorColors[i % 3];
        ctx.globalAlpha = 0.5;
        ctx.fillText(`S${i + 1}`, x + 2, traceTop + 8);
        ctx.globalAlpha = 1;
      });

      // ── E. Cursor position ─────────────────────────────────────
      if (globalCursorS !== null) {
        const cx = sToX(globalCursorS);
        ctx.strokeStyle = 'rgba(255,255,255,0.4)';
        ctx.lineWidth = 1;
        ctx.setLineDash([2, 2]);
        ctx.beginPath(); ctx.moveTo(cx, 0); ctx.lineTo(cx, H); ctx.stroke();
        ctx.setLineDash([]);

        // Cursor marker (triangle at top)
        ctx.fillStyle = '#22d3ee';
        ctx.beginPath();
        ctx.moveTo(cx, 0);
        ctx.lineTo(cx - 4, 5);
        ctx.lineTo(cx + 4, 5);
        ctx.closePath();
        ctx.fill();

        // Distance label
        ctx.fillStyle = 'rgba(255,255,255,0.6)';
        ctx.font = `600 6px "JetBrains Mono"`;
        ctx.textAlign = cx > W / 2 ? 'right' : 'left';
        ctx.fillText(`${globalCursorS.toFixed(0)}m`, cx + (cx > W / 2 ? -3 : 3), H - 1);
      }

      animRef.current = requestAnimationFrame(loop);
    };

    animRef.current = requestAnimationFrame(loop);
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current!.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const { history } = useTelemetryStore.getState();
    if (history.length < 2) return;
    const minS = history[0].s, maxS = history[history.length - 1].s;
    useTelemetryStore.getState().setGlobalCursor(minS + x * (maxS - minS));
  }, []);

  const handleMouseLeave = useCallback(() => {
    useTelemetryStore.getState().setGlobalCursor(null);
  }, []);

  return (
    <div ref={containerRef} className="w-full h-full">
      <canvas
        ref={canvasRef}
        style={{ width: '100%', height: '100%', display: 'block', cursor: 'crosshair' }}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        onMouseDown={handleMouseMove}
      />
    </div>
  );
};
