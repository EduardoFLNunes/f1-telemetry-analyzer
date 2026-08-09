function drawPolyline(ctx: CanvasRenderingContext2D, x: number[] = [], y: number[] = [], close = false) {
  if (!x.length || !y.length) return;
  ctx.beginPath();
  ctx.moveTo(x[0], y[0]);
  for (let i = 1; i < x.length; i += 1) {
    ctx.lineTo(x[i], y[i]);
  }
  if (close) ctx.closePath();
}

type TrackSurfaceCache = {
  asphaltPath: Path2D;
  leftPath: Path2D | null;
  rightPath: Path2D | null;
  centerPath: Path2D | null;
};

export type ReliefMode = 'NONE' | 'ELEVATION' | 'GRADIENT';

// The band is shaded by filling one path per colour band rather than one per
// sample: 2680 quads per frame is a lot of fill calls for a 24-step scale.
const RELIEF_STEPS = 24;
const RELIEF_ALPHA = 0.62;
// Anything past this reads as full climb or full descent. Interlagos peaks near
// 13% over a 12 m window, but almost all of the lap sits inside this.
const GRADIENT_FULL_SCALE = 0.08;

type ReliefCache = { paths: Path2D[]; colors: string[] };
const RELIEF_CACHE = new WeakMap<object, Partial<Record<ReliefMode, ReliefCache | null>>>();

function mixChannel(from: number, to: number, t: number): number {
  return Math.round(from + (to - from) * t);
}

function rampColor(stops: Array<[number, number, number]>, t: number): string {
  const clamped = Math.max(0, Math.min(1, t));
  const scaled = clamped * (stops.length - 1);
  const index = Math.min(stops.length - 2, Math.floor(scaled));
  const local = scaled - index;
  const [r1, g1, b1] = stops[index];
  const [r2, g2, b2] = stops[index + 1];
  return `rgba(${mixChannel(r1, r2, local)},${mixChannel(g1, g2, local)},${mixChannel(b1, b2, local)},${RELIEF_ALPHA})`;
}

const ELEVATION_STOPS: Array<[number, number, number]> = [
  [26, 54, 93], [31, 106, 122], [86, 168, 130], [201, 190, 96], [244, 162, 74],
];
const GRADIENT_STOPS: Array<[number, number, number]> = [
  [56, 152, 220], [70, 96, 130], [70, 76, 92], [160, 96, 60], [232, 122, 48],
];

function reliefValues(trackData: any, mode: ReliefMode): number[] | null {
  const center = trackData?.centerline;
  if (!center) return null;
  const values = mode === 'ELEVATION' ? center.elevation : center.gradient;
  if (!Array.isArray(values) || values.length < 2) return null;
  return values.map((value: unknown) => Number(value)).filter((v: number) => Number.isFinite(v)).length === values.length
    ? values
    : null;
}

function buildReliefCache(trackData: any, mode: ReliefMode): ReliefCache | null {
  if (typeof Path2D === 'undefined') return null;
  const left = trackData?.left_edge;
  const right = trackData?.right_edge;
  const values = reliefValues(trackData, mode);
  if (!values || !left?.x?.length || !right?.x?.length) return null;

  const count = Math.min(values.length, left.x.length, right.x.length);
  if (count < 2) return null;

  let low: number;
  let high: number;
  if (mode === 'GRADIENT') {
    low = -GRADIENT_FULL_SCALE;
    high = GRADIENT_FULL_SCALE;
  } else {
    low = Math.min(...values.slice(0, count));
    high = Math.max(...values.slice(0, count));
  }
  const span = high - low;
  if (!(span > 1e-9)) return null;

  const stops = mode === 'GRADIENT' ? GRADIENT_STOPS : ELEVATION_STOPS;
  const paths: Path2D[] = [];
  const colors: string[] = [];
  for (let step = 0; step < RELIEF_STEPS; step += 1) {
    paths.push(new Path2D());
    colors.push(rampColor(stops, step / (RELIEF_STEPS - 1)));
  }

  for (let i = 0; i < count; i += 1) {
    const next = (i + 1) % count;
    const value = (values[i] + values[next]) / 2;
    const t = Math.max(0, Math.min(1, (value - low) / span));
    const step = Math.min(RELIEF_STEPS - 1, Math.floor(t * RELIEF_STEPS));
    const path = paths[step];
    // A quad spanning this sample and the next, edge to edge.
    path.moveTo(left.x[i], left.y[i]);
    path.lineTo(left.x[next], left.y[next]);
    path.lineTo(right.x[next], right.y[next]);
    path.lineTo(right.x[i], right.y[i]);
    path.closePath();
  }
  return { paths, colors };
}

