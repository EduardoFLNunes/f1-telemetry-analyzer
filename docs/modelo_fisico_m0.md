# Modelo físico do carro, etapa M0 (pedido 18, ADR 0017)

Branch: `etapa/canais-fisicos`, a partir de `develop`.

## 1. Registrado antes de construir (Parte C)

Esta seção foi commitada antes de o store v2 ser refeito com os canais físicos. Nada nela muda depois de olhar os resultados.

### 1.1 As colunas novas do store v2

As colunas novas são reamostradas na grade de 2 m como as outras: interpoladas linearmente ao longo da distância da própria volta. A ordem das rodas é a do jogo: FL (dianteira esquerda), FR, RL e RR.

| coluna | de onde vem na amostra gravada | unidade |
|---|---|---|
| `tyre_core_temp_fl`, `_fr`, `_rl`, `_rr` | `carPhysics.tyres.tyreCoreTemperature` | °C |
| `wheel_load_fl` … `_rr` | `carPhysics.tyres.wheelLoad` | N |
| `wheel_slip_fl` … `_rr` | `carPhysics.tyres.wheelSlip` | adimensional, a medida do jogo |
| `tyre_pressure_fl` … `_rr` | `carPhysics.tyres.tyrePressure` | psi |
| `brake_temp_fl` … `_rr` | `carPhysics.brakes.brakeTemp` | °C; só nas gravações feitas depois do pedido 18 |
| `steer_angle` | `carPhysics.controls.steerAngle`, bruto, sem o corte de ±1,5 da limpeza | sem unidade documentada (seção 3) |
| `yaw_rate` | `carPhysics.motion.localAngularVelocity.y` | rad/s; só nas gravações novas |
| `velocity_long`, `velocity_lat` | `carPhysics.motion.localVelocity.z` e `.x` | m/s; só nas gravações novas |

- **As colunas que já existiam** continuam calculadas do mesmo jeito; a coluna `wheel_slip`, que é a média das 4 rodas, também fica.
- **Volta sem o campo:** a coluna fica vazia (NaN). O meta lista, para cada volta, os canais novos que ela tem (`canais_por_volta`).
- **O esquema** sobe para `2.1` no meta (`esquema`). O nome do arquivo continua `laps_grid_v2.parquet`.

### 1.2 Checagens

| checagem | passa quando |
|---|---|
| **Nada do que já existe muda** | O store tem as mesmas voltas do início desta etapa: as 585 do store refeito em 05/10 depois da anotação da sessão da noite (`data/ml/laps_grid_v2.parquet`, sha256 registrado no relatório). Também precisam ser iguais o `lap_id`, o `lap_time_s` e as colunas antigas, idênticas valor a valor (NaN igual a NaN). |
| **Canais novos preenchidos** | Nas voltas da sessão `2026-10-04`, cada canal novo cujo campo existe na gravação tem pelo menos 95% dos pontos da grade preenchidos. A sessão `2026-10-05`, do app instalado, é relatada à parte. |
| **Store íntegro** | As checagens do pedido 16 continuam passando: o período contra o cronômetro do jogo, nenhum box, nenhuma duplicata e uma geometria só. |

**Se alguma coluna antiga mudar, o trabalho para aqui** e o relatório vai para o Eduardo, sem merge.

### 1.3 Custo

O relatório traz o tamanho do store e o tempo do `atualizar_coach`, antes e depois. Se o comando passar de 35 minutos, isso é relatado; o modo incremental continua sendo um pedido próprio.

## 2. O que é gravado (Parte B)

O inventário (`python -m ml.scripts.inventario_canais`) olhou as gravações das duas sessões:

- **`2026-10-04`:** 7 gravações do app de desenvolvimento, 447.811 amostras.
- **`2026-10-05`:** 1 gravação do app instalado, 142.459 amostras.

O JSON completo está em `docs/handoff/2026-10-04_canais-fisicos_inventario.json`.

