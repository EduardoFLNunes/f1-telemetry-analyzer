/**
 * O replay da curva (pedido 36, Parte E): as contas, sem React.
 *
 * Os dados vêm de `/api/radio/replay/<id>` (`backend/core/radio/replay.py`): para cada
 * curva citada pelo rádio, as duas linhas (você e a referência) na geometria oficial, com
 * o tempo desde a mesma entrada e o pedal, as freadas, as mínimas, o traçado e a perda.
 * Sempre "você" e "IA (referência)": a diferença medida contra uma volta real (ADR 0012).
 */
import { base } from '../volta/projecao';

/** [x, z, tempo desde a entrada da curva, pedal (0 parcial, 1 acelerador, 2 freio)] */
export type PontoDoReplay = [number, number, number, number];
/** `dM`: a distância desde a entrada do replay, em metros (pedido 43; ausente num backend antigo). */
type Marca = { x: number; z: number; s?: number; dM?: number };

export type CurvaDoReplay = {
  curva: string;
  lado: string;
  volta: number | null;
  referencia: string | null;
  rotuloDaReferencia: string;
  perdaS: number;
  duracaoS: number;
  linhas: { voce: PontoDoReplay[]; referencia: PontoDoReplay[] };
  freadas: { voce: Marca | null; referencia: Marca | null; distanciaM: number | null };
  /** Pedido 43: `null` na frase do coach sem as duas mínimas. */
  minimas: { voce: Marca & { kmh: number }; referencia: Marca & { kmh: number } } | null;
  /** Pedido 43: `null` na frase do coach (o coach não mede o lado). */
  tracado: { voce: [number, number]; referencia: [number, number]; distanciaM: number; lado: string } | null;
  // Pedido 43 (os visuais e os números da voz); um backend antigo não manda.
  passoM?: number;
  velocidades?: { voce: number[]; referencia: number[] };
  secoes?: { freadaM: number | null; minimaM: number | null; saidaM: number | null };
  voz?: { microssetor: number; inicioM: number; fimM: number; perdaS: number | null } | null;
  /** Na análise: a diferença acumulada no trecho da curva, do zero à perda da curva. */
  diferencaNoTrecho?: DiferencaNoTrecho | null;
};

export type DiferencaNoTrecho = { comprimentoM: number; passoM: number; entradaDoReplayM: number; valores: number[] };

export type DadosDoReplay = { id: number; origem: string; curvas: CurvaDoReplay[] };

const nf = (v: number, casas: number) => v.toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas });

/** Onde o carro está no tempo `t` (cada um no seu próprio tempo); o fim da linha depois dela. */
export function posicaoNoTempo(linha: PontoDoReplay[], t: number): [number, number] {
  if (!linha.length) return [0, 0];
  if (t <= linha[0][2]) return [linha[0][0], linha[0][1]];
  const n = linha.length;
  if (t >= linha[n - 1][2]) return [linha[n - 1][0], linha[n - 1][1]];
  let a = 0;
  let b = n - 1;
  while (b - a > 1) {
    const m = (a + b) >> 1;
    if (linha[m][2] <= t) a = m;
    else b = m;
  }
  const p = linha[a];
  const q = linha[b];
  const u = q[2] > p[2] ? (t - p[2]) / (q[2] - p[2]) : 0;
  return [p[0] + (q[0] - p[0]) * u, p[1] + (q[1] - p[1]) * u];
}

export type Camera = {
  ang: number; k: number; ax: number; ay: number; rcx: number; rcy: number;
  /** Do mundo (x, z) para a tela. */
  tela: (x: number, z: number) => [number, number];
};

/**
 * A câmera que mostra a curva inteira: a entrada para cima (a direção dos primeiros pontos da
 * referência), na orientação do mapa do app (`base(x, z) = (z, −x)`), encaixada em `largura` x
 * `altura` com `margem` e a faixa de cima (`topo`).
 */
export function cameraDaCurva(c: CurvaDoReplay, largura: number, altura: number, margem = 18, topo = 26): Camera {
  const ref = c.linhas.referencia;
  const p0 = base(ref[0][0], ref[0][1]);
  const p1 = base(ref[Math.min(ref.length - 1, 10)][0], ref[Math.min(ref.length - 1, 10)][1]);
  const ang = -Math.PI / 2 - Math.atan2(p1[1] - p0[1], p1[0] - p0[0]);
  const cs = Math.cos(ang);
  const sn = Math.sin(ang);
  const girar = (x: number, z: number): [number, number] => {
    const [u, v] = base(x, z);
    return [u * cs - v * sn, u * sn + v * cs];
  };
  let x0 = Infinity;
  let x1 = -Infinity;
  let y0 = Infinity;
  let y1 = -Infinity;
  for (const p of [...c.linhas.voce, ...ref]) {
    const [gx, gy] = girar(p[0], p[1]);
    x0 = Math.min(x0, gx);
    x1 = Math.max(x1, gx);
    y0 = Math.min(y0, gy);
    y1 = Math.max(y1, gy);
  }
  const w = Math.max(x1 - x0, 1);
  const h = Math.max(y1 - y0, 1);
  const k = Math.min((largura - 2 * margem) / w, (altura - 2 * margem - topo) / h);
  const ax = largura / 2;
  const ay = topo + (altura - topo) / 2;
  const rcx = (x0 + x1) / 2;
  const rcy = (y0 + y1) / 2;
  return {
    ang, k, ax, ay, rcx, rcy,
    tela: (x, z) => {
      const [gx, gy] = girar(x, z);
      return [ax + k * (gx - rcx), ay + k * (gy - rcy)];
    },
  };
}

