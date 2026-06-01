import React, { useEffect, useMemo, useState } from 'react';
import { Activity, Gauge, Thermometer, Wrench } from 'lucide-react';
import { api } from '../api/client';
import { useTelemetryStore } from '../store/useTelemetryStore';
import { CarPhysicsResponse, CarPhysicsTelemetry } from '../types/carPhysics';

const BORDER = 'rgba(255,255,255,0.06)';
const SURFACE = 'rgba(255,255,255,0.025)';
const TEXT = '#e2e8f0';
const MUTED = '#64748b';
const CYAN = '#22d3ee';
const EMERALD = '#34d399';
const ROSE = '#fb7185';
const AMBER = '#fbbf24';

const format = (value: number | null | undefined, digits = 1, suffix = '') => (
  value === null || value === undefined || !Number.isFinite(value) ? 'UNAVAILABLE' : `${value.toFixed(digits)}${suffix}`
);

const percent = (value: number | null | undefined) => (
  value === null || value === undefined || !Number.isFinite(value) ? 'UNAVAILABLE' : `${(value * 100).toFixed(0)}%`
);

const stateColor = (state: string | undefined) => {
  if (state === 'BRAKING') return ROSE;
  if (state === 'ACCELERATING') return EMERALD;
  if (state === 'COASTING') return AMBER;
  return MUTED;
};

