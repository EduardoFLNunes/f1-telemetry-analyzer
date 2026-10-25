# Modelo 2: o erro que custou tempo, as técnicas e o estilo (pedido 38, ADR 0023)

Este documento descreve as quatro peças do Modelo 2 aplicadas às voltas gravadas da IA e do piloto:

- a comparação com uma volta real;
- os detectores de técnica;
- as dimensões de estilo;
- o modelo supervisionado leve.

A seção 1 foi registrada **antes de rodar qualquer conta nas voltas** e não muda depois de ver os resultados. Uma mudança entra numa seção nova, com a data e o motivo, sem apagar a original (pedido 38, Parte A.3). As seções seguintes, escritas depois, contam o que saiu.

O código fica em `backend/ml/modelo2/`, e o comando é `python -m ml.scripts.modelo2`. Nada do app, do rádio, do coach, do store v2 ou do relatório de evolução muda.

---

## 1. Registrado antes de construir (25/10/2026)

### 1.1 As voltas

- **Do piloto:** as voltas do store v2 com origem `humano`, equipamento `atual`, válidas, com o relógio conferido e sem `relogio_suspeito`. É o filtro do relatório de evolução (`evolution.driver_laps`).
- **Da IA:** as voltas do store v2 com origem `ia`, válidas e com o relógio conferido, de sessões a partir de 04/10 (o filtro `coach_references.ai_laps`).
- **De fora do store v2:** as gravações posteriores à construção dele (22/10, 03:34), que o store ainda não tem:
  - `2026-10-22_09-46-01` (IA);
  - `2026-10-24_13-26-12` e `2026-10-24_13-43-32` (do piloto).

  Elas são lidas com as mesmas funções do store (`iter_laps`, `clean_lap`, `align_lap`, `evaluate_lap`, `resample_lap` com `line_clock`, `pit_lap`), **sem escrever no store**. Cada volta entra quando:
  - passa nos portões de qualidade (`evaluate_lap`) e não passa pelo box;
  - a origem pelo indicador `isAIControlled` é única: todas as amostras com o campo `true` dão `ia`, todas `false` dão `humano`, e uma mistura fica fora (ADR 0014). O equipamento é o `atual` (gravação depois de 01/10);
  - o tempo da grade e o tempo do jogo costurado na troca de volta (`game_lap_time`) diferem em no máximo 0,05 s. É a conferência do relógio que essas voltas não passaram no inventário.

  Elas são marcadas `fora_do_store` em todas as saídas.
- **A IA em níveis de força** é lida de `docs/experimentos/ia_niveis.csv`, se existir. Cada linha tem a gravação, as voltas do bloco, o nível, a agressividade e a variação. Sem o arquivo, o teste do nível fica "não conclusivo".
- **Sessão** é a regra do relatório de evolução (`group_sessions`): gravações separadas por menos de 3 h. A sessão leva a data em que terminou.
- **A volta de referência da perda** é a volta da IA do coach (`volta_ia` do modelo do repositório: `2026-10-04_03-42-10_vhe_interlagos#0013`, 84,829 s). A outra referência é a melhor volta do piloto em todas as sessões (`minha_melhor`).
- **As referências da calibração** são todas as passagens da IA (as 13 de 04/10 e as de fora do store), cada detector só nas que têm o canal dele.

### 1.2 Os canais e o relógio

- **A grade de 2 m** é a do store v2 (2.167 pontos, `geometry_id` `0ed16f0dd2225990`). A perda, as posições (s_b, s_ti, s_vmin, s_pu) e os níveis de pedal são lidos nela.
- **As taxas** são calculadas nos dados originais e só depois levadas à grade:
  - **o relógio** é o cronômetro do jogo (`lap_time_s`, ADR 0022), depois de tirar as amostras em que ele não andou;
  - **as taxas** são diferenças centradas em ±0,05 s (freio, acelerador, volante e fração de carga dianteira);
  - **também no tempo original:** a média móvel de 0,5 s do volante, as reversões e as trocas de marcha.

  O valor de cada ponto da grade é a interpolação pelo `s` das amostras originais. Uma janela com um buraco de 0,2 s ou mais no cronômetro dá "não conclusivo" nos detectores de taxa.
