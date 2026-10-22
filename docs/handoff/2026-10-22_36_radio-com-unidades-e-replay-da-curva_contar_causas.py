"""Pedido 36 (fechamento): quantas mensagens com causa perderam a causa na fala, antes e depois.

Com causa: a frase do coach com `causa`, o resumo com `piorCurva` e a analise com alguma
diferenca dita na primeira curva. Perdeu: a fala nao diz nenhuma diferenca (freada, minima,
acelerador, tracado) nem, no resumo, a curva que mais perdeu.
Uso: python contar_causas.py <pasta> <saida.json> 13-10 18-10 21-10 ...
"""
import json, re, sys
from pathlib import Path
P, SAIDA, SESSOES = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]
CAUSA = re.compile(r"Freia|Acelera|M[íi]nima|Passa")

def contar(arq):
    ms = json.loads(arq.read_text(encoding='utf-8'))['mensagens']
    com, quais, dur = 0, [], {}
    for m in ms:
        o, fala = m['origem'], m.get('fala') or ''
        d = dur.setdefault(o, [99, 0, 0]); d[0] = min(d[0], m['duracaoS']); d[1] = max(d[1], m['duracaoS']); d[2] += 1
        if o == 'coach' and m.get('causa'):
            tem, disse = True, bool(CAUSA.search(fala))
        elif o == 'resumo' and m.get('piorCurva'):
            tem, disse = True, 'Mais perdeu' in fala or 'mais perdeu' in fala
        elif o == 'analise' and (m.get('curvasDaAnalise') or [{}])[0].get('ditas'):
            tem, disse = True, bool(CAUSA.search(fala))
        else:
            continue
        com += 1
        if not disse:
            quais.append([o, m['id'], fala, m['duracaoS']])
    return {'mensagens': len(ms), 'comCausa': com, 'perderamACausa': len(quais), 'quais': quais, 'duracao': dur}

out = {s: {q: contar(P / f'radio_{q}2_{s}.json') for q in ('antes', 'depois')} for s in SESSOES}
SAIDA.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
for s, v in out.items():
    print(s, 'antes', v['antes']['perderamACausa'], 'de', v['antes']['comCausa'], '| depois', v['depois']['perderamACausa'], 'de', v['depois']['comCausa'], '| mensagens', v['depois']['mensagens'], v['depois']['duracao'])
    for q in v['depois']['quais']: print('   ', q)
