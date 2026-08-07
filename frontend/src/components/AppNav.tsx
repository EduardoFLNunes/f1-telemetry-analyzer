import React from 'react';
import { Home, Activity, LineChart, Stethoscope } from 'lucide-react';

export type AppPage = 'home' | 'live' | 'analysis' | 'diagnostics';

type NavEntry = {
  id: AppPage;
  label: string;
  title: string;
  Icon: typeof Home;
};

const ENTRIES: NavEntry[] = [
  { id: 'home', label: 'Inicio', title: 'Pagina inicial', Icon: Home },
  { id: 'live', label: 'Pista', title: 'Telemetria ao vivo', Icon: Activity },
  { id: 'analysis', label: 'Analise', title: 'Analise de voltas gravadas', Icon: LineChart },
  { id: 'diagnostics', label: 'Sistema', title: 'Diagnostico e qualidade de dados', Icon: Stethoscope },
];

type Props = {
  page: AppPage;
  onNavigate: (page: AppPage) => void;
  /** Green when Assetto Corsa telemetry can be captured, amber while waiting. */
  captureActive?: boolean;
};

export const AppNav: React.FC<Props> = ({ page, onNavigate, captureActive = false }) => (
  <nav className="app-nav" aria-label="Navegacao principal">
    <div className="app-nav-brand">
      <div className="app-nav-mark">AT</div>
      <span className="app-nav-label" style={{ color: 'var(--text-3)' }}>TELEM</span>
    </div>

    {ENTRIES.map(({ id, label, title, Icon }) => (
      <button
        key={id}
        type="button"
        title={title}
        aria-current={page === id ? 'page' : undefined}
        onClick={() => onNavigate(id)}
        className="app-nav-item"
        style={{ position: 'relative' }}
      >
        <Icon size={15} strokeWidth={2} />
        <span className="app-nav-label">{label}</span>
        {id === 'live' && (
          <span
            className="app-nav-badge"
            title={captureActive ? 'Coletando telemetria' : 'Aguardando o Assetto Corsa'}
            style={{
              background: captureActive ? 'var(--emerald)' : 'var(--amber)',
              boxShadow: captureActive
                ? '0 0 6px rgba(52,211,153,0.8)'
                : '0 0 6px rgba(251,191,36,0.7)',
            }}
          />
        )}
      </button>
    ))}
  </nav>
);

export default AppNav;
