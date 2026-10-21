/**
 * A "Volta com fantasma" ao vivo (pedido 31, Parte D.1), com o mesmo componente
 * da tela Volta:
 *
 * - o carro na posição atual, sobre a pista tratada (as camadas do cache);
 * - o traçado da volta em andamento, colorido pelo pedal;
 * - o fantasma da referência escolhida na Coleta (volta da IA ou sua melhor),
 *   posicionado pelo tempo.
 *
 * Pedido 35 (Parte D): o mapa não trava mais.
 *
 * - **Só os pontos novos:** a cada 30 ms (até 33 vezes por segundo) a tela pede
 *   `/api/live/volta/novos`; a volta inteira vem só na abertura e numa volta nova.
 * - **Fora do React:** os pontos ficam num acumulador (`AcumuladorAoVivo`); o
 *   componente só volta a renderizar quando o estado muda (sem dados, a volta nova).
 *   O painel de leitura acompanha 5 vezes por segundo.
 * - **O carro anda liso:** a cada quadro da tela, entre duas posições, o carro anda
 *   pela geometria oficial na velocidade dele (só desenho: a posição continua sendo
 *   a projeção do coach). O fantasma precisa do relógio da volta, que só existe
 *   depois de uma passagem pela linha.
 */
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api/client';
import { PainelVidro } from '../components/ui/base';
import { Fantasma, type FonteAoVivo } from '../volta/Fantasma';
import type { VoltaDoStore } from '../volta/dados';
import { lerCamadasDaPista, lerGeometria, lerVolta, useLeitura, useSessoesDoRelatorio } from '../volta/dados';
import { useEstadoDaVolta } from '../volta/estado';
import { curvasDoRelatorio } from '../volta/medidas';
import { AcumuladorAoVivo, type RespostaNovos } from './voltaAoVivo';

const PERIODO_MS = 30;              // um relógio fixo de 30 ms, sem pedir de novo com uma leitura em andamento: até 33 por segundo
const PERIODO_DO_PAINEL_MS = 200;   // o painel de leitura (React), 5 vezes por segundo
const MAXIMO_A_FRENTE_S = 0.25;     // entre duas posições, o carro anda no máximo isto à frente
const SALTO_M = 30;                 // mais que isto entre o desenho e a posição: pula (a linha, um reset)

type Situacao = { disponivel: boolean; desdeALinha: boolean; volta: number | null; motivo?: string };

