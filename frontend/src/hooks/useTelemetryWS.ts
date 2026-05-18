/**
 * Resilient WebSocket Client for Telemetry Streaming
 * Handles backpressure, reconnection, and event dispatching.
 */
import { useEffect, useRef, useCallback } from 'react';
import { useTelemetryStore, TelemetryFrame, CoachingEvent, EngineerSpeech, CognitiveState } from '../store/useTelemetryStore';

const WS_URL = `ws://${window.location.hostname}:8000/ws`;

export const useTelemetryWS = () => {
  const socketRef = useRef<WebSocket | null>(null);
  const { addFrame, addCoachingEvent, addEngineerSpeech, setCognitiveState, setStreaming } = useTelemetryStore();
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const shouldReconnectRef = useRef(true);

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
          addFrame(frame);
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
  }, [addFrame, addCoachingEvent, addEngineerSpeech, setCognitiveState, setStreaming]);

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
