# Relatório do pedido 39 — M1: a geometria do carro medida pela telemetria do jogo

- **Pedido:** `docs/prompts/2026-10-25_39_m1-geometria-medida.md`
- **Situação:** **parado na Parte C, como o pedido manda,** esperando a sessão de medição do Eduardo. As Partes A, B e C estão feitas. As Partes D (a geometria medida) e E (a retomada do pedido 37) vêm depois do aviso "medi a geometria".
- **Branch:** `etapa/m1-modelo-do-carro` (a mesma do pedido 37), sem merge em `develop` e sem push.
- **Commits deste pedido:**
  - `23b2ea49` docs: pedido 39 (M1: a geometria do carro medida pela telemetria do jogo, e a retomada do pedido 37)
  - `946edea3` Pedido 39, Parte A: o ADR 0024 e a emenda 1.9 da M1, registrados antes de medir
  - `3b0f1535` Pedido 39, Parte A (continuacao): a emenda 1.9 da M1, registrada antes de medir
  - `b2f5abea` Pedido 39, Parte B: a primeira olhada na geometria do retrato da memoria
  - `28de6176` Pedido 39, Parte C: a ferramenta que mede a geometria pela memoria do jogo, parada para a sessao do Eduardo
  - e o commit deste aviso sobre a sessão do pedido 38 (ver "Coisas que não batiam com o contexto")
  - **também na branch, sem ser deste pedido:** `f38f89a5` docs: pedido 38, commitado pela sessão do pedido 38 depois que eu troquei a branch da pasta (abaixo)
- **Arquivos de handoff** (`docs/handoff/`):
  - `2026-10-25_39_m1-geometria-medida_relatorio.md` (este)
  - `2026-10-25_39_m1-geometria-medida_retrato.json` (Parte B)
  - `2026-10-25_39_m1-geometria-medida_pytest_parte_c.txt` (a suíte do backend)

## Parte A — registrado antes de medir

- **O ADR 0024** está em `docs/decisoes/`, com a linha no índice, e `docs/prompts/anexos-39/` foi apagado.
  - O índice pula do 0022 para o 0024: o 0023 é do pedido 38 (`docs/prompts/anexos-38/`), que ainda não rodou.
- **A seção 1.9 de `docs/modelo_fisico_m1.md`** registra a sessão de medição, como cada parâmetro é medido, os portões e o caminho de cada falha.
  - **A seção 1.4 não foi apagada nem reescrita:** ganhou só uma linha no começo, apontando para a 1.9.
  - **A conferência da guinada** está registrada na seção 3 pela leitura do texto registrado, por decisão do Eduardo de 25/10.
- **Dois commits na Parte A.** O primeiro (`946edea3`) saiu só com o ADR e o índice: o `python` do Windows não achou o arquivo temporário que o bash tinha escrito em `/tmp`, e a seção 1.9 não entrou. O segundo (`3b0f1535`) traz a seção 1.9, a linha na 1.4 e a decisão da guinada. **Nada foi medido antes do segundo commit.**
- **Os pontos que a 1.9 fixa além do ADR:**
  - **duas partes da sessão:** `k_δ` usa todas as amostras com um `packetId` novo, inclusive paradas no box, onde o cronômetro da volta pode não andar; `L`, `h` e `x_v` usam o preparo da Parte B do pedido 37 (cronômetro do jogo, sem repetidas, trechos em buracos de 50 ms, grade de 50 ms);
  - **"em reta"** é `vx` ≥ 10 m/s com |a_y| < 0,2 g; `cgHeight` é a mediana com `vx` ≥ 10 m/s;
  - **o ângulo das rodas** é o da direção média dos dianteiros menos o da média dos traseiros, nos eixos do carro, positivo para a esquerda; `k_δ = −inclinação` contra o `steerAngle`, porque o volante é positivo à direita;
  - **`x_v`** é a inclinação de `vy_gravada − v_lat,traseiro` contra `r`, pela origem, com |r| ≥ 0,05 rad/s. O intervalo de 95% sai de um bootstrap por trecho (200 reamostragens, semente 39). A conta pelo eixo dianteiro é conferência;
  - **`b` continua por rodada:** `b = w_f · L`, com o `w_f` das cargas das 4 sessões de treino, como na 1.4;
  - **`vy_cm = vy_gravada + (b − x_v) · r`** em todas as amostras das 5 sessões, antes do desvio-padrão de normalização, dos passos, dos casos e da correção;
  - **a sessão só vale** com `carModel = rss_formula_rss_3_v6_2026` e `track = vhe_interlagos` na página estática.

## Parte B — a primeira olhada no retrato

Comando: `python -m ml.scripts.m1_modelo_carro retrato`. **É só uma olhada: nenhum destes números entra na M1.**

**O retrato é deste carro.** O contexto do pedido diz que não se sabe com que carro ele foi tirado. Mas a página estática do próprio retrato (17/05/2026, 22:48 UTC, AC 1.16.4) traz `carModel = rss_formula_rss_3_v6_2026` e `track = vhe_interlagos`. Lido junto com a página de física, ele é deste carro nesta pista.

