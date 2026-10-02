Eduardo aqui. Este pedido foi escrito junto com o Claude (Cowork), que faz a revisão e a arquitetura do projeto, e eu aprovo. O plano é meu. Pode executar.

As ferramentas da Fase 2c estão aprovadas. O cuidado com o número de volta repetido e o aviso de que a linha de 2 m fica fora do que já foi visto foram ótimos. Os 2 m continuam: criar variação que os dados não têm é justamente o objetivo do experimento, e o fato de os estimadores precisarem se abster na linha também testa o filtro de fora da distribuição.

Leia antes de começar:

- `docs/decisoes/0012-coach-diferenca-medida-nao-ganho-prometido.md`;
- a seção "Durante a sessão" de `docs/experimentos/protocolo_sessao_controlada.md`, que foi atualizada: sem box durante o plano e voltas inválidas anotadas pelo número do jogo.

## Parte A: incorporar as ferramentas

1. Em `develop`, faça `git merge --no-ff etapa/fase2c-ferramentas-experimento` e rode a suíte completa.
2. Commite em `develop`:
   - `docs/prompts/` (pedido 09);
   - `docs/decisoes/` (ADR 0012 e o índice);
   - o protocolo atualizado.

   Mensagem: `docs: ADR 0012, protocolo atualizado e pedido 09`.
3. Crie a tag `handoff/fase2c-ferramentas` nesse commit.

## Parte B: dois ajustes pequenos na análise do experimento

Branch `etapa/fase2c-ajustes`, a partir de `handoff/fase2c-ferramentas`.

1. **Intervalo de confiança.** Os ICs cobriram o valor verdadeiro entre 90 % e 99 % das 300 sessões sintéticas. Confirme se o IC do modelo linear usa a distribuição t com os graus de liberdade corretos para 8 blocos. Se usa a normal, troque pela t e repita a verificação de cobertura. O alvo é ficar perto de 95 %.
2. **Lista de voltas para o piloto.** Quando a análise listar as voltas gravadas, mostre também o número da volta no jogo, o tempo de volta e a hora do relógio. Assim eu consigo identificar uma volta inválida com o que vi na tela.

Faça o merge em `develop` só se a suíte passar, e me relate.

## Parte C: coach honesto (ADR 0012)

Branch `etapa/coach-referencia-real`, a partir de `develop` depois da Parte B. Pode commitar nela; não faça merge.

### 1. Medir antes de mudar

Antes de alterar o coach, meça o quanto o "melhor de todos por microsetor" é otimista, só com dados já gravados.

- Para cada sessão com pelo menos 20 voltas válidas, divida as voltas em duas metades na ordem em que foram feitas.
- Monte o "melhor de todos" de cada microsetor só com a primeira metade.
- Na segunda metade, relate:
  - em que fração das voltas cada microsetor atinge esse melhor;
  - quanto o "ganho na mesa" calculado pela primeira metade se realiza de fato na melhor volta da segunda metade.
- Relate também a volta ideal da primeira metade contra a melhor volta real da segunda.

Isso entra no relatório e no documento da etapa como evidência do problema descrito no ADR 0012.

### 2. Referência real

- Acrescente ao `reference_model` um modo **"volta de referência"**: a melhor volta válida e completa da mesma pista, carro e geometria, com opção de escolher outra pelo `lap_id`.
- Para cada microsetor, guarde dessa volta: o tempo do microsetor, o ponto de frenagem, a velocidade mínima e o ponto de retomada do acelerador.
- O limiar de fala continua igual: duas vezes a oscilação do próprio piloto no microsetor.
- O modo antigo continua disponível, desligado por padrão, para comparação.

### 3. O que o coach diz

- Troque "dá para ganhar X s" por "X s atrás da sua volta de referência neste trecho".
- Quando houver, acrescente a meta de resultado da referência: "na referência: freada em … m, mínima de … km/h".
- Nada de "volta ideal" ou "ganho possível" como número.

### 4. Interface

- Localize no frontend onde aparecem "volta ideal", "na mesa", "ganho" ou equivalentes vindos desse modelo.
- Troque pelo rótulo do novo modo (por exemplo, "diferença para a volta de referência") ou remova o número.
- Faça a menor mudança possível e liste no relatório cada texto alterado, com arquivo e linha.
- Não mude o layout.

### 5. Testes

- O modo novo escolhe a melhor volta válida completa.
- As diferenças por microsetor somam a diferença de tempo de volta, dentro da tolerância de interpolação.
- As frases novas não contêm "ganhar" nem "ideal".
- O modo antigo continua funcionando quando ligado.

### Restrições

- Não mexa no `optimal.json`, nas LSTMs nem na geometria do runtime (ADR 0002 fica para outra etapa).
- Não contorne nenhuma trava: se algo bloquear, pare e me avise.

### Entrega

Em `docs/handoff/`:

- o patch contra `develop`;
- a saída completa do pytest;
- um JSON com a medição do item 1 e o resultado dos testes.

Escreva também `docs/coach_referencia_real.md` em português simples: o problema, a medição, a mudança e as limitações.

No relatório, apresente as partes A, B e C nessa ordem. Não envie nada ao remoto.
