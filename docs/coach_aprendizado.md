# Coach na fase de aprendizado (pedido 14, ADR 0013 e 0016)

Branch: `etapa/coach-geometria-oficial`, com o `develop` trazido em 2026-10-04 (merge `13e4a359`).

## 1. Critérios do coach na geometria oficial (registrados antes de mudar o código)

Os critérios a–d são os do pedido 11, com os mesmos limites. O (e) é novo. A medição é feita por `backend/tools/validate_coach_geometry.py`.

| | o que mede | limite |
|---|---|---|
| **a** | Projeção do coach contra `TrackGeometry.project_sequence`, nas voltas válidas de três sessões: MergeFix (`2026-06-20_13-13-02`), cache atual (`2026-08-16_03-30-14`) e sem cache (`2026-08-09_19-20-59`). O coach projeta a sessão inteira, amostra por amostra e na ordem gravada, com um projetor só, como ao vivo. | cada sessão: p99 \|Δs\| ≤ 0,5 m e p99 \|Δd\| ≤ 0,2 m |
| **b** | Tempo de projeção por amostra, nas mesmas amostras de (a) | p99 ≤ 1 ms |
| **c** | Tempos por microsetor do coach (volta lida pelo carregador do app e reprojetada) contra os do store do ML, nas mesmas fronteiras, na volta válida mais rápida de 5 sessões diferentes | máximo ≤ 0,02 s por microsetor; soma = tempo da volta do store ± 0,02 s |
| **d** | Ensaio: o coach roda amostra por amostra sobre duas sessões inteiras (20/06 e 09/08) | nenhuma frase com "ganh", "ideal" ou "otimo" |
| **e** (novo) | Salto de projeção nas voltas limpas: \|Δs\| entre a projeção do coach e `TrackGeometry.project_sequence`, em todas as amostras das voltas limpas das sessões de (a) e da sessão rotulada de 04/10 (todos os seus arquivos). Volta limpa = válida, única, com o relógio conferido, sem `relogio_suspeito` e sem box (filtros dos pedidos 12 e 13, inventário de `data/ml/origem/`). | cada sessão: \|Δs\| máximo ≤ 2 m |

### Achado antes do registro: o store do ML erra a linha de chegada por um passo da grade

Ao preparar o passo 3, medi o tempo de volta e o microsetor 0 nas 5 voltas de (c) de três formas: pelo jogo, pelo store e pelo período verdadeiro, que é o tempo entre duas passagens pelo mesmo ponto, com s = 0 interpolado.

| volta | jogo | período verdadeiro | store do ML | diferença do store |
|---|---:|---:|---:|---:|
| `2026-08-16_03-30-14` | ~84,873 s | 84,8735 s | 84,8478 s | −25,7 ms |
| `2026-06-18_20-06-03` | ~85,293 s | 85,3277 s | 85,2997 s | −28,0 ms |
| `2026-06-20_13-13-02` | ~85,467 s | 85,4674 s | 85,4415 s | −26,0 ms |
| `2026-08-09_19-20-59` | ~85,494 s | 85,4982 s | 85,4717 s | −26,5 ms |
| `2026-06-14_12-23-46` | ~85,557 s | 85,5641 s | 85,5378 s | −26,3 ms |

- **A diferença é o tempo de um passo da grade na reta** (2 m a cerca de 280 km/h, de 25,7 a 26,5 ms), e cai inteira no microsetor 0.
- **A causa:** `ml/preprocessing/resampling.py::_reference_clock_to_grid` zera o relógio em s = 0 da grade, mas usa como período o `span` dos tempos na grade, que fica um passo mais curto que a volta.
- **O que isso explica:** é o "+26 ms" do critério (c) no pedido 11. O coach estava certo e o store, curto. Explica também o viés de −0,034 s do relógio no microsetor 0 no pedido 12: −26 ms deste passo, mais o viés de −8 ms que aparece em todo microsetor.

