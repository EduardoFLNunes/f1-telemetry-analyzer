# Pedido 45 — O replay de perto, as voltas nos boxes e o rádio que diz onde e por quê

**De:** Eduardo. **Data:** 02/11/2026.
**Tipo:** backend (o rádio, o replay e as voltas da sessão), app Lua do CSP (o replay e o minimapa), front (a tela que abre o replay) e documentação. Nenhum modelo nem store muda.

**Quando começar:** depois do merge do pedido 44 em `develop`, nesta conversa ou numa nova. Antes de criar a branch, confira que nenhuma outra sessão está ativa na pasta (ADR 0008).

## Contexto

1. **O que eu observei (02/11):**
   - **o replay mostra a curva de muito longe.** Enquanto eu dirijo, não dá para ver onde eu errei;
   - **nos boxes, o replay tem de aparecer,** com as voltas da sessão e o replay de cada uma, para eu estudar, e com um botão que abre o replay no app do Windows, com mais informação;
   - **o rádio passa pouca informação útil.** Hoje ele quase sempre diz só a diferença da volta para a IA. Eu quero ouvir:
     - a diferença da volta para a minha melhor ou para a anterior, e para a IA, em décimos ou segundos;
     - quantos décimos eu perdi na curva X;
     - e por quê: lento demais, aberto demais, longe do traçado, freada cedo ou tarde.
2. **O que o código faz hoje** (`develop`, app do jogo 0.4.2):
   - **a câmera do replay** (`cameraDaCurva`, em `radio_engenheiro.lua`, a mesma da tela Ao vivo em `frontend/src/aoVivo/replay.ts`) encaixa as duas linhas da curva inteira na janela, com 18 px de margem. Numa curva longa, os carros ficam pequenos. O mapa aproximado, ao contrário, abre com 120 m e tem zoom pela roda do mouse, de 50 a 400 m;
   - **nos boxes ou com o jogo pausado,** a janela do replay cresce 1,6 vez e repete a última análise, com a grade das últimas 8 voltas válidas. Sem análise, ela não tem o que mostrar, e ela só aparece se eu tiver ligado a janela. No teste de 01/11, a ida aos boxes caiu com a janela desligada;
   - **o resumo na linha** (`docs/realidade_aumentada.md`, seção 2.2) diz a diferença para a referência e a curva que mais perdeu. A curva só entra numa volta completa (todos os microssetores medidos);
   - **as janelas de rádio:** três em Interlagos. O resumo nasce na linha e sai quase sempre na reta oposta (723 a 1.192 m), com 7,8 a 8,7 s de janela. Os limites são 7,7 s (resumo), 7,3 s (frase do coach) e 8,8 s (análise), com a voz a 1,4x.
3. **Por que o rádio diz pouco** (itens do backlog que saíram do pedido 43; a minha decisão de 01/11 foi um pedido próprio, que passa a ser este):
   - **voltas de tempo normal marcadas como incompletas:** 9 das 19 em 21/10, como a volta 10 (1:29,518). Elas ficam fora da análise e da grade, o resumo delas não cita a curva, e quase todas as frases do coach caem nelas;
   - **os buracos na numeração das voltas:** em 13/10, o 10 aparece duas vezes e o 9 some; em 21/10, a 8 e a 14 não fecham na linha;
   - **o erro "attached to a different loop"** no envio por WebSocket (`TelemetryBroadcaster._drain_frames`, `core/websocket_server.py`);
   - o FPS que varia ao longo da sessão fica no backlog, fora deste pedido.
