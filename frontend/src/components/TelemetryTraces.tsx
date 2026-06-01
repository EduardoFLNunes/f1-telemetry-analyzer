import React, { useCallback, useEffect, useRef, useState } from 'react';
import { PerformanceMode, useTelemetryStore, TelemetryFrame, LapDebugState } from '../store/useTelemetryStore';
import { useRenderCounter } from '../hooks/useRenderCounter';
import { formatDelta, formatLapTime } from '../utils/lapFormat';

type TraceId = 'speed' | 'throttle' | 'brake';

interface TraceConfig {
  id: TraceId;
  label: string;
  unit: string;
  min: number;
  max: number;
  value: (frame: TelemetryFrame) => number | null;
  format: (value: number | null) => string;
}

const CURRENT_COLOR = '#22d3ee';
const PREVIOUS_COLOR = '#f59e0b';
const GRID_COLOR = 'rgba(255,255,255,0.055)';
const TEXT_MUTED = 'rgba(148,163,184,0.62)';
const TEXT_DIM = 'rgba(71,85,105,0.9)';
const TRACE_RENDER_MS: Record<PerformanceMode, number> = {
  QUALITY: 1000 / 20,
  BALANCED: 1000 / 10,
  PERFORMANCE: 1000 / 5,
};
const PAD_LEFT = 54;
const PAD_RIGHT = 18;
const PAD_TOP = 28;
const PAD_BOTTOM = 10;
const ROW_GAP = 8;
const MAX_POINTS: Record<PerformanceMode, number> = {
  QUALITY: 1000,
  BALANCED: 650,
  PERFORMANCE: 320,
};
const MAX_SERIES_CACHE_ENTRIES = 96;

function tracePerf() {
  const target = window as any;
  if (!target.__telemetryPerf) target.__telemetryPerf = {};
  target.__telemetryPerf.traceFrames = target.__telemetryPerf.traceFrames || 0;
  target.__telemetryPerf.traceRenderMs = target.__telemetryPerf.traceRenderMs || 0;
  return target.__telemetryPerf;
}

function recordTraceRender(durationMs: number) {
  const metrics = tracePerf();
  metrics.traceFrames += 1;
  metrics.traceRenderMs += durationMs;
}

