# Pedido 36 — O rádio com as unidades, a freada da IA nos mapas e o replay da curva

**De:** Eduardo. **Data:** 22/10/2026.
**Tipo:** backend (rádio), app Lua do CSP, front (tela Ao vivo) e documentação. Nenhum modelo, store ou critério muda. O coach continua decidindo as frases.

**Quando começar:** agora; o pedido 35 está fechado. Os cuidados de processo da Parte C do pedido 33 valem aqui (janela de teste com "[teste]" e fechada no fim; nenhuma trava do git apagada sem me perguntar).

## Contexto

1. **O teste no jogo de 21/10** (relatório do pedido 35) funcionou: a voz tocou nas 30 mensagens, o registro bate com o caminho fora do tempo real, e os dois mapas custam cerca de 3% do FPS.
2. **O que eu observei andando:**
   - **a voz solta números sem unidade.** "Curva 4: 1,0 por volta. Mínima 102 contra 128." não diz se é segundo, décimo, metro ou km/h. Assim, eu não entendo o que é cada número;
   - **o minimapa (a pista inteira) corta do lado direito;**
   - **quero ver o ponto de freada da IA** no minimapa e no mapa aproximado;
   - **o engenheiro precisa mostrar, e não só falar.** Quando ele diz que passei 8 metros mais à direita, quero ver uma animação com onde eu passei e onde a IA passou;
   - **no geral, faltam representações visuais.**
3. **As minhas decisões sobre o pedido 35:**
   - **a voz fica a 1,4x.** O desvio está aprovado;
   - **a volta com rodada sai da análise** (item da Parte B);
   - **o log de acesso do backend é silenciado** nas rotas pedidas várias vezes por segundo (Parte B);
   - **o CSV de anotações é normalizado** (Parte B);
   - a pasta `recordings/` continua fora do `.gitignore`.

## Parte A — Conferências rápidas

1. **A contagem oficial da M1** depois da rodada de 22/10, com as sessões que contam. A sessão `2026-10-21_20-30-54` deve ser a 5ª; confirme ou diga por que não.
2. **A volta de 1:26,875** (`2026-10-21_20-30-54#0017`), que virou a sua melhor:
   - o `tyres_out` e o `off_track` dela, como foi feito com a volta de 1:27,594 no pedido 32;
   - a fração fora do corredor, só para registro.

   Nenhuma regra muda. Se houver sinal de corte de pista, relate; a decisão é minha.

## Parte B — As decisões do pedido 35

1. **A voz a 1,4x:** registre a decisão em `docs/realidade_aumentada.md` e no relatório do pedido 35 (seção "Desvios"), como aprovada em 22/10.
2. **A volta com rodada:**
   - a volta em que uma curva perde mais de 5 s contra a referência não conta para a análise das voltas;
   - o resumo dessa volta diz o tempo e a diferença, sem citar a curva;
   - o coach, o store e as regras de volta válida do store não mudam. É uma regra só do rádio;
   - escreva a regra em `docs/realidade_aumentada.md` e numa linha de atualização no ADR 0021;
   - teste: a volta 5 de 21/10 (26,5 s na C12) sai da primeira análise, e a análise passa a usar a volta válida seguinte.
3. **O log de acesso:**
   - silencie o registro de acesso das rotas que a tela Ao vivo e o app do jogo pedem várias vezes por segundo (os pontos novos da volta e as mensagens do rádio);
   - os erros e as outras rotas continuam no log;
   - relate quanto o log cresce por hora, antes e depois, numa reprodução de gravação.
   - **O arquivo de 3,8 GB que já existe** não é apagado. Diga só o tamanho dele compactado; a decisão de apagar é minha.
4. **O CSV de anotações** (`docs/experimentos/anotacoes_de_sessao.csv`):
   - normalize o fim de linha para o que a maioria das linhas usa, sem mudar nenhum conteúdo;
   - confira que todos os leitores do arquivo (o `atualizar_coach`, o botão do app e os testes) leem as mesmas linhas antes e depois.

## Parte C — As unidades na voz e no cartão

1. **Todo número falado tem a sua unidade:**
   - **o tempo perdido:**
     - abaixo de 1 s, em décimos: "4 décimos";
     - de 1 s para cima, em segundos, com uma casa: "1,2 segundo", "2,5 segundos";
   - **o tempo da volta:** "1 minuto e 29,1 segundos";
   - **a diferença da volta:** "4,2 segundos atrás da IA";
   - **a distância:** "46 metros", "1,8 metro";
   - **a velocidade:** em quilômetros por hora. Quando dois números aparecem juntos, a unidade pode vir uma vez só, no fim, se ficar claro: "mínima de 102 contra 128 quilômetros por hora".
