import { describe, expect, it } from 'vitest';
import {
  arredondarParaPar,
  curvasDoRelatorio,
  diferencaPorMicrossetor,
  distanciaComSinal,
  estadoDoFantasma,
  indiceDe,
  inicioDaFreada,
  janela,
  medidasDasCurvas,
  pedalEm,
  sNoTempo,
  tempoDoTrecho,
  tempoEm,
  type Curva,
  type Grade,
  type Linhas,
} from './medidas';

// Uma pista de 100 m com passo de 10 m: pontos em 0, 10, ..., 90; a linha em 100.
const g: Grade = { n: 10, comprimento: 100, passo: 10 };

function volta(segundosPorPonto: number, freioEm: number[] = [], lateral = 0): Linhas {
  const elapsed = Array.from({ length: 10 }, (_, i) => i * segundosPorPonto);
  return {
    elapsed,
    total: 10 * segundosPorPonto,
    velocidade: Array.from({ length: 10 }, (_, i) => 100 + i),
    acelerador: Array.from({ length: 10 }, () => 1),
    freio: Array.from({ length: 10 }, (_, i) => (freioEm.includes(i) ? 0.8 : 0)),
    lateral: Array.from({ length: 10 }, () => lateral),
  };
}

describe('medidas da tela Volta (método do relatório de evolução)', () => {
  it('índice, janela e distância com sinal como no ML', () => {
    expect(indiceDe(g, 29.9)).toBe(2);
    expect(indiceDe(g, 105)).toBe(0);
    expect(janela(g, 80, 20)).toEqual([8, 9, 0, 1, 2]);
    expect(distanciaComSinal(g, 10, 90)).toBe(20);
    expect(distanciaComSinal(g, 90, 10)).toBe(-20);
    expect(arredondarParaPar(2.5)).toBe(2);
    expect(arredondarParaPar(3.5)).toBe(4);
  });

  it('o relógio fecha na linha com o tempo da volta, e o trecho que cruza a linha soma as duas pontas', () => {
    const v = volta(1);
    expect(tempoEm(g, v, 95)).toBeCloseTo(9.5, 9);
    expect(tempoDoTrecho(g, v, [90, 20])).toBeCloseTo(3, 9);
    expect(sNoTempo(g, v, 4.5)).toBeCloseTo(45, 9);
    expect(sNoTempo(g, v, 99)).toBe(100);
  });

  it('a freada é a subida do freio entre o ápice anterior e o ápice', () => {
    expect(inicioDaFreada(g, volta(1, [3, 4]).freio, 10, 50)).toBe(30);
    expect(inicioDaFreada(g, volta(1).freio, 10, 50)).toBeNull();
  });

  it('as curvas somam a diferença da volta, e cada uma traz freada, ápice e mínima', () => {
    const curvas: Curva[] = [
      { codigo: 'C01', lado: 'esq.', trecho: [80, 40], curva: [20, 30], apice: 20 },
      { codigo: 'C02', lado: 'dir.', trecho: [40, 80], curva: [50, 70], apice: 60 },
    ];
    const lenta = volta(1.1, [5], 0.5);
    const rapida = volta(1, [4], 0);
    const m = medidasDasCurvas(g, lenta, rapida, curvas);
    expect(m[0].perdaS + m[1].perdaS).toBeCloseTo(lenta.total - rapida.total, 9);
    expect(m[1].freadaM).toBe(10); // a lenta freia 10 m depois
    expect(m[1].lateralApiceM).toBeCloseTo(0.5, 9);
    expect(m[0].minimaKmh).toBe(0);
  });

  it('as curvas do relatório voltam para a grade', () => {
    const passo = 2.000036717997977;
    const [c] = curvasDoRelatorio({ n: 2167, comprimento: 2167 * passo, passo }, [
      { curva: 'C01-esq', trecho_m: [4112.1, 346.0], curva_m: [224.0, 334.0], apice_m: 298.0 },
    ]);
    // 298,0 m arredondado é o ponto 149 (298,0055 m): o índice certo do ápice.
    expect(c.apice / passo).toBeCloseTo(149, 9);
    expect(c.codigo).toBe('C01');
    expect(c.lado).toBe('esq.');
  });

  it('microssetores: a diferença soma a diferença da volta', () => {
    const d = diferencaPorMicrossetor(g, volta(1.2), volta(1), [0, 50, 100]);
    expect(d[0]).toBeCloseTo(1, 9);
    expect(d[1]).toBeCloseTo(1, 9);
  });

  it('o fantasma por curva recomeça no início do trecho; na volta inteira acumula', () => {
    const curvas: Curva[] = [
      { codigo: 'C01', lado: 'esq.', trecho: [0, 50], curva: [10, 20], apice: 10 },
      { codigo: 'C02', lado: 'dir.', trecho: [50, 100], curva: [60, 70], apice: 60 },
    ];
    const lenta = volta(1.1);
    const rapida = volta(1);
    const porCurva = estadoDoFantasma(g, lenta, rapida, curvas, 70, 'curva');
    expect(porCurva.curva).toBe('C02');
    expect(porCurva.diferenca).toBeCloseTo(0.2, 9); // de 50 a 70 m: 2,2 s contra 2,0 s
    const inteira = estadoDoFantasma(g, lenta, rapida, curvas, 70, 'volta');
    expect(inteira.diferenca).toBeCloseTo(0.7, 9); // 7,7 s contra 7,0 s
    expect(inteira.sFantasma).toBeCloseTo(77, 9); // a referência em 7,7 s estava em 77 m
  });

  it('pedal: freio ≥ 0,15, acelerador ≥ 0,9, o resto é parcial', () => {
    const v = volta(1, [2]);
    expect(pedalEm(g, v, 20)).toBe('freio');
    expect(pedalEm(g, v, 50)).toBe('acelerador');
    expect(pedalEm(g, { ...v, acelerador: v.acelerador.map(() => 0.5) }, 50)).toBe('parcial');
  });
});
