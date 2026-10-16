import { describe, expect, it } from 'vitest';
import { carroDaConfirmacao, origemDaGravacao, podeAnotar, tempoDaReferencia } from './regrasDoCoachNoApp';

const comVoltas = (...origens: string[]) => ({ voltas: origens.map((origem) => ({ origem })) });

describe('origemDaGravacao', () => {
  it('todas humano pelo indicador: não precisa de anotação', () => {
    expect(origemDaGravacao(comVoltas('humano', 'humano'))).toBe('indicador');
  });
  it('sem indicador: voltas desconhecida', () => {
    expect(origemDaGravacao(comVoltas('desconhecida', 'desconhecida'))).toBe('sem_indicador');
  });
  it('qualquer volta da IA ou misturada: fica como está', () => {
    expect(origemDaGravacao(comVoltas('desconhecida', 'ia'))).toBe('com_ia');
    expect(origemDaGravacao(comVoltas('humano', 'misturada'))).toBe('com_ia');
  });
  it('sem conferência', () => {
    expect(origemDaGravacao(null)).toBe('sem_conferencia');
    expect(origemDaGravacao({ voltas: [] })).toBe('sem_conferencia');
  });
});

describe('podeAnotar', () => {
  it('só a gravação sem indicador e ainda não anotada', () => {
    expect(podeAnotar('sem_indicador', false)).toBe(true);
    expect(podeAnotar('sem_indicador', true)).toBe(false);
    expect(podeAnotar('indicador', false)).toBe(false);
    expect(podeAnotar('com_ia', false)).toBe(false);
    expect(podeAnotar('sem_conferencia', false)).toBe(false);
  });
});

describe('carroDaConfirmacao', () => {
  it('o carro gravado, ou o padrão com o aviso', () => {
    expect(carroDaConfirmacao('ks_ferrari')).toEqual({ carro: 'ks_ferrari', confirmar: false });
    expect(carroDaConfirmacao(null)).toEqual({ carro: 'rss_formula_rss_3_v6_2026', confirmar: true });
  });
});

describe('tempoDaReferencia', () => {
  it('M:SS,mmm', () => {
    expect(tempoDaReferencia(87.014)).toBe('1:27,014');
    expect(tempoDaReferencia(null)).toBe('—');
  });
});
