const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const http = require('node:http');
const https = require('node:https');
const path = require('node:path');

const APP_ROOT = path.resolve(__dirname, '..');
const FRONTEND_DIST = path.join(APP_ROOT, 'frontend', 'dist', 'index.html');
const DEFAULT_FRONTEND_DEV_URL = 'http://127.0.0.1:5173';
const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8000';
const BACKEND_EXE_NAME = process.platform === 'win32' ? 'automobilista-backend.exe' : 'automobilista-backend';

const FRONTEND_URL = process.env.AT_DESKTOP_FRONTEND_URL || DEFAULT_FRONTEND_DEV_URL;
const BACKEND_URL = stripTrailingSlash(process.env.AT_BACKEND_URL || DEFAULT_BACKEND_URL);
const HEALTH_URL = process.env.AT_BACKEND_HEALTH_URL || `${BACKEND_URL}/api/health`;
const BACKEND_HOST = backendHostFromUrl(BACKEND_URL);
const BACKEND_PORT = backendPortFromUrl(BACKEND_URL);
const SHOULD_START_BACKEND = flagEnabled(process.env.AT_DESKTOP_AUTOSTART_BACKEND)
  || flagEnabled(process.env.AT_DESKTOP_START_BACKEND)
  || flagEnabled(process.env.DESKTOP_AUTOSTART_BACKEND);
const BACKEND_COMMAND = process.env.AT_BACKEND_COMMAND || '';
const BACKEND_ARGS = parseBackendArgs(process.env.AT_BACKEND_ARGS);

let mainWindow = null;
let backendProcess = null;
let backendStartedByElectron = false;
let backendStopping = false;

const desktopRuntimeState = {
  autostartEnabled: SHOULD_START_BACKEND,
  backendStartedByElectron: false,
  backendSource: 'unavailable',
  backendExecutablePath: null,
  backendRunnerPath: null,
  backendCommand: null,
  backendPid: null,
  apiBaseUrl: BACKEND_URL,
  healthUrl: HEALTH_URL,
  lastBackendError: null,
  lastHealth: null,
  lastCheckedAt: null,
};

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

function backendHostFromUrl(value) {
  try {
    return new URL(value).hostname || '127.0.0.1';
  } catch {
    return '127.0.0.1';
  }
}

