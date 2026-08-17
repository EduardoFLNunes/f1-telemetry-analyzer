import { resolveSampleMapPosition, MapPosition } from '../../utils/spatialTransform';
import { formatLapTime } from '../../utils/lapFormat';

/**
 * The follow view as a broadcast graphic.
 *
 * A lap on television is three things and nothing else: the road, the car, and
 * a number. Everything here serves that. The car is a disc rather than a car
 * shape, because at this zoom a shape is a smudge and a disc is a position. The
 * road behind it is coloured by what the driver was doing there and fades out
 * over a few seconds, which turns the map into a short memory instead of a
 * diagram. The readout sits in the middle, big enough to be read from across a
 * room, because that is the whole point of a view that only shows one car.
 *
 * The colours say what the pedals did: on power, braking, or neither. A
 * broadcast would say DEPLOY and REGEN there; we do not model an ERS, and
 * inventing one on top of throttle and brake would be a graphic that lies.
 */

const TRAIL_SECONDS = 14;
const TRAIL_MAX_POINTS = 700;
// A lap wraps, and a replay can be scrubbed. Either way the next point is a
// long way from the last one, and joining them would draw a chord across the
// infield.
const TRAIL_MAX_GAP_METERS = 45;
const TRAIL_METERS = 1.5;
const TRAIL_MIN_PX = 3.2;
const TRAIL_TAIL_ALPHA = 0.06;

export const DRIVER_STATES = {
  power: { label: 'ACELERA', colour: [34, 197, 94] as [number, number, number] },
  brake: { label: 'FREIO', colour: [249, 115, 22] as [number, number, number] },
  coast: { label: 'INERCIA', colour: [161, 161, 170] as [number, number, number] },
};

export type DriverState = typeof DRIVER_STATES[keyof typeof DRIVER_STATES];

function pedal(value: unknown): number {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.max(0, Math.min(1, number > 1 ? number / 100 : number));
}

/** What the car is doing, in the three states a colour can carry. */
export function driverState(sample: any): DriverState {
  if (pedal(sample?.brake) > 0.05) return DRIVER_STATES.brake;
  if (pedal(sample?.throttle) > 0.12) return DRIVER_STATES.power;
  return DRIVER_STATES.coast;
}

export function speedKmh(sample: any): number | null {
  const direct = Number(sample?.speedKmh);
  if (Number.isFinite(direct)) return direct;
  const metric = Number(sample?.speed);
  return Number.isFinite(metric) ? metric * 3.6 : null;
}

function sampleClock(sample: any): number | null {
  for (const candidate of [sample?.lap_time, sample?.lapTime, sample?.lapSampleTime, sample?.timestamp]) {
    const number = Number(candidate);
    if (Number.isFinite(number)) return number;
  }
  return null;
}

/**
 * The last few seconds of driving, thinned to something a frame can draw.
 *
 * Falls back to a straight count when the samples carry no clock, so a lap with
 * broken timestamps still leaves a trail instead of nothing.
 */
export function trailWindow(samples: any[], seconds = TRAIL_SECONDS): any[] {
  if (!Array.isArray(samples) || samples.length < 2) return [];
  const last = samples[samples.length - 1];
  const now = sampleClock(last);

  let start = 0;
  if (now !== null) {
    for (let index = samples.length - 1; index >= 0; index -= 1) {
      const clock = sampleClock(samples[index]);
      if (clock !== null && now - clock > seconds) {
        start = index + 1;
        break;
      }
    }
  } else {
    start = Math.max(0, samples.length - 400);
  }

  const window = samples.slice(start);
  const stride = Math.max(1, Math.ceil(window.length / TRAIL_MAX_POINTS));
  if (stride === 1) return window;
  const thinned = window.filter((_, index) => index % stride === 0);
  if (thinned[thinned.length - 1] !== last) thinned.push(last);
  return thinned;
}

type TrailPoint = { position: MapPosition; sample: any };

function trailPoints(samples: any[]): TrailPoint[] {
  const points: TrailPoint[] = [];
  for (const sample of samples) {
    const position = resolveSampleMapPosition(sample);
    if (position && Number.isFinite(position.x) && Number.isFinite(position.y)) {
      points.push({ position, sample });
    }
  }
  return points;
}

/**
 * The road just driven, coloured by the pedals and fading into the past.
 *
 * Drawn segment by segment because the colour changes along it; the alpha ramp
 * is what makes it read as a trail rather than as a racing line.
 */