4. **Como engenheiros e coaches falam com o piloto** (pesquisa de 02/11; as fontes estão no fim):
   - **curto e direto,** para o piloto agir sem pensar. Um lembrete custa pouco;
   - **na reta,** nunca na freada nem numa curva rápida. O que não é urgente fica para os boxes;
   - **informação, e não "vai mais rápido":** um número e um alvo;
   - **o tempo sozinho ajuda pouco.** "0,8 s mais lento no setor 2" não diz o que fazer; "freando cedo demais na curva 5" diz. A ferramenta Delta (Coach Dave) compara cada fase da curva (freada, entrada, ápice e saída) com uma volta de referência e recomenda uma referência de 0,5 a 1,5 s mais rápida: mais longe que isso, tudo vira perda;
   - **uma correção por vez** (o coach por voz da Trophi): depois da curva, o que mais custou; no fim da volta, o que melhorou, o que ainda segura e o foco seguinte. A freada é dada por uma marca da pista, como a placa de 100 m;
   - **na F1, em corrida,** a FIA restringiu o coaching por rádio (o traçado e a zebra) em 2014 e 2016. O tempo de volta e de setor do próprio piloto continuou permitido. O nosso rádio é de treino, onde o coaching vale;
   - **no projeto** (`docs/tecnica_de_pilotagem_pesquisa.md`): uma correção por vez, o foco externo (uma marca da pista, e não o corpo), a faixa de tolerância (não falar do que está perto da referência) e a eficácia só provada por um teste de retenção.
5. **As regras que continuam:**
   - a diferença medida contra uma volta real, nunca um ganho prometido (ADR 0012);
   - as unidades na voz (pedido 36);
   - no replay de uma mensagem com curva, os números da voz (pedido 43);
   - nada dito dentro das 14 curvas;
   - a referência é a escolhida na Coleta (a IA por padrão). A escolha da referência para sugerir técnica (C2) não muda aqui.

## Parte A — Conferências (só leitura)

1. **Os caminhos do contexto:**
   - o replay: `backend/core/radio/replay.py`, `GET /api/radio/replay/{id}`, a função `replay` do app do jogo e `frontend/src/aoVivo/replay.ts`;
   - o texto (`backend/core/radio/texto.py`), a análise (`core/radio/analise.py`), as janelas (`core/radio/janelas.py`) e a grade (`/api/radio/grade`).

   Se algum não estiver onde o contexto diz, registre.
2. **O antes,** nas sessões de 13/10, 18/10, 21/10 e 01/11 (a do teste do pedido 43), fora do tempo real: o que o rádio disse em cada volta e quantos resumos trazem só a diferença para a IA, com o motivo (volta incompleta, rodada, IA ou outro).
3. **O que o backend guarda das voltas da sessão ao vivo:** as voltas, a perda por curva e os pontos na grade oficial (posição, relógio, velocidade e pedais). O replay de qualquer volta e de qualquer curva da sessão (Parte E) precisa disso. Se os pontos das voltas antigas não ficam guardados, diga como obtê-los sem ler a gravação durante a sessão, e o custo em memória.
4. **O que a análise já mede por curva:** a freada, a mínima, o traçado (onde e com que corte) e as separações da diferença acumulada do pedido 43 (freada, mínima e saída). A Parte C usa só essas medidas, mais a velocidade no fim da curva.
5. **O app do Windows:**
   - se ele recebe pedidos do backend, pelo WebSocket ou por outro canal que já existe;
   - se alguma tela abre numa volta e numa curva escolhidas (a tela Volta ou o cartão do replay da tela Ao vivo).
6. **As marcas da pista:** se o projeto já tem a posição das placas de freada de Interlagos. Se não tem, não crie: registre no backlog.

## Parte B — As voltas que o rádio não vê

1. **As voltas marcadas como incompletas:**
   - ache a causa nas 9 de 21/10 (a volta 10, de 1:29,518, primeiro) e conte o mesmo nas outras 3 sessões;
   - se for um defeito (um microssetor sem medida por um buraco na amostragem, na projeção ou no corte da volta), corrija;
   - **se a correção exigir mudar o critério de volta completa do coach, pare nesse item e proponha.** A decisão é minha.
2. **A numeração das voltas:**
   - ache de onde vem cada buraco: a gravação, o coach, o store ou o rádio;
   - **uma volta tem um número só** no rádio, na grade, na lista dos boxes e no app do Windows. O botão da Parte E precisa abrir a volta certa;
   - registre qual numeração vence e por quê.
3. **O erro "attached to a different loop":** a causa e a correção. Conte o erro numa reprodução de gravação, antes e depois; depois, zero.
4. **Testes** para cada item, e a contagem antes e depois nas 4 sessões: voltas completas, voltas com o número errado e erros do WebSocket.

