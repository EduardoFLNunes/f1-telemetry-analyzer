"""Pedido 43, C.2 e B.2: o que os visuais mostram contra o que a voz disse, mensagem a mensagem.

Para cada replay de uma passagem do `radio_offline.py` (depois do pedido 43):

* **na frase do coach:** a subida da diferenca acumulada dentro do trecho da fala (o seu tempo
  menos o da referencia, das linhas da rota, interpolado nas bordas do trecho) contra o tempo
  que a voz e o cartao disseram (`lossSeconds` do coach). E, nas minimas, a velocidade da grade
  no ponto marcado contra o numero da voz (o coach mede nos quadros; a grade e a projecao deles);
* **na analise:** o fim da linha (a diferenca acumulada na saida do replay) contra o "perde X s
  nesta curva" (a perda no trecho da curva, do meio da reta anterior ao meio da seguinte).

Uso: python medir_visuais.py <passagem.json> [...]
"""
import json
import sys
from pathlib import Path


def dif_em(c, d):
    """A diferenca acumulada a `d` metros da entrada (interpolada entre dois pontos da grade)."""
    v, r, passo = c["linhas"]["voce"], c["linhas"]["referencia"], c["passoM"]
    x = d / passo
    i = max(0, min(len(v) - 2, int(x)))
    u = min(max(x - i, 0.0), 1.0)
    a = v[i][2] - r[i][2]
    b = v[i + 1][2] - r[i + 1][2]
    return a + (b - a) * u


saida = []
for arq in map(Path, sys.argv[1:]):
    dados = json.loads(arq.read_text(encoding="utf-8"))
    evid = dados["evidencias"]
    por_id = {str(m["id"]): m for m in dados["mensagens"]}
    for id_, rep in dados["replays"].items():
        m = por_id[id_]
        for c in rep["curvas"]:
            linha = {"sessao": dados["sessao"][:10], "id": int(id_), "origem": m["origem"], "curva": c["curva"],
                     "volta": c["volta"], "bytesDaRota": dados["bytesDaRota"][id_]}
            fim = c["linhas"]["voce"][-1][2] - c["linhas"]["referencia"][-1][2]
            if c.get("voz"):
                ev = [e for e in evid if e.get("volta") == m["volta"] and abs(e["lossSeconds"] - m["perdaS"]) < 6e-4][-1]
                subida = dif_em(c, c["voz"]["fimM"]) - dif_em(c, c["voz"]["inicioM"])
                k = lambda d: round(d / c["passoM"])  # noqa: E731
                minimas = None
                if c.get("minimas"):
                    minimas = {
                        "vozSua": ev.get("yourMinSpeedKmh"), "gradeSua": c["velocidades"]["voce"][k(c["minimas"]["voce"]["dM"])],
                        "vozDela": ev.get("referenceMinSpeedKmh"),
                        "gradeDela": c["velocidades"]["referencia"][k(c["minimas"]["referencia"]["dM"])],
                    }
                linha.update({
                    "fala": m["fala"], "microssetor": c["voz"]["microssetor"],
                    "tempoDaVozS": ev["lossSeconds"], "noCartao": c["voz"]["perdaS"],
                    "subidaNoTrechoS": round(subida, 3), "diferencaS": round(subida - ev["lossSeconds"], 3),
                    "dentroDoArredondamentoDoCartao": abs(round(subida, 2) - c["voz"]["perdaS"]) < 1e-9,
                    "dentroDoArredondamentoDaVoz": abs(subida - ev["lossSeconds"]) <= 0.05,
                    "fimDaLinhaS": round(fim, 3), "perdaNaCurvaS": c["perdaS"], "minimas": minimas,
                })
            else:
                linha.update({"fimDaLinhaS": round(fim, 3), "perdaNaCurvaS": c["perdaS"],
                              "diferencaS": round(fim - c["perdaS"], 3)})
            saida.append(linha)
print(json.dumps(saida, ensure_ascii=False, indent=1))
