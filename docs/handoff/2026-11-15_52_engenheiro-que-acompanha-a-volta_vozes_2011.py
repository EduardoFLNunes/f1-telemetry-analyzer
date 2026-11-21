"""Pedido 52, D.2 da atualizacao de 20/11: os audios de cada variante do molde (a, b e c), com a voz do projeto
(Microsoft Daniel a 1,4x, sem a vinheta, como o aviso sai), para o Eduardo ouvir e escolher.

* **as falas sozinhas dos 15 trechos:** cada acao possivel de cada trecho na volta do modelo (a tabela da B.4:
  freie, vire, acelere e, onde vale, "sem tirar o pe"), no molde de cada variante;
* **as falas com dois avisos** que a D.1 encontrou (as linhas `aviso` com `falaJunta` das rodadas com o engenheiro).

Grava em `data/radio/[teste] vozes do engenheiro 20-11/<variante>/` (fora da pasta do jogo e fora do git) e um
indice com o texto e a duracao de cada arquivo.

Uso (na pasta backend): python <este arquivo> <conferencia_da_volta_do_modelo.json> <pasta das rodadas da D.1>
  <indice.json>
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
from core.engenheiro import plano as P  # noqa: E402
from core.engenheiro import regras as R  # noqa: E402
from core.radio.audio import falar  # noqa: E402

CONF, RODADAS, INDICE = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
REPO = Path("..").resolve()
DESTINO = REPO / "data" / "radio" / "[teste] vozes do engenheiro 20-11"
conf = json.loads(CONF.read_text(encoding="utf-8"))
indice = {"voz": "OneCore:Daniel a 1,4x, sem a vinheta", "pasta": str(DESTINO), "variantes": {}}
for v in P.MOLDES:
    pasta = DESTINO / v
    pasta.mkdir(parents=True, exist_ok=True)
    itens = []
    for f in conf["frases"]:
        for acao in ("freie", "vire", "acelere", R.SEM_TIRAR_O_PE):
            x = f.get(acao)
            if not x:
                continue
            frase = P.frase_falada(acao, x.get("marco"), x.get("d"), v, x["frase"])
            texto = P.fala_sozinha(frase)
            nome = f"{f['trecho'].replace('->', '_')}_{acao.replace(' ', '_')}.wav"
            dur = float(falar(texto, pasta / nome, vinheta_antes=False))
            itens.append({"arquivo": f"{v}/{nome}", "trecho": f["trecho"], "acao": acao, "texto": texto, "duracaoS": round(dur, 2)})
            print(v, f"{dur:5.2f} s", texto, flush=True)
    pares = set()
    for arq in sorted(RODADAS.glob(f"*_com_{v}.json")):
        d = json.loads(arq.read_text(encoding="utf-8"))
        for a in d.get("registroDoEngenheiro") or []:
            if a.get("tipo") == "aviso" and a.get("falaJunta") and a.get("fala"):
                pares.add(a["fala"])
    for k, texto in enumerate(sorted(pares), 1):
        nome = f"par_{k:02d}.wav"
        dur = float(falar(texto, pasta / nome, vinheta_antes=False))
        itens.append({"arquivo": f"{v}/{nome}", "trecho": None, "acao": "par", "texto": texto, "duracaoS": round(dur, 2)})
        print(v, f"{dur:5.2f} s", texto, flush=True)
    indice["variantes"][v] = itens
INDICE.write_text(json.dumps(indice, ensure_ascii=False, indent=1), encoding="utf-8")
(DESTINO / "indice.json").write_text(json.dumps(indice, ensure_ascii=False, indent=1), encoding="utf-8")
print(INDICE)
