// Pedido 35, Parte D: mede o mapa ao vivo na janela de teste, pelo DevTools Protocol.
// Uso: node medir_mapa.mjs <porta> <segundos> <padrao-da-url> [saida.json]
//
// Na pagina:
//   * redesenhos: chamadas de clearRect por canvas (cada desenho completo limpa o canvas uma vez);
//   * respostas: XHR para a URL do mapa (padrao), com bytes e tempo de cada uma;
//   * posicoes novas: `s` distintos nas respostas (o carro so muda de lugar com um `s` novo), ou,
//     se a pagina expuser `window.__mapaAoVivo` (depois da Parte D), as posicoes desenhadas.
// No processo da pagina: Performance.getMetrics (tempo de script e de tarefas por segundo).
import { writeFileSync } from 'node:fs';

const [porta, segundos, padrao, saida] = process.argv.slice(2);
const alvos = await (await fetch(`http://127.0.0.1:${porta}/json`)).json();
const pagina = alvos.find((a) => a.type === 'page' && !a.url.startsWith('devtools://'));
const ws = new WebSocket(pagina.webSocketDebuggerUrl);
await new Promise((r, e) => { ws.onopen = r; ws.onerror = e; });
let id = 0;
const pend = new Map();
ws.onmessage = (m) => {
  const d = JSON.parse(m.data);
  if (d.id && pend.has(d.id)) { const { r, e } = pend.get(d.id); pend.delete(d.id); d.error ? e(new Error(JSON.stringify(d.error))) : r(d.result); }
};
const chamar = (method, params = {}) => new Promise((r, e) => { id += 1; pend.set(id, { r, e }); ws.send(JSON.stringify({ id, method, params })); });
const avaliar = async (expr) => {
  const res = await chamar('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
  if (res.exceptionDetails) throw new Error(JSON.stringify(res.exceptionDetails));
  return res.result.value;
};

await chamar('Performance.enable');
await avaliar(`(() => {
  const m = window.__medida = { limpezas: new Map(), respostas: [], s: new Set(), inicio: performance.now(),
    q0: window.__mapaAoVivo ? window.__mapaAoVivo.quadros : null, p0: window.__mapaAoVivo ? window.__mapaAoVivo.posicoes : null };
  if (!window.__ganchos3) {
    window.__ganchos3 = true;
    const limpar = window.__clearRectOriginal || CanvasRenderingContext2D.prototype.clearRect; window.__clearRectOriginal = limpar;
    CanvasRenderingContext2D.prototype.clearRect = function (...a) {
      const md = window.__medida; if (md) { const c = this.canvas; md.limpezas.set(c, (md.limpezas.get(c) || 0) + 1); }
      return limpar.apply(this, a);
    };
    const abrir = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function (metodo, url, ...r) { this.__url = String(url); this.__t0 = performance.now(); return abrir.call(this, metodo, url, ...r); };
    const enviar = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function (...a) {
      this.__t0 = performance.now();
      this.addEventListener('loadend', () => {
        const md = window.__medida; if (!md || !this.__url.includes(${JSON.stringify(padrao)})) return;
        let j = null; let bytes = 0;
        try {
          if (this.responseType === '' || this.responseType === 'text') { bytes = this.responseText.length; j = JSON.parse(this.responseText); }
          else { j = this.response; bytes = JSON.stringify(j).length; }
        } catch {}
        md.respostas.push({ ms: performance.now() - this.__t0, bytes });
        const s = j && (j.s ?? j.carro?.s); if (s != null) md.s.add(String(s));
      });
      return enviar.apply(this, a);
    };
  }
  return true;
})()`);
const m0 = Object.fromEntries((await chamar('Performance.getMetrics')).metrics.map((x) => [x.name, x.value]));
await new Promise((r) => setTimeout(r, Number(segundos) * 1000));
const m1 = Object.fromEntries((await chamar('Performance.getMetrics')).metrics.map((x) => [x.name, x.value]));
const pag = await avaliar(`(() => {
  const m = window.__medida; const dur = (performance.now() - m.inicio) / 1000;
  const canvas = [...m.limpezas.entries()].map(([c, n]) => ({ w: c.width, h: c.height, porSegundo: +(n / dur).toFixed(2) }))
    .sort((a, b) => b.w * b.h - a.w * a.h);
  const r = m.respostas; const med = (xs) => { const s = [...xs].sort((a, b) => a - b); return s.length ? s[Math.floor(s.length / 2)] : null; };
  const desenho = window.__mapaAoVivo && m.q0 !== null ? { quadrosPorSegundo: +((window.__mapaAoVivo.quadros - m.q0) / dur).toFixed(1),
    posicoesDesenhadasPorSegundo: +((window.__mapaAoVivo.posicoes - m.p0) / dur).toFixed(1) } : null;
  return { segundos: +dur.toFixed(1), canvas, respostasPorSegundo: +(r.length / dur).toFixed(2),
    bytesMediana: med(r.map((x) => x.bytes)), msMediana: med(r.map((x) => x.ms)), msMaximo: r.length ? Math.max(...r.map((x) => x.ms)) : null,
    posicoesNovasPorSegundo: +(m.s.size / dur).toFixed(2), desenho };
})()`);
const dt = (m1.Timestamp - m0.Timestamp);
const res = {
  pagina: pag,
  processoDaPagina: {
    scriptMsPorSegundo: +(1000 * (m1.ScriptDuration - m0.ScriptDuration) / dt).toFixed(1),
    tarefasMsPorSegundo: +(1000 * (m1.TaskDuration - m0.TaskDuration) / dt).toFixed(1),
    layoutsPorSegundo: +((m1.LayoutCount - m0.LayoutCount) / dt).toFixed(2),
    estilosPorSegundo: +((m1.RecalcStyleCount - m0.RecalcStyleCount) / dt).toFixed(2),
  },
};
console.log(JSON.stringify(res, null, 1));
if (saida) writeFileSync(saida, JSON.stringify(res, null, 1));
ws.close();
