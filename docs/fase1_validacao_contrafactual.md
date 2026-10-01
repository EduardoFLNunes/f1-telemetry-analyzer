# Fase 1 — Integridade dos dados e validação do estimador contrafactual

Relatório de 2026-09-30. Segue a auditoria em
[`correcao_trajetoria_auditoria.md`](correcao_trajetoria_auditoria.md).
A camada de autocorreção não foi implementada e o algoritmo evolutivo não foi
alterado.

Convenção deste texto: **medido** é número que saiu de código executado nesta
fase contra os dados reais; **hipótese** é interpretação ainda não testada.

**Rastreabilidade.** Todo número medido sai de um destes dois scripts, e as
saídas estão congeladas em `docs/handoff/`:

| script | saída | conteúdo |
|---|---|---|
| `python -m ml.scripts.measure_integrity` | `docs/handoff/2026-09-30_fase1_resultados.json` → `integridade` | formatos, sinal, réguas de `s`, store × backup, replay, simulador dentro da sessão |
| `python -m ml.scripts.validate_counterfactual` | `docs/handoff/2026-09-30_fase1_resultados.json` → `contrafactual` | pares, métricas, critérios, decomposição |

O diff da fase está em `docs/handoff/2026-09-30_fase1.patch`, e a saída
completa do pytest em `docs/handoff/2026-09-30_fase1_testes.txt`.

---

## Resumo

| pergunta | resposta (medida) |
|---|---|
| Os leitores de pedal concordam agora? | Sim. Uma regra só (`core.telemetry.channels`), testada em amostras reais de maio, junho e agosto. |
| Quantas voltas válidas? | **122 em 11 sessões** (antes: 113 em 10). As 9 novas são da sessão `2026-06-14_12-23-46`, que tinha pedais e era rejeitada pelo leitor. |
| A geometria regravada em 25/08 mudou os dados? | Não. As 113 voltas em comum são idênticas (diferença 0,0 em `lateral`, tempo e velocidade). Agora um store de outra geometria é recusado. |
| As voltas válidas se associam ao replay? | As 122 têm associação `exact`. 39 voltas rejeitadas são trechos que o replay emenda com outros (contador travado no box). |
| O sinal lateral está consistente? | Sim, com a conversão explícita: gravado = −ml em todas as gerações (correlação −0,95 a −0,99). |
| **A diferença de tempo entre duas trajetórias é previsível?** | **Não, no nível em que uma recomendação existiria.** Nenhum estimador bate o "ganho zero" por microsetor em validação por sessão. |
| Ganho de linha e de execução podem ser somados? | Só dentro de um modelo cuja premissa não está validada, e os dois termos têm correlação **−0,60** entre si. Não somar. |

**Decisão pelos critérios fixados antes da execução: o estimador não avança para
a próxima fase.** Detalhes na seção 6.

---

## 1. Arquivos modificados e por quê

### P1 — leitura unificada dos pedais

| arquivo | mudança |
|---|---|
| `backend/core/telemetry/channels.py` (novo) | `driver_inputs(sample)`: lê `carPhysics.controls` e, se faltar, o topo da amostra. `input_schema(sample)` diz qual formato a amostra usa. |
| `backend/core/assisted_analysis/utils.py` | `normalize_lap_dataframe` lê os pedais por `driver_inputs` (antes: só o topo, com acelerador zerado nas sessões de 09/08). |
| `backend/ml/data/samples.py` | `flatten` lê os pedais por `driver_inputs` (antes: só `carPhysics.controls`, com `None` em maio e junho). |
| `backend/ml/config.py`, `backend/ml/README.md` | Texto: a sessão `2026-06-14_12-23-46` tem pedais; os canais mudaram de lugar entre versões do gravador. |

Medido antes de escolher a prioridade: nas sessões com os dois formatos, topo e
`carPhysics.controls` têm diferença máxima **0,0** em `throttle`, `brake`,
`steering`, `gear` e `rpm` (120 000 amostras, 4 sessões; `integridade.formatos_e_sinal`). A ordem de leitura não
muda nenhum valor.

