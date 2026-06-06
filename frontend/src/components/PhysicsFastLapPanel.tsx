import React, { useEffect, useMemo, useState } from 'react';
import { Activity, AlertTriangle, Gauge, Timer, Zap } from 'lucide-react';
import { api } from '../api/client';
import { useTelemetryStore } from '../store/useTelemetryStore';
import { PhysicsFastLapReport, PhysicsLapSegment, PhysicsLimitingFactor } from '../types/physicsFastLap';

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

const deltaColor = (value: number | null | undefined) => {
  if (value === null || value === undefined) return MUTED;
  if (value > 0.03) return ROSE;
  if (value < -0.03) return EMERALD;
  return MUTED;
};

const factorLabel = (factor: PhysicsLimitingFactor | string | null | undefined) => {
  if (factor === 'CURVATURE') return 'Curva';
  if (factor === 'BRAKING') return 'Frenagem';
  if (factor === 'ACCELERATION') return 'Aceleracao';
  if (factor === 'STRAIGHT_SPEED') return 'Reta';
  if (factor === 'DATA_LIMITED') return 'Dados limitados';
  return 'Inconclusivo';
};

const warningLabel = (warning: string) => {
  if (warning === 'physics_model_v1_simplified') return 'Modelo V1 simplificado';
  if (warning === 'uses_existing_reference_racing_line') return 'Usa a Racing Line real existente';
  if (warning === 'not_a_full_assetto_corsa_physics_simulation') return 'Nao e simulacao fisica completa';
  return warning.replaceAll('_', ' ');
};

