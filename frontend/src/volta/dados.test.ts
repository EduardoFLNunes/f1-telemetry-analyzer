import { describe, expect, it } from 'vitest';
import { textoDoErro } from './dados';

describe('textoDoErro', () => {
  it('diz que o backend não respondeu quando não há resposta', () => {
    expect(textoDoErro({ isAxiosError: true, message: 'Network Error' })).toBe('o backend não respondeu; tentando de novo');
  });
  it('usa a frase do backend quando ele manda uma', () => {
    expect(textoDoErro({ isAxiosError: true, response: { status: 404, data: { detail: 'volta não encontrada no store' } } })).toBe('volta não encontrada no store');
  });
  it('diz o código quando o backend não manda frase', () => {
    expect(textoDoErro({ isAxiosError: true, response: { status: 500, data: {} } })).toBe('o backend respondeu 500');
  });
  it('mantém a mensagem dos outros erros', () => {
    expect(textoDoErro(new Error('sem dados'))).toBe('sem dados');
  });
});
