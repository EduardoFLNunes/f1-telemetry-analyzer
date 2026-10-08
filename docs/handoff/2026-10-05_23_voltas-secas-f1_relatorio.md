# Relatório do pedido 23: faixa de linhas da F1 em Interlagos com voltas secas de classificação

- **Pedido:** `docs/prompts/2026-10-05_23_voltas-secas-f1.md`
- **Branch:** `etapa/f1-voltas-secas`, com merge em `develop`
- **Commits e merge:**
  - `dd8bde1f` docs: backlog dos dados externos (chuva em 2024, faixa de voltas secas) e pedido 23 (Parte A)
  - `3d3b1102` ML: coleta das voltas secas de classificacao da F1 em Interlagos, so X e Y da posicao (pedido 23, Parte B)
  - `e02f8d96` ML: alinhamento das voltas secas, criterio por volta, incerteza V1 e V2 e faixa da F1 (pedido 23, Parte C)
  - `c2a66aff` ML: diagnostico por sessao e escala relativa ao decimetro no resumo da faixa da F1 (pedido 23, Parte C)
  - `1bc0cea3` docs: dados externos da F1 (faixa de voltas secas, limites) e resultado no backlog (pedido 23)
  - `fb9217aa` Merge etapa/f1-voltas-secas (pedido 23: faixa de voltas secas da F1)
  - o commit deste relatório, com o patch, a saída da suíte, o resumo JSON e as duas figuras: "Relatório do pedido 23: faixa de voltas secas da F1"
- **Arquivos de handoff:**
  - `docs/handoff/2026-10-05_23_voltas-secas-f1_relatorio.md` (este)
  - `docs/handoff/2026-10-05_23_voltas-secas-f1.patch` (de `635283fa` até o merge `fb9217aa`; sha256 `cb826db1…7a98a752`)
  - `docs/handoff/2026-10-05_23_voltas-secas-f1_testes.txt` (suíte `backend/tests`: 643 passando)
  - `docs/handoff/2026-10-05_23_voltas-secas-f1_resumo.json` (cópia de `data/ml/externo/f1_faixa/resumo.json`)
  - `docs/handoff/2026-10-05_23_voltas-secas-f1_faixa_pista.png` (cópia de `data/ml/externo/f1_faixa/faixa_pista.png`)
  - `docs/handoff/2026-10-05_23_voltas-secas-f1_faixa_lateral.png` (cópia de `data/ml/externo/f1_faixa/faixa_lateral.png`)

**Errata (08/10, pedido 24):** onde este relatório diz que a pasta da classificação de 2024 no cache foi baixada em junho "com o mesmo FastF1 3.4.0" ou "com a mesma versão", a afirmação está errada. Os arquivos de junho não passaram na checagem de versão do cache do FastF1 3.4.0 e foram sobrescritos no pedido 24. Ver `docs/handoff/2026-10-08_24_f1-referencia-2023-25_relatorio.md`.

Nada foi enviado ao remoto. O app instalado e os arquivos do jogo não foram tocados. Nenhum pacote foi instalado nem atualizado. Nenhum modelo foi treinado, e coach, store e critérios não mudaram.

## Em resumo

1. **A faixa foi formada com 64 voltas aceitas de 8 sessões**, acima do mínimo de 20 voltas de 3 sessões.
2. **Achado principal: a posição do FastF1 não parece ser a linha de cada carro.**
   - Dentro de uma sessão, carros diferentes ficam a 3 a 8 cm uns dos outros (desvio-padrão mediano).
   - As sessões de 2023 a 2025 ficam a 3 a 4 cm da mediana geral.
   - A volta de chuva de 2024 passa a 6 cm da mediana seca da Sprint Qualifying do mesmo fim de semana.
   - 2019 se afasta até 8,3 m, e 2021–22 até 2,7 m.

   O padrão é de um traçado de referência por época. A largura da faixa (mediana de 2,71 m) mede a diferença entre épocas, e não entre pilotos. Isso não é fato documentado: é a leitura dos números (seção "Diagnóstico por sessão").
3. **A classificação de 2024 não carregou** no FastF1 3.4.0, por causa do caminho da sessão adiada. Por isso, ficaram sem fazer:
   - a checagem do pneu da volta 32 de Norris;
   - a conferência com o pedido 22 (item C.2);
   - a volta de chuva com posição crua.

   Na comparação do item 6, usei a linha já alinhada do pedido 22. A correção é uma decisão do Eduardo (ponto 1 no fim).
4. **2018 ficou sem nenhuma volta.** 284 das 300 voltas estão como `SUPERSOFT`, nome de composto da época, e o filtro do plano aceita só SOFT, MEDIUM e HARD. As 4 que sobraram caíram por chuva.

## Conferência do contexto

| fato do pedido | onde está | bate? |
|---|---|---|
| Pedido 22 aceitou a volta 32 de Norris (2024, Q): 2,03% fora do corredor e p95 do excesso de 0 m | `data/ml/externo/fastf1_alinhamento_resumo.json` | sim |
| A classificação de 2024 foi com chuva, e a volta usou pneu de chuva ou intermediário | `Compound` do FastF1 | **não conferido**: a sessão não carregou (Parte B). Não busquei em outra fonte |
| FastF1 fixado em 3.4.0 em `backend/requirements.txt` | `backend/requirements.txt`, linha 10 | sim. O `.venv` do projeto, com torch e pytest, tem o 3.4.0, e foi o que usei. O Python global da máquina tem o 3.7.0 e não foi usado |
| Os dados de posição da volta vêm de `get_pos_data()` | `Lap.get_pos_data()` em `fastf1/core.py` 3.4.0 | sim. Ele recorta `Session.pos_data` por `LapStartTime` e `Time`, sem preencher nem interpolar bordas (padrão do `slice_by_lap`) |
| A coluna `Deleted` só existe com as mensagens da direção de prova | `_set_laps_deleted_from_rcm` | sim. Sem as mensagens, a coluna fica sem valor booleano, e a sessão sairia |
| `SQ` também nomeia a corrida sprint de 2021 e 2022 | calendário do FastF1 3.4.0 | **em parte.** No 3.4.0, a sessão de 2021 e 2022 se chama "Sprint", e não "Sprint Qualifying". Ela fica fora pelo nome e também pela data (vem depois da classificação, e não antes de uma corrida sprint) |
| Geometria `0ed16f0dd2225990`, grade de 2.167 pontos, store v2 aprovado | `load_geometry()` e `store_v2_meta()` | sim. O script para se não bater |
| 13 voltas `ia` rotuladas de 04/10 e voltas `humano` com equipamento `atual` | store v2 | sim: 13 e 18, as mesmas listas do pedido 22 |

## Parte A: documentação

Commit `dd8bde1f`, junto com o arquivo do pedido. Em `docs/backlog.md`:

1. **"Dados externos no treino do Modelo 1":**
   - acrescentei ao Impacto: "A volta alinhada no pedido 22 é da classificação de 2024, com chuva";
   - o Quando passou de "A definir" para "Em andamento: alinhamento de uma volta aceito no pedido 22; faixa de voltas secas no pedido 23. Entra no treino junto com o retreino das três fontes".
2. **"Retreinar a LSTM geradora com as três fontes":** troquei "(pedido 22, Parte B)" por "(pedidos 22 e 23)".

No fim (commit `1bc0cea3`), o Quando da primeira linha ganhou o resultado:

