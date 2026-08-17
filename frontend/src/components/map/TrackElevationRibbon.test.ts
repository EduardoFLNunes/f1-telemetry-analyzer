import { describe, expect, it } from 'vitest';
import {
  advanceYaw,
  buildGeometry,
  carPosition,
  makeProjector,
  nearestStation,
  yawTarget,
} from './TrackElevationRibbon';

/**
 * A circuit shaped like a ring, which is enough for every property the ribbon
 * cares about: it closes, it has a centre, both edges carry their own height and
 * the road can be banked by giving the two edges different ones.
 */
function ringTrack(options: {
  count?: number;
  radius?: number;
  width?: number;
  height?: (angle: number) => number;
  bank?: (angle: number) => number;
} = {}) {
  const count = options.count ?? 80;
  const radius = options.radius ?? 200;
  const width = options.width ?? 10;
  const height = options.height ?? (() => 0);
  const bank = options.bank ?? (() => 0);

  const left = { x: [] as number[], y: [] as number[] };
  const right = { x: [] as number[], y: [] as number[] };
  const leftElevation: number[] = [];
  const rightElevation: number[] = [];

  for (let index = 0; index < count; index += 1) {
    const angle = (index / count) * Math.PI * 2;
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    left.x.push((radius + width / 2) * cos);
    left.y.push((radius + width / 2) * sin);
    right.x.push((radius - width / 2) * cos);
    right.y.push((radius - width / 2) * sin);
    leftElevation.push(height(angle) + bank(angle) / 2);
    rightElevation.push(height(angle) - bank(angle) / 2);
  }

  return {
    left_edge: left,
    right_edge: right,
    edgeElevation: { left: leftElevation, right: rightElevation },
  };
}

const ORIGIN = { x: 0, y: 0 };

describe('buildGeometry', () => {
  it('reads the height of both edges from edgeElevation', () => {
    const geometry = buildGeometry(ringTrack({ height: (angle) => 20 * Math.sin(angle) }));
    expect(geometry).not.toBeNull();
    expect(geometry!.stations.length).toBeGreaterThan(8);
    // Each station keeps its own left and right height -- that is what lets a
    // corner lean. A single centre line could not express it.
    const heights = geometry!.stations.map((station) => station.left[2]);
    expect(Math.max(...heights)).toBeGreaterThan(15);
    expect(Math.min(...heights)).toBeLessThan(-15);
  });

  it('falls back to the elevation carried on the edge itself', () => {
    const track: any = ringTrack();
    (track.left_edge as any).elevation = track.edgeElevation.left;
    (track.right_edge as any).elevation = track.edgeElevation.right;
    delete track.edgeElevation;
    expect(buildGeometry(track)).not.toBeNull();
  });

  it('refuses a track with no height on the edges', () => {
    const track: any = ringTrack();
    delete track.edgeElevation;
    // Without height there is no relief to draw, and the component says so
    // instead of drawing a flat ring pretending to be a circuit.
    expect(buildGeometry(track)).toBeNull();
  });

  it('refuses a track with too few samples to make a ribbon', () => {
    expect(buildGeometry(ringTrack({ count: 12 }))).toBeNull();
    expect(buildGeometry(null)).toBeNull();
    expect(buildGeometry({ left_edge: { x: [] }, right_edge: { x: [] } })).toBeNull();
  });

  it('skips samples whose height is missing rather than drawing them at zero', () => {
    const track = ringTrack({ height: () => 30 });
    track.edgeElevation.left[8] = null as any;
    track.edgeElevation.left[12] = null as any;
    const geometry = buildGeometry(track)!;
    expect(geometry.stations.every((station) => station.left[2] === 30)).toBe(true);
  });

  it('accepts z where the edge has no y', () => {
    const track: any = ringTrack();
    track.left_edge = { x: track.left_edge.x, z: track.left_edge.y };
    track.right_edge = { x: track.right_edge.x, z: track.right_edge.y };
    const geometry = buildGeometry(track);
    expect(geometry).not.toBeNull();
    expect(geometry!.radius).toBeGreaterThan(150);
  });

  it('measures the circuit so the frame does not breathe as it turns', () => {
    const geometry = buildGeometry(ringTrack({ radius: 300, height: (a) => 10 * Math.cos(a) }))!;
    expect(geometry.centre.x).toBeCloseTo(0, 6);
    expect(geometry.centre.y).toBeCloseTo(0, 6);
    expect(geometry.radius).toBeCloseTo(300, 0);
    expect(geometry.heightSpan).toBeCloseTo(20, 0);
  });

  it('never reports a height span of zero on a flat track', () => {
    // The span divides the vertical framing; a flat circuit must not blow it up.
    expect(buildGeometry(ringTrack())!.heightSpan).toBe(1);
  });
});

