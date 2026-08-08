import React, { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  Database,
  GitCompare,
  Radio,
  RefreshCw,
  Route,
  ShieldCheck,
} from 'lucide-react';
import { api } from '../api/client';
import { useTelemetryStore } from '../store/useTelemetryStore';

type QualityStatus =
  | 'OK'
  | 'WARNING'
  | 'ERROR'
  | 'UNKNOWN'
  | 'VALID'
  | 'PARTIAL'
  | 'INVALID'
  | 'READY'
  | 'INSUFFICIENT_DATA'
  | 'TRACK_READY'
  | 'TRACK_PARTIAL'
  | 'TRACK_MISSING'
  | 'receiving'
  | 'waiting'
  | 'stale'
  | 'error';

type DataQualityReport = {
  status: QualityStatus;
  generatedAt: string;
  player: {
    source: string;
    status: QualityStatus;
    frequencyStatus: QualityStatus;
    targetHz: number;
    estimatedHz: number | null;
    stableHz: number | null;
    sampleCount: number;
    droppedSamplesEstimate: number | null;
    secondsSinceLastSample: number | null;
    invalidSampleCount: number;
    hasPhysics: boolean;
    hasTyres: boolean;
    hasFuel: boolean;
    hasSuspension: boolean;
    hasPosition: boolean;
    hasSpline: boolean;
  };
  opponents: {
    source: string;
    status: QualityStatus;
    estimatedHz: number | null;
    packetsReceived: number;
    packetsAccepted: number;
    packetsDropped: number;
    packetsInvalid: number;
    packetsOutOfOrder: number;
    opponentsCount: number;
    playerFilteredCount: number;
  };
  laps: {
    sessionCount: number;
    completedLapCount: number;
    validLapCount: number;
    invalidLapCount: number;
    partialLapCount: number;
    issues: string[];
  };
  track: {
    status: QualityStatus;
    sampleCount: number;
    hasCenterline: boolean;
    hasBounds: boolean;
    hasSectors: boolean;
    issues: string[];
    paintAgreement?: {
      status: 'OK' | 'DIVERGENT' | 'INSUFFICIENT_PAINT' | 'UNAVAILABLE';
      measuredSides?: number;
      sides?: Record<string, { coveragePercent: number; ratioMedian: number | null }>;
    };
  };
  comparison: {
    status: QualityStatus;
    issues: string[];
  };
};

type Tone = 'ok' | 'warning' | 'error' | 'quiet';

const toneByStatus = (status?: QualityStatus | null): Tone => {
  const normalized = String(status || 'UNKNOWN').toUpperCase();
  if (['OK', 'VALID', 'READY', 'TRACK_READY', 'RECEIVING'].includes(normalized)) return 'ok';
  if (['ERROR', 'INVALID', 'TRACK_MISSING'].includes(normalized)) return 'error';
  if (['WARNING', 'PARTIAL', 'TRACK_PARTIAL', 'STALE'].includes(normalized)) return 'warning';
  return 'quiet';
};

const numberOr = (value: unknown, fallback = 0) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const hz = (value: number | null | undefined) => (
  value !== null && value !== undefined && Number.isFinite(Number(value))
    ? `${Number(value).toFixed(1)} Hz`
    : '--'
);

const age = (value: number | null | undefined) => (
  value !== null && value !== undefined && Number.isFinite(Number(value))
    ? `${Number(value).toFixed(1)}s`
    : '--'
);

const StatusChip = ({ status }: { status?: QualityStatus | null }) => (
  <span className="quality-chip" data-tone={toneByStatus(status)}>
    {String(status || 'UNKNOWN').replace(/_/g, ' ')}
  </span>
);

const BooleanMetric = ({ label, value }: { label: string; value: boolean }) => (
  <div className="quality-boolean" data-ok={value ? 'true' : 'false'}>
    <span>{label}</span>
    <strong>{value ? 'OK' : 'MISS'}</strong>
  </div>
);

const Metric = ({
  label,
  value,
  tone = 'quiet',
}: {
  label: string;
  value: React.ReactNode;
  tone?: Tone;
}) => (
  <div className="quality-metric" data-tone={tone}>
    <span>{label}</span>
    <strong>{value}</strong>
  </div>
);

