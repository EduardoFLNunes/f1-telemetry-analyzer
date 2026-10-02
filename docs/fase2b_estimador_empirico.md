# Fase 2b — Estimador empírico de ganho por janela de curva

Relatório de 2026-10-02. Segue os ADRs 0005, 0006 e 0010. Branch
`etapa/fase2b-estimador-empirico`, a partir de `handoff/coach-mapeamento`.

Convenção: **medido** = número que saiu da execução registrada em
`docs/handoff/2026-10-02_fase2b_resultados.json`; **hipótese** = interpretação
não testada.

---

## Resumo

**Pergunta.** Só com as voltas do próprio piloto, sem depender do simulador, dá
para prever a diferença de tempo de uma correção local melhor do que "ganho
zero"?

**Resposta (medida): não, pelos critérios fixados antes de rodar.** Nenhum dos
quatro estimadores candidatos (E1 a E4) passou em todos os critérios do ADR
0006. Os dois melhores (KNN e Processo Gaussiano) erram menos que "prever zero",
com intervalo de confiança acima de zero. Mas o ganho é pequeno (skill +0,08 e
+0,11, contra o mínimo de 0,20), carregam viés, e o resultado desaparece sem as
duas sessões dominantes.

O teto (E2-teto, que usa velocidades e por isso é quase tautológico) passou nos
critérios com todas as sessões. Ele mostra que existe informação nas
diferenças de velocidade. Não é candidato e não foi aprovado como estimador.

Pela regra do pedido, isso é um resultado válido: relatado aqui, e a fase para.

---

## 1. O que foi feito

### Janela de curva

Do início de uma zona de frenagem até o início da próxima: a curva **mais** a
reta seguinte (ADR 0005). As janelas cobrem a volta inteira, então os tempos
delas somam o tempo da volta.

As zonas de frenagem saem das voltas, não da geometria. O detector de curvas
acha 14 curvas, mas o piloto freia em 7 lugares: curvas encadeadas, como o S do
Senna, dividem uma frenagem só. A regra, fixada antes de olhar qualquer tempo:

- início de frenagem = freio ≥ 0,15, com 20 m sem freio antes e 10 m com freio
  depois (descarta toques);
- inícios a menos de 30 m entre si formam um aglomerado;
- um aglomerado é zona de frenagem se pelo menos metade das voltas freia ali;
- zonas a menos de 150 m (pela mediana) se juntam: são o segundo toque na mesma
  curva, sem reta entre eles;
- a janela começa 10 m antes do início mais precoce (5º percentil) da zona,
  arredondado a 10 m.

As janelas são definidas **só com as sessões de treino de cada rodada**.

**Janelas medidas, com todas as sessões no treino (7 por volta):**

| janela | curva de referência | início–fim (m) | comprimento |
|---|---|---|---:|
| J1 | C01 (S do Senna) | 90–1150 | 1060 m |
| J2 | C04 (Descida do Lago) | 1150–1870 | 720 m |
| J3 | C06 (Ferradura) | 1870–2170 | 300 m |
| J4 | C07 (Laranjinha) | 2170–2350 | 180 m |
| J5 | C08 (Pinheirinho) | 2350–2590 | 240 m |
| J6 | C10 (Bico de Pato) | 2590–3080 | 490 m |
| J7 | C12 (Junção, + reta principal) | 3080–90 | 1344 m |

Em 1 das 8 rodadas com todas as sessões (a que testa `2026-06-20_13-13-02`) e
em 5 das 6 sem as dominantes, surgiu uma 8ª janela: o segundo toque de freio no
S do Senna (~350 m) passou da metade das voltas de treino daquela rodada. As
fronteiras de todas as rodadas estão no JSON (`dobras[].janelas`).

### Pares

Os mesmos da Fase 2. Na mesma sessão, A = a volta mais lenta, B = a mais
rápida. Um par-janela entra quando:

- a diferença de combustível é ≤ 5 L e a de desgaste de pneu ≤ 1 p.p.;
- nenhuma das duas voltas tem amostra fora de pista;
- a velocidade de entrada na janela difere ≤ 3 km/h;
- não há incidente (velocidade observada < 0,6 × a simulada);
- a frenagem e a retomada do acelerador foram detectadas nas duas voltas.

