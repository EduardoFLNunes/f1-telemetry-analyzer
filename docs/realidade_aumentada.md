# Realidade aumentada: o rádio do engenheiro, os mapas e o replay da curva (pedido 31, ADR 0020; pedidos 35 e 36, ADR 0021)

O rádio leva o que o coach já decide até o piloto, durante a volta, com o jogo em tela cheia: uma mensagem curta, num cartão dentro do jogo e em voz, no momento em que dá para ouvir. É o jeito de o Modelo 2 chegar ao piloto (ADR 0018). O rádio não decide nada do coach: quais frases saem, o limite de 3 por volta, o foco e o limiar continuam no coach. Desde o pedido 35, ele também analisa as voltas a cada 3 voltas válidas, lendo só o que a volta ao vivo e o store já medem (ADR 0021). O app do jogo ganhou dois mapas com o fantasma da referência: o minimapa, com a pista inteira, e o mapa aproximado, a vista de perto da tela Volta. Desde o pedido 36, todo número falado tem a unidade (seção 2.6), os dois mapas marcam a freada da IA e o engenheiro mostra o que diz: o replay da curva (seção 5.4), no jogo e na tela Ao vivo.

## 1. Como funciona

1. **O coach ao vivo** mede a volta na geometria oficial e, quando um microssetor de foco passa o limiar, publica uma frase (`coaching_event`).
2. **O backend monta cada mensagem uma vez** (`backend/core/radio/texto.py`), com o cartão e a fala. São quatro tipos:

   | tipo | quando nasce | a fala dura até |
   |---|---|---|
   | frase do coach | quando o coach publica (no máximo 3 por volta, regra do coach) | cerca de 6 s |
   | resumo | na linha de chegada | cerca de 7 s |
   | análise | a cada 3 voltas válidas da sessão (pedido 35) | cerca de 8 s |
   | teste | pela tela Sistema | — |

   **As regras da escrita:** português com acento, número com vírgula, microssetor contado a partir de 1 (o índice 2 do coach é o microssetor 3) e curva pelo nome técnico, com o lado por extenso (ADR 0003). Sempre a diferença medida contra uma volta real, nunca um ganho prometido (ADR 0012).
3. **Ela espera uma janela de rádio** (seção 3) e só é entregue se a fala inteira cabe no que resta da janela, na velocidade do carro. Nada é dito dentro das 14 curvas. Sai uma por vez: a seguinte espera o áudio da anterior acabar. O resumo vai para a frente da fila.
4. **O app do jogo e a tela Ao vivo** leem as mensagens entregues em `/api/radio/mensagens` e mostram o mesmo texto. A tela Volta usa a mesma escrita nas frases de uma volta gravada.

## 2. O que o rádio diz (pedido 35)

Os exemplos são das sessões de 13/10 e 18/10, passadas pelo rádio fora do tempo real, com a voz de verdade e o cronômetro do gravador (handoff do pedido 35). Desde o pedido 36, as falas são as com as unidades (seção 2.6), da mesma passagem refeita (handoff do pedido 36).

### 2.1 A frase do coach com a causa

A voz diz a curva, a diferença e a causa principal, quando o `evidence` do coach tiver:

- **a regra:**
  1. a freada, quando a diferença do ponto de freada passa de 15 m;
  2. senão, a mínima, quando a diferença passa de 8 km/h;
  3. abaixo dos dois cortes, a voz não diz causa.
- **exemplos:**

  | cartão | fala | dura |
  |---|---|---|
  | C12, esquerda · +1,87 s para a volta da IA no microssetor 44 · a IA freia 54 m depois de você | "Curva 12: 1,9 segundo atrás da IA. Freia 54 metros antes da IA." | 6,2 s |
  | C11, esquerda · +1,25 s para a volta da IA no microssetor 39 · mínima da IA 94 km/h, a sua 64 km/h | "Curva 11: 1,3 segundo atrás. Mínima de 64 contra 94 quilômetros por hora." | 7,2 s |

O cartão continua com todos os números (os dois tempos, a freada e a mínima).

### 2.2 O resumo na linha

O tempo da volta (o período de s = 0 a s = 0, que o coach mede como o store v2), a diferença para a referência escolhida e a curva em que a volta mais perdeu, com a perda:

| cartão | fala | dura |
|---|---|---|
| Volta 8: 1:29,059 · +4,230 s para a volta da IA (1:24,829) · mais perdeu na C01, esquerda: +0,75 s | "Volta 8: 4,2 segundos atrás da IA. Mais perdeu na curva 1: 7 décimos." | 6,7 s |
| Volta 4: 1:40,073 · +15,244 s para a volta da IA (1:24,829) | "Volta 4: 1 minuto e 40,1 segundos, 15,2 segundos atrás da IA." | 6,0 s |

A curva que mais perdeu só entra numa volta completa (com todos os microssetores medidos): numa volta com parada, "mais perdeu na curva 1: 66,4" é verdade, mas não ajuda.

### 2.3 A análise das voltas

- **Quando:** a cada 3 voltas válidas da sessão, sobre essas 3. Uma volta é válida quando:
  - não teve a IA;
  - o coach mediu todos os microssetores;
  - a volta ao vivo tem o relógio medido em pelo menos 90% dos pontos da grade;
  - **nenhuma curva perdeu mais de 5 s contra a referência** (pedido 36, decisão do Eduardo de 22/10). Uma perda dessas é uma rodada ou uma saída de pista: no teste de 21/10, a volta 5 perdeu 26,5 s na C12 e entrou na primeira análise. A volta com rodada não conta para a análise, e o resumo dela diz o tempo e a diferença sem citar a curva. É uma regra só do rádio (`PERDA_DE_RODADA_S` em `core/radio/analise.py`): o coach, o store e as regras de volta válida do store não mudam.