function getReliefCache(trackData: any, mode: ReliefMode): ReliefCache | null {
  if (mode === 'NONE' || !trackData) return null;
  let byMode = RELIEF_CACHE.get(trackData);
  if (!byMode) {
    byMode = {};
    RELIEF_CACHE.set(trackData, byMode);
  }
  if (byMode[mode] === undefined) {
    byMode[mode] = buildReliefCache(trackData, mode);
  }
  return byMode[mode] || null;
}

export function trackHasRelief(trackData: any): boolean {
  return Boolean(reliefValues(trackData, 'ELEVATION'));
}

export function reliefRange(trackData: any, mode: ReliefMode): { low: number; high: number } | null {
  if (mode === 'GRADIENT') return { low: -GRADIENT_FULL_SCALE, high: GRADIENT_FULL_SCALE };
  const values = reliefValues(trackData, 'ELEVATION');
  if (!values) return null;
  return { low: Math.min(...values), high: Math.max(...values) };
}

export function reliefColorAt(mode: ReliefMode, t: number): string {
  return rampColor(mode === 'GRADIENT' ? GRADIENT_STOPS : ELEVATION_STOPS, t);
}

const TRACK_SURFACE_CACHE = new WeakMap<object, TrackSurfaceCache>();

function buildPath(x: number[] = [], y: number[] = [], close = false): Path2D | null {
  if (typeof Path2D === 'undefined' || !x.length || !y.length) return null;
  const path = new Path2D();
  path.moveTo(x[0], y[0]);
  for (let i = 1; i < x.length; i += 1) {
    path.lineTo(x[i], y[i]);
  }
  if (close) path.closePath();
  return path;
}

function getTrackSurfaceCache(trackData: any): TrackSurfaceCache | null {
  if (!trackData || typeof Path2D === 'undefined') return null;
  const cached = TRACK_SURFACE_CACHE.get(trackData);
  if (cached) return cached;

  const left = trackData.left_edge || {};
  const right = trackData.right_edge || {};
  const center = trackData.visualCenterline || trackData.centerline || {};
  const closed = trackData.closedLoop !== false;

  const asphaltPath = new Path2D();
  if (left.x?.length && right.x?.length) {
    asphaltPath.moveTo(left.x[0], left.y[0]);
    for (let i = 1; i < left.x.length; i += 1) {
      asphaltPath.lineTo(left.x[i], left.y[i]);
    }
    for (let i = right.x.length - 1; i >= 0; i -= 1) {
      asphaltPath.lineTo(right.x[i], right.y[i]);
    }
    asphaltPath.closePath();
  }

  const cache: TrackSurfaceCache = {
    asphaltPath,
    leftPath: buildPath(left.x, left.y, closed),
    rightPath: buildPath(right.x, right.y, closed),
    centerPath: buildPath(center.x, center.y, closed),
  };
  TRACK_SURFACE_CACHE.set(trackData, cache);
  return cache;
}

function indexInRanges(index: number, ranges: any[] = []): boolean {
  return ranges.some((range) => {
    const start = Number(range?.[0]);
    const end = Number(range?.[1]);
    if (!Number.isFinite(start) || !Number.isFinite(end)) return false;
    if (start <= end) return index >= start && index <= end;
    return index >= start || index <= end;
  });
}

function strokePolylineSegments(
  ctx: CanvasRenderingContext2D,
  x: number[] = [],
  y: number[] = [],
  close = false,
  suppressedRanges: any[] = [],
) {
  if (!x.length || !y.length) return;
  if (!suppressedRanges.length) {
    drawPolyline(ctx, x, y, close);
    ctx.stroke();
    return;
  }

  let drawing = false;
  const segmentCount = close ? x.length : x.length - 1;
  for (let i = 0; i < segmentCount; i += 1) {
    const next = (i + 1) % x.length;
    const suppressed = indexInRanges(i, suppressedRanges) || indexInRanges(next, suppressedRanges);
    if (suppressed) {
      if (drawing) {
        ctx.stroke();
        drawing = false;
      }
      continue;
    }
    if (!drawing) {
      ctx.beginPath();
      ctx.moveTo(x[i], y[i]);
      drawing = true;
    }
    ctx.lineTo(x[next], y[next]);
  }
  if (drawing) ctx.stroke();
}

