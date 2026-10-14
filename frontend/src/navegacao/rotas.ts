/**
 * As telas do app e o endereço de cada uma (pedido 29).
 *
 * O endereço fica no hash (`#/volta`), e não num roteador com histórico do
 * navegador: o app abre por `file://` no Electron, onde só o hash sobrevive ao
 * recarregar. Recarregar a página volta para a mesma tela, o que antes não
 * acontecia (inventário, seção 1.1).
 */

export type Tela = 'sessoes' | 'ao-vivo' | 'volta' | 'evolucao' | 'coleta' | 'sistema';

export type Rota = {
  tela: Tela;
  /** Subpágina, quando a tela tem (Sistema › Guia visual). */
  sub: string | null;
};

export const TELAS: ReadonlyArray<{ id: Tela; rotulo: string; descricao: string }> = [
  { id: 'sessoes', rotulo: 'Sessões', descricao: 'Início: o hero e as sessões gravadas' },
  { id: 'ao-vivo', rotulo: 'Ao vivo', descricao: 'A sessão em andamento e o rádio do engenheiro' },
  { id: 'volta', rotulo: 'Volta', descricao: 'Uma volta contra a referência' },
  { id: 'evolucao', rotulo: 'Evolução', descricao: 'Voltas gravadas e a evolução entre sessões' },
  { id: 'coleta', rotulo: 'Coleta de dados', descricao: 'A gravação tem o que os modelos precisam?' },
  { id: 'sistema', rotulo: 'Sistema', descricao: 'Desenvolvimento, depuração e o guia visual' },
];

const IDS = new Set<string>(TELAS.map((tela) => tela.id));

export const ROTA_INICIAL: Rota = { tela: 'sessoes', sub: null };

/** `#/sistema/guia` → `{ tela: 'sistema', sub: 'guia' }`. Endereço desconhecido → Sessões. */
export function rotaDoHash(hash: string | null | undefined): Rota {
  const limpo = String(hash || '').replace(/^#\/?/, '').replace(/\/+$/, '');
  if (!limpo) return ROTA_INICIAL;
  const [tela, sub] = limpo.split('/');
  if (!IDS.has(tela)) return ROTA_INICIAL;
  return { tela: tela as Tela, sub: sub ? decodeURIComponent(sub) : null };
}

export function hashDaRota(tela: Tela, sub?: string | null): string {
  return sub ? `#/${tela}/${encodeURIComponent(sub)}` : `#/${tela}`;
}