| grupo | campo | gravado? | preenchido | faixa p1 / p50 / p99 (04/10) | unidade provável |
|---|---|---|---:|---|---|
| pneus | `tyreCoreTemperature[4]` | sim | 100% | 0,0 / 47,4 / 86,8 | °C |
| pneus | temperatura interna, central e externa | **não** (lidas da memória, não gravadas) | — | — | °C |
| pneus | `tyrePressure[4]` | sim | 100% | 13,0 / 18,2 / 22,1 | psi |
| pneus | `tyreWear[4]` | sim | 100% | 99,94 / 100,0 / 100,0 | %, 100 = novo |
| pneus | `wheelSlip[4]` | sim | 100% | 0,001 / 0,09 / 2,04 | adimensional (medida do jogo) |
| pneus | `wheelLoad[4]` | sim | 100% | 16 / 2.108 / 5.605 | N |
| freios | `brakeTemp[4]` | **não** | — | — | °C |
| freios | distribuição (`brakeBias`) | **não** | — | — | fração na dianteira |
| movimento | velocidades longitudinal e lateral (`localVelocity`) | **não** | — | — | m/s |
| movimento | velocidade no mundo (`velocity`) | sim | 100% | −62,5 / 0,0 / 69,8 | m/s, eixos do mundo |
| movimento | velocidade angular, guinada (`localAngularVel`) | **não** (lida, não gravada) | — | — | rad/s |
| movimento | `accG[3]` | sim | 100% | −2,06 / 0,00 / 2,07 | g |
| movimento | `heading` | sim | 100% | −2,99 / −0,23 / 3,03 | rad |
| suspensão | `suspensionTravel[4]` | sim | 100% | 0,035 / 0,041 / 0,067 | m |
| suspensão | `rideHeight[2]` | sim | 100% | −0,005 / 0,016 / 0,035 | m (dianteira, traseira) |
| comandos | `steerAngle` | sim | 100% | −0,48 / 0,00 / 0,51 | sem unidade documentada (seção 3) |
| comandos | acelerador e freio | sim | 100% | 0 / 0 / 1 | 0 a 1 |
| comandos | embreagem | sim, **mas sempre 0** | 100% | 0 / 0 / 0 | 0 a 1 |
| comandos | marcha | sim | 100% | 0 / 2 / 6 | marcha do jogo |

- **O app instalado** grava os mesmos campos, menos o indicador de IA. A sessão de 05/10 tem as mesmas faixas, exceto o volante (seção 3).

### A estrutura da memória compartilhada estava desalinhada

Conferindo no código quais campos eram lidos e não gravados, apareceu um erro no adaptador (`core/assetto_adapter.py`):

- **O que estava errado:** do `kersCurrentKJ` em diante, a estrutura da página de física seguia a ordem de outro simulador. O retrato salvo da memória compartilhada (`data/debug/ac_shared_memory_full_inventory.json`) mostra os efeitos:
  - o `brakeTemp` do adaptador tinha 0,55 e uma velocidade cujo z é `speedKmh / 3,6`: era a `brakeBias` e a `localVelocity`;
  - as temperaturas reais dos freios (18,19 °C) estavam em `visualTyreDamage` e em dois inteiros;
  - o `diffPa` tinha os bits do float 1,0, que é a embreagem;
  - o `clutch` era lido além do fim da página. **Por isso a embreagem gravada é 0 em todas as gravações.**
- **O que estava certo:** as temperaturas interna, central e externa dos pneus e o `isAIControlled` caíam no lugar certo. O indicador de IA dos pedidos 12 a 17 continua valendo.
- **A correção:** a estrutura agora segue a ordem do Assetto Corsa 1. Um teste lê os bytes do retrato com as duas estruturas.

### O que entrou no gravador

O gravador do repositório passa a gravar, no bloco `carPhysics`:

- `tyres.tyreTempInner`, `tyreTempMiddle` e `tyreTempOuter`: as temperaturas da superfície do pneu;
- `brakes.brakeTemp[4]` e `brakes.brakeBias`;
- `motion.localVelocity`: x lateral, y vertical, z longitudinal, em m/s;
- `motion.localAngularVelocity`, com a guinada no y, em rad/s;
- e a embreagem certa.

