# Relatório do pedido 38: Modelo 2, o erro que custou tempo, as técnicas e o estilo

- **Pedido:** `docs/prompts/2026-10-24_38_modelo2-erro-tecnica-e-estilo.md`, retomado nesta pasta por decisão do Eduardo ("Pare a outra sessão. Retome o 38 nesta pasta", 25/10).
- **Situação:** **parado na Parte H, como o pedido manda,** esperando a rotulagem do Eduardo. As Partes A a H.3 e a Parte I estão feitas. Falta a H.4: a precisão e a revocação, depois dos rótulos.
- **Branch:** `etapa/modelo2-erro-tecnica-e-estilo`, a partir de `develop` (`4782aefb`). **Sem merge em `develop`:** o pedido parou na rotulagem, como no pedido 37. Sem push.
- **Commits** (ver "Os commits" no fim para os do relatório e das saídas):
  - `fcc94f86` docs: pedido 38 (Modelo 2: o erro, as tecnicas e o estilo, nas voltas da IA e do piloto) e as pesquisas de 24/10
  - `2cbac952` Pedido 38, Parte A: o ADR 0023 e o Modelo 2 registrado antes de construir
  - `e8688671` Pedido 38, Parte B: as voltas da IA e do piloto, as taxas no tempo original e as conferencias dos canais
  - `41c1a1f4` Pedido 38, Parte C: as fases das 14 curvas, fixas para todas as voltas
  - `1e043c13` Pedido 38, Parte E: os detectores de tecnica e de erro, com tres estados e a calibracao na IA
  - `a695397d` Pedido 38, Parte D: a perda por fase, o ranking, a cadeia causal e a atribuicao do erro
  - `41a60fe6` Pedido 38, Partes F e G: a assinatura de estilo e o modelo supervisionado leve
  - `96cb0847` Pedido 38, Parte H: o kit de rotulagem, o comando, os testes e as emendas da primeira rodada
  - `53d563f1` Pedido 38, Parte I: a documentacao do Modelo 2, a lista viva e a arquitetura; a conferencia do escorregamento sem os pontos quebrados
  - `d705d43f` Pedido 38, Parte H, parado: as saidas, o kit de rotulagem e o relatorio
- **Arquivos de handoff** (`docs/handoff/`, prefixo `2026-10-24_38_modelo2-erro-tecnica-e-estilo_`):
  - `relatorio.md` (este);
  - `resultados.json` (ADR 0007: o commit, o `geometry_id`, os comandos e os hashes dos arquivos lidos e escritos);
  - `canais_e_conferencias.json` (Parte B), `fases.json` (Parte C), `erros_por_sessao.json` (Parte D), `tecnicas.json` (Parte E), `estilo.json` (Parte F) e `modelo_leve.json` (Parte G);
  - `kit_rotulagem.html` e `rotulagem.csv` (Parte H);
  - `pytest.txt` (a suíte do backend).

## Resumo

1. **Parte A** (`2cbac952`): o ADR 0023 em `docs/decisoes/`, a linha no índice, o anexo apagado, e a seção 1 de `docs/modelo2_tecnica_e_estilo.md`, registrada antes de rodar nas voltas.
2. **Os dados:**
   - 144 voltas rotuladas: 130 minhas e 14 da IA;
   - 10 delas vêm de gravações posteriores ao store v2, lidas sem mexer nele: 9 minhas de 24/10 e a volta da IA de 22/10;
   - a minha melhor volta (86,568 s) é de 24/10, fora do store.
3. **Os canais conferem**, com os sinais da M1. O escorregamento do jogo é **combinado** (longitudinal e lateral). O carro **não tem ABS ligado** (`carState.abs` = 0 em todas as amostras lidas).
4. **As fases** das 14 curvas são fixas para todas as voltas, e as 70 fases somam a volta inteira (diferença 0,000 s).
5. **Erros por sessão:**
   - **pela regra registrada,** o primeiro item é sempre a **consistência**, porque o desvio da minha volta passa de 1 s em todas as sessões. Depois vêm as perdas nas duas retas longas, que o peso pela reta seguinte põe à frente;
   - **sem o peso (só informativo),** aparecem a **frenagem antecipada na C04** (34 a 44 m antes da IA), **um trecho sem pedal no meio da C10** e **a deriva acima da IA no meio da C01** (21/10).
6. **Técnicas:**
   - **a IA freia forte em C02, C06 e C08,** onde eu quase nunca freio, e chega ao pico do freio em 0,03 s na mediana (eu, em 0,48 s);
   - **eu deixo o carro sem pedal na entrada** de C04, C06, C07, C10 e C12 (80% a 98% das passagens, contra 7% a 8% da IA);
   - o meu ponto de frenagem fica dentro da faixa da IA em 0% a 21% das passagens, exceto na C10 (86%).
7. **O estilo:** a IA é quase binária no freio (5,6% das amostras com freio intermediário, contra 13,5% minhas) e corrige mais o volante nas curvas lentas. Na forma da curva (V ou U), não há diferença.
8. **O modelo leve:** R² de −0,29 a 0,68 deixando uma sessão de fora. O tempo sem pedal e o uso da aderência aparecem com sinal estável na maioria das curvas.
9. **Parte H:** o kit de 120 passagens está pronto. **Parei aqui.**

## Antes de começar: a parada de 00:41 e a retomada

- **A ordem dos pedidos:**
  - o pedido 38 pedia para começar depois que o 37 fechasse; o 37 estava parado. Perguntei, e você respondeu "começar o 38 já";
  - às 00:09 apareceu o pedido 39, dizendo que o 38 vinha depois dele. Perguntei de novo, e você respondeu "seguir com o 38".
- **A colisão:** às 00:40 a sessão do pedido 39 trocou a branch desta mesma pasta, e o meu commit dos documentos (`f38f89a5`) caiu em `etapa/m1-modelo-do-carro`. Parei e gravei o relatório de parada.
- **A retomada, depois do seu "retome o 38 nesta pasta":**
  - **a outra sessão** já estava parada (sem turno em andamento desde 01:00), então não houve nada a interromper;
  - **trouxe o commit dos documentos para a branch do 38 com `cherry-pick`** (`fcc94f86`, o mesmo conteúdo). O `f38f89a5` continua na branch do 37 e do 39 e entra em `develop` com o merge dela;
  - **a lista viva:** a linha que o Cowork acrescentou às 01:07 (sem commit) foi guardada e vai neste pedido junto com as minhas atualizações.
- **Possível conflito no merge:** a lista viva foi mudada nas duas branches. No merge da segunda em `develop`, ela pode precisar de uma resolução à mão.
- **A sua mensagem colada às 04:40** (o instalador 0.5.0, a sessão de medição, as Partes D e E da M1) era para a sessão do pedido 39, como você confirmou. Não fiz nada dela aqui.
- **A cada commit,** conferi que a pasta continuava na branch do 38.

## Parte A: registrado antes de construir

- **Commit:** `2cbac952`, antes de qualquer conta nas voltas. Só tinham sido lidos os metadados (quais voltas e canais existem) e o `isAIControlled` das gravações de fora do store, para saber quem pilotou.
- **O que a seção 1 fixa além do pedido:**
  - **as voltas de fora do store** entram com as funções do store, a origem pelo indicador e o relógio conferido contra o tempo do jogo (±0,05 s);
  - **as fases:** b_k = min(mediana da IA, percentil 10 meu) − 10 m, limitado a [e_(k−1), a_k]; o meio é o trecho com |curvatura| ≥ 0,6 × a maior;
  - **os 27 detectores,** com o tipo P (limiar fixo; a IA só alarga a faixa de dúvida) e o tipo C (limiar relativo à IA da mesma curva);
  - **o subesterço com a medida substituta:** L = 2,955 m e k_δ = 0,267 rad, do retrato da memória do pedido 39 (Parte B), até a M1 medir;
  - **a atribuição:** o detector explica se eu e a IA diferimos, se a minha melhor volta concorda com a IA e se a diferença passa de 1 desvio meu;
  - **os tipos de curva:** lenta abaixo de 120 km/h, média de 120 a 180 e rápida acima de 180, pela mínima da IA. O 180 é escolha minha;
  - **o modelo leve:** ridge com a sessão centrada, porque o statsmodels (efeitos mistos) não está instalado e o pedido proíbe instalar;
  - **o que se espera:** "as maiores perdas contra a IA estão na frenagem e na entrada das curvas lentas que alimentam retas longas (C01, C04 e C10), explicadas pelo ponto de frenagem antecipado e por uma soltura em degrau sem trail braking, que a IA aplica na maioria das curvas com frenagem e eu em poucas".
- **O que veio depois** está na seção 2 do documento, com a data: uma correção de código, uma regra nova para o escorregamento quebrado, um ranking informativo e três limitações (ver "As emendas" abaixo).

## Parte B: os dados, os canais e as conferências

### As voltas

| grupo | voltas | onde | guinada e velocidades no carro | temperatura dos freios | cargas, escorregamento, pneus, volante, pedais, marcha |
|---|---:|---|---|---|---|
| minhas, 04/10 a 13/10 | 76 | store v2 | não | não | sim |
| minhas, 15/10 a 21/10 (as 5 sessões da M1) | 45 | store v2 | sim | sim | sim |
| minhas, 24/10 | 9 | fora do store | sim | sim | sim |
| IA, 04/10 | 13 | store v2 | não | não | sim |
| IA, 22/10 | 1 | fora do store | sim | sim | sim |

