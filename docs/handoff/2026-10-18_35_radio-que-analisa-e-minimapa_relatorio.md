# Relatório do pedido 35: o rádio que analisa as voltas, a voz no jogo, o mapa ao vivo sem travar e o minimapa

- **Pedido:** `docs/prompts/2026-10-18_35_radio-que-analisa-e-minimapa.md` (ADR 0021). **Este relatório é parcial:** parei na Parte G, como o pedido manda. Falta o teste no jogo com você.
- **Branch:** `etapa/radio-v2-e-minimapa`, criada de `develop` (`58bf2b46`), com merge em `develop`. Nada foi enviado ao remoto.
- **Commits e merge:**
  - `d10e7cb3` docs: pedido 35 e o anexo do ADR 0021
  - `999c8f56` Parte A: o pedido 31 fechado com o teste de 18/10
  - `4689a1c9` Partes C, D e E no backend: a análise, a causa na voz, o resumo com a curva, os pontos novos do mapa, o minimapa e o reprodutor de gravações
  - `042c09cb` Parte C: as falas cabem no tempo (pela conferência nas sessões de 13/10 e 18/10)
  - `4e8c3197` Partes D e C.7: o mapa ao vivo sem travar e a análise na tela
  - `ed009592` Partes B e E: o app do jogo, com a voz em três caminhos e o minimapa
  - `822c96d7` Parte H: a documentação e o ADR 0021 em `docs/decisoes/`
  - `4029c42a` Parte F.1: o teste das duas rotas novas
  - `b1af6f2d` o relatório parcial, com o handoff
  - `6e7cbee1` o merge em `develop` (até a Parte G)
  - **depois da sua captura do jogo (21/10):**
    - `3fe260ee` o mapa aproximado: a terceira janela do app do jogo, a pista detalhada, a referência com o pedal e o nome das curvas, e o aviso do minimapa que não cabia
    - o commit desta atualização do relatório, com o handoff: "Relatório parcial do pedido 35: o mapa aproximado"
    - o merge em `develop`: "Merge etapa/radio-v2-e-minimapa (pedido 35: o mapa aproximado)"
- **Arquivos de handoff** (`docs/handoff/2026-10-18_35_radio-que-analisa-e-minimapa_*`):
  - `_relatorio.md` (este arquivo);
  - `_captura_ao_vivo_com_a_analise_1920x1080.png`: a tela Ao vivo com o cartão da análise (janela de teste, com a gravação de 18/10 tocando);
  - `_captura_minimapa_fora_do_jogo_600x600.png`: o minimapa desenhado fora do jogo (Parte E);
  - `_captura_mapa_aproximado_saida_dos_boxes_720x720.png` e `_captura_mapa_aproximado_freada_da_c04_720x720.png`: o mapa aproximado desenhado fora do jogo;
  - `_conferencia_13-10.json` e `_conferencia_18-10.json`: as mensagens que o rádio daria em cada sessão (Parte F.4);
  - `_minimapa_conta_do_app_13-10.json` e `_18-10.json`: a conta do minimapa contra a conta da grade, com a referência em todos os 2.167 pontos;
  - `_minimapa_da_rota.json`: o que a rota do minimapa entregou na janela de teste;
  - `_mapa_ao_vivo_antes.json` e `_depois.json`: as medidas da Parte D;
  - `_variacao_das_medidas.json`: a variação volta a volta que deu os cortes;
  - `_conferencia_do_lua.txt`: a conferência do app do jogo contra o SDK do CSP;
  - `_testes.txt`: a saída das suítes;
  - `_scripts/`: os scripts das conferências e das medidas;
  - `.patch`: de `d10e7cb3` até o mapa aproximado (`3fe260ee`), com o código e os documentos, sem o handoff.

## Em resumo

1. **Parte A:** o caminho ao vivo não perdeu nenhuma frase em 18/10. O coach ficou calado porque, nos 3 microssetores de foco, a perda ficou abaixo do limiar dele em 44 de 48 passagens.
2. **O que o rádio diz (Parte C):**
   - a frase do coach diz a causa na voz: "Curva 11: 1,25 atrás. Mínima 64 contra 94.";
   - o resumo diz a curva em que a volta mais perdeu: "Volta 8, 4,2 atrás. Mais perdeu na curva 1: 0,7.";
   - a análise das voltas sai a cada 3 voltas válidas: "Análise das voltas 9, 12 e 13. Curva 1: 0,9 por volta: freia 46 metros antes.";
   - nas sessões de 13/10 e 18/10, todas as falas couberam no que restava da janela, e nada foi dito dentro das curvas.
3. **O mapa ao vivo (Parte D):**
   - o carro recebe 23 posições novas por segundo (eram 2,95) e é desenhado a cada quadro da tela (144 por segundo);
   - cada resposta tem cerca de 0,5 KB (eram 65 KB);
   - o backend gasta 0,05 ms de processador por resposta (eram 10,7 ms).
4. **A voz no jogo (Parte B):** três caminhos, um depois do outro, com uma linha no log do CSP por mensagem. Qual funciona só o teste no jogo vai dizer.
5. **O minimapa (Parte E):**
   - uma segunda janela do app do jogo, com a pista, o carro, o fantasma, a diferença ao vivo e as curvas da última análise;
   - fora do jogo, a conta do app ficou a 0,01 s da conta da grade (mediana) nas duas sessões;
   - o custo no jogo vai para o log a cada 10 s (o FPS com o minimapa ligado e desligado).
