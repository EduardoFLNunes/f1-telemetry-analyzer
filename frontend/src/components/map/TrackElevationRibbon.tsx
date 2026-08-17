import React, { useEffect, useMemo, useRef, useState } from 'react';

/**
 * The lap seen from outside, turning to keep the car in front of the viewer.
 *
 * Two things make this readable that a flat map cannot show. The road is tilted
 * as the mesh has it -- both edges carry their own height, so a banked corner
 * leans here instead of lying flat; the AI line is one thread down the middle of
 * the road and cannot express banking at all. And the whole circuit rotates as
 * the car goes round, so the corner the car is in always faces the viewer. Over
 * a lap the view turns exactly once, which means the end of one lap hands over
 * to the start of the next without a jump.
 *
 * The rotation follows the car's bearing from the centre of the circuit rather
 * than its lap distance. Bearing pins the car to one place on screen; distance
 * would turn at a constant rate and let the car drift around the ribbon. Bearing
 * is not monotonic through the infield, so it is unwrapped and eased rather than
 * followed exactly -- otherwise the view snaps back and forth in the esses.
 */

export type Station = {
  left: [number, number, number];   // x, y, height
  right: [number, number, number];
  shade: number;
};

export type Geometry = {
  stations: Station[];
  centre: { x: number; y: number };
  radius: number;
  heightSpan: number;
};

// The camera is pitched down towards the circuit, and that is all it does: the
// ground plane stays horizontal and only shortens vertically with the pitch.
//
// The first version instead sheared depth sideways as well -- an oblique
// projection -- which does not tip the camera, it tips the ground. Raising the
// depth to make the view more isometric therefore leaned the whole circuit over.
// With a pitch, sin governs how much of the lap's depth survives on screen and
// cos how much of the height does: straight down would be a flat map with no
// relief, straight on would be a side elevation with no plan.
const PITCH_SIN = 0.55;                                  // about 33 degrees
const PITCH_COS = Math.sqrt(1 - PITCH_SIN * PITCH_SIN);
// 43 m of elevation over 4.3 km of lap is a flat line at true scale.
const HEIGHT_EXAGGERATION = 3;
const GRADIENT_FULL_SCALE = 0.08;
// One quad per this many stations. 2680 fills a frame is too many; a quarter of
// them is 6 m of road each, which is finer than this is ever drawn.
const STATION_STEP = 4;
// How hard the view chases the car's bearing. Lower is calmer through the esses.
const YAW_EASING = 0.12;

const RAMP: Array<[number, number, number]> = [
  [56, 152, 220], [70, 96, 130], [86, 92, 104], [170, 108, 62], [236, 132, 46],
];

function rampColour(t: number): string {
  const scaled = Math.max(0, Math.min(1, t)) * (RAMP.length - 1);
  const index = Math.min(RAMP.length - 2, Math.floor(scaled));
  const local = scaled - index;
  const [r1, g1, b1] = RAMP[index];
  const [r2, g2, b2] = RAMP[index + 1];
  const mix = (a: number, b: number) => Math.round(a + (b - a) * local);
  return `rgb(${mix(r1, r2)},${mix(g1, g2)},${mix(b1, b2)})`;
}

/**
 * The camera at a given yaw: where a point of road lands, and how far away it is.
 *
 * `project` turns the circuit around its centre, flattens the depth by the pitch
 * and lifts the height by what is left of it. `depth` is the same rotation's
 * far-to-near axis, which is all the painter's sort needs.
 */
export function makeProjector(yaw: number, centre: { x: number; y: number }) {
  const cos = Math.cos(yaw);
  const sin = Math.sin(yaw);
  return {
    // The canvas is drawn with a negated vertical scale, so a larger Y here is
    // higher on screen -- height has to be added. Subtracting it, as the first
    // version did, drew every climb as a descent.
    project(x: number, y: number, height: number): [number, number] {
      const dx = x - centre.x;
      const dy = y - centre.y;
      const rx = dx * cos - dy * sin;
      const ry = dx * sin + dy * cos;
      return [rx, ry * PITCH_SIN + height * HEIGHT_EXAGGERATION * PITCH_COS];
    },
    depth(x: number, y: number): number {
      return (x - centre.x) * sin + (y - centre.y) * cos;
    },
  };
}

