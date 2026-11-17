# Pedido 54 — A trava do store v2: as sessões aceitas com margem e a causa da linha do jogo

**De:** Eduardo. **Data:** 17/11/2026.
**Tipo:** a checagem da posição da linha do jogo no store v2 (pedido 34), a rodada do store e do relatório de evolução, e uma análise da causa. O coach, o rádio, o app, o engenheiro (pedido 52) e o Modelo 2 não mudam.

**Quando começar:** agora, na pasta `f1-telemetry-analyzer-47`, em paralelo com o pedido 52 (pasta principal, branch `etapa/engenheiro`) e com o pedido 42 (pasta do 48, branch `etapa/modelo2-rodada-2`). A pasta do 47 está livre: o 50 já está em `develop`, e ela ficou na branch `etapa/linha-do-projeto`. O texto deste pedido está na pasta do 47, sem commit. Comece pela Parte 0.

**As duas partes têm pressas diferentes:**

- **a Parte A** reaprova o store com as sessões aceitas com margem. Ela destrava o pedido 42 e o relatório de evolução, e tem uma parada curta antes da rodada (A.5);
- **a Parte B** procura a causa e é só análise. Ela não muda nada.

## Contexto

1. **A trava** (relatório do 51, seção "O construtor rodado (item 2) e a trava do store v2"):
   - a checagem "a linha do jogo fica onde foi medida (pedido 34)" falhou no passo 6 do `atualizar_coach` de 15/11;
   - o store v2 foi regravado com 721 voltas e `aprovado: false` (`data/ml/laps_grid_v2_meta.json`, construído em 15/11, commit `a168e41f`);
   - o passo 7 (o relatório de evolução) não rodou. A tela Evolução mostra o relatório de 22/10, contra a `#0013`, com o rótulo novo "volta de referência". **É um rótulo errado enquanto a trava existir.**
2. **A checagem** (pedido 34): a linha do jogo fica 1,463 m depois do s = 0 da geometria oficial, medida nas gravações, com tolerância de 0,10 m, conferida sessão a sessão. As sessões fora:

   | Sessão | Voltas | Mediana | Desvio |
   |---|---|---|---|
   | `2026-11-01_19-47-03` | 6 | 1,606 m | 0,018 m |
   | `2026-11-07_18-46-00` | 5 | 1,581 m | 0,080 m |
   | `2026-11-12_22-57-03` | 4 | 1,573 m | 0,023 m |

   As outras checagens passam, a do período contra o cronômetro do jogo incluída (mediana de 0,78 ms). A mediana de todas as sessões fica em 1,497 m.
3. **O que mudou perto de 01/11:**
   - as sessões até 24/10 passam, e foram gravadas com o app 0.4.x;
   - a de 01/11 foi gravada com o app 0.5.0, e as de 07/11 e 12/11 com o 0.7.0, todas pelo app do repositório (`data/recordings`, `appPackaged: false`);
   - o CSP 0.3.1 chegou em 01/11;
   - a sessão `2026-11-07_19-52-33` (2 voltas) está no store e não aparece entre as reprovadas;
   - as sessões dos pedidos 47 e 50, na cópia da pista (`vhe_interlagos_teste_m1`), são a IA dirigindo, com muitas voltas, na mesma geometria (`geometry_id` `0ed16f0dd2225990`).
4. **O efeito no tempo:** 0,11 a 0,14 m a mais, na velocidade da reta dos boxes, dá cerca de 2 ms.
5. **O pedido 42 parou na Parte 0:** o carregador do Modelo 2 (`backend/ml/modelo2/dados.py`, `carregar`) recusa o store com `aprovado: false`.
6. **A minha decisão (17/11):** as 3 sessões são aceitas. Como a diferença fica em cerca de 2 ms, ela é tratada como uma margem de erro, para cima e para baixo. O store é reaprovado com essas sessões, e a causa continua sendo procurada (Parte B).

## Parte 0 — A pasta e os dados

