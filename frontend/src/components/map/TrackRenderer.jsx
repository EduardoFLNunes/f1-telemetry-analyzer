import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTelemetryStore } from '../../store/useTelemetryStore';
import { useInterpolatedCarState } from '../../hooks/useInterpolatedCarState';
import { drawCar, drawTrajectory } from './CarRenderer.jsx';
import { applyCameraTransform, computeTrackBounds } from './CameraController.jsx';
import {
  createTrackPathCache,
  drawHud,
  drawPhysicsEdges,
  drawProjectionDebug,
  drawTrackSurface,
} from './OverlayRenderer.jsx';
import { ProjectionDebugOverlay } from '../debug/ProjectionDebugOverlay.jsx';
import { mirrorMode, resolveMirrorX } from './renderTransform.js';

function normalizeTrack(trackData) {
  if (!trackData) return null;

  const centerY = trackData.centerline?.y || trackData.centerline?.z || [];
  const leftY = trackData.left_edge?.y || trackData.left_edge?.z || [];
  const rightY = trackData.right_edge?.y || trackData.right_edge?.z || [];

  return {
    ...trackData,
    trackLength: trackData.trackLength || trackData.length_meters || 0,
    centerline: {
      ...trackData.centerline,
      y: centerY,
    },
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

function normalizeVisualTrack(trackData) {
  const visual = trackData?.visualGeometry;
  const visualLeft = visual?.leftEdge || visual?.left_edge;
  const visualRight = visual?.rightEdge || visual?.right_edge;
  if (!trackData || !visualLeft?.x?.length || !visualRight?.x?.length) return null;
  return {
    ...trackData,
    source: visual.source || trackData.source,
    centerline: {
      ...(trackData.centerline || {}),
      ...(visual.centerline || {}),
      y: visual.centerline?.y || visual.centerline?.z || [],
    },
    left_edge: {
      ...(visualLeft || {}),
      y: visualLeft?.y || visualLeft?.z || [],
    },
    right_edge: {
      ...(visualRight || {}),
      y: visualRight?.y || visualRight?.z || [],
    },
    localWidth: visual.width || visual.localWidth || trackData.localWidth,
    bounds: visual.bounds || trackData.bounds,
    widthMin: visual.widthMin ?? trackData.widthMin,
    widthAvg: visual.widthAvg ?? trackData.widthAvg,
    widthMax: visual.widthMax ?? trackData.widthMax,
    visualGeometryEnabled: true,
  };
}

function selectDebugTrajectory(history = [], frame = null, maxPoints = 260) {
  if (!frame || !history?.length) return [];
  const frameLap = Number(frame.lap_number);
  const hasLap = Number.isFinite(frameLap);
  const filtered = hasLap
    ? history.filter((sample) => Number(sample.lap_number) === frameLap)
    : history;
  return filtered.slice(-maxPoints);
}

function TrackRendererComponent({ trackData, mirrorX, trackDiagnostics }) {
  const canvasRef = useRef(null);
  const mapCanvasRef = useRef(null);
  const trackLayerCanvasRef = useRef(null);
  const trackLayerKeyRef = useRef('');
  const containerRef = useRef(null);
  const animationRef = useRef(null);
  const pathCacheBuildCountRef = useRef(0);
  const offscreenMetricsRef = useRef({
    recreated: 0,
    resized: 0,
  });
  const trackLayerMetricsRef = useRef({
    builds: 0,
    resized: 0,
  });
  const [cameraMode, setCameraMode] = useState('OVERVIEW');
  const [debugEnabled, setDebugEnabled] = useState(false);
  const [debugLayers, setDebugLayers] = useState({
    projection: true,
    physics: false,
    trajectory: false,
    centerline: false,
  });
  const [debugOverlayFrame, setDebugOverlayFrame] = useState(null);

  const cameraRef = useRef({
    mode: 'OVERVIEW',
    zoom: 1,
    offset: { x: 0, y: 0 },
    center: null,
    heading: 0,
    easingFactor: 0.12,
    deadzoneMeters: 1.2,
    cameraEasingEnabled: false,
    isPanning: false,
    lastMouse: { x: 0, y: 0 },
  });
  const renderMetricsRef = useRef({
    fps: 0,
    lastFrameAt: 0,
    trackPointCount: 0,
    renderedPointCount: 0,
    interpolationEnabled: true,
    pathCacheEnabled: false,
    cameraEasingEnabled: false,
    pathCacheBuildCount: 0,
    offscreenCanvasRecreatedCount: 0,
    offscreenCanvasResizeCount: 0,
    trackFetchCount: 0,
    trackPayloadBytes: 0,
    trackPollingEnabled: false,
    debugOverlaysEnabled: false,
    staticTrackLayerCacheEnabled: false,
    staticTrackLayerBuildCount: 0,
    staticTrackLayerResizeCount: 0,
    maxFrameDeltaMs: 0,
    droppedFrames: 0,
    telemetryHz: 0,
    renderHz: 0,
    lastPacketAgeMs: null,
    packetDeltaMs: null,
    responseLatencyMs: null,
    backendSampleDeltaMs: null,
    backendReadDeltaMs: null,
    interpolationBufferSize: 0,
    outOfOrderPackets: 0,
    duplicatePackets: 0,
  });
  const interpolatedCar = useInterpolatedCarState();

  const renderOptions = useMemo(() => ({
    mirrorX: resolveMirrorX(mirrorX),
  }), [mirrorX]);
  const normalizedTrack = useMemo(() => normalizeTrack(trackData), [trackData]);
  const visualTrack = useMemo(() => normalizeVisualTrack(normalizedTrack) || normalizedTrack, [normalizedTrack]);
  const fixedBounds = useMemo(() => computeTrackBounds(visualTrack), [visualTrack]);
  const trackPathCache = useMemo(() => {
    const cache = createTrackPathCache(visualTrack, { logBuild: Boolean(import.meta.env?.DEV) });
    if (cache.pathCacheEnabled) {
      pathCacheBuildCountRef.current += 1;
      cache.pathCacheBuildCount = pathCacheBuildCountRef.current;
    }
    return cache;
  }, [visualTrack]);

  useEffect(() => {
    cameraRef.current.mode = cameraMode;
    if (cameraMode === 'OVERVIEW') {
      cameraRef.current.center = null;
    }
  }, [cameraMode]);

  useEffect(() => {
    cameraRef.current.center = null;
  }, [renderOptions.mirrorX]);

  useEffect(() => {
    if (!debugEnabled) {
      setDebugOverlayFrame(null);
      return undefined;
    }
    const interval = window.setInterval(() => {
      setDebugOverlayFrame(interpolatedCar.frameRef.current);
    }, 150);
    return () => window.clearInterval(interval);
  }, [debugEnabled, interpolatedCar]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return undefined;

    const ctx = canvas.getContext('2d');
    if (!ctx) return undefined;

    const render = (timestamp) => {
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

      if (!mapCanvasRef.current) {
        mapCanvasRef.current = document.createElement('canvas');
        offscreenMetricsRef.current.recreated += 1;
      }
      const mapCanvas = mapCanvasRef.current;
      if (mapCanvas.width !== canvas.width || mapCanvas.height !== canvas.height) {
        mapCanvas.width = canvas.width;
        mapCanvas.height = canvas.height;
        offscreenMetricsRef.current.resized += 1;
      }
      const mapCtx = mapCanvas.getContext('2d');
      if (!mapCtx) {
        animationRef.current = requestAnimationFrame(render);
        return;
      }
      mapCtx.setTransform(1, 0, 0, 1, 0, 0);
      mapCtx.clearRect(0, 0, mapCanvas.width, mapCanvas.height);
      mapCtx.setTransform(dpr, 0, 0, dpr, 0, 0);

      const { latestFrame: liveFrame, history: liveHistory } = useTelemetryStore.getState();
      const renderFrame = interpolatedCar.frameRef.current || liveFrame;
      const liveDebugHistory = debugEnabled && debugLayers.trajectory
        ? selectDebugTrajectory(liveHistory, renderFrame)
        : [];
      const renderBounds = visualTrack ? fixedBounds : computeTrackBounds(null, liveDebugHistory, renderFrame);
      const metrics = renderMetricsRef.current;
      if (metrics.lastFrameAt) {
        const frameDeltaMs = Math.max(timestamp - metrics.lastFrameAt, 1);
        const instantFps = 1000 / frameDeltaMs;
        metrics.fps = metrics.fps ? metrics.fps * 0.9 + instantFps * 0.1 : instantFps;
        metrics.renderHz = metrics.fps;
        metrics.maxFrameDeltaMs = Math.max(metrics.maxFrameDeltaMs || 0, frameDeltaMs);
        if (frameDeltaMs > 50) metrics.droppedFrames = (metrics.droppedFrames || 0) + 1;
      }
      metrics.lastFrameAt = timestamp;
      const telemetryPerf = useTelemetryStore.getState().telemetryPerf || {};
      metrics.trackPointCount = visualTrack?.total_points || visualTrack?.centerline?.x?.length || 0;
      metrics.renderedPointCount = trackPathCache?.renderedPointCount || 0;
      metrics.pathCacheEnabled = Boolean(trackPathCache?.pathCacheEnabled);
      metrics.pathCacheBuildCount = pathCacheBuildCountRef.current;
      metrics.offscreenCanvasRecreatedCount = offscreenMetricsRef.current.recreated;
      metrics.offscreenCanvasResizeCount = offscreenMetricsRef.current.resized;
      metrics.interpolationEnabled = Boolean(interpolatedCar.interpolationEnabled);
      metrics.cameraEasingEnabled = Boolean(cameraRef.current.cameraEasingEnabled);
      metrics.mirrorX = renderOptions.mirrorX;
      metrics.mirrorMode = mirrorMode(renderOptions);
      metrics.visualGeometryEnabled = Boolean(normalizedTrack?.visualGeometry);
      metrics.debugOverlaysEnabled = debugEnabled;
      metrics.debugProjectionEnabled = Boolean(debugEnabled && debugLayers.projection);
      metrics.debugPhysicsEnabled = Boolean(debugEnabled && debugLayers.physics);
      metrics.debugTrajectoryEnabled = Boolean(debugEnabled && debugLayers.trajectory);
      metrics.debugCenterlineEnabled = Boolean(debugEnabled && debugLayers.centerline);
      metrics.trackFetchCount = trackDiagnostics?.trackFetchCount || 0;
      metrics.trackPayloadBytes = trackDiagnostics?.payloadBytes || 0;
      metrics.trackPollingEnabled = Boolean(trackDiagnostics?.trackPollingEnabled);
      metrics.staticTrackLayerCacheEnabled = Boolean(visualTrack && cameraRef.current.mode === 'OVERVIEW');
      metrics.staticTrackLayerBuildCount = trackLayerMetricsRef.current.builds;
      metrics.staticTrackLayerResizeCount = trackLayerMetricsRef.current.resized;
      metrics.telemetryHz = telemetryPerf.telemetryHz || 0;
      metrics.packetDeltaMs = telemetryPerf.packetDeltaMs;
      metrics.lastPacketAgeMs = telemetryPerf.lastPacketAgeMs;
      metrics.responseLatencyMs = telemetryPerf.responseLatencyMs;
      metrics.backendSampleDeltaMs = telemetryPerf.backendSampleDeltaMs;
      metrics.backendReadDeltaMs = telemetryPerf.backendReadDeltaMs;
      metrics.outOfOrderPackets = telemetryPerf.outOfOrderPackets || 0;
      metrics.duplicatePackets = telemetryPerf.duplicatePackets || 0;
      metrics.interpolationBufferSize = interpolatedCar.metricsRef.current.bufferSize || 0;

      let scale = 1;
      const useStaticTrackLayer = Boolean(visualTrack) && cameraRef.current.mode === 'OVERVIEW';
      if (useStaticTrackLayer) {
        if (!trackLayerCanvasRef.current) {
          trackLayerCanvasRef.current = document.createElement('canvas');
        }
        const trackLayerCanvas = trackLayerCanvasRef.current;
        if (trackLayerCanvas.width !== canvas.width || trackLayerCanvas.height !== canvas.height) {
          trackLayerCanvas.width = canvas.width;
          trackLayerCanvas.height = canvas.height;
          trackLayerMetricsRef.current.resized += 1;
          trackLayerKeyRef.current = '';
        }

        const staticTrackKey = [
          canvas.width,
          canvas.height,
          dpr.toFixed(2),
          cameraRef.current.zoom.toFixed(4),
          cameraRef.current.offset.x.toFixed(1),
          cameraRef.current.offset.y.toFixed(1),
          debugLayers.physics ? 'physics' : 'physics-off',
          debugLayers.centerline ? 'centerline' : 'centerline-off',
          trackPathCache?.pathCacheBuildCount || 0,
          visualTrack?.cachePath || visualTrack?.trackName || '',
        ].join('|');

        if (trackLayerKeyRef.current !== staticTrackKey) {
          const trackLayerCtx = trackLayerCanvas.getContext('2d');
          if (trackLayerCtx) {
            trackLayerCtx.setTransform(1, 0, 0, 1, 0, 0);
            trackLayerCtx.clearRect(0, 0, trackLayerCanvas.width, trackLayerCanvas.height);
            trackLayerCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
            trackLayerCtx.save();
            const layerScale = applyCameraTransform(trackLayerCtx, rect.width, rect.height, renderBounds, cameraRef.current, null);
            drawTrackSurface(trackLayerCtx, visualTrack, renderBounds, layerScale, trackPathCache, {
              showCenterline: debugEnabled && debugLayers.centerline,
              logPathCacheReuse: Boolean(import.meta.env?.DEV),
            });
            if (debugEnabled && debugLayers.physics && normalizedTrack?.visualGeometry) drawPhysicsEdges(trackLayerCtx, normalizedTrack, layerScale);
            trackLayerCtx.restore();
            trackLayerMetricsRef.current.builds += 1;
            metrics.staticTrackLayerBuildCount = trackLayerMetricsRef.current.builds;
            metrics.staticTrackLayerResizeCount = trackLayerMetricsRef.current.resized;
            trackLayerKeyRef.current = staticTrackKey;
          }
        }

        mapCtx.drawImage(trackLayerCanvas, 0, 0);

        mapCtx.save();
        scale = applyCameraTransform(mapCtx, rect.width, rect.height, renderBounds, cameraRef.current, renderFrame);
        metrics.cameraEasingEnabled = Boolean(cameraRef.current.cameraEasingEnabled);
        if (debugEnabled && debugLayers.trajectory) drawTrajectory(mapCtx, liveDebugHistory, scale, { maxSegmentDistance: 35 });
        if (debugEnabled && debugLayers.projection && normalizedTrack && renderFrame) drawProjectionDebug(mapCtx, renderFrame, scale);
        if (renderFrame) drawCar(mapCtx, renderFrame, scale);
        mapCtx.restore();
      } else {
        mapCtx.save();
        scale = applyCameraTransform(mapCtx, rect.width, rect.height, renderBounds, cameraRef.current, renderFrame);
        metrics.cameraEasingEnabled = Boolean(cameraRef.current.cameraEasingEnabled);

        if (visualTrack) {
          drawTrackSurface(mapCtx, visualTrack, renderBounds, scale, trackPathCache, {
            showCenterline: debugEnabled && debugLayers.centerline,
            logPathCacheReuse: Boolean(import.meta.env?.DEV),
          });
        }
        if (debugEnabled && debugLayers.physics && normalizedTrack?.visualGeometry) drawPhysicsEdges(mapCtx, normalizedTrack, scale);
        if (debugEnabled && debugLayers.trajectory) drawTrajectory(mapCtx, liveDebugHistory, scale, { maxSegmentDistance: 35 });
        if (debugEnabled && debugLayers.projection && normalizedTrack && renderFrame) drawProjectionDebug(mapCtx, renderFrame, scale);
        if (renderFrame) drawCar(mapCtx, renderFrame, scale);
        mapCtx.restore();
      }

      ctx.save();
      ctx.resetTransform();
      ctx.imageSmoothingEnabled = true;
      if (renderOptions.mirrorX) {
        ctx.translate(mapCanvas.width, 0);
        ctx.scale(-1, 1);
      }
      ctx.drawImage(mapCanvas, 0, 0);
      ctx.restore();

      drawHud(ctx, rect.width, rect.height, visualTrack, renderFrame, cameraRef.current, debugEnabled, metrics);
      animationRef.current = requestAnimationFrame(render);
    };

    animationRef.current = requestAnimationFrame(render);
    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
    };
  }, [
    debugEnabled,
    debugLayers,
    fixedBounds,
    interpolatedCar,
    normalizedTrack,
    renderOptions,
    trackDiagnostics,
    trackPathCache,
    visualTrack,
  ]);

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
        <div className="panel px-1.5 py-1 flex gap-1">
          <button
            onClick={() => setDebugEnabled((value) => !value)}
            className={`px-2 py-0.5 num text-[7px] uppercase rounded-sm transition-all ${
              debugEnabled ? 'bg-amber-500/15 text-amber-300 border border-amber-500/30' : 'text-slate-600 hover:text-slate-400'
            }`}
          >
            Debug
          </button>
        </div>
        {debugEnabled && (
          <div className="panel px-1.5 py-1 grid grid-cols-2 gap-1">
            {[
              ['projection', 'Proj'],
              ['physics', 'Phys'],
              ['trajectory', 'Trail'],
              ['centerline', 'Ctr'],
            ].map(([key, label]) => (
              <button
                key={key}
                onClick={() => setDebugLayers((layers) => ({ ...layers, [key]: !layers[key] }))}
                className={`px-2 py-0.5 num text-[7px] uppercase rounded-sm transition-all ${
                  debugLayers[key] ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30' : 'text-slate-600 hover:text-slate-400'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        )}
      </div>

      {debugEnabled && debugLayers.projection && <ProjectionDebugOverlay frame={debugOverlayFrame} renderOptions={renderOptions} />}
    </div>
  );
}

export const TrackRenderer = React.memo(TrackRendererComponent);
export default TrackRenderer;
