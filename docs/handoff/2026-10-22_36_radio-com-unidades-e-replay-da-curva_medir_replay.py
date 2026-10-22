"""Pedido 36, Parte H: quanto o backend leva para montar o replay (a passagem do radio_offline, com um cronometro)."""
import json, os, runpy, sys, time
sys.path.insert(0, os.getcwd())
import core.radio.servico as sv
medidas = []
def cronometrar(nome, f):
    def g(*a, **k):
        t0 = time.perf_counter(); r = f(*a, **k); medidas.append((nome, (time.perf_counter() - t0) * 1000, len(r) if isinstance(r, list) else int(bool(r))))
        return r
    return g
sv.replay_da_analise = cronometrar('analise', sv.replay_da_analise)
sv.dados_da_curva = cronometrar('frase', sv.dados_da_curva)
saida = sys.argv[3]
sys.argv = [sys.argv[1], sys.argv[2], saida]
runpy.run_path(sys.argv[0], run_name='__main__')
json.dump(medidas, open(saida + '.tempos.json', 'w'))
for n, ms, c in medidas: print(n, round(ms, 1), 'ms', c, 'curva(s)')
