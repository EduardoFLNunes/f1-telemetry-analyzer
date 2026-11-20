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

---

## 2. Emendas de 25/10/2026, depois da primeira rodada

A seção 1 não muda. A primeira rodada mostrou três coisas, registradas aqui com o motivo:

1. **Correção de código, sem mudar regra: as pontas das fases.** Na primeira rodada, a soma das 70 fases diferia da diferença de tempo de volta em até 0,069 s. O fim de uma fase e o começo da seguinte eram arredondados de jeitos diferentes, e um ponto da grade podia entrar em duas fases ou em nenhuma. Agora as duas pontas usam o mesmo índice da grade, e a soma fecha em 0,000 s, como a seção 1.6 diz.
2. **O escorregamento acima de 10 sai da conta.** A seção 1.5 diz que um canal não confiável no trecho dá "não conclusivo", mas não registrou como reconhecer um escorregamento quebrado.
   - **O que apareceu:** numa volta minha de 04/10, o escorregamento traseiro marcou 290 na C11, contra uns 0,4 nas outras voltas. Esse valor sozinho levava o R² do modelo leve da C11 a −1.027.
   - **A distribuição no store v2:** mediana 0,20, percentil 99 de 1,05, percentil 99,99 de 7,6.
   - **A regra nova:** um ponto com escorregamento acima de 10 é leitura quebrada (ou roda no ar) e sai da conta. Se a janela de um detector fica sem pontos, o detector dá "não conclusivo".
3. **Um ranking informativo, ao lado do registrado.** O peso da curva (o comprimento da reta seguinte, seção 1.3) põe a perda na reta principal e na reta oposta à frente de tudo em todas as sessões. Ele também zera o peso das curvas seguidas de outra curva (C01, C07, C08 e C09). Por isso, a saída traz também os 3 itens de maior perda **sem o peso**, com a mesma atribuição. Ele não substitui o ranking registrado.

**Limitações das regras registradas, sem mudança agora** (para decidir num pedido próprio):

- **s_pu, a retomada,** é o primeiro acelerador ≥ 0,10 depois do fim da frenagem e do s_ti. A IA usa acelerador parcial na entrada: na mediana, ela "retoma" de 1,1 a 1,9 s antes da mínima nas curvas lentas. Com isso:
  - M6 dá "não aplica" em quase todas as passagens, da IA e minhas;
  - M7 (volante crescendo depois da retomada) dá "aplica" na IA.

  Uma regra melhor procuraria a última subida do acelerador antes do pleno.
- **s_ti** é o começo da sequência de volante que contém o ápice. Um contraesterço antes do ápice corta essa sequência e fica fora da janela de E4.
- **A frenagem "emendada":** quando a frenagem de uma curva continua depois do ápice da anterior (C09 para C10, por exemplo), s_b cai no ápice anterior. É a mesma situação que o relatório de evolução marca como "freada emendada".

---

## 3. O que o Modelo 2 faz, em linguagem simples

O Modelo 2 olha cada curva das voltas gravadas e responde a três perguntas:

1. **Onde eu perco tempo contra a IA, e por quê?**
2. **Que técnicas a IA aplica e quais eu aplico?**
3. **Como cada um pilota?** Esse é o estilo.

Ele faz isso em quatro passos.

### 3.1 As fases da curva (Parte C)

Cada uma das 14 curvas é cortada em cinco pedaços:

- **frenagem:** do ponto em que se começa a frear até a curva começar;
- **entrada:** do começo da curva até perto do ápice;
- **meio:** o trecho mais fechado, em volta do ápice;
- **saída:** do meio até o fim da curva;
- **reta seguinte:** até a frenagem da próxima curva.

Os cortes são os mesmos em todas as voltas. Assim, "a frenagem da C04" é o mesmo pedaço de pista na volta da IA e na minha, e o tempo de cada pedaço pode ser comparado. Os 70 pedaços somam a volta inteira. A tabela com os metros de cada fronteira está no relatório do pedido 38.

### 3.2 A localização do erro (Parte D)

- **A perda:** para cada pedaço, é o tempo que levei nele menos o tempo da volta da IA no mesmo pedaço.
- **O que entra no ranking:** a perda tem de aparecer em pelo menos 2 das 3 últimas voltas da sessão, para não confundir um erro de uma volta com um hábito.
- **A cadeia causal:**
  - uma perda na saída que vem de uma entrada mal feita é procurada na entrada;
  - frear mais tarde e perder mais na entrada do que se ganhou na frenagem é um **falso ganho**, e não melhora.
- **A atribuição:** para cada perda, o Modelo 2 procura o detector (3.3) em que eu e a IA fazemos diferente, e em que a minha melhor volta faz como a IA. Se nenhum detector explicar, a resposta é "não conclusivo", e o Modelo 2 não inventa causa.

### 3.3 Os detectores de técnica e de erro (Parte E)

Um detector é uma regra que olha os pedais, o volante, a velocidade e a guinada numa curva e diz se uma técnica foi aplicada (ou se um erro aconteceu). Por exemplo:

- o **trail braking** aplica quando o freio continua um pouco apertado depois que o volante começa a virar;
- a **soltura progressiva** aplica quando o freio é solto em rampa, e não de uma vez.

Cada detector tem três respostas: **aplica**, **não aplica** e **não conclusivo**. A última aparece quando falta o canal, quando o canal falha naquele trecho ou quando o valor fica na faixa de dúvida.

São 27 detectores, em quatro famílias:

- frenagem;
- entrada e equilíbrio;
- meio e saída;
- a volta inteira.

Os limiares vêm da pesquisa e são ajustados pela IA na mesma curva, porque um número publicado para outro carro não vale para este.

**Importante:** os detectores ainda não foram validados. O Eduardo vai rotular 120 passagens à mão (o kit da Parte H), e só depois se sabe quanto cada detector acerta (a precisão e a revocação). Até lá, nenhum deles vai para o rádio nem para o coach (ADR 0023, item 4).

### 3.4 A assinatura de estilo (Parte F)

O estilo é descrito por seis dimensões contínuas, sem rótulos fixos:

- a forma da curva (V ou U);
- o perfil de frenagem;
- o uso dos pedais;
- a resposta do carro na entrada;
- a aplicação do volante;
- o perfil do acelerador.

Elas são calculadas para curvas lentas, médias e rápidas. Cada número é um escore-z: quantos "desvios típicos" eu ou a IA estamos acima ou abaixo do conjunto de todas as passagens. Para um iniciante, a assinatura muda de sessão para sessão, por isso ela se chama **assinatura atual**.

A consistência (o quanto eu repito a mesma curva) fica de fora do estilo, porque mede habilidade.

### 3.5 O modelo supervisionado leve (Parte G)

Para cada curva, o modelo mede quais indicadores dos detectores andam junto com um tempo menor no trecho, nas minhas voltas, dentro de cada sessão. Ele é testado deixando uma sessão de fora de cada vez.

Ele **mostra associação, não causa,** e não promete ganho (ADR 0004). Serve para ver quais detectores importam neste carro e nesta pista.

### 3.6 Onde ficam as saídas

| saída | onde |
|---|---|
| o comando | `python -m ml.scripts.modelo2 todos --saida <pasta>` (de `backend/`); desde o pedido 42, cada rodada grava em `data/ml/modelo2/<pasta>/`, só com os 144 `lap_id` da rodada 1 (seção 4.6) |
| os dados intermediários | `data/ml/modelo2/` (fora do git): as passagens, os estados de cada passagem, os derivados e o gabarito do kit |
| os resultados do pedido 38 | `docs/handoff/2026-10-24_38_modelo2-erro-tecnica-e-estilo_*.json` |
| o kit de rotulagem | `docs/handoff/2026-10-24_38_modelo2-erro-tecnica-e-estilo_kit_rotulagem.html` e `_rotulagem.csv` |
| a precisão e a revocação, depois da rotulagem | `python -m ml.scripts.modelo2 rotulos --rotulos <o csv preenchido>` |

---

## 4. Rodada 2: as emendas de 29/10 e a referência de 15/11 (registrado em 17/11/2026, antes de rodar)

Pedido 42, Parte A. Esta seção foi escrita e commitada **antes de qualquer conta da rodada 2**, antes da rodada 1 refeita e sem ler o store v2. As seções 1 e 2 não mudam: a rodada 1 continua registrada como está, e as duas rodadas aparecem lado a lado.

### 4.1 A honestidade da rodada

A rodada 2 muda duas coisas, decididas antes de qualquer conta deste pedido:

- **as três emendas** (4.2), decididas pelo Eduardo em 29/10, **depois de ver a rodada 1 e antes da H.4** (a precisão contra os rótulos, que ainda não rodou);
- **a referência** (4.4): a volta do modelo, por decisão do Eduardo de 15/11 (ADR 0032).

Para separar os dois efeitos, a perda e o ranking da rodada 2 também são calculados **contra a `#0013`**, a referência da rodada 1. Essas saídas são marcadas "só comparação" e não valem como resultado.

### 4.2 As emendas, com os valores fixos

**A retomada, s_pu (troca a regra de 1.4).**

- **A busca:** de s_vmin (a menor velocidade entre a_k e e_k, como em 1.4) até e_k + 50 m, o mesmo fim da rodada 1. A retomada nunca fica antes da mínima.
- **O começo da subida:** o último ponto, desde s_vmin, em que o acelerador está no menor valor visto até ali, com uma tolerância de 0,02.
- **A subida** tem de levar o acelerador a pelo menos **0,10 acima** do valor do começo. É o mesmo 0,10 da rodada 1, agora como subida, e não como nível.
- **"Contínua"** quer dizer que, nos **0,5 s** depois do começo, o acelerador nunca fica abaixo do valor do começo menos **0,02**. Uma subida que volta abaixo disso é descartada, e a procura segue do novo mínimo.
- **O porquê dos valores** (da definição, sem olhar dados):
  - 0,5 s é o horizonte que a seção 1.5 já usa para a resposta da entrada. É mais longo que uma correção de pedal e mais curto que a ida da mínima ao pleno;
  - 0,02 é menos da metade do limiar de pedal de 1.4 (0,05). Ele existe para o ruído do canal não cortar a subida.
- **Acelerador já alto na mínima:** se o acelerador está em 0,90 ou mais em s_vmin, não há subida possível de 0,10. Então s_pu = s_vmin, e a passagem é marcada `retomada_no_pleno`.
- **Sem subida até e_k + 50 m:** a passagem fica "sem retomada", como na rodada 1.
- **s_full não muda:** o primeiro ponto depois de s_pu com acelerador ≥ 0,95.

**A entrada, s_ti (troca a regra de 1.4).**

- **O limiar:** o volante no sentido da curva passa de **0,15·δ_pk**, o mesmo número de 1.4 e do F5.
- **O porquê do limiar** (da definição):
  - "começar a virar para a curva" é medido em relação ao volante que a própria curva pede (δ_pk);
  - um limiar em graus confundiria uma correção de reta com a entrada numa curva rápida, e chegaria tarde num cotovelo;
  - manter o 0,15 deixa o F5 e o E1 com a mesma definição de "volante para dentro".

  O que muda é só o corte.
- **A regra nova:** a sequência de pontos com o volante acima do limiar, que contém o ápice, **não é cortada numa troca de sinal**. Dois trechos acima do limiar são unidos quando, no buraco entre eles, o volante passa para o outro lado além de **0,05·δ_pk** (o mesmo ruído do E4). s_ti é o começo dessa sequência unida.
- **Um buraco sem troca de sinal** (o volante só aliviou, sem passar para o outro lado) continua cortando, como na rodada 1.

**A janela do E4 (troca a janela de 1.5).**

- **O começo:** b_k, o início da fase de frenagem, fixo para todas as voltas (1.3).
- **Nas curvas sem frenagem** (C03, C05, C11, C13 e C14, conferidas nas fases da rodada 1), b_k = a_k: a janela começa no início da curva.
- **O fim** continua em e_k. O resto do E4 não muda.

**O ranking sem o peso (troca a pontuação de 1.6).**

