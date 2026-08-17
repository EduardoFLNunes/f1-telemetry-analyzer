import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTelemetryStore } from '../../store/useTelemetryStore';
import { useRenderCounter } from '../../hooks/useRenderCounter';
import { api } from '../../api/client';
import { drawCar, drawOpponentCar } from './CarRenderer';
import { applyCameraTransform, computeTrackBounds, CameraState, FOLLOW_VIEW_METERS } from './CameraController';
import { drawHud, drawMiniMap, drawTrackSurface, screenSpace } from './OverlayRenderer';
import { drawBroadcastCar, drawBroadcastHud, drawBroadcastTrail } from './BroadcastOverlay';
import { resolveSampleMapPosition, MapPosition } from '../../utils/spatialTransform';
import {
  drawPreparedRacingLineOverlay,
  drawRacingLineLegend,
  prepareRacingLineOverlay,
  racingLineModeLabel,
  RACING_LINE_OVERLAY_MODES,
  PreparedRacingLineOverlay,
} from './RacingLineOverlay';

const MAP_RENDER_FRAME_MS = 1000 / 60;
const MAP_RENDER_FRAME_MS_BY_MODE: Record<string, number> = {
  QUALITY: 1000 / 60,
  BALANCED: 1000 / 60,
  PERFORMANCE: 1000 / 60,
};
const RACING_LINE_POLL_MS = 6000;
const HISTORY_WINDOW_BY_MODE: Record<string, number> = {
  QUALITY: 1800,
  BALANCED: 1200,
  PERFORMANCE: 600,
};
const PERFORMANCE_MODES = ['QUALITY', 'BALANCED', 'PERFORMANCE'] as const;
const MAX_REPLAY_TRACE_GAP_METERS = 180;
// Same reasoning as the racing line: trace weights are metres, not pixels, so the
// trace stays proportional to the track when zoomed in, with a floor so it stays
// visible when the whole circuit is on screen.
const TRACE_METERS_PER_UNIT = 0.72;
const MIN_TRACE_SCREEN_PX = 1.2;

function scaledTraceWidth(weight: number, scale: number): number {
  return Math.max(weight * TRACE_METERS_PER_UNIT, MIN_TRACE_SCREEN_PX / Math.max(scale, 1e-6));
}
const REPLAY_TRACK_BOUNDS_MARGIN_METERS = 80;

