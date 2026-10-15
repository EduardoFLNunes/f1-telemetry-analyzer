/**
 * Mapa dos 60 microssetores da tela Volta (pedido 30), como no protótipo A:
 * a linha central da geometria oficial, cada microssetor colorido pela
 * diferença para a referência, o nome das 14 curvas (clique para escolher) e o
 * ponto do cursor.
 */
import React, { useMemo, useState } from 'react';
import { Dica } from '../components/ui/base';
import { useEstadoDaVolta } from './estado';
import type { Geometria } from './dados';
import { calor } from './cores';
import { interp, type Curva } from './medidas';
import { nf, sg } from './formato';
import { base, rotuloDaCurva, type Ponto } from './projecao';
import type { FraseDaVolta } from './RadioDaVolta';

const W = 640;
const H = 420;
const MARGEM = 34;

type Props = { geometria: Geometria; curvas: Curva[]; microssetores: number[]; frases?: FraseDaVolta[] | null };

/** O ponto do cursor: só ele acompanha o replay. */
function PontoDoCursor({ S, X, Y }: { S: number[]; X: number[]; Y: number[] }) {
  const s = useEstadoDaVolta((e) => e.s);
  if (s === null) return null;
  return <circle cx={interp(s, S, X)} cy={interp(s, S, Y)} r={6} style={{ fill: 'var(--voce)', stroke: 'var(--superficie)', strokeWidth: 2 }} />;
}

export const MapaMicrossetores: React.FC<Props> = ({ geometria, curvas, microssetores, frases }) => {
  const curvaEscolhida = useEstadoDaVolta((e) => e.curva);
  const escolherCurva = useEstadoDaVolta((e) => e.escolherCurva);
  const [dica, setDica] = useState<{ x: number; y: number; texto: string } | null>(null);
  const L = geometria.comprimentoM;

  const proj = useMemo(() => {
    const pts = geometria.x.map((x, i) => base(x, geometria.z[i]));
    const xs = pts.map((p) => p[0]);
    const ys = pts.map((p) => p[1]);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const k = Math.min((W - 2 * MARGEM) / (maxX - minX), (H - 2 * MARGEM) / (maxY - minY));
    const ox = (W - k * (maxX - minX)) / 2 - k * minX;
    const oy = (H - k * (maxY - minY)) / 2 - k * minY;
    const tela = (p: Ponto): Ponto => [ox + k * p[0], oy + k * p[1]];
    const X = pts.map((p) => tela(p)[0]);
    const Y = pts.map((p) => tela(p)[1]);
    const S = geometria.x.map((_, i) => i * geometria.passoM);
    // Fecha o laço na linha.
    X.push(X[0]);
    Y.push(Y[0]);
    S.push(L);
    return { X, Y, S, tela };
  }, [geometria, L]);

  const trecho = (a: number, b: number) => {
    const pts: Ponto[] = [];
    const add = (s0: number, s1: number) => {
      pts.push([interp(s0, proj.S, proj.X), interp(s0, proj.S, proj.Y)]);
      for (let i = 0; i < proj.S.length; i += 1) if (proj.S[i] > s0 && proj.S[i] < s1) pts.push([proj.X[i], proj.Y[i]]);
      pts.push([interp(s1, proj.S, proj.X), interp(s1, proj.S, proj.Y)]);
    };
    if (b >= a) add(a, b);
    else {
      add(a, L);
      add(0, b);
    }
    return pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join('');
  };

  const pista = useMemo(() => proj.X.map((x, i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${proj.Y[i].toFixed(1)}`).join('') + 'Z', [proj]);
  const bordas = geometria.bordasDosMicrossetores;
  const caminhosMs = useMemo(() => bordas.slice(0, -1).map((a, k) => trecho(a, bordas[k + 1])), [bordas, proj]); // eslint-disable-line react-hooks/exhaustive-deps
  const escolhida = curvas.find((c) => c.codigo === curvaEscolhida) || null;
  const rotulos = useMemo(
    () => curvas.map((c) => ({ c, p: proj.tela(rotuloDaCurva(geometria, c.apice, c.lado, 24)) })),
    [curvas, geometria, proj],
  );

  return (
    <div style={{ position: 'relative' }}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Mapa de Interlagos colorido pela diferença em cada um dos 60 microssetores" style={{ width: '100%', height: 'auto', display: 'block' }}>
        <path d={pista} style={{ fill: 'none', stroke: 'var(--pista-desenho)', strokeWidth: 16, strokeLinejoin: 'round' }} />
        {escolhida && (
          <path d={trecho(escolhida.trecho[0], escolhida.trecho[1])} style={{ fill: 'none', stroke: 'var(--texto-1)', strokeWidth: 15, strokeLinecap: 'round', strokeOpacity: 0.5 }} />
        )}
        {caminhosMs.map((d, k) => (
          <path
            key={k}
            d={d}
            style={{ fill: 'none', stroke: calor(microssetores[k]), strokeWidth: 8 }}
            onMouseMove={(ev) => setDica({ x: ev.clientX, y: ev.clientY, texto: `Microssetor ${k + 1} (${nf(bordas[k], 0)}–${nf(bordas[k + 1], 0)} m): ${sg(microssetores[k], 3)} s` })}
            onMouseLeave={() => setDica(null)}
          />
        ))}
        <rect x={proj.X[0] - 2} y={proj.Y[0] - 9} width={4} height={18} style={{ fill: 'var(--texto-1)' }} />
        {rotulos.map(({ c, p }) => (
          <text
            key={c.codigo}
            x={p[0]}
            y={p[1] + 4}
            textAnchor="middle"
            className="grafico-rotulo-curva"
            role="button"
            tabIndex={0}
            aria-label={`Escolher a curva ${c.codigo}`}
            aria-pressed={curvaEscolhida === c.codigo}
            onClick={() => escolherCurva(c.codigo)}
            onKeyDown={(ev) => {
              if (ev.key === 'Enter' || ev.key === ' ') {
                ev.preventDefault();
                escolherCurva(c.codigo);
              }
            }}
          >
            {c.codigo}
          </text>
        ))}
        {(frases ?? []).map((f) => {
          const x = interp(f.s, proj.S, proj.X);
          const y = interp(f.s, proj.S, proj.Y);
          return (
            <path
              key={f.mensagem.id}
              d={`M${x.toFixed(1)} ${(y - 6).toFixed(1)}L${(x + 6).toFixed(1)} ${y.toFixed(1)}L${x.toFixed(1)} ${(y + 6).toFixed(1)}L${(x - 6).toFixed(1)} ${y.toFixed(1)}Z`}
              style={{ fill: 'var(--superficie)', stroke: 'var(--texto-1)', strokeWidth: 1.6 }}
              onMouseMove={(ev) => setDica({ x: ev.clientX, y: ev.clientY, texto: `Rádio em ${nf(f.s, 0)} m: ${f.mensagem.frase}` })}
              onMouseLeave={() => setDica(null)}
            />
          );
        })}
        <PontoDoCursor S={proj.S} X={proj.X} Y={proj.Y} />
      </svg>
      {dica && <Dica x={dica.x} y={dica.y}>{dica.texto}</Dica>}
    </div>
  );
};
