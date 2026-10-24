# Modelo físico do carro, etapa M1 (pedido 37, ADR 0017 e ADR 0022)

Branch: `etapa/m1-modelo-do-carro`, a partir de `develop`.

**O que a M1 é, em uma frase:** um modelo que recebe como o carro está agora (velocidades e giro) e o que o piloto faz (volante, acelerador e freio) e diz como o carro vai estar 50 ms depois. Repetido passo a passo, ele "pilota no papel" com os comandos gravados e é comparado com o que o carro de fato fez.

## 1. Registrado antes de construir (Parte A)

Esta seção foi commitada antes de qualquer ajuste, treino ou teste. **Nada nela muda depois de ver o teste.** Se algo tiver de mudar, o trabalho para, o Eduardo decide, e a mudança vira um ADR antes de rodar de novo (ADR 0022, Consequências).

### 1.1 Os dados

- **As 5 sessões da contagem oficial** (pedido 36, Parte A), e dentro delas só as voltas válidas do store v2 (`data/ml/laps_grid_v2.parquet`, de 22/10, `geometry_id` `0ed16f0dd2225990`), todas com `origem` igual a `humano`:

| sessão | pasta | voltas válidas | voltas (ordem no arquivo) |
|---|---|---:|---|
| `2026-10-15_23-24-50` | repositório | 11 | 1, 2, 3, 5, 6, 7, 8, 11, 12, 14, 17 |
| `2026-10-17_01-02-22` | repositório | 12 | 3, 5, 6, 9, 10, 11, 13, 15, 16, 17, 18, 19 |
| `2026-10-17_16-17-08` | app instalado (`%APPDATA%`) | 16 | 1, 2, 3, 4, 6, 7, 9, 10, 11, 12, 13, 15, 16, 18, 20, 21 |
| `2026-10-18_12-38-44` | repositório | 9 | 1, 2, 6, 7, 8, 11, 12, 13, 14 |
| `2026-10-21_20-30-54` | repositório | 9 | 6, 8, 9, 10, 12, 13, 15, 16, 17 |
| **total** | | **57** | |

- **De onde:** as amostras cruas (`player.jsonl`), só lidas. A volta é cortada pelas mesmas funções do store v2: `iter_laps` (o corte pelo cronômetro), `clean_lap` e `align_lap`. Uma volta entra se o `lap_id` dela está no store v2. A conferência de que o corte é o mesmo: o número de amostras cruas de cada volta tem de bater com o `raw_samples` do meta do store.
- **Canais lidos de cada amostra:** o cronômetro da volta (`lap_time`), a posição (`world_x`, `world_z`), o `heading`, a velocidade no mundo (`carPhysics.motion.velocity`), `localVelocity`, `localAngularVelocity`, `steerAngle`, acelerador, freio, `accG`, `wheelLoad`, `brakeBias` e `tyreCoreTemperature`.

### 1.2 O relógio e o passo Δt

- **O relógio é o cronômetro do jogo** (`lap_time` de cada amostra, dentro da volta). O horário do gravador não entra em nenhuma conta.
- **Amostra repetida:** a que tem o cronômetro igual ou menor que o da última amostra mantida. É descartada.
- **Trecho contínuo:** termina num intervalo de **50 ms ou mais** entre duas amostras mantidas, e no fim da volta. Nenhum passo e nenhuma previsão atravessam o fim de um trecho.
- **Δt = 50 ms (0,05 s).** Os dados são reamostrados por interpolação linear nos instantes `t0 + k·Δt` de cada trecho (o `heading` é desdobrado antes de interpolar).
  - **Por quê:** o gravador anda em cerca de 15 ms, mas a amostragem é adaptativa e cai para 20 Hz (50 ms) sob carga. Com o corte em 50 ms, todo intervalo de Δt dentro de um trecho tem pelo menos uma amostra real, então nenhum ponto da grade é inventado entre amostras distantes.
  - Um passo de 50 ms é largo o bastante para a variação do estado ficar acima do ruído da diferença finita, e curto o bastante para a física simples andar com 5 subpassos.
  - Os horizontes ficam em passos inteiros: 0,25 s = 5 passos, 0,5 s = 10 e 1,0 s = 20.