## Parte C — O rádio que diz onde e por quê

**Regras para a Parte C:**

- **Os cortes novos** (a velocidade no fim da curva e o traçado, se a análise não tiver um corte) são registrados e commitados antes de rodar as sessões, com o porquê tirado da definição, e não do resultado.
- **Uma correção por mensagem:** uma curva e uma causa. A segunda causa só entra se couber, e é a primeira a sair (pedido 36).
- **O cartão traz todos os números; a voz, os que cabem.** As unidades seguem o pedido 36: décimos abaixo de 1 s, segundos com uma casa a partir de 1 s.
- **O replay de uma mensagem com curva** mostra os números da voz, pela regra do pedido 43.

### C.1 O resumo da volta

1. **O que entra, pela ordem de importância:**
   1. a diferença para a sua melhor volta da sessão; ou "melhor volta", com o quanto ela foi mais rápida que a melhor anterior;
   2. a curva da volta (C.2), com a perda e a causa;
   3. a diferença para a IA (a referência escolhida);
   4. a diferença para a volta anterior, só quando a volta melhorou sobre a anterior sem ser a melhor;
   5. o tempo da volta. O cartão sempre tem o tempo.
2. **As variantes** vão da mais completa à mais curta, como hoje, e perdem os itens de baixo para cima na lista. Relate quanto cada variante dura.
3. **A melhor volta** é a mais rápida da sessão entre as que contam para a análise. Quando a volta bater a melhor de todas as sessões do store, para o carro e a pista, a voz diz "recorde pessoal".
4. **A volta com rodada, a inválida e a da IA:** o tempo e a diferença para a melhor, sem a curva, como hoje.
5. **Se a curva não couber no resumo,** ela vai numa mensagem própria, na próxima janela livre, sem passar à frente das frases do coach. Se a curva for passar de novo antes dessa janela, a mensagem sai da fila. Relate quantas vezes isso aconteceu.

### C.2 A curva da volta e o porquê

1. **A curva:** a que mais perdeu na volta contra a referência, com a mesma perda da análise e da grade. Abaixo de 1 décimo, nenhuma curva é citada.
2. **O porquê:** o trecho da curva (freada, mínima ou saída) com a maior parte da perda, pelas separações da diferença acumulada do pedido 43. A causa é a medida desse trecho:

   | trecho | a causa, quando passa do corte | exemplo da voz |
   |---|---|---|
   | freada | o ponto de freada, antes ou depois da IA (corte do coach: 15 m) | "freou 15 metros antes da IA" |
   | mínima | a mínima (corte do coach: 8 km/h); senão, o traçado no ápice, por fora ou por dentro | "mínima 9 quilômetros por hora abaixo da IA" · "passou 3 metros por fora no ápice" |
   | saída | a velocidade no fim da curva (corte novo) | "saiu 8 quilômetros por hora mais lento" |

3. **Se o trecho não tiver causa acima do corte,** a voz diz só o trecho: "perdeu 3 décimos na saída".
4. **"Por fora" e "por dentro"** vêm do lado da curva (ADR 0003): numa curva à esquerda, mais à direita é por fora.
5. **Se a Parte A.6 achar as placas de freada,** a freada também pode ser dita pela placa. Senão, fica pela IA.

### C.3 A frase do coach e a análise

- **A frase do coach:** o coach continua decidindo quando falar (o foco, o limiar, o máximo de 3 por volta e o microssetor). Só o texto passa a usar as palavras da C.2.
- **A análise das voltas:** a regra não muda. O texto usa as palavras da C.2 e, se couber, começa pela tendência: a média das 3 voltas contra a das 3 anteriores.

### C.4 A diferença ao vivo no minimapa

- Hoje o minimapa mostra a diferença ao vivo para a referência. Ele passa a mostrar também a diferença para a sua melhor volta da sessão, quando ela existe.
- Se isso pedir mais que uma rota nova e uma linha no minimapa, relate e deixe para depois.

### C.5 Exemplos do que eu quero ouvir

