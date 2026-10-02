# 0006 — Protocolo de validação dos estimadores

- **Status:** aceita; aplicada na Fase 2
- **Data:** 2026-09-30
- **Decisor:** Eduardo

## Contexto

Amostras da mesma volta e da mesma sessão são correlacionadas. Dividir aleatoriamente infla os resultados; a validação deixando um participante inteiro de fora é o padrão quando há medições repetidas da mesma pessoa.

A meteorologia mede o valor de um modelo pelo skill score: quanto ele erra menos que uma previsão ingênua.

## Decisão

- **Divisão:** deixar uma sessão inteira de fora a cada rodada. Tudo que é ajustado (envelope, parâmetros, calibração) usa só as outras sessões.
- **Métrica principal:** erro na diferença de tempo, nunca tempo absoluto.
- **Referência:** prever ganho zero. Skill = 1 − MAE do modelo ÷ MAE de prever zero.
- **Relatar:** MAE, RMSE, viés, dispersão, correlação de Spearman, concordância de sinal, IC 95 % por bootstrap agrupado por sessão; resultados separados por ritmo, por sessão e por tamanho da diferença.
- **Critérios fixados antes de rodar**, sem ajuste depois de ver o resultado. Para aprovar, todos precisam ser atendidos:
  - skill ≥ 0,20;
  - limite inferior do IC 95 % do skill > 0;
  - |viés| ≤ 25 % do erro de prever zero;
  - Spearman ≥ 0,30;
  - concordância de sinal ≥ 0,65;
  - pelo menos 70 % das sessões com skill positivo;
  - pelo menos 5 sessões testáveis.
- **Concentração de dados:** quando uma ou duas sessões dominam a amostra, relatar também o resultado sem elas. Hoje as sessões 2026-08-09_19-20-59 e 2026-06-20_13-13-02 somam 91 de 122 voltas (75 %), 39 958 de 42 805 microsetores comparáveis (93 %) e 6 237 de 6 728 microsetores primários (93 %).

## Consequências

- Resultados negativos são aceitos e documentados.
- Mudar um critério exige um novo ADR, registrado antes de rodar o experimento.
