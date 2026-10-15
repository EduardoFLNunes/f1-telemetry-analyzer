/**
 * As 14 curvas da volta contra a referência (pedido 30), como no protótipo A.
 * Os números são os do método do relatório de evolução (`medidas.ts`); a
 * coluna "Mediana da sessão" só aparece contra a volta da IA, que é a
 * referência do relatório.
 */
import React from 'react';
import { useEstadoDaVolta } from './estado';
import type { MedidaDaCurva } from './medidas';
import { nf, sg, textoDaFreada, textoDaLateral, textoDaMinima } from './formato';

type Props = {
  medidas: MedidaDaCurva[];
  /** Mediana da perda para a IA na sessão, por curva; `null` sem a coluna. */
  medianas: Array<number | null> | null;
  diferencaDaVolta: number;
  referencia: 'ia' | 'melhor';
};

export const TabelaDasCurvas: React.FC<Props> = ({ medidas, medianas, diferencaDaVolta, referencia }) => {
  const escolhida = useEstadoDaVolta((e) => e.curva);
  const escolher = useEstadoDaVolta((e) => e.escolherCurva);
  const maior = Math.max(...medidas.map((m) => Math.abs(m.perdaS))) || 1;
  const comMediana = Boolean(medianas);
  return (
    <div className="superficie tabela-caixa">
      <table className="tabela tabela--compacta">
        <thead>
          <tr>
            <th scope="col">Curva</th>
            <th scope="col" style={{ minWidth: 150 }}>Perda (s)</th>
            {comMediana && <th scope="col" className="num">Mediana da sessão</th>}
            <th scope="col">Início da freada</th>
            <th scope="col" className="num">Velocidade mínima</th>
            <th scope="col">Posição no ápice</th>
          </tr>
        </thead>
        <tbody>
          {medidas.map((m, i) => {
            const ganho = m.perdaS < 0;
            const largura = Math.max(2, Math.round((Math.abs(m.perdaS) / maior) * 100));
            return (
              <tr
                key={m.codigo}
                className="escolhivel"
                aria-selected={escolhida === m.codigo}
                tabIndex={0}
                onClick={() => escolher(m.codigo)}
                onKeyDown={(ev) => {
                  if (ev.key === 'Enter' || ev.key === ' ') {
                    ev.preventDefault();
                    escolher(m.codigo);
                  }
                }}
              >
                <th scope="row" className="dado" style={{ fontWeight: 500, whiteSpace: 'nowrap' }}>
                  {m.codigo} · {m.lado}
                </th>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span className={`dado ${ganho ? 'cor-ganho' : 'cor-perda'}`} style={{ width: 62, textAlign: 'right' }}>
                      {sg(m.perdaS, 3)}
                    </span>
                    <span className="barra-perda">
                      <i style={{ width: `${largura}%`, background: ganho ? 'var(--ganho)' : 'var(--perda)' }} />
                    </span>
                  </div>
                </td>
                {comMediana && (
                  <td className="num texto-apoio">{medianas?.[i] === null || medianas?.[i] === undefined ? '—' : nf(medianas[i] as number, 3)}</td>
                )}
                <td>{textoDaFreada(m.freadaM, m.refFreia, false, referencia)}</td>
                <td className="num">{Number.isFinite(m.minimaKmh) ? textoDaMinima(m.minimaKmh, false) : '—'}</td>
                <td>{Number.isFinite(m.lateralApiceM) ? textoDaLateral(m.lateralApiceM) : '—'}</td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row" className="texto-fraco" style={{ fontWeight: 500 }}>Soma</th>
            <td className={`dado ${diferencaDaVolta < 0 ? 'cor-ganho' : 'cor-perda'}`}>{sg(diferencaDaVolta, 3)} s</td>
            <td colSpan={comMediana ? 4 : 3} className="texto-fraco">as 14 curvas cobrem a volta inteira</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
};
