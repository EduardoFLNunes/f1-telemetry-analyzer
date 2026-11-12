# Relatório do pedido 50: a linha do projeto (parado na Parte D, o teste no jogo)

- **Pedido:** `docs/prompts/2026-11-12_50_linha-do-projeto.md`.
- **Situação:** **parado na Parte D,** com o roteiro do teste no jogo pronto para você.
  - As Partes 0, A, B e C estão feitas.
  - A conferência da codificação (A.4) parou uma vez. Você escolheu a emenda (a), que entrou no ADR 0031 antes de seguir.
  - **Nada foi enviado ao GitHub.** O envio do pedido 49 ainda não foi feito, e este pedido espera por ele (veja "O envio").
- **Pasta:** `C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47`.
- **Branch:** `etapa/linha-do-projeto`, a partir de `develop` em `e873d6a6`.
- **Commits:**
  - `2bf248c1` Pedido 50: o texto do pedido (a linha do projeto);
  - `3f777af4` Pedido 50, Parte A: ADR 0031 (a linha do projeto), registrado antes de qualquer busca, calibração ou arquivo de linha;
  - `02f6fd8e` Relatório do pedido 50: parado na conferência da codificação (A.4); o medidor (M-v2 escolhido), o `trocar_linha.ps1` com L1 e L2 e o código da Parte B;
  - `eb6064b6` Pedido 50: emenda ao ADR 0031 (item 13, a sua decisão, opção a): o raio do C0 pela curvatura de 12 m e a tolerância de 10% na conferência;
  - `99d76e2f` Pedido 50, Parte B: a L1 (montagem por trecho), a L2 (busca com o M-v2 e a região de confiança) e os arquivos do jogo;
  - o commit deste relatório, com a conferência entre as sessões e os arquivos de handoff (o hash está no chat).
- **Merges:** nenhum. O merge vem depois das Partes E e F.
- **Arquivos de handoff** (`docs/handoff/2026-11-12_50_linha-do-projeto…`):
  - `_relatorio.md` (este);
  - `_conferencia.json` (B.1: a escada, a conferência por trecho e os limites das restrições);
  - `_medidor.json` (B.2: os três medidores, os `β` e o Spearman por microssetor);
  - `_l1.json` e `_l2.json` (B.3: a escolha por trecho, as emendas, a busca e as medidas de cada linha);
  - `_arquivos.json` (B.4: os arquivos do jogo e os sha256);
  - `_linhas.png` (B.3: as linhas sobre a pista, com a C06, a C09, a C10 e a subida dos boxes);
  - `_testes.txt` (a suíte do backend).

## Em uma frase

**As duas linhas do projeto estão prontas para o jogo,** sem nada do `fast_lane.ai` na saída.
- **A L1** é a montagem por trecho da C2, da C3 e da C4, com 8 emendas nas retas. O teto dela no jogo do 49 é −0,46 s.
- **A L2** é a busca genética a partir da L1, a até 1,0 m dela (usou no máximo 0,63 m).
- **A codificação nova** (uma spline no plano X/Z) tira as quinas da grade, mas não a ondulação da linha central na subida dos boxes: a L1 ainda tem um raio de 125 m em 3.898 m. Ali, a C4 não fez a IA frear no 47.
- **Os medidores discordam muito.** Contra o C0, o M-v2 (o escolhido) prevê −1,36 s para a L1 e −2,33 s para a L2. O calibrado (M-cal) prevê −0,01 s e −0,41 s, e é o que mais acertou o jogo na volta inteira.

## Parte 0: a pasta

1. **A pasta do 47** estava como a Parte 0 pede:
   - na branch `etapa/modelo1-por-trecho`, sem mudança sem commit;
   - já juntada a `develop` (as duas em `e873d6a6`);
   - nenhuma pasta tinha `develop` aberta. A principal está em `etapa/replay-e-radio-que-ensina`, e a do 48 em `etapa/diagnostico-m1`. As duas não foram tocadas, salvo o item 2.
2. **O envio do 49 não foi feito:** `origin/develop` está em `bbff5c97`, 13 commits atrás do local, sem divergir (o remoto é ancestral do local). Por isso, segui sem enviar nada.
3. **O texto do pedido:** copiado e commitado (`2bf248c1`). O commit guarda LF, e com CRLF o sha256 bate com o da principal (`dda355a7…6a01a36`). **Apaguei só esse arquivo na principal,** que ficou limpa.
4. **Os imports e os dados:**
   - o `.venv` da principal, rodando de dentro de `f1-telemetry-analyzer-47\backend`. Nada foi instalado;
   - as junções (`data\ml`, `data\recordings`, `data\cache`) só foram lidas;
   - as gravações da cópia (as 7 sessões do 47, 28 arquivos) só foram lidas, pelo `carregar_voltas_do_teste` do 49. Os sha256 delas estão no `_medidor.json`;
   - a saída vai para `data\linha_do_projeto\`, que entrou no `.gitignore` (`3f777af4`). Os `fast_lane.ai` vão para `data\pista_teste\linhas\L1` e `L2`.
   - **A foto de `data\ml`, `data\cache` e `data\recordings` da principal** foi tirada antes das contas da Parte B e de novo depois da suíte (veja "Os dados da pasta principal").
5. **O `acs.exe`** estava fechado antes de cada conta (a conferência, o medidor, a L1, a busca e a suíte).

## Parte A: o ADR 0031 (`3f777af4`)

**Commitado antes de qualquer busca, calibração ou arquivo de linha.** O número estava livre em todas as branches, locais e remotas, e uma linha no índice entrou no mesmo commit.

**Medido antes do registro, só a geometria** (Contexto, item 4 do ADR):
- **a grade de 2 m sozinha estraga o raio do arquivo.** A linha da IA projetada na grade e escrita de volta pelo escritor do 47 cai de 37,7 m para 19,9 m de menor raio na C01. A interpolação linear cria quinas, e o raio de três pontos do arquivo pega cada uma;
- **a linha central ondula na subida dos boxes:** a curvatura vai de −0,011 a +0,013 1/m entre 3.860 e 3.940 m;
- **a `#0013` não fecha na linha de chegada:** perto de s = 0, o raio estimado cai para 3 a 15 m.

