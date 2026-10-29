# Pedido 44 — O corredor pela borda da superfície e o retreino da LSTM geradora com as três fontes

**De:** Eduardo. **Data:** 29/10/2026.
**Tipo:** Modelo 1 (`backend/ml/`), dois ADRs novos, documentação e testes. O coach, o rádio, o app, o store v2, o Modelo 2 e a M1 não mudam.

**Quando começar:** quando a pasta estiver livre, na ordem que eu mandar. Este pedido não depende dos pedidos 38, 39, 42 e 43. Antes de criar a branch, confira que nenhuma outra sessão está ativa na pasta (ADR 0008).

**Ao mandar executar este pedido, eu aprovo** os dois ADRs da Parte A como estão escritos aqui.

## Contexto

1. **O pedido 27 comparou o corredor do ML com a pintura e com o sinal do jogo** (`docs/handoff/2026-10-10_27_corredor-x-pintura_relatorio.md`):
   - o corredor passa da pintura em 20,6% da volta à esquerda e 46,3% à direita;
   - contra o sinal de pneus fora do jogo, ele é "estreito demais" em 15.338 amostras e "largo demais" em 548;
   - **a opção 3** (a borda da superfície do cache: asfalto, zebra e pintura) é a que mais se aproxima do jogo: 6.764 e 411;
   - **a separação proposta:** o `geometry_id` continua cobrindo a linha central, as normais e a grade (de onde saem o `s` e o `lateral`), e um `corridor_id` à parte cobre as larguras. Assim, só o que depende das larguras é refeito;
   - **um risco de hoje:** `CAR_HALF_WIDTH_M` e `KERB_ALLOWANCE_M` não entram em nenhuma impressão digital.
2. **A minha decisão (29/10):** a opção 3, com o `corridor_id` separado.
3. **O ADR 0018** manda retreinar a LSTM geradora com três fontes e testar na régua do ADR 0006:
   - as voltas `humano` com equipamento `atual` (ADR 0015);
   - as voltas `ia` rotuladas pelo indicador do jogo ou por anotação, nunca pelo detector (ADR 0014 e o esclarecimento do 0018);
   - o traçado de referência da F1 na época 2023–25, só a posição (ADR 0019).
4. **A LSTM de hoje** (`data/ml/models/reference/`, de 24/08) é de antes da regravação do cache e de antes das sessões do equipamento atual. Na auditoria (`docs/auditoria_ml.md`, seção 3), ela erra 0,528 m de lateral nas voltas abaixo de 88 s e 2,898 m nas acima.
5. **O ADR 0019, item 6:** se a F1 ajuda o Modelo 1, só o retreino com e sem ela dirá, na mesma régua.
6. **A nova busca evolutiva** com a M1 como juiz não entra aqui: ela espera a M1 aprovada.

## Parte A — Registrar antes de rodar (dois ADRs)

Use os próximos números livres em `docs/decisoes/` (devem ser 0025 e 0026) e a linha de cada um no índice. Commite a Parte A antes de qualquer outra.

### ADR do corredor: a borda da superfície e o `corridor_id`

- **A borda do corredor** é a borda da superfície do cache (asfalto, zebra e pintura) de cada lado, pela regra da opção 3 do pedido 27. Onde ela faltar (1 ponto à esquerda), fica a borda de hoje.
- **O corredor útil** continua sendo a largura menos (`CAR_HALF_WIDTH_M` − `KERB_ALLOWANCE_M`).
- **O `corridor_id`** é a impressão digital das larguras, de `CAR_HALF_WIDTH_M`, de `KERB_ALLOWANCE_M` e do `geometry_id` em que elas valem.
- **O `geometry_id` não muda:** o `s`, o `lateral`, o store, o inventário e o coach ficam como estão.
- **Toda saída que depende das larguras** registra o `corridor_id` (o ADR 0007 vale para ele como para o `geometry_id`).
- **Emenda o ADR 0002:** uma linha de atualização nele.

### ADR do retreino da LSTM geradora: a régua e os critérios

O ADR 0006 foi escrito para estimadores de diferença de tempo. Para a geradora, ele fica assim:

- **A divisão:** deixar uma sessão inteira de fora a cada rodada, entre as sessões com voltas `humano` do equipamento atual ou voltas `ia` rotuladas. Tudo que é ajustado (pesos, normalização, parada) usa só as outras sessões.
- **A tarefa testada:** a geradora recebe a pista e as perdas da própria volta deixada de fora (o condicionamento de hoje), e devolve a lateral.
- **A métrica principal:** o erro absoluto médio da lateral, em metros, na grade oficial.
- **A referência ingênua:** a lateral mediana das voltas de treino, ponto a ponto. Skill = 1 − erro do modelo ÷ erro da referência.
- **Relatar também:** o erro de velocidade, freio e acelerador; o skill por sessão; por ritmo (abaixo e acima de 88 s, como na auditoria); e por fonte (minhas voltas e voltas da IA).
- **Critérios fixados antes de rodar.** Para aprovar, todos precisam ser atendidos:
  - skill ≥ 0,20;
  - limite inferior do IC 95% do skill > 0 (bootstrap agrupado por sessão);
  - pelo menos 70% das sessões com skill positivo;
  - pelo menos 5 sessões testáveis.
- **A entrada da F1** e o tratamento dos microssetores pouco confiáveis (Parte D.4) ficam escritos neste ADR antes de rodar.
- **Com e sem a F1:** as duas versões passam pela mesma régua. **A F1 fica no modelo final só se** o skill com ela for maior que sem ela, com o limite inferior do IC 95% da diferença (bootstrap pareado por sessão) acima de 0. Senão, o modelo final é o sem a F1, e o resultado é registrado.
- **A LSTM substituta** é retreinada com os atributos do corredor novo e relatada (erro por passo e por volta, deixando uma sessão de fora), sem critério de aprovação: o papel dela na aptidão é decidido no pedido da nova busca.
- **Um resultado negativo é aceito e registrado,** como mandam os ADRs 0006 e 0022.

## Parte B — O corredor novo

1. **Antes de mudar, liste quem lê as larguras,** como na Parte A do pedido 27, incluindo o que entrou depois dele (o Modelo 2, a M1, o rádio e o app). **Se algum uso fora do Modelo 1** (o coach, o Modelo 2, a M1, o rádio, o app ou a tela Volta) passar a mudar de comportamento, pare e me pergunte antes.
2. **Construa as bordas novas** (`core/geometry/`) e o `corridor_id` (`backend/ml/track/geometry.py`).
3. **Confira:**
   - o `geometry_id` continua `0ed16f0dd2225990`;
   - o `s` e o `lateral` de uma sessão continuam iguais, ponto a ponto;
   - o coach não fica em silêncio (ele só confere o `geometry_id`);
   - contra o sinal do jogo, o "estreito demais" e o "largo demais" repetem os 6.764 e 411 do pedido 27 (ou o relatório explica a diferença);
   - o degrau de 1,64 m no fechamento do laço, à direita, e os de até 0,81 m: diga se continuam e de onde vêm;
   - a figura dos 8 trechos do pedido 27, com as bordas novas.
4. **Guarde antes** os artefatos que vão ser regravados (ADR 0007), como em `data/ml/_backup_pre_fase1/`.

## Parte C — O que depende do corredor

1. **O critério da F1** (o excesso sobre o corredor no alinhamento e em cada volta da faixa): rode de novo e relate quantas voltas mudam de aceita para recusada, e o contrário.
2. **A métrica `outside_corridor_fraction`:** recalculada.
3. **O evolutivo não roda aqui.** O `optimised_lateral.npy` de 24/08 fica guardado como está, marcado como de outra geometria.

## Parte D — Os dados do retreino

1. **As voltas:** as das três fontes do contexto (item 3), com a contagem por fonte e por sessão. As voltas antigas de origem `desconhecida` ficam fora (esclarecimento do ADR 0018).
2. **As sessões fora do store v2** (por exemplo, as de 24/10 e as da IA em níveis, se já existirem): entram lidas com as funções do store, sem gravar nele, marcadas `fora_do_store`, como o pedido 38 fez.
3. **O fora de pista:** confira se alguma sessão do treino depende do `off_track = False` que o leitor põe quando o campo falta (`backend/ml/data/samples.py`, ponto 3 das decisões do pedido 27). Se depender, trate o fora de pista dela como desconhecido e relate.
4. **A F1:** só a posição, nunca velocidade, pedal ou ponto de frenagem. Registre no ADR da Parte A, antes de rodar:
   - como a linha entra no treino (por exemplo, só a lateral como alvo, com os outros canais fora da perda, e com que condicionamento);
   - o que fazer nos microssetores marcados como "faixa pouco confiável" (MS04 a MS09, MS19 e MS46 a MS48).

   O erro de alinhamento da F1 à geometria oficial fica registrado.
