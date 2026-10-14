import { describe, expect, it } from 'vitest';
import { dataDoNomeDaSessao, partesDoLapId, resumoDaConferencia, trechoDaVolta, voltaPeloTempo } from './dadosDoHero';

describe('números do hero', () => {
  it('voltas válidas e a melhor vêm só das voltas que entram no store', () => {
    const resultado = {
      veredito: { voltasValidas: 2 },
      voltas: [
        { entraNoStore: true, tempoS: 90.313 },
        { entraNoStore: false, tempoS: 87.1 }, // não passou nos portões: não vira a melhor
        { entraNoStore: true, tempoS: 89.768 },
      ],
    };
    expect(resumoDaConferencia(resultado)).toEqual({ voltasValidas: 2, melhorS: 89.768 });
    expect(resumoDaConferencia({ voltas: [] })).toEqual({ voltasValidas: 0, melhorS: null });
    expect(resumoDaConferencia(null)).toBeNull();
  });

  it('a volta de referência é achada pelo tempo, e só se for única', () => {
    const voltas = [
      { lapNumber: 4, duration: 188.574 },
      { lapNumber: 5, duration: 89.388 },
      { lapNumber: 8, duration: 86.1 },
    ];
    expect(voltaPeloTempo(voltas, 89.389)?.lapNumber).toBe(5);
    expect(voltaPeloTempo(voltas, 84.828)).toBeNull();
    expect(voltaPeloTempo([...voltas, { lapNumber: 9, duration: 89.39 }], 89.389)).toBeNull();
  });

  it('traça só a passagem que fecha no tempo da referência', () => {
    // 04/10, "volta 5" do gravador: uma passagem de 85,107 s e, depois que a sessão recomeçou, a de 89,388 s.
    const amostras = [
      { lap_time: 0.012, id: 'a' }, { lap_time: 40.9, id: 'b' }, { lap_time: 85.107, id: 'c' },
      { lap_time: 0.042, id: 'd' }, { lap_time: 46.5, id: 'e' }, { lap_time: 89.388, id: 'f' },
    ];
    expect(trechoDaVolta(amostras, 89.389)?.map((a) => a.id)).toEqual(['d', 'e', 'f']);
    expect(trechoDaVolta(amostras, 85.1)?.map((a) => a.id)).toEqual(['a', 'b', 'c']);
    expect(trechoDaVolta(amostras, 90.5)).toBeNull();
  });

  it('lê a sessão e a data do id da volta do store v2', () => {
    expect(partesDoLapId('2026-10-04_02-24-04_vhe_interlagos#0018')).toEqual({ sessao: '2026-10-04_02-24-04_vhe_interlagos', sequencia: 18 });
    expect(partesDoLapId('sem-cerquilha')).toBeNull();
    expect(dataDoNomeDaSessao('2026-10-04_02-24-04_vhe_interlagos')).toBe('04/10');
  });
});