**Alvo:** ΔT = tempo de B − tempo de A naquela janela, pelo cronômetro.

### Entradas (diferenças B − A)

- ponto de frenagem (m; positivo = B freou depois);
- posição lateral na entrada, no ápice e na saída da curva (m, positivo à
  esquerda, convenção do ML);
- ponto de retomada do acelerador ≥ 0,6 (m).

Para o E2-teto, também a diferença de velocidade mínima na curva e de velocidade
na saída (km/h).

### Estimadores

| | o que é | incerteza (faixa de 95 %) |
|---|---|---|
| E0 | prever zero | — |
| E1 | ΔT do simulador na janela × inclinação ajustada por janela no treino | — |
| E2 | ridge por janela, sem intercepto; α escolhido no treino | quantis dos resíduos fora da amostra no treino |
| E3 | KNN de regressão por janela; k escolhido no treino | quantis dos resíduos fora da amostra no treino |
| E4 | Processo Gaussiano por janela (RBF com escala por entrada + ruído) | desvio previsto pelo modelo |
| E2-teto | E2 + velocidades mínima e de saída | quantis dos resíduos; só teto |

Detalhes que valem explicação:

- **Pares nas duas ordens no treino.** Cada par entra como (A, B) e (B, A), com
  entradas e alvo de sinal trocado. Trocar as voltas troca o sinal do ganho. Sem
  isso, o modelo aprenderia que "A é sempre a mais lenta" em vez da pilotagem.
- **Resíduos fora da amostra.** Os quantis do E2 e do E3 vêm de uma validação
  interna, deixando uma sessão de treino de fora por vez. Resíduos dentro da
  amostra dariam faixas estreitas demais.
- **GP com no máximo 600 pontos de treino por janela** (300 pares nas duas
  ordens, sorteados com semente fixa), porque o custo cresce com o cubo do
  número de pontos.
- Hiperparâmetros testados: α ∈ {0,01; 0,1; 1; 10; 100; 1000}; k ∈ {3, 5, 10,
  20, 40, 80}.

### Abstenção ("não conclusivo")

- **Faixa inclui zero:** o estimador não diz se a correção ganha ou perde.
- **Fora da distribuição:** alguma entrada do par de teste está fora da faixa
  2,5 %–97,5 % das diferenças vistas no treino naquela janela. É contado à
  parte, igual para todos os estimadores.

### Validação

- Uma sessão inteira fora por rodada: 8 rodadas com todas as sessões, 6 sem as
  duas dominantes. As janelas, o envelope do carro, a inclinação do E1, o α, o k
  e os hiperparâmetros do GP saem só das sessões de treino.
- Critérios do ADR 0006, idênticos aos da Fase 2. A regra de decisão foi
  commitada antes da primeira execução (commit `2c792a01`): **aprova quem passa
  em todos os critérios com previsão em todos os casos dentro da distribuição.**
  Os critérios aplicados só aos casos em que o estimador responde são resultado
  secundário.

---

## 2. Dados (medido)

| | todas as sessões | sem as dominantes |
|---|---:|---:|
| voltas | 122 | 31 |
| rodadas (sessões testáveis) | 8 | 6 |
| pares-janela comparáveis no teste | 4 703 | 331 |
| — fora da distribuição | 1 341 (29 %) | 130 (39 %) |
| — dentro da distribuição (avaliados) | **3 362** | **201** |
| exclusões por combustível | 9 312 | 104 |
| por velocidade de entrada | 1 425 | 75 |
| por incidente | 246 | 8 |
| por frenagem/retomada não detectada | 14 | 6 |

A sessão `2026-08-09_19-20-59` responde por 2 770 dos 3 362 casos avaliados
(82 %).

Hashes dos dados lidos (ADR 0007), no JSON em `dados`:

- `laps_grid.parquet` `a9798c3a…`
- `laps_grid_meta.json` `5a4d3823…`
- `lap_inventory.parquet` `78f23117…`
- cache da geometria `6ee98614…`