- **O volante** é o `steer_angle` gravado. Pelo pedido 39, ele é positivo à direita, e a M1 (pedido 37) confirmou que o sinal de −`steer_angle` é o da guinada. A unidade não importa para quase nenhum detector, porque o volante é dividido pelo pico da passagem, δ_pk (o maior |volante| entre o começo e o fim geométricos da curva).
- **Subesterço, medida substituta (ADR 0023, Consequências).** O ângulo de subesterço precisa do entre-eixos e da unidade do volante, que a M1 ainda não mediu (pedido 39, parado). Até lá, ele usa os valores do retrato da memória do jogo, deste carro, lidos no pedido 39 (Parte B), **marcados como substitutos**:
  - L = 2,955 m;
  - k_δ = 0,267 rad de roda por unidade de volante;
  - δ_roda = −k_δ · volante, positivo para a esquerda.

  Quando a M1 medir os dois, o detector é recalculado com eles, numa seção nova.
- **Sinais** (pedido 37, conferidos de novo na Parte B): a guinada, a aceleração lateral e a `localVelocity.x` são positivas para a esquerda. A deriva do veículo é β = atan2(v_lat, v_long).
- **Pedais:** freio e acelerador de 0 a 1. Os limiares em pedal valem para esta escala, e nenhum limiar publicado em pressão é usado.

### 1.3 As fases de cada curva

As 14 curvas são as de `detect_corners`, com os nomes C01 a C14 que o rádio e o relatório de evolução usam. Cada curva k tem o começo a_k, o ápice p_k (o ponto de maior curvatura) e o fim e_k na geometria oficial.

**As fronteiras são definidas uma vez, para todas as voltas, e juntas cobrem a volta inteira:**

| fase | de | até |
|---|---|---|
| frenagem | b_k | a_k |
| entrada | a_k | m1_k |
| meio | m1_k | m2_k |
| saída | m2_k | e_k |
| reta seguinte | e_k | b_(k+1) |

- **O meio** é o trecho contíguo em volta do ápice em que |curvatura| ≥ 0,6 × a maior curvatura da curva. Ele tem pelo menos 10 m (alargado igualmente para os dois lados) e deixa pelo menos 4 m para a entrada e 4 m para a saída.
- **O início da frenagem, b_k,** sai do pedal das voltas rotuladas, calculado uma vez:
  - b_k = min(mediana do ponto de frenagem das passagens da IA, percentil 10 das passagens do piloto) − 10 m;
  - b_k fica limitado a [e_(k−1), a_k];
  - se a IA e o piloto não freiam na maioria das passagens, b_k = a_k, e a fase de frenagem fica vazia ("curva sem frenagem").
- **Por que as duas regras:**
  - **a geometria** dá a entrada, o meio e a saída iguais para todas as voltas, sem depender de quem pilota. Ela não sabe onde a frenagem começa;
  - **o pedal** sabe, mas cada volta freia num ponto diferente. Se a fronteira fosse a de cada volta, a mesma fase teria tamanhos diferentes em voltas diferentes e as perdas não se somariam.

  O ponto fixo, recuado até a frenagem mais antecipada do piloto, põe a perda de frear cedo na fase de frenagem da curva, e não na reta seguinte da curva anterior. É a combinação das duas regras que a pesquisa cita (a curvatura da linha de referência e o sistema especialista de pedais).
- **O trecho da curva** (o alvo do modelo supervisionado e a perda total por curva) é o do relatório de evolução: do meio da reta anterior ao meio da seguinte.
- **O peso da curva** (Parte D) é o comprimento da reta seguinte, b_(k+1) − e_k, dividido pela média dos 14.
- **O tipo de curva** sai da velocidade mínima da volta da IA do coach entre a_k e e_k. Os limiares são o de Krause e Bentley para carros com carga aerodinâmica (120 km/h) e, por escolha minha, 180 km/h para separar as curvas quase de pé embaixo:

  | tipo | mínima da IA |
  |---|---|
  | lenta | < 120 km/h |
  | média | 120 a 180 km/h |
  | rápida | ≥ 180 km/h |

### 1.4 Os eventos de cada passagem

Uma passagem é uma volta numa curva. Os eventos de cada passagem, na grade:

- **s_b, o ponto de frenagem:**
  - procura-se entre o ápice anterior, p_(k−1), e o ápice, p_k;
  - vale a sequência de freio ≥ 0,05 que contém o maior freio dessa janela. Sequências separadas por menos de 10 m são juntadas;
  - s_b é o começo dessa sequência, e s_be é o fim dela;
  - com o maior freio da janela abaixo de 0,15, a passagem não tem frenagem.