/** "perde 0,92 s nesta curva" (com a unidade). */
export function textoDaPerda(perdaS: number): string {
  return `${perdaS >= 0 ? 'perde' : 'ganha'} ${nf(Math.abs(perdaS), 2)} s nesta curva`;
}

/**
 * O alto do replay. Na frase do coach (pedido 43), o tempo é o da voz, no trecho da fala; na
 * análise, a perda na curva: "C12, esquerda · volta 2 · perde 0,64 s no trecho da fala".
 */
export function textoDoAlto(c: CurvaDoReplay): string {
  const inicio = `${c.curva}, ${c.lado}${c.volta ? ` · volta ${c.volta}` : ''}`;
  if (c.voz) {
    const p = c.voz.perdaS;
    return p === null || p === undefined ? inicio : `${inicio} · ${p >= 0 ? 'perde' : 'ganha'} ${nf(Math.abs(p), 2)} s no trecho da fala`;
  }
  return `${inicio} · ${textoDaPerda(c.perdaS)}`;
}

// ── os visuais (pedido 43, Parte C) ─────────────────────────────────────

/** A curva tem os dados dos visuais (um backend antigo não manda). */
export function temVisuais(c: CurvaDoReplay): boolean {
  return !!c.passoM && !!c.velocidades && c.velocidades.voce.length === c.linhas.voce.length
    && c.velocidades.referencia.length === c.linhas.referencia.length;
}

/** Onde o carro está no tempo `t`, em metros desde a entrada (o cursor dos visuais). */
export function distanciaNoTempo(linha: PontoDoReplay[], t: number, passoM: number): number {
  const n = linha.length;
  if (!n) return 0;
  if (t <= linha[0][2]) return 0;
  if (t >= linha[n - 1][2]) return (n - 1) * passoM;
  let a = 0;
  let b = n - 1;
  while (b - a > 1) {
    const m = (a + b) >> 1;
    if (linha[m][2] <= t) a = m;
    else b = m;
  }
  const u = linha[b][2] > linha[a][2] ? (t - linha[a][2]) / (linha[b][2] - linha[a][2]) : 0;
  return (a + u) * passoM;
}

/**
 * A diferença acumulada (C.2), ponto a ponto: o seu tempo menos o da referência desde a mesma
 * entrada. Sobe quando você perde, desce quando ganha.
 */
export function diferencaAcumulada(c: CurvaDoReplay): number[] {
  const v = c.linhas.voce;
  const r = c.linhas.referencia;
  return v.map((p, i) => p[2] - (r[i] ? r[i][2] : r[r.length - 1][2]));
}

/**
 * A linha da diferença acumulada e o seu eixo. Na análise, o trecho inteiro da curva (o eixo
 * não é o da animação: `deslocamento` leva a distância do replay para ele). Na frase do coach e
 * num backend antigo, a janela do replay.
 */
export type SerieDaDiferenca = { valores: number[]; passoM: number; totalM: number; deslocamento: number };

export function serieDaDiferenca(c: CurvaDoReplay): SerieDaDiferenca {
  const n = c.diferencaNoTrecho;
  if (n && n.valores.length > 1) {
    return { valores: n.valores, passoM: n.passoM, totalM: n.comprimentoM, deslocamento: n.entradaDoReplayM };
  }
  const passoM = c.passoM ?? 1;
  const valores = diferencaAcumulada(c);
  return { valores, passoM, totalM: Math.max((valores.length - 1) * passoM, 1), deslocamento: 0 };
}

/** As faixas do pedal (C.3): trechos seguidos com o mesmo pedal, em metros [de, até, pedal]. */
export function faixasDoPedal(linha: PontoDoReplay[], passoM: number): [number, number, number][] {
  const out: [number, number, number][] = [];
  for (let i = 0; i < linha.length; i += 1) {
    const pedal = linha[i][3];
    const de = Math.max(0, (i - 0.5) * passoM);
    const ate = Math.min((linha.length - 1) * passoM, (i + 0.5) * passoM);
    const ultimo = out[out.length - 1];
    if (ultimo && ultimo[2] === pedal) ultimo[1] = ate;
    else out.push([de, ate, pedal]);
  }
  return out;
}

