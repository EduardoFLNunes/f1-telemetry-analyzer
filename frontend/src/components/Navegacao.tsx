/**
 * A navegação do app (pedido 29): uma barra de vidro no topo, com as seis
 * telas, no lugar do trilho lateral. Cada item é um link de verdade para
 * `#/tela`, então recarregar a janela volta para a mesma tela.
 */
import React from 'react';
import clsx from 'clsx';
import { hashDaRota, TELAS, type Tela } from '../navegacao/rotas';
import type { EstadoDoApp } from '../hooks/useEstadoDoApp';

const Marca: React.FC = () => (
  <a href={hashDaRota('sessoes')} className="navegacao-marca" style={{ textDecoration: 'none' }} aria-label="Sistema de Telemetria e Otimização de Trajetórias: início">
    <svg width="26" height="26" viewBox="0 0 26 26" fill="none" aria-hidden="true">
      <path d="M4 18c3-9 7-12 11-12 4 0 7 3 7 7s-4 7-9 7" stroke="var(--texto-1)" strokeWidth="2.2" strokeLinecap="round" />
      <circle cx="13" cy="20" r="2.6" fill="var(--vermelho)" />
    </svg>
    <span>
      Telemetria e
      <br />
      Trajetórias
    </span>
  </a>
);

function textoDoBackend(estado: EstadoDoApp): { texto: string; cor: string } {
  const { fase, versao, segundos } = estado.backend;
  if (fase === 'pronto') return { texto: `backend pronto${versao ? ` · ${versao}` : ''}`, cor: 'var(--estado-ok)' };
  if (fase === 'caiu') return { texto: 'backend sem resposta', cor: 'var(--estado-erro)' };
  return { texto: `ligando o backend · ${segundos} s`, cor: 'var(--estado-aviso)' };
}

export const Navegacao: React.FC<{ tela: Tela; estado: EstadoDoApp }> = ({ tela, estado }) => {
  const backend = textoDoBackend(estado);
  const pontoAoVivo = estado.gravando ? 'navegacao-ponto--gravando' : estado.capturaLiberada ? 'navegacao-ponto--conectado' : '';
  const rotuloAoVivo = estado.gravando ? 'gravando' : estado.capturaLiberada ? 'jogo conectado' : 'sem sessão no jogo';

  return (
    <nav className="vidro navegacao" aria-label="Telas">
      <Marca />
      <div className="navegacao-itens">
        {TELAS.map(({ id, rotulo, descricao }) => (
          <a
            key={id}
            href={hashDaRota(id)}
            className="navegacao-item"
            aria-current={tela === id ? 'page' : undefined}
            title={descricao}
          >
            {rotulo}
            {id === 'ao-vivo' && (
              <span
                className={clsx('navegacao-ponto', pontoAoVivo, estado.gravando && 'pulso')}
                role="img"
                aria-label={rotuloAoVivo}
                title={rotuloAoVivo}
              />
            )}
          </a>
        ))}
      </div>
      <span className="navegacao-estado" role="status">
        <span className={clsx('ponto', estado.backend.fase === 'subindo' && 'pulso')} style={{ width: 8, height: 8, background: backend.cor }} />
        {backend.texto}
      </span>
    </nav>
  );
};

export default Navegacao;
