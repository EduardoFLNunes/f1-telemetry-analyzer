"""Atualiza o coach depois de uma sessao, com um comando so (pedido 15).

    python tools/atualizar_coach.py [--sem-varrer | --completo] [--saida data/ml/origem]
        [--modelo ARQUIVO] [--geometria-arquivo ARQUIVO] [--resumo ARQUIVO]

Em ordem:

1. refaz o inventario novo em `data/ml/origem/`, lendo das duas pastas de
   gravacoes so as sessoes novas ou mudadas; as outras saem do cache por
   gravacao em `data/ml/origem/cache/` (pedido 25; `--completo` le todas e
   refaz o cache, `--sem-varrer` pula o passo);
2. aplica as anotacoes versionadas da sessao de 04/10
   (`docs/experimentos/2026-10-04_rotulos_por_volta.csv`);
3. rotula as sessoes novas sem anotacao: antes de a IA ligar pela primeira vez
   na sessao do jogo, `humano` pelo indicador; a volta em que ela liga,
   `misturada`; depois, com o indicador travado, o detector pela linha da IA
   decide, e o que ele nao resolve fica `desconhecida`;
4. copia o modelo do repositorio para `data/reference_models/backup/` e o
   treina de novo;
5. imprime o resumo: as duas referencias, as voltas de cada origem, o limiar e
   o foco inicial;
6. refaz o store v2 com as checagens (`ml.scripts.build_lap_store_v2`, pedido
   16), para as sessoes novas entrarem no relatorio de evolucao; as voltas das
   sessoes que nao mudaram saem do cache em `data/ml/cache_store_v2/`, e os
   rotulos e o `carModel` sao sempre recalculados (pedido 25);
7. roda o relatorio de evolucao (`tools/relatorio_evolucao.py`).

Nao toca no store antigo (`laps_grid.parquet`) nem no app instalado: o modelo
gravado e o do repositorio, lido pelo app de desenvolvimento. Qualquer trava
dos passos (os rotulos de 04/10 que nao batem com o inventario, os limites do
detector que nao batem com a sessao rotulada, nenhuma volta limpa para
treinar, uma checagem do store v2 que falha) para o comando.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from core.assisted_analysis.reference_model import (  # noqa: E402
    DEFAULT_REFERENCE,
    REFERENCE_KINDS,
    REFERENCE_LABELS,
    DriverReferenceModel,
    model_path,
)
from core.live.driving_coach import LiveDrivingCoach  # noqa: E402
from ml import config  # noqa: E402
from ml.data import origin  # noqa: E402
from ml.data.inventory import inventory_path  # noqa: E402
from ml.data.store_v2 import store_v2_meta  # noqa: E402
from ml.scripts import build_lap_store_v2, detector_ia, report_lap_origin  # noqa: E402
from ml.track.geometry import load_geometry  # noqa: E402

TRACK = "vhe_interlagos"
# A pasta do app instalado: o comando nunca grava nela.
INSTALLED_APP_FOLDER = "Automobilista Telemetria"
TIMES_FILE = "atualizar_coach_tempos.json"
STEPS = {
    "1": "inventario",
    "2-3": "anotacoes e sessoes novas",
    "4": "backup e treino",
    "5": "resumo",
    "6": "store v2",
    "7": "relatorio de evolucao",
}


def _tool(name: str):
    spec = importlib.util.spec_from_file_location(name, BACKEND_DIR / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _train_script():
    return _tool("train_reference_model")


def _evolution_script():
    return _tool("relatorio_evolucao")


def backup_model(path: Path, now: Optional[datetime] = None) -> Optional[Path]:
    """Copia o modelo para `backup/<nome>.<data_hora>.antes-de-atualizar.json`. Nada a copiar -> None."""
    if not path.exists():
        return None
    stamp = (now or datetime.now()).strftime("%Y-%m-%d_%H-%M-%S")
    target = path.parent / "backup" / f"{path.stem}.{stamp}.antes-de-atualizar{path.suffix}"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise SystemExit(f"PARADO: o backup {target} ja existe.")
    shutil.copy2(path, target)
    return target


def origin_counts(inventory: pd.DataFrame) -> Dict[str, object]:
    """Voltas de cada origem: todas, e as do equipamento atual (as que falam do piloto de hoje)."""
    current = inventory[inventory["equipamento"] == origin.CURRENT_EQUIPMENT]
    return {
        "todas": {k: int(v) for k, v in inventory["origem"].value_counts().items()},
        "equipamento_atual": {k: int(v) for k, v in current["origem"].value_counts().items()},
        "equipamento_atual_por_fonte": {
            f"{o} ({f})": int(n) for (o, f), n in current.groupby(["origem", current["origem_fonte"].fillna("-")]).size().items()
        },
    }


class _Silent:
    def schedule(self, topic, payload, loop_ref=None):
        pass


def summary(model: DriverReferenceModel, inventory: pd.DataFrame) -> Dict[str, object]:
    """As duas referencias, as voltas de cada origem, o limiar e o foco inicial de cada modo."""
    coach = LiveDrivingCoach(_Silent(), lambda _t: model)
    thresholds = np.array([coach._threshold_for(t) for t in model.targets], dtype=float)
    references = {}
    focus = {}
    for kind in REFERENCE_KINDS:
        reference = model.references.get(kind)
        if not reference:
            references[kind] = None
            continue
        references[kind] = {"volta": reference.get("lap_id"), "tempo_s": reference.get("lap_seconds"),
                            "carro": reference.get("carro")}
        model.use_reference(kind)
        sectors, source = coach.focus_sectors(model)
        by_index = {t.index: t for t in model.targets}
        focus[kind] = {
            "setores": list(sectors),
            "fonte": source,
            "diferenca_mediana_s": {
                str(k): round(float(by_index[k].median_seconds) - float(by_index[k].reference_seconds), 3)
                for k in sectors
            },
        }
    model.use_reference(DEFAULT_REFERENCE)
    return {
        "referencias": references,
        "referencia_padrao": model.reference_kind,
        "voltas_do_piloto_no_modelo": model.lap_count,
        "voltas_por_origem": origin_counts(inventory),
        "limiar_s": {
            "regra": "2 x (mediana - melhor) das suas voltas por microsetor, minimo de 0.06 s",
            "mediana": round(float(np.median(thresholds)), 3) if thresholds.size else None,
            "min": round(float(thresholds.min()), 3) if thresholds.size else None,
            "max": round(float(thresholds.max()), 3) if thresholds.size else None,
            "microsetores_no_minimo": int((thresholds <= coach.min_loss_seconds + 1e-9).sum()),
        },
        "foco_inicial": focus,
    }


def print_summary(result: Dict[str, object]) -> None:
    print()
    print("=" * 66)
    print("RESUMO DO COACH")
    for kind, reference in result["referencias"].items():
        label = REFERENCE_LABELS.get(kind, kind)
        if reference is None:
            print(f"  {kind:13s}: nenhuma volta valida")
            continue
        print(f"  {kind:13s}: {reference['tempo_s']:.3f} s  {reference['volta']}  ({label})")
    print(f"  referencia padrao do app: {result['referencia_padrao']}")
    counts = result["voltas_por_origem"]
    print(f"  voltas por origem, equipamento atual: {counts['equipamento_atual']}")
    print(f"     por fonte: {counts['equipamento_atual_por_fonte']}")
    print(f"  voltas por origem, todas: {counts['todas']}")
    print(f"  voltas suas no modelo (limpas): {result['voltas_do_piloto_no_modelo']}")
    t = result["limiar_s"]
    print(f"  limiar: mediana {t['mediana']} s (min {t['min']}, max {t['max']}; "
          f"{t['microsetores_no_minimo']} microsetores no minimo de 0.06 s)")
    for kind, focus in result["foco_inicial"].items():
        listed = ", ".join(f"{k} ({v:.2f} s)" for k, v in focus["diferenca_mediana_s"].items())
        print(f"  foco inicial, {kind}: setores {listed}  [fonte: {focus['fonte']}]")
    print("=" * 66)


class Clock:
    """O tempo de cada passo e o que os passos 1 e 6 leram (pedido 25)."""

    def __init__(self):
        self.started = time.perf_counter()
        self.steps: Dict[str, float] = {}
        self.reads: Dict[str, Dict[str, object]] = {}
        self.final_line: Optional[str] = None
        self._open: Optional[tuple] = None

    def start(self, step: str) -> None:
        self.stop()
        self._open = (step, time.perf_counter())

    def stop(self) -> None:
        if self._open is not None:
            step, t0 = self._open
            self.steps[step] = self.steps.get(step, 0.0) + time.perf_counter() - t0
            self._open = None

    def report(self, out_dir: Path) -> None:
        self.stop()
        total = time.perf_counter() - self.started
        print()
        print("tempo de cada passo:")
        for step, name in STEPS.items():
            if step in self.steps:
                print(f"  {step:4s} {name:28s} {self.steps[step]:8.1f} s")
        print(f"  {'':4s} {'total':28s} {total:8.1f} s")
        for step, info in self.reads.items():
            if not info:
                continue
            gone = info.get("sumiram") or []
            print(f"  passo {step}: {info.get('modo')}; lidas {len(info.get('lidas') or [])}, do cache "
                  f"{info.get('do_cache')}" + (f", sumiram {len(gone)}" if gone else "")
                  + (f" (motivo: {info['motivo']})" if info.get("motivo") else ""))
        try:
            (out_dir / TIMES_FILE).write_text(json.dumps({
                "gerado_em": datetime.now().isoformat(timespec="seconds"),
                "passos_s": {k: round(v, 1) for k, v in self.steps.items()},
                "total_s": round(total, 1),
                "leituras": self.reads,
            }, indent=1, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass


def main(argv=None) -> int:
    clock = Clock()
    code, args = _run(argv, clock)
    if args is not None:
        clock.report(args.saida)
    if clock.final_line:
        # Pedido 17: a ultima linha e o caminho do painel.
        print()
        print(clock.final_line)
    return code


def _run(argv, clock: Clock):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    scan_mode = parser.add_mutually_exclusive_group()
    scan_mode.add_argument("--sem-varrer", action="store_true", help="pula o passo 1 e usa o inventario que ja existe")
    scan_mode.add_argument("--completo", action="store_true",
                           help="le todas as gravacoes nos passos 1 e 6 e refaz os dois caches")
    parser.add_argument("--saida", type=Path, default=config.artifacts_root() / "origem",
                        help="pasta do inventario novo (padrao: data/ml/origem)")
    parser.add_argument("--modelo", type=Path, default=model_path(BACKEND_DIR.parent, TRACK),
                        help="modelo do coach (padrao: o do repositorio, lido pelo app de desenvolvimento)")
    parser.add_argument("--geometria-arquivo", type=Path, default=None)
    parser.add_argument("--resumo", type=Path, default=None, help="JSON do resumo (padrao: <saida>/atualizar_coach.json)")
    args = parser.parse_args(argv)

    if INSTALLED_APP_FOLDER.lower() in str(args.modelo.resolve()).lower():
        print(f"PARADO: {args.modelo} e o modelo do app instalado; este comando so grava o do repositorio.")
        return 2, None
    if INSTALLED_APP_FOLDER.lower() in str(args.saida.resolve()).lower():
        print(f"PARADO: {args.saida} fica no app instalado; o inventario e os caches nao sao gravados la.")
        return 2, None
    track = load_geometry()
    args.saida.mkdir(parents=True, exist_ok=True)
    # Pedido 25: o incremental e o padrao desde que as tres rodadas da conferencia passaram.
    mode = "completo" if args.completo else "incremental"

    print("1/7 inventario novo" + (" (pulado: --sem-varrer)" if args.sem_varrer else f" ({mode})"), flush=True)
    clock.start("1")
    if not args.sem_varrer:
        clock.reads["1"] = report_lap_origin.scan(args.saida, track, mode=mode)
    if not inventory_path(args.saida).exists():
        print(f"PARADO: nenhum inventario em {args.saida}.")
        return 2, args

    print("2/7 anotacoes versionadas de 04/10 e 3/7 sessoes novas sem anotacao", flush=True)
    clock.start("2-3")
    applied = detector_ia.apply(args.saida, track, args.saida / "detector_aplicar.json", promote=False)
    labelled = applied["sessao_rotulada_aplicada"]
    print(f"   sessao de 04/10: {labelled['voltas']} voltas, {labelled['origem']}")
    for row in applied.get("sessoes_anotadas_inteiras", []):
        print(f"   gravacao anotada inteira: {row['sessao']}: {row['voltas']} voltas ({row['validas']} validas), "
              f"{row['origem']}")
    news = applied["sessoes_novas_sem_anotacao"]
    print(f"   sessoes novas sem anotacao: {len(news)}")
    for row in news:
        print(f"     {row['sessao']}: {row['voltas']} voltas, origem {row['origem']}, fonte {row['fonte']}")

    print("4/7 backup e treino do modelo do repositorio", flush=True)
    clock.start("4")
    backup = backup_model(args.modelo)
    print(f"   backup: {backup if backup else '(nao havia modelo)'}")
    train_args = ["--track", TRACK, "--inventario", str(inventory_path(args.saida)), "--saida", str(args.modelo)]
    if args.geometria_arquivo:
        train_args += ["--geometria-arquivo", str(args.geometria_arquivo)]
    code = _train_script().main(train_args)
    if code != 0:
        print("PARADO: o treino nao gravou o modelo (acima, o motivo). O backup ficou onde estava.")
        return code, args

    print("5/7 resumo", flush=True)
    clock.start("5")
    model = DriverReferenceModel.load(args.modelo)
    if model is None:
        print(f"PARADO: o modelo gravado em {args.modelo} nao abre.")
        return 2, args
    result = summary(model, pd.read_parquet(inventory_path(args.saida)))
    result["modelo"] = str(args.modelo)
    result["backup"] = str(backup) if backup else None
    result["sessoes_novas_sem_anotacao"] = news
    result["sessao_rotulada"] = labelled
    print_summary(result)
    out = args.resumo or (args.saida / "atualizar_coach.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"-> {out}")

    print("6/7 store v2, com as checagens", flush=True)
    clock.start("6")
    code = build_lap_store_v2.main(["--inventario", str(inventory_path(args.saida)), f"--{mode}"])
    construction = store_v2_meta().get("construcao") or {}
    clock.reads["6"] = {
        "modo": construction.get("modo"), "motivo": construction.get("motivo"),
        "lidas": construction.get("sessoes_lidas"), "do_cache": construction.get("sessoes_do_cache"),
        "sumiram": construction.get("sumiram"),
    } if construction else {}
    if code != 0:
        print("PARADO: o store v2 nao passou nas checagens (acima); o relatorio de evolucao nao rodou.")
        return code, args

    print("7/7 relatorio de evolucao", flush=True)
    clock.start("7")
    evolution = _evolution_script()
    code = evolution.main(["--modelo", str(args.modelo)])
    clock.stop()
    if code == 0:
        clock.final_line = f"painel da evolucao: {config.artifacts_root() / 'evolucao' / evolution.PANEL_FILENAME}"
    return code, args


if __name__ == "__main__":
    raise SystemExit(main())
