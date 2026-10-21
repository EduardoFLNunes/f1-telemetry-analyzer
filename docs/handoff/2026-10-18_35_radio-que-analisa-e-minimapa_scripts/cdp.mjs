// Fala com a janela do Electron pelo DevTools Protocol (Node 24: WebSocket e fetch globais).
// Uso: node cdp.mjs <porta> <comando> [args...]
//   eval "<js>"                         avalia na página e imprime o resultado
//   shot <arquivo.png> <largura> <altura> [rolagem] [fullpage]   captura com viewport emulado
//   viewport <largura> <altura>         fixa o viewport emulado
import { writeFileSync } from 'node:fs';

const [porta, comando, ...args] = process.argv.slice(2);
const alvos = await (await fetch(`http://127.0.0.1:${porta}/json`)).json();
const pagina = alvos.find((a) => a.type === 'page' && !a.url.startsWith('devtools://'));
if (!pagina) throw new Error('janela não encontrada');
const ws = new WebSocket(pagina.webSocketDebuggerUrl);
await new Promise((r, e) => { ws.onopen = r; ws.onerror = e; });
let id = 0;
const pendentes = new Map();
ws.onmessage = (m) => {
  const d = JSON.parse(m.data);
  if (d.id && pendentes.has(d.id)) {
    const { r, e } = pendentes.get(d.id);
    pendentes.delete(d.id);
    d.error ? e(new Error(JSON.stringify(d.error))) : r(d.result);
  }
};
const chamar = (method, params = {}) => new Promise((r, e) => { id += 1; pendentes.set(id, { r, e }); ws.send(JSON.stringify({ id, method, params })); });
const avaliar = async (expr) => {
  const res = await chamar('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
  if (res.exceptionDetails) throw new Error(JSON.stringify(res.exceptionDetails));
  return res.result.value;
};
const viewport = (w, h) => chamar('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: 1, mobile: false });

try {
  if (comando === 'eval') {
    console.log(JSON.stringify(await avaliar(args[0]), null, 2));
  } else if (comando === 'viewport') {
    await viewport(Number(args[0]), Number(args[1]));
    console.log('ok');
  } else if (comando === 'shot') {
    const [arquivo, w, h, rolagem, inteira] = args;
    await chamar('Page.bringToFront');
    await chamar('Emulation.setFocusEmulationEnabled', { enabled: true });
    await viewport(Number(w), Number(h));
    await new Promise((r) => setTimeout(r, 400));
    if (rolagem) await avaliar(`document.querySelector('.tela')?.scrollTo(0, ${Number(rolagem)}); true`);
    let clip;
    if (inteira === 'fullpage') {
      // A tela rola dentro de .tela: aumenta o viewport até caber o conteúdo inteiro.
      const altura = await avaliar(`(() => { const t = document.querySelector('.tela'); const n = document.querySelector('.navegacao'); return t ? Math.ceil(t.scrollHeight + (n ? n.getBoundingClientRect().bottom : 0) + 16) : Math.ceil(document.documentElement.scrollHeight); })()`);
      await viewport(Number(w), Math.max(Number(h), altura));
      await new Promise((r) => setTimeout(r, 600));
    }
    await new Promise((r) => setTimeout(r, 500));
    const captura = chamar('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false, ...(clip ? { clip } : {}) });
    const { data } = await Promise.race([captura, new Promise((_, e) => setTimeout(() => e(new Error('captura demorou mais de 20 s')), 20000))]);
    writeFileSync(arquivo, Buffer.from(data, 'base64'));
    console.log(`gravado ${arquivo}`);
  } else {
    throw new Error(`comando desconhecido: ${comando}`);
  }
} finally {
  ws.close();
}
