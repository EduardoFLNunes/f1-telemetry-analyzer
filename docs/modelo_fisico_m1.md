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

## 7. M1 v2 (pedido 46; ADR 0028)

**A M1 v2 é a segunda e última tentativa da M1 neste TCC.** Ela foi desenhada depois de ver o teste da v1, com o diagnóstico dela (as curvas, a velocidade lateral, a C10), e é testada nas mesmas sessões, com os mesmos 7 critérios do ADR 0022. Se não passar, não há v3 ajustada nas mesmas sessões. A v1 (seções 1 a 6) fica como está, como resultado negativo, e aparece ao lado da v2 em todas as tabelas.

### 7.1 Registrado antes de rodar (Parte A)

O registro completo, com as fórmulas, as faixas e os porquês, está no **ADR 0028**, commitado antes de qualquer conta nas sessões. Em resumo, o que muda da v1:

| | v1 | v2 |
|---|---|---|
| rodas | bicicleta: as duas rodas de cada eixo viram uma | quatro rodas, cada uma com o seu ângulo de deriva, a sua carga e a sua força; o momento de guinada inclui os lados |
| carga | por eixo: peso parado, downforce e transferência longitudinal (pela regra dos 2%) | por roda: o mesmo, com a transferência longitudinal sempre, mais a transferência lateral `λ·h_y·a_y/t` em cada eixo, com `λ` e `h_y` medidos contra `wheel_load_*` |
| atrito | `μ` constante | `μ(n) = μ_ref·(n/n_ref)^(q−1)`, `n_ref = g/4`, `q` de 0,6 a 1,0 |
| curva do pneu | `tanh`: satura e fica no máximo | Fórmula Mágica de Pacejka sem deslocamentos: pico em `α_pico` (3° a 12°) e queda até `f` (0,7 a 1,0); a mesma rigidez `C_α·n` da v1 |
| elipse de atrito | por eixo | por roda |
| parâmetros ajustados | 7 | 10 (`μ` vira `μ_ref` e `q`; entram `α_pico` e `f`) |
| amostra da correção | 2.000 passos, 400 por regime, semente 37 | 6.000 passos, na proporção dos regimes no treino, semente 46 |
| "não conclusivo" | o desvio do Processo Gaussiano sem o ruído, o maior de 3 grandezas e 10 passos; o corte saiu no teto | a distância média aos 10 vizinhos de treino nas 6 entradas; o corte é o percentil 99 nos casos de treino, sem os vizinhos da mesma volta |
| critérios | os 7 do ADR 0022 | os mesmos 7, com R1 sendo a física v2; a física v1 entra como terceira referência, só relatada |

**O que se espera, escrito antes de rodar (ADR 0028, item 9):** a v2 deve ganhar nas curvas, mais na faixa de 160 a 220 km/h, e na velocidade lateral; na reta, na freada e na tração ela não deve mudar. O critério 1 é o mais difícil, e não há garantia de que a v2 passe.

**Comandos:** `python -m ml.scripts.m1_modelo_carro validar-v2 --fase treino` (Parte B) e, depois do commit da fase de treino, `validar-v2 --fase teste` (Parte C). Os arquivos da v1 em `data/ml/modelo_carro/` não são sobrescritos: os da v2 levam o sufixo `_v2`.

### 7.2 A carga e o pneu medidos (Parte B)

Comando: `python -m ml.scripts.m1_modelo_carro validar-v2 --fase treino` (1 h 35 min), só com as 4 sessões de treino de cada rodada. JSON: `docs/handoff/2026-11-07_46_m1-v2-e-modelo1-final_fisica_treino_v2.json`.

**A carga lateral é identificável nas 5 rodadas,** então a parada da B.5 não se aplica:

| rodada (sessão de fora) | `λ` (fração na frente) | `h_y` (m) | IC 95% de `c_f` | IC 95% de `c_r` |
|---|---:|---:|---|---|
| `2026-10-15_23-24-50` | 0,647 | 0,324 | 0,262 a 0,267 | 0,149 a 0,154 |
| `2026-10-17_01-02-22` | 0,647 | 0,329 | 0,266 a 0,271 | 0,151 a 0,156 |
| `2026-10-17_16-17-08` | 0,651 | 0,363 | 0,295 a 0,301 | 0,165 a 0,171 |
| `2026-10-18_12-38-44` | 0,647 | 0,334 | 0,270 a 0,276 | 0,153 a 0,159 |
| `2026-10-21_20-30-54` | 0,645 | 0,322 | 0,260 a 0,264 | 0,149 a 0,154 |

- **`λ` e `h_y` ficam dentro das faixas** (0,30 a 0,70 e 0,15 a 0,45 m) nas 5 rodadas, e nenhum intervalo passa de zero. O intervalo de 95% de `λ` tem cerca de ±0,005.
- **`h_y` sai de 19% a 34% acima do `cgHeight`** (0,271 m). Parte disso vem da massa: ela é a das regressões da v1 (578 a 653 kg, abaixo da faixa), e as cargas por unidade de massa saem infladas na mesma proporção. A sessão de 17/10 16:17, a de massa mais baixa (578 kg), é a de `h_y` mais alto.
- **Cerca de 65% da transferência lateral vai para a frente.**
- **O erro da carga prevista** (com `vx`, `a_x` e `a_y` gravados) contra `wheel_load_*`:
  - no geral, fica entre 18% e 24% da carga média de cada roda;
  - na reta, entre 16% e 17%;
  - é maior na roda dianteira esquerda nas curvas (26% a 28%).

  A carga gravada oscila com as zebras e as ondulações, e o modelo de carga não tem suspensão.

**O pneu ajustado (10 parâmetros):**

| parâmetro | faixa nas 5 rodadas | no limite? |
|---|---|---|
| `C_α` (1/rad) | 30,4 a 34,8 | não |
| `μ_ref` | 2,10 a 2,23 | não |
| `q` | 0,600 nas 5 | **sim, no limite de baixo** |
| `α_pico` | 12,0° nas 5 | **sim, no limite de cima** |
| `f` | 0,700 nas 5 | **sim, no limite de baixo** |
| `k²` (m²) | 2,08 a 3,03 | não |
| `κ_D` (1/m) | 0,0003 nas 5 | sim, no limite de baixo (como na v1) |
| `c0` (m/s²) | 0 a 0,43 | no limite de baixo em 3 rodadas (como na v1) |
| `s_T` | 0,82 a 1,04 | não |
| `β_B` (m/s²) | 24,5 a 25,7 | não |

- **A figura** (`docs/handoff/2026-11-07_46_m1-v2-e-modelo1-final_curva_do_pneu.png`) mostra o porquê dos limites:
  - os pontos das sessões de treino quase não passam de 6° de deriva;
  - o ajuste empurra o pico para o fim da faixa (12°), fora dos dados, e com ele a queda (`f`) fica sem efeito onde há dados;
  - dentro dos dados, a curva sobe e satura, como a da v1.
- **O que pesa é a sensibilidade à carga.** Com `q = 0,6`, o atrito cai de 2,2 com a roda parada para cerca de 1,4 a 1,6 a 270 km/h, e a curva fica mais baixa em alta velocidade. Os pontos de treino mostram o mesmo: a força por carga satura mais baixo em alta velocidade.
- **`q` no limite de 0,6** quer dizer que os dados pediriam um expoente ainda menor. A faixa foi registrada antes e não muda.

**A física v2 sozinha nas sessões de treino (B.4), antes de qualquer teste:**