**A ordem 4 × 3 confere:** lidos achatados (roda `w`, coordenada `c` no índice `3·w + c`), os 4 contatos ficam nos cantos de um retângulo de 2,95 × 1,55 m em volta do `carCoordinates`. Lidos como 3 × 4, não formam carro nenhum.

| medida | retrato | reportagem | diferença |
|---|---:|---:|---:|
| entre-eixos | **2,955 m** | 2,943 m | +0,4% |
| bitola dianteira | **1,578 m** | 1,552 m | +1,7% |
| bitola traseira | **1,517 m** | 1,502 m | +1,0% |

- **As bitolas** medidas aqui são entre os pontos de contato, que se movem com o câmber e a deformação do pneu (o carro estava a 193 km/h, numa curva leve à esquerda). A reportagem deve ser entre os centros das rodas.
- **`carCoordinates`** fica **1,056 m à frente do eixo traseiro** (36% do entre-eixos), 0,008 m para o lado e 0,227 m acima dos contatos. O `cgHeight` no mesmo instante é 0,263 m.
  - Com o `w_f` das cargas (0,42 a 0,45 no pedido 37), o centro de massa ficaria de 1,24 a 1,33 m à frente do eixo traseiro. O `carCoordinates` fica uns 0,2 m atrás disso: não parece ser o centro de massa.
- **As direções dos pneus apontam para trás,** como o pedido avisou: o produto escalar com o vetor do eixo traseiro para o dianteiro é negativo. Elas são invertidas antes de medir o ângulo.
- **O ângulo das rodas:** 0,0100 rad (0,57°) para a esquerda, com o volante em −0,0375 (à esquerda).
  - **Por unidade de volante: 0,267 rad (15,3°),** a mesma conta do Cowork e perto dos 15° que a M0 sugeriu;
  - **por lado:** 0,336 (esquerdo) e 0,199 (direito). Com um instante só, não dá para separar a convergência estática da inclinação: com o volante quase no centro, a diferença entre os lados é a convergência. A sessão de medição separa as duas pela regressão.
- **`L/k_δ` = 2,955 / 0,267 = 11,06,** contra a razão volante ÷ curvatura da M0, de 10,1 a 10,6 em baixa velocidade (nas voltas do Eduardo). A diferença de 4% a 9% cabe numa deriva dianteira maior que a traseira, ou na leitura de um instante só.
- **A velocidade no referencial do carro** no mesmo instante (lida no antigo `brakeTemp`, como o pedido 18 achou): `vy` = −0,69 m/s, com a guinada em 0,146 rad/s e `vx` = 53,5 m/s.

## Parte C — a ferramenta de medição

**`backend/ml/scripts/medir_geometria.py`:**

- **Usa o adaptador do backend** (`core.assetto_adapter`): as páginas são abertas só para leitura (`ACCESS_READ`), e a trava que espera o Assetto Corsa estar aberto é respeitada.
  - Conferido agora, sem o jogo: a trava responde `allowed: False` (`stale_assetto_corsa_shared_memory_without_process`), e a ferramenta fica esperando.
- **Lê a cerca de 60 Hz** e grava, sem descartar nada:
  - o cronômetro do jogo (`iCurrentTime`), o `packetId` da física e o da página gráfica, e o horário da ferramenta;
  - o `steerAngle`, o acelerador e o freio;
  - o `heading`, a arfagem e a rolagem;
  - a `velocity`, a `localVelocity`, a `localAngularVelocity` e a `accG`;
  - as 4 cargas das rodas, a velocidade e o `cgHeight`;
  - os 4 pontos de contato e as 4 direções dos pneus, achatados na ordem da memoria (`cp_0` a `cp_11`, `ch_0` a `ch_11`);
  - o `carCoordinates`, o box (`isInPit`, `isInPitLane`), as voltas completas e o estado do jogo.
- **Salva em `data/ml/modelo_carro/geometria_<data>_<hora>.parquet`,** fora do git, com um `.json` ao lado (carro, pista, versão do jogo, amostras, taxa média).
  - O arquivo é regravado a cada minuto, para nada se perder se o jogo fechar antes.
  - O carro e a pista são fixados quando a página estática os traz; se não forem o `rss_formula_rss_3_v6_2026` em `vhe_interlagos`, a ferramenta avisa na tela.
- **Não escreve na memória do jogo, não muda o app nem o gravador, e não lê nenhum arquivo do carro.**
- **As contas da Parte D já estão escritas** (`backend/ml/modelo_carro/geometria_medida.py`), pela seção 1.9, e testadas num carro sintético. **Não rodaram em nenhuma sessão de medição,** porque ela ainda não existe.

### Testes

