import { resolveSampleMapPosition } from '../../utils/spatialTransform';

export type CarRenderOptions = {
  noGlow?: boolean;
};

// Real single-seater footprint. The marker used to be a fixed pixel size, so in
// FOLLOW (about 4 px per metre) it drew roughly 2.3 m long -- half a real car --
// and looked lost on the track. Sizing in metres keeps it proportional to the
// asphalt at every zoom.
const CAR_LENGTH_METERS = 4.8;
const CAR_WIDTH_METERS = 2.0;
// The body polygon spans 1.82x its length unit and 1.16x its width unit.
const LENGTH_UNIT_SPAN = 1.82;
const WIDTH_UNIT_SPAN = 1.16;
// Floor so the car is still findable when the whole circuit is on screen.
const MIN_CAR_SCREEN_PX = 11;

export function carBodyUnits(scale: number): { length: number; width: number; zoomFloor: number } {
  const zoomFloor = Math.max(1, MIN_CAR_SCREEN_PX / Math.max(CAR_LENGTH_METERS * scale, 1e-6));
  return {
    length: (CAR_LENGTH_METERS / LENGTH_UNIT_SPAN) * zoomFloor,
    width: (CAR_WIDTH_METERS / WIDTH_UNIT_SPAN) * zoomFloor,
    zoomFloor,
  };
}

export function drawCar(
  ctx: CanvasRenderingContext2D,
  frame: any,
  scale: number,
  color = '#22d3ee',
  options: CarRenderOptions = {},
) {
  const position = resolveSampleMapPosition(frame);
  if (!position || !Number.isFinite(position.x) || !Number.isFinite(position.y)) return;

  const heading = Number.isFinite(frame?.heading) ? frame.heading : 0;
  const { length, width } = carBodyUnits(scale);

  ctx.save();
  ctx.translate(position.x, position.y);
  // The map mirrors the Z axis (mapY = -worldZ), so a world heading has to be
  // negated to rotate correctly in map space -- applyCameraTransform already does
  // this. Without the negation the marker turns the wrong way round the lap:
  // measured against the track tangent while driving, the un-negated form was off
  // by 87 degrees on average (27 to 172), the negated form by 6.5, and that
  // remainder is slip angle -- near zero on the straight, largest mid-corner.
  ctx.rotate(-heading - Math.PI / 2);
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

function safeLabel(value: unknown, fallback = ''): string {
  if (value === null || value === undefined) return fallback;
  const text = String(value).trim();
  return text || fallback;
}

function shortName(name: unknown): string {
  const text = safeLabel(name, '');
  if (!text) return '';
  return text.length > 14 ? `${text.slice(0, 13)}...` : text;
}

function opponentColor(opponent: any, index: number): string {
  if (opponent?.status === 'stale') return '#64748b';
  return OPPONENT_COLORS[Math.abs(opponent?.carId ?? index) % OPPONENT_COLORS.length];
}

export type OpponentRenderOptions = {
  labelMode?: 'none' | 'id' | string;
  color?: string;
  isStale?: boolean;
  isHovered?: boolean;
  noGlow?: boolean;
};

export function drawOpponentCar(
  ctx: CanvasRenderingContext2D,
  opponent: any,
  scale: number,
  index = 0,
  options: OpponentRenderOptions = {},
) {
  const position = resolveSampleMapPosition(opponent);
  if (!position || !Number.isFinite(position.x) || !Number.isFinite(position.y)) return;

  const labelMode = options.labelMode || 'none';
  const color = options.color || opponentColor(opponent, index);
  const isStale = opponent?.status === 'stale' || options.isStale;
  // Also in metres, for the same reason as the player marker, so a pack of cars
  // reads at the right size against the track width.
  const { length: carLength, zoomFloor } = carBodyUnits(scale);
  const radius = carLength * 0.55 * (options.isHovered ? 1.2 : 1.0);
  const ring = Math.max(0.18 * zoomFloor, 1.0 / scale);
  // Two heading sources with different frames, so resolve to a map-space nose
  // angle here instead of rotating by a raw value.
  //   yaw            - world heading from the exporter, same frame as the player's,
  //                    so it needs the Z-mirror negation (see drawCar).
  //   estimatedHeading - already derived from successive *map* positions in
  //                    withEstimatedHeadings as atan2(dy, dx) + PI/2, so it is
  //                    map-space already and must not be negated.
  // Only the player's frame could be measured against the track tangent; no
  // opponents were on track at the time, so the yaw branch follows the player's
  // convention by construction rather than by measurement.
  const noseAngle = Number.isFinite(opponent.yaw)
    ? -opponent.yaw - Math.PI / 2
    : (Number.isFinite(opponent.estimatedHeading) ? opponent.estimatedHeading - Math.PI / 2 : null);

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

  if (noseAngle !== null) {
    ctx.rotate(noseAngle);
    ctx.beginPath();
    ctx.moveTo(radius * 1.65, 0);
    ctx.lineTo(radius * 0.45, radius * 0.52);
    ctx.lineTo(radius * 0.45, -radius * 0.52);
    ctx.closePath();
    ctx.fillStyle = 'rgba(255,255,255,0.92)';
    ctx.fill();
    ctx.rotate(-noseAngle);
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

export function drawTrajectory(ctx: CanvasRenderingContext2D, history: unknown[], scale: number) {
  if (!history || history.length < 2) return;

  ctx.save();
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.shadowBlur = 10 / scale;
  ctx.shadowColor = 'rgba(34,211,238,0.35)';

  for (let i = 1; i < history.length; i += 1) {
    const a = history[i - 1];
    const b = history[i];
    const previous = resolveSampleMapPosition(a);
    const current = resolveSampleMapPosition(b);
    const ax = previous?.x;
    const ay = previous?.y;
    const bx = current?.x;
    const by = current?.y;
    if (!Number.isFinite(ax) || !Number.isFinite(ay) || !Number.isFinite(bx) || !Number.isFinite(by)) continue;
    const alpha = Math.max(0.08, i / history.length);
    ctx.beginPath();
    ctx.moveTo(ax as number, ay as number);
    ctx.lineTo(bx as number, by as number);
    ctx.strokeStyle = `rgba(34,211,238,${alpha * 0.55})`;
    ctx.lineWidth = 3 / scale;
    ctx.stroke();
  }

  ctx.restore();
}
