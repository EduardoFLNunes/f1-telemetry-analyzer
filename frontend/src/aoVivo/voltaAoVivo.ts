/**
 * A volta em andamento (`/api/live/volta`) no formato das voltas do store, para
 * o mesmo componente da tela Volta (pedido 31, Parte D.1).
 *
 * O backend manda, ponto a ponto da grade oficial, o que o coach já projetou
 * (lateral e o relógio desde a linha) e a velocidade e os pedais do quadro.
 * Aqui só se preenchem os buracos entre dois pontos medidos (interpolação) e,
 * depois do ponto atual, o relógio segue reto na velocidade do carro, para o
 * relógio da volta continuar crescendo (o componente só usa até o ponto atual).
 *
 * Pedido 35 (Parte D): a tela não recebe mais a volta inteira a cada leitura. O
 * `AcumuladorAoVivo` guarda os pontos e recebe só os novos (`/api/live/volta/novos`);
 * depois do ponto atual, a lateral e a velocidade ficam as do último ponto, para o
 * carro andar entre duas posições sem sair do traçado.
 */
import type { VoltaDoStore } from '../volta/dados';

export type VoltaDoBackend = {
  disponivel: boolean;
  volta: number | null;
  desdeALinha: boolean;
  comprimentoM: number;
  pontosDaGrade: number;
  passoM: number;
  indice: number;
  s: number;
  linhas: Record<'elapsed' | 'velocidade' | 'acelerador' | 'freio' | 'lateral', Array<number | null>>;
};

const VELOCIDADE_MINIMA_KMH = 30;

function preencher(valores: Array<number | null>, ate: number, interpolar: boolean): number[] {
  const out: number[] = new Array(valores.length).fill(Number.NaN);
  let anterior = -1;
  for (let i = 0; i <= ate; i += 1) {
    const v = valores[i];
    if (v === null || v === undefined || !Number.isFinite(v)) continue;
    out[i] = v;
    if (anterior >= 0 && i - anterior > 1) {
      for (let k = anterior + 1; k < i; k += 1) {
        out[k] = interpolar ? out[anterior] + ((v - out[anterior]) * (k - anterior)) / (i - anterior) : out[anterior];
      }
    }
    anterior = i;
  }
  return out;
}

/** A volta em andamento como `VoltaDoStore`; null antes da primeira passagem pela linha. */
export function voltaDoAoVivo(r: VoltaDoBackend | null, geometryId: string): VoltaDoStore | null {
  if (!r || !r.disponivel || !r.desdeALinha) return null;
  const n = r.pontosDaGrade;
  const k = Math.min(Math.max(0, r.indice), n - 1);
  const elapsed = preencher(r.linhas.elapsed, k, true);
  // Antes do primeiro ponto medido da volta: do zero na linha até ele.
  const primeiro = elapsed.findIndex((v) => Number.isFinite(v));
  if (primeiro < 0) return null;
  for (let i = 0; i < primeiro; i += 1) elapsed[i] = (elapsed[primeiro] * i) / Math.max(primeiro, 1);
  const velocidade = preencher(r.linhas.velocidade, k, false);
  const lateral = preencher(r.linhas.lateral, k, true);
  let ultimo = k;
  while (ultimo > 0 && !Number.isFinite(elapsed[ultimo])) ultimo -= 1;
  const v = Math.max(Number.isFinite(velocidade[ultimo]) ? velocidade[ultimo] : 0, VELOCIDADE_MINIMA_KMH) / 3.6;
  for (let i = ultimo + 1; i < n; i += 1) elapsed[i] = elapsed[ultimo] + ((i - ultimo) * r.passoM) / v;
  const total = elapsed[n - 1] + r.passoM / v;
  // Depois do ponto atual: a lateral e a velocidade do último ponto medido (pedido 35).
  for (let i = ultimo + 1; i < n; i += 1) {
    lateral[i] = lateral[ultimo];
    velocidade[i] = velocidade[ultimo];
  }
  const numero = Number(r.volta ?? 0);
  return {
    lapId: `ao-vivo#${String(Number.isFinite(numero) ? numero : 0).padStart(4, '0')}`,
    gravacao: '',
    tempoS: elapsed[ultimo],
    replayLapId: null,
    geometryId,
    pontosDaGrade: n,
    comprimentoM: r.comprimentoM,
    passoM: r.passoM,
    linhas: {
      elapsed,
      total,
      velocidade,
      acelerador: preencher(r.linhas.acelerador, k, false),
      freio: preencher(r.linhas.freio, k, false),
      lateral,
    },
  };
}

const NOMES = ['elapsed', 'velocidade', 'acelerador', 'freio', 'lateral'] as const;
type Nome = (typeof NOMES)[number];

export type RespostaNovos = Omit<VoltaDoBackend, 'linhas'> & {
  versao: number;
  seq: number;
  completa: boolean;
  carro?: { s: number; indice: number; velocidadeKmh: number | null; tempoDaVolta: number | null; seq: number };
  linhas?: VoltaDoBackend['linhas'];
  pontos?: { indices: number[] } & Record<Nome, Array<number | null>>;
};

/**
 * A volta ao vivo na tela (pedido 35): guarda os pontos e recebe só os novos.
 * `aplicar` devolve se algo mudou; `volta` monta a volta no formato da tela Volta.
 */
export class AcumuladorAoVivo {
  versao: number | null = null;
  seq: number | null = null;
  cabecalho: Omit<VoltaDoBackend, 'linhas'> | null = null;
  carro: RespostaNovos['carro'] | null = null;
  private linhas: VoltaDoBackend['linhas'] | null = null;

  aplicar(r: RespostaNovos | null): boolean {
    if (!r || !r.disponivel) {
      const mudou = this.cabecalho !== null;
      this.versao = this.seq = null;
      this.cabecalho = this.linhas = null;
      this.carro = null;
      return mudou;
    }
    if (r.completa && r.linhas) {
      this.linhas = { ...r.linhas };
    } else if (r.pontos && this.linhas && r.versao === this.versao) {
      const { indices } = r.pontos;
      NOMES.forEach((nome) => {
        const destino = this.linhas![nome];
        r.pontos![nome].forEach((valor, j) => {
          destino[indices[j]] = valor;
        });
      });
    } else {
      return false; // pontos de outra volta sem a volta inteira: espera a próxima leitura
    }
    const { linhas: _l, pontos: _p, carro, versao, seq, completa: _c, ...cabecalho } = r;
    void _l; void _p; void _c;
    const mudou = this.seq !== seq || this.versao !== versao;
    this.versao = versao;
    this.seq = seq;
    this.carro = carro ?? null;
    this.cabecalho = cabecalho;
    return mudou;
  }

  volta(geometryId: string): VoltaDoStore | null {
    if (!this.cabecalho || !this.linhas) return null;
    return voltaDoAoVivo({ ...this.cabecalho, linhas: this.linhas }, geometryId);
  }
}
