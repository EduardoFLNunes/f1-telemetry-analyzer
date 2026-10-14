import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { lerCor, razaoDeContraste, tabelaDeContraste, tokensDoCss } from './contraste';

const tokens = tokensDoCss(readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'tokens.css'), 'utf-8'));

describe('contraste do sistema visual', () => {
  it('a fórmula do WCAG dá 21:1 entre preto e branco', () => {
    expect(razaoDeContraste(lerCor('#000'), lerCor('#ffffff'))).toBeCloseTo(21, 5);
  });

  it('todo texto passa no AA (4,5:1) sobre o vidro, no pior caso do fundo', () => {
    const { linhas } = tabelaDeContraste(tokens);
    const reprovadas = linhas.filter((l) => !l.passaAA).map((l) => `${l.token} ${l.pior}`);
    expect(reprovadas).toEqual([]);
  });
});
