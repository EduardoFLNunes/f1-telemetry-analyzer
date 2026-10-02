# 0003 — Convenção de sinal do deslocamento lateral

- **Status:** aceita; implementada na Fase 1 (`handoff/fase1`)
- **Data:** 2026-09-30
- **Decisor:** Eduardo

## Contexto

O `lateralOffset` gravado pelo app é positivo para a direita do piloto. O `lateral` do ML é positivo para a esquerda. Nas sessões de maio, junho e agosto, a correlação entre os dois fica entre −0,95 e −0,99.

Não existe convenção universal. O código de otimização de traçado da TUM usa normal para a direita; o padrão de robótica ROS usa positivo para a esquerda.

## Decisão

- O formato gravado continua positivo para a direita, porque 11 GB de gravações já o usam.
- O ML continua positivo para a esquerda.
- A conversão acontece num único lugar: `core.projection.lateral_offset.to_left_positive`.
- Testes com amostras reais impedem regressão.

## Consequências

- Qualquer novo consumidor do `lateralOffset` usa essa função, nunca uma conversão própria.
- Toda correção lateral mostrada na interface deve dizer o lado em palavras ("0,4 m para a esquerda"), não com sinal.