function finite(value: unknown): number | null {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function speedKmh(frame: TelemetryFrame): number | null {
  const direct = finite(frame.speedKmh);
  if (direct !== null) return direct;
  const speed = finite(frame.speed);
  return speed !== null ? speed * 3.6 : null;
}

const TRACES: TraceConfig[] = [
  {
    id: 'speed',
    label: 'Speed',
    unit: 'km/h',
    min: 0,
    max: 340,
    value: speedKmh,
    format: (value) => (value === null ? '--' : `${value.toFixed(0)} km/h`),
  },
  {
    id: 'throttle',
    label: 'Throttle',
    unit: '%',
    min: 0,
    max: 1,
    value: (frame) => finite(frame.throttle),
    format: (value) => (value === null ? '--' : `${(value * 100).toFixed(0)}%`),
  },
  {
    id: 'brake',
    label: 'Brake',
    unit: '%',
    min: 0,
    max: 1,
    value: (frame) => finite(frame.brake),
    format: (value) => (value === null ? '--' : `${(value * 100).toFixed(0)}%`),
  },
];

function sampleProgress(frame: TelemetryFrame, minS: number, rangeS: number): number | null {
  const progress = finite(frame.lapProgress);
  if (progress !== null) return clamp(progress, 0, 1);

  const distance = finite(frame.s ?? frame.distanceAlongTrack);
  if (distance === null || rangeS <= 0) return null;
  return clamp((distance - minS) / rangeS, 0, 1);
}

function sampleVersion(sample: TelemetryFrame | undefined): string {
  if (!sample) return 'none';
  return [
    sample.timestamp,
    sample.lapSampleTime,
    sample.lapProgress,
    sample.s,
    sample.speed,
  ].join(':');
}

function seriesPoints(samples: TelemetryFrame[], trace: TraceConfig, maxPoints: number) {
  if (samples.length < 2) return [];
  const distances = samples
    .map((sample) => finite(sample.s ?? sample.distanceAlongTrack))
    .filter((value): value is number => value !== null);
  const minS = distances.length ? Math.min(...distances) : 0;
  const maxS = distances.length ? Math.max(...distances) : 1;
  const rangeS = Math.max(1, maxS - minS);

  const points = samples
    .map((sample) => {
      const x = sampleProgress(sample, minS, rangeS);
      const value = trace.value(sample);
      if (x === null || value === null) return null;
      return { x, value: clamp(value, trace.min, trace.max), sample };
    })
    .filter((point): point is { x: number; value: number; sample: TelemetryFrame } => Boolean(point))
    .sort((a, b) => a.x - b.x);

  if (points.length <= maxPoints) return points;
  const step = Math.ceil(points.length / maxPoints);
  return points.filter((_, index) => index % step === 0 || index === points.length - 1);
}

type SeriesPoints = ReturnType<typeof seriesPoints>;
const SERIES_CACHE = new Map<string, SeriesPoints>();

function cachedSeriesPoints(samples: TelemetryFrame[], trace: TraceConfig, performanceMode: PerformanceMode) {
  const maxPoints = MAX_POINTS[performanceMode] ?? MAX_POINTS.BALANCED;
  const key = [
    trace.id,
    performanceMode,
    maxPoints,
    samples.length,
    sampleVersion(samples[0]),
    sampleVersion(samples[samples.length - 1]),
  ].join('|');
  const cached = SERIES_CACHE.get(key);
  if (cached) return cached;
  const points = seriesPoints(samples, trace, maxPoints);
  SERIES_CACHE.set(key, points);
  if (SERIES_CACHE.size > MAX_SERIES_CACHE_ENTRIES) {
    const firstKey = SERIES_CACHE.keys().next().value;
    if (firstKey) SERIES_CACHE.delete(firstKey);
  }
  return points;
}

function nearestSampleAtProgress(samples: TelemetryFrame[], progress: number, performanceMode: PerformanceMode): TelemetryFrame | null {
  const points = cachedSeriesPoints(samples, TRACES[0], performanceMode);
  if (!points.length) return null;
  return points.reduce((best, point) => (
    Math.abs(point.x - progress) < Math.abs(best.x - progress) ? point : best
  )).sample;
}

function drawTrace(
  ctx: CanvasRenderingContext2D,
  points: ReturnType<typeof seriesPoints>,
  trace: TraceConfig,
  x0: number,
  y0: number,
  width: number,
  height: number,
  color: string,
  lineWidth: number,
  alpha = 1,
) {
  if (points.length < 2) return;
  const valueToY = (value: number) => y0 + height - ((value - trace.min) / (trace.max - trace.min)) * height;

  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';
  ctx.beginPath();
  points.forEach((point, index) => {
    const x = x0 + point.x * width;
    const y = valueToY(point.value);
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
  ctx.restore();
}

function drawRow(
  ctx: CanvasRenderingContext2D,
  trace: TraceConfig,
  current: TelemetryFrame[],
  previous: TelemetryFrame[],
  x0: number,
  y0: number,
  width: number,
  height: number,
  cursorProgress: number | null,
  performanceMode: PerformanceMode,
) {
  ctx.fillStyle = 'rgba(255,255,255,0.018)';
  ctx.fillRect(x0, y0, width, height);

  ctx.strokeStyle = GRID_COLOR;
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i += 1) {
    const x = x0 + (i / 4) * width;
    ctx.beginPath();
    ctx.moveTo(x, y0);
    ctx.lineTo(x, y0 + height);
    ctx.stroke();
  }

  ctx.fillStyle = TEXT_MUTED;
  ctx.font = '700 8px "JetBrains Mono"';
  ctx.textAlign = 'left';
  ctx.fillText(trace.label.toUpperCase(), 10, y0 + 10);
  ctx.fillStyle = TEXT_DIM;
  ctx.font = '600 7px "JetBrains Mono"';
  ctx.fillText(trace.unit, 10, y0 + 21);

  const currentPoints = cachedSeriesPoints(current, trace, performanceMode);
  const previousPoints = cachedSeriesPoints(previous, trace, performanceMode);
  drawTrace(ctx, previousPoints, trace, x0, y0, width, height, PREVIOUS_COLOR, 1.1, 0.62);
  drawTrace(ctx, currentPoints, trace, x0, y0, width, height, CURRENT_COLOR, 1.7, 1);

  const currentValue = current.length ? trace.value(current[current.length - 1]) : null;
  ctx.fillStyle = CURRENT_COLOR;
  ctx.font = '700 8px "JetBrains Mono"';
  ctx.textAlign = 'right';
  ctx.fillText(trace.format(currentValue), x0 + width - 2, y0 + 10);

  if (cursorProgress !== null) {
    const x = x0 + cursorProgress * width;
    ctx.strokeStyle = 'rgba(255,255,255,0.22)';
    ctx.setLineDash([3, 4]);
    ctx.beginPath();
    ctx.moveTo(x, y0);
    ctx.lineTo(x, y0 + height);
    ctx.stroke();
    ctx.setLineDash([]);
  }
}

export const TelemetryTraces: React.FC = () => {
  useRenderCounter('TelemetryTraces');
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>();
  const lastRenderRef = useRef(0);
  const cursorProgressRef = useRef<number | null>(null);
  const performanceMode = useTelemetryStore((state) => state.performanceMode);
  const performanceModeRef = useRef<PerformanceMode>('BALANCED');
  const [showLapDebug, setShowLapDebug] = useState(false);
  const [lapDebug, setLapDebug] = useState<LapDebugState | null>(null);

  useEffect(() => {
    performanceModeRef.current = performanceMode;
  }, [performanceMode]);

  useEffect(() => {
    if (!showLapDebug) {
      setLapDebug(null);
      return undefined;
    }
    const interval = setInterval(() => {
      const { lapDebug: debug } = useTelemetryStore.getState();
      setLapDebug(debug);
    }, 500);
    return () => clearInterval(interval);
  }, [showLapDebug]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return undefined;
    const ctx = canvas.getContext('2d');
    if (!ctx) return undefined;

    const loop = (frameTime = performance.now()) => {
      const mode = performanceModeRef.current;
      const renderMs = TRACE_RENDER_MS[mode] ?? TRACE_RENDER_MS.BALANCED;
      if (frameTime - lastRenderRef.current < renderMs) {
        animRef.current = requestAnimationFrame(loop);
        return;
      }
      lastRenderRef.current = frameTime;
      const renderStart = performance.now();

      const {
        currentLapSamples,
        previousLapSamples,
        lapMetrics,
      } = useTelemetryStore.getState();

      const rect = container.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      const width = rect.width;
      const height = rect.height;
      if (canvas.width !== Math.round(width * dpr) || canvas.height !== Math.round(height * dpr)) {
        canvas.width = Math.round(width * dpr);
        canvas.height = Math.round(height * dpr);
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = '#08080f';
      ctx.fillRect(0, 0, width, height);

      ctx.fillStyle = 'rgba(241,245,249,0.86)';
      ctx.font = '800 9px "JetBrains Mono"';
      ctx.textAlign = 'left';
      ctx.fillText('LAP COMPARISON', 10, 13);

      ctx.fillStyle = CURRENT_COLOR;
      ctx.fillRect(128, 8, 18, 2);
      ctx.fillStyle = TEXT_MUTED;
      ctx.font = '700 7px "JetBrains Mono"';
      ctx.fillText(`CURRENT L${lapMetrics.currentLapNumber ?? '--'}`, 152, 12);

      ctx.fillStyle = PREVIOUS_COLOR;
      ctx.fillRect(244, 8, 18, 2);
      ctx.fillStyle = TEXT_MUTED;
      ctx.fillText(
        lapMetrics.hasPreviousLap ? `PREVIOUS L${lapMetrics.previousLapNumber ?? '--'}` : 'NO PREVIOUS LAP',
        268,
        12,
      );

      ctx.textAlign = 'right';
      ctx.fillStyle = 'rgba(241,245,249,0.76)';
      ctx.fillText(`LAP ${formatLapTime(lapMetrics.currentLapTime)}`, width - 148, 12);
      ctx.fillStyle = lapMetrics.delta !== null && lapMetrics.delta <= 0 ? '#34d399' : (lapMetrics.delta === null ? TEXT_DIM : '#fb7185');
      ctx.fillText(`DELTA ${formatDelta(lapMetrics.delta)}`, width - 18, 12);

      if (currentLapSamples.length < 2) {
        ctx.fillStyle = 'rgba(255,255,255,0.08)';
        ctx.font = '700 9px "JetBrains Mono"';
        ctx.textAlign = 'center';
        ctx.fillText('WAITING FOR CURRENT LAP TELEMETRY', width / 2, height / 2);
        recordTraceRender(performance.now() - renderStart);
        animRef.current = requestAnimationFrame(loop);
        return;
      }

      const graphX = PAD_LEFT;
      const graphW = Math.max(1, width - PAD_LEFT - PAD_RIGHT);
      const availableH = Math.max(1, height - PAD_TOP - PAD_BOTTOM - ROW_GAP * (TRACES.length - 1));
      const rowH = availableH / TRACES.length;
      TRACES.forEach((trace, index) => {
        drawRow(
          ctx,
          trace,
          currentLapSamples,
          previousLapSamples,
          graphX,
          PAD_TOP + index * (rowH + ROW_GAP),
          graphW,
          rowH,
          cursorProgressRef.current,
          mode,
        );
      });
      const perf = tracePerf();
      perf.graphPoints = currentLapSamples.length + previousLapSamples.length;
      perf.traceCacheEntries = SERIES_CACHE.size;

      ctx.fillStyle = TEXT_DIM;
      ctx.font = '600 7px "JetBrains Mono"';
      ctx.textAlign = 'left';
      ctx.fillText('0%', graphX, height - 2);
      ctx.textAlign = 'center';
      ctx.fillText('50%', graphX + graphW / 2, height - 2);
      ctx.textAlign = 'right';
      ctx.fillText('100%', graphX + graphW, height - 2);

      recordTraceRender(performance.now() - renderStart);
      animRef.current = requestAnimationFrame(loop);
    };

    animRef.current = requestAnimationFrame(loop);
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, []);

  const handleMouseMove = useCallback((event: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const graphW = Math.max(1, rect.width - PAD_LEFT - PAD_RIGHT);
    const x = event.clientX - rect.left;
    if (x < PAD_LEFT || x > PAD_LEFT + graphW) {
      cursorProgressRef.current = null;
      useTelemetryStore.getState().setGlobalCursor(null);
      return;
    }

    const progress = clamp((x - PAD_LEFT) / graphW, 0, 1);
    cursorProgressRef.current = progress;
    const nearest = nearestSampleAtProgress(
      useTelemetryStore.getState().currentLapSamples,
      progress,
      performanceModeRef.current,
    );
    useTelemetryStore.getState().setGlobalCursor(nearest?.s ?? null);
  }, []);

  const handleMouseLeave = useCallback(() => {
    cursorProgressRef.current = null;
    useTelemetryStore.getState().setGlobalCursor(null);
  }, []);

  return (
    <div ref={containerRef} className="relative w-full h-full" style={{ background: '#08080f' }}>
      <canvas
        ref={canvasRef}
        style={{ width: '100%', height: '100%', display: 'block', cursor: 'crosshair' }}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      />
      <button
        type="button"
        onClick={() => setShowLapDebug((visible) => !visible)}
        className="absolute right-2 top-1 num text-[7px] uppercase text-slate-600 hover:text-cyan-300"
        style={{ zIndex: 5, background: 'transparent', border: 0, padding: '2px 4px', cursor: 'pointer' }}
      >
        LAP DBG
      </button>
      {showLapDebug && lapDebug && (
        <div
          className="absolute right-2 top-6 panel px-2 py-1.5"
          style={{ zIndex: 6, width: 210, background: 'rgba(8,12,22,0.94)', pointerEvents: 'none' }}
        >
          <div className="grid grid-cols-2 gap-x-2 gap-y-0.5">
            <span className="label" style={{ fontSize: 6 }}>Current</span>
            <span className="num text-[8px] text-slate-300 text-right">{lapDebug.currentLapNumber ?? '--'}</span>
            <span className="label" style={{ fontSize: 6 }}>Reference</span>
            <span className="num text-[8px] text-slate-300 text-right">{lapDebug.referenceLapNumber ?? '--'}</span>
            <span className="label" style={{ fontSize: 6 }}>Current Samples</span>
            <span className="num text-[8px] text-slate-300 text-right">{lapDebug.currentLapSamplesLength}</span>
            <span className="label" style={{ fontSize: 6 }}>Previous Samples</span>
            <span className="num text-[8px] text-slate-300 text-right">{lapDebug.previousLapSamplesLength}</span>
            <span className="label" style={{ fontSize: 6 }}>Partial</span>
            <span className="num text-[8px] text-slate-300 text-right">{lapDebug.currentLapIsPartial ? 'true' : 'false'}</span>
            <span className="label" style={{ fontSize: 6 }}>Last Complete</span>
            <span className="num text-[8px] text-slate-300 text-right">{lapDebug.lastCompletedLapNumber ?? '--'}</span>
            <span className="label" style={{ fontSize: 6 }}>Transition</span>
            <span className="num text-[8px] text-slate-300 text-right truncate">{lapDebug.lastLapTransitionReason ?? '--'}</span>
            <span className="label" style={{ fontSize: 6 }}>Rejected</span>
            <span className="num text-[8px] text-slate-300 text-right truncate">{lapDebug.lastRejectedLapReason ?? '--'}</span>
            <span className="label" style={{ fontSize: 6 }}>Prev Valid</span>
            <span className="num text-[8px] text-slate-300 text-right">{lapDebug.previousLapValid ? 'true' : 'false'}</span>
            <span className="label" style={{ fontSize: 6 }}>Progress</span>
            <span className="num text-[8px] text-slate-300 text-right">
              {lapDebug.finalizedProgressStart?.toFixed(3) ?? '--'} / {lapDebug.finalizedProgressEnd?.toFixed(3) ?? '--'}
            </span>
            <span className="label" style={{ fontSize: 6 }}>Duration</span>
            <span className="num text-[8px] text-slate-300 text-right">
              {lapDebug.finalizedLapDuration !== null ? `${lapDebug.finalizedLapDuration.toFixed(2)}s` : '--'}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};