**O que o ADR fixa:**
- **a linha do projeto:** produzida pelos algoritmos do projeto, no formato do projeto, sem copiar o `fast_lane.ai`;
- **a meta:** a melhor volta válida da linha, igual ou menor que a dos dois blocos de C0 vizinhos;
- **o teste:** cinco blocos de 9 voltas, na ordem sorteada com a semente 50: **C0, L1, C0, L2, C0**;
- **a codificação nova:** uma spline cúbica periódica no plano X/Z, com a curvatura contínua e os pontos mais densos nas janelas das curvas. A escada de espaçamento é 10/25, 8/20, 6/15 e 5/12,5 m. As restrições por trecho são 90% do menor raio e 110% da maior taxa das 150 voltas;
- **os três medidores e a escolha** pelo Spearman por microssetor;
- **a região de confiança:** 1,0 m da L1;
- **a L1, a L2, os arquivos, o que se espera e a regra da referência** para a Parte E.

**Uma diferença do pedido:** ele cita o item 4 do ADR 0029 para a volta válida, mas a regra está no item 5 (o item 4 é o das voltas). O ADR 0031 segue o item 5 e registra isso.

## A parada na conferência e a emenda (a)

- **A primeira conferência (A.4) não passou em nenhum degrau da escada.**
  - A distância passou folgada.
  - O menor raio por trecho não ficou a 5%: a `#0013` convergiu com o espaçamento fino, e o C0 piorou. Sem regularização, a spline fina segue o ruído dos pontos do próprio arquivo, e o menor raio é um valor extremo, decidido por um ponto só.
- **Parei, relatei (`02f6fd8e`) e perguntei.**
- **A sua decisão: a opção (a).**
  - Entrou no ADR como o item 13 (`eb6064b6`), antes de refazer a conferência e antes de qualquer linha nova.
  - O raio do C0 passa a ser medido como o da `#0013`: pela curvatura de 12 m, na lateral da grade.
  - A tolerância do raio passa a 10%. A distância continua em 0,10 m.

## Parte B.1: a codificação nova e a conferência

O comando: `python -m ml.scripts.linha_do_projeto conferencia`.

| par (m) | genes | C0: p95 da distância | C0: pior raio | `#0013`: p95 | `#0013`: pior raio | passa |
|---|---:|---:|---|---:|---|---|
| 10/25 | 331 | 0,013 m | 17,8% | 0,026 m | 31,5% | não |
| 8/20 | 412 | 0,009 m | 13,5% | 0,017 m | 19,5% | não |
| **6/15** | **546** | **0,007 m** | **9,1% (C12)** | **0,012 m** | **6,6% (C13)** | **sim** |

**A escolhida é 6/15 m:** 6 m nas janelas das curvas e 15 m fora delas, com 546 genes. A distância fica a até 0,10 m em 98,4% dos pontos do C0 e em 98,0% da `#0013`.

**O menor raio de cada trecho com 6/15 m** (a curvatura de 12 m; a última coluna é o raio de três pontos do arquivo, só relatado):