- **As curvas:** até 2 das 14, pela maior perda mediana contra a referência escolhida na Coleta, e só as perdidas em pelo menos 2 das 3 voltas.
- **As medidas de cada curva** (`backend/core/radio/analise.py`), sempre "sua volta menos a referência", em mediana das 3 voltas:

  | medida | de onde vem |
  |---|---|
  | perda no trecho da curva | o relógio da grade, do meio da reta anterior ao meio da seguinte (o trecho do relatório de evolução) |
  | ponto de freada (m) | o primeiro ponto com o freio acima de 0,15, do ápice anterior ao ápice (o relatório de evolução) |
  | mínima (km/h) | a menor velocidade dentro da curva (o relatório de evolução) |
  | volta ao acelerador cheio (m) | montada aqui: o primeiro ponto, do ápice ao fim do trecho, com o acelerador em 0,95 ou mais |
  | traçado (m) | montado aqui: a posição lateral no ponto da mínima da referência, com o lado por extenso (ADR 0003) |

  A volta do piloto é a grade que a volta ao vivo guarda, com a projeção que o coach já faz; a referência é a volta do store v2. Nenhuma conta de física nova.
- **O que vai na fala:** as diferenças que mais pesam, até 2 por curva. O peso é a diferença dividida pelo corte da medida (seção 2.4); só entra o que passa do corte. Se a fala não couber em cerca de 8 s, sai a variante mais curta (seção 2.5).
- **Como cada diferença é falada:** uma frase, como na frase do coach, com a unidade e contra quem (seção 2.6):
  - "Freia 46 metros antes da IA.";
  - "Mínima de 102 contra 128 quilômetros por hora.";
  - "Acelera 14 metros depois da IA.";
  - "Passa 8 metros mais à direita que a IA.": de 2 m para cima, o número inteiro; abaixo de 2 m, com a vírgula e no singular ("1,8 metro").

  Contra a sua melhor volta, "da sua melhor" e "que a sua melhor".
- **O cartão:** as curvas com todos os números, uma linha por curva.
- **Exemplos:**

  | sessão | cartão | fala | dura |
  |---|---|---|---|
  | 18/10 | Análise das voltas 3, 7 e 8 · C04 perde 1,04 s por volta · C01 perde 0,95 s por volta, contra a volta da IA. Linha da C04: perde 1,04 s por volta (1,04 s · 1,06 s · 0,22 s); mínima 102 contra 128 km/h; freada 40 m antes; acelerador cheio 16 m depois; traçado 1,5 m mais à direita | "Curva 4: perde 1,0 segundo por volta. Mínima de 102 contra 128 quilômetros por hora." (sem a abertura, para caber) | 7,8 s |
  | 18/10 | Análise das voltas 9, 12 e 13 · C01 perde 0,86 s por volta · C05 perde 0,55 s por volta | "Análise das voltas 9, 12 e 13. Curva 1: perde 9 décimos por volta. Freia 46 metros antes da IA." | 8,7 s |
  | 13/10 | Análise das voltas 6 a 8 · C01 perde 1,09 s por volta · C11 perde 0,70 s por volta | "Análise das voltas 6 a 8. Curva 1: perde 1,1 segundo por volta. Freia 36 metros antes da IA." | 8,3 s |
  | 21/10 | Análise das voltas 16 a 18 · C01 perde 1,21 s por volta · C10 perde 0,46 s por volta | "Voltas 16 a 18. Curva 1: perde 1,2 segundo por volta. Passa 8 metros mais à direita que a IA." | 8,3 s |

### 2.4 Os cortes e o porquê

Abaixo do corte, a diferença está dentro da variação normal do próprio piloto de uma volta para outra, e não é dita. Cada corte é a mediana do desvio-padrão volta a volta daquela medida, por curva e por sessão, nas 73 voltas humanas do store v2 de 11/10 a 18/10, arredondada:

| medida | variação medida (mediana; p75) | corte |
|---|---|---|
| ponto de freada | 14,7 m; 21,6 m | 15 m |
| mínima | 7,7 km/h; 10,9 km/h | 8 km/h |
| volta ao acelerador cheio | 10,7 m; 18,7 m | 10 m |
| traçado | 1,76 m; 2,25 m | 1,8 m |

Na análise, vale a mediana de 3 voltas, que varia menos que uma volta: o corte de uma volta é, então, conservador. A frase do coach usa os mesmos cortes da freada e da mínima.

### 2.5 Quanto cabe em cada janela

