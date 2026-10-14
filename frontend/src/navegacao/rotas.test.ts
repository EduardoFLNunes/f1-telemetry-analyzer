import { describe, expect, it } from 'vitest';
import { hashDaRota, rotaDoHash, TELAS } from './rotas';

describe('rotas das telas', () => {
  it('as seis telas do redesenho, na ordem da navegação', () => {
    expect(TELAS.map((t) => t.rotulo)).toEqual(['Sessões', 'Ao vivo', 'Volta', 'Evolução', 'Coleta de dados', 'Sistema']);
  });

  it('lê a tela e a subpágina do hash', () => {
    expect(rotaDoHash('#/volta')).toEqual({ tela: 'volta', sub: null });
    expect(rotaDoHash('#/sistema/guia')).toEqual({ tela: 'sistema', sub: 'guia' });
    expect(rotaDoHash('#/ao-vivo/')).toEqual({ tela: 'ao-vivo', sub: null });
  });

  it('sem hash ou com endereço desconhecido, abre Sessões', () => {
    expect(rotaDoHash('')).toEqual({ tela: 'sessoes', sub: null });
    expect(rotaDoHash('#/pista')).toEqual({ tela: 'sessoes', sub: null });
    expect(rotaDoHash(undefined)).toEqual({ tela: 'sessoes', sub: null });
  });

  it('ida e volta entre hash e rota', () => {
    for (const { id } of TELAS) expect(rotaDoHash(hashDaRota(id))).toEqual({ tela: id, sub: null });
    expect(hashDaRota('sistema', 'guia')).toBe('#/sistema/guia');
  });
});
