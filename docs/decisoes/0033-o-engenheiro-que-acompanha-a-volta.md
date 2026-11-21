# 0033 — O engenheiro que acompanha a volta

- **Status:** aceita (pedido 52). Registrada antes de qualquer código, antes de ler os arquivos da pista e antes de qualquer conta nas gravações
- **Data:** 2026-11-15
- **Decisor:** Eduardo
- **Usa:** a volta do modelo como referência (ADR 0032), os 15 trechos e os pontos de linha (ADR 0030), as causas e os limites do rádio (ADR 0027), o app do jogo (ADRs 0020 e 0021). **Refina:** 0021 (o app do jogo passa a desenhar na pista) e 0027 (o feedback espera os blocos de voz). **Mantém:** o Modelo 1, o Modelo 2, o store v2 e a volta do modelo

## Contexto

1. **O engenheiro** é a parte do Modelo 2 que leva o diagnóstico ao piloto durante a volta (ADR 0018: o rádio é o caminho do Modelo 2 até o piloto). O Modelo 1 diz onde e quanto (a volta do modelo, ADR 0032); o Modelo 2 diz por quê (as causas que o rádio do pedido 45 mede); o engenheiro diz o que fazer, antes da curva, por um marco que se vê na pista.
2. **As decisões do Eduardo de 14/11 e 15/11:**
   - toda curva com perda é avisada, sem limite de quantidade;
   - a referência é a volta do modelo (`data/reference_models/vhe_interlagos.volta_do_modelo.json`). Num trecho em que o piloto for mais rápido que ela, a referência daquele trecho é a melhor passagem dele. A volta da IA do jogo nunca é referência;
   - o aviso vem durante a volta, antes da curva, pelo marco da pista e depois os metros ("Curva 1: freie 10 metros depois da placa de 100"). Nunca "xx metros antes da curva": o piloto não tem trena, só os marcos;
   - a voz faz duas coisas: o aviso antes da curva e o feedback das curvas, nas retas. O bipe fica para a versão 2;
   - a janela durante a volta é a realidade aumentada (o app do jogo). Na volta lenta, a janela mostra a lista inteira;
   - os marcos vêm dos arquivos da pista, sem sessão de marcação.
3. **O que o rádio já mede** (pedido 45, `core/radio/analise.py`), por curva e contra uma volta de referência: o ponto de freada (freio acima de 0,15, corte de 15 m), a mínima (corte de 8 km/h), o traçado no ponto da mínima da referência (corte de 1,8 m), a volta ao acelerador cheio (0,95, corte de 10 m) e a velocidade no fim da curva (corte de 8 km/h), e as partes da perda (reta, freada, mínima e saída). A causa principal é a medida da parte que mais perdeu (`causa_da_curva`).
4. **O que não bate com o pedido** (registrado antes do código): o pedido cita seis causas, "as medidas do 45: freada cedo, freada leve, mínima baixa, acelerador tarde, marcha acima, traçado aberto". Duas delas não são medidas do rádio do 45:
   - **"freada leve"** (a força do freio) não é medida pelo rádio. Medida contra a volta do modelo, ela julgaria a amplitude do pedal da IA, o que o ADR 0032 (item 5) proíbe: "o formato dos pedais só é desenhado, nunca julgado";
   - **"marcha acima"** não é medida pelo rádio: a volta ao vivo (`VoltaAoVivo`) não guarda a marcha. Só a volta do modelo tem a marcha.

   As duas ficam **fora deste pedido** (ADR 0012: nada sem medida) e vão para a decisão do Eduardo (o relatório do pedido 52 e o backlog). As outras quatro são as do 45.

## Decisão

### 1. A lista da volta

