/**
 * Guarda o instalador de cada versao num lugar so e diz qual e a mais atual.
 *
 *   node scripts/publish-version.js            guarda a versao do package.json e refaz o indice
 *   node scripts/publish-version.js --indice   so refaz o indice
 *
 * A pasta e `versoes/` na raiz do repositorio, uma subpasta por versao:
 *   versoes/<versao>/<instalador>.exe
 *   versoes/<versao>/build-info.json   (o carimbo do build: commit, data, arvore suja)
 *   versoes/<versao>/sha256.txt
 * e `versoes/LEIA-ME.md`, refeito a cada chamada, com a versao mais atual (a de
 * build mais recente, nao a de numero maior), a instalada neste computador
 * (registro do Windows) e como instalar e abrir.
 *
 * Roda no fim do `npm run dist:win`. Os instaladores ficam fora do git; so o
 * LEIA-ME e versionado.
 */

const { execFileSync } = require('child_process');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const DESKTOP_DIR = path.resolve(__dirname, '..');
const REPO_ROOT = path.resolve(DESKTOP_DIR, '..');
const VERSIONS_DIR = path.join(REPO_ROOT, 'versoes');
const INDEX = path.join(VERSIONS_DIR, 'LEIA-ME.md');
const PRODUCT = 'Automobilista Telemetria';
const DEFAULT_INSTALL_DIR = path.join(process.env.LOCALAPPDATA || '', 'Programs', PRODUCT);

function sha256(file) {
  const hash = crypto.createHash('sha256');
  const fd = fs.openSync(file, 'r');
  const buffer = Buffer.alloc(1 << 22);
  let read;
  while ((read = fs.readSync(fd, buffer, 0, buffer.length, null)) > 0) hash.update(buffer.subarray(0, read));
  fs.closeSync(fd);
  return hash.digest('hex');
}

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch {
    return null;
  }
}

/** Copia o instalador recem-gerado para versoes/<versao>/. */
function publish() {
  const pkg = readJson(path.join(DESKTOP_DIR, 'package.json'));
  const version = pkg.version;
  const name = pkg.build.artifactName.replace('${version}', version).replace('${ext}', 'exe');
  const installer = path.join(DESKTOP_DIR, pkg.build.directories.output || 'dist', name);
  if (!fs.existsSync(installer)) throw new Error(`Instalador nao encontrado: ${installer}`);
  const info = readJson(path.join(DESKTOP_DIR, 'build-info.json'));
  if (!info || info.version !== version) {
    throw new Error(`build-info.json nao e da versao ${version}; rode o build completo (npm run dist:win).`);
  }
  const target = path.join(VERSIONS_DIR, version);
  fs.mkdirSync(target, { recursive: true });
  fs.copyFileSync(installer, path.join(target, name));
  fs.writeFileSync(path.join(target, 'build-info.json'), JSON.stringify(info, null, 2) + '\n', 'utf8');
  fs.writeFileSync(path.join(target, 'sha256.txt'), `${sha256(installer)}  ${name}\n`, 'utf8');
  console.log(`versoes: ${version} guardada em ${target}`);
}

/** A versao instalada neste computador, pelo registro de desinstalacao do Windows. */
function installedVersion() {
  if (process.platform !== 'win32') return null;
  const script = [
    "$out = foreach ($root in 'HKCU','HKLM') {",
    "  Get-ChildItem \"$($root):\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\" -ErrorAction SilentlyContinue |",
    '  ForEach-Object { Get-ItemProperty $_.PSPath } |',
    `  Where-Object { $_.DisplayName -eq '${PRODUCT}' } |`,
    '  ForEach-Object { [pscustomobject]@{ root = $root; version = $_.DisplayVersion; uninstall = $_.UninstallString } }',
    '}',
    '@($out) | ConvertTo-Json -Compress',
  ].join(' ');
  try {
    const out = String(execFileSync('powershell.exe', ['-NoProfile', '-Command', script], { windowsHide: true })).trim();
    const found = out ? [].concat(JSON.parse(out)) : [];
    const entry = found[0];
    if (!entry) return null;
    const exe = String(entry.uninstall || '').match(/"([^"]+)"/);
    return {
      version: entry.version || null,
      scope: entry.root === 'HKLM' ? 'todos os usuários' : 'só este usuário',
      folder: exe ? path.dirname(exe[1]) : null,
      count: found.length,
    };
  } catch {
    return null;
  }
}

function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function megabytes(bytes) {
  return `${(bytes / 1e6).toLocaleString('pt-BR', { maximumFractionDigits: 0 })} MB`;
}

