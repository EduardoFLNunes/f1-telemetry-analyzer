import { describe, expect, it } from 'vitest';
import {
  APROXIMAR_S, ENQUADRAR_S, QuadroDeRotulos, cameraDaCurva, cameraDePerto, citadasNaVolta, curvaNoTempo, planoDoTempo, tempoNoReplay, trechoMarcado, diferencaAcumulada, distanciaNoTempo, dividirAArea, faixasDoPedal,
  forcaDaCelula, posicaoNoTempo, serieDaDiferenca, temVisuais, textoDaCelula, textoDaFreada, textoDaMinima, textoDaPerda, textoDaVoltaDeFora,
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

  it('na análise, a linha cobre o trecho da curva e termina na perda; sem o trecho, fica a janela do replay', () => {
    const trecho = { comprimentoM: 568, passoM: 2, entradaDoReplayM: 300, valores: [0, 0.4, 0.92] };
    expect(serieDaDiferenca({ ...comVisuais, diferencaNoTrecho: trecho })).toEqual({
      valores: [0, 0.4, 0.92], passoM: 2, totalM: 568, deslocamento: 300,
    });
    const janela = serieDaDiferenca(comVisuais);
    expect(janela.deslocamento).toBe(0);
    expect(janela.totalM).toBe(200);
    expect(janela.valores).toEqual(diferencaAcumulada(comVisuais));
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
    expect(textoDaVoltaDeFora({ volta: 12, tempoS: null, motivo: 'incompleta', citadas: ['C11', 'C12'] }))
      .toBe('volta 12: incompleta; citada: C11, C12');
  });
});

describe('o replay de perto (pedido 45, Parte D)', () => {
  const W = 300;
  const H = 300;
  const dentro = (p: [number, number]) => p[0] >= 0 && p[0] <= W && p[1] >= 0 && p[1] <= H;

  it('começa na curva inteira e depois aproxima', () => {
    const cheia = cameraDaCurva(curva, W, H);
    expect(cameraDePerto(curva, 0, 0, W, H).k).toBeCloseTo(cheia.k, 6);
    const perto = cameraDePerto(curva, 0, ENQUADRAR_S + APROXIMAR_S, W, H);
    expect(perto.k).toBeGreaterThan(cheia.k);
    // 80 m no lado menor da area util
    expect(perto.k).toBeCloseTo(Math.min(W - 36, H - 36 - 26) / 80, 6);
  });

  it('acompanha o meio dos dois carros, com a orientação fixa', () => {
    const a = cameraDePerto(curva, 1, 5, W, H);
    const b = cameraDePerto(curva, 3, 5, W, H);
    expect(a.ang).toBe(b.ang);
    const [vx, vz] = posicaoNoTempo(curva.linhas.voce, 3);
    const [rx, rz] = posicaoNoTempo(curva.linhas.referencia, 3);
    const v = b.tela(vx, vz);
    const r = b.tela(rx, rz);
    expect((v[0] + r[0]) / 2).toBeCloseTo(b.ax, 6);
    expect((v[1] + r[1]) / 2).toBeCloseTo(b.ay, 6);
  });

  it('os dois carros sempre na tela: se eles se afastam, a câmera se afasta, até a curva inteira', () => {
    const longe: CurvaDoReplay = { ...curva, duracaoS: 40,
      linhas: { voce: linha(-7.9, 5), referencia: linha(0, 50) } };
    const cheia = cameraDaCurva(longe, W, H);
    for (const t of [0, 1, 2, 3, 4, 10, 40]) {
      const cam = cameraDePerto(longe, t, 99, W, H);
      expect(cam.k).toBeGreaterThanOrEqual(cheia.k - 1e-9);
      const [vx, vz] = posicaoNoTempo(longe.linhas.voce, t);
      const [rx, rz] = posicaoNoTempo(longe.linhas.referencia, t);
      expect(dentro(cam.tela(vx, vz))).toBe(true);
      expect(dentro(cam.tela(rx, rz))).toBe(true);
    }
  });

  it('marca o trecho da causa e o passa em câmera lenta quando o tempo deixa', () => {
    const c: CurvaDoReplay = { ...curva, passoM: 2, causa: { trecho: 'freada', inicioM: 40, fimM: 80, perdaS: 0.5, medida: 'freada', valor: -15 } };
    expect(trechoMarcado(c)?.nome).toBe('trecho da causa');
    const p = planoDoTempo(c);
    expect(p.lento).toBe(true);
    expect(tempoNoReplay(p, 0.5)).toBe(0);                 // a curva inteira, parada
    expect(tempoNoReplay(p, ENQUADRAR_S + p.lentoDe)).toBeCloseTo(p.lentoDe, 6);
    expect(tempoNoReplay(p, ENQUADRAR_S + p.lentoDe + 0.2)).toBeCloseTo(p.lentoDe + 0.1, 6);   // metade da velocidade
    const fim = ENQUADRAR_S + p.lentoDe + 2 * (p.lentoAte - p.lentoDe);
    expect(tempoNoReplay(p, fim + 0.3)).toBeCloseTo(p.lentoAte + 0.3, 6);
  });

  it('na reta, sem tempo, não fica lento e começa mais perto do trecho', () => {
    const c: CurvaDoReplay = { ...curva, duracaoS: 12, passoM: 2,
      linhas: { voce: linha(-7.9, 200 / 12), referencia: linha(0, 18) },
      causa: { trecho: 'saida', inicioM: 160, fimM: 190, perdaS: 0.3, medida: 'saida', valor: -9 } };
    const p = planoDoTempo(c, 6);
    expect(p.lento).toBe(false);
    expect(p.t0).toBeGreaterThan(0);
    expect(p.t0).toBeLessThanOrEqual(p.lentoDe);
    expect(p.totalReal).toBeLessThanOrEqual(6 + 1e-6);
  });

  it('a volta inteira: a célula acesa é a da curva em que você está', () => {
    const c: CurvaDoReplay = { ...curva, curva: null, voltaInteira: true, passoM: 2, tempoDaVoltaS: 89.518,
      curvasNaVolta: [{ curva: 'C01', inicioM: 40, fimM: 80, tempoS: 1, perdaS: 0.2 }] };
    expect(curvaNoTempo(c, 0)).toBeNull();
    expect(curvaNoTempo(c, 60 / 45)).toBe('C01');
    expect(textoDoAlto(c)).toContain('volta 17 · 1:29,518');
  });
});