function drawEdgePolygon(ctx: CanvasRenderingContext2D, leftPoints: number[][] = [], rightPoints: number[][] = []) {
  if (!leftPoints.length || !rightPoints.length) return;
  ctx.beginPath();
  leftPoints.forEach((point, index) => {
    if (index === 0) {
      ctx.moveTo(point[0], point[1]);
    } else {
      ctx.lineTo(point[0], point[1]);
    }
  });
  for (let i = rightPoints.length - 1; i >= 0; i -= 1) {
    ctx.lineTo(rightPoints[i][0], rightPoints[i][1]);
  }
  ctx.closePath();
}

function strokePointLine(ctx: CanvasRenderingContext2D, points: number[][] = []) {
  if (!points.length) return;
  ctx.beginPath();
  points.forEach((point, index) => {
    if (index === 0) {
      ctx.moveTo(point[0], point[1]);
    } else {
      ctx.lineTo(point[0], point[1]);
    }
  });
  ctx.stroke();
}

function strokePitGeometry(ctx: CanvasRenderingContext2D, geometry: any, left: number[][] = [], right: number[][] = []) {
  const hints = geometry?.renderHints || {};
  const openStart = Boolean(geometry?.openStart || hints.openStart);
  const openEnd = Boolean(geometry?.openEnd || hints.openEnd);
  if (!openStart && !openEnd) {
    ctx.stroke();
    return;
  }

  strokePointLine(ctx, left);
  strokePointLine(ctx, right);

  if (!openStart && left.length && right.length) {
    strokePointLine(ctx, [left[0], right[0]]);
  }
  if (!openEnd && left.length && right.length) {
    strokePointLine(ctx, [left[left.length - 1], right[right.length - 1]]);
  }
}

function drawPitVisualGeometry(ctx: CanvasRenderingContext2D, trackData: any, asphalt: CanvasGradient, scale: number) {
  const geometries = Object.values(trackData?.pitVisualGeometry?.geometries || {}) as any[];
  if (!geometries.length) return;
  const surfaceUnion = trackData?.pitVisualGeometry?.surfaceUnionFix;

  ctx.save();
  ctx.fillStyle = asphalt;
  ctx.strokeStyle = 'rgba(255,255,255,0.42)';
  ctx.lineWidth = 1.25 / scale;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  if (surfaceUnion?.suppressInternalEdges) {
    geometries.forEach((geometry) => {
      drawEdgePolygon(ctx, geometry.leftEdge?.points || [], geometry.rightEdge?.points || []);
      ctx.fill();
    });

    ctx.strokeStyle = 'rgba(255,255,255,0.42)';
    ctx.lineWidth = 1.25 / scale;
    const policy = surfaceUnion.pitGeometryStrokePolicy || {};
    geometries.forEach((geometry) => {
      const strokeEdges = policy[geometry.name]?.strokeEdges || geometry.renderHints?.strokeEdges || ['leftEdge', 'rightEdge'];
      strokeEdges.forEach((edgeName: string) => {
        strokePointLine(ctx, geometry[edgeName]?.points || []);
      });
    });
    (surfaceUnion.stitchEdges || []).forEach((edge: any) => {
      strokePointLine(ctx, edge.points?.points || []);
    });
    ctx.restore();
    return;
  }

  geometries.forEach((geometry) => {
    const left = geometry.leftEdge?.points || [];
    const right = geometry.rightEdge?.points || [];
    drawEdgePolygon(ctx, left, right);
    ctx.fill();
    strokePitGeometry(ctx, geometry, left, right);
  });
  ctx.restore();
}

const KERB_STRIPE_METERS = 1.6;

