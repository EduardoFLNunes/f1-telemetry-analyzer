/**
 * Sistema (pedido 29): tudo o que é de desenvolvimento, fora das telas do
 * piloto. Três partes, cada uma com o seu endereço:
 *
 * - `#/sistema`: o diagnóstico de antes (runtime, versão, qualidade dos dados,
 *   física do carro), como estava;
 * - `#/sistema/depuracao`: a depuração que saiu do mapa e dos painéis;
 * - `#/sistema/guia`: o guia visual.
 */
import React from 'react';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { DataQualityPanel } from '../components/DataQualityPanel';
import { DesktopRuntimePanel } from '../components/DesktopRuntimePanel';
import { VersionPanel } from '../components/VersionPanel';
import { CarPhysicsDebugPanel } from '../components/CarPhysicsDebugPanel';
import { hashDaRota } from '../navegacao/rotas';
import { DepuracaoSistema } from './sistema/DepuracaoSistema';
import { GuiaVisual } from './sistema/GuiaVisual';

const ABAS: ReadonlyArray<{ id: string | null; rotulo: string }> = [
  { id: null, rotulo: 'Diagnóstico' },
  { id: 'depuracao', rotulo: 'Depuração' },
  { id: 'guia', rotulo: 'Guia visual' },
];

const Diagnostico: React.FC = () => (
  <>
    <section className="vidro painel">
      <div className="superficie" style={{ minHeight: 300, overflow: 'hidden' }}>
        <DesktopRuntimePanel active />
        <VersionPanel />
      </div>
    </section>
    <div className="grade-2">
      <section className="vidro painel">
        <div className="superficie" style={{ minHeight: 320, overflow: 'hidden' }}>
          <DataQualityPanel active />
        </div>
      </section>
      <section className="vidro painel">
        <div className="superficie" style={{ minHeight: 320, overflow: 'hidden' }}>
          <CarPhysicsDebugPanel active />
        </div>
      </section>
    </div>
  </>
);

export const SistemaPage: React.FC<{ sub: string | null }> = ({ sub }) => {
  const aba = sub === 'depuracao' || sub === 'guia' ? sub : null;
  return (
    <ErrorBoundary>
      <div className="tela-conteudo">
        <header className="cabecalho-tela">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div className="sobrancelha">Desenvolvimento</div>
            <h1 className="titulo-tela">Sistema</h1>
          </div>
          <nav className="segmentado" aria-label="Partes da tela Sistema">
            {ABAS.map((a) => (
              <a
                key={a.rotulo}
                href={hashDaRota('sistema', a.id)}
                aria-current={aba === a.id ? 'page' : undefined}
                className="segmentado-link"
              >
                {a.rotulo}
              </a>
            ))}
          </nav>
        </header>
        {aba === null && <Diagnostico />}
        {aba === 'depuracao' && <DepuracaoSistema />}
        {aba === 'guia' && <GuiaVisual />}
      </div>
    </ErrorBoundary>
  );
};

export default SistemaPage;
