# Pedido 35 — O rádio que analisa as voltas, a voz no jogo, o mapa ao vivo sem travar e o minimapa no jogo

**De:** Eduardo. **Data:** 18/10/2026.
**Tipo:** backend (rádio), app Lua do CSP, front (tela Ao vivo) e documentação. Nenhum modelo, store ou critério muda. O coach continua decidindo as frases.

**Ao mandar executar este pedido, eu aprovo o ADR 0021** (`docs/prompts/anexos-35/0021-radio-que-analisa-as-voltas-e-minimapa.md`).

**Quando começar:** depois que o pedido 34 fechar (ADR 0008). Os cuidados de processo da Parte C do pedido 33 valem aqui.

## Contexto

1. **O teste no jogo de 18/10** (das 12:38 às 13:08), pelo registro `data/radio/2026-10-18_12-38-44_vhe_interlagos.jsonl`:
   - **19 mensagens:** 4 de teste, 13 resumos na linha e só 2 frases do coach (C11 na volta 4 e C08 na volta 10), em 15 voltas;
   - **no jogo, não vi o cartão nem ouvi a voz.** As mensagens apareceram só no app;
   - **a causa provável:** a conferência da API calava o app do jogo. Ela foi corrigida depois do teste, em `7904758f` e `416ae3f7` (relatório do pedido 33). **A cópia instalada no jogo ainda é a de antes da correção;**
   - **a voz pela URL** (`ui.MediaPlayer` com `setSource` na URL do backend) nunca rodou com o app ligado. Ela continua sem confirmação.
2. **O que eu quero do rádio,** depois do teste:
   - **hoje ele só fala o tempo da volta e a diferença para a IA.** Ele não diz onde estou perdendo tempo nem o que faço diferente da IA;
   - **ele tem de analisar algumas voltas minhas** e dizer onde perco tempo, em voz e na tela do jogo.
3. **Por que hoje ele só fala o tempo,** pelo registro e pelo código:
   - **o coach fala pouco:** só nos 3 trechos de foco, uma frase por trecho e só acima do limiar (seção 9 de `docs/coach_aprendizado.md`). Em 15 voltas, foram 2 frases;
   - **o resumo na linha** só tem o tempo e a diferença (`mensagem_de_resumo`, em `core/radio/texto.py`);
   - **a fala da frase do coach perde a causa:** o cartão tinha "mínima da IA 94 km/h, a sua 64 km/h", mas a voz disse só "Curva 11, esquerda: 1,25 atrás da IA."
4. **O mapa ao vivo trava** quando estou gravando. Pelo código (`aoVivo/FantasmaAoVivo.tsx`):
   - a tela pede `/api/live/volta` a cada 300 ms e recebe a volta inteira, com 5 linhas de 2.167 pontos;
   - a cada resposta, ela remonta a volta, recalcula o traçado e redesenha a pista inteira (asfalto, pintura e zebras);
   - o carro só anda 3 vezes por segundo. A 250 km/h, são saltos de uns 20 m.
5. **O minimapa no jogo:** quero ver dentro do jogo um minimapa comparando a minha volta com a da IA. Antes disso, o mapa ao vivo tem de ficar leve.
6. **O gravador nas sessões mais recentes** (pedido 33, A.3):
   - a sessão de 18/10 tem mais amostras repetidas (3,98%) e mais buracos que as do 0.3.0 (cerca de 1,5%);
   - a causa não ficou estabelecida;
   - com a tela Ao vivo e o rádio, o backend faz mais coisas a cada quadro. **O que este pedido fizer não pode piorar a gravação,** que é o dado da M1.

## Parte A — Fechar o pedido 31 e entender o teste de 18/10

1. **Feche o relatório do pedido 31** com o teste de 18/10, na seção da Parte F:
   - o que aconteceu no jogo;
   - as duas correções do app;
   - o registro do rádio contra as frases do coach.
2. **Passe a sessão `2026-10-18_12-38-44` pelo coach,** fora do tempo real, como na Parte E.2 do pedido 31. Relate:
   - quantas frases o coach daria e quantas chegaram ao registro (2);
   - o foco de cada volta, os 3 microssetores;
   - por que o coach ficou calado nas outras voltas: abaixo do limiar, fora do foco, volta inválida ou outro motivo.