- **B_pk:** o maior freio da sequência. **t_pk:** o primeiro instante com freio ≥ 0,9·B_pk.
- **s_ti, o ponto de entrada:** o começo da sequência de |volante| ≥ 0,15·δ_pk, no sentido da curva, que contém o ápice.
- **s_vmin:** a menor velocidade entre a_k e e_k.
- **s_pu, a retomada do acelerador:** o primeiro ponto depois de max(s_be, s_ti) e antes de e_k + 50 m com acelerador ≥ 0,10. **s_full:** o primeiro ponto depois de s_pu com acelerador ≥ 0,95.

### 1.5 Os detectores

**Os três estados.** Cada detector dá, a cada passagem, "aplica", "não aplica" ou "não conclusivo". "Aplica" quer dizer que a condição do detector vale:

- num detector de **técnica**, a técnica foi aplicada;
- num detector de **erro**, o erro ocorreu.

É "não conclusivo" em três casos:

- falta o canal;
- o canal não é confiável no trecho (buraco no cronômetro, ou um evento necessário que não existe);
- o valor cai na faixa de dúvida.

**Os dois tipos de regra e a calibração:**

- **P, regra física:** o limiar é fixo (da pesquisa ou físico). A calibração nas voltas de referência da mesma curva só alarga a faixa de dúvida em volta do limiar:
  - faixa = max(faixa inicial, 0,5 × desvio robusto do indicador nas passagens da IA naquela curva);
  - o desvio robusto é o intervalo interquartil dividido por 1,349;
  - "aplica" exige o valor além do limiar por mais que a faixa, e "não aplica" exige o valor do outro lado por mais que a faixa.

  Assim, a IA não aplica a técnica "por construção".
- **C, comparação com a referência:** o limiar é relativo às passagens da IA na mesma curva (a mediana, ou um percentil), com um mínimo fixo.
  - Com menos de 3 passagens da IA com o canal, a referência é o que houver (1 ou 2 passagens), e isso é marcado;
  - sem nenhuma passagem da IA com o canal, o detector dá "não conclusivo".

Na tabela, med_ref, q90_ref e q95_ref são a mediana e os percentis 90 e 95 das passagens da IA, e sdr é o desvio robusto. As fontes dos limiares iniciais estão na pesquisa (`docs/tecnica_de_pilotagem_pesquisa.md`, seção "Cada técnica…").

**Frenagem**

| id | detector (técnica ou erro) | tipo | indicador | aplica | não aplica | fonte do limiar inicial |
|---|---|---|---|---|---|---|
| F1 | referência de frenagem (técnica) | C | x = s_b − med_ref(s_b), em m (+ é mais tarde). T = max(10 m, 2·sdr) | \|x\| ≤ T | \|x\| ≥ T + 5 m, ou sem frenagem com a IA freando | Driver61, Blayze. Curva em que a IA não freia em metade ou mais das passagens: "não conclusivo" |
| F2 | frenagem no limiar (técnica) | C | x1 = t_pk − t(s_b), em s (tempo original); x2 = B_pk / med_ref(B_pk). T1 = max(0,38 s, q90_ref(x1)) | x1 ≤ T1 e x2 ≥ 0,90 | x1 ≥ T1 + 0,20 s ou x2 ≤ 0,80 | van Leeuwen et al. (0,38 s contra 1,12 s) |
| F3 | perfil com carga aerodinâmica (técnica) | P | D = t(s_be) − t(s_b) ≥ 0,6 s. x1 = (t_pk − t(s_b)) / D; x2 = (B_pk − mediana do freio no terço do meio de D) / B_pk | x1 ≤ 0,35 e x2 ≥ 0,10 | x1 ≥ 0,50 ou x2 ≤ 0,03 | VRS 3.4. D < 0,6 s: "não conclusivo" |
| F4 | soltura progressiva (técnica) | P | soltura: do último instante com freio ≥ 0,5·B_pk até s_be. x = −(menor taxa do freio no último terço da soltura), em 1/s. Limiar 3,0/s, faixa inicial 0,75/s. Ao lado: a maior queda da fração de carga dianteira, em 1/s | x ≤ 3,0 − faixa | x ≥ 3,0 + faixa | Coach Dave, Winding Road (degrau na soltura) |
| F5 | trail braking (técnica) | P | x1 = freio(s_ti) / B_pk (retenção); x2 = tempo com freio ≥ 0,05 e \|volante\| ≥ 0,15·δ_pk no sentido da curva, depois de s_ti, em s; x3 = correlação de Spearman entre o freio e o \|volante\| nesse trecho (relatada) | x2 ≥ 0,20 s e x1 ≥ 0,10 | x2 ≤ 0,05 s ou x1 ≤ 0,03 | Speed Secrets, HP Academy |
| F6 | travamento de roda (erro) | C | pontos da frenagem com freio ≥ 0,3 e \|volante\| ≤ 0,1·δ_pk. x = maior escorregamento dianteiro (fl, fr) / q95_ref do mesmo | x ≥ 1,5 | x ≤ 1,1 | HP Academy, SimHub. Sem pontos em linha reta: "não conclusivo" |
| F7 | sobreposição de pedais, pé esquerdo (técnica) | P | x = tempo com freio ≥ 0,05 e acelerador ≥ 0,05 na frenagem e na entrada, fora de ±0,15 s de uma redução (o toque de acelerador na redução), em s | x ≥ 0,20 s | x ≤ 0,05 s | HP Academy, CEUR-WS |
| F8 | redução de marcha brusca (erro) | C | para cada redução na frenagem e na entrada: o maior escorregamento traseiro (rl, rr) nos 0,3 s seguintes. x = maior deles / q95_ref do mesmo. Ao lado: o número de reduções contra a IA | x ≥ 1,5 | x ≤ 1,1 | Blayze, AMS2 wiki. Sem redução: "não conclusivo" |