| trecho | C0 (12 m) | `#0013` (12 m) | C0, raio de três pontos (só relatado) |
|---|---|---|---|
| C01 | 32,9 → 33,9 m (+2,8%) | 35,8 → 37,0 m (+3,3%) | 37,7 → 31,1 m (−17,6%) |
| C02 | 45,5 → 42,0 m (−7,7%) | 49,1 → 50,6 m (+3,1%) | 46,8 → 40,3 m (−13,9%) |
| C03 | 73,5 → 73,2 m (−0,4%) | 74,4 → 74,3 m (−0,2%) | 76,6 → 72,6 m (−5,2%) |
| C04 | 55,0 → 53,4 m (−2,8%) | 53,3 → 56,6 m (+6,1%) | 58,5 → 51,5 m (−12,1%) |
| C05 | 110,0 → 111,3 m (+1,2%) | 129,6 → 132,1 m (+1,9%) | 104,9 → 108,9 m (+3,9%) |
| C06 | 73,3 → 74,3 m (+1,4%) | 59,5 → 61,1 m (+2,8%) | 71,9 → 67,2 m (−6,4%) |
| C07 | 29,3 → 29,6 m (+1,0%) | 30,2 → 30,5 m (+0,9%) | 28,9 → 29,5 m (+2,1%) |
| C08 | 35,0 → 35,3 m (+0,8%) | 34,1 → 35,3 m (+3,4%) | 34,2 → 35,2 m (+2,9%) |
| C09 | 180,7 → 180,3 m (−0,3%) | 146,3 → 150,7 m (+3,0%) | 176,7 → 172,8 m (−2,2%) |
| C10 | 22,8 → 23,1 m (+1,4%) | 23,3 → 23,6 m (+1,2%) | 22,0 → 23,0 m (+4,6%) |
| C11 | 72,2 → 74,4 m (+3,2%) | 75,5 → 76,4 m (+1,1%) | 71,0 → 74,4 m (+4,8%) |
| C12 | 35,2 → 38,4 m (+9,1%) | 38,3 → 39,8 m (+4,1%) | 38,1 → 37,8 m (−0,9%) |
| C13 | 110,2 → 118,7 m (+7,7%) | 101,1 → 107,8 m (+6,6%) | 113,0 → 121,6 m (+7,6%) |
| C14 | 139,9 → 140,2 m (+0,3%) | 142,0 → 143,3 m (+0,9%) | 141,4 → 132,4 m (−6,4%) |
| C14→linha | 235,2 → 243,8 m (+3,7%) | 248,0 → 238,3 m (−3,9%) | 226,5 → 242,5 m (+7,1%) |

**Os limites das restrições (item 4.4) saíram frouxos.**
- O menor raio das 150 voltas num trecho pega voltas com uma correção ou uma escorregada. Por exemplo, 5,5 m na C07 e 8,4 m na C08.
- Com isso, 90% desse raio quase não restringe nada. A regra é a registrada, e o relatório só aponta isso (está nos itens para o backlog).

## Parte B.2: os três medidores

O comando: `python -m ml.scripts.linha_do_projeto medidor`.

- **A conferência:** o M-real dá 85,316 s no C0 e 82,898 s na C3, os mesmos números do pedido 47.
- **Os tempos por microssetor** foram refeitos das gravações da cópia (as 39 voltas que contam), e cada volta soma o tempo dela em até 5 ms.

**O Spearman da diferença contra o C0, por microssetor,** nas linhas deixadas de fora (4 linhas × 60 microssetores):

| medidor | ρ juntos (p) | C1 | C2 | C3 | C4 |
|---|---|---:|---:|---:|---:|
| M-real (o envelope das voltas reais) | 0,458 (7 × 10⁻¹⁴) | 0,54 | 0,73 | 0,26 | 0,21 |
| M-cal (a escala por trecho) | 0,469 (2 × 10⁻¹⁴) | 0,56 | 0,70 | 0,31 | 0,21 |
| **M-v2 (o envelope da M1 v2), o escolhido** | **0,484 (2 × 10⁻¹⁵)** | 0,53 | 0,72 | 0,29 | 0,29 |

**A volta inteira, contra o C0 (s):**

| linha | jogo | M-real | M-v2 | M-cal (com a linha de fora) |
|---|---:|---:|---:|---:|
| C1 | +2,078 | +2,638 | +2,890 | +1,288 |
| C2 | +1,575 | +2,363 | +1,694 | +1,219 |
| C3 | +0,576 | −2,419 | −2,559 | −0,582 |
| C4 | +0,482 | −1,835 | −1,929 | −0,188 |

- **O esperado (item 10.3, o M-cal escolhido) não se confirmou.** O M-v2 ganhou por pouco no Spearman por microssetor, que é a regra registrada.
- **Na volta inteira, o M-cal acerta muito mais:** é o único que põe a C3 e a C4 perto do C0. Ele ainda erra o sinal das duas.
- **Os `β` por trecho, com as quatro linhas:** C01 0,41; C02 0,76; C03 1,36; C04 0,00; C05 0,56; C06 0,33; C07 0,00; C08 0,00; C09 0,14; C10 0,00; C11 0,25; C12 0,68; C13 1,13; C14 0,63; C14→linha 0,71. Com 0, o medidor deixa de usar o trecho: o simulador apontava a direção errada ali.

## Parte B.3: a L1 e a L2

### A L1, a montagem por trecho

O comando: `python -m ml.scripts.linha_do_projeto l1`.

**A escolha, pela tabela B.1 do 49** (a menor mediana do trecho entre C2, C3 e C4):

| trecho | linha | contra o C0 no jogo (s) |
|---|---|---:|
| C01 | C3 | +0,054 |
| C02 | C2 | +0,053 |
| C03 | C2 | +0,029 |
| C04 | C2 | −0,187 |
| C05 | C4 | +0,011 |
| C06 | C3 | −0,234 |
| C07 | C4 | −0,074 |
| C08 | C4 | −0,002 |
| C09 | C4 | −0,140 |
| C10 | C2 | +0,065 |
| C11 | C3 | −0,050 |
| C12 | C3 | −0,023 |
| C13 | C4 | −0,013 |
| C14 | C4 | +0,018 |
| C14→linha | C4 | +0,033 |
| **soma (o teto)** | | **−0,460** |

**As 8 emendas, nas retas:**

