# Origem e confiabilidade das voltas (pedido 12, ADR 0014)

Data: 2026-10-03 e 04. Branch: `etapa/origem-das-voltas`.

> **Nota de 05/10/2026 sobre os JSONs deste pedido (pedidos 19 e 20).** Os campos abaixo são o `duration_s` do inventário, e não o tempo de volta:
>
> - em `docs/handoff/2026-10-04_origem-das-voltas_resultados.json`: o `lap_time_s` de `item5_inventario` e o de `best_lap`, e os campos `sessoes[].melhor_volta_s` e `tempo_volta_mediana_s`;
> - os resumos `data/ml/origem/lap_inventory_summary.json`.
>
> O resumo do inventário publicava esse valor com o nome `lap_time_s`, o que foi corrigido no pedido 20. Os JSONs ficam como foram gravados. Os tempos oficiais estão no store v2 (`lap_time_s`).

O objetivo desta etapa é saber, volta a volta, **quem pilotou** (o Eduardo ou a IA do Assetto Corsa) e **se o tempo da volta merece confiança**. Nenhum modelo foi treinado. O store do ML e os resultados antigos não foram refeitos.

## 1. As duas pastas de gravações

O app grava em dois lugares, conforme o jeito como é aberto:

- **repositório:** `data/recordings`, quando o app roda a partir do código. É a única pasta que o ML lia até hoje.
- **app instalado:** `%APPDATA%\Automobilista Telemetria\data\recordings`. O ML nunca leu esta pasta.

As duas pastas foram só lidas: nada foi copiado, movido ou apagado nelas. Cada arquivo de cada sessão passou por um hash SHA-256, num total de 179 sessões, em 34 s.

| | repositório | app instalado |
|---|---:|---:|
| sessões (diretórios) | 89 | 90 |
| sessões de Interlagos com gravação não vazia | 54 | 71 |
| mesmo id nas duas pastas | 0 | 0 |
| mesmo id **e** mesmo conteúdo (hash) | 0 | 0 |
| mesmo `player.jsonl` com outro id | 0 | 0 |
| só nesta pasta | 89 | 90 |

**Nenhuma sessão está nas duas pastas.** São 125 sessões de Interlagos diferentes, num total de 5.488.618 amostras dentro de voltas.

**Mas há voltas gravadas duas vezes.** O hash não pega este caso, porque cada cópia tem um id próprio. Em alguns momentos havia dois backends abertos ao mesmo tempo, e os dois gravaram os mesmos instantes:

| sessão | outra sessão | tempo em comum | o que se vê |
|---|---|---:|---|
| repo `2026-06-14_11-30-32` | app `2026-06-14_11-29-22` | 13 s | mesma volta do jogo (56), mesma posição (distância mediana 0,00 m) |
| repo `2026-08-09_19-10-41` | app `2026-08-09_18-47-11` | 285 s | voltas 363 a 367, distância mediana 0,00 m |
| repo `2026-08-09_19-15-35` | app `2026-08-09_18-47-11` | 193 s | voltas 367 a 369, distância mediana 0,00 m |
| repo `2026-06-01_15-05-10` | repo `18-08-50`, `18-26-01`, `18-36-55` | 166 a 2249 s | mesmas voltas (192 a 217), distância mediana de 0,7 a 1,3 m (as amostras não caem no mesmo instante) |

A deduplicação é feita por volta, com a coluna `duplicada_de`. Duas voltas de sessões diferentes contam como a mesma quando se sobrepõem em mais de 50 % do tempo de relógio da mais curta e o número da volta do jogo difere no máximo em 1. Fica a cópia com mais amostras; se empatar, fica a da sessão de nome menor. **Resultado: 45 voltas duplicadas, das quais 4 válidas.** As 4 válidas estão na sessão `2026-08-09_18-47-11` (app), e as cópias mantidas estão no repositório. Nenhuma das 122 voltas do store em uso é duplicada.

## 2. As gravações já dizem quem pilotou?

**O jogo publica o campo, mas as gravações não o têm.**

