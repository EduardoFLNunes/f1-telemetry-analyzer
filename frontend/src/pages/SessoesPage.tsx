/**
 * Sessões (pedido 29): o início do app. O hero no topo e as sessões gravadas
 * embaixo, no lugar da antiga página inicial.
 *
 * A lista de sessões é a do gravador (`/api/sessions`); voltas válidas e
 * melhor volta vêm da conferência da Coleta, a mesma régua do store v2. Sessão
 * não conferida diz isso, em vez de mostrar o tempo medido de outro jeito.
 * O redesenho completo desta tela é o pedido 5 do redesenho.
 */
import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { EstadoDoApp } from '../hooks/useEstadoDoApp';
import { hashDaRota } from '../navegacao/rotas';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { HeroSessoes } from '../components/sessoes/HeroSessoes';
import { PainelVidro } from '../components/ui/base';
import { dataCurtaDaSessao, formatarTempo, resumoDaConferencia, type ResumoConferido } from '../components/sessoes/dadosDoHero';

type Linha = {
  id: string;
  quando: string | null;
  carro: string | null;
  voltasGravadas: number;
  conferida: ResumoConferido | null;
};

const SessoesGravadas: React.FC<{ pronto: boolean }> = ({ pronto }) => {
  const [linhas, setLinhas] = useState<Linha[] | null>(null);
  const [falhou, setFalhou] = useState(false);

  useEffect(() => {
    if (!pronto) return undefined;
    let cancelado = false;
    const ler = async () => {
      try {
        const [sessoes, conferencias] = await Promise.all([
          api.getSessions(8),
          api.listColetaVerificacoes().catch(() => ({ verificacoes: [] })),
        ]);
        const conferidas = new Set((conferencias?.verificacoes || []).filter((v: any) => v?.final !== false).map((v: any) => v.sessao));
        const lista: any[] = Array.isArray(sessoes?.sessions) ? sessoes.sessions : [];
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
  }, [pronto]);

  return (
    <PainelVidro id="sessoes-gravadas" titulo="Sessões gravadas" nota="voltas válidas e melhor volta pela conferência da Coleta">
      {!pronto ? (
        <p className="texto-fraco" style={{ margin: 0 }}>Aguardando o backend.</p>
      ) : falhou ? (
        <p className="texto-fraco" style={{ margin: 0 }}>O backend não devolveu as sessões.</p>
      ) : linhas === null ? (
        <p className="texto-fraco" style={{ margin: 0 }}>Lendo as sessões…</p>
      ) : linhas.length === 0 ? (
        <p className="texto-fraco" style={{ margin: 0 }}>Nenhuma sessão gravada ainda. Abra o Assetto Corsa e entre na pista.</p>
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

export const SessoesPage: React.FC<{ estado: EstadoDoApp }> = ({ estado }) => (
  <ErrorBoundary>
    <div className="tela-conteudo">
      <HeroSessoes estado={estado} />
      <SessoesGravadas pronto={estado.backend.fase === 'pronto'} />
    </div>
  </ErrorBoundary>
);

export default SessoesPage;
