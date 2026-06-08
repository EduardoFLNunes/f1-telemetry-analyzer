import React, { useEffect, useMemo, useState } from 'react';
import { API_BASE_URL, apiUrl } from '../config/runtime';
import { useTelemetryStore } from '../store/useTelemetryStore';

declare global {
  interface Window {
    desktopRuntime?: {
      apiBaseUrl?: string;
      wsUrl?: string;
      backendPort?: number;
      frontendDevPort?: number;
      udpOpponentsPort?: number;
      mode?: string;
      autostartEnabled?: boolean;
      phase?: string;
    };
    automobilistaDesktop?: {
      runtimeStatus?: () => Promise<DesktopRuntimeStatus>;
      backendHealth?: () => Promise<unknown>;
      phase?: string;
    };
  }
}

type DesktopRuntimeStatus = {
  autostartEnabled?: boolean;
  backendStartedByElectron?: boolean;
  backendSource?: string | null;
  backendExecutablePath?: string | null;
  backendRunnerPath?: string | null;
  backendCommand?: string | null;
  backendPid?: number | null;
  apiBaseUrl?: string;
  healthUrl?: string;
  lastBackendError?: string | null;
  healthOk?: boolean;
  healthStatusCode?: number | null;
  mode?: string;
};

type RuntimeStatus = {
  status?: string;
  backend?: {
    online?: boolean;
    trackState?: string | null;
  };
  telemetry?: {
    online?: boolean;
    sampleCount?: number | null;
    liveTrajectoryCount?: number | null;
    activeTrackReady?: boolean | null;
  };
  opponents?: {
    online?: boolean;
    count?: number | null;
    lastUpdateTimestamp?: number | null;
    udpPort?: number | null;
  };
  racingLine?: {
    available?: boolean;
  };
  coach?: {
    online?: boolean;
    eventCount?: number | null;
  };
};

const POLL_MS = 5000;

const statusColor = {
  ok: '#34d399',
  warn: '#fbbf24',
  bad: '#fb7185',
  quiet: '#64748b',
};

function numeric(value: unknown, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function runtimePorts() {
  const runtime = typeof window !== 'undefined' ? window.desktopRuntime : undefined;
  return {
    backend: numeric(runtime?.backendPort, 8000),
    frontend: numeric(runtime?.frontendDevPort, 5173),
    opponents: numeric(runtime?.udpOpponentsPort, 8765),
  };
}

function compactPath(value?: string | null): string {
  if (!value) return '--';
  return value.length > 28 ? `...${value.slice(-25)}` : value;
}

function Pill({ label, value, tone = 'quiet' }: { label: string; value: string; tone?: keyof typeof statusColor }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, minWidth: 0 }}>
      <span className="label" style={{ fontSize: 6, letterSpacing: '0.08em', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {label}
      </span>
      <span className="num" style={{ fontSize: 7, color: statusColor[tone], fontWeight: 700, textAlign: 'right', whiteSpace: 'nowrap', letterSpacing: 0 }}>
        {value}
      </span>
    </div>
  );
}

