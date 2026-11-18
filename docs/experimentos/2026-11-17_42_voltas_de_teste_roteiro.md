# Voltas de teste com comportamento provocado: o roteiro (pedido 42, Parte F.1)

Registrado em 17/11/2026, **antes de qualquer sessão de teste**, junto com o que se espera de cada comportamento. Nenhum limiar muda por causa do teste. Se um detector falhar, o relatório diz como e propõe uma emenda para uma rodada 3, registrada antes de rodar.

**Os arquivos:**

- este roteiro;
- `2026-11-17_42_voltas_de_teste_folha.html`: a folha para imprimir, volta a volta;
- `2026-11-17_42_voltas_de_teste_marcacao.csv`: o CSV em que você marca, depois de cada volta, "consegui", "nao consegui" ou "nao sei";
- `2026-11-17_42_voltas_de_teste_esperado.json`: o que se espera, legível pelo código da Parte F.2.

## 1. Os comportamentos

Todos os detectores do catálogo (F1 a F8, E1 a E6, M1 a M9 e V1 a V5) que dá para provocar de propósito, com o carro, o setup e as ajudas de sempre. **As curvas foram escolhidas pela física de cada uma, e não pelos números da rodada 2:**

- as frenagens fortes depois de reta longa: C01, a primeira perna do S do Senna, e C04;
- as lentas e médias com frenagem, boas para a entrada e para a forma da curva: C06, C09, C10 e C12;
- as saídas lentas em marcha baixa, boas para o acelerador: C08 e C12;
- as médias sem frenagem, boas para a velocidade no meio: C03 e C11.

A C14 (rápida, antes da reta dos boxes) e a C13 ficam fora de propósito: uma provocação ali põe o carro no muro em alta velocidade.

**Em cada comportamento:**

- **o "aplica" provocado:** 3 passagens, alternando as duas curvas;
- **o "não aplica" de controle:** as passagens normais nas mesmas curvas, das voltas normais entre os blocos. São 6 na sessão 1 e 5 na sessão 2, todas nas mesmas curvas.

**As colunas da tabela:**

- **"devem dizer aplica" e "devem dizer não aplica":** o estado esperado nas passagens provocadas;
- **"não devem mudar":** detectores de outra família, cujo estado nas provocadas deve ficar igual ao dos controles.