- **A voz a 1,4x** (era 1,25x no pedido 31): os números falados por extenso faziam a frase com a causa, o resumo com a curva e a análise passarem de 6, 7 e 8 s. Não estava no pedido 35 e ficou registrada como desvio no relatório dele. **O Eduardo aprovou a 1,4x em 22/10** (pedido 36).
- **As variantes:** cada mensagem traz a fala da mais completa à mais curta. O rádio gera o áudio e fica com a primeira que cabe no limite do tipo: 7,3 s (frase do coach), 7,7 s (resumo) e 8,8 s (análise). Eram os 6, 7 e 8 s do pedido 35 com 10% de folga; a frase do coach subiu de 6,6 para 7,3 s no pedido 36, decisão do Eduardo, para a causa com a unidade caber (seção 2.6).
- **A entrega:** só quando a fala inteira cabe no que resta da janela, pela velocidade do carro, com 0,3 s de folga.
- **Nas duas sessões** (todas as falas couberam no que restava da janela):

  | sessão | tipo | mensagens | a fala dura | onde foi entregue |
  |---|---|---|---|---|
  | 18/10 | resumo | 13 | 6,1 a 7,7 s | 12 na reta oposta (723 m, sobrando 7,8 a 8,7 s), 1 na reta dos boxes |
  | 18/10 | frase do coach | 2 | 5,9 a 6,2 s | reta dos boxes (3.697 m, sobrando 13,8 e 15,6 s) |
  | 18/10 | análise | 2 | 7,9 e 8,1 s | reta dos boxes (sobrando 12,9 e 12,2 s) |
  | 13/10 | resumo | 13 | 6,1 a 7,7 s | 11 na reta oposta, 2 na reta dos boxes |
  | 13/10 | frase do coach | 6 | 5,8 a 6,5 s | reta dos boxes (5 em 3.697 m, 1 em 3.953 m) |
  | 13/10 | análise | 1 | 6,8 s | reta dos boxes (sobrando 12,3 s) |

  A janela entre a C05 e a C06 (1.637 a 1.818 m, cerca de 3 s a 200 km/h) não recebeu nenhuma fala: nenhuma cabe nela.

### 2.6 As unidades (pedido 36)

Todo número falado tem a sua unidade (`backend/core/radio/texto.py`):

| o quê | regra | exemplos |
|---|---|---|
| tempo abaixo de 1 s | em décimos | "7 décimos", "1 décimo", "menos de 1 décimo" |
| tempo de 1 s para cima | uma casa, "segundo" no singular abaixo de 2 | "1,2 segundo", "5,4 segundos" |
| tempo da volta | minutos e segundos | "1 minuto e 29,1 segundos", "2 minutos e 8,2 segundos" |
| distância | o inteiro; abaixo de 2 m, uma casa e no singular | "46 metros", "1,8 metro" |
| mínima | as duas velocidades e a unidade uma vez, no fim | "Mínima de 102 contra 128 quilômetros por hora." |

- **Contra quem:** a diferença diz a referência ("atrás da IA", "antes da IA", "que a IA"; "da sua melhor" contra a sua melhor volta). Sem espaço, sai ("Freia 15 metros antes.").
- **A ordem do corte,** quando a fala não cabe no limite do tipo (seção 2.5): **a unidade nunca sai.**
  - na frase do coach: sai o lado da curva, depois o "contra quem" e, por último, a causa;
  - na análise: sai a segunda curva, depois a abertura encurta ("Voltas 16 a 18."), depois a segunda causa, o "contra quem", a abertura inteira e, por último, a primeira causa.
- **O teste:** `test_todo_numero_falado_tem_a_unidade...` (em `backend/tests/test_radio.py`) passa todas as falas de todas as variantes por um leitor que acusa número sem unidade.
- **Quantas mensagens perderam a causa** por causa das unidades, nas três sessões passadas pelo rádio (handoff do pedido 36), entre as que têm causa (a frase do coach com a causa, o resumo com a curva que mais perdeu e a análise):

  | sessão | antes das unidades | com as unidades e o limite de 6,6 s | com o limite de 7,3 s (o atual) |
  |---|---|---|---|
  | 13/10 | 0 de 12 | 2 de 12 | 0 de 12 |
  | 18/10 | 0 de 13 | 2 de 13 | 0 de 13 |
  | 21/10 | 0 de 18 | 6 de 18 | 0 de 18 |

  Todas são frases do coach da C11 com a mínima: "Curva 11, esquerda: 1,3 segundo atrás da IA. Mínima de 64 contra 94 quilômetros por hora." dura de 6,8 a 7,2 s na variante mais curta com a causa, e o limite era 6,6 s: a causa da C11 saía, e a voz dizia só a curva e o tempo. **Com o limite de 7,3 s, nenhuma mensagem perde a causa** nas três sessões, e todas continuam sendo entregues (as frases do coach duram de 6,0 a 7,3 s).

## 3. As janelas de rádio

Uma janela é um trecho da geometria oficial fora das 14 curvas (`backend/core/radio/janelas.py`):

- **a curva:** o trecho em que a pista curva (`ml.track.corners.detect_corners`, como o relatório de evolução);
- **as margens:** 120 m antes de cada curva (a freada) e 30 m depois (a saída);
- **o tamanho mínimo:** 80 m.

Em Interlagos, isso dá três janelas:

| janela | onde |
|---|---|
| 723 a 1.192 m | a reta oposta, depois do S do Senna |
| 1.637 a 1.818 m | entre a C05 e a C06 |
| 3.697 a 104 m | a reta dos boxes, que cruza a linha |

Uma frase do miolo (C06 a C14) espera a reta dos boxes. A posição do carro é a projeção na geometria oficial que o coach já faz (`LiveDrivingCoach.posicao_oficial`), sem cálculo novo.

## 4. A voz

- **A escolhida:** **Microsoft Daniel (OneCore, pt-BR), a 1,4x** (`VELOCIDADE_PADRAO` em `core/radio/audio.py`; a 1,25x até o pedido 35). A 1,4x foi um desvio do pedido 35, aprovado pelo Eduardo em 22/10 (seção 2.5).
- **Como é gerada:** pelo `backend/core/radio/voz.ps1`, com o PowerShell do Windows, sem instalar nada.
- **As três vozes pt-BR deste Windows,** testadas no pedido 31 com a mesma frase ("Curva 1, esquerda: 0,74 atrás da IA."), a 1,25x:

| voz | interface | gera em | dura (com a vinheta) |
|---|---|---|---|
| Microsoft Daniel | OneCore (`Windows.Media.SpeechSynthesis`) | 1,5 s | 4,5 s |
| Microsoft Maria | OneCore | 0,8 s | 4,8 s |
| Microsoft Maria Desktop | SAPI 5 (`System.Speech`) | 1,0 s | 4,8 s |

- **Por que a Daniel:**
  - as vozes OneCore são as mais novas do Windows;
  - a Daniel foi a mais curta das três (cabe melhor numa reta);
  - uma voz masculina grave se separa melhor do ronco do motor.
- **Como trocar:** a voz fica em `core/radio/audio.py` (`VOZ_PADRAO`). As três amostras estão no handoff do pedido 31.
- **A vinheta antes da voz:** gerada pelo próprio código, sem som copiado de transmissão. É um estalo curto de ruído e dois bipes descendo (1.400 e 1.050 Hz).
- **O arquivo:** um WAV por mensagem em `<pasta de dados>/data/radio/audio/`, mono, 16 bits, com o silêncio das pontas cortado.

## 5. O app do jogo

- **A versão:** 0.4.1 (`manifest.ini`, `VERSION = 0.4.1`), a que está instalada no jogo desde 24/10. Ela entrou em `develop` no pedido 40; antes, só estava em `etapa/radio-unidades-e-replay` (commit `0092ed38`), e o `instalar.ps1` de `develop` instalava a 0.4.0.
- **Onde fica:** `tools/csp_app/radio_engenheiro/`:
  - `manifest.ini`;
  - `radio_engenheiro.lua`;
  - `pista.json`: a pista simplificada para quando o backend estiver fora do ar, o nome das 14 curvas e onde fica a imagem da pista detalhada no mundo;
  - `pista_detalhada.png`: a pista do mapa aproximado (seção 5.3) e do replay da curva (seção 5.4).

  Os dois arquivos são gerados por `tools/csp_app/gerar_pista.py`, a partir da geometria oficial e do cache da pista. Se o cache mudar, rode de novo.
- **Quatro janelas,** ligadas e desligadas cada uma na barra de apps do jogo:
  - **"Rádio · Sistema de Telemetria e Otimização de Trajetórias":** o cartão e a voz;
  - **"Minimapa · Sistema de Telemetria e Otimização de Trajetórias":** a pista inteira, o carro e o fantasma;
  - **"Mapa aproximado · Sistema de Telemetria e Otimização de Trajetórias":** a vista de perto, que gira com o carro;
  - **"Replay da curva · Sistema de Telemetria e Otimização de Trajetórias"** (pedido 36, versão 0.4.0): a curva de que o rádio fala, com a sua linha e a da referência.
- **O encaixe na janela** (pedido 36, Parte D.1): no teste de 21/10, o minimapa cortava à direita. Fora do jogo, isso não se reproduz; as causas possíveis são a janela passando da borda da tela, o recorte padrão do ImGui e o espaçamento interno da janela. Desde o pedido 36, os mapas e o replay se encaixam na parte visível da janela (a janela menos o que passa da tela, pelo `ui.windowPos` e o tamanho da tela do jogo) e desenham com o recorte da janela inteira. Cada janela escreve uma vez no log do CSP as suas medidas (`[radio_engenheiro] minimapa: janela 300 x 300 em 1600 x 40; tela 1920 x 1080, escala 1,00; cursor ...; visível de 0,0 a 300,300`), para confirmar a causa no jogo. **No teste de 22/10,** o minimapa estava em −9 × 543 numa tela de 2.560 × 1.080: 9 px da janela passavam da borda esquerda, e a área visível começou em 9 px. É a primeira causa (a janela passando da borda da tela), agora com o encaixe cuidando dela.
- **A janela salva fora da tela** (versão 0.4.1, teste de 24/10): o jogo trocou do monitor de 2.560 px para o de 1.920 px, e o mapa aproximado abriu na posição salva (x = 2.188), fora da tela; não era desenhado e o mouse não o alcançava. A cada 2 s, uma janela ligada do app com menos de 40 px dentro da tela volta para dentro (`ac.getAppWindows` e `AppWindowAccessor:move`), com uma linha no log do CSP.
- **O que não faz:** não muda o carro, os controles nem nada do jogo, e não desenha na pista.
- **Onde grava:** só na subpasta `voz` da própria pasta do app (ADR 0021, item 6), que ele limpa dos `.wav` ao abrir.
- **Onde pôr as janelas:** num canto, sem cobrir o centro da tela. A posição é a do modo de mover apps do jogo.
- **A conferência sem o jogo:** `tools/csp_app/conferir_lua.py` confere o léxico, os blocos, a API e os métodos usados contra o `lib.lua` do SDK do CSP instalado (só leitura). Ele também acusa `type(...) == 'function'` numa função da API, o erro que calou o app no teste de 18/10.

### 5.1 O rádio

- **As mensagens:** a cada 0,3 s, pede as novas ao backend (`http://127.0.0.1:8000`). O CSP aceita no máximo dois pedidos de uma vez; o app tem uma fila só e nunca passa de dois.
- **O cartão:**
  - carbono e vermelho, por pelo menos 5 s (12 s na análise);
  - na análise, o resumo em até duas linhas e uma linha por curva, com todos os números.
- **A voz tem três caminhos, um depois do outro** (pedido 35, Parte B):
  1. **pela URL do backend** (`ui.MediaPlayer` aceita URL);
  2. **pelo arquivo** que o backend grava em `data/radio/audio/`: o backend manda o caminho (`audioArquivo`), e os apps do CSP podem ler fora da pasta deles (o `rules.json` do SDK só tira o acesso a arquivos dos scripts de carro e de pista);
  3. **baixando o áudio** com `web.get` e gravando-o em `voz\<id>.wav`, dentro da pasta do app. O anterior é apagado quando o seguinte toca.
