import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTelemetryStore } from '../../store/useTelemetryStore';
import { useRenderCounter } from '../../hooks/useRenderCounter';
import { api } from '../../api/client';
import { drawCar, drawOpponentCar } from './CarRenderer.jsx';
import { applyCameraTransform, computeTrackBounds } from './CameraController.jsx';
import { drawHud, drawTrackSurface } from './OverlayRenderer.jsx';
import {
  drawPreparedRacingLineOverlay,
  drawRacingLineLegend,
  prepareRacingLineOverlay,
  racingLineModeLabel,
  RACING_LINE_OVERLAY_MODES,
} from './RacingLineOverlay.jsx';

const MAP_RENDER_FRAME_MS = 1000 / 60;
const MAP_RENDER_FRAME_MS_BY_MODE = {
  QUALITY: 1000 / 60,
  BALANCED: 1000 / 60,
  PERFORMANCE: 1000 / 60,
};
const RACING_LINE_POLL_MS = 6000;
const HISTORY_WINDOW_BY_MODE = {
  QUALITY: 1800,
  BALANCED: 1200,
  PERFORMANCE: 600,
};
const PERFORMANCE_MODES = ['QUALITY', 'BALANCED', 'PERFORMANCE'];

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

function isFiniteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value);
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function positionFromSpline(trackData, splinePosition) {
  if (!trackData || !isFiniteNumber(splinePosition)) return null;

  const center = trackData.centerline || {};
  const xs = center.x || [];
  const ys = center.y || [];
  if (!xs.length || xs.length !== ys.length) return null;

  const p = Math.max(0, Math.min(1, splinePosition));
  const spline = Array.isArray(center.spline_t) ? center.spline_t : null;

  if (spline && spline.length === xs.length && spline.length > 1) {
    for (let i = 1; i < spline.length; i += 1) {
      const prevP = Number(spline[i - 1]);
      const nextP = Number(spline[i]);
      if (!Number.isFinite(prevP) || !Number.isFinite(nextP)) continue;
      if (p <= nextP) {
        const t = nextP === prevP ? 0 : Math.max(0, Math.min(1, (p - prevP) / (nextP - prevP)));
        return {
          x: lerp(xs[i - 1], xs[i], t),
          y: lerp(ys[i - 1], ys[i], t),
        };
      }
    }
  }

  const idx = p * (xs.length - 1);
  const lo = Math.floor(idx);
  const hi = Math.min(xs.length - 1, lo + 1);
  const t = idx - lo;
  return {
    x: lerp(xs[lo], xs[hi], t),
    y: lerp(ys[lo], ys[hi], t),
  };
}

function resolveOpponentRenderState(opponent, trackData) {
  const mapPosition = opponent?.mapPosition;
  if (mapPosition && isFiniteNumber(mapPosition.x) && isFiniteNumber(mapPosition.y)) {
    return opponent;
  }

  const fallbackPosition = positionFromSpline(trackData, opponent?.splinePosition);
  if (!fallbackPosition) return null;
  return {
    ...opponent,
    mapPosition: fallbackPosition,
  };
}

function formatOpponentNumber(value, digits = 0) {
  return isFiniteNumber(value) ? value.toFixed(digits) : '--';
}

function opponentDisplayName(opponent) {
  const name = typeof opponent?.driverName === 'string' ? opponent.driverName.trim() : '';
  return name || 'Unknown';
}

function opponentSplinePercent(opponent) {
  return isFiniteNumber(opponent?.splinePosition) ? opponent.splinePosition * 100 : null;
}

function isStaleOpponent(opponent, staleAfterSeconds) {
  if (opponent?.status === 'stale') return true;
  if (!isFiniteNumber(opponent?.lastSeenTimestamp) || !isFiniteNumber(staleAfterSeconds)) return false;
  return (Date.now() / 1000) - opponent.lastSeenTimestamp > staleAfterSeconds;
}

function withEstimatedHeadings(opponents, motionCache) {
  return opponents.map((opponent) => {
    const position = opponent?.mapPosition;
    if (!position || !isFiniteNumber(position.x) || !isFiniteNumber(position.y)) return opponent;

    const previous = motionCache.get(opponent.carId);
    let estimatedHeading = previous?.estimatedHeading;
    if (previous && isFiniteNumber(previous.x) && isFiniteNumber(previous.y)) {
      const dx = position.x - previous.x;
      const dy = position.y - previous.y;
      if (Math.hypot(dx, dy) > 0.15) {
        estimatedHeading = Math.atan2(dy, dx) + Math.PI / 2;
      }
    }
    motionCache.set(opponent.carId, {
      x: position.x,
      y: position.y,
      estimatedHeading,
    });

    return isFiniteNumber(estimatedHeading)
      ? { ...opponent, estimatedHeading }
      : opponent;
  });
}

function worldToScreen(point, width, height, bounds, camera, carFrame) {
  if (!point || !isFiniteNumber(point.x) || !isFiniteNumber(point.y)) return null;

  if (camera.mode === 'FOLLOW' && carFrame) {
    const carPosition = carFrame.mapPosition || { x: carFrame.x, y: carFrame.z };
    if (!carPosition || !isFiniteNumber(carPosition.x) || !isFiniteNumber(carPosition.y)) return null;
    const scale = (height / 90) * camera.zoom;
    const angle = -(carFrame.heading || 0) + Math.PI / 2;
    const dx = point.x - carPosition.x;
    const dy = point.y - carPosition.y;
    const rx = dx * Math.cos(angle) - dy * Math.sin(angle);
    const ry = dx * Math.sin(angle) + dy * Math.cos(angle);
    return { x: width / 2 + rx * scale, y: height * 0.68 + ry * scale, scale };
  }

  const scale = Math.min(width / bounds.w, height / bounds.h) * 0.84 * camera.zoom;
  return {
    x: width / 2 + camera.offset.x + (point.x - bounds.cx) * scale,
    y: height / 2 + camera.offset.y + (point.y - bounds.cy) * scale,
    scale,
  };
}