| entre | de → para | centro (m) | janela (m) | distância entre as linhas no centro (m) |
|---|---|---:|---:|---:|
| C01/C02 | C3 → C2 | 346,0 | 24 (a reta só tem 24 m) | 1,02 |
| C04/C05 | C2 → C4 | 1.440,0 | 40 | 0,96 |
| C05/C06 | C4 → C3 | 1.722,0 | 40 | 0,00 |
| C06/C07 | C3 → C4 | 2.192,0 | 40 | 0,02 |
| C09/C10 | C4 → C2 | 2.652,0 | 40 | **4,05** |
| C10/C11 | C2 → C3 | 2.778,1 | 40 | 0,84 |
| C12/C13 | C3 → C4 | 3.282,1 | 40 | 1,07 |
| C14→linha/C01 | C4 → C3 | 150,0 | 40 | 0,00 |

- **A emenda da C09 para a C10 é a mais forte:** as duas linhas ficam a 4 m uma da outra na reta curta antes da C10, então a L1 cruza a pista em 40 m. A figura mostra isso.
- **A codificação nova** reproduz a montagem a 0,011 m no percentil 95 (0,039 m no máximo).
- **A L1 ficou** dentro do corredor (sem precisar de reparo), da forma (serpenteio 0,068 contra 0,072 de limite; variação 0,00025 contra 0,00032) e das restrições em todos os trechos.

### A L2, a busca nova

O comando: `python -m ml.scripts.linha_do_projeto l2`.

- **O medidor** é o M-v2; **a semente** é 50.
- **As sementes:** a L1, a composição dos melhores trechos, a LSTM geradora (`model.json` `a4a10733…`, `weights.pt` `d7622dca…`) e as 87 voltas mais rápidas das 150. Todas foram trazidas para a região de confiança, e 10 são aleatórias dentro dela.
- **A busca:** 250 gerações (parou pelo limite, e ainda melhorava: 84,262 s na 240ª e 84,223 s na 250ª), com 25.101 avaliações em 150 s.
- **O custo foi de 85,196 s (a L1) para 84,223 s,** sem nenhuma penalização: corredor, forma, restrições e região, todas em zero.
- **O afastamento da L1** é de 0,63 m no máximo e de 0,38 m no percentil 95. Ela nunca chegou ao limite de 1,0 m.

### As duas linhas lado a lado

**O tempo previsto pelos três medidores** (s):

| linha | M-real (contra o C0) | M-v2, o escolhido (contra o C0) | M-cal (tempo / contra o C0) |
|---|---:|---:|---|
| C0 | 85,316 (0) | 86,554 (0) | 85,438 (0) |
| L1 | 84,228 (−1,089) | 85,196 (−1,358) | 85,425 (−0,013) |
| L2 | 83,101 (−2,215) | 84,223 (−2,332) | 85,028 (−0,410) |

**Por trecho:**
- a distância à linha da IA (mediana / máximo);
- o menor raio pela curvatura de 12 m e o menor raio do arquivo (o que a IA lê);
- a maior taxa de variação da curvatura.

Todas ficam dentro dos limites, e o corredor fica sem penalização nas duas.

| trecho | L1: distância (m) | L1: raio 12 m / arquivo (m) | L1: taxa (1/m²) | L2: distância (m) | L2: raio 12 m / arquivo (m) | L2: taxa (1/m²) |
|---|---|---|---:|---|---|---:|
| C01 | 0,29 / 1,36 | 39,5 / 38,5 | 1,7 × 10⁻³ | 0,24 / 0,96 | 40,4 / 40,2 | 1,9 × 10⁻³ |
| C02 | 0,76 / 1,96 | 42,7 / 42,5 | 4,5 × 10⁻³ | 0,66 / 1,84 | 44,9 / 44,9 | 4,0 × 10⁻³ |
| C03 | 0,91 / 1,96 | 88,2 / 88,6 | 1,1 × 10⁻³ | 0,89 / 1,83 | 85,4 / 78,0 | 1,5 × 10⁻³ |
| C04 | 1,07 / 2,36 | 57,1 / 56,5 | 0,7 × 10⁻³ | 0,90 / 2,37 | 60,5 / 60,1 | 0,7 × 10⁻³ |
| C05 | 0,44 / 2,12 | 76,0 / 76,7 | 1,4 × 10⁻³ | 0,49 / 2,15 | 75,1 / 74,9 | 1,0 × 10⁻³ |
| C06 | 0,90 / 3,70 | 87,5 / 85,7 | 0,5 × 10⁻³ | 0,96 / 3,92 | 65,4 / 56,8 | 2,4 × 10⁻³ |
| C07 | 0,50 / 2,04 | 31,1 / 30,7 | 1,3 × 10⁻³ | 0,45 / 2,26 | 31,9 / 31,2 | 2,3 × 10⁻³ |
| C08 | 0,46 / 4,10 | 39,2 / 39,3 | 1,7 × 10⁻³ | 0,59 / 4,38 | 39,3 / 39,1 | 2,3 × 10⁻³ |
| C09 | 3,34 / 4,90 | 113,0 / 112,5 | 0,6 × 10⁻³ | 3,24 / 4,99 | 109,9 / 106,1 | 0,6 × 10⁻³ |
| C10 | 2,41 / 5,69 | 25,1 / 25,0 | 2,7 × 10⁻³ | 2,38 / 5,30 | 22,8 / 22,4 | 3,2 × 10⁻³ |
| C11 | 0,92 / 2,21 | 92,2 / 90,1 | 1,2 × 10⁻³ | 0,80 / 2,29 | 78,4 / 71,0 | 1,7 × 10⁻³ |
| C12 | 0,63 / 3,33 | 39,4 / 39,0 | 1,2 × 10⁻³ | 0,60 / 2,96 | 35,0 / 31,9 | 2,6 × 10⁻³ |
| C13 | 1,94 / 6,08 | 69,8 / 69,5 | 0,7 × 10⁻³ | 2,01 / 5,87 | 75,9 / 71,6 | 1,8 × 10⁻³ |
| C14 | 6,24 / 8,63 | 142,2 / 136,1 | 0,5 × 10⁻³ | 5,90 / 8,28 | 131,2 / 116,3 | 1,1 × 10⁻³ |
| C14→linha | 2,25 / 10,07 | 134,2 / **125,2 em 3.898 m** | 1,2 × 10⁻³ | 2,07 / 9,65 | 147,9 / **137,8 em 3.898 m** | 1,1 × 10⁻³ |

