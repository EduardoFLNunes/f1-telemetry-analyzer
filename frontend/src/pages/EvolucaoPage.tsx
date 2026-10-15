/**
 * Evolução (pedido 30), como no protótipo A:
 *
 * - mediana e melhor volta por sessão, com o critério do ADR 0015;
 * - perda por curva entre sessões, com a faixa de 90% de confiança;
 * - técnica de pilotagem por curva (bloco `tecnica` do JSON da sessão).
 *
 * Tudo do relatório de evolução (`/api/evolucao/resumo` e
 * `/api/evolucao/sessoes/{sessao}`); nada é recalculado aqui.
 */
import React, { useState } from 'react';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { PainelVidro } from '../components/ui/base';
import type { Tela } from '../navegacao/rotas';
import { useSessoesDoRelatorio, type TecnicaDaCurva } from '../volta/dados';
import { nf, nomeDaSessao, tempo } from '../volta/formato';
import { GraficoTendencia, IntervaloDaCurva } from '../evolucao/Graficos';

const codigoDaCurva = (curva: string) => curva.split('-')[0];

function textoDaEmendada(t: TecnicaDaCurva): React.ReactNode {
  const e = t.freada_emendada;
  if (!e) return '—';
  const ia = String(e.ia ?? '—').replace('nao', 'não');
  return (
    <>
      {e.voltas_com_frenagem ? `${e.voltas_emendadas} de ${e.voltas_com_frenagem} voltas` : 'sem frenagem'} <span className="texto-fraco">(IA: {ia})</span>
    </>
  );
}

const numero = (v: number | null | undefined, casas: number) => (v === null || v === undefined ? '—' : nf(v, casas));

export const EvolucaoPage: React.FC<{ navegar: (tela: Tela, sub?: string | null) => void }> = () => {
  const relatorio = useSessoesDoRelatorio();
  const [escolhida, setEscolhida] = useState<string | null>(null);
  const resumo = relatorio.dado?.resumo;
  const sessoes = relatorio.dado?.sessoes ?? [];
  const tempoIa = resumo?.referencia?.tempo_s ?? null;
  const a15 = resumo?.criterio_adr_0015;
  const sessaoTecnica = sessoes.find((s) => s.sessao === escolhida) ?? sessoes[sessoes.length - 1] ?? null;
  const curvas = sessoes[0]?.curvas.map((c) => c.curva) ?? [];

  return (
    <ErrorBoundary>
      <div className="tela-conteudo">
        <header className="cabecalho-tela">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div className="sobrancelha">Interlagos · referência: volta da IA {tempoIa === null ? '—' : tempo(tempoIa)}</div>
            <h1 className="titulo-tela">Evolução</h1>
          </div>
        </header>

        {relatorio.carregando && <p className="texto-fraco">Lendo o relatório de evolução…</p>}
        {relatorio.erro && (
          <PainelVidro titulo="Evolução">
            <p className="texto-apoio" style={{ margin: 0 }}>Sem dados: {relatorio.erro}</p>
          </PainelVidro>
        )}

        {resumo && (
          <>
            <PainelVidro titulo="Mediana e melhor volta por sessão">
              {a15 && (
                <p className="texto-apoio" style={{ margin: 0 }}>
                  Critério do ADR 0015: {a15.estabilizou ? 'estabilizou' : 'ainda variando'} (amplitude{' '}
                  {a15.amplitude_s === null ? '—' : `${nf(a15.amplitude_s, 3)} s`}, limite {nf(a15.limite_s, 1)} s, {a15.sessoes_disponiveis} sessões
                  de {a15.sessoes_necessarias} necessárias).
                </p>
              )}
              <GraficoTendencia sessoes={resumo.sessoes} tempoIa={tempoIa} />
              <span className="legenda">
                <span><i className="linha" style={{ borderColor: 'var(--voce)' }} />mediana</span>
                <span><i className="linha" style={{ borderColor: 'var(--voce)', borderTopStyle: 'dashed' }} />melhor volta</span>
                <span><i className="linha" style={{ borderColor: 'var(--referencia)', borderTopStyle: 'dashed' }} />volta da IA</span>
              </span>
            </PainelVidro>

            <PainelVidro titulo="Perda por curva entre sessões">
              <p className="texto-apoio" style={{ margin: 0 }}>
                Ponto: perda mediana para a IA, em segundos. Traço: faixa de 90% de confiança. Ponto vazio: sem diferença consistente.
              </p>
              <div className="superficie tabela-caixa">
                <table className="tabela tabela--curvas">
                  <thead>
                    <tr>
                      <th scope="col">Curva</th>
                      {sessoes.map((s) => (
                        <th key={s.sessao} scope="col">{nomeDaSessao(s.sessao)}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {curvas.map((nome) => (
                      <tr key={nome}>
                        <th scope="row" className="dado" style={{ fontWeight: 500 }}>{codigoDaCurva(nome)}</th>
                        {sessoes.map((s) => (
                          <td key={s.sessao}>
                            <IntervaloDaCurva curva={s.curvas.find((c) => c.curva === nome)} />
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </PainelVidro>

            <PainelVidro
              titulo="Técnica de pilotagem por curva"
              acao={
                <div className="chips" role="group" aria-label="Sessão">
                  {sessoes.map((s) => (
                    <button key={s.sessao} type="button" className="chip" aria-pressed={s.sessao === sessaoTecnica?.sessao} onClick={() => setEscolhida(s.sessao)}>
                      {nomeDaSessao(s.sessao)}
                    </button>
                  ))}
                </div>
              }
            >
              <p className="texto-apoio" style={{ margin: 0 }}>
                Medidas descritivas: não entram em nenhum critério. Uso da aderência: p95 da aceleração combinada na curva. Freio e volante juntos: metros
                com freio e volante ao mesmo tempo.
              </p>
              {sessaoTecnica?.tecnica?.curvas?.length ? (
                <div className="superficie tabela-caixa">
                  <table className="tabela tabela--curvas">
                    <thead>
                      <tr>
                        <th scope="col">Curva</th>
                        <th scope="col" className="num">Uso da aderência (g)</th>
                        <th scope="col" className="num">IA (g)</th>
                        <th scope="col" className="num">Freio e volante juntos (m)</th>
                        <th scope="col" className="num">IA (m)</th>
                        <th scope="col">Freada emendada</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sessaoTecnica.tecnica.curvas.map((t) => (
                        <tr key={t.curva}>
                          <th scope="row" className="dado" style={{ fontWeight: 500 }}>{codigoDaCurva(t.curva)}</th>
                          <td className="num">{numero(t.uso_da_aderencia?.mediana, 2)}</td>
                          <td className="num texto-apoio">{numero(t.uso_da_aderencia?.ia_g, 2)}</td>
                          <td className="num">{numero(t.freio_e_volante_juntos?.mediana, 0)}</td>
                          <td className="num texto-apoio">{numero(t.freio_e_volante_juntos?.ia_m, 0)}</td>
                          <td>{textoDaEmendada(t)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="texto-apoio" style={{ margin: 0 }}>Sem dados: o JSON desta sessão não tem o bloco de técnica.</p>
              )}
            </PainelVidro>
          </>
        )}
      </div>
    </ErrorBoundary>
  );
};

export default EvolucaoPage;
