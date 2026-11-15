"""Pedido 45, Parte F.4: a janela do replay do jogo, fora do jogo.

Repete, num canvas HTML, as contas da janela do app do jogo (`radio_engenheiro.lua`, versao 0.5.0):

* `cameraDaCurva` (a de antes, a curva inteira encaixada; a de depois, 80 m no lado menor, o centro entre os
  dois carros, afastando so o necessario), com a `pista_detalhada.png` recortada e girada;
* `desenharAsVoltas`: a lista das voltas e a grade, nos boxes.

Os dados sao os das rotas `/api/radio/replay-da-volta` e `/api/radio/voltas`, numa passagem real da sessao
pelo radio (`radio_depois.py`, com GUARDAR_REPLAYS=1).

Uso: python previa.py camera <passagem.json> <volta> <saida.html>
     python previa.py voltas <passagem.json> <largura> <altura> <saida.html>
"""
import json
import sys
from pathlib import Path

MODO = sys.argv[1]
APP = Path(__file__).resolve().parents[2] / "tools" / "csp_app" / "radio_engenheiro"
pj = json.loads((APP / "pista.json").read_text(encoding="utf-8"))
img = dict(pj["imagem"], url=pj["imagem"]["arquivo"])  # servida junto com o HTML
dados = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))

JS_COMUM = r"""
const IMG = %IMG%;
const ENQ = 1.0, APROX = 0.8, MARGEM = 18;
function pos(l, t) { const n = l.length; if (t <= l[0][2]) return [l[0][0], l[0][1]]; if (t >= l[n-1][2]) return [l[n-1][0], l[n-1][1]];
  let a = 0, b = n-1; while (b-a > 1) { const m = (a+b)>>1; if (l[m][2] <= t) a = m; else b = m; }
  const p = l[a], q = l[b], u = q[2] > p[2] ? (t-p[2])/(q[2]-p[2]) : 0; return [p[0]+(q[0]-p[0])*u, p[1]+(q[1]-p[1])*u]; }
// `cameraDaCurva` do app do jogo; `perto` = false: a de antes (a curva inteira).
function camera(c, t, real, zoom, W, H, topo, perto) {
  const ref = c.linhas.referencia, a = ref[0], b = ref[Math.min(ref.length-1, 10)];
  const ang = -Math.PI/2 - Math.atan2(-(b[0]-a[0]), b[1]-a[1]), cs = Math.cos(ang), sn = Math.sin(ang);
  const gir = (x, z) => { const u = z, v = -x; return [u*cs - v*sn, u*sn + v*cs]; };
  let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
  for (const l of [c.linhas.voce, ref]) for (const p of l) { const g = gir(p[0], p[1]); x0 = Math.min(x0, g[0]); x1 = Math.max(x1, g[0]); y0 = Math.min(y0, g[1]); y1 = Math.max(y1, g[1]); }
  const uX = W-2*MARGEM, uY = H-2*MARGEM-topo;
  const kC = Math.min(uX/Math.max(x1-x0, 1), uY/Math.max(y1-y0, 1));
  let k = kC, rcx = (x0+x1)/2, rcy = (y0+y1)/2;
  if (perto) {
    const gv = gir(...pos(c.linhas.voce, t)), gr = gir(...pos(ref, t));
    const kP = Math.min(uX, uY)/zoom, kD = Math.min(uX/Math.max(Math.abs(gv[0]-gr[0]), .001), uY/Math.max(Math.abs(gv[1]-gr[1]), .001));
    const f = Math.max(0, Math.min(1, (real-ENQ)/APROX)), s = f*f*(3-2*f);
    k = kC*Math.pow(Math.min(kP, kD)/kC, s); rcx += ((gv[0]+gr[0])/2-rcx)*s; rcy += ((gv[1]+gr[1])/2-rcy)*s;
  }
  const ax = W/2, ay = topo+(H-topo)/2;
  return { ang, k, ax, ay, rcx, rcy, tela: (x, z) => { const g = gir(x, z); return [ax+k*(g[0]-rcx), ay+k*(g[1]-rcy)]; } };
}
function desenharCurva(ctx, c, t, real, W, H, perto, imagem) {
  const topo = (perto && c.textoDaVoz) ? 42 : 24;
  const cam = camera(c, t, real, 80, W, H, topo, perto);
  ctx.save(); ctx.beginPath(); ctx.rect(0, 0, W, H); ctx.clip();
  ctx.fillStyle = '#111214'; ctx.fillRect(0, 0, W, H);
  ctx.save(); ctx.translate(cam.ax, cam.ay); ctx.scale(cam.k, cam.k); ctx.translate(-cam.rcx, -cam.rcy); ctx.rotate(cam.ang);
  // da imagem ao mapa: (coluna, linha) -> (u, v) = (z, -x)
  const p = IMG.pxPorMetro; ctx.transform(0, -1/p, -1/p, 0, -IMG.y0, -IMG.x0); ctx.drawImage(imagem, 0, 0); ctx.restore();
  const linha = (pts, cor, w) => { ctx.beginPath(); pts.forEach((q, i) => { const s = cam.tela(q[0], q[1]); i ? ctx.lineTo(s[0], s[1]) : ctx.moveTo(s[0], s[1]); }); ctx.strokeStyle = cor; ctx.lineWidth = w; ctx.stroke(); };
  const tr = c.voz || c.causa;
  if (tr && perto && c.passoM) { const a = Math.round(tr.inicioM/c.passoM), b = Math.round(tr.fimM/c.passoM); linha(c.linhas.referencia.slice(a, b+1), 'rgba(255,255,255,.32)', 16); }
  linha(c.linhas.referencia, 'rgba(233,237,242,.9)', 2.5); linha(c.linhas.voce, '#e10600', 2.5);
  ctx.font = '600 11px "Segoe UI"';
  const marca = (m, cor) => { if (!m) return; const s = cam.tela(m.x, m.z); ctx.fillStyle = cor; ctx.fillRect(s[0]-7, s[1]-1.5, 14, 3); };
  if (c.freadas) { marca(c.freadas.voce, '#e10600'); marca(c.freadas.referencia, 'rgba(233,237,242,.9)'); }
  const car = (l, miolo, borda, nome, dx, dy) => { const s = cam.tela(...pos(l, t)); ctx.beginPath(); ctx.arc(s[0], s[1], 6.5, 0, 7); ctx.fillStyle = miolo; ctx.fill(); ctx.lineWidth = 2.5; ctx.strokeStyle = borda; ctx.stroke();
    const w = ctx.measureText(nome).width+6, bx = Math.min(W-w-2, Math.max(2, s[0]+dx)), by = Math.min(H-17, Math.max(topo+2, s[1]+dy)); ctx.fillStyle = 'rgba(8,9,11,.7)'; ctx.fillRect(bx, by, w, 15); ctx.fillStyle = borda; ctx.fillText(nome, bx+3, by+12); };
  car(c.linhas.referencia, 'rgba(8,9,11,.6)', 'rgba(233,237,242,.9)', c.rotuloDaReferencia, 8, -22);
  car(c.linhas.voce, '#fff', '#e10600', 'você', -40, 8);
  ctx.fillStyle = 'rgba(8,9,11,.8)'; ctx.fillRect(0, 0, W, topo);
  ctx.fillStyle = '#f2f4f5'; ctx.font = '600 12px "Segoe UI"';
  const alto = c.voltaInteira ? 'volta '+c.volta : c.curva+', '+c.lado+' · volta '+c.volta+' · '+(c.perdaS >= 0 ? 'perde ' : 'ganha ')+Math.abs(c.perdaS).toFixed(2).replace('.', ',')+' s nesta curva';
  ctx.fillText(alto, 10, 16);
  if (perto && c.textoDaVoz) { ctx.fillStyle = '#ffa24a'; ctx.font = '600 11px "Segoe UI"'; ctx.fillText(c.textoDaVoz, 10, 34); }
  ctx.restore();
}
"""

