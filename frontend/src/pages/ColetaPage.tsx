/**
 * Coleta de dados (pedido 28): antes, durante e depois da sessão, se a gravação
 * tem o que os modelos precisam.
 *
 * Só lê. O que é preciso vem do registro do backend (`/api/coleta/requisitos`,
 * usado pelas rotas de `/api/coleta`); o estado do backend e do jogo vem de
 * `/api/runtime/status` e `/api/recording/status`, como no cartão "Estado da
 * coleta" da página inicial. A única coisa que a aba muda é a configuração do
 * app: o repositório de onde o coach lê o modelo e a referência do coach.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, ClipboardCheck, Loader2, RefreshCw, Save } from 'lucide-react';
import { api } from '../api/client';
import { LiveSessionStrip } from '../components/LiveSessionStrip';
import { ErrorBoundary } from '../components/ErrorBoundary';
import {
  COR_DO_TOM,
  ROTULO_ESTADO,
  corDoDisco,
  formatarComponentes,
  formatarNumero,
  formatarPorcentagem,
  formatarTempo,
  tomDoEstado,
  type EstadoCanal,
} from '../utils/coleta';

type Tom = 'ok' | 'aviso' | 'ruim' | 'neutro';

const GRUPOS_TABELA: Array<{ id: string; rotulo: string }> = [
  { id: 'base', rotulo: 'Base' },
  { id: 'origem', rotulo: 'Origem' },
  { id: 'limites', rotulo: 'Limites' },
  { id: 'm1', rotulo: 'M1' },
  { id: 'contexto', rotulo: 'Contexto' },
];

function usePolling<T>(loader: () => Promise<T>, intervalMs: number): [T | null, boolean, () => Promise<void>] {
  const [data, setData] = useState<T | null>(null);
  const [failed, setFailed] = useState(false);
  const load = useCallback(async () => {
    try {
      setData(await loader());
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, [loader]);
  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      if (!cancelled) await load();
    };
    tick();
    const timer = window.setInterval(tick, intervalMs);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [load, intervalMs]);
  return [data, failed, load];
}

const Pill: React.FC<{ tom: Tom; children: React.ReactNode; title?: string }> = ({ tom, children, title }) => (
  <span
    title={title}
    className="num"
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 4,
      padding: '2px 7px',
      borderRadius: 3,
      fontSize: 9,
      fontWeight: 800,
      letterSpacing: '0.04em',
      whiteSpace: 'nowrap',
      color: COR_DO_TOM[tom],
      border: `1px solid ${COR_DO_TOM[tom]}55`,
      background: `${COR_DO_TOM[tom]}14`,
    }}
  >
    {children}
  </span>
);

const Check: React.FC<{ titulo: string; detalhe: React.ReactNode; tom: Tom; texto: string }> = ({ titulo, detalhe, tom, texto }) => (
  <div
    style={{
      display: 'grid',
      gridTemplateColumns: 'minmax(0, 1fr) auto',
      gap: 10,
      alignItems: 'center',
      padding: '8px 0',
      borderTop: '1px solid var(--border)',
    }}
  >
    <div style={{ minWidth: 0 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-1)' }}>{titulo}</div>
      <div style={{ fontSize: 10, color: 'var(--text-2)', marginTop: 2, lineHeight: 1.45, overflowWrap: 'anywhere' }}>{detalhe}</div>
    </div>
    <Pill tom={tom}>{texto}</Pill>
  </div>
);

const Secao: React.FC<{ titulo: string; subtitulo: string; children: React.ReactNode; acao?: React.ReactNode }> = ({ titulo, subtitulo, children, acao }) => (
  <section className="panel home-card">
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'flex-start' }}>
      <div>
        <div className="app-page-title">{titulo}</div>
        <div className="app-page-subtitle">{subtitulo}</div>
      </div>
      {acao}
    </div>
    {children}
  </section>
);

const thStyle: React.CSSProperties = {
  textAlign: 'left',
  fontFamily: "'JetBrains Mono', monospace",
  fontSize: 8,
  fontWeight: 700,
  letterSpacing: '0.12em',
  textTransform: 'uppercase',
  color: 'var(--text-3)',
  padding: '5px 6px',
  borderBottom: '1px solid var(--border-hi)',
};
const tdStyle: React.CSSProperties = {
  fontSize: 10.5,
  color: 'var(--text-1)',
  padding: '5px 6px',
  borderBottom: '1px solid var(--border)',
  verticalAlign: 'top',
};

function dataCurta(valor: unknown): string {
  if (typeof valor !== 'string' || !valor) return '—';
  const parsed = new Date(valor);
  if (Number.isNaN(parsed.getTime())) return String(valor);
  return parsed.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

// ── Antes de pilotar ────────────────────────────────────────────────────────

const AntesDePilotar: React.FC<{ antes: any; runtime: any; recording: any; falhou: boolean; onSalvar: (c: Record<string, unknown>) => Promise<string | null>; oficial: any }> = ({
  antes,
  runtime,
  recording,
  falhou,
  onSalvar,
  oficial,
}) => {
  const [repo, setRepo] = useState('');
  const [mensagem, setMensagem] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);
  const config = antes?.configuracao;
  useEffect(() => {
    if (config?.repositorio !== undefined) setRepo(config.repositorio || '');
  }, [config?.repositorio]);

  if (!antes) {
    return (
      <Secao titulo="Antes de pilotar" subtitulo="Versão, disco, jogo e coach.">
        <div style={{ fontSize: 10, color: 'var(--text-3)' }}>
          {falhou ? 'O backend não respondeu às rotas da coleta.' : <><Loader2 size={12} className="animate-spin" /> Verificando...</>}
        </div>
      </Secao>
    );
  }

  const app = antes.app || {};
  const disco = antes.gravacao || {};
  const jogo = antes.jogo || {};
  const coach = antes.coach || {};
  const captura = recording?.captureGate || runtime?.capture || jogo.captura || {};
  const backendOnline = runtime?.status === 'ok';
  const gravando = Boolean(recording?.recording);

  const salvar = async (changes: Record<string, unknown>) => {
    setSalvando(true);
    setMensagem(await onSalvar(changes));
    setSalvando(false);
  };

  const discoTom: Tom = disco.nivel === 'vermelho' ? 'ruim' : disco.nivel === 'amarelo' ? 'aviso' : disco.nivel === 'ok' ? 'ok' : 'neutro';
  const m1 = oficial && oficial.disponivel ? oficial : null;

  return (
    <Secao titulo="Antes de pilotar" subtitulo="Confira antes de abrir o Assetto Corsa.">
      <div className="home-columns" style={{ gap: 14 }}>
        <div>
          <Check
            titulo="Versão do app"
            detalhe={<>
              <span className="num">{app.versao || 'desconhecida'}</span> · commit <span className="num">{app.commitCurto || '—'}</span>
              {app.empacotado ? ' · app instalado' : ' · rodando do código-fonte'}
              {app.arvoreSuja ? ' · árvore com mudanças não commitadas' : ''}
            </>}
            tom={app.commit ? 'ok' : 'aviso'}
            texto={app.commitCurto || 'sem commit'}
          />
          <Check
            titulo="Pasta das gravações"
            detalhe={<><span className="num">{disco.pasta}</span>{disco.livreGb != null ? ` · ${formatarNumero(disco.livreGb, 1)} GB livres de ${formatarNumero(disco.totalGb, 0)} GB em ${disco.disco}` : ''} · amarelo abaixo de 5 GB, vermelho abaixo de 2 GB</>}
            tom={discoTom}
            texto={disco.livreGb != null ? `${formatarNumero(disco.livreGb, 1)} GB livres` : 'sem leitura'}
          />
          <Check
            titulo="Backend"
            detalhe={<>Versão <span className="num">{runtime?.version || antes.backend?.versao}</span> · pasta de dados <span className="num">{antes.backend?.pastaDeDados}</span></>}
            tom={backendOnline ? 'ok' : 'ruim'}
            texto={backendOnline ? 'online' : 'offline'}
          />
          <Check
            titulo="Assetto Corsa"
            detalhe={captura.allowed
              ? (gravando ? `Conectado e gravando (${recording?.sessionId || 'sessão nova'}).` : 'Conectado. A gravação começa quando o carro entra na pista.')
              : (captura.message || 'Abra o Assetto Corsa e carregue uma sessão de pilotagem.')}
            tom={captura.allowed ? 'ok' : 'aviso'}
            texto={captura.allowed ? (gravando ? 'gravando' : 'conectado') : 'aguardando'}
          />
          <Check
            titulo="Carro e pista detectados"
            detalhe={<>
              <span className="num">{jogo.carro || 'carro não detectado'}</span> · <span className="num">{jogo.pista || 'pista não detectada'}</span>
              {(jogo.avisos || []).map((aviso: string) => <div key={aviso} style={{ color: 'var(--amber)' }}>{aviso}</div>)}
              {!jogo.carro && <div style={{ color: 'var(--text-3)' }}>Esperado: {jogo.carroEsperado} em {jogo.pistaEsperada}.</div>}
            </>}
            tom={(jogo.avisos || []).length ? 'aviso' : jogo.carro ? 'ok' : 'neutro'}
            texto={(jogo.avisos || []).length ? 'diferente' : jogo.carro ? 'esperados' : 'sem jogo'}
          />
          <Check
            titulo="Coach"
            detalhe={coach.ativo
              ? <>Referência: {coach.referenciaRotulo}. Modelo de {dataCurta(coach.modelo?.construidoEm)}, com {coach.modelo?.voltasSuas ?? '—'} voltas suas. <span className="num">geometry_id {coach.modelo?.geometryId}</span> bate com a geometria.</>
              : <>Calado: {coach.motivoCalado}.</>}
            tom={coach.ativo ? 'ok' : coach.referencia === 'desligado' ? 'neutro' : 'aviso'}
            texto={coach.ativo ? 'ligado' : coach.referencia === 'desligado' ? 'desligado' : 'calado'}
          />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ padding: '10px 12px', border: '1px solid var(--border)', borderRadius: 4 }}>
            <div className="label" style={{ marginBottom: 6 }}>Referência do coach</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {(config?.opcoesReferencia || []).map((opcao: any) => (
                <button
                  key={opcao.id}
                  type="button"
                  className={`home-cta ${config?.referenciaCoach === opcao.id ? '' : 'home-cta-muted'}`}
                  aria-pressed={config?.referenciaCoach === opcao.id}
                  disabled={salvando || config?.referenciaTravadaPelaVariavel}
                  onClick={() => salvar({ referenciaCoach: opcao.id })}
                >
                  {opcao.rotulo}
                </button>
              ))}
            </div>
            {config?.referenciaTravadaPelaVariavel && (
              <div style={{ fontSize: 10, color: 'var(--amber)', marginTop: 6 }}>
                Definida pela variável AT_COACH_REFERENCE (app de desenvolvimento). Tire a variável para escolher aqui.
              </div>
            )}

            <div className="label" style={{ margin: '12px 0 6px' }}>Repositório do modelo</div>
            <div style={{ display: 'flex', gap: 6 }}>
              <input
                value={repo}
                onChange={(event) => setRepo(event.target.value)}
                placeholder={config?.repositorioPadrao || 'C:\\caminho\\do\\repositorio'}
                aria-label="Caminho do repositório"
                className="num"
                style={{
                  flex: 1,
                  minWidth: 0,
                  fontSize: 10,
                  padding: '6px 8px',
                  borderRadius: 3,
                  border: '1px solid var(--border-hi)',
                  background: 'rgba(255,255,255,0.02)',
                  color: 'var(--text-1)',
                }}
              />
              <button type="button" className="home-cta" disabled={salvando} onClick={() => salvar({ repositorio: repo.trim() })}>
                <Save size={11} /> Salvar
              </button>
            </div>
            <div style={{ fontSize: 9.5, color: 'var(--text-3)', marginTop: 6, lineHeight: 1.5 }}>
              O coach lê <span className="num">data/reference_models/vhe_interlagos.json</span> e <span className="num">vhe_interlagos.geometry.json</span> desta pasta, só lendo.
              Origem do caminho: {config?.repositorioFonte === 'configuracao' ? 'salvo nesta aba' : config?.repositorioFonte === 'AT_REPO_PATH' ? 'repositório em que o app foi construído' : config?.repositorioFonte === 'codigo-fonte' ? 'código-fonte' : 'nenhum'}.
              Deixe vazio e salve para voltar ao padrão.
            </div>
            {mensagem && <div style={{ fontSize: 10, color: mensagem.startsWith('Salvo') ? 'var(--emerald)' : 'var(--rose)', marginTop: 6 }}>{mensagem}</div>}
          </div>

          <div style={{ padding: '10px 12px', border: '1px solid var(--border)', borderRadius: 4 }}>
            <div className="label" style={{ marginBottom: 4 }}>Sessões para a M1 (contagem oficial)</div>
            {m1 ? (
              <>
                <div className="num" style={{ fontSize: 22, fontWeight: 800, color: m1.n >= m1.meta ? 'var(--emerald)' : 'var(--text-1)' }}>{m1.n} de {m1.meta}</div>
                <div style={{ height: 5, borderRadius: 3, background: 'rgba(255,255,255,0.05)', marginTop: 4 }} role="progressbar" aria-valuemin={0} aria-valuemax={m1.meta} aria-valuenow={m1.n} aria-label="Sessões para a M1">
                  <div style={{ width: `${Math.min(100, (m1.n / m1.meta) * 100)}%`, height: '100%', borderRadius: 3, background: 'var(--emerald)' }} />
                </div>
                <div style={{ fontSize: 9.5, color: 'var(--text-3)', marginTop: 6, lineHeight: 1.5 }}>
                  Lida do store v2 do repositório, refeito pelo <span className="num">atualizar_coach</span> em {dataCurta(m1.store?.construidoEm)}.
                  {m1.sessoesQueContam?.length ? <> Contam: <span className="num">{m1.sessoesQueContam.join(', ')}</span>.</> : null}
                </div>
              </>
            ) : (
              <div style={{ fontSize: 10, color: 'var(--text-3)' }}>{oficial?.motivo || 'Lendo o store v2...'}</div>
            )}
          </div>
        </div>
      </div>
    </Secao>
  );
};

// ── Durante a sessão ────────────────────────────────────────────────────────

const Indicador: React.FC<{ aoVivo: any }> = ({ aoVivo }) => {
  let tom: Tom = 'neutro';
  let texto = 'Sem gravação em andamento';
  let detalhe = 'O estado dos canais aparece quando a gravação começa.';
  if (aoVivo?.gravando && aoVivo?.quadros) {
    if (aoVivo.indicadorIA === false) {
      tom = 'ok';
      texto = 'Você no volante';
      detalhe = 'O indicador de IA está desligado: as voltas saem como suas, sem anotação.';
    } else if (aoVivo.indicadorIA === true) {
      tom = 'ruim';
      texto = 'IA no volante';
      detalhe = 'Volta da IA: não conta como sua. A sessão deixa de contar para a M1.';
    } else {
      tom = 'aviso';
      texto = 'Indicador de IA ausente';
      detalhe = 'A gravação não tem o indicador: a origem das voltas vai precisar de anotação.';
    }
  }
  return (
    <div style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '10px 12px', borderRadius: 4, border: `1px solid ${COR_DO_TOM[tom]}55`, background: `${COR_DO_TOM[tom]}12` }}>
      <span style={{ width: 10, height: 10, borderRadius: '50%', background: COR_DO_TOM[tom], flexShrink: 0 }} />
      <div>
        <div className="num" style={{ fontSize: 12, fontWeight: 800, color: COR_DO_TOM[tom] }}>{texto}</div>
        <div style={{ fontSize: 10, color: 'var(--text-2)', marginTop: 2 }}>{detalhe}</div>
      </div>
    </div>
  );
};

const DuranteASessao: React.FC<{ aoVivo: any; registro: any }> = ({ aoVivo, registro }) => {
  const itens: any[] = aoVivo?.itens || [];
  const regras = registro?.regras || {};
  return (
    <Secao
      titulo="Durante a sessão"
      subtitulo={`Ao vivo, numa janela de ${formatarNumero(regras.janelaAoVivoS ?? 5, 0)} s do que está sendo gravado. Taxa baixa abaixo de ${formatarNumero(regras.taxaMinimaHz ?? 40, 0)} Hz; parado é um valor que não muda com o carro acima de ${formatarNumero(regras.velocidadeAndandoKmh ?? 30, 0)} km/h.`}
    >
      <LiveSessionStrip taxaHz={aoVivo?.gravando ? aoVivo?.taxaHz ?? null : null} />
      <div className="home-columns" style={{ gap: 12 }}>
        <Indicador aoVivo={aoVivo} />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
          <div className="home-stat">
            <div className="label" style={{ marginBottom: 3 }}>Taxa real</div>
            <div className="home-stat-value">{aoVivo?.taxaHz != null ? `${formatarNumero(aoVivo.taxaHz, 1)} Hz` : '—'}</div>
          </div>
          <div className="home-stat">
            <div className="label" style={{ marginBottom: 3 }}>Amostras gravadas</div>
            <div className="home-stat-value">{aoVivo?.gravador?.amostrasEscritas != null ? Number(aoVivo.gravador.amostrasEscritas).toLocaleString('pt-BR') : '—'}</div>
          </div>
          <div className="home-stat">
            <div className="label" style={{ marginBottom: 3 }}>Descartadas</div>
            <div className="home-stat-value" style={{ color: aoVivo?.gravador?.descartadas ? 'var(--rose)' : 'var(--text-1)' }}>{aoVivo?.gravador?.descartadas ?? '—'}</div>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: 12 }}>
        {(aoVivo?.grupos || registro?.grupos || []).map((grupo: any) => {
          const doGrupo = itens.filter((item) => item.grupo === grupo.id);
          return (
            <div key={grupo.id} style={{ border: '1px solid var(--border)', borderRadius: 4, padding: '8px 10px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <div className="label" style={{ fontSize: 8 }}>{grupo.nome}</div>
                {grupo.estado && <Pill tom={tomDoEstado(grupo.estado)}>{ROTULO_ESTADO[grupo.estado as EstadoCanal] || grupo.estado}</Pill>}
              </div>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={thStyle}>Canal</th>
                    <th style={thStyle}>Estado</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Hz</th>
                    <th style={thStyle}>Último valor</th>
                  </tr>
                </thead>
                <tbody>
                  {doGrupo.map((item) => (
                    <tr key={item.id}>
                      <td style={tdStyle}>
                        {item.nome}
                        {item.obrigatorioM1 && <span style={{ color: 'var(--cyan)', fontSize: 8.5, marginLeft: 4 }}>M1</span>}
                      </td>
                      <td style={tdStyle}><Pill tom={tomDoEstado(item.estado)}>{ROTULO_ESTADO[item.estado as EstadoCanal] || item.estado}</Pill></td>
                      <td style={{ ...tdStyle, textAlign: 'right' }} className="num">{item.taxaHz != null ? formatarNumero(item.taxaHz, 0) : '—'}</td>
                      <td style={{ ...tdStyle, color: 'var(--text-2)' }} className="num">{formatarComponentes(item.componentes || [], item.tipo, item.unidade)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        })}
      </div>
    </Secao>
  );
};

// ── Depois de cada volta e no fim da sessão ────────────────────────────────

const Veredito: React.FC<{ resultado: any; oficial: any }> = ({ resultado, oficial }) => {
  const veredito = resultado?.veredito;
  if (!veredito) return null;
  const tom: Tom = veredito.conta ? 'ok' : 'ruim';
  return (
    <div style={{ padding: '10px 12px', borderRadius: 4, border: `1px solid ${COR_DO_TOM[tom]}55`, background: `${COR_DO_TOM[tom]}10` }}>
      <div className="label" style={{ marginBottom: 4 }}>Esta sessão conta para a M1? {veredito.final ? '' : '(sessão em andamento)'}</div>
      <div style={{ fontSize: 12, fontWeight: 700, color: COR_DO_TOM[tom] }}>{veredito.texto}</div>
      <div style={{ fontSize: 10, color: 'var(--text-2)', marginTop: 6, lineHeight: 1.5 }}>
        {veredito.voltasValidas} de {veredito.voltas} voltas válidas pelos portões. Preenchimento na grade das voltas válidas:{' '}
        {Object.entries(veredito.preenchimentoGrade || {})
          .filter(([coluna]) => ['yaw_rate', 'velocity_long', 'velocity_lat', 'brake_temp_fl'].includes(coluna))
          .map(([coluna, valor]) => `${coluna} ${formatarPorcentagem(valor as number)}`)
          .join(', ')}.
      </div>
      <div style={{ fontSize: 9.5, color: 'var(--text-3)', marginTop: 6, lineHeight: 1.5 }}>
        Prévia pela regra da M1 ({veredito.regra}). A contagem oficial continua no store v2, depois do <span className="num">atualizar_coach</span>
        {oficial?.disponivel ? <>: hoje, {oficial.n} de {oficial.meta}.</> : '.'}
      </div>
    </div>
  );
};

const TabelaDeVoltas: React.FC<{ resultado: any }> = ({ resultado }) => {
  const voltas: any[] = resultado?.voltas || [];
  if (!voltas.length) {
    return <div style={{ fontSize: 10, color: 'var(--text-3)' }}>Nenhuma volta fechada ainda.</div>;
  }
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={thStyle}>Volta</th>
            <th style={thStyle}>Tempo</th>
            <th style={thStyle}>Quem</th>
            <th style={thStyle}>Portões</th>
            {GRUPOS_TABELA.map((g) => <th key={g.id} style={{ ...thStyle, textAlign: 'right' }}>{g.rotulo}</th>)}
          </tr>
        </thead>
        <tbody>
          {voltas.map((volta) => (
            <tr key={volta.lapId}>
              <td style={tdStyle} className="num">#{String(volta.sequencia).padStart(4, '0')} <span style={{ color: 'var(--text-3)' }}>(jogo {volta.voltaDoJogo})</span></td>
              <td style={tdStyle} className="num">{volta.tempo || (volta.duracao ? <span style={{ color: 'var(--text-3)' }}>{volta.duracao}*</span> : '—')}</td>
              <td style={tdStyle}><Pill tom={volta.origem === 'humano' ? 'ok' : volta.origem === 'desconhecida' ? 'aviso' : 'ruim'}>{volta.origemRotulo}</Pill></td>
              <td style={tdStyle}>
                <Pill tom={volta.entraNoStore ? 'ok' : 'ruim'}>{volta.entraNoStore ? 'passa' : 'não passa'}</Pill>
                {!volta.entraNoStore && (volta.motivos || []).length > 0 && (
                  <div style={{ fontSize: 9.5, color: 'var(--text-2)', marginTop: 3, maxWidth: 360 }}>{volta.motivos.join('; ')}</div>
                )}
              </td>
              {GRUPOS_TABELA.map((g) => {
                const grupo = volta.preenchimentoGrupos?.[g.id];
                const valor = grupo?.minimo;
                const tom: Tom = valor == null ? 'neutro' : valor >= 0.95 ? 'ok' : valor > 0 ? 'aviso' : 'ruim';
                return (
                  <td key={g.id} style={{ ...tdStyle, textAlign: 'right' }} className="num" title={grupo?.piorItem ? `pior item: ${grupo.piorItem}` : undefined}>
                    <span style={{ color: COR_DO_TOM[tom] }}>{formatarPorcentagem(valor)}</span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ fontSize: 9.5, color: 'var(--text-3)', marginTop: 6 }}>
        Tempo pelo relógio da grade, como no store v2. * duração da volta que não passou nos portões. Preenchimento: o pior item de cada grupo, nas amostras da volta.
      </div>
    </div>
  );
};

const DepoisDaSessao: React.FC<{ sessaoAtual: any; oficial: any }> = ({ sessaoAtual, oficial }) => {
  const [verificacoes, setVerificacoes] = useState<any[]>([]);
  const [sessoes, setSessoes] = useState<any[]>([]);
  const [escolhida, setEscolhida] = useState<string | null>(null);
  const [detalhe, setDetalhe] = useState<any>(null);

  const recarregar = useCallback(async () => {
    try {
      const [lista, gravadas] = await Promise.all([
        api.listColetaVerificacoes().catch(() => ({ verificacoes: [] })),
        api.getSessions(15).catch(() => ({ sessions: [] })),
      ]);
      setVerificacoes(lista?.verificacoes || []);
      setSessoes(gravadas?.sessions || []);
    } catch {
      /* a lista fica como estava */
    }
  }, []);

  useEffect(() => {
    recarregar();
    const timer = window.setInterval(recarregar, 15000);
    return () => window.clearInterval(timer);
  }, [recarregar]);

  useEffect(() => {
    if (!escolhida) {
      setDetalhe(null);
      return undefined;
    }
    let cancelled = false;
    const load = async () => {
      try {
        const estado = await api.getColetaVerificacao(escolhida);
        if (!cancelled) setDetalhe(estado);
        if (estado?.estado === 'conferindo') return true;
      } catch {
        if (!cancelled) setDetalhe({ estado: 'erro', erro: 'O backend não respondeu.' });
      }
      return false;
    };
    load();
    const timer = window.setInterval(async () => {
      const continuar = await load();
      if (!continuar) {
        window.clearInterval(timer);
        recarregar();
      }
    }, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [escolhida, recarregar]);

  const conferir = async (sessionId: string) => {
    try {
      await api.conferirSessao(sessionId);
    } catch {
      /* o estado mostra o erro */
    }
    setEscolhida(null);
    window.setTimeout(() => setEscolhida(sessionId), 50);
  };

  const atual = sessaoAtual?.resultado;
  const mostrado = detalhe?.resultado || (!escolhida ? atual : null);
  const conferidas = new Set(verificacoes.map((v) => v.sessao));

  return (
    <Secao
      titulo="Depois de cada volta e no fim da sessão"
      subtitulo="Cada volta passa pelos portões de qualidade do pipeline (quality.py). A conferência fica gravada em data/verificacoes, fora da pasta de gravações."
      acao={<button type="button" className="home-cta home-cta-muted" onClick={recarregar}><RefreshCw size={11} /> Atualizar</button>}
    >
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
        <span className="label">Mostrando</span>
        <button type="button" className={`home-cta ${!escolhida ? '' : 'home-cta-muted'}`} onClick={() => setEscolhida(null)}>
          {atual ? `Sessão em gravação: ${atual.sessao}` : 'Sessão em gravação (nenhuma)'}
        </button>
        {verificacoes.slice(0, 8).map((v) => (
          <button key={v.sessao} type="button" className={`home-cta ${escolhida === v.sessao ? '' : 'home-cta-muted'}`} onClick={() => setEscolhida(v.sessao)} title={v.texto}>
            {v.conta ? <CheckCircle2 size={11} /> : null}
            {v.sessao}
          </button>
        ))}
      </div>

      {detalhe?.estado === 'conferindo' && (
        <div style={{ fontSize: 10, color: 'var(--cyan)' }}>
          <Loader2 size={12} className="animate-spin" style={{ display: 'inline', verticalAlign: -2 }} /> Conferindo {escolhida}
          {detalhe.progresso != null ? ` · ${formatarPorcentagem(detalhe.progresso)} do arquivo lido` : ''}...
        </div>
      )}
      {detalhe?.estado === 'erro' && <div style={{ fontSize: 10, color: 'var(--rose)' }}>A conferência falhou: {detalhe.erro}</div>}
      {detalhe?.estado === 'nao_conferida' && <div style={{ fontSize: 10, color: 'var(--text-3)' }}>Esta sessão ainda não foi conferida.</div>}

      {mostrado ? (
        <>
          <div style={{ fontSize: 10, color: 'var(--text-2)' }}>
            <span className="num">{mostrado.sessao}</span> · carro <span className="num">{mostrado.gravacao?.carModel || 'não gravado'}</span>
            {' '}· app <span className="num">{mostrado.gravacao?.appVersion || 'versão não gravada'}{mostrado.gravacao?.appCommit ? ` @ ${String(mostrado.gravacao.appCommit).slice(0, 7)}` : ''}</span>
            {mostrado.geometria ? <> · geometria <span className="num">{mostrado.geometria.geometryId}</span></> : null}
            {mostrado.voltaAberta ? ` · volta aberta: jogo ${mostrado.voltaAberta.voltaDoJogo}, ${mostrado.voltaAberta.amostras} amostras` : ''}
          </div>
          <Veredito resultado={mostrado} oficial={oficial} />
          <TabelaDeVoltas resultado={mostrado} />
        </>
      ) : (
        !escolhida && <div style={{ fontSize: 10, color: 'var(--text-3)' }}>Nenhuma sessão sendo gravada agora. Escolha uma conferência acima, ou confira uma sessão gravada abaixo.</div>
      )}

      <div>
        <div className="label" style={{ margin: '6px 0 4px' }}>Conferir uma sessão gravada</div>
        {sessoes.length === 0 ? (
          <div style={{ fontSize: 10, color: 'var(--text-3)' }}>Nenhuma sessão na pasta de gravações do app.</div>
        ) : (
          sessoes.slice(0, 8).map((sessao) => (
            <div key={sessao.sessionId} className="home-session-row">
              <div className="num" style={{ fontSize: 10, color: 'var(--text-1)' }}>
                {sessao.sessionId}
                <span style={{ color: 'var(--text-3)' }}> · {Array.isArray(sessao.laps) ? sessao.laps.length : '—'} voltas{conferidas.has(sessao.sessionId) ? ' · conferida' : ''}</span>
              </div>
              <button type="button" className="home-cta home-cta-muted" onClick={() => conferir(sessao.sessionId)}>
                <ClipboardCheck size={11} /> Conferir
              </button>
            </div>
          ))
        )}
      </div>

      <div style={{ fontSize: 10, color: 'var(--text-2)', lineHeight: 1.6, borderTop: '1px solid var(--border)', paddingTop: 8 }}>
        Depois de pilotar, feche o app e rode, na pasta <span className="num">backend</span>:{' '}
        <span className="num" style={{ color: 'var(--text-1)' }}>..\.venv\Scripts\python.exe tools\atualizar_coach.py</span>. A sessão entra no store v2 e na contagem oficial.
      </div>
    </Secao>
  );
};

// ── Página ──────────────────────────────────────────────────────────────────

export const ColetaPage: React.FC = () => {
  const [antes, antesFalhou, recarregarAntes] = usePolling(api.getColetaAntes, 10000);
  const [runtime] = usePolling(api.getRuntimeStatus, 5000);
  const [recording] = usePolling(api.getRecordingStatus, 5000);
  const [aoVivo] = usePolling(api.getColetaAoVivo, 2000);
  const [sessaoAtual] = usePolling(api.getColetaSessaoAtual, 5000);
  const [oficial, , recarregarOficial] = usePolling(api.getColetaM1Oficial, 60000);
  const [registro] = usePolling(api.getColetaRequisitos, 600000);

  const salvar = useCallback(async (changes: Record<string, unknown>): Promise<string | null> => {
    try {
      await api.putColetaConfiguracao(changes);
      await Promise.all([recarregarAntes(), recarregarOficial()]);
      return 'Salvo. O coach já usa a configuração nova.';
    } catch (error: any) {
      return error?.response?.data?.detail || 'Não foi possível salvar.';
    }
  }, [recarregarAntes, recarregarOficial]);

  return (
    <ErrorBoundary>
      <div className="app-page">
        <div>
          <div className="app-page-title">Coleta de dados</div>
          <div className="app-page-subtitle">
            Antes, durante e depois da sessão: a gravação tem o que o coach, o store v2 e o modelo do carro (M1) precisam?
          </div>
        </div>
        <AntesDePilotar antes={antes} runtime={runtime} recording={recording} falhou={antesFalhou} onSalvar={salvar} oficial={oficial} />
        <DuranteASessao aoVivo={aoVivo} registro={registro} />
        <DepoisDaSessao sessaoAtual={sessaoAtual} oficial={oficial} />
      </div>
    </ErrorBoundary>
  );
};

export default ColetaPage;
