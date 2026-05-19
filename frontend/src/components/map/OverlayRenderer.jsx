import { toRenderPoint, toRenderVector } from './renderTransform.js';

function drawRenderPolyline(ctx, x = [], y = [], close = false, options = {}) {
  if (!x.length || !y.length) return;
  const first = toRenderPoint({ x: x[0], y: y[0] }, options);
  if (!first) return;
  ctx.beginPath();
  ctx.moveTo(first.x, first.y);
  for (let i = 1; i < x.length; i += 1) {
    const point = toRenderPoint({ x: x[i], y: y[i] }, options);
    if (!point) continue;
    ctx.lineTo(point.x, point.y);
  }
  if (close) ctx.closePath();
}

function buildPolylinePath(x = [], y = [], close = false, options = {}) {
  if (typeof Path2D === 'undefined' || !x.length || !y.length) return null;
  const first = toRenderPoint({ x: x[0], y: y[0] }, options);
  if (!first) return null;
  const path = new Path2D();
  path.moveTo(first.x, first.y);
  for (let i = 1; i < x.length; i += 1) {
    const point = toRenderPoint({ x: x[i], y: y[i] }, options);
    if (!point) continue;
    path.lineTo(point.x, point.y);
  }
  if (close) path.closePath();
  return path;
}

export function createTrackPathCache(trackData, options = {}) {
  if (!trackData || typeof Path2D === 'undefined') {
    return {
      pathCacheEnabled: false,
      trackPointCount: 0,
      renderedPointCount: 0,
      asphaltPath: null,
      leftEdgePath: null,
      rightEdgePath: null,
      centerlinePath: null,
    };
  }

  const left = trackData.left_edge;
  const right = trackData.right_edge;
  const center = trackData.centerline;
  const closed = trackData.closedLoop !== false;
  const asphaltPath = new Path2D();

  if (options.logBuild) {
    console.info('[OverlayRenderer] building visual Path2D', {
      track: trackData.trackName || trackData.name,
      leftPoints: left?.x?.length || 0,
      rightPoints: right?.x?.length || 0,
      centerlinePoints: center?.x?.length || 0,
      visualGeometryEnabled: Boolean(trackData.visualGeometryEnabled),
    });
  }

  if (left?.x?.length && right?.x?.length) {
    const firstLeft = toRenderPoint({ x: left.x[0], y: left.y[0] }, options);
    if (firstLeft) asphaltPath.moveTo(firstLeft.x, firstLeft.y);
    for (let i = 1; i < left.x.length; i += 1) {
      const point = toRenderPoint({ x: left.x[i], y: left.y[i] }, options);
      if (point) asphaltPath.lineTo(point.x, point.y);
    }
    for (let i = right.x.length - 1; i >= 0; i -= 1) {
      const point = toRenderPoint({ x: right.x[i], y: right.y[i] }, options);
      if (point) asphaltPath.lineTo(point.x, point.y);
    }
    asphaltPath.closePath();
  }

  const leftEdgePath = buildPolylinePath(left?.x, left?.y, closed, options);
  const rightEdgePath = buildPolylinePath(right?.x, right?.y, closed, options);
  const centerlinePath = buildPolylinePath(center?.x, center?.y, closed, options);

  return {
    pathCacheEnabled: true,
    trackPointCount: center?.x?.length || 0,
    renderedPointCount: (left?.x?.length || 0) + (right?.x?.length || 0) + (center?.x?.length || 0),
    asphaltPath,
    leftEdgePath,
    rightEdgePath,
    centerlinePath,
  };
}