**Entrada e equilíbrio**

| id | detector (técnica ou erro) | tipo | indicador | aplica | não aplica | fonte do limiar inicial |
|---|---|---|---|---|---|---|
| E1 | entrada antecipada (erro) | C | x = s_ti − med_ref(s_ti), em m. T = max(10 m, 2·sdr). Ao lado: a taxa de entrada (a maior taxa do \|volante\| / δ_pk nos 0,5 s depois de s_ti, em 1/s) | x ≤ −(T + 5 m) | x ≥ −T | CEUR-WS, Driver61 |
| E2 | subesterço (erro; **medida substituta**, 1.2) | C | no meio, com \|a_y\| ≥ 0,4 g e \|r\| ≥ 0,05 rad/s: UA = sinal(r)·(δ_roda − L·r/v_x), em graus. x = mediana de UA − med_ref | x ≥ 0,5° | x ≤ 0,2° | patente US 10293852 (sem limiar publicado): limiar meu, relativo à IA. Exige a guinada e v_x |
| E3 | sobresterço (erro) | C | β = atan2(v_lat, v_long). x = p95 de \|β\| da entrada à saída − med_ref do mesmo, em graus | x ≥ 1,0° | x ≤ 0,3° | Betz et al., Binetti et al. Exige as velocidades no referencial do carro |
| E4 | contraesterço (erro) | P | contraesterço = o volante com o sinal oposto ao normal para a guinada (normal: −volante com o sinal de r), com \|volante\| ≥ 0,05·δ_pk e \|r\| ≥ 0,05 rad/s. x = a sequência mais longa de s_ti a e_k, em s | x ≥ 0,10 s | x ≤ 0,03 s | Binetti et al. Exige a guinada |
| E5 | reversões do volante (erro) | C | no tempo original, de s_ti a e_k: o volante com média móvel de 0,1 s. Reversão = um extremo local que difere do anterior em ≥ 0,05·δ_pk. x = número − med_ref(número) | x ≥ 2 | x ≤ 0 | Markkula e Engström, Hojaji et al. |
| E6 | suavidade do volante (técnica) | C | x = média de \|volante − média móvel de 0,5 s\| de s_ti a e_k / δ_pk (tempo original) | x ≤ 1,2·q90_ref | x ≥ 1,6·q90_ref | HP Academy, Betz et al. |

**Meio e saída**

