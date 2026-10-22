"""Pedido 36, Parte B.3: quanto o log do backend cresce por hora, numa reproducao de gravacao.

Sobe o backend do repositorio (o `desktop_backend_runner.py`, o mesmo do app) na porta
de teste, com a pasta de dados e as gravacoes isoladas no scratchpad e o reprodutor
ligado (`AT_TESTE_REPRODUTOR=1`); toca a sessao de 21/10 pelo caminho do jogo; e pede as
rotas no ritmo medido no teste no jogo de 21/10: os pontos novos 28 vezes por segundo
(a tela Ao vivo) e as mensagens do radio a cada 0,3 s duas vezes (o app do jogo e a
tela). O log e a saida do processo, como no app. Mede o crescimento depois do arranque.

Uso: python medir_log.py <rotulo> <segundos> <saida.json>
"""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROTULO, SEGUNDOS, SAIDA = sys.argv[1], float(sys.argv[2]), Path(sys.argv[3])
REPO = Path(r"C:\Users\Dokas\Desktop\f1-telemetry-analyzer")
AQUI = Path(__file__).resolve().parent
PORTA = 8011
BASE = f"http://127.0.0.1:{PORTA}"
LOG = AQUI / f"backend_{ROTULO}.log"
GRAVACAO = REPO / "data" / "recordings" / "2026-10-21_20-30-54_vhe_interlagos" / "player.jsonl"

env = dict(os.environ, AT_BACKEND_PORT=str(PORTA), AT_BACKEND_RESOURCE_ROOT=str(REPO), AT_BACKEND_REPO_ROOT=str(REPO),
           AT_BACKEND_RUNTIME_ROOT=str(AQUI / "runtime"), TELEMETRY_RECORDING_DIR=str(AQUI / "runtime" / "gravacoes"),
           AT_TESTE_REPRODUTOR="1", PYTHONIOENCODING="utf-8")
(AQUI / "runtime" / "gravacoes").mkdir(parents=True, exist_ok=True)
saida_do_processo = LOG.open("wb")
proc = subprocess.Popen([str(REPO / ".venv" / "Scripts" / "python.exe"), str(REPO / "backend" / "desktop_backend_runner.py")],
                        cwd=str(REPO / "backend"), env=env, stdout=saida_do_processo, stderr=subprocess.STDOUT)


def pedir(caminho: str, corpo=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(BASE + caminho, data=dados, headers={"Content-Type": "application/json"} if dados else {})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read() or b"null")


try:
    for _ in range(120):
        try:
            pedir("/api/radio/estado")
            break
        except Exception:
            time.sleep(1)
    else:
        raise SystemExit("o backend nao subiu")
    pedir("/api/teste/reproduzir", {"arquivo": str(GRAVACAO), "desdeVolta": 8, "velocidade": 1.0})
    parar = threading.Event()
    contagem = {"novos": 0, "mensagens": 0, "erros": 0}

    def tela_ao_vivo():
        versao = desde = None
        while not parar.is_set():
            t = time.perf_counter()
            try:
                q = "" if versao is None else f"?versao={versao}&desde={desde}"
                r = pedir("/api/live/volta/novos" + q)
                versao, desde = r.get("versao", versao), r.get("seq", desde)
                contagem["novos"] += 1
            except Exception:
                contagem["erros"] += 1
            time.sleep(max(0.0, 1 / 28 - (time.perf_counter() - t)))

    def radio():
        while not parar.is_set():
            try:
                pedir("/api/radio/mensagens?desde=0")
                contagem["mensagens"] += 1
            except Exception:
                contagem["erros"] += 1
            time.sleep(0.3)

    fios = [threading.Thread(target=tela_ao_vivo), threading.Thread(target=radio), threading.Thread(target=radio)]
    for f in fios:
        f.start()
    time.sleep(10)                      # o arranque da reproducao fica de fora
    saida_do_processo.flush()
    b0, t0 = LOG.stat().st_size, time.time()
    time.sleep(SEGUNDOS)
    b1, t1 = LOG.stat().st_size, time.time()
    parar.set()
    for f in fios:
        f.join()
    linhas = LOG.read_bytes().decode("utf-8", "replace").splitlines()
    acesso = sum(1 for l in linhas if '"GET /api/' in l or '"POST /api/' in l)
    resultado = {"rotulo": ROTULO, "segundosMedidos": round(t1 - t0, 1), "bytes": b1 - b0,
                 "bytesPorHora": round((b1 - b0) / (t1 - t0) * 3600), "MBporHora": round((b1 - b0) / (t1 - t0) * 3600 / 2**20, 2),
                 "pedidos": contagem, "linhasDeAcessoNoLog": acesso, "linhasNoLog": len(linhas)}
    print(json.dumps(resultado, ensure_ascii=False))
    SAIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
finally:
    try:
        pedir("/api/teste/parar", {})
    except Exception:
        pass
    proc.terminate()
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()
    saida_do_processo.close()