3. **Se o caminho ao vivo perdeu frases** (o coach, a fila do rádio, as janelas ou a pista), ache onde. Corrija só se for defeito de código, com teste. Nenhuma regra do coach muda.

## Parte B — A voz e o cartão no jogo

1. **Confira na `lib.lua` instalada:**
   - como o `ui.MediaPlayer` e o `ac.AudioEvent` carregam o som (URL, caminho de arquivo);
   - de que pastas o app do jogo pode ler e em quais pode gravar.
2. **A voz tem três caminhos, um depois do outro:**
   1. pela URL do backend, como hoje;
   2. pelo caminho do arquivo que o backend já grava em `data/radio/audio/`, se a API deixar o app ler fora da pasta dele;
   3. baixando o áudio com `web.get` e guardando-o **só dentro da pasta do app**, numa subpasta que o próprio app limpa ao abrir (ADR 0021, item 6).

   O app passa ao caminho seguinte quando o anterior não toca, e guarda o que funcionou.
3. **Uma linha no log do CSP por mensagem:** `[radio_engenheiro] voz: <caminho> tocou` ou `falhou: <motivo>`.
4. **O volume do rádio** fica numa constante no começo do arquivo, explicada num comentário.
5. **Os scripts:** o `instalar.ps1` sobrescreve só a pasta do app, e eu rodo de novo.

## Parte C — O que o rádio diz (ADR 0021)

1. **A frase do coach com a causa na voz.**
   - Exemplo: "Curva 11, esquerda: 1,25 atrás da IA. Mínima 64 contra 94."
   - **A regra da causa principal,** por exemplo:
     - a freada, quando a diferença do ponto de freada passa de um corte;
     - senão, a mínima, quando a diferença passa de outro corte.

     Escolha os cortes, diga por quê e escreva a regra no documento.
   - A fala fica em até cerca de 6 s.
2. **A análise das voltas,** o tipo novo:
   - **quando:** a cada 3 voltas válidas da sessão, sobre essas 3;
   - **as curvas:**
     - até 2 curvas (C01 a C14), com a maior perda mediana contra a referência escolhida na Coleta;
     - só entra uma curva perdida em pelo menos 2 das 3 voltas;
   - **o que difere em cada curva,** pelas medidas:
     - o ponto de freada (m);
     - a mínima (km/h);
     - a volta ao acelerador cheio (m);
     - o traçado: a posição lateral no ponto da mínima da referência, em metros e com o lado por extenso (ADR 0003);
   - **o que vai na fala:** as diferenças que mais pesam, uma ou duas por curva. A fala fica em até cerca de 8 s;
   - **o cartão** mostra as curvas com todos os números;
   - **o que já existe e o que é novo:**
     - a freada e a mínima já estão no `evidence` do coach;
     - se o acelerador e o traçado não estiverem prontos ao vivo, monte-os com os canais da grade que o coach já projeta, sem conta de física nova, e relate a regra;
   - **a forma:** sempre a diferença medida contra uma volta real, nunca um ganho prometido (ADR 0012).

     Exemplo do tipo de frase: "Análise das voltas 6 a 8: na Curva 12 você perde 0,9 por volta. Freia 50 metros antes da IA e passa a 80 contra 145."
3. **O resumo na linha** passa a dizer também a curva em que a volta mais perdeu, com a perda. A fala fica em até cerca de 7 s.
4. **Quando cada mensagem é entregue:**
   - as janelas de rádio continuam as mesmas (723 a 1.192 m, 1.637 a 1.818 m e 3.697 a 104 m);
   - a análise vai na primeira janela em que a fala inteira cabe, pela velocidade do carro;
   - nada é dito dentro das 14 curvas;
   - relate, numa sessão real, quanto tempo cada tipo de fala ocupa e em que janela cai.
5. **O que não muda:** as frases do coach (o foco, o limiar e no máximo 3 por volta). A análise é no máximo uma a cada 3 voltas válidas.
6. **O registro** de cada análise, em `data/radio/<sessão>.jsonl`:
   - as voltas analisadas;
   - as curvas, com a perda em cada uma das 3 voltas;
   - as diferenças ditas;
   - a referência.

   Isso deve bastar para medir depois se a curva citada melhorou nas 3 voltas seguintes. Diga se basta.
7. **A tela Ao vivo** mostra a análise como as outras mensagens, com o texto pronto do backend.

