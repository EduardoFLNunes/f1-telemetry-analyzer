/**
 * Volta (pedido 30): uma volta contra a referência, na organização da opção A
 * do protótipo (`frontend/mockups/prototipo_dashboard.html`).
 *
 * - Barra de contexto: sessão, volta, tempo e a diferença para a referência.
 * - Escolha da sessão, da volta e da referência (volta da IA ou sua melhor).
 * - Volta com fantasma, com o replay.
 * - Mapa dos 60 microssetores e a tabela das 14 curvas, lado a lado.
 * - Diferença acumulada por distância, velocidade, acelerador e freio.
 *
 * Tudo vem das rotas de leitura (`/api/evolucao/*`, `/api/coach/referencias`,
 * `/api/store/voltas/{lap}`, `/api/geometria/oficial`) e das camadas da pista do
 * cache (`/api/track/geometry`). As medidas são as do relatório de evolução
 * (`volta/medidas.ts`, conferidas contra o `por_volta` oficial).
 *
 * Endereço: `#/volta/<lapId>`; `#/volta/ultima` abre a última volta do
 * relatório; sem volta, a melhor da sessão mais recente.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { PainelVidro } from '../components/ui/base';
import type { Tela } from '../navegacao/rotas';
import {
  gradeDaVolta,
  lerCamadasDaPista,
  lerGeometria,
  lerReferencias,
  lerVolta,
  useLeitura,
  useSessoesDoRelatorio,
  type Sessao,
  type VoltaDoStore,
} from '../volta/dados';
import { useEstadoDaVolta } from '../volta/estado';
import {
  curvaEm,
  curvasDoRelatorio,
  diferencaAcumulada,
  diferencaPorMicrossetor,
  medidasDasCurvas,
  tempoEm,
  valorEm,
} from '../volta/medidas';
import { nf, nomeDaSessao, numeroDaVolta, sg, tempo } from '../volta/formato';
import { EixoDeDistancia, GraficoPorDistancia } from '../volta/Graficos';
import { MapaMicrossetores } from '../volta/MapaMicrossetores';
import { TabelaDasCurvas } from '../volta/TabelaDasCurvas';
import { Fantasma } from '../volta/Fantasma';
import { frasesDosEventos, RadioDaVolta } from '../volta/RadioDaVolta';
import { api } from '../api/client';

type Referencia = 'ia' | 'melhor';

const NOME_DA_REFERENCIA: Record<Referencia, string> = { ia: 'volta da IA', melhor: 'sua melhor volta' };

function melhorDaSessao(s: Sessao): string | null {
  const v = [...s.voltas].sort((a, b) => a.tempo_s - b.tempo_s)[0];
  return v ? v.volta : null;
}

/** A última volta do relatório: a da gravação mais recente, com o maior número. */
function ultimaDoRelatorio(sessoes: Sessao[]): string | null {
  const todas = sessoes.flatMap((s) => s.voltas.map((v) => v.volta));
  return todas.sort().at(-1) ?? null;
}

function SemDados({ titulo, texto }: { titulo: string; texto: string }) {
  return (
    <PainelVidro titulo={titulo}>
      <p className="texto-apoio" style={{ margin: 0 }}>Sem dados: {texto}</p>
    </PainelVidro>
  );
}

