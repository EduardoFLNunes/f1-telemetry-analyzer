import { resolveSampleMapPosition, MapPosition } from '../../utils/spatialTransform';

export type TrackBounds = {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
  cx: number;
  cy: number;
  w: number;
  h: number;
};

export type CameraState = {
  mode: 'FOLLOW' | 'OVERVIEW' | string;
  zoom: number;
  offset: { x: number; y: number };
};

export function computeTrackBounds(
  trackData: any,
  history: unknown[] = [],
  carFrame: unknown = null,
  extraPositions: MapPosition[] = [],
): TrackBounds {
  const left = trackData?.left_edge || {};
  const right = trackData?.right_edge || {};
  const pitGeometries = Object.values(trackData?.pitVisualGeometry?.geometries || {}) as any[];
  const pitPoints = pitGeometries.flatMap((geometry) => [
    ...(geometry.leftEdge?.points || []),
    ...(geometry.rightEdge?.points || []),
  ]);
  const livePositions: MapPosition[] = history
    .map((frame) => resolveSampleMapPosition(frame))
    .filter((point): point is MapPosition => Boolean(point) && Number.isFinite(point?.x) && Number.isFinite(point?.y));
  const carPosition = resolveSampleMapPosition(carFrame);
  if (carPosition && Number.isFinite(carPosition.x) && Number.isFinite(carPosition.y)) {
    livePositions.push(carPosition);
  }
  extraPositions.forEach((point) => {
    if (Number.isFinite(point?.x) && Number.isFinite(point?.y)) {
      livePositions.push(point);
    }
  });

  const xs = [
    ...(left.x || []),
    ...(right.x || []),
    ...pitPoints.map((point: any) => point?.[0]),
    ...livePositions.map((point) => point.x),
  ].filter(Number.isFinite);
  const ys = [
    ...(left.y || left.z || []),
    ...(right.y || right.z || []),
    ...pitPoints.map((point: any) => point?.[1]),
    ...livePositions.map((point) => point.y),
  ].filter(Number.isFinite);

  if (!xs.length || !ys.length) {
    return { minX: -100, maxX: 100, minY: -100, maxY: 100, cx: 0, cy: 0, w: 200, h: 200 };
  }

  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);

  return {
    minX,
    maxX,
    minY,
    maxY,
    cx: (minX + maxX) / 2,
    cy: (minY + maxY) / 2,
    w: Math.max(maxX - minX, 1),
    h: Math.max(maxY - minY, 1),
  };
}

export function applyCameraTransform(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  bounds: TrackBounds,
  camera: CameraState,
  carFrame: unknown,
): number {
  const mode = camera.mode;
  const zoom = camera.zoom;

  if (mode === 'FOLLOW' && carFrame) {
    const carPosition = resolveSampleMapPosition(carFrame);
    if (!carPosition) {
      return applyCameraTransform(ctx, width, height, bounds, { ...camera, mode: 'OVERVIEW' }, null);
    }
    const scale = (height / 90) * zoom;
    ctx.translate(width / 2, height * 0.68);
    ctx.scale(scale, scale);
    ctx.rotate(-((carFrame as any).heading || 0) + Math.PI / 2);
    ctx.translate(-carPosition.x, -carPosition.y);
    return scale;
  }

  const scale = Math.min(width / bounds.w, height / bounds.h) * 0.84 * zoom;
  ctx.translate(width / 2 + camera.offset.x, height / 2 + camera.offset.y);
  ctx.scale(scale, scale);
  ctx.translate(-bounds.cx, -bounds.cy);
  return scale;
}