### P2 — identidade da geometria

| arquivo | mudança |
|---|---|
| `backend/ml/track/geometry.py` | `TrackGeometry.geometry_id` (hash das coordenadas que o pipeline lê, ao milímetro, mais os parâmetros de processamento) e `source_hash` (do cache). |
| `backend/ml/data/inventory.py` | Cada volta registra `geometry_id`. |
| `backend/ml/data/lap_store.py` | O store grava `geometry_id`/`source_hash`. `load_store(track=...)` recusa um store de outra geometria ou sem registro (`GeometryMismatchError`). `build_store` recusa um inventário de outra geometria. |
| `backend/ml/preprocessing/alignment.py` | Por volta: `recorded_s_p95_m`, `recorded_lateral_p95_m`, `recorded_lateral_correlation` — o quanto a projeção gravada concorda com a recalculada. |
| `backend/ml/scripts/{compare_lap,export_coaching,fit_envelope,optimize_line,plot_comparison,run_pipeline,train_models,validate}.py` | Passam a carregar o store com `track=track`. |

O `generatedAt` do cache não entra no hash. Por isso, uma regravação idêntica
mantém o id. O hash do arquivo mudaria a cada regravação; o `sourceHash` do jogo
não muda quando o algoritmo de reconstrução muda.

### P3 — associação com o replay

| arquivo | mudança |
|---|---|
| `backend/ml/data/lap_identity.py` (novo) | Conta, por volta do `ml`, quantas amostras têm cada número do jogo, e classifica: `exact`, `replay_has_more` (o replay emenda esta volta com outros trechos), `spans_counters`, `no_counter`. |
| `backend/ml/data/inventory.py`, `lap_store.py` | Cada volta leva `replay_lap_id` (`rec__<sessão>__<n>`), `replay_match` e as frações. |

O replay (`session_repository.lap_detail`) entrega **todas** as amostras com o
mesmo número do jogo. O mapeamento é medido, não deduzido. O comportamento do
replay não foi alterado.

### P4 — sinal do deslocamento lateral

| arquivo | mudança |
|---|---|
| `backend/core/projection/lateral_offset.py` | Documenta a convenção do runtime (positivo à **direita**), declara `RECORDED_OFFSET_POSITIVE_SIDE = "right"` e oferece `to_left_positive`, a única conversão. |
| `backend/ml/data/samples.py`, `preprocessing/resampling.py` | O offset gravado entra no `ml` já convertido, como `lateral_recorded` (antes: `lateral_offset_recorded`, com o sinal do runtime). |

A emissão do runtime **não foi invertida**. 11 GB de gravações já usam a
convenção atual, e os consumidores do runtime ou tomam `abs()` ou subtraem dois
offsets da mesma convenção (`vehicle_dynamics_analyzer`). Inverter na fonte
deixaria gravações antigas e novas com sinais diferentes sob o mesmo nome de
campo. A correção está na fronteira: ninguém troca o sinal por suposição.

Medido (alinhamento de voltas reais, mesmas amostras): correlação entre
`lateralOffset` gravado e `lateral` do `ml` de −0,983 (ago), −0,955 (jun, ambos
os formatos), −0,974 (jun, topo), −0,989 (mai). Depois da conversão:
correlação **+0,957** (média de 66 voltas válidas com projeção gravada) e
|diferença| p95 de **0,42 m**.

### Etapa 2 — avaliação

| arquivo | conteúdo |
|---|---|
| `backend/ml/validation/counterfactual.py` (novo) | Perfis de volta, pares, regras de comparabilidade, estimadores, métricas, bootstrap por sessão, decomposição, critérios de aceitação. |
| `backend/ml/scripts/validate_counterfactual.py` (novo) | Execução com uma sessão de fora por vez; escreve em `data/ml/validation/counterfactual/`. |