6. **Testes:**
   - **backend:** a suíte passa com **786 testes** (eram 777, mais os 9 novos do rádio);
   - **front:** o `tsc` passa, e o `vitest` passa com 184 testes (eram 182);
   - **o app do jogo:** a conferência passa, com as 32 chamadas da API e os 9 métodos no SDK do CSP.
7. **Falta:** o teste no jogo (Parte G), com os passos no fim deste relatório.

## Depois da sua captura do jogo (21/10): o mapa aproximado

**O que você mandou:**
- a captura do minimapa no jogo: a pista inteira, o carro e o aviso "o fantasma aparece depois da próxima passagem pela linha";
- a captura da tela Volta na vista "fantasma por curva", com o pedido: "o certo era esse mapa com zoom in; mantenha o que já está e inclua esse novo".

**O que a sua captura já mostra:**
- o app novo carregou no jogo, e o minimapa desenhou a pista e o carro;
- **o aviso de cima não cabia na janela** ("…pela lin"). Agora ele quebra a linha e cabe na largura (a faixa de cima passou de 26 para 30 px).

**O que eu fiz** (`3fe260ee`), mantendo o minimapa como estava:
- **uma terceira janela, "Mapa aproximado",** com a vista de perto da tela Volta:
  - **a câmera** segue o carro e gira com a pista, como a tela Volta. A direção vem da volta de referência perto do carro; sem ela, vem do carro;
  - **o zoom** abre com 120 m no lado menor da janela. A roda do mouse, com o ponteiro sobre a janela, vai de 50 m a 400 m;
  - **a pista detalhada** tem as mesmas camadas do mapa do app: o asfalto, a pintura (o limite em branco, os boxes em amarelo, as vias de serviço em cinza) e as zebras. Ela é desenhada uma vez numa imagem, `pista_detalhada.png` (3 px por metro, 0,56 MB), e girada em volta do carro a cada quadro;
  - **por cima:**
    - o seu traçado desde a linha, pintado pelo pedal, lido do jogo 20 vezes por segundo;
    - o traçado do fantasma até onde ele está;
    - o nome das 14 curvas;
    - o fantasma ("IA" ou "Sua melhor", com uma seta na borda se ele sair da janela);
    - o carro ("Você · V<n>");
    - a diferença numa faixa escura no alto;
- **a rota do minimapa** passou a mandar:
  - a referência em todos os 2.167 pontos da grade, com o pedal;
  - o nome das 14 curvas, na mesma posição da tela Volta.

  Ela monta tudo em cerca de 20 ms e manda 64 KB, uma vez por referência ou análise;
- **o `gerar_pista.py`** desenha a imagem e grava, na `pista.json`, onde ela fica no mundo e o nome das curvas.

**A conferência fora do jogo:**
- **a parte arriscada é girar a imagem.** Uma prévia em HTML repete as contas do app, com a referência da IA e dois instantes reais de 18/10:
  - **na saída da reta dos boxes** (`_captura_mapa_aproximado_saida_dos_boxes_720x720.png`), a pintura amarela dos boxes fica à esquerda, como na sua captura da tela Volta;
  - **na freada da C04** (`_captura_mapa_aproximado_freada_da_c04_720x720.png`), o carro e os dois traçados ficam dentro do asfalto, e a curva vira para a esquerda;
- **o minimapa com a referência completa** dá os mesmos números: a diferença a 0,010 s da conta da grade em 18/10 e a 0,011 s em 13/10 (mediana), e o fantasma a 0,46 m;
- **a conferência do app do jogo** passa com 38 chamadas da API (eram 32) e os 9 métodos, todos no SDK do CSP;
- **os testes** do minimapa cobrem o pedal de cada ponto e a posição do nome das curvas. A suíte do backend passa com 786 testes.

**O custo do mapa aproximado** entra no mesmo registro do FPS: a linha do log diz se o minimapa e o mapa aproximado estavam ligados.

## Parte A: o pedido 31 fechado e o teste de 18/10

**A.1** O relatório do pedido 31 ganhou a seção "O teste no jogo de 18/10" (`999c8f56`):
- o que aconteceu no jogo: o app carregou e ficou calado pela conferência da API;
- as duas correções do app: `7904758f` e `416ae3f7`;
- o registro do rádio contra as frases do coach.

**A.2 A sessão `2026-10-18_12-38-44` pelo coach, fora do tempo real** (com o modelo que estava ativo no teste, o backup de 17:32):
- **o coach daria 2 frases, e as 2 chegaram ao registro:** C11 na volta 4 (+1,25 s, microssetor 39) e C08 na volta 10 (+0,85 s, microssetor 33);
- **o foco de cada volta** (os 3 microssetores, contados a partir de 1):

  | voltas | foco | de onde |
  |---|---|---|
  | 1 a 9 | 3 (C01), 39 (C11) e 44 (C12) | o modelo |
  | 10 a 13 | 33 (C08), 39 (C11) e 44 (C12) | a sessão |
  | 14 | 31 (C07), 39 (C11) e 44 (C12) | a sessão |
  | 15 | 31 (C07), 33 (C08) e 44 (C12) | a sessão |
  | 16 | 31 (C07), 39 (C11) e 44 (C12) | a sessão |

