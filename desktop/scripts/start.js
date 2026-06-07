const { spawn } = require('node:child_process');
const path = require('node:path');
const electronPath = require('electron');

const desktopRoot = path.resolve(__dirname, '..');
const args = new Set(process.argv.slice(2));
const mode = args.has('--production') ? 'production' : 'development';

const child = spawn(electronPath, ['.'], {
  cwd: desktopRoot,
  stdio: 'inherit',
  env: {
    ...process.env,
    AT_DESKTOP_MODE: mode,
  },
});

child.on('exit', (code) => {
  process.exit(code ?? 0);
});

child.on('error', (error) => {
  console.error(error.message);
  process.exit(1);
});