| rodada | erro de um passo: v2 / v1 / R0 | skill v2 contra R0 em 0,5 s | skill v2 contra a v1 em 0,5 s | v1 contra R0 em 0,5 s (pedido 39) |
|---|---|---:|---:|---:|
| `2026-10-15_23-24-50` | 0,0749 / 0,0783 / 0,0887 | 0,356 | 0,338 | 0,027 |
| `2026-10-17_01-02-22` | 0,0772 / 0,0809 / 0,0929 | 0,391 | 0,364 | 0,043 |
| `2026-10-17_16-17-08` | 0,0745 / 0,0788 / 0,0912 | 0,394 | 0,259 | 0,183 |
| `2026-10-18_12-38-44` | 0,0769 / 0,0804 / 0,0901 | 0,320 | 0,319 | 0,002 |
| `2026-10-21_20-30-54` | 0,0777 / 0,0804 / 0,0904 | 0,212 | 0,253 | −0,056 |

Nas curvas das sessões de treino, o erro em 0,5 s da física v2 fica entre 0,30 e 0,42. O da v1 fica entre 0,42 e 0,56, e o da persistência entre 0,46 e 0,49.

### 7.3 A validação e o veredito (Parte C)

Comando: `python -m ml.scripts.m1_modelo_carro validar-v2 --fase teste` (1 h 34 min), rodado depois do commit da fase de treino. Os casos são os mesmos 39.142 da v1, conferidos caso a caso. JSON: `docs/handoff/2026-11-07_46_m1-v2-e-modelo1-final_validacao_v2.json`.

**Em uma frase: a M1 v2 não foi aprovada, por pouco.** Em 0,5 s, ela corta 48,7% do erro da persistência, e o critério 1 pede 50%. Os outros 6 critérios passam, inclusive o 2, que a v1 não passava.

| nº | critério | v1 (pedido 39) | **v2** | resultado da v2 |
|---|---|---|---|---|
| 1 | skill contra R0 ≥ 0,50 | 0,202 | **0,487** | **não passa** |
| 2 | skill contra R1 ≥ 0,20 | 0,174 | **0,207** | passa |
| 3 | limite inferior do IC 95% do skill contra R1 > 0 | 0,159 | 0,172 (IC de 0,172 a 0,245) | passa |
| 4 | skill contra R1 positivo em pelo menos 4 das 5 sessões | 5 | 5 | passa |
| 5 | \|viés\| ≤ 25% do erro de R1 (`vx` / `vy` / `r`) | 3,9% / 2,2% / 3,3% | 1,9% / 0,4% / 2,8% | passa |
| 6 | o intervalo de 90% cobre de 80% a 97% | 85,7% | 89,6% (`vx` 91,3%; `vy` 88,9%; `r` 88,5%) | passa |
| 7 | pelo menos 5 sessões testáveis | 5 | 5 | passa |

- **Pela regra do ADR 0022, a M1 v2 não é aprovada.** O caso "só a física passa" também não vale: a física v2 sozinha corta 35% do erro da persistência, e o critério 1 pede 50%.
- **Nenhum critério, corte ou parâmetro foi mudado depois de ver o teste.** Pelo ADR 0028, item 1, não há v3.

**Os horizontes, lado a lado (erro combinado):**

| horizonte | M1 v2 | física v2 (R1) | M1 v1 | física v1 | R0 | skill M1 v2 contra R0 | skill M1 v1 contra R0 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0,25 s | 0,153 | 0,178 | 0,189 | 0,212 | 0,270 | 0,43 | 0,30 |
| **0,5 s** | **0,226** | **0,285** | **0,351** | **0,425** | **0,440** | **0,49** | **0,20** |
| 1,0 s | 0,378 | 0,500 | 0,849 | 1,059 | 0,666 | 0,43 | −0,27 |

- **Em 1,0 s, a v2 continua melhor que a persistência** (skill de 0,43). A v1 ficava pior (−0,27).
- **Em 0,5 s, a física v2 sozinha corta 33% do erro da física v1,** e a M1 v2 corta 36% do erro da M1 v1.

**Cada grandeza em 0,5 s** (raiz do erro quadrático; viés):

| | `vx` (m/s) | **`vy` (m/s)** | `r` (rad/s) |
|---|---|---|---|
| M1 v2 | 0,39; −0,01 | **0,42; 0,00** | 0,070; −0,002 |
| física v2 | 0,73; +0,46 | 0,55; −0,10 | 0,077; +0,015 |
| M1 v1 | 0,40; −0,03 | 0,68; +0,02 | 0,094; −0,004 |
| física v1 | 0,85; +0,68 | 0,84; −0,07 | 0,108; +0,012 |
| R0 | 2,69; +0,03 | 0,70; +0,01 | 0,174; 0,000 |

- **A velocidade lateral é onde a v2 mais ganha:**
  - no geral, 0,42 m/s, contra 0,68 da M1 v1 e 0,70 da persistência;
  - nas curvas, 0,48 contra 0,81 e 0,78.

  A v1 só empatava com a persistência nessa grandeza.
- **Na longitudinal, a v2 e a v1 ficam iguais** (0,39 e 0,40 m/s). A física v2 ainda prevê o carro mais rápido que o gravado (+0,46 m/s em 0,5 s), e a correção tira esse viés, como na v1.

**Por sessão, por regime e por faixa de velocidade** (skill em 0,5 s):

| sessão | casos | M1 v2 contra R0 | física v2 contra R0 | M1 v1 contra R0 | M1 v2 contra a física v2 |
|---|---:|---:|---:|---:|---:|
| `2026-10-15_23-24-50` | 8.438 | 0,50 | 0,35 | 0,16 | 0,22 |
| `2026-10-17_01-02-22` | 9.420 | 0,51 | 0,38 | 0,20 | 0,20 |
| `2026-10-17_16-17-08` | 10.314 | 0,55 | 0,48 | 0,34 | 0,15 |
| `2026-10-18_12-38-44` | 5.125 | 0,45 | 0,29 | 0,14 | 0,23 |
| `2026-10-21_20-30-54` | 5.845 | 0,41 | 0,25 | 0,15 | 0,21 |

| regime | casos | M1 v2 contra R0 | física v2 contra R0 | M1 v1 contra R0 | física v2 contra a física v1 |
|---|---:|---:|---:|---:|---:|
| reta | 6.953 | 0,68 | 0,66 | 0,66 | 0,03 |
| freada | 2.936 | 0,71 | 0,68 | 0,68 | 0,04 |
| tração | 1.725 | 0,73 | 0,71 | 0,71 | −0,01 |
| **curva** | **25.251** | **0,46** | **0,30** | **0,13** | **0,34** |
| freio e volante juntos | 2.277 | 0,45 | 0,43 | 0,25 | 0,31 |

| faixa | casos | M1 v2 contra R0 | física v2 contra R0 | M1 v1 contra R0 | física v2 contra a física v1 |
|---|---:|---:|---:|---:|---:|
| abaixo de 100 km/h | 4.718 | 0,44 | 0,39 | 0,22 | 0,37 |
| 100 a 160 km/h | 13.779 | 0,49 | 0,34 | 0,24 | 0,32 |
| **160 a 220 km/h** | **12.580** | **0,49** | **0,31** | **0,08** | **0,34** |
| acima de 220 km/h | 8.064 | 0,58 | 0,54 | 0,55 | −0,06 |

- **O que se esperava (7.1) se confirmou:**
  - o ganho está nas curvas, onde a física v2 corta 34% do erro da v1;
  - na faixa de 160 a 220 km/h, o skill contra a persistência sobe de 0,08 para 0,49;
  - na velocidade lateral, como mostra a tabela anterior;
  - na reta, na freada e na tração, nada mudou.
- **O que não passa:** as curvas continuam abaixo de 0,50 (0,46), e elas são 65% dos casos. Duas sessões passam de 0,50 sozinhas (17/10 01:02 e 17/10 16:17), e a de 21/10 fica em 0,41.

