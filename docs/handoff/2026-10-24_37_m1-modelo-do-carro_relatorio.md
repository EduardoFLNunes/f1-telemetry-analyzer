# Relatório do pedido 37 — M1: o primeiro modelo do carro para a frente

- **Pedido:** `docs/prompts/2026-10-24_37_m1-modelo-do-carro.md`
- **Continuação:** o pedido 39 retoma este pedido com a geometria medida pela telemetria do jogo (ADR 0024): `docs/handoff/2026-10-25_39_m1-geometria-medida_relatorio.md`.
- **Situação:** **parado na Parte C**, antes de qualquer previsão na sessão de teste. A regra registrada na Parte A para o entre-eixos e a unidade do volante não funciona com os dados, e mudá-la é decisão do Eduardo (Parte A.3). Nenhum número de teste foi calculado.
- **Branch:** `etapa/m1-modelo-do-carro`, a partir de `develop` (`4782aefb`). **Sem merge em `develop`** (o pedido parou no meio). Sem push.
- **Commits:**
  - `35b5c020` docs: pedido 37 (M1: o primeiro modelo do carro para a frente, fisica simples e correcao aprendida)
  - `e0a62949` Pedido 37, Parte A: o ADR 0022 e a M1 registrada antes de construir
  - `7bf5f565` Pedido 37, Parte B: os dados da M1 no cronometro do jogo e as conferencias de convencao
  - `4dab48c8` Pedido 37, Parte C, parado: a regra registrada para o entre-eixos nao identifica
- **Arquivos de handoff** (`docs/handoff/`):
  - `2026-10-24_37_m1-modelo-do-carro_relatorio.md` (este)
  - `2026-10-24_37_m1-modelo-do-carro_resultados.json` (ADR 0007: commit, `geometry_id`, ambiente, comandos, hashes)
  - `2026-10-24_37_m1-modelo-do-carro_dados.json` (Parte B: por sessão e por volta)
  - `2026-10-24_37_m1-modelo-do-carro_convencoes.json` (Parte B.3)
  - `2026-10-24_37_m1-modelo-do-carro_geometria_por_rodada.py` e `.json` (a regra registrada nas 5 rodadas)
  - `2026-10-24_37_m1-modelo-do-carro_sanidade_treino.py` e `.txt` (a física registrada, só no treino da rodada 1)
  - `2026-10-24_37_m1-modelo-do-carro_diagnostico_geometria.py` e `.txt` (o porquê, e `L` e `k_δ` ajustados junto)
  - `2026-10-24_37_m1-modelo-do-carro_opcao_b_por_rodada.py` e `.txt` (a regressão com a deriva dividida pela carga)
  - `2026-10-24_37_m1-modelo-do-carro_pytest.txt` (a suíte do backend)

## Resumo

1. **Parte A feita e commitada antes de qualquer ajuste** (`e0a62949`): o ADR 0022 em `docs/decisoes/`, a linha no índice, o anexo apagado, e a seção 1 de `docs/modelo_fisico_m1.md` com os dados, o relógio (cronômetro do jogo, **Δt = 50 ms**), o estado e as entradas com os sinais, a física e os parâmetros com as faixas, a correção, o corte de "não conclusivo", os critérios e o que se espera.
2. **Parte B feita** (`7bf5f565`): as 57 voltas válidas das 5 sessões, com o corte do store conferido volta a volta, 8.849 amostras repetidas descartadas, 1.627 buracos, **102.250 passos de 50 ms** (84 minutos de dados). **As 5 conferências de convenção batem**, com um ponto para você confirmar (abaixo).
3. **Parte C parada.** A regra registrada para `b` (centro de massa ao eixo traseiro), `L` (entre-eixos) e `k_δ` (unidade do volante) dá `L` negativo ou menor que 1,1 m nas 5 rodadas. Com isso a física fica pior que a persistência já nas sessões de treino. Diagnostiquei a causa e testei duas alternativas, só nas sessões de treino; nenhuma foi adotada.
4. **Pronto, mas não rodado na sessão de teste:** o código da física, da correção (Processo Gaussiano), da malha aberta e das métricas, com os testes do pedido. Depois da sua decisão, falta rodar as Partes C a E e escrever a Parte F.

## Parte A — registrado antes de construir

