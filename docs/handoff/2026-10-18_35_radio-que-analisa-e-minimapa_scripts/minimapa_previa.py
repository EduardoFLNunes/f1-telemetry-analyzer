"""Pedido 35, Parte F.6: o minimapa desenhado fora do jogo.

Nao ha como rodar o app Lua fora do jogo. Esta previa repete o desenho de
`radio_engenheiro.lua` num canvas HTML (a mesma projecao `base(x, z) = (z, -x)`, as
mesmas margens, cores, raios e textos) com:

* o minimapa que a rota `/api/radio/minimapa` entregou na janela de teste (a referencia
  escolhida, a sua melhor, e as curvas da ultima analise);
* o carro num instante real da sessao de 18/10 e o fantasma e a diferenca calculados pela
  conta do app (as mesmas funcoes de `minimapa_offline.py`).

O fundo cinza esta no lugar da imagem do jogo. A captura e do Edge sem janela (headless).

Uso (na pasta backend): python minimapa_previa.py <minimapa.json> <pasta da sessao> <tempo da volta s> <cronometro_s> <saida.html>

A volta e escolhida pelo tempo dela (o maior cronometro), porque a numeracao das voltas
na gravacao e a do radio nao sao a mesma.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, ".")
from ml.data.recordings import Session, iter_laps  # noqa: E402

MINI, PASTA, TEMPO_DA_VOLTA, CRONOMETRO, SAIDA = Path(sys.argv[1]), Path(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), Path(sys.argv[5])
mm = json.loads(MINI.read_text(encoding="utf-8"))
ref = mm["referencia"]
pontos = ref["pontos"]


def fantasma_em(t_ref):
    n = len(pontos)
    i = 1
    while i < n - 1 and pontos[i][2] <= t_ref:
        i += 1
    a, b = pontos[i - 1], pontos[i]
    u = max(0.0, min(1.0, (t_ref - a[2]) / (b[2] - a[2]))) if b[2] > a[2] else 0.0
    return a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u


def tempo_perto(x, z):
    melhor, tempo = math.inf, None
    for i in range(1, len(pontos)):
        p, q = pontos[i - 1], pontos[i]
        dx, dz = q[0] - p[0], q[1] - p[1]
        l2 = dx * dx + dz * dz
        u = max(0.0, min(1.0, ((x - p[0]) * dx + (z - p[1]) * dz) / l2)) if l2 > 0 else 0.0
        d2 = (p[0] + dx * u - x) ** 2 + (p[1] + dz * u - z) ** 2
        if d2 < melhor:
            melhor, tempo = d2, p[2] + (q[2] - p[2]) * u
    return tempo


carro = None
for lap in iter_laps(Session(session_id=PASTA.name, directory=PASTA, track="vhe_interlagos")):
    if abs(float(lap.frame["lap_time_s"].max()) - TEMPO_DA_VOLTA) > 0.15:
        continue
    for d in lap.frame.to_dict("records"):
        if d.get("lap_time_s") is not None and d["lap_time_s"] >= CRONOMETRO and d.get("x") == d.get("x"):
            carro = (float(d["x"]), float(d["z"]), float(d["lap_time_s"]))
            break
    if carro:
        break
x, z, tv = carro
t_carro = tv + ref["tempoNaLinhaDoJogoS"]
fx, fz = fantasma_em(t_carro)
dif = t_carro - tempo_perto(x, z)
instante = {"carro": [x, z], "fantasma": [fx, fz], "diferenca": dif, "tipo": ref["tipo"],
            "tempoDaVoltaS": TEMPO_DA_VOLTA, "cronometroS": tv, "sessao": PASTA.name}
print(json.dumps(instante))

HTML = """<!doctype html><html><head><meta charset="utf-8"><title>[teste] minimapa fora do jogo</title>
<style>html,body{margin:0;background:#5b6168}canvas{display:block}</style></head><body>
<canvas id="c" width="300" height="300"></canvas><script>
const mm = __MINI__, agora = __AGORA__;
// As constantes e as cores de radio_engenheiro.lua.
const TOPO = 30, MARGEM = 12, W = 300, H = 300;
const cor = (r, g, b, a) => `rgba(${Math.round(r * 255)},${Math.round(g * 255)},${Math.round(b * 255)},${a})`;
const CORES = { painel: cor(0.031, 0.035, 0.043, 0.62), texto: cor(0.949, 0.957, 0.961, 1), apoio: cor(0.72, 0.76, 0.80, 1),
  vermelho: cor(0.882, 0.024, 0, 1), voce: cor(1, 1, 1, 1), fantasma: cor(0.914, 0.929, 0.949, 0.9),
  fantasmaMiolo: cor(0.031, 0.035, 0.043, 0.6), pista: cor(0.165, 0.184, 0.212, 1), borda: cor(0.914, 0.929, 0.949, 0.35),
  perda: cor(1, 0.635, 0.29, 1), ganho: cor(0.435, 0.608, 1, 1) };
const ctx = document.getElementById('c').getContext('2d');
const C = mm.pista.contornos;
let umin = Infinity, umax = -Infinity, vmin = Infinity, vmax = -Infinity;
for (const c of C) for (const q of c) { const u = q[1], v = -q[0];
  umin = Math.min(umin, u); umax = Math.max(umax, u); vmin = Math.min(vmin, v); vmax = Math.max(vmax, v); }
const larg = W - 2 * MARGEM, alt = H - 2 * MARGEM - TOPO;
const k = Math.min(larg / (umax - umin), alt / (vmax - vmin));
const ox = MARGEM + (larg - k * (umax - umin)) / 2 - k * umin, oy = MARGEM + TOPO + (alt - k * (vmax - vmin)) / 2 - k * vmin;
const tela = (x, z) => [ox + k * z, oy - k * x];
function caminho(pts, fechado) { ctx.beginPath(); pts.forEach((p, i) => (i ? ctx.lineTo(...p) : ctx.moveTo(...p))); if (fechado) ctx.closePath(); }
ctx.fillStyle = CORES.painel; ctx.beginPath(); ctx.roundRect(0, 0, W, H, 10); ctx.fill();
// o contorno do asfalto tratado (radio_engenheiro.lua: CORES.contorno, 1,6 px)
for (const c of C) { caminho(c.map((q) => tela(q[0], q[1])), true); ctx.strokeStyle = 'rgba(233,237,242,0.6)'; ctx.lineWidth = 1.6; ctx.lineJoin = 'round'; ctx.stroke(); }
const L = mm.linhaDoS0; caminho([tela(L[0][0], L[0][1]), tela(L[1][0], L[1][1])], false); ctx.strokeStyle = CORES.texto; ctx.lineWidth = 2; ctx.stroke();
ctx.font = '11px "Segoe UI", sans-serif'; ctx.textBaseline = 'top';
for (const c of mm.curvasDaAnalise) { const [qx, qy] = tela(c.x, c.z); ctx.beginPath(); ctx.arc(qx, qy, 7, 0, 2 * Math.PI);
  ctx.strokeStyle = CORES.perda; ctx.lineWidth = 2; ctx.stroke(); ctx.fillStyle = CORES.perda; ctx.fillText(c.curva, qx + 9 + 26 > W ? qx - 9 - 26 : qx + 9, qy - 7); }
// o fantasma e o carro
function marca(p, r, miolo, borda, esp) { ctx.beginPath(); ctx.arc(p[0], p[1], r, 0, 2 * Math.PI); ctx.fillStyle = miolo; ctx.fill(); ctx.strokeStyle = borda; ctx.lineWidth = esp; ctx.stroke(); }
marca(tela(...agora.fantasma), 5, CORES.fantasmaMiolo, CORES.fantasma, 2);
marca(tela(...agora.carro), 5.5, CORES.voce, CORES.vermelho, 2.5);
// a diferença
const d = agora.diferenca, txt = (d >= 0 ? '+' : '\\u2212') + Math.abs(d).toFixed(2).replace('.', ',') + ' s';
ctx.font = '17px "Segoe UI", sans-serif'; ctx.fillStyle = d > 0 ? CORES.perda : CORES.ganho; ctx.fillText(txt, MARGEM, 4);
ctx.font = '11px "Segoe UI", sans-serif'; ctx.fillStyle = CORES.apoio;
ctx.fillText(agora.tipo === 'minha_melhor' ? 'para a sua melhor' : 'para a volta da IA', MARGEM + 82, 10);
</script></body></html>"""
SAIDA.write_text(HTML.replace("__MINI__", json.dumps(mm)).replace("__AGORA__", json.dumps(instante)), encoding="utf-8")
