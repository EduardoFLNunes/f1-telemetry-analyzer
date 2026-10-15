# Relatório do pedido 30: complemento do pedido 29 (as telas do protótipo A)

- **Pedido:** `docs/prompts/2026-10-14_30_complemento-prototipo-a.md`
- **Branch:** `etapa/redesenho-base`, a mesma do pedido 29, com merge em `develop`. Nada foi enviado ao remoto.
- **Commits e merge:**
  - `9c5db42f` docs: pedido 30 (complemento do pedido 29: as telas do protótipo A agora), arquivo do Cowork
  - `30985f8e` Rotas de leitura para Sessões, Volta e Evolução: relatório de evolução, linhas de uma volta do store v2, referências do coach e geometria oficial, só lendo os arquivos do repositório configurado (seção 5)
  - `a3d1e694` Medidas da tela Volta no método do relatório de evolução (porte de `evolution.py` e `microsectors.py`), com as curvas do `sessao_*.json` encaixadas na grade, e o script que confere a tela contra o protótipo A e o `por_volta` oficial (seções 3 e 6)
  - `9b4926f2` Telas Volta e Evolução do protótipo A (seção 3)
  - `f3356b10` Tela Sessões do protótipo A (seção 3); atalho "Última volta" para a tela Volta e o nome completo do produto na navegação
  - `c21621d9` Leituras das telas Sessões, Volta e Evolução tentam de novo enquanto o backend não responde, com o erro em português
  - `30b4808d` Sessões: a tendência da mediana por sessão no texto do gráfico
  - `ee3721e4` Tabelas por curva de Volta e Evolução com o nome da curva em destaque
  - `7dde6cdd` Merge etapa/redesenho-base (pedido 30: as telas Sessões, Volta e Evolução do protótipo A, com as rotas de leitura)
  - o commit deste relatório, com o handoff e o inventário: "Relatório do pedido 30: as telas do protótipo A"; `develop` avança até ele
- **Arquivos de handoff** (sha256, 12 primeiros dígitos):
  - `docs/handoff/2026-10-14_30_complemento-prototipo-a_relatorio.md` (este)
  - a seção "Complemento: pedido 30" em `docs/handoff/2026-10-14_29_redesenho-base_relatorio.md`, com o mesmo conteúdo
  - `docs/handoff/2026-10-14_30_complemento-prototipo-a.patch`: de `9c5db42f` até `ee3721e4`, só `backend` e `frontend` (`06530806bdec`)
  - `docs/handoff/2026-10-14_30_complemento-prototipo-a_testes.txt`: `tsc --noEmit`, `vitest run`, o build e o `pytest` do backend (`7ccd11609f52`)
  - `docs/handoff/2026-10-14_30_complemento-prototipo-a_conferencia.json`: a conferência da volta 8 contra a IA, curva a curva e microssetor a microssetor (`bb6b64cdafc1`)
  - `docs/handoff/2026-10-14_30_complemento-prototipo-a_lado-a-lado_*`: 5 telas em 1920×1080 e 2560×1440 (10 arquivos; lista em "Capturas lado a lado")

## Em resumo

1. **As telas Sessões, Volta e Evolução seguem o protótipo A** (opção A, escura e densa), com as cores, as fontes e o vidro do pedido 29. Todos os números vêm das rotas do app; sem dado, a tela diz "Sem dados" e por quê.
2. **Pista e Análise deixaram de ser telas.** O que sobrou delas foi para onde a seção 6 do inventário manda; as frases do coach ficaram embaixo do replay da Volta e marcadas no mapa.
3. **Cinco rotas novas, só de leitura**, com 7 testes. Nenhuma calcula nada; nenhuma tela precisou da projeção do runtime.
4. **A conferência bate.** Na volta 8 de 05/10 (20:33) contra a volta da IA:
   - o tempo (1:30,629) e a diferença (+5,800 s) são iguais no app, no protótipo e no relatório;
   - a perda por curva bate com o `por_volta` oficial (diferença 0) e com o protótipo (no máximo 0,001 s);
   - a diferença por microssetor bate com o protótipo (no máximo 0,0005 s, arredondamento);
   - a diferença no modo por curva bate com o protótipo (no máximo 0,002 s, porque o protótipo usa uma grade de 8 m).