- **Quando:** ao cruzar a linha, numa volta que conta para a análise do rádio (completa pela regra do coach, com as medidas, sem rodada, sem a IA, ADR 0027). As voltas que não contam (incompleta, com rodada, de saída ou de entrada nos boxes, com a IA) não põem nem tiram nada da lista: os trechos dela ficam sem medida.
- **Os trechos:** os 15 do ADR 0030 (14 curvas e o trecho da chegada), com os limites da tabela dele.
- **O tempo de um trecho:** o relógio da volta (o `elapsed` desde o s = 0) interpolado no fim menos no começo, como no ADR 0030. A perda é o tempo do trecho na volta menos o da referência do trecho (item 2).
- **O ruído de cada trecho:** o desvio padrão amostral dos tempos daquele trecho nas 7 voltas que contam do bloco 4 do pedido 50 (a L2, `trechos_s` de `docs/handoff/2026-11-12_50_linha-do-projeto_resultado.json`). É calculado e gravado num arquivo do projeto antes de o rádio ser ligado em qualquer sessão, e não muda depois.
- **Entra na lista** todo trecho com perda maior que o ruído do trecho, sem limite de quantidade.
- **A causa principal de cada trecho** é a do rádio do 45 (`causa_da_curva`, a medida da parte da perda que mais perdeu, acima do corte), medida contra a referência do trecho, e vira uma das quatro causas do engenheiro:

| a parte e a medida do 45 | a causa do engenheiro | a ação |
|---|---|---|
| freada: o ponto de freada antes da referência (≤ −15 m) | freada cedo | freie |
| freada: o ponto de freada depois da referência (≥ +15 m) | freada tarde | freie |
| mínima: a mínima abaixo da referência (≤ −8 km/h) | mínima baixa | vire |
| mínima: senão, o traçado no ápice (≥ 1,8 m) | traçado (por fora ou por dentro) | vire |
| saída: a volta ao acelerador cheio depois da referência (≥ +10 m) | acelerador tarde | acelere |

  - "freada tarde" não está entre as seis do pedido, mas é a mesma medida da "freada cedo" com o outro sinal, e a ação é a mesma ("freie" no ponto da referência);
  - na parte da saída, o 45 olha a velocidade no fim da curva; o engenheiro olha a volta ao acelerador cheio, que é a medida do 45 que diz a ação ("acelere"). Se ela não passar do corte, a saída fica sem causa;
  - **um trecho na lista sem causa acima do corte** (ou o trecho da chegada, que não tem curva) fica na lista só com a perda: aparece na lista inteira da janela (volta lenta), sem frase de ação, sem voz e sem marca.
- **Uma dica não aplicada continua na lista até ser aplicada** (item 8). Na linha, primeiro se confere a dica de cada trecho da lista; depois, a volta nova põe os trechos dela (um trecho que volta à lista ganha a causa nova); por fim, saem da lista os trechos com a dica aplicada que a volta nova não pôs de volta. Uma volta que não conta não confere nada.
- **A lista vale de uma linha à seguinte.** Um aviso cujo `s_fala` cai antes da linha (a C01, cujo aviso começa na reta dos boxes) usa a lista em vigor naquele ponto.

### 2. A referência de cada trecho e os pontos

- **A referência do trecho** é a volta do modelo. Se a melhor passagem do piloto pelo trecho for mais rápida que a da volta do modelo, a referência daquele trecho é a volta dessa passagem. **A melhor passagem** é o menor tempo do trecho entre a "Sua melhor volta" (ADR 0032, do store) e as voltas que contaram na sessão, antes da volta medida.
- **Sem a volta do modelo** para a pista e o carro, o engenheiro fica calado (a janela diz "A volta de referência desta pista ainda não foi gerada pelo modelo").
- **Os pontos de cada trecho,** na referência do trecho:
  - **a freada:** onde o freio passa de 0,15, do ápice anterior ao ápice (`ml.comparison.evolution.braking_point`, a regra do relatório de evolução e do 45). Sem freada, o trecho não tem ponto de freada;
  - **a entrada:** o início da curva (`pontos_de_linha_s.entrada`, ADR 0030);
  - **a retomada:** o primeiro ponto do trecho a partir do qual o acelerador fica em 0,90 ou mais até o fim do trecho (ADR 0030, item 5). Sem isso, o trecho não tem retomada.
