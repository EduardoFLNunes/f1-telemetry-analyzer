/** Nomes e números das telas Sessões, Volta e Evolução (pedido 30), como no protótipo A. */

/** `2026-10-05-2` → `05/10 (2)`. */
export function nomeDaSessao(id: string): string {
  const p = String(id).split('-');
  if (p.length < 3) return id;
  return `${p[2]}/${p[1]}${p[3] ? ` (${p[3]})` : ''}`;
}

/** `…#0008` → 8. */
export function numeroDaVolta(lapId: string): number {
  return parseInt(String(lapId).split('#')[1] || '0', 10);
}

/** Número com vírgula e `casas` casas fixas. */
export function nf(v: number, casas: number): string {
  return Number(v).toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas });
}

/** Com sinal: +0,214 / −0,098 / 0,000. */
export function sg(v: number, casas: number): string {
  return `${v > 0 ? '+' : v < 0 ? '−' : ''}${nf(Math.abs(v), casas)}`;
}

/** M:SS,mmm. */
export function tempo(t: number): string {
  if (!Number.isFinite(t)) return '—';
  const m = Math.floor(t / 60);
  const s = t - 60 * m;
  return `${m}:${s < 10 ? '0' : ''}${nf(s, 3)}`;
}

export function textoDaFreada(freadaM: number | null, refFreia: boolean, longo: boolean, rotuloRef: 'ia' | 'melhor'): string {
  if (freadaM === null) {
    if (refFreia) return longo ? 'sem freada medida nesta volta' : 'não medida';
    return longo ? (rotuloRef === 'ia' ? 'a IA não freia aqui' : 'a referência não freia aqui') : 'ref. não freia';
  }
  const m = Math.round(freadaM);
  if (m === 0) return longo ? 'no mesmo ponto' : 'mesmo ponto';
  return `${Math.abs(m)} m ${m < 0 ? 'antes' : 'depois'}${longo ? (rotuloRef === 'ia' ? ' da IA' : ' da referência') : ''}`;
}

export function textoDaMinima(v: number, longo: boolean): string {
  if (!longo) return `${sg(v, 1)} km/h`;
  if (Math.abs(v) < 0.05) return 'igual';
  return `${nf(Math.abs(v), 1)} km/h ${v < 0 ? 'mais lenta' : 'mais rápida'}`;
}

export function textoDaLateral(v: number): string {
  if (Math.abs(v) < 0.005) return 'na mesma linha';
  return `${nf(Math.abs(v), 2)} m à ${v > 0 ? 'esquerda' : 'direita'}`;
}