/** The yaw that puts the car at the front of the view. */
export function yawTarget(position: { x: number; y: number }, centre: { x: number; y: number }): number {
  return -Math.atan2(position.y - centre.y, position.x - centre.x) - Math.PI / 2;
}

/**
 * A step of the view towards `target`, unwrapped so the turn never doubles back
 * across the +/-pi seam.
 */
export function advanceYaw(current: number, target: number): number {
  let delta = target - current;
  while (delta > Math.PI) delta -= Math.PI * 2;
  while (delta < -Math.PI) delta += Math.PI * 2;
  return current + delta * YAW_EASING;
}

export function buildGeometry(trackData: any): Geometry | null {
  const left = trackData?.left_edge;
  const right = trackData?.right_edge;
  const elevation = trackData?.edgeElevation;
  if (!left?.x?.length || !right?.x?.length) return null;

  const leftHeight: number[] = elevation?.left || left.elevation;
  const rightHeight: number[] = elevation?.right || right.elevation;
  if (!Array.isArray(leftHeight) || !Array.isArray(rightHeight)) return null;

  const gradient: number[] = Array.isArray(trackData?.centerline?.gradient) ? trackData.centerline.gradient : [];
  const leftY = left.y || left.z;
  const rightY = right.y || right.z;
  const count = Math.min(left.x.length, right.x.length, leftHeight.length, rightHeight.length);
  if (count < 8) return null;

  const stations: Station[] = [];
  let sumX = 0;
  let sumY = 0;
  for (let index = 0; index < count; index += STATION_STEP) {
    if (leftHeight[index] == null || rightHeight[index] == null) continue;
    const gradientAt = gradient[index] ?? 0;
    stations.push({
      left: [left.x[index], leftY[index], leftHeight[index]],
      right: [right.x[index], rightY[index], rightHeight[index]],
      shade: Math.max(0, Math.min(1, (gradientAt + GRADIENT_FULL_SCALE) / (2 * GRADIENT_FULL_SCALE))),
    });
    sumX += (left.x[index] + right.x[index]) / 2;
    sumY += (leftY[index] + rightY[index]) / 2;
  }
  if (stations.length < 8) return null;

  const centre = { x: sumX / stations.length, y: sumY / stations.length };
  let radius = 0;
  let lowest = Infinity;
  let highest = -Infinity;
  for (const station of stations) {
    const mx = (station.left[0] + station.right[0]) / 2 - centre.x;
    const my = (station.left[1] + station.right[1]) / 2 - centre.y;
    radius = Math.max(radius, Math.hypot(mx, my));
    lowest = Math.min(lowest, station.left[2], station.right[2]);
    highest = Math.max(highest, station.left[2], station.right[2]);
  }
  return { stations, centre, radius, heightSpan: Math.max(highest - lowest, 1) };
}

export function carPosition(car: any): { x: number; y: number } | null {
  const map = car?.mapPosition;
  const x = Number(map?.x ?? car?.x);
  const y = Number(map?.y ?? car?.y);
  return Number.isFinite(x) && Number.isFinite(y) ? { x, y } : null;
}

/** Nearest station to the car, so the marker sits on the ribbon itself. */
export function nearestStation(geometry: Geometry, position: { x: number; y: number } | null): number | null {
  if (!position) return null;
  let best = -1;
  let bestDistance = Infinity;
  geometry.stations.forEach((station, index) => {
    const mx = (station.left[0] + station.right[0]) / 2;
    const my = (station.left[1] + station.right[1]) / 2;
    const distance = (mx - position.x) ** 2 + (my - position.y) ** 2;
    if (distance < bestDistance) {
      bestDistance = distance;
      best = index;
    }
  });
  return best >= 0 ? best : null;
}