- **O ponto da ação:** freie, a freada; vire, a entrada; acelere, a retomada.

### 3. Os marcos

A tabela da Parte B do pedido 52, lida dos arquivos da pista (só leitura), com o tipo, o `s` na geometria oficial, o lado (pelo vetor normal da geometria, positivo à esquerda, ADR 0003) e, nas placas de freada, o valor. Os tipos: placa de freada (50, 100 ou 200), placa do DRS, passarela, pórtico da largada, posto de bandeira e zebra (começo e fim, com o lado). A tabela fica num arquivo ao lado dos outros da pista, com o sha256 dos kn5 lidos e o `geometry_id`.

### 4. A frase

**A ação, pela causa:** freada cedo ou tarde: "freie"; mínima baixa ou traçado: "vire"; acelerador tarde: "acelere".

**O ponto, pelo marco de menor custo:**
- **a janela:** para frear, o marco serve se estiver até 150 m antes do ponto ou até 60 m depois; para virar e acelerar, até 80 m antes ou 40 m depois. Todos os tipos de marco servem para as três ações;
- **o custo:** com `d` = o `s` do ponto menos o `s` do marco, em metros (na volta, pelo caminho mais curto), o custo é `d` quando o marco vem antes (`d ≥ 0`) e `1,5 × |d|` quando vem depois;
- **o bônus:** uma placa de freada vale 15 m a menos para frear; o começo ou o fim de uma zebra, 10 m a menos para virar e para acelerar;
- **o empate:** o marco de menor `s`;
- **o texto:** com `|d| < 5 m`, "freie na placa de 100"; senão, `|d|` arredondado a 5 m (meio para cima): "freie 10 metros depois da placa de 100", "vire 15 metros antes do começo da zebra à direita". Os nomes: "placa de 50/100/200", "placa do DRS", "passarela", "pórtico da largada", "posto de bandeira à direita/à esquerda", "começo/fim da zebra à direita/à esquerda" (zebras e postos levam o lado);
- **o molde da voz:** "Curva N: <frase>." ("Curva 1: freie 10 metros depois da placa de 100.");
- **sem marco na janela:** a frase fica só na janela, "Curva N: <ação> no ponto marcado", com a marca desenhada (item 7), e sem voz.

### 5. A voz

- **O aviso:** só nos trechos da lista em que a referência do trecho freia e que têm frase com marco. A voz diz a frase do trecho (freie, vire ou acelere).
- **Onde começa:** `s_fala = s_freada − v × (t_frase + 1,0 s)`, com `v` a velocidade da referência do trecho na freada e `t_frase` a duração da fala gerada pela voz do projeto (Microsoft Daniel a 1,4x). Assim, a fala acaba pelo menos 1,0 s antes da freada na velocidade da referência.
- **Na hora:** a fala sai quando o carro passa o `s_fala`, se o tempo até a freada, na velocidade do carro, for pelo menos `t_frase + 1,0 s`. Senão, o aviso daquela volta fica só na janela.
- **Os blocos de voz:** na volta do modelo, cada bloco vai da retomada do trecho anterior até 1,0 s (no relógio da volta do modelo) antes da primeira ação do trecho (a freada ou a entrada, a que vier antes). O trecho da chegada não tem ação: o bloco da reta dos boxes vai da retomada da C14 até a primeira ação da C01. Um trecho anterior sem retomada não abre bloco.
- **O aviso cabe no bloco** quando o `s_fala` fica dentro do bloco que termina na freada dele. O trecho sem bloco que caiba a frase fica só na janela.
- **A reserva:** em cada bloco, do primeiro `s_fala` dos avisos da lista em vigor até o fim do bloco.
- **O feedback nas retas:** a frase do coach, o resumo e a análise (ADR 0027) saem no começo de um bloco, na variante mais completa que caiba antes da reserva (e dentro do limite do tipo: 7,3, 8,0 e 8,8 s), na velocidade do carro. Se nenhuma couber, a mensagem espera o bloco seguinte. As variantes, os limites e a ordem do corte não mudam.
- **A prioridade:** o aviso nunca é cortado nem adiado pelo feedback.
- **Nunca** dentro de uma curva, nunca por cima de outra fala, nunca na volta de saída dos boxes nem nas voltas da IA.

