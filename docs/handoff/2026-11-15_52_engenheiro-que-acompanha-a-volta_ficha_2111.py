"""Pedido 52, depois do teste de 21/11: a proposta da "ficha da curva" (o formato que o Eduardo pediu as 18h51):

    "Curva X, freie entre a placa de 100 e a de 50, mova o carro para a zebra do lado X e mantenha X de
    velocidade. A curva X pode ser feita de pe embaixo ou com trail braking."

So leitura: a volta de referencia (`data/reference_models/vhe_interlagos.volta_do_modelo.json`), os marcos
(`vhe_interlagos.marcos.json`) e a geometria oficial. Nada do app muda. Para cada curva:

* **a frenagem:** a frenagem da referencia (a regra do engenheiro, desde a saida do trecho anterior) entre as
  duas placas que a cercam; sem placa no trecho, o marco mais perto (a frase do engenheiro, no molde b);
* **a tecnica:** "de pe embaixo" (sem frenagem e o acelerador em 0,90 ou mais de 50 m antes da entrada ao
  apice), "so um alivio" (sem frenagem, com o acelerador abaixo de 0,90), "com trail braking" (o freio ainda pisado 10 m ou mais depois da entrada da curva)
  ou "frenagem em linha reta" (o freio solto antes da entrada). So o momento do freio, nunca a forca;
* **o lado da entrada:** a lateral da referencia na frenagem (ou 50 m antes da entrada), quando passa de metade
  da meia largura da pista; positivo e a esquerda;
* **a zebra do apice:** a zebra do lado de dentro que cobre o apice (ate 25 m), quando a referencia passa a
  menos de 1,5 m da borda de dentro;
* **a minima:** a velocidade minima da referencia na curva, arredondada de 5 em 5 km/h, e a marcha nela.

Grava o JSON e, com `--audio`, a fala de cada curva com a voz do projeto (Daniel a 1,4x, sem a vinheta) em
`data/radio/[teste] fichas das curvas 21-11/` (fora da pasta do jogo e fora do git), com a duracao.

Uso (na pasta backend): python <este arquivo> <saida.json> [--audio]
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")
from core.assisted_analysis import volta_do_modelo as VM  # noqa: E402
from core.engenheiro import plano as P  # noqa: E402
from core.engenheiro import regras as R  # noqa: E402
from core.radio.analise import grade  # noqa: E402
from core.radio.janelas import carregar_geometria  # noqa: E402
from ml.pista_teste.por_trecho import FREIO_INICIO  # noqa: E402  (0,10: o freio pisado, ADR 0030)
from ml.track.corners import detect_corners  # noqa: E402

SAIDA = Path(sys.argv[1])
COM_AUDIO = "--audio" in sys.argv
REPO = Path("..").resolve()
track = carregar_geometria(REPO)
L = float(track.length)
S = np.asarray(track.s, float)
trechos = R.trechos_da_pista(track)
curvas = {round(c.apex_s, 1): c for c in detect_corners(track)}
dados = VM.encontrar([REPO], "vhe_interlagos")
G = grade(VM.como_volta_do_store(dados))
total = float(dados["tempo_s"])
lateral = np.asarray(dados["grade"]["lateral"], float)
marcha = np.asarray(dados["grade"]["gear"], float)
freio = np.asarray(G["freio"], float)
acel = np.asarray(G["acelerador"], float)
vel = np.asarray(G["velocidade"], float)
larg_esq = np.asarray(track.width_left, float)
larg_dir = np.asarray(track.width_right, float)
marcos = json.loads((REPO / "data/reference_models/vhe_interlagos.marcos.json").read_text(encoding="utf-8"))["marcos"]
placas = sorted([m for m in marcos if m["tipo"] == "placa"], key=lambda m: m["s"])
zebras = [m for m in marcos if m["tipo"] == "zebra"]
conf = json.loads((REPO / "docs/handoff/2026-11-15_52_engenheiro-que-acompanha-a-volta_conferencia_da_volta_do_modelo.json")
                  .read_text(encoding="utf-8"))
frases = {f["trecho"]: f for f in conf["frases"]}
NUM = {1: "um", 2: "dois", 3: "três", 4: "quatro", 5: "cinco", 6: "seis", 7: "sete", 8: "oito", 9: "nove", 10: "dez",
       11: "onze", 12: "doze", 13: "treze", 14: "catorze"}
MARCHA = {1: "primeira", 2: "segunda", 3: "terceira", 4: "quarta", 5: "quinta", 6: "sexta", 7: "sétima", 8: "oitava"}


def i_de(s):
    return int(track.index_of(float(s) % L))


def entre(a, b, s):
    """s no intervalo [a, b) da volta (com a volta pela linha)."""
    a, b, s = a % L, b % L, s % L
    return a <= s < b if a <= b else (s >= a or s < b)


def lado_da_lateral(lat, i):
    meia = larg_esq[i] if lat > 0 else larg_dir[i]
    if abs(lat) < 0.5 * meia:
        return None
    return "esquerda" if lat > 0 else "direita"


fichas = []
for k, t in enumerate(trechos):
    if not t.tem_curva:
        continue
    n = R.numero_da_curva(t.nome)
    c = curvas.get(round(t.apice_s, 1))
    lado = ("esquerda" if c.direction > 0 else "direita") if c is not None else None
    pts = R.pontos_do_trecho(G, total, track, trechos, k)
    busca = R.inicio_da_busca_da_freada(trechos, k)
    freada = pts["freada"]
    # a tecnica (so o momento do freio e do acelerador)
    curva_toda = [j for j in range(len(S)) if entre(t.entrada_s - 50.0, t.apice_s, S[j])]
    # o acelerador da IA cai a 0 por 1 ou 2 pontos (2 a 4 m) nas trocas de marcha: so conta como alivio uma
    # queda abaixo de 0,90 por 10 m ou mais (5 pontos da grade)
    pontos_de_alivio = int(np.sum(acel[curva_toda] < 0.90)) if curva_toda else 0
    freio_max = float(np.nanmax(freio[curva_toda])) if curva_toda else float("nan")
    pe_embaixo = freada is None and (bool(pts["semTirarOPe"]) or (pontos_de_alivio < 5 and freio_max < FREIO_INICIO))
    if pe_embaixo:
        tecnica = "de pé embaixo"
    elif freada is None:
        tecnica = "só um alívio"
    else:
        depois = [j for j in range(len(S)) if entre(t.entrada_s + 10.0, t.apice_s, S[j])]
        tecnica = "com trail braking" if any(freio[j] >= FREIO_INICIO for j in depois) else "frenagem em linha reta"
    # a frenagem entre as placas
    frenagem = None
    if freada is not None:
        zona = [p for p in placas if entre(busca, t.apice_s, p["s"])]
        antes = [p for p in zona if (freada - p["s"]) % L < L / 2]
        depois_p = [p for p in zona if (p["s"] - freada) % L < L / 2 and p not in antes]
        a = max(antes, key=lambda p: p["s"]) if antes else None
        b = min(depois_p, key=lambda p: p["s"]) if depois_p else None
        if a and b:
            frenagem = {"texto": f"freie entre a placa de {a['valor']} e a de {b['valor']}", "falado": f"freie entre o {a['valor']} e o {b['valor']}"}
        elif b:
            frenagem = {"texto": f"freie antes da placa de {b['valor']}", "falado": f"freie antes do {b['valor']}"}
        elif a and (freada - a["s"]) % L <= 40.0:
            frenagem = {"texto": f"freie logo depois da placa de {a['valor']}", "falado": f"freie logo depois do {a['valor']}"}
        else:
            f = (frases.get(t.nome) or {}).get("freie")
            if f:
                txt = P.frase_falada("freie", f.get("marco"), f.get("d"), "b", f["frase"])
                frenagem = {"texto": txt, "falado": txt}
    # o lado da entrada
    ref_entrada = freada if freada is not None else t.entrada_s - 50.0
    i0 = i_de(ref_entrada)
    lado_entrada = lado_da_lateral(lateral[i0], i0)
    # a zebra do apice
    ia = i_de(t.apice_s)
    borda = larg_esq[ia] if lado == "esquerda" else larg_dir[ia]
    dentro = lateral[ia] if lado == "esquerda" else -lateral[ia]
    zebra = None
    if lado and borda - dentro <= 1.5:
        zs = [z for z in zebras if z["lado"] == lado and entre(z["s"] - 25.0, z["sFim"] + 25.0, t.apice_s)]
        if zs:
            zebra = f"a zebra da {lado}"
    # a minima e a marcha nela
    # a minima: da entrada (menos 50 m) a saida da curva; de pe embaixo, a velocidade no apice
    idx = np.asarray([j for j in range(len(S)) if entre(t.entrada_s - 50.0, t.saida_s, S[j])])
    j = ia if pe_embaixo else idx[int(np.argmin(vel[idx]))]
    minima = int(5 * round(float(vel[j]) / 5.0))
    m = int(marcha[j]) if np.isfinite(marcha[j]) else None
    # o texto
    partes_escritas = [f"Curva {n}, à {lado}" if lado else f"Curva {n}"]
    partes_faladas = [f"Curva {NUM.get(n, n)}, à {lado}." if lado else f"Curva {NUM.get(n, n)}."]
    if frenagem:
        partes_escritas.append(f"{frenagem['texto']}, {tecnica}")
        partes_faladas.append(f"{frenagem['falado'][0].upper()}{frenagem['falado'][1:]}, {tecnica}.")
    else:
        partes_escritas.append(tecnica)
        partes_faladas.append(f"{tecnica[0].upper()}{tecnica[1:]}.")
    mov = []
    if lado_entrada and lado and lado_entrada != lado:
        mov.append(f"entre pela {lado_entrada}")
    if zebra:
        mov.append(f"tangencie {zebra}")
    if mov:
        partes_escritas.append(" e ".join(mov))
        texto = " e ".join(mov)
        partes_faladas.append(f"{texto[0].upper()}{texto[1:]}.")
    if pe_embaixo:
        partes_escritas.append(f"passe a {minima} km/h no ápice" + (f", em {MARCHA.get(m, m)}" if m else ""))
        partes_faladas.append(f"Passe a {minima}.")
    else:
        partes_escritas.append(f"mínima de {minima} km/h" + (f", em {MARCHA.get(m, m)}" if m else ""))
        partes_faladas.append(f"Mínima de {minima}.")
    fichas.append({
        "trecho": t.nome, "curva": n, "lado": lado, "freadaS": None if freada is None else round(float(freada), 1),
        "entradaS": round(float(t.entrada_s), 1), "apiceS": round(float(t.apice_s), 1), "tecnica": tecnica,
        "frenagem": frenagem, "ladoDaEntrada": lado_entrada, "lateralNaEntradaM": round(float(lateral[i0]), 2),
        "zebraDoApice": zebra, "lateralNoApiceM": round(float(lateral[ia]), 2), "bordaDeDentroM": round(float(borda), 2),
        "minimaKmh": round(float(vel[j]), 1), "minimaArredondada": minima, "marcha": m,
        "escrita": "; ".join(partes_escritas) + ".", "fala": " ".join(partes_faladas),
    })

if COM_AUDIO:
    from core.radio.audio import falar
    destino = REPO / "data" / "radio" / "[teste] fichas das curvas 21-11"
    destino.mkdir(parents=True, exist_ok=True)
    for f in fichas:
        arq = destino / f"{f['trecho']}.wav"
        f["arquivo"] = str(arq)
        f["duracaoS"] = round(float(falar(f["fala"], arq, vinheta_antes=False)), 2)

SAIDA.write_text(json.dumps({"pedido": "52, depois do teste de 21/11", "voltaDeReferencia": dados.get("tempo"),
                             "fichas": fichas}, ensure_ascii=False, indent=1), encoding="utf-8")
for f in fichas:
    print(f["trecho"], f.get("duracaoS"), "|", f["fala"])
    print("   ", f["escrita"])
