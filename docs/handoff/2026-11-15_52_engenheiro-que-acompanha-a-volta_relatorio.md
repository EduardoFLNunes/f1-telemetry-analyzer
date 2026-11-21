# Pedido 52: relatório

- **Pedido:** `docs/prompts/2026-11-15_52_engenheiro-que-acompanha-a-volta.md` (o engenheiro que acompanha a volta).
- **Pasta e branch:** `C:\Users\Dokas\Desktop\f1-telemetry-analyzer`, `etapa/engenheiro` (a partir de `develop` em `14fe1ca0`, com o merge do 51, `c4869295`).
- **Atualização de 16/11 e 17/11 (as duas seções no fim):** as decisões estão no ADR 0033 (emenda, itens 1 a 10) e no código.
  - A B.4 e a D.1 foram refeitas: o feedback com o engenheiro perde a causa na voz em 6 mensagens, contra 42 antes.
  - A suíte do backend passou: **1069 testes**.
  - **Pronto para o seu teste no jogo (a Parte E).**
- **A atualização de 20/11 (a última seção):**
  - as suas decisões estão no ADR 0033 (`73c4186c`) e no código (`9a40c004`, com o app do jogo 0.8.0);
  - a D.1 foi refeita com as três variantes do molde, e a D.2 tem a prévia da janela e os áudios;
  - a suíte do backend passou (**1080 testes**);
  - **parado antes do novo teste no jogo:** você escolhe o molde ouvindo os áudios.
- **A decisão de 20/11 sobre o molde (a última seção):** você escolheu o **(b)**. Ela está no ADR 0033 (`e6147005`, antes do código), e o (b) é o padrão no código. **Parado antes do teste no jogo:** falta o seu "pode instalar".
- **A Parte E (20/11), a seção "Parte E: o teste no jogo":**
  - o teste no jogo foi feito, e a leitura E.3 está feita, com o foco na voz e no tempo;
  - **parado para a sua decisão:** nenhum código foi mudado depois do teste;
  - arquivos novos: `_e3_voltas.py`, `_e3_analise.py` e `.json`, `_e3_falas_curtas.py` e `.json`.
- **Situação antes da atualização:** **parado na Parte E, como o pedido manda.** As Partes A a D e a documentação da F estão feitas e commitadas. Falta o seu teste no jogo ("rodei o engenheiro"); depois dele, a minha leitura da sessão, o merge em `develop` e o instalador 0.9.0. Há **três pontos para a sua decisão** (a seção "O que precisa de decisão").
- **Commits** (em `etapa/engenheiro`):
  - `227e46cc` Pedido 52: o texto do pedido
  - `1578276f` Parte A: o ADR 0033, antes do código
  - `78869c7d` Parte B: os marcos da pista (só leitura dos kn5), o ruído por trecho e a conferência na volta do modelo
  - `626db885` Parte C: o engenheiro no rádio e no app do jogo (0.9.0-engenheiro; app do jogo 0.7.0)
  - `d185d927` Partes D e F: as conferências sem jogo, os testes, a documentação e o relatório
  - `ef0251a0` a suíte do backend (1062 passando), a conferência da rota e o relatório
  - `fa1262ed` atualização de 16/11: as decisões no ADR 0033, antes do código
  - `a95c0843` atualização de 16/11: as decisões 1 a 4 e 6 no código, os testes e a documentação
  - `0bbb85c8` o relatório da atualização (parado antes da D.1)
  - `cd74772c` o termo "freada" no relatório
  - `1edbebf3` "frenagem" no lugar de "freada" no que o piloto ouve e lê (ADR 0033, emenda, item 9)
  - `eb526234` a pisada em andamento na saída do trecho anterior conta desde o começo (a C10; item 10)
  - `a724ff76` a B.4 com a voz curta, a D.1 refeita e a saída da suíte (os arquivos de dados)
  - `063977be` o relatório com a B.4, a D.1 refeita e a suíte
  - `f1c60d00` a leitura do teste no jogo (E.3)
  - `73c4186c` atualização de 20/11: as decisões no ADR 0033, antes do código
  - `9a40c004` atualização de 20/11: o código, o app do jogo 0.8.0, os testes e a documentação
  - `d0a13eba` atualização de 20/11: a D.1 com as três variantes, a D.2, as suítes e o relatório
  - `e6147005` a decisão de 20/11 sobre o molde: o (b), no ADR 0033, antes do código
  - o commit do (b) como padrão no código, do teste e deste relatório
- **Merge:** nenhum (depois do teste no jogo). **Envio:** nenhum feito por mim (os comandos estão no fim).
- **Arquivos de handoff** (`docs/handoff/2026-11-15_52_engenheiro-que-acompanha-a-volta_…`):
  - `_relatorio.md` (este);
  - `_marcos.json` (a tabela dos marcos, cópia do arquivo do app), `_marcos.png` e `_figura_marcos.py` (a figura da B.3);
  - `_ruido_por_trecho.json` (o ruído de cada trecho, cópia do arquivo do app);
  - `_conferencia_da_volta_do_modelo.json` (os pontos, os blocos, as placas e as frases dos 15 trechos);
  - `_duracao_dos_avisos.py` e `_duracao_dos_avisos.json` (a C.3);
  - `_radio_offline.py`, `_radio_contar.py` e `_radio_com_e_sem.json` (a D.1);
  - `_previa.py`, `_previa.html` e `_previa.png` (a D.2);
  - `_testes.txt` e `_conferir_lua.txt` (a D.4).

## Parte 0: a pasta

- A pasta principal estava em `develop` (`14fe1ca0`), com o merge do 51 (`c4869295`) e só o texto deste pedido sem commit. O app do repositório e o `acs.exe` fechados; o `acs.exe` também estava fechado em cada conta pesada (a leitura dos kn5, a voz e a D.1).
- **O brief da sessão que me abriu dizia que o 51 tinha parado no meio da Parte C.** Não confere: o 51 está terminado e em `develop` desde 15/11, 17:38 (o relatório dele e a nota da sessão do 51). O 52 não dependia de nada parado.
- A branch `etapa/engenheiro` foi criada a partir de `develop`, e o texto do pedido é o primeiro commit (`227e46cc`). A pasta do 47 e a do 48 não foram tocadas.

## Parte A: o ADR 0033

`docs/decisoes/0033-o-engenheiro-que-acompanha-a-volta.md`, com a linha no índice, no commit **`1578276f`**, antes de qualquer código e antes de ler os arquivos da pista. O 0033 era o próximo número livre.

**O que eu fixei onde o pedido deixava lacuna** (tudo no ADR, antes do código):
- a melhor passagem é o menor tempo do trecho entre a "Sua melhor volta" (store) e as voltas que contaram na sessão, antes da volta medida;
- um trecho na lista sem causa acima do corte (e o trecho da chegada, sem curva) fica só com a perda, sem frase, sem voz e sem marca;
- `v` em `s_fala` é a velocidade da referência na freada; na hora, o aviso só sai se o tempo até a freada, na velocidade do carro, for pelo menos a fala mais 1,0 s;
- **a voz diz a frase do trecho (freie, vire ou acelere) nos trechos em que a referência freia**, que é como li "o aviso de freada: só nos trechos da lista em que a referência freia" junto com "a duração de cada aviso possível dos 15 trechos";
- a marca é uma faixa de 1,5 m × 6 m centrada na linha da referência, e acompanha a janela do engenheiro (desligada a janela, some a marca);
- a volta lenta, uma vez lenta, fica lenta até a linha (cobre "uma volta que já teve uma rodada").

**O que não bateu com o repositório** (no ADR, contexto, item 4): o pedido cita seis causas como "as medidas do 45". Duas não são:
- **"freada leve":** o rádio do 45 não mede a força do freio. Medida contra a volta do modelo, ela julgaria a amplitude do pedal da IA, o que o ADR 0032 (item 5) proíbe;
- **"marcha acima":** o rádio não mede a marcha; a volta ao vivo não guarda a marcha.

As duas ficaram **fora deste pedido** (nada sem medida, ADR 0012), para a sua decisão. As outras quatro são as do 45, e acrescentei "freada tarde" (a mesma medida da "freada cedo", com o outro sinal; a ação também é "freie").

## Parte B: os marcos da pista

**A leitura** (só leitura, `core/kn5/kn5_marcos.py` e `core/engenheiro/marcos.py`): o leitor de kn5 do projeto não guarda o UV, a normal nem a textura de cada material, e lê o material de um campo errado (o número de filhos do nó). Escrevi um leitor à parte, com o mesmo formato binário, que lê o arquivo inteiro sem sobra de bytes. Os dois kn5 foram abertos só para leitura; nada foi escrito na pasta da pista nem na do jogo.

- `vhe_interlagos.kn5`: sha256 `ce1f3bb2f93d419a3fc571712c051f4c2ce5a22e9e8397b7f456cb7abe1da9d3` (o mesmo do relatório do 51);
- `obj_extra.kn5`: sha256 `c88965b5d71edad3a5c181abb5ad89dfba15cbaab129f39b9889719c0204bfbb`;
- a geometria: `geometry_id` `0ed16f0dd2225990`.

**Duas leituras fora do item 3 do contexto, registradas:**
- **li o `models_gp.ini` da pasta da pista** (só leitura, para conferir a posição dos kn5: todas 0,0,0). Ele não está na exceção do pedido; foi um engano meu, e não usei nada dele no código;
- **não li o `map.png`:** a B.3 pede a figura sobre ele, mas ele fica fora da exceção de leitura ("da pista, só a leitura do contexto, item 3"). A figura foi desenhada sobre a própria geometria oficial (a linha central e as bordas do corredor). Se quiser a figura sobre o `map.png`, é só autorizar a leitura dele.

**O valor das placas:** pela coluna da textura nas faces com número. Olhei as texturas: no `DISTMARKERB.DDS`, 50, 100 e 200 nos três primeiros quartos da largura (o último é o verso, em branco); no `DISTMARKER.DDS`, o mesmo na metade de baixo (a de cima é a moldura de metal). A frente de toda placa com número olha para o carro que chega (cosseno de 1,0 com o sentido contrário ao da pista).

**O arquivo:** `data/reference_models/vhe_interlagos.marcos.json`, ao lado da volta do modelo, **fora do git** pela regra que já existia (`data/reference_models/*.json`). O instalador o leva pelo filtro novo `*.marcos.json` no `extraResources`, como no 51. A cópia está no handoff.

### A tabela dos marcos (54)

| tipo | s (m) | lado | valor | Cowork | diferença |
|---|---:|---|---|---:|---:|
| pórtico da largada | 3,1 | atravessa | | 3 | 0,1 |
| placa de freada | 16,4 | direita | 200 | 16 | 0,4 |
| placa de freada | 114,0 | direita | 100 | 114 | 0,0 |
| placa de freada | 156,1 | direita | 50 | 156 | 0,1 |
| posto de bandeira | 175,0 | direita | | 175 | 0,0 |
| placa do DRS | 741,4 | direita | | 741 | 0,4 |
| posto de bandeira | 865,3 | esquerda | | 865 | 0,3 |
| passarela | 939,5 | atravessa | | 940 | 0,5 |
| placa de freada | 1.141,2 | direita | 200 | 1.141 | 0,2 |
| posto de bandeira | 1.200,6 | direita | | 1.201 | 0,4 |
| placa de freada | 1.227,2 | direita | 100 | 1.227 | 0,2 |
| placa de freada | 1.272,8 | direita | 50 | 1.273 | 0,2 |
| placa de freada | 1.857,8 | esquerda | 100 | 1.858 | 0,2 |
| placa de freada | 1.903,4 | esquerda | 50 | 1.903 | 0,4 |
| placa de freada | 3.108,5 | esquerda | 100 | 3.109 | 0,5 |
| placa de freada | 3.154,2 | esquerda | 50 | 3.154 | 0,2 |
| posto de bandeira | 3.512,6 | direita | | 3.513 | 0,4 |
| posto de bandeira | 3.647,1 | esquerda | | 3.647 | 0,1 |
| passarela | 3.782,2 | atravessa | | 3.782 | 0,2 |
| posto de bandeira | 3.788,9 | esquerda | | 3.789 | 0,1 |
| placa do DRS | 3.890,0 | direita | | 3.890 | 0,0 |
| posto de bandeira | 3.992,6 | direita | | 3.993 | 0,4 |
| posto de bandeira | 4.327,0 | esquerda | | 4.327 | 0,0 |

**As 31 zebras** (começo–fim em m, lado): 261–351 e; 351–420 d; 366–407 d; 425–743 e; 701–827 d; 1310–1410 e; 1335–1361 e; 1377–1472 d; 1476–1584 e; 1615–1697 d; 1941–1997 d; 2079–2125 d; 2134–2264 e; 2231–2336 d; 2260–2306 d; 2359–2509 e; 2503–2596 d; 2596–2805 d; 2630–2768 d; 2687–2732 d; 2751–2787 e; 2844–3019 e; 3034–3093 d; 3170–3366 e; 3211–3232 d; 3247–3336 d; 3466–3477 e; 3469–3475 e; 3486–3502 e; 3503–3540 e; 3613–3671 e.

### A conferência, sem jogo

- **Os marcos do contexto, a até 2 m em s:** **todos os 23 conferem** (a maior diferença é 0,5 m), e são 31 zebras, como o Cowork contou. **Nenhum falta.**
- **O que sobrou na leitura e ficou fora** (relatado, como o pedido manda):
  - uma "passarela" em 3,1 m (`ADVERT_OV02`, 2 peças a 23 m de altura): é o painel do próprio pórtico, no mesmo s; ficou como parte do pórtico;
  - uma "passarela" em 2.532,4 m (`ADVERT_OV02` e `OVERHEADAD_DETAILS`, 2 peças a 1 m de altura): vai só do centro à borda esquerda e não atravessa a pista; ficou fora;
  - 3 peças sem número nas placas da C01 (16,5, 114,1 e 156,2 m, 1,2 m mais longe da pista): o verso das placas, separado da frente; ficaram como parte delas;
  - 2 zebras repetidas (2.134–2.264 m e 3.247–3.336 m, nas camadas `RMBGA` e `RMBLA`, com o começo e o fim a menos de 2 m): uma só zebra cada; sem elas, as 31 do Cowork;
  - 12 postos a mais de 14 m da linha central e 64 peças de zebra a mais de 12 m (a pista de kart e o lado de fora), como o pedido manda.
- **Cada conjunto de placas em ordem decrescente antes de uma freada da volta do modelo:** **os 4 conferem.**

