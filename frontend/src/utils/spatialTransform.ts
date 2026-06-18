export type MapPosition = {
  x: number;
  y: number;
};

const finiteNumber = (value: unknown): number | null => {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};

const finitePoint = (x: unknown, y: unknown): MapPosition | null => {
  const mapX = finiteNumber(x);
  const mapY = finiteNumber(y);
  return mapX !== null && mapY !== null ? { x: mapX, y: mapY } : null;
};

const valueAt = (source: unknown, key: string): unknown => (
  source && typeof source === 'object' && !Array.isArray(source)
    ? (source as Record<string, unknown>)[key]
    : undefined
);

const firstFinite = (...values: unknown[]): number | null => {
  for (const value of values) {
    const number = finiteNumber(value);
    if (number !== null) return number;
  }
  return null;
};

export const transformWorldToMapPoint = (sample: unknown): MapPosition | null => {
  if (!sample || typeof sample !== 'object') return null;
  const raw = sample as Record<string, unknown>;
  const world = raw.worldPosition ?? raw.world_position;

  if (Array.isArray(world)) {
    const x = firstFinite(world[0]);
    const z = firstFinite(world[2]);
    return x !== null && z !== null ? { x, y: -z } : null;
  }

  const worldObject = world && typeof world === 'object'
    ? world as Record<string, unknown>
    : {};
  const x = firstFinite(
    worldObject.x,
    raw.worldPositionX,
    raw.world_x,
    raw.worldX,
  );
  const z = firstFinite(
    worldObject.z,
    raw.worldPositionZ,
    raw.world_z,
    raw.worldZ,
  );

  return x !== null && z !== null ? { x, y: -z } : null;
};

export const resolveSampleMapPosition = (sample: unknown): MapPosition | null => {
  if (!sample || typeof sample !== 'object') return null;
  const raw = sample as Record<string, unknown>;
  const fromWorld = transformWorldToMapPoint(raw);
  if (fromWorld) return fromWorld;

  const mapPosition = raw.mapPosition ?? raw.map_position;
  if (mapPosition && typeof mapPosition === 'object') {
    const point = finitePoint(valueAt(mapPosition, 'x'), valueAt(mapPosition, 'y'));
    if (point) return point;
  }

  const x = firstFinite(raw.x);
  const y = firstFinite(raw.y);
  if (x !== null && y !== null) return { x, y };

  const z = firstFinite(raw.z);
  return x !== null && z !== null ? { x, y: z } : null;
};
