import { classifyPointInTrackArea, colorForTrackArea } from './PitAreaClassifier.js';

export function mapToCanvasPoint(point) {
  if (!point) return null;
  const x = Number(point.x);
  const y = Number(point.y);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return { x, y };
}

function pointIsFinite(point) {
  return Boolean(mapToCanvasPoint(point));
}

function buildPolyline(points = [], close = false) {
  if (typeof Path2D === 'undefined' || !points.length) return null;
  const first = mapToCanvasPoint(points.find(pointIsFinite));
  if (!first) return null;
  const path = new Path2D();
  path.moveTo(first.x, first.y);
  for (let index = 1; index < points.length; index += 1) {
    const point = mapToCanvasPoint(points[index]);
    if (pointIsFinite(point)) path.lineTo(point.x, point.y);
  }
  if (close) path.closePath();
  return path;
}

function buildCorridor(leftEdge = [], rightEdge = []) {
  if (typeof Path2D === 'undefined' || !leftEdge.length || !rightEdge.length) return null;
  const first = mapToCanvasPoint(leftEdge.find(pointIsFinite));
  if (!first) return null;
  const path = new Path2D();
  path.moveTo(first.x, first.y);
  for (let index = 1; index < leftEdge.length; index += 1) {
    const point = mapToCanvasPoint(leftEdge[index]);
    if (pointIsFinite(point)) path.lineTo(point.x, point.y);
  }
  for (let index = rightEdge.length - 1; index >= 0; index -= 1) {
    const point = mapToCanvasPoint(rightEdge[index]);
    if (pointIsFinite(point)) path.lineTo(point.x, point.y);
  }
  path.closePath();
  return path;
}

function buildTrianglePaths(triangles = []) {
  if (typeof Path2D === 'undefined') return [];
  return triangles
    .map((triangle) => {
      const vertices = triangle.vertices || [];
      if (vertices.length < 3) return null;
      const points = vertices.map(mapToCanvasPoint).filter(Boolean);
      if (points.length < 3) return null;
      const path = new Path2D();
      path.moveTo(points[0].x, points[0].y);
      path.lineTo(points[1].x, points[1].y);
      path.lineTo(points[2].x, points[2].y);
      path.closePath();
      return path;
    })
    .filter(Boolean);
}

function buildBoundaryLoopPaths(loops = []) {
  if (typeof Path2D === 'undefined') return [];
  return loops
    .map((loop) => {
      const points = loop.points || [];
      if (points.length < 3) return null;
      const path = buildPolyline(points, true);
      return path ? { loopId: loop.loopId, path } : null;
    })
    .filter(Boolean);
}

function accessGeometryV2(pitlaneData, pitArea, kind) {
  if (kind === 'entry') {
    return pitlaneData.pitEntryAccessGeometryV2 || pitArea.entryAccessGeometryV2 || pitlaneData.pitEntryAccess || {};
  }
  return pitlaneData.pitExitAccessGeometryV2 || pitArea.exitAccessGeometryV2 || pitlaneData.pitExitAccess || {};
}