### Testes novos

| arquivo | o que prova |
|---|---|
| `backend/tests/fixtures/recording_schemas/*.jsonl` | 15 linhas copiadas sem alteração de 5 sessões reais (maio só-topo, junho só-topo, junho ambos, agosto só-aninhado, agosto ambos). |
| `backend/tests/test_recording_schemas.py` (8) | Detecção de formato, pedais encontrados em todos, os dois leitores iguais, sinal gravado invertido na entrada do `ml`, runtime e `ml` com sinais opostos no mesmo ponto. **Três deles falham com o código anterior** (conferido revertendo os dois leitores). |
| `backend/tests/test_ml_data_integrity.py` (13) | Hash estável a regravação e sensível a 5 cm; store recusado com outra geometria ou sem registro; contador travado classificado como `replay_has_more`; atraso de 3 quadros continua `exact`; correlação negativa denuncia sinal trocado. |
| `backend/tests/test_ml_counterfactual.py` (7) | Identidade do modelo de eficiência; decomposição sem execução e sem interação quando só a linha muda; estimador de eficiência exato nesse caso; pares e exclusões; métricas; critérios. |

### Artefatos regenerados (fora do versionamento)

- `data/ml/lap_inventory.parquet`, `lap_inventory_summary.json`,
  `laps_grid.parquet`, `laps_grid_meta.json`, reconstruídos com
  `build_inventory` + `build_lap_store` (~5 min).
- Cópia dos anteriores em `data/ml/_backup_pre_fase1/`.
- Resultado da validação em `data/ml/validation/counterfactual/`
  (`resultado.json`, `pares_por_microsetor.parquet`, `pares_por_volta.csv`).

**Não foram retreinados**: as duas LSTMs, o envelope em
`vehicle_envelope.json`, o traçado otimizado e `optimal.json`. Eles foram
gerados a partir das 113 voltas anteriores.

---

## 2. Testes executados

```
cd backend && ../.venv/Scripts/python.exe -m unittest discover -s tests -t .
Ran 396 tests in 22.5s — OK
```

Linha de base antes das mudanças: 368 testes, OK. Diferença: +28 testes novos;
nenhum teste existente foi alterado ou removido.

---

## 3. Dados

| | medido |
|---|---|
| voltas brutas detectadas | 1009 |
| voltas válidas | **122** |
| sessões com volta válida | **11** |
| sessões com ≥ 2 voltas (testáveis) | 8 |
| voltas nas duas maiores sessões | 52 (`2026-08-09_19-20-59`) + 39 (`2026-06-20_13-13-02`) = 75 % |
| sessões com 1 volta | 3 (entram só como dado de ajuste) |
| pares possíveis | 7381 |
| pares dentro da mesma sessão | 2137 |
| pares comparáveis como volta | **875** |
| pares excluídos por combustível (> 5 L) | 1262 |
| pares entre sessões (não formados) | 5244 |
| microsetores de pares comparáveis | 42 805 |
| — excluídos por velocidade de entrada (> 3 km/h) | 9 484 |
| — excluídos por incidente (eficiência < 0,6) | 211 |
| **microsetores primários** (comparáveis e linhas ≥ 0,5 m distantes) | **6 728** |

Associação com o replay (inventário inteiro): 970 voltas `exact`, 39
`replay_has_more`. Todas as 122 válidas: `exact`.

---

## 4. O que foi testado e como

**Pares.** Em cada sessão, todos os pares de voltas válidas. **A** é a mais
lenta (a "observada") e **B** a mais rápida (a "alternativa"). O alvo é
`t_B − t_A` medido pelo cronômetro, por microsetor e por volta. O estimador
recebe a linha de B e a linha e a pilotagem de A. Nunca recebe o tempo de B.

**Comparabilidade.** Regras fixadas antes da execução:

- mesma sessão;
- nenhuma das duas voltas com amostra fora de pista;
- |Δ combustível| ≤ 5 L (≈ 0,1 s de volta);
- |Δ desgaste de pneu| ≤ 1 p.p.;
- por microsetor: velocidade de entrada a até 3 km/h, para a diferença nascer
  dentro do microsetor;
- por microsetor: sem incidente (velocidade observada < 0,6 × a simulada).

**Estimadores**, todos sobre o simulador existente:

| nome | previsão de `t_B − t_A` |
|---|---|
| `zero` | 0 (referência) |
| `physics` | `T_sim(B) − T_sim(A)` |
| `physics_cal` | `k · (T_sim(B) − T_sim(A))`, com `k` ajustado nas sessões de treino |
| `efficiency` | linha de B percorrida com a eficiência de A, `η_A = v_obs/v_sim`, suavizada numa janela ajustada nas sessões de treino |
| `surrogate` | LSTM substituta existente; só nas 4 sessões fora do treino e da validação dela (`metrics.json`) |

**Validação.** Uma sessão de fora por vez (8 dobras). O envelope do carro, `k` e
a janela de `η` são ajustados só nas outras sessões. A sessão de fora fornece só
os pares de teste. Nenhuma rede foi treinada.

**Critérios** (`AcceptanceCriteria`, fixados no código antes da primeira
execução), no subconjunto primário com as previsões de todas as dobras juntas:

| critério | limiar |
|---|---|
| perícia = 1 − MAE/MAE(zero) | ≥ 0,20 |
| IC 95 % da perícia (bootstrap por sessão, 2000×), limite inferior | > 0 |
| \|viés\| | ≤ 25 % do MAE de prever zero |
| Spearman (previsto × observado) | ≥ 0,30 |
| concordância de sinal (onde \|Δ\| > 0,02 s) | ≥ 65 % |
| sessões com perícia > 0 | ≥ 70 % |
| sessões testáveis | ≥ 5 |

---

## 5. Resultados medidos

### 5.1 Por microsetor — subconjunto primário (6 728 microsetores, 7 sessões)

| estimador | MAE (s) | viés (s) | DP do erro (s) | perícia | IC 95 % | Spearman | sinal |
|---|---:|---:|---:|---:|---|---:|---:|
| zero | 0,0172 | +0,0068 | 0,1007 | 0 | — | — | — |
| physics | 0,0462 | −0,0234 | 0,2092 | **−1,69** | [−9,23; −0,70] | 0,30 | 0,77 |
| efficiency | 0,0286 | −0,0073 | 0,0910 | **−0,66** | [−3,77; −0,29] | 0,30 | 0,77 |
| physics_cal | 0,0219 | +0,0020 | 0,1113 | **−0,27** | [−2,46; +0,01] | 0,28 | 0,77 |
| surrogate (435, 3 sessões) | 0,0215 | +0,0072 | 0,0459 | **−0,57** | [−3,46; −0,28] | 0,28 | 0,67 |

Todos erram mais do que prever ganho zero. O sinal acerta em ~77 % dos casos
(ordenação fraca, Spearman ≈ 0,3), mas a magnitude é pior que não prever nada.

### 5.2 Por diferença de linha (todos os microsetores comparáveis)

| \|L_B − L_A\| médio | n | MAE zero | MAE efficiency | perícia efficiency | perícia physics_cal |
|---|---:|---:|---:|---:|---:|
| < 0,5 m | 36 077 | 0,0074 | 0,0115 | −0,55 | −0,10 |
| 0,5–1,5 m | 4 438 | 0,0102 | 0,0226 | −1,21 | −0,39 |
| ≥ 1,5 m | 2 290 | 0,0307 | 0,0401 | −0,31 | −0,20 |

Mesmo onde as linhas diferem mais de 1,5 m, nenhum estimador bate o zero.

### 5.3 Por faixa de ritmo (primário; faixa = tempo da volta mais lenta do par)

