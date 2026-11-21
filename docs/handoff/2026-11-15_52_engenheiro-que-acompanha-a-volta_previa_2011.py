"""Pedido 52, D.2 da atualizacao de 20/11: a previa da janela "Engenheiro" com os dois proximos avisos.

Nao ha como rodar o app Lua fora do jogo. A previa repete o desenho de `desenharOEngenheiro`
(`radio_engenheiro.lua`, app 0.8.0) num SVG: o painel, a faixa vermelha, "ENGENHEIRO", o aviso da vez em destaque
(fundo vermelho claro, 20 px, a cor do texto) e o seguinte menor (15 px, a cor de apoio), com "a N m" ate o ponto
dito e "so na janela". Os avisos e os pontos (`sJanela`, `sFimDaJanela`, `sDito`) vem do engenheiro de verdade,
como ele ficou no fim da rodada da D.1 da sessao de 20/11 com o molde (a). O carro e posto em tres pontos em que
ha dois avisos na janela.

Uso (na pasta backend): python <este arquivo> <rodada da D.1 (20/11, molde a).json> <saida.html>
"""
import html
import json
import sys
from pathlib import Path

COR = {"painel": "rgba(8,9,11,0.62)", "vermelho": "#e10600", "destaque": "rgba(225,6,0,0.18)", "texto": "#f2f4f5",
       "apoio": "#b8c2cc", "fraco": "#8c979f"}
rodada = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
eng = rodada["engenheiro"]
L = float(eng["comprimentoM"])
lista = [i for i in eng["lista"] if i.get("frase") and i.get("sJanela") is not None]


def frente(de, ate):
    return (ate - de) % L


def ativos(s):
    out = [i for i in lista if frente(i["sJanela"], s) <= frente(i["sJanela"], i["sFimDaJanela"])]
    out.sort(key=lambda i: frente(s, i["sFimDaJanela"]))
    return out[:2]


def janela(s, W=520, H=200):
    corpo, y = [], 30
    for k, it in enumerate(ativos(s)):
        vez = k == 0
        dist = frente(s, it["sDito"])
        if vez:
            corpo.append(f'<rect x="14" y="{y - 4}" width="{W - 24}" height="74" rx="6" fill="{COR["destaque"]}"/>')
        corpo.append(f'<foreignObject x="20" y="{y}" width="{W - 90}" height="{52 if vez else 40}"><div xmlns="http://www.w3.org/1999/xhtml" '
                     f'style="font:{20 if vez else 15}px \'Segoe UI\';color:{COR["texto"] if vez else COR["apoio"]};line-height:1.2">'
                     f'{html.escape(it["janela"])}</div></foreignObject>')
        corpo.append(f'<text x="20" y="{y + (66 if vez else 54)}" font-size="12" fill="{COR["apoio"]}" font-family="Segoe UI">'
                     f'a {dist:.0f} m{"" if it.get("voz") else " · só na janela"}</text>')
        y += 76 if vez else 60
    return f"""<svg width="{W}" height="{H}" style="background:#5a6470">
  <rect x="0" y="0" width="{W}" height="{H}" rx="10" fill="{COR['painel']}"/>
  <rect x="0" y="0" width="6" height="{H}" rx="3" fill="{COR['vermelho']}"/>
  <text x="20" y="22" font-size="13" fill="{COR['vermelho']}" font-family="Segoe UI">ENGENHEIRO</text>
  {''.join(corpo)}</svg>"""


# tres pontos com dois avisos na janela: o primeiro de cada trecho da pista em que isso acontece
pontos, ultimo = [], -1e9
for k in range(0, int(L), 5):
    s = float(k)
    a = ativos(s)
    if len(a) == 2 and s - ultimo > 600:
        pontos.append((s, a))
        ultimo = s
    if len(pontos) == 3:
        break
blocos = []
for s, a in pontos:
    txt = " e ".join(f"{i['trecho']} (aparece em {i['sJanela']:.0f} m, sai em {i['sFimDaJanela']:.0f} m)" for i in a)
    blocos.append(f"<p>O carro em {s:.0f} m: {html.escape(txt)}</p>{janela(s)}")
pagina = f"""<!doctype html><meta charset="utf-8"><title>[teste] Pedido 52: a janela com os dois próximos avisos</title>
<body style="background:#1b1f24;color:#eee;font-family:Segoe UI;margin:16px">
<h3>Pedido 52, D.2 de 20/11: a janela "Engenheiro" com os dois próximos avisos (prévia fora do jogo)</h3>
<p>Sessão {html.escape(rodada['sessao'])}, molde {html.escape(str(rodada.get('molde')))}, o perfil: {html.escape(str(eng.get('perfil')))}.</p>
{''.join(blocos)}
</body>"""
Path(sys.argv[2]).write_text(pagina, encoding="utf-8")
print(sys.argv[2], [(round(s), [i["trecho"] for i in a]) for s, a in pontos])