| conjunto | placas (s) | freada da volta do modelo | onde a freada cai |
|---|---|---:|---|
| antes da C01 | 200 (16), 100 (114), 50 (156) | 122,0 m | 8 m depois da de 100 |
| antes da C04 | 200 (1.141), 100 (1.227), 50 (1.273) | 1.216,0 m | 11 m antes da de 100 |
| antes da C06 | 100 (1.858), 50 (1.903) | 1.904,0 m | na de 50 (0,6 m depois) |
| antes da C12 | 100 (3.109), 50 (3.154) | 3.124,1 m | 16 m depois da de 100 |

- **A figura:** `_marcos.png` (as placas com o valor, as do DRS, as passarelas, o pórtico, os postos e as zebras sobre a pista da geometria oficial).

### O ruído de cada trecho (ADR 0033, item 1)

Gravado em `data/reference_models/vhe_interlagos.ruido_por_trecho.json` (fora do git; filtro `*.ruido_por_trecho.json` no instalador) **antes de o rádio ser ligado em qualquer sessão**: o desvio padrão amostral dos tempos do trecho nas 7 voltas que contam do bloco 4 do 50.

| trecho | ruído (ms) | trecho | ruído (ms) | trecho | ruído (ms) |
|---|---:|---|---:|---|---:|
| C01 | 26,1 | C06 | 18,9 | C11 | 36,2 |
| C02 | 5,6 | C07 | 29,4 | C12 | 14,4 |
| C03 | 4,6 | C08 | 15,1 | C13 | 4,4 |
| C04 | 11,4 | C09 | 10,1 | C14 | 6,0 |
| C05 | 20,7 | C10 | 14,2 | C14→linha | 12,1 |

**Atenção:** é o ruído da IA, que é muito constante (de 4 a 36 ms). Nas sessões da D.1, quase todo trecho com perda entrou na lista (de 7 a 14 trechos por volta). É o que "toda curva com perda é avisada" pede, mas a janela da volta lenta fica longa.

### B.4: a frase de cada trecho (contra a volta do modelo) e a duração

A duração é a da voz do projeto (Microsoft Daniel a 1,4x, com a vinheta), medida antes de o código usar (C.3). "Voz" diz se o aviso cabe no bloco de voz antes da freada; "—" quando a volta do modelo não tem aquele ponto no trecho.

| trecho | freie (ponto) | s | vire (ponto) | s | acelere (ponto) | s |
|---|---|---:|---|---:|---|---:|
| C01 | freie 10 metros depois da placa de 100 · 3,34 s · **voz** | 122 | vire 35 metros antes do começo da zebra à esquerda · 4,43 s · **voz** | 224 | — (sem retomada no trecho) | |
| C02 | freie no começo da zebra à direita · 3,20 s · janela | 366 | vire 5 metros depois do começo da zebra à direita · 4,28 s · janela | 358 | acelere no fim da zebra à direita · 3,10 s · janela | 410 |
| C03 | — (a referência não freia) | | vire 10 metros depois do começo da zebra à esquerda · 4,19 s · janela | 434 | acelere no ponto marcado · 2,68 s · janela | 554 |
| C04 | freie 10 metros antes da placa de 100 · 3,54 s · **voz** | 1.216 | vire no começo da zebra à esquerda · 3,22 s · **voz** | 1.312 | acelere 15 metros depois do começo da zebra à direita · 4,45 s · **voz** | 1.390 |
| C05 | — | | vire no começo da zebra à esquerda · 3,21 s · janela | 1.480 | acelere 35 metros depois do começo da zebra à esquerda · 4,83 s · janela | 1.510 |
| C06 | freie na placa de 50 · 2,84 s · **voz** | 1.904 | vire no começo da zebra à direita · 3,19 s · **voz** | 1.938 | — | |
| C07 | freie 35 metros antes do começo da zebra à direita · 4,67 s · janela | 2.194 | vire 15 metros depois do começo da zebra à direita · 4,31 s · janela | 2.246 | acelere no fim da zebra à direita · 3,12 s · janela | 2.332 |
| C08 | freie no começo da zebra à esquerda · 3,18 s · janela | 2.356 | vire 10 metros antes do começo da zebra à esquerda · 4,09 s · janela | 2.350 | acelere 15 metros antes do começo da zebra à direita · 4,33 s · janela | 2.488 |
| C09 | freie 50 metros antes do começo da zebra à direita · 4,40 s · janela | 2.454 | vire 30 metros antes do fim da zebra à direita · 4,02 s · janela | 2.566 | — | |
| C10 | freie 10 metros antes do começo da zebra à direita · 4,14 s · janela | 2.622 | vire 15 metros antes do começo da zebra à direita · 4,21 s · janela | 2.672 | acelere no começo da zebra à esquerda · 3,27 s · janela | 2.750 |
| C11 | — | | vire 5 metros depois do começo da zebra à esquerda · 4,22 s · janela | 2.850 | acelere 80 metros depois do começo da zebra à esquerda · 4,43 s · janela | 2.922 |
| C12 | freie 15 metros depois da placa de 100 · 3,61 s · janela | 3.124 | vire 20 metros depois do começo da zebra à esquerda · 4,24 s · janela | 3.188 | acelere 10 metros depois do começo da zebra à direita · 4,28 s · janela | 3.258 |
| C13 | — | | vire no fim da zebra à direita · 3,00 s · janela | 3.334 | acelere 30 metros antes do fim da zebra à direita · 4,19 s · janela | 3.306 |
| C14 | — | | vire 40 metros depois do fim da zebra à esquerda · 4,45 s · janela | 3.578 | acelere no começo da zebra à esquerda · 3,53 s · janela | 3.618 |
| C14→linha | — | | — | | acelere 15 metros antes do posto de bandeira à direita · 3,58 s · janela | 3.980 |

Cada aviso é falado no molde "Curva N: <frase>." (por exemplo, "Curva 1: freie 10 metros depois da placa de 100.", o seu exemplo, saiu exatamente assim na C01).

**Por que só C01, C04 e C06 têm voz:** nas outras, a referência não freia (C03, C05, C11, C13, C14), não há bloco de voz antes da freada (C02, C07, C08, C09, C10) ou a frase não cabe no bloco (C12: o bloco tem 2,5 s, e a frase mais curta, 3,6 s mais 1,0 s).

**As frases que podem soar estranhas para um piloto** (para você decidir; não mudei nada):
1. **C13, acelere 30 m antes do fim da zebra (3.306 m), antes do vire (3.334 m):** acelerar antes de virar. A volta do modelo fica com o acelerador acima de 0,90 desde 3.306 m até o fim do trecho; pela regra do ADR 0030, isso é a retomada.
2. **C09, freie 50 m antes do começo da zebra (2.454 m):** a "freada" da C09 é um toque de freio da volta do modelo ainda na saída da C08, a 120 km/h, e a mínima da C09 é 164 km/h. A busca vai do ápice anterior (o da C08) ao ápice da C09, a regra do relatório de evolução.
3. **C02 e C08, freie depois do vire:** na C02, a freada (366 m) vem 8 m depois do ponto de virar (358 m); na C08, 6 m depois (2.356 contra 2.350 m). Nas duas, a referência freia já mudando de direção.
4. **C14→linha, acelere 15 m antes do posto:** o trecho não tem curva. A frase nunca é dita (sem a medida do 45, o trecho não tem causa), mas aparece na tabela.
5. **C03, acelere no ponto marcado:** não há marco na janela (80 m antes ou 40 m depois de 554 m); fica só na janela, com a marca.
6. **C11, acelere 80 metros depois do começo da zebra:** a retomada fica longe do marco (78 m), mas dentro da janela.

## Parte C: o engenheiro no rádio e no app do jogo

### Os blocos de voz, refeitos com a volta do modelo

| bloco | Cowork | refeito (volta do modelo) | duração (Cowork / refeito) |
|---|---|---|---|
| reta dos boxes, antes da C01 | 3.660 → 44 m | 3.618 → 45 m | 10,0 / 10,9 s |
| reta oposta, antes da C04 | 556 → 1.141 m | 554 → 1.141 m | 8,9 / 9,1 s |
| antes da C06 | 1.540 → 1.848 m | 1.510 → 1.838 m | 5,0 / 5,5 s |
| antes da C12 | 2.928 → 3.071 m | 2.922 → 3.063 m | 2,5 / 2,5 s |
| antes da C14 | 3.376 → 3.517 m | 3.306 → 3.521 m | 2,6 / 4,4 s |
| antes da C05 | — | 1.390 → 1.434 m | — / 1,1 s |
| antes da C11 | — | 2.750 → 2.807 m | — / 1,7 s |
| antes da C13 | — | 3.258 → 3.293 m | — / 1,0 s |

- **As diferenças vêm da retomada:** uso a do ADR 0030 (o acelerador em 0,90 ou mais até o fim do trecho). Antes da C14, a retomada da C13 é 3.306 m (a volta do modelo não tira o pé na C13), e o Cowork usou 3.376 m. Antes da C01, a retomada da C14 é 3.618 m, contra 3.660 m.
- **Sem bloco:** C02 e C07 (o trecho anterior não tem retomada), C03 e C08 (a primeira ação vem menos de 1,0 s depois da retomada), C09 (a primeira ação vem antes da retomada da C08) e C10 (a C09 não tem retomada). No miolo, como o Cowork disse, nenhum bloco passa de 1,7 s.

### O que mudou no app

- **`core/engenheiro/`** (novo): `regras.py` (os trechos, os pontos, a causa, a frase pelo marco, os blocos, o `s_fala` e a conferência, puros), `servico.py` (a lista que vive de linha a linha, a melhor passagem, os avisos no `s_fala`, a reserva dos blocos, a conferência depois da ação e o registro), `marcos.py` e `preparar.py`.
- **O rádio** (`core/radio/servico.py`): o engenheiro ligado por padrão (`AT_ENGENHEIRO=desligado` volta ao rádio do 51); o aviso sai no quadro em que o carro passa o `s_fala`, antes de qualquer feedback; o feedback espera um bloco e sai na variante mais completa que cabe antes da reserva (com o engenheiro, todas as variantes que cabem no limite do tipo são geradas de antemão); a acurácia vai no cartão do resumo e na variante mais completa da fala. A voz dos avisos tem uma fila própria, para não atrasar o resumo.
- **A rota** `GET /api/radio/engenheiro` (a lista para a janela do jogo) e, em `main.py`, as raízes dos arquivos (o repositório, a pasta de dados e a de recursos) e a "Sua melhor volta" do modelo do coach.
- **A conferência só vale para a dica que foi dada antes de o carro passar a ação.** A primeira rodada da D.1 mostrou o caso da C01: o aviso sai a 4.122 m, antes da linha, e eu conferia na linha seguinte a C01 da volta que já tinha passado. Corrigido: a dica dada fica guardada como foi dita (a frase, o ponto dito e a voz), mesmo que a lista mude, e só é conferida depois de o carro passar o ponto da ação.
- **O registro:** `<pasta de dados>/data/radio/<sessão>.engenheiro.jsonl`, com uma linha por aviso (o trecho, a causa, a frase, o `s_fala`, voz ou janela e por quê, a folga até a freada), uma por conferência e uma por volta que conta (a perda nos 15 trechos e a lista). A perda do trecho nas voltas seguintes sai das linhas "volta".
- **O app do jogo 0.7.0** (`radio_engenheiro.lua` e `manifest.ini`): a quinta janela, "Engenheiro", ligada e desligada na barra de apps como as outras; a marca no asfalto por `render.on('main.track.transparent')`, `render.quad` e `physics.raycastTrack` (que o `lib.lua` do SDK instalado tem), ou a contagem 3-2-1 se o CSP não tiver; o cartão "ENGENHEIRO" no rádio para o aviso; o FPS no log com a janela do engenheiro ligada ou desligada.
- **As versões:** o app do Windows `0.9.0-engenheiro` nos três pontos (`desktop/package.json`, `desktop/main.js` e `backend/main.py`); o app do jogo 0.7.0.

## Parte D: as conferências, sem jogo

### D.1, o rádio fora do tempo real

**Como:** o script do 51 (`_radio_offline.py`), com o engenheiro ligado (`com`) e desligado (`sem`, o rádio do 51 com a volta do modelo), nas 4 sessões, com a voz de verdade e o relógio do gravador. A "Sua melhor volta" é a do modelo do repositório (`2026-10-24_13-43-32_vhe_interlagos#0003`).

| sessão | voltas que contaram | avisos dados | pela voz (C01 / C04) | só na janela | folga até a freada (mín / máx) | feedback sem / com | mudaram de bloco | com a causa na voz (sem / com) | acima do limite |
|---|---:|---:|---|---:|---|---|---:|---|---:|
| 13/10 (19:24) | 8 | 94 | 14 (10 / 4) | 80 | 1,46 / 11,71 s | 24 / 30 | 13 | 16 / 11 | 0 |
| 18/10 (12:38) | 9 | 115 | 20 (12 / 8) | 95 | 1,42 / 2,23 s | 22 / 29 | 11 | 15 / 5 | 0 |
| 21/10 (20:30) | 7 | 99 | 12 (10 / 2) | 87 | 1,26 / 5,87 s | 35 / 39 | 22 | 25 / 13 | 0 |
| 12/11 (22:57) | 5 | 56 | 8 (4 / 4) | 48 | 1,39 / 4,98 s | 13 / 15 | 6 | 7 / 1 | 0 |

- **"Avisos dados"** é cada vez que o carro passou o `s_fala` de um trecho da lista. **Pela voz,** só C01 e C04; todos os 54 avisos pela voz foram entregues pelo rádio.
- **Por que a C06 nunca foi pela voz:** a sua melhor volta (a `#0003` de 24/10, 1:26,568) é mais rápida que a volta do modelo em 5 trechos: C02 (−105 ms), C06 (−45 ms), C10 (−24 ms), C03 (−12 ms) e C05 (−4 ms). Nesses trechos, a referência é a sua melhor passagem (ADR 0033, item 2), e nela a C06 é feita sem freio (o freio fica em 0 no trecho). Sem freada na referência, a C06 fica só na janela ("vire").
- **Só na janela, por quê** (as 4 sessões): a referência não freia no trecho (142), sem bloco de voz antes da freada (98), a frase não cabe no bloco (42), outra fala em andamento (23) e a volta de saída dos boxes (5).
- **A folga até a freada** (o tempo até a freada da referência, na velocidade do carro, menos a duração da fala): **nunca abaixo de 1,26 s**, então todo aviso pela voz acabou pelo menos 1,0 s antes da freada.
- **Nenhuma fala acima do limite** (7,3, 8,0 e 8,8 s) nas 8 rodadas. A maior fala do feedback com o engenheiro foi 7,26 s (coach), 7,77 s (resumo) e 6,32 s (análise).
- **O feedback com o engenheiro tem mais mensagens** (a curva da volta que não coube no resumo vai numa mensagem própria: 6, 7, 4 e 3) e **nenhuma mensagem do "sem" se perdeu,** salvo um resumo de 12/11 (a volta 9, com rodada, no fim da sessão, que ficou pendente com o engenheiro).
- **A acurácia:** 13 de 48, 7 de 51, 15 de 44 e 7 de 29 dicas aplicadas (as conferidas com medida). São voltas de sessões antigas, sem o engenheiro no carro: o número só mostra que a conta roda; não diz nada do efeito.

