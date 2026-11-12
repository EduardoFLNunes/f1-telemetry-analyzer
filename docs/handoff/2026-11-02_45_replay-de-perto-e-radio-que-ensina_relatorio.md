# Relatório parcial do pedido 45: o replay de perto, as voltas nos boxes e o rádio que diz onde e por quê

- **Pedido:** `docs/prompts/2026-11-02_45_replay-de-perto-e-radio-que-ensina.md`, com a sua decisão de 04/11 no item B.1.
- **Situação (12/11, 14:26):** **as suas quatro decisões estão aplicadas; você decidiu testar no jogo antes do merge.** Os registros não mostram o teste do rádio depois da correção da voz, e as anotações não vieram (seção "12/11"). Sem merge em `develop`. O envio é você quem faz: os comandos estão no fim.
- **Branch:** `etapa/replay-e-radio-que-ensina`, a partir de `develop` em `bd04b93e`.
- **Commits:**
  - em `develop`: `bd04b93e` Pedido 45: texto do pedido, atualizacao de 04/11 do pedido 42 e backlog;
  - `29dec5ba` Parte B: um numero so para cada volta, a primeira volta com as medidas e o erro do WebSocket;
  - `460acdc9` Parte C: os cortes novos, antes de rodar as sessoes;
  - `e2ebc931` Parte C e rotas da Parte E: o radio diz onde e por que; as voltas da sessao ficam guardadas;
  - `7c9d2d5e` Partes C.4, D e E: a camera de perto, os boxes, o botao e a diferenca para a melhor;
  - `3fc07fa0` Parte H e E.3: documentacao, ADR 0027, versao 0.7.0 e as voltas que nao comecam na linha;
  - `6c87e3ed` Relatorio parcial do pedido 45 (a primeira parada);
  - `9c1f9349` B.1: a regra dos boxes do coach so vale no pit lane (sua decisao de 04/11);
  - `d6594970` B.2: a volta com o carro movido no meio nao repete o numero na lista;
  - `0907aec8` Pedido 45: o relatorio da parada da Parte G, as previas e a documentacao corrigida (enviado e conferido no remoto);
  - o commit da nota de 06/11: "Pedido 45: o aviso de teste chegou, mas o jogo nao abriu desde 01/11".
- **Arquivos de handoff** (`docs/handoff/2026-11-02_45_replay-de-perto-e-radio-que-ensina…`):
  - `_relatorio.md` (este);
  - `_radio_antes_e_depois.json` (o C.6: as 4 sessões, fala a fala, com a voz de verdade);
  - `_duracao_das_falas.json` (quanto dura cada variante);
  - `_incompletas.py` e `_incompletas.json` (o B.1, rodado **antes** da regra nova: com ela, as duas colunas do script ficam iguais);
  - `_previa.py`, `_previa_camera.png` (a folha inteira), `_previa_camera_c01.png`, `_c06.png`, `_c12.png` e `_previa_lista_01-11.jpg`;
  - `_abrir_no_app_v7_c01.jpg` e `_abrir_no_app_v7_inteira.jpg`;
  - `_conferir_lua.txt` e `_testes.txt`;
  - `_limite_8s.json` (12/11: o resumo com 7,7 s e com 8,0 s, nas 4 sessões, fala a fala).

## 06/11: o aviso de teste chegou, mas o teste ainda não aconteceu

- **O envio da branch está conferido:** `git ls-remote` dá `0907aec8d5e93c089f5e836275c75b11b072bcea` no remoto, igual ao local.
- **Em 06/11, às 23:27, chegou o aviso "Testei no jogo",** sem a tabela preenchida. Antes de ler qualquer resultado, conferi se o jogo abriu (23:28):

| sinal | o que tem | o que teria depois do teste |
|---|---|---|
| `apps\lua\radio_engenheiro\manifest.ini` na pasta do jogo | `VERSION = 0.4.2`, gravado em 01/11 às 16:02 | `VERSION = 0.5.0`, gravado pelo `instalar.ps1` |
| logs do jogo (`Documents\Assetto Corsa\logs`) | o último é de 01/11 às 20:22 (`custom_shaders_patch.log`, `py_log.txt`) | data de 05/11 ou 06/11 |
| última gravação em `data/recordings` | `2026-11-01_21-07-46_spa` | uma sessão de Interlagos de 05/11 ou 06/11 |
| última gravação do app instalado | `2026-10-18_12-18-08_vhe_interlagos` | — |

- **Ou seja: o app do jogo 0.5.0 não foi instalado, e o jogo não abriu desde 01/11.** Não escrevi nenhum resultado de jogo, não medi o FPS, não li log do CSP e **não fiz o merge em `develop`**, porque tudo isso depende do teste.
- **Para seguir:** os passos da Parte G continuam valendo, a partir do passo 1. O passo 2 (o `instalar.ps1`) é o que deixa a pasta do jogo na 0.5.0. Depois, avise de novo, com a tabela se puder.

## 07/11: o primeiro teste no jogo, com o app do jogo errado

**A pasta mudou de branch no meio do teste:**

- 10:46: abri o app do Windows pelo repositório, nesta branch (backend `radio-que-ensina`, porta 8000).
- 11:22:49: a sessão do pedido 46 trocou a pasta para `develop`. Às 14:21, ela fez o merge do pedido 46 em `develop` (`a780c9d1` no fim).
- Depois disso, o `instalar.ps1` copiou o app do jogo de `develop`: a pasta do jogo ficou com `VERSION = 0.4.2`, com a data 11:22:49 (a do checkout).
- O backend já estava carregado desta branch, e o rádio falou com as palavras novas. **O app do jogo 0.5.0 não foi testado:** a janela nos boxes, a lista, a grade, a roda do mouse e o botão "Abrir no app" não existem na 0.4.2. O log do backend não tem nenhum pedido às rotas novas vindo do jogo.
- Às 19:06, com a sua autorização, voltei a pasta para esta branch, para repetir o teste.