5. **Capturas lado a lado** (app à esquerda, protótipo A à direita) de Sessões, Volta, Evolução, Coleta de dados e Sistema, em 1920×1080 e 2560×1440, da janela real do Electron, isolada.
6. **Testes:** o `tsc` passa; o `vitest` passa com **173 testes em 14 arquivos** (eram 161; entraram 12); o `pytest` do backend dá **743 passando e 1 falha**. A falha é `backend/test_ws_client.py`, um script antigo solto na raiz do backend (de `5eb00c71`, sem mudança neste pedido): ele é `async` e precisa de um plugin que não está instalado. As 7 rotas novas passam.
7. **Achados fora do pedido:** o coach conta os microssetores a partir de 0, a rota das frases do coach só procura gravações em duas pastas, e o hero e o relatório diferem em 1 ms nos tempos das referências.

## O que mudou, por parte

### Rotas novas (seção 5)

Ficam em `backend/routers/leitura.py`, com a leitura em `backend/core/leitura/arquivos.py`. Todas leem a pasta do repositório configurada na Coleta de dados (pedido 28), por `main.app_config.coach_root()`, e rodam fora do laço do servidor (`asyncio.to_thread`).

| Rota | O que lê | O que devolve |
|---|---|---|
| `GET /api/evolucao/resumo` | `data/ml/evolucao/resumo.json` | o JSON como está, e a lista dos `sessao_*.json` |
| `GET /api/evolucao/sessoes/{sessao}` | `data/ml/evolucao/sessao_{sessao}.json` | o JSON como está; o nome é validado (`AAAA-MM-DD` ou `AAAA-MM-DD-N`) |
| `GET /api/coach/referencias` | `data/reference_models/vhe_interlagos.json` | qual volta é a `volta_ia` e qual é a `minha_melhor`, com tempo e carro |
| `GET /api/store/voltas/{lap_id}` | `data/ml/laps_grid_v2.parquet`, filtrado pela volta | as linhas da volta na ordem da grade: `elapsed_s`, velocidade, acelerador, freio e `lateral_m`, mais o `replayLapId` |
| `GET /api/geometria/oficial` | a geometria oficial exportada e o cache da pista | a linha central, as normais, as bordas dos 60 microssetores e, quando o `geometry_id` bate, a altitude e as larguras |

- **Testes** (`backend/tests/test_leitura.py`, 7): os arquivos voltam como estão; sem arquivo ou com nome inválido, a rota diz por quê; as referências do modelo do coach; a volta do store na ordem da grade, sem conta; volta desconhecida ou id inválido; a geometria sem o cache fica sem relevo; e a volta da conferência nos arquivos reais (2.167 pontos, 90,6288 s).
- **O que já existia continua:** as camadas da pista vêm de `/api/track/geometry`, as gravações de `/api/sessions` e as frases do coach de `/api/analysis/coach/lap/{id}`.
- **Projeção:** nenhuma tela precisou da projeção do runtime. A posição do carro e do fantasma é a linha central oficial mais o `lateral_m` do store v2. As frases do coach trazem o `s` do próprio coach, que projeta na geometria oficial desde o ADR 0013.

### Sessões

- **O hero** do pedido 29, sem mudança, a não ser o atalho "Última volta", que agora abre `#/volta/ultima`.
- **As sessões do relatório de evolução,** a mais nova em cima. Cada uma tem os números da sessão (voltas, melhor, mediana, desvio, mediana contra a IA, curvas com diferença consistente), **uma marca por volta válida** numa faixa de tempo, com a linha da IA, e o botão "Ver a melhor volta".
- **Mediana e melhor volta por sessão,** com a tendência da mediana e o critério do ADR 0015 (hoje: ainda variando, amplitude 0,643 s, limite 0,5 s).
- **As gravações fora do relatório:** o que `/api/sessions` tem e os JSONs de sessão ainda não. A conferência da Coleta continua dando as voltas válidas e a melhor volta, como no pedido 29.

