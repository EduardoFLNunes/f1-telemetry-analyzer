"""A ficha da curva (pedido 52; ADR 0033, decisoes do Eduardo de 21/11, itens 6 a 8 e 11): funcoes puras, sem
estado, testadas com dados sinteticos. Vale para qualquer pista e qualquer trecho.

* **onde frear:** o ponto de frenagem da referencia entre as duas placas que o cercam; sem placa, o marco mais
  perto no molde (b);
* **a tecnica:** "de pe embaixo" e "so um alivio" pela referencia; "com trail braking" ou "frenagem em linha
  reta" pela melhor passagem do piloto (nunca pelo pedal da IA; ADR 0032, item 5); sem passagem dele, fora;
* **a linha:** o lado da entrada e a zebra do apice, pela lateral da referencia (positiva a esquerda);
* **a velocidade:** a minima da referencia (ou a velocidade no apice, de pe embaixo), de 5 em 5 km/h;
* **o lembrete:** a parte de onde frear, com o numero da curva por extenso.

A marcha fica fora (ADR 0033, emenda de 21/11, item 6).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from . import plano as P
from . import regras as R

FREIO_PISADO = 0.10                 # item 7: o freio pisado (o mesmo limite do ADR 0030)
TRAIL_DEPOIS_DA_ENTRADA_M = 10.0    # item 7: o freio pisado 10 m ou mais depois da entrada
LOGO_DEPOIS_DA_PLACA_M = 40.0       # item 6: "logo depois da placa de 50"
ZEBRA_PERTO_DO_APICE_M = 25.0       # item 6: a zebra de dentro que cobre o apice
BORDA_NO_APICE_M = 1.5              # item 6: a referencia a 1,5 m ou menos da borda de dentro
ANTES_DA_ENTRADA_M = 50.0           # itens 6 e 7: 50 m antes da entrada

FRENAGEM, PE_EMBAIXO, ALIVIO = "frenagem", "pé embaixo", "alívio"


def _entre(a: float, b: float, s: float, L: float) -> bool:
    a, b, s = a % L, b % L, s % L
    return a <= s < b if a <= b else (s >= a or s < b)


def _indices(track, a: float, b: float) -> np.ndarray:
    s = np.asarray(track.s, float)
    L = float(track.length)
    a, b = a % L, b % L
    sel = np.flatnonzero((s >= a) & (s < b)) if a <= b else np.concatenate([np.flatnonzero(s >= a), np.flatnonzero(s < b)])
    return sel


def lado_da_curva(track, trecho) -> Optional[str]:
    """O lado da curva pela direcao do `detect_corners` (1: esquerda), casado pelo apice."""
    from ml.track.corners import detect_corners

    if trecho.apice_s is None:
        return None
    for c in detect_corners(track):
        if abs(float(c.apex_s) - float(trecho.apice_s)) < 1.0:
            return "esquerda" if c.direction > 0 else "direita"
    return None


def tecnica_da_passagem(grade: Optional[Dict[str, np.ndarray]], track, trechos: Sequence[Any], k: int) -> Optional[str]:
    """Item 7: "com trail braking" (o freio pisado 10 m ou mais depois da entrada, ate o apice) ou "frenagem em
    linha reta" (solto antes), na passagem do piloto. None: sem passagem, ou sem frenagem nela."""
    from core.radio.analise import freada_desde

    if grade is None:
        return None
    t = trechos[k]
    freio = np.nan_to_num(np.asarray(grade["freio"], float))
    if freada_desde(freio, track, R.inicio_da_busca_da_freada(trechos, k), float(t.apice_s)) is None:
        return None
    depois = _indices(track, float(t.entrada_s) + TRAIL_DEPOIS_DA_ENTRADA_M, float(t.apice_s))
    if len(depois) and bool(np.any(freio[depois] >= FREIO_PISADO)):
        return "com trail braking"
    return "frenagem em linha reta"


def onde_frear(s_freada: float, placas: Sequence[Dict[str, Any]], de: float, ate: float, L: float
               ) -> Optional[Dict[str, str]]:
    """Item 6: o ponto entre as duas placas que o cercam (as placas de `de` a `ate`). None: sem placa que sirva."""
    zona = [p for p in placas if _entre(de, ate, float(p["s"]), L)]
    antes = [p for p in zona if (s_freada - float(p["s"])) % L < L / 2]
    depois = [p for p in zona if p not in antes]
    a = max(antes, key=lambda p: (float(p["s"]) - de) % L) if antes else None
    b = min(depois, key=lambda p: (float(p["s"]) - de) % L) if depois else None
    if a and b:
        return {"texto": f"freie entre a placa de {a['valor']} e a de {b['valor']}",
                "falado": f"freie entre o {a['valor']} e o {b['valor']}", "lembrete": f"entre o {a['valor']} e o {b['valor']}"}
    if b:
        return {"texto": f"freie antes da placa de {b['valor']}", "falado": f"freie antes do {b['valor']}",
                "lembrete": f"antes do {b['valor']}"}
    if a and (s_freada - float(a["s"])) % L <= LOGO_DEPOIS_DA_PLACA_M:
        return {"texto": f"freie logo depois da placa de {a['valor']}", "falado": f"freie logo depois do {a['valor']}",
                "lembrete": f"logo depois do {a['valor']}"}
    return None