| faixa | n | MAE zero | perícia physics | perícia efficiency | perícia physics_cal | perícia surrogate |
|---|---:|---:|---:|---:|---:|---:|
| < 86 s | 3 136 | 0,0035 | −1,09 | −1,02 | −0,04 | −3,30 |
| 86–88 s | 1 820 | 0,0142 | −1,85 | −1,20 | +0,003 | −1,50 |
| ≥ 88 s | 1 772 | 0,0444 | −1,73 | −0,44 | −0,40 | −0,26 |

### 5.4 Por sessão (primário, perícia)

| sessão | n | MAE zero | physics | efficiency | physics_cal |
|---|---:|---:|---:|---:|---:|
| 2026-06-14_12-23-46 | 274 | 0,0018 | −18,7 | −15,6 | −1,88 |
| 2026-06-18_20-06-03 | 39 | 0,0107 | −1,42 | −1,21 | +0,03 |
| 2026-06-19_23-24-46 | 95 | 0,0357 | −0,31 | −0,18 | +0,07 |
| 2026-06-20_13-04-20 | 17 | 0,0208 | −2,65 | −2,02 | −0,21 |
| 2026-06-20_13-13-02 | 2 566 | 0,0380 | −0,74 | −0,29 | +0,005 |
| 2026-08-09_19-20-59 | 3 671 | 0,0030 | −9,92 | −3,47 | −2,80 |
| 2026-08-16_03-30-14 | 66 | 0,0312 | −0,26 | −0,20 | +0,02 |

`physics_cal` fica próximo de zero (+0,005 a +0,07) nas sessões em que o `k`
aprendido nas outras é ~0,11. Ou seja, ele só "funciona" encolhendo a previsão
do simulador para ~10 % — quase o estimador zero. O `k` ajustado variou de
**0,01 a 0,29** entre dobras. Não há uma escala estável entre a diferença
simulada e a real.

### 5.5 Diagnóstico: microsetores com pedais semelhantes

Onde as duas voltas usaram freio e acelerador do mesmo jeito (diferença média
< 0,05) — e onde, portanto, a diferença de tempo teria de vir da linha: 5 260
microsetores, MAE de prever zero **0,0047 s**, `efficiency` 0,0213 s (perícia
−3,58), `physics` 0,0419 s (−8,0). Com pilotagem parecida, linhas que diferem
≥ 0,5 m quase não mudam o tempo real. O simulador prevê mudanças grandes.
(Diagnóstico, não critério: usa os pedais de B, que numa recomendação real não
existiriam.)

### 5.6 Volta inteira (875 pares)

| estimador | MAE (s) | viés (s) | perícia | Spearman |
|---|---:|---:|---:|---:|
| zero | 2,816 | +2,816 | 0 | — |
| physics | 1,013 | −0,401 | +0,64 | 0,70 |
| efficiency | 0,851 | +0,681 | +0,70 | 0,71 |
| physics_cal | 2,225 | +2,220 | +0,21 | 0,61 |

Por faixa de ritmo, a perícia positiva existe **só em ≥ 88 s** (efficiency
+0,77, Spearman 0,95). Ali as diferenças são de vários segundos e vêm de
erros grandes. Em < 86 s a perícia é −0,52 e em 86–88 s é −0,20. A perícia "da
volta inteira" é efeito das voltas lentas, não capacidade de discriminar
trajetórias próximas.

### 5.7 Checagem independente

Na sessão de 52 voltas (40 abaixo de 88 s, desvio-padrão real 0,159 s), a
correlação entre tempo simulado e tempo real é **0,07**. Na de 39 voltas (26
abaixo de 88 s), 0,58. A correlação de 0,93 documentada antes para o simulador
vem da amplitude de todo o conjunto, que inclui voltas de 100 s. Não diz nada
sobre separar trajetórias parecidas. O componente de alta frequência do
`lateral` (< 30 m) tem RMS de 7–11 mm por volta. A discrepância não é ruído
fino da linha.

