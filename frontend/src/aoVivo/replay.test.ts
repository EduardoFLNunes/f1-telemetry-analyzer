import { describe, expect, it } from 'vitest';
import {
  QuadroDeRotulos, cameraDaCurva, citadasNaVolta, diferencaAcumulada, distanciaNoTempo, dividirAArea, faixasDoPedal,
  forcaDaCelula, posicaoNoTempo, temVisuais, textoDaCelula, textoDaFreada, textoDaMinima, textoDaPerda, textoDaVoltaDeFora,
  textoDoAlto, textoDoTracado, type CurvaDoReplay, type GradeDaSessao, type PontoDoReplay,
} from './replay';

// Uma curva de mentira: as duas linhas indo de z = 0 a z = 200 (para cima no mapa do app), a IA mais rápida.
function linha(lateral: number, velocidade: number): PontoDoReplay[] {
  return Array.from({ length: 101 }, (_, i) => [lateral, i * 2, (i * 2) / velocidade, i < 30 ? 2 : 1] as PontoDoReplay);
}
const curva: CurvaDoReplay = {
  curva: 'C01', lado: 'esquerda', volta: 17, referencia: 'volta_ia', rotuloDaReferencia: 'IA (referência)',
  perdaS: 0.92, duracaoS: 200 / 45,
  linhas: { voce: linha(-7.9, 45), referencia: linha(0, 50) },
  freadas: { voce: { x: -7.9, z: 10 }, referencia: { x: 0, z: 52 }, distanciaM: -42 },
  minimas: { voce: { x: -7.9, z: 120, kmh: 102.4 }, referencia: { x: 0, z: 110, kmh: 128 } },
  tracado: { voce: [-7.9, 110], referencia: [0, 110], distanciaM: 7.94, lado: 'direita' },
};

describe('o replay da curva (pedido 36, Parte E)', () => {
  it('põe cada carro no seu próprio tempo, desde a mesma entrada', () => {
    expect(posicaoNoTempo(curva.linhas.referencia, 0)).toEqual([0, 0]);
    expect(posicaoNoTempo(curva.linhas.referencia, 1)).toEqual([0, 50]);       // 50 m/s
    expect(posicaoNoTempo(curva.linhas.voce, 1)).toEqual([-7.9, 45]);          // 45 m/s: a IA abre 5 m
    expect(posicaoNoTempo(curva.linhas.voce, 99)).toEqual([-7.9, 200]);        // depois do fim, no fim
  });

  it('encaixa as duas linhas na tela, com a entrada para cima', () => {
    const W = 360;
    const H = 250;
    const cam = cameraDaCurva(curva, W, H);
    for (const p of [...curva.linhas.voce, ...curva.linhas.referencia]) {
      const [x, y] = cam.tela(p[0], p[1]);
      expect(x).toBeGreaterThanOrEqual(18 - 1e-6);
      expect(x).toBeLessThanOrEqual(W - 18 + 1e-6);
      expect(y).toBeGreaterThanOrEqual(26 + 18 - 1e-6);
      expect(y).toBeLessThanOrEqual(H - 18 + 1e-6);
    }
    const [, yEntrada] = cam.tela(0, 0);
    const [, ySaida] = cam.tela(0, 200);
    expect(ySaida).toBeLessThan(yEntrada);                                       // anda para cima
  });

  it('desenha os 7,9 m do traçado como a distância entre as duas linhas', () => {
    const cam = cameraDaCurva(curva, 360, 250);
    const [ax, ay] = cam.tela(...curva.tracado!.voce);
    const [bx, by] = cam.tela(...curva.tracado!.referencia);
    expect(Math.hypot(ax - bx, ay - by) / cam.k).toBeCloseTo(7.9, 6);
  });

  it('escreve os números com a unidade', () => {
    expect(textoDaPerda(0.92)).toBe('perde 0,92 s nesta curva');
    expect(textoDaPerda(-0.1)).toBe('ganha 0,10 s nesta curva');
    expect(textoDaFreada(-42)).toBe('você freia 42 m antes da IA');
    expect(textoDaFreada(16, 'da sua melhor')).toBe('você freia 16 m depois da sua melhor');
    expect(textoDaFreada(null)).toBeNull();
    expect(textoDoTracado(curva.tracado!)).toBe('você passa 7,9 m mais à direita');
    expect(textoDaMinima(102.4)).toBe('102 km/h');
  });
});

describe('os rótulos do replay', () => {
  it('não cobrem um ao outro nem saem da área', () => {
    const q = new QuadroDeRotulos([0, 26, 360, 250]);
    q.ocupar(200, 100, 9);
    const caixas = [
      q.colocar(200, 100, 120, 15, 'direita'),
      q.colocar(205, 102, 120, 15, 'direita'),
      q.colocar(350, 240, 140, 15, 'direita'),   // perto do canto: entra para dentro
    ].map(([x, y], i) => [x, y, x + [120, 120, 140][i], y + 15]);
    for (const [x0, y0, x1, y1] of caixas) {
      expect(x0).toBeGreaterThanOrEqual(0);
      expect(x1).toBeLessThanOrEqual(360);
      expect(y0).toBeGreaterThanOrEqual(26);
      expect(y1).toBeLessThanOrEqual(250);
    }
    for (let i = 0; i < caixas.length; i++) {
      for (let j = i + 1; j < caixas.length; j++) {
        const [a, b] = [caixas[i], caixas[j]];
        expect(a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3]).toBe(false);
      }
    }
  });
});