- A pontuação de um item passa a ser **a perda mediana nas 3 voltas**, sem o peso da reta seguinte. O ranking sem peso, informativo na rodada 1 (seção 2, item 3), passa a ser o registrado.
- O ranking ponderado fica nas saídas como informativo.
- A fase "reta seguinte" continua sendo uma fase, com a perda dela. A consistência (V5) não muda.

### 4.3 A família inteira das emendas

Tudo o que usa s_pu, s_ti ou a janela do E4 segue as regras novas:

| o quê | usa | onde aparece |
|---|---|---|
| M6, retomada | s_pu (`retomada_s`) | detector; atribuição; indicador principal no modelo leve |
| M7, volante crescendo depois da retomada | s_pu | detector; condição do M6 |
| M8, alívio depois da retomada | s_pu até s_full | detector; condição do M6 |
| `retoma` (houve retomada) | s_pu | "não conclusivo" do M6, M7 e M8; "a IA retoma" do M6 |
| `apice_ao_pleno_s` | s_full, que depende de s_pu | estilo, perfil do acelerador |
| `retomada_s` na consistência do estilo e no desvio volta a volta da IA | s_pu | estilo; verificações da IA |
| a cadeia causal (retomada atrasada) | s_pu | ranking (1.6) |
| E1, entrada antecipada | s_ti (`s_ti_rel`) | detector; atribuição; indicador principal no modelo leve |
| F5, trail braking | s_ti (retenção e sobreposição desde s_ti) | detector; kit |
| E5 e E6, reversões e suavidade | s_ti até e_k | detectores |
| taxa de entrada | s_ti | ao lado do E1; estilo, aplicação do volante |
| `guinada_por_roda` e `beta_entrada` | s_ti | estilo, resposta na entrada |
| E4, contraesterço | a janela (agora desde b_k) | detector; estilo, resposta na entrada |

**Os limiares fixos e a regra de calibração não mudam.** Os detectores desta tabela continuam calibrados nas passagens da IA da mesma curva, pela regra de 1.5. Como o indicador deles mudou, os valores da calibração (med_ref, q90_ref e sdr) são refeitos pela mesma regra, com o indicador novo. Os outros detectores ficam com os mesmos valores, porque as passagens da IA são as mesmas.

### 4.4 A referência: a volta do modelo (ADR 0032)

- **A volta:** `2026-11-15_02-47-12_vhe_interlagos_teste_m1#0008`, com 1:24,552, lida de `data/reference_models/vhe_interlagos.volta_do_modelo.json`.
- **Os canais:** o arquivo tem, na grade de 2 m (2.167 pontos), o tempo, a lateral, a posição, a velocidade, a marcha e os pedais. **Ele não tem o volante nem a guinada.**
- **A regra:**
  - **da volta do modelo, só valem a linha, a velocidade e os pontos:** onde ela freia (s_b), a mínima (s_vmin e v_min) e onde ela retoma (s_pu, pela regra de 4.2);
  - **a forma dos pedais e do volante nunca é comparada com ela.** Os pedais dela são o comando da IA (ADR 0032, item 5): valem como pontos, e não como técnica. A forma é comparada com a "Sua melhor volta", ou fica "não julgada".
- **A "Sua melhor volta"** é a do app: `2026-10-24_13-43-32_vhe_interlagos#0003`, com 1:26,568 na grade da rodada 1 (o app mostra 1:26,566). É a mesma melhor volta da rodada 1. Quando a passagem for dela, a comparação usa a segunda melhor, e isso é registrado.

**Cada lugar do Modelo 2 que usa uma volta de referência:**

| lugar | rodada 1 | rodada 2 |
|---|---|---|
| a perda por fase e por curva (1.6) | contra a `#0013`, com a melhor volta ao lado | contra a volta do modelo (o relógio da grade dela), com a "Sua melhor volta" ao lado; e contra a `#0013`, "só comparação" |
| a conferência das fases | a soma das 70 fecha a diferença contra a `#0013` | fecha a diferença contra a volta do modelo (e contra a `#0013`) |
| o ranking por sessão | a perda contra a `#0013` | a perda contra a volta do modelo, sem o peso (4.2); e contra a `#0013`, "só comparação" |
| o falso ganho | "freia mais tarde que a IA": F1.x, contra a mediana das passagens da IA | "freia mais tarde que a volta do modelo": s_b da passagem − s_b da volta do modelo > T, com o mesmo T de F1 (max(10 m, 2·sdr da IA)). É um ponto |
| a cadeia causal | a retomada e a mínima contra a mediana das passagens da IA | a retomada (t(s_pu) − t(s_vmin)) e a mínima contra as da volta do modelo. São pontos |
| a atribuição do erro | os estados do piloto, da IA e da melhor volta | veja a regra abaixo |
| as fronteiras das fases e o tipo de curva | b_k pelas passagens da IA e do piloto; o tipo pela mínima da `#0013` | **não mudam:** as 70 fases são as da rodada 1, definidas uma vez na geometria oficial |
| a calibração dos limiares (1.5) | as passagens da IA | **não muda:** as passagens da IA são dados, e não referência |
| as comparações "IA e eu" (listas, frações, evolução, verificações da IA) | as voltas da IA | **não mudam**, pelo mesmo motivo |
| o envelope E(v) do M1 | todas as voltas rotuladas | **não muda**, porque não usa referência; calculado só nas 144 voltas (4.6) |
| as assinaturas de estilo e o modelo leve | sem referência | **não mudam** |
| o kit 2 e a galeria (Parte E) | o kit do 38 não mostrava referência | a volta do modelo em cinza (a linha e a velocidade; nos pedais, só os pontos) e a "Sua melhor volta" tracejada, em todos os canais |

**A atribuição do erro na rodada 2.** Os detectores da fase de origem se dividem em dois grupos.

- **De ponto:** F1 (s_b), M2 (s_vmin), M4 (a linha na saída) e a parte "atraso" do M6 (t(s_pu) − t(s_vmin)).
  - O valor de referência é o mesmo indicador medido na volta do modelo, com as mesmas funções.
  - Ele explica o item quando a diferença entre a mediana do piloto nas 3 voltas e o valor da volta do modelo passa do desvio robusto do piloto naquela curva (como em 1.6) **e** a "Sua melhor volta" fica mais perto da volta do modelo que a mediana do piloto.