**Só as sessões gravadas depois deste pedido, com o app aberto a partir do repositório, terão esses campos.** O app instalado continua sem eles até ser reempacotado (backlog).

## 3. A unidade do volante

- **Arquivos do carro:** os dados do `rss_formula_rss_3_v6_2026` estão empacotados no `data.acd`, que é criptografado, e não existe pasta `data/` aberta. Pela restrição do pedido, não tentei abrir. O ângulo máximo e a relação de direção não vêm dos arquivos.
- **Faixa observada nas voltas válidas** (`python -m ml.scripts.relatorio_volante`):

| grupo | voltas | p1 | p50 | p99 | máximo \|valor\| |
|---|---:|---:|---:|---:|---:|
| 04/10, suas, app de desenvolvimento | 11 | −0,38 | −0,01 | 0,37 | 0,60 |
| 04/10, IA | 13 | −0,44 | −0,01 | 0,53 | 0,72 |
| 05/10, suas, app instalado | 7 | −0,40 | −0,01 | 0,39 | 0,64 |

  Fora das voltas (box e manobras), a gravação de 05/10 chega a ±0,98.
- **Estimativa empírica,** abaixo de 80 km/h nas curvas fechadas (raio mínimo abaixo de 30 m: C01, C02, C07, C10 e C12), com |a lateral| de 0,3 g ou mais. Usa a razão |volante| / |curvatura|, com a curvatura `a_lat / v²`.

| grupo | pontos | razão p25 | p50 | p75 | mediana por volta (min a max) |
|---|---:|---:|---:|---:|---|
| 04/10, suas | 288 | 10,1 | 10,6 | 11,6 | 10,2 a 11,5 (10 voltas) |
| 04/10, IA | 12 | 13,3 | 13,3 | 13,5 | 13,3 a 13,5 (3 voltas) |
| 05/10, suas | 116 | 9,8 | 10,1 | 11,0 | 9,8 a 11,5 (6 voltas) |

- **Sinal:** o volante positivo vem sempre com a aceleração lateral negativa (416 de 416 pontos). As convenções de sinal do volante e da aceleração lateral são opostas.
- **O que a razão sugere,** sem nada adotado:
  - **Ângulo da roda em radianos?** A razão ficaria perto do entre-eixos, cerca de 2,5 a 3 m. Ela é 3 a 4 vezes maior.
  - **Ângulo do volante em radianos?** A razão ficaria perto do entre-eixos vezes a relação de direção, algumas dezenas.
  - **Fração do curso do volante?** A razão seria o entre-eixos dividido pelo esterço máximo da roda. Com 10,6 e um entre-eixos de 2,8 m, a roda teria cerca de 0,26 rad (15°) no fim do curso.
  - **IA contra você:** a IA dá mais volante para a mesma curvatura. Pode ser o carro escorregando mais na frente no limite, com mais ângulo de deriva, e não outra escala; ela passa pouco abaixo de 80 km/h, então só tem 12 pontos.
- **Para fechar a unidade:** uma volta com a guinada gravada (`localAngularVelocity`, agora no gravador) dá a curvatura sem depender da aceleração lateral. Uma sessão com o ajuste de rotação do volante conhecido diria se o valor é uma fração.

## 4. O que entrou no store e as checagens (Parte C)

- **As colunas** da seção 1.1 entraram no `laps_grid_v2.parquet`, com o esquema `2.1` e os canais de cada volta no meta (`canais_por_volta`).

| checagem | resultado |
|---|---|
| nada do que já existe muda | **passou.** As mesmas 585 voltas, o mesmo `lap_time_s` e as colunas antigas idênticas valor a valor, contra a cópia do início da etapa (`data/ml/_backup_antes_pedido18/`, sha256 `3c056ba0…`) |
| canais novos preenchidos na sessão `2026-10-04` | **passou.** Os 17 canais que existem nas gravações (pneus, carga, escorregamento, pressão e `steer_angle`) estão 100% preenchidos. Freios, guinada e velocidades locais não existem nessas gravações. |
| sessão `2026-10-05`, à parte | os mesmos 17 canais, 100% preenchidos |
| store íntegro | **passou.** As checagens do pedido 16 continuam passando (período com p99 de 3,3 ms). |