- **Commit:** `e0a62949`, antes de qualquer leitura de dados para ajuste.
- **Conteúdo:** `docs/modelo_fisico_m1.md`, seção 1. Os pontos que não estavam no pedido e que eu fixei ali:
  - **Δt = 50 ms:** igual ao corte de buraco, então todo intervalo de Δt num trecho tem uma amostra real; os horizontes ficam em 5, 10 e 20 passos;
  - **a entrada de cada passo** é a média das entradas gravadas em `k` e `k+1`;
  - **uma rigidez de deriva só** (`Cα`, por unidade de carga) para os dois eixos: a diferença entre eles entra pela carga de cada eixo;
  - **a transferência de carga** entra se reduzir o erro de um passo no treino em pelo menos 2%;
  - **a massa, a carga aerodinâmica, `w_f`, `f_aero` e `h/L`** medidos nas cargas das rodas; **`b`, `L` e `k_δ`** por regressões cinemáticas em |a_y| ≤ 0,5 g (é esta regra que falhou);
  - **o subconjunto do Processo Gaussiano:** 2.000 passos, 400 por regime, semente 37;
  - **o índice de "fora dos dados"** e o corte no percentil 99 dos casos de treino;
  - **as métricas da aprovação usam todos os casos**, conclusivos ou não;
  - **o que se espera:** a física bate a persistência com folga, e a correção melhora pouco sobre ela, perto do limite de 0,20.

## Parte B — os dados

Comando: `python -m ml.scripts.m1_modelo_carro dados` (1 min 40 s para as 5 sessões).

- **As gravações não mudaram:** o sha256 de cada `player.jsonl` é o registrado no meta do store v2.
- **O corte é o do store:** o número de amostras cruas de cada uma das 57 voltas bate com o `raw_samples` do meta.
- **A sessão `2026-10-17_16-17-08`** está na pasta do app instalado (`%APPDATA%\Automobilista Telemetria\data\recordings`), não em `data/recordings`. O `ml` lê as duas pastas, como desde o ADR 0014.

| sessão | voltas | amostras cruas | tiradas na limpeza | repetidas | buracos ≥ 50 ms | trechos | trechos curtos tirados | passos de 50 ms | segundos |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `2026-10-15_23-24-50` | 11 | 57.929 | 49 | 845 (1,5%) | 167 | 162 | 16 | 19.856 | 985 |
| `2026-10-17_01-02-22` | 12 | 63.486 | 94 | 879 (1,4%) | 170 | 163 | 19 | 21.751 | 1.079 |
| `2026-10-17_16-17-08` | 16 | 85.788 | 97 | 4.392 (5,1%) | 659 | 458 | 217 | 28.804 | 1.417 |
| `2026-10-18_12-38-44` | 9 | 46.161 | 95 | 1.890 (4,1%) | 383 | 331 | 61 | 15.943 | 781 |
| `2026-10-21_20-30-54` | 9 | 46.251 | 64 | 843 (1,8%) | 248 | 237 | 20 | 15.896 | 783 |
| **total** | **57** | **299.615** | **399** | **8.849** | **1.627** | **1.351** | **333** | **102.250** | **5.045** |

- **Por que cada descarte:**
  - **tiradas na limpeza:** as do `clean_lap` do store (horário do gravador repetido);
  - **repetidas:** o cronômetro do jogo não andou;
  - **trechos curtos:** menos de 2 pontos entre dois buracos.
- **A sessão do pacote 0.4.0** (17/10 16:17) tem 41 buracos por volta, contra cerca de 15 nas outras, e perde 217 trechos curtos.
- **Faixas (p1 / p50 / p99):** `vx` 19 / 46 / 74 m/s; `vy` −4,6 / −0,23 / 5,0 m/s; guinada −0,85 / 0,08 / 0,75 rad/s; volante −0,47 / −0,01 / 0,47; `brakeBias` sempre 0,55; temperatura média dos pneus 31 / 63 a 82 / 93 °C (varia por sessão). Todos os canais 100% preenchidos.
- **Onde fica:** `data/ml/modelo_carro/grade_<sessão>.parquet` e `dados_relatorio.json`, fora do git; hashes no `resultados.json`.

### As conferências de convenção

Comando: `python -m ml.scripts.m1_modelo_carro convencoes`. **Todas batem, com a mesma convenção nas 5 sessões.**

