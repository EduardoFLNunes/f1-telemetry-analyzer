# 0011 — Os dados observacionais não medem o efeito das instruções de controle; o próximo passo é um experimento controlado

- **Status:** aceita
- **Data:** 2026-10-02
- **Decisor:** Eduardo

## Contexto

A Fase 2b (branch `etapa/fase2b-estimador-empirico`; regra de decisão pré-registrada no commit `2c792a01`, antes da primeira execução) avaliou 3 362 casos (par de voltas × janela de curva), em 8 rodadas com uma sessão de fora por vez.

| Estimador | Skill | IC 95 % | Resultado |
|---|---|---|---|
| E1 simulador calibrado | −0,25 | [−0,35; −0,11] | reprovado |
| E2 ridge | −0,09 | [−0,11; +0,09] | reprovado |
| E3 KNN | +0,08 | [+0,06; +0,27] | reprovado: skill < 0,20 e viés de 36 % |
| E4 Processo Gaussiano | +0,11 | [+0,08; +0,29] | reprovado: skill < 0,20 e viés de 39 % |
| E2-teto (com velocidades) | +0,38 | [+0,31; +0,55] | passa, mas não é candidato |

- Sem as duas sessões dominantes, nenhum estimador bate prever zero de forma útil (E4: −0,61).
- Em 99 % dos pares, as duas voltas freiam a menos de 5 m uma da outra e passam a menos de 0,5 m no ápice.
- A variação de tempo entre voltas está na velocidade carregada, que é resultado da execução, não uma instrução de controle.

Interpretação: para aprender o efeito de mudar o ponto de frenagem ou a linha, os dados precisam conter voltas em que essas coisas mudaram de verdade. Nos dados atuais elas quase não mudam, então o efeito não pode ser identificado, com qualquer modelo. Os artigos que medem ganho real (BayesRace, Costa et al., identificação na pista) geram dados novos de propósito a cada rodada.

## Decisão

1. A Fase 2b é aceita como resultado negativo e incorporada a `develop` (tag `handoff/fase2b`).
2. O próximo passo científico é a **Fase 2c, experimento controlado no jogo**: variar de propósito o ponto de frenagem e a linha numa curva, em ordem sorteada, com voltas suficientes para separar o efeito do ruído. O protocolo está em `docs/experimentos/protocolo_sessao_controlada.md`.
3. O experimento também é o primeiro teste real dos estimadores: medir o efeito de verdade e comparar com o que E1 a E4 teriam previsto para as mesmas mudanças.
4. O sistema distingue dois tipos de recomendação:
   - **instruções de controle** (frear X m antes, mudar a linha): só ganham número de tempo depois de validadas pelo experimento;
   - **metas de resultado** (velocidade mínima ou de saída numa curva): podem vir das suas próprias voltas mais rápidas, sempre rotuladas como associação observada, nunca como garantia causal.

## Consequências

- O projeto passa a depender de uma sessão pilotada pelo Eduardo, de cerca de 40 voltas.
- O resultado negativo da Fase 2b vira um achado da monografia: com um piloto consistente, os dados do dia a dia não bastam para estimar o efeito de instruções de controle. É preciso desenhar o experimento.