**O "não conclusivo", pela regra nova:**

- o corte ficou entre 0,79 e 0,87 nas 5 rodadas;
- **443 dos 39.142 casos (1,1%) foram marcados;**
- por regime: 0,3% na reta, 0,6% na freada, 0,5% na tração, 1,2% nas curvas e 4,5% com freio e volante juntos. Abaixo de 100 km/h, 4,7%;
- por sessão: de 0,6% (17/10 01:02) a 2,3% (21/10);
- nos casos conclusivos, o erro em 0,5 s é 0,201 na M1 v2, 0,264 na física v2 e 0,415 em R0.

**A regra funciona como foi pensada:** ela marca perto de 1% dos casos, e mais onde o piloto faz coisas raras.

**As figuras** (rodada sem 21/10, volta 6, com a faixa de 5% a 95% da M1 v2):

- **a freada da C01** (`..._figura_c01_v2.png`), a 266 km/h. O erro da velocidade em 0,5 s:
  - M1 v2: 0,14 m/s;
  - física v2: −0,37;
  - M1 v1: 0,08;
  - física v1: 0,71;
  - persistência: 7,2.
- **a curva lenta, a C10** (`..._figura_c10_v2.png`), a 76 km/h, com o volante em 0,87. **A v2 escorrega bem menos que a v1:**
  - em 0,5 s, `vy` sai 0,62 m/s acima do gravado na M1 v2, contra 1,47 na M1 v1;
  - em 1,0 s, 1,4 m/s contra 3,5.

  O carro do jogo ainda faz a curva com `vy` perto de zero, e a v2 também exagera a guinada. O retrato da falha da v1 melhorou, mas não sumiu.

**Só para informação, fora do veredito (C.4):** os modelos da rodada sem 21/10 (treinados nas sessões de 15/10 a 18/10), nas voltas rotuladas no pedido 44.

| sessão | voltas | casos | erro em 0,5 s: M1 v2 / física v2 / física v1 / R0 | skill M1 v2 contra R0 | `vy` (m/s): M1 v2 / R0 |
|---|---:|---:|---|---:|---|
| `2026-10-24_13-26-12` | 3 | 1.807 | 0,255 / 0,411 / 0,609 / 0,438 | 0,42 | 0,47 / 0,66 |
| `2026-10-24_13-43-32` | 6 | 3.930 | 0,291 / 0,444 / 0,608 / 0,496 | 0,41 | 0,55 / 0,78 |
| `2026-11-01_19-47-03` | 6 | 4.468 | 0,366 / 0,452 / 0,530 / 0,415 | 0,12 | 0,73 / 0,61 |

Em 24/10, a v2 se comporta como nas sessões de teste. Em 01/11 ela piora: nessa sessão, a persistência prevê a velocidade lateral melhor que a M1 v2.

**A temperatura dos pneus (indicação para a M2):** o Spearman entre o resíduo de um passo e a temperatura média dos pneus dá −0,22 na longitudinal, 0,01 na lateral e −0,01 na guinada, como na v1.

**O que o resultado quer dizer:**

- **Para quem não é da área:** a segunda versão do modelo prevê o carro bem melhor que a primeira, principalmente nas curvas e no quanto ele escorrega de lado. Ela erra metade do que erraria quem dissesse "o carro continua como está", e o critério pede um pouco mais que isso. Pela regra combinada antes, ela não passa.
- **Pela regra do ADR 0022:** a M1 não vira a base da etapa M4 nem do medidor do tempo. Pelo ADR 0028, este é o fim da M1 neste TCC.

### 7.4 O Modelo 1 com a M1 v2 reprovada (Parte D)

Como a M1 v2 não foi aprovada, o medidor do Modelo 1 continua sendo o simulador quase-estacionário com o envelope das voltas reais. O resultado final do Modelo 1 está em `docs/arquitetura_ml.md`, na seção "O medidor do tempo e o resultado final do Modelo 1".

### 7.5 Diagnóstico da M1 v2 (pedido 48)

**O que é:** uma análise de onde e por que a M1 v2 errou, com os modelos do pedido 46 sem mudança. **Nenhum modelo novo é ajustado, nenhum parâmetro é reajustado e nenhum veredito muda.** O ADR 0028, item 1, continua valendo: a v2 foi a última tentativa nas mesmas sessões de teste. Os dados de manobra e um modelo novo ficam como trabalhos futuros (7.5.4).

#### 7.5.1 Registrado antes de calcular (Parte A)

Esta subseção foi commitada antes de qualquer conta nas sessões, inclusive a reprodução da Parte B. **Nenhuma regra muda depois de ver os números.**

**As definições comuns:**

- **Os modelos e os casos são os do pedido 46:** as 5 rodadas, os 39.142 casos, as 3 grandezas normalizadas pelo desvio-padrão do treino de cada rodada e o erro combinado da seção 1.7. O **skill** é sempre o da M1 v2 contra a persistência (R0) em 0,5 s (10 passos), salvo quando outro modelo ou horizonte é dito.
- **A reprodução:** os parâmetros da física de cada rodada vêm de `rodadas_treino_v2.json`. Os Processos Gaussianos não foram salvos pelo pedido 46. Por isso, são reajustados pela função `fase_teste` do pedido 46, sem mudança: o mesmo código, a mesma amostra (6.000 passos, semente 46) e o mesmo núcleo. Até 0,002 de diferença nos números da seção 7.3, o trabalho segue; acima disso, para.
- **A deriva estimada** de cada roda vem do estado gravado e da geometria medida de cada rodada, pela fórmula do ADR 0028, item 3. A fórmula é `α_i = δ_i − atan2(vy + x_i·r, vx − y_i·r)`, com:
  - `vy` levada ao centro de massa, como no modelo;
  - `δ = −k_δ·steer` nas duas rodas da frente e `δ = 0` atrás;
  - `vx` de pelo menos 5 m/s.

  Ela não usa o modelo do pneu. **A deriva de um eixo** é a média das duas rodas, e as faixas usam o módulo, em graus.
- **As faixas:**
  - de velocidade, as da seção 7.3 (`vx` no início: abaixo de 100 km/h, 100 a 160, 160 a 220 e acima de 220);
  - de |`steer`|: 0 a 0,1, 0,1 a 0,2, 0,2 a 0,4, 0,4 a 0,6 e acima de 0,6;
  - de deriva: abaixo de 3°, 3° a 6°, 6° a 8°, 8° a 10° e acima de 10°;
  - de |`a_y`|: abaixo de 0,5 g (só fora das curvas), 0,5 a 1,0 g, 1,0 a 1,5, 1,5 a 2,0 e acima de 2,0;
  - da taxa do volante, |d`steer`/dt| (diferença central na grade de 50 ms, dentro do trecho): os tercis de todos os passos das 4 sessões de treino de cada rodada.
- **As curvas e as fases:** as 14 curvas (C01 a C14) de `detect_corners` na geometria do store v2 (`0ed16f0dd2225990`), pelo `s` do início do caso. A **entrada** vai do início da curva ao ápice, e a **saída**, do ápice ao fim. Um caso fora de todas as curvas fica em "fora".
- **A parte de um grupo no erro:** a soma do erro quadrático normalizado da M1 v2 em 0,5 s nos casos do grupo, dividida pela soma no conjunto de referência (as curvas, por exemplo). As partes somam 100%.
- **As curvas, nas regras abaixo,** são os casos do regime "curva" (seção 1.5) no início. Freio e volante juntos são relatados à parte, com as mesmas tabelas.

**As hipóteses e as regras.** Cada hipótese recebe um rótulo: **apoiada, não apoiada ou inconclusiva.** O que não for nem apoiada nem não apoiada é inconclusiva. Uma hipótese sem dados, por um canal não gravado, é "sem dados", com o motivo.

