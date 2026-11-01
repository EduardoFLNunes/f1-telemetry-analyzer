"""Pedido 43, Parte D.4: a janela "Replay da curva" do jogo desenhada fora do jogo.

Repete, num canvas HTML, as contas da janela do app do jogo (`radio_engenheiro.lua`, versao
0.4.2): a divisao da area (`dividirAJanela`: o replay fica com pelo menos 150 px; entram, na
ordem, o pedal, a diferenca acumulada e a velocidade), a curva (`desenharACurva`, com a
`pista_detalhada.png` recortada e girada como o `ui.drawImageQuad`, o trecho da fala, os
rotulos e os carros), os tres visuais (`desenharOPedal`, `desenharADiferenca`,
`desenharAVelocidade`) e, nos boxes, a grade da sessao (`desenharAGrade`, as ultimas 8 voltas).
Os dados sao os da rota `/api/radio/replay/<id>` e `/api/radio/grade` numa passagem real da
sessao pelo radio (`radio_offline.py`).

Uso: python previa.py <passagem.json> <id> <curva> <fracao do tempo> <largura> <altura> <boxes 0|1> <saida.html>
"""
import json
import sys
from pathlib import Path

ARQ, ID, CURVA = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
FRACAO, W, H, BOXES, SAIDA = float(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]), sys.argv[7] == "1", Path(sys.argv[8])
APP = Path(__file__).resolve().parents[2] / "tools" / "csp_app" / "radio_engenheiro"
dados = json.loads(ARQ.read_text(encoding="utf-8"))
curva = next(c for c in dados["replays"][ID]["curvas"] if c["curva"] == CURVA)
pj = json.loads((APP / "pista.json").read_text(encoding="utf-8"))
img = dict(pj["imagem"], url=(APP / pj["imagem"]["arquivo"]).as_uri())
grade = dados.get("grade") if BOXES else None

