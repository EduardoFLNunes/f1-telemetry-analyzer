import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Cable, Loader2, Power } from 'lucide-react';
import { api } from '../api/client';
import { useTelemetryStore } from '../store/useTelemetryStore';

type BackendState = 'checking' | 'online' | 'offline' | 'stopping';
type Operation = 'connect' | 'shutdown' | null;

interface SourceStatus {
  source?: string;
  sample_count?: number;
  active_reader?: string;
  track_name?: string | null;
  car_model?: string | null;
  ac_available?: boolean;
}

const sourceLabel = (source?: string) => {
  if (source === 'assetto_corsa') return 'ASSETTO LIVE';
  if (source === 'replay') return 'REPLAY';
  if (source === 'mock') return 'SAFE MODE';
  return 'NO SOURCE';
};

const sourceColor = (source?: string) => {
  if (source === 'assetto_corsa') return '#34d399';
  if (source === 'replay') return '#a78bfa';
  if (source === 'mock') return '#fbbf24';
  return '#64748b';
};

const buttonBase: React.CSSProperties = {
  height: 30,
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 7,
  padding: '0 12px',
  borderRadius: 4,
  fontSize: 9,
  fontWeight: 900,
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  cursor: 'pointer',
  transition: 'opacity 0.18s ease, border-color 0.18s ease, background 0.18s ease',
};

export const BackendControlBar: React.FC = () => {
  const clearHistory = useTelemetryStore((state) => state.clearHistory);
  const [backendState, setBackendState] = useState<BackendState>('checking');
  const [sourceStatus, setSourceStatus] = useState<SourceStatus | null>(null);
  const [operation, setOperation] = useState<Operation>(null);
  const [message, setMessage] = useState('Aguardando comando manual');

  const refreshStatus = useCallback(async (quiet = false) => {
    try {
      const data = await api.getLiveSource();
      setSourceStatus(data);
      setBackendState('online');
      if (!quiet) {
        setMessage(data.source === 'assetto_corsa' ? 'Assetto conectado' : 'Modo seguro ativo');
      }
    } catch {
      setBackendState((current) => (current === 'stopping' ? 'stopping' : 'offline'));
      setSourceStatus(null);
      if (!quiet) {
        setMessage('Backend offline');
      }
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      if (cancelled) return;
      await refreshStatus(true);
    };
    poll();
    const interval = window.setInterval(poll, 2500);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [refreshStatus]);

  const handleConnectAssetto = async () => {
    setOperation('connect');
    setMessage('Conectando Assetto');
    try {
      const data = await api.setLiveSource('assetto_corsa');
      clearHistory();
      setSourceStatus(data);
      setBackendState('online');
      setMessage('Assetto conectado');
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      setMessage(detail ? 'Assetto nao pronto' : 'Falha ao conectar');
    } finally {
      setOperation(null);
    }
  };

  const handleShutdownBackend = async () => {
    const confirmed = window.confirm('Encerrar completamente o backend?');
    if (!confirmed) return;
    setOperation('shutdown');
    setBackendState('stopping');
    setMessage('Encerrando backend');
    try {
      await api.shutdownBackend();
    } catch {
      // The request may be cut by the process shutdown. Treat that as expected.
    } finally {
      window.setTimeout(() => {
        setOperation(null);
        setBackendState('offline');
        setSourceStatus(null);
        setMessage('Backend offline');
      }, 1200);
    }
  };

  const source = sourceStatus?.source;
  const isAssetto = source === 'assetto_corsa';
  const backendOnline = backendState === 'online';
  const statusText = backendState === 'offline'
    ? 'BACKEND OFF'
    : backendState === 'stopping'
      ? 'STOPPING'
      : sourceLabel(source);
  const statusColor = backendState === 'offline'
    ? '#fb7185'
    : backendState === 'stopping'
      ? '#fbbf24'
      : sourceColor(source);
  const detailText = useMemo(() => {
    if (sourceStatus?.track_name) return sourceStatus.track_name;
    if (sourceStatus?.car_model) return sourceStatus.car_model;
    if (backendState === 'checking') return 'CHECKING';
    return `${sourceStatus?.sample_count ?? 0} samples`;
  }, [backendState, sourceStatus]);

  const connectDisabled = !backendOnline || isAssetto || operation !== null;
  const shutdownDisabled = backendState === 'offline' || operation !== null;

  return (
    <div
      className="panel"
      style={{
        height: 42,
        flexShrink: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 12,
        padding: '0 12px',
        borderLeft: 0,
        borderRight: 0,
        background: '#090914',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
        <div style={{ width: 3, height: 22, borderRadius: 2, background: statusColor, boxShadow: `0 0 12px ${statusColor}55`, flexShrink: 0 }} />
        <div style={{ minWidth: 0 }}>
          <div className="label" style={{ fontSize: 7 }}>TELEMETRY SOURCE</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, minWidth: 0 }}>
            <span className="num" style={{ color: statusColor, fontSize: 13, fontWeight: 900, whiteSpace: 'nowrap' }}>
              {statusText}
            </span>
            <span className="num" style={{ color: '#64748b', fontSize: 9, fontWeight: 800, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 240 }}>
              {detailText}
            </span>
            <span className="num" title={message} style={{ color: '#94a3b8', fontSize: 9, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 260 }}>
              {message}
            </span>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
        <button
          type="button"
          onClick={handleConnectAssetto}
          disabled={connectDisabled}
          title={isAssetto ? 'Assetto Corsa conectado' : 'Conectar ao Assetto Corsa'}
          className="num"
          style={{
            ...buttonBase,
            border: '1px solid rgba(52,211,153,0.36)',
            background: isAssetto ? 'rgba(52,211,153,0.12)' : 'rgba(52,211,153,0.05)',
            color: isAssetto ? '#34d399' : '#d1fae5',
            opacity: connectDisabled && !isAssetto ? 0.45 : 1,
            cursor: connectDisabled ? 'default' : 'pointer',
          }}
        >
          {operation === 'connect' ? <Loader2 className="backend-spin" size={13} /> : <Cable size={13} />}
          CONECTAR AC
        </button>

        <button
          type="button"
          onClick={handleShutdownBackend}
          disabled={shutdownDisabled}
          title="Encerrar completamente o backend"
          className="num"
          style={{
            ...buttonBase,
            border: '1px solid rgba(251,113,133,0.42)',
            background: 'rgba(251,113,133,0.06)',
            color: '#fecdd3',
            opacity: shutdownDisabled ? 0.45 : 1,
            cursor: shutdownDisabled ? 'default' : 'pointer',
          }}
        >
          {operation === 'shutdown' ? <Loader2 className="backend-spin" size={13} /> : <Power size={13} />}
          ENCERRAR BACKEND
        </button>
      </div>
    </div>
  );
};
