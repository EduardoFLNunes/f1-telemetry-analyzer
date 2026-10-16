/**
 * O botão do coach e a anotação na tela Sessões (pedido 32, Parte B): as regras
 * que não dependem da tela, para testar sem o React.
 */

export type OrigemDaGravacao = 'indicador' | 'sem_indicador' | 'com_ia' | 'sem_conferencia';

/** A mesma regra do backend (`core/coleta/anotacao.classificar`), pelas voltas da conferência. */
export function origemDaGravacao(resultado: any): OrigemDaGravacao {
  const voltas: any[] = Array.isArray(resultado?.voltas) ? resultado.voltas : [];
  if (!voltas.length) return 'sem_conferencia';
  const origens = new Set(voltas.map((v) => String(v?.origem || 'desconhecida')));
  if (origens.has('ia') || origens.has('misturada')) return 'com_ia';
  if (origens.size === 1 && origens.has('humano')) return 'indicador';
  return 'sem_indicador';
}

export const ROTULO_DA_ORIGEM: Record<OrigemDaGravacao, string> = {
  indicador: 'indicador de IA gravado',
  sem_indicador: 'sem indicador',
  com_ia: 'voltas da IA ou misturada',
  sem_conferencia: 'não conferida',
};

/** O botão "Todas as voltas foram minhas" só aparece na gravação sem indicador, conferida e ainda não anotada. */
export function podeAnotar(origem: OrigemDaGravacao, anotada: boolean): boolean {
  return origem === 'sem_indicador' && !anotada;
}

export const CARRO_PADRAO = 'rss_formula_rss_3_v6_2026';

/** O carro da confirmação: o gravado ou, sem ele, o padrão com o aviso "confirme o carro". */
export function carroDaConfirmacao(carroGravado: string | null | undefined): { carro: string; confirmar: boolean } {
  return carroGravado ? { carro: carroGravado, confirmar: false } : { carro: CARRO_PADRAO, confirmar: true };
}

export type EstadoDoPasso = 'pendente' | 'rodando' | 'feito' | 'parado';

export const ROTULO_DO_PASSO: Record<EstadoDoPasso, string> = {
  pendente: 'a fazer',
  rodando: 'rodando',
  feito: 'feito',
  parado: 'parou aqui',
};

/** Tempo da referência (segundos) como M:SS,mmm. */
export function tempoDaReferencia(segundos: unknown): string {
  if (segundos === null || segundos === undefined || segundos === '') return '—';
  const t = Number(segundos);
  if (!Number.isFinite(t)) return '—';
  const m = Math.floor(t / 60);
  const s = t - 60 * m;
  return `${m}:${s < 10 ? '0' : ''}${s.toFixed(3).replace('.', ',')}`;
}
