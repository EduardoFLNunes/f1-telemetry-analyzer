# Pedido 43 — Os 4 visuais do rádio e os números da voz no replay

**De:** Eduardo. **Data:** 29/10/2026.
**Tipo:** backend (a rota do replay), app Lua do CSP (a janela "Replay da curva"), front (tela Ao vivo) e documentação. Nenhum modelo, store, critério ou frase do coach muda.

**Quando começar:** depois do merge do pedido 39 em `develop`. Se o pedido 38 estiver pronto para a H.4 ao mesmo tempo, ele vai primeiro. Antes de criar a branch, confira que nenhuma outra sessão está ativa na pasta (ADR 0008).

## Contexto

1. **O replay da curva** existe desde o pedido 36 (`backend/core/radio/replay.py`, a rota `GET /api/radio/replay/{id}`, a janela "Replay da curva" do app do jogo e a animação na tela Ao vivo).
2. **O relatório do pedido 36 propôs 4 visuais,** sem implementar (seção "Outras representações visuais"). **Eu escolhi os 4:**
   1. a velocidade ao longo da curva;
   2. a diferença acumulada dentro da curva;
   3. a faixa do pedal sincronizada;
   4. a grade da sessão.
3. **O achado de 22/10** (fechamento do pedido 36, item 4): na frase do coach, a voz e o replay não dizem o mesmo número. Na C12 da volta 2 de 21/10:

   | | a voz e o cartão (o coach) | o replay |
   |---|---|---|
   | o que mede | o microssetor 44 (cerca de 70 m) | a curva C12 inteira |
   | freada | "Freia 16 metros antes da IA" | "você freia 56 m antes da IA" |
   | mínimas | a sua 101, a da IA 145 km/h | 90 e 98 km/h |
   | tempo | +0,64 s no microssetor | perde 0,92 s nesta curva |

   Na análise das voltas, os dois usam a mesma medida (os 7,9 m da C01 batiam).
4. **A minha decisão (29/10):** no replay de uma frase do coach, **os rótulos mostram os números da voz.** As linhas e os carros continuam os da curva inteira. Eu tenho de ver no replay o que acabei de ouvir.
5. **As versões:** o app do jogo 0.4.1 está em `develop` e instalado no jogo. O app 0.5.0-radio-e-replay está instalado no Windows e vai continuar sendo usado nas minhas sessões (IA em níveis, avaliação do aprendizado).

## Parte A — Conferências (só leitura)

1. **Os caminhos do contexto:** confirme os arquivos do replay no backend, na janela do app do jogo e na tela Ao vivo (incluindo o `QuadroDeRotulos`). Se algum não estiver onde o contexto diz, registre.
2. **O antes:** reproduza, com o código de hoje, a frase do coach da C12 da volta 2 de 21/10 e o replay dela, e anote os números da tabela do contexto.
3. **O que a frase do coach carrega:** os números (freada, mínimas, tempo, traçado) e se ela tem também os pontos da pista onde cada um foi medido. Se só tiver os números, diga como a Parte B vai achar os pontos, pela mesma regra do coach.
4. **As grades que o rádio já tem,** na volta ao vivo e na volta de referência: velocidade, relógio, freio, acelerador e lateral, na grade oficial. Os visuais 1 a 3 precisam de velocidade, tempo e pedal pela distância dentro da curva, nas duas voltas. Se faltar alguma, relate; nada de física nova e nada de modelo.

## Parte B — Os números da voz no replay da frase do coach

1. **Todo número escrito no replay de uma frase do coach é o número da voz,** com a mesma unidade e o mesmo arredondamento do cartão: a freada, as mínimas, o traçado e o tempo. A fonte é a mensagem do coach, e não uma conta nova.
2. **As marcas acompanham o rótulo:**
   - as duas freadas e a distância entre elas medem os metros do rótulo;
   - as duas mínimas ficam onde o coach as mediu;
   - a seta do traçado fica no ponto onde o coach mediu o lado.

   Se o coach não guarda esses pontos, ache-os pela mesma regra que ele usa, no mesmo microssetor e com os mesmos dados. Se não der, pare nesse item e proponha; não invente um ponto.
3. **O trecho da voz:** no replay de uma frase do coach, o microssetor que a voz mediu aparece na pista como uma faixa clara, com o rótulo "trecho da fala". As linhas e os carros continuam os da curva inteira.
4. **Na análise das voltas, nada muda:** a fala e o replay já usam a mesma medida.
5. **O teste:** em todas as mensagens com replay (análise e frase do coach) das sessões de 13/10, 18/10 e 21/10, fora do tempo real, todo número escrito nos rótulos do replay aparece na fala, com a unidade. Relate quantos replays tinham um rótulo com outro número antes e depois.

## Parte C — Os 4 visuais

**Regras para os 4:**