**Consequência para o critério (c):** com o coach seguindo a convenção de s = 0 interpolado (passo 3), o microsetor 0 e a soma vão diferir do store em cerca de 26 ms, acima do limite de 20 ms, por causa do store. O critério continua como foi escrito, contra o store. Para a decisão, o relatório trará também, **sem valer como critério**, a mesma comparação contra os microsetores do ML recalculados com o período verdadeiro. Não mexi no ML nem no store.

## 2. O que mudou no coach (Parte B)

### Linha de chegada (passo 3)

- **Microsetores fora da pista** (`reference_model.microsector_splits`), usados no treino, no replay e no critério (c): a volta vai de s = 0 a s = 0. A bandeira é interpolada no fim da volta, onde a gravação passa por s = 0 alguns metros antes de o jogo zerar o cronômetro. O início é a bandeira menos um período, o tempo entre duas passagens pelo primeiro ponto da volta. Antes, o início era extrapolado para trás a partir da primeira amostra.
- **Ao vivo** (`driving_coach.on_frame`, modelo na geometria oficial): a volta vira na passagem por s = 0, interpolada entre as duas amostras. Antes, virava quando o contador de voltas do jogo mudava, alguns metros depois. Um salto de mais de 5 % da volta que não seja a linha (box pelo menu, reset) recomeça a contagem sem falar.
- **Relógio:** é o cronômetro do jogo, que é o relógio da física. Na virada, ele é costurado pela distância entre as duas amostras sobre a velocidade. O `timestamp` do gravador não serve: ele engasga (medido em 04/10, +357 ms numa amostra e +2 ms na seguinte, com o carro andando 21 m).
- **O viés de −0,034 s do relógio no microsetor 0 (pedido 12) tem a mesma causa** do "+26 ms" do pedido 11: o store do ML encurta a volta e o microsetor 0 em um passo da grade (seção 1). São −26 ms do passo, mais o viés geral de −8 ms.

### Continuidade (passo 4)

- **`MapMatchingEngine` ganhou um limite rígido de avanço por amostra:** velocidade × intervalo × 1,5 + 5 m. Sem velocidade ou intervalo, vale 60 m, como no ML. Dentro do limite, vence o trecho mais perto, sem a penalidade antiga. Se nada dentro dele está a menos de 50 m do carro, o carro foi movido de verdade, e a projeção acompanha.
- **A opção fica desligada por padrão,** e só o projetor do coach (`CoachProjector`) a liga. Mapa e painel não mudaram.

### Rodadas dos critérios

Os critérios e os limites não mudaram entre as rodadas. Cada correção resolveu um defeito de implementação com causa medida.

| rodada | código | a | b | c | d | e | o que corrigiu |
|---|---|---|---|---|---|---|---|
| 1 | `fe88367f` | passou | falhou (p99 1,98 ms) | falhou | passou | falhou (até 17,3 m) | o intervalo vinha do `timestamp`, que engasga, e o motor calculava a normal de todo candidato. Além disso, a suíte rodava em paralelo |
| 2 | `66e4b720` | passou | passou (0,94 ms) | falhou | passou | falhou (até 8,0 m) | depois de um buraco de gravação, a penalidade antiga preferia um ponto 8 m atrás |
| 3 | `c753df6d` | passou | passou | **falhou** | passou | passou | — |

### Números da rodada 3

