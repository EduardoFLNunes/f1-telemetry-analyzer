import React, { useEffect, useMemo, useState } from 'react';
import { Archive, Gauge, Radio, RefreshCw, Target, XCircle } from 'lucide-react';
import { api } from '../api/client';
import { TelemetryFrame, useTelemetryStore } from '../store/useTelemetryStore';
import { formatLapTime } from '../utils/lapFormat';

type LapSummary = {
  lapId?: string;
  sessionId?: string;
  lapNumber: number;
  sampleCount: number;
  duration: number | null;
  lapTime?: number | null;
  maxSpeedKmh: number | null;
  avgSpeedKmh: number | null;
  completed: boolean;
  valid: boolean;
  acceptedByPhase13?: boolean;
  hasAssistedAnalysis?: boolean;
  canAnalyze?: boolean;
  analysisStatus?: 'AVAILABLE' | 'NOT_GENERATED' | 'NOT_ELIGIBLE';
  validationStatus?: 'VALID' | 'PARTIAL' | 'INVALID';
  reliabilityStatus?: 'VALID' | 'PARTIAL' | 'INVALID';
  issues?: string[];
};

type SessionSummary = {
  sessionId: string;
  track: string | null;
  car?: string | null;
  startedAt: string | null;
  endedAt: string | null;
  sampleRateHz: number | null;
  sampleCount: number;
  lapCount: number;
  completedLapCount: number;
  validLapCount: number;
  bestLapTime: number | null;
  indexed: boolean;
  offlineAvailable?: boolean;
  active?: boolean;
  laps: LapSummary[];
};

const numberOr = (value: unknown, fallback = 0) => {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
};

const progressOrNull = (raw: any): number | null => {
  const candidates = [
    raw?.lapProgress,
    raw?.p,
    raw?.spline_t,
    raw?.normalizedSplinePosition,
    raw?.splinePosition,
  ];
  for (const candidate of candidates) {
    const number = Number(candidate);
    if (Number.isFinite(number)) return Math.max(0, Math.min(1, number));
  }
  return null;
};

const normalizeStoredFrame = (raw: any): TelemetryFrame => {
  const mapPosition = raw?.mapPosition || {
    x: numberOr(raw?.x ?? raw?.world_x),
    y: numberOr(raw?.y ?? raw?.z ?? -(raw?.world_z ?? 0)),
  };
  const timestamp = numberOr(raw?.timestamp, Date.now());
  const lapProgress = progressOrNull(raw);
  return {
    ...raw,
    driver_id: raw?.driver_id || 'player',
    lap_number: numberOr(raw?.lap_number ?? raw?.lap),
    lap_time: numberOr(raw?.lap_time ?? raw?.lapTime),
    lapProgress,
    lapSampleTime: timestamp > 100_000_000_000 ? timestamp / 1000 : timestamp,
    s: numberOr(raw?.s ?? raw?.distanceAlongTrack),
    L: raw?.L ?? raw?.lateralOffset ?? null,
    speed: Number.isFinite(Number(raw?.speed))
      ? Number(raw.speed)
      : numberOr(raw?.speedKmh) / 3.6,
    speedKmh: Number.isFinite(Number(raw?.speedKmh))
      ? Number(raw.speedKmh)
      : numberOr(raw?.speed) * 3.6,
    throttle: numberOr(raw?.throttle),
    brake: numberOr(raw?.brake),
    steering: numberOr(raw?.steering),
    gear: numberOr(raw?.gear),
    delta: numberOr(raw?.delta),
    x: numberOr(mapPosition.x),
    y: numberOr(mapPosition.y),
    z: numberOr(mapPosition.y),
    mapPosition: { x: numberOr(mapPosition.x), y: numberOr(mapPosition.y) },
    accel_g: raw?.accel_g || { x: 0, y: 0, z: 0 },
    timestamp,
  };
};

const compactTrack = (value: string | null) => (
  (value || 'Pista desconhecida').replace(/[_-]+/g, ' ')
);

const safeLapFragment = (value: string) => (
  value.trim().replace(/[^A-Za-z0-9_.-]+/g, '_').replace(/^_+|_+$/g, '') || 'session'
);

const recordingLapId = (sessionId: string, lap: LapSummary) => (
  lap.lapId || `rec__${safeLapFragment(sessionId)}__${lap.lapNumber}`
);

const LapButton = ({
  lap,
  selected,
  loading,
  onClick,
}: {
  lap: LapSummary;
  selected: boolean;
  loading?: boolean;
  onClick: () => void;
}) => (
  <button
    type="button"
    onClick={onClick}
    className="lap-row"
    data-selected={selected ? 'true' : 'false'}
    data-valid={lap.valid ? 'true' : 'false'}
    disabled={loading || !lap.valid}
    title={!lap.valid ? (lap.issues?.join('; ') || 'Volta indisponivel para referencia') : undefined}
  >
    <span className="lap-row-number">L{lap.lapNumber}</span>
    <span className="lap-row-time">{loading ? 'CARREGANDO' : formatLapTime(lap.duration)}</span>
    <span className="lap-row-speed">{lap.maxSpeedKmh ? `${Math.round(lap.maxSpeedKmh)} km/h` : '--'}</span>
    <span className={`lap-row-state ${lap.valid ? 'is-valid' : ''}`}>
      {lap.valid ? 'VALIDA' : lap.validationStatus === 'INVALID' ? 'INVALIDA' : lap.completed ? 'PARCIAL' : 'EM CURSO'}
    </span>
  </button>
);

