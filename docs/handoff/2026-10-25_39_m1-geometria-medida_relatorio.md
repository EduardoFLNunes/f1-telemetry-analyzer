# Relatório do pedido 39 — M1: a geometria do carro medida pela telemetria do jogo

- **Pedido:** `docs/prompts/2026-10-25_39_m1-geometria-medida.md`
- **Situação (29/10):** **a M1 não foi aprovada, e o trabalho parou, como o pedido manda** ("se um critério não passar, relate e pare"). Em 0,5 s, a M1 tem skill de **0,202** contra a persistência (o critério 1 pede 0,50) e de **0,174** contra a física sozinha (o critério 2 pede 0,20). Os outros 5 critérios passam. A geometria medida passou nos portões de `L` e de `x_v`; `k_δ` seguiu o caminho do ADR 0024 por uma batida no fim da sessão de medição. Falta a sua decisão sobre o resto da Parte F e o merge (seção "O que precisa da sua decisão", no fim). O teste do rádio com o app 0.5.0 não foi feito e fica para depois, como você pediu.
- **Branch:** `etapa/m1-modelo-do-carro` (a mesma do pedido 37), sem merge em `develop`. Eu não enviei nada ao remoto. Pelo relatório do pedido 41, a branch já estava no GitHub desde 28/10, igual à local de então; os commits de 29/10 estão só aqui.
- **Commits deste pedido:**
  - `23b2ea49` docs: pedido 39 (M1: a geometria do carro medida pela telemetria do jogo, e a retomada do pedido 37)
  - `946edea3` Pedido 39, Parte A: o ADR 0024 e a emenda 1.9 da M1, registrados antes de medir
  - `3b0f1535` Pedido 39, Parte A (continuacao): a emenda 1.9 da M1, registrada antes de medir
  - `b2f5abea` Pedido 39, Parte B: a primeira olhada na geometria do retrato da memoria
  - `28de6176` Pedido 39, Parte C: a ferramenta que mede a geometria pela memoria do jogo, parada para a sessao do Eduardo
  - `6171e279` Relatorio do pedido 39: o commit do pedido 38 que caiu nesta branch
  - `85123d10` Relatorio do pedido 39: o f38f89a5 fica nesta branch, o instalador 0.5.0 ja gerado e uma ida so ao jogo
  - `ac8fdaa9` Relatorio do pedido 39: o aviso da medicao chegou sem o arquivo nem o app 0.5.0 instalado
  - `c3d48d3b` Relatorio do pedido 39: o app 0.5.0 instalado, e o app do jogo 0.4.1 que nao esta em develop
  - `121a83c7` Pedido 39, Parte D: a geometria medida pela telemetria do jogo e os portoes
  - `00fff510` Pedido 39, Parte E (treino): a fisica com a geometria medida, antes de qualquer sessao de teste
  - o commit da Parte E (teste) com o veredito e este relatório: ver `git log` da branch (a mensagem começa com "Pedido 39, Parte E (teste)")
  - **também na branch, sem ser deste pedido:**
    - `f38f89a5` docs: pedido 38, commitado pela sessão do pedido 38 depois que eu troquei a branch da pasta (abaixo);
    - `a85d16ad` chore: ignora gravacoes da raiz e `73565e79` docs: atualiza backlog do pedido 40, de 28/10, feitos por outra sessão
- **Merges:** nenhum.
- **Arquivos de handoff** (`docs/handoff/`, prefixo `2026-10-25_39_m1-geometria-medida_`):
  - `relatorio.md` (este)
  - `retrato.json` (Parte B)
  - `pytest_parte_c.txt` (a suíte do backend na Parte C)
  - `geometria.json` (Parte D: a geometria medida e os portões)
  - `fisica_treino.json` (Parte E: a física nas sessões de treino, por rodada)
  - `validacao.json` (Parte E: o veredito, os horizontes, as tabelas, a correção por rodada, as figuras e a temperatura dos pneus)
  - `figura_c01.png` e `figura_c10.png` (Parte E)
  - `resultados.json` (ADR 0007: os commits, o `geometry_id`, os comandos e os hashes dos arquivos lidos)
  - `pytest.txt` (a suíte do backend no fim)

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