describe('os visuais e os números da voz (pedido 43)', () => {
  const comVisuais: CurvaDoReplay = {
    ...curva,
    passoM: 2,
    velocidades: { voce: curva.linhas.voce.map(() => 162), referencia: curva.linhas.referencia.map(() => 180) },
    secoes: { freadaM: 10, minimaM: 110, saidaM: 180 },
  };

  it('escreve no alto o tempo da voz na frase do coach, e a perda da curva na análise', () => {
    expect(textoDoAlto(curva)).toBe('C01, esquerda · volta 17 · perde 0,92 s nesta curva');
    const frase = { ...curva, voz: { microssetor: 44, inicioM: 90, fimM: 162.3, perdaS: 0.64 } };
    expect(textoDoAlto(frase)).toBe('C01, esquerda · volta 17 · perde 0,64 s no trecho da fala');
  });

  it('a freada da voz não é arredondada de novo (16,0 m continua 16)', () => {
    expect(textoDaFreada(-16)).toBe('você freia 16 m antes da IA');
  });

  it('só desenha os visuais quando a rota traz os dados (o backend do 0.5.0 não traz)', () => {
    expect(temVisuais(curva)).toBe(false);
    expect(temVisuais(comVisuais)).toBe(true);
  });

  it('o cursor anda com cada carro, em metros desde a entrada', () => {
    expect(distanciaNoTempo(curva.linhas.referencia, 1, 2)).toBeCloseTo(50, 6);   // 50 m/s
    expect(distanciaNoTempo(curva.linhas.voce, 1, 2)).toBeCloseTo(45, 6);
    expect(distanciaNoTempo(curva.linhas.voce, 99, 2)).toBe(200);
  });

  it('a diferença acumulada começa em zero e sobe quando você perde', () => {
    const d = diferencaAcumulada(curva);
    expect(d[0]).toBe(0);
    expect(d[d.length - 1]).toBeCloseTo(200 / 45 - 200 / 50, 6);
    expect(d.every((v, i) => i === 0 || v >= d[i - 1])).toBe(true);
  });

  it('as faixas do pedal juntam os pontos seguidos com o mesmo pedal', () => {
    expect(faixasDoPedal(curva.linhas.voce, 2)).toEqual([[0, 59, 2], [59, 200, 1]]);
  });

  it('quando a janela é pequena, sai primeiro a velocidade, depois a diferença e por último o pedal', () => {
    const tudo = dividirAArea(0, 0, 420, 150 + 30 + 60 + 74, true);
    expect([tudo.pedal, tudo.diferenca, tudo.velocidade].every(Boolean)).toBe(true);
    expect(tudo.replay.h).toBe(150);
    const trezentos = dividirAArea(0, 0, 300, 300, true);   // 300 x 300: a velocidade sai
    expect([Boolean(trezentos.pedal), Boolean(trezentos.diferenca), trezentos.velocidade]).toEqual([true, true, null]);
    expect(trezentos.replay.h).toBe(210);
    const pequena = dividirAArea(0, 0, 260, 200, true);
    expect(pequena.pedal).not.toBeNull();
    expect(pequena.diferenca).toBeNull();
    expect(pequena.velocidade).toBeNull();
    expect(dividirAArea(0, 0, 260, 170, true).pedal).toBeNull();
    expect(dividirAArea(0, 0, 420, 300, false).replay.h).toBe(300);
  });

  it('a grade: a célula com a unidade, a cor pela perda e as curvas citadas na volta', () => {
    expect(textoDaCelula(0.805)).toBe('0,81 s');
    expect(textoDaCelula(-0.362)).toBe('−0,36 s');
    expect(forcaDaCelula(0)).toBeCloseTo(0.15);
    expect(forcaDaCelula(2.5)).toBeCloseTo(0.9);
    const grade: GradeDaSessao = {
      sessao: 's', curvas: ['C01', 'C12'], voltas: [{ volta: 13, tempoS: 88.329, perdas: [0.805, 0.201] }],
      fora: [{ volta: 5, tempoS: 115.447, motivo: 'rodada ou saída de pista: perdeu 26,5 s na C12' }],
      citadas: [{ volta: 13, curva: 'C01', origem: 'analise', id: 18 }, { volta: 13, curva: 'C01', origem: 'coach', id: 17 }],
    };
    expect(citadasNaVolta(grade, 13).get('C01')).toEqual(['analise', 'coach']);
    expect(citadasNaVolta(grade, 12).size).toBe(0);
    expect(textoDaVoltaDeFora(grade.fora[0])).toBe('volta 5: rodada ou saída de pista: perdeu 26,5 s na C12 (1:55,447)');
  });
});
