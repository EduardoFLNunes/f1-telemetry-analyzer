import React, { useState } from 'react';
import { AssistedAnalysisPanel } from '../components/AssistedAnalysisPanel';
import { AssistedLapTraces } from '../components/AssistedLapTraces';
import { SessionLapsPanel } from '../components/SessionLapsPanel';
import { ElevationProfile } from '../components/ElevationProfile';
import { ErrorBoundary } from '../components/ErrorBoundary';

type Tab = 'laps' | 'assisted' | 'traces' | 'elevation';

const TABS: Array<[Tab, string]> = [
  ['laps', 'Voltas'],
  ['assisted', 'Analise assistida'],
  ['traces', 'Tracados'],
  ['elevation', 'Elevacao'],
];

/**
 * Post-lap analysis. These panels used to compete for the dashboard's right rail
 * against live-driving widgets; giving them a page of their own is what removes
 * the "everything at once" problem from the live view.
 */
export const AnalysisPage: React.FC = () => {
  const [tab, setTab] = useState<Tab>('laps');

  return (
    <ErrorBoundary>
      <div className="app-page">
        <div>
          <div className="app-page-title">Analise de voltas</div>
          <div className="app-page-subtitle">
            Sessoes gravadas em disco, feedback assistido e comparacao de tracados.
          </div>
        </div>

        <div className="panel" style={{ display: 'flex', gap: 3, padding: 4, alignSelf: 'flex-start' }}>
          {TABS.map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className="num"
              style={{
                padding: '6px 12px',
                fontSize: 8,
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.1em',
                borderRadius: 2,
                cursor: 'pointer',
                border: tab === id ? '1px solid rgba(34,211,238,0.22)' : '1px solid transparent',
                background: tab === id ? 'rgba(34,211,238,0.08)' : 'transparent',
                color: tab === id ? 'var(--cyan)' : 'var(--text-3)',
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Panels stay mounted so their internal caches survive tab switches; the
            `active` prop is what suspends polling on the hidden ones. */}
        <div className="panel" style={{ flex: 1, minHeight: 420, position: 'relative', overflow: 'hidden' }}>
          <div style={{ position: 'absolute', inset: 0, opacity: tab === 'laps' ? 1 : 0, pointerEvents: tab === 'laps' ? 'auto' : 'none', transition: 'opacity 0.2s' }}>
            <SessionLapsPanel active={tab === 'laps'} onOpenAssistedAnalysis={() => setTab('assisted')} />
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
