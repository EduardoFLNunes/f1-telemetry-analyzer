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

> **Emenda de 25/10 (ADR 0024):** `L`, `b`, `h/L` e `k_δ` passam a ser medidos pela telemetria do jogo, e a velocidade lateral é levada ao centro de massa. A regra é a da seção 1.9; a regra abaixo, das regressões cinemáticas, não identificou os parâmetros (seção 4).

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

### 1.9 Emenda de 25/10 (ADR 0024)

Registrada antes de medir, num commit próprio (pedido 39, Parte A). Ela troca só a forma de obter `L`, `b`, `h/L` e `k_δ` da seção 1.4 e acrescenta o ponto `x_v` da velocidade gravada. A regra antiga das regressões cinemáticas fica registrada na 1.4: ela não identificou os parâmetros (seção 4). Todo o resto da seção 1, e os critérios do ADR 0022, não mudam.

**A sessão de medição**

- Gravada pela ferramenta `ml/scripts/medir_geometria.py`, que só lê a memória compartilhada do jogo, em cerca de 60 Hz. **Não é uma das 5 sessões da M1**, então nada da sessão de teste entra na geometria.
- Só vale se a página estática disser `carModel = rss_formula_rss_3_v6_2026` e `track = vhe_interlagos`. Se não disser, nada é medido.
- O roteiro: parado no box, o volante girado devagar de um batente ao outro, duas vezes; depois 3 voltas normais.
- **A ordem dos campos 4 × 3:** `tyreContactPoint` e `tyreContactHeading` são lidos achatados, na ordem da memória; a roda `w` (0 = dianteira esquerda, 1 = dianteira direita, 2 = traseira esquerda, 3 = traseira direita) e a coordenada `c` (x, y, z do mundo) ficam no índice `3·w + c`.
- **As duas partes da sessão:**
  - **sem relógio** (só para `k_δ`): todas as amostras com um `packetId` da física diferente do anterior, inclusive paradas no box, onde o cronômetro da volta pode não andar;
  - **com relógio** (para `L`, `h` e `x_v`): o mesmo preparo da Parte B. O relógio é o cronômetro do jogo (`iCurrentTime`), as amostras repetidas são descartadas, os trechos são cortados em buracos de 50 ms ou mais, e os dados são reamostrados em 50 ms.
- **Os eixos do carro** saem do `heading` pela convenção da seção 3: frente `(−sen h, cos h)` e esquerda `(cos h, sen h)`, no plano (x, z) do mundo. "Em movimento" quer dizer `vx` ≥ 10 m/s.

**Como cada parâmetro é medido**

| parâmetro | regra |
|---|---|
| `L` | Em cada amostra, o ponto médio dos contatos dianteiros menos o ponto médio dos traseiros, no plano (x, z), projetado na frente do carro. **A mediana nas amostras em movimento com \|a_y\| < 0,2 g** (a reta). |
| `b` | `b = w_f · L`, com `w_f` medido nas cargas das 4 sessões de treino de cada rodada, como na 1.4. `a = L − b`. |
| `h/L` | A mediana de `cgHeight` nas amostras em movimento, dividida por `L`. Substitui o `h/L` das cargas, que fica só como conferência. |
| `k_δ` | Cada direção de pneu é escrita nos eixos do carro, e o ângulo dela é `atan2(esquerda, frente)`. O ângulo das rodas é o da direção média dos dois dianteiros menos o da direção média dos dois traseiros, positivo para a esquerda. Na parte sem relógio, a regressão linear `ângulo = c + s · steerAngle` dá `k_δ = −s` (o volante é positivo à direita) e `c`, a convergência estática. O mesmo é feito com cada pneu dianteiro contra a média dos traseiros (esquerdo e direito, relatados à parte). **O modelo usa a regressão da média.** |
| sentido de `tyreContactHeading` | Antes de medir o ângulo: se, na mediana, a direção dos pneus aponta contra o vetor do eixo traseiro para o dianteiro (produto escalar negativo), todas as direções são invertidas. |
| `x_v` | Na parte com relógio, em movimento: a velocidade de cada ponto médio de eixo é a derivada no tempo da posição dele, dentro do trecho. A parte lateral é a projeção na esquerda do carro. Num corpo rígido, `vy_gravada = v_lat,traseiro + x_v · r`. Então `x_v` (em metros, a partir do eixo traseiro, positivo para a frente) é a inclinação de `vy_gravada − v_lat,traseiro` contra `r`, pela origem, com \|r\| ≥ 0,05 rad/s. A mesma conta com o eixo dianteiro (`x_v = L + inclinação`) é relatada como conferência. O intervalo de 95% sai de um bootstrap por trecho (200 reamostragens, semente 39). |
| a velocidade lateral do modelo | `vy_cm = vy_gravada + (b − x_v) · r`, em todas as amostras das 5 sessões, antes de qualquer conta (o desvio-padrão de normalização, os passos, os casos e a correção usam `vy_cm`). |