/** Os índices da linha dentro do trecho da fala (para a faixa clara na pista). */
export function indicesDoTrecho(c: CurvaDoReplay): [number, number] | null {
  if (!c.voz || !c.passoM) return null;
  const n = c.linhas.referencia.length;
  const a = Math.max(0, Math.round(c.voz.inicioM / c.passoM));
  const b = Math.min(n - 1, Math.round(c.voz.fimM / c.passoM));
  return b > a ? [a, b] : null;
}

/**
 * Onde cada parte fica na área do replay (pedido 43). A ordem de importância, quando a altura
 * não dá para tudo: o replay, a faixa do pedal, a diferença acumulada e a velocidade. O replay
 * fica com pelo menos `REPLAY_MINIMO`; cada visual só entra se ainda sobrar isso para ele.
 * A mesma regra da janela do jogo (`radio_engenheiro.lua`, `dividirAJanela`).
 */
export const ALTURAS_DOS_VISUAIS = { pedal: 30, diferenca: 60, velocidade: 74 } as const;
export const REPLAY_MINIMO = 150;
export type Area = { x: number; y: number; w: number; h: number };
export type Divisao = { replay: Area; pedal: Area | null; diferenca: Area | null; velocidade: Area | null };

export function dividirAArea(x: number, y: number, w: number, h: number, comVisuais: boolean): Divisao {
  const out: Divisao = { replay: { x, y, w, h }, pedal: null, diferenca: null, velocidade: null };
  if (!comVisuais) return out;
  let resto = h;
  const entram: (keyof typeof ALTURAS_DOS_VISUAIS)[] = [];
  for (const nome of ['pedal', 'diferenca', 'velocidade'] as const) {
    if (resto - ALTURAS_DOS_VISUAIS[nome] < REPLAY_MINIMO) break;
    resto -= ALTURAS_DOS_VISUAIS[nome];
    entram.push(nome);
  }
  out.replay = { x, y, w, h: resto };
  // De cima para baixo, sob o replay: o pedal (colado nos carros), a diferença e a velocidade.
  let yy = y + resto;
  for (const nome of ['pedal', 'diferenca', 'velocidade'] as const) {
    if (!entram.includes(nome)) continue;
    out[nome] = { x, y: yy, w, h: ALTURAS_DOS_VISUAIS[nome] };
    yy += ALTURAS_DOS_VISUAIS[nome];
  }
  return out;
}

// ── a grade da sessão (pedido 43, C.4) ──────────────────────────────────

export type GradeDaSessao = {
  sessao: string | null;
  curvas: string[];
  voltas: { volta: number | null; tempoS: number; perdas: (number | null)[] }[];
  fora: { volta: number | null; tempoS: number | null; motivo: string; citadas?: string[] }[];
  citadas: { volta: number; curva: string; origem: 'coach' | 'analise'; id: number; perdaS?: number }[];
};

/** A perda que pinta a célula com a cor mais forte. */
export const PERDA_FORTE_S = 1.0;

/** "0,81 s", "−0,36 s" (com a unidade). */
export function textoDaCelula(perdaS: number): string {
  return `${perdaS < 0 ? '−' : ''}${nf(Math.abs(perdaS), 2)} s`;
}

/** A força da cor da célula, de 0,15 a 0,9, pela perda (a perda e o ganho, cada um na sua cor). */
export function forcaDaCelula(perdaS: number): number {
  return 0.15 + 0.75 * Math.min(1, Math.abs(perdaS) / PERDA_FORTE_S);
}

/** As curvas citadas numa volta, cada uma com quem citou. */
export function citadasNaVolta(g: GradeDaSessao, volta: number | null): Map<string, string[]> {
  const out = new Map<string, string[]>();
  for (const c of g.citadas) {
    if (c.volta !== volta) continue;
    out.set(c.curva, [...(out.get(c.curva) ?? []), c.origem]);
  }
  return out;
}

/** "volta 12: incompleta (1:43,199); citada: C11" — o tempo no formato M:SS,mmm. */
export function textoDaVoltaDeFora(f: GradeDaSessao['fora'][number]): string {
  const tempo = f.tempoS === null || f.tempoS === undefined ? '' : ` (${tempoDeVolta(f.tempoS)})`;
  const citadas = f.citadas && f.citadas.length ? `; citada: ${f.citadas.join(', ')}` : '';
  return `volta ${f.volta ?? '?'}: ${f.motivo}${tempo}${citadas}`;
}

export function tempoDeVolta(s: number): string {
  const m = Math.floor(s / 60);
  const resto = s - 60 * m;
  return `${m}:${resto < 10 ? '0' : ''}${nf(resto, 3)}`;
}

