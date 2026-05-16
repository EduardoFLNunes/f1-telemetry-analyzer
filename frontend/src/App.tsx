/**
 * Motorsport Intelligence Workstation — Entry Shell
 */
import React from 'react';
import './App.css';
import { useTelemetryWS } from './hooks/useTelemetryWS';
import Dashboard from './Dashboard';

const App: React.FC = () => {
  useTelemetryWS();
  return (
    <div style={{ width: '100vw', height: '100vh', overflow: 'hidden', background: '#06060d' }}>
      <Dashboard />
    </div>
  );
};

export default App;