- **De forma** (pedal e volante: F2 a F8, E2 a E6, M1, M3, M5, M7, M8, M9 e V3):
  - comparados com a "Sua melhor volta", e nunca com a volta do modelo;
  - um deles explica o item quando o estado do piloto (a maioria das 3 voltas, com pelo menos 2 conclusivas) difere do estado da melhor volta, os dois são conclusivos e a diferença do indicador principal (a mediana do piloto menos a melhor volta) passa do desvio robusto do piloto naquela curva.
- **O que sai:** entre os que explicam, vale o de maior diferença em desvios. **Se nenhum explicar, o resultado é "não conclusivo".**
- **A IA continua nos dados:** o estado da IA em cada detector vai ao lado, como informação. Os detectores de forma em que o estado da IA difere do piloto e a melhor volta concorda com o piloto são listados à parte, como "técnica da IA que nenhuma volta minha mostra". É o equivalente da "técnica que o piloto não mostrou em nenhuma volta" da rodada 1.
  - *Correção de redação de 17/11, antes de rodar:* a primeira redação desta frase descrevia o caso errado.

### 4.5 A margem de ±2 ms das sessões aceitas com margem

- **A decisão do Eduardo (17/11):** as 3 sessões em que a linha do jogo ficou fora da tolerância do pedido 34 (`2026-11-01_19-47-03`, `2026-11-07_18-46-00` e `2026-11-12_22-57-03`) são aceitas. A diferença no tempo, de cerca de 2 ms, é tratada como uma margem de erro para cima e para baixo.
- **De onde vem a lista:** do meta do store (`laps_grid_v2_meta.json`), e não de uma lista no código. O pedido 54 (`docs/store_v2_e_evolucao.md`, emenda de 17/11) registrou duas chaves:
  - `sessoes_aceitas_com_margem`: cada item com `sessao`, `mediana_m`, `diferenca_m`, `efeito_ms`, `voltas` e `decisao`;
  - `margem_linha_do_jogo_ms`: a margem, 2,0.

  A sessão do item é a gravação, comparada com `gravacao` da volta. Sem a segunda chave, vale 2,0 ms, pela decisão.
- **A regra:** numa passagem de uma sessão da lista, uma perda ou um ganho de até a margem, em módulo, por fase ou por curva, fica **"dentro da margem"**:
  - não conta como perda nem como ganho no ranking;
  - por isso, não entra na atribuição do erro.

  As perdas acima da margem entram como as outras. A regra registrada de 1.6 já exige 0,02 s para um item, então a margem só muda casos de borda. Mesmo assim, ela é aplicada e marcada.
- **As tabelas:** as passagens, as perdas e os rankings dessas sessões levam a marca `sessao_com_margem`.
- **Os detectores não mudam.** A linha do jogo só mexe no fechamento da volta (o tempo do ponto s = 0), e não nos tempos de dentro da volta. Os menores limiares de tempo dos detectores são 0,03 s (o "não aplica" do E4) e 0,05 s (o "não aplica" do F5 e do F7, e a faixa inicial do M5): 15 e 25 vezes a margem. Nenhum depende de tempo na escala de 2 ms.
- **Onde essas sessões entram:** são todas posteriores a 24/10. Elas não estão nas 144 voltas da comparação. Entram só na tabela à parte da Parte D.3 e no E3 das saídas de traseira de 01/11 (Parte D.6).

### 4.6 As voltas, as pastas de saída e a rodada 1 refeita

- **A comparação usa os 144 `lap_id` da rodada 1:** 130 do piloto e 14 da IA, das quais 10 vêm de fora do store.
  - **A fonte da lista** é o `docs/handoff/2026-10-24_38_modelo2-erro-tecnica-e-estilo_canais_e_conferencias.json`, no git (`d705d43f`). A lista é igual à de `data/ml/modelo2/passagens.parquet`.
  - **As 10 voltas de fora do store** são lidas como na rodada 1, do cache `fora_do_store.parquet` e `fora_do_store.json` da rodada 1. O store de 15/11 também tem as gravações de 24/10, mas, nessas voltas, a versão de fora do store continua valendo.
- **As fases, o envelope E(v) e a calibração** saem só dessas 144 voltas, nas duas rodadas.
- **As voltas novas** são as do piloto, na pista original, de sessões depois de 24/10. Elas são só medidas, com as fases, o envelope e a calibração das 144, e vão para a tabela à parte (Parte D.3).
- **Ficam fora de tudo:** as sessões na cópia da pista (`vhe_interlagos_teste_m1`), salvo a volta do modelo como referência, e as voltas de teste da Parte F.
- **As pastas de saída:**
  - `data/ml/modelo2/rodada1_refeita/` e `data/ml/modelo2/rodada2/`;
  - nada da rodada 1 em `data/ml/modelo2/` é sobrescrito: nem as saídas, nem o `derivados.parquet`, nem os caches de fora do store, nem o `rotulagem_gabarito.json`;
  - os caches da rodada 1 são só lidos. Uma taxa derivada que falte (das voltas novas) vai para o cache da pasta da rodada;
  - o kit 2 tem gabarito próprio, na pasta da rodada 2.
- **A rodada 1 refeita** roda as regras da rodada 1 (a seção 1 com as emendas de código da seção 2, como no commit `53d563f1`). Ela confere com os arquivos guardados:
  - os estados de cada detector, por passagem;
  - as perdas;
  - o ranking;
  - as fases;
  - o fechamento.

  Se não reproduzir, a diferença é relatada, e a Parte D não roda.

### 4.6.1 O E2 com a geometria medida (Parte C; registrado em 17/11, antes de rodar)

A seção 1.2 já previa recalcular o subesterço quando a M1 medisse o entre-eixos e a unidade do volante. Na rodada 2:

- **os valores** são `L` e `k_δ` como o pedido 39 os deixou: a chave `usados` de `docs/handoff/2026-10-25_39_m1-geometria-medida_geometria.json` (`L` = 2,9636 m; `k_δ` = 0,30396 rad de roda por unidade de volante). O código lê o arquivo, e não copia os números;
- **o que muda:** o E2, e a razão guinada ÷ ângulo de roda da resposta na entrada (estilo), que usa o mesmo `k_δ`. Os limiares do E2 (0,5° e 0,2° contra a mediana da IA) não mudam;
- **a rodada 1 refeita** continua com a medida substituta (`L` = 2,955 m; `k_δ` = 0,267 rad);
- **o relatório** dá, por curva, a fração de "aplica" do E2 antes e depois, para mim e para a IA.

**Duas medidas a mais, só relatadas** (não mudam nenhum estado):

- `contra_antes_apice_s`: a maior sequência de contraesterço da janela do E4 que acaba antes do ápice. Ela conta quantas passagens ganharam um contraesterço antes do ápice;
- `s_pu_rel`: a posição da retomada. Ela marca no kit 2 onde a Volta de referência retoma.

### 4.7 A frenagem emendada

Não muda. Uma passagem tem frenagem emendada quando a sequência de freio que dá s_b já está ligada no primeiro ponto da janela, ou seja, o freio continua desde o ápice anterior, p_(k−1). Ela é só contada, por curva, nas duas rodadas.

### 4.8 A validação, registrada antes de qualquer rótulo ou volta de teste

- **O kit 2 (Parte E.1):**
  - as mesmas 120 passagens do kit do 38 (semente 38), com as referências do app (4.4) e uma página por pergunta com a assinatura da literatura;
  - a origem e o estado do detector continuam escondidos;
  - **o que se espera:**
    - nos detectores de pedal (F4, F5), a precisão de "aplica" maior que nos de equilíbrio (E2, E3), que são lidos na guinada e na deriva, mais difíceis de ver nos traços;
    - "nao sei" em até um quarto das passagens, mais nos detectores de equilíbrio.
- **A consistência:** 30 das 120 passagens (semente 42), com outros ids e em outra ordem, rotuladas de novo pelo menos 3 dias depois.
  - **O que se espera:** o kappa de Cohen de 0,6 ou mais (concordância "substancial", na escala de Landis e Koch).
  - **Abaixo de 0,4,** os rótulos não dão base para a precisão, e isso é dito no relatório. Nenhum limiar muda por isso.
- **A galeria (Parte E.2), gerada só depois dos rótulos:** 3 passagens "aplica" e 3 "não aplica" de cada um dos 5 detectores, ao lado do desenho da literatura.
  - **O que se espera:** que o "aplica" de F4, F5 e M6 se pareça com o desenho em pelo menos 2 das 3 passagens.
- **As voltas de teste (Parte F):** cada comportamento provocado em 3 passagens, com 3 de controle nas mesmas curvas.
  - **O que se espera:**
    - o detector certo marca "aplica" em pelo menos 2 das 3 provocadas e em no máximo 1 das 3 de controle;
    - os detectores de outras famílias não mudam.

    A tabela esperada, comportamento a comportamento, é registrada no roteiro (F.1), antes das sessões.
- **Nenhum limiar muda por causa dos rótulos, da galeria ou das voltas de teste.** Uma falha vira proposta de emenda para uma rodada 3, registrada antes de rodar.

---

## 5. Rodada 3: a emenda da entrada (registrado em 18/11/2026, antes de rodar)

Pedido 42, "Atualização de 18/11", item 1. A seção 4 não muda. A rodada 3 muda uma coisa só: o ponto de entrada, s_ti.

### 5.1 Por que

**O que a rodada 2 mostrou:** a regra da seção 4.2 ("não cortar na troca de sinal") une dois trechos de volante acima do limiar quando, no buraco entre eles, o volante passa para o outro lado além de 0,05·δ_pk.

- **Onde falha:** nas curvas que vêm depois de outra curva para o mesmo lado (C01 depois da C14, C04 depois da C03, C07 depois da C06, C12 depois da C11 e C14 depois da C13).
- **Por quê:** o volante passa levemente para o outro lado na reta entre as duas curvas, e a regra une o volante da curva anterior ao desta. Na C04, a entrada recuou 531 m na mediana.
- **O efeito:** o E1, o F5, o E5, o E6 e a entrada do estilo dessas curvas ficaram contaminados.

A emenda foi decidida pelo Eduardo em 18/11, depois de ver a rodada 2.

### 5.2 A regra

- **O limiar e a troca de sinal não mudam:** o volante no sentido da curva acima de 0,15·δ_pk, e a troca de sinal além de 0,05·δ_pk no buraco.
- **A união só vale entre o fim da curva anterior, e_(k−1), e o ápice:**
  - dois trechos só são unidos quando os dois estão nesse intervalo, ou seja, quando o trecho anterior começa em e_(k−1) ou depois;
  - um trecho que começa antes de e_(k−1) (o volante da curva anterior, mesmo que passe do fim geométrico dela) nunca é unido;
  - fora disso, a sequência é cortada como na rodada 1.
  - *Correção de redação de 18/11, antes de rodar a rodada 3:* a primeira redação deixava unir um trecho que começava antes de e_(k−1) e acabava depois, com a sequência começando em e_(k−1). O teste sintético (duas curvas para o mesmo lado) mostrou que isso ainda levava a entrada até o fim da curva anterior, a 620 m. Isso é contra a decisão do Eduardo ("a união só vale entre e_(k−1) e o ápice"). Nenhuma conta da rodada 3 tinha rodado.
- **Um trecho único,** sem buraco, que já começa antes de e_(k−1) (o volante não volta abaixo do limiar entre as duas curvas) continua como na rodada 1. Nada é unido aí.
- **Na C01,** a curva anterior é a C14, no fim da volta, e a janela atravessa o s = 0. Vale a mesma definição que as fases já usam:
  - a distância é medida para a frente, com o módulo do comprimento da volta (`fases.ahead` e `fases.window`);
  - e_(k−1) é o fim geométrico da C14 (e_14), contado a partir do ápice da C14, que é o começo da janela da passagem.

### 5.3 O que não muda

- a retomada, a janela do E4 (desde b_k), o ranking sem peso;
- a referência (a volta do modelo, e a `#0013` só como comparação);
- a margem de ±2 ms e os 144 `lap_id`;
- o E2 com a geometria do pedido 39;
- as fases, o envelope e a calibração das 144 voltas.

