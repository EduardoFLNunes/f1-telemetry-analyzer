"""Pedido 52, C.3: a duracao de cada aviso possivel dos 15 trechos, com a voz do projeto (Microsoft Daniel a
1,4x, `core.radio.audio.falar`: a vinheta e a voz, como o radio entrega), e se cabe no bloco de voz.

Para cada trecho em que a volta do modelo freia: `s_fala = s_freada - v x (t_frase + 1,0 s)` e o bloco que
termina na freada dele (ADR 0033, item 5). Os outros so na janela.

Uso (na pasta backend): python <este arquivo> <conferencia_da_volta_do_modelo.json> <saida.json>
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")
from core.engenheiro import regras as R  # noqa: E402
from core.radio.audio import falar  # noqa: E402

conf = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
L = float(conf["comprimentoM"])
pasta = Path(tempfile.mkdtemp(prefix="avisos_52_"))
saida = []
for f in conf["frases"]:
    p = f["pontos"]
    bloco = R.bloco_do_trecho(conf["blocos"], f["trecho"])
    for acao in ("freie", "vire", "acelere"):
        x = f.get(acao)
        if not x:
            continue
        dur = float(falar(x["fala"], pasta / f"{f['trecho'].replace('>', '')}_{acao}.wav"))
        item = {"trecho": f["trecho"], "acao": acao, "fala": x["fala"], "comMarco": x["comMarco"], "duracaoS": round(dur, 2)}
        if p.get("freada") is not None and p.get("velocidadeNaFreadaKmh"):
            sf = R.s_fala(p["freada"], p["velocidadeNaFreadaKmh"], dur, L)
            item["sFala"] = round(sf, 1)
            item["bloco"] = [bloco["inicio"], bloco["fim"]] if bloco else None
            item["cabeNoBloco"] = bool(bloco and x["comMarco"] and R.dentro_do_bloco(sf, bloco, L))
            item["voz"] = item["cabeNoBloco"]
            if not item["voz"]:
                item["porque"] = ("sem marco na janela" if not x["comMarco"] else
                                  "sem bloco antes da freada" if not bloco else "o s_fala cai antes do começo do bloco")
        else:
            item.update(sFala=None, bloco=None, cabeNoBloco=False, voz=False, porque="a referência não freia no trecho")
        saida.append(item)
        print(f"{item['trecho']:<11} {acao:<8} {dur:5.2f} s  voz={item['voz']!s:<5} {item.get('sFala')}  {x['fala']}", flush=True)
Path(sys.argv[2]).write_text(json.dumps({"pedido": 52, "voz": "OneCore:Daniel a 1,4x (com a vinheta)", "avisos": saida},
                                        ensure_ascii=False, indent=1), encoding="utf-8")