**Os portões**

| parâmetro | passa quando | se não passar |
|---|---|---|
| `L` | fica entre 2,8 e 3,8 m, e a faixa entre os percentis 5 e 95 é menor que 3% do valor | usa o valor publicado, 2,943 m, declarado como fonte externa e exceção ao ADR 0017 |
| `k_δ` | fica entre 0,05 e 1,5 rad, com R² ≥ 0,95 na regressão da média | sai da regressão em regime permanente `−steer = (L/k_δ) · κ + K · a_y`, com `κ = r/vx`, nas amostras em movimento com \|dr/dt\| < 0,1 rad/s², com o `L` medido |
| `x_v` | a meia-largura do intervalo de 95% é menor que 0,2 m | supõe-se que a velocidade gravada é a do centro de massa (`x_v = b`, sem correção), e isso é relatado |

- **A geometria é do carro, não do piloto:** é medida uma vez e usada nas 5 rodadas (só `b` muda de rodada, pelo `w_f`).
- **O que também é relatado, sem decidir nada:** `h/L` pelo `cgHeight` contra o das cargas; `L/k_δ` contra a razão volante ÷ curvatura da M0 (cerca de 10,6); e se o ângulo da roda contra o volante é linear em toda a faixa (a razão por faixa de \|steer\|).

## 2. Os dados (Parte B)

Comando: `python -m ml.scripts.m1_modelo_carro dados`. As 5 gravações têm o mesmo sha256 registrado no meta do store v2, e o número de amostras cruas de cada uma das 57 voltas bate com o `raw_samples` do store: o corte é o mesmo.

| sessão | voltas | amostras cruas | tiradas na limpeza | repetidas | buracos ≥ 50 ms | trechos | trechos curtos tirados | passos de 50 ms | segundos |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `2026-10-15_23-24-50` | 11 | 57.929 | 49 | 845 (1,5%) | 167 | 162 | 16 | 19.856 | 985 |
| `2026-10-17_01-02-22` | 12 | 63.486 | 94 | 879 (1,4%) | 170 | 163 | 19 | 21.751 | 1.079 |
| `2026-10-17_16-17-08` | 16 | 85.788 | 97 | 4.392 (5,1%) | 659 | 458 | 217 | 28.804 | 1.417 |
| `2026-10-18_12-38-44` | 9 | 46.161 | 95 | 1.890 (4,1%) | 383 | 331 | 61 | 15.943 | 781 |
| `2026-10-21_20-30-54` | 9 | 46.251 | 64 | 843 (1,8%) | 248 | 237 | 20 | 15.896 | 783 |
| **total** | **57** | **299.615** | **399** | **8.849** | **1.627** | **1.351** | **333** | **102.250** | **5.045** |