**O que o teste mostrou** (sessão `2026-11-07_18-46-00_vhe_interlagos`; às 19:03 o jogo ainda estava aberto):

| id | hora | origem | volta | fala | s | limite |
|---|---|---|---|---|---|---|
| 1 | 18:47 | teste | – | "Teste do rádio. Se você me ouve, está tudo certo." | 4,09 | – |
| 2 | 18:50 | coach | 2 | "Curva 11, esquerda: 6 décimos atrás da IA. Mínima 15 quilômetros por hora abaixo da IA." | 6,50 | 7,3 |
| 3 | 18:51 | resumo | 2 | "Volta com rodada: 1 minuto e 35,1 segundos, 10,3 segundos atrás da IA." | 6,37 | 7,7 |
| 4 | 18:52 | resumo | 3 | "Melhor volta. Curva 1: 1,0 segundo, freou 104 metros antes da IA." | 6,13 | 7,7 |
| 5 | 18:54 | resumo | 4 | "Melhor volta, 1,8 segundo mais rápida. Curva 1: 7 décimos." | 5,74 | 7,7 |
| 6 | 18:55 | curva | 4 | "Curva 1: 7 décimos, freou 46 metros antes da IA." | 4,33 | 7,3 |
| 7 | 18:55 | resumo | 5 | "Volta com rodada: 1 minuto e 45,5 segundos, 17,0 segundos atrás da sua melhor." | 7,43 | 7,7 |
| 8 | 18:57 | resumo | 6 | "Melhor volta, 3 décimos mais rápida. Curva 1: 6 décimos, perdeu 2 décimos na freada." | 6,95 | 7,7 |
| 9 | 18:58 | analise | 6 | "Voltas 3, 4 e 6. Curva 1: perde 7 décimos por volta. Freou 46 metros antes da IA." | 8,29 | 8,8 |
| 10 | 19:00 | coach | 7 | "Curva 11, esquerda: 5 décimos atrás da IA. Mínima 23 quilômetros por hora abaixo da IA." | 6,89 | 7,3 |

- **As voltas:**
  - 1: incompleta, 3:17,442 (saída dos boxes);
  - 2: com rodada, 1:35,129;
  - 3: válida, 1:30,362;
  - 4: válida, 1:28,544;
  - 5: com rodada, 1:45,547;
  - 6: válida, 1:28,246 (a melhor).

  A volta 7 estava em curso.
- **As falas:** nenhuma passou do limite. A causa entrou no resumo em 2 das 3 voltas válidas; na volta 4, saiu numa mensagem própria (id 6).
- **Os replays:** o app do jogo 0.4.2 pediu 16 replays (`/api/radio/replay/<id>`), todos com resposta 200.
- **O erro "attached to a different loop":** 0 no log do backend de hoje (31 mil linhas). Com o código antigo, foram 70 em 24/10 e 63 em 01/11. É a primeira prova no jogo de que a correção da B.3 funciona.
- **Depois da primeira leitura** (o jogo ficou aberto até cerca de 19:11), o rádio falou mais 5 vezes, todas dentro do limite:
  - 11 (coach, volta 7): "Curva 12, esquerda: 8 décimos atrás da IA. Freou 32 metros antes da IA." (6,11 s);
  - 12 (coach, volta 7): "Curva 12: 1,3 segundo atrás da IA. Mínima 57 quilômetros por hora abaixo da IA." (6,84 s);
  - 13 (resumo, volta 8): "11,9 segundos atrás da sua melhor. Curva 1: 3,9 segundos." (6,03 s);
  - 14 (curva, volta 8): "Curva 1: 3,9 segundos, freou 72 metros depois da IA." (5,01 s);
  - 15 (coach, volta 9): "Curva 11, esquerda: 5 décimos atrás da IA." (3,52 s).
- **As idas aos boxes:** a gravação tem 10 voltas. A 7 levou 5:42,195, com a parada; a 10 terminou nos boxes (velocidade máxima de 53 km/h). A volta 7 ficou sem resumo, como manda a regra do pit lane. Com a 0.4.2, a janela dos boxes não existia.
- **O log do CSP** (`custom_shaders_patch.log`; o `log.txt` só tem avisos de ícone):
  - nenhum erro de Lua;
  - a voz tocou 15 vezes, e o backend entregou os áudios de 1 a 15 (o 1, duas vezes);
  - 3 "Slow script", o pior com 328 ms, no desenho do rádio, logo antes da primeira voz;
  - 2 "App radio_engenheiro is not allowed to load", no começo, seguidos de uma recarga normal;
  - no fim, "o backend não respondeu", quando o app do Windows foi fechado, às 19:11.
- **O FPS:** a média foi de 106,2 fps com o replay ligado (126 medidas de 10 s; mediana 107,5, a pior 69,2). Com o replay desligado, há só 2 medidas (97,4 de média), no começo e antes de entrar na pista. **Não dá para comparar:** o replay não foi desligado durante as voltas. E, na 0.4.2, o replay não tem a câmera de perto.
- **As suas anotações** (a tabela da Parte G) não chegaram.

## 07/11: o app do Windows 0.7.0 instalado, a seu pedido