- "3 décimos atrás da sua melhor, 4,2 segundos atrás da IA. Curva 1: 7 décimos, freou 15 metros antes da IA."
- "Melhor volta, 2 décimos mais rápida. Curva 12: 4 décimos, saiu 8 quilômetros por hora mais lento."
- "1,1 segundo atrás da sua melhor. Curva 6: 5 décimos, passou 3 metros por fora no ápice."
- "Volta com rodada: 1 minuto e 36,4 segundos, 7,0 segundos atrás da sua melhor."

### C.6 O teste fora do jogo

Nas 4 sessões, antes e depois:

- quantos resumos trazem a diferença para a melhor, a diferença para a IA e a curva com a causa;
- quantas mensagens perderam a curva ou a causa por falta de janela;
- a causa de cada curva citada, por trecho;
- quanto cada fala dura, contra o limite do tipo;
- se os números do replay de cada mensagem com curva aparecem na fala.

## Parte D — O replay de perto

1. **A câmera acompanha os carros:**
   - centrada entre "você" e "IA (referência)", com cerca de 80 m no lado menor da janela. Escolha o valor entre 60 e 100 m pelo tamanho do carro na tela e registre;
   - a orientação continua a de hoje (a entrada para cima), fixa durante a curva.
2. **O começo:** a curva inteira por cerca de 1 s, para eu me localizar, e depois a aproximação.
3. **Os dois carros sempre na tela:** se eles se afastarem mais que a janela, a câmera se afasta o necessário, até a curva inteira.
4. **O trecho da causa** (C.2) ou o trecho da fala (pedido 43) fica marcado na pista. Quando o tempo deixar, ele passa em câmera lenta, na metade da velocidade. Na reta, o replay continua acabando com a janela de rádio (`restaS`).
5. **A roda do mouse** muda o zoom, como no mapa aproximado.
6. **Os rótulos** continuam sem se sobrepor (`QuadroDeRotulos`). Os números da voz ficam no alto da janela, mesmo quando a marca está fora da tela.
7. **A mesma câmera** na janela do jogo e na tela Ao vivo.

## Parte E — Os boxes: as voltas para estudar e o botão do app

1. **A janela abre sozinha:** nos boxes ou com o jogo pausado, a janela do replay aparece, mesmo desligada, e volta como estava quando eu saio.
2. **A lista das voltas:**
   - todas as voltas da sessão, e não só as últimas 8, com o número, o tempo (M:SS,mmm) e a diferença para a melhor;
   - o estado de cada uma, com o motivo: válida, inválida, com rodada, da IA ou incompleta;
   - a lista rola.
3. **A grade é o caminho para o replay:**
   - um clique numa célula toca a curva daquela volta;
   - um clique na volta toca a volta inteira, com a câmera da Parte D. A célula da curva em que os carros estão fica acesa, e um clique numa curva pula para ela;
   - as voltas com rodada também tocam, com o aviso "fora da análise: rodada". Elas mostram onde o carro saiu de traseira (em 01/11: a C05, a C06 e a C13 na volta 3; a saída do S do Senna e a C06 na volta 4; a C05 na volta 10; a C01 na volta 11). As voltas da IA ficam fora.
4. **A rota:**
   - o replay de qualquer volta e de qualquer curva da sessão, no formato de `GET /api/radio/replay/{id}`, com os números da análise;
   - o app do jogo pede um replay por vez, só nos boxes ou com o jogo pausado;
   - relate o tamanho e o tempo de montar. Se a volta inteira passar de 500 KB, proponha uma grade mais grossa.
5. **Sem volta fechada,** a janela diz "nenhuma volta fechada nesta sessão". Ela nunca fica vazia sem explicar.
6. **O botão "Abrir no app":**
   - abre no app do Windows o replay daquela volta e daquela curva, com os 4 visuais e o caminho para a tela Volta;
   - o app do jogo só faz o pedido ao backend local (127.0.0.1), e o backend avisa o app do Windows por um canal que já existe;
   - nada de registrar protocolo no Windows, nada de pacote novo e nada gravado na pasta do jogo;
   - o cartão avisa que o jogo vai para segundo plano. Se o app do Windows estiver fechado, o botão diz isso;
   - relate o que o Windows faz: se o app vem para a frente ou só pisca na barra de tarefas;
   - **se nem a tela Volta nem o cartão da tela Ao vivo abrirem numa volta e numa curva escolhidas,** faça a tela Ao vivo abrir esse replay em tamanho grande.