- **A entrada de cada passo** (de `k` para `k+1`) é a média das entradas gravadas em `k` e `k+1`, a mesma para a física e para a correção.

### 1.3 O estado e as entradas, com unidades e sinais

A convenção do modelo: **x para a frente, y para a esquerda, giro positivo para a esquerda** (anti-horário visto de cima).

| grandeza | símbolo | unidade | de onde vem | sinal no modelo |
|---|---|---|---|---|
| velocidade longitudinal | `vx` | m/s | `localVelocity.z` | positiva para a frente |
| velocidade lateral | `vy` | m/s | `localVelocity.x` × `s_vy` | positiva para a esquerda |
| guinada | `r` | rad/s | `localAngularVelocity.y` × `s_r` | positiva girando para a esquerda |
| posição e rumo (só para andar no horizonte) | `X`, `Y`, `ψ` | m, rad | integrados a partir de zero em cada início | `ψ` positivo para a esquerda |
| volante | `steer` | gravado sem unidade (seção 3 da M0) | `steerAngle` bruto | positivo à direita (M0); a roda é `δ = −k_δ · steer`, em rad, positiva à esquerda |
| acelerador, freio | `T`, `B` | 0 a 1 | `controls` | — |
| aceleração lateral (só nas regressões da geometria e nos regimes) | `a_y` | m/s² | `accG.lateral` × 9,80665 | positiva para a esquerda (M0, ADR 0003) |

- **Os sinais `s_vy` e `s_r`** e a relação do `heading` com o rumo saem das conferências da Parte B, por esta regra fixada aqui:
  - **`s_r`:** o que faz `a_y ≈ vx · r` (a aceleração centrípeta) ter inclinação positiva;
  - **`heading`:** a derivada dele contra a guinada dá a inclinação +1 ou −1, e isso define o sinal de `ψ`;
  - **`s_vy`:** a velocidade do mundo é projetada no eixo do carro (dado pelo `heading`), com "esquerda" definida pelo lado para onde o rumo gira nas curvas à esquerda da geometria (`Corner.direction = +1`); `s_vy` é o sinal da inclinação de `localVelocity.x` contra essa projeção;
  - **`vx`:** `localVelocity.z` contra a velocidade do mundo projetada para a frente.
- **Uma conferência "bate" quando:** a inclinação fica entre 0,95 e 1,05 em módulo (0,90 a 1,10 para `vy`, que é pequena), a correlação é pelo menos 0,95 (0,90 para `vy`), e o sinal é o mesmo nas curvas à esquerda e nas à direita. Para o volante: com |`a_y`| ≥ 0,5 g, o sinal de `−steer` é o de `r` em pelo menos 95% das amostras. **Se alguma não bater, o trabalho para** (pedido 37, Parte B.3).

### 1.4 A física simples (a referência R1)

**A forma:** o modelo de bicicleta dinâmico, por unidade de massa (as forças divididas pela massa, em m/s²). As rodas de cada eixo viram uma só.

```
ângulo de deriva:   α_f = δ − atan2(vy + a·r, vx)        α_r = −atan2(vy − b·r, vx)      (vx ≥ 5 m/s na conta)
carga por eixo:     n_f = g·w_f + κ_L·f_aero·vx² − (h/L)·a_x        n_r = g·(1 − w_f) + κ_L·(1 − f_aero)·vx² + (h/L)·a_x
força longitudinal: tração (traseira)  F_xr = s_T · T · (A_env(vx) + κ_D·vx² + c0)
                    freio              F_x,i = −min(β_B · B · bias_i, 0,99·μ·n_i)    bias_f = brakeBias, bias_r = 1 − brakeBias
                    resistência        R = κ_D·vx² + c0·(1 − T)
força lateral:      F_y,i = F_max,i · tanh(Cα · n_i · α_i / F_max,i),   F_max,i = √(max((μ·n_i)² − F_x,i², ε))   (elipse de atrito)
equações:           dvx/dt = F_xr + F_xf·cos δ − F_yf·sin δ − R + vy·r
                    dvy/dt = F_yr + F_yf·cos δ + F_xf·sin δ − vx·r
                    dr/dt  = (a·(F_yf·cos δ + F_xf·sin δ) − b·F_yr) / k²
                    dψ/dt = r,  dX/dt = vx·cos ψ − vy·sin ψ,  dY/dt = vx·sin ψ + vy·cos ψ
```

