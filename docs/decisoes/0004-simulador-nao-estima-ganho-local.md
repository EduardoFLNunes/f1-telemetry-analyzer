# 0004 — O simulador não é usado para estimar ganho de tempo local

- **Status:** aceita
- **Data:** 2026-09-30
- **Decisor:** Eduardo

## Contexto

Na Fase 2 do plano (validação do estimador, entregue junto com a Fase 1 na tag `handoff/fase1`) foram avaliados 6 728 microsetores de pares comparáveis, em 7 sessões, deixando uma sessão inteira de fora a cada rodada. Nenhuma variante do simulador bateu "prever ganho zero":

| estimador | skill vs. zero | IC 95 % |
|---|---|---|
| simulador direto | −1,69 | [−9,2; −0,7] |
| simulador × eficiência | −0,66 | [−3,8; −0,3] |
| simulador calibrado | −0,27 | [−2,5; +0,01] |
| rede substituta (3 sessões) | −0,57 | [−3,5; −0,3] |

- O simulador acerta a direção da diferença em ~77 % dos casos, mas não o tamanho.
- Agrupar microsetores em trechos maiores não resolveu. Este é um teste exploratório feito pelo Claude (Cowork), não pela sessão de implementação: ele somou as predições e as diferenças observadas de `data/ml/validation/counterfactual/pares_por_microsetor.parquet` em blocos de 5, 10, 25 e 50 microsetores consecutivos, só com blocos inteiramente comparáveis. Skill do simulador calibrado: −0,15, −0,27, −0,47, +0,10 e +0,07 (com 1, 5, 10, 25 e 50 microsetores). Nenhum resultado é consistente, e os blocos maiores têm poucas amostras (430 e 42). A Fase 2b repete o teste formalmente, avaliando o simulador na janela de curva (estimador E1).
- Times de Fórmula SAE já usam simulador só para diferenças relativas, nunca para tempo absoluto. Aqui, nem a diferença relativa se sustenta na escala de uma curva.

## Decisão

- O tempo do simulador não é apresentado como ganho estimado em curva ou microsetor.
- Os alvos do coach mostram onde frear e qual velocidade mínima atingir, sem segundos por trecho, até um estimador passar na validação (ver 0005).
- O simulador continua disponível para gerar trajetórias candidatas e para análise de direção (melhora ou piora).

## Consequências

- O "ganho estimado: X s" do experimento final depende do estimador empírico (0005).
- A interface do coach precisa de ajuste: esconder ou rotular os segundos por trecho.
- Caminho futuro, quando houver dados suficientes: aprender o erro do simulador (resíduo), como em Kabzan et al., Learning-Based MPC.
