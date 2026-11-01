"""Pedido 43, Parte B.5: o `radio_offline.py` com o replay de antes do pedido (o de `develop` em 4ac3d7af).

Carrega o `replay.py` e o `servico.py` de antes (tirados com `git show 4ac3d7af:...` para a pasta
`ANTIGO`) no lugar dos atuais; o coach, o texto e o resto do radio sao os mesmos. Assim, so o
replay muda entre as rodadas de antes e de depois.

Uso (na pasta backend): ANTIGO=<pasta> python radio_offline_antes.py <pasta da sessao> <saida.json>
"""
import importlib.util
import os
import runpy
import sys
from pathlib import Path

sys.path.insert(0, os.getcwd())
import core.radio  # noqa: E402,F401  (o pacote, antes dos modulos trocados)

ANTIGO = Path(os.environ["ANTIGO"])
for nome in ("replay", "servico"):
    spec = importlib.util.spec_from_file_location(f"core.radio.{nome}", ANTIGO / f"{nome}.py")
    modulo = importlib.util.module_from_spec(spec)
    modulo.__package__ = "core.radio"
    sys.modules[f"core.radio.{nome}"] = modulo
    spec.loader.exec_module(modulo)

script = Path(__file__).with_name("2026-10-29_43_visuais-do-radio_radio_offline.py")
sys.argv = [str(script), *sys.argv[1:]]
runpy.run_path(str(script), run_name="__main__")
