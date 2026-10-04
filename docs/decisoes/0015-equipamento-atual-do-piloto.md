# 0015 — O modelo do piloto usa só voltas com o equipamento atual

- **Status:** aceita; complementa o ADR 0014
- **Data:** 2026-10-04
- **Decisor:** Eduardo

## Contexto

O Eduardo pilota com um volante RS50 e pedais com célula de carga desde 01/10/2026. Todas as gravações de maio a setembro são anteriores a isso.

O pedido 12 mostrou que, em todas as sessões antigas, o freio vai de 0 a 0,99 de uma vez. Isso combina com a IA do jogo ou com um controle sem pedal analógico, e não com pedais de célula de carga. A sessão de teste de 04/10, já com o equipamento novo, deu voltas humanas de 93,0 s e 95,3 s, contra 85,0 s e 85,1 s da IA.

Com equipamento novo, o jeito de pilotar muda e deve melhorar rápido nas primeiras semanas. Voltas humanas antigas, se houver, descrevem outro piloto na prática.

## Decisão

- Toda volta recebe também o campo `equipamento`: `atual` (a partir de 01/10/2026) ou `anterior`.
- Para tudo que fala do piloto (referência do coach, variação, estilo, tamanho do experimento), valem só voltas `humano` com equipamento `atual`.
- Nas voltas antigas, o detector serve para separar as voltas da IA, que podem virar referência rotulada. Ele não serve para medir o jeito de pilotar do Eduardo.
- **O experimento controlado espera a curva de aprendizado estabilizar.** O critério é medido: a mediana do tempo de volta das últimas 3 sessões varia menos de 0,5 s entre elas. O limite pode ser revisto com os primeiros dados, desde que seja antes de olhar o resultado do experimento.

## Consequências

- Medidas de dosagem do freio e de frenagem em curva passam a ser possíveis, porque o freio agora é analógico.
- O histórico do piloto começa praticamente do zero. Cada sessão nova vale mais do que as antigas.
- A evolução do piloto, sessão a sessão, vira um resultado do próprio projeto: tempo de volta, consistência e distância até a linha da IA por curva.
- O coach é mais útil justamente agora, na fase de aprendizado. A comparação com a volta da IA, rotulada como tal, é a referência mais estável enquanto o melhor tempo do piloto muda a cada sessão.
