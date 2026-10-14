/**
 * As medidas da tela Volta (pedido 30), no método do relatório de evolução.
 *
 * Porte direto de `backend/ml/comparison/evolution.py` e
 * `backend/ml/track/microsectors.py`, para que a tela, o protótipo A e o
 * `sessao_*.json` deem o mesmo número:
 *
 * - perda por curva: tempo do trecho da curva (do meio da reta anterior ao meio
 *   da seguinte) na volta menos na referência; os 14 trechos cobrem a volta;
 * - início da freada: primeiro ponto, do ápice da curva anterior ao ápice dela,
 *   em que o freio passa de < 0,15 para ≥ 0,15; a diferença é com sinal, em
 *   metros de pista;
 * - posição no ápice: lateral da volta menos a da referência no ponto do ápice;
 * - velocidade mínima: mínima dentro da curva, volta menos referência;
 * - microssetores: tempo em cada um dos 60, volta menos referência.
 *
 * Tudo em cima das linhas do store v2 (`/api/store/voltas/{id}`), que já estão
 * na grade da geometria oficial: o ponto i está em s = i · passo. Sem imports,
 * para o Node rodar a conferência (`scripts/conferencia_prototipo.ts`).
 */

export type Grade = {
  /** Número de pontos (2167 em Interlagos). */
  n: number;
  /** Comprimento da volta, em metros. */
  comprimento: number;
  /** Passo da grade, em metros. */
  passo: number;
};

export type Linhas = {
  elapsed: number[];
  /** Tempo da volta, pelo relógio do jogo (`lap_time_s` do store v2). */
  total: number;
  velocidade: number[];
  acelerador: number[];
  freio: number[];
  lateral: number[];
};

export type Curva = {
  /** C01 a C14. */
  codigo: string;
  /** 'esq.' ou 'dir.'. */
  lado: string;
  /** Trecho da curva: do meio da reta anterior ao meio da seguinte (pode cruzar a linha). */
  trecho: [number, number];
  /** A curva em si: onde a mínima é procurada. */
  curva: [number, number];
  apice: number;
};

/**
 * As 14 curvas do relatório de evolução (`sessao_*.json`, campo `curvas`),
 * encaixadas na grade.
 *
 * O JSON grava os limites arredondados a 0,1 m. No ML, o início, o fim e o
 * ápice de cada curva caem exatamente num ponto da grade, e o trecho cai no
 * meio entre dois pontos. Ler o valor arredondado poria o ápice no ponto
 * vizinho (298,0 m vira o ponto 148, e o ápice é o 149, em 298,0055 m), e a
 * lateral no ápice e a mínima sairiam de outro ponto. O encaixe no ponto (ou
 * meio ponto) mais próximo devolve o valor exato: conferido em 14/10 nos 42
 * limites das 14 curvas.
 */
export function curvasDoRelatorio(g: Grade, curvas: Array<{ curva: string; trecho_m: number[]; curva_m: number[]; apice_m: number }>): Curva[] {
  const noPonto = (v: number) => Math.round(v / g.passo) * g.passo;
  const noMeioPonto = (v: number) => (Math.round((2 * v) / g.passo) / 2) * g.passo;
  return curvas.map((c) => {
    const [codigo, lado] = String(c.curva).split('-');
    return {
      codigo,
      lado: lado === 'esq' ? 'esq.' : lado === 'dir' ? 'dir.' : String(lado || ''),
      trecho: [noMeioPonto(Number(c.trecho_m[0])), noMeioPonto(Number(c.trecho_m[1]))],
      curva: [noPonto(Number(c.curva_m[0])), noPonto(Number(c.curva_m[1]))],
      apice: noPonto(Number(c.apice_m)),
    };
  });
}

export const FREIO_LIGADO = 0.15;
export const ACELERADOR_CHEIO = 0.9;

/** Resto com o sinal do divisor, como o `np.mod`. */
export function mod(a: number, n: number): number {
  const r = a % n;
  return r < 0 ? r + n : r;
}

/** Arredonda meio para o par, como o `np.round`. */
export function arredondarParaPar(v: number): number {
  const piso = Math.floor(v);
  const fracao = v - piso;
  if (Math.abs(fracao - 0.5) < 1e-9) return piso % 2 === 0 ? piso : piso + 1;
  return Math.round(v);
}

/** `np.interp` (xs crescente), com os extremos presos. */
export function interp(x: number, xs: ArrayLike<number>, ys: ArrayLike<number>): number {
  const n = xs.length;
  if (x <= xs[0]) return ys[0];
  if (x >= xs[n - 1]) return ys[n - 1];
  let lo = 0;
  let hi = n - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (xs[mid] <= x) lo = mid;
    else hi = mid;
  }
  const t = (x - xs[lo]) / (xs[hi] - xs[lo]);
  return ys[lo] + t * (ys[hi] - ys[lo]);
}

export function sDoPonto(g: Grade, i: number): number {
  return i * g.passo;
}

