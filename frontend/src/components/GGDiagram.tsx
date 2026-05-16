/**
 * Professional G-G Diagram — Traction Circle Visualization
 * Phase 6: Physically-accurate G-force envelope display.
 */
import React, { useRef, useEffect } from 'react';
import { useTelemetryStore } from '../store/useTelemetryStore';

const G_RANGE = 4;
const TRAIL_LEN = 80;

export const GGDiagram: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef   = useRef<number>();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const loop = () => {
      const { latestFrame, history } = useTelemetryStore.getState();

      const dpr  = window.devicePixelRatio || 1;
      const size = canvas.offsetWidth;
      if (canvas.width !== size * dpr) {
        canvas.width  = size * dpr;
        canvas.height = size * dpr;
        ctx.scale(dpr, dpr);
      }

      const S  = size;
      const cx = S / 2, cy = S / 2;
      const R  = (S / 2) * 0.84;

      ctx.clearRect(0, 0, S, S);

      // Background
      ctx.fillStyle = '#080810';
      ctx.fillRect(0, 0, S, S);

      // Traction circle rings
      [1, 2, 3, 4].forEach(g => {
        const r = (g / G_RANGE) * R;
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.strokeStyle = g === 4 ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.07)';
        ctx.lineWidth = g === 4 ? 1 : 0.6;
        ctx.stroke();
        if (g < 4) {
          ctx.fillStyle = 'rgba(255,255,255,0.2)';
          ctx.font = `500 5.5px "JetBrains Mono"`;
          ctx.textAlign = 'left';
          ctx.fillText(`${g}G`, cx + r + 1, cy - 1);
        }
      });

      // Axes
      ctx.strokeStyle = 'rgba(255,255,255,0.1)';
      ctx.lineWidth = 0.6;
      ctx.setLineDash([2, 4]);
      ctx.beginPath(); ctx.moveTo(cx - R, cy); ctx.lineTo(cx + R, cy); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(cx, cy - R); ctx.lineTo(cx, cy + R); ctx.stroke();
      ctx.setLineDash([]);

      // Axis labels
      ctx.fillStyle = 'rgba(255,255,255,0.2)';
      ctx.font = `500 5px "JetBrains Mono"`;
      ctx.textAlign = 'center';
      ctx.fillText('LAT', cx, cy + R + 8);
      ctx.save(); ctx.translate(cx - R - 7, cy); ctx.rotate(-Math.PI/2);
      ctx.fillText('LON', 0, 0); ctx.restore();

      // Trail
      const trail = history.slice(-TRAIL_LEN);
      if (trail.length > 1) {
        for (let i = 1; i < trail.length; i++) {
          const f = trail[i];
          const lx = cx + (f.accel_g?.x ?? 0) / G_RANGE * R;
          const ly = cy - (f.accel_g?.z ?? 0) / G_RANGE * R;
          const alpha = (i / trail.length) * 0.5;
          ctx.beginPath();
          ctx.arc(lx, ly, 0.8, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(34,211,238,${alpha})`;
          ctx.fill();
        }
      }

      // Current point
      if (latestFrame) {
        const gx = latestFrame.accel_g?.x ?? 0;
        const gz = latestFrame.accel_g?.z ?? 0;
        const px = cx + gx / G_RANGE * R;
        const py = cy - gz / G_RANGE * R;
        const totalG = Math.hypot(gx, gz);
        const intensity = Math.min(totalG / G_RANGE, 1);

        // Vector line from center
        ctx.beginPath();
        ctx.moveTo(cx, cy); ctx.lineTo(px, py);
        ctx.strokeStyle = `rgba(34,211,238,${0.2 + intensity * 0.3})`;
        ctx.lineWidth = 0.8;
        ctx.stroke();

        // Outer glow
        ctx.beginPath();
        ctx.arc(px, py, 5, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(34,211,238,${0.1 + intensity * 0.1})`;
        ctx.fill();

        // Core dot
        ctx.shadowBlur = 8;
        ctx.shadowColor = '#22d3ee';
        ctx.beginPath();
        ctx.arc(px, py, 2.5, 0, Math.PI * 2);
        ctx.fillStyle = intensity > 0.8 ? '#fb7185' : intensity > 0.5 ? '#fbbf24' : '#22d3ee';
        ctx.fill();
        ctx.shadowBlur = 0;

        // G readout
        ctx.fillStyle = 'rgba(255,255,255,0.6)';
        ctx.font = `bold 6px "JetBrains Mono"`;
        ctx.textAlign = 'center';
        ctx.fillText(`${totalG.toFixed(2)}G`, cx, S - 4);
      }

      animRef.current = requestAnimationFrame(loop);
    };

    animRef.current = requestAnimationFrame(loop);
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
  }, []);

  return (
    <div className="w-full aspect-square relative">
      <canvas ref={canvasRef} className="w-full h-full" />
    </div>
  );
};