def _maiuscula(texto: str) -> str:
    return f"{texto[0].upper()}{texto[1:]}" if texto else texto


def ficha_da_curva(k: int, ref: Dict[str, Any], track, trechos: Sequence[Any], marcos: Sequence[Dict[str, Any]],
                   pontos_dos_marcos: Sequence[Dict[str, Any]], passagem: Optional[Dict[str, np.ndarray]] = None
                   ) -> Optional[Dict[str, Any]]:
    """A ficha da curva do trecho `k` (ADR 0033, emenda de 21/11, itens 6, 7 e 11). `ref`: a volta de referencia
    ({grade, tempoS}); `marcos`: os marcos da pista (as placas e as zebras); `passagem`: a grade da melhor passagem
    do piloto no trecho (a tecnica com frenagem). None: o trecho nao tem curva."""
    t = trechos[k]
    if not t.tem_curva:
        return None
    L = float(track.length)
    g = ref["grade"]
    s = np.asarray(track.s, float)
    n = R.numero_da_curva(t.nome)
    nome = P.NUMEROS.get(int(n), str(n)) if n is not None else t.nome
    lado = lado_da_curva(track, t)
    pts = R.pontos_do_trecho(g, float(ref["tempoS"]), track, trechos, k)
    freada = pts["freada"]
    acel = np.nan_to_num(np.asarray(g["acelerador"], float))
    freio = np.nan_to_num(np.asarray(g["freio"], float))
    vel = np.asarray(g["velocidade"], float)
    lateral = np.nan_to_num(np.asarray(g.get("lateral", np.zeros_like(vel)), float))
    curva = _indices(track, float(t.entrada_s) - ANTES_DA_ENTRADA_M, float(t.apice_s))
    # a tecnica (itens 7 e 8)
    if freada is not None:
        tipo = FRENAGEM
        tecnica = tecnica_da_passagem(passagem, track, trechos, k)
        tecnica_de = "sua melhor passagem" if tecnica else None
    elif len(curva) and not R.tem_alivio(acel, track, curva) and float(freio[curva].max()) < FREIO_PISADO:
        tipo, tecnica, tecnica_de = PE_EMBAIXO, "de pé embaixo", "referência"
    else:
        tipo, tecnica, tecnica_de = ALIVIO, "só um alívio", "referência"
    # onde frear (item 6)
    frenagem = None
    if freada is not None:
        placas = [m for m in marcos if m.get("tipo") == "placa" and m.get("valor") is not None]
        frenagem = onde_frear(float(freada), placas, R.inicio_da_busca_da_freada(trechos, k), float(t.apice_s), L)
        if frenagem is None:
            f = R.frase_da_acao("freie", float(freada), pontos_dos_marcos, L)
            texto = P.frase_falada("freie", f.get("marco"), f.get("d"), "b", f["frase"])
            frenagem = {"texto": texto, "falado": texto, "lembrete": texto}
    # a linha (item 6)
    i0 = int(track.index_of(float(freada) if freada is not None else float(t.entrada_s) - ANTES_DA_ENTRADA_M))
    larg_esq = np.asarray(getattr(track, "width_left", np.full(len(s), 6.0)), float)
    larg_dir = np.asarray(getattr(track, "width_right", np.full(len(s), 6.0)), float)
    lat0 = float(lateral[i0])
    meia = larg_esq[i0] if lat0 > 0 else larg_dir[i0]
    lado_entrada = ("esquerda" if lat0 > 0 else "direita") if abs(lat0) >= 0.5 * float(meia) else None
    ia = int(track.index_of(float(t.apice_s)))
    zebra = None
    if lado:
        borda = float(larg_esq[ia] if lado == "esquerda" else larg_dir[ia])
        dentro = float(lateral[ia] if lado == "esquerda" else -lateral[ia])
        if borda - dentro <= BORDA_NO_APICE_M:
            if any(m.get("tipo") == "zebra" and m.get("lado") == lado and m.get("sFim") is not None
                   and _entre(float(m["s"]) - ZEBRA_PERTO_DO_APICE_M, float(m["sFim"]) + ZEBRA_PERTO_DO_APICE_M,
                              float(t.apice_s), L) for m in marcos):
                zebra = f"a zebra da {lado}"
    movimento = []
    if lado_entrada and lado and lado_entrada != lado:
        movimento.append(f"entre pela {lado_entrada}")
    if zebra:
        movimento.append(f"tangencie {zebra}")
    # a velocidade (item 6)
    if tipo == PE_EMBAIXO:
        v = float(vel[ia])
    else:
        idx = _indices(track, float(t.entrada_s) - ANTES_DA_ENTRADA_M, float(t.saida_s))
        v = float(np.nanmin(vel[idx])) if len(idx) else float(vel[ia])
    v5 = int(5 * round(v / 5.0))
    # o texto
    cabeca_f = f"Curva {nome}, à {lado}." if lado else f"Curva {nome}."
    cabeca_e = f"Curva {n}, à {lado}" if lado else f"Curva {n}"
    fala, escrita = [cabeca_f], [cabeca_e]
    if frenagem:
        fala.append(_maiuscula(frenagem["falado"]) + (f", {tecnica}." if tecnica else "."))
        escrita.append(frenagem["texto"] + (f", {tecnica}" if tecnica else ""))
    else:
        fala.append(_maiuscula(tecnica) + ".")
        escrita.append(tecnica)
    if movimento:
        m = " e ".join(movimento)
        fala.append(_maiuscula(m) + ".")
        escrita.append(m)
    if tipo == PE_EMBAIXO:
        fala.append(f"Passe a {v5}.")
        escrita.append(f"passe a {v5} km/h no ápice")
    else:
        fala.append(f"Mínima de {v5}.")
        escrita.append(f"mínima de {v5} km/h")
    # o lembrete (item 11)
    if frenagem:
        lembrete = frenagem["lembrete"]
    else:
        lembrete = "pé embaixo" if tipo == PE_EMBAIXO else "só um alívio"
    # o ponto da ficha: a frenagem da referencia (a marca e o ultimo bipe); sem frenagem, a entrada
    s_ponto = float(freada) if freada is not None else float(t.entrada_s)
    marca = None
    if freada is not None:
        k_ponto = int(track.index_of(float(freada)))
        x, z = track.to_world([float(freada)], [float(lateral[k_ponto])])[0]
        marca = {"x": round(float(x), 2), "z": round(float(z), 2),
                 "direcao": [round(float(track.tangent[k_ponto][0]), 4), round(float(track.tangent[k_ponto][1]), 4)]}
    return {
        "trecho": t.nome, "k": k, "curva": n, "lado": lado, "tipo": tipo, "tecnica": tecnica, "tecnicaDe": tecnica_de,
        "sFreada": None if freada is None else round(float(freada), 1), "sPonto": round(s_ponto % L, 1),
        "sEntrada": round(float(t.entrada_s), 1), "frenagem": None if frenagem is None else frenagem["texto"],
        "ladoDaEntrada": lado_entrada, "zebra": zebra, "velocidadeKmh": v5, "refMinimaKmh": pts.get("minimaKmh"),
        "fala": " ".join(fala), "escrita": "; ".join(escrita) + ".",
        "lembrete": f"{_maiuscula(nome)}: {lembrete}." if n is not None else _maiuscula(lembrete) + ".",
        "marca": marca,
    }