- **Tiradas na limpeza:** as que o `clean_lap` do store tira (horário do gravador repetido).
- **Repetidas:** o cronômetro do jogo não andou. A sessão do pacote 0.4.0 (17/10 16:17) tem 5,1%, como o pedido 33 já tinha medido.
- **Buracos:** a mesma sessão tem 659 buracos de 50 ms ou mais em 16 voltas, contra 15 por volta nas outras. Por isso ela perde 217 trechos curtos demais (menos de 2 pontos).
- **Faixas (p1 / p50 / p99, todas as sessões):** `vx` de 19 a 74 m/s (mediana 46); `vy` de −4,6 a 5,0 m/s (mediana −0,23); guinada de −0,85 a 0,75 rad/s; volante de −0,47 a 0,47; `brakeBias` sempre 0,55; temperatura média dos pneus de 31 °C (início de sessão) a 93 °C. Todos os canais estão 100% preenchidos. O JSON completo, por sessão e por volta, está em `docs/handoff/2026-10-24_37_m1-modelo-do-carro_dados.json`.

## 3. As conferências de convenção (Parte B.3)

Comando: `python -m ml.scripts.m1_modelo_carro convencoes`. Todas batem, com a mesma convenção nas 5 sessões.

| conferência | inclinação | correlação | esquerda / direita | resultado |
|---|---:|---:|---|---|
| aceleração lateral contra `vx` × guinada gravada | 0,972 | 0,985 | 0,977 / 0,989 (correlação 0,907 / 0,884) | bate; a guinada gravada já é positiva para a esquerda (`s_r = +1`) |
| derivada do `heading` contra a guinada gravada | −0,999 | −0,999 | −1,001 / −1,000 | bate; o `heading` **diminui** girando para a esquerda (`ψ = −heading`) |
| `localVelocity.x` contra a velocidade do mundo para a esquerda | 0,998 | 0,99998 | 0,997 / 1,000 | bate; `localVelocity.x` já é positiva para a esquerda (`s_vy = +1`) |
| `localVelocity.z` contra a velocidade do mundo para a frente | 1,001 | 0,99999 | 1,001 / 1,001 | bate |
| volante: sinal de `−steer` igual ao da guinada, com \|a_y\| ≥ 0,5 g | — | — | 99,8% / 99,5% (99,2% no geral) | bate |

- **A direção do carro no mundo** é `(−sen h, cos h)` no plano (x, z), e a esquerda é `(cos h, sen h)`.
- **A aceleração lateral positiva para a esquerda** (M0) confere com a geometria: positiva em 99,3% dos pontos com \|a_y\| ≥ 0,5 g nas curvas à esquerda, e negativa em 99,9% nas à direita.
- **O sinal da velocidade lateral nas curvas:** `vy` é negativa nas curvas à esquerda (C01: mediana −0,83 m/s a 105 km/h) e positiva nas à direita (C10: +0,30 m/s a 83 km/h; C06: +2,5 m/s a 171 km/h). O carro aponta para dentro da curva e o centro dele anda para fora: a deriva do pneu traseiro vence o efeito geométrico em todas as 14 curvas, até nas lentas.
- **A correlação dentro de cada lado.** Na guinada, a correlação calculada só dentro das curvas à esquerda (0,907) e só dentro das à direita (0,884) fica abaixo de 0,95. A regra registrada (1.3) pede a inclinação e a correlação em todas as amostras e o mesmo sinal nos dois lados, e isso é atendido. Dentro de um lado só, os valores ficam numa faixa estreita e a correlação cai sem que o sinal esteja em dúvida (a inclinação é 0,977 e 0,989). A primeira versão do código aplicava os limites também a cada lado, mais rígido que o texto; ela foi alinhada ao texto registrado. **Decidido pelo Eduardo em 25/10 (pedido 39): vale a leitura do texto registrado, e a guinada bate.**

## 4. A física: onde o trabalho parou (Parte C)

**A regra registrada para o entre-eixos não funciona com estes dados.** Ela foi aplicada nas 4 sessões de treino de cada rodada, como registrado:

| rodada (sessão de fora) | `m` (kg) | `w_f` | `h/L` | `b` (m) | `L` (m) | IC 95% de `L` | `k_δ` (rad) |
|---|---:|---:|---:|---:|---:|---|---:|
| `2026-10-15_23-24-50` | 648 | 0,428 | 0,135 | −0,08 | −0,18 | −1,75 a 1,31 | 0,066 |
| `2026-10-17_01-02-22` | 639 | 0,431 | 0,137 | 0,20 | 0,45 | −0,08 a 1,04 | 0,079 |
| `2026-10-17_16-17-08` | 578 | 0,451 | 0,163 | −0,22 | −0,49 | −2,47 a 1,00 | 0,014 |
| `2026-10-18_12-38-44` | 630 | 0,425 | 0,142 | −0,16 | −0,37 | −1,94 a 0,89 | 0,048 |
| `2026-10-21_20-30-54` | 653 | 0,417 | 0,135 | −0,17 | −0,40 | −2,21 a 1,05 | 0,051 |

- **O que dá certo:** a distribuição do peso (`w_f` de 0,42 a 0,45), a carga aerodinâmica (`κ_L` de 0,0030 a 0,0036 1/m, cerca de 1,7 vez o peso a 270 km/h, com 43% a 45% na frente) e `h/L` (0,13 a 0,16) saem estáveis entre as rodadas. A massa (578 a 653 kg) fica abaixo da faixa registrada (700 a 900 kg): as amostras calmas (\|a_x\| e \|a_y\| < 0,1 g) estão quase todas nas retas, em alta velocidade, e o intercepto em `v = 0` é uma extrapolação. A massa não entra na conta da física (tudo é por unidade de massa), só no `h/L`.
- **O que não dá:** `b` sai perto de zero e `L` sai negativo ou menor que 1,1 m, longe da faixa plausível (2,8 a 3,8 m), com um intervalo que passa de zero em 4 das 5 rodadas. Com `L` negativo a física não tem sentido, e o ajuste dela nas sessões de treino fica **pior que a persistência** já em um passo (0,095 contra 0,089 no erro normalizado) e em 0,5 s (skill −0,04 contra R0), com 3 parâmetros no limite (`k²`, `κ_D` e `c0`).
- **Por quê (diagnóstico só nas sessões de treino da rodada 1):** a inclinação de `vy` contra `r` muda com a velocidade: −0,87 m entre 10 e 30 m/s, −1,05 entre 30 e 45, −2,41 entre 45 e 60, −3,55 entre 60 e 90. A regra supõe que a deriva do pneu traseiro por unidade de aceleração lateral é constante. Com a carga aerodinâmica, a rigidez do pneu cresce com a velocidade, a deriva cai, e a regressão confunde os dois termos. Além disso, com \|a_y\| ≤ 0,5 g a guinada quase não varia em alta velocidade (desvio de 0,04 rad/s acima de 60 m/s), e `r` e `vx·a_y` ficam quase colineares.
- **Duas tentativas de diagnóstico, nenhuma adotada:**
  - **a mesma regressão com a deriva dividida pela carga do eixo** (que cresce com `v²`): `b` de 0,16 a 0,56 m e `L` de 0,37 a 1,31 m, com intervalos que passam de zero. Também não identifica;
  - **`L` e `k_δ` ajustados junto com a física** (com `b = w_f·L`, nos limites registrados): `L` vai para o limite de 3,8 m, `k_δ` sai 0,30 rad (17°, perto dos 15° que a M0 sugeriu), e a física passa a bater a persistência em um passo (0,078 contra 0,089). Em 0,5 s, nas próprias sessões de treino, o skill contra R0 é 0,09 (a velocidade lateral é a grandeza em que a física perde para a persistência); em 1,0 s, −0,39.
- **O que isso muda:** a seção 1.4 precisa de outra regra para `b`, `L` e `k_δ`, e isso é uma mudança do registrado. **O trabalho parou aqui, antes de qualquer previsão na sessão de teste,** para o Eduardo decidir (relatório do pedido 37). Nenhum número de teste foi calculado.