> Em andamento: alinhamento de uma volta aceito no pedido 22; faixa de voltas secas no pedido 23, formada com 64 voltas de 8 sessões. A posição do FastF1 parece seguir um traçado de referência por época, e não a linha de cada carro (`docs/dados_externos_f1.md`). Entra no treino junto com o retreino das três fontes

A segunda frase é minha: sem ela, "faixa formada" sugere mais do que os dados mostram. Vale o Cowork revisar.

**Documento novo:** `docs/dados_externos_f1.md`. Ele traz o que entra, a fonte, o método, os resultados e os limites, com links para o ADR 0018 e para os relatórios 22 e 23.

## Parte B: coleta das voltas secas

### O que foi feito

| arquivo | o que é |
|---|---|
| `backend/ml/external/f1_dry_laps.py` (novo) | calendário (nome e data), carga com `laps`, `telemetry`, `weather` e `messages`, funil dos seis filtros, melhor volta por piloto e corte nos 10, e leitura de só `X` e `Y` |
| `backend/tests/test_f1_voltas_secas.py` (novo, 9 testes) | filtros, escolha das sessões, leitura e sessão sem `Deleted`, com um módulo FastF1 falso |

O importador do app (`backend/core/external_references/`) não foi alterado.

### Sessões

| ano | sessão | data no calendário | situação |
|---|---|---|---|
| 2018 | Qualifying | 10/11, 15:00 | carregou |
| 2019 | Qualifying | 16/11, 15:00 | carregou |
| 2021 | Qualifying | 12/11, 16:00 | carregou |
| 2022 | Qualifying | 11/11, 16:00 | carregou |
| 2023 | Qualifying | 03/11, 15:00 | carregou |
| 2023 | Sprint Shootout | 04/11, 11:00 (antes da Sprint, 15:30) | carregou |
| 2024 | Sprint Qualifying | 01/11, 15:30 (antes da Sprint, 02/11) | carregou |
| 2024 | Qualifying | 03/11, 07:30 | **não carregou** |
| 2025 | Sprint Qualifying | 07/11, 15:30 (antes da Sprint, 08/11) | carregou |
| 2025 | Qualifying | 08/11, 15:00 | carregou |

A corrida sprint de 2021, 2022, 2023, 2024 e 2025 ficou fora, registrada no manifesto.

**O erro de 2024.** O FastF1 3.4.0 monta o caminho da sessão a partir das datas do calendário: `/static/2024/2024-11-03_São_Paulo_Grand_Prix/2024-11-03_Qualifying/`. A classificação foi adiada de sábado para domingo por causa da chuva, e o calendário de hoje traz a data nova. O servidor da F1 responde que não há dados nesse caminho (`SessionNotAvailableError`), e nenhuma parte da sessão carrega.

Os avisos do FastF1 estão no manifesto, de "Failed to load session info data!" a "Car position data is unavailable!". O resultado é um `DataNotLoadedError` ao ler as voltas.

O cache já tem essa sessão em `2024-11-03_São_Paulo_Grand_Prix/2024-11-02_Qualifying/`. Ela foi baixada em junho, pelo importador do app, com o mesmo FastF1 3.4.0, quando o calendário ainda dizia 02/11. Segui a regra do plano: registrei o erro e segui com as outras. Não mudei o caminho, porque isso contornaria o que o plano manda fazer. O ponto 1 do fim descreve a correção.

**Rede, cache e tempo.**

| | valor |
|---|---|
| cache antes do pedido | 55.528.409 bytes (55,5 MB), só a classificação de 2024 baixada em junho |
| cache no fim | **474.895.068 bytes (474,9 MB)** |
| download das 9 sessões | **129 s** no total, de 13 a 15 s cada, mais 8,8 s da tentativa de 2024 |
| calendário e carga do cache, na rodada final | 22,6 s para as 10 sessões (cerca de 1 a 2 s cada, 7,8 s na de 2024, que tenta a rede) |
| rodada inteira (coleta, alinhamento, faixa e figuras) | 61,7 s |

O primeiro download foi feito por um script de sondagem meu, fora do repositório, para conferir as colunas antes de escrever o código. Ele leu só a tabela de voltas, o tempo, as mensagens e a presença dos dados de posição. Nenhum canal do carro foi lido. Cada rodada acrescenta 4 KB ao cache, da resposta de erro de 2024.

### Funil por sessão

Voltas que restam depois de cada filtro, na ordem do pedido:

| sessão | voltas | pneu seco | `IsAccurate` | não apagada | bandeira verde | sem box | sem chuva | melhores por piloto | escolhidas |
|---|---|---|---|---|---|---|---|---|---|
| 2018 Q | 300 | 16 | 4 | 4 | 4 | 4 | **0** | 0 | 0 |
| 2019 Q | 271 | 271 | 106 | 106 | 102 | 102 | 102 | 19 | 10 |
| 2021 Q | 323 | 323 | 133 | 129 | 129 | 129 | 129 | 20 | 10 |
| 2022 Q | 416 | 277 | 158 | 158 | 158 | 158 | 149 | 20 | 10 |
| 2023 Q | 293 | 293 | 101 | 100 | 98 | 98 | 98 | 20 | 10 |
| 2023 Sprint Shootout | 209 | 209 | 82 | 82 | 79 | 79 | 79 | 20 | 10 |
| 2024 Sprint Qualifying | 221 | 221 | 81 | 79 | 79 | 79 | 79 | 20 | 10 |
| 2024 Q | — | — | — | — | — | — | — | — | erro de carga |
| 2025 Sprint Qualifying | 253 | 253 | 121 | 120 | 117 | 117 | 117 | 20 | 10 |
| 2025 Q | 316 | 316 | 109 | 109 | 109 | 109 | 109 | 19 | 10 |

- **2018:** os pneus são 284 `SUPERSOFT` e 16 `SOFT`. Apliquei o filtro como está no plano e não mexi nele depois de ver o resultado. Das 16 SOFT, 12 são imprecisas e 4 caem na chuva: houve `Rainfall` verdadeiro em 33 dos 78 registros de tempo da sessão.
- **2022:** 139 voltas de intermediário saem no primeiro filtro, e 9 secas saem por chuva (27 dos 81 registros com chuva).
- **Informação de volta apagada:** a coluna `Deleted` é booleana nas 9 sessões, então nenhuma saiu por isso. Conferi também com as mensagens da direção de prova. O número de mensagens com "DELETED" é igual ao de voltas marcadas como apagadas em todas as sessões (0, 0, 4, 1, 1, 0, 2, 1 e 0, na ordem da tabela). Não houve "REINSTATED".
- **Registros de tempo:** todas as 80 voltas escolhidas têm 1 ou 2 registros de `weather_data` dentro da volta (62 com 1 e 18 com 2). Nenhuma passou no filtro de chuva por falta de registro.
- **Leitura:** de cada volta escolhida saíram de 228 a 315 amostras de `X` e `Y`, todas finitas.

## Parte C: alinhar, aceitar e formar a faixa

### O que foi feito

| arquivo | o que é |
|---|---|
| `backend/ml/external/f1_line.py` (alterado) | `umeyama`, `fit_similarity` e `refine_icp` aceitam `fixed_scale` (V1); funções novas `with_scale`, `align_fixed_scale` e `refine_icp_session` (V2). Os valores padrão não mudaram |
| `backend/ml/external/f1_band.py` (novo) | critério por volta, dispersão das transformações, faixa, amplitude entre sessões e comparação com a faixa |
| `backend/ml/scripts/faixa_f1_secas.py` (novo) | roda as Partes B e C e grava em `data/ml/externo/f1_faixa/` |
| `backend/tests/test_f1_faixa.py` (novo, 10 testes) | V1, V2, faixa, regra de "dentro" e critério por volta |