7. **O app do jogo novo funciona com o backend do 0.5.0 e do 0.6.0:** sem as rotas novas, a janela mostra o replay como hoje, sem erro.

## Parte F — Testes e conferência sem o jogo

1. **Backend:**
   - a Parte B;
   - o resumo (a ordem, as variantes e as unidades), a curva e a causa, a melhor volta e o recorde;
   - a rota das voltas da sessão, com o tamanho e o tempo;
   - o pedido para abrir o app do Windows.
2. **App Lua:** a conferência contra o SDK do CSP (`tools/csp_app/conferir_lua.py`), com as chamadas novas, e o caminho sem as rotas novas.
3. **Front:** os testes, o `tsc` e o build.
4. **Prévias fora do jogo,** por um HTML que repete as contas da janela do jogo:
   - a câmera de antes e a de depois, na C01 (o S do Senna, longa), na C06 e na C12, em 300 × 300, em 420 × 300 e na janela dos boxes;
   - a lista das voltas e a grade de 01/11, com as voltas com rodada.
5. **Ponta a ponta,** com o reprodutor de gravações e as pastas isoladas, como no pedido 43: o botão "Abrir no app" abre a volta e a curva certas. A aba do navegador com "[teste]" no título, fechada no fim.
6. **As suítes** do backend e do front continuam passando.

## Parte G — Teste no jogo (comigo)

Pare aqui. Commite e envie a branch ao GitHub (regra "Cópia no GitHub") e grave o relatório parcial com os passos para mim, com os comandos exatos:

1. fechar o jogo e o app instalado, inclusive o ícone na bandeja;
2. rodar o `instalar.ps1` desta branch, com a versão nova do app do jogo;
3. abrir o app pelo repositório (com a pasta onde ele grava);
4. no jogo, ligar o rádio, o minimapa e o replay;
5. mandar a mensagem de teste e olhar o cartão, que ficou sem confirmação no pedido 43;
6. andar pelo menos 8 voltas eu mesmo, com uma ida aos boxes depois da 3ª volta válida e outra no fim, de pelo menos 1 minuto cada;
7. nos boxes: ver se a janela abriu sozinha, tocar 2 voltas e 2 curvas e apertar "Abrir no app" uma vez;
8. nunca apertar Ctrl+C (ele passa o carro para a IA, e o rádio se cala);
9. desligar o replay por 2 ou 3 voltas e ligar de novo, para o FPS;
10. anotar, numa tabela que o relatório parcial traz pronta, em cada fala: o que eu ouvi, se entendi onde perdi, se entendi por quê e se o replay mostrou;
11. avisar: "testei o rádio e o replay no jogo".

**Diga também** se, depois do teste, o app do jogo novo fica instalado, e se ele funciona com o 0.5.0 instalado.

**Depois do aviso:**

- confira o registro do rádio e os replays entregues;
- leia, sem mudar nada, as linhas `[radio_engenheiro]` do log do CSP;
- meça o FPS com o replay ligado e desligado;
- complete o relatório e a documentação.

## Parte H — Documentação e versão

- **`docs/realidade_aumentada.md`:** o que o rádio diz e em que ordem, a curva e o porquê, a câmera do replay, os boxes e o botão, com a pesquisa do contexto e as fontes.
- **Um ADR novo** (o próximo número livre depois dos do pedido 44): o que o rádio diz, em que ordem e por quê, com a pesquisa.
- **ADR 0021:** uma linha de atualização com a câmera, os boxes e o pedido do app do jogo para abrir o app do Windows.
- **`docs/backlog.md`:** os três itens da Parte B, fechados ou atualizados. O do FPS continua.
- **`docs/app_para_producao.md`:** a linha deste pedido na tabela.
- **`docs/dashboard_inventario.md`:** "O que o pedido 45 entregou", no fim da seção 7.
- **`docs/tecnica_de_pilotagem_lista.md`:** uma linha no histórico.
- **A versão:** `0.7.0-radio-que-ensina` nos 3 pontos, juntos (`desktop/package.json`, `backend/main.py` e `desktop/main.js`), e o app do jogo 0.5.0.