### Volta (opção A)

- **A barra de contexto:** sessão, volta, tempo em M:SS,mmm e a diferença para a referência.
- **A escolha:** os chips de sessão (abrem a melhor volta da sessão), os de volta e os de referência (volta da IA ou sua melhor). O endereço guarda a volta (`#/volta/<lapId>`); `#/volta/ultima` abre a última volta do relatório; sem volta, abre a melhor da sessão mais recente.
- **A volta com fantasma** (`frontend/src/volta/Fantasma.tsx`):
  - câmera de 80, 150 ou 400 m (a roda do mouse aproxima entre 40 e 1.200 m), com a opção de girar com o carro;
  - a pista são as camadas do cache (`drawTrackSurface`: asfalto, pintura classificada e zebras), no sentido anti-horário;
  - o traçado desde o início da volta, colorido pelo pedal (freio a partir de 0,15, acelerador a partir de 0,9, o resto parcial);
  - o fantasma da referência posicionado pelo tempo, por curva (recomeça junto no início de cada curva) ou na volta inteira; fora da tela, uma seta com a distância;
  - o relevo no canto superior direito, com a altitude e a inclinação no ponto do carro, e a pista inteira no inferior direito;
  - a leitura dos dois carros (pedal, velocidade, tempo) e a diferença no centro;
  - o replay: tocar, 0,5× a 4×, a barra de posição e a leitura no cursor;
  - **o rádio nesta volta:** as frases do coach, no ponto em que saíram; clicar leva o cursor até lá, e a última frase já dita fica destacada durante o replay.
- **O mapa dos 60 microssetores,** colorido pela diferença, com o nome das curvas (clicar escolhe a curva) e as frases do coach marcadas.
- **A tabela das 14 curvas:** perda, mediana da sessão (só contra a volta da IA, que é a referência do relatório), início da freada, velocidade mínima e posição no ápice, com a soma.
- **Os traços:** diferença acumulada por distância em metros, velocidade, acelerador e freio, com as faixas das curvas e um cursor compartilhado com o mapa, o fantasma e o replay.
- **As medidas** repetem o método do relatório de evolução (`frontend/src/volta/medidas.ts`, porte de `evolution.py` e `microsectors.py`, com 8 testes). As curvas do `sessao_*.json` vêm arredondadas a 0,1 m e são encaixadas na grade antes da conta, senão a C01 a C09 mediam o ponto vizinho.

### Evolução

- Mediana e melhor volta por sessão, com o critério do ADR 0015.
- Perda por curva entre sessões: ponto na perda mediana para a IA, traço na faixa de 90% de confiança, ponto vazio sem diferença consistente.
- Técnica de pilotagem por curva (bloco `tecnica`), com a escolha da sessão: uso da aderência, freio e volante juntos e freada emendada, cada um com o número da IA ao lado.

### O resto

- **A navegação** mostra o nome do produto inteiro: "Sistema de Telemetria e Otimização de Trajetórias".
- **Trocar de tela começa do topo;** trocar de volta na mesma tela mantém a rolagem, como no protótipo.
- **As leituras tentam de novo** a cada 3 s enquanto o backend não responde. Achei isso nas capturas: o Electron abre a janela antes de o backend subir, e a tela ficava parada em "Network Error". Os erros agora saem em português.
- **Coleta de dados, Ao vivo e Sistema** ficaram como no pedido 29.
- **`Dashboard.tsx` e `AnalysisPage.tsx`** saíram das rotas, mas continuam no código, junto com os componentes que só eles usavam. Pela seção 6 do inventário, saem no pedido de limpeza.
- **`docs/dashboard_inventario.md`:** no fim da seção 7, "O que o pedido 30 entregou".

## Conferência contra o protótipo (seção 6)

