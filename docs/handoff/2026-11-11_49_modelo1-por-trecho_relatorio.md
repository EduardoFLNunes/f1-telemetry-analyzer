# Relatório do pedido 49: o Modelo 1 por trecho

- **Pedido:** `docs/prompts/2026-11-11_49_modelo1-por-trecho.md`.
- **Situação:** **concluído**, salvo o envio ao GitHub. O controle de permissões da sessão recusou o `push`, e os comandos estão em "O envio ao GitHub".
- **Pasta:** `C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47`.
- **Branch:** `etapa/modelo1-por-trecho`, a partir de `develop` em `bbff5c97` (com os pedidos 47 e 48).
- **Commits** (na branch):
  - `63ad8c91` Pedido 49: o texto do pedido (o Modelo 1 por trecho);
  - `c9daed61` Pedido 49, Parte 0: data/modelo1_por_trecho/ no .gitignore;
  - `ec00f0de` Relatorio do pedido 49: parado antes da Parte A (o p-valor por permutacao da A.3 precisa de decisao);
  - `41a09840` Pedido 49, Parte A: ADR 0030 (o Modelo 1 por trecho), registrado antes de qualquer conta nas gravacoes;
  - `ac0f0a52` Pedido 49, Parte B: a conta por trecho (ADR 0030);
  - `2457540b` Pedido 49, Parte C: a referencia por trecho (a linha da IA em todos os trechos; candidatas a validar no jogo);
  - `686003de` Pedido 49, Parte D: os testes do Modelo 1 por trecho; o script le as sessoes da copia pelo etapas.py;
  - `96865958` Pedido 49, Parte D: a suite do backend (1 falha de ambiente, test_leitura) e as saidas refeitas com o codigo commitado;
  - `266ed75e` Pedido 49, Parte E: o resultado no ADR 0030, a linha no ADR 0029, o indice e a arquitetura;
  - `a2cc3da4` Pedido 49, Parte E: o commit das contas no resultado do ADR 0030;
  - `d8d2f45e` Relatorio do pedido 49: o Modelo 1 por trecho (candidatas na C06, C09 e C13; a referencia continua a linha da IA).
- **Merge:** `4175c251` Merge do pedido 49: o Modelo 1 por trecho (ADR 0030; candidatas C3 e C4 na C06 e na C09, C4 na C13; a referencia continua a linha da IA). É um `--no-ff` em `develop`, sem conflito.
- **O commit final deste relatório** (os hashes do merge e o envio) foi feito em `develop`, e a branch do pedido avançou até ele por avanço simples. O hash dele está no chat.
- **Arquivos de handoff** (`docs/handoff/2026-11-11_49_modelo1-por-trecho…`):
  - `_relatorio.md` (este);
  - `_conta.json` (Parte B: os trechos, as voltas, os tempos, as comparações, a execução, as hipóteses, as minhas voltas e o teto; sem a lateral ponto a ponto);
  - `_por_trecho.png` (B.1: cada trecho contra o C0, com o IC, na ordem da pista);
  - `_tabelas.md` (todas as tabelas da Parte B, como o script as escreve);
  - `_referencia.json` (Parte C: o resumo da referência, sem a lateral ponto a ponto);
  - `_testes.txt` (a suíte do backend).

## Em uma frase

**Com a mesma IA, a linha gerada ganha em três trechos e perde em quatro ou cinco.**
- **Ganhos:** C06 (−0,22 a −0,23 s) e C09 (−0,10 a −0,14 s), nas duas linhas geradas, e C13 (−0,013 s), só na C4. São as candidatas, "a validar no jogo".
- **Perdas:** C02, C03 e C10 nas duas, mais C07 (C3) e C01 e C12 (C4).
- **A referência de todos os trechos continua sendo a linha da IA (C0).**
- **A codificação perde 41% do tempo num ponto só.** No trecho da C14 até a linha (a subida dos boxes), a IA freia na C1 e na C2 e perde 0,84 s. O menor raio do arquivo ali é de 85 a 90 m, contra 134 a 226 m nas outras linhas.
- **As duas hipóteses registradas não se confirmaram:** as dicas e a rugosidade espalhada.

## Parte 0: a pasta

1. **A pasta do 47** estava como o pedido pede:
   - na branch `etapa/linha-gerada-no-jogo`;
   - sem mudança sem commit;
   - já juntada a `develop`.

   `develop` local e `origin/develop` estavam em `bbff5c97`, e nenhuma pasta tinha `develop` aberta.
2. **O texto do pedido:**
   - copiado e commitado (`63ad8c91`). O commit guarda LF;
   - **na pasta principal havia duas cópias do mesmo texto:** `2026-11-11_49_modelo1-por-trecho.md`, com CRLF (sha256 `c1c544de…4cb8`, igual ao do commit com CRLF), e `…-1.md`, com LF (sha256 `14115b89…5d85`, igual ao do commit);
   - **apaguei as duas, e só elas,** depois de conferir os dois sha256. A principal ficou limpa, na branch `etapa/replay-e-radio-que-ensina`.
