# 0010 — Fase 2b ajustada pela leitura dos artigos

- **Status:** aceita; complementa o ADR 0005
- **Data:** 2026-10-02
- **Decisor:** Eduardo

## Contexto

A leitura de oito artigos de corrida autônoma (documento "Artigos de corrida autônoma — o que cada um traz para o projeto") trouxe quatro pontos que afetam diretamente a Fase 2b:

- Kabzan et al. (2019) e Jain et al. (BayesRace, 2021): Processos Gaussianos aprendem bem com poucos dados e entregam a incerteza junto da previsão.
- Identificação na pista em menos de um minuto (2025): com poucos dados, redes maiores decoram os dados; e o modelo diverge fora da faixa de situações que viu.
- O KNN de regressão é o estimador empírico mais simples, e é o modelo que o Eduardo já conhece.
- Toda faixa de incerteza precisa ser conferida: uma "faixa de 95 %" que só acerta 60 % das vezes engana.

## Decisão

A Fase 2b compara, na janela de curva do ADR 0005:

| Estimador | O que é | Incerteza |
|---|---|---|
| E0 | prever zero | — |
| E1 | simulador calibrado na janela | — |
| E2 | regressão linear com regularização sobre diferenças acionáveis | resíduos das sessões de treino |
| E3 | KNN de regressão (k escolhido só com as sessões de treino) | dispersão dos vizinhos ou resíduos de treino |
| E4 | Processo Gaussiano sobre as mesmas diferenças | desvio previsto pelo próprio modelo |
| E2-teto | E2 com velocidades mínima e de saída | só como teto, nunca como candidato |

Regras novas:

1. **Sem redes neurais nesta fase.** Modelos pequenos primeiro.
2. **Filtro de fora da distribuição.** Se alguma diferença de entrada do par de teste fica fora da faixa de 2,5 % a 97,5 % das diferenças vistas nas sessões de treino para aquela curva, a resposta é "não conclusivo", contada à parte.
3. **Calibração das faixas.** Para cada estimador com incerteza, relatar a fração dos ΔT reais que caem dentro da faixa de 95 %. Uma faixa bem calibrada fica perto de 95 %.
4. **Mesmo protocolo e mesmos critérios do ADR 0006,** fixados antes de rodar, com a curva risco × cobertura de cada estimador.

## Consequências

- A Fase 2b fica um pouco maior, mas todos os estimadores rodam no mesmo conjunto de pares e no mesmo protocolo, o que torna a comparação justa.
- O simulador + corretor aprendido (proposta 1 do documento dos artigos) fica para a etapa seguinte. Se E4 funcionar, a mesma técnica é aplicada ao resíduo do simulador.