- **Como o app decide:**
  - um caminho tocou quando a posição do áudio anda (`player:currentTime()`). Se não tocar em 2,5 s (5 s na primeira mensagem, enquanto o CSP carrega o Media Foundation), o app passa ao seguinte;
  - o caminho que tocou fica em `voz\caminho.txt` e é o primeiro tentado na próxima vez.
- **O log do CSP:** uma linha por mensagem:
  - `[radio_engenheiro] voz: <caminho> tocou`, com os caminhos que falharam antes entre parênteses;
  - ou `[radio_engenheiro] voz: falhou: <caminho>: <motivo>; ...`.
- **O volume:** `VOLUME_DO_RADIO`, no começo do arquivo, de 0 a 1. O som sai pelo áudio do jogo, e o volume geral do Assetto Corsa vale por cima.
- **O que funcionou no jogo** (teste de 21/10): **a URL do backend.** As 30 mensagens da sessão tocaram por ela (`voz: url tocou`), sem nenhuma falha; os outros dois caminhos não foram precisos. O caminho fica guardado em `voz\caminho.txt`.
- **Com o backend fora do ar:** um ponto apagado e "rádio sem backend" no rodapé da janela, e o aviso uma vez no log do CSP.
- **Se a API do CSP não tiver o que o app usa:** avisa uma vez e fica calado. Se faltar só o que o minimapa ou o terceiro caminho da voz usam, só eles ficam de fora.

### 5.2 O minimapa

- **A pista tratada:**
  - **o que é:** o contorno do asfalto tratado do cache da pista (`asphaltSurface.loops`), a mesma camada que o mapa do app e o mapa aproximado desenham. Só entram os laços com pelo menos 1.000 m² (o contorno de fora, o buraco do miolo, as áreas de escape e dos boxes), e cada laço é simplificado pelo Douglas-Peucker com 2 m de tolerância: em Interlagos, 12 contornos e 363 pontos. As camadas do cache estão em (x, −z) e viram (x, z), a posição do carro (`core/radio/minimapa.py`, `contorno_do_asfalto`);
  - **até o fechamento do pedido 35,** eram as duas bordas da geometria oficial (o centro mais e menos a largura do corredor). Elas só ficam quando o backend não tem o cache da pista, e a rota diz isso em `pista.origem`;
  - **como é desenhada:** o contorno, sem preencher o asfalto (o desenho do CSP não preenche polígonos côncavos). Uma vez, num `ui.ExtraCanvas`, refeito só quando o minimapa muda ou a janela muda de tamanho. A cada quadro, o app só desenha essa imagem;
  - **a orientação:** a mesma do mapa do app (`base(x, z) = (z, −x)`, `frontend/src/volta/projecao.ts`);
  - **as marcas:** a linha do s = 0 (da geometria oficial, só como marca) e as curvas da última análise, com um círculo e o nome (C01...);
  - **a freada da IA** (pedido 36): só a da próxima curva, uma marca curta atravessando a pista, na cor do fantasma. O ponto é o do relatório de evolução (`ml.comparison.evolution.braking_point`: o freio da referência passa de 0,15, do ápice anterior ao ápice), e a marca vai da borda esquerda à direita da geometria oficial nesse ponto (`core/radio/minimapa.py`, `freadas_da_referencia`). Em Interlagos, a IA freia em 8 das 14 curvas (C01, C02, C04, C06, C07, C08, C10 e C12), as mesmas do relatório de evolução. Uma curva em que a referência não freia fica sem marca.
- **O carro:** a posição vem do próprio jogo, a cada quadro (`ac.getCar(0).position`), sem pedir nada ao backend. A posição do jogo e a da geometria oficial estão no mesmo sistema de coordenadas: é a mesma que o coach projeta.
- **O fantasma da referência escolhida na Coleta:**
  - a volta é baixada do backend uma vez, quando o app abre ou quando a referência ou a análise mudam (a `minimapaVersao` das mensagens). Ela vem em todos os 2.167 pontos da grade do store (2 m), com a posição, o tempo e o pedal;
  - **o alinhamento dos relógios:** o cronômetro do jogo zera na linha do jogo, 1,463 m depois do s = 0 (pedido 33; o backend usa a medida do store, 1,495 m, pedido 34). O tempo da referência conta desde o s = 0. O backend manda o tempo da referência na linha do jogo (`tempoNaLinhaDoJogoS`, 0,020 s na volta da IA), e o app soma: **tempo da referência = cronômetro do jogo + tempoNaLinhaDoJogoS**. O fantasma fica no ponto da referência com esse tempo;
  - aparece depois da primeira passagem pela linha (o cronômetro da volta de saída dos boxes não serve).
- **A diferença ao vivo, em segundos e com sinal:**
  - **calculada no app:** o tempo do carro (o mesmo alinhamento) menos o da referência no ponto dela mais perto do carro, projetado no segmento. É a conta da tela Volta;
  - **por que no app:** a posição do carro é a do jogo, a cada quadro, e o app já tem a referência inteira. Pelo backend, a diferença chegaria a cada pedido de 0,3 s, ocuparia um dos dois pedidos que o CSP permite e pararia com o backend fora do ar;
  - **a conferência fora do jogo:** a mesma conta, portada para Python, nas sessões de 13/10 e 18/10, contra a conta da grade (o s do carro pela linha central e o tempo da referência nesse s):
    - a diferença do app ficou a 0,010 s da grade na mediana (p95 de 0,04 s em 18/10 e de 0,06 s em 13/10);
    - o fantasma ficou a 0,5 m, ao longo da pista, de onde a grade o põe (p95 de 1,0 m);
    - os poucos pontos acima de 0,5 s (0,1% em 13/10 e 0,9% em 18/10) foram com o carro a mais de 20 m da linha central, fora da pista;
    - os números são os mesmos com a referência em 362 pontos (a primeira versão) e em 2.167.
