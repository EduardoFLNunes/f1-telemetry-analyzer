"""Pedido 52, Parte D.1: junta as rodadas do radio fora do tempo real (sem e com o engenheiro) das 4 sessoes.

Uso: python <este arquivo> <pasta das rodadas> <saida.json>

* os avisos: as linhas `aviso` do registro do engenheiro (cada vez que o carro passou o `s_fala` de um trecho
  da lista): pela voz ou so na janela, com o motivo; a folga ate a freada (o tempo ate a freada da referencia,
  na velocidade do carro, menos a duracao da fala) dos que foram pela voz;
* o feedback: as mensagens do coach, do resumo, da curva e da analise entregues, sem e com o engenheiro;
* as falas que mudaram de lugar: a mesma mensagem (a mesma origem, a volta e o titulo, na ordem) entregue
  sem e com o engenheiro, com o `s` do carro de cada uma; "mudou de bloco" quando o `s` difere em mais de 300 m
  (outra reta) ou a volta do carro mudou;
* acima do limite: a duracao passa do `falaMaxS` (7,3, 8,0 e 8,8 s nao mudam; o aviso nao tem limite de tipo);
* a conferencia: as dicas conferidas e as aplicadas;
* a causa na voz do feedback: a fala tem a causa ("Freou", "Mínima", "Passou", "Saiu", "Acelerou", a regra do
  pedido 51), sem e com o engenheiro, e as mensagens que tinham a causa sem o engenheiro e perderam com ele.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

PASTA, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
SESSOES = ["2026-10-13", "2026-10-18", "2026-10-21", "2026-11-12"]
FEEDBACK = ("coach", "resumo", "curva", "analise")
CAUSA = re.compile(r"\b([Ff]reou|[Mm]ínima|[Pp]assou|[Ss]aiu|[Aa]celerou)\b")


def chave(m):
    return (m.get("origem"), m.get("volta") or m.get("voltaDoCarro"), m.get("titulo"))


saida = {"regras": __doc__, "sessoes": {}}
for s in SESSOES:
    com = json.loads((PASTA / f"{s}_com.json").read_text(encoding="utf-8"))
    sem = json.loads((PASTA / f"{s}_sem.json").read_text(encoding="utf-8"))
    reg = com.get("registroDoEngenheiro") or []
    avisos = [x for x in reg if x["tipo"] == "aviso"]
    voz = [x for x in avisos if x["voz"]]
    janela = [x for x in avisos if not x["voz"]]
    conf = [x for x in reg if x["tipo"] == "conferencia"]
    voltas = [x for x in reg if x["tipo"] == "volta"]
    msgs_com = com["mensagens"]
    msgs_sem = sem["mensagens"]
    fb_com = [m for m in msgs_com if m["origem"] in FEEDBACK]
    fb_sem = [m for m in msgs_sem if m["origem"] in FEEDBACK]
    antes = {}
    for m in fb_sem:
        antes.setdefault(chave(m), []).append(m)
    pares, mudou, so_sem, so_com, perdeu_causa = [], [], [], [], []
    for m in fb_com:
        lista = antes.get(chave(m)) or []
        if not lista:
            so_com.append({k: m.get(k) for k in ("origem", "volta", "voltaDoCarro", "titulo", "fala", "sCarro")})
            continue
        a = lista.pop(0)
        par = {"origem": m["origem"], "volta": m.get("volta") or m.get("voltaDoCarro"), "titulo": m.get("titulo"),
               "sem": {"voltaDoCarro": a.get("voltaDoCarro"), "sCarro": a.get("sCarro"), "fala": a.get("fala"), "duracaoS": a.get("duracaoS")},
               "com": {"voltaDoCarro": m.get("voltaDoCarro"), "sCarro": m.get("sCarro"), "fala": m.get("fala"), "duracaoS": m.get("duracaoS")}}
        pares.append(par)
        if a.get("voltaDoCarro") != m.get("voltaDoCarro") or abs(float(a.get("sCarro") or 0) - float(m.get("sCarro") or 0)) > 300:
            mudou.append(par)
        if a.get("fala") and CAUSA.search(a["fala"]) and not (m.get("fala") and CAUSA.search(m["fala"])):
            perdeu_causa.append(par)
    for resto in antes.values():
        so_sem += [{k: m.get(k) for k in ("origem", "volta", "voltaDoCarro", "titulo", "fala", "sCarro")} for m in resto]
    acima = [{"id": m["id"], "origem": m["origem"], "duracaoS": m["duracaoS"], "falaMaxS": m["falaMaxS"]}
             for m in msgs_com + msgs_sem if m.get("duracaoS") and m.get("falaMaxS") and m["duracaoS"] > m["falaMaxS"]]
    entregues_voz = [m for m in msgs_com if m["origem"] == "aviso"]
    folgas = [x["folgaAteAFreadaS"] for x in voz if x.get("folgaAteAFreadaS") is not None]
    saida["sessoes"][s] = {
        "sessao": com["sessao"],
        "voltasQueContaram": len(voltas),
        "avisos": {
            "dados": len(avisos), "pelaVoz": len(voz), "soNaJanela": len(janela),
            "pelaVozPorTrecho": dict(Counter(x["trecho"] for x in voz)),
            "soNaJanelaPorMotivo": dict(Counter(x["porqueSoNaJanela"] for x in janela)),
            "entreguesNoRadio": len(entregues_voz),
            "folgaAteAFreadaS": {"min": min(folgas) if folgas else None, "max": max(folgas) if folgas else None,
                                 "todas": folgas},
            "pelaVozLista": [{"trecho": x["trecho"], "frase": x["frase"], "sFala": x["sFala"], "sCarro": x["sCarro"],
                              "velocidadeKmh": x["velocidadeKmh"], "folgaAteAFreadaS": x["folgaAteAFreadaS"]} for x in voz],
        },
        "conferencia": {"conferidas": len([c for c in conf if c["aplicada"] is not None]),
                        "aplicadas": len([c for c in conf if c["aplicada"] is True]),
                        "semMedida": len([c for c in conf if c["aplicada"] is None]),
                        "acuraciaPorVolta": [{"volta": v["volta"], "aplicadas": v["aplicadas"], "medidas": v["medidas"]} for v in voltas]},
        "feedback": {"sem": dict(Counter(m["origem"] for m in fb_sem)), "com": dict(Counter(m["origem"] for m in fb_com)),
                     "pendentesNoFim": {"sem": sem["pendentesNoFim"], "com": com["pendentesNoFim"]},
                     "mesmaMensagemNasDuas": len(pares), "mudaramDeBloco": mudou, "soSem": so_sem, "soCom": so_com,
                     "comCausaNaVoz": {"sem": sum(1 for m in fb_sem if m.get("fala") and CAUSA.search(m["fala"])),
                                       "com": sum(1 for m in fb_com if m.get("fala") and CAUSA.search(m["fala"]))},
                     "perderamACausa": perdeu_causa,
                     "duracaoMediaS": {"sem": round(sum(m["duracaoS"] or 0 for m in fb_sem) / max(1, len(fb_sem)), 2),
                                       "com": round(sum(m["duracaoS"] or 0 for m in fb_com) / max(1, len(fb_com)), 2)}},
        "acimaDoLimite": acima,
        "maiorDuracaoPorOrigem": {o: max((m["duracaoS"] or 0) for m in msgs_com if m["origem"] == o)
                                  for o in {m["origem"] for m in msgs_com}},
        "listaNoFim": [{"trecho": i["trecho"], "causa": i["causa"], "frase": i["frase"], "voz": i["voz"]}
                       for i in (com.get("engenheiro") or {}).get("lista", [])],
    }
SAIDA.write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")
for s, d in saida["sessoes"].items():
    a, f = d["avisos"], d["feedback"]
    print(s, "voltas", d["voltasQueContaram"], "| avisos", a["dados"], "voz", a["pelaVoz"], "janela", a["soNaJanela"],
          "folga", a["folgaAteAFreadaS"]["min"], a["folgaAteAFreadaS"]["max"], "| feedback sem", f["sem"], "com", f["com"],
          "| mudaram", len(f["mudaramDeBloco"]), "so sem", len(f["soSem"]), "so com", len(f["soCom"]),
          "| acima", len(d["acimaDoLimite"]), "| conf", d["conferencia"]["aplicadas"], "/", d["conferencia"]["conferidas"],
          "| causa na voz", f["comCausaNaVoz"], "perderam", len(f["perderamACausa"]), "| duracao media", f["duracaoMediaS"])
