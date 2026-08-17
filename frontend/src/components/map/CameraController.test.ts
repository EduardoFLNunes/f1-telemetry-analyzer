import { describe, expect, it } from 'vitest';
import { applyCameraTransform, computeTrackBounds, FOLLOW_VIEW_METERS } from './CameraController';
import { createFakeContext, opSequence, callsOf } from '../../test/fakeCanvas';

const BOUNDS = computeTrackBounds({
  left_edge: { x: [-100, 100], y: [-100, 100] },
  right_edge: { x: [-90, 90], y: [-90, 90] },
});

const FOLLOW = { mode: 'FOLLOW', zoom: 1, offset: { x: 0, y: 0 } };
const car = (x: number, y: number, heading = 1.3) => ({ mapPosition: { x, y }, heading });

describe('the follow camera', () => {
  it('pans with the car and leaves the circuit where it is', () => {
    // Turning the map to keep the car's nose up spins the whole world under a
    // car that never appears to turn, and no corner looks like itself twice.
    const ctx = createFakeContext();
    applyCameraTransform(ctx, 800, 400, BOUNDS, FOLLOW, car(120, -60));
    expect(opSequence(ctx)).toEqual(['translate', 'scale', 'translate']);
    expect(opSequence(ctx)).not.toContain('rotate');
  });

  it('puts the car in the middle of the panel', () => {
    const ctx = createFakeContext();
    applyCameraTransform(ctx, 800, 400, BOUNDS, FOLLOW, car(120, -60));
    const [toCentre, toCar] = callsOf(ctx, 'translate');
    expect(toCentre.args).toEqual([400, 200]);
    expect(toCar.args).toEqual([-120, 60]);
  });

  it('holds a fixed stretch of road across the panel, scaled by the zoom', () => {
    const ctx = createFakeContext();
    const scale = applyCameraTransform(ctx, 800, 400, BOUNDS, FOLLOW, car(0, 0));
    expect(scale).toBeCloseTo(400 / FOLLOW_VIEW_METERS, 6);
    expect(callsOf(ctx, 'scale')[0].args).toEqual([scale, scale]);

    const zoomed = createFakeContext();
    const zoomedScale = applyCameraTransform(zoomed, 800, 400, BOUNDS, { ...FOLLOW, zoom: 2 }, car(0, 0));
    expect(zoomedScale).toBeCloseTo(scale * 2, 6);
  });

  it('falls back to the whole circuit when there is no car to follow', () => {
    const ctx = createFakeContext();
    const scale = applyCameraTransform(ctx, 800, 400, BOUNDS, FOLLOW, { speed: 12 });
    // Framed from the bounds instead, which is the overview transform.
    expect(scale).toBeCloseTo(Math.min(800 / BOUNDS.w, 400 / BOUNDS.h) * 0.84, 6);
  });
});

describe('the overview camera', () => {
  it('frames the circuit and honours the pan offset', () => {
    const ctx = createFakeContext();
    applyCameraTransform(ctx, 800, 400, BOUNDS, { mode: 'OVERVIEW', zoom: 1, offset: { x: 30, y: -10 } }, null);
    const [toCentre, toTrack] = callsOf(ctx, 'translate');
    expect(toCentre.args).toEqual([430, 190]);
    expect(toTrack.args).toEqual([-BOUNDS.cx, -BOUNDS.cy]);
  });
});

describe('computeTrackBounds', () => {
  it('covers the track, the car and the rivals on it', () => {
    const bounds = computeTrackBounds(
      { left_edge: { x: [0, 10], y: [0, 10] }, right_edge: { x: [2, 8], y: [2, 8] } },
      [{ mapPosition: { x: -50, y: 0 } }],
      { mapPosition: { x: 0, y: 90 } },
      [{ x: 200, y: -30 }],
    );
    expect(bounds.minX).toBe(-50);
    expect(bounds.maxX).toBe(200);
    expect(bounds.maxY).toBe(90);
    expect(bounds.cx).toBeCloseTo(75, 6);
  });

  it('falls back to a square rather than dividing by nothing', () => {
    const bounds = computeTrackBounds(null);
    expect(bounds.w).toBeGreaterThan(0);
    expect(bounds.h).toBeGreaterThan(0);
  });
});
