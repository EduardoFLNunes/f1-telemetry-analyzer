/**
 * O rádio do engenheiro na tela Sistema (pedido 31, Parte B.4): o estado (janelas
 * de rádio e voz) e a mensagem de teste, para conferir o cartão e a voz no jogo
 * sem andar na pista.
 */
import React, { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { MensagemRadioCartao, PainelVidro } from '../../components/ui/base';
import { textoDoErro } from '../../volta/dados';
import { mensagemDoRadio } from '../../utils/radio';

export const RadioDeTeste: React.FC = () => {
  const [estado, setEstado] = useState<any>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [mandando, setMandando] = useState(false);
  const [ultima, setUltima] = useState<any>(null);

  useEffect(() => {
    let cancelado = false;
    api.getRadioEstado().then((e) => !cancelado && setEstado(e)).catch((f) => !cancelado && setErro(textoDoErro(f)));
    return () => {
      cancelado = true;
    };
  }, []);

  const mandar = async () => {
    setMandando(true);
    try {
      const m = await api.postRadioTeste();
      setUltima(m);
      setErro(null);
      if (m?.audio) new Audio(api.urlDoAudio(m.audio)).play().catch(() => undefined);
    } catch (f) {
      setErro(textoDoErro(f));
    } finally {
      setMandando(false);
    }
  };

  const janelas: Array<[number, number]> = estado?.janelas ?? [];
  return (
    <PainelVidro
      id="sistema-radio"
      titulo="Rádio do engenheiro"
      acao={
        <button type="button" className="botao botao--primario botao--pequeno" onClick={mandar} disabled={mandando}>
          {mandando ? 'Gerando a voz…' : 'Mandar mensagem de teste'}
        </button>
      }
    >
      <p className="texto-apoio" style={{ margin: 0 }}>
        A mensagem de teste sai na hora, sem esperar uma reta: com o app do rádio ligado no jogo, o cartão aparece e a voz toca.
      </p>
      {erro && <p className="texto-apoio" style={{ margin: 0 }}>Sem dados: {erro}</p>}
      {estado && (
        <div className="fatos dado">
          <span>voz {estado.voz} a {String(estado.velocidade).replace('.', ',')}x</span>
          <span>
            janelas de rádio:{' '}
            {janelas.length
              ? janelas.map(([a, b]) => `${Math.round(a).toLocaleString('pt-BR')}–${Math.round(b).toLocaleString('pt-BR')} m`).join(', ')
              : 'sem a geometria oficial'}
          </span>
          <span>{estado.entregues} entregues nesta abertura · {estado.pendentes} esperando</span>
          {estado.erroDaVoz && <span>sem voz: {estado.erroDaVoz}</span>}
        </div>
      )}
      {ultima && <MensagemRadioCartao mensagem={mensagemDoRadio(ultima)} aoOuvir={ultima.audio ? () => new Audio(api.urlDoAudio(ultima.audio)).play().catch(() => undefined) : undefined} />}
    </PainelVidro>
  );
};
