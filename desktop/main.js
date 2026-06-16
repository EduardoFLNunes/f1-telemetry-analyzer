const { app, BrowserWindow, ipcMain, shell, dialog, clipboard } = require('electron');
const { spawn, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const http = require('node:http');
const https = require('node:https');
const path = require('node:path');

const APP_ROOT = app.isPackaged ? path.dirname(process.execPath) : path.resolve(__dirname, '..');
const REPO_ROOT = path.resolve(__dirname, '..');
const REPO_FRONTEND_DIST = path.join(REPO_ROOT, 'frontend', 'dist', 'index.html');
const DEFAULT_FRONTEND_DEV_URL = 'http://127.0.0.1:5173';
const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8000';
const BACKEND_EXE_NAME = process.platform === 'win32' ? 'automobilista-backend.exe' : 'automobilista-backend';
const EXPECTED_BACKEND_SERVICE = 'automobilista-telemetria-backend';
const EXPECTED_BACKEND_VERSION = 'phase-14.2-real-session-assisted-validation';
const WINDOW_ICON_NAME = process.platform === 'win32' ? 'icon.ico' : 'icon.png';
const ASSETTO_PLUGIN_ID = 'ac_opponents_exporter';
const ASSETTO_PLUGIN_DISPLAY_NAME = 'Opponents Exporter';
const ASSETTO_PLUGIN_FILE = 'ac_opponents_exporter.py';
const ASSETTO_CONFIG_FILE = 'assetto-corsa-setup.json';
const UDP_OPPONENTS_HOST = process.env.AT_UDP_OPPONENTS_HOST || '127.0.0.1';
const UDP_OPPONENTS_PORT = Number(process.env.AT_UDP_OPPONENTS_PORT || 8765);
const DESKTOP_BRANCH_NAME = process.env.AT_DESKTOP_BRANCH_NAME || 'feature/phase-14-2-real-session-assisted-validation';
const DESKTOP_WINDOW_TITLE = `Automobilista Telemetria - ${DESKTOP_BRANCH_NAME}`;

const FRONTEND_URL = process.env.AT_DESKTOP_FRONTEND_URL || DEFAULT_FRONTEND_DEV_URL;
const BACKEND_URL = stripTrailingSlash(process.env.AT_BACKEND_URL || DEFAULT_BACKEND_URL);
const HEALTH_URL = process.env.AT_BACKEND_HEALTH_URL || `${BACKEND_URL}/api/health`;
const BACKEND_HOST = backendHostFromUrl(BACKEND_URL);
const BACKEND_PORT = backendPortFromUrl(BACKEND_URL);
const SHOULD_START_BACKEND = !flagEnabled(process.env.AT_DESKTOP_DISABLE_BACKEND_AUTOSTART)
  && (
    app.isPackaged
    || flagEnabled(process.env.AT_DESKTOP_AUTOSTART_BACKEND)
    || flagEnabled(process.env.AT_DESKTOP_START_BACKEND)
    || flagEnabled(process.env.DESKTOP_AUTOSTART_BACKEND)
  );
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
  backendStartedAt: null,
  backendStatus: 'offline',
  backendStatusMessage: 'Backend ainda nao verificado.',
  backendPort: BACKEND_PORT,
  apiBaseUrl: BACKEND_URL,
  healthUrl: HEALTH_URL,
  portConflict: false,
  portConflictMessage: null,
  lastBackendError: null,
  lastBackendExitCode: null,
  lastBackendExitSignal: null,
  lastHealth: null,
  lastCheckedAt: null,
  frontendIndexPath: null,
  backendResourceRoot: null,
  backendRuntimeRoot: null,
  logsDir: null,
};

function resolveBackendResourceRoot() {
  const configured = resolveMaybeRelativePath(process.env.AT_BACKEND_RESOURCE_ROOT);
  if (configured) return configured;
  if (app.isPackaged && process.resourcesPath) return process.resourcesPath;
  return REPO_ROOT;
}

function resolveBackendRuntimeRoot() {
  const configured = resolveMaybeRelativePath(process.env.AT_BACKEND_RUNTIME_ROOT);
  if (configured) return configured;
  if (app.isPackaged) return app.getPath('userData');
  return REPO_ROOT;
}

function resolveLogsDir() {
  const configured = resolveMaybeRelativePath(process.env.AT_DESKTOP_LOG_DIR);
  if (configured) return configured;
  if (app.isPackaged) return path.join(app.getPath('userData'), 'logs');
  return path.join(REPO_ROOT, 'logs');
}

function resolveWindowIconPath() {
  const iconPath = path.join(__dirname, 'assets', WINDOW_ICON_NAME);
  return fs.existsSync(iconPath) ? iconPath : null;
}

