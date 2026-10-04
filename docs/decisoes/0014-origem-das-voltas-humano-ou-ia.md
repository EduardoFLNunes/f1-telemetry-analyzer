# 0014 — Toda volta tem origem: humano, IA ou desconhecida

- **Status:** aceita
- **Data:** 2026-10-03
- **Decisor:** Eduardo

## Contexto

O Eduardo informou que muitas sessões foram gravadas com a IA do Assetto Corsa pilotando o carro, ligada por um botão no jogo. Ele lembra de ter usado a IA nas sessões de 14/06 a 19/06, de 20/06 e de 09/08. Juntas, elas somam 115 das 122 voltas válidas. Ele também alternava entre a IA e a própria pilotagem dentro da mesma sessão, então o rótulo precisa ser por volta, não por sessão.

Até agora, o projeto tratou todas as voltas como do piloto. Isso afeta conclusões já registradas:

- **Consistência.** "Em 99 % dos pares de voltas, o ponto de frenagem varia menos de 5 m e o ápice menos de 0,5 m" (Fase 2b, ADR 0011) é o que se espera de uma IA seguindo sempre a mesma linha.
- **Tamanho do experimento controlado.** A variação usada no cálculo (14 a 35 ms no Bico de Pato) veio das sessões de 09/08 e 20/06. Se a variação humana for maior, o número de voltas necessário cresce com o quadrado dela.
- **Coach.** A volta de referência e o limiar de fala (duas vezes a oscilação do piloto) podem estar vindo de voltas da IA.
- **Modelos.** As LSTMs, o envelope do carro e os estimadores das Fases 2 e 2b foram ajustados com voltas misturadas.

## Decisão

- Toda volta recebe uma origem: `humano`, `ia` ou `desconhecida`.
- **Nada que fale do piloto usa voltas que não sejam `humano`.** Isso vale para a referência do coach, o limiar de fala, os clusters de estilo, o tamanho do experimento e qualquer frase com "você".
- As voltas da IA ficam guardadas e rotuladas. Elas podem ser usadas como uma referência explícita ("volta da IA") ou em estudos do carro e do simulador, nunca como se fossem do piloto.
- O gravador passa a registrar se a IA está no controle e qual é o carro.
- As voltas antigas são rotuladas pelo registro do jogo, se ele existir nas gravações. Se não existir, um detector por volta é treinado com sessões novas já rotuladas e validado por sessão. Quando ele não tiver certeza, a volta fica `desconhecida`.
- A sessão controlada espera até a variação humana no Bico de Pato ser medida com voltas `humano`.

## Consequências

- O merge do pedido 11 (coach na geometria oficial) espera a rotulagem, para a volta de referência ser humana.
- Os números das Fases 2 e 2b continuam valendo como medidas dos estimadores naquelas voltas. A leitura deles como "o jeito de pilotar do Eduardo" será refeita com voltas `humano`.
- A conclusão do ADR 0011 continua de pé, e fica mais forte: voltas sem variação proposital não medem o efeito de uma instrução.
- Textos já publicados que dizem "você" sobre essas voltas (apresentações, vídeo, documentos) serão corrigidos depois da rotulagem, com os números certos.
- As voltas da IA podem virar uma vantagem. A IA é um piloto constante dentro do próprio jogo, e isso pesa a favor de usar o Assetto Corsa como simulador (decisão futura).