| | hipótese | evidência | apoiada | não apoiada |
|---|---|---|---|---|
| H1 | **o pico do pneu:** os casos com deriva alta concentram o erro das curvas | C.2, C.6 | o skill acima de 6° fica pelo menos 0,15 abaixo do skill abaixo de 3°, e as faixas acima de 6° têm pelo menos 15% do erro das curvas | a diferença fica abaixo de 0,05 |
| H2 | **a relaxação do pneu:** o carro do jogo responde ao volante com um atraso que a física não tem | C.3 | o atraso a mais tem o IC 95% acima de +10 ms em pelo menos 3 das 4 faixas de velocidade, e o produto do atraso a mais pela velocidade fica a até ±35% da mediana dele nessas faixas | o atraso a mais fica abaixo de 10 ms em todas as faixas |
| H3 | **a direção:** o ângulo da roda não é linear no volante (Ackermann, complacência), e isso erra com muito volante | C.4 | o ganho efetivo com \|`steer`\| ≥ 0,4 difere pelo menos 15% do ganho com \|`steer`\| < 0,2, e o erro de `r` em 0,5 s com \|`steer`\| ≥ 0,4 fica pelo menos 1,5 vez a mediana das curvas | a diferença fica abaixo de 5% |
| H4 | **a carga:** a aerodinâmica muda com a altura do carro (e com o DRS), e o modelo de carga não tem isso | C.5 | a altura e a velocidade explicam pelo menos 30% da variância do resíduo da carga de cada eixo, e o skill no quartil de maior erro de carga fica pelo menos 0,10 abaixo do quartil de menor | menos de 10% e diferença abaixo de 0,05 |
| H5 | **o acúmulo no horizonte:** o ajuste mira um passo, e o erro cresce ao realimentar o próprio estado | C.7 | a razão de acúmulo nas curvas é pelo menos 1,3 | a razão fica até 1,1 |
| H6 | **a correção sem memória:** o resíduo depende do que aconteceu antes, e o Processo Gaussiano só vê o passo atual | C.7 | a autocorrelação do resíduo de um passo no atraso 1 é pelo menos 0,5 em `vy` ou em `r`, nas curvas | fica até 0,2 nas duas |
| H7a | **01/11, a pilotagem:** a queda vem de mais escorregamento | C.8 | nos casos com deriva abaixo de 3°, o skill de 01/11 fica a até 0,10 do de 24/10 nos mesmos casos | o H7b é apoiado |
| H7b | **01/11, o carro ou o jogo mudou** (CSP 0.3.1 ou outra condição) | C.8 | nesses casos, o skill de 01/11 fica mais de 0,20 abaixo do de 24/10 | o H7a é apoiado |

**Como cada regra é medida.** Onde o pedido deixa uma escolha, ela é fixada aqui, antes das contas:

- **H1:** a deriva no início do caso, nas curvas.
  - A regra é aplicada à deriva do eixo dianteiro e à do traseiro, separadamente.
  - É **apoiada** se as duas condições valem em pelo menos um eixo, e **não apoiada** se a diferença de skill (abaixo de 3° menos acima de 6°) fica abaixo de 0,05 nos dois eixos.
  - Uma faixa com menos de 100 casos tem o skill relatado, mas não decide. Se a faixa acima de 6° tiver menos de 100 casos nos dois eixos, a H1 é inconclusiva.
- **H2:** o atraso de cada faixa é o pico da correlação entre a taxa do volante e a taxa da guinada (d`r`/dt), somada em todas as entradas da faixa.
  - **O atraso a mais** é o atraso do gravado menos o da física v2, os dois calculados do mesmo jeito. A guinada passa pela grade de 50 ms (o gravado nos instantes da grade, a física no próprio passo) e volta a 5 ms por interpolação linear. A taxa do volante é a das amostras cruas reamostradas a 5 ms.
  - O atraso do gravado direto a 5 ms também é relatado. A diferença entre as duas versões do gravado mede o efeito da grade.
  - A velocidade de cada faixa, para o produto, é a média de `vx` nas entradas dela. Uma faixa com menos de 20 entradas não decide.
  - **A entrada de cada passo** do modelo é a média das entradas em `k` e `k+1`, e a física integra o passo inteiro com ela. O teste da Parte E confere quanto isso desloca o atraso medido de um sistema de primeira ordem rodado na mesma grade.
  - **Emenda de 09/11, antes de qualquer conta nas sessões:** a frase anterior dizia que a entrada média "não atrasa nem adianta a resposta". O teste sintético da Parte E mostrou que isso só vale para dinâmicas lentas. Num sistema de primeira ordem com constante de tempo τ, rodado na grade de 50 ms com a entrada média, o atraso medido sobe em relação ao do sistema contínuo amostrado na mesma grade:

    | τ | 10 ms | 20 ms | 40 ms | 80 ms | 150 ms | 300 ms |
    |---|---:|---:|---:|---:|---:|---:|
    | atraso a mais criado pela grade | 16,1 ms | 10,0 ms | 5,6 ms | 2,9 ms | 1,7 ms | 1,1 ms |

    Com τ curto, a resposta chega ao fim dentro do passo e reflete a entrada do meio do passo, que é meio passo (25 ms) mais velha. **A regra da H2 não muda.** O atraso a mais continua sendo o gravado na grade menos a física v2. Esse efeito faz parte do modelo da M1, que anda na grade, e puxa o atraso a mais para baixo, o que é relatado junto com o resultado.
  - **Uma entrada de curva** começa no instante em que |`steer`| passa de 0,1 para cima, desde que |`steer`| suba nos quatro intervalos de 50 ms seguintes (0,2 s). Ela é procurada nas voltas válidas das 5 sessões, e o trecho de amostras cruas (intervalos de até 20 ms) tem de cobrir de 0,5 s antes a 1,2 s depois.
  - A correlação usa a janela de 0,25 s antes a 0,75 s depois do início. Cada sessão usa os modelos da rodada em que ela é a de teste.
- **H3:** o ganho efetivo `k_ef` sai da regressão de `L·r/vx` contra `−steer`, com um `k_ef` por faixa de |`steer`| e um `K` comum multiplicando `−a_y`, e com o `L` medido.
  - **As amostras** são as quase estacionárias das 5 sessões: |d`r`/dt| < 0,1 rad/s², taxa do volante no tercil de baixo de todos os passos das 5 sessões e `vx` ≥ 10 m/s.
  - **A regra usa a regressão com todas as velocidades juntas;** as regressões por faixa de velocidade são relatadas.
  - O ganho com \|`steer`\| ≥ 0,4 é a média dos `k_ef` das faixas de 0,4 a 0,6 e acima de 0,6, pesada pelo número de amostras. O ganho com \|`steer`\| < 0,2 é a média das faixas de 0 a 0,1 e de 0,1 a 0,2. Só entram faixas com pelo menos 200 amostras.
  - O erro de `r` é o módulo do erro da M1 v2 em 0,5 s. A regra compara a mediana dele nos casos de curva com \|`steer`\| ≥ 0,4 com a mediana em todos os casos de curva.
- **H4:** o resíduo da carga de um eixo é a soma das duas rodas, prevista menos gravada, em N. A carga prevista vem da conta da seção 7.2, com os parâmetros de cada rodada, nos passos das sessões de teste.
  - O R² é o da regressão linear com intercepto e os termos `rideHeight_f`, `rideHeight_r`, `vx²`, `vx²·rideHeight_f` e `vx²·rideHeight_r`. A regra pede pelo menos 30% nos dois eixos para apoiada, e menos de 10% nos dois para não apoiada.
  - Uma segunda regressão, com o `suspensionTravel` das 4 rodas a mais, é relatada sem decidir.
  - **O erro de carga no início do caso** é a soma, nas 4 rodas, de \|prevista − gravada\|, dividida pela soma das cargas gravadas. Os quartis são os de todos os casos, e o skill é o de todos os casos de cada quartil.