| | critério | medido | resultado |
|---|---|---|---|
| **a** MergeFix (39 voltas) | p99 \|Δs\| ≤ 0,5 m; p99 \|Δd\| ≤ 0,2 m | \|Δs\| p99 0,037 m (máx. 31,4 m, fora das voltas limpas); \|Δd\| p99 0,0018 m | passou |
| **a** cache atual (7 voltas) | idem | \|Δs\| p99 0,036 m (máx. 0,04 m); \|Δd\| p99 0,0015 m | passou |
| **a** sem cache (52 voltas) | idem | \|Δs\| p99 0,037 m (máx. 29,9 m, fora das voltas limpas); \|Δd\| p99 0,0019 m | passou |
| **b** (582.527 amostras) | p99 ≤ 1 ms | p50 0,33 ms, p99 0,91 ms | passou |
| **c** (5 voltas) | ≤ 0,02 s por microsetor; soma = tempo do store ± 0,02 s | microsetor 0: +0,026 a +0,029 s; microsetores 1 a 59: no máximo 0,002 a 0,004 s; soma − store: +0,026 a +0,029 s | **falhou** |
| **d** (20/06 e 09/08) | nenhuma frase proibida | 303 frases, 0 proibidas | passou |
| **e** (voltas limpas: 3 sessões de (a) e 3 arquivos de 04/10; os outros 4 arquivos de 04/10 não têm volta limpa) | \|Δs\| máx. ≤ 2 m por sessão | 0,04 a 0,31 m | passou |

**Diagnóstico do (c), que não vale como critério.** Contra os microsetores do ML com o período verdadeiro, a diferença máxima por microsetor fica entre 0,002 e 0,004 s, e a soma bate com o período com diferença de 0,1 a 1,4 ms. Nas 5 voltas, o (c) só falha pelo passo do store no microsetor 0. Os ±78 ms entre os microsetores 25 e 26 da volta de 20/06, vistos no pedido 11, sumiram com a continuidade rígida.

## 3. Desvio do pré-registro

O critério (c) falhou porque a régua, o store, tem um erro medido. Ao zerar o relógio usando o período da grade, o store encurta toda volta e o microsetor 0 em um passo da grade: de 25,7 a 28,0 ms nas 5 voltas. Isso foi conferido contra o cronômetro do jogo (84,8735 s contra 84,873 s). Contra o ML com o período corrigido, o (c) passa: no máximo 3,7 ms por microsetor, e a soma bate com o período em ±1,4 ms. Nenhum limite foi mudado.

**Decisão do Eduardo em 04/10:** seguir para as Partes C e D e para o merge. O ML não é corrigido agora. A correção entra no item "Reconstrução do store" do backlog, junto com o portão das voltas com box, as voltas rotuladas e a pasta do app instalado, num pedido próprio depois do coach.

## Registro da parada (antes da decisão)

Pelo pedido, com o (c) falhando, parei antes da Parte C. Não fiz merge, não treinei nem regravei modelo e não mexi no ML nem no store. A decisão do que fazer com o store está no relatório.

## 4. As duas referências (Parte C, ADR 0016)

### O modelo

O modelo do coach guarda as duas referências, as duas voltas reais e completas, cada uma com o tempo, o início de frenagem e a velocidade mínima de cada microsetor. A ativa é escolhida por configuração: a variável de ambiente `AT_COACH_REFERENCE`, com `volta_ia` (padrão) ou `minha_melhor`.

| referência | como é escolhida | hoje |
|---|---|---|
| `volta_ia` (padrão) | a melhor volta limpa com origem `ia`, de sessões gravadas a partir de 04/10, no mesmo `carModel` e na geometria oficial | 84,828 s, `2026-10-04_03-42-10#0013` (parte 2, volta 26), entre 13 voltas limpas da IA |
| `minha_melhor` | a melhor volta limpa `humano` com equipamento `atual`, no mesmo carro | 89,389 s, `2026-10-04_02-24-04#0018` (parte 2, volta 5), entre 11 voltas limpas suas |