| conferência | inclinação | correlação | esquerda / direita | resultado |
|---|---:|---:|---|---|
| aceleração lateral contra `vx` × guinada gravada | 0,972 | 0,985 | 0,977 / 0,989 (correlação 0,907 / 0,884) | bate; a guinada gravada já é positiva para a esquerda |
| derivada do `heading` contra a guinada gravada | −0,999 | −0,999 | −1,001 / −1,000 | bate; o `heading` diminui girando para a esquerda |
| `localVelocity.x` contra a velocidade do mundo para a esquerda | 0,998 | 0,99998 | 0,997 / 1,000 | bate; `localVelocity.x` já é positiva para a esquerda |
| `localVelocity.z` contra a velocidade do mundo para a frente | 1,001 | 0,99999 | 1,001 / 1,001 | bate; contra `speedKmh / 3,6`, inclinação 1,000 |
| volante: o sinal de `−steer` é o da guinada, com \|a_y\| ≥ 0,5 g | — | — | 99,8% / 99,5% (99,2% no geral) | bate |

- **A direção do carro no mundo** é `(−sen h, cos h)` no plano (x, z); a esquerda é `(cos h, sen h)`.
- **A aceleração lateral positiva para a esquerda** (M0) confere com a geometria em 99,3% (curvas à esquerda) e 99,9% (à direita) dos pontos com |a_y| ≥ 0,5 g.
- **A velocidade lateral numa curva à esquerda e numa à direita:** negativa nas curvas à esquerda (C01: mediana −0,83 m/s a 105 km/h) e positiva nas à direita (C10: +0,30 m/s a 83 km/h). O carro aponta para dentro e o centro anda para fora em todas as 14 curvas, até nas lentas.

**Ponto para você confirmar: a correlação dentro de cada lado.** Na guinada, a correlação só dentro das curvas à esquerda (0,907) e só dentro das à direita (0,884) fica abaixo de 0,95.

- **O texto registrado** (seção 1.3) pede a inclinação e a correlação em todas as amostras, e o mesmo sinal nos dois lados. Isso é atendido: 0,972 e 0,985, sinal positivo nos dois lados.
- **A primeira versão do código** aplicava os limites também dentro de cada lado, mais rígido que o texto, e dava "não bate". Alinhei o código ao texto registrado, antes do commit da Parte B.
- **Por que a correlação cai dentro de um lado:** os valores ficam numa faixa estreita (só curva, quase tudo entre 1 e 2,5 g) e o ruído pesa mais. O sinal não está em dúvida: a inclinação por lado é 0,977 e 0,989, a derivada do `heading` dá −1,000 com correlação 0,99 em cada lado, e o volante concorda em 99,5%.
- Se você preferir a leitura mais rígida, a guinada "não bate" e a Parte B para aí.

## Parte C — onde parou

**A regra registrada para `b`, `L` e `k_δ`** (seção 1.4), aplicada nas 4 sessões de treino de cada rodada:

| rodada (sessão de fora) | `m` (kg) | `w_f` | `κ_L` (1/m) | `f_aero` | `h/L` | `b` (m) | `L` (m) | IC 95% de `L` | `k_δ` (rad) |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| `2026-10-15_23-24-50` | 648 | 0,428 | 0,0030 | 0,442 | 0,135 | −0,08 | −0,18 | −1,75 a 1,31 | 0,066 |
| `2026-10-17_01-02-22` | 639 | 0,431 | 0,0031 | 0,440 | 0,137 | 0,20 | 0,45 | −0,08 a 1,04 | 0,079 |
| `2026-10-17_16-17-08` | 578 | 0,451 | 0,0036 | 0,430 | 0,163 | −0,22 | −0,49 | −2,47 a 1,00 | 0,014 |
| `2026-10-18_12-38-44` | 630 | 0,425 | 0,0032 | 0,443 | 0,142 | −0,16 | −0,37 | −1,94 a 0,89 | 0,048 |
| `2026-10-21_20-30-54` | 653 | 0,417 | 0,0030 | 0,447 | 0,135 | −0,17 | −0,40 | −2,21 a 1,05 | 0,051 |

- **Estáveis e plausíveis:** `w_f`, `κ_L` (a 270 km/h, cerca de 1,7 vez o peso em carga aerodinâmica), `f_aero` e `h/L`.
- **A massa** fica abaixo da faixa registrada (700 a 900 kg): o intercepto em `v = 0` é extrapolado de amostras quase todas em reta, em alta velocidade. Ela não entra nas equações (tudo é por unidade de massa), só no `h/L`.
- **`b` e `L` não são plausíveis:** `L` negativo em 4 rodadas, e nenhuma perto da faixa de 2,8 a 3,8 m.

**A física com essa geometria, nas sessões de treino da rodada 1** (sem a sessão de teste), em erro normalizado (a métrica do ADR 0022):