Comando: `python -m ml.scripts.faixa_f1_secas`, a partir de `backend/`, com o Python do `.venv`.

**O pedido 22 não mudou.** Depois de mexer em `f1_line.py`, rodei o `alinhar_fastf1` de novo numa pasta temporária. A grade em CSV saiu idêntica byte a byte, e o JSON só mudou em `gerado_em`, `commit` e no caminho da figura.

### 1. Alinhamento de cada volta

Usei o método do pedido 22, sem mudança: busca inicial por Procrustes, ICP contra a linha central da geometria `0ed16f0dd2225990`, escala única livre, espelho permitido, projeção na grade de 2.167 pontos e excesso sobre o corredor.

- **As 80 voltas escolhidas convergiram.**
- As 64 aceitas saíram espelhadas, todas.
- A escala ficou entre 0,9977 e 0,9982 do decímetro.

### 2. Conferência com o pedido 22

**Não feita.** A classificação de 2024 não carregou, então não há posição crua da volta 32 de Norris para passar pelo caminho novo. O código da conferência está pronto, em `conference_with_p22`, e roda sozinho se a sessão carregar.

### 3. Critério por volta e veredito

O critério foi fixado antes de rodar e não mudou:

- cobertura ≥ 0,99;
- maior buraco ≤ 80 m;
- fração fora do corredor ≤ 10%;
- p95 do excesso ≤ 1 m.

**80 escolhidas, 64 aceitas e 16 recusadas.**

Aceitas:

| sessão | n | voltas (piloto e número) |
|---|---|---|
| 2019 Q | 9 | HAM 15, VER 5, LEC 16, VET 11, ALB 10, BOT 13, GAS 12, MAG 8, GRO 7 |
| 2021 Q | 10 | RIC 21, NOR 21, GAS 17, PER 21, ALO 18, LEC 15, VER 13, HAM 22, SAI 18, BOT 16 |
| 2022 Q | 8 | LEC 20, VER 19, HAM 17, RUS 20, ALO 13, OCO 17, NOR 20, MAG 22 |
| 2023 Q | 7 | SAI 14, RUS 14, ALO 14, VER 11, PER 13, NOR 9, PIA 8 |
| 2023 Sprint Shootout | 9 | VER 15, PER 15, LEC 14, TSU 11, RIC 10, HAM 13, SAI 12, RUS 13, PIA 13 |
| 2024 Sprint Qualifying | 8 | RUS 14, BEA 8, ALB 8, LEC 17, SAI 14, GAS 11, LAW 7, VER 11 |
| 2025 Sprint Qualifying | 5 | VER 14, NOR 19, HAD 8, ANT 12, HUL 8 |
| 2025 Q | 8 | NOR 20, PIA 10, RUS 8, GAS 14, HAD 20, ANT 15, LAW 11, BEA 10 |

Nas aceitas, estes são os números do critério:

| medida | mínimo | mediana | máximo |
|---|---|---|---|
| cobertura | 0,9905 | 0,9952 | 1,0002 |
| maior buraco | 21,4 m | 42,7 m | 79,7 m |
| fração fora do corredor | 1,0% | 1,9% | 2,9% |
| p95 do excesso | 0 m | 0 m | 0 m |

Uma cobertura acima de 1 quer dizer que a primeira e a última amostra se sobrepõem alguns metros na linha de chegada.

Recusadas, com os números:

| volta | tempo (s) | pneu | cobertura | maior buraco (m) | fora | p95 (m) | falhou em |
|---|---|---|---|---|---|---|---|
| 2019 Q RAI 11 | 68,858 | SOFT | 0,9897 | 44,5 | 2,5% | 0 | cobertura |
| 2022 Q PER 20 | 71,456 | SOFT | 0,9899 | 66,4 | 2,8% | 0 | cobertura |
| 2022 Q SAI 20 | 70,890 | SOFT | 0,9966 | 100,2 | 2,8% | 0 | buraco |
| 2023 Q LEC 14 | 70,303 | SOFT | 0,9926 | 83,3 | 1,9% | 0 | buraco |
| 2023 Q STR 12 | 70,375 | SOFT | 0,9861 | 60,2 | 1,8% | 0 | cobertura |
| 2023 Q HAM 17 | 70,266 | SOFT | 0,9967 | 86,1 | 1,8% | 0 | buraco |
| 2023 SS NOR 14 | 70,622 | SOFT | 0,9854 | 63,2 | 1,5% | 0 | cobertura |
| 2024 SQ NOR 11 | 68,928 | SOFT | 0,9991 | 90,1 | 1,8% | 0 | buraco |
| 2024 SQ PIA 15 | 68,899 | SOFT | 0,9891 | 47,4 | 1,9% | 0 | cobertura |
| 2025 SQ ALO 8 | 69,330 | MEDIUM | 0,9948 | 108,1 | 1,8% | 0 | buraco |
| 2025 SQ LEC 15 | 69,725 | SOFT | 0,9938 | 104,0 | 1,9% | 0 | buraco |
| 2025 SQ STR 8 | 69,647 | MEDIUM | 0,9956 | 93,0 | 1,8% | 0 | buraco |
| 2025 SQ RUS 6 | 69,447 | MEDIUM | 0,9849 | 73,6 | 1,9% | 0 | cobertura |
| 2025 SQ PIA 11 | 69,416 | MEDIUM | 0,9911 | 96,4 | 1,6% | 0 | buraco |
| 2025 Q HUL 16 | 69,985 | SOFT | 0,9888 | 74,7 | 1,8% | 0 | cobertura |
| 2025 Q LEC 15 | 69,801 | SOFT | 0,9948 | 96,0 | 1,9% | 0 | buraco |

O tempo só identifica a volta. Todas as recusas vêm da amostragem: 9 por buraco e 7 por cobertura. Nenhuma volta passou de 2,9% fora do corredor. A posição crua tem cerca de 4 amostras por segundo, contra as cerca de 8 da volta do pedido 22, que juntava posição e dados do carro.

**Onde fica o excesso.** Fica nos mesmos três microsetores do pedido 22. Não medi o lado do excesso nas voltas novas.

- MS19, Descida do Lago: 53 das 64 voltas;
- MS38, Bico de Pato: 55 voltas;
- MS45, Junção: 54 voltas, com o máximo de 2,39 m.

Em menos voltas, aparece também em MS06 (23 voltas), MS12 a MS14 (9 voltas) e MS32 (8 voltas).

### 4. Incerteza do alinhamento (V1 e V2)

As duas variantes foram calculadas para as 64 voltas aceitas e não escolheram nenhuma volta.

**As posições de uma sessão estão no mesmo sistema de coordenadas.** As transformações por volta (método principal) variam muito pouco dentro de cada sessão:

| sessão | voltas | escala / decímetro (por volta) | rotação mediana | amplitude da rotação | maior distância no centróide (m) | escala da sessão (V2) | rotação da sessão (V2) | iterações (V2) |
|---|---|---|---|---|---|---|---|---|
| 2019 Q | 9 | 0,9980 a 0,9980 | 0,801° | 0,0028° | 0,010 | 0,9980 | 0,801° | 20 |
| 2021 Q | 10 | 0,9977 a 0,9977 | 0,569° | 0,0030° | 0,006 | 0,9977 | 0,569° | 19 |
| 2022 Q | 8 | 0,9978 a 0,9979 | 0,559° | 0,0122° | 0,061 | 0,9979 | 0,560° | 29 |
| 2023 Q | 7 | 0,9980 a 0,9981 | 0,551° | 0,0052° | 0,052 | 0,9981 | 0,551° | 22 |
| 2023 Sprint Shootout | 9 | 0,9980 a 0,9981 | 0,550° | 0,0084° | 0,052 | 0,9980 | 0,550° | 30 |
| 2024 Sprint Qualifying | 8 | 0,9980 a 0,9981 | 0,550° | 0,0065° | 0,036 | 0,9980 | 0,550° | 25 |
| 2025 Sprint Qualifying | 5 | 0,9978 a 0,9982 | 0,544° | 0,0198° | 0,093 | 0,9980 | 0,544° | 30 |
| 2025 Q | 8 | 0,9979 a 0,9981 | 0,552° | 0,0106° | 0,093 | 0,9980 | 0,552° | 26 |

A "maior distância no centróide" é a maior distância entre a imagem do centróide da sessão por uma volta e a mediana dessas imagens. A V2 convergiu nas 8 sessões. A rotação de 2019 (0,80°) difere da dos outros anos (0,54° a 0,57°).

**Por microsetor**, a mediana e o p90 de |lateral da variante − lateral principal| estão nas colunas V1 e V2 da tabela da faixa, mais abaixo:

- **V2 (uma transformação por sessão):** p90 de 0,016 m a 0,065 m. Ela quase não muda nada.
- **V1 (escala presa em 0,1 m por unidade):** p90 de 0,06 m a 1,27 m. A escala livre sai 0,2% abaixo do decímetro, e prendê-la desloca o lateral em até cerca de 1 m nos trechos mais longe do centro da pista.

**Faixa pouco confiável (p90 acima de 1 m), 10 microsetores, todos pela V1:** MS04 a MS09 (217 a 650 m, do S do Senna em diante), MS19 (Descida do Lago) e MS46 a MS48 (3.251 a 3.467 m, depois da Junção). É a confusão entre escala e lateral registrada no pedido 22, agora medida.

### 5. Faixa

**Formada: 64 voltas de 8 sessões**, contra o mínimo de 20 de 3.

| medida | valor |
|---|---|
| largura p10–p90 (por ponto) | mediana 2,71 m, p90 5,72 m |
| amplitude entre as medianas das sessões (por microsetor) | mediana 2,67 m, p90 5,35 m, máximo 6,89 m (MS56) |
| lateral médio na volta | mediana da F1 −0,20 m, mediana da IA +0,38 m, mediana do piloto −0,81 m |

O `n` é 64 em todos os pontos: toda volta aceita cobre a grade inteira, com a interpolação em `s`.

Por microsetor, em metros (positivo à esquerda). As colunas p10, p50, p90 e largura são a mediana, no microsetor, dos valores por ponto. V1 e V2 trazem mediana / p90 de |variante − principal|.