Geometria `0ed16f0dd2225990`. Ambiente: Python 3.9.7, numpy 1.26.3,
pandas 2.1.4, scikit-learn 1.6.1.

---

## 3. Resultados (medido)

### 3.1 Decisão — todas as sessões, todos os casos dentro da distribuição (3 362)

| | MAE (s) | viés (s) | skill | IC 95 % | Spearman | sinal | sessões com skill > 0 | **resultado** |
|---|---:|---:|---:|---|---:|---:|---:|---|
| E0 zero | 0,0352 | +0,0202 | 0 | — | — | — | — | referência |
| E1 simulador | 0,0440 | +0,0107 | −0,25 | [−0,35; −0,11] | 0,29 | 0,65 | 38 % | reprovado |
| E2 ridge | 0,0383 | +0,0198 | −0,09 | [−0,11; +0,09] | −0,16 | 0,44 | 50 % | reprovado |
| E3 KNN | 0,0323 | +0,0128 | **+0,08** | [+0,06; +0,27] | 0,41 | 0,71 | 88 % | reprovado |
| E4 GP | 0,0313 | +0,0137 | **+0,11** | [+0,08; +0,29] | 0,43 | 0,71 | 75 % | reprovado |
| E2-teto | 0,0218 | +0,0068 | +0,38 | [+0,31; +0,55] | 0,73 | 0,89 | 88 % | passou (não candidato) |

**Por que E3 e E4 reprovam:**

- skill abaixo de 0,20 (+0,08 e +0,11);
- viés acima de 25 % do erro de prever zero (36 % e 39 %).

Eles passam no limite inferior do IC, no Spearman, na concordância de sinal e na
fração de sessões com skill positivo.

### 3.2 Sem as duas sessões dominantes (201 casos, 5 sessões avaliáveis)

| | skill | IC 95 % | Spearman | sinal | resultado |
|---|---:|---|---:|---:|---|
| E1 | −0,50 | [−1,57; −0,16] | 0,08 | 0,49 | reprovado |
| E2 | +0,005 | [−0,01; +0,03] | 0,06 | 0,60 | reprovado |
| E3 | −0,02 | [−0,47; +0,01] | 0,07 | 0,08 | reprovado |
| E4 | −0,61 | [−0,68; −0,11] | 0,35 | 0,72 | reprovado |
| E2-teto | +0,05 | [+0,04; +0,23] | 0,55 | 0,87 | reprovado |

Sem as duas sessões grandes, sobram 31 voltas. Nenhum estimador, nem o teto,
bate prever zero de forma útil. O GP piora muito: com poucos dados, a faixa
dele erra para menos (seção 3.4).

Informativo: os modelos treinados com todas as sessões, **avaliados** só nas
outras 6 (298 casos), dão skill +0,25 (E3) e +0,26 (E4), mas com IC [−0,10;
+0,37] e [−0,03; +0,44]: não passam no limite inferior do IC.

### 3.3 Abstenção — o que acontece quando o estimador só responde quando a faixa exclui zero

Todas as sessões, 3 362 casos dentro da distribuição:

| | responde | skill quando responde | IC 95 % | critérios no subconjunto (secundário) |
|---|---:|---:|---|---|
| E2 | 9 (0,3 %) | +0,42 | [+0,30; +0,61] | não passa |
| E3 | 61 (1,8 %) | +0,62 | [+0,52; +0,83] | passa |
| E4 | 424 (12,6 %) | +0,59 | [+0,47; +0,61] | passa |
| E2-teto | 120 (3,6 %) | +0,60 | [+0,52; +0,82] | não passa |

Quando E3 e E4 respondem, acertam bem: erro 59–62 % menor que prever zero. Mas:

- **respondem pouco:** 1,8 % e 12,6 % dos casos;
- **não se sustenta sem as dominantes:** sem as duas sessões, E2 e E3 não
  respondem nenhuma vez, e o E4 responde 60 % dos casos com skill **−0,84**.

