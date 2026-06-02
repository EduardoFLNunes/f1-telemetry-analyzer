import React, { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Bot, Radio, Target, Timer } from 'lucide-react';
import { api } from '../api/client';
import { CoachingReport, CoachingSeverity } from '../types/raceCoach';
import { PerformanceMode, useTelemetryStore } from '../store/useTelemetryStore';
import { useRenderCounter } from '../hooks/useRenderCounter';

const BORDER = 'rgba(255,255,255,0.06)';
const SURFACE = 'rgba(255,255,255,0.025)';
const TEXT = '#e2e8f0';
const MUTED = '#64748b';
const CYAN = '#22d3ee';
const EMERALD = '#34d399';
const AMBER = '#fbbf24';
const ROSE = '#fb7185';

const POLL_MS: Record<PerformanceMode, number> = {
  QUALITY: 3000,
  BALANCED: 5000,
  PERFORMANCE: 8000,
};

const severityColor = (severity: CoachingSeverity | null | undefined) => {
  if (severity === 'HIGH') return ROSE;
  if (severity === 'MEDIUM') return AMBER;
  if (severity === 'LOW') return CYAN;
  return MUTED;
};

const formatSeconds = (value: number | null | undefined) => {
  if (value === null || value === undefined || !Number.isFinite(value)) return '--';
  return `${value > 0 ? '+' : ''}${value.toFixed(3)}s`;
};

const issueLabel = (issue: string | null | undefined) => {
  if (issue === 'BRAKING_TOO_EARLY') return 'Freio cedo';
  if (issue === 'BRAKING_TOO_LATE') return 'Freio tarde';
  if (issue === 'ACCELERATING_TOO_LATE') return 'Acel. tardia';
  if (issue === 'LOW_CORNER_SPEED') return 'Contorno baixo';
  if (issue === 'LOW_EXIT_SPEED') return 'Saida baixa';
  if (issue === 'TRAJECTORY_DEVIATION') return 'Trajetoria';
  if (issue === 'GOOD_GAIN') return 'Ganho';
  if (issue === 'SECTOR_LOSS') return 'Perda setor';
  if (issue === 'INSUFFICIENT_DATA') return 'Sem dados';
  return '--';
};

