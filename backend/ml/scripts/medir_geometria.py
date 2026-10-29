"""Grava a geometria do carro direto da memoria compartilhada do jogo (pedido 39, Parte C; ADR 0024).

    python -m ml.scripts.medir_geometria [--hz 60] [--duracao SEGUNDOS] [--saida ARQUIVO]

So le. Usa o adaptador do backend (`core.assetto_adapter`), que abre as paginas
do jogo em modo de leitura e respeita a trava que espera o Assetto Corsa estar
aberto. Nao escreve na memoria do jogo, nao muda o app nem o gravador e nao le
nenhum arquivo do carro.

Grava, sem descartar nada, a cerca de 60 Hz: o cronometro do jogo
(`iCurrentTime`), o `packetId` da fisica, o `steerAngle`, o `heading`, a
`localVelocity`, a `localAngularVelocity`, a `accG`, as cargas das rodas, a
velocidade, o `cgHeight`, os 4 pontos de contato e as 4 direcoes dos pneus, a
posicao do carro (`carCoordinates`), o acelerador, o freio e se esta no box.

Os campos 4 x 3 (`tyreContactPoint`, `tyreContactHeading`) sao gravados
achatados, na ordem da memoria: a roda `w` (0 = dianteira esquerda, 1 =
dianteira direita, 2 = traseira esquerda, 3 = traseira direita), coordenada `c`
(x, y, z do mundo), fica na coluna `cp_<3w+c>` / `ch_<3w+c>`.

Termina com Ctrl+C (ou depois de `--duracao`) e salva em
`data/ml/modelo_carro/geometria_<data>.parquet`, fora do git, com um
`.json` ao lado (carro, pista, versao do jogo, amostras e taxa). O arquivo e
regravado a cada minuto, para nada se perder se o jogo fechar antes.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402

from ml import config  # noqa: E402

CARRO_ESPERADO = "rss_formula_rss_3_v6_2026"
PISTA_ESPERADA = "vhe_interlagos"
WHEELS = ("fl", "fr", "rl", "rr")


def _achatado(field) -> List[float]:
    """Um campo 4 x 3 do ctypes, na ordem da memoria (12 numeros)."""
    return [float(v) for row in field for v in row]


def amostra(physics, graphics, t_wall: float) -> Dict[str, object]:
    """Uma linha da gravacao, a partir das estruturas lidas pelo adaptador."""
    row: Dict[str, object] = {
        "t_wall": float(t_wall),
        "packet_id": int(physics.packetId),
        "graphics_packet_id": int(graphics.packetId),
        "i_current_time_ms": int(graphics.iCurrentTime),
        "completed_laps": int(graphics.completedLaps),
        "is_in_pit": int(graphics.isInPit),
        "is_in_pit_lane": int(graphics.isInPitLane),
        "status": int(graphics.status),
        "steer": float(physics.steerAngle),
        "gas": float(physics.gas),
        "brake": float(physics.brake),
        "speed_kmh": float(physics.speedKmh),
        "heading": float(physics.heading),
        "pitch": float(physics.pitch),
        "roll": float(physics.roll),
        "cg_height": float(physics.cgHeight),
        "car_x": float(graphics.carCoordinates[0]),
        "car_y": float(graphics.carCoordinates[1]),
        "car_z": float(graphics.carCoordinates[2]),
    }
    for axis, value in zip("xyz", physics.velocity):
        row[f"vel_{axis}"] = float(value)
    for axis, value in zip("xyz", physics.localVelocity):
        row[f"lv_{axis}"] = float(value)
    for axis, value in zip("xyz", physics.localAngularVel):
        row[f"lav_{axis}"] = float(value)
    for axis, value in zip("xyz", physics.accG):
        row[f"acc_{axis}"] = float(value)
    for wheel, value in zip(WHEELS, physics.wheelLoad):
        row[f"wheel_load_{wheel}"] = float(value)
    for i, value in enumerate(_achatado(physics.tyreContactPoint)):
        row[f"cp_{i}"] = value
    for i, value in enumerate(_achatado(physics.tyreContactHeading)):
        row[f"ch_{i}"] = value
    return row


def salvar(rows: List[Dict[str, object]], path: Path, meta: Dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)
    path.with_suffix(".json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    return path


class Medidor:
    """O laco de leitura. O relogio, a espera e a leitura sao injetaveis para os testes."""

    def __init__(self, adapter, path: Path, hz: float = 60.0,
                 clock: Callable[[], float] = time.perf_counter, sleep: Callable[[float], None] = time.sleep,
                 checkpoint_s: float = 60.0, log=print):
        self.adapter, self.path, self.period = adapter, Path(path), 1.0 / hz
        self.clock, self.sleep, self.checkpoint_s, self.log = clock, sleep, checkpoint_s, log
        self.rows: List[Dict[str, object]] = []
        self.meta: Dict[str, object] = {}

    def _static(self) -> Dict[str, object]:
        static = self.adapter.static
        return {"carModel": str(static.carModel), "track": str(static.track),
                "acVersion": str(static.acVersion), "smVersion": str(static.smVersion)}

    def rodar(self, duracao: Optional[float] = None, max_amostras: Optional[int] = None) -> Path:
        started = self.clock()
        last_save = started
        next_tick = started
        try:
            while True:
                now = self.clock()
                if duracao is not None and now - started >= duracao:
                    break
                if max_amostras is not None and len(self.rows) >= max_amostras:
                    break
                frame = self.adapter.poll()
                if frame is not None:
                    # No menu do jogo a pagina estatica pode vir vazia: o carro so e fixado quando aparece.
                    if not self.meta.get("carModel") and self._static()["carModel"]:
                        self.meta = {**self._static(), "inicio": self.meta.get("inicio") or datetime.now().isoformat(timespec="seconds"),
                                     "hz_pedido": 1.0 / self.period, "ferramenta": "ml.scripts.medir_geometria"}
                        ok = self.meta["carModel"] == CARRO_ESPERADO and self.meta["track"] == PISTA_ESPERADA
                        self.log(f"carro {self.meta['carModel']}, pista {self.meta['track']}"
                                 + ("" if ok else f" -- ATENCAO: a medicao so vale com {CARRO_ESPERADO} em {PISTA_ESPERADA}"))
                    self.rows.append(amostra(self.adapter.physics, self.adapter.graphics, now - started))
                if now - last_save >= self.checkpoint_s and self.rows:
                    self._salvar(now - started)
                    last_save = now
                    self.log(f"{len(self.rows)} amostras gravadas ({now - started:.0f} s)")
                next_tick += self.period
                wait = next_tick - self.clock()
                if wait > 0:
                    self.sleep(wait)
                else:
                    next_tick = self.clock()
        except KeyboardInterrupt:
            self.log("encerrado pelo Ctrl+C")
        return self._salvar(self.clock() - started)

    def _salvar(self, elapsed: float) -> Path:
        meta = {**self.meta, "amostras": len(self.rows), "segundos": round(elapsed, 2),
                "hz_medio": round(len(self.rows) / elapsed, 2) if elapsed > 0 else None}
        return salvar(self.rows, self.path, meta)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--hz", type=float, default=60.0)
    parser.add_argument("--duracao", type=float, default=None, help="segundos; sem isso, ate o Ctrl+C")
    parser.add_argument("--saida", type=Path, default=None)
    args = parser.parse_args(argv)

    from core.assetto_adapter import AssettoAdapter

    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = args.saida or (config.artifacts_root() / "modelo_carro" / f"geometria_{stamp}.parquet")
    adapter = AssettoAdapter()
    print("esperando o Assetto Corsa (Ctrl+C para sair)...", flush=True)
    try:
        while not adapter.connect():
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("saiu antes de conectar; nada gravado")
        return 1
    print(f"conectado; gravando em {path}. Ctrl+C encerra e salva.", flush=True)
    out = Medidor(adapter, path, hz=args.hz).rodar(duracao=args.duracao)
    meta = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    print(f"salvo: {out} ({meta.get('amostras')} amostras, {meta.get('hz_medio')} Hz)")
    adapter.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