export const DataQualityPanel = React.memo(function DataQualityPanel({
  active = true,
}: {
  active?: boolean;
}) {
  const performanceMode = useTelemetryStore((state) => active ? state.performanceMode : 'BALANCED');
  const selectedLap = useTelemetryStore((state) => active ? state.selectedLap : null);
  const selectedSessionId = useTelemetryStore((state) => active ? state.selectedSessionId : null);
  const [report, setReport] = useState<DataQualityReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    setRefreshing(true);
    try {
      setReport(await api.getDataQuality());
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Diagnostico indisponivel');
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (!active) return undefined;
    load();
    const intervalMs = performanceMode === 'PERFORMANCE' ? 5000 : 2500;
    const interval = window.setInterval(load, intervalMs);
    return () => window.clearInterval(interval);
  }, [active, performanceMode]);

  const referenceLabel = useMemo(() => {
    if (selectedLap === null) return 'AUTO';
    return selectedSessionId ? `${selectedSessionId}:L${selectedLap}` : `LIVE:L${selectedLap}`;
  }, [selectedLap, selectedSessionId]);

  // The painted limit lines are an independent check on the extracted edges:
  // where paint exists, the edge should sit on it. Only part of a lap is
  // painted, so having too little is not a defect -- only disagreeing is.
  const paint = report?.track.paintAgreement;
  const paintLabel = useMemo(() => {
    if (!paint || paint.status === 'UNAVAILABLE') return '--';
    if (paint.status === 'INSUFFICIENT_PAINT') return 'sem pintura util';
    const ratios = Object.values(paint.sides || {})
      .filter((side) => side.ratioMedian !== null)
      .map((side) => `${Math.round((side.ratioMedian as number) * 100)}%`);
    if (!ratios.length) return paint.status;
    return `${paint.status === 'OK' ? 'OK' : 'DIVERGE'} ${ratios.join(' / ')}`;
  }, [paint]);
  const paintTone: Tone = paint?.status === 'DIVERGENT'
    ? 'warning'
    : paint?.status === 'OK' ? 'ok' : 'quiet';

  const issues = [
    ...(report?.laps.issues || []),
    ...(report?.track.issues || []),
    ...(report?.comparison.issues || []),
  ].slice(0, 4);

  return (
    <div className="data-quality-panel">
      <header className="quality-header">
        <div>
          <span className="quality-eyebrow">Validation &amp; Data Reliability</span>
          <strong>Qualidade dos dados</strong>
        </div>
        <div className="quality-header-actions">
          <StatusChip status={report?.status || (error ? 'ERROR' : 'UNKNOWN')} />
          <button type="button" title="Atualizar diagnostico" onClick={load}>
            <RefreshCw size={13} className={refreshing ? 'quality-spin' : ''} />
          </button>
        </div>
      </header>

      {error && <div className="quality-error">{error}</div>}

      <div className="quality-scroll">
        <section className="quality-section">
          <div className="quality-section-title">
            <Activity size={12} />
            <span>Player / Shared Memory</span>
            <StatusChip status={report?.player.status} />
          </div>
          <div className="quality-metric-grid">
            <Metric label="Frequencia" value={hz(report?.player.estimatedHz)} tone={toneByStatus(report?.player.frequencyStatus)} />
            <Metric label="Meta" value={hz(report?.player.targetHz)} />
            <Metric label="Janela 30s" value={hz(report?.player.stableHz)} />
            <Metric label="Ultima amostra" value={age(report?.player.secondsSinceLastSample)} />
            <Metric label="Amostras" value={numberOr(report?.player.sampleCount).toLocaleString()} />
            <Metric
              label="Quedas estim."
              value={report?.player.droppedSamplesEstimate ?? '--'}
              tone={numberOr(report?.player.droppedSamplesEstimate) > 0 ? 'warning' : 'ok'}
            />
          </div>
          <div className="quality-boolean-grid">
            <BooleanMetric label="Fisica" value={Boolean(report?.player.hasPhysics)} />
            <BooleanMetric label="Pneus" value={Boolean(report?.player.hasTyres)} />
            <BooleanMetric label="Fuel" value={Boolean(report?.player.hasFuel)} />
            <BooleanMetric label="Suspensao" value={Boolean(report?.player.hasSuspension)} />
            <BooleanMetric label="Posicao" value={Boolean(report?.player.hasPosition)} />
            <BooleanMetric label="Spline" value={Boolean(report?.player.hasSpline)} />
          </div>
        </section>

        <section className="quality-section">
          <div className="quality-section-title">
            <Radio size={12} />
            <span>Oponentes / UDP</span>
            <StatusChip status={report?.opponents.status} />
          </div>
          <div className="quality-metric-grid quality-metric-grid-wide">
            <Metric label="Pacotes" value={numberOr(report?.opponents.packetsReceived).toLocaleString()} />
            <Metric label="Aceitos" value={numberOr(report?.opponents.packetsAccepted).toLocaleString()} tone="ok" />
            <Metric label="Hz" value={hz(report?.opponents.estimatedHz)} />
            <Metric label="Oponentes" value={numberOr(report?.opponents.opponentsCount)} />
            <Metric label="Invalidos" value={numberOr(report?.opponents.packetsInvalid)} tone={numberOr(report?.opponents.packetsInvalid) ? 'error' : 'ok'} />
            <Metric label="Fora ordem" value={numberOr(report?.opponents.packetsOutOfOrder)} tone={numberOr(report?.opponents.packetsOutOfOrder) ? 'warning' : 'ok'} />
            <Metric label="Descartados" value={numberOr(report?.opponents.packetsDropped)} />
            <Metric label="Player filtrado" value={numberOr(report?.opponents.playerFilteredCount)} />
          </div>
        </section>

        <div className="quality-dual-grid">
          <section className="quality-section">
            <div className="quality-section-title">
              <Database size={12} />
              <span>Voltas</span>
            </div>
            <div className="quality-summary-line">
              <b>{numberOr(report?.laps.validLapCount)}</b><span>validas</span>
              <b>{numberOr(report?.laps.partialLapCount)}</b><span>parciais</span>
              <b>{numberOr(report?.laps.invalidLapCount)}</b><span>invalidas</span>
            </div>
            <Metric label="Sessoes" value={numberOr(report?.laps.sessionCount)} />
            <Metric label="Completas" value={numberOr(report?.laps.completedLapCount)} />
          </section>

          <section className="quality-section">
            <div className="quality-section-title">
              <Route size={12} />
              <span>Pista</span>
              <StatusChip status={report?.track.status} />
            </div>
            <Metric label="Pontos" value={numberOr(report?.track.sampleCount).toLocaleString()} />
            <div className="quality-boolean-grid quality-boolean-grid-track">
              <BooleanMetric label="Centro" value={Boolean(report?.track.hasCenterline)} />
              <BooleanMetric label="Limites" value={Boolean(report?.track.hasBounds)} />
              <BooleanMetric label="Setores" value={Boolean(report?.track.hasSectors)} />
            </div>
            <Metric
              label="Confere com a pintura"
              value={paintLabel}
              tone={paintTone}
            />
          </section>
        </div>

        <section className="quality-section">
          <div className="quality-section-title">
            <GitCompare size={12} />
            <span>Comparacao</span>
            <StatusChip status={report?.comparison.status} />
          </div>
          <Metric label="Referencia ativa" value={referenceLabel} tone={selectedLap === null ? 'quiet' : 'ok'} />
        </section>

        {issues.length > 0 && (
          <section className="quality-issues">
            <div className="quality-section-title">
              <AlertTriangle size={12} />
              <span>Diagnosticos</span>
            </div>
            {issues.map((issue, index) => (
              <p key={`${issue}-${index}`}>{issue}</p>
            ))}
          </section>
        )}
      </div>

      <footer className="quality-footer">
        <ShieldCheck size={11} />
        <span>
          {report?.generatedAt
            ? `Atualizado ${new Date(report.generatedAt).toLocaleTimeString('pt-BR')}`
            : 'Aguardando relatorio local'}
        </span>
      </footer>
    </div>
  );
});