| id | detector (técnica ou erro) | tipo | indicador | aplica | não aplica | fonte do limiar inicial |
|---|---|---|---|---|---|---|
| M1 | uso do círculo de atrito (técnica; mede habilidade) | P | envelope E(v) = percentil 98 de √(a_x² + a_y²) em faixas de 20 km/h, em todas as voltas rotuladas (calculado uma vez). x = p95 de √(a_x² + a_y²)/E(v) de b_k a e_k. Ao lado: a fração "na diagonal" (\|a_x\| e \|a_y\| ≥ 0,3·E) de s_b a p_k | x ≥ 0,90 | x ≤ 0,80 | HP Academy g-g, Speed Secrets |
| M2 | ápice antecipado (erro) | C | x = s_vmin − med_ref(s_vmin), em m. T = max(10 m, 2·sdr). Ao lado: a posição lateral no ápice geométrico contra a IA | x ≤ −(T + 5 m) | x ≥ −T | Betz et al., PSR |
| M3 | forma em U (técnica-estilo; "não aplica" = forma em V) | P | x = tempo com velocidade ≤ 1,03·v_min, de b_k a e_k, em s. Ao lado: v_min / v(s_b) | x ≥ 0,60 s | x ≤ 0,30 s | Speed Secrets (U acima de ~120 km/h em carro com carga aerodinâmica) |
| M4 | uso da largura na saída (técnica) | C | na saída e nos 60 m seguintes: x = maior afastamento do centro para fora da curva (−sentido·lateral), em m. Δ = x − med_ref(x) | Δ ≥ −0,5 m | Δ ≤ −1,5 m | PSR |
| M5 | fase sem pedal (erro) | P | x = tempo com acelerador < 0,05, freio < 0,05 e v > 5 m/s, em sequências de 0,1 s ou mais, de b_k a e_k, em s. Limiar 0,25 s, faixa inicial 0,05 s | x ≥ 0,25 + faixa | x ≤ 0,25 − faixa | Betz et al. (1,99 s por volta no profissional) |
| M6 | retomada do acelerador (técnica) | C | x1 = t(s_pu) − t(s_vmin), em s; x2 = x1 − med_ref(x1) | x1 ≥ −0,10 s e x2 ≤ 0,20 s, com M7 e M8 "não aplica" | x1 ≤ −0,30 s, ou x2 ≥ 0,50 s, ou M7 ou M8 "aplica", ou sem retomada até e_k + 50 m com a IA retomando | Betz et al., Blayze, Coach Dave |
| M7 | acelerador cedo, volante crescendo depois da retomada (erro) | P | x = maior \|volante\| (média de 0,2 s) depois de s_pu até e_k, menos \|volante\| em s_pu, dividido por δ_pk | x ≥ 0,10 | x ≤ 0,03 | Blayze |
| M8 | alívio depois da retomada (erro) | P | x = maior queda do acelerador em relação ao máximo anterior, de s_pu até s_full (ou e_k + 100 m) | x ≥ 0,15 | x ≤ 0,05 | Coach Dave |
| M9 | patinação e sobresterço de potência (erro) | C | na saída e nos 100 m seguintes, com acelerador ≥ 0,3: x = maior escorregamento traseiro / q95_ref do mesmo | x ≥ 1,5 | x ≤ 1,1 | SimHub, HP Academy |

**Volta e sessão**

| id | detector (técnica ou erro) | tipo | indicador | aplica | não aplica | fonte do limiar inicial |
|---|---|---|---|---|---|---|
| V1 | uso decidido do acelerador (técnica; por volta) | P | f0 = fração da volta com acelerador < 0,02; f100 = fração com > 0,98; ao lado, f20–60. x = f0 + f100 | x ≥ 0,85 | x ≤ 0,75 | van Leeuwen et al. |
| V2 | rotação de troca (técnica; por volta) | C | x = mediana da rotação na última amostra antes de cada troca para cima − med_ref, em rpm. Ao lado: a fração do tempo acima do p99,5 da rotação da IA | \|x\| ≤ 300 | \|x\| ≥ 600 | AMS2 wiki |
| V3 | transferência de carga brusca (erro; por curva) | C | fração de carga dianteira F = (Fz_fl + Fz_fr)/ΣFz. x = maior \|dF/dt\| de s_b a e_k (tempo original) / q90_ref do mesmo | x ≥ 1,5 | x ≤ 1,1 | Beckman |
| V4 | pneus na faixa da IA (técnica; por volta) | C | x = média da temperatura do núcleo dos 4 pneus na volta − med_ref, em °C. Ao lado: a inclinação na sessão, em °C por volta | \|x\| ≤ 5 | \|x\| ≥ 10 | simracingcockpit. Uma diferença com o pneu frio não é erro técnico (pesquisa, "gestão de pneus") |
| V5 | consistência (técnica; por sessão e curva, com 5 voltas ou mais) | P | x = desvio-padrão do tempo do trecho da curva nas voltas válidas da sessão, em s. Ao lado: os desvios de s_b, v_min e s_pu e o desvio do tempo de volta (aplica ≤ 0,5 s; não aplica ≥ 1,0 s) | x ≤ 0,08 s | x ≥ 0,15 s | Grassroots Motorsports (0,25 a 0,5 s na volta) |