- **A lista por volta,** com os 9 canais, está em `canais_e_conferencias.json` (`voltas`).
- **As minhas voltas do store** são 121, e não 127: o filtro da evolução tira as de relógio suspeito.
- **As gravações de fora do store:**
  - **22/10 09:46:** a volta 1 é misturada (78% IA) e fica fora; a 2 é da IA e entra (89,106 s na grade, 89,104 s no jogo); a 3 é parcial;
  - **24/10 13:26:** 3 voltas válidas;
  - **24/10 13:43:** 6 voltas válidas, com a minha melhor (86,568 s). As outras caem nos portões de qualidade (box, parada, pista incompleta).

  O tempo da grade e o do jogo diferem em no máximo 0,002 s nas 10 voltas que entraram.
- **A volta da IA de 22/10 levou 89,1 s,** 4,3 s mais que as de 04/10 (84,8 a 85,2 s). Ela é a única referência da IA para o subesterço, o sobresterço e o contraesterço. Não sei com que nível de força ela andou.

### As conferências

| conferência | resultado |
|---|---|
| volante em linha reta (\|a_y\| < 0,05 g, acima de 100 km/h) | média 0,00001 (minhas, 22.141 pontos) e 0,00008 (IA); p5 a p95 de −0,009 a +0,009. O pico típico nas curvas é 0,47, então o desvio fica abaixo de 2% |
| sinais nas 14 curvas, perto do ápice, com \|a_y\| ≥ 0,5 g | **batem em todas.** À esquerda (C01): volante −0,36, guinada +0,66 rad/s, a_y +1,90 g, v_lat −1,28 m/s. À direita (C10): volante +0,41, guinada −0,79, a_y −1,92 g, v_lat +0,33. O volante é positivo à direita, e a guinada, a_y e a `localVelocity.x` são positivas à esquerda, como na M1 |
| unidade do volante e entre-eixos | **a M1 (pedido 37) não identificou** `L` nem `k_δ`. O retrato do pedido 39 dá L = 2,955 m (a reportagem dá 2,943 m, +0,4%) e k_δ = 0,267 rad, com L/k_δ = 11,07. A razão volante ÷ curvatura nas minhas voltas é 11,0 m entre 10 e 20 m/s (195 pontos), 12,6 entre 20 e 30, 12,8 entre 30 e 45 e 13,5 acima de 45 m/s. Em baixa velocidade, ela bate com L/k_δ; em alta, cresce, como o subesterço manda |
| escorregamento | **combinado.** Medianas (dianteiro / traseiro): frenagem em reta 0,19 / 0,18; curva sem pedal (≥ 1 g) 0,68 / 0,59; curva com acelerador parcial 0,63 / 0,47; reta com o pé embaixo 0,05 / 0,13. O canal sobe na curva sem pedal, onde só há escorregamento lateral, e também na frenagem em reta e na tração (traseiro 0,13 contra 0,05 no dianteiro, com o pé embaixo), onde ele é longitudinal. Por isso, os detectores de travamento e de patinação só leem trechos em linha reta ou comparam com a IA no mesmo trecho |
| ABS | **sem ABS ligado:** `carState.abs` = 0 e `carState.tc` = 0 em todas as amostras lidas (22/10, 21/10 e 24/10). Na frenagem forte em reta (freio ≥ 0,9 por 0,5 s ou mais, 37 trechos), o escorregamento dianteiro oscila cerca de 9 vezes por segundo (p90 de 11,5), com máximo típico de 0,40. A grade de 2 m só resolve até ~12 Hz, então isso não prova nem descarta ciclos de ABS; o ajuste gravado é o dado mais forte |

### A sessão nova da IA, em níveis de força: os passos para você

**Ainda não existe.** Os detectores que precisam da guinada ficam com uma volta só da IA (22/10). Os passos, com o app do repositório:

1. **Prepare o app do repositório** como nas sessões de teste:

   ```bash
   cd /c/Users/Dokas/Desktop/f1-telemetry-analyzer
   ```

   Suba o app como de costume (o gravador precisa estar ativo).
2. **Para cada nível de força, uma sessão do jogo nova.** O indicador `isAIControlled` liga no Ctrl+C e só desliga quando a sessão do jogo reinicia (`docs/detector_ia.md`). Por isso, cada nível precisa de uma sessão própria.
3. **No Content Manager:** prática sozinho, `rss_formula_rss_3_v6_2026`, Interlagos (`vhe_interlagos`, traçado `gp`). Ajuste:
   - **força da IA:** 100% no primeiro bloco, depois 95% e depois 90%;
   - **agressividade e variação:** fixas e iguais nos três blocos. Sugiro agressividade 50% e variação 0%. Anote o que usar.
4. **No jogo:** com o carro no box, aperte **Ctrl+C** para a IA assumir. Deixe a IA andar **8 voltas completas** sem tocar nos controles. Saia da sessão.
5. **Repita** os passos 3 e 4 para 95% e para 90%.
6. **Anote os blocos** em `docs/experimentos/ia_niveis.csv`, uma linha por gravação, que o código lê:

   ```
   gravacao,volta_de,volta_ate,nivel,agressividade,variacao,anotado_em,observacao
   2026-10-26_10-00-00_vhe_interlagos,0,999,100,50,0,2026-10-26,"IA sozinha, Ctrl+C no box"
   ```

   `gravacao` é o nome da pasta em `data/recordings`. `volta_de` e `volta_ate` são as voltas da gravação, pela ordem no arquivo (0 a 999 = todas).
7. **Me avise.** Rodo `python -m ml.scripts.modelo2 todos` com as gravações novas, e o teste do nível (pedais que só mudam de escala ou que mudam de forma) sai em `tecnicas.json`.

**Um cuidado:** não sei se o nível de força do Content Manager vale para a IA que dirige o carro do jogador depois do Ctrl+C. Se os tempos de volta dos três blocos ficarem iguais, o ajuste não chega a ela, e o teste do nível fica "não conclusivo".

### Os coeficientes da IA (`ai.ini`)