- **H5:** a razão de acúmulo é o erro combinado da M1 v2 em 0,5 s em malha aberta, dividido pelo erro combinado em 0,5 s da soma dos incrementos de um passo. Cada incremento é previsto a partir do estado gravado no passo, com a entrada do passo: é o mesmo modelo, sem realimentar o próprio estado. A regra usa os casos de curva.
- **H6:** o resíduo de um passo é o estado gravado em `k+1` menos a previsão de um passo da M1 v2 a partir do gravado em `k`, em todos os passos das sessões de teste.
  - A autocorrelação de cada grandeza usa os pares de passos (`k`, `k+j`) do mesmo trecho em que os dois passos são de curva. A da reta (os dois passos de reta) é a comparação para o efeito da interpolação.
  - **A correlação parcial** com a taxa do volante é a do resíduo com a média da taxa do volante de 0,1 a 0,3 s antes (passos `k−6` a `k−2`), descontada a parte linear das 6 entradas do Processo Gaussiano no passo `k`.
- **H7:** os modelos são os da rodada sem 21/10 (como na C.4 do pedido 46), nas voltas rotuladas no pedido 44.
  - "Deriva abaixo de 3°" quer dizer os dois eixos abaixo de 3° no início do caso. As duas sessões de 24/10 entram juntas.
  - Se a diferença (24/10 menos 01/11) ficar até 0,10, a H7a é apoiada e a H7b não apoiada. Se passar de 0,20, a H7b é apoiada e a H7a não apoiada. Entre os dois valores, as duas são inconclusivas.
  - Se 01/11 ou 24/10 tiverem menos de 100 casos nessa faixa, as duas são inconclusivas.

**As outras regras da Parte C:**

- **C.1:** o IC 95% do skill do critério 1, por bootstrap agrupado por volta (10.000 reamostragens, semente 48, percentis 2,5 e 97,5): no geral, por sessão e só nas curvas. **Isso não muda o veredito:** o critério é o valor pontual (ADR 0022).
- **C.2, o skill que as curvas precisariam ter,** com o resto igual, para o total chegar a 0,50. Com `Σ` a soma do erro quadrático normalizado:
  - a soma das curvas teria de ser `Σ*_curvas = 0,25·Σ_R0,todos − Σ_M1,resto`;
  - o skill das curvas teria de ser `1 − √(Σ*_curvas / Σ_R0,curvas)`.
- **C.6, a cobertura:** a fração dos passos com deriva acima de 6°, 8° e 10°, em cada eixo, em quatro conjuntos:
  - **treino:** todos os passos das 5 sessões (cada uma é de treino em 4 das 5 rodadas), com a geometria da rodada sem 21/10;
  - **teste:** os inícios dos 39.142 casos, com a geometria de cada rodada;
  - **24/10 e 01/11:** os passos das voltas rotuladas, com a geometria da rodada sem 21/10.
- **C.8, os 7 episódios:**
  - as voltas são achadas pelos tempos do contexto (3, 4, 10 e 11 no `session-index.json`);
  - o pico é a amostra de maior \|`atan2(vy, vx)`\| entre o início da curva e 50 m depois do fim dela;
  - os casos começam 1,0, 0,5 e 0,25 s antes do pico, numa grade de 50 ms que termina no pico;
  - a regra de "acompanha a escapada" é a do pedido, aplicada à M1 v2. A física v2 é relatada ao lado.

**O que se espera, antes de calcular, e o porquê:**

- **H1:** os dados quase não passam de 6° (seção 7.2). Por isso, as faixas acima de 6° devem ter pouco do erro das curvas, mesmo com skill pior nelas. Espera-se **não apoiada ou inconclusiva** pela parte do erro. O pico do pneu explica a falha da identificação (`α_pico` no limite), mas não deve explicar a maior parte do erro das curvas.
- **H2:** um pneu com relaxação atrasa a força lateral por `σ/v`. Com um comprimento de relaxação de algumas dezenas de centímetros, o atraso fica entre 10 e 40 ms abaixo de 100 km/h e é menor em alta. Espera-se um atraso a mais **perto do limite de 10 ms**, apoiado só em baixa velocidade, e por isso **inconclusiva**.
- **H3:** a C10 (volante em 0,87, `vy` exagerada) sugere que a roda vira menos do que `k_δ·steer` com muito volante. Espera-se o ganho caindo com |`steer`|, e **apoiada** se a faixa acima de 0,4 tiver amostras quase estacionárias suficientes.
- **H4:** num carro de fórmula, a carga aerodinâmica depende da altura, e o erro da carga é de 18% a 24%. Espera-se um R² de 10% a 30%, porque a carga gravada oscila com as zebras, que a altura não explica. A expectativa é **inconclusiva**.
- **H5:** a física foi ajustada no erro de um passo, e o erro de 0,5 s é 1,5 vez o de 0,25 s. Espera-se uma razão acima de 1,3 nas curvas: **apoiada**.
- **H6:** a reamostragem a 50 ms e o estado escondido (a carga das molas, a temperatura) criam correlação de um passo para o outro. Espera-se autocorrelação acima de 0,5 nas curvas, mas também alta na reta, o que enfraquece a leitura. A expectativa é **apoiada pela regra**, com essa ressalva.
- **H7:** a sessão de 01/11 tem as saídas de traseira que o Eduardo sentiu. Espera-se que, nos casos de pouca deriva, o skill de 01/11 fique perto do de 24/10: **H7a apoiada**.

#### 7.5.2 Os dados e a reprodução (Parte B)

Comandos: `python -m ml.scripts.m1_diagnostico dados`, `reproduzir` e `analisar`. Tudo o que sai fica em `data/diagnostico_m1/`, fora do git. JSON com todos os números: `docs/handoff/2026-11-09_48_diagnostico-da-m1-v2.json`.

- **Os canais extras** (`rideHeight`, `wheelSlip`, `suspensionTravel`, DRS, combustível, ar e pista) foram lidos das gravações com o mesmo corte de volta e a mesma reamostragem do pedido 46. A grade refeita é igual à do 46 chave a chave e coluna a coluna, nas 5 sessões e nas 3 de depois (24/10 e 01/11). Os canais estão preenchidos em 100% dos passos.
- **Os Processos Gaussianos foram reajustados** pela `fase_teste` do pedido 46, sem mudança. Os 39.142 casos têm o erro quadrático de cada modelo **igual ao do 46, com diferença 0,0**, e os 515 números da seção 7.3 (os critérios, os horizontes e as tabelas por sessão, regime e faixa) se repetem com diferença máxima de 0,0. O critério 1 dá 0,4868, e o 2, 0,2069.

#### 7.5.3 O resultado das análises (Parte C)

**C.1, o acaso perto do limite** (bootstrap por volta, 10.000 reamostragens, semente 48). O veredito não muda: o critério é o valor pontual.

| conjunto | skill | IC 95% | 0,50 dentro? |
|---|---:|---|---|
| todos os casos | 0,487 | 0,447 a 0,523 | sim |
| só as curvas | 0,458 | 0,409 a 0,501 | sim (no limite) |
| `2026-10-15_23-24-50` | 0,496 | 0,446 a 0,542 | sim |
| `2026-10-17_01-02-22` | 0,509 | 0,374 a 0,613 | sim |
| `2026-10-17_16-17-08` | 0,552 | 0,506 a 0,601 | não (acima) |
| `2026-10-18_12-38-44` | 0,453 | 0,404 a 0,505 | sim |
| `2026-10-21_20-30-54` | 0,407 | 0,272 a 0,485 | não (abaixo) |