export function createPitLanePathCache(pitlaneData) {
  if (!pitlaneData || typeof Path2D === 'undefined') {
    return {
      pathCacheEnabled: false,
      cacheKey: 'pitlane-none',
      mainTrackCenterline: null,
      pitAreaTriangles: [],
      pitAreaComponents: {},
      fastLaneReference: null,
      pitLaneAiReference: null,
      v2Centerline: null,
      v2Corridor: null,
      v2SurfaceLoops: [],
      legacyCenterline: null,
      legacyCorridor: null,
    };
  }

  const pitlaneV2 = pitlaneData.pitLaneCorridorV2 || pitlaneData.pitlaneV2 || {};
  const v2 = pitlaneV2.geometry || {};
  const pitArea = pitlaneData.pitAreaGeometry || {};
  const pitAreaSurface = pitArea.surface || {};
  const pitAreaComponents = pitArea.components?.components || [];
  const aiReferences = pitArea.centerlines?.aiReferences || {};
  const entryAccess = pitlaneData.pitEntryAccess || {};
  const exitAccess = pitlaneData.pitExitAccess || {};
  const entryAccessV2 = accessGeometryV2(pitlaneData, pitArea, 'entry');
  const exitAccessV2 = accessGeometryV2(pitlaneData, pitArea, 'exit');
  const legacy = pitlaneData.pitlaneLegacy?.geometry || pitlaneData.pitlaneTrimmedManual || {};
  const surfaceLoops = pitlaneV2.surface?.boundaryLoops || [];
  const cacheKey = [
    pitlaneData.activePitlaneDebugVersion || 'pitlaneV2',
    v2.pointCount || 0,
    v2.lengthMeters || 0,
    entryAccess.pointCount || 0,
    exitAccess.pointCount || 0,
    entryAccessV2.triangleCount || entryAccessV2.surfaceFootprint?.triangleCount || 0,
    exitAccessV2.triangleCount || exitAccessV2.surfaceFootprint?.triangleCount || 0,
    entryAccessV2.boundaryLoopCount || entryAccessV2.boundaryLoops?.length || 0,
    exitAccessV2.boundaryLoopCount || exitAccessV2.boundaryLoops?.length || 0,
    legacy.pointCount || 0,
    surfaceLoops.length,
    pitAreaSurface.triangleCount || 0,
    pitAreaSurface.sampleTriangleCount || pitAreaSurface.sampleTriangles?.length || 0,
  ].join('|');

  const componentTrianglePaths = pitAreaComponents.reduce((acc, component) => {
    acc[component.name] = buildTrianglePaths(component.sampleTriangles || []);
    return acc;
  }, {});

  return {
    pathCacheEnabled: true,
    cacheKey,
    mainTrackCenterline: buildPolyline(pitlaneData.mainTrack?.centerline || [], true),
    pitAreaTriangles: buildTrianglePaths(pitAreaSurface.sampleTriangles || []),
    pitAreaComponents: componentTrianglePaths,
    fastLaneReference: buildPolyline(aiReferences.fastLane?.centerline || [], true),
    pitLaneAiReference: buildPolyline(aiReferences.pitLane?.centerline || [], false),
    v2Centerline: buildPolyline(v2.centerline, false),
    v2Corridor: buildCorridor(v2.leftEdge, v2.rightEdge),
    entryAccessCenterline: buildPolyline(entryAccess.centerline, false),
    exitAccessCenterline: buildPolyline(exitAccess.centerline, false),
    entryAccessFootprint: buildTrianglePaths(entryAccess.surfaceFootprint?.sampleTriangles || []),
    exitAccessFootprint: buildTrianglePaths(exitAccess.surfaceFootprint?.sampleTriangles || []),
    entryAccessV2Centerline: buildPolyline(entryAccessV2.centerline, false),
    exitAccessV2Centerline: buildPolyline(exitAccessV2.centerline, false),
    entryAccessV2Footprint: buildTrianglePaths(entryAccessV2.surfaceFootprint?.sampleTriangles || []),
    exitAccessV2Footprint: buildTrianglePaths(exitAccessV2.surfaceFootprint?.sampleTriangles || []),
    entryAccessV2BoundaryLoops: buildBoundaryLoopPaths(entryAccessV2.boundaryLoops || []),
    exitAccessV2BoundaryLoops: buildBoundaryLoopPaths(exitAccessV2.boundaryLoops || []),
    v2SurfaceLoops: surfaceLoops.map((loop) => ({
      loopId: loop.loopId,
      path: buildPolyline(loop.points, true),
    })),
    legacyCenterline: buildPolyline(legacy.centerline, false),
    legacyCorridor: buildCorridor(legacy.leftEdge, legacy.rightEdge),
  };
}

function drawPathOrPolyline(ctx, path, points = [], close = false) {
  if (path) {
    ctx.stroke(path);
    return;
  }
  if (!points.length) return;
  const first = mapToCanvasPoint(points.find(pointIsFinite));
  if (!first) return;
  ctx.beginPath();
  ctx.moveTo(first.x, first.y);
  for (let index = 1; index < points.length; index += 1) {
    const point = mapToCanvasPoint(points[index]);
    if (pointIsFinite(point)) ctx.lineTo(point.x, point.y);
  }
  if (close) ctx.closePath();
  ctx.stroke();
}