HTML = r"""<!doctype html><html><head><meta charset="utf-8"><title>[teste] replay da curva fora do jogo</title>
<style>html,body{margin:0;background:#5b6168}canvas{display:block}</style></head><body>
<canvas id="c" width="__W__" height="__H__"></canvas><script>
const c = __CURVA__, img = __IMG__, T = __T__, G = __GRADE__, W = __W__, H = __H__;
const TOPO = 24, MARGEM = 18, ALT = { pedal: 30, diferenca: 60, velocidade: 74 }, MINIMO = 150, COL = 34;
const VERMELHO = 'rgb(225,6,0)', FANTASMA = 'rgba(233,237,242,0.9)', MIOLO = 'rgba(8,9,11,0.6)', TEXTO = 'rgb(242,244,245)';
const FUNDO_MAPA = 'rgba(17,18,20,0.92)', FRACO = 'rgb(140,150,161)', APOIO = 'rgb(184,194,204)', TRECHO = 'rgba(255,255,255,0.16)', TRECHO_NA_PISTA = 'rgba(255,255,255,0.32)';
const PEDAL = { 0: 'rgb(245,197,66)', 1: 'rgb(61,220,132)', 2: 'rgb(255,90,95)' };
const ctx = document.getElementById('c').getContext('2d');
const dec = (v, k) => v.toFixed(k).replace('.', ',');
// dividirAJanela
function dividir(x0, y0, w, h, com) {
  const d = { replay: [x0, y0, w, h] };
  if (!com) return d;
  let resto = h; const entram = {};
  for (const n of ['pedal', 'diferenca', 'velocidade']) { if (resto - ALT[n] < MINIMO) break; resto -= ALT[n]; entram[n] = true; }
  d.replay = [x0, y0, w, resto]; let y = y0 + resto;
  for (const n of ['pedal', 'diferenca', 'velocidade']) if (entram[n]) { d[n] = [x0, y, w, ALT[n]]; y += ALT[n]; }
  return d;
}
const temVisuais = !!c.passoM && !!c.velocidades;
// a grade nos boxes
const GV = 8;
const altGrade = G && G.voltas.length ? 18 + 15 + 15 * Math.min(G.voltas.length, GV) + 13 * Math.min(G.fora.length, 2) + 6 : 0;
const usaGrade = altGrade && H - altGrade >= MINIMO;
const div = dividir(0, 0, W, H - (usaGrade ? altGrade : 0), temVisuais);
const [RX, RY, RW, RH] = div.replay;
// cameraDaCurva
const ref = c.linhas.referencia, pa = ref[0], pb = ref[Math.min(ref.length, 11) - 1];
const du = pb[1] - pa[1], dv = -(pb[0] - pa[0]);
const ang = -Math.PI / 2 - Math.atan2(dv, du), cs = Math.cos(ang), sn = Math.sin(ang);
const girar = (x, z) => { const u = z, v = -x; return [u * cs - v * sn, u * sn + v * cs]; };
let gx0 = Infinity, gx1 = -Infinity, gy0 = Infinity, gy1 = -Infinity;
for (const p of [...c.linhas.voce, ...ref]) { const [gx, gy] = girar(p[0], p[1]); gx0 = Math.min(gx0, gx); gx1 = Math.max(gx1, gx); gy0 = Math.min(gy0, gy); gy1 = Math.max(gy1, gy); }
const k = Math.min((RW - 2 * MARGEM) / Math.max(gx1 - gx0, 1), (RH - 2 * MARGEM - TOPO) / Math.max(gy1 - gy0, 1));
const ax = RX + RW / 2, ay = RY + TOPO + (RH - TOPO) / 2, rcx = (gx0 + gx1) / 2, rcy = (gy0 + gy1) / 2;
const tela = (x, z) => { const [gx, gy] = girar(x, z); return [ax + k * (gx - rcx), ay + k * (gy - rcy)]; };
const mapa = (sx, sy) => { const gx = (sx - ax) / k + rcx, gy = (sy - ay) / k + rcy; const u = gx * cs + gy * sn, v = -gx * sn + gy * cs; return [-v, -u]; };
const uv = (sx, sy) => { const [mx, my] = mapa(sx, sy); return [(mx - img.x0) * img.pxPorMetro, (my - img.y0) * img.pxPorMetro]; };
function posicao(linha, t) { if (t <= linha[0][2]) return linha[0]; const n = linha.length; if (t >= linha[n - 1][2]) return linha[n - 1];
  let i = 1; while (linha[i][2] < t) i++; const p = linha[i - 1], q = linha[i], u = (t - p[2]) / (q[2] - p[2]); return [p[0] + (q[0] - p[0]) * u, p[1] + (q[1] - p[1]) * u]; }
function distancia(linha, t, passo) { const n = linha.length; if (t <= linha[0][2]) return 0; if (t >= linha[n - 1][2]) return (n - 1) * passo;
  let a = 0; while (linha[a + 1][2] <= t) a++; const u = (t - linha[a][2]) / (linha[a + 1][2] - linha[a][2]); return (a + u) * passo; }
// o encaixe dos rotulos (radio_engenheiro.lua, rotulo)
const LUGARES = ['direita', 'esquerda', 'abaixo', 'acima', 'direitaAcima', 'esquerdaAbaixo', 'direitaAbaixo', 'esquerdaAcima'];
const area = [RX + 2, RY + TOPO + 2, RX + RW - 2, RY + RH - 2], ocupados = [], AFAST = [0, 14, 28, 44, 60];
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
function caminho(pts, cor, larg) { ctx.beginPath(); pts.forEach((p, i) => { const [x, y] = tela(p[0], p[1]); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }); ctx.strokeStyle = cor; ctx.lineWidth = larg; ctx.lineJoin = 'round'; ctx.stroke(); }
ctx.fillStyle = 'rgb(91,97,104)'; ctx.fillRect(0, 0, W, H);
ctx.fillStyle = FUNDO_MAPA; ctx.fillRect(RX, RY, RW, RH);
const imagem = new Image();
imagem.onload = () => {
  ctx.save(); ctx.beginPath(); ctx.rect(RX, RY, RW, RH); ctx.clip();
  const P0 = uv(RX, RY), P1 = uv(RX + RW, RY), P2 = uv(RX, RY + RH);
  const U = [P1[0] - P0[0], P1[1] - P0[1]], V = [P2[0] - P0[0], P2[1] - P0[1]], det = U[0] * V[1] - V[0] * U[1];
  const A = RW * V[1] / det, B = RH * -U[1] / det, C = RW * -V[0] / det, D = RH * U[0] / det;
  ctx.setTransform(A, B, C, D, RX - (A * P0[0] + C * P0[1]), RY - (B * P0[0] + D * P0[1])); ctx.drawImage(imagem, 0, 0); ctx.restore();
  curvaDoReplay(); if (div.pedal) pedal(div.pedal); if (div.diferenca) diferenca(div.diferenca); if (div.velocidade) velocidade(div.velocidade);
  if (usaGrade) desenharAGrade(0, H - altGrade, W, altGrade);
  if (G) { ctx.font = '11px "Segoe UI", sans-serif'; ctx.fillStyle = APOIO; ctx.textBaseline = 'top'; ctx.fillText('nos boxes: a última análise, em repetição', RX + 10, RY + RH - 18); }
};
imagem.src = img.url;
function curvaDoReplay() {
  let ta = null, tb = null;
  if (c.voz && c.passoM) { const n = ref.length; ta = Math.max(0, Math.round(c.voz.inicioM / c.passoM)); tb = Math.min(n - 1, Math.round(c.voz.fimM / c.passoM)); if (tb <= ta) ta = null; }
  if (ta !== null) { ctx.lineCap = 'round'; caminho(ref.slice(ta, tb + 1), TRECHO_NA_PISTA, 16); ctx.lineCap = 'butt'; }
  caminho(ref, FANTASMA, 2.5); caminho(c.linhas.voce, VERMELHO, 2.5);
  const r = posicao(ref, T), v = posicao(c.linhas.voce, T);
  const [rsx, rsy] = tela(r[0], r[1]), [vsx, vsy] = tela(v[0], v[1]);
  ocupar(rsx, rsy, 9); ocupar(vsx, vsy, 9);
  let mv = null, mr = null, tv = null, tr = null;
  if (c.minimas) { mv = tela(c.minimas.voce.x, c.minimas.voce.z); mr = tela(c.minimas.referencia.x, c.minimas.referencia.z); ocupar(...mv, 5); ocupar(...mr, 5); }
  if (c.tracado) { tv = tela(...c.tracado.voce); tr = tela(...c.tracado.referencia); ocupar(...tv, 5); ocupar(...tr, 5); }
  if (ta !== null) { const m = ref[Math.floor((ta + tb) / 2)]; const [x, y] = tela(m[0], m[1]); rotulo('trecho da fala', x, y, TEXTO, 'esquerda'); }
  const traco = (m, cor) => { if (!m) return null; const [x, y] = tela(m.x, m.z); ctx.beginPath(); ctx.moveTo(x - 7, y); ctx.lineTo(x + 7, y); ctx.strokeStyle = cor; ctx.lineWidth = 3; ctx.stroke(); ocupar(x, y, 7); return [x, y]; };
  const fv = traco(c.freadas.voce, VERMELHO); traco(c.freadas.referencia, FANTASMA);
  const contra = c.referencia === 'minha_melhor' ? 'da sua melhor' : 'da IA', d = c.freadas.distanciaM;
  if (fv && d !== null) { const m = Math.floor(Math.abs(d) + 0.5); rotulo(m < 1 ? 'você freia no mesmo ponto' : `você freia ${m} m ${d < 0 ? 'antes' : 'depois'} ${contra}`, fv[0], fv[1], VERMELHO, 'direita'); }
  if (c.tracado) { const [tvx, tvy] = tv, [trx, try_] = tr; const am = PEDAL[0];
    if (Math.hypot(tvx - trx, tvy - try_) > 2) { ctx.beginPath(); ctx.moveTo(trx, try_); ctx.lineTo(tvx, tvy); ctx.strokeStyle = am; ctx.lineWidth = 1.5; ctx.stroke();
      const an = Math.atan2(tvy - try_, tvx - trx); ctx.beginPath(); ctx.moveTo(tvx, tvy); ctx.lineTo(tvx - 7 * Math.cos(an - 0.5), tvy - 7 * Math.sin(an - 0.5)); ctx.lineTo(tvx - 7 * Math.cos(an + 0.5), tvy - 7 * Math.sin(an + 0.5)); ctx.closePath(); ctx.fillStyle = am; ctx.fill(); }
    rotulo(`você passa ${dec(c.tracado.distanciaM, 1)} m mais à ${c.tracado.lado}`, (tvx + trx) / 2, (tvy + try_) / 2, am, 'abaixo'); }
  if (c.minimas) { for (const [[x, y], cor] of [[mv, VERMELHO], [mr, FANTASMA]]) { ctx.beginPath(); ctx.arc(x, y, 3.5, 0, 2 * Math.PI); ctx.fillStyle = cor; ctx.fill(); }
    rotulo(`mínima ${Math.floor(c.minimas.voce.kmh + 0.5)} km/h`, mv[0], mv[1], VERMELHO, 'esquerda');
    rotulo(`mínima ${Math.floor(c.minimas.referencia.kmh + 0.5)} km/h`, mr[0], mr[1], FANTASMA, 'direita'); }
  marca(rsx, rsy, MIOLO, FANTASMA); marca(vsx, vsy, '#fff', VERMELHO);
  rotulo(c.rotuloDaReferencia, rsx, rsy, FANTASMA, 'direitaAcima'); rotulo('você', vsx, vsy, TEXTO, 'esquerdaAbaixo');
  ctx.fillStyle = 'rgba(17,18,20,0.78)'; ctx.fillRect(RX, RY, RW, TOPO);
  ctx.font = '12px "Segoe UI", sans-serif'; ctx.fillStyle = TEXTO; ctx.textBaseline = 'top';
  const volta = c.volta ? ` · volta ${c.volta}` : '';
  let alto;
  if (c.voz) { const p = c.voz.perdaS; alto = `${c.curva}, ${c.lado}${volta}` + (p === null ? '' : ` · ${p >= 0 ? 'perde' : 'ganha'} ${dec(Math.abs(p), 2)} s no trecho da fala`); }
  else alto = `${c.curva}, ${c.lado}${volta} · ${c.perdaS >= 0 ? 'perde' : 'ganha'} ${dec(Math.abs(c.perdaS), 2)} s nesta curva`;
  ctx.fillText(alto, RX + 10, RY + 5);
}
function moldura(a, titulo, totalM) { const [x, y, w, h] = a; ctx.fillStyle = FUNDO_MAPA; ctx.fillRect(x, y, w, h - 2);
  const x0 = x + COL, larg = w - COL - 8, total = totalM || Math.max((c.linhas.voce.length - 1) * c.passoM, 1), emX = d => x0 + larg * d / total;
  if (c.voz) { ctx.fillStyle = TRECHO; ctx.fillRect(emX(c.voz.inicioM), y, emX(c.voz.fimM) - emX(c.voz.inicioM), h - 2); }
  if (titulo) { ctx.font = '10px "Segoe UI", sans-serif'; ctx.fillStyle = FRACO; ctx.textBaseline = 'top'; ctx.fillText(titulo, x0 + 2, y + 2); }
  return emX; }
function cursores(a, emX, desl = 0, totalM = Infinity) { for (const [linha, cor] of [[ref, FANTASMA], [c.linhas.voce, VERMELHO]]) { const dd = distancia(linha, T, c.passoM) + desl; if (dd < 0 || dd > totalM) continue; const xx = emX(dd); ctx.beginPath(); ctx.moveTo(xx, a[1]); ctx.lineTo(xx, a[1] + a[3] - 2); ctx.strokeStyle = cor; ctx.lineWidth = 1.5; ctx.stroke(); } }
function pedal(a) { const emX = moldura(a, '');
  const faixa = (linha, y, nome, cor) => { const n = linha.length; let i = 0;
    while (i < n) { const p = linha[i][3]; let j = i; while (j < n - 1 && linha[j + 1][3] === p) j++;
      const de = Math.max(0, (i - 0.5) * c.passoM), ate = Math.min((n - 1) * c.passoM, (j + 0.5) * c.passoM);
      ctx.fillStyle = PEDAL[p]; ctx.fillRect(emX(de), y, Math.max(emX(ate) - emX(de), 1), 10); i = j + 1; }
    ctx.font = '10px "Segoe UI", sans-serif'; ctx.fillStyle = cor; ctx.textBaseline = 'top'; ctx.fillText(nome, a[0] + 4, y - 1); };
  faixa(c.linhas.voce, a[1] + 3, 'você', VERMELHO); faixa(ref, a[1] + 15, c.referencia === 'minha_melhor' ? 'sua' : 'IA', FANTASMA); cursores(a, emX); }
function diferenca(a) { const tr = c.diferencaNoTrecho && c.diferencaNoTrecho.valores.length > 1 ? c.diferencaNoTrecho : null;
  const passo = tr ? tr.passoM : c.passoM, totalM = tr ? tr.comprimentoM : undefined, desl = tr ? tr.entradaDoReplayM : 0;
  const emX = moldura(a, tr ? 'diferença acumulada no trecho da curva (s): sobe quando você perde' : 'diferença acumulada (s): sobe quando você perde', totalM);
  const v = c.linhas.voce, dif = tr ? tr.valores : v.map((p, i) => p[2] - (ref[i] || ref[ref.length - 1])[2]), n = dif.length;
  const maior = Math.max(0.05, ...dif.map(Math.abs)), topo = a[1] + 16, meio = topo + (a[3] - 20) / 2, emY = x => meio - ((a[3] - 22) / 2) * (x / maior);
  ctx.beginPath(); ctx.moveTo(emX(0), meio); ctx.lineTo(emX((n - 1) * passo), meio); ctx.strokeStyle = 'rgba(233,237,242,0.35)'; ctx.lineWidth = 1; ctx.stroke();
  for (let i = 0; i < n - 1; i++) { const xa = emX(i * passo), xb = emX((i + 1) * passo);
    if (dif[i] >= 0 && dif[i + 1] >= 0) ctx.fillStyle = 'rgba(255,162,74,0.35)'; else if (dif[i] <= 0 && dif[i + 1] <= 0) ctx.fillStyle = 'rgba(111,155,255,0.35)'; else continue;
    ctx.beginPath(); ctx.moveTo(xa, meio); ctx.lineTo(xa, emY(dif[i])); ctx.lineTo(xb, emY(dif[i + 1])); ctx.lineTo(xb, meio); ctx.closePath(); ctx.fill(); }
  ctx.beginPath(); dif.forEach((x, i) => i ? ctx.lineTo(emX(i * passo), emY(x)) : ctx.moveTo(emX(0), emY(x))); ctx.strokeStyle = VERMELHO; ctx.lineWidth = 1.5; ctx.stroke();
  const s = c.secoes || {};
  for (const [d, nome] of [[s.freadaM, 'freada'], [s.minimaM, 'mínima'], [s.saidaM, 'saída']]) { if (d === null || d === undefined) continue; const noEixo = d + desl; if (noEixo < 0 || (totalM && noEixo > totalM)) continue; const xx = emX(noEixo);
    for (let yy = topo; yy < a[1] + a[3] - 4; yy += 6) { ctx.beginPath(); ctx.moveTo(xx, yy); ctx.lineTo(xx, Math.min(yy + 3, a[1] + a[3] - 2)); ctx.strokeStyle = 'rgba(233,237,242,0.6)'; ctx.lineWidth = 1; ctx.stroke(); }
    ctx.font = '10px "Segoe UI", sans-serif'; ctx.fillStyle = APOIO; ctx.textBaseline = 'top'; const w = ctx.measureText(nome).width; ctx.fillText(nome, xx - w / 2, a[1] + a[3] - 14); }
  cursores(a, emX, desl, totalM === undefined ? Infinity : totalM); }
function velocidade(a) { const emX = moldura(a, 'velocidade (km/h) pela distância (m)'); const vel = c.velocidades;
  const todas = [...vel.voce, ...vel.referencia], v0 = Math.min(...todas), v1 = Math.max(...todas), emY = x => a[1] + a[3] - 6 - (a[3] - 24) * (x - v0) / Math.max(v1 - v0, 1);
  for (const [serie, cor] of [[vel.referencia, FANTASMA], [vel.voce, VERMELHO]]) { ctx.beginPath(); serie.forEach((x, i) => i ? ctx.lineTo(emX(i * c.passoM), emY(x)) : ctx.moveTo(emX(0), emY(x))); ctx.strokeStyle = cor; ctx.lineWidth = 1.5; ctx.stroke(); }
  const na = (serie, d) => serie[Math.min(serie.length - 1, Math.max(0, Math.round(d / c.passoM)))];
  for (const [m, serie, cor] of [[c.freadas.voce, vel.voce, VERMELHO], [c.freadas.referencia, vel.referencia, FANTASMA]]) { if (!m || m.dM === undefined) continue;
    const xx = emX(m.dM), yy = emY(na(serie, m.dM)); ctx.beginPath(); ctx.moveTo(xx, yy - 6); ctx.lineTo(xx, yy + 6); ctx.strokeStyle = cor; ctx.lineWidth = 3; ctx.stroke(); }
  if (c.minimas) for (const [m, serie, cor] of [[c.minimas.voce, vel.voce, VERMELHO], [c.minimas.referencia, vel.referencia, FANTASMA]]) {
    ctx.beginPath(); ctx.arc(emX(m.dM), emY(na(serie, m.dM)), 3.5, 0, 2 * Math.PI); ctx.fillStyle = cor; ctx.fill(); }
  cursores(a, emX); }
function desenharAGrade(x0, y0, w, h) {
  ctx.fillStyle = FUNDO_MAPA; ctx.fillRect(x0, y0, w, h);
  ctx.textBaseline = 'top'; ctx.font = '10px "Segoe UI", sans-serif'; ctx.fillStyle = APOIO;
  ctx.fillText('Grade da sessão: a perda em cada curva (laranja perde, azul ganha; contorno: citada)', x0 + 6, y0 + 3);
  const nc = G.curvas.length, cw = (w - 40 - 6) / nc, fonte = Math.min(10, cw / 3.6);
  let y = y0 + 18; ctx.font = `${fonte}px "Segoe UI", sans-serif`; ctx.fillStyle = FRACO;
  G.curvas.forEach((n, k) => ctx.fillText(n, x0 + 40 + k * cw + 2, y)); y += 15;
  const cit = new Set(G.citadas.map(c => `${c.volta}:${c.curva}`));
  for (const v of G.voltas.slice(-GV)) { ctx.fillStyle = TEXTO; ctx.fillText(`volta ${v.volta}`, x0 + 4, y + 1);
    v.perdas.forEach((p, k) => { const ax_ = x0 + 40 + k * cw + 1, bx = x0 + 40 + (k + 1) * cw - 1;
      if (p !== null) { const f = 0.15 + 0.75 * Math.min(1, Math.abs(p) / 1.0); ctx.fillStyle = p >= 0 ? `rgba(255,162,74,${f})` : `rgba(111,155,255,${f})`; ctx.fillRect(ax_, y, bx - ax_, 13);
        ctx.fillStyle = Math.abs(p) > 0.6 ? 'rgb(8,9,11)' : TEXTO; ctx.fillText(`${p < 0 ? '−' : ''}${dec(Math.abs(p), 2)} s`, ax_ + 2, y + 1); }
      if (cit.has(`${v.volta}:${G.curvas[k]}`)) { ctx.strokeStyle = VERMELHO; ctx.lineWidth = 2; ctx.strokeRect(ax_, y, bx - ax_, 13); } });
    y += 15; }
  ctx.font = '10px "Segoe UI", sans-serif'; ctx.fillStyle = FRACO;
  for (let i = 0; i < Math.min(G.fora.length, 2); i++) { const f = G.fora[G.fora.length - 1 - i]; ctx.fillText(`fora: volta ${f.volta}: ${f.motivo}${f.citadas && f.citadas.length ? '; citada: ' + f.citadas.join(', ') : ''}`, x0 + 6, y); y += 13; }
}
</script></body></html>"""
SAIDA.write_text(HTML.replace("__CURVA__", json.dumps(curva)).replace("__IMG__", json.dumps(img))
                 .replace("__GRADE__", json.dumps(grade)).replace("__W__", str(W)).replace("__H__", str(H))
                 .replace("__T__", json.dumps(curva["duracaoS"] * FRACAO)), encoding="utf-8")
print(CURVA, "volta", curva["volta"], "t =", round(curva["duracaoS"] * FRACAO, 2), "s", f"{W} x {H}", "boxes" if BOXES else "")