### 5.4 A família e a calibração

- **Quem segue a regra nova:** todos os detectores e atributos que usam s_ti, a lista da seção 4.3:
  - E1 (`s_ti_rel`, também no modelo leve) e F5;
  - E5 e E6;
  - a taxa de entrada, a `guinada_por_roda` e a `beta_entrada`.
- **A calibração:** os detectores cujo indicador mudar são recalibrados pela mesma regra, nas mesmas passagens da IA, como na rodada 2.

### 5.5 As saídas e o relato

- **As saídas** vão para `data/ml/modelo2/rodada3/`. Nada da rodada 1 nem da rodada 2 é sobrescrito.
- **O relato, ao lado da rodada 2:**
  - o recuo da entrada por curva;
  - nas 5 curvas, o E1, o F5, o E5, o E6 e o estilo da entrada;
  - nas outras 9, a confirmação de que nada mudou, ou o que mudou e por quê;
  - o modelo leve;
  - os 3 maiores erros por sessão;
  - o fechamento das fases.
- **Se a rodada 3 mostrar outro defeito,** nada muda depois de ver os números: ele é relatado e vira proposta.
- **A precisão (E.2)** sai para as três rodadas, com os mesmos rótulos. O kit 2 não muda.
- **O M7 na IA** fica registrado como limitação: ele dá "aplica" em 9 das 14 curvas na rodada 2, porque o volante da IA continua crescendo depois da retomada. Nada muda nele agora.

---

## 6. Rodada 4: a entrada a partir do início da frenagem (registrado em 18/11/2026, antes de rodar)

Pedido 42, "Atualização de 18/11, à tarde", item 1. A seção 5 não muda. A rodada 4 muda só onde a união dos trechos da entrada pode começar. **É a última mudança de regra antes dos rótulos** (item 2).

### 6.1 Por que

**O que a rodada 3 mostrou:** ela resolveu a entrada na C01, na C07, na C12 e na C14, mas sobrou um segundo defeito.

- **Onde:** na C04 (29 passagens minhas) e na C06 (17).
- **O que acontece:** uma correção de volante na reta, depois do fim da curva anterior, passa de 0,15·δ_pk e é unida à entrada pela troca de sinal. Na C04, a entrada dessas passagens ficou a uns 576 m da curva (mediana).

A emenda foi proposta no relatório de 18/11 e aprovada pelo Eduardo em 18/11, à tarde.

### 6.2 A regra

- **O limiar e a troca de sinal não mudam:** 0,15·δ_pk, e 0,05·δ_pk para o outro lado no buraco.
- **A união só vale a partir do início da fase de frenagem, b_k, até o ápice.** É a mesma janela do E4 da seção 4.2.
  - Nas curvas sem frenagem (C03, C05, C11, C13 e C14), b_k = a_k.
  - Dois trechos só são unidos quando os dois estão nesse intervalo, ou seja, quando o trecho anterior começa em b_k ou depois.
  - Um trecho que começa antes de b_k nunca é unido; fora disso, a sequência é cortada como na rodada 1.
- **Um trecho único,** sem buraco, que já começa antes de b_k, continua como na rodada 1. Nada é unido aí.
- **Como b_k fica** sempre entre e_(k−1) e a_k (seção 1.3), a janela da rodada 4 fica dentro da janela da rodada 3. A rodada 4 só pode unir menos.
- **Na C01,** depois da C14, vale a mesma definição das fases, com o módulo do comprimento da volta.

### 6.3 O que não muda

O resto é a rodada 3:

- a família (a lista da seção 4.3) e a recalibração pela mesma regra, nas mesmas passagens da IA;
- a retomada, a janela do E4, o ranking sem peso;
- a referência (a volta do modelo e a `#0013` só como comparação);
- a margem de ±2 ms e os 144 `lap_id`;
- o E2 com a geometria do pedido 39.

### 6.4 As saídas e o relato

- **As saídas** vão para `data/ml/modelo2/rodada4/`, com o próprio gabarito do kit 2. Nada das rodadas 1 a 3 é sobrescrito.
- **O relato, ao lado da rodada 3:**
  - o recuo da entrada por curva. Na C04 e na C06, ele deve ficar perto de zero;
  - nas outras curvas, a confirmação de que nada mudou, ou o que mudou e por quê;
  - o E1, o F5, o E5 e o E6 por curva, eu e a IA;
  - o E4, que não deve mudar, porque a janela é a mesma;
  - o modelo leve, os 3 maiores erros por sessão e o fechamento das fases.
- **Se a rodada 4 mostrar outro defeito,** nada muda: ele fica relatado e registrado como trabalho futuro.
- **A E.2** julga as quatro rodadas como estão, com os mesmos rótulos. A rodada que vale para o TCC é a 4; as outras aparecem como o caminho até ela.

---

## 7. Os rótulos pelos critérios da literatura (registrado em 20/11/2026, antes de rodar)

Pedido 42, "Atualização de 20/11". As seções 1 a 6 e as rodadas 1 a 4 não mudam.

### 7.1 Por que, e o nome do resultado

- **A decisão:** o Eduardo não é piloto, e o risco de rotular errado lendo a telemetria é grande demais. Em 20/11, ele decidiu que cada passagem do kit 2 é rotulada por um critério numérico tirado da literatura.
- **O que fica sem uso:**
  - o CSV de rótulos do pedido 38 fica vazio;
  - o kit 2 fica como material de figura;
  - a consistência das 30 passagens sai do pedido.
- **O nome do resultado:** deixa de ser "precisão contra rótulos humanos" e passa a ser **"concordância com um critério independente da literatura"**.
- **A medida contra a verdade** continua sendo a das voltas provocadas (Parte F), em que o Eduardo só marca o que fez de propósito.

### 7.2 A independência