export function drawTrackSurface(ctx, trackData, bounds, scale, pathCache = null, options = {}) {
  const left = trackData.left_edge;
  const right = trackData.right_edge;
  const center = trackData.centerline;
  const cache = pathCache?.pathCacheEnabled ? pathCache : null;
  if (cache && options.logPathCacheReuse && !cache.reuseLogged) {
    console.info('[OverlayRenderer] reusing visual Path2D');
    cache.reuseLogged = true;
  }

  ctx.save();
  if (!cache) {
    ctx.beginPath();
    for (let i = 0; i < left.x.length; i += 1) {
      const point = toRenderPoint({ x: left.x[i], y: left.y[i] }, options);
      if (!point) continue;
      const op = i === 0 ? 'moveTo' : 'lineTo';
      ctx[op](point.x, point.y);
    }
    for (let i = right.x.length - 1; i >= 0; i -= 1) {
      const point = toRenderPoint({ x: right.x[i], y: right.y[i] }, options);
      if (point) ctx.lineTo(point.x, point.y);
    }
    ctx.closePath();
  }

  const asphalt = ctx.createLinearGradient(bounds.minX, bounds.minY, bounds.maxX, bounds.maxY);
  asphalt.addColorStop(0, '#1b1f2b');
  asphalt.addColorStop(0.5, '#262a36');
  asphalt.addColorStop(1, '#171b25');
  ctx.fillStyle = asphalt;
  if (cache?.asphaltPath) ctx.fill(cache.asphaltPath);
  else ctx.fill();

  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  ctx.strokeStyle = 'rgba(255,255,255,0.48)';
  ctx.lineWidth = 1.4 / scale;
  const closed = trackData.closedLoop !== false;
  if (cache?.leftEdgePath) ctx.stroke(cache.leftEdgePath);
  else {
    drawRenderPolyline(ctx, left.x, left.y, closed, options);
    ctx.stroke();
  }
  if (cache?.rightEdgePath) ctx.stroke(cache.rightEdgePath);
  else {
    drawRenderPolyline(ctx, right.x, right.y, closed, options);
    ctx.stroke();
  }

  if (options.showCenterline) {
    ctx.setLineDash([10 / scale, 16 / scale]);
    ctx.strokeStyle = 'rgba(255,255,255,0.12)';
    ctx.lineWidth = 0.8 / scale;
    if (cache?.centerlinePath) ctx.stroke(cache.centerlinePath);
    else {
      drawRenderPolyline(ctx, center.x, center.y, closed, options);
      ctx.stroke();
    }
    ctx.setLineDash([]);
  }
  ctx.restore();
}

export function drawPhysicsEdges(ctx, trackData, scale, options = {}) {
  if (!trackData?.left_edge?.x?.length || !trackData?.right_edge?.x?.length) return;
  const closed = trackData.closedLoop !== false;
  ctx.save();
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.setLineDash([4 / scale, 6 / scale]);
  ctx.strokeStyle = 'rgba(251,113,133,0.52)';
  ctx.lineWidth = 0.9 / scale;
  drawRenderPolyline(ctx, trackData.left_edge.x, trackData.left_edge.y, closed, options);
  ctx.stroke();
  ctx.strokeStyle = 'rgba(251,191,36,0.52)';
  drawRenderPolyline(ctx, trackData.right_edge.x, trackData.right_edge.y, closed, options);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.restore();
}

export function drawProjectionDebug(ctx, frame, scale, options = {}) {
  const mapPosition = toRenderPoint(frame?.mapPosition, options);
  const projectedPosition = toRenderPoint(frame?.projectedPosition, options);
  if (!mapPosition || !projectedPosition || !Number.isFinite(projectedPosition.x) || !Number.isFinite(projectedPosition.y)) return;

  ctx.save();
  ctx.setLineDash([3 / scale, 3 / scale]);
  ctx.strokeStyle = Math.abs(frame.L || 0) > 6 ? '#fb7185' : '#34d399';
  ctx.lineWidth = 1.4 / scale;
  ctx.beginPath();
  ctx.moveTo(mapPosition.x, mapPosition.y);
  ctx.lineTo(projectedPosition.x, projectedPosition.y);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.strokeStyle = 'rgba(255,255,255,0.7)';
  ctx.lineWidth = 1 / scale;
  ctx.beginPath();
  ctx.moveTo(projectedPosition.x - 3 / scale, projectedPosition.y);
  ctx.lineTo(projectedPosition.x + 3 / scale, projectedPosition.y);
  ctx.moveTo(projectedPosition.x, projectedPosition.y - 3 / scale);
  ctx.lineTo(projectedPosition.x, projectedPosition.y + 3 / scale);
  ctx.stroke();

  const debug = frame.projectionDebug;
  const normal = toRenderVector(debug?.normalVector, options);
  const tangent = toRenderVector(debug?.tangentVector, options);
  if (normal && tangent) {
    const vx = projectedPosition.x;
    const vy = projectedPosition.y;
    const len = 18 / scale;

    ctx.lineWidth = 1.5 / scale;
    ctx.strokeStyle = '#38bdf8';
    ctx.beginPath();
    ctx.moveTo(vx, vy);
    ctx.lineTo(vx + tangent.x * len, vy + tangent.y * len);
    ctx.stroke();

    ctx.strokeStyle = '#fbbf24';
    ctx.beginPath();
    ctx.moveTo(vx, vy);
    ctx.lineTo(vx + normal.x * len, vy + normal.y * len);
    ctx.stroke();
  }

  ctx.restore();
}

