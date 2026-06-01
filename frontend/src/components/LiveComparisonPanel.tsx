import React, { useMemo, useState } from 'react';
import { AlertTriangle, BarChart3, Gauge, Timer, Trophy } from 'lucide-react';
import { LapDebugState, OpponentCarState, TelemetryFrame, useTelemetryStore } from '../store/useTelemetryStore';
import { useRenderCounter } from '../hooks/useRenderCounter';
import { buildComparisonAnalysisFromStore, ComparisonSegment, LossReason } from '../utils/comparisonAnalysis';

const PANEL_BG = '#0c0c16';
const SURFACE = 'rgba(255,255,255,0.025)';
const BORDER = 'rgba(255,255,255,0.06)';
const CYAN = '#22d3ee';
const EMERALD = '#34d399';
const ROSE = '#fb7185';
const AMBER = '#fbbf24';
const TEXT = '#e2e8f0';
const MUTED = '#64748b';

const EMPTY_FRAMES: TelemetryFrame[] = [];
const EMPTY_OPPONENT_HISTORY: Record<number, OpponentCarState[]> = {};

const formatSeconds = (value: number | null | undefined) => {
  if (value === null || value === undefined || !Number.isFinite(value)) return '--';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(3)}s`;
};

const formatNumber = (value: number | null | undefined, digits = 1) => (
  value === null || value === undefined || !Number.isFinite(value) ? '--' : value.toFixed(digits)
);

const reasonLabel = (reason: LossReason | string | null | undefined) => {
  if (reason === 'BRAKING') return 'Freia antes';
  if (reason === 'ACCELERATION') return 'Acelera depois';
  if (reason === 'SPEED') return 'Velocidade';
  if (reason === 'TRAJECTORY') return 'Trajetoria';
  if (reason === 'UNKNOWN') return 'Inconclusivo';
  return 'Sem dados';
};

const classificationLabel = (classification: string | null | undefined) => {
  if (!classification) return 'Sem dados';
  return classification
    .replace(/^OPPONENT_/, 'OPP ')
    .replace(/_/g, ' ')
    .toLowerCase();
};

const deltaColor = (value: number | null | undefined) => {
  if (value === null || value === undefined) return MUTED;
  if (value > 0.03) return ROSE;
  if (value < -0.03) return EMERALD;
  return MUTED;
};

const pillStyle = (active: boolean): React.CSSProperties => ({
  height: 22,
  minWidth: 34,
  border: `1px solid ${active ? 'rgba(34,211,238,0.45)' : BORDER}`,
  borderRadius: 4,
  background: active ? 'rgba(34,211,238,0.1)' : 'transparent',
  color: active ? CYAN : MUTED,
  cursor: 'pointer',
  fontSize: 8,
  fontWeight: 800,
});

const SectorCard = ({
  sector,
  delta,
  reason,
  bestOpponent,
  worstSegment,
}: {
  sector: number;
  delta: number | null;
  reason: string | null;
  bestOpponent: number | null;
  worstSegment: number | null;
}) => (
  <div style={{ padding: 8, border: `1px solid ${BORDER}`, background: SURFACE, borderRadius: 4, display: 'flex', flexDirection: 'column', gap: 5 }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <span className="label" style={{ fontSize: 6 }}>SETOR {sector}</span>
      <span className="num" style={{ fontSize: 9, color: deltaColor(delta), fontWeight: 800 }}>{formatSeconds(delta)}</span>
    </div>
    <div className="num" style={{ fontSize: 8, color: TEXT, lineHeight: 1.35 }}>{reasonLabel(reason)}</div>
    <div className="num" style={{ fontSize: 7, color: MUTED, display: 'flex', justifyContent: 'space-between' }}>
      <span>OPP {bestOpponent ?? '--'}</span>
      <span>SEG {worstSegment ?? '--'}</span>
    </div>
  </div>
);

const SegmentRow = ({ segment, selectedOpponentId }: { segment: ComparisonSegment; selectedOpponentId: number | null }) => {
  const opponent = selectedOpponentId === null
    ? null
    : segment.opponents.find((item) => item.carId === selectedOpponentId) || null;
  return (
    <div
      className="num"
      style={{
        display: 'grid',
        gridTemplateColumns: '34px 44px 42px 44px 1fr',
        gap: 6,
        alignItems: 'center',
        minHeight: 24,
        padding: '4px 6px',
        borderBottom: `1px solid ${BORDER}`,
        fontSize: 7,
        color: TEXT,
      }}
    >
      <span style={{ color: MUTED }}>{segment.segmentIndex}</span>
      <span style={{ color: deltaColor(segment.playerVsReference.deltaSeconds), fontWeight: 800 }}>
        {formatSeconds(segment.playerVsReference.deltaSeconds)}
      </span>
      <span>{formatNumber(segment.player.avgSpeedKmh, 0)}</span>
      <span style={{ color: deltaColor(opponent?.deltaToPlayerSeconds) }}>
        {formatSeconds(opponent?.deltaToPlayerSeconds)}
      </span>
      <span style={{ color: MUTED, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {opponent ? classificationLabel(opponent.classification) : reasonLabel(segment.playerVsReference.mainLossReason)}
      </span>
    </div>
  );
};

export const LiveComparisonPanel = React.memo(function LiveComparisonPanel({ active = true }: { active?: boolean }) {
  useRenderCounter('LiveComparisonPanel');
  const [microSectorCount, setMicroSectorCount] = useState(50);
  const [selectedOpponentId, setSelectedOpponentId] = useState<number | null>(null);
  const currentLapSamples = useTelemetryStore((state) => active ? state.currentLapSamples : EMPTY_FRAMES);
  const previousLapSamples = useTelemetryStore((state) => active ? state.previousLapSamples : EMPTY_FRAMES);
  const opponentHistoryByCarId = useTelemetryStore((state) => active ? state.opponentHistoryByCarId : EMPTY_OPPONENT_HISTORY);
  const opponentsMeta = useTelemetryStore((state) => active ? state.opponentsMeta : null);
  const lapDebug = useTelemetryStore((state): LapDebugState | null => active ? state.lapDebug : null);

  const analysis = useMemo(() => {
    if (!active) return {
      segments: [],
      sectors: [],
      biggestLosses: [],
      biggestGains: [],
      opponentRanking: [],
      debug: { playerSamples: 0, referenceSamples: 0, opponentsAnalyzed: 0, validMicroSectors: 0 }
    };
    return buildComparisonAnalysisFromStore({
      currentLapSamples,
      referenceLapSamples: previousLapSamples,
      opponentHistoryByCarId,
      track: opponentsMeta?.track ?? null,
      microSectorCount,
    });
  }, [active, currentLapSamples, previousLapSamples, opponentHistoryByCarId, opponentsMeta?.track, microSectorCount]);

  const opponentIds = useMemo(() => (
    Object.keys(opponentHistoryByCarId)
      .map(Number)
      .filter((carId) => Number.isFinite(carId) && carId !== 0)
      .sort((a, b) => a - b)
  ), [opponentHistoryByCarId]);
  const activeOpponentId = selectedOpponentId !== null && opponentIds.includes(selectedOpponentId)
    ? selectedOpponentId
    : (opponentIds[0] ?? null);

  const keyMessage = analysis.biggestLosses[0]?.message
    || analysis.biggestGains[0]?.message
    || (previousLapSamples.length
      ? 'Dados insuficientes para classificar perdas neste trecho.'
      : 'Aguardando volta de referencia valida do store.');
  const hasReferenceLap = Boolean(lapDebug?.previousLapValid);

  return (
    <div className="panel" style={{ height: '100%', display: 'flex', flexDirection: 'column', background: PANEL_BG, overflow: 'hidden' }}>
      <div style={{ padding: '8px 9px', borderBottom: `1px solid ${BORDER}`, display: 'flex', flexDirection: 'column', gap: 7 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <BarChart3 size={14} color={CYAN} />
            <span className="num" style={{ fontSize: 8, fontWeight: 800, color: TEXT, textTransform: 'uppercase' }}>Comparacao</span>
          </div>
          <div style={{ display: 'flex', gap: 3 }}>
            {[20, 50, 100].map((count) => (
              <button key={count} type="button" onClick={() => setMicroSectorCount(count)} style={pillStyle(microSectorCount === count)} className="num">
                {count}
              </button>
            ))}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 5 }}>
          {analysis.sectors.map((sector) => (
            <SectorCard
              key={sector.sector}
              sector={sector.sector}
              delta={sector.playerVsReferenceDeltaSeconds}
              reason={sector.mainLossReason}
              bestOpponent={sector.bestOpponentCarId}
              worstSegment={sector.worstSegmentIndex}
            />
          ))}
        </div>

        <div style={{ display: 'flex', gap: 7, alignItems: 'flex-start', border: `1px solid ${BORDER}`, background: 'rgba(34,211,238,0.035)', padding: 7, borderRadius: 4 }}>
          <AlertTriangle size={13} color={AMBER} style={{ flexShrink: 0, marginTop: 1 }} />
          <div className="num" style={{ fontSize: 8, lineHeight: 1.45, color: TEXT }}>{keyMessage}</div>
        </div>
      </div>

      <div style={{ padding: '7px 9px', borderBottom: `1px solid ${BORDER}`, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <Timer size={12} color={ROSE} />
            <span className="label" style={{ fontSize: 6 }}>PERDAS</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {(analysis.biggestLosses.length ? analysis.biggestLosses : [{ segmentIndex: '--', deltaSeconds: null, reason: null }]).slice(0, 3).map((loss, index) => (
              <div key={`${loss.segmentIndex}-${index}`} className="num" style={{ display: 'flex', justifyContent: 'space-between', gap: 5, fontSize: 7, color: TEXT }}>
                <span>SEG {loss.segmentIndex}</span>
                <span style={{ color: deltaColor(loss.deltaSeconds), fontWeight: 800 }}>{formatSeconds(loss.deltaSeconds)}</span>
              </div>
            ))}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <Trophy size={12} color={EMERALD} />
            <span className="label" style={{ fontSize: 6 }}>GANHOS</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {(analysis.biggestGains.length ? analysis.biggestGains : [{ segmentIndex: '--', deltaSeconds: null }]).slice(0, 3).map((gain, index) => (
              <div key={`${gain.segmentIndex}-${index}`} className="num" style={{ display: 'flex', justifyContent: 'space-between', gap: 5, fontSize: 7, color: TEXT }}>
                <span>SEG {gain.segmentIndex}</span>
                <span style={{ color: deltaColor(gain.deltaSeconds), fontWeight: 800 }}>{formatSeconds(gain.deltaSeconds)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ padding: '7px 9px', borderBottom: `1px solid ${BORDER}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, minWidth: 0 }}>
          <Gauge size={12} color={CYAN} />
          <span className="label" style={{ fontSize: 6 }}>OPONENTE</span>
        </div>
        <select
          className="num"
          value={activeOpponentId ?? ''}
          onChange={(event) => setSelectedOpponentId(event.target.value ? Number(event.target.value) : null)}
          style={{
            width: 84,
            height: 24,
            borderRadius: 4,
            border: `1px solid ${BORDER}`,
            background: '#08080f',
            color: TEXT,
            fontSize: 8,
            padding: '0 7px',
          }}
        >
          {opponentIds.length === 0 && <option value="">--</option>}
          {opponentIds.map((carId) => <option key={carId} value={carId}>Car {carId}</option>)}
        </select>
      </div>

      <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
        <div
          className="label"
          style={{
            display: 'grid',
            gridTemplateColumns: '34px 44px 42px 44px 1fr',
            gap: 6,
            padding: '5px 6px',
            position: 'sticky',
            top: 0,
            background: '#08080f',
            borderBottom: `1px solid ${BORDER}`,
            zIndex: 1,
            fontSize: 6,
          }}
        >
          <span>SEG</span>
          <span>D REF</span>
          <span>KMH</span>
          <span>D OPP</span>
          <span>MOTIVO</span>
        </div>
        {analysis.segments.map((segment) => (
          <SegmentRow key={segment.segmentIndex} segment={segment} selectedOpponentId={activeOpponentId} />
        ))}
      </div>

      <div style={{ borderTop: `1px solid ${BORDER}`, padding: '6px 9px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
        <div className="num" style={{ fontSize: 7, color: MUTED }}>P {analysis.debug.playerSamples} / REF {analysis.debug.referenceSamples}</div>
        <div className="num" style={{ fontSize: 7, color: MUTED, textAlign: 'right' }}>OPP {analysis.debug.opponentsAnalyzed} / VALID {analysis.debug.validMicroSectors}</div>
        <div className="num" style={{ gridColumn: '1 / -1', fontSize: 7, color: hasReferenceLap ? EMERALD : AMBER, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {hasReferenceLap ? `Reference lap ${lapDebug?.referenceLapNumber}` : 'Reference lap unavailable or incomplete'}
        </div>
      </div>
    </div>
  );
});
