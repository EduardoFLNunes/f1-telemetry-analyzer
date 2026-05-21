import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTelemetryStore } from '../../store/useTelemetryStore';
import { useInterpolatedCarState } from '../../hooks/useInterpolatedCarState';
import { usePitLaneDebugData } from '../../hooks/usePitLaneDebugData';
import { drawCar, drawTrajectory } from './CarRenderer.jsx';
import { applyCameraTransform, computeTrackBounds } from './CameraController.jsx';
import {
  createTrackPathCache,
  drawHud,
  drawPhysicsEdges,
  drawProjectionDebug,
  drawTrackSurface,
} from './OverlayRenderer.jsx';
import { createPitLanePathCache, drawPitAreaCarPath, drawPitLaneOverlay } from './PitLaneOverlay.jsx';
import { PitLaneDebugPanel } from './PitLaneDebugPanel.jsx';
import { classifyPointInTrackArea } from './PitAreaClassifier.js';
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
  const ribbon = visual?.visualRibbonGeometry;
  return {
    ...trackData,
    source: visual.source || trackData.source,
    visualRenderMode: visual.visualRenderMode || visual.metadata?.visualRenderMode || trackData.visualRenderMode || 'polygon',
    visualRibbonGeometry: ribbon || null,
    ribbonWidthMeters: visual.ribbonWidthMeters || ribbon?.ribbonWidthMeters || ribbon?.width,
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

function normalizePhysicsDisplayTrack(trackData) {
  const display = trackData?.physicsDisplayGeometry;
  if (!display || !display.leftEdge || !display.rightEdge) return null;
  return {
    ...trackData,
    source: display.source || trackData.source,
    visualRenderMode: 'polygon',
    centerline: {
      x: display.centerline.map((p) => p.x),
      y: display.centerline.map((p) => p.y),
    },
    left_edge: {
      x: display.leftEdge.map((p) => p.x),
      y: display.leftEdge.map((p) => p.y),
    },
    right_edge: {
      x: display.rightEdge.map((p) => p.x),
      y: display.rightEdge.map((p) => p.y),
    },
    localWidth: display.width,
    visualGeometryEnabled: true,
    physicsDisplayEnabled: true,
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
  const pitPathRecordingRef = useRef({
    recording: false,
    samples: [],
    lastRecordedAt: 0,
  });
  const [cameraMode, setCameraMode] = useState('OVERVIEW');
  const [geometryMode, setGeometryMode] = useState('RIBBON');
  const [debugEnabled, setDebugEnabled] = useState(false);
  const [debugLayers, setDebugLayers] = useState({
    projection: true,
    physics: false,
    trajectory: false,
    centerline: false,
    pitlane: false,
  });
  const [pitLaneOptions, setPitLaneOptions] = useState({
    showMainTrack: true,
    showPitArea: true,
    showPitCorridorV2: true,
    showEntryAccess: true,
    showExitAccess: true,
    showEntryExit: true,
    showAiReferences: true,
    showCarPath: false,
    showSurface: false,
    showLabels: true,
    showAdvancedLegacy: false,
  });
  const [pitPathRecording, setPitPathRecording] = useState(false);
  const [recordedPitPathCount, setRecordedPitPathCount] = useState(0);
  const [pitPathExportStatus, setPitPathExportStatus] = useState('');
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
  const pitLaneEnabled = Boolean(debugEnabled && debugLayers.pitlane);
  const pitLaneDebugState = usePitLaneDebugData(pitLaneEnabled);
  const normalizedTrack = useMemo(() => normalizeTrack(trackData), [trackData]);
  const visualTrack = useMemo(() => normalizeVisualTrack(normalizedTrack) || normalizedTrack, [normalizedTrack]);
  const physicsDisplayTrack = useMemo(() => normalizePhysicsDisplayTrack(normalizedTrack) || normalizedTrack, [normalizedTrack]);
  
  const fixedBounds = useMemo(() => computeTrackBounds(visualTrack), [visualTrack]);

  const trackPathCache = useMemo(() => {
    const cache = createTrackPathCache(visualTrack, { logBuild: Boolean(import.meta.env?.DEV) });
    if (cache.pathCacheEnabled) {
      pathCacheBuildCountRef.current += 1;
      cache.pathCacheBuildCount = pathCacheBuildCountRef.current;
    }
    return cache;
  }, [visualTrack]);

  const rawPhysicsPathCache = useMemo(() => {
    const cache = createTrackPathCache(normalizedTrack, { logBuild: Boolean(import.meta.env?.DEV) });
    return cache;
  }, [normalizedTrack]);

  const physicsDisplayPathCache = useMemo(() => {
    const cache = createTrackPathCache(physicsDisplayTrack, { logBuild: Boolean(import.meta.env?.DEV) });
    return cache;
  }, [physicsDisplayTrack]);

  const pitLanePathCache = useMemo(
    () => createPitLanePathCache(pitLaneDebugState.data),
    [pitLaneDebugState.data],
  );
  const pitAreaClassification = useMemo(
    () => classifyPointInTrackArea(debugOverlayFrame?.mapPosition, pitLaneDebugState.data),
    [debugOverlayFrame, pitLaneDebugState.data],
  );

  useEffect(() => {
    pitPathRecordingRef.current.recording = pitPathRecording;
    if (pitPathRecording) {
      pitPathRecordingRef.current.samples = [];
      pitPathRecordingRef.current.lastRecordedAt = 0;
      setRecordedPitPathCount(0);
      setPitPathExportStatus('recording started');
    }
  }, [pitPathRecording]);

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
      const pitLaneDriverHistory = pitLaneEnabled && pitLaneOptions.showCarPath
        ? selectDebugTrajectory(liveHistory, renderFrame, 900)
        : [];
      if (pitLaneEnabled && pitPathRecordingRef.current.recording && renderFrame?.mapPosition) {
        const now = Date.now();
        if (now - pitPathRecordingRef.current.lastRecordedAt >= 100) {
          const classification = classifyPointInTrackArea(renderFrame.mapPosition, pitLaneDebugState.data);
          pitPathRecordingRef.current.samples.push({
            timestamp: now,
            lap: renderFrame.lap_number,
            mapPosition: {
              x: Number(renderFrame.mapPosition.x),
              y: Number(renderFrame.mapPosition.y),
            },
            areaClassification: classification.area,
            distanceToExitAccess: classification.distanceToExitAccess,
            distanceToPitCorridor: classification.distanceToPitCorridor,
            distanceToMainTrack: classification.distanceToMainTrack,
            confidence: classification.confidence,
          });
          if (pitPathRecordingRef.current.samples.length > 6000) {
            pitPathRecordingRef.current.samples = pitPathRecordingRef.current.samples.slice(-6000);
          }
          pitPathRecordingRef.current.lastRecordedAt = now;
          setRecordedPitPathCount(pitPathRecordingRef.current.samples.length);
        }
      }
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
      metrics.debugPitLaneEnabled = pitLaneEnabled;
      metrics.pitLanePathCacheEnabled = Boolean(pitLanePathCache?.pathCacheEnabled);
      metrics.visualRenderMode = visualTrack?.visualRenderMode || 'polygon';
      metrics.ribbonWidthMeters = visualTrack?.ribbonWidthMeters;
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

      let activeTrack = visualTrack;
      let activeCache = trackPathCache;

      if (geometryMode === 'PHYSICS') {
        activeTrack = physicsDisplayTrack;
        activeCache = physicsDisplayPathCache;
      } else if (geometryMode === 'RAW_PHYSICS') {
        activeTrack = normalizedTrack;
        activeCache = rawPhysicsPathCache;
      }

      let scale = 1;
      const useStaticTrackLayer = Boolean(activeTrack) && cameraRef.current.mode === 'OVERVIEW';
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
          geometryMode,
          activeCache?.pathCacheBuildCount || 0,
          activeTrack?.visualRenderMode || 'polygon',
          activeTrack?.ribbonWidthMeters || 0,
          activeTrack?.cachePath || activeTrack?.trackName || '',
          pitLaneEnabled ? 'pitlane-on' : 'pitlane-off',
          pitLaneOptions.showMainTrack ? 'pit-main' : 'pit-main-off',
          pitLaneOptions.showPitArea ? 'pit-area' : 'pit-area-off',
          pitLaneOptions.showPitCorridorV2 ? 'pit-corridor-v2' : 'pit-corridor-v2-off',
          pitLaneOptions.showEntryAccess ? 'pit-entry-access' : 'pit-entry-access-off',
          pitLaneOptions.showExitAccess ? 'pit-exit-access' : 'pit-exit-access-off',
          pitLaneOptions.showEntryExit ? 'pit-entry-exit' : 'pit-entry-exit-off',
          pitLaneOptions.showAiReferences ? 'pit-ai-references' : 'pit-ai-references-off',
          pitLaneOptions.showCarPath ? 'pit-car-path' : 'pit-car-path-off',
          pitLaneOptions.showSurface ? 'pit-surface' : 'pit-surface-off',
          pitLaneOptions.showLabels ? 'pit-labels' : 'pit-labels-off',
          pitLaneOptions.showAdvancedLegacy ? 'pit-legacy' : 'pit-legacy-off',
          renderOptions.mirrorX ? 'screen-mirror-x' : 'screen-mirror-off',
          pitLanePathCache?.cacheKey || 'pitlane-none',
        ].join('|');

        if (trackLayerKeyRef.current !== staticTrackKey) {
          const trackLayerCtx = trackLayerCanvas.getContext('2d');
          if (trackLayerCtx) {
            trackLayerCtx.setTransform(1, 0, 0, 1, 0, 0);
            trackLayerCtx.clearRect(0, 0, trackLayerCanvas.width, trackLayerCanvas.height);
            trackLayerCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
            trackLayerCtx.save();
            const layerScale = applyCameraTransform(trackLayerCtx, rect.width, rect.height, renderBounds, cameraRef.current, null);
            drawTrackSurface(trackLayerCtx, activeTrack, renderBounds, layerScale, activeCache, {
              showCenterline: debugEnabled && debugLayers.centerline,
              logPathCacheReuse: Boolean(import.meta.env?.DEV),
            });
            if (geometryMode === 'OVERLAY' || (debugEnabled && debugLayers.physics)) {
              drawPhysicsEdges(trackLayerCtx, normalizedTrack, layerScale);
            }
            if (pitLaneEnabled && pitLaneDebugState.data) {
              drawPitLaneOverlay(trackLayerCtx, pitLaneDebugState.data, layerScale, pitLanePathCache, {
                ...pitLaneOptions,
                screenMirrorX: renderOptions.mirrorX,
              });
            }
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
        if (pitLaneEnabled && pitLaneDebugState.data && pitLaneOptions.showCarPath) {
          drawPitAreaCarPath(mapCtx, pitLaneDebugState.data, pitLaneDriverHistory, scale, pitLaneOptions);
        }
        if (debugEnabled && debugLayers.projection && normalizedTrack && renderFrame) drawProjectionDebug(mapCtx, renderFrame, scale);
        if (renderFrame) drawCar(mapCtx, renderFrame, scale);
        mapCtx.restore();
      } else {
        mapCtx.save();
        scale = applyCameraTransform(mapCtx, rect.width, rect.height, renderBounds, cameraRef.current, renderFrame);
        metrics.cameraEasingEnabled = Boolean(cameraRef.current.cameraEasingEnabled);

        if (activeTrack) {
          drawTrackSurface(mapCtx, activeTrack, renderBounds, scale, activeCache, {
            showCenterline: debugEnabled && debugLayers.centerline,
            logPathCacheReuse: Boolean(import.meta.env?.DEV),
          });
        }
        if (geometryMode === 'OVERLAY' || (debugEnabled && debugLayers.physics)) {
          drawPhysicsEdges(mapCtx, normalizedTrack, scale);
        }
        if (debugEnabled && debugLayers.trajectory) drawTrajectory(mapCtx, liveDebugHistory, scale, { maxSegmentDistance: 35 });
        if (pitLaneEnabled && pitLaneDebugState.data) {
          drawPitLaneOverlay(mapCtx, pitLaneDebugState.data, scale, pitLanePathCache, {
            ...pitLaneOptions,
            screenMirrorX: renderOptions.mirrorX,
          });
        }
        if (pitLaneEnabled && pitLaneDebugState.data && pitLaneOptions.showCarPath) {
          drawPitAreaCarPath(mapCtx, pitLaneDebugState.data, pitLaneDriverHistory, scale, pitLaneOptions);
        }
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

      metrics.geometryMode = geometryMode;
      drawHud(ctx, rect.width, rect.height, activeTrack, renderFrame, cameraRef.current, debugEnabled, metrics);
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
    physicsDisplayTrack,
    geometryMode,
    rawPhysicsPathCache,
    physicsDisplayPathCache,
    pitLaneEnabled,
    pitLaneDebugState.data,
    pitLaneOptions,
    pitLanePathCache,
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

  const togglePitLaneOption = useCallback((key) => {
    setPitLaneOptions((options) => ({ ...options, [key]: !options[key] }));
  }, []);

  const togglePitPathRecording = useCallback(() => {
    setPitPathRecording((value) => !value);
  }, []);

  const exportPitPathRecording = useCallback(async () => {
    const samples = pitPathRecordingRef.current.samples;
    if (!samples.length) {
      setPitPathExportStatus('no samples recorded');
      return;
    }
    setPitPathExportStatus('exporting...');
    try {
      const response = await fetch(`http://${window.location.hostname}:8000/api/debug/pitlane/recorded-car-path`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source: 'frontend_debug_pit_recording', samples }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      const exitSamples = payload.recordedPath?.samplesInsideExitAccess ?? 0;
      const validated = Boolean(payload.recordedPath?.exitAccessValidated);
      setPitPathExportStatus(`exported ${samples.length} samples, exit=${exitSamples}, validated=${validated}`);
      pitLaneDebugState.reload();
    } catch (error) {
      setPitPathExportStatus(`export failed: ${error instanceof Error ? error.message : String(error)}`);
    }
  }, [pitLaneDebugState]);

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
          {[
            ['RIBBON', 'Ribbon'],
            ['PHYSICS', 'Phys'],
            ['RAW_PHYSICS', 'Raw Phys'],
            ['OVERLAY', 'Overlay'],
          ].map(([mode, label]) => (
            <button
              key={mode}
              onClick={() => setGeometryMode(mode)}
              className={`px-2 py-0.5 num text-[7px] uppercase rounded-sm transition-all ${
                geometryMode === mode ? 'bg-indigo-500/15 text-indigo-300 border border-indigo-500/30' : 'text-slate-600 hover:text-slate-400'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
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
              ['pitlane', 'Pit'],
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
      {debugEnabled && debugLayers.pitlane && (
        <PitLaneDebugPanel
          state={pitLaneDebugState}
          options={pitLaneOptions}
          onToggle={togglePitLaneOption}
          classification={pitAreaClassification}
          recording={pitPathRecording}
          recordedCount={recordedPitPathCount || pitPathRecordingRef.current.samples.length}
          exportStatus={pitPathExportStatus}
          onToggleRecording={togglePitPathRecording}
          onExportRecording={exportPitPathRecording}
        />
      )}
    </div>
  );
}

export const TrackRenderer = React.memo(TrackRendererComponent);
export default TrackRenderer;
