# 0024 — M1: a geometria do carro medida pela telemetria do jogo

- **Status:** aceita
- **Data:** 2026-10-25
- **Decisor:** Eduardo
- **Refina:** 0022 e a seção 1.4 de `docs/modelo_fisico_m1.md` (como medir `b`, `L` e `k_δ`). **Mantém:** 0017 (os parâmetros saem da telemetria; nenhum arquivo criptografado é aberto) e todos os critérios do 0022

## Contexto

1. **O pedido 37 parou na Parte C.** A regra registrada mede `b` (do centro de massa ao eixo traseiro), `L` (entre-eixos) e `k_δ` (ângulo da roda por unidade de volante) por regressões cinemáticas com |a_y| ≤ 0,5 g. Ela deu `L` negativo ou menor que 1,1 m nas 5 rodadas, com o intervalo de confiança passando por zero. Nenhum número de teste foi calculado.
2. **As causas,** pelo diagnóstico do relatório do pedido 37:
   - com |a_y| ≤ 0,5 g, quase todos os dados são de reta em alta velocidade, onde a guinada mal varia. O termo geométrico (`b·r`) fica pequeno e se confunde com a deriva do pneu;
   - com a carga aerodinâmica, a deriva por g não é constante com a velocidade;
   - **o ângulo de deriva medido** (`vy/vx`) é proporcional à aceleração lateral, sem a parte geométrica que um `b` de 1,3 m daria em baixa velocidade. A velocidade lateral gravada pode não ser a do centro de massa.
3. **Por que isso pesa no resultado:** a métrica do ADR 0022 divide cada grandeza pelo seu desvio-padrão. A velocidade lateral tem o menor desvio (1,25 m/s), então domina o erro combinado, e é justamente nela que a física perdeu para a persistência.
4. **O jogo já entrega a geometria, sem abrir arquivo nenhum.** A página de física da memória compartilhada tem, para cada pneu:
   - `tyreContactPoint`: o ponto de contato com o chão, em coordenadas do mundo;
   - `tyreContactHeading`: a direção para onde o pneu aponta;
   - e, para o carro, `cgHeight`: a altura do centro de massa.

   O adaptador do backend já lê esses campos na estrutura, mas o gravador não os grava.
5. **Um retrato da memória** (`data/debug/ac_shared_memory_full_inventory.csv`, de maio de 2026, com o carro não confirmado) dá, pelas contas do Claude (Cowork):
   - **entre-eixos** de cerca de 2,96 m;
   - **bitolas** de 1,58 m na frente e 1,52 m atrás;
   - **altura do centro de massa** de 0,263 m;
   - **ângulo das rodas da frente contra as de trás** de 0,57° com o volante em −0,0375, isto é, cerca de 15° (0,27 rad) por unidade de volante.

   Uma reportagem cita, para este carro, 2,943 m de entre-eixos e bitolas de 1,552 m e 1,502 m, sem confirmação do fabricante.

## Decisão

### 1. Medir, e não ajustar

Numa sessão curta, gravada por uma ferramenta que só lê a memória compartilhada, e que **não é uma das 5 sessões da M1**:

| parâmetro | como é medido |
|---|---|
| **`L`** | a distância, ao longo do eixo do carro, entre o ponto médio dos contatos dianteiros e o ponto médio dos traseiros; a mediana nas amostras em reta, com |a_y| < 0,2 g |
| **`b`** | `b = w_f · L`, com `w_f` medido nas cargas das rodas, como já registrado |
| **`h`** | a mediana de `cgHeight`. A razão `h/L` passa a ser `cgHeight / L`; a estimativa pelas cargas fica como conferência |
| **`k_δ`** | o ângulo entre a direção média dos pneus dianteiros e a direção média dos traseiros, no plano do carro, contra o `steerAngle`, por regressão linear em toda a sessão. A inclinação é `k_δ`; o intercepto é a convergência estática. Os lados esquerdo e direito são relatados à parte, e o modelo usa a média |
| **`x_v`, o ponto da velocidade gravada** | a velocidade lateral dos pontos médios dos eixos, pela derivada dos pontos de contato no tempo, comparada com a `localVelocity` e com a guinada. Isso localiza, ao longo do carro, o ponto em que a velocidade é medida. No modelo, a velocidade lateral é levada ao centro de massa: `vy_cm = vy_gravada + (b − x_v)·r`, com `x_v` e `b` medidos a partir do eixo traseiro |

### 2. Portões, fixados antes de medir

| parâmetro | passa quando | se não passar |
|---|---|---|
| `L` | fica entre 2,8 e 3,8 m, com a faixa entre os percentis 5 e 95 menor que 3% do valor | usa o valor publicado (2,943 m), declarado como fonte externa e exceção ao ADR 0017 |
| `k_δ` | fica entre 0,05 e 1,5 rad, com R² ≥ 0,95 | sai da regressão em regime permanente `steer = (L/k_δ)·κ + K·a_y`, com o `L` medido |
| `x_v` | o intervalo de 95% tem meia-largura menor que 0,2 m | supõe-se que a velocidade é a do centro de massa, e isso é relatado |

### 3. Constantes do carro

- **A geometria é do carro, não do piloto.** Ela é medida uma vez e usada nas 5 rodadas.
- **Ela não vem de nenhuma das 5 sessões da M1,** então não há vazamento da sessão de teste.

### 4. O resto do ADR 0022 não muda

Os dados das 5 sessões, o relógio, o passo de 50 ms, as referências R0 e R1, a métrica e os 7 critérios ficam como estão. Os parâmetros que continuam ajustados (`Cα`, `μ`, `k²`, `κ_D`, `c0`, `s_T` e `β_B`) seguem a regra registrada, agora com a geometria medida.

## Consequências

- **É preciso uma sessão curta do Eduardo** com a ferramenta de medição. O app e o gravador não mudam.
- **A mesma geometria serve ao Modelo 2:** o ângulo de subesterço do pedido 38 precisa de `L` e de `k_δ`.
- **Se, com a geometria medida, a física ainda não passar no critério 1 do ADR 0022,** o resultado negativo é documentado, como o ADR 0022 manda. Nenhum critério muda depois de ver os números.
- **A seção 1.4 original fica registrada,** com a nota de que a regra das regressões cinemáticas não identificou os parâmetros, e por quê.
