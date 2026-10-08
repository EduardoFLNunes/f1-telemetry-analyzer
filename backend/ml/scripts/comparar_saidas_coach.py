"""Compara as saidas do `atualizar_coach` com uma referencia guardada (pedido 25).

    python -m ml.scripts.comparar_saidas_coach --guardar data/ml/_p25_referencia_completa
    python -m ml.scripts.comparar_saidas_coach --referencia data/ml/_p25_referencia_completa [--json ARQUIVO]

`--guardar` copia as saidas atuais para a pasta (a "referencia completa").
`--referencia` compara as saidas atuais com ela, pelo criterio do pedido 25:

* **tabelas** (parquet): mesmo esquema (colunas, ordem e tipos), mesmas linhas
  na mesma ordem e valores identicos, com NaN igual a NaN. A comparacao e
  coluna a coluna, para o store v2 nao precisar caber inteiro na memoria duas
  vezes;
* **JSONs**: mesmas chaves e mesmos valores. Ficam fora so os campos listados
  em `EXCLUDED`: data e hora, duracao, commit, caminho de backup e o campo novo
  `construcao` do meta.

Sai com 0 se tudo bate e 1 se algo difere, e diz o arquivo, a coluna (ou o
campo), quantas linhas diferem e um exemplo.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml import config  # noqa: E402

ROOT = config.repo_root()

# (rotulo na referencia, caminho na raiz do repositorio, tipo)
OUTPUTS: Tuple[Tuple[str, str, str], ...] = (
    ("origem/lap_inventory.parquet", "data/ml/origem/lap_inventory.parquet", "tabela"),
    ("origem/relogio_microsetores.parquet", "data/ml/origem/relogio_microsetores.parquet", "tabela"),
    ("origem/sinais_voltas.parquet", "data/ml/origem/sinais_voltas.parquet", "tabela"),
    ("origem/grade_voltas.parquet", "data/ml/origem/grade_voltas.parquet", "tabela"),
    ("origem/lap_inventory_summary.json", "data/ml/origem/lap_inventory_summary.json", "json"),
    ("origem/detector_aplicar.json", "data/ml/origem/detector_aplicar.json", "json"),
    ("origem/atualizar_coach.json", "data/ml/origem/atualizar_coach.json", "json"),
    ("laps_grid_v2.parquet", "data/ml/laps_grid_v2.parquet", "tabela"),
    ("laps_grid_v2_meta.json", "data/ml/laps_grid_v2_meta.json", "json"),
    ("store_v2_relatorio.json", "data/ml/store_v2_relatorio.json", "json"),
    ("reference_models/vhe_interlagos.json", "data/reference_models/vhe_interlagos.json", "json"),
)
# Os JSONs do relatorio de evolucao: todos os da pasta.
EVOLUTION_DIR = ("evolucao", "data/ml/evolucao")

# Campos fora da comparacao, por arquivo. Um caminho e uma sequencia de chaves
# separadas por ponto; `*` vale para qualquer chave ou posicao de lista.
# Levantados nos JSONs da referencia completa antes da primeira rodada. Ficam na
# comparacao as datas e duracoes que saem das gravacoes (`periodos_das_gravacoes`).
EXCLUDED: Dict[str, Tuple[str, ...]] = {
    "origem/atualizar_coach.json": ("backup",),                               # caminho do backup
    "laps_grid_v2_meta.json": ("construido_em", "commit", "construcao"),    # data, commit, campo novo
    "store_v2_relatorio.json": ("segundos", "meta.commit"),                  # duracao, commit
    "reference_models/vhe_interlagos.json": ("built_at",),                    # data do treino
}
EVOLUTION_EXCLUDED: Tuple[str, ...] = ("store.commit_do_store",)               # commit do store lido


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


def current_outputs() -> List[Tuple[str, Path, str]]:
    out = [(label, ROOT / relative, kind) for label, relative, kind in OUTPUTS]
    label, relative = EVOLUTION_DIR
    for path in sorted((ROOT / relative).glob("*.json")):
        out.append((f"{label}/{path.name}", path, "json"))
    return out


def excluded_for(label: str) -> Tuple[str, ...]:
    if label.startswith(EVOLUTION_DIR[0] + "/"):
        return EVOLUTION_EXCLUDED
    return EXCLUDED.get(label, ())


# ----------------------------------------------------------------- tabelas ---

def _values_equal(a: pd.Series, b: pd.Series) -> np.ndarray:
    """Igualdade elemento a elemento, com NaN igual a NaN e o tipo do valor conferido nos objetos."""
    if a.dtype.kind == "f" and b.dtype.kind == "f":
        x, y = a.to_numpy(), b.to_numpy()
        return (x == y) | (np.isnan(x) & np.isnan(y))
    if a.dtype == object or b.dtype == object:
        out = np.empty(len(a), dtype=bool)
        for i, (x, y) in enumerate(zip(a.tolist(), b.tolist())):
            x_nan = isinstance(x, float) and math.isnan(x)
            y_nan = isinstance(y, float) and math.isnan(y)
            if x_nan or y_nan:
                out[i] = x_nan and y_nan
            elif type(x) is not type(y):
                out[i] = False
            elif isinstance(x, np.ndarray):
                out[i] = bool(np.array_equal(x, y))
            else:
                out[i] = bool(x == y)
        return out
    na = a.isna().to_numpy() & b.isna().to_numpy()
    eq = (a.to_numpy() == b.to_numpy())
    return np.asarray(eq | na, dtype=bool)


def compare_tables(reference: Path, current: Path) -> Dict[str, Any]:
    if sha256(reference) == sha256(current):
        return {"igual": True, "bytes_iguais": True}
    ref_file, cur_file = pq.ParquetFile(reference), pq.ParquetFile(current)
    ref_schema, cur_schema = ref_file.schema_arrow, cur_file.schema_arrow
    problems: List[Dict[str, Any]] = []
    if ref_schema.names != cur_schema.names:
        problems.append({"coluna": None, "problema": "colunas diferentes",
                         "referencia": ref_schema.names, "atual": cur_schema.names})
        return {"igual": False, "bytes_iguais": False, "diferencas": problems}
    if ref_file.metadata.num_rows != cur_file.metadata.num_rows:
        problems.append({"coluna": None, "problema": "numero de linhas",
                         "referencia": ref_file.metadata.num_rows, "atual": cur_file.metadata.num_rows})
        return {"igual": False, "bytes_iguais": False, "diferencas": problems}
    for name in ref_schema.names:
        ref_type, cur_type = ref_schema.field(name).type, cur_schema.field(name).type
        if ref_type != cur_type:
            problems.append({"coluna": name, "problema": "tipo", "referencia": str(ref_type), "atual": str(cur_type)})
            continue
        a = ref_file.read(columns=[name]).column(name).to_pandas()
        b = cur_file.read(columns=[name]).column(name).to_pandas()
        if a.dtype != b.dtype:
            problems.append({"coluna": name, "problema": "tipo no pandas", "referencia": str(a.dtype),
                             "atual": str(b.dtype)})
            continue
        equal = _values_equal(a, b)
        if not equal.all():
            bad = np.flatnonzero(~equal)
            problems.append({"coluna": name, "problema": "valores", "linhas_diferentes": int(bad.size),
                             "exemplo": {"linha": int(bad[0]), "referencia": repr(a.iloc[bad[0]]),
                                         "atual": repr(b.iloc[bad[0]])}})
    if (ref_schema.metadata or {}) != (cur_schema.metadata or {}):
        problems.append({"coluna": None, "problema": "metadados do esquema (pandas)"})
    return {"igual": not problems, "bytes_iguais": False, "diferencas": problems}


# ------------------------------------------------------------------- JSONs ---

def _matches(path: Sequence[str], pattern: Sequence[str]) -> bool:
    return len(path) == len(pattern) and all(p == "*" or p == k for k, p in zip(path, pattern))


def _diff_json(a: Any, b: Any, path: List[str], excluded: List[List[str]], out: List[Dict[str, Any]]) -> None:
    if any(_matches(path, pattern) for pattern in excluded):
        return
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b), key=str):
            child = path + [str(key)]
            if any(_matches(child, pattern) for pattern in excluded):
                continue
            if key not in a or key not in b:
                out.append({"campo": ".".join(child), "problema": "chave so na " + ("atual" if key in b else "referencia")})
                continue
            _diff_json(a[key], b[key], child, excluded, out)
        return
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append({"campo": ".".join(path), "problema": "tamanho da lista", "referencia": len(a), "atual": len(b)})
            return
        for i, (x, y) in enumerate(zip(a, b)):
            _diff_json(x, y, path + [str(i)], excluded, out)
        return
    if type(a) is not type(b) or a != b:
        if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
            return
        out.append({"campo": ".".join(path), "problema": "valor", "referencia": a, "atual": b})


def compare_json(reference: Path, current: Path, excluded: Sequence[str]) -> Dict[str, Any]:
    a = json.loads(reference.read_text(encoding="utf-8"))
    b = json.loads(current.read_text(encoding="utf-8"))
    differences: List[Dict[str, Any]] = []
    _diff_json(a, b, [], [pattern.split(".") for pattern in excluded], differences)
    return {"igual": not differences, "campos_excluidos": list(excluded), "diferencas": differences[:20],
            "total_de_diferencas": len(differences)}


# ------------------------------------------------------------------- fluxo ---

def save_reference(target: Path) -> List[str]:
    target = Path(target)
    if target.exists():
        raise SystemExit(f"PARADO: {target} ja existe; a referencia nao e sobrescrita.")
    saved = []
    for label, path, _ in current_outputs():
        if not path.exists():
            raise SystemExit(f"PARADO: {path} nao existe.")
        destination = target / label
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        saved.append(label)
    return saved


def compare(reference: Path) -> Dict[str, Any]:
    reference = Path(reference)
    results: Dict[str, Any] = {}
    current = {label: (path, kind) for label, path, kind in current_outputs()}
    expected = {str(p.relative_to(reference)).replace("\\", "/") for p in reference.rglob("*") if p.is_file()}
    for label in sorted(set(current) | expected):
        if label not in current or not current[label][0].exists():
            results[label] = {"igual": False, "problema": "o arquivo atual nao existe"}
            continue
        if label not in expected:
            results[label] = {"igual": False, "problema": "o arquivo nao esta na referencia"}
            continue
        path, kind = current[label]
        if kind == "tabela":
            results[label] = {"tipo": "tabela", **compare_tables(reference / label, path)}
        else:
            results[label] = {"tipo": "json", **compare_json(reference / label, path, excluded_for(label))}
    return {"referencia": str(reference), "tudo_igual": all(r["igual"] for r in results.values()),
            "arquivos": results}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--guardar", type=Path, help="copia as saidas atuais para esta pasta")
    group.add_argument("--referencia", type=Path, help="compara as saidas atuais com esta pasta")
    parser.add_argument("--json", type=Path, default=None, help="grava o resultado da comparacao")
    args = parser.parse_args(argv)
    if args.guardar:
        saved = save_reference(args.guardar)
        print(f"{len(saved)} arquivos guardados em {args.guardar}")
        for label in saved:
            print(f"  {label}")
        return 0
    result = compare(args.referencia)
    for label, item in result["arquivos"].items():
        state = "igual" if item["igual"] else "DIFERENTE"
        extra = " (bytes iguais)" if item.get("bytes_iguais") else ""
        excluded = item.get("campos_excluidos")
        print(f"  [{state}] {label}{extra}" + (f"  excluidos: {', '.join(excluded)}" if excluded else ""))
        for difference in item.get("diferencas", [])[:5]:
            print(f"      {json.dumps(difference, ensure_ascii=False, default=str)[:300]}")
    print("tudo igual" if result["tudo_igual"] else "HA DIFERENCAS")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    return 0 if result["tudo_igual"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
