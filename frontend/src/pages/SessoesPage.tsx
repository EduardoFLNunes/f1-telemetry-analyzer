/**
 * Sessões (pedidos 29 e 30): o início do app, como no protótipo A.
 *
 * - O hero no topo.
 * - As sessões do relatório de evolução (`/api/evolucao/*`), a mais nova em
 *   cima: os números da sessão, uma marca por volta válida e o atalho para a
 *   melhor volta na tela Volta.
 * - Mediana e melhor volta por sessão, com o critério do ADR 0015.
 * - As gravações que ainda não entraram no relatório (`/api/sessions` menos as
 *   gravações dos JSONs de sessão): voltas válidas e melhor volta vêm da
 *   conferência da Coleta, a mesma régua do store v2. Gravação não conferida
 *   diz isso, em vez de mostrar o tempo medido de outro jeito.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import type { EstadoDoApp } from '../hooks/useEstadoDoApp';
import { hashDaRota } from '../navegacao/rotas';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { HeroSessoes } from '../components/sessoes/HeroSessoes';
import { PainelVidro } from '../components/ui/base';
import { dataCurtaDaSessao, formatarTempo, resumoDaConferencia, type ResumoConferido } from '../components/sessoes/dadosDoHero';
import { useSessoesDoRelatorio, type Resumo, type Sessao } from '../volta/dados';
import { nf, nomeDaSessao, sg, tempo } from '../volta/formato';
import { FaixaDeVoltas, GraficoTendencia } from '../evolucao/Graficos';

type Linha = {
  id: string;
  quando: string | null;
  carro: string | null;
  voltasGravadas: number;
  conferida: ResumoConferido | null;
};

const GravacoesFora: React.FC<{ pronto: boolean; noRelatorio: Set<string> | null }> = ({ pronto, noRelatorio }) => {
  const [linhas, setLinhas] = useState<Linha[] | null>(null);
  const [falhou, setFalhou] = useState(false);

  useEffect(() => {
    if (!pronto || noRelatorio === null) return undefined;
    let cancelado = false;
    const ler = async () => {
      try {
        const [sessoes, conferencias] = await Promise.all([
          api.getSessions(8),
          api.listColetaVerificacoes().catch(() => ({ verificacoes: [] })),
        ]);
        const conferidas = new Set((conferencias?.verificacoes || []).filter((v: any) => v?.final !== false).map((v: any) => v.sessao));
        const lista: any[] = (Array.isArray(sessoes?.sessions) ? sessoes.sessions : []).filter((x: any) => !noRelatorio.has(x.sessionId));
        const novas: Linha[] = await Promise.all(lista.map(async (s) => {
          let conferida: ResumoConferido | null = null;
          if (conferidas.has(s.sessionId)) {
            try {
              const r = await api.getColetaVerificacao(s.sessionId);
              if (r?.estado === 'pronta') conferida = resumoDaConferencia(r.resultado);
            } catch {
              conferida = null;
            }
          }
          return {
            id: s.sessionId,
            quando: dataCurtaDaSessao(s.startedAt),
            carro: s.car ?? null,
            voltasGravadas: Array.isArray(s.laps) ? s.laps.length : 0,
            conferida,
          };
        }));
        if (!cancelado) {
          setLinhas(novas);
          setFalhou(false);
        }
      } catch {
        if (!cancelado) setFalhou(true);
      }
    };
    ler();
    const timer = window.setInterval(ler, 30_000);
    return () => {
      cancelado = true;
      window.clearInterval(timer);
    };
  }, [pronto, noRelatorio]);

  return (
    <PainelVidro id="gravacoes-fora" titulo="Gravações fora do relatório" nota="voltas válidas e melhor volta pela conferência da Coleta">
      <p className="texto-apoio" style={{ margin: 0 }}>
        Entram no relatório de evolução quando o <span className="dado">atualizar_coach</span> roda, com o app fechado.
      </p>
      {!pronto || noRelatorio === null ? (
        <p className="texto-fraco" style={{ margin: 0 }}>Aguardando o backend.</p>
      ) : falhou ? (
        <p className="texto-fraco" style={{ margin: 0 }}>O backend não devolveu as sessões.</p>
      ) : linhas === null ? (
        <p className="texto-fraco" style={{ margin: 0 }}>Lendo as sessões…</p>
      ) : linhas.length === 0 ? (
        <p className="texto-fraco" style={{ margin: 0 }}>Nenhuma: as gravações recentes já estão no relatório.</p>
      ) : (
        <div className="superficie tabela-caixa">
          <table className="tabela" style={{ minWidth: 640 }}>
            <thead>
              <tr>
                <th scope="col">Sessão</th>
                <th scope="col">Carro</th>
                <th scope="col" className="num">Voltas gravadas</th>
                <th scope="col" className="num">Voltas válidas</th>
                <th scope="col" className="num">Melhor</th>
              </tr>
            </thead>
            <tbody>
              {linhas.map((l) => (
                <tr key={l.id}>
                  <td className="dado" title={l.id}>{l.quando ?? l.id}</td>
                  <td className="texto-apoio">{l.carro ?? 'não gravado'}</td>
                  <td className="num">{l.voltasGravadas}</td>
                  <td className="num">{l.conferida ? l.conferida.voltasValidas : <a href={hashDaRota('coleta')} className="texto-fraco">conferir</a>}</td>
                  <td className="num">{l.conferida?.melhorS != null ? formatarTempo(l.conferida.melhorS) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </PainelVidro>
  );
};

/** Uma sessão do relatório, como o `sescard` do protótipo. */
const CartaoDaSessao: React.FC<{ s: Sessao; doResumo: Resumo['sessoes'][number] | undefined; tempoIa: number | null }> = ({ s, doResumo, tempoIa }) => {
  const melhor = [...s.voltas].sort((a, b) => a.tempo_s - b.tempo_s)[0];
  const consistentes = s.curvas.filter((c) => c.situacao === 'diferenca_consistente').length;
  return (
    <div className="cartao-sessao">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0 }}>
        <h3 className="titulo-cartao">{nomeDaSessao(s.sessao)}</h3>
        <div className="fatos dado">
          <span>{s.resumo.voltas} voltas</span>
          <span>melhor {tempo(s.resumo.melhor_s)}</span>
          <span>mediana {tempo(s.resumo.mediana_s)}</span>
          {doResumo?.desvio_s !== null && doResumo?.desvio_s !== undefined && <span>desvio {nf(doResumo.desvio_s, 3)} s</span>}
          <span>mediana {sg(s.resumo.mediana_s - s.resumo.volta_da_ia_s, 3)} s da IA</span>
          <span>{consistentes} de {s.curvas.length} curvas com diferença consistente</span>
        </div>
        <FaixaDeVoltas voltas={s.voltas} tempoIa={tempoIa} />
      </div>
      {melhor && (
        <a className="botao" href={hashDaRota('volta', melhor.volta)}>
          Ver a melhor volta
        </a>
      )}
    </div>
  );
};