| microsetor | s (m) | p10 | p50 | p90 | largura | amplitude entre sessões | V1 | V2 | pouco confiável |
|---|---|---|---|---|---|---|---|---|---|
| MS01 | 0 a 72 | −4,66 | −4,59 | −0,19 | 4,47 | 4,49 | 0,58 / 0,68 | 0,007 / 0,028 | |
| MS02 | 72 a 144 | −4,48 | −4,40 | −0,39 | 4,09 | 4,11 | 0,61 / 0,71 | 0,008 / 0,032 | |
| MS03 | 144 a 217 | −3,07 | −2,95 | −0,33 | 2,76 | 2,74 | 0,67 / 0,78 | 0,009 / 0,040 | |
| MS04 | 217 a 289 | −0,33 | +1,56 | +2,37 | 2,65 | 2,76 | 0,94 / 1,13 | 0,009 / 0,042 | sim |
| MS05 | 289 a 361 | −1,12 | +0,24 | +2,06 | 3,19 | 3,08 | 0,77 / 1,09 | 0,011 / 0,035 | sim |
| MS06 | 361 a 433 | −5,05 | −4,03 | +0,01 | 4,29 | 5,06 | 0,96 / 1,12 | 0,009 / 0,030 | sim |
| MS07 | 433 a 506 | −0,64 | +4,62 | +4,70 | 5,39 | 5,33 | 1,04 / 1,19 | 0,009 / 0,038 | sim |
| MS08 | 506 a 578 | −0,92 | +4,12 | +4,22 | 5,14 | 5,12 | 1,09 / 1,27 | 0,009 / 0,033 | sim |
| MS09 | 578 a 650 | −1,07 | +2,09 | +2,22 | 3,27 | 3,28 | 1,00 / 1,13 | 0,009 / 0,027 | sim |
| MS10 | 650 a 722 | −2,64 | −2,44 | −0,64 | 1,94 | 1,95 | 0,77 / 0,90 | 0,009 / 0,030 | |
| MS11 | 722 a 795 | −4,70 | −4,50 | +0,29 | 4,94 | 5,00 | 0,62 / 0,72 | 0,008 / 0,029 | |
| MS12 | 795 a 867 | −1,83 | −1,64 | +2,24 | 4,06 | 4,10 | 0,63 / 0,74 | 0,008 / 0,024 | |
| MS13 | 867 a 939 | +0,12 | +0,33 | +2,72 | 2,54 | 2,62 | 0,66 / 0,76 | 0,007 / 0,030 | |
| MS14 | 939 a 1.011 | −1,61 | −1,41 | −0,07 | 1,60 | 1,62 | 0,68 / 0,79 | 0,006 / 0,038 | |
| MS15 | 1.011 a 1.084 | −1,34 | −1,15 | +0,00 | 1,34 | 1,40 | 0,70 / 0,82 | 0,006 / 0,043 | |
| MS16 | 1.084 a 1.156 | −1,21 | −0,98 | +0,18 | 1,40 | 1,45 | 0,73 / 0,85 | 0,006 / 0,049 | |
| MS17 | 1.156 a 1.228 | −1,05 | −0,81 | +0,58 | 1,58 | 1,66 | 0,75 / 0,87 | 0,007 / 0,044 | |
| MS18 | 1.228 a 1.300 | −1,47 | −1,12 | +0,81 | 2,27 | 2,31 | 0,78 / 0,90 | 0,007 / 0,045 | |
| MS19 | 1.300 a 1.372 | +0,49 | +6,24 | +7,02 | 6,89 | 6,56 | 0,88 / 1,03 | 0,010 / 0,058 | sim |
| MS20 | 1.372 a 1.445 | −2,78 | −2,54 | −0,16 | 4,20 | 2,56 | 0,60 / 0,82 | 0,009 / 0,051 | |
| MS21 | 1.445 a 1.517 | −1,23 | −1,01 | −0,13 | 1,85 | 1,08 | 0,39 / 0,48 | 0,009 / 0,041 | |
| MS22 | 1.517 a 1.589 | +0,43 | +2,86 | +3,21 | 2,73 | 2,89 | 0,10 / 0,24 | 0,008 / 0,034 | |
| MS23 | 1.589 a 1.661 | −1,25 | −1,08 | +0,64 | 1,89 | 1,85 | 0,10 / 0,13 | 0,006 / 0,023 | |
| MS24 | 1.661 a 1.734 | −3,50 | −1,22 | +0,70 | 4,20 | 4,22 | 0,12 / 0,14 | 0,005 / 0,019 | |
| MS25 | 1.734 a 1.806 | −1,23 | −1,14 | +0,62 | 1,85 | 1,85 | 0,10 / 0,12 | 0,004 / 0,016 | |
| MS26 | 1.806 a 1.878 | +0,66 | +0,76 | +1,17 | 0,75 | 0,52 | 0,08 / 0,09 | 0,004 / 0,016 | |
| MS27 | 1.878 a 1.950 | +0,61 | +2,21 | +2,59 | 1,96 | 1,98 | 0,06 / 0,07 | 0,005 / 0,019 | |
| MS28 | 1.950 a 2.023 | −0,97 | −0,79 | +0,83 | 1,75 | 1,77 | 0,13 / 0,18 | 0,008 / 0,027 | |
| MS29 | 2.023 a 2.095 | +0,06 | +0,95 | +1,16 | 1,37 | 1,13 | 0,25 / 0,30 | 0,008 / 0,033 | |
| MS30 | 2.095 a 2.167 | −1,03 | −0,88 | −0,33 | 2,53 | 0,46 | 0,34 / 0,39 | 0,006 / 0,033 | |
| MS31 | 2.167 a 2.239 | −0,61 | +3,54 | +3,70 | 4,32 | 4,29 | 0,35 / 0,41 | 0,006 / 0,029 | |
| MS32 | 2.239 a 2.312 | −5,54 | −5,35 | −0,33 | 5,35 | 5,23 | 0,40 / 0,46 | 0,007 / 0,031 | |
| MS33 | 2.312 a 2.384 | −0,47 | +0,42 | +0,67 | 2,65 | 0,90 | 0,12 / 0,18 | 0,010 / 0,047 | |
| MS34 | 2.384 a 2.456 | +0,59 | +2,31 | +3,26 | 2,90 | 2,72 | 0,19 / 0,23 | 0,006 / 0,026 | |
| MS35 | 2.456 a 2.528 | +0,27 | +2,48 | +2,69 | 2,26 | 2,48 | 0,10 / 0,18 | 0,007 / 0,043 | |
| MS36 | 2.528 a 2.600 | −3,71 | −3,61 | −0,54 | 3,08 | 3,19 | 0,17 / 0,20 | 0,009 / 0,055 | |
| MS37 | 2.600 a 2.673 | −1,82 | −1,14 | −0,94 | 1,52 | 0,58 | 0,07 / 0,16 | 0,009 / 0,048 | |
| MS38 | 2.673 a 2.745 | −6,59 | −6,43 | −1,09 | 5,98 | 5,55 | 0,61 / 0,75 | 0,009 / 0,041 | |
| MS39 | 2.745 a 2.817 | −0,06 | +0,48 | +0,92 | 1,39 | 0,83 | 0,37 / 0,57 | 0,011 / 0,065 | |
| MS40 | 2.817 a 2.889 | −1,83 | −1,70 | −0,37 | 1,50 | 1,40 | 0,40 / 0,49 | 0,011 / 0,057 | |
| MS41 | 2.889 a 2.962 | +0,66 | +4,28 | +4,38 | 3,67 | 3,74 | 0,46 / 0,53 | 0,009 / 0,041 | |
| MS42 | 2.962 a 3.034 | +0,89 | +1,92 | +2,09 | 2,27 | 1,22 | 0,25 / 0,36 | 0,008 / 0,033 | |
| MS43 | 3.034 a 3.106 | −3,57 | −3,01 | +0,12 | 3,66 | 3,73 | 0,03 / 0,06 | 0,008 / 0,031 | |
| MS44 | 3.106 a 3.178 | −1,47 | −1,03 | +0,61 | 2,09 | 2,11 | 0,05 / 0,11 | 0,009 / 0,038 | |
| MS45 | 3.178 a 3.251 | +0,45 | +6,45 | +6,73 | 6,24 | 6,21 | 0,64 / 0,98 | 0,012 / 0,061 | |
| MS46 | 3.251 a 3.323 | −1,00 | −0,88 | +0,38 | 1,58 | 1,34 | 1,00 / 1,17 | 0,013 / 0,063 | sim |
| MS47 | 3.323 a 3.395 | −0,13 | +1,10 | +1,25 | 1,21 | 1,25 | 0,98 / 1,12 | 0,012 / 0,057 | sim |
| MS48 | 3.395 a 3.467 | −1,84 | −1,71 | −0,74 | 1,04 | 1,11 | 0,91 / 1,05 | 0,012 / 0,048 | sim |
| MS49 | 3.467 a 3.539 | −2,16 | −2,02 | −0,78 | 1,40 | 1,34 | 0,85 / 0,98 | 0,012 / 0,043 | |
| MS50 | 3.539 a 3.612 | −0,56 | +3,24 | +3,47 | 3,98 | 4,06 | 0,78 / 0,87 | 0,012 / 0,045 | |
| MS51 | 3.612 a 3.684 | −1,10 | +5,51 | +5,62 | 6,72 | 6,70 | 0,64 / 0,73 | 0,009 / 0,040 | |
| MS52 | 3.684 a 3.756 | −3,22 | −2,61 | −0,66 | 2,66 | 2,27 | 0,53 / 0,61 | 0,008 / 0,037 | |
| MS53 | 3.756 a 3.828 | −6,34 | −5,10 | −0,15 | 6,22 | 6,20 | 0,48 / 0,56 | 0,008 / 0,033 | |
| MS54 | 3.828 a 3.901 | −4,94 | −3,74 | +0,12 | 5,08 | 5,31 | 0,49 / 0,56 | 0,008 / 0,034 | |
| MS55 | 3.901 a 3.973 | +0,80 | +3,41 | +3,61 | 2,73 | 2,83 | 0,48 / 0,55 | 0,008 / 0,032 | |
| MS56 | 3.973 a 4.045 | +0,44 | +7,15 | +7,33 | 6,78 | 6,89 | 0,48 / 0,55 | 0,007 / 0,030 | |
| MS57 | 4.045 a 4.117 | +1,12 | +3,59 | +3,70 | 2,58 | 2,60 | 0,49 / 0,57 | 0,006 / 0,027 | |
| MS58 | 4.117 a 4.190 | −1,51 | −1,42 | +0,41 | 1,92 | 1,93 | 0,51 / 0,59 | 0,005 / 0,023 | |
| MS59 | 4.190 a 4.262 | −3,49 | −3,43 | +0,27 | 3,76 | 3,75 | 0,53 / 0,62 | 0,006 / 0,022 | |
| MS60 | 4.262 a 4.334 | −4,39 | −4,34 | +0,03 | 4,42 | 4,43 | 0,56 / 0,65 | 0,006 / 0,026 | |

**A faixa é assimétrica.** A mediana fica quase sempre colada numa das bordas. Por exemplo, no MS56 o p10 é +0,44, o p50 +7,15 e o p90 +7,33. A largura acompanha a amplitude entre sessões em quase todos os microsetores. A seção seguinte explica por quê.

### Diagnóstico por sessão (descritivo, acrescentado depois da primeira rodada)

A primeira rodada mostrou a faixa assimétrica. Para entender, acrescentei ao `resumo.json` um diagnóstico por sessão. Ele não muda a faixa nem nenhum critério: `faixa.csv` e as 64 grades por volta ficaram idênticos byte a byte entre as rodadas.