export const VoltaPage: React.FC<{ sub: string | null; navegar: (tela: Tela, sub?: string | null) => void }> = ({ sub, navegar }) => {
  const relatorio = useSessoesDoRelatorio();
  const referencias = useLeitura('referencias', lerReferencias);
  const geometria = useLeitura('geometria', lerGeometria);
  const camadas = useLeitura('camadas', lerCamadasDaPista);
  const [referencia, setReferencia] = useState<Referencia>('ia');

  const sessoes = relatorio.dado?.sessoes ?? [];
  const lapId = useMemo(() => {
    if (sub && sub.includes('#')) return sub;
    if (!sessoes.length) return null;
    if (sub === 'ultima') return ultimaDoRelatorio(sessoes);
    return melhorDaSessao(sessoes[sessoes.length - 1]);
  }, [sub, sessoes]);
  const sessaoDaVolta = useMemo(() => sessoes.find((s) => s.voltas.some((v) => v.volta === lapId)) ?? null, [sessoes, lapId]);

  const lapIa = referencias.dado?.volta_ia?.volta ?? null;
  const lapMelhor = referencias.dado?.minha_melhor?.volta ?? null;
  const lapRef = referencia === 'ia' ? lapIa : lapMelhor;
  const volta = useLeitura(lapId ? `volta:${lapId}` : null, () => lerVolta(lapId as string));
  const voltaIa = useLeitura(lapIa ? `volta:${lapIa}` : null, () => lerVolta(lapIa as string));
  const voltaMelhor = useLeitura(lapMelhor ? `volta:${lapMelhor}` : null, () => lerVolta(lapMelhor as string));
  const ref = referencia === 'ia' ? voltaIa : voltaMelhor;
  const replayLapId = volta.dado?.replayLapId ?? null;
  const coach = useLeitura(replayLapId ? `coach:${replayLapId}` : null, () =>
    api.getLapCoaching(replayLapId as string).catch((e) => {
      // A rota responde 404 (com a frase em inglês) quando a gravação da volta não está na pasta de gravações.
      if (e?.response?.status === 404) throw new Error('a gravação desta volta não está na pasta de gravações do backend');
      throw e;
    }),
  );

  // Trocar de volta ou de referência desliga o replay e tira o cursor, como no protótipo.
  useEffect(() => {
    const { setS, setTocando } = useEstadoDaVolta.getState();
    setTocando(false);
    setS(null);
  }, [lapId, lapRef]);

  const v = volta.dado;
  const r = ref.dado;
  const geo = geometria.dado;
  const conta = useMemo(() => {
    if (!v || !r || !geo || !sessoes.length) return null;
    if (v.geometryId !== geo.geometryId || r.geometryId !== geo.geometryId) return { erro: 'a volta e a referência não estão na grade da geometria oficial' } as const;
    const g = gradeDaVolta(v);
    const curvas = curvasDoRelatorio(g, (sessaoDaVolta ?? sessoes[0]).curvas);
    return {
      erro: null,
      g,
      curvas,
      medidas: medidasDasCurvas(g, v.linhas, r.linhas, curvas),
      microssetores: diferencaPorMicrossetor(g, v.linhas, r.linhas, geo.bordasDosMicrossetores),
      acumulada: diferencaAcumulada(v.linhas, r.linhas),
    } as const;
  }, [v, r, geo, sessoes, sessaoDaVolta]);

  const frases = useMemo(() => (coach.dado && v ? frasesDosEventos(coach.dado.events, v.comprimentoM) : null), [coach.dado, v]);
  const medianas = referencia === 'ia' && sessaoDaVolta ? sessaoDaVolta.curvas.map((c) => c.perda_para_ia_s?.mediana ?? null) : null;
  const carregando = relatorio.carregando || referencias.carregando || geometria.carregando || volta.carregando || ref.carregando;
  const falha = relatorio.erro || referencias.erro || geometria.erro || volta.erro || ref.erro;
  const nomeRef = NOME_DA_REFERENCIA[referencia];
  const diferenca = v && r ? v.tempoS - r.tempoS : null;

  return (
    <ErrorBoundary>
      <div className="tela-conteudo">
        <section className="contexto-volta" aria-label="Volta escolhida">
          <div>
            <div className="rotulo">
              {sessaoDaVolta ? `Sessão ${nomeDaSessao(sessaoDaVolta.sessao)}` : 'Fora do relatório'}
              {lapId ? ` · volta ${numeroDaVolta(lapId)}` : ''}
            </div>
            <div className="numero-grande">{v ? tempo(v.tempoS) : '—'}</div>
            <div className="texto-fraco">tempo de volta, relógio do jogo</div>
          </div>
          <div>
            <div className="rotulo">Diferença</div>
            <div className={`numero-grande ${diferenca === null ? '' : diferenca > 0 ? 'cor-perda' : 'cor-ganho'}`}>
              {diferenca === null ? '—' : `${sg(diferenca, 3)} s`}
            </div>
            <div className="texto-fraco">{diferenca === null ? nomeRef : `${diferenca >= 0 ? 'acima' : 'abaixo'} da ${nomeRef}`}</div>
          </div>
        </section>

        <section className="contexto-volta" style={{ alignItems: 'flex-start', gap: '14px 36px' }}>
          <div role="group" aria-label="Sessão" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span className="rotulo">Sessão</span>
            <div className="chips">
              {sessoes.map((s) => (
                <button
                  key={s.sessao}
                  type="button"
                  className="chip"
                  aria-pressed={s.sessao === sessaoDaVolta?.sessao}
                  onClick={() => {
                    const melhor = melhorDaSessao(s);
                    if (melhor) navegar('volta', melhor);
                  }}
                >
                  {nomeDaSessao(s.sessao)}
                </button>
              ))}
            </div>
          </div>
          <div role="group" aria-label="Referência" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span className="rotulo">Comparar com</span>
            <div className="chips">
              <button type="button" className="chip" aria-pressed={referencia === 'ia'} disabled={!lapIa} onClick={() => setReferencia('ia')}>
                Volta da IA · {voltaIa.dado ? tempo(voltaIa.dado.tempoS) : '—'}
              </button>
              <button type="button" className="chip" aria-pressed={referencia === 'melhor'} disabled={!lapMelhor} onClick={() => setReferencia('melhor')}>
                Sua melhor · {voltaMelhor.dado ? tempo(voltaMelhor.dado.tempoS) : '—'}
              </button>
            </div>
          </div>
        </section>

        {sessaoDaVolta && (
          <section className="chips" aria-label="Voltas válidas da sessão" style={{ alignItems: 'center' }}>
            <span className="rotulo" style={{ marginRight: 6 }}>Voltas</span>
            {sessaoDaVolta.voltas.map((x) => (
              <button key={x.volta} type="button" className="chip" aria-pressed={x.volta === lapId} onClick={() => navegar('volta', x.volta)}>
                V{numeroDaVolta(x.volta)} · {tempo(x.tempo_s)}
              </button>
            ))}
          </section>
        )}

        {falha && <SemDados titulo="Volta" texto={falha} />}
        {!falha && !carregando && !lapId && <SemDados titulo="Volta" texto="o relatório de evolução ainda não tem voltas." />}
        {!falha && carregando && !conta && (
          <PainelVidro titulo="Volta com fantasma">
            <p className="texto-fraco" style={{ margin: 0 }}>Lendo a volta, a referência e a geometria oficial…</p>
          </PainelVidro>
        )}
        {conta?.erro && <SemDados titulo="Volta" texto={conta.erro} />}

        {conta && !conta.erro && v && r && geo && (
          <>
            <Fantasma
              key={`${v.lapId}|${r.lapId}`}
              grade={conta.g}
              geometria={geo}
              curvas={conta.curvas}
              volta={v}
              voltaRef={r}
              referencia={referencia}
              camadas={camadas.dado}
            >
              <RadioDaVolta
                frases={frases}
                curvas={conta.curvas}
                erro={coach.erro ?? (!coach.carregando && !replayLapId ? 'esta volta não tem a gravação ligada no store' : null)}
              />
            </Fantasma>
            <div className="grade-dupla">
              <PainelVidro
                titulo="Diferença por microssetor"
                acao={
                  <span className="legenda">
                    <span><i className="amostra" style={{ background: 'var(--ganho)' }} />ganhou</span>
                    <span><i className="amostra" style={{ background: 'var(--perda-fraca)' }} />perdeu pouco</span>
                    <span><i className="amostra" style={{ background: 'var(--perda)' }} />perdeu muito</span>
                  </span>
                }
              >
                <MapaMicrossetores geometria={geo} curvas={conta.curvas} microssetores={conta.microssetores} frases={frases} />
              </PainelVidro>
              <PainelVidro titulo={`As 14 curvas, contra a ${nomeRef}`}>
                <TabelaDasCurvas medidas={conta.medidas} medianas={medianas} diferencaDaVolta={v.tempoS - r.tempoS} referencia={referencia} />
              </PainelVidro>
            </div>
            <Tracos conta={conta} volta={v} ref_={r} nomeRef={nomeRef} />
            <footer className="texto-fraco dado">
              Fonte: store v2 (tempo pelo relógio do jogo), geometria oficial {geo.geometryId} e relatório de evolução. As comparações por curva
              repetem o método do relatório de evolução.
            </footer>
          </>
        )}
      </div>
    </ErrorBoundary>
  );
};

