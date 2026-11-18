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

- **A pista:** a original (`vhe_interlagos`), e não a cópia (`vhe_interlagos_teste_m1`).
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

## 3. As sessões de teste fora de tudo o que mede a evolução (item 4): **sem jeito limpo com o que já existe; proposta e parada neste item**

As sessões de teste têm de ficar fora de:

- o coach;
- a "Sua melhor volta" do app;
- o engenheiro (a melhor da sessão e a volta lenta);
- o relatório de evolução;
- a avaliação do aprendizado;
- os treinos dos modelos, a LSTM incluída.

**O que existe hoje:**

- **A anotação de sessão** (`docs/experimentos/anotacoes_de_sessao.csv`, lida por `ml/data/session_annotations.py`) só sabe dizer **quem pilotou**: `humano`, `ia`, `misturada` ou `desconhecida`.
  - Anotar a sessão de teste como `desconhecida` tiraria as voltas do store como voltas do piloto e, por isso, do coach, da "Sua melhor volta" (quando o coach for refeito), do relatório de evolução e dos treinos.
  - Mas seria uma origem falsa: fui eu que pilotei.
  - E tiraria as voltas também do Modelo 2, que só lê voltas `humano` e `ia`: a Parte F.2 não teria o que analisar.
- **As pistas de teste** (`config.TEST_TRACK_NAMES`) ficam fora de tudo, mas só valem para a cópia da pista. O teste tem de ser na original.
- **O engenheiro (pedido 52) é ao vivo.** Durante a sessão de teste, a "melhor da sessão" e a "volta lenta" dele seriam as das voltas provocadas. Nenhuma marca depois da sessão muda isso.

**A proposta** (código novo; não fiz, porque o pedido manda parar neste item):

1. **Uma coluna `finalidade` na anotação de sessão,** com o valor `teste_provocado`, sem mudar a origem, que continua `humano`.
2. **Quem lê a marca e deixa a sessão fora:**
   - a seleção das voltas do piloto (`evolution.driver_laps`, que alimenta a evolução, o coach e a "Sua melhor volta");
   - os treinos (o retreino da LSTM e o Modelo 1);
   - a avaliação do aprendizado.

   O store guarda as voltas com a marca, como faz com as outras.
3. **O Modelo 2** lê as sessões `teste_provocado` só na Parte F.2, pedindo explicitamente, como o `incluir_pistas_de_teste` faz com a cópia da pista.
4. **O engenheiro ao vivo:**
   - **sem código:** você desliga o coach e o engenheiro no app antes de sair dos boxes nas duas sessões (a configuração "coach desligado" já existe);
   - **com código,** como alternativa: um botão "sessão de teste" no app, que grava a marca no metadado da gravação, e o engenheiro não usa a sessão marcada.
5. **Testes:** uma sessão marcada não entra na evolução, no coach nem nos treinos, e entra no Modelo 2 só pedindo.

**Até a decisão, as sessões de teste não devem ser gravadas.** O roteiro, a folha, o CSV e o esperado já estão prontos e commitados.