- **No jogo:** a página de física da memória compartilhada do Assetto Corsa tem `isAIControlled`. O struct do projeto já o lê (`backend/core/assetto_adapter.py:75`, `("isAIControlled", c_int)`), na posição certa: os campos vizinhos, temperatura dos pneus antes e ponto de contato depois, têm valores plausíveis no dump de 2026-05-17 (`data/debug/ac_shared_memory_full_inventory.csv:57`). Nesse dump o valor era 1. Não sei se a IA estava no volante naquele momento, e a gravação curta alternando IA e piloto vai mostrar.
- **Nas gravações:** o adaptador lia o campo e o descartava. Em nenhuma das 125 sessões ele aparece, com qualquer nome (`isAIControlled`, `AIControlled`, `aiControlled`, `ai_controlled`, `isAI`, `"ai"`). Foram 5.488.623 linhas lidas byte a byte nas duas pastas. Os blocos `availability` e `inferred` também não trazem nenhum indicador equivalente. As únicas chaves parecidas eram `airDensity` e `airTemp`.
- **Por sessão:** em todas as 125 o campo **não existe**, e a fração de amostras da IA é **indefinida**. A tabela por sessão está no JSON da entrega (`sessoes[].campo_ia_existe`, `amostras_com_campo_ia`, `fracao_amostras_ia`).

Por isso **todas as 1.899 voltas antigas ficam `desconhecida`**.

## 3. O que mudou no gravador

A mudança é mínima, e o caminho é o mesmo que o pedal e o volante já seguem:

| arquivo | mudança |
|---|---|
| `core/assetto_adapter.py` | publica `is_ai_controlled = bool(physics.isAIControlled)` em toda leitura |
| `core/telemetry/telemetry_reader_impl.py` | leva o campo até a amostra |
| `core/telemetry/telemetry_models.py` | `TelemetrySample.isAIControlled` (None quando a fonte não diz) |
| `core/car_physics.py` | grava `carPhysics.controls.isAIControlled` em toda amostra |
| `main.py` | `metadata.json` da sessão ganha `carModel` (página estática) |
| `core/telemetry/channels.py` | `ai_controlled(sample)`: True, False ou None. None quer dizer "não registrado", nunca "o piloto" |
| `ml/data/samples.py` | coluna `ai_controlled` |

Os testes estão em `tests/test_lap_origin.py`, classes `RecorderTests` e `ChannelTests`.

**Atenção:** o app instalado só passa a gravar o campo depois de ser reempacotado e reinstalado. Até lá, a gravação de teste tem que ser feita com o app aberto a partir do repositório (`develop`), e ela vai para `data/recordings`. Também falta conferir, numa gravação real, se `carModel` já está preenchido quando a gravação começa. O valor vem da página estática, lida junto com a primeira amostra.

## 4. Relógio plausível

### Como é medido

Para cada volta válida, na grade de 2 m e nos 60 microsetores do ML:

- **pelo relógio:** é o tempo do microsetor dado pelo cronômetro gravado (`elapsed_s`, o mesmo que dá o tempo da volta).
- **pela velocidade:** é a soma, passo a passo da grade, de *comprimento do passo / velocidade média no passo*. O comprimento do passo segue a trajetória do carro, não a centerline (`trajectory.step_lengths`). Assim, a linha por fora de uma curva não aparece como erro.
- **a diferença:** relógio − velocidade, por microsetor. As duas medidas usam as mesmas fronteiras (`split_times`).

Uma diferença grande quer dizer que o relógio e a distância percorrida não contam a mesma história: o relógio pulou, a posição saltou, ou o carro andou por fora da grade.

### Distribuição medida (antes de escolher o limite)

Foram 688 voltas válidas e únicas das duas pastas, ou seja, 41.280 microsetores.

| | p1 | p5 | p50 | p95 | p99 | p99,9 | máx |
|---|---:|---:|---:|---:|---:|---:|---:|
| diferença (s) | −0,035 | −0,025 | −0,009 | −0,005 | +0,007 | +0,750 | +23,75 |
| \|diferença\| (s) | 0,004 | 0,005 | 0,009 | 0,026 | 0,042 | 0,750 | 23,75 |
| pior \|diferença\| da volta (s) | 0,032 | 0,033 | 0,034 | 0,758 | 1,480 | 8,47 | 23,75 |

