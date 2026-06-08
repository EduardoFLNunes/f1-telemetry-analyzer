const { spawn } = require('node:child_process');
const path = require('node:path');
const electronPath = require('electron');

const desktopRoot = path.resolve(__dirname, '..');
const args = new Set(process.argv.slice(2));
const mode = args.has('--production') ? 'production' : 'development';
const autostart = args.has('--autostart');

const child = spawn(electronPath, ['.'], {
  cwd: desktopRoot,
  stdio: 'inherit',
  env: {
    ...process.env,
    AT_DESKTOP_MODE: mode,
    AT_DESKTOP_AUTOSTART_BACKEND: autostart ? 'true' : process.env.AT_DESKTOP_AUTOSTART_BACKEND,
    DESKTOP_AUTOSTART_BACKEND: autostart ? 'true' : process.env.DESKTOP_AUTOSTART_BACKEND,
  },
});

child.on('exit', (code) => {
  process.exit(code ?? 0);
});

child.on('error', (error) => {
  console.error(error.message);
  process.exit(1);
});
