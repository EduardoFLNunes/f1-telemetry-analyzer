# Relatório do pedido 34: a régua da checagem do período

- **Pedido:** `docs/prompts/2026-10-18_34_regua-da-checagem-do-periodo.md`, Partes A, B e C. Você escolheu a opção 1 do relatório do pedido 33.
- **Branch:** `etapa/regua-do-periodo`, criada de `develop` (`341ed51f`), com merge em `develop`. Nada foi enviado ao remoto.
- **Commits e merge:**
  - `6efb299e` docs: pedido 34
  - `6eb233a4` Parte A: a régua nova, a medida da linha do jogo, a checagem nova, a emenda e 9 testes
  - `c15b2587` Parte C: o relógio da M1 registrado como pendente
  - `fc9cdd2b` Parte B: o antes e depois da rodada no documento do store (seção 3)
  - o commit deste relatório, com o handoff: "Relatório do pedido 34"
  - o merge em `develop`: "Merge etapa/regua-do-periodo (pedido 34)"
- **Arquivos de handoff** (`docs/handoff/2026-10-18_34_regua-da-checagem-do-periodo_*`):
  - `_relatorio.md` (este arquivo);
  - `_rodada.txt`: a saída inteira do `atualizar_coach`;
  - `_checagens.json`: a checagem do período antes da rodada e todas as checagens depois, com o controle, os efeitos e as contagens;
  - `_outra_regua.csv`: a conferência pela outra régua, volta a volta;
  - `_captura_sessoes_1920x1080.png`: a tela Sessões depois da rodada;
  - `_testes.txt`;
  - `.patch`: de `341ed51f` até o merge, com o `backend` e os dois documentos.

## Em resumo

1. **A régua nova está no código, e a checagem passou** com o limite de 5 ms.
   - **Antes:** p99 de 7,63 ms (676 voltas), com 10 voltas acima de 5 ms.
   - **Depois:** p99 de **3,56 ms** (685 voltas), com 3 acima, todas de 14/06, do gravador de junho.
   - **A régua antiga, nas mesmas 685 voltas:** reprovaria, com p99 de 7,56 ms.
2. **A régua escolhida soma a travessia ao tempo do jogo.** Ela confere o próprio período que o store guarda, e as duas réguas dão o mesmo resultado a menos de 0,4 ms.
3. **A distância até a linha do jogo é medida nas gravações:** 1,495 m, a mediana de 683 voltas.
   - **A checagem nova** confere cada sessão contra 1,463 ± 0,10 m, a tolerância fixada antes de rodar.
   - **O resultado:** as 47 sessões com voltas suficientes ficaram entre 1,418 e 1,536 m.
4. **A rodada seguiu até o fim:** código 0, 24,8 min, com o store aprovado e o relatório de evolução refeito.
5. **A sessão de 18/10 (12:38) entrou:**
   - 9 voltas válidas, as 9 no store e no coach;
   - a mais rápida é de 1:29,061;
   - no relatório, ela aparece como `2026-10-18` (18/10 na tela Sessões).
6. **A contagem oficial da M1, agora lida de um store aprovado, é 4 de 5.**
7. **O critério do ADR 0015 segue "ainda variando":** 11 sessões, com amplitude de 1,479 s nas três últimas.
8. **O relógio da M1** ficou registrado como pendente, sem mudança agora (Parte C).
9. **Testes:**
   - **backend:** a suíte passa com **777 testes** (eram 768, mais os 9 novos);
   - **front:** o `tsc` passa, e o `vitest` passa com 182 testes;
   - **os 9 testes novos** cobrem as voltas que começam devagar e terminam rápido (e o contrário), a passagem entre duas amostras e a checagem da distância.

## Parte A: a emenda

### A.1 A régua escolhida e a conferência pela outra

**A escolhida: somar a travessia ao tempo do jogo.**

