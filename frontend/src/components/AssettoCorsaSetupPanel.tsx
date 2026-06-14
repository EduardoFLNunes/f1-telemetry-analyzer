import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Clipboard, FolderOpen, RefreshCw, Search } from 'lucide-react';
import { apiUrl } from '../config/runtime';

type Tone = 'ok' | 'warn' | 'bad' | 'quiet';

type RuntimeStatus = {
  status?: string;
  telemetry?: {
    source?: string | null;
    playerSource?: string | null;
    playerStatus?: 'receiving' | 'waiting' | 'stale' | 'unknown';
    secondsSinceLastPlayerSample?: number | null;
  };
  opponents?: {
    source?: string | null;
    enabled?: boolean;
    status?: 'receiving' | 'waiting' | 'stale' | 'unknown';
    secondsSinceLastOpponentSample?: number | null;
    udpPort?: number | null;
  };
};

type AssettoPluginStatus = {
  gamePath?: string | null;
  status?: 'installed' | 'not-installed' | 'unknown';
  expectedPluginDir?: string | null;
  source?: {
    available?: boolean;
    path?: string | null;
  };
  transport?: {
    backendApiPort?: number;
    udpOpponentsPort?: number;
  };
  instructions?: string;
};

const POLL_MS = 4000;

const statusColor: Record<Tone, string> = {
  ok: '#34d399',
  warn: '#fbbf24',
  bad: '#fb7185',
  quiet: '#64748b',
};

function desktopBridge() {
  return window.automobilistaDesktop || window.desktopRuntime;
}

function compactPath(value?: string | null, max = 35): string {
  if (!value) return '--';
  return value.length > max ? `...${value.slice(-(max - 3))}` : value;
}

function statusTone(value?: string | null): Tone {
  if (value === 'installed' || value === 'receiving' || value === 'online' || value === 'ready') return 'ok';
  if (value === 'not-installed' || value === 'waiting' || value === 'stale' || value === 'missing') return 'warn';
  if (value === 'offline' || value === 'error') return 'bad';
  return 'quiet';
}

function ageText(value?: number | null): string {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return '--';
  return `${Math.max(0, Math.round(Number(value)))}s`;
}

function iconButtonStyle(enabled: boolean): React.CSSProperties {
  return {
    width: 22,
    height: 22,
    display: 'grid',
    placeItems: 'center',
    border: '1px solid rgba(34, 211, 238, 0.26)',
    background: enabled ? 'rgba(15, 23, 42, 0.72)' : 'rgba(15, 23, 42, 0.34)',
    color: 'var(--cyan)',
    opacity: enabled ? 1 : 0.35,
    cursor: enabled ? 'pointer' : 'default',
  };
}

