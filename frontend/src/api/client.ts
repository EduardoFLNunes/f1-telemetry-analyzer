import axios, { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { API_BASE_URL } from '../config/runtime';

type RequestMetadata = { startedAt: number };
type ConfigWithMetadata = InternalAxiosRequestConfig & { metadata?: RequestMetadata };

const BASE_URL = API_BASE_URL;

const client = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

function perfTarget(): Record<string, any> | null {
  if (typeof window === 'undefined') return null;
  window.__telemetryPerf = window.__telemetryPerf || {};
  return window.__telemetryPerf;
}

function nowMs(): number {
  return typeof performance !== 'undefined' && performance.now ? performance.now() : Date.now();
}

function payloadKbFromResponse(response?: AxiosResponse | null): number {
  const headerValue = response?.headers?.['content-length'];
  const headerNumber = Number(headerValue);
  if (Number.isFinite(headerNumber) && headerNumber >= 0) {
    return headerNumber / 1024;
  }
  try {
    return JSON.stringify(response?.data ?? '').length / 1024;
  } catch {
    return 0;
  }
}

function recordHttpPerf(config?: ConfigWithMetadata, status: 'success' | 'error' = 'success', response: AxiosResponse | null = null) {
  const metrics = perfTarget();
  if (!metrics || !config?.metadata?.startedAt) return;
  const duration = nowMs() - config.metadata.startedAt;
  const payloadKb = response ? payloadKbFromResponse(response) : 0;
  metrics.httpRequests = (metrics.httpRequests || 0) + 1;
  metrics.httpDurationMs = (metrics.httpDurationMs || 0) + duration;
  metrics.httpPayloadKb = (metrics.httpPayloadKb || 0) + payloadKb;
  metrics.httpErrors = (metrics.httpErrors || 0) + (status === 'error' ? 1 : 0);
  metrics.httpEndpoints = metrics.httpEndpoints || {};
  const key = config.url || 'unknown';
  const endpoint = metrics.httpEndpoints[key] || { count: 0, durationMs: 0, errors: 0, payloadKb: 0, lastPayloadKb: 0 };
  endpoint.count += 1;
  endpoint.durationMs += duration;
  endpoint.payloadKb += payloadKb;
  endpoint.lastPayloadKb = payloadKb;
  endpoint.errors += status === 'error' ? 1 : 0;
  metrics.httpEndpoints[key] = endpoint;
  if (key.includes('/api/live/telemetry')) metrics.telemetryPayloadKb = payloadKb;
  if (key.includes('/api/live/racing-line')) metrics.racingLinePayloadKb = payloadKb;
}

client.interceptors.request.use((config: ConfigWithMetadata) => {
  config.metadata = { ...(config.metadata || {}), startedAt: nowMs() };
  return config;
});

client.interceptors.response.use(
  (response: AxiosResponse) => {
    recordHttpPerf(response.config as ConfigWithMetadata, 'success', response);
    return response;
  },
  (error: AxiosError) => {
    recordHttpPerf(error.config as ConfigWithMetadata | undefined, 'error');
    return Promise.reject(error);
  },
);

type RacingLineOptions = {
  includeVisualLine?: boolean;
  includeComparison?: boolean;
};

export const api = {
  // ─── Track / Telemetry ───────────────────────────────────────────────────
  getTrackGeometry: async (): Promise<any> => (await client.get('/api/track/geometry')).data,
  /** Curto de propósito: enquanto o backend sobe, cada tentativa falha rápido e o hero mostra a espera real. */
  getHealth: async (timeoutMs = 2500): Promise<any> => (await client.get('/api/health', { timeout: timeoutMs })).data,
  getRuntimeStatus: async (): Promise<any> => (await client.get('/api/runtime/status')).data,
  getDataQuality: async (): Promise<any> => (await client.get('/api/validation/data-quality')).data,
  getRacingLine: async (microSectors = 50, options: RacingLineOptions = {}): Promise<any> => (
    await client.get('/api/live/racing-line', {
      params: {
        microSectors,
        includeVisualLine: options.includeVisualLine,
        includeComparison: options.includeComparison,
      },
    })
  ).data,
  getPlayerPhysics: async (): Promise<any> => (await client.get('/api/live/player-physics')).data,
  getRecordingStatus: async (): Promise<any> => (await client.get('/api/recording/status')).data,
  getSessions: async (limit = 30): Promise<any> => (await client.get('/api/sessions', { params: { limit } })).data,
  getSessionLaps: async (sessionId: string): Promise<any> => (
    await client.get(`/api/sessions/${encodeURIComponent(sessionId)}/laps`)
  ).data,
  getOfflineLapReplay: async (lapId: string, maxSamples = 36_000): Promise<any> => (
    await client.get(`/api/laps/${encodeURIComponent(lapId)}/replay`, { params: { maxSamples } })
  ).data,
  /** Everything the coach would have said over a recorded lap. */
  getLapCoaching: async (lapId: string): Promise<any> => {
    const res = await client.get(`/api/analysis/coach/lap/${encodeURIComponent(lapId)}`);
    return res.data;
  },
  // ─── Coleta de dados (pedido 28) ──────────────────────────────────────────
  getColetaRequisitos: async (): Promise<any> => (await client.get('/api/coleta/requisitos')).data,
  getColetaAntes: async (): Promise<any> => (await client.get('/api/coleta/antes', { timeout: 60_000 })).data,
  getColetaAoVivo: async (): Promise<any> => (await client.get('/api/coleta/ao-vivo')).data,
  putColetaConfiguracao: async (changes: Record<string, unknown>): Promise<any> => (
    await client.put('/api/coleta/configuracao', changes, { timeout: 30_000 })
  ).data,
  getColetaSessaoAtual: async (): Promise<any> => (await client.get('/api/coleta/sessao-atual')).data,
  listColetaVerificacoes: async (): Promise<any> => (await client.get('/api/coleta/verificacoes')).data,
  getColetaVerificacao: async (sessionId: string): Promise<any> => (
    await client.get(`/api/coleta/verificacoes/${encodeURIComponent(sessionId)}`)
  ).data,
  conferirSessao: async (sessionId: string): Promise<any> => (
    await client.post(`/api/coleta/verificacoes/${encodeURIComponent(sessionId)}`)
  ).data,
  getColetaM1Oficial: async (): Promise<any> => (await client.get('/api/coleta/m1/oficial', { timeout: 60_000 })).data,
  // ─── Pedido 31: o rádio do engenheiro e a volta ao vivo ───────────────────
  getRadioMensagens: async (desde: number, instancia: string | null): Promise<any> => (
    await client.get('/api/radio/mensagens', { params: { desde, ...(instancia ? { instancia } : {}) } })
  ).data,
  postRadioTeste: async (): Promise<any> => (await client.post('/api/radio/teste', null, { timeout: 45_000 })).data,
  getRadioEstado: async (): Promise<any> => (await client.get('/api/radio/estado', { timeout: 30_000 })).data,
  /** Pedido 35: só os pontos novos da volta ao vivo (a volta inteira numa volta nova). */
  getLiveVoltaNovos: async (versao: number | null, desde: number | null): Promise<any> =>
    (await client.get('/api/live/volta/novos', { params: { versao: versao ?? undefined, desde: desde ?? undefined }, timeout: 2_000 })).data,
  /** Pedido 36: os dados do replay da curva de uma mensagem (`/api/radio/replay/<id>`). */
  getRadioReplay: async (caminho: string): Promise<any> => (await client.get(caminho, { timeout: 10_000 })).data,
  /** O endereço completo do áudio de uma mensagem (`/api/radio/audio/<id>`). */
  urlDoAudio: (caminho: string): string => `${BASE_URL}${caminho}`,
  // ─── Pedido 32: o botão do coach e a anotação de sessão ────────────────────
  getCoachRodada: async (): Promise<any> => (await client.get('/api/coleta/coach/rodada', { timeout: 15_000 })).data,
  postCoachRodada: async (): Promise<any> => (await client.post('/api/coleta/coach/rodada', null, { timeout: 30_000 })).data,
  getColetaAnotacoes: async (): Promise<any> => (await client.get('/api/coleta/anotacoes')).data,
  postColetaAnotacao: async (sessionId: string): Promise<any> => (
    await client.post(`/api/coleta/anotacoes/${encodeURIComponent(sessionId)}`, null, { timeout: 30_000 })
  ).data,

  // ─── Ao vivo (pedido 29) ──────────────────────────────────────────────────
  /** As frases recentes do coach, a mais nova primeiro (as 20 últimas de uma fila de 50). */
  getLiveCoach: async (): Promise<any> => (await client.get('/api/live/coach')).data,

  // ─── Sessões, Volta e Evolução (pedido 30): só leitura ─────────────────────
  getEvolucaoResumo: async (): Promise<any> => (await client.get('/api/evolucao/resumo', { timeout: 30_000 })).data,
  getEvolucaoSessao: async (sessao: string): Promise<any> => (
    await client.get(`/api/evolucao/sessoes/${encodeURIComponent(sessao)}`, { timeout: 30_000 })
  ).data,
  getCoachReferencias: async (): Promise<any> => (await client.get('/api/coach/referencias', { timeout: 30_000 })).data,
  /** As linhas de uma volta no store v2 (o `#` do id vai codificado). */
  getStoreVolta: async (lapId: string): Promise<any> => (
    await client.get(`/api/store/voltas/${encodeURIComponent(lapId)}`, { timeout: 60_000 })
  ).data,
  getGeometriaOficial: async (): Promise<any> => (await client.get('/api/geometria/oficial', { timeout: 60_000 })).data,
};

export default client;
