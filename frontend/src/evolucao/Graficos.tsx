/**
 * Gráficos das telas Sessões e Evolução (pedido 30), como no protótipo A:
 *
 * - `GraficoTendencia`: mediana (linha cheia) e melhor volta (tracejada) por
 *   sessão, com a volta da IA como referência;
 * - `FaixaDeVoltas`: uma marca por volta válida da sessão, numa faixa de tempo;
 * - `IntervaloDaCurva`: a perda mediana de uma curva para a IA, com a faixa de
 *   90% de confiança (ponto vazio: sem diferença consistente).
 */
import React from 'react';
import { useLargura } from '../volta/Graficos';
import type { CurvaDaSessao, SessaoDoResumo } from '../volta/dados';
import { nomeDaSessao, numeroDaVolta, sg, tempo } from '../volta/formato';

/** M:SS sem os milésimos, para os eixos. */
const tempoCurto = (t: number) => tempo(t).replace(/,\d+$/, '');

export const GraficoTendencia: React.FC<{ sessoes: SessaoDoResumo[]; tempoIa: number | null }> = ({ sessoes, tempoIa }) => {
  const [caixa, W0] = useLargura<HTMLDivElement>();
  const W = Math.max(280, W0);
  const H = 200;
  const pl = 54;
  const pr = 48;
  const topo = 14;
  const base = 30;
  const valores = sessoes.flatMap((s) => [s.mediana_s, s.melhor_s]);
  if (tempoIa !== null) valores.push(tempoIa);
  const mn = Math.floor(Math.min(...valores)) - 1;
  const mx = Math.ceil(Math.max(...valores)) + 1;
  const x = (i: number) => pl + (sessoes.length === 1 ? 0.5 : i / (sessoes.length - 1)) * (W - pl - pr);
  const y = (v: number) => topo + ((mx - v) / (mx - mn)) * (H - topo - base);
  const marcas: number[] = [];
  for (let v = Math.ceil(mn); v <= mx; v += 2) marcas.push(v);
  return (
    <div ref={caixa} style={{ width: '100%' }}>
      {W0 > 0 && sessoes.length > 0 && (
        <svg width={W} height={H} role="img" aria-label="Mediana e melhor volta por sessão" style={{ display: 'block' }}>
          {marcas.map((v) => (
            <g key={v}>
              <line x1={pl} x2={W - pr} y1={y(v)} y2={y(v)} style={{ stroke: 'var(--linha)', strokeWidth: 0.6 }} />
              <text x={pl - 6} y={y(v) + 3} textAnchor="end" className="grafico-texto">{tempoCurto(v)}</text>
            </g>
          ))}
          {tempoIa !== null && (
            <g>
              <line x1={pl} x2={W - pr} y1={y(tempoIa)} y2={y(tempoIa)} style={{ stroke: 'var(--referencia)', strokeDasharray: '5 4' }} />
              <text x={W - pr} y={y(tempoIa) - 5} textAnchor="end" className="grafico-texto">volta da IA {tempo(tempoIa)}</text>
            </g>
          )}
          {(['mediana_s', 'melhor_s'] as const).map((campo) => (
            <g key={campo}>
              <path
                d={sessoes.map((s, i) => `${i ? 'L' : 'M'}${x(i)} ${y(s[campo])}`).join('')}
                style={{ fill: 'none', stroke: 'var(--voce)', strokeWidth: 2, strokeDasharray: campo === 'melhor_s' ? '3 3' : undefined }}
              />
              {sessoes.map((s, i) => (
                <circle
                  key={s.sessao}
                  cx={x(i)}
                  cy={y(s[campo])}
                  r={4}
                  style={{ fill: campo === 'mediana_s' ? 'var(--voce)' : 'var(--superficie)', stroke: 'var(--voce)', strokeWidth: 2 }}
                >
                  <title>{`${nomeDaSessao(s.sessao)}: ${campo === 'mediana_s' ? 'mediana' : 'melhor volta'} ${tempo(s[campo])}`}</title>
                </circle>
              ))}
            </g>
          ))}
          {sessoes.map((s, i) => (
            <text key={s.sessao} x={x(i)} y={H - 10} textAnchor="middle" className="grafico-texto">{nomeDaSessao(s.sessao)}</text>
          ))}
        </svg>
      )}
    </div>
  );
};

export const FaixaDeVoltas: React.FC<{ voltas: Array<{ volta: string; tempo_s: number }>; tempoIa: number | null }> = ({ voltas, tempoIa }) => {
  const [caixa, W0] = useLargura<HTMLDivElement>();
  const W = Math.max(260, W0);
  const H = 34;
  const lo = 83;
  const hi = 102;
  const x = (v: number) => 4 + ((Math.min(hi, Math.max(lo, v)) - lo) / (hi - lo)) * (W - 8);
  return (
    <div ref={caixa} style={{ width: '100%' }}>
      {W0 > 0 && (
        <svg width={W} height={H} role="img" aria-label={`Tempos das ${voltas.length} voltas válidas da sessão`} style={{ display: 'block' }}>
          <line x1={4} x2={W - 4} y1={14} y2={14} style={{ stroke: 'var(--linha)' }} />
          {tempoIa !== null && (
            <g>
              <line x1={x(tempoIa)} x2={x(tempoIa)} y1={4} y2={24} style={{ stroke: 'var(--referencia)', strokeDasharray: '3 2' }} />
              <text x={x(tempoIa) + 4} y={10} className="grafico-texto">IA</text>
            </g>
          )}
          {voltas.map((v) => (
            <circle key={v.volta} cx={x(v.tempo_s)} cy={14} r={4.5} style={{ fill: 'var(--voce)', fillOpacity: 0.55 }}>
              <title>{`volta ${numeroDaVolta(v.volta)}: ${tempo(v.tempo_s)}`}</title>
            </circle>
          ))}
          {[88, 92, 96, 100].map((t) => (
            <text key={t} x={x(t)} y={32} textAnchor="middle" className="grafico-texto">{tempoCurto(t)}</text>
          ))}
        </svg>
      )}
    </div>
  );
};

export const IntervaloDaCurva: React.FC<{ curva: CurvaDaSessao | undefined }> = ({ curva }) => {
  const mediana = curva?.perda_para_ia_s?.mediana;
  if (!curva || mediana === undefined || mediana === null) return <span className="texto-fraco">—</span>;
  const W = 96;
  const mx = 1.6;
  const x = (v: number) => 4 + (Math.max(0, Math.min(mx, v)) / mx) * (W - 8);
  const consistente = curva.situacao === 'diferenca_consistente';
  const ic = curva.intervalo_90_s;
  const texto = consistente ? 'diferença consistente' : curva.situacao === 'poucos_dados' ? 'poucos dados' : 'sem diferença consistente';
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }} title={`${sg(mediana, 3)} s${ic ? ` (90%: ${sg(ic[0], 3)} a ${sg(ic[1], 3)})` : ''} · ${texto}`}>
      <svg width={W} height={18} aria-hidden="true">
        <line x1={x(0)} x2={x(0)} y1={2} y2={16} style={{ stroke: 'var(--linha)' }} />
        {ic && <line x1={x(ic[0])} x2={x(ic[1])} y1={9} y2={9} style={{ stroke: 'var(--texto-3)', strokeWidth: 2 }} />}
        <circle cx={x(mediana)} cy={9} r={4} style={{ fill: consistente ? 'var(--voce)' : 'var(--superficie)', stroke: 'var(--voce)', strokeWidth: 2 }} />
      </svg>
      <span className="dado" style={{ fontSize: 12 }}>{sg(mediana, 2)}</span>
    </span>
  );
};