5. **O tempo:** estime quanto leva o treino completo (todas as rodadas, com e sem a F1, e a substituta). Se passar de 6 horas, pare e proponha como reduzir, sem mudar os critérios.

## Parte E — O retreino e a régua

1. **Rode as rodadas** deixando uma sessão de fora, com e sem a F1.
2. **Relate a tabela dos critérios** do ADR da Parte A, com o veredito de cada um, e o veredito final.
3. **O modelo final** (o que a Parte A manda) é treinado em todas as sessões e salvo com o `corridor_id`, o commit e os hashes dos dados (ADR 0007).
4. **As conferências da linha de referência** (a geradora consultada com perda 0):
   - nenhum ponto fora do corredor útil novo antes do corte;
   - a resposta com perda 0 e com perda 0,5 s, como na `docs/arquitetura_ml.md` (Figura 4): a velocidade mediana e o quanto a linha se desloca;
   - a distância, por microssetor, entre a linha nova, a da IA do coach, a minha melhor volta e a da F1.
5. **Testes:** as bordas novas e o `corridor_id` (um caso sintético em que mudar `CAR_HALF_WIDTH_M` muda o `corridor_id` e não muda o `geometry_id`), a divisão por sessão sem vazamento e a entrada da F1 sem velocidade nem pedal. A suíte do backend continua passando.

## Parte F — Documentação

- **Os dois ADRs** (Parte A) e as linhas de atualização nos ADRs 0002, 0018 e 0019.
- **`docs/arquitetura_ml.md`:** o corredor novo e as fontes da geradora.
- **`backend/ml/README.md`:** os resultados medidos e as limitações.
- **`docs/auditoria_ml.md`:** uma nota na seção 3 apontando para o resultado novo, sem apagar o antigo.

## Regras gerais

- **O coach, o rádio, o app, o store v2, o Modelo 2 e a M1 não mudam.** Se a Parte B mostrar que algum deles mudaria, pare e me pergunte.
- **Nenhum critério muda depois de ver os números.** Os ADRs da Parte A são commitados antes de rodar.
- **As gravações só são lidas.** Não apague nem mova nenhuma, e não copie gravações entre a pasta do app instalado e a do repositório.
- **O `data.acd` nunca é aberto.**
- **Não instale nem atualize pacotes.** Se algo pedir pacote novo, pare e relate.
- **Não contorne nenhuma trava:** se algo parar, pare também e registre o motivo.
- **Branch e commits:** branch `etapa/corredor-e-retreino-lstm`, a partir de `develop`, commits por parte, merge em `develop`. As branches de outros pedidos não são tocadas.
- **Cópia no GitHub (vale para todo pedido):**
  - depois dos commits de cada parte e antes de cada parada, envie a branch do pedido ao `origin`; depois do merge, envie `develop`;
  - só envios que não reescrevem o remoto (branch nova ou avanço simples). Nunca `--force` nem `--force-with-lease`;
  - `main` e as tags não vão neste pedido;
  - antes do primeiro envio, confira que nada acima de 50 MB, nenhum segredo e nenhuma gravação (`recordings/`, `data/recordings`, `data/ml`) entrou nos commits. Os modelos treinados ficam em `data/ml`, fora do git;
  - depois de cada envio, confira com `git ls-remote origin` que o hash remoto é o mesmo do local;
  - se pedir login, se o envio for recusado ou se o remoto tiver divergido, pare e me avise. Nenhum token ou senha no chat, nos arquivos ou no relatório.
- **Uma sessão de implementação por vez** (ADR 0008). Antes de trocar de branch, confira se outra sessão está ativa.
- **Os tempos de volta** no formato M:SS,mmm.
- **Relatório** em `docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_relatorio.md`, como manda o CLAUDE.md, com:
  - os dois ADRs e o commit em que foram registrados;
  - a lista de quem lê as larguras e o que mudou em cada um;
  - as conferências da Parte B;
  - a Parte C;
  - os dados do treino, por fonte e por sessão;
  - a tabela dos critérios, com e sem a F1, e o veredito;
  - as conferências da linha de referência;
  - a saída dos testes e os commits;
  - o que foi enviado ao GitHub: a ref, o hash local e o hash no remoto.
- Se algo do contexto não bater com o repositório, pare e registre no relatório.
