import { resolveSampleMapPosition, MapPosition } from '../../utils/spatialTransform';

/**
 * The follow view as a broadcast graphic.
 *
 * A lap on television is three things and nothing else: the road, the car, and
 * a number. Everything here serves that. The car is a disc rather than a car
 * shape, because at this zoom a shape is a smudge and a disc is a position. The
 * road behind it is coloured by what the driver was doing there and fades out
 * over a few seconds, which turns the map into a short memory instead of a
 * diagram. The readout sits in the bottom right corner, big enough to be read
 * from across a room and clear of the car it describes.
 *
 * The colours say what the pedals did, on a ramp from full brake through
 * coasting to full power. A broadcast would say DEPLOY and REGEN there; we do
 * not model an ERS, and inventing one on top of throttle and brake would be a
 * graphic that lies.
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

export type Rgb = [number, number, number];

/**
 * The pedals as one number, and that number as a colour.
 *
 * Three fixed colours drew a hard seam every time the driver lifted: green
 * until one sample, orange from the next, with nothing in between. What the
 * driver actually does is continuous -- ease off, coast, squeeze the brake --
 * and the road behind the car should say so. So the pedals collapse to a single
 * balance from -1 (full brake) through 0 (coasting) to +1 (full power), and the
 * colour is read off a ramp at that point.
 *
 * The brake decides whenever it is touched, even with the throttle still open:
 * trailing the brake into a corner is braking, and painting it green would say
 * the opposite.
 */
const DRIVE_RAMP: Array<[number, Rgb]> = [
  [-1.00, [239, 68, 68]],     // full brake
  [-0.35, [249, 115, 22]],    // easing the brake off
  [0.00, [161, 161, 170]],    // coasting
  [0.35, [163, 230, 53]],     // feeding the throttle back in
  [1.00, [34, 197, 94]],      // full power
];

export const DRIVER_STATES = {
  power: { label: 'ACELERA' },
  brake: { label: 'FREIO' },
  coast: { label: 'INERCIA' },
};

export type DriverState = { label: string; colour: Rgb; balance: number };

function pedal(value: unknown): number {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.max(0, Math.min(1, number > 1 ? number / 100 : number));
}

/** -1 hard on the brake, 0 coasting, +1 hard on the power. */
export function driveBalance(sample: any): number {
  const brake = pedal(sample?.brake);
  if (brake > 0.02) return -brake;
  return pedal(sample?.throttle);
}

/** The ramp, read at one point. */
export function driveColour(balance: number): Rgb {
  const point = Math.max(-1, Math.min(1, Number(balance) || 0));
  for (let index = 1; index < DRIVE_RAMP.length; index += 1) {
    const [toStop, to] = DRIVE_RAMP[index];
    if (point > toStop && index < DRIVE_RAMP.length - 1) continue;
    const [fromStop, from] = DRIVE_RAMP[index - 1];
    const span = toStop - fromStop;
    const t = span === 0 ? 0 : Math.max(0, Math.min(1, (point - fromStop) / span));
    return [
      Math.round(from[0] + (to[0] - from[0]) * t),
      Math.round(from[1] + (to[1] - from[1]) * t),
      Math.round(from[2] + (to[2] - from[2]) * t),
    ];
  }
  return DRIVE_RAMP[DRIVE_RAMP.length - 1][1];
}

/** What the car is doing: a word for the readout, a colour for the road. */
export function driverState(sample: any): DriverState {
  const balance = driveBalance(sample);
  const label = balance <= -0.02
    ? DRIVER_STATES.brake.label
    : (balance >= 0.12 ? DRIVER_STATES.power.label : DRIVER_STATES.coast.label);
  return { label, colour: driveColour(balance), balance };
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

/** How far apart two ramp colours are, summed over the channels. */
function colourDistance(from: Rgb, to: Rgb): number {
  return Math.abs(from[0] - to[0]) + Math.abs(from[1] - to[1]) + Math.abs(from[2] - to[2]);
}

function rgba(colour: Rgb, alpha: number): string {
  return `rgba(${colour[0]},${colour[1]},${colour[2]},${alpha.toFixed(3)})`;
}

const TRAIL_BLEND_DELTA = 24;

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
    const from = driveColour(driveBalance(previous.sample));
    const to = driveColour(driveBalance(current.sample));

    // Where the pedals changed between two samples, the segment carries the
    // change along its own length instead of switching colour at the joint.
    // Twenty samples a second is coarse enough that a lift shows up as a step
    // otherwise, which is the seam this is here to remove.
    if (colourDistance(from, to) > TRAIL_BLEND_DELTA) {
      const gradient = ctx.createLinearGradient(
        previous.position.x, previous.position.y,
        current.position.x, current.position.y,
      );
      gradient.addColorStop(0, rgba(from, alpha));
      gradient.addColorStop(1, rgba(to, alpha));
      ctx.strokeStyle = gradient;
    } else {
      ctx.strokeStyle = rgba(to, alpha);
    }
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
