import { toRenderHeading, toRenderPoint } from './renderTransform.js';

export function drawCar(ctx, frame, scale, color = '#22d3ee', options = {}) {
  const position = toRenderPoint(frame?.mapPosition, options);
  if (!position || !Number.isFinite(position.x) || !Number.isFinite(position.y)) return;

  const heading = toRenderHeading(Number.isFinite(frame.heading) ? frame.heading : 0, options);
  const length = 9 / scale;
  const width = 4.5 / scale;

  ctx.save();
  ctx.translate(position.x, position.y);
  ctx.rotate(heading - Math.PI / 2);
  ctx.shadowBlur = 14 / scale;
  ctx.shadowColor = color;

  ctx.beginPath();
  ctx.moveTo(length * 1.1, 0);
  ctx.lineTo(length * 0.35, width * 0.52);
  ctx.lineTo(-length * 0.72, width * 0.58);
  ctx.lineTo(-length * 0.72, -width * 0.58);
  ctx.lineTo(length * 0.35, -width * 0.52);
  ctx.closePath();
  ctx.fillStyle = color;
  ctx.fill();

  ctx.shadowBlur = 0;
  ctx.fillStyle = 'rgba(2,6,23,0.9)';
  ctx.beginPath();
  ctx.ellipse(length * 0.16, 0, length * 0.25, width * 0.22, 0, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = 'rgba(2,6,23,0.95)';
  ctx.fillRect(length * 0.72, -width * 0.9, length * 0.28, width * 1.8);
  ctx.fillRect(-length * 0.86, -width * 0.82, length * 0.2, width * 1.64);

  ctx.restore();
}

export function drawTrajectory(ctx, history, scale, options = {}) {
  if (!history || history.length < 2) return;
  const maxSegmentDistance = Number.isFinite(options.maxSegmentDistance)
    ? options.maxSegmentDistance
    : 35;

  ctx.save();
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.shadowBlur = 6 / scale;
  ctx.shadowColor = 'rgba(34,211,238,0.28)';

  for (let i = 1; i < history.length; i += 1) {
    const a = history[i - 1];
    const b = history[i];
    const start = toRenderPoint(a.mapPosition || { x: a.x, y: a.y ?? a.z }, options);
    const end = toRenderPoint(b.mapPosition || { x: b.x, y: b.y ?? b.z }, options);
    if (!start || !end) continue;
    const segmentDistance = Math.hypot(end.x - start.x, end.y - start.y);
    if (!Number.isFinite(segmentDistance) || segmentDistance > maxSegmentDistance) continue;
    const alpha = Math.max(0.08, i / history.length);
    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(end.x, end.y);
    ctx.strokeStyle = `rgba(34,211,238,${alpha * 0.42})`;
    ctx.lineWidth = 2 / scale;
    ctx.stroke();
  }

  ctx.restore();
}