- **A integração:** 5 subpassos de 10 ms por passo de Δt, pelo método de Heun, com a entrada do passo constante. `a_x` na carga é a aceleração longitudinal da própria conta (uma iteração de ponto fixo, partindo das cargas sem transferência). Na tração, a força é limitada também pela elipse do eixo traseiro.
- **`A_env(v)`** é a tração do envelope (`ml/optimization/vehicle_model.py`, `fit_envelope`), **reajustado em cada rodada só com as voltas das 4 sessões de treino** no store v2. Com `s_T = 1` e acelerador no fundo, a aceleração líquida é a do envelope.

**Os parâmetros, em dois grupos:**

*Medidos dos dados por conta direta (regressões nas 4 sessões de treino de cada rodada):*

| parâmetro | o que é | unidade | faixa plausível | como |
|---|---|---|---|---|
| `m` | massa (com piloto e combustível) | kg | 700 a 900 | soma das 4 cargas = `m·g + m·κ_L·v²`, com \|a_x\| e \|a_y\| < 0,1 g; o intercepto dá `m·g` |
| `κ_L` | carga aerodinâmica por massa | 1/m | 0,001 a 0,006 | a inclinação da mesma regressão, dividida por `m` |
| `w_f` | fração do peso na frente, parado | — | 0,40 a 0,50 | a mesma regressão com a carga da frente: intercepto ÷ `m·g` |
| `f_aero` | fração da carga aerodinâmica na frente | — | 0,35 a 0,55 | inclinação da frente ÷ inclinação total |
| `h/L` | altura do centro de massa ÷ entre-eixos | — | 0,05 a 0,15 | a carga da frente que sobra das regressões acima contra `a_x`, com \|a_y\| < 0,1 g |
| `b` | do centro de massa ao eixo traseiro | m | 1,4 a 2,1 | `vy = b·r + c_r·vx·a_y + d`, com \|a_y\| ≤ 0,5 g, `vx` ≥ 10 m/s e freio < 0,05 (o eixo traseiro anda na direção da roda, menos a deriva) |
| `L` | entre-eixos | m | 2,8 a 3,8 | `L = b / w_f` (equilíbrio do peso parado) |
| `a` | do centro de massa ao eixo dianteiro | m | — | `a = L − b` |
| `k_δ` | ângulo da roda por unidade de `steer` | rad | 0,05 a 1,5 | `(vy + a·r)/vx = k_δ·(−steer) + c_f·a_y + d`, nas mesmas amostras |
| `brakeBias` | fração do freio na frente | — | 0,5 a 0,7 | média gravada |

- **A incerteza** de `b`, `L` e `k_δ` sai de um bootstrap agrupado por volta (200 reamostragens) e da variação entre as 5 rodadas.

*Ajustados por mínimos quadrados (`scipy.optimize.least_squares`, perda quadrática, com a faixa plausível como limite):*

| parâmetro | o que é | unidade | faixa plausível (limite do ajuste) | início |
|---|---|---|---|---|
| `Cα` | rigidez de deriva por unidade de carga | 1/rad | 5 a 60 | 20 |
| `μ` | atrito máximo | — | 1,0 a 2,5 | 1,6 |
| `k²` | inércia de guinada ÷ massa (raio de giração ao quadrado) | m² | 0,5 a 4,0 | 1,5 |
| `κ_D` | arrasto por massa | 1/m | 0,0003 a 0,003 | 0,001 |
| `c0` | desaceleração sem acelerador (freio-motor e rolamento) | m/s² | 0 a 3 | 1 |
| `s_T` | escala da tração do envelope | — | 0,5 a 1,5 | 1 |
| `β_B` | desaceleração pedida com o freio no fundo | m/s² | 10 a 60 | 30 |