Pela regra pré-registrada, esse resultado é secundário e não aprova ninguém.

### 3.4 Calibração da faixa de 95 % (fração dos ΔT reais dentro da faixa)

| | todas, dentro da distr. | todas, fora | sem dominantes, dentro |
|---|---:|---:|---:|
| E2 | 0,99 | 0,63 | 0,98 |
| E3 | 0,99 | 0,63 | 0,99 |
| E4 | 0,89 | 0,72 | **0,36** |
| E2-teto | 0,99 | 0,63 | 0,98 |

- E2 e E3 têm faixas **largas demais** (99 % em vez de 95 %). Por isso quase
  nunca respondem.
- O E4 fica perto do nominal com todos os dados (89 %), mas **erra muito para
  menos** com poucos dados (36 %): a faixa dele promete 95 % e acerta um terço.
  É o risco que o ADR 0010 apontou.
- Fora da distribuição, todas as faixas falham (63–72 %). Isso confirma que o
  filtro de distribuição é necessário.

### 3.5 Curva risco × cobertura (skill nos casos mais confiantes, todas as sessões)

| cobertura | 10 % | 20 % | 30 % | 50 % | 70 % | 100 % |
|---|---:|---:|---:|---:|---:|---:|
| E2 | +0,06 | −0,06 | −0,10 | −0,12 | −0,11 | −0,09 |
| E3 | +0,18 | +0,33 | +0,29 | +0,14 | +0,10 | +0,08 |
| E4 | **+0,62** | +0,48 | +0,32 | +0,19 | +0,15 | +0,11 |
| E2-teto | +0,60 | +0,60 | +0,58 | +0,52 | +0,45 | +0,38 |

A confiança do E4 ordena bem os casos: nos 10 % mais confiantes, o erro é 62 %
menor que prever zero, e cai suavemente com a cobertura. O E2 (linear) não tem
essa propriedade.

### 3.6 Por faixa de ritmo (skill, todas as sessões)

| ritmo da volta mais lenta | casos | E1 | E2 | E3 | E4 | teto |
|---|---:|---:|---:|---:|---:|---:|
| < 86 s | 2 106 | −0,12 | −0,14 | +0,05 | +0,07 | +0,36 |
| 86–88 s | 572 | +0,12 | −0,03 | +0,25 | +0,20 | +0,41 |
| ≥ 88 s | 684 | −0,83 | −0,00 | +0,04 | +0,15 | +0,41 |

### 3.7 Por sessão (skill, todas as sessões)

| sessão | casos | E3 | E4 | teto |
|---|---:|---:|---:|---:|
| 2026-06-14_12-23-46 | 235 | +0,26 | +0,26 | +0,58 |
| 2026-06-18_20-06-03 | 14 | −0,68 | −0,39 | +0,15 |
| 2026-06-19_23-24-46 | 4 | +0,49 | +0,55 | +0,58 |
| 2026-06-20_13-04-20 | 1 | +0,25 | +0,49 | −0,27 |
| 2026-06-20_13-13-02 | 294 | +0,11 | +0,07 | +0,31 |
| 2026-08-09_19-10-41 | 18 | +0,23 | +0,28 | +0,19 |
| 2026-08-09_19-20-59 | 2 770 | +0,06 | +0,10 | +0,37 |
| 2026-08-16_03-30-14 | 26 | +0,08 | −0,02 | +0,38 |

### 3.8 Tamanho das diferenças de pilotagem

Dos 3 362 casos avaliados:

- 3 331 (99 %) têm diferença de ponto de frenagem **abaixo de 5 m**;
- 3 361 têm diferença de posição lateral no ápice **abaixo de 0,5 m**.

As voltas comparáveis do piloto são muito parecidas entre si. Os estimadores
aprendem quase só com diferenças pequenas. Nos 30 casos com frenagem de 5 a
15 m de diferença, E3 e E4 dão skill +0,46 e +0,64. Mas 30 casos é pouco para
afirmar qualquer coisa.

---

## 4. Leitura (hipóteses)