function polygonPath(ctx: CanvasRenderingContext2D, points: number[][]) {
  ctx.beginPath();
  points.forEach((point, index) => {
    if (index === 0) ctx.moveTo(point[0], point[1]);
    else ctx.lineTo(point[0], point[1]);
  });
  ctx.closePath();
}

/** Dominant direction of a ring, so stripes run across the kerb rather than along it. */
function dominantAngle(points: number[][]): number {
  let sx = 0;
  let sy = 0;
  for (let i = 1; i < points.length; i += 1) {
    let dx = points[i][0] - points[i - 1][0];
    let dy = points[i][1] - points[i - 1][1];
    // Fold to a half-circle so opposite sides of the ring reinforce instead of cancel.
    if (dx < 0) { dx = -dx; dy = -dy; }
    sx += dx;
    sy += dy;
  }
  return Math.atan2(sy, sx);
}

export function drawKerbs(ctx: CanvasRenderingContext2D, trackData: any, scale: number) {
  const polygons = trackData?.kerbGeometry?.polygons;
  if (!Array.isArray(polygons) || !polygons.length) return;

  ctx.save();
  for (const polygon of polygons) {
    const points = polygon?.points;
    if (!Array.isArray(points) || points.length < 4) continue;

    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const point of points) {
      if (point[0] < minX) minX = point[0];
      if (point[0] > maxX) maxX = point[0];
      if (point[1] < minY) minY = point[1];
      if (point[1] > maxY) maxY = point[1];
    }
    if (!Number.isFinite(minX) || !Number.isFinite(minY)) continue;

    ctx.save();
    polygonPath(ctx, points);
    ctx.clip();

    // Base colour, then white bars across it: the red/white kerb reads instantly
    // even when the map is zoomed out far enough that the strip is a few pixels.
    ctx.fillStyle = '#b3382f';
    ctx.fillRect(minX, minY, maxX - minX, maxY - minY);

    const angle = dominantAngle(points);
    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;
    const span = Math.hypot(maxX - minX, maxY - minY);
    ctx.translate(cx, cy);
    ctx.rotate(angle);
    ctx.fillStyle = '#e8e8e8';
    for (let offset = -span; offset <= span; offset += KERB_STRIPE_METERS * 2) {
      ctx.fillRect(offset, -span, KERB_STRIPE_METERS, span * 2);
    }
    ctx.restore();

    // Thin outline keeps adjacent kerb segments distinguishable.
    ctx.lineWidth = 0.5 / scale;
    ctx.strokeStyle = 'rgba(15,23,42,0.55)';
    polygonPath(ctx, points);
    ctx.stroke();
  }
  ctx.restore();
}

export function drawMarkings(ctx: CanvasRenderingContext2D, trackData: any, scale: number) {
  const groups = trackData?.markingGeometry?.polygons;
  if (!Array.isArray(groups) || !groups.length) return;

  ctx.save();
  ctx.fillStyle = 'rgba(236,240,245,0.82)';
  for (const group of groups) {
    const rings = group?.rings;
    if (!Array.isArray(rings) || !rings.length) continue;

    // A line running the whole lap encloses the infield, and the paint is the
    // band between that ring and its holes -- so all rings go into one path and
    // are filled even-odd. Filling the outer ring alone would flood the middle
    // of the circuit.
    ctx.beginPath();
    for (const ring of rings) {
      if (!Array.isArray(ring) || ring.length < 4) continue;
      ring.forEach((point: number[], index: number) => {
        if (index === 0) ctx.moveTo(point[0], point[1]);
        else ctx.lineTo(point[0], point[1]);
      });
      ctx.closePath();
    }
    ctx.fill('evenodd');
  }
  ctx.restore();
}

