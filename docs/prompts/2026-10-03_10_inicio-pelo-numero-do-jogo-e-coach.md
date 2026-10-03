Eduardo aqui. Este pedido foi escrito junto com o Claude (Cowork), que faz a revisão e a arquitetura do projeto, e eu aprovo. O plano é meu. Pode executar.

Boa verificação do intervalo de confiança: cobertura de 94,8 % a 95,3 % é exatamente o que precisávamos. As respostas às suas duas perguntas estão abaixo.

## 1. Voltas de aquecimento: nem (a) nem (b) sozinhas

Contar voltas de aquecimento de cabeça durante a sessão é fácil de errar, e um erro de uma volta desalinharia o plano inteiro. Por isso, a análise passa a começar por uma volta que eu anoto, e não pela contagem.

Na branch `etapa/fase2c-inicio-por-volta`, a partir de `develop`:

1. O `.txt` do plano ganha, logo depois do aquecimento, a linha: `ANOTE o número no jogo desta volta (primeira do bloco 1): ____`.
2. A análise ganha o argumento `--inicio <número da volta no jogo>`. A partir dessa volta, ela casa as voltas válidas com os blocos do plano, em ordem. As voltas antes dela são ignoradas, sejam quantas forem.
3. O número de voltas medidas (32 mais as repetidas por invalidez) continua sendo conferido de forma estrita. Se não bater, a análise para e mostra a lista, como hoje.
4. Se `--inicio` não for informado, mantenha o comportamento atual (contagem pelo plano), para não quebrar o que já existe.
5. Testes:
   - aquecimento com 4, 5 e 7 voltas, todos com o mesmo resultado quando `--inicio` é dado;
   - `--inicio` apontando para um número que não existe na sessão deve parar com mensagem clara.
6. Atualize o plano de exemplo em `docs/experimentos/`.
7. Se a suíte passar, faça o merge em `develop`.

O protocolo já foi atualizado com essa instrução: cerca de 5 voltas de aquecimento além da saída dos boxes, anotando o número da primeira volta do bloco 1.

## 2. Diferença de 3 h no horário: não investigar agora

A causa provável é uma confusão entre UTC e o fuso de São Paulo (UTC−3). Ela só afeta a exibição da hora, e a sua solução pelo `startedAt` resolve isso para a análise. O item ficou registrado em `docs/backlog.md`, a nova lista de pendências do projeto.

## 3. Commit de documentação

Em `develop`, commite:

- `docs/prompts/` (pedido 10);
- `docs/backlog.md`;
- o protocolo atualizado.

Mensagem: `docs: backlog, protocolo (inicio pela volta anotada) e pedido 10`.

## 4. Depois: Parte C do pedido 09

Siga a Parte C de `docs/prompts/2026-10-02_09_merge-fase2c-e-coach-honesto.md`, sem mudanças, em ordem:

1. medir o otimismo do "melhor por microsetor";
2. criar o modo "volta de referência";
3. trocar as frases do coach;
4. trocar os rótulos da interface;
5. testes, handoff e `docs/coach_referencia_real.md`.

Crie a branch `etapa/coach-referencia-real` a partir de `develop` depois dos itens 1 e 3 deste pedido.

No relatório, apresente os itens 1 e 3 e depois a Parte C. Não envie nada ao remoto.
