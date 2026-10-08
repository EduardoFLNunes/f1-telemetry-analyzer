# Relatório do pedido 24: classificação de 2024 pelo caminho publicado e referência única da F1 na época 2023–25 (ADR 0019)

- **Pedido:** `docs/prompts/2026-10-08_24_f1-referencia-2023-25.md`
- **Branch:** `etapa/f1-referencia-2023-25`, com merge em `develop`
- **Commits e merge:**
  - `0646185d` docs: ADR 0019 (F1 como traçado de referência da época 2023-25), índice, ADR 0018, backlog e pedido 24 (Parte A)
  - `c54dfbf0` ML: classificacao de 2024 pelo caminho publicado, so nessa sessao (pedido 24, Parte B)
  - `bcf72920` ML: traçado de referencia unico da F1 na epoca 2023-25, coerencia por sessao e comparacao (pedido 24, Parte C)
  - `01c5cbc2` docs: dados externos da F1 com a decisao do ADR 0019, a classificacao de 2024 e a referencia 2023-25 (pedido 24, Parte D)
  - `5e1bd317` Merge etapa/f1-referencia-2023-25 (pedido 24: classificação de 2024 e referência da F1 2023-25)
  - o commit deste relatório, com o patch, a saída da suíte, os dois resumos JSON e a figura: "Relatório do pedido 24: classificação de 2024 e referência da F1 2023-25"
- **Arquivos de handoff:**
  - `docs/handoff/2026-10-08_24_f1-referencia-2023-25_relatorio.md` (este)
  - `docs/handoff/2026-10-08_24_f1-referencia-2023-25.patch` (de `06681522` até o merge `5e1bd317`; sha256 `8e5a3c65…a97dd20e`)
  - `docs/handoff/2026-10-08_24_f1-referencia-2023-25_testes.txt` (suíte `backend/tests`: 656 passando)
  - `docs/handoff/2026-10-08_24_f1-referencia-2023-25_resumo.json` (cópia de `data/ml/externo/f1_referencia/resumo.json`)
  - `docs/handoff/2026-10-08_24_f1-referencia-2023-25_referencia_lateral.png` (cópia de `data/ml/externo/f1_referencia/referencia_lateral.png`)
  - `docs/handoff/2026-10-08_24_f1-referencia-2023-25_faixa_resumo.json` (cópia de `data/ml/externo/f1_faixa/resumo.json`, da rodada com a classificação de 2024; traz a conferência com o pedido 22 e a volta de chuva com posição crua)

Nada foi enviado ao remoto. O app instalado e os arquivos do jogo não foram tocados. Nenhum pacote foi instalado nem atualizado, e nenhum arquivo do FastF1 foi editado. Nenhum modelo foi treinado, e coach, store e critérios não mudaram.

## Em resumo

1. **A classificação de 2024 carregou pelo caminho publicado.**
   - A volta 32 de Norris foi com pneu `INTERMEDIATE`, em 83,405 s.
   - As 425 voltas da sessão são `WET` ou `INTERMEDIATE`, então nenhuma é seca. Por isso, `faixa.csv` e os 64 CSVs por volta do pedido 23 ficaram **idênticos byte a byte**.
2. **Conferência com o pedido 22:** pela posição crua, a mesma volta dá 2,12% de pontos fora do corredor (antes 2,03%), p95 do excesso de 0 m e rotação de 0,553° (antes 0,552°). O lateral difere 1,9 cm na mediana ponto a ponto.
3. **Volta de chuva com posição crua:** fica dentro da faixa seca em 55 dos 60 microssetores (antes 53) e a 5,5 a 6,9 cm das medianas de 2023–25 (antes 6 cm). Segue a poucos centímetros da linha seca.
4. **A referência da época 2023–25 tem 37 voltas de 5 sessões.** As cinco passam na coerência com folga: mediana de 1,7 a 3,0 cm e p90 de 5,7 a 9,7 cm, contra limites de 10 e 30 cm. A amplitude entre as medianas das sessões tem mediana de 6 cm.
5. **Comparação:** referência − IA tem |Δ| por microssetor com mediana de 1,86 m, e referência − piloto, de 1,53 m. A tabela quase não muda em relação ao pedido 23: a diferença por microssetor tem mediana de 3 cm e máximo de 17 cm.

## Conferência do contexto