**Custo:**

| | antes | depois |
|---|---|---|
| tamanho do store v2 | 137 MB | 315 MB |
| construção do store v2 | 457 s | 556 s |
| `atualizar_coach` completo | 1.151 s (19 min, em 05/10 de manhã) | CUSTO_DEPOIS |

## 5. Técnica de pilotagem: como ler (Parte D)

As definições estão na seção 1.7 do `docs/store_v2_e_evolucao.md`, e o formato do bloco `tecnica` está na seção 5 dele. São medidas descritivas: a "diferença consistente" e o coach não mudam. A regressão nos JSONs das duas sessões saiu idêntica, tirando o bloco novo e o hash do store.

- **Uso da aderência (g):** o quanto do pneu você usa no trecho. É o p95 da aceleração combinada. A razão contra a IA abaixo de 1 quer dizer que sobra aderência.
- **Freio e volante juntos (m):** quantos metros você freia já virando. A IA faz isso no S do Senna e na Junção; um piloto que termina de frear antes de virar fica perto de zero.
- **Freada emendada:** a freada desta curva começa antes do ápice da anterior. É o caso do Bico de Pato.
- **Pneus:** a temperatura média por volta e a correlação com o tempo da volta. Negativa quer dizer volta mais quente, volta mais rápida, e isso não separa causa.

### Primeira rodada

| | 04/10 (11 voltas) | 05/10 (7 voltas) | IA |
|---|---|---|---|
| **C01, S do Senna:** aderência (g) | 1,95 (razão 0,75) | 2,02 (0,78) | 2,60 |
| C01: freio e volante juntos | 0 m | 0 m | 16 m |
| C01: freada emendada | 0 de 11 | 0 de 7 | não |
| **C10, Bico de Pato:** aderência (g) | 1,78 (0,74) | 2,03 (0,84) | 2,41 |
| C10: freio e volante juntos | 14 m | 16 m | 0 m |
| C10: freada emendada | **7 de 11** | **4 de 7** | não |
| pneus: correlação de Spearman entre temperatura e tempo | −0,16 | −0,57 | — |
| freios | sem o canal | sem o canal | — |

**As 14 curvas, em resumo:**

- **Aderência:** você usa de 54% a 97% da aceleração combinada da IA. A menor razão é na C09 (0,54 e 0,56). As maiores são na C03 (0,97 e 0,93), na C05 (0,90 e 0,96) e na C14 (0,88 e 0,95). De 04/10 para 05/10, a razão subiu em 10 das 14 curvas.
- **Freio e volante juntos:** a IA freia virando no S do Senna (16 m na C01, 10 m na C02), na C06 (24 m), C08 (20 m) e C12 (18 m). Você quase não faz isso nessas curvas: 0 a 8 m. Você freia virando mais que a IA no Bico de Pato (14 e 16 m, a IA 0 m) e, em 05/10, na C04 (18 m, a IA 6 m).
- **Freada emendada:** só aparece na C10, e só nas suas voltas.
- **Pneus:** a média ao longo da volta vai de 52 °C a 74 °C em 04/10 e de 52 °C a 61 °C em 05/10. A traseira fica de 0,7 °C a 11 °C acima da dianteira.

## 6. O que ainda falta para a M1

- **Sessões com os canais novos.** A guinada, as velocidades locais e os freios só existem nas gravações feitas depois deste pedido, com o app do repositório. O ADR 0017 pede 5 sessões humanas com canais físicos para a M1.
- **Reempacotar o app instalado** depois do merge, para ele gravar o indicador de IA, os canais novos e a embreagem certa (backlog).
- **A unidade do volante,** fechada com a guinada gravada (seção 3).
- **O entre-eixos e os dados do carro** que não vêm do `data.acd`: o modelo da M1 vai ter de estimá-los dos dados ou recebê-los de fora.
- **A embreagem antiga não serve:** todas as gravações anteriores têm 0 nela.
