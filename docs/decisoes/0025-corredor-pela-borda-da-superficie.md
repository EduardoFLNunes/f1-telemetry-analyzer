# 0025 — O corredor do Modelo 1 vai pela borda da superfície, com um `corridor_id` à parte

- **Status:** aceita (pedido 44); emenda o 0002
- **Data:** 2026-10-29 (registrada em 2026-11-02, antes de rodar)
- **Decisor:** Eduardo

## Contexto

O pedido 27 comparou o corredor do ML com a pintura e com o sinal de pneus fora do jogo (`docs/handoff/2026-10-10_27_corredor-x-pintura_relatorio.md`):

- o corredor passa da pintura em 20,6% da volta à esquerda e em 46,3% à direita;
- contra o sinal do jogo, ele é "estreito demais" em 15.338 amostras e "largo demais" em 548;
- a opção 3, a borda da superfície do cache (asfalto, zebra e pintura), é a que mais se aproxima do jogo: 6.764 e 411.

Ele também apontou dois problemas de identidade: mudar as bordas no cache muda o `geometry_id` e força refazer o store, o inventário e o coach, embora o `s` e o `lateral` só dependam da linha central e das normais; e `CAR_HALF_WIDTH_M` e `KERB_ALLOWANCE_M` não entram em nenhuma impressão digital, então o corredor útil pode mudar sem que nada registre isso.

Em 29/10, o Eduardo escolheu a opção 3, com o `corridor_id` separado.

## Decisão

1. **A borda do corredor** é a borda da superfície do cache (asfalto, zebra e pintura) de cada lado, pela regra da opção 3 do pedido 27: em cada ponto da grade, um raio sai da linha central ao longo da normal, com passo de 0,05 m e até 30 m, e a borda é o início do primeiro trecho de ao menos 0,3 m fora da superfície. Onde ela faltar (1 ponto à esquerda), fica a borda de hoje.
2. **O corredor útil** continua sendo a largura menos (`CAR_HALF_WIDTH_M` − `KERB_ALLOWANCE_M`).
3. **O `corridor_id`** é a impressão digital das larguras, de `CAR_HALF_WIDTH_M`, de `KERB_ALLOWANCE_M` e do `geometry_id` em que elas valem.
4. **O `geometry_id` não muda:** o `s`, o `lateral`, o store, o inventário e o coach ficam como estão.
5. **Toda saída que depende das larguras** registra o `corridor_id`. O ADR 0007 vale para ele como para o `geometry_id`.

## Consequências

- O que depende das larguras é refeito: a LSTM geradora, a substituta, o critério da F1 e a métrica `outside_corridor_fraction`. O evolutivo é refeito no pedido da nova busca.
- O `optimised_lateral.npy` de 24/08 fica guardado como está, marcado como de outra geometria.
- O ADR 0002 ganha uma linha de atualização: o `geometry_id` não cobre mais o que o corredor do Modelo 1 significa.
