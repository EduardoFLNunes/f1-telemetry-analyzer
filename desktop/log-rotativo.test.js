// node --test (na pasta desktop): a rotação do log do backend (pedido 36).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { criarLogRotativo, nomeGirado } = require('./log-rotativo');

function pastaNova() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'log-rotativo-'));
}

function escrever(log, texto) {
  return new Promise((ok, falha) => log.write(texto, (erro) => (erro ? falha(erro) : ok())));
}

test('gira quando o arquivo passaria do limite e guarda só os 5 mais novos', async () => {
  const pasta = pastaNova();
  const caminho = path.join(pasta, 'backend.log');
  const log = criarLogRotativo(caminho, { maxBytes: 100, arquivos: 5 });
  for (let i = 0; i < 40; i += 1) await escrever(log, `linha ${String(i).padStart(2, '0')} ${'x'.repeat(30)}\n`); // 40 bytes cada
  const nomes = fs.readdirSync(pasta).sort();
  assert.deepEqual(nomes, ['backend.1.log', 'backend.2.log', 'backend.3.log', 'backend.4.log', 'backend.5.log', 'backend.log']);
  for (const nome of nomes) assert.ok(fs.statSync(path.join(pasta, nome)).size <= 100, nome);
  // Nenhuma linha cortada ao meio, e o mais novo fica no backend.log.
  const atual = fs.readFileSync(caminho, 'utf8');
  assert.match(atual, /^(linha \d\d x{30}\n)+$/);
  assert.match(atual, /linha 39/);
  assert.match(fs.readFileSync(nomeGirado(caminho, 1), 'utf8'), /^(linha \d\d x{30}\n)+$/);
  // 6 arquivos de 2 linhas: as 12 mais novas ficam; a 27 e as anteriores saíram.
  const tudo = nomes.map((n) => fs.readFileSync(path.join(pasta, n), 'utf8')).join('');
  assert.doesNotMatch(tudo, /linha 27/);
  assert.match(tudo, /linha 28/);
});

test('no arranque, um arquivo que já passou do limite gira antes da primeira linha', async () => {
  const pasta = pastaNova();
  const caminho = path.join(pasta, 'backend.log');
  fs.writeFileSync(caminho, 'velho\n'.repeat(50));
  const log = criarLogRotativo(caminho, { maxBytes: 100 });
  await escrever(log, 'novo\n');
  assert.equal(fs.readFileSync(caminho, 'utf8'), 'novo\n');
  assert.equal(fs.readFileSync(nomeGirado(caminho, 1), 'utf8'), 'velho\n'.repeat(50));
});

test('abaixo do limite, continua acrescentando no mesmo arquivo', async () => {
  const pasta = pastaNova();
  const caminho = path.join(pasta, 'backend.log');
  fs.writeFileSync(caminho, 'de antes\n');
  const log = criarLogRotativo(caminho);
  await escrever(log, 'de agora\n');
  assert.equal(fs.readFileSync(caminho, 'utf8'), 'de antes\nde agora\n');
  assert.equal(fs.readdirSync(pasta).length, 1);
});

test('se não der para girar, avisa e segue escrevendo', async () => {
  const pasta = pastaNova();
  const caminho = path.join(pasta, 'backend.log');
  const avisos = [];
  const log = criarLogRotativo(caminho, { maxBytes: 10, avisar: (m) => avisos.push(m) });
  fs.mkdirSync(path.join(nomeGirado(caminho, 5), 'dentro'), { recursive: true }); // uma pasta no lugar do backend.5.log: não sai
  await escrever(log, '0123456789\n');
  await escrever(log, 'mais uma\n');
  await escrever(log, 'e outra\n');
  assert.equal(fs.readFileSync(caminho, 'utf8'), '0123456789\nmais uma\ne outra\n');
  assert.equal(avisos.length, 1);
});
