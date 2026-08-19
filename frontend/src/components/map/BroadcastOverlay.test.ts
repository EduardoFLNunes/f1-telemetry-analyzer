import { describe, expect, it } from 'vitest';
import {
  DRIVER_STATES,
  drawBroadcastCar,
  drawBroadcastTrail,
  driveBalance,
  driveColour,
  driverState,
  speedKmh,
  trailWindow,
} from './BroadcastOverlay';
import { callsOf, createFakeContext, parseRgba } from '../../test/fakeCanvas';

/** A stretch of driving, one sample every tenth of a second. */
function drive(count: number, options: { throttle?: number; brake?: number; step?: number } = {}): any[] {
  const step = options.step ?? 0.1;
  return Array.from({ length: count }, (_, index) => ({
    lap_time: index * step,
    mapPosition: { x: index * 4, y: 0 },
    speed: 60,
    throttle: options.throttle ?? 1,
    brake: options.brake ?? 0,
  }));
}

describe('driveBalance', () => {
  it('reads the pedals as one number, with the brake deciding', () => {
    expect(driveBalance({ throttle: 1, brake: 0 })).toBeCloseTo(1, 6);
    expect(driveBalance({ throttle: 0, brake: 1 })).toBeCloseTo(-1, 6);
    expect(driveBalance({ throttle: 0, brake: 0 })).toBe(0);
    // Trailing the brake into a corner is braking, whatever the throttle says.
    expect(driveBalance({ throttle: 1, brake: 0.4 })).toBeCloseTo(-0.4, 6);
  });

  it('accepts pedals given as percentages', () => {
    expect(driveBalance({ throttle: 80, brake: 0 })).toBeCloseTo(0.8, 6);
    expect(driveBalance({ throttle: 0, brake: 45 })).toBeCloseTo(-0.45, 6);
  });

  it('is zero for a sample that says nothing', () => {
    expect(driveBalance(null)).toBe(0);
    expect(driveBalance({ throttle: 'abc' })).toBe(0);
  });
});

describe('driveColour', () => {
  it('moves without a step from the brake to the power', () => {
    // The seam this replaced: green until one sample, orange from the next.
    let previous = driveColour(-1);
    let biggestJump = 0;
    for (let balance = -1; balance <= 1.0001; balance += 0.02) {
      const colour = driveColour(balance);
      const jump = Math.abs(colour[0] - previous[0])
        + Math.abs(colour[1] - previous[1])
        + Math.abs(colour[2] - previous[2]);
      biggestJump = Math.max(biggestJump, jump);
      previous = colour;
    }
    expect(biggestJump).toBeLessThan(20);
  });

  it('keeps the two ends far apart, so the trail still says which is which', () => {
    const brake = driveColour(-1);
    const power = driveColour(1);
    expect(brake[0]).toBeGreaterThan(power[0]);   // red channel: braking is warm
    expect(power[1]).toBeGreaterThan(brake[1]);   // green channel: power is green
  });

  it('passes through a neutral tone at coasting', () => {
    const [r, g, b] = driveColour(0);
    expect(Math.abs(r - g)).toBeLessThan(20);
    expect(Math.abs(g - b)).toBeLessThan(20);
  });

  it('clamps anything beyond the pedals', () => {
    expect(driveColour(5)).toEqual(driveColour(1));
    expect(driveColour(-5)).toEqual(driveColour(-1));
    expect(driveColour(NaN)).toEqual(driveColour(0));
  });
});

describe('driverState', () => {
  it('names what the car is doing', () => {
    expect(driverState({ throttle: 1, brake: 0 }).label).toBe(DRIVER_STATES.power.label);
    expect(driverState({ throttle: 0, brake: 0.9 }).label).toBe(DRIVER_STATES.brake.label);
    expect(driverState({ throttle: 1, brake: 0.4 }).label).toBe(DRIVER_STATES.brake.label);
    expect(driverState({ throttle: 0.02, brake: 0 }).label).toBe(DRIVER_STATES.coast.label);
    expect(driverState(null).label).toBe(DRIVER_STATES.coast.label);
  });

  it('carries the colour of its own balance', () => {
    const state = driverState({ throttle: 0, brake: 0.6 });
    expect(state.colour).toEqual(driveColour(-0.6));
  });
});