- **A conta:** tempo do jogo no s = 0 = tempo do jogo + d × (1/v no começo − 1/v no fim).
- **O código:** `store_checks.game_time_at_zero`.
- **A velocidade:** a gravada em cada passagem por s = 0, ou seja, a mediana das amostras da mesma janela de 15 m que acha a passagem (`store_v2.line_speeds`).

**Por que esta, e não medir o período em s = 1,463 m:**

1. **Ela confere o número que o store guarda.** O `lap_time_s` do store, de s = 0 a s = 0, é o relógio da grade inteira. A régua nova compara esse número com o cronômetro do jogo.
   - A outra régua compararia um terceiro número, que o store não guarda.
   - A checagem continua provando o que estava registrado: "o período de s = 0 a s = 0 bate com o cronômetro do jogo".
2. **A correção é pequena, explícita e aparece por volta** (no meta, a linha e as duas velocidades de cada volta). A outra régua escondia a correção dentro da interpolação.
3. **As duas precisavam reler as gravações uma vez,** por causa da medida da distância, então o custo foi o mesmo.

**A conferência pela outra régua:** nas 99 voltas das 9 sessões lidas no pedido 33, medi o período na própria linha do jogo, com a mesma interpolação (`crossing_time`, em s = d nas duas pontas), e comparei direto com o tempo do jogo.

| régua | \|diferença\| mediana | p99 | máximo | acima de 5 ms |
|---|---|---|---|---|
| antiga | 1,18 ms | 20,17 ms | 21,46 ms | 9 |
| **escolhida** | 1,10 ms | 7,47 ms | 8,15 ms | 2 |
| outra (período na linha do jogo) | 1,14 ms | 7,48 ms | 8,28 ms | 2 |
| **diferença entre as duas novas** | 0,05 ms | 0,33 ms | 0,40 ms | 0 |

- **As duas réguas novas dão o mesmo veredito, volta a volta.**
- **A volta `2026-10-17_16-17-08#0007`:** dá 0,28 ms nas duas, contra 11,74 ms na régua antiga.
- **As 2 voltas acima de 5 ms nessas 99** são de 14/06 e continuam acima nas três réguas.
- O p99 aqui é alto porque são só 99 voltas, de 9 sessões escolhidas no pedido 33 justamente por terem as piores voltas.

### A.2 A distância até a linha do jogo e a checagem nova

**A medida** (`store_v2.game_line_position`, campo `linha_do_jogo_m` de cada volta):
- usa as 3 primeiras amostras depois de o cronômetro zerar, com ele em até 0,06 s e o carro a 100 km/h ou mais;
- em cada uma, a linha fica em `s − v × cronômetro`;
- vale a mediana dessas amostras.

**A distância usada na régua** é a mediana de todas as voltas do store. Na rodada, deu **1,495 m**, com 683 voltas medidas.
- O pedido 33 tinha medido 1,463 m em 138 voltas de 9 sessões.
- Com o store inteiro, a mediana sobe 3 cm.
- Esses 3 cm mexem cerca de 0,5 ms, no máximo, na pior volta vista.

**A checagem nova, "a linha do jogo fica onde foi medida"** (`store_checks.check_game_line`):
- **o que confere:** cada sessão com pelo menos 3 voltas medidas tem a mediana a até **0,10 m** de 1,463 m (o valor registrado no pedido 33), e a mediana de todas também;
- **quando reprova:** se a geometria oficial ou a linha do jogo mudarem, a checagem reprova e diz qual sessão saiu e para onde;
- **por que 0,10 m:** a tolerância foi fixada antes de rodar, com as 9 sessões do pedido 33 (de 1,425 a 1,505 m). Um erro de 0,10 m na distância move a régua em no máximo 1,5 ms na pior volta vista (127 contra 264 km/h);
- **na rodada:**
  - passou;
  - 47 sessões tiveram veredito, entre 1,418 m (14/06 12:23) e 1,536 m (16/08 03:30 e 19/08 22:23);
  - 13 sessões ficaram sem veredito, com menos de 3 voltas medidas.

