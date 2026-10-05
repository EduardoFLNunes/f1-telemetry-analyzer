# 0016 — Na fase de aprendizado, a referência padrão do coach é a volta da IA

- **Status:** aceita; refina o ADR 0012
- **Data:** 2026-10-04
- **Decisor:** Eduardo

## Contexto

A sessão rotulada de 04/10 (pedido 13), com o volante e os pedais novos, mediu pela primeira vez o piloto separado da IA, no mesmo carro (`rss_formula_rss_3_v6_2026`):

| | Eduardo (11 voltas limpas) | IA (13 voltas limpas) |
|---|---|---|
| Desvio entre voltas no Bico de Pato | 0,91 s | 0,012 s |
| Dispersão do ponto de frenagem | 14,7 m | 1,0 m |
| Dispersão do ápice | 1,84 m | 0,04 m |
| Melhor volta | 89,379 s | 84,816 s |

> **Errata de 05/10/2026 (pedidos 19 e 20).** Os tempos da linha "Melhor volta" vieram do `duration_s` do inventário. Ele mede do primeiro ao último ponto gravado da volta e não é o tempo de volta.
>
> Os tempos oficiais (`lap_time_s` do store v2, conferidos contra o cronômetro do jogo) são:
>
> - o seu: **89,390 s** (`2026-10-04_02-24-04#0018`);
> - o da IA: **84,829 s** (`2026-10-04_03-42-10#0013`).
>
> A decisão não muda.

Três consequências:

1. **O ADR 0012 manda comparar com a melhor volta do próprio piloto.** Numa fase em que o piloto melhora a cada sessão, essa referência muda o tempo todo e fica longe do que o carro consegue.
2. **A IA é uma referência medida e estável:** mesmo carro, mesma pista, mesma geometria, repetindo a linha com diferença de centímetros.
3. **O experimento controlado com o piloto não é viável agora.** Com o desvio dele, detectar 30 ms exigiria 5.862 voltas por condição, e 8 voltas só detectam efeitos a partir de 0,81 s. A variação natural do piloto (14,7 m na frenagem) já é maior que as mudanças planejadas (10 m e 2 m).

## Decisão

- **O coach tem duas referências, ambas voltas reais e completas:**
  - `volta_ia`, a referência padrão nesta fase: a melhor volta limpa da IA, no mesmo carro e na geometria oficial, gravada com o comportamento atual da IA;
  - `minha_melhor`: a melhor volta limpa do piloto, só `humano` com equipamento `atual` (ADR 0015).
- As frases dizem qual referência estão usando ("atrás da volta da IA neste trecho"). Continua valendo o ADR 0012: diferença medida, nunca ganho prometido.
- O coach mostra também a diferença de ponto de frenagem em relação à referência ("a IA freia 12 m depois de você"). É um fato medido e mais útil ao vivo que a posição absoluta em metros.
- O limiar de fala continua sendo duas vezes a oscilação do piloto, calculada só com voltas `humano` e equipamento `atual`. Como a diferença para a IA aparece em quase todo trecho, o coach fala no máximo 3 vezes por volta, nos trechos de maior diferença, e resume no fim da volta.
- O experimento controlado com o piloto fica suspenso. A pergunta "quanto vale frear antes ou mudar a linha" passa para o caminho em que o próprio jogo executa as variações (decisão futura sobre o AC como simulador). Lá, o desvio da IA, de 12 ms, torna o experimento barato.

## Consequências

- O coach passa a ser útil já nas próximas sessões, como ferramenta de aprendizado.
- Volta da IA antiga não serve de referência: o detector mostrou que a IA de agosto fazia diferente no microsetor 41 e freava 6 a 8 m longe em duas zonas. A referência vem de sessões novas, rotuladas.
- Hipótese a testar: a IA em níveis mais fracos do jogo poderia dar referências no ritmo do piloto, a "trajetória coerente com o ritmo" do pedido original.
- Hipótese a testar: como o piloto varia muito naturalmente, as voltas dele podem um dia mostrar efeitos que as voltas da IA não mostravam (o contrário do ADR 0011). O risco de confusão continua: quem freia tarde também tende a errar o ápice.