## 5. A geometria medida pela telemetria do jogo (pedido 39, Parte D; ADR 0024)

Comando: `python -m ml.scripts.m1_modelo_carro geometria --sessao data/ml/modelo_carro/geometria_2026-10-28_13-23-49.parquet`. A regra é a da seção 1.9.

**A sessão de medição** (28/10, 13:23, gravada pela ferramenta `ml.scripts.medir_geometria`):
- `rss_formula_rss_3_v6_2026` em `vhe_interlagos`, AC 1.16.4: 20.292 amostras em 339 s (59,8 Hz);
- o volante de batente a batente duas vezes, parado no box; depois a volta de saída, **1 volta completa** e parte da seguinte;
- **um desvio do roteiro:** foi 1 volta, e não as 3 dos passos. Pela decisão do Eduardo, os portões decidem se isso basta. Os de `L` e de `x_v` passaram com folga;
- **uma batida no fim:** aos 325 s há um impacto de 18,9 g, e o carro para. Depois dela, a direção do pneu dianteiro direito fica 0,57 rad (33°) fora do que o volante pede, enquanto a do esquerdo continua certa: a direção daquele lado entortou com o dano.

**Os parâmetros e os portões:**

| parâmetro | medido | portão | resultado | usado no modelo |
|---|---|---|---|---|
| `L` (entre-eixos) | **2,964 m** (percentis 5 e 95: 2,952 e 2,965 m; 1.114 amostras em reta) | 2,8 a 3,8 m, faixa < 3% | **passa** (faixa de 0,46%) | 2,964 m, medido |
| `k_δ` (roda por unidade de volante) | 0,312 rad na regressão da média, com **R² = 0,744** | 0,05 a 1,5 rad, R² ≥ 0,95 | **não passa** | **0,304 rad**, pela regressão em regime permanente (`−steer = 9,75·κ + 0,0017·a_y`, 1.358 amostras) |
| `x_v` (onde a velocidade é medida, a partir do eixo traseiro) | **1,209 m** (IC 95%: 1,201 a 1,214 m); pelo eixo dianteiro, 1,214 m | meia-largura < 0,2 m | **passa** (0,006 m) | 1,209 m, medido |
| `h` (`cgHeight`) | **0,271 m** (percentis 5 e 95: 0,263 e 0,276 m) | — | — | `h/L = 0,0915` |

- **Por que `k_δ` não passou:** pela batida no fim. Na sessão inteira, o pneu esquerdo dá R² de 0,9996 e o direito, 0,443. Os 566 pontos ruins do direito (3% da sessão) vêm todos depois do impacto. **O caminho é o do ADR 0024, e o modelo usa 0,304 rad.** Nenhuma regra foi mudada depois de ver o número.
- **Só para informação, sem decidir nada: antes da batida** (as amostras até 325 s), `k_δ` = 0,2974 rad, com R² de 0,9998; o esquerdo dá 0,2969 e o direito 0,2980, com a convergência estática de ±0,003 rad (simétrica). A regressão de reserva dá 0,301. O valor usado (0,304) fica 2% acima.
- **A curva do ângulo da roda contra o volante é linear em toda a faixa** (antes da batida): a razão local vai de 0,296 rad perto do centro a 0,299 rad nos batentes, menos de 1% de diferença. **O volante gravado é uma fração do curso:** ele vai de −1,0 a +1,0, de batente a batente, e no batente a roda vira cerca de 0,30 rad (17°). Isso fecha a pendência da seção 3 da M0.
- **`L/k_δ` = 2,964 / 0,304 = 9,75** (9,97 com o valor de antes da batida), contra a razão volante ÷ curvatura da M0 em baixa velocidade, de 10,1 a 10,6 nas voltas do Eduardo. A razão da M0 inclui a deriva dos pneus, que a deixa maior.
- **`x_v` fica perto do centro de massa:** com o `w_f` das cargas de cada rodada (0,417 a 0,451), `b = w_f · L` vai de 1,24 a 1,34 m. A velocidade gravada é medida de 0,03 a 0,13 m atrás do centro de massa, e a correção `vy_cm = vy_gravada + (b − x_v)·r` é pequena (em 0,6 rad/s de guinada, de 0,02 a 0,08 m/s). **A hipótese do ADR 0024, de que a velocidade gravada estaria longe do centro de massa, não se confirma.** A falta da parte geométrica no ângulo de deriva (seção 4) vem do pneu, não do ponto de medida.
- **`h/L` pelo `cgHeight` (0,0915) fica abaixo do das cargas** (0,135 a 0,163, pedido 37). A estimativa pelas cargas inclui a transferência pela suspensão e pela aerodinâmica na freada, que a altura do centro de massa sozinha não tem. Pelo ADR 0024, o modelo usa o `cgHeight`.
- **As bitolas,** entre os pontos de contato em reta: 1,588 m na frente e 1,509 m atrás. O retrato de maio deu 2,955 m de entre-eixos (0,3% abaixo do medido aqui) e a reportagem, 2,943 m.

