function drawPolyline(ctx, x = [], y = [], close = false) {
  if (!x.length || !y.length) return;
  ctx.beginPath();
  ctx.moveTo(x[0], y[0]);
  for (let i = 1; i < x.length; i += 1) {
    ctx.lineTo(x[i], y[i]);
  }
  if (close) ctx.closePath();
}

export function drawTrackSurface(ctx, trackData, bounds, scale) {
  const left = trackData.left_edge;
  const right = trackData.right_edge;
  const center = trackData.centerline;

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

export function drawProjectionDebug(ctx, frame, scale) {
  const mapPosition = frame?.mapPosition;
  const projectedPosition = frame?.projectedPosition;
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
  const normal = debug?.normalVector;
  const tangent = debug?.tangentVector;
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

export function drawHud(ctx, width, height, trackData, frame, camera, debugEnabled) {
  ctx.save();
  ctx.resetTransform();
  ctx.fillStyle = 'rgba(6,8,16,0.78)';
  ctx.strokeStyle = 'rgba(148,163,184,0.16)';
  ctx.lineWidth = 1;
  ctx.fillRect(12, 12, 260, debugEnabled ? 122 : 62);
  ctx.strokeRect(12, 12, 260, debugEnabled ? 122 : 62);

  ctx.fillStyle = '#22d3ee';
  ctx.font = 'bold 9px "JetBrains Mono", monospace';
  ctx.fillText(trackData?.trackName || trackData?.name || 'COLLECTING LAP', 24, 32);

  ctx.fillStyle = '#94a3b8';
  ctx.font = '8px "JetBrains Mono", monospace';
  ctx.fillText(`${Math.round(trackData?.trackLength || trackData?.length_meters || 0)} m | ${trackData?.total_points || 0} pts | ${trackData?.source || 'driver path debug'}`, 24, 48);
  ctx.fillText(`Camera ${camera.mode}  Zoom x${camera.zoom.toFixed(1)}`, 24, 64);

  if (debugEnabled && frame) {
    ctx.fillStyle = '#cbd5e1';
    const lateral = Number.isFinite(frame.L) ? `${Number(frame.L).toFixed(2)}m` : 'pending';
    const drift = Number.isFinite(frame.alignment_drift) ? `${Number(frame.alignment_drift).toFixed(3)}m` : 'pending';
    ctx.fillText(`s ${Number(frame.s || 0).toFixed(2)}m   L ${lateral}`, 24, 84);
    ctx.fillText(`drift ${drift}`, 24, 100);
    ctx.fillText(`segment ${frame.projectionDebug?.nearestSegmentIndex ?? '-'}`, 24, 116);
  }

  ctx.restore();
}