function labelText(opponent, mode) {
  const carId = Number.isFinite(opponent?.carId) ? `#${opponent.carId}` : '#?';
  if (mode === 'id') return carId;
  const name = opponentDisplayName(opponent);
  const compactName = name.length > 13 ? `${name.slice(0, 12)}...` : name;
  const speed = isFiniteNumber(opponent?.speedKmh) ? `${Math.round(opponent.speedKmh)} km/h` : '-- km/h';
  const spline = isFiniteNumber(opponent?.splinePosition) ? `p${(opponent.splinePosition * 100).toFixed(1)}%` : 'p--';
  return `${carId} ${compactName} ${speed} ${spline}`;
}

function labelRect(screen, mode, text) {
  if (mode === 'none') return null;
  const width = mode === 'id' ? Math.max(22, text.length * 7 + 8) : Math.min(174, text.length * 6.3 + 12);
  const height = mode === 'id' ? 15 : 18;
  const x = mode === 'id' ? screen.x - width / 2 : screen.x + 10;
  const y = mode === 'id' ? screen.y - 25 : screen.y - 28;
  return { x, y, width, height };
}

function intersects(a, b, padding = 3) {
  return !(
    a.x + a.width + padding < b.x ||
    b.x + b.width + padding < a.x ||
    a.y + a.height + padding < b.y ||
    b.y + b.height + padding < a.y
  );
}

function buildLabelModes(screenOpponents, scale) {
  const baseMode = scale < 0.42 ? 'none' : (scale < 1.05 ? 'id' : 'full');
  const occupied = [];
  const modes = new Map();

  screenOpponents.forEach(({ opponent, screen }) => {
    let mode = baseMode;
    if (mode === 'none') {
      modes.set(opponent.carId, 'none');
      return;
    }

    let text = labelText(opponent, mode);
    let rect = labelRect(screen, mode, text);
    if (rect && occupied.some((box) => intersects(box, rect))) {
      mode = mode === 'full' ? 'id' : 'none';
      text = labelText(opponent, mode);
      rect = labelRect(screen, mode, text);
    }
    if (rect && occupied.some((box) => intersects(box, rect))) {
      mode = 'none';
      rect = null;
    }
    if (rect) occupied.push(rect);
    modes.set(opponent.carId, mode);
  });

  return modes;
}

function findOpponentHit(screenOpponents, x, y) {
  let best = null;
  screenOpponents.forEach((entry) => {
    const distance = Math.hypot(entry.screen.x - x, entry.screen.y - y);
    if (distance <= 16 && (!best || distance < best.distance)) {
      best = { ...entry, distance };
    }
  });
  return best;
}