- **Limiar de fala:** continua sendo duas vezes a sua oscilação por microsetor (mediana menos melhor), com mínimo de 0,06 s, e é calculado só com as suas 11 voltas limpas. A oscilação tem mediana de 0,079 s e p90 de 0,218 s, então o limiar típico fica em cerca de 0,16 s.
- **Identidade das voltas:** o treino (`tools/train_reference_model.py`) escolhe as voltas pelo inventário rotulado (`data/ml/origem/`) e as lê pela identidade do ML (`<sessão>#<ordem>`). A identidade do replay (`rec__<sessão>__<n>`) colaria, na sessão de 04/10, a volta 5 da IA (parte 1) com a sua volta 5 (parte 2), porque o contador do jogo recomeça quando a sessão é reiniciada.
- **Onde o treino grava:** por padrão, no modelo do repositório, que é o lido pelo app de desenvolvimento. O modelo do app instalado só é gravado se for pedido com `--saida`.
- **Modo antigo:** o `best_per_microsector` continua desligado.

### O que o coach diz

- **Cada frase nomeia a referência:** "Setor 2: 0.34s atras da volta da IA neste trecho (1.59s contra 1.25s). Minima da IA 157 km/h, a sua 122 km/h."
- **A freada vem em relação à referência,** quando a referência começa a frear naquele microsetor e você começou a frear a até 60 m dela: "A IA freia 34 m depois de voce" ou "Na sua melhor volta voce freou 7 m depois". O início de frenagem é o pedal passando de 0,15, o mesmo critério da Fase 2b, na referência e ao vivo.
- **No máximo 3 frases por volta:** até o pedido 14, as primeiras que passavam do limiar; desde o pedido 15, só nos 3 trechos de foco, uma por trecho (seção 9).
- **No fim da volta, um resumo:** "Volta fechada. Maiores diferencas para a volta da IA: setor 32 (0.67s), setor 38 (0.66s) e setor 43 (0.48s). Volta da IA: 84.83s." Diferenças que arredondam para 0,00 s ficam de fora.
- **Trechos não comparados:**
  - o microsetor em que a contagem começa (parcial), exceto na linha de chegada;
  - o microsetor com o carro parado (abaixo de 5 km/h);
  - o microsetor no pit lane (mais de 10 m fora da linha e abaixo de 90 km/h).

  O ensaio mostrou por quê: saindo do box, o coach dizia "52.84s atras … a sua 0 km/h".
- **Estilo:** sem acentos, decimal com ponto, e nunca "ganh", "ideal" ou "otimo".

### Textos alterados

| arquivo e linha | antes | agora |
|---|---|---|
| `frontend/src/components/CoachingFeed.tsx:76` (rótulo, com o mapa nas linhas 53–56) | `REFERENCIA 1.96s` | `VOLTA DA IA 1.38s` ou `SUA MELHOR 1.50s`; `REFERENCIA` só com um modelo antigo |
| `backend/core/live/driving_coach.py:501` | "Setor N: X.XXs atras da sua volta de referencia neste trecho (…)" | "Setor N: X.XXs atras da volta da IA neste trecho (…)" ou "… da sua melhor volta …" |
| `backend/core/live/driving_coach.py:686–705` | "Na referencia: freada em 1578 m, minima de 110 km/h." | "A IA freia 12 m depois de voce; minima da IA 110 km/h, a sua 98 km/h." ou "Na sua melhor volta voce freou 12 m depois; minima na sua melhor volta 110 km/h, agora 98 km/h." |
| `backend/core/live/driving_coach.py:607` | "Volta fechada. X.XXs somando os trechos em que ficou atras da sua volta de referencia; a maior diferenca no setor N (…)." | "Volta fechada. Maiores diferencas para a volta da IA: setor A (…), setor B (…) e setor C (…). Volta da IA: 84.83s." |

O layout não mudou.

## 5. Testes e ensaio (Parte D)

- **Testes novos** (`backend/tests/test_coach_learning_phase.py`, 23 testes; 38 execuções, porque duas classes herdam os casos de outra):
  - continuidade rígida, linha de chegada e engasgo do relógio;
  - `volta_ia` só com voltas da IA de sessões novas, e `minha_melhor` só com `humano` de equipamento `atual`;
  - teto de 3 frases e resumo dos 3 maiores;
  - sinal de "antes" e "depois";
  - frases que nomeiam a referência e não contêm "ganh", "ideal" ou "otimo";
  - escolha da referência por configuração;
  - trechos parciais, parados e no box.
