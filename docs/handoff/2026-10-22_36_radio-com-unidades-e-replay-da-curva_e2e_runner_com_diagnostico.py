"""Pedido 36, E.9: o runner do backend com um diagnostico do replay da frase (so no teste; o codigo do repo nao muda)."""
import logging, runpy, sys
from pathlib import Path
sys.path.insert(0, r"C:\Users\Dokas\Desktop\f1-telemetry-analyzer\backend")
import numpy as np
import core.radio.servico as sv
from core.radio.analise import grade
from core.radio.replay import janela_da_curva, cobertura_na_curva
log = logging.getLogger("diagnostico_do_replay")
original = sv.RadioDoEngenheiro._replay_da_frase

def com_diagnostico(self, mensagem):
    r = original(self, mensagem)
    try:
        codigo, numero = mensagem.get("curva"), mensagem.get("volta")
        ref = self._grade_da_referencia()
        partes = [f"curva={codigo} volta={numero!r} causa={bool(mensagem.get('causa'))} geometria={self._geometria is not None} ref={ref is not None} -> {len(r)} curva(s)"]
        for nome, c in (("atual", self._volta_atual()), ("fechada", self._volta_fechada())):
            if not c:
                partes.append(f"{nome}=None"); continue
            p = f"{nome}: volta={c.get('volta')!r} linhas={bool(c.get('linhas'))} pontos={c.get('pontosDaGrade')} track={int(self._geometria.track.size) if self._geometria is not None else None}"
            if c.get("linhas") and ref is not None:
                try:
                    g = grade(c["linhas"]); j = janela_da_curva(self._geometria, codigo, g, ref["grade"])
                    p += f" janela={'None' if j is None else len(j[2])} cobertura={None if j is None else round(cobertura_na_curva(c['linhas'], j[2]), 3)}"
                except Exception as e:
                    p += f" erro={type(e).__name__}: {e}"
            partes.append(p)
        log.warning("replay da frase: " + " | ".join(partes))
    except Exception as e:
        log.warning("diagnostico falhou: %s", e)
    return r

sv.RadioDoEngenheiro._replay_da_frase = com_diagnostico
sys.argv = [r"C:\Users\Dokas\Desktop\f1-telemetry-analyzer\backend\desktop_backend_runner.py"]
runpy.run_path(sys.argv[0], run_name="__main__")