- **O código** fica em `backend/ml/modelo2/rotulos_literatura.py`. Ele não importa o código dos detectores (`detectores.py`) nem o da calibração. Também não lê o estado dos detectores nem os gabaritos.
- **O que ele recebe:**
  - os traços da passagem na grade de 2 m (os mesmos canais do kit: pedais, volante, velocidade, guinada, aceleração lateral, velocidades no referencial do carro e o tempo);
  - as fronteiras geométricas da curva (o começo, o ápice e o fim, e o meio da seção 1.3) e o sentido dela;
  - o `L` e o `k_δ` do pedido 39 (a chave `usados` de `docs/handoff/2026-10-25_39_m1-geometria-medida_geometria.json`), lidos do arquivo;
  - a referência do próprio carro do item 7.4 (E2): o gradiente de subesterço nas voltas do Eduardo, com aceleração lateral baixa.
  - **Nunca a mediana da IA,** que calibra os detectores.
- **Quem chama o módulo:** um script à parte (o comando `literatura` de `ml.scripts.modelo2`).
  - Ele tira do gabarito do kit do 38 só o endereço de cada passagem (o id, a pergunta, a volta e a curva), sem o estado nem a origem, e passa ao módulo só os traços.
  - A concordância com as rodadas é calculada depois, por outro código, que junta os rótulos e os gabaritos.
- **Os limiares:** nenhum limiar do rótulo é cópia de um limiar de detector. As coincidências que existem por definição estão ditas em cada critério.

### 7.3 Os três resultados

Cada critério dá **aplica**, **nao aplica** ou **nao sei**. É "nao sei" quando:

- falta o canal;
- o evento que o critério mede não existe na passagem;
- o valor cai na faixa do meio.

### 7.4 Os critérios

**F4, soltura progressiva do freio** (Sector4, Brake release trace patterns; Coach Dave, A delta guide: understanding brake traces).

- **A frenagem:** a sequência de freio que contém o maior freio entre o ápice anterior e o ápice da curva.
  - **Sem frenagem:** com o maior freio abaixo de 0,10, a passagem não tem frenagem para julgar, e o resultado é "nao sei". É escolha do projeto: um freio abaixo de 10% não é uma frenagem de curva.
- **A descida:** do último ponto com freio ≥ 0,9 do maior até o primeiro ponto depois dele com freio < 0,02 do maior.
- **O penhasco:** uma descida inteira em 0,20 s ou menos é um degrau, e o resultado é "nao aplica". É escolha do projeto: 0,20 s é o tempo de tirar o pé de uma vez.
- **A gagueira:** se, na descida, o freio volta a subir 0,04 ou mais acima do menor valor anterior, o resultado é "nao aplica". A gagueira e o platô são os padrões ruins da Sector4. O 0,04 é escolha do projeto: acima do ruído do pedal.
- **O último terço da descida (no tempo)** é normalizado de 0 a 1 na pressão (dividido pelo valor no começo do terço) e no tempo, e reamostrado em 30 pontos.
- **A comparação:** a distância DTW (Al-Din 2023; a soma das diferenças absolutas no melhor alinhamento, dividida pelo número de pontos) a dois moldes:
  - **a rampa curva:** y = (1 − x)²; a soltura boa é curva, e não linear (Sector4; Coach Dave);
  - **o degrau:** y = 1 até x = 0,5 e 0 depois.
- **O resultado:**
  - **aplica:** a distância à rampa é menor que 0,8 da distância ao degrau;
  - **nao aplica:** a distância ao degrau é menor que 0,8 da distância à rampa;
  - **nao sei:** as duas distâncias ficam dentro de 20% uma da outra (escolha do projeto), ou o terço tem menos de 4 pontos da grade.

**F5, trail braking** (Velenis, Tsiotras e Lu 2008; Coach Dave; Virtual Racing School; Fanatec).

- **"Começa a virar":** o último ponto antes do ápice em que o volante, no sentido da curva, sobe acima de **0,25** do maior volante da curva. É escolha do projeto, e é diferente do 0,15 do detector: 25% marca uma entrada já decidida, e não uma correção.
- **O freio nesse instante,** em fração do pedal. A literatura dá **5% a 10%** mantidos (Virtual Racing School); o número usado é o 5%.
  - **Uma coincidência por definição:** o 0,05 do detector é o "pedal acionado" (seção 1.4), e aqui é o número da literatura.
  - Ao redor dele, uma faixa de ±0,01 é "nao sei" (o ruído do pedal; escolha do projeto).
- **A sobreposição:** do instante de virar até o primeiro ponto com freio < 0,02, ou até o ápice. Nela, a correlação de Pearson entre o freio e o volante: o freio desce enquanto o volante sobe (Velenis et al.).
- **O resultado:**
  - **aplica:** freio ≥ 0,06 no instante de virar, e correlação ≤ −0,2 na sobreposição, com 5 pontos ou mais. O −0,2 é escolha do projeto: uma tendência negativa clara, sem exigir uma reta;
  - **nao aplica:** freio < 0,04 no instante de virar;
  - **nao sei:** o meio; ou a curva sem frenagem (o maior freio da janela abaixo de 0,10); ou sem o volante.

**M6, retomada do acelerador** (Coach Dave, cornering; Fanatec, speed graph).

- **A janela:** da velocidade mínima (entre o começo e o fim da curva) até o fim da curva.
- **A subida:** começa no primeiro ponto em que o acelerador passa 0,08 acima do menor valor visto desde a mínima. É escolha do projeto: 8% do curso do pedal, acima da modulação.
- **Medido da subida até o fim da curva:**
  - **a queda total:** a soma de todas as descidas do acelerador;
  - **o volante crescendo:** o maior volante, no sentido da curva, menos o volante no começo da subida, dividido pelo maior volante da curva.
- **O resultado:**
  - **aplica:** queda total ≤ 0,08 e volante crescendo ≤ 0,05;
  - **nao aplica:** queda total ≥ 0,20 (um alívio claro, um quinto do pedal) ou volante crescendo ≥ 0,20;
  - **nao sei:** o meio; ou o acelerador sem cair abaixo de 0,92 na janela (nada a retomar); ou sem subida.
- **Os números** são escolha do projeto: a literatura só descreve a forma, a subida contínua sem corte nem hesitação.
- **Este é o rótulo menos independente:** a regra do M6, desde a rodada 2, já mede a subida contínua depois da mínima. A concordância do M6 deve ser lida com isso em mente.

