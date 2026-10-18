# Pedido 34 — A régua da checagem do período: medir o tempo do jogo na mesma linha do período

**De:** Eduardo. **Data:** 18/10/2026.
**Tipo:** emenda de uma checagem do store v2, e a rodada do `atualizar_coach` que estava parada. O limite de 5 ms não muda, e nenhuma volta sai do store.

**Ao mandar executar este pedido, eu escolho a opção 1** do relatório do pedido 33 ("O que precisa de decisão").

**Ordem:** este pedido vem antes do pedido 35. Só um chat trabalha por vez na pasta (ADR 0008). Os cuidados de processo da Parte C do pedido 33 valem aqui.

## Contexto

Está no relatório do pedido 33 (`docs/handoff/2026-10-18_33_relogio-do-gravador-novo_relatorio.md`):

1. **A checagem `store_checks.check_period` compara duas linhas diferentes:**
   - o período vai de s = 0 a s = 0 da geometria oficial;
   - o tempo do jogo vai de linha do jogo a linha do jogo, e a linha do jogo fica 1,463 m depois do s = 0 (138 voltas, desvio de 0,07 m).
2. **Por isso, a diferença depende da velocidade nas duas pontas da volta.** Ela só some quando o carro passa pela linha na mesma velocidade no começo e no fim.
3. **Sem a travessia,** o p99 das 676 voltas cai de 7,63 ms para 3,56 ms, e as voltas acima de 5 ms caem de 10 para 3.
4. **O gravador, o corte em voltas e a interpolação na linha estão certos** (Parte A do pedido 33).
5. **Enquanto a checagem reprova:**
   - o relatório de evolução continua o de 16/10;
   - o botão "Atualizar coach e relatório" para no mesmo passo;
   - a contagem oficial da M1 (3 de 5) é provisória;
   - a sessão `2026-10-18_12-38-44` (15 voltas) espera a próxima rodada.

## Princípio, fixado antes de rodar

- **O que a checagem prova não muda:** o período de uma volta bate com o cronômetro do jogo.
- **Só a régua muda:** os dois lados passam a medir na mesma linha.
- **O limite de 5 ms continua.** Nenhuma volta sai do store, e nenhuma gravação é mudada.
- **Se a checagem não passar com a régua nova,** pare e relate. Não mexa no limite.

## Parte A — A emenda

1. **A régua nova.** Escolha uma destas duas e diga por quê:
   - **medir o período na linha do jogo:** a mesma interpolação de hoje, em s = 1,463 m em vez de s = 0, nas duas pontas;
   - **somar a travessia ao tempo do jogo:** 1,463 m × (1/v no começo − 1/v no fim), com a velocidade gravada na passagem.

   A outra entra só como conferência, no relatório.
2. **A distância de 1,463 m** não é um número solto no código:
   - ela é medida nas gravações, como no pedido 33 (onde o cronômetro do jogo zera);
   - uma checagem nova confere, sessão a sessão, que ela fica perto do valor medido. Se a geometria oficial ou a linha do jogo mudarem, a checagem reprova com o motivo.
3. **Os testes:**
   - uma volta que começa devagar e termina rápido, e o contrário;
   - uma volta com a passagem pela linha entre duas amostras;
   - a checagem nova da distância.
4. **O registro:** a emenda vai em `docs/store_v2_e_evolucao.md` (1.3), com a medida, a régua e o antes e depois.

## Parte B — A rodada

1. **Antes de rodar:**
   - guarde a cópia de antes, fora do git, como no pedido 26;
   - confirme que o app instalado está fechado e que nenhuma sessão está sendo gravada.
2. **Rode o `atualizar_coach` padrão (incremental).** Ele deve passar no passo da checagem e seguir até o fim.
3. **Relate o antes e depois,** como no pedido 32:
   - **a checagem do período:** o p99 e as voltas acima de 5 ms, antes e depois, com a lista das que continuarem acima;
   - **a sessão `2026-10-18_12-38-44`:** as voltas válidas, as que entram no coach, a mais rápida e o nome no relatório de evolução;
   - **o coach:** as duas referências, quantas voltas suas, o limiar e o foco de cada modo;
   - **o store v2:** as voltas por origem;
   - **o critério do ADR 0015:** as três últimas sessões e a amplitude;
   - **a contagem oficial da M1,** agora lida de um store aprovado.
4. **Confira na tela Sessões** que a sessão de 18/10 entrou em "Sessões no relatório".

## Parte C — A recomendação para a M1

O pedido 33 (A.5) recomenda usar o cronômetro do jogo como relógio da M1 e descartar as amostras repetidas. Registre isso no documento da M1 como **pendente, sem mudança agora**. A decisão fica para o pedido que retreinar a M1.

## Regras gerais

- **Nenhum critério muda além da régua desta checagem:** o limite, os portões, as regras do coach e do store ficam como estão. Nenhuma volta sai do store.
- **As gravações são só lidas.**
- **Não mexa no app instalado nem em arquivos do jogo.**
- **Não instale nem atualize pacotes.**
- **Não gere instalador.**
- **Não contorne nenhuma trava:** se algo parar, pare também e registre o motivo. Uma trava do git não é apagada sem me perguntar.
- **Branch e commits:** branch `etapa/regua-do-periodo`, commits por parte, merge em `develop`. Sem push.
- **Uma sessão de implementação por vez** (ADR 0008).
- **Relatório** em `docs/handoff/2026-10-18_34_regua-da-checagem-do-periodo_relatorio.md`, como manda o CLAUDE.md, com:
  - a régua escolhida e a conferência pela outra;
  - a medida da distância e a checagem nova;
  - o antes e depois da Parte B;
  - a saída dos testes e os commits.
- Se algo do contexto não bater com o repositório, pare e registre no relatório.
