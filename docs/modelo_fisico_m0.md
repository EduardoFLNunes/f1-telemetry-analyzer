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
