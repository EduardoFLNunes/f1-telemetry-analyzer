/**
 * Tabela de contraste do sistema visual (pedido 29), a partir de src/theme/tokens.css.
 *
 *   node scripts/contraste.ts [saida.json]
 *
 * Imprime a tabela em Markdown e, com `saida.json`, grava os números. Roda no
 * Node 24 direto (tipos removidos pelo próprio Node), sem pacote novo.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { tabelaDeContraste, tokensDoCss } from '../src/theme/contraste.ts';

const aqui = dirname(fileURLToPath(import.meta.url));
const tokens = tokensDoCss(readFileSync(join(aqui, '..', 'src', 'theme', 'tokens.css'), 'utf-8'));
const { superficies, linhas } = tabelaDeContraste(tokens);

const fmt = (n: number) => n.toFixed(2).replace('.', ',');
const ids = superficies.map((s) => s.id);
const saida: string[] = [];
saida.push('Superfícies (cor composta no pior caso):');
for (const s of superficies) saida.push(`- \`${s.id}\` ${s.cor}: ${s.nome}`);
saida.push('');
saida.push(`| texto | cor | uso | ${ids.join(' | ')} | pior | AA |`);
saida.push(`|---|---|---|${ids.map(() => '---:').join('|')}|---:|---|`);
for (const l of linhas) {
  const celulas = ids.map((id) => (l.razoes[id] !== undefined ? fmt(l.razoes[id]) : '—'));
  if (l.razoes.vermelho !== undefined) celulas[0] = `${fmt(l.razoes.vermelho)} (sobre o vermelho)`;
  saida.push(`| \`${l.token}\` | ${l.cor} | ${l.uso} | ${celulas.join(' | ')} | ${fmt(l.pior)} | ${l.passaAA ? 'passa' : '**não passa**'} |`);
}
console.log(saida.join('\n'));

const destino = process.argv[2];
if (destino) {
  writeFileSync(destino, JSON.stringify({ formato: 'contraste/1', fonte: 'frontend/src/theme/tokens.css', superficies, linhas }, null, 2) + '\n', 'utf-8');
  console.log(`\ngravado em ${destino}`);
}