describe('makeProjector', () => {
  it('draws a climb above the flat road, not below it', () => {
    // The regression this pins: the canvas is scaled with a negated Y, so height
    // has to be added. The first version subtracted it and every hill in
    // Interlagos came out as a hole.
    const { project } = makeProjector(0, ORIGIN);
    const flat = project(0, 100, 0);
    const climb = project(0, 100, 12);
    expect(climb[1]).toBeGreaterThan(flat[1]);
  });

  it('keeps the ground horizontal instead of shearing it sideways', () => {
    // The other regression: an oblique projection displaced X by the depth,
    // which does not tip the camera, it tips the circuit. Moving a point along
    // the depth axis must not move it sideways on screen.
    for (const yaw of [0, 0.9, -2.2, Math.PI]) {
      const { project } = makeProjector(yaw, ORIGIN);
      const sin = Math.sin(yaw);
      const cos = Math.cos(yaw);
      const base = project(40, -60, 0);
      for (const step of [-150, -20, 35, 210]) {
        const moved = project(40 + step * sin, -60 + step * cos, 0);
        expect(moved[0]).toBeCloseTo(base[0], 8);
      }
    }
  });

  it('does not move a point sideways when it rises', () => {
    const { project } = makeProjector(1.1, ORIGIN);
    expect(project(30, 40, 25)[0]).toBeCloseTo(project(30, 40, 0)[0], 10);
  });

  it('foreshortens the plan and keeps some of the relief', () => {
    const { project } = makeProjector(0, ORIGIN);
    const depthStep = project(0, 100, 0)[1] - project(0, 0, 0)[1];
    // Pitched down: depth survives, shortened. Straight down would flatten it to
    // nothing and lose the relief with it.
    expect(depthStep).toBeGreaterThan(0);
    expect(depthStep).toBeLessThan(100);

    const heightStep = project(0, 0, 10)[1] - project(0, 0, 0)[1];
    expect(heightStep).toBeGreaterThan(0);
  });

  it('lifts height by the same amount whatever way the view is turned', () => {
    // Banking is a difference between two edge heights; it has to read the same
    // at every point of the lap, so rotation must not scale the height term.
    const steps = [0, 0.7, 2.9, -1.4].map((yaw) => {
      const { project } = makeProjector(yaw, ORIGIN);
      return project(120, -80, 4)[1] - project(120, -80, 0)[1];
    });
    for (const step of steps) expect(step).toBeCloseTo(steps[0], 10);
    expect(steps[0]).toBeGreaterThan(0);
  });

  it('leans a banked road and lays a flat one level', () => {
    const { project } = makeProjector(0, ORIGIN);
    const flatLeft = project(-5, 100, 0)[1];
    const flatRight = project(5, 100, 0)[1];
    expect(flatLeft).toBeCloseTo(flatRight, 10);

    const bankedLeft = project(-5, 100, 1.2)[1];
    const bankedRight = project(5, 100, 0)[1];
    expect(bankedLeft).toBeGreaterThan(bankedRight);
  });

  it('holds the car at the bottom centre as the view tracks it', () => {
    // The point of following the bearing: wherever the car is on the lap, the
    // camera turns so it sits in the same place on screen.
    const radius = 250;
    for (const bearing of [0, 1.3, 2.9, -0.6, -2.8]) {
      const car = { x: radius * Math.cos(bearing), y: radius * Math.sin(bearing) };
      const { project, depth } = makeProjector(yawTarget(car, ORIGIN), ORIGIN);
      const [x, y] = project(car.x, car.y, 0);
      expect(x).toBeCloseTo(0, 6);
      expect(y).toBeLessThan(0);
      // Nearest to the viewer, so the painter's sort draws it last, on top.
      expect(depth(car.x, car.y)).toBeCloseTo(-radius, 6);
    }
  });

  it('sorts the far side of the circuit behind the near side', () => {
    const { depth } = makeProjector(0, ORIGIN);
    expect(depth(0, 200)).toBeGreaterThan(depth(0, -200));
    expect(depth(0, 0)).toBeCloseTo(0, 10);
  });
});

