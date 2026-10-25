"""Modelo 2: o erro que custou tempo, as tecnicas e o estilo (pedido 38, ADR 0023).

As regras foram registradas antes de rodar nas voltas, em
`docs/modelo2_tecnica_e_estilo.md`, secao 1. As pecas:

* `dados` -- as voltas rotuladas da IA e do piloto (store v2 e as gravacoes
  posteriores a ele) e as taxas no tempo original, levadas a grade;
* `conferencias` -- os canais antes de qualquer detector (Parte B.3);
* `fases` -- as fases de cada curva, fixas para todas as voltas (Parte C);
* `detectores` -- uma regra por tecnica ou erro, com tres estados (Parte E);
* `perda` -- a perda por fase, o ranking, a cadeia causal e a atribuicao (Parte D);
* `estilo` -- as dimensoes de estilo por tipo de curva (Parte F);
* `supervisionado` -- o tempo do trecho contra os indicadores (Parte G);
* `rotulagem` -- o kit para validar 5 detectores (Parte H).

Nada daqui e lido pelo app, pelo radio ou pelo coach.
"""
