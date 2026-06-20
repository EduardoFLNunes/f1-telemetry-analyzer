import { transformWorldToMapPoint } from '../../utils/spatialTransform';

export const RACING_LINE_OVERLAY_MODES = [
  'LINE_ONLY',
  'DIAGNOSTIC',
  'BRAKE_ACCEL',
  'RAW_REFERENCE_SAMPLES',
  'RACING_LINE_POINTS',
  'SEGMENT_CONNECTIONS',
  'SMOOTHED_LINE',
  'PLAYER_INPUT_GRADIENT',
];

const MODE_LABELS = {
  LINE_ONLY: 'LINE',
  DIAGNOSTIC: 'DIAG',
  BRAKE_ACCEL: 'PEDAL',
  RAW_REFERENCE_SAMPLES: 'RAW',
  RACING_LINE_POINTS: 'PTS',
  SEGMENT_CONNECTIONS: 'SEGS',
  SMOOTHED_LINE: 'SMTH',
  PLAYER_INPUT_GRADIENT: 'SPEED',
};

const ISSUE_COLORS = {
  LOW_CORNER_SPEED: '#fbbf24',
  LOW_EXIT_SPEED: '#fb923c',
  BRAKING_TOO_EARLY: '#fb7185',
  BRAKING_TOO_LATE: '#f97316',
  ACCELERATING_TOO_LATE: '#facc15',
  TRAJECTORY: '#a855f7',
};

function finiteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value);
}

function currentProgress(frame) {
  const candidates = [
    frame?.lapProgress,
    frame?.p,
    frame?.normalizedSplinePosition,
    frame?.splinePosition,
    frame?.spline_t,
  ];
  for (const candidate of candidates) {
    const value = Number(candidate);
    if (Number.isFinite(value) && value >= 0 && value <= 1) return Math.max(0, Math.min(1, value));
  }
  return null;
}

function clamp01(value) {
  return Math.max(0, Math.min(1, value));
}

function normalizePedal(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return clamp01(number > 1 ? number / 100 : number);
}

function entrySpeedKmh(entry) {
  const candidates = [
    entry?.point?.speedKmh,
    entry?.point?.avgSpeedKmh,
    entry?.point?.maxSpeedKmh,
  ];
  for (const candidate of candidates) {
    const value = Number(candidate);
    if (Number.isFinite(value) && value >= 0) return value;
  }
  return null;
}

function speedGradientStats(entries) {
  const speeds = entries
    .map((entry) => entrySpeedKmh(entry))
    .filter((value) => finiteNumber(value));
  if (!speeds.length) return { minSpeed: 0, maxSpeed: 1 };
  return {
    minSpeed: Math.min(...speeds),
    maxSpeed: Math.max(...speeds),
  };
}

function speedBrakeGradientColor(entry, stats) {
  const brake = normalizePedal(entry?.point?.brake);
  if (brake > 0.05) {
    const t = clamp01(brake);
    const lightness = 47 - t * 24;
    return `hsla(0, 88%, ${lightness.toFixed(1)}%, 0.98)`;
  }

  const speed = entrySpeedKmh(entry);
  if (!finiteNumber(speed)) return 'rgba(148,163,184,0.28)';
  const range = Math.max(1, (stats?.maxSpeed || 1) - (stats?.minSpeed || 0));
  const t = clamp01((speed - (stats?.minSpeed || 0)) / range);
  const hue = 0 + t * 142;
  const saturation = 78 - Math.abs(t - 0.5) * 18;
  const lightness = 44 + Math.sin(t * Math.PI) * 20 - (1 - t) * 8;
  return `hsla(${hue.toFixed(1)}, ${saturation.toFixed(1)}%, ${lightness.toFixed(1)}%, 0.98)`;
}

function currentSegmentIndex(frame, microSectorCount) {
  const progress = currentProgress(frame);
  if (!finiteNumber(progress) || !Number.isFinite(microSectorCount) || microSectorCount <= 0) return null;
  return Math.min(microSectorCount - 1, Math.max(0, Math.floor(progress * microSectorCount)));
}

function pointProgress(point, fallback = null) {
  const candidates = [
    point?.splinePosition,
    point?.normalizedSplinePosition,
    finiteNumber(point?.splineStart) && finiteNumber(point?.splineEnd)
      ? (point.splineStart + point.splineEnd) / 2
      : null,
    fallback,
  ];
  for (const candidate of candidates) {
    const value = Number(candidate);
    if (Number.isFinite(value)) return Math.max(0, Math.min(1, value));
  }
  return null;
}