| | 1 passo | 0,25 s | 0,5 s | 1,0 s |
|---|---:|---:|---:|---:|
| R1, a física registrada | 0,095 | 0,269 | 0,447 | 0,722 |
| R0, persistência | 0,089 | 0,264 | 0,431 | 0,660 |

- A física fica pior que a persistência em todos os horizontes, e 3 parâmetros vão para o limite (`k²` = 4,0, `κ_D` = 0,003, `c0` = 0). A transferência de carga não passou na regra dos 2% (0,0952 com, 0,0948 sem).

**Por quê** (diagnóstico só nas sessões de treino da rodada 1):

- **A inclinação de `vy` contra `r` muda com a velocidade:** −0,87 m entre 10 e 30 m/s, −1,05 entre 30 e 45, −2,41 entre 45 e 60 e −3,55 entre 60 e 90.
- **A regra supõe que a deriva do pneu traseiro por g de aceleração lateral é constante.** Com a carga aerodinâmica, a rigidez cresce com a velocidade, e a regressão confunde a parte geométrica (`b·r`) com a deriva.
- **Com |a_y| ≤ 0,5 g, a guinada quase não varia** em alta velocidade (desvio de 0,04 rad/s acima de 60 m/s), e as duas variáveis da regressão ficam quase colineares.
- **O ângulo de deriva do carro** (`vy/vx`) é quase proporcional à aceleração lateral, −0,002 rad por m/s², igual entre 15 e 60 m/s. Não aparece a parte geométrica que um `b` de 1,5 m daria em baixa velocidade (+0,05 rad numa curva de 30 m de raio). Uma explicação possível, não conferida: a `localVelocity` do jogo pode ser medida num ponto perto do eixo traseiro, e não no centro de massa.

**Duas alternativas testadas, só nas sessões de treino, nenhuma adotada:**

| alternativa | o que deu |
|---|---|
| **(b)** a mesma regressão, com a deriva dividida pela carga do eixo, que cresce com `v²` | `b` de 0,16 a 0,56 m e `L` de 0,37 a 1,31 m, com IC passando de zero em 4 rodadas; `k_δ` de 0,07 a 0,12 rad. **Também não identifica.** |
| **(a)** `L` e `k_δ` ajustados junto com a física por mínimos quadrados, com `b = w_f·L`, nos limites registrados (rodada 1) | `L` vai ao limite de 3,8 m; `k_δ` = 0,30 rad (17°, perto dos 15° que a M0 sugeriu). A física passa a bater a persistência em um passo (0,078 contra 0,089) e em 0,25 s (skill 0,21), mas em 0,5 s o skill contra R0 é **0,09** nas próprias sessões de treino, e em 1,0 s é −0,39. A velocidade lateral é onde a física perde: em 0,5 s, 0,77 m/s de erro contra 0,68 da persistência. Ainda há parâmetros no limite (`k²` = 4,0, `κ_D` e `s_T` no mínimo, `c0` = 0). |

## O que precisa da sua decisão

1. **A conferência da guinada:** aceitar a leitura do texto registrado (correlação em todas as amostras e o mesmo sinal nos dois lados), com a guinada batendo? Ou a leitura mais rígida, com a Parte B parando aí?
2. **Como medir `b`, `L` e `k_δ`.** A regra da seção 1.4 não identifica, e mudar exige um ADR antes de rodar. As opções:
   - **(a) recomendada:** `L` e `k_δ` entram no ajuste por mínimos quadrados da física, com `b = w_f·L` e os mesmos limites (2,8 a 3,8 m; 0,05 a 1,5 rad). Tudo continua saindo da telemetria (ADR 0017). `L` no limite é relatado como "não identificado". No treino, `L` foi ao limite de 3,8 m;
   - **(b)** `L` fixado de fora (por exemplo, o limite de 3,4 m do regulamento de 2026, ou a ficha do carro) e `k_δ` pela regressão do eixo dianteiro ou pelo ajuste. Contraria "tudo sai dos dados" do ADR 0017 e precisaria ser dito no ADR novo;
   - **(c)** um parâmetro a mais para o ponto do carro onde a `localVelocity` é medida, ajustado com a física. É mais um parâmetro mal determinado.