- **O alvo do ajuste:** o estado depois de um passo (`vx`, `vy`, `r` em `k+1`), a partir do estado gravado em `k`, cada grandeza dividida pelo desvio-padrão dela nas sessões de treino. Todos os passos das 4 sessões de treino entram.
- **Uma rigidez só (`Cα`) para os dois eixos:** a diferença entre a frente e a traseira já entra pela carga de cada eixo (`n_f`, `n_r`). Isso tira um parâmetro mal determinado.
- **Parâmetro no limite** é relatado como tal.

**A transferência de carga longitudinal** (o termo `h/L · a_x`) só entra se mudar o resultado, pela regra fixada aqui: em cada rodada, a física é ajustada com e sem o termo (com `h/L` medido nas cargas, sem parâmetro livre a mais); o termo entra se reduzir o erro de um passo nas sessões de treino em pelo menos 2%. A transferência lateral não entra (o modelo de bicicleta não separa os lados).

**O que esta física não tem, de propósito:** a inclinação e o relevo da pista, a marcha e o motor (a tração vem do envelope por velocidade), a temperatura dos pneus e dos freios (etapa M2), e a diferença de pneus entre os lados.

### 1.5 A correção aprendida (a M1)

- **O que aprende:** o resíduo da física em um passo: o estado gravado em `k+1` menos o que a física prevê a partir do estado gravado em `k`. Um Processo Gaussiano por grandeza (`vx`, `vy` e `r`), do scikit-learn 1.6.1.
- **As variáveis de entrada (6):** `vx`, `vy`, `r` e a entrada do passo (`steer`, `T`, `B`), padronizadas pela média e desvio-padrão do subconjunto de treino. **Nada que identifique a volta, a sessão, o tempo da sessão ou o ponto da pista** (ADR 0017, item 1).
- **O núcleo:** `Constante × RBF com um comprimento por variável + Ruído branco`, com `normalize_y=True`. Limites: constante de 1e-3 a 1e3; comprimentos de 1e-2 a 1e2 (início 1); ruído de 1e-6 a 10 (início 0,1). Os hiperparâmetros saem da verossimilhança, só nas sessões de treino, com o otimizador padrão e sem reinícios.
- **O subconjunto, para caber na memória:** 2.000 passos das 4 sessões de treino, **400 por regime**, sorteados com a semente 37. Regime com menos de 400 passos entra inteiro e a cota que sobra não é redistribuída. Os regimes, pelo estado gravado no passo:

| regime | regra |
|---|---|
| freio e volante juntos | freio ≥ 0,1 e \|a_y\| ≥ 0,5 g |
| freada | freio ≥ 0,1 e \|a_y\| < 0,5 g |
| curva | freio < 0,1 e \|a_y\| ≥ 0,5 g |
| tração | freio < 0,1, \|a_y\| < 0,5 g, acelerador ≥ 0,5 e `a_x` ≥ 0,3 g |
| reta | o resto |

- **Na previsão,** a M1 é a física mais a média do Processo Gaussiano, a cada passo, em malha aberta.
- **O intervalo de 90%** de um passo é a média ± 1,645 × o desvio-padrão previsto (com o ruído).

### 1.6 O corte de "não conclusivo"

- **O índice de um ponto:** para cada grandeza, o desvio-padrão do Processo Gaussiano sem o ruído (a parte que vem de não ter visto dados parecidos), dividido pelo desvio-padrão do sinal (a raiz da constante do núcleo). Vai de 0 (dados parecidos no treino) a 1 (nada parecido). O índice do ponto é o maior das 3 grandezas.
- **O índice de um caso** (um início de previsão) é o maior índice dos pontos do caminho previsto pela M1 até 0,5 s.
- **O corte:** o percentil 99 do índice dos casos das 4 sessões de treino da rodada (inícios a cada 0,5 s). Um caso de teste acima do corte é marcado "não conclusivo".
- **As métricas da aprovação usam todos os casos,** conclusivos ou não; o resultado só nos conclusivos é relatado à parte. A fração de "não conclusivo" é relatada por regime e por sessão (ADR 0022, item 6).

### 1.7 A validação (copiada do ADR 0022)

