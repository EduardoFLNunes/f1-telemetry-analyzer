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
type Marca = { x: number; z: number; s?: number };

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
  minimas: { voce: Marca & { kmh: number }; referencia: Marca & { kmh: number } };
  tracado: { voce: [number, number]; referencia: [number, number]; distanciaM: number; lado: string };
};

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

/** "você freia 42 m antes da IA" (a distância de `freadas.distanciaM`: negativa = antes). */
export function textoDaFreada(distanciaM: number | null, contra = 'da IA'): string | null {
  if (distanciaM === null || distanciaM === undefined) return null;
  const m = Math.round(Math.abs(distanciaM));
  if (m < 1) return `você freia no mesmo ponto ${contra.replace(/^da /, 'que a ')}`;
  return `você freia ${m} m ${distanciaM < 0 ? 'antes' : 'depois'} ${contra}`;
}

/** "você passa 7,9 m mais à direita" (no ponto da mínima da referência; ADR 0003). */
export function textoDoTracado(t: CurvaDoReplay['tracado']): string {
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
