/**
 * O estado do app que aparece em todas as telas (pedido 29): se o backend
 * respondeu, se o jogo está aberto e se está gravando.
 *
 * Na abertura, o backend leva até cerca de 40 s para responder (achado 1 do
 * pedido 28: o cache da pista é refeito). Enquanto isso, `/api/health` é
 * consultado a cada segundo e o hero mostra a espera real: os segundos desde a
 * abertura e as tentativas. Nenhuma barra de progresso inventada.
 */
import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';

export type FaseBackend = 'subindo' | 'pronto' | 'caiu';

export type EstadoDoApp = {
  backend: {
    fase: FaseBackend;
    versao: string | null;
    tentativas: number;
    /** Segundos desde a abertura do app até agora (subindo) ou até a resposta (pronto). */
    segundos: number;
  };
  /** O jogo está aberto numa sessão e o backend pode capturar. */
  capturaLiberada: boolean;
  /** O texto do portão de captura, quando ele explica por que não grava. */
  motivoCaptura: string | null;
  gravando: boolean;
  sessaoGravando: string | null;
};

const ABERTURA = typeof performance !== 'undefined' ? performance.now() : Date.now();
const agora = () => (typeof performance !== 'undefined' ? performance.now() : Date.now());

const MOTIVOS: Record<string, string> = {
  waiting_for_assetto_corsa_process: 'o Assetto Corsa está fechado',
  waiting_for_assetto_corsa_shared_memory_pages: 'o Assetto Corsa abriu, mas a sessão ainda não carregou',
  waiting_for_assetto_corsa_static_data: 'o Assetto Corsa ainda está carregando o carro e a pista',
  stale_assetto_corsa_shared_memory_without_process: 'há memória do jogo aberta sem o jogo: feche o processo que a criou',
};

export function motivoDaCaptura(captura: any): string | null {
  if (!captura || captura.allowed) return null;
  const razao = typeof captura.reason === 'string' ? captura.reason : '';
  return MOTIVOS[razao] || (typeof captura.message === 'string' && captura.message) || 'o jogo ainda não está pronto';
}

export function useEstadoDoApp(): EstadoDoApp {
  const [estado, setEstado] = useState<EstadoDoApp>({
    backend: { fase: 'subindo', versao: null, tentativas: 0, segundos: 0 },
    capturaLiberada: false,
    motivoCaptura: null,
    gravando: false,
    sessaoGravando: null,
  });
  const fase = useRef<FaseBackend>('subindo');
  const tentativas = useRef(0);

  // O backend: a cada segundo enquanto não responde, a cada 10 s depois.
  useEffect(() => {
    let cancelado = false;
    let timer: number | undefined;
    const tentar = async () => {
      tentativas.current += 1;
      let versao: string | null = null;
      let ok = false;
      try {
        // Enquanto sobe, cada tentativa falha rápido; depois, o backend pode estar
        // ocupado lendo uma gravação grande e merece mais tempo antes de "sem resposta".
        const saude = await api.getHealth(fase.current === 'pronto' ? 8000 : 2500);
        ok = saude?.status === 'ok';
        versao = saude?.version ?? null;
      } catch {
        ok = false;
      }
      if (cancelado) return;
      const anterior = fase.current;
      const nova: FaseBackend = ok ? 'pronto' : anterior === 'pronto' ? 'caiu' : anterior;
      fase.current = nova;
      setEstado((e) => ({
        ...e,
        backend: {
          fase: nova,
          versao: versao ?? e.backend.versao,
          tentativas: tentativas.current,
          // Os segundos contam até a primeira resposta; depois de uma queda, não recomeçam.
          segundos: anterior === 'subindo' ? Math.round((agora() - ABERTURA) / 1000) : e.backend.segundos,
        },
      }));
      timer = window.setTimeout(tentar, nova === 'pronto' ? 10_000 : 1_000);
    };
    tentar();
    return () => {
      cancelado = true;
      window.clearTimeout(timer);
    };
  }, []);

  // O jogo e a gravação, como a navegação antiga fazia, só depois que o backend responde.
  useEffect(() => {
    if (estado.backend.fase !== 'pronto') return undefined;
    let cancelado = false;
    const ler = async () => {
      try {
        const gravacao = await api.getRecordingStatus();
        if (cancelado) return;
        const captura = gravacao?.captureGate || {};
        setEstado((e) => ({
          ...e,
          capturaLiberada: Boolean(captura.allowed),
          motivoCaptura: motivoDaCaptura(captura),
          gravando: Boolean(gravacao?.recording),
          sessaoGravando: gravacao?.sessionId ?? null,
        }));
      } catch {
        /* fica o último estado; a fase do backend diz se ele caiu */
      }
    };
    ler();
    const timer = window.setInterval(ler, 5000);
    return () => {
      cancelado = true;
      window.clearInterval(timer);
    };
  }, [estado.backend.fase]);

  return estado;
}