function backendPortFromUrl(value) {
  try {
    const parsed = new URL(value);
    return Number(parsed.port || (parsed.protocol === 'https:' ? 443 : 80));
  } catch {
    return 8000;
  }
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

function resolveMaybeRelativePath(value) {
  if (!value) return null;
  if (path.isAbsolute(value)) return value;
  if (!value.includes('/') && !value.includes('\\') && !value.startsWith('.')) return value;
  return path.join(APP_ROOT, value);
}

function packagedBackendCandidates() {
  const candidates = [];
  const configured = resolveMaybeRelativePath(process.env.AT_BACKEND_EXE_PATH);
  if (configured) candidates.push(configured);

  if (app.isPackaged && process.resourcesPath) {
    candidates.push(path.join(process.resourcesPath, 'backend', BACKEND_EXE_NAME));
  }

  candidates.push(path.join(__dirname, 'resources', 'backend', BACKEND_EXE_NAME));
  candidates.push(path.join(APP_ROOT, 'backend', 'dist', BACKEND_EXE_NAME));
  candidates.push(path.join(APP_ROOT, 'dist', BACKEND_EXE_NAME));
  return candidates;
}

function resolvePythonRunnerLaunch() {
  const usePythonRunner = flagEnabled(process.env.AT_BACKEND_USE_PYTHON_RUNNER)
    || String(process.env.AT_BACKEND_RUNNER || '').trim().toLowerCase() === 'python';
  if (!usePythonRunner) return null;

  const pythonPath = resolveMaybeRelativePath(process.env.AT_BACKEND_PYTHON)
    || path.join(APP_ROOT, '.venv', process.platform === 'win32' ? 'Scripts' : 'bin', process.platform === 'win32' ? 'python.exe' : 'python');
  const runnerPath = resolveMaybeRelativePath(process.env.AT_BACKEND_RUNNER_PATH)
    || path.join(APP_ROOT, 'backend', 'desktop_backend_runner.py');

  if (!fs.existsSync(pythonPath)) {
    return { error: `Python runner requested but Python was not found: ${pythonPath}` };
  }
  if (!fs.existsSync(runnerPath)) {
    return { error: `Python runner requested but runner was not found: ${runnerPath}` };
  }

  return {
    source: 'python-runner',
    command: pythonPath,
    args: [runnerPath],
    cwd: APP_ROOT,
    runnerPath,
    useShell: false,
  };
}

function resolveBackendLaunch() {
  if (BACKEND_COMMAND) {
    const command = resolveMaybeRelativePath(BACKEND_COMMAND);
    return {
      source: process.env.AT_BACKEND_SOURCE || 'custom-command',
      command,
      args: BACKEND_ARGS,
      cwd: APP_ROOT,
      executablePath: command,
      useShell: process.platform === 'win32' && /\.(cmd|bat)$/i.test(command),
    };
  }

  const pythonLaunch = resolvePythonRunnerLaunch();
  if (pythonLaunch) return pythonLaunch;

  const candidates = packagedBackendCandidates();
  const executablePath = candidates.find((candidate) => fs.existsSync(candidate));
  if (executablePath) {
    return {
      source: 'packaged-exe',
      command: executablePath,
      args: [],
      cwd: APP_ROOT,
      executablePath,
      useShell: false,
    };
  }

  const configuredPath = resolveMaybeRelativePath(process.env.AT_BACKEND_EXE_PATH);
  const searched = configuredPath || candidates.join('; ');
  return { error: `Backend executable not found. Searched: ${searched}` };
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
    const health = await requestJson(HEALTH_URL);
    desktopRuntimeState.lastHealth = health;
    desktopRuntimeState.lastCheckedAt = new Date().toISOString();
    if (health.ok) desktopRuntimeState.lastBackendError = null;
    return health;
  } catch (error) {
    const health = {
      ok: false,
      statusCode: null,
      error: error.message,
    };
    desktopRuntimeState.lastHealth = health;
    desktopRuntimeState.lastCheckedAt = new Date().toISOString();
    return health;
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
  if (backendProcess) return;

  const launch = resolveBackendLaunch();
  if (!launch || launch.error) {
    desktopRuntimeState.backendSource = 'unavailable';
    desktopRuntimeState.lastBackendError = launch?.error || 'Backend launch configuration is unavailable.';
    appendDesktopLog(desktopRuntimeState.lastBackendError);
    return;
  }

  const logsDir = ensureLogsDir();
  const backendLog = fs.createWriteStream(path.join(logsDir, 'backend.log'), { flags: 'a' });
  backendLog.write(`\n[${new Date().toISOString()}] Starting ${launch.source}: ${launch.command} ${launch.args.join(' ')}\n`);
  backendProcess = spawn(launch.command, launch.args, {
    cwd: launch.cwd || APP_ROOT,
    shell: Boolean(launch.useShell),
    env: {
      ...process.env,
      AT_BACKEND_HOST: process.env.AT_BACKEND_HOST || BACKEND_HOST,
      AT_BACKEND_PORT: process.env.AT_BACKEND_PORT || String(BACKEND_PORT),
      AT_BACKEND_REPO_ROOT: process.env.AT_BACKEND_REPO_ROOT || APP_ROOT,
      PYTHONUNBUFFERED: '1',
    },
  });
  backendStartedByElectron = true;
  desktopRuntimeState.backendStartedByElectron = true;
  desktopRuntimeState.backendSource = launch.source;
  desktopRuntimeState.backendExecutablePath = launch.executablePath || null;
  desktopRuntimeState.backendRunnerPath = launch.runnerPath || null;
  desktopRuntimeState.backendCommand = launch.command;
  desktopRuntimeState.backendPid = backendProcess.pid;
  desktopRuntimeState.lastBackendError = null;

  backendProcess.stdout?.pipe(backendLog);
  backendProcess.stderr?.pipe(backendLog);
  backendProcess.on('error', (error) => {
    appendDesktopLog(`Backend process failed to start: ${error.message}`);
    desktopRuntimeState.lastBackendError = error.message;
    desktopRuntimeState.backendSource = 'unavailable';
    desktopRuntimeState.backendStartedByElectron = false;
    desktopRuntimeState.backendPid = null;
    backendStartedByElectron = false;
    backendProcess = null;
  });
  backendProcess.on('exit', (code, signal) => {
    appendDesktopLog(`Backend process exited code=${code} signal=${signal}`);
    desktopRuntimeState.backendPid = null;
    if (backendStartedByElectron && !backendStopping) {
      desktopRuntimeState.lastBackendError = `Backend process exited code=${code} signal=${signal}`;
    }
    desktopRuntimeState.backendStartedByElectron = false;
    backendStartedByElectron = false;
    backendStopping = false;
    backendProcess = null;
  });
  appendDesktopLog(`Backend process started by Electron source=${launch.source} pid=${backendProcess.pid}`);
}

async function prepareBackendRuntime() {
  const existingHealth = await backendHealth();
  if (existingHealth.ok) {
    desktopRuntimeState.backendSource = 'already-running';
    desktopRuntimeState.backendStartedByElectron = false;
    desktopRuntimeState.backendPid = null;
    appendDesktopLog(`Backend already online at ${HEALTH_URL}.`);
    return existingHealth;
  }

  if (existingHealth.statusCode) {
    appendDesktopLog(`Backend port responded without a valid health payload. status=${existingHealth.statusCode} error=${existingHealth.error || 'none'}`);
  } else {
    appendDesktopLog(`Backend health unavailable before startup. error=${existingHealth.error || 'connection unavailable'}`);
  }

  if (!SHOULD_START_BACKEND) {
    desktopRuntimeState.backendSource = 'unavailable';
    desktopRuntimeState.lastBackendError = existingHealth.error || 'Backend is offline and autostart is disabled.';
    appendDesktopLog('Backend autostart remains disabled; user must start FastAPI separately.');
    return existingHealth;
  }

  startBackendProcess();
  const startedHealth = await waitForBackendHealth();
  if (startedHealth.ok) {
    appendDesktopLog(`Backend health OK after autostart at ${HEALTH_URL}.`);
  } else {
    desktopRuntimeState.lastBackendError = startedHealth.error || 'Backend health timeout after autostart.';
    appendDesktopLog(`Backend autostart did not reach health OK. error=${startedHealth.error || 'unknown'}`);
  }
  return startedHealth;
}

function stopBackendProcess() {
  if (!backendProcess || !backendStartedByElectron) return;
  backendStopping = true;
  if (process.platform === 'win32' && backendProcess.pid) {
    spawnSync('taskkill', ['/PID', String(backendProcess.pid), '/T', '/F'], { windowsHide: true });
  } else {
    backendProcess.kill();
  }
  backendProcess = null;
  backendStartedByElectron = false;
  desktopRuntimeState.backendStartedByElectron = false;
  desktopRuntimeState.backendPid = null;
  appendDesktopLog('Backend process stopped.');
}

async function desktopRuntimeStatus() {
  const health = await backendHealth();
  return {
    ...desktopRuntimeState,
    backendOnline: health.ok,
    healthStatusCode: health.statusCode,
    healthOk: health.ok,
    mode: process.env.AT_DESKTOP_MODE === 'production' ? 'production' : 'development',
  };
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
  try {
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
  } catch (error) {
    appendDesktopLog(`Frontend load failed: ${error.message}`);
  }
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
ipcMain.handle('desktop:runtime', desktopRuntimeStatus);