**A volta:** `2026-10-05_20-33-47_vhe_interlagos#0008` (volta 8 de 05/10, 20:33) contra a volta da IA, `2026-10-04_03-42-10_vhe_interlagos#0013`. O script `frontend/scripts/conferencia_prototipo.ts` lê as rotas do app (backend isolado), os dados embutidos no protótipo e o `por_volta` oficial de `sessao_2026-10-05-2.json`. A saída inteira está em `…_conferencia.json`.

| Número | App | Protótipo A | Relatório oficial | Maior diferença |
|---|---|---|---|---|
| Tempo da volta | 1:30,629 (90,6288 s) | 1:30,629 | 1:30,629 | 0 |
| Tempo da volta da IA | 1:24,829 (84,8292 s) | 1:24,829 | 1:24,829 | 0 |
| Diferença da volta | +5,800 s | +5,800 s | +5,800 s | 0 |
| Soma das 14 curvas | +5,800 s | +5,800 s | | 0 |
| Perda por curva (14) | | | | 0,001 s contra o protótipo; 0 contra o oficial |
| Início da freada | | | | 0 m contra o oficial |
| Velocidade mínima e posição no ápice | | | | 0,001 contra o oficial |
| Diferença por microssetor (60) | | | | 0,0005 s contra o protótipo |
| Diferença no modo por curva, no fim de cada curva | | | | 0,002 s contra o protótipo |

| Curva | Perda: app | Protótipo | `por_volta` oficial | Modo por curva, no fim da curva: app | Protótipo |
|---|---|---|---|---|---|
| C01 | +1,221 | +1,221 | +1,221 | +1,029 | +1,029 |
| C02 | +0,091 | +0,091 | +0,091 | +0,091 | +0,090 |
| C03 | +0,475 | +0,475 | +0,475 | +0,475 | +0,475 |
| C04 | +0,492 | +0,492 | +0,492 | +0,492 | +0,493 |
| C05 | +0,348 | +0,348 | +0,348 | +0,348 | +0,347 |
| C06 | +0,328 | +0,328 | +0,328 | +0,328 | +0,328 |
| C07 | +0,378 | +0,378 | +0,378 | +0,378 | +0,379 |
| C08 | −0,098 | −0,098 | −0,098 | −0,098 | −0,099 |
| C09 | +0,348 | +0,347 | +0,348 | +0,347 | +0,348 |
| C10 | +0,895 | +0,895 | +0,895 | +0,895 | +0,893 |
| C11 | +0,525 | +0,525 | +0,525 | +0,525 | +0,526 |
| C12 | +0,237 | +0,237 | +0,237 | +0,237 | +0,237 |
| C13 | +0,146 | +0,146 | +0,146 | +0,146 | +0,147 |
| C14 | +0,415 | +0,415 | +0,415 | +0,415 | +0,415 |

**As diferenças e as causas:**
- **Perda da C09, 0,001 s:** o protótipo guarda 3 casas; o valor do app é 0,3475, que arredonda para 0,348, como o oficial.
- **Microssetores, até 0,0005 s:** o mesmo arredondamento em 3 casas no protótipo. Os maiores são o 37 (+0,577 s), o 4 (+0,369 s) e o 39 (+0,342 s); o de maior ganho é o 34 (−0,142 s).
- **Modo por curva, até 0,002 s:** o protótipo guarda as voltas numa grade de 8 m e interpola; o app usa a grade do store, de 2 m. Pelo mesmo motivo, a leitura da velocidade no cursor pode diferir em 1 km/h (nos 300 m: 112 contra 113 km/h da IA).
- **Por que a C01 dá +1,029 no modo por curva e +1,221 na perda:** a C01 começa antes da linha (4.112 m) e termina depois dela (346 m). No modo por curva, o fantasma recomeça na linha, como no protótipo; a perda do relatório conta o trecho inteiro.

## Capturas lado a lado

App à esquerda (o build do repositório na janela do Electron), protótipo A à direita, cada um com a página inteira. A Volta está com o cursor nos 300 m (ápice da C01), igual nos dois.

