"""Constroi o store v2 e roda as checagens registradas (pedido 16).

    python -m ml.scripts.build_lap_store_v2 [--inventario data/ml/origem/lap_inventory.parquet]
        [--relatorio ARQUIVO]

Le o inventario rotulado (o do `atualizar_coach`), materializa as voltas
validas e unicas sem box na grade, com o relogio zerado na linha pelo periodo
verdadeiro, e grava `data/ml/laps_grid_v2.parquet` e o meta. O store antigo
(`laps_grid.parquet`) nao e tocado.

As checagens (`ml.data.store_checks`) vao para o meta e para o relatorio. Se
alguma falhar, o meta fica com `aprovado: false` -- o relatorio de evolucao
recusa ler um store assim -- e o comando sai com codigo 2.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402

from ml import config  # noqa: E402
from ml.data import store_checks  # noqa: E402
from ml.data.lap_store import load_store, store_path  # noqa: E402
from ml.data.recordings import list_all_sessions  # noqa: E402
from ml.data.store_v2 import (  # noqa: E402
    STORE_V2_FILENAME,
    build_store_v2,
    default_inventory_path,
    file_entry,
    git_commit,
    save_store_v2,
)
from ml.track.geometry import load_geometry  # noqa: E402
from ml.track.microsectors import build_microsectors  # noqa: E402


def lap_labels_path() -> Path:
    return config.repo_root() / "docs" / "experimentos" / "2026-10-04_rotulos_por_volta.csv"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--inventario", type=Path, default=default_inventory_path())
    parser.add_argument("--relatorio", type=Path, default=config.artifacts_root() / "store_v2_relatorio.json")
    args = parser.parse_args(argv)

    started = time.time()
    if not args.inventario.exists():
        print(f"PARADO: inventario nao encontrado em {args.inventario}. Rode tools/atualizar_coach.py.")
        return 2
    inventory = pd.read_parquet(args.inventario)
    missing = {"origem", "equipamento", "duplicada_de", "pasta", "relogio_suspeito"} - set(inventory.columns)
    if missing:
        print(f"PARADO: o inventario nao tem {sorted(missing)}.")
        return 2
    track = load_geometry()
    sectors = build_microsectors(track)
    sessions = list_all_sessions()
    store, details = build_store_v2(inventory, track=track, sessions=sessions,
                                    progress=lambda text: print(text, flush=True), sectors=sectors)

    old = None
    if store_path().exists():
        old = load_store()
    result = store_checks.run_checks(store, track, sectors, old=old)
    result["contagens"] = store_checks.counts_by(store.laps)
    result["selecao"] = {
        **details.selection,
        "box_tiradas": len(details.box_removed),
        "voltas_com_box_tiradas": details.box_removed,
        "nao_encontradas": details.not_found,
        "no_store_v2": int(len(store.laps)),
    }

    by_id = {s.session_id: s for s in sessions}
    used = sorted(store.laps["session_id"].unique())
    inputs = {
        "inventario": file_entry(args.inventario),
        "rotulos_04_10": file_entry(lap_labels_path()) if lap_labels_path().exists() else None,
        "gravacoes": {sid: file_entry(by_id[sid].player_stream) for sid in used if sid in by_id},
    }
    extra = {
        "versao": 2,
        "construido_em": pd.Timestamp.now(tz="UTC").isoformat(),
        "commit": git_commit(),
        "entradas": inputs,
        "aprovado": bool(result["todas_passaram"]),
        "checagens": result["checagens"],
    }
    path = save_store_v2(store, extra)
    result["store"] = {"arquivo": str(path), **file_entry(path)}
    result["meta"] = {"commit": extra["commit"], "geometry_id": store.geometry_id, "source_hash": store.source_hash,
                      "aprovado": extra["aprovado"], "entradas": {"inventario": inputs["inventario"],
                                                                   "rotulos_04_10": inputs["rotulos_04_10"],
                                                                   "gravacoes": len(inputs["gravacoes"])}}
    result["segundos"] = round(time.time() - started, 1)
    args.relatorio.parent.mkdir(parents=True, exist_ok=True)
    args.relatorio.write_text(json.dumps(result, indent=1, ensure_ascii=False, default=str), encoding="utf-8")

    checks = result["checagens"]
    print(f"\nstore v2 -> {path}  ({result['segundos']:.0f} s)")
    print(f"voltas: {len(store.laps)}  {result['contagens']['por_origem']}  {result['contagens']['por_equipamento']}"
          f"  {result['contagens']['por_pasta']}")
    print(f"selecao: {json.dumps({k: v for k, v in result['selecao'].items() if not isinstance(v, list)})}")
    for name, check in checks.items():
        print(f"  [{'ok' if check['passou'] else 'FALHOU'}] {check['checagem']}")
    period = checks["principal_periodo"]
    print(f"     periodo - jogo (ms): {period['diferenca_ms']}  sem fechamento medido: "
          f"{period['voltas_sem_fechamento_medido']}")
    if "efeitos_esperados" in result:
        effects = result["efeitos_esperados"]
        print(f"  efeitos: volta {effects['volta_v2_menos_antigo_ms'].get('mediana')} ms, microsetor 0 "
              f"{effects['microsetor_0_v2_menos_antigo_ms'].get('mediana')} ms, outros p99 "
              f"{effects['outros_microsetores_abs_ms'].get('p99')} ms ({effects['voltas_nos_dois_stores']} voltas)")
        print(f"  controle (store antigo contra o jogo): {result['controle_store_antigo']['diferenca_ms']}")
    print(f"-> {args.relatorio}")
    if not result["principal_passou"]:
        print("PARADO: a checagem principal falhou. O store v2 ficou gravado com aprovado: false.")
        return 2
    if not result["todas_passaram"]:
        print("PARADO: uma checagem falhou. O store v2 ficou gravado com aprovado: false.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