- Às 19:07, você pediu para atualizar o app instalado para esta versão. Perguntei qual dos dois e você escolheu o app do Windows. Isso abre uma exceção às regras "Não gere instalador" e "Não mexa no app instalado".
- `npm run dist:win`, na pasta `desktop`: gerou `versoes/0.7.0-radio-que-ensina/Automobilista-Telemetria-Setup-0.7.0-radio-que-ensina.exe` (229 MB), do commit `0bbc0c2`, com a árvore limpa (`build-info.json`: `dirty: false`). Nada foi enviado: o `publicar` só copia para `versoes/`.
- Instalei sem perguntas (`/S`), por cima da 0.5.0, com o jogo e o app fechados. O instalador saiu com o código 0. O executável instalado é a 0.7.0.0 e o desinstalador, a `0.7.0-radio-que-ensina`.
- As 100 gravações do app instalado continuam em `%APPDATA%\Automobilista Telemetria\data\recordings`.
- O `versoes/LEIA-ME.md` foi refeito (`npm run versoes`) e agora diz que a instalada é a mais atual.
- **Não abri o app instalado:** a versão foi conferida pelo executável e pelo desinstalador, não pela tela.
- **O app do jogo continua na 0.4.2.** O `instalar.ps1` desta branch (que já está na pasta) é o que leva para a 0.5.0.

## 07/11, 19:52 a 20:16: o segundo teste, com o app instalado 0.7.0 e o app do jogo 0.5.0

- **O teste aconteceu:**
  - a pasta do jogo tem `VERSION = 0.5.0` (você rodou o `instalar.ps1` desta branch);
  - às 19:50, conferi que o app aberto era o instalado 0.7.0 (backend `radio-que-ensina`, porta 8000);
  - a gravação é `2026-11-07_19-52-33_vhe_interlagos`, no app instalado. Ela fica lá: o pedido proíbe copiar gravações para o repositório;
  - o jogo foi aberto às 19:52 e de novo às 20:05. **O log do CSP das 19:52 se perdeu** quando o jogo reabriu. O das 20:05 foi lido e guardado fora do repositório.
- **Defeito encontrado: o app instalado não tinha voz.** O log dele mostra "Radio sem voz" em cada fala: o `voz.ps1` não estava em `_internal\core\radio`. O build (`backend/packaging/build_backend.ps1`) nunca incluiu esse arquivo. Pelo script, o defeito vem de antes deste pedido e também valia para a 0.5.0. O rádio entregou 5 mensagens sem áudio, e o app do jogo registrou "voz: falhou: a mensagem N veio sem áudio".
- **O que funcionou, pelo log do CSP das 20:05 e pelo log do backend:**
  - nenhum erro de Lua;
  - a janela do replay **abriu sozinha nas 3 entradas nos boxes** ("nos boxes: a janela abre") e **voltou como estava nas 2 saídas**;
  - a lista das voltas foi pedida 49 vezes (`/api/radio/voltas`), e uma curva foi aberta pelo clique (`/api/radio/replay-da-volta/1?curva=C07`, resposta 200);
  - `/api/radio/melhor`, uma vez: a referência foi a sua melhor volta do store (`minha_melhor|2026-10-21_20-30-54_vhe_interlagos#0017`);
  - nenhum "different loop" e nenhum erro grave no log do backend.
- **O que não foi usado:** o botão "Abrir no app" (0 pedidos a `/api/radio/abrir-no-app`) e a roda do mouse (não aparece no log).
- **Para você conferir:** o log registrou uma vez "replay: janela 32 x 32", logo no começo. A janela do replay apareceu pequena demais na tela?
- **As falas (sem som):** o teste do rádio; 3 frases do coach na volta de saída, contra "a sua melhor"; e 1 resumo: "Melhor volta, 2,5 segundos atrás da referência. Curva 3: 7 décimos, mínima 24 quilômetros por hora abaixo da sua melhor. Tempo: 1 minuto e 29,4 segundos." **Esse resumo precisa ser revisto:** uma "melhor volta" que está "atrás da referência" confunde. A referência aqui é a sua melhor do store, e não a volta da IA.
- **O FPS (20:05 a 20:15):** média de 97,0 com o replay ligado (55 medidas de 10 s, mediana 97,9, a pior 80,4). **De novo, nenhuma medida com o replay desligado durante as voltas.**

## 07/11, 20:16 a 20:53: a voz no app instalado, corrigida

- `60d3f9e7`: `build_backend.ps1` passa a incluir o `voz.ps1` com `--add-data ...;core\radio`. O `audio.py` procura o arquivo ao lado dele mesmo, e no pacote isso é `_internal\core\radio`. É o único arquivo do backend que não é Python.
- `npm run dist:win` de novo, no commit `60d3f9e`. O `build-info.json` diz `dirty: true` só por causa de `versoes/LEIA-ME.md` (refeito pelo próprio build) e do pedido 47, que não é deste pedido e não está no commit.
- A instalação (`/S`) ficou parada até você aceitar a permissão de administrador do Windows, às 20:48. Ela terminou com o código 0, e o `voz.ps1` agora está no app instalado.
- **Conferido às 20:53:** abri o app instalado e mandei a mensagem de teste (`POST /api/radio/teste`). O backend gerou o áudio (`duracaoS` 4,09; um `.wav` de 131 KB), e nenhum "Radio sem voz" apareceu no log depois da instalação. **O som não foi ouvido no jogo.** O app instalado ficou aberto.

## 12/11: as suas decisões e o aviso de teste

**O aviso:** "Testei o rádio e o replay no jogo", com as quatro decisões e "pode fechar o pedido e fazer o merge". **As anotações não vieram na mensagem.**