| fato do pedido | onde está | bate? |
|---|---|---|
| Pedido 23: 64 voltas secas de 8 sessões e os números do diagnóstico por sessão | relatório 23 e `data/ml/externo/f1_faixa/resumo.json` | sim |
| Erro de 2024: o FastF1 3.4.0 monta o caminho com a data atual (03/11), e a sessão está publicada em `/static/2024/2024-11-03_São_Paulo_Grand_Prix/2024-11-02_Qualifying/` | `fastf1/core.py:1180` e o calendário | sim |
| "O cache já tem essa pasta, baixada em junho pelo importador do app com a mesma versão" | `data/fastf1_cache/2024/…/2024-11-02_Qualifying/` | **em parte.** A pasta existia, com 8 arquivos de 16/06. Mas o FastF1 3.4.0 do `.venv` não aceitou nenhum deles: baixou a sessão inteira de novo e sobrescreveu os arquivos (seção "O que foi baixado"). Ou os arquivos não foram gravados por esta instalação do FastF1 3.4.0, ou não abriram nela. Como foram sobrescritos, não dá mais para saber qual das duas. **Correção do relatório 23:** lá escrevi "com o mesmo FastF1 3.4.0" sem conferir. Não parei, porque nenhum passo dependia de usar os arquivos de junho: a fonte e o caminho são os publicados pela F1 |
| Backlog: "linha **Retreinar a LSTM geradora**, no **Impacto**, troque 'forma da linha da F1'" | `docs/backlog.md`, linha 31 | **em parte.** A expressão não está no Impacto: está na coluna **Item** ("…voltas `ia` rotuladas e forma da linha da F1), testada na régua do ADR 0006"), uma vez só na linha. Troquei onde ela está. O Impacto não mudou |
| Atributo do caminho no FastF1 3.4.0: provavelmente `Session.api_path` | `fastf1/core.py` | sim: `Session.api_path` |

## Parte A: documentação

Commit `0646185d`, junto com o arquivo do pedido.

1. **`docs/decisoes/0019-f1-tracado-de-referencia-2023-25.md`**, com o texto do pedido sem mudança. Conferi com um `diff` contra o bloco do pedido: idêntico.
2. **`docs/decisoes/README.md`:**
   - linha nova: "[0019](0019-f1-tracado-de-referencia-2023-25.md) | A F1 entra no Modelo 1 como um traçado de referência único da época 2023–25 | aceita; refina 0018";
   - status do 0018: "aceita; item 3 refinado por 0019".
3. **ADR 0018:** texto intacto, com uma linha nova no fim: "**Refinado por [0019](0019-f1-tracado-de-referencia-2023-25.md)** (08/10): a F1 entra como traçado de referência único da época 2023–25."
4. **`docs/backlog.md`:**
   - "Dados externos no treino do Modelo 1": o Quando ganhou, no fim, "Pedido 24: referência única da época 2023–25 (ADR 0019); classificação de 2024 pelo caminho publicado";
   - "Retreinar a LSTM geradora com as três fontes": "forma da linha da F1" virou "traçado de referência da F1 na época 2023–25 (ADR 0019)", na coluna Item (ver a conferência do contexto).

## Parte B: classificação de 2024 pelo caminho publicado

### A correção

- **Onde o FastF1 guarda o caminho:** em `Session.api_path`, atribuído em `.venv/Lib/site-packages/fastf1/core.py`, **linha 1180**, com `api.make_path(EventName, EventDate, name, data local da sessão)`. O cache usa o mesmo caminho para montar a pasta (`fastf1/req.py`, **linha 470**: `os.path.join(cls._CACHE_DIR, api_path[8:])`).
- **No nosso código:** em `backend/ml/external/f1_dry_laps.py`, duas funções novas:
  - `published_api_path(year, event_name, session_name)` devolve o caminho de `PUBLISHED_PATHS` só se a chave for exatamente `(2024, "São Paulo Grand Prix", "Qualifying")`;
  - `use_published_path(session, …)` troca o `api_path` da sessão por esse caminho, antes do `load()`, e devolve o caminho anterior. Em qualquer outra sessão, devolve `None` e nada muda.

  O `collect_session` chama `use_published_path` entre o `get_session` e o `load`, e grava no manifesto `caminho_corrigido` (o caminho montado pelo FastF1 e o publicado). Nenhum arquivo do FastF1 foi tocado. Usei o Python do `.venv` (FastF1 3.4.0), como no pedido 23.

### O que foi baixado

O FastF1 3.4.0 só usa um arquivo do cache se ele abre e se a versão gravada nele é a sua (`_API_CORE_VERSION = 13`, `fastf1/req.py`, linhas 221 e 480 a 488). Os 8 arquivos de junho não passaram nessa checagem: o log diz "Updating cache for …" para cada um. Ele baixou tudo de novo pelo caminho publicado:

| arquivo | junho (bytes) | agora (bytes) |
|---|---|---|
| `session_info` | 558 | 558 |
| `driver_info` | 5.381 | 5.381 |
| `session_status_data` | 715 | 715 |
| `track_status_data` | 964 | 964 |
| `_extended_timing_data` | 111.649 | 111.648 |
| `timing_app_data` | 49.713 | 49.526 |
| `car_data` | 28.331.034 | 28.330.761 |
| `position_data` | 26.905.515 | 26.905.242 |
| `weather_data` | — | 7.003 (novo) |
| `race_control_messages` | — | 9.810 (novo) |

- Os arquivos novos estão na versão 13. Os tamanhos quase iguais são compatíveis com os mesmos dados gravados de novo.
- O `car_data` vem junto porque a carga pede `telemetry=True`, como no pedido 23. Nada dele é lido (ADR 0018).
- A carga levou 18,5 s.

| cache | bytes |
|---|---|
| antes deste pedido | 474.895.068 |
| **depois** | **485.581.227 (485,6 MB)** |
| diferença | +10.686.159: 10.670.080 do cache HTTP (`fastf1_http_cache.sqlite`, de 61.558.784 para 72.228.864) e cerca de 16 KB das pastas |

### Resultados

**A sessão carregou.**

| | valor |
|---|---|
| caminho montado pelo FastF1 | `/static/2024/2024-11-03_São_Paulo_Grand_Prix/2024-11-03_Qualifying/` |
| caminho usado | `/static/2024/2024-11-03_São_Paulo_Grand_Prix/2024-11-02_Qualifying/` |
| voltas | 425 |
| pneus | `WET` 263 e `INTERMEDIATE` 162 |
| registros de tempo | 107, sendo 87 com `Rainfall` verdadeiro |
| avisos do FastF1 | só a correção do nome do evento e os do Ergast ("Failed to load result data from Ergast!"), como nas outras sessões |

**Pneu da volta 32 de Norris: `INTERMEDIATE`, tempo de 83,405 s.** O tempo só identifica a volta. Isso confirma o contexto do pedido 23: era uma volta de pista molhada.

**Funil da sessão**, com os mesmos seis filtros e a mesma escolha do pedido 23:

| voltas | pneu seco | `IsAccurate` | não apagada | bandeira verde | sem box | sem chuva | melhores por piloto | escolhidas |
|---|---|---|---|---|---|---|---|---|
| 425 | **0** | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Não sobrou nenhuma volta seca, então não há o que alinhar nem julgar pelo critério.

**Mensagens de volta apagada.** Há 35 mensagens com "DELETED", e o FastF1 marcou 28 voltas como apagadas. Conferi a diferença:

- 29 mensagens casam com o padrão do FastF1 ("CAR n … TIME m:ss.sss DELETED - …"). Elas dão 28 pares carro/tempo, porque uma se repete.
- 6 vêm no formato "CAR n (XXX) LAP DELETED - …", sem tempo de volta, e o padrão do FastF1 3.4.0 não as reconhece. Uma é por bandeira amarela dupla e cinco por limite de pista, com "(PIT)".

Nada disso muda o resultado aqui, porque todas as voltas caem pelo pneu. Nas sessões do pedido 23, o número de mensagens "DELETED" era igual ao de voltas marcadas. Em sessões futuras, uma volta apagada nesse formato passaria pelo filtro 3: fica registrado.

**Conferência com o pedido 22** (`conference_with_p22`, sem mudança). A mesma volta 32, agora com os dados de posição crus (307 amostras), no lugar da leitura do `get_telemetry` (633 amostras):

| | pedido 22 | caminho novo (posição crua) |
|---|---|---|
| fração fora do corredor | 2,03% | 2,12% |
| p95 do excesso | 0 m | 0 m |
| escala | 0,0998 m por unidade (0,9981 do decímetro) | 0,0998 m por unidade (0,9981 do decímetro) |
| rotação | 0,552° | 0,553° |
| espelho | sim | sim |

| diferença de lateral ponto a ponto (2.167 pontos) | valor |
|---|---|
| mediana | 0,019 m |
| p95 | 0,213 m |
| máximo | 1,009 m |

Pelo critério por volta do pedido 23, a volta crua passaria: cobertura de 0,994, maior buraco de 60,8 m, 2,12% fora e p95 de 0 m. Ela continua fora da faixa por ser volta de chuva.

