# Pedido 48 — Diagnóstico da M1 v2: onde ela erra e por quê (só análise)

**De:** Eduardo. **Data:** 09/11/2026.
**Tipo:** análise e documentação (`backend/ml/scripts/`, `tests/`, `docs/`). **Nenhum modelo novo é ajustado, e nenhum veredito muda.** O coach, o rádio, o app, o store v2, a M1 v2, o Modelo 1 e o Modelo 2 não mudam.

**Quando começar: agora, numa pasta separada.** A pasta principal (`C:\Users\Dokas\Desktop\f1-telemetry-analyzer`) fica na branch do pedido 45, e a do 47 (`f1-telemetry-analyzer-47`) fica na branch dele, esperando as minhas sessões no jogo. **Nenhuma das duas troca de branch por causa deste pedido, e nenhuma das duas é tocada,** salvo o item 0.2.

### Parte 0 — A pasta separada

1. **Crie a pasta com `git worktree`,** a partir da principal, sem trocar a branch dela:
   ```powershell
   git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer worktree add C:\Users\Dokas\Desktop\f1-telemetry-analyzer-48 -b etapa/diagnostico-m1 develop
   ```
   Todo o trabalho deste pedido acontece em `f1-telemetry-analyzer-48`. Confira que `develop` tem o merge do pedido 46 (o ADR 0028 com a seção "Resultado").
