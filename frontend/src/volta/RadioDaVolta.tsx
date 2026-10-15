/**
 * As frases do coach nesta volta (inventário, seção 6: "as frases ficam no
 * replay da Volta, marcadas no mapa").
 *
 * Vêm da rota que já existe, `/api/analysis/coach/lap/{replayLapId}`: o mesmo
 * coach, percorrido no servidor sobre a volta gravada. Cada evento traz o `s`
 * onde a frase sai, já na geometria oficial (o coach projeta nela desde o
 * ADR 0013). A frase é montada em português por `utils/radio.ts`, com os mesmos
 * números do evento. Clicar numa frase leva o cursor até o ponto dela; durante
 * o replay, a última frase já dita fica destacada.
 */
import React from 'react';
import { mensagemDoEvento, type EventoCoach, type MensagemRadio } from '../utils/radio';
import { useEstadoDaVolta } from './estado';
import { curvaEm, type Curva } from './medidas';
import { nf } from './formato';

export type FraseDaVolta = { s: number; mensagem: MensagemRadio };

/** Os eventos da rota com `s` válido, na ordem da volta. */
export function frasesDosEventos(eventos: unknown, comprimento: number): FraseDaVolta[] {
  if (!Array.isArray(eventos)) return [];
  return eventos
    .map((e: EventoCoach & { s?: unknown }, i) => ({ s: Number(e?.s), mensagem: mensagemDoEvento(e, i) }))
    .filter((f) => Number.isFinite(f.s) && f.s >= 0 && f.s <= comprimento + 1)
    .sort((a, b) => a.s - b.s);
}

export const RadioDaVolta: React.FC<{ frases: FraseDaVolta[] | null; curvas: Curva[]; erro: string | null }> = ({ frases, curvas, erro }) => {
  const s = useEstadoDaVolta((e) => e.s);
  const { setS, setTocando } = useEstadoDaVolta.getState();
  const ultima = s === null || !frases ? -1 : frases.reduce((k, f, i) => (f.s <= s ? i : k), -1);
  return (
    <div className="radio-da-volta" aria-label="Rádio nesta volta">
      <span className="rotulo">Rádio nesta volta</span>
      {erro ? (
        <p className="texto-fraco" style={{ margin: 0 }}>Sem dados: {erro}</p>
      ) : frases === null ? (
        <p className="texto-fraco" style={{ margin: 0 }}>Lendo as frases do coach…</p>
      ) : frases.length === 0 ? (
        <p className="texto-fraco" style={{ margin: 0 }}>O coach não falou durante esta volta.</p>
      ) : (
        <ol className="radio-lista">
          {frases.map((f, i) => {
            const c = curvaEm(curvas, f.s);
            return (
              <li key={f.mensagem.id}>
                <button
                  type="button"
                  className="radio-frase"
                  aria-current={i === ultima ? 'true' : undefined}
                  onClick={() => {
                    setTocando(false);
                    setS(f.s);
                  }}
                >
                  <span className="dado texto-fraco">{nf(f.s, 0)} m{c ? ` · ${c.codigo}` : ''}</span>
                  <span>{f.mensagem.frase}</span>
                  {f.mensagem.detalhe && <span className="texto-fraco">{f.mensagem.detalhe}</span>}
                </button>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
};