function Row({ label, value, tone = 'quiet' }: { label: string; value: string; tone?: Tone }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, minWidth: 0 }} title={`${label}: ${value}`}>
      <span className="label" style={{ fontSize: 6, letterSpacing: 0, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {label}
      </span>
      <span className="num" style={{ fontSize: 7, color: statusColor[tone], fontWeight: 800, textAlign: 'right', whiteSpace: 'nowrap', letterSpacing: 0, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {value}
      </span>
    </div>
  );
}

export const AssettoCorsaSetupPanel: React.FC = () => {
  const [plugin, setPlugin] = useState<AssettoPluginStatus | null>(null);
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);

  const bridge = useMemo(desktopBridge, []);

  const load = useCallback(async () => {
    try {
      const pluginStatus = await bridge?.getAssettoPluginStatus?.();
      setPlugin((pluginStatus || null) as AssettoPluginStatus | null);
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Assetto diagnostics unavailable');
      setPlugin(null);
    }

    try {
      const response = await fetch(apiUrl('/api/runtime/status'));
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setRuntime(await response.json());
    } catch {
      setRuntime(null);
    }
    setUpdatedAt(Date.now());
  }, [bridge]);

  useEffect(() => {
    load();
    const interval = window.setInterval(load, POLL_MS);
    return () => window.clearInterval(interval);
  }, [load]);

  const browse = async () => {
    setActionMessage(null);
    await bridge?.openAssettoFolderPicker?.();
    await load();
  };

  const openFolder = async () => {
    setActionMessage(null);
    const result = await bridge?.openAssettoFolder?.(plugin?.gamePath || null);
    if (result && result.ok === false) setActionMessage(result.error || 'Folder open failed');
  };

  const copyInstructions = async () => {
    setActionMessage(null);
    try {
      if (bridge?.copyAssettoSetupInstructions) {
        await bridge.copyAssettoSetupInstructions();
      } else if (plugin?.instructions && navigator.clipboard) {
        await navigator.clipboard.writeText(plugin.instructions);
      }
      setActionMessage('Instructions copied');
    } catch (nextError) {
      setActionMessage(nextError instanceof Error ? nextError.message : 'Copy failed');
    }
  };

  const gameDetected = Boolean(plugin?.gamePath);
  const pluginStatus = plugin?.status || 'unknown';
  const backendStatus = runtime?.status === 'ok' ? 'online' : 'offline';
  const telemetryStatus = runtime?.telemetry?.playerStatus || 'unknown';
  const opponentsStatus = runtime?.opponents?.status || 'unknown';
  const playerSource = runtime?.telemetry?.playerSource || 'shared_memory';
  const opponentsSource = runtime?.opponents?.source || 'udp';
  const sourceStatus = plugin?.source?.available ? 'ready' : 'missing';
  const ports = `${plugin?.transport?.backendApiPort || 8000}/${plugin?.transport?.udpOpponentsPort || runtime?.opponents?.udpPort || 8765}`;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minHeight: 0, overflow: 'hidden' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
        <span className="label" style={{ color: 'var(--cyan)', fontSize: 6, letterSpacing: 0 }}>Assetto Setup</span>
        <div style={{ display: 'flex', gap: 4 }}>
          <button type="button" title="Procurar pasta do Assetto Corsa" aria-label="Procurar pasta do Assetto Corsa" onClick={browse} disabled={!bridge?.openAssettoFolderPicker} style={iconButtonStyle(Boolean(bridge?.openAssettoFolderPicker))}>
            <Search size={12} strokeWidth={1.9} />
          </button>
          <button type="button" title="Abrir pasta detectada" aria-label="Abrir pasta detectada" onClick={openFolder} disabled={!gameDetected || !bridge?.openAssettoFolder} style={iconButtonStyle(Boolean(gameDetected && bridge?.openAssettoFolder))}>
            <FolderOpen size={12} strokeWidth={1.9} />
          </button>
          <button type="button" title="Copiar instrucoes de instalacao" aria-label="Copiar instrucoes de instalacao" onClick={copyInstructions} disabled={!plugin?.instructions} style={iconButtonStyle(Boolean(plugin?.instructions))}>
            <Clipboard size={12} strokeWidth={1.9} />
          </button>
          <button type="button" title="Validar plugin" aria-label="Validar plugin" onClick={load} style={iconButtonStyle(true)}>
            <RefreshCw size={12} strokeWidth={1.9} />
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', columnGap: 8, rowGap: 3, minWidth: 0 }}>
        <Row label="Assetto Corsa" value={gameDetected ? 'detected' : 'not found'} tone={gameDetected ? 'ok' : 'warn'} />
        <Row label="Plugin" value={pluginStatus} tone={statusTone(pluginStatus)} />
        <Row label="Backend" value={backendStatus} tone={statusTone(backendStatus)} />
        <Row label="Telemetry" value={telemetryStatus} tone={statusTone(telemetryStatus)} />
        <Row label="Opponents" value={opponentsStatus} tone={statusTone(opponentsStatus)} />
        <Row label="Player Source" value={playerSource} tone="ok" />
        <Row label="Opp Source" value={opponentsSource} tone={runtime?.opponents?.enabled === false ? 'warn' : 'ok'} />
        <Row label="Source Files" value={sourceStatus} tone={statusTone(sourceStatus)} />
        <Row label="Player Age" value={ageText(runtime?.telemetry?.secondsSinceLastPlayerSample)} tone={telemetryStatus === 'receiving' ? 'ok' : 'warn'} />
        <Row label="Opp Age" value={ageText(runtime?.opponents?.secondsSinceLastOpponentSample)} tone={opponentsStatus === 'receiving' ? 'ok' : 'warn'} />
        <Row label="Ports API/UDP" value={ports} tone="quiet" />
        <Row label="Refresh" value={updatedAt ? `${Math.max(0, Math.round((Date.now() - updatedAt) / 1000))}s` : '--'} tone="quiet" />
      </div>

      <div style={{ height: 1, background: 'rgba(255,255,255,0.05)' }} />

      <div style={{ display: 'grid', gridTemplateColumns: '1fr', rowGap: 3, minWidth: 0 }}>
        <Row label="Game Path" value={compactPath(plugin?.gamePath)} tone={gameDetected ? 'quiet' : 'warn'} />
        <Row label="Plugin Path" value={compactPath(plugin?.expectedPluginDir)} tone={pluginStatus === 'installed' ? 'ok' : 'warn'} />
        <Row label="Bundled Source" value={compactPath(plugin?.source?.path)} tone={plugin?.source?.available ? 'quiet' : 'warn'} />
      </div>

      <div className="num" style={{ fontSize: 7, lineHeight: 1.25, color: error ? statusColor.bad : actionMessage ? statusColor.ok : statusColor.quiet, minHeight: 9, overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }} title={error || actionMessage || ''}>
        {error || actionMessage || (pluginStatus === 'not-installed' ? 'Manual install pending' : 'Diagnostics ready')}
      </div>
    </div>
  );
};