Com 57 voltas, a diferença entre 0,487 e 0,50 está dentro do que o acaso das voltas produz.

**C.2, onde está o erro das curvas** (25.251 casos, skill 0,458; figura `..._mapa_do_erro.png`):

- **Com o resto igual, as curvas precisariam de 0,475** para o total chegar a 0,50: faltam 0,017.
- **Por grandeza:** a velocidade lateral tem 75,8% do erro das curvas (skill 0,38), a guinada 23,9% (skill 0,58) e a longitudinal 0,3%.
- **Por volante e velocidade:** \|`steer`\| de 0,1 a 0,4 tem 69% do erro. As duas células mais pesadas são \|`steer`\| de 0,2 a 0,4 a 100–160 km/h (21,6% do erro, skill 0,30) e \|`steer`\| de 0,1 a 0,2 a 160–220 km/h (21,7%, skill 0,26). Com \|`steer`\| de 0,4 a 0,6, o skill cai para 0,22 (10,3% do erro).
- **Por \|`a_y`\|:** acima de 2,0 g estão 21% dos casos e 50,5% do erro, com skill de 0,29. De 0,5 a 1,0 g, o skill é 0,61.
- **Por deriva estimada:**

| faixa | dianteira: casos | skill | parte do erro | traseira: casos | skill | parte do erro |
|---|---:|---:|---:|---:|---:|---:|
| abaixo de 3° | 14.511 | 0,67 | 16,7% | 19.034 | 0,58 | 30,2% |
| 3° a 6° | 7.656 | 0,43 | 35,2% | 5.613 | 0,33 | 43,7% |
| 6° a 8° | 2.210 | 0,13 | 23,8% | 311 | 0,38 | 9,7% |
| 8° a 10° | 551 | 0,26 | 10,0% | 90 | 0,36 | 5,0% |
| acima de 10° | 323 | 0,34 | 14,3% | 203 | 0,39 | 11,4% |

- **Por taxa do volante:** o volante parado (tercil de baixo) é o pior, com skill de 0,30, e nele a física v2 sozinha quase não ganha da persistência (0,02). O tercil de cima tem skill de 0,53.
- **Por fase:** na entrada, o skill é 0,35 (44,1% do erro); na saída, 0,43 (35,0%), onde a física sozinha fica em 0,10. Os casos de regime "curva" fora das 14 curvas têm 20,9% do erro, com skill de 0,60.
- **Por curva:** a C06 tem 20,3% do erro (skill 0,34), a C02 10,7% (skill −0,05), a C08 10,0% e a C04 8,8%. A C10 tem 4,6%.
- **Freio e volante juntos** (2.277 casos, skill 0,45): o mesmo retrato, com a velocidade lateral em 79% do erro e o skill caindo com \|`a_y`\| e com a deriva.

**C.3, o atraso do volante para a guinada: sem dados pela regra.**

- Nas amostras cruas, de 16% a 30% dos intervalos passam de 20 ms (a mediana é de 15 a 18 ms, e o percentil 95, de 30 a 33 ms). O trecho mais longo só com intervalos de até 20 ms dura de 0,22 a 0,29 s, conforme a sessão. **Nenhuma entrada de curva cabe na janela de 1,7 s**, então a H2 fica "sem dados".
- **Só para informação, sem decidir:** a mesma conta com os trechos da seção 1.2 (intervalos menores que 50 ms) tem 412 entradas. O resultado vai na figura `..._atraso.png`:

| faixa | entradas | gravado (5 ms) | gravado (grade) | física v2 | M1 v2 | gravado − física v2 (IC 95%) |
|---|---:|---:|---:|---:|---:|---|
| abaixo de 100 km/h | 55 | 35 ms | 48 ms | 59 ms | 49 ms | −11 ms (−144 a +8) |
| 100 a 160 km/h | 276 | 46 ms | 44 ms | 80 ms | 58 ms | −36 ms (−51 a −20) |
| 160 a 220 km/h | 78 | 28 ms | 27 ms | 61 ms | 39 ms | −34 ms (−45 a −27) |
| acima de 220 km/h | 3 | — | — | — | — | poucas entradas |

  O sinal é o contrário do que a relaxação do pneu daria: **o carro do jogo responde ao volante de 30 a 36 ms antes da física v2**, e a M1 v2 fica no meio. A emenda de 09/11 mostra que a grade de 50 ms atrasa a física em alguns milissegundos, mas não em 30 ms com dinâmicas de 50 a 80 ms. Uma explicação possível, não testada aqui, é uma inércia de guinada alta (`k²` de 2,1 a 3,0 m²).

**C.4, a direção com muito volante.** Foram 9.985 amostras quase estacionárias (tercil de baixo da taxa do volante: 0,04 rad/s), com `L` = 2,964 m:

| \|`steer`\| | amostras | `k_ef` | `k_ef`/`k_δ` |
|---|---:|---:|---:|
| 0 a 0,1 | 8.734 | 0,300 | 0,99 |
| 0,1 a 0,2 | 531 | 0,251 | 0,82 |
| 0,2 a 0,4 | 491 | 0,229 | 0,75 |
| 0,4 a 0,6 | 223 | 0,215 | 0,71 |
| acima de 0,6 | 6 | (menos de 200) | — |

- O ganho com \|`steer`\| ≥ 0,4 (0,215) fica **28% abaixo** do ganho com \|`steer`\| < 0,2 (0,297). A regressão tem R² de 0,94, e `K` comum de 0,0003 rad/(m/s²).
- **Nas curvas, o erro de `r` em 0,5 s** tem mediana de 0,082 rad/s com \|`steer`\| ≥ 0,4, contra 0,029 em todas as curvas: 2,8 vezes. Acima de 0,6, a mediana é de 0,17 rad/s, em 73 casos.
- **As regressões por faixa de velocidade não identificam o ganho.** Dentro de uma faixa, `L·r/vx` e `a_y` andam juntos (`a_y ≈ vx·r`), e o `K` troca de lugar com o `k_ef`, que sai entre 0,10 e 0,14. Elas são relatadas no JSON, mas não são lidas.
- **O que a regressão não separa:** a curva do pneu dianteiro saturando também baixa o ganho efetivo, e o termo `K·a_y` é linear. Parte da queda pode ser o pneu, e não a direção (ver 7.5.4).

**C.5, a carga.**

- **O resíduo da carga** (prevista − gravada, por eixo, nos 102.250 passos de teste) tem média de −355 N na frente e −635 N atrás: o modelo prevê carga a menos. A altura e a velocidade explicam **57% (dianteiro) e 61% (traseiro)** da variância dele. Com o `suspensionTravel`, explicam 65% e 72%. Só `vx²` explica 3%.
- **A leitura tem um limite:** a altura do carro também é efeito da carga, porque as molas comprimem com ela. O R² alto mostra que o estado da suspensão explica o resíduo; ele não prova sozinho que a aerodinâmica muda com a altura.
- **O DRS foi gravado,** e ficou desligado em 100% dos passos.
- **A massa pela soma das cargas** com o carro quase parado (`vx` < 15 m/s, \|`a_x`\| e \|`a_y`\| < 0,1 g, em todas as amostras da gravação) fica **entre 735 e 752 kg**, com 8 a 30 L de combustível. Ela cabe na faixa de 700 a 900 kg da seção 1.4. As regressões da v1 deram de 578 a 653 kg, e um F3 real pesa 673 kg com o piloto. **A massa das regressões estava de 13% a 22% abaixo da soma das cargas gravadas.**
- **O skill por quartil do erro de carga no início:** 0,62, 0,58, 0,51 e 0,33, do menor para o maior. Nas curvas: 0,60, 0,57, 0,48 e 0,31. Três casos sem carga gravada (soma zero) ficam fora.

