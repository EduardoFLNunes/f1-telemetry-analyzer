/**
 * Os dados das telas Sessões, Volta e Evolução (pedido 30), todos das rotas do
 * app; nada do JSON embutido no protótipo. Cada leitura fica guardada enquanto
 * o app está aberto: os arquivos só mudam quando o `atualizar_coach` roda.
 */
import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { Grade, Linhas } from './medidas';

export type SessaoDoResumo = {
  sessao: string;
  voltas: number;
  melhor_s: number;
  mediana_s: number;
  desvio_s: number | null;
  mediana_menos_ia_s: number;
  melhor_menos_ia_s: number;
  poucos_dados: boolean;
  curvas_com_diferenca_consistente: string[];
};

export type Resumo = {
  sessoes: SessaoDoResumo[];
  tendencia_mediana_s_por_sessao: number | null;
  criterio_adr_0015: {
    limite_s: number;
    sessoes_necessarias: number;
    sessoes_disponiveis: number;
    amplitude_s: number | null;
    estabilizou: boolean | null;
    situacao: string;
  };
  referencia: { tipo: string; volta: string; tempo_s: number };
};

export type CurvaDaSessao = {
  curva: string;
  trecho_m: number[];
  curva_m: number[];
  apice_m: number;
  perda_para_ia_s: { mediana: number } | null;
  situacao: string;
  intervalo_90_s: [number, number] | null;
};

export type TecnicaDaCurva = {
  curva: string;
  uso_da_aderencia: { mediana: number | null; ia_g: number | null } | null;
  freio_e_volante_juntos: { mediana: number | null; ia_m: number | null } | null;
  freada_emendada: { voltas_emendadas: number; voltas_com_frenagem: number; ia: string | null } | null;
};

export type Sessao = {
  sessao: string;
  gravacoes: string[];
  voltas: Array<{ volta: string; gravacao: string; tempo_s: number }>;
  curvas: CurvaDaSessao[];
  tecnica?: { curvas: TecnicaDaCurva[] };
  resumo: { voltas: number; melhor_s: number; mediana_s: number; volta_da_ia_s: number };
};

export type Referencias = {
  volta_ia?: { volta: string; tempoS: number };
  minha_melhor?: { volta: string; tempoS: number };
};

export type Geometria = {
  geometryId: string;
  comprimentoM: number;
  passoM: number;
  x: number[];
  z: number[];
  normalX: number[];
  normalZ: number[];
  bordasDosMicrossetores: number[];
  elevacaoM: number[] | null;
  larguraEsquerdaM: number[] | null;
  larguraDireitaM: number[] | null;
};

export type VoltaDoStore = {
  lapId: string;
  gravacao: string;
  tempoS: number;
  replayLapId: string | null;
  geometryId: string;
  pontosDaGrade: number;
  comprimentoM: number;
  passoM: number;
  linhas: Linhas;
};

export type Carga<T> = { dado: T | null; erro: string | null; carregando: boolean };

const guardados = new Map<string, Promise<any>>();

function lerUmaVez<T>(chave: string, ler: () => Promise<T>): Promise<T> {
  let p = guardados.get(chave);
  if (!p) {
    p = ler().catch((e) => {
      guardados.delete(chave);
      throw e;
    });
    guardados.set(chave, p);
  }
  return p;
}

/** Esquece as leituras guardadas (depois de um `atualizar_coach`, por exemplo). */
export function esquecerLeituras(): void {
  guardados.clear();
}

async function exigir<T>(promessa: Promise<any>, campo: string): Promise<T> {
  const r = await promessa;
  if (!r || r.disponivel === false) throw new Error(r?.motivo || 'sem dados');
  return (campo ? r[campo] : r) as T;
}

export const lerResumo = () => lerUmaVez('resumo', () => exigir<Resumo>(api.getEvolucaoResumo(), 'resumo'));
export const lerSessao = (sessao: string) => lerUmaVez(`sessao:${sessao}`, () => exigir<Sessao>(api.getEvolucaoSessao(sessao), 'sessao'));
export const lerReferencias = () => lerUmaVez('referencias', () => exigir<Referencias>(api.getCoachReferencias(), 'referencias'));
export const lerGeometria = () => lerUmaVez('geometria', () => exigir<Geometria>(api.getGeometriaOficial(), ''));
export const lerCamadasDaPista = () => lerUmaVez('camadas', async () => {
  const r = await api.getTrackGeometry();
  if (!r?.activeTrackReady || !r?.track) throw new Error('o backend ainda não tem a pista do cache pronta');
  return r.track;
});
export const lerVolta = (lapId: string) => lerUmaVez(`volta:${lapId}`, async (): Promise<VoltaDoStore> => {
  const v = await exigir<any>(api.getStoreVolta(lapId), '');
  return {
    lapId: v.lapId,
    gravacao: v.gravacao,
    tempoS: v.tempoS,
    replayLapId: v.replayLapId ?? null,
    geometryId: v.geometryId,
    pontosDaGrade: v.pontosDaGrade,
    comprimentoM: v.comprimentoM,
    passoM: v.passoM,
    linhas: {
      elapsed: v.elapsedS,
      total: v.tempoS,
      velocidade: v.velocidadeKmh,
      acelerador: v.acelerador,
      freio: v.freio,
      lateral: v.lateralM,
    },
  };
});

export function gradeDaVolta(v: VoltaDoStore): Grade {
  return { n: v.pontosDaGrade, comprimento: v.comprimentoM, passo: v.passoM };
}

/** Uma leitura com o estado de carga; `null` na chave não lê nada. */
export function useLeitura<T>(chave: string | null, ler: () => Promise<T>): Carga<T> {
  const [estado, setEstado] = useState<Carga<T>>({ dado: null, erro: null, carregando: Boolean(chave) });
  useEffect(() => {
    if (!chave) {
      setEstado({ dado: null, erro: null, carregando: false });
      return undefined;
    }
    let cancelado = false;
    setEstado((e) => ({ dado: e.dado, erro: null, carregando: true }));
    ler()
      .then((dado) => !cancelado && setEstado({ dado, erro: null, carregando: false }))
      .catch((e) => !cancelado && setEstado({ dado: null, erro: e instanceof Error ? e.message : String(e), carregando: false }));
    return () => {
      cancelado = true;
    };
    // `ler` muda a cada render; a chave diz quando ler de novo.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chave]);
  return estado;
}

/** Todas as sessões do relatório, cada uma com o seu JSON. */
export function useSessoesDoRelatorio(): Carga<{ resumo: Resumo; sessoes: Sessao[] }> {
  return useLeitura('todas-as-sessoes', async () => {
    const resumo = await lerResumo();
    const sessoes = await Promise.all(resumo.sessoes.map((s) => lerSessao(s.sessao)));
    return { resumo, sessoes };
  });
}