### 6. A realidade aumentada

Uma janela nova no app do jogo, "Engenheiro", ligada e desligada na barra de apps como as outras quatro:
- **na volta rápida:** a frase de cada trecho da lista (os de voz e os sem voz), de `s_fala` até o ponto da ação. Para os sem voz, `s_fala` usa a mesma conta, com a velocidade da referência no ponto da ação. Depois da linha, por alguns segundos, só o sinal da conferência por trecho ("C01 aplicada", "C04 não");
- **na volta lenta:** a lista inteira, com a frase, a perda e a conferência com os valores ("C01: freou a 98 m do marco, dito 100"). **A volta lenta:** a diferença ao vivo para a melhor volta da sessão de 5,0 s ou mais naquele ponto, ou a volta de saída ou de entrada nos boxes, ou uma volta que já teve uma rodada ou ficou incompleta.

### 7. A marca na pista

- **Se a API do CSP instalada tiver o que é preciso** (`render.on` com o evento da pista transparente, `render.quad` e `physics.raycastTrack`, conferidos no `lib.lua` do SDK), a marca do ponto da ação é desenhada no asfalto, em 3D, na cor do fantasma: uma faixa de 1,5 m de comprimento atravessando a linha da referência (6 m de largura, centrada nela), de `s_fala` até o carro passar o ponto, nos trechos da lista.
- **Senão,** a janela mostra a contagem 3-2-1 até o ponto, pelo tempo até ele (a distância dividida pela velocidade do carro).
- **O ADR 0021 ganha uma linha:** o app do jogo passa a desenhar na pista, só a marca do engenheiro.

### 8. A conferência da dica

Na volta seguinte à dica, com a volta medida:
- **freie:** aplicada se o ponto de freada (freio acima de 0,15, a mesma regra) ficou a até 10 m do ponto dito;
- **vire:** aplicada se a mínima do trecho ficou a até 5 km/h da mínima da referência do trecho;
- **acelere:** aplicada se a retomada (ADR 0030) ficou a até 10 m do ponto dito.

**O ponto dito** é o do texto: o `s` do marco mais os metros ditos (ou o próprio marco, "na placa de 100"); sem marco, o ponto da ação. Um trecho sem a medida na volta (por exemplo, sem freada) fica "sem medida" e a dica continua. **O trecho sem causa** (item 1) não tem dica e não é conferido.

### 9. A acurácia da volta

"2 de 3 avisos aplicados": as dicas conferidas na volta e quantas foram aplicadas. Na janela, depois da linha; no resumo, só na variante mais completa da fala (é o primeiro item a sair no corte), e sempre no cartão.

### 10. O registro

Em `<pasta de dados>/data/radio/<sessão>.engenheiro.jsonl`, uma linha por aviso planejado (a volta, o trecho, a causa, a frase, o `s_fala`, "voz" ou "janela", e depois se foi entregue e se foi aplicado) e uma linha por volta que conta (a perda em cada um dos 15 trechos e a conferência), de onde sai a perda do trecho avisado nas voltas seguintes. É a entrada do protocolo de avaliação e da tela Volta (pedido 53).

### 11. O que o engenheiro nunca diz

Nada sem medida (ADR 0012); nenhum conselho de setup; a volta da IA do jogo nunca é referência (ADR 0032); nenhuma frase sobre a força do freio ou a marcha até uma decisão própria (contexto, item 4).

## Consequências

- O rádio passa a usar os blocos de voz no lugar das janelas geométricas do pedido 31 quando o engenheiro está ligado. As frases do coach e as análises podem esperar mais: no miolo (da C07 à C13), pela conta do Cowork, nenhum bloco passa de 1,5 s.
- O app do jogo ganha a quinta janela e desenha na pista (a exceção do ADR 0020 continua do mesmo tamanho: só a pasta do app, só pelos scripts).
- Os marcos e o ruído por trecho são arquivos derivados, fora do git, que o instalador leva pelo mesmo filtro do `extraResources`.
- O engenheiro pode ser desligado no backend (`AT_ENGENHEIRO=desligado`); com ele desligado, o rádio volta a ser o do pedido 51.

