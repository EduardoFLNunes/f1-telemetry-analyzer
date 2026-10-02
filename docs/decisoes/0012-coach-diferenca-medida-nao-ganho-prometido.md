# 0012 — O coach mostra diferença medida contra uma volta real, não "ganho possível" pela soma dos melhores trechos

- **Status:** aceita; refina o ADR 0004
- **Data:** 2026-10-02
- **Decisor:** Eduardo

## Contexto

O coach ao vivo (`core/assisted_analysis/reference_model.py` e `core/live/driving_coach.py`, descritos em `docs/mapa_dashboard_e_coach.md`) guarda, para cada um dos 60 microsetores, **o mais rápido que o piloto já foi ali**. Com isso:

- diz frases como "dá para ganhar 0,4 s em T4";
- soma os 60 melhores para formar uma "volta ideal" (83,542 s contra 84,861 s da melhor volta real, com "1,319 s na mesa").

Esse é exatamente o método da "volta ideal teórica", que o ADR 0005 proíbe como estimativa de ganho. Ela tem dois problemas:

1. **Junta trechos incompatíveis.** Um trecho rápido pode ter custado o trecho seguinte, e a soma ignora isso.
2. **É otimista por construção.** O melhor de 150 tentativas ruidosas é sempre mais baixo que o que o piloto consegue repetir, mesmo sem nenhuma melhora real. Quanto mais voltas no histórico, mais otimista fica o "ganho".

Ferramentas comerciais (Coach Dave Delta, Garage 61) mostram a diferença medida contra uma **volta de referência real e completa**.

## Decisão

O coach distingue três tipos de número:

| Tipo | Exemplo | Permitido? |
|---|---|---|
| Diferença medida contra uma volta real completa | "0,12 s atrás da sua volta de referência neste trecho" | sim: é um fato medido |
| Meta de resultado tirada dessa volta | "na referência, a mínima aqui foi 124 km/h e a freada começou em 2 610 m" | sim, rotulada como "da sua volta de referência" |
| Ganho possível ou previsto | "dá para ganhar 0,4 s", "volta ideal 83,5 s" | não, até um estimador passar no protocolo do ADR 0006 |

- A volta de referência padrão é a melhor volta válida e completa da mesma pista, carro e geometria, e o piloto pode escolher outra.
- O limiar de quando o coach fala continua sendo o atual: duas vezes a oscilação do próprio piloto naquele microsetor.
- O modo antigo ("melhor de todos por microsetor") pode continuar no código para comparação, desligado por padrão.

## Consequências

- O coach fica mais honesto e mais parecido com as ferramentas usadas no automobilismo.
- A "volta ideal" sai da interface, ou passa a ser explicada como limite otimista e não como meta.
- O ADR 0004 continua valendo para os segundos vindos do simulador. Este ADR esclarece que a diferença medida contra uma volta real não é previsão e pode ser mostrada.
