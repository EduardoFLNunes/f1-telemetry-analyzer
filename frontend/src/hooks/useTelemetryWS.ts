/**
 * Resilient WebSocket Client for Telemetry Streaming
 * Handles backpressure, reconnection, and event dispatching.
 */
import { useEffect, useRef, useCallback } from 'react';
import { PerformanceMode, useTelemetryStore, TelemetryFrame, CoachingEvent, EngineerSpeech, CognitiveState } from '../store/useTelemetryStore';
import { WS_URL, apiUrl } from '../config/runtime';
import { resolveSampleMapPosition } from '../utils/spatialTransform';

const OPPONENTS_POLL_MS = 2000;
const OPPONENTS_WS_FRESH_MS = 2500;
const FLUSH_TICK_MS = 50;
const STORE_FLUSH_MS: Record<PerformanceMode, number> = {
  QUALITY: 50,
  BALANCED: 100,
  PERFORMANCE: 200,
};

const perf = () => {
  const target = window as any;
  const metrics = target.__telemetryPerf || {};
  target.__telemetryPerf = metrics;
  [
    'wsMessages',
    'wsTelemetryMessages',
    'wsOpponentsMessages',
    'telemetryStoreUpdates',
    'opponentsStoreUpdates',
    'telemetryFramesDroppedForRender',
    'opponentsFramesDroppedForRender',
    'lastWsAt',
  ].forEach((key) => {
    if (typeof metrics[key] !== 'number' || Number.isNaN(metrics[key])) {
      metrics[key] = 0;
    }
  });
  return metrics;
};

const recordWsMessage = (type: string) => {
  const metrics = perf();
  metrics.wsMessages += 1;
  metrics.lastWsAt = performance.now();
  if (type === 'telemetry') metrics.wsTelemetryMessages += 1;
  if (type === 'opponents') metrics.wsOpponentsMessages += 1;
};

