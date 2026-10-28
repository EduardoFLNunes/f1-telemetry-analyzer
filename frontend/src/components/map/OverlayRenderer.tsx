/**
 * Back to screen space, without throwing away the device pixel ratio.
 *
 * The canvas is sized in device pixels and drawn through a `dpr` transform, so
 * everything below is authored in CSS pixels. `resetTransform` drops that
 * transform along with the camera, which puts every screen-space overlay --
 * readouts, insets, legends -- into the top left quadrant of a HiDPI display
 * while looking perfect at 1x. This restores the base transform instead.
 */
export function screenSpace(ctx: CanvasRenderingContext2D): void {
  const ratio = (typeof window !== 'undefined' && window.devicePixelRatio) || 1;
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
}

/**
 * The circuit as a broadcast graphic.
 *
 * Grey asphalt, a hard white line down each side and kerbs as white teeth
 * against the dark. It is the palette a lap looks like on television, and it
 * survives being small: three tones, maximum contrast between them, no hue to
 * confuse with the car or its trail.
 */
const ASPHALT_FILL = '#2c2c2c';
const KERB_STRIPE_METERS = 1.1;
const KERB_DARK = '#111111';
const KERB_LIGHT = '#f4f4f5';
const KERB_EDGE = 'rgba(228,228,231,0.85)';

function polygonPath(ctx: CanvasRenderingContext2D, points: number[][]) {
  ctx.beginPath();
  points.forEach((point, index) => {
    if (index === 0) ctx.moveTo(point[0], point[1]);
    else ctx.lineTo(point[0], point[1]);
  });
  ctx.closePath();
}

/** Dominant direction of a ring, so stripes run across the kerb rather than along it. */
function dominantAngle(points: number[][]): number {
  let sx = 0;
  let sy = 0;
  for (let i = 1; i < points.length; i += 1) {
    let dx = points[i][0] - points[i - 1][0];
    let dy = points[i][1] - points[i - 1][1];
    // Fold to a half-circle so opposite sides of the ring reinforce instead of cancel.
    if (dx < 0) { dx = -dx; dy = -dy; }
    sx += dx;
    sy += dy;
  }
  return Math.atan2(sy, sx);
}

/**
 * The road surface as the game models it.
 *
 * Outer boundaries and holes together in one path, filled even-odd: a line that
 * runs the whole lap encloses the infield, so filling an outer loop on its own
 * would flood the middle of the circuit. The loops arrive already free of the
 * paint and kerb strips -- `build_drawn_asphalt` takes those out before tracing
 * the boundary, because each thin strip contributed a pair of loops that flipped
 * the parity and stained the infield.
 */
export function drawAsphaltSurface(ctx: CanvasRenderingContext2D, trackData: any) {
  const loops = trackData?.asphaltSurface?.loops;
  if (!Array.isArray(loops) || !loops.length) return false;

  ctx.save();
  ctx.fillStyle = ASPHALT_FILL;
  ctx.beginPath();
  for (const loop of loops) {
    const points = loop?.points;
    if (!Array.isArray(points) || points.length < 3) continue;
    points.forEach((point: number[], index: number) => {
      if (index === 0) ctx.moveTo(point[0], point[1]);
      else ctx.lineTo(point[0], point[1]);
    });
    ctx.closePath();
  }
  ctx.fill('evenodd');
  ctx.restore();
  return true;
}