export function drawBroadcastTrail(ctx: CanvasRenderingContext2D, samples: any[], scale: number): boolean {
  const points = trailPoints(trailWindow(samples));
  if (points.length < 2 || !Number.isFinite(scale) || scale <= 0) return false;

  const width = Math.max(TRAIL_METERS, TRAIL_MIN_PX / scale);
  ctx.save();
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.lineWidth = width;

  for (let index = 1; index < points.length; index += 1) {
    const previous = points[index - 1];
    const current = points[index];
    const gap = Math.hypot(
      current.position.x - previous.position.x,
      current.position.y - previous.position.y,
    );
    if (gap > TRAIL_MAX_GAP_METERS) continue;

    const age = index / (points.length - 1);
    const alpha = TRAIL_TAIL_ALPHA + (1 - TRAIL_TAIL_ALPHA) * age * age;
    const [r, g, b] = driverState(current.sample).colour;
    ctx.strokeStyle = `rgba(${r},${g},${b},${alpha.toFixed(3)})`;
    ctx.beginPath();
    ctx.moveTo(previous.position.x, previous.position.y);
    ctx.lineTo(current.position.x, current.position.y);
    ctx.stroke();
  }

  ctx.restore();
  return true;
}

const CAR_RADIUS_METERS = 1.15;
const CAR_MIN_SCREEN_PX = 7;

/** The car as a disc: a white ring around what the driver is doing. */
export function drawBroadcastCar(ctx: CanvasRenderingContext2D, frame: any, scale: number): boolean {
  const position = resolveSampleMapPosition(frame);
  if (!position || !Number.isFinite(scale) || scale <= 0) return false;

  const radius = Math.max(CAR_RADIUS_METERS, CAR_MIN_SCREEN_PX / scale);
  const [r, g, b] = driverState(frame).colour;

  ctx.save();
  ctx.beginPath();
  ctx.arc(position.x, position.y, radius * 2.4, 0, Math.PI * 2);
  ctx.fillStyle = `rgba(${r},${g},${b},0.16)`;
  ctx.fill();

  ctx.beginPath();
  ctx.arc(position.x, position.y, radius, 0, Math.PI * 2);
  ctx.fillStyle = `rgb(${r},${g},${b})`;
  ctx.fill();
  ctx.lineWidth = Math.max(0.28, 2.4 / scale);
  ctx.strokeStyle = '#ffffff';
  ctx.stroke();
  ctx.restore();
  return true;
}

/** Sizes for the readout, from the panel it has to fit in. */
export function hudMetrics(width: number, height: number) {
  const speed = Math.max(20, Math.min(64, Math.round(Math.min(height * 0.20, width * 0.11))));
  return {
    speed,
    label: Math.max(9, Math.round(speed * 0.26)),
    unit: Math.max(8, Math.round(speed * 0.20)),
    lap: Math.max(8, Math.round(speed * 0.21)),
  };
}

/**
 * Speed, state and lap time, centred under the car.
 *
 * Drawn in screen space after the camera is restored, so it holds still while
 * the circuit moves behind it.
 */
export function drawBroadcastHud(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  frame: any,
  options: { lapTime?: number | null; caption?: string | null } = {},
): boolean {
  if (!frame || width < 80 || height < 70) return false;

  const state = driverState(frame);
  const speed = speedKmh(frame);
  const font = hudMetrics(width, height);
  const centre = Math.round(width / 2);
  const lapTime = options.lapTime ?? Number(frame?.lap_time ?? frame?.lapTime);
  const caption = options.caption;

  ctx.save();
  ctx.resetTransform();
  ctx.textAlign = 'center';
  ctx.textBaseline = 'alphabetic';
  // The readout sits over whatever the camera is on -- often grey asphalt, not
  // the black the numbers were designed against. The shadow is what keeps them
  // readable there without a panel behind them.
  ctx.shadowColor = 'rgba(0,0,0,0.9)';
  ctx.shadowBlur = Math.round(font.speed * 0.4);

  let cursor = Math.round(height - (caption ? font.lap * 2.6 : font.lap * 1.4));

  if (caption) {
    ctx.font = `${font.lap}px "JetBrains Mono", monospace`;
    ctx.fillStyle = 'rgba(148,163,184,0.6)';
    ctx.fillText(caption, centre, Math.round(height - font.lap * 0.9));
  }

  ctx.font = `700 ${font.lap}px "JetBrains Mono", monospace`;
  ctx.fillStyle = 'rgba(226,232,240,0.85)';
  ctx.fillText(`VOLTA  ${formatLapTime(Number.isFinite(lapTime as number) ? (lapTime as number) : null)}`, centre, cursor);

  cursor -= Math.round(font.unit * 1.7);
  ctx.font = `${font.unit}px "JetBrains Mono", monospace`;
  ctx.fillStyle = 'rgba(226,232,240,0.72)';
  ctx.fillText('KM/H', centre, cursor);

  cursor -= Math.round(font.speed * 0.95);
  ctx.font = `700 ${font.speed}px "JetBrains Mono", monospace`;
  ctx.fillStyle = '#ffffff';
  ctx.fillText(speed === null ? '--' : String(Math.round(speed)), centre, cursor);

  cursor -= Math.round(font.speed * 0.62);
  const [r, g, b] = state.colour;
  ctx.font = `700 ${font.label}px "JetBrains Mono", monospace`;
  ctx.fillStyle = `rgb(${r},${g},${b})`;
  ctx.fillText(state.label, centre, cursor);

  ctx.restore();
  return true;
}
