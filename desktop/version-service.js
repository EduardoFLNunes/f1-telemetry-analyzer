/**
 * What is installed, what the coach is driving against, and how far behind both are.
 *
 * Two things move independently in this project and it is easy to lose track of
 * which one is stale. The app is built from a commit; the racing line the coach
 * uses is produced by an offline search and shipped as a file. Rebuilding the
 * app does not regenerate the line, and regenerating the line does not rebuild
 * the app -- so a single "version" would be a lie about one of them.
 *
 * `build-info.json` is stamped at build time and travels inside the asar. The
 * racing lines are read from the resources folder, where extraResources puts
 * them. The repository, when this machine has one, is the yardstick for both.
 *
 * Everything here degrades to "unknown" rather than throwing: a machine with no
 * git, no repository, or no network still has to show its own versions.
 */

const { execFile } = require('child_process');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const GIT_TIMEOUT_MS = 20000;
const FETCH_TIMEOUT_MS = 60000;

function runGit(args, cwd, timeout = GIT_TIMEOUT_MS) {
  return new Promise((resolve) => {
    execFile('git', args, { cwd, timeout, windowsHide: true }, (error, stdout, stderr) => {
      resolve({
        ok: !error,
        stdout: String(stdout || '').trim(),
        stderr: String(stderr || '').trim(),
        error: error ? String(error.message || error) : null,
      });
    });
  });
}

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch {
    return null;
  }
}

function hashFile(file) {
  try {
    return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').slice(0, 12);
  } catch {
    return null;
  }
}

/** The stamp written by `scripts/stamp-build-info.js` at build time. */
function buildInfo(appRoot, fallbackVersion) {
  const stamped = readJson(path.join(appRoot, 'build-info.json'));
  if (stamped) return stamped;
  // A dev run, or a build that skipped the stamp. Saying so is better than
  // showing a commit that may not be the one this code came from.
  return {
    version: fallbackVersion || null,
    commit: null,
    branch: null,
    committedAt: null,
    builtAt: null,
    stamped: false,
  };
}

/**
 * The racing lines actually installed, with the version stamp each one carries.
 *
 * `built_at` and `source` come from `ml.scripts.export_coaching`, so this
 * reports what produced the file rather than when it was copied.
 */
function installedRacingLines(resourceRoot) {
  const dir = path.join(resourceRoot, 'data', 'reference_models');
  let entries = [];
  try {
    entries = fs.readdirSync(dir).filter((name) => name.endsWith('.optimal.json'));
  } catch {
    return [];
  }
  return entries.map((name) => {
    const file = path.join(dir, name);
    const payload = readJson(file) || {};
    return {
      track: payload.track || name.replace('.optimal.json', ''),
      lapSeconds: typeof payload.lap_seconds === 'number' ? payload.lap_seconds : null,
      microsectors: payload.microsectors ?? null,
      source: payload.source || null,
      builtAt: payload.built_at || null,
      digest: hashFile(file),
      path: file,
    };
  });
}

/**
 * How far this build is behind the repository, when the repository is reachable.
 *
 * `fetch` is what makes the count mean anything -- without it the comparison is
 * against whatever was last pulled, which is exactly the number the user is
 * trying to stop guessing at.
 */
async function repositoryState(repoPath, { fetch = false } = {}) {
  if (!repoPath || !fs.existsSync(path.join(repoPath, '.git'))) {
    return { available: false, reason: 'no_repository', path: repoPath || null };
  }

  const version = await runGit(['--version'], repoPath);
  if (!version.ok) {
    return { available: false, reason: 'git_unavailable', path: repoPath, error: version.error };
  }

  const state = { available: true, path: repoPath, fetched: false, fetchError: null };

  if (fetch) {
    const fetched = await runGit(['fetch', '--quiet', '--prune'], repoPath, FETCH_TIMEOUT_MS);
    state.fetched = fetched.ok;
    state.fetchError = fetched.ok ? null : fetched.stderr || fetched.error;
    state.fetchedAt = fetched.ok ? new Date().toISOString() : null;
  }

  const branch = await runGit(['rev-parse', '--abbrev-ref', 'HEAD'], repoPath);
  state.branch = branch.ok ? branch.stdout : null;

  const head = await runGit(['rev-parse', 'HEAD'], repoPath);
  state.head = head.ok ? head.stdout : null;
  state.shortHead = state.head ? state.head.slice(0, 7) : null;

  const dirty = await runGit(['status', '--porcelain'], repoPath);
  state.dirty = dirty.ok ? dirty.stdout.length > 0 : null;

  // The upstream may simply not exist yet -- a branch that was never pushed.
  // That is a normal state, not an error, and the count is then unknowable.
  const upstream = await runGit(['rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}'], repoPath);
  if (!upstream.ok) {
    state.upstream = null;
    state.behind = null;
    state.ahead = null;
    state.reason = 'no_upstream';
    return state;
  }
  state.upstream = upstream.stdout;

  const counts = await runGit(['rev-list', '--left-right', '--count', `HEAD...${state.upstream}`], repoPath);
  if (counts.ok) {
    const [ahead, behind] = counts.stdout.split(/\s+/).map((value) => Number(value));
    state.ahead = Number.isFinite(ahead) ? ahead : null;
    state.behind = Number.isFinite(behind) ? behind : null;
  }
  return state;
}

/**
 * How many commits separate the build from the repository head.
 *
 * Distinct from `behind` above: that one compares the working copy with its
 * upstream, this one compares the *installed build* with the working copy. A
 * user who never rebuilt after pulling is behind by this number even when the
 * repository says it is up to date.
 */
async function buildBehind(repoPath, buildCommit) {
  if (!repoPath || !buildCommit) return null;
  const known = await runGit(['cat-file', '-e', `${buildCommit}^{commit}`], repoPath);
  if (!known.ok) return { unknownCommit: true, commits: null };
  const counts = await runGit(['rev-list', '--count', `${buildCommit}..HEAD`], repoPath);
  if (!counts.ok) return { unknownCommit: false, commits: null };
  const commits = Number(counts.stdout);
  return { unknownCommit: false, commits: Number.isFinite(commits) ? commits : null };
}

/**
 * Whether the installed racing line is the one the repository currently holds.
 *
 * Compares content, not dates: a line regenerated from an identical search is
 * the same target even with a newer timestamp, and a line copied without being
 * regenerated has an old timestamp but may still be current.
 */
function racingLinesAgainstRepo(lines, repoPath) {
  if (!repoPath) return lines.map((line) => ({ ...line, repoDigest: null, current: null }));
  return lines.map((line) => {
    const inRepo = path.join(repoPath, 'data', 'reference_models', path.basename(line.path));
    const repoDigest = hashFile(inRepo);
    return {
      ...line,
      repoDigest,
      current: repoDigest === null ? null : repoDigest === line.digest,
    };
  });
}

async function collect({ appRoot, resourceRoot, repoPath, fallbackVersion, fetch = false }) {
  const app = buildInfo(appRoot, fallbackVersion);
  const repo = await repositoryState(repoPath, { fetch });
  const lines = installedRacingLines(resourceRoot);

  return {
    app,
    racingLines: racingLinesAgainstRepo(lines, repo.available ? repo.path : null),
    repo,
    buildBehind: repo.available ? await buildBehind(repo.path, app.commit) : null,
    checkedAt: new Date().toISOString(),
  };
}

module.exports = { collect, repositoryState, installedRacingLines, buildInfo, runGit };