### 5.8 Leitura (hipóteses, não medidas)

- O simulador quase-estacionário supõe o carro no limite em todo ponto. A
  linha muda a velocidade-limite simulada, mas o piloto real não anda no
  limite, e o quanto ele se aproxima depende da linha de um jeito que `η` fixo
  não captura.
- A forte correlação negativa entre o termo de linha e o de execução (5.9)
  sugere que parte do "efeito de linha" simulado é absorvida pela eficiência
  real: o simulador credita à linha velocidade que o piloto não usa.

### 5.9 Decomposição linha × execução (Etapa 3, medida)

Modelo: `t = Σ comprimento(L) / (η · v_sim(L))`. Com `η` ponto a ponto, as duas
combinações "puras" reproduzem o cronômetro (erro máximo 1,1 × 10⁻¹⁶ s).

| microsetores comparáveis (42 805) | valor |
|---|---:|
| \|linha\| médio | 0,0123 s |
| \|execução\| médio | 0,0180 s |
| \|interação\| médio | 0,0045 s |
| interação / (\|linha\| + \|execução\|), mediana | 0,08 % |
| idem, p90 | 0,99 % |
| microsetores com interação > 25 % | 0,5 % |
| **correlação entre linha e execução** | **−0,60** |

| volta inteira (875 pares) | valor |
|---|---:|
| \|linha\| médio | 2,47 s |
| \|execução\| médio | 0,89 s |
| \|interação\| médio | 0,88 s |
| \|total\| médio | 2,82 s |

---

## 6. Decisão pelos critérios

| estimador | perícia ≥ 0,20 | IC inf. > 0 | viés | Spearman ≥ 0,30 | sinal ≥ 65 % | sessões > 0 ≥ 70 % | ≥ 5 sessões | **resultado** |
|---|---|---|---|---|---|---|---|---|
| physics | ✗ −1,69 | ✗ −9,23 | ✗ | ✗ 0,300* | ✓ 0,77 | ✗ 0 % | ✓ 7 | **reprovado** |
| efficiency | ✗ −0,66 | ✗ −3,77 | ✗ | ✓ 0,302 | ✓ 0,77 | ✗ 0 % | ✓ 7 | **reprovado** |
| physics_cal | ✗ −0,27 | ✗ −2,46 | ✓ | ✗ 0,28 | ✓ 0,77 | ✗ 57 % | ✓ 7 | **reprovado** |
| surrogate | ✗ −0,57 | ✗ −3,46 | ✗ | ✗ 0,28 | ✓ 0,67 | ✗ 0 % | ✗ 3 | **reprovado** |

\* 0,29994, abaixo do limiar por arredondamento.

**Nenhum estimador pode sustentar um número de "ganho estimado" por correção
local.** O que se sustenta, medido: a direção da diferença acerta ~77 % das
vezes no subconjunto primário. Isso pode servir para ordenar alternativas, mas
não para dar segundos.

---

## 7. Etapa 3 — ganho de linha, de execução e total

**Definições.**

- **A. Ganho de trajetória**: a diferença de tempo atribuída a mudar só a linha,
  com a pilotagem fixa. Na decomposição acima,
  `t(L_B, η_A) − t(L_A, η_A)`.
- **B. Ganho de execução**: a diferença atribuída a mudar só frenagem,
  acelerador e velocidade, com a linha fixa: `t(L_A, η_B) − t(L_A, η_A)`.
- **C. Ganho total**: `t_B − t_A`, o que o cronômetro mede.
  `C = A + B + interação`.

**O que foi medido.** Dentro do modelo multiplicativo, a interação por
microsetor é pequena (mediana 0,08 %). Pela aritmética, somar A e B por
microsetor quase não erra. Duas medições impedem tomar isso como licença para
somar:

1. **A e B não são independentes.** Têm correlação de **−0,60**. Onde o modelo
   atribui ganho à linha, atribui perda à execução, e vice-versa. Somar os dois
   numa manchete apresentaria como ganhos separados duas parcelas que, nos
   dados, se cancelam.
