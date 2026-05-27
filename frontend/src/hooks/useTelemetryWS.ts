/**
 * Resilient WebSocket Client for Telemetry Streaming
 * Handles backpressure, reconnection, and event dispatching.
 */
import { useEffect, useRef, useCallback } from 'react';
import { useTelemetryStore, TelemetryFrame, CoachingEvent, EngineerSpeech, CognitiveState } from '../store/useTelemetryStore';

const WS_URL = `ws://${window.location.hostname}:8000/ws`;
const OPPONENTS_POLL_MS = 2000;
const OPPONENTS_WS_FRESH_MS = 2500;
const PLAYER_VISUAL_FLUSH_MS = 50;
const OPPONENTS_VISUAL_FLUSH_MS = 100;

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
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const opponentsPollRef = useRef<NodeJS.Timeout>();
  const playerFlushRef = useRef<NodeJS.Timeout>();
  const opponentsFlushRef = useRef<NodeJS.Timeout>();
  const shouldReconnectRef = useRef(true);
  const lastOpponentsWsAtRef = useRef(0);
  const pendingFrameRef = useRef<TelemetryFrame | null>(null);
  const pendingOpponentsRef = useRef<any | null>(null);

  const connect = useCallback(() => {
    if (socketRef.current?.readyState === WebSocket.OPEN) return;

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
          const mapPosition = raw.mapPosition || { x: raw.x, y: raw.y ?? raw.z };
          const projectedPosition = raw.projectedPosition || (
            raw.projected_x !== undefined && (raw.projected_y !== undefined || raw.projected_z !== undefined)
              ? { x: raw.projected_x, y: raw.projected_y ?? raw.projected_z }
              : undefined
          );
          // Map to professional structure
          const frame: TelemetryFrame = {
            ...raw,
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
          if (pendingFrameRef.current) perf().telemetryFramesDroppedForRender += 1;
          pendingFrameRef.current = frame;
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
      pendingFrameRef.current = null;
      addFrame(frame);
      perf().telemetryStoreUpdates += 1;
    }, PLAYER_VISUAL_FLUSH_MS);

    opponentsFlushRef.current = setInterval(() => {
      const snapshot = pendingOpponentsRef.current;
      if (!snapshot) return;
      pendingOpponentsRef.current = null;
      setOpponentsSnapshot(snapshot);
      perf().opponentsStoreUpdates += 1;
    }, OPPONENTS_VISUAL_FLUSH_MS);

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
        const response = await fetch('/api/live/opponents');
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
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, [connect]);

  return {
    isConnected: socketRef.current?.readyState === WebSocket.OPEN
  };
};