## Decisões do Eduardo de 16/11

Emenda depois do relatório da parada na Parte E (o pedido 52, "Atualização de 16/11"). O texto acima fica como estava; onde ele e esta seção divergem, vale esta seção. Registrada antes de mudar o código.

1. **O feedback espera a reta longa com a causa** (muda o item 5, "o feedback nas retas"):
   - **a variante com a causa** é a fala que diz uma das causas medidas do rádio do 45 (a freada, a mínima, o traçado, a saída ou o acelerador: "freou", "mínima", "passou", "saiu" ou "acelerou"). **A variante alvo** de uma mensagem é a mais completa com a causa entre as que cabem no limite do tipo (7,3, 8,0 e 8,8 s);
   - a frase do coach, o resumo e a análise (e a curva da volta que não coube no resumo) saem no começo do bloco em que a variante alvo cabe antes da reserva dos avisos, na velocidade do carro;
   - **as retas longas** são os blocos de voz que duram pelo menos o maior limite do feedback (8,8 s) na volta do modelo: a reta dos boxes (10,9 s) e a reta oposta (9,1 s);
   - **a primeira reta longa depois de a mensagem nascer** é a primeira em que o carro entra depois disso (a reta em que a mensagem nasce não conta). Se a variante alvo não couber nem nela, sai nessa reta a variante mais completa que couber, como o rádio do 45 fazia. A mensagem nunca espera mais do que até essa reta: dali em diante, sai no primeiro bloco em que alguma variante caiba antes da reserva;
   - uma mensagem sem nenhuma variante com a causa segue a regra do item 5 (a mais completa que caiba, no primeiro bloco em que caiba);
   - os limites (7,3, 8,0 e 8,8 s) e a ordem do corte não mudam. O aviso de freada continua com a prioridade: nunca é cortado nem adiado pelo feedback, e o feedback nunca passa da reserva.