export const TrackRenderer = React.memo(function TrackRenderer({ trackData }) {
  useRenderCounter('TrackRenderer');
  const performanceMode = useTelemetryStore((state) => state.performanceMode);
  const setPerformanceMode = useTelemetryStore((state) => state.setPerformanceMode);
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const animationRef = useRef(null);
  const lastCanvasRenderRef = useRef(0);
  const opponentMotionRef = useRef(new Map());
  const screenOpponentsRef = useRef([]);
  const racingLineOverlayRef = useRef(null);
  const [cameraMode, setCameraMode] = useState('OVERVIEW');
  const [showRacingLine, setShowRacingLine] = useState(true);
  const [racingLineMode, setRacingLineMode] = useState('LINE_ONLY');
  const showRacingLineRef = useRef(true);
  const racingLineModeRef = useRef('LINE_ONLY');
  const performanceModeRef = useRef('BALANCED');
  const [hoveredOpponent, setHoveredOpponent] = useState(null);
  const [selectedOpponent, setSelectedOpponent] = useState(null);
  const hoveredOpponentRef = useRef(null);
  const selectedOpponentRef = useRef(null);
  const perfRef = useRef({
    frames: 0,
    renderMs: 0,
    lastAt: performance.now(),
    lastWsMessages: 0,
    lastTelemetryMessages: 0,
    lastOpponentsMessages: 0,
    lastTelemetryStoreUpdates: 0,
    lastOpponentsStoreUpdates: 0,
    lastTraceFrames: 0,
    lastTraceRenderMs: 0,
    lastTelemetryDropped: 0,
    lastOpponentsDropped: 0,
    lastRacingLineOverlayMs: 0,
    lastHttpRequests: 0,
    lastHttpDurationMs: 0,
    frameDeltas: [],
    previousFrameTime: 0,
  });
  const [opponentsPanelOpen, setOpponentsPanelOpen] = useState(true);
  const [mapSize, setMapSize] = useState({ width: 0, height: 0 });
  const [panelOpponents, setPanelOpponents] = useState([]);
  const [panelOpponentsMeta, setPanelOpponentsMeta] = useState({
    source: 'opponents_collector',
    count: 0,
    track: null,
    sessionTime: null,
    lastUpdateTimestamp: null,
    staleAfterSeconds: null,
  });
  const [showPerf, setShowPerf] = useState(false);
  const [perfStats, setPerfStats] = useState({
    fps: 0,
    avgRenderMs: 0,
    opponentsRendered: 0,
    wsHz: 0,
    telemetryHz: 0,
    opponentsHz: 0,
    telemetryStoreHz: 0,
    opponentsStoreHz: 0,
    traceFps: 0,
    avgTraceRenderMs: 0,
    telemetryDroppedHz: 0,
    opponentsDroppedHz: 0,
    racingLineOverlayMs: 0,
    httpHz: 0,
    httpAvgMs: 0,
    currentLapSamples: 0,
    previousLapSamples: 0,
    dashboardRps: 0,
    trackRendererRps: 0,
    tracesRps: 0,
    comparisonRps: 0,
    ggDiagramRps: 0,
    linePanelRps: 0,
    hiddenPanelRps: 0,
    p95FrameMs: 0,
    graphPoints: 0,
    traceCacheEntries: 0,
    liveTrajectoryPoints: 0,
    completedLapsHistory: 0,
    racingLineVisualPoints: 0,
    opponentSamples: 0,
    telemetryPayloadKb: 0,
    racingLinePayloadKb: 0,
    memoryEstimateMb: 0,
    performanceMode: 'BALANCED',
  });

  const cameraRef = useRef({
    mode: 'OVERVIEW',
    zoom: 1,
    offset: { x: 0, y: 0 },
    isPanning: false,
    lastMouse: { x: 0, y: 0 },
  });

  const normalizedTrack = useMemo(() => normalizeTrack(trackData), [trackData]);
  const bounds = useMemo(() => computeTrackBounds(normalizedTrack), [normalizedTrack]);
  const visibleOpponents = useMemo(
    () => panelOpponents
      .map((opponent) => resolveOpponentRenderState(opponent, normalizedTrack))
      .filter(Boolean),
    [panelOpponents, normalizedTrack],
  );
  const sortedOpponents = useMemo(
    () => [...visibleOpponents].sort((a, b) => {
      const ap = opponentSplinePercent(a);
      const bp = opponentSplinePercent(b);
      if (isFiniteNumber(ap) && isFiniteNumber(bp)) return ap - bp;
      return (a.carId ?? 0) - (b.carId ?? 0);
    }),
    [visibleOpponents],
  );

  useEffect(() => {
    cameraRef.current.mode = cameraMode;
  }, [cameraMode]);

  useEffect(() => {
    showRacingLineRef.current = showRacingLine;
  }, [showRacingLine]);

  useEffect(() => {
    racingLineModeRef.current = racingLineMode;
  }, [racingLineMode]);

  useEffect(() => {
    performanceModeRef.current = performanceMode;
    if (performanceMode === 'PERFORMANCE' && racingLineModeRef.current !== 'LINE_ONLY') {
      setRacingLineMode('LINE_ONLY');
    }
  }, [performanceMode]);

  useEffect(() => {
    if (!showRacingLine) {
      racingLineOverlayRef.current = null;
      return undefined;
    }

    let cancelled = false;
    const loadRacingLine = async () => {
      try {
        const needsComparison = racingLineModeRef.current === 'DIAGNOSTIC';
        const payload = await api.getRacingLine(50, {
          includeVisualLine: true,
          includeComparison: needsComparison,
        });
        if (!cancelled) {
          racingLineOverlayRef.current = prepareRacingLineOverlay(payload);
        }
      } catch {
        if (!cancelled) {
          racingLineOverlayRef.current = prepareRacingLineOverlay({
            status: 'INSUFFICIENT_DATA',
            racingLine: null,
            comparison: null,
            debug: { reason: 'endpoint_unavailable' },
          });
        }
      }
    };

    loadRacingLine();
    const interval = setInterval(loadRacingLine, RACING_LINE_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [showRacingLine, racingLineMode]);

  useEffect(() => {
    hoveredOpponentRef.current = hoveredOpponent;
  }, [hoveredOpponent]);

  useEffect(() => {
    selectedOpponentRef.current = selectedOpponent;
  }, [selectedOpponent]);

  useEffect(() => {
    let lastOpponentsStamp = null;
    const interval = setInterval(() => {
      const { opponents, opponentsMeta } = useTelemetryStore.getState();
      const stamp = `${opponentsMeta?.lastUpdateTimestamp ?? 'none'}:${opponents.length}`;
      if (stamp === lastOpponentsStamp) return;
      lastOpponentsStamp = stamp;
      setPanelOpponents(opponents);
      setPanelOpponentsMeta(opponentsMeta);
    }, 250);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || typeof ResizeObserver === 'undefined') return undefined;

    const updateSize = () => {
      const rect = container.getBoundingClientRect();
      setMapSize({ width: rect.width, height: rect.height });
    };
    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return undefined;

    const ctx = canvas.getContext('2d');
    if (!ctx) return undefined;

    const render = (frameTime = performance.now()) => {
      const activePerformanceMode = performanceModeRef.current || 'BALANCED';
      const frameBudgetMs = MAP_RENDER_FRAME_MS_BY_MODE[activePerformanceMode] || MAP_RENDER_FRAME_MS;
      const simpleVisuals = activePerformanceMode === 'PERFORMANCE';
      if (frameTime - lastCanvasRenderRef.current < frameBudgetMs) {
        animationRef.current = requestAnimationFrame(render);
        return;
      }
      lastCanvasRenderRef.current = frameTime;
      const perf = perfRef.current;
      if (perf.previousFrameTime) {
        perf.frameDeltas.push(frameTime - perf.previousFrameTime);
        if (perf.frameDeltas.length > 180) perf.frameDeltas.shift();
      }
      perf.previousFrameTime = frameTime;

      const renderStart = performance.now();
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

      const {
        latestFrame: storeFrame,
        history: liveHistory,
        opponents: liveOpponents,
        opponentsMeta: liveOpponentsMeta,
      } = useTelemetryStore.getState();

      const liveFrame = window.__latestFrame || storeFrame;
      const historyWindow = HISTORY_WINDOW_BY_MODE[activePerformanceMode] || HISTORY_WINDOW_BY_MODE.BALANCED;

      const renderOpponents = withEstimatedHeadings(liveOpponents
        .map((opponent) => resolveOpponentRenderState(opponent, normalizedTrack))
        .filter(Boolean), opponentMotionRef.current);
      const opponentPositions = renderOpponents
        .map((opponent) => opponent.mapPosition)
        .filter((position) => Number.isFinite(position?.x) && Number.isFinite(position?.y));
      const renderBounds = normalizedTrack
        ? computeTrackBounds(normalizedTrack, liveHistory.slice(-historyWindow), liveFrame, opponentPositions)
        : computeTrackBounds(null, liveHistory.slice(-historyWindow), liveFrame, opponentPositions);

      ctx.save();
      const scale = applyCameraTransform(ctx, rect.width, rect.height, renderBounds, cameraRef.current, liveFrame);

      if (normalizedTrack) {
        drawTrackSurface(ctx, normalizedTrack, renderBounds, scale);
      }
      if (showRacingLineRef.current && racingLineOverlayRef.current) {
        const overlayCost = drawPreparedRacingLineOverlay(
          ctx,
          racingLineOverlayRef.current,
          liveFrame,
          scale,
          racingLineModeRef.current,
          { simple: simpleVisuals },
        );
        perf.lastRacingLineOverlayMs = overlayCost;
        window.__telemetryPerf = window.__telemetryPerf || {};
        window.__telemetryPerf.racingLineOverlayMs = overlayCost;
      }

      const screenOpponents = renderOpponents
        .map((opponent) => ({
          opponent,
          screen: worldToScreen(opponent.mapPosition, rect.width, rect.height, renderBounds, cameraRef.current, liveFrame),
        }))
        .filter((entry) => Number.isFinite(entry.screen?.x) && Number.isFinite(entry.screen?.y));
      screenOpponentsRef.current = screenOpponents;
      const labelModes = simpleVisuals ? new Map() : buildLabelModes(screenOpponents, scale);

      renderOpponents.forEach((opponent, index) => {
        const isHovered =
          hoveredOpponentRef.current?.opponent?.carId === opponent.carId ||
          selectedOpponentRef.current?.opponent?.carId === opponent.carId;
        drawOpponentCar(ctx, opponent, scale, index, {
          labelMode: simpleVisuals ? 'none' : (labelModes.get(opponent.carId) || 'none'),
          isHovered,
          isStale: isStaleOpponent(opponent, liveOpponentsMeta?.staleAfterSeconds),
          noGlow: simpleVisuals,
        });
      });
      if (liveFrame) drawCar(ctx, liveFrame, scale, '#22d3ee', { noGlow: simpleVisuals });

      ctx.restore();
      drawHud(ctx, rect.width, rect.height, normalizedTrack, liveFrame, cameraRef.current, { performanceMode: activePerformanceMode });
      if (!simpleVisuals && showRacingLineRef.current && racingLineOverlayRef.current) {
        drawRacingLineLegend(ctx, rect.width, rect.height, racingLineOverlayRef.current, racingLineModeRef.current);
      }

      const renderDuration = performance.now() - renderStart;
      perf.frames += 1;
      perf.renderMs += renderDuration;
      const now = performance.now();
      if (now - perf.lastAt >= 1000) {
        const seconds = (now - perf.lastAt) / 1000;
        const wsMetrics = window.__telemetryPerf || {};
        const wsMessages = Number(wsMetrics.wsMessages || 0);
        const telemetryMessages = Number(wsMetrics.wsTelemetryMessages || 0);
        const opponentsMessages = Number(wsMetrics.wsOpponentsMessages || 0);
        const telemetryStoreUpdates = Number(wsMetrics.telemetryStoreUpdates || 0);
        const opponentsStoreUpdates = Number(wsMetrics.opponentsStoreUpdates || 0);
        const traceFrames = Number(wsMetrics.traceFrames || 0);
        const traceRenderMs = Number(wsMetrics.traceRenderMs || 0);
        const telemetryDropped = Number(wsMetrics.telemetryFramesDroppedForRender || 0);
        const opponentsDropped = Number(wsMetrics.opponentsFramesDroppedForRender || 0);
        const httpRequests = Number(wsMetrics.httpRequests || 0);
        const httpDurationMs = Number(wsMetrics.httpDurationMs || 0);
        const storeState = useTelemetryStore.getState();
        const traceFramesDelta = traceFrames - perf.lastTraceFrames;
        const traceRenderDelta = traceRenderMs - perf.lastTraceRenderMs;
        const httpRequestsDelta = httpRequests - perf.lastHttpRequests;
        const httpDurationDelta = httpDurationMs - perf.lastHttpDurationMs;
        const renderMetrics = window.__renderMetrics || {};
        const sortedFrameDeltas = perf.frameDeltas
          .filter((value) => Number.isFinite(value) && value > 0)
          .slice()
          .sort((a, b) => a - b);
        const p95FrameMs = sortedFrameDeltas.length
          ? sortedFrameDeltas[Math.floor(sortedFrameDeltas.length * 0.95)]
          : 0;
        const opponentSamples = Object.values(storeState.opponentHistoryByCarId || {})
          .reduce((sum, samples) => sum + (Array.isArray(samples) ? samples.length : 0), 0);
        const panelRps = [
          renderMetrics['AIEngineerPanel']?.fps || 0,
          renderMetrics['AIDebriefPanel']?.fps || 0,
          renderMetrics['LiveComparisonPanel']?.fps || 0,
          renderMetrics['RacingLineAnalysisPanel']?.fps || 0,
          renderMetrics['CarPhysicsDebugPanel']?.fps || 0,
        ].reduce((sum, value) => sum + value, 0);
        const memory = performance.memory?.usedJSHeapSize
          ? performance.memory.usedJSHeapSize / 1024 / 1024
          : 0;
        setPerfStats({
          performanceMode: activePerformanceMode,
          fps: perf.frames / seconds,
          avgRenderMs: perf.renderMs / Math.max(perf.frames, 1),
          p95FrameMs,
          opponentsRendered: renderOpponents.length,
          wsHz: (wsMessages - perf.lastWsMessages) / seconds,
          telemetryHz: (telemetryMessages - perf.lastTelemetryMessages) / seconds,
          opponentsHz: (opponentsMessages - perf.lastOpponentsMessages) / seconds,
          telemetryStoreHz: (telemetryStoreUpdates - perf.lastTelemetryStoreUpdates) / seconds,
          opponentsStoreHz: (opponentsStoreUpdates - perf.lastOpponentsStoreUpdates) / seconds,
          traceFps: traceFramesDelta / seconds,
          avgTraceRenderMs: traceRenderDelta / Math.max(traceFramesDelta, 1),
          telemetryDroppedHz: (telemetryDropped - perf.lastTelemetryDropped) / seconds,
          opponentsDroppedHz: (opponentsDropped - perf.lastOpponentsDropped) / seconds,
          racingLineOverlayMs: perf.lastRacingLineOverlayMs || 0,
          httpHz: httpRequestsDelta / seconds,
          httpAvgMs: httpDurationDelta / Math.max(httpRequestsDelta, 1),
          currentLapSamples: storeState.currentLapSamples?.length || 0,
          previousLapSamples: storeState.previousLapSamples?.length || 0,
          liveTrajectoryPoints: storeState.history?.length || 0,
          completedLapsHistory: storeState.completedLapsHistory?.length || 0,
          racingLineVisualPoints: racingLineOverlayRef.current?.debug?.rawDisplayPointCount || 0,
          opponentSamples,
          graphPoints: Number(wsMetrics.graphPoints || 0),
          traceCacheEntries: Number(wsMetrics.traceCacheEntries || 0),
          telemetryPayloadKb: Number(wsMetrics.telemetryPayloadKb || 0),
          racingLinePayloadKb: Number(wsMetrics.racingLinePayloadKb || 0),
          memoryEstimateMb: memory,
          dashboardRps: renderMetrics['Dashboard']?.fps || 0,
          trackRendererRps: renderMetrics['TrackRenderer']?.fps || 0,
          tracesRps: renderMetrics['TelemetryTraces']?.fps || 0,
          ggDiagramRps: renderMetrics['GGDiagram']?.fps || 0,
          linePanelRps: renderMetrics['RacingLineAnalysisPanel']?.fps || 0,
          comparisonRps: renderMetrics['LiveComparisonPanel']?.fps || 0,
          hiddenPanelRps: panelRps,
        });
        perf.frames = 0;
        perf.renderMs = 0;
        perf.lastAt = now;
        perf.lastWsMessages = wsMessages;
        perf.lastTelemetryMessages = telemetryMessages;
        perf.lastOpponentsMessages = opponentsMessages;
        perf.lastTelemetryStoreUpdates = telemetryStoreUpdates;
        perf.lastOpponentsStoreUpdates = opponentsStoreUpdates;
        perf.lastTraceFrames = traceFrames;
        perf.lastTraceRenderMs = traceRenderMs;
        perf.lastTelemetryDropped = telemetryDropped;
        perf.lastOpponentsDropped = opponentsDropped;
        perf.lastRacingLineOverlayMs = 0;
        perf.lastHttpRequests = httpRequests;
        perf.lastHttpDurationMs = httpDurationMs;
        perf.frameDeltas = [];
      }
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

  const getOpponentHitFromEvent = useCallback((event) => {
    const container = containerRef.current;
    if (!container) return null;
    const rect = container.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const hit = findOpponentHit(screenOpponentsRef.current, x, y);
    if (!hit) return null;
    return {
      opponent: hit.opponent,
      x: Math.max(8, Math.min(event.clientX + 14, window.innerWidth - 236)),
      y: Math.max(8, Math.min(event.clientY - 12, window.innerHeight - 178)),
    };
  }, []);

  const handleMouseDown = useCallback((event) => {
    if (cameraRef.current.mode !== 'OVERVIEW') return;
    if (getOpponentHitFromEvent(event)) return;
    cameraRef.current.isPanning = true;
    cameraRef.current.lastMouse = { x: event.clientX, y: event.clientY };
  }, [getOpponentHitFromEvent]);

  const handleMouseMove = useCallback((event) => {
    const camera = cameraRef.current;
    if (camera.isPanning) {
      camera.offset.x += event.clientX - camera.lastMouse.x;
      camera.offset.y += event.clientY - camera.lastMouse.y;
      camera.lastMouse = { x: event.clientX, y: event.clientY };
      setHoveredOpponent(null);
      return;
    }

    const hit = getOpponentHitFromEvent(event);
    setHoveredOpponent((previous) => {
      if (!hit && !previous) return previous;
      if (
        hit &&
        previous &&
        hit.opponent?.carId === previous.opponent?.carId &&
        Math.abs(hit.x - previous.x) < 2 &&
        Math.abs(hit.y - previous.y) < 2
      ) {
        return previous;
      }
      return hit;
    });
  }, [getOpponentHitFromEvent]);

  const handleClick = useCallback((event) => {
    const hit = getOpponentHitFromEvent(event);
    setSelectedOpponent(hit);
  }, [getOpponentHitFromEvent]);

  const stopPan = useCallback(() => {
    cameraRef.current.isPanning = false;
  }, []);

  const handleMouseLeave = useCallback(() => {
    setHoveredOpponent(null);
    stopPan();
  }, [stopPan]);

  const activeOpponentTooltip = hoveredOpponent || selectedOpponent;
  const tooltipOpponent = activeOpponentTooltip?.opponent;
  const tooltipWorld = tooltipOpponent?.worldPosition || {};
  const totalOpponents = panelOpponentsMeta.count || visibleOpponents.length;
  const compactOpponentsPanel = mapSize.width > 0 && mapSize.width < 260;
  const availableRacingLineModes = performanceMode === 'PERFORMANCE'
    ? ['LINE_ONLY']
    : RACING_LINE_OVERLAY_MODES;

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full overflow-hidden select-none cursor-crosshair"
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={stopPan}
      onMouseLeave={handleMouseLeave}
      onClick={handleClick}
    >
      <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />

      <div
        className="absolute top-3 right-3 flex flex-col gap-1"
        style={{ zIndex: 70, pointerEvents: 'auto' }}
        onMouseDown={(event) => event.stopPropagation()}
        onClick={(event) => event.stopPropagation()}
      >
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
        <div className="panel px-1.5 py-1">
          <button
            type="button"
            onClick={() => setShowRacingLine((visible) => !visible)}
            className={`num text-[7px] uppercase rounded-sm transition-all ${
              showRacingLine ? 'text-cyan-300' : 'text-slate-600 hover:text-slate-400'
            }`}
            style={{
              background: showRacingLine ? 'rgba(34,211,238,0.08)' : 'transparent',
              border: showRacingLine ? '1px solid rgba(34,211,238,0.22)' : '1px solid transparent',
              padding: '2px 6px',
              cursor: 'pointer',
            }}
          >
            RACING LINE
          </button>
        </div>
        {showRacingLine && (
          <div className="panel px-1.5 py-1 grid grid-cols-4 gap-1">
            {availableRacingLineModes.map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => setRacingLineMode(mode)}
                className={`num text-[7px] uppercase rounded-sm transition-all ${
                  racingLineMode === mode ? 'text-cyan-300' : 'text-slate-600 hover:text-slate-400'
                }`}
                style={{
                  background: racingLineMode === mode ? 'rgba(34,211,238,0.08)' : 'transparent',
                  border: racingLineMode === mode ? '1px solid rgba(34,211,238,0.22)' : '1px solid transparent',
                  padding: '2px 4px',
                  cursor: 'pointer',
                }}
              >
                {racingLineModeLabel(mode)}
              </button>
            ))}
          </div>
        )}
        <div className="panel px-1.5 py-1">
          <button
            type="button"
            onClick={() => setShowPerf((visible) => !visible)}
            className="num text-[7px] uppercase rounded-sm transition-all text-slate-500 hover:text-cyan-300"
            style={{ background: 'transparent', border: 0, padding: '1px 4px', cursor: 'pointer' }}
          >
            PERF
          </button>
        </div>
        {showPerf && (
          <div className="panel px-2 py-1.5 w-[184px]">
            <div className="grid grid-cols-3 gap-1 mb-1.5">
              {PERFORMANCE_MODES.map((mode) => (
                <button
                  key={mode}
                  type="button"
                  onClick={() => setPerformanceMode(mode)}
                  className="num text-[6px] uppercase rounded-sm transition-all"
                  style={{
                    height: 18,
                    border: performanceMode === mode ? '1px solid rgba(34,211,238,0.34)' : '1px solid rgba(255,255,255,0.05)',
                    background: performanceMode === mode ? 'rgba(34,211,238,0.10)' : 'rgba(255,255,255,0.02)',
                    color: performanceMode === mode ? '#22d3ee' : '#64748b',
                    cursor: 'pointer',
                  }}
                >
                  {mode === 'PERFORMANCE' ? 'PERF' : mode}
                </button>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-x-2 gap-y-1">
              <span className="label" style={{ fontSize: 6 }}>MODE</span>
              <span className="num text-[8px] text-cyan-300 text-right">{perfStats.performanceMode}</span>
              <span className="label" style={{ fontSize: 6 }}>FPS</span>
              <span className="num text-[8px] text-cyan-300 text-right">{perfStats.fps.toFixed(0)}</span>
              <span className="label" style={{ fontSize: 6 }}>P95</span>
              <span className="num text-[8px] text-slate-300 text-right">{perfStats.p95FrameMs.toFixed(1)}ms</span>
              <span className="label" style={{ fontSize: 6 }}>Render</span>
              <span className="num text-[8px] text-slate-300 text-right">{perfStats.avgRenderMs.toFixed(1)}ms</span>
              <span className="label" style={{ fontSize: 6 }}>Opp</span>
              <span className="num text-[8px] text-orange-300 text-right">{perfStats.opponentsRendered}</span>
              <span className="label" style={{ fontSize: 6 }}>WS</span>
              <span className="num text-[8px] text-slate-300 text-right">{perfStats.wsHz.toFixed(0)}hz</span>
              <span className="label" style={{ fontSize: 6 }}>PLY</span>
              <span className="num text-[8px] text-slate-300 text-right">{perfStats.telemetryHz.toFixed(0)}hz</span>
              <span className="label" style={{ fontSize: 6 }}>OPP</span>
              <span className="num text-[8px] text-slate-300 text-right">{perfStats.opponentsHz.toFixed(0)}hz</span>
              <span className="label" style={{ fontSize: 6 }}>Store P/O</span>
              <span className="num text-[8px] text-slate-300 text-right">
                {perfStats.telemetryStoreHz.toFixed(0)}/{perfStats.opponentsStoreHz.toFixed(0)}hz
              </span>
              <span className="label" style={{ fontSize: 6 }}>Trace</span>
              <span className="num text-[8px] text-slate-300 text-right">
                {perfStats.traceFps.toFixed(0)}hz {perfStats.avgTraceRenderMs.toFixed(1)}ms
              </span>
              <span className="label" style={{ fontSize: 6 }}>Dropped P/O</span>
              <span className="num text-[8px] text-slate-300 text-right">
                {perfStats.telemetryDroppedHz.toFixed(0)}/{perfStats.opponentsDroppedHz.toFixed(0)}hz
              </span>
              <span className="label" style={{ fontSize: 6 }}>Line</span>
              <span className="num text-[8px] text-slate-300 text-right">{perfStats.racingLineOverlayMs.toFixed(2)}ms</span>
              <span className="label" style={{ fontSize: 6 }}>HTTP</span>
              <span className="num text-[8px] text-slate-300 text-right">
                {perfStats.httpHz.toFixed(1)}hz {perfStats.httpAvgMs.toFixed(0)}ms
              </span>
              <span className="label" style={{ fontSize: 6 }}>Payload T/R</span>
              <span className="num text-[8px] text-slate-300 text-right">
                {perfStats.telemetryPayloadKb.toFixed(1)}/{perfStats.racingLinePayloadKb.toFixed(1)}kb
              </span>
              <span className="label" style={{ fontSize: 6 }}>Lap Samples</span>
              <span className="num text-[8px] text-slate-300 text-right">
                {perfStats.currentLapSamples}/{perfStats.previousLapSamples}
              </span>
              <span className="label" style={{ fontSize: 6 }}>Buffers</span>
              <span className="num text-[8px] text-slate-300 text-right">
                H{perfStats.liveTrajectoryPoints} L{perfStats.completedLapsHistory}
              </span>
              <span className="label" style={{ fontSize: 6 }}>Graph/cache</span>
              <span className="num text-[8px] text-slate-300 text-right">
                {perfStats.graphPoints}/{perfStats.traceCacheEntries}
              </span>
              <span className="label" style={{ fontSize: 6 }}>Line pts</span>
              <span className="num text-[8px] text-slate-300 text-right">{perfStats.racingLineVisualPoints}</span>
              <span className="label" style={{ fontSize: 6 }}>Opp samples</span>
              <span className="num text-[8px] text-slate-300 text-right">{perfStats.opponentSamples}</span>
              <span className="label" style={{ fontSize: 6 }}>Heap</span>
              <span className="num text-[8px] text-slate-300 text-right">
                {perfStats.memoryEstimateMb ? `${perfStats.memoryEstimateMb.toFixed(0)}mb` : '--'}
              </span>
              <div className="col-span-2 h-[1px] bg-slate-800 my-0.5" />
              <span className="label text-orange-200" style={{ fontSize: 6 }}>DASH RENDERS</span>
              <span className="num text-[8px] text-orange-200 text-right">{perfStats.dashboardRps.toFixed(1)}/s</span>
              <span className="label text-orange-200" style={{ fontSize: 6 }}>MAP RENDERS</span>
              <span className="num text-[8px] text-orange-200 text-right">{perfStats.trackRendererRps.toFixed(1)}/s</span>
              <span className="label text-orange-200" style={{ fontSize: 6 }}>TRACE RENDERS</span>
              <span className="num text-[8px] text-orange-200 text-right">{perfStats.tracesRps.toFixed(1)}/s</span>
              <span className="label text-orange-200" style={{ fontSize: 6 }}>GG RENDERS</span>
              <span className="num text-[8px] text-orange-200 text-right">{perfStats.ggDiagramRps.toFixed(1)}/s</span>
              <span className="label text-orange-200" style={{ fontSize: 6 }}>LINE RENDERS</span>
              <span className="num text-[8px] text-orange-200 text-right">{perfStats.linePanelRps.toFixed(1)}/s</span>
              <span className="label text-orange-200" style={{ fontSize: 6 }}>COMP RENDERS</span>
              <span className="num text-[8px] text-orange-200 text-right">{perfStats.comparisonRps.toFixed(1)}/s</span>
              <span className="label text-orange-200" style={{ fontSize: 6 }}>PANEL RENDERS</span>
              <span className="num text-[8px] text-orange-200 text-right">{perfStats.hiddenPanelRps.toFixed(1)}/s</span>
            </div>
          </div>
        )}
      </div>

      {visibleOpponents.length > 0 && (
        <div
          className="absolute left-3 bottom-3 panel px-2 py-2 overflow-hidden"
          style={{
            width: compactOpponentsPanel ? '44px' : 'min(218px, calc(100% - 24px))',
            pointerEvents: 'auto',
          }}
          onMouseDown={(event) => event.stopPropagation()}
          onClick={(event) => event.stopPropagation()}
        >
          <div className="flex items-center justify-between gap-2">
            <button
              type="button"
              onClick={() => setOpponentsPanelOpen((open) => !open)}
              className="num text-[8px] text-orange-300 font-bold uppercase hover:text-orange-200"
              style={{ background: 'transparent', border: 0, padding: 0, cursor: 'pointer' }}
            >
              {compactOpponentsPanel ? 'OP' : `Opponents ${opponentsPanelOpen ? '-' : '+'}`}
            </button>
            <span className="num text-[8px] text-slate-400">{totalOpponents}</span>
          </div>
          {opponentsPanelOpen && !compactOpponentsPanel && (
            <div className="flex flex-col gap-1 mt-1" style={{ maxHeight: 168, overflow: 'hidden' }}>
              {sortedOpponents.slice(0, 8).map((opponent) => {
              const world = opponent.worldPosition || {};
              const splinePercent = isFiniteNumber(opponent.splinePosition) ? opponent.splinePosition * 100 : null;
              const stale = isStaleOpponent(opponent, panelOpponentsMeta.staleAfterSeconds);
              return (
                <div
                  key={opponent.carId}
                  className="grid gap-1 items-center"
                  style={{
                    gridTemplateColumns: '24px minmax(0, 1fr) 48px',
                    opacity: stale ? 0.45 : 1,
                  }}
                >
                  <span className="num text-[8px] text-orange-200">#{opponent.carId}</span>
                  <span className="text-[9px] text-slate-200 truncate">
                    {opponentDisplayName(opponent)}
                  </span>
                  <span className="num text-[8px] text-slate-400 text-right">
                    {formatOpponentNumber(opponent.speedKmh)} km/h
                  </span>
                  <span className="num text-[7px] text-slate-600 col-start-2 col-span-2 truncate">
                    p {formatOpponentNumber(splinePercent, 1)}% / x {formatOpponentNumber(world.x, 0)} z {formatOpponentNumber(world.z, 0)}
                  </span>
                </div>
              );
              })}
            </div>
          )}
          {panelOpponentsMeta.track && opponentsPanelOpen && !compactOpponentsPanel && (
            <div className="num text-[7px] text-slate-600 mt-1 truncate">{panelOpponentsMeta.track}</div>
          )}
        </div>
      )}

      {tooltipOpponent && (
        <div
          className="absolute panel px-2 py-2 pointer-events-none"
          style={{
            position: 'fixed',
            left: activeOpponentTooltip.x,
            top: activeOpponentTooltip.y,
            width: 224,
            background: 'rgba(8, 12, 22, 0.94)',
            borderColor: 'rgba(251,146,60,0.32)',
            boxShadow: '0 10px 28px rgba(0,0,0,0.35)',
            zIndex: 80,
          }}
        >
          <div className="flex items-center justify-between gap-2 mb-1">
            <span className="num text-[9px] text-orange-200 font-bold">#{tooltipOpponent.carId}</span>
            <span className="num text-[8px] text-slate-500 truncate">{tooltipOpponent.status || 'on_track'}</span>
          </div>
          <div className="text-[10px] text-slate-100 truncate">{opponentDisplayName(tooltipOpponent)}</div>
          {tooltipOpponent.carModel && (
            <div className="text-[8px] text-slate-500 truncate mt-0.5">{tooltipOpponent.carModel}</div>
          )}
          <div className="grid grid-cols-2 gap-x-3 gap-y-1 mt-2">
            <span className="label" style={{ fontSize: 6 }}>Speed</span>
            <span className="num text-[8px] text-slate-300 text-right">{formatOpponentNumber(tooltipOpponent.speedKmh)} km/h</span>
            <span className="label" style={{ fontSize: 6 }}>Spline</span>
            <span className="num text-[8px] text-slate-300 text-right">{formatOpponentNumber(opponentSplinePercent(tooltipOpponent), 1)}%</span>
            <span className="label" style={{ fontSize: 6 }}>World X</span>
            <span className="num text-[8px] text-slate-300 text-right">{formatOpponentNumber(tooltipWorld.x, 2)}</span>
            <span className="label" style={{ fontSize: 6 }}>World Y</span>
            <span className="num text-[8px] text-slate-300 text-right">{formatOpponentNumber(tooltipWorld.y, 2)}</span>
            <span className="label" style={{ fontSize: 6 }}>World Z</span>
            <span className="num text-[8px] text-slate-300 text-right">{formatOpponentNumber(tooltipWorld.z, 2)}</span>
          </div>
        </div>
      )}
    </div>
  );
});

export default TrackRenderer;
