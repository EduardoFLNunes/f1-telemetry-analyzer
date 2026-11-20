"""Os rotulos pela literatura do kit 2 (pedido 42, atualizacao de 20/11; secao 7 do documento do Modelo 2).

    python -m ml.scripts.modelo2_literatura e3            # o teste nas 7 saidas de traseira de 01/11
    python -m ml.scripts.modelo2_literatura rotular       # as 120 passagens do kit
    python -m ml.scripts.modelo2_literatura concordancia  # contra as quatro rodadas
    python -m ml.scripts.modelo2_literatura galeria       # a galeria da rodada 4

`e3` e `rotular` nao carregam o codigo dos detectores (conferido no fim de cada
um). As saidas ficam em `data/ml/modelo2/literatura/` e no CSV dos rotulos em
`data/ml/modelo2/rotulagem/`; com `--handoff`, uma copia vai para `docs/handoff/`.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import numpy as np  # noqa: E402

from ml.modelo2 import literatura_execucao as X  # noqa: E402
from ml.modelo2 import rotulos_literatura as RL  # noqa: E402
from ml.modelo2.dados import GEOMETRIA_39_FILE, carregar, raiz, sha256, voltas_da_rodada1  # noqa: E402
from ml.track.geometry import load_geometry  # noqa: E402

PREFIXO = "docs/handoff/2026-10-29_42_modelo2-rodada-2"
CSV_NOME = "2026-11-20_42_rotulos_literatura.csv"


def pasta() -> Path:
    p = raiz() / "literatura"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _write(path: Path, data) -> Path:
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    return path


def _fases():
    return json.loads((raiz() / "rodada4" / "fases.json").read_text(encoding="utf-8"))["curvas"]


def _detectores_carregados() -> bool:
    return "ml.modelo2.detectores" in sys.modules


def _base():
    track = load_geometry()
    L, k = RL.geometria_do_39(GEOMETRIA_39_FILE)
    data = carregar(track, so_ids=voltas_da_rodada1(), progress=lambda *_: None)   # sem saida: nada e gravado
    mine = [v for v in data.voltas.values() if v.origem != "ia"]
    ref = X.referencia(mine, L, k)
    return track, data, ref


def cmd_e3(handoff: bool) -> int:
    started = time.time()
    track, data, ref = _base()
    rows = X.e3_nas_saidas(track, _fases(), ref)
    c06 = [r for r in rows if r["curva"].startswith("C06")]
    out = {"referencia_do_carro": {"L": ref.L, "k_delta": ref.k_delta, "k_us_rad_por_g": ref.k_us,
                                   "intercepto_rad": ref.intercepto, "mu": ref.mu, "pontos": ref.pontos, **ref.extra},
           "passagens": rows, "aplica": sum(r["rotulo"] == RL.APLICA for r in rows), "total": len(rows),
           "as_duas_da_C06_aplicam": all(r["rotulo"] == RL.APLICA for r in c06) and len(c06) == 2,
           "detectores_carregados": _detectores_carregados(), "tempo_s": round(time.time() - started, 1)}
    path = _write(pasta() / "e3_saidas_de_0111.json", out)
    if handoff:
        shutil.copy(path, BACKEND.parent / f"{PREFIXO}_literatura_e3_saidas_de_0111.json")
    print(json.dumps(out, indent=1, ensure_ascii=False, default=float))
    if not out["as_duas_da_C06_aplicam"]:
        print("PARADO: o criterio do E3 nao pegou as duas passagens da C06 (secao 7.5, item 2).")
        return 3
    return 0


def cmd_rotular(handoff: bool) -> int:
    started = time.time()
    track, data, ref = _base()
    enderecos = X.enderecos_do_kit(raiz() / "rotulagem_gabarito.json")
    rows = X.rotular_o_kit(enderecos, data.voltas, track, _fases(), ref)
    csv_path = X.gravar_csv(rows, raiz() / "rotulagem" / CSV_NOME)
    resumo = {}
    for r in rows:
        d = resumo.setdefault(r["pergunta"], {RL.APLICA: 0, RL.NAO_APLICA: 0, RL.NAO_SEI: 0})
        d[r["rotulo"]] += 1
    out = {"csv": str(csv_path), "sha256": sha256(csv_path), "por_pergunta": resumo,
           "referencia_do_carro": {"L": ref.L, "k_delta": ref.k_delta, "k_us_rad_por_g": ref.k_us,
                                   "intercepto_rad": ref.intercepto, "mu": ref.mu, "pontos": ref.pontos},
           "detectores_carregados": _detectores_carregados(), "tempo_s": round(time.time() - started, 1)}
    _write(pasta() / "rotulos_resumo.json", out)
    if handoff:
        shutil.copy(csv_path, BACKEND.parent / f"{PREFIXO}_{CSV_NOME}")
        _write(BACKEND.parent / f"{PREFIXO}_literatura_rotulos_resumo.json", out)
    print(json.dumps(out, indent=1, ensure_ascii=False, default=float))
    return 0


def cmd_concordancia(handoff: bool) -> int:
    from ml.modelo2.comparacao import concordancia_literatura
    out = concordancia_literatura(raiz() / "rotulagem" / CSV_NOME, raiz())
    _write(pasta() / "concordancia.json", out)
    if handoff:
        _write(BACKEND.parent / f"{PREFIXO}_literatura_concordancia.json", out)
    print(json.dumps(out["resumo"], indent=1, ensure_ascii=False, default=float))
    return 0


def cmd_galeria(handoff: bool) -> int:
    from ml.modelo2.galeria import gerar_galeria
    path = gerar_galeria(pasta() / "galeria_rodada4.html")
    if handoff:
        shutil.copy(path, BACKEND.parent / f"{PREFIXO}_galeria_rodada4.html")
    print(path)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("comando", choices=["e3", "rotular", "concordancia", "galeria"])
    parser.add_argument("--handoff", action="store_true")
    args = parser.parse_args(argv)
    return {"e3": cmd_e3, "rotular": cmd_rotular, "concordancia": cmd_concordancia, "galeria": cmd_galeria}[args.comando](args.handoff)


if __name__ == "__main__":
    raise SystemExit(main())