- **Testes antigos atualizados:** os que esperavam a freada em metros absolutos e o resumo antigo (`test_coach_reference_lap.py`), e o do script de treino (`test_lap_origin.py`).
- **Suítes:** backend com **554 testes** passando, frontend com **137** (vitest) e build do frontend sem erro.

### Ensaio nas suas voltas de 04/10

O coach rodou amostra por amostra sobre os arquivos da sessão, nos dois modos, e cada frase ficou ligada à volta em que foi dita. Foram 32 voltas suas, das quais 11 válidas.

| | volta_ia | minha_melhor |
|---|---|---|
| frases por volta, nas 11 válidas | 3,0 (máx. 3) | 2,5 (máx. 3) |
| frases de trecho, nas 32 voltas | 94 | 79 |
| resumos de fim de volta | 26 | 26 |
| microsetores mais citados (válidas) | 2 (11), 0 (6), 1 (5), 3 (3) | 8 (4), 2 (3), 43, 47, 9, 38, 40 e 41 (2 cada) |
| frases proibidas | 0 | 0 |

- **Mais de 3 frases numa volta do ML** (até 6) só acontecem em voltas inválidas, com pausa ou ida ao box: o coach recomeça a contagem depois do salto, e a volta do ML junta os dois trechos.
- **Critério (d) refeito com o coach final:** 188 frases, nenhuma proibida, no máximo 3 por volta.

## 6. Merge e modelo

- **Merge:** `etapa/coach-geometria-oficial` entrou em `develop` (`be7e8901`). Uma correção posterior, do resumo com diferenças zeradas, veio em `bffa135f`.
- **Backup do modelo do repositório:** `data/reference_models/backup/vhe_interlagos.2026-10-04.antes-do-pedido-14.json` (sha256 `9d08d705…`).
- **Geometria oficial exportada para o app de desenvolvimento:** `data/reference_models/vhe_interlagos.geometry.json` (`0ed16f0dd2225990`). Sem ela, o coach fica calado.
- **Modelo treinado com o código de `develop`:** `data/reference_models/vhe_interlagos.json` (sha256 `9a2ce243…`). O modelo do app instalado ficou como estava (`9d08d705…`).
- **Leitura pelo app:** o `AssistedAnalysisService` (o mesmo do `main.py`) leu o modelo e a geometria nos dois modos.
- **Ensaio numa volta sua** (91,74 s, `03-21-52#0002`):
  - `volta_ia`: 3 frases (setores 2, 11 e 12) e o resumo (setores 32, 38 e 43);
  - `minha_melhor`: 1 frase (setor 32, 0.64 s) e o resumo (setores 32, 38 e 26).

  Na sua melhor volta, o modo `minha_melhor` fica calado, porque ela é a própria referência.

## 7. Limitações

- **As 3 frases eram as primeiras, não as maiores** (resolvido no pedido 15 com os trechos de foco, seção 9). Contra a IA, o limiar é baixo para as diferenças que existem, e as 3 frases quase sempre caem no começo da volta (S do Senna, microsetores 0 a 3). As maiores diferenças só aparecem no resumo: na volta de 91,74 s, as frases foram para os setores 2, 11 e 12 (0,07 a 0,34 s), e os maiores foram 32, 38 e 43 (0,48 a 0,67 s). Se incomodar, as opções são subir o limiar contra a IA ou falar os 3 maiores de cada terço da volta, mas isso é decisão sua.
- **A freada só aparece se você começou a frear a até 60 m do ponto da referência e antes de o microsetor terminar.** No ensaio, poucas frases trazem a freada (2 contra a IA e 1 contra a sua melhor).
- **As referências vêm de uma sessão só** (04/10), com 13 voltas da IA e 11 suas. A cada sessão nova, rode `python tools/atualizar_coach.py` (seção 10), que faz os passos que antes eram manuais.
- **O store do ML continua um passo curto** no microsetor 0 até a "Reconstrução do store" (backlog).
- **O app instalado continua com o coach antigo** e com o modelo antigo até ser reempacotado.