| sessão | voltas | desvio-padrão entre voltas (mediana dos pontos, m) | amplitude entre voltas, mediana (m) | idem, p90 (m) | \|sessão − mediana geral\|, mediana (m) | idem, p90 (m) | idem, máx. (m) | \|volta de chuva − sessão\|, mediana (m) | idem, p90 (m) |
|---|---|---|---|---|---|---|---|---|---|
| 2019 Q | 9 | 0,026 | 0,08 | 0,17 | 2,29 | 5,13 | 8,30 | 2,33 | 5,23 |
| 2021 Q | 10 | 0,029 | 0,10 | 0,17 | 0,26 | 0,85 | 2,49 | 0,32 | 0,90 |
| 2022 Q | 8 | 0,053 | 0,17 | 0,55 | 0,25 | 1,01 | 2,72 | 0,29 | 0,96 |
| 2023 Q | 7 | 0,043 | 0,13 | 0,35 | 0,03 | 0,11 | 0,35 | 0,06 | 0,22 |
| 2023 Sprint Shootout | 9 | 0,049 | 0,16 | 0,45 | 0,03 | 0,11 | 0,49 | 0,06 | 0,21 |
| 2024 Sprint Qualifying | 8 | 0,045 | 0,14 | 0,41 | 0,03 | 0,10 | 0,29 | 0,06 | 0,22 |
| 2025 Sprint Qualifying | 5 | 0,080 | 0,21 | 0,56 | 0,04 | 0,13 | 0,35 | 0,08 | 0,24 |
| 2025 Q | 8 | 0,056 | 0,18 | 0,47 | 0,03 | 0,10 | 0,25 | 0,06 | 0,23 |

O que os números mostram:

- **Dentro de cada sessão, as voltas quase coincidem.** São 5 a 10 carros de equipes diferentes, e o desvio-padrão por ponto fica entre 3 e 8 cm. Linhas de pilotos diferentes não coincidem a centímetros nas curvas.
- **Há três grupos, por época:**
  - 2023, 2024 e 2025 ficam a 3 a 4 cm da mediana geral;
  - 2021 e 2022 ficam a cerca de 0,25 m, com até 2,7 m;
  - 2019 fica a 2,3 m na mediana, com até 8,3 m.
- **A volta de chuva de 2024** (a linha do pedido 22, na Q de domingo) passa a 6 cm, na mediana, da Sprint Qualifying seca de sexta e da mediana de 2023–25. Se ela foi de fato com pneu de chuva, uma linha real dificilmente ficaria tão perto da seca.

**Leitura:** a posição do FastF1 parece seguir um traçado de referência por época, e não a linha que cada carro fez. Não achei nada na documentação do FastF1 3.4.0 instalado que confirme ou negue isso, então fica como hipótese apoiada pelos números.

Consequências:

- a largura da faixa mede quase só a diferença entre os três grupos;
- 2023–25 tem 37 das 64 voltas, e por isso a mediana da faixa fica colada no traçado dessa época;
- a hipótese do contexto, de que na chuva os pilotos fogem da linha seca, não pode ser medida com estes dados.

### 6. Comparação descritiva, só para leitura

Nada disto muda coach, store ou critério. As linhas são as mesmas do pedido 22: 13 voltas `ia` rotuladas de 04/10 e 18 voltas `humano` com equipamento `atual`. Um microsetor conta como "dentro" se pelo menos 50% dos seus pontos ficam em [p10, p90].

| linha | microsetores dentro | pontos dentro |
|---|---|---|
| mediana da IA (13 voltas) | **16 de 60** | 27,6% |
| mediana do piloto (18 voltas) | **17 de 60** | 33,4% |
| volta de chuva de 2024 (linha do pedido 22) | **53 de 60** | 79,7% |

Os 5 mais fora de cada uma. A ordem é pela distância mediana até a borda da faixa, no microsetor. Positivo quer dizer que a linha passa à esquerda da faixa (ADR 0003).

| | microsetor | pontos dentro | lado | distância até a borda (m) |
|---|---|---|---|---|
| IA | MS37 (2.600 a 2.673 m) | 3% | esquerda | +4,42 |
| IA | MS48 (3.395 a 3.467 m) | 0% | esquerda | +3,97 |
| IA | MS26 (1.806 a 1.878 m) | 0% | esquerda | +3,74 |
| IA | MS44 (3.106 a 3.178 m) | 0% | direita | −3,24 |
| IA | MS09 (578 a 650 m) | 0% | esquerda | +2,93 |
| piloto | MS58 (4.117 a 4.190 m) | 0% | direita | −3,39 |
| piloto | MS29 (2.023 a 2.095 m) | 0% | direita | −2,71 |
| piloto | MS26 (1.806 a 1.878 m) | 0% | esquerda | +2,64 |
| piloto | MS28 (1.950 a 2.023 m) | 0% | direita | −2,57 |
| piloto | MS46 (3.251 a 3.323 m) | 0% | direita | −2,38 |
| chuva | MS28 (1.950 a 2.023 m) | 11% | direita | −0,13 |
| chuva | MS41 (2.889 a 2.962 m) | 19% | esquerda | +0,11 |
| chuva | MS42 (2.962 a 3.034 m) | 33% | esquerda | +0,10 |
| chuva | MS56 (3.973 a 4.045 m) | 33% | esquerda | +0,04 |
| chuva | MS45 (3.178 a 3.251 m) | 47% | esquerda | +0,02 |

A volta de chuva fica fora em 7 microsetores (MS09, MS28, MS41, MS42, MS45, MS56 e MS60), mas sempre a no máximo 0,13 m da borda.

**"F1 − IA" e "F1 − piloto" com a mediana da faixa.** A diferença é a mediana da faixa menos a mediana das voltas, por ponto, reduzida por microsetor pela mediana. Positivo quer dizer F1 mais à esquerda.

| | mediana de \|Δ\| por microsetor | p90 | máximo |
|---|---|---|---|
| mediana da F1 − mediana da IA | 1,85 m | 3,36 m | 5,00 m (MS48, 3.395 a 3.467 m) |
| mediana da F1 − mediana do piloto | 1,48 m | 3,02 m | 3,82 m (MS35, 2.456 a 2.528 m) |

**Contra o pedido 22** (1,81, 3,33 e 5,02 m para a IA; 1,44, 3,04 e 3,80 m para o piloto), a tabela quase não muda. Por microsetor, a diferença entre as duas tem mediana de 0,08 m na IA e 0,05 m no piloto, com máximo de 0,38 m e 0,32 m. É o esperado pelo diagnóstico: a mediana da faixa é o traçado de 2023–25, e a volta do pedido 22 está nele.

Tabela completa, em metros. "Dentro" marca os microsetores com pelo menos 50% dos pontos em [p10, p90].