### A.3 Os testes (`backend/tests/test_regua_do_periodo.py`, 9 testes)

**As voltas sintéticas:**
- são gravações a 60 Hz numa pista circular;
- o cronômetro zera e o contador sobe a 1,463 m do s = 0;
- passam pelo caminho inteiro do store (gravação, corte, alinhamento e grade).

**Os testes:**

1. **Uma volta que começa devagar e termina rápido** (108 → 270 km/h, com uma rampa no meio):
   - o período, o tempo do jogo, a linha e as duas velocidades batem com o valor exato;
   - a régua antiga dá +29 ms;
   - a nova dá menos de 1 ms.
2. **O contrário** (270 → 108 km/h): a régua antiga dá −29 ms, e a nova, menos de 1 ms.
3. **A checagem do período com essa volta:** passa com a régua nova; a régua antiga acusaria a volta.
4. **A passagem pela linha entre duas amostras,** com 4 fases diferentes das amostras em relação às duas linhas: a linha medida, o período e o tempo do jogo continuam certos.
5. **A medida da linha** precisa das primeiras amostras com o carro andando. A velocidade da passagem que não está no quadro sai vazia.
6. **A checagem da distância passa perto do valor registrado,** e uma sessão com menos de 3 voltas fica sem veredito.
7. **Ela reprova com o motivo quando a linha muda:** uma sessão com a linha a 3,1 m sai com "a geometria oficial ou a linha do jogo mudaram".
8. **Ela reprova sem nenhuma medida.**
9. **A checagem do período conta a volta sem a velocidade na linha** como não medida.

O teste antigo da checagem principal ganhou as colunas novas (a mesma velocidade nas duas pontas, então a conta é a de antes).

### A.4 O registro

- **`docs/store_v2_e_evolucao.md`:**
  - a seção 1.3 ganhou a "Emenda de 18/10/2026 (pedido 34)", com o porquê, a régua, a medida, a checagem nova, a tolerância, o que não muda e o que se esperava antes de rodar;
  - a seção 3 ganhou o antes e depois da rodada.
- **O controle do store antigo** passou a usar a mesma régua. Ele continua 27,2 ms curto (mediana), como antes.

## Parte B: a rodada

### B.1 Antes de rodar

- **A cópia de antes,** fora do git, está em `data/ml/_p34_antes/` (33 MB):
  - `atualizar_coach.json` e `atualizar_coach_tempos.json`;
  - o meta do store v2 e o `store_v2_relatorio.json`;
  - o modelo do coach;
  - os JSONs de `data/ml/evolucao/`;
  - as tabelas de `data/ml/origem/`.
- **O app instalado estava fechado:**
  - não havia nenhum processo dele, do Electron nem do jogo;
  - nada respondia na porta 8000;
  - o log dele mostra que ele ficou aberto hoje até 17:10, sem gravar;
  - a rodada começou às 17:30.
- **Nenhuma sessão estava sendo gravada.**
- **Uma sessão a mais, que o pedido não cita:** a `2026-10-18_12-18-08`, gravada hoje pelo app instalado (0.4.0) entre 12:18 e 12:36.
  - Ela tem 3 voltas: duas de 7 e 9 minutos, com o carro parado em 72 a 74% das amostras, e uma de 2,5 minutos, fora da pista em 35% delas.
  - Nenhuma é válida.
  - Ela entrou no inventário como as outras e não mudou nada no coach nem no store.

### B.2 A rodada

`..\.venv\Scripts\python.exe tools\atualizar_coach.py`, padrão (incremental), na pasta `backend`. **Terminou com código 0,** das 17:30:54 às 17:55:45.