**Volta de chuva com posição crua** (item 6 do pedido 23, só para ela):

| | pedido 23 (linha do pedido 22) | pedido 24 (posição crua) |
|---|---|---|
| microssetores dentro da faixa seca | 53 de 60 | **55 de 60** |
| pontos dentro | 79,7% | 85,6% |
| microssetores fora | MS09, MS28, MS41, MS42, MS45, MS56 e MS60 | MS02, MS28, MS41, MS42 e MS60 |
| maior distância mediana até a borda | 0,13 m (MS28) | 0,09 m (MS28) |
| \|chuva − mediana da Sprint Qualifying 2024\|, mediana | 0,06 m | 0,057 m |
| \|chuva − mediana de cada sessão de 2023–25\|, mediana | 0,06 a 0,08 m | 0,055 a 0,069 m |

Com a posição crua, a volta de chuva fica ainda mais perto da linha seca. Os 5 microssetores "mais fora" ficam a no máximo 9 cm da borda: MS28 (−0,09, direita), MS41 (+0,07), MS42 (+0,05), MS60 (−0,01) e MS45 (+0,01, com 50% dentro). A hipótese da chuva continua sem poder ser medida (ADR 0019, consequências).

### `faixa.csv` e os CSVs por volta

Rodei de novo o `faixa_f1_secas` com a correção (o `commit` do resumo é `c54dfbf0`):

- **`faixa.csv`: idêntico byte a byte** ao do pedido 23;
- **os 64 CSVs de `voltas/`: idênticos byte a byte.**

É o esperado, porque a classificação de 2024 não tem volta seca aceita. No `resumo.json` da faixa mudaram só a sessão de 2024 (agora carregada), a conferência, a volta de chuva (agora com posição crua), o diagnóstico da volta de chuva, os tempos, o tamanho do cache e o commit. A cópia está em `docs/handoff/2026-10-08_24_f1-referencia-2023-25_faixa_resumo.json`.

## Parte C: referência única da época 2023–25

### O que foi feito

| arquivo | o que é |
|---|---|
| `backend/ml/external/f1_reference.py` (novo) | seleção da época (`era_laps`), coerência por sessão (`coherence`, `coherence_verdict`), referência (`reference_line`), amplitude entre sessões e marca de pouco confiável |
| `backend/ml/scripts/referencia_f1.py` (novo) | roda a Parte C a partir das saídas do `faixa_f1_secas`, sem FastF1 e sem rede, e grava em `data/ml/externo/f1_referencia/` |
| `backend/tests/test_f1_referencia.py` (novo, 11 testes) | seleção, referência, amplitude, marca e coerência |
| `backend/tests/test_f1_voltas_secas.py` (2 testes novos) | caminho de 2024 |

Comando: `python -m ml.scripts.referencia_f1`, a partir de `backend/`, com o Python do `.venv`.

Antes de usar, o script confere:

- a geometria `0ed16f0dd2225990` e o store v2 aprovado;
- que cada grade por volta tem os 2.167 pontos da geometria;
- que as voltas `ia` e `humano` do store são as mesmas do pedido 23 (13 e 18). Todas batem.

### 1. Voltas da época

Entram as voltas escolhidas e aceitas pelo critério do pedido 23, dos anos 2023, 2024 e 2025. A volta registrada à parte (a de chuva) nunca entra, mesmo com o alinhamento aceito. 2019, 2021 e 2022 ficam fora. **São 37 candidatas, de 5 sessões.** A classificação de 2024 não tem nenhuma.

### 2. Coerência da época

Os limites foram fixados no pedido, antes de rodar: |mediana da sessão − referência sem ela| com mediana ≤ 0,10 m e p90 ≤ 0,30 m.

A "referência sem ela" é a mediana por ponto das voltas de todas as outras sessões candidatas. É uma passada só, com cada sessão contra as outras quatro. Essa regra de uma passada é minha: o pedido não dizia se a sessão recusada saía antes de medir as outras. Como nenhuma saiu, não faz diferença.

| sessão | voltas | voltas das outras | mediana | p90 | máximo | entra? |
|---|---|---|---|---|---|---|
| 2023 Q | 7 | 30 | 0,019 m | 0,060 m | 0,357 m | sim |
| 2023 Sprint Shootout | 9 | 28 | 0,017 m | 0,057 m | 0,263 m | sim |
| 2024 Sprint Qualifying | 8 | 29 | 0,018 m | 0,058 m | 0,267 m | sim |
| 2025 Sprint Qualifying | 5 | 32 | 0,030 m | 0,097 m | 0,414 m | sim |
| 2025 Q | 8 | 29 | 0,019 m | 0,061 m | 0,265 m | sim |

