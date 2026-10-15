/**
 * A pista nas visões da tela Volta (pedido 30), como no protótipo A.
 *
 * O protótipo gira o mundo 90° (`base(x, z) = [z, −x]`): a pista fica deitada,
 * melhor para a tela larga, e continua no sentido anti-horário (é uma rotação,
 * não um espelho). As posições do carro e do fantasma são a linha central da
 * geometria oficial mais o deslocamento lateral do store v2 (positivo para a
 * esquerda, na direção da normal).
 *
 * As camadas desenhadas (asfalto, pintura e zebras) vêm do cache em
 * coordenadas de mapa (x, −z); `transformarCamadas` leva o contexto do canvas
 * para elas.
 */
import type { Geometria } from './dados';

export type Ponto = [number, number];

/** Mundo (x, z) → tela da tela Volta. */
export function base(x: number, z: number): Ponto {
  return [z, -x];
}

/** Coordenadas de mapa (x, −z) → mesmas coordenadas de `base`: (u, v) ↦ (−v, −u). */
export function transformarCamadas(ctx: CanvasRenderingContext2D): void {
  ctx.transform(0, -1, -1, 0, 0, 0);
}

export type LinhaCentral = { cx: number[]; cy: number[]; n: number; passo: number };

export function linhaCentral(geo: Geometria): LinhaCentral {
  const cx: number[] = [];
  const cy: number[] = [];
  for (let i = 0; i < geo.x.length; i += 1) {
    const [u, v] = base(geo.x[i], geo.z[i]);
    cx.push(u);
    cy.push(v);
  }
  return { cx, cy, n: cx.length, passo: geo.passoM };
}

/** O traçado de uma volta: linha central + lateral × normal, ponto a ponto da grade. */
export function tracadoDaVolta(geo: Geometria, lateral: ArrayLike<number>): { x: number[]; y: number[] } {
  const x: number[] = [];
  const y: number[] = [];
  for (let i = 0; i < geo.x.length; i += 1) {
    const l = Number(lateral[i]) || 0;
    const [u, v] = base(geo.x[i] + l * geo.normalX[i], geo.z[i] + l * geo.normalZ[i]);
    x.push(u);
    y.push(v);
  }
  return { x, y };
}

/** Posição em `s` no traçado (interpolada entre os pontos da grade; não passa da linha). */
export function posicaoEm(tracado: { x: number[]; y: number[] }, passo: number, s: number): Ponto {
  const n = tracado.x.length;
  const j = Math.max(0, s) / passo;
  const j0 = Math.floor(j);
  if (j0 >= n - 1) return [tracado.x[n - 1], tracado.y[n - 1]];
  const f = j - j0;
  return [tracado.x[j0] + f * (tracado.x[j0 + 1] - tracado.x[j0]), tracado.y[j0] + f * (tracado.y[j0 + 1] - tracado.y[j0])];
}

/** Onde escrever o nome de uma curva: por fora dela, além da borda. */
export function rotuloDaCurva(geo: Geometria, apiceS: number, lado: string, folgaM = 9): Ponto {
  const i = Math.round(apiceS / geo.passoM) % geo.x.length;
  const fora = lado === 'esq.' ? -1 : 1;
  const largura = (fora > 0 ? geo.larguraEsquerdaM?.[i] : geo.larguraDireitaM?.[i]) ?? 7;
  const w = largura + folgaM;
  return base(geo.x[i] + fora * w * geo.normalX[i], geo.z[i] + fora * w * geo.normalZ[i]);
}