export function drawTrackSurface(
  ctx: CanvasRenderingContext2D,
  trackData: any,
  bounds: any,
  scale: number,
  reliefMode: ReliefMode = 'NONE',
) {
  const left = trackData.left_edge;
  const right = trackData.right_edge;
  const center = trackData.visualCenterline || trackData.centerline;
  const cache = getTrackSurfaceCache(trackData);

  ctx.save();

  const asphalt = ctx.createLinearGradient(bounds.minX, bounds.minY, bounds.maxX, bounds.maxY);
  asphalt.addColorStop(0, '#1b1f2b');
  asphalt.addColorStop(0.5, '#262a36');
  asphalt.addColorStop(1, '#171b25');
  ctx.fillStyle = asphalt;
  if (cache?.asphaltPath) {
    ctx.fill(cache.asphaltPath);
  } else {
    ctx.beginPath();
    for (let i = 0; i < left.x.length; i += 1) {
      if (i === 0) {
        ctx.moveTo(left.x[i], left.y[i]);
      } else {
        ctx.lineTo(left.x[i], left.y[i]);
      }
    }
    for (let i = right.x.length - 1; i >= 0; i -= 1) {
      ctx.lineTo(right.x[i], right.y[i]);
    }
    ctx.closePath();
    ctx.fill();
  }
  drawPitVisualGeometry(ctx, trackData, asphalt, scale);

  // Relief goes straight onto the asphalt, under the paint: the shading is a
  // property of the surface, not something painted on it.
  const relief = getReliefCache(trackData, reliefMode);
  if (relief) {
    for (let step = 0; step < relief.paths.length; step += 1) {
      ctx.fillStyle = relief.colors[step];
      ctx.fill(relief.paths[step]);
    }
  }

  // Paint sits on the asphalt, kerbs on top of the paint, and the edge strokes
  // last so the track outline still reads as the outermost line.
  drawMarkings(ctx, trackData, scale);
  drawKerbs(ctx, trackData, scale);

  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  ctx.strokeStyle = 'rgba(255,255,255,0.48)';
  ctx.lineWidth = 1.4 / scale;
  const closed = trackData.closedLoop !== false;
  const surfaceUnion = trackData?.pitVisualGeometry?.surfaceUnionFix;
  const leftSuppression = surfaceUnion?.mainTrackStrokeSuppression?.leftRanges || [];
  const rightSuppression = surfaceUnion?.mainTrackStrokeSuppression?.rightRanges || [];
  if (cache?.leftPath && !leftSuppression.length) {
    ctx.stroke(cache.leftPath);
  } else {
    strokePolylineSegments(ctx, left.x, left.y, closed, leftSuppression);
  }
  if (cache?.rightPath && !rightSuppression.length) {
    ctx.stroke(cache.rightPath);
  } else {
    strokePolylineSegments(ctx, right.x, right.y, closed, rightSuppression);
  }

  ctx.setLineDash([10 / scale, 16 / scale]);
  ctx.strokeStyle = 'rgba(255,255,255,0.12)';
  ctx.lineWidth = 0.8 / scale;
  if (cache?.centerPath) {
    ctx.stroke(cache.centerPath);
  } else {
    drawPolyline(ctx, center.x, center.y, closed);
    ctx.stroke();
  }
  ctx.setLineDash([]);
  ctx.restore();
}

export function drawHud(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  trackData: any,
  frame: any,
  camera: { mode: string; zoom: number },
  options: { performanceMode?: string } = {},
) {
  const performanceMode = options.performanceMode || 'BALANCED';
  const compact = performanceMode === 'PERFORMANCE';
  ctx.save();
  ctx.resetTransform();
  ctx.fillStyle = 'rgba(6,8,16,0.78)';
  ctx.strokeStyle = 'rgba(148,163,184,0.16)';
  ctx.lineWidth = 1;
  ctx.fillRect(12, 12, compact ? 170 : 260, compact ? 42 : 62);
  ctx.strokeRect(12, 12, compact ? 170 : 260, compact ? 42 : 62);

  ctx.fillStyle = '#22d3ee';
  ctx.font = 'bold 9px "JetBrains Mono", monospace';
  ctx.fillText(trackData?.trackName || trackData?.name || 'COLLECTING LAP', 24, 32);

  ctx.fillStyle = '#94a3b8';
  ctx.font = '8px "JetBrains Mono", monospace';
  if (compact) {
    ctx.fillText(`${camera.mode} x${camera.zoom.toFixed(1)}`, 24, 50);
  } else {
    ctx.fillText(`${Math.round(trackData?.trackLength || trackData?.length_meters || 0)} m | ${trackData?.total_points || 0} pts | ${trackData?.source || 'track geometry'}`, 24, 48);
    ctx.fillText(`Camera ${camera.mode}  Zoom x${camera.zoom.toFixed(1)}`, 24, 64);
  }

  ctx.restore();
}