def instrucao_principal(ficha: Dict[str, Any]) -> Dict[str, Any]:
    """ADR 0033, emenda de 21/11, item 4: a instrucao da ficha que a conferencia mede (a mesma medida do item 8):
    a frenagem no ponto da referencia; "sem tirar o pe"; ou a minima da referencia (so um alivio)."""
    acao = {FRENAGEM: "freie", PE_EMBAIXO: R.SEM_TIRAR_O_PE, ALIVIO: "vire"}[ficha["tipo"]]
    return {"trecho": ficha["trecho"], "acao": acao, "sDito": ficha["sPonto"], "refMinimaKmh": ficha.get("refMinimaKmh"),
            "marco": None}


def lista_de_fichas(ref: Dict[str, Any], track, trechos: Sequence[Any], marcos: Sequence[Dict[str, Any]],
                    pontos_dos_marcos: Sequence[Dict[str, Any]],
                    passagens: Optional[Dict[str, Dict[str, np.ndarray]]] = None) -> List[Dict[str, Any]]:
    out = []
    for k in range(len(trechos)):
        f = ficha_da_curva(k, ref, track, trechos, marcos, pontos_dos_marcos, (passagens or {}).get(trechos[k].nome))
        if f is not None:
            out.append(f)
    return out


def texto_da_conferencia(ficha: Dict[str, Any], conf: Dict[str, Any]) -> str:
    """A conferencia do foco em uma frase curta (o cartao e a voz do resumo da volta):
    "Curva 1: freou 12 m antes do ponto"."""
    nome = f"Curva {ficha['curva']}" if ficha.get("curva") is not None else ficha["trecho"]
    if conf.get("aplicada") is None:
        return f"{nome}: {conf.get('motivo') or 'sem medida'}"
    if ficha["tipo"] == FRENAGEM:
        dif = float(conf.get("difM") or 0.0)
        if conf["aplicada"]:
            return f"{nome}: freou no ponto"
        return f"{nome}: freou {abs(dif):.0f} m {'depois' if dif > 0 else 'antes'} do ponto"
    if ficha["tipo"] == PE_EMBAIXO:
        return f"{nome}: sem tirar o pé" if conf["aplicada"] else f"{nome}: tirou o pé"
    dif = float(conf.get("difKmh") or 0.0)
    if conf["aplicada"]:
        return f"{nome}: mínima de {float(conf['valor']):.0f}, como a referência"
    return f"{nome}: mínima de {float(conf['valor']):.0f}, {abs(dif):.0f} km/h {'abaixo' if dif < 0 else 'acima'} da referência"