2. **Exemplos do que eu quero ouvir:**
   - "Curva 11: 1,2 segundo atrás da IA. Mínima de 64 contra 94 quilômetros por hora."
   - "Volta 8: 4,2 segundos atrás da IA. Mais perdeu na curva 1: 7 décimos."
   - "Curva 4: perde 1,0 segundo por volta. Freia 46 metros antes da IA."
3. **Para caber na janela:**
   - a unidade nunca sai da fala;
   - se não couber, sai primeiro a segunda causa, depois a primeira, como nas variantes que já existem;
   - relate, nas sessões de 13/10, 18/10 e 21/10, quantas mensagens perderam a causa por causa das unidades, antes e depois.
4. **O cartão** mostra as mesmas unidades, com os números completos (s, m e km/h).
5. **Testes:** todo número de toda fala tem a unidade logo depois, em todos os tipos de mensagem.

## Parte D — O minimapa e a freada da IA nos mapas

1. **O minimapa que corta à direita:**
   - ache a causa: a conta do encaixe, a margem, os contornos novos do asfalto tratado, o nome das curvas ou a janela que não é quadrada;
   - a pista inteira e os nomes cabem, com margem, em todos os tamanhos da janela (de 200 a 640) e numa janela mais larga que alta, ou mais alta que larga;
   - se houver captura minha do jogo no repositório, use-a; senão, mostre a prévia nos tamanhos 200, 300 e 640.
2. **O ponto de freada da IA:**
   - **a regra:** o começo da freada da volta de referência em cada curva, pela mesma regra do relatório de evolução (a janela de frenagem do pedido 17). Nada de conta nova;
   - **no minimapa:** só a freada da próxima curva, como uma marca curta atravessando a pista, na cor do fantasma. Com 14 curvas, mais que isso polui;
   - **no mapa aproximado:** a freada da IA em todas as curvas que estiverem na janela, como uma linha atravessando o asfalto, com o rótulo "freada da IA". O seu traçado, pintado pelo pedal, já mostra onde você freou: o vermelho começa ali;
   - os pontos vêm com a referência, na rota do minimapa, uma vez por referência.

## Parte E — O replay da curva: o engenheiro mostra o que diz

**O que é:** uma animação curta da curva citada pelo rádio, vista de cima, sobre a pista tratada (asfalto, pintura e zebras):

1. **O que mostra:**
   - **duas linhas:** onde você passou e onde a IA passou. O texto diz "você" e "IA (referência)", nunca "onde devia passar": é uma diferença medida contra uma volta real (ADR 0012);
   - **dois carros andando** sobre as linhas, cada um no seu próprio tempo, a partir da mesma entrada da curva. A diferença de tempo aparece sozinha, no quanto a IA abre;
   - **as duas freadas,** com a distância entre elas em metros;
   - **as duas mínimas,** no ponto de cada uma, com o valor em km/h;
   - **o traçado:** no ponto da mínima da IA, uma seta entre as duas linhas com a distância em metros e o lado por extenso (ADR 0003);
   - **o tempo perdido na curva,** com a unidade.
2. **Qual volta sua:** uma volta real, e não uma média. Na análise, é a volta das 3 cuja perda na curva fica mais perto da mediana. Na frase do coach, é a volta em que a frase saiu.
3. **De onde vêm os dados:** a volta ao vivo que o backend já guarda (a lateral, o relógio e o pedal na grade oficial) e a volta de referência, com as posições montadas na geometria oficial, como o traçado da tela Volta. Nada de física nova.
4. **No jogo:**
   - **uma janela nova do app,** "Replay da curva", separada das outras na barra de apps;
   - **na reta:** ela aparece junto com a fala de uma análise ou de uma frase do coach com causa, toca a animação de cada curva citada e some quando a janela de rádio acaba. Nunca aparece dentro das 14 curvas;
   - **nos boxes ou com o jogo pausado:** a última análise fica disponível, maior e em repetição, até você sair. Confira na `lib.lua` como saber que o carro está nos boxes;
   - **o desenho:** a imagem da pista que o app já tem (`pista_detalhada.png`), recortada e girada na curva, com as linhas e os carros por cima;
   - **o custo:** meça o FPS com a janela ligada e desligada, como no pedido 35.
5. **No app,** na tela Ao vivo: o cartão da análise e o da frase com causa ganham a mesma animação, com um botão de repetir.
6. **A rota:** uma rota entrega os dados do replay de cada mensagem, uma vez por mensagem, com a versão na mensagem, como o minimapa.