## 8. Como abrir o app de desenvolvimento para treinar com o coach ligado

1. **Feche o app instalado,** inclusive na bandeja do Windows. Ele usa a mesma porta (8000), e os dois abertos gravam em dobro.
2. **Abra um PowerShell na pasta do projeto** (`C:\Users\Dokas\Desktop\f1-telemetry-analyzer`).
3. **Só na primeira vez, ou depois de atualizar o código, gere o frontend:**
   ```
   cd frontend
   npm.cmd run build
   cd ..
   ```
4. **Escolha a referência e abra o app:**
   ```
   $env:AT_BACKEND_USE_PYTHON_RUNNER = 'true'
   $env:AT_COACH_REFERENCE = 'volta_ia'
   cd desktop
   npm.cmd run desktop:prod:autostart
   ```
   Para comparar com a sua melhor volta, use `$env:AT_COACH_REFERENCE = 'minha_melhor'`.
5. **Abra o Assetto Corsa** em Interlagos, com o `rss_formula_rss_3_v6_2026`. A gravação começa sozinha quando o carro entra na pista. As frases aparecem no painel "AI Coaching", com o rótulo **VOLTA DA IA** ou **SUA MELHOR**, e o resumo sai ao cruzar a linha.
6. **O coach usa dois arquivos,** ambos fora do git: `data/reference_models/vhe_interlagos.json` (o modelo) e `data/reference_models/vhe_interlagos.geometry.json` (a geometria). Sem a geometria, o coach fica calado e avisa uma vez no log.
7. **Para treinar sem o coach,** feche o app e renomeie `data/reference_models/vhe_interlagos.json` (do repositório). Devolva o nome depois.
8. **No fim, feche o app.** As sessões ficam em `data/recordings`. Para elas entrarem nas referências, rode `python tools/atualizar_coach.py` (seção 10).

## 9. Trechos de foco (pedido 15)

### Como o foco é escolhido

- **Antes de cada volta,** o coach escolhe 3 trechos de foco: os 3 microsetores com a maior diferença mediana para a referência ativa, nas últimas 5 voltas válidas da sessão.
- **Volta válida da sessão,** para o foco:
  - começou na linha de chegada;
  - teve todos os 60 microsetores comparados, então fica de fora a volta com box, com o carro parado ou que começou a contar no meio;
  - não teve a IA no volante em nenhuma amostra.
- **Enquanto a sessão não tem 5 voltas válidas,** o foco vem das suas voltas no modelo: a sua mediana em cada microsetor menos a referência ativa.
- **Só entra no foco um trecho em que você está atrás,** com diferença mediana de pelo menos 0,005 s, o mesmo corte do resumo. Um modelo de uma volta só não tem foco, e o coach fica calado durante a volta.
- **Trocar a referência ou o modelo** recomeça a contagem das 5 voltas.

### O que o coach diz

- **Durante a volta:** só nos trechos de foco, quando a diferença passa do limiar, e no máximo uma frase por trecho. Então são no máximo 3 frases por volta.
- **No fim da volta:** o resumo dos 3 trechos de maior diferença, igual ao do pedido 14.
- **Quando o foco muda:** uma linha no próprio feed, sem componente novo. Ela aparece como "FOCO NAS PROXIMAS VOLTAS: SETORES 32, 38 E 43" e, embaixo, de onde veio. Exemplo: "Maior diferenca mediana para a volta da IA nas ultimas 5 voltas validas da sessao".
- **No replay de uma volta gravada,** a linha de foco não entra na lista de eventos da volta; ela vem à parte, no campo `focus`.