function fillPathOrCorridor(ctx, path, leftEdge = [], rightEdge = []) {
  if (path) {
    ctx.fill(path);
    ctx.stroke(path);
    return;
  }
  if (!leftEdge.length || !rightEdge.length) return;
  const first = mapToCanvasPoint(leftEdge.find(pointIsFinite));
  if (!first) return;
  ctx.beginPath();
  ctx.moveTo(first.x, first.y);
  for (let index = 1; index < leftEdge.length; index += 1) {
    const point = mapToCanvasPoint(leftEdge[index]);
    if (pointIsFinite(point)) ctx.lineTo(point.x, point.y);
  }
  for (let index = rightEdge.length - 1; index >= 0; index -= 1) {
    const point = mapToCanvasPoint(rightEdge[index]);
    if (pointIsFinite(point)) ctx.lineTo(point.x, point.y);
  }
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
}

function fillTrianglePaths(ctx, paths = []) {
  paths.forEach((path) => {
    ctx.fill(path);
    ctx.stroke(path);
  });
}

function strokeBoundaryLoops(ctx, loops = []) {
  loops.forEach((loop) => {
    if (loop.path) ctx.stroke(loop.path);
  });
}

function accessLabelPoint(geometry, fallback = []) {
  const centerline = geometry?.centerline || fallback || [];
  if (centerline.length) return centerline[Math.floor(centerline.length / 2)];
  const loop = geometry?.boundaryLoops?.find((item) => item.points?.length);
  if (loop?.points?.length) return loop.points[Math.floor(loop.points.length / 2)];
  const triangle = geometry?.surfaceFootprint?.sampleTriangles?.find((item) => item.vertices?.length >= 3);
  if (triangle) {
    const points = triangle.vertices.map(mapToCanvasPoint).filter(Boolean);
    if (points.length >= 3) {
      return {
        x: (points[0].x + points[1].x + points[2].x) / 3,
        y: (points[0].y + points[1].y + points[2].y) / 3,
      };
    }
  }
  return null;
}

