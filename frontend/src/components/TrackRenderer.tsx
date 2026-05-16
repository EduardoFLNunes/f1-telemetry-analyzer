/**
 * Professional Motorsport Track Renderer
 * Complete spatial renderer with proper 60fps RAF loop, heatmaps, and vehicle physics.
 * Phases 3-7: Track, Camera, Motion, and Vehicle Systems
 */
import React, { useRef, useEffect, useMemo, useState, useCallback } from 'react';
import { useTelemetryStore, TelemetryFrame } from '../store/useTelemetryStore';

interface TrackRendererProps {
  trackData: {
    name?: string;
    centerline: { x: number[]; y: number[] };
    left_edge: { x: number[]; y: number[] };
    right_edge: { x: number[]; y: number[] };
    corners?: { apex_idx: number; corner_id: number; type?: string }[];
  } | null;
}

type CameraMode = 'OVERVIEW' | 'FOLLOW';
type HeatLayer  = 'NONE' | 'SPEED' | 'BRAKE' | 'DELTA' | 'THROTTLE' | 'DEBUG';

/* ── Speed-to-color (low=blue, mid=yellow, high=red) ─────────────── */
function speedColor(ratio: number, alpha = 1): string {
  const r = ratio < 0.5 ? Math.round(ratio * 2 * 255) : 255;
  const g = ratio < 0.5 ? Math.round(ratio * 2 * 200) : Math.round((1 - (ratio - 0.5) * 2) * 200);
  const b = ratio < 0.5 ? 255 : Math.round((1 - (ratio - 0.5) * 2) * 100);
  return `rgba(${r},${g},${b},${alpha})`;
}

/* ── Draw Arrow ────────────────────────────────────────────────── */
function drawArrow(ctx: CanvasRenderingContext2D, x: number, y: number, angle: number, size: number, color: string) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(angle);
  ctx.beginPath();
  ctx.moveTo(0, 0);
  ctx.lineTo(size, 0);
  ctx.moveTo(size - 3, -2);
  ctx.lineTo(size, 0);
  ctx.lineTo(size - 3, 2);
  ctx.strokeStyle = color;
  ctx.lineWidth = 1;
  ctx.stroke();
  ctx.restore();
}

/* ── Heading lerp (handles wrap-around) ──────────────────────────── */
function lerpAngle(a: number, b: number, t: number): number {
  let d = b - a;
  while (d > Math.PI)  d -= Math.PI * 2;
  while (d < -Math.PI) d += Math.PI * 2;
  return a + d * t;
}

/* ── Critically Damped Spring ────────────────────────────────────── */
function criticallyDamped(current: number, target: number, velocity: { val: number }, dt: number, smoothTime: number): number {
  const omega = 2 / smoothTime;
  const x = omega * dt;
  const exp = 1 / (1 + x + 0.48 * x * x + 0.235 * x * x * x);
  const change = current - target;
  const temp = (velocity.val + omega * change) * dt;
  velocity.val = (velocity.val - omega * temp) * exp;
  return target + (change + temp) * exp;
}

/* ── Draw curbs (alternating stripes along edge) ─────────────────── */
function drawCurbs(
  ctx: CanvasRenderingContext2D,
  edge: { x: number[]; y: number[] },
  center: { x: number[]; y: number[] },
  scale: number,
  side: 'left' | 'right'
) {
  const stripeLen = 8 / scale;  // world-units per stripe
  const curbWidth = 3 / scale;
  let dist = 0;
  let stripeIdx = 0;

  for (let i = 1; i < edge.x.length; i++) {
    const ex1 = edge.x[i-1], ey1 = edge.y[i-1];
    const ex2 = edge.x[i],   ey2 = edge.y[i];
    const cx1 = center.x[i-1] ?? ex1, cy1 = center.y[i-1] ?? ey1;
    const cx2 = center.x[i]   ?? ex2, cy2 = center.y[i]   ?? ey2;

    const segLen = Math.hypot(ex2 - ex1, ey2 - ey1);
    const isRed = (Math.floor(dist / stripeLen) % 2 === 0);

    // Direction from edge toward center
    const nx = (cx1 - ex1) / (Math.hypot(cx1 - ex1, cy1 - ey1) || 1);
    const ny = (cy1 - ey1) / (Math.hypot(cx1 - ex1, cy1 - ey1) || 1);

    ctx.beginPath();
    ctx.moveTo(ex1, ey1);
    ctx.lineTo(ex2, ey2);
    ctx.lineTo(ex2 + nx * curbWidth, ey2 + ny * curbWidth);
    ctx.lineTo(ex1 + nx * curbWidth, ey1 + ny * curbWidth);
    ctx.closePath();
    ctx.fillStyle = isRed ? 'rgba(220,38,38,0.9)' : 'rgba(255,255,255,0.7)';
    ctx.fill();

    dist += segLen;
  }
}

