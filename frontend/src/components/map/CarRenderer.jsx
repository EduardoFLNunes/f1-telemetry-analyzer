export function drawCar(ctx, frame, scale, color = '#22d3ee', options = {}) {
  const position = frame?.mapPosition;
  if (!position || !Number.isFinite(position.x) || !Number.isFinite(position.y)) return;

  const heading = Number.isFinite(frame.heading) ? frame.heading : 0;
  const length = 9 / scale;
  const width = 4.5 / scale;

  ctx.save();
  ctx.translate(position.x, position.y);
  ctx.rotate(heading - Math.PI / 2);
  ctx.shadowBlur = options.noGlow ? 0 : 14 / scale;
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

const OPPONENT_COLORS = [
  '#f97316',
  '#a3e635',
  '#f43f5e',
  '#38bdf8',
  '#facc15',
  '#fb7185',
  '#34d399',
  '#c084fc',
];

function safeLabel(value, fallback = '') {
  if (value === null || value === undefined) return fallback;
  const text = String(value).trim();
  return text || fallback;
}

function shortName(name) {
  const text = safeLabel(name, '');
  if (!text) return '';
  return text.length > 14 ? `${text.slice(0, 13)}...` : text;
}

function opponentColor(opponent, index) {
  if (opponent?.status === 'stale') return '#64748b';
  return OPPONENT_COLORS[Math.abs(opponent?.carId ?? index) % OPPONENT_COLORS.length];
}

export function drawOpponentCar(ctx, opponent, scale, index = 0, options = {}) {
  const position = opponent?.mapPosition;
  if (!position || !Number.isFinite(position.x) || !Number.isFinite(position.y)) return;

  const labelMode = options.labelMode || 'none';
  const color = options.color || opponentColor(opponent, index);
  const isStale = opponent?.status === 'stale' || options.isStale;
  const radius = (options.isHovered ? 5.2 : 4.3) / scale;
  const ring = 1.25 / scale;
  const heading = Number.isFinite(opponent.yaw)
    ? opponent.yaw
    : (Number.isFinite(opponent.estimatedHeading) ? opponent.estimatedHeading : null);

  ctx.save();
  if (isStale) ctx.globalAlpha = 0.42;
  ctx.translate(position.x, position.y);
  ctx.shadowBlur = options.noGlow ? 0 : (options.isHovered ? 12 : 7) / scale;
  ctx.shadowColor = color;

  ctx.beginPath();
  ctx.arc(0, 0, radius, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
  ctx.lineWidth = ring;
  ctx.strokeStyle = 'rgba(15,23,42,0.9)';
  ctx.stroke();

  if (heading !== null) {
    ctx.rotate(heading - Math.PI / 2);
    ctx.beginPath();
    ctx.moveTo(radius * 1.65, 0);
    ctx.lineTo(radius * 0.45, radius * 0.52);
    ctx.lineTo(radius * 0.45, -radius * 0.52);
    ctx.closePath();
    ctx.fillStyle = 'rgba(255,255,255,0.92)';
    ctx.fill();
    ctx.rotate(-(heading - Math.PI / 2));
  }

  ctx.shadowBlur = 0;
  if (labelMode === 'none') {
    ctx.restore();
    return;
  }

  const carId = Number.isFinite(opponent.carId) ? `#${opponent.carId}` : '#?';
  const spline = Number.isFinite(opponent.splinePosition) ? ` p${(opponent.splinePosition * 100).toFixed(1)}%` : '';
  const label = labelMode === 'id'
    ? carId
    : `${carId} ${shortName(opponent.driverName) || 'Unknown'} ${Number.isFinite(opponent.speedKmh) ? `${Math.round(opponent.speedKmh)} km/h` : '-- km/h'}${spline}`;

  const fontSize = (labelMode === 'id' ? 9 : 10) / scale;
  ctx.font = `600 ${fontSize}px Inter, system-ui, sans-serif`;
  const textWidth = ctx.measureText(label).width;
  const padX = (labelMode === 'id' ? 3 : 4) / scale;
  const padY = 2.25 / scale;
  const labelX = (labelMode === 'id' ? -textWidth / 2 : 8 / scale);
  const labelY = (labelMode === 'id' ? -8 / scale : -9 / scale);

  ctx.fillStyle = labelMode === 'id' ? 'rgba(2,6,23,0.58)' : 'rgba(2,6,23,0.78)';
  ctx.fillRect(labelX - padX, labelY - fontSize, textWidth + padX * 2, fontSize + padY * 2);
  ctx.fillStyle = isStale ? 'rgba(203,213,225,0.86)' : 'rgba(248,250,252,0.94)';
  ctx.fillText(label, labelX, labelY);

  ctx.restore();
}

export function drawTrajectory(ctx, history, scale) {
  if (!history || history.length < 2) return;

  ctx.save();
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.shadowBlur = 10 / scale;
  ctx.shadowColor = 'rgba(34,211,238,0.35)';

  for (let i = 1; i < history.length; i += 1) {
    const a = history[i - 1];
    const b = history[i];
    const ax = a.mapPosition?.x ?? a.x;
    const ay = a.mapPosition?.y ?? a.z;
    const bx = b.mapPosition?.x ?? b.x;
    const by = b.mapPosition?.y ?? b.z;
    if (!Number.isFinite(ax) || !Number.isFinite(ay) || !Number.isFinite(bx) || !Number.isFinite(by)) continue;
    const alpha = Math.max(0.08, i / history.length);
    ctx.beginPath();
    ctx.moveTo(ax, ay);
    ctx.lineTo(bx, by);
    ctx.strokeStyle = `rgba(34,211,238,${alpha * 0.55})`;
    ctx.lineWidth = 3 / scale;
    ctx.stroke();
  }

  ctx.restore();
}