export function drawKerbs(ctx: CanvasRenderingContext2D, trackData: any, scale: number) {
  const polygons = trackData?.kerbGeometry?.polygons;
  if (!Array.isArray(polygons) || !polygons.length) return;

  const detail = mapDetail(scale);
  const widthFactor = lerp(DETAIL_MIN_WIDTH, 1, detail);
  const alphaFactor = lerp(DETAIL_MIN_ALPHA, 1, detail);

  ctx.save();
  ctx.globalAlpha = alphaFactor;
  for (const polygon of polygons) {
    const points = polygon?.points;
    if (!Array.isArray(points) || points.length < 4) continue;

    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const point of points) {
      if (point[0] < minX) minX = point[0];
      if (point[0] > maxX) maxX = point[0];
      if (point[1] < minY) minY = point[1];
      if (point[1] > maxY) maxY = point[1];
    }
    if (!Number.isFinite(minX) || !Number.isFinite(minY)) continue;

    ctx.save();
    polygonPath(ctx, points);
    ctx.clip();

    // Dark base, then white bars across it: the kerb reads as teeth, which is
    // what tells a corner apart from a straight at a glance.
    ctx.fillStyle = KERB_DARK;
    ctx.fillRect(minX, minY, maxX - minX, maxY - minY);

    const angle = dominantAngle(points);
    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;
    const span = Math.hypot(maxX - minX, maxY - minY);
    ctx.translate(cx, cy);
    ctx.rotate(angle);
    ctx.fillStyle = KERB_LIGHT;
    for (let offset = -span; offset <= span; offset += KERB_STRIPE_METERS * 2) {
      ctx.fillRect(offset, -span, KERB_STRIPE_METERS, span * 2);
    }
    ctx.restore();

    // The striped fill is clipped to the real kerb, about a metre and a half
    // across, which is under a pixel at map zoom and rasterises to nothing. So
    // the outline carries the kerb when zoomed out and thins to its real edge as
    // you close in, handing the job over to the stripes once there is room.
    ctx.lineWidth = Math.max(0.15, (1.2 * widthFactor) / Math.max(scale, 1e-6));
    ctx.strokeStyle = KERB_EDGE;
    polygonPath(ctx, points);
    ctx.stroke();
  }
  ctx.restore();
}

/**
 * How each class of paint is drawn.
 *
 * The colours are the circuit's, not a legend's: the paint that bounds the track
 * is white because that is what it is, the pit lane reads warm so it separates
 * from the track without competing with it, and access roads sit back in grey.
 * An earlier pass used a debug palette here -- green, pink, blue -- which made
 * every class shout equally and left the eye with no idea which line was the
 * track.
 *
 * `metres` is the paint's real width and `minPx` the floor in screen space. Zoom
 * in far enough and the line takes its true width; zoomed out, where a quarter
 * of a metre is a fraction of a pixel and would vanish, the floor keeps it
 * legible. `order` is the painting order, lowest first, so the track limit ends
 * up on top of everything else.
 */
const MARKING_STYLES: Record<string, { colour: [number, number, number]; alpha: number; metres: number; minPx: number; order: number }> = {
  servico: { colour: [148, 163, 184], alpha: 0.34, metres: 0.12, minPx: 0.9, order: 0 },
  boxes: { colour: [234, 179, 8], alpha: 0.62, metres: 0.15, minPx: 1.1, order: 1 },
  limite: { colour: [255, 255, 255], alpha: 1, metres: 0.22, minPx: 2.1, order: 2 },
};
const DEFAULT_MARKING_STYLE = MARKING_STYLES.limite;

// Pulling back, every line holds its screen width and the circuit closes into a
// solid mass with the car lost inside it. So past the point where the whole
// track fits, the paint thins and fades with the zoom: the shape stays readable
// and the car stays the brightest thing on the map.
const DETAIL_FULL_SCALE = 0.30;   // px per metre, roughly a whole lap on screen
const DETAIL_MIN_SCALE = 0.08;    // below this the map is a thumbnail
const DETAIL_MIN_WIDTH = 0.42;    // how thin the lines get down there
const DETAIL_MIN_ALPHA = 0.34;    // and how faint

export function mapDetail(scale: number): number {
  const span = DETAIL_FULL_SCALE - DETAIL_MIN_SCALE;
  return Math.max(0, Math.min(1, (scale - DETAIL_MIN_SCALE) / span));
}

function lerp(from: number, to: number, t: number): number {
  return from + (to - from) * t;
}

export function drawClassifiedMarkings(ctx: CanvasRenderingContext2D, trackData: any, scale: number) {
  const features = trackData?.markingGeometry?.features;
  if (!Array.isArray(features) || !features.length) return false;

  const ordered = [...features].sort(
    (a, b) => (MARKING_STYLES[a?.kind] || DEFAULT_MARKING_STYLE).order
      - (MARKING_STYLES[b?.kind] || DEFAULT_MARKING_STYLE).order,
  );

  const detail = mapDetail(scale);
  const widthFactor = lerp(DETAIL_MIN_WIDTH, 1, detail);
  const alphaFactor = lerp(DETAIL_MIN_ALPHA, 1, detail);

  ctx.save();
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  for (const feature of ordered) {
    const points = feature?.points;
    if (!Array.isArray(points) || points.length < 2) continue;
    const style = MARKING_STYLES[feature.kind] || DEFAULT_MARKING_STYLE;
    const [r, g, b] = style.colour;
    ctx.strokeStyle = `rgba(${r},${g},${b},${(style.alpha * alphaFactor).toFixed(3)})`;
    ctx.lineWidth = Math.max(style.metres, (style.minPx * widthFactor) / Math.max(scale, 1e-6));
    ctx.beginPath();
    points.forEach((point: number[], index: number) => {
      if (index === 0) ctx.moveTo(point[0], point[1]);
      else ctx.lineTo(point[0], point[1]);
    });
    if (feature.closed) ctx.closePath();
    ctx.stroke();
  }
  ctx.restore();
  return true;
}