## 6. A validação e o veredito (pedido 39, Parte E; ADR 0022)

**Em uma frase: a M1 não foi aprovada.** A física simples com a correção aprendida prevê o carro melhor que só a física e melhor que "o carro continua igual", mas não com a folga que o ADR 0022 exige: em 0,5 s, ela corta 20% do erro da persistência (o critério pede 50%) e 17% do erro da física (o critério pede 20%).

### 6.1 Como foi testado

- **As 5 rodadas:** em cada uma, uma sessão inteira fica de fora. Tudo o que é ajustado usa só as outras 4: as cargas, o envelope, `b = w_f · L`, o desvio-padrão de normalização, os 7 parâmetros da física, a correção e o corte de "não conclusivo". A geometria (`L`, `k_δ`, `x_v`, `h/L`) vem da sessão de medição, que não é nenhuma das 5 (seção 5).
- **Os casos:** 39.142 inícios de previsão, a cada 0,1 s, em todos os trechos das 5 sessões de teste com pelo menos 1,0 s pela frente (de 5.125 a 10.314 por sessão). Em cada um, o modelo anda em malha aberta, com o volante, o acelerador e o freio gravados, sem olhar o estado gravado no caminho.
- **A correção:** um Processo Gaussiano por grandeza, treinado em 2.000 passos por rodada (400 de cada regime; todos os regimes tinham mais de 400). Ajustar os três leva de 68 a 89 s por rodada.
- **Comandos:** `python -m ml.scripts.m1_modelo_carro validar --fase treino` e, depois do commit da fase de treino, `validar --fase teste` (10 min).

### 6.2 O veredito (todos em 0,5 s)

| nº | critério | medido | resultado |
|---|---|---|---|
| 1 | skill contra R0 ≥ 0,50 | **0,202** | **não passa** |
| 2 | skill contra R1 ≥ 0,20 | **0,174** | **não passa** |
| 3 | limite inferior do IC 95% do skill contra R1 > 0 | 0,159 (IC de 0,159 a 0,191; 57 voltas, 2.000 reamostragens) | passa |
| 4 | skill contra R1 positivo em pelo menos 4 das 5 sessões | 5 de 5 | passa |
| 5 | \|viés\| de cada grandeza ≤ 25% do erro de R1 | `vx` 3,9%; `vy` 2,2%; `r` 3,3% | passa |
| 6 | o intervalo de 90% cobre de 80% a 97%, no passo de Δt | 85,7% (`vx` 93,2%; `vy` 81,5%; `r` 82,5%) | passa |
| 7 | pelo menos 5 sessões testáveis | 5 | passa |

- **O erro combinado em 0,5 s:** M1 0,351; R1 (só a física) 0,425; R0 (persistência) 0,440.
- **Pela regra do ADR 0022, a M1 não é aprovada.** Também não vale o caso "só a física passa": a física sozinha bate a persistência por só 3% em 0,5 s.

