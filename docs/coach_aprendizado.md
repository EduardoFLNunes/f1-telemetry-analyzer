# Coach na fase de aprendizado (pedido 14, ADR 0013 e 0016)

Branch: `etapa/coach-geometria-oficial`, com o `develop` trazido em 2026-10-04 (merge `13e4a359`).

## 1. Critérios do coach na geometria oficial (registrados antes de mudar o código)

Os critérios a–d são os do pedido 11, com os mesmos limites. O (e) é novo. A medição é feita por `backend/tools/validate_coach_geometry.py`.

| | o que mede | limite |
|---|---|---|
| **a** | Projeção do coach contra `TrackGeometry.project_sequence`, nas voltas válidas de três sessões: MergeFix (`2026-06-20_13-13-02`), cache atual (`2026-08-16_03-30-14`) e sem cache (`2026-08-09_19-20-59`). O coach projeta a sessão inteira, amostra por amostra e na ordem gravada, com um projetor só, como ao vivo. | cada sessão: p99 \|Δs\| ≤ 0,5 m e p99 \|Δd\| ≤ 0,2 m |
| **b** | Tempo de projeção por amostra, nas mesmas amostras de (a) | p99 ≤ 1 ms |
| **c** | Tempos por microsetor do coach (volta lida pelo carregador do app e reprojetada) contra os do store do ML, nas mesmas fronteiras, na volta válida mais rápida de 5 sessões diferentes | máximo ≤ 0,02 s por microsetor; soma = tempo da volta do store ± 0,02 s |
| **d** | Ensaio: o coach roda amostra por amostra sobre duas sessões inteiras (20/06 e 09/08) | nenhuma frase com "ganh", "ideal" ou "otimo" |
| **e** (novo) | Salto de projeção nas voltas limpas: \|Δs\| entre a projeção do coach e `TrackGeometry.project_sequence`, em todas as amostras das voltas limpas das sessões de (a) e da sessão rotulada de 04/10 (todos os seus arquivos). Volta limpa = válida, única, com o relógio conferido, sem `relogio_suspeito` e sem box (filtros dos pedidos 12 e 13, inventário de `data/ml/origem/`). | cada sessão: \|Δs\| máximo ≤ 2 m |

### Achado antes do registro: o store do ML erra a linha de chegada por um passo da grade

Ao preparar o passo 3, medi o tempo de volta e o microsetor 0 nas 5 voltas de (c) de três formas: pelo jogo, pelo store e pelo período verdadeiro, que é o tempo entre duas passagens pelo mesmo ponto, com s = 0 interpolado.

| volta | jogo | período verdadeiro | store do ML | diferença do store |
|---|---:|---:|---:|---:|
| `2026-08-16_03-30-14` | ~84,873 s | 84,8735 s | 84,8478 s | −25,7 ms |
| `2026-06-18_20-06-03` | ~85,293 s | 85,3277 s | 85,2997 s | −28,0 ms |
| `2026-06-20_13-13-02` | ~85,467 s | 85,4674 s | 85,4415 s | −26,0 ms |
| `2026-08-09_19-20-59` | ~85,494 s | 85,4982 s | 85,4717 s | −26,5 ms |
| `2026-06-14_12-23-46` | ~85,557 s | 85,5641 s | 85,5378 s | −26,3 ms |

- **A diferença é o tempo de um passo da grade na reta** (2 m a cerca de 280 km/h, de 25,7 a 26,5 ms), e cai inteira no microsetor 0.
- **A causa:** `ml/preprocessing/resampling.py::_reference_clock_to_grid` zera o relógio em s = 0 da grade, mas usa como período o `span` dos tempos na grade, que fica um passo mais curto que a volta.
- **O que isso explica:** é o "+26 ms" do critério (c) no pedido 11. O coach estava certo e o store, curto. Explica também o viés de −0,034 s do relógio no microsetor 0 no pedido 12: −26 ms deste passo, mais o viés de −8 ms que aparece em todo microsetor.

**Consequência para o critério (c):** com o coach seguindo a convenção de s = 0 interpolado (passo 3), o microsetor 0 e a soma vão diferir do store em cerca de 26 ms, acima do limite de 20 ms, por causa do store. O critério continua como foi escrito, contra o store. Para a decisão, o relatório trará também, **sem valer como critério**, a mesma comparação contra os microsetores do ML recalculados com o período verdadeiro. Não mexi no ML nem no store.

## 2. O que mudou no coach (Parte B)

### Linha de chegada (passo 3)