3. **Só para você saber, sem mudar nada:** com a física da opção (a), nas sessões de treino, o skill contra R0 em 0,5 s é 0,09. O critério 1 do ADR 0022 pede 0,50. A correção aprendida teria de cortar mais da metade do erro da física para aprovar. O resultado negativo é aceito (ADR 0022), mas o número ajuda a decidir se vale escrever o ADR novo agora ou repensar a M1 antes.

## O que está pronto e o que falta

- **Pronto e commitado, não rodado na sessão de teste:**
  - `ml/modelo_carro/fisica.py`: o modelo de bicicleta da seção 1.4, a integração de Heun, a malha aberta, a persistência, as posições e o ajuste com a regra da transferência de carga;
  - `ml/modelo_carro/geometria.py`: as medidas diretas da seção 1.4, com o bootstrap por volta;
  - `ml/modelo_carro/correcao.py`: os regimes, o subconjunto de 400 por regime, os 3 Processos Gaussianos e o índice de "fora dos dados";
  - `ml/modelo_carro/validacao.py`: os passos, os casos a cada 0,1 s sem atravessar buraco, o erro combinado, o skill, o bootstrap por volta, a cobertura e as faixas de velocidade.
- **Falta, depois da decisão:** o ADR novo (se houver), o comando `validar` (as 5 rodadas, o corte de "não conclusivo", a tabela do veredito, as tabelas por sessão, regime e velocidade, as figuras da C01 e da C10, a correlação com a temperatura dos pneus), a Parte F (`modelo_fisico_m1.md` seções 5 em diante, M0 seções 3 e 6, `arquitetura_ml.md`, `integracao_ml_e_empacotamento.md`, `backlog.md` e a nota sobre o ADR 0004) e o merge em `develop`.
- **O tempo de cada etapa** de ajuste ainda não foi medido. A física levou 29 s por ajuste nas sessões de treino; o Processo Gaussiano com 2.000 pontos não foi treinado nos dados reais.

## Testes

- **`tests/test_m1_modelo_carro.py`: 14 passaram:**
  - **os dados:** o descarte das repetidas, o corte nos buracos de 50 ms, a reamostragem com o `heading` desdobrado, e o trecho que não atravessa o buraco;
  - **as convenções:** os sinais numa curva à esquerda e numa à direita, o sinal da velocidade lateral pela velocidade do mundo, e o volante trocado que não bate;
  - **a física:** a curva em regime permanente dá `r = vx·δ/L` e a deriva da conta, e a freada em linha reta dá o pedido do freio mais o arrasto, ou o limite de atrito quando satura;
  - **a malha aberta:** o passo e o caso não atravessam buraco;
  - **as métricas:** o skill e o bootstrap contra uma referência conhecida (0,5 exato);
  - **o "não conclusivo":** um ponto fora dos dados de treino tem o índice muito acima do corte.
- **A suíte do backend:** ver o fim de `2026-10-24_37_m1-modelo-do-carro_pytest.txt` (resultado abaixo).

**Suíte do backend: 808 passaram em 9 min 33 s** (`python -m pytest tests -q`, com os 14 da M1).

## Tempo de cada etapa

| etapa | início | fim |
|---|---|---|
| leitura do pedido e desenho | 13:53 | 13:59 |
| Parte A (commit `e0a62949`) | 13:59 | 14:01 |
| Parte B: dados (1 min 40 s de leitura) e convenções, testes (commit `7bf5f565`) | 14:01 | 14:09 |
| Parte C: física, sanidade no treino, diagnóstico, alternativas | 14:09 | 14:18 |
| testes, suíte do backend (9 min 33 s), relatório e documentação | 14:18 | 14:30 |

## Coisas que não batiam com o contexto

- **A sessão `2026-10-17_16-17-08`** não está em `data/recordings`, e sim na pasta do app instalado. O `ml` já lê as duas pastas; nada mudou.
- **A massa medida** (578 a 653 kg) fica abaixo da faixa que registrei (700 a 900 kg). Não muda a física, que é por unidade de massa.
- **A branch em que eu estava** (`etapa/radio-unidades-e-replay`) tem o commit `0092ed38` (app do jogo 0.4.1) que não está em `develop`. A branch da M1 saiu de `develop`, como o pedido manda, e não tem esse commit. Ele não toca no `ml`.
- **`recordings/` na raiz do repositório** está fora do git desde 14/10. Não mexi.
- **O app, o rádio, o coach, o store v2 e o relatório de evolução não mudaram.** As gravações só foram lidas. Nenhum pacote instalado.

Arquivo: `docs/handoff/2026-10-24_37_m1-modelo-do-carro_relatorio.md`
