const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000';
const DEFAULT_WS_URL = 'ws://127.0.0.1:8000/ws';

function desktopRuntime() {
  if (typeof window === 'undefined') return null;
  return window.desktopRuntime || null;
}

function stripTrailingSlash(value: unknown): string {
  return String(value || '').replace(/\/+$/, '');
}

function resolveApiBaseUrl(): string {
  const runtime = desktopRuntime();
  return stripTrailingSlash(
    import.meta.env.VITE_API_BASE_URL ||
    import.meta.env.VITE_API_URL ||
    runtime?.apiBaseUrl ||
    DEFAULT_API_BASE_URL,
  );
}

function apiBaseToWebSocketUrl(apiBaseUrl: string): string {
  try {
    const url = new URL(apiBaseUrl);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    url.pathname = '/ws';
    url.search = '';
    url.hash = '';
    return url.toString();
  } catch {
    return DEFAULT_WS_URL;
  }
}

export const API_BASE_URL = resolveApiBaseUrl();
export const WS_URL = import.meta.env.VITE_WS_URL || desktopRuntime()?.wsUrl || apiBaseToWebSocketUrl(API_BASE_URL);

export function apiUrl(path: string): string {
  const normalizedPath = String(path || '').startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
}
