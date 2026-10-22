"""Pedido 36, Parte F.5: o replay da curva desenhado fora do jogo.

Repete, num canvas HTML, o desenho da janela "Replay da curva" do app do jogo
(`radio_engenheiro.lua`, `desenharACurva`): a mesma camera (a entrada para cima, a
orientacao do mapa do app), a `pista_detalhada.png` recortada e girada na curva (o canvas
usa a transformacao afim dos tres cantos, como o `ui.drawImageQuad`), as duas linhas, as
freadas, as minimas, o tracado, os dois carros e o alto. Os dados sao os da rota
`/api/radio/replay/<id>` numa passagem real da sessao de 21/10 pelo radio.

Uso: python replay_previa.py <radio_replay.json> <id> <curva> <fracao do tempo> <saida.html>
"""
import json
import sys
from pathlib import Path

ARQ, ID, CURVA, FRACAO, SAIDA = Path(sys.argv[1]), sys.argv[2], sys.argv[3], float(sys.argv[4]), Path(sys.argv[5])
APP = Path(r"C:\Users\Dokas\Desktop\f1-telemetry-analyzer\tools\csp_app\radio_engenheiro")
dados = json.loads(ARQ.read_text(encoding="utf-8"))
curva = next(c for c in dados["replays"][ID]["curvas"] if c["curva"] == CURVA)
pj = json.loads((APP / "pista.json").read_text(encoding="utf-8"))
img = dict(pj["imagem"], url=(APP / pj["imagem"]["arquivo"]).as_uri())