| id | comportamento | detectores | curvas | o que você faz | devem dizer "aplica" | devem dizer "não aplica" | não devem mudar | estilo e notas |
|---|---|---|---|---|---|---|---|---|
| P01 | Frear antes | F1 | C01, C04 | Na curva, comece a frear uma placa antes (uns 30 m) do seu ponto de sempre, com a mesma força. | — | F1 | F4, F5, E4, E5, M7, M8 | — |
| P02 | Pico do freio lento | F2, F3 | C06, C10 | Na curva, aperte o freio devagar, levando quase 1 s para chegar ao máximo. | — | F2, F3 | F1, E5, M7, M8 | perfil de frenagem: o pico mais tarde |
| P03 | Soltura em degrau | F4, V3 | C01, C10 | Na curva, no fim da frenagem, solte o freio de uma vez, antes de virar. | V3 | F4, F5 | F1, F2, M8 | perfil de frenagem: a soltura mais rápida |
| P04 | Trail braking | F5 | C04, C12 | Na curva, continue com um pouco de freio enquanto começa a virar e vá soltando aos poucos até perto do ápice. | F5, F4 | — | F1, F2, M8 | — |
| P05 | Pé esquerdo | F7 | C06, C09 | Na curva, freie com o pé esquerdo e mantenha um pouco de acelerador junto por meio segundo. | F7 | — | F1, E5, M7 | uso dos pedais: F7 maior |
| P06 | Virar cedo | E1 | C06, C12 | Na curva, comece a virar uns 15 m antes do seu ponto de sempre. | E1 | — | F2, F4, F7, M8 | aplicação do volante; o M2 pode ir junto (ápice antecipado) |
| P07 | Volante em zigue-zague | E5, E6 | C09, C11 | No meio da curva, faça 3 ou 4 correções pequenas no volante, para lá e para cá. | E5 | E6 | F1, F4, M8 | aplicação do volante: mais reversões |
| P08 | Curva devagar | M1 | C03, C11 | Faça a curva uns 20 km/h abaixo do normal, tirando o pé um pouco antes. | — | M1 | F4, F7, E5 | — |
| P09 | Ápice cedo | M2 | C06, C10 | Na curva, mire o ápice cedo: chegue ao miolo antes e saia aberto. | M2 | — | F2, F4, F7 | o E1 pode ir junto |
| P10 | Curva em V | M3 | C06, C12 | Na curva, freie mais fundo, vire rápido no ponto mais lento e acelere cedo: a curva em V. | — | M3 | F1, F7, E5 | forma V ou U: mais V |
| P11 | Curva em U | M3 | C04, C09 | Na curva, entre mais rápido e segure a velocidade mínima por mais tempo, com o volante parado: a curva em U. | M3 | — | F7, E5, M8 | forma V ou U: mais U |
| P12 | Saída fechada | M4 | C04, C12 | Na saída da curva, fique perto do meio da pista, sem abrir até a zebra de fora. | — | M4 | F1, F4, F5, E5 | — |
| P13 | Sem pedal | M5 | C06, C10 | Na curva, depois de soltar o freio, fique cerca de 1 s sem freio e sem acelerador antes de acelerar. | M5 | M6 | F1, F2, E5 | — |
| P14 | Retomada tarde | M6 | C10, C12 | Na curva, espere 1 s a mais depois do ponto mais lento antes de acelerar. | — | M6 | F1, F4, E5 | perfil do acelerador: do ápice ao pleno mais longo |
| P15 | Acelerar cedo e abrir o volante | M7 | C06, C10 | Na curva, acelere antes do ápice e, quando a frente abrir, aumente o volante para segurar a linha. | M7 | M6 | F1, F4 | — |
| P16 | Alívio na saída | M8 | C08, C12 | Na saída da curva, acelere até a metade, tire o pé e acelere de novo. | M8 | M6 | F1, F4, E5 | perfil do acelerador |
| P17 | Meio pedal e troca cedo | V1, V2 | volta | Nesta volta inteira, use meio acelerador nas saídas e troque de marcha uns 1.000 rpm antes do normal. | — | V1, V2 | F1, F4, E5 | — |
| P18 | Entrar rápido demais | E2 | C09, C12 | Entre na curva uns 10 km/h mais rápido que o normal e segure a linha com mais volante. | E2 | — | F4, F7 | resposta na entrada: menos guinada por volante |
| P19 | Redução brusca | F8 | C01, C10 | Na curva, reduza duas marchas de uma vez, cedo, ainda em alta. | F8 | — | F4, F7 | o E3 pode ir junto |
| P20 | Travar a roda | F6 | C01, C04 | Na curva, pise o freio com força total e de uma vez, em linha reta. | F6 | — | E5, M8 | pode não travar, se o carro tiver ABS |
| P21 | Sobresterço de potência | E3, E4, M9 | C08, C12 | Na saída da curva, acelere de uma vez até o fim, em marcha baixa. | M9, E3, E4 | — | F1, F4 | o último bloco: pode rodar |

**Os que não dá para provocar:**

- **V4, pneus na faixa da IA:** a temperatura do pneu acompanha o ritmo de várias voltas e não muda numa passagem. Provocar exigiria estragar o resto da sessão;
- **V5, consistência:** mede o desvio de 5 voltas ou mais por sessão e curva. Uma sessão de provocações é inconsistente por construção e não testa o detector.

O F6 (travar a roda) entra como tentativa: se o carro tiver ABS, a roda pode não travar. Nesse caso, a passagem é marcada "nao consegui", e não conta contra o detector.

## 2. A sessão

