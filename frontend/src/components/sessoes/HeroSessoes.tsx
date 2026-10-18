/**
 * O hero (pedido 29): o topo da tela Sessões, não uma tela de abertura.
 *
 * Enquanto o backend sobe, mostra a espera real (`/api/health`): os segundos
 * desde a abertura e as tentativas. Depois, os números, todos de dado real
 * (ver dadosDoHero.ts), e Interlagos com a sua melhor volta traçada.
 * Sem o dado, "sem dados"; nada é inventado no lugar.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../api/client';
import type { EstadoDoApp } from '../../hooks/useEstadoDoApp';
import { hashDaRota } from '../../navegacao/rotas';
import { CartaoNumero, EtiquetaEstado } from '../ui/base';
import { diferencaComSinal } from '../../utils/radio';
import { PistaHero, type PontoMapa } from './PistaHero';
import {
  dataCurtaDaSessao,
  dataDoNomeDaSessao,
  formatarTempo,
  partesDoLapId,
  resumoDaConferencia,
  trechoDaVolta,
  voltaPeloTempo,
  type ResumoConferido,
} from './dadosDoHero';

type Referencia = { volta: string | null; tempoS: number | null; carro: string | null };

type Dados = {
  pista: any | null;
  ultima: { id: string; quando: string | null } | null;
  sessoesLidas: boolean;
  conferencia: { estado: string; resumo: ResumoConferido | null } | null;
  minhaMelhor: Referencia | null;
  voltaIA: Referencia | null;
  coachConstruidoEm: string | null;
  carro: string | null;
  referenciasLidas: boolean;
  m1: { n: number; meta: number } | null;
  m1Lida: boolean;
  traco: PontoMapa[] | null;
};

const VAZIO: Dados = {
  pista: null,
  ultima: null,
  sessoesLidas: false,
  conferencia: null,
  minhaMelhor: null,
  voltaIA: null,
  coachConstruidoEm: null,
  carro: null,
  referenciasLidas: false,
  m1: null,
  m1Lida: false,
  traco: null,
};

const ALTURA_PISTA = 500;

function referencia(valor: any): Referencia | null {
  if (!valor || typeof valor !== 'object') return null;
  // Pedido 31, A.3: o tempo do store v2 (o mesmo da tela Volta e do relatório); o do modelo do coach só sem ele.
  const tempo = Number(valor.tempoStoreS ?? valor.tempoS);
  return { volta: valor.volta ?? null, tempoS: Number.isFinite(tempo) ? tempo : null, carro: valor.carro ?? null };
}

function dataDaReferencia(ref: Referencia | null): string | null {
  const partes = partesDoLapId(ref?.volta);
  if (!partes) return null;
  const data = dataDoNomeDaSessao(partes.sessao);
  return [data, partes.sequencia !== null ? `volta ${partes.sequencia}` : null].filter(Boolean).join(' · ') || null;
}

function dataDoModelo(valor: string | null): string | null {
  if (!valor) return null;
  const d = new Date(valor);
  if (Number.isNaN(d.getTime())) return null;
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`;
}

async function tracoDaReferencia(ref: Referencia | null): Promise<PontoMapa[] | null> {
  const partes = partesDoLapId(ref?.volta);
  if (!partes || ref?.tempoS == null) return null;
  const lista = await api.getSessionLaps(partes.sessao);
  const volta = voltaPeloTempo(Array.isArray(lista?.laps) ? lista.laps : [], ref.tempoS);
  if (!volta || !(volta as any).lapId) return null;
  const replay = await api.getOfflineLapReplay((volta as any).lapId, 3000);
  const trecho = trechoDaVolta(Array.isArray(replay?.samples) ? replay.samples : [], ref.tempoS);
  if (!trecho) return null;
  const pontos = trecho
    .map((s: any) => s?.mapPosition ?? (Number.isFinite(s?.x) && Number.isFinite(s?.y) ? { x: s.x, y: s.y } : null))
    .filter((p: any): p is PontoMapa => p && Number.isFinite(p.x) && Number.isFinite(p.y));
  return pontos.length > 10 ? pontos : null;
}

export const HeroSessoes: React.FC<{ estado: EstadoDoApp }> = ({ estado }) => {
  const [dados, setDados] = useState<Dados>(VAZIO);
  const [conferindo, setConferindo] = useState(false);
  const pronto = estado.backend.fase === 'pronto';
  const juntar = useCallback((parte: Partial<Dados>) => setDados((d) => ({ ...d, ...parte })), []);

  const lerConferencia = useCallback(async (id: string) => {
    try {
      const r = await api.getColetaVerificacao(id);
      juntar({ conferencia: { estado: r?.estado ?? 'erro', resumo: r?.estado === 'pronta' ? resumoDaConferencia(r.resultado) : null } });
      return r?.estado as string | undefined;
    } catch {
      juntar({ conferencia: { estado: 'erro', resumo: null } });
      return 'erro';
    }
  }, [juntar]);

  useEffect(() => {
    if (!pronto) return undefined;
    let cancelado = false;
    const seguro = <T,>(p: Promise<T>) => p.catch(() => null);

    seguro(api.getTrackGeometry()).then((g) => {
      if (!cancelado) juntar({ pista: g?.activeTrackReady ? g.track : null });
    });
    seguro(api.getSessions(8)).then(async (s) => {
      if (cancelado) return;
      const lista: any[] = Array.isArray(s?.sessions) ? s.sessions : [];
      const primeira = lista[0];
      juntar({ sessoesLidas: true, ultima: primeira ? { id: primeira.sessionId, quando: dataCurtaDaSessao(primeira.startedAt) } : null });
      if (primeira) await lerConferencia(primeira.sessionId);
    });
    seguro(api.getColetaAntes()).then(async (antes) => {
      if (cancelado) return;
      const refs = antes?.coach?.modelo?.referencias || {};
      const minhaMelhor = referencia(refs.minha_melhor);
      juntar({
        referenciasLidas: true,
        minhaMelhor,
        voltaIA: referencia(refs.volta_ia),
        coachConstruidoEm: antes?.coach?.modelo?.construidoEm ?? null,
        carro: minhaMelhor?.carro ?? antes?.jogo?.carroEsperado ?? null,
      });
      const traco = await seguro(tracoDaReferencia(minhaMelhor));
      if (!cancelado) juntar({ traco });
    });
    seguro(api.getColetaM1Oficial()).then((m) => {
      if (cancelado) return;
      juntar({ m1Lida: true, m1: m?.disponivel ? { n: Number(m.n), meta: Number(m.meta) } : null });
    });
    return () => {
      cancelado = true;
    };
  }, [pronto, juntar, lerConferencia]);

  const conferirAgora = async () => {
    if (!dados.ultima) return;
    setConferindo(true);
    try {
      await api.conferirSessao(dados.ultima.id);
      for (let i = 0; i < 120; i += 1) {
        // a conferência lê a sessão inteira; a rota diz quando terminou
        const e = await lerConferencia(dados.ultima.id);
        if (e !== 'conferindo') break;
        await new Promise((r) => window.setTimeout(r, 1500));
      }
    } finally {
      setConferindo(false);
    }
  };

  const fase = estado.backend.fase;
  const aguardando = fase !== 'pronto' ? 'aguardando o backend' : null;
  const { minhaMelhor, voltaIA } = dados;
  const diferencaIA = minhaMelhor?.tempoS != null && voltaIA?.tempoS != null ? minhaMelhor.tempoS - voltaIA.tempoS : null;
  const resumo = dados.conferencia?.resumo ?? null;

  let detalheUltima: React.ReactNode = aguardando ?? (dados.sessoesLidas ? 'sem dados' : 'lendo…');
  if (dados.ultima && dados.conferencia) {
    if (resumo) {
      detalheUltima = `${resumo.voltasValidas} ${resumo.voltasValidas === 1 ? 'volta válida' : 'voltas válidas'} · melhor ${resumo.melhorS != null ? formatarTempo(resumo.melhorS) : 'sem volta válida'}`;
    } else if (dados.conferencia.estado === 'nao_conferida') {
      detalheUltima = (
        <button type="button" className="botao botao--pequeno" onClick={conferirAgora} disabled={conferindo} style={{ marginTop: 4, alignSelf: 'flex-start' }}>
          {conferindo ? 'Conferindo…' : 'Conferir voltas e melhor volta'}
        </button>
      );
    } else if (dados.conferencia.estado === 'conferindo') {
      detalheUltima = 'conferindo as voltas…';
    } else {
      detalheUltima = 'conferência indisponível';
    }
  }

  let gravacao: React.ReactNode;
  if (fase === 'subindo') gravacao = null;
  else if (fase === 'caiu') gravacao = <EtiquetaEstado tom="erro">o backend parou de responder</EtiquetaEstado>;
  else if (estado.gravando) gravacao = <EtiquetaEstado tom="ok">gravando {estado.sessaoGravando ?? ''}</EtiquetaEstado>;
  else if (estado.capturaLiberada) gravacao = <EtiquetaEstado tom="ok">pronto para gravar: entre na pista</EtiquetaEstado>;
  else gravacao = <EtiquetaEstado tom="aviso" estado="parado">não grava ainda: {estado.motivoCaptura ?? 'o jogo não está pronto'}</EtiquetaEstado>;

  return (
    <section className="vidro hero" aria-labelledby="hero-titulo" aria-busy={fase === 'subindo'}>
      <div className="hero-texto">
        <div className="sobrancelha">Interlagos{dados.carro ? ` · ${dados.carro}` : ''}</div>
        <h1 id="hero-titulo" className="hero-titulo">Sistema de Telemetria e Otimização de Trajetórias</h1>

        {fase === 'subindo' ? (
          <div className="superficie hero-subindo" role="status">
            <div className="hero-subindo__titulo">
              <span className="ponto pulso" style={{ background: 'var(--estado-aviso)' }} />
              Ligando o backend
            </div>
            <div className="dado texto-apoio" style={{ fontSize: 12.5 }}>
              /api/health ainda não respondeu · {estado.backend.segundos} s desde a abertura · {estado.backend.tentativas}{' '}
              {estado.backend.tentativas === 1 ? 'tentativa' : 'tentativas'}
            </div>
            <div className="texto-fraco">
              Na primeira abertura leva até cerca de 40 s. As telas já podem ser usadas; os números chegam quando ele responder.
            </div>
          </div>
        ) : (
          <div className="hero-estados">
            {fase === 'pronto' && (
              <EtiquetaEstado tom="ok">
                backend pronto · {estado.backend.versao ?? 'versão desconhecida'}
                {estado.backend.segundos >= 2 ? ` · respondeu em ${estado.backend.segundos} s` : ''}
              </EtiquetaEstado>
            )}
            {gravacao}
          </div>
        )}

        <div className="grade-cartoes">
          <CartaoNumero rotulo="Última sessão" valor={dados.ultima?.quando ?? null} detalhe={detalheUltima} />
          <CartaoNumero
            rotulo="Sua melhor volta"
            valor={minhaMelhor?.tempoS != null ? formatarTempo(minhaMelhor.tempoS) : null}
            cor={minhaMelhor?.tempoS != null ? 'tempo-verde' : null}
            detalhe={aguardando ?? (minhaMelhor
              ? [dataDaReferencia(minhaMelhor), dataDoModelo(dados.coachConstruidoEm) && `coach de ${dataDoModelo(dados.coachConstruidoEm)}`].filter(Boolean).join(' · ')
              : dados.referenciasLidas ? 'sem dados' : 'lendo…')}
          />
          <CartaoNumero
            rotulo="Volta da IA"
            valor={voltaIA?.tempoS != null ? formatarTempo(voltaIA.tempoS) : null}
            detalhe={aguardando ?? (voltaIA ? (
              <>
                {dataDaReferencia(voltaIA)}
                {diferencaIA != null && (
                  <>
                    {' · sua melhor '}
                    <span className="cor-perda">{diferencaComSinal(diferencaIA, 3)}</span>
                  </>
                )}
              </>
            ) : dados.referenciasLidas ? 'sem dados' : 'lendo…')}
          />
          <CartaoNumero
            rotulo="Modelo do carro (M1)"
            valor={dados.m1 ? `${dados.m1.n} de ${dados.m1.meta}` : null}
            detalhe={aguardando ?? (dados.m1 ? 'sessões com os canais físicos' : dados.m1Lida ? 'sem dados' : 'lendo…')}
          />
        </div>

        <div className="hero-atalhos">
          <a className="botao botao--primario" href={hashDaRota('coleta')}>
            Coleta de dados
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M3 8h10M9 4l4 4-4 4" />
            </svg>
          </a>
          <a className="botao" href={hashDaRota('volta', 'ultima')}>Última volta</a>
          <a className="botao" href={hashDaRota('evolucao')}>Evolução</a>
        </div>
      </div>

      <figure className="hero-pista">
        <PistaHero
          pista={dados.pista}
          volta={dados.traco}
          altura={ALTURA_PISTA}
          descricao={dados.traco ? 'Interlagos no sentido anti-horário, com a sua melhor volta traçada' : 'Interlagos no sentido anti-horário'}
        />
        <figcaption>
          {dados.traco && minhaMelhor?.tempoS != null
            ? `sua melhor volta · ${formatarTempo(minhaMelhor.tempoS)} · sentido anti-horário`
            : fase === 'pronto' && dados.referenciasLidas
              ? 'sem a sua melhor volta para traçar'
              : 'Interlagos · sentido anti-horário'}
        </figcaption>
      </figure>
    </section>
  );
};

export default HeroSessoes;
