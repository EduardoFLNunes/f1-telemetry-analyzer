# 0022 — Validação da M1: como o modelo do carro para a frente é aprovado, e com que relógio

- **Status:** aceita
- **Data:** 2026-10-24
- **Decisor:** Eduardo
- **Complementa:** 0006 (protocolo de validação) e 0017 (modelo físico do carro, etapa M1)

## Contexto

1. **A M1 do ADR 0017** é o modelo do carro "para a frente": recebe o estado do carro agora e as entradas do piloto (volante, acelerador e freio) e devolve o estado depois de Δt. É uma física simples com uma correção aprendida dos dados (Kabzan et al. 2019; BayesRace 2021).
2. **O ADR 0006 foi escrito para estimadores de ganho de tempo:** a métrica é o erro na diferença de tempo, e a referência é "prever ganho zero". A M1 não estima ganho; ela prevê o movimento do carro. A métrica e a referência precisam ser outras. O próprio ADR 0006 manda registrar um ADR novo antes de rodar quando um critério muda.
3. **A coleta terminou:** a contagem oficial está em 5 de 5 sessões humanas com a guinada e as velocidades no referencial do carro (pedido 36, Parte A):
   - `2026-10-15_23-24-50`;
   - `2026-10-17_01-02-22`;
   - `2026-10-17_16-17-08`;
   - `2026-10-18_12-38-44`;
   - `2026-10-21_20-30-54`.
4. **O relógio das amostras estava pendente** (`docs/modelo_fisico_m0.md`, seção 6, pelo pedido 33):
   - o cronômetro do jogo anda em passos de física de 3 ms, e o tempo e a posição de cada amostra vêm do mesmo passo;
   - o horário do gravador se afasta do cronômetro (p99 de 7 a 14 ms, até 29 ms numa sessão);
   - de 1,5% a 5% das amostras são repetidas: o cronômetro não andou, mas a página de física mudou.

## Decisão

### 1. Os dados e o relógio

- **Só as 5 sessões da contagem oficial,** e dentro delas só as voltas válidas do store v2, cortadas pelas mesmas funções do store.
- **O relógio é o cronômetro do jogo.** O horário do gravador não entra em nenhuma conta.
- **As amostras repetidas são descartadas.**
- **Um trecho contínuo** termina num buraco de 50 ms ou mais. Nenhuma previsão atravessa um buraco.
- **Os dados são reamostrados num passo fixo de Δt** dentro de cada trecho. O valor de Δt é escolhido antes de treinar e registrado com o porquê.

### 2. A divisão

- **Uma sessão inteira fica de fora a cada rodada:** 5 rodadas.
- **Tudo o que é ajustado** (parâmetros da física, a correção aprendida e os seus hiperparâmetros, o corte de "fora dos dados") usa só as outras 4 sessões. A sessão de teste não escolhe nada.

### 3. As duas referências

- **R0, persistência:** o estado do carro fica igual durante o horizonte. É o equivalente de "prever ganho zero" do ADR 0006.
- **R1, só a física:** a física simples sem a correção aprendida, com os parâmetros ajustados nas 4 sessões de treino.

### 4. A métrica

- **A previsão é feita em malha aberta:** a partir de um instante, o modelo anda passo a passo com as entradas gravadas do piloto, sem olhar o estado gravado no caminho.
- **O erro principal** é o erro no estado do carro (velocidade longitudinal, velocidade lateral e guinada) **no horizonte de 0,5 s**. Cada grandeza é dividida pelo seu desvio-padrão nas sessões de treino, e o erro combinado é a raiz da média dos quadrados.
- **Skill** = 1 − erro do modelo ÷ erro da referência.
- **Também são relatados, sem entrar na aprovação:**
  - os horizontes de 0,25 s e 1,0 s;
  - o erro de posição em metros;
  - cada grandeza separada;
  - os resultados por sessão e por regime: freada, curva, tração e freio e volante juntos;
  - o resultado por faixa de velocidade.

### 5. Os critérios, fixados antes de rodar

Para aprovar a M1, todos precisam ser atendidos no horizonte de 0,5 s:

1. **skill contra R0 ≥ 0,50.** É a conferência de sanidade: se a física com a correção não bate a persistência com folga, os dados ou as convenções estão errados;
2. **skill contra R1 ≥ 0,20:** a correção aprendida tem de valer a pena;
3. **o limite inferior do IC 95 % do skill contra R1 > 0,** por bootstrap agrupado por volta;
4. **skill contra R1 positivo em pelo menos 4 das 5 sessões;**
5. **|viés| de cada grandeza ≤ 25 % do erro de R1;**
6. **a incerteza é honesta:** o intervalo de 90 % da correção aprendida cobre de 80 % a 97 % dos casos de teste, no passo de Δt;
7. **pelo menos 5 sessões testáveis.**

### 6. "Fora dos dados" é "não conclusivo"

- **O corte** é fixado nas sessões de treino: uma previsão cuja incerteza passa dele é marcada "não conclusivo", em vez de dar um número.
- **A fração** de casos "não conclusivo" no teste é relatada por regime. Ela não entra na aprovação, mas é o que impede o modelo de afirmar algo fora do que o piloto já fez.

## Consequências

- **Resultado negativo é aceito e documentado** (ADR 0006). Nenhum critério, corte ou hiperparâmetro é mudado depois de ver o teste. Mudar um critério exige um ADR novo, antes de rodar de novo.
- **Se a M1 passar,** ela vira a base da etapa M4 (peça D) e, depois, do cálculo do tempo de volta da busca evolutiva (ADR 0018). O ADR 0004 só é revisto com a M4, porque prever o movimento do carro não é o mesmo que estimar ganho de tempo.
- **Se só a física passar** (critério 1 sim, critério 2 não), a física simples fica como o modelo do carro, e a correção aprendida volta para quando houver mais sessões.
- **O tempo de volta não é avaliado aqui.** Uma volta inteira em malha aberta diverge. Prever tempo de volta precisa de um piloto que siga a linha (etapas M3 e M4).
- **O relógio decidido aqui** fecha a pendência da seção 6 de `docs/modelo_fisico_m0.md`.
