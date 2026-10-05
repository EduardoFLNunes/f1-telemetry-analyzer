"""Inventario dos canais fisicos nas gravacoes (pedido 18, Parte B; ADR 0017, M0).

    python -m ml.scripts.inventario_canais [--sessoes 2026-10-04 2026-10-05] [--saida ARQUIVO]

Para cada campo da lista do pedido 18 (pneus, freios, movimento, suspensao,
comandos), nas gravacoes das sessoes dadas e separado por app (o de
desenvolvimento grava em `data/recordings`; o instalado, em `%APPDATA%`):
se existe na amostra gravada, a fracao de amostras preenchidas, a faixa
(p1, p50, p99) e a unidade provavel. As sessoes seguem a regra da emenda de
05/10 (`evolution.group_sessions`), sobre o inventario rotulado.

Um campo que o adaptador le da memoria compartilhada mas nao grava aparece
como `gravado: false`, com a nota de onde ele esta na estrutura.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ml import config  # noqa: E402
from ml.comparison.evolution import group_sessions  # noqa: E402
from ml.data.origin import recording_folder  # noqa: E402
from ml.data.recordings import list_all_sessions  # noqa: E402
from ml.data.store_v2 import default_inventory_path, recording_periods  # noqa: E402

# (grupo, campo, caminho na amostra gravada ou None, unidade provavel, nota)
FIELDS = (
    ("pneus", "tyreCoreTemperature", "carPhysics.tyres.tyreCoreTemperature", "°C", ""),
    ("pneus", "tyreTempI", None, "°C", "temperatura interna; lida pelo adaptador, nao gravada"),
    ("pneus", "tyreTempM", None, "°C", "temperatura central; lida pelo adaptador, nao gravada"),
    ("pneus", "tyreTempO", None, "°C", "temperatura externa; lida pelo adaptador, nao gravada"),
    ("pneus", "tyrePressure", "carPhysics.tyres.tyrePressure", "psi", "wheelsPressure na memoria"),
    ("pneus", "tyreWear", "carPhysics.tyres.tyreWear", "% (100 = novo)", ""),
    ("pneus", "wheelSlip", "carPhysics.tyres.wheelSlip", "adimensional (escorregamento do jogo)", ""),
    ("pneus", "wheelLoad", "carPhysics.tyres.wheelLoad", "N", ""),
    ("freios", "brakeTemp", None, "°C",
     "existe na memoria; o adaptador le no deslocamento errado (le brakeBias e localVelocity) e nao grava"),
    ("freios", "brakeBias", None, "fracao na dianteira",
     "existe na memoria; o adaptador nao declara no lugar certo e nao grava"),
    ("movimento", "localVelocity", None, "m/s (x lateral, y vertical, z longitudinal)",
     "existe na memoria; o adaptador nao declara no lugar certo e nao grava"),
    ("movimento", "velocity", "carPhysics.motion.velocity", "m/s, eixos do mundo", "nao e a velocidade local do carro"),
    ("movimento", "localAngularVel", None, "rad/s (y = guinada)", "lida pelo adaptador, nao gravada"),
    ("movimento", "accG", "carPhysics.motion.accG", "g", ""),
    ("movimento", "heading", "heading", "rad", ""),
    ("suspensao", "suspensionTravel", "carPhysics.suspension.suspensionTravel", "m", ""),
    ("suspensao", "rideHeight", "carPhysics.suspension.rideHeight", "m (dianteira, traseira)", ""),
    ("comandos", "steerAngle", "carPhysics.controls.steerAngle", "sem unidade documentada (ver o relatorio do volante)", ""),
    ("comandos", "throttle", "carPhysics.controls.throttle", "0 a 1", ""),
    ("comandos", "brake", "carPhysics.controls.brake", "0 a 1", ""),
    ("comandos", "clutch", "carPhysics.controls.clutch", "0 a 1",
     "o adaptador le alem do fim da estrutura do AC1: o valor gravado e sempre 0"),
    ("comandos", "gear", "carPhysics.controls.gear", "marcha (jogo: 0 = re, 1 = neutro)", ""),
)


def _get(sample: Dict, path: str):
    value = sample
    for key in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _flatten(value) -> List[Optional[float]]:
    if isinstance(value, dict):
        return [_number(v) for v in value.values()]
    if isinstance(value, (list, tuple)):
        return [_number(v) for v in value]
    return [_number(value)]


def _number(value) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return float(value) if isinstance(value, bool) else None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def scan_recording(path: Path, step: int = 1) -> Dict[str, Dict[str, object]]:
    """Le um player.jsonl e junta, por campo gravado, os valores e quantas amostras tinham o campo."""
    values: Dict[str, List[List[Optional[float]]]] = {f: [] for _, f, p, _, _ in FIELDS if p}
    present: Dict[str, int] = {f: 0 for f in values}
    total = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for index, line in enumerate(handle):
            if index % step:
                continue
            try:
                sample = json.loads(line).get("sample") or {}
            except json.JSONDecodeError:
                continue
            total += 1
            for _, name, field_path, _, _ in FIELDS:
                if not field_path:
                    continue
                raw = _get(sample, field_path)
                if raw is None:
                    continue
                present[name] += 1
                values[name].append(_flatten(raw))
    return {"amostras": total, "presentes": present, "valores": values}


def summarize(scans: List[Dict[str, object]]) -> Dict[str, object]:
    total = sum(s["amostras"] for s in scans)
    out: Dict[str, object] = {"amostras": total, "campos": {}}
    for group, name, field_path, unit, note in FIELDS:
        entry: Dict[str, object] = {"grupo": group, "unidade_provavel": unit, "nota": note or None,
                                    "gravado": bool(field_path), "caminho": field_path}
        if field_path:
            rows = [row for s in scans for row in s["valores"][name]]
            present = sum(s["presentes"][name] for s in scans)
            width = max((len(r) for r in rows), default=0)
            matrix = np.array([r + [None] * (width - len(r)) for r in rows], dtype=float) if rows else np.empty((0, 0))
            filled = np.isfinite(matrix).all(axis=1) if matrix.size else np.array([], dtype=bool)
            entry["existe"] = present > 0
            entry["componentes"] = width
            entry["fracao_preenchida"] = round(float(filled.sum()) / total, 4) if total else 0.0
            finite = matrix[np.isfinite(matrix)] if matrix.size else np.array([])
            if finite.size:
                entry["faixa"] = {"p1": round(float(np.percentile(finite, 1)), 4),
                                  "p50": round(float(np.percentile(finite, 50)), 4),
                                  "p99": round(float(np.percentile(finite, 99)), 4)}
                entry["constante"] = bool(np.nanmin(finite) == np.nanmax(finite))
                if width > 1:
                    entry["p50_por_componente"] = [round(float(np.nanmedian(matrix[:, k])), 4) for k in range(width)]
        else:
            entry["existe"] = False
        out["campos"][name] = entry
    return out


def session_recordings(sessions: List[str]) -> Dict[str, List[str]]:
    inventory = pd.read_parquet(default_inventory_path())
    october = sorted(i for i in inventory["session_id"].unique() if str(i) >= "2026-10-01")
    mapping = group_sessions(recording_periods(inventory, october))
    return {key: sorted(r for r, k in mapping.items() if k == key) for key in sessions}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sessoes", nargs="*", default=["2026-10-04", "2026-10-05"])
    parser.add_argument("--saida", type=Path, default=config.artifacts_root() / "canais" / "inventario_canais.json")
    args = parser.parse_args(argv)
    available = {s.session_id: s for s in list_all_sessions()}
    out: Dict[str, object] = {"sessoes": {}}
    for key, recordings in session_recordings(args.sessoes).items():
        by_app: Dict[str, List[str]] = {}
        for rid in recordings:
            by_app.setdefault(recording_folder(available[rid].directory), []).append(rid)
        out["sessoes"][key] = {}
        for app, rids in sorted(by_app.items()):
            scans = [scan_recording(available[rid].player_stream) for rid in rids]
            summary = summarize(scans)
            summary["gravacoes"] = rids
            out["sessoes"][key][app] = summary
            print(f"{key} / {app}: {len(rids)} gravacoes, {summary['amostras']} amostras")
            for name, entry in summary["campos"].items():
                if entry["existe"]:
                    print(f"   {name:20s} {entry['fracao_preenchida']:.3f}  {entry.get('faixa')}  {entry['unidade_provavel']}"
                          f"{'  CONSTANTE' if entry.get('constante') else ''}")
                else:
                    print(f"   {name:20s} nao gravado: {entry['nota']}")
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"-> {args.saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