export const TrackElevationRibbon: React.FC<{ trackData: any; car?: any }> = ({ trackData, car }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const yawRef = useRef(0);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const geometry = useMemo(() => buildGeometry(trackData), [trackData]);
  const position = carPosition(car);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || typeof ResizeObserver === 'undefined') return undefined;
    const update = () => {
      const rect = container.getBoundingClientRect();
      setSize({ width: rect.width, height: rect.height });
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !geometry || size.width < 40 || size.height < 30) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Ease towards the car's bearing rather than snapping to it.
    if (position) {
      yawRef.current = advanceYaw(yawRef.current, yawTarget(position, geometry.centre));
    }
    const { project, depth } = makeProjector(yawRef.current, geometry.centre);

    const quads = geometry.stations.map((station, index) => {
      const next = geometry.stations[(index + 1) % geometry.stations.length];
      const corners: Array<[number, number]> = [
        project(station.left[0], station.left[1], station.left[2]),
        project(next.left[0], next.left[1], next.left[2]),
        project(next.right[0], next.right[1], next.right[2]),
        project(station.right[0], station.right[1], station.right[2]),
      ];
      const mx = (station.left[0] + station.right[0]) / 2;
      const my = (station.left[1] + station.right[1]) / 2;
      return { corners, depth: depth(mx, my), shade: station.shade, station: index };
    });
    // Painter's algorithm: what is further from the viewer goes down first, so a
    // rise in front of a dip covers it instead of bleeding through.
    quads.sort((a, b) => b.depth - a.depth);

    // The frame is sized from the circuit's own radius rather than the projected
    // extent, so the lap does not breathe in and out as it turns.
    const reach = geometry.radius;
    const vertical = geometry.radius * 2 * PITCH_SIN
      + geometry.heightSpan * HEIGHT_EXAGGERATION * PITCH_COS;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(size.width * dpr);
    canvas.height = Math.round(size.height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, size.width, size.height);

    const scale = Math.min(size.width / (reach * 2), size.height / vertical) * 0.92;
    ctx.save();
    ctx.translate(size.width / 2, size.height / 2);
    ctx.scale(scale, -scale);

    for (const quad of quads) {
      ctx.fillStyle = rampColour(quad.shade);
      ctx.beginPath();
      ctx.moveTo(quad.corners[0][0], quad.corners[0][1]);
      for (let corner = 1; corner < quad.corners.length; corner += 1) {
        ctx.lineTo(quad.corners[corner][0], quad.corners[corner][1]);
      }
      ctx.closePath();
      ctx.fill();
    }

    const station = nearestStation(geometry, position);
    if (station !== null) {
      const marker = quads.find((quad) => quad.station === station);
      if (marker) {
        const cx = marker.corners.reduce((sum, corner) => sum + corner[0], 0) / 4;
        const cy = marker.corners.reduce((sum, corner) => sum + corner[1], 0) / 4;
        ctx.fillStyle = 'rgba(250,204,21,0.28)';
        ctx.beginPath();
        ctx.arc(cx, cy, 22 / scale, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#facc15';
        ctx.beginPath();
        ctx.arc(cx, cy, 9 / scale, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    ctx.restore();
  }, [geometry, size, car, position?.x, position?.y]);

  if (!geometry) {
    return (
      <div ref={containerRef} className="num" style={{
        height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 9, color: 'var(--text-3)', textAlign: 'center', padding: 12,
      }}>
        Esta pista ainda nao tem altura extraida das duas bordas.
      </div>
    );
  }

  return (
    <div ref={containerRef} style={{ position: 'relative', height: '100%', width: '100%' }}>
      <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />
      <div className="num" style={{
        position: 'absolute', left: 10, top: 8, fontSize: 7, letterSpacing: '0.1em',
        textTransform: 'uppercase', color: 'var(--text-3)',
      }}>
        Relevo e inclinacao
      </div>
    </div>
  );
};

export default TrackElevationRibbon;