- **`tests/test_m1_geometria_medida.py`: 6 passaram:**
  - **a ordem 4 × 3:** 12 números escritos na memória simulada voltam na coluna `3·w + c`, e o vetor aninhado do ctypes (3 linhas de 4) é lido na mesma ordem;
  - **o cronômetro e o arquivo:** com uma memória simulada e um relógio falso, o laço grava o cronômetro de cada leitura, guarda os `packetId` repetidos (nada é descartado), anda em 1/60 s e salva o parquet e o `.json` com o carro e a pista;
  - **as contas, num carro sintético com geometria conhecida:** o entre-eixos, as bitolas e as direções invertidas; `k_δ` e a convergência de cada lado; `L`, `cgHeight` e `x_v` na parte com relógio, com os 3 portões passando;
  - **o portão que falha usa o caminho registrado:** o `L` publicado, a regressão de reserva de `k_δ` e a velocidade suposta no centro de massa.
- **`tests/test_m1_modelo_carro.py`:** os 14 do pedido 37 continuam passando.
- **A suíte do backend:** ver abaixo.

**Suíte do backend: 814 passaram em 10 min 56 s** (`python -m pytest tests -q`), com os 20 da M1 (14 do pedido 37 e 6 deste).

## Os passos para você: a sessão de medição

1. **Abra o Assetto Corsa** com o `rss_formula_rss_3_v6_2026` em Interlagos (`vhe_interlagos`, traçado `gp`), numa sessão de treino sozinho. O app de telemetria pode ficar aberto ou fechado; a ferramenta não depende dele.
2. **Rode a ferramenta** num terminal (PowerShell), antes ou depois de abrir o jogo:

   ```
   cd C:\Users\Dokas\Desktop\f1-telemetry-analyzer\backend
   ..\.venv\Scripts\python -m ml.scripts.medir_geometria
   ```

   Espere as linhas `conectado; gravando em ...` e `carro rss_formula_rss_3_v6_2026, pista vhe_interlagos`, **sem** a palavra "ATENCAO".
3. **Parado no box:** com o carro parado e sem acelerar, gire o volante **devagar** de um batente ao outro e volte, **duas vezes** (uns 10 segundos para cada lado).
4. **Saia do box e ande 3 voltas normais.**
5. **Encerre a ferramenta com Ctrl+C** na janela dela e espere a linha `salvo: ... (N amostras, ... Hz)`. A taxa deve ficar perto de 60 Hz.
6. **Me avise:** "medi a geometria".

Se o jogo fechar antes do Ctrl+C, o arquivo do último minuto já está salvo.

## O que vem depois do aviso

- **Parte D:** medir `L`, `b`, `h`, `k_δ` (esquerdo, direito e médio) e `x_v`, aplicar os portões e relatar `h/L` contra o das cargas, `L/k_δ` contra a M0 e a linearidade do volante.
- **Parte E:** retomar as Partes C a F do pedido 37 com a geometria medida:
  - a física nas sessões de treino, antes e depois da geometria medida;
  - a M1, as 5 rodadas e a tabela do veredito;
  - as tabelas, as figuras e a temperatura dos pneus;
  - a documentação e o merge em `develop`.

## Coisas que não batiam com o contexto

- **O carro do retrato é conhecido:** a página estática dele diz `rss_formula_rss_3_v6_2026` em `vhe_interlagos` (acima).
- **Duas sessões de implementação na mesma pasta (ADR 0008).** Quando comecei, a pasta estava em `etapa/modelo2-erro-tecnica-e-estilo`, do pedido 38, sem nenhum commit além de `develop`. Conferi só isso, e não se havia outra sessão ativa nela. Havia: a sessão do pedido 38 estava trabalhando ali.
  - **00:40:09:** troquei para `etapa/m1-modelo-do-carro` (`git switch`);
  - **00:41:02:** a sessão do 38 commitou o texto do pedido 38 e as três pesquisas (`docs/tecnica_de_pilotagem_*.md`). O commit (`f38f89a5`) caiu na branch do 37, por causa da minha troca;
  - **00:41:17:** o meu commit do pedido 39 (`23b2ea49`) ficou por cima dele.
  - **A sessão do 38 parou** e deixou o relatório dela sem commit (`docs/handoff/2026-10-24_38_modelo2-erro-tecnica-e-estilo_relatorio.md`), com as opções. Ela também tirou a cópia não commitada do ADR 0023 de `docs/decisoes/`. Eu não mexi no relatório dela, no anexo dela, nem no `f38f89a5`.
  - **O que isso muda aqui:** a branch do 37 e do 39 tem, entre o `5c8ed449` e o `23b2ea49`, o commit `f38f89a5` (só documentos do 38, 4 arquivos, nenhum código). Se nada for feito, ele vai para `develop` com o merge do fim deste pedido.
  - **A decisão é sua,** e é a mesma que o relatório do 38 pede: (a) deixar como está (a recomendação dele, e a minha), ou (b) tirar o `f38f89a5` da branch depois do 39, reescrevendo o histórico, só com o seu ok. Daqui para frente, antes de trocar de branch, confiro se outra sessão está ativa na pasta.
- **`recordings/` na raiz** continua fora do git; não mexi.

Arquivo: `docs/handoff/2026-10-25_39_m1-geometria-medida_relatorio.md`
