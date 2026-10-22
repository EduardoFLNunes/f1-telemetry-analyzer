"""Pedido 35, fechamento: a fala nova da analise ("Minima 102 contra 128.") nas 5 analises reais.

Para cada analise registrada (as curvas, as perdas e as diferencas medidas), monta a
mensagem com o texto de agora e gera a voz de cada variante, da mais completa a mais
curta, ate a primeira que cabe no limite da analise (8,8 s), como o radio faz.

Uso (na pasta backend): python fala_da_analise.py <saida.json> <registro ou conferencia>...
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")
from core.radio import audio  # noqa: E402
from core.radio.texto import FALA_MAXIMA_S, mensagem_de_analise  # noqa: E402

saida, fontes = Path(sys.argv[1]), sys.argv[2:]
resultado = []
pasta = Path(tempfile.mkdtemp(prefix="fala_analise_"))
for fonte in fontes:
    texto = Path(fonte).read_text(encoding="utf-8")
    msgs = json.loads(texto)["mensagens"] if fonte.endswith(".json") else [json.loads(l) for l in texto.splitlines()]
    for antiga in (m for m in msgs if m["origem"] == "analise"):
        analise = {"voltas": antiga["voltasAnalisadas"], "curvas": antiga["curvasDaAnalise"]}
        nova = mensagem_de_analise(analise, "volta_ia")
        escolhida, duracao, tentadas = None, None, []
        for i, fala in enumerate(nova["falas"]):
            d = audio.falar(fala, pasta / f"{len(resultado)}_{i}.wav")
            tentadas.append({"fala": fala, "duracaoS": round(d, 2)})
            if d <= FALA_MAXIMA_S["analise"]:
                escolhida, duracao = fala, d
                break
        resultado.append({"fonte": Path(fonte).name, "voltas": antiga["voltasAnalisadas"], "falaAntiga": antiga["fala"],
                          "duracaoAntigaS": antiga.get("duracaoS"), "falaNova": escolhida,
                          "duracaoNovaS": round(duracao, 2) if duracao else None, "tentadas": tentadas})
        print(resultado[-1]["voltas"], "|", antiga["fala"], antiga.get("duracaoS"), "->", escolhida, resultado[-1]["duracaoNovaS"])
saida.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
