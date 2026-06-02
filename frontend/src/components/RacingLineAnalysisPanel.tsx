import React, { useEffect, useMemo, useState } from 'react';
import { Activity, AlertTriangle, BarChart3, Gauge, Timer, Trophy } from 'lucide-react';
import { api } from '../api/client';
import { RacingLineComparisonSegment, RacingLineLapSummary, RacingLinePayload } from '../types/racingLine';
import { useRenderCounter } from '../hooks/useRenderCounter';
import { RaceCoachPanel } from './RaceCoachPanel';

const PANEL_BG = '#0c0c16';
const SURFACE = 'rgba(255,255,255,0.025)';
const BORDER = 'rgba(255,255,255,0.06)';
const CYAN = '#22d3ee';
const EMERALD = '#34d399';
const ROSE = '#fb7185';
const AMBER = '#fbbf24';
const TEXT = '#e2e8f0';
const MUTED = '#64748b';

const formatNumber = (value: number | null | undefined, digits = 1) => (
  value === null || value === undefined || !Number.isFinite(value) ? '--' : value.toFixed(digits)
);

const formatSeconds = (value: number | null | undefined) => {
  if (value === null || value === undefined || !Number.isFinite(value)) return '--';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(3)}s`;
};

const formatLapTime = (value: number | null | undefined) => {
  if (value === null || value === undefined || !Number.isFinite(value)) return '--:--.---';
  const minutes = Math.floor(value / 60);
  const seconds = value - minutes * 60;
  return `${minutes}:${seconds.toFixed(3).padStart(6, '0')}`;
};

const formatDeltaCompact = (value: number | null | undefined) => {
  if (value === null || value === undefined || !Number.isFinite(value)) return '--';
  if (Math.abs(value) < 0.0005) return 'BEST';
  return `${value > 0 ? '+' : ''}${value.toFixed(3)}`;
};

const deltaColor = (value: number | null | undefined) => {
  if (value === null || value === undefined) return MUTED;
  if (value > 0.03) return ROSE;
  if (value < -0.03) return EMERALD;
  return MUTED;
};

const issueLabel = (issue: string | null | undefined) => {
  if (issue === 'TRAJECTORY') return 'Trajetoria';
  if (issue === 'BRAKING_TOO_EARLY') return 'Freio cedo';
  if (issue === 'BRAKING_TOO_LATE') return 'Freio tarde';
  if (issue === 'ACCELERATING_TOO_LATE') return 'Acel. tardia';
  if (issue === 'LOW_CORNER_SPEED') return 'Contorno baixo';
  if (issue === 'LOW_EXIT_SPEED') return 'Saida baixa';
  if (issue === 'GOOD') return 'Bom';
  if (issue === 'INSUFFICIENT_DATA') return 'Sem dados';
  return 'Inconclusivo';
};

const sourceLabel = (source: string | null | undefined) => {
  if (source === 'REFERENCE_LAP') return 'Referencia';
  if (source === 'BEST_LAP') return 'Melhor volta';
  if (source === 'COMPOSITE') return 'Composta';
  if (source === 'IMPORTED') return 'Importada';
  return 'Desconhecida';
};

const pillStyle = (active: boolean): React.CSSProperties => ({
  height: 26,
  minWidth: 42,
  border: `1px solid ${active ? 'rgba(34,211,238,0.45)' : BORDER}`,
  borderRadius: 4,
  background: active ? 'rgba(34,211,238,0.1)' : 'transparent',
  color: active ? CYAN : MUTED,
  cursor: 'pointer',
  fontSize: 9,
  fontWeight: 800,
});

const Stat = ({ label, value, color = TEXT }: { label: string; value: string; color?: string }) => (
  <div style={{ padding: 10, border: `1px solid ${BORDER}`, background: SURFACE, borderRadius: 4, minWidth: 0 }}>
    <div className="label" style={{ fontSize: 8, marginBottom: 5 }}>{label}</div>
    <div className="num" style={{ fontSize: 14, color, fontWeight: 900, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
      {value}
    </div>
  </div>
);

const SectorCard = ({
  sector,
  delta,
  issue,
  worstSegment,
}: {
  sector: number;
  delta: number | null;
  issue: string | null;
  worstSegment: number | null;
}) => (
  <div style={{ padding: 9, border: `1px solid ${BORDER}`, background: SURFACE, borderRadius: 4, display: 'flex', flexDirection: 'column', gap: 6 }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <span className="label" style={{ fontSize: 8 }}>SETOR {sector}</span>
      <span className="num" style={{ fontSize: 11, color: deltaColor(delta), fontWeight: 900 }}>{formatSeconds(delta)}</span>
    </div>
    <div className="num" style={{ fontSize: 10, color: TEXT, lineHeight: 1.35 }}>{issueLabel(issue)}</div>
    <div className="num" style={{ fontSize: 8, color: MUTED }}>MICRO {worstSegment ?? '--'}</div>
  </div>
);

const SegmentRow = ({ segment }: { segment: RacingLineComparisonSegment }) => (
  <div
    className="num"
    style={{
      display: 'grid',
      gridTemplateColumns: '42px 58px 54px 54px minmax(0, 1fr)',
      gap: 8,
      alignItems: 'center',
      minHeight: 30,
      padding: '6px 8px',
      borderBottom: `1px solid ${BORDER}`,
      fontSize: 9,
      color: TEXT,
    }}
  >
    <span style={{ color: MUTED }}>{segment.segmentIndex}</span>
    <span style={{ color: deltaColor(segment.estimatedDeltaSeconds), fontWeight: 800 }}>{formatSeconds(segment.estimatedDeltaSeconds)}</span>
    <span>{formatNumber(segment.playerSpeedKmh, 0)}</span>
    <span>{formatNumber(segment.trajectoryDeviationMeters, 1)}</span>
    <span style={{ color: MUTED, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{issueLabel(segment.mainIssue)}</span>
  </div>
);

const LapRow = ({ lap, rank }: { lap: RacingLineLapSummary; rank?: number }) => (
  <div
    className="num"
    style={{
      display: 'grid',
      gridTemplateColumns: '38px minmax(0, 1fr) 70px 56px',
      gap: 8,
      alignItems: 'center',
      minHeight: 28,
      padding: '5px 0',
      borderBottom: `1px solid ${BORDER}`,
      fontSize: 9,
      color: lap.valid ? TEXT : MUTED,
    }}
  >
    <span style={{ color: lap.usedForRacingLine ? CYAN : MUTED }}>{rank ? `#${rank}` : `V${lap.lapNumber}`}</span>
    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
      V{lap.lapNumber}
      {lap.usedForRacingLine ? ' REF' : ''}
      {!lap.valid && lap.rejectedReason ? ` ${lap.rejectedReason}` : ''}
    </span>
    <span style={{ color: lap.valid ? TEXT : MUTED, fontWeight: lap.usedForRacingLine ? 900 : 700 }}>
      {formatLapTime(lap.durationSeconds)}
    </span>
    <span style={{ color: deltaColor(lap.deltaToBestSeconds), textAlign: 'right', fontWeight: 800 }}>
      {formatDeltaCompact(lap.deltaToBestSeconds)}
    </span>
  </div>
);

