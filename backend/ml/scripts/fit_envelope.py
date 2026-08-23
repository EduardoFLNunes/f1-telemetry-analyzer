"""Ajusta o envelope dinamico do carro e mede o erro do simulador.

    python -m ml.scripts.fit_envelope

O numero que importa no fim nao e o erro medio de tempo de volta -- e a
correlacao entre o tempo simulado e o medido nas mesmas trajetorias. E ela que
diz se o simulador ordena trajetorias como a pista ordena, que e a unica coisa
que o algoritmo evolutivo lhe pergunta.
"""

from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from ml.data.lap_store import load_store
from ml.optimization.fitness import fit_shape_reference, shape_metrics
from ml.optimization.lap_time_model import calibration_error
from ml.optimization.vehicle_model import fit_envelope, save_envelope
from ml.preprocessing.splits import split_by_session
from ml.track.geometry import load_geometry


def main() -> int:
    started = time.time()
    track = load_geometry()
    store = load_store()
    split = split_by_session(store.laps)

    train_ids = set(split.train)
    training_rows = store.frame[store.frame["lap_id"].isin(train_ids)]
    print(f"ajustando envelope em {len(train_ids)} voltas de treino ({len(training_rows)} pontos)")

    envelope = fit_envelope(training_rows, source_laps=len(train_ids))
    path = save_envelope(envelope)
    print(f"\nenvelope -> {path}")
    print(envelope.describe().to_string(index=False))
    print(f"velocidade maxima observada: {envelope.top_speed_mps * 3.6:.1f} km/h")

    laterals = store.matrix("lateral")
    measured = store.laps.set_index("lap_id").loc[store.lap_ids, "lap_time_s"].to_numpy()
    print("\nsimulando as 125 voltas reais...", flush=True)
    error = calibration_error(track, envelope, laterals, measured)
    print(json.dumps(error, indent=2))

    reference = fit_shape_reference(track, laterals)
    metrics = shape_metrics(track, laterals)
    print("\nforma das voltas reais (limiares de penalizacao):")
    print(f"  serpenteio |dL/ds| medio: p50={np.median(metrics['weaving']):.4f} "
          f"p95={reference.weaving:.4f}")
    print(f"  variacao de curvatura   : p50={np.median(metrics['curvature_jerk']):.6f} "
          f"p95={reference.curvature_jerk:.6f}")

    output = path.parent / "shape_reference.json"
    output.write_text(json.dumps(reference.to_dict(), indent=2), encoding="utf-8")
    print(f"\nlimiares -> {output}")
    print(f"concluido em {time.time() - started:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
