# 0023 — Modelo 2: as quatro peças para achar o erro, a técnica e o estilo, nas voltas da IA e do piloto

- **Status:** aceita
- **Data:** 2026-10-24
- **Decisor:** Eduardo
- **Refina:** 0018 (peças B e C do Modelo 2). **Mantém:** 0012 (diferença medida, nunca ganho prometido), 0014 e 0015 (origem das voltas e equipamento atual), 0004 (o simulador não estima ganho local)

## Contexto

1. **O problema que o Eduardo identificou (24/10):** ensinar onde e quando frear não basta; sem os conceitos técnicos, o piloto continua perdendo tempo. O Modelo 2 precisa achar o erro que custou tempo, ver se o piloto aplica as técnicas e saber se a técnica combina com o estilo dele.
2. **A pesquisa de 24/10** (`docs/tecnica_de_pilotagem_pesquisa.md`) concluiu:
   - **o cluster não serve como resultado principal.** Os estudos que agruparam voltas de simulador (Remonda et al. 2021; Hojaji et al. 2026) encontraram níveis de tempo de volta e estágios de aprendizagem, não estilos, e o método pede de 20 a 30 casos por grupo;
   - **o que funciona** é combinar quatro peças: a comparação com uma volta real, detectores de técnica por regras, dimensões contínuas de estilo e um modelo supervisionado pelo tempo de cada trecho;
   - **cada técnica e cada erro** tem um indicador calculável com os canais que o Assetto Corsa grava.
3. **A decisão do Eduardo (24/10):**
   - seguir com a combinação das quatro peças;
   - identificar tudo nas voltas gravadas, **tanto da IA quanto do piloto**: o erro que fez o piloto perder tempo contra a IA, as técnicas que cada um usa e o estilo de cada um;
   - montar o estilo também com dados externos de outras categorias, porque há pouca informação sobre este carro, e posicionar a IA e o piloto pelos vizinhos mais próximos (KNN) entre pilotos de estilo bem definido.

## Decisão

### 1. As quatro peças

| Peça | Pergunta | Como |
|---|---|---|
| **Comparação com uma volta real** | Onde e quanto o piloto perde? | A diferença de tempo na grade de 2 m, somada por curva e por fase da curva (frenagem, entrada, meio, saída e reta seguinte), contra a volta da IA e contra a melhor volta do piloto |
| **Detectores de técnica por regras** | O piloto aplica a técnica? Que erro ocorreu? | Uma regra física por técnica, com três estados: "aplica", "não aplica" e "não conclusivo". Os limiares são calibrados pela distribuição das voltas de referência na mesma curva |
| **Dimensões contínuas de estilo** | Como o piloto executa? | Um vetor de medidas por tipo de curva (por exemplo, forma em V ou U, perfil de frenagem, uso dos pedais, aplicação do volante e perfil do acelerador), sem forçar categorias |
| **Modelo supervisionado leve** | Que medidas explicam o tempo nesta curva? | O tempo do trecho como alvo e as medidas dos detectores como entrada, validado deixando uma sessão de fora. Mostra associação, não causa, e não estima ganho (ADR 0004) |

### 2. Nas voltas da IA e nas do piloto

- **As mesmas regras rodam nos dois.** Só entram voltas de origem rotulada: `humano` com o equipamento atual e `ia` pelo indicador ou por anotação (ADR 0014, 0015 e 0018).
- **"Erro" é sempre uma diferença medida** contra uma volta real, com o tempo que ela custou. Uma passagem em que o piloto é mais rápido que a IA não é erro.
- **A IA não é o alvo.** A IA do jogo não pilota como um humano; uma diferença de técnica contra ela é uma diferença, não necessariamente um defeito. A melhor volta do próprio piloto é a outra referência.

### 3. O estilo com dados externos e o KNN

- **É um caminho próprio,** ao lado das quatro peças, desenhado depois da pesquisa de datasets.
- **Regras fixadas desde já:**
  - só entram medidas calculáveis nos dois lados (no nosso dado e no dataset externo);
  - as medidas são normalizadas para tirar o efeito do carro (por exemplo, relativas a uma referência do mesmo carro ou adimensionais);
  - os rótulos de estilo dos pilotos de referência vêm de fontes documentadas, com o tipo de evidência;
  - o KNN é validado deixando um piloto de fora: ele precisa acertar o estilo documentado de quem ficou de fora;
  - a posição da IA e a do piloto vêm com a distância aos vizinhos e com "não conclusivo" quando nenhum vizinho fica perto.

### 4. Antes de chegar ao piloto

- **Os detectores são validados** contra passagens rotuladas à mão pelo Eduardo (precisão e revocação) antes de qualquer frase nova no rádio.
- **O rádio e o coach não mudam** por causa desta decisão. A mudança do rádio para "uma correção por vez, com confirmação e retirada" é outra decisão (item C3 de `docs/tecnica_de_pilotagem_lista.md`).

## Consequências

- **O ângulo de subesterço** precisa da unidade do volante e do entre-eixos, que saem da M1 (ADR 0022, pedido 37). Até lá, ele usa uma medida substituta, marcada como tal.
- **As voltas da IA rotuladas de 04/10** não têm a guinada nem as velocidades no referencial do carro, porque foram gravadas antes do pedido 18. Os detectores que dependem desses canais ficam "não conclusivo" na IA até haver uma sessão nova da IA gravada pelo app do repositório.
- **A biblioteca de conceitos** (o que é cada técnica, por que funciona, como se treina e como medir) é outra peça, independente desta decisão, e entra no relatório depois da sessão.
- **Resultados negativos são aceitos e documentados.** Se um detector não passar na validação, ele não chega ao piloto.
