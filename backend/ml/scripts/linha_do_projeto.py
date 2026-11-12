"""A linha do projeto (pedido 50; ADR 0031).

    python -m ml.scripts.linha_do_projeto conferencia [--handoff PREFIXO]
    python -m ml.scripts.linha_do_projeto medidor     [--handoff PREFIXO]
    python -m ml.scripts.linha_do_projeto l1          [--handoff PREFIXO]
    python -m ml.scripts.linha_do_projeto l2          [--handoff PREFIXO]
    python -m ml.scripts.linha_do_projeto arquivos    [--handoff PREFIXO]

* `conferencia`: a codificacao nova (item 4), com a escada do espacamento e a
  conferencia do item 4.5 na linha da IA e na volta `#0013`, mais os limites das
  restricoes por trecho (item 4.4);
* `medidor`: os tres medidores (item 5), a calibracao com uma linha de fora de
  cada vez e a escolha pelo Spearman por microssetor;
* `l1`: a montagem por trecho (item 7);
* `l2`: a busca nova (item 7), a partir da L1;
* `arquivos`: os `fast_lane.ai` da L1 e da L2 em `data/pista_teste/linhas/`,
  com o sha256 e a figura (B.3 e B.4).

Tudo o que sai vai para `data/linha_do_projeto/` (fora do git). Nada aqui le a
pasta do jogo: o arquivo da linha da IA vem de `data/pista_teste/linhas/C0`,
conferido pelo `linhas.json` do pedido 47.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402

from ml import config  # noqa: E402
from ml.data.store_v2 import git_commit  # noqa: E402
from ml.optimization import codificacao_nova as CN  # noqa: E402
from ml.pista_teste import ai_spline as A  # noqa: E402
from ml.pista_teste import condicoes as C  # noqa: E402
from ml.pista_teste import linha_nova as N  # noqa: E402
from ml.pista_teste import por_trecho as PT  # noqa: E402
from ml.track.corners import detect_corners  # noqa: E402
from ml.track.geometry import load_corridor_geometry  # noqa: E402

PEDIDO = 50
CONTA_DO_49 = "docs/handoff/2026-11-11_49_modelo1-por-trecho_conta.json"


def raiz() -> Path:
    out = config.repo_root() / "data" / "linha_do_projeto"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _padrao(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return str(o)
    raise TypeError(type(o))


def _json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False, default=_padrao), encoding="utf-8")


def _ler_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _cabecalho(parte: str, comando: str, track) -> dict:
    return {"pedido": PEDIDO, "adr": "0031", "parte": parte, "commit": git_commit(), "comando": comando,
            "ambiente": {"python": platform.python_version(), "numpy": np.__version__, "plataforma": platform.platform()},
            "geometry_id": track.geometry_id, "corridor_id": track.corridor_id}


# ---------------------------------------------------------------- comum ---

class Base:
    """O que todas as etapas usam: a geometria, as curvas, os trechos e a linha da IA (so como adversaria)."""

    def __init__(self):
        self.track = load_corridor_geometry()
        self.corners = detect_corners(self.track)
        self.trechos = PT.trechos(self.corners, self.track.length)
        self.curvas = [(c.start_s, c.end_s) for c in self.corners]
        pasta = C.raiz_saida() / "linhas"
        manifesto = _ler_json(pasta / "linhas.json")
        arquivo = pasta / "C0" / "fast_lane.ai"
        sha = A.sha256_arquivo(arquivo)
        if sha != manifesto["condicoes"]["C0"]["sha256"] or sha != manifesto["original"]["sha256"]:
            raise SystemExit("PARADO: o arquivo C0 nao e a copia do original do linhas.json do pedido 47.")
        self.manifesto_47 = manifesto
        self.original = A.ler(arquivo)
        self.original_sha256 = sha
        self.xz_c0 = self.original.pos[:, [0, 2]].astype(float)
        self.estacao = np.mod(N.estacoes(self.original, self.track), self.track.length)
        self.lateral_c0 = C.lateral_da_linha(self.track, self.xz_c0)

    def codificacao(self, par=None) -> CN.CodificacaoNova:
        if par is None:
            par = tuple(_ler_json(raiz() / "conferencia.json")["escolhido"])
        return CN.construir(self.track, self.curvas, *par)

    def voltas_rotuladas(self):
        """As 150 voltas do pedido 44 com a lateral completa: (ordenadas pelo tempo, {id: lateral}, tabela)."""
        from ml.optimization.seed import lateral_by_lap
        from ml.scripts import retreino_lstm as RL

        src = RL.load_prepared(self.track)
        tabela = src.table[src.table["origem"].isin(["humano", "ia"])].sort_values("lap_time_s")
        todas = lateral_by_lap(src.store, tabela["lap_id"].tolist())
        laterais = {k: todas[k] for k in tabela["lap_id"] if k in todas and np.isfinite(todas[k]).all()}
        return laterais, tabela, src


# ---------------------------------------------------------- conferencia ---

def conferencia(args) -> int:
    t0 = time.time()
    b = Base()
    track = b.track
    laterais, tabela, _ = b.voltas_rotuladas()
    if C.VOLTA_IA not in laterais:
        raise SystemExit(f"PARADO: a volta {C.VOLTA_IA} nao tem a lateral completa.")
    raio_arquivo = b.original.campo("raio").astype(float)
    tentativas = []
    escolhido = None
    for par in CN.ESCADA:
        cod = CN.construir(track, b.curvas, *par)
        c0 = CN.conferir_c0(cod, b.xz_c0, b.estacao, raio_arquivo, b.trechos)
        v13 = CN.conferir_volta(cod, laterais[C.VOLTA_IA], b.trechos, C.VOLTA_IA)
        item = {"par_m": list(par), "codificacao": cod.descricao(),
                "c0": {k: v for k, v in c0.items() if k != "genes"}, "volta_0013": {k: v for k, v in v13.items() if k != "genes"},
                "passa": bool(c0["passa"] and v13["passa"])}
        tentativas.append(item)
        print(f"{par[0]:4.1f}/{par[1]:4.1f} m  genes {cod.genes:4d}  C0 p95 {c0['distancia_p95_m']:.3f} m raio {c0['maior_diferenca_relativa_do_raio']:+.3f}"
              f"  #0013 p95 {v13['distancia_p95_m']:.3f} m raio {v13['maior_diferenca_relativa_do_raio']:+.3f}  passa: {item['passa']}", flush=True)
        if item["passa"]:
            escolhido = par
            break
    limites = CN.limites_por_trecho(track, list(laterais.values()), b.trechos)
    payload = {**_cabecalho("B.1", "python -m ml.scripts.linha_do_projeto conferencia", track),
               "escada": [list(p) for p in CN.ESCADA], "tentativas": tentativas,
               "escolhido": list(escolhido) if escolhido else None,
               "janelas_das_curvas": CN.janelas_das_curvas(track.length, b.curvas),
               "arquivo_c0": {"sha256": b.original_sha256, "pontos": b.original.n},
               "restricoes": {"voltas": limites["voltas"], "emenda_fora_m": CN.EMENDA_DA_VOLTA_M,
                              "por_trecho": [{"trecho": t.nome, "inicio_s": t.inicio_s, "fim_s": t.fim_s,
                                              "menor_raio_das_voltas_m": float(limites["menor_raio_das_voltas_m"][i]),
                                              "raio_min_m": float(limites["raio_min_m"][i]),
                                              "maior_taxa_das_voltas": float(limites["maior_taxa_das_voltas"][i]),
                                              "taxa_max": float(limites["taxa_max"][i])} for i, t in enumerate(b.trechos)]},
               "tempo_s": round(time.time() - t0, 1)}
    _json(raiz() / "conferencia.json", payload)
    if args.handoff:
        _json(Path(str(args.handoff) + "_conferencia.json"), payload)
    if escolhido is None:
        print("PARADO: nenhum par da escada passou na conferencia (ADR 0031, item 4.6).")
        return 2
    print("escolhido:", escolhido)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("comando", choices=("conferencia", "medidor", "l1", "l2", "arquivos"))
    parser.add_argument("--handoff", help="prefixo dos arquivos de handoff")
    args = parser.parse_args(argv)
    if args.comando == "conferencia":
        return conferencia(args)
    from ml.scripts import linha_do_projeto_etapas as E
    return {"medidor": E.medidor, "l1": E.l1, "l2": E.l2, "arquivos": E.arquivos}[args.comando](args)


if __name__ == "__main__":
    raise SystemExit(main())
