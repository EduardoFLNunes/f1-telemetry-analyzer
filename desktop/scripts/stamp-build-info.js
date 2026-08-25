/**
 * Records which commit this build came from, so the app can say it later.
 *
 * Runs before the installer is assembled. The file lands next to `main.js` and
 * travels inside the asar, which is what makes it trustworthy: it cannot drift
 * from the code it was stamped alongside.
 *
 * A build from a dirty tree says so. "Three commits behind" is a useful number;
 * "three commits behind, plus whatever was uncommitted at build time" is the
 * honest version of it.
 */

const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const DESKTOP_DIR = path.resolve(__dirname, '..');
const REPO_ROOT = path.resolve(DESKTOP_DIR, '..');

function git(args, fallback = null) {
  try {
    return String(execFileSync('git', args, { cwd: REPO_ROOT, windowsHide: true })).trim();
  } catch {
    return fallback;
  }
}

function main() {
  const pkg = JSON.parse(fs.readFileSync(path.join(DESKTOP_DIR, 'package.json'), 'utf8'));
  const commit = git(['rev-parse', 'HEAD']);
  const status = git(['status', '--porcelain'], '');

  const info = {
    version: pkg.version,
    commit,
    shortCommit: commit ? commit.slice(0, 7) : null,
    branch: git(['rev-parse', '--abbrev-ref', 'HEAD']),
    committedAt: git(['log', '-1', '--format=%cI']),
    subject: git(['log', '-1', '--format=%s']),
    dirty: status === null ? null : status.length > 0,
    builtAt: new Date().toISOString(),
    stamped: true,
  };

  const destination = path.join(DESKTOP_DIR, 'build-info.json');
  fs.writeFileSync(destination, JSON.stringify(info, null, 2) + '\n', 'utf8');

  const dirtyNote = info.dirty ? ' (arvore suja)' : '';
  console.log(`build-info: ${info.version} @ ${info.shortCommit || 'sem git'}${dirtyNote}`);
}

main();