- **Viés fixo:** a velocidade explica cerca de 9 ms a mais que o relógio, em quase todos os microsetores.
- **Microsetor 0 (linha de chegada):** tem um viés próprio de −0,034 s, igual em todas as voltas. É o fechamento da volta na grade, e o pedido 11 viu o mesmo efeito no coach.
- **Os outros microsetores:** fora o 0, o 3 (saída do box) e o 59 (entrada do box), a \|diferença\| tem p99 de 0,028 s e p99,9 de 0,068 s.

Voltas cuja pior \|diferença\| passa de cada valor:

| limite (s) | 0,02 | 0,03 | 0,05 | 0,075 | 0,10 | 0,15 | 0,20 | 0,30 | 0,50 | 1,0 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| voltas | 688 | 686 | 159 | 148 | 144 | 143 | 141 | 123 | 69 | 17 |

O corpo da distribuição acaba perto de 0,05 s. Entre 0,05 e 0,1 s ficam só 15 voltas, quase todas com o microsetor 0 entre −0,05 e −0,08 s e tempo de volta normal (85,6 a 86,6 s). De 0,1 a 0,2 s o número quase não muda (144 → 141).

### Limite proposto, registrado antes de aplicar

**`relogio_suspeito` = alguma \|diferença\| de microsetor maior que 0,10 s.**

Os motivos:

- 0,10 s é 1,5 vez o p99,9 dos microsetores normais (0,068 s) e 3 vezes o viés do microsetor 0 (0,034 s);
- o limite cai no platô da distribuição, então mexer nele um pouco para cima ou para baixo quase não muda quais voltas são marcadas;
- as 15 voltas da zona cinza (0,05 a 0,1 s) têm tempo normal e ficam sem a marca.

O limite está em `ml/data/origin.py` (`CLOCK_LIMIT_S = 0.10`) e é aplicado com `python -m ml.scripts.report_lap_origin --remarcar`. Voltas não válidas não têm o relógio conferido (`relogio_verificado = False`), e o filtro padrão também as deixa de fora.

### O que o limite marca

Aplicado depois do commit acima (`15b0e268`), o limite marcou **144 das 688 voltas válidas e únicas**. Na maioria delas o problema não é o relógio:

| tipo | voltas | como aparece |
|---|---:|---|
| passagem pelo box | 135 | volta de entrada (≈ 101,7 s): o carro sai da pista no microsetor 0, com lateral de até 30 m, e faz o microsetor 3 a 18–74 km/h, dando +1,5 s nele. Volta de saída (≈ 93 s): começa dentro do box a 80 km/h, dando −0,4 a −0,7 s no microsetor 0 |
| parada ou rodada no meio da volta | 3 | todas em `2026-08-19_20-58-36`. O relógio tem até 23,75 s a mais que a velocidade explica (microsetor 29) |
| tempo a menos no meio da volta | 6 | o relógio anda menos do que a distância exige, por exemplo −0,48 s nos microsetores 29 a 31 de `2026-06-14_10-15-25#0010`. As outras são `2026-06-14_10-15-25#0007`, `2026-06-14_11-45-28#0009`, `2026-08-08_16-38-27#0003`, `#0004` e `2026-08-19_21-45-59#0001`. São os casos de relógio ou posição que saltou de verdade |

Assim, a marca separa toda volta em que o tempo de algum microsetor não vem de o carro percorrer a pista. Isso inclui passar pelo box, parar ou ter um salto. Os portões de qualidade do ML deixavam passar as voltas de box como "válidas". **No store em uso (122 voltas), 21 receberiam a marca**, todas passagens pelo box: 11 voltas de saída (92,9 a 96,5 s) e 10 voltas de entrada (101,6 a 102,3 s). Os resultados das Fases 2 e 2b não foram refeitos (fica para depois, se o Eduardo pedir).

### As 3 voltas do pedido 11