/** Índice da grade de uma distância (com a volta na linha), como `TrackGeometry.index_of`. */
export function indiceDe(g: Grade, s: number): number {
  return Math.min(g.n - 1, Math.max(0, Math.floor(mod(s, g.comprimento) / g.passo)));
}

/** Índices da grade de `a` a `b`, dando a volta se preciso (`_window`). */
export function janela(g: Grade, a: number, b: number): number[] {
  const inicio = indiceDe(g, a);
  const vao = arredondarParaPar(mod(b - a, g.comprimento) / g.passo) + 1;
  const out = new Array<number>(vao);
  for (let k = 0; k < vao; k += 1) out[k] = (inicio + k) % g.n;
  return out;
}

/** `a − b` em metros de pista, no intervalo (−L/2, L/2]. */
export function distanciaComSinal(g: Grade, a: number, b: number): number {
  return mod(a - b + g.comprimento / 2, g.comprimento) - g.comprimento / 2;
}

function eixoComFim(g: Grade): number[] {
  const xs = new Array<number>(g.n + 1);
  for (let i = 0; i < g.n; i += 1) xs[i] = i * g.passo;
  xs[g.n] = g.comprimento;
  return xs;
}

const eixos = new WeakMap<Grade, number[]>();
function eixo(g: Grade): number[] {
  let xs = eixos.get(g);
  if (!xs) {
    xs = eixoComFim(g);
    eixos.set(g, xs);
  }
  return xs;
}

const relogios = new WeakMap<object, number[]>();
/** O relógio da volta com o tempo da volta na linha, no fim (guardado por volta). */
function relogio(v: Pick<Linhas, 'elapsed' | 'total'>): number[] {
  let ys = relogios.get(v);
  if (!ys) {
    ys = [...v.elapsed, v.total];
    relogios.set(v, ys);
  }
  return ys;
}

/** Tempo da volta no ponto `s`: o relógio vai de 0 em s = 0 ao tempo da volta na linha (`time_at`). */
export function tempoEm(g: Grade, v: Pick<Linhas, 'elapsed' | 'total'>, s: number): number {
  return interp(mod(s, g.comprimento), eixo(g), relogio(v));
}

/** O `s` em que a volta estava no tempo `t` (o inverso de `tempoEm`, sem passar da linha). */
export function sNoTempo(g: Grade, v: Pick<Linhas, 'elapsed' | 'total'>, t: number): number {
  if (t >= v.total) return g.comprimento;
  if (t <= v.elapsed[0]) return 0;
  return interp(t, relogio(v), eixo(g));
}

/** Tempo de um trecho; o que cruza a linha soma o fim e o começo da mesma volta (`segment_time`). */
export function tempoDoTrecho(g: Grade, v: Pick<Linhas, 'elapsed' | 'total'>, trecho: [number, number]): number {
  return mod(tempoEm(g, v, trecho[1]) - tempoEm(g, v, trecho[0]), v.total);
}

/** Início da freada entre o ápice da curva anterior e o ápice dela (`braking_point`). */
export function inicioDaFreada(g: Grade, freio: ArrayLike<number>, deS: number, apice: number): number | null {
  const idx = janela(g, deS, apice);
  const estendido = [mod(idx[0] - 1, g.n), ...idx];
  const ligado = estendido.map((i) => {
    const f = Number(freio[i]);
    return (Number.isFinite(f) ? f : 0) >= FREIO_LIGADO;
  });
  for (let k = 0; k < ligado.length - 1; k += 1) {
    if (ligado[k + 1] && !ligado[k]) return sDoPonto(g, idx[k]);
  }
  return null;
}

function minimo(valores: ArrayLike<number>, indices: number[]): number {
  let m = Infinity;
  for (const i of indices) {
    const v = Number(valores[i]);
    if (Number.isFinite(v) && v < m) m = v;
  }
  return m === Infinity ? NaN : m;
}

export type MedidaDaCurva = {
  codigo: string;
  lado: string;
  perdaS: number;
  /** A referência freia nesta curva. */
  refFreia: boolean;
  /** Início da freada da volta menos o da referência (m); negativo = antes. */
  freadaM: number | null;
  /** A volta tem freada medida nesta curva. */
  voltaFreia: boolean;
  /** Lateral no ápice, volta menos referência (m); positivo = mais à esquerda. */
  lateralApiceM: number;
  /** Velocidade mínima na curva, volta menos referência (km/h). */
  minimaKmh: number;
};

/** As 14 curvas de uma volta contra a referência (`lap_corner_features`). */
export function medidasDasCurvas(g: Grade, volta: Linhas, ref: Linhas, curvas: Curva[]): MedidaDaCurva[] {
  const n = curvas.length;
  return curvas.map((c, k) => {
    const anterior = curvas[(k - 1 + n) % n];
    const freadaVolta = inicioDaFreada(g, volta.freio, anterior.apice, c.apice);
    const freadaRef = inicioDaFreada(g, ref.freio, anterior.apice, c.apice);
    const dentro = janela(g, c.curva[0], c.curva[1]);
    const apice = indiceDe(g, c.apice);
    return {
      codigo: c.codigo,
      lado: c.lado,
      perdaS: tempoDoTrecho(g, volta, c.trecho) - tempoDoTrecho(g, ref, c.trecho),
      refFreia: freadaRef !== null,
      voltaFreia: freadaVolta !== null,
      freadaM: freadaVolta !== null && freadaRef !== null ? distanciaComSinal(g, freadaVolta, freadaRef) : null,
      lateralApiceM: Number(volta.lateral[apice]) - Number(ref.lateral[apice]),
      minimaKmh: minimo(volta.velocidade, dentro) - minimo(ref.velocidade, dentro),
    };
  });
}

