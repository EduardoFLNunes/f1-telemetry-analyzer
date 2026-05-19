export function resolveMirrorX(value) {
  if (typeof value === 'boolean') return value;
  const raw = import.meta.env?.VITE_MIRROR_MAP_X ?? import.meta.env?.MIRROR_MAP_X ?? 'false';
  return ['1', 'true', 'yes', 'on'].includes(String(raw).trim().toLowerCase());
}

export function toRenderPoint(point, options = {}) {
  if (!point) return null;
  const x = Number(point.x);
  const y = Number(point.y);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return { x, y };
}

export function toRenderVector(vector, options = {}) {
  if (!vector) return null;
  const x = Number(vector.x);
  const y = Number(vector.y);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return { x, y };
}

export function toRenderHeading(heading = 0, options = {}) {
  return Number.isFinite(heading) ? heading : 0;
}

export function toRenderBounds(bounds, options = {}) {
  return bounds;
}

export function mirrorMode(options = {}) {
  return options.mirrorX ? 'screen-space' : 'off';
}

export function pointFromFrame(frame) {
  if (!frame) return null;
  return frame.mapPosition || { x: frame.x, y: frame.y ?? frame.z };
}