| volta do coach | volta do ML | o que o relógio diz |
|---|---|---|
| `rec__2026-08-08_13-18-00_vhe_interlagos__67` (microsetor 4 com 1,006 s) | `2026-08-08_13-18-00#0000`, **não válida**: faltam 326 m de pista (a gravação começou no meio da volta) | o relógio não foi conferido. O microsetor 4 do coach (290 a 350 m) cai justamente no trecho que não foi gravado: o coach contou uma volta incompleta |
| `rec__2026-08-19_20-58-36_vhe_interlagos__9` (microsetor 28 com 1,395 s) | `2026-08-19_20-58-36#0008`, válida | **limpo**: a pior diferença é −0,035 s, no microsetor 0 (o viés fixo) |
| `rec__2026-08-16_03-30-14_vhe_interlagos__5` (microsetor 29 com 1,418 s) | `2026-08-16_03-30-14#0004`, válida | **limpo**: a pior diferença é −0,038 s, no microsetor 0 |

Resumindo: o relógio gravado não explica os tempos impossíveis do pedido 11. Em duas voltas o relógio está certo, e o erro vem da projeção do coach, como o pedido 11 já tinha visto (saltos de até 28 m). Na terceira, o coach aceitou uma volta incompleta. As duas correções ficam para o pedido 13.

## 5. Origem no inventário e filtros

**Colunas novas por volta** (`ml/data/inventory.py`, cálculo em `ml/data/origin.py`):

| coluna | o que é |
|---|---|
| `origem` | `humano` ou `ia` quando o campo existe e é constante na volta; `misturada` quando muda; `desconhecida` quando não existe. Se o campo falta em parte da volta e o resto é constante, a volta também fica `desconhecida` |
| `ia_fracao`, `ia_amostras_com_campo` | fração das amostras com IA, e quantas amostras têm o campo |
| `pasta` | `repositorio` ou `app_instalado` |
| `inicio_epoch_s`, `fim_epoch_s` | relógio de parede da volta (usado para achar duplicatas) |
| `relogio_verificado`, `relogio_pior_s`, `relogio_pior_microsetor` | conferência do relógio (só nas voltas válidas) |
| `relogio_suspeito`, `relogio_limite_s` | a marca e o limite usado |
| `duplicada_de` | a volta mantida, quando esta é uma cópia |

O inventário novo, das duas pastas, está em `data/ml/origem/lap_inventory.parquet`, junto com a tabela do relógio por microsetor. **O inventário e o store em uso (`data/ml/lap_inventory.parquet` e `laps_grid.parquet`) não foram tocados.**

| | voltas | válidas | válidas e únicas | relógio suspeito | limpas |
|---|---:|---:|---:|---:|---:|
| repositório | 1.009 | 122 | 122 | 21 | 101 |
| app instalado | 890 | 570 | 566 | 123 | 443 |
| total | 1.899 | 692 | 688 | 144 | 544 |

Todas as 1.899 voltas ficam com `origem = desconhecida`.

**Filtros.** Para tudo o que fala do piloto, o padrão é: `humano`, relógio conferido, sem `relogio_suspeito` e sem duplicata. Uma duplicata nunca passa, em nenhum filtro.

- **store:** `build_store(..., origins=("humano",), include_clock_suspect=False)` e `python -m ml.scripts.build_lap_store [--origem humano ia misturada desconhecida | todas] [--incluir-relogio-suspeito]`. O store guarda o filtro usado (`selection`) e as colunas de origem de cada volta.
- **treino do coach:** `tools/train_reference_model.py [--origem ...] [--incluir-relogio-suspeito] [--inventario ARQUIVO]`. Uma volta do coach (`rec__<sessão>__<n>`) só passa se todas as voltas do ML dentro dela passarem. O motivo é que o contador do jogo trava no box e junta trechos. Sem um inventário com `origem`, o treino para em vez de adivinhar.
- **inventário:** `python -m ml.scripts.build_inventory` agora lê as duas pastas (`--pastas` restringe) e aceita `--saida`. Se o mesmo id aparecer nas duas pastas, ele para e pede para comparar.

