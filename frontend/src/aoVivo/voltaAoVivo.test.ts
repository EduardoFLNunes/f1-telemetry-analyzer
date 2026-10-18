import { describe, expect, it } from 'vitest';
import { AcumuladorAoVivo, voltaDoAoVivo, type VoltaDoBackend } from './voltaAoVivo';

function backend(parcial: Partial<VoltaDoBackend> = {}): VoltaDoBackend {
  const n = 10;
  const vazio = () => new Array<number | null>(n).fill(null);
  const linhas = { elapsed: vazio(), velocidade: vazio(), acelerador: vazio(), freio: vazio(), lateral: vazio() };
  // Medido nos pontos 1, 2 e 5 (o 3 e o 4 caíram entre dois quadros).
  [[1, 0.1], [2, 0.2], [5, 0.5]].forEach(([i, t]) => {
    linhas.elapsed[i] = t;
    linhas.velocidade[i] = 72; // 20 m/s
    linhas.acelerador[i] = 1;
    linhas.freio[i] = 0;
    linhas.lateral[i] = i;
  });
  return { disponivel: true, volta: 7, desdeALinha: true, comprimentoM: 20, pontosDaGrade: n, passoM: 2, indice: 5, s: 10.4, linhas, ...parcial };
}

describe('voltaDoAoVivo', () => {
  it('preenche os buracos até o ponto atual e segue o relógio depois dele', () => {
    const v = voltaDoAoVivo(backend(), 'g1')!;
    expect(v.lapId).toBe('ao-vivo#0007');
    expect(v.linhas.elapsed[0]).toBe(0);
    expect(v.linhas.elapsed[3]).toBeCloseTo(0.3);
    expect(v.linhas.elapsed[4]).toBeCloseTo(0.4);
    expect(v.linhas.elapsed[6]).toBeCloseTo(0.6); // 2 m a 20 m/s
    expect(v.linhas.total).toBeCloseTo(1.0);
    expect(v.linhas.lateral[3]).toBeCloseTo(3);
    expect(v.linhas.acelerador[4]).toBe(1);
    expect(Number.isNaN(v.linhas.freio[7])).toBe(true);
    expect(v.tempoS).toBeCloseTo(0.5);
  });

  it('sem passar pela linha ainda, não há relógio para o fantasma', () => {
    expect(voltaDoAoVivo(backend({ desdeALinha: false }), 'g1')).toBeNull();
    expect(voltaDoAoVivo({ ...backend(), disponivel: false }, 'g1')).toBeNull();
    expect(voltaDoAoVivo(null, 'g1')).toBeNull();
  });
});

describe('AcumuladorAoVivo (pedido 35: só os pontos novos)', () => {
  const cabecalho = { disponivel: true, volta: 7, desdeALinha: true, comprimentoM: 20, pontosDaGrade: 10, passoM: 2 };
  const vazias = () => ({ elapsed: new Array(10).fill(null), velocidade: new Array(10).fill(null), acelerador: new Array(10).fill(null),
    freio: new Array(10).fill(null), lateral: new Array(10).fill(null) });

  it('recebe a volta inteira, depois só os pontos novos, e a volta nova inteira de novo', () => {
    const acc = new AcumuladorAoVivo();
    const linhas = vazias();
    linhas.elapsed[1] = 0.1; linhas.velocidade[1] = 72; linhas.lateral[1] = 1;
    expect(acc.aplicar({ ...cabecalho, versao: 3, seq: 10, completa: true, indice: 1, s: 2.5, linhas } as any)).toBe(true);
    expect(acc.aplicar({ ...cabecalho, versao: 3, seq: 12, completa: false, indice: 3, s: 6.5,
      carro: { s: 6.5, indice: 3, velocidadeKmh: 72, tempoDaVolta: 0.3, seq: 12 },
      pontos: { indices: [2, 3], elapsed: [0.2, 0.3], velocidade: [72, 72], acelerador: [1, 1], freio: [0, 0], lateral: [2, 3] } } as any)).toBe(true);
    const v = acc.volta('g1')!;
    expect(v.linhas.elapsed[3]).toBeCloseTo(0.3);
    expect(v.linhas.lateral[2]).toBeCloseTo(2);
    // Depois do ponto atual, a lateral e a velocidade ficam as do último ponto (o carro anda no traçado).
    expect(v.linhas.lateral[8]).toBeCloseTo(3);
    expect(v.linhas.velocidade[8]).toBeCloseTo(72);
    expect(acc.carro?.s).toBe(6.5);
    // Pontos de outra volta sem a volta inteira: ignorados até a volta inteira chegar.
    expect(acc.aplicar({ ...cabecalho, versao: 4, seq: 13, completa: false, indice: 0, s: 0.5,
      pontos: { indices: [0], elapsed: [0.01], velocidade: [72], acelerador: [1], freio: [0], lateral: [0] } } as any)).toBe(false);
    expect(acc.versao).toBe(3);
    // Sem dados: o acumulador esvazia.
    expect(acc.aplicar({ disponivel: false } as any)).toBe(true);
    expect(acc.volta('g1')).toBeNull();
  });
});