/** Tempo em cada microssetor (`split_times`): a última borda é a linha, no tempo da volta. */
export function temposDosMicrossetores(g: Grade, v: Pick<Linhas, 'elapsed' | 'total'>, bordas: number[]): number[] {
  const xs = new Array<number>(g.n);
  for (let i = 0; i < g.n; i += 1) xs[i] = i * g.passo;
  const limites = bordas.map((b) => interp(b, xs, v.elapsed));
  limites[limites.length - 1] = v.total;
  const out: number[] = [];
  for (let k = 1; k < limites.length; k += 1) out.push(limites[k] - limites[k - 1]);
  return out;
}

export function diferencaPorMicrossetor(g: Grade, volta: Linhas, ref: Linhas, bordas: number[]): number[] {
  const a = temposDosMicrossetores(g, volta, bordas);
  const b = temposDosMicrossetores(g, ref, bordas);
  return a.map((v, i) => v - b[i]);
}

/** Diferença acumulada ponto a ponto da grade (s): volta menos referência. */
export function diferencaAcumulada(volta: Linhas, ref: Linhas): number[] {
  return volta.elapsed.map((t, i) => t - ref.elapsed[i]);
}

/** A curva em que `s` cai, pelos trechos (que cobrem a volta inteira). */
export function curvaEm(curvas: Curva[], s: number): Curva | null {
  for (const c of curvas) {
    const [a, b] = c.trecho;
    if (b >= a ? s >= a && s < b : s >= a || s < b) return c;
  }
  return null;
}

export type Pedal = 'freio' | 'acelerador' | 'parcial';

/** O estado do pedal: freio ≥ 0,15; acelerador ≥ 0,9; o resto é parcial ou sem pedal. */
export function pedalEm(g: Grade, v: Linhas, s: number): Pedal {
  const xs = eixo(g);
  const f = interp(mod(s, g.comprimento), xs, [...v.freio, v.freio[0]]);
  const a = interp(mod(s, g.comprimento), xs, [...v.acelerador, v.acelerador[0]]);
  if (f >= FREIO_LIGADO) return 'freio';
  if (a >= ACELERADOR_CHEIO) return 'acelerador';
  return 'parcial';
}

export function valorEm(g: Grade, valores: ArrayLike<number>, s: number): number {
  const xs = eixo(g);
  const ys = Array.from(valores);
  ys.push(Number(valores[0]));
  return interp(mod(s, g.comprimento), xs, ys);
}

export type ModoDoFantasma = 'curva' | 'volta';

export type EstadoDoFantasma = {
  s: number;
  /** Tempo da volta em `s`. */
  tempoVolta: number;
  /** Onde o fantasma da referência está, e o tempo dele. */
  sFantasma: number;
  tempoFantasma: number;
  /** Onde o fantasma recomeçou (início da curva, no modo por curva). */
  s0: number;
  /** Diferença desde `s0`: positivo = a volta perdeu tempo. */
  diferenca: number;
  curva: string | null;
};

/**
 * O fantasma da referência, posicionado pelo tempo (como no protótipo A):
 * onde a referência estava depois do mesmo tempo. No modo por curva, ele
 * recomeça junto com a volta no início do trecho de cada curva; o trecho que
 * cruza a linha recomeça em 0, onde a volta começa.
 */
export function estadoDoFantasma(g: Grade, volta: Linhas, ref: Linhas, curvas: Curva[], s: number, modo: ModoDoFantasma): EstadoDoFantasma {
  const tempoVolta = tempoEm(g, volta, s);
  let s0 = 0;
  let t0Volta = 0;
  let t0Ref = 0;
  let curva: string | null = null;
  if (modo === 'curva') {
    const c = curvaEm(curvas, s);
    if (c) {
      const [a, b] = c.trecho;
      s0 = b >= a ? a : s >= a ? a : 0;
      t0Volta = tempoEm(g, volta, s0);
      t0Ref = tempoEm(g, ref, s0);
      curva = c.codigo;
    }
  }
  const tg = t0Ref + (tempoVolta - t0Volta);
  const sFantasma = tg >= ref.total ? g.comprimento : sNoTempo(g, ref, tg);
  const diferenca = tempoVolta - t0Volta - (tempoEm(g, ref, s) - t0Ref);
  return { s, tempoVolta, sFantasma, tempoFantasma: Math.min(tg, ref.total), s0, diferenca, curva };
}
