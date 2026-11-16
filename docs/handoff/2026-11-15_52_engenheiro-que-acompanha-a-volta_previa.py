"""Pedido 52, Parte D.2: as previas da janela do engenheiro e da marca na pista, na C01 e na C06.

Nao ha como rodar o app Lua fora do jogo. A previa repete o desenho de `engenheiro` (`radio_engenheiro.lua`) num
SVG: as mesmas cores (o painel, a faixa vermelha, "ENGENHEIRO", o texto e o apoio), os mesmos tamanhos de fonte
e os mesmos textos (a frase da janela, "a N m" e "so na janela"). A frase e o ponto vem do engenheiro de
verdade (`core.engenheiro`), com a volta do modelo, os marcos e a regra do ADR 0033.

A marca na pista: a vista do piloto (1,0 m acima da linha da referencia, olhando ao longo da pista), 120 m e
40 m antes do ponto da acao, em perspectiva: as bordas da pista (o corredor da geometria oficial), as placas de
freada como postes com o numero, as zebras e a faixa da marca (1,5 m x 6 m, centrada na linha da referencia,
na cor do fantasma), como o `render.quad` desenha. O asfalto e plano (a altura da geometria); no jogo, a
altura vem do `physics.raycastTrack`.

Uso (na pasta backend): python <este arquivo> <saida.html> <rodada da D.1 com o engenheiro (12/11).json>
"""
import html
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")
from core.engenheiro import marcos as M  # noqa: E402
from core.engenheiro import regras as R  # noqa: E402
from core.engenheiro.preparar import volta_do_modelo  # noqa: E402
from core.radio.janelas import carregar_geometria  # noqa: E402

REPO = Path("..").resolve()
track = carregar_geometria(REPO)
L = float(track.length)
marcos = M.encontrar([REPO], "vhe_interlagos")["marcos"]
pts_marcos = M.pontos_de_referencia(marcos)
_, g, total = volta_do_modelo()
trechos = R.trechos_da_pista(track)
duracoes = {a["fala"]: a["duracaoS"] for a in json.loads(
    (REPO / "docs/handoff/2026-11-15_52_engenheiro-que-acompanha-a-volta_duracao_dos_avisos.json").read_text(encoding="utf-8"))["avisos"]}

COR = {"painel": "rgba(8,9,11,0.62)", "vermelho": "#e10600", "texto": "#f2f4f5", "apoio": "#b8c2cc",
       "fraco": "#8c979f", "fantasma": "rgba(233,237,242,0.9)", "pista": "#2a2f36", "borda": "rgba(233,237,242,0.35)"}


def item(trecho, acao):
    k = [t.nome for t in trechos].index(trecho)
    p = R.pontos_do_trecho(g, total, track, trechos, k)
    s_acao = p[{"freie": "freada", "vire": "entrada", "acelere": "retomada"}[acao]]
    f = R.frase_da_acao(acao, s_acao, pts_marcos, L)
    fala = R.fala_do_aviso(trecho, f["frase"])
    dur = duracoes.get(fala, 4.0)
    sf = R.s_fala(p["freada"], p["velocidadeNaFreadaKmh"], dur, L)
    return {"trecho": trecho, "frase": f["frase"], "janela": f"Curva {int(trecho[1:])}: {f['frase']}", "sAcao": s_acao,
            "sFala": sf, "duracaoS": dur, "voz": True, "marco": f["marco"]}


def janela(it, s_carro, W=520, H=200):
    dist = (it["sAcao"] - s_carro) % L
    return f"""<svg width="{W}" height="{H}" style="background:#5a6470">
  <rect x="0" y="0" width="{W}" height="{H}" rx="10" fill="{COR['painel']}"/>
  <rect x="0" y="0" width="6" height="{H}" rx="3" fill="{COR['vermelho']}"/>
  <text x="20" y="22" font-size="13" fill="{COR['vermelho']}" font-family="Segoe UI">ENGENHEIRO</text>
  <foreignObject x="20" y="30" width="{W - 90}" height="56"><div xmlns="http://www.w3.org/1999/xhtml"
    style="font:20px 'Segoe UI';color:{COR['texto']};line-height:1.2">{html.escape(it['janela'])}</div></foreignObject>
  <text x="20" y="98" font-size="12" fill="{COR['apoio']}" font-family="Segoe UI">a {dist:.0f} m</text>
</svg>"""