function normalizeTrack(trackData: any): any {
  if (!trackData) return null;

  const centerY = trackData.centerline?.y || trackData.centerline?.z || [];
  const visualCenterY = trackData.visualCenterline?.y || trackData.visualCenterline?.z || [];
  const leftY = trackData.left_edge?.y || trackData.left_edge?.z || [];
  const rightY = trackData.right_edge?.y || trackData.right_edge?.z || [];

  return {
    ...trackData,
    trackLength: trackData.trackLength || trackData.length_meters || 0,
    centerline: {
      ...trackData.centerline,
      y: centerY,
    },
    visualCenterline: trackData.visualCenterline
      ? {
          ...trackData.visualCenterline,
          y: visualCenterY,
        }
      : null,
    left_edge: {
      ...trackData.left_edge,
      y: leftY,
    },
    right_edge: {
      ...trackData.right_edge,
      y: rightY,
    },
  };
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

/** The circuit's name, for the line the broadcast look keeps at the bottom. */
export function trackCaption(trackData: any): string | null {
  const raw = trackData?.trackName || trackData?.name || trackData?.metadata?.trackName;
  if (typeof raw !== 'string') return null;
  const cleaned = raw.replace(/[_-]+/g, ' ').trim();
  return cleaned ? cleaned.toUpperCase() : null;
}

function percentile(values: number[], ratio: number): number {
  if (!values.length) return 0;
  const sorted = values
    .filter((value) => Number.isFinite(value) && value >= 0)
    .slice()
    .sort((a, b) => a - b);
  if (!sorted.length) return 0;
  return sorted[Math.min(Math.floor((sorted.length - 1) * ratio), sorted.length - 1)];
}

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function positionFromSpline(trackData: any, splinePosition: unknown): MapPosition | null {
  if (!trackData || !isFiniteNumber(splinePosition)) return null;

  const center = trackData.centerline || {};
  const xs = center.x || [];
  const ys = center.y || [];
  if (!xs.length || xs.length !== ys.length) return null;

  const p = Math.max(0, Math.min(1, splinePosition));
  const spline = Array.isArray(center.spline_t) ? center.spline_t : null;

  if (spline && spline.length === xs.length && spline.length > 1) {
    for (let i = 1; i < spline.length; i += 1) {
      const prevP = Number(spline[i - 1]);
      const nextP = Number(spline[i]);
      if (!Number.isFinite(prevP) || !Number.isFinite(nextP)) continue;
      if (p <= nextP) {
        const t = nextP === prevP ? 0 : Math.max(0, Math.min(1, (p - prevP) / (nextP - prevP)));
        return {
          x: lerp(xs[i - 1], xs[i], t),
          y: lerp(ys[i - 1], ys[i], t),
        };
      }
    }
  }

  const idx = p * (xs.length - 1);
  const lo = Math.floor(idx);
  const hi = Math.min(xs.length - 1, lo + 1);
  const t = idx - lo;
  return {
    x: lerp(xs[lo], xs[hi], t),
    y: lerp(ys[lo], ys[hi], t),
  };
}

function resolveOpponentRenderState(opponent: any, trackData: any): any {
  const mapPosition = opponent?.mapPosition;
  if (mapPosition && isFiniteNumber(mapPosition.x) && isFiniteNumber(mapPosition.y)) {
    return opponent;
  }

  const fallbackPosition = positionFromSpline(trackData, opponent?.splinePosition);
  if (!fallbackPosition) return null;
  return {
    ...opponent,
    mapPosition: fallbackPosition,
  };
}

function sampleMapPosition(sample: unknown): MapPosition | null {
  return resolveSampleMapPosition(sample);
}

type TraceEntry = { sample: any; position: MapPosition; index: number };
type TraceOptions = {
  maxPoints?: number;
  width?: number;
  alpha?: number;
  dashed?: boolean;
  maxGapMeters?: number;
  usePrevious?: boolean;
  maxMarkers?: number;
  radius?: number;
};

function drawLapTrace(ctx: CanvasRenderingContext2D, samples: any[], scale: number, color: string, options: TraceOptions = {}) {
  if (!Array.isArray(samples) || samples.length < 2) return;
  const entries = sampleTraceEntries(samples, options.maxPoints || 2200);
  if (entries.length < 2) return;
  const segments = traceEntrySegments(entries, options);
  if (!segments.length) return;
  const width = options.width || 2.2;
  const alpha = options.alpha || 0.72;
  ctx.save();
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.strokeStyle = color;
  ctx.globalAlpha = alpha;
  ctx.lineWidth = scaledTraceWidth(width, scale);
  if (options.dashed) ctx.setLineDash([10 / scale, 8 / scale]);
  segments.forEach((segment) => {
    ctx.beginPath();
    segment.forEach(({ position }, index) => {
      if (index === 0) {
        ctx.moveTo(position.x, position.y);
      } else {
        ctx.lineTo(position.x, position.y);
      }
    });
    ctx.stroke();
  });
  ctx.restore();
}

function sampleTraceEntries(samples: any[], maxPoints = 2200): TraceEntry[] {
  if (!Array.isArray(samples) || samples.length === 0) return [];
  const stride = Math.max(1, Math.ceil(samples.length / Math.max(1, maxPoints)));
  const entries: TraceEntry[] = [];
  for (let index = 0; index < samples.length; index += stride) {
    const position = sampleMapPosition(samples[index]);
    if (position) entries.push({ sample: samples[index], position, index });
  }
  const lastIndex = samples.length - 1;
  if (lastIndex >= 0 && entries[entries.length - 1]?.index !== lastIndex) {
    const position = sampleMapPosition(samples[lastIndex]);
    if (position) entries.push({ sample: samples[lastIndex], position, index: lastIndex });
  }
  return entries;
}

function sampleLapTime(sample: any): number | null {
  const candidates = [sample?.lapTime, sample?.lap_time, sample?.currentLapTime, sample?.sessionTime, sample?.session_time];
  for (const candidate of candidates) {
    const number = Number(candidate);
    if (Number.isFinite(number)) return number;
  }
  return null;
}

function sampleDistance(sample: any): number | null {
  const candidates = [sample?.s, sample?.distanceAlongTrack, sample?.lapDistance];
  for (const candidate of candidates) {
    const number = Number(candidate);
    if (Number.isFinite(number)) return number;
  }
  return null;
}

function shouldBreakTrace(previous: TraceEntry | undefined, current: TraceEntry | undefined, options: TraceOptions = {}): boolean {
  if (!previous || !current) return false;
  const maxGap = options.maxGapMeters || MAX_REPLAY_TRACE_GAP_METERS;
  const distance = Math.hypot(
    current.position.x - previous.position.x,
    current.position.y - previous.position.y,
  );
  if (distance > maxGap) return true;

  const previousProgress = sampleProgress(previous.sample);
  const currentProgress = sampleProgress(current.sample);
  if (isFiniteNumber(previousProgress) && isFiniteNumber(currentProgress) && currentProgress < previousProgress - 0.18) {
    return true;
  }

  const previousLapTime = sampleLapTime(previous.sample);
  const currentLapTime = sampleLapTime(current.sample);
  if (isFiniteNumber(previousLapTime) && isFiniteNumber(currentLapTime) && currentLapTime + 0.35 < previousLapTime) {
    return true;
  }

  const previousDistance = sampleDistance(previous.sample);
  const currentDistance = sampleDistance(current.sample);
  return isFiniteNumber(previousDistance) && isFiniteNumber(currentDistance) && currentDistance + 120 < previousDistance;
}

function traceEntrySegments(entries: TraceEntry[], options: TraceOptions = {}): TraceEntry[][] {
  const segments: TraceEntry[][] = [];
  let current: TraceEntry[] = [];
  entries.forEach((entry) => {
    if (current.length > 0 && shouldBreakTrace(current[current.length - 1], entry, options)) {
      if (current.length > 1) segments.push(current);
      current = [entry];
    } else {
      current.push(entry);
    }
  });
  if (current.length > 1) segments.push(current);
  return segments;
}

function sampleSpeedKmh(sample: any): number | null {
  if (isFiniteNumber(sample?.speedKmh)) return sample.speedKmh;
  if (isFiniteNumber(sample?.speed)) return sample.speed * 3.6;
  return null;
}

function normalizedPedal(value: unknown): number {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.max(0, Math.min(1, number > 1 ? number / 100 : number));
}

function sampleProgress(sample: any): number | null {
  const candidates = [
    sample?.lapProgress,
    sample?.p,
    sample?.normalizedSplinePosition,
    sample?.splinePosition,
    sample?.spline_t,
  ];
  for (const candidate of candidates) {
    const number = Number(candidate);
    if (Number.isFinite(number) && number >= 0 && number <= 1) return number;
  }
  return null;
}

function speedStats(entries: TraceEntry[]): { min: number; max: number } {
  const speeds = entries
    .map((entry) => sampleSpeedKmh(entry.sample))
    .filter((value): value is number => isFiniteNumber(value));
  if (!speeds.length) return { min: 0, max: 1 };
  return { min: Math.min(...speeds), max: Math.max(...speeds) };
}

function replaySpeedColor(speed: number | null, stats: { min: number; max: number }): string {
  if (!isFiniteNumber(speed)) return 'rgba(148,163,184,0.42)';
  const range = Math.max(1, stats.max - stats.min);
  const t = Math.max(0, Math.min(1, (speed - stats.min) / range));
  const hue = 0 + t * 142;
  const lightness = 43 + Math.sin(t * Math.PI) * 18;
  return `hsla(${hue.toFixed(1)}, 82%, ${lightness.toFixed(1)}%, 0.94)`;
}

function replayPedalColor(sample: any): string {
  const brake = normalizedPedal(sample?.brake);
  const throttle = normalizedPedal(sample?.throttle);
  if (brake > 0.05) return `rgba(251,113,133,${Math.max(0.38, Math.min(0.95, brake)).toFixed(2)})`;
  if (throttle > 0.08) return `rgba(52,211,153,${Math.max(0.32, Math.min(0.92, throttle)).toFixed(2)})`;
  return 'rgba(203,213,225,0.34)';
}

function drawTraceSegments(
  ctx: CanvasRenderingContext2D,
  entries: TraceEntry[],
  scale: number,
  colorForEntry: (entry: TraceEntry, previous: TraceEntry, current: TraceEntry) => string,
  options: TraceOptions = {},
) {
  if (entries.length < 2) return;
  const segments = traceEntrySegments(entries, options);
  if (!segments.length) return;
  ctx.save();
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.lineWidth = scaledTraceWidth(options.width || 2.5, scale);
  segments.forEach((segment) => {
    for (let index = 1; index < segment.length; index += 1) {
      const previous = segment[index - 1];
      const current = segment[index];
      const colorEntry = options.usePrevious ? previous : current;
      ctx.strokeStyle = colorForEntry(colorEntry, previous, current);
      ctx.beginPath();
      ctx.moveTo(previous.position.x, previous.position.y);
      ctx.lineTo(current.position.x, current.position.y);
      ctx.stroke();
    }
  });
  ctx.restore();
}

function drawReplayPoints(ctx: CanvasRenderingContext2D, entries: TraceEntry[], scale: number, color: string, options: TraceOptions = {}) {
  if (!entries.length) return;
  const stride = Math.max(1, Math.ceil(entries.length / (options.maxMarkers || 180)));
  ctx.save();
  entries.forEach((entry, index) => {
    if (index % stride !== 0 && index !== entries.length - 1) return;
    ctx.beginPath();
    ctx.arc(entry.position.x, entry.position.y, (options.radius || 2.1) / scale, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
  });
  ctx.restore();
}

function smoothTraceEntries(entries: TraceEntry[]): TraceEntry[] {
  if (entries.length < 5) return entries;
  return entries.map((entry, index) => {
    const start = Math.max(0, index - 2);
    const end = Math.min(entries.length - 1, index + 2);
    let x = 0;
    let y = 0;
    let count = 0;
    for (let cursor = start; cursor <= end; cursor += 1) {
      x += entries[cursor].position.x;
      y += entries[cursor].position.y;
      count += 1;
    }
    return {
      ...entry,
      position: { x: x / count, y: y / count },
    };
  });
}

function drawReplaySegmentMarkers(ctx: CanvasRenderingContext2D, entries: TraceEntry[], scale: number) {
  if (!entries.length) return;
  const seen = new Set<number>();
  ctx.save();
  ctx.font = `${Math.max(7 / scale, 4)}px "JetBrains Mono", monospace`;
  entries.forEach((entry) => {
    const progress = sampleProgress(entry.sample);
    if (!isFiniteNumber(progress)) return;
    const segment = Math.min(9, Math.max(0, Math.floor(progress * 10)));
    if (seen.has(segment)) return;
    seen.add(segment);
    ctx.beginPath();
    ctx.arc(entry.position.x, entry.position.y, 4.2 / scale, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(15,23,42,0.78)';
    ctx.fill();
    ctx.lineWidth = 1 / scale;
    ctx.strokeStyle = 'rgba(250,204,21,0.78)';
    ctx.stroke();
    ctx.fillStyle = '#fde68a';
    ctx.fillText(String(segment + 1), entry.position.x + 5 / scale, entry.position.y - 5 / scale);
  });
  ctx.restore();
}

function drawReplayDiagnosticMarkers(ctx: CanvasRenderingContext2D, entries: TraceEntry[], scale: number) {
  if (!entries.length) return;
  ctx.save();
  const stride = Math.max(1, Math.ceil(entries.length / 220));
  entries.forEach((entry, index) => {
    if (index % stride !== 0) return;
    const brake = normalizedPedal(entry.sample?.brake);
    const throttle = normalizedPedal(entry.sample?.throttle);
    const steering = Math.abs(Number(entry.sample?.steering) || 0);
    const coasting = brake < 0.04 && throttle < 0.06;
    const highSteerBrake = brake > 0.18 && steering > 0.38;
    if (!coasting && !highSteerBrake) return;
    ctx.beginPath();
    ctx.arc(entry.position.x, entry.position.y, (highSteerBrake ? 3.4 : 2.4) / scale, 0, Math.PI * 2);
    ctx.fillStyle = highSteerBrake ? 'rgba(251,113,133,0.78)' : 'rgba(251,191,36,0.68)';
    ctx.fill();
  });
  ctx.restore();
}

function drawReplayCurrentMarker(ctx: CanvasRenderingContext2D, frame: any, scale: number) {
  const position = sampleMapPosition(frame);
  if (!position) return;
  ctx.save();
  ctx.beginPath();
  ctx.arc(position.x, position.y, 6 / scale, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(250,204,21,0.18)';
  ctx.fill();
  ctx.lineWidth = 1.6 / scale;
  ctx.strokeStyle = 'rgba(250,204,21,0.96)';
  ctx.stroke();
  ctx.restore();
}

function trackMapBounds(trackData: any): { minX: number; maxX: number; minY: number; maxY: number } | null {
  if (!trackData) return null;
  const xs = [
    ...(trackData.left_edge?.x || []),
    ...(trackData.right_edge?.x || []),
    ...(trackData.centerline?.x || []),
  ].filter(Number.isFinite);
  const ys = [
    ...(trackData.left_edge?.y || trackData.left_edge?.z || []),
    ...(trackData.right_edge?.y || trackData.right_edge?.z || []),
    ...(trackData.centerline?.y || trackData.centerline?.z || []),
  ].filter(Number.isFinite);
  if (!xs.length || !ys.length) return null;
  return {
    minX: Math.min(...xs),
    maxX: Math.max(...xs),
    minY: Math.min(...ys),
    maxY: Math.max(...ys),
  };
}

function replayMapDiagnostics(
  entries: TraceEntry[],
  bounds: { minX: number; maxX: number; minY: number; maxY: number } | null,
  replayTrack: unknown,
  activeTrack: unknown,
): { warning: string | null; outsideRatio: number } | null {
  if (!bounds || !entries.length) return null;
  const margin = REPLAY_TRACK_BOUNDS_MARGIN_METERS;
  const outsideCount = entries.filter((entry) => (
    entry.position.x < bounds.minX - margin
    || entry.position.x > bounds.maxX + margin
    || entry.position.y < bounds.minY - margin
    || entry.position.y > bounds.maxY + margin
  )).length;
  const outsideRatio = outsideCount / entries.length;
  const normalizedReplayTrack = typeof replayTrack === 'string' ? replayTrack.trim().toLowerCase() : '';
  const normalizedActiveTrack = typeof activeTrack === 'string' ? activeTrack.trim().toLowerCase() : '';
  const trackMismatch = Boolean(
    normalizedReplayTrack
    && normalizedActiveTrack
    && !normalizedActiveTrack.includes(normalizedReplayTrack.split('_')[0]),
  );
  if (trackMismatch) {
    return { warning: 'Persisted lap track differs from active map', outsideRatio };
  }
  if (outsideRatio > 0.08) {
    return { warning: 'Replay coordinates out of track bounds', outsideRatio };
  }
  return { warning: null, outsideRatio };
}

function drawReplayLapOverlay(
  ctx: CanvasRenderingContext2D,
  replay: any,
  frame: any,
  scale: number,
  mode: string = 'LINE_ONLY',
  options: { simple?: boolean; trackBounds?: any; activeTrack?: any } = {},
): number {
  if (!replay?.active || !Number.isFinite(scale) || scale <= 0) return 0;
  const start = performance.now();
  const safeMode = options.simple ? 'LINE_ONLY' : ((RACING_LINE_OVERLAY_MODES as readonly string[]).includes(mode) ? mode : 'LINE_ONLY');
  const lapEntries = sampleTraceEntries(replay.samples, safeMode === 'RAW_REFERENCE_SAMPLES' ? 3000 : 2200);
  const referenceEntries = sampleTraceEntries(replay.referenceSamples || [], 2200);
  (window as any).__replayMapDiagnostics = replayMapDiagnostics(
    lapEntries,
    options.trackBounds,
    replay.track,
    options.activeTrack,
  );

  drawLapTrace(ctx, replay.referenceSamples || [], scale, '#a78bfa', { width: 2.0, alpha: 0.62, dashed: true });

  if (safeMode === 'PLAYER_INPUT_GRADIENT') {
    const stats = speedStats(lapEntries);
    drawTraceSegments(ctx, lapEntries, scale, (entry) => replaySpeedColor(sampleSpeedKmh(entry.sample), stats), { width: 3.0 });
  } else if (safeMode === 'BRAKE_ACCEL') {
    drawTraceSegments(ctx, lapEntries, scale, (entry) => replayPedalColor(entry.sample), { width: 3.0 });
  } else if (safeMode === 'RAW_REFERENCE_SAMPLES') {
    drawLapTrace(ctx, replay.samples || [], scale, '#facc15', { width: 1.4, alpha: 0.38, maxPoints: 3000 });
    drawReplayPoints(ctx, referenceEntries, scale, 'rgba(167,139,250,0.56)', { radius: 1.6, maxMarkers: 420 });
    drawReplayPoints(ctx, lapEntries, scale, 'rgba(250,204,21,0.66)', { radius: 1.7, maxMarkers: 520 });
  } else if (safeMode === 'RACING_LINE_POINTS') {
    drawLapTrace(ctx, replay.samples || [], scale, '#facc15', { width: 2.2, alpha: 0.46 });
    drawReplayPoints(ctx, lapEntries, scale, 'rgba(250,204,21,0.82)', { radius: 2.3, maxMarkers: 260 });
  } else if (safeMode === 'SEGMENT_CONNECTIONS') {
    drawLapTrace(ctx, replay.samples || [], scale, '#facc15', { width: 2.0, alpha: 0.58 });
    drawReplaySegmentMarkers(ctx, lapEntries, scale);
  } else if (safeMode === 'SMOOTHED_LINE') {
    drawLapTrace(ctx, replay.samples || [], scale, '#facc15', { width: 1.2, alpha: 0.28 });
    traceEntrySegments(lapEntries).forEach((segment) => {
      const smoothed = smoothTraceEntries(segment);
      drawTraceSegments(ctx, smoothed, scale, () => 'rgba(250,204,21,0.9)', { width: 2.8 });
    });
  } else {
    drawLapTrace(ctx, replay.samples || [], scale, '#facc15', { width: 2.8, alpha: 0.82 });
    if (safeMode === 'DIAGNOSTIC') {
      drawReplayDiagnosticMarkers(ctx, lapEntries, scale);
    }
  }

  drawReplayCurrentMarker(ctx, frame, scale);
  return performance.now() - start;
}

function drawReplayLegend(ctx: CanvasRenderingContext2D, width: number, height: number, replay: any, mode: string = 'LINE_ONLY') {
  if (!replay?.active) return;
  ctx.save();
  screenSpace(ctx);

  const safeMode = (RACING_LINE_OVERLAY_MODES as readonly string[]).includes(mode) ? mode : 'LINE_ONLY';
  const panelWidth = Math.min(292, Math.max(230, width - 28));
  const diagnostics = (window as any).__replayMapDiagnostics || null;
  const hasWarning = Boolean(diagnostics?.warning);
  const panelHeight = (safeMode === 'PLAYER_INPUT_GRADIENT' ? 72 : 58) + (hasWarning ? 14 : 0);
  const x = 14;
  const y = height - panelHeight - 14;
  ctx.fillStyle = 'rgba(6,8,16,0.76)';
  ctx.strokeStyle = 'rgba(250,204,21,0.18)';
  ctx.lineWidth = 1;
  ctx.fillRect(x, y, panelWidth, panelHeight);
  ctx.strokeRect(x, y, panelWidth, panelHeight);

  ctx.fillStyle = '#fde68a';
  ctx.font = '700 8px "JetBrains Mono", monospace';
  ctx.fillText(`PERSISTED LAP ${racingLineModeLabel(safeMode)}`, x + 10, y + 16);
  ctx.fillStyle = '#94a3b8';
  ctx.font = '7px "JetBrains Mono", monospace';
  const refText = replay.referenceSamples?.length ? `REF ROXA ${replay.referenceSamples.length}` : 'REF ROXA --';
  ctx.fillText(`USADA AMARELA ${replay.samples?.length || 0} / ${refText}`, x + 10, y + 32);

  if (hasWarning) {
    ctx.fillStyle = '#fb7185';
    ctx.fillText(diagnostics.warning, x + 10, y + 46);
  }

  if (safeMode === 'PLAYER_INPUT_GRADIENT') {
    const gradientY = y + (hasWarning ? 56 : 43);
    const gradient = ctx.createLinearGradient(x + 10, gradientY, x + panelWidth - 10, gradientY);
    gradient.addColorStop(0, '#7f1d1d');
    gradient.addColorStop(0.32, '#ef4444');
    gradient.addColorStop(0.5, '#facc15');
    gradient.addColorStop(0.76, '#22c55e');
    gradient.addColorStop(1, '#047857');
    ctx.fillStyle = gradient;
    ctx.fillRect(x + 10, gradientY, panelWidth - 20, 7);
    ctx.fillStyle = '#94a3b8';
    ctx.fillText('BAIXA', x + 10, gradientY + 20);
    ctx.fillText('ALTA', x + panelWidth - 42, gradientY + 20);
    ctx.restore();
    return;
  }

  const items: Array<[string, string]> = safeMode === 'BRAKE_ACCEL'
    ? [['FREIO', '#fb7185'], ['ACEL', '#34d399'], ['COAST', '#cbd5e1']]
    : safeMode === 'DIAGNOSTIC'
      ? [['COAST', '#fbbf24'], ['FREIO+VOL', '#fb7185'], ['ATUAL', '#facc15']]
      : [['REF', '#a78bfa'], ['USADA', '#facc15'], ['ATUAL', '#facc15']];
  items.forEach(([label, color], index) => {
    const lx = x + 10 + index * 82;
    const ly = y + (hasWarning ? 61 : 47);
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

function formatOpponentNumber(value: unknown, digits = 0): string {
  return isFiniteNumber(value) ? value.toFixed(digits) : '--';
}

function opponentDisplayName(opponent: any): string {
  const name = typeof opponent?.driverName === 'string' ? opponent.driverName.trim() : '';
  return name || 'Unknown';
}

function opponentSplinePercent(opponent: any): number | null {
  return isFiniteNumber(opponent?.splinePosition) ? opponent.splinePosition * 100 : null;
}

function isStaleOpponent(opponent: any, staleAfterSeconds: unknown): boolean {
  if (opponent?.status === 'stale') return true;
  if (!isFiniteNumber(opponent?.lastSeenTimestamp) || !isFiniteNumber(staleAfterSeconds)) return false;
  return (Date.now() / 1000) - opponent.lastSeenTimestamp > staleAfterSeconds;
}

function withEstimatedHeadings(opponents: any[], motionCache: Map<number, any>): any[] {
  return opponents.map((opponent) => {
    const position = opponent?.mapPosition;
    if (!position || !isFiniteNumber(position.x) || !isFiniteNumber(position.y)) return opponent;

    const previous = motionCache.get(opponent.carId);
    let estimatedHeading = previous?.estimatedHeading;
    if (previous && isFiniteNumber(previous.x) && isFiniteNumber(previous.y)) {
      const dx = position.x - previous.x;
      const dy = position.y - previous.y;
      if (Math.hypot(dx, dy) > 0.15) {
        estimatedHeading = Math.atan2(dy, dx) + Math.PI / 2;
      }
    }
    motionCache.set(opponent.carId, {
      x: position.x,
      y: position.y,
      estimatedHeading,
    });

    return isFiniteNumber(estimatedHeading)
      ? { ...opponent, estimatedHeading }
      : opponent;
  });
}

function interpolateMotionState(
  item: any,
  key: string | number,
  cache: Map<string | number, any>,
  now: number,
  defaultDurationMs: number,
  snapDistance = 120,
): any {
  const position = item?.mapPosition;
  if (!position || !isFiniteNumber(position.x) || !isFiniteNumber(position.y)) return item;
  const sampleStamp = item.timestamp ?? item.sessionTime ?? `${position.x}:${position.y}`;
  let state = cache.get(key);
  if (!state) {
    state = {
      from: position,
      to: position,
      startedAt: now,
      durationMs: defaultDurationMs,
      targetReceivedAt: now,
      sampleStamp,
    };
    cache.set(key, state);
    return item;
  }

  const currentProgress = Math.max(0, Math.min(1, (now - state.startedAt) / Math.max(state.durationMs, 1)));
  const current = {
    x: lerp(state.from.x, state.to.x, currentProgress),
    y: lerp(state.from.y, state.to.y, currentProgress),
  };
  const targetChanged = sampleStamp !== state.sampleStamp
    || Math.hypot(position.x - state.to.x, position.y - state.to.y) > 0.001;
  if (targetChanged) {
    const distance = Math.hypot(position.x - current.x, position.y - current.y);
    const observedInterval = Math.max(now - state.targetReceivedAt, 1);
    const durationMs = Math.max(
      defaultDurationMs * 0.55,
      Math.min(observedInterval, defaultDurationMs * 1.8),
    );
    state = distance > snapDistance
      ? {
          from: position,
          to: position,
          startedAt: now,
          durationMs: 1,
          targetReceivedAt: now,
          sampleStamp,
        }
      : {
          from: current,
          to: position,
          startedAt: now,
          durationMs,
          targetReceivedAt: now,
          sampleStamp,
        };
    cache.set(key, state);
  }

  const progress = Math.max(0, Math.min(1, (now - state.startedAt) / Math.max(state.durationMs, 1)));
  return {
    ...item,
    mapPosition: {
      x: lerp(state.from.x, state.to.x, progress),
      y: lerp(state.from.y, state.to.y, progress),
    },
  };
}

function worldToScreen(
  point: MapPosition | null | undefined,
  width: number,
  height: number,
  bounds: any,
  camera: CameraState,
  carFrame: any,
): { x: number; y: number; scale: number } | null {
  if (!point || !isFiniteNumber(point.x) || !isFiniteNumber(point.y)) return null;

  // Mirrors applyCameraTransform's follow branch: pan only, no rotation.
  if (camera.mode === 'FOLLOW' && carFrame) {
    const carPosition = carFrame.mapPosition || { x: carFrame.x, y: carFrame.z };
    if (!carPosition || !isFiniteNumber(carPosition.x) || !isFiniteNumber(carPosition.y)) return null;
    const scale = (height / FOLLOW_VIEW_METERS) * camera.zoom;
    return {
      x: width / 2 + (point.x - carPosition.x) * scale,
      y: height / 2 + (point.y - carPosition.y) * scale,
      scale,
    };
  }

  const scale = Math.min(width / bounds.w, height / bounds.h) * 0.84 * camera.zoom;
  return {
    x: width / 2 + camera.offset.x + (point.x - bounds.cx) * scale,
    y: height / 2 + camera.offset.y + (point.y - bounds.cy) * scale,
    scale,
  };
}

function labelText(opponent: any, mode: string): string {
  const carId = Number.isFinite(opponent?.carId) ? `#${opponent.carId}` : '#?';
  if (mode === 'id') return carId;
  const name = opponentDisplayName(opponent);
  const compactName = name.length > 13 ? `${name.slice(0, 12)}...` : name;
  const speed = isFiniteNumber(opponent?.speedKmh) ? `${Math.round(opponent.speedKmh)} km/h` : '-- km/h';
  const spline = isFiniteNumber(opponent?.splinePosition) ? `p${(opponent.splinePosition * 100).toFixed(1)}%` : 'p--';
  return `${carId} ${compactName} ${speed} ${spline}`;
}

type LabelRect = { x: number; y: number; width: number; height: number };

function labelRect(screen: { x: number; y: number }, mode: string, text: string): LabelRect | null {
  if (mode === 'none') return null;
  const width = mode === 'id' ? Math.max(22, text.length * 7 + 8) : Math.min(174, text.length * 6.3 + 12);
  const height = mode === 'id' ? 15 : 18;
  const x = mode === 'id' ? screen.x - width / 2 : screen.x + 10;
  const y = mode === 'id' ? screen.y - 25 : screen.y - 28;
  return { x, y, width, height };
}

function intersects(a: LabelRect, b: LabelRect, padding = 3): boolean {
  return !(
    a.x + a.width + padding < b.x ||
    b.x + b.width + padding < a.x ||
    a.y + a.height + padding < b.y ||
    b.y + b.height + padding < a.y
  );
}

type ScreenOpponent = { opponent: any; screen: { x: number; y: number; scale: number } };

function buildLabelModes(screenOpponents: ScreenOpponent[], scale: number): Map<number, string> {
  const baseMode = scale < 0.42 ? 'none' : (scale < 1.05 ? 'id' : 'full');
  const occupied: LabelRect[] = [];
  const modes = new Map<number, string>();

  screenOpponents.forEach(({ opponent, screen }) => {
    let mode = baseMode;
    if (mode === 'none') {
      modes.set(opponent.carId, 'none');
      return;
    }

    let text = labelText(opponent, mode);
    let rect = labelRect(screen, mode, text);
    if (rect && occupied.some((box) => intersects(box, rect as LabelRect))) {
      mode = mode === 'full' ? 'id' : 'none';
      text = labelText(opponent, mode);
      rect = labelRect(screen, mode, text);
    }
    if (rect && occupied.some((box) => intersects(box, rect as LabelRect))) {
      mode = 'none';
      rect = null;
    }
    if (rect) occupied.push(rect);
    modes.set(opponent.carId, mode);
  });

  return modes;
}

function findOpponentHit(screenOpponents: ScreenOpponent[], x: number, y: number): (ScreenOpponent & { distance: number }) | null {
  let best: (ScreenOpponent & { distance: number }) | null = null;
  screenOpponents.forEach((entry) => {
    const distance = Math.hypot(entry.screen.x - x, entry.screen.y - y);
    if (distance <= 16 && (!best || distance < best.distance)) {
      best = { ...entry, distance };
    }
  });
  return best;
}

export const TrackRenderer = React.memo(function TrackRenderer({ trackData }: { trackData: any }) {
  useRenderCounter('TrackRenderer');
  const performanceMode = useTelemetryStore((state) => state.performanceMode);
  const setPerformanceMode = useTelemetryStore((state) => state.setPerformanceMode);
  const replayActive = useTelemetryStore((state) => state.offlineReplay.active);
  const replayLapNumber = useTelemetryStore((state) => state.offlineReplay.lapNumber);
  const replayTrack = useTelemetryStore((state) => state.offlineReplay.track);
  const replaySource = useTelemetryStore((state) => state.offlineReplay.source);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const animationRef = useRef<number | null>(null);
  const lastCanvasRenderRef = useRef(0);
  const playerInterpolationRef = useRef(new Map<string | number, any>());
  const opponentInterpolationRef = useRef(new Map<string | number, any>());
  const opponentMotionRef = useRef(new Map<number, any>());
  const screenOpponentsRef = useRef<ScreenOpponent[]>([]);
  const racingLineOverlayRef = useRef<PreparedRacingLineOverlay | null>(null);
  // Follow is what the map is for: one car, the road it is on, and where that
  // road goes next. The whole circuit at once is the exception, not the default.
  const [cameraMode, setCameraMode] = useState<'OVERVIEW' | 'FOLLOW'>('FOLLOW');
  const [showRacingLine, setShowRacingLine] = useState(true);
  const [showOpponents, setShowOpponents] = useState(true);
  const [racingLineMode, setRacingLineMode] = useState('LINE_ONLY');
  const showRacingLineRef = useRef(true);
  const showOpponentsRef = useRef(true);
  const racingLineModeRef = useRef('LINE_ONLY');
  const performanceModeRef = useRef('BALANCED');
  const [hoveredOpponent, setHoveredOpponent] = useState<{ opponent: any; x: number; y: number } | null>(null);
  const [selectedOpponent, setSelectedOpponent] = useState<{ opponent: any; x: number; y: number } | null>(null);
  const hoveredOpponentRef = useRef<{ opponent: any; x: number; y: number } | null>(null);
  const selectedOpponentRef = useRef<{ opponent: any; x: number; y: number } | null>(null);
  const perfRef = useRef({
    frames: 0,
    renderMs: 0,
    lastAt: performance.now(),
    lastWsMessages: 0,
    lastTelemetryMessages: 0,
    lastOpponentsMessages: 0,
    lastTelemetryStoreUpdates: 0,
    lastOpponentsStoreUpdates: 0,
    lastTraceFrames: 0,
    lastTraceRenderMs: 0,
    lastTelemetryDropped: 0,
    lastOpponentsDropped: 0,
    lastRacingLineOverlayMs: 0,
    lastHttpRequests: 0,
    lastHttpDurationMs: 0,
    frameDeltas: [] as number[],
    renderDurations: [] as number[],
    staticDrawDurations: [] as number[],
    opponentsTransformDurations: [] as number[],
    opponentsDrawDurations: [] as number[],
    playerDrawDurations: [] as number[],
    previousFrameTime: 0,
  });
  const [opponentsPanelOpen, setOpponentsPanelOpen] = useState(true);
  const [mapSize, setMapSize] = useState({ width: 0, height: 0 });
  const [panelOpponents, setPanelOpponents] = useState<any[]>([]);
  const [panelOpponentsMeta, setPanelOpponentsMeta] = useState<any>({
    source: 'opponents_collector',
    count: 0,
    track: null,
    sessionTime: null,
    lastUpdateTimestamp: null,
    staleAfterSeconds: null,
  });
  const [showPerf, setShowPerf] = useState(false);
  const [perfStats, setPerfStats] = useState({
    fps: 0,
    avgRenderMs: 0,
    opponentsRendered: 0,
    wsHz: 0,
    telemetryHz: 0,
    opponentsHz: 0,
    telemetryStoreHz: 0,
    opponentsStoreHz: 0,
    traceFps: 0,
    avgTraceRenderMs: 0,
    telemetryDroppedHz: 0,
    opponentsDroppedHz: 0,
    racingLineOverlayMs: 0,
    httpHz: 0,
    httpAvgMs: 0,
    currentLapSamples: 0,
    previousLapSamples: 0,
    dashboardRps: 0,
    trackRendererRps: 0,
    tracesRps: 0,
    comparisonRps: 0,
    ggDiagramRps: 0,
    linePanelRps: 0,
    hiddenPanelRps: 0,
    p95FrameMs: 0,
    p99FrameMs: 0,
    staticDrawMs: 0,
    opponentsTransformMs: 0,
    opponentsDrawMs: 0,
    playerDrawMs: 0,
    graphPoints: 0,
    traceCacheEntries: 0,
    liveTrajectoryPoints: 0,
    completedLapsHistory: 0,
    racingLineVisualPoints: 0,
    opponentSamples: 0,
    telemetryPayloadKb: 0,
    racingLinePayloadKb: 0,
    memoryEstimateMb: 0,
    performanceMode: 'BALANCED',
  });

  const cameraRef = useRef<CameraState & { isPanning: boolean; lastMouse: { x: number; y: number } }>({
    mode: 'FOLLOW',
    zoom: 1,
    offset: { x: 0, y: 0 },
    isPanning: false,
    lastMouse: { x: 0, y: 0 },
  });

  const normalizedTrack = useMemo(() => normalizeTrack(trackData), [trackData]);
  const bounds = useMemo(() => computeTrackBounds(normalizedTrack), [normalizedTrack]);
  const visibleOpponents = useMemo(
    () => (showOpponents ? panelOpponents : [])
      .map((opponent) => resolveOpponentRenderState(opponent, normalizedTrack))
      .filter(Boolean),
    [panelOpponents, normalizedTrack, showOpponents],
  );
  const sortedOpponents = useMemo(
    () => [...visibleOpponents].sort((a, b) => {
      const ap = opponentSplinePercent(a);
      const bp = opponentSplinePercent(b);
      if (isFiniteNumber(ap) && isFiniteNumber(bp)) return ap - bp;
      return (a.carId ?? 0) - (b.carId ?? 0);
    }),
    [visibleOpponents],
  );

  useEffect(() => {
    cameraRef.current.mode = cameraMode;
  }, [cameraMode]);


  useEffect(() => {
    showRacingLineRef.current = showRacingLine;
  }, [showRacingLine]);

  useEffect(() => {
    showOpponentsRef.current = showOpponents;
    if (!showOpponents) {
      setHoveredOpponent(null);
      setSelectedOpponent(null);
      screenOpponentsRef.current = [];
    }
  }, [showOpponents]);

  useEffect(() => {
    racingLineModeRef.current = racingLineMode;
  }, [racingLineMode]);

  useEffect(() => {
    performanceModeRef.current = performanceMode;
    if (performanceMode === 'PERFORMANCE' && racingLineModeRef.current !== 'LINE_ONLY') {
      setRacingLineMode('LINE_ONLY');
    }
  }, [performanceMode]);

  useEffect(() => {
    if (!showRacingLine || replayActive) {
      racingLineOverlayRef.current = null;
      return undefined;
    }

    let cancelled = false;
    const loadRacingLine = async () => {
      try {
        const needsComparison = racingLineModeRef.current === 'DIAGNOSTIC';
        const payload = await api.getRacingLine(50, {
          includeVisualLine: true,
          includeComparison: needsComparison,
        });
        if (!cancelled) {
          racingLineOverlayRef.current = prepareRacingLineOverlay(payload);
        }
      } catch {
        if (!cancelled) {
          racingLineOverlayRef.current = prepareRacingLineOverlay({
            status: 'INSUFFICIENT_DATA',
            racingLine: null,
            comparison: null,
            debug: { reason: 'endpoint_unavailable' },
          });
        }
      }
    };

    loadRacingLine();
    const interval = setInterval(loadRacingLine, RACING_LINE_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [showRacingLine, racingLineMode, replayActive]);

  useEffect(() => {
    hoveredOpponentRef.current = hoveredOpponent;
  }, [hoveredOpponent]);

  useEffect(() => {
    selectedOpponentRef.current = selectedOpponent;
  }, [selectedOpponent]);

  useEffect(() => {
    let lastOpponentsStamp: string | null = null;
    const interval = setInterval(() => {
      const { opponents, opponentsMeta } = useTelemetryStore.getState();
      const stamp = `${opponentsMeta?.lastUpdateTimestamp ?? 'none'}:${opponents.length}`;
      if (stamp === lastOpponentsStamp) return;
      lastOpponentsStamp = stamp;
      setPanelOpponents(opponents);
      setPanelOpponentsMeta(opponentsMeta);
    }, 250);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || typeof ResizeObserver === 'undefined') return undefined;

    const updateSize = () => {
      const rect = container.getBoundingClientRect();
      setMapSize({ width: rect.width, height: rect.height });
    };
    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return undefined;

    const ctx = canvas.getContext('2d');
    if (!ctx) return undefined;

    const render = (frameTime: number = performance.now()) => {
      const activePerformanceMode = performanceModeRef.current || 'BALANCED';
      const frameBudgetMs = MAP_RENDER_FRAME_MS_BY_MODE[activePerformanceMode] || MAP_RENDER_FRAME_MS;
      const simpleVisuals = activePerformanceMode === 'PERFORMANCE';
      if (frameTime - lastCanvasRenderRef.current < frameBudgetMs) {
        animationRef.current = requestAnimationFrame(render);
        return;
      }
      lastCanvasRenderRef.current = frameTime;
      const perf = perfRef.current;
      if (perf.previousFrameTime) {
        perf.frameDeltas.push(frameTime - perf.previousFrameTime);
        if (perf.frameDeltas.length > 180) perf.frameDeltas.shift();
      }
      perf.previousFrameTime = frameTime;

      const renderStart = performance.now();
      let staticDrawMs = 0;
      let opponentsTransformMs = 0;
      let opponentsDrawMs = 0;
      let playerDrawMs = 0;
      const rect = container.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      if (canvas.width !== Math.round(rect.width * dpr) || canvas.height !== Math.round(rect.height * dpr)) {
        canvas.width = Math.round(rect.width * dpr);
        canvas.height = Math.round(rect.height * dpr);
      }

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, rect.width, rect.height);
      // Near black, so the grey of the asphalt is the lightest thing on screen
      // until the paint and the car arrive on top of it.
      ctx.fillStyle = '#070707';
      ctx.fillRect(0, 0, rect.width, rect.height);

      const {
        latestFrame: storeFrame,
        history: liveHistory,
        opponents: liveOpponents,
        opponentsMeta: liveOpponentsMeta,
        offlineReplay,
      } = useTelemetryStore.getState();

      const replayActiveNow = Boolean(offlineReplay?.active && offlineReplay.samples?.length);
      const rawLiveFrame: any = replayActiveNow
        ? (offlineReplay.currentSample || offlineReplay.samples[offlineReplay.currentIndex || 0])
        : ((window as any).__latestFrame || storeFrame);
      const liveFrame = replayActiveNow
        ? rawLiveFrame
        : interpolateMotionState(
            rawLiveFrame,
            'player',
            playerInterpolationRef.current,
            frameTime,
            1000 / 30,
            160,
          );
      const renderHistory = replayActiveNow ? offlineReplay.samples : liveHistory;
      const historyWindow = HISTORY_WINDOW_BY_MODE[activePerformanceMode] || HISTORY_WINDOW_BY_MODE.BALANCED;
      const boundsHistory = replayActiveNow && normalizedTrack
        ? []
        : (replayActiveNow ? renderHistory : renderHistory.slice(-historyWindow));

      const opponentsTransformStarted = performance.now();
      const latestOpponents = Array.isArray((window as any).__latestOpponents?.opponents)
        ? (window as any).__latestOpponents.opponents
        : liveOpponents;
      const liveOpponentsForRender = (!replayActiveNow && showOpponentsRef.current) ? latestOpponents : [];
      const renderOpponents = withEstimatedHeadings(liveOpponentsForRender
        .map((opponent: any) => resolveOpponentRenderState(opponent, normalizedTrack))
        .filter(Boolean)
        .map((opponent: any) => interpolateMotionState(
          opponent,
          opponent.carId,
          opponentInterpolationRef.current,
          frameTime,
          1000 / 10,
          200,
        )), opponentMotionRef.current);
      const opponentPositions = renderOpponents
        .map((opponent: any) => opponent.mapPosition)
        .filter((position: any) => Number.isFinite(position?.x) && Number.isFinite(position?.y));
      opponentsTransformMs = performance.now() - opponentsTransformStarted;
      const boundsFrame = replayActiveNow && normalizedTrack ? null : liveFrame;
      const renderBounds = normalizedTrack
        ? computeTrackBounds(normalizedTrack, boundsHistory, boundsFrame, opponentPositions)
        : computeTrackBounds(null, boundsHistory, liveFrame, opponentPositions);

      ctx.save();
      const scale = applyCameraTransform(ctx, rect.width, rect.height, renderBounds, cameraRef.current, liveFrame);
      // Following one car is what the broadcast look is for; the overview keeps
      // the analytical HUD, where the whole lap and every rival are on screen.
      const broadcast = cameraRef.current.mode === 'FOLLOW' && Boolean(liveFrame);

      if (normalizedTrack) {
        const staticDrawStarted = performance.now();
        drawTrackSurface(ctx, normalizedTrack, renderBounds, scale);
        staticDrawMs = performance.now() - staticDrawStarted;
      }
      // Following the car, the whole lap drawn in yellow competes with the trail
      // for the same road; the racing line switch turns it off and leaves the
      // broadcast view clean. In overview it is the point of the picture.
      if (replayActiveNow && (!broadcast || showRacingLineRef.current)) {
        const overlayCost = drawReplayLapOverlay(
          ctx,
          offlineReplay,
          liveFrame,
          scale,
          showRacingLineRef.current ? racingLineModeRef.current : 'LINE_ONLY',
          {
            simple: simpleVisuals,
            trackBounds: trackMapBounds(normalizedTrack),
            activeTrack: normalizedTrack?.trackName || normalizedTrack?.name || normalizedTrack?.metadata?.trackName,
          },
        );
        perf.lastRacingLineOverlayMs = overlayCost;
        (window as any).__telemetryPerf = (window as any).__telemetryPerf || {};
        (window as any).__telemetryPerf.racingLineOverlayMs = overlayCost;
      } else if (showRacingLineRef.current && racingLineOverlayRef.current) {
        const overlayCost = drawPreparedRacingLineOverlay(
          ctx,
          racingLineOverlayRef.current,
          liveFrame,
          scale,
          racingLineModeRef.current,
          { simple: simpleVisuals },
        );
        perf.lastRacingLineOverlayMs = overlayCost;
        (window as any).__telemetryPerf = (window as any).__telemetryPerf || {};
        (window as any).__telemetryPerf.racingLineOverlayMs = overlayCost;
      }

      // The road just driven, on top of the reference lines and under the car.
      if (broadcast) {
        const trailSamples = replayActiveNow
          ? offlineReplay.samples.slice(0, (offlineReplay.currentIndex || 0) + 1)
          : renderHistory;
        drawBroadcastTrail(ctx, trailSamples, scale);
      }

      const screenOpponents: ScreenOpponent[] = renderOpponents
        .map((opponent: any) => ({
          opponent,
          screen: worldToScreen(opponent.mapPosition, rect.width, rect.height, renderBounds, cameraRef.current, liveFrame),
        }))
        .filter((entry: any): entry is ScreenOpponent => Number.isFinite(entry.screen?.x) && Number.isFinite(entry.screen?.y));
      screenOpponentsRef.current = screenOpponents;
      const labelModes = simpleVisuals ? new Map<number, string>() : buildLabelModes(screenOpponents, scale);

      const opponentsDrawStarted = performance.now();
      renderOpponents.forEach((opponent: any, index: number) => {
        const isHovered =
          hoveredOpponentRef.current?.opponent?.carId === opponent.carId ||
          selectedOpponentRef.current?.opponent?.carId === opponent.carId;
        drawOpponentCar(ctx, opponent, scale, index, {
          labelMode: simpleVisuals ? 'none' : (labelModes.get(opponent.carId) || 'none'),
          isHovered,
          isStale: isStaleOpponent(opponent, liveOpponentsMeta?.staleAfterSeconds),
          noGlow: simpleVisuals,
        });
      });
      opponentsDrawMs = performance.now() - opponentsDrawStarted;
      if (liveFrame) {
        const playerDrawStarted = performance.now();
        // A car shape is a smudge at follow zoom; a disc is a position.
        if (broadcast) {
          drawBroadcastCar(ctx, liveFrame, scale);
        } else {
          drawCar(ctx, liveFrame, scale, replayActiveNow ? '#facc15' : '#22d3ee', { noGlow: simpleVisuals });
        }
        playerDrawMs = performance.now() - playerDrawStarted;
      }

      ctx.restore();
      if (broadcast) {
        drawBroadcastHud(ctx, rect.width, rect.height, liveFrame, { caption: trackCaption(normalizedTrack) });
        // The inset moves to the free corner: the camera controls own the right.
        drawMiniMap(ctx, rect.width, rect.height, normalizedTrack, resolveSampleMapPosition(liveFrame), {
          corner: 'bottom-left',
          bare: true,
        });
      } else {
        drawHud(ctx, rect.width, rect.height, normalizedTrack, liveFrame, cameraRef.current, { performanceMode: activePerformanceMode });
        if (!simpleVisuals && replayActiveNow) {
          drawReplayLegend(ctx, rect.width, rect.height, offlineReplay, showRacingLineRef.current ? racingLineModeRef.current : 'LINE_ONLY');
        } else if (!simpleVisuals && showRacingLineRef.current && racingLineOverlayRef.current) {
          drawRacingLineLegend(ctx, rect.width, rect.height, racingLineOverlayRef.current, racingLineModeRef.current);
        }
      }

      const renderDuration = performance.now() - renderStart;
      perf.renderDurations.push(renderDuration);
      perf.staticDrawDurations.push(staticDrawMs);
      perf.opponentsTransformDurations.push(opponentsTransformMs);
      perf.opponentsDrawDurations.push(opponentsDrawMs);
      perf.playerDrawDurations.push(playerDrawMs);
      [
        perf.renderDurations,
        perf.staticDrawDurations,
        perf.opponentsTransformDurations,
        perf.opponentsDrawDurations,
        perf.playerDrawDurations,
      ].forEach((values) => {
        if (values.length > 180) values.shift();
      });
      perf.frames += 1;
      perf.renderMs += renderDuration;
      const now = performance.now();
      if (now - perf.lastAt >= 1000) {
        const seconds = (now - perf.lastAt) / 1000;
        const wsMetrics = (window as any).__telemetryPerf || {};
        const wsMessages = Number(wsMetrics.wsMessages || 0);
        const telemetryMessages = Number(wsMetrics.wsTelemetryMessages || 0);
        const opponentsMessages = Number(wsMetrics.wsOpponentsMessages || 0);
        const telemetryStoreUpdates = Number(wsMetrics.telemetryStoreUpdates || 0);
        const opponentsStoreUpdates = Number(wsMetrics.opponentsStoreUpdates || 0);
        const traceFrames = Number(wsMetrics.traceFrames || 0);
        const traceRenderMs = Number(wsMetrics.traceRenderMs || 0);
        const telemetryDropped = Number(wsMetrics.telemetryFramesDroppedForRender || 0);
        const opponentsDropped = Number(wsMetrics.opponentsFramesDroppedForRender || 0);
        const httpRequests = Number(wsMetrics.httpRequests || 0);
        const httpDurationMs = Number(wsMetrics.httpDurationMs || 0);
        const storeState = useTelemetryStore.getState();
        const traceFramesDelta = traceFrames - perf.lastTraceFrames;
        const traceRenderDelta = traceRenderMs - perf.lastTraceRenderMs;
        const httpRequestsDelta = httpRequests - perf.lastHttpRequests;
        const httpDurationDelta = httpDurationMs - perf.lastHttpDurationMs;
        const renderMetrics = (window as any).__renderMetrics || {};
        const p50FrameMs = percentile(perf.frameDeltas, 0.50);
        const p95FrameMs = percentile(perf.frameDeltas, 0.95);
        const p99FrameMs = percentile(perf.frameDeltas, 0.99);
        const p95RenderMs = percentile(perf.renderDurations, 0.95);
        const staticDrawP95 = percentile(perf.staticDrawDurations, 0.95);
        const opponentsTransformP95 = percentile(perf.opponentsTransformDurations, 0.95);
        const opponentsDrawP95 = percentile(perf.opponentsDrawDurations, 0.95);
        const playerDrawP95 = percentile(perf.playerDrawDurations, 0.95);
        const opponentSamples = Object.values(storeState.opponentHistoryByCarId || {})
          .reduce((sum: number, samples: any) => sum + (Array.isArray(samples) ? samples.length : 0), 0);
        const panelRps = [
          renderMetrics['AIEngineerPanel']?.fps || 0,
          renderMetrics['AIDebriefPanel']?.fps || 0,
          renderMetrics['LiveComparisonPanel']?.fps || 0,
          renderMetrics['RacingLineAnalysisPanel']?.fps || 0,
          renderMetrics['CarPhysicsDebugPanel']?.fps || 0,
        ].reduce((sum, value) => sum + value, 0);
        const memory = (performance as any).memory?.usedJSHeapSize
          ? (performance as any).memory.usedJSHeapSize / 1024 / 1024
          : 0;
        setPerfStats({
          performanceMode: activePerformanceMode,
          fps: perf.frames / seconds,
          avgRenderMs: perf.renderMs / Math.max(perf.frames, 1),
          p95FrameMs,
          p99FrameMs,
          staticDrawMs: staticDrawP95,
          opponentsTransformMs: opponentsTransformP95,
          opponentsDrawMs: opponentsDrawP95,
          playerDrawMs: playerDrawP95,
          opponentsRendered: renderOpponents.length,
          wsHz: (wsMessages - perf.lastWsMessages) / seconds,
          telemetryHz: (telemetryMessages - perf.lastTelemetryMessages) / seconds,
          opponentsHz: (opponentsMessages - perf.lastOpponentsMessages) / seconds,
          telemetryStoreHz: (telemetryStoreUpdates - perf.lastTelemetryStoreUpdates) / seconds,
          opponentsStoreHz: (opponentsStoreUpdates - perf.lastOpponentsStoreUpdates) / seconds,
          traceFps: traceFramesDelta / seconds,
          avgTraceRenderMs: traceRenderDelta / Math.max(traceFramesDelta, 1),
          telemetryDroppedHz: (telemetryDropped - perf.lastTelemetryDropped) / seconds,
          opponentsDroppedHz: (opponentsDropped - perf.lastOpponentsDropped) / seconds,
          racingLineOverlayMs: perf.lastRacingLineOverlayMs || 0,
          httpHz: httpRequestsDelta / seconds,
          httpAvgMs: httpDurationDelta / Math.max(httpRequestsDelta, 1),
          currentLapSamples: storeState.currentLapSamples?.length || 0,
          previousLapSamples: storeState.previousLapSamples?.length || 0,
          liveTrajectoryPoints: storeState.history?.length || 0,
          completedLapsHistory: storeState.completedLapsHistory?.length || 0,
          racingLineVisualPoints: storeState.offlineReplay?.active
            ? (storeState.offlineReplay.sampleCount || storeState.offlineReplay.samples?.length || 0)
            : (racingLineOverlayRef.current?.debug?.rawDisplayPointCount || 0),
          opponentSamples,
          graphPoints: Number(wsMetrics.graphPoints || 0),
          traceCacheEntries: Number(wsMetrics.traceCacheEntries || 0),
          telemetryPayloadKb: Number(wsMetrics.telemetryPayloadKb || 0),
          racingLinePayloadKb: Number(wsMetrics.racingLinePayloadKb || 0),
          memoryEstimateMb: memory,
          dashboardRps: renderMetrics['Dashboard']?.fps || 0,
          trackRendererRps: renderMetrics['TrackRenderer']?.fps || 0,
          tracesRps: renderMetrics['TelemetryTraces']?.fps || 0,
          ggDiagramRps: renderMetrics['GGDiagram']?.fps || 0,
          linePanelRps: renderMetrics['RacingLineAnalysisPanel']?.fps || 0,
          comparisonRps: renderMetrics['LiveComparisonPanel']?.fps || 0,
          hiddenPanelRps: panelRps,
        });
        const trackPointCount = (normalizedTrack?.centerline?.x?.length || 0)
          + (normalizedTrack?.left_edge?.x?.length || 0)
          + (normalizedTrack?.right_edge?.x?.length || 0);
        (window as any).__telemetryPerf = (window as any).__telemetryPerf || {};
        (window as any).__telemetryPerf.trackRenderer = {
          fps: perf.frames / seconds,
          frameMs: { p50: p50FrameMs, p95: p95FrameMs, p99: p99FrameMs },
          renderMs: {
            avg: perf.renderMs / Math.max(perf.frames, 1),
            p95: p95RenderMs,
          },
          staticTrackDrawMsP95: staticDrawP95,
          opponentsTransformMsP95: opponentsTransformP95,
          opponentsDrawMsP95: opponentsDrawP95,
          playerDrawMsP95: playerDrawP95,
          opponentsDrawnPerFrame: renderOpponents.length,
          trackPointsDrawnPerFrame: trackPointCount,
          racingLinePointsDrawnPerFrame: racingLineOverlayRef.current?.debug?.rawDisplayPointCount || 0,
          opponentsOverlayEnabled: showOpponentsRef.current,
          storeUpdateMs: {
            playerAvg: Number(wsMetrics.telemetryStoreUpdateMs || 0) / Math.max(telemetryStoreUpdates, 1),
            opponentsAvg: Number(wsMetrics.opponentsStoreUpdateMs || 0) / Math.max(opponentsStoreUpdates, 1),
          },
          payloadByType: wsMetrics.wsPayloadByType || {},
          parseByType: wsMetrics.wsParseByType || {},
        };
        perf.frames = 0;
        perf.renderMs = 0;
        perf.lastAt = now;
        perf.lastWsMessages = wsMessages;
        perf.lastTelemetryMessages = telemetryMessages;
        perf.lastOpponentsMessages = opponentsMessages;
        perf.lastTelemetryStoreUpdates = telemetryStoreUpdates;
        perf.lastOpponentsStoreUpdates = opponentsStoreUpdates;
        perf.lastTraceFrames = traceFrames;
        perf.lastTraceRenderMs = traceRenderMs;
        perf.lastTelemetryDropped = telemetryDropped;
        perf.lastOpponentsDropped = opponentsDropped;
        perf.lastRacingLineOverlayMs = 0;
        perf.lastHttpRequests = httpRequests;
        perf.lastHttpDurationMs = httpDurationMs;
        perf.frameDeltas = [];
        perf.renderDurations = [];
        perf.staticDrawDurations = [];
        perf.opponentsTransformDurations = [];
        perf.opponentsDrawDurations = [];
        perf.playerDrawDurations = [];
      }
      animationRef.current = requestAnimationFrame(render);
    };

    animationRef.current = requestAnimationFrame(render);
    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
    };
  }, [bounds, normalizedTrack]);

  const handleWheel = useCallback((event: React.WheelEvent<HTMLDivElement>) => {
    event.preventDefault();
    const factor = event.deltaY < 0 ? 1.12 : 0.9;
    cameraRef.current.zoom = Math.max(0.2, Math.min(28, cameraRef.current.zoom * factor));
  }, []);

  const getOpponentHitFromEvent = useCallback((event: React.MouseEvent<HTMLDivElement>) => {
    const container = containerRef.current;
    if (!container) return null;
    const rect = container.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const hit = findOpponentHit(screenOpponentsRef.current, x, y);
    if (!hit) return null;
    return {
      opponent: hit.opponent,
      x: Math.max(8, Math.min(event.clientX + 14, window.innerWidth - 236)),
      y: Math.max(8, Math.min(event.clientY - 12, window.innerHeight - 178)),
    };
  }, []);

  const handleMouseDown = useCallback((event: React.MouseEvent<HTMLDivElement>) => {
    if (cameraRef.current.mode !== 'OVERVIEW') return;
    if (getOpponentHitFromEvent(event)) return;
    cameraRef.current.isPanning = true;
    cameraRef.current.lastMouse = { x: event.clientX, y: event.clientY };
  }, [getOpponentHitFromEvent]);

  const handleMouseMove = useCallback((event: React.MouseEvent<HTMLDivElement>) => {
    const camera = cameraRef.current;
    if (camera.isPanning) {
      camera.offset.x += event.clientX - camera.lastMouse.x;
      camera.offset.y += event.clientY - camera.lastMouse.y;
      camera.lastMouse = { x: event.clientX, y: event.clientY };
      setHoveredOpponent(null);
      return;
    }

    const hit = getOpponentHitFromEvent(event);
    setHoveredOpponent((previous) => {
      if (!hit && !previous) return previous;
      if (
        hit &&
        previous &&
        hit.opponent?.carId === previous.opponent?.carId &&
        Math.abs(hit.x - previous.x) < 2 &&
        Math.abs(hit.y - previous.y) < 2
      ) {
        return previous;
      }
      return hit;
    });
  }, [getOpponentHitFromEvent]);

  const handleClick = useCallback((event: React.MouseEvent<HTMLDivElement>) => {
    const hit = getOpponentHitFromEvent(event);
    setSelectedOpponent(hit);
  }, [getOpponentHitFromEvent]);

  const stopPan = useCallback(() => {
    cameraRef.current.isPanning = false;
  }, []);

  const handleMouseLeave = useCallback(() => {
    setHoveredOpponent(null);
    stopPan();
  }, [stopPan]);

  const activeOpponentTooltip = hoveredOpponent || selectedOpponent;
  const tooltipOpponent = activeOpponentTooltip?.opponent;
  const tooltipWorld = tooltipOpponent?.worldPosition || {};
  const totalOpponents = panelOpponentsMeta.count || visibleOpponents.length;
  const compactOpponentsPanel = mapSize.width > 0 && mapSize.width < 260;
  const availableRacingLineModes = performanceMode === 'PERFORMANCE'
    ? ['LINE_ONLY']
    : RACING_LINE_OVERLAY_MODES;

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full overflow-hidden select-none cursor-crosshair"
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={stopPan}
      onMouseLeave={handleMouseLeave}
      onClick={handleClick}
    >
      <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />

      {replayActive && (
        <div
          className="absolute top-3 left-3 panel px-2 py-1.5"
          style={{
            zIndex: 72,
            background: 'rgba(8,12,22,0.88)',
            borderColor: 'rgba(250,204,21,0.28)',
            pointerEvents: 'none',
          }}
        >
          <div className="num text-[8px] font-bold uppercase text-yellow-200">Replay offline</div>
          <div className="num text-[7px] uppercase text-slate-500">
            L{replayLapNumber ?? '--'} / Fonte: {replaySource || 'persisted lap'}
          </div>
          {replayTrack && (
            <div className="num text-[7px] uppercase text-slate-600 truncate" style={{ maxWidth: 220 }}>
              {String(replayTrack).replace(/[_-]+/g, ' ')}
            </div>
          )}
        </div>
      )}

      <div
        className="absolute top-3 right-3 flex flex-col gap-1"
        style={{ zIndex: 70, pointerEvents: 'auto' }}
        onMouseDown={(event) => event.stopPropagation()}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="panel px-1.5 py-1 flex gap-1">
          {(['OVERVIEW', 'FOLLOW'] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setCameraMode(mode)}
              className={`px-2 py-0.5 num text-[7px] uppercase rounded-sm transition-all ${
                cameraMode === mode ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30' : 'text-slate-600 hover:text-slate-400'
              }`}
            >
              {mode}
            </button>
          ))}
        </div>
        <div className="panel px-1.5 py-1">
          <button
            type="button"
            onClick={() => setShowRacingLine((visible) => !visible)}
            className={`num text-[7px] uppercase rounded-sm transition-all ${
              showRacingLine ? 'text-cyan-300' : 'text-slate-600 hover:text-slate-400'
            }`}
            style={{
              background: showRacingLine ? 'rgba(34,211,238,0.08)' : 'transparent',
              border: showRacingLine ? '1px solid rgba(34,211,238,0.22)' : '1px solid transparent',
              padding: '2px 6px',
              cursor: 'pointer',
            }}
          >
            RACING LINE
          </button>
        </div>
        <div className="panel px-1.5 py-1">
          <button
            type="button"
            onClick={() => setShowOpponents((visible) => !visible)}
            className={`num text-[7px] uppercase rounded-sm transition-all ${
              showOpponents ? 'text-orange-300' : 'text-sky-300'
            }`}
            style={{
              background: showOpponents ? 'rgba(249,115,22,0.08)' : 'rgba(56,189,248,0.09)',
              border: showOpponents ? '1px solid rgba(249,115,22,0.22)' : '1px solid rgba(56,189,248,0.24)',
              padding: '2px 6px',
              cursor: 'pointer',
            }}
            title="Alternar visualizacao de oponentes no mapa"
          >
            {showOpponents ? 'OPPONENTS ON' : 'PLAYER ONLY'}
          </button>
        </div>
        {showRacingLine && (
          <div className="panel px-1.5 py-1 grid grid-cols-4 gap-1">
            {availableRacingLineModes.map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => setRacingLineMode(mode)}
                className={`num text-[7px] uppercase rounded-sm transition-all ${
                  racingLineMode === mode ? 'text-cyan-300' : 'text-slate-600 hover:text-slate-400'
                }`}
                style={{
                  background: racingLineMode === mode ? 'rgba(34,211,238,0.08)' : 'transparent',
                  border: racingLineMode === mode ? '1px solid rgba(34,211,238,0.22)' : '1px solid transparent',
                  padding: '2px 4px',
                  cursor: 'pointer',
                }}
              >
                {racingLineModeLabel(mode)}
              </button>
            ))}
          </div>
        )}
        <div className="panel px-1.5 py-1">
          <button
            type="button"
            onClick={() => setShowPerf((visible) => !visible)}
            className="num text-[7px] uppercase rounded-sm transition-all text-slate-500 hover:text-cyan-300"
            style={{ background: 'transparent', border: 0, padding: '1px 4px', cursor: 'pointer' }}
          >
            PERF
          </button>
        </div>
        {showPerf && (
          <div className="panel px-2 py-1.5 w-[184px]">
            <div className="grid grid-cols-3 gap-1 mb-1.5">
              {PERFORMANCE_MODES.map((mode) => (
                <button
                  key={mode}
                  type="button"
                  onClick={() => setPerformanceMode(mode)}
                  className="num text-[6px] uppercase rounded-sm transition-all"
                  style={{
                    height: 18,
                    border: performanceMode === mode ? '1px solid rgba(34,211,238,0.34)' : '1px solid rgba(255,255,255,0.05)',
                    background: performanceMode === mode ? 'rgba(34,211,238,0.10)' : 'rgba(255,255,255,0.02)',
                    color: performanceMode === mode ? '#22d3ee' : '#64748b',
                    cursor: 'pointer',
                  }}
                >
                  {mode === 'PERFORMANCE' ? 'PERF' : mode}
                </button>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-x-2 gap-y-1">
              <span className="label" style={{ fontSize: 6 }}>MODE</span>
              <span className="num text-[8px] text-cyan-300 text-right">{perfStats.performanceMode}</span>
              <span className="label" style={{ fontSize: 6 }}>FPS</span>
              <span className="num text-[8px] text-cyan-300 text-right">{perfStats.fps.toFixed(0)}</span>
              <span className="label" style={{ fontSize: 6 }}>P95</span>
              <span className="num text-[8px] text-slate-300 text-right">{perfStats.p95FrameMs.toFixed(1)}ms</span>
              <span className="label" style={{ fontSize: 6 }}>Render</span>
              <span className="num text-[8px] text-slate-300 text-right">{perfStats.avgRenderMs.toFixed(1)}ms</span>
              <span className="label" style={{ fontSize: 6 }}>Opp</span>
              <span className="num text-[8px] text-orange-300 text-right">{perfStats.opponentsRendered}</span>
              <span className="label" style={{ fontSize: 6 }}>WS</span>
              <span className="num text-[8px] text-slate-300 text-right">{perfStats.wsHz.toFixed(0)}hz</span>
              <span className="label" style={{ fontSize: 6 }}>PLY</span>
              <span className="num text-[8px] text-slate-300 text-right">{perfStats.telemetryHz.toFixed(0)}hz</span>
              <span className="label" style={{ fontSize: 6 }}>OPP</span>
              <span className="num text-[8px] text-slate-300 text-right">{perfStats.opponentsHz.toFixed(0)}hz</span>
              <span className="label" style={{ fontSize: 6 }}>Store P/O</span>
              <span className="num text-[8px] text-slate-300 text-right">
                {perfStats.telemetryStoreHz.toFixed(0)}/{perfStats.opponentsStoreHz.toFixed(0)}hz
              </span>
              <span className="label" style={{ fontSize: 6 }}>Trace</span>
              <span className="num text-[8px] text-slate-300 text-right">
                {perfStats.traceFps.toFixed(0)}hz {perfStats.avgTraceRenderMs.toFixed(1)}ms
              </span>
              <span className="label" style={{ fontSize: 6 }}>Dropped P/O</span>
              <span className="num text-[8px] text-slate-300 text-right">
                {perfStats.telemetryDroppedHz.toFixed(0)}/{perfStats.opponentsDroppedHz.toFixed(0)}hz
              </span>
              <span className="label" style={{ fontSize: 6 }}>Line</span>
              <span className="num text-[8px] text-slate-300 text-right">{perfStats.racingLineOverlayMs.toFixed(2)}ms</span>
              <span className="label" style={{ fontSize: 6 }}>HTTP</span>
              <span className="num text-[8px] text-slate-300 text-right">
                {perfStats.httpHz.toFixed(1)}hz {perfStats.httpAvgMs.toFixed(0)}ms
              </span>
              <span className="label" style={{ fontSize: 6 }}>Payload T/R</span>
              <span className="num text-[8px] text-slate-300 text-right">
                {perfStats.telemetryPayloadKb.toFixed(1)}/{perfStats.racingLinePayloadKb.toFixed(1)}kb
              </span>
              <span className="label" style={{ fontSize: 6 }}>Lap Samples</span>
              <span className="num text-[8px] text-slate-300 text-right">
                {perfStats.currentLapSamples}/{perfStats.previousLapSamples}
              </span>
              <span className="label" style={{ fontSize: 6 }}>Buffers</span>
              <span className="num text-[8px] text-slate-300 text-right">
                H{perfStats.liveTrajectoryPoints} L{perfStats.completedLapsHistory}
              </span>
              <span className="label" style={{ fontSize: 6 }}>Graph/cache</span>
              <span className="num text-[8px] text-slate-300 text-right">
                {perfStats.graphPoints}/{perfStats.traceCacheEntries}
              </span>
              <span className="label" style={{ fontSize: 6 }}>Line pts</span>
              <span className="num text-[8px] text-slate-300 text-right">{perfStats.racingLineVisualPoints}</span>
              <span className="label" style={{ fontSize: 6 }}>Opp samples</span>
              <span className="num text-[8px] text-slate-300 text-right">{perfStats.opponentSamples}</span>
              <span className="label" style={{ fontSize: 6 }}>Heap</span>
              <span className="num text-[8px] text-slate-300 text-right">
                {perfStats.memoryEstimateMb ? `${perfStats.memoryEstimateMb.toFixed(0)}mb` : '--'}
              </span>
              <div className="col-span-2 h-[1px] bg-slate-800 my-0.5" />
              <span className="label text-orange-200" style={{ fontSize: 6 }}>DASH RENDERS</span>
              <span className="num text-[8px] text-orange-200 text-right">{perfStats.dashboardRps.toFixed(1)}/s</span>
              <span className="label text-orange-200" style={{ fontSize: 6 }}>MAP RENDERS</span>
              <span className="num text-[8px] text-orange-200 text-right">{perfStats.trackRendererRps.toFixed(1)}/s</span>
              <span className="label text-orange-200" style={{ fontSize: 6 }}>TRACE RENDERS</span>
              <span className="num text-[8px] text-orange-200 text-right">{perfStats.tracesRps.toFixed(1)}/s</span>
              <span className="label text-orange-200" style={{ fontSize: 6 }}>GG RENDERS</span>
              <span className="num text-[8px] text-orange-200 text-right">{perfStats.ggDiagramRps.toFixed(1)}/s</span>
              <span className="label text-orange-200" style={{ fontSize: 6 }}>LINE RENDERS</span>
              <span className="num text-[8px] text-orange-200 text-right">{perfStats.linePanelRps.toFixed(1)}/s</span>
              <span className="label text-orange-200" style={{ fontSize: 6 }}>COMP RENDERS</span>
              <span className="num text-[8px] text-orange-200 text-right">{perfStats.comparisonRps.toFixed(1)}/s</span>
              <span className="label text-orange-200" style={{ fontSize: 6 }}>PANEL RENDERS</span>
              <span className="num text-[8px] text-orange-200 text-right">{perfStats.hiddenPanelRps.toFixed(1)}/s</span>
            </div>
          </div>
        )}
      </div>

      {!replayActive && showOpponents && visibleOpponents.length > 0 && (
        <div
          className="absolute left-3 bottom-3 panel px-2 py-2 overflow-hidden"
          style={{
            width: compactOpponentsPanel ? '44px' : 'min(218px, calc(100% - 24px))',
            pointerEvents: 'auto',
          }}
          onMouseDown={(event) => event.stopPropagation()}
          onClick={(event) => event.stopPropagation()}
        >
          <div className="flex items-center justify-between gap-2">
            <button
              type="button"
              onClick={() => setOpponentsPanelOpen((open) => !open)}
              className="num text-[8px] text-orange-300 font-bold uppercase hover:text-orange-200"
              style={{ background: 'transparent', border: 0, padding: 0, cursor: 'pointer' }}
            >
              {compactOpponentsPanel ? 'OP' : `Opponents ${opponentsPanelOpen ? '-' : '+'}`}
            </button>
            <span className="num text-[8px] text-slate-400">{totalOpponents}</span>
          </div>
          {opponentsPanelOpen && !compactOpponentsPanel && (
            <div className="flex flex-col gap-1 mt-1" style={{ maxHeight: 168, overflow: 'hidden' }}>
              {sortedOpponents.slice(0, 8).map((opponent) => {
              const world = opponent.worldPosition || {};
              const splinePercent = isFiniteNumber(opponent.splinePosition) ? opponent.splinePosition * 100 : null;
              const stale = isStaleOpponent(opponent, panelOpponentsMeta.staleAfterSeconds);
              return (
                <div
                  key={opponent.carId}
                  className="grid gap-1 items-center"
                  style={{
                    gridTemplateColumns: '24px minmax(0, 1fr) 48px',
                    opacity: stale ? 0.45 : 1,
                  }}
                >
                  <span className="num text-[8px] text-orange-200">#{opponent.carId}</span>
                  <span className="text-[9px] text-slate-200 truncate">
                    {opponentDisplayName(opponent)}
                  </span>
                  <span className="num text-[8px] text-slate-400 text-right">
                    {formatOpponentNumber(opponent.speedKmh)} km/h
                  </span>
                  <span className="num text-[7px] text-slate-600 col-start-2 col-span-2 truncate">
                    p {formatOpponentNumber(splinePercent, 1)}% / x {formatOpponentNumber(world.x, 0)} z {formatOpponentNumber(world.z, 0)}
                  </span>
                </div>
              );
              })}
            </div>
          )}
          {panelOpponentsMeta.track && opponentsPanelOpen && !compactOpponentsPanel && (
            <div className="num text-[7px] text-slate-600 mt-1 truncate">{panelOpponentsMeta.track}</div>
          )}
        </div>
      )}

      {tooltipOpponent && (
        <div
          className="absolute panel px-2 py-2 pointer-events-none"
          style={{
            position: 'fixed',
            left: activeOpponentTooltip.x,
            top: activeOpponentTooltip.y,
            width: 224,
            background: 'rgba(8, 12, 22, 0.94)',
            borderColor: 'rgba(251,146,60,0.32)',
            boxShadow: '0 10px 28px rgba(0,0,0,0.35)',
            zIndex: 80,
          }}
        >
          <div className="flex items-center justify-between gap-2 mb-1">
            <span className="num text-[9px] text-orange-200 font-bold">#{tooltipOpponent.carId}</span>
            <span className="num text-[8px] text-slate-500 truncate">{tooltipOpponent.status || 'on_track'}</span>
          </div>
          <div className="text-[10px] text-slate-100 truncate">{opponentDisplayName(tooltipOpponent)}</div>
          {tooltipOpponent.carModel && (
            <div className="text-[8px] text-slate-500 truncate mt-0.5">{tooltipOpponent.carModel}</div>
          )}
          <div className="grid grid-cols-2 gap-x-3 gap-y-1 mt-2">
            <span className="label" style={{ fontSize: 6 }}>Speed</span>
            <span className="num text-[8px] text-slate-300 text-right">{formatOpponentNumber(tooltipOpponent.speedKmh)} km/h</span>
            <span className="label" style={{ fontSize: 6 }}>Spline</span>
            <span className="num text-[8px] text-slate-300 text-right">{formatOpponentNumber(opponentSplinePercent(tooltipOpponent), 1)}%</span>
            <span className="label" style={{ fontSize: 6 }}>World X</span>
            <span className="num text-[8px] text-slate-300 text-right">{formatOpponentNumber(tooltipWorld.x, 2)}</span>
            <span className="label" style={{ fontSize: 6 }}>World Y</span>
            <span className="num text-[8px] text-slate-300 text-right">{formatOpponentNumber(tooltipWorld.y, 2)}</span>
            <span className="label" style={{ fontSize: 6 }}>World Z</span>
            <span className="num text-[8px] text-slate-300 text-right">{formatOpponentNumber(tooltipWorld.z, 2)}</span>
          </div>
        </div>
      )}
    </div>
  );
});

export default TrackRenderer;
