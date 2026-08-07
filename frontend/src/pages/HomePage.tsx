import React, { useCallback, useEffect, useState } from 'react';
import { Activity, ArrowRight, CheckCircle2, Clock, Gauge, LineChart, Loader2, MapPin } from 'lucide-react';
import { api } from '../api/client';
import { formatLapTime } from '../utils/lapFormat';
import type { AppPage } from '../components/AppNav';

type CaptureGate = {
  allowed?: boolean;
  reason?: string | null;
  message?: string | null;
};

type HomeState = {
  loading: boolean;
  gate: CaptureGate;
  recording: boolean;
  trackName: string | null;
  playerStatus: string | null;
  opponentsStatus: string | null;
  sessions: any[];
  sessionsError: boolean;
};

const INITIAL: HomeState = {
  loading: true,
  gate: { allowed: false, reason: null, message: null },
  recording: false,
  trackName: null,
  playerStatus: null,
  opponentsStatus: null,
  sessions: [],
  sessionsError: false,
};

function bestLapOf(session: any): number | null {
  const value = Number(session?.bestLapTime);
  return Number.isFinite(value) && value > 0 ? value : null;
}

function countLaps(session: any): number {
  const laps = Array.isArray(session?.laps) ? session.laps : [];
  return laps.length;
}

function formatWhen(value: unknown): string {
  if (typeof value !== 'string' || !value) return '--';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '--';
  return parsed.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit' });
}

function prettyTrack(value: unknown): string {
  if (typeof value !== 'string' || !value.trim()) return 'Pista desconhecida';
  return value.replace(/[_-]+/g, ' ').trim().toUpperCase();
}

type StepTone = 'done' | 'active' | 'idle';

const Step: React.FC<{
  index: number;
  tone: StepTone;
  title: string;
  hint: string;
  action?: { label: string; onClick: () => void };
}> = ({ index, tone, title, hint, action }) => (
  <div className={`home-step ${tone === 'done' ? 'home-step-done' : tone === 'active' ? 'home-step-active' : ''}`}>
    <div className="home-step-index">{tone === 'done' ? <CheckCircle2 size={12} /> : index}</div>
    <div style={{ minWidth: 0 }}>
      <div className="home-step-title">{title}</div>
      <div className="home-step-hint">{hint}</div>
    </div>
    {action && (
      <button type="button" className="home-cta home-cta-muted" onClick={action.onClick}>
        {action.label}
        <ArrowRight size={11} />
      </button>
    )}
  </div>
);