2. **O molde curto do aviso** (muda o item 4, "o molde da voz"): a voz diz só a frase, sem "Curva N:" e sem a vinheta: "Freie 10 metros depois da placa de 100.". O cartão do rádio e a janela do jogo continuam escrevendo "Curva N: <frase>". O `t_frase` do `s_fala` é a duração dessa fala curta, medida com a voz do projeto.
3. **"Sem tirar o pé"** (muda o item 4, "a ação"): num trecho com curva em que a referência do trecho não freia nem alivia (o acelerador fica em 0,90 ou mais do começo ao fim do trecho), a frase de qualquer causa é "sem tirar o pé", sem marco e sem metros. Vale para todo trecho nessa condição, e não só para a C13. Por ser um trecho em que a referência não freia, a frase fica só na janela (item 5), de `s_fala` até o início da curva (`pontos_de_linha_s.entrada`), sem a marca no asfalto e sem a contagem 3-2-1. **A conferência** (item 8): aplicada se, na volta, o acelerador ficou em 0,90 ou mais do começo ao fim do trecho.
4. **A freada só depois da saída do trecho anterior** (muda o item 2, "a freada"): a busca do ponto de freada de cada trecho começa na saída do trecho anterior (`pontos_de_linha_s.saida`; antes da C01, o fim do trecho da chegada, que é a linha) e vai até o ápice do trecho, e não mais do ápice anterior. Vale para todos os trechos e para tudo o que o engenheiro mede com ela: o ponto de freada da referência, os blocos de voz, a medida "freada cedo ou tarde" da causa do engenheiro e a conferência do "freie". O feedback do rádio (as medidas do 45 nas frases do coach, no resumo e na análise) continua com a regra dele.
5. **A C02 e a C08 ficam como estão:** a referência freia já mudando de direção, e "freie no começo da zebra" está certa.
6. **"Freada leve" e "marcha acima" ficam para uma versão futura** (o contexto, item 4, continua valendo): o coach deve ler a pressão aplicada no freio e a marcha usada na curva. Vão para o backlog: a volta ao vivo guardar a marcha e a força do freio; e a força do freio comparada com a melhor passagem do piloto, nunca com o pedal da volta do modelo (ADR 0032, item 5).
7. **A conferência fora do tempo real (a D.1) é refeita** nas 4 sessões com as decisões 1 a 4, antes do teste no jogo.
8. **A marca no asfalto fica como está** (item 7) para o teste no jogo; o Eduardo diz no jogo se ela aparece a tempo.
9. **"Frenagem", e não "freada"** (16/11, 14h20, depois do relatório da atualização): no que o piloto ouve e lê, o substantivo é "frenagem", o termo dos pilotos no Brasil ("ponto de frenagem"). As causas do engenheiro passam a "frenagem cedo" e "frenagem tarde"; o cartão do rádio, "na frenagem" e "frenagem 15 m antes"; o app do jogo, "frenagem da referência"; as telas, "Início da frenagem" e "Frenagem emendada". O verbo fica ("Freie", "Freou"). As chaves internas (`freada`, `freadaM`) e o texto técnico da documentação não mudam.
10. **A pisada em andamento na saída do trecho anterior** (16/11, depois do relatório da atualização; muda o item 4 desta seção): se o freio já estiver apertado (0,15 ou mais) na saída do trecho anterior, a frenagem do trecho é onde essa pisada começou, mesmo antes da saída. Senão, vale o item 4. Na volta do modelo, só a C10 está nesse caso: a frenagem dela começa em 2.622 m, 4 m antes da saída da C09 (2.626 m), e não na segunda pisada (2.680 m). A C09 continua sem frenagem.

## Decisões do Eduardo de 20/11

Emenda depois do teste no jogo de 20/11 e da leitura E.3 (o pedido 52, "Atualização de 20/11"). O texto acima fica como estava; onde ele e esta seção divergem, vale esta seção. Registrada antes de mudar o código. Os números da E.3 são o motivo das decisões; nenhuma regra abaixo muda depois de ver os números da D.1 nova. **Tudo vale para qualquer pista e qualquer trecho**; Interlagos é só o exemplo.

**A escolha:** a opção H da E.3 (juntar o aviso com o da curva anterior, com a fala curta), mais o bipe (G) e a janela com as duas próximas dicas, com uma folga mínima de 3,0 s.

### As correções (valem para todo aviso)

1. **O aviso nunca espera na fila do app do jogo.**
   - Quando o aviso chega, o cartão que estiver na tela sai, e uma fala de feedback em andamento é cortada.
   - O corte vai para o registro do engenheiro (uma linha "corte": a mensagem cortada, a fala do aviso e onde).
   - O feedback cortado não volta a tocar na mesma reta: ele volta à fila e só pode sair numa reta longa seguinte. Lá vale a decisão 1 de 16/11: a variante com a causa, se couber; senão, a mais completa que couber.
2. **O aviso é disparado no próprio jogo, pelo `s` do carro, com o áudio já baixado** (a opção B).
   - O backend manda ao app do jogo (`GET /api/radio/engenheiro`) a lista das falas planejadas, cada uma com o `s_fala`, o texto, a duração e o endereço do áudio.
   - O app baixa os áudios antes, e toca cada fala no quadro em que o carro passa o `s_fala`, sem esperar a rede. Sem o arquivo baixado, toca pelo endereço.
   - O backend não entrega mais o aviso pela fila de mensagens do rádio: quem fala é o app do jogo. O backend registra e acompanha a fala pelo mesmo `s`, para a reserva e o corte.
   - **A latência do disparo no jogo** entra nas contas como 0,1 s: é uma estimativa, a ser medida no teste. O app do jogo registra no log o `s` do disparo e o do começo do som.