def vista(it, antes_m=120.0, W=740, H=330):
    s0 = (it["sAcao"] - antes_m) % L
    lat_ref = np.asarray(g["lateral"], float)
    k0 = int(track.index_of(s0))
    olho = np.r_[track.to_world([s0], [lat_ref[k0]])[0], 0.0]
    frente = np.r_[np.asarray(track.tangent[k0], float), 0.0]
    esq = np.r_[np.asarray(track.normal[k0], float), 0.0]
    altura = 1.0
    foco = W * 0.9

    def proj(xz, y=0.0):
        d = np.array([xz[0], xz[1]]) - olho[:2]
        prof = d @ frente[:2]
        lado = d @ esq[:2]
        if prof < 1.0:
            return None
        return (W / 2 - foco * lado / prof, H * 0.42 + foco * (altura - y) / prof)

    def poligono(pontos, cor, opac=1.0, contorno="none"):
        pp = [proj(p, y) for p, y in pontos]
        if any(q is None for q in pp):
            return ""
        return f'<polygon points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in pp)}" fill="{cor}" fill-opacity="{opac}" stroke="{contorno}"/>'

    partes = [f'<rect width="{W}" height="{H * 0.42:.0f}" fill="#7b8a99"/>',
              f'<rect y="{H * 0.42:.0f}" width="{W}" height="{H * 0.58:.0f}" fill="#3c4a37"/>']
    # o asfalto, de 2 em 2 m, de 2 m ate 300 m a frente
    ss = np.arange(2.0, 300.0, 2.0)
    for a, b in zip(ss[:-1], ss[1:]):
        sa, sb = (s0 + a) % L, (s0 + b) % L
        ka, kb = int(track.index_of(sa)), int(track.index_of(sb))
        pa_e = track.to_world([sa], [track.width_left[ka]])[0]
        pa_d = track.to_world([sa], [-track.width_right[ka]])[0]
        pb_e = track.to_world([sb], [track.width_left[kb]])[0]
        pb_d = track.to_world([sb], [-track.width_right[kb]])[0]
        partes.append(poligono([(pa_e, 0), (pb_e, 0), (pb_d, 0), (pa_d, 0)], COR["pista"]))
    # as zebras e as placas a frente
    for m in marcos:
        if m["tipo"] == "zebra":
            for s in np.arange(m["s"], m["s"] + m["comprimentoM"], 2.0):
                d = (s - s0) % L
                if 2.0 < d < 300.0:
                    k = int(track.index_of(s))
                    lado = 1.0 if m["lado"] == "esquerda" else -1.0
                    borda = track.width_left[k] if lado > 0 else track.width_right[k]
                    cor = "#d22" if int(s // 4) % 2 == 0 else "#eee"
                    a1 = track.to_world([s], [lado * (borda - 1.0)])[0]
                    a2 = track.to_world([s], [lado * borda])[0]
                    b1 = track.to_world([s + 2], [lado * (borda - 1.0)])[0]
                    b2 = track.to_world([s + 2], [lado * borda])[0]
                    partes.append(poligono([(a1, 0.01), (b1, 0.01), (b2, 0.01), (a2, 0.01)], cor))
    for m in marcos:
        if m["tipo"] in ("placa", "placa_drs"):
            d = (m["s"] - s0) % L
            if 2.0 < d < 300.0:
                base = np.array([m["x"], m["z"]])
                q1, q2 = proj(base, 0.0), proj(base, 2.2)
                if q1 and q2:
                    w = max(3.0, 1.2 * foco / d)
                    partes.append(f'<rect x="{q2[0] - w / 2:.1f}" y="{q2[1]:.1f}" width="{w:.1f}" height="{(q1[1] - q2[1]) * 0.55:.1f}" fill="#eee" stroke="#333"/>')
                    if m["tipo"] == "placa":
                        partes.append(f'<text x="{q2[0]:.1f}" y="{q2[1] + (q1[1] - q2[1]) * 0.4:.1f}" font-size="{max(7.0, w * 0.45):.0f}" text-anchor="middle" fill="#222" font-family="Segoe UI" font-weight="bold">{m["valor"]}</text>')
    # a marca: 1,5 m x 6 m, centrada na linha da referencia, na cor do fantasma
    k = int(track.index_of(it["sAcao"]))
    c = track.to_world([it["sAcao"]], [lat_ref[k]])[0]
    t_ = np.asarray(track.tangent[k], float)
    n_ = np.array([-t_[1], t_[0]])
    a, b = 0.75, 3.0
    quad = [c - t_ * a - n_ * b, c - t_ * a + n_ * b, c + t_ * a + n_ * b, c + t_ * a - n_ * b]
    partes.append(poligono([(p, 0.04) for p in quad], COR["fantasma"], 0.9))
    partes.append(f'<text x="12" y="20" font-size="13" fill="#fff" font-family="Segoe UI">vista do piloto, {antes_m:.0f} m antes do ponto da ação (s = {it["sAcao"]:.0f} m); a marca: 1,5 m × 6 m na linha da referência</text>')
    return f'<svg width="{W}" height="{H}">{"".join(partes)}</svg>'


def lista_lenta(W=520, H=300):
    """A lista inteira, como o engenheiro a deixou no fim da sessao de 12/11 fora do tempo real (D.1)."""
    d = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    linhas = []
    for i in d["engenheiro"]["lista"]:
        perda = f"−{abs(float(i['perdaS'])):.2f} s".replace(".", ",")
        linhas.append((i["janela"], perda + ("" if i.get("voz") else "  (só na janela)"), i.get("conferencia"), i.get("aplicada")))
    y = 44
    corpo = []
    for texto, perda, conf, ok in linhas:
        corpo.append(f'<text x="20" y="{y}" font-size="13" fill="{COR["texto"]}" font-family="Segoe UI">{html.escape(texto)}  {perda}</text>')
        y += 17
        if y > H - 10:
            break
        if conf:
            corpo.append(f'<text x="20" y="{y}" font-size="12" fill="{"#6f9bff" if ok else "#ffa24a"}" font-family="Segoe UI">   {html.escape(conf)}</text>')
            y += 16
    return f"""<svg width="{W}" height="{H}" style="background:#5a6470">
  <rect width="{W}" height="{H}" rx="10" fill="{COR['painel']}"/><rect width="6" height="{H}" rx="3" fill="{COR['vermelho']}"/>
  <text x="20" y="22" font-size="13" fill="{COR['vermelho']}" font-family="Segoe UI">ENGENHEIRO</text>
  <text x="120" y="22" font-size="12" fill="{COR['apoio']}" font-family="Segoe UI">volta lenta (exemplo de motivo: 5,0 s atrás da melhor da sessão)</text>
  {''.join(corpo)}</svg>"""


c01 = item("C01", "freie")
c06 = item("C06", "freie")
pagina = f"""<!doctype html><meta charset="utf-8"><title>[teste] Pedido 52: a janela do engenheiro e a marca</title>
<body style="background:#1b1f24;color:#eee;font-family:Segoe UI;margin:16px">
<h3>Pedido 52, D.2: a janela "Engenheiro" e a marca na pista (prévia fora do jogo)</h3>
<p>C01: {html.escape(c01['janela'])} (s_fala {c01['sFala']:.0f} m, ação {c01['sAcao']:.0f} m, {c01['duracaoS']:.2f} s de fala)</p>
<div style="display:flex;gap:16px;align-items:flex-start">{janela(c01, (c01['sAcao'] - 150) % L)}</div>
<div style="display:flex;gap:16px;margin-top:8px">{vista(c01, 120.0)}{vista(c01, 40.0)}</div>
<p>C06: {html.escape(c06['janela'])} (s_fala {c06['sFala']:.0f} m, ação {c06['sAcao']:.0f} m, {c06['duracaoS']:.2f} s de fala)</p>
<div style="display:flex;gap:16px;align-items:flex-start">{janela(c06, (c06['sAcao'] - 150) % L)}</div>
<div style="display:flex;gap:16px;margin-top:8px">{vista(c06, 120.0)}{vista(c06, 40.0)}</div>
<p>Na volta lenta, a lista inteira: a do engenheiro no fim da sessão de 12/11, fora do tempo real (D.1).</p>
{lista_lenta()}
</body>"""
Path(sys.argv[1]).write_text(pagina, encoding="utf-8")
print(sys.argv[1], c01["janela"], c06["janela"])
