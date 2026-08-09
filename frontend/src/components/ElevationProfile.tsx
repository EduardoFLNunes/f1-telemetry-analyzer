import React, { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api/client';
import { reliefColorAt } from './map/OverlayRenderer';

type Profile = {
  distance: number[];
  elevation: number[];
  gradient: number[];
};

const PAD = { left: 44, right: 14, top: 14, bottom: 24 };
// Anything past this reads as full climb or descent, matching the map shading.
const GRADIENT_FULL_SCALE = 0.08;

function readProfile(track: any): Profile | null {
  const center = track?.centerline;
  if (!center) return null;
  const distance = center.distance;
  const elevation = center.elevation;
  if (!Array.isArray(distance) || !Array.isArray(elevation)) return null;
  if (distance.length !== elevation.length || distance.length < 2) return null;
  // A track whose height was never derived arrives as a flat line of zeros;
  // drawing that as a profile would claim Interlagos is a table.
  const low = Math.min(...elevation);
  const high = Math.max(...elevation);
  if (high - low < 0.5) return null;
  const gradient = Array.isArray(center.gradient) && center.gradient.length === distance.length
    ? center.gradient
    : new Array(distance.length).fill(0);
  return { distance, elevation, gradient };
}

/**
 * Track elevation against lap distance. Braking downhill and traction uphill are
 * gradient questions, so the profile is filled by slope rather than by height:
 * the shape says where the track goes, the colour says how hard it is.
 */
export const ElevationProfile: React.FC<{ active?: boolean }> = ({ active = true }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hover, setHover] = useState<number | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    if (!active) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const payload = await api.getTrackGeometry();
        if (cancelled) return;
        const next = readProfile(payload?.track || payload);
        setProfile(next);
        setError(next ? null : 'Esta pista ainda nao tem altura extraida.');
      } catch (nextError) {
        if (!cancelled) setError(nextError instanceof Error ? nextError.message : 'Perfil indisponivel');
      }
    })();
    return () => { cancelled = true; };
  }, [active]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || typeof ResizeObserver === 'undefined') return undefined;
    const update = () => {
      const rect = container.getBoundingClientRect();
      setSize({ width: rect.width, height: rect.height });
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  const stats = useMemo(() => {
    if (!profile) return null;
    const low = Math.min(...profile.elevation);
    const high = Math.max(...profile.elevation);
    const steepestClimb = Math.max(...profile.gradient);
    const steepestDrop = Math.min(...profile.gradient);
    return { low, high, drop: high - low, steepestClimb, steepestDrop };
  }, [profile]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !profile || !stats || size.width < 40 || size.height < 40) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(size.width * dpr);
    canvas.height = Math.round(size.height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, size.width, size.height);

    const plotW = size.width - PAD.left - PAD.right;
    const plotH = size.height - PAD.top - PAD.bottom;
    const totalDistance = profile.distance[profile.distance.length - 1] || 1;
    const span = Math.max(stats.high - stats.low, 1e-6);
    const sx = (d: number) => PAD.left + (d / totalDistance) * plotW;
    const sy = (e: number) => PAD.top + plotH - ((e - stats.low) / span) * plotH;

    // Height grid, every 10 m.
    ctx.strokeStyle = 'rgba(148,163,184,0.13)';
    ctx.fillStyle = 'rgba(148,163,184,0.7)';
    ctx.font = '9px "JetBrains Mono", monospace';
    ctx.lineWidth = 1;
    const first = Math.ceil(stats.low / 10) * 10;
    for (let height = first; height <= stats.high; height += 10) {
      const y = sy(height);
      ctx.beginPath();
      ctx.moveTo(PAD.left, y);
      ctx.lineTo(PAD.left + plotW, y);
      ctx.stroke();
      ctx.fillText(`${height.toFixed(0)}m`, 6, y + 3);
    }

    // The area under the curve, coloured by slope one segment at a time.
    for (let i = 1; i < profile.distance.length; i += 1) {
      const t = Math.max(0, Math.min(1, (profile.gradient[i] + GRADIENT_FULL_SCALE) / (2 * GRADIENT_FULL_SCALE)));
      ctx.fillStyle = reliefColorAt('GRADIENT', t);
      ctx.beginPath();
      ctx.moveTo(sx(profile.distance[i - 1]), sy(profile.elevation[i - 1]));
      ctx.lineTo(sx(profile.distance[i]), sy(profile.elevation[i]));
      ctx.lineTo(sx(profile.distance[i]), PAD.top + plotH);
      ctx.lineTo(sx(profile.distance[i - 1]), PAD.top + plotH);
      ctx.closePath();
      ctx.fill();
    }

    ctx.strokeStyle = 'rgba(226,232,240,0.85)';
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    profile.distance.forEach((d, i) => {
      const x = sx(d);
      const y = sy(profile.elevation[i]);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();

    ctx.fillStyle = 'rgba(148,163,184,0.7)';
    for (let d = 0; d <= totalDistance; d += 1000) {
      ctx.fillText(`${(d / 1000).toFixed(0)}km`, sx(d) - 8, size.height - 8);
    }

    if (hover !== null) {
      const index = Math.max(0, Math.min(profile.distance.length - 1,
        Math.round((hover - PAD.left) / plotW * (profile.distance.length - 1))));
      const x = sx(profile.distance[index]);
      const y = sy(profile.elevation[index]);
      ctx.strokeStyle = 'rgba(250,204,21,0.6)';
      ctx.beginPath();
      ctx.moveTo(x, PAD.top);
      ctx.lineTo(x, PAD.top + plotH);
      ctx.stroke();
      ctx.fillStyle = '#facc15';
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fill();
      const label = `${profile.distance[index].toFixed(0)}m  ${profile.elevation[index].toFixed(1)}m  ${(profile.gradient[index] * 100).toFixed(1)}%`;
      const width = ctx.measureText(label).width + 10;
      const boxX = Math.min(x + 8, size.width - width - 4);
      ctx.fillStyle = 'rgba(6,8,16,0.88)';
      ctx.fillRect(boxX, PAD.top + 4, width, 16);
      ctx.fillStyle = '#e2e8f0';
      ctx.fillText(label, boxX + 5, PAD.top + 15);
    }
  }, [profile, stats, size, hover]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 8, padding: 10 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, flexWrap: 'wrap' }}>
        <strong style={{ fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
          Perfil de elevacao
        </strong>
        {stats && (
          <span className="num" style={{ fontSize: 9, color: 'var(--text-3)' }}>
            desnivel {stats.drop.toFixed(1)} m &nbsp;|&nbsp; {stats.low.toFixed(1)} a {stats.high.toFixed(1)} m
            &nbsp;|&nbsp; subida max {(stats.steepestClimb * 100).toFixed(1)}%
            &nbsp;|&nbsp; descida max {(stats.steepestDrop * 100).toFixed(1)}%
          </span>
        )}
      </div>
      <div ref={containerRef} style={{ flex: 1, minHeight: 180, position: 'relative' }}>
        {error ? (
          <div className="num" style={{ fontSize: 9, color: 'var(--text-3)', padding: 12 }}>{error}</div>
        ) : (
          <canvas
            ref={canvasRef}
            style={{ width: '100%', height: '100%', display: 'block', cursor: 'crosshair' }}
            onMouseMove={(event) => setHover(event.nativeEvent.offsetX)}
            onMouseLeave={() => setHover(null)}
          />
        )}
      </div>
    </div>
  );
};

export default ElevationProfile;
