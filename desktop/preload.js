const { contextBridge, ipcRenderer } = require('electron');

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000';
const DEFAULT_FRONTEND_DEV_URL = 'http://127.0.0.1:5173';
const DEFAULT_UDP_OPPONENTS_PORT = 8765;

function stripTrailingSlash(value) {
  return String(value || '').replace(/\/+$/, '');
}

function apiBaseToWebSocketUrl(apiBaseUrl) {
  try {
    const url = new URL(apiBaseUrl);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    url.pathname = '/ws';
    url.search = '';
    url.hash = '';
    return url.toString();
  } catch {
    return 'ws://127.0.0.1:8000/ws';
  }
}

function portFromUrl(url, fallback) {
  try {
    const parsed = new URL(url);
    return Number(parsed.port || (parsed.protocol === 'https:' ? 443 : 80));
  } catch {
    return fallback;
  }
}

const apiBaseUrl = stripTrailingSlash(
  process.env.AT_BACKEND_URL ||
  process.env.VITE_API_BASE_URL ||
  process.env.VITE_API_URL ||
  DEFAULT_API_BASE_URL,
);
const frontendDevUrl = process.env.AT_DESKTOP_FRONTEND_URL || DEFAULT_FRONTEND_DEV_URL;
const wsUrl = process.env.VITE_WS_URL || process.env.AT_BACKEND_WS_URL || apiBaseToWebSocketUrl(apiBaseUrl);
const mode = process.env.AT_DESKTOP_MODE === 'production' ? 'production' : 'development';

contextBridge.exposeInMainWorld('desktopRuntime', {
  apiBaseUrl,
  wsUrl,
  backendPort: portFromUrl(apiBaseUrl, 8000),
  frontendDevPort: portFromUrl(frontendDevUrl, 5173),
  udpOpponentsPort: Number(process.env.AT_UDP_OPPONENTS_PORT || DEFAULT_UDP_OPPONENTS_PORT),
  mode,
  phase: 'phase-12.1-prep',
});

contextBridge.exposeInMainWorld('automobilistaDesktop', {
  backendHealth: () => ipcRenderer.invoke('backend:health'),
  phase: 'phase-12.1-prep',
});
