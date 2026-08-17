import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
  drawAsphaltSurface,
  drawClassifiedMarkings,
  drawKerbs,
  drawMiniMap,
  drawTrackSurface,
  mapDetail,
} from './OverlayRenderer';
import {
  FakePath2D,
  callsOf,
  createFakeContext,
  installFakePath2D,
  parseRgba,
} from '../../test/fakeCanvas';

const LIMITE = [255, 255, 255];
const BOXES = [234, 179, 8];
const SERVICO = [148, 163, 184];

/** 0 for black, 1 for white -- enough to say "light" or "dark" without a hex. */
function brightness(colour: any): number {
  const text = String(colour);
  const rgba = parseRgba(text);
  if (rgba) return (rgba.r + rgba.g + rgba.b) / (3 * 255);
  const hex = /^#([0-9a-f]{6})$/i.exec(text.trim());
  if (!hex) return NaN;
  const value = parseInt(hex[1], 16);
  return ((value >> 16 & 255) + (value >> 8 & 255) + (value & 255)) / (3 * 255);
}

function line(from: number, count = 6): number[][] {
  return Array.from({ length: count }, (_, index) => [from + index, index * 2]);
}

function ring(radius: number, count = 24): number[][] {
  return Array.from({ length: count }, (_, index) => {
    const angle = (index / count) * Math.PI * 2;
    return [radius * Math.cos(angle), radius * Math.sin(angle)];
  });
}

describe('mapDetail', () => {
  it('is full detail while the map is close and none when it is a thumbnail', () => {
    expect(mapDetail(0.30)).toBe(1);
    expect(mapDetail(2)).toBe(1);
    expect(mapDetail(0.08)).toBe(0);
    expect(mapDetail(0.001)).toBe(0);
  });

  it('falls away without a step between the two', () => {
    let previous = -1;
    for (let scale = 0.02; scale <= 0.4; scale += 0.01) {
      const detail = mapDetail(scale);
      expect(detail).toBeGreaterThanOrEqual(previous);
      expect(detail).toBeGreaterThanOrEqual(0);
      expect(detail).toBeLessThanOrEqual(1);
      previous = detail;
    }
    expect(mapDetail(0.19)).toBeCloseTo(0.5, 1);
  });
});

describe('drawClassifiedMarkings', () => {
  const track = () => ({
    markingGeometry: {
      features: [
        { kind: 'limite', points: ring(400), closed: true },
        { kind: 'servico', points: line(0) },
        { kind: 'boxes', points: line(50) },
      ],
    },
  });

  it('reports that it drew nothing when the paint has no verdicts', () => {
    // The caller uses this to fall back to the unclassified fill, so an older
    // cache still shows a track instead of a blank map.
    const ctx = createFakeContext();
    expect(drawClassifiedMarkings(ctx, {}, 0.3)).toBe(false);
    expect(drawClassifiedMarkings(ctx, { markingGeometry: { features: [] } }, 0.3)).toBe(false);
    expect(ctx.calls.length).toBe(0);
  });

  it('puts the track limit on top of the pit and service paint', () => {
    // Order is the whole point of the classification: the line that bounds the
    // track has to win wherever it crosses anything else.
    const ctx = createFakeContext();
    expect(drawClassifiedMarkings(ctx, track(), 0.3)).toBe(true);
    const painted = callsOf(ctx, 'stroke').map((call) => parseRgba(call.strokeStyle)!);
    expect(painted.map((colour) => [colour.r, colour.g, colour.b])).toEqual([
      SERVICO, BOXES, LIMITE,
    ]);
  });

  it('thins and fades the paint as the map pulls back', () => {
    // Zoomed out, every line holding its screen width closes the circuit into a
    // solid mass and the car disappears inside it.
    const close = createFakeContext();
    const far = createFakeContext();
    drawClassifiedMarkings(close, track(), 0.30);
    drawClassifiedMarkings(far, track(), 0.04);

    const closeStroke = callsOf(close, 'stroke').at(-1)!;
    const farStroke = callsOf(far, 'stroke').at(-1)!;
    expect(closeStroke.lineWidth * 0.30).toBeGreaterThan(farStroke.lineWidth * 0.04);
    expect(parseRgba(farStroke.strokeStyle)!.a).toBeLessThan(parseRgba(closeStroke.strokeStyle)!.a);
    expect(parseRgba(farStroke.strokeStyle)!.a).toBeGreaterThan(0.2);
  });

  it('takes the paint down to its real width once there is room for it', () => {
    const ctx = createFakeContext();
    drawClassifiedMarkings(ctx, track(), 40);
    // The track limit line as it is painted on the circuit, in metres.
    expect(callsOf(ctx, 'stroke').at(-1)!.lineWidth).toBeCloseTo(0.22, 6);
  });

  it('closes a ring and leaves an open line open', () => {
    const ctx = createFakeContext();
    drawClassifiedMarkings(ctx, track(), 0.3);
    expect(callsOf(ctx, 'closePath').length).toBe(1);
  });

  it('ignores a feature with nothing to draw', () => {
    const ctx = createFakeContext();
    const drawn = drawClassifiedMarkings(ctx, {
      markingGeometry: {
        features: [
          { kind: 'limite', points: [[0, 0]] },
          { kind: 'boxes', points: null },
          { kind: 'servico', points: line(0) },
        ],
      },
    }, 0.3);
    expect(drawn).toBe(true);
    expect(callsOf(ctx, 'stroke').length).toBe(1);
  });

  it('draws an unknown class rather than dropping it', () => {
    const ctx = createFakeContext();
    drawClassifiedMarkings(ctx, {
      markingGeometry: { features: [{ kind: 'algo-novo', points: line(0) }] },
    }, 0.3);
    expect(callsOf(ctx, 'stroke').length).toBe(1);
  });

  it('hands the context back as it found it', () => {
    const ctx = createFakeContext();
    ctx.lineCap = 'butt';
    ctx.lineWidth = 1;
    drawClassifiedMarkings(ctx, track(), 0.3);
    expect(ctx.lineCap).toBe('butt');
    expect(ctx.lineWidth).toBe(1);
  });
});

