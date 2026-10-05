"""A unidade do volante gravado (pedido 18, Parte B3; ADR 0017, M0).

    python -m ml.scripts.relatorio_volante [--saida ARQUIVO]

O `steerAngle` gravado nao tem unidade documentada. Relata, do store v2:

* a faixa observada nas voltas do piloto e nas da IA, por sessao e app;
* uma estimativa empirica: abaixo de 80 km/h, nas curvas mais fechadas (raio
  minimo abaixo de 30 m), a razao entre o volante e a curvatura da trajetoria,
  `|volante| / |kappa|`, com `kappa = a_lat / v^2` (aceleracao lateral medida e
  velocidade). So pontos com |a_lat| >= 0,3 g, e com o volante e a curvatura
  na relacao de sinal que domina (medido: volante positivo com a_lat
  negativa, ou seja, convencoes de sinal opostas).

Se o volante fosse o angulo das rodas em radianos, a razao ficaria perto do
entre-eixos do carro (2,5 a 3 m num formula). Se fosse o angulo do volante em
radianos, perto do entre-eixos vezes a relacao de direcao (dezenas). Se fosse
uma fracao do curso do volante, mudaria com o ajuste de rotacao do volante.
Nada e adotado aqui.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402

from ml import config  # noqa: E402
from ml.comparison.evolution import group_sessions  # noqa: E402
from ml.comparison.lap_vs_reference import _window  # noqa: E402
from ml.data.store_v2 import load_store_v2, store_v2_meta  # noqa: E402
from ml.track.corners import detect_corners  # noqa: E402
from ml.track.geometry import load_geometry  # noqa: E402

G = 9.80665
MAX_SPEED_KMH = 80.0
MIN_LATERAL_G = 0.3
TIGHT_RADIUS_M = 30.0


def _stats(values: np.ndarray, digits: int = 4) -> Dict[str, float]:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return {"n": 0}
    p1, p25, p50, p75, p99 = np.percentile(values, [1, 25, 50, 75, 99])
    return {"n": int(values.size), "p1": round(float(p1), digits), "p25": round(float(p25), digits),
            "p50": round(float(p50), digits), "p75": round(float(p75), digits), "p99": round(float(p99), digits),
            "max_abs": round(float(np.max(np.abs(values))), digits)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--saida", type=Path, default=config.artifacts_root() / "canais" / "relatorio_volante.json")
    args = parser.parse_args(argv)
    track = load_geometry()
    store = load_store_v2(track=track)
    meta = store_v2_meta()
    sessions = group_sessions(meta.get("periodos_das_gravacoes") or {})
    laps = store.laps.assign(sessao=store.laps["session_id"].map(sessions))
    corners = [c for c in detect_corners(track) if c.min_radius_m < TIGHT_RADIUS_M]
    inside = np.zeros(track.size, dtype=bool)
    for corner in corners:
        inside[_window(track, corner.start_s, corner.end_s)] = True
    column = "steer_angle" if "steer_angle" in store.frame.columns else "steering"

    groups: Dict[str, List[str]] = {}
    for _, row in laps.iterrows():
        if row["sessao"] in ("2026-10-04", "2026-10-05") and row["origem"] in ("humano", "ia"):
            groups.setdefault(f"{row['sessao']} / {row['origem']} / {row['pasta']}", []).append(row["lap_id"])

    out: Dict[str, object] = {"coluna": column, "curvas_fechadas": [c.label for c in corners],
                              "limites": {"velocidade_max_kmh": MAX_SPEED_KMH, "a_lat_min_g": MIN_LATERAL_G,
                                          "raio_minimo_abaixo_de_m": TIGHT_RADIUS_M},
                              "grupos": {}}
    for name, lap_ids in sorted(groups.items()):
        steer_all, ratios, per_lap = [], [], []
        for lap_id in lap_ids:
            grid = store.lap(lap_id)
            steer = grid[column].to_numpy(dtype=float)
            speed = grid["speed_kmh"].to_numpy(dtype=float) / 3.6
            lat_g = grid["lateral_g"].to_numpy(dtype=float)
            steer_all.append(steer)
            with np.errstate(divide="ignore", invalid="ignore"):
                kappa = lat_g * G / speed ** 2
            use = (inside & (speed * 3.6 < MAX_SPEED_KMH) & (np.abs(lat_g) >= MIN_LATERAL_G)
                   & np.isfinite(steer) & np.isfinite(kappa) & (np.abs(steer) > 1e-4))
            opposite = np.sign(steer) == -np.sign(kappa)
            same_side = opposite if (use & opposite).sum() >= (use & ~opposite).sum() else ~opposite
            r = np.abs(steer[use & same_side]) / np.abs(kappa[use & same_side])
            ratios.append(r)
            if r.size:
                per_lap.append(float(np.median(r)))
            out.setdefault("_sinais", {}).setdefault(name, []).append(
                {"volta": lap_id, "pontos": int(use.sum()), "sinais_opostos": int((use & opposite).sum())})
        steer_values = np.concatenate(steer_all) if steer_all else np.array([])
        ratio_values = np.concatenate(ratios) if ratios else np.array([])
        out["grupos"][name] = {
            "voltas": len(lap_ids),
            "faixa_do_volante": _stats(steer_values),
            "razao_volante_curvatura_m": _stats(ratio_values, 3),
            "mediana_por_volta_m": _stats(np.array(per_lap), 3),
        }
    signs = out.pop("_sinais", {})
    out["pontos_por_grupo"] = {k: {"pontos": sum(v["pontos"] for v in rows),
                                   "sinais_opostos": sum(v["sinais_opostos"] for v in rows)}
                               for k, rows in signs.items()}
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for name, group in out["grupos"].items():
        f, r = group["faixa_do_volante"], group["razao_volante_curvatura_m"]
        print(f"{name}: {group['voltas']} voltas | volante p1 {f.get('p1')} p50 {f.get('p50')} p99 {f.get('p99')} "
              f"max {f.get('max_abs')} | razao p25 {r.get('p25')} p50 {r.get('p50')} p75 {r.get('p75')} (n {r.get('n')})")
    print(f"pontos: {out['pontos_por_grupo']}")
    print(f"-> {args.saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
