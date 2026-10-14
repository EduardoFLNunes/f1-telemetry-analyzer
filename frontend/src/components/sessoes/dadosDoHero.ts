/**
 * Os números do hero e da lista de sessões (pedido 29), todos de dado real e
 * cada um de uma fonte só:
 *
 * - voltas válidas e melhor volta de uma sessão: a conferência da Coleta
 *   (`/api/coleta/verificacoes/{id}`), que usa os portões do pipeline e o
 *   relógio da grade, como o store v2 (`lap_time_s`). A lista de sessões do
 *   gravador (`/api/sessions`) mede a volta de outro jeito e dá outros números
 *   (13/10: 13 válidas e 1:29,757 contra 9 e 1:29,768); dela só sai a data;
 * - sua melhor volta e a volta da IA: as referências do modelo do coach
 *   (`/api/coleta/antes`, `coach.modelo.referencias`);
 * - a M1: a contagem oficial (`/api/coleta/m1/oficial`).
 *
 * Sem o dado, o número fica `null` e a tela mostra "sem dados".
 */
import { formatarTempo } from '../../utils/coleta';

export { formatarTempo };

export type ResumoConferido = { voltasValidas: number; melhorS: number | null };

/** Voltas que entram no store e a mais rápida delas, de uma conferência pronta. */
export function resumoDaConferencia(resultado: any): ResumoConferido | null {
  const voltas: any[] = Array.isArray(resultado?.voltas) ? resultado.voltas : [];
  if (!resultado || !Array.isArray(resultado.voltas)) return null;
  const entram = voltas.filter((v) => v?.entraNoStore);
  const tempos = entram.map((v) => Number(v?.tempoS)).filter((t) => Number.isFinite(t) && t > 0);
  return {
    voltasValidas: Number.isFinite(Number(resultado?.veredito?.voltasValidas)) ? Number(resultado.veredito.voltasValidas) : entram.length,
    melhorS: tempos.length ? Math.min(...tempos) : null,
  };
}

/** `2026-10-04_02-24-04_vhe_interlagos#0018` → a sessão e o número da volta no store v2. */
export function partesDoLapId(lapId: unknown): { sessao: string; sequencia: number | null } | null {
  if (typeof lapId !== 'string' || !lapId.includes('#')) return null;
  const [sessao, numero] = lapId.split('#');
  const sequencia = Number(numero);
  return sessao ? { sessao, sequencia: Number.isFinite(sequencia) ? sequencia : null } : null;
}

/**
 * A volta gravada que é a referência do coach.
 *
 * O número do store v2 (`#0018`) não é o número da volta no jogo, e a lista do
 * gravador numera pelo jogo. A volta é achada pelo tempo: a única com duração a
 * menos de `tolerancia` do tempo da referência. Nenhuma, ou mais de uma → nada
 * é traçado. Em 04/10, a `#0018` (89,389 s) é a volta 5 do jogo (89,388 s).
 */
export function voltaPeloTempo<T extends { duration?: unknown; lapTime?: unknown }>(
  voltas: T[],
  tempoS: number,
  tolerancia = 0.05,
): T | null {
  const perto = voltas.filter((v) => {
    const d = Number(v?.duration ?? v?.lapTime);
    return Number.isFinite(d) && Math.abs(d - tempoS) < tolerancia;
  });
  return perto.length === 1 ? perto[0] : null;
}

/**
 * O trecho das amostras que é a volta de referência.
 *
 * O gravador agrupa as amostras pelo número da volta do jogo, e esse número se
 * repete quando a sessão recomeça: em 04/10, a "volta 5" do gravador junta uma
 * passagem de 85,1 s e, 46 min depois, a de 89,388 s. O relógio da volta
 * (`lap_time`) zera a cada passagem; o trecho certo é o que termina mais perto
 * do tempo da referência, a menos de `tolerancia`. Nenhum → nada é traçado.
 */
export function trechoDaVolta<T extends { lap_time?: unknown; lapTime?: unknown }>(
  amostras: T[],
  tempoS: number,
  tolerancia = 0.05,
): T[] | null {
  const relogio = (a: T) => Number(a?.lap_time ?? a?.lapTime);
  const trechos: T[][] = [];
  let atual: T[] = [];
  let anterior = -Infinity;
  for (const a of amostras) {
    const t = relogio(a);
    if (Number.isFinite(t) && t < anterior - 1 && atual.length) {
      trechos.push(atual);
      atual = [];
    }
    atual.push(a);
    if (Number.isFinite(t)) anterior = t;
  }
  if (atual.length) trechos.push(atual);
  let melhor: T[] | null = null;
  let menor = Infinity;
  for (const trecho of trechos) {
    const fim = relogio(trecho[trecho.length - 1]);
    const erro = Math.abs(fim - tempoS);
    if (Number.isFinite(erro) && erro < menor) {
      menor = erro;
      melhor = trecho;
    }
  }
  return melhor && menor < tolerancia ? melhor : null;
}

/** 13/10 · 19:24. */
export function dataCurtaDaSessao(valor: unknown): string | null {
  if (typeof valor !== 'string' || !valor) return null;
  const d = new Date(valor);
  if (Number.isNaN(d.getTime())) return null;
  const dois = (n: number) => String(n).padStart(2, '0');
  return `${dois(d.getDate())}/${dois(d.getMonth() + 1)} · ${dois(d.getHours())}:${dois(d.getMinutes())}`;
}

/** A data de uma sessão pelo nome (`2026-10-04_02-24-04_…`), para a referência. */
export function dataDoNomeDaSessao(sessao: string | null | undefined): string | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})_/.exec(String(sessao || ''));
  return m ? `${m[3]}/${m[2]}` : null;
}