- **5 rodadas,** cada uma com uma sessão inteira de fora. Tudo o que é ajustado (os parâmetros medidos e os ajustados da física, o envelope, o desvio-padrão de normalização, a correção e os hiperparâmetros dela, o corte de "não conclusivo") usa só as outras 4.
- **Os casos:** inícios a cada 0,1 s (2 passos) em todos os trechos da sessão de teste, desde que o trecho tenha pelo menos 1,0 s depois do início. Os três horizontes usam os mesmos casos.
- **A malha aberta:** a partir do estado gravado no início, o modelo anda passo a passo com as entradas gravadas, sem olhar o estado gravado no caminho.
- **As referências:** **R0**, persistência: `vx`, `vy` e `r` ficam iguais ao do início (a posição anda em arco com esse estado). **R1**, só a física, com os parâmetros da rodada.
- **O erro principal:** em 0,5 s, o erro de `vx`, `vy` e `r`, cada um dividido pelo desvio-padrão da grandeza nas sessões de treino; o erro combinado é a raiz da média dos quadrados, sobre os casos e as 3 grandezas. **Skill = 1 − erro do modelo ÷ erro da referência.**
- **Os 7 critérios,** todos em 0,5 s, todos necessários para aprovar:

| nº | critério | como é medido aqui |
|---|---|---|
| 1 | skill contra R0 ≥ 0,50 | casos das 5 rodadas juntos |
| 2 | skill contra R1 ≥ 0,20 | casos das 5 rodadas juntos |
| 3 | limite inferior do IC 95% do skill contra R1 > 0 | bootstrap agrupado por volta, 2.000 reamostragens, semente 37, percentis 2,5 e 97,5 |
| 4 | skill contra R1 positivo em pelo menos 4 das 5 sessões | cada sessão na rodada em que é a de teste |
| 5 | \|viés\| de cada grandeza ≤ 25% do erro de R1 | para `vx`, `vy` e `r`: \|média de (M1 − gravado)\| ≤ 0,25 × raiz do erro quadrático médio de R1 na mesma grandeza |
| 6 | o intervalo de 90% cobre de 80% a 97% dos casos de teste, no passo de Δt | no primeiro passo de cada caso: o resíduo gravado dentro da média ± 1,645 desvio-padrão; as 3 grandezas e as 5 rodadas juntas |
| 7 | pelo menos 5 sessões testáveis | sessão testável: pelo menos 100 casos |

- **Também relatados, sem entrar na aprovação:** os horizontes de 0,25 s e 1,0 s; o erro de posição em metros (a distância entre a posição prevista e a gravada, no referencial do início); cada grandeza separada; por sessão, por regime (a regra da seção 1.5, pelo estado gravado no início) e por faixa de velocidade (`vx` no início: abaixo de 100 km/h, 100 a 160, 160 a 220 e acima de 220); a fração de "não conclusivo"; a cobertura de cada grandeza.
- **As figuras:** na rodada em que a sessão `2026-10-21_20-30-54` é a de teste, na primeira volta válida em que o trecho cobre o caso:
  - **a freada da C01:** início 0,2 s antes do primeiro passo com freio ≥ 0,5 entre 250 m antes do começo da C01 e o ápice dela;
  - **a curva lenta, a C10:** início 0,5 s antes do passo de menor `vx` dentro da C10;
  - horizonte de 1,0 s; a M1, R1, R0 e o gravado; a faixa de 5% a 95% da M1 por Monte Carlo (200 caminhos, cada passo sorteado da previsão do Processo Gaussiano com o ruído), semente 37.
- **A indicação para a M2:** a correlação de Spearman entre o resíduo da M1 no primeiro passo (cada grandeza) e a temperatura média dos 4 pneus no início, com os casos das 5 rodadas. Só a correlação.
- **Se um critério não passar,** o resultado é relatado e o trabalho para. Nenhum ajuste depois de ver o teste.

### 1.8 O que se espera, antes de ver qualquer número

A física simples deve bater a persistência com folga (critério 1), e a correção aprendida deve melhorar pouco sobre ela em 0,5 s, perto do limite de 0,20 contra R1, com o maior ganho na guinada e na velocidade lateral e o menor na longitudinal.