| passo | tempo | leitura |
|---|---|---|
| 1 inventário | 69,2 s | incremental: 4 sessões lidas, 141 do cache |
| 2 e 3 anotações e sessões novas | 2,5 s | as duas de 18/10, `humano` pelo indicador |
| 4 backup e treino | 649,0 s | backup `vhe_interlagos.2026-10-18_17-32-09…` |
| 5 resumo | 0 s | |
| 6 store v2 | 759,6 s | **completo:** 60 sessões lidas, porque o `store_v2.py` mudou (a chave do cache) |
| 7 relatório de evolução | 6,9 s | |
| **total** | **1.487,2 s (24,8 min)** | |

- **O passo 1 releu quatro sessões:** as duas de 18/10 e duas antigas (04/10 02:24 e 15/10 23:24).
  - O índice das duas antigas mudou, porque o app indexa a sessão quando a lê (o `session-index.json` da de 15/10 foi escrito às 12:39 pelo app do repositório).
  - As gravações em si não mudaram.
- **A próxima rodada volta a sair do cache no passo 6:**
  - os arquivos de código já estão com o fim de linha que o git entrega no checkout (CRLF);
  - então o merge não muda a chave.

### B.3 O antes e depois

**A checagem do período:**

| | antes (store de 18/10 04:51) | depois (store de 18/10 17:55) |
|---|---|---|
| régua | linha do jogo contra s = 0 | as duas em s = 0 |
| voltas medidas | 676 | 685 |
| p99 de \|diferença\| | 7,63 ms | **3,56 ms** |
| mediana de \|diferença\| | 1,03 ms | 1,05 ms |
| voltas acima de 5 ms | 10 | **3** |
| aprovado | não | **sim** |

- **As 3 voltas que continuam acima de 5 ms:**
  - `2026-06-14_12-23-46#0007`: −8,15 ms;
  - `2026-06-14_12-23-46#0005`: +7,46 ms;
  - `2026-06-14_12-44-04#0002`: −5,43 ms.
- **Por que elas continuam acima:** são todas de 14/06, do gravador de junho a 31 Hz, que parava cerca de 0,8 s logo depois da linha (pedido 33, A.4). Elas já estavam no store quando o p99 era de 4,60 ms.
- **A régua antiga, nas mesmas 685 voltas:** p99 de 7,56 ms, com 10 acima de 5 ms.
- **As outras quatro checagens também passaram:** a linha do jogo, nenhum box, nenhuma duplicata e uma geometria só.

**A sessão `2026-10-18_12-38-44`:**

- **no inventário:** 16 voltas, todas `humano` pelo indicador;
- **válidas:** 9. As outras 7 saíram pelos portões de sempre:
  - a volta de saída e a última incompletas;
  - uma volta de 335 s com o carro parado;
  - quatro com o carro fora da pista ou parado em parte da volta;
- **no store:** as 9 válidas;
- **no coach:** as 9 entram (as voltas suas no modelo foram de 103 para 112);
- **a mais rápida:** 1:29,061;
- **no relatório de evolução:** `2026-10-18`, com 9 voltas, mediana de 1:30,271, a mediana 5,442 s acima da IA e 13 de 14 curvas com diferença consistente.

**O coach:**

| | antes | depois |
|---|---|---|
| volta da IA | 1:24,828, `2026-10-04_03-42-10#0013` | igual |
| sua melhor | 1:27,013, `2026-10-15_23-24-50#0008` | igual |
| voltas suas no modelo | 103 | **112** |
| limiar | mediana 0,175 s (mín. 0,06, máx. 0,874; 3 microssetores no mínimo) | mediana 0,176 s (mín. 0,06, máx. 0,862; 3 no mínimo) |
| foco, volta da IA | índices 2, 38 e 43 (0,317, 0,367 e 0,450 s) | os mesmos (0,30, 0,36 e 0,43 s) |
| foco, sua melhor | índices 2, 18 e 31 (0,254, 0,273 e 0,255 s) | os mesmos (0,24, 0,27 e 0,26 s) |

Os focos estão no índice interno do coach. Para o piloto, são os microssetores 3, 39 e 44 (IA) e 3, 19 e 32 (sua melhor).