Nenhuma sessão ficou fora.

### 3. A referência

**37 voltas de 5 sessões**, mediana por ponto com cada volta pesando igual:

| sessão | voltas (piloto e número) |
|---|---|
| 2023 Q | SAI 14, RUS 14, ALO 14, VER 11, PER 13, NOR 9, PIA 8 |
| 2023 Sprint Shootout | VER 15, PER 15, LEC 14, TSU 11, RIC 10, HAM 13, SAI 12, RUS 13, PIA 13 |
| 2024 Sprint Qualifying | RUS 14, BEA 8, ALB 8, LEC 17, SAI 14, GAS 11, LAW 7, VER 11 |
| 2025 Sprint Qualifying | VER 14, NOR 19, HAD 8, ANT 12, HUL 8 |
| 2025 Q | NOR 20, PIA 10, RUS 8, GAS 14, HAD 20, ANT 15, LAW 11, BEA 10 |

| medida | valor |
|---|---|
| `n` de voltas e de sessões em cada ponto | 37 e 5, em todos os pontos (toda volta aceita cobre a grade inteira) |
| lateral da referência | de −7,21 m a +8,76 m; média −0,20 m |
| amplitude entre as medianas das 5 sessões, por ponto | mediana 0,06 m, p90 0,15 m, máximo 0,51 m |
| \|referência − mediana da faixa do pedido 23\| | mediana 0,02 m, p90 0,10 m, máximo 0,34 m |
| microssetores pouco confiáveis, herdados da V1 do pedido 23 | MS04 a MS09, MS19 e MS46 a MS48 (10) |

A marca de pouco confiável é lida da lista `incerteza.microsetores_pouco_confiaveis` do resumo da faixa, que não mudou na rodada da Parte B.

`data/ml/externo/f1_referencia/referencia_2023_25.csv` tem 2.167 linhas, com as colunas `s`, `microsetor`, `lateral`, `n_voltas`, `n_sessoes`, `amplitude_entre_sessoes_m` e `pouco_confiavel`. Nenhum canal da F1 além do lateral, vindo de `X` e `Y`.

### 4. Comparação, só para leitura

A diferença é a referência menos a mediana das voltas, por ponto, reduzida por microssetor pela mediana. Positivo quer dizer F1 mais à esquerda. As voltas são as mesmas do pedido 23: 13 `ia` rotuladas de 04/10 e 18 `humano` com equipamento `atual`.

| | mediana de \|Δ\| por microssetor | p90 | máximo |
|---|---|---|---|
| referência − mediana da IA | 1,86 m | 3,34 m | 5,06 m (MS48, 3.395 a 3.467 m) |
| referência − mediana do piloto | 1,53 m | 3,08 m | 3,82 m (MS35, 2.456 a 2.528 m) |
| *pedido 23:* mediana da faixa − IA | 1,85 m | 3,36 m | 5,00 m (MS48) |
| *pedido 23:* mediana da faixa − piloto | 1,48 m | 3,02 m | 3,82 m (MS35) |

**Contra o pedido 23**, por microssetor:

- |nova − antiga| para a IA: mediana 0,026 m, p90 0,082 m, máximo 0,166 m (MS45);
- para o piloto: mediana 0,026 m, p90 0,081 m, máximo 0,175 m (MS45).

A referência e a mediana da faixa quase coincidem, porque 37 das 64 voltas da faixa já eram de 2023–25. A maior mudança fica na Junção (MS45).

Tabela completa, em metros. "Pouco confiável" é a marca herdada da V1.

