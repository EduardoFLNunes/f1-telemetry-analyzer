/**
 * A "Volta com fantasma" ao vivo (pedido 31, Parte D.1), com o mesmo componente
 * da tela Volta:
 *
 * - o carro na posição atual, sobre a pista tratada (as camadas do cache);
 * - o traçado da volta em andamento, colorido pelo pedal;
 * - o fantasma da referência escolhida na Coleta (volta da IA ou sua melhor),
 *   posicionado pelo tempo.
 *
 * A posição é a projeção na geometria oficial que o coach já faz
 * (`/api/live/volta`, a cada 300 ms). O fantasma precisa do relógio da volta, que
 * só existe depois de uma passagem pela linha.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import { PainelVidro } from '../components/ui/base';
import { Fantasma } from '../volta/Fantasma';
import { lerCamadasDaPista, lerGeometria, lerVolta, useLeitura, useSessoesDoRelatorio } from '../volta/dados';
import { useEstadoDaVolta } from '../volta/estado';
import { curvasDoRelatorio } from '../volta/medidas';
import { voltaDoAoVivo, type VoltaDoBackend } from './voltaAoVivo';

const PERIODO_MS = 300;

export const FantasmaAoVivo: React.FC<{ pronto: boolean }> = ({ pronto }) => {
  const [aoVivo, setAoVivo] = useState<VoltaDoBackend | null>(null);
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

  useEffect(() => {
    if (!pronto) return undefined;
    let cancelado = false;
    let timer = 0;
    const { setS, setTocando } = useEstadoDaVolta.getState();
    setTocando(true); // a câmera gira suave, como no replay
    const ler = async () => {
      try {
        const r = await api.getLiveVolta();
        if (cancelado) return;
        setAoVivo(r);
        if (r?.disponivel && r.s != null) setS(Number(r.s));
      } catch {
        if (!cancelado) setAoVivo(null);
      }
      if (!cancelado) timer = window.setTimeout(ler, PERIODO_MS);
    };
    ler();
    return () => {
      cancelado = true;
      window.clearTimeout(timer);
      useEstadoDaVolta.getState().setTocando(false);
    };
  }, [pronto]);

  const geo = geometria.dado;
  const volta = useMemo(() => (geo ? voltaDoAoVivo(aoVivo, geo.geometryId) : null), [aoVivo, geo]);
  const grade = volta ? { n: volta.pontosDaGrade, comprimento: volta.comprimentoM, passo: volta.passoM } : null;
  const sessoes = relatorio.dado?.sessoes ?? [];
  const curvas = useMemo(() => (grade && sessoes.length ? curvasDoRelatorio(grade, sessoes[0].curvas) : []), [grade?.n, grade?.passo, sessoes]); // eslint-disable-line react-hooks/exhaustive-deps

  let motivo: string | null = null;
  if (!pronto) motivo = 'aguardando o backend';
  else if (geometria.erro) motivo = `sem a geometria oficial: ${geometria.erro}`;
  else if (escolha.dado && !lapRef) motivo = 'o coach não tem a referência escolhida na Coleta';
  else if (ref.erro) motivo = `sem a volta de referência: ${ref.erro}`;
  else if (!aoVivo || !aoVivo.disponivel) motivo = aoVivo && 'motivo' in aoVivo ? String((aoVivo as any).motivo) : 'sem quadros do jogo';
  else if (!aoVivo.desdeALinha) motivo = 'o fantasma aparece depois da próxima passagem pela linha: o relógio da volta começa nela';

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
    />
  );
};