describe('yawTarget and advanceYaw', () => {
  it('turns the view exactly once over a lap, so the laps join up', () => {
    // What the user asked for: the camera completes one revolution per lap and
    // hands over to the next lap without a jump.
    let previous = yawTarget({ x: 200, y: 0 }, ORIGIN);
    let travelled = 0;
    for (let step = 1; step <= 360; step += 1) {
      const bearing = (step / 360) * Math.PI * 2;
      const target = yawTarget({ x: 200 * Math.cos(bearing), y: 200 * Math.sin(bearing) }, ORIGIN);
      let delta = target - previous;
      while (delta > Math.PI) delta -= Math.PI * 2;
      while (delta < -Math.PI) delta += Math.PI * 2;
      travelled += delta;
      previous = target;
    }
    expect(travelled).toBeCloseTo(-Math.PI * 2, 6);
  });

  it('eases towards the target by a constant fraction of what is left', () => {
    const near = advanceYaw(0, 1);
    const far = advanceYaw(0, 2);
    expect(near).toBeGreaterThan(0);
    expect(near).toBeLessThan(1);
    expect(far / near).toBeCloseTo(2, 10);
  });

  it('takes the short way across the +/-pi seam', () => {
    // The seam is where a naive ease spins the whole circuit backwards. From
    // just under +pi to just over it, the step is small and forwards.
    const stepped = advanceYaw(3.10, -3.10);
    expect(stepped).toBeGreaterThan(3.10);
    expect(stepped - 3.10).toBeLessThan(0.05);
  });

  it('settles on the target instead of orbiting it', () => {
    // It settles on an angle equal to the target, not necessarily the same
    // number: from -2.5 the short way to 1.2 runs backwards through -pi, so the
    // view arrives at 1.2 - 2pi. Same heading, one fewer turn taken.
    for (const [from, to] of [[-2.5, 1.2], [0, 3], [3.1, -3.1]]) {
      let yaw = from;
      for (let step = 0; step < 400; step += 1) yaw = advanceYaw(yaw, to);
      let error = (yaw - to) % (Math.PI * 2);
      if (error > Math.PI) error -= Math.PI * 2;
      if (error < -Math.PI) error += Math.PI * 2;
      expect(error).toBeCloseTo(0, 6);
    }
  });

  it('never overshoots in one step', () => {
    for (const [from, to] of [[0, 3], [1, -1], [3.1, -3.1], [-2, 2]]) {
      const stepped = advanceYaw(from, to);
      let delta = to - from;
      while (delta > Math.PI) delta -= Math.PI * 2;
      while (delta < -Math.PI) delta += Math.PI * 2;
      expect(Math.abs(stepped - from)).toBeLessThanOrEqual(Math.abs(delta) + 1e-12);
      expect(Math.sign(stepped - from) === Math.sign(delta) || delta === 0).toBe(true);
    }
  });
});

describe('carPosition and nearestStation', () => {
  it('prefers the mapped position and falls back to the raw one', () => {
    expect(carPosition({ mapPosition: { x: 1, y: 2 }, x: 9, y: 9 })).toEqual({ x: 1, y: 2 });
    expect(carPosition({ x: 3, y: 4 })).toEqual({ x: 3, y: 4 });
  });

  it('reports no position rather than a broken one', () => {
    expect(carPosition(null)).toBeNull();
    expect(carPosition({})).toBeNull();
    expect(carPosition({ x: 'abc', y: 2 })).toBeNull();
    expect(carPosition({ x: NaN, y: 0 })).toBeNull();
  });

  it('puts the marker on the station the car is actually at', () => {
    const geometry = buildGeometry(ringTrack({ radius: 200, height: () => 5 }))!;
    const bearing = Math.PI / 2;
    const car = { x: 200 * Math.cos(bearing), y: 200 * Math.sin(bearing) };
    const index = nearestStation(geometry, car)!;
    const station = geometry.stations[index];
    const mx = (station.left[0] + station.right[0]) / 2;
    const my = (station.left[1] + station.right[1]) / 2;
    expect(Math.hypot(mx - car.x, my - car.y)).toBeLessThan(40);
  });

  it('has no station without a car', () => {
    const geometry = buildGeometry(ringTrack())!;
    expect(nearestStation(geometry, null)).toBeNull();
  });
});