**Hoje, com o filtro padrão, nada passa.** O store responde "nenhuma das 692 voltas válidas passa no filtro de origem ['humano']…", e o treino do coach responde "0 de 906 voltas → PARADO: nenhuma volta passa no filtro de origem. Modelo não gravado." Esse teste foi feito com `--dry-run`, e nenhum modelo foi escrito. Isso é o esperado até existirem voltas gravadas com o campo novo.

## 6. Sinais candidatos para separar IA de piloto

As gravações antigas não têm o campo, e por isso **nenhum detector foi treinado**. Para cada volta limpa (válida, única e com o relógio sem marca: 544 voltas) foram medidos os sinais abaixo, com a distribuição por sessão. Eles servem para escolher o que o detector vai usar quando houver sessões rotuladas, e não como rótulo.

| sinal | como é medido (`ml/data/origin_signals.py`, `ml/scripts/report_lap_origin.py`) |
|---|---|
| volante rápido | p95 de \|Δvolante/Δt\| e mudanças de sentido do volante por km (com histerese de 0,01) |
| formato dos pedais | fração do tempo com acelerador e freio parciais (entre 0,05 e 0,95), pico de cada frenagem, tempo até 90 % do pico |
| dispersão da frenagem e do ápice | desvio-padrão entre as voltas da sessão do início de frenagem e da lateral no ápice, nas janelas da Fase 2b, e, **por volta**, a distância até a mediana da pista |
| trocas de marcha | RPM na última amostra antes de subir a marcha e a dispersão dele. Toda troca passa uma amostra pela marcha 0, e isso é tratado |
| tempo | dispersão robusta do tempo de volta e do Bico de Pato (2.590 a 3.080 m) |

Sessões com pelo menos 3 voltas limpas (a lista completa, com as 124 sessões, está no JSON da entrega). A coluna "data citada" diz se a data é uma das que o Eduardo lembra de ter usado a IA. Isso não é rótulo, porque as sessões alternam IA e piloto.