| microssetor | s (m) | referência (lateral) | amplitude entre sessões | pouco confiável | ref − IA | 23: F1 − IA | ref − piloto | 23: F1 − piloto |
|---|---|---|---|---|---|---|---|---|
| MS01 | 0 a 72 | −4,63 | 0,04 |  | +1,50 | +1,54 | +1,22 | +1,25 |
| MS02 | 72 a 144 | −4,46 | 0,06 |  | +1,80 | +1,86 | +1,63 | +1,69 |
| MS03 | 144 a 217 | −3,03 | 0,04 |  | +2,93 | +3,01 | +2,38 | +2,46 |
| MS04 | 217 a 289 | +1,54 | 0,06 | sim | +2,32 | +2,34 | +2,22 | +2,24 |
| MS05 | 289 a 361 | +0,23 | 0,06 | sim | −2,95 | −2,94 | −1,86 | −1,83 |
| MS06 | 361 a 433 | −4,00 | 0,14 | sim | −0,23 | −0,26 | −0,35 | −0,39 |
| MS07 | 433 a 506 | +4,65 | 0,05 | sim | −1,93 | −1,98 | −0,71 | −0,73 |
| MS08 | 506 a 578 | +4,17 | 0,04 | sim | −2,24 | −2,28 | −0,39 | −0,41 |
| MS09 | 578 a 650 | +2,17 | 0,04 | sim | −2,98 | −3,06 | −1,07 | −1,15 |
| MS10 | 650 a 722 | −2,42 | 0,07 |  | −3,32 | −3,34 | −2,40 | −2,45 |
| MS11 | 722 a 795 | −4,48 | 0,05 |  | +0,15 | +0,13 | −0,57 | −0,58 |
| MS12 | 795 a 867 | −1,63 | 0,05 |  | −0,65 | −0,66 | +0,02 | +0,01 |
| MS13 | 867 a 939 | +0,33 | 0,04 |  | +0,14 | +0,13 | +0,74 | +0,72 |
| MS14 | 939 a 1.011 | −1,40 | 0,13 |  | +1,10 | +1,07 | +0,71 | +0,68 |
| MS15 | 1.011 a 1.084 | −1,14 | 0,03 |  | +1,72 | +1,71 | +0,62 | +0,61 |
| MS16 | 1.084 a 1.156 | −0,97 | 0,03 |  | +2,27 | +2,27 | +1,09 | +1,09 |
| MS17 | 1.156 a 1.228 | −0,80 | 0,03 |  | +2,34 | +2,33 | +2,02 | +2,01 |
| MS18 | 1.228 a 1.300 | −1,10 | 0,05 |  | +1,85 | +1,83 | +2,16 | +2,14 |
| MS19 | 1.300 a 1.372 | +6,20 | 0,14 | sim | +1,93 | +1,92 | +2,66 | +2,67 |
| MS20 | 1.372 a 1.445 | −2,70 | 0,11 |  | −0,37 | −0,33 | +1,89 | +1,92 |
| MS21 | 1.445 a 1.517 | −1,13 | 0,07 |  | +0,36 | +0,48 | +1,28 | +1,36 |
| MS22 | 1.517 a 1.589 | +2,84 | 0,06 |  | −2,60 | −2,59 | +0,73 | +0,74 |
| MS23 | 1.589 a 1.661 | −1,08 | 0,06 |  | −2,16 | −2,16 | +0,99 | +0,98 |
| MS24 | 1.661 a 1.734 | −1,21 | 0,03 |  | +1,10 | +1,09 | +1,24 | +1,23 |
| MS25 | 1.734 a 1.806 | −1,19 | 0,04 |  | −3,07 | −3,01 | −2,02 | −1,96 |
| MS26 | 1.806 a 1.878 | +0,76 | 0,03 |  | −4,25 | −4,22 | −3,02 | −3,01 |
| MS27 | 1.878 a 1.950 | +2,20 | 0,09 |  | −1,86 | −1,83 | −0,86 | −0,83 |
| MS28 | 1.950 a 2.023 | −0,90 | 0,09 |  | +2,05 | +2,13 | +2,63 | +2,71 |
| MS29 | 2.023 a 2.095 | +0,96 | 0,07 |  | −0,51 | −0,52 | +3,48 | +3,47 |
| MS30 | 2.095 a 2.167 | −0,89 | 0,12 |  | +0,03 | −0,01 | +0,88 | +0,89 |
| MS31 | 2.167 a 2.239 | +3,62 | 0,07 |  | −0,64 | −0,69 | −0,61 | −0,67 |
| MS32 | 2.239 a 2.312 | −5,35 | 0,05 |  | −1,12 | −1,13 | −1,67 | −1,67 |
| MS33 | 2.312 a 2.384 | +0,41 | 0,06 |  | +0,02 | +0,06 | −3,16 | −3,14 |
| MS34 | 2.384 a 2.456 | +2,30 | 0,08 |  | −3,54 | −3,52 | −1,79 | −1,77 |
| MS35 | 2.456 a 2.528 | +2,49 | 0,09 |  | −2,18 | −2,19 | +3,82 | +3,82 |
| MS36 | 2.528 a 2.600 | −3,60 | 0,06 |  | −2,18 | −2,19 | −0,60 | −0,62 |
| MS37 | 2.600 a 2.673 | −1,07 | 0,06 |  | −4,49 | −4,59 | −0,68 | −0,74 |
| MS38 | 2.673 a 2.745 | −6,44 | 0,07 |  | −1,87 | −1,86 | −2,14 | −2,13 |
| MS39 | 2.745 a 2.817 | +0,45 | 0,06 |  | −0,48 | −0,44 | −1,04 | −1,02 |
| MS40 | 2.817 a 2.889 | −1,74 | 0,07 |  | −3,10 | −3,06 | −2,52 | −2,48 |
| MS41 | 2.889 a 2.962 | +4,34 | 0,06 |  | −2,16 | −2,21 | −1,35 | −1,41 |
| MS42 | 2.962 a 3.034 | +2,02 | 0,10 |  | +1,04 | +0,94 | +0,01 | −0,10 |
| MS43 | 3.034 a 3.106 | −2,99 | 0,12 |  | +1,83 | +1,81 | +1,53 | +1,52 |
| MS44 | 3.106 a 3.178 | −1,03 | 0,11 |  | +3,72 | +3,70 | +2,51 | +2,50 |
| MS45 | 3.178 a 3.251 | +6,60 | 0,16 |  | +2,26 | +2,09 | +3,34 | +3,16 |
| MS46 | 3.251 a 3.323 | −0,92 | 0,07 | sim | +2,01 | +2,05 | +2,57 | +2,59 |
| MS47 | 3.323 a 3.395 | +1,08 | 0,11 | sim | −2,02 | −2,00 | +0,23 | +0,26 |
| MS48 | 3.395 a 3.467 | −1,79 | 0,05 | sim | −5,06 | −5,00 | +1,09 | +1,14 |
| MS49 | 3.467 a 3.539 | −2,09 | 0,05 |  | −3,97 | −3,90 | +0,21 | +0,28 |
| MS50 | 3.539 a 3.612 | +3,23 | 0,06 |  | −1,90 | −1,89 | +0,09 | +0,10 |
| MS51 | 3.612 a 3.684 | +5,55 | 0,08 |  | +0,05 | +0,02 | +2,41 | +2,37 |
| MS52 | 3.684 a 3.756 | −2,58 | 0,05 |  | −1,45 | −1,47 | +1,70 | +1,65 |
| MS53 | 3.756 a 3.828 | −5,08 | 0,04 |  | −0,06 | −0,07 | −0,20 | −0,21 |
| MS54 | 3.828 a 3.901 | −3,64 | 0,17 |  | −0,03 | −0,07 | +1,53 | +1,44 |
| MS55 | 3.901 a 3.973 | +3,49 | 0,08 |  | −0,72 | −0,83 | +3,08 | +2,97 |
| MS56 | 3.973 a 4.045 | +7,29 | 0,13 |  | −0,95 | −1,07 | +2,79 | +2,67 |
| MS57 | 4.045 a 4.117 | +3,58 | 0,06 |  | −1,69 | −1,68 | +3,08 | +3,10 |
| MS58 | 4.117 a 4.190 | −1,47 | 0,07 |  | −1,33 | −1,28 | +3,43 | +3,49 |
| MS59 | 4.190 a 4.262 | −3,46 | 0,04 |  | +0,34 | +0,37 | +1,92 | +1,95 |
| MS60 | 4.262 a 4.334 | −4,36 | 0,05 |  | +1,33 | +1,36 | +1,37 | +1,40 |

