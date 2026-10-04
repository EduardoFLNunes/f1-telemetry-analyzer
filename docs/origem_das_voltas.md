# Origem e confiabilidade das voltas (pedido 12, ADR 0014)

Data: 2026-10-03 e 04. Branch: `etapa/origem-das-voltas`.

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

*(preenchido depois de aplicar)*

## 5. Origem no inventário e filtros

*(preenchido depois de aplicar)*

## 6. Sinais candidatos para separar IA de piloto

*(preenchido depois de aplicar)*

## 7. Números por origem

*(preenchido depois de aplicar)*