| sessão | pasta | data citada | voltas limpas | Hz | dp tempo (s) | dp Bico (ms) | frenagem dp (m) | ápice dp (m) | desvio frenagem p50 / p90 (m) | desvio ápice p90 (m) | reversões volante /km | troca dp (rpm) |
|---|---|:-:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `2026-06-14_10-43-46` | app | sim | 3 | 29 | 0,00 | 1 | 1,6 | 0,05 | 2,0 / 2,0 | 0,04 | 57 | 13 |
| `2026-06-14_12-23-46` | repo | sim | 8 | 32 | 0,15 | 11 | 1,0 | 0,03 | 0,5 / 2,0 | 0,04 | 58 | 6 |
| `2026-06-18_20-06-03` | repo | sim | 3 | 30 | 0,21 | 8 | 1,2 | 0,09 | 2,0 / 2,0 | 0,05 | 61 | 7 |
| `2026-06-19_23-24-46` | repo | sim | 4 | 38 | 2,22 | 376 | 8,4 | 1,68 | 4,0 / 9,9 | 1,59 | 61 | 7 |
| `2026-06-20_13-13-02` | repo | sim | 31 | 58 | 0,59 | 47 | 7,5 | 1,15 | 3,0 / 16,0 | 0,35 | 67 | 5 |
| `2026-08-07_20-27-52` | app | não | 54 | 58 | 0,15 | 15 | 1,2 | 0,03 | 0,0 / 2,0 | 0,03 | 60 | 4 |
| `2026-08-08_11-58-41` | app | não | 13 | 55 | 0,07 | 10 | 1,1 | 0,03 | 0,0 / 0,8 | 0,03 | 59 | 4 |
| `2026-08-08_12-23-51` | app | não | 26 | 55 | 0,18 | 27 | 1,7 | 0,05 | 1,5 / 2,0 | 0,04 | 58 | 5 |
| `2026-08-08_13-22-07` | app | não | 10 | 54 | 0,16 | 13 | 1,0 | 0,03 | 1,0 / 2,0 | 0,04 | 58 | 4 |
| `2026-08-08_16-38-27` | app | não | 3 | 56 | 0,02 | 8 | 0,0 | 0,01 | 1,0 / 1,8 | 0,03 | 58 | 7 |
| `2026-08-08_17-04-15` | app | não | 66 | 54 | 0,14 | 18 | 1,3 | 0,04 | 1,0 / 2,0 | 0,04 | 58 | 5 |
| `2026-08-09_10-27-39` | app | sim | 48 | 54 | 0,19 | 22 | 2,0 | 0,04 | 0,0 / 2,0 | 0,04 | 58 | 6 |
| `2026-08-09_12-04-40` | app | sim | 6 | 55 | 0,10 | 14 | 1,6 | 0,03 | 1,0 / 1,5 | 0,03 | 59 | 6 |
| `2026-08-09_12-21-19` | app | sim | 5 | 56 | 0,02 | 21 | 0,9 | 0,04 | 0,0 / 1,6 | 0,04 | 60 | 7 |
| `2026-08-09_12-37-42` | app | sim | 12 | 53 | 0,16 | 19 | 1,5 | 0,04 | 0,5 / 2,0 | 0,05 | 58 | 6 |
| `2026-08-09_13-02-49` | app | sim | 19 | 55 | 0,28 | 19 | 2,7 | 0,06 | 2,0 / 2,2 | 0,05 | 59 | 4 |
| `2026-08-09_13-42-29` | app | sim | 16 | 54 | 0,27 | 29 | 1,9 | 0,04 | 1,0 / 2,0 | 0,06 | 58 | 6 |
| `2026-08-09_14-16-51` | app | sim | 11 | 56 | 0,11 | 7 | 1,3 | 0,03 | 2,0 / 2,0 | 0,05 | 60 | 4 |
| `2026-08-09_14-44-00` | app | sim | 8 | 54 | 0,08 | 9 | 2,4 | 0,06 | 2,0 / 2,0 | 0,04 | 59 | 5 |
| `2026-08-09_14-58-46` | app | sim | 6 | 57 | 0,14 | 31 | 1,6 | 0,04 | 1,5 / 2,0 | 0,06 | 61 | 5 |
| `2026-08-09_15-10-52` | app | sim | 49 | 58 | 0,15 | 11 | 1,3 | 0,04 | 2,0 / 2,0 | 0,06 | 60 | 6 |
| `2026-08-09_17-06-41` | app | sim | 6 | 54 | 0,16 | 5 | 1,6 | 0,04 | 1,5 / 2,0 | 0,03 | 59 | 6 |
| `2026-08-09_17-23-56` | app | sim | 6 | 56 | 0,19 | 3 | 1,2 | 0,05 | 0,0 / 1,0 | 0,05 | 60 | 5 |
| `2026-08-09_17-37-33` | app | sim | 21 | 54 | 0,11 | 13 | 2,0 | 0,04 | 2,0 / 2,0 | 0,04 | 59 | 5 |
| `2026-08-09_18-22-00` | app | sim | 6 | 55 | 0,06 | 16 | 0,9 | 0,03 | 1,5 / 2,0 | 0,04 | 60 | 6 |
| `2026-08-09_18-41-18` | app | sim | 3 | 58 | 0,01 | 1 | 1,2 | 0,04 | 2,0 / 2,0 | 0,04 | 61 | 5 |
| `2026-08-09_18-47-11` | app | sim | 12 | 53 | 0,14 | 21 | 2,4 | 0,04 | 1,0 / 2,0 | 0,06 | 60 | 6 |
| `2026-08-09_19-10-41` | repo | sim | 3 | 58 | 0,20 | 18 | 1,2 | 0,02 | 1,0 / 1,8 | 0,03 | 63 | 3 |
| `2026-08-09_19-20-59` | repo | sim | 40 | 59 | 0,19 | 14 | 1,3 | 0,03 | 1,0 / 2,0 | 0,04 | 61 | 4 |
| `2026-08-16_03-30-14` | repo | não | 7 | 58 | 10,39 | 50 | 7,2 | 0,89 | 4,0 / 22,2 | 1,35 | 45 | 11 |
| `2026-08-19_20-58-36` | app | não | 4 | 57 | 3,55 | 865 | 7,4 | 1,20 | 11,5 / 18,4 | 1,57 | 47 | 46 |
| `2026-08-19_22-23-14` | app | não | 14 | 54 | 0,15 | 21 | 1,0 | 0,04 | 4,0 / 4,0 | 0,05 | 56 | 5 |

