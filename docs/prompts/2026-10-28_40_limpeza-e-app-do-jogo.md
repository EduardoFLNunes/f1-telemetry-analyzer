# Pedido 40 — Limpeza do código sem uso, defeitos do backlog e o app do jogo 0.4.1 em `develop`

**De:** Eduardo. **Data:** 28/10/2026.
**Tipo:** front, backend e app do jogo, sem mudar nenhuma regra. Nada do coach, do store v2, do relatório de evolução, do rádio, da M1 ou do Modelo 2 muda de regra.

**Ao mandar executar este pedido, eu aprovo:**
1. trazer o app do jogo 0.4.1 (`0092ed38`) para `develop`;
2. remover o código, as rotas e os globais que nada usa, pela regra da Parte C;
3. corrigir os defeitos da Parte D, cada um com um teste que mostra o defeito antes e a correção depois.

**Quando começar:** agora, num chat novo. Os pedidos 38 e 39 estão parados, sem merge:
- o 38 (`etapa/modelo2-erro-tecnica-e-estilo`) espera a minha rotulagem;
- o 39 (`etapa/m1-modelo-do-carro`, a branch em que a pasta está) espera a minha sessão de medição.

Eu não mando nada para esses dois chats enquanto este pedido roda.

## Contexto

1. **O app do jogo 0.4.1** traz de volta as janelas salvas fora da tela (teste de 24/10). Ele é o que está instalado no jogo desde 24/10, mas o commit `0092ed38` ("App do jogo 0.4.1") está só em `etapa/radio-unidades-e-replay`. O `tools/csp_app/instalar.ps1` de `develop` instala o 0.4.0 e tiraria essa correção (relatórios dos pedidos 38 e 39).
2. **O código sem uso** está listado em `docs/dashboard_inventario.md`, seção 2.H, e é o item 6 da seção 7 ("Limpeza de componentes, rotas e globais sem uso"):
   - os componentes `CognitiveDashboard`, `GGDiagram`, `SessionTimeline` e `StabilityPanel`;
   - `Dashboard.tsx`, `AnalysisPage.tsx` e os componentes que só eles usavam, sem rota desde o pedido 30;
   - as funções mortas do mapa (`OverlayRenderer.tsx`, `CarRenderer.tsx`);
   - cerca de 30 rotas sem uso (debug, legacy, upload, duplicatas da análise assistida);
   - os globais em `window` usados como canal de dados (`__latestFrame`, `__latestOpponents`, `__telemetryPerf`, `__replayMapDiagnostics`).

   Os números de linha do inventário são de 14/10 e podem ter mudado.
3. **Os defeitos** estão em `docs/backlog.md` e na seção "A conferir na implementação" do inventário da dashboard (lista na Parte D).

## Parte A — Preparar

1. **Antes de trocar de branch:** confira que as sessões dos pedidos 38 e 39 estão paradas, que a árvore está limpa e que não há trava do git. Se uma sessão estiver ativa, pare e me avise. Uma trava do git não é apagada sem me perguntar.
2. **Crie `etapa/limpeza-e-app-do-jogo` a partir de `develop`** e commite este pedido ("docs: pedido 40").
3. **Meça o antes, em `develop`:** a suíte do backend, o `vitest run` e o `tsc --noEmit` do front, o `npm test` do `desktop` e o `tools/csp_app/conferir_lua.py`. Guarde as contagens para o relatório.

## Parte B — O app do jogo 0.4.1 em `develop`

1. **Veja o que a branch traz:** `git log --oneline develop..etapa/radio-unidades-e-replay`.
   - Se for só o `0092ed38` (e documentos), faça o merge de `etapa/radio-unidades-e-replay` na branch deste pedido.
   - Se houver outro commit de código, pare e me mostre a lista.
2. **Confira:** o `manifest.ini` diz `VERSION = 0.4.1`, e o `conferir_lua.py` passa (léxico, blocos, chamadas da API do CSP).
3. **Documente** a versão onde o app do jogo é citado (`docs/realidade_aumentada.md`).
4. **Não rode o `instalar.ps1`** e não escreva na pasta do jogo: o 0.4.1 já está instalado.

## Parte C — O código sem uso

1. **Antes de remover, procure todos os que usam cada item:**
   - o front (`frontend`) e o `desktop`;
   - o app do jogo (`tools/csp_app`), que chama rotas do backend;
   - o backend inteiro, inclusive `ml` e `scripts`;
   - os testes.

   Grave a lista em `docs/handoff/2026-10-28_40_limpeza-e-app-do-jogo_remocoes.csv`, com as colunas: item, onde está, quem usa, decisão.
2. **Remova só o que ninguém usa:**
   - uma rota usada pelo app do jogo, pelo app instalado, por um script ou por um teste fica;
   - um global em `window` que alguém lê fica (trocar o canal é refatoração, fora deste pedido);
   - na dúvida, fica, e entra no relatório.
3. **Teste:**
   - `tsc --noEmit`, `vitest run`, a suíte do backend e o `npm test` do `desktop`;
   - **de ponta a ponta:** o backend do repositório numa porta de teste, com as pastas isoladas no rascunho (como no pedido 36). Abra as 6 telas (Sessões, Ao vivo, Volta, Evolução, Coleta de dados e Sistema) numa janela "[teste]" e confira que não há erro no console. No fim, feche a janela e pare o backend.
