"""Pedido 36 (pedido no chat): o que ocupa o logs/backend.log de 3,8 GB. So le o arquivo.

Cada linha vira um "tipo": as datas, os numeros, os enderecos e as consultas trocados
por '#'. Para cada tipo: as linhas, os bytes e o periodo (a ultima linha datada antes
dele; as linhas de acesso do uvicorn nao tem data). Tambem os bytes por dia.

Uso: python varrer_log.py <log> <saida.json>
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

LOG, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
DATA = re.compile(rb"^(\d{4}-\d\d-\d\d) (\d\d:\d\d):\d\d")
TROCAS = [(re.compile(rb"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d+"), b"<data>"),
          (re.compile(rb"\?[^ \"]*"), b"?<consulta>"),
          (re.compile(rb"\d+(\.\d+)?"), b"#")]
tipos = defaultdict(lambda: {"linhas": 0, "bytes": 0, "de": None, "ate": None})
por_dia = defaultdict(int)
dia, momento = "(antes da primeira data)", None
total = linhas = 0
with LOG.open("rb") as f:
    for linha in f:
        total += len(linha)
        linhas += 1
        m = DATA.match(linha)
        if m:
            dia, momento = m.group(1).decode(), f"{m.group(1).decode()} {m.group(2).decode()}"
        chave = linha[:160].rstrip()
        for padrao, troca in TROCAS:
            chave = padrao.sub(troca, chave)
        t = tipos[chave]
        t["linhas"] += 1
        t["bytes"] += len(linha)
        if t["de"] is None:
            t["de"] = momento
        t["ate"] = momento
        por_dia[dia] += len(linha)
ordem = sorted(tipos.items(), key=lambda kv: -kv[1]["bytes"])
resultado = {"bytes": total, "linhas": linhas, "tipos": len(tipos),
             "maiores": [{"tipo": k.decode("utf-8", "replace"), **v, "porcento": round(100 * v["bytes"] / total, 2)}
                         for k, v in ordem[:25]],
             "porDia": {d: round(b / 2**20, 1) for d, b in sorted(por_dia.items())}}
SAIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in resultado.items() if k != "maiores"}, ensure_ascii=False)[:3000])
for x in resultado["maiores"][:15]:
    print(f"{x['porcento']:6.2f}%  {x['linhas']:>10}  {x['de']} -> {x['ate']}  {x['tipo'][:110]}")