describe('speedKmh', () => {
  it('takes km/h as given and converts what the game sends in m/s', () => {
    expect(speedKmh({ speedKmh: 214 })).toBe(214);
    expect(speedKmh({ speed: 50 })).toBeCloseTo(180, 6);
    expect(speedKmh({})).toBeNull();
  });
});

describe('trailWindow', () => {
  it('keeps the last few seconds and drops what is older', () => {
    const window = trailWindow(drive(400), 14);   // 40 s of driving
    expect(window.length).toBeLessThan(400);
    expect(window[window.length - 1]).toEqual(drive(400)[399]);
    const span = window[window.length - 1].lap_time - window[0].lap_time;
    expect(span).toBeLessThanOrEqual(14.001);
    expect(span).toBeGreaterThan(13);
  });

  it('thins a dense window but never loses the car', () => {
    const dense = Array.from({ length: 9000 }, (_, index) => ({
      lap_time: index * 0.001,
      mapPosition: { x: index, y: 0 },
    }));
    const window = trailWindow(dense, 14);
    expect(window.length).toBeLessThanOrEqual(701);
    // The last sample is where the car is now; a thinned trail that stops short
    // of it leaves a gap between the road and the marker.
    expect(window[window.length - 1]).toBe(dense[8999]);
  });

  it('still leaves a trail when the samples carry no clock', () => {
    const noClock = Array.from({ length: 900 }, (_, index) => ({ mapPosition: { x: index, y: 0 } }));
    const window = trailWindow(noClock);
    expect(window.length).toBeGreaterThan(100);
    expect(window[window.length - 1]).toBe(noClock[899]);
  });

  it('has nothing to draw from a single point', () => {
    expect(trailWindow([])).toEqual([]);
    expect(trailWindow([{ mapPosition: { x: 0, y: 0 } }])).toEqual([]);
  });
});