4. **Refaça o build do front** (`frontend/dist`), se o app aberto pelo repositório o usa.

## Parte D — Os defeitos do backlog

Para cada um: um teste que mostra o defeito, a correção, e o teste passando. Se a correção mudar uma regra do coach, do store v2, do relatório de evolução ou o formato da gravação, não corrija: pare e relate.

1. **O gravador junta duas passagens numa volta** quando o contador de voltas do jogo volta (a sessão recomeça; pedido 29, achado 1).
   - Corte a volta quando o contador diminuir ou a sessão reiniciar.
   - O teste usa a gravação em que isso aconteceu (relatório do pedido 29) e dados simulados.
   - O formato do arquivo não muda. Vale só para as gravações novas; as antigas não são regravadas.
   - O app instalado (0.5.0) só recebe a correção no instalador final.
2. **A rota das frases do coach** (`/api/analysis/coach/lap/{id}`) só procura a gravação em `data/recordings` (pedido 30, achado 2).
   - Ela passa a achar a gravação também na pasta configurada e na do app instalado, pelo mesmo caminho que o `list_all_sessions` usa, com a mesma regra de nome repetido.
3. **O cache da pista é refeito a cada abertura do backend** (cerca de 36 s; pedido 28, achado 1).
   - Guarde o cache com uma chave do conteúdo de origem e refaça só quando a origem mudar.
   - Meça o tempo de abertura antes e depois.
4. **`backend/test_ws_client.py` falha** quando a suíte roda na pasta `backend` (pedido 30).
   - Tire-o da coleta do pytest sem instalar nada (por exemplo, movendo-o para `tools/`).
   - Confira que a suíte passa rodada de `backend`.
5. **`/api/sessions` e a conferência da Coleta contam as voltas de jeitos diferentes** (13/10: 13 válidas e 1:29,757 contra 9 e 1:29,768; pedido 29, achado 2).
   - Depois da Parte C, liste quem ainda usa cada uma.
   - Se só as telas novas usam `/api/sessions`, alinhe-a à conferência. Se não, relate e não mude.
6. **O `timestamp` do gravador engasga** (+357 ms numa amostra; pedido 14).
   - Só confira e relate quem ainda usa o `timestamp` no lugar do cronômetro do jogo (por exemplo, o cálculo da frequência nos portões).
   - Mude só se um uso estiver errado e um teste mostrar isso.
7. **A conferir, do inventário da dashboard** (seção 2.G e "A conferir na implementação"):
   - o canto inferior direito do mapa lê `latestFrame` durante o replay;
   - `addFrame` altera o store durante o replay;
   - a rota da linha de corrida travava o servidor por 1 a 1,8 s a cada 6 s.

   Confira se cada um ainda acontece. Se sim, corrija com teste; se não, registre como já resolvido.

**Fora deste pedido:**
- o horário 3 h adiantado do gravador (mudaria o nome das pastas de gravação);
- a migração para a geometria única (ADR 0002);
- o `stash@{0}`;
- qualquer mudança de regra.

## Parte E — Documentação

1. **`docs/dashboard_inventario.md`:** "O que o pedido 40 entregou", no fim da seção 7.
2. **`docs/backlog.md`:** não edite (o Cowork mantém). Liste no relatório cada item resolvido, com o commit.
3. **`docs/realidade_aumentada.md`:** a versão 0.4.1 do app do jogo (Parte B).

## Parte F — Merge e devolver a pasta

1. **Com as suítes passando:** merge em `develop`, sem push.
2. **Volte a pasta para `etapa/m1-modelo-do-carro`** (a branch do pedido 39), conferindo antes que nenhuma outra sessão está ativa e que a árvore está limpa. A ferramenta de medição do pedido 39 só existe nessa branch, e eu vou rodar a sessão de medição a partir dela.

## Regras gerais

- **Não instale nem atualize pacotes.** Se algo pedir pacote novo, pare e relate.
- **Não gere instalador.**
- **Não mexa no app instalado nem na pasta do jogo.** O `data.acd` nunca é aberto.
- **As gravações são só lidas.** A mudança do gravador da Parte D vale só para as gravações novas.
- **Não contorne nenhuma trava:** se algo parar, pare também e registre o motivo.
- **Janelas de teste** levam "[teste]" no título e são fechadas no fim.
- **Branch e commits:** `etapa/limpeza-e-app-do-jogo`, criada de `develop`; commits por parte; merge em `develop` no fim; sem push.
- **Uma sessão de implementação por vez** (ADR 0008).
- **Relatório** em `docs/handoff/2026-10-28_40_limpeza-e-app-do-jogo_relatorio.md`, como manda o CLAUDE.md, com:
  - as contagens dos testes antes e depois;
  - o que a Parte B trouxe;
  - a lista das remoções (o CSV) e o que ficou, com o motivo;
  - cada defeito da Parte D, com o teste, o commit e o antes e depois;
  - o tempo de abertura do backend, antes e depois do cache;
  - os commits, o merge e a branch em que a pasta ficou.
- Tempos de volta em M:SS,mmm. Se algo do contexto não bater com o repositório, pare e registre no relatório.