export function drawHud(ctx, width, height, trackData, frame, camera, debugEnabled, metrics = {}) {
  const formatBytes = (bytes = 0) => {
    if (!bytes) return '0 KB';
    if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
    return `${Math.round(bytes / 1024)} KB`;
  };
  const formatMs = (value) => Number.isFinite(value) ? `${Number(value).toFixed(0)}ms` : '--';

  ctx.save();
  ctx.resetTransform();
  ctx.fillStyle = 'rgba(6,8,16,0.78)';
  ctx.strokeStyle = 'rgba(148,163,184,0.16)';
  ctx.lineWidth = 1;
  const hudHeight = debugEnabled ? 234 : 162;
  ctx.fillRect(12, 12, 360, hudHeight);
  ctx.strokeRect(12, 12, 360, hudHeight);

  ctx.fillStyle = '#22d3ee';
  ctx.font = 'bold 9px "JetBrains Mono", monospace';
  ctx.fillText(trackData?.trackName || trackData?.name || 'COLLECTING LAP', 24, 32);

  ctx.fillStyle = '#94a3b8';
  ctx.font = '8px "JetBrains Mono", monospace';
  ctx.fillText(`${Math.round(trackData?.trackLength || trackData?.length_meters || 0)} m | ${trackData?.total_points || 0} pts | ${trackData?.source || 'driver path debug'}`, 24, 48);
  ctx.fillText(`Camera ${camera.mode}  Zoom x${camera.zoom.toFixed(1)}`, 24, 64);
  ctx.fillText(`FPS ${Math.round(metrics.fps || 0)} | Path cache ${metrics.pathCacheEnabled ? 'ON' : 'OFF'} | Interp ${metrics.interpolationEnabled ? 'ON' : 'OFF'} | Visual ${metrics.visualGeometryEnabled ? 'ON' : 'OFF'} | mirrorMode ${metrics.mirrorMode || 'off'}`, 24, 80);
  ctx.fillText(`Track fetches ${metrics.trackFetchCount || 0} | Payload ${formatBytes(metrics.trackPayloadBytes || 0)} | Poll ${metrics.trackPollingEnabled ? 'ON' : 'OFF'}`, 24, 96);
  const debugFlags = metrics.debugOverlaysEnabled
    ? `${metrics.debugProjectionEnabled ? 'P' : '-'}${metrics.debugPhysicsEnabled ? 'E' : '-'}${metrics.debugTrajectoryEnabled ? 'T' : '-'}${metrics.debugCenterlineEnabled ? 'C' : '-'}`
    : 'OFF';
  ctx.fillText(`Path builds ${metrics.pathCacheBuildCount || 0} | Static layer ${metrics.staticTrackLayerCacheEnabled ? 'ON' : 'OFF'}:${metrics.staticTrackLayerBuildCount || 0} | Offscreen create ${metrics.offscreenCanvasRecreatedCount || 0} | Debug ${debugFlags}`, 24, 112);
  ctx.fillText(`Telemetry ${Number(metrics.telemetryHz || 0).toFixed(1)}Hz | Render ${Number(metrics.renderHz || metrics.fps || 0).toFixed(1)}Hz | age ${formatMs(metrics.lastPacketAgeMs)} | pkt ${formatMs(metrics.packetDeltaMs)}`, 24, 128);
  ctx.fillText(`Backend sample ${formatMs(metrics.backendSampleDeltaMs)} | read ${formatMs(metrics.backendReadDeltaMs)} | latency ${formatMs(metrics.responseLatencyMs)} | interpBuf ${metrics.interpolationBufferSize || 0}`, 24, 144);
  ctx.fillText(`maxFrame ${formatMs(metrics.maxFrameDeltaMs)} | dropped ${metrics.droppedFrames || 0} | outOfOrder ${metrics.outOfOrderPackets || 0} | dup ${metrics.duplicatePackets || 0}`, 24, 160);

  if (debugEnabled && frame) {
    ctx.fillStyle = '#cbd5e1';
    const lateral = Number.isFinite(frame.L) ? `${Number(frame.L).toFixed(2)}m` : 'pending';
    const drift = Number.isFinite(frame.alignment_drift) ? `${Number(frame.alignment_drift).toFixed(3)}m` : 'pending';
    ctx.fillText(`s ${Number(frame.s || 0).toFixed(2)}m   L ${lateral}`, 24, 182);
    ctx.fillText(`drift ${drift}`, 24, 198);
    ctx.fillText(`segment ${frame.projectionDebug?.nearestSegmentIndex ?? '-'}`, 24, 214);
    ctx.fillText(`rendered ${metrics.renderedPointCount || 0} pts | camera easing ${metrics.cameraEasingEnabled ? 'ON' : 'OFF'}`, 24, 230);
  }
  ctx.restore();
}
