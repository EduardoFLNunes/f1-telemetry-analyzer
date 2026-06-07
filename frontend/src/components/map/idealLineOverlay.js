const UNKNOWN_SPEED_COLOR = 'rgba(148, 163, 184, 0.52)';
const LOW_SPEED = [239, 68, 68];
const MID_SPEED = [245, 158, 11];
const HIGH_SPEED = [34, 197, 94];
const CURRENT_LAP_STYLE = {
  color: 'rgba(56, 189, 248, 0.96)',
  shadowColor: 'rgba(56, 189, 248, 0.42)',
  alpha: 0.88,
  lineWidth: 2.35,
};
const PREVIOUS_LAP_STYLE = {
  color: 'rgba(251, 191, 36, 0.88)',
  shadowColor: 'rgba(251, 191, 36, 0.34)',
  alpha: 0.72,
  lineWidth: 2,
};
const DEFAULT_MAX_JUMP_METERS = 140;
const CURRENT_LINE_MAX_JUMP_METERS = 95;
const POINT_CAP_BY_MODE = {
  QUALITY: Number.POSITIVE_INFINITY,
  BALANCED: 900,
  PERFORMANCE: 420,
};

export const LINE_OVERLAY_MODES = {
  OFF: 'OFF',
  LINE: 'LINE',
};

export const LINE_VISUAL_MODES = {
  LINES: 'LINES',
  SPEED: 'SPEED',
};

export const LINE_PERFORMANCE_MODES = {
  QUALITY: 'QUALITY',
  BALANCED: 'BALANCED',
  PERFORMANCE: 'PERFORMANCE',
};

function isFiniteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value);
}