function drawMarker(ctx, point, scale, color, radius = 5.5) {
  const canvasPoint = mapToCanvasPoint(point);
  if (!canvasPoint) return;
  ctx.save();
  ctx.beginPath();
  ctx.arc(canvasPoint.x, canvasPoint.y, radius / scale, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.strokeStyle = 'rgba(2,6,23,0.92)';
  ctx.lineWidth = 2 / scale;
  ctx.fill();
  ctx.stroke();
  ctx.restore();
}

function drawLabel(ctx, point, scale, text, color = '#e2e8f0', options = {}) {
  const canvasPoint = mapToCanvasPoint(point);
  if (!canvasPoint || !text) return;
  ctx.save();
  ctx.translate(canvasPoint.x, canvasPoint.y);
  if (options.screenMirrorX) ctx.scale(-1, 1);
  const fontSize = 9 / scale;
  ctx.font = `${fontSize}px Consolas, monospace`;
  ctx.textBaseline = 'middle';
  const x = 7 / scale;
  const y = -7 / scale;
  const metrics = ctx.measureText(text);
  ctx.fillStyle = 'rgba(2,6,23,0.74)';
  ctx.fillRect(x - 3 / scale, y - 6 / scale, metrics.width + 6 / scale, 12 / scale);
  ctx.fillStyle = color;
  ctx.fillText(text, x, y);
  ctx.restore();
}

function drawDirectionTicks(ctx, points = [], scale, color) {
  if (points.length < 4) return;
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.35 / scale;
  const step = Math.max(12, Math.floor(points.length / 9));
  for (let index = step; index < points.length - 2; index += step) {
    const a = points[index];
    const b = points[index + 2];
    const canvasA = mapToCanvasPoint(a);
    const canvasB = mapToCanvasPoint(b);
    if (!canvasA || !canvasB) continue;
    const dx = canvasB.x - canvasA.x;
    const dy = canvasB.y - canvasA.y;
    const length = Math.hypot(dx, dy) || 1;
    const ux = dx / length;
    const uy = dy / length;
    const px = -uy;
    const py = ux;
    const size = 4.5 / scale;
    ctx.beginPath();
    ctx.moveTo(canvasA.x - ux * size - px * size * 0.55, canvasA.y - uy * size - py * size * 0.55);
    ctx.lineTo(canvasA.x + ux * size, canvasA.y + uy * size);
    ctx.lineTo(canvasA.x - ux * size + px * size * 0.55, canvasA.y - uy * size + py * size * 0.55);
    ctx.stroke();
  }
  ctx.restore();
}

export function drawPitLaneOverlay(ctx, pitlaneData, scale, pathCache, options = {}) {
  if (!pitlaneData) return;
  const pitlaneV2 = pitlaneData.pitLaneCorridorV2 || pitlaneData.pitlaneV2 || {};
  const v2 = pitlaneV2.geometry || {};
  const pitArea = pitlaneData.pitAreaGeometry || {};
  const pitAreaSurface = pitArea.surface || {};
  const pitAreaComponents = pitArea.components?.components || [];
  const aiReferences = pitArea.centerlines?.aiReferences || {};
  const entryAccess = pitlaneData.pitEntryAccess || {};
  const exitAccess = pitlaneData.pitExitAccess || {};
  const entryAccessV2 = accessGeometryV2(pitlaneData, pitArea, 'entry');
  const exitAccessV2 = accessGeometryV2(pitlaneData, pitArea, 'exit');
  const legacy = pitlaneData.pitlaneLegacy?.geometry || pitlaneData.pitlaneTrimmedManual || {};
  const cache = pathCache?.pathCacheEnabled ? pathCache : null;
  const {
    showMainTrack = true,
    showPitArea = true,
    showPitCorridorV2,
    showPitV2,
    showEntryAccess = true,
    showExitAccess = true,
    showEntryExit = true,
    showAiReferences = true,
    showSurface = false,
    showLabels = true,
    showAdvancedLegacy,
    showLegacy,
  } = options;
  const pitCorridorVisible = showPitCorridorV2 ?? showPitV2 ?? true;
  const legacyVisible = showAdvancedLegacy ?? showLegacy ?? false;
  const labelOptions = { screenMirrorX: Boolean(options.screenMirrorX) };

  ctx.save();
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  if (showMainTrack && pitlaneData.mainTrack?.centerline?.length) {
    ctx.setLineDash([8 / scale, 12 / scale]);
    ctx.strokeStyle = 'rgba(148,163,184,0.42)';
    ctx.lineWidth = 1.1 / scale;
    drawPathOrPolyline(ctx, cache?.mainTrackCenterline, pitlaneData.mainTrack.centerline, true);
    ctx.setLineDash([]);
  }

  if (showAiReferences) {
    const fastLane = aiReferences.fastLane?.centerline || [];
    const pitLaneAi = aiReferences.pitLane?.centerline || [];
    if (fastLane.length) {
      ctx.setLineDash([8 / scale, 7 / scale]);
      ctx.strokeStyle = 'rgba(168,85,247,0.56)';
      ctx.lineWidth = 1.1 / scale;
      drawPathOrPolyline(ctx, cache?.fastLaneReference, fastLane, true);
    }
    if (pitLaneAi.length) {
      ctx.setLineDash([7 / scale, 7 / scale]);
      ctx.strokeStyle = 'rgba(56,189,248,0.50)';
      ctx.lineWidth = 1.1 / scale;
      drawPathOrPolyline(ctx, cache?.pitLaneAiReference, pitLaneAi, false);
    }
    ctx.setLineDash([]);
  }

  if (showPitArea && pitAreaSurface.sampleTriangles?.length) {
    ctx.fillStyle = 'rgba(250,204,21,0.075)';
    ctx.strokeStyle = 'rgba(250,204,21,0.16)';
    ctx.lineWidth = 0.28 / scale;
    fillTrianglePaths(ctx, cache?.pitAreaTriangles || buildTrianglePaths(pitAreaSurface.sampleTriangles));

    if (pitAreaComponents.length) {
      const componentPaths = cache?.pitAreaComponents || {};
      if (pitCorridorVisible) {
        ctx.fillStyle = 'rgba(250,204,21,0.13)';
        ctx.strokeStyle = 'rgba(250,204,21,0.20)';
        fillTrianglePaths(ctx, componentPaths.PitLaneCorridor || []);
      }
      if (showEntryAccess) {
        ctx.fillStyle = 'rgba(34,197,94,0.07)';
        ctx.strokeStyle = 'rgba(34,197,94,0.12)';
        fillTrianglePaths(ctx, componentPaths.PitEntryAccessArea || []);
      }
      if (showExitAccess) {
        ctx.fillStyle = 'rgba(251,146,60,0.07)';
        ctx.strokeStyle = 'rgba(251,146,60,0.12)';
        fillTrianglePaths(ctx, componentPaths.PitExitAccessArea || []);
      }
    }
  }

  if (showEntryAccess && entryAccessV2.surfaceFootprint?.sampleTriangles?.length) {
    ctx.fillStyle = 'rgba(34,197,94,0.24)';
    ctx.strokeStyle = 'rgba(34,197,94,0.36)';
    ctx.lineWidth = 0.32 / scale;
    fillTrianglePaths(ctx, cache?.entryAccessV2Footprint || buildTrianglePaths(entryAccessV2.surfaceFootprint.sampleTriangles));

    ctx.strokeStyle = 'rgba(134,239,172,0.92)';
    ctx.lineWidth = 2.2 / scale;
    strokeBoundaryLoops(ctx, cache?.entryAccessV2BoundaryLoops || buildBoundaryLoopPaths(entryAccessV2.boundaryLoops || []));
  }

  if (showExitAccess && exitAccessV2.surfaceFootprint?.sampleTriangles?.length) {
    ctx.fillStyle = 'rgba(251,146,60,0.25)';
    ctx.strokeStyle = 'rgba(251,146,60,0.38)';
    ctx.lineWidth = 0.32 / scale;
    fillTrianglePaths(ctx, cache?.exitAccessV2Footprint || buildTrianglePaths(exitAccessV2.surfaceFootprint.sampleTriangles));

    ctx.strokeStyle = 'rgba(253,186,116,0.94)';
    ctx.lineWidth = 2.2 / scale;
    strokeBoundaryLoops(ctx, cache?.exitAccessV2BoundaryLoops || buildBoundaryLoopPaths(exitAccessV2.boundaryLoops || []));
  }

  if (showSurface) {
    ctx.fillStyle = 'rgba(250,204,21,0.08)';
    ctx.strokeStyle = 'rgba(250,204,21,0.25)';
    ctx.lineWidth = 0.8 / scale;
    (cache?.v2SurfaceLoops || []).forEach((loop) => {
      if (loop.path) {
        ctx.fill(loop.path);
        ctx.stroke(loop.path);
      }
    });

    ctx.fillStyle = 'rgba(34,197,94,0.10)';
    ctx.strokeStyle = 'rgba(34,197,94,0.24)';
    ctx.lineWidth = 0.35 / scale;
    (cache?.entryAccessFootprint || []).forEach((path) => {
      ctx.fill(path);
      ctx.stroke(path);
    });

    ctx.fillStyle = 'rgba(251,146,60,0.10)';
    ctx.strokeStyle = 'rgba(251,146,60,0.24)';
    (cache?.exitAccessFootprint || []).forEach((path) => {
      ctx.fill(path);
      ctx.stroke(path);
    });
  }

  if (legacyVisible && legacy.centerline?.length) {
    ctx.fillStyle = 'rgba(239,68,68,0.06)';
    ctx.strokeStyle = 'rgba(239,68,68,0.22)';
    ctx.lineWidth = 0.9 / scale;
    fillPathOrCorridor(ctx, cache?.legacyCorridor, legacy.leftEdge, legacy.rightEdge);

    ctx.setLineDash([10 / scale, 8 / scale]);
    ctx.strokeStyle = 'rgba(248,113,113,0.46)';
    ctx.lineWidth = 2.0 / scale;
    drawPathOrPolyline(ctx, cache?.legacyCenterline, legacy.centerline, false);
    ctx.setLineDash([]);
    if (showLabels) {
      drawLabel(ctx, legacy.centerline[Math.floor(legacy.centerline.length / 2)], scale, 'Legacy', '#fecaca', labelOptions);
    }
  }

  if (pitCorridorVisible && v2.centerline?.length) {
    ctx.fillStyle = 'rgba(250,204,21,0.16)';
    ctx.strokeStyle = 'rgba(250,204,21,0.62)';
    ctx.lineWidth = 1.0 / scale;
    fillPathOrCorridor(ctx, cache?.v2Corridor, v2.leftEdge, v2.rightEdge);

    ctx.shadowBlur = 7 / scale;
    ctx.shadowColor = 'rgba(253,224,71,0.30)';
    ctx.strokeStyle = '#fde047';
    ctx.lineWidth = 3.0 / scale;
    drawPathOrPolyline(ctx, cache?.v2Centerline, v2.centerline, false);
    ctx.shadowBlur = 0;
    drawDirectionTicks(ctx, v2.centerline, scale, '#fde047');
  }

  if (showEntryAccess && (entryAccessV2.centerline?.length || entryAccess.centerline?.length)) {
    const centerline = entryAccessV2.centerline?.length ? entryAccessV2.centerline : entryAccess.centerline;
    ctx.strokeStyle = 'rgba(187,247,208,0.74)';
    ctx.lineWidth = 1.55 / scale;
    ctx.setLineDash([]);
    drawPathOrPolyline(ctx, cache?.entryAccessV2Centerline || cache?.entryAccessCenterline, centerline, false);
  }

  if (showExitAccess && (exitAccessV2.centerline?.length || exitAccess.centerline?.length)) {
    const centerline = exitAccessV2.centerline?.length ? exitAccessV2.centerline : exitAccess.centerline;
    ctx.strokeStyle = 'rgba(254,215,170,0.76)';
    ctx.lineWidth = 1.55 / scale;
    ctx.setLineDash([]);
    drawPathOrPolyline(ctx, cache?.exitAccessV2Centerline || cache?.exitAccessCenterline, centerline, false);
  }

  if (pitCorridorVisible && showEntryExit && v2.centerline?.length) {
    drawMarker(ctx, v2.start, scale, '#22c55e', 5.8);
    drawMarker(ctx, v2.end, scale, '#fb923c', 5.8);
    if (showLabels) {
      drawLabel(ctx, v2.start, scale, 'Entry', '#bbf7d0', labelOptions);
      drawLabel(ctx, v2.end, scale, 'Exit', '#fed7aa', labelOptions);
    }
  }

  if (showLabels) {
    if (pitCorridorVisible && v2.centerline?.length) {
      drawLabel(ctx, v2.centerline[Math.floor(v2.centerline.length / 2)], scale, 'Pit Corridor V2', '#fef08a', labelOptions);
    }
    if (showEntryAccess) {
      const point = accessLabelPoint(entryAccessV2, entryAccess.centerline);
      if (point) drawLabel(ctx, point, scale, 'Entry Access Area', '#bbf7d0', labelOptions);
    }
    if (showExitAccess) {
      const point = accessLabelPoint(exitAccessV2, exitAccess.centerline);
      if (point) drawLabel(ctx, point, scale, 'Exit Access Area', '#fed7aa', labelOptions);
    }
  }

  ctx.restore();
}

export function drawPitAreaCarPath(ctx, pitlaneData, history = [], scale, options = {}) {
  if (!pitlaneData || !history?.length || !options.showCarPath) return;

  const step = Math.max(1, Math.ceil(history.length / 260));
  const samples = history
    .filter((_, index) => index % step === 0)
    .map((frame) => {
      const point = frame.mapPosition || { x: frame.x, y: frame.y ?? frame.z };
      const canvasPoint = mapToCanvasPoint(point);
      if (!canvasPoint) return null;
      return {
        point: canvasPoint,
        classification: classifyPointInTrackArea(point, pitlaneData),
      };
    })
    .filter(Boolean);
  if (!samples.length) return;

  ctx.save();
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.globalAlpha = 0.78;
  for (let index = 1; index < samples.length; index += 1) {
    const prev = samples[index - 1];
    const current = samples[index];
    const segmentDistance = Math.hypot(current.point.x - prev.point.x, current.point.y - prev.point.y);
    if (!Number.isFinite(segmentDistance) || segmentDistance > 38) continue;
    ctx.beginPath();
    ctx.moveTo(prev.point.x, prev.point.y);
    ctx.lineTo(current.point.x, current.point.y);
    ctx.strokeStyle = colorForTrackArea(current.classification.area);
    ctx.lineWidth = 1.7 / scale;
    ctx.stroke();
  }

  const markerStep = Math.max(1, Math.ceil(samples.length / 190));
  for (let index = 0; index < samples.length; index += markerStep) {
    const sample = samples[index];
    ctx.beginPath();
    ctx.arc(sample.point.x, sample.point.y, 2.1 / scale, 0, Math.PI * 2);
    ctx.fillStyle = colorForTrackArea(sample.classification.area);
    ctx.fill();
  }
  ctx.restore();
}
