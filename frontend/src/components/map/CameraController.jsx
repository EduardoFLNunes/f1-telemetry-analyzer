import { pointFromFrame, toRenderHeading, toRenderPoint } from './renderTransform.js';

export function computeTrackBounds(trackData, history = [], carFrame = null, options = {}) {
  const left = trackData?.left_edge || {};
  const right = trackData?.right_edge || {};
  const leftY = left.y || left.z || [];
  const rightY = right.y || right.z || [];
  const trackPoints = [
    ...(left.x || []).map((x, index) => toRenderPoint({ x, y: leftY[index] }, options)),
    ...(right.x || []).map((x, index) => toRenderPoint({ x, y: rightY[index] }, options)),
  ].filter(Boolean);
  const trackXs = trackPoints.map((point) => point.x).filter(Number.isFinite);
  const trackYs = trackPoints.map((point) => point.y).filter(Number.isFinite);
  const hasFixedTrack = trackXs.length > 0 && trackYs.length > 0;
  const livePositions = hasFixedTrack
    ? []
    : history
      .map((frame) => toRenderPoint(pointFromFrame(frame), options))
      .filter((point) => Number.isFinite(point?.x) && Number.isFinite(point?.y));
  if (!hasFixedTrack) {
    const carPosition = toRenderPoint(pointFromFrame(carFrame), options);
    if (carPosition && Number.isFinite(carPosition.x) && Number.isFinite(carPosition.y)) {
      livePositions.push(carPosition);
    }
  }

  const xs = [
    ...trackXs,
    ...livePositions.map((point) => point.x),
  ].filter(Number.isFinite);
  const ys = [
    ...trackYs,
    ...livePositions.map((point) => point.y),
  ].filter(Number.isFinite);

  if (!xs.length || !ys.length) {
    return { minX: -100, maxX: 100, minY: -100, maxY: 100, cx: 0, cy: 0, w: 200, h: 200 };
  }

  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);

  return {
    minX,
    maxX,
    minY,
    maxY,
    cx: (minX + maxX) / 2,
    cy: (minY + maxY) / 2,
    w: Math.max(maxX - minX, 1),
    h: Math.max(maxY - minY, 1),
  };
}

function lerp(from, to, factor) {
  return from + (to - from) * factor;
}

function normalizeAngle(angle) {
  return Math.atan2(Math.sin(angle), Math.cos(angle));
}

function lerpAngle(from, to, factor) {
  return from + normalizeAngle(to - from) * factor;
}

function carForwardVector(heading = 0) {
  return {
    x: Math.sin(heading),
    y: -Math.cos(heading),
  };
}

export function applyCameraTransform(ctx, width, height, bounds, camera, carFrame, options = {}) {
  const mode = camera.mode;
  const zoom = camera.zoom;

  if (mode === 'FOLLOW' && carFrame) {
    const carPosition = toRenderPoint(pointFromFrame(carFrame), options);
    if (carPosition) {
      const heading = toRenderHeading(Number.isFinite(carFrame.heading) ? carFrame.heading : 0, options);
      const speedKmh = Number.isFinite(carFrame.speedKmh)
        ? carFrame.speedKmh
        : Number.isFinite(carFrame.speed)
          ? carFrame.speed * 3.6
          : 0;
      const forward = carForwardVector(heading);
      const aheadMeters = Math.max(0, Math.min(18, speedKmh * 0.045));
      const target = {
        x: carPosition.x + forward.x * aheadMeters,
        y: carPosition.y + forward.y * aheadMeters,
      };
      const deadzone = camera.deadzoneMeters ?? 1.2;
      const factor = camera.easingFactor ?? 0.12;

      if (!camera.center || !Number.isFinite(camera.center.x) || !Number.isFinite(camera.center.y)) {
        camera.center = { ...target };
        camera.heading = heading;
      }

      const distance = Math.hypot(target.x - camera.center.x, target.y - camera.center.y);
      if (distance > deadzone) {
        camera.center.x = lerp(camera.center.x, target.x, factor);
        camera.center.y = lerp(camera.center.y, target.y, factor);
      }
      camera.heading = lerpAngle(camera.heading ?? heading, heading, Math.min(0.16, factor * 1.15));
      camera.cameraEasingEnabled = true;

      const scale = (height / 90) * zoom;
      ctx.translate(width / 2, height * 0.68);
      ctx.scale(scale, scale);
      ctx.rotate(-(camera.heading || 0) + Math.PI / 2);
      ctx.translate(-camera.center.x, -camera.center.y);
      return scale;
    }
  }

  camera.cameraEasingEnabled = false;
  const scale = Math.min(width / bounds.w, height / bounds.h) * 0.84 * zoom;
  ctx.translate(width / 2 + camera.offset.x, height / 2 + camera.offset.y);
  ctx.scale(scale, scale);
  ctx.translate(-bounds.cx, -bounds.cy);
  return scale;
}