### Ensaio nas suas voltas de 04/10 (antes e depois)

O ensaio (`tools/ensaio_coach.py`) roda um coach só, atravessando todos os arquivos do dia, como o app aberto. Cada modo roda duas vezes:

- **antes:** o coach do pedido 14, com o foco aberto a todos os microsetores;
- **agora:** com os 3 trechos de foco.

O "antes" reproduz as frases de trecho do ensaio do pedido 14, texto por texto: 94 e 79 frases, e na volta de 91,74 s os setores 2, 11 e 12. Dos resumos, um do modo `minha_melhor` sai da contagem (25 contra 26). O motivo: agora cada fala é ligada à volta pela amostra anterior a ela, porque o resumo sai na amostra que já cruzou a linha.

**"Nos 3 maiores da volta"** quer dizer que a frase caiu num dos 3 setores que o resumo daquela mesma volta lista.

| | volta_ia antes | volta_ia agora | minha_melhor antes | minha_melhor agora |
|---|---|---|---|---|
| frases de trecho, 32 voltas | 94 | 38 | 79 | 9 |
| frases por volta, 11 válidas (média, máx.) | 3,0, 3 | 1,2, 2 | 2,5, 3 | 0,2, 1 |
| nas válidas, frases nos 3 maiores da volta | 7 de 33 (21%) | 11 de 13 (85%) | 10 de 27 (37%) | 2 de 2 (100%) |
| microsetor mediano das frases (válidas) | 2 | 43 | 9 | 35 |
| frases nos microsetores 0 a 5 (válidas) | 27 | 1 | 6 | 0 |
| mais citados (válidas) | 2, 0, 1, 3 | 43 (7), 38 (4), 36, 2 | 8, 2, 43, 47 | 32, 38 |
| frases proibidas | 0 | 0 | 0 | 0 |

**Como o foco mudou ao longo do dia:**

- `volta_ia`: começou no modelo, com os setores 36, 38 e 43, e depois veio da sessão:
  - 26, 38 e 43;
  - 36, 38 e 43;
  - 2, 38 e 43.
- `minha_melhor`: começou no modelo, com os setores 32, 36 e 44, e depois veio da sessão:
  - 26, 43 e 44;
  - 36, 38 e 43;
  - 36, 38 e 39.

**Contra a sua melhor volta, o coach quase não fala.** O limiar é o mesmo nos dois modos (2× a sua oscilação), e a sua diferença para a sua própria melhor volta raramente passa dele nos trechos de foco. Antes, as frases passavam do limiar em trechos de pouca diferença, no começo da volta.

**Na volta de 91,74 s** (`2026-10-04_03-21-52_vhe_interlagos#0002`), o resumo lista os setores 32 (0,67 s), 38 (0,66 s) e 43 (0,48 s).

| | antes (pedido 14) | agora |
|---|---|---|
| `volta_ia` | setores 2, 11 e 12 (0,34, 0,07 e 0,07 s) | setores 38 (0,66 s) e 43 (0,48 s); foco 36, 38 e 43, do modelo |
| `minha_melhor` | setor 32 (0,64 s) | setor 32 (0,64 s); foco 32, 36 e 44, do modelo |

- **As frases foram todas para trechos de maior diferença da volta.**
- **O maior da volta contra a IA, o 32, ficou sem frase,** porque não estava no foco. O foco é escolhido antes da volta, pela sua mediana: nas suas 11 voltas do modelo, o 32 custa 0,24 s contra a IA, o 6º maior. O 36 custa 0,42 s, o 38 custa 0,43 s e o 43 custa 0,48 s. Nesta volta você perdeu 0,67 s no 32, bem acima do seu normal ali, e o coach só mostra isso no resumo.

### Limitação

- **O indicador de IA fica travado depois do Ctrl+C** até a sessão do jogo reiniciar. Assim, as suas voltas depois de um Ctrl+C não contam para o foco da sessão, e o foco volta a ser o do modelo até a sessão do jogo ser reiniciada e você somar 5 voltas válidas.