3. **A branch:** `git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47 switch -c etapa/modelo1-por-trecho develop`, sem recusa.
4. **Os imports e os dados:**
   - o `.venv` da principal, rodando de dentro de `f1-telemetry-analyzer-47\backend`. `core` e `ml` vêm da pasta do 47. Nada foi instalado;
   - as junções do 47, só para leitura: `data\recordings`, `data\ml` e `data\cache`. Nada foi escrito por elas;
   - **as gravações da cópia** (10 sessões, na pasta do app instalado) só foram lidas. Os sha256 dos 28 arquivos das sessões usadas estão no `_conta.json` e na referência;
   - **a saída** vai para `data\modelo1_por_trecho\`, uma pasta de verdade, no `.gitignore` (`c9daed61`);
   - **a foto de `data\ml`** está em "Os dados da pasta principal".
5. **A cópia da pista** continua instalada. Nenhum script de `tools\pista_teste\` rodou, e nada da pasta do jogo foi aberto: as linhas vêm de `data\pista_teste\linhas\`, conferidas pelo sha256 do `linhas.json`. A C0 é a cópia do original.
6. **O processador:** o `acs.exe` estava fechado antes de cada conta e da suíte.

## A decisão da A.3 (12/11)

**O problema, achado antes de qualquer conta nas gravações:** com a diferença das medianas como estatística da permutação, nenhum trecho podia passar no Holm.
- Com separação completa, o menor p-valor exato é 0,0117 (7 contra 7) e 0,0121 (7 contra 4).
- O primeiro limite do Holm com 15 trechos é 0,0033.

A conta sintética está no `ec00f0de`.

**A sua decisão: "Diferença das médias".**
- **A permutação** é exata, com todas as divisões, e a estatística é a diferença das médias. O piso fica em 0,0006 (7 contra 7) e 0,0030 (7 contra 4).
- **A diferença das medianas** continua sendo o efeito, o sinal da regra e o IC por bootstrap.
- **Além disso, o ADR exige o mesmo sinal na mediana e na média,** registrado antes das contas.

## Parte A: o ADR 0030

**Commitado em `41a09840`, antes de qualquer conta nas gravações.** O número 0030 estava livre: o 0027 está na branch do 45, e nenhuma branch tem um 0030. O ADR fixa:
1. **Os 15 trechos,** com os limites na geometria do corredor (`geometry_id 0ed16f0dd2225990`, `corridor_id 707d07029036abd6`);
2. **as voltas:** as 39 que contam no 47 e as 136 `humano` do 44;
3. **a regra do ganho:** a mediana, o bootstrap com semente 49, a permutação exata da média e o Holm, contra o C0 e contra o C0 final;
4. **a candidata;**
5. **as medidas da execução;**
6. **as hipóteses,** com a rugosidade definida;
7. **as regras provisórias;**
8. **as contas só relatadas;**
9. **o arquivo da referência;**
10. **o que se espera,** com o porquê.

Uma linha no índice entrou no mesmo commit.

## Parte B: a conta por trecho

**O comando:** `python -m ml.scripts.modelo1_por_trecho --handoff …` (de `backend\`, 47 s). Todas as tabelas estão em `_tabelas.md`.

### A conferência

- **As 39 voltas refeitas** das gravações têm o mesmo tempo do 47 (diferença máxima de 0,0 ms).
- **A soma dos 15 trechos bate com o tempo da volta:** até 0,33 ms nas voltas da IA e até 1,85 ms nas 136 do Eduardo (o limite é 5 ms).
- **Os canais:** o freio vai até 0,99 na IA e até 1 nas suas voltas. Nenhum canal faltou.

### B.1, o tempo por trecho: cada condição contra o C0

Diferença das medianas contra o C0 (s), com a regra da A.3 para C1 a C4. **A regra só dá ganho ou perda com o mesmo sentido significativo contra o C0 e contra o C0 final.** A última coluna é a deriva (marcada com * onde passa no Holm).

| trecho | C0 (mediana, s) | C1 | C2 | C3 | C4 | C0 final |
|---|---:|---|---|---|---|---:|
| C01 | 6,392 | +0,173 perda | +0,300 perda | +0,054 empate | +0,213 perda | +0,029 |
| C02 | 2,406 | +0,274 perda | +0,053 perda | +0,079 perda | +0,182 perda | +0,016 |
| C03 | 5,284 | +0,134 perda | +0,029 empate | +0,181 perda | +0,175 perda | +0,014 * |
| C04 | 11,643 | +0,075 perda | −0,187 **ganho** | −0,013 empate | −0,069 empate | −0,024 |
| C05 | 4,098 | +0,032 empate | +0,056 empate | +0,114 empate | +0,011 empate | +0,051 |
| C06 | 9,662 | +0,056 perda | −0,176 **ganho** | −0,234 **ganho** | −0,223 **ganho** | +0,030 |
| C07 | 5,364 | +0,144 perda | −0,056 empate | +0,096 perda | −0,074 empate | −0,015 |
| C08 | 4,832 | +0,002 empate | +0,066 perda | +0,010 empate | −0,002 empate | −0,021 |
| C09 | 2,949 | −0,057 **ganho** | +0,108 perda | −0,105 **ganho** | −0,140 **ganho** | −0,030 |
| C10 | 4,225 | +0,021 empate | +0,065 empate | +0,301 perda | +0,283 perda | +0,056 |
| C11 | 5,819 | −0,041 empate | +0,115 empate | −0,050 empate | −0,037 empate | +0,028 |
| C12 | 5,202 | +0,366 perda | +0,273 perda | −0,023 empate | +0,150 perda | −0,006 |
| C13 | 2,848 | +0,032 perda | +0,025 perda | +0,006 empate | −0,013 **ganho** | +0,003 |
| C14 | 5,095 | −0,002 empate | +0,043 empate | +0,034 empate | +0,018 empate | +0,038 * |
| C14→linha | 9,618 | +0,836 perda | +0,856 perda | +0,102 empate | +0,033 empate | +0,079 * |
| **soma das medianas** | 1:25,438 | 1:27,483 | 1:27,007 | 1:25,990 | 1:25,945 | 1:25,685 |

- **O desvio de um trecho** vai de 0,002 a 0,12 s, quase sempre abaixo de 0,03 s. Por isso, a separação completa é comum, e muitos p-valores ficam no piso (0,0006 e 0,0030).
- **Em alguns trechos, o sentido contra o C0 e contra o C0 final é oposto.** Por exemplo, a C4 na C14 e na C14→linha é mais lenta que o C0 e mais rápida que o C0 final, com as duas diferenças significativas. É a deriva do fim da volta, e a regra dá empate.

**A figura** (`_por_trecho.png`): cada trecho contra o C0, com o IC de 95%, na ordem da pista. O marcador cheio é significativo no Holm contra o C0.

### As candidatas

| trecho | linha | contra o C0 (IC 95%) | contra o C0 final (IC 95%) | p (C0 / C0 final) |
|---|---|---|---|---|
| C06 | **C3** | −0,234 s (−0,246 a −0,208) | −0,264 s (−0,276 a −0,243) | 0,0006 / 0,0030 |
| C06 | C4 | −0,223 s (−0,236 a −0,196) | −0,253 s (−0,265 a −0,232) | 0,0006 / 0,0030 |
| C09 | C3 | −0,105 s (−0,112 a −0,059) | −0,075 s (−0,089 a −0,064) | 0,0006 / 0,0030 |
| C09 | **C4** | −0,140 s (−0,165 a −0,097) | −0,111 s (−0,138 a −0,093) | 0,0006 / 0,0030 |
| C13 | **C4** | −0,013 s (−0,019 a −0,008) | −0,016 s (−0,021 a −0,011) | 0,0006 / 0,0030 |

Em negrito, a que vai para a referência: a de maior ganho contra o C0 no trecho. A outra fica como "outras candidatas".

### B.2, a deriva por trecho

**Os 0,23 s do C0 final ficaram no fim da volta.** Três trechos passam no Holm: C03 (+0,014 s), C14 (+0,038 s) e C14→linha (+0,079 s). Eles somam 0,131 s dos 0,248 s da soma das medianas. Nos outros 12, a diferença fica entre −0,030 e +0,056 s, sem significância.

### B.3, a minha linha

**A C2 (a IA na sua linha codificada)** ganha da linha da IA na C04 (−0,187 s) e na C06 (−0,176 s), e perde em 7 trechos. A maior perda é a C14→linha (+0,856 s), a mesma frenagem da C1.

**A C2 contra as linhas geradas** (só relatado; diferença das medianas, s; "—" quando não passa no Holm):

| trecho | C2 − C3 | C2 − C4 |
|---|---:|---:|
| C01 | +0,246 | +0,087 |
| C02 | −0,026 | −0,129 |
| C03 | −0,152 | −0,147 |
| C04 | −0,174 | −0,118 |
| C05 | −0,059 | +0,045 |
| C06 | +0,058 | +0,047 |
| C07 | −0,152 | — (+0,018) |
| C08 | +0,056 | +0,068 |
| C09 | +0,213 | +0,249 |
| C10 | −0,236 | −0,217 |
| C11 | +0,165 | +0,151 |
| C12 | +0,296 | +0,123 |
| C13 | +0,018 | +0,038 |
| C14 | +0,010 | +0,025 |
| C14→linha | +0,753 | +0,823 |

**A sua linha dirigida pela IA ganha das duas geradas** na C02, na C03, na C04 e na C10, e da C3 também na C05 e na C07.

**As suas voltas reais por trecho** (as 136 `humano` do pedido 44; as 9 de 24/10 são parte delas):

| trecho | mediana (136) | melhor (136) | mediana − C0 | melhor − C0 | mediana (24/10) | melhor (24/10) | mediana − C0 (24/10) |
|---|---:|---:|---:|---:|---:|---:|---:|
| C01 | 7,228 | 6,640 | +0,836 | +0,248 | 6,819 | 6,647 | +0,426 |
| C02 | 2,532 | 2,284 | +0,126 | −0,123 | 2,488 | 2,301 | +0,082 |
| C03 | 5,474 | 4,997 | +0,190 | −0,288 | 5,298 | 5,211 | +0,013 |
| C04 | 12,194 | 11,390 | +0,552 | −0,252 | 12,135 | 11,892 | +0,492 |
| C05 | 4,253 | 3,978 | +0,155 | −0,120 | 4,195 | 4,056 | +0,097 |
| C06 | 9,639 | 9,137 | −0,023 | −0,526 | 9,277 | 9,137 | −0,385 |
| C07 | 5,850 | 5,339 | +0,486 | −0,025 | 5,542 | 5,339 | +0,178 |
| C08 | 5,251 | 4,830 | +0,419 | −0,002 | 5,092 | 4,927 | +0,260 |
| C09 | 3,088 | 2,773 | +0,139 | −0,177 | 2,955 | 2,852 | +0,005 |
| C10 | 4,624 | 4,312 | +0,399 | +0,087 | 4,593 | 4,395 | +0,368 |
| C11 | 6,165 | 5,686 | +0,346 | −0,133 | 5,981 | 5,910 | +0,162 |
| C12 | 5,836 | 5,355 | +0,634 | +0,153 | 5,606 | 5,355 | +0,405 |
| C13 | 2,972 | 2,787 | +0,124 | −0,061 | 2,897 | 2,839 | +0,049 |
| C14 | 5,224 | 4,960 | +0,129 | −0,134 | 5,241 | 5,156 | +0,146 |
| C14→linha | 9,857 | 9,475 | +0,239 | −0,144 | 9,728 | 9,682 | +0,110 |

- **A sua mediana fica atrás da IA em 14 dos 15 trechos.** A exceção é a C06: −0,023 s nas 136 e −0,385 s nas de 24/10.
- **A sua melhor de cada trecho fica à frente da IA em 12 trechos.** Ela fica atrás na C01, na C10 e na C12.
- **As suas voltas são da pista original,** e as da IA, da cópia, com a mesma geometria.

**A sua diferença em cada trecho: a linha.**
- Na entrada, no ápice e na saída de cada trecho, comparei a distância da sua mediana à linha da IA com o limite "de linha" (o percentil 90 da sua repetibilidade, A.7).
- **Ela fica dentro do limite em 43 dos 45 pontos.** Passa só na saída da C08 (6,31 m contra 3,71 m) e na saída da C13 (4,96 m contra 3,58 m).
- **O limite é largo,** de 1,44 a 6,11 m, porque as 136 voltas juntam semanas diferentes.
- **A fração do trecho acima do limite:** 0,45 na C14, 0,27 na C09, 0,24 na C08, 0,22 na C14→linha, 0,21 na C10, 0,14 na C13, 0,03 na C12 e zero nos outros 8.

| trecho | entrada: distância / limite (m) | ápice | saída | fração acima |
|---|---|---|---|---:|
| C01 | 0,26 / 1,54 | 0,75 / 2,74 | 1,22 / 4,72 | 0,00 |
| C02 | 0,62 / 3,60 | 0,40 / 2,43 | 0,35 / 3,44 | 0,00 |
| C03 | 0,30 / 3,48 | 1,84 / 2,45 | 0,85 / 3,95 | 0,00 |
| C04 | 0,17 / 1,80 | 1,03 / 3,49 | 1,92 / 3,90 | 0,00 |
| C05 | 0,39 / 3,09 | 0,45 / 3,35 | 2,71 / 3,21 | 0,00 |
| C06 | 0,96 / 2,06 | 2,47 / 4,20 | 0,27 / 3,33 | 0,00 |
| C07 | 0,84 / 3,57 | 0,14 / 3,64 | 3,67 / 5,12 | 0,00 |
| C08 | 2,01 / 4,10 | 0,49 / 3,10 | **6,31 / 3,71** | 0,24 |
| C09 | 0,19 / 3,38 | 1,30 / 3,11 | 2,61 / 2,85 | 0,27 |
| C10 | 1,29 / 2,21 | 1,98 / 4,17 | 2,09 / 3,48 | 0,21 |
| C11 | 1,51 / 3,20 | 2,19 / 3,04 | 1,96 / 2,91 | 0,00 |
| C12 | 0,55 / 2,31 | 0,47 / 2,64 | 2,01 / 3,22 | 0,03 |
| C13 | 0,83 / 2,53 | 2,57 / 3,31 | **4,96 / 3,58** | 0,14 |
| C14 | 1,95 / 4,54 | 1,66 / 5,08 | 1,77 / 5,48 | 0,45 |
| C14→linha | 1,77 / 5,48 | 4,83 / 6,11 | 0,16 / 1,44 | 0,22 |

**A sua diferença em cada trecho: a execução** (medianas; você / a IA no C0; a marcha sem o neutro da troca):

| trecho | início da frenagem (m) | freio máx. | mínima (km/h) | onde (m) | marcha mín. | retomada (m) |
|---|---|---|---|---|---|---|
| C01 | 84 / 136 | 0,75 / 0,99 | 100,0 / 108,0 | 308 / 322 | 3 / 2 | 327 / 332 |
| C02 | 370 / 360 | 0,26 / 0,99 | 105,4 / 114,5 | 334 / 334 | 3 / 2 | 412 / sem retomada no trecho |
| C03 | sem frenagem / sem frenagem | — | 129,4 / 131,5 | 422 / 422 | 3 / 2 | 430 / 558 |
| C04 | 1.178 / 1.210 | 0,73 / 0,99 | 124,0 / 126,8 | 1.360 / 1.374 | 3 / 3 | 1.394 / 1.386 |
| C05 | sem frenagem / sem frenagem | — | 134,7 / 139,0 | 1.402 / 1.402 | 3 / 3 | 1.411 / 1.514 |
| C06 | 1.836 / 1.894 | 0,28 / 0,80 | 161,0 / 150,1 | 2.108 / 2.108 | 4 / 4 | 2.116 / 2.114 |
| C07 | 2.177 / 2.202 | 0,49 / 0,99 | 84,3 / 87,0 | 2.300 / 2.300 | 2 / 1 | 2.328 / 2.330 |
| C08 | 2.377 / 2.362 | 0,15 / 0,99 | 94,7 / 101,9 | 2.334 / 2.416 | 2 / 2 | 2.484 / 2.482 |
| C09 | 2.604 / sem frenagem | 0,41 / — | 124,5 / 124,0 | 2.498 / 2.498 | 2 / 2 | sem retomada no trecho / 2.538 |
| C10 | 2.642 / 2.652 | 0,27 / 0,88 | 78,3 / 78,3 | 2.726 / 2.734 | 2 / 1 | 2.754 / 2.744 |
| C11 | sem frenagem / sem frenagem | — | 90,7 / 102,6 | 2.758 / 2.758 | 2 / 1 | 2.794 / 2.930 |
| C12 | 3.079 / 3.124 | 0,55 / 0,99 | 105,0 / 102,5 | 3.232 / 3.222 | 3 / 2 | 3.256 / 3.252 |
| C13 | sem frenagem / sem frenagem | — | 114,7 / 118,3 | 3.262 / 3.262 | 3 / 2 | 3.262 / 3.308 |
| C14 | sem frenagem / sem frenagem | — | 168,7 / 171,4 | 3.380 / 3.380 | 3 / 3 | 3.380 / 3.650 |
| C14→linha | 4.310 / sem frenagem | 0,21 / — | 216,2 / 217,7 | 3.666 / 3.666 | 5 / 5 | 3.666 / 4.034 |

- **Você começa a frear antes da IA** na C01 (52 m), na C04 (32 m), na C06 (58 m), na C07 (25 m), na C10 (10 m) e na C12 (45 m).
- **O seu freio máximo** (mediana de 0,15 a 0,75) fica abaixo do da IA (0,80 a 0,99).
- **A sua mínima é mais baixa em 11 trechos.** Ela é mais alta na C06 (161 contra 150 km/h), na C09 e na C12, e igual na C10.
- **Você usa uma marcha acima da IA em 8 trechos:** C01, C02, C03, C07, C10, C11, C12 e C13.
- **A leitura:** a sua diferença está mais na execução (frenagem antes e mais leve, mínima mais baixa) do que na linha, que fica quase toda dentro da sua própria repetibilidade.

### B.4, a execução da IA por condição (destaques)

**A C06**, onde as linhas geradas ganham (medianas):

| condição | início da frenagem (m) | freio máx. | mínima (km/h) | onde (m) | trocas (sem neutro) | retomada (m) |
|---|---:|---:|---:|---:|---|---|
| C0 | 1.894 | 0,80 | 150,1 | 2.108 | 4→5 em 1.706, 5→4 em 2.010 | 2.114 (7 voltas) |
| C1 | 1.900 | 0,99 | 149,6 | 2.138 | 4→5 em 1.706, 5→4 em 1.936, 4→3 em 2.076 | 2.130 (1 volta) |
| C2 | 1.908 | 0,99 | 166,1 | 2.016 | 4→5 em 1.710, 5→4 em 1.944 | sem retomada no trecho |
| C3 | 1.910 | 0,99 | 173,4 | 1.992 | 4→5 em 1.722, 5→4 em 1.992 | sem retomada no trecho |
| C4 | 1.908 | 0,99 | 169,2 | 2.138 | 4→5 em 1.702, 5→4 em 1.994 | sem retomada no trecho |
| C0 final | 1.899 | 0,99 | 153,9 | 2.106 | 4→5 em 1.726, 5→4 em 2.010 | 2.112 (4 voltas) |

- **Nas linhas geradas, a IA passa a C06 com 19 a 23 km/h a mais de mínima** (169 a 173 contra 150 km/h). Ela reduz para a 4ª uns 16 a 18 m antes (5→4 em 1.992 e 1.994, contra 2.010).
- **Na C3, a mínima vem 116 m antes** (em 1.992 m). O ganho é a velocidade de passagem, e não a saída: a retomada plena (acelerador ≥ 0,90) não chega até o fim do trecho em nenhuma das três.
- **A C1 faz uma redução a mais** (4→3 em 2.076 m), e a retomada só chega numa volta.

**A C10**, onde o medidor do 46 previa −1,0 s e as linhas geradas perdem 0,28 a 0,30 s:

| condição | início da frenagem (m) | freio máx. | até o ápice (m) | mínima (km/h) | onde (m) | trocas (sem neutro) | retomada (m) |
|---|---:|---:|---:|---:|---:|---|---:|
| C0 | 2.652 | 0,88 | 76 | 78,3 | 2.734 | 3→2 em 2.672, 2→1 em 2.694 | 2.744 |
| C1 | 2.684 | 0,77 | 44 | 81,7 | 2.720 | 3→2 em 2.660, 2→1 em 2.688 | 2.750 |
| C2 | 2.632 | 0,99 | 96 | 83,6 | 2.730 | 3→2 em 2.666, 2→1 em 2.692 | 2.750 |
| C3 | 2.626 | 0,99 | 102 | 77,1 | 2.730 | 3→2 em 2.660, 2→1 em 2.686 | 2.742 |
| C4 | 2.678 | 0,87 | 50 | 75,7 | 2.728 | 3→2 em 2.660, 2→1 em 2.684 | 2.740 |
| C0 final | 2.652 | 0,89 | 76 | 75,2 | 2.733 | 3→2 em 2.672, 2→1 em 2.689 | 2.745 |

- **As duas linhas geradas perdem na C10 por caminhos opostos.** A C3 freia 26 m antes e com tudo (0,99). A C4 freia 26 m depois. Nas duas, a mínima fica 1 a 3 km/h abaixo da do C0, e a redução para a 2ª vem 12 m antes.
- **A C10 tem um desvio maior no C0 e no C0 final** (0,035 e 0,075 s), porque a IA varia a freada ali.

### B.5, as hipóteses dos 2,1 s (só relatadas)

**As dicas da linha: o esperado não se confirmou.**

| trecho | frenagem da IA C0 / C1 (m) | C1 − C0 (m) | dica do arquivo: freio em (m) | mínima da IA C0 / C1 (km/h) | dica: mínima (km/h) em (m) |
|---|---|---:|---:|---|---|
| C01 | 136 / 150 | +14 | 89,7 | 108,0 / 103,8 | 92,5 em 310,7 |
| C02 | 360 / 362 | +2 | 361,4 | 114,5 / 102,5 | 107,1 em 335,2 |
| C04 | 1.210 / 1.214 | +4 | 1.183,0 | 126,8 / 123,5 | 112,2 em 1.360,9 |
| C06 | 1.894 / 1.900 | +6 | 1.852,8 | 150,1 / 149,6 | 131,3 em 2.088,6 |
| C07 | 2.202 / 2.208 | +6 | 2.178,8 | 87,0 / 82,9 | 77,4 em 2.293,5 |
| C08 | 2.362 / 2.358 | −4 | 2.349,6 | 101,9 / 101,1 | 89,0 em 2.414,3 |
| C10 | 2.652 / 2.684 | +32 | sem dica no trecho | 78,3 / 81,7 | 69,5 em 2.702,8 |
| C12 | 3.124 / 3.126 | +2 | 3.094,7 | 102,5 / 94,3 | 92,2 em 3.232,6 |
| C14→linha | sem frenagem / 3.860 | — | sem dica no trecho | 217,7 / 204,4 | 198,9 em 3.666,2 |

- **Nos 8 trechos em que a IA freia nas duas,** o início fica a menos de 4 m em só 2 (C02 e C12). Nos outros, a frenagem da C1 vem de −4 a +32 m do C0.
- **A IA também não freia no ponto da dica no C0:** em 6 dos 7 trechos com dica de freio, ela começa de 12 a 46 m depois (só na C02 ela freia no ponto da dica).
- **Na C14→linha, o arquivo não tem freio, e a IA freia na C1.**
- **As dicas da C0 e da C1 são iguais em todos os trechos,** porque foram copiadas pela estação.

**A curvatura, como registrada: o esperado também não se confirmou.**

| linha | perda nos microssetores (s) | ρ com a diferença de rugosidade (p) | ρ com o afastamento lateral (p) | rugosidade média (1/m) | afastamento médio (m) |
|---|---:|---|---|---:|---:|
| C1 | +2,026 | +0,03 (0,81) | +0,36 (0,004) | 1,37 × 10⁻³ | 0,40 |
| C2 | +1,527 | −0,05 (0,71) | +0,29 (0,023) | 1,46 × 10⁻³ | 2,19 |
| C3 | +0,541 | +0,18 (0,17) | +0,09 (0,49) | 1,35 × 10⁻³ | 1,82 |
| C4 | +0,529 | −0,04 (0,75) | +0,17 (0,18) | 1,32 × 10⁻³ | 1,95 |
| C0 | — | — | — | 0,31 × 10⁻³ | — |

- **A perda da C1 por microssetor não acompanha a rugosidade** (ρ = +0,03). Ela acompanha o afastamento lateral (ρ = +0,36, p = 0,004).
- **As quatro linhas codificadas têm a curvatura de 4 a 5 vezes mais rugosa que a do C0.** A rugosidade é comum às quatro e não separa a C1 (−2,0 s) da C3 (−0,5 s).

**O que a conta mostra (leitura acrescentada depois de ver os dados, só relatada): um raio fechado num ponto só.**

| trecho | C0 | C1 | C2 | C3 | C4 |
|---|---|---|---|---|---|
| C14→linha (menor raio, m, e onde) | 226 em 3.666 | **85 em 3.898** | **90 em 3.898** | 134 em 3.898 | 136 em 3.898 |

- **A IA freia na C1 e na C2 a partir de 3.860 m e 3.866 m,** com a mínima em 3.904 m e 3.908 m (204 e 208 km/h), logo depois do ponto de 85 a 90 m de raio.
- **Na C3 e na C4,** com 134 a 136 m, e no C0, com 226 m, ela não freia e passa a 218 a 220 km/h.
- **Esse trecho custa +0,84 s à C1 e +0,86 s à C2.** São 41% da perda da C1.
- **A leitura:** a perda grande da codificação parece vir de pontos com o raio fechado, e não de uma rugosidade espalhada. A medida registrada (a média numa janela de 20 m por microssetor) não pega um ponto só. A tabela inteira do menor raio por trecho está em `_tabelas.md`.

### B.6, o teto da referência por trecho (só relatado)

**A linha mais rápida de cada trecho, somada, dá 1:24,712, contra 1:25,438 do C0 (−0,726 s).** Ela junta:
- a C2 na C04;
- a C3 na C06, na C11 e na C12;
- a C4 na C07, na C08, na C09 e na C13;
- a C1 na C14;
- o C0 nos outros 6 trechos.

**É um teto, e não uma previsão:** o ganho de um trecho muda a entrada do seguinte, e escolher depois de ver favorece o acaso. Só com as candidatas pela regra (C3 na C06 e C4 na C09 e na C13), a soma das diferenças é de −0,387 s.

### O que se esperava e o que veio

| item do ADR | esperado | resultado |
|---|---|---|
| 10.1 | ganho na C06 e talvez na C08; perda no C01/C02, C03, C07 e C10 | **em parte:** ganho na C06 e na C09 (não na C08); perda no C02, C03 e C10 nas duas, no C01 só na C4, no C07 só na C3 |
| 10.2 | 0,1 s ou mais passa no Holm contra o C0 | **sim** |
| 10.3 | quase nada passa contra o C0 final; no máximo a C06 | **não:** 5 candidatas, porque o desvio por trecho é pequeno |
| 10.4 | a deriva se espalha, sem trecho no Holm | **não:** 3 trechos passam, no fim da volta |
| 10.5 | a C1 perde em quase todos, mais nos longos e rápidos | **em parte:** 9 perdas; a maior é a C14→linha |
| 10.6 | a curvatura explica mais que as dicas | **nenhuma das duas, como registradas;** um raio fechado num ponto explica a maior perda (depois de ver os dados) |
| 10.7 | você perde em quase todos, mais pela execução; a linha passa do limite no ápice das curvas lentas | **em parte:** perde em 14 de 15 e freia antes; a linha passa do limite só em duas saídas (C08 e C13) |
| 10.8 | teto de −0,2 a −0,5 s | **não:** −0,726 s |

### Duas leituras acrescentadas depois de ver os dados

**Nenhuma regra mudou.** As duas estão marcadas no código, no JSON e no ADR como "depois de ver os dados", e só relatadas.

1. **A marcha sem o neutro da troca.**
   - O gravador guarda a marcha como `gear − 1` do jogo (`core/assetto_adapter.py`): −1 é a ré, 0 o neutro e 1 a primeira.
   - O carro passa pelo neutro em cada troca: de 2 a 6 m na grade, e no máximo 16 m nas voltas do pedido 44. Conferi a duração dos trechos com 0 nas 150 voltas do 44.
   - **Por isso, a "marcha mínima" do item 5 sai 0 em todo trecho com troca.** A medida registrada continua no JSON.
   - A leitura sem o neutro ignora o 0 e a ré, e junta `5 → 0 → 4` em `5 → 4`.
2. **O menor raio do arquivo por trecho,** para a frenagem da IA na C14→linha.

## Parte C: a referência por trecho

**O comando:** `python -m ml.scripts.referencia_por_trecho --handoff …`. Ele lê o `conta.json` e escreve `data/modelo1_por_trecho/referencia_por_trecho.json` (176 KB, fora do git). O resumo, sem a lateral ponto a ponto, está em `_referencia.json`.

Por trecho, o arquivo traz:
- **os limites** e os pontos de entrada, ápice e saída;
- **a linha de referência:** a C0 em todos os 15 trechos, com a lateral em cada ponto da grade de 2 m (no arquivo completo);
- **a execução da IA nela:** as medidas do item 5, com a mediana, o desvio e quantas das 7 voltas do C0 têm cada uma, mais o tempo do trecho;
- **a candidata,** em 3 trechos:
  - C06: a C3, com a C4 como outra candidata;
  - C09: a C4, com a C3 como outra candidata;
  - C13: a C4.

  Cada uma leva a lateral, o ganho contra o C0 e o C0 final, com o IC e o p-valor, e a marca "a validar no jogo";
- **as propostas provisórias,** com a marca "provisório, sem confirmação":
  - o ponto de frenagem traduzido;
  - a rampa;
  - o limite "de linha" na entrada, no ápice e na saída.

  **A rampa do seu freio** vai de 7,5 m (C10) a 35,7 m (C01) nos 7 trechos com pelo menos 5 voltas com frenagem. **O ponto traduzido** sai nos 6 trechos em que a IA também freia: C01 100,3 m, C04 1.174,7 m, C06 1.877,2 m, C07 2.183,3 m, C10 2.644,6 m e C12 3.100,5 m. Nos outros 9, ele fica "sem dados".

O arquivo também traz:
- o `geometry_id`, o `corridor_id` e o commit (`686003de`);
- o sha256 dos 28 arquivos das gravações da cópia, das voltas do 44 (`voltas.parquet`, `voltas_tabela.parquet`, `fontes.json`), do `_resultado.json` do 47, das 5 linhas e do `conta.json`.

**O formato é conferido pelo próprio script,** antes de gravar (`conferir_formato_da_referencia`). **O coach não lê esse arquivo.**

## Parte D: os testes

**`backend/tests/test_modelo1_por_trecho.py`: 18 testes, todos com dados sintéticos, todos passando:**
- **os trechos:**
  - cobrem a volta, e cada ponto da grade fica em um só trecho;
  - um buraco, uma sobreposição e uma curva que cruza a linha são recusados;
  - a soma dos tempos bate com o tempo da volta, e 6 ms de diferença param a conta;
- **a regra da A.3:**
  - a permutação exata contra uma conta ingênua: 2/3.432 com separação completa (7 contra 7), 7 contra 4 e dados aleatórios;
  - o bootstrap é fixo pela semente e cobre a diferença;
  - o Holm num caso conhecido, incluindo o piso da mediana (0,0117) que não passa e o da média (2/3.432) que passa;
  - o ganho, a perda e o empate pelo C0 e pelo C0 final;
  - sinais diferentes na mediana e na média não contam;
- **as medidas da A.5 num traço sintético:**
  - a frenagem, o freio máximo e a distância até o ápice;
  - a mínima e onde ela acontece;
  - as trocas e a retomada;
  - sem frenagem, sem retomada e com um canal que falta;
  - a frenagem que vem do trecho anterior e a que vem depois do ápice não contam;
  - o trecho da chegada sem ápice;
  - o resumo, e a leitura sem o neutro da troca;
- **a rampa e o limite da A.7:**
  - a rampa linear de 16 m;
  - a rampa com o máximo em 0,5;
  - um degrau;
  - sem frenagem;
  - o percentil 90 e o "acima do limite";
- **a rugosidade:**
  - zero num círculo de raio constante (pela geometria e pelos campos do arquivo);
  - maior numa linha serrilhada e num raio alternado;
  - a janela de 20 m, conferida num pico;
- **o JSON da Parte C:** o formato certo passa, e oito formas de estragar são recusadas.

**A suíte do backend:** `1 failed, 983 passed, 37 warnings in 514.01s` (a saída inteira em `_testes.txt`, rodada com o código de `686003de`).
- **A falha é a conhecida, de ambiente:** `test_leitura.py::test_volta_da_conferencia_nos_arquivos_reais`, com `KeyError: 'geometryId'`. Falta, na pasta separada, o `data/reference_models/vhe_interlagos.geometry.json`, que o git ignora. Ele existe na principal. Não corrigi.
- **Na primeira rodada houve uma segunda falha, causada por este pedido:** `test_pista_teste.py::test_so_o_resultado_do_pedido_47_pede_as_sessoes_da_copia`.
  - O teste do 47 garante que só `ml/pista_teste/etapas.py` pede as sessões da cópia, e o script novo também pedia.
  - **Consertei sem mudar o teste:** o `etapas.py` ganhou `sessoes_da_copia()`, e o script chama por ela (`686003de`).
  - As saídas B e C foram refeitas com esse código e saíram iguais, salvo o commit.
- **São 18 testes a mais que no pedido 48** (966 lá, 984 aqui), todos de `test_modelo1_por_trecho.py`.

## Parte E: a documentação

- **ADR 0030:**
  - o resultado entrou numa seção no fim, sem mudar nada acima dela (conferido no diff: a única linha tirada é o marcador "Escrito depois das contas");
  - a linha do índice ganhou o resultado.
- **ADR 0029:** uma linha de atualização no cabeçalho, apontando para o 0030.
- **`docs/arquitetura_ml.md`:** a seção nova "O Modelo 1 por trecho (pedido 49; ADR 0030)", depois da do teste no jogo.
- **ADR 0009:** não muda.
- **`docs/backlog.md`:** não editado. Os itens estão no fim deste relatório.

## Os dados da pasta principal

**Nada foi escrito nos dados da principal.**
- A foto de `data\ml` (616 arquivos), `data\cache` (3) e `data\recordings` (313) foi tirada antes de tudo e de novo depois da suíte. **Não há nenhuma diferença** de nome, tamanho ou data nos 932 arquivos.
- As fotos estão em `data\modelo1_por_trecho\foto_antes.tsv` e `foto_depois.tsv`, fora do git.

## O merge

**Antes do merge:**
- `develop` não tinha andado: local e remoto em `bbff5c97`, o mesmo ponto de partida da branch;
- nenhuma pasta estava com `develop` aberta. A principal está em `etapa/replay-e-radio-que-ensina`, e a do 48 em `etapa/diagnostico-m1`.

**O que foi feito, na pasta do 47:**
- `git switch develop` e `git merge --no-ff etapa/modelo1-por-trecho`: o merge `4175c251`, sem conflito, com 17 arquivos;
- o commit final deste relatório, em `develop`;
- a branch do pedido avançou até ele por avanço simples, e a pasta voltou para `etapa/modelo1-por-trecho`.

**Nada foi enviado ao GitHub** (veja "O envio ao GitHub").

## O envio ao GitHub

**O controle de permissões recusou o envio** (o primeiro, depois da Parte 0). Não tentei de novo pelos outros caminhos.

**Antes do envio, conferi o que vai** (as mudanças desde `bbff5c97`):
- nenhum arquivo passa de 50 MB (o maior é o `_conta.json`, com 357 KB);
- nada de `recordings/`, `data/recordings`, `data/ml` ou `data/modelo1_por_trecho`, e nenhum `.ai`;
- nenhum segredo.

**Os comandos para você rodar pelo terminal, nesta ordem:**

```powershell
git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47 push -u origin etapa/modelo1-por-trecho
git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47 push origin develop
git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47 rev-parse etapa/modelo1-por-trecho develop
git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47 ls-remote origin refs/heads/etapa/modelo1-por-trecho refs/heads/develop
```

Depois de cada `push`, o hash do `rev-parse` e o do `ls-remote` têm de ser iguais. Todos os envios são branch nova ou avanço simples, sem `--force`. `main` e as tags não vão.

## Itens para o backlog (para o Cowork)

1. **Um teste novo no jogo para as candidatas** (C06 e C09, talvez a C13).
   - Por exemplo, a linha da IA em todos os trechos e a C3 ou a C4 só na C06 e na C09, com uma emenda contínua nas fronteiras.
   - O C0 intercalado entre as condições, para separar a deriva.
   - O ganho de um trecho muda a entrada do seguinte, então a emenda precisa de cuidado.
2. **A codificação faz a IA frear num raio fechado.**
   - Na subida dos boxes, a C1 e a C2 têm 85 a 90 m de raio num ponto, e a IA freia (+0,84 s).
   - Uma restrição de raio mínimo, ou de variação de curvatura entre pontos, na codificação e na busca pode tirar a maior parte dos 2,1 s.
   - Partir da linha do `fast_lane.ai` (item 8 do backlog do 47) é outro caminho.
   - Uma medida pontual (o menor raio, ou a maior variação de raio) deveria ser registrada antes, num pedido próprio.
3. **A IA não freia no ponto da dica do arquivo:** ela começa de 12 a 46 m depois, em 6 de 7 trechos. Vale testar uma linha com os campos de velocidade e pedais zerados ou suavizados, para saber se a IA os usa.
4. **A deriva do C0 final ficou no fim da volta** (C14 e C14→linha, 0,12 s; com a C03, 0,13 s). A causa segue desconhecida.
5. **O limite "de linha" com as 136 voltas é largo** (1,4 a 6,1 m), porque junta semanas diferentes. Para o coach (decisão 5 do desenho), um limite das voltas recentes, ou por sessão, faria mais sentido.
6. **A rampa do seu freio só existe em 7 trechos,** e você freia antes da IA em 6 deles (10 a 58 m). O ponto traduzido (decisão 3 do desenho) moveria a sua frenagem para depois em quase todos: por exemplo, de 84 m para 100,3 m na C01.
7. **A marcha gravada passa pelo 0 (o neutro) em cada troca.** Qualquer medida de marcha (no coach, no rádio ou no Modelo 2) precisa ignorar esse 0. Vale conferir se alguma já usa a marcha mínima.
8. **Para pedidos futuros:** com poucas voltas, a permutação da diferença das medianas tem um piso de p-valor que o Holm não deixa passar. A permutação da média resolve.
9. **A falha do `test_leitura` volta em toda pasta separada,** porque falta o `data/reference_models/vhe_interlagos.geometry.json`, que o git ignora. Uma junção desse arquivo, ou um teste que pule quando ele falta, resolveria.

## O que falta

- **O envio** (os comandos acima).
- **A cópia da pista continua instalada,** e a pasta do 47 não foi apagada. Você decide quando.