- **As cores:** as da tela Volta (`frontend/src/theme/tokens.css`):
  - o carro, "você": branco com o anel vermelho;
  - o fantasma: o miolo escuro com o anel claro;
  - a diferença em laranja quando perde e em azul quando ganha.
- **Com o backend fora do ar:**
  - a pista vem da `pista.json` da pasta do app;
  - o carro continua;
  - sem a volta de referência, o texto de cima diz, discreto, "sem fantasma: backend fora do ar". O texto quebra a linha e cabe na largura da janela;
  - se o backend cair depois de o app ter baixado a referência, o fantasma continua (os dados estão no app) e o canto de baixo diz "sem backend".
- **O custo no jogo:**
  - a cada 10 s, o app escreve no log do CSP o FPS do jogo (`ac.getSim().fps`, lido a cada 1 s): a média, a mínima e a máxima, e se cada mapa estava ligado ou desligado. O formato da linha: `[radio_engenheiro] fps: média <n> (mín <n>, máx <n>) em 10 s; minimapa ligado; mapa aproximado desligado` (ou `ligado e desligado`, quando mudou no meio). Com o jogo pausado ou num replay, a leitura não conta;
  - **o custo medido no jogo** (21/10, 285 janelas de 10 s): com os dois mapas desligados, 140,9 FPS de média; com os dois ligados, 136,9 (a tela Ao vivo aberta no app). Com a tela Sessões, 138,9 e 136,0. **Os dois mapas juntos custam de 3 a 4 FPS, cerca de 3%.** No teste, os dois foram desligados juntos, então o custo de cada um não aparece separado;
  - **a tela do app não muda o FPS do jogo:** 137,0 de média com a tela Ao vivo aberta e 136,1 com a tela Sessões;
  - fora do jogo: a rota monta o minimapa em cerca de 20 ms, uma vez, e manda 64 KB. A cada quadro, o app desenha a imagem da pista, dois círculos e o texto, e procura o ponto mais perto em cerca de 34 segmentos da referência.

### 5.3 O mapa aproximado

Pedido depois do primeiro teste no jogo (21/10): a vista de perto da tela Volta ("fantasma por curva"), dentro do jogo, ao lado do minimapa.

- **A câmera:**
  - segue o carro, um pouco abaixo do meio da janela, para mostrar mais da pista à frente;
  - gira com a pista, como a tela Volta. A direção é a da volta de referência perto do carro, mais estável que a do carro numa escorregada; sem ela, é a do carro. O giro acompanha em cerca de 0,15 s;
  - abre com 120 m no lado menor da janela. **A roda do mouse,** com o ponteiro sobre a janela, aproxima até 50 m e afasta até 400 m.
- **A pista detalhada:**
  - as camadas do cache que o mapa do app desenha (`drawTrackSurface`): o asfalto, a pintura classificada (o limite em branco, os boxes em amarelo, as vias de serviço em cinza) e as zebras (a base escura com as faixas brancas), com as cores e as larguras do app;
  - desenhada uma vez numa imagem, `pista_detalhada.png` (2.788 × 4.118 px, 3 px por metro, 0,56 MB), pelo `gerar_pista.py`;
  - a cada quadro, o app desenha essa imagem girada (`ui.drawImageQuad`): cada canto da janela volta para o mundo e daí para a imagem, que está nas coordenadas do mapa (x, −z), as mesmas da posição do carro;
  - sem a imagem, ou enquanto ela carrega, o app desenha só o contorno do asfalto, como no minimapa.
- **Por cima da pista:**
  - **o seu traçado** desde a linha, pintado pelo pedal: o freio em vermelho, o acelerador cheio em verde e o parcial em amarelo. O app lê a posição e os pedais do jogo 20 vezes por segundo e guarda um ponto a cada 1,5 m;
  - **o traçado do fantasma,** da linha até onde ele está, mais apagado, com o pedal da volta de referência;
  - **o nome das 14 curvas,** na mesma posição da tela Volta (do lado de fora, a largura da pista mais 9 m do ápice);
  - **o fantasma,** com "IA" ou "Sua melhor". Fora da janela, ele vira uma seta na borda, apontando para onde está;
  - **o carro,** "Você · V<n>", com o número da volta do jogo;
  - **a diferença,** a mesma do minimapa, numa faixa escura no alto;
  - **a freada da IA** (pedido 36): em todas as curvas que aparecem na janela, uma linha atravessando o asfalto, um pouco além das bordas, com o rótulo "freada da IA" ("freada da sua melhor", contra a sua melhor volta). O ponto é o mesmo do minimapa. O seu traçado mostra onde você freou: o vermelho começa ali.
- **A conferência fora do jogo:** uma prévia em HTML repete as contas do app (a câmera, a imagem girada, os traçados e as marcas), com a referência da IA e instantes reais da sessão de 18/10:
  - **na saída da reta dos boxes,** a pintura amarela dos boxes fica à esquerda, como na tela Volta;
  - **na freada da C04,** o carro e os dois traçados ficam dentro do asfalto, e a curva vira para a esquerda.
- **O custo:** uma imagem e algumas centenas de pontos por quadro. O FPS entra no mesmo registro do minimapa. O custo medido está na seção 5.2: os dois mapas juntos, de 3 a 4 FPS.