describe('drawAsphaltSurface', () => {
  it('fills the road and its holes in one even-odd path', () => {
    // Each loop that is not the outer boundary is a hole. Filled separately they
    // would paint over the infield; the parity is what keeps the middle clean.
    const ctx = createFakeContext();
    const drawn = drawAsphaltSurface(ctx, {
      asphaltSurface: { loops: [{ points: ring(500) }, { points: ring(420) }, { points: ring(80) }] },
    });
    expect(drawn).toBe(true);
    const fills = callsOf(ctx, 'fill');
    expect(fills.length).toBe(1);
    expect(fills[0].args[0]).toBe('evenodd');
    expect(callsOf(ctx, 'moveTo').length).toBe(3);
  });

  it('says nothing was drawn when the mesh carried no surface', () => {
    const ctx = createFakeContext();
    expect(drawAsphaltSurface(ctx, {})).toBe(false);
    expect(drawAsphaltSurface(ctx, { asphaltSurface: { loops: [] } })).toBe(false);
    expect(ctx.calls.length).toBe(0);
  });

  it('skips a loop that is not a polygon', () => {
    const ctx = createFakeContext();
    drawAsphaltSurface(ctx, { asphaltSurface: { loops: [{ points: [[0, 0], [1, 1]] }, { points: ring(50) }] } });
    expect(callsOf(ctx, 'moveTo').length).toBe(1);
  });
});

describe('drawTrackSurface', () => {
  const classified = {
    asphaltSurface: { loops: [{ points: ring(500) }] },
    markingGeometry: {
      features: [{ kind: 'limite', points: ring(400), closed: true }],
      polygons: [{ rings: [ring(400), ring(380)] }],
    },
  };

  it('draws the classified paint and not the unclassified fill', () => {
    const ctx = createFakeContext();
    drawTrackSurface(ctx, classified, null, 0.3);
    const flat = ctx.calls.filter((call: any) => String(call.fillStyle).startsWith('rgba(236,240,245'));
    expect(flat.length).toBe(0);
    expect(callsOf(ctx, 'stroke').length).toBeGreaterThan(0);
  });

  it('falls back to the flat fill for a track with no verdicts', () => {
    const ctx = createFakeContext();
    drawTrackSurface(ctx, { markingGeometry: { polygons: [{ rings: [ring(400), ring(380)] }] } }, null, 0.3);
    const flat = callsOf(ctx, 'fill').filter((call) => String(call.fillStyle).startsWith('rgba(236,240,245'));
    expect(flat.length).toBe(1);
    expect(flat[0].args[0]).toBe('evenodd');
  });

  it('puts the asphalt down before the paint that sits on it', () => {
    const ctx = createFakeContext();
    drawTrackSurface(ctx, classified, null, 0.3);
    const firstFill = ctx.calls.findIndex((call: any) => call.op === 'fill');
    const firstStroke = ctx.calls.findIndex((call: any) => call.op === 'stroke');
    expect(firstFill).toBeGreaterThanOrEqual(0);
    expect(firstFill).toBeLessThan(firstStroke);
  });
});