**A fase de cada detector** (para a atribuição da Parte D):

| fase | detectores |
|---|---|
| frenagem | F1, F2, F3, F6, F7, F8, V3 |
| entrada | F4, F5, E1, E5, E6, M5 |
| meio | E2, E3, E4, M1, M2, M3, M5 |
| saída | M6, M7, M8, M9, M4, E3 |
| reta seguinte | M4, M6, M8 |

**O domínio de uma técnica** (relatado, sem decisão): ela conta como dominada se foi aplicada em pelo menos 4 das últimas 6 passagens conclusivas.

### 1.6 A localização, a cadeia causal e a atribuição do erro (Parte D)

**A perda** de uma passagem numa fase é (t_volta(fim) − t_volta(início)) − (t_ref(fim) − t_ref(início)), com o relógio da grade do store v2. Ela é calculada contra a volta da IA do coach e, ao lado, contra a melhor volta do piloto. As 70 fases cobrem a volta, então a soma das perdas é a diferença de tempo de volta.

**O ranking, por sessão:**

1. **Voltas:** as 3 últimas voltas válidas da sessão, pela ordem na gravação.
2. **Item:** um par (curva, fase). Ele entra se a perda for ≥ 0,02 s em pelo menos 2 das 3 voltas. Uma perda numa volta só não entra.
3. **Valor:** a mediana da perda nas 3 voltas. **Pontuação:** valor × peso da curva (1.3).
4. **Consistência primeiro:** o primeiro item é a consistência quando, na sessão, o desvio do tempo de volta passa de 1,0 s, ou o desvio do ponto de frenagem passa de 15 m em alguma curva com frenagem (com 5 voltas ou mais). Os valores vão no item.
5. **A saída:** os 3 itens de maior pontuação, contando o de consistência quando ele existe.

**A cadeia causal:**

- **Perda na saída ou na reta seguinte** com a retomada atrasada (mediana de M6.x2 > 0,20 s nas 3 voltas) e a mínima abaixo da IA (mediana de v_min − v_min,IA < −2 km/h): a origem é procurada na entrada. A atribuição olha os detectores da frenagem, da entrada e do meio da mesma curva, e o item registra a fase do sintoma e a fase de origem.
- **Falso ganho:** numa curva, em pelo menos 2 das 3 voltas,
  - a frenagem tem perda < 0 (ganho);
  - o ponto de frenagem é mais tarde que a IA (F1.x > T);
  - a perda da entrada e do meio é maior que o ganho da frenagem.

  O item vira "falso ganho": a perda é a soma da frenagem, da entrada e do meio, a origem é a frenagem, e ele não conta como melhora.

**A atribuição.** Para cada item, nos detectores da fase de origem:

- **o estado do piloto** é o da maioria das 3 voltas, com pelo menos 2 conclusivas;
- **o estado da IA** é o da maioria das passagens conclusivas dela, com pelo menos 1;
- **o estado da melhor volta** é o da melhor volta do piloto.

Um detector **explica** o item quando:

- o estado do piloto difere do da IA;
- a melhor volta concorda com a IA ou é "não conclusiva" (se a IA e a melhor volta discordam, a técnica não separa o rápido do lento, e o detector fica "não conclusivo", como manda a pesquisa);
- a diferença do indicador principal (mediana do piloto − mediana da IA) é maior que o desvio robusto do piloto naquela curva.

Entre os que explicam, vale o de maior diferença em desvios do piloto. A saída dá o detector, a diferença na unidade do indicador e em desvios, e os três estados. **Se nenhum explicar, a saída é "não conclusivo".** Os detectores em que a melhor volta também difere da IA são listados à parte, como "técnica que o piloto não mostrou em nenhuma volta".

### 1.7 As dimensões de estilo (Parte F)

São calculadas por tipo de curva (1.3), nas passagens conclusivas, para a IA e para o piloto (por sessão e no total).