**O efeito que precisa de decisão:** **com o engenheiro, o feedback perde a causa na voz em 42 mensagens** (7, 14, 15 e 6 por sessão). A duração média do feedback caiu de 7,0–7,2 s para 4,2–5,5 s. A regra do ADR ("a variante mais completa que caiba antes da reserva; o bloco seguinte só se nenhuma couber") faz a mensagem sair no primeiro bloco em que a variante curta cabe, que agora é um bloco curto, em vez de esperar a reta dos boxes com a variante completa. Exemplos:
- 13/10, coach: "Curva 7, direita: 8 décimos atrás da referência. Freou 39 metros antes da referência." (6,93 s) virou "Curva 7: 8 décimos atrás." (2,58 s);
- 18/10, coach: "Curva 11: 1,7 segundo atrás. Mínima 41 quilômetros por hora abaixo da referência." (6,84 s) virou "Curva 11, esquerda: 1,7 segundo atrás da referência." (4,39 s);
- 12/11, resumo: "Melhor da sessão. Curva 4: 1,1 segundo, freou 34 metros antes da referência." (6,76 s) virou "Melhor da sessão. Curva 4: 1,1 segundo." (4,17 s).

Não mudei a regra (ela é do ADR e nenhuma regra muda depois de ver os números).

### D.2, as prévias

`_previa.html` e `_previa.png`, com o engenheiro de verdade (a volta do modelo, os marcos e a regra do ADR):
- **a janela na C01 e na C06,** a 150 m do ponto: "Curva 1: freie 10 metros depois da placa de 100" e "Curva 6: freie na placa de 50", com "a 150 m";
- **a marca na pista,** na vista do piloto (1,0 m acima da linha da referência), a 120 m e a 40 m do ponto: **a 120 m, a faixa de 1,5 m no chão quase não aparece** (menos de 1 px de altura na tela, por causa da perspectiva rasante); **a 40 m, ela aparece como uma linha branca fina.** O tamanho é o do ADR; se no jogo ela for difícil de ver, a medida da faixa é uma decisão sua;
- **a lista inteira da volta lenta,** como o engenheiro a deixou no fim da sessão de 12/11 fora do tempo real, com a perda e a conferência com os valores.

Não há como rodar o app Lua fora do jogo: a prévia repete o desenho da janela num SVG (as mesmas cores, fontes e textos). A captura é do Edge sem janela; a pasta de perfil dele ficou no scratchpad.

### D.3, os testes novos

`backend/tests/test_engenheiro.py`, **18 testes passando**, com dados sintéticos:
- o kn5 (um arquivo sintético escrito pelo teste): a textura, o UV e a transformação do nó;
- a separação das placas pelas faces ligadas (com os vértices repetidos por face e o verso junto) e o valor pela coluna da textura, com a metade de baixo do `DISTMARKER.DDS`;
- a projeção e o lado (ADR 0003);
- a regra da frase: o custo, o bônus da placa e da zebra, a janela de cada ação, o marco depois (1,5 ×), o empate pelo menor s, o arredondamento a 5 m e a frase que passa pela linha;
- a causa do engenheiro a partir da causa do 45;
- o bloco (da retomada anterior a 1,0 s antes da primeira ação), o `s_fala` e a reserva;
- a conferência (freie, vire e acelere, com o texto da lista);
- a dica dada antes da linha, conferida só depois da ação;
- a prioridade do aviso (nunca por cima de outra fala, nunca na volta de saída, só com tempo até a freada);
- a troca da referência do trecho pela melhor passagem;
- a volta lenta (4,9 s não, 5,0 s sim, fica lenta até a linha, e a volta de saída);
- os filtros do instalador e as versões.

### D.4, as suítes

- **backend, a suíte inteira:** **1062 passando** (`_testes.txt`);
- **os testes do rádio, do 45, da referência e do engenheiro:** 91 passando. Dois testes antigos mudaram só pela versão (`test_a_versao_do_backend` agora pede `engenheiro`; `test_o_app_do_jogo_nao_diz_ia_para_a_referencia`, o app do jogo 0.7.0);
- **front:** 180 testes passando; `tsc` sem erro (o front não mudou);
- **desktop:** 4 testes passando;
- **Lua** (`conferir_lua.py`, agora também com `render.`, `physics.` e `vec3`, contra o `lib.lua` do SDK do CSP): 38.559 tokens, nenhum erro de léxico, os blocos ok, as 55 chamadas da API e os 14 métodos existem (`_conferir_lua.txt`).

### A suíte do backend e a rota

- **backend, a suíte inteira:** **1062 passando**, nenhuma falha (12 min 47 s; 37 avisos do scikit-learn, os de sempre). Saída em `_testes.txt`.
- **A rota no backend de verdade** (16/11, 09:32): um backend de teste na porta 8017, com a pasta de dados no scratchpad (`AT_BACKEND_RUNTIME_ROOT`) e o repositório como fonte. `GET /api/radio/engenheiro` respondeu `disponivel: true`, com a lista vazia (sem jogo) e os 8 blocos de voz; `/api/radio/estado` mostra o engenheiro ligado e o registro na pasta isolada; `/api/radio/mensagens` traz o `engenheiroVersao`. O backend foi encerrado com `taskkill /T`, e o cache da pista do repositório não mudou (01/11).

## Parte E: o teste no jogo, com você (não feito)