- **Os dados:** só o que o backend já tem para o replay (a volta ao vivo e a volta de referência, na grade oficial). Os visuais 1 a 3 vêm na mesma rota do replay, uma vez por mensagem.
- **O texto** diz "você" e "IA (referência)" (ADR 0012), com as cores que o replay já usa.
- **Todo número tem a unidade** (regra do pedido 36).
- **No replay de uma frase do coach,** vale a Parte B: o único número escrito é o da voz, e o trecho da fala aparece também nos visuais 1 a 3.
- **No jogo,** os visuais ficam dentro da janela "Replay da curva": aparecem e somem com ela, e nunca dentro das 14 curvas.
- **O app do jogo novo funciona com o backend do 0.5.0 instalado:** se a rota não trouxer os campos novos, a janela mostra o replay como hoje, sem erro.

### C.1 A velocidade ao longo da curva

- As duas velocidades pela distância, da entrada à saída do replay, em km/h, com o eixo em metros.
- As duas freadas e as duas mínimas marcadas.
- Um cursor que anda junto com os carros do replay.
- **Onde:** sob a animação, na janela do jogo e no cartão da tela Ao vivo.

### C.2 A diferença acumulada dentro da curva

- Uma linha que começa em zero na entrada do replay, sobe quando eu perco e desce quando eu ganho.
- As separações na freada, na mínima e na saída, para mostrar onde o tempo foi embora.
- **Na análise:** o fim da linha é o "perde X s nesta curva" do replay.
- **Na frase do coach:** a subida dentro do trecho da fala é o tempo que a voz disse, dentro do arredondamento da voz. Relate a diferença em cada mensagem; se não bater, explique por quê, sem ajustar o número.
- **Onde:** sob a animação, junto com a C.1.

### C.3 A faixa do pedal sincronizada

- Duas faixas pela distância, uma para mim e outra para a IA: o freio, o acelerador parcial e o acelerador cheio, cada um com a sua cor.
- **A regra das cores:** a mesma do traçado pintado pelo pedal no mapa aproximado. Nada de limiar novo.
- As faixas andam com os carros, pelo mesmo cursor da C.1.
- **Onde:** sob a animação, na janela do jogo e no cartão da tela Ao vivo.

### C.4 A grade da sessão

- Uma tabela: as voltas válidas da sessão nas linhas e as 14 curvas nas colunas. Cada célula tem a perda na curva, em segundos, e a cor pela perda: uma cor para perda e outra para ganho, mais forte quanto maior.
- **A perda é a mesma da análise das voltas.** A célula da curva citada, na volta citada, tem o número que a análise usou.
- As curvas citadas pelo rádio ficam marcadas na volta em que foram citadas. Assim, eu vejo se a curva melhorou nas voltas seguintes.
- As voltas da IA, as inválidas e as que saíram da análise por rodada ficam fora, com o motivo.
- **Onde:**
  - na tela Ao vivo, sob os cartões do rádio, atualizada a cada volta;
  - no jogo, só nos boxes ou com o jogo pausado, na janela "Replay da curva" grande, com as últimas 8 voltas.

**Quando a janela do jogo for pequena:** proponha e relate o que sai primeiro. A minha ordem de importância é: o replay, a faixa do pedal, a diferença acumulada e a velocidade.

## Parte D — Testes e conferência sem o jogo

1. **Backend:**
   - os números da voz no replay (Parte B.5);
   - os dados dos visuais 1 a 3 na rota;
   - a grade da sessão contra os números de cada análise;
   - o tamanho da rota, antes (cerca de 8 KB numa frase e 20 KB numa análise) e depois. Se uma análise passar de 60 KB, proponha uma grade mais grossa para os visuais;
   - o tempo para montar a rota, antes e depois.
2. **App Lua:** a conferência contra o SDK do CSP (`tools/csp_app/conferir_lua.py`), com as chamadas novas, e o caminho sem os campos novos (o backend do 0.5.0).
3. **Front:** os testes da tela Ao vivo, o `tsc` e o build.
4. **Prévias fora do jogo,** por um HTML que repete as contas da janela do jogo, como no pedido 36:
   - a C12 da volta 2 de 21/10 (a frase do coach), antes e depois;
   - a C01 da segunda análise de 21/10 (volta 17) e a C10 (volta 16);
   - a grade da sessão de 21/10, na tela Ao vivo e na janela grande do jogo;
   - a janela do jogo em 300 × 300 e na janela grande dos boxes (1,6 vez maior).
5. **A tela Ao vivo, ponta a ponta,** com o reprodutor de gravações e as pastas isoladas, como no item 4 do fechamento do pedido 36. A aba do navegador com "[teste]" no título, fechada no fim.
6. **As suítes:** a do backend e a do front continuam passando.

## Parte E — Teste no jogo (comigo)