### 5.4 O replay da curva (pedido 36)

O engenheiro mostra o que diz: quando o rádio fala de uma curva, a janela mostra essa curva vista de cima, com a sua passagem e a da referência lado a lado. O mesmo replay aparece na tela Ao vivo, sob o cartão.

- **O que mostra:**
  - a curva sobre a pista tratada (no jogo, a `pista_detalhada.png`; na tela Ao vivo, as camadas do cache que o mapa do app desenha), com a entrada para cima;
  - **as duas linhas:** "você" em vermelho e "IA (referência)" (ou "Sua melhor") em claro, da entrada à saída;
  - **os dois carros,** cada um andando no seu próprio tempo a partir da mesma entrada: a diferença aparece sozinha, no quanto a referência abre;
  - **as duas freadas,** um traço em cada linha, com a distância ("você freia 34 m antes da IA");
  - **as duas mínimas,** no ponto de cada uma, em km/h;
  - **o traçado:** uma seta, no ponto da mínima da referência, da linha da referência à sua, com a distância e o lado ("você passa 7,9 m mais à direita");
  - **no alto:** a curva, o lado, a volta e o tempo perdido na curva ("C01, esquerda · volta 17 · perde 1,21 s nesta curva");
  - os rótulos não se cobrem, não cobrem os carros e as marcas e não saem da janela: cada um procura um lugar livre em volta do seu ponto e, se precisar ir mais longe, ganha um fio até ele.
- **De onde vem cada dado** (`backend/core/radio/replay.py`), só com o que o rádio já tem, sem física nova:

  | dado | de onde vem |
  |---|---|
  | a sua volta | na frase do coach, a volta em que a frase saiu (a volta ao vivo, ou a que acabou de fechar, se a entrega já passou da linha; só com o relógio medido em pelo menos 90% da curva). A volta de saída dos boxes não tem o relógio (ele começa na linha), e a frase dela fica sem replay. Na análise, das 3 voltas analisadas, a de perda na curva mais perto da mediana |
  | a referência | a volta do store v2 escolhida na Coleta, a mesma do rádio |
  | as linhas | a geometria oficial (o centro mais a normal vezes a posição lateral), o traçado da tela Volta, de 50 m antes da primeira freada (ou do começo da curva) até 60 m depois do fim da curva |
  | o tempo de cada carro | o relógio da grade, zerado na mesma entrada |
  | as freadas | o primeiro ponto com o freio acima de 0,15, do ápice anterior ao ápice (o relatório de evolução) |
  | as mínimas | a menor velocidade dentro da curva (o relatório de evolução) |
  | o traçado | a posição lateral no ponto da mínima da referência, a mesma medida da análise (ADR 0003) |
  | o tempo perdido | o trecho do relatório de evolução, a mesma perda da análise |

- **Quando aparece, no jogo:**
  - **na reta:** junto com a fala de uma análise ou de uma frase do coach com causa. Toca cada curva citada, uma depois da outra, e some quando a janela de rádio acaba (o `restaS` que o backend manda na mensagem: o que resta da janela, pela velocidade do carro, na entrega). Como a fala, nunca aparece dentro das 14 curvas;
  - **nos boxes ou com o jogo pausado:** a última análise, em repetição, com a janela 1,6 vez maior, até você sair. A janela volta ao tamanho de antes na saída;
  - o resumo na linha e a frase do coach sem causa não têm replay.
- **Na tela Ao vivo:** sob o cartão da análise e da frase do coach com causa, a mesma animação, uma vez, e o botão "Repetir o replay".
- **A rota:** `GET /api/radio/replay/<id>`, uma vez por mensagem. A mensagem diz se tem replay (`replay.url` e as curvas). Uma análise com 2 curvas ocupa cerca de 20 KB; uma frase do coach, cerca de 8 KB.
- **A medida da frase do coach e a do replay não são a mesma** (achado da conferência ponta a ponta de 22/10, decisão pendente do Eduardo). A voz e o cartão da frase do coach dizem o que o coach mediu no microssetor (o `evidence`: a freada e as mínimas daquele trecho de cerca de 70 m); o replay mede a curva inteira, pela regra do relatório de evolução. Na C12 da volta 2 de 21/10, a voz diz "Freia 16 metros antes da IA." e o cartão "mínima da IA 145 km/h, a sua 101 km/h", e o replay mostra "você freia 56 m antes da IA" e as mínimas de 90 e 98 km/h. Na análise das voltas, a fala e o replay usam a mesma medida.
- **A conferência ponta a ponta** (22/10): o backend do repositório numa porta de teste, com as pastas isoladas, tocou a sessão de 21/10 pelo caminho do jogo, e a tela Ao vivo, apontada para ele, mostrou o replay da frase da C12 da volta 2 sob o cartão, com o botão de repetir (capturas no handoff do pedido 36).
- **A conferência fora do jogo:** uma prévia em HTML repete as contas da janela (a câmera, a imagem girada, as linhas, as marcas e o encaixe dos rótulos) com 3 curvas reais da sessão de 21/10: a C01 e a C10 da segunda análise e a C12 da primeira. Na C01 da segunda análise, os 7,9 m do traçado batem: a distância entre os dois pontos da seta é 7,941 m, e cada ponto está sobre a sua linha.
- **O custo:**
  - **no backend:** montar o replay leva cerca de 1 ms numa frase do coach e 3 ms numa análise com 2 curvas (sessão de 21/10, 9 replays), uma vez, na entrega;
  - **no jogo:** a cada quadro, uma imagem, duas linhas de 120 a 200 pontos, as marcas e os rótulos, e só enquanto o replay está na tela. O FPS entra no mesmo registro dos mapas (`replay ligado` ou `desligado`). **No teste de 22/10,** com as 4 janelas ligadas, 119,4 FPS de média (21 blocos de 10 s, de 112 a 127), numa tela de 2.560 × 1.080. Só houve um bloco com tudo desligado (137,3, no começo), e o replay não chegou a aparecer, porque a IA dirigiu a sessão e o rádio ficou calado; o custo de cada janela ainda não está medido.

