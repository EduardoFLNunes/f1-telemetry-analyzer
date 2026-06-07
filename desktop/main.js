const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const http = require('node:http');
const https = require('node:https');
const path = require('node:path');

const APP_ROOT = path.resolve(__dirname, '..');
const FRONTEND_DIST = path.join(APP_ROOT, 'frontend', 'dist', 'index.html');
const DEFAULT_FRONTEND_DEV_URL = 'http://127.0.0.1:5173';
const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8000';

const FRONTEND_URL = process.env.AT_DESKTOP_FRONTEND_URL || DEFAULT_FRONTEND_DEV_URL;
const BACKEND_URL = stripTrailingSlash(process.env.AT_BACKEND_URL || DEFAULT_BACKEND_URL);
const HEALTH_URL = process.env.AT_BACKEND_HEALTH_URL || `${BACKEND_URL}/api/health`;
const SHOULD_START_BACKEND = flagEnabled(process.env.AT_DESKTOP_START_BACKEND) || flagEnabled(process.env.DESKTOP_AUTOSTART_BACKEND);
const BACKEND_COMMAND = process.env.AT_BACKEND_COMMAND || '';
const BACKEND_ARGS = parseBackendArgs(process.env.AT_BACKEND_ARGS);

let mainWindow = null;
let backendProcess = null;

function ensureLogsDir() {
  const logsDir = path.join(APP_ROOT, 'logs');
  fs.mkdirSync(logsDir, { recursive: true });
  return logsDir;
}

function appendDesktopLog(message) {
  const line = `[${new Date().toISOString()}] ${message}\n`;
  fs.appendFileSync(path.join(ensureLogsDir(), 'desktop.log'), line);
}

function stripTrailingSlash(value) {
  return String(value || '').replace(/\/+$/, '');
}

function flagEnabled(value) {
  return ['1', 'true', 'yes', 'on'].includes(String(value || '').trim().toLowerCase());
}

function parseBackendArgs(value) {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value);
    if (Array.isArray(parsed)) return parsed.map(String);
  } catch {
    // Plain command-line text is accepted for the early packaging phase.
  }
  return String(value).match(/(?:[^\s"]+|"[^"]*")+/g)?.map((arg) => arg.replace(/^"|"$/g, '')) || [];
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function requestJson(url, timeoutMs = 2500) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(url);
    const client = parsed.protocol === 'https:' ? https : http;
    const req = client.get(parsed, { timeout: timeoutMs }, (res) => {
      let body = '';
      res.setEncoding('utf8');
      res.on('data', (chunk) => {
        body += chunk;
      });
      res.on('end', () => {
        let data = null;
        let parseError = null;
        try {
          data = body ? JSON.parse(body) : null;
        } catch (error) {
          parseError = error;
        }
        resolve({
          ok: res.statusCode >= 200 && res.statusCode < 300 && !parseError,
          statusCode: res.statusCode,
          data,
          error: parseError ? parseError.message : undefined,
        });
      });
    });
    req.on('timeout', () => {
      req.destroy(new Error(`Health check timed out: ${url}`));
    });
    req.on('error', reject);
  });
}

async function backendHealth() {
  try {
    return await requestJson(HEALTH_URL);
  } catch (error) {
    return {
      ok: false,
      statusCode: null,
      error: error.message,
    };
  }
}

async function waitForBackendHealth(timeoutMs = 15000, intervalMs = 500) {
  const startedAt = Date.now();
  let lastHealth = null;
  while (Date.now() - startedAt < timeoutMs) {
    lastHealth = await backendHealth();
    if (lastHealth.ok) return lastHealth;
    await sleep(intervalMs);
  }
  return {
    ok: false,
    statusCode: lastHealth?.statusCode ?? null,
    error: lastHealth?.error || `Backend health did not become ready within ${timeoutMs}ms`,
  };
}

function startBackendProcess() {
  if (!SHOULD_START_BACKEND) {
    appendDesktopLog('Backend autostart disabled.');
    return;
  }
  if (!BACKEND_COMMAND) {
    appendDesktopLog('Backend autostart requested but AT_BACKEND_COMMAND is empty.');
    return;
  }
  if (backendProcess) return;

  const logsDir = ensureLogsDir();
  const backendLog = fs.createWriteStream(path.join(logsDir, 'backend.log'), { flags: 'a' });
  backendProcess = spawn(BACKEND_COMMAND, BACKEND_ARGS, {
    cwd: APP_ROOT,
    shell: process.platform === 'win32',
    env: process.env,
  });
  backendProcess.stdout?.pipe(backendLog);
  backendProcess.stderr?.pipe(backendLog);
  backendProcess.on('error', (error) => {
    appendDesktopLog(`Backend process failed to start: ${error.message}`);
    backendProcess = null;
  });
  backendProcess.on('exit', (code, signal) => {
    appendDesktopLog(`Backend process exited code=${code} signal=${signal}`);
    backendProcess = null;
  });
  appendDesktopLog(`Backend process started: ${BACKEND_COMMAND} ${BACKEND_ARGS.join(' ')}`);
}

async function prepareBackendRuntime() {
  const existingHealth = await backendHealth();
  if (existingHealth.ok) {
    appendDesktopLog(`Backend already online at ${HEALTH_URL}.`);
    return existingHealth;
  }

  if (existingHealth.statusCode) {
    appendDesktopLog(`Backend port responded without a valid health payload. status=${existingHealth.statusCode} error=${existingHealth.error || 'none'}`);
  } else {
    appendDesktopLog(`Backend health unavailable before startup. error=${existingHealth.error || 'connection unavailable'}`);
  }

  if (!SHOULD_START_BACKEND) {
    appendDesktopLog('Backend autostart remains disabled; user must start FastAPI separately.');
    return existingHealth;
  }

  startBackendProcess();
  const startedHealth = await waitForBackendHealth();
  if (startedHealth.ok) {
    appendDesktopLog(`Backend health OK after autostart at ${HEALTH_URL}.`);
  } else {
    appendDesktopLog(`Backend autostart did not reach health OK. error=${startedHealth.error || 'unknown'}`);
  }
  return startedHealth;
}

function stopBackendProcess() {
  if (!backendProcess) return;
  backendProcess.kill();
  backendProcess = null;
  appendDesktopLog('Backend process stopped.');
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 1024,
    minHeight: 640,
    backgroundColor: '#06060d',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  const useDevServer = process.env.AT_DESKTOP_MODE !== 'production';
  if (useDevServer) {
    appendDesktopLog(`Loading frontend dev server: ${FRONTEND_URL}`);
    await mainWindow.loadURL(FRONTEND_URL);
    return;
  }

  if (fs.existsSync(FRONTEND_DIST)) {
    appendDesktopLog(`Loading frontend static build: ${FRONTEND_DIST}`);
    await mainWindow.loadFile(FRONTEND_DIST);
    return;
  }

  appendDesktopLog('frontend/dist is missing; falling back to dev server URL.');
  await mainWindow.loadURL(FRONTEND_URL);
}

app.whenReady().then(async () => {
  appendDesktopLog('Desktop shell starting.');
  await prepareBackendRuntime();
  await createWindow();

  app.on('activate', async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      await createWindow();
    }
  });
});

app.on('before-quit', () => {
  stopBackendProcess();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

ipcMain.handle('backend:health', backendHealth);