export const RacingLineAnalysisPanel = React.memo(function RacingLineAnalysisPanel({ active = true }: { active?: boolean }) {
  useRenderCounter('RacingLineAnalysisPanel');
  const [microSectorCount, setMicroSectorCount] = useState(50);
  const [payload, setPayload] = useState<RacingLinePayload | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!active) return undefined;
    let cancelled = false;
    const load = async () => {
      try {
        const data = await api.getRacingLine(microSectorCount, {
          includeVisualLine: false,
          includeComparison: true,
        });
        if (!cancelled) {
          setPayload(data as RacingLinePayload);
          setFailed(false);
        }
      } catch {
        if (!cancelled) setFailed(true);
      }
    };
    load();
    const interval = setInterval(load, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [active, microSectorCount]);

  const racingLine = payload?.racingLine ?? null;
  const comparison = payload?.comparison ?? null;
  const fastestLaps = payload?.fastestLaps ?? [];
  const lapHistory = payload?.lapHistory ?? [];
  const bestLap = fastestLaps[0] ?? lapHistory.find((lap) => lap.usedForRacingLine) ?? null;
  const validLapCount = lapHistory.filter((lap) => lap.valid).length;
  const status = payload?.status ?? 'INSUFFICIENT_DATA';
  const ready = status === 'READY' && Boolean(racingLine);

  const keyMessage = useMemo(() => {
    if (failed) return 'Endpoint de Racing Line indisponivel.';
    if (!payload) return 'Aguardando Racing Line...';
    if (payload.status !== 'READY') {
      if (payload.debug?.reason === 'previous_lap_not_valid_reference') {
        return 'Racing Line ainda indisponivel: volta anterior parcial ou invalida.';
      }
      return 'Racing Line ainda indisponivel: nenhuma volta de referencia valida.';
    }
    if (bestLap) {
      return `Racing Line usando a melhor volta valida: V${bestLap.lapNumber} (${formatLapTime(bestLap.durationSeconds)}).`;
    }
    if (racingLine?.referenceLapNumber !== null && racingLine?.referenceLapNumber !== undefined) {
      return `Racing Line gerada a partir da volta ${racingLine.referenceLapNumber}.`;
    }
    return 'Racing Line gerada a partir da volta de referencia.';
  }, [bestLap, failed, payload, racingLine?.referenceLapNumber]);

  const sectorSummary = comparison?.sectorSummary ?? ([1, 2, 3] as const).map((sector) => ({
    sector,
    estimatedDeltaSeconds: null,
    biggestIssue: null,
    worstSegmentIndex: null,
  }));
  const losses = comparison?.biggestLosses ?? [];
  const gains = comparison?.biggestGains ?? [];
  const segments = comparison?.segments ?? [];

  return (
    <div className="panel" style={{ height: '100%', display: 'flex', flexDirection: 'column', background: PANEL_BG, overflow: 'auto' }}>
      <div style={{ padding: '10px 11px', borderBottom: `1px solid ${BORDER}`, display: 'flex', flexDirection: 'column', gap: 9 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
            <Activity size={14} color={ready ? CYAN : AMBER} />
            <span className="num" style={{ fontSize: 10, fontWeight: 900, color: TEXT, textTransform: 'uppercase' }}>Racing Line</span>
          </div>
          <div style={{ display: 'flex', gap: 3 }}>
            {[20, 50, 100].map((count) => (
              <button key={count} type="button" onClick={() => setMicroSectorCount(count)} style={pillStyle(microSectorCount === count)} className="num">
                {count}
              </button>
            ))}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 5 }}>
          <Stat label="STATUS" value={ready ? 'READY' : 'WAITING'} color={ready ? EMERALD : AMBER} />
          <Stat label="FONTE" value={sourceLabel(racingLine?.source)} color={ready ? CYAN : MUTED} />
          <Stat label="MELHOR" value={formatLapTime(bestLap?.durationSeconds)} color={bestLap ? EMERALD : MUTED} />
          <Stat label="HIST" value={`${validLapCount}/${lapHistory.length}`} />
          <Stat label="VOLTA BASE" value={racingLine?.referenceLapNumber === null || racingLine?.referenceLapNumber === undefined ? '--' : `V${racingLine.referenceLapNumber}`} />
          <Stat label="VALIDOS" value={`${racingLine?.debug.validSegments ?? 0}/${racingLine?.microSectorCount ?? microSectorCount}`} color={ready ? EMERALD : MUTED} />
        </div>

        <div style={{ display: 'flex', gap: 7, alignItems: 'flex-start', border: `1px solid ${BORDER}`, background: ready ? 'rgba(34,211,238,0.035)' : 'rgba(251,191,36,0.035)', padding: 7, borderRadius: 4 }}>
          <AlertTriangle size={13} color={ready ? CYAN : AMBER} style={{ flexShrink: 0, marginTop: 1 }} />
          <div className="num" style={{ fontSize: 10, lineHeight: 1.45, color: TEXT }}>{keyMessage}</div>
        </div>

        <div style={{ border: `1px solid ${BORDER}`, background: SURFACE, borderRadius: 4, padding: '6px 7px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <Trophy size={12} color={EMERALD} />
              <span className="label" style={{ fontSize: 8 }}>TOP VOLTAS</span>
            </div>
            <span className="num" style={{ fontSize: 9, color: MUTED }}>{fastestLaps.length} validas</span>
          </div>
          {fastestLaps.length ? (
            fastestLaps.slice(0, 3).map((lap, index) => <LapRow key={lap.lapNumber} lap={lap} rank={index + 1} />)
          ) : (
            <div className="num" style={{ fontSize: 10, color: MUTED, padding: '4px 0' }}>Aguardando voltas validas.</div>
          )}
        </div>

        <RaceCoachPanel active={active} microSectorCount={microSectorCount} />
      </div>

      <div style={{ padding: '9px 11px', borderBottom: `1px solid ${BORDER}`, display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 7 }}>
        {sectorSummary.map((sector) => (
          <SectorCard
            key={sector.sector}
            sector={sector.sector}
            delta={sector.estimatedDeltaSeconds}
            issue={sector.biggestIssue}
            worstSegment={sector.worstSegmentIndex}
          />
        ))}
      </div>

      <div style={{ padding: '9px 11px', borderBottom: `1px solid ${BORDER}`, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <Timer size={12} color={ROSE} />
            <span className="label" style={{ fontSize: 8 }}>PERDAS</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {(losses.length ? losses : [{ segmentIndex: '--', estimatedDeltaSeconds: null, mainIssue: null }]).slice(0, 3).map((loss, index) => (
              <div key={`${loss.segmentIndex}-${index}`} className="num" style={{ display: 'flex', justifyContent: 'space-between', gap: 5, fontSize: 9, color: TEXT }}>
                <span>SEG {loss.segmentIndex}</span>
                <span style={{ color: deltaColor(loss.estimatedDeltaSeconds), fontWeight: 800 }}>{formatSeconds(loss.estimatedDeltaSeconds)}</span>
              </div>
            ))}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <Trophy size={12} color={EMERALD} />
            <span className="label" style={{ fontSize: 8 }}>GANHOS</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {(gains.length ? gains : [{ segmentIndex: '--', estimatedDeltaSeconds: null, mainIssue: null }]).slice(0, 3).map((gain, index) => (
              <div key={`${gain.segmentIndex}-${index}`} className="num" style={{ display: 'flex', justifyContent: 'space-between', gap: 5, fontSize: 9, color: TEXT }}>
                <span>SEG {gain.segmentIndex}</span>
                <span style={{ color: deltaColor(gain.estimatedDeltaSeconds), fontWeight: 800 }}>{formatSeconds(gain.estimatedDeltaSeconds)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ padding: '9px 11px', borderBottom: `1px solid ${BORDER}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, minWidth: 0 }}>
          <Gauge size={12} color={CYAN} />
          <span className="label" style={{ fontSize: 8 }}>MICROSETORES</span>
        </div>
        <div className="num" style={{ fontSize: 10, color: MUTED }}>
          P {comparison?.debug?.playerSamples ?? 0} / REF {racingLine?.debug?.inputSamples ?? 0}
        </div>
      </div>

      <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
        <div style={{ padding: '9px 11px', borderBottom: `1px solid ${BORDER}` }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <BarChart3 size={12} color={CYAN} />
              <span className="label" style={{ fontSize: 8 }}>HISTORICO DE VOLTAS</span>
            </div>
            <span className="num" style={{ fontSize: 9, color: MUTED }}>{lapHistory.length} voltas</span>
          </div>
          {lapHistory.length ? (
            lapHistory.slice(-8).reverse().map((lap) => <LapRow key={lap.lapNumber} lap={lap} />)
          ) : (
            <div className="num" style={{ fontSize: 10, color: MUTED, padding: '4px 0' }}>Nenhuma volta completa ainda.</div>
          )}
        </div>

        <div
          className="label"
          style={{
            display: 'grid',
            gridTemplateColumns: '42px 58px 54px 54px minmax(0, 1fr)',
            gap: 8,
            padding: '7px 8px',
            position: 'sticky',
            top: 0,
            background: '#08080f',
            borderBottom: `1px solid ${BORDER}`,
            zIndex: 1,
            fontSize: 8,
          }}
        >
          <span>SEG</span>
          <span>DELTA</span>
          <span>KMH</span>
          <span>DESV</span>
          <span>ISSUE</span>
        </div>
        {segments.length ? (
          segments.map((segment) => <SegmentRow key={segment.segmentIndex} segment={segment} />)
        ) : (
          <div className="num" style={{ padding: 12, fontSize: 10, color: MUTED }}>Sem microsetores comparaveis.</div>
        )}
      </div>

      <div style={{ borderTop: `1px solid ${BORDER}`, padding: '6px 9px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
        <div className="num" style={{ fontSize: 8, color: MUTED }}>TRACK {payload?.track ?? '--'}</div>
        <div className="num" style={{ fontSize: 8, color: ready ? EMERALD : AMBER, textAlign: 'right' }}>{status}</div>
        <div className="num" style={{ gridColumn: '1 / -1', fontSize: 8, color: MUTED, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {comparison?.debug?.reasonForRejectedSegments?.join(', ') || payload?.debug?.reason || 'ready'}
        </div>
      </div>
    </div>
  );
});