**O que os registros mostram depois da correção da voz (07/11, 20:53):**

- nenhuma fala do rádio: o último registro do rádio é de 07/11 (`data/radio` do app instalado e do repositório), e o último áudio é o da mensagem de teste das 20:53;
- as 10 sessões de 09/11 (8:57 a 15:16) são na pista `vhe_interlagos_teste_m1`, a cópia da pista do pedido 47, em que a IA do jogo dirige a linha gerada (ADR 0029). Com a IA dirigindo, o rádio se cala, como manda a regra (decisão 2). O log do backend de 09/11 tem 28 pedidos da lista dos boxes e nenhum de áudio;
- o log do CSP da última abertura (09/11, 15:01): nenhum erro de Lua; a janela do replay abriu sozinha nos boxes e voltou como estava na saída; o FPS com o replay ligado foi de 192,5 de média (86 medidas), numa janela de 1078 × 802. **Não dá para comparar** com os 97 e 106 de 07/11, em tela cheia.

**O que, por isso, nenhum teste mostrou:** o rádio falando pelo app instalado, o botão "Abrir no app" (0 pedidos, em todos os logs), a roda do mouse e o FPS com o replay desligado durante as voltas. A janela do replay aparece como 32 × 32 no log, logo depois de carregar, nas aberturas de 07/11 e de 09/11: falta saber se ela fica pequena na tela.

### As decisões, aplicadas

1. **O limite do resumo passa a 8,0 s** (`FALA_MAXIMA_S`, em `backend/core/radio/texto.py`).
2. **A volta da IA fica calada:** já era assim; está registrado no ADR 0027.
3. **A perda antes da primeira freada não conta como causa:** já era assim; está registrado no ADR 0027.
4. **O resumo sempre diz contra quem:**
   - a melhor volta desta sessão é "melhor volta da sessão", e a diferença para ela é "atrás da melhor da sessão";
   - a referência "minha melhor" (a sua melhor volta limpa do store) é "do seu recorde", na voz, no cartão ("para o seu recorde (1:26,900)"), na causa ("freou 15 metros antes do seu recorde"), na frase do coach e na análise;
   - a IA continua "da IA"; sem referência conhecida, "da referência";
   - quando a volta é recorde pessoal e a referência é a sua melhor, a diferença para a referência não é dita: o recorde já diz quanto bateu o antigo;
   - o seu exemplo agora sai assim: "Melhor volta da sessão, 2,5 segundos atrás do seu recorde.";
   - as mesmas palavras no replay ("seu recorde (referência)"), no app do jogo ("para o seu recorde", "para a melhor da sessão", "freada do seu recorde"; versão **0.5.1**) e no replay da tela Ao vivo.

**Por que o app instalado usou a sua melhor no lugar da volta da IA:** a configuração dele, `%APPDATA%\Automobilista Telemetria\data\configuracao\app.json`, tem `"referenciaCoach": "minha_melhor"`, gravada em 14/10/2026 às 11:58. É a escolha "Minha melhor" da tela Coleta de dados, feita no app instalado. O app do repositório não tem esse arquivo e usa o padrão, a volta da IA. Em 07/11, a referência do app instalado foi a volta `2026-10-21_20-30-54_vhe_interlagos#0017`, e o resumo comparou a melhor volta da sessão com ela: "Melhor volta, 2,5 segundos atrás da referência". **Para voltar à IA:** na tela Coleta de dados do app instalado, escolha "Volta da IA".

### O que o limite de 8,0 s mudou, com a voz de verdade

As 4 sessões de novo, pelo mesmo caminho do C.6 (`radio_depois.py`), com o código de hoje. Os números estão em `…_limite_8s.json`.

| | com 7,7 s e as palavras de antes | com 8,0 s e as palavras novas |
|---|---|---|
| resumos | 51 | 49 |
| resumos de voltas que contam (com a curva) | 31 | 30 |
| a curva na voz | 31 | 30 |
| a curva e a causa na voz | 19 | 17 |
| mensagens próprias da curva | 5 | 5 |
| a diferença para a IA na voz | 7 | 7 |
| falas acima do limite | 0 | 0 |
| o resumo mais longo | 7,69 s | 7,94 s |

- **O limite novo não deu mais causas, porque as palavras novas custam o mesmo tempo.** A causa entrou numa volta (21/10, volta 17: "4 décimos atrás da melhor da sessão. Curva 1: 1,2 segundo, mínima 35 quilômetros por hora abaixo.", 7,94 s) e saiu de duas: 18/10, volta 8, e 01/11, volta 6. Nas duas, "Melhor volta da sessão, … Curva 1: 7 décimos, freou 46 metros antes." passa de 8,0 s. Antes, com "Melhor volta", cabia em 7,69 e 7,67 s.
- **Os 2 resumos a menos** são os da última volta de 13/10 (volta 14) e de 21/10 (volta 20, com rodada): a gravação acaba antes de o rádio achar uma janela para eles.
- **Se você quiser as causas de volta:** um limite de 8,3 s, ou "Melhor da sessão" no lugar de "Melhor volta da sessão". Não mudei nada além do que você decidiu.

### Os testes

- backend: a suíte inteira, **935 passando** (37 avisos do scikit-learn, como antes), em 10 min 37 s, com o código de `7c9f6c9c`;
- os testes do rádio: 63 passando, com um teste novo para a decisão 4 (`test_o_resumo_sempre_diz_contra_quem`);
- front: 180 passando; `tsc` sem erro;
- Lua: a conferência contra o SDK do CSP passa (34.612 tokens, nenhum erro de léxico, toda a API existe).

### O que ficou instalado