function ensureLogsDir() {
  const logsDir = resolveLogsDir();
  fs.mkdirSync(logsDir, { recursive: true });
  desktopRuntimeState.logsDir = logsDir;
  return logsDir;
}

function safeExists(targetPath) {
  try {
    return Boolean(targetPath && fs.existsSync(targetPath));
  } catch {
    return false;
  }
}

function safeIsDirectory(targetPath) {
  try {
    return Boolean(targetPath && fs.statSync(targetPath).isDirectory());
  } catch {
    return false;
  }
}

function normalizeAssettoPath(targetPath) {
  if (!targetPath) return null;
  return path.resolve(String(targetPath));
}

function assettoConfidence(candidate) {
  if (candidate.exists && candidate.hasAssettoExecutable && candidate.hasAppsPythonFolder) return 'HIGH';
  if (candidate.exists && (candidate.hasAssettoExecutable || candidate.hasAppsPythonFolder)) return 'MEDIUM';
  return 'LOW';
}

function inspectAssettoCandidate(candidatePath, source = 'unknown') {
  const resolvedPath = normalizeAssettoPath(candidatePath);
  const exists = safeIsDirectory(resolvedPath);
  const hasAssettoExecutable = exists && safeExists(path.join(resolvedPath, 'acs.exe'));
  const hasAppsPythonFolder = exists && safeIsDirectory(path.join(resolvedPath, 'apps', 'python'));
  const candidate = {
    path: resolvedPath,
    exists,
    hasAssettoExecutable,
    hasAppsPythonFolder,
    confidence: 'LOW',
    source,
  };
  candidate.confidence = assettoConfidence(candidate);
  return candidate;
}

function uniquePaths(pathsWithSource) {
  const unique = new Map();
  for (const item of pathsWithSource) {
    const candidatePath = normalizeAssettoPath(item.path);
    if (!candidatePath) continue;
    const key = candidatePath.toLowerCase();
    if (!unique.has(key)) {
      unique.set(key, { path: candidatePath, source: item.source || 'unknown' });
    }
  }
  return [...unique.values()];
}

function assettoConfigPath() {
  return path.join(app.getPath('userData'), ASSETTO_CONFIG_FILE);
}

function readAssettoConfig() {
  try {
    const configPath = assettoConfigPath();
    if (!safeExists(configPath)) return {};
    return JSON.parse(fs.readFileSync(configPath, 'utf8'));
  } catch (error) {
    appendDesktopLog(`Assetto setup config read failed: ${error.message}`);
    return {};
  }
}

function writeAssettoConfig(config) {
  const configPath = assettoConfigPath();
  fs.mkdirSync(path.dirname(configPath), { recursive: true });
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf8');
}

function parseSteamInstallPath(regOutput) {
  const match = String(regOutput || '').match(/InstallPath\s+REG_\w+\s+(.+)/i);
  return match ? match[1].trim() : null;
}

function steamRootsFromRegistry() {
  if (process.platform !== 'win32') return [];
  const keys = [
    'HKLM\\SOFTWARE\\WOW6432Node\\Valve\\Steam',
    'HKLM\\SOFTWARE\\Valve\\Steam',
    'HKCU\\SOFTWARE\\Valve\\Steam',
  ];
  const roots = [];
  for (const key of keys) {
    const result = spawnSync('reg.exe', ['query', key, '/v', 'InstallPath'], {
      encoding: 'utf8',
      windowsHide: true,
    });
    if (result.status === 0) {
      const installPath = parseSteamInstallPath(result.stdout);
      if (installPath) roots.push(installPath);
    }
  }
  return roots;
}

function parseSteamLibraryFolders(vdfPath) {
  if (!safeExists(vdfPath)) return [];
  try {
    const content = fs.readFileSync(vdfPath, 'utf8');
    const libraries = [];
    const pattern = /"(?:path|\d+)"\s+"([^"]+)"/gi;
    let match = pattern.exec(content);
    while (match) {
      const libraryPath = match[1].replace(/\\\\/g, '\\');
      if (/^[a-z]:\\/i.test(libraryPath) || libraryPath.startsWith('\\\\')) {
        libraries.push(libraryPath);
      }
      match = pattern.exec(content);
    }
    return libraries;
  } catch (error) {
    appendDesktopLog(`Steam library parse failed: ${error.message}`);
    return [];
  }
}

function assettoPathFromSteamRoot(steamRoot) {
  return path.join(steamRoot, 'steamapps', 'common', 'assettocorsa');
}