/** "você freia 42 m antes da IA" (a distância de `freadas.distanciaM`: negativa = antes). */
export function textoDaFreada(distanciaM: number | null, contra = 'da IA'): string | null {
  if (distanciaM === null || distanciaM === undefined) return null;
  const m = Math.round(Math.abs(distanciaM));
  if (m < 1) return `você freia no mesmo ponto ${contra.replace(/^da /, 'que a ')}`;
  return `você freia ${m} m ${distanciaM < 0 ? 'antes' : 'depois'} ${contra}`;
}

/** "você passa 7,9 m mais à direita" (no ponto da mínima da referência; ADR 0003). */
export function textoDoTracado(t: NonNullable<CurvaDoReplay['tracado']>): string {
  return `você passa ${nf(t.distanciaM, 1)} m mais à ${t.lado}`;
}

/** "102 km/h" */
export function textoDaMinima(kmh: number): string {
  return `${Math.round(kmh)} km/h`;
}

/**
 * Os rótulos do replay não cobrem um ao outro, nem os carros e as marcas, nem saem da área:
 * cada um tenta, em ordem, os lugares em volta do seu ponto (o preferido primeiro), encostado e
 * depois cada vez mais longe (com um fio até o ponto); se nenhum estiver livre, fica no
 * preferido, empurrado para dentro. A mesma regra do app do jogo (`radio_engenheiro.lua`, `rotulo`).
 */
export type LugarDoRotulo =
  | 'direita' | 'esquerda' | 'abaixo' | 'acima' | 'direitaAcima' | 'esquerdaAbaixo' | 'direitaAbaixo' | 'esquerdaAcima';
type Caixa = [number, number, number, number];
const LUGARES: LugarDoRotulo[] = [
  'direita', 'esquerda', 'abaixo', 'acima', 'direitaAcima', 'esquerdaAbaixo', 'direitaAbaixo', 'esquerdaAcima',
];
const AFASTAMENTOS = [0, 14, 28, 44, 60];
const DIRECAO: Record<LugarDoRotulo, [number, number]> = {
  direita: [1, 0], esquerda: [-1, 0], abaixo: [0, 1], acima: [0, -1],
  direitaAcima: [0.7, -0.7], esquerdaAbaixo: [-0.7, 0.7], direitaAbaixo: [0.7, 0.7], esquerdaAcima: [-0.7, -0.7],
};

function cantoDoRotulo(lugar: LugarDoRotulo, x: number, y: number, w: number, h: number): [number, number] {
  switch (lugar) {
    case 'direita': return [x + 8, y - h / 2];
    case 'esquerda': return [x - 8 - w, y - h / 2];
    case 'abaixo': return [x - w / 2, y + 8];
    case 'acima': return [x - w / 2, y - 8 - h];
    case 'direitaAcima': return [x + 6, y - 6 - h];
    case 'esquerdaAbaixo': return [x - 6 - w, y + 6];
    case 'direitaAbaixo': return [x + 6, y + 6];
    default: return [x - 6 - w, y - 6 - h];
  }
}

export class QuadroDeRotulos {
  readonly ocupados: Caixa[] = [];
  constructor(readonly area: Caixa) {}

  ocupar(x: number, y: number, raio: number) {
    this.ocupados.push([x - raio, y - raio, x + raio, y + raio]);
  }

  /**
   * O canto de cima à esquerda da caixa do rótulo (largura `w`, altura `h`), e a ocupa. O terceiro
   * valor diz se a caixa ficou longe do ponto (então vale um fio até ele).
   */
  colocar(x: number, y: number, w: number, h: number, preferido: LugarDoRotulo): [number, number, boolean] {
    const [a0, a1, a2, a3] = this.area;
    const livre = (bx: number, by: number) =>
      bx >= a0 && by >= a1 && bx + w <= a2 && by + h <= a3
      && this.ocupados.every((r) => !(bx < r[2] && r[0] < bx + w && by < r[3] && r[1] < by + h));
    let canto: [number, number] | null = null;
    let longe = false;
    for (const d of AFASTAMENTOS) {
      for (const lugar of [preferido, ...LUGARES]) {
        const c = cantoDoRotulo(lugar, x + DIRECAO[lugar][0] * d, y + DIRECAO[lugar][1] * d, w, h);
        if (livre(c[0], c[1])) {
          canto = c;
          longe = d > 0;
          break;
        }
      }
      if (canto) break;
    }
    if (!canto) {
      const [bx, by] = cantoDoRotulo(preferido, x, y, w, h);
      canto = [Math.min(Math.max(bx, a0), a2 - w), Math.min(Math.max(by, a1), a3 - h)];
    }
    this.ocupados.push([canto[0], canto[1], canto[0] + w, canto[1] + h]);
    return [canto[0], canto[1], longe];
  }
}
