"""Pedido 52, D.2 da atualizacao de 21/11: as fichas das curvas com a tecnica da melhor passagem do piloto, em audio,
e a previa da janela "Engenheiro" (app do jogo 0.9.0).

* **a melhor passagem** de cada curva: a de menor tempo no trecho (ADR 0030) entre as voltas humanas do store
  (`data/ml/laps_grid_v2`, o carro da referencia), como o engenheiro guarda em `melhores` (ADR 0033, item 2). So
  leitura do store;
* **as fichas:** `core.engenheiro.ficha.lista_de_fichas` com a volta de referencia e essas passagens (a tecnica com
  frenagem vem da passagem; "de pe embaixo" e "so um alivio", da referencia);
* **os audios:** a ficha e o lembrete de cada curva, com a voz do projeto (Daniel a 1,4x, sem a vinheta), em
  `data/radio/[teste] fichas da curva de foco 21-11/` (fora da pasta do jogo e fora do git), com a duracao;
* **a previa da janela:** o desenho de `desenharOEngenheiro` (o painel, a faixa vermelha, "ENGENHEIRO", a linha do
  foco, a ficha escrita em destaque e "a N m do ponto"), em tres estados: a ficha da curva de foco, a conferencia
  depois da linha e "Esperando uma volta que conte". Nao ha como rodar o app Lua fora do jogo.

Uso (na pasta backend): python <este arquivo> <saida.json> <saida.html> [--audio] [<rodada da D.1 de 21/11.json>]
"""
import html
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")
from core.assisted_analysis import volta_do_modelo as VM  # noqa: E402
from core.engenheiro import ficha as F  # noqa: E402
from core.engenheiro import marcos as M  # noqa: E402
from core.engenheiro import regras as R  # noqa: E402
from core.leitura.arquivos import LeitorDoStore  # noqa: E402
from core.radio.analise import grade  # noqa: E402
from core.radio.janelas import carregar_geometria  # noqa: E402

SAIDA, PAGINA = Path(sys.argv[1]), Path(sys.argv[2])
COM_AUDIO = "--audio" in sys.argv
RODADA = next((Path(a) for a in sys.argv[3:] if a.endswith(".json")), None)
REPO = Path("..").resolve()
track = carregar_geometria(REPO)
trechos = R.trechos_da_pista(track)
dados = VM.encontrar([REPO], "vhe_interlagos")
st = VM.como_volta_do_store(dados)
ref = {"grade": grade(st), "tempoS": float(st["tempoS"])}
mc = M.encontrar([REPO], "vhe_interlagos")
pontos = M.pontos_de_referencia(mc["marcos"])
carro = dados.get("carro") or "rss_formula_rss_3_v6_2026"

# a melhor passagem de cada trecho entre as voltas humanas do store
meta = json.loads((REPO / "data" / "ml" / "laps_grid_v2_meta.json").read_text(encoding="utf-8"))
leitor = LeitorDoStore()
melhores = {}
lidas = 0
for v in meta.get("laps") or []:
    if v.get("origem") != "humano" or v.get("carModel") not in (carro, None) or v.get("track") not in ("vhe_interlagos", None):
        continue
    volta = leitor.ler_volta(REPO, str(v["lap_id"]))
    if not volta or volta.get("disponivel") is False or not volta.get("tempoS"):
        continue
    g = grade(volta)
    lidas += 1
    tempos = R.tempos_dos_trechos(g["elapsed"], float(volta["tempoS"]), track, trechos)
    for t, x in zip(trechos, tempos):
        if np.isfinite(x) and x > 0 and (t.nome not in melhores or x < melhores[t.nome]["tempoS"]):
            melhores[t.nome] = {"tempoS": float(x), "grade": g, "lapId": v["lap_id"], "sessao": v.get("session_id")}
fichas = F.lista_de_fichas(ref, track, trechos, mc["marcos"], pontos, {k: m["grade"] for k, m in melhores.items()})
for f in fichas:
    m = melhores.get(f["trecho"])
    f["passagem"] = None if m is None else {"lapId": m["lapId"], "sessao": m["sessao"], "tempoDoTrechoS": round(m["tempoS"], 3)}
if COM_AUDIO:
    from core.radio.audio import falar
    destino = REPO / "data" / "radio" / "[teste] fichas da curva de foco 21-11"
    destino.mkdir(parents=True, exist_ok=True)
    for f in fichas:
        for tipo in ("fala", "lembrete"):
            arq = destino / f"{f['trecho']}_{'ficha' if tipo == 'fala' else 'lembrete'}.wav"
            f[f"arquivo_{tipo}"] = str(arq)
            f[f"duracao_{tipo}S"] = round(float(falar(f[tipo], arq, vinheta_antes=False)), 2)

