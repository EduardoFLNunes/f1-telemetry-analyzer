import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTelemetryStore } from '../../store/useTelemetryStore';
import { drawCar } from './CarRenderer.jsx';
import { applyCameraTransform, computeTrackBounds } from './CameraController.jsx';
import { drawHud, drawTrackSurface } from './OverlayRenderer.jsx';

function normalizeTrack(trackData) {
  if (!trackData) return null;

  const centerY = trackData.centerline?.y || trackData.centerline?.z || [];
  const visualCenterY = trackData.visualCenterline?.y || trackData.visualCenterline?.z || [];
  const leftY = trackData.left_edge?.y || trackData.left_edge?.z || [];
  const rightY = trackData.right_edge?.y || trackData.right_edge?.z || [];

  return {
    ...trackData,
    trackLength: trackData.trackLength || trackData.length_meters || 0,
    centerline: {
      ...trackData.centerline,
      y: centerY,
    },
    visualCenterline: trackData.visualCenterline
      ? {
          ...trackData.visualCenterline,
          y: visualCenterY,
        }
      : null,
    left_edge: {
      ...trackData.left_edge,
      y: leftY,
    },
    right_edge: {
      ...trackData.right_edge,
      y: rightY,
    },
  };
}

export function TrackRenderer({ trackData }) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const animationRef = useRef(null);
  const [cameraMode, setCameraMode] = useState('OVERVIEW');

  const cameraRef = useRef({
    mode: 'OVERVIEW',
    zoom: 1,
    offset: { x: 0, y: 0 },
    isPanning: false,
    lastMouse: { x: 0, y: 0 },
  });

  const normalizedTrack = useMemo(() => normalizeTrack(trackData), [trackData]);
  const bounds = useMemo(() => computeTrackBounds(normalizedTrack), [normalizedTrack]);

  useEffect(() => {
    cameraRef.current.mode = cameraMode;
  }, [cameraMode]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return undefined;

    const ctx = canvas.getContext('2d');
    if (!ctx) return undefined;

    const render = () => {
      const rect = container.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      if (canvas.width !== Math.round(rect.width * dpr) || canvas.height !== Math.round(rect.height * dpr)) {
        canvas.width = Math.round(rect.width * dpr);
        canvas.height = Math.round(rect.height * dpr);
      }

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, rect.width, rect.height);
      ctx.fillStyle = '#070a12';
      ctx.fillRect(0, 0, rect.width, rect.height);

      const { latestFrame: liveFrame, history: liveHistory } = useTelemetryStore.getState();
      const renderBounds = normalizedTrack
        ? computeTrackBounds(normalizedTrack, liveHistory.slice(-1200), liveFrame)
        : computeTrackBounds(null, liveHistory.slice(-1200), liveFrame);

      ctx.save();
      const scale = applyCameraTransform(ctx, rect.width, rect.height, renderBounds, cameraRef.current, liveFrame);

      if (normalizedTrack) {
        drawTrackSurface(ctx, normalizedTrack, renderBounds, scale);
      }
      if (liveFrame) drawCar(ctx, liveFrame, scale);

      ctx.restore();
      drawHud(ctx, rect.width, rect.height, normalizedTrack, liveFrame, cameraRef.current);
      animationRef.current = requestAnimationFrame(render);
    };

    animationRef.current = requestAnimationFrame(render);
    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
    };
  }, [bounds, normalizedTrack]);

  const handleWheel = useCallback((event) => {
    event.preventDefault();
    const factor = event.deltaY < 0 ? 1.12 : 0.9;
    cameraRef.current.zoom = Math.max(0.2, Math.min(28, cameraRef.current.zoom * factor));
  }, []);

  const handleMouseDown = useCallback((event) => {
    if (cameraRef.current.mode !== 'OVERVIEW') return;
    cameraRef.current.isPanning = true;
    cameraRef.current.lastMouse = { x: event.clientX, y: event.clientY };
  }, []);

  const handleMouseMove = useCallback((event) => {
    const camera = cameraRef.current;
    if (!camera.isPanning) return;
    camera.offset.x += event.clientX - camera.lastMouse.x;
    camera.offset.y += event.clientY - camera.lastMouse.y;
    camera.lastMouse = { x: event.clientX, y: event.clientY };
  }, []);

  const stopPan = useCallback(() => {
    cameraRef.current.isPanning = false;
  }, []);

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full overflow-hidden select-none cursor-crosshair"
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={stopPan}
      onMouseLeave={stopPan}
    >
      <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />

      <div className="absolute top-3 right-3 flex flex-col gap-1">
        <div className="panel px-1.5 py-1 flex gap-1">
          {['OVERVIEW', 'FOLLOW'].map((mode) => (
            <button
              key={mode}
              onClick={() => setCameraMode(mode)}
              className={`px-2 py-0.5 num text-[7px] uppercase rounded-sm transition-all ${
                cameraMode === mode ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30' : 'text-slate-600 hover:text-slate-400'
              }`}
            >
              {mode}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export default TrackRenderer;