/* ── Vehicle renderer ────────────────────────────────────────────── */
function drawVehicle(
  ctx: CanvasRenderingContext2D,
  frame: TelemetryFrame,
  color: string,
  scale: number,
  isLive: boolean,
  label?: string
) {
  const slip = frame.slip_angle ?? 0;
  const steer = frame.steering ?? 0;

  ctx.save();
  ctx.translate(frame.x, frame.z);
  // Subtract PI/2 because heading 0 (North) should point UP (-Y in Canvas)
  // and in Canvas rotate(0) points RIGHT (+X).
  ctx.rotate((frame.heading ?? 0) - Math.PI / 2 + slip * 0.25); 

  if (isLive) {
    ctx.shadowBlur = 15 / scale;
    ctx.shadowColor = color;
  }

  const len = 9 / scale;
  const wid = 4.5 / scale;

  // --- Car body (high-fidelity silhouette) ---
  ctx.beginPath();
  ctx.moveTo(len * 1.1, 0);               
  ctx.lineTo(len * 0.4, wid * 0.5);  
  ctx.lineTo(-len * 0.7, wid * 0.6);  
  ctx.lineTo(-len * 0.7, -wid * 0.6); 
  ctx.lineTo(len * 0.4, -wid * 0.5);  
  ctx.closePath();
  ctx.fillStyle = color;
  ctx.fill();

  // --- Cockpit ----
  ctx.beginPath();
  ctx.ellipse(len * 0.2, 0, len * 0.25, wid * 0.22, 0, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(0,0,0,0.85)';
  ctx.fill();

  // --- Front/Rear Wings ---
  ctx.fillStyle = isLive ? `${color}dd` : 'rgba(255,255,255,0.3)';
  ctx.fillRect(len * 0.8, -wid * 0.95, len * 0.3, wid * 1.9); // Front
  ctx.fillRect(-len * 0.85, -wid * 0.85, len * 0.2, wid * 1.7); // Rear

  // --- Wheels (Smoothly steered) ---
  const wheelW = 3.5 / scale, wheelH = 1.8 / scale;
  [-wid * 0.75, wid * 0.75].forEach(wheelY => {
    // Front
    ctx.save();
    ctx.translate(len * 0.6, wheelY);
    ctx.rotate(steer * 0.75); // Visual steering amplification
    ctx.fillStyle = '#111';
    ctx.fillRect(-wheelW/2, -wheelH/2, wheelW, wheelH);
    ctx.restore();
    // Rear
    ctx.fillStyle = '#111';
    ctx.fillRect(-len * 0.5 - wheelW/2, wheelY - wheelH/2, wheelW, wheelH);
  });

  ctx.shadowBlur = 0;
  ctx.restore();

  // --- HUD Indicators ---
  if (isLive) {
    ctx.save();
    ctx.translate(frame.x, frame.z);
    const indicatorR = 15 / scale;
    if (frame.throttle > 0.02) {
      ctx.beginPath();
      ctx.arc(0, 0, indicatorR, -Math.PI / 2, -Math.PI / 2 + frame.throttle * Math.PI * 2);
      ctx.strokeStyle = 'rgba(52,211,153,0.6)';
      ctx.lineWidth = 2 / scale;
      ctx.stroke();
    }
    if (frame.brake > 0.02) {
      ctx.beginPath();
      ctx.arc(0, 0, indicatorR + 2.5 / scale, -Math.PI / 2, -Math.PI / 2 - frame.brake * Math.PI * 2, true);
      ctx.strokeStyle = 'rgba(251,113,133,0.7)';
      ctx.lineWidth = 2 / scale;
      ctx.stroke();
    }
    ctx.restore();
  }

  // --- Label ---
  if (label) {
    ctx.save();
    ctx.translate(frame.x, frame.z);
    ctx.fillStyle = isLive ? '#fff' : 'rgba(255,255,255,0.4)';
    ctx.font = `bold ${7 / scale}px "JetBrains Mono"`;
    ctx.textAlign = 'center';
    ctx.fillText(label, 0, -16 / scale);
    ctx.restore();
  }
}

/* ── Debug mode visualization ────────────────────────────────────── */
function drawDebugSpatial(
  ctx: CanvasRenderingContext2D,
  frame: TelemetryFrame,
  trackData: any,
  scale: number
) {
  // 1. Projected Position on Spline (Visualized)
  // Use the analytical projection from backend if available, otherwise fallback to simple nearest
  let nx = frame.projected_x;
  let nz = frame.projected_z;

  if (nx === undefined || nz === undefined) {
    let minDist = Infinity;
    let nearestIdx = 0;
    for (let i = 0; i < trackData.centerline.x.length; i++) {
      const d = Math.hypot(frame.x - trackData.centerline.x[i], frame.z - trackData.centerline.y[i]);
      if (d < minDist) {
        minDist = d;
        nearestIdx = i;
      }
    }
    nx = trackData.centerline.x[nearestIdx];
    nz = trackData.centerline.y[nearestIdx];
  }

  // Draw offset line (Decoupling Check)
  ctx.beginPath();
  ctx.moveTo(frame.x, frame.z); // Real visual position
  ctx.lineTo(nx, nz);           // Analytical projected position
  ctx.strokeStyle = Math.abs(frame.L || 0) > 6.0 ? '#ef4444' : '#10b981'; // Red if high lateral error
  ctx.lineWidth = 1.5 / scale;
  ctx.setLineDash([2/scale, 2/scale]);
  ctx.stroke();
  ctx.setLineDash([]);

  // Draw analytical ghost marker (Small cross at projection)
  ctx.beginPath();
  ctx.moveTo(nx - 2/scale, nz - 2/scale); ctx.lineTo(nx + 2/scale, nz + 2/scale);
  ctx.moveTo(nx + 2/scale, nz - 2/scale); ctx.lineTo(nx - 2/scale, nz + 2/scale);
  ctx.strokeStyle = 'rgba(255,255,255,0.5)';
  ctx.stroke();

  // 2. Metrics HUD (Professional Diagnostics)
  ctx.save();
  ctx.resetTransform();
  ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
  ctx.fillRect(10, 50, 180, 180);
  ctx.strokeStyle = '#334155';
  ctx.strokeRect(10, 50, 180, 180);
  
  ctx.fillStyle = '#0ea5e9';
  ctx.font = 'bold 9px "JetBrains Mono"';
  ctx.fillText('SPATIAL INTELLIGENCE', 20, 65);

  ctx.fillStyle = '#94a3b8';
  ctx.font = '8px "JetBrains Mono"';
  ctx.fillText(`s (Progress): ${frame.s?.toFixed(2)}m`, 20, 80);
  ctx.fillText(`L (Lateral): ${frame.L?.toFixed(2)}m`, 20, 95);
  ctx.fillText(`Yaw: ${(frame.heading || 0).toFixed(3)} rad`, 20, 110);
  ctx.fillText(`Conf: ${((frame as any).reconstruction_confidence * 100)?.toFixed(1)}%`, 20, 125);
  ctx.fillText(`V: ${(frame.speed * 3.6).toFixed(1)} km/h`, 20, 140);
  
  // Alignment Diagnostics
  ctx.fillStyle = '#38bdf8';
  ctx.fillText(`dx (Offset): ${frame.dx?.toFixed(3)}m`, 20, 160);
  ctx.fillText(`dz (Offset): ${frame.dz?.toFixed(3)}m`, 20, 175);
  ctx.fillStyle = (frame.alignment_drift || 0) > 1.0 ? '#fbbf24' : '#10b981';
  ctx.fillText(`Drift: ${frame.alignment_drift?.toFixed(3)}m`, 20, 190);
  
  // Bootstrap Diagnostics
  ctx.fillStyle = frame.is_pitlane ? '#f43f5e' : '#94a3b8';
  ctx.fillText(`Pitlane: ${frame.is_pitlane ? 'YES' : 'NO'}`, 20, 205);
  ctx.fillStyle = (frame.bootstrap_conf || 0) > 0.8 ? '#10b981' : '#fbbf24';
  ctx.fillText(`Boot Conf: ${((frame.bootstrap_conf || 0) * 100).toFixed(0)}%`, 20, 220);
  
  ctx.restore();

  // 3. Heading Vectors
  const vhx = Math.sin(frame.heading ?? 0);
  const vhz = -Math.cos(frame.heading ?? 0);
  ctx.beginPath();
  ctx.moveTo(frame.x, frame.z);
  ctx.lineTo(frame.x + vhx * 25 / scale, frame.z + vhz * 25 / scale);
  ctx.strokeStyle = '#fbbf24';
  ctx.lineWidth = 2 / scale;
  ctx.stroke();
}

/* ═══════════════════════════════════════════════════════════════════ */

export const TrackRenderer: React.FC<TrackRendererProps> = ({ trackData }) => {
  const canvasRef    = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const animRef      = useRef<number>();

  // Camera + UI state (as refs — no re-renders in hot path)
  const uiRef = useRef({
    zoom: 1,
    cameraMode: 'OVERVIEW' as CameraMode,
    heatLayer: 'NONE' as HeatLayer,
    offset: { x: 0, y: 0 },
    isPanning: false,
    lastMouse: { x: 0, y: 0 },
    // Temporal Pipeline State
    renderBuffer: [] as TelemetryFrame[],
    renderHistory: [] as { x: number, z: number, s: number, speed: number, throttle: number, brake: number, delta: number }[],
    interpolatedFrame: null as TelemetryFrame | null,
    renderLagMs: 120, // 120ms lag for smooth interpolation
    // Lerped rendering state (State Prediction Engine)
    carX: 0, carZ: 0, carH: 0,
    carVelX: { val: 0 }, carVelZ: { val: 0 }, carVelH: { val: 0 },
    camX: 0, camY: 0, camH: 0, camZoom: 1,
    camVelX: { val: 0 }, camVelY: { val: 0 }, camVelH: { val: 0 },
    lastFrameTime: 0,
    prevS: 0, prevL: 0,
    // Debug Stats
    packetTiming: [] as number[],
    bufferSize: 0,
    interpDelay: 0
    });

    // React state for UI buttons only
    const [cameraMode, _setCameraMode] = useState<CameraMode>('OVERVIEW');
    const [heatLayer, _setHeatLayer]   = useState<HeatLayer>('NONE');

    const setCameraMode = useCallback((m: CameraMode) => {
    uiRef.current.cameraMode = m;
    _setCameraMode(m);
    }, []);
    const setHeatLayer = useCallback((l: HeatLayer) => {
    uiRef.current.heatLayer = l;
    _setHeatLayer(l);
    }, []);

    // Track bounds (memoized)
    const bounds = useMemo(() => {
    if (!trackData) return { minX: -100, maxX: 100, minY: -100, maxY: 100, cx: 0, cy: 0, w: 200, h: 200 };
    const ax = [...trackData.left_edge.x, ...trackData.right_edge.x].filter(isFinite);
    const ay = [...trackData.left_edge.y, ...trackData.right_edge.y].filter(isFinite);
    if (ax.length === 0 || ay.length === 0) return { minX: -100, maxX: 100, minY: -100, maxY: 100, cx: 0, cy: 0, w: 200, h: 200 };

    const minX = Math.min(...ax), maxX = Math.max(...ax);
    const minY = Math.min(...ay), maxY = Math.max(...ay);
    return { minX, maxX, minY, maxY, cx: (minX + maxX) / 2, cy: (minY + maxY) / 2, w: maxX - minX, h: maxY - minY };
    }, [trackData]);

    /* ── Main render loop ──────────────────────────────────────────── */
    useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const loop = (timestamp: number) => {
      const { latestFrame, history, ghostHistory, globalCursorS } = useTelemetryStore.getState();
      const ui = uiRef.current;

      const dt = ui.lastFrameTime ? (timestamp - ui.lastFrameTime) / 1000 : 0.016;
      ui.lastFrameTime = timestamp;

      // ── Resize canvas ──────────────────────────────────────────
      const dpr  = window.devicePixelRatio || 1;
      const rect = container.getBoundingClientRect();
      const W = rect.width, H = rect.height;
      if (canvas.width !== W * dpr || canvas.height !== H * dpr) {
        canvas.width  = W * dpr;
        canvas.height = H * dpr;
        ctx.scale(dpr, dpr);
      }

      // ── Temporal Pipeline: Buffer Management ──────────────────
      if (latestFrame && (!ui.renderBuffer.length || ui.renderBuffer[ui.renderBuffer.length-1].timestamp !== latestFrame.timestamp)) {
        if (ui.renderBuffer.length > 0) {
          const lastT = ui.renderBuffer[ui.renderBuffer.length-1].timestamp;
          ui.packetTiming.push(latestFrame.timestamp - lastT);
          if (ui.packetTiming.length > 60) ui.packetTiming.shift();
        }
        ui.renderBuffer.push(latestFrame);
        if (ui.renderBuffer.length > 60) ui.renderBuffer.shift();
      }

      // Adaptive Render Lag (Dynamic jitter compensation)
      const targetBufferSize = 15;
      if (ui.renderBuffer.length < targetBufferSize) ui.renderLagMs += 2;
      else if (ui.renderBuffer.length > targetBufferSize + 5) ui.renderLagMs -= 2;
      ui.renderLagMs = Math.max(80, Math.min(300, ui.renderLagMs));

      // ── Temporal Pipeline: Sub-frame Interpolation ────────────
      const renderTime = Date.now() - ui.renderLagMs;
      let frameA: TelemetryFrame | null = null;
      let frameB: TelemetryFrame | null = null;

      for (let i = ui.renderBuffer.length - 1; i > 0; i--) {
        if (ui.renderBuffer[i].timestamp <= renderTime) {
           frameA = ui.renderBuffer[i];
           frameB = ui.renderBuffer[i+1] || null;
           break;
        }
      }

      let interpTarget: TelemetryFrame | null = null;
      if (frameA && frameB) {
        const t = (renderTime - frameA.timestamp) / (frameB.timestamp - frameA.timestamp);
        interpTarget = {
          ...frameA,
          x: frameA.x + (frameB.x - frameA.x) * t,
          z: frameA.z + (frameB.z - frameA.z) * t,
          heading: lerpAngle(frameA.heading || 0, frameB.heading || 0, t),
          speed: frameA.speed + (frameB.speed - frameA.speed) * t,
          s: frameA.s + (frameB.s - frameA.s) * t,
          L: frameA.L + (frameB.L - frameA.L) * t,
          projected_x: frameA.projected_x && frameB.projected_x ? frameA.projected_x + (frameB.projected_x - frameA.projected_x) * t : undefined,
          projected_z: frameA.projected_z && frameB.projected_z ? frameA.projected_z + (frameB.projected_z - frameA.projected_z) * t : undefined,
          throttle: frameA.throttle + (frameB.throttle - frameA.throttle) * t,
          brake: frameA.brake + (frameB.brake - frameA.brake) * t,
          steering: frameA.steering + (frameB.steering - frameA.steering) * t
        };
      } else if (ui.renderBuffer.length > 0) {
        interpTarget = ui.renderBuffer[ui.renderBuffer.length - 1];
      }
      ui.interpolatedFrame = interpTarget;

      // ── State Prediction & Smoothing (Critically Damped) ──────
      if (interpTarget) {
        const smoothingTime = 0.04; // Very fast smoothing to maintain physical alignment
        
        // Initial snap or recovery from large jumps
        const distSq = Math.pow(ui.carX - interpTarget.x, 2) + Math.pow(ui.carZ - interpTarget.z, 2);
        if (ui.carX === 0 || distSq > 10000) {
            ui.carX = interpTarget.x;
            ui.carZ = interpTarget.z;
            ui.carH = interpTarget.heading || 0;
            ui.carVelX.val = 0; ui.carVelZ.val = 0; ui.carVelH.val = 0;
            // Also snap camera
            ui.camX = ui.carX; ui.camY = ui.carZ; ui.camH = ui.carH;
        }

        ui.carX = criticallyDamped(ui.carX, interpTarget.x, ui.carVelX, dt, smoothingTime);
        ui.carZ = criticallyDamped(ui.carZ, interpTarget.z, ui.carVelZ, dt, smoothingTime);
        ui.carH = criticallyDamped(ui.carH, interpTarget.heading || 0, ui.carVelH, dt, smoothingTime * 1.5);

        // Update render history for smooth trajectory
        if (ui.renderHistory.length === 0 || Math.hypot(ui.carX - ui.renderHistory[ui.renderHistory.length-1].x, ui.carZ - ui.renderHistory[ui.renderHistory.length-1].z) > 1.5) {
          ui.renderHistory.push({
            x: ui.carX,
            z: ui.carZ,
            s: interpTarget.s,
            speed: interpTarget.speed,
            throttle: interpTarget.throttle,
            brake: interpTarget.brake,
            delta: interpTarget.delta
          });
          if (ui.renderHistory.length > 500) ui.renderHistory.shift();
        }
      }

      // ── Transform setup ─────────────────────────────────────
      ctx.clearRect(0, 0, W, H);

      // Deep-space background
      const bgGrad = ctx.createRadialGradient(W/2, H/2, 0, W/2, H/2, Math.max(W, H) * 0.7);
      bgGrad.addColorStop(0, '#0a0a16');
      bgGrad.addColorStop(1, '#060609');
      ctx.fillStyle = bgGrad;
      ctx.fillRect(0, 0, W, H);

      ctx.save();
      let finalScale = 1;

      if (ui.cameraMode === 'OVERVIEW' || !interpTarget) {
        finalScale = Math.min(W / (bounds.w || 1), H / (bounds.h || 1)) * 0.85 * ui.zoom;
        ctx.translate(W / 2 + ui.offset.x, H / 2 + ui.offset.y);
        ctx.scale(finalScale, finalScale);
        ctx.translate(-bounds.cx, -bounds.cy);
      } else {
        // PROFESSIONAL FOLLOW CAMERA: Predictive & Track-Relative
        finalScale = (H / 75) * ui.zoom; 

        const camSmooth = 0.35; // Cinematic camera smoothing
        ui.camX = criticallyDamped(ui.camX, ui.carX, ui.camVelX, dt, camSmooth);
        ui.camY = criticallyDamped(ui.camY, ui.carZ, ui.camVelY, dt, camSmooth);
        ui.camH = criticallyDamped(ui.camH, ui.carH, ui.camVelH, dt, camSmooth * 0.8);

        ctx.translate(W / 2, H * 0.7); 
        ctx.scale(finalScale, finalScale);
        ctx.rotate(-ui.camH + Math.PI / 2);
        ctx.translate(-ui.camX, -ui.camY);
      }


      if (!trackData) { ctx.restore(); animRef.current = requestAnimationFrame(loop); return; }

      // ── A. Track surface ─────────────────────────────────────
      ctx.beginPath();
      for (let i = 0; i < trackData.left_edge.x.length; i++) {
        const op = i === 0 ? 'moveTo' : 'lineTo';
        ctx[op](trackData.left_edge.x[i], trackData.left_edge.y[i]);
      }
      for (let i = trackData.right_edge.x.length - 1; i >= 0; i--) {
        ctx.lineTo(trackData.right_edge.x[i], trackData.right_edge.y[i]);
      }
      ctx.closePath();

      // Asphalt with subtle grain
      const surfaceGrad = ctx.createLinearGradient(bounds.minX, bounds.minY, bounds.maxX, bounds.maxY);
      surfaceGrad.addColorStop(0, '#1a1a2b');
      surfaceGrad.addColorStop(0.5, '#1e1e32');
      surfaceGrad.addColorStop(1, '#181826');
      ctx.fillStyle = surfaceGrad;
      ctx.fill();

      // Subtle asphalt grain (performance efficient)
      ctx.globalCompositeOperation = 'overlay';
      ctx.fillStyle = 'rgba(255,255,255,0.02)';
      for (let i = 0; i < 50; i++) {
        const gx = Math.random() * bounds.w + bounds.minX;
        const gy = Math.random() * bounds.h + bounds.minY;
        ctx.fillRect(gx, gy, 10/finalScale, 10/finalScale);
      }
      ctx.globalCompositeOperation = 'source-over';

      // ── B. Heatmap layer ─────────────────────────────────────
      if (ui.heatLayer !== 'NONE' && ui.renderHistory.length > 2) {
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        const heatW = 5 / finalScale;

        for (let i = 1; i < ui.renderHistory.length; i++) {
          const p1 = ui.renderHistory[i - 1], p2 = ui.renderHistory[i];
          let col: string;

          if (ui.heatLayer === 'SPEED') {
            const ratio = Math.min(p2.speed / 80, 1);
            col = speedColor(ratio, 0.6);
          } else if (ui.heatLayer === 'BRAKE') {
            col = `rgba(251,113,133,${0.2 + p2.brake * 0.7})`;
          } else if (ui.heatLayer === 'THROTTLE') {
            col = `rgba(52,211,153,${0.2 + p2.throttle * 0.7})`;
          } else {
            col = p2.delta <= 0 ? 'rgba(52,211,153,0.4)' : 'rgba(251,113,133,0.4)';
          }

          ctx.strokeStyle = col;
          ctx.lineWidth = heatW;
          ctx.beginPath();
          ctx.moveTo(p1.x, p1.z);
          ctx.lineTo(p2.x, p2.z);
          ctx.stroke();
        }
      }

      // ── C. Curbs (Enhanced multi-layer) ──────────────────────
      if (ui.cameraMode === 'OVERVIEW') {
        drawCurbs(ctx, trackData.left_edge, trackData.centerline, finalScale, 'left');
        drawCurbs(ctx, trackData.right_edge, trackData.centerline, finalScale, 'right');
      }

      // ── D. Edge lines (High Contrast) ─────────────────────────
      const drawEdge = (pts: { x: number[]; y: number[] }, color: string, width: number) => {
        ctx.beginPath();
        ctx.strokeStyle = color;
        ctx.lineWidth = width / finalScale;
        ctx.setLineDash([]);
        ctx.moveTo(pts.x[0], pts.y[0]);
        for (let i = 1; i < pts.x.length; i++) ctx.lineTo(pts.x[i], pts.y[i]);
        ctx.stroke();
      };
      
      // Concrete edge shadow
      drawEdge(trackData.left_edge,  'rgba(0,0,0,0.4)', 3.0);
      drawEdge(trackData.right_edge, 'rgba(0,0,0,0.4)', 3.0);
      // Primary white line
      drawEdge(trackData.left_edge,  'rgba(255,255,255,0.4)', 1.2);
      drawEdge(trackData.right_edge, 'rgba(255,255,255,0.4)', 1.2);

      // Center dashes (Technical style)
      ctx.beginPath();
      ctx.strokeStyle = 'rgba(255,255,255,0.06)';
      ctx.lineWidth = 0.6 / finalScale;
      ctx.setLineDash([10 / finalScale, 20 / finalScale]);
      ctx.moveTo(trackData.centerline.x[0], trackData.centerline.y[0]);
      for (let i = 1; i < trackData.centerline.x.length; i++) {
        ctx.lineTo(trackData.centerline.x[i], trackData.centerline.y[i]);
      }
      ctx.stroke();
      ctx.setLineDash([]);

      // ── E. Rubbered racing line (Cinematic Trail) ────────────
      if (ui.renderHistory.length > 2 && ui.heatLayer === 'NONE') {
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        
        // Glow pass
        ctx.shadowBlur = 10;
        ctx.shadowColor = 'rgba(34,211,238,0.3)';
        
        for (let i = 1; i < ui.renderHistory.length; i++) {
          const p1 = ui.renderHistory[i - 1], p2 = ui.renderHistory[i];
          const age   = (ui.renderHistory.length - i) / ui.renderHistory.length;
          const alpha = Math.max(0.05, 1 - age * 0.9);
          const vfac  = Math.min(p2.speed / 85, 1);
          
          ctx.beginPath();
          ctx.strokeStyle = `rgba(34,211,238,${alpha})`;
          ctx.lineWidth   = (2.0 + vfac * 3.0) / finalScale;
          ctx.moveTo(p1.x, p1.z);
          ctx.lineTo(p2.x, p2.z);
          ctx.stroke();
        }
        ctx.shadowBlur = 0;
      }

      // Ghost line
      if (ghostHistory.length > 2) {
        ctx.beginPath();
        ctx.strokeStyle = 'rgba(251,191,36,0.2)';
        ctx.lineWidth = 1 / finalScale;
        ctx.moveTo(ghostHistory[0].x, ghostHistory[0].z);
        for (let i = 1; i < ghostHistory.length; i++) ctx.lineTo(ghostHistory[i].x, ghostHistory[i].z);
        ctx.stroke();
      }


      // ── F. Apex & corner markers ──────────────────────────────
      if (trackData.corners && ui.cameraMode === 'OVERVIEW') {
        trackData.corners.forEach(c => {
          const cx = trackData.centerline.x[c.apex_idx];
          const cy = trackData.centerline.y[c.apex_idx];
          if (!isFinite(cx) || !isFinite(cy)) return;

          // Apex circle
          ctx.beginPath();
          ctx.arc(cx, cy, 4 / finalScale, 0, Math.PI * 2);
          ctx.fillStyle = 'rgba(251,191,36,0.15)';
          ctx.fill();
          ctx.strokeStyle = 'rgba(251,191,36,0.5)';
          ctx.lineWidth = 1 / finalScale;
          ctx.stroke();

          // Corner label
          ctx.fillStyle = 'rgba(251,191,36,0.7)';
          ctx.font = `bold ${7 / finalScale}px "JetBrains Mono"`;
          ctx.textAlign = 'center';
          ctx.fillText(`T${c.corner_id}`, cx, cy - 8 / finalScale);
        });
      }

      // ── G. Vehicles ───────────────────────────────────────────
      // Ghost car
      if (interpTarget && ghostHistory.length > 0) {
        const ghost = ghostHistory.find(f => Math.abs(f.s - interpTarget!.s) < 3);
        if (ghost && isFinite(ghost.x) && isFinite(ghost.z)) {
          drawVehicle(ctx, ghost, 'rgba(251,191,36,0.5)', finalScale, false, 'REF');
        }
      }

      // Cursor car (scrubbing)
      if (globalCursorS !== null && history.length > 0) {
        const cursor = history.reduce((prev, cur) =>
          Math.abs(cur.s - globalCursorS!) < Math.abs(prev.s - globalCursorS!) ? cur : prev);
        if (cursor && isFinite(cursor.x) && isFinite(cursor.z)) {
          drawVehicle(ctx, cursor, 'rgba(167,139,250,0.65)', finalScale, false, 'POS');
        }
      }

      // Live car
      if (interpTarget && isFinite(ui.carX) && isFinite(ui.carZ)) {
        const renderFrame: TelemetryFrame = {
          ...interpTarget,
          x: ui.carX,
          z: ui.carZ,
          heading: ui.carH
        };
        drawVehicle(ctx, renderFrame, '#22d3ee', finalScale, true);

        // Debug spatial info
        if (ui.heatLayer === 'DEBUG') {
          drawDebugSpatial(ctx, renderFrame, trackData, finalScale);
          
          // Temporal Debug HUD
          ctx.save();
          ctx.resetTransform();
          ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
          ctx.fillRect(W - 180, 50, 170, 100);
          ctx.strokeStyle = '#0ea5e9';
          ctx.strokeRect(W - 180, 50, 170, 100);
          
          ctx.fillStyle = '#0ea5e9';
          ctx.font = 'bold 9px "JetBrains Mono"';
          ctx.fillText('TEMPORAL PIPELINE', W - 170, 65);
          
          ctx.fillStyle = '#94a3b8';
          ctx.font = '8px "JetBrains Mono"';
          ctx.fillText(`Buffer: ${ui.renderBuffer.length} frames`, W - 170, 80);
          ctx.fillText(`Interp: ${frameA && frameB ? 'ACTIVE' : 'STALLED'}`, W - 170, 95);
          ctx.fillText(`Lag: ${ui.renderLagMs}ms`, W - 170, 110);
          ctx.fillText(`Jitter: ${(ui.packetTiming[ui.packetTiming.length-1] || 0).toFixed(1)}ms`, W - 170, 125);
          ctx.fillText(`FPS: ${(1/dt).toFixed(0)}`, W - 170, 140);
          ctx.restore();
        }
      }

      ctx.restore();
      animRef.current = requestAnimationFrame(loop);
    };

    animRef.current = requestAnimationFrame(loop);
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
  }, [trackData, bounds]);

  /* ── Mouse handlers ────────────────────────────────────────────── */
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.12 : 0.9;
    uiRef.current.zoom = Math.max(0.1, Math.min(30, uiRef.current.zoom * factor));
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (uiRef.current.cameraMode === 'OVERVIEW') {
      uiRef.current.isPanning = true;
      uiRef.current.lastMouse = { x: e.clientX, y: e.clientY };
    }
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    const ui = uiRef.current;
    if (ui.isPanning) {
      ui.offset.x += e.clientX - ui.lastMouse.x;
      ui.offset.y += e.clientY - ui.lastMouse.y;
      ui.lastMouse = { x: e.clientX, y: e.clientY };
    }
  }, []);

  const handleMouseUp = useCallback(() => { uiRef.current.isPanning = false; }, []);

  /* ── HUD Controls ─────────────────────────────────────────────── */
  const CamBtn = ({ mode }: { mode: CameraMode }) => (
    <button
      onClick={() => setCameraMode(mode)}
      className={`px-2 py-0.5 num text-[7px] uppercase tracking-wider rounded-sm transition-all
        ${cameraMode === mode ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30' : 'text-slate-600 hover:text-slate-400'}`}
    >{mode}</button>
  );

  const HeatBtn = ({ layer }: { layer: HeatLayer }) => (
    <button
      onClick={() => setHeatLayer(layer)}
      className={`px-1.5 py-0.5 num text-[7px] uppercase tracking-wide rounded-sm transition-all
        ${heatLayer === layer ? 'bg-slate-700/60 text-white' : 'text-slate-700 hover:text-slate-500'}`}
    >{layer === 'NONE' ? '–' : layer.substring(0, 3)}</button>
  );

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full overflow-hidden select-none cursor-crosshair"
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />

      {/* ── Top-left: session info ── */}
      <div className="absolute top-3 left-3 flex flex-col gap-1 opacity-70 hover:opacity-100 transition-opacity">
        <div className="panel px-2 py-1 flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 status-live" />
          <span className="num text-[8px] text-slate-400 uppercase tracking-widest">
            {trackData?.name ?? 'CIRCUIT'}
          </span>
        </div>
      </div>

      {/* ── Top-right: camera + heat controls ── */}
      <div className="absolute top-3 right-3 flex flex-col gap-1">
        <div className="panel px-1.5 py-1 flex gap-1">
          <CamBtn mode="OVERVIEW" />
          <CamBtn mode="FOLLOW" />
        </div>
        <div className="panel px-1.5 py-1 flex gap-0.5">
          {(['NONE', 'SPEED', 'BRAKE', 'THROTTLE', 'DELTA', 'DEBUG'] as HeatLayer[]).map(l => (
            <HeatBtn key={l} layer={l} />
          ))}
        </div>
      </div>

      {/* ── Legend (heat mode active) ── */}
      {heatLayer !== 'NONE' && (
        <div className="absolute bottom-3 left-3 panel px-2 py-1 flex items-center gap-2">
          <span className="label">HEAT</span>
          <div className="w-16 h-1.5 rounded" style={{
            background: heatLayer === 'SPEED'
              ? 'linear-gradient(to right, #3b82f6, #fbbf24, #ef4444)'
              : heatLayer === 'BRAKE'
              ? 'linear-gradient(to right, transparent, #fb7185)'
              : heatLayer === 'THROTTLE'
              ? 'linear-gradient(to right, transparent, #34d399)'
              : 'linear-gradient(to right, #34d399, transparent, #fb7185)'
          }} />
          <span className="label">{heatLayer}</span>
        </div>
      )}

      {/* ── Zoom indicator ── */}
      <div className="absolute bottom-3 right-3 panel px-2 py-0.5">
        <span className="num text-[7px] text-slate-600">×{uiRef.current.zoom.toFixed(1)}</span>
      </div>
    </div>
  );
};