### 6.3 Os horizontes e cada grandeza

| horizonte | erro M1 / R1 / R0 | skill M1 contra R0 | skill M1 contra R1 | skill R1 contra R0 |
|---|---|---:|---:|---:|
| 0,25 s | 0,189 / 0,212 / 0,270 | 0,30 | 0,11 | 0,22 |
| **0,5 s** | **0,351 / 0,425 / 0,440** | **0,20** | **0,17** | **0,03** |
| 1,0 s | 0,849 / 1,059 / 0,666 | −0,27 | 0,20 | −0,59 |

| em 0,5 s | `vx` (m/s): raiz do erro quadrático, viés | `vy` (m/s) | `r` (rad/s) | posição (m): média, p90 |
|---|---|---|---|---|
| M1 | 0,40; −0,03 | 0,68; +0,02 | 0,094; −0,004 | 0,13; 0,27 |
| R1 | 0,85; **+0,68** | 0,84; −0,07 | 0,108; +0,012 | 0,26; 0,44 |
| R0 | 2,69; +0,03 | **0,70**; +0,01 | 0,174; 0,000 | 0,58; 1,11 |

- **Na velocidade longitudinal,** a correção tira o viés da física (+0,68 m/s, o carro previsto mais rápido que o gravado em 0,5 s) e corta o erro pela metade.
- **Na guinada,** a M1 é a melhor das três.
- **Na velocidade lateral, a M1 só empata com a persistência** (0,68 contra 0,70 m/s), e é ela que pesa no erro combinado, porque tem o menor desvio-padrão (cerca de 1,25 m/s). Em 1,0 s, a lateral da M1 erra 1,77 m/s, contra 1,03 da persistência.
- **A posição** sai melhor na M1 em todos os horizontes: 0,13 m de erro médio em 0,5 s e 0,53 m em 1,0 s.

### 6.4 Por sessão, por regime e por velocidade (0,5 s)

| sessão | casos | skill M1 contra R0 | skill M1 contra R1 | skill R1 contra R0 |
|---|---:|---:|---:|---:|
| `2026-10-15_23-24-50` | 8.438 | 0,16 | 0,15 | 0,01 |
| `2026-10-17_01-02-22` | 9.420 | 0,20 | 0,16 | 0,05 |
| `2026-10-17_16-17-08` | 10.314 | 0,34 | 0,20 | 0,18 |
| `2026-10-18_12-38-44` | 5.125 | 0,14 | 0,20 | −0,07 |
| `2026-10-21_20-30-54` | 5.845 | 0,15 | 0,18 | −0,04 |

| regime | casos | erro M1 / R1 / R0 | skill M1 contra R0 | skill M1 contra R1 |
|---|---:|---|---:|---:|
| reta | 6.953 | 0,076 / 0,080 / 0,226 | 0,66 | 0,05 |
| freada | 2.936 | 0,134 / 0,139 / 0,422 | 0,68 | 0,04 |
| tração | 1.725 | 0,111 / 0,110 / 0,387 | 0,71 | −0,01 |
| **curva** | **25.251** | **0,412 / 0,505 / 0,474** | **0,13** | **0,19** |
| freio e volante juntos | 2.277 | 0,431 / 0,473 / 0,578 | 0,25 | 0,09 |

| faixa de velocidade | casos | skill M1 contra R0 | skill M1 contra R1 |
|---|---:|---:|---:|
| abaixo de 100 km/h | 4.718 | 0,22 | 0,21 |
| 100 a 160 km/h | 13.779 | 0,24 | 0,21 |
| 160 a 220 km/h | 12.580 | 0,08 | 0,12 |
| acima de 220 km/h | 8.064 | 0,55 | −0,03 |