export function drawMarkings(ctx: CanvasRenderingContext2D, trackData: any, scale: number) {
  const groups = trackData?.markingGeometry?.polygons;
  if (!Array.isArray(groups) || !groups.length) return;

  ctx.save();
  ctx.fillStyle = 'rgba(236,240,245,0.82)';
  for (const group of groups) {
    const rings = group?.rings;
    if (!Array.isArray(rings) || !rings.length) continue;

    // A line running the whole lap encloses the infield, and the paint is the
    // band between that ring and its holes -- so all rings go into one path and
    // are filled even-odd. Filling the outer ring alone would flood the middle
    // of the circuit.
    ctx.beginPath();
    for (const ring of rings) {
      if (!Array.isArray(ring) || ring.length < 4) continue;
      ring.forEach((point: number[], index: number) => {
        if (index === 0) ctx.moveTo(point[0], point[1]);
        else ctx.lineTo(point[0], point[1]);
      });
      ctx.closePath();
    }
    ctx.fill('evenodd');
  }
  ctx.restore();
}

/**
 * The map the user sees.
 *
 * Only what the game's own meshes carry: the painted markings, told apart by
 * what they mark, and the kerbs. The reconstructed corridor -- centreline, left
 * and right edge, width -- is deliberately not drawn. That geometry exists to
 * project telemetry onto the track, and it is good enough for that; asking it to
 * also *be* the picture is what produced a map that disagreed with the circuit.
 * The two live in the same world X/Z space, so the car placed by the projection
 * lands where the paint says it should.
 *
 * `reliefMode` is accepted and ignored: relief was shading painted across the
 * reconstructed asphalt band, and there is no band any more.
 */
type ReliefMode = 'NONE' | 'ELEVATION' | 'GRADIENT';

export function drawTrackSurface(
  ctx: CanvasRenderingContext2D,
  trackData: any,
  _bounds: any,
  scale: number,
  _reliefMode: ReliefMode = 'NONE',
) {
  ctx.save();
  drawAsphaltSurface(ctx, trackData);
  // Falls back to the unclassified fill when the paint has no verdicts yet --
  // an older cache, or a track whose AI lines the classifier could not read.
  if (!drawClassifiedMarkings(ctx, trackData, scale)) {
    drawMarkings(ctx, trackData, scale);
  }
  drawKerbs(ctx, trackData, scale);
  ctx.restore();
}

const MINI_MAP_CACHE = new WeakMap<object, { path: Path2D; bounds: any } | null>();

function miniMapPath(trackData: any): { path: Path2D; bounds: any } | null {
  if (!trackData || typeof Path2D === 'undefined') return null;
  const cached = MINI_MAP_CACHE.get(trackData);
  if (cached !== undefined) return cached;

  // The track limit paint already traces the circuit, so the inset is the same
  // shape the map draws rather than a second idea of where the track is.
  const features = (trackData?.markingGeometry?.features || [])
    .filter((feature: any) => feature?.kind === 'limite' && Array.isArray(feature.points) && feature.points.length > 8);
  const path = new Path2D();
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  let drawn = 0;

  for (const feature of features) {
    feature.points.forEach((point: number[], index: number) => {
      if (index === 0) path.moveTo(point[0], point[1]);
      else path.lineTo(point[0], point[1]);
      if (point[0] < minX) minX = point[0];
      if (point[0] > maxX) maxX = point[0];
      if (point[1] < minY) minY = point[1];
      if (point[1] > maxY) maxY = point[1];
    });
    if (feature.closed) path.closePath();
    drawn += 1;
  }

  const result = drawn ? { path, bounds: { minX, maxX, minY, maxY } } : null;
  MINI_MAP_CACHE.set(trackData, result);
  return result;
}

