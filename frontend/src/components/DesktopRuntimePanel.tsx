import React, { useEffect, useMemo, useState } from 'react';
import { FolderOpen } from 'lucide-react';
import { API_BASE_URL, apiUrl } from '../config/runtime';
import { useTelemetryStore } from '../store/useTelemetryStore';
import { AssettoCorsaSetupPanel } from './AssettoCorsaSetupPanel';

type BackendStatus =
  | 'online'
  | 'offline'
  | 'starting'
  | 'already-running'
  | 'port-conflict'
  | 'health-timeout'
  | 'executable-not-found'
  | 'crashed';

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
      detectAssettoCorsa?: () => Promise<AssettoDetectionResult>;
      getAssettoPluginStatus?: () => Promise<AssettoPluginStatus>;
      openAssettoFolderPicker?: () => Promise<unknown>;
      openAssettoFolder?: (assettoPath?: string | null) => Promise<{ ok?: boolean; path?: string; error?: string | null }>;
      copyAssettoSetupInstructions?: () => Promise<{ ok?: boolean; length?: number; error?: string | null }>;
      phase?: string;
    };
    automobilistaDesktop?: {
      runtimeStatus?: () => Promise<DesktopRuntimeStatus>;
      backendHealth?: () => Promise<unknown>;
      openLogsDir?: () => Promise<{ ok?: boolean; path?: string; error?: string | null }>;
      detectAssettoCorsa?: () => Promise<AssettoDetectionResult>;
      getAssettoPluginStatus?: () => Promise<AssettoPluginStatus>;
      openAssettoFolderPicker?: () => Promise<unknown>;
      openAssettoFolder?: (assettoPath?: string | null) => Promise<{ ok?: boolean; path?: string; error?: string | null }>;
      copyAssettoSetupInstructions?: () => Promise<{ ok?: boolean; length?: number; error?: string | null }>;
      phase?: string;
    };
  }
}

export type AssettoDetectionCandidate = {
  path: string;
  exists: boolean;
  hasAssettoExecutable: boolean;
  hasAppsPythonFolder: boolean;
  confidence: 'HIGH' | 'MEDIUM' | 'LOW';
  source: 'steam-default' | 'steam-library' | 'manual' | 'unknown';
};

export type AssettoDetectionResult = {
  candidates: AssettoDetectionCandidate[];
  selectedPath: string | null;
};

export type AssettoPluginStatus = {
  assetto?: AssettoDetectionResult;
  gamePath?: string | null;
  pluginId?: string;
  pluginName?: string;
  status?: 'installed' | 'not-installed' | 'unknown';
  installed?: boolean;
  expectedPluginDir?: string | null;
  targetFiles?: Array<{ name: string; path: string; required: boolean; exists: boolean }>;
  source?: {
    available?: boolean;
    path?: string | null;
    files?: Array<{ name: string; path: string; required: boolean; exists: boolean }>;
  };
  canInstall?: boolean;
  transport?: {
    playerTelemetry?: string;
    opponents?: string;
    host?: string;
    backendApiPort?: number;
    udpOpponentsPort?: number;
    websocketPath?: string;
  };
  instructions?: string;
};

type DesktopRuntimeStatus = {
  autostartEnabled?: boolean;
  backendStartedByElectron?: boolean;
  backendSource?: string | null;
  backendExecutablePath?: string | null;
  backendRunnerPath?: string | null;
  backendCommand?: string | null;
  backendPid?: number | null;
  backendStatus?: BackendStatus;
  backendStatusMessage?: string | null;
  backendPort?: number | null;
  backendResourceRoot?: string | null;
  backendRuntimeRoot?: string | null;
  frontendIndexPath?: string | null;
  logsDir?: string | null;
  apiBaseUrl?: string;
  healthUrl?: string;
  portConflict?: boolean;
  portConflictMessage?: string | null;
  lastBackendError?: string | null;
  healthOk?: boolean;
  healthStatusCode?: number | null;
  mode?: string;
  packaged?: boolean;
};