Pare aqui. Commite e envie a branch ao GitHub (regra "Cópia no GitHub"), e grave o relatório parcial com os passos para mim, com os comandos exatos:

1. fechar o jogo e o app instalado, inclusive o ícone na bandeja;
2. rodar o `instalar.ps1` desta branch, com a versão nova do app do jogo;
3. abrir o app pelo repositório (com a pasta onde ele grava);
4. no jogo, ligar as 4 janelas;
5. mandar a mensagem de teste;
6. andar pelo menos 8 voltas eu mesmo, com uma ida aos boxes depois da 3ª volta válida, para ver a grade;
7. nunca apertar Ctrl+C (ele passa o carro para a IA, e o rádio se cala);
8. desligar o replay por 2 ou 3 voltas e ligar de novo, para o FPS;
9. anotar, em cada fala, se os números do replay são os que eu ouvi e se os visuais mostram a curva certa;
10. avisar: "testei os visuais no jogo".

**Diga também** se, depois do teste, o app do jogo novo fica instalado, e que ele funciona com o 0.5.0 instalado (Parte C).

**Depois do aviso:**

- confira o registro do rádio e os replays entregues;
- leia, sem mudar nada, as linhas `[radio_engenheiro]` do log do CSP;
- meça o FPS com o replay ligado e desligado;
- complete o relatório e a documentação.

## Parte F — Documentação

- **`docs/realidade_aumentada.md`,** na seção do replay da curva:
  - a regra dos números da voz no replay da frase do coach e o trecho da fala;
  - os 4 visuais: o que cada um mostra, de onde vem cada dado, onde aparece e o custo medido.
- **ADR 0021:** uma linha de atualização com a regra dos números da voz e os 4 visuais.
- **`docs/dashboard_inventario.md`:** "O que o pedido 43 entregou", no fim da seção 7.
- **`docs/tecnica_de_pilotagem_lista.md`:**
  - a linha D3 passa a citar o pedido 43;
  - uma linha no histórico com a decisão de 29/10 e o que este pedido entregou.

## Regras gerais

- **O coach continua decidindo as frases.** O foco, o limiar, o limite de 3 por volta e o microssetor de cada frase não mudam.
- **Nenhum modelo, store ou critério muda.** A regra dos números da voz é só do replay.
- **Não grave na pasta do jogo.** O `instalar.ps1` é rodado por mim (ADR 0020). Em tempo de jogo, o app só grava dentro da pasta dele (ADR 0021).
- **Não instale nem atualize pacotes.** Se algo pedir pacote novo, pare e relate.
- **Não mexa no app instalado.** Os testes usam a pasta isolada.
- **Não gere instalador.** O instalador final vem no fim do desenvolvimento.
- **Não apague nenhuma gravação** e não copie gravações entre a pasta do app instalado e a do repositório.
- **Nada de marca alheia:** sem logotipo, som ou fonte da F1, do WEC, da FIA ou de equipes.
- **Não contorne nenhuma trava:** se algo parar, pare também e registre o motivo.
- **Janelas de teste** com "[teste]" no título, fechadas no fim.
- **Branch e commits:** branch `etapa/visuais-do-radio`, a partir de `develop`, commits por parte, merge em `develop`. As branches dos pedidos 38 e 39 não são tocadas.
- **Cópia no GitHub (vale para todo pedido):**
  - depois dos commits de cada parte e antes de cada parada, envie a branch do pedido ao `origin`; depois do merge, envie `develop`;
  - só envios que não reescrevem o remoto (branch nova ou avanço simples). Nunca `--force` nem `--force-with-lease`;
  - `main` e as tags não vão neste pedido;
  - antes do primeiro envio, confira que nada acima de 50 MB, nenhum segredo e nenhuma gravação (`recordings/`, `data/recordings`, `data/ml`) entrou nos commits;
  - depois de cada envio, confira com `git ls-remote origin` que o hash remoto é o mesmo do local;
  - se pedir login, se o envio for recusado ou se o remoto tiver divergido, pare e me avise. Nenhum token ou senha no chat, nos arquivos ou no relatório.
- **Uma sessão de implementação por vez** (ADR 0008). Antes de trocar de branch, confira se outra sessão está ativa.
- **Os tempos de volta** no formato M:SS,mmm.
- **Relatório** em `docs/handoff/2026-10-29_43_visuais-do-radio_relatorio.md`, como manda o CLAUDE.md, com:
  - a Parte A;
  - o antes e o depois da C12 da volta 2 de 21/10;
  - a contagem da Parte B.5;
  - as prévias dos 4 visuais;
  - o tamanho e o tempo da rota;
  - a saída dos testes e os commits;
  - o que foi enviado ao GitHub: a ref, o hash local e o hash no remoto;
  - na parada da Parte E, os passos para mim.
- Se algo do contexto não bater com o repositório, pare e registre no relatório.
