/**
 * O replay em tamanho grande (pedido 45, E.6): o botão "Abrir no app", na janela do jogo, pede ao backend
 * local, e o backend avisa este app pelo WebSocket (`abrir_replay`). O replay de uma volta e de uma curva da
 * sessão ao vivo, com os 4 visuais. A tela Volta só tem as voltas do store: o caminho até ela aparece
 * quando esta volta já entrou nele (a próxima rodada do coach lê a gravação).
 */
import React, { useEffect, useState } from 'react';
import { create } from 'zustand';
import type { DadosDoReplay } from './replay';
import { ReplayDaCurva } from './ReplayDaCurva';

/** `vez`: o mesmo pedido de novo lê o replay de novo (a volta pode ter fechado depois do primeiro). */
export type PedidoDeReplay = { volta: number; curva: string | null; vez?: number };

export const usePedidoDeReplay = create<{ pedido: PedidoDeReplay | null; abrir: (p: PedidoDeReplay) => void; fechar: () => void }>((set) => ({
  pedido: null,
  abrir: (pedido) => set((e) => ({ pedido: { ...pedido, vez: (e.pedido?.vez ?? 0) + 1 } })),
  fechar: () => set({ pedido: null }),
}));

/** O que o app faz com o aviso do WebSocket: a tela Ao vivo, o replay grande e a janela para a frente. */
export function aoPedirOReplay(dados: { volta?: unknown; curva?: unknown }): void {
  const volta = Number(dados?.volta);
  if (!Number.isFinite(volta)) return;
  usePedidoDeReplay.getState().abrir({ volta, curva: typeof dados?.curva === 'string' ? dados.curva : null });
  window.location.hash = '#/ao-vivo';
  (window as any).automobilistaDesktop?.trazerParaAFrente?.();
}

export function urlDoReplay(p: PedidoDeReplay): string {
  return `/api/radio/replay-da-volta/${p.volta}${p.curva ? `?curva=${encodeURIComponent(p.curva)}` : ''}`;
}

export const ReplayGrande: React.FC = () => {
  const { pedido, fechar, abrir } = usePedidoDeReplay();
  const [dados, setDados] = useState<DadosDoReplay | null>(null);
  const [altura, setAltura] = useState(640);

  useEffect(() => {
    const medir = () => setAltura(Math.max(420, window.innerHeight - 190));
    medir();
    window.addEventListener('resize', medir);
    return () => window.removeEventListener('resize', medir);
  }, []);

  if (!pedido) return null;
  const curva = dados?.curvas[0];
  const curvas = curva?.curvasNaVolta?.map((c) => c.curva) ?? null;
  const noStore = dados?.voltaNoStore ?? null;
  return (
    <div role="dialog" aria-label="Replay da volta" style={{ position: 'fixed', inset: 0, zIndex: 50, background: 'rgba(8,9,11,0.82)', padding: 24, overflow: 'auto' }}>
      <div className="painel" style={{ maxWidth: 1400, margin: '0 auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 10, background: '#0e0f12' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <strong>Volta {pedido.volta}{pedido.curva ? ` · ${pedido.curva}` : ''}</strong>
          {pedido.curva && (
            <button type="button" className="botao botao--pequeno" onClick={() => abrir({ volta: pedido.volta, curva: null })}>
              A volta inteira
            </button>
          )}
          {noStore ? (
            <a className="botao botao--pequeno" href={`#/volta/${encodeURIComponent(noStore.lapId)}`} onClick={fechar}>
              Abrir na tela Volta
            </a>
          ) : (
            <span className="texto-fraco">Na tela Volta só depois que a próxima rodada do coach ler esta gravação.</span>
          )}
          <button type="button" className="botao botao--pequeno" style={{ marginLeft: 'auto' }} onClick={fechar}>Fechar</button>
        </div>
        {curvas && (
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {curvas.map((c) => (
              <button key={c} type="button" className="chip" onClick={() => abrir({ volta: pedido.volta, curva: c })}>{c}</button>
            ))}
          </div>
        )}
        <ReplayDaCurva key={pedido.vez} url={urlDoReplay(pedido)} alturaFixa={altura} repetir aoLer={setDados} />
      </div>
    </div>
  );
};

