import { describe, expect, it } from 'vitest';
import { decimal, diferencaComSinal, mensagemDoEvento } from './radio';

// Um evento como o `_emit_reference_event` do coach publica (driving_coach.py).
const eventoReferencia = {
  type: 'coaching_event',
  event: 'Setor 12: 0.31s atras da volta da IA neste trecho (3.12s contra 2.81s). A IA freia 12 m depois de voce.',
  severity: 0.62,
  evidence: {
    microsector: 12,
    yourSeconds: 3.12,
    referenceSeconds: 2.81,
    lossSeconds: 0.31,
    referenceKind: 'volta_ia',
    referenceLabel: 'volta da IA',
    referenceBrakeOnsetM: 812.4,
    yourBrakeOnsetM: 800.1,
    brakeDeltaM: 12.3,
    referenceMinSpeedKmh: 104.2,
    yourMinSpeedKmh: 96.4,
  },
  lap_number: 7,
  timestamp: 1_792_000_000,
};

describe('mensagens de rádio', () => {
  it('monta a frase em português com os números do evento, sem mudar os números', () => {
    const m = mensagemDoEvento(eventoReferencia);
    expect(m.tipo).toBe('diferenca');
    expect(m.frase).toBe('+0,31 s para a volta da IA neste trecho');
    expect(m.onde).toBe('volta 7 · microssetor 13');
    expect(m.detalhe).toBe('3,12 s contra 2,81 s · a IA freia 12 m depois de você · mínima da IA 104 km/h, a sua 96 km/h');
    expect(m.perdaS).toBeCloseTo(0.31);
  });

  it('diz a freada contra a sua melhor volta como o coach diz', () => {
    const m = mensagemDoEvento({
      ...eventoReferencia,
      evidence: { ...eventoReferencia.evidence, referenceKind: 'minha_melhor', referenceLabel: 'sua melhor volta', brakeDeltaM: -9 },
    });
    expect(m.frase).toBe('+0,31 s para a sua melhor volta neste trecho');
    expect(m.detalhe).toContain('na sua melhor volta você freou 9 m antes');
  });

  it('o foco lista os microssetores por extenso', () => {
    const m = mensagemDoEvento({
      type: 'coaching_focus',
      event: 'Foco nas proximas voltas: setores 3, 12 e 41',
      focusSectors: [3, 12, 41],
      focusSource: 'modelo',
      lap_number: 6,
      timestamp: 1_792_000_000,
    });
    expect(m.tipo).toBe('foco');
    expect(m.tag).toBe('Foco');
    expect(m.frase).toBe('Foco nas próximas voltas: microssetores 4, 13 e 42');
    expect(m.detalhe).toBe('maior diferença mediana para a referência nas suas voltas do modelo');
  });

  it('sem os números, mostra a frase do backend como veio', () => {
    const m = mensagemDoEvento({ type: 'coaching_event', event: 'Volta fechada.', lap_number: 3 });
    expect(m.tipo).toBe('outro');
    expect(m.frase).toBe('Volta fechada.');
    expect(m.detalhe).toBeNull();
  });

  it('formata com vírgula e sempre com o sinal', () => {
    expect(decimal(4.561, 3)).toBe('4,561');
    expect(diferencaComSinal(0.214, 3)).toBe('+0,214 s');
    expect(diferencaComSinal(-0.12)).toBe('−0,12 s');
    expect(diferencaComSinal(0)).toBe('0,00 s');
  });
});