- **Sessões:** `docs/handoff/2026-10-14_30_complemento-prototipo-a_lado-a-lado_1_sessoes_1920x1080.png` (`e37712d7118d`) e `…_1_sessoes_2560x1440.png` (`31cbe5499ed7`)
- **Volta, com o cursor nos 300 m:** `docs/handoff/2026-10-14_30_complemento-prototipo-a_lado-a-lado_2_volta_1920x1080.png` (`358fc6350c5a`) e `…_2_volta_2560x1440.png` (`b6e52c4fb759`)
- **Evolução:** `docs/handoff/2026-10-14_30_complemento-prototipo-a_lado-a-lado_3_evolucao_1920x1080.png` (`10739f922d4b`) e `…_3_evolucao_2560x1440.png` (`c4e8ea2e6e36`)
- **Coleta de dados (no protótipo, "Antes de pilotar"):** `docs/handoff/2026-10-14_30_complemento-prototipo-a_lado-a-lado_4_coleta_1920x1080.png` (`76440ad11756`) e `…_4_coleta_2560x1440.png` (`ca83e9c9fdf8`)
- **Sistema:** `docs/handoff/2026-10-14_30_complemento-prototipo-a_lado-a-lado_5_sistema_1920x1080.png` (`9dd00582a4a2`) e `…_5_sistema_2560x1440.png` (`ae9af1acb9f4`)

**Como foram tiradas:** o Electron do repositório com o front construído (`AT_DESKTOP_MODE=production`), comandado pelo DevTools Protocol, com viewport emulado. O perfil (`AT_DESKTOP_USER_DATA_DIR`), o backend (porta 8011, raiz no scratchpad) e as gravações (links físicos) ficaram no scratchpad, como no pedido 29. O protótipo abriu na mesma janela, por `file://`, na opção A. Não mexi no app instalado (porta 8000) nem nos arquivos do jogo.

## O que ficou diferente do protótipo, e por quê

1. **As cores** são as do pedido 29, como o pedido 30 manda: você em branco, a referência em cinza tracejado, a perda em laranja, o ganho em azul e o vermelho do produto nos chips escolhidos. No protótipo, você é laranja.
2. **Cinco sessões em vez de três:** o protótipo tem os dados embutidos até 05/10 (2); o app lê o relatório de hoje, que já tem 09/10 e 10/10. Pelo mesmo motivo, o critério do ADR 0015 dá amplitude 0,643 s no app e 2,062 s no protótipo.
3. **Sessões começa pelo hero,** como o pedido manda, e não pela fileira de cartões do protótipo. O que os cartões tinham e o hero não tem (a tendência da mediana e o critério do ADR 0015) está no texto do gráfico de tendência.
4. **Sem o chip "Outra volta…":** no protótipo ele aparece desligado ("No app: qualquer volta gravada"). O pedido limita a referência à volta da IA e à sua melhor, e um botão que não faz nada não entra.
5. **O rádio nesta volta e as marcas no mapa** não existem no protótipo. Entraram pela seção 6 do inventário ("as frases ficam no replay da Volta, marcadas no mapa").
6. **Os traços de acelerador e freio parecem mais densos:** o app desenha a grade de 2 m do store; o protótipo, a de 8 m.
7. **A tabela das curvas** pinta a perda de laranja; o protótipo deixa a perda na cor do texto. É a regra de cor de dado do pedido 29.
8. **Coleta de dados e Sistema** são as do pedido 28 e do pedido 29, como o pedido 30 manda. O protótipo tem "Antes de pilotar" e uma lista de cartões no lugar delas; as capturas mostram os dois lado a lado mesmo assim.
9. **O sentido e a projeção** são os mesmos do protótipo: `base(x, z) = [z, −x]`, uma rotação, no anti-horário. Os desenhos da pista, do relevo e do minimapa conferem nas capturas.

## Achados fora do pedido