export const FantasmaAoVivo: React.FC<{ pronto: boolean }> = ({ pronto }) => {
  const [situacao, setSituacao] = useState<Situacao | null>(null);
  const [volta, setVolta] = useState<VoltaDoStore | null>(null);
  const geometria = useLeitura(pronto ? 'geometria' : null, lerGeometria);
  const camadas = useLeitura(pronto ? 'camadas' : null, lerCamadasDaPista);
  const relatorio = useSessoesDoRelatorio();
  const escolha = useLeitura(pronto ? 'coach-escolha' : null, async () => {
    const antes = await api.getColetaAntes();
    const tipo = antes?.coach?.referencia === 'minha_melhor' ? 'minha_melhor' : 'volta_ia';
    return { tipo, lapId: antes?.coach?.modelo?.referencias?.[tipo]?.volta ?? null } as { tipo: string; lapId: string | null };
  });
  const lapRef = escolha.dado?.lapId ?? null;
  const ref = useLeitura(lapRef ? `volta:${lapRef}` : null, () => lerVolta(lapRef as string));
  const geo = geometria.dado;

  // O que muda a cada leitura fica aqui, fora do estado do React.
  const acumulador = useRef(new AcumuladorAoVivo());
  const vivo = useRef({ volta: null as VoltaDoStore | null, versaoDosDados: 0, sRecebido: 0, vRecebida: 0, tRecebido: 0,
    sDesenho: null as number | null, quadros: 0, posicoes: 0 });
  const fonte = useRef<FonteAoVivo | null>(null);
  fonte.current = useMemo<FonteAoVivo>(() => ({
    versao: () => vivo.current.versaoDosDados,
    s: () => {
      const v = vivo.current;
      const dt = Math.min((performance.now() - v.tRecebido) / 1000, MAXIMO_A_FRENTE_S);
      const alvo = v.sRecebido + (Math.max(v.vRecebida, 0) / 3.6) * dt;
      const antes = v.sDesenho;
      v.sDesenho = antes === null || Math.abs(alvo - antes) > SALTO_M ? alvo : Math.max(antes, antes + (alvo - antes) * 0.5);
      v.quadros += 1;
      if (v.sDesenho !== antes) v.posicoes += 1;
      return v.sDesenho;
    },
  }), []);

  useEffect(() => {
    if (!pronto || !geo) return undefined;
    let cancelado = false;
    let lendo = false;
    let ultimoPainel = 0;
    const { setS, setTocando } = useEstadoDaVolta.getState();
    setTocando(true); // a câmera gira suave, como no replay
    // Para a medição do pedido 35 (Parte D): quadros e posições desenhadas desde a abertura.
    (window as any).__mapaAoVivo = { get quadros() { return vivo.current.quadros; }, get posicoes() { return vivo.current.posicoes; } };
    const ler = async () => {
      if (lendo) return;
      lendo = true;
      const acc = acumulador.current;
      try {
        const r = (await api.getLiveVoltaNovos(acc.versao, acc.seq)) as RespostaNovos;
        if (cancelado) return;
        const mudou = acc.aplicar(r);
        const cab = acc.cabecalho;
        const nova: Situacao = cab
          ? { disponivel: true, desdeALinha: cab.desdeALinha, volta: cab.volta }
          : { disponivel: false, desdeALinha: false, volta: null, motivo: (r as any)?.motivo };
        setSituacao((antiga) => (antiga && antiga.disponivel === nova.disponivel && antiga.desdeALinha === nova.desdeALinha
          && antiga.volta === nova.volta && antiga.motivo === nova.motivo ? antiga : nova));
        if (mudou && cab) {
          const v = vivo.current;
          const montada = acc.volta(geo.geometryId);
          if (montada) {
            if (v.volta && v.volta.lapId === montada.lapId) {
              // A mesma volta: troca os dados no mesmo objeto (o componente não renderiza de novo).
              v.volta.linhas = montada.linhas;
              v.volta.tempoS = montada.tempoS;
            } else {
              v.volta = montada;
              setVolta(montada);
            }
            v.versaoDosDados += 1;
          }
          const carro = acc.carro;
          if (carro) {
            v.sRecebido = carro.s;
            v.vRecebida = carro.velocidadeKmh ?? 0;
            v.tRecebido = performance.now();
          }
          const agora = performance.now();
          if (agora - ultimoPainel >= PERIODO_DO_PAINEL_MS && v.sDesenho !== null) {
            ultimoPainel = agora;
            setS(v.sDesenho);
          }
        }
      } catch {
        if (!cancelado) setSituacao({ disponivel: false, desdeALinha: false, volta: null, motivo: 'o backend não respondeu' });
      }
      lendo = false;
    };
    ler();
    const relogio = window.setInterval(ler, PERIODO_MS);
    return () => {
      cancelado = true;
      window.clearInterval(relogio);
      useEstadoDaVolta.getState().setTocando(false);
    };
  }, [pronto, geo]);

  const grade = volta ? { n: volta.pontosDaGrade, comprimento: volta.comprimentoM, passo: volta.passoM } : null;
  const sessoes = relatorio.dado?.sessoes ?? [];
  const curvas = useMemo(() => (grade && sessoes.length ? curvasDoRelatorio(grade, sessoes[0].curvas) : []), [grade?.n, grade?.passo, sessoes]); // eslint-disable-line react-hooks/exhaustive-deps

  let motivo: string | null = null;
  if (!pronto) motivo = 'aguardando o backend';
  else if (geometria.erro) motivo = `sem a geometria oficial: ${geometria.erro}`;
  else if (escolha.dado && !lapRef) motivo = 'o coach não tem a referência escolhida na Coleta';
  else if (ref.erro) motivo = `sem a volta de referência: ${ref.erro}`;
  else if (!situacao || !situacao.disponivel) motivo = situacao?.motivo ?? 'sem quadros do jogo';
  else if (!situacao.desdeALinha) motivo = 'o fantasma aparece depois da próxima passagem pela linha: o relógio da volta começa nela';

  if (motivo || !volta || !grade || !geo || !ref.dado || !curvas.length) {
    return (
      <PainelVidro titulo="Volta com fantasma">
        <p className="texto-apoio" style={{ margin: 0 }}>
          {motivo ? `Sem dados: ${motivo}.` : 'Lendo a geometria oficial, a referência e a volta…'}
        </p>
      </PainelVidro>
    );
  }
  return (
    <Fantasma
      grade={grade}
      geometria={geo}
      curvas={curvas}
      volta={volta}
      voltaRef={ref.dado}
      referencia={escolha.dado?.tipo === 'minha_melhor' ? 'melhor' : 'ia'}
      camadas={camadas.dado}
      aoVivo
      fonteAoVivo={fonte}
    />
  );
};