- **O app do Windows instalado** é a 0.7.0 de `60d3f9e`: tem a voz, mas não as palavras de hoje nem o limite de 8,0 s. Elas só chegam no próximo instalador, quando você pedir.
- **A pasta do jogo** tem o app do jogo 0.5.0. A 0.5.1, com as palavras novas, vai pelo `instalar.ps1`, que você roda.

## O que precisa de você

1. **O teste no jogo:** os passos e a tabela estão na Parte G. **Antes, rode os comandos de envio** (no fim), porque o pedido manda enviar a branch antes da parada.
2. **Decisão: o limite do resumo** (Parte C). O que você quer ouvir nem sempre cabe em 7,7 s, e a diferença para a IA quase sumiu da voz: ela está em 7 dos 51 resumos.
3. **Decisão: a volta da IA.** A C.1 diz "o tempo e a diferença para a melhor, como hoje", mas hoje ela não tem resumo, e a G.8 diz que o rádio se cala. Deixei calada.
4. **Confira uma escolha minha:** a parte da perda antes da primeira freada não conta como causa (Parte C).

## O que este pedido ainda não prova

- **Nada do app do jogo foi visto dentro do jogo:** a janela que abre sozinha, a lista, o clique, a roda do mouse e o botão. Não há Lua neste computador. A conferência cobre o léxico, os blocos e a API; as prévias repetem as contas num HTML.
- **O erro do WebSocket não apareceu em nenhuma reprodução de gravação, nem no código antigo** (Parte B.3). A correção está provada direto no código; falta contar no log depois do teste no jogo.
- **Se o rádio ensina:** a eficácia só um teste de retenção prova.
- **O caminho com o backend do 0.5.0 e do 0.6.0** foi conferido só lendo o código.

## Parte A: as conferências

1. **Os caminhos do contexto:** todos estão onde o contexto diz.
2. **O antes:** na tabela do C.6, com o motivo. As falas, volta a volta, estão no JSON.
3. **O que o backend guardava das voltas:** só a última fechada e as válidas da análise. Agora toda volta fica guardada, em 5 linhas float32: **43 KB por volta,** de 563 a 867 KB por sessão, sem ler a gravação.
4. **O que a análise mede por curva:** a perda, a freada, a mínima, o acelerador e o traçado (com corte de 1,8 m). Entraram a velocidade no fim da curva e as partes da perda.
5. **O app do Windows:** ele ouve o WebSocket, e o aviso novo passa por ali. A tela Volta abre numa volta (`#/volta/<lapId>`), mas só nas voltas do store, e a sessão ao vivo não está nele. Por isso, a tela Ao vivo abre o replay em tamanho grande, como o pedido manda.
6. **As placas de freada:** o projeto não tem. Registrei no backlog, e a freada fica dita pela IA.

**O que não bate com o pedido:** o estado "inválida" não existe. As gravações e o quadro do jogo não trazem esse sinal. A lista tem válida, com rodada, da IA e incompleta. Registrei no backlog.

## Parte B: as voltas que o rádio não vê

### B.1 As voltas incompletas

**A causa não era um buraco na amostragem.** Era a regra "boxes" do coach: um microssetor com a lateral acima de 10 m e abaixo de 90 km/h não era comparado, em qualquer ponto da pista. A volta 10 de 21/10 (1:29,518) caía nela por um microssetor, o 38, com 11,0 m e 81,9 km/h.

**Sua decisão, aplicada:** a regra só vale no pit lane, nos microssetores 54 a 59 e 0 a 10 de Interlagos. Em outra pista, ela continua na volta inteira.

**Um defeito corrigido junto:** o rádio só lia a geometria na primeira frase do coach ou na primeira janela, e a primeira volta que fechava antes disso saía "sem as medidas" (a volta 2 de 13/10 e de 18/10).

| | 13/10 | 18/10 | 21/10 | 01/11 |
|---|---:|---:|---:|---:|
| voltas que fecham na linha | 13 | 13 | 17 | 9 |
| completas, antes | 7 | 9 | 7 | 6 |
| completas, depois | 8 | 10 | 9 | 7 |
| **na grade, antes** | 6 | 8 | 6 | 6 |
| **na grade, depois** | 8 | 9 | 8 | 6 |

As 5 voltas que ficaram completas: 1:33,120 (13/10), 1:40,073 (18/10), 1:34,494 e 1:29,518 (21/10) e 2:17,368 (01/11). A de 2:17,368 continua fora da grade, por rodada. **A maioria das incompletas é parada ou saída de verdade, e continua incompleta.**

**A regra mudou também as frases do coach,** porque mais microssetores são medidos e o foco muda: de 26 para 31 nas 4 sessões (5→5, 3→4, 10→15 e 8→7). As regras de quando falar não mudaram. Não medi se essas frases novas são boas: confira no teste.

### B.2 A numeração

**De onde vinha cada buraco:**

- **o coach:** o contador do jogo muda cerca de 1 a 2 m depois do s = 0, mas em 2 passagens ele mudou antes (13/10, a volta 9; 21/10, a 14). A volta saía com o número seguinte e perdia as medidas, porque o número não batia com o da volta ao vivo;
- **voltas que não começam na linha:** a saída dos boxes ou o carro movido (21/10, a 8 e a 15; 01/11, a 3, a 4 e a 9). Em 21/10, a 14 fecha na linha; quem não fecha é a 15. O número errado escondia isso;
- **a gravação e o store não têm buracos.** O store já guarda o número certo (`game_lap_number`).