/** Refaz versoes/LEIA-ME.md a partir das subpastas. */
function writeIndex() {
  fs.mkdirSync(VERSIONS_DIR, { recursive: true });
  const versions = fs.readdirSync(VERSIONS_DIR, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => {
      const folder = path.join(VERSIONS_DIR, entry.name);
      const info = readJson(path.join(folder, 'build-info.json')) || {};
      const installers = fs.readdirSync(folder).filter((file) => file.toLowerCase().endsWith('.exe'));
      const hashes = fs.existsSync(path.join(folder, 'sha256.txt'))
        ? fs.readFileSync(path.join(folder, 'sha256.txt'), 'utf8') : '';
      return {
        version: entry.name,
        info,
        builtAt: info.builtAt || null,
        installers: installers.map((file) => ({
          file,
          bytes: fs.statSync(path.join(folder, file)).size,
          sha256: (hashes.split(/\r?\n/).find((line) => line.endsWith(file)) || '').split(/\s+/)[0] || null,
        })),
      };
    })
    .filter((v) => v.installers.length)
    .sort((a, b) => String(b.builtAt || '').localeCompare(String(a.builtAt || '')));
  const latest = versions[0];
  const installed = installedVersion();
  const installedIsLatest = installed && latest && installed.version === latest.version;
  const installFolder = (installed && installed.folder) || DEFAULT_INSTALL_DIR;

  const lines = [];
  lines.push(`# Versões do app ${PRODUCT}`);
  lines.push('');
  lines.push(`Gerado por \`desktop/scripts/publish-version.js\` em ${formatDate(new Date().toISOString())}. Não edite à mão: o arquivo é refeito a cada build (\`npm run dist:win\`) e por \`npm run versoes\` (na pasta \`desktop\`).`);
  lines.push('');
  if (latest) {
    const inst = latest.installers[0];
    lines.push(`- **A mais atual:** \`${latest.version}\`, gerada em ${formatDate(latest.builtAt)}${latest.info.shortCommit ? `, commit \`${latest.info.shortCommit}\`` : ''}.`);
    lines.push(`  - Instalador: \`versoes\\${latest.version}\\${inst.file}\``);
  }
  if (installed) {
    lines.push(`- **Instalada neste computador:** \`${installed.version}\`, para ${installed.scope}, em \`${installFolder}\`.`);
    lines.push(installedIsLatest
      ? '  - É a mais atual.'
      : '  - **Não é a mais atual.** Instale a mais atual pelos passos abaixo.');
  } else {
    lines.push('- **Instalada neste computador:** nenhuma encontrada no registro do Windows.');
  }
  lines.push('');
  lines.push('A "mais atual" é a de build mais recente, não a de número maior: a `0.2.0-assetto-udp` (14/06) é anterior à `0.1.7-phase-16` (25/08).');
  lines.push('');
  lines.push('## Como instalar a mais atual');
  lines.push('');
  lines.push('1. Feche o jogo e o app, inclusive na bandeja do Windows.');
  lines.push('2. Rode o instalador da mais atual, por cima da instalada.');
  if (installed) {
    lines.push(`   - Se ele perguntar para quem instalar, escolha **${installed.scope}**, como na instalação atual.`);
    lines.push(`   - Mantenha a pasta \`${installFolder}\`.`);
  }
  lines.push('   - A instalação preserva os dados em `%APPDATA%\\Automobilista Telemetria` (gravações, configuração).');
  lines.push('3. Abra o app pelo menu Iniciar, procurando **Automobilista Telemetria**, ou pelo atalho da área de trabalho.');
  lines.push(`   - O executável fica em \`${path.join(installFolder, `${PRODUCT}.exe`)}\`.`);
  lines.push('4. Confira a versão na aba **Coleta de dados** ("Versão do app") ou em **Sistema**.');
  lines.push('');
  lines.push('## Todas as versões');
  lines.push('');
  lines.push('| versão | gerada em | commit | instalador | tamanho | sha256 |');
  lines.push('|---|---|---|---|---:|---|');
  for (const v of versions) {
    for (const inst of v.installers) {
      const mark = v === latest ? ' (mais atual)' : '';
      const here = installed && installed.version === v.version ? ' (instalada)' : '';
      lines.push(`| \`${v.version}\`${mark}${here} | ${formatDate(v.builtAt)} | ${v.info.shortCommit ? `\`${v.info.shortCommit}\`` : 'desconhecido'} | \`${inst.file}\` | ${megabytes(inst.bytes)} | ${inst.sha256 ? `\`${inst.sha256.slice(0, 12)}…\`` : '—'} |`);
    }
  }
  lines.push('');
  lines.push('Os instaladores ficam fora do git (só este arquivo é versionado). Cada pasta tem o `build-info.json` do build, quando ele existe, e o `sha256.txt`.');
  fs.writeFileSync(INDEX, lines.join('\n') + '\n', 'utf8');
  console.log(`versoes: indice refeito (${versions.length} versoes; mais atual ${latest ? latest.version : 'nenhuma'})`);
}

if (!process.argv.includes('--indice')) publish();
writeIndex();