if MODO == "camera":
    VOLTA, SAIDA = sys.argv[3], Path(sys.argv[4])
    amostra = dados["amostras"][VOLTA]
    curvas = {k: amostra[k]["curvas"][0] for k in ("C01", "C06", "C12") if amostra.get(k)}
    html = """<!doctype html><meta charset="utf-8"><title>[teste] previa da camera</title>
<body style="margin:0;background:#08090b;color:#b8c1cc;font:12px Segoe UI"><div id="f" style="padding:8px"></div><script>
""" + JS_COMUM.replace("%IMG%", json.dumps(img)) + """
const CURVAS = """ + json.dumps(curvas, ensure_ascii=False) + """;
const im = new Image(); im.src = IMG.url; im.onload = () => {
  const f = document.getElementById('f');
  const tam = [[300,300,"300 x 300"],[420,300,"420 x 300"],[560,400,"boxes: area do replay em 840 x 600"]];
  for (const nome of Object.keys(CURVAS)) {
    const c = CURVAS[nome];
    const titulo = document.createElement('div'); titulo.textContent = nome+': antes (a curva inteira) e depois (1 s, 2,5 s e no trecho da causa)'; titulo.style.margin = '8px 0 4px'; f.appendChild(titulo);
    const ta = c.causa && c.passoM ? c.linhas.voce[Math.min(c.linhas.voce.length-1, Math.round((c.causa.inicioM+c.causa.fimM)/2/c.passoM))][2] : c.duracaoS*0.55;
    for (const [W, H, rot] of tam) {
      const lin = document.createElement('div'); lin.style.cssText = 'display:flex;gap:6px;margin-bottom:6px;align-items:flex-start';
      const quadros = [['antes', ta, 99, false], ['depois, começo (0,5 s)', 0, 0.5, true], ['depois, aproximando', Math.min(ta, 1.5), 1.4+Math.min(ta,1.5), true], ['depois, no trecho', ta, ta+1.8, true]];
      for (const [leg, t, real, perto] of quadros) {
        const d = document.createElement('div'); d.innerHTML = '<div style="margin-bottom:2px">'+rot+' · '+leg+'</div>';
        const cv = document.createElement('canvas'); cv.width = W; cv.height = H; d.appendChild(cv); lin.appendChild(d);
        desenharCurva(cv.getContext('2d'), c, t, real, W, H, perto, im);
      }
      f.appendChild(lin);
    }
  }
};
</script>"""
else:
    W, H, SAIDA = int(sys.argv[3]), int(sys.argv[4]), Path(sys.argv[5])
    html = """<!doctype html><meta charset="utf-8"><title>[teste] previa da lista</title>
<body style="margin:0;background:#08090b"><canvas id="c" width=""" + str(W) + """ height=""" + str(H) + """></canvas><script>
const g = """ + json.dumps(dados["lista"], ensure_ascii=False) + """;
const W = """ + str(W) + """, H = """ + str(H) + """, ctx = document.getElementById('c').getContext('2d');
const LINHA = 16, CAB = 34, ROD = 18, COL = 172, E = {valida:'válida', invalida:'inválida', rodada:'rodada', ia:'IA', incompleta:'incompleta'};
const nf = (v, c) => v.toFixed(c).replace('.', ',');
const tempo = (s) => { const m = Math.floor(s/60), r = s-60*m; return m+':'+(r<10?'0':'')+nf(r,3); };
const T = (t, x, y, cor, tam) => { ctx.fillStyle = cor; ctx.font = '600 '+tam+'px "Segoe UI"'; ctx.fillText(t, x, y+tam); };
ctx.fillStyle = 'rgba(17,18,20,.95)'; ctx.fillRect(0, 0, W, H);
T('Voltas da sessão · abre esta volta no app do Windows; o jogo vai para segundo plano', 6, 4, '#b8c1cc', 10);
ctx.fillStyle = '#e10600'; ctx.fillRect(W-90, 2, 84, 15); T('Abrir no app', W-83, 3, '#f2f4f5', 11);
const nc = g.curvas.length, cw = (W-COL-8)/nc, f = Math.min(10, cw/3.6);
g.curvas.forEach((n, k) => T(n, COL+k*cw+2, 19, '#8c949c', f));
g.voltas.forEach((v, i) => {
  const y = CAB+i*LINHA, cor = v.temReplay ? '#f2f4f5' : '#8c949c';
  T('V'+v.volta, 6, y+2, cor, 10);
  if (v.tempoS) T(tempo(v.tempoS), 32, y+2, cor, 10);
  if (v.difMelhorS !== null) T(g.melhorVolta === v.volta ? 'melhor' : (v.difMelhorS >= 0 ? '+' : '−')+nf(Math.abs(v.difMelhorS), 3), 82, y+2, g.melhorVolta === v.volta ? '#6f9bff' : '#b8c1cc', 10);
  T(E[v.estado] || v.estado, 124, y+3, v.estado === 'valida' ? '#8c949c' : '#ffa24a', 9);
  let tem = false;
  v.perdas.forEach((p, k) => { if (p === null) return; tem = true;
    const a = COL+k*cw+1, fo = .15+.75*Math.min(1, Math.abs(p));
    ctx.fillStyle = p >= 0 ? 'rgba(255,162,74,'+fo+')' : 'rgba(111,155,255,'+fo+')'; ctx.fillRect(a, y+1, cw-2, LINHA-2);
    T((p < 0 ? '−' : '')+nf(Math.abs(p), 2), a+2, y+2, Math.abs(p) > .6 ? '#08090b' : '#f2f4f5', f);
    if ((v.citadas || []).includes(g.curvas[k])) { ctx.strokeStyle = '#e10600'; ctx.lineWidth = 1.5; ctx.strokeRect(a, y+1, cw-2, LINHA-2); } });
  if (!tem) T(v.motivo.slice(0, 80), COL+2, y+3, '#8c949c', 9);
});
T('clique na volta para a volta inteira; numa célula, para a curva', 6, H-ROD+3, '#8c949c', 10);
</script>"""
SAIDA.write_text(html, encoding="utf-8")