- **As diferenças acionáveis entre voltas parecidas são pequenas demais para
  separar sinal de ruído.** Num par típico, as duas voltas freiam a menos de 5 m
  uma da outra e passam a menos de 0,5 m no ápice. Nessa escala, o tempo na
  janela depende mais de detalhes de execução que essas 5 entradas não
  descrevem: modulação do freio, escorregamento, pequenas correções de volante.
- **O teto mostra onde está a informação.** Com velocidade mínima e de saída, o
  erro cai 38 %. A velocidade é o *resultado* da execução, não uma instrução que
  o coach possa dar. A distância entre o teto e o E3/E4 é o que falta descrever
  em termos acionáveis.
- **O viés positivo é o mesmo em todos** (+0,01 a +0,02 s por janela). A volta
  mais rápida do par é mais rápida em quase toda janela por algo que as
  entradas acionáveis não capturam. É coerente com a leitura acima.
- **O ridge ficou quase sempre no maior α testado (1000).** Ele encolheu os
  coeficientes até perto de zero: nenhuma relação linear estável foi achada. O α
  ficou no limite da grade pré-registrada; não ampliei a grade depois de ver o
  resultado.

---

## 5. Limitações

- **Concentração.** 82 % dos casos avaliados vêm de uma sessão. Sem as duas
  dominantes sobram 31 voltas e 201 casos, e os resultados mudam de sinal.
- **Pares dependentes.** Cada volta entra em muitos pares. O IC é por sessão,
  com 5 a 8 grupos, e por isso é largo.
- **O filtro de combustível descarta a maior parte dos pares** (9 312
  pares-janela). Ele foi fixado antes, na Fase 2.
- **Janelas variam entre rodadas.** É o preço de não vazar informação do teste.
  O recorte "por janela" no JSON mistura definições; ele não é usado para
  decidir nada.
- **GP subamostrado** (até 300 pares por janela e rodada). Com mais pontos, o
  resultado do E4 poderia mudar; não testado.
- **Um piloto, um carro, uma pista.**

---

## 6. Quando o ganho estimado não é confiável (medido)

| situação | evidência |
|---|---|
| qualquer previsão pontual, sem abstenção | nenhum candidato passa; melhor skill +0,11 |
| poucos dados (sem as dominantes) | E4 skill −0,61, faixa de 95 % acerta 36 % |
| entradas fora da distribuição de treino | faixas acertam 63–72 % |
| E2 linear em qualquer cobertura | skill negativo de 20 % a 100 % de cobertura |

Onde há sinal (medido, mas secundário pela regra): E4 respondendo só quando a
faixa exclui zero, com todas as sessões no treino. São 12,6 % dos casos, skill
+0,59, e não se repete sem as dominantes.

---

## 7. Arquivos

| arquivo | conteúdo |
|---|---|
| `backend/ml/requirements.txt` | `scikit-learn==1.6.1` (commit `ecde4190`) |
| `backend/ml/validation/empirical.py` | janelas, entradas, pares, E2–E4, abstenção, risco × cobertura, calibração |
| `backend/ml/scripts/validate_empirical.py` | execução e regra de decisão (pré-registro, commit `2c792a01`) |
| `backend/tests/test_ml_empirical.py` | 8 testes sintéticos |
| `docs/handoff/2026-10-02_fase2b.patch` | diff contra `handoff/coach-mapeamento` |
| `docs/handoff/2026-10-02_fase2b_testes.txt` | saída completa do pytest |
| `docs/handoff/2026-10-02_fase2b_resultados.json` | todos os números, hashes dos dados e ambiente |

Reproduzir: `cd backend && python -m ml.scripts.validate_empirical` (748 s).

Reutilizado sem duplicar:

- filtros, métricas, bootstrap e critérios de `ml/validation/counterfactual.py`;
- limiares de pedal e auxiliares de janela de `ml/comparison/lap_vs_reference.py`;
- curvas de `ml/track/corners.py`;
- simulador e envelope existentes, para o E1 e o filtro de incidente.

Nenhuma LSTM foi retreinada; `optimal.json`, interface e algoritmo evolutivo
não foram tocados.
