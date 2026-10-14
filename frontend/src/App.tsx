/**
 * Sistema de Telemetria e Otimização de Trajetórias: a casca do app (pedido 29).
 *
 * A navegação de vidro no topo, o fundo em carbono e a tela da rota atual
 * (`#/tela`, ver navegacao/rotas.ts). O WebSocket da telemetria fica aqui, e
 * não numa tela, para o fluxo ao vivo continuar ligado enquanto o piloto
 * troca de tela.
 */
import React, { useEffect } from 'react';
import './App.css';
import { useTelemetryWS } from './hooks/useTelemetryWS';
import { useEstadoDoApp } from './hooks/useEstadoDoApp';
import { useRota } from './navegacao/useRota';
import { Navegacao } from './components/Navegacao';
import Dashboard from './Dashboard';
import SessoesPage from './pages/SessoesPage';
import AoVivoPage from './pages/AoVivoPage';
import AnalysisPage from './pages/AnalysisPage';
import ColetaPage from './pages/ColetaPage';
import SistemaPage from './pages/SistemaPage';
import { aplicarVidro, vidroLigado } from './theme/vidro';

const App: React.FC = () => {
  useTelemetryWS();
  const { tela, sub, navegar } = useRota();
  const estado = useEstadoDoApp();

  useEffect(() => {
    aplicarVidro(vidroLigado());
  }, []);

  return (
    <div className="casca">
      <div className="casca-fundo" aria-hidden="true" />
      <Navegacao tela={tela} estado={estado} />
      <main className={tela === 'volta' ? 'tela tela--cheia' : 'tela'} id="conteudo">
        {tela === 'sessoes' && <SessoesPage estado={estado} />}
        {tela === 'ao-vivo' && <AoVivoPage estado={estado} />}
        {tela === 'volta' && <Dashboard />}
        {tela === 'evolucao' && (
          <AnalysisPage abrirUltimaVolta={sub === 'ultima-volta'} aoAbrirReplay={() => navegar('volta')} />
        )}
        {tela === 'coleta' && <ColetaPage />}
        {tela === 'sistema' && <SistemaPage sub={sub} />}
      </main>
    </div>
  );
};

export default App;