3. **A reserva de fala usa o tempo da volta do item 5 até o ponto,** e não a velocidade do momento: o tempo que o carro leva de um `s` a outro vem do perfil de tempo daquela volta.

### As regras novas do aviso

4. **Todo aviso pode ir para a voz:** "freie", "vire", "acelere" e "sem tirar o pé". A regra "a voz só onde a referência freia" (item 5) sai. A janela e o cartão continuam para todos os avisos.
5. **O aviso é calculado contra a ação do piloto, e não contra a da referência.**
   - **A ação do piloto num trecho** é buscada desde a saída do trecho anterior (a emenda de 16/11, item 4) até o ápice:
     - para "freie", a frenagem (freio de 0,15 ou mais; uma pisada em andamento na saída conta desde o começo, item 10 de 16/11). Sem frenagem, vale a regra do "vire";
     - para "vire", a primeira frenagem ou o primeiro alívio (acelerador abaixo de 0,90); sem nenhum dos dois, a entrada da curva (`pontos_de_linha_s.entrada`);
     - para "sem tirar o pé", a entrada da curva;
     - para "acelere", o ponto em que ele volta ao acelerador: a retomada do trecho (ADR 0030, item 5). Sem ela, o primeiro ponto com o acelerador em 0,90 ou mais depois do ápice, até o fim do trecho. Sem nenhum dos dois, o aviso fica só na janela e no bipe.
   - **De qual volta (o perfil):**
     - a última volta da sessão que conta (completa pela regra do coach, sem rodada e sem a IA);
     - antes de haver uma, a "Sua melhor volta" guardada da pista;
     - sem ela, a volta de referência (a volta do modelo).
   - **Depois de cada volta que conta,** o backend refaz o plano das falas (os `s_fala`) e manda a lista nova ao app do jogo.
   - **O pedaço livre que atravessa a linha de chegada** usa a volta anterior: o perfil é tratado como um laço, e o fim da volta emenda no começo dela.
6. **A folga mínima: 3,0 s.**
   - A fala acaba pelo menos 3,0 s antes do mais cedo destes dois pontos: a ação esperada do piloto (item 5) e o ponto dito no aviso.
   - "Mais cedo" é no tempo do perfil, andando para a frente desde o pedaço livre.
   - A conta inclui a latência do item 2: o disparo, mais 0,1 s, mais a duração da fala, acaba até 3,0 s antes do ponto.
7. **Onde a fala acontece (a opção H):**
   - **O pedaço livre,** no perfil: um trecho contínuo com o acelerador em 0,90 ou mais e o freio abaixo de 0,15.
     - Ele vai de quando a ação anterior acaba até a ação seguinte.
     - Se o ponto do item 6 cair dentro de um pedaço livre, o pedaço acaba nele.
   - **Os dois candidatos de cada aviso:** o pedaço livre que acaba mais perto antes do ponto do item 6 e o seguinte para trás. Nunca um pedaço mais antigo que esses dois.
   - **A fala começa e acaba dentro do pedaço livre:** nunca dentro de uma curva nem durante outra ação, e nunca por cima de outro aviso. Entre duas falas do mesmo pedaço há pelo menos 0,3 s.
   - **A escolha do pedaço:**
     1. Cada aviso vai para o primeiro candidato em que a fala dele sozinha cabe com a folga do item 6; senão, para o segundo.
     2. Num mesmo pedaço, os avisos são postos em pares na ordem da pista (o 1º com o 2º, o 3º com o 4º), e cada par vira uma fala só, com o número da curva por extenso ("Seis: vire na zebra. Sete: freie na zebra."). No máximo dois avisos por fala; um aviso sozinho continua sem o número (16/11, item 2).
     3. As falas do pedaço são postas de trás para a frente, cada uma o mais tarde possível que respeite a folga de todos os avisos dela e não encoste na fala seguinte.
     4. Uma fala que não couber (o pedaço ficou cheio) manda os seus avisos para o segundo candidato, e o plano é refeito. Um aviso que não couber em nenhum dos dois fica só na janela e no bipe, com o motivo no registro.
   - **A duração de cada fala** é a da voz do projeto, medida ao gerar o áudio. Até lá, entra uma estimativa: a soma das falas sozinhas mais 0,8 s num par. O plano é refeito quando a duração real chega.