| dimensão | medida | canais |
|---|---|---|
| forma V ou U | M3.x (tempo perto da mínima); v_min / v(s_b); posição de s_vmin na curva, (s_vmin − a_k)/(e_k − a_k) | velocidade |
| perfil de frenagem | F2.x2 (pico relativo); (t_pk − t_b)/D (tempo até o pico ÷ duração); F4.x (taxa no fim da soltura) | freio |
| uso dos pedais | o menor acelerador entre o alívio e s_b (Leclerc: 7 a 11%); F7.x | freio, acelerador |
| resposta do carro na entrada | a razão guinada ÷ δ_roda nos 0,5 s depois de s_ti; \|β\| na entrada; E4.x | guinada, volante, velocidades no referencial do carro |
| aplicação do volante | E1, taxa de entrada (1/s); E5, número de reversões; δ_pk | volante |
| perfil do acelerador | t(s_full) − t(s_vmin) (do ápice ao pleno); f20–60 na saída | acelerador |
| consistência | desvio entre voltas de s_b, v_min e s_pu, relatado à parte | freio, velocidade, acelerador |

- **Escore-z:** (mediana da medida − mediana de todas as passagens rotuladas, IA e piloto, daquele tipo de curva) ÷ desvio robusto dessas passagens.
- **A incerteza** é o intervalo de 90% da mediana por bootstrap das voltas (1.000 reamostragens, semente 38).
- **A consistência** fica fora do vetor de estilo e é relatada à parte (pesquisa de datasets).
- **A minha assinatura** é calculada sessão a sessão e chamada de "assinatura atual".

### 1.8 O modelo supervisionado leve (Parte G)

- **Por curva:**
  - **o alvo** é o tempo do trecho da curva (1.3) em cada passagem do piloto;
  - **as entradas** são os indicadores principais dos detectores da curva com valor em pelo menos 80% das passagens do piloto. Falta é preenchida com a mediana do treino, e tudo é padronizado com o treino.
- **A forma:** uma regressão ridge, com o alvo e as entradas centrados pela média de cada sessão. É a sessão como efeito fixo; o statsmodels, que faria os efeitos mistos, não está instalado, e o pedido proíbe instalar. O modelo só mede a associação dentro de uma sessão, sem o ganho de ritmo de uma sessão para outra.
- **A regularização:** α entre {0,3; 1; 3; 10; 30; 100}, escolhido por "deixar uma sessão de fora" dentro das sessões de treino.
- **A validação:** deixar uma sessão de fora (por fora), com R² = 1 − Σ(erro)²/Σ(desvio da média do treino)² nas sessões de fora. Só curvas com 30 passagens ou mais e 3 sessões ou mais.
- **A saída:** o coeficiente padronizado de cada entrada (segundos por desvio), com o intervalo de 90% de um bootstrap das voltas dentro das sessões (500 reamostragens, com o α escolhido em todos os dados). O sinal é estável se o intervalo não cruza o zero.
- **É descritivo:** mostra associação, não causa, e não vira ganho estimado (ADR 0004).

### 1.9 O kit de rotulagem (Parte H)

- **Os detectores:** F4 (soltura), F5 (trail braking), M6 (retomada), E2 (subesterço) e E3 (sobresterço).
- **As passagens:** 24 por detector, sorteadas com a semente 38:
  - estratificadas pelo estado do detector (8 de cada estado; o que faltar num estado é completado com os outros);
  - com até um terço da IA, quando houver;
  - E2 e E3 só têm a IA nas passagens com a guinada (a volta de 22/10).
- **O que o kit mostra:** a posição na pista e os traços de pedal, volante, velocidade e guinada, com as fronteiras das fases.
- **O que o kit esconde:** o estado do detector e a origem (IA ou piloto). Os dois ficam num gabarito fora do git, com o hash no `resultados.json`.
- **Depois da rotulagem:**
  - a precisão e a revocação de "aplica" contra os rótulos "aplica" e "não aplica" do Eduardo;
  - as passagens "não sei" e as "não conclusivas" do detector ficam fora da conta e são contadas à parte.

### 1.10 O que se espera, antes de ver qualquer número

Espero que as maiores perdas contra a IA estejam na frenagem e na entrada das curvas lentas que alimentam retas longas (C01, C04 e C10), explicadas pelo ponto de frenagem antecipado e por uma soltura em degrau sem trail braking, que a IA aplica na maioria das curvas com frenagem e eu em poucas.