function distance(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function median(values) {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

function buildLinearPath(points) {
  if (typeof Path2D === 'undefined' || points.length < 2) return null;
  const path = new Path2D();
  path.moveTo(points[0].x, points[0].y);
  for (let index = 1; index < points.length; index += 1) {
    path.lineTo(points[index].x, points[index].y);
  }
  return path;
}

function buildSmoothPath(points) {
  if (typeof Path2D === 'undefined' || points.length < 2) return null;
  const path = new Path2D();
  path.moveTo(points[0].x, points[0].y);
  if (points.length === 2) {
    path.lineTo(points[1].x, points[1].y);
    return path;
  }

  for (let index = 1; index < points.length - 1; index += 1) {
    const current = points[index];
    const next = points[index + 1];
    path.quadraticCurveTo(
      current.x,
      current.y,
      (current.x + next.x) / 2,
      (current.y + next.y) / 2,
    );
  }
  const last = points[points.length - 1];
  path.lineTo(last.x, last.y);
  return path;
}

function drawPolyline(ctx, points) {
  if (points.length < 2) return;
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  for (let index = 1; index < points.length; index += 1) {
    ctx.lineTo(points[index].x, points[index].y);
  }
  ctx.stroke();
}

function drawPathOrPolyline(ctx, chunk) {
  if (chunk.path) {
    ctx.stroke(chunk.path);
    return;
  }
  drawPolyline(ctx, chunk.points);
}

function marker(ctx, point, radius, fill, scale, stroke = 'rgba(2,6,23,0.78)') {
  ctx.beginPath();
  ctx.arc(point.x, point.y, radius / scale, 0, Math.PI * 2);
  ctx.fillStyle = fill;
  ctx.fill();
  ctx.lineWidth = 0.9 / scale;
  ctx.strokeStyle = stroke;
  ctx.stroke();
}

function issueColor(segment) {
  if (!segment) return null;
  if (finiteNumber(segment.estimatedDeltaSeconds) && segment.estimatedDeltaSeconds < -0.03) return '#34d399';
  if (segment.mainIssue === 'GOOD' || segment.mainIssue === 'UNKNOWN' || segment.mainIssue === 'INSUFFICIENT_DATA') return null;
  return ISSUE_COLORS[segment.mainIssue] || '#fbbf24';
}

function buildChunks(entries, { smooth = false, breakOnSegmentGap = false } = {}) {
  const distances = [];
  for (let index = 1; index < entries.length; index += 1) {
    const previous = entries[index - 1];
    const entry = entries[index];
    if (previous.connectable && entry.connectable) {
      distances.push(distance(previous.map, entry.map));
    }
  }

  const typical = median(distances.filter((value) => value > 0));
  const maxJump = Math.max(typical * 4.5, 180);
  let abnormalConnectionCount = 0;
  const chunks = [];
  let current = [];

  entries.forEach((entry, index) => {
    const previous = entries[index - 1];
    const previousSegment = previous?.point?.segmentIndex;
    const currentSegment = entry?.point?.segmentIndex;
    const hasSegmentGap =
      breakOnSegmentGap &&
      finiteNumber(previousSegment) &&
      finiteNumber(currentSegment) &&
      currentSegment - previousSegment > 1;
    const hasJump = previous && typical > 0 && distance(previous.map, entry.map) > maxJump;
    const breaks = !entry.connectable || (previous && !previous.connectable) || hasSegmentGap || hasJump;

    if (hasJump) abnormalConnectionCount += 1;
    if (breaks) {
      if (current.length >= 2) {
        chunks.push({
          points: current,
          path: smooth ? buildSmoothPath(current) : buildLinearPath(current),
        });
      }
      current = entry.connectable ? [entry.map] : [];
      return;
    }

    current.push(entry.map);
  });

  if (current.length >= 2) {
    chunks.push({
      points: current,
      path: smooth ? buildSmoothPath(current) : buildLinearPath(current),
    });
  }

  return {
    chunks,
    typicalDistance: typical,
    maxJump,
    abnormalConnectionCount,
  };
}

function buildMicroEntries(payload, comparisons) {
  const points = payload?.racingLine?.points || [];
  return points
    .slice()
    .sort((a, b) => a.segmentIndex - b.segmentIndex)
    .map((point) => ({
      source: 'microsector',
      point,
      progress: pointProgress(point),
      map: transformWorldToMapPoint({ worldPosition: point.position }),
      connectable: point.confidence !== 'INSUFFICIENT_DATA',
      comparison: comparisons.get(point.segmentIndex) || null,
    }))
    .filter((entry) => entry.map);
}

function buildRawReferenceEntries(payload, microSectorCount) {
  const visualPoints = payload?.racingLine?.visualLine?.points || [];
  return visualPoints
    .slice()
    .sort((a, b) => {
      const ap = pointProgress(a, 0);
      const bp = pointProgress(b, 0);
      return ap - bp;
    })
    .map((point, index) => {
      const progress = pointProgress(point, index / Math.max(1, visualPoints.length - 1));
      return {
        source: 'raw_reference_sample',
        point: {
          ...point,
          segmentIndex: finiteNumber(progress)
            ? Math.min(microSectorCount - 1, Math.max(0, Math.floor(progress * microSectorCount)))
            : index,
        },
        progress,
        map: transformWorldToMapPoint({ worldPosition: point.position }),
        connectable: true,
        comparison: null,
      };
    })
    .filter((entry) => entry.map);
}

function nearestByProgress(entries, progress) {
  if (!finiteNumber(progress) || !entries.length) return null;
  let nearest = null;
  let best = Number.POSITIVE_INFINITY;
  entries.forEach((entry) => {
    if (!finiteNumber(entry.progress)) return;
    const delta = Math.abs(entry.progress - progress);
    if (delta < best) {
      best = delta;
      nearest = entry;
    }
  });
  return nearest;
}

export function prepareRacingLineOverlay(payload) {
  if (payload?.status !== 'READY' || !payload?.racingLine?.points?.length) {
    return {
      status: payload?.status || 'INSUFFICIENT_DATA',
      payload,
      microSectorCount: 0,
      baseChunks: [],
      smoothedChunks: [],
      segmentChunks: [],
      baseEntries: [],
      rawEntries: [],
      entries: [],
      mapPositions: [],
      biggestLossSegmentIndex: null,
      debug: {
        visualSource: 'UNAVAILABLE',
        rawReferenceSampleCount: 0,
        rawDisplayPointCount: 0,
        racingLinePointCount: 0,
        validRacingLinePointCount: 0,
        smoothingAppliedToMainLine: false,
        suspectedIssue: payload?.debug?.reason || 'endpoint_not_ready',
      },
    };
  }

  const comparisons = new Map(
    (payload.comparison?.segments || []).map((segment) => [segment.segmentIndex, segment]),
  );
  const microSectorCount = payload.racingLine.microSectorCount || payload.racingLine.points.length;
  const microEntries = buildMicroEntries(payload, comparisons);
  const rawEntries = buildRawReferenceEntries(payload, microSectorCount);
  const baseEntries = rawEntries.length >= 2 ? rawEntries : microEntries;
  const baseResult = buildChunks(baseEntries, { smooth: false, breakOnSegmentGap: false });
  const segmentResult = buildChunks(microEntries, { smooth: false, breakOnSegmentGap: true });
  const smoothedResult = buildChunks(microEntries, { smooth: true, breakOnSegmentGap: true });
  const gradientStats = speedGradientStats(baseEntries);
  const usingRawSamples = rawEntries.length >= 2;

  return {
    status: payload.status,
    payload,
    microSectorCount,
    baseChunks: baseResult.chunks,
    smoothedChunks: smoothedResult.chunks,
    segmentChunks: segmentResult.chunks,
    baseEntries,
    rawEntries,
    entries: microEntries,
    mapPositions: baseEntries.map((entry) => entry.map),
    biggestLossSegmentIndex: payload.comparison?.biggestLosses?.[0]?.segmentIndex ?? null,
    debug: {
      visualSource: usingRawSamples ? 'REFERENCE_LAP_SAMPLES' : 'MICROSECTOR_POINTS_FALLBACK',
      rawReferenceSampleCount: payload.racingLine.visualLine?.sampleCount || rawEntries.length,
      rawDisplayPointCount: rawEntries.length,
      racingLinePointCount: payload.racingLine.points.length,
      validRacingLinePointCount: microEntries.filter((entry) => entry.connectable).length,
      smoothingAppliedToMainLine: false,
      debugLayers: [
        'SMOOTHED_LINE',
        'RAW_REFERENCE_SAMPLES',
        'RACING_LINE_POINTS',
        'SEGMENT_CONNECTIONS',
        'PLAYER_INPUT_GRADIENT',
      ],
      baseAbnormalConnectionCount: baseResult.abnormalConnectionCount,
      baseMaxJump: baseResult.maxJump,
      speedGradientMinKmh: gradientStats.minSpeed,
      speedGradientMaxKmh: gradientStats.maxSpeed,
      microAbnormalConnectionCount: segmentResult.abnormalConnectionCount,
      suspectedIssue: usingRawSamples && rawEntries.length > microEntries.length * 3
        ? 'MICROSECTOR_VISUAL_UNDERSAMPLING_AND_SMOOTHING'
        : 'NONE_DETECTED',
    },
  };
}

export function racingLineMapPositions(prepared) {
  return prepared?.mapPositions || [];
}

export function racingLineModeLabel(mode) {
  return MODE_LABELS[mode] || MODE_LABELS.LINE_ONLY;
}

function strokeChunks(ctx, chunks, scale, strokeStyle, lineWidth) {
  ctx.strokeStyle = strokeStyle;
  ctx.lineWidth = lineWidth / scale;
  chunks.forEach((chunk) => drawPathOrPolyline(ctx, chunk));
}

function drawBaseLine(ctx, prepared, scale, alpha = 1, options = {}) {
  ctx.save();
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  if (!options.simple) {
    strokeChunks(ctx, prepared.baseChunks, scale, `rgba(34,211,238,${0.14 * alpha})`, 3.2);
  }
  strokeChunks(ctx, prepared.baseChunks, scale, `rgba(34,211,238,${0.82 * alpha})`, options.simple ? 1.05 : 1.25);
  ctx.restore();
}

function drawDiagnosticMarkers(ctx, prepared, scale, currentIndex) {
  prepared.entries.forEach((entry) => {
    const color = issueColor(entry.comparison);
    if (!color) return;
    const isCurrent = entry.point.segmentIndex === currentIndex;
    marker(ctx, entry.map, isCurrent ? 3.6 : 2.6, `${color}cc`, scale, `${color}ee`);
  });
}

function drawBrakeAccelMarkers(ctx, prepared, scale, currentIndex) {
  prepared.entries.forEach((entry) => {
    const isCurrent = entry.point.segmentIndex === currentIndex;
    if (entry.point.brakingZone) {
      marker(ctx, entry.map, isCurrent ? 3.8 : 2.4, 'rgba(251,113,133,0.78)', scale, 'rgba(251,113,133,0.92)');
    } else if (entry.point.accelerationZone) {
      marker(ctx, entry.map, isCurrent ? 3.8 : 2.4, 'rgba(52,211,153,0.72)', scale, 'rgba(52,211,153,0.90)');
    }
  });
}

function drawRawReferenceSamples(ctx, prepared, scale) {
  prepared.rawEntries.forEach((entry) => {
    marker(ctx, entry.map, 1.45, 'rgba(125,211,252,0.62)', scale, 'rgba(125,211,252,0.20)');
  });
}

function drawRacingLinePoints(ctx, prepared, scale, currentIndex) {
  prepared.entries.forEach((entry) => {
    const isCurrent = entry.point.segmentIndex === currentIndex;
    marker(ctx, entry.map, isCurrent ? 3.8 : 2.3, 'rgba(251,191,36,0.78)', scale, 'rgba(251,191,36,0.92)');
  });
}

function drawSegmentConnections(ctx, prepared, scale) {
  ctx.save();
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  strokeChunks(ctx, prepared.segmentChunks, scale, 'rgba(251,191,36,0.72)', 1.35);
  ctx.restore();
}

function drawSmoothedLine(ctx, prepared, scale) {
  ctx.save();
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  strokeChunks(ctx, prepared.smoothedChunks, scale, 'rgba(168,85,247,0.26)', 3.4);
  strokeChunks(ctx, prepared.smoothedChunks, scale, 'rgba(168,85,247,0.86)', 1.35);
  ctx.restore();
}

function drawPlayerInputGradient(ctx, prepared, scale) {
  const entries = prepared.baseEntries || prepared.rawEntries || [];
  if (entries.length < 2) return;

  const maxJump = prepared.debug?.baseMaxJump || 180;
  const stats = {
    minSpeed: prepared.debug?.speedGradientMinKmh,
    maxSpeed: prepared.debug?.speedGradientMaxKmh,
  };
  ctx.save();
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.lineWidth = 2.45 / scale;
  for (let index = 1; index < entries.length; index += 1) {
    const previous = entries[index - 1];
    const current = entries[index];
    if (!previous?.map || !current?.map || distance(previous.map, current.map) > maxJump) continue;
    const previousSpeed = entrySpeedKmh(previous);
    const currentSpeed = entrySpeedKmh(current);
    const colorEntry = {
      point: {
        speedKmh: finiteNumber(previousSpeed) && finiteNumber(currentSpeed)
          ? (previousSpeed + currentSpeed) / 2
          : (currentSpeed ?? previousSpeed),
        brake: Math.max(normalizePedal(previous.point?.brake), normalizePedal(current.point?.brake)),
      },
    };
    ctx.strokeStyle = speedBrakeGradientColor(colorEntry, stats);
    ctx.beginPath();
    ctx.moveTo(previous.map.x, previous.map.y);
    ctx.lineTo(current.map.x, current.map.y);
    ctx.stroke();
  }
  ctx.restore();
}

function drawCurrentMarker(ctx, prepared, scale, currentIndex, progress) {
  const rawCurrent = nearestByProgress(prepared.rawEntries, progress);
  const current = rawCurrent || prepared.entries.find((entry) => entry.point.segmentIndex === currentIndex);
  if (!current) return;
  marker(ctx, current.map, 5.3, 'rgba(34,211,238,0.18)', scale, 'rgba(34,211,238,0.78)');
}

function drawSpeedGradientLegend(ctx, x, y, width, prepared) {
  const gradient = ctx.createLinearGradient(x, y, x + width, y);
  gradient.addColorStop(0, '#7f1d1d');
  gradient.addColorStop(0.24, '#dc2626');
  gradient.addColorStop(0.46, '#fb923c');
  gradient.addColorStop(0.62, '#fef08a');
  gradient.addColorStop(0.78, '#86efac');
  gradient.addColorStop(1, '#047857');
  ctx.fillStyle = gradient;
  ctx.fillRect(x, y, width, 7);
  ctx.strokeStyle = 'rgba(226,232,240,0.32)';
  ctx.lineWidth = 1;
  ctx.strokeRect(x, y, width, 7);

  const minSpeed = prepared.debug?.speedGradientMinKmh;
  const maxSpeed = prepared.debug?.speedGradientMaxKmh;
  ctx.fillStyle = '#94a3b8';
  ctx.font = '7px "JetBrains Mono", monospace';
  ctx.fillText(finiteNumber(minSpeed) ? `${Math.round(minSpeed)} KMH` : 'LOW', x, y + 19);
  const maxLabel = finiteNumber(maxSpeed) ? `${Math.round(maxSpeed)} KMH` : 'HIGH';
  ctx.fillText(maxLabel, x + width - ctx.measureText(maxLabel).width, y + 19);
  ctx.fillStyle = '#cbd5e1';
  ctx.fillText('FREIO / BAIXA', x + width * 0.28 - 38, y + 19);
  ctx.fillText('ALTA', x + width * 0.76, y + 19);
}

export function drawPreparedRacingLineOverlay(ctx, prepared, frame, scale, mode = 'LINE_ONLY', options = {}) {
  if (!prepared || !Number.isFinite(scale) || scale <= 0) return 0;
  const ready = prepared.status === 'READY' && (prepared.baseChunks.length || prepared.rawEntries.length || prepared.entries.length);
  if (!ready) return 0;

  const start = performance.now();
  const simple = Boolean(options.simple);
  const safeMode = simple ? 'LINE_ONLY' : (RACING_LINE_OVERLAY_MODES.includes(mode) ? mode : 'LINE_ONLY');
  const progress = currentProgress(frame);
  const currentIndex = currentSegmentIndex(frame, prepared.microSectorCount);

  if (safeMode === 'RAW_REFERENCE_SAMPLES') {
    drawRawReferenceSamples(ctx, prepared, scale);
    drawCurrentMarker(ctx, prepared, scale, currentIndex, progress);
  } else if (safeMode === 'RACING_LINE_POINTS') {
    drawRacingLinePoints(ctx, prepared, scale, currentIndex);
    drawCurrentMarker(ctx, prepared, scale, currentIndex, progress);
  } else if (safeMode === 'SEGMENT_CONNECTIONS') {
    drawSegmentConnections(ctx, prepared, scale);
    drawRacingLinePoints(ctx, prepared, scale, currentIndex);
    drawCurrentMarker(ctx, prepared, scale, currentIndex, progress);
  } else if (safeMode === 'SMOOTHED_LINE') {
    drawBaseLine(ctx, prepared, scale, 0.35, options);
    drawSmoothedLine(ctx, prepared, scale);
    drawRacingLinePoints(ctx, prepared, scale, currentIndex);
    drawCurrentMarker(ctx, prepared, scale, currentIndex, progress);
  } else if (safeMode === 'PLAYER_INPUT_GRADIENT') {
    drawBaseLine(ctx, prepared, scale, 0.22, options);
    drawPlayerInputGradient(ctx, prepared, scale);
    drawCurrentMarker(ctx, prepared, scale, currentIndex, progress);
  } else {
    drawBaseLine(ctx, prepared, scale, 1, options);
    drawCurrentMarker(ctx, prepared, scale, currentIndex, progress);
    if (safeMode === 'DIAGNOSTIC') {
      drawDiagnosticMarkers(ctx, prepared, scale, currentIndex);
    } else if (safeMode === 'BRAKE_ACCEL') {
      drawBrakeAccelMarkers(ctx, prepared, scale, currentIndex);
    }
  }

  return performance.now() - start;
}

export function drawRacingLineLegend(ctx, width, height, prepared, mode = 'LINE_ONLY') {
  if (!prepared) return;
  ctx.save();
  ctx.resetTransform();

  const status = prepared.status || 'INSUFFICIENT_DATA';
  const ready = status === 'READY' && (prepared.baseChunks.length || prepared.rawEntries.length || prepared.entries.length);
  const panelWidth = Math.min(280, Math.max(220, width - 28));
  const safeMode = RACING_LINE_OVERLAY_MODES.includes(mode) ? mode : 'LINE_ONLY';
  const panelHeight = safeMode === 'PLAYER_INPUT_GRADIENT' ? 72 : 58;
  const x = 14;
  const y = height - panelHeight - 14;

  ctx.fillStyle = 'rgba(6,8,16,0.72)';
  ctx.strokeStyle = ready ? 'rgba(34,211,238,0.16)' : 'rgba(251,191,36,0.18)';
  ctx.lineWidth = 1;
  ctx.fillRect(x, y, panelWidth, panelHeight);
  ctx.strokeRect(x, y, panelWidth, panelHeight);

  ctx.fillStyle = ready ? '#22d3ee' : '#fbbf24';
  ctx.font = '700 8px "JetBrains Mono", monospace';
  ctx.fillText(ready ? `RACING LINE ${racingLineModeLabel(safeMode)}` : 'RACING LINE INDISPONIVEL', x + 10, y + 16);

  ctx.fillStyle = '#94a3b8';
  ctx.font = '7px "JetBrains Mono", monospace';
  if (!ready) {
    ctx.fillText('Aguardando volta de referencia valida.', x + 10, y + 36);
    ctx.restore();
    return;
  }

  const rawCount = prepared.debug?.rawDisplayPointCount || prepared.rawEntries.length;
  const microCount = prepared.debug?.racingLinePointCount || prepared.entries.length;
  ctx.fillText(`VIS ${prepared.debug?.visualSource || 'UNKNOWN'} / RAW ${rawCount} / MICRO ${microCount}`, x + 10, y + 32);

  if (safeMode === 'PLAYER_INPUT_GRADIENT') {
    drawSpeedGradientLegend(ctx, x + 10, y + 43, panelWidth - 20, prepared);
    ctx.restore();
    return;
  }

  const items = safeMode === 'BRAKE_ACCEL'
    ? [['REF', '#22d3ee'], ['FREIO', '#fb7185'], ['ACEL', '#34d399']]
    : safeMode === 'DIAGNOSTIC'
      ? [['REF', '#22d3ee'], ['PERDA', '#fbbf24'], ['TRAJ', '#a855f7']]
      : safeMode === 'RAW_REFERENCE_SAMPLES'
        ? [['SAMPLES', '#7dd3fc']]
        : safeMode === 'RACING_LINE_POINTS'
          ? [['MICRO PTS', '#fbbf24']]
          : safeMode === 'SEGMENT_CONNECTIONS'
            ? [['MICRO SEGS', '#fbbf24']]
            : safeMode === 'SMOOTHED_LINE'
              ? [['REF REAL', '#22d3ee'], ['SMOOTH', '#a855f7']]
              : [['REF REAL', '#22d3ee']];

  items.forEach(([label, color], index) => {
    const lx = x + 10 + index * 82;
    const ly = y + 47;
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(lx, ly);
    ctx.lineTo(lx + 16, ly);
    ctx.stroke();
    ctx.fillStyle = '#94a3b8';
    ctx.fillText(label, lx + 22, ly + 2);
  });

  ctx.restore();
}