# a previa da janela (o desenho de `desenharOEngenheiro`, app 0.9.0)
COR = {"painel": "rgba(8,9,11,0.62)", "vermelho": "#e10600", "destaque": "rgba(225,6,0,0.18)", "texto": "#f2f4f5",
       "apoio": "#b8c2cc", "fraco": "#8c979f", "ganho": "#3ccf6e", "perda": "#ff6b5a"}


def caixa(texto, tamanho, x, y, w, h, cor):
    return (f'<foreignObject x="{x}" y="{y}" width="{w}" height="{h}"><div xmlns="http://www.w3.org/1999/xhtml" '
            f'style="font:{tamanho}px \'Segoe UI\';color:{cor};line-height:1.25">{html.escape(texto)}</div></foreignObject>')


def janela(corpo, W=520, H=200):
    return f"""<svg width="{W}" height="{H}" style="background:#5a6470">
  <rect x="0" y="0" width="{W}" height="{H}" rx="10" fill="{COR['painel']}"/>
  <rect x="0" y="0" width="6" height="{H}" rx="3" fill="{COR['vermelho']}"/>
  <text x="20" y="22" font-size="13" fill="{COR['vermelho']}" font-family="Segoe UI">ENGENHEIRO</text>
  {corpo}</svg>"""


def com_foco(f, dist, origem, W=520, H=200):
    return janela(
        f'<text x="120" y="22" font-size="12" fill="{COR["apoio"]}" font-family="Segoe UI">foco: {f["trecho"]} · {html.escape(origem)}</text>'
        f'<rect x="14" y="26" width="{W - 24}" height="{H - 56}" rx="6" fill="{COR["destaque"]}"/>'
        + caixa(f["escrita"], 18, 20, 30, W - 90, H - 64, COR["texto"])
        + f'<text x="20" y="{H - 14}" font-size="12" fill="{COR["apoio"]}" font-family="Segoe UI">a {dist:.0f} m do ponto</text>')


foco_trecho, origem = "C01", "volta 5 da sessão"
if RODADA is not None and RODADA.exists():
    r = json.loads(RODADA.read_text(encoding="utf-8"))
    fo = (r.get("engenheiro") or {}).get("foco") or {}
    foco_trecho, origem = fo.get("trecho") or foco_trecho, fo.get("origem") or origem
f_foco = next(f for f in fichas if f["trecho"] == foco_trecho)
estados = [
    (f"A ficha da curva de foco ({foco_trecho}), a 180 m do ponto de frenagem", com_foco(f_foco, 180.0, origem)),
    ("Depois da linha: a conferência do foco (8 s)", janela(caixa("Curva 2: freou 40 m antes do ponto", 20, 20, 30, 490, 120, COR["perda"])
                                                           + f'<text x="20" y="186" font-size="12" fill="{COR["apoio"]}" font-family="Segoe UI">foco: C02 · 1 de 3 voltas</text>')),
    ("Sem foco: a última volta descartada", janela(caixa("Esperando uma volta que conte (volta 3: rodada (perdeu 19,9 s na C13))",
                                                          18, 20, 30, 490, 160, COR["apoio"]))),
]
linhas = "".join(f"<tr><td>{f['trecho']}</td><td>{html.escape(f['fala'])}</td><td>{f.get('duracao_falaS', '')}</td>"
                  f"<td>{html.escape(f['lembrete'])}</td><td>{f.get('duracao_lembreteS', '')}</td>"
                  f"<td>{html.escape(str(f.get('tecnicaDe') or 'fora'))}</td></tr>" for f in fichas)
pagina = f"""<!doctype html><meta charset="utf-8"><title>[teste] Pedido 52: a janela da curva de foco</title>
<body style="background:#1b1f24;color:#eee;font-family:Segoe UI;margin:16px;font-size:13px">
<h3>Pedido 52, D.2 de 21/11: a janela "Engenheiro" do app do jogo 0.9.0 (prévia fora do jogo)</h3>
{''.join(f'<p>{html.escape(t)}</p>{s}' for t, s in estados)}
<h3>As fichas, com a técnica da sua melhor passagem ({lidas} voltas do store)</h3>
<table border="1" cellpadding="4" style="border-collapse:collapse"><tr><th>curva</th><th>ficha</th><th>s</th><th>lembrete</th><th>s</th><th>técnica de</th></tr>{linhas}</table>
</body>"""
PAGINA.write_text(pagina, encoding="utf-8")
SAIDA.write_text(json.dumps({"voltasLidas": lidas, "foco": foco_trecho, "fichas": fichas}, ensure_ascii=False, indent=1),
                 encoding="utf-8")
print("voltas do store lidas:", lidas)
for f in fichas:
    print(f["trecho"], f.get("duracao_falaS"), f.get("duracao_lembreteS"), "|", f["fala"], "|", f["lembrete"], "|",
          (f.get("passagem") or {}).get("lapId"))