**Qual vence: o contador do jogo no meio da volta.** É o número que você vê no jogo, ele existe ao vivo e bateu com o store nas voltas que conferi em 13/10 e 21/10. O `#NNNN` do id é só a ordem no arquivo. A tela Volta passou a mostrar o número do jogo, e o botão cruza pelo tempo da volta (±0,15 s).

| números repetidos na lista | 13/10 | 18/10 | 21/10 | 01/11 |
|---|---:|---:|---:|---:|
| antes | 1 | 0 | 0 | 0 |
| depois | 0 | 0 | 0 | 0 |

**A prévia achou um defeito meu, corrigido:** com o carro movido no meio da volta, a mesma volta entrava duas vezes (a 8 de 21/10). Agora fica o pedaço que mediu mais pontos.

### B.3 O erro "attached to a different loop"

**A causa:** no Python 3.9, `asyncio.Lock()` guarda o laço em que nasce, e o gerente nasce ao importar o módulo, antes do laço do servidor. Só dá erro quando dois envios disputam a trava. **A correção:** a trava nasce no laço que envia.

| como | antes | depois |
|---|---:|---:|
| 3 envios ao mesmo tempo, direto no módulo | **2 de 3 falham** | 0 |
| gravação, clientes lentos e travados, adversários a 40 Hz | 0 | 0 |
| gravação com a tela Ao vivo aberta, velocidade 3, adversários a 40 Hz, 240 s | 0 | 0 |

**O pedido manda contar numa reprodução de gravação, e ela não distingue os dois:** não consegui fazer o erro aparecer assim, mesmo no código antigo. As 9 ocorrências do pedido 43 não se repetiram. O `logs/backend.log` tem 133, de sessões com o jogo. **A prova que falta é contar no log depois do teste no jogo.**

**Duas medições foram descartadas:** um backend meu que tinha sobrado na porta respondia no lugar do novo, e numa delas fechei a tela no meio. Os números acima são os refeitos, com um cliente ligado em cada passagem.

## Parte C: o rádio

**Os cortes novos** (`460acdc9`, antes de rodar as sessões): a velocidade no fim da curva usa o corte da mínima, 8 km/h, porque é a mesma grandeza, medida do mesmo jeito. O traçado usa o que a análise já tinha, 1,8 m. Abaixo de 1 décimo, nenhuma curva é citada.

**A escolha minha, para você conferir:** as separações do pedido 43 são 3 marcas, então a perda ficou em 4 partes, e o trecho que explica a perda é um dos 3 últimos:

| parte | de onde a onde | é causa? |
|---|---|---|
| reta | da entrada do trecho à primeira freada | não: veio da curva anterior |
| freada | da primeira freada à mínima da referência | sim |
| mínima | da mínima da referência ao fim da curva | sim |
| saída | do fim da curva ao fim do trecho | sim |

**Outra escolha:** uma mínima ou uma saída mais rápidas que a IA não contam como causa do resumo, porque não explicam uma perda.

### C.6 Antes e depois, com a voz de verdade e o código final

| resumos | 13/10 | 18/10 | 21/10 | 01/11 | total |
|---|---:|---:|---:|---:|---:|
| total | 13 | 13 | 17 | 8 | 51 |
| **antes:** com a curva | 6 | 8 | 6 | 6 | 26 |
| **antes:** só a diferença para a IA | 7 | 5 | 11 | 2 | 25 |
| motivo: incompleta | 5 | 4 | 9 | 2 | 20 |
| motivo: sem as medidas | 2 | 1 | 1 | 0 | 4 |
| motivo: rodada | 0 | 0 | 1 | 0 | 1 |
| **depois:** com a diferença para a melhor | 13 | 13 | 12 | 8 | 46 |
| **depois:** com a diferença para a IA | 1 | 0 | 6 | 0 | 7 |
| **depois:** com a curva | 8 | 9 | 8 | 6 | 31 |
| **depois:** com a curva e a causa | 7 | 6 | 3 | 3 | 19 |
| curva ou causa sem lugar: mensagem própria criada | 1 | 3 | 5 | 3 | 12 |
| dessas, faladas | 1 | 1 | 1 | 2 | 5 |
| dessas, saíram da fila (a curva passou antes) | 0 | 2 | 4 | 1 | 7 |

- **A causa de cada curva citada (31):** por trecho, freada 18, mínima 11 e saída 2. Por medida, freada 17, mínima 10, saída 2, traçado 1 e só o trecho 1.
- **Quanto cada fala dura, contra o limite:** nenhuma passou. Resumo até 7,69 s (limite 7,7), coach até 7,30 s (7,3), análise até 8,73 s (8,8) e curva até 5,70 s (7,3).
- **Os números do replay na fala:** 52 de 60 curvas. As outras 8 são a segunda curva de uma análise, que a voz não citou: elas não têm número falado, e o replay mostra o do cartão.
- **"Recorde pessoal" apareceu:** volta 18 de 21/10 (1:26,875). Fora do tempo real, o recorde foi medido contra as sessões anteriores do store.

**O problema que continua: 12 das 31 curvas citadas ficaram sem a causa no resumo, e só 5 dessas falaram numa mensagem própria.** É o mesmo limite da decisão abaixo.

Exemplos de 21/10, com a voz de verdade:

- volta 18: "Recorde pessoal, 1 décimo mais rápida. Curva 1: 7 décimos, freou 46 metros antes da IA." (7,44 s);
- volta 10: "Melhor volta, 1,3 segundo mais rápida. Curva 11: 1,5 segundo." (6,28 s; a causa não coube);
- volta 14: "2,4 segundos atrás da sua melhor, 5,7 segundos atrás da IA." (5,59 s; a volta não conta, sem a curva).