**A subida dos boxes:** o raio do arquivo em 3.898 m é de 125 m na L1 e 138 m na L2. Na linha da IA é 226 m, e era 136 m no arquivo da C4 do 47.
- O ponto é o mesmo de 85 a 90 m da C1 e da C2, onde a IA freou.
- Quem vai nesse trecho é a C4, e a linha dela no mundo já carrega a ondulação da linha central. A spline de 15 m fora das curvas segue essa ondulação.
- **O esperado (item 10.2, mais de 200 m) não se confirmou.** No 47, a IA não freou na C4 ali, com 136 m. O teste no jogo vai mostrar se 125 m basta.

### A figura

`_linhas.png`: a pista inteira, a C06, a C09, a C10 e a subida dos boxes (s de 3.800 a 4.050 m), com a linha da IA em cinza e as bordas do corredor do pedido 44.
- **A L1 e a L2 quase se sobrepõem.**
- **As duas se afastam da linha da IA** na C09 (cerca de 3 m), na C10 (cerca de 2 a 5 m) e no fim da volta (C14: cerca de 6 m).

## Parte B.4: os arquivos do jogo (fora dos commits)

O comando: `python -m ml.scripts.linha_do_projeto arquivos`. O manifesto à parte é `data\pista_teste\linhas\linha_do_projeto.json`, e o `linhas.json` do 47 não mudou.

| linha | arquivo | bytes | sha256 | menor raio do arquivo |
|---|---|---:|---|---:|
| L1 | `data\pista_teste\linhas\L1\fast_lane.ai` | 1.282.396 | `c3d304129468e86e60cbc2abbe50cff3619bcb6e3edd722619c9ca47a19e8012` | 25,0 m |
| L2 | `data\pista_teste\linhas\L2\fast_lane.ai` | 1.282.396 | `4e9f125094c08a9572c89f85da8d0ab8aa0a6d23b8f27430db13bd00a180fd1e` | 22,4 m |

- **Os dois arquivos** têm 2.680 pontos e voltam iguais depois de relidos.
- **A velocidade, o acelerador e o freio** são os do original, ponto a ponto (item 8).
- **O original** continua com o sha256 `36b57fd8…3d8342`.

## Parte B.5: o `trocar_linha.ps1`

- **O script aceita `-Condicao L1` e `-Condicao L2`.** Para elas, o sha256 vem do `linha_do_projeto.json`, e ele recusa uma condição que o manifesto não tem.
- **As travas são as mesmas do 47:** o jogo fechado, só a cópia, nenhum link ou junção no caminho, os caches do CSP da cópia apagados, a linha no `registro.csv` e a original conferida antes e depois.
- **O `registro.py`** aceita L1 e L2 e ganhou os blocos do pedido 50:
  - `blocos`: as trocas depois do commit do ADR;
  - `atribuir_aos_blocos`: cada gravação no bloco da última troca, com o sha256 conferido;
  - `vizinhos_de_c0`.
- **A conferência entre as sessões, sem tempos:** `python -m ml.scripts.linha_do_projeto conferencia-sessao --rotulo <nome>`. Antes do teste, ela dá 0 blocos, deixa as 10 gravações do 47 de fora e confirma o original intacto.

## Parte C: mais carros da IA na pista (só leitura e relatório)

### C.1, o que cada carro da IA expõe