**Antes de você ir ao jogo:**
1. **O app do jogo 0.7.0,** pelo `instalar.ps1`, que você roda:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Dokas\Desktop\f1-telemetry-analyzer\tools\csp_app\instalar.ps1
```

2. **O app do repositório** (backend na porta 8000), na branch `etapa/engenheiro`. O engenheiro já vem ligado; os três arquivos dele (a volta do modelo, os marcos e o ruído) estão em `data/reference_models`.
3. **Na barra de apps do jogo,** ligue a janela nova "Engenheiro" (a marca na pista só aparece com ela ligada).

**O roteiro** (do pedido): até 45 minutos, pelo menos 10 voltas, na pista original, com o preset de sempre. Quando acabar, me avise com **"rodei o engenheiro"**.

**O que vou ler depois:** os avisos dados e entregues e a folga até a freada (`data/radio/<sessão>.engenheiro.jsonl` e o registro do rádio), os aplicados, a perda nos trechos avisados nas voltas seguintes (só relatada), o FPS com a janela e a marca ligadas (o log do CSP, a linha "fps:" com "engenheiro ligado"), os logs do CSP e as suas anotações.

**O que vale olhar no jogo:**
- o aviso "Curva 1: freie 10 metros depois da placa de 100" na reta dos boxes e o da C04 na reta oposta, se a C01 e a C04 estiverem na lista;
- se a marca no asfalto aparece (o log do CSP diz "a marca na pista ligada (render.on)") e se dá para vê-la a tempo;
- a janela depois da linha ("C01 aplicada · C04 não", "2 de 3 avisos aplicados") e a lista inteira numa volta lenta;
- o feedback mais curto nas retas (o ponto 1 da decisão, abaixo).

## Parte F: a documentação

- **ADR 0033,** com a linha no índice (`1578276f`);
- **ADRs 0021, 0027 e 0032:** uma linha de atualização cada (o desenho na pista; o feedback nos blocos e a acurácia; a volta do modelo como referência de cada trecho e o freio só como ponto);
- **`docs/realidade_aumentada.md`:** a seção 9, "O engenheiro que acompanha a volta", a rota nova na seção 7 e uma nota na seção 3 (as janelas de rádio);
- **`docs/app_para_producao.md`:** a 0.9.0, o app do jogo 0.7.0, a coluna da `etapa/engenheiro` e os riscos dos arquivos fora do git;
- **`docs/backlog.md`:** não editado (os itens estão abaixo).
- **O merge e o instalador 0.9.0:** depois do teste no jogo e da conferência; a instalação só com o seu "pode instalar".

## O que precisa de decisão

1. **O feedback perde a causa na voz com o engenheiro** (42 mensagens nas 4 sessões; a seção D.1). Opções que mudam a regra: o feedback com a causa esperar um bloco em que caiba a variante completa (na prática, a reta dos boxes ou a oposta), ou só os resumos e as análises esperarem. Sem decisão, fica como o ADR está.
2. **"Freada leve" e "marcha acima"** ficaram fora (ADR 0033, contexto, item 4). Para medir a marcha, a volta ao vivo teria de guardar a marcha; a "freada leve" contra a volta do modelo esbarra no ADR 0032, item 5.
3. **As frases estranhas da B.4** (a C13 acelerando antes de virar, a C09 com o toque de freio da C08, a C02 e a C08 freando depois do ponto de virar).

## O que foi enviado ao GitHub

**Nada foi enviado por mim:** o `git push` é recusado pelo controle de permissões desta sessão.

**A conferência antes do primeiro envio** (os arquivos dos commits do pedido contra `develop`):
- nenhum arquivo acima de 50 MB (o maior é `_duracao_dos_avisos.json`, com 18 KB, e a `_previa.png`, com 106 KB);
- nenhuma gravação (`recordings/`, `data/recordings`, `data/ml`), nenhum `.ai`, nenhum segredo e nenhum arquivo da pista. A tabela dos marcos (`_marcos.json`) é derivada da leitura (s, lado, valor e a posição de cada marco), e não um arquivo da pista; as texturas lidas para conferir as colunas ficaram só no scratchpad.

**O comando** (uma branch nova, que não reescreve o remoto):

```bash
git -C C:/Users/Dokas/Desktop/f1-telemetry-analyzer push origin etapa/engenheiro
```

Quando você avisar, confiro com `git ls-remote origin` que o hash remoto é o local. `develop` vai depois do merge.

## Itens para o backlog

1. **A causa que sai da voz do feedback com o engenheiro** (a decisão 1, se ficar como está).
2. **"Freada leve" e "marcha acima"** (a decisão 2): a marcha na volta ao vivo; a força do freio só contra a sua melhor passagem.
3. **O ruído do bloco 4 é o da IA** (4 a 36 ms): quase todo trecho com perda entra na lista. Um ruído do piloto (o desvio das suas passagens) seria outra regra.
4. **A marca no asfalto é fina de longe** (a prévia): a 120 m quase não aparece.
5. **O leitor de kn5 do projeto** (`core/kn5/kn5_reader.py`) lê o material de um campo errado (o número de filhos do nó, sempre 0): todas as malhas ficam com o primeiro material. A extração da superfície não depende disso (ela casa pelo nome da malha), mas o inventário mostra o material errado.
6. **O `map.png`** não foi lido (fora da exceção); a figura dos marcos pode ir para cima dele com a sua autorização.
7. **A latência do app do jogo** (o pedido de mensagens a cada 0,3 s e a voz que começa depois do download) come parte do 1,0 s de folga antes da freada; a menor folga na D.1 foi 1,26 s, medida no backend.
8. **Um interruptor do engenheiro no app do Windows** (hoje só a variável `AT_ENGENHEIRO`).

## O que falta

1. **A Parte E:** o seu teste no jogo e a minha leitura dele ("rodei o engenheiro").
2. **As decisões** da seção acima.
3. **O merge em `develop`,** o envio e **o instalador 0.9.0** (a instalação só com o seu "pode instalar").
4. **O envio da branch,** pelo comando acima.

## Atualização de 16/11: as suas decisões (parado antes da D.1)

**O pedido:** a "Atualização de 16/11" no fim do pedido 52.

### O que foi feito

- **O ADR 0033** ganhou a seção "Decisões do Eduardo de 16/11", como emenda, sem mudar o texto acima (`fa1262ed`, antes do código). Onde a decisão deixava lacuna, fixei no ADR:
  - **a variante com a causa** é a fala que diz "freou", "mínima", "passou", "saiu" ou "acelerou" (as causas medidas do 45; é a mesma conta da D.1);
  - **as retas longas** são os blocos de voz de 8,8 s ou mais na volta do modelo: a reta dos boxes (10,9 s) e a reta oposta (9,1 s);
  - **a primeira reta longa depois de a mensagem nascer** é a primeira em que o carro *entra* depois disso; a reta em que a mensagem nasce não conta;
  - **"sem tirar o pé"** fica só na janela (a referência não freia), até o início da curva, sem marca no asfalto e sem contagem; é aplicada se o acelerador da volta ficou em 0,90 ou mais no trecho inteiro;
  - **a freada desde a saída do trecho anterior** vale para tudo o que o engenheiro mede (a referência, os blocos, a causa "freada cedo ou tarde" e a conferência). O feedback do rádio continua com a regra do 45, porque a decisão fala da freada de cada trecho do engenheiro.
- **O código** (`a95c0843`):
  - o feedback espera a reta longa com a causa (`core/radio/servico.py`);
  - o aviso é falado curto e sem a vinheta (`audio.falar` ganhou `vinheta_antes`), e o cartão e a janela continuam com "Curva N:";
  - "sem tirar o pé" e a freada desde a saída do trecho anterior (`core/engenheiro/regras.py` e `servico.py`); a busca da freada do 45 aceita outro começo só quando o engenheiro pede (`medidas_da_volta(..., inicio_da_freada=...)`);
  - no app do jogo, só uma linha: sem contagem 3-2-1 quando o item não tem marca. O app continua 0.7.0, que ainda não foi instalado. A conferência do Lua contra o SDK passou (`_conferir_lua.txt`).
- **Os testes:** 24 do engenheiro (6 novos: a freada desde a saída, "sem tirar o pé", o feedback que espera a variante com a causa, a mais completa na primeira reta longa, a reta em que a mensagem nasce, e o aviso sem a vinheta). Com os do rádio, do 45 e da referência, **97 passando**. A suíte inteira fica para depois da D.1.
- **O backlog** (decisão 6): duas linhas novas em `docs/backlog.md`. A volta ao vivo deve guardar a marcha e a força do freio. A força do freio deve ser comparada com a sua melhor passagem, nunca com o pedal da volta do modelo.
- **A documentação:** a seção 9 de `docs/realidade_aumentada.md`, a linha do engenheiro em `docs/app_para_producao.md` e uma linha no ADR 0027.
- **A conferência da volta do modelo** foi refeita (`_conferencia_da_volta_do_modelo.json`).

### O que mudou nos 15 trechos (decisões 3 e 4, na volta do modelo)

| trecho | freada antes | freada agora | a frase do "freie" agora | sem tirar o pé |
|---|---:|---:|---|---|
| C09 | 2.454 m (o toque na saída da C08) | — (sem freada) | — | não |
| C10 | 2.622 m | **2.680 m** | "Freie 5 metros antes do começo da zebra à direita." (antes, 10 m antes) | não |
| os outros 13 | iguais | iguais | iguais | **nenhum** |

- **A C09** perdeu o toque de freio, como você queria: a frase do "freie" some, e ficam "vire" e o bloco curto antes da C09 (0,9 s, que não cabe frase).
- Os blocos de voz só mudaram na C09; os outros sete são os mesmos.

### Os dois pontos que precisam da sua decisão

1. **"Sem tirar o pé" não pega nenhum trecho da volta do modelo, nem a C13.** A volta do modelo não freia na C13, mas alivia: o acelerador vai a 0 dentro do trecho da C13 antes de 3.306 m, que é a retomada. Pela regra escrita ("o acelerador fica em 0,90 ou mais do começo ao fim do trecho"), a C13 continua com "vire no fim da zebra" e "acelere 30 metros antes do fim da zebra". A regra só vai pegar um trecho em que a referência for a sua melhor passagem e ela não aliviar. Não mudei a regra.
2. **Na C10, a freada da referência começa 4 m antes da saída da C09.** A referência freia a 0,99 desde 2.622 m, e a saída da C09 é 2.626 m. A busca que começa na saída já encontra o freio apertado, então pega a segunda pisada, em 2.680 m. Essa pisada vem depois do ponto de virar (2.672 m), com o freio a 0,67. Antes da decisão, a freada da C10 era 2.622 m. A C10 não tem bloco de voz, então essa frase só aparece na janela. Ainda assim, a dica e a conferência do "freie" na C10 passam a usar a segunda pisada. Não mudei a regra.

Uma saída possível para a C10: se o freio já estiver apertado na saída do trecho anterior, a freada é onde essa pisada começou. Com ela, a C10 volta a 2.622 m e a C09 continua sem freada. Para a C13, uma regra como "a referência não freia no trecho" pegaria a C13, mas também a C03, a C05, a C11 e a C14, que aliviam. Escolher entre essas saídas cabe a você.

### O termo "freada" (a sua pergunta de 16/11, 14h19)

- **No Brasil, o termo técnico é "frenagem":** "ponto de frenagem", "zona de frenagem". "Freada" é a forma coloquial; em Portugal, diz-se "travagem". A busca não achou um glossário oficial, só o uso em matérias de automobilismo, como a da Band sobre o S do Senna.
- **Onde "freada" aparece hoje:**
  - **na voz**, só no fim da causa sem medida ("perdeu 3 décimos na freada"). O aviso diz "Freie…" e o feedback diz "Freou 39 metros antes…", que são formas do verbo;
  - **no texto escrito**, em mais lugares: o cartão ("na freada, +0,52 s", "freada 15 m antes"), a causa do engenheiro ("freada cedo" e "freada tarde"), os rótulos do replay ("freada da referência") e o minimapa.
- **A proposta:** trocar o substantivo por "frenagem" na voz e no texto ("perdeu 3 décimos na frenagem", "frenagem 15 m antes", "frenagem cedo", "frenagem da referência") e manter o verbo ("Freie", "Freou").
- **Aplicada (sua resposta: "Sim, frenagem"; ADR 0033, emenda, item 9):**
  - **no rádio:** a causa falada sem medida ("na frenagem"), o cartão ("na frenagem, +0,52 s"; "frenagem 15 m antes") e as linhas da análise;
  - **no engenheiro:** as causas "frenagem cedo" e "frenagem tarde" e os motivos da janela e do registro ("sem bloco de voz antes da frenagem", "pouco tempo até a frenagem");
  - **no app do jogo:** "frenagem da referência", "frenagem do seu recorde" e o rótulo do replay;
  - **nas telas:** "Início da frenagem" (Volta), "Frenagem emendada" (Evolução) e "sem frenagem medida nesta volta";
  - **na base de conhecimento:** "Frenagem antecipada" e "Frenagem tardia".
- **O que não mudou:** o verbo e as chaves internas (`freada`, `freadaM`). O texto técnico da documentação também ficou como estava.
- **Os testes:** 114 do backend passando (o engenheiro, o rádio, o 45, a referência, a análise assistida e o coach). No front, 180 passando e o `tsc` sem erro. O Lua continua passando na conferência contra o SDK.

### O que faltava (feito depois das suas respostas; veja a seção seguinte)

1. **A sua resposta** aos dois pontos acima (a C13 e a C10). O termo já está aplicado.
2. **Medir a voz de novo** (a frase curta, sem a vinheta) e refazer a tabela da B.4: quais avisos cabem na voz agora.
3. **Refazer a D.1** nas 4 sessões. Os dois passos esperam o jogo fechar (o `acs.exe` estava aberto às 14h, com 1h47 de CPU), porque são contas pesadas. Também dependem da resposta acima, que muda a C10.
4. **A suíte inteira do backend** e o relatório com a D.1 nova. Depois disso, aviso você antes do teste no jogo, como pedido.

## Depois das suas respostas (16/11 e 17/11): a voz curta, a D.1 refeita e o teste no jogo

**As suas respostas:**
- **"Sim, frenagem":** aplicada (`1edbebf3`; ADR 0033, emenda, item 9). Veja a seção do termo, acima.
- **A C10, "Sim, do começo dela":** se o freio já estiver apertado (0,15 ou mais) na saída do trecho anterior, a frenagem é onde essa pisada começou (`eb526234`; ADR 0033, emenda, item 10).
  - Na volta do modelo, só a C10 está nesse caso. A frenagem dela voltou a 2.622 m ("Freie 10 metros antes do começo da zebra à direita."), e a C09 continua sem frenagem.
  - Os blocos de voz ficaram como na tabela da seção da atualização: a C09 ganhou um bloco de 0,9 s, e os outros sete não mudaram.
- **A C13:** você não pediu outra regra, então fica a regra escrita. Na volta do modelo, a C13 continua com "vire" e "acelere". Nas sessões, "sem tirar o pé" apareceu na C03, na C05 e na C14, onde a referência do trecho era a sua melhor passagem (veja a D.1).

### B.4 refeita: a duração de cada aviso no molde curto (sem "Curva N:" e sem a vinheta)

A medição usou a voz do projeto (Microsoft Daniel a 1,4x), com o `acs.exe` fechado (`_duracao_dos_avisos.py` e `.json`).
- Cada aviso ficou cerca de 1,15 s mais curto: 0,34 s da vinheta e cerca de 0,8 s do "Curva N:". A frase da chegada, que não tinha "Curva N:", só perdeu os 0,34 s.

| trecho | ação | a fala | antes | agora | voz ou janela |
|---|---|---|---:|---:|---|
| C01 | freie | Freie 10 metros depois da placa de 100. | 3,34 s | 2,37 s | **voz** |
| C01 | vire | Vire 35 metros antes do começo da zebra à esquerda. | 4,43 s | 3,49 s | **voz** |
| C02 | freie | Freie no começo da zebra à direita. | 3,20 s | 2,02 s | janela (sem bloco antes da frenagem) |
| C02 | vire | Vire 5 metros depois do começo da zebra à direita. | 4,28 s | 3,13 s | janela (sem bloco) |
| C02 | acelere | Acelere no fim da zebra à direita. | 3,10 s | 1,95 s | janela (sem bloco) |
| C03 | vire | Vire 10 metros depois do começo da zebra à esquerda. | 4,19 s | 3,02 s | janela (a referência não freia) |
| C03 | acelere | Acelere no ponto marcado. | 2,68 s | 1,52 s | janela (a referência não freia) |
| C04 | freie | Freie 10 metros antes da placa de 100. | 3,54 s | 2,35 s | **voz** |
| C04 | vire | Vire no começo da zebra à esquerda. | 3,22 s | 2,02 s | **voz** |
| C04 | acelere | Acelere 15 metros depois do começo da zebra à direita. | 4,45 s | 3,27 s | **voz** |
| C05 | vire | Vire no começo da zebra à esquerda. | 3,21 s | 2,02 s | janela (a referência não freia) |
| C05 | acelere | Acelere 35 metros depois do começo da zebra à esquerda. | 4,83 s | 3,66 s | janela (a referência não freia) |
| C06 | freie | Freie na placa de 50. | 2,84 s | 1,66 s | **voz** |
| C06 | vire | Vire no começo da zebra à direita. | 3,19 s | 2,01 s | **voz** |
| C07 | freie | Freie 35 metros antes do começo da zebra à direita. | 4,67 s | 3,47 s | janela (sem bloco) |
| C07 | vire | Vire 15 metros depois do começo da zebra à direita. | 4,31 s | 3,14 s | janela (sem bloco) |
| C07 | acelere | Acelere no fim da zebra à direita. | 3,12 s | 1,95 s | janela (sem bloco) |
| C08 | freie | Freie no começo da zebra à esquerda. | 3,18 s | 2,05 s | janela (sem bloco) |
| C08 | vire | Vire 10 metros antes do começo da zebra à esquerda. | 4,09 s | 3,00 s | janela (sem bloco) |
| C08 | acelere | Acelere 15 metros antes do começo da zebra à direita. | 4,33 s | 3,24 s | janela (sem bloco) |
| C09 | vire | Vire 30 metros antes do fim da zebra à direita. | 4,02 s | 2,87 s | janela (a referência não freia mais na C09) |
| C10 | freie | Freie 10 metros antes do começo da zebra à direita. | 4,14 s | 2,98 s | janela (sem bloco) |
| C10 | vire | Vire 15 metros antes do começo da zebra à direita. | 4,21 s | 3,10 s | janela (sem bloco) |
| C10 | acelere | Acelere no começo da zebra à esquerda. | 3,27 s | 2,17 s | janela (sem bloco) |
| C11 | vire | Vire 5 metros depois do começo da zebra à esquerda. | 4,22 s | 3,16 s | janela (a referência não freia) |
| C11 | acelere | Acelere 80 metros depois do começo da zebra à esquerda. | 4,43 s | 3,35 s | janela (a referência não freia) |
| C12 | freie | Freie 15 metros depois da placa de 100. | 3,61 s | 2,49 s | janela (não cabe no bloco) |
| C12 | vire | Vire 20 metros depois do começo da zebra à esquerda. | 4,24 s | 3,12 s | janela (não cabe no bloco) |
| C12 | acelere | Acelere 10 metros depois do começo da zebra à direita. | 4,28 s | 3,17 s | janela (não cabe no bloco) |
| C13 | vire | Vire no fim da zebra à direita. | 3,00 s | 1,82 s | janela (a referência não freia) |
| C13 | acelere | Acelere 30 metros antes do fim da zebra à direita. | 4,19 s | 3,02 s | janela (a referência não freia) |
| C14 | vire | Vire 40 metros depois do fim da zebra à esquerda. | 4,45 s | 3,08 s | janela (a referência não freia) |
| C14 | acelere | Acelere no começo da zebra à esquerda. | 3,53 s | 2,17 s | janela (a referência não freia) |
| C14→linha | acelere | Acelere 15 metros antes do posto de bandeira à direita. | 3,58 s | 3,24 s | janela (sem curva, sem causa) |

**Quais cabem na voz agora:**
- **Os mesmos de antes:** a C01, a C04 e a C06.
- **A C12 é a única perto de entrar.** A frase mais curta (2,49 s) mais 1,0 s pede um `s_fala` em 2.910 m, e o bloco começa em 2.922 m: ficam faltando 12 m.
- **As outras não mudam com a frase mais curta:** ou não têm bloco de voz antes da frenagem, ou a referência não freia.

### D.1 refeita (as 4 sessões, com as decisões 1 a 4, 9 e 10)

As rodadas são as do 51, com o engenheiro ligado (`com`) e desligado (`sem`), a voz de verdade e o relógio do gravador, com o jogo fechado (`_radio_com_e_sem.json`). As 8 rodadas terminaram sem erro.

| sessão | voltas que contaram | avisos dados | pela voz (C01 / C04) | só na janela | folga até a frenagem (mín / máx) | feedback sem / com | mudaram de bloco | com a causa na voz (sem / com) | perderam a causa | acima do limite |
|---|---:|---:|---|---:|---|---|---:|---|---:|---:|
| 13/10 (19:24) | 8 | 94 | 17 (11 / 6) | 77 | 1,32 / 9,33 s | 24 / 26 | 10 | 16 / 16 | 2 | 0 |
| 18/10 (12:38) | 9 | 121 | 16 (12 / 4) | 105 | 1,30 / 1,63 s | 22 / 24 | 8 | 15 / 15 | 2 | 0 |
| 21/10 (20:30) | 7 | 99 | 12 (10 / 2) | 87 | 1,17 / 10,83 s | 35 / 36 | 17 | 25 / 24 | 1 | 0 |
| 12/11 (22:57) | 5 | 56 | 5 (4 / 1) | 51 | 1,26 / 9,57 s | 13 / 13 | 6 | 7 / 6 | 1 | 0 |

- **A causa na voz:**
  - **6 mensagens perdem a causa, contra 42 antes da decisão 1.** Com o engenheiro, a voz diz a causa em 61 mensagens, contra 63 sem ele (antes eram 30 contra 63);
  - **a duração média do feedback** com o engenheiro voltou a 6,3 a 6,9 s (antes da decisão, 4,2 a 5,5 s; sem o engenheiro, 6,9 a 7,2 s).
- **As 6 que perderam a causa:**
  - **3 frases do coach**, porque a variante com a causa (6,8 a 6,9 s) não coube nem na primeira reta longa, antes da reserva do aviso da C04:
    - 13/10, volta 4: "Curva 12: 1,9 segundo atrás da referência. Freou 56 metros antes da referência." virou "Curva 12: 1,9 segundo atrás da referência." (3,66 s);
    - 18/10, volta 1: a Curva 11 saiu sem a causa;
    - 21/10, volta 1: a Curva 12 saiu sem a causa;
  - **2 resumos:** 13/10, volta 10, e 12/11, volta 3. Em 13/10, a curva com a causa foi numa mensagem própria ("Curva 1: 1,0 segundo, freou 64 metros antes da referência."), pela regra do 45;
  - **1 análise:** 18/10, volta 7.
- **Os avisos pela voz:**
  - **só na C01 (37) e na C04 (13)**, todos entregues;
  - **a menor folga até a frenagem foi 1,17 s**, então todo aviso acabou mais de 1,0 s antes da frenagem;
  - **a C06 continua sem voz,** porque a referência dela é a sua melhor passagem, que não freia.
- **Só na janela, por quê** (as 4 sessões):
  - a referência não freia no trecho: 125;
  - sem bloco de voz antes da frenagem: 67;
  - "sem tirar o pé": 54;
  - a frase não cabe no bloco: 42;
  - outra fala em andamento: 27;
  - volta de saída dos boxes: 5.
- **"Sem tirar o pé" nas sessões:**
  - apareceu na C03 (30 vezes), na C05 (19) e na C14 (5), onde a referência era a sua melhor passagem e ela não tirou o pé;
  - das conferidas, 15 aplicadas e 16 não.
- **Nenhuma fala acima do limite** (7,3, 8,0 e 8,8 s).
- **Mensagens pendentes no fim:** 0, 0, 1 e 1 com o engenheiro, contra 1, 1, 2 e 0 sem ele.
  - **"Só sem"** é a mensagem que, com o engenheiro, ficou pendente no fim: um resumo de volta com rodada de 12/11.
  - **"Só com"** são as curvas em mensagem própria, uma análise a mais em 18/10 e um resumo de volta com rodada em 21/10, que sem o engenheiro ficou pendente.
- **A acurácia** (sessões antigas, sem o engenheiro no carro, então o número só mostra que a conta roda): 12 de 48, 10 de 52, 14 de 44 e 10 de 29.

### As suítes

- **Backend, a suíte inteira:** **1069 passando**, nenhuma falha (9 min 30 s; 37 avisos do scikit-learn, os de sempre; `_testes.txt`).
- **Testes do engenheiro, do rádio, do 45 e da referência:** 98 passando. O engenheiro tem 25 testes.
- **Front:** 180 testes passando e o `tsc` sem erro.
- **Lua:** passa na conferência contra o SDK do CSP.

### Para o teste no jogo (a Parte E)

1. **Instale o app do jogo 0.7.0** pelo `instalar.ps1`. Ele mudou desde o relatório anterior (o "frenagem" e a contagem do "sem tirar o pé"), mas continua 0.7.0, porque ainda não tinha sido instalado:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Dokas\Desktop\f1-telemetry-analyzer\tools\csp_app\instalar.ps1
```

