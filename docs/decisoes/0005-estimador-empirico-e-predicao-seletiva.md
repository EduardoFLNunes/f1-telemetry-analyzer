# 0005 — Estimador empírico de ganho e predição seletiva

- **Status:** aceita; em implementação na Fase 2b
- **Data:** 2026-09-30
- **Decisor:** Eduardo

## Contexto

O simulador não estima ganho local (0004). Ferramentas de coaching comerciais, como Coach Dave Delta e Garage 61, comparam com voltas reais por curva, numa grade fixa de distância.

A "volta ideal teórica" (soma dos melhores trechos) é criticada por juntar trechos incompatíveis: frear tarde parece ganhar tempo na entrada e perde na saída e na reta seguinte. As correções recomendadas são usar trechos que cubram a curva mais a reta seguinte e comparar voltas realistas.

A literatura de aprendizado de máquina formaliza a abstenção como "predição seletiva" ou "opção de rejeição", avaliada pela curva risco × cobertura.

## Decisão

1. **Unidade de análise:** janela de curva, do início da frenagem até o fim da reta seguinte, para capturar o efeito em cadeia de cada correção.
2. **Estimador:** aprender, só com as voltas do próprio piloto, a relação entre diferenças de condução acionáveis numa janela (ponto de frenagem, posição lateral na entrada, no ápice e na saída, ponto de retomada do acelerador) e a diferença de tempo na janela.
3. **Incerteza:** cada estimativa vem com um intervalo. Quando ele inclui zero ou é largo demais, a resposta é "ganho não conclusivo".
4. **Avaliação:** a mesma da Fase 2 (0006). A abstenção é medida pela curva risco × cobertura.

## Consequências

- "Não conclusivo" é uma saída formal e medida, não uma falha.
- A soma simples dos melhores trechos fica proibida como estimativa de ganho.
- Usar velocidade mínima ou de saída como variável de entrada é quase tautológico, porque a velocidade já contém o tempo. Essas variáveis só entram numa versão separada, apresentada como teto de referência.