O que a tabela mostra:

- **A maioria das sessões é tão constante quanto uma máquina.** Em 27 das 32 sessões, 90 % das voltas freiam a até 2,2 m da mediana da pista, e 2 m é a própria resolução da grade. O ápice fica a até 6 cm, e o Bico de Pato varia de 1 a 31 ms. Isso inclui todas as sessões de 07/08 e 08/08, **que não estão entre as datas citadas** e que não se distinguem das de 09/08.
- **Quatro sessões são bem mais variáveis:** `2026-06-19_23-24-46`, `2026-06-20_13-13-02`, `2026-08-16_03-30-14` e `2026-08-19_20-58-36`. Nelas, a dispersão da frenagem vai de 7 a 8,4 m e a do ápice de 0,9 a 1,7 m. Em `2026-06-20_13-13-02` metade das voltas fica a até 3 m da mediana e 10 % passam de 16 m, o que combina com uma sessão alternada.
- **`2026-08-19_22-23-14` é constante, mas diferente:** freia sempre de 3 a 4 m longe da mediana das outras, e o ápice fica a até 5 cm. É dela a volta de referência do modelo de ensaio do pedido 11 (84,663 s).

  > **Nota de 05/10/2026 (pedidos 19 e 20):** 84,663 s foi o tempo medido pelo coach antigo nesse modelo de ensaio. O tempo oficial da volta (`2026-08-19_22-23-14#0004`, `lap_time_s` do store v2) é 84,672 s.
- **Pedais e trocas de marcha não variam entre sessões nestes dados.** O freio vai de 0 a 0,99 numa amostra em todas as sessões, inclusive nas quatro variáveis. A marcha sobe a 8.200 rpm, com dispersão de 3 a 13 rpm, em quase todas (46 rpm na mais variável). Nestes dados, esses sinais não separam nada. Com outro controle ou câmbio manual, isso pode mudar.
- **O volante varia, mas depende de outras coisas.** As mudanças de sentido por km vão de 45 a 67, e as duas sessões com menos (45 e 47) estão entre as variáveis. Mas `2026-06-20` (variável) tem 67. A taxa de giro (p95) depende da frequência de gravação: as sessões de 30 Hz dão valores menores.

## 7. Números por origem

Não foram calculados. Nenhuma volta tem origem conhecida (`humano` = 0, `ia` = 0), então não há grupos para comparar o número de voltas, a dispersão da frenagem e do ápice, a variação do Bico de Pato e a melhor volta. O cálculo fica pronto para quando houver voltas rotuladas: o relatório já mede tudo isso por sessão, e o filtro de origem já existe.

## O que falta

1. **Gravação curta alternando a IA e o Eduardo, com o app aberto a partir do repositório.** O app instalado ainda é o antigo. Nela, conferir quatro coisas: se `isAIControlled` muda quando a IA assume e quando ela solta; se as voltas saem `humano`, `ia` e `misturada`; se `carModel` aparece no `metadata.json`; e o que significa o valor 1 do dump de maio. Depois, rodar `python -m ml.scripts.report_lap_origin` (ou `build_inventory`) para ver os rótulos.
2. **Detector por volta,** para as gravações antigas. Treinar com sessões rotuladas e validar por sessão (ADR 0014). Os candidatos mais promissores nestes dados são a distância da frenagem e do ápice até a mediana, por volta, e a dispersão do tempo. Pedais e trocas não variaram.
3. **Pedido 13 (coach):**
   - o coach aceitou uma volta incompleta (`rec__2026-08-08_13-18-00__67`);
   - a projeção do coach cria tempos impossíveis em voltas de relógio limpo;
   - a volta de referência do ensaio vem de uma sessão que ainda não tem rótulo.
4. **As voltas de box passam nos portões de qualidade como válidas:** são 135 nas duas pastas e 21 no store em uso. Fica para decidir se os portões passam a rejeitá-las. Isso não foi mudado agora, para não mexer nos resultados antigos.
5. **Reempacotar o app instalado** para que ele também grave quem pilota.