## Mensagem de 25/10, às 11:57: o commit do 38 nesta branch, o instalador 0.5.0 e uma ida só ao jogo

**Antes de tudo:** as duas outras sessões da pasta ("Modelo2 erro técnica e estilo" e "Redesenho base") estavam paradas, e não havia trava do git. A pasta estava em `etapa/modelo2-erro-tecnica-e-estilo`, limpa (só a `recordings/` da raiz, de sempre). Voltei para `etapa/m1-modelo-do-carro`.

### O `f38f89a5` fica nesta branch (decisão do Eduardo)

- **Decidido em 25/10:** o `f38f89a5` (o texto do pedido 38 e as três pesquisas) fica na branch do 37/39 e vai para `develop` com o merge.
- **No merge em `develop`:** se `docs/tecnica_de_pilotagem_lista.md` der conflito, fica a versão de `develop`.
- **Uma coisa que não bate com a mensagem:** hoje `develop` **ainda não tem** o `fcc94f86`. Ele está só na branch do 38 (`etapa/modelo2-erro-tecnica-e-estilo`), que não teve merge; `develop` continua em `4782aefb`. Então:
  - **se o 38 for para `develop` antes do 39,** os arquivos do `f38f89a5` já estarão lá pelo `fcc94f86`, e a regra acima resolve a lista;
  - **se o 39 for antes,** o `f38f89a5` leva os arquivos para `develop`. O conflito, se houver, aparece depois, no merge do 38, e a mesma regra vale.

### O instalador 0.5.0: já gerado, não refiz

- **A sessão do pedido 38 já gerou o instalador** na branch dela, com tudo o que a mensagem pede (está no relatório do 38, seção "Mudança de prioridade em 25/10, às 11:36"):
  - o `git diff --stat develop...HEAD` só com `backend/ml`, os testes do Modelo 2 e `docs`;
  - os testes: `vitest run` com 189 passando, `tsc --noEmit` sem erro, `npm test` do `desktop` com 4 passando e o `conferir_lua.py` sem erro;
  - a versão `0.5.0-radio-e-replay` num commit próprio (`825ef60d`, as 3 linhas de versão de sempre);
  - o `npm run dist:win` pelo `publish-version.js`, sem baixar pacote: o Electron 42.3.3 veio do cache local;
  - o `versoes\LEIA-ME.md` commitado em `d4cff2c3`.
- **O que conferi aqui:**
  - **o instalador:** `versoes\0.5.0-radio-e-replay\Automobilista-Telemetria-Setup-0.5.0-radio-e-replay.exe`, 229.288.854 bytes, sha256 `4db96566280e…`. O `build-info.json` dá o commit `825ef60` e a branch do 38, e marca a árvore suja só pela `recordings/` da raiz;
  - **o app nele é o de `develop`:** fora de `backend/ml`, dos testes e de `docs`, a branch do 38 só muda as 3 linhas de versão. **A branch do 37/39 tem o mesmo app:** o `git diff --stat develop...etapa/m1-modelo-do-carro` não mostra nada fora de `backend/ml`, dos testes da M1 e de `docs`.
- **Por que não refiz:** um build daqui daria o mesmo app, mas sobrescreveria o `.exe` da mesma versão com outro sha256 e criaria um segundo commit da versão 0.5.0 em paralelo, que brigaria com o `825ef60d` no merge. **Não rodei o instalador e não mexi no app instalado nem na pasta do jogo.**

### Onde o app instalado grava, e se o Modelo 2 lê