2. **Abra o app do repositório** na branch `etapa/engenheiro` e ligue a janela "Engenheiro" na barra de apps do jogo.
3. **O roteiro do pedido:** até 45 minutos, pelo menos 10 voltas. Quando acabar, me avise com **"rodei o engenheiro"**.

**O que vale ouvir e olhar:**
- os avisos curtos, sem a vinheta, na reta dos boxes ("Freie 10 metros depois da placa de 100.") e na reta oposta;
- o feedback com a causa, que agora espera a reta longa;
- "sem tirar o pé" na janela, se a C03, a C05 ou a C14 entrarem na lista com a sua melhor passagem como referência;
- a marca no asfalto (a decisão 8: você diz se ela aparece a tempo).

### O que falta

1. **A Parte E:** o seu teste no jogo e a minha leitura dele.
2. **O merge em `develop` e o instalador 0.9.0,** depois do teste. A instalação, só com o seu "pode instalar".
3. **O envio da branch,** que é seu (o `git push` é recusado aqui):

```bash
git -C C:/Users/Dokas/Desktop/f1-telemetry-analyzer push origin etapa/engenheiro
```

## Parte E: o teste no jogo (20/11) e a leitura (E.3), com o foco na voz e no tempo (parado: a decisão é sua)

**O pedido:** a sua mensagem de 20/11, com a leitura da sessão focada em dois problemas: (1) o engenheiro não falou, só apareceu na janela e na marca; (2) as mensagens chegam muito em cima. Nenhum código foi mudado.

**A sessão:** `2026-11-20_19-06-14_vhe_interlagos`, gravada pelo app do repositório 0.9.0-engenheiro (`063977be`, sem mudança local) com o app do jogo 0.7.0. O `radio_engenheiro.lua` instalado é igual ao do repositório.
- **Voltas (5, nenhuma com a IA):**
  - a volta de saída;
  - 1:42,045 (com rodada);
  - **1:32,071 (limpa, a única que contou)**;
  - 1:50,524 (com rodada);
  - uma última incompleta: o jogo fechou às 19:16.
- **O roteiro do pedido não foi cumprido:** pedia 10 voltas e 45 minutos, e a sessão teve 5 voltas e uns 10 minutos.
- **A lista do engenheiro foi montada uma vez só,** na linha da volta de 1:32,071, e não mudou mais.
- **O que voltou ao normal:** o app do repositório (o backend, o front e a janela) foi fechado depois da leitura, e o cache da pista não mudou.

**Como li:**
- a gravação, projetada na geometria oficial;
- o registro do engenheiro e o do rádio;
- o log do CSP;
- o rádio fora do tempo real nesta mesma sessão, que reproduz os 14 avisos do jogo e dá o ponto da ação de cada um;
- a ação de cada trecho, buscada desde a saída do trecho anterior (a regra do engenheiro):
  - para "freie", a sua frenagem;
  - para "vire", a sua primeira frenagem ou o primeiro alívio (acelerador abaixo de 0,90);
  - sem nenhum dos dois, e para "sem tirar o pé", a entrada da curva.
- **O relógio da gravação está 3 h adiantado** (o defeito do gravador, no backlog): a hora certa vem do `startedAt`.

**Os arquivos:**
- `_e3_voltas.py`, `_e3_analise.py` e `_e3_analise.json`: a leitura e as opções;
- `_e3_falas_curtas.py` e `_e3_falas_curtas.json`: as falas candidatas, medidas com a voz do projeto.

### E.3.1 Cada aviso da sessão

"Até a sua ação" é o tempo entre o aviso aparecer na janela e a sua ação naquela passagem. A janela desenha o aviso no quadro em que o carro passa o `s_fala`, sem esperar a rede: a lista já está no jogo.

| hora | trecho | a frase | voz? | o motivo (registro) | até a sua ação | a sua ação |
|---|---|---|---|---|---:|---|
| 19:11:58,2 | C02 | vire 5 metros depois do começo da zebra à direita | não | a referência não freia no trecho | 3,67 s | alívio em 334 m |
| 19:12:15,2 | **C04** | freie 10 metros antes da placa de 100 | **sim** | — | 3,90 s | frenagem em 1.183 m |
| 19:12:24,0 | C05 | sem tirar o pé | não | sem tirar o pé (a referência não freia nem alivia) | 2,39 s | entrada (1.480 m) |
| 19:12:31,6 | C06 | vire no começo da zebra à direita | não | a referência não freia no trecho | 1,22 s | alívio em 1.834 m |
| 19:12:34,9 | C07 | freie 35 metros antes do começo da zebra à direita | não | sem bloco de voz antes da frenagem | 4,02 s | frenagem em 2.162 m |
| 19:12:46,6 | C09 | vire 30 metros antes do fim da zebra à direita | não | a referência não freia no trecho | 5,84 s | alívio em 2.606 m |
| 19:12:53,8 | C11 | vire 5 metros depois do começo da zebra à esquerda | não | a referência não freia no trecho | 3,90 s | alívio em 2.758 m |
| 19:13:17,9 | C12 | freie 15 metros depois da placa de 100 | não | a frase não cabe no bloco | 4,14 s | frenagem em 3.109 m |
| 19:13:43,0 | **C01** | freie 10 metros depois da placa de 100 | **sim** | — | 3,03 s | frenagem em 72 m |
| 19:13:49,6 | C02 | (a mesma) | não | a referência não freia no trecho | 4,30 s | alívio em 334 m |
| 19:14:06,9 | C04 | (a mesma) | não | **outra fala em andamento** | 3,09 s | frenagem em 1.176 m |
| 19:14:14,9 | C05 | sem tirar o pé | não | (o mesmo) | 2,56 s | entrada |
| 19:14:23,8 | C06 | (a mesma) | não | a referência não freia no trecho | 2,78 s | alívio em 1.911 m |
| 19:14:27,4 | C07 | (a mesma) | não | sem bloco de voz antes da frenagem | — | (a volta não chegou à C07) |

**Os 2 avisos pela voz foram gerados, entregues e tocados no jogo.** O log do CSP tem "voz: url tocou" para as 6 mensagens do rádio: a frase do coach, três resumos e os dois avisos. Não há nenhum "voz: falhou".

| aviso | voz gerada | entregue (rádio) | tocou no jogo | latência | o carro no começo e no fim da fala | o fim da fala até a sua frenagem | até o ponto dito |
|---|---|---|---|---:|---|---:|---:|
| C04 | sim (2,35 s) | id 4, 19:12:15 | 19:12:17,30 | **2,06 s** | 1.075 m → 1.213 m | **−0,51 s** (você freou em 1.183 m, ainda durante a fala) | 0,07 s |
| C01 | sim (2,37 s) | id 5, 19:13:43 | 19:13:43,45 | 0,44 s | 4.227 m → 58 m | **0,22 s** | 1,07 s |

**O que explica o problema (1), "não falou nada":**
1. **Só 2 dos 14 avisos tinham voz,** e isso é pela regra do ADR 0033:
   - 7 avisos são de trechos em que a referência não freia (a voz só vale onde ela freia);
   - 2 são "sem tirar o pé";
   - 2 são de trechos sem bloco de voz (C07);
   - 1 é de frase que não cabe no bloco (C12);
   - 1 foi bloqueado por outra fala.
2. **Os 2 que tocaram ficaram em cima da frenagem,** e um falou por cima dela. É provável que tenham se perdido no meio da pilotagem. O log diz que o jogo tocou, mas não diz se ficou audível.
3. **O aviso da C04 atrasou 2,06 s por causa do app do jogo.** Cada cartão do rádio fica na tela pelo menos max(5 s, fala + 2,5 s) (`CARTAO_MINIMO_S` e `FOLGA_DEPOIS_DA_VOZ_S`), e o aviso entra na fila atrás dele.
   - O resumo da volta de 1:32 tocou às 19:12:07,76, com 6,85 s; o cartão dele ficou até 19:12:17,1.
   - O aviso, que o backend entregou às 19:12:15, só tocou às 19:12:17,30. A prioridade que o backend dá ao aviso não chega ao jogo.
4. **O segundo aviso da C04 foi para a janela por "outra fala em andamento".**
   - O resumo da volta de 1:50 começou no começo do bloco (554 m) a 166,6 km/h. O backend calculou que ele acabava antes do `s_fala` da C04 (965 m), pela velocidade daquele momento.
   - O carro acelerou até uns 235 km/h e chegou ao `s_fala` antes: a reserva usa a velocidade do momento, e não o tempo que o carro leva até lá.

**O que explica o problema (2), "chega muito em cima":**
1. **O aviso foi feito para acabar 1,0 s antes da frenagem da referência, mas você freia antes dela,** e é justamente isso que o aviso corrige ("frenagem cedo").
   - Na C01, a referência freia em 122 m e você freou em 72 m: 50 m, uns 0,7 s antes.
   - Na C04, a referência freia em 1.216 m e você freou em 1.176 a 1.183 m.
   - Por isso, mesmo sem atraso, a fala acaba quase na sua frenagem: 0,22 s antes, na C01.
2. **Na janela, cada aviso aparece de 1,2 a 5,8 s antes da sua ação** (mediana de 3,7 s), porque o `s_fala` usa a mesma conta da voz. A frase escrita tem de 15 a 52 caracteres. A 200 km/h, isso é pouco para tirar o olho da pista, ler e agir.

### E.3.2 O tempo entre as ações, nas suas voltas desta sessão

Medi nas três voltas completas (1:42,045, 1:32,071 e 1:50,524), nos 9 trechos que tiveram aviso. Duas medidas:
- **"pedaço livre":** de quando a ação anterior acaba (acelerador em 0,90 ou mais e sem freio) até a sua ação no trecho;
- **"desde a curva anterior":** do começo da ação na curva anterior até a ação no trecho.

| trecho | a sua ação | pedaço livre (1:42 / 1:32 / 1:50) | desde a curva anterior (1:42 / 1:32 / 1:50) |
|---|---|---|---|
| C01 | frenagem (100 / 96 / 73 m) | **19,1 / 19,9 / 19,4 s** (a reta dos boxes, desde a C13) | 12,8 / 12,9 / 12,2 s |
| C02 | alívio (334 m) | 0 s (emendada na C01) | 6,5 / 7,0 / 6,4 s |
| C04 | frenagem (1.159 / 1.189 / 1.183 m) | **12,5 / 14,9 / 12,7 s** (a reta oposta) | 12,2 / 12,6 / 14,9 s |
| C05 | entrada (1.480 m) | 0 s (emendada na C04) | 7,4 / 7,6 / 7,3 s |
| C06 | alívio (1.827 / 1.845 / 1.834 m) | **8,4 / 8,9 / 8,6 s** | 6,5 / 6,6 / 6,4 s |
| C07 | frenagem (2.187 / 2.175 / 2.162 m) | 0 s (emendada na C06) | 7,3 / 6,3 / 6,1 s |
| C09 | alívio (2.555 / 2.606 / 2.606 m) | 3,0 / 2,9 / 3,6 s | 11,3 / 7,4 / 7,5 s |
| C11 | alívio (2.758 m) | 0 s (emendada na C10) | 5,8 / 4,7 / 4,8 s |
| C12 | frenagem (3.074 / 3.077 / 3.109 m) | 0 / 5,9 / 7,5 s | 7,4 / 6,8 / 24,3 s |

- **Há três pedaços livres longos por volta:** a reta dos boxes (19 s, porque você faz a C14 sem tirar o pé), a reta oposta (12,5 a 15 s) e antes da C06 (8,4 a 8,9 s).
- **No miolo, quase tudo é emendado:** a C09 tem 3 s, a C12 tem 6 a 7,5 s nas voltas sem rodada, e a C02, a C05, a C07 e a C11 têm 0 s.
- **Entre uma ação e a seguinte há de 4,7 a 7,5 s no miolo.** É esse tempo que sobra para um aviso de uma curva emendada, falado durante a curva anterior (o que hoje o ADR proíbe: "nunca dentro de uma curva").

### E.3.3 As opções, com os números desta sessão

Para cada opção: em quantos dos 9 trechos com aviso a fala cabe, em cada uma das três voltas, e a folga (do fim da fala até a sua ação, mínimo, mediana e máximo).
- **A condição para a fala caber:** ela começa num pedaço livre (fora de curva e de outra ação), acaba dentro dele, não passa por cima de outro aviso e acaba pelo menos 1,0 s antes da sua ação.
- **As durações** são as medidas com a voz do projeto.
- **As latências:** 0,45 s hoje (a C01, sem cartão na frente); 0,1 s com o aviso disparado no próprio jogo e o áudio já baixado. Esse 0,1 s é uma estimativa e não foi medido.
- **Nas opções A a D,** a folga é a maior possível (a fala no começo do pedaço). Ela pode ser encurtada, atrasando a fala, para um alvo como 2 a 3 s.

