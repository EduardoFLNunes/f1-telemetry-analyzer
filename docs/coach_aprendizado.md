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
