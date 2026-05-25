function drawPolyline(ctx, x = [], y = [], close = false) {
  if (!x.length || !y.length) return;
  ctx.beginPath();
  ctx.moveTo(x[0], y[0]);
  for (let i = 1; i < x.length; i += 1) {
    ctx.lineTo(x[i], y[i]);
  }
  if (close) ctx.closePath();
}

function drawEdgePolygon(ctx, leftPoints = [], rightPoints = []) {
  if (!leftPoints.length || !rightPoints.length) return;
  ctx.beginPath();
  leftPoints.forEach((point, index) => {
    const op = index === 0 ? 'moveTo' : 'lineTo';
    ctx[op](point[0], point[1]);
  });
  for (let i = rightPoints.length - 1; i >= 0; i -= 1) {
    ctx.lineTo(rightPoints[i][0], rightPoints[i][1]);
  }
  ctx.closePath();
}

function strokePointLine(ctx, points = []) {
  if (!points.length) return;
  ctx.beginPath();
  points.forEach((point, index) => {
    const op = index === 0 ? 'moveTo' : 'lineTo';
    ctx[op](point[0], point[1]);
  });
  ctx.stroke();
}

function strokePitGeometry(ctx, geometry, left = [], right = []) {
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

function drawPitVisualGeometry(ctx, trackData, asphalt, scale) {
  const geometries = Object.values(trackData?.pitVisualGeometry?.geometries || {});
  if (!geometries.length) return;

  ctx.save();
  ctx.fillStyle = asphalt;
  ctx.strokeStyle = 'rgba(255,255,255,0.42)';
  ctx.lineWidth = 1.25 / scale;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  geometries.forEach((geometry) => {
    const left = geometry.leftEdge?.points || [];
    const right = geometry.rightEdge?.points || [];
    drawEdgePolygon(ctx, left, right);
    ctx.fill();
    strokePitGeometry(ctx, geometry, left, right);
  });
  ctx.restore();
}

export function drawTrackSurface(ctx, trackData, bounds, scale) {
  const left = trackData.left_edge;
  const right = trackData.right_edge;
  const center = trackData.visualCenterline || trackData.centerline;

  ctx.save();
  ctx.beginPath();
  for (let i = 0; i < left.x.length; i += 1) {
    const op = i === 0 ? 'moveTo' : 'lineTo';
    ctx[op](left.x[i], left.y[i]);
  }
  for (let i = right.x.length - 1; i >= 0; i -= 1) {
    ctx.lineTo(right.x[i], right.y[i]);
  }
  ctx.closePath();

  const asphalt = ctx.createLinearGradient(bounds.minX, bounds.minY, bounds.maxX, bounds.maxY);
  asphalt.addColorStop(0, '#1b1f2b');
  asphalt.addColorStop(0.5, '#262a36');
  asphalt.addColorStop(1, '#171b25');
  ctx.fillStyle = asphalt;
  ctx.fill();
  drawPitVisualGeometry(ctx, trackData, asphalt, scale);

  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  ctx.strokeStyle = 'rgba(255,255,255,0.48)';
  ctx.lineWidth = 1.4 / scale;
  const closed = trackData.closedLoop !== false;
  drawPolyline(ctx, left.x, left.y, closed);
  ctx.stroke();
  drawPolyline(ctx, right.x, right.y, closed);
  ctx.stroke();

  ctx.setLineDash([10 / scale, 16 / scale]);
  ctx.strokeStyle = 'rgba(255,255,255,0.12)';
  ctx.lineWidth = 0.8 / scale;
  drawPolyline(ctx, center.x, center.y, closed);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.restore();
}

export function drawHud(ctx, width, height, trackData, frame, camera) {
  ctx.save();
  ctx.resetTransform();
  ctx.fillStyle = 'rgba(6,8,16,0.78)';
  ctx.strokeStyle = 'rgba(148,163,184,0.16)';
  ctx.lineWidth = 1;
  ctx.fillRect(12, 12, 260, 62);
  ctx.strokeRect(12, 12, 260, 62);

  ctx.fillStyle = '#22d3ee';
  ctx.font = 'bold 9px "JetBrains Mono", monospace';
  ctx.fillText(trackData?.trackName || trackData?.name || 'COLLECTING LAP', 24, 32);

  ctx.fillStyle = '#94a3b8';
  ctx.font = '8px "JetBrains Mono", monospace';
  ctx.fillText(`${Math.round(trackData?.trackLength || trackData?.length_meters || 0)} m | ${trackData?.total_points || 0} pts | ${trackData?.source || 'track geometry'}`, 24, 48);
  ctx.fillText(`Camera ${camera.mode}  Zoom x${camera.zoom.toFixed(1)}`, 24, 64);

  ctx.restore();
}
