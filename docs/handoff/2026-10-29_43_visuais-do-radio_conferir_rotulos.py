"""Pedido 43, Parte B.5: todo numero escrito nos rotulos do replay aparece na fala, com a unidade?

Para cada mensagem com replay (a analise e a frase do coach) de uma passagem do `radio_offline.py`:

1. **os rotulos,** como a janela do jogo (`radio_engenheiro.lua`, `desenharACurva`) e a tela Ao
   vivo (`ReplayDaCurva.tsx`) os escrevem: os de antes do pedido 43 (pedido 36) ou os de agora
   (com os numeros da voz na frase do coach). O arredondamento e o do cliente (`Math.round` e
   `math.floor(x + 0,5)`: 16,5 vira 17);
2. **os numeros da mensagem,** com a unidade: no cartao (titulo, texto, detalhe e linhas) e na voz
   (a fala entregue). A voz diz "16 metros", "6 decimos", "1,2 segundo" e "64 contra 94
   quilometros por hora": tudo vira numero e unidade ("16 m", "0,6 s", "64 km/h");
3. **a conta:** cada numero com unidade de cada rotulo (o numero da volta e o da curva nao sao
   medidas) tem de estar na mensagem. Conta separado "no cartao ou na voz" e "so na voz".

Uso: python conferir_rotulos.py antes|depois <passagem.json> [...]
"""
import json
import math
import re
import sys
from pathlib import Path

MODO, ARQUIVOS = sys.argv[1], [Path(a) for a in sys.argv[2:]]


def js_round(x):
    return math.floor(x + 0.5)


def dec(v, casas):
    return f"{v:.{casas}f}".replace(".", ",")


def rotulos(c):
    """Os textos que o cliente escreve no replay de uma curva."""
    out = []
    voz = c.get("voz") if MODO == "depois" else None
    volta = f" · volta {c['volta']}" if c.get("volta") else ""
    if voz:
        perda = voz.get("perdaS")
        out.append(f"{c['curva']}, {c['lado']}{volta}"
                   + (f" · perde {dec(abs(perda), 2)} s no trecho da fala" if perda is not None else ""))
        out.append("trecho da fala")
    else:
        perda = c["perdaS"]
        out.append(f"{c['curva']}, {c['lado']}{volta} · {'perde' if perda >= 0 else 'ganha'} {dec(abs(perda), 2)} s nesta curva")
    contra = "da sua melhor" if c.get("referencia") == "minha_melhor" else "da IA"
    f = c.get("freadas") or {}
    d = f.get("distanciaM")
    if f.get("voce") and d is not None:
        m = js_round(abs(d))
        out.append("você freia no mesmo ponto" if m < 1 else f"você freia {m} m {'antes' if d < 0 else 'depois'} {contra}")
    t = c.get("tracado")
    if t:
        out.append(f"você passa {dec(t['distanciaM'], 1)} m mais à {t['lado']}")
    mi = c.get("minimas")
    if mi:
        out.append(f"mínima {js_round(mi['voce']['kmh'])} km/h")
        out.append(f"mínima {js_round(mi['referencia']['kmh'])} km/h")
    return out


MEDIDA = re.compile(r"(\d+(?:,\d+)?)\s*(km/h|m|s)(?![\w/])")


def medidas(texto):
    return [(float(v.replace(",", ".")), u) for v, u in MEDIDA.findall(texto)]


def normalizar(texto):
    """A escrita da voz e do cartao como numero e unidade."""
    t = texto.replace("quilômetros por hora", "km/h")
    t = re.sub(r"(\d+) contra (\d+) km/h", r"\1 km/h contra \2 km/h", t)
    t = re.sub(r"(\d+(?:,\d+)?) metros?\b", r"\1 m", t)
    t = re.sub(r"(\d+) décimos?\b", lambda m: f"0,{m.group(1)} s", t)
    t = re.sub(r"(\d+(?:,\d+)?) segundos?\b", r"\1 s", t)
    return t


def casa(v, u, lista):
    return any(u == u2 and abs(v - v2) < 1e-6 for v2, u2 in lista)


resumo = {}
detalhes = []
for arq in ARQUIVOS:
    dados = json.loads(arq.read_text(encoding="utf-8"))
    por_id = {str(m["id"]): m for m in dados["mensagens"]}
    for id_, rep in dados["replays"].items():
        m = por_id[id_]
        cartao = " | ".join(str(x) for x in (m.get("titulo"), m.get("texto"), m.get("detalhe"), *(m.get("linhas") or [])) if x)
        no_cartao = medidas(normalizar(cartao))
        na_voz = medidas(normalizar(m.get("fala") or ""))
        fora_da_mensagem, fora_da_voz = [], []
        for c in rep["curvas"]:
            for r in rotulos(c):
                for v, u in medidas(r.replace(f"volta {c.get('volta')}", "")):
                    if not casa(v, u, no_cartao + na_voz):
                        fora_da_mensagem.append(f"{c['curva']}: {r}")
                    if not casa(v, u, na_voz):
                        fora_da_voz.append(f"{c['curva']}: {r}")
        chave = (dados["sessao"][:10], m["origem"])
        s = resumo.setdefault(chave, {"replays": 0, "comOutroNumero": 0, "comNumeroForaDaVoz": 0})
        s["replays"] += 1
        s["comOutroNumero"] += bool(fora_da_mensagem)
        s["comNumeroForaDaVoz"] += bool(fora_da_voz)
        detalhes.append({"sessao": dados["sessao"][:10], "id": int(id_), "origem": m["origem"], "volta": m.get("volta"),
                         "titulo": m.get("titulo"), "fala": m.get("fala"),
                         "rotulos": [r for c in rep["curvas"] for r in rotulos(c)],
                         "foraDaMensagem": fora_da_mensagem, "foraDaVoz": fora_da_voz})

print(json.dumps({"modo": MODO,
                  "resumo": [{"sessao": k[0], "origem": k[1], **v} for k, v in sorted(resumo.items())],
                  "detalhes": detalhes}, ensure_ascii=False, indent=1))
