import React, { useEffect, useState } from 'react';
import { Disc3, RadioTower, Route, Save, TimerReset } from 'lucide-react';
import { api } from '../api/client';
import { useTelemetryStore } from '../store/useTelemetryStore';

type RuntimePayload = {
  telemetry?: {
    playerStatus?: string;
    source?: string;
    sampleCount?: number;
  };
  opponents?: {
    status?: string;
    count?: number;
    udpPort?: number;
  };
  backend?: {
    trackState?: string;
    trackCache?: string | null;
  };
};

const Item = ({
  icon,
  label,
  value,
  active = false,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  active?: boolean;
}) => (
  <div className="live-strip-item" data-active={active ? 'true' : 'false'}>
    <span className="live-strip-icon">{icon}</span>
    <span>
      <small>{label}</small>
      <strong>{value}</strong>
    </span>
  </div>
);

export const LiveSessionStrip: React.FC<{
  onTrackKeyChange?: (trackKey: string | null) => void;
}> = ({ onTrackKeyChange }) => {
  const lapMetrics = useTelemetryStore((state) => state.lapMetrics);
  const [runtime, setRuntime] = useState<RuntimePayload | null>(null);
  const [recording, setRecording] = useState<any>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [runtimePayload, recordingPayload] = await Promise.all([
          api.getRuntimeStatus(),
          api.getRecordingStatus(),
        ]);
        if (!cancelled) {
          setRuntime(runtimePayload);
          setRecording(recordingPayload);
        }
      } catch {
        if (!cancelled) setRuntime(null);
      }
    };
    load();
    const interval = window.setInterval(load, 2500);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  const trackKey = runtime?.backend?.trackCache || null;
  useEffect(() => {
    onTrackKeyChange?.(trackKey);
  }, [onTrackKeyChange, trackKey]);

  const playerLive = runtime?.telemetry?.playerStatus === 'receiving';
  const opponentsLive = runtime?.opponents?.status === 'receiving';
  const trackReady = runtime?.backend?.trackState === 'TRACK_READY';
  const track = String(trackKey || 'Aguardando pista').replace(/[_-]+/g, ' ');
  const source = String(runtime?.telemetry?.source || 'Assetto Corsa').replace(/[_-]+/g, ' ');

  return (
    <div className="live-session-strip">
      <Item icon={<RadioTower size={14} />} label="CAPTURA PLAYER" value={playerLive ? 'RECEBENDO' : 'AGUARDANDO'} active={playerLive} />
      <Item icon={<Route size={14} />} label="PISTA" value={track} active={trackReady} />
      <Item
        icon={<Disc3 size={14} />}
        label={`OPONENTES UDP ${runtime?.opponents?.udpPort || 8765}`}
        value={opponentsLive ? `${runtime?.opponents?.count || 0} ATIVOS` : 'AGUARDANDO'}
        active={opponentsLive}
      />
      <Item icon={<TimerReset size={14} />} label="VOLTA ATUAL" value={String(lapMetrics.currentLapNumber ?? '--')} active={playerLive} />
      <Item
        icon={<Save size={14} />}
        label="GRAVAÇÃO 60 HZ"
        value={recording?.recording ? `${Number(recording.playerSamplesWritten || 0).toLocaleString()} AMOSTRAS` : 'PAUSADA'}
        active={Boolean(recording?.recording)}
      />
      <div className="live-strip-packets">
        <small>FONTE</small>
        <strong>{source}</strong>
      </div>
    </div>
  );
};