**C.6, a cobertura do pneu.**

| conjunto | dianteira > 6° | > 8° | > 10° | traseira > 6° | > 8° | > 10° |
|---|---:|---:|---:|---:|---:|---:|
| treino (5 sessões) | 8,2% | 2,4% | 0,9% | 1,8% | 0,9% | 0,6% |
| teste (inícios dos casos) | 8,4% | 2,5% | 1,0% | 1,9% | 0,9% | 0,6% |
| 24/10 | 12,7% | 3,2% | 0,6% | 2,0% | 0,6% | 0,4% |
| 01/11 | 5,2% | 0,8% | 0,1% | 0,8% | 0,3% | 0,1% |

- A figura `..._deriva.png` mostra a distribuição, com as marcas de 6° e de 12° (o `α_pico` ajustado). Menos de 1% dos passos passa de 10°.
- **O `wheelSlip`** vai de 0 a 1,35 (percentis 1 e 99, com picos acima de 7). Ele cresce junto com a deriva estimada (Spearman de 0,98 na frente e 0,94 atrás) e com a força lateral por carga (0,96 e 0,92). A força por carga cresce até o último decil do `wheelSlip` (mediana de 1,32 na frente e 1,35 atrás), cada vez mais devagar, e não para de crescer dentro dos dados. O que o `wheelSlip` mede não está documentado; a relação é relatada sem concluir o significado (figura `..._wheelslip.png`).

**C.7, o acúmulo e a memória.**

- **A razão de acúmulo nas curvas é 0,76** (M1 v2) e 0,80 (física v2): o erro em malha aberta é **menor** que o da soma dos incrementos de um passo. No geral, é 0,74; na reta, 0,42. Somar os incrementos a partir do gravado também soma o ruído do gravado em cada passo, e a malha aberta não tem esse ruído.
- **O skill por horizonte nas curvas** (M1 v2): 0,16 em 1 passo, 0,25 em 2, 0,40 em 5, 0,46 em 10 e 0,38 em 20. Ele sobe com o horizonte até 0,5 s, porque a persistência piora mais rápido.
- **A autocorrelação do resíduo de um passo da M1 v2 nas curvas,** no atraso 1: 0,69 em `vx`, 0,51 em `vy` e 0,16 em `r`. No atraso 2, `vy` cai para 0,13, e `r` fica negativa (−0,38). **Na reta é maior:** 0,85 em `vy` e 0,52 em `r`, no atraso 1.
- **A correlação parcial** do resíduo com a taxa do volante de 0,1 a 0,3 s antes fica em 0,01 (`vx`), 0,05 (`vy`) e −0,01 (`r`): o resíduo quase não depende do volante de antes.

**C.8, 01/11 e as saídas de traseira** (modelos da rodada sem 21/10):

| sessão | casos | skill M1 v2 | skill física v2 | não conclusivo | pneus (média) | ar / pista gravados | app |
|---|---:|---:|---:|---:|---:|---|---|
| `2026-10-24_13-26-12` | 1.807 | 0,42 | 0,06 | 0,1% | 86 °C | 24 / 36 °C | 0.4.0-redesenho |
| `2026-10-24_13-43-32` | 3.930 | 0,41 | 0,11 | 1,2% | 89 °C | 25 / 35 °C | 0.4.0-redesenho |
| `2026-11-01_19-47-03` | 4.468 | 0,12 | −0,09 | 0,3% | 58 °C | 0 / 0,9 °C | 0.5.0-radio-e-replay |

- **A versão do CSP não é gravada.** Pela informação do Eduardo, 01/11 é a primeira no 0.3.1; nas outras ela é "não registrada".
- **O ar e a pista em 0 °C** também aparecem nas três sessões da noite do treino (15/10 23:24, 17/10 01:02 e 21/10 20:30), com os pneus entre 60 e 63 °C. Nas do dia, os pneus ficam entre 79 e 89 °C. Não está claro se o 0 °C é a temperatura de verdade ou um campo que o jogo não preenche à noite.
- **Em 01/11 há menos deriva alta que em 24/10,** e não mais: 5,2% dos passos acima de 6° na frente, contra 12,7%.
- **Com os dois eixos abaixo de 3°,** o skill é 0,75 em 24/10 (3.876 casos) e 0,58 em 01/11 (3.169 casos), uma diferença de 0,17. **Com a deriva de 3° a 6°,** 01/11 cai para −0,41 (1.078 casos), e 24/10 fica em 0,41.
- **Os 7 episódios** (figuras `..._episodios.png`, pela regra, e `..._episodios_vx10.png`, só informativa):
  - **pela regra,** o pico de maior \|`atan2(vy, vx)`\| caiu, nos 7, com o carro já girado e parado ou andando de ré (β entre ±156° e ±180°, `vx` de 0 a −55 km/h). Nesses instantes a variação de `vy` é pequena, e a contagem pela regra (a M1 v2 "acompanha" em 4 dos 7; a física v2 em 5) não diz nada sobre a escapada;
  - **só para informação,** com o pico procurado só onde `vx` ≥ 10 m/s, a M1 v2 acompanha em 2 dos 7 e a física v2 em 3. As voltas 3 e 4 passam mais de uma vez pela região da curva (o carro gira e volta), e o pico de "volta 3, C05" caiu numa passagem a 186 km/h com β de −1,9°, que não é a escapada;
  - **o início é "não conclusivo"** em 38 dos 42 casos (7 episódios, 3 inícios e as duas versões), contra o corte de 0,82. Só os 3 inícios da passagem a 186 km/h e um da volta 10 ficam abaixo dele. Os modelos não viram nada parecido no treino.

**C.9, o que o jogo expõe:**

- **A memória compartilhada que o repositório lê** (`SPageFilePhysics` em `backend/core/assetto_adapter.py`, 75 campos até `iDiffOut`; o retrato em `data/debug/ac_shared_memory_full_inventory.json`, de 17/05) tem, por roda:
  - `wheelSlip`, `wheelLoad`, `wheelsPressure`, `wheelAngularSpeed`, `camberRAD` e `suspensionTravel`;
  - `tyreContactPoint`, `tyreContactNormal` e `tyreContactHeading`;
  - mais `rideHeight` (dois valores), `drs` e `cgHeight`.

  **Não tem o ângulo de deriva, a razão de escorregamento nem as forças do pneu.**
