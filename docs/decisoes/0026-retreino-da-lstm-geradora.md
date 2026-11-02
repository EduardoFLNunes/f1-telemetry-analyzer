# 0026 — Retreino da LSTM geradora: a régua e os critérios

- **Status:** aceita (pedido 44); adapta o 0006 à geradora; refina 0018 e 0019
- **Data:** 2026-10-29 (registrada em 2026-11-02, antes de rodar)
- **Decisor:** Eduardo

## Contexto

O ADR 0018 manda retreinar a LSTM geradora com três fontes e testar na régua do ADR 0006, que foi escrito para estimadores de diferença de tempo. O ADR 0019, item 6, diz que só o retreino com e sem a F1 dirá se ela ajuda. A LSTM de hoje é de antes da regravação do cache e de antes das sessões do equipamento atual: erra 0,528 m de lateral nas voltas abaixo de 88 s e 2,898 m nas acima (`docs/auditoria_ml.md`, seção 3).

## Decisão

### A régua

- **A divisão:** deixar uma sessão inteira de fora a cada rodada, entre as sessões com voltas `humano` do equipamento atual ou voltas `ia` rotuladas. Tudo que é ajustado (pesos, normalização, parada) usa só as outras sessões.
- **A tarefa testada:** a geradora recebe a pista e as perdas da própria volta deixada de fora (o condicionamento de hoje), e devolve a lateral.
- **A métrica principal:** o erro absoluto médio da lateral, em metros, na grade oficial.
- **A referência ingênua:** a lateral mediana das voltas de treino, ponto a ponto. Skill = 1 − erro do modelo ÷ erro da referência.
- **Relatar também:** o erro de velocidade, freio e acelerador; o skill por sessão; por ritmo (abaixo e acima de 88 s, como na auditoria); e por fonte (as voltas do Eduardo e as da IA).

### Os critérios, fixados antes de rodar

Para aprovar, todos precisam ser atendidos:

- skill ≥ 0,20;
- limite inferior do IC 95% do skill > 0 (bootstrap agrupado por sessão);
- pelo menos 70% das sessões com skill positivo;
- pelo menos 5 sessões testáveis.

### Como cada número sai (fixado antes de rodar)

- **Sessão:** a de `ml.comparison.evolution.group_sessions`, a mesma da evolução e do Modelo 2: uma pausa de mais de 3 h entre gravações abre uma sessão nova. Na data deste registro são 15 sessões e 150 voltas (136 `humano` e 14 `ia`).
- **Sessão testável:** tem ao menos uma volta com a lateral finita nos 2.167 pontos.
- **Erro de uma volta:** a média de |previsto − real| nos pontos da grade. A previsão é a volta inteira, com o aquecimento de uma janela de `generate`, e a saída crua da rede, sem a projeção em splines nem o corte no corredor.
- **Erro agregado:** a média dos erros das voltas de teste, cada volta pesando igual. O skill agregado e o de cada grupo saem dessas médias.
- **IC 95%:** percentis 2,5 e 97,5 de 10.000 reamostragens das sessões com reposição, semente 44, recalculando o skill agregado.
- **Concentração (ADR 0006):** a maior sessão tem cerca de 16% das voltas, então não há "resultado sem elas"; o skill médio por sessão é relatado junto.
- **Ritmo:** pelo tempo da volta deixada de fora, abaixo de 88 s e a partir de 88 s.

### O treino de cada rodada

- **Arquitetura e treino de hoje:** `REFERENCE_TASK` (janela de 128, passo de 16), LSTM bidirecional de 2 camadas e 96 células, `SmoothL1`, `TrainConfig` padrão (teto de 200 épocas, paciência de 10), a mesma semente em toda rodada e nas duas versões.
- **As perdas de condicionamento** saem de `build_reference` sobre as voltas de treino da rodada (`humano` e `ia`), como hoje saem das voltas de treino.
- **A parada:** a validação é a primeira sessão depois da deixada de fora, em ordem cronológica e fechando o ciclo, e as seguintes, até somar ao menos 15% das voltas de treino. Sessões com voltas `ia` não entram na validação, para o treino não ficar sem elas. Ela sai do treino da rodada.
- **O fora de pista:** a sessão que dependa do `off_track = False` que o leitor põe quando o campo falta tem o fora de pista tratado como desconhecido, e isso é relatado.

### A entrada da F1

A F1 é o traçado de referência da época 2023–25 (ADR 0019), **só a posição, nunca velocidade, pedal ou ponto de frenagem**:

- **O alvo:** só a lateral. Velocidade, freio e acelerador ficam ausentes na linha da F1 e fora da perda, que passa a ignorar alvos ausentes.
- **O condicionamento:** perda 0 no microssetor e na volta, a pergunta que se faz à geradora. Combustível, desgaste e aderência ficam na média das voltas de treino da rodada.
- **Os microssetores de faixa pouco confiável** (MS04 a MS09, MS19 e MS46 a MS48): a lateral da F1 fica ausente neles, fora da perda. A F1 ali não ensina nada, e as voltas reais continuam valendo.
- **O peso:** a linha entra repetida até pesar uma sessão típica: a mediana de voltas por sessão de treino da rodada, arredondada.
- **O que ela não toca:** a normalização, as perdas de condicionamento, a validação de parada e a referência ingênua saem só das voltas reais. As duas versões têm a mesma referência ingênua.
- **O erro de alinhamento da F1 à geometria oficial** fica registrado no resultado.

### Com e sem a F1

As duas versões passam pela mesma régua. **A F1 fica no modelo final só se** o skill com ela for maior que sem ela, com o limite inferior do IC 95% da diferença (bootstrap pareado por sessão: as mesmas sessões sorteadas nas duas versões, 10.000 reamostragens, semente 44) acima de 0. Senão, o modelo final é o sem a F1, e o resultado é registrado.

### O modelo final

É a versão que a regra acima escolher, treinada em todas as sessões e salva com o `corridor_id`, o commit e os hashes dos dados (ADR 0007). Sem sessão de validação, ele treina pelo número de épocas da mediana da melhor época das rodadas daquela versão, e a taxa de aprendizado reage à perda de treino. Se a régua reprovar, o modelo é salvo mesmo assim, marcado como reprovado.

### A LSTM substituta

É retreinada com os atributos do corredor novo e relatada (erro por passo e por volta, deixando uma sessão de fora), sem critério de aprovação: o papel dela na aptidão é decidido no pedido da nova busca. Ela não usa a F1, que não tem tempo.

### Um resultado negativo é aceito e registrado

Como mandam os ADRs 0006 e 0022. Mudar um critério exige um novo ADR, registrado antes de rodar.

## Consequências

- As voltas antigas de origem `desconhecida` ficam fora (esclarecimento do ADR 0018). As sessões fora do store v2 entram lidas com as funções do store, sem gravar nele, marcadas `fora_do_store`.
- A nova busca evolutiva com a M1 como juiz não entra aqui: ela espera a M1 aprovada.
- A volta do Modelo 1 só vira referência do coach pelo item 4 do ADR 0018, seja qual for o resultado desta régua.
