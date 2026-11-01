"""Pedido 43, depois do teste no jogo: guarda o que o backend entregou e mede o FPS pelo log do CSP.

So le: as rotas do rádio do backend aberto (as mensagens, cada replay e a grade) e o log do CSP. Os
replays so ficam na memoria do backend, entao rode com o app ainda aberto.

* `<saida>_jogo.json`, no formato do `radio_offline.py`, para o `conferir_rotulos.py`: as mensagens,
  os replays, a grade e os bytes de cada rota;
* o FPS: cada bloco de 10 s do log (`fps: media ...`), separado pela situacao da janela do replay e
  por o replay estar mesmo na tela (de `entregueEm` ate `entregueEm + restaS`, com o relogio do log
  alinhado pela primeira mensagem: a de teste, "voz: url tocou").

Uso: python ler_o_teste.py <porta> <log do CSP> <registro do radio .jsonl> <saida>
"""
import json
import re
import statistics
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

PORTA, LOG, REGISTRO, SAIDA = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
BASE = f"http://127.0.0.1:{PORTA}"


def pegar(rota):
    with urllib.request.urlopen(BASE + rota, timeout=20) as r:
        return r.read().decode("utf-8")


arq = SAIDA.with_name(SAIDA.name + "_jogo.json")
try:
    d = json.loads(pegar("/api/radio/mensagens?desde=0"))
    replays, bytes_ = {}, {}
    for m in d["mensagens"]:
        if (m.get("replay") or {}).get("url"):
            corpo = pegar(m["replay"]["url"])
            replays[str(m["id"])] = json.loads(corpo)
            bytes_[str(m["id"])] = len(corpo.encode("utf-8"))
    dados = {"sessao": REGISTRO.stem, "mensagens": d["mensagens"], "replays": replays, "bytesDaRota": bytes_,
             "grade": json.loads(pegar("/api/radio/grade")), "evidencias": []}
    arq.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    print("guardado:", arq, len(d["mensagens"]), "mensagens,", len(replays), "replays")
except OSError as erro:
    # o backend ja fechou: fica o que foi guardado da vez anterior
    print("backend fora:", erro)
    dados = json.loads(arq.read_text(encoding="utf-8"))

# ── o FPS ──
texto = LOG.read_bytes().decode("utf-8", "replace")
BLOCO = re.compile(r"^\s*(\d+)\s.*\[radio_engenheiro\] fps: média ([\d,]+) \(mín (\d+), máx (\d+)\) em (\d+) s; "
                   r"minimapa ([^;]+); mapa aproximado ([^;]+); replay (.+?)\s*$", re.M)
blocos = [{"ms": int(a), "fps": float(b.replace(",", ".")), "min": int(c), "max": int(e), "n": int(f),
           "mini": g, "perto": h, "replay": i} for a, b, c, e, f, g, h, i in BLOCO.findall(texto)]
registro = [json.loads(x) for x in REGISTRO.read_text(encoding="utf-8").splitlines() if x.strip()]
hora = lambda m: datetime.fromisoformat(m["entregueEm"]).timestamp()  # noqa: E731
teste = next(m for m in registro if m["origem"] == "teste")
voz = re.search(r"^\s*(\d+)\s.*\[radio_engenheiro\] voz: url tocou", texto, re.M)
zero = hora(teste) - int(voz.group(1)) / 1000.0
na_tela = [(hora(m) - zero, hora(m) - zero + float(m.get("restaS") or 0)) for m in registro if m.get("replay")]
for b in blocos:
    fim, ini = b["ms"] / 1000.0, b["ms"] / 1000.0 - b["n"]
    b["replayNaTela"] = sum(max(0.0, min(fim, y) - max(ini, x)) for x, y in na_tela) / max(b["n"], 1)


def resumo(nome, lista):
    if not lista:
        print(f"{nome}: nenhum bloco")
        return
    v = [b["fps"] for b in lista]
    print(f"{nome}: {len(v)} blocos, media {statistics.mean(v):.1f}, mediana {statistics.median(v):.1f}, "
          f"de {min(v):.1f} a {max(v):.1f}; minimo de um quadro {min(b['min'] for b in lista)}")


print("blocos de FPS:", len(blocos))
por_situacao = {}
for b in blocos:
    por_situacao.setdefault((b["mini"], b["perto"], b["replay"]), []).append(b)
for chave, lista in sorted(por_situacao.items(), key=lambda x: -len(x[1])):
    resumo(f"minimapa {chave[0]} | aproximado {chave[1]} | replay {chave[2]}", lista)
com = [b for b in blocos if b["replay"] == "ligado"]
resumo("janela do replay ligada, replay na tela em metade do bloco ou mais", [b for b in com if b["replayNaTela"] >= 0.5])
resumo("janela do replay ligada, sem replay na tela", [b for b in com if b["replayNaTela"] == 0])
resumo("janela do replay desligada", [b for b in blocos if b["replay"] == "desligado"])
SAIDA.with_name(SAIDA.name + "_fps.json").write_text(json.dumps(blocos, ensure_ascii=False, indent=0), encoding="utf-8")