| opção | o que muda | trechos com voz (de 9; por volta) | folga (mín / mediana / máx) |
|---|---|---|---|
| hoje (medido) | a regra do ADR 0033: só onde a referência freia, no bloco da volta do modelo, terminando 1,0 s antes da frenagem da referência | 2 nas voltas desta sessão | **−0,51 s e 0,22 s** (os dois que tocaram) |
| **A** | a fala no seu pedaço livre, terminando antes da **sua** ação (e não da frenagem da referência), para freie, vire, acelere e "sem tirar o pé" | 3 / 4 / 4 (C01, C04, C06 e C12) | 3,1 / 9,8 / 17,1 s |
| **B** | A, com o aviso disparado no jogo pelo `s` do carro e o áudio baixado antes (sem a fila do cartão) | 3 / 4 / 4 | 3,4 / 10,2 / 17,5 s |
| **C** | B, com a fala curta: o verbo e o marco, sem "metros" ("Freie no cem, mais dez.", 1,67 s; "Vire na zebra, mais cinco.", 1,84 s; "Acelere no fim da zebra.", 1,47 s; "Sem tirar o pé.", 1,00 s) | 4 / 5 / 5 (+ C09) | 1,0 / 6,8 / 18,2 s |
| **D** | C, com a voz a 1,7x (cada fala fica 14% a 20% mais curta) | 4 / 5 / 5 | 1,3 / 7,1 / 18,4 s |
| **E** | B, com o aviso dito mais cedo: no pedaço livre anterior mais perto em que caiba, mesmo uma ou duas curvas antes, um aviso depois do outro | **9 / 9 / 9** | 3,4 / 16,2 / **48,1 s** |
| **E20** | E, com no máximo 20 s entre a fala e a ação | 7 / 6 / 8 | 3,4 / 10,4 / 19,9 s |
| **F** | E, com a fala curta | **9 / 9 / 9** | 1,0 / 13,2 / 39,7 s |
| **F20** | F, com no máximo 20 s | 6 / 7 / 7 | 1,0 / 11,0 / 19,4 s |
| **H** | C, juntando o aviso com o da curva anterior (só os dois pedaços livres mais perto; por exemplo, "Seis: vire na zebra. Sete: freie na zebra.", que mede 2,9 a 3,2 s a 1,4x) | 7 / 9 / 9 | 1,0 / 11,7 / 27,2 s |
| **G** | um bipe de 0,25 s disparado no jogo 1,0 s antes da sua ação, junto com a marca; ele diz "agora", e o que fazer vem da janela ou da lista (I) | **9 / 9 / 9** | 1,0 s (a escolher) |
| **I** | a lista lida nas retas longas, com as falas curtas: "Quatro: cem, menos dez. Cinco: sem tirar o pé. Seis: vire na zebra." mede 6,0 s a 1,4x e 5,0 s a 1,7x | na reta dos boxes cabem 9 avisos curtos (10 a 1,7x); na oposta, 6 a 7 | de 10 a 40 s até a curva (é para lembrar, e não para agir) |

**O que pesa em cada uma:**
- **O que vale para todas:** a latência e a reserva.
  - O aviso tem de furar a fila do cartão no app do jogo. Hoje ele espera o cartão anterior, como na C04, com 2,06 s.
  - A reserva do backend tem de usar o tempo da sua volta até o `s_fala`, e não a velocidade do momento. Isso evita o "outra fala em andamento" do segundo aviso da C04.
  - Sem essas duas correções, qualquer opção pode chegar 2 s atrasada.
- **A, B, C e D (o seu pedaço livre):** só a C01, a C04, a C06, a C12 (nas voltas sem rodada) e, com a fala curta, a C09 têm um pedaço livre. As emendadas (C02, C05, C07 e C11) nunca têm.
- **E e F (avisar mais cedo):** todos os 9 trechos ganham voz, mas a C09 e a C11 são ditas na reta oposta ou antes da C06, de 27 a 48 s antes da ação. É preciso guardar 2 a 4 dicas de cabeça.
- **E20 e F20:** com o limite de 20 s, 6 a 8 dos 9 ficam com voz.
- **H (juntar com a curva anterior):** 7 a 9 dos 9, a maioria com 6 a 22 s de antecedência. A frase de duas curvas cabe nos pedaços antes da C01, da C04 e da C06.
- **G (o bipe):** é o único que dá o "agora" em todos os trechos com a folga exata, mas sozinho não diz o que fazer.
- **G mais H ou I:** o que fazer chega antes, pela voz, e o bipe marca o ponto. É a combinação que cobre os 9 trechos e chega a tempo.
- **A janela:** pode mostrar o aviso desde o começo do seu pedaço livre, ou o aviso da curva seguinte desde a ação anterior.
  - Assim, o tempo para ler passa de 1,2 a 5,8 s para de 4,7 a 19,9 s ("desde a curva anterior", na tabela da E.3.2).
  - Mostrar as duas próximas dicas ao mesmo tempo também ajuda nas emendadas.
- **Duas mudanças de regra que várias opções pedem:**
  - **o aviso contra a sua ação, e não contra a da referência.** A sua frenagem desta sessão serve de estimativa; numa sessão nova, vale a da volta anterior;
  - **o aviso pela voz também onde a referência não freia** ("vire", "acelere" e "sem tirar o pé"). Hoje só vale onde ela freia.
- **Os limites desta leitura:**
  - são só três voltas completas, duas com rodada;
  - a latência de 0,1 s do disparo no jogo é uma estimativa;
  - a fala curta sem "metros" não foi testada no jogo para ver se você entende.

**O que preciso de você:** a decisão de quais opções seguir, e se a regra do ADR 0033 muda. Nada foi mudado no código. O merge e o instalador 0.9.0 continuam parados até depois disso e de um novo teste no jogo.

## Atualização de 20/11: as suas decisões depois do teste no jogo (parado antes do novo teste: você escolhe o molde)

**O pedido:** a "Atualização de 20/11" no fim do pedido 52 (a opção H, mais o bipe e a janela com os dois próximos avisos, com folga mínima de 3,0 s).

**Os commits:**
- `73c4186c`: a emenda "Decisões do Eduardo de 20/11" no ADR 0033, commitada antes do código;
- `9a40c004`: o código (backend e app do jogo 0.8.0), os testes e a documentação;
- o commit desta seção: a D.1, a D.2, as suítes e o relatório.

### O que fixei no ADR onde a decisão deixava lacuna

- **O perfil** (a volta de onde vêm o tempo e a sua ação):
  - a última volta da sessão que conta (completa, sem rodada e sem a IA);
  - antes dela, a "Sua melhor volta";
  - sem ela, a volta de referência.
  
  O perfil é tratado como um laço: o pedaço livre que atravessa a linha emenda o fim no começo.
- **A sua ação no "acelere":** a retomada do trecho (ADR 0030); sem ela, o primeiro ponto com o acelerador em 0,90 ou mais depois do ápice. No "freie" sem frenagem, vale a regra do "vire".
- **Os candidatos:** os dois pedaços livres que acabam mais perto antes do ponto do item 6. Se o ponto cai dentro de um pedaço, o pedaço acaba nele.
- **Os pares:**
  - num mesmo pedaço, os avisos formam pares na ordem da pista;
  - o número da curva vai por extenso ("Seis: …");
  - entre duas falas do mesmo pedaço há pelo menos 0,3 s;
  - **uma fala que não cabe manda os dois avisos dela para o segundo candidato,** e o plano é refeito.
- **A latência do disparo no jogo:** 0,1 s nas contas. É uma estimativa; o app registra no log do CSP o `s` do disparo e quanto o som demorou.
- **O molde:**
  - o padrão é (a) até a sua escolha;
  - só as placas perdem "placa de" em (b) e (c); os outros marcos guardam o nome e o lado;
  - a janela e o cartão continuam no molde (a), com "Curva N:".
- **O bipe:**
  - um tom de 2.000 Hz, com 0,25 s, gerado pelo código (`tools/csp_app/gerar_bipe.py`, `bipe.wav` na pasta do app);
  - toca num player próprio, que não corta a fala;
  - a marca no asfalto passou para o ponto dito, que é o mesmo ponto do bipe.
- **O tempo de reação do bipe: não confirmado, 0 s.**
  - Green (2000, "How Long Does It Take to Stop?") dá cerca de 0,70 a 0,75 s para uma frenagem totalmente esperada, mas li só por resumos (o apêndice da FHWA), e é um sinal visual.
  - Um estudo antigo com buzina dá 0,51 s, mas a data e a amostra não estão claras.
  - Nenhum dos dois é um sinal sonoro esperado ao volante. Pela sua regra, fica 0 s: o bipe soa no ponto.
- **O backend não entrega mais o aviso pela fila do rádio:** quem fala é o app do jogo. Por isso o app do jogo 0.8.0 é o par do backend 0.9.0. Um app do jogo mais antigo com este backend fica sem a voz dos avisos.

### O código

- **`core/engenheiro/plano.py` (novo, puro):**
  - o perfil, os pedaços livres e a sua ação;
  - o mais cedo entre a ação e o ponto dito, os dois candidatos e a folga de 3,0 s;
  - os pares, as falas o mais tarde possível e os três moldes.
- **`core/engenheiro/servico.py`:**
  - o perfil muda e o plano é refeito depois de cada volta que conta, com uma linha "plano" no registro;
  - a voz de cada fala é pedida, e o plano é refeito quando a duração real chega;
  - a lista ao app do jogo traz as falas planejadas (o `s_fala`, o texto, a duração e o áudio), os pontos da janela (`sJanela`, `sFimDaJanela`) e o bipe;
  - a reserva é medida pelo tempo do perfil.
- **`core/radio/servico.py`:**
  - o aviso corta o feedback em andamento, com uma linha "corte" no registro;
  - o feedback cortado volta à fila e só sai numa reta longa seguinte;
  - a reserva é medida pelo tempo do perfil, e não pela velocidade.
- **A rota nova:** `GET /api/radio/engenheiro/audio/{chave}`.
- **O app do jogo 0.8.0** (`radio_engenheiro.lua` e `manifest.ini`):
  - baixa o áudio das falas antes;
  - toca cada fala no quadro em que o carro passa o `s_fala` (`setInterval(acompanharOsAvisos, 0)`), com a janela aberta ou não;
  - tira o cartão da tela e corta a voz em andamento;
  - toca o bipe;
  - a janela mostra os dois próximos avisos, com o da vez em destaque;
  - a marca fica no ponto dito.
- **A conferência do Lua:** 40.715 tokens, sem erro de léxico e com os blocos certos. As 55 chamadas da API e os 15 métodos (agora com `setCurrentTime`) existem no SDK do CSP (`_conferir_lua.txt`).
- **A documentação:** a seção 9.7 de `docs/realidade_aumentada.md` e a linha do app do jogo em `docs/app_para_producao.md`.

### Os testes (`backend/tests/test_engenheiro.py`, 36 passando)

Os 11 testes novos e os 3 reescritos cobrem a lista do item 12, com dados sintéticos:
- **o pedaço livre,** que forma um laço;
- **a sua ação** em cada tipo de aviso, e as três voltas de onde ela pode vir: a de referência, a "Sua melhor volta" e a volta 5 da sessão. Uma volta que não conta não muda o perfil;
- **a folga de 3,0 s** contra o mais cedo entre a ação e o ponto dito;
- **o primeiro e o segundo pedaço,** e o aviso que não cabe;
- **a junção** de no máximo dois avisos (três no mesmo pedaço viram um par e uma fala sozinha, sem se encostarem);
- **a fala o mais tarde possível;**
- **o bipe** no ponto dito, a ausência dele em "sem tirar o pé" e a chave que o desliga;
- **o aviso que não espera:** ele não entra na fila do rádio, e o Lua tira o cartão;
- **o corte do feedback,** que só volta numa reta longa seguinte;
- **a reserva** pelo tempo do perfil;
- **a lista e o plano refeitos** depois de cada volta;
- **os três moldes.**

### D.1: as 5 sessões, com as três variantes do molde

As rodadas são as do rádio fora do tempo real, com a voz de verdade, sem o engenheiro e com os moldes (a), (b) e (c). As 20 rodadas terminaram sem erro (`_d1_2011_contar.py` e `_d1_2011.json`).
- **A folga real** é medida contra o que você fez de fato naquela passagem, na gravação: a fala começa no `s_fala` mais 0,1 s e acaba depois da duração. Fora do jogo, não dá para medir a latência do jogo.
- **Um erro meu na primeira contagem:** a busca da sua ação pegava, às vezes, a passagem da volta anterior quando o aviso era dito longe da curva. Corrigi, e os números abaixo já são os corrigidos.

| sessão | molde | avisos pela voz / só na janela | trechos com voz por volta (média) | folga até a sua ação (mín / mediana / máx) | abaixo de 3 s | até o ponto dito (mín / mediana / máx) | falas com 2 avisos | bipe até a sua ação (mediana) | cortes | feedback que mudou de bloco |
|---|---|---|---|---|---:|---|---:|---|---:|---:|
| 13/10 | (a) | 67 / 24 | 5,2 de 7,0 | 2,39 / 8,87 / 45,78 s | 10 de 64 | 3,19 / 9,04 / 48,04 s | 25 | -0,7 s (-30,2 m) | 3 | 13 |
| 13/10 | (b) | 73 / 19 | 5,6 de 7,1 | 2,36 / 8,89 / 44,05 s | 8 de 70 | 3,2 / 9,6 / 43,21 s | 25 | -0,7 s (-31,8 m) | 5 | 9 |
| 13/10 | (c) | 73 / 19 | 5,6 de 7,1 | 2,38 / 8,91 / 43,94 s | 9 de 70 | 3,19 / 9,59 / 43,2 s | 25 | -0,7 s (-31,8 m) | 5 | 8 |
| 18/10 | (a) | 67 / 41 | 4,8 de 7,1 | 2,46 / 6,75 / 49,74 s | 10 de 66 | 3,26 / 6,57 / 53,62 s | 15 | -0,68 s (-34,45 m) | 4 | 12 |
| 18/10 | (b) | 73 / 35 | 5,2 de 7,1 | 2,46 / 6,63 / 46,16 s | 7 de 72 | 3,28 / 6,4 / 50,03 s | 15 | -0,68 s (-34,95 m) | 4 | 13 |
| 18/10 | (c) | 69 / 39 | 4,9 de 7,1 | 2,46 / 6,8 / 47,06 s | 10 de 68 | 3,28 / 6,49 / 50,94 s | 15 | -0,68 s (-34,95 m) | 4 | 13 |
| 21/10 | (a) | 61 / 35 | 5,1 de 7,4 | 2,34 / 11,13 / 30,84 s | 8 de 58 | 3,01 / 10,29 / 37,94 s | 18 | -0,8 s (-47,5 m) | 2 | 20 |
| 21/10 | (b) | 62 / 34 | 5,2 de 7,3 | 2,37 / 8,1 / 30,83 s | 7 de 60 | 3,01 / 8,2 / 37,94 s | 18 | -0,8 s (-47,5 m) | 2 | 18 |
| 21/10 | (c) | 63 / 33 | 5,2 de 7,4 | 2,34 / 8,22 / 30,83 s | 7 de 61 | 3,01 / 8,68 / 37,94 s | 18 | -0,8 s (-47,5 m) | 3 | 18 |
| 12/11 | (a) | 38 / 16 | 5,4 de 7,7 | 2,31 / 7,44 / 22,23 s | 5 de 34 | 3,24 / 8,83 / 23,49 s | 10 | -0,6 s (-25,3 m) | 2 | 3 |
| 12/11 | (b) | 41 / 13 | 5,9 de 7,7 | 2,34 / 7,17 / 23,54 s | 5 de 37 | 3,23 / 8,83 / 23,59 s | 10 | -0,6 s (-25,3 m) | 2 | 3 |
| 12/11 | (c) | 40 / 14 | 5,7 de 7,7 | 2,33 / 7,46 / 23,6 s | 5 de 36 | 3,24 / 8,84 / 23,65 s | 10 | -0,6 s (-25,3 m) | 2 | 3 |
| 20/11 | (a) | 15 / 0 | 7,5 de 7,5 | 3,1 / 16,2 / 24,63 s | 0 de 12 | 3,95 / 16,97 / 42,58 s | 7 | -0,64 s (-35,4 m) | 0 | 1 |
| 20/11 | (b) | 14 / 0 | 7,0 de 7,0 | 3,01 / 12,95 / 21,16 s | 0 de 12 | 3,86 / 16,45 / 24,56 s | 5 | -0,64 s (-35,4 m) | 0 | 1 |
| 20/11 | (c) | 15 / 0 | 7,5 de 7,5 | 3,05 / 15,2 / 24,67 s | 0 de 12 | 3,9 / 16,63 / 42,62 s | 7 | -0,64 s (-35,4 m) | 0 | 1 |

