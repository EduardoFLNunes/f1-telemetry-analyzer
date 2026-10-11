/**
 * A aba "Coleta de dados" mostra tempos em M:SS,mmm, números com vírgula e
 * uma cor por estado de canal (pedido 28).
 */
import { describe, expect, it } from 'vitest';

import {
  corDoDisco,
  formatarComponentes,
  formatarNumero,
  formatarPorcentagem,
  formatarTempo,
  formatarValor,
  tomDoEstado,
} from './coleta';

describe('formatarTempo', () => {
  it('usa M:SS,mmm', () => {
    expect(formatarTempo(84.828)).toBe('1:24,828');
    expect(formatarTempo(91.7425)).toBe('1:31,743');
    expect(formatarTempo(5)).toBe('0:05,000');
  });

  it('não inventa tempo', () => {
    expect(formatarTempo(null)).toBe('—');
    expect(formatarTempo(Number.NaN)).toBe('—');
    expect(formatarTempo(-1)).toBe('—');
  });
});

describe('números', () => {
  it('usa vírgula decimal', () => {
    expect(formatarNumero(0.1462, 3)).toBe('0,146');
    expect(formatarNumero(5605.46)).toBe('5.605');
    expect(formatarPorcentagem(0.953)).toBe('95%');
  });

  it('mostra sim e não para o indicador de IA', () => {
    expect(formatarValor(false, 'booleano')).toBe('não');
    expect(formatarValor(true, 'booleano')).toBe('sim');
    expect(formatarValor(null, 'numero', 'rad/s')).toBe('—');
  });

  it('junta as quatro rodas numa linha', () => {
    const rodas = [
      { rotulo: 'DE', ultimo: 300.5 },
      { rotulo: 'DD', ultimo: 301 },
      { rotulo: 'TE', ultimo: null },
      { rotulo: 'TD', ultimo: 280 },
    ];
    expect(formatarComponentes(rodas, 'numero', '°C')).toBe('DE 300,5 · DD 301 · TE — · TD 280 °C');
  });
});

describe('estados', () => {
  it('dá uma cor a cada estado', () => {
    expect(tomDoEstado('ok')).toBe('ok');
    expect(tomDoEstado('ausente')).toBe('ruim');
    expect(tomDoEstado('parado')).toBe('ruim');
    expect(tomDoEstado('fora_da_faixa')).toBe('aviso');
    expect(tomDoEstado('taxa_baixa')).toBe('aviso');
    expect(tomDoEstado('sem_dados')).toBe('neutro');
  });

  it('pinta o disco pelo nível do backend', () => {
    expect(corDoDisco('vermelho')).toBe('var(--rose)');
    expect(corDoDisco('amarelo')).toBe('var(--amber)');
    expect(corDoDisco('ok')).toBe('var(--emerald)');
  });
});