### Decisão: o limite do resumo

| os seus exemplos (C.5) | dura |
|---|---:|
| "3 décimos atrás da sua melhor, 4,2 segundos atrás da IA. Curva 1: 7 décimos, freou 15 metros antes da IA." | **8,73 s** |
| "Melhor volta, 2 décimos mais rápida. Curva 12: 4 décimos, saiu 8 quilômetros por hora mais lento." | **7,72 s** |
| "1,1 segundo atrás da sua melhor. Curva 6: 5 décimos, passou 3 metros por fora no ápice." | 7,48 s |
| "Volta com rodada: 1 minuto e 36,4 segundos, 7,0 segundos atrás da sua melhor." | 7,13 s |

| cada variante, das 4 causas | dura |
|---|---:|
| tudo: a melhor, a anterior, a IA, a curva e o tempo | 14,8 a 16,1 s |
| sem o tempo | 11,0 a 12,4 s |
| sem a anterior | 8,7 a 10,1 s |
| sem a IA | 6,4 a 7,8 s |
| sem dizer contra quem ("da IA") | 6,2 a 7,5 s |
| sem a causa | 4,7 a 5,2 s |
| só a melhor | 2,4 s |

As janelas têm de 7,8 a 8,7 s. **As duas opções:**

- **subir o limite do resumo para 8,0 s:** o seu segundo exemplo passa a caber, e a causa cabe mais vezes (não medi quantas). A IA continua fora na maioria. Com a folga de 0,3 s, a fala precisa de 8,3 s de janela, então as janelas mais curtas ficam de fora;
- **subir para cerca de 8,7 s:** o seu primeiro exemplo cabe, mas só na janela mais longa, e o resumo pode esperar a volta seguinte.

**Recomendo 8,0 s.** A causa foi o que você pediu, e a IA fica no cartão. **Não mudei o limite:** ouça no teste e decida.

### C.3 e C.4

- **A frase do coach e a análise** usam as palavras novas. A análise começa pela tendência, se couber: "Média 9 décimos mais lenta que as 3 anteriores."
- **O minimapa:** uma rota nova (`/api/radio/melhor`) e uma linha, "+0,31 s para a sua melhor". Coube no que o pedido pediu. A faixa de cima cresceu de 30 para 40 px.

## Parte D: o replay de perto

**O zoom: 80 m no lado menor.** Numa janela de 300 px, um carro de 4,5 m fica com cerca de 15 px.

As prévias repetem as contas da janela do jogo, na volta 6 de 01/11, em 300 × 300, em 420 × 300 e na área do replay dos boxes (560 × 400), com a câmera de antes e a de depois: `_previa_camera_c01.png`, `_c06.png`, `_c12.png` e a folha inteira. **Os carros ficam bem maiores, e o trecho da causa fica marcado.**

- **O começo:** a curva inteira por 1 s, parada, e 0,8 s de aproximação.
- **Os dois carros sempre na tela:** há um teste com um carro muito mais lento.
- **Câmera lenta:** só quando cabe no que resta da janela. Na reta, se a curva não couber, o replay começa um pouco antes do trecho, para ele aparecer. Isso não estava no pedido, mas sem isso a janela acabaria antes da causa.
- **A marca fora da tela** não ganha rótulo; os números da voz ficam no alto.

## Parte E: os boxes e o botão

- **A janela** abre sozinha e cresce 2 vezes, para 840 × 600. Eram 1,6 vez: mudei para a lista caber. Na saída, ela volta como estava.
- **A lista e a grade de 01/11** estão em `_previa_lista_01-11.jpg`. Elas mostram o que você descreveu: a C06 e a C13 na volta 3, a C01 e a C06 na volta 4, a C05 na volta 10 e a C01 na volta 11.
- **As voltas 3 e 4 de 01/11 não começam na linha,** então não fechavam para o rádio. Elas agora entram na lista e tocam, com o tempo corrido do jogo, sem resumo, fora da análise e sem a diferença para a melhor, porque esse tempo inclui as paradas.
- **Sem volta fechada:** "nenhuma volta fechada nesta sessão".

**O tamanho e o tempo das rotas, nas 4 sessões:**

| rota | tamanho máximo | tempo máximo |
|---|---:|---:|
| a lista das voltas | 5,1 KB | 0,2 ms para serializar |
| a volta inteira | **140,5 KB** (limite de 500 KB) | 42 ms |
| uma curva | 31,9 KB | 9 ms |
| a melhor volta (01/11) | 17 KB | 5,5 ms |

**Ponta a ponta,** com o reprodutor e a pasta isolada, numa aba "[teste]" já fechada: o pedido feito direto à rota abriu a volta 7 na C01 (`_abrir_no_app_v7_c01.jpg`) e a volta inteira (`_abrir_no_app_v7_inteira.jpg`), com os 4 visuais. Com a aba fechada, a resposta foi "o app do Windows está fechado". **O teste achou um defeito, corrigido:** repetir o mesmo pedido não relia o replay. **Não repeti depois da regra do pit lane e da correção do número,** que não mexem nesse caminho.

**O caminho para a tela Volta:** o botão aparece quando a volta já está no store. Numa sessão ao vivo, ele só aparece depois da próxima rodada do coach, e o replay grande diz isso.

**O que o Windows faz** (o app vir para a frente ou só piscar) só o teste no jogo mostra.

## Os testes

- **Backend:** 934 passando, 37 avisos (`_testes.txt`), no código de `d6594970`.
- **Front:** 180 passando, `tsc` e build sem erro.
- **Lua:** `conferir_lua.py` contra o SDK do CSP: 0 erros de léxico, blocos fechados, API e métodos no SDK. 172 locais no topo, de 200.

