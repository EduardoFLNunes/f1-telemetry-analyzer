"""Pedido 36, E.9: o backend do repositorio na porta de teste 8011, com as pastas isoladas e o reprodutor."""
import os, subprocess, sys
from pathlib import Path
REPO = Path(r"C:\Users\Dokas\Desktop\f1-telemetry-analyzer")
AQUI = Path(__file__).resolve().parent
(AQUI / "runtime" / "gravacoes").mkdir(parents=True, exist_ok=True)
env = dict(os.environ, AT_BACKEND_PORT="8011", AT_BACKEND_RESOURCE_ROOT=str(REPO), AT_BACKEND_REPO_ROOT=str(REPO),
           AT_BACKEND_RUNTIME_ROOT=str(AQUI / "runtime"), TELEMETRY_RECORDING_DIR=str(AQUI / "runtime" / "gravacoes"),
           AT_TESTE_REPRODUTOR="1", PYTHONIOENCODING="utf-8")
with (AQUI / "backend.log").open("wb") as log:
    sys.exit(subprocess.call([str(REPO / ".venv" / "Scripts" / "python.exe"), str(AQUI / "runner_com_diagnostico.py")],
                             cwd=str(REPO / "backend"), env=env, stdout=log, stderr=subprocess.STDOUT))