function numberOrNull(value) {
  if (value === null || value === undefined || value === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function clamp01(value) {
  return Math.max(0, Math.min(1, value));
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function colorToString(color) {
  return `rgb(${Math.round(color[0])}, ${Math.round(color[1])}, ${Math.round(color[2])})`;
}

function interpolateColor(a, b, t) {
  return [
    lerp(a[0], b[0], t),
    lerp(a[1], b[1], t),
    lerp(a[2], b[2], t),
  ];
}

export function getSpeedColor(speedKmh, minSpeedKmh, maxSpeedKmh) {
  const speed = numberOrNull(speedKmh);
  const minSpeed = numberOrNull(minSpeedKmh);
  const maxSpeed = numberOrNull(maxSpeedKmh);
  if (speed === null || minSpeed === null || maxSpeed === null || maxSpeed <= minSpeed) {
    return UNKNOWN_SPEED_COLOR;
  }

  const t = clamp01((speed - minSpeed) / (maxSpeed - minSpeed));
  if (t <= 0.5) {
    return colorToString(interpolateColor(LOW_SPEED, MID_SPEED, t / 0.5));
  }
  return colorToString(interpolateColor(MID_SPEED, HIGH_SPEED, (t - 0.5) / 0.5));
}

export function computeSpeedRange(points = []) {
  const speeds = points
    .map((point) => numberOrNull(point?.speedKmh))
    .filter((speed) => speed !== null && speed > 0);
  if (!speeds.length) {
    return { minSpeedKmh: null, maxSpeedKmh: null };
  }
  return {
    minSpeedKmh: Math.min(...speeds),
    maxSpeedKmh: Math.max(...speeds),
  };
}

function speedForPoint(point) {
  const speed = numberOrNull(point?.speedKmh);
  return speed !== null && speed > 0 ? speed : null;
}

function speedForFrame(frame) {
  const speedKmh = numberOrNull(frame?.speedKmh);
  if (speedKmh !== null && speedKmh > 0) return speedKmh;

  const speed = numberOrNull(frame?.speed);
  if (speed === null || speed <= 0) return null;
  return speed > 120 ? speed : speed * 3.6;
}

function idealPointToMapPoint(point) {
  const x = numberOrNull(point?.x);
  const z = numberOrNull(point?.z);
  const fallbackY = numberOrNull(point?.y);
  const mapY = z !== null ? -z : fallbackY;
  if (x === null || mapY === null) return null;
  return {
    x,
    y: mapY,
    speedKmh: speedForPoint(point),
    splinePosition: numberOrNull(point?.splinePosition),
  };
}

function frameToMapPoint(frame) {
  const mapX = numberOrNull(frame?.mapPosition?.x);
  const mapY = numberOrNull(frame?.mapPosition?.y);
  if (mapX !== null && mapY !== null) {
    return { x: mapX, y: mapY, speedKmh: speedForFrame(frame) };
  }

  const x = numberOrNull(frame?.x ?? frame?.world_x ?? frame?.worldPositionX);
  const y = numberOrNull(frame?.y ?? frame?.z ?? frame?.world_z ?? frame?.worldPositionZ);
  if (x === null || y === null) return null;
  return { x, y, speedKmh: speedForFrame(frame) };
}

function distance(a, b) {
  return Math.hypot(b.x - a.x, b.y - a.y);
}

function pointStepForMode(length, performanceMode) {
  const cap = POINT_CAP_BY_MODE[performanceMode] ?? POINT_CAP_BY_MODE.BALANCED;
  if (!Number.isFinite(cap) || length <= cap) return 1;
  return Math.max(1, Math.ceil(length / cap));
}

function downsampleSegment(segment, performanceMode) {
  if (segment.length <= 2) return segment;
  const step = pointStepForMode(segment.length, performanceMode);
  if (step <= 1) return segment;

  const sampled = [];
  for (let i = 0; i < segment.length; i += step) {
    sampled.push(segment[i]);
  }
  const last = segment[segment.length - 1];
  if (sampled[sampled.length - 1] !== last) sampled.push(last);
  return sampled;
}

function collectSegments(rawPoints, pointMapper, maxJumpMeters) {
  const segments = [];
  let current = [];

  rawPoints.forEach((rawPoint) => {
    const point = pointMapper(rawPoint);
    if (!point) {
      if (current.length) segments.push(current);
      current = [];
      return;
    }

    const previous = current[current.length - 1];
    if (previous && distance(previous, point) > maxJumpMeters) {
      segments.push(current);
      current = [point];
      return;
    }

    current.push(point);
  });

  if (current.length) segments.push(current);
  return segments;
}

function averageNullable(a, b) {
  if (a !== null && b !== null) return (a + b) / 2;
  return a ?? b ?? null;
}

function buildPathFromSegments(segments) {
  if (typeof Path2D === 'undefined') return null;
  return segments
    .filter((segment) => segment.length > 1)
    .map((segment) => {
      const path = new Path2D();
      path.moveTo(segment[0].x, segment[0].y);
      for (let i = 1; i < segment.length; i += 1) {
        path.lineTo(segment[i].x, segment[i].y);
      }
      return path;
    });
}

function drawSegmentsAsPath(ctx, segments) {
  segments.forEach((segment) => {
    if (segment.length < 2) return;
    ctx.beginPath();
    ctx.moveTo(segment[0].x, segment[0].y);
    for (let i = 1; i < segment.length; i += 1) {
      ctx.lineTo(segment[i].x, segment[i].y);
    }
    ctx.stroke();
  });
}

function buildColoredSegments(segments, minSpeedKmh, maxSpeedKmh) {
  const coloredSegments = [];
  segments.forEach((segment) => {
    for (let i = 1; i < segment.length; i += 1) {
      const a = segment[i - 1];
      const b = segment[i];
      const speed = averageNullable(a.speedKmh, b.speedKmh);
      coloredSegments.push({
        from: a,
        to: b,
        color: getSpeedColor(speed, minSpeedKmh, maxSpeedKmh),
      });
    }
  });
  return coloredSegments;
}

function computeSpeedRangeFromSegments(segments = []) {
  const speeds = [];
  segments.forEach((segment) => {
    segment.forEach((point) => {
      const speed = numberOrNull(point?.speedKmh);
      if (speed !== null && speed > 0) speeds.push(speed);
    });
  });
  if (!speeds.length) return { minSpeedKmh: null, maxSpeedKmh: null };
  return {
    minSpeedKmh: Math.min(...speeds),
    maxSpeedKmh: Math.max(...speeds),
  };
}

function drawSpeedContourSegments(ctx, coloredSegments, scale, lineWidth = 6.5) {
  coloredSegments.forEach((segment) => {
    ctx.beginPath();
    ctx.moveTo(segment.from.x, segment.from.y);
    ctx.lineTo(segment.to.x, segment.to.y);
    ctx.strokeStyle = segment.color;
    ctx.lineWidth = lineWidth / scale;
    ctx.stroke();
  });
}

export function buildIdealLineRenderModel(data, options = {}) {
  const points = Array.isArray(data?.points) ? data.points : [];
  const performanceMode = options.performanceMode || LINE_PERFORMANCE_MODES.BALANCED;
  const maxJumpMeters = numberOrNull(options.maxJumpMeters) ?? DEFAULT_MAX_JUMP_METERS;
  const explicitMin = numberOrNull(data?.minSpeedKmh);
  const explicitMax = numberOrNull(data?.maxSpeedKmh);
  const computedRange = explicitMin !== null && explicitMax !== null
    ? { minSpeedKmh: explicitMin, maxSpeedKmh: explicitMax }
    : computeSpeedRange(points);

  const rawSegments = collectSegments(points, idealPointToMapPoint, maxJumpMeters);
  const centerSegments = rawSegments
    .map((segment) => downsampleSegment(segment, performanceMode))
    .filter((segment) => segment.length > 0);
  const coloredSegments = buildColoredSegments(
    centerSegments,
    computedRange.minSpeedKmh,
    computedRange.maxSpeedKmh,
  );

  return {
    source: data?.source || 'UNKNOWN',
    referenceLapNumber: numberOrNull(data?.referenceLapNumber),
    minSpeedKmh: computedRange.minSpeedKmh,
    maxSpeedKmh: computedRange.maxSpeedKmh,
    centerSegments,
    coloredSegments,
    validPointCount: centerSegments.reduce((total, segment) => total + segment.length, 0),
  };
}

export function buildIdealLineOverlayCache(data, performanceMode = LINE_PERFORMANCE_MODES.BALANCED, previousCache = null) {
  const points = Array.isArray(data?.points) ? data.points : [];
  const cacheKey = [
    data?.generatedAt || 'no-time',
    data?.source || 'UNKNOWN',
    data?.referenceLapNumber ?? 'no-lap',
    data?.minSpeedKmh ?? 'no-min',
    data?.maxSpeedKmh ?? 'no-max',
    points.length,
    performanceMode,
  ].join(':');

  if (previousCache?.cacheKey === cacheKey) return previousCache;

  const model = buildIdealLineRenderModel(data, { performanceMode });
  return {
    cacheKey,
    model,
    centerPaths: buildPathFromSegments(model.centerSegments),
  };
}

export function buildCurrentLinePathCache(samples = [], performanceMode = LINE_PERFORMANCE_MODES.BALANCED, previousCache = null) {
  const first = samples[0];
  const last = samples[samples.length - 1];
  const cacheKey = [
    samples.length,
    first?.timestamp ?? 'no-first',
    last?.timestamp ?? 'no-last',
    last?.lap_number ?? last?.lap ?? 'no-lap',
    performanceMode,
  ].join(':');

  if (previousCache?.cacheKey === cacheKey) return previousCache;

  const rawSegments = collectSegments(samples, frameToMapPoint, CURRENT_LINE_MAX_JUMP_METERS);
  const centerSegments = rawSegments
    .map((segment) => downsampleSegment(segment, performanceMode))
    .filter((segment) => segment.length > 0);
  const speedRange = computeSpeedRangeFromSegments(centerSegments);
  const coloredSegments = buildColoredSegments(
    centerSegments,
    speedRange.minSpeedKmh,
    speedRange.maxSpeedKmh,
  );

  return {
    cacheKey,
    centerSegments,
    coloredSegments,
    centerPaths: buildPathFromSegments(centerSegments),
    minSpeedKmh: speedRange.minSpeedKmh,
    maxSpeedKmh: speedRange.maxSpeedKmh,
    validPointCount: centerSegments.reduce((total, segment) => total + segment.length, 0),
  };
}

export function drawIdealLineOverlay(ctx, cache, scale, options = {}) {
  const model = cache?.model;
  if (!model || model.validPointCount < 2) return;
  const speedContour = options.speedContour === true;

  ctx.save();
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.globalAlpha = 0.94;
  if (speedContour) {
    ctx.shadowBlur = 4 / scale;
    ctx.shadowColor = 'rgba(15, 23, 42, 0.7)';
    drawSpeedContourSegments(ctx, model.coloredSegments, scale, 8.5);
  }

  ctx.shadowBlur = 6 / scale;
  ctx.shadowColor = 'rgba(168, 85, 247, 0.55)';
  ctx.strokeStyle = '#a855f7';
  ctx.lineWidth = 3 / scale;
  if (cache.centerPaths) {
    cache.centerPaths.forEach((path) => ctx.stroke(path));
  } else {
    drawSegmentsAsPath(ctx, model.centerSegments);
  }

  ctx.restore();
}

export function drawLapLineOverlay(ctx, cache, scale, style = CURRENT_LAP_STYLE, options = {}) {
  if (!cache || cache.validPointCount < 2) return;
  const speedContour = options.speedContour === true;

  ctx.save();
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.globalAlpha = style.alpha ?? 0.82;
  if (speedContour) {
    ctx.shadowBlur = 3 / scale;
    ctx.shadowColor = 'rgba(15, 23, 42, 0.64)';
    drawSpeedContourSegments(ctx, cache.coloredSegments || [], scale, style.haloLineWidth ?? 6);
  }

  ctx.shadowBlur = 5 / scale;
  ctx.shadowColor = style.shadowColor || 'rgba(34, 211, 238, 0.38)';
  ctx.strokeStyle = style.color || 'rgba(56, 189, 248, 0.96)';
  ctx.lineWidth = (style.lineWidth ?? 2.25) / scale;
  if (cache.centerPaths) {
    cache.centerPaths.forEach((path) => ctx.stroke(path));
  } else {
    drawSegmentsAsPath(ctx, cache.centerSegments);
  }
  ctx.restore();
}

export function drawCurrentLineOverlay(ctx, cache, scale, options = {}) {
  drawLapLineOverlay(ctx, cache, scale, CURRENT_LAP_STYLE, options);
}

export function drawPreviousLineOverlay(ctx, cache, scale, options = {}) {
  drawLapLineOverlay(ctx, cache, scale, PREVIOUS_LAP_STYLE, options);
}

export function formatIdealLineSourceLabel(data) {
  const source = data?.source || 'UNKNOWN';
  const lap = numberOrNull(data?.referenceLapNumber);
  if (source === 'REFERENCE_LAP') return lap !== null ? `Reference Lap ${lap}` : 'Reference Lap';
  if (source === 'BEST_PLAYER_LAP') return lap !== null ? `Best Player Lap ${lap}` : 'Best Player Lap';
  if (source === 'BEST_OPPONENT_LAP') return 'Best Opponent Lap';
  if (source === 'PHYSICS_SIMULATION') return 'Physics Simulation';
  return 'Unknown';
}
