// O log do backend com tamanho máximo (pedido 36).
//
// Antes, o `main.js` acrescentava a saída do backend em `logs/backend.log` para sempre: um
// erro em laço (04/10/2026) deixou o arquivo com 3,8 GB. Agora, quando o arquivo passaria de
// `maxBytes`, ele vira `backend.1.log`, o `.1` vira `.2`, e assim até `arquivos`; o mais velho
// sai. O máximo no disco fica em cerca de (arquivos + 1) × maxBytes.
//
// A conferência é feita a cada escrita, e não só no arranque: um erro em laço gira o arquivo
// na hora, em vez de encher o disco até o próximo arranque.
const fs = require('node:fs');
const path = require('node:path');
const { Writable } = require('node:stream');

const MAX_BYTES_PADRAO = 20 * 1024 * 1024;
const ARQUIVOS_PADRAO = 5;

function nomeGirado(caminho, n) {
  const ext = path.extname(caminho);
  return path.join(path.dirname(caminho), `${path.basename(caminho, ext)}.${n}${ext}`);
}

// backend.log → backend.1.log, backend.1.log → backend.2.log, ...; o de número `arquivos` sai.
function girar(caminho, arquivos = ARQUIVOS_PADRAO) {
  fs.rmSync(nomeGirado(caminho, arquivos), { force: true });
  for (let n = arquivos - 1; n >= 1; n -= 1) {
    const de = nomeGirado(caminho, n);
    if (fs.existsSync(de)) fs.renameSync(de, nomeGirado(caminho, n + 1));
  }
  if (fs.existsSync(caminho)) fs.renameSync(caminho, nomeGirado(caminho, 1));
}

function tamanhoDe(caminho) {
  try {
    return fs.statSync(caminho).size;
  } catch {
    return 0;
  }
}

class LogRotativo extends Writable {
  constructor(caminho, { maxBytes = MAX_BYTES_PADRAO, arquivos = ARQUIVOS_PADRAO, avisar = () => {} } = {}) {
    super();
    this.caminho = caminho;
    this.maxBytes = maxBytes;
    this.arquivos = arquivos;
    this.avisar = avisar;
    this.tamanho = tamanhoDe(caminho);
    this.avisou = false;
    // No arranque, um arquivo que já passou do limite (o de 3,8 GB) gira antes da primeira linha.
    if (this.tamanho > this.maxBytes) this._girar();
  }

  _girar() {
    try {
      girar(this.caminho, this.arquivos);
      this.tamanho = 0;
      this.avisou = false;
    } catch (erro) {
      // Um arquivo preso por outro programa não para o backend: o log segue no mesmo arquivo
      // e tenta girar de novo na próxima escrita (o aviso sai uma vez só).
      if (!this.avisou) this.avisar(`Não consegui girar ${this.caminho}: ${erro.message}`);
      this.avisou = true;
    }
  }

  _write(pedaco, codificacao, pronto) {
    const dados = Buffer.isBuffer(pedaco) ? pedaco : Buffer.from(pedaco, codificacao);
    if (this.tamanho > 0 && this.tamanho + dados.length > this.maxBytes) this._girar();
    fs.appendFile(this.caminho, dados, (erro) => {
      if (!erro) this.tamanho += dados.length;
      pronto(erro);
    });
  }
}

function criarLogRotativo(caminho, opcoes) {
  return new LogRotativo(caminho, opcoes);
}

module.exports = { criarLogRotativo, girar, nomeGirado, MAX_BYTES_PADRAO, ARQUIVOS_PADRAO };