describe('drawBroadcastTrail', () => {
  it('fades into the past so it reads as a trail, not a racing line', () => {
    const ctx = createFakeContext();
    expect(drawBroadcastTrail(ctx, drive(60), 4)).toBe(true);
    const strokes = callsOf(ctx, 'stroke');
    expect(strokes.length).toBeGreaterThan(10);
    const oldest = parseRgba(strokes[0].strokeStyle)!.a;
    const newest = parseRgba(strokes[strokes.length - 1].strokeStyle)!.a;
    expect(newest).toBeGreaterThan(oldest);
    expect(newest).toBeGreaterThan(0.9);
    expect(oldest).toBeLessThan(0.2);
  });

  it('colours the road by what the driver was doing on it', () => {
    const ctx = createFakeContext();
    const samples = [...drive(20), ...drive(20, { throttle: 0, brake: 1, step: 0.1 })
      .map((sample, index) => ({ ...sample, lap_time: 2 + index * 0.1, mapPosition: { x: 80 + index * 4, y: 0 } }))];
    drawBroadcastTrail(ctx, samples, 4);
    const flat = callsOf(ctx, 'stroke')
      .map((call) => parseRgba(call.strokeStyle))
      .filter((colour): colour is NonNullable<typeof colour> => Boolean(colour));
    const power = driveColour(1);
    const brake = driveColour(-1);
    expect(flat.some((c) => c.r === power[0] && c.g === power[1])).toBe(true);
    expect(flat.some((c) => c.r === brake[0] && c.g === brake[1])).toBe(true);
  });

  it('carries a change of pedal along the segment instead of at the joint', () => {
    // Twenty samples a second is coarse: a lift lands between two points, and a
    // flat colour per segment shows it as a step.
    const ctx = createFakeContext();
    const samples = [
      { lap_time: 0.0, mapPosition: { x: 0, y: 0 }, throttle: 1, brake: 0 },
      { lap_time: 0.1, mapPosition: { x: 4, y: 0 }, throttle: 1, brake: 0 },
      { lap_time: 0.2, mapPosition: { x: 8, y: 0 }, throttle: 0, brake: 1 },
      { lap_time: 0.3, mapPosition: { x: 12, y: 0 }, throttle: 0, brake: 1 },
    ];
    drawBroadcastTrail(ctx, samples, 4);
    const gradients = callsOf(ctx, 'stroke').filter((call) => typeof call.strokeStyle === 'object');
    expect(gradients.length).toBe(1);
  });

  it('does not draw a chord across the infield when the lap wraps', () => {
    // The sample after the finish line is hundreds of metres from the one
    // before it; joining them would put a straight line through the middle.
    const samples = [
      ...drive(10),
      { lap_time: 1.1, mapPosition: { x: -900, y: 400 }, throttle: 1, brake: 0 },
      { lap_time: 1.2, mapPosition: { x: -896, y: 400 }, throttle: 1, brake: 0 },
    ];
    const ctx = createFakeContext();
    drawBroadcastTrail(ctx, samples, 4);
    const jumps = callsOf(ctx, 'lineTo').filter((call, index) => {
      const from = callsOf(ctx, 'moveTo')[index];
      return from && Math.hypot(call.args[0] - from.args[0], call.args[1] - from.args[1]) > 45;
    });
    expect(jumps.length).toBe(0);
  });

  it('says it drew nothing rather than drawing a stub', () => {
    const ctx = createFakeContext();
    expect(drawBroadcastTrail(ctx, [], 4)).toBe(false);
    expect(drawBroadcastTrail(ctx, drive(30), 0)).toBe(false);
    expect(drawBroadcastTrail(ctx, [{ foo: 1 }, { bar: 2 }] as any, 4)).toBe(false);
    expect(ctx.calls.length).toBe(0);
  });

  it('holds a visible width when the map is pulled back', () => {
    const close = createFakeContext();
    const far = createFakeContext();
    drawBroadcastTrail(close, drive(30), 8);
    drawBroadcastTrail(far, drive(30), 0.2);
    expect(callsOf(close, 'stroke')[0].lineWidth).toBeCloseTo(1.5, 6);
    expect(callsOf(far, 'stroke')[0].lineWidth * 0.2).toBeGreaterThan(3);
  });
});

describe('drawBroadcastCar', () => {
  it('draws a disc in the state colour inside a white ring', () => {
    const ctx = createFakeContext();
    expect(drawBroadcastCar(ctx, { mapPosition: { x: 10, y: 20 }, brake: 1 }, 5)).toBe(true);
    const discs = callsOf(ctx, 'arc');
    expect(discs.length).toBe(2);
    // Halo first, then the car itself, both on the car.
    expect(discs.every((call) => call.args[0] === 10 && call.args[1] === 20)).toBe(true);
    expect(discs[0].args[2]).toBeGreaterThan(discs[1].args[2]);
    const body = callsOf(ctx, 'fill').at(-1)!;
    const [r, g, b] = driveColour(-1);
    expect(body.fillStyle).toBe(`rgb(${r},${g},${b})`);
    expect(callsOf(ctx, 'stroke')[0].strokeStyle).toBe('#ffffff');
  });

  it('never shrinks below a few pixels, however far the map pulls back', () => {
    const ctx = createFakeContext();
    drawBroadcastCar(ctx, { mapPosition: { x: 0, y: 0 }, throttle: 1 }, 0.1);
    const radius = callsOf(ctx, 'arc')[1].args[2];
    expect(radius * 0.1).toBeGreaterThanOrEqual(7);
  });

  it('draws nothing without a position on the map', () => {
    const ctx = createFakeContext();
    expect(drawBroadcastCar(ctx, null, 5)).toBe(false);
    expect(drawBroadcastCar(ctx, { speed: 50 }, 5)).toBe(false);
    expect(ctx.calls.length).toBe(0);
  });
});
