import React from 'react';
import { DataQualityPanel } from '../components/DataQualityPanel';
import { DesktopRuntimePanel } from '../components/DesktopRuntimePanel';
import { VersionPanel } from '../components/VersionPanel';
import { CarPhysicsDebugPanel } from '../components/CarPhysicsDebugPanel';
import { ErrorBoundary } from '../components/ErrorBoundary';

/**
 * System-facing view: runtime/packaging state, Assetto Corsa setup, data
 * reliability and raw car physics. Kept off the live dashboard so driving does
 * not compete with diagnostics for screen space.
 */
export const DiagnosticsPage: React.FC = () => (
  <ErrorBoundary>
    <div className="app-page">
      <div>
        <div className="app-page-title">Diagnostico do sistema</div>
        <div className="app-page-subtitle">
          Estado do runtime, configuracao do Assetto Corsa, confiabilidade dos dados e fisica do carro.
        </div>
      </div>

      <div className="panel" style={{ minHeight: 300, overflow: 'hidden' }}>
        <DesktopRuntimePanel active />
        <VersionPanel />
      </div>

      <div className="home-columns">
        <div className="panel" style={{ minHeight: 320, overflow: 'hidden' }}>
          <DataQualityPanel active />
        </div>
        <div className="panel" style={{ minHeight: 320, overflow: 'hidden' }}>
          <CarPhysicsDebugPanel active />
        </div>
      </div>
    </div>
  </ErrorBoundary>
);

export default DiagnosticsPage;
