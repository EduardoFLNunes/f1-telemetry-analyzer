import { describe, expect, it } from 'vitest';
import {
  DRIVER_STATES,
  drawBroadcastCar,
  drawBroadcastHud,
  drawBroadcastTrail,
  driverState,
  hudMetrics,
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

describe('driverState', () => {
  it('reads the pedals, with the brake winning over the throttle', () => {
    expect(driverState({ throttle: 1, brake: 0 })).toBe(DRIVER_STATES.power);
    expect(driverState({ throttle: 0, brake: 0.9 })).toBe(DRIVER_STATES.brake);
    // Both at once is a driver trailing the brake into a corner; that is
    // braking, and colouring it green would say the opposite.
    expect(driverState({ throttle: 1, brake: 0.4 })).toBe(DRIVER_STATES.brake);
    expect(driverState({ throttle: 0.02, brake: 0 })).toBe(DRIVER_STATES.coast);
    expect(driverState(null)).toBe(DRIVER_STATES.coast);
  });

  it('accepts pedals given as percentages', () => {
    expect(driverState({ throttle: 80, brake: 0 })).toBe(DRIVER_STATES.power);
    expect(driverState({ throttle: 0, brake: 45 })).toBe(DRIVER_STATES.brake);
  });

  it('keeps the three states apart by colour', () => {
    const colours = new Set(Object.values(DRIVER_STATES).map((state) => state.colour.join(',')));
    expect(colours.size).toBe(3);
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
    const colours = callsOf(ctx, 'stroke').map((call) => parseRgba(call.strokeStyle)!);
    const power = DRIVER_STATES.power.colour;
    const brake = DRIVER_STATES.brake.colour;
    expect(colours.some((c) => c.r === power[0] && c.g === power[1])).toBe(true);
    expect(colours.some((c) => c.r === brake[0] && c.g === brake[1])).toBe(true);
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
    const [r, g, b] = DRIVER_STATES.brake.colour;
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

describe('drawBroadcastHud', () => {
  const frame = { speedKmh: 198.4, lap_time: 73.21, throttle: 1, brake: 0, mapPosition: { x: 0, y: 0 } };

  it('reads out the speed, the state and the lap time', () => {
    const ctx = createFakeContext();
    expect(drawBroadcastHud(ctx, 700, 340, frame)).toBe(true);
    const text = callsOf(ctx, 'fillText').map((call) => String(call.args[0]));
    expect(text).toContain('198');
    expect(text).toContain('KM/H');
    expect(text).toContain(DRIVER_STATES.power.label);
    expect(text.some((line) => line.includes('1:13.210'))).toBe(true);
  });

  it('stacks the readout up the middle of the panel', () => {
    const ctx = createFakeContext();
    drawBroadcastHud(ctx, 700, 340, frame, { caption: 'INTERLAGOS' });
    const lines = callsOf(ctx, 'fillText');
    expect(lines.every((call) => call.args[1] === 350)).toBe(true);
    expect(ctx.textAlign).toBe('center');
    // Top to bottom: state, speed, unit, lap time, caption.
    const ys = lines.map((call) => call.args[2]);
    expect(ys[ys.length - 1]).toBeLessThan(340);
    expect(new Set(ys).size).toBe(lines.length);
  });

  it('draws in screen space so it holds still while the circuit moves', () => {
    const ctx = createFakeContext();
    drawBroadcastHud(ctx, 700, 340, frame);
    expect(callsOf(ctx, 'resetTransform').length).toBe(1);
  });

  it('shows the state colour, not a fixed one', () => {
    const braking = createFakeContext();
    drawBroadcastHud(braking, 700, 340, { ...frame, throttle: 0, brake: 1 });
    // The readout is drawn bottom-up, so the state label is the last line out.
    const label = callsOf(braking, 'fillText').at(-1)!;
    const [r, g, b] = DRIVER_STATES.brake.colour;
    expect(label.args[0]).toBe(DRIVER_STATES.brake.label);
    expect(label.fillStyle).toBe(`rgb(${r},${g},${b})`);
  });

  it('says it does not know rather than showing a wrong number', () => {
    const ctx = createFakeContext();
    drawBroadcastHud(ctx, 700, 340, { throttle: 0, brake: 0 });
    const text = callsOf(ctx, 'fillText').map((call) => String(call.args[0]));
    expect(text).toContain('--');
    expect(text.some((line) => line.includes('--:--.---'))).toBe(true);
  });

  it('stays out of the way when there is no room and no car', () => {
    const ctx = createFakeContext();
    expect(drawBroadcastHud(ctx, 700, 40, frame)).toBe(false);
    expect(drawBroadcastHud(ctx, 700, 340, null)).toBe(false);
    expect(ctx.calls.length).toBe(0);
  });

  it('sizes the number to the panel it has', () => {
    const small = hudMetrics(320, 180);
    const large = hudMetrics(1200, 700);
    expect(large.speed).toBeGreaterThan(small.speed);
    expect(small.speed).toBeGreaterThanOrEqual(20);
    expect(large.speed).toBeLessThanOrEqual(64);
    // A narrow panel is governed by its width, not its height.
    expect(hudMetrics(200, 900).speed).toBeLessThan(hudMetrics(900, 900).speed);
  });
});
