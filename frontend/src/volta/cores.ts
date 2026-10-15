/** Cores do canvas e dos mapas da tela Volta, lidas das variáveis do tema (tokens.css). */

const lidas = new Map<string, string>();

export function token(nome: string, padrao: string): string {
  if (typeof window === 'undefined') return padrao;
  const guardada = lidas.get(nome);
  if (guardada) return guardada;
  const v = getComputedStyle(document.documentElement).getPropertyValue(nome).trim() || padrao;
  lidas.set(nome, v);
  return v;
}

function rgb(cor: string): [number, number, number] {
  const c = cor.trim();
  if (c.startsWith('#')) {
    const h = c.length === 4 ? c.slice(1).split('').map((x) => x + x).join('') : c.slice(1, 7);
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
  }
  const m = /rgba?\(([^)]+)\)/.exec(c);
  if (m) {
    const [r, g, b] = m[1].split(',').map((x) => parseFloat(x));
    return [r, g, b];
  }
  return [128, 128, 128];
}

export function misturar(a: string, b: string, t: number): string {
  const A = rgb(a);
  const B = rgb(b);
  return `rgb(${A.map((x, i) => Math.round(x + (B[i] - x) * t)).join(',')})`;
}

/** A escala do protótipo: ganho em azul; perda do marrom ao laranja, saturando em 0,45 s. */
export function calor(v: number): string {
  if (!Number.isFinite(v)) return token('--pista-desenho', '#2a2f36');
  if (v < 0) return token('--ganho', '#6f9bff');
  return misturar(token('--perda-fraca', '#4a3322'), token('--perda', '#ffa24a'), Math.min(v / 0.45, 1));
}

export const CORES_DO_PEDAL = {
  freio: () => token('--freio', '#ff5a5f'),
  acelerador: () => token('--acelerador', '#3ddc84'),
  parcial: () => token('--parcial', '#f5c542'),
};
