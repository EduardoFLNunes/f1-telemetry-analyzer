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
from ml.data.session_cache import (  # noqa: E402
    STORE_CODE,
    STORE_FILES,
    CacheBroken,
    SessionCache,
    fingerprint,
    global_key,
)
from ml.data.store_v2 import (  # noqa: E402
    STORE_V2_FILENAME,
    STORE_V2_SCHEMA,
    build_store_v2,
    default_inventory_path,
    file_entry,
    git_commit,
    materialize_session,
    recording_periods,
    save_store_v2,
    selection_plan,
)
from ml.track.geometry import load_geometry  # noqa: E402
from ml.track.microsectors import build_microsectors  # noqa: E402

# Cache por gravacao do passo 6 do `atualizar_coach` (pedido 25), fora do git.
DEFAULT_CACHE_DIR = config.artifacts_root() / "cache_store_v2"


def lap_labels_path() -> Path:
    return config.repo_root() / "docs" / "experimentos" / "2026-10-04_rotulos_por_volta.csv"


def materials_from_cache(inventory, track, sectors, sessions, mode: str, cache_dir: Path):
    """As sessoes materializadas: do cache as que podem sair dele, lidas as outras (pedido 25).

    Uma sessao e lida de novo quando os arquivos dela mudaram, quando uma volta
    selecionada dela nao foi pedida na leitura guardada, ou quando a chave
    global mudou (entao o cache inteiro e refeito). Na releitura, as voltas
    pedidas antes continuam pedidas: materializar uma volta a mais nao muda
    nenhuma outra, e a sessao nao fica indo e voltando.

    Devolve (materiais, cache, construcao).
    """
    by_session, _, _ = selection_plan(inventory, track)
    available = {s.session_id: s for s in sessions}
    cache = SessionCache(cache_dir, global_key(track.geometry_id, config.DEFAULT_GATES, STORE_CODE))
    reason = cache.prepare("--completo" if mode == "completo" else None)
    if reason:
        print(f"   leitura completa: {reason}", flush=True)
    had_cache = bool(cache.sessions)
    wanted = {sid: seqs for sid, seqs in by_session.items() if sid in available}
    files = {sid: fingerprint(available[sid], STORE_FILES) for sid in wanted}
    materials = {}
    if reason is None:
        try:
            for sid, seqs in sorted(wanted.items()):
                entry = cache.entry(sid)
                if entry is None or not set(seqs) <= set(entry.get("sequencias_pedidas") or []):
                    continue
                material = cache.load(sid, files[sid])
                if material is not None:
                    materials[sid] = material
        except CacheBroken as exc:
            reason = f"o cache nao abre ({exc})"
            print(f"   leitura completa: {reason}", flush=True)
            cache.reset()
            materials = {}
    read = []
    for sid, seqs in sorted(wanted.items()):
        if sid in materials:
            continue
        before = cache.entry(sid) if cache.matches(sid, files[sid]) else None
        requested = set(seqs) | set((before or {}).get("sequencias_pedidas") or [])
        material = materialize_session(available[sid], requested, track, sectors)
        materials[sid] = material
        read.append(sid)
        cache.store(available[sid], files[sid], material, sequencias_pedidas=list(material.requested),
                    sha256_player=None)
        print(f"   lida: {sid} ({len(material.laps)} voltas materializadas)", flush=True)
    gone = [sid for sid in cache.session_ids if sid not in available]
    for sid in gone:
        cache.remove(sid)
    construction = {
        "modo": "completo" if reason else "incremental",
        "motivo": reason,
        "cache_vazio_no_inicio": not had_cache and reason is None,
        "sessoes_com_voltas_selecionadas": len(wanted),
        "sessoes_lidas": read,
        "sessoes_do_cache": len(wanted) - len(read),
        "sumiram": gone,
    }
    # O manifesto sai junto com os arquivos das sessoes: o cache nunca fica sem ele.
    cache.finish(construction)
    return materials, cache, construction


def recording_entries(used, by_id, cache: SessionCache = None) -> dict:
    """`file_entry` de cada gravacao usada; com o cache, o sha256 sai dele se os arquivos nao mudaram."""
    out = {}
    for sid in used:
        if sid not in by_id:
            continue
        path = by_id[sid].player_stream
        entry = cache.entry(sid) if cache is not None else None
        if entry is not None and entry.get("sha256_player") and cache.matches(sid, fingerprint(by_id[sid], STORE_FILES)):
            out[sid] = {"arquivo": str(path), "bytes": int(path.stat().st_size), "sha256": entry["sha256_player"]}
            continue
        out[sid] = file_entry(path)
        if entry is not None:
            cache.update(sid, sha256_player=out[sid]["sha256"])
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--inventario", type=Path, default=default_inventory_path())
    parser.add_argument("--relatorio", type=Path, default=config.artifacts_root() / "store_v2_relatorio.json")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--incremental", action="store_true",
                      help="usa o cache por gravacao: le so as sessoes novas ou mudadas (pedido 25)")
    mode.add_argument("--completo", action="store_true", help="le todas as sessoes e refaz o cache")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE_DIR, help="pasta do cache por gravacao")
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
    cache = construction = None
    materials = None
    if args.incremental or args.completo:
        materials, cache, construction = materials_from_cache(
            inventory, track, sectors, sessions, "completo" if args.completo else "incremental", args.cache)
    store, details = build_store_v2(inventory, track=track, sessions=sessions,
                                    progress=lambda text: print(text, flush=True), sectors=sectors,
                                    materials=materials)

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
        "gravacoes": recording_entries(used, by_id, cache),
    }
    extra = {
        "versao": 2,
        "esquema": STORE_V2_SCHEMA,
        "canais_por_volta": details.channels_by_lap,
        "construido_em": pd.Timestamp.now(tz="UTC").isoformat(),
        "commit": git_commit(),
        "entradas": inputs,
        "aprovado": bool(result["todas_passaram"]),
        "checagens": result["checagens"],
        # 05/10: para o relatorio de evolucao separar as sessoes pelas pausas.
        "periodos_das_gravacoes": recording_periods(inventory, used),
    }
    if construction is not None:
        # Pedido 25: como o store foi construido. E o unico campo novo do meta.
        extra["construcao"] = construction
        cache.finish(construction)          # de novo, agora com o sha256 das gravacoes usadas
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
