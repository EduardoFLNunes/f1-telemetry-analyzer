/**
 * Contraste do texto sobre o vidro e o fundo (pedido 29), pela fórmula do
 * WCAG 2.1 (luminância relativa e razão (L1 + 0,05) / (L2 + 0,05)).
 *
 * O vidro é translúcido: a cor atrás do texto é o vidro composto sobre o
 * fundo. O pior caso para texto claro é o ponto mais claro do fundo, no centro
 * do brilho vermelho, com a trama por cima. O desfoque só mistura cores
 * vizinhas e nunca deixa o fundo mais claro que esse ponto, então o pior caso
 * vale com e sem desfoque.
 *
 * Usado pelo guia visual (tela Sistema) e por `scripts/contraste.ts`, que grava
 * a tabela do relatório. Sem imports, para rodar no Node direto.
 */

export type Rgba = { r: number; g: number; b: number; a: number };

/** `#rrggbb`, `#rgb` ou `rgba(r, g, b, a)`. */
export function lerCor(texto: string): Rgba {
  const t = texto.trim().toLowerCase();
  const hex = /^#([0-9a-f]{3}|[0-9a-f]{6})$/.exec(t);
  if (hex) {
    const h = hex[1].length === 3 ? hex[1].split('').map((c) => c + c).join('') : hex[1];
    return { r: parseInt(h.slice(0, 2), 16), g: parseInt(h.slice(2, 4), 16), b: parseInt(h.slice(4, 6), 16), a: 1 };
  }
  const rgb = /^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)$/.exec(t);
  if (rgb) return { r: Number(rgb[1]), g: Number(rgb[2]), b: Number(rgb[3]), a: rgb[4] === undefined ? 1 : Number(rgb[4]) };
  throw new Error(`cor que não sei ler: ${texto}`);
}

/** `frente` (com alfa) por cima de `fundo` (opaco). */
export function compor(frente: Rgba, fundo: Rgba): Rgba {
  const a = frente.a;
  return {
    r: frente.r * a + fundo.r * (1 - a),
    g: frente.g * a + fundo.g * (1 - a),
    b: frente.b * a + fundo.b * (1 - a),
    a: 1,
  };
}

export function luminancia(c: Rgba): number {
  const canal = (v: number) => {
    const s = v / 255;
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * canal(c.r) + 0.7152 * canal(c.g) + 0.0722 * canal(c.b);
}

export function razaoDeContraste(a: Rgba, b: Rgba): number {
  const la = luminancia(a);
  const lb = luminancia(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

export function hex(c: Rgba): string {
  const h = (v: number) => Math.round(v).toString(16).padStart(2, '0');
  return `#${h(c.r)}${h(c.g)}${h(c.b)}`;
}

/** Os valores de tokens.css que entram na conta. */
export type Tokens = Record<string, string>;

/** As superfícies em que há texto, compostas no pior caso. */
export function superficies(t: Tokens): Array<{ id: string; nome: string; cor: Rgba }> {
  const fundo = lerCor(t['--fundo']);
  const maisClaro = compor(lerCor(t['--fundo-trama']), compor(lerCor(t['--fundo-brilho-vermelho']), fundo));
  const frio = compor(lerCor(t['--fundo-trama']), compor(lerCor(t['--fundo-brilho-frio']), fundo));
  const vidro = compor(lerCor(t['--vidro-fundo']), maisClaro);
  const vidroFrio = compor(lerCor(t['--vidro-fundo']), frio);
  const opacaNoVidro = compor(lerCor(t['--superficie-no-vidro']), vidro);
  const dica = compor(lerCor(t['--vidro-fundo-forte']), maisClaro);
  return [
    { id: 'vidro', nome: 'vidro sobre o brilho vermelho (pior caso)', cor: vidro },
    { id: 'vidro-frio', nome: 'vidro sobre o brilho frio', cor: vidroFrio },
    { id: 'opaca-no-vidro', nome: 'superfície opaca dentro do vidro', cor: opacaNoVidro },
    { id: 'dica', nome: 'dica (vidro forte)', cor: dica },
    { id: 'superficie', nome: 'superfície opaca (gráficos, tabelas, mapas)', cor: lerCor(t['--superficie']) },
    { id: 'sem-transparencia', nome: 'vidro sem transparência', cor: lerCor('#14171b') },
  ];
}

/** As cores que aparecem como texto. */
export const TEXTOS: ReadonlyArray<{ token: string; uso: string }> = [
  { token: '--texto-1', uso: 'títulos, números e corpo' },
  { token: '--texto-2', uso: 'texto de apoio' },
  { token: '--texto-3', uso: 'rótulos e legendas' },
  { token: '--vermelho-claro', uso: 'vermelho como texto' },
  { token: '--perda', uso: 'perda (+ e o número)' },
  { token: '--ganho', uso: 'ganho (− e o número)' },
  { token: '--tempo-verde', uso: 'a sua melhor' },
  { token: '--tempo-roxo', uso: 'a melhor de todas' },
  { token: '--tempo-amarelo', uso: 'sem melhora' },
  { token: '--estado-ok', uso: 'etiqueta ok' },
  { token: '--estado-aviso', uso: 'etiqueta de aviso' },
  { token: '--estado-erro', uso: 'etiqueta de erro' },
];

export type LinhaContraste = { token: string; uso: string; cor: string; razoes: Record<string, number>; pior: number; passaAA: boolean };

export function tabelaDeContraste(t: Tokens): { superficies: Array<{ id: string; nome: string; cor: string }>; linhas: LinhaContraste[] } {
  const sups = superficies(t);
  const linhas = TEXTOS.map(({ token, uso }) => {
    const cor = lerCor(t[token]);
    const razoes: Record<string, number> = {};
    for (const s of sups) razoes[s.id] = Math.round(razaoDeContraste(cor, s.cor) * 100) / 100;
    const pior = Math.min(...Object.values(razoes));
    return { token, uso, cor: hex(cor), razoes, pior, passaAA: pior >= 4.5 };
  });
  // Texto branco no botão vermelho.
  const branco = lerCor(t['--texto-sobre-vermelho']);
  const vermelho = lerCor(t['--vermelho']);
  const r = Math.round(razaoDeContraste(branco, vermelho) * 100) / 100;
  linhas.push({ token: '--texto-sobre-vermelho', uso: 'texto do botão vermelho (sobre --vermelho)', cor: hex(branco), razoes: { vermelho: r }, pior: r, passaAA: r >= 4.5 });
  return { superficies: sups.map((s) => ({ id: s.id, nome: s.nome, cor: hex(s.cor) })), linhas };
}

/** As variáveis de `:root` de um texto de CSS (o primeiro bloco `:root`). */
export function tokensDoCss(css: string): Tokens {
  const bloco = /:root\s*\{([\s\S]*?)\n\}/.exec(css);
  const out: Tokens = {};
  if (!bloco) return out;
  for (const m of bloco[1].matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/g)) out[m[1]] = m[2].trim();
  return out;
}
