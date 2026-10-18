/**
 * A volta em andamento (`/api/live/volta`) no formato das voltas do store, para
 * o mesmo componente da tela Volta (pedido 31, Parte D.1).
 *
 * O backend manda, ponto a ponto da grade oficial, o que o coach já projetou
 * (lateral e o relógio desde a linha) e a velocidade e os pedais do quadro.
 * Aqui só se preenchem os buracos entre dois pontos medidos (interpolação) e,
 * depois do ponto atual, o relógio segue reto na velocidade do carro, para o
 * relógio da volta continuar crescendo (o componente só usa até o ponto atual).
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
  let ultimo = k;
  while (ultimo > 0 && !Number.isFinite(elapsed[ultimo])) ultimo -= 1;
  const v = Math.max(Number.isFinite(velocidade[ultimo]) ? velocidade[ultimo] : 0, VELOCIDADE_MINIMA_KMH) / 3.6;
  for (let i = ultimo + 1; i < n; i += 1) elapsed[i] = elapsed[ultimo] + ((i - ultimo) * r.passoM) / v;
  const total = elapsed[n - 1] + r.passoM / v;
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
      lateral: preencher(r.linhas.lateral, k, true),
    },
  };
}