- **Fora das curvas** (reta, freada e tração), a física sozinha já passa a persistência com folga (skill de 0,65 a 0,72), e a correção quase não muda nada.
- **Nas curvas**, que são 65% dos casos, a física perde para a persistência (skill −0,07), e a correção a leva só a 0,13. É aí que a M1 não passa. A pior faixa é a de 160 a 220 km/h, a das curvas rápidas.
- **Um caso** (sessão `2026-10-17_16-17-08`, volta 12) começa com `vx` de −0,7 km/h e fica fora das faixas de velocidade.

### 6.5 "Não conclusivo": o corte não funcionou

- **O corte saiu 1,000 nas 5 rodadas, e nenhum caso de teste foi marcado.** O índice registrado (1.6) vai de 0 a 1 e chega a 1 em mais de 1% dos casos de treino, então o percentil 99 dele é o próprio teto, e nada fica acima.
- **Por quê:** o índice é o maior das 3 grandezas e dos 10 passos do caminho. O Processo Gaussiano da velocidade longitudinal aprendeu comprimentos muito curtos em algumas entradas (perto de 1 desvio-padrão), e os da velocidade lateral e da guinada aprenderam comprimentos ainda mais curtos (de 0,06 a 0,45 desvio-padrão) na velocidade lateral, na guinada e no volante. Assim, um caminho de 0,5 s sai do que o treino cobriu em quase qualquer lugar.
- **Isso não muda o veredito:** as métricas da aprovação usam todos os casos (1.6), e os resultados "só nos conclusivos" são os mesmos.
- **O que isso quer dizer:** com o índice como registrado, a M1 não sabe dizer quando está fora dos dados. Corrigir isso é uma mudança da regra e fica para depois.

### 6.6 As figuras

Na rodada em que a sessão `2026-10-21_20-30-54` é a de teste, volta 6, com a faixa de 5% a 95% da M1 (200 caminhos):

- **a freada da C01** (`docs/handoff/2026-10-25_39_m1-geometria-medida_figura_c01.png`), a 266 km/h: a M1 segue o gravado quase em cima da linha. Em 0,5 s, ela erra a velocidade em 0,08 m/s; a física sozinha, em 0,71 m/s; a persistência, em 7,2 m/s;
- **a curva lenta, a C10** (`..._figura_c10.png`), a 76 km/h, com o volante em 0,87 (perto do batente): a física e a M1 fazem o carro escorregar para fora (`vy` sobe a 1,5 m/s em 0,5 s e a 3,5 m/s em 1,0 s) e exageram a guinada. No gravado, o carro faz a curva com `vy` perto de zero. A faixa de incerteza cobre o gravado, mas é larga. É o retrato do que falha nas curvas: com muito volante, a física prevê uma derrapagem que o carro do jogo não faz.

### 6.7 Indicação para a M2: o resíduo e a temperatura dos pneus

Só a correlação de Spearman entre o resíduo da M1 no primeiro passo e a temperatura média dos 4 pneus, nos 39.142 casos:

| grandeza | Spearman |
|---|---:|
| `vx` | **−0,22** |
| `vy` | 0,00 |
| `r` | −0,01 |

- **Na velocidade longitudinal há uma correlação clara:** com os pneus mais quentes, o carro desacelera um pouco mais do que a M1 prevê (ou acelera menos). A temperatura também muda ao longo da sessão, junto com o combustível e o desgaste, então isso não separa a causa.
- **Na lateral e na guinada, nada.** A falha da M1 nas curvas não parece vir da temperatura.

### 6.8 O que o resultado quer dizer

- **Para quem não é da área:** o modelo acerta bem o que o carro faz em reta, na freada e na aceleração. Ele erra quando o carro está virando, principalmente com muito volante, porque o pneu do jogo segura o carro de um jeito que a física simples não descreve. A correção aprendida dos dados ajuda, mas não o bastante para o critério.
- **Pela regra do ADR 0022:** a M1 não vira a base da etapa M4 nem do cálculo do tempo de volta. O simulador quase-estacionário continua como está, e o ADR 0004 continua valendo.
- **Nenhum critério, corte ou parâmetro foi mudado depois de ver o teste.**