HTML = r"""<!doctype html><html><head><meta charset="utf-8"><title>[teste] replay da curva fora do jogo</title>
<style>html,body{margin:0;background:#5b6168}canvas{display:block}</style></head><body>
<canvas id="c" width="420" height="300"></canvas><script>
const c = __CURVA__, img = __IMG__, T = __T__;
const W = 420, H = 300, TOPO = 24, MARGEM = 18;
const VERMELHO = 'rgb(225,6,0)', FANTASMA = 'rgba(233,237,242,0.9)', AMARELO = 'rgb(245,197,66)', MIOLO = 'rgba(8,9,11,0.6)';
const ctx = document.getElementById('c').getContext('2d');
// cameraDaCurva (radio_engenheiro.lua)
const ref = c.linhas.referencia, a = ref[0], b = ref[Math.min(ref.length, 11) - 1];
const du = b[1] - a[1], dv = -(b[0] - a[0]);
const ang = -Math.PI / 2 - Math.atan2(dv, du), cs = Math.cos(ang), sn = Math.sin(ang);
const girar = (x, z) => { const u = z, v = -x; return [u * cs - v * sn, u * sn + v * cs]; };
let gx0 = Infinity, gx1 = -Infinity, gy0 = Infinity, gy1 = -Infinity;
for (const p of [...c.linhas.voce, ...ref]) { const [gx, gy] = girar(p[0], p[1]); gx0 = Math.min(gx0, gx); gx1 = Math.max(gx1, gx); gy0 = Math.min(gy0, gy); gy1 = Math.max(gy1, gy); }
const k = Math.min((W - 2 * MARGEM) / Math.max(gx1 - gx0, 1), (H - 2 * MARGEM - TOPO) / Math.max(gy1 - gy0, 1));
const ax = W / 2, ay = TOPO + (H - TOPO) / 2, rcx = (gx0 + gx1) / 2, rcy = (gy0 + gy1) / 2;
const tela = (x, z) => { const [gx, gy] = girar(x, z); return [ax + k * (gx - rcx), ay + k * (gy - rcy)]; };
const mapa = (sx, sy) => { const gx = (sx - ax) / k + rcx, gy = (sy - ay) / k + rcy; const u = gx * cs + gy * sn, v = -gx * sn + gy * cs; return [-v, -u]; };
const uv = (sx, sy) => { const [mx, my] = mapa(sx, sy); return [(mx - img.x0) * img.pxPorMetro, (my - img.y0) * img.pxPorMetro]; };
function posicao(linha, t) { if (t <= linha[0][2]) return linha[0]; const n = linha.length; if (t >= linha[n - 1][2]) return linha[n - 1];
  let i = 1; while (linha[i][2] < t) i++; const p = linha[i - 1], q = linha[i], u = (t - p[2]) / (q[2] - p[2]); return [p[0] + (q[0] - p[0]) * u, p[1] + (q[1] - p[1]) * u]; }
// O encaixe dos rotulos (radio_engenheiro.lua, rotulo; replay.ts, QuadroDeRotulos)
const LUGARES = ['direita', 'esquerda', 'abaixo', 'acima', 'direitaAcima', 'esquerdaAbaixo', 'direitaAbaixo', 'esquerdaAcima'];
const area = [2, TOPO + 2, W - 2, H - 2], ocupados = [], AFAST = [0, 14, 28, 44, 60];
const DIR = { direita: [1, 0], esquerda: [-1, 0], abaixo: [0, 1], acima: [0, -1], direitaAcima: [0.7, -0.7], esquerdaAbaixo: [-0.7, 0.7], direitaAbaixo: [0.7, 0.7], esquerdaAcima: [-0.7, -0.7] };
const ocupar = (x, y, r) => ocupados.push([x - r, y - r, x + r, y + r]);
function canto(l, x, y, w, h) { return l === 'direita' ? [x + 8, y - h / 2] : l === 'esquerda' ? [x - 8 - w, y - h / 2] : l === 'abaixo' ? [x - w / 2, y + 8]
  : l === 'acima' ? [x - w / 2, y - 8 - h] : l === 'direitaAcima' ? [x + 6, y - 6 - h] : l === 'esquerdaAbaixo' ? [x - 6 - w, y + 6]
  : l === 'direitaAbaixo' ? [x + 6, y + 6] : [x - 6 - w, y - 6 - h]; }
function rotulo(texto, x, y, cor, preferido) { ctx.font = '11px "Segoe UI", sans-serif'; const w = ctx.measureText(texto).width + 6, h = 15;
  const livre = (bx, by) => bx >= area[0] && by >= area[1] && bx + w <= area[2] && by + h <= area[3] && ocupados.every(r => !(bx < r[2] && r[0] < bx + w && by < r[3] && r[1] < by + h));
  let c0 = null, longe = false; for (const d of AFAST) { for (const l of [preferido, ...LUGARES]) { const c1 = canto(l, x + DIR[l][0] * d, y + DIR[l][1] * d, w, h); if (livre(...c1)) { c0 = c1; longe = d > 0; break; } } if (c0) break; }
  if (!c0) { const [bx, by] = canto(preferido, x, y, w, h); c0 = [Math.min(Math.max(bx, area[0]), area[2] - w), Math.min(Math.max(by, area[1]), area[3] - h)]; }
  ocupados.push([c0[0], c0[1], c0[0] + w, c0[1] + h]);
  if (longe) { ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(Math.min(Math.max(x, c0[0]), c0[0] + w), Math.min(Math.max(y, c0[1]), c0[1] + h)); ctx.strokeStyle = cor; ctx.lineWidth = 1; ctx.stroke(); }
  ctx.fillStyle = MIOLO; ctx.fillRect(c0[0], c0[1], w, h); ctx.fillStyle = cor; ctx.textBaseline = 'top'; ctx.fillText(texto, c0[0] + 3, c0[1] + 1); }
function marca(x, y, miolo, borda) { ctx.beginPath(); ctx.arc(x, y, 6.5, 0, 2 * Math.PI); ctx.fillStyle = miolo; ctx.fill(); ctx.lineWidth = 2.5; ctx.strokeStyle = borda; ctx.stroke(); }
ctx.fillStyle = 'rgba(17,18,20,0.92)'; ctx.fillRect(0, 0, W, H);
const imagem = new Image();
imagem.onload = () => {
  const P0 = uv(0, 0), P1 = uv(W, 0), P2 = uv(0, H);
  const U = [P1[0] - P0[0], P1[1] - P0[1]], V = [P2[0] - P0[0], P2[1] - P0[1]], det = U[0] * V[1] - V[0] * U[1];
  const A = W * V[1] / det, B = H * -U[1] / det, C = W * -V[0] / det, D = H * U[0] / det;
  ctx.save(); ctx.setTransform(A, B, C, D, -(A * P0[0] + C * P0[1]), -(B * P0[0] + D * P0[1])); ctx.drawImage(imagem, 0, 0); ctx.restore();
  resto();
};
imagem.src = img.url;
function resto() {
  for (const [linha, cor] of [[ref, FANTASMA], [c.linhas.voce, VERMELHO]]) { ctx.beginPath(); linha.forEach((p, i) => { const [x, y] = tela(p[0], p[1]); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
    ctx.strokeStyle = cor; ctx.lineWidth = 2.5; ctx.lineJoin = 'round'; ctx.stroke(); }
  const r = posicao(ref, T), v = posicao(c.linhas.voce, T);
  const [rsx, rsy] = tela(r[0], r[1]), [vsx, vsy] = tela(v[0], v[1]);
  const [mvx, mvy] = tela(c.minimas.voce.x, c.minimas.voce.z), [mrx, mry] = tela(c.minimas.referencia.x, c.minimas.referencia.z);
  const [tvx, tvy] = tela(...c.tracado.voce), [trx, try_] = tela(...c.tracado.referencia);
  ocupar(rsx, rsy, 9); ocupar(vsx, vsy, 9); for (const [x, y] of [[mvx, mvy], [mrx, mry], [tvx, tvy], [trx, try_]]) ocupar(x, y, 5);
  const traco = (m, cor) => { if (!m) return null; const [x, y] = tela(m.x, m.z); ctx.beginPath(); ctx.moveTo(x - 7, y); ctx.lineTo(x + 7, y); ctx.strokeStyle = cor; ctx.lineWidth = 3; ctx.stroke(); ocupar(x, y, 7); return [x, y]; };
  const fv = traco(c.freadas.voce, VERMELHO); traco(c.freadas.referencia, FANTASMA);
  const contra = c.referencia === 'minha_melhor' ? 'da sua melhor' : 'da IA', d = c.freadas.distanciaM;
  if (fv && d !== null) { const m = Math.round(Math.abs(d)); rotulo(m < 1 ? 'você freia no mesmo ponto' : `você freia ${m} m ${d < 0 ? 'antes' : 'depois'} ${contra}`, fv[0], fv[1], VERMELHO, 'direita'); }
  if (Math.hypot(tvx - trx, tvy - try_) > 2) { ctx.beginPath(); ctx.moveTo(trx, try_); ctx.lineTo(tvx, tvy); ctx.strokeStyle = AMARELO; ctx.lineWidth = 1.5; ctx.stroke();
    const an = Math.atan2(tvy - try_, tvx - trx); ctx.beginPath(); ctx.moveTo(tvx, tvy); ctx.lineTo(tvx - 7 * Math.cos(an - 0.5), tvy - 7 * Math.sin(an - 0.5)); ctx.lineTo(tvx - 7 * Math.cos(an + 0.5), tvy - 7 * Math.sin(an + 0.5)); ctx.closePath(); ctx.fillStyle = AMARELO; ctx.fill(); }
  rotulo(`você passa ${c.tracado.distanciaM.toFixed(1).replace('.', ',')} m mais à ${c.tracado.lado}`, (tvx + trx) / 2, (tvy + try_) / 2, AMARELO, 'abaixo');
  for (const [x, y, cor] of [[mvx, mvy, VERMELHO], [mrx, mry, FANTASMA]]) { ctx.beginPath(); ctx.arc(x, y, 3.5, 0, 2 * Math.PI); ctx.fillStyle = cor; ctx.fill(); }
  rotulo(`mínima ${Math.round(c.minimas.voce.kmh)} km/h`, mvx, mvy, VERMELHO, 'esquerda');
  rotulo(`mínima ${Math.round(c.minimas.referencia.kmh)} km/h`, mrx, mry, FANTASMA, 'direita');
  marca(rsx, rsy, MIOLO, FANTASMA); marca(vsx, vsy, '#fff', VERMELHO);
  rotulo(c.rotuloDaReferencia, rsx, rsy, FANTASMA, 'direitaAcima'); rotulo('você', vsx, vsy, '#f2f4f5', 'esquerdaAbaixo');
  ctx.fillStyle = 'rgba(17,18,20,0.78)'; ctx.fillRect(0, 0, W, TOPO);
  ctx.font = '12px "Segoe UI", sans-serif'; ctx.fillStyle = '#f2f4f5'; ctx.textBaseline = 'top';
  ctx.fillText(`${c.curva}, ${c.lado}${c.volta ? ' · volta ' + c.volta : ''} · ${c.perdaS >= 0 ? 'perde' : 'ganha'} ${Math.abs(c.perdaS).toFixed(2).replace('.', ',')} s nesta curva`, 10, 5);
}
</script></body></html>"""
SAIDA.write_text(HTML.replace("__CURVA__", json.dumps(curva)).replace("__IMG__", json.dumps(img))
                 .replace("__T__", json.dumps(curva["duracaoS"] * FRACAO)), encoding="utf-8")
print(CURVA, "volta", curva["volta"], "t =", round(curva["duracaoS"] * FRACAO, 2), "s")
