"""A geometria oficial (ADR 0002), exportada para o app ler sem importar `ml`.

O coach passa a medir a volta na mesma regua da analise (ADR 0013): `s` e `d`
calculados a partir da posicao no mundo, na grade de `load_geometry`, com os 60
microsetores de mesma distancia do `ml`. O backend empacotado nao importa este
pacote (nem SciPy de reconstrucao, nem PyTorch), entao a geometria sai daqui
como JSON puro -- o mesmo padrao do tracado exportado em `coaching.py`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import numpy as np

from ..track.geometry import TrackGeometry
from ..track.microsectors import Microsectors

FORMAT_VERSION = "official-geometry-1"


def official_geometry(track: TrackGeometry, sectors: Microsectors, track_name: str) -> Dict[str, Any]:
    """Grade (x, z, s), normais, fronteiras dos microsetores e identidade."""
    return {
        "version": FORMAT_VERSION,
        "track": track_name,
        "geometry_id": track.geometry_id,
        "source_hash": track.source_hash,
        "track_length": float(track.length),
        "step": float(track.step),
        # Normal para a ESQUERDA, como no `ml` (ADR 0003).
        "normal_side": "left",
        "x": np.round(track.x, 4).tolist(),
        "z": np.round(track.z, 4).tolist(),
        "s": np.round(track.s, 4).tolist(),
        "normal_x": np.round(track.normal[:, 0], 6).tolist(),
        "normal_z": np.round(track.normal[:, 1], 6).tolist(),
        "microsector_edges": np.round(sectors.edges_s, 4).tolist(),
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def save(payload: Dict[str, Any], path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return path