describe('drawKerbs', () => {
  const kerbs = { kerbGeometry: { polygons: [{ points: [[0, 0], [6, 0], [6, 1.5], [0, 1.5]] }] } };

  it('outlines the kerb so it survives a zoom that rasterises the stripes', () => {
    // A kerb is about a metre and a half across, under a pixel at map zoom; the
    // clipped stripe fill comes out as nothing, so the outline carries it.
    const ctx = createFakeContext();
    drawKerbs(ctx, kerbs, 0.1);
    const outline = callsOf(ctx, 'stroke');
    expect(outline.length).toBe(1);
    // Light against the near-black background, so the kerb still marks the
    // corner when it is a couple of pixels wide.
    expect(brightness(outline[0].strokeStyle)).toBeGreaterThan(0.7);
    expect(outline[0].lineWidth * 0.1).toBeGreaterThan(0.4);
  });

  it('gives the kerb its real edge once the stripes can be seen', () => {
    const close = createFakeContext();
    drawKerbs(close, kerbs, 30);
    expect(callsOf(close, 'stroke')[0].lineWidth).toBeCloseTo(0.15, 6);
    // Dark base with light teeth across it: one base fill, then the bars.
    const bars = callsOf(close, 'fillRect');
    expect(brightness(bars[0].fillStyle)).toBeLessThan(0.2);
    const teeth = bars.slice(1);
    expect(teeth.length).toBeGreaterThan(1);
    expect(teeth.every((call) => brightness(call.fillStyle) > 0.85)).toBe(true);
  });

  it('fades with the rest of the map', () => {
    const far = createFakeContext();
    const close = createFakeContext();
    drawKerbs(far, kerbs, 0.04);
    drawKerbs(close, kerbs, 0.3);
    expect(callsOf(far, 'stroke')[0].globalAlpha).toBeLessThan(callsOf(close, 'stroke')[0].globalAlpha);
  });

  it('ignores a track with no kerbs and a polygon that is not one', () => {
    const ctx = createFakeContext();
    drawKerbs(ctx, {}, 0.3);
    drawKerbs(ctx, { kerbGeometry: { polygons: [{ points: [[0, 0], [1, 1]] }] } }, 0.3);
    expect(callsOf(ctx, 'stroke').length).toBe(0);
  });
});

describe('drawMiniMap', () => {
  let restore: () => void;

  beforeEach(() => {
    restore = installFakePath2D();
    FakePath2D.created = 0;
  });
  afterEach(() => restore());

  const track = () => ({
    markingGeometry: {
      features: [
        { kind: 'limite', points: ring(400, 40), closed: true },
        { kind: 'boxes', points: ring(100, 40) },
        { kind: 'servico', points: ring(60, 40) },
      ],
    },
  });

  it('pins the inset to the top right corner whatever the canvas size', () => {
    for (const [width, height] of [[900, 600], [420, 380]]) {
      const ctx = createFakeContext();
      drawMiniMap(ctx, width, height, track(), null, { size: 120, margin: 14 });
      const frame = callsOf(ctx, 'rect')[0];
      expect(frame.args).toEqual([width - 120 - 14, 14, 120, 120]);
    }
  });

  it('traces the inset from the track limit alone', () => {
    // Not the pit lane, not the access roads: the inset answers where in the lap
    // the car is, and anything else is noise at that size.
    const ctx = createFakeContext();
    drawMiniMap(ctx, 900, 600, track(), null, { size: 120 });
    const path: FakePath2D = callsOf(ctx, 'stroke').at(-1)!.args[0];
    expect(path).toBeInstanceOf(FakePath2D);
    expect(path.ops.filter((op) => op.op === 'moveTo').length).toBe(1);
    const traced = path.ops.filter((op) => op.op === 'lineTo').length;
    expect(traced).toBe(39);
  });

  it('draws nothing when the track has no limit paint to trace', () => {
    const ctx = createFakeContext();
    drawMiniMap(ctx, 900, 600, { markingGeometry: { features: [{ kind: 'boxes', points: ring(100, 40) }] } }, null);
    drawMiniMap(ctx, 900, 600, {}, null);
    expect(ctx.calls.length).toBe(0);
  });

  it('marks the car on the inset, and leaves it off when there is no car', () => {
    const withCar = createFakeContext();
    drawMiniMap(withCar, 900, 600, track(), { x: 400, y: 0 });
    expect(callsOf(withCar, 'arc').length).toBe(1);

    const without = createFakeContext();
    drawMiniMap(without, 900, 600, track(), null);
    expect(callsOf(without, 'arc').length).toBe(0);

    const broken = createFakeContext();
    drawMiniMap(broken, 900, 600, track(), { x: NaN, y: 0 });
    expect(callsOf(broken, 'arc').length).toBe(0);
  });

  it('traces the outline once and reuses it every frame', () => {
    // This runs on every frame of the map; retracing the lap each time is the
    // difference between an inset and a stutter.
    const data = track();
    const ctx = createFakeContext();
    for (let frame = 0; frame < 30; frame += 1) drawMiniMap(ctx, 900, 600, data, { x: 400, y: 0 });
    expect(FakePath2D.created).toBe(1);
  });

  it('draws in screen space so it stays put while the map moves under it', () => {
    const ctx = createFakeContext();
    drawMiniMap(ctx, 900, 600, track(), { x: 400, y: 0 });
    expect(callsOf(ctx, 'resetTransform').length).toBe(1);
    // And it clips, so a car off the far side of the outline cannot spill out.
    expect(callsOf(ctx, 'clip').length).toBe(1);
  });
});