const Row = ({ label, value, color = TEXT }: { label: string; value: string; color?: string }) => (
  <div className="num" style={{ display: 'flex', justifyContent: 'space-between', gap: 8, minHeight: 18, fontSize: 8, borderBottom: `1px solid ${BORDER}`, padding: '3px 0' }}>
    <span style={{ color: MUTED, textTransform: 'uppercase' }}>{label}</span>
    <span style={{ color, textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{value}</span>
  </div>
);

const ArrayRow = ({ label, values, digits = 1, suffix = '' }: { label: string; values?: Array<number | null>; digits?: number; suffix?: string }) => (
  <Row
    label={label}
    value={(values && values.length ? values : [null, null, null, null])
      .map((value) => format(value, digits, suffix).replace('UNAVAILABLE', '--'))
      .join(' / ')}
  />
);

const Section = ({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 4, padding: 8, border: `1px solid ${BORDER}`, background: SURFACE, borderRadius: 4 }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      {icon}
      <span className="label" style={{ fontSize: 6 }}>{title}</span>
    </div>
    {children}
  </div>
);

const fallbackFromFrame = (frame: ReturnType<typeof useTelemetryStore.getState>['latestFrame']): CarPhysicsTelemetry | null => {
  if (!frame) return null;
  if (frame.carPhysics) return frame.carPhysics;
  return {
    source: {
      playerPhysicsAvailable: true,
      opponentPhysicsAvailable: false,
      dataCompleteness: 'MINIMAL',
    },
    motion: {
      speedKmh: frame.speedKmh ?? frame.speed * 3.6,
      accG: {
        lateral: frame.accel_g?.x ?? null,
        longitudinal: frame.accel_g?.z ?? null,
        vertical: frame.accel_g?.y ?? null,
      },
      velocity: { x: null, y: null, z: null },
    },
    controls: {
      throttle: frame.throttle ?? null,
      brake: frame.brake ?? null,
      clutch: null,
      steerAngle: frame.steering ?? null,
      gear: frame.gear ?? null,
      rpm: (frame as any).rpm ?? null,
    },
    tyres: {
      tyreCoreTemperature: [null, null, null, null],
      tyrePressure: [null, null, null, null],
      tyreWear: [null, null, null, null],
      tyreDirtyLevel: [null, null, null, null],
      wheelSlip: [null, null, null, null],
      wheelLoad: [null, null, null, null],
      estimatedGripIndex: [null, null, null, null],
    },
    suspension: {
      suspensionTravel: [null, null, null, null],
      rideHeight: [null, null],
      camberRad: [null, null, null, null],
    },
    carState: {
      fuel: null,
      maxFuel: null,
      ballast: null,
      carDamage: [null, null, null, null, null],
      abs: null,
      tc: null,
      drs: null,
      turboBoost: null,
    },
    environment: {
      airTemp: null,
      roadTemp: null,
      surfaceGrip: null,
      airDensity: null,
    },
    inferred: {
      estimatedAccelerationState: 'UNKNOWN',
      estimatedGripLevel: 'UNKNOWN',
      estimatedMassKg: null,
      estimatedDragState: 'UNKNOWN',
    },
    availability: {
      hasRealThrottle: frame.throttle !== null && frame.throttle !== undefined,
      hasRealBrake: frame.brake !== null && frame.brake !== undefined,
      hasRealTyreData: false,
      hasRealSuspensionData: false,
      hasRealEnvironmentData: false,
      hasInferredGrip: false,
      hasInferredAccelerationState: false,
    },
  };
};

export const CarPhysicsDebugPanel: React.FC = () => {
  const latestFrame = useTelemetryStore((state) => state.latestFrame);
  const [payload, setPayload] = useState<CarPhysicsResponse | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const data = await api.getPlayerPhysics();
        if (!cancelled) {
          setPayload(data);
          setFailed(false);
        }
      } catch {
        if (!cancelled) setFailed(true);
      }
    };
    load();
    const interval = setInterval(load, 1000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const physics = useMemo(() => payload?.player ?? fallbackFromFrame(latestFrame), [payload, latestFrame]);
  const firstOpponent = payload?.opponents?.[0] ?? null;

  if (!physics) {
    return (
      <div className="panel flex h-full items-center justify-center">
        <span className="num text-[8px] text-slate-700 uppercase tracking-wider">Awaiting physics...</span>
      </div>
    );
  }

  return (
    <div className="panel" style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden', background: '#0c0c16' }}>
      <div style={{ padding: '8px 9px', borderBottom: `1px solid ${BORDER}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Activity size={14} color={CYAN} />
          <span className="num" style={{ fontSize: 8, fontWeight: 800, color: TEXT, textTransform: 'uppercase' }}>Car Physics</span>
        </div>
        <span className="num" style={{ fontSize: 8, fontWeight: 800, color: physics.source.dataCompleteness === 'FULL' ? EMERALD : physics.source.dataCompleteness === 'PARTIAL' ? AMBER : MUTED }}>
          {physics.source.dataCompleteness}
        </span>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 9, display: 'flex', flexDirection: 'column', gap: 8 }}>
        <Section icon={<Gauge size={12} color={CYAN} />} title="Motion And Controls">
          <Row label="Speed" value={format(physics.motion.speedKmh, 1, ' km/h')} color={CYAN} />
          <Row label="Throttle" value={percent(physics.controls.throttle)} color={physics.availability.hasRealThrottle ? EMERALD : MUTED} />
          <Row label="Brake" value={percent(physics.controls.brake)} color={physics.availability.hasRealBrake ? ROSE : MUTED} />
          <Row label="Gear" value={format(physics.controls.gear, 0)} />
          <Row label="RPM" value={format(physics.controls.rpm, 0)} />
          <Row label="State" value={physics.inferred.estimatedAccelerationState} color={stateColor(physics.inferred.estimatedAccelerationState)} />
          <Row label="Lat / Lon G" value={`${format(physics.motion.accG?.lateral, 2)} / ${format(physics.motion.accG?.longitudinal, 2)}`} />
        </Section>

        <Section icon={<Thermometer size={12} color={AMBER} />} title="Tyres">
          <ArrayRow label="Core Temp" values={physics.tyres.tyreCoreTemperature} suffix=" C" />
          <ArrayRow label="Pressure" values={physics.tyres.tyrePressure} digits={2} />
          <ArrayRow label="Wear" values={physics.tyres.tyreWear} digits={2} />
          <ArrayRow label="Dirty" values={physics.tyres.tyreDirtyLevel} digits={2} />
          <ArrayRow label="Slip" values={physics.tyres.wheelSlip} digits={2} />
          <ArrayRow label="Load" values={physics.tyres.wheelLoad} digits={0} />
          <Row label="Grip" value={physics.inferred.estimatedGripLevel} color={physics.availability.hasInferredGrip ? EMERALD : MUTED} />
        </Section>

        <Section icon={<Wrench size={12} color={EMERALD} />} title="Car And Environment">
          <Row label="Fuel" value={format(physics.carState.fuel, 1, ' L')} />
          <Row label="ABS / TC" value={`${format(physics.carState.abs, 0)} / ${format(physics.carState.tc, 0)}`} />
          <Row label="DRS" value={physics.carState.drs === null || physics.carState.drs === undefined ? 'UNAVAILABLE' : String(physics.carState.drs).toUpperCase()} />
          <ArrayRow label="Susp Travel" values={physics.suspension.suspensionTravel} digits={3} />
          <ArrayRow label="Ride Height" values={physics.suspension.rideHeight} digits={3} />
          <Row label="Air / Road" value={`${format(physics.environment.airTemp, 1, ' C')} / ${format(physics.environment.roadTemp, 1, ' C')}`} />
          <Row label="Surface Grip" value={format(physics.environment.surfaceGrip, 2)} />
        </Section>

        <Section icon={<Activity size={12} color={firstOpponent ? CYAN : MUTED} />} title="Opponent Physics">
          <Row label="Data" value={firstOpponent ? 'MINIMAL DATA' : 'UNAVAILABLE'} color={firstOpponent ? AMBER : MUTED} />
          <Row label="Car" value={firstOpponent ? String(firstOpponent.carId) : 'UNAVAILABLE'} />
          <Row label="Speed" value={format(firstOpponent?.physics.motion.speedKmh, 1, ' km/h')} />
          <Row label="Throttle" value="UNAVAILABLE" color={MUTED} />
          <Row label="Brake" value="UNAVAILABLE" color={MUTED} />
          <Row label="State" value={firstOpponent?.physics.inferred.estimatedAccelerationState ?? 'UNKNOWN'} color={stateColor(firstOpponent?.physics.inferred.estimatedAccelerationState)} />
        </Section>
      </div>

      <div style={{ borderTop: `1px solid ${BORDER}`, padding: '6px 9px', display: 'flex', flexDirection: 'column', gap: 2 }}>
        <div className="num" style={{ fontSize: 7, color: failed ? ROSE : MUTED }}>
          {failed ? 'Endpoint unavailable, using live frame fallback' : `Samples P ${payload?.carPhysicsDebug.playerPhysicsSamples ?? '--'} / O ${payload?.carPhysicsDebug.opponentPhysicsSamples ?? '--'}`}
        </div>
        <div className="num" style={{ fontSize: 7, color: MUTED, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          Missing: {payload?.carPhysicsDebug.missingPlayerFields.slice(0, 3).join(', ') || '--'}
        </div>
      </div>
    </div>
  );
};