| microsetor | s (m) | IA na faixa | piloto na faixa | chuva na faixa | F1 − IA | F1 − piloto |
|---|---|---|---|---|---|---|
| MS01 | 0 a 72 | 0% | 0% | 59% dentro | +1,54 | +1,25 |
| MS02 | 72 a 144 | 0% | 0% | 58% dentro | +1,86 | +1,69 |
| MS03 | 144 a 217 | 0% | 0% | 89% dentro | +3,01 | +2,46 |
| MS04 | 217 a 289 | 31% | 31% | 89% dentro | +2,34 | +2,24 |
| MS05 | 289 a 361 | 11% | 61% dentro | 100% dentro | −2,94 | −1,83 |
| MS06 | 361 a 433 | 75% dentro | 67% dentro | 92% dentro | −0,26 | −0,39 |
| MS07 | 433 a 506 | 0% | 0% | 100% dentro | −1,98 | −0,73 |
| MS08 | 506 a 578 | 0% | 25% | 56% dentro | −2,28 | −0,41 |
| MS09 | 578 a 650 | 0% | 0% | 35% | −3,06 | −1,15 |
| MS10 | 650 a 722 | 36% | 39% | 92% dentro | −3,34 | −2,45 |
| MS11 | 722 a 795 | 56% dentro | 81% dentro | 100% dentro | +0,13 | −0,58 |
| MS12 | 795 a 867 | 100% dentro | 83% dentro | 100% dentro | −0,66 | +0,01 |
| MS13 | 867 a 939 | 53% dentro | 0% | 100% dentro | +0,13 | +0,72 |
| MS14 | 939 a 1.011 | 0% | 0% | 94% dentro | +1,07 | +0,68 |
| MS15 | 1.011 a 1.084 | 0% | 0% | 100% dentro | +1,71 | +0,61 |
| MS16 | 1.084 a 1.156 | 0% | 0% | 100% dentro | +2,27 | +1,09 |
| MS17 | 1.156 a 1.228 | 0% | 0% | 100% dentro | +2,33 | +2,01 |
| MS18 | 1.228 a 1.300 | 0% | 0% | 100% dentro | +1,83 | +2,14 |
| MS19 | 1.300 a 1.372 | 78% dentro | 75% dentro | 100% dentro | +1,92 | +2,67 |
| MS20 | 1.372 a 1.445 | 67% dentro | 28% | 94% dentro | −0,33 | +1,92 |
| MS21 | 1.445 a 1.517 | 14% | 19% | 97% dentro | +0,48 | +1,36 |
| MS22 | 1.517 a 1.589 | 0% | 100% dentro | 89% dentro | −2,59 | +0,74 |
| MS23 | 1.589 a 1.661 | 44% | 28% | 97% dentro | −2,16 | +0,98 |
| MS24 | 1.661 a 1.734 | 100% dentro | 100% dentro | 100% dentro | +1,09 | +1,23 |
| MS25 | 1.734 a 1.806 | 22% | 44% | 97% dentro | −3,01 | −1,96 |
| MS26 | 1.806 a 1.878 | 0% | 0% | 100% dentro | −4,22 | −3,01 |
| MS27 | 1.878 a 1.950 | 8% | 17% | 86% dentro | −1,83 | −0,83 |
| MS28 | 1.950 a 2.023 | 0% | 0% | 11% | +2,13 | +2,71 |
| MS29 | 2.023 a 2.095 | 44% | 0% | 69% dentro | −0,52 | +3,47 |
| MS30 | 2.095 a 2.167 | 100% dentro | 31% | 50% dentro | −0,01 | +0,89 |
| MS31 | 2.167 a 2.239 | 8% | 11% | 78% dentro | −0,69 | −0,67 |
| MS32 | 2.239 a 2.312 | 36% | 72% dentro | 86% dentro | −1,13 | −1,67 |
| MS33 | 2.312 a 2.384 | 31% | 11% | 64% dentro | +0,06 | −3,14 |
| MS34 | 2.384 a 2.456 | 0% | 42% | 100% dentro | −3,52 | −1,77 |
| MS35 | 2.456 a 2.528 | 0% | 30% | 100% dentro | −2,19 | +3,82 |
| MS36 | 2.528 a 2.600 | 72% dentro | 69% dentro | 94% dentro | −2,19 | −0,62 |
| MS37 | 2.600 a 2.673 | 3% | 31% | 100% dentro | −4,59 | −0,74 |
| MS38 | 2.673 a 2.745 | 75% dentro | 81% dentro | 64% dentro | −1,86 | −2,13 |
| MS39 | 2.745 a 2.817 | 36% | 39% | 81% dentro | −0,44 | −1,02 |
| MS40 | 2.817 a 2.889 | 25% | 31% | 67% dentro | −3,06 | −2,48 |
| MS41 | 2.889 a 2.962 | 0% | 0% | 19% | −2,21 | −1,41 |
| MS42 | 2.962 a 3.034 | 42% | 31% | 33% | +0,94 | −0,10 |
| MS43 | 3.034 a 3.106 | 0% | 0% | 100% dentro | +1,81 | +1,52 |
| MS44 | 3.106 a 3.178 | 0% | 0% | 100% dentro | +3,70 | +2,50 |
| MS45 | 3.178 a 3.251 | 81% dentro | 75% dentro | 47% | +2,09 | +3,16 |
| MS46 | 3.251 a 3.323 | 8% | 0% | 69% dentro | +2,05 | +2,59 |
| MS47 | 3.323 a 3.395 | 6% | 67% dentro | 89% dentro | −2,00 | +0,26 |
| MS48 | 3.395 a 3.467 | 0% | 0% | 72% dentro | −5,00 | +1,14 |
| MS49 | 3.467 a 3.539 | 0% | 33% | 53% dentro | −3,90 | +0,28 |
| MS50 | 3.539 a 3.612 | 0% | 78% dentro | 78% dentro | −1,89 | +0,10 |
| MS51 | 3.612 a 3.684 | 61% dentro | 100% dentro | 69% dentro | +0,02 | +2,37 |
| MS52 | 3.684 a 3.756 | 51% dentro | 51% dentro | 73% dentro | −1,47 | +1,65 |
| MS53 | 3.756 a 3.828 | 100% dentro | 100% dentro | 100% dentro | −0,07 | −0,21 |
| MS54 | 3.828 a 3.901 | 94% dentro | 44% | 100% dentro | −0,07 | +1,44 |
| MS55 | 3.901 a 3.973 | 0% | 42% | 64% dentro | −0,83 | +2,97 |
| MS56 | 3.973 a 4.045 | 0% | 100% dentro | 33% | −1,07 | +2,67 |
| MS57 | 4.045 a 4.117 | 0% | 42% | 89% dentro | −1,68 | +3,10 |
| MS58 | 4.117 a 4.190 | 64% dentro | 0% | 86% dentro | −1,28 | +3,49 |
| MS59 | 4.190 a 4.262 | 28% | 0% | 94% dentro | +0,37 | +1,95 |
| MS60 | 4.262 a 4.334 | 0% | 0% | 19% | +1,36 | +1,40 |

### 7. Figuras

As duas foram copiadas para `docs/handoff/`. O plano das figuras é o X/Z do jogo.

- **`docs/handoff/2026-10-05_23_voltas-secas-f1_faixa_pista.png`**, cópia de `data/ml/externo/f1_faixa/faixa_pista.png`. Mostra:
  - a pista oficial;
  - a faixa p10–p90 sombreada;
  - a mediana da F1, a da IA e a do piloto;
  - zoom no S do Senna (s = 184 a 462 m), no Bico de Pato (2.632 a 2.798 m) e na Junção (3.148 a 3.302 m).
- **`docs/handoff/2026-10-05_23_voltas-secas-f1_faixa_lateral.png`**, cópia de `data/ml/externo/f1_faixa/faixa_lateral.png`. Mostra o lateral × `s` em quatro faixas de pista:
  - a faixa e a mediana da F1;
  - a IA, o piloto e a volta de chuva, tracejada;
  - o corredor;
  - os microsetores pouco confiáveis, sombreados em cinza.

  Na figura, a mediana da F1 corre colada numa borda da faixa, e a volta de chuva fica em cima dela.

### Saídas

Ficam em `data/ml/externo/f1_faixa/`, fora do git, com 5,3 MB:

- `manifesto.json`: 10 sessões e 2.602 voltas, com a etapa do funil de cada uma, e o critério e o veredito das 80 escolhidas;
- `voltas/`: 64 CSVs, com `s`, `lateral` e `excesso_m`;
- `faixa.csv`: `s`, microsetor, p10, p50, p90, `n` e a mediana e o p90 de |V1 − principal| e de |V2 − principal| por ponto;
- `resumo.json` e as duas figuras.

