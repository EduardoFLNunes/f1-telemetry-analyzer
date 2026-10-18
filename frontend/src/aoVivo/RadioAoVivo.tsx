/**
 * O rádio da tela Ao vivo (pedido 31, Parte D.2): as mensagens que o backend
 * entregou (`/api/radio/mensagens`), com o texto pronto (o mesmo do app do
 * jogo), a hora, o ponto da pista e o botão para ouvir o áudio.
 *
 * Lê só o que é novo (`desde` o último id). Se o backend reiniciou (outra
 * `instancia`), começa de novo.
 */
import React, { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { MensagemRadioCartao } from '../components/ui/base';
import { mensagemDoRadio, type MensagemDoBackend } from '../utils/radio';

const GUARDADAS = 20;

export const RadioAoVivo: React.FC<{ pronto: boolean }> = ({ pronto }) => {
  const [mensagens, setMensagens] = useState<MensagemDoBackend[]>([]);
  const [falhou, setFalhou] = useState(false);
  const [erroDaVoz, setErroDaVoz] = useState<string | null>(null);
  const cursor = useRef<{ desde: number; instancia: string | null }>({ desde: 0, instancia: null });
  const tocando = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (!pronto) return undefined;
    let cancelado = false;
    let timer = 0;
    const ler = async () => {
      try {
        const r = await api.getRadioMensagens(cursor.current.desde, cursor.current.instancia);
        if (cancelado) return;
        const reiniciou = cursor.current.instancia !== null && r.instancia !== cursor.current.instancia;
        cursor.current = { desde: r.ultimoId ?? cursor.current.desde, instancia: r.instancia ?? null };
        const novas: MensagemDoBackend[] = Array.isArray(r.mensagens) ? r.mensagens : [];
        if (reiniciou) setMensagens(novas.slice(-GUARDADAS).reverse());
        else if (novas.length) setMensagens((atuais) => [...novas.slice().reverse(), ...atuais].slice(0, GUARDADAS));
        setErroDaVoz(r.erroDaVoz ?? null);
        setFalhou(false);
      } catch {
        if (!cancelado) setFalhou(true);
      }
      if (!cancelado) timer = window.setTimeout(ler, 1000);
    };
    ler();
    return () => {
      cancelado = true;
      window.clearTimeout(timer);
    };
  }, [pronto]);

  const ouvir = (caminho: string) => {
    tocando.current?.pause();
    const audio = new Audio(api.urlDoAudio(caminho));
    tocando.current = audio;
    audio.play().catch(() => undefined);
  };

  return (
    <div role="log" aria-live="polite" aria-label="Mensagens do rádio" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {falhou && <p className="texto-fraco" style={{ margin: 0 }}>O backend não respondeu ao rádio.</p>}
      {erroDaVoz && <p className="texto-fraco" style={{ margin: 0 }}>Sem voz: {erroDaVoz}</p>}
      {!falhou && mensagens.length === 0 && (
        <p className="texto-fraco" style={{ margin: 0 }}>
          {pronto
            ? 'Nenhuma mensagem nesta abertura do app. Elas chegam nas retas (as frases do coach) e na linha (o resumo da volta).'
            : 'Aguardando o backend.'}
        </p>
      )}
      {mensagens.map((m, i) => {
        const cartao = mensagemDoRadio(m, i);
        return (
          <MensagemRadioCartao
            key={cartao.id}
            mensagem={cartao}
            esmaecida={Math.max(0.6, 1 - i * 0.08)}
            aoOuvir={cartao.audio ? () => ouvir(cartao.audio as string) : undefined}
          />
        );
      })}
    </div>
  );
};
