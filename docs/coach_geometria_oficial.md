# Coach na geometria oficial (ADR 0013)

Relatório de 2026-10-03. Branch `etapa/coach-geometria-oficial`, a partir de
`etapa/coach-referencia-real`. **Sem merge.** Dois motivos para parar antes do
passo 9:

- o critério (c) falhou (seção 4);
- muitas sessões foram pilotadas pela IA do Assetto Corsa, e o modelo do coach
  só pode ser treinado depois de as voltas serem rotuladas como humano ou IA
  (pedido do Eduardo durante a etapa).

Nenhum modelo do coach foi treinado ou regravado, nem no repositório nem no app
instalado.

---

## 1. O problema

O coach recortava a volta pelo progresso `p` gravado pelo runtime. Isso tem três
problemas, já medidos:

1. **Três réguas misturadas.** O modelo em uso mistura alvos de sessões
   gravadas com três geometrias diferentes.
2. **As voltas de 09/08 ficavam de fora.** Elas não têm `p`.
3. **Escolher um cache só deixaria quase tudo de fora.**

## 2. A mudança

### Geometria oficial exportada

`python -m ml.scripts.export_geometry` grava
`data/reference_models/<pista>.geometry.json`, fora do git. O arquivo traz:

- a grade de `load_geometry` (x, z, s, 2167 pontos de 2 m);
- as normais, com convenção à esquerda;
- as 61 fronteiras dos 60 microsetores de mesma distância;
- o comprimento da pista e o `geometry_id` (`0ed16f0dd2225990`).

O backend só lê esse arquivo (`core/assisted_analysis/official_geometry.py`) e
não importa o pacote `ml`. O arquivo é recusado se não tiver `geometry_id` ou se
as fronteiras não forem de mesma distância.

### Projeção: reaproveitada

O coach usa o `MapMatchingEngine` que já existia em `core/spatial_engine.py`,
trocando só a geometria: ele recebe a grade oficial no lugar da linha central do
runtime. O motivo da escolha:

- **Ele já faz o que o pedido exige.** Tem desempate por continuidade (penaliza
  candidatos longe do último `s`, o que separa a reta dos boxes do retorno) e
  trata a passagem pela linha de chegada.
- **O `ProjectionEngine` de `core/projection/` não serve.** Ele aceita outra
  geometria, mas não tem continuidade nenhuma.

Duas adaptações finas, no `CoachProjector`:

- **`s` volta para a régua exportada por um fator único (1,00755).** A grade do
  ML é a soma das cordas da linha suavizada, reescalada para os 4334,08 m
  declarados.
- **`d` passa para a convenção do ML** (positivo à esquerda) pela única função
  que faz isso, `to_left_positive` (ADR 0003).

### Treino do modelo

- **Com `geometry=`,** `build_reference_model` reprojeta cada volta pela posição
  no mundo e ignora o `p` gravado. Entram voltas de qualquer cache, inclusive as
  de 09/08, e os microsetores são as 60 fronteiras exportadas. O modelo grava o
  `geometry_id`.
- **Sai a regra da "geometria da maioria".**
- **O modelo lista as 5 voltas válidas mais rápidas,** com o motivo de cada uma
  ter sido escolhida como referência ou não.
- **Achado no primeiro treino:** uma volta em que o carro saiu 43 m da pista fez
  a projeção pular 120 m e deu microsetores de 0,009 s, e a soma dos melhores
  trechos caiu para 72 s. Agora uma volta cuja projeção salta mais de 30 m a
  mais de 120 m/s (432 km/h) fica fora do modelo, com motivo
  `projection_jump`. Isso foi corrigido em commit separado, sem mexer nos
  critérios.
- **O carregador do app (`LapDataLoader`) ganhou `load_recorded_laps`.** Ele lê
  cada sessão uma vez só. A versão de uma volta passou a chamá-la, então a
  regra existe num só lugar, e numa volta real o resultado é idêntico ao do
  código antigo. Treinar com as 642 voltas levou 455 s; antes, ~19 s por volta.

### Ao vivo