| sessão | molde | motivos de "só na janela" | feedback sem / com | com a causa na voz (sem / com) | pendentes no fim (sem / com) |
|---|---|---|---|---|---|
| 13/10 | (a) | não coube com as outras falas do pedaço livre: 16; não cabe em nenhum dos dois pedaços livres antes da ação: 8 | 24 / 20 | 16 / 4 | 1 / 8 |
| 13/10 | (b) | não coube com as outras falas do pedaço livre: 10; não cabe em nenhum dos dois pedaços livres antes da ação: 9 | 24 / 20 | 16 / 2 | 1 / 10 |
| 13/10 | (c) | não coube com as outras falas do pedaço livre: 10; não cabe em nenhum dos dois pedaços livres antes da ação: 9 | 24 / 19 | 16 / 2 | 1 / 12 |
| 18/10 | (a) | não cabe em nenhum dos dois pedaços livres antes da ação: 26; não coube com as outras falas do pedaço livre: 10; volta de saída dos boxes: 5 | 22 / 22 | 15 / 3 | 1 / 6 |
| 18/10 | (b) | não cabe em nenhum dos dois pedaços livres antes da ação: 20; não coube com as outras falas do pedaço livre: 9; volta de saída dos boxes: 6 | 22 / 24 | 15 / 6 | 1 / 4 |
| 18/10 | (c) | não cabe em nenhum dos dois pedaços livres antes da ação: 25; não coube com as outras falas do pedaço livre: 9; volta de saída dos boxes: 5 | 22 / 24 | 15 / 5 | 1 / 4 |
| 21/10 | (a) | não cabe em nenhum dos dois pedaços livres antes da ação: 18; não coube com as outras falas do pedaço livre: 12; volta de saída dos boxes: 5 | 35 / 38 | 25 / 10 | 2 / 3 |
| 21/10 | (b) | não coube com as outras falas do pedaço livre: 19; não cabe em nenhum dos dois pedaços livres antes da ação: 10; volta de saída dos boxes: 5 | 35 / 38 | 25 / 11 | 2 / 3 |
| 21/10 | (c) | não coube com as outras falas do pedaço livre: 18; não cabe em nenhum dos dois pedaços livres antes da ação: 10; volta de saída dos boxes: 5 | 35 / 39 | 25 / 12 | 2 / 3 |
| 12/11 | (a) | não cabe em nenhum dos dois pedaços livres antes da ação: 14; não coube com as outras falas do pedaço livre: 2 | 13 / 8 | 7 / 2 | 0 / 7 |
| 12/11 | (b) | não cabe em nenhum dos dois pedaços livres antes da ação: 11; não coube com as outras falas do pedaço livre: 2 | 13 / 8 | 7 / 2 | 0 / 7 |
| 12/11 | (c) | não cabe em nenhum dos dois pedaços livres antes da ação: 12; não coube com as outras falas do pedaço livre: 2 | 13 / 8 | 7 / 2 | 0 / 7 |
| 20/11 | (a) | — | 4 / 3 | 2 / 1 | 0 / 1 |
| 20/11 | (b) | — | 4 / 3 | 2 / 1 | 0 / 1 |
| 20/11 | (c) | — | 4 / 3 | 2 / 1 | 0 / 1 |

**O que os números dizem:**
- **A voz cobre muito mais.**
  - Antes desta emenda, a D.1 tinha 17, 16, 12 e 5 avisos pela voz por sessão, e o teste no jogo, 2.
  - Agora são de 61 a 73 nas sessões longas, e 14 a 15 na de 20/11, onde todos os avisos foram pela voz.
  - Por volta, de 5 a 7,5 dos 7 a 7,7 trechos com aviso têm voz.
  - O molde (b) dá um pouco mais de voz, porque é o mais curto.
- **A folga real até a sua ação** tem mediana de 6,6 a 16 s e mínimo de 2,3 s.
  - Nas sessões antigas, ficam abaixo de 3,0 s de 5 a 10 avisos por sessão (7% a 17%). Na de 20/11, nenhum.
  - O plano dá 3,0 s contra o perfil, e nessas voltas você agiu até 0,7 s antes do que no perfil. É a variação de uma volta para a outra.
  - A folga até o ponto dito nunca fica abaixo de 3,0 s.
- **As falas longe da ação:** algumas saem de 30 a 50 s antes. A regra manda o aviso para o segundo pedaço livre, que no miolo pode estar a duas ou três curvas.
  - Por exemplo, "Quatro: freie 10 metros antes da placa de 100. Dez: vire 15 metros antes do começo da zebra à direita." é dita na reta oposta. A C10 vem uns 36 s depois.
- **Um efeito da regra do par que não cabe** (o ADR, item 7). Na sessão de 20/11, a C06 e a C07 cabem sozinhas no pedaço antes da C06, mas não juntas. As duas vão para a reta oposta, e a C06 é dita uns 14 s antes, em vez de uns 6 s.
  - Outra regra seria a C06 ficar no pedaço dela e só a C07 ir para trás.
  - Não mudei a regra, porque ela está no ADR, gravado antes do código.
- **O bipe soa, na mediana, de 0,6 a 0,8 s depois da sua ação** (de 25 a 48 m depois). Ele marca o ponto dito, e você freia ou alivia antes dele: o bipe é a correção.
  - Há alguns casos de até 10 a 18 s, em voltas com rodada ou nos boxes.
- **Os pares:** de 5 a 25 falas com dois avisos por sessão.
- **O feedback perdeu espaço.**
  - Com os avisos de todos os tipos reservando as retas primeiro (item 11), o feedback com a causa na voz caiu de 16 para 2 a 4 (13/10), de 15 para 3 a 6 (18/10), de 25 para 10 a 12 (21/10) e de 7 para 2 (12/11).
  - As mensagens pendentes no fim subiram, de 1 para 8 a 12 em 13/10 e de 0 para 7 em 12/11.
  - Houve de 0 a 5 cortes por sessão. É a regra do item 11, "o feedback usa o que sobrar", mas é uma troca que você deve ver.

### D.2: a janela e os áudios

- **A janela:** `_previa_2011.html` e `_previa_2011.png`, com o desenho da janela do app 0.8.0 num SVG e os avisos do engenheiro de verdade (a rodada de 20/11, molde (a)). Há três pontos com dois avisos na tela:
  - em 0 m, a C01 em destaque e a C02 embaixo;
  - em 1.400 m, a C05 e a C06;
  - em 2.485 m, a C09 e a C11.
- **Os áudios, para você ouvir e escolher:** `data/radio/[teste] vozes do engenheiro 20-11/` (fora da pasta do jogo e fora do git), uma subpasta por variante. Cada uma tem:
  - as 34 falas sozinhas dos 15 trechos (cada ação possível na volta do modelo);
  - de 17 a 18 falas com dois avisos que a D.1 encontrou;
  - um `indice.json` com o texto e a duração de cada arquivo, também copiado em `_vozes_2011.json`.

| variante | exemplo (C01, freie) | falas sozinhas (mín / mediana / máx) | falas com dois (mín / mediana / máx) |
|---|---|---|---|
| (a) | "Freie 10 metros depois da placa de 100." (2,37 s) | 1,52 / 2,99 / 3,66 s | 4,77 / 6,85 / 8,09 s |
| (b) | "Freie 10 depois do 100." (1,52 s) | 1,18 / 2,58 / 3,25 s | 3,92 / 5,68 / 7,29 s |
| (c) | "Freie no 100, mais 10." (1,67 s) | 1,18 / 2,79 / 3,36 s | 4,06 / 5,97 / 7,71 s |

Mais exemplos:
- C04, freie: (a) "Freie 10 metros antes da placa de 100." 2,35 s; (b) "Freie 10 antes do 100." 1,41 s; (c) "Freie no 100, menos 10." 1,70 s.
- C02, vire: (a) "Vire 5 metros depois do começo da zebra à direita." 3,13 s; (b) "Vire 5 depois do começo da zebra à direita." 2,73 s; (c) "Vire no começo da zebra à direita, mais 5." 2,81 s.

### As suítes

- **backend, a suíte inteira:** **1080 passando**, nenhuma falha (11 min 11 s; 37 avisos do scikit-learn, os de sempre; `_testes.txt`). O engenheiro, o rádio, o 45 e a referência são 109 deles;
- **front:** 180 testes passando, e o `tsc` sem erro;
- **desktop:** 4 testes passando;
- **Lua:** passa na conferência contra o SDK do CSP (`_conferir_lua.txt`).

### O cartão para o teste no jogo (preencha depois da sessão)

Para cada trecho em que o engenheiro avisou, marque sim ou não:

| trecho | ouvi | entendi | deu tempo | anotação |
|---|---|---|---|---|
| C01 | | | | |
| C02 | | | | |
| C03 | | | | |
| C04 | | | | |
| C05 | | | | |
| C06 | | | | |
| C07 | | | | |
| C08 | | | | |
| C09 | | | | |
| C10 | | | | |
| C11 | | | | |
| C12 | | | | |
| C13 | | | | |
| C14 | | | | |
| o bipe | | | | |

### O que falta

1. **A sua escolha do molde,** ouvindo os áudios da pasta "[teste]". Ela entra no ADR como a decisão de 20/11 sobre o molde.
   - No backend, a escolha é a variável `AT_ENGENHEIRO_MOLDE`, que hoje vale (a). Com a sua escolha, ponho o valor no padrão do código.
2. **O seu "pode instalar":** depois disso, você roda o `instalar.ps1` do app do jogo 0.8.0.
3. **O teste no jogo de novo,** com o roteiro da Parte E: pelo menos 10 voltas, até 45 minutos, na pista original. Depois, preencha o cartão acima.
4. **Duas coisas para você olhar antes do teste** (não mudei nada):
   - o feedback perdeu espaço para os avisos (D.1);
   - a regra do par que não cabe manda os dois avisos para o segundo pedaço.
5. **O merge em `develop` e o instalador 0.9.0** continuam parados até depois do teste.

## A decisão de 20/11 sobre o molde: o (b) (parado antes do teste no jogo)

Você ouviu as três variantes e escolheu o **molde (b)**: "Freie 10 depois do 100.".

- **O ADR 0033** ganhou a seção "A decisão de 20/11 sobre o molde" (`e6147005`, antes do código). O item 8 da emenda de 20/11 agora remete a ela.
- **O código:** `MOLDE_PADRAO = "b"` em `backend/core/engenheiro/plano.py`. O `Engenheiro` usa esse padrão quando `AT_ENGENHEIRO_MOLDE` não está definida ou tem um valor que não existe. As variantes (a) e (c) continuam disponíveis pela variável.
- **Nada mais muda:**
  - a janela e o cartão continuam escrevendo "Curva N: <frase>" no molde (a);
  - "Sem tirar o pé." e "no ponto marcado" ficam iguais;
  - o app do jogo não muda: ele só toca o áudio que o backend gera.
- **`docs/realidade_aumentada.md`** (seção 9.7): o (b) é o padrão.
- **O teste novo:** `test_o_molde_padrao_e_o_b_da_escolha_de_20_11`.
- **As suítes:**
  - o engenheiro e a referência: 47 passando;
  - os testes com "radio" no nome: 66 passando;
  - backend, a suíte inteira: **1081 passando**, nenhuma falha (10 min 26 s; os 37 avisos de sempre).
  - O front, o desktop e o Lua não mudaram.
- **As durações no (b),** da D.2: a mediana é 2,58 s nas falas sozinhas e 5,68 s nos pares. Os números da D.1 com o (b) estão na tabela da D.1 acima, nas linhas "(b)": 73, 73, 62, 41 e 14 avisos pela voz (13/10, 18/10, 21/10, 12/11 e 20/11); a folga até a sua ação tem o mínimo de 2,34 s e a mediana de 6,6 a 13,0 s.

### O que falta

1. **O seu "pode instalar":** depois dele, você roda o `instalar.ps1` do app do jogo 0.8.0.
2. **O teste no jogo de novo,** com o roteiro da Parte E: pelo menos 10 voltas, até 45 minutos, na pista original. O backend do repositório já fala no (b), sem precisar da variável. Depois, preencha o cartão da seção "Atualização de 20/11".
3. **Duas coisas para você olhar antes do teste** (não mudei nada):
   - o feedback perdeu espaço para os avisos (D.1);
   - a regra do par que não cabe manda os dois avisos para o segundo pedaço.
4. **O merge em `develop` e o instalador 0.9.0** continuam parados até depois do teste.
5. **O envio:** nada foi enviado. Para enviar a branch:
   `git -C C:/Users/Dokas/Desktop/f1-telemetry-analyzer push origin etapa/engenheiro`

### O "pode instalar" (21/11, 0h01)

- **Você deu o "pode instalar" do app do jogo 0.8.0.** Quem roda o `instalar.ps1` é você, como o script e o pedido dizem: ele pede confirmação na tela e grava na pasta do jogo, onde eu não escrevo.
- **O que conferi antes:**
  - o `acs.exe` está fechado;
  - o pacote `tools/csp_app/radio_engenheiro/` está na 0.8.0 (`manifest.ini`) e tem o `bipe.wav`.