1. **A pasta:** confira que nenhuma outra sessão está ativa na pasta do 47 (ADR 0008). **A pasta principal é do pedido 52, e a do 48 é do pedido 42:** nenhum comando que mude a branch ou a área de trabalho delas.
2. **A branch:** crie `etapa/trava-do-store-v2` a partir de `develop`, levando o texto deste pedido, e commite o texto primeiro. Se o git recusar a troca por causa do texto, pare e me avise.
3. **Os dados:** na pasta do 47, `data/ml`, `data/recordings` e `data/cache` já são links. Confira que apontam para a pasta principal.
   - **Este pedido escreve dados:** o store, o meta dele e o relatório de evolução. Eles têm de ficar em `data/` da pasta principal, onde o app os lê, e chegar lá pelos links;
   - para o que faltar na pasta do 47, use o mesmo tipo de link que o pedido 42 usou: junção para uma pasta que não existe, vínculo real para um arquivo numa pasta que já existe. Registre cada link;
   - **cuidado com o vínculo real:** um arquivo regravado como arquivo novo deixa de ser o da pasta principal. Depois de cada escrita, confira pelo SHA-256 que o arquivo da pasta principal é o novo;
   - nada da pasta principal fora de `data/` muda. Se o construtor precisar escrever em outro lugar, pare e me avise.
4. **O jogo:** as contas pesadas só com o `acs.exe` fechado. Confira antes de cada uma.

## Parte A — As sessões aceitas com margem

1. **Registre antes do código,** em `docs/store_v2_e_evolucao.md` (a seção da checagem da linha do jogo, do pedido 34), e numa linha de atualização no ADR que registra as checagens do store v2:
   - a minha decisão de 17/11 (contexto, item 6);
   - **a regra:** uma sessão em que a linha do jogo fica fora da tolerância de 0,10 m, mas em que o efeito no tempo fica em até 2,0 ms em módulo, para cima ou para baixo, é "aceita com margem". O efeito é a diferença de posição dividida pela velocidade na linha, volta a volta. Defina qual número da sessão vale (por exemplo, o p95 das voltas) e registre antes de rodar;
   - **acima de 2,0 ms,** a sessão continua reprovando o store, como hoje;
   - **o que não muda:** os 1,463 m, a tolerância de 0,10 m, a checagem do período e as outras checagens. Nenhuma volta sai do store, e nenhuma gravação muda;
   - **a lista sai da medida, e não de uma lista no código:** as 3 sessões entram porque medem dentro da regra. Uma sessão nova com a mesma diferença entra do mesmo jeito, e uma com diferença maior reprova.
2. **O meta do store:** `aprovado: true` quando cada sessão passa ou é aceita com margem. O meta guarda a lista das sessões aceitas com margem, com a diferença de posição, o efeito em ms e a data da decisão, e a margem de 2,0 ms. Registre o nome das chaves no relatório: o pedido 42 lê essa lista.
3. **O motivo na checagem:** a saída da checagem diz, para cada sessão aceita com margem, a diferença medida e o efeito, como faz hoje quando reprova.
4. **Testes:**
   - uma sessão dentro da tolerância (passa);
   - uma fora da tolerância com efeito de até 2,0 ms (aceita com margem e listada no meta), com a linha antes e depois de 1,463 m;
   - uma com efeito acima de 2,0 ms (reprova);
   - o meta com a lista e a margem.

   A suíte do backend continua passando.
5. **Pare antes da rodada e me avise.** Eu confirmo que o teste do pedido 52 no jogo não está acontecendo, porque a rodada regrava os dados que o app lê.
6. **A rodada,** depois do meu sinal:
   - guarde a cópia de antes, fora do git, como no pedido 26;
   - confirme que o app instalado e o app do repositório estão fechados e que nenhuma sessão está sendo gravada;
   - rode só o que a reaprovação precisa: o store (passo 6) e o relatório de evolução (passo 7). O modelo do coach já foi refeito em 15/11 e não precisa mudar. Se o construtor não permitir rodar só esses passos, pare e me avise antes de rodar tudo.
7. **Relate o antes e o depois:**
   - o meta: `aprovado`, a lista das sessões aceitas com margem, a diferença e o efeito de cada uma;
   - o store: as voltas por origem;
   - **o relatório de evolução:** refeito contra a volta do modelo (ADR 0032), com o rótulo certo, as sessões que entraram e o critério do ADR 0015;
   - a conferência pelo SHA-256 dos arquivos regravados na pasta principal.
8. **O merge da Parte A em `develop` vem logo depois da rodada aprovada,** sem esperar a Parte B, porque qualquer rodada nova do construtor sem a Parte A reprova o store de novo:
   - antes, traga o `develop` para a branch, com merge e sem rebase (o 52 pode ter entrado antes). Se houver conflito fora dos documentos, pare e me avise;
   - depois do merge, a pasta do 47 volta para a branch do pedido e não fica em `develop`, porque a pasta principal vai precisar dele para o merge do 52;
   - avise no relatório parcial que o pedido 42 pode retomar.