Procurei nas saídas qualquer canal do carro: velocidade, pedais, marcha, rotação, DRS ou distância. Só aparece o campo que lista o que não foi lido.

## Testes

**Novos, 19, todos sintéticos e sem internet:**

- `test_f1_voltas_secas.py` (9 testes):
  - **filtros:** uma volta de cada caso (intermediário, imprecisa, apagada, bandeira amarela, saída do box e chuva), em que só a limpa sobra; a primeira etapa que falha é a que conta; uma volta sem intervalo não passa no filtro de chuva;
  - **escolha:** a melhor volta por piloto e o corte nos 10;
  - **sessão sem `Deleted`:** fica fora, sem nenhuma leitura de posição;
  - **sessão da sprint:** só entra antes de uma corrida "Sprint";
  - **leitura:** só `["X", "Y"]` é pedido aos dados de posição, `get_telemetry` e `get_car_data` nunca são chamados, e só as voltas escolhidas (e a volta à parte) são lidas;
  - **sessão que não carrega:** o erro fica registrado.
- `test_f1_faixa.py` (10 testes):
  - **V1:** recupera rotação e translação conhecidas, com a escala presa e espelho;
  - **V2:** recupera uma transformação conhecida aplicada a três linhas da mesma sessão;
  - **dispersão:** é medida no centróide;
  - **faixa:** p10, p50 e p90 conhecidos (1, 5 e 9 com 11 voltas), a regra de 50% para "dentro", o lado e a distância até a borda;
  - **mínimo:** 20 voltas de 3 sessões;
  - **amplitude entre sessões;**
  - **critério:** cada condição recusa sozinha, e as bordas (0,99, 80 m, 10% e 1 m) passam; o buraco conta o que fecha a volta; uma volta sintética com buraco de 126 m é recusada, e a limpa é aceita.

**Suíte `backend/tests`:** 643 passando, 4 avisos, em 6 min 50 s. Eram 624 no pedido 22; os 19 novos somam 643. Rodei só `tests/`, como nos relatórios anteriores.

Durante o desenvolvimento, só um teste falhou, por um erro do próprio teste: um `NaT` sozinho numa coluna virou data, e não intervalo. Corrigi o teste. O código não mudou.

## Escolhas minhas e o que mudou entre as rodadas

Estas escolhas foram fixadas antes de rodar a coleta real:

1. **Python:** o do `.venv` do projeto (FastF1 3.4.0). O Python global tem o FastF1 3.7.0 e não foi usado.
2. **Uma volta sem início ou fim conhecido cai no filtro de chuva**, porque não dá para conferir. Isso não aconteceu em nenhuma volta.
3. **Uma sessão sem `weather_data` sairia inteira**, como a sem `Deleted`. Também não aconteceu.
4. **A classificatória da sprint só entra se vier antes de uma sessão chamada "Sprint"**: é a conferência pelo nome e pela data.
5. **O maior buraco é medido em metros de `s`**, contando o trecho que fecha a volta, do último ponto ao primeiro. A cobertura é a mesma do pedido 22.
6. **Os "5 mais fora"** são ordenados pela distância mediana até a borda no microsetor.
7. **Partidas dos ajustes:**
   - a V1 parte da rotação e do espelho do método principal, mantendo o centróide no lugar;
   - a V2 parte da transformação da primeira volta da sessão.
8. **A amplitude entre sessões usa todas as sessões com volta aceita.** A menor tem 5 voltas.
9. **A volta de chuva:** o plano não dizia o que fazer se a classificação de 2024 não carregasse. Usei a linha já alinhada do pedido 22 (`fastf1_linha_na_grade.csv`, que veio do `get_telemetry`), com o rótulo no JSON e na figura. É a mesma volta, por outro caminho de leitura. Se a sessão carregar, o script usa a posição crua.

Rodei três vezes:

- **Rodada 1:** os números do relatório.
- **Rodada 2:** depois de ver a faixa assimétrica, acrescentei o diagnóstico por sessão ao `resumo.json`. Também troquei o título da figura da pista, de "Faixa de linhas reais da F1" para "Faixa das linhas da F1 (posição do FastF1)".
- **Rodada 3:** acrescentei a escala relativa ao decímetro, porque com 4 casas a escala em m por unidade aparecia como 0,0998 em todas.

Entre as rodadas, `faixa.csv` e os 64 CSVs por volta ficaram idênticos byte a byte. Nos JSONs, só mudaram `gerado_em`, `commit`, os tempos, o tamanho do cache e os campos novos. O `commit` do `resumo.json` final é `c2a66aff`, o código que o gerou.

## Pontos para o Cowork e decisões do Eduardo

1. **A classificação de 2024: precisa de decisão.** O FastF1 3.4.0 monta o caminho pela data atual do calendário (03/11), e a sessão está publicada em `2024-11-02_Qualifying`. O cache já tem essa pasta, baixada pelo importador do app em junho com a mesma versão.

   A correção seria, só para essa sessão, trocar o `api_path` pelo caminho de 02/11 antes do `load`. A fonte e o cache são os mesmos, sem atualizar pacote. O tempo e as mensagens da direção de prova ainda seriam baixados. Com isso, ficariam completos:
   - o pneu da volta 32;
   - a conferência do item C.2;
   - a volta de chuva com posição crua.

   Não fiz, porque o plano manda registrar o erro e seguir. Cheguei a perguntar no chat, mas a pergunta foi interrompida sem resposta, e segui pela regra do plano.
2. **A posição do FastF1 parece presa a um traçado por época.** Isso mexe na premissa do ADR 0018 de que a F1 dá a "forma da linha": com estes dados, ela daria a forma de um traçado de referência, e não a linha dos pilotos. Algumas leituras possíveis, para o Cowork e o Eduardo:
   - usar só uma época, como 2023–25, e tratar a faixa como uma linha só, sem dispersão real;
   - procurar outra referência que confirme ou negue o "traçado por época";
   - rever se a F1 ainda faz sentido como terceira fonte.

   Não fiz nada disso.
3. **2018 ficou fora pelo nome do composto.** `SUPERSOFT` era pneu seco em 2018. Aceitar os compostos secos da época mudaria o filtro 1. Mesmo assim, as 4 SOFT que passaram dos outros filtros caíram por chuva, e a sessão teve `Rainfall` em 33 dos 78 registros. Talvez 2018 desse poucas voltas de qualquer jeito.
4. **As recusas vêm da amostragem.** São 9 por buraco acima de 80 m e 7 por cobertura abaixo de 0,99. A posição crua tem cerca de 4 amostras por segundo, e buracos de até 108 m.
5. **O excesso fica sempre nos mesmos lugares:** Descida do Lago, Bico de Pato e Junção, como no pedido 22, em 53 a 55 das 64 voltas. Se o traçado é de referência, as três hipóteses do pedido 22 (zebra, borda do jogo e alinhamento) passam a incluir uma quarta: o traçado da F1 nesses pontos.

## O que falta

- **Depende da decisão 1:**
  - o pneu da volta 32 de Norris em 2024;
  - a conferência com o pedido 22 (C.2);
  - a volta de chuva com posição crua.
- **Do resto do pedido, nada falta.** O retreino com as três fontes continua no backlog e espera pedido próprio, junto com as decisões dos pontos 2 e 3.

`docs/handoff/2026-10-05_23_voltas-secas-f1_relatorio.md`
