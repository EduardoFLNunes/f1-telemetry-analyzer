import { describe, expect, it } from 'vitest';
import { voltaDoAoVivo, type VoltaDoBackend } from './voltaAoVivo';

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
