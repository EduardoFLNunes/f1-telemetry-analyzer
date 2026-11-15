"""Os marcos da pista (pedido 52, Parte B; ADR 0033, item 3): lidos dos kn5, so leitura.

Cada marco e projetado na geometria oficial: o `s` e o lado (o vetor normal aponta para a
esquerda, ADR 0003: positivo e a esquerda).

* **as placas de freada:** as malhas com a textura `DISTMARKERB.DDS` ou `DISTMARKER.DDS`, uma placa
  por peca ligada (as placas de uma pista ficam juntas numa malha por material). O valor vem da
  coluna da textura nas faces da frente: 50, 100 e 200 em colunas de 1/4 da largura (o ultimo
  quarto e o verso, em branco); no `DISTMARKER.DDS`, so a metade de baixo tem os numeros;
* **as placas do DRS:** a textura `DISTMARKERDRS.DDS`;
* **as passarelas:** os materiais `ADVERT_OV01`, `ADVERT_OV02` e `OVERHEADAD_DETAILS`, das pecas que
  atravessam a pista (de um lado ao outro), juntas pelo `s`;
* **o portico da largada:** o material `STARTLIGHT_POLES`;
* **os postos de bandeira:** as malhas `marshall01` a `marshall20` do `obj_extra.kn5`, so os que
  ficam a ate `POSTO_MAXIMO_M` da linha central;
* **as zebras:** os materiais `RMB*`, uma zebra por peca ligada, com o comeco, o fim e o lado; so as
  que ficam na pista (a parte mais perto da linha central a ate `ZEBRA_MAXIMA_M`).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from core.kn5.kn5_marcos import Kn5, Malha, ler_kn5, pecas_ligadas

FORMATO = "marcos-da-pista/1"
ARQUIVOS = ("vhe_interlagos.kn5", "obj_extra.kn5")
TEXTURAS_DE_FREADA = {"DISTMARKERB.DDS": False, "DISTMARKER.DDS": True}   # True: so a metade de baixo
TEXTURA_DO_DRS = "DISTMARKERDRS.DDS"
MATERIAIS_DA_PASSARELA = ("ADVERT_OV01", "ADVERT_OV02", "OVERHEADAD_DETAILS")
MATERIAL_DO_PORTICO = "STARTLIGHT_POLES"
VALORES_DAS_COLUNAS = (50, 100, 200)      # a quarta coluna e o verso
POSTO_MAXIMO_M = 14.0
ZEBRA_MAXIMA_M = 12.0
JUNTAR_M = 30.0                           # pecas de uma passarela (ou do portico) a menos disto em s
MESMA_ZEBRA_M = 2.0                       # o verso de uma placa e a outra camada de uma zebra


def sha256(arquivo: Path) -> str:
    h = hashlib.sha256()
    with Path(arquivo).open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _area(p: np.ndarray, t: np.ndarray) -> np.ndarray:
    a, b, c = p[t[:, 0]], p[t[:, 1]], p[t[:, 2]]
    return 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)


def _projetar(track, pontos_xz: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    s, lat = track.project(np.asarray(pontos_xz, dtype=float))
    return np.asarray(s, dtype=float), np.asarray(lat, dtype=float)


def _lado(lateral: float) -> str:
    return "esquerda" if lateral > 0 else "direita"


def _media_circular(s: np.ndarray, L: float) -> float:
    ang = np.asarray(s) / L * 2 * np.pi
    m = np.arctan2(np.sin(ang).mean(), np.cos(ang).mean())
    return float(np.mod(m / (2 * np.pi) * L, L))


def valor_da_placa(malha: Malha, tri: np.ndarray, so_metade_de_baixo: bool) -> Tuple[Optional[int], Dict[str, float]]:
    """O valor da placa pela coluna da textura das faces com numero (a frente): a coluna com mais area."""
    uv = malha.uv[malha.triangulos[tri]].mean(axis=1)
    u = np.mod(uv[:, 0], 1.0)
    v = np.mod(uv[:, 1], 1.0)
    areas = _area(malha.posicoes, malha.triangulos[tri])
    coluna = np.minimum((u * 4).astype(int), 3)
    ok = coluna < 3
    if so_metade_de_baixo:
        ok &= v >= 0.5
    por = {}
    for k in range(3):
        por[str(VALORES_DAS_COLUNAS[k])] = float(areas[ok & (coluna == k)].sum())
    if not any(por.values()):
        return None, por
    k = max(range(3), key=lambda i: por[str(VALORES_DAS_COLUNAS[i])])
    return VALORES_DAS_COLUNAS[k], por


def _frente_para_quem_chega(track, malha: Malha, tri: np.ndarray, s: float) -> Optional[float]:
    """O cosseno entre a normal media das faces com numero e o sentido contrario ao da pista (quem chega).
    Perto de 1: a frente olha para o carro que vem."""
    t = malha.triangulos[tri]
    uv = malha.uv[t].mean(axis=1)
    frente = np.minimum((np.mod(uv[:, 0], 1.0) * 4).astype(int), 3) < 3
    if not frente.any():
        return None
    n = malha.normais[t[frente]].mean(axis=(0, 1))
    n2 = np.array([n[0], n[2]])
    if np.linalg.norm(n2) < 1e-9:
        return None
    k = int(track.index_of(s))
    return float(np.dot(n2 / np.linalg.norm(n2), -np.asarray(track.tangent[k])))


def _juntar_pelo_s(itens: List[Dict[str, Any]], L: float, juntar: float = JUNTAR_M) -> List[List[Dict[str, Any]]]:
    itens = sorted(itens, key=lambda x: x["s"])
    grupos: List[List[Dict[str, Any]]] = []
    for it in itens:
        if grupos and (it["s"] - grupos[-1][-1]["s"]) <= juntar:
            grupos[-1].append(it)
        else:
            grupos.append([it])
    if len(grupos) > 1 and (grupos[0][0]["s"] + L - grupos[-1][-1]["s"]) <= juntar:
        grupos[0] = grupos.pop() + grupos[0]
    return grupos


def ler_os_marcos(pasta_da_pista: Path, track) -> Dict[str, Any]:
    """Le os dois kn5 (so leitura) e devolve a tabela dos marcos, com o sha256 dos arquivos e o `geometry_id`."""
    pasta = Path(pasta_da_pista)
    pista = ler_kn5(pasta / ARQUIVOS[0])
    extra = ler_kn5(pasta / ARQUIVOS[1])
    L = float(track.length)
    marcos: List[Dict[str, Any]] = []
    fora: List[Dict[str, Any]] = []

    # as placas de freada e as do DRS
    for malha in pista.malhas:
        tex = (malha.textura or "").upper()
        if tex not in TEXTURAS_DE_FREADA and tex != TEXTURA_DO_DRS:
            continue
        for tri in pecas_ligadas(malha):
            vert = np.unique(malha.triangulos[tri].ravel())
            c = malha.posicoes[vert].mean(axis=0)
            s, lat = _projetar(track, [[c[0], c[2]]])
            item = {"s": round(float(s[0]), 1), "lateralM": round(float(lat[0]), 2), "lado": _lado(float(lat[0])),
                    "malha": malha.nome, "textura": malha.textura, "x": round(float(c[0]), 2),
                    "z": round(float(c[2]), 2), "y": round(float(c[1]), 2)}
            if tex == TEXTURA_DO_DRS:
                item["tipo"] = "placa_drs"
            else:
                valor, areas = valor_da_placa(malha, tri, TEXTURAS_DE_FREADA[tex])
                item.update(tipo="placa", valor=valor, areaPorColuna={k: round(v, 3) for k, v in areas.items()})
                cos = _frente_para_quem_chega(track, malha, tri, float(s[0]))
                item["frenteParaQuemChega"] = round(cos, 3) if cos is not None else None
            marcos.append(item)

    # as passarelas e o portico: as pecas que atravessam a pista, juntas pelo s
    def atravessam(materiais: Sequence[str], tipo: str) -> None:
        pecas = []
        for malha in pista.malhas:
            if malha.material not in materiais:
                continue
            for tri in pecas_ligadas(malha):
                vert = np.unique(malha.triangulos[tri].ravel())
                p = malha.posicoes[vert]
                s, lat = _projetar(track, p[:, [0, 2]])
                c = p.mean(axis=0)
                sc, latc = _projetar(track, [[c[0], c[2]]])
                pecas.append({"s": float(sc[0]), "latMin": float(lat.min()), "latMax": float(lat.max()),
                              "malha": malha.nome, "material": malha.material, "x": float(c[0]), "z": float(c[2]),
                              "y": float(c[1])})
        for grupo in _juntar_pelo_s(pecas, L):
            lmin, lmax = min(g["latMin"] for g in grupo), max(g["latMax"] for g in grupo)
            item = {"tipo": tipo, "s": round(_media_circular(np.array([g["s"] for g in grupo]), L), 1),
                    "lado": "atravessa", "lateralDeM": round(lmin, 1), "lateralAteM": round(lmax, 1),
                    "pecas": len(grupo), "materiais": sorted({g["material"] for g in grupo}),
                    "x": round(float(np.mean([g["x"] for g in grupo])), 2),
                    "z": round(float(np.mean([g["z"] for g in grupo])), 2),
                    "y": round(float(np.mean([g["y"] for g in grupo])), 2)}
            # De um lado ao outro: as pecas cobrem as duas bordas da pista naquele s.
            k = int(track.index_of(item["s"]))
            borda_esq, borda_dir = float(track.width_left[k]), float(track.width_right[k])
            item["bordasM"] = [round(-borda_dir, 1), round(borda_esq, 1)]
            if lmin <= -borda_dir and lmax >= borda_esq:
                marcos.append(item)
            else:
                fora.append({**item, "motivo": "nao atravessa a pista (nao cobre as duas bordas)"})

    atravessam(MATERIAIS_DA_PASSARELA, "passarela")
    atravessam((MATERIAL_DO_PORTICO,), "portico")
    # Um painel de passarela no mesmo lugar do portico e o painel do proprio portico.
    porticos = [m for m in marcos if m["tipo"] == "portico"]
    for m in [m for m in marcos if m["tipo"] == "passarela"]:
        if any(abs((m["s"] - p["s"] + L / 2) % L - L / 2) <= JUNTAR_M for p in porticos):
            marcos.remove(m)
            fora.append({**m, "motivo": "o painel do portico da largada (o mesmo s)"})

    # os postos de bandeira
    for malha in extra.malhas:
        if not malha.nome.lower().startswith("marshall"):
            continue
        c = malha.posicoes.mean(axis=0)
        s, lat = _projetar(track, [[c[0], c[2]]])
        item = {"tipo": "posto", "s": round(float(s[0]), 1), "lateralM": round(float(lat[0]), 2),
                "lado": _lado(float(lat[0])), "malha": malha.nome, "x": round(float(c[0]), 2),
                "z": round(float(c[2]), 2), "y": round(float(c[1]), 2)}
        if abs(float(lat[0])) <= POSTO_MAXIMO_M:
            marcos.append(item)
        else:
            fora.append({**item, "motivo": f"a mais de {POSTO_MAXIMO_M:.0f} m da linha central"})

    # as zebras
    for malha in pista.malhas:
        if not malha.material.upper().startswith("RMB"):
            continue
        for tri in pecas_ligadas(malha):
            vert = np.unique(malha.triangulos[tri].ravel())
            p = malha.posicoes[vert]
            s, lat = _projetar(track, p[:, [0, 2]])
            base = float(s[0])
            rel = np.mod(s - base + L / 2, L) - L / 2           # sem o salto na linha
            ini, fim = np.mod(base + rel.min(), L), np.mod(base + rel.max(), L)
            perto = float(np.min(np.abs(lat)))
            lado_lat = float(np.median(lat))
            c = p.mean(axis=0)
            item = {"tipo": "zebra", "s": round(float(ini), 1), "sFim": round(float(fim), 1),
                    "comprimentoM": round(float(rel.max() - rel.min()), 1), "lado": _lado(lado_lat),
                    "lateralM": round(lado_lat, 2), "maisPertoM": round(perto, 2), "malha": malha.nome,
                    "material": malha.material, "x": round(float(c[0]), 2), "z": round(float(c[2]), 2),
                    "y": round(float(c[1]), 2)}
            if perto <= ZEBRA_MAXIMA_M:
                marcos.append(item)
            else:
                fora.append({**item, "motivo": f"a parte mais perto fica a mais de {ZEBRA_MAXIMA_M:.0f} m da linha central"})

    # As placas: a peca sem numero ao lado de uma placa com numero (o mesmo lado, a ate 2 m em s) e o verso dela.
    com_numero = [m for m in marcos if m["tipo"] == "placa" and m.get("valor") is not None]
    for m in [m for m in marcos if m["tipo"] == "placa" and m.get("valor") is None]:
        dono = next((c for c in com_numero if c["lado"] == m["lado"] and abs(c["s"] - m["s"]) <= MESMA_ZEBRA_M), None)
        marcos.remove(m)
        fora.append({**m, "motivo": f"o verso da placa de {dono['valor']} em {dono['s']}" if dono else "placa sem numero"})
    # As zebras: duas pecas no mesmo lado com o comeco e o fim a ate 2 m sao a mesma zebra (duas camadas).
    zebras = sorted([m for m in marcos if m["tipo"] == "zebra"], key=lambda m: (m["s"], m["material"]))
    for a in zebras:
        for b in zebras:
            if a is b or a not in marcos or b not in marcos or a["lado"] != b["lado"]:
                continue
            if abs(a["s"] - b["s"]) <= MESMA_ZEBRA_M and abs(a["sFim"] - b["sFim"]) <= MESMA_ZEBRA_M:
                marcos.remove(b)
                fora.append({**b, "motivo": f"a mesma zebra de {a['s']} a {a['sFim']} ({a['material']}), outra camada"})
    marcos.sort(key=lambda m: (m["s"], m["tipo"]))
    for k, m in enumerate(marcos):
        m["id"] = f"M{k + 1:03d}"
    return {
        "formato": FORMATO,
        "pista": "vhe_interlagos",
        "geometry_id": getattr(track, "geometry_id", ""),
        "comprimentoM": round(L, 3),
        "arquivos": [{"arquivo": a, "sha256": sha256(pasta / a), "bytes": (pasta / a).stat().st_size} for a in ARQUIVOS],
        "regras": {"postoMaximoM": POSTO_MAXIMO_M, "zebraMaximaM": ZEBRA_MAXIMA_M, "juntarM": JUNTAR_M,
                   "mesmaPecaM": MESMA_ZEBRA_M, "colunas": list(VALORES_DAS_COLUNAS), "lado": "pelo vetor normal da geometria: positivo e a esquerda"},
        "marcos": marcos,
        "fora": fora,
    }


# ── o arquivo do app ─────────────────────────────────────────────────────

def caminho(raiz: Path, pista: str) -> Path:
    return Path(raiz) / "data" / "reference_models" / f"{pista}.marcos.json"


def encontrar(raizes: Sequence[Optional[Path]], pista: str) -> Optional[Dict[str, Any]]:
    """O arquivo dos marcos na pasta do repositorio, na de dados e na de recursos, nessa ordem."""
    for raiz in raizes:
        if not raiz:
            continue
        arquivo = caminho(Path(raiz), pista)
        if arquivo.exists():
            try:
                dados = json.loads(arquivo.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if dados.get("formato") == FORMATO:
                return dados
    return None


def nome_do_marco(m: Dict[str, Any], ponta: Optional[str] = None) -> str:
    """O nome falado do marco (ADR 0033, item 4)."""
    tipo = m["tipo"]
    if tipo == "placa":
        return f"placa de {m['valor']}"
    if tipo == "placa_drs":
        return "placa do DRS"
    if tipo == "passarela":
        return "passarela"
    if tipo == "portico":
        return "pórtico da largada"
    lado = "à direita" if m.get("lado") == "direita" else "à esquerda"
    if tipo == "posto":
        return f"posto de bandeira {lado}"
    if tipo == "zebra":
        return f"{'fim' if ponta == 'fim' else 'começo'} da zebra {lado}"
    return tipo


def pontos_de_referencia(marcos: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Os pontos que servem de marco: cada marco no seu `s`, e cada zebra duas vezes (o comeco e o fim)."""
    out = []
    for m in marcos:
        if m["tipo"] == "zebra":
            out.append({**m, "ponta": "comeco", "sMarco": float(m["s"]), "nome": nome_do_marco(m, "comeco")})
            out.append({**m, "ponta": "fim", "sMarco": float(m["sFim"]), "nome": nome_do_marco(m, "fim")})
        else:
            out.append({**m, "ponta": None, "sMarco": float(m["s"]), "nome": nome_do_marco(m)})
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Le os marcos (so leitura na pasta da pista) e grava `data/reference_models/<pista>.marcos.json`."""
    import argparse

    from core.radio.janelas import carregar_geometria

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pasta_da_pista")
    ap.add_argument("--repositorio", default=str(Path(__file__).resolve().parents[3]))
    a = ap.parse_args(argv)
    repo = Path(a.repositorio)
    track = carregar_geometria(repo)
    if track is None:
        raise SystemExit("sem a geometria oficial no repositorio")
    dados = ler_os_marcos(Path(a.pasta_da_pista), track)
    saida = caminho(repo, dados["pista"])
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    print(saida, len(dados["marcos"]), "marcos;", len(dados["fora"]), "fora")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