type Conta = {
  g: ReturnType<typeof gradeDaVolta>;
  curvas: ReturnType<typeof curvasDoRelatorio>;
  acumulada: number[];
};

/** Os traços por distância, como no `tracesPanel` do protótipo. */
function Tracos({ conta, volta, ref_: ref, nomeRef }: { conta: Conta; volta: VoltaDoStore; ref_: VoltaDoStore; nomeRef: string }) {
  const { g, curvas, acumulada } = conta;
  const L = g.comprimento;
  const eixo = useMemo(() => {
    let mn = Math.min(0, ...acumulada);
    let mx = Math.max(0.5, ...acumulada);
    mn = Math.floor(mn * 2) / 2 - (mn < 0 ? 0 : 0.2);
    mx = Math.ceil(mx);
    const marcas: Array<{ v: number; rotulo: string; forte?: boolean }> = [];
    const passo = mx - mn > 4 ? 2 : 1;
    for (let t = Math.ceil(mn); t <= mx; t += passo) marcas.push({ v: t, rotulo: `${sg(t, 0)} s`, forte: t === 0 });
    return { mn, mx, marcas };
  }, [acumulada]);
  const dica = (s: number) => {
    const d = tempoEm(g, volta.linhas, s) - tempoEm(g, ref.linhas, s);
    const c = curvaEm(curvas, s);
    return `${nf(s, 0)} m · ${c ? c.codigo : '—'} · ${sg(d, 3)} s · ${nf(valorEm(g, volta.linhas.velocidade, s), 0)} km/h (ref. ${nf(valorEm(g, ref.linhas.velocidade, s), 0)})`;
  };
  const voce = 'var(--voce)';
  const outra = 'var(--referencia)';
  const pedal = [
    { v: 0, rotulo: '0%' },
    { v: 1, rotulo: '100%' },
  ];
  return (
    <>
      <PainelVidro titulo={`Diferença acumulada para a ${nomeRef}`} nota="passe o mouse para ler; clique numa faixa para escolher a curva">
        <GraficoPorDistancia
          comprimento={L}
          passo={g.passo}
          altura={170}
          min={eixo.mn}
          max={eixo.mx}
          marcas={eixo.marcas}
          series={[{ valores: acumulada, cor: voce, largura: 2, area: true }]}
          curvas={curvas}
          rotulosDasCurvas
          rotulo={`Diferença acumulada para a ${nomeRef}`}
          dica={dica}
        />
      </PainelVidro>
      <PainelVidro
        titulo="Velocidade (km/h), acelerador e freio"
        acao={
          <span className="legenda">
            <span><i className="linha" style={{ borderColor: voce }} />volta {numeroDaVolta(volta.lapId)}</span>
            <span><i className="linha" style={{ borderColor: outra, borderTopStyle: 'dashed' }} />{nomeRef}</span>
          </span>
        }
      >
        <div>
          <GraficoPorDistancia
            comprimento={L}
            passo={g.passo}
            altura={180}
            min={60}
            max={300}
            marcas={[100, 150, 200, 250, 300].map((k) => ({ v: k, rotulo: String(k) }))}
            series={[
              { valores: ref.linhas.velocidade, cor: outra, largura: 1.3, tracejado: '5 4' },
              { valores: volta.linhas.velocidade, cor: voce, largura: 1.8 },
            ]}
            curvas={curvas}
            rotulo="Velocidade"
            dica={dica}
          />
          <div className="rotulo" style={{ marginTop: 4 }}>Acelerador</div>
          <GraficoPorDistancia
            comprimento={L}
            passo={g.passo}
            altura={64}
            min={0}
            max={1.05}
            marcas={pedal}
            series={[
              { valores: ref.linhas.acelerador, cor: outra, largura: 1.1, tracejado: '4 3' },
              { valores: volta.linhas.acelerador, cor: voce, largura: 1.5 },
            ]}
            curvas={curvas}
            rotulo="Acelerador"
            dica={dica}
          />
          <div className="rotulo">Freio</div>
          <GraficoPorDistancia
            comprimento={L}
            passo={g.passo}
            altura={64}
            min={0}
            max={1.05}
            marcas={pedal}
            series={[
              { valores: ref.linhas.freio, cor: outra, largura: 1.1, tracejado: '4 3' },
              { valores: volta.linhas.freio, cor: voce, largura: 1.5 },
            ]}
            curvas={curvas}
            rotulo="Freio"
            dica={dica}
          />
          <EixoDeDistancia comprimento={L} />
        </div>
      </PainelVidro>
    </>
  );
}

export default VoltaPage;