**O store v2, por origem:**

| | antes (676) | depois (685) |
|---|---|---|
| desconhecida | 552 | 552 |
| humano | 109 | **118** |
| ia | 13 | 13 |
| misturada | 2 | 2 |

Por pasta: 526 do app instalado e 159 do repositório.

**O critério do ADR 0015:**

| | antes (relatório de 16/10) | depois |
|---|---|---|
| sessões no relatório | 8 | **11** |
| as três últimas | — | 17/10 (+6,371 s), 17/10 (2) (+6,921 s) e 18/10 (+5,442 s), a mediana contra a IA |
| amplitude | 1,314 s | **1,479 s** |
| situação | ainda variando | ainda variando (o limite é 0,5 s) |

A tendência da mediana é de −0,223 s por sessão.

**A contagem oficial da M1,** agora lida de um store aprovado: **4 de 5.**
- As sessões que contam são as de 15/10 23:24, 17/10 01:02, 17/10 16:17 e 18/10 12:38.
- As outras com voltas suas não contam: ou têm voltas que não são suas no store, ou não têm a guinada e as velocidades locais em 95% da grade.

### B.4 A tela Sessões

Abri o app do repositório numa janela de teste, a `_captura_sessoes_1920x1080.png`:
- a janela tinha "[teste]" no título e a pasta de dados isolada;
- o backend rodava na 8011;
- fechei a janela no fim, e nenhum processo ficou aberto.

O que a tela mostra:
- **"Sessões no relatório":** 11 sessões e 112 voltas válidas;
- **a de 18/10 aparece no topo:** 9 voltas, melhor de 1:29,061, mediana de 1:30,271 e +5,442 s da IA;
- **o cartão "Modelo do carro (M1)":** 4 de 5;
- **o gráfico** termina em 18/10, com "Critério do ADR 0015: ainda variando (amplitude 1,479 s, limite 0,5 s)".

**Uma observação sobre a captura:** o cartão "Última sessão" mostra 17/10 01:02. Isso vem da pasta de gravações isolada da janela de teste, que só tem sessões até 17/10. O app de verdade lê a pasta real.

## Parte C: a recomendação para a M1

Registrei em `docs/modelo_fisico_m0.md` (seção 6, "O relógio da M1") como **pendente, sem mudança agora**:
- usar o cronômetro do jogo como relógio da M1;
- descartar as amostras repetidas;
- os números do pedido 33 (A.5) que justificam as duas coisas.

A decisão fica para o pedido que retreinar a M1.

## O que não bateu com o contexto

1. **A distância medida no store inteiro é 1,495 m,** e não 1,463 m.
   - O pedido 33 mediu 138 voltas de 9 sessões; o store tem 683 voltas medidas.
   - A checagem nova usa 1,463 m como valor registrado, e todas as sessões ficaram a até 0,08 m dele.
2. **A sessão `2026-10-18_12-18-08`,** do app instalado, não é citada no pedido. Ela não tem volta válida e não mudou nada (B.1).

Nenhum dos dois é motivo de parada.

## O que fica para você

- **O pedido 35** está na pasta, ainda sem commit, e vem depois deste.
- **Um detalhe do pedido 31** (o rádio): a pasta `data/radio/` aparece como não versionada no git, porque não está no `.gitignore`. Corrijo isso quando o pedido 31 fechar.

## Testes

- **backend:** `pytest tests`: **777 passaram**, em 8 min 56 s (eram 768; entraram os 9 de `test_regua_do_periodo.py`).
- **front:**
  - `tsc --noEmit`: sem erros;
  - `vitest`: 182 testes em 16 arquivos, todos passando.
- A saída completa está em `_testes.txt`.
- **Os testes novos e os do store,** rodados antes da rodada: 71 passando (`test_regua_do_periodo.py`, `test_store_v2_e_evolucao.py` e `test_lap_origin.py`).
