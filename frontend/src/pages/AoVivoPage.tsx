/**
 * Ao vivo (pedidos 29 e 31): a sessão em andamento, como o rádio do engenheiro.
 *
 * - Volta com fantasma: o mesmo componente da tela Volta, com o carro na
 *   posição atual (a projeção do coach na geometria oficial), o traçado da volta
 *   em andamento e o fantasma da referência escolhida (`/api/live/volta`).
 * - Rádio: as mensagens que o backend entregou (`/api/radio/mensagens`), com o
 *   texto pronto (o mesmo do app do jogo), a hora, o ponto da pista e o áudio.
 * - Gravação e canais: `/api/coleta/ao-vivo` (pedido 28), a cada 2 s.
 */
import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { EstadoDoApp } from '../hooks/useEstadoDoApp';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { CartaoNumero, EtiquetaEstado, PainelVidro, type Tom } from '../components/ui/base';
import { RadioAoVivo } from '../aoVivo/RadioAoVivo';
import { GradeDaSessaoAoVivo } from '../aoVivo/GradeDaSessao';
import { FantasmaAoVivo } from '../aoVivo/FantasmaAoVivo';
import { formatarNumero, ROTULO_ESTADO, tomDoEstado, type EstadoCanal } from '../utils/coleta';

function usePeriodico<T>(ler: () => Promise<T>, ms: number, ligado: boolean): [T | null, boolean] {
  const [dado, setDado] = useState<T | null>(null);
  const [falhou, setFalhou] = useState(false);
  useEffect(() => {
    if (!ligado) return undefined;
    let cancelado = false;
    const tick = async () => {
      try {
        const d = await ler();
        if (!cancelado) {
          setDado(d);
          setFalhou(false);
        }
      } catch {
        if (!cancelado) setFalhou(true);
      }
    };
    tick();
    const timer = window.setInterval(tick, ms);
    return () => {
      cancelado = true;
      window.clearInterval(timer);
    };
  }, [ler, ms, ligado]);
  return [dado, falhou];
}

const TOM: Record<ReturnType<typeof tomDoEstado>, Tom> = { ok: 'ok', aviso: 'aviso', ruim: 'erro', neutro: 'neutro' };

function quemPilota(aoVivo: any): string | null {
  if (!aoVivo?.gravando || !aoVivo?.quadros) return null;
  if (aoVivo.indicadorIA === false) return 'você';
  if (aoVivo.indicadorIA === true) return 'a IA';
  return 'sem indicador';
}

export const AoVivoPage: React.FC<{ estado: EstadoDoApp }> = ({ estado }) => {
  const pronto = estado.backend.fase === 'pronto';
  const [aoVivo, aoVivoFalhou] = usePeriodico(api.getColetaAoVivo, 2000, pronto);
  const itens: any[] = aoVivo?.itens || [];
  const grupos: any[] = aoVivo?.grupos || [];
  const gravando = Boolean(aoVivo?.gravando);

  return (
    <ErrorBoundary>
      <div className="tela-conteudo">
        <header className="cabecalho-tela">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div className="sobrancelha">Interlagos{aoVivo?.carro ? ` · ${aoVivo.carro}` : ''}</div>
            <h1 className="titulo-tela">Ao vivo</h1>
          </div>
          {gravando ? (
            <div className="vidro" role="status" style={{ display: 'inline-flex', alignItems: 'center', gap: 12, padding: '10px 16px', borderRadius: 12, background: 'var(--vermelho-fundo)', borderColor: 'var(--vermelho-borda)' }}>
              <span className="ponto pulso" style={{ width: 10, height: 10, background: 'var(--vermelho)' }} />
              <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.25 }}>
                <b style={{ fontSize: 15 }}>Gravando</b>
                <span className="dado texto-apoio" style={{ fontSize: 12 }}>{aoVivo?.sessao ?? 'sessão nova'}</span>
              </div>
            </div>
          ) : (
            <EtiquetaEstado tom={estado.capturaLiberada ? 'ok' : 'neutro'} estado={estado.capturaLiberada ? 'ok' : 'sem_dados'}>
              {!pronto ? 'aguardando o backend' : estado.capturaLiberada ? 'jogo conectado, sem gravação' : `sem sessão: ${estado.motivoCaptura ?? 'o jogo não está pronto'}`}
            </EtiquetaEstado>
          )}
        </header>

        <FantasmaAoVivo pronto={pronto} />

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'flex-start' }}>
          <PainelVidro id="ao-vivo-canais" titulo="Gravação e canais" nota="/api/coleta/ao-vivo · últimos segundos" style={{ flex: '999 1 560px', minWidth: 0 }}>
            {aoVivoFalhou && <p className="texto-fraco" style={{ margin: 0 }}>O backend não respondeu ao estado ao vivo.</p>}
            <div className="grade-cartoes" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))' }}>
              <CartaoNumero rotulo="Taxa medida" valor={aoVivo?.taxaHz != null ? `${formatarNumero(aoVivo.taxaHz, 1)} Hz` : null} />
              <CartaoNumero rotulo="Amostras escritas" valor={aoVivo?.gravador?.amostrasEscritas != null && gravando ? Number(aoVivo.gravador.amostrasEscritas).toLocaleString('pt-BR') : null} />
              <CartaoNumero rotulo="Descartadas" valor={gravando && aoVivo?.gravador?.descartadas != null ? String(aoVivo.gravador.descartadas) : null} cor={aoVivo?.gravador?.descartadas ? 'perda' : null} />
              <CartaoNumero rotulo="Fila do gravador" valor={gravando && aoVivo?.gravador?.fila != null ? String(aoVivo.gravador.fila) : null} />
              <CartaoNumero rotulo="No volante" valor={quemPilota(aoVivo)} />
            </div>
            <div className="superficie" style={{ overflow: 'hidden' }}>
              {grupos.length === 0 && <p className="texto-fraco" style={{ margin: 0, padding: '12px 16px' }}>{pronto ? 'Lendo o estado dos canais…' : 'Aguardando o backend.'}</p>}
              {grupos.map((g) => {
                const nomes = itens.filter((i) => i.grupo === g.id).map((i) => i.nome);
                return (
                  <div key={g.id} style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '8px 16px', padding: '12px 16px', borderBottom: '1px solid var(--linha-fraca)' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
                      <b style={{ fontWeight: 600 }}>{g.nome}</b>
                      <span className="texto-fraco">{nomes.slice(0, 5).join(', ')}{nomes.length > 5 ? ` e mais ${nomes.length - 5}` : ''}</span>
                    </div>
                    <EtiquetaEstado tom={TOM[tomDoEstado(g.estado)]} estado={g.estado}>
                      {ROTULO_ESTADO[g.estado as EstadoCanal] || g.estadoRotulo || g.estado}
                    </EtiquetaEstado>
                  </div>
                );
              })}
            </div>
          </PainelVidro>

          <PainelVidro id="ao-vivo-radio" titulo="Rádio" nota="nas retas: até 3 frases por volta, o resumo da volta e, a cada 3 voltas válidas, a análise" style={{ flex: '1 1 400px', minWidth: 0 }}>
            <RadioAoVivo pronto={pronto} />
            <span className="texto-fraco dado">/api/radio/mensagens · as 20 mais recentes</span>
            <GradeDaSessaoAoVivo pronto={pronto} />
          </PainelVidro>
        </div>
      </div>
    </ErrorBoundary>
  );
};

export default AoVivoPage;
