import React, { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import { TelemetryFrame, useTelemetryStore } from '../store/useTelemetryStore';

type TraceRole = 'reference' | 'analyzed' | 'current';

type TraceSample = {
  progress: number;
  elapsedS: number | null;
  speedKmh: number | null;
  throttle: number | null;
  brake: number | null;
};

type TraceLap = {
  role: TraceRole;
  lapId: string;
  label: string;
  samples: TraceSample[];
};

type TraceVisibility = Record<TraceRole, boolean>;

type RecordedLapItem = {
  lapId: string;
  source: string;
  driverId: string;
  lapNumber: number;
  track?: string | null;
  lapTime?: number | null;
  sampleCount: number;
  sessionId?: string | null;
};

const traceColors: Record<TraceRole, string> = {
  reference: '#a78bfa',
  analyzed: '#facc15',
  current: '#38bdf8',
};

const traceLabels: Record<TraceRole, string> = {
  reference: 'Referencia',
  analyzed: 'Analisada',
  current: 'Atual',
};

const traceRows = [
  { key: 'speedKmh', label: 'Speed', unit: 'km/h' },
  { key: 'throttle', label: 'Throttle', unit: '%' },
  { key: 'brake', label: 'Brake', unit: '%' },
] as const;

const NO_REFERENCE = '__none__';

const compactValue = (value: unknown) => {
  if (value === null || value === undefined || value === '') return '--';
  const text = String(value).replace(/^rec__/, '');
  return text.length > 30 ? `...${text.slice(-27)}` : text;
};

const lapOptionLabel = (lap: RecordedLapItem) => {
  const source = lap.source === 'telemetry_db' ? 'DB' : lap.source === 'buffer' ? 'LIVE' : 'REC';
  const time = Number.isFinite(Number(lap.lapTime)) && Number(lap.lapTime) > 0
    ? ` ${Number(lap.lapTime).toFixed(1)}s`
    : '';
  const track = lap.track ? ` ${lap.track}` : '';
  return `${source} L${lap.lapNumber}${time}${track} (${lap.sampleCount})`;
};

const traceLabelForLap = (lap: RecordedLapItem | null, fallbackLapId: string, fallbackLapNumber: number | null) => {
  if (lap) return `L${lap.lapNumber}`;
  return fallbackLapNumber ? `L${fallbackLapNumber}` : compactValue(fallbackLapId);
};

const numberOrNull = (value: unknown): number | null => {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};

const clamp01 = (value: number) => Math.max(0, Math.min(1, value));

const normalizePedal = (value: unknown): number | null => {
  const number = numberOrNull(value);
  if (number === null) return null;
  return clamp01(number > 1 ? number / 100 : number);
};

const speedKmhFromFrame = (sample: any): number | null => {
  const direct = numberOrNull(sample?.speedKmh ?? sample?.speed_kmh);
  if (direct !== null) return direct;
  const speed = numberOrNull(sample?.speed);
  return speed !== null ? speed * 3.6 : null;
};

const progressFromSample = (sample: any, index: number, total: number): number => {
  const direct = numberOrNull(
    sample?.progress
    ?? sample?.lapProgress
    ?? sample?.p
    ?? sample?.spline_t
    ?? sample?.splinePosition
    ?? sample?.normalizedSplinePosition,
  );
  if (direct !== null && direct >= 0 && direct <= 1) return clamp01(direct);
  return total > 1 ? index / (total - 1) : 0;
};

const normalizeTraceSamples = (samples: any[] = []): TraceSample[] => (
  samples
    .map((sample, index) => ({
      progress: progressFromSample(sample, index, samples.length),
      elapsedS: numberOrNull(sample?.elapsedS ?? sample?.elapsed_s ?? sample?.lap_time ?? sample?.lapTime),
      speedKmh: speedKmhFromFrame(sample),
      throttle: normalizePedal(sample?.throttle),
      brake: normalizePedal(sample?.brake),
    }))
    .filter(sample => sample.speedKmh !== null || sample.throttle !== null || sample.brake !== null)
    .sort((a, b) => a.progress - b.progress)
);

const buildTraceLap = (role: TraceRole, lapId: string, label: string, samples: any[]): TraceLap => ({
  role,
  lapId,
  label,
  samples: normalizeTraceSamples(samples),
});

const downsampleTrace = (samples: TraceSample[], maxPoints = 760): TraceSample[] => {
  if (samples.length <= maxPoints) return samples;
  const step = Math.ceil(samples.length / maxPoints);
  return samples.filter((_, index) => index % step === 0 || index === samples.length - 1);
};

const tracePath = (
  samples: TraceSample[],
  key: keyof Pick<TraceSample, 'speedKmh' | 'throttle' | 'brake'>,
  max: number,
  x: number,
  y: number,
  width: number,
  height: number,
) => {
  const points = downsampleTrace(samples)
    .map(sample => {
      const value = numberOrNull(sample[key]);
      if (value === null) return null;
      const px = x + clamp01(sample.progress) * width;
      const py = y + height - clamp01(value / max) * height;
      return `${px.toFixed(1)},${py.toFixed(1)}`;
    })
    .filter((point): point is string => Boolean(point));
  if (points.length < 2) return '';
  return points.map((point, index) => `${index === 0 ? 'M' : 'L'}${point}`).join(' ');
};

const TraceToggle = ({
  role,
  visible,
  onChange,
}: {
  role: TraceRole;
  visible: boolean;
  onChange: () => void;
}) => (
  <label className="num flex items-center gap-1 text-[7px] uppercase cursor-pointer" style={{ color: visible ? '#cbd5e1' : '#64748b' }}>
    <input
      type="checkbox"
      checked={visible}
      onChange={onChange}
      style={{ width: 10, height: 10, accentColor: traceColors[role] }}
    />
    <span style={{ width: 13, height: 2, background: traceColors[role], opacity: visible ? 1 : 0.35 }} />
    {traceLabels[role]}
  </label>
);

export const AssistedLapTraces: React.FC<{ active?: boolean }> = ({ active = true }) => {
  const context = useTelemetryStore(state => state.assistedTraceContext);
  const [recordedLaps, setRecordedLaps] = useState<RecordedLapItem[]>([]);
  const [selectedAnalyzedLapId, setSelectedAnalyzedLapId] = useState('');
  const [selectedReferenceLapId, setSelectedReferenceLapId] = useState(NO_REFERENCE);
  const [traceLaps, setTraceLaps] = useState<{ analyzed: TraceLap | null; reference: TraceLap | null }>({
    analyzed: null,
    reference: null,
  });
  const [currentTraceLap, setCurrentTraceLap] = useState<TraceLap | null>(null);
  const [visibility, setVisibility] = useState<TraceVisibility>({
    reference: true,
    analyzed: true,
    current: true,
  });
  const [loading, setLoading] = useState(false);
  const [listLoading, setListLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  const analyzedLapId = selectedAnalyzedLapId || context.analyzedLapId || '';
  const requestedReferenceLapId = selectedReferenceLapId === NO_REFERENCE
    ? ''
    : selectedReferenceLapId || context.referenceLapId || '';
  const referenceLapId = requestedReferenceLapId && requestedReferenceLapId !== analyzedLapId
    ? requestedReferenceLapId
    : '';
  const selectedAnalyzedLap = useMemo(
    () => recordedLaps.find(lap => lap.lapId === analyzedLapId) || null,
    [recordedLaps, analyzedLapId],
  );
  const selectedReferenceLap = useMemo(
    () => recordedLaps.find(lap => lap.lapId === referenceLapId) || null,
    [recordedLaps, referenceLapId],
  );

  const loadRecordedLaps = async () => {
    setListLoading(true);
    try {
      const payload = await api.listAssistedAnalysisLaps();
      const next = Array.isArray(payload?.laps) ? payload.laps : [];
      setRecordedLaps(next);
      setSelectedAnalyzedLapId(current => {
        if (current && next.some((lap: RecordedLapItem) => lap.lapId === current)) return current;
        if (context.analyzedLapId && next.some((lap: RecordedLapItem) => lap.lapId === context.analyzedLapId)) {
          return context.analyzedLapId;
        }
        return next.find((lap: RecordedLapItem) => lap.sampleCount >= 40)?.lapId || next[0]?.lapId || '';
      });
      setSelectedReferenceLapId(current => {
        if (current === NO_REFERENCE) return current;
        if (current && next.some((lap: RecordedLapItem) => lap.lapId === current)) return current;
        if (context.referenceLapId && next.some((lap: RecordedLapItem) => lap.lapId === context.referenceLapId)) {
          return context.referenceLapId;
        }
        return NO_REFERENCE;
      });
      setListError(null);
    } catch (exc: any) {
      setRecordedLaps([]);
      setListError(exc?.response?.data?.detail || 'Recorded laps unavailable');
    } finally {
      setListLoading(false);
    }
  };

  useEffect(() => {
    if (!active) return undefined;
    loadRecordedLaps();
    const interval = window.setInterval(loadRecordedLaps, 10_000);
    return () => window.clearInterval(interval);
  }, [active, context.analyzedLapId, context.referenceLapId]);

  useEffect(() => {
    if (!context.analyzedLapId) return;
    setSelectedAnalyzedLapId(context.analyzedLapId);
    setSelectedReferenceLapId(context.referenceLapId || NO_REFERENCE);
  }, [context.analyzedLapId, context.referenceLapId]);

  useEffect(() => {
    if (!active || !analyzedLapId) {
      setTraceLaps({ analyzed: null, reference: null });
      setError(null);
      return undefined;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    const loadTrace = async () => {
      try {
        const [analyzedPayload, referencePayload] = await Promise.all([
          api.getAssistedLapTelemetry(analyzedLapId, 8_000),
          referenceLapId ? api.getAssistedLapTelemetry(referenceLapId, 8_000) : Promise.resolve(null),
        ]);
        if (cancelled) return;
        setTraceLaps({
          analyzed: buildTraceLap(
            'analyzed',
            analyzedLapId,
            traceLabelForLap(selectedAnalyzedLap, analyzedLapId, context.analyzedLapNumber),
            analyzedPayload?.samples || [],
          ),
          reference: referencePayload
            ? buildTraceLap(
                'reference',
                referenceLapId as string,
                traceLabelForLap(selectedReferenceLap, referenceLapId, context.referenceLapNumber),
                referencePayload?.samples || [],
              )
            : null,
        });
      } catch (exc: any) {
        if (!cancelled) {
          setTraceLaps({ analyzed: null, reference: null });
          setError(exc?.response?.data?.detail || 'Lap telemetry unavailable');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    loadTrace();
    return () => {
      cancelled = true;
    };
  }, [
    active,
    analyzedLapId,
    referenceLapId,
    context.analyzedLapNumber,
    context.referenceLapNumber,
    selectedAnalyzedLap,
    selectedReferenceLap,
  ]);

  useEffect(() => {
    if (!active) return undefined;
    const updateCurrentTrace = () => {
      const { currentLapSamples, lapMetrics } = useTelemetryStore.getState();
      setCurrentTraceLap(buildTraceLap(
        'current',
        `current__${lapMetrics.currentLapNumber ?? 'live'}`,
        lapMetrics.currentLapNumber ? `L${lapMetrics.currentLapNumber}` : 'Live',
        currentLapSamples as TelemetryFrame[],
      ));
    };
    updateCurrentTrace();
    const interval = window.setInterval(updateCurrentTrace, 500);
    return () => window.clearInterval(interval);
  }, [active]);

  const laps = useMemo(() => [
    visibility.reference ? traceLaps.reference : null,
    visibility.analyzed ? traceLaps.analyzed : null,
    visibility.current ? currentTraceLap : null,
  ].filter((lap): lap is TraceLap => Boolean(lap && lap.samples.length > 1)), [
    visibility,
    traceLaps.reference,
    traceLaps.analyzed,
    currentTraceLap,
  ]);

  const speedScale = useMemo(() => {
    const speedMax = Math.max(120, ...laps.flatMap(lap => lap.samples.map(sample => sample.speedKmh ?? 0)));
    return Math.ceil(speedMax / 20) * 20;
  }, [laps]);

  const toggleTrace = (role: TraceRole) => {
    setVisibility(current => ({ ...current, [role]: !current[role] }));
  };

  const changeAnalyzedLap = (lapId: string) => {
    setSelectedAnalyzedLapId(lapId);
    setSelectedReferenceLapId(current => (current === lapId ? NO_REFERENCE : current));
  };

  const graphX = 58;
  const graphW = 552;
  const rowH = 33;
  const rowGap = 8;
  const top = 45;
  const height = 190;
  const emptyMessage = listLoading
    ? 'Loading recorded laps'
    : listError || (recordedLaps.length ? 'Select a recorded lap' : 'No recorded laps found');

  return (
    <div className="relative w-full h-full" style={{ background: '#08080f', padding: '6px 8px 5px' }}>
      <div className="absolute left-2 right-2 top-1 flex items-start justify-between gap-2" style={{ zIndex: 3 }}>
        <div className="flex items-center gap-2 min-w-0">
          <span className="num text-[8px] font-extrabold text-slate-200 uppercase tracking-widest shrink-0">Lap Traces</span>
          <select
            className="num"
            value={analyzedLapId}
            onChange={event => changeAnalyzedLap(event.target.value)}
            title="Volta gravada analisada"
            style={{
              height: 18,
              width: 164,
              minWidth: 0,
              borderRadius: 2,
              border: '1px solid rgba(250,204,21,0.2)',
              background: 'rgba(8,12,22,0.94)',
              color: '#facc15',
              padding: '0 6px',
              fontSize: 7,
              fontWeight: 800,
            }}
          >
            {recordedLaps.length === 0 && <option value="">No recorded laps</option>}
            {recordedLaps.map(lap => (
              <option key={`analyzed-${lap.lapId}`} value={lap.lapId}>{lapOptionLabel(lap)}</option>
            ))}
          </select>
          <select
            className="num"
            value={referenceLapId}
            onChange={event => setSelectedReferenceLapId(event.target.value || NO_REFERENCE)}
            title="Volta gravada de referencia"
            style={{
              height: 18,
              width: 164,
              minWidth: 0,
              borderRadius: 2,
              border: '1px solid rgba(167,139,250,0.2)',
              background: 'rgba(8,12,22,0.94)',
              color: '#a78bfa',
              padding: '0 6px',
              fontSize: 7,
              fontWeight: 800,
            }}
          >
            <option value="">No reference</option>
            {recordedLaps
              .filter(lap => lap.lapId !== analyzedLapId)
              .map(lap => (
                <option key={`reference-${lap.lapId}`} value={lap.lapId}>{lapOptionLabel(lap)}</option>
              ))}
          </select>
        </div>
        <div className="hidden sm:flex items-center gap-2 shrink-0">
          {(['reference', 'analyzed', 'current'] as TraceRole[]).map(role => (
            <TraceToggle key={role} role={role} visible={visibility[role]} onChange={() => toggleTrace(role)} />
          ))}
        </div>
      </div>
      <div className="absolute right-2 top-5 flex items-center gap-2" style={{ zIndex: 3 }}>
        <span className="num text-[7px] text-slate-500 uppercase">
          {loading || listLoading ? 'loading' : `${laps.length}/3 visible`}
        </span>
        {(selectedAnalyzedLap?.track || context.track) && (
          <span className="num text-[7px] text-slate-600 uppercase">{selectedAnalyzedLap?.track || context.track}</span>
        )}
      </div>
      {(error || listError) && (
        <div className="absolute left-2 top-5 num text-[7px] text-rose-300" style={{ zIndex: 4 }}>
          {error || listError}
        </div>
      )}
      <svg viewBox={`0 0 640 ${height}`} width="100%" height="100%" style={{ display: 'block' }}>
        <rect x="0" y="0" width="640" height={height} fill="#08080f" />
        {traceRows.map((row, index) => {
          const y = top + index * (rowH + rowGap);
          const max = row.key === 'speedKmh' ? speedScale : 1;
          return (
            <g key={row.key}>
              <text x="10" y={y + 12} fill="rgba(203,213,225,0.78)" fontSize="8" fontWeight="800">{row.label.toUpperCase()}</text>
              <text x="10" y={y + 24} fill="rgba(100,116,139,0.86)" fontSize="7" fontWeight="700">{row.unit}</text>
              <rect x={graphX} y={y} width={graphW} height={rowH} fill="rgba(255,255,255,0.018)" />
              {[0, 0.25, 0.5, 0.75, 1].map(tick => (
                <line
                  key={`${row.key}-${tick}`}
                  x1={graphX + graphW * tick}
                  x2={graphX + graphW * tick}
                  y1={y}
                  y2={y + rowH}
                  stroke="rgba(255,255,255,0.055)"
                  strokeWidth="1"
                />
              ))}
              {laps.map(lap => {
                const path = tracePath(lap.samples, row.key, max, graphX, y, graphW, rowH);
                return path ? (
                  <path
                    key={`${lap.role}-${row.key}`}
                    d={path}
                    fill="none"
                    stroke={traceColors[lap.role]}
                    strokeWidth={lap.role === 'current' ? 2.1 : 1.65}
                    strokeOpacity={lap.role === 'reference' ? 0.88 : 0.96}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                ) : null;
              })}
              <text x="626" y={y + 10} fill="rgba(100,116,139,0.85)" fontSize="7" fontWeight="700" textAnchor="end">
                {row.key === 'speedKmh' ? `${max.toFixed(0)}` : '100'}
              </text>
            </g>
          );
        })}
        <text x={graphX} y={height - 5} fill="rgba(100,116,139,0.85)" fontSize="7" fontWeight="700">0%</text>
        <text x={graphX + graphW / 2} y={height - 5} fill="rgba(100,116,139,0.85)" fontSize="7" fontWeight="700" textAnchor="middle">50%</text>
        <text x={graphX + graphW} y={height - 5} fill="rgba(100,116,139,0.85)" fontSize="7" fontWeight="700" textAnchor="end">100%</text>
        {(!analyzedLapId || laps.length === 0) && (
          <text x="320" y="104" fill="rgba(100,116,139,0.78)" fontSize="9" fontWeight="800" textAnchor="middle">
            {emptyMessage.toUpperCase()}
          </text>
        )}
      </svg>
      <div className="absolute left-2 right-2 bottom-1 grid grid-cols-3 gap-2">
        {(['reference', 'analyzed', 'current'] as TraceRole[]).map(role => {
          const lap = role === 'reference' ? traceLaps.reference : role === 'analyzed' ? traceLaps.analyzed : currentTraceLap;
          return (
            <div key={`assist-trace-meta-${role}`} className="num text-[7px] uppercase truncate" style={{ color: visibility[role] ? traceColors[role] : '#475569' }}>
              {traceLabels[role]} {lap?.label || '--'} {lap?.samples.length ? `(${lap.samples.length})` : ''}
            </div>
          );
        })}
      </div>
    </div>
  );
};
