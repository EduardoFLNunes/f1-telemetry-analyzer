"""Gera a pista simplificada que acompanha o app do jogo (pedido 35, Parte E).

O minimapa baixa a pista do backend (`GET /api/radio/minimapa`); com o backend fora do
ar, ele usa esta copia, que vai na pasta do app (`radio_engenheiro/pista.json`) e e
instalada pelo `instalar.ps1`. As bordas sao as mesmas da rota: a geometria oficial do
repositorio, simplificada (`core/radio/minimapa.py`). So le o repositorio.

Uso (na pasta backend): python ../tools/csp_app/gerar_pista.py
"""
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

from core.radio import minimapa  # noqa: E402
from core.radio.janelas import carregar_geometria  # noqa: E402

REPO = BACKEND.parent
track = carregar_geometria(REPO)
if track is None:
    raise SystemExit("sem a geometria oficial em data/cache/tracks")
dados = minimapa.montar(track, [], None, None, None, minimapa.linha_do_jogo_m(REPO))
saida = Path(__file__).resolve().parent / "radio_engenheiro" / "pista.json"
saida.write_text(json.dumps({"comprimentoM": dados["comprimentoM"], "pista": dados["pista"],
                             "geometryId": getattr(track, "geometry_id", None)},
                            separators=(",", ":")), encoding="utf-8")
print(f"{saida}: {saida.stat().st_size} bytes, {len(dados['pista']['esquerda'])} pontos por borda")