export const DesktopRuntimePanel: React.FC = () => {
  const isStreaming = useTelemetryStore((state) => state.isStreaming);
  const latestFrame = useTelemetryStore((state) => state.latestFrame);
  const opponentsMeta = useTelemetryStore((state) => state.opponentsMeta);
  const lastOpponentsUpdateAt = useTelemetryStore((state) => state.lastOpponentsUpdateAt);
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null);
  const [desktopStatus, setDesktopStatus] = useState<DesktopRuntimeStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    let controller: AbortController | null = null;

    const load = async () => {
      controller?.abort();
      controller = new AbortController();
      try {
        const desktopPayload = await window.automobilistaDesktop?.runtimeStatus?.();
        if (!cancelled && desktopPayload) setDesktopStatus(desktopPayload);
      } catch {
        if (!cancelled) setDesktopStatus(null);
      }
      try {
        const response = await fetch(apiUrl('/api/runtime/status'), { signal: controller.signal });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const payload = await response.json();
        if (cancelled) return;
        setRuntime(payload);
        setError(null);
        setUpdatedAt(Date.now());
      } catch (nextError) {
        if (cancelled || (nextError instanceof DOMException && nextError.name === 'AbortError')) return;
        setRuntime(null);
        setError(nextError instanceof Error ? nextError.message : 'offline');
        setUpdatedAt(Date.now());
      }
    };

    load();
    const interval = window.setInterval(load, POLL_MS);
    return () => {
      cancelled = true;
      controller?.abort();
      window.clearInterval(interval);
    };
  }, []);

  const ports = useMemo(runtimePorts, []);
  const healthOk = !error && runtime?.status === 'ok';
  const desktopHealthOk = desktopStatus?.healthOk ?? healthOk;
  const telemetryReceiving = isStreaming || Boolean(latestFrame) || numeric(runtime?.telemetry?.sampleCount, 0) > 0;
  const opponentsReceiving = numeric(runtime?.opponents?.count ?? opponentsMeta.count, 0) > 0
    || Boolean(lastOpponentsUpdateAt && Date.now() - lastOpponentsUpdateAt < 10000);
  const racingLineReady = Boolean(runtime?.racingLine?.available);
  const coachReady = Boolean(runtime?.coach?.online && runtime?.telemetry?.activeTrackReady);
  const trackState = runtime?.backend?.trackState || 'UNKNOWN';
  const backendSource = desktopStatus?.backendSource || (healthOk ? 'already-running' : 'unavailable');
  const autostartEnabled = desktopStatus?.autostartEnabled ?? window.desktopRuntime?.autostartEnabled ?? false;
  const startedByElectron = Boolean(desktopStatus?.backendStartedByElectron);
  const backendPath = desktopStatus?.backendExecutablePath || desktopStatus?.backendRunnerPath || desktopStatus?.backendCommand;
  const lastBackendError = desktopStatus?.lastBackendError || error;

  return (
    <div className="panel" style={{ height: '100%', padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 7, minHeight: 124, overflow: 'hidden' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
        <span className="label" style={{ color: 'var(--cyan)', fontSize: 6, letterSpacing: '0.08em' }}>Runtime</span>
        <span className="num" style={{ fontSize: 7, color: desktopHealthOk ? statusColor.ok : statusColor.bad, fontWeight: 800, letterSpacing: 0 }}>
          {desktopHealthOk ? 'ONLINE' : 'OFFLINE'}
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 4, minWidth: 0 }}>
        <Pill label="Backend" value={runtime?.backend?.online || desktopHealthOk ? 'online' : 'offline'} tone={desktopHealthOk ? 'ok' : 'bad'} />
        <Pill label="Source" value={backendSource} tone={backendSource === 'unavailable' ? 'bad' : 'ok'} />
        <Pill label="Autostart" value={autostartEnabled ? 'enabled' : 'disabled'} tone={autostartEnabled ? 'ok' : 'quiet'} />
        <Pill label="Started Here" value={startedByElectron ? 'yes' : 'no'} tone={startedByElectron ? 'ok' : 'quiet'} />
        <Pill label="Health" value={desktopHealthOk ? 'OK' : (lastBackendError || 'erro')} tone={desktopHealthOk ? 'ok' : 'bad'} />
        <Pill label="Telemetry" value={telemetryReceiving ? 'recebendo' : 'aguardando'} tone={telemetryReceiving ? 'ok' : 'warn'} />
        <Pill label="Opponents" value={opponentsReceiving ? 'recebendo' : 'aguardando'} tone={opponentsReceiving ? 'ok' : 'warn'} />
        <Pill label="Racing Line" value={racingLineReady ? 'READY' : 'INSUFFICIENT_DATA'} tone={racingLineReady ? 'ok' : 'warn'} />
        <Pill label="Coach" value={coachReady ? 'READY' : 'INSUFFICIENT_DATA'} tone={coachReady ? 'ok' : 'warn'} />
      </div>

      <div style={{ height: 1, background: 'rgba(255,255,255,0.05)' }} />

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', columnGap: 8, rowGap: 3 }}>
        <Pill label="API" value={API_BASE_URL.replace(/^https?:\/\//, '')} tone="quiet" />
        <Pill label="Track" value={trackState} tone={trackState === 'TRACK_READY' ? 'ok' : 'warn'} />
        <Pill label="Backend Port" value={String(ports.backend)} tone="quiet" />
        <Pill label="Vite Port" value={String(ports.frontend)} tone="quiet" />
        <Pill label="UDP Opp" value={String(ports.opponents)} tone="quiet" />
        <Pill label="Backend Path" value={compactPath(backendPath)} tone={backendPath ? 'quiet' : 'warn'} />
        <Pill label="Last Error" value={lastBackendError ? compactPath(lastBackendError) : '--'} tone={lastBackendError ? 'bad' : 'quiet'} />
        <Pill label="Refresh" value={updatedAt ? `${Math.max(0, Math.round((Date.now() - updatedAt) / 1000))}s` : '--'} tone="quiet" />
      </div>
    </div>
  );
};