export const HomePage: React.FC<{ onNavigate: (page: AppPage) => void }> = ({ onNavigate }) => {
  const [state, setState] = useState<HomeState>(INITIAL);

  const refresh = useCallback(async () => {
    const next: Partial<HomeState> = { loading: false };

    try {
      const [runtime, recording] = await Promise.all([
        api.getRuntimeStatus().catch(() => null),
        api.getRecordingStatus().catch(() => null),
      ]);
      const capture = recording?.captureGate || runtime?.capture || {};
      next.gate = {
        allowed: Boolean(capture.allowed),
        reason: capture.reason ?? null,
        message: capture.message ?? null,
      };
      next.recording = Boolean(recording?.recording);
      next.trackName = runtime?.backend?.trackCache ?? null;
      next.playerStatus = runtime?.telemetry?.playerStatus ?? null;
      next.opponentsStatus = runtime?.opponents?.status ?? null;
    } catch {
      next.gate = { allowed: false, reason: 'backend_unreachable', message: 'Backend indisponivel.' };
    }

    try {
      const sessions = await api.getSessions(8);
      next.sessions = Array.isArray(sessions?.sessions) ? sessions.sessions : [];
      next.sessionsError = false;
    } catch {
      next.sessions = [];
      next.sessionsError = true;
    }

    setState((previous) => ({ ...previous, ...next } as HomeState));
  }, []);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      if (cancelled) return;
      await refresh();
    };
    tick();
    const timer = window.setInterval(tick, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [refresh]);

  const { gate, recording, trackName, sessions, sessionsError, loading } = state;
  const gameReady = Boolean(gate.allowed);
  const hasTrack = Boolean(trackName);

  const totalSessions = sessions.length;
  const totalLaps = sessions.reduce((sum, session) => sum + countLaps(session), 0);
  const bestLap = sessions
    .map(bestLapOf)
    .filter((value): value is number => value !== null)
    .reduce<number | null>((best, value) => (best === null || value < best ? value : best), null);

  return (
    <div className="app-page">
      {/* ── Identidade do trabalho ── */}
      <section className="panel home-hero">
        <div>
          <div className="label" style={{ marginBottom: 6 }}>Trabalho de Conclusao de Curso</div>
          <h1 className="home-hero-title">Telemetria Assistida para Simulacao Automobilistica</h1>
        </div>
        <p className="home-hero-sub">
          Captura de telemetria em tempo real do Assetto Corsa, reconstrucao da geometria real
          de Interlagos a partir dos arquivos do proprio jogo e analise assistida de pilotagem
          com base fisica &mdash; sem valores arbitrarios.
        </p>
        <div className="home-chip-row">
          {['Assetto Corsa', 'Interlagos', 'Memoria compartilhada', 'UDP oponentes', 'FastAPI', 'React', 'Electron'].map((chip) => (
            <span key={chip} className="home-chip">{chip}</span>
          ))}
        </div>
      </section>

      <div className="home-columns">
        {/* ── Estado do sistema e proximo passo ── */}
        <section className="panel home-card">
          <div>
            <div className="app-page-title">Estado da coleta</div>
            <div className="app-page-subtitle">
              A coleta so inicia com o Assetto Corsa aberto e uma sessao carregada.
            </div>
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '9px 11px',
              borderRadius: 3,
              border: `1px solid ${gameReady ? 'rgba(52,211,153,0.3)' : 'rgba(251,191,36,0.28)'}`,
              background: gameReady ? 'rgba(52,211,153,0.07)' : 'rgba(251,191,36,0.06)',
            }}
          >
            {loading ? (
              <Loader2 size={14} className="animate-spin" style={{ color: 'var(--text-3)' }} />
            ) : (
              <span
                className={gameReady ? 'status-live' : ''}
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: gameReady ? 'var(--emerald)' : 'var(--amber)',
                  flexShrink: 0,
                }}
              />
            )}
            <div style={{ minWidth: 0 }}>
              <div className="num" style={{ fontSize: 9, fontWeight: 800, textTransform: 'uppercase', color: gameReady ? 'var(--emerald)' : 'var(--amber)' }}>
                {loading ? 'Verificando...' : gameReady ? (recording ? 'Coletando telemetria' : 'Pronto para coletar') : 'Aguardando o Assetto Corsa'}
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-2)', marginTop: 2, lineHeight: 1.4 }}>
                {gameReady
                  ? 'Entre na pista para gravar voltas automaticamente.'
                  : (gate.message || 'Abra o Assetto Corsa e carregue uma sessao de pilotagem.')}
              </div>
            </div>
          </div>

          <div>
            <Step
              index={1}
              tone={gameReady ? 'done' : 'active'}
              title="Abrir o Assetto Corsa e entrar na pista"
              hint={gameReady
                ? 'Jogo detectado e memoria compartilhada disponivel.'
                : 'O sistema le a telemetria direto da memoria compartilhada do jogo.'}
            />
            <Step
              index={2}
              tone={hasTrack ? 'done' : gameReady ? 'active' : 'idle'}
              title="Carregar a geometria da pista"
              hint={hasTrack
                ? `Pista ativa: ${prettyTrack(trackName)}`
                : 'A pista e reconstruida a partir dos arquivos do proprio jogo.'}
            />
            <Step
              index={3}
              tone={recording ? 'done' : gameReady ? 'active' : 'idle'}
              title="Gravar voltas"
              hint={recording
                ? 'Gravacao em andamento; as voltas aparecem na aba Analise.'
                : 'A gravacao comeca sozinha quando a telemetria real chega.'}
              action={{ label: 'Ver pista', onClick: () => onNavigate('live') }}
            />
            <Step
              index={4}
              tone={totalLaps > 0 ? 'done' : 'idle'}
              title="Analisar a pilotagem"
              hint="Comparacao por microsetor, linha ideal e feedback assistido pos-volta."
              action={{ label: 'Analisar', onClick: () => onNavigate('analysis') }}
            />
          </div>
        </section>

        {/* ── Sessoes gravadas ── */}
        <section className="panel home-card">
          <div>
            <div className="app-page-title">Sessoes gravadas</div>
            <div className="app-page-subtitle">
              {sessionsError ? 'Nao foi possivel ler as sessoes.' : 'Ultimas sessoes persistidas em disco.'}
            </div>
          </div>

          <div className="home-stat-grid">
            <div className="home-stat">
              <div className="label" style={{ marginBottom: 3 }}>Sessoes</div>
              <div className="home-stat-value">{totalSessions || '--'}</div>
            </div>
            <div className="home-stat">
              <div className="label" style={{ marginBottom: 3 }}>Voltas</div>
              <div className="home-stat-value">{totalLaps || '--'}</div>
            </div>
            <div className="home-stat">
              <div className="label" style={{ marginBottom: 3 }}>Melhor</div>
              <div className="home-stat-value" style={{ fontSize: 14, color: bestLap ? 'var(--emerald)' : 'var(--text-1)' }}>
                {bestLap ? formatLapTime(bestLap) : '--:--.---'}
              </div>
            </div>
          </div>

          <div style={{ minHeight: 0 }}>
            {sessions.length === 0 ? (
              <div style={{ fontSize: 10, color: 'var(--text-3)', padding: '10px 0', lineHeight: 1.5 }}>
                {loading ? 'Carregando...' : 'Nenhuma sessao gravada ainda. Abra o Assetto Corsa e entre na pista.'}
              </div>
            ) : (
              sessions.slice(0, 6).map((session) => (
                <div key={session.sessionId} className="home-session-row">
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 10.5, color: 'var(--text-1)', display: 'flex', alignItems: 'center', gap: 5 }}>
                      <MapPin size={10} style={{ color: 'var(--text-3)', flexShrink: 0 }} />
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {prettyTrack(session.track)}
                      </span>
                    </div>
                    <div className="num" style={{ fontSize: 8, color: 'var(--text-3)', marginTop: 2 }}>
                      <Clock size={8} style={{ display: 'inline', marginRight: 3, verticalAlign: -1 }} />
                      {formatWhen(session.startedAt)} &middot; {countLaps(session)} voltas
                    </div>
                  </div>
                  <div className="num" style={{ fontSize: 10, color: bestLapOf(session) ? 'var(--cyan)' : 'var(--text-3)' }}>
                    {bestLapOf(session) ? formatLapTime(bestLapOf(session)) : '--'}
                  </div>
                </div>
              ))
            )}
          </div>

          <button type="button" className="home-cta" onClick={() => onNavigate('analysis')}>
            <LineChart size={12} />
            Abrir analise
          </button>
        </section>
      </div>

      {/* ── Atalhos ── */}
      <section className="panel home-card" style={{ flexDirection: 'row', gap: 10, flexWrap: 'wrap' }}>
        <button type="button" className="home-cta home-cta-muted" onClick={() => onNavigate('live')}>
          <Activity size={12} />
          Telemetria ao vivo
        </button>
        <button type="button" className="home-cta home-cta-muted" onClick={() => onNavigate('diagnostics')}>
          <Gauge size={12} />
          Diagnostico do sistema
        </button>
      </section>
    </div>
  );
};

export default HomePage;
