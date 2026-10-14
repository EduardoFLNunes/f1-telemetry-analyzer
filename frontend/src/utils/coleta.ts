/**
 * Formatação da aba "Coleta de dados" (pedido 28).
 *
 * O que é preciso vem do registro do backend (`/api/coleta/requisitos`); aqui
 * só se decide como mostrar: tempos em M:SS,mmm, números com vírgula e a cor
 * de cada estado.
 */

export type EstadoCanal = 'ok' | 'ausente' | 'parado' | 'fora_da_faixa' | 'taxa_baixa' | 'sem_dados';

export const ROTULO_ESTADO: Record<EstadoCanal, string> = {
  ok: 'ok',
  ausente: 'ausente',
  parado: 'parado',
  fora_da_faixa: 'fora da faixa',
  taxa_baixa: 'taxa baixa',
  sem_dados: 'sem dados',
};

/** Tom de cada estado: verde, âmbar, vermelho ou neutro. */
export function tomDoEstado(estado: string | null | undefined): 'ok' | 'aviso' | 'ruim' | 'neutro' {
  switch (estado) {
    case 'ok':
      return 'ok';
    case 'fora_da_faixa':
    case 'taxa_baixa':
      return 'aviso';
    case 'ausente':
    case 'parado':
      return 'ruim';
    default:
      return 'neutro';
  }
}

export const COR_DO_TOM: Record<ReturnType<typeof tomDoEstado>, string> = {
  ok: 'var(--emerald)',
  aviso: 'var(--amber)',
  ruim: 'var(--rose)',
  neutro: 'var(--text-3)',
};

/** M:SS,mmm. */
export function formatarTempo(segundos: number | null | undefined): string {
  if (typeof segundos !== 'number' || !Number.isFinite(segundos) || segundos < 0) return '—';
  const minutos = Math.floor(segundos / 60);
  const resto = segundos - minutos * 60;
  return `${minutos}:${resto.toFixed(3).padStart(6, '0').replace('.', ',')}`;
}

/** Número com vírgula decimal, sem passar de `casas` casas. */
export function formatarNumero(valor: number | null | undefined, casas = 2): string {
  if (typeof valor !== 'number' || !Number.isFinite(valor)) return '—';
  const absoluto = Math.abs(valor);
  const usadas = absoluto >= 1000 ? 0 : absoluto >= 100 ? Math.min(casas, 1) : casas;
  return valor.toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: usadas });
}

export function formatarPorcentagem(fracao: number | null | undefined, casas = 0): string {
  if (typeof fracao !== 'number' || !Number.isFinite(fracao)) return '—';
  return `${(fracao * 100).toLocaleString('pt-BR', { maximumFractionDigits: casas })}%`;
}

/** O último valor de um item, com a unidade quando ela é curta. */
export function formatarValor(valor: unknown, tipo: string, unidade?: string): string {
  if (valor === null || valor === undefined || valor === '') return '—';
  if (tipo === 'booleano' || typeof valor === 'boolean') return valor ? 'sim' : 'não';
  if (tipo === 'texto' || typeof valor === 'string') return String(valor);
  const texto = formatarNumero(Number(valor));
  const curta = unidade && unidade.length <= 6 ? ` ${unidade}` : '';
  return `${texto}${curta}`;
}

/** Os valores de cada componente (rodas, eixos) numa linha só. */
export function formatarComponentes(
  componentes: Array<{ rotulo: string; ultimo: unknown }>,
  tipo: string,
  unidade?: string,
): string {
  if (!componentes.length) return '—';
  if (componentes.length === 1 && !componentes[0].rotulo) return formatarValor(componentes[0].ultimo, tipo, unidade);
  const partes = componentes.map((c) => `${c.rotulo} ${formatarValor(c.ultimo, tipo)}`);
  const curta = unidade && unidade.length <= 6 ? ` ${unidade}` : '';
  return `${partes.join(' · ')}${curta}`;
}

/** Cor do espaço livre: amarelo abaixo de 5 GB, vermelho abaixo de 2 GB (o backend decide o nível). */
export function corDoDisco(nivel: string | null | undefined): string {
  if (nivel === 'vermelho') return 'var(--rose)';
  if (nivel === 'amarelo') return 'var(--amber)';
  if (nivel === 'ok') return 'var(--emerald)';
  return 'var(--text-3)';
}