2. **O termo A depende do simulador, que não passou na validação (seção 6).**
   A interação é pequena por construção do modelo (`η` multiplica `v_sim`), não
   por evidência de que linha e execução agem separadamente no carro real.

Na volta inteira a interação já é da ordem do termo de execução (0,88 s ×
0,89 s), puxada pelos microsetores com incidente.

**Limitação registrada.** Com dados observacionais, a decomposição só existe
**dentro de um modelo**. Não se observa a mesma volta com só a linha trocada.
O método atual não permite uma decomposição válida no carro real.

**Experimento proposto para medir** (hipótese de desenho, não executado):

- *Fatorial 2 × 2 controlado no jogo.* Uma sessão, combustível fixo (sem
  consumo, ou reabastecido a cada stint), pneus estabilizados. Um trecho de 2–3
  curvas. Quatro condições:
  - linha de referência × linha alterada (marcada por cones ou pela linha do
    replay como fantasma);
  - ponto de frenagem/aceleração de referência × alterado (marcado por placa de
    distância).

  ≥ 8 passagens válidas por célula, ordem sorteada em blocos. O efeito de
  interação da ANOVA mede diretamente se A e B se somam. É também o primeiro
  dado de "linha trocada, execução fixa" que o projeto teria — o alvo que falta
  para validar a parte A.
- *Variante com execução determinística.* O piloto da IA do Assetto Corsa segue
  `fast_lane.ai`. Editar a spline num trecho e repetir voltas da IA com a mesma
  agressividade dá linha trocada com execução reprodutível. Precisa de
  ferramenta para escrever `fast_lane.ai`, que o projeto ainda não tem.

---

## 8. Limitações estatísticas

- **Uma pessoa, 8 sessões testáveis, duas com 75 % das voltas.** O bootstrap por
  sessão reamostra 7 grupos, e os ICs são largos (ex.: [−3,77; −0,29]). Não há
  como falar de generalização entre pilotos.
- **Pares não são independentes.** Cada volta entra em dezenas de pares. Por
  isso o IC é por sessão, não por par.
- **O critério de combustível exclui 59 % dos pares dentro da sessão** (1262 de
  2137): stints longos têm consumo > 5 L entre voltas distantes. O limiar foi
  fixado antes. Uma análise de sensibilidade com outro limiar seria
  exploratória e não foi feita.
- **O alvo mistura linha e execução.** Não existe par real "só linha trocada".
  O diagnóstico 5.5 aproxima isso usando os pedais de B, informação que uma
  recomendação real não teria.
- **Diferenças típicas são pequenas.** MAE de prever zero de 0,017 s por
  microsetor no primário, e de 0,0035 s nos pares abaixo de 86 s. O cronômetro
  interpolado na grade de 2 m tem resolução de milissegundos a 50–60 Hz, então
  medir o alvo não é o problema; o problema é o estimador.
- **A substituta tem 435 microsetores primários em 3 sessões.** Não é avaliável
  pelo critério de 5 sessões. Ela foi treinada na grade da geometria atual, cuja
  identidade foi confirmada igual (seção 3).
- **O envelope foi reajustado por dobra.** O arquivo `vehicle_envelope.json`
  usado pelo resto do pipeline foi ajustado com sessões que aqui são de teste;
  ele não foi usado na avaliação.

---

## 9. Quando o ganho estimado não é confiável (medido)

| situação | evidência |
|---|---|
| qualquer microsetor isolado, em qualquer faixa de ritmo | perícia ≤ 0,003 para todos os estimadores (5.3) |
| linhas parecidas (< 0,5 m) | nenhum estimador bate o zero: perícia −0,05 a −0,83 |
| linhas diferentes (≥ 1,5 m) | ainda pior que zero (−0,20 a −1,19) |
| pilotos rápidos, voltas próximas (< 86 s) | MAE zero 0,0035 s; qualquer estimador erra o dobro ou mais |
| pilotagem semelhante entre as voltas | o tempo real quase não muda, o simulado muda muito (5.5) |
| somar ganho de linha com ganho de execução | correlação −0,60 entre os termos (5.9) |
| volta inteira com diferença < ~1 s | perícia negativa em < 86 s e 86–88 s (5.6) |