const Stat = ({ label, value, color = TEXT }: { label: string; value: string; color?: string }) => (
  <div style={{ minWidth: 0, border: `1px solid ${BORDER}`, background: SURFACE, borderRadius: 4, padding: 9 }}>
    <div className="label" style={{ fontSize: 8, marginBottom: 4 }}>{label}</div>
    <div className="num" style={{ fontSize: 13, fontWeight: 900, color, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{value}</div>
  </div>
);

export const RaceCoachPanel = React.memo(function RaceCoachPanel({
  active = true,
  microSectorCount = 50,
}: {
  active?: boolean;
  microSectorCount?: number;
}) {
  useRenderCounter('RaceCoachPanel');
  const performanceMode = useTelemetryStore((state) => state.performanceMode);
  const [report, setReport] = useState<CoachingReport | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!active) return undefined;
    let cancelled = false;
    let inFlight = false;

    const load = async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        const data = await api.getRaceCoach(microSectorCount, { performanceMode });
        if (!cancelled) {
          setReport(data as CoachingReport);
          setFailed(false);
        }
      } catch {
        if (!cancelled) setFailed(true);
      } finally {
        inFlight = false;
      }
    };

    load();
    const interval = setInterval(load, POLL_MS[performanceMode] ?? POLL_MS.BALANCED);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [active, microSectorCount, performanceMode]);

  const ready = report?.status === 'READY';
  const topInsights = report?.topInsights ?? [];
  const sectorInsights = report?.sectorInsights ?? [];
  const statusMessage = useMemo(() => {
    if (failed) return 'Race Coach indisponivel.';
    if (!report) return 'Aguardando coach...';
    if (!ready) return 'Dados insuficientes para coaching confiavel.';
    if (!topInsights.length) return 'Sem perda relevante detectada nesta leitura.';
    return topInsights[0].message;
  }, [failed, ready, report, topInsights]);

  return (
    <div style={{ border: `1px solid ${BORDER}`, background: 'rgba(12,12,22,0.92)', borderRadius: 4, overflow: 'hidden' }}>
      <div style={{ padding: '9px 10px', borderBottom: `1px solid ${BORDER}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 7 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
          <Bot size={13} color={ready ? CYAN : AMBER} />
          <span className="num" style={{ fontSize: 10, fontWeight: 900, color: TEXT, textTransform: 'uppercase' }}>Race Coach</span>
        </div>
        <span className="num" style={{ fontSize: 9, color: ready ? EMERALD : AMBER, fontWeight: 900 }}>{report?.status ?? 'WAIT'}</span>
      </div>

      <div style={{ padding: 10, display: 'flex', flexDirection: 'column', gap: 9 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 7 }}>
          <Stat label="PROBLEMA" value={issueLabel(report?.summary?.mainIssue)} color={ready ? CYAN : MUTED} />
          <Stat label="PIOR SETOR" value={report?.summary?.worstSector ? `S${report.summary.worstSector}` : '--'} color={ready ? AMBER : MUTED} />
          <Stat label="PERDA" value={formatSeconds(report?.summary?.estimatedTotalLossSeconds)} color={ready ? ROSE : MUTED} />
        </div>

        <div style={{ display: 'flex', gap: 7, alignItems: 'flex-start', border: `1px solid ${BORDER}`, background: ready ? 'rgba(34,211,238,0.035)' : 'rgba(251,191,36,0.035)', borderRadius: 4, padding: 7 }}>
          <Radio size={12} color={ready ? CYAN : AMBER} style={{ flexShrink: 0, marginTop: 1 }} />
          <div className="num" style={{ fontSize: 10, lineHeight: 1.45, color: TEXT }}>{statusMessage}</div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
          {topInsights.length ? (
            topInsights.slice(0, 3).map((insight) => (
              <div key={insight.id} style={{ border: `1px solid ${BORDER}`, background: SURFACE, borderRadius: 4, padding: 9 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6, marginBottom: 4 }}>
                  <div className="num" style={{ fontSize: 10, color: TEXT, fontWeight: 900, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{insight.title}</div>
                  <div className="num" style={{ fontSize: 9, color: severityColor(insight.severity), fontWeight: 900 }}>{insight.severity}</div>
                </div>
                <div className="num" style={{ fontSize: 9, lineHeight: 1.42, color: TEXT, marginBottom: 6 }}>{insight.message}</div>
                <div className="num" style={{ fontSize: 9, lineHeight: 1.42, color: MUTED }}>{insight.recommendation}</div>
                <div style={{ marginTop: 6, display: 'flex', justifyContent: 'space-between', gap: 7 }}>
                  <span className="num" style={{ fontSize: 8, color: MUTED }}>S{insight.sector ?? '--'} / M{insight.segmentIndex ?? '--'}</span>
                  <span className="num" style={{ fontSize: 8, color: severityColor(insight.severity), fontWeight: 900 }}>{formatSeconds(insight.estimatedDeltaSeconds)}</span>
                </div>
              </div>
            ))
          ) : (
            <div style={{ border: `1px solid ${BORDER}`, background: SURFACE, borderRadius: 4, padding: 8, display: 'flex', alignItems: 'center', gap: 7 }}>
              <AlertTriangle size={12} color={ready ? EMERALD : AMBER} />
              <span className="num" style={{ fontSize: 10, color: MUTED }}>{ready ? 'Sem insights prioritarios.' : 'Aguardando volta valida.'}</span>
            </div>
          )}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 7 }}>
          {sectorInsights.slice(0, 3).map((sector) => (
            <div key={sector.sector} style={{ border: `1px solid ${BORDER}`, background: SURFACE, borderRadius: 4, padding: 8, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 3 }}>
                <Target size={10} color={sector.estimatedDeltaSeconds && sector.estimatedDeltaSeconds > 0 ? ROSE : CYAN} />
                <span className="label" style={{ fontSize: 8 }}>S{sector.sector}</span>
              </div>
              <div className="num" style={{ fontSize: 10, color: TEXT, fontWeight: 800 }}>{formatSeconds(sector.estimatedDeltaSeconds)}</div>
              <div className="num" style={{ marginTop: 4, fontSize: 8, color: MUTED, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{issueLabel(sector.mainIssue)}</div>
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <Timer size={11} color={MUTED} />
            <span className="num" style={{ fontSize: 8, color: MUTED }}>REF V{report?.referenceLapNumber ?? '--'} / CUR V{report?.currentLapNumber ?? '--'}</span>
          </div>
          <span className="num" style={{ fontSize: 8, color: MUTED }}>
            {report?.debug?.comparisonSegments ?? 0} seg / {report?.debug?.generatedInsights ?? 0} insights
          </span>
        </div>
      </div>
    </div>
  );
});