function assettoCandidatesFromSteam() {
  const candidates = [];
  const steamRoots = steamRootsFromRegistry();
  for (const steamRoot of steamRoots) {
    candidates.push({ path: assettoPathFromSteamRoot(steamRoot), source: 'steam-default' });
    const libraryFile = path.join(steamRoot, 'steamapps', 'libraryfolders.vdf');
    for (const libraryRoot of parseSteamLibraryFolders(libraryFile)) {
      candidates.push({ path: assettoPathFromSteamRoot(libraryRoot), source: 'steam-library' });
    }
  }
  return candidates;
}

function assettoDefaultCandidates() {
  return [
    { path: 'C:\\Program Files (x86)\\Steam\\steamapps\\common\\assettocorsa', source: 'steam-default' },
    { path: 'C:\\Program Files\\Steam\\steamapps\\common\\assettocorsa', source: 'steam-default' },
    { path: 'D:\\SteamLibrary\\steamapps\\common\\assettocorsa', source: 'steam-library' },
    { path: 'D:\\Steam\\steamapps\\common\\assettocorsa', source: 'steam-library' },
    { path: 'E:\\SteamLibrary\\steamapps\\common\\assettocorsa', source: 'steam-library' },
    { path: 'E:\\Steam\\steamapps\\common\\assettocorsa', source: 'steam-library' },
  ];
}

async function detectAssettoCorsaInstallPaths() {
  const config = readAssettoConfig();
  const candidates = [];
  const envRoot = process.env.ASSETTO_CORSA_ROOT || process.env.AT_ASSETTO_CORSA_ROOT;
  if (envRoot) candidates.push({ path: envRoot, source: 'manual' });
  if (config.selectedPath) candidates.push({ path: config.selectedPath, source: 'manual' });
  candidates.push(...assettoCandidatesFromSteam());
  candidates.push(...assettoDefaultCandidates());

  const inspected = uniquePaths(candidates)
    .map((candidate) => inspectAssettoCandidate(candidate.path, candidate.source))
    .sort((left, right) => {
      const rank = { HIGH: 0, MEDIUM: 1, LOW: 2 };
      return rank[left.confidence] - rank[right.confidence];
    });
  const selected = inspected.find((candidate) => ['HIGH', 'MEDIUM'].includes(candidate.confidence));
  return {
    candidates: inspected,
    selectedPath: selected ? selected.path : null,
  };
}

function resolveAssettoExporterSourceDir() {
  const candidates = [
    path.join(resolveBackendResourceRoot(), 'assetto_plugin', ASSETTO_PLUGIN_ID),
    process.resourcesPath ? path.join(process.resourcesPath, 'assetto_plugin', ASSETTO_PLUGIN_ID) : null,
    path.join(__dirname, 'resources', 'assetto_plugin', ASSETTO_PLUGIN_ID),
    path.join(REPO_ROOT, 'tools', 'assetto_opponents_exporter'),
  ].filter(Boolean);
  return candidates.find((candidate) => safeExists(path.join(candidate, ASSETTO_PLUGIN_FILE))) || null;
}

function assettoSetupInstructions(gamePath, expectedPluginDir) {
  const destination = expectedPluginDir || '<Assetto Corsa>\\apps\\python\\ac_opponents_exporter';
  return [
    'Automobilista Telemetria - Assetto Corsa setup',
    '',
    `1. Confirm the Assetto Corsa folder: ${gamePath || '<not detected>'}`,
    `2. Copy the exporter folder to: ${destination}`,
    `3. The required file is: ${ASSETTO_PLUGIN_FILE}`,
    '4. Open Assetto Corsa or Content Manager.',
    `5. Enable the Python app/module named ${ASSETTO_PLUGIN_ID} or ${ASSETTO_PLUGIN_DISPLAY_NAME}.`,
    `6. Start a session and open ${ASSETTO_PLUGIN_DISPLAY_NAME} from the in-game app bar.`,
    `7. Keep Automobilista Telemetria running. Opponents are sent to UDP ${UDP_OPPONENTS_HOST}:${UDP_OPPONENTS_PORT}.`,
    '',
    'Player telemetry uses Assetto Corsa shared memory and does not require this opponents exporter.',
  ].join('\n');
}