## Parte D — O mapa ao vivo sem travar

1. **Meça antes de mudar:**
   - quantas vezes por segundo o mapa é desenhado;
   - quantas vezes por segundo o carro muda de lugar;
   - o tamanho e o tempo de cada resposta de `/api/live/volta`;
   - o tempo de processador do backend por resposta.

   **Sem o jogo:** use uma gravação real, tocada em tempo real no mesmo caminho ao vivo. Se não houver como fazer isso hoje, crie uma ferramenta só de teste que alimente o barramento com a gravação, sem mudar o caminho ao vivo, e use a pasta isolada.
2. **O que tem de mudar:**
   - **o carro anda liso:**
     - o mapa é desenhado a cada quadro da tela;
     - o carro recebe posição nova pelo menos 20 vezes por segundo, pelo WebSocket que já existe ou por uma rota só com os pontos novos;
     - entre duas posições, a tela leva o carro pela geometria oficial, na velocidade dele. Isso é só desenho; a posição continua sendo a projeção do coach;
   - **só os pontos novos** chegam a cada atualização. A volta inteira vem só na abertura da tela ou numa volta nova;
   - **a pista é desenhada uma vez** (asfalto, pintura e zebras) e reaproveitada. Ela só é redesenhada quando o zoom ou o tamanho mudam;
   - **a tela não refaz os componentes do React a cada amostra.**
3. **Meça depois,** com as mesmas medidas, numa tabela de antes e depois.
4. **A tela Volta continua igual:** o mesmo componente, o mesmo replay e os mesmos testes.
5. **A gravação não pode piorar.** No teste no jogo (Parte G), compare as amostras repetidas, os buracos de 50 ms ou mais e o p99 do relógio do gravador (as medidas do pedido 33):
   - nas voltas com a tela Ao vivo aberta;
   - nas voltas com outra tela.

## Parte E — O minimapa no jogo (ADR 0021)

1. **Confira na `lib.lua` instalada:**
   - a posição do carro e o tempo da volta;
   - um jeito de desenhar a pista uma vez e reaproveitar, por exemplo um canvas guardado, se a API tiver.
2. **O que o minimapa mostra,** numa janela 2D do app do jogo, num canto, sem cobrir o centro da tela:
   - **a pista tratada:** o contorno do asfalto do cache, simplificado para poucas centenas de pontos e desenhado uma vez;
   - **o carro:** a posição vem do próprio jogo, a cada quadro, sem pedir nada ao backend;
   - **o fantasma da referência escolhida na Coleta:**
     - ele é posicionado pelo tempo da volta;
     - a volta de referência (posição e tempo) é baixada do backend uma vez, quando o app abre ou a referência muda;
     - a linha do jogo fica 1,463 m depois do s = 0 (pedido 33). Diga como o relógio da volta do jogo e o da referência foram alinhados;
   - **a diferença ao vivo,** em segundos, com sinal. Ela pode vir do backend ou ser calculada no app; diga qual e por quê;
   - **as curvas da última análise,** marcadas no contorno.
3. **As cores** são as da tela Volta: o carro como "você" e o fantasma como "fantasma". Nada de marca alheia.
4. **Uma rota nova** entrega a pista simplificada e a volta de referência para o app do jogo.
5. **Com o backend fora do ar,** o minimapa mostra a pista e o carro e avisa, discreto, que não há fantasma.
6. **O minimapa liga e desliga sozinho** na barra de apps do jogo, separado do cartão do rádio.
7. **O custo no jogo:**
   - meça o FPS do jogo com o minimapa ligado e desligado, com o que a API tiver;
   - se a API não tiver como medir, deixe os passos para eu ler o contador de FPS do jogo.

## Parte F — Testes e conferência sem o jogo

1. **Testes do backend:**
   - a frase do coach com a causa: os dois casos e o corte;
   - a análise:
     - a cada 3 voltas válidas;
     - só curvas perdidas em 2 de 3;
     - no máximo 2 curvas;
     - o texto com número com vírgula e lado por extenso;
   - o resumo com a curva de maior perda;
   - o limite do coach continua em 3 frases por volta;
   - a janela: a análise espera uma janela em que caiba;
   - as rotas novas, a de pontos novos e a do minimapa;
   - o registro da análise.
