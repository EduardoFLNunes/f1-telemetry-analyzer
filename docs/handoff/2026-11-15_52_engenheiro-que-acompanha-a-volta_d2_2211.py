"""Pedido 52, decisoes de 22/11: os textos das 14 curvas nos tres niveis (iniciante, amador e pro), pela volta de
referencia, em audio, para o Eduardo ouvir.

* **os textos:** `core.engenheiro.explicacao` (as medidas de cada curva e os limites das palavras do ADR 0033,
  decisoes de 22/11), como o engenheiro os prepara ao subir;
* **os audios:** a voz do projeto (Daniel a 1,4x, sem a vinheta), em
  `data/radio/[teste] engenheiro que ensina 22-11/<nivel>/` (fora da pasta do jogo e fora do git), com a duracao.

Uso (na pasta backend): python <este arquivo> <saida.json> [--audio]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
from core.assisted_analysis import volta_do_modelo as VM  # noqa: E402
from core.engenheiro import explicacao as E  # noqa: E402
from core.engenheiro import ficha as F  # noqa: E402
from core.engenheiro import marcos as M  # noqa: E402
from core.engenheiro import regras as R  # noqa: E402
from core.radio.analise import grade  # noqa: E402
from core.radio.janelas import carregar_geometria  # noqa: E402

SAIDA = Path(sys.argv[1])
COM_AUDIO = "--audio" in sys.argv
REPO = Path("..").resolve()
track = carregar_geometria(REPO)
L = float(track.length)
trechos = R.trechos_da_pista(track)
g = grade(VM.como_volta_do_store(VM.encontrar([REPO], "vhe_interlagos")))
mc = M.encontrar([REPO], "vhe_interlagos")["marcos"]
pontos = M.pontos_de_referencia(mc)
curvas = [k for k, t in enumerate(trechos) if t.tem_curva]
saida = []
for k in curvas:
    t = trechos[k]
    lado = F.lado_da_curva(track, t)
    m = E.medidas_da_curva(g, track, trechos, k, lado, mc)
    tipo = E.tipo_da_curva(g, track, trechos, k)
    kn = next((j for j in curvas if j > k), curvas[0])
    seguinte = E._seguinte(E.tipo_da_curva(g, track, trechos, kn), R.numero_da_curva(trechos[kn].nome))
    textos = E.textos_da_curva(m, R.numero_da_curva(t.nome), tipo, seguinte, L, pontos)
    item = {"trecho": t.nome, "tipo": tipo, "medidas": {c: m.get(c) for c in (
        "chegada", "freada", "vFreadaKmh", "fimDaFrenagem", "frenagemM", "reta", "virar", "semPedalM", "minimaKmh",
        "sMinima", "apiceDaBordaM", "aceleradorCheio", "saidaDaBordaM")}, "textos": textos, "duracaoS": {}}
    if COM_AUDIO:
        from core.radio.audio import falar
        for nivel in E.NIVEIS:
            destino = REPO / "data" / "radio" / "[teste] engenheiro que ensina 22-11" / nivel
            destino.mkdir(parents=True, exist_ok=True)
            item["duracaoS"][nivel] = round(float(falar(textos[nivel], destino / f"{t.nome}.wav", vinheta_antes=False)), 2)
    saida.append(item)
    print(t.nome, item["duracaoS"], flush=True)
SAIDA.write_text(json.dumps({"curvas": saida}, ensure_ascii=False, indent=1), encoding="utf-8")
