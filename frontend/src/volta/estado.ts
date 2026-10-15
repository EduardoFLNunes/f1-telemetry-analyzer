/**
 * O estado compartilhado da tela Volta: o cursor (onde a volta está, em
 * metros), o replay e as escolhas da visão com fantasma. O canvas e os
 * gráficos assinam só o que usam, para o replay não refazer a tela inteira a
 * cada quadro.
 */
import { create } from 'zustand';
import type { ModoDoFantasma } from './medidas';

type EstadoDaVolta = {
  /** Cursor em metros; `null` sem cursor. */
  s: number | null;
  tocando: boolean;
  velocidade: number;
  modo: ModoDoFantasma;
  zoom: number;
  girar: boolean;
  curva: string | null;
  setS: (s: number | null) => void;
  setTocando: (t: boolean) => void;
  setVelocidade: (v: number) => void;
  setModo: (m: ModoDoFantasma) => void;
  setZoom: (z: number) => void;
  setGirar: (g: boolean) => void;
  escolherCurva: (c: string | null) => void;
};

export const useEstadoDaVolta = create<EstadoDaVolta>((set, get) => ({
  s: null,
  tocando: false,
  velocidade: 1,
  modo: 'curva',
  zoom: 150,
  girar: true,
  curva: null,
  setS: (s) => set({ s }),
  setTocando: (tocando) => set({ tocando }),
  setVelocidade: (velocidade) => set({ velocidade }),
  setModo: (modo) => set({ modo }),
  setZoom: (zoom) => set({ zoom }),
  setGirar: (girar) => set({ girar }),
  escolherCurva: (c) => set({ curva: get().curva === c ? null : c }),
}));
