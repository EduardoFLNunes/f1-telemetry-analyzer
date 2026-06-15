import React, { useEffect, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  Download,
  FileCheck2,
  Flag,
  Gauge,
  Radio,
  RefreshCw,
  Route,
} from 'lucide-react';
import { api } from '../api/client';
import { useTelemetryStore } from '../store/useTelemetryStore';
import { formatLapTime } from '../utils/lapFormat';

type AuditStatus = 'OK' | 'WARNING' | 'ERROR' | 'UNKNOWN';

type AuditReport = {
  sessionId: string;
  trackName: string | null;
  carName: string | null;
  startedAt: string | null;
  endedAt: string | null;
  durationSeconds: number | null;
  overallStatus: AuditStatus;
  playerCapture: {
    source: 'shared_memory';
    targetHz: number;
    avgHz: number | null;
    minHz: number | null;
    maxHz: number | null;
    p95FrameGapMs: number | null;
    p99FrameGapMs: number | null;
    totalSamples: number;
    estimatedDroppedSamples: number | null;
    longestGapMs: number | null;
    stalePeriods: number;
    qualityStatus: AuditStatus;
  };
  udpOpponents: {
    source: 'udp';
    totalPacketsReceived: number;
    totalPacketsAccepted: number;
    totalPacketsDropped: number;
    totalPacketsInvalid: number;
    totalPacketsOutOfOrder: number;
    playerFilteredCount: number;
    avgHz: number | null;
    opponentsSeen: number;
    qualityStatus: AuditStatus;
  };
  laps: {
    totalLaps: number;
    validLaps: number;
    partialLaps: number;
    invalidLaps: number;
    bestValidLapId: string | null;
    bestValidLapTime: number | null;
    issues: string[];
  };
  track: {
    status: string;
    hasCenterline: boolean;
    hasBounds: boolean;
    hasSectors: boolean;
    calibrationProfile: string | null;
    issues: string[];
  };
  recommendations: string[];
};

const tone = (status?: string | null) => {
  const value = String(status || 'UNKNOWN').toUpperCase();
  if (['OK', 'VALID', 'TRACK_READY'].includes(value)) return 'ok';
  if (['ERROR', 'INVALID', 'TRACK_MISSING'].includes(value)) return 'error';
  if (['WARNING', 'PARTIAL', 'TRACK_PARTIAL'].includes(value)) return 'warning';
  return 'quiet';
};

const StatusChip = ({ status }: { status?: string | null }) => (
  <span className="quality-chip" data-tone={tone(status)}>
    {String(status || 'UNKNOWN').replace(/_/g, ' ')}
  </span>
);

const valueOr = (value: number | null | undefined, digits = 1) => (
  value === null || value === undefined || !Number.isFinite(Number(value))
    ? '--'
    : Number(value).toFixed(digits)
);

const Metric = ({
  label,
  value,
  status,
}: {
  label: string;
  value: React.ReactNode;
  status?: string | null;
}) => (
  <div className="quality-metric" data-tone={tone(status)}>
    <span>{label}</span>
    <strong>{value}</strong>
  </div>
);