- **O app instalado grava em** `%APPDATA%\Automobilista Telemetria\data\recordings\`, uma pasta por sessão, com o nome `<data>_<hora>_vhe_interlagos`.
- **O `ml.scripts.modelo2` lê essa pasta:** ele acha as gravações por `list_all_sessions`, que lê as duas pastas (a do repositório e a do app instalado), como o resto do `ml` desde o ADR 0014. A M1 também.
- **Não copie as sessões novas para `data\recordings`.** O relatório do 38 sugere uma cópia com `robocopy`, mas `list_all_sessions` **para com erro** quando o mesmo nome de sessão existe nas duas pastas ("compare as duas antes de seguir"). Com uma cópia, o Modelo 2, a M1 e o `atualizar_coach` param. Hoje não há nenhum nome repetido. Deixe as sessões onde o app grava.
- **A ferramenta de medição** grava no repositório, em `data\ml\modelo_carro\geometria_<data>_<hora>.parquet`.

## Os passos para você: uma ida ao jogo (instalação, medição e rádio)

Uma sessão do jogo só, sem a IA. A ferramenta de medição grava a sessão inteira: o giro do volante no box e todas as voltas. As voltas do teste do rádio valem como as "3 voltas normais" da medição.

**1. Instalar (com o jogo e o app fechados, inclusive na bandeja do Windows)**

- O app 0.5.0: rode o instalador, escolha **todos os usuários** e mantenha a pasta `C:\Users\Dokas\AppData\Local\Programs\Automobilista Telemetria`:
  ```
  C:\Users\Dokas\Desktop\f1-telemetry-analyzer\versoes\0.5.0-radio-e-replay\Automobilista-Telemetria-Setup-0.5.0-radio-e-replay.exe
  ```
- O app do jogo, num PowerShell:
  ```
  powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Dokas\Desktop\f1-telemetry-analyzer\tools\csp_app\instalar.ps1
  ```
- Abra o app pelo menu Iniciar ("Automobilista Telemetria") e confira, na aba **Coleta de dados** ("Versão do app") ou em **Sistema**: tem de aparecer `0.5.0-radio-e-replay`.

**2. Ligar a ferramenta de medição, antes de abrir o jogo**

Num PowerShell separado, que fica aberto a sessão toda:
```
cd C:\Users\Dokas\Desktop\f1-telemetry-analyzer\backend
..\.venv\Scripts\python -m ml.scripts.medir_geometria
```
Ela mostra `esperando o Assetto Corsa...` até o jogo abrir.

**3. Abrir o jogo** com o `rss_formula_rss_3_v6_2026` em Interlagos (`vhe_interlagos`, traçado `gp`), num treino sozinho.
- Na janela da ferramenta, espere `conectado; gravando em ...` e `carro rss_formula_rss_3_v6_2026, pista vhe_interlagos`, **sem** a palavra "ATENCAO".

**4. No jogo, ligue as 4 janelas** na barra de apps: "Rádio", "Minimapa", "Mapa aproximado" e "Replay da curva". Ponha o replay num canto, sem cobrir o centro.

**5. No app, na tela Sistema, "Mandar mensagem de teste":** confira o cartão e a voz no jogo.

**6. A medição, parado no box:** com o carro parado e sem acelerar, gire o volante **devagar** de um batente ao outro e volte, **duas vezes** (uns 10 segundos para cada lado).

**7. O teste do rádio:**
- Confira que a IA não está dirigindo. **Não aperte Ctrl+C no jogo:** lá ele passa o carro para a IA.
- Ande **pelo menos 8 voltas**, com **uma ida aos boxes depois da 3ª volta válida**.
- Para o FPS: desligue o "Replay da curva" por 2 ou 3 voltas e ligue de novo.
- Deixe a tela **Ao vivo** aberta no app.

**8. Encerrar a ferramenta:** com o carro parado no box, troque para a janela do PowerShell (Alt+Tab) e aperte **Ctrl+C lá**. Espere `salvo: ... (N amostras, ... Hz)`; a taxa deve ficar perto de 60 Hz. Se o jogo fechar antes, o arquivo do último minuto já está salvo.

**9. Feche o jogo e me avise:** "medi a geometria e testei o app 0.5.0".

**Depois disso:** a Parte D, a leitura do teste do rádio sem mudar nada (numa seção nova do relatório do pedido 36) e a Parte E, com o merge em `develop` no fim.

## Os primeiros passos, de 25/10 de madrugada (substituídos pelos de cima)


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

## Aviso de 25/10, às 12:20: "medi a geometria e testei o app 0.5.0", sem os arquivos

- **Antes de tudo:** a sessão do pedido 38 estava parada, a pasta estava em `etapa/m1-modelo-do-carro`, limpa, e sem trava do git.
- **O que procurei e não achei neste computador:**
  - **o arquivo da medição:** nenhum `geometria_*.parquet` em `data\ml\modelo_carro\`, nem em outro lugar do repositório, de `%APPDATA%`, de `%LOCALAPPDATA%`, da Área de Trabalho ou de Documentos. Só os arquivos dos testes automáticos, na pasta temporária;
  - **o app 0.5.0 instalado:** o app em `C:\Users\Dokas\AppData\Local\Programs\Automobilista Telemetria` continua na `0.4.0-redesenho` (o `app.asar` e o executável são de 17/10);
  - **as gravações do teste do rádio:** a última em `%APPDATA%\Automobilista Telemetria\data\recordings` é de 18/10, e a última em `data\recordings` é de 24/10, 13:43;
  - **os logs do app instalado:** o `backend.log` e o `desktop.log` são de 18/10. O 0.5.0 gira o log em 20 MB, e o `backend.log` tem 1 GB: o 0.5.0 não rodou.
- **Por isso a Parte D, a leitura do teste do rádio e a Parte E não começaram.** Nada foi medido nem lido do teste.
- **O que pode ter acontecido:** a ida ao jogo foi em outro computador, os arquivos ficaram noutra pasta, ou a ferramenta e o instalador não rodaram. Se os arquivos existirem em outro lugar, basta dizer onde. Se a sessão foi noutro computador, são precisos o `geometria_<data>_<hora>.parquet` (com o `.json` ao lado) e a pasta da gravação do app.

## 25/10, às 13:38: "agora está instalado"

- **O app 0.5.0 está instalado e rodando:** o `app.asar` em `C:\Users\Dokas\AppData\Local\Programs\Automobilista Telemetria` diz `0.5.0-radio-e-replay`, e o log girou como o 0.5.0 faz (o de 1 GB virou `backend.1.log`; o `backend.log` novo é de 13:39).
- **Ainda não há medição nem teste do rádio:** nenhum `geometria_*.parquet` e nenhuma gravação nova. Os passos 2 a 9 continuam valendo.
- **O app do jogo instalado é o 0.4.1, mais novo que o deste checkout.** Em `D:\SteamLibrary\steamapps\common\assettocorsa\apps\lua\radio_engenheiro` (de 24/10, 13:34), o `manifest.ini` diz `VERSION = 0.4.1` e o `radio_engenheiro.lua` tem a função que traz as janelas fora da tela de volta. É o commit `0092ed38` ("App do jogo 0.4.1"), que está só em `etapa/radio-unidades-e-replay`, **fora de `develop`** e fora desta branch, onde o app do jogo ainda é o 0.4.0.
  - **Por isso, pule a instalação do app do jogo no passo 1.** O `instalar.ps1` rodado deste checkout trocaria o 0.4.1 pelo 0.4.0 e tiraria a correção das janelas. O 0.4.1 tem tudo do 0.4.0 e mais essa correção.
  - **Fica para você decidir, fora deste pedido:** o merge do `0092ed38` em `develop`.

## Parte D — a geometria medida (29/10)

- **Antes de tudo:** as outras três sessões da pasta (o pedido 38, o 40 e o 41) estavam paradas; a pasta estava em `etapa/m1-modelo-do-carro`, sem trava do git. O pedido 41 deixou três arquivos sem commit (o pedido, o inventário e o relatório dele), que não são meus e ficaram como estavam.
- **Os commits do backlog e do `.gitignore`,** pedidos em 28/10, já estavam feitos nesta branch quando voltei (`a85d16ad` e `73565e79`, de 28/10, às 20:03 e 20:04). A linha com tabulação descrita no backlog não existia: faltava a linha `recordings/`, e o `a85d16ad` a acrescentou.
- **A sessão usada:** `data\ml\modelo_carro\geometria_2026-10-28_13-23-49.parquet` (20.292 amostras, 339 s, 59,8 Hz). O `geometria_2026-10-28_13-20-17` (teste de conexão) não foi usado.
- **O desvio do roteiro:** 1 volta completa, e não 3. Os portões decidiram: os de `L` e de `x_v` passaram com folga, então a volta bastou para eles.
- **Comando:** `python -m ml.scripts.m1_modelo_carro geometria --sessao data/ml/modelo_carro/geometria_2026-10-28_13-23-49.parquet`. A saída completa está em `2026-10-25_39_m1-geometria-medida_geometria.json`.

| parâmetro | medido | portão | resultado | usado no modelo |
|---|---|---|---|---|
| `L` | **2,964 m** (p5 a p95: 2,952 a 2,965 m) | 2,8 a 3,8 m, faixa < 3% | **passa** (0,46%) | 2,964 m, medido |
| `b = w_f · L` | de 1,236 a 1,336 m, conforme o `w_f` da rodada (0,417 a 0,451) | — | — | por rodada |
| `h` | `cgHeight` = **0,271 m**; `h/L` = **0,0915** | — | — | 0,0915 |
| `k_δ` (média) | 0,312 rad, **R² = 0,744** | 0,05 a 1,5 rad, R² ≥ 0,95 | **não passa** | **0,304 rad**, pela regressão em regime permanente (o caminho do ADR 0024) |
| `k_δ` esquerdo / direito | 0,297 (R² 0,9996) / 0,327 (R² 0,443) | — | — | — |
| `x_v` | **1,209 m** do eixo traseiro (IC 95%: 1,201 a 1,214; pelo eixo dianteiro, 1,214) | meia-largura < 0,2 m | **passa** (0,006 m) | 1,209 m, medido |

- **Por que `k_δ` não passou: uma batida, e não a falta de dados.** Aos 325 s da sessão há um impacto de 18,9 g, e o carro para. Depois dele, a direção do pneu dianteiro direito fica 0,57 rad fora do que o volante pede: a direção daquele lado entortou. Os 566 pontos ruins (3%) vêm todos depois do impacto. Como o portão falhou por outro motivo que não a falta de dados, segui o caminho registrado (a regressão de reserva) e não parei. **Se você preferir regravar a sessão sem a batida, o valor muda pouco:** antes do impacto, `k_δ` = 0,2974 rad, com R² de 0,9998, os dois lados iguais (0,2969 e 0,2980) e a convergência simétrica de ±0,003 rad. O usado, 0,304, fica 2% acima.
- **`h/L` pelo `cgHeight` contra o das cargas:** 0,0915 contra 0,135 a 0,163 (pedido 37). As cargas incluem a transferência pela suspensão e pela aerodinâmica, que a altura do centro de massa sozinha não tem. O modelo usa 0,0915, pelo ADR 0024.
- **`L/k_δ` contra a M0:** 9,75 (9,97 com o valor de antes da batida), contra 10,1 a 10,6 da razão volante ÷ curvatura da M0, que inclui a deriva dos pneus.
- **A linearidade:** antes da batida, a razão local vai de 0,296 rad perto do centro a 0,299 nos batentes; é linear em toda a faixa. O volante vai de −1,0 a +1,0: **é uma fração do curso, e no batente a roda vira cerca de 0,30 rad (17°).**
- **`x_v` fica perto do centro de massa:** de 0,03 a 0,13 m atrás dele, conforme a rodada. A correção da velocidade lateral é pequena (de 0,02 a 0,08 m/s com 0,6 rad/s de guinada). A falta da parte geométrica no ângulo de deriva, vista no pedido 37, vem do pneu, e não do ponto onde a velocidade é medida.

## Parte E.1 e E.2 — a física com a geometria medida, só nas sessões de treino

Comando: `python -m ml.scripts.m1_modelo_carro validar --fase treino` (3 min). **Nenhuma sessão de teste foi lida nesta fase.** Em cada rodada, a geometria fica fixa (`L` = 2,964 m, `k_δ` = 0,304 rad, `x_v` = 1,209 m, `h/L` = 0,0915), `b = w_f · L` vem das cargas das 4 sessões de treino, a velocidade lateral é levada ao centro de massa, e os 7 parâmetros são ajustados por mínimos quadrados. Saída completa: `2026-10-25_39_m1-geometria-medida_fisica_treino.json`.

**Os parâmetros por rodada:**

| rodada (sessão de fora) | `w_f` | `b` (m) | `b − x_v` (m) | `Cα` (1/rad) | `μ` | `k²` (m²) | `κ_D` (1/m) | `c0` (m/s²) | `s_T` | `β_B` (m/s²) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `2026-10-15_23-24-50` | 0,428 | 1,268 | 0,058 | 32,7 | 1,68 | 3,31 | **0,0003** | **0** | 1,08 | 19,2 |
| `2026-10-17_01-02-22` | 0,431 | 1,276 | 0,067 | 32,8 | 1,67 | 3,12 | **0,0003** | **0** | 1,04 | 20,7 |
| `2026-10-17_16-17-08` | 0,451 | 1,335 | 0,126 | 29,9 | 1,53 | 2,44 | **0,0003** | **0** | 0,89 | 17,6 |
| `2026-10-18_12-38-44` | 0,425 | 1,261 | 0,051 | 32,0 | 1,65 | 3,52 | **0,0003** | **0** | 1,06 | 21,3 |
| `2026-10-21_20-30-54` | 0,417 | 1,237 | 0,028 | 32,9 | 1,70 | 3,84 | **0,0003** | **0** | 1,12 | 21,9 |

- **No limite, nas 5 rodadas:** o arrasto (`κ_D`, no mínimo de 0,0003) e a desaceleração sem acelerador (`c0`, em 0). O resto fica dentro das faixas e estável entre as rodadas, menos na rodada sem a sessão do pacote 0.4.0, que tem `k²` e `μ` mais baixos.
- **A transferência de carga entrou nas 5 rodadas** pela regra dos 2%: o erro de um passo cai de 0,082–0,085 para 0,078–0,081 (4% a 5%).
- **`k²` de 2,4 a 3,8 m²** (raio de giração de 1,6 a 2,0 m) fica alto para um carro de 2,96 m de entre-eixos.

**O erro da física (R1) contra a persistência (R0), nas próprias sessões de treino** (inícios a cada 0,1 s; erro normalizado do ADR 0022; skill = 1 − R1 ÷ R0):

| rodada (sessão de fora) | 1 passo: R1 / R0 | skill em 0,25 s | **skill em 0,5 s** | skill em 1,0 s | `vy` em 0,5 s: R1 / R0 (m/s) |
|---|---|---:|---:|---:|---|
| `2026-10-15_23-24-50` | 0,078 / 0,089 | 0,21 | **0,03** | −0,57 | 0,82 / 0,68 |
| `2026-10-17_01-02-22` | 0,081 / 0,093 | 0,23 | **0,04** | −0,58 | 0,85 / 0,73 |
| `2026-10-17_16-17-08` | 0,079 / 0,091 | 0,25 | **0,18** | −0,05 | 0,73 / 0,71 |
| `2026-10-18_12-38-44` | 0,080 / 0,090 | 0,20 | **0,00** | −0,66 | 0,87 / 0,70 |
| `2026-10-21_20-30-54` | 0,080 / 0,090 | 0,19 | **−0,06** | −0,85 | 0,89 / 0,69 |

**Contra a regra antiga** (pedido 37, rodada sem `2026-10-15_23-24-50`, nas mesmas sessões de treino):

| | 1 passo: R1 / R0 | skill em 0,25 s | skill em 0,5 s | skill em 1,0 s |
|---|---|---:|---:|---:|
| regra das regressões cinemáticas (`L` = −0,18 m) | 0,095 / 0,089 | −0,02 | −0,04 | −0,09 |
| `L` e `k_δ` ajustados junto (diagnóstico do 37, não adotado) | 0,078 / 0,089 | 0,21 | 0,09 | −0,39 |
| **a geometria medida (este pedido)** | **0,078 / 0,089** | **0,21** | **0,03** | **−0,57** |

- **A geometria medida faz a física bater a persistência em um passo e em 0,25 s,** nas 5 rodadas, o que a regra antiga não fazia.
- **Em 0,5 s ela empata com a persistência** (skill de −0,06 a 0,18), e em 1,0 s perde. A velocidade longitudinal e a guinada saem bem melhores que na persistência. **A velocidade lateral sai pior:** em malha aberta, o erro dela cresce mais rápido que o da persistência.
- **O que isso diz do critério 1** (skill da M1 contra R0 ≥ 0,50): a correção aprendida teria de cortar mais da metade do erro da física em 0,5 s. Nada foi mudado por isso. A fase de teste segue como registrada.

## Parte E.3 — a M1 e a validação: não aprovada

Comando: `python -m ml.scripts.m1_modelo_carro validar --fase teste` (10 min), rodado depois do commit da fase de treino (`00fff510`). O texto completo, para quem não é da área, está em `docs/modelo_fisico_m1.md`, seção 6; os números, em `validacao.json`.

**A tabela do veredito** (todos em 0,5 s; 39.142 casos nas 5 sessões de teste):

| nº | critério | medido | resultado |
|---|---|---|---|
| 1 | skill contra R0 ≥ 0,50 | **0,202** | **não passa** |
| 2 | skill contra R1 ≥ 0,20 | **0,174** | **não passa** |
| 3 | limite inferior do IC 95% do skill contra R1 > 0 | 0,159 (IC 0,159 a 0,191) | passa |
| 4 | skill contra R1 positivo em pelo menos 4 das 5 sessões | 5 de 5 | passa |
| 5 | \|viés\| de cada grandeza ≤ 25% do erro de R1 | `vx` 3,9%; `vy` 2,2%; `r` 3,3% | passa |
| 6 | o intervalo de 90% cobre de 80% a 97%, no passo de Δt | 85,7% (`vx` 93,2%; `vy` 81,5%; `r` 82,5%) | passa |
| 7 | pelo menos 5 sessões testáveis | 5 | passa |

- **O erro combinado em 0,5 s:** M1 0,351; R1 0,425; R0 0,440. Em 0,25 s, a M1 tem skill de 0,30 contra R0; em 1,0 s, −0,27.
- **Onde a M1 falha:** nas curvas, que são 65% dos casos. Ali a física perde para a persistência (skill −0,07) e a correção a leva só a 0,13. Fora das curvas (reta, freada, tração), a física sozinha já tem skill de 0,65 a 0,72 contra a persistência.
- **Por grandeza, em 0,5 s:** a correção tira o viés da física na velocidade longitudinal (+0,68 m/s) e corta o erro dela pela metade. A guinada sai melhor que nas duas referências. **A velocidade lateral só empata com a persistência** (0,68 contra 0,70 m/s), e é ela que pesa no erro combinado.
- **Por sessão:** o skill contra R0 vai de 0,14 a 0,34 e contra R1 de 0,15 a 0,20. A sessão do pacote 0.4.0 (`2026-10-17_16-17-08`) é a melhor nos dois.

**A correção por rodada:** 2.000 passos (400 de cada regime), de 68 a 89 s para ajustar os 3 Processos Gaussianos. O ruído aprendido fica entre 34% e 53% da variância do resíduo de `vx`, e entre 4% e 9% no de `vy` e no de `r`. Os comprimentos de cada rodada estão em `validacao.json`.

**"Não conclusivo": o corte não funcionou.** Ele saiu 1,000 nas 5 rodadas (o teto do índice), e nenhum caso foi marcado. O índice registrado chega a 1 em mais de 1% dos casos de treino, porque os Processos Gaussianos aprenderam comprimentos curtos (de 0,06 a 0,45 desvio-padrão na velocidade lateral, na guinada e no volante). Isso não muda o veredito: as métricas usam todos os casos. **Mas, com o índice como está, a M1 não sabe dizer quando está fora dos dados.**

**As figuras** (rodada sem a sessão `2026-10-21_20-30-54`, volta 6):
- **a freada da C01**, a 266 km/h (`figura_c01.png`): a M1 segue o gravado quase em cima da linha. Em 0,5 s, ela erra a velocidade em 0,08 m/s, contra 0,71 da física sozinha e 7,2 da persistência;
- **a curva lenta, a C10**, a 76 km/h, com o volante em 0,87 (`figura_c10.png`): a física e a M1 fazem o carro escorregar para fora (`vy` de 1,5 m/s em 0,5 s e de 3,5 m/s em 1,0 s) e exageram a guinada; o carro gravado faz a curva com `vy` perto de zero.

**A indicação para a M2:** a correlação de Spearman entre o resíduo da M1 no primeiro passo e a temperatura média dos pneus é **−0,22 na velocidade longitudinal** e quase zero na lateral (0,00) e na guinada (−0,01). A temperatura muda junto com o combustível e o desgaste ao longo da sessão, então isso não separa a causa.

**Nenhum critério, corte ou parâmetro foi mudado depois de ver o teste.**

### Testes

- **`tests/test_m1_modelo_carro.py`: 16 passaram** (os 14 do pedido 37, mais o início da figura dentro do trecho e o veredito com números conhecidos).
- **`tests/test_m1_geometria_medida.py`: 6 passaram.**
- **A suíte do backend:** ver abaixo.

**A suíte do backend: 816 passaram em 8 min 13 s** (`python -m pytest tests -q`), com os 22 da M1. Saída em `pytest.txt`.

## O que precisa da sua decisão

1. **O resto da Parte F e o merge em `develop`.** O pedido diz "se um critério não passar, relate e pare". Parei aqui. Já estão escritas a seção 6 de `docs/modelo_fisico_m1.md` (o veredito, para quem não é da área) e o fechamento da unidade do volante e do relógio na M0. **Não fiz:**
   - a linha do cálculo do tempo de volta em `docs/arquitetura_ml.md` ("M1 feita, não aprovada");
   - o que muda em `docs/integracao_ml_e_empacotamento.md` e em `docs/backlog.md`;
   - a nota sobre o ADR 0004: o resultado não muda nada nele, porque a M1 não foi aprovada e o ADR 0004 só seria revisto com a M4;
   - o merge em `develop`, com os conflitos do pedido 40 (manter os dois lados) e as suítes depois.

   Se você quiser, faço tudo isso, documentando o resultado negativo como o ADR 0022 manda.
2. **O `k_δ` da batida.** O modelo usou 0,304 rad, pelo caminho do ADR 0024. Antes da batida, o pneu dá 0,2974 rad, com R² de 0,9998. A diferença é de 2%, e é improvável que ela mude o veredito, mas a decisão de regravar é sua.
3. **O "não conclusivo",** que não funcionou com o índice registrado. Mudar a regra exige um ADR antes de rodar de novo.

## Coisas que não batiam com o contexto

- **O carro do retrato é conhecido:** a página estática dele diz `rss_formula_rss_3_v6_2026` em `vhe_interlagos` (acima).
- **Duas sessões de implementação na mesma pasta (ADR 0008).** Quando comecei, a pasta estava em `etapa/modelo2-erro-tecnica-e-estilo`, do pedido 38, sem nenhum commit além de `develop`. Conferi só isso, e não se havia outra sessão ativa nela. Havia: a sessão do pedido 38 estava trabalhando ali.
  - **00:40:09:** troquei para `etapa/m1-modelo-do-carro` (`git switch`);
  - **00:41:02:** a sessão do 38 commitou o texto do pedido 38 e as três pesquisas (`docs/tecnica_de_pilotagem_*.md`). O commit (`f38f89a5`) caiu na branch do 37, por causa da minha troca;
  - **00:41:17:** o meu commit do pedido 39 (`23b2ea49`) ficou por cima dele.
  - **A sessão do 38 parou** e deixou o relatório dela sem commit (`docs/handoff/2026-10-24_38_modelo2-erro-tecnica-e-estilo_relatorio.md`), com as opções. Ela também tirou a cópia não commitada do ADR 0023 de `docs/decisoes/`. Eu não mexi no relatório dela, no anexo dela, nem no `f38f89a5`.
  - **O que isso muda aqui:** a branch do 37 e do 39 tem, entre o `5c8ed449` e o `23b2ea49`, o commit `f38f89a5` (só documentos do 38, 4 arquivos, nenhum código). Se nada for feito, ele vai para `develop` com o merge do fim deste pedido.
  - **Decidido em 25/10:** o `f38f89a5` fica nesta branch (seção "Mensagem de 25/10, às 11:57"). Daqui para frente, antes de trocar de branch, confiro se outra sessão está ativa na pasta.
- **`recordings/` na raiz** continua fora do git; não mexi.

Arquivo: `docs/handoff/2026-10-25_39_m1-geometria-medida_relatorio.md`
