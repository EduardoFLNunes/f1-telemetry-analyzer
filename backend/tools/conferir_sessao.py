"""Conferencia de fim de sessao numa gravacao ja feita, so lendo (pedido 28, Parte E.2).

    python tools/conferir_sessao.py --sessao PASTA [--sessao PASTA ...] [--saida ARQUIVO.json]

Roda a mesma conferencia da aba "Coleta de dados" (`core.coleta.conferencia`)
sobre a sessao inteira e imprime, volta a volta, o tempo, os portoes e o
preenchimento de cada grupo, e o veredito da M1. Com o store v2 do repositorio
a mao, compara as voltas que a conferencia deixa entrar com as que o store tem
daquela sessao, e o tempo de cada uma.

Nao escreve na gravacao nem em `data/verificacoes`; so no `--saida`.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.coleta.conferencia import candidatos_de_geometria, carregar_geometria, conferir_sessao  # noqa: E402
from core.coleta.oficial import STORE_V2_METADATA  # noqa: E402

REPO = BACKEND_DIR.parent


def store_laps(session_id: str):
    meta_path = REPO / "data" / "ml" / STORE_V2_METADATA
    if not meta_path.exists():
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return {lap["lap_id"]: lap for lap in meta.get("laps") or [] if lap.get("session_id") == session_id}


def compare_with_store(result):
    laps = store_laps(result["sessao"])
    if laps is None:
        return None
    entram = {v["lapId"]: v for v in result["voltas"] if v["entraNoStore"]}
    comuns = sorted(set(entram) & set(laps))
    diferencas = {lap_id: round(abs(entram[lap_id]["tempoS"] - float(laps[lap_id]["lap_time_s"])), 6)
                  for lap_id in comuns}
    return {
        "voltas_no_store": sorted(laps),
        "voltas_que_a_conferencia_deixa_entrar": sorted(entram),
        "so_na_conferencia": sorted(set(entram) - set(laps)),
        "so_no_store": sorted(set(laps) - set(entram)),
        "maior_diferenca_de_tempo_s": max(diferencas.values()) if diferencas else None,
        "origem_no_store": {lap_id: laps[lap_id].get("origem") for lap_id in sorted(laps)},
        "origem_fonte_no_store": {lap_id: laps[lap_id].get("origem_fonte") for lap_id in sorted(laps)},
    }


def print_result(result, comparison, seconds):
    print("=" * 78)
    print(f"{result['sessao']}  ({seconds:.1f} s, {result['leitura']['linhas']} linhas, "
          f"{result['leitura']['bytes'] / 1e6:.0f} MB)")
    gravacao = result["gravacao"]
    print(f"  carModel: {gravacao.get('carModel')}  app: {gravacao.get('appVersion')} {gravacao.get('appCommit')}")
    print(f"  geometria: {result['geometria']['geometryId'] if result['geometria'] else None}")
    print(f"  {'volta':>6} {'jogo':>4} {'amostras':>8} {'quem':>13} {'tempo':>9}  portoes  base origem limites  m1 contexto")
    for v in result["voltas"]:
        grupos = v["preenchimentoGrupos"]
        fill = "  ".join(f"{grupos[g]['minimo']:>4.0%}" for g in ("base", "origem", "limites", "m1", "contexto"))
        tempo = v["tempo"] or (f"({v['duracao']})" if v["duracao"] else "-")
        status = "passa" if v["entraNoStore"] else "nao passa"
        print(f"  #{v['sequencia']:04d} {v['voltaDoJogo']:>4} {v['amostras']:>8} {v['origemRotulo']:>13} {tempo:>9}  "
              f"{status:<9} {fill}")
        if not v["entraNoStore"]:
            print(f"         motivo: {'; '.join(v['motivos'])}")
    veredito = result["veredito"]
    print(f"  VEREDITO: {veredito['texto']}")
    print(f"  preenchimento na grade das validas: {veredito['preenchimentoGrade']}")
    if comparison is not None:
        print(f"  store v2: {len(comparison['voltas_no_store'])} voltas; so na conferencia {comparison['so_na_conferencia']}; "
              f"so no store {comparison['so_no_store']}; maior diferenca de tempo {comparison['maior_diferenca_de_tempo_s']} s")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessao", action="append", required=True, help="pasta da gravacao")
    parser.add_argument("--saida", help="JSON com o resultado completo")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    geometria = carregar_geometria(candidatos_de_geometria(REPO, None))
    if geometria is None:
        raise SystemExit("PARADO: geometria de Interlagos nao encontrada no repositorio.")
    out = {"gerado_em": datetime.now().isoformat(timespec="seconds"), "geometria": geometria.to_api(), "sessoes": []}
    for pasta in args.sessao:
        directory = Path(pasta)
        before = sorted((p.name, p.stat().st_size, p.stat().st_mtime_ns) for p in directory.iterdir())
        start = time.perf_counter()
        result = conferir_sessao(directory, geometria).to_api()
        seconds = time.perf_counter() - start
        after = sorted((p.name, p.stat().st_size, p.stat().st_mtime_ns) for p in directory.iterdir())
        if before != after:
            raise SystemExit(f"PARADO: a pasta {directory} mudou durante a conferencia.")
        comparison = compare_with_store(result)
        print_result(result, comparison, seconds)
        out["sessoes"].append({"resultado": result, "segundos": round(seconds, 1), "comparacao_com_store_v2": comparison,
                               "pasta_inalterada": True})
    if args.saida:
        Path(args.saida).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nresultado: {args.saida}")


if __name__ == "__main__":
    main()