- **por que o coach ficou calado:**
  - **nos microssetores de foco,** foram 48 passagens: 44 abaixo do limiar, 2 com o carro parado ou no box e as 2 frases;
  - **o limiar** é o dobro do espalhamento do próprio piloto no microssetor (a mediana menos a melhor, no modelo), de 0,49 s (C11) a 0,72 s (C08). Nas 44 passagens abaixo dele, a perda mediana contra a IA foi de 0,28 s, e o limiar mediano, de 0,67 s;
  - **fora do foco,** 240 passagens ficaram acima do limiar, mas o coach só fala nos 3 microssetores de foco (regra do pedido 15);
  - **no total,** dos 987 microssetores fechados: 599 abaixo do limiar, 113 em que você ganhou da IA, 240 acima do limiar fora do foco, 30 parado ou no box, 3 no microssetor em que a contagem começou e 2 frases.

  O silêncio é a regra do coach, e não uma perda no caminho. Foi isso que levou à análise das voltas (ADR 0021), que olha as 14 curvas.

**A.3** O caminho ao vivo não perdeu nada (nem o coach, nem a fila, nem as janelas). Não houve defeito para corrigir.

## Parte B: a voz e o cartão no jogo

**B.1 O que a API do CSP 0.2.11 permite** (`extension\internal\lua-sdk\ac_apps\lib.lua` e `rules.json`, só leitura):
- **`ui.MediaPlayer`:** `setSource` aceita uma URL ou um arquivo ("URL or a filename"), pelo Media Foundation do Windows. O som sai pelo áudio do jogo (FMOD);
- **`ac.AudioEvent.fromFile`:** só arquivo, sem URL. Não usei: o `MediaPlayer` cobre os dois casos;
- **onde o app pode ler e gravar:**
  - o `rules.json` só tira o acesso a arquivos (`withoutIO`) dos scripts de carro e de pista. Os apps (`apps/*`) têm `io.save`, `io.createDir`, `io.deleteFile` e `io.scanDir`;
  - a API não restringe a pasta. A regra de só gravar na pasta do app é nossa (ADR 0021, item 6);
  - a pasta do app vem de `ac.getFolder(ac.FolderID.ScriptOrigin)`.

**B.2 Os três caminhos, um depois do outro:**
1. **a URL do backend** (`/api/radio/audio/<id>`), como no pedido 31;
2. **o arquivo** que o backend já grava em `data/radio/audio/`: a mensagem traz o caminho (`audioArquivo`), e o app confere se o enxerga antes de tocar;
3. **o áudio baixado** com `web.get` e gravado em `voz\<id>.wav`, dentro da pasta do app. O app limpa os `.wav` dessa subpasta ao abrir e apaga o anterior quando o seguinte toca.

- **Como o app decide:**
  - um caminho tocou quando a posição do áudio anda (`currentTime`);
  - se não tocar em 2,5 s, passa ao seguinte. Na primeira mensagem, espera 5 s, porque o CSP pode estar carregando o Media Foundation;
  - o caminho que tocou fica em `voz\caminho.txt` e é o primeiro tentado na próxima vez.
- **Uma ressalva:** se a URL não tocar, a primeira mensagem sai até cerca de 5 s atrasada, e pode passar da janela. É para isso que serve a mensagem de teste do passo 5: depois dela, o app já começa pelo caminho que funciona.

**B.3 A linha no log do CSP, por mensagem:**
- `[radio_engenheiro] voz: url tocou`, com os caminhos que falharam antes entre parênteses (por exemplo, `voz: arquivo tocou (antes: url: não tocou em 5,0 s)`);
- ou `[radio_engenheiro] voz: falhou: url: ...; arquivo: ...; baixado: ...`.

**B.4 O volume:** `VOLUME_DO_RADIO = 1.0`, no começo do `radio_engenheiro.lua`, com o comentário: de 0 a 1, o volume do player; o volume geral do jogo vale por cima.

