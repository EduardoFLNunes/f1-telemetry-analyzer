import { useEffect, useRef } from 'react';
import type { MutableRefObject } from 'react';
import { useTelemetryStore } from '../store/useTelemetryStore';
import type { TelemetryFrame } from '../store/useTelemetryStore';

type Point = { x: number; y: number };

export interface InterpolationMetrics {
  interpolationEnabled: boolean;
  lastTelemetryUpdate: number | null;
  renderFrameCount: number;
  bufferSize: number;
}

export interface InterpolatedCarStateHandle {
  frameRef: MutableRefObject<TelemetryFrame | null>;
  metricsRef: MutableRefObject<InterpolationMetrics>;
  interpolationEnabled: boolean;
}

const DEFAULT_SMOOTHING_SECONDS = 0.045;
const SNAP_DISTANCE_METERS = 65;

function isFinitePoint(point?: Point | null): point is Point {
  return Boolean(point && Number.isFinite(point.x) && Number.isFinite(point.y));
}

function normalizeAngle(angle: number): number {
  return Math.atan2(Math.sin(angle), Math.cos(angle));
}

function lerpAngle(from: number, to: number, alpha: number): number {
  return from + normalizeAngle(to - from) * alpha;
}

function lerp(from: number, to: number, alpha: number): number {
  return from + (to - from) * alpha;
}

function sanitizeFrame(frame: TelemetryFrame | null): TelemetryFrame | null {
  if (!frame) return null;
  const mapPosition = isFinitePoint(frame.mapPosition)
    ? frame.mapPosition
    : Number.isFinite(frame.x) && Number.isFinite(frame.y ?? frame.z)
      ? { x: frame.x, y: frame.y ?? frame.z }
      : null;
  if (!mapPosition) return null;

  return {
    ...frame,
    mapPosition,
    x: mapPosition.x,
    y: mapPosition.y,
    z: mapPosition.y,
    heading: Number.isFinite(frame.heading) ? frame.heading : 0,
  };
}

function blendProjectedPosition(current: TelemetryFrame, target: TelemetryFrame, alpha: number) {
  const currentProjected = current.projectedPosition;
  const targetProjected = target.projectedPosition;
  if (!isFinitePoint(currentProjected) || !isFinitePoint(targetProjected)) return targetProjected;
  return {
    x: lerp(currentProjected.x, targetProjected.x, alpha),
    y: lerp(currentProjected.y, targetProjected.y, alpha),
  };
}

function blendFrame(current: TelemetryFrame, target: TelemetryFrame, alpha: number): TelemetryFrame {
  const currentPosition = current.mapPosition || { x: current.x, y: current.y ?? current.z };
  const targetPosition = target.mapPosition || { x: target.x, y: target.y ?? target.z };
  const mapPosition = {
    x: lerp(currentPosition.x, targetPosition.x, alpha),
    y: lerp(currentPosition.y, targetPosition.y, alpha),
  };

  return {
    ...target,
    mapPosition,
    projectedPosition: blendProjectedPosition(current, target, alpha),
    x: mapPosition.x,
    y: mapPosition.y,
    z: mapPosition.y,
    heading: lerpAngle(current.heading || 0, target.heading || 0, alpha),
    speed: Number.isFinite(target.speed) ? target.speed : current.speed,
    throttle: Number.isFinite(target.throttle) ? target.throttle : current.throttle,
    brake: Number.isFinite(target.brake) ? target.brake : current.brake,
    steering: Number.isFinite(target.steering) ? target.steering : current.steering,
  };
}

export function useInterpolatedCarState(sourceFrame?: TelemetryFrame | null): InterpolatedCarStateHandle {
  const targetRef = useRef<TelemetryFrame | null>(null);
  const frameRef = useRef<TelemetryFrame | null>(null);
  const metricsRef = useRef<InterpolationMetrics>({
    interpolationEnabled: true,
    lastTelemetryUpdate: null,
    renderFrameCount: 0,
    bufferSize: 0,
  });
  const rafRef = useRef<number | null>(null);
  const lastTimeRef = useRef<number | null>(null);
  const handleRef = useRef<InterpolatedCarStateHandle>({
    frameRef,
    metricsRef,
    interpolationEnabled: true,
  });

  const applySourceFrame = (frame: TelemetryFrame | null) => {
    const sanitized = sanitizeFrame(frame);
    if (!sanitized) return;
    targetRef.current = sanitized;
    metricsRef.current.lastTelemetryUpdate = Date.now();
    metricsRef.current.bufferSize = 1;
    if (!frameRef.current) {
      frameRef.current = sanitized;
    }
  };

  useEffect(() => {
    if (sourceFrame !== undefined) {
      applySourceFrame(sourceFrame);
      return undefined;
    }

    applySourceFrame(useTelemetryStore.getState().latestFrame);
    const unsubscribe = useTelemetryStore.subscribe((state, previousState) => {
      if (state.latestFrame !== previousState.latestFrame) {
        applySourceFrame(state.latestFrame);
      }
    });
    return unsubscribe;
  }, [sourceFrame]);

  useEffect(() => {
    const tick = (now: number) => {
      const lastTime = lastTimeRef.current ?? now;
      const dt = Math.max(0.001, Math.min(0.05, (now - lastTime) / 1000));
      lastTimeRef.current = now;

      const target = targetRef.current;
      const current = frameRef.current;
      if (target) {
        if (!current) {
          frameRef.current = target;
        } else {
          const currentPosition = current.mapPosition || { x: current.x, y: current.y ?? current.z };
          const targetPosition = target.mapPosition || { x: target.x, y: target.y ?? target.z };
          const distance = Math.hypot(targetPosition.x - currentPosition.x, targetPosition.y - currentPosition.y);
          if (!Number.isFinite(distance) || distance > SNAP_DISTANCE_METERS) {
            frameRef.current = target;
          } else {
            const alpha = 1 - Math.exp(-dt / DEFAULT_SMOOTHING_SECONDS);
            frameRef.current = blendFrame(current, target, alpha);
          }
        }
      }

      metricsRef.current.renderFrameCount += 1;
      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
      lastTimeRef.current = null;
    };
  }, []);

  return handleRef.current;
}
