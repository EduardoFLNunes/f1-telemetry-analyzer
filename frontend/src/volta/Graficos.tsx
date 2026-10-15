/**
 * Gráficos por distância da tela Volta (pedido 30), como no protótipo A: eixo
 * em metros, as 14 curvas como faixas, um cursor compartilhado com o mapa e o
 * replay, a dica ao passar o mouse e o clique para escolher a curva.
 */
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Dica } from '../components/ui/base';
import { useEstadoDaVolta } from './estado';
import { curvaEm, type Curva } from './medidas';
import { nf } from './formato';

const PL = 6;
const PR = 52;

export function useLargura<T extends HTMLElement>(): [React.RefObject<T>, number] {
  const ref = useRef<T>(null);
  const [largura, setLargura] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    setLargura(el.clientWidth);
    const ro = new ResizeObserver((entradas) => setLargura(Math.round(entradas[0].contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, largura];
}

export type Serie = { valores: ArrayLike<number>; cor: string; largura?: number; tracejado?: string; area?: boolean };

type PropsDoGrafico = {
  comprimento: number;
  passo: number;
  altura: number;
  min: number;
  max: number;
  marcas: Array<{ v: number; rotulo: string; forte?: boolean }>;
  series: Serie[];
  curvas: Curva[];
  rotulosDasCurvas?: boolean;
  rotulo: string;
  dica: (s: number) => string;
};

const xDe = (s: number, W: number, L: number) => PL + (s / L) * (W - PL - PR);

/** Faixas das curvas (alternadas) e a curva escolhida. */
function Faixas({ curvas, W, H, L, rotulos }: { curvas: Curva[]; W: number; H: number; L: number; rotulos: boolean }) {
  const escolhida = useEstadoDaVolta((e) => e.curva);
  return (
    <g>
      {curvas.map((c, k) => {
        const [a, b] = c.trecho;
        const partes = b >= a ? [[a, b]] : [[a, L], [0, b]];
        const cor = escolhida === c.codigo ? 'var(--faixa-selecionada)' : k % 2 ? 'var(--faixa-curva)' : 'transparent';
        const meio = b >= a ? (a + b) / 2 : b / 2;
        return (
          <g key={c.codigo}>
            {partes.map(([p0, p1]) => (
              <rect key={p0} x={xDe(p0, W, L)} y={0} width={Math.max(0, xDe(p1, W, L) - xDe(p0, W, L))} height={H} style={{ fill: cor }} />
            ))}
            {rotulos && W > 520 && (
              <text x={xDe(meio, W, L)} y={11} textAnchor="middle" className="grafico-texto">
                {c.codigo}
              </text>
            )}
          </g>
        );
      })}
    </g>
  );
}

function LinhaDoCursor({ W, H, L }: { W: number; H: number; L: number }) {
  const s = useEstadoDaVolta((e) => e.s);
  if (s === null) return null;
  const x = xDe(s, W, L);
  return <line x1={x} x2={x} y1={0} y2={H} style={{ stroke: 'var(--texto-1)', strokeWidth: 1 }} />;
}

export const GraficoPorDistancia: React.FC<PropsDoGrafico> = ({
  comprimento: L, passo, altura: H, min, max, marcas, series, curvas, rotulosDasCurvas = false, rotulo, dica,
}) => {
  const [caixa, W0] = useLargura<HTMLDivElement>();
  const W = Math.max(280, W0);
  const topo = rotulosDasCurvas ? 16 : 4;
  const y = (v: number) => topo + ((max - v) / (max - min)) * (H - topo - 4);
  const [dicaEm, setDicaEm] = useState<{ x: number; y: number; texto: string } | null>(null);
  const { setS, escolherCurva } = useEstadoDaVolta.getState();

  const caminhos = useMemo(
    () =>
      series.map((sr) => {
        let d = '';
        for (let i = 0; i < sr.valores.length; i += 1) {
          const v = Number(sr.valores[i]);
          if (!Number.isFinite(v)) continue;
          d += `${d ? 'L' : 'M'}${xDe(i * passo, W, L).toFixed(1)} ${y(v).toFixed(1)}`;
        }
        return d;
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [series, W, L, passo, min, max, H],
  );

  const sDoEvento = (ev: React.MouseEvent<SVGRectElement>) => {
    const r = (ev.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect();
    return Math.max(0, Math.min(L, ((ev.clientX - r.left - PL) / (W - PL - PR)) * L));
  };

  return (
    <div ref={caixa} style={{ width: '100%' }}>
      {W0 > 0 && (
        <svg width={W} height={H} role="img" aria-label={rotulo} style={{ display: 'block' }}>
          <Faixas curvas={curvas} W={W} H={H} L={L} rotulos={rotulosDasCurvas} />
          {marcas.map((m) => (
            <g key={m.v}>
              <line x1={PL} x2={W - PR} y1={y(m.v)} y2={y(m.v)} style={{ stroke: 'var(--linha)', strokeWidth: m.forte ? 1.2 : 0.6 }} />
              <text x={W - 4} y={y(m.v) + 3} textAnchor="end" className="grafico-texto">
                {m.rotulo}
              </text>
            </g>
          ))}
          {series.map((sr, k) =>
            sr.area ? (
              <path
                key={`a${k}`}
                d={`${caminhos[k]}L${W - PR} ${y(0).toFixed(1)}L${PL} ${y(0).toFixed(1)}Z`}
                style={{ fill: sr.cor, fillOpacity: 0.12, stroke: 'none' }}
              />
            ) : null,
          )}
          {series.map((sr, k) => (
            <path
              key={k}
              d={caminhos[k]}
              style={{ fill: 'none', stroke: sr.cor, strokeWidth: sr.largura ?? 1.6, strokeDasharray: sr.tracejado, strokeLinejoin: 'round' }}
            />
          ))}
          <LinhaDoCursor W={W} H={H} L={L} />
          <rect
            x={PL}
            y={0}
            width={W - PL - PR}
            height={H}
            style={{ fill: 'transparent', cursor: 'crosshair' }}
            onMouseMove={(ev) => {
              const s = sDoEvento(ev);
              setS(s);
              setDicaEm({ x: ev.clientX, y: ev.clientY, texto: dica(s) });
            }}
            onMouseLeave={() => {
              setDicaEm(null);
              if (!useEstadoDaVolta.getState().tocando) setS(null);
            }}
            onClick={(ev) => {
              const c = curvaEm(curvas, sDoEvento(ev));
              if (c) escolherCurva(c.codigo);
            }}
          />
        </svg>
      )}
      {dicaEm && <Dica x={dicaEm.x} y={dicaEm.y}>{dicaEm.texto}</Dica>}
    </div>
  );
};

/** O eixo de distância, em metros, alinhado com os gráficos. */
export const EixoDeDistancia: React.FC<{ comprimento: number }> = ({ comprimento: L }) => {
  const [caixa, W0] = useLargura<HTMLDivElement>();
  const W = Math.max(280, W0);
  return (
    <div ref={caixa} style={{ width: '100%' }}>
      {W0 > 0 && (
        <svg width={W} height={16} aria-hidden="true" style={{ display: 'block' }}>
          {[0, 1000, 2000, 3000, 4000].filter((m) => m <= L).map((m) => (
            <text key={m} x={xDe(m, W, L)} y={12} textAnchor={m ? 'middle' : 'start'} className="grafico-texto">
              {nf(m, 0)} m
            </text>
          ))}
        </svg>
      )}
    </div>
  );
};
