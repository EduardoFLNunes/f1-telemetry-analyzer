"""As condicoes do teste no jogo (pedido 47, ADR 0029) e as linhas de cada uma."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import numpy as np

from .. import config

PISTA_ORIGINAL = "vhe_interlagos"
PISTA_COPIA = "vhe_interlagos_teste_m1"
LAYOUT = "gp"
NOME_NO_JOGO = {"gp": "Interlagos [teste]", "norm": "Interlagos National [teste]"}
VOLTA_IA = "2026-10-04_03-42-10_vhe_interlagos#0013"
VOLTA_EDUARDO = "2026-10-24_13-43-32_vhe_interlagos#0003"
CONDICOES = ("C0", "C1", "C2", "C3", "C4")
DESCRICAO = {
    "C0": "a linha original (o arquivo da copia sem mudanca)",
    "C1": f"a volta da IA {VOLTA_IA}, codificada como as linhas da busca do pedido 46",
    "C2": f"a melhor volta do Eduardo {VOLTA_EDUARDO}, codificada do mesmo jeito",
    "C3": "a linha gerada sem a LSTM (data/ml/modelo1_final/linha_sem_lstm.npy)",
    "C4": "a linha gerada com a LSTM (data/ml/modelo1_final/linha_com_lstm.npy)",
}


def pasta_do_jogo() -> Path:
    from core.track_file_resolver import TrackFileResolver

    return TrackFileResolver().resolve_ac_root()


def fast_lane_original() -> Path:
    return pasta_do_jogo() / "content" / "tracks" / PISTA_ORIGINAL / LAYOUT / "ai" / "fast_lane.ai"


def raiz_saida() -> Path:
    """`data/pista_teste/` da pasta do pedido (fora do git)."""
    return config.repo_root() / "data" / "pista_teste"


def lateral_da_linha(track, xz: np.ndarray) -> np.ndarray:
    """Uma linha em X/Z (pontos em ordem) como deslocamento lateral na grade da geometria."""
    s, lat = track.project_sequence(np.asarray(xz, float))
    ordem = np.argsort(s)
    s, lat = s[ordem], lat[ordem]
    return np.interp(track.s, np.r_[s - track.length, s, s + track.length], np.r_[lat, lat, lat])


def linhas(track, original_xz: np.ndarray) -> Dict[str, np.ndarray]:
    """{condicao: deslocamento lateral na grade}. C0 e a linha do arquivo original, projetada na grade."""
    from ..optimization.representation import DEFAULT_CONTROL_SPACING_M, build_encoding
    from ..optimization.seed import lateral_by_lap
    from ..scripts import retreino_lstm as RL

    encoding = build_encoding(track, spacing_m=DEFAULT_CONTROL_SPACING_M)
    src = RL.load_prepared(track)
    lat = lateral_by_lap(src.store, [VOLTA_IA, VOLTA_EDUARDO])
    for lap in (VOLTA_IA, VOLTA_EDUARDO):
        if lap not in lat or not np.isfinite(lat[lap]).all():
            raise SystemExit(f"PARADO: a volta {lap} nao esta entre as voltas rotuladas com a lateral completa.")
    raiz = config.artifacts_root() / "modelo1_final"
    return {
        "C0": lateral_da_linha(track, original_xz),
        "C1": encoding.decode(encoding.encode(lat[VOLTA_IA])),
        "C2": encoding.decode(encoding.encode(lat[VOLTA_EDUARDO])),
        "C3": np.load(raiz / "linha_sem_lstm.npy"),
        "C4": np.load(raiz / "linha_com_lstm.npy"),
    }
