# Pedido 52: relatório

- **Pedido:** `docs/prompts/2026-11-15_52_engenheiro-que-acompanha-a-volta.md` (o engenheiro que acompanha a volta).
- **Pasta e branch:** `C:\Users\Dokas\Desktop\f1-telemetry-analyzer`, `etapa/engenheiro` (a partir de `develop` em `14fe1ca0`, com o merge do 51, `c4869295`).
- **Atualização de 16/11 e 17/11 (as duas seções no fim):** as decisões estão no ADR 0033 (emenda, itens 1 a 10) e no código.
  - A B.4 e a D.1 foram refeitas: o feedback com o engenheiro perde a causa na voz em 6 mensagens, contra 42 antes.
  - A suíte do backend passou: **1069 testes**.
  - **Pronto para o seu teste no jogo (a Parte E).**
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
  - o commit deste relatório
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
