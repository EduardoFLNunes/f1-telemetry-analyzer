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

export function drawTrackSurface(ctx: CanvasRenderingContext2D, trackData: any, bounds: any, scale: number) {
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