Onde há sinal: voltas inteiras com erro grande (≥ 88 s, Spearman 0,95). Ali a
resposta já é óbvia sem modelo.

---

## 10. Critérios objetivos para avançar

Mantidos como estão (`ml/validation/counterfactual.py::AcceptanceCriteria`). Um
estimador avança para alimentar a autocorreção quando, no subconjunto primário
e em validação por sessão:

1. perícia ≥ 0,20 contra prever zero;
2. limite inferior do IC 95 % por sessão > 0;
3. |viés| ≤ 25 % do MAE de prever zero;
4. Spearman ≥ 0,30 e concordância de sinal ≥ 65 %;
5. perícia > 0 em ≥ 70 % das sessões testáveis, com ≥ 5 sessões.

Para reavaliar: `python -m ml.scripts.validate_counterfactual` (11,6 s).

---

## 11. Problemas que permanecem

1. **O `s` gravado e o do `ml` são réguas diferentes** (medido em 5 sessões de
   maio e junho, perfil idêntico em todas): diferença 0 m na linha, +14 m em
   500 m, **+31 m em 1000 m**, +24 m em 2000 m, +12 m em 4300 m. Na sessão
   `2026-08-16_03-30-14` o perfil é outro (+20 m em 1000 m, 0 m em 4300 m) — o
   runtime daquela gravação usava outra versão da poligonal.
   O runtime mede a poligonal bruta do cache; o `ml`, a centerline consertada,
   suavizada em 60 m e reparametrizada. Por isso `recorded_s_p95_m` (~31 m) mede
   régua, não identidade de geometria.
2. **Alvos do coach possivelmente deslocados** (hipótese forte, não medida
   diretamente): `ml/export/coaching.py::progress_to_distance` converte `p` na
   distância da poligonal bruta e a usa como `s` da grade do `ml`. Pelo perfil
   acima, os alvos por fatia de 72 m em `optimal.json` estariam calculados sobre
   pista deslocada em até ~31 m. Não corrigido aqui: muda alvos que o app já usa.
   Registrado como tarefa separada.
3. **O replay emenda trechos com o mesmo número do jogo.** 39 voltas do
   inventário são `replay_has_more`. A associação agora diz isso; o replay
   continua mostrando o trecho emendado.
4. **`2026-08-09_*` não gravou `lateralOffset` nem `distanceAlongTrack`.** Para
   essas 56 voltas não há como conferir a projeção gravada.
5. **Modelos e traçado otimizado não foram regenerados** com as 122 voltas. A
   divisão em `metrics.json` continua a do treino original.
6. **Nenhum estimador de diferença de tempo validado.** Bloqueia a camada de
   autocorreção na forma proposta (ganho em segundos por correção).

---

## 12. O que isso muda no plano

Medido: com o simulador e os modelos existentes, a diferença de tempo entre
trajetórias próximas não é previsível melhor que zero.

Caminhos possíveis (hipóteses, cada um precisa passar pelos mesmos critérios):

- recomendar sem prometer segundos: usar só a direção (~77 % de acerto) e o
  histórico do próprio piloto ("você já fez este trecho 0,1 s mais rápido com
  esta linha"), que é medido e não contrafactual;
- um modelo de diferença aprendido diretamente nos pares por microsetor, com o
  mesmo protocolo por sessão. Isso é treinar um modelo — fica para a fase
  seguinte, se aprovada;
- o experimento controlado da seção 7, que é o único jeito de obter o alvo
  "linha trocada, execução fixa".