type RuntimeStatus = {
  status?: string;
  backend?: {
    online?: boolean;
    trackState?: string | null;
    resourceRoot?: string | null;
    runtimeRoot?: string | null;
  };
  telemetry?: {
    online?: boolean;
    playerSource?: string | null;
    sampleCount?: number | null;
    liveTrajectoryCount?: number | null;
    activeTrackReady?: boolean | null;
    playerStatus?: 'receiving' | 'waiting' | 'stale' | 'unknown';
    lastPlayerSampleAt?: string | null;
    secondsSinceLastPlayerSample?: number | null;
  };
  opponents?: {
    online?: boolean;
    source?: string | null;
    enabled?: boolean;
    count?: number | null;
    lastUpdateTimestamp?: number | null;
    udpPort?: number | null;
    status?: 'receiving' | 'waiting' | 'stale' | 'unknown';
    lastOpponentSampleAt?: string | null;
    secondsSinceLastOpponentSample?: number | null;
  };
  racingLine?: {
    available?: boolean;
    status?: 'READY' | 'INSUFFICIENT_DATA' | 'UNKNOWN';
  };
  coach?: {
    online?: boolean;
    eventCount?: number | null;
    status?: 'READY' | 'INSUFFICIENT_DATA' | 'UNKNOWN';
  };
};

const POLL_MS = 4000;

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

function compactPath(value?: string | null, max = 34): string {
  if (!value) return '--';
  return value.length > max ? `...${value.slice(-(max - 3))}` : value;
}

function statusTone(status: BackendStatus, healthOk: boolean): keyof typeof statusColor {
  if (healthOk || status === 'online' || status === 'already-running') return 'ok';
  if (status === 'starting') return 'warn';
  if (status === 'offline') return 'warn';
  return 'bad';
}

function statusLabel(status: BackendStatus): string {
  return status.replace(/-/g, ' ').toUpperCase();
}

function friendlyMessage(status: BackendStatus, port: number, error?: string | null): string {
  if (status === 'online' || status === 'already-running') return 'Backend online. API local respondendo normalmente.';
  if (status === 'starting') return 'Backend iniciando. Aguardando health check local.';
  if (status === 'port-conflict') return `Porta ${port} ocupada por outro processo. Feche o processo ou altere a porta configurada.`;
  if (status === 'executable-not-found') return 'Backend empacotado nao encontrado nos resources do aplicativo.';
  if (status === 'health-timeout') return 'Backend iniciou, mas nao respondeu ao health check dentro do tempo esperado.';
  if (status === 'crashed') return 'Backend parou durante o uso. Consulte os logs locais.';
  return error || 'Backend offline. O app esta aberto, mas a API local ainda nao respondeu.';
}

