/**
 * What the coaching feed says about a microsector.
 *
 * These events used to fall through to `JSON.stringify(evidence).slice(0, 60)`,
 * which put a truncated object in front of the driver. They now get their own
 * line, and it has to survive the second target being absent -- which is the
 * normal case on every track the optimised line has not been generated for.
 */
import { describe, expect, it } from 'vitest';

import { microsectorEvidence, renderEvidence } from './CoachingFeed';

const microsectorEvent = (extra: Record<string, unknown> = {}) => ({
  event: 'Setor 20: 0.45s atras do seu melhor (2.41s contra 1.96s).',
  severity: 0.9,
  evidence: {
    microsector: 20,
    yourSeconds: 2.41,
    bestSeconds: 1.96,
    lossSeconds: 0.45,
    ...extra,
  },
});

describe('microsectorEvidence', () => {
  it('recognises the coach events by their microsector index', () => {
    expect(microsectorEvidence(microsectorEvent())).not.toBeNull();
  });

  it('ignores the physics events, which carry no microsector', () => {
    expect(microsectorEvidence({ event: 'late_brake', evidence: { delta_m: 4.2 } })).toBeNull();
  });

  it('ignores a string evidence payload', () => {
    expect(microsectorEvidence({ event: 'x', evidence: 'texto solto' })).toBeNull();
  });

  it('does not mistake microsector zero for a missing one', () => {
    expect(microsectorEvidence(microsectorEvent({ microsector: 0 }))).not.toBeNull();
  });
});

describe('renderEvidence', () => {
  it('shows both targets when the track has an optimised line', () => {
    const line = renderEvidence(microsectorEvent({ optimalSeconds: 1.78 }));
    expect(line).toContain('VOCE 2.41s');
    expect(line).toContain('MELHOR 1.96s');
    expect(line).toContain('OTIMO 1.78s');
  });

  it('shows only the driver target when there is no line', () => {
    const line = renderEvidence(microsectorEvent());
    expect(line).toContain('VOCE 2.41s');
    expect(line).toContain('MELHOR 1.96s');
    expect(line).not.toContain('OTIMO');
  });

  it('never falls back to a raw JSON dump for a coach event', () => {
    expect(renderEvidence(microsectorEvent())).not.toContain('{');
  });

  it('leaves the physics events formatted as they were', () => {
    const line = renderEvidence({ event: 'late_brake', evidence: { delta_m: 4.2, ref_s: 1200 } });
    expect(line).toContain('BRAKE_DELTA: 4.2m');
    expect(line).toContain('REF_S: 1200m');
  });

  it('labels the reference lap, not a best, in the default mode', () => {
    const line = renderEvidence({
      event: 'Setor 20: 0.45s atras da sua volta de referencia neste trecho (2.41s contra 1.96s).',
      evidence: { microsector: 20, yourSeconds: 2.41, referenceSeconds: 1.96, lossSeconds: 0.45 },
    });
    expect(line).toContain('VOCE 2.41s');
    expect(line).toContain('REFERENCIA 1.96s');
    expect(line).not.toContain('MELHOR');
    expect(line).not.toContain('OTIMO');
  });

  it('names the reference in use (ADR 0016)', () => {
    const ai = renderEvidence({
      event: 'Setor 22: 0.60s atras da volta da IA neste trecho (1.98s contra 1.38s).',
      evidence: { microsector: 22, yourSeconds: 1.98, referenceSeconds: 1.38, lossSeconds: 0.6, referenceKind: 'volta_ia' },
    });
    expect(ai).toContain('VOLTA DA IA 1.38s');
    const own = renderEvidence({
      event: 'x',
      evidence: { microsector: 22, yourSeconds: 1.98, referenceSeconds: 1.5, lossSeconds: 0.48, referenceKind: 'minha_melhor' },
    });
    expect(own).toContain('SUA MELHOR 1.50s');
  });

  it('survives an optimal split that arrives as null', () => {
    const line = renderEvidence(microsectorEvent({ optimalSeconds: null }));
    expect(line).not.toContain('OTIMO');
  });

  it('shows the focus line of pedido 15 as a plain feed line', () => {
    const focus = {
      type: 'coaching_focus',
      event: 'Foco nas proximas voltas: setores 32, 38 e 43',
      evidence: 'Maior diferenca mediana para a volta da IA nas suas voltas do modelo.',
    };
    expect(microsectorEvidence(focus)).toBeNull();
    expect(renderEvidence(focus)).toBe('Maior diferenca mediana para a volta da IA nas suas voltas do modelo.');
  });
});