- **O comando** (na pasta do repositório):
  `powershell -NoProfile -ExecutionPolicy Bypass -File tools\csp_app\instalar.ps1`
- **A mensagem final do script** lista só as janelas "Rádio", "Minimapa" e "Mapa aproximado". A janela "Engenheiro" também é instalada e é ligada na mesma barra de apps. Não mudei o script.
- **Depois da instalação:** o app do repositório (o backend na porta 8000, o front e a janela) antes do jogo, e o teste com o roteiro da Parte E e o cartão.

## A leitura do item 13 (21/11, 10h43): parada, não achei o teste

Você pediu a leitura do novo teste no jogo, com o app do jogo 0.8.0 e o molde (b). **Não achei sinal de sessão depois da instalação**, então não fiz a leitura, para não inventar resultado. Nenhum código mudou.

- **O jogo:** o `log.txt` e o `custom_shaders_patch.log` (em `Documentos\Assetto Corsa\logs`) são de **20/11, 19h16**: a sessão do teste anterior, com o app do jogo 0.7.0. O jogo regrava esses arquivos a cada vez que abre, então ele não foi aberto depois disso.
- **O app do jogo 0.8.0** foi instalado em 20/11, às 21h10, e a pasta dele não tem a subpasta `voz`, que ele cria quando baixa a primeira fala.
- **As gravações e os registros:** a última gravação em `data/recordings` e o último `.engenheiro.jsonl` em `data/radio` são os de `2026-11-20_19-06-14`. Na pasta de dados do app instalado não há gravação nova.
- **O app do repositório:**
  - a janela do Electron que abri em 21/11, às 0h10, fechou às 2h17;
  - o backend da porta 8000 também não está mais no ar.
- **O cartão e as anotações** chegaram com o texto do modelo, entre colchetes, sem as respostas.

### O que falta

1. **Confirmar se o teste foi feito.** Se você rodou o teste em outra máquina, ou com outra pasta de dados, me diga onde estão a gravação e o `.engenheiro.jsonl`.
2. **Se o teste não foi feito:** eu abro o app do repositório de novo (o backend, o front e a janela). Depois, você faz o teste e preenche o cartão da seção "Atualização de 20/11".
3. **A leitura,** depois do teste: as tabelas da E.3.1 e da E.3.2, com a voz, a latência, as folgas, o bipe e a sua ação nas voltas seguintes, mais o FPS, os logs do CSP e o seu cartão.

## O teste de 21/11 (sessão `2026-11-21_18-10-46`): "o engenheiro não está falando e nem mostrando nada" (18h20)

O engenheiro está ligado e ativo, com o molde (b), mas **a lista dele está vazia porque nenhuma volta contou até as 18h20.** É a regra do ADR 0033 (itens 1 e 8): a lista de avisos sai da comparação de uma volta que conta com a referência de cada trecho. Sem lista, não há fala, nem janela, nem marca. Nenhum código mudou.

| volta | tempo | o que o rádio registrou |
|---|---|---|
| 1 | 2:54,441 | fora da análise: não começou na linha (saída dos boxes) |
| 2 | 1:36,567 | incompleta: 1 microssetor sem medida (parada ou longe do traçado) |
| 3 | 1:51,310 | rodada (perdeu 19,9 s na C13) |
| 4 (em andamento) | | marcada como volta de saída dos boxes |

- O backend não registrou nenhum erro nem aviso. O app do jogo busca a lista do engenheiro o tempo todo, e ela vem vazia.
- O `.engenheiro.jsonl` desta sessão ainda não existe: a primeira linha dele é a da primeira volta que conta.
- **Para o engenheiro começar:** uma volta inteira, começada na linha, sem rodada e sem sair do traçado. Os avisos aparecem a partir da volta seguinte a ela.

## O teste de 21/11: os problemas que você apontou (18h47), com os números da sessão (parado: a decisão é sua)

Fontes: o `.engenheiro.jsonl` da sessão `2026-11-21_18-10-46` e o log do CSP. Nenhum código mudou.

**A parte técnica funcionou.**
- Cada fala tocou de 0,06 a 0,08 s depois do disparo no jogo.
- Cada bipe tocou a menos de 1 m do ponto dito.
- O FPS ficou entre 63 e 68 de média.
- Três voltas contaram para o plano: a 5, a 6 e a 9. Pela voz saíram 28 avisos, em falas de um ou dois avisos; outros 16 ficaram só na janela.

### 1. "O engenheiro não passa a informação de maneira clara; por que não usamos o bipe para identificar onde frear?"

O bipe de hoje (ADR 0033, emenda de 20/11, item 9) toca no **ponto dito** de cada aviso de "freie", "vire" e "acelere". É um som só para três ações diferentes. Na sessão:

- **Nos avisos de "vire", o bipe veio de 91 a 95 m depois da sua ação** (C06 e C11; na C09, 68 m depois). A sua ação, nesses trechos, é o primeiro alívio ou a primeira frenagem; o ponto dito é a entrada na zebra. Quando o bipe toca, você já está na curva.
- **Nos avisos de "freie"** (C04 e C12), o bipe veio de 23 a 57 m depois da sua frenagem de costume. Isso é a correção que o aviso pede ("freie mais tarde"), mas sem nada que avise que o bipe vem.
- **Numa volta, tocaram até 8 bipes** (C01, C02, C04, C06, C08, C09, C11, C12 e C14 aparecem no log), e cada um marca uma coisa diferente.

### 2. "O rádio dá muita informação, ele fala da curva 1 até a 11"

- **Todos os tipos de aviso vão para a voz** (emenda de 20/11, item 4). Por volta foram 3 a 4 falas do engenheiro, com 5 a 6 avisos, mais o feedback do rádio (o resumo e o coach).
- **As falas saem muito antes da curva:** de 400 a 2.000 m antes do ponto dito. Por exemplo, "Onze: … Doze: …" foi dita em s = 1.510, e os pontos estão em 2.849 e 3.123: de 1.340 a 1.610 m depois. Entre a fala e a curva, você passa pela C06 até a C10. Isso vem da regra do par e do segundo pedaço livre (emenda de 20/11, item 7), que eu tinha apontado na D.1 ("avisos muito longe da curva").

### Opções para a sua decisão (não apliquei nenhuma)

**O bipe:**
- **(B1)** O bipe só para "freie", no ponto de frenagem dito. "Vire" e "acelere" ficam sem bipe.
- **(B2)** A B1 com uma contagem curta: três bipes em ritmo fixo, e o último no ponto de frenagem. Você antecipa o ponto em vez de reagir ao bipe.
- **(B3)** O bipe como marca de frenagem em toda curva com frenagem da referência, sem depender de aviso de voz.

**A quantidade:**
- **(Q1)** No máximo um ou dois avisos por volta: os trechos com a maior perda. O mesmo aviso se repete até ser aplicado.
- **(Q2)** Só o aviso da próxima curva, no pedaço livre logo antes dela. Sai o segundo pedaço e saem os pares, e o aviso que não couber fica só na janela.
- **(Q3)** A Q1 e a Q2 juntas: um aviso de cada vez, perto da curva, e só nos trechos que mais perdem.

Você disse que achou diversos problemas. Se houver mais itens, eu os registro aqui antes da leitura completa do item 13.

## A "ficha da curva": o formato que você pediu (21/11, 18h51), com a proposta (parado: a decisão é sua)

O seu pedido:

> "Curva X, freie entre a placa de 50 e 100, mova o carro para a zebra do lado X e mantenha X velocidade. Curva X pode ser realizada com pé embaixo ou trail braking."

Montei essa fala para as 14 curvas, com a volta de referência, os marcos da pista e a geometria, e medi a duração de cada uma com a voz do projeto. **Nenhum código do app mudou:** é um script de conferência (`_ficha_2111.py` e `_ficha_2111.json`).

### O que entra em cada ficha e de onde sai

- **A frenagem:** o ponto de frenagem da referência, dito como o intervalo entre as duas placas que o cercam ("entre a placa de 100 e a de 50"). Sem placa no trecho, entra o marco mais perto, no molde (b).
- **A técnica:**
  - "de pé embaixo": sem frenagem, com o acelerador em 0,90 ou mais de 50 m antes da entrada até o ápice;
  - "só um alívio": sem frenagem, com o acelerador abaixo de 0,90;
  - "com trail braking": o freio ainda pisado 10 m ou mais depois da entrada;
  - "frenagem em linha reta": o freio solto antes da entrada.
- **O movimento do carro:**
  - "entre pela X": o lado da pista em que a referência está na frenagem, quando passa da metade da meia largura;
  - "tangencie a zebra da X": a zebra de dentro no ápice, quando a referência passa a 1,5 m ou menos da borda.
- **A velocidade:** a mínima da referência, arredondada de 5 em 5 km/h. Nas curvas de pé embaixo, a velocidade no ápice ("passe a 190").
- **A marcha** fica só na escrita (na janela). A marcha gravada vai de 0 a 6, e na reta oposta a referência está em sexta, mas não conferi se ela é a marcha real do carro.

### As 14 fichas, com a duração da fala

| curva | a fala (Daniel a 1,4x, sem a vinheta) | duração |
|---|---|---:|
| C01 | Curva um, à esquerda. Freie entre o 100 e o 50, com trail braking. Entre pela direita e tangencie a zebra da esquerda. Mínima de 105. | 9,75 s |
| C02 | Curva dois, à direita. Freie no começo da zebra à direita, com trail braking. Tangencie a zebra da direita. Mínima de 105. | 9,30 s |
| C03 | Curva três, à esquerda. Só um alívio. Entre pela direita e tangencie a zebra da esquerda. Mínima de 115. | 8,17 s |
| C04 | Curva quatro, à esquerda. Freie entre o 200 e o 100, com trail braking. Mínima de 135. | 7,17 s |
| C05 | Curva cinco, à esquerda. De pé embaixo. Entre pela direita. Passe a 190. | 6,82 s |
| C06 | Curva seis, à direita. Freie logo depois do 50, com trail braking. Mínima de 175. | 7,37 s |
| C07 | Curva sete, à direita. Freie 35 antes do começo da zebra à direita, com trail braking. Entre pela esquerda e tangencie a zebra da direita. Mínima de 90. | 11,05 s |
| C08 | Curva oito, à esquerda. Freie no começo da zebra à esquerda, com trail braking. Mínima de 95. | 7,20 s |
| C09 | Curva nove, à direita. De pé embaixo. Passe a 175. | 5,48 s |
| C10 | Curva dez, à direita. Freie 10 antes do começo da zebra à direita, com trail braking. Mínima de 85. | 7,65 s |
| C11 | Curva onze, à esquerda. De pé embaixo. Passe a 175. | 5,47 s |
| C12 | Curva doze, à esquerda. Freie entre o 100 e o 50, com trail braking. Entre pela direita. Mínima de 110. | 8,45 s |
| C13 | Curva treze, à esquerda. De pé embaixo. Entre pela direita. Passe a 165. | 7,25 s |
| C14 | Curva catorze, à esquerda. De pé embaixo. Passe a 220. | 5,40 s |

**Os áudios, para você ouvir:** `data/radio/[teste] fichas das curvas 21-11/` (`C01.wav` a `C14.wav`), fora da pasta do jogo e fora do git.

### Três cuidados para a ficha ser certa ("assertiva")

1. **"Trail braking" aparece em todas as curvas com frenagem,** porque a IA que fez a volta de referência segura o freio depois da entrada em todas. O ADR 0032 (item 5) diz que os pedais da IA são desenhados, nunca julgados. Para dizer a técnica ao piloto, eu usaria a sua melhor passagem em cada curva, e não a IA. Também dá para dizer só "freie" e deixar a técnica de fora.
2. **O acelerador da IA cai a zero por 2 a 4 m nas trocas de marcha.** Sem um filtro, a C05, a C09, a C11, a C13 e a C14 saíam como "só um alívio" (corrigi no script: só conta como alívio uma queda de 10 m ou mais). **A mesma queda pode afetar a regra "sem tirar o pé" do engenheiro de hoje,** que olha o mínimo do acelerador. Isso é para conferir no código, se você decidir.
3. **A ficha é longa: de 5,4 a 11 s.** Só cabe inteira nas duas retas longas: a dos boxes, antes da C01, e a oposta, antes da C04. Falada curva por curva, ela repete o problema 2 ("muita informação").

### A proposta: como entregar a ficha sem encher o rádio

1. **Uma curva de foco por vez:** a curva em que você mais perde, contra o ruído do trecho. Ela continua o foco até a conferência mostrar que você aplicou, ou por 3 voltas; depois vem a seguinte.
2. **A ficha inteira só para a curva de foco,** dita na reta longa antes dela. A janela mostra a ficha escrita da curva de foco a volta toda.
3. **Na volta, perto da curva de foco, só o lembrete curto** ("Um: entre o 100 e o 50.", de 1,5 a 2,5 s), no pedaço livre logo antes.
4. **O bipe só na frenagem da curva de foco:** três bipes em ritmo fixo, com o último no ponto de frenagem (a opção B2 da seção anterior). Curvas de pé embaixo não têm bipe.
5. **Depois da curva, a conferência** que já existe ("Curva 1: freou 20 m cedo").

As outras curvas ficam caladas até virarem o foco. Isso vem dos achados da pesquisa:
- uma instrução de cada vez, com marcos que o piloto vê (placa, zebra);
- falar só nas retas, quando a carga do piloto é menor;
- uma só voz para o piloto.

Fontes:
- [Blayze, os 5 pontos de referência de cada curva](https://blayze.io/blog/car-racing/5-reference-points-for-every-corner-on-the-race-track)
- [Driver61, a entrada da curva](https://driver61.com/uni/corner-entry/)
- [Speed Secrets, notas de frenagem e entrada](https://speedsecrets.com/wp-content/uploads/2019/01/Braking-Entry-Notes-1-15-19.pdf)
- [Red Bull Racing, o guia do rádio](https://www.redbullracing.com/int-en/bulls-guide-to-team-radio)
- [Porsche Christophorus, "Off Camera"](https://newsroom.porsche.com/EN/Christophorus/Off-Camera.html)
- [Autosport, os segredos do rádio na corrida](https://www.autosport.com/f1/news/the-secrets-of-in-race-radio-chat-5102490/5102490/)

### O que precisa da sua decisão

1. **O formato da ficha:** este texto, ou com mudanças, depois de ouvir os áudios.
2. **A técnica:** sair da sua melhor passagem, ou ficar fora da fala.
3. **A entrega:** a proposta acima (uma curva de foco, a ficha na reta longa, o lembrete curto e o bipe só na frenagem), ou outra.
4. **Depois da decisão:** o ADR 0033 ganha a emenda antes do código, como nas outras vezes. Para isso, é melhor um pedido novo com as decisões.