As colunas "referência" e "amplitude" são a mediana, no microssetor, dos valores por ponto.

### 5. Figura

**`docs/handoff/2026-10-08_24_f1-referencia-2023-25_referencia_lateral.png`**, cópia de `data/ml/externo/f1_referencia/referencia_lateral.png`. Ela mostra o lateral × `s` em quatro faixas de pista, com:

- a referência da F1 (laranja);
- a mediana da IA (azul) e a do piloto (verde);
- o corredor tracejado;
- os 10 microssetores pouco confiáveis sombreados em cinza.

### Saídas

Ficam em `data/ml/externo/f1_referencia/`, fora do git, com 548 KB: `referencia_2023_25.csv`, `resumo.json` e `referencia_lateral.png`.

O `resumo.json` traz:

- o commit (`bcf72920`) e o commit da faixa que ele leu (`c54dfbf0`);
- a geometria;
- as sessões e as 37 voltas usadas;
- a coerência por sessão;
- a comparação, com a tabela por microssetor e o confronto com o pedido 23.

## Parte D: documento da F1

Em `docs/dados_externos_f1.md` (commit `01c5cbc2`):

- **cabeçalho:** links para o ADR 0019 e para este relatório;
- **seção nova "Decisão (ADR 0019)":** a referência única da época 2023–25, o que fica fora (2019, 2021–22, 2018 e a volta de chuva) e por quê;
- **"Fonte, sessões e anos":** o código novo, a saída nova e a correção do caminho de 2024;
- **seção nova "Classificação de 2024 (pedido 24)":** o novo download, os pneus, a volta 32, a conferência com o pedido 22, a volta de chuva com posição crua e as mensagens "LAP DELETED";
- **seção nova "Referência da época 2023–25 (pedido 24)":** as voltas, as sessões, a coerência por sessão e a comparação com a IA e o piloto;
- **duas frases atualizadas:** a do funil (a classificação de 2024 agora carregou, sem volta seca) e a dos limites (o pneu da volta de chuva, agora conferido).