const SessoesDoRelatorio: React.FC = () => {
  const relatorio = useSessoesDoRelatorio();
  const resumo = relatorio.dado?.resumo;
  const sessoes = relatorio.dado?.sessoes ?? [];
  const tempoIa = resumo?.referencia?.tempo_s ?? null;
  const a15 = resumo?.criterio_adr_0015;
  if (relatorio.erro) {
    return (
      <PainelVidro titulo="Sessões no relatório">
        <p className="texto-apoio" style={{ margin: 0 }}>Sem dados: {relatorio.erro}</p>
      </PainelVidro>
    );
  }
  return (
    <>
      <PainelVidro
        titulo="Sessões no relatório"
        nota={resumo ? `${sessoes.length} sessões · ${sessoes.reduce((n, x) => n + x.voltas.length, 0)} voltas válidas` : undefined}
      >
        {!resumo ? (
          <p className="texto-fraco" style={{ margin: 0 }}>Lendo o relatório de evolução…</p>
        ) : (
          <div className="lista-sessoes">
            {[...sessoes].reverse().map((x) => (
              <CartaoDaSessao key={x.sessao} s={x} doResumo={resumo.sessoes.find((r) => r.sessao === x.sessao)} tempoIa={tempoIa} />
            ))}
          </div>
        )}
      </PainelVidro>
      {resumo && (
        <PainelVidro titulo="Mediana e melhor volta por sessão">
          <p className="texto-apoio" style={{ margin: 0 }}>
            Linha cheia: mediana. Tracejada: melhor volta. A volta da IA é a referência.
            {resumo.tendencia_mediana_s_por_sessao !== null && <> Tendência da mediana: {sg(resumo.tendencia_mediana_s_por_sessao, 3)} s por sessão.</>}
            {a15 && (
              <>
                {' '}Critério do ADR 0015: {a15.estabilizou ? 'estabilizou' : 'ainda variando'} (amplitude{' '}
                {a15.amplitude_s === null ? '—' : `${nf(a15.amplitude_s, 3)} s`}, limite {nf(a15.limite_s, 1)} s).
              </>
            )}
          </p>
          <GraficoTendencia sessoes={resumo.sessoes} tempoIa={tempoIa} />
        </PainelVidro>
      )}
    </>
  );
};

export const SessoesPage: React.FC<{ estado: EstadoDoApp }> = ({ estado }) => {
  const relatorio = useSessoesDoRelatorio();
  // Sem o relatório (erro), todas as gravações recentes contam como fora dele.
  const noRelatorio = useMemo(
    () => (relatorio.dado ? new Set(relatorio.dado.sessoes.flatMap((x) => x.gravacoes)) : relatorio.erro ? new Set<string>() : null),
    [relatorio.dado, relatorio.erro],
  );
  return (
    <ErrorBoundary>
      <div className="tela-conteudo">
        <HeroSessoes estado={estado} />
        <SessoesDoRelatorio />
        <GravacoesFora pronto={estado.backend.fase === 'pronto'} noRelatorio={noRelatorio} />
      </div>
    </ErrorBoundary>
  );
};

export default SessoesPage;
