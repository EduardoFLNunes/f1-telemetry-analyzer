"""Checagens da M0 no store v2 (pedido 18, Parte C; docs/modelo_fisico_m0.md, secao 1.2).

    python -m ml.scripts.checar_canais_fisicos --base DIR [--saida ARQUIVO]

`--base` e a pasta com a copia do store v2 do inicio da etapa
(`laps_grid_v2.parquet` e o meta). Confere:

* **nada do que ja existe muda** -- as mesmas voltas, o mesmo `lap_time_s` e as
  colunas antigas identicas valor a valor (NaN igual a NaN);
* **canais novos preenchidos** -- na sessao `2026-10-04`, cada canal novo cujo
  campo existe na gravacao tem pelo menos 95% dos pontos da grade
  preenchidos; a sessao `2026-10-05` (app instalado) e relatada a parte;
* **store integro** -- o meta do store novo traz as checagens do pedido 16
  aprovadas.

Sai com codigo 2 se alguma coluna antiga mudou.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ml import config  # noqa: E402
from ml.comparison.evolution import group_sessions  # noqa: E402
from ml.data.lap_store import StoredLaps  # noqa: E402
from ml.data.store_v2 import PHYSICAL_COLUMNS, load_store_v2, store_v2_meta  # noqa: E402

FILL_LIMIT = 0.95
CHECKED_SESSION = "2026-10-04"
SEPARATE_SESSION = "2026-10-05"


def unchanged(new: StoredLaps, base: StoredLaps) -> Dict[str, object]:
    """As voltas, os tempos e as colunas do store base, iguais no novo."""
    base_ids, new_ids = set(base.lap_ids), set(new.lap_ids)
    times_base = base.laps.set_index("lap_id")["lap_time_s"]
    times_new = new.laps.set_index("lap_id")["lap_time_s"]
    common = sorted(base_ids & new_ids)
    time_diff = [i for i in common if float(times_base[i]) != float(times_new[i])]
    old_columns = [c for c in base.frame.columns if c not in ("lap_id", "grid_index")]
    a = base.frame.sort_values(["lap_id", "grid_index"]).reset_index(drop=True)
    b = new.frame[new.frame["lap_id"].isin(base_ids)].sort_values(["lap_id", "grid_index"]).reset_index(drop=True)
    changed: List[str] = []
    missing = [c for c in old_columns if c not in b.columns]
    if len(a) != len(b) or not (a["lap_id"].to_numpy() == b["lap_id"].to_numpy()).all():
        changed.append("(linhas da grade)")
    else:
        for column in old_columns:
            if column in missing:
                continue
            if not np.array_equal(a[column].to_numpy(dtype=float), b[column].to_numpy(dtype=float), equal_nan=True):
                changed.append(column)
    return {
        "checagem": "nada do que ja existe muda",
        "voltas_base": len(base_ids), "voltas_novo": len(new_ids),
        "so_na_base": sorted(base_ids - new_ids), "so_no_novo": sorted(new_ids - base_ids),
        "lap_time_s_diferente": time_diff,
        "colunas_antigas": old_columns,
        "colunas_ausentes": missing,
        "colunas_mudadas": changed,
        "passou": base_ids == new_ids and not time_diff and not changed and not missing,
    }


def fill(store: StoredLaps, lap_ids: List[str]) -> Dict[str, object]:
    """Preenchimento de cada canal novo nas voltas dadas, e se o campo existe na gravacao."""
    frame = store.frame[store.frame["lap_id"].isin(lap_ids)]
    out = {}
    for column in PHYSICAL_COLUMNS:
        values = frame[column].to_numpy(dtype=float) if column in frame else np.array([])
        finite = np.isfinite(values)
        out[column] = {
            "existe_na_gravacao": bool(finite.any()),
            "preenchimento": round(float(finite.mean()), 4) if values.size else 0.0,
        }
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--saida", type=Path, default=config.artifacts_root() / "canais" / "checagens_store_m0.json")
    args = parser.parse_args(argv)

    new = load_store_v2()
    base = load_store_v2(args.base)
    meta = store_v2_meta()
    sessions = group_sessions({sid: p for sid, p in (meta.get("periodos_das_gravacoes") or {}).items()})
    laps = new.laps.assign(sessao=new.laps["session_id"].map(sessions))
    by_session = {key: laps.loc[laps["sessao"] == key, "lap_id"].tolist() for key in (CHECKED_SESSION, SEPARATE_SESSION)}

    result: Dict[str, object] = {"esquema": meta.get("esquema"), "nada_muda": unchanged(new, base)}
    checked = fill(new, by_session[CHECKED_SESSION])
    existing = {c: v for c, v in checked.items() if v["existe_na_gravacao"]}
    result["preenchimento"] = {
        "checagem": f"canais novos com pelo menos {FILL_LIMIT:.0%} preenchidos na sessao {CHECKED_SESSION}",
        "voltas": len(by_session[CHECKED_SESSION]),
        "canais": checked,
        "abaixo_do_limite": [c for c, v in existing.items() if v["preenchimento"] < FILL_LIMIT],
        "passou": bool(existing) and all(v["preenchimento"] >= FILL_LIMIT for v in existing.values()),
    }
    result[f"sessao_{SEPARATE_SESSION}_a_parte"] = {"voltas": len(by_session[SEPARATE_SESSION]),
                                                    "canais": fill(new, by_session[SEPARATE_SESSION])}
    result["store_integro"] = {"checagem": "checagens do pedido 16", "aprovado": bool(meta.get("aprovado")),
                               "passou": bool(meta.get("aprovado"))}
    result["canais_por_volta"] = {"voltas_com_algum_canal_novo": sum(1 for v in (meta.get("canais_por_volta") or {}).values() if v)}
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")

    for key in ("nada_muda", "preenchimento", "store_integro"):
        print(f"[{'ok' if result[key]['passou'] else 'FALHOU'}] {result[key]['checagem']}")
    if result["nada_muda"]["colunas_mudadas"] or result["nada_muda"]["colunas_ausentes"]:
        print(f"   colunas mudadas: {result['nada_muda']['colunas_mudadas']}  ausentes: {result['nada_muda']['colunas_ausentes']}")
    for column, value in checked.items():
        print(f"   {CHECKED_SESSION} {column:20s} existe={value['existe_na_gravacao']}  {value['preenchimento']:.3f}")
    print(f"-> {args.saida}")
    if not result["nada_muda"]["passou"]:
        print("PARADO: uma coluna antiga mudou (ou as voltas mudaram).")
        return 2
    return 0 if all(result[k]["passou"] for k in ("preenchimento", "store_integro")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