- **Não existe em texto.** A pasta do carro (`D:\SteamLibrary\steamapps\common\assettocorsa\content\cars\rss_formula_rss_3_v6_2026\`) não tem `data/`, só o `data.acd`, que **não abri**.
- **O TRAIL_HINT não é legível.** A verificação "sobreposição de freio e volante contra o TRAIL_HINT" fica só com a medida da sobreposição.
- **Lido do `ui_car.json`:** 729 kg com o piloto. O entre-eixos não aparece lá.

## Parte C: as fases de cada curva

Em metros na geometria oficial (`geometry_id` `0ed16f0dd2225990`, volta de 4.334,1 m). A frenagem vai de b a a, a entrada de a a m1, o meio de m1 a m2, a saída de m2 a e, e a reta seguinte de e ao b da curva seguinte.

| curva | tipo | mínima da IA (km/h) | b | a | m1 | m2 | e | b seguinte | reta seguinte (m) | peso | sem frenagem |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| C01-esq | lenta | 104 | 30 | 224 | 274 | 318 | 334 | 334 | 0 | 0,00 | não |
| C02-dir | lenta | 116 | 334 | 358 | 374 | 406 | 422 | 434 | 12 | 0,09 | não |
| C03-esq | média | 136 | 434 | 434 | 476 | 574 | 692 | 1128 | 436 | 3,39 | sim |
| C04-esq | média | 128 | 1128 | 1312 | 1328 | 1390 | 1402 | 1480 | 78 | 0,61 | não |
| C05-esq | média | 179 | 1480 | 1480 | 1484 | 1602 | 1606 | 1792 | 186 | 1,44 | sim |
| C06-dir | média | 152 | 1792 | 1938 | 2084 | 2132 | 2140 | 2146 | 6 | 0,05 | não |
| C07-dir | lenta | 86 | 2146 | 2246 | 2264 | 2318 | 2334 | 2334 | 0 | 0,00 | não |
| C08-esq | lenta | 92 | 2334 | 2350 | 2364 | 2486 | 2498 | 2498 | 0 | 0,00 | não |
| C09-dir | média | 163 | 2498 | 2566 | 2570 | 2622 | 2626 | 2626 | 0 | 0,00 | não |
| C10-dir | lenta | 81 | 2626 | 2672 | 2688 | 2746 | 2758 | 2850 | 92 | 0,72 | não |
| C11-esq | média | 167 | 2850 | 2850 | 2856 | 3014 | 3024 | 3046 | 22 | 0,17 | sim |
| C12-esq | lenta | 98 | 3046 | 3188 | 3204 | 3240 | 3262 | 3334 | 72 | 0,56 | não |
| C13-esq | média | 158 | 3334 | 3334 | 3340 | 3372 | 3380 | 3578 | 198 | 1,54 | sim |
| C14-esq | rápida | 215 | 3578 | 3578 | 3582 | 3662 | 3666 | 30 | 698 | 5,43 | sim |

- **Por que as duas regras** (seção 1.3):
  - a geometria dá a entrada, o meio e a saída iguais para todas as voltas;
  - o pedal, calculado uma vez, põe a frenagem antecipada na fase de frenagem da própria curva, e não na reta da anterior.
- **A C01 começa a frenagem em 30 m,** 194 m antes da curva. É o percentil 10 do meu ponto de frenagem (a mediana minha é 144 m antes do começo da curva; a da IA é 98 m) mais a margem de 10 m.
- **Quatro curvas têm a reta seguinte zerada** (C01, C07, C08 e C09): a curva seguinte começa logo depois. Pela regra, o peso delas é zero (ver a Parte D).
- **Cinco curvas não têm frenagem** (C03, C05, C11, C13 e C14): nem a IA nem eu freamos na maioria das passagens.

## Parte D: os 3 maiores erros por sessão

Contra a volta da IA do coach (`2026-10-04_03-42-10_vhe_interlagos#0013`, 84,829 s). Ao lado, contra a minha melhor volta (`2026-10-24_13-43-32_vhe_interlagos#0003`, 86,568 s). As perdas são medianas das 3 últimas voltas válidas da sessão.

### Pela regra registrada (com o peso da reta seguinte)

| sessão | voltas | 1º | 2º | 3º |
|---|---:|---|---|---|
| 2026-10-04 | 11 | consistência: desvio da volta 2,40 s; frenagem 26,9 m na C01-esq | C14-esq, reta seguinte: +0,62 s (contra a melhor: 0,22 s); não conclusivo | C03-esq, reta seguinte: +0,23 s (contra a melhor: -0,11 s); não conclusivo |
| 2026-10-05 | 7 | consistência: desvio da volta 1,21 s; frenagem 35,5 m na C01-esq | C14-esq, reta seguinte: +0,27 s (contra a melhor: -0,14 s); não conclusivo | C03-esq, reta seguinte: +0,19 s (contra a melhor: -0,14 s); não conclusivo |
| 2026-10-05-2 | 10 | consistência: desvio da volta 3,54 s; frenagem 76,5 m na C09-dir | C14-esq, reta seguinte, origem entrada (cadeia causal): +0,62 s (contra a melhor: 0,21 s); não conclusivo | C03-esq, reta seguinte: +0,40 s (contra a melhor: 0,06 s); não conclusivo |
| 2026-10-09 | 4 | consistência: desvio da volta 2,36 s | C14-esq, reta seguinte: +0,24 s (contra a melhor: -0,17 s); não conclusivo | C03-esq, reta seguinte: +0,18 s (contra a melhor: -0,16 s); não conclusivo |
| 2026-10-10 | 11 | consistência: desvio da volta 7,81 s; frenagem 43,8 m na C12-esq | C14-esq, reta seguinte, origem entrada (cadeia causal): +0,63 s (contra a melhor: 0,22 s); não conclusivo | C03-esq, reta seguinte: +0,37 s (contra a melhor: 0,04 s); M4 largura na saída: eu não aplica, IA aplica, -4,14 (-1,47 desvios) |
| 2026-10-11 | 16 | consistência: desvio da volta 1,26 s; frenagem 23,2 m na C01-esq | C14-esq, reta seguinte, origem entrada (cadeia causal): +0,69 s (contra a melhor: 0,28 s); não conclusivo | C03-esq, reta seguinte: +0,20 s (contra a melhor: -0,14 s); M4 largura na saída: eu não aplica, IA aplica, -6,68 (-1,79 desvios) |
| 2026-10-13 | 7 | consistência: desvio da volta 0,98 s; frenagem 23,8 m na C01-esq | C14-esq, reta seguinte, origem entrada (cadeia causal): +0,67 s (contra a melhor: 0,26 s); não conclusivo | C03-esq, reta seguinte: +0,35 s (contra a melhor: 0,01 s); não conclusivo |
| 2026-10-16 | 11 | consistência: desvio da volta 3,44 s; frenagem 28,6 m na C01-esq | C14-esq, reta seguinte: +0,25 s (contra a melhor: -0,16 s); não conclusivo | C03-esq, reta seguinte: +0,14 s (contra a melhor: -0,20 s); não conclusivo |
| 2026-10-17 | 11 | consistência: desvio da volta 2,24 s; frenagem 20,0 m na C04-esq | C14-esq, reta seguinte: +0,25 s (contra a melhor: -0,16 s); não conclusivo | C03-esq, reta seguinte: +0,31 s (contra a melhor: -0,03 s); M4 largura na saída: eu não aplica, IA aplica, -2,78 (-1,91 desvios) |
| 2026-10-17-2 | 15 | consistência: desvio da volta 3,77 s; frenagem 31,6 m na C01-esq | C14-esq, reta seguinte, origem entrada (cadeia causal): +0,67 s (contra a melhor: 0,26 s); não conclusivo; nunca mostrada: M1 | C03-esq, reta seguinte: +0,53 s (contra a melhor: 0,19 s); M4 largura na saída: eu não aplica, IA aplica, -2,30 (-1,18 desvios) |
| 2026-10-18 | 9 | consistência: desvio da volta 1,58 s; frenagem 15,8 m na C04-esq | C14-esq, reta seguinte: +0,63 s (contra a melhor: 0,22 s); não conclusivo | C03-esq, reta seguinte, origem entrada (cadeia causal): +0,37 s (contra a melhor: 0,03 s); não conclusivo |
| 2026-10-21 | 9 | consistência: desvio da volta 2,20 s; frenagem 26,4 m na C04-esq | C14-esq, reta seguinte: +0,28 s (contra a melhor: -0,13 s); não conclusivo | C03-esq, reta seguinte: +0,19 s (contra a melhor: -0,15 s); não conclusivo |
| 2026-10-24 | 9 | consistência: desvio da volta 1,48 s; frenagem 20,3 m na C04-esq | C14-esq, reta seguinte, origem entrada (cadeia causal): +0,48 s (contra a melhor: 0,07 s); não conclusivo | C03-esq, reta seguinte: +0,49 s (contra a melhor: 0,15 s); M4 largura na saída: eu não aplica, IA aplica, -8,32 (-4,57 desvios) |

**A leitura:**

- **Consistência primeiro, em todas as sessões.** O desvio do meu tempo de volta vai de 0,98 s (13/10) a 7,8 s (10/10). O desvio do meu ponto de frenagem passa de 15 m em pelo menos uma curva em todas as sessões com 5 voltas ou mais.
- **As duas retas longas** (depois da C14, peso 5,4; depois da C03, peso 3,4) ficam com os outros dois lugares em todas as sessões.
  - **A reta principal:** o detector da fase (largura, retomada e alívio) não explica, então dá "não conclusivo".
  - **A reta oposta:** em 5 sessões, a explicação é a **largura na saída da C03** (M4): eu fico de 2,3 a 8,3 m mais perto do centro que a IA.

### Informativo: os 3 de maior perda, sem o peso

Fora da regra registrada (seção 2 do documento). A atribuição é a mesma.

| sessão | voltas | 1º | 2º | 3º |
|---|---:|---|---|---|
| 2026-10-04 | 11 | C14-esq, reta seguinte: +0,62 s (contra a melhor: 0,22 s); não conclusivo | C01-esq, frenagem: +0,57 s (contra a melhor: 0,37 s); não conclusivo; nunca mostrada: F1, F2 | C12-esq, frenagem: +0,55 s (contra a melhor: 0,04 s); não conclusivo; nunca mostrada: F1, F2 |
| 2026-10-05 | 7 | C01-esq, frenagem: +0,46 s (contra a melhor: 0,27 s); não conclusivo; nunca mostrada: F1, F2 | C07-dir, frenagem: +0,45 s (contra a melhor: 0,38 s); não conclusivo; nunca mostrada: F1, F2 | C12-esq, frenagem: +0,44 s (contra a melhor: -0,07 s); não conclusivo; nunca mostrada: F1, F2 |
| 2026-10-05-2 | 10 | C12-esq, frenagem: +0,84 s (contra a melhor: 0,33 s); não conclusivo; nunca mostrada: F1, F2 | C01-esq, frenagem: +0,79 s (contra a melhor: 0,59 s); F3 perfil com carga aerodinâmica: eu aplica, IA não aplica, 0,32 (1,92 desvios); nunca mostrada: F1, F2 | C14-esq, reta seguinte, origem entrada (cadeia causal): +0,62 s (contra a melhor: 0,21 s); não conclusivo |
| 2026-10-09 | 4 | C01-esq, frenagem: +0,75 s (contra a melhor: 0,56 s); não conclusivo; nunca mostrada: F1, F2 | C12-esq, frenagem: +0,66 s (contra a melhor: 0,15 s); F3 perfil com carga aerodinâmica: eu aplica, IA não aplica, 0,17 (2,05 desvios); nunca mostrada: F1, F2 | C11-esq, meio: +0,57 s (contra a melhor: 0,31 s); não conclusivo |
| 2026-10-10 | 11 | C01-esq, frenagem: +0,77 s (contra a melhor: 0,58 s); F3 perfil com carga aerodinâmica: eu aplica, IA não aplica, 0,12 (3,95 desvios); nunca mostrada: F1, F2 | C12-esq, frenagem: +0,69 s (contra a melhor: 0,17 s); não conclusivo; nunca mostrada: F1, F2 | C14-esq, reta seguinte, origem entrada (cadeia causal): +0,63 s (contra a melhor: 0,22 s); não conclusivo |
| 2026-10-11 | 16 | C14-esq, reta seguinte, origem entrada (cadeia causal): +0,69 s (contra a melhor: 0,28 s); não conclusivo | C12-esq, frenagem: +0,48 s (contra a melhor: -0,03 s); não conclusivo; nunca mostrada: F1, F2 | C01-esq, frenagem: +0,37 s (contra a melhor: 0,17 s); não conclusivo; nunca mostrada: F1, F2 |
| 2026-10-13 | 7 | C01-esq, frenagem: +0,72 s (contra a melhor: 0,53 s); F3 perfil com carga aerodinâmica: eu aplica, IA não aplica, 0,21 (2,46 desvios); nunca mostrada: F1, F2 | C14-esq, reta seguinte, origem entrada (cadeia causal): +0,67 s (contra a melhor: 0,26 s); não conclusivo | C12-esq, frenagem: +0,54 s (contra a melhor: 0,03 s); não conclusivo; nunca mostrada: F1, F2 |
| 2026-10-16 | 11 | C10-dir, reta seguinte, origem entrada (cadeia causal): +0,48 s (contra a melhor: 0,32 s); M5 fase sem pedal: eu aplica, IA não aplica, 1,02 (1,06 desvios); nunca mostrada: F2, E1 | C12-esq, frenagem: +0,43 s (contra a melhor: -0,08 s); F3 perfil com carga aerodinâmica: eu aplica, IA não aplica, 0,16 (2,68 desvios); nunca mostrada: F1, F2 | C04-esq, frenagem: +0,32 s (contra a melhor: 0,21 s); F1 referência de frenagem: eu não aplica, IA aplica, -44,00 (-2,58 desvios); nunca mostrada: F2, F7 |
| 2026-10-17 | 11 | C12-esq, frenagem: +0,55 s (contra a melhor: 0,04 s); F3 perfil com carga aerodinâmica: eu aplica, IA não aplica, 0,21 (2,96 desvios); nunca mostrada: F1, F2 | C04-esq, frenagem: +0,52 s (contra a melhor: 0,40 s); F1 referência de frenagem: eu não aplica, IA aplica, -34,00 (-1,91 desvios); nunca mostrada: F7 | C01-esq, frenagem: +0,44 s (contra a melhor: 0,24 s); não conclusivo; nunca mostrada: F1 |
| 2026-10-17-2 | 15 | C14-esq, reta seguinte, origem entrada (cadeia causal): +0,67 s (contra a melhor: 0,26 s); não conclusivo; nunca mostrada: M1 | C12-esq, frenagem: +0,58 s (contra a melhor: 0,07 s); não conclusivo; nunca mostrada: F1 | C01-esq, frenagem: +0,57 s (contra a melhor: 0,38 s); não conclusivo; nunca mostrada: F1, F2 |
| 2026-10-18 | 9 | C14-esq, reta seguinte: +0,63 s (contra a melhor: 0,22 s); não conclusivo | C12-esq, frenagem: +0,41 s (contra a melhor: -0,10 s); não conclusivo; nunca mostrada: F1, F2 | C01-esq, frenagem: +0,40 s (contra a melhor: 0,21 s); F3 perfil com carga aerodinâmica: eu aplica, IA não aplica, 0,12 (3,08 desvios); nunca mostrada: F1, F2 |
| 2026-10-21 | 9 | C01-esq, meio: +0,82 s (contra a melhor: 0,78 s); E3 sobresterço: eu aplica, IA não aplica, 6,10 (5,37 desvios) | C12-esq, frenagem: +0,41 s (contra a melhor: -0,10 s); não conclusivo; nunca mostrada: F1, F2 | C14-esq, reta seguinte: +0,28 s (contra a melhor: -0,13 s); não conclusivo |
| 2026-10-24 | 9 | C03-esq, reta seguinte: +0,49 s (contra a melhor: 0,15 s); M4 largura na saída: eu não aplica, IA aplica, -8,32 (-4,57 desvios) | C14-esq, reta seguinte, origem entrada (cadeia causal): +0,48 s (contra a melhor: 0,07 s); não conclusivo | C10-dir, meio: +0,38 s (contra a melhor: 0,19 s); M5 fase sem pedal: eu aplica, IA não aplica, 0,91 (5,06 desvios) |

**A leitura:**

- **A frenagem da C01 e da C12** está entre as 3 maiores perdas em quase todas as sessões (0,4 a 0,8 s por passagem).
  - Os detectores que mais diferem são a referência de frenagem (F1) e a frenagem no limiar (F2). Eles dão "técnica nunca mostrada": a minha melhor volta também não freia como a IA.
  - Por isso, pela regra, eles não "explicam" o item.
- **A frenagem da C04** (16/10 e 17/10): eu freio 34 a 44 m antes da IA (F1), com a melhor volta fazendo como a IA.
- **A C10** (16/10 e 24/10): um trecho sem pedal (M5) de 0,9 a 1,0 s a mais que a IA, no meio ou na entrada.
- **A C01, no meio** (21/10): a deriva do carro (E3) passa a da IA em 6,1°, ou 5,4 desvios meus. Foi uma escorregada; a perda é de 0,8 s.
- **O falso ganho** (frear mais tarde e perder mais na entrada) não apareceu em nenhuma sessão.

## Parte E: as técnicas da IA e as minhas

**A fração das passagens conclusivas em que cada um aplica**, em %, IA/eu ("—" = nenhuma passagem conclusiva). "Aplica" num detector de erro quer dizer que o erro aconteceu.

| detector | C01 | C02 | C03 | C04 | C05 | C06 | C07 | C08 | C09 | C10 | C11 | C12 | C13 | C14 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| F1 referência de frenagem | 93/6 | 100/1 | —/— | 93/14 | —/— | 93/0 | 93/21 | 100/0 | 62/0 | 100/86 | —/— | 93/1 | —/— | —/— |
| F2 frenagem no limiar | 100/9 | 100/0 | —/— | 100/3 | —/— | 100/0 | 100/0 | 100/0 | 100/100 | 100/1 | —/— | 100/1 | —/— | —/— |
| F3 perfil com carga aerodinâmica | 0/70 | —/0 | —/— | 0/62 | —/100 | 100/27 | 14/66 | 100/50 | —/0 | 100/82 | —/— | 0/66 | —/— | —/— |
| F4 soltura progressiva | 100/100 | 70/100 | —/— | 100/100 | —/100 | 62/100 | 100/100 | 100/100 | 100/100 | 100/100 | —/— | 100/100 | —/— | —/— |
| F5 trail braking | 100/86 | 0/17 | —/— | 0/84 | —/50 | 7/50 | 100/87 | 0/0 | 0/5 | 100/97 | —/— | 100/81 | —/— | —/— |
| F6 travamento | 0/14 | —/— | —/— | 0/7 | —/— | 0/0 | 0/4 | —/— | —/— | 0/1 | —/— | 0/0 | —/— | —/— |
| F7 sobreposição de pedais | 100/94 | —/1 | 0/0 | 0/95 | 0/0 | 100/6 | 50/24 | —/1 | 0/0 | 0/5 | 0/0 | —/84 | 0/0 | 0/0 |
| F8 redução brusca | 0/1 | —/— | 0/0 | 0/1 | —/— | 0/1 | 0/3 | 0/0 | 0/0 | 0/2 | —/— | 0/0 | —/— | 0/0 |
| E1 entrada antecipada | 0/28 | 0/0 | 0/0 | 0/1 | 0/0 | 0/67 | 0/8 | 0/0 | 0/95 | 0/77 | 0/8 | 0/22 | 0/0 | 0/32 |
| E2 subesterço (substituta) | 0/10 | 0/86 | 0/2 | 0/2 | 0/0 | 0/8 | 0/3 | 0/91 | 0/0 | 0/2 | 0/12 | 0/66 | 0/0 | 0/0 |
| E3 sobresterço | 0/17 | 0/54 | 0/16 | 0/40 | 0/0 | 0/93 | 0/37 | 0/2 | 0/16 | 0/50 | 0/8 | 0/32 | 0/0 | 0/4 |
| E4 contraesterço | 0/2 | 0/2 | 0/2 | 0/0 | —/0 | 0/0 | 0/2 | 0/2 | 0/0 | 0/0 | 0/2 | 0/0 | 0/2 | 0/2 |
| E5 reversões do volante | 0/1 | 0/5 | 8/0 | 0/10 | 0/0 | 0/0 | 0/2 | 8/1 | 0/44 | 0/22 | 20/46 | 27/0 | 0/10 | 0/4 |
| E6 suavidade do volante | 100/100 | 100/100 | 100/100 | 100/100 | 100/100 | 100/100 | 100/99 | 100/100 | 100/98 | 100/100 | 100/99 | 100/100 | 100/99 | 100/100 |
| M1 círculo de atrito | 100/96 | 100/95 | 0/8 | 100/94 | 7/0 | 100/99 | 100/73 | 100/98 | 0/1 | 100/93 | 100/94 | 100/81 | 0/0 | 100/51 |
| M2 ápice antecipado | 0/16 | 0/83 | 0/0 | 0/53 | 0/0 | 0/19 | 7/16 | 0/50 | 0/0 | 0/11 | 0/0 | 0/25 | 0/0 | 0/0 |
| M3 forma em U | 100/100 | 100/100 | 0/2 | 100/99 | 0/2 | 100/87 | 100/96 | 100/100 | 100/93 | 100/99 | 0/10 | 100/98 | 0/3 | 100/98 |
| M4 largura na saída | 100/88 | 100/49 | 100/28 | 100/86 | 100/72 | 100/68 | 100/80 | 100/94 | 100/12 | 100/76 | 100/33 | 100/91 | 100/100 | 100/84 |
| M5 fase sem pedal | 100/94 | 0/21 | 0/2 | 7/87 | 7/1 | 7/98 | 8/93 | 79/88 | 0/9 | 7/92 | 0/4 | 7/80 | 0/1 | 0/1 |
| M6 retomada | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/1 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| M7 acelerador cedo | 100/69 | 100/100 | 100/100 | 100/77 | 7/55 | 100/81 | 100/53 | 100/95 | 100/86 | 100/52 | 100/100 | 100/78 | 100/100 | 100/98 |
| M8 alívio | 100/92 | 100/80 | 0/3 | 100/54 | 0/7 | 60/94 | 100/94 | 29/97 | 0/68 | 100/66 | 0/24 | 100/62 | 0/16 | 0/2 |
| M9 patinação | 0/9 | 0/1 | 0/1 | 0/55 | 0/1 | 0/1 | 0/1 | 0/1 | 0/2 | 0/0 | 0/1 | 0/2 | 0/0 | 0/15 |
| V3 transferência brusca | 0/9 | 0/16 | 0/13 | 0/25 | 0/10 | 0/3 | 0/9 | 0/4 | 0/3 | 0/13 | 0/3 | 0/3 | 0/1 | 0/3 |

**As técnicas que a IA aplica e eu não** (IA ≥ 60%, eu ≤ 30%, com 3 passagens conclusivas ou mais de cada lado):

- **referência de frenagem (F1):** C01, C02, C04, C06, C07, C08, C09 e C12;
- **frenagem no limiar (F2):** C01, C02, C04, C06, C07, C08, C10 e C12. A IA chega ao pico do freio em 0,01 a 0,11 s (mediana 0,03 s), com o pedal a 0,99. Eu chego em 0,2 a 0,6 s (mediana 0,48 s), com um pico de 0,25 a 0,76.

  **Cuidado:** o pico do pedal depende do mapeamento do pedal (a escala de 0 a 1). Uma diferença no pico relativo pode ser do equipamento, e não do pé;
- **sobreposição de pedais (F7):** C06;
- **largura na saída (M4):** C03 e C09.

**As que eu aplico e a IA não:**

- **perfil com carga aerodinâmica (F3):** C01, C04, C07 e C12. A IA vai ao pico e fica nele (platô); eu chego ao pico mais devagar e solto antes;
- **trail braking (F5):** C04;
- **fase sem pedal (M5, erro):** C04, C06, C07, C10 e C12;
- **entrada antecipada (E1, erro):** C06, C09 e C10;
- **ápice antecipado (M2, erro):** C02;
- **alívio depois da retomada (M8, erro):** C08 e C09.

**A minha evolução, sessão a sessão** (fração das passagens conclusivas em que eu aplico):

| sessão | F1 referência de frenagem | F4 soltura | F5 trail braking | E1 entrada antecipada | E3 sobresterço | M2 ápice antecipado | M5 sem pedal | M8 alívio |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-10-04 | 1% | 100% | 70% | 21% | — | 34% | 49% | 63% |
| 2026-10-05 | 0% | 100% | 80% | 25% | — | 17% | 50% | 61% |
| 2026-10-05-2 | 1% | 100% | 70% | 24% | — | 26% | 49% | 56% |
| 2026-10-09 | 0% | 100% | 86% | 20% | — | 20% | 49% | 60% |
| 2026-10-10 | 11% | 100% | 79% | 25% | — | 20% | 42% | 57% |
| 2026-10-11 | 12% | 100% | 86% | 22% | — | 13% | 43% | 57% |
| 2026-10-13 | 9% | 100% | 76% | 20% | — | 13% | 50% | 48% |
| 2026-10-16 | 7% | 100% | 67% | 27% | 26% | 20% | 47% | 54% |
| 2026-10-17 | 7% | 100% | 80% | 23% | 14% | 24% | 50% | 54% |
| 2026-10-17-2 | 14% | 100% | 76% | 22% | 19% | 20% | 47% | 49% |
| 2026-10-18 | 3% | 100% | 87% | 18% | 26% | 18% | 46% | 49% |
| 2026-10-21 | 7% | 100% | 87% | 21% | 39% | 10% | 48% | 48% |
| 2026-10-24 | 18% | 100% | 91% | 23% | 36% | 9% | 48% | 42% |

- **Na tendência,** o ápice antecipado (M2) cai de 34% para 9%, o alívio (M8) de 63% para 43%, e o trail braking (F5) sobe de 70% para 91%.
- **O sobresterço (E3)** fica entre 15% e 26% de 16/10 a 18/10 e sobe para 36% a 39% em 21/10 e 24/10.
- **A fase sem pedal (M5)** fica em cerca de 48% em todas as sessões.

**Por volta:**

| detector | eu: aplica / não aplica / não conclusivo | IA |
|---|---|---|
| V1 uso decidido do acelerador | 0 / 118 / 12 | 0 / 14 / 0 |
| V2 rotação de troca | 14 / 19 / 97 | 8 / 2 / 4 |
| V4 pneus na faixa da IA | 29 / 81 / 20 | 13 / 1 / 0 |
| V5 consistência (por sessão e curva) | 4 / 130 / 48 | 14 / 0 / 14 |

### As verificações próprias da IA

- **Os pedais da IA são quase binários no freio:**
  - **freio intermediário** (entre 0,05 e 0,95): 5,6% das amostras da IA, contra 13,5% minhas;
  - **acelerador intermediário:** 18,6% da IA, contra 24,5% meus.
- **A sobreposição de freio e volante da IA**, por curva (mediana): 0,73 s na C01, 0,50 na C04, 0,78 na C07, 0,98 na C08, 0,52 na C10 e 0,83 na C12. O TRAIL_HINT não é legível, então não há o que confrontar.
- **A dispersão volta a volta da IA,** contra a minha:

  | | ponto de frenagem | mínima |
  |---|---|---|
  | **IA** | 0,8 a 14 m na maioria das curvas, e 29 m na C06 | 0,2 a 1,6 km/h, exceto 8,6 km/h na C05 |
  | **eu** | 7 a 43 m | 5 a 16 km/h |

  Pelo desvio, a IA é muito mais consistente que eu.
- **A IA muda de técnica de uma curva para outra:**
  - **trail braking:** em C01, C07, C10 e C12, e não em C02, C04, C06, C08 e C09;
  - **perfil com carga aerodinâmica:** em C06, C08 e C10, e não nas outras.

  Lista completa em `tecnicas.json` (`ia_muda_a_tecnica_entre_curvas`).
- **Os níveis de força:** "não conclusivo", porque a sessão ainda não existe.
- **O rótulo esperado**, "referência consistente, que segue uma linha gravada", tem apoio na dispersão baixa e nos pedais quase binários. O teste do nível falta.

## Parte F: as assinaturas de estilo

Os escores-z são contra todas as passagens rotuladas do mesmo tipo de curva. A consistência fica à parte. Os intervalos de 90% estão em `estilo.json`.

**Curvas lentas (C01, C02, C07, C08, C10 e C12):**

| medida | IA | eu |
|---|---|---|
| tempo perto da mínima (forma U) | 0,93 s (z −0,15) | 1,00 s (z +0,03) |
| mínima ÷ velocidade na frenagem | 0,47 (z −0,15) | 0,53 (z +0,01) |
| pico do freio, relativo ao da IA | 1,00 (z +1,41) | 0,56 (z −0,12) |
| tempo até o pico ÷ duração da frenagem | 0,02 (z −1,54) | 0,21 (z +0,16) |
| taxa no fim da soltura (1/s) | 1,29 (z +1,13) | 0,69 (z −0,11) |
| menor acelerador entre o alívio e a frenagem | 0,14 (z −0,43) | 0,41 (z +0,18) |
| taxa de entrada do volante (1/s) | 1,41 (z +0,60) | 0,86 (z −0,12) |
| reversões do volante | 5 (z +2,70) | 1 (z 0,00) |
| do ápice ao acelerador pleno | 0,94 s (z −0,54) | 1,70 s (z +0,16) |

**Curvas médias:**

- **a IA** chega ao pico em 0,02 da duração da frenagem (z −2,0), solta o freio mais depressa (z +1,1) e corrige mais o volante (9 reversões, z +1,35);
- **eu** fico no centro nas outras medidas.

**A curva rápida (C14):** a IA tem mais volante no pico (z +1,8) e mais reversões (z +1,45). Lá ninguém freia.

**A leitura:**

- **A IA é "pico alto e curto":** o freio vai ao máximo de uma vez e solta depressa, com mais correções de volante.
- **Eu sou "pico menor, zona longa":** chego ao pico devagar, solto devagar e levo mais tempo do ápice ao pleno.
- **Na forma da curva** (V ou U), a IA e eu ficamos iguais (z perto de 0 nos dois).

**A minha assinatura sessão a sessão** (curvas lentas, mediana e z):

| sessão | tempo perto da mínima | tempo até o pico ÷ duração | taxa no fim da soltura | menor acelerador antes da frenagem | taxa de entrada | do ápice ao pleno |
|---|---|---|---|---|---|---|
| 2026-10-04 | 1,01 (z 0,01) | 0,26 (z 0,42) | 0,57 (z -0,30) | 0,29 (z -0,27) | 0,91 (z 0,07) | 2,08 (z 0,32) |
| 2026-10-05 | 0,81 (z -0,50) | 0,23 (z 0,15) | 0,79 (z 0,25) | 0,39 (z -0,05) | 0,96 (z 0,13) | 2,17 (z 0,40) |
| 2026-10-05-2 | 1,02 (z 0,03) | 0,26 (z 0,45) | 0,58 (z -0,27) | 0,34 (z -0,17) | 0,97 (z 0,14) | 1,92 (z 0,19) |
| 2026-10-09 | 0,99 (z -0,02) | 0,22 (z 0,06) | 0,47 (z -0,55) | 0,22 (z -0,43) | 1,22 (z 0,48) | 1,95 (z 0,22) |
| 2026-10-10 | 0,96 (z -0,10) | 0,17 (z -0,40) | 0,62 (z -0,18) | 0,20 (z -0,47) | 0,84 (z -0,04) | 1,66 (z -0,03) |
| 2026-10-11 | 1,04 (z 0,09) | 0,21 (z -0,03) | 0,67 (z -0,05) | 0,60 (z 0,42) | 0,73 (z -0,18) | 1,62 (z -0,07) |
| 2026-10-13 | 1,09 (z 0,22) | 0,27 (z 0,55) | 0,85 (z 0,40) | 0,41 (z -0,00) | 0,88 (z 0,02) | 1,37 (z -0,28) |
| 2026-10-16 | 1,07 (z 0,16) | 0,19 (z -0,17) | 0,82 (z 0,31) | 0,50 (z 0,18) | 0,74 (z -0,16) | 1,80 (z 0,09) |
| 2026-10-17 | 1,04 (z 0,09) | 0,22 (z 0,12) | 0,75 (z 0,14) | 0,31 (z -0,24) | 0,84 (z -0,03) | 1,66 (z -0,03) |
| 2026-10-17-2 | 1,05 (z 0,12) | 0,26 (z 0,50) | 0,88 (z 0,48) | 0,46 (z 0,10) | 0,90 (z 0,05) | 1,82 (z 0,10) |
| 2026-10-18 | 0,96 (z -0,12) | 0,20 (z -0,12) | 0,66 (z -0,07) | 0,30 (z -0,26) | 0,97 (z 0,14) | 1,61 (z -0,08) |
| 2026-10-21 | 0,84 (z -0,41) | 0,18 (z -0,31) | 0,55 (z -0,34) | 0,47 (z 0,13) | 0,81 (z -0,07) | 1,23 (z -0,39) |
| 2026-10-24 | 0,95 (z -0,13) | 0,16 (z -0,45) | 0,73 (z 0,11) | 0,61 (z 0,44) | 0,86 (z -0,00) | 1,46 (z -0,20) |

- **A assinatura muda pouco de sessão para sessão:** os z ficam entre −0,55 e +0,55.
- **A tendência que aparece** é o tempo do ápice ao pleno caindo, de 2,1 s (04/10) para 1,2 a 1,5 s (21/10 e 24/10).
- **É a "assinatura atual",** não um traço fixo.

### Preparação do pedido seguinte: o estilo com dados externos

No máximo 10 medidas, todas razões adimensionais por fase da curva (a primeira classe da pesquisa de datasets). Elas são calculadas por faixa de velocidade e de raio, e não pelo nome da curva:

- **faixa de velocidade:** a mínima da referência, lenta abaixo de 120 km/h, média de 120 a 180 e rápida acima de 180;
- **faixa de raio:** o menor raio da curva, abaixo de 50 m, de 50 a 150 m e acima de 150 m.

| # | medida | canais | na F1 pública (FastF1) |
|---|---|---|---|
| 1 | posição da mínima na curva: (s_vmin − começo)/(fim − começo) | velocidade, posição | sim |
| 2 | mínima ÷ velocidade de entrada | velocidade | sim |
| 3 | tempo perto da mínima (≤ 1,03·v_min) ÷ tempo da curva | velocidade | sim, aproximado a 4 Hz |
| 4 | retomada do acelerador em relação ao ápice: (t_pu − t_vmin) ÷ tempo da curva | acelerador, velocidade | sim (a semântica do acelerador é incerta) |
| 5 | fração da curva do ápice ao acelerador pleno | acelerador, velocidade | aproximado |
| 6 | aceitação do acelerador: \|a_y no pleno\| ÷ maior \|a_y\| da curva | acelerador, aceleração lateral | não (sem acelerômetro) |
| 7 | tempo até o pico de freio ÷ duração da frenagem | freio contínuo | não (freio ligado ou desligado) |
| 8 | fim da soltura em relação à mínima: (t_fim do freio − t_vmin) ÷ duração da frenagem | freio contínuo, velocidade | não |
| 9 | sobreposição de freio e volante ÷ duração da entrada | freio contínuo, volante | não (sem volante); com cautela, porque depende da carga aerodinâmica |
| 10 | fração da curva sem pedal | freio, acelerador | aproximada (freio binário) |

- **Ficam fora do vetor e são relatados à parte,** porque medem habilidade: o uso da aderência (M1), a consistência e o tempo.
- **Também ficam fora** os valores absolutos: metros, km/h, g e o ângulo de volante sem conversão.
- **Contra a F1,** só as medidas 1 a 5 e 10 servem, com as minhas voltas reamostradas a cerca de 4 Hz e o freio binarizado.

## Parte G: o modelo supervisionado leve

Por curva, nas minhas 130 passagens de 13 sessões. Ridge com a sessão centrada, validado deixando uma sessão de fora. Na tabela, os 3 maiores coeficientes com sinal estável, em segundos por desvio, com o intervalo de 90%.

| curva | tipo | passagens | sessões | R² (sessão de fora) | α | maiores coeficientes estáveis |
|---|---|---:|---:|---:|---:|---|
| C01-esq | lenta | 130 | 13 | 0,32 | 0,3 | sem_pedal_s +0,477 [+0,192, +0,600]; s_vmin_rel -0,354 [-0,453, -0,181]; sobreposicao_s +0,304 [+0,111, +0,386] |
| C02-dir | lenta | 130 | 13 | 0,01 | 100,0 | sem_pedal_s +0,032 [+0,014, +0,040]; uso_aderencia -0,027 [-0,035, -0,017]; s_ti_rel +0,016 [+0,006, +0,026] |
| C03-esq | média | 130 | 13 | 0,16 | 10,0 | uso_aderencia -0,125 [-0,153, -0,084]; taxa_carga +0,104 [+0,035, +0,141]; sem_pedal_s +0,092 [+0,053, +0,116] |
| C04-esq | média | 130 | 13 | 0,26 | 0,3 | s_vmin_rel -0,225 [-0,295, -0,143]; sem_pedal_s +0,204 [+0,119, +0,275]; pico_fracao -0,183 [-0,353, -0,006] |
| C05-esq | média | 130 | 13 | 0,35 | 100,0 | taxa_carga +0,057 [+0,029, +0,072]; uso_aderencia -0,044 [-0,056, -0,024]; s_ti_rel +0,036 [+0,019, +0,045] |
| C06-dir | média | 130 | 13 | -0,04 | 100,0 | uso_aderencia -0,111 [-0,137, -0,065]; afastamento_m -0,090 [-0,136, -0,015]; sem_pedal_s +0,062 [+0,001, +0,101] |
| C07-dir | lenta | 130 | 13 | -0,19 | 100,0 | volante_depois +0,065 [+0,007, +0,108]; taxa_carga +0,038 [+0,018, +0,051]; uso_aderencia -0,034 [-0,046, -0,009] |
| C08-esq | lenta | 130 | 13 | 0,16 | 100,0 | taxa_carga +0,125 [+0,037, +0,166]; uso_aderencia -0,092 [-0,121, -0,044]; afastamento_m +0,084 [+0,009, +0,134] |
| C09-dir | média | 130 | 13 | 0,68 | 3,0 | sem_pedal_s +0,236 [+0,103, +0,291]; taxa_carga +0,076 [+0,018, +0,109]; alivio +0,064 [+0,033, +0,093] |
| C10-dir | lenta | 130 | 13 | 0,26 | 30,0 | uso_aderencia -0,107 [-0,125, -0,069]; sem_pedal_s +0,092 [+0,042, +0,114]; alivio +0,067 [+0,031, +0,090] |
| C11-esq | média | 130 | 13 | -0,29 | 1,0 | retomada_s -0,364 [-0,548, -0,184]; s_ti_rel +0,325 [+0,196, +0,464]; uso_aderencia -0,315 [-0,400, -0,153] |
| C12-esq | lenta | 130 | 13 | 0,50 | 1,0 | uso_aderencia -0,464 [-0,632, -0,140]; sem_pedal_s +0,212 [+0,105, +0,271]; s_ti_rel +0,152 [+0,090, +0,199] |
| C13-esq | média | 130 | 13 | -0,13 | 100,0 | alivio +0,067 [+0,014, +0,108]; irregularidade -0,050 [-0,085, -0,007]; uso_aderencia -0,049 [-0,083, -0,006] |
| C14-esq | rápida | 130 | 13 | 0,25 | 100,0 | uso_aderencia -0,240 [-0,371, -0,046]; alivio +0,232 [+0,077, +0,413]; irregularidade -0,144 [-0,251, -0,006] |

**A leitura:**

- **O modelo prevê bem a C09 (0,68), a C12 (0,50), a C05 (0,35) e a C01 (0,32).** Em C06, C07, C11 e C13, o R² fica negativo: os indicadores não explicam o tempo dentro da sessão melhor que a média.
- **Os dois indicadores com sinal estável em mais curvas:**
  - **o tempo sem pedal** (M5), positivo: mais tempo sem pedal anda junto com um trecho mais lento. Aparece em C01, C02, C03, C04, C06, C09, C10 e C12;
  - **o uso da aderência** (M1), negativo: usar mais o círculo de atrito anda junto com um trecho mais rápido. Aparece em quase todas.
- **Na C01, a sobreposição de freio e volante** (o tempo do trail braking) tem coeficiente positivo (+0,30 s por desvio): mais tempo freando com o volante virado anda junto com um trecho mais lento. É associação, não causa. Um trail braking longo pode ser sintoma de uma entrada lenta.
- **É descritivo:** confirma que a fase sem pedal e o uso da aderência importam neste carro e nesta pista. Não vira ganho estimado (ADR 0004).
- **A C11, antes da emenda do escorregamento:** o R² era −1.027, por causa de um único ponto de escorregamento 290 numa volta de 04/10. Com a emenda, fica em −0,29.

## Parte H: o kit de rotulagem (parado aqui)

**O kit:** `docs/handoff/2026-10-24_38_modelo2-erro-tecnica-e-estilo_kit_rotulagem.html` (abra no navegador). São 120 passagens, 24 por detector:

| detector | passagens | aplica | não aplica | não conclusivo | da IA |
|---|---:|---:|---:|---:|---:|
| F4 soltura progressiva | 24 | 12 | 2 | 10 | 7 |
| F5 trail braking | 24 | 8 | 8 | 8 | 6 |
| M6 retomada | 24 | 1 | 19 | 4 | 3 |
| E2 subesterço (substituta) | 24 | 8 | 8 | 8 | 2 |
| E3 sobresterço | 24 | 8 | 8 | 8 | 2 |

(O estado de cada passagem é a composição do sorteio, não um resultado. O kit não mostra o estado.)

- **Em cada passagem:** o mapa da pista com a curva marcada, os traços de freio e acelerador, o volante (para dentro da curva, dividido pelo maior da curva), a velocidade e a guinada, com as fronteiras das fases.
- **O que o kit não mostra:** o estado que o detector deu e se a volta é sua ou da IA. Os dois estão no gabarito `data/ml/modelo2/rotulagem_gabarito.json`, fora do git, com o hash no `resultados.json`.
- **E2 e E3** só têm 2 passagens da IA cada, porque a IA com a guinada é uma volta só.

### As instruções para você

1. **Abra o kit** no navegador e a planilha `docs/handoff/2026-10-24_38_modelo2-erro-tecnica-e-estilo_rotulagem.csv` num editor (Excel ou o Bloco de Notas).
2. **Para cada passagem** (pelo `id`, por exemplo `F4-07`), leia a pergunta do detector no topo da seção e olhe os traços.
3. **Na coluna `rotulo`,** escreva `aplica`, `nao aplica` ou `nao sei`. A coluna `observacao` é livre.
4. **Salve o CSV no mesmo lugar** (separado por vírgulas, UTF-8) e me avise: "rotulei o kit".
5. **Depois,** eu rodo:

   ```bash
   cd /c/Users/Dokas/Desktop/f1-telemetry-analyzer/backend && ../.venv/Scripts/python.exe -m ml.scripts.modelo2 rotulos --rotulos ../docs/handoff/2026-10-24_38_modelo2-erro-tecnica-e-estilo_rotulagem.csv
   ```

   Com isso, completo este relatório com a precisão e a revocação de cada detector.

**A conta:** precisão e revocação de "aplica", nas passagens que você rotulou "aplica" ou "nao aplica" e em que o detector foi conclusivo. Os "nao sei" e os "não conclusivos" do detector são contados à parte.

## As emendas da primeira rodada (seção 2 do documento)

1. **Correção de código:** as pontas das fases arredondavam de jeitos diferentes. A soma das 70 fases diferia da diferença de tempo de volta em até 0,069 s; agora fecha em 0,000 s. A regra não mudou.
2. **O escorregamento acima de 10 sai da conta,** como canal não confiável. A seção 1 dizia que um canal não confiável dá "não conclusivo", mas não registrou o limite.
   - **A distribuição:** a mediana é 0,20; o percentil 99,99 é 7,6; 0,06% dos pontos passam de 5.
   - **O caso:** uma leitura de 290 levava o R² da C11 a −1.027.
3. **O ranking sem o peso,** só informativo, ao lado do registrado.

**Três limitações das regras registradas, sem mudança** (para você decidir):

- **A retomada (s_pu)** pega o primeiro acelerador ≥ 0,10 depois da frenagem e da entrada. A IA usa acelerador parcial na entrada e "retoma" 1,1 a 1,9 s antes da mínima nas curvas lentas.
  - Com isso, a retomada (M6) dá "não aplica" em quase todas as passagens dos dois lados (1 aplica em 2.016).
  - E o acelerador cedo (M7) dá "aplica" na IA em 93% das passagens.
  - **M6 e M7, como estão, não informam.** O kit inclui M6 para a rotulagem confirmar isso.
- **O ponto de entrada (s_ti)** é o começo da sequência de volante que contém o ápice. Um contraesterço antes do ápice corta a sequência e fica fora da janela do contraesterço (E4).
- **A frenagem emendada:** quando o freio de uma curva continua depois do ápice da anterior (C09 para C10, 71% das minhas passagens na C10), o ponto de frenagem cai no ápice anterior.

## Testes

- **`tests/test_modelo2.py`: 35 passaram:**
  - **as fases:** as 70 fases cobrem a volta, a soma dos tempos é o tempo de volta em duas voltas diferentes, e as fronteiras são as mesmas a cada construção; uma curva sem frenagem tem a fase vazia;
  - **cada detector** (23 por curva): um caso que aplica, um que não aplica e um sem canal ("não conclusivo"). Também a retomada (M6), com as dependências de M7 e M8, e os detectores por volta (V1, V2, V4) e a consistência (V5);
  - **as medições, numa volta sintética na geometria real:** a soltura em rampa e em degrau, o trail braking com e sem, a fase sem pedal, o alívio, o contraesterço, a falta da guinada (E2, E3 e E4 dão "não conclusivo") e o escorregamento quebrado fora da conta;
  - **a atribuição do erro:** o falso ganho da frenagem tardia é classificado como tal (um item só, de frenagem a meio, com a perda líquida);
  - **a regra de repetição:** uma perda numa volta só não entra no ranking; em 2 de 3, entra.
- **A suíte do backend:** **829 passaram em 8 min 12 s** (`python -m pytest tests -q`), com os 35 do Modelo 2. A saída está em `pytest.txt`. A suíte rodou antes do commit `53d563f1`, que só mudou a conferência do escorregamento (o `nanmedian`), que nenhum teste importa, e a documentação.

## Coisas que não batiam com o contexto

- **O pedido 37 não fechou** (o pedido 38 pedia para esperar). Você mandou seguir. O subesterço usa o retrato do pedido 39 como medida substituta.
- **Gravações que o pedido não cita:** as duas sessões minhas de 24/10 (13:26 e 13:43) estão fora do store v2. Entraram, lidas com as funções do store, e estão marcadas `fora_do_store`. A minha melhor volta é de lá.
- **A volta da IA de 22/10 é 4,3 s mais lenta** que as de 04/10. É a única referência da IA com a guinada.
- **As minhas voltas do store são 121, e não 127,** pelo filtro de relógio da evolução.
- **O índice dos ADR nesta branch pula do 0021 para o 0023:** o 0022 está na branch do 37 e entra em `develop` com o merge dela.
- **O statsmodels não está instalado:** o modelo leve usa a sessão como efeito fixo (centrada), sem instalar nada.
- **O app, o rádio, o coach, o store v2 e o relatório de evolução não mudaram.** As gravações só foram lidas. Nenhum pacote foi instalado. O `data.acd` não foi aberto.

## O que falta e o que precisa da sua decisão

1. **Rotular o kit** (Parte H) e me avisar. Depois, a precisão e a revocação (H.4) e o merge em `develop`.
2. **Gravar a sessão da IA em níveis de força** (os passos acima), para os detectores de equilíbrio terem mais que uma volta da IA e para o teste do nível.
3. **Decidir, num pedido próprio, se as regras mudam:**
   - a retomada (s_pu), para M6 e M7 informarem;
   - o peso pela reta seguinte, que zera C01, C07, C08 e C09 e põe as retas à frente;
   - o ponto de entrada (s_ti) e o contraesterço antes do ápice.
4. **Quando a M1 medir `L` e `k_δ`** (pedido 39), o subesterço (E2) é recalculado com eles.

## Os commits

| commit | o quê |
|---|---|
| `fcc94f86` | o texto do pedido 38 e as três pesquisas (o mesmo conteúdo do `f38f89a5`, trazido com `cherry-pick` da branch do 37) |
| `2cbac952` | Parte A: o ADR 0023 e a seção 1, antes de rodar |
| `e8688671` | Parte B: `dados.py` e `conferencias.py` |
| `41c1a1f4` | Parte C: `fases.py` |
| `1e043c13` | Parte E: `detectores.py` |
| `a695397d` | Parte D: `perda.py` |
| `41a60fe6` | Partes F e G: `estilo.py` e `supervisionado.py` |
| `96cb0847` | Parte H: `rotulagem.py`, o comando `ml/scripts/modelo2.py`, os testes e a seção 2 do documento |
| `53d563f1` | Parte I: as seções 3 do documento, a lista viva, a arquitetura e a conferência do escorregamento com `nanmedian`. **É o commit da rodada final** (o `commit` do `resultados.json`) |
| `d705d43f` | as saídas em `docs/handoff/`, o kit e este relatório |

**O comando da rodada final** (de `backend/`, 4 min 26 s):

```bash
cd /c/Users/Dokas/Desktop/f1-telemetry-analyzer/backend && ../.venv/Scripts/python.exe -W ignore -m ml.scripts.modelo2 todos --handoff docs/handoff/2026-10-24_38_modelo2-erro-tecnica-e-estilo
```

Quase todo o tempo vai nos bootstraps do modelo leve. A leitura das gravações (3 min 46 s na primeira vez) fica guardada em `data/ml/modelo2/derivados.parquet` e `fora_do_store.parquet`.

## A H.4, pedida em 25/10 às 11:25: parada, sem os rótulos

- **O pedido:** "Rotulei o kit. Rode a H.4, complete o relatório e faça o merge em develop. Inclua no commit a linha nova de `docs/tecnica_de_pilotagem_lista.md`, que o Cowork acrescentou."
- **Os rótulos não estão no arquivo:**
  - `docs/handoff/2026-10-24_38_modelo2-erro-tecnica-e-estilo_rotulagem.csv` não muda desde 05:29, quando foi gerado. As 120 linhas estão com o `rotulo` vazio (24 por detector);
  - a cópia em `data/ml/modelo2/rotulagem/` também está vazia;
  - não há nenhum CSV, XLSX ou TXT novo depois de 05:31 na Área de Trabalho, em Downloads, em Documentos ou no OneDrive.
- **Por isso,** a precisão e a revocação não foram calculadas e **o merge em `develop` não foi feito**. O pedido manda o merge no fim, e a H.4 é parte dele.
- **A lista viva:**
  - às 11:19, `docs/tecnica_de_pilotagem_lista.md` foi regravado na pasta com um conteúdo idêntico, byte a byte, à versão do Cowork de 01:07. Essa versão já está no commit `53d563f1`, com as minhas atualizações de B1, B2, B3, B10, E1, E2 e E3 e a linha do histórico;
  - a regravação **não traz nenhuma linha nova**: ela só desfaz as minhas atualizações;
  - **não commitei** a regravação e não mexi no arquivo. Ele continua modificado na pasta, sem commit.
- **O que falta:**
  1. **os rótulos no CSV:** se você rotulou em outro arquivo, me diga qual;
  2. **qual é a linha nova do Cowork:** se ela existe, ainda não chegou à pasta.

  Com os dois, rodo a H.4, completo o relatório e faço o merge.

## Mudança de prioridade em 25/10, às 11:36: o instalador 0.5.0 antes da H.4

- **O pedido** (Eduardo, no chat): gerar o instalador 0.5.0 do app nesta branch, sem trocar de branch, para testar sozinho o app instalado. A H.4 continua parada, esperando os rótulos. É uma exceção autorizada à regra "Não gere instalador" deste pedido.
- **A pasta:** antes de começar, o `ListAgents` mostrou duas outras sessões nesta pasta, as duas paradas ("Modelo do carro 2026-10-24" e "Redesenho base 2026-10-14"). A branch não mudou durante o trabalho.
- **A lista viva** corrigida pelo Cowork (a da Parte I mais a linha de validação de 25/10) foi commitada sozinha: `d988fe62`.
- **O app completo nesta branch:**
  - os commits do fechamento do pedido 36, `52ce0a02` (a frase do coach sobe para 7,3 s) e `db39300f` (o log do backend gira em 20 MB), estão na branch;
  - `git diff --stat develop...HEAD` só mostra `backend/ml`, `backend/tests/test_modelo2.py` e `docs`. Nada em `desktop`, `frontend`, `tools/csp_app` nem no backend fora de `ml`.
  - **Um ponto que não estava na lista, para você saber:** o app do jogo 0.4.1 (`0092ed38`, a janela salva fora da tela volta para dentro, do teste de 24/10) **não está nesta branch nem em `develop`**, só em `etapa/radio-unidades-e-replay`. O `instalar.ps1` desta branch instala o app do jogo **0.4.0**. Se uma janela do app sumir depois de trocar de monitor, é esse caso (ver os passos).
- **Os testes:**
  - **o front:** `vitest run` com 189 passaram em 17 arquivos; `tsc --noEmit` sem erro;
  - **o `desktop`:** `npm test` com 4 passaram (a rotação do log);
  - **o app do jogo:** `conferir_lua.py` contra o `lib.lua` dos apps do CSP instalado: 0 erros de léxico, os blocos fecham, e as 45 funções da API e os 11 métodos usados existem no SDK;
  - **a suíte do backend** não rodou de novo: desde `28de6176`, só `backend/ml`, os testes do Modelo 2 e a versão mudaram, e a suíte de 05:29 (829 passaram) já cobre o `ml`.
- **A versão:** `0.5.0-radio-e-replay`, no commit `825ef60d`. São os mesmos três lugares da 0.4.0: `desktop/package.json`, `BACKEND_PHASE_VERSION` em `backend/main.py` e `EXPECTED_BACKEND_VERSION` em `desktop/main.js`. O sufixo diz o que entrou desde a 0.4.0: o rádio que analisa e o replay da curva (pedidos 33 a 36).
- **O build:** `npm run dist:win` (de `desktop`), terminou às 11:47 sem erro, em cerca de 9 minutos.
  - **O instalador:** `versoes\0.5.0-radio-e-replay\Automobilista-Telemetria-Setup-0.5.0-radio-e-replay.exe`, 229 MB (229.288.854 bytes).
  - **O sha256:** `4db96566280e46fc932b85c5a6b807a6b0794870a73845a81849d24c5b86d3d7`, no `sha256.txt` da pasta.
  - **O `build-info.json`:** versão `0.5.0-radio-e-replay`, commit `825ef60`, branch `etapa/modelo2-erro-tecnica-e-estilo`. Ele marca `dirty`, mas o único arquivo fora do git é a pasta `recordings/` da raiz, que está assim desde 14/10.
  - **O índice:** `versoes\LEIA-ME.md` foi refeito pelo `publish-version.js` (11 versões; a mais atual é a 0.5.0) e foi commitado com este relatório. O instalador fica fora do git, como os anteriores.
  - **Nada foi baixado nem instalado:**
    - o log diz "downloaded label=electron", mas o zip do Electron 42.3.3 já estava no cache local (`%LOCALAPPDATA%\electron\Cache`, de 07/06), e nenhum arquivo novo apareceu nos caches depois das 11:00;
    - o "installing native dependencies" do `@electron/rebuild` não instalou nada, porque o projeto não tem módulo nativo ("no node modules returned");
    - o PyInstaller e o resto já estavam no `.venv`.
  - **Não rodei o instalador** e não mexi no app instalado nem no jogo.

### Os passos para você, sozinho

**1. Instalar o app 0.5.0 e o app do jogo**

1. Feche o jogo e o app, inclusive o ícone na bandeja do Windows.
2. Rode o instalador, por cima do instalado:

   ```
   C:\Users\Dokas\Desktop\f1-telemetry-analyzer\versoes\0.5.0-radio-e-replay\Automobilista-Telemetria-Setup-0.5.0-radio-e-replay.exe
   ```

   Escolha **todos os usuários** e mantenha a pasta `C:\Users\Dokas\AppData\Local\Programs\Automobilista Telemetria`. As gravações e a configuração em `%APPDATA%\Automobilista Telemetria` ficam.
3. Instale o app do jogo, num PowerShell:

   ```
   powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Dokas\Desktop\f1-telemetry-analyzer\tools\csp_app\instalar.ps1
   ```

   Aperte Enter para aceitar a pasta `D:\SteamLibrary\steamapps\common\assettocorsa`.
4. **Confira as versões:**
   - **o app:** pelo menu Iniciar ("Automobilista Telemetria"), na aba **Coleta de dados** ("Versão do app") ou em **Sistema**. Tem de aparecer `0.5.0-radio-e-replay`;
   - **o app do jogo:** abra `D:\SteamLibrary\steamapps\common\assettocorsa\apps\lua\radio_engenheiro\manifest.ini` no Bloco de Notas. A linha `VERSION` tem de dizer `0.4.0` (a 0.4.1 não está nesta branch).

**2. Testar o rádio no jogo, sem a IA**

1. Abra o app instalado **antes** do jogo.
2. Abra o Assetto Corsa pelo Content Manager: prática, `rss_formula_rss_3_v6_2026`, Interlagos (`vhe_interlagos`, traçado `gp`).
3. **No jogo, ligue as 4 janelas** na barra de apps: "Rádio", "Minimapa", "Mapa aproximado" e "Replay da curva". Ponha o replay num canto, sem cobrir o centro.
4. **No app, na tela Sistema, clique em "Mandar mensagem de teste":** o cartão e a voz têm de aparecer no jogo.
5. **Ande pelo menos 8 voltas você mesmo,** com uma ida aos boxes depois da 3ª volta válida (é quando sai a primeira análise). Para medir o FPS de cada janela, desligue o replay por 2 ou 3 voltas e ligue de novo.
6. **Não aperte Ctrl+C no jogo:** ele passa o carro para a IA, e o indicador da IA fica ligado até a sessão do jogo reiniciar. O rádio fica calado nas voltas da IA, de propósito, e as suas voltas depois do Ctrl+C também não contam para o foco. Se apertou sem querer, saia da sessão e comece outra.
7. **Se uma janela do app sumir** depois de trocar de monitor: é o caso que a 0.4.1 corrige. Desligue e ligue a janela na barra de apps. Se ela não voltar, anote qual janela foi e siga com as outras.

**3. Onde ficam as gravações e como trazê-las para o repositório**

- **O app instalado grava em** `%APPDATA%\Automobilista Telemetria\data\recordings\`, uma pasta por sessão (por exemplo, `2026-10-26_10-00-00_vhe_interlagos`).
- **O Modelo 2 e o resto do `ml` já leem as duas pastas** (a do repositório e a do app instalado). Mesmo assim, para guardar no repositório como as outras, copie cada sessão nova para `data\recordings`, num PowerShell. Troque o nome da pasta:

  ```
  robocopy "$env:APPDATA\Automobilista Telemetria\data\recordings\2026-10-26_10-00-00_vhe_interlagos" "C:\Users\Dokas\Desktop\f1-telemetry-analyzer\data\recordings\2026-10-26_10-00-00_vhe_interlagos" /E
  ```

  É uma cópia: a original fica no lugar. O `ml` marca as cópias com `duplicada_de` e não conta a mesma sessão duas vezes.
- **Para a IA em níveis de força,** os passos são os da Parte B deste relatório. Cada nível é uma sessão do jogo nova, e cada sessão vira uma pasta. Anote cada pasta em `docs\experimentos\ia_niveis.csv`, com o nível, a agressividade e a variação.

**4. O que anotar durante os testes** (num papel ou no Bloco de Notas; eu leio os logs depois)

- **O horário de cada coisa,** pelo relógio do Windows: quando abriu o app e o jogo, a mensagem de teste, a ida aos boxes, quando desligou e religou o replay, e quando saiu.
- **A versão** que o app mostrou e a `VERSION` do `manifest.ini`.
- **A mensagem de teste:** se o cartão apareceu, se a voz saiu, e quanto tempo depois do clique.
- **A cada fala do rádio:** a volta, a curva que ele citou, se a voz saiu numa reta, se a frase fez sentido e se o replay mostrou a curva certa.
- **O FPS** que o jogo mostrar, com o replay ligado e desligado, se você tiver um contador na tela.
- **Qualquer janela que sumiu, travou ou ficou cortada,** e em que monitor.
- **Se apertou Ctrl+C sem querer,** em que volta.
- **Para a sessão da IA:** o nome de cada pasta nova em `recordings`, o nível, a agressividade e a variação, e se os tempos de volta mudaram de um nível para o outro.

**Onde ficam os logs, para eu ler depois:**

- **o do app:** `%APPDATA%\Automobilista Telemetria\logs\backend.log` e `desktop.log`;
- **o do app do jogo:** as linhas `[radio_engenheiro]` no log do CSP, em `Documentos\Assetto Corsa\logs\custom_shaders_patch.log`.

  Não apague nem mova esses arquivos. O `backend.log` gira em 20 MB e guarda os 5 últimos.

### O que falta

- **A H.4** continua esperando os rótulos no CSV ("rotulei o kit"). O merge em `develop` vem depois dela, com a versão 0.5.0 junto.

Arquivo: `docs/handoff/2026-10-24_38_modelo2-erro-tecnica-e-estilo_relatorio.md`
