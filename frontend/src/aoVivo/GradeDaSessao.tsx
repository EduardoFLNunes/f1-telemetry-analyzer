/**
 * A grade da sessão na tela Ao vivo (pedido 43, C.4), sob os cartões do rádio.
 *
 * As voltas válidas da sessão nas linhas e as 14 curvas nas colunas. Cada célula tem a perda
 * na curva contra a referência, a mesma da análise das voltas (`/api/radio/grade`), pintada
 * de laranja quando você perde e de azul quando ganha, mais forte quanto maior. As curvas
 * citadas pelo rádio ficam marcadas na volta em que foram citadas: dá para ver se a curva
 * melhorou nas voltas seguintes. As voltas da IA, as incompletas e as com rodada ficam fora,
 * com o motivo. Atualizada a cada volta (lida a cada 5 s).
 */
import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { citadasNaVolta, forcaDaCelula, tempoDeVolta, textoDaCelula, textoDaVoltaDeFora, type GradeDaSessao } from './replay';

const LEITURA_MS = 5000;

export const TabelaDaGrade: React.FC<{ grade: GradeDaSessao }> = ({ grade }) => {
  if (!grade.voltas.length) {
    return <p className="texto-fraco" style={{ margin: 0 }}>Nenhuma volta válida nesta sessão ainda.</p>;
  }
  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="dado" style={{ borderCollapse: 'separate', borderSpacing: 2, fontSize: 11, minWidth: '100%' }}
        aria-label="Grade da sessão: a perda em cada curva, por volta">
        <thead>
          <tr>
            <th style={{ textAlign: 'left', fontWeight: 600, padding: '2px 4px' }}>volta</th>
            {grade.curvas.map((c) => <th key={c} style={{ fontWeight: 600, padding: '2px 4px' }}>{c}</th>)}
          </tr>
        </thead>
        <tbody>
          {grade.voltas.map((v) => {
            const citadas = citadasNaVolta(grade, v.volta);
            return (
              <tr key={`${v.volta}-${v.tempoS}`}>
                <td style={{ padding: '2px 4px', whiteSpace: 'nowrap' }} title={tempoDeVolta(v.tempoS)}>{v.volta ?? '?'}</td>
                {v.perdas.map((p, i) => {
                  const curva = grade.curvas[i];
                  const quem = citadas.get(curva);
                  const fundo = p === null ? 'transparent'
                    : p >= 0 ? `rgba(255,162,74,${forcaDaCelula(p)})` : `rgba(111,155,255,${forcaDaCelula(p)})`;
                  return (
                    <td key={curva}
                      title={quem ? `citada pelo rádio (${quem.map((o) => (o === 'coach' ? 'frase do coach' : 'análise')).join(' e ')})` : undefined}
                      style={{
                        background: fundo, color: p !== null && Math.abs(p) > 0.6 ? '#111214' : 'var(--texto)', textAlign: 'right',
                        padding: '2px 4px', whiteSpace: 'nowrap', borderRadius: 3,
                        outline: quem ? '2px solid var(--vermelho)' : undefined, outlineOffset: -2,
                      }}>
                      {p === null ? '—' : textoDaCelula(p)}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export const GradeDaSessaoAoVivo: React.FC<{ pronto: boolean }> = ({ pronto }) => {
  const [grade, setGrade] = useState<GradeDaSessao | null>(null);
  const [falta, setFalta] = useState(false);

  useEffect(() => {
    if (!pronto) return undefined;
    let vivo = true;
    let timer = 0;
    const ler = async () => {
      try {
        const g = await api.getRadioGrade();
        if (vivo) {
          setGrade(g);
          setFalta(false);
        }
      } catch {
        if (vivo) setFalta(true);   // um backend antigo (sem a rota) ou parado: a grade não aparece
      }
      if (vivo) timer = window.setTimeout(ler, LEITURA_MS);
    };
    ler();
    return () => {
      vivo = false;
      window.clearTimeout(timer);
    };
  }, [pronto]);

  if (falta || !grade) return null;
  return (
    <section aria-label="Grade da sessão" style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
      <b style={{ fontWeight: 600 }}>Grade da sessão: a perda em cada curva contra a referência</b>
      <span className="texto-fraco">
        laranja: você perde; azul: você ganha; mais forte quanto maior a diferença. Contorno vermelho: a curva citada pelo rádio nessa volta.
      </span>
      <TabelaDaGrade grade={grade} />
      {grade.fora.length > 0 && (
        <ul className="texto-fraco" style={{ margin: 0, paddingLeft: 18 }} aria-label="Voltas fora da grade">
          {grade.fora.map((f, i) => <li key={i}>{textoDaVoltaDeFora(f)}</li>)}
        </ul>
      )}
      <span className="texto-fraco dado">/api/radio/grade · a mesma perda da análise das voltas</span>
    </section>
  );
};