function Pill({ label, value, tone = 'quiet' }: { label: string; value: string; tone?: keyof typeof statusColor }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, minWidth: 0 }} title={`${label}: ${value}`}>
      <span className="label" style={{ fontSize: 6, letterSpacing: 0, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {label}
      </span>
      <span className="num" style={{ fontSize: 7, color: statusColor[tone], fontWeight: 700, textAlign: 'right', whiteSpace: 'nowrap', letterSpacing: 0, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}>
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
  const [logsOpenError, setLogsOpenError] = useState<string | null>(null);
  const [view, setView] = useState<'runtime' | 'assetto'>('runtime');

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
  const backendPort = numeric(desktopStatus?.backendPort, ports.backend);
  const healthOk = !error && runtime?.status === 'ok';
  const desktopHealthOk = desktopStatus?.healthOk ?? healthOk;
  const backendStatus: BackendStatus = desktopStatus?.backendStatus || (desktopHealthOk ? 'online' : 'offline');
  const backendTone = statusTone(backendStatus, desktopHealthOk);
  const telemetryState = runtime?.telemetry?.playerStatus || (telemetryReceivingFallback() ? 'receiving' : 'waiting');
  function telemetryReceivingFallback() {
    return isStreaming || Boolean(latestFrame) || numeric(runtime?.telemetry?.sampleCount, 0) > 0;
  }
  const telemetryReceiving = telemetryState === 'receiving' || telemetryReceivingFallback();
  const opponentsState = runtime?.opponents?.status;
  const opponentsReceiving = opponentsState === 'receiving'
    || numeric(runtime?.opponents?.count ?? opponentsMeta.count, 0) > 0
    || Boolean(lastOpponentsUpdateAt && Date.now() - lastOpponentsUpdateAt < 10000);
  const racingLineReady = runtime?.racingLine?.status === 'READY' || Boolean(runtime?.racingLine?.available);
  const coachReady = runtime?.coach?.status === 'READY' || Boolean(runtime?.coach?.online && runtime?.telemetry?.activeTrackReady);
  const trackState = runtime?.backend?.trackState || 'UNKNOWN';
  const backendSource = desktopStatus?.backendSource || (healthOk ? 'already-running' : 'unavailable');
  const autostartEnabled = desktopStatus?.autostartEnabled ?? window.desktopRuntime?.autostartEnabled ?? false;
  const startedByElectron = Boolean(desktopStatus?.backendStartedByElectron);
  const backendPath = desktopStatus?.backendExecutablePath || desktopStatus?.backendRunnerPath || desktopStatus?.backendCommand;
  const resourceRoot = desktopStatus?.backendResourceRoot || runtime?.backend?.resourceRoot;
  const runtimeRoot = desktopStatus?.backendRuntimeRoot || runtime?.backend?.runtimeRoot;
  const logsDir = desktopStatus?.logsDir;
  const lastBackendError = desktopStatus?.portConflictMessage || desktopStatus?.lastBackendError || error || logsOpenError;
  const message = friendlyMessage(backendStatus, backendPort, lastBackendError || desktopStatus?.backendStatusMessage);

  const openLogs = async () => {
    setLogsOpenError(null);
    const result = await window.automobilistaDesktop?.openLogsDir?.();
    if (result && result.ok === false) setLogsOpenError(result.error || 'Falha ao abrir logs');
  };

  return (
    <div className="panel" style={{ height: '100%', padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 6, minHeight: 124, overflow: 'hidden' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
        <div style={{ display: 'flex', gap: 2, minWidth: 0 }}>
          {(['runtime', 'assetto'] as const).map((item) => (
            <button
              key={item}
              type="button"
              className="num"
              onClick={() => setView(item)}
              style={{
                height: 20,
                padding: '0 7px',
                border: '1px solid rgba(34, 211, 238, 0.18)',
                background: view === item ? 'rgba(34, 211, 238, 0.12)' : 'rgba(15, 23, 42, 0.34)',
                color: view === item ? 'var(--cyan)' : '#64748b',
                fontSize: 7,
                fontWeight: 800,
                letterSpacing: 0,
                textTransform: 'uppercase',
                cursor: 'pointer',
              }}
            >
              {item === 'runtime' ? 'Runtime' : 'Assetto'}
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
          <span className="num" style={{ fontSize: 7, color: statusColor[backendTone], fontWeight: 800, letterSpacing: 0, whiteSpace: 'nowrap' }}>
            {statusLabel(backendStatus)}
          </span>
          <button
            type="button"
            title={logsDir ? `Abrir logs: ${logsDir}` : 'Abrir pasta de logs'}
            aria-label="Abrir pasta de logs"
            onClick={openLogs}
            disabled={!window.automobilistaDesktop?.openLogsDir}
            style={{
              width: 20,
              height: 20,
              display: 'grid',
              placeItems: 'center',
              border: '1px solid rgba(34, 211, 238, 0.28)',
              background: 'rgba(15, 23, 42, 0.66)',
              color: 'var(--cyan)',
              opacity: window.automobilistaDesktop?.openLogsDir ? 1 : 0.35,
              cursor: window.automobilistaDesktop?.openLogsDir ? 'pointer' : 'default',
            }}
          >
            <FolderOpen size={12} strokeWidth={1.8} />
          </button>
        </div>
      </div>

      {view === 'assetto' ? (
        <AssettoCorsaSetupPanel />
      ) : (
        <>
      <div className="num" title={message} style={{ fontSize: 7, lineHeight: 1.25, color: statusColor[backendTone], minHeight: 18, overflow: 'hidden' }}>
        {message}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', columnGap: 8, rowGap: 3, minWidth: 0 }}>
        <Pill label="Backend" value={desktopHealthOk ? 'online' : 'offline'} tone={desktopHealthOk ? 'ok' : backendTone} />
        <Pill label="Source" value={backendSource} tone={backendSource === 'unavailable' ? 'bad' : 'ok'} />
        <Pill label="Autostart" value={autostartEnabled ? 'enabled' : 'disabled'} tone={autostartEnabled ? 'ok' : 'quiet'} />
        <Pill label="Started Here" value={startedByElectron ? 'yes' : 'no'} tone={startedByElectron ? 'ok' : 'quiet'} />
        <Pill label="Health" value={desktopHealthOk ? 'OK' : (desktopStatus?.healthStatusCode ? `HTTP ${desktopStatus.healthStatusCode}` : 'waiting')} tone={desktopHealthOk ? 'ok' : backendTone} />
        <Pill label="API" value={(desktopStatus?.apiBaseUrl || API_BASE_URL).replace(/^https?:\/\//, '')} tone="quiet" />
        <Pill label="Track" value={trackState} tone={trackState === 'TRACK_READY' ? 'ok' : 'warn'} />
        <Pill label="Backend Port" value={String(backendPort)} tone={desktopStatus?.portConflict ? 'bad' : 'quiet'} />
        <Pill label="Telemetry" value={telemetryReceiving ? telemetryState : 'waiting'} tone={telemetryReceiving ? 'ok' : 'warn'} />
        <Pill label="Opponents" value={opponentsReceiving ? (opponentsState || 'receiving') : 'waiting'} tone={opponentsReceiving ? 'ok' : 'warn'} />
        <Pill label="Player Source" value={runtime?.telemetry?.playerSource || 'shared_memory'} tone="ok" />
        <Pill label="Opp Source" value={runtime?.opponents?.source || 'udp'} tone={runtime?.opponents?.enabled === false ? 'warn' : 'ok'} />
        <Pill label="Racing Line" value={racingLineReady ? 'READY' : 'INSUFFICIENT'} tone={racingLineReady ? 'ok' : 'warn'} />
        <Pill label="Coach" value={coachReady ? 'READY' : 'INSUFFICIENT'} tone={coachReady ? 'ok' : 'warn'} />
      </div>

      <div style={{ height: 1, background: 'rgba(255,255,255,0.05)' }} />

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', columnGap: 8, rowGap: 3, minWidth: 0 }}>
        <Pill label="Resource Root" value={compactPath(resourceRoot)} tone={resourceRoot ? 'quiet' : 'warn'} />
        <Pill label="Runtime Root" value={compactPath(runtimeRoot)} tone={runtimeRoot ? 'quiet' : 'warn'} />
        <Pill label="Logs" value={compactPath(logsDir)} tone={logsDir ? 'quiet' : 'warn'} />
        <Pill label="Backend Path" value={compactPath(backendPath)} tone={backendPath ? 'quiet' : 'warn'} />
        <Pill label="Last Error" value={lastBackendError ? compactPath(lastBackendError) : '--'} tone={lastBackendError ? 'bad' : 'quiet'} />
        <Pill label="Refresh" value={updatedAt ? `${Math.max(0, Math.round((Date.now() - updatedAt) / 1000))}s` : '--'} tone="quiet" />
      </div>
        </>
      )}
    </div>
  );
};