- **Microsetores fora da pista** (`reference_model.microsector_splits`), usados no treino, no replay e no critério (c): a volta vai de s = 0 a s = 0. A bandeira é interpolada no fim da volta, onde a gravação passa por s = 0 alguns metros antes de o jogo zerar o cronômetro. O início é a bandeira menos um período, o tempo entre duas passagens pelo primeiro ponto da volta. Antes, o início era extrapolado para trás a partir da primeira amostra.
- **Ao vivo** (`driving_coach.on_frame`, modelo na geometria oficial): a volta vira na passagem por s = 0, interpolada entre as duas amostras. Antes, virava quando o contador de voltas do jogo mudava, alguns metros depois. Um salto de mais de 5 % da volta que não seja a linha (box pelo menu, reset) recomeça a contagem sem falar.
- **Relógio:** é o cronômetro do jogo, que é o relógio da física. Na virada, ele é costurado pela distância entre as duas amostras sobre a velocidade. O `timestamp` do gravador não serve: ele engasga (medido em 04/10, +357 ms numa amostra e +2 ms na seguinte, com o carro andando 21 m).
- **O viés de −0,034 s do relógio no microsetor 0 (pedido 12) tem a mesma causa** do "+26 ms" do pedido 11: o store do ML encurta a volta e o microsetor 0 em um passo da grade (seção 1). São −26 ms do passo, mais o viés geral de −8 ms.

### Continuidade (passo 4)

- **`MapMatchingEngine` ganhou um limite rígido de avanço por amostra:** velocidade × intervalo × 1,5 + 5 m. Sem velocidade ou intervalo, vale 60 m, como no ML. Dentro do limite, vence o trecho mais perto, sem a penalidade antiga. Se nada dentro dele está a menos de 50 m do carro, o carro foi movido de verdade, e a projeção acompanha.
- **A opção fica desligada por padrão,** e só o projetor do coach (`CoachProjector`) a liga. Mapa e painel não mudaram.

### Rodadas dos critérios

Os critérios e os limites não mudaram entre as rodadas. Cada correção resolveu um defeito de implementação com causa medida.

| rodada | código | a | b | c | d | e | o que corrigiu |
|---|---|---|---|---|---|---|---|
| 1 | `fe88367f` | passou | falhou (p99 1,98 ms) | falhou | passou | falhou (até 17,3 m) | o intervalo vinha do `timestamp`, que engasga, e o motor calculava a normal de todo candidato. Além disso, a suíte rodava em paralelo |
| 2 | `66e4b720` | passou | passou (0,94 ms) | falhou | passou | falhou (até 8,0 m) | depois de um buraco de gravação, a penalidade antiga preferia um ponto 8 m atrás |
| 3 | `c753df6d` | passou | passou | **falhou** | passou | passou | — |

### Números da rodada 3

| | critério | medido | resultado |
|---|---|---|---|
| **a** MergeFix (39 voltas) | p99 \|Δs\| ≤ 0,5 m; p99 \|Δd\| ≤ 0,2 m | \|Δs\| p99 0,037 m (máx. 31,4 m, fora das voltas limpas); \|Δd\| p99 0,0018 m | passou |
| **a** cache atual (7 voltas) | idem | \|Δs\| p99 0,036 m (máx. 0,04 m); \|Δd\| p99 0,0015 m | passou |
| **a** sem cache (52 voltas) | idem | \|Δs\| p99 0,037 m (máx. 29,9 m, fora das voltas limpas); \|Δd\| p99 0,0019 m | passou |
| **b** (582.527 amostras) | p99 ≤ 1 ms | p50 0,33 ms, p99 0,91 ms | passou |
| **c** (5 voltas) | ≤ 0,02 s por microsetor; soma = tempo do store ± 0,02 s | microsetor 0: +0,026 a +0,029 s; microsetores 1 a 59: no máximo 0,002 a 0,004 s; soma − store: +0,026 a +0,029 s | **falhou** |
| **d** (20/06 e 09/08) | nenhuma frase proibida | 303 frases, 0 proibidas | passou |
| **e** (voltas limpas: 3 sessões de (a) e 3 arquivos de 04/10; os outros 4 arquivos de 04/10 não têm volta limpa) | \|Δs\| máx. ≤ 2 m por sessão | 0,04 a 0,31 m | passou |

**Diagnóstico do (c), que não vale como critério.** Contra os microsetores do ML com o período verdadeiro, a diferença máxima por microsetor fica entre 0,002 e 0,004 s, e a soma bate com o período com diferença de 0,1 a 1,4 ms. Nas 5 voltas, o (c) só falha pelo passo do store no microsetor 0. Os ±78 ms entre os microsetores 25 e 26 da volta de 20/06, vistos no pedido 11, sumiram com a continuidade rígida.

## 3. Parada

Pelo pedido, com o (c) falhando, parei antes da Parte C. Não fiz merge, não treinei nem regravei modelo e não mexi no ML nem no store. A decisão do que fazer com o store está no relatório.

