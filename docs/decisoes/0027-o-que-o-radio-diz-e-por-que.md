# 0027 — O que o rádio diz, em que ordem e por quê

- **Status:** aceita (pedido 45); complementa 0012, 0020 e 0021; uma decisão em aberto (ver o fim)
- **Data:** 2026-11-04
- **Decisor:** Eduardo

## Contexto

O Eduardo observou em 02/11 que o rádio quase sempre dizia só a diferença da volta para a IA. Ele pediu para ouvir a diferença para a melhor volta dele, quantos décimos perdeu em qual curva e por quê.

A pesquisa de 02/11 e a do projeto (`docs/tecnica_de_pilotagem_pesquisa.md`) dizem o mesmo:

- **curto e direto,** para o piloto agir sem pensar;
- **na reta,** nunca na freada nem numa curva rápida; o que não é urgente fica para os boxes;
- **informação, e não "vai mais rápido":** um número e um alvo;
- **o tempo sozinho ajuda pouco.** "0,8 s mais lento no setor 2" não diz o que fazer; "freando cedo demais na curva 5" diz. A Delta (Coach Dave) compara cada fase da curva com uma volta de referência;
- **uma correção por vez** (o coach por voz da Trophi): depois da curva, o que mais custou; no fim da volta, o que melhorou, o que ainda segura e o foco seguinte;
- **o foco externo e a faixa de tolerância:** uma marca da pista, e não o corpo; não falar do que está perto da referência.

Na F1, em corrida, a FIA restringiu o coaching por rádio em 2014 e 2016. O nosso rádio é de treino, onde o coaching vale.

## Decisão

### O resumo da volta

Pela ordem de importância:

1. a diferença para a sua melhor volta da sessão; ou "melhor volta", com o quanto ela foi mais rápida que a melhor anterior; ou "recorde pessoal", se ela bater a melhor de todas as sessões do store, para o carro e a pista;
2. a curva da volta, com a perda e a causa;
3. a diferença para a referência escolhida na Coleta (a IA por padrão);
4. a diferença para a volta anterior, só quando a volta melhorou sobre a anterior sem ser a melhor;
5. o tempo da volta. O cartão sempre traz o tempo e todos os números.

As variantes da fala vão da mais completa à mais curta e perdem os itens de baixo para cima. A unidade nunca sai (pedido 36). A fala tem de caber no limite do tipo (7,7 s no resumo).

**A melhor volta** é a mais rápida da sessão entre as que contam para a análise: completa pela regra do coach, com as medidas e sem rodada.

**A volta com rodada e a incompleta** dizem o tempo e a diferença, sem a curva. **A volta da IA continua calada,** como hoje: a volta não tem resumo. **O estado "inválida"** existe na lista, mas nenhuma volta chega nele: o jogo não manda esse sinal ao backend.

**A curva que não cabe** vai numa mensagem própria, para o fim da fila (ela não passa à frente das frases do coach). Se o carro passar pela curva antes de achar uma janela, a mensagem sai da fila: falar de uma curva que acabou de ser refeita confunde.

### A curva da volta e o porquê

- **A curva:** a que mais perdeu na volta contra a referência, com a mesma perda da análise e da grade. Abaixo de 1 décimo, nenhuma curva é citada.
- **O trecho:** a parte da curva com a maior parte da perda, pelas separações da diferença acumulada do pedido 43 (`analise.partes_da_perda`):

| parte | de onde a onde | conta como causa? |
|---|---|---|
| `reta` | da entrada do trecho à primeira freada | não: é o que veio da curva anterior |
| `freada` | da primeira freada à mínima da referência | sim |
| `mínima` | da mínima da referência ao fim da curva | sim |
| `saída` | do fim da curva ao fim do trecho | sim |

- **A causa:** a medida desse trecho, quando passa do corte (`analise.causa_da_curva`):