- **A pista: a cópia, `vhe_interlagos_teste_m1`.** No Content Manager, escolha "Interlagos [teste]", com o preset de sempre (o carro, o setup e as ajudas de sempre). É a decisão do Eduardo de 18/11, e a conferência está na seção 3.
  - A cópia tem a mesma geometria da original (`geometry_id` `0ed16f0dd2225990`, ADR 0032, item 2).
  - Conferi em 18/11, na pasta do jogo, os mesmos arquivos de superfície: o `vhe_interlagos.kn5` (`ce1f3bb2…`) e o `gp/data/surfaces.ini` (`4520b16b…`) são iguais nas duas pastas.
  - As curvas, as fases e os números C01 a C14 são os mesmos.
- **As voltas:**
  - no máximo dois comportamentos por volta, em curvas a pelo menos 3 curvas de distância uma da outra;
  - uma volta normal depois de cada bloco de 3 voltas.
- **A ordem:** o sobresterço, a redução brusca, a roda travada e a entrada rápida demais ficam na sessão 2, e as rodadas possíveis (P21) no último bloco, para não estragar o resto.
- **O tamanho:** 2 sessões, com 25 e 21 voltas. Cerca de 37 e 31 minutos a 1:30 por volta, dentro dos 40 minutos.
- **A folha:** a página HTML imprime uma tabela por sessão.
- **Depois de cada volta,** marque no CSV "consegui", "nao consegui" ou "nao sei" em cada comportamento da volta. Nas voltas normais, marque "consegui" se a volta foi normal mesmo.

**O plano, volta a volta** (o id é o da tabela acima):

| sessão | volta | bloco | o que fazer |
|---|---|---|---|
| 1 | 1 | saída dos boxes | saída dos boxes |
| 1 | 2 | bloco 1 | P01 na C01; P16 na C08 |
| 1 | 3 | bloco 1 | P01 na C04; P16 na C12 |
| 1 | 4 | bloco 1 | P01 na C01; P16 na C08 |
| 1 | 5 | volta normal (controle) | volta normal (controle) |
| 1 | 6 | bloco 2 | P02 na C06; P12 na C12 |
| 1 | 7 | bloco 2 | P02 na C06; P12 na C12 |
| 1 | 8 | bloco 2 | P02 na C06; P12 na C12 |
| 1 | 9 | volta normal (controle) | volta normal (controle) |
| 1 | 10 | bloco 3 | P03 na C01; P07 na C09 |
| 1 | 11 | bloco 3 | P03 na C01; P07 na C11 |
| 1 | 12 | bloco 3 | P03 na C01; P07 na C09 |
| 1 | 13 | volta normal (controle) | volta normal (controle) |
| 1 | 14 | bloco 4 | P04 na C04; P13 na C10 |
| 1 | 15 | bloco 4 | P04 na C04; P13 na C10 |
| 1 | 16 | bloco 4 | P04 na C04; P13 na C10 |
| 1 | 17 | volta normal (controle) | volta normal (controle) |
| 1 | 18 | bloco 5 | P05 na C06; P14 na C10 |
| 1 | 19 | bloco 5 | P05 na C09; P14 na C12 |
| 1 | 20 | bloco 5 | P05 na C06; P14 na C10 |
| 1 | 21 | volta normal (controle) | volta normal (controle) |
| 1 | 22 | bloco 6 | P06 na C06; P08 na C03 |
| 1 | 23 | bloco 6 | P06 na C06; P08 na C11 |
| 1 | 24 | bloco 6 | P06 na C06; P08 na C03 |
| 1 | 25 | volta normal (controle) | volta normal (controle) |
| 2 | 1 | saída dos boxes | saída dos boxes |
| 2 | 2 | bloco 1 | P09 na C10; P11 na C04 |
| 2 | 3 | bloco 1 | P09 na C10; P11 na C04 |
| 2 | 4 | bloco 1 | P09 na C10; P11 na C04 |
| 2 | 5 | volta normal (controle) | volta normal (controle) |
| 2 | 6 | bloco 2 | P10 na C12; P15 na C06 |
| 2 | 7 | bloco 2 | P10 na C12; P15 na C06 |
| 2 | 8 | bloco 2 | P10 na C12; P15 na C06 |
| 2 | 9 | volta normal (controle) | volta normal (controle) |
| 2 | 10 | bloco 3 | P17 na volta inteira |
| 2 | 11 | bloco 3 | P17 na volta inteira |
| 2 | 12 | bloco 3 | P17 na volta inteira |
| 2 | 13 | volta normal (controle) | volta normal (controle) |
| 2 | 14 | bloco 4 | P18 na C09; P19 na C01 |
| 2 | 15 | bloco 4 | P18 na C12; P19 na C01 |
| 2 | 16 | bloco 4 | P18 na C09; P19 na C01 |
| 2 | 17 | volta normal (controle) | volta normal (controle) |
| 2 | 18 | bloco 5 | P20 na C01; P21 na C08 |
| 2 | 19 | bloco 5 | P20 na C04; P21 na C12 |
| 2 | 20 | bloco 5 | P20 na C01; P21 na C08 |
| 2 | 21 | volta normal (controle) | volta normal (controle) |

