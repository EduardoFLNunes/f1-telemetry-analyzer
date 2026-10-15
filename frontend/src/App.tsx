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
import SessoesPage from './pages/SessoesPage';
import AoVivoPage from './pages/AoVivoPage';
import VoltaPage from './pages/VoltaPage';
import EvolucaoPage from './pages/EvolucaoPage';
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

  // Trocar de tela começa do topo; trocar de volta na mesma tela mantém a rolagem, como no protótipo.
  useEffect(() => {
    document.getElementById('conteudo')?.scrollTo(0, 0);
  }, [tela]);

  return (
    <div className="casca">
      <div className="casca-fundo" aria-hidden="true" />
      <Navegacao tela={tela} estado={estado} />
      <main className="tela" id="conteudo">
        {tela === 'sessoes' && <SessoesPage estado={estado} />}
        {tela === 'ao-vivo' && <AoVivoPage estado={estado} />}
        {tela === 'volta' && <VoltaPage sub={sub} navegar={navegar} />}
        {tela === 'evolucao' && <EvolucaoPage navegar={navegar} />}
        {tela === 'coleta' && <ColetaPage />}
        {tela === 'sistema' && <SistemaPage sub={sub} />}
      </main>
    </div>
  );
};

export default App;