const Stat = ({ label, value, color = TEXT }: { label: string; value: string; color?: string }) => (
  <div style={{ padding: 8, border: `1px solid ${BORDER}`, background: SURFACE, borderRadius: 4, minWidth: 0 }}>
    <div className="label" style={{ fontSize: 8, marginBottom: 4 }}>{label}</div>
    <div className="num" style={{ fontSize: 12, color, fontWeight: 900, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
      {value}
    </div>
  </div>
);

const SectorRow = ({ sector }: { sector: PhysicsFastLapReport['sectors'][number] }) => (
  <div
    className="num"
    style={{
      display: 'grid',
      gridTemplateColumns: '28px 62px 62px minmax(0, 1fr)',
      gap: 7,
      alignItems: 'center',
      minHeight: 28,
      padding: '5px 0',
      borderBottom: `1px solid ${BORDER}`,
      fontSize: 9,
      color: TEXT,
    }}
  >
    <span style={{ color: CYAN }}>S{sector.sector}</span>
    <span>{formatLapTime(sector.physicsTargetTimeSeconds)}</span>
    <span style={{ color: deltaColor(sector.deltaSeconds), fontWeight: 800 }}>{formatSeconds(sector.deltaSeconds)}</span>
    <span style={{ color: MUTED, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
      {factorLabel(sector.mainLimitingFactor)}
    </span>
  </div>
);

const LossRow = ({ segment }: { segment: PhysicsLapSegment }) => (
  <div
    className="num"
    style={{
      display: 'grid',
      gridTemplateColumns: '40px 58px 54px minmax(0, 1fr)',
      gap: 7,
      alignItems: 'center',
      minHeight: 27,
      padding: '4px 0',
      borderBottom: `1px solid ${BORDER}`,
      fontSize: 9,
      color: TEXT,
    }}
  >
    <span style={{ color: MUTED }}>M{segment.segmentIndex}</span>
    <span style={{ color: deltaColor(segment.playerVsPhysicsDeltaSeconds), fontWeight: 800 }}>
      {formatSeconds(segment.playerVsPhysicsDeltaSeconds)}
    </span>
    <span>{formatNumber(segment.physicsTargetSpeedKmh, 0)}</span>
    <span style={{ color: MUTED, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
      {factorLabel(segment.limitingFactor)}
    </span>
  </div>
);

export const PhysicsFastLapPanel = React.memo(function PhysicsFastLapPanel({
  active = true,
  microSectorCount = 50,
}: {
  active?: boolean;
  microSectorCount?: number;
}) {
  const performanceMode = useTelemetryStore((state) => state.performanceMode);
  const [report, setReport] = useState<PhysicsFastLapReport | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!active) return undefined;
    let cancelled = false;
    const load = async () => {
      try {
        const data = await api.getPhysicsFastLap(microSectorCount);
        if (!cancelled) {
          setReport(data as PhysicsFastLapReport);
          setFailed(false);
        }
      } catch {
        if (!cancelled) setFailed(true);
      }
    };
    load();
    const intervalMs = performanceMode === 'PERFORMANCE' ? 12000 : 7000;
    const interval = setInterval(load, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [active, microSectorCount, performanceMode]);

  const ready = report?.status === 'READY';
  const topLosses = useMemo(
    () => [...(report?.segments ?? [])]
      .filter((segment) => (segment.playerVsPhysicsDeltaSeconds ?? 0) > 0.03)
      .sort((a, b) => (b.playerVsPhysicsDeltaSeconds ?? 0) - (a.playerVsPhysicsDeltaSeconds ?? 0))
      .slice(0, 4),
    [report?.segments],
  );
  const message = failed
    ? 'Endpoint Physics Fast Lap indisponivel.'
    : (!report
      ? 'Aguardando modelo fisico...'
      : (ready
        ? 'Perfil de velocidade alvo gerado sobre a Racing Line existente.'
        : 'Modelo fisico aguardando uma Racing Line valida.'));

  return (
    <div style={{ border: `1px solid ${BORDER}`, background: SURFACE, borderRadius: 4, padding: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
          <Zap size={13} color={ready ? CYAN : AMBER} />
          <span className="num" style={{ fontSize: 10, fontWeight: 900, color: TEXT, textTransform: 'uppercase' }}>Physics Fast Lap</span>
        </div>
        <span className="num" style={{ fontSize: 9, color: ready ? EMERALD : AMBER, fontWeight: 900 }}>{report?.status ?? 'WAIT'}</span>
      </div>

      <div style={{ display: 'flex', gap: 6, alignItems: 'flex-start', border: `1px solid ${BORDER}`, background: ready ? 'rgba(34,211,238,0.035)' : 'rgba(251,191,36,0.035)', padding: 7, borderRadius: 4 }}>
        <AlertTriangle size={12} color={ready ? CYAN : AMBER} style={{ flexShrink: 0, marginTop: 1 }} />
        <div className="num" style={{ fontSize: 10, lineHeight: 1.45, color: TEXT }}>{message}</div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 5 }}>
        <Stat label="ALVO FISICO" value={formatLapTime(report?.summary.estimatedPhysicsLapTimeSeconds)} color={ready ? CYAN : MUTED} />
        <Stat label="REFERENCIA" value={formatLapTime(report?.summary.referenceLapTimeSeconds)} color={ready ? EMERALD : MUTED} />
        <Stat label="PILOTO X ALVO" value={formatSeconds(report?.summary.playerLossToPhysicsSeconds)} color={deltaColor(report?.summary.playerLossToPhysicsSeconds)} />
        <Stat label="PIOR SETOR" value={report?.summary.biggestLossSector ? `S${report.summary.biggestLossSector}` : '--'} />
        <Stat label="LIMITE" value={factorLabel(report?.summary.biggestLimitingFactor)} color={ready ? AMBER : MUTED} />
        <Stat label="CACHE" value={report?.debug.physicsTargetCacheHit ? 'HIT' : 'MISS'} color={report?.debug.physicsTargetCacheHit ? EMERALD : MUTED} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 5 }}>
        <Stat label="LAT G" value={formatNumber(report?.parameters.maxLateralG.value, 2)} color={CYAN} />
        <Stat label="ACEL M/S2" value={formatNumber(report?.parameters.maxAccelerationMs2.value, 1)} color={EMERALD} />
        <Stat label="FREIO M/S2" value={formatNumber(report?.parameters.maxBrakingMs2.value, 1)} color={ROSE} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 3 }}>
            <Timer size={12} color={CYAN} />
            <span className="label" style={{ fontSize: 8 }}>SETORES</span>
          </div>
          {(report?.sectors ?? [1, 2, 3].map((sector) => ({
            sector: sector as 1 | 2 | 3,
            physicsTargetTimeSeconds: null,
            playerEstimatedTimeSeconds: null,
            deltaSeconds: null,
            mainLimitingFactor: null,
          }))).map((sector) => <SectorRow key={sector.sector} sector={sector} />)}
        </div>

        <div style={{ minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 3 }}>
            <Gauge size={12} color={ROSE} />
            <span className="label" style={{ fontSize: 8 }}>TOP PERDAS</span>
          </div>
          {topLosses.length ? (
            topLosses.map((segment) => <LossRow key={segment.segmentIndex} segment={segment} />)
          ) : (
            <div className="num" style={{ fontSize: 10, color: MUTED, padding: '5px 0' }}>Sem perdas contra o alvo.</div>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
        <Activity size={12} color={MUTED} />
        {(report?.debug.warnings ?? ['physics_model_v1_simplified']).slice(0, 3).map((warning) => (
          <span key={warning} className="num" style={{ fontSize: 8, color: MUTED }}>
            {warningLabel(warning)}
          </span>
        ))}
      </div>
    </div>
  );
});