- **O gravador grava** `wheelSlip`, `wheelLoad`, `suspensionTravel`, `rideHeight`, `camberRad`, as temperaturas, a pressão, o desgaste, o DRS e o combustível. **Não grava** `wheelAngularSpeed` nem `tyreContactHeading`, que o adaptador lê.
- **A telemetria por UDP do Assetto Corsa** (a estrutura `RTCarInfo`, no "AC Socket Document": https://docs.google.com/document/d/1KfkZiIluXZ6mMhLWfDX1qAGbvhGRC3ZUzjVIt5FQpp4/pub) tem `slipAngle[4]`, `slipAngle_ContactPatch[4]`, `slipRatio[4]`, `tyreSlip[4]`, `load[4]`, `Dy[4]` e `Mz[4]`.
- **No CSP,** o SDK de Lua (https://github.com/ac-custom-shaders-patch/acc-lua-sdk) define o estado do carro por `ac.getCar`. A definição dos campos de cada roda não foi encontrada nos arquivos públicos abertos nesta análise: "não confirmado". O app do jogo do repositório (`tools/csp_app/radio_engenheiro`) lê só a volta e o tempo.
- **O que um pedido futuro teria de mudar para gravar esses canais:**
  - gravar `wheelAngularSpeed` e `tyreContactHeading`, que o adaptador já lê. Com eles e o raio da roda, dá para estimar a razão de escorregamento e o ângulo real de cada roda;
  - ou ler a telemetria por UDP (`RTCarInfo`) ao lado da memória compartilhada, para ter a deriva e o escorregamento do próprio jogo;
  - ou, se o SDK do CSP expuser os campos da roda, gravá-los pelo app do jogo.

  Nenhum desses caminhos foi testado, e o gravador e o app não mudaram.

#### 7.5.4 O quadro das causas e os trabalhos futuros (Parte D)

| | hipótese | o número que decidiu | rótulo | figura |
|---|---|---|---|---|
| H1 | o pico do pneu | dianteira: skill 0,67 abaixo de 3° contra 0,24 acima de 6° (diferença 0,43), e 48,1% do erro das curvas acima de 6°. Traseira: 0,58 contra 0,38, com 26,1% | **apoiada** | `_mapa_do_erro`, `_deriva` |
| H2 | a relaxação do pneu | nenhuma entrada de curva nos trechos de até 20 ms. Só para informação, nos de até 50 ms, o jogo responde de 30 a 36 ms **antes** da física v2 | **sem dados** | `_atraso` |
| H3 | a direção com muito volante | ganho 28% menor com \|`steer`\| ≥ 0,4; erro de `r` 2,8 vezes a mediana das curvas | **apoiada** | — |
| H4 | a carga com a altura e o DRS | R² de 0,57 e 0,61; skill do quartil de menor erro de carga 0,29 acima do de maior | **apoiada** (com o limite da C.5) | — |
| H5 | o acúmulo no horizonte | razão de acúmulo de 0,76 nas curvas | **não apoiada** | — |
| H6 | a correção sem memória | autocorrelação de 0,51 em `vy` no atraso 1 (pela regra); na reta, 0,85 | **apoiada pela regra**, mas a leitura é fraca: a reta tem mais, e o volante de antes não explica o resíduo (parcial de 0,05) | — |
| H7a | 01/11, a pilotagem | diferença de 0,17 com deriva abaixo de 3° | **inconclusiva** | `_episodios` |
| H7b | 01/11, o carro ou o jogo | a mesma diferença, abaixo de 0,20 | **inconclusiva** | `_episodios` |

**A ordem, pela parte do erro das curvas que cada causa apoiada explica** (as partes se sobrepõem e não são somadas):

1. **O pico do pneu (H1):** os casos com a deriva dianteira acima de 6° têm 12% dos casos de curva e 48,1% do erro.
2. **A carga (H4):** o quartil de maior erro de carga no início tem 50,0% do erro das curvas.
3. **A direção (H3):** os casos com \|`steer`\| ≥ 0,4 têm 13,5% do erro.
4. **A memória (H6)** não tem parte mensurável; a regra a apoia, mas a evidência é fraca.

**Onde elas se misturam:**
- 63% dos casos com \|`steer`\| ≥ 0,4 têm a deriva dianteira acima de 6°, e a interseção tem 11,2% do erro.
- Deriva alta e erro de carga alto juntos têm 21,6% do erro.
- As três juntas têm 6,1%, e a união delas, 77,6%.
- A deriva dianteira alta acontece a 124 km/h em média, contra 157 km/h no resto das curvas, e 61% desses casos estão acima de 2 g.
- **A deriva dianteira estimada usa `k_δ` linear.** Se a roda vira menos com muito volante (H3), a deriva estimada nesses casos fica alta demais. Parte do que a H1 mostra pode ser a direção, e parte do que a H3 mostra pode ser o pneu saturando. Os dados de rua não separam as duas: isso pede a manobra da rampa de volante (abaixo).

**Os trabalhos futuros:**

- **Dados de manobra, numa sessão própria** (cerca de 15 a 20 voltas ou trechos, numa pista de teste ou numa reta larga):
  - **um círculo de raio constante com a velocidade subindo devagar,** nos dois sentidos, 3 a 4 vezes cada. Ele identifica a curva do pneu até o pico, o subesterço e o `K`. Responde à H1 e à falta de dados acima de 6°, que é a mesma limitação descrita por "Learning-Based On-Track System Identification for Scaled Autonomous Racing in Under a Minute" (2024, https://arxiv.org/abs/2411.17508) e por "Bayesian Optimization-based Tire Parameter and Uncertainty Estimation for Real-World Data" (2025, https://arxiv.org/abs/2504.20863);
  - **uma rampa de volante a velocidade constante,** em 3 velocidades, 2 vezes cada. Ela identifica o ganho da direção e separa a H3 da H1. "Short-Horizon Position Accuracy of Single-Track Models" (2026, https://arxiv.org/abs/2606.14216) aponta a complacência da direção como fonte de erro;
  - **um seno de volante em 3 ou 4 velocidades,** 2 vezes cada, **com o gravador sem cair para 20 Hz.** Ele identifica o atraso e a relaxação (Pacejka, "Tire and Vehicle Dynamics"; Clemson, grupo de B. Ayalew, "On the Frequency Domain Analysis of Tire Relaxation Effects on Transient On-Center Vehicle Handling Performance"). A H2 ficou sem dados por causa dos intervalos das amostras, e o informativo sugere que o problema é a física lenta, e não o jogo atrasado.
- **Um modelo novo,** só se sobrar tempo depois do pedido 42, testado em sessões novas que ele não tenha visto (ADR 0028, item 1):
  - **prioridade, com hipótese apoiada:**
    - a curva do pneu identificada com dados que cheguem ao pico (H1);
    - a direção não linear (H3);
    - a carga com a altura e a massa medida pela soma das cargas, em vez da regressão (H4);
  - **a testar:**
    - a correção com o histórico de estados e entradas e a guarda física (H6, fraca), como em Spielberg et al. (2019, https://doi.org/10.1126/scirobotics.aaw1975) e Chrosniak et al. (2024, https://arxiv.org/abs/2312.04374), ou o Processo Gaussiano no resíduo como em Kabzan et al. (2019, https://doi.org/10.1109/LRA.2019.2926677) e Jain et al. (2020, https://arxiv.org/abs/2005.04755);
    - a relaxação do pneu e a inércia de guinada (H2, sem dados);
    - o ajuste em vários passos (H5 não apoiada: a razão de acúmulo ficou abaixo de 1). A literatura diz que ele ajuda quando o modelo é mal especificado: Lambert, Pister e Calandra (2022, https://arxiv.org/abs/2203.09637) e "Learning with Imperfect Models: When Multi-step Prediction Mitigates Compounding Error" (2025, https://arxiv.org/abs/2504.01766). O ajuste fino de uma rede física híbrida ("Fine-Tuning Hybrid Physics-Informed Neural Networks for Vehicle Dynamics Model Estimation", 2024, https://arxiv.org/abs/2409.19647) é outra forma de testar isso.

#### 7.5.5 Para quem não é da área

A segunda versão do modelo do carro errou quase só nas curvas, e quase só no quanto o carro escorrega de lado. O erro se concentra nos momentos em que os pneus da frente trabalham muito torcidos e o carro faz muita força lateral, acima de 2 g. Nesses momentos, o modelo de pneu foi ajustado sem dados suficientes: o jogo raramente leva o carro até ali nas voltas normais. O volante também parece virar a roda menos do que o modelo supõe quando é muito girado. E o modelo calculava as cargas nas rodas com um carro de 100 a 170 kg mais leve do que o jogo mostra. A diferença para a meta (0,487 contra 0,50) está dentro do que o acaso das voltas produziria, mas a regra combinada antes vale como está, e o veredito não muda. Para um modelo novo, o que mais falta são dados de manobras feitas de propósito, que levem o carro ao limite de forma controlada.