### 5.5 Instalar, ligar e remover

O Eduardo roda os scripts; o Claude Code não grava na pasta do jogo (ADR 0020).

1. **Instalar,** com o jogo fechado:
   ```
   powershell -NoProfile -ExecutionPolicy Bypass -File tools\csp_app\instalar.ps1
   ```
   O script:
   - pede a pasta do jogo, com `D:\SteamLibrary\steamapps\common\assettocorsa` como sugestão;
   - confere que ela tem o `acs.exe` e o `extension\installed.log` do CSP;
   - mostra o que vai copiar e pede confirmação;
   - apaga e copia de novo só `apps\lua\radio_engenheiro\` (a subpasta `voz` vai junto).

   O `-ExecutionPolicy Bypass` vale só para esse comando e não muda a configuração do Windows.
2. **Ligar:**
   - abra o app do repositório (o backend com o rádio) antes do jogo;
   - no jogo, abra a barra de apps, no lado direito da tela, e ligue as janelas "Rádio", "Minimapa", "Mapa aproximado" e "Replay da curva".
3. **Conferir:** na tela Sistema, "Mandar mensagem de teste". O cartão aparece no jogo e a voz toca. O log do CSP diz por qual caminho.
4. **Remover:**
   ```
   powershell -NoProfile -ExecutionPolicy Bypass -File tools\csp_app\remover.ps1
   ```
   Apaga só `apps\lua\radio_engenheiro\`, depois de conferir que a pasta é mesmo a do rádio.

## 6. O registro e a avaliação do Modelo 2

- **Onde fica:** cada mensagem entregue vai para `<pasta de dados>/data/radio/<sessão>.jsonl`, fora da pasta de gravações (e fora do git).
- **O que tem cada linha:**
  - o id, a hora e a volta;
  - o `s` e a velocidade do carro na entrega, e a janela;
  - o `s` da geometria oficial do que foi medido (o fim do microssetor), o microssetor (a partir de 1) e a curva;
  - o texto, a fala, quanto ela dura e a origem (`coach`, `resumo`, `analise` ou `teste`);
  - na frase do coach, a causa dita;
  - o que restava da janela na entrega (`restaS`) e, quando há, o replay (o caminho e as curvas; pedido 36);
  - no resumo, o tempo da volta e a curva que mais perdeu;
  - **na análise:**
    - as voltas analisadas;
    - as curvas, com a perda em cada uma das 3 voltas;
    - as diferenças ditas;
    - a referência (o tipo e a volta).
- **Nenhum leitor do ML confunde essa pasta com uma sessão:** as varreduras do inventário e do store procuram `player.jsonl` dentro das pastas de gravação (`data/recordings`), e `data/radio` não tem nenhum.
- **Como medir se a curva citada melhorou** (ADR 0020, decisão 6; ADR 0021, item 7):
  - para cada análise, pegue as curvas citadas e a perda delas nas 3 voltas analisadas;
  - no store v2, meça a perda da mesma curva, contra a mesma referência, nas 3 voltas válidas seguintes da sessão, com as medidas do relatório de evolução (os mesmos trechos);
  - compare as duas medianas, e compare com as curvas não citadas, para separar o efeito do rádio da melhora geral.
- **O registro basta, com uma ressalva:** o número da volta é o do contador do jogo, e o store numera as voltas pela ordem no arquivo. Para achar a volta no store, cruze pelo tempo da volta, que o resumo de cada volta traz no mesmo registro. Numa gravação antiga (13/10), o contador do jogo se repetiu numa passagem pela linha, e dois resumos saíram como "Volta 10".

## 7. As rotas

| rota | o que faz |
|---|---|
| `GET /api/radio/mensagens?desde=<id>&instancia=<inst>` | as mensagens entregues depois do id e a `minimapaVersao`; outra instância (o backend reiniciou) devolve todas |
| `GET /api/radio/audio/{id}` | o WAV da mensagem |
| `POST /api/radio/teste` | a mensagem de teste, entregue na hora (só pela tela Sistema) |
| `GET /api/radio/estado` | as janelas, a voz, o que está esperando e as voltas válidas da sessão |
| `GET /api/radio/minimapa` | a pista simplificada, a volta de referência com o tempo e o pedal, o alinhamento da linha do jogo, o nome das 14 curvas e as curvas da última análise (pedido 35); desde o pedido 36, a freada da referência em cada curva (`referencia.freadas`) |
| `GET /api/radio/replay/{id}` | os dados do replay da curva de uma mensagem entregue (pedido 36); 404 sem replay |
| `GET /api/live/volta` | a volta em andamento inteira, na grade oficial |
| `GET /api/live/volta/novos?versao=<v>&desde=<seq>` | só os pontos novos e a posição do carro (pedido 35); a volta inteira só numa volta nova |
| `POST /api/teste/reproduzir`, `POST /api/teste/parar`, `GET /api/teste/estado` | só nos testes (`AT_TESTE_REPRODUTOR=1`): toca uma gravação pelo caminho do jogo, para medir a tela Ao vivo sem o jogo |