export const SessionLapsPanel: React.FC<{ active?: boolean; onOpenAssistedAnalysis?: () => void }> = ({
  active = true,
  onOpenAssistedAnalysis,
}) => {
  const completedLaps = useTelemetryStore((state) => state.completedLapsHistory);
  const selectedLap = useTelemetryStore((state) => state.selectedLap);
  const selectedSessionId = useTelemetryStore((state) => state.selectedSessionId);
  const setReferenceLap = useTelemetryStore((state) => state.setReferenceLap);
  const clearReferenceLap = useTelemetryStore((state) => state.clearReferenceLap);
  const setAssistedTraceContext = useTelemetryStore((state) => state.setAssistedTraceContext);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [runtimeStatus, setRuntimeStatus] = useState<any>(null);
  const [expandedSession, setExpandedSession] = useState<string | null>(null);
  const [loadingKey, setLoadingKey] = useState<string | null>(null);
  const [loadingSessionId, setLoadingSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadSessions = async () => {
    try {
      const payload = await api.getSessions(20);
      const nextSessions = Array.isArray(payload?.sessions) ? payload.sessions : [];
      setSessions(nextSessions);
      setExpandedSession((current) => (
        current || nextSessions.find((session: SessionSummary) => session.indexed)?.sessionId || null
      ));
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Sessões indisponíveis');
    }
    try {
      setRuntimeStatus(await api.getRuntimeStatus());
    } catch {
      setRuntimeStatus(null);
    }
  };

  useEffect(() => {
    if (!active) return undefined;
    loadSessions();
    const interval = window.setInterval(loadSessions, 5000);
    return () => window.clearInterval(interval);
  }, [active]);

  const liveLaps = useMemo(
    () => [...completedLaps].reverse().map((lap) => ({
      lapNumber: lap.lapNumber,
      sampleCount: lap.samples.length,
      duration: lap.duration,
      maxSpeedKmh: Math.max(...lap.samples.map((sample) => sample.speedKmh ?? sample.speed * 3.6), 0),
      avgSpeedKmh: null,
      completed: true,
      valid: lap.valid,
      samples: lap.samples,
    })),
    [completedLaps],
  );

  const chooseArchivedLap = async (session: SessionSummary, lap: LapSummary) => {
    const sessionId = session.sessionId;
    const lapNumber = lap.lapNumber;
    const key = `${sessionId}:${lapNumber}`;
    setLoadingKey(key);
    try {
      const payload = await api.getOfflineLapSamples(recordingLapId(sessionId, lap), 36_000);
      const samples = (payload?.samples || []).map(normalizeStoredFrame);
      setReferenceLap(samples, lapNumber, sessionId);
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Volta indisponível');
    } finally {
      setLoadingKey(null);
    }
  };

  const openAssistedLap = (session: SessionSummary, lap: LapSummary) => {
    const accepted = Boolean(lap.acceptedByPhase13 ?? lap.valid);
    if (!accepted) {
      setError('Volta rejeitada pela Phase 13; ASSIST usa apenas voltas validas.');
      return;
    }
    setAssistedTraceContext({
      analyzedLapId: recordingLapId(session.sessionId, lap),
      analyzedLapNumber: lap.lapNumber,
      referenceLapId: null,
      referenceLapNumber: null,
      track: session.track,
      headline: lap.hasAssistedAnalysis
        ? 'Analise assistida offline disponivel'
        : 'Volta persistida pronta para analise assistida',
    });
    setError(null);
    onOpenAssistedAnalysis?.();
  };

  const toggleSession = async (session: SessionSummary) => {
    if (expandedSession === session.sessionId) {
      setExpandedSession(null);
      return;
    }
    setExpandedSession(session.sessionId);
    if (session.indexed) return;

    setLoadingSessionId(session.sessionId);
    try {
      const payload = await api.getSessionLaps(session.sessionId);
      const indexedLaps = Array.isArray(payload?.laps) ? payload.laps : null;
      if (indexedLaps) {
        setSessions((current) => current.map((item) => (
          item.sessionId === session.sessionId
            ? { ...item, indexed: true, track: payload.track ?? item.track, car: payload.car ?? item.car, laps: indexedLaps }
            : item
        )));
      }
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Falha ao indexar sessão');
    } finally {
      setLoadingSessionId(null);
    }
  };

  const activeSession = sessions.find((session) => session.active);
  const telemetryRuntime = runtimeStatus?.telemetry || {};
  const assettoClosed = telemetryRuntime.assettoProcessRunning === false || telemetryRuntime.sharedMemoryAllowed === false;
  const assettoLabel = runtimeStatus ? (assettoClosed ? 'AC OFF' : 'AC ON') : 'LOCAL';

  return (
    <div className="session-laps-panel">
      <div className="session-laps-header">
        <div>
          <span className="eyebrow">Biblioteca da sessão</span>
          <strong>Voltas capturadas</strong>
        </div>
        <div className="session-laps-actions">
          {selectedLap !== null && (
            <button type="button" title="Voltar à referência automática" onClick={clearReferenceLap}>
              <XCircle size={13} />
            </button>
          )}
          <button type="button" title="Atualizar sessões" onClick={loadSessions}>
            <RefreshCw size={13} />
          </button>
        </div>
      </div>

      <div className="session-stat-grid">
        <div><span>Amostras</span><strong>{Number(activeSession?.sampleCount || 0).toLocaleString()}</strong></div>
        <div><span>Voltas</span><strong>{activeSession?.completedLapCount || 0}</strong></div>
        <div><span>Melhor</span><strong>{formatLapTime(activeSession?.bestLapTime ?? null)}</strong></div>
      </div>

      <div className="session-reference-card">
        <Gauge size={14} />
        <div>
          <span>Referência do comparativo</span>
          <strong>{selectedLap !== null ? `Volta ${selectedLap}` : 'Última volta válida'}</strong>
        </div>
        <small>{selectedSessionId ? 'ARQUIVO' : selectedLap !== null ? 'AO VIVO' : 'AUTO'}</small>
      </div>

      <div className="session-reference-card">
        <Archive size={14} />
        <div>
          <span>Biblioteca offline</span>
          <strong>{sessions.length ? `${sessions.length} sessoes locais` : 'Sem voltas persistidas'}</strong>
        </div>
        <small>{assettoLabel}</small>
      </div>

      <div className="session-laps-scroll">
        <section>
          <div className="session-section-title">
            <Radio size={11} />
            <span>Sessão atual</span>
            <b>{liveLaps.length}</b>
          </div>
          {liveLaps.length === 0 ? (
            <div className="session-empty">Complete uma volta para criar a primeira referência comparável.</div>
          ) : liveLaps.map((lap) => (
            <LapButton
              key={`live-${lap.lapNumber}`}
              lap={lap}
              selected={selectedSessionId === null && selectedLap === lap.lapNumber}
              onClick={() => setReferenceLap(lap.samples, lap.lapNumber, null)}
            />
          ))}
        </section>

        <section>
          <div className="session-section-title">
            <Archive size={11} />
            <span>Arquivo local</span>
            <b>{sessions.length}</b>
          </div>
          {sessions.map((session) => (
            <div className="session-card" key={session.sessionId} data-active={session.active ? 'true' : 'false'}>
              <button
                type="button"
                className="session-card-summary"
                onClick={() => toggleSession(session)}
              >
                <div>
                  <strong>{compactTrack(session.track)}</strong>
                  <span>{session.startedAt ? new Date(session.startedAt).toLocaleString('pt-BR') : session.sessionId}</span>
                </div>
                <div>
                  <strong>{formatLapTime(session.bestLapTime)}</strong>
                  <span>
                    {loadingSessionId === session.sessionId
                      ? 'INDEXANDO...'
                      : session.indexed
                        ? `${session.validLapCount}/${session.completedLapCount} válidas`
                        : 'ABRIR PARA INDEXAR'}
                  </span>
                </div>
              </button>
              {expandedSession === session.sessionId && (
                <div className="session-card-laps">
                  {session.laps.map((lap) => (
                    <div className="lap-library-row" key={`${session.sessionId}-${lap.lapNumber}`}>
                      <LapButton
                        lap={lap}
                        loading={loadingKey === `${session.sessionId}:${lap.lapNumber}`}
                        selected={selectedSessionId === session.sessionId && selectedLap === lap.lapNumber}
                        onClick={() => chooseArchivedLap(session, lap)}
                      />
                      <button
                        type="button"
                        className="lap-assist-button"
                        disabled={!(lap.acceptedByPhase13 ?? lap.valid)}
                        title={(lap.acceptedByPhase13 ?? lap.valid)
                          ? 'Abrir volta persistida no Assisted Analysis'
                          : 'Volta rejeitada pela Phase 13'}
                        onClick={() => openAssistedLap(session, lap)}
                      >
                        <Target size={10} />
                        {lap.hasAssistedAnalysis ? 'OPEN' : 'ASSIST'}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
          {sessions.length === 0 && <div className="session-empty">Nenhuma sessão gravada ainda.</div>}
        </section>
      </div>

      <div className="session-laps-footer">
        <span>{loadingKey ? 'Carregando telemetria completa...' : error || 'Persistência local contínua em JSONL'}</span>
      </div>
    </div>
  );
};
