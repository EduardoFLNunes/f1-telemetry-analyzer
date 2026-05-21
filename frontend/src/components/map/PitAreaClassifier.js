function toPoint(point) {
  if (!point) return null;
  const x = Number(point.x);
  const y = Number(point.y ?? point.z);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return { x, y };
}

function distance(a, b) {
  return Math.hypot(b.x - a.x, b.y - a.y);
}

function distancePointToSegment(point, a, b) {
  const abx = b.x - a.x;
  const aby = b.y - a.y;
  const denom = abx * abx + aby * aby;
  if (denom <= 1e-12) return distance(point, a);
  const apx = point.x - a.x;
  const apy = point.y - a.y;
  const t = Math.max(0, Math.min(1, (apx * abx + apy * aby) / denom));
  return distance(point, { x: a.x + abx * t, y: a.y + aby * t });
}

function distanceToPolyline(point, line = []) {
  if (!point || line.length < 2) return Number.POSITIVE_INFINITY;
  let best = Number.POSITIVE_INFINITY;
  for (let index = 1; index < line.length; index += 1) {
    const a = toPoint(line[index - 1]);
    const b = toPoint(line[index]);
    if (!a || !b) continue;
    best = Math.min(best, distancePointToSegment(point, a, b));
  }
  return best;
}

function pointInTriangle(point, vertices = []) {
  if (!point || vertices.length < 3) return false;
  const a = toPoint(vertices[0]);
  const b = toPoint(vertices[1]);
  const c = toPoint(vertices[2]);
  if (!a || !b || !c) return false;
  const denom = (b.y - c.y) * (a.x - c.x) + (c.x - b.x) * (a.y - c.y);
  if (Math.abs(denom) <= 1e-12) return false;
  const u = ((b.y - c.y) * (point.x - c.x) + (c.x - b.x) * (point.y - c.y)) / denom;
  const v = ((c.y - a.y) * (point.x - c.x) + (a.x - c.x) * (point.y - c.y)) / denom;
  const w = 1 - u - v;
  return u >= -1e-6 && v >= -1e-6 && w >= -1e-6;
}

function sampleItems(items = [], maxCount) {
  if (items.length <= maxCount) return items;
  const step = Math.max(1, Math.ceil(items.length / maxCount));
  return items.filter((_, index) => index % step === 0).slice(0, maxCount);
}

function componentTriangles(pitlaneData, componentName, maxCount = 380) {
  const components = pitlaneData?.pitAreaGeometry?.components?.components || [];
  const component = components.find((item) => item.name === componentName);
  return sampleItems(component?.sampleTriangles || [], maxCount);
}

function centerline(pitlaneData, name) {
  return pitlaneData?.pitAreaGeometry?.centerlines?.centerlines?.[name]?.centerline || [];
}

function insideAnyTriangle(point, triangles = []) {
  return triangles.some((triangle) => pointInTriangle(point, triangle.vertices || []));
}

export function labelForTrackArea(area) {
  switch (area) {
    case 'main_track':
      return 'MAIN';
    case 'pit_entry_access':
      return 'PIT ENTRY';
    case 'pit_corridor':
      return 'PIT LANE';
    case 'pit_exit_access':
      return 'PIT EXIT';
    case 'pit_area_other':
      return 'PIT AREA';
    default:
      return 'UNKNOWN';
  }
}

export function colorForTrackArea(area) {
  switch (area) {
    case 'main_track':
      return '#cbd5e1';
    case 'pit_entry_access':
      return '#22c55e';
    case 'pit_corridor':
      return '#facc15';
    case 'pit_exit_access':
      return '#fb923c';
    case 'pit_area_other':
      return '#eab308';
    default:
      return '#94a3b8';
  }
}

export function classifyPointInTrackArea(mapPosition, pitlaneData) {
  const point = toPoint(mapPosition);
  if (!point || !pitlaneData) {
    return {
      area: 'unknown',
      label: 'UNKNOWN',
      distanceToPitArea: null,
      distanceToMainTrack: null,
      confidence: 'low',
    };
  }

  const entryLine = centerline(pitlaneData, 'PitEntryAccessCenterline');
  const corridorLine = centerline(pitlaneData, 'PitLaneCorridorCenterline');
  const exitLine = centerline(pitlaneData, 'PitExitAccessCenterline');
  const mainLine = sampleItems(pitlaneData.mainTrack?.centerline || [], 650);

  const distanceToEntry = distanceToPolyline(point, entryLine);
  const distanceToCorridor = distanceToPolyline(point, corridorLine);
  const distanceToExit = distanceToPolyline(point, exitLine);
  const distanceToPitArea = Math.min(distanceToEntry, distanceToCorridor, distanceToExit);
  const distanceToMainTrack = distanceToPolyline(point, mainLine);

  let area = 'unknown';
  let confidence = 'low';

  if (distanceToEntry <= 7) {
    area = 'pit_entry_access';
    confidence = 'high';
  } else if (distanceToExit <= 7) {
    area = 'pit_exit_access';
    confidence = 'high';
  } else if (distanceToCorridor <= 7.5) {
    area = 'pit_corridor';
    confidence = 'high';
  } else if (insideAnyTriangle(point, componentTriangles(pitlaneData, 'PitEntryAccessArea', 260))) {
    area = 'pit_entry_access';
    confidence = 'medium';
  } else if (insideAnyTriangle(point, componentTriangles(pitlaneData, 'PitExitAccessArea', 260))) {
    area = 'pit_exit_access';
    confidence = 'medium';
  } else if (insideAnyTriangle(point, componentTriangles(pitlaneData, 'PitLaneCorridor', 320))) {
    area = 'pit_corridor';
    confidence = 'medium';
  } else if (insideAnyTriangle(point, componentTriangles(pitlaneData, 'OtherPitArea', 260))) {
    area = 'pit_area_other';
    confidence = 'medium';
  } else if (distanceToEntry <= 11) {
    area = 'pit_entry_access';
    confidence = 'medium';
  } else if (distanceToExit <= 11) {
    area = 'pit_exit_access';
    confidence = 'medium';
  } else if (distanceToCorridor <= 12) {
    area = 'pit_corridor';
    confidence = 'medium';
  } else if (distanceToMainTrack <= 12) {
    area = 'main_track';
    confidence = 'medium';
  }

  return {
    area,
    label: labelForTrackArea(area),
    distanceToPitArea: Number.isFinite(distanceToPitArea) ? distanceToPitArea : null,
    distanceToEntryAccess: Number.isFinite(distanceToEntry) ? distanceToEntry : null,
    distanceToPitCorridor: Number.isFinite(distanceToCorridor) ? distanceToCorridor : null,
    distanceToExitAccess: Number.isFinite(distanceToExit) ? distanceToExit : null,
    distanceToMainTrack: Number.isFinite(distanceToMainTrack) ? distanceToMainTrack : null,
    confidence,
  };
}