export const SessionAuditPanel = React.memo(function SessionAuditPanel({
  active = true,
}: {
  active?: boolean;
}) {
  const performanceMode = useTelemetryStore((state) => state.performanceMode);
  const [report, setReport] = useState<AuditReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [exportMessage, setExportMessage] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const payload = await api.getLatestSessionAudit();
      setReport(payload.audit || null);
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Auditoria indisponivel');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!active) return undefined;
    load();
    const interval = window.setInterval(
      load,
      performanceMode === 'PERFORMANCE' ? 30000 : 15000,
    );
    return () => window.clearInterval(interval);
  }, [active, performanceMode]);

  const exportReport = async () => {
    setLoading(true);
    try {
      const result = await api.exportLatestSessionAudit();
      setExportMessage(`JSON + Markdown: ${result.directory}`);
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Falha ao exportar relatorio');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="data-quality-panel session-audit-panel">
      <header className="quality-header">
        <div>
          <span className="quality-eyebrow">Real Session Audit &amp; Calibration</span>
          <strong>Auditoria da sessão</strong>
        </div>
        <div className="quality-header-actions">
          <StatusChip status={report?.overallStatus || (error ? 'ERROR' : 'UNKNOWN')} />
          <button type="button" title="Atualizar auditoria" onClick={load}>
            <RefreshCw size={13} className={loading ? 'quality-spin' : ''} />
          </button>
          <button type="button" title="Exportar relatorio" onClick={exportReport} disabled={!report}>
            <Download size={13} />
          </button>
        </div>
      </header>

      {error && <div className="quality-error">{error}</div>}
      {!report && !error && (
        <div className="audit-empty">
          Nenhuma sessão persistida com telemetria foi encontrada.
        </div>
      )}

      {report && (
        <div className="quality-scroll">
          <section className="quality-section audit-session-summary">
            <div className="quality-section-title">
              <FileCheck2 size={12} />
              <span>Sessão auditada</span>
              <StatusChip status={report.overallStatus} />
            </div>
            <strong>{report.trackName || 'Pista desconhecida'}</strong>
            <small>{report.sessionId}</small>
            <div className="audit-meta-line">
              <span>{report.carName || 'Carro não identificado'}</span>
              <span>{report.durationSeconds ? `${valueOr(report.durationSeconds, 0)}s` : '--'}</span>
            </div>
          </section>

          <section className="quality-section">
            <div className="quality-section-title">
              <Activity size={12} />
              <span>Player / Shared Memory</span>
              <StatusChip status={report.playerCapture.qualityStatus} />
            </div>
            <div className="quality-metric-grid">
              <Metric label="Média" value={`${valueOr(report.playerCapture.avgHz)} Hz`} status={report.playerCapture.qualityStatus} />
              <Metric label="P95 gap" value={`${valueOr(report.playerCapture.p95FrameGapMs)} ms`} />
              <Metric label="P99 gap" value={`${valueOr(report.playerCapture.p99FrameGapMs)} ms`} />
              <Metric label="Amostras" value={report.playerCapture.totalSamples.toLocaleString()} />
              <Metric label="Perdidas est." value={report.playerCapture.estimatedDroppedSamples ?? '--'} />
              <Metric label="Maior gap" value={`${valueOr(report.playerCapture.longestGapMs)} ms`} />
            </div>
          </section>

          <div className="quality-dual-grid">
            <section className="quality-section">
              <div className="quality-section-title">
                <Flag size={12} />
                <span>Voltas</span>
              </div>
              <div className="quality-summary-line">
                <b>{report.laps.validLaps}</b><span>válidas</span>
                <b>{report.laps.partialLaps}</b><span>parciais</span>
                <b>{report.laps.invalidLaps}</b><span>inválidas</span>
              </div>
              <Metric label="Melhor válida" value={formatLapTime(report.laps.bestValidLapTime)} status={report.laps.bestValidLapTime ? 'OK' : 'UNKNOWN'} />
            </section>

            <section className="quality-section">
              <div className="quality-section-title">
                <Radio size={12} />
                <span>UDP</span>
                <StatusChip status={report.udpOpponents.qualityStatus} />
              </div>
              <div className="quality-metric-grid audit-compact-grid">
                <Metric label="Recebidos" value={report.udpOpponents.totalPacketsReceived.toLocaleString()} />
                <Metric label="Descartados" value={report.udpOpponents.totalPacketsDropped} />
                <Metric label="Oponentes" value={report.udpOpponents.opponentsSeen} />
              </div>
            </section>
          </div>

          <section className="quality-section">
            <div className="quality-section-title">
              <Route size={12} />
              <span>Pista / Calibração</span>
              <StatusChip status={report.track.status} />
            </div>
            <div className="quality-metric-grid">
              <Metric label="Perfil" value={report.track.calibrationProfile || 'default'} />
              <Metric label="Centerline" value={report.track.hasCenterline ? 'OK' : 'MISS'} status={report.track.hasCenterline ? 'OK' : 'WARNING'} />
              <Metric label="Limites" value={report.track.hasBounds ? 'OK' : 'MISS'} status={report.track.hasBounds ? 'OK' : 'WARNING'} />
            </div>
          </section>

          <section className="quality-issues audit-recommendations">
            <div className="quality-section-title">
              <Gauge size={12} />
              <span>Recomendações</span>
            </div>
            {report.recommendations.slice(0, 5).map((item, index) => (
              <p key={`${item}-${index}`}>{item}</p>
            ))}
          </section>

          {report.laps.issues.length > 0 && (
            <section className="quality-issues">
              <div className="quality-section-title">
                <AlertTriangle size={12} />
                <span>Issues de voltas</span>
              </div>
              {report.laps.issues.slice(0, 4).map((item, index) => (
                <p key={`${item}-${index}`}>{item}</p>
              ))}
            </section>
          )}
        </div>
      )}

      <footer className="quality-footer">
        <FileCheck2 size={11} />
        <span>{exportMessage || 'Relatórios locais em JSON e Markdown'}</span>
      </footer>
    </div>
  );
});
