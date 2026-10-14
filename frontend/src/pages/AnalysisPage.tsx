import React, { useState } from 'react';
import { AssistedAnalysisPanel } from '../components/AssistedAnalysisPanel';
import { AssistedLapTraces } from '../components/AssistedLapTraces';
import { SessionLapsPanel } from '../components/SessionLapsPanel';
import { ElevationProfile } from '../components/ElevationProfile';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { Segmentado } from '../components/ui/base';

type Tab = 'laps' | 'assisted' | 'traces' | 'elevation';

const TABS: Array<[Tab, string]> = [
  ['laps', 'Voltas'],
  ['assisted', 'Análise assistida'],
  ['traces', 'Traçados'],
  ['elevation', 'Elevação'],
];

/**
 * Evolução (pedido 29): por enquanto, o conteúdo da antiga Análise dentro da
 * casca nova. O redesenho desta tela, com o painel de evolução, é o pedido 4
 * do redesenho.
 *
 * `abrirUltimaVolta` (atalho "Última volta" do hero) abre a última volta válida
 * da sessão mais recente no replay; `aoAbrirReplay` leva para a tela Volta, que
 * é onde o replay toca (inventário, problema E).
 */
export const AnalysisPage: React.FC<{ abrirUltimaVolta?: boolean; aoAbrirReplay?: () => void }> = ({ abrirUltimaVolta = false, aoAbrirReplay }) => {
  const [tab, setTab] = useState<Tab>('laps');

  return (
    <ErrorBoundary>
      <div className="tela-conteudo" style={{ minHeight: '100%' }}>
        <header className="cabecalho-tela">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div className="sobrancelha">Voltas gravadas · conteúdo atual da Análise</div>
            <h1 className="titulo-tela">Evolução</h1>
          </div>
          <Segmentado rotulo="Partes da Evolução" opcoes={TABS.map(([id, texto]) => ({ id, texto }))} valor={tab} aoMudar={setTab} />
        </header>

        {/* Panels stay mounted so their internal caches survive tab switches; the
            `active` prop is what suspends polling on the hidden ones. */}
        <div className="vidro" style={{ flex: 1, minHeight: 640, position: 'relative', overflow: 'hidden', padding: 0 }}>
          <div style={{ position: 'absolute', inset: 0, opacity: tab === 'laps' ? 1 : 0, pointerEvents: tab === 'laps' ? 'auto' : 'none', transition: 'opacity 0.2s' }}>
            <SessionLapsPanel
              active={tab === 'laps'}
              onOpenAssistedAnalysis={() => setTab('assisted')}
              abrirUltimaVolta={abrirUltimaVolta}
              aoAbrirReplay={aoAbrirReplay}
            />
          </div>
          <div style={{ position: 'absolute', inset: 0, opacity: tab === 'assisted' ? 1 : 0, pointerEvents: tab === 'assisted' ? 'auto' : 'none', transition: 'opacity 0.2s' }}>
            <AssistedAnalysisPanel active={tab === 'assisted'} />
          </div>
          <div style={{ position: 'absolute', inset: 0, opacity: tab === 'traces' ? 1 : 0, pointerEvents: tab === 'traces' ? 'auto' : 'none', transition: 'opacity 0.2s' }}>
            <AssistedLapTraces active={tab === 'traces'} />
          </div>
          <div style={{ position: 'absolute', inset: 0, opacity: tab === 'elevation' ? 1 : 0, pointerEvents: tab === 'elevation' ? 'auto' : 'none', transition: 'opacity 0.2s' }}>
            <ElevationProfile active={tab === 'elevation'} />
          </div>
        </div>
      </div>
    </ErrorBoundary>
  );
};

export default AnalysisPage;