| fonte | carros | posição | velocidade | volante, acelerador, freio, marcha | cargas e escorregamento | confirmado por |
|---|---|---|---|---|---|---|
| **memória compartilhada** (`acpmf_physics`, `acpmf_graphics`, `acpmf_static`) | **só o carro do jogador** (o físico inteiro), mais o `numCars` | `carCoordinates[3]`, um ponto só | `speedKmh` e a velocidade, só do jogador | do jogador (`gas`, `brake`, `steerAngle`, `gear`) | do jogador (`wheelLoad[4]`, `wheelSlip[4]`) | as estruturas do projeto (`backend/core/assetto_adapter.py`), feitas a partir da documentação oficial do fórum. **Não abri o documento oficial** ([referência do C#](https://github.com/mdjarv/assettocorsasharedmemory)) |
| **telemetria por UDP** (porta 9996) | `RTCarInfo`: **um carro**, sem identificador; `RTLap`: o fim de volta de todos os carros | `carCoordinates[3]` | `speed_Kmh` | `gas`, `brake`, `steer`, `gear` | `load[4]`, `ndSlip[4]`, `slipAngle[4]`, `slipRatio[4]` | [o documento da telemetria remota](https://docs.google.com/document/d/1KfkZiIluXZ6mMhLWfDX1qAGbvhGRC3ZUzjVIt5FQpp4/pub). Que o `RTCarInfo` é do carro do jogador ou do focado: **não confirmado** |
| **API em Python do jogo** (`ac.getCarState(carId, acsys.CS.…)`) | **todos os carros, por `carId`** | `WorldPosition` | `SpeedKMH` | **não confirmado** para os outros carros | **não confirmado** | o exportador do projeto (`tools/assetto_opponents_exporter/`) já lê, de cada carro, `WorldPosition`, `SpeedKMH`, `Heading`, `NormalizedSplinePosition`, `LapCount`, `LapTime` e `RacePosition`. Os nomes das constantes ficam no `acsys.py` do jogo, e a documentação tem erros ([fórum](https://www.assettocorsamods.net/threads/ac-python-documentation-missing-identifier.3198)) |
| **API em Lua do CSP** (`ac.getCar(i)` → `ac.StateCar`) | **todos os carros, pelo índice** (0 é o jogador) | `position` | `velocity`, `speedKmh` | `gas`, `brake` (lidos no carro 0 pelo app do rádio); volante e marcha **não confirmados** | `wheels[i]` (carga e escorregamento): **não confirmado** | o SDK do CSP ([ac_car_cphys.lua](https://www.github.com/ac-custom-shaders-patch/acc-lua-sdk/blob/main/ac_car_cphys.lua)) declara `ac.StateCar`. Os campos são gerados no build (`__definitions('core')` em [ac_common.lua](https://github.com/ac-custom-shaders-patch/acc-lua-sdk)) e eu não os achei escritos. Um app de IA lê o combustível dos outros carros por `ac.getCar(id)` ([DumbAI](https://www.gtplanet.net/forum/threads/dumbai.434461/post-14567224)) |

**A leitura:**
- **o gravador de hoje (a memória compartilhada) só vê um carro;**
- **a API em Lua do CSP é o caminho mais provável para os outros,** porque o app do jogo do projeto já é um app Lua. A lista de campos válidos para um carro da IA precisa de um teste próprio no jogo: ler `ac.getCar(i)` de 2 a 3 carros e gravar quais campos mudam.

### C.2, o modo do jogo e a IA no tráfego

- **Vários carros da IA, sem largada:** uma sessão de prática ou de "track day" com IA, pelo Content Manager e pelo CSP.
  - O "AI Flood" do CSP mantém carros da IA passando perto do jogador ([Realistic Trackday](https://www.gtplanet.net/forum/downloads/assetto-corsa-realistic-trackday.7387)).
  - **Que o "Track Day" é um modo do próprio Content Manager e como ele escolhe o número de carros: não confirmado** (não achei documentação oficial).
- **A IA muda a linha no tráfego:**
  - com o "New AI Behaviour" do CSP, a IA abre para um lado para deixar passar e volta para a linha depois ([Realistic Trackday](https://www.gtplanet.net/forum/downloads/assetto-corsa-realistic-trackday.7387));
  - o CSP tem linhas alternativas para a IA (a pasta `cache\ai_alt_lanes`, que o pedido 47 apaga na cópia). A documentação delas eu não achei; há só relatos de usuários ([GTPlanet](https://www.gtplanet.net/forum/threads/assetto-corsa-pc-mods-general-discussion.307899/post-14504459)). **Não confirmado;**
  - **as voltas com tráfego não servem como linha ideal.**

### C.3, a regra para uma volta com tráfego ficar fora (proposta)

Uma volta de um carro da IA fica fora quando, em qualquer amostra:
- **outro carro está a menos de 2,0 s à frente,** pela distância ao longo da pista (`NormalizedSplinePosition` ou `s`) dividida pela velocidade do carro;
- **ou outro carro está lado a lado:** menos de 10 m ao longo da pista e menos de 4 m na lateral;
- **ou outro carro está a menos de 1,0 s atrás** (com o "New AI Behaviour", a IA abre para deixar passar).

Além disso, a volta passa pelas regras de volta válida do ADR 0029, item 5.

### C.4, um plano para um pedido próprio, depois do merge do 45

- **O que muda:** o app do jogo (Lua, CSP) grava, de cada carro da IA:
  - por `ac.getCar(i)`, a posição, a velocidade, o volante, o acelerador, o freio, a marcha, as cargas e o escorregamento das quatro rodas, e o `isAIControlled`;
  - um arquivo por carro, como o `player.jsonl`, só com esses canais;
  - antes, um teste curto confere quais campos variam nos carros da IA.

  O gravador do app do Windows não muda: ele continua lendo o jogador pela memória compartilhada.
- **Quantos carros:** de 6 a 10. Com mais, sobe a chance de tráfego, e as voltas fora pela regra C.3 aumentam.
- **Quantas voltas:** numa sessão de 45 minutos, cada carro dá cerca de 30 voltas (1:25 por volta). Com 8 carros, são cerca de 240 voltas por sessão, menos as com tráfego (estimativa: metade fica). Hoje, um bloco dá 9.
- **Quanto disco:** a gravação do jogador ocupa cerca de 21 MB por volta (1.558 MB nas 75 voltas das 7 sessões do 47, no `player.jsonl`).
  - Com os canais do item acima, a estimativa é de 1 a 2 MB por volta e por carro, ou de 0,3 a 0,5 GB por sessão com 8 carros.
  - Com o formato do jogador inteiro, seriam uns 5 GB por sessão.

  São estimativas, não medidas.

## Parte D: o roteiro do teste no jogo, com você

**Antes de começar:**
1. **O app instalado grava, como no 47.** Ninguém aperta "Atualizar coach" nem roda o `atualizar_coach` com as gravações da cópia.
2. **O preset "pedido 47 [teste]", sem mudança:**
   - o carro, a pista "Interlagos [teste]" (layout GP) e a prática sozinho, largando dos boxes;
   - o combustível em 30 L com o consumo em 0×, e o desgaste do pneu em 0×;
   - "Clear" a 25 °C, a pista "Optimum" sem evolução e 14:00 com o tempo parado;
   - a IA com nível 100% e agressividade 0%, e as mesmas ajudas.
3. **A cópia da pista continua instalada.** Não rode o `criar_copia.ps1`.

**Cada bloco** (PowerShell, com o jogo fechado; o Content Manager pode ficar aberto):

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47\tools\pista_teste\trocar_linha.ps1 -Condicao C0
```

(troque `C0` pela condição do bloco). Depois:
- abra o jogo pelo preset;
- nos boxes, aperte **Ctrl+C** para a IA dirigir, e deixe-a sair dos boxes;
- **deixe a IA completar 9 voltas:** a 1ª é a de saída, a 2ª é a primeira lançada, e as 7 seguintes contam. **Espere a IA cruzar a linha ao fim da 9ª volta antes de sair;**
- **feche o jogo** (até o `acs.exe` fechar) antes da próxima troca.

**A ordem, sorteada com a semente 50, em duas sessões de até 45 minutos** (um bloco leva cerca de 14 minutos):
- **Sessão 1: C0, L1, C0** (cerca de 42 min):
  ```powershell
  powershell -ExecutionPolicy Bypass -File C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47\tools\pista_teste\trocar_linha.ps1 -Condicao C0
  ```
  ```powershell
  powershell -ExecutionPolicy Bypass -File C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47\tools\pista_teste\trocar_linha.ps1 -Condicao L1
  ```
  ```powershell
  powershell -ExecutionPolicy Bypass -File C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47\tools\pista_teste\trocar_linha.ps1 -Condicao C0
  ```
- **Entre as sessões:** com o jogo fechado, avise "terminei a sessão 1". Eu faço só a conferência da troca, sem nenhum tempo (`conferencia-sessao --rotulo sessao1`), e digo se você pode seguir. Até lá, não rode nenhum script.
- **Sessão 2: L2, C0** (cerca de 28 min):
  ```powershell
  powershell -ExecutionPolicy Bypass -File C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47\tools\pista_teste\trocar_linha.ps1 -Condicao L2
  ```
  ```powershell
  powershell -ExecutionPolicy Bypass -File C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47\tools\pista_teste\trocar_linha.ps1 -Condicao C0
  ```

**Se a IA rodar ou sair da pista,** deixe seguir: a volta é descartada pelo resultado. Se ela não conseguir andar (presa, ou rodando a cada volta), feche o jogo, anote e passe para o próximo bloco. **Se um script parar** com "PARADO: …", não contorne: anote a mensagem e me avise.

**Ao terminar, avise: "rodei a linha do projeto".** Aí eu faço:
- a Parte E: a conferência, as voltas, o veredito da meta, a comparação por trecho, os medidores contra o jogo e a referência para o app;
- a Parte F: os ADRs e a arquitetura;
- o merge e o envio.

A cópia fica instalada até você rodar o `remover_copia.ps1`.

## O que se esperava e o que veio (até a Parte D)

| item do ADR | esperado | resultado |
|---|---|---|
| 10.1 | a conferência passa no 1º ou no 2º par | **não:** nenhum passou na regra registrada; com a emenda (a), passou o 3º (6/15 m) |
| 10.2 | o raio do arquivo da L1 no trecho C14→linha passa de 200 m | **não:** 125 m em 3.898 m (a C4 carrega a ondulação da linha central) |
| 10.3 | o M-cal é o escolhido | **não:** o M-v2 (ρ 0,484 contra 0,469) |
| 10.4 | o medidor prevê a L2 de 0,1 a 0,3 s mais rápida que a L1, perto de 1,0 m em poucos trechos | **não:** 0,97 s mais rápida no M-v2; no máximo 0,63 m da L1 |
| 10.5 a 10.7 | no jogo | depois do teste |

## Testes

- **`backend/tests/test_linha_do_projeto.py`: 19 testes, todos sintéticos.** Eles cobrem:
  - as janelas e os pontos de controle;
  - a curvatura contínua;
  - a ida e volta;
  - o raio mínimo e a taxa;
  - a emenda da volta;
  - a conferência (passa num círculo e reprova um raio fechado);
  - o reparo do corredor;
  - a calibração com uma linha de fora, os pesos e o Spearman;
  - a região de confiança;
  - a montagem e as emendas;
  - o veredito da meta;
  - os blocos do registro;
  - o arquivo pela curva;
  - o `trocar_linha.ps1` com L1 e L2 e as travas, numa pasta falsa "[teste]" apagada no fim.
- **A suíte do backend:** `1 failed, 1003 passed, 37 warnings in 699.54s` (a saída inteira em `_testes.txt`, rodada com o código de `99d76e2f`).
  - **A falha é a de ambiente, conhecida:** `test_leitura.py::test_volta_da_conferencia_nos_arquivos_reais`, com `KeyError: 'geometryId'`. Falta, na pasta separada, o `data/reference_models/vhe_interlagos.geometry.json`, que o git ignora. Não corrigi.
  - **Os testes do 47 continuam passando,** inclusive os do `trocar_linha.ps1`.
  - A conferência entre as sessões (`conferencia-sessao`) entrou depois da suíte e não tem teste próprio. As funções de blocos que ela usa têm.

## Os dados da pasta principal

**Nada foi escrito nos dados da principal.** A foto de `data\ml`, `data\cache` e `dataecordings` (932 arquivos: nome, tamanho e data) foi tirada antes das contas da Parte B e de novo depois da suíte, **sem nenhuma diferença.** As duas fotos estão em `data\linha_do_projetooto_antes.tsv` e `foto_depois.tsv`, fora do git.

## O envio

**Nada foi enviado.** O envio do pedido 49 ainda não foi feito (`origin/develop` em `bbff5c97`), e este pedido manda esperar por ele. **Primeiro, os comandos do 49** (do relatório dele):

```powershell
git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47 push -u origin etapa/modelo1-por-trecho
```

```powershell
git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47 push origin develop
```

**Depois, a branch deste pedido:**

```powershell
git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47 push -u origin etapa/linha-do-projeto
```

```powershell
git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47 ls-remote origin refs/heads/develop refs/heads/etapa/modelo1-por-trecho refs/heads/etapa/linha-do-projeto
```

O hash de cada ref no `ls-remote` tem de ser o mesmo do local (`git -C … rev-parse develop etapa/modelo1-por-trecho etapa/linha-do-projeto`). **Antes do envio, conferi o que vai** (as mudanças desde `e873d6a6`): nenhum arquivo acima de 50 MB, nenhum segredo, nada de `recordings/`, `data/recordings`, `data/ml` ou `data/linha_do_projeto`, e nenhum `.ai`.

## Itens para o backlog (para o Cowork)

1. **A linha central do projeto ondula na subida dos boxes** (curvatura de ±0,013 1/m entre 3.860 e 3.940 m). Toda linha guardada como lateral em relação a ela, e decodificada sem compensar, leva essa ondulação. Isso inclui a C3 e a C4 do 46, e a L1 e a L2 no trecho C14→linha. Suavizar a linha central ali, num pedido próprio, mudaria o `geometry_id`.
2. **O raio de três pontos do `fast_lane.ai` é muito sensível ao ruído dos pontos.** Qualquer escritor de linha precisa de uma curva suave no plano X/Z, e não da grade de 2 m em linha reta (o escritor do 47).
3. **As restrições pelo menor raio das 150 voltas ficaram frouxas** (5,5 m na C07, 8,4 m na C08), porque um valor extremo pega uma correção ou uma escorregada. Um percentil por trecho, ou as voltas de uma sessão só, restringiria de verdade.
4. **A conferência por "menor raio do trecho" também é um valor extremo.** Um percentil, ou o raio numa janela fixa, seria mais estável.
5. **O medidor escolhido (M-v2) prevê −2,3 s para a L2, e o calibrado, −0,4 s.** Os três medidores erram o sinal da C3 e da C4 no 47. O teste no jogo vai dizer qual errou menos fora das linhas do 47. Vale registrar antes, num pedido próprio, um medidor que use o tempo por trecho do jogo como dado de treino.
6. **A busca da L2 parou pelo limite de 250 gerações, ainda melhorando.** Com mais gerações, ela iria mais longe no medidor, e não necessariamente no jogo.
7. **A emenda da C09 para a C10 cruza 4 m de pista em 40 m.** Se a L1 perder na C10, essa emenda é a primeira suspeita.
8. **Mais carros da IA (Parte C):** um pedido próprio, depois do merge do 45, começando por um teste de quais campos do `ac.getCar(i)` valem para os carros da IA.
9. **A falha do `test_leitura` volta em toda pasta separada** (falta o `data/reference_models/vhe_interlagos.geometry.json`, que o git ignora).

## O que falta

- **O teste no jogo (Parte D),** com você.
- **Depois do seu aviso "rodei a linha do projeto":** a Parte E (o resultado, o veredito e a referência), a Parte F (os ADRs 0031, 0028, 0009, 0029 e 0030 e a arquitetura), o merge em `develop` e o envio.
- **O envio do 49 e o deste pedido:** os comandos acima.
- **A cópia da pista continua instalada,** e a pasta do 47 não foi apagada.