8. **O molde da fala é um parâmetro com três variantes** (`AT_ENGENHEIRO_MOLDE`: `a`, `b` ou `c`):
   - **(a)** o molde curto de 16/11: "Freie 10 metros depois da placa de 100.";
   - **(b)** o verbo, a distância e o marco, sem "metros" e sem "placa": "Freie 10 depois do 100." ("dez depois do cem");
   - **(c)** o verbo e o marco, com a correção no fim: "Freie no 100, mais 10." ("no cem, mais dez").
   - **Nas três:**
     - só as placas perdem "placa de"; os outros marcos guardam o nome e o lado ("Vire 5 depois do começo da zebra à direita.");
     - "Sem tirar o pé." e "no ponto marcado" não mudam;
     - a velocidade da voz não muda.
   - **O padrão é (a) até a escolha do Eduardo,** que ele faz ouvindo, antes do teste no jogo. A escolha entra neste ADR como a decisão de 20/11 sobre o molde.
   - **A janela e o cartão** continuam escrevendo "Curva N: <frase>" no molde (a), que é o mais completo para ler.
9. **O bipe (a opção G):**
   - **O som:** um bipe curto (0,25 s), gerado pelo código (um tom só, de 2.000 Hz, diferente da vinheta e de qualquer som do rádio). Ele é instalado junto com o app do jogo (`bipe.wav`), e o app toca o bipe pelo `s` do carro num player próprio, que não corta a fala.
   - **O ponto:** o ponto dito no aviso, o mesmo da marca na pista (a marca passa a ser desenhada no ponto dito). Ele é antecipado do tempo de reação: o bipe soa quando o tempo até o ponto, na velocidade do carro, fica menor ou igual ao tempo de reação.
   - **O que o bipe marca:** o ponto dito, e não a ação de costume do piloto. É ele que corrige a ação.
   - **O tempo de reação** é um parâmetro (`TEMPO_DE_REACAO_AO_BIPE_S`). **Não confirmado:**
     - nenhuma fonte achada dá um valor para um sinal sonoro esperado ao volante;
     - Green (2000, "How Long Does It Take to Stop?", *Transportation Human Factors* 2(3)) dá cerca de 0,70 a 0,75 s para uma frenagem totalmente esperada, mas só foi lido por resumos (o apêndice da FHWA, publicação 06-033), e para um sinal visual;
     - um estudo antigo dá 0,51 s depois de uma buzina (citado num artigo da Indiana Academy of Science, sem a data e a amostra claras).
     
     Por isso, o valor inicial é 0 s: o bipe soa no ponto.
   - **Quais avisos:** "freie", "vire" e "acelere". "Sem tirar o pé" não tem bipe, porque não há ação para marcar.
   - **A chave:** `AT_ENGENHEIRO_BIPE=desligado` desliga o bipe, como o `AT_ENGENHEIRO`. O padrão é ligado.
   - **O bipe é a única exceção ao "nunca dentro de uma curva"** (item 5): ele não é uma fala.
10. **A janela mostra sempre os dois próximos avisos:**
    - cada um aparece desde o fim da ação anterior a ele, que é o começo do pedaço livre logo antes da ação do piloto, e não mais desde o `s_fala`;
    - o da vez fica em destaque e sai depois da ação: o mais tarde entre a ação do piloto e o ponto dito, mais 20 m;
    - os textos continuam com "Curva N:".
11. **O feedback continua como na decisão 1 de 16/11.** A reserva das retas longas é feita primeiro para os avisos, agora de todos os tipos: a reserva de um bloco começa no `s_fala` da primeira fala planejada à frente do carro dentro dele. O feedback usa o que sobrar, medido pelo tempo do perfil (item 3).

**O app do jogo** sobe para a 0.8.0.