## Testes

**13 novos, sintéticos e sem internet:**

- **caminho de 2024** (`test_f1_voltas_secas.py`, 2 testes):
  - a troca só acontece em `(2024, "São Paulo Grand Prix", "Qualifying")`. A Sprint Qualifying de 2024, a classificação de 2023 e de 2025, o "Brazilian Grand Prix" e a corrida sprint não mudam;
  - pelo `collect_session` com o FastF1 falso, a classificação de 2024 carrega pelo caminho publicado e registra o caminho anterior, e a Sprint Qualifying de 2024 carrega pelo caminho de sempre.
- **referência** (`test_f1_referencia.py`, 11 testes):
  - **seleção da época:** só 2023 a 2025 entram; 2019, 2021, 2022, a volta de chuva, a volta recusada e a não escolhida ficam fora, e a volta de chuva fica fora mesmo com o alinhamento aceito;
  - **referência:** a mediana por ponto com valores conhecidos; cada volta pesa igual (3 voltas em 0 e 1 em 10 dão 0); a amplitude entre sessões; a marca de pouco confiável lida dos rótulos;
  - **coerência:** as bordas (0,10 m e 0,30 m) passam; a mediana acima recusa sozinha; o p90 acima recusa sozinho; uma sessão sem outras na época fica fora.

Durante o desenvolvimento, um teste novo falhou por um erro do próprio teste: com o tempo seco do falso, mais uma volta era escolhida, e ela não tinha posição falsa. Corrigi o teste. O código não mudou.

**Suíte `backend/tests`:** 656 passando, 4 avisos, em 7 min 24 s. Eram 643 no pedido 23; os 13 novos somam 656. Rodei só `tests/`, como nos relatórios anteriores.

## Escolhas minhas

1. **A chave da correção** é exata: ano 2024, `EventName` igual a "São Paulo Grand Prix" (com o "ã" composto, como o FastF1 grava) e sessão "Qualifying". O caminho fica numa tabela (`PUBLISHED_PATHS`) com uma entrada só.
2. **A coerência é de uma passada**, com cada sessão contra todas as outras candidatas. Nenhuma sessão saiu, então a escolha não mudou o resultado.
3. **A Parte C lê as saídas do `faixa_f1_secas`**, e não o FastF1. A referência depende do veredito por volta do pedido 23, e assim usa exatamente as mesmas grades.
4. **A marca de pouco confiável é lida do resumo da faixa**, e não recalculada.
5. **Copiei também o `resumo.json` da faixa para o handoff.** É nele que estão os resultados da classificação de 2024.

## Pontos para o Cowork e decisões do Eduardo

Nada disto bloqueou o pedido.

1. **"LAP DELETED" sem tempo de volta.** O FastF1 3.4.0 não reconhece esse formato, e uma volta apagada assim passaria pelo filtro 3. Nas sessões usadas hoje, isso não aconteceu: as contagens batiam no pedido 23, e em 2024 tudo cai pelo pneu. Vale lembrar se entrarem sessões novas.
2. **O cache de junho não era utilizável pelo FastF1 3.4.0** e foi sobrescrito. A frase do relatório 23 sobre a "mesma versão" estava errada. O cache tem agora 485,6 MB.
3. **Os 10 microssetores pouco confiáveis seguem marcados na referência** (ADR 0019, item 7). Como tratá-los fica para o pedido do retreino.

## O que falta

Nada deste pedido. O retreino da LSTM geradora com as três fontes continua no backlog, com a referência da época 2023–25 como fonte externa.

`docs/handoff/2026-10-08_24_f1-referencia-2023-25_relatorio.md`