**B.5 Os scripts:** o `instalar.ps1` já apagava e copiava de novo só `apps\lua\radio_engenheiro\`. Mudou só a mensagem final, que agora cita as duas janelas.

**O cartão:** carbono e vermelho como antes. A análise fica 12 s na tela, com o resumo em até duas linhas e uma linha por curva. A janela do rádio passou a 600 × 220, com o tamanho fixo.

**O que funcionou no jogo:** a preencher depois do teste.

## Parte C: o que o rádio diz

As regras, os cortes e os exemplos estão em `docs/realidade_aumentada.md`, seção 2. O principal:

**C.1 A frase do coach com a causa:**
- **a regra:** a freada, quando a diferença do ponto de freada passa de 15 m; senão, a mínima, quando passa de 8 km/h; abaixo dos dois, sem causa;
- **por que esses cortes:** são a mediana do desvio-padrão volta a volta de cada medida, por curva e por sessão, nas 73 voltas humanas do store v2 de 11/10 a 18/10 (14,7 m e 7,7 km/h), arredondada. Abaixo disso, a diferença está dentro da sua variação normal;
- **exemplos reais:**
  - "Curva 11: 1,25 atrás. Mínima 64 contra 94." (18/10, 6,2 s);
  - "Curva 12: 1,87 atrás. Freia 54 metros antes." (13/10, 5,8 s).

**C.2 A análise das voltas:**
- **quando:** a cada 3 voltas válidas: sem a IA, com todos os microssetores medidos pelo coach e com o relógio da grade em pelo menos 90% dos pontos;
- **as curvas:** até 2, pela maior perda mediana, e só as perdidas em 2 das 3 voltas;
- **as medidas:**
  - a freada e a mínima, como no relatório de evolução;
  - **o acelerador e o traçado não estavam prontos ao vivo.** Montei-os com os canais da grade que a volta ao vivo já guarda, sem física nova:
    - a volta ao acelerador cheio é o primeiro ponto, do ápice ao fim do trecho, com o acelerador em 0,95 ou mais;
    - o traçado é a posição lateral no ponto da mínima da referência;
  - os cortes do acelerador (10 m) e do traçado (1,8 m) saem da mesma conta (10,7 m e 1,76 m);
- **a fala:** até 2 diferenças por curva, as que mais pesam (a diferença dividida pelo corte), só acima do corte;
- **o cartão:** todas as curvas, com todos os números;
- **exemplo real (18/10):**
  - o cartão: "Análise das voltas 3, 7 e 8 · C04 perde 1,04 s por volta · C01 perde 0,95 s por volta, contra a volta da IA", e uma linha por curva: "C04, esquerda: perde 1,04 s por volta (1,04 · 1,06 · 0,22); mínima 102 contra 128 km/h; freada 40 m antes; acelerador cheio 16 m depois; traçado 1,5 m mais à direita";
  - a fala: "Voltas 3, 7 e 8. Curva 4: 1,0 por volta: passa a 102 contra 128." (8,1 s).

**C.3 O resumo:** "Volta 8, 4,2 atrás. Mais perdeu na curva 1: 0,7." A curva só entra numa volta completa: numa volta com parada, "mais perdeu na curva 1: 66,4" é verdade, mas não ajuda.

**C.4 Quando cada mensagem é entregue:**
- as janelas continuam as mesmas, e nada é dito dentro das 14 curvas;
- a mensagem só sai quando a fala inteira cabe no que resta da janela, pela velocidade do carro;
- **para caber:**
  - a voz passou de 1,25x para 1,4x. A 1,25x, os números falados por extenso passavam de 6, 7 e 8 s (medido: 6,8, 8,2 e 8,5 s);
  - cada mensagem traz variantes da fala, e o rádio fica com a primeira que cabe em 6,6, 7,7 ou 8,8 s (os limites do pedido com 10% de folga);
  - o resumo vai para a frente da fila: sem isso, numa sessão real, ele chegava uma volta atrasado.
- **quanto cada tipo ocupa e onde cai,** na seção da Parte F.4.

**C.5 O que não muda:** o coach decide as frases (o foco, o limiar e no máximo 3 por volta), e a análise sai no máximo uma vez a cada 3 voltas válidas. Nenhum modelo, store ou critério mudou. O coach só ganhou um campo de leitura na `ultima_volta` (`completa`).

**C.6 O registro da análise** (`data/radio/<sessão>.jsonl`):
- tem as voltas analisadas, as curvas com a perda em cada uma das 3 voltas, as diferenças ditas e a referência;
- **basta para medir se a curva citada melhorou,** com uma ressalva: o número da volta é o do contador do jogo, e o store numera pela ordem no arquivo. O cruzamento é pelo tempo da volta, que o resumo traz no mesmo registro. A conta está em `docs/realidade_aumentada.md`, seção 6.

**C.7 A tela Ao vivo** mostra a análise como as outras mensagens, com o texto pronto do backend e uma linha por curva (`_captura_ao_vivo_com_a_analise_1920x1080.png`).

## Parte D: o mapa ao vivo sem travar

**Como medi, sem o jogo:**
- criei um reprodutor só de teste: `POST /api/teste/reproduzir` toca uma gravação em tempo real pelo mesmo caminho do jogo (a projeção do coach, a volta ao vivo e o barramento);
- ele só existe com `AT_TESTE_REPRODUTOR=1`, e o caminho ao vivo não mudou;
- a medição foi numa janela de teste ("[teste]" no título), com a pasta isolada e o backend na 8011, tocando a sessão de 18/10. Depois, a janela foi fechada.

**Antes e depois** (20 s cada, a tela Ao vivo aberta):

| medida | antes | depois |
|---|---|---|
| redesenhos do mapa por segundo | 10 | 144 (cada quadro da tela) |
| respostas por segundo | 2,95 | 24,1 |
| tamanho da resposta (mediana) | 65 KB | 491 B |
| tempo da resposta (mediana / máximo) | 14,6 / 352 ms | 3 / 447 ms |
| posições novas do carro por segundo | 2,95 | 23,2 |
| posições desenhadas por segundo | 2,95 | 140,6 |
| processador do backend por resposta | 10,7 ms (cerca de 32 ms por segundo) | 0,053 ms (cerca de 1,3 ms por segundo) |
| script da página | 26,6 ms/s | 51,5 ms/s |
| tarefas da página | 39,8 ms/s | 105 ms/s |

- **O que mudou:**
  - a tela pede só os pontos novos (`/api/live/volta/novos`) num relógio de 30 ms, sem pedir de novo com uma leitura em andamento. A volta inteira vem só na abertura e numa volta nova;
  - os pontos ficam fora do React. O componente só renderiza de novo numa volta nova, e o painel de leitura acompanha 5 vezes por segundo;
  - o mapa é desenhado a cada quadro, e o carro anda entre duas posições pela geometria oficial, na velocidade dele (só desenho, até 250 ms à frente);
  - a pista (asfalto, pintura e zebras) é desenhada uma vez num bitmap e refeita só quando o zoom ou o tamanho mudam;
  - as rotas da volta respondem pelo `json` direto: a volta inteira caiu de 10,7 ms para 1,33 ms de processador.
- **O custo que subiu:** a página gasta mais (51,5 ms de script por segundo), porque desenha 144 vezes por segundo. É cerca de 5% de um núcleo, no processo da tela. O backend, que é quem grava, passou a gastar 25 vezes menos.
- **O máximo de 447 ms** foi uma resposta só, na abertura (a volta inteira). As outras ficaram perto de 3 ms.

**D.4 A tela Volta continua igual:** é o mesmo componente, com o mesmo replay. A fonte ao vivo é opcional e só a tela Ao vivo a usa. Os testes da tela Volta passam.

**D.5 A gravação não pode piorar:** a comparação é no teste no jogo, com as voltas com a tela Ao vivo aberta e com outra tela. Faço depois do seu aviso.

## Parte E: o minimapa no jogo

**E.1 O que a API tem:**
- **o carro:** `ac.getCar(0).position` (a posição no mundo), `.lapTimeMs` e `.lapCount`;
- **a pista uma vez:** `ui.ExtraCanvas`, um canvas guardado que é desenhado uma vez e reaproveitado com `ui.drawImage`;
- **o FPS:** `ac.getSim().fps`.

**E.2 O que o minimapa mostra** (a captura fora do jogo: `_captura_minimapa_fora_do_jogo_600x600.png`):
- **a pista tratada:**
  - as duas bordas do asfalto da geometria oficial, simplificadas para 271 pontos cada;
  - desenhada uma vez no canvas, com a linha do s = 0;
  - a mesma orientação do mapa do app;
- **o carro:** do próprio jogo, a cada quadro, sem pedir nada ao backend. A posição do jogo está no mesmo sistema de coordenadas da geometria oficial: é a que o coach projeta;
- **o fantasma da referência escolhida na Coleta:**
  - a volta (a posição e o tempo, 362 pontos) é baixada uma vez, quando o app abre e quando a referência ou a análise mudam. As mensagens do rádio trazem a versão (`minimapaVersao`);
  - **o alinhamento dos relógios:** o cronômetro do jogo zera na linha do jogo, depois do s = 0; o tempo da referência conta desde o s = 0. O backend manda o tempo da referência na linha do jogo (`tempoNaLinhaDoJogoS`), e o app soma: **tempo da referência = cronômetro do jogo + tempoNaLinhaDoJogoS**;
  - **a distância até a linha:** o backend usa a medida do store (1,495 m, pedido 34) e, sem ela, a registrada (1,463 m, pedido 33). Os 3 cm de diferença valem menos de 1 ms;
  - o fantasma aparece depois da primeira passagem pela linha, porque o cronômetro da volta de saída dos boxes não serve;
- **a diferença ao vivo, calculada no app:**
  - é o tempo do carro menos o da referência no ponto dela mais perto do carro, projetado no segmento. É a conta da tela Volta;
  - **por que no app:** a posição do carro já está lá, a cada quadro, e a referência inteira também. Pelo backend, a diferença chegaria a cada 0,3 s, ocuparia um dos dois pedidos que o CSP permite e pararia com o backend fora do ar;
- **as curvas da última análise:** marcadas no contorno, com um círculo e o nome.

**A conferência fora do jogo:** não há Lua neste computador. Portei a conta do app para Python, linha a linha (`_scripts/minimapa_offline.py`), e a comparei com a conta da grade nas duas sessões:

| sessão | amostras | diferença: app menos grade (mediana / p95) | fantasma ao longo da pista (mediana / p95) | acima de 0,5 s |
|---|---|---|---|---|
| 13/10 | 63.862 | 0,011 / 0,062 s | 0,47 / 0,96 m | 64 (0,1%), todas com o carro a mais de 20 m da linha central |
| 18/10 | 75.387 | 0,010 / 0,039 s | 0,46 / 0,96 m | 669 (0,9%), todas com o carro a mais de 20 m da linha central |

- **No fim de cada volta,** a diferença do app dá o tempo da volta menos o da referência: por exemplo, 5,46 s para 1:30,240 contra 1:24,829 (5,41 s).
- **As amostras a menos de 5 m do s = 0** ficaram fora da comparação: a grade emenda ali, e o app não usa a grade.

**E.3 As cores** são as da tela Volta: o carro como "você" (branco, com o anel vermelho) e o fantasma como "fantasma" (o miolo escuro, com o anel claro). A diferença fica em laranja quando você perde e em azul quando ganha. Nada de marca alheia.

**E.4 A rota nova:** `GET /api/radio/minimapa` monta tudo em 9 ms e manda 18,8 KB. Com o backend fora do ar, o app usa a `pista.json` da pasta dele (9,2 KB, gerada por `tools/csp_app/gerar_pista.py`).

**E.5 Com o backend fora do ar:**
- a pista e o carro continuam;
- sem a referência, aparece "sem fantasma: backend fora do ar", discreto, no alto;
- **uma escolha minha, para você confirmar:** se o backend cair depois de o app ter baixado a referência, o fantasma continua, porque os dados já estão no app, e o canto de baixo diz "sem backend". Se preferir que o fantasma suma, é uma linha.

**E.6 Duas janelas:** "Rádio" e "Minimapa" aparecem separadas na barra de apps do jogo. O minimapa tem 300 × 300 e pode ser redimensionado de 200 a 640.

**E.7 O custo no jogo:**
- **a API tem como medir:** a cada 10 s, o app escreve no log do CSP o FPS do jogo (lido a cada 1 s), com a média, a mínima e a máxima, e se o minimapa estava ligado ou desligado. O formato é `[radio_engenheiro] fps: média <n> (mín <n>, máx <n>) em 10 s; minimapa ligado`;
- **a cada quadro,** o app desenha a imagem da pista, dois círculos e o texto, e procura o ponto mais perto em cerca de 34 segmentos. A pista inteira só é redesenhada quando muda;
- **o número medido:** a preencher depois do teste. No passo 6, você desliga o minimapa numa volta de cada bloco.

## Parte F: testes e conferência sem o jogo

**F.1 Os testes do backend** (`backend/tests/test_radio.py`, 21 testes, 9 deles novos neste pedido):

| o que o pedido pede | o teste |
|---|---|
| a frase com a causa: os dois casos e o corte | `test_a_causa_principal_freada_antes_da_minima_e_os_cortes` |
| a análise: só curvas perdidas em 2 de 3, no máximo 2, o texto com vírgula e o lado por extenso | `test_a_analise_so_curvas_perdidas_em_2_de_3_e_no_maximo_2` |
| a análise a cada 3 voltas válidas, esperando uma janela em que caiba, e o registro | `test_a_analise_sai_a_cada_3_voltas_validas_espera_a_janela_e_vai_para_o_registro` |
| o resumo com a curva de maior perda | `test_resumo_com_a_curva_de_maior_perda` |
| o limite do coach continua em 3 frases por volta | `test_o_radio_nao_cria_frases_o_limite_do_coach_continua` |
| a fala que cabe | `test_a_voz_fica_com_a_primeira_fala_que_cabe` e `test_uma_por_vez_e_so_quando_a_fala_inteira_cabe_na_janela` |
| as rotas novas: a de pontos novos e a do minimapa | `test_as_rotas_novas_pontos_novos_e_minimapa`, `test_volta_ao_vivo_manda_so_os_pontos_novos_e_guarda_a_volta_fechada` e `test_o_minimapa_monta_a_pista_a_referencia_e_o_relogio_da_linha_do_jogo` |
| a versão do minimapa nas mensagens | `test_as_mensagens_dizem_a_versao_do_minimapa` |

**F.2 O app do jogo** (`tools/csp_app/conferir_lua.py`, contra o `lib.lua` do CSP instalado; `_conferencia_do_lua.txt`):
- o léxico e os blocos passam;
- **a API usada** (32), todas no SDK: `JSON.parse`, `ac.FolderID`, `ac.getCar`, `ac.getFolder`, `ac.getSim`, `ac.log`, `io.createDir`, `io.deleteFile`, `io.fileExists`, `io.load`, `io.save`, `io.scanDir`, `os.preciseClock`, `rgbm`, `setInterval`, `ui.Alignment`, `ui.ExtraCanvas`, `ui.MediaPlayer`, `ui.drawCircle`, `ui.drawCircleFilled`, `ui.drawImage`, `ui.drawLine`, `ui.drawRectFilled`, `ui.dwriteDrawText`, `ui.dwriteDrawTextClipped`, `ui.pathClear`, `ui.pathLineTo`, `ui.pathStroke`, `ui.windowSize`, `vec2`, `web.get` e `web.timeouts`;
- **os métodos** (9), todos no SDK: `clear`, `currentTime`, `dispose`, `pause`, `play`, `setAutoPlay`, `setSource`, `setVolume` e `update`. A conferência dos métodos é nova (pedido 35);
- **os campos lidos,** conferidos à mão: `position`, `lapTimeMs` e `lapCount` em `ac.StateCar`; `fps`, `isPaused` e `isReplayActive` em `ac.StateSim`; e `ui.MediaPlayer.supportedAsync`;
- nenhuma função da API é conferida com `type(...) == 'function'`.

**F.3 O front:**
- o `tsc` passa;
- o `vitest` passa com 184 testes (eram 182). Os 2 novos são o acumulador dos pontos ao vivo (`voltaAoVivo.test.ts`) e o cartão da análise (`radio.test.ts`);
- os testes da tela Volta continuam os mesmos e passam.

**F.4 A conferência nas gravações de 13/10 e 18/10,** fora do tempo real, com a voz de verdade (`_conferencia_13-10.json` e `_conferencia_18-10.json`). Todas as falas couberam no que restava da janela na entrega:

| sessão | tipo | mensagens | a fala dura | onde foi entregue (o que restava da janela) |
|---|---|---|---|---|
| 18/10 | resumo | 13 | 6,1 a 7,7 s | 12 na reta oposta, perto de 723 m (7,8 a 8,7 s); 1 na reta dos boxes (12,3 s) |
| 18/10 | frase do coach | 2 | 5,9 a 6,2 s | reta dos boxes, 3.697 m (13,8 e 15,6 s) |
| 18/10 | análise | 2 | 7,9 e 8,1 s | reta dos boxes, 3.698 m (12,9 e 12,2 s) |
| 13/10 | resumo | 13 | 6,1 a 7,7 s | 11 na reta oposta; 2 na reta dos boxes |
| 13/10 | frase do coach | 6 | 5,8 a 6,5 s | reta dos boxes (5 em 3.697 m e 1 em 3.953 m) |
| 13/10 | análise | 1 | 6,8 s | reta dos boxes, 3.698 m (12,3 s) |

- **A janela entre a C05 e a C06** (1.637 a 1.818 m, cerca de 3 s) não recebeu nenhuma fala: nenhuma cabe nela.
- **Os textos de 18/10, na ordem:**

  | volta do carro | tipo | fala |
  |---|---|---|
  | 3 | resumo | "Volta 2, 1 minuto e 33,3. 8,46 atrás da IA." |
  | 4 | resumo | "Volta 3, 5,4 atrás. Mais perdeu na curva 4: 1,0." |
  | 4 | coach | "Curva 11: 1,25 atrás. Mínima 64 contra 94." |
  | 5 | resumo | "Volta 4, 1 minuto e 40,1. 15,24 atrás da IA." |
  | 7 | resumo | "Volta 6, 1 minuto e 45,4. 20,54 atrás da IA." |
  | 8 | resumo | "Volta 7: 1 e 30,8, 6,0 atrás. Mais perdeu na curva 4: 1,1." |
  | 9 | resumo | "Volta 8, 4,2 atrás. Mais perdeu na curva 1: 0,7." |
  | 9 | análise | "Voltas 3, 7 e 8. Curva 4: 1,0 por volta: passa a 102 contra 128." |
  | 10 | resumo | "Volta 9, 5,6 atrás. Mais perdeu na curva 14: 1,0." |
  | 10 | coach | "Curva 8: 0,85 atrás. Mínima 74 contra 90." |
  | 11 | resumo | "Volta 10, 2 minutos e 39,7. 74,92 atrás da IA." |
  | 12 | resumo | "Volta 11, 1 minuto e 44,3. 19,49 atrás da IA." |
  | 13 | resumo | "Volta 12, 4,5 atrás. Mais perdeu na curva 1: 0,9." |
  | 14 | resumo | "Volta 13, 8,5 atrás. Mais perdeu na curva 6: 3,1." |
  | 14 | análise | "Análise das voltas 9, 12 e 13. Curva 1: 0,9 por volta: freia 46 metros antes." |
  | 15 | resumo | "Volta 14, 5,1 atrás. Mais perdeu na curva 1: 0,9." |
  | 16 | resumo | "Volta 15, 4,9 atrás. Mais perdeu na curva 1: 0,9." |

  - **as voltas 2, 4, 6, 10 e 11 saíram sem a curva:** o coach não as mediu completas, ou a volta ao vivo não cobriu 90% da grade. Nenhuma delas entrou na análise;
  - **a volta 5 não tem resumo:** ela durou 5:34, com uma parada, e o coach não mediu o período dela. A gravação não tem nenhuma amostra com a IA.
- **Os textos de 13/10** estão no JSON. Duas observações:
  - **dois resumos saíram como "Volta 10"** (1:33,120 e 1:29,767). Nessa gravação, o contador de voltas do jogo não andou numa passagem pela linha, e o coach tira o número da volta dele (`driving_coach.py:280`). Em 18/10 isso não acontece. Não mexi no coach;
  - **a análise das voltas 6 a 8** mostra "mínima 104 contra 104 km/h" na linha da C01: o cartão mostra todos os números, como o pedido manda, e a fala diz só a freada (36 m antes).

**F.5 As suítes** (`_testes.txt`):
- **backend:** `pytest tests` passa com 786 testes, em 8 min 14 s;
- **front:** o `tsc` e o `vitest` passam.

**F.6 As capturas:**
- a tela Ao vivo com a análise: `_captura_ao_vivo_com_a_analise_1920x1080.png`;
- **o minimapa fora do jogo:** `_captura_minimapa_fora_do_jogo_600x600.png`:
  - o app Lua não roda fora do jogo. A prévia repete o desenho dele num canvas HTML: a mesma projeção, as margens, as cores, os raios e os textos;
  - os dados são o minimapa que a rota entregou na janela de teste (a referência "sua melhor", as curvas C07 e C14 da última análise) e um instante real de 18/10 (a volta de 1:29,059, aos 40 s): o fantasma 1,15 s à frente;
  - o fundo cinza está no lugar da imagem do jogo. A captura foi feita pelo Edge sem janela.

## Parte H: a documentação

- **`docs/realidade_aumentada.md`,** reescrito:
  - a frase com a causa, o resumo e a análise, com exemplos reais;
  - os cortes e o porquê;
  - quanto cabe em cada janela;
  - os três caminhos da voz (o que funcionou no jogo fica para depois do teste);
  - o minimapa: o que mostra, de onde vem cada dado e o custo (o medido no jogo fica para depois do teste);
  - o registro e como medir se a curva citada melhorou;
  - as rotas novas.
- **O ADR 0021** foi para `docs/decisoes/` (com `git mv`, que tirou a pasta `docs/prompts/anexos-35/`), com a linha no índice. A linha do 0020 passou a dizer "item 4 refinado por 0021".
- **`docs/dashboard_inventario.md`:** "O que o pedido 35 entregou", no fim da seção 7.

## Parte G: o teste no jogo (com você)

**Antes de começar:**
- **o front já está construído** com o código deste pedido (`frontend/dist`, de 18/10 às 20:40). Não precisa rodar o build;
- **abrir o app do repositório regrava o cache da pista** (`data/cache/tracks/vhe_interlagos_gp_kn5_surface_interval_geometry.json`):
  - já guardei uma cópia;
  - o hash de agora é `dbac662a…83db598`;
  - depois do teste, eu comparo e, se mudar além do `generatedAt`, restauro;
- **a sessão vai ter 6 voltas,** mais de 5. Então ela entra no coach na próxima rodada;
- **se você já tinha começado o teste,** recomece do passo 1: o app do jogo mudou (é preciso instalar de novo) e o backend também (é preciso abrir o app do repositório de novo).

**Os passos:**

1. **Feche o jogo.** Feche também o app instalado, inclusive na bandeja do Windows: os dois usam a porta 8000, e o app do jogo fala com a 8000.
2. **Instale o app do jogo de novo.** Num PowerShell:
   ```
   powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Dokas\Desktop\f1-telemetry-analyzer\tools\csp_app\instalar.ps1
   ```
   - aceite a pasta sugerida (`D:\SteamLibrary\steamapps\common\assettocorsa`) com Enter;
   - confira o que ele vai copiar;
   - responda `s`.

   O `-ExecutionPolicy Bypass` vale só para esse comando e não muda a configuração do Windows.
3. **Abra o app pelo repositório,** no mesmo PowerShell, um comando por linha:
   ```
   cd C:\Users\Dokas\Desktop\f1-telemetry-analyzer
   $env:AT_BACKEND_USE_PYTHON_RUNNER = 'true'
   cd desktop
   npm.cmd run desktop:prod:autostart
   ```
   Espere o "backend pronto" no topo da tela.
4. **Abra o Assetto Corsa** em Interlagos, com o `rss_formula_rss_3_v6_2026`. Na barra de apps, no lado direito da tela, ligue as três janelas do app:
   - **"Rádio · Sistema de Telemetria e Otimização de Trajetórias":** não tem fundo e só aparece quando chega uma mensagem;
   - **"Minimapa · Sistema de Telemetria e Otimização de Trajetórias":** ponha num canto, sem cobrir o centro da tela. O fantasma só aparece depois da primeira passagem pela linha;
   - **"Mapa aproximado · Sistema de Telemetria e Otimização de Trajetórias":** ponha em outro canto. Com o ponteiro sobre ele, a roda do mouse muda o zoom.

   Se a barra mostrar só "Rádio do engenheiro", abra-o: as janelas ficam dentro dele. Se não achar alguma, me diga o que aparece.
5. **No app, mande a mensagem de teste:** tela **Sistema**, aba Diagnóstico, botão **"Mandar mensagem de teste"**.
   - No jogo, aparece o cartão "TESTE", e a voz toca.
   - Se a primeira forma de tocar não funcionar, o app tenta a seguinte. A voz pode demorar até uns 10 s nessa primeira vez.
6. **Ande 6 voltas sem a IA:**
   - **as 3 primeiras com a tela Ao vivo aberta** no app;
   - **as 3 últimas com a tela Sessões aberta;**
   - **na 2ª volta,** desligue o minimapa e o mapa aproximado na barra de apps e ligue os dois de novo na linha seguinte. **Na 5ª,** desligue só o mapa aproximado. Assim, o log tem o FPS com os dois mapas ligados, com os dois desligados e só com o minimapa.

   O que esperar:
   - as frases do coach e os resumos chegam nas retas, com a causa e a curva na voz;
   - **a análise** chega depois da 3ª volta válida, na reta dos boxes. Ela precisa de 3 voltas completas, sem parada.
7. **Feche o jogo e o app** e me avise: **"testei o rádio v2 no jogo"**.

**Se algo não funcionar:**
- **o app do jogo** escreve as linhas `[radio_engenheiro]` no log do CSP (`C:\Users\Dokas\Documents\Assetto Corsa\logs\custom_shaders_patch.log`): a voz de cada mensagem, o minimapa e o FPS;
- **o backend** escreve em `logs\backend.log` do repositório.

Não precisa copiar nada: eu leio os dois.

**Depois do seu aviso, eu:**
- confiro o registro do rádio contra as frases do coach e as análises;
- leio, sem mudar nada, as linhas `[radio_engenheiro]` do log do CSP: o caminho da voz e o FPS com os mapas ligados e desligados;
- comparo a gravação nas voltas com a tela Ao vivo aberta e com a tela Sessões: as amostras repetidas, os buracos de 50 ms ou mais e o p99 do relógio do gravador (as medidas do pedido 33);
- confiro o cache da pista;
- completo este relatório e as partes "a preencher" de `docs/realidade_aumentada.md`.

## O que falta e o que precisa de decisão

**Falta, deste pedido:** o teste no jogo (Parte G) e o que vem depois dele (o caminho da voz, o custo dos dois mapas e a gravação com a tela Ao vivo aberta e fechada).

**Para você decidir:**
1. **O fantasma com o backend fora do ar** (Parte E.5): ele continua se já tinha sido baixado. Manter ou esconder?

**As decisões de antes, ainda abertas:**
1. **O CSV de anotações:** normalizar o fim de linha, que está misturado.
2. **A referência de 1:27,014:** manter ou não, já que tem 9,2% fora do corredor.

**Nenhuma trava** apareceu neste pedido. Nenhum pacote foi instalado, e nada foi gravado na pasta do jogo nem no app instalado. As janelas de teste foram fechadas.