/**
 * The whole lap in a corner of the map, with the car on it.
 *
 * Following the car is the right way to read the road ahead and the wrong way to
 * know where in the lap you are -- at follow zoom every corner looks like any
 * other. This is the answer to that second question, and nothing more: no kerbs,
 * no paint classes, no scale bar.
 *
 * Drawn in screen space, after the camera transform has been restored, so it
 * stays pinned to the corner while the map pans and rotates underneath.
 */
export function drawMiniMap(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  trackData: any,
  carPosition: { x: number; y: number } | null,
  options: {
    size?: number;
    margin?: number;
    corner?: 'top-right' | 'top-left' | 'bottom-left' | 'bottom-right';
    bare?: boolean;
  } = {},
) {
  const outline = miniMapPath(trackData);
  if (!outline) return;

  const size = options.size ?? Math.max(84, Math.min(150, Math.round(Math.min(width, height) * 0.24)));
  const margin = options.margin ?? 14;
  const { minX, maxX, minY, maxY } = outline.bounds;
  const span = Math.max(maxX - minX, maxY - minY, 1);
  const scale = (size * 0.86) / span;

  // Top right by default. The follow view has three corners spoken for -- the
  // camera controls, the replay badge, the readout across the bottom middle --
  // so it puts the inset in the one that is left.
  const corner = options.corner || 'top-right';
  const left = corner.endsWith('left') ? margin : width - size - margin;
  const top = corner.startsWith('bottom') ? height - size - margin : margin;

  ctx.save();
  screenSpace(ctx);

  // A framed panel reads as a control. Bare, it reads as the lap -- but the
  // follow camera often has grey asphalt behind this corner, so it still needs
  // something to sit on: a scrim, with no border to call itself a widget.
  ctx.beginPath();
  ctx.rect(left, top, size, size);
  if (options.bare) {
    ctx.fillStyle = 'rgba(7,7,7,0.62)';
    ctx.fill();
  } else {
    ctx.fillStyle = 'rgba(6,8,16,0.72)';
    ctx.strokeStyle = 'rgba(148,163,184,0.18)';
    ctx.lineWidth = 1;
    ctx.fill();
    ctx.stroke();
  }

  ctx.save();
  ctx.beginPath();
  ctx.rect(left, top, size, size);
  ctx.clip();
  ctx.translate(left + size / 2, top + size / 2);
  ctx.scale(scale, -scale);
  ctx.translate(-(minX + maxX) / 2, -(minY + maxY) / 2);

  ctx.strokeStyle = 'rgba(226,232,240,0.55)';
  ctx.lineWidth = 1.6 / scale;
  ctx.stroke(outline.path);

  if (carPosition && Number.isFinite(carPosition.x) && Number.isFinite(carPosition.y)) {
    ctx.fillStyle = '#facc15';
    ctx.beginPath();
    ctx.arc(carPosition.x, carPosition.y, 4.5 / scale, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
  ctx.restore();
}

export function drawHud(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  trackData: any,
  frame: any,
  camera: { mode: string; zoom: number },
  options: { performanceMode?: string } = {},
) {
  const performanceMode = options.performanceMode || 'BALANCED';
  const compact = performanceMode === 'PERFORMANCE';
  ctx.save();
  screenSpace(ctx);
  ctx.fillStyle = 'rgba(6,8,16,0.78)';
  ctx.strokeStyle = 'rgba(148,163,184,0.16)';
  ctx.lineWidth = 1;
  ctx.fillRect(12, 12, compact ? 170 : 260, compact ? 42 : 62);
  ctx.strokeRect(12, 12, compact ? 170 : 260, compact ? 42 : 62);

  ctx.fillStyle = '#22d3ee';
  ctx.font = 'bold 9px "IBM Plex Mono", monospace';
  ctx.fillText(trackData?.trackName || trackData?.name || 'COLLECTING LAP', 24, 32);

  ctx.fillStyle = '#94a3b8';
  ctx.font = '8px "IBM Plex Mono", monospace';
  if (compact) {
    ctx.fillText(`${camera.mode} x${camera.zoom.toFixed(1)}`, 24, 50);
  } else {
    ctx.fillText(`${Math.round(trackData?.trackLength || trackData?.length_meters || 0)} m | ${trackData?.total_points || 0} pts | ${trackData?.source || 'track geometry'}`, 24, 48);
    ctx.fillText(`Camera ${camera.mode}  Zoom x${camera.zoom.toFixed(1)}`, 24, 64);
  }

  ctx.restore();
}
