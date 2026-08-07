/**
 * Motorsport Intelligence Workstation — Entry Shell
 *
 * Holds the persistent navigation rail and swaps the active page. The telemetry
 * WebSocket lives here (not inside a page) so the live stream and its store stay
 * connected while the user browses analysis or diagnostics.
 */
import React, { useEffect, useState } from 'react';
import './App.css';
import { useTelemetryWS } from './hooks/useTelemetryWS';
import { AppNav, AppPage } from './components/AppNav';
import Dashboard from './Dashboard';
import HomePage from './pages/HomePage';
import AnalysisPage from './pages/AnalysisPage';
import DiagnosticsPage from './pages/DiagnosticsPage';
import { api } from './api/client';

const App: React.FC = () => {
  useTelemetryWS();
  const [page, setPage] = useState<AppPage>('home');
  const [captureActive, setCaptureActive] = useState(false);

  // Drives the nav indicator so the capture state is visible from every page.
  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const runtime = await api.getRuntimeStatus();
        if (!cancelled) setCaptureActive(Boolean(runtime?.capture?.allowed));
      } catch {
        if (!cancelled) setCaptureActive(false);
      }
    };
    poll();
    const timer = window.setInterval(poll, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <div className="app-root">
      <AppNav page={page} onNavigate={setPage} captureActive={captureActive} />
      <div className="app-main">
        {page === 'home' && <HomePage onNavigate={setPage} />}
        {page === 'live' && <Dashboard />}
        {page === 'analysis' && <AnalysisPage />}
        {page === 'diagnostics' && <DiagnosticsPage />}
      </div>
    </div>
  );
};

export default App;