1. **O coach conta os microssetores a partir de 0.** O índice vem de `int(progresso × 60)` (`driving_coach.py`). O resumo de fim da volta 8 fala em "setor 36 (0.58s), setor 3 (0.37s) e setor 38 (0.34s)", e no mapa da tela Volta (que conta de 1, como o relatório) esses são os microssetores 37, 4 e 39, com os mesmos números. Na tela Volta a frase não mostra o número, então não há conflito ali; no rádio da tela Ao vivo (pedido 29), "microssetor 2" é o terceiro de 60. Não mexi no coach. **Decisão sua:** somar 1 na escrita do rádio, ou deixar.
2. **A rota das frases do coach só procura gravações em duas pastas:** `data/recordings` do repositório e da raiz do backend (`AssistedAnalysisService`), e não na pasta de gravação configurada (`TELEMETRY_RECORDING_DIR`). Achei nas capturas: o backend do Electron de teste tinha outra raiz e respondia 404. Resolvi no teste com uma junção no scratchpad, e a tela agora diz "a gravação desta volta não está na pasta de gravações do backend" em vez da frase em inglês. Se o app instalado gravar fora da raiz dele, o rádio da Volta vai dizer isso. Não mexi (seria backend fora das rotas de leitura).
3. **O hero e o relatório diferem em 1 ms nos tempos das referências.** O hero (pedido 29) lê o modelo do coach: 1:29,389 e 1:24,828. O relatório e o store dão 89,3898 e 84,8292 s, que arredondam para 1:29,390 e 1:24,829. A diferença vem das fontes, não da tela. **Decisão sua:** o hero passa a usar o store, para os números baterem na mesma tela?
4. **O achado 2 do pedido 29 ficou resolvido na Evolução:** ela agora mostra os números do relatório de evolução, e não mais os tempos do gravador.

## O que não mudou

- Nenhum modelo, critério, store, regra do coach ou rota de cálculo. No backend, só entraram as rotas de leitura e o teste delas (`git diff --stat 9c5db42f HEAD -- backend`: 5 arquivos, todos de leitura, mais duas linhas em `main.py` para registrar o router).
- Não instalei nem atualizei pacotes. Não gerei instalador. Não mexi no app instalado nem nos arquivos do jogo.
- Nada de marca alheia: as fontes são as do pedido 29 (OFL), e a pista é o desenho do cache.
- Nada foi enviado ao remoto.

## O que falta e o que precisa de decisão

- **Nada do pedido 30 ficou para trás.** O merge está em `develop`; nada foi enviado ao remoto.
- **Decisões suas:**
  - **o achado 1:** o rádio passa a somar 1 no número do microssetor, para bater com o mapa e o relatório?
  - **o achado 3:** o hero passa a usar os tempos do store, para bater com a tela Volta e o relatório?
  - **o achado 2:** a rota das frases do coach deveria procurar também na pasta de gravação configurada (é backend; seria um pedido próprio).
- **Para o pedido de limpeza:** `Dashboard.tsx`, `AnalysisPage.tsx` e os componentes que só eles usavam.
- **O canvas de design** do pedido 29 não foi atualizado com as telas novas; as capturas lado a lado fazem esse papel aqui.
- **O pedido 31** (realidade aumentada) espera o seu "Execute".

## Correção depois da entrega (15/10, pedida no chat)

- **O problema:** na tela Volta, a roda do mouse sobre a visão com fantasma mudava a aproximação e rolava a página ao mesmo tempo.
- **A causa:** o `onWheel` do React é registrado como passivo, então o `preventDefault` dele não segurava a rolagem.
- **A correção** (`2c3f9c12`): um ouvinte nativo de `wheel` com `passive: false` na visão.
  - **Dentro da visão:** a roda só aproxima e afasta.
  - **Fora dela:** a página rola como antes.
- **Como foi conferido:** na janela do Electron isolada, a roda dentro da visão cancelou o evento, a rolagem ficou em 200 px e a aproximação foi de 150 para 172 m. Fora da visão, o evento passou. `tsc`, `vitest` (173 testes) e o build passam.