**Outras representações visuais:** proponha no relatório, sem implementar, outras formas de mostrar o que o rádio diz (por exemplo, no cartão do resumo ou na frase do coach), com um esboço de cada uma.

## Parte F — Testes e conferência sem o jogo

1. **Backend:**
   - as unidades em todas as falas (Parte C.5);
   - a volta com rodada fora da análise (Parte B.2);
   - a freada da IA por curva, contra o relatório de evolução;
   - a escolha da volta do replay (a mais perto da mediana);
   - as rotas novas e o log silenciado.
2. **App Lua:** a conferência contra o SDK do CSP (`tools/csp_app/conferir_lua.py`), com as chamadas novas.
3. **Front:** os testes da tela Ao vivo e da tela Volta.
4. **Conferência nas sessões de 13/10, 18/10 e 21/10,** fora do tempo real:
   - as falas novas, com a duração e a janela em que caem;
   - as mensagens que perderam a causa (Parte C.3).
5. **Prévias fora do jogo:**
   - o minimapa nos tamanhos da Parte D.1, com a marca de freada;
   - o mapa aproximado com a linha de freada da IA;
   - **o replay de 3 curvas reais de 21/10,** incluindo a C01 da segunda análise (o traçado 7,9 m mais à direita). Diga se esses 7,9 m batem com as duas linhas desenhadas.
6. **As suítes:** a do backend e os testes do front continuam passando.

## Parte G — Teste no jogo (comigo)

Pare aqui. Grave o relatório parcial com os passos para mim, com os comandos exatos, como no pedido 35:

1. fechar o jogo e o app instalado;
2. rodar o `instalar.ps1` de novo;
3. abrir o app pelo repositório;
4. no jogo, ligar as quatro janelas: rádio, minimapa, mapa aproximado e replay da curva;
5. mandar a mensagem de teste;
6. andar pelo menos 8 voltas sem a IA, com uma ida aos boxes no meio, para ver o replay grande;
7. avisar: "testei o rádio com o replay no jogo".

**Depois do aviso:**

- confira o registro do rádio, as unidades e os replays entregues;
- leia, sem mudar nada, as linhas `[radio_engenheiro]` do log do CSP;
- meça o FPS com cada janela;
- complete o relatório e `docs/realidade_aumentada.md`.

## Parte H — Documentação

- **`docs/realidade_aumentada.md`:**
  - as unidades e os exemplos;
  - a regra da volta com rodada;
  - a freada da IA nos mapas;
  - o replay da curva: o que mostra, de onde vem cada dado, quando aparece e o custo medido.
- **ADR 0021:** uma linha de atualização com a janela do replay, as marcas de freada e a regra da volta com rodada.
- **`docs/dashboard_inventario.md`:** o que este pedido entregou, no fim da seção 7.

## Regras gerais

- **O coach continua decidindo as frases.** O foco, o limiar e o limite de 3 por volta não mudam.
- **Nenhum modelo, store ou critério muda.** A regra da volta com rodada é só do rádio.
- **Não grave na pasta do jogo.** Os scripts são rodados por mim. Em tempo de jogo, o app só grava dentro da pasta dele (ADR 0021).
- **Não instale nem atualize pacotes.** Se algo pedir pacote novo, pare e relate.
- **Não mexa no app instalado.** Os testes usam a pasta isolada.
- **Não apague o log de 3,8 GB nem nenhuma gravação.**
- **Não gere instalador.** Ele vem depois deste teste no jogo.
- **Nada de marca alheia:** sem logotipo, som ou fonte da F1, do WEC, da FIA ou de equipes.
- **Não contorne nenhuma trava:** se algo parar, pare também e registre o motivo.
- **Janelas de teste** com "[teste]" no título, fechadas no fim.
- **Branch e commits:** branch `etapa/radio-unidades-e-replay`, commits por parte, merge em `develop`. Sem push.
- **Uma sessão de implementação por vez** (ADR 0008).
- **Relatório** em `docs/handoff/2026-10-22_36_radio-com-unidades-e-replay-da-curva_relatorio.md`, como manda o CLAUDE.md, com:
  - a Parte A;
  - as falas novas, com exemplos reais e o antes e depois do que cabe;
  - a causa do corte no minimapa e as prévias;
  - o replay: as prévias e a conferência dos 7,9 m;
  - as propostas de outras representações visuais;
  - a saída dos testes e os commits;
  - na parada da Parte G, os passos para mim.
- Se algo do contexto não bater com o repositório, pare e registre no relatório.