## Parte H: a documentação e a versão

Feita: `docs/realidade_aumentada.md` (seções 2.2, 5.4.2, 7 e 8), ADR 0027 (novo), ADR 0021, `docs/backlog.md` (os 3 itens da Parte B fechados, o do FPS continua e 2 novos: as placas e o estado "inválida"), `docs/app_para_producao.md`, `docs/dashboard_inventario.md` e `docs/tecnica_de_pilotagem_lista.md`. Os exemplos antigos da documentação, medidos com as palavras de antes, ficaram como estão, com um aviso.

**A versão:** `0.7.0-radio-que-ensina` nos 3 pontos e o app do jogo 0.5.0. **Falta completar, depois do teste:** o FPS e o que o Windows faz.

## Parte G: o teste no jogo, com você

**A versão nova do app do jogo é a 0.5.0.** O número é igual ao do app do Windows instalado, mas são dois programas diferentes.

**O app do jogo novo fica instalado depois do teste. Ele funciona com o 0.5.0 instalado:** sem as rotas novas, a janela mostra o replay como hoje, sem a lista e sem o botão. Conferi isso lendo o código; o teste não passa por esse caminho.

**Os passos:**

1. **Feche o jogo e o app instalado, inclusive o ícone na bandeja.**
2. **Instale o app do jogo 0.5.0.** A pasta tem de estar na branch `etapa/replay-e-radio-que-ensina`:
   ```powershell
   git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer branch --show-current
   ```
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Dokas\Desktop\f1-telemetry-analyzer\tools\csp_app\instalar.ps1
   ```
3. **Abra o app pelo repositório.** Ele grava em `C:\Users\Dokas\Desktop\f1-telemetry-analyzer\data\recordings`:
   ```powershell
   $env:AT_BACKEND_USE_PYTHON_RUNNER='true'; cd C:\Users\Dokas\Desktop\f1-telemetry-analyzer\desktop; npm.cmd run desktop:prod:autostart
   ```
   **Confira na aba Coleta de dados, em "Versão do app":** tem de aparecer `0.7.0-radio-que-ensina`, "rodando do código-fonte".
4. **No jogo, ligue o rádio, o minimapa e o replay** na barra de apps. Ponha o replay num canto, sem cobrir o centro.
5. **Na tela Sistema, clique em "Mandar mensagem de teste"** e olhe o cartão. Ele ficou sem confirmação no pedido 43.
6. **Ande pelo menos 8 voltas, você mesmo, com uma ida aos boxes depois da 3ª volta válida e outra no fim, de pelo menos 1 minuto cada.**
7. **Nos boxes:**
   - veja se a janela abriu sozinha, e se volta como estava na saída;
   - toque 2 voltas (clique no número) e 2 curvas (clique na célula);
   - gire a roda do mouse sobre o replay e sobre a lista;
   - aperte "Abrir no app" uma vez e anote se o app veio para a frente ou só piscou.
8. **Nunca aperte Ctrl+C:** ele passa o carro para a IA, e o rádio se cala.
9. **Desligue o replay por 2 ou 3 voltas e ligue de novo,** para o FPS.
10. **Anote, em cada fala, na tabela abaixo.**
11. **Avise: "testei o rádio e o replay no jogo".**

| volta | o que eu ouvi | entendi onde perdi? | entendi por quê? | o replay mostrou? |
|---|---|---|---|---|
| | | | | |
| | | | | |
| | | | | |
| | | | | |
| | | | | |
| | | | | |
| | | | | |
| | | | | |

**Se puder, responda também:** o resumo ficou comprido? Sentiu falta da diferença para a IA na voz? As frases do coach em curvas novas fizeram sentido?

**Depois do seu aviso, eu:**

- confiro que o teste aconteceu (a versão na pasta do jogo, a data do `log.txt` e a última gravação);
- confiro o registro do rádio e os replays entregues;
- **conto "different loop" no log do backend;**
- leio, sem mudar nada, as linhas `[radio_engenheiro]` do log do CSP;
- meço o FPS com o replay ligado e desligado;
- completo este relatório e a documentação, com as suas decisões;
- faço o merge em `develop`.

## O envio ao GitHub

**Nada foi enviado.** No pedido 44, o controle de permissões recusou o envio, então é você quem roda.

**Conferido antes do envio, nos commits desde `aa576597`:** o maior arquivo tem 1,3 MB (nada acima de 50 MB); nenhum arquivo em `recordings/`, `data/recordings` ou `data/ml`; nenhum segredo.

| ref | hash local | no remoto |
|---|---|---|
| `refs/heads/etapa/replay-e-radio-que-ensina` | `0907aec8` (e depois o commit da nota de 06/11) | `0907aec8`, conferido em 06/11 |
| `refs/heads/develop` | `bd04b93e` | `aa576597` |

**Só a branch vai agora.** Ela já leva `bd04b93e`. O `develop` vai depois do merge. `main` e as tags não vão. Sem `--force`.

```powershell
git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer push -u origin etapa/replay-e-radio-que-ensina
```

```powershell
git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer ls-remote origin refs/heads/etapa/replay-e-radio-que-ensina
```

Me avise quando rodar, para eu conferir o hash remoto. Se pedir login, se recusar ou se o remoto tiver divergido, pare e me avise.

**O que abri para testar já está fechado:** não sobrou backend nas portas de teste (8011, 8021, 8022, 8031, 8032, 8041, 8042), nem o servidor das prévias, nem aba "[teste]". Nenhum Electron foi aberto.