| trecho | a causa | corte | a voz |
|---|---|---|---|
| freada | o ponto de freada, antes ou depois | 15 m (o do coach) | "freou 15 metros antes da IA" |
| mínima | a mínima abaixo da referência | 8 km/h (o do coach) | "mínima 9 quilômetros por hora abaixo da IA" |
| mínima | senão, o traçado no ápice | 1,8 m (o da análise) | "passou 3 metros por fora no ápice" |
| saída | a velocidade mais baixa no fim da curva | 8 km/h (novo) | "saiu 8 quilômetros por hora mais lento" |

Sem medida acima do corte, a voz diz só o trecho: "perdeu 3 décimos na saída". "Por fora" e "por dentro" vêm do lado da curva (ADR 0003).

**O corte novo** (`CORTE_SAIDA_KMH`, commit `460acdc9`, antes de rodar as sessões): a velocidade no fim da curva é a mesma grandeza da mínima, medida do mesmo jeito, então vale o corte da mínima. O porquê vem da definição, e não do resultado.

**Uma mínima ou uma saída mais rápidas que a referência não são causa:** elas não explicam uma perda. A frase do coach continua dizendo "acima", porque ali a causa é a que o coach mediu.

### A frase do coach e a análise

O coach continua decidindo quando falar (o foco, o limiar, o máximo de 3 por volta e o microssetor). Só o texto muda, para as palavras acima. A regra da análise não muda; o texto usa as mesmas palavras e, se couber, começa pela tendência: a média das 3 voltas contra a das 3 anteriores.

### Um número só para cada volta

Vence **o contador do jogo no meio da volta,** o mesmo `game_lap_number` que o store já guarda. O piloto vê esse número no jogo, ele existe ao vivo, e o id do store (`#NNNN`) é só a ordem no arquivo. No quadro da passagem pela linha, o contador pode já ter adiantado (13/10, a volta 9; 21/10, a 14); no meio da volta, ele é sempre o certo.

## O que continua

A diferença é medida contra uma volta real, nunca um ganho prometido (ADR 0012). Nada é dito dentro das 14 curvas. A referência é a escolhida na Coleta. No replay de uma mensagem com curva, os números da voz.

## A regra dos boxes (decisão do Eduardo, 04/11)

A regra "boxes" do coach (a lateral acima de 10 m, abaixo de 90 km/h) passa a valer só onde existe pit lane: em Interlagos, os microssetores 54 a 59 e 0 a 10. Fora dele, é uma saída larga, e o microssetor é medido. A volta de 1:29,518 de 21/10 caía nela por um microssetor, com 11,0 m a 81,9 km/h. Numa pista fora da lista, a regra continua na volta inteira. A parada (abaixo de 5 km/h) e a rodada (mais de 5 s numa curva) não mudam.

## Decisões em aberto, do Eduardo

1. **O limite do resumo.** Os exemplos do pedido duram de 7,13 a 8,73 s com a voz de verdade, e o limite é 7,7 s. Pela ordem acima, a diferença para a IA é a primeira a sair quando a curva precisa caber.

Os números e as opções estão em `docs/handoff/2026-11-02_45_replay-de-perto-e-radio-que-ensina_relatorio.md`.

## Fontes

- Autosport, "The secrets of in-race radio chat": https://www.autosport.com/f1/news/the-secrets-of-in-race-radio-chat-5102490/5102490/
- Formula1.com, "FIA clarifies radio transmission restrictions" (2014): https://www.formula1.com/en/latest/article/fia-clarifies-radio-transmission-restrictions.4uSbLsruNnnmXXDqUjh7yV
- RACER, 18/03/2016, sobre o coaching por rádio: https://racer.com/2016/03/18/f1-radio-coaching-intolerable-whiting/
- Coach Dave Academy, "How to use Auto Insights (AI coaching) in Delta": https://coachdaveacademy.com/documentation/how-to-use-auto-insights-ai-coaching-in-delta/
- Trophi.ai, "Mansell": https://www.trophi.ai/sim-racing-features/mansell
- `docs/tecnica_de_pilotagem_pesquisa.md`: as fontes do projeto sobre o feedback no ensino da pilotagem.