## Parte B — A causa (só análise)

1. **A medida, sessão a sessão:** a posição da linha do jogo em todas as sessões de Interlagos, de junho até hoje, com:
   - a data, a versão do app que gravou e o `appPackaged`;
   - a versão do CSP e a do jogo, se a gravação guardar;
   - a pista (a original ou a cópia) e a origem das voltas (eu ou a IA);
   - a mediana, o desvio e o número de voltas.

   Inclua as sessões da cópia da pista (pedidos 47 e 50) e a `2026-11-07_19-52-33`.
2. **As hipóteses, registradas antes das contas,** com o que confirmaria e o que descartaria cada uma:
   - o CSP 0.3.1;
   - o gravador do app 0.5.0 em diante (por exemplo, onde ele lê a troca de volta ou o instante da amostra);
   - uma atualização do jogo ou da pista;
   - a geometria oficial ou o cache da pista;
   - outra que os dados mostrarem.
3. **As evidências:**
   - a data exata da mudança: a última sessão que passa e a primeira que reprova;
   - as amostras em volta da passagem pela linha, numa sessão que passa e numa que reprova: onde o contador de voltas troca e como a posição é interpolada;
   - o histórico do código do gravador entre o 0.4.x e o 0.5.0 (`git log` e `git diff` dos arquivos do gravador);
   - as sessões da cópia da pista, que têm muitas voltas da IA;
   - as gravações do app instalado contra as do app do repositório.
4. **A conclusão:** a causa confirmada, a provável ou "não encontrada", com as evidências. Se houver uma correção (no gravador, uma nova medida dos 1,463 m ou manter a margem), proponha. **A decisão é minha:** nada muda neste pedido além da Parte A.

## Regras gerais

- **O coach, o rádio, o app, o engenheiro (pedido 52) e o Modelo 2 não mudam.** Só a checagem da linha do jogo e o meta do store mudam, na Parte A.
- **Nenhum critério muda além da regra da Parte A.** Os 1,463 m, a tolerância de 0,10 m e as outras checagens ficam como estão. Nenhuma volta sai do store.
- **As gravações só são lidas.** Não apague, não mova e não copie nenhuma.
- **O `data.acd` nunca é aberto, e nada é escrito na pasta do jogo.** Os arquivos da pista só são lidos.
- **Não instale nem atualize pacotes.** Se algo pedir pacote novo, pare e relate.
- **Não gere instalador.**
- **Não contorne nenhuma trava:** se algo parar, pare também e registre o motivo. Uma trava do git não é apagada sem me perguntar.
- **Branch e commits:** branch `etapa/trava-do-store-v2`, a partir de `develop`, na pasta do 47, commits por parte. As branches de outros pedidos não são tocadas.
- **Cópia no GitHub (vale para todo pedido):**
  - depois dos commits de cada parte e antes de cada parada, envie a branch do pedido ao `origin`; depois do merge, envie `develop`;
  - só envios que não reescrevem o remoto (branch nova ou avanço simples). Nunca `--force` nem `--force-with-lease`;
  - `main` e as tags não vão neste pedido;
  - antes do primeiro envio, confira que nada acima de 50 MB, nenhum segredo e nenhuma gravação (`recordings/`, `data/recordings`, `data/ml`) entrou nos commits;
  - depois de cada envio, confira com `git ls-remote origin` que o hash remoto é o mesmo do local;
  - se o controle de permissões da sessão recusar o envio, deixe no relatório os comandos para eu rodar pelo terminal;
  - se pedir login, se o envio for recusado pelo GitHub ou se o remoto tiver divergido, pare e me avise. Nenhum token ou senha no chat, nos arquivos ou no relatório.
- **Uma sessão por pasta** (ADR 0008).
- **Os tempos de volta** no formato M:SS,mmm.
- **Relatório** em `docs/handoff/2026-11-17_54_trava-do-store-v2_relatorio.md`, como manda o CLAUDE.md, com:
  - a Parte 0: os links e a conferência;
  - a regra registrada e o commit em que foi registrada, antes do código;
  - o nome das chaves do meta, para o pedido 42;
  - na parada da A.5: o que está pronto e o que a rodada vai regravar;
  - o antes e o depois da rodada (A.7) e o merge;
  - a Parte B: a tabela por sessão, as hipóteses, as evidências e a conclusão;
  - a saída dos testes e os commits;
  - o que foi enviado ao GitHub: a ref, o hash local e o hash no remoto.
- Se algo do contexto não bater com o repositório, pare e registre no relatório.