- **Se o modelo tem `geometry_id`,** o coach calcula o progresso pela posição no
  mundo (`world_x`, `world_z`), projetada na geometria oficial.
- **Se a geometria falta ou é outra,** fica em silêncio e avisa uma vez no log.
- **Um modelo sem `geometry_id`** segue pelo `p`, como antes.
- **O replay do coach** (`coach_recorded_lap`) usa a mesma projeção.
- **Mapa, painel ao vivo e mapa do replay** não mudaram.

### "Ganho estimado" do `feedback_generator.py`

O número vem de `CornerComparison.estimated_gain()`, que é o
`segment_time_delta_s`: a diferença **medida** entre o tempo da curva na volta e
na volta de referência real (a melhor volta pessoal, `_load_reference`). Não vem
do simulador nem da soma dos melhores trechos. Por isso o número fica, e só o
rótulo muda (ADR 0012):

| arquivo e linha | antes | agora |
|---|---|---|
| `core/assisted_analysis/feedback_generator.py:33` | " Ganho estimado: 0.120s." | " Diferenca medida para a volta de referencia nesta curva: 0.120s." |
| `core/assisted_analysis/feedback_generator.py:45–46` | "Maior oportunidade em T4: … Ganho total estimado 0.480s." | "Maior diferenca para a volta de referencia em T4: … Soma das curvas em que ficou atras: 0.480s." |

Uma ressalva: dentro de uma curva, o total é repartido entre os erros
proporcionalmente à severidade (`driver_error_classifier.py:63`). Essa divisão é
heurística. A soma por curva é medida, e é ela que aparece nos textos. No
frontend, esses números aparecem sob rótulos neutros ("Summary", "Main Losses",
"Corner Diagnostics"), sem a palavra "ganho".

### Coach desligado na sessão controlada

**Não existe hoje um jeito de desligar ou esconder o coach.** O `main.py` sempre
o inscreve nos frames, e o painel "AI Coaching" fica numa faixa fixa
(`Dashboard.tsx:159`). Não criei nada na interface, e o "(a preencher)" do
protocolo continua lá. As opções mais simples estão no relatório (seção 6).

## 3. Testes

- **`backend/tests/test_coach_official_geometry.py` (13 testes):**
  - o projetor na pista circular devolve `s` e `d` conhecidos, e passa pela
    linha de chegada sem saltar;
  - num "clipe" com duas retas a 10 m uma da outra, a continuidade mantém o
    carro na própria reta;
  - o arquivo de geometria faz a volta completa (gravar e ler) e é recusado se
    estiver quebrado;
  - uma volta sem `p` (formato de 09/08) entra no modelo;
  - voltas com `p` de réguas diferentes entram no mesmo modelo;
  - os motivos das 5 voltas mais rápidas aparecem;
  - uma volta com salto de projeção fica de fora;
  - com geometria ausente ou com outro `geometry_id`, o coach fica em silêncio
    e avisa uma vez;
  - o replay usa a mesma projeção.
- **Suítes:** backend **460 passed**, frontend **136 passed**.

## 4. Validação (critérios fixados antes de rodar)

Script: `backend/tools/validate_coach_geometry.py`. O código e os critérios foram
commitados antes da primeira execução (`7cae8f2e`).

| | critério | medido | resultado |
|---|---|---|---|
| **a** MergeFix (`2026-06-20_13-13-02`, 39 voltas, 195 350 amostras) | p99 \|Δs\| ≤ 0,5 m, p99 \|Δd\| ≤ 0,2 m | \|Δs\| p99 **0,037 m** (máx. 28,2 m); \|Δd\| p99 **0,0019 m** (máx. 0,61 m) | passou |
| **a** cache atual (`2026-08-16_03-30-14`, 7 voltas, 36 549 amostras) | idem | \|Δs\| p99 **0,037 m** (máx. 7,8 m); \|Δd\| p99 **0,0016 m** (máx. 0,17 m) | passou |
| **a** sem cache (`2026-08-09_19-20-59`, 52 voltas, 271 245 amostras) | idem | \|Δs\| p99 **0,036 m** (máx. 28,1 m); \|Δd\| p99 **0,0019 m** (máx. 0,18 m) | passou |
| **b** tempo por amostra (582 527 amostras) | p99 ≤ 1 ms | p50 0,30 ms, **p99 0,74 ms**, máx. 14,9 ms | passou |
| **c** microsetores do coach × store, 5 voltas de 5 sessões | máx. ≤ 0,02 s por microsetor; soma = tempo de volta ± 0,02 s | máx. por microsetor **0,026 a 0,078 s**; soma − tempo de volta **+0,026 s** em todas | **falhou** |
| **d** ensaio em duas sessões inteiras | nenhuma frase com "ganh", "ideal" ou "otimo" | 294 frases, **0 proibidas**; 20/06: 4,2 frases por volta com fala (máx. 12); 09/08: 7,5 (máx. 11) | passou |