async function getAssettoPluginStatus() {
  const detection = await detectAssettoCorsaInstallPaths();
  const gamePath = detection.selectedPath;
  const expectedPluginDir = gamePath ? path.join(gamePath, 'apps', 'python', ASSETTO_PLUGIN_ID) : null;
  const requiredTarget = expectedPluginDir ? path.join(expectedPluginDir, ASSETTO_PLUGIN_FILE) : null;
  const installed = Boolean(requiredTarget && safeExists(requiredTarget));
  const sourceDir = resolveAssettoExporterSourceDir();
  const sourceFiles = sourceDir ? [
    { name: ASSETTO_PLUGIN_FILE, path: path.join(sourceDir, ASSETTO_PLUGIN_FILE), required: true, exists: safeExists(path.join(sourceDir, ASSETTO_PLUGIN_FILE)) },
    { name: 'icon.png', path: path.join(sourceDir, 'icon.png'), required: false, exists: safeExists(path.join(sourceDir, 'icon.png')) },
  ] : [];
  const targetFiles = expectedPluginDir ? [
    { name: ASSETTO_PLUGIN_FILE, path: requiredTarget, required: true, exists: installed },
    { name: 'icon.png', path: path.join(expectedPluginDir, 'icon.png'), required: false, exists: safeExists(path.join(expectedPluginDir, 'icon.png')) },
    { name: 'stdlib\\_ctypes.pyd', path: path.join(expectedPluginDir, 'stdlib', '_ctypes.pyd'), required: false, exists: safeExists(path.join(expectedPluginDir, 'stdlib', '_ctypes.pyd')) },
    { name: 'stdlib64\\_ctypes.pyd', path: path.join(expectedPluginDir, 'stdlib64', '_ctypes.pyd'), required: false, exists: safeExists(path.join(expectedPluginDir, 'stdlib64', '_ctypes.pyd')) },
  ] : [];

  return {
    assetto: detection,
    gamePath,
    pluginId: ASSETTO_PLUGIN_ID,
    pluginName: ASSETTO_PLUGIN_DISPLAY_NAME,
    status: gamePath ? (installed ? 'installed' : 'not-installed') : 'unknown',
    installed,
    expectedPluginDir,
    targetFiles,
    source: {
      available: Boolean(sourceDir),
      path: sourceDir,
      files: sourceFiles,
    },
    canInstall: Boolean(gamePath && sourceDir),
    transport: {
      playerTelemetry: 'assetto-corsa-shared-memory',
      opponents: 'udp',
      host: UDP_OPPONENTS_HOST,
      backendApiPort: BACKEND_PORT,
      udpOpponentsPort: UDP_OPPONENTS_PORT,
      websocketPath: '/ws',
    },
    instructions: assettoSetupInstructions(gamePath, expectedPluginDir),
  };
}

async function openAssettoFolderPicker() {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'Select Assetto Corsa folder',
    properties: ['openDirectory', 'dontAddToRecent'],
  });
  if (result.canceled || !result.filePaths?.[0]) {
    return { ok: false, canceled: true, detection: await detectAssettoCorsaInstallPaths() };
  }

  const selectedPath = normalizeAssettoPath(result.filePaths[0]);
  const candidate = inspectAssettoCandidate(selectedPath, 'manual');
  writeAssettoConfig({
    selectedPath,
    updatedAt: new Date().toISOString(),
    confidence: candidate.confidence,
  });
  appendDesktopLog(`Assetto Corsa manual path selected: ${selectedPath} confidence=${candidate.confidence}`);
  return { ok: true, canceled: false, candidate, detection: await detectAssettoCorsaInstallPaths() };
}

async function openAssettoFolder(requestedPath) {
  const detection = await detectAssettoCorsaInstallPaths();
  const targetPath = normalizeAssettoPath(requestedPath || detection.selectedPath);
  const allowed = detection.candidates.some((candidate) => samePath(candidate.path, targetPath));
  if (!targetPath || !allowed || !safeIsDirectory(targetPath)) {
    return { ok: false, path: targetPath, error: 'Assetto Corsa folder is not a detected candidate.' };
  }
  const error = await shell.openPath(targetPath);
  if (error) return { ok: false, path: targetPath, error };
  appendDesktopLog(`Opened Assetto Corsa directory: ${targetPath}`);
  return { ok: true, path: targetPath, error: null };
}

async function copyAssettoSetupInstructions() {
  const status = await getAssettoPluginStatus();
  clipboard.writeText(status.instructions);
  return { ok: true, length: status.instructions.length };
}