2. **O texto deste pedido** está sem commit na pasta principal. Copie-o para a pasta separada e faça dele o primeiro commit da branch. Depois de conferir que os dois são iguais (sha256), apague a cópia da pasta principal, e só ela.
3. **Os imports e os dados,** como no pedido 47 (Parte 0 do relatório dele):
   - o `.venv` da principal, rodando de dentro de `f1-telemetry-analyzer-48\backend`, com `core.__file__` e `ml.__file__` conferidos na pasta separada;
   - junções de pasta, só para leitura, para `data\recordings`, `data\ml` e `data\cache` da principal. A sessão de `2026-10-17_16-17-08` fica na pasta do app instalado e também só é lida;
   - **nada é escrito através de uma junção.** O que este pedido gera vai para `data\diagnostico_m1\`, uma pasta de verdade na pasta separada, fora dos commits (confira o `.gitignore`). Tire uma foto dos arquivos de `data\ml` da principal (nome, tamanho, data) antes e compare no fim.
4. **O processador:** antes de cada conta pesada, confira se o jogo (`acs.exe`) está aberto. Se estiver, espere: são as minhas sessões do pedido 47.
5. **A regra das pastas separadas** está no ADR 0008 da branch do 47, ainda sem merge. Não a escreva de novo aqui, para não dar conflito.
6. **Relate** o comando, como os imports e os dados foram resolvidos e o que foi apagado na principal.

## Contexto

1. **O resultado da M1 v2** (pedido 46; ADR 0028; `docs/modelo_fisico_m1.md`, seções 7.2 e 7.3):
   - **o critério 1 não passou por pouco:** skill de 0,487 contra a persistência (R0) em 0,5 s, e ele pede 0,50. Os critérios 2 a 7 passaram (0,207 contra a física v2);
   - **por regime:** reta 0,68, freada 0,71, tração 0,73; **curva 0,46** (25.251 dos 39.142 casos, 65%); freio e volante juntos 0,45;
   - **por velocidade:** 0,44 abaixo de 100 km/h, 0,49 de 100 a 160, 0,49 de 160 a 220 e 0,58 acima de 220;
   - **por sessão:** de 0,41 (21/10) a 0,55 (17/10 16:17). Fora do teste (C.4): 0,41 e 0,42 em 24/10 e **0,12 em 01/11**, onde a persistência prevê `vy` melhor que a M1 v2;
   - **a C10:** a 76 km/h e com o volante em 0,87, `vy` sai 0,62 m/s acima do gravado em 0,5 s e 1,4 m/s em 1,0 s; a v2 também exagera a guinada;
   - **o pneu:** `q`, `α_pico` e `f` no limite da faixa nas 5 rodadas. Os dados quase não passam de 6° de deriva, e o pico foi para 12°, fora deles;
   - **a carga:** erro de 18% a 24% contra `wheel_load_*` (26% a 28% na dianteira esquerda nas curvas); `h_y` de 19% a 34% acima do `cgHeight`; a massa das regressões, de 578 a 653 kg, abaixo da faixa de 700 a 900 kg escrita na seção 1.4.
2. **O ADR 0028, item 1, continua valendo:** a v2 foi a última tentativa nas mesmas sessões de teste, e o veredito não muda. **A minha decisão de 09/11:** este pedido só explica por que a v2 não passou. Os dados de manobra e um modelo novo ficam como trabalhos futuros na monografia. Uma v3 só existe se sobrar tempo depois do pedido 42, num pedido próprio, com sessões de teste novas que ela não tenha visto.
3. **O carro** (`rss_formula_rss_3_v6_2026`) é da classe F3, com física do CSP e DRS, pela página da loja. Um F3 real (Dallara F3 2025) pesa 673 kg com o piloto. Pelas discussões públicas de modding, o pneu do Assetto Corsa tem um comprimento de relaxação (`RELAXATION_LENGTH`), a carga de referência e a sensibilidade (`FZ0`, `LS_EXPY`), o ângulo do limite (`FRICTION_LIMIT_ANGLE`) e a queda (`FALLOFF_LEVEL`, `FALLOFF_SPEED`). **Os arquivos do carro não são abertos.**
4. **A sessão de 01/11** (`2026-11-01_19-47-03`) é a primeira no CSP 0.3.1. As saídas de traseira que eu senti, pela numeração do meu relato (pedido 42, contexto, item 7):
   - volta 3: a C05, a C06 e a C13, a caminho dos boxes;
   - volta 4: a saída do S do Senna e a C06, logo depois dos boxes (o relatório do 45 marcou a saída do S como C01);
   - volta 10: a C05;
   - volta 11: a C01, na freada forte.

   No `session-index.json`, as voltas 3, 4, 10 e 11 têm 4:45,743, 3:44,219, 2:25,948 e 2:39,678. São voltas inválidas.
5. **A literatura** (cite como está aqui, sem inventar referências):
   - Kabzan, Hewing, Liniger e Zeilinger (2019), "Learning-Based Model Predictive Control for Autonomous Racing", IEEE RA-L, https://doi.org/10.1109/LRA.2019.2926677: Processo Gaussiano no resíduo de `vx`, `vy` e `r` de um modelo físico, a mesma estrutura da M1;
   - Jain et al. (2020), "BayesRace: Learning to race autonomously using prior experience", CoRL, https://arxiv.org/abs/2005.04755: correção por Processo Gaussiano de um modelo físico, com dados de pista;
   - Spielberg et al. (2019), "Neural network vehicle models for high-performance automated driving", Science Robotics, https://doi.org/10.1126/scirobotics.aaw1975: uma rede com o histórico dos estados (alguns passos), no limite de aderência;
   - Chrosniak et al. (2024), "Deep Dynamics: Vehicle Dynamics Modeling with a Physics-Constrained Neural Network for Autonomous Racing", https://arxiv.org/abs/2312.04374: histórico de estados e entradas, parâmetros físicos presos em faixas (a guarda física);
   - "Fine-Tuning Hybrid Physics-Informed Neural Networks for Vehicle Dynamics Model Estimation" (2024), https://arxiv.org/abs/2409.19647;
   - "Learning-Based On-Track System Identification for Scaled Autonomous Racing in Under a Minute" (2024), https://arxiv.org/abs/2411.17508: com poucos dados, os modelos divergem fora da faixa de deriva vista;
   - "Bayesian Optimization-based Tire Parameter and Uncertainty Estimation for Real-World Data" (2025), https://arxiv.org/abs/2504.20863: os parâmetros do pico do pneu só ficam bem estimados com dados que chegam perto dele;
   - "Short-Horizon Position Accuracy of Single-Track Models: Implications for Motion Planning of Autonomous Vehicles" (2026), https://arxiv.org/abs/2606.14216: o modelo de pneu não linear ficou pior que o linear, pela incerteza da identificação e pela complacência da direção;
   - Lambert, Pister e Calandra (2022), "Investigating Compounding Prediction Errors in Learned Dynamics Models", https://arxiv.org/abs/2203.09637: o erro de um passo se acumula no horizonte;
   - "Learning with Imperfect Models: When Multi-step Prediction Mitigates Compounding Error" (2025), https://arxiv.org/abs/2504.01766: com um modelo mal especificado, o ajuste em vários passos reduz o viés no horizonte;
   - Pacejka, "Tire and Vehicle Dynamics" (livro): o comprimento de relaxação (a força lateral cresce depois de o pneu rodar uma distância);
   - Clemson, grupo de B. Ayalew, "On the Frequency Domain Analysis of Tire Relaxation Effects on Transient On-Center Vehicle Handling Performance": o efeito da relaxação na resposta transitória.

## Parte A — Registrar antes de calcular

Escreva a **seção 7.5, "Diagnóstico da M1 v2 (pedido 48)"**, em `docs/modelo_fisico_m1.md`, e commite-a **antes de qualquer conta nas sessões** (a reprodução da Parte B inclusive). Ela tem:

1. **As hipóteses, as evidências e as regras abaixo,** copiadas com as faixas e os limites. As regras dão a cada hipótese um de três rótulos: **apoiada, não apoiada ou inconclusiva.** Nenhuma regra muda depois de ver os números.
2. **As definições comuns:**
   - **os modelos e os casos são os do pedido 46:** as 5 rodadas, os 39.142 casos, as 3 grandezas normalizadas e o erro combinado da seção 1.7;
   - **a deriva estimada** de cada roda vem do estado gravado e da geometria medida, pela fórmula do ADR 0028, item 3 (`α_i = δ_i − atan2(vy + x_i·r, vx − y_i·r)`), e não do modelo do pneu. A deriva de um eixo é a média das duas rodas;
   - **as faixas:** de velocidade, as da seção 7.3; de |`steer`|, 0 a 0,1, 0,1 a 0,2, 0,2 a 0,4, 0,4 a 0,6 e acima de 0,6; de deriva, abaixo de 3°, 3° a 6°, 6° a 8°, 8° a 10° e acima de 10°; de |`a_y`|, 0,5 a 1,0 g, 1,0 a 1,5, 1,5 a 2,0 e acima de 2,0; da taxa do volante, os tercis dos passos de treino;
   - **as curvas e as fases:** as curvas C01 a C14 da geometria do store v2; a entrada vai do início da curva ao ápice, e a saída, do ápice ao fim;
   - **a parte de um grupo no erro:** a soma do erro quadrático normalizado dos casos do grupo, dividida pela soma de todos os casos. As partes somam 100%.
3. **O que se espera,** escrito antes de calcular, com o porquê.

**As hipóteses:**

| | hipótese | evidência (Parte C) | apoiada | não apoiada |
|---|---|---|---|---|
| H1 | **o pico do pneu:** os casos com deriva alta concentram o erro das curvas | C.2, C.6 | o skill acima de 6° fica pelo menos 0,15 abaixo do skill abaixo de 3°, e as faixas acima de 6° têm pelo menos 15% do erro das curvas | a diferença fica abaixo de 0,05 |
| H2 | **a relaxação do pneu:** o carro do jogo responde ao volante com um atraso que a física não tem | C.3 | o atraso a mais tem o IC 95% acima de +10 ms em pelo menos 3 das 4 faixas de velocidade, e o produto do atraso a mais pela velocidade fica a até ±35% da mediana dele nessas faixas | o atraso a mais fica abaixo de 10 ms em todas as faixas |
| H3 | **a direção:** o ângulo da roda não é linear no volante (Ackermann, complacência), e isso erra com muito volante | C.4 | o ganho efetivo com \|`steer`\| ≥ 0,4 difere pelo menos 15% do ganho com \|`steer`\| < 0,2, e o erro de `r` em 0,5 s com \|`steer`\| ≥ 0,4 fica pelo menos 1,5 vez a mediana das curvas | a diferença fica abaixo de 5% |
| H4 | **a carga:** a aerodinâmica muda com a altura do carro (e com o DRS), e o modelo de carga não tem isso | C.5 | a altura e a velocidade explicam pelo menos 30% da variância do resíduo da carga de cada eixo, e o skill no quartil de maior erro de carga fica pelo menos 0,10 abaixo do quartil de menor | menos de 10% e diferença abaixo de 0,05 |
| H5 | **o acúmulo no horizonte:** o ajuste mira um passo, e o erro cresce ao realimentar o próprio estado | C.7 | a razão de acúmulo nas curvas é pelo menos 1,3 | a razão fica até 1,1 |
| H6 | **a correção sem memória:** o resíduo depende do que aconteceu antes, e o Processo Gaussiano só vê o passo atual | C.7 | a autocorrelação do resíduo de um passo no atraso 1 é pelo menos 0,5 em `vy` ou em `r`, nas curvas | fica até 0,2 nas duas |
| H7a | **01/11, a pilotagem:** a queda vem de mais escorregamento | C.8 | nos casos com deriva abaixo de 3°, o skill de 01/11 fica a até 0,10 do de 24/10 nos mesmos casos | o H7b é apoiado |
| H7b | **01/11, o carro ou o jogo mudou** (CSP 0.3.1 ou outra condição) | C.8 | nesses casos, o skill de 01/11 fica mais de 0,20 abaixo do de 24/10 | o H7a é apoiado |

O que não for nem "apoiada" nem "não apoiada" é **inconclusiva.** Uma hipótese sem dados (um canal não gravado) é "sem dados", com o motivo.

## Parte B — Os dados e a reprodução

1. **As previsões caso a caso.** Se o pedido 46 guardou a previsão de cada caso, use-a. Se não guardou, refaça a fase de teste num script novo (`ml/scripts/m1_diagnostico.py`), que importa as funções do 46 sem mudá-las:
   - com os parâmetros da física de cada rodada lidos do JSON da fase de treino do 46, e os Processos Gaussianos lidos de onde o 46 os salvou;
   - se eles não foram salvos, reajustados com o mesmo commit, a mesma amostra e a semente 46.
2. **A conferência:** os números da seção 7.3 têm de se repetir: o skill do critério 1 (0,487), o do critério 2 (0,207), os erros combinados dos horizontes e os skills por regime, por sessão e por faixa. **Até 0,002 de diferença,** siga e relate. **Acima disso, pare** e relate a diferença.
3. **Guarde, por caso,** em `data/diagnostico_m1/casos.parquet`: a rodada, a sessão, a volta, o instante, a curva e a fase, o estado e as entradas no início, a deriva estimada de cada roda, a carga gravada e a prevista, `rideHeight`, `wheelSlip`, os erros normalizados de cada grandeza em 1, 2, 5, 10 e 20 passos (M1 v2, física v2 e R0) e o índice do "não conclusivo".
4. **Nada da M1 v2 é reescrito:** os arquivos com o sufixo `_v2` ficam como estão.

## Parte C — As análises

Todas usam os modelos do 46, sem mudança. **Nenhuma previsão de um modelo novo ou mudado é relatada como skill.**

1. **O acaso perto do limite.** O IC 95% do skill do critério 1, por bootstrap agrupado por volta (10.000 reamostragens, semente 48, percentis 2,5 e 97,5): no geral, por sessão e só nas curvas. Diga se 0,50 está dentro do intervalo. **Isso não muda o veredito:** o critério é o valor pontual (ADR 0022).
2. **Onde está o erro das curvas** (e de freio e volante juntos), em 0,5 s: o skill e a parte no erro por faixa de |`steer`|, de velocidade, de |`a_y`|, de deriva estimada (dianteira e traseira), de taxa do volante, por curva (C01 a C14), por fase e por grandeza (`vx`, `vy`, `r`). E a conta: **com o resto igual, que skill as curvas precisariam ter para o total chegar a 0,50?**
3. **O atraso do volante para a guinada.** Nas entradas de curva (o |`steer`| passa de 0,1 e sobe por pelo menos 0,2 s), por faixa de velocidade:
   - o atraso que maximiza a correlação entre a taxa do volante e a taxa da guinada, de −0,1 a +0,4 s, nas amostras cruas (nos trechos com intervalos de até 20 ms, reamostrados a 5 ms), com o pico refinado por parábola;
   - o mesmo com a guinada prevista pela física v2 e pela M1 v2 em malha aberta, a partir de 0,5 s antes da entrada, com o volante gravado. Leve em conta que a entrada de cada passo é a média de `k` e `k+1` (seção 1.2);
   - o atraso a mais (gravado menos física v2), com IC 95% por bootstrap por volta (2.000 reamostragens, semente 48), e o produto dele pela velocidade, que seria o comprimento de relaxação.
4. **A direção com muito volante.** Nas amostras quase estacionárias das sessões de treino (|`dr/dt`| < 0,1 rad/s², taxa do volante no tercil de baixo, `vx` ≥ 10 m/s), por faixa de velocidade: a regressão `L·r/vx = k_ef·(−steer) − K·a_y`, com um `k_ef` por faixa de |`steer`| e um `K` comum. Compare cada `k_ef` com `k_δ = 0,304` e use só as faixas com pelo menos 200 amostras. Relate também o erro de `r` em 0,5 s por faixa de |`steer`|.
5. **A carga.**
   - O resíduo da carga prevista de cada eixo (a conta da seção 7.2, com `vx`, `a_x` e `a_y` gravados) contra `rideHeight` (frente e trás), a velocidade e o `suspensionTravel`, por regressão linear com os termos `rideHeight_f`, `rideHeight_r`, `vx²`, `vx²·rideHeight_f` e `vx²·rideHeight_r`. Relate o R².
   - O DRS, se a gravação tiver o campo. Se não tiver, "não gravado".
   - A massa pela soma das cargas com `vx` < 15 m/s e \|`a_x`\| e \|`a_y`\| < 0,1 g, por sessão, ao lado das regressões da v1 (578 a 653 kg) e do F3 real (673 kg). O combustível, se gravado.
   - O skill por quartil do erro de carga no início do caso.
6. **A cobertura do pneu.**
   - A fração dos passos com deriva estimada acima de 6°, 8° e 10° (cada eixo) nas sessões de treino, nas de teste, em 24/10 e em 01/11.
   - O `wheelSlip` gravado contra a deriva estimada e contra a força lateral por carga (`a_y` e as cargas gravadas). O que o `wheelSlip` mede não está documentado: relate a relação, e diga se a força por carga para de crescer em algum valor dele. Não conclua o significado sem fonte.
7. **O acúmulo e a memória.**
   - **A razão de acúmulo:** o erro em 0,5 s em malha aberta, dividido pelo erro em 0,5 s somando os incrementos de um passo previstos a partir do estado gravado em cada passo (o mesmo modelo, sem realimentar o próprio estado). Na M1 v2 e na física v2, por regime.
   - O skill em 1, 2, 5, 10 e 20 passos, por regime.
   - **A memória:** a autocorrelação do resíduo de um passo da M1 v2, nas curvas, nos atrasos de 1 a 10 passos, para cada grandeza, e a correlação parcial dele com a taxa do volante dos 0,1 a 0,3 s anteriores. A interpolação para a grade de 50 ms também cria autocorrelação: meça a do mesmo resíduo na reta, como comparação.
8. **01/11 e as saídas de traseira.**
   - **A sessão,** com os modelos da rodada sem 21/10 (como na C.4): a cobertura (C.6), o skill por faixa de deriva ao lado de 24/10, a fração "não conclusivo", a temperatura média dos pneus e a versão do CSP de cada sessão, se a gravação a tiver. Se não tiver, use a minha informação (01/11 é a primeira no 0.3.1) e escreva "não registrada" para as outras.
   - **Os 7 episódios,** das amostras cruas pelo `iter_laps`, sem o filtro de volta válida. As voltas são achadas pelos tempos do contexto, item 4.
     - O pico de cada episódio é a amostra de maior |`atan2(vy, vx)`| dentro da curva citada, estendida 50 m depois do fim dela.
     - Rode os casos que começam 1,0, 0,5 e 0,25 s antes do pico, com a M1 v2, a física v2 e R0.
     - Relate: `vy` e `r` previstos e gravados até o pico, a deriva estimada e o `wheelSlip` no pico, e se o caso de início seria marcado "não conclusivo".
     - **O modelo acompanha a escapada** se, no caso de 0,5 s, a variação prevista de `vy` até o pico tiver o mesmo sinal da gravada e pelo menos metade do tamanho dela. Conte em quantos dos 7 isso acontece.
9. **O que o jogo expõe.** A deriva, a razão de escorregamento e as forças de cada pneu existem na memória compartilhada ou na API do CSP? O gravador grava algum deles?
   - Use as fontes públicas (cite os links), o retrato da memória compartilhada que o repositório já tem (`data/debug/ac_shared_memory_full_inventory.json`), o adaptador e o código do app do jogo.
   - A pasta do jogo não é aberta, e o gravador e o app não mudam. Diga o que um pedido futuro teria de mudar para gravar esses canais.

## Parte D — O quadro e os trabalhos futuros

1. **O quadro das causas:** uma linha por hipótese, com o número que decidiu, o rótulo e a figura.
2. **A ordem:** pela parte do erro das curvas que cada causa apoiada explica, quando der para medir. As causas se sobrepõem (a C10 tem volante alto, deriva alta e velocidade baixa juntos): diga onde elas se misturam, e não some as partes.
3. **Os trabalhos futuros,** com as citações do contexto, item 5, ligados às hipóteses:
   - **dados de manobra,** numa sessão própria: um círculo de raio constante com a velocidade subindo devagar (a curva do pneu até o pico e o subesterço), uma rampa de volante a velocidade constante (o ganho da direção) e um seno de volante em 3 ou 4 velocidades (o atraso e a relaxação). Diga o que cada um identifica e quantas voltas pediria;
   - **um modelo novo,** se houver tempo depois do 42, testado em sessões novas: o ajuste em vários passos, a direção não linear, a relaxação do pneu, a carga com a altura e o DRS, e a correção com o histórico e a guarda física. Só os itens com hipótese apoiada entram como prioridade; os outros entram como "a testar".
4. **Para quem não é da área:** um parágrafo, como na seção 7.3.

## Parte E — Testes

Em `tests/`, com dados sintéticos:

- o bootstrap agrupado por volta (um caso com IC conhecido);
- a deriva estimada de cada roda, numa curva sintética em regime permanente, com os sinais da convenção do modelo;
- o atraso: um sistema de primeira ordem com comprimento de relaxação conhecido, em 3 velocidades. O estimador acha o atraso (`σ/v`) com erro de até 5 ms;
- a regressão do ganho da direção acha um ganho não linear conhecido;
- as partes do erro somam 100%, e o skill que as curvas precisariam bate com uma conta à mão;
- a razão de acúmulo vale 1 num modelo sem realimentação;
- a localização do pico de um episódio.

A suíte do backend continua passando.

## Parte F — Documentação

- **`docs/modelo_fisico_m1.md`, seção 7.5:** o registro (Parte A), o resultado (Partes C e D), as figuras e os trabalhos futuros.
- **As figuras,** em `docs/handoff/2026-11-09_48_diagnostico-da-m1-v2_*.png`:
  - a parte do erro das curvas por |`steer`| e velocidade (mapa de calor);
  - a distribuição da deriva estimada, com as marcas de 6° e de 12° (o `α_pico` ajustado);
  - o atraso por velocidade (gravado, física v2 e M1 v2), com o produto pela velocidade;
  - o `wheelSlip` contra a deriva estimada e a força lateral por carga;
  - os 7 episódios de 01/11, um quadro cada (`vy` e `r`).
- **O JSON** com todos os números: `docs/handoff/2026-11-09_48_diagnostico-da-m1-v2.json`.
- **ADR 0028:** uma linha de atualização: "diagnóstico no pedido 48, seção 7.5 da M1; o veredito não muda".
- **`docs/arquitetura_ml.md`:** uma linha na parte da M1, apontando para a seção 7.5.
- **`docs/backlog.md`:** não edite; liste os itens no relatório.

## Regras gerais

- **Só análise.** Nenhum modelo novo, nenhum parâmetro reajustado para melhorar, nenhuma "v3 escondida". Variantes de modelo não são rodadas, nem "só para ver".
- **Nenhum critério muda,** e o veredito da M1 v2 fica como está. As regras da Parte A são commitadas antes das contas.
- **Não invente resultados.** Um canal não gravado é "não gravado"; uma hipótese sem dados é "sem dados".
- **Os arquivos do carro e o `data.acd` nunca são abertos.** A pasta do jogo não é tocada.
- **As gravações só são lidas.** Não apague, não mova e não copie nenhuma, nem entre a pasta do app instalado e o repositório.
- **Não instale nem atualize pacotes.** Se algo pedir pacote novo, pare e relate.
- **Não contorne nenhuma trava:** se algo parar, pare também e registre o motivo.
- **Branch e commits:** `etapa/diagnostico-m1`, a partir de `develop`, na pasta separada; o texto deste pedido é o primeiro commit; a Parte A antes das contas; commits por parte.
- **O merge, depois da Parte F, na pasta separada:**
  - se `develop` tiver andado (por exemplo, com o merge do 45 ou do 47), traga `develop` para a branch antes, resolvendo os conflitos simples (como as linhas de atualização);
  - se `develop` estiver aberta em outra pasta, pare e me avise: uma branch só pode estar aberta numa pasta;
  - depois do merge e do envio, volte a pasta separada para a branch do pedido;
  - não apague a pasta separada: eu decido quando.
- **A pasta principal, a pasta do 47 e as branches de outros pedidos não são tocadas,** salvo o item 0.2.
- **Cópia no GitHub (vale para todo pedido):**
  - depois dos commits de cada parte, envie a branch do pedido ao `origin`; depois do merge, envie `develop`;
  - só envios que não reescrevem o remoto (branch nova ou avanço simples). Nunca `--force` nem `--force-with-lease`;
  - `main` e as tags não vão neste pedido;
  - antes do primeiro envio, confira que nada acima de 50 MB, nenhum segredo, nenhuma gravação (`recordings/`, `data/recordings`, `data/ml`) e nada de `data/diagnostico_m1` entrou nos commits;
  - depois de cada envio, confira com `git ls-remote origin` que o hash remoto é o mesmo do local;
  - se o controle de permissões da sessão recusar o envio, deixe no relatório os comandos para eu rodar pelo terminal;
  - se pedir login, se o envio for recusado pelo GitHub ou se o remoto tiver divergido, pare e me avise. Nenhum token ou senha no chat, nos arquivos ou no relatório.
- **Nomes técnicos** nos textos, sem apelidos. **Os tempos de volta** no formato M:SS,mmm.
- **Relatório** em `docs/handoff/2026-11-09_48_diagnostico-da-m1-v2_relatorio.md`, na pasta separada, com:
  - a Parte 0: a pasta, os imports, os dados, o que foi apagado na principal e a comparação da foto de `data\ml`;
  - o commit da Parte A;
  - a reprodução (Parte B): de onde vieram os modelos e as diferenças;
  - cada análise da Parte C, o quadro e os trabalhos futuros (Parte D);
  - a saída dos testes e os commits;
  - o que foi enviado ao GitHub: a ref, o hash local e o hash no remoto;
  - os itens para o backlog.
- Se algo do contexto não bater com o repositório, pare e registre no relatório.
