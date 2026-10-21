"""Pedido 35, depois do teste no jogo: o mapa aproximado desenhado fora do jogo.

O app Lua nao roda fora do jogo. Esta previa repete, num canvas HTML, as contas de
`aproximado()` em `radio_engenheiro.lua`, com os mesmos nomes:

* a camera: base(x, z) = (z, -x), girada pela direcao da referencia perto do carro;
* a imagem da pista: cada canto da janela volta para o mundo e dai para a imagem
  (a mesma funcao `uv`); o canvas usa a transformacao afim que leva esses tres cantos
  aos cantos da janela, que e o que o `ui.drawImageQuad` faz;
* os tracados pintados pelo pedal, o nome das curvas, o fantasma e o carro.

Os dados: o minimapa como a rota manda (a volta da IA, com os pedais e as curvas), a
`pista_detalhada.png` e a `pista.json` da pasta do app, e um instante real de uma
sessao gravada (o seu tracado vem da gravacao, de 1,5 em 1,5 m, desde a linha).

Uso (na pasta backend): python aproximado_previa.py <pasta da sessao> <tempo da volta s> <s do carro m> <saida.html>
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, ".")
from core.assisted_analysis.reference_model import DriverReferenceModel, model_path  # noqa: E402
from core.leitura.arquivos import LeitorDoStore  # noqa: E402
from core.radio import minimapa  # noqa: E402
from core.radio.analise import Pista  # noqa: E402
from core.radio.janelas import carregar_geometria  # noqa: E402
from ml.data.recordings import Session, iter_laps  # noqa: E402

PASTA, TEMPO_DA_VOLTA, S_DO_CARRO, SAIDA = Path(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3]), Path(sys.argv[4])
REPO = Path("..").resolve()
APP = REPO / "tools" / "csp_app" / "radio_engenheiro"

track = carregar_geometria(REPO)
pista = Pista.da_geometria(track)
modelo = DriverReferenceModel.load(model_path(REPO, "vhe_interlagos"))
volta_ref = LeitorDoStore().ler_volta(REPO, str(modelo.reference_lap_id))
mm = minimapa.montar(track, pista.segmentos, volta_ref, modelo.reference_kind, None, minimapa.linha_do_jogo_m(REPO))
pj = json.loads((APP / "pista.json").read_text(encoding="utf-8"))
ref = mm["referencia"]
pontos = ref["pontos"]
kd = cKDTree(np.column_stack([track.x, track.z]))

quadro, rastro = None, []
for lap in iter_laps(Session(session_id=PASTA.name, directory=PASTA, track="vhe_interlagos")):
    f = lap.frame
    if abs(float(f["lap_time_s"].max()) - TEMPO_DA_VOLTA) > 0.15:
        continue
    for d in f.to_dict("records"):
        if d.get("x") != d.get("x") or d.get("lap_time_s") is None:
            continue
        x, z = float(d["x"]), float(d["z"])
        # o seu tracado, como o gravarORastro: um ponto a cada 1,5 m, com o pedal
        if not rastro or (x - rastro[-1][0]) ** 2 + (z - rastro[-1][1]) ** 2 >= 1.5 ** 2:
            pedal = 2 if (d.get("brake") or 0) >= 0.15 else 1 if (d.get("throttle") or 0) >= 0.9 else 0
            rastro.append([x, z, pedal])
        s = float(track.s[kd.query([x, z])[1]])
        if S_DO_CARRO <= s < S_DO_CARRO + 50 and float(d["lap_time_s"]) > 0.5:
            quadro = d
            break
    break
x, z, tv = float(quadro["x"]), float(quadro["z"]), float(quadro["lap_time_s"])
t_carro = tv + ref["tempoNaLinhaDoJogoS"]
# o fantasma pelo tempo (fantasmaEm) e o ponto da referencia mais perto do carro (tempoDaReferenciaPerto)
i = 1
while i < len(pontos) - 1 and pontos[i][2] <= t_carro:
    i += 1
a, b = pontos[i - 1], pontos[i]
u = max(0.0, min(1.0, (t_carro - a[2]) / (b[2] - a[2]))) if b[2] > a[2] else 0.0
i_fantasma, fx, fz = i, a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u
melhor, t_ref, i_carro = math.inf, None, None
for j in range(1, len(pontos)):
    p, q = pontos[j - 1], pontos[j]
    dx, dz = q[0] - p[0], q[1] - p[1]
    l2 = dx * dx + dz * dz
    uu = max(0.0, min(1.0, ((x - p[0]) * dx + (z - p[1]) * dz) / l2)) if l2 > 0 else 0.0
    d2 = (p[0] + dx * uu - x) ** 2 + (p[1] + dz * uu - z) ** 2
    if d2 < melhor:
        melhor, t_ref, i_carro = d2, p[2] + (q[2] - p[2]) * uu, j
instante = {"carro": [x, z], "cronometroS": tv, "volta": 8, "fantasma": [fx, fz], "iFantasma": i_fantasma,
            "iCarro": i_carro, "diferenca": t_carro - t_ref, "tipo": ref["tipo"], "sessao": PASTA.name,
            "tempoDaVoltaS": TEMPO_DA_VOLTA}
print(json.dumps({k: v for k, v in instante.items()}))

HTML = r"""<!doctype html><html><head><meta charset="utf-8"><title>[teste] mapa aproximado fora do jogo</title>
<style>html,body{margin:0;background:#5b6168}canvas{display:block}</style></head><body>
<canvas id="c" width="360" height="360"></canvas><script>
const mm = __MM__, img = __IMG__, rastro = __RASTRO__, agora = __AGORA__, rotulos = __ROTULOS__;
const W = 360, H = 360, ZOOM = 120, CENTRO_VERTICAL = 0.62, TOPO = 30, MARGEM = 12;
const cor = (r, g, b, a) => `rgba(${Math.round(r * 255)},${Math.round(g * 255)},${Math.round(b * 255)},${a})`;
const PEDAL = [[0.961, 0.773, 0.259], [0.239, 0.863, 0.518], [1.0, 0.353, 0.373]];
const ctx = document.getElementById('c').getContext('2d');
const [x, z] = agora.carro;
const pts = mm.referencia.pontos;
// a direcao: a da referencia perto do carro (iCarro e iCarro + 4, indices do Lua)
const a = pts[agora.iCarro - 1], b = pts[Math.min(pts.length, agora.iCarro + 4) - 1];
const du = b[1] - a[1], dv = -(b[0] - a[0]);
const ang = -Math.PI / 2 - Math.atan2(dv, du);
const cs = Math.cos(ang), sn = Math.sin(ang), k = Math.min(W, H) / ZOOM;
const cx = W * 0.5, cy = H * CENTRO_VERTICAL, bu0 = z, bv0 = -x;
const tela = (px, pz) => { const eu = pz - bu0, ev = -px - bv0; return [cx + k * (eu * cs - ev * sn), cy + k * (eu * sn + ev * cs)]; };
function uv(sx, sy) {
  const ex = (sx - cx) / k, ey = (sy - cy) / k;
  const bu = bu0 + ex * cs + ey * sn, bv = bv0 - ex * sn + ey * cs;
  const mx = -bv, my = -bu;
  return [(mx - img.x0) * img.pxPorMetro / img.largura, (my - img.y0) * img.pxPorMetro / img.altura];
}
ctx.fillStyle = cor(0.067, 0.071, 0.078, 0.92); ctx.beginPath(); ctx.roundRect(0, 0, W, H, 6); ctx.fill();
const imagem = new Image();
imagem.onload = () => {
  // o drawImageQuad: os cantos (0,0), (W,0) e (0,H) da janela recebem os uv deles
  const P0 = uv(0, 0).map((v, i) => v * (i ? img.altura : img.largura));
  const P1 = uv(W, 0).map((v, i) => v * (i ? img.altura : img.largura));
  const P2 = uv(0, H).map((v, i) => v * (i ? img.altura : img.largura));
  const U = [P1[0] - P0[0], P1[1] - P0[1]], V = [P2[0] - P0[0], P2[1] - P0[1]];
  const det = U[0] * V[1] - V[0] * U[1];
  // tela = diag(W, H) * inv([U V]) * (px - P0)
  const ia = V[1] / det, ib = -U[1] / det, ic = -V[0] / det, id = U[0] / det;
  const A = W * ia, B = H * ib, C = W * ic, D = H * id;
  ctx.save();
  ctx.setTransform(A, B, C, D, -(A * P0[0] + C * P0[1]), -(B * P0[0] + D * P0[1]));
  ctx.drawImage(imagem, 0, 0);
  ctx.restore();
  resto();
};
imagem.src = img.url;
function tracar(lista, ate, ip, alfa, largura) {
  let aberto = false, corAtual = 0, ax = null, az = null;
  ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.lineWidth = largura;
  const fechar = () => { const c = PEDAL[corAtual]; ctx.strokeStyle = cor(c[0], c[1], c[2], alfa); ctx.stroke(); };
  for (let i = 0; i < Math.min(ate, lista.length); i++) {
    const p = lista[i];
    const [sx, sy] = tela(p[0], p[1]);
    const visivel = sx > -40 && sx < W + 40 && sy > -40 && sy < H + 40;
    const pedal = p[ip] || 0;
    const salto = ax !== null && (p[0] - ax) ** 2 + (p[1] - az) ** 2 > 400;
    if (aberto && (!visivel || salto || pedal !== corAtual)) { if (visivel && !salto) ctx.lineTo(sx, sy); fechar(); aberto = false; }
    if (visivel) { if (!aberto) { ctx.beginPath(); ctx.moveTo(sx, sy); aberto = true; corAtual = pedal; } else ctx.lineTo(sx, sy); }
    ax = p[0]; az = p[1];
  }
  if (aberto) fechar();
}
function marca(px, py, r, miolo, borda, esp) { ctx.beginPath(); ctx.arc(px, py, r, 0, 2 * Math.PI); ctx.fillStyle = miolo; ctx.fill(); ctx.lineWidth = esp; ctx.strokeStyle = borda; ctx.stroke(); }
function rotulo(t, tam, px, py, c) { ctx.font = `${tam}px "Segoe UI", sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillStyle = c; ctx.fillText(t, px, py); }
function resto() {
  tracar(pts, agora.iFantasma + 1, 3, 0.6, 3.5);
  tracar(rastro, rastro.length, 2, 1.0, 5);
  for (const c of rotulos) { const [sx, sy] = tela(c.x, c.z); if (sx > 12 && sx < W - 12 && sy > TOPO + 8 && sy < H - 8) rotulo(c.curva, 12, sx, sy, cor(0.914, 0.929, 0.949, 0.75)); }
  const [gx, gy] = tela(agora.fantasma[0], agora.fantasma[1]);
  marca(gx, gy, 8, cor(0.031, 0.035, 0.043, 0.6), cor(0.914, 0.929, 0.949, 0.9), 2.5);
  rotulo(agora.tipo === 'minha_melhor' ? 'Sua melhor' : 'IA', 12, gx, gy - 16, cor(0.949, 0.957, 0.961, 1));
  marca(cx, cy, 8.5, '#ffffff', cor(0.882, 0.024, 0, 1), 2.5);
  rotulo('Você · V' + agora.volta, 12, cx, cy + 18, cor(0.949, 0.957, 0.961, 1));
  ctx.fillStyle = cor(0.067, 0.071, 0.078, 0.78); ctx.beginPath(); ctx.roundRect(0, 0, W, TOPO + 2, 6); ctx.fill();
  const d = agora.diferenca, txt = (d >= 0 ? '+' : '−') + Math.abs(d).toFixed(2).replace('.', ',') + ' s';
  ctx.textAlign = 'left'; ctx.textBaseline = 'top';
  ctx.font = '17px "Segoe UI", sans-serif'; ctx.fillStyle = d > 0 ? cor(1, 0.635, 0.29, 1) : cor(0.435, 0.608, 1, 1); ctx.fillText(txt, MARGEM, 4);
  ctx.font = '11px "Segoe UI", sans-serif'; ctx.fillStyle = cor(0.72, 0.76, 0.80, 1);
  ctx.fillText(agora.tipo === 'minha_melhor' ? 'para a sua melhor' : 'para a volta da IA', MARGEM + 82, 10);
}
</script></body></html>"""
img = dict(pj["imagem"], url=(APP / pj["imagem"]["arquivo"]).as_uri())
html = (HTML.replace("__MM__", json.dumps(mm)).replace("__IMG__", json.dumps(img)).replace("__RASTRO__", json.dumps(rastro))
        .replace("__AGORA__", json.dumps(instante)).replace("__ROTULOS__", json.dumps(mm["curvas"])))
SAIDA.write_text(html, encoding="utf-8")
