"""Pedido 51, Parte D.1: junta as tres rodadas do radio fora do tempo real (antes, palavras, depois) das 4 sessoes.

Uso: python <este arquivo> <pasta das rodadas> <saida.json>

* entregues: as mensagens que o radio entregou (todas as da lista), por origem;
* a causa na voz: a fala tem a causa ("Freou", "Mínima", "Passou", "Saiu", "Acelerou", com maiuscula ou
  minuscula). "Perdeu a causa": a mesma mensagem (a mesma origem, volta e titulo, na ordem) tinha a causa
  no `antes` e nao tem no `palavras` (so as palavras mudam entre os dois);
* "IA" na fala, no texto, no detalhe e nos rotulos do replay;
* acima do limite: a duracao passa do `falaMaxS` (7,3, 8,0 e 8,8 s nao mudam).
"""
import json
import re
import sys
from pathlib import Path

PASTA, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
CAUSA = re.compile(r"\b([Ff]reou|[Mm]ínima|[Pp]assou|[Ss]aiu|[Aa]celerou)\b")
IA = re.compile(r"\bIA\b")
SESSOES = ["2026-10-13", "2026-10-18", "2026-10-21", "2026-11-12"]


def chave(m):
    return (m.get("origem"), m.get("volta") or m.get("voltaDoCarro"), m.get("titulo"))


def resumo(d):
    ms = d["mensagens"]
    por = {}
    for m in ms:
        por[m["origem"]] = por.get(m["origem"], 0) + 1
    return {
        "referencia": d["referencia"], "entregues": len(ms), "porOrigem": por, "pendentesNoFim": d["pendentesNoFim"],
        "comCausaNaVoz": sum(1 for m in ms if m.get("fala") and CAUSA.search(m["fala"])),
        "comIA": [m["fala"] for m in ms if any(IA.search(str(m.get(k) or "")) for k in ("fala", "texto", "detalhe"))],
        "rotulosDoReplay": d.get("rotulosDoReplay"),
        "acimaDoLimite": [m["id"] for m in ms if m.get("duracaoS") and m.get("falaMaxS") and m["duracaoS"] > m["falaMaxS"]],
        "maiorDuracaoPorOrigem": {o: max((m["duracaoS"] or 0) for m in ms if m["origem"] == o) for o in por},
    }


saida = {"regras": __doc__, "sessoes": {}}
for s in SESSOES:
    rod = {modo: json.loads((PASTA / f"{s}_{modo}.json").read_text(encoding="utf-8")) for modo in ("antes", "palavras", "depois")}
    item = {modo: resumo(d) for modo, d in rod.items()}
    antes = {}
    for m in rod["antes"]["mensagens"]:
        antes.setdefault(chave(m), []).append(m)
    perdeu, ganhou, pares = [], [], []
    for m in rod["palavras"]["mensagens"]:
        lista = antes.get(chave(m)) or []
        if not lista:
            continue
        a = lista.pop(0)
        ca, cb = bool(a.get("fala") and CAUSA.search(a["fala"])), bool(m.get("fala") and CAUSA.search(m["fala"]))
        par = {"origem": m["origem"], "volta": m.get("volta") or m.get("voltaDoCarro"), "titulo": m.get("titulo"),
               "antes": a.get("fala"), "antesS": a.get("duracaoS"), "depois": m.get("fala"), "depoisS": m.get("duracaoS")}
        pares.append(par)
        if ca and not cb:
            perdeu.append(par)
        elif cb and not ca:
            ganhou.append(par)
    item["antesContraPalavras"] = {"pares": len(pares), "perderamACausa": perdeu, "ganharamACausa": ganhou,
                                   "falas": pares}
    item["depoisFalas"] = [{"origem": m["origem"], "volta": m.get("volta") or m.get("voltaDoCarro"),
                            "fala": m.get("fala"), "duracaoS": m.get("duracaoS")} for m in rod["depois"]["mensagens"]]
    saida["sessoes"][s] = item
SAIDA.write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")
for s, it in saida["sessoes"].items():
    print(s, {m: (it[m]["entregues"], it[m]["comCausaNaVoz"], len(it[m]["comIA"]), it[m]["acimaDoLimite"], it[m]["rotulosDoReplay"])
              for m in ("antes", "palavras", "depois")},
          "perderam:", len(it["antesContraPalavras"]["perderamACausa"]), "ganharam:", len(it["antesContraPalavras"]["ganharamACausa"]),
          "pares:", it["antesContraPalavras"]["pares"])