2. **App Lua:** a conferência de sintaxe (`tools/csp_app/conferir_lua.py`), com a lista de chamadas da API que o app usa.
3. **Front:** os testes do mapa ao vivo e da tela Volta.
4. **Conferência em gravações reais:** passe as sessões de 13/10 e de 18/10 pelo rádio novo, fora do tempo real. Relate, sessão a sessão:
   - as mensagens que o rádio daria, de cada tipo, com o texto e a fala;
   - o ponto da pista em que cada uma seria entregue;
   - quanto tempo cada fala dura.

   Quero ler isso antes de ir ao jogo.
5. **As suítes:** a do backend e os testes do front continuam passando.
6. **Capturas:** a tela Ao vivo com a análise e o minimapa desenhado fora do jogo, se houver como.

## Parte G — Teste no jogo (comigo)

Pare aqui. Grave o relatório parcial com estes passos para mim, com os comandos exatos:

1. Fechar o jogo.
2. Rodar `tools/csp_app/instalar.ps1` de novo.
3. Abrir o app pelo repositório (o rádio ainda não está no instalador).
4. Abrir o Assetto Corsa em Interlagos e ligar, na barra de apps do jogo, o cartão do rádio e o minimapa.
5. Na tela Sistema, mandar a mensagem de teste. O cartão aparece no jogo e a voz toca.
6. Andar 6 voltas sem a IA:
   - as 3 primeiras com a tela Ao vivo aberta no app;
   - as 3 últimas com a tela Sessões aberta.
7. Fechar e avisar: "testei o rádio v2 no jogo".

**Depois do aviso:**

- confira o registro do rádio contra as frases do coach e as análises;
- leia, sem mudar nada, as linhas `[radio_engenheiro]` do log do CSP;
- compare a gravação com a tela Ao vivo aberta e fechada (Parte D.5);
- complete o relatório.

## Parte H — Documentação

- **`docs/realidade_aumentada.md`:**
  - a frase com a causa, a análise e o resumo novo, com exemplos reais;
  - os três caminhos da voz e o que funcionou no jogo;
  - o minimapa: o que mostra, de onde vem cada dado e o custo medido;
  - o registro e como medir se a curva citada melhorou.
- **ADR 0021:**
  - copie o anexo para `docs/decisoes/`;
  - acrescente a linha em `docs/decisoes/README.md`;
  - apague a pasta `docs/prompts/anexos-35/`.
- **`docs/dashboard_inventario.md`:** o que este pedido entregou, no fim da seção 7.

## Regras gerais

- **O coach continua decidindo as frases.** O foco, o limiar e o limite de 3 por volta não mudam. A análise só lê o que o coach e a grade já medem.
- **Nenhum modelo, store ou critério muda.**
- **Não grave na pasta do jogo.** Os scripts são rodados por mim. Em tempo de jogo, o app só grava dentro da pasta dele (ADR 0021, item 6).
- **Não instale nem atualize pacotes** (npm, pip ou Lua). Se algo pedir pacote novo, pare e relate.
- **Não mexa no app instalado.** Os testes usam a pasta isolada, como nos pedidos 28 a 31.
- **Não gere instalador.** Ele vem quando o rádio e o minimapa estiverem aprovados no jogo.
- **Nada de marca alheia:** sem logotipo, som ou fonte da F1, do WEC, da FIA ou de equipes.
- **Não contorne nenhuma trava:** se algo parar, pare também e registre o motivo. Uma trava do git não é apagada sem me perguntar.
- **Janelas de teste** com "[teste]" no título, fechadas no fim.
- **Branch e commits:** branch `etapa/radio-v2-e-minimapa`, commits por parte, merge em `develop`. Sem push.
- **Uma sessão de implementação por vez** (ADR 0008).
- **Relatório** em `docs/handoff/2026-10-18_35_radio-que-analisa-e-minimapa_relatorio.md`, como manda o CLAUDE.md, com:
  - a Parte A;
  - o caminho da voz e o que a API permite;
  - as regras novas do texto, com exemplos reais;
  - a tabela de antes e depois do mapa ao vivo;
  - o minimapa e o custo medido;
  - a conferência da Parte F.4;
  - a saída dos testes e os commits;
  - na parada da Parte G, os passos para mim.
- Se algo do contexto não bater com o repositório, pare e registre no relatório.