**E2, subesterço** (Milliken e Milliken, pelo canal do MoTeC i2; SAE J670 e ISO 8855; a ideia do ensaio de raio constante da ISO 4138).

- **O ângulo de subesterço:** UA = δ_roda − L·a_y/v², em graus.
  - δ_roda = −k_δ·volante, positivo para a esquerda;
  - a_y é a aceleração lateral, positiva para a esquerda;
  - v é a velocidade;
  - o sinal é virado pelo sentido da curva, para que positivo seja subesterço.
- **A reta do próprio carro:** nas voltas do Eduardo (as 130 das 144), nos pontos com 0,10 g ≤ |a_y| ≤ 0,35 g e v ≥ 50 km/h, a reta de mínimos quadrados de UA contra a_y (em g) dá o gradiente K_us e o intercepto.
  - Os limites são escolha do projeto: abaixo de 0,10 g, o ruído do volante domina; até 0,35 g, longe do limite de aderência do carro (perto de 2 g), o pneu ainda está na faixa linear.
  - O corte de 50 km/h é o do canal do MoTeC.
- **Na passagem,** no meio da curva, nos pontos com |a_y| ≥ 0,5 g (fora da faixa linear) e v ≥ 50 km/h, mede-se a mediana do excesso: UA menos a reta.
- **O resultado:**
  - **aplica:** excesso ≥ 1,0°;
  - **nao aplica:** excesso ≤ 0,4°;
  - **nao sei:** entre os dois; ou menos de 5 pontos; ou sem a guinada (as voltas da IA de 04/10).
- **Os números** 1,0° e 0,4° são escolha do projeto: um grau a mais de ângulo de roda que a curva pede é um subesterço claro, e 0,4° fica dentro do ruído do volante.

**E3, sobresterço** (Bosch, Automotive Electronics Handbook, cap. 17, citando Shibahata; Linköping, TSFS02, aula 7; Pitschi et al. 2026; Kegelman, Harbott e Gerdes 2017).

- **A janela:** do começo da curva até 60 m depois do fim. Ela pega a saída, onde as saídas de traseira de 01/11 aconteceram.
- **Três sinais absolutos:**
  - **(a) o contraesterço:** o ângulo de roda para fora da curva, além de 0,5°, com a aceleração lateral ainda para dentro, acima de 0,3 g, por 0,15 s ou mais;
  - **(b) a deriva:** |β| = |atan2(v_lat, v_long)| de **10° ou mais**, por 0,1 s ou mais. O 10° é o número da literatura: a perda de dirigibilidade no seco (Bosch, citando Shibahata);
  - **(c) a guinada acima da referência:**
    - a referência é r_ref = v·δ_roda/(L + K_us·v²/g), com o K_us da reta do E2, limitada a μg/v, com μ = o percentil 99 de |a_y| nas voltas do Eduardo (o limite do próprio carro);
    - o sinal (c) dispara quando a guinada, no sentido da curva, passa de r_ref por 0,10 rad/s ou mais, por 0,20 s ou mais.
- **Os números** 0,5°, 0,3 g, 0,15 s, 0,10 rad/s e 0,20 s são escolha do projeto: além do ruído do volante e da guinada, e por um tempo que exclui um pico de um ponto.
- **O resultado:**
  - **aplica:** qualquer um dos três sinais;
  - **nao aplica:**
    - a guinada nunca passa de r_ref por mais de 0,05 rad/s;
    - |β| fica abaixo de 5° (a metade dos 10°) em toda a janela;
    - nenhum contraesterço;
  - **nao sei:** o meio; ou sem a guinada e as velocidades no referencial do carro, quando o sinal (a) não disparou.

### 7.5 A ordem

1. este registro, commitado;
2. **o teste do E3 nas 7 saídas de traseira de 01/11, antes das 120.** Se o critério não pegar as duas passagens da C06 que passaram de 59°, o trabalho para. O relatório dá o sinal que disparou em cada uma;
3. os rótulos das 120 passagens em `data/ml/modelo2/rotulagem/2026-11-20_42_rotulos_literatura.csv` (o id, a pergunta, a curva, o rótulo, o critério que decidiu, o valor medido e a margem), com cópia em `docs/handoff/`;
4. **a concordância com as quatro rodadas, por detector:**
   - a tabela 2×2, o kappa de Cohen e a fração de acordo, nas passagens em que o rótulo e o detector são conclusivos;
   - os "nao sei" e os "não conclusivos" à parte;
   - a rodada que vale é a 4;
5. a galeria (E.2.5): 3 passagens "aplica" e 3 "não aplica" da rodada 4 em cada pergunta, ao lado do desenho da literatura;
6. a seção da H.4 no relatório do 38, com os nomes do item 7.1.

### 7.6 As fontes (abertas e lidas pelo Eduardo em 20/11)

- Velenis, Tsiotras e Lu (2008), Trail-Braking Driver Input Parameterization for General Corner Geometry, SAE 2008-01-2986;
- Kegelman, Harbott e Gerdes (2017), Insights into vehicle trajectories at the handling limits: analysing open data from race car drivers;
- Pitschi et al. (2026), Stability Control for Real World Testing in Autonomous Racing;
- Bosch, Automotive Electronics Handbook, cap. 17, Stability Control;
- Linköping University, TSFS02, aula 7, controle de estabilidade;
- ISO 4138:2021 (a prévia);
- Ratner et al. (2017), Snorkel: Rapid Training Data Creation with Weak Supervision, para a ideia de rótulos por regras que votam ou se abstêm;
- Al-Din (2023), Driving Maneuvers Recognition and Classification, IJACSA 14(2), para o DTW com moldes;
- os guias técnicos: Coach Dave Academy (brake traces; cornering types), Sector4 (brake release trace patterns), Virtual Racing School (braking technique), Fanatec (trail braking; speed graph), o fórum da MoTeC (oversteer maths formula), o Rennlist (understeer/oversteer visualization) e a Wikipedia (Understeer and oversteer).

Milliken e Milliken (Race Car Vehicle Dynamics), Segers (Analysis Techniques for Racecar Data Acquisition) e o texto completo da ISO 4138 não foram lidos: entram só como citados pelas fontes acima.