## Regras gerais

- **O coach continua decidindo quando falar.** O foco, o limiar, o limite de 3 por volta e o microssetor de cada frase não mudam.
- **Nenhum modelo nem store muda.** Um critério só muda com a minha decisão (Parte B.1).
- **Não grave na pasta do jogo.** O `instalar.ps1` é rodado por mim (ADR 0020). Em tempo de jogo, o app só grava dentro da pasta dele (ADR 0021).
- **Não instale nem atualize pacotes.** Se algo pedir pacote novo, pare e relate.
- **Não mexa no app instalado.** Os testes usam a pasta isolada.
- **Não gere instalador.** O instalador vem quando eu pedir.
- **Não apague nenhuma gravação** e não copie gravações entre a pasta do app instalado e a do repositório.
- **Nada de marca alheia:** sem logotipo, som ou fonte da F1, do WEC, da FIA ou de equipes.
- **Não contorne nenhuma trava:** se algo parar, pare também e registre o motivo.
- **Janelas de teste** com "[teste]" no título, fechadas no fim.
- **Branch e commits:** branch `etapa/replay-e-radio-que-ensina`, a partir de `develop` depois do merge do pedido 44, commits por parte, merge em `develop`. As branches de outros pedidos não são tocadas.
- **Cópia no GitHub (vale para todo pedido):**
  - depois dos commits de cada parte e antes de cada parada, envie a branch do pedido ao `origin`; depois do merge, envie `develop`;
  - só envios que não reescrevem o remoto (branch nova ou avanço simples). Nunca `--force` nem `--force-with-lease`;
  - `main` e as tags não vão neste pedido;
  - antes do primeiro envio, confira que nada acima de 50 MB, nenhum segredo e nenhuma gravação (`recordings/`, `data/recordings`, `data/ml`) entrou nos commits;
  - depois de cada envio, confira com `git ls-remote origin` que o hash remoto é o mesmo do local;
  - se pedir login, se o envio for recusado ou se o remoto tiver divergido, pare e me avise. Nenhum token ou senha no chat, nos arquivos ou no relatório.
- **Uma sessão de implementação por vez** (ADR 0008). Antes de trocar de branch, confira se outra sessão está ativa.
- **Os tempos de volta** no formato M:SS,mmm.
- **Relatório** em `docs/handoff/2026-11-02_45_replay-de-perto-e-radio-que-ensina_relatorio.md`, como manda o CLAUDE.md, com:
  - a Parte A;
  - os cortes novos e o commit em que foram registrados;
  - a Parte B, antes e depois;
  - o rádio antes e depois nas 4 sessões (C.6);
  - as prévias da câmera e dos boxes;
  - o tamanho e o tempo das rotas;
  - a saída dos testes e os commits;
  - o que foi enviado ao GitHub: a ref, o hash local e o hash no remoto;
  - na parada da Parte G, os passos e a tabela para eu anotar.
- Se algo do contexto não bater com o repositório, pare e registre no relatório.

## Fontes da pesquisa (02/11)

- Autosport, "The secrets of in-race radio chat": https://www.autosport.com/f1/news/the-secrets-of-in-race-radio-chat-5102490/5102490/
- Formula1.com, "FIA clarifies radio transmission restrictions" (2014): https://www.formula1.com/en/latest/article/fia-clarifies-radio-transmission-restrictions.4uSbLsruNnnmXXDqUjh7yV
- RACER, 18/03/2016, sobre o coaching por rádio: https://racer.com/2016/03/18/f1-radio-coaching-intolerable-whiting/
- Coach Dave Academy, "How to use Auto Insights (AI coaching) in Delta": https://coachdaveacademy.com/documentation/how-to-use-auto-insights-ai-coaching-in-delta/
- Trophi.ai, "Mansell", o coach por voz em tempo real: https://www.trophi.ai/sim-racing-features/mansell
- `docs/tecnica_de_pilotagem_pesquisa.md`: as fontes do projeto sobre o feedback no ensino da pilotagem.