export const useTelemetryWS = () => {
  const socketRef = useRef<WebSocket | null>(null);
  const addFrame = useTelemetryStore((state) => state.addFrame);
  const addCoachingEvent = useTelemetryStore((state) => state.addCoachingEvent);
  const addEngineerSpeech = useTelemetryStore((state) => state.addEngineerSpeech);
  const setCognitiveState = useTelemetryStore((state) => state.setCognitiveState);
  const setStreaming = useTelemetryStore((state) => state.setStreaming);
  const setOpponentsSnapshot = useTelemetryStore((state) => state.setOpponentsSnapshot);
  const performanceMode = useTelemetryStore((state) => state.performanceMode);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const opponentsPollRef = useRef<NodeJS.Timeout>();
  const playerFlushRef = useRef<NodeJS.Timeout>();
  const opponentsFlushRef = useRef<NodeJS.Timeout>();
  const shouldReconnectRef = useRef(true);
  const lastOpponentsWsAtRef = useRef(0);
  const lastPlayerFlushAtRef = useRef(0);
  const lastOpponentsFlushAtRef = useRef(0);
  const performanceModeRef = useRef<PerformanceMode>('BALANCED');
  const pendingFrameRef = useRef<TelemetryFrame | null>(null);
  const pendingOpponentsRef = useRef<any | null>(null);
  const latestCarPhysicsRef = useRef<TelemetryFrame['carPhysics'] | undefined>();

  useEffect(() => {
    performanceModeRef.current = performanceMode;
  }, [performanceMode]);

  const connect = useCallback(() => {
    if (
      socketRef.current?.readyState === WebSocket.OPEN
      || socketRef.current?.readyState === WebSocket.CONNECTING
    ) return;

    shouldReconnectRef.current = true;
    console.log('Connecting to telemetry stream...', WS_URL);
    const ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      console.log('Connected to telemetry engine');
      setStreaming(true);
    };

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        recordWsMessage(payload.type);
        
        if (payload.type === 'telemetry') {
          const raw = payload.data;
          const mapPosition = resolveSampleMapPosition(raw) || { x: 0, y: 0 };
          const projectedPosition = raw.projectedPosition || (
            raw.projected_x !== undefined && (raw.projected_y !== undefined || raw.projected_z !== undefined)
              ? { x: raw.projected_x, y: raw.projected_y ?? raw.projected_z }
              : undefined
          );
          // Map to professional structure
          const frame: TelemetryFrame = {
            ...raw,
            carPhysics: raw.carPhysics ?? latestCarPhysicsRef.current,
            mapPosition,
            projectedPosition,
            x: mapPosition.x,
            y: mapPosition.y,
            z: mapPosition.y,
            projected_x: projectedPosition?.x,
            projected_y: projectedPosition?.y,
            projected_z: projectedPosition?.y,
            steering: raw.steering || 0,
            accel_g: typeof raw.accel_g === 'number' 
                ? { x: 0, y: raw.accel_g, z: 0 } 
                : (raw.accel_g || { x: 0, y: 0, z: 0 }),
            timestamp: raw.timestamp || Date.now()
          };
          (window as any).__latestFrame = frame;
          if (pendingFrameRef.current) perf().telemetryFramesDroppedForRender += 1;
          pendingFrameRef.current = frame;
        } else if (payload.type === 'telemetry_detail') {
          const carPhysics = payload.data?.carPhysics;
          if (carPhysics) {
            latestCarPhysicsRef.current = carPhysics;
            if (pendingFrameRef.current) {
              pendingFrameRef.current = { ...pendingFrameRef.current, carPhysics };
            }
          }
        } else if (payload.type === 'opponents') {
          const raw = payload.data || {};
          const opponents = Array.isArray(raw.opponents)
            ? raw.opponents
            : (Array.isArray(raw.cars) ? raw.cars : []);
          lastOpponentsWsAtRef.current = Date.now();
          if (pendingOpponentsRef.current) perf().opponentsFramesDroppedForRender += 1;
          pendingOpponentsRef.current = {
            ...raw,
            opponents,
            count: typeof raw.count === 'number' ? raw.count : opponents.length,
          };
        } else if (payload.data?.type === 'coaching_event' || payload.data?.type === 'predictive_warning' || payload.type === 'coaching_event') {
          addCoachingEvent(payload.data || payload);
        } else if (payload.type === 'event') {
            if (payload.data?.metrics) {
                setCognitiveState(payload.data as CognitiveState);
            } else if (payload.data?.message) {
                addEngineerSpeech(payload.data as EngineerSpeech);
            }
        }
      } catch (err) {
        console.error('WS Message Error:', err);
      }
    };

    ws.onclose = () => {
      if (socketRef.current !== ws) return;
      socketRef.current = null;
      console.log('Telemetry stream closed');
      setStreaming(false);
      if (shouldReconnectRef.current) {
        reconnectTimeoutRef.current = setTimeout(connect, 1000);
      }
    };

    ws.onerror = (err) => {
      console.warn('Telemetry socket retrying', err);
      if (ws.readyState !== WebSocket.CLOSED && ws.readyState !== WebSocket.CLOSING) {
        ws.close();
      }
    };

    socketRef.current = ws;
  }, [addFrame, addCoachingEvent, addEngineerSpeech, setCognitiveState, setStreaming, setOpponentsSnapshot]);

  useEffect(() => {
    playerFlushRef.current = setInterval(() => {
      const frame = pendingFrameRef.current;
      if (!frame) return;
      const now = performance.now();
      const flushMs = STORE_FLUSH_MS[performanceModeRef.current] ?? STORE_FLUSH_MS.BALANCED;
      if (now - lastPlayerFlushAtRef.current < flushMs) return;
      pendingFrameRef.current = null;
      lastPlayerFlushAtRef.current = now;
      addFrame(frame);
      perf().telemetryStoreUpdates += 1;
      perf().telemetryFlushIntervalMs = flushMs;
    }, FLUSH_TICK_MS);

    opponentsFlushRef.current = setInterval(() => {
      const snapshot = pendingOpponentsRef.current;
      if (!snapshot) return;
      const now = performance.now();
      const flushMs = STORE_FLUSH_MS[performanceModeRef.current] ?? STORE_FLUSH_MS.BALANCED;
      if (now - lastOpponentsFlushAtRef.current < flushMs) return;
      pendingOpponentsRef.current = null;
      lastOpponentsFlushAtRef.current = now;
      setOpponentsSnapshot(snapshot);
      perf().opponentsStoreUpdates += 1;
      perf().opponentsFlushIntervalMs = flushMs;
    }, FLUSH_TICK_MS);

    return () => {
      if (playerFlushRef.current) clearInterval(playerFlushRef.current);
      if (opponentsFlushRef.current) clearInterval(opponentsFlushRef.current);
    };
  }, [addFrame, setOpponentsSnapshot]);

  useEffect(() => {
    let cancelled = false;

    const pollOpponents = async () => {
      if (Date.now() - lastOpponentsWsAtRef.current < OPPONENTS_WS_FRESH_MS) return;
      try {
        const response = await fetch(apiUrl('/api/live/opponents'));
        if (!response.ok) return;
        const data = await response.json();
        if (cancelled || data?.status !== 'success') return;
        if (pendingOpponentsRef.current) perf().opponentsFramesDroppedForRender += 1;
        pendingOpponentsRef.current = {
          ...data,
          opponents: Array.isArray(data.opponents) ? data.opponents : [],
        };
      } catch {
        // Keep the player telemetry stream quiet if the optional opponents endpoint is unavailable.
      }
    };

    pollOpponents();
    opponentsPollRef.current = setInterval(pollOpponents, OPPONENTS_POLL_MS);
    return () => {
      cancelled = true;
      if (opponentsPollRef.current) clearInterval(opponentsPollRef.current);
    };
  }, [setOpponentsSnapshot]);

  useEffect(() => {
    connect();
    return () => {
      shouldReconnectRef.current = false;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      const socket = socketRef.current;
      socketRef.current = null;
      socket?.close();
    };
  }, [connect]);

  return {
    isConnected: socketRef.current?.readyState === WebSocket.OPEN
  };
};