function setBackendStatus(status, message, extra = {}) {
  desktopRuntimeState.backendStatus = status;
  desktopRuntimeState.backendStatusMessage = message;
  if (Object.prototype.hasOwnProperty.call(extra, 'lastBackendError')) {
    desktopRuntimeState.lastBackendError = extra.lastBackendError;
  }
  if (Object.prototype.hasOwnProperty.call(extra, 'portConflict')) {
    desktopRuntimeState.portConflict = Boolean(extra.portConflict);
  }
  if (Object.prototype.hasOwnProperty.call(extra, 'portConflictMessage')) {
    desktopRuntimeState.portConflictMessage = extra.portConflictMessage;
  }
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

function frontendIndexCandidates() {
  const candidates = [];
  if (app.isPackaged && process.resourcesPath) {
    candidates.push(path.join(process.resourcesPath, 'frontend', 'index.html'));
  }
  candidates.push(path.join(__dirname, 'resources', 'frontend', 'index.html'));
  candidates.push(REPO_FRONTEND_DIST);
  return candidates;
}

function resolveFrontendIndexPath() {
  return frontendIndexCandidates().find((candidate) => fs.existsSync(candidate)) || null;
}

function packagedResourceBackendPath() {
  return path.join(resolveBackendResourceRoot(), 'backend', BACKEND_EXE_NAME);
}

function samePath(left, right) {
  if (!left || !right) return false;
  return path.resolve(left).toLowerCase() === path.resolve(right).toLowerCase();
}

function packagedBackendCandidates() {
  const candidates = [];
  const configured = resolveMaybeRelativePath(process.env.AT_BACKEND_EXE_PATH);
  if (configured) candidates.push(configured);

  candidates.push(packagedResourceBackendPath());
  candidates.push(path.join(__dirname, 'resources', 'backend', BACKEND_EXE_NAME));
  candidates.push(path.join(REPO_ROOT, 'backend', 'dist', BACKEND_EXE_NAME));
  candidates.push(path.join(REPO_ROOT, 'dist', BACKEND_EXE_NAME));
  return candidates;
}

function resolvePythonRunnerLaunch() {
  const usePythonRunner = flagEnabled(process.env.AT_BACKEND_USE_PYTHON_RUNNER)
    || String(process.env.AT_BACKEND_RUNNER || '').trim().toLowerCase() === 'python';
  if (!usePythonRunner) return null;

  const pythonPath = resolveMaybeRelativePath(process.env.AT_BACKEND_PYTHON)
    || path.join(REPO_ROOT, '.venv', process.platform === 'win32' ? 'Scripts' : 'bin', process.platform === 'win32' ? 'python.exe' : 'python');
  const runnerPath = resolveMaybeRelativePath(process.env.AT_BACKEND_RUNNER_PATH)
    || path.join(REPO_ROOT, 'backend', 'desktop_backend_runner.py');

  if (!fs.existsSync(pythonPath)) {
    return { error: `Python runner requested but Python was not found: ${pythonPath}`, status: 'executable-not-found' };
  }
  if (!fs.existsSync(runnerPath)) {
    return { error: `Python runner requested but runner was not found: ${runnerPath}`, status: 'executable-not-found' };
  }

  return {
    source: 'python-runner',
    command: pythonPath,
    args: [runnerPath],
    cwd: REPO_ROOT,
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
      source: samePath(executablePath, packagedResourceBackendPath()) ? 'packaged-resource' : 'packaged-exe',
      command: executablePath,
      args: [],
      cwd: APP_ROOT,
      executablePath,
      useShell: false,
    };
  }

  const configuredPath = resolveMaybeRelativePath(process.env.AT_BACKEND_EXE_PATH);
  const searched = configuredPath || candidates.join('; ');
  return { error: `Backend executable not found. Searched: ${searched}`, status: 'executable-not-found' };
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

function normalizeBackendHealth(response) {
  const service = response?.data?.service || null;
  const status = response?.data?.status || null;
  const version = response?.data?.version || null;
  const expectedService = service === EXPECTED_BACKEND_SERVICE && status === 'ok';
  const expectedVersion = version === EXPECTED_BACKEND_VERSION;
  const reachable = Boolean(response?.statusCode);
  const portMessage = expectedService
    ? `Porta ${BACKEND_PORT} respondeu com backend ${version || 'sem versao'}, mas esta build exige ${EXPECTED_BACKEND_VERSION}.`
    : `Porta ${BACKEND_PORT} respondeu, mas nao parece ser o backend ${EXPECTED_BACKEND_SERVICE}.`;
  return {
    ...response,
    ok: Boolean(response?.ok && expectedService && expectedVersion),
    reachable,
    expectedService,
    expectedVersion,
    service,
    version,
    error: response?.ok && (!expectedService || !expectedVersion) ? portMessage : response?.error,
  };
}

function healthLooksLikePortConflict(health) {
  return Boolean(health && !health.ok && (health.reachable || health.statusCode));
}

async function backendHealth() {
  try {
    const health = normalizeBackendHealth(await requestJson(HEALTH_URL));
    desktopRuntimeState.lastHealth = health;
    desktopRuntimeState.lastCheckedAt = new Date().toISOString();
    if (health.ok) {
      desktopRuntimeState.lastBackendError = null;
      desktopRuntimeState.portConflict = false;
      desktopRuntimeState.portConflictMessage = null;
    }
    return health;
  } catch (error) {
    const health = {
      ok: false,
      reachable: false,
      expectedService: false,
      service: null,
      statusCode: null,
      error: error.message,
    };
    desktopRuntimeState.lastHealth = health;
    desktopRuntimeState.lastCheckedAt = new Date().toISOString();
    return health;
  }
}

async function waitForBackendHealth(timeoutMs = 60000, intervalMs = 500) {
  const startedAt = Date.now();
  let lastHealth = null;
  while (Date.now() - startedAt < timeoutMs) {
    lastHealth = await backendHealth();
    if (lastHealth.ok) return lastHealth;
    await sleep(intervalMs);
  }
  return {
    ok: false,
    reachable: lastHealth?.reachable ?? false,
    expectedService: lastHealth?.expectedService ?? false,
    statusCode: lastHealth?.statusCode ?? null,
    error: lastHealth?.error || `Backend health did not become ready within ${timeoutMs}ms`,
  };
}

function startBackendProcess() {
  if (!SHOULD_START_BACKEND) {
    setBackendStatus('offline', 'Backend autostart desativado.', { lastBackendError: 'Backend autostart disabled.' });
    appendDesktopLog('Backend autostart disabled.');
    return false;
  }
  if (backendProcess) return true;

  const launch = resolveBackendLaunch();
  if (!launch || launch.error) {
    desktopRuntimeState.backendSource = 'unavailable';
    const status = launch?.status || 'offline';
    const message = launch?.error || 'Backend launch configuration is unavailable.';
    setBackendStatus(status, message, { lastBackendError: message, portConflict: false, portConflictMessage: null });
    appendDesktopLog(desktopRuntimeState.lastBackendError);
    return false;
  }

  const logsDir = ensureLogsDir();
  const backendResourceRoot = resolveBackendResourceRoot();
  const backendRuntimeRoot = resolveBackendRuntimeRoot();
  const backendLog = fs.createWriteStream(path.join(logsDir, 'backend.log'), { flags: 'a' });
  backendLog.write(`\n[${new Date().toISOString()}] Starting ${launch.source}: ${launch.command} ${launch.args.join(' ')}\n`);
  backendProcess = spawn(launch.command, launch.args, {
    cwd: launch.cwd || APP_ROOT,
    shell: Boolean(launch.useShell),
    env: {
      ...process.env,
      AT_BACKEND_HOST: process.env.AT_BACKEND_HOST || BACKEND_HOST,
      AT_BACKEND_PORT: process.env.AT_BACKEND_PORT || String(BACKEND_PORT),
      AT_BACKEND_RESOURCE_ROOT: process.env.AT_BACKEND_RESOURCE_ROOT || backendResourceRoot,
      AT_BACKEND_RUNTIME_ROOT: process.env.AT_BACKEND_RUNTIME_ROOT || backendRuntimeRoot,
      AT_BACKEND_REPO_ROOT: process.env.AT_BACKEND_REPO_ROOT || backendResourceRoot,
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
  desktopRuntimeState.backendStartedAt = new Date().toISOString();
  desktopRuntimeState.backendResourceRoot = backendResourceRoot;
  desktopRuntimeState.backendRuntimeRoot = backendRuntimeRoot;
  desktopRuntimeState.logsDir = logsDir;
  desktopRuntimeState.lastBackendExitCode = null;
  desktopRuntimeState.lastBackendExitSignal = null;
  desktopRuntimeState.lastBackendError = null;
  setBackendStatus('starting', 'Backend empacotado iniciando.', { portConflict: false, portConflictMessage: null });

  backendProcess.stdout?.pipe(backendLog);
  backendProcess.stderr?.pipe(backendLog);
  backendProcess.on('error', (error) => {
    appendDesktopLog(`Backend process failed to start: ${error.message}`);
    setBackendStatus('crashed', `Backend falhou ao iniciar: ${error.message}`, { lastBackendError: error.message });
    desktopRuntimeState.backendSource = 'unavailable';
    desktopRuntimeState.backendStartedByElectron = false;
    desktopRuntimeState.backendPid = null;
    desktopRuntimeState.backendStartedAt = null;
    backendStartedByElectron = false;
    backendProcess = null;
  });
  backendProcess.on('exit', (code, signal) => {
    appendDesktopLog(`Backend process exited code=${code} signal=${signal}`);
    desktopRuntimeState.backendPid = null;
    desktopRuntimeState.lastBackendExitCode = code;
    desktopRuntimeState.lastBackendExitSignal = signal;
    if (backendStartedByElectron && !backendStopping) {
      const message = `Backend process exited code=${code} signal=${signal}`;
      setBackendStatus('crashed', message, { lastBackendError: message });
    } else if (backendStopping) {
      setBackendStatus('offline', 'Backend encerrado junto com o aplicativo.', { lastBackendError: null });
    }
    desktopRuntimeState.backendStartedByElectron = false;
    desktopRuntimeState.backendStartedAt = null;
    backendStartedByElectron = false;
    backendStopping = false;
    backendProcess = null;
  });
  appendDesktopLog(`Backend process started by Electron source=${launch.source} pid=${backendProcess.pid}`);
  return true;
}

async function prepareBackendRuntime() {
  const existingHealth = await backendHealth();
  if (existingHealth.ok) {
    desktopRuntimeState.backendSource = 'already-running';
    desktopRuntimeState.backendStartedByElectron = false;
    desktopRuntimeState.backendPid = null;
    setBackendStatus('already-running', `Backend valido ja esta online em ${HEALTH_URL}.`, { portConflict: false, portConflictMessage: null });
    appendDesktopLog(`Backend already online at ${HEALTH_URL}.`);
    return existingHealth;
  }

  if (healthLooksLikePortConflict(existingHealth)) {
    const message = existingHealth.error || `Porta ${BACKEND_PORT} ocupada por processo desconhecido.`;
    desktopRuntimeState.backendSource = 'unavailable';
    desktopRuntimeState.backendStartedByElectron = false;
    desktopRuntimeState.backendPid = null;
    setBackendStatus('port-conflict', message, {
      lastBackendError: message,
      portConflict: true,
      portConflictMessage: message,
    });
    appendDesktopLog(`Backend port conflict before startup. status=${existingHealth.statusCode || 'none'} error=${message}`);
    return existingHealth;
  }

  appendDesktopLog(`Backend health unavailable before startup. error=${existingHealth.error || 'connection unavailable'}`);

  if (!SHOULD_START_BACKEND) {
    desktopRuntimeState.backendSource = 'unavailable';
    const message = existingHealth.error || 'Backend is offline and autostart is disabled.';
    setBackendStatus('offline', message, { lastBackendError: message, portConflict: false, portConflictMessage: null });
    appendDesktopLog('Backend autostart remains disabled; user must start FastAPI separately.');
    return existingHealth;
  }

  const launched = startBackendProcess();
  if (!launched) return existingHealth;
  const startedHealth = await waitForBackendHealth();
  if (startedHealth.ok) {
    setBackendStatus('online', `Backend respondeu ao health check em ${HEALTH_URL}.`, { portConflict: false, portConflictMessage: null });
    appendDesktopLog(`Backend health OK after autostart at ${HEALTH_URL}.`);
  } else if (healthLooksLikePortConflict(startedHealth)) {
    const message = startedHealth.error || `Porta ${BACKEND_PORT} ocupada por processo desconhecido.`;
    setBackendStatus('port-conflict', message, {
      lastBackendError: message,
      portConflict: true,
      portConflictMessage: message,
    });
    appendDesktopLog(`Backend autostart hit a port conflict. error=${message}`);
  } else {
    const message = startedHealth.error || 'Backend health timeout after autostart.';
    setBackendStatus('health-timeout', message, { lastBackendError: message, portConflict: false, portConflictMessage: null });
    appendDesktopLog(`Backend autostart did not reach health OK. error=${startedHealth.error || 'unknown'}`);
  }
  return startedHealth;
}

function stopStartedBackendChildren() {
  if (process.platform !== 'win32') return;
  const executablePath = desktopRuntimeState.backendExecutablePath;
  const startedAt = desktopRuntimeState.backendStartedAt;
  if (!executablePath || !startedAt) return;

  const command = [
    '$exe=$env:AT_BACKEND_STOP_EXE;',
    '$cutoff=[datetime]$env:AT_BACKEND_STOP_CUTOFF;',
    "Get-CimInstance Win32_Process -Filter \"Name = 'automobilista-backend.exe'\"",
    '| Where-Object { $_.ExecutablePath -eq $exe -and $_.CreationDate -ge $cutoff }',
    '| ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }',
  ].join(' ');
  const result = spawnSync('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', command], {
    windowsHide: true,
    env: {
      ...process.env,
      AT_BACKEND_STOP_EXE: executablePath,
      AT_BACKEND_STOP_CUTOFF: new Date(Date.parse(startedAt) - 5000).toISOString(),
    },
  });
  if (result.status && result.status !== 0) {
    appendDesktopLog(`Backend child cleanup failed: ${String(result.stderr || result.error || result.status)}`);
  }
}

function stopBackendProcess() {
  if (!backendProcess || !backendStartedByElectron) return;
  backendStopping = true;
  if (process.platform === 'win32' && backendProcess.pid) {
    spawnSync('taskkill', ['/PID', String(backendProcess.pid), '/T', '/F'], { windowsHide: true });
    stopStartedBackendChildren();
  } else {
    backendProcess.kill();
  }
  backendProcess = null;
  backendStartedByElectron = false;
  desktopRuntimeState.backendStartedByElectron = false;
  desktopRuntimeState.backendPid = null;
  desktopRuntimeState.backendStartedAt = null;
  setBackendStatus('offline', 'Backend encerrado junto com o aplicativo.', { portConflict: false, portConflictMessage: null });
  appendDesktopLog('Backend process stopped.');
}

function refreshBackendStatusFromHealth(health) {
  if (health.ok) {
    const onlineStatus = desktopRuntimeState.backendSource === 'already-running' ? 'already-running' : 'online';
    const message = onlineStatus === 'already-running'
      ? `Backend valido ja esta online em ${HEALTH_URL}.`
      : `Backend online em ${HEALTH_URL}.`;
    setBackendStatus(onlineStatus, message, { portConflict: false, portConflictMessage: null, lastBackendError: null });
    return;
  }

  if (healthLooksLikePortConflict(health)) {
    const message = health.error || `Porta ${BACKEND_PORT} ocupada por processo desconhecido.`;
    setBackendStatus('port-conflict', message, {
      lastBackendError: message,
      portConflict: true,
      portConflictMessage: message,
    });
    return;
  }

  if (desktopRuntimeState.backendStatus === 'starting') return;
  if (['crashed', 'health-timeout', 'executable-not-found'].includes(desktopRuntimeState.backendStatus)) return;

  const message = health.error || 'Backend offline. A API local ainda nao respondeu.';
  setBackendStatus('offline', message, { lastBackendError: message, portConflict: false, portConflictMessage: null });
}

async function desktopRuntimeStatus() {
  const health = await backendHealth();
  refreshBackendStatusFromHealth(health);
  return {
    ...desktopRuntimeState,
    softwareName: DESKTOP_WINDOW_TITLE,
    branchName: DESKTOP_BRANCH_NAME,
    frontendIndexPath: desktopRuntimeState.frontendIndexPath || resolveFrontendIndexPath(),
    backendResourceRoot: desktopRuntimeState.backendResourceRoot || resolveBackendResourceRoot(),
    backendRuntimeRoot: desktopRuntimeState.backendRuntimeRoot || resolveBackendRuntimeRoot(),
    logsDir: desktopRuntimeState.logsDir || resolveLogsDir(),
    backendOnline: health.ok,
    healthStatusCode: health.statusCode,
    healthOk: health.ok,
    mode: app.isPackaged || process.env.AT_DESKTOP_MODE === 'production' ? 'production' : 'development',
    packaged: app.isPackaged,
  };
}

async function openLogsDir() {
  const logsDir = ensureLogsDir();
  const error = await shell.openPath(logsDir);
  if (error) {
    appendDesktopLog(`Failed to open logs directory: ${error}`);
    return { ok: false, path: logsDir, error };
  }
  appendDesktopLog(`Opened logs directory: ${logsDir}`);
  return { ok: true, path: logsDir, error: null };
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 1024,
    minHeight: 640,
    title: DESKTOP_WINDOW_TITLE,
    backgroundColor: '#06060d',
    ...(resolveWindowIconPath() ? { icon: resolveWindowIconPath() } : {}),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  mainWindow.on('page-title-updated', (event) => {
    event.preventDefault();
    mainWindow.setTitle(DESKTOP_WINDOW_TITLE);
  });

  const useDevServer = !app.isPackaged && process.env.AT_DESKTOP_MODE !== 'production';
  try {
    if (useDevServer) {
      appendDesktopLog(`Loading frontend dev server: ${FRONTEND_URL}`);
      await mainWindow.loadURL(FRONTEND_URL);
      return;
    }

    const frontendIndexPath = resolveFrontendIndexPath();
    desktopRuntimeState.frontendIndexPath = frontendIndexPath;
    if (frontendIndexPath) {
      appendDesktopLog(`Loading frontend static build: ${frontendIndexPath}`);
      await mainWindow.loadFile(frontendIndexPath);
      return;
    }

    appendDesktopLog(`Frontend static build is missing. Searched: ${frontendIndexCandidates().join('; ')}. Falling back to dev server URL.`);
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
ipcMain.handle('desktop:open-logs', openLogsDir);
ipcMain.handle('assetto:detect', detectAssettoCorsaInstallPaths);
ipcMain.handle('assetto:plugin-status', getAssettoPluginStatus);
ipcMain.handle('assetto:open-folder-picker', openAssettoFolderPicker);
ipcMain.handle('assetto:open-folder', (_event, requestedPath) => openAssettoFolder(requestedPath));
ipcMain.handle('assetto:copy-instructions', copyAssettoSetupInstructions);