## 10. Atualizar o coach com um comando (pedido 15)

Depois de uma sessão nova, feche o app e rode, na pasta `backend`:

```
..\.venv\Scripts\python.exe tools\atualizar_coach.py
```

O comando faz, em ordem:

1. **Refaz o inventário novo** em `data/ml/origem/`, varrendo as duas pastas de gravações. A varredura só lê as gravações e leva cerca de 13 minutos. `--sem-varrer` pula este passo.
2. **Aplica as anotações versionadas de 04/10.** Elas ficam em `docs/experimentos/2026-10-04_rotulos_por_volta.csv`: 53 voltas, pela identidade do ML, feitas das suas anotações por parte e volta do jogo (`2026-10-04_sessao_rotulada_anotacoes.csv`). O comando para se o arquivo não bater com o inventário ou com as suas anotações. Uma sessão gravada depois, mesmo no dia 04/10, não herda as anotações.
3. **Rotula as sessões novas sem anotação** (equipamento `atual`):
   - antes de a IA ligar pela primeira vez na sessão do jogo, a volta é `humano`, pelo indicador;
   - a volta em que a IA liga é `misturada`;
   - depois disso, o indicador fica travado em `ia`, e quem decide é o detector pela linha da IA (`ai_detector.LIMITS`, com a referência das voltas limpas da IA de 04/10);
   - o que o detector não resolve, ou uma volta sem o campo do indicador, fica `desconhecida`.

   As voltas do equipamento anterior continuam como o indicador diz, e o detector só grava as colunas `*_detector` delas, como no pedido 13.
4. **Copia o modelo do repositório** para `data/reference_models/backup/vhe_interlagos.<data_hora>.antes-de-atualizar.json` e o treina de novo.
5. **Imprime o resumo:**
   - as duas referências;
   - as voltas de cada origem;
   - o limiar;
   - o foco inicial de cada modo.

   O resumo também fica em `data/ml/origem/atualizar_coach.json`.

**O que o comando não faz:**

- não reconstrói o store do ML;
- não grava o modelo do app instalado, e recusa um `--modelo` dentro da pasta dele.

**Quando ele para:** qualquer trava dos passos para o comando antes de treinar:

- os rótulos de 04/10 que não batem com o inventário;
- os microsetores e zonas do detector que não batem com a sessão rotulada;
- nenhuma volta limpa sua para treinar.

### Primeira rodada (04/10, depois do merge)

- **Saída:** código 0, em cerca de 16 minutos, quase tudo na varredura de 132 sessões.
- **Sessão de 04/10:** 53 voltas reaplicadas pelo arquivo versionado, 32 `humano`, 17 `ia` e 4 `misturada`, os mesmos números de antes da varredura. Nenhuma sessão nova sem anotação.
- **Referências:** as mesmas do pedido 14.
  - `volta_ia`: 84,828 s, `2026-10-04_03-42-10_vhe_interlagos#0013`.
  - `minha_melhor`: 89,389 s, `2026-10-04_02-24-04_vhe_interlagos#0018`.
- **Voltas no modelo:** 11 suas e 13 da IA, todas limpas.
- **Limiar:** mediana de 0,157 s (de 0,06 a 0,62 s), com 18 microsetores no mínimo de 0,06 s.
- **Foco inicial:**
  - `volta_ia`: setores 36, 38 e 43;
  - `minha_melhor`: setores 32, 36 e 44.
- **Modelo do repositório:** backup em `backup/vhe_interlagos.2026-10-04_17-19-56.antes-de-atualizar.json`. O modelo novo só difere dele na data de treino (`built_at`).
- **O que não mudou:** o modelo do app instalado (`9d08d705…`) e o store do ML (`data/ml/lap_inventory.parquet` e `laps_grid.parquet`).