### Por que (c) falhou (diagnóstico, nada corrigido)

1. **Microsetor 0, nas 5 voltas: +0,026 s.** É toda a diferença da soma. O coach
   extrapola a passagem por `s = 0` da geometria oficial a partir da primeira
   amostra da volta (`s ≈ 3,2 m`, com o cronômetro do jogo em zero), e o store
   do ML resolve a linha de outro jeito (rerreferencia o relógio na grade).
   Entre os microsetores 1 e 58, a diferença máxima fica em 2 a 13 ms em quatro
   das cinco voltas.
2. **Uma volta de 20/06: ±0,078 s entre os microsetores 25 e 26, e −0,072 s no
   51**, sempre em pares de sinais opostos: uma fronteira deslocada no tempo. É
   coerente com os desvios isolados da projeção do coach que (a) mostrou (máximo
   de 28 m em amostras isoladas, com p99 de 0,04 m). A continuidade do
   `MapMatchingEngine` é uma penalidade, e não a regra rígida de 60 m do ML.

O ensaio (d) usou um modelo de teste, treinado no scratchpad com as 642 voltas
de todas as pastas. Ele serviu só para exercitar o coach, e não deve ser usado.
As frases estão em `docs/handoff/2026-10-03_coach_geometria_frases.json`.

## 5. Achados que mudam o próximo passo

- **Há uma segunda pasta de gravações.** O script de treino lê também
  `%APPDATA%\Automobilista Telemetria\data\recordings`: 90 sessões, 14 GB, que o
  pipeline do ML nunca leu. A volta de referência do modelo de teste (84,663 s,
  `rec__2026-08-19_22-23-14_vhe_interlagos__32`) e as outras 4 mais rápidas vêm
  de lá. Pelo aviso do Eduardo, essas sessões podem ter a IA pilotando.
- **O app instalado usa o próprio modelo,**
  `%APPDATA%\...\data\reference_models\vhe_interlagos.json`, e o script de
  treino grava lá por padrão (`runtime_root()`). O passo 9 do pedido fala do
  arquivo do repositório. É preciso decidir qual dos dois treinar.
- **O "melhor de todos" ainda está contaminado.** Mesmo sem as 7 voltas com
  salto de projeção, a soma dos melhores trechos do modelo de teste é 78,16 s,
  contra 84,67 s da referência. Dos 5 microsetores com "melhor" abaixo de 90 % da
  referência, 1 é saída de pista (32,9 m além da borda). Os outros 3 ficam
  **dentro** da pista e mesmo assim mostram tempos impossíveis (1,006 s contra
  2,078 s de mediana), o que sugere falha no relógio gravado ou voltas da IA. No
  modo padrão isso não muda a comparação, mas muda o limiar de fala:
  2 × (mediana − melhor) iria a ~2,1 s no S do Senna, e o coach quase nunca
  falaria ali.

## 6. Limitações

- **Duas projeções ao vivo, durante a transição:** a do runtime, para mapa e
  painel, e a do coach (ADR 0013).
- **A continuidade do coach é uma penalidade, e não um limite rígido.** Daí os
  máximos de 28 m em amostras isoladas.
- **A fronteira na linha de chegada** tem convenções diferentes entre o coach e
  o ML (+26 ms no microsetor 0).
- **O carro não é registrado nas gravações.**