## 3. As sessões de teste fora de tudo o que mede a evolução (item 4)

**A decisão do Eduardo (18/11):**

- as sessões de teste são gravadas na cópia da pista;
- nenhum código fora do Modelo 2 muda por causa disso;
- se algum ponto da conferência abaixo falhasse, este pedido parava.

**A proposta de 17/11** (uma coluna `finalidade` na anotação de sessão) ficou sem efeito.

**A conferência (18/11, pelo código de `develop` e da branch do pedido 52, sem rodar nada no jogo).** Uma sessão minha na cópia fica fora de:

| o quê | por quê | fica fora? |
|---|---|---|
| o store v2 | o construtor lista as gravações com `list_all_sessions()`, que deixa as pistas de teste (`config.TEST_TRACK_NAMES`) sempre fora, salvo pedindo (`incluir_pistas_de_teste=True`) | sim |
| o coach: as duas referências e a seleção das minhas voltas | o `atualizar_coach` e o construtor do modelo (`tools/train_reference_model.py`) usam o mesmo `list_all_sessions()` e o inventário (`build_inventory`, idem). A volta do modelo vem do arquivo próprio dela (`vhe_interlagos`) | sim |
| a "Sua melhor volta" | é a `minha_melhor` do modelo do coach, feita pelo mesmo construtor; o "recorde pessoal" do rádio vem do store | sim |
| o relatório de evolução | é feito do store v2 | sim |
| os treinos | o retreino da LSTM (`retreino_lstm.py`) usa `list_all_sessions()`; o Modelo 1 e a validação usam o store (`lap_store.py`, idem) | sim |
| a avaliação do aprendizado | a validação (`ml/scripts/validate.py`) lê o store | sim |
| o Modelo 2 | o `carregar` lê o store e as gravações de fora dele pela lista sem as pistas de teste. Só a Parte F.2 lê a cópia, pedindo, com `incluir_pistas_de_teste=True`, pela sessão do roteiro, e só as minhas voltas (as da IA ficam de fora pelo `isAIControlled`) | sim (lê só pedindo) |

As únicas listagens das gravações que não passam pelo filtro são as do app que acham uma volta pelo id (a tela Volta e as frases do coach de uma volta já gravada). Elas não medem nada.

**O engenheiro (o app do jogo) na cópia: pelo código, ele cala.**

- O coach ao vivo procura o modelo pelo nome da pista do jogo (`model_path(…, "vhe_interlagos_teste_m1")`). Esse arquivo não existe, nem na pasta principal nem na do app instalado. Sem modelo, não há a projeção na geometria oficial.
- O rádio e o engenheiro (pedido 52) pegam a posição do carro dessa projeção (`posicao_oficial`). Sem ela, não há posição: nem os avisos do engenheiro, nem o feedback do rádio.
- **Não foi testado no jogo:** as sessões dos pedidos 47 e 50 na cópia eram da IA, e o rádio já cala com a IA.
- Se o engenheiro falar numa volta de teste, a volta continua valendo para o teste. Anote no CSV.

**No Modelo 2 (Parte F.2):** a análise lê as sessões de teste na cópia pedindo explicitamente, pela sessão do roteiro, e só as minhas voltas. Os detectores, as fases, o envelope e a calibração são os das 144 voltas, como nas voltas depois do kit.

**Tudo isso foi commitado antes de qualquer sessão de teste.**
