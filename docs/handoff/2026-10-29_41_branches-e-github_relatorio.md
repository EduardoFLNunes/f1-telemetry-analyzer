# Relatório do pedido 41: branches e GitHub

- **Pedido:** `docs/prompts/2026-10-29_41_branches-e-github.md`.
- **Branch da pasta:** `etapa/m1-modelo-do-carro` (não troquei). Nenhum commit e nenhum merge. O pedido manda deixar o relatório e o CSV sem commit; a próxima sessão de implementação commita.
- **Envios** (depois do seu ok, em 29/10 01:16, para "enviar público"), todos sem forçar:
  - `develop` `b1dc2502..770881b8`;
  - `etapa/modelo2-erro-tecnica-e-estilo` `4de43780` (nova);
  - as 14 tags (novas).
- **Arquivos de handoff gerados:**
  - `docs/handoff/2026-10-29_41_branches-e-github_relatorio.md` (este);
  - `docs/handoff/2026-10-29_41_branches-e-github_inventario.csv` (61 linhas: 41 branches locais, 4 só remotas, 14 tags e o stash).

## Resumo

`EduardoFLNunes/f1-telemetry-analyzer` está **público** no GitHub. A Parte A, item 2, manda parar antes de qualquer envio nesse caso, e eu parei. As Partes A, B e D foram feitas antes, porque só leem.

As conferências deram limpo: nenhum arquivo acima de 50 MB, nenhum segredo e nenhuma gravação no histórico das refs locais.

**Na segunda etapa,** você respondeu "Pode enviar público". Fiz os envios da Parte C sem forçar nada e conferi cada ref com `git ls-remote origin`: todas têm o mesmo hash da local. `main` e as quatro remotas antigas não foram tocadas.

## Parte A — Conferências

### A pasta e as sessões
- Ao começar, a sessão do pedido 38 ("Modelo2 erro técnica e estilo") estava **com um turno em andamento**. Esse turno só conferiu os commits `a85d16ad` e `73565e79` (já existentes) e terminou sem mexer no git. Esperei terminar e só comecei depois de ver as duas sessões paradas (`idle`). A sessão do pedido 39 ("Modelo do carro 2026-10-24") e a do pedido 40 estavam paradas.
- Nenhuma trava do git (`.git/*.lock`).
- `status` com `--no-optional-locks`. Árvore de trabalho intacta; o único arquivo fora do git é o próprio pedido 41.

### A visibilidade do repositório
- O `gh` **não está instalado**. Não instalei.
- Conferi pela API pública do GitHub, sem login: `curl https://api.github.com/repos/EduardoFLNunes/f1-telemetry-analyzer`. Resposta 200, com `"private": false` e `"visibility": "public"`. Um repositório privado responderia 404 sem login, então o resultado não deixa dúvida.
- **Isso quer dizer que `etapa/m1-modelo-do-carro`, enviada em 28/10, já está pública.** Ela carrega quase todo o histórico de `develop` (só 15 commits de `develop` não estão nela): pedidos, ADRs, handoffs e código até o pedido 39.

### A autenticação
- `git fetch origin --prune` e `git ls-remote origin` funcionaram com a credencial que o git já tem, sem pedir login (`GIT_TERMINAL_PROMPT=0`). Nenhum token ou senha foi digitado ou gravado.
- O `fetch` não removeu nenhuma ref; as remotas são as do contexto do pedido.

### Arquivos grandes (Parte A.5)
- Em todo o histórico das 41 branches locais e das 14 tags (`git rev-list --objects --branches --tags | git cat-file --batch-check`): **nenhum arquivo acima de 50 MB, nem acima de 20 MB.**
- Os maiores são de 6,7 MB (`data/debug/track_edges_interval_raycast_vhe_interlagos.json`) e 5,2 MB (`data/debug/interlagos_consolidated_geometry.json`).
- Já estão no remoto, nas branches antigas de antes do filter-repo, arquivos de 56,8 MB e 50,7 MB (`backup/data/cache/2024/.../position_data.ff1pkl` e `car_data.ff1pkl`). Ficam abaixo de 100 MB e já foram aceitos; nenhum envio da Parte C os inclui.

### Segredos (Parte A.6)
- **Padrões fortes** (`ghp_`, `github_pat_`, `sk-`, `AKIA`, `BEGIN … PRIVATE KEY`):
  - nas pontas das refs locais (`git grep`) e em **todo o histórico** delas (`git log -p`): **nada**;
  - nas branches antigas já públicas, só falsos positivos: o texto `asterisk-…` (identificadores de licença dentro de um `.venv` que entrou no `master` antigo) e o `cacert.pem` público do pip.
- **Palavras** `api_key`, `apikey`, `secret`, `password`, `senha`: nenhum arquivo.
- **`token`:** aparece em 16 arquivos. Nas atribuições, é sempre token de cor do tema (`contraste.ts`, `GuiaVisual.tsx`, o JSON de contraste do pedido 29) ou variável de laço sobre palavras (`for token in ("heading", "pitch", …)` em `ac_shared_memory_full_inventory.py` e afins). Nenhum é credencial.
- **Arquivos `.env`:** só `frontend/.env.local`, e só em 4 tags `archive/*` (não está em nenhuma branch). Tem uma única linha, `VITE_MIRROR_MAP_X`, um ajuste de espelhamento do mapa com um valor de 4 letras minúsculas. Não é segredo. O valor não foi copiado para cá.

### Gravações (Parte A.7)
- Em todo o histórico das refs locais, nenhum caminho em `recordings/`, `data/recordings/` ou `data/ml/`.
- De `versoes/`, só o `versoes/LEIA-ME.md`.

## Parte B — Inventário (resumo do CSV)

### `develop` e `main` contra o remoto
| ref | local | remota | ancestral comum | estado |
|---|---|---|---|---|
| `develop` | `770881b8` (28/10, pedido 40) | `b1dc2502` (25/08) | `b1dc2502` | **à frente, 250 commits, avanço simples** |
| `main` | `44f6d9d0` (20/06) | `dd9ba8d0` (25/08) | `5fdadf60` | **divergente: 1 à frente, 68 atrás** |

- **O filter-repo** rodou em 07/08 (`.git/filter-repo`) e reescreveu `develop`, `main`, as 2 `feature/*` e 8 tags. Ele tirou caches do FastF1, bancos `duckdb`, `parquet`, logs em `outputs/` e a pasta `backup/`. O `origin/develop` e o `origin/main` de hoje já são do histórico reescrito. Por isso `develop` é avanço simples.
- **`main` local não tem conteúdo próprio.** O único commit dela fora de `develop` e de `origin/main` é o merge `44f6d9d0`, "Merge Phase 15.1 runtime sampling diagnostics into main", e a árvore dele é idêntica à do pai `5fdadf60`. O app nela é o `0.1.5-phase-14-2-shared-memory-gate`.
- **`origin/main` está inteira dentro de `develop`** (0 commits fora). Ela chega a 25/08, com o app `0.1.7-phase-16`; a última versão com nome de entrega nela é "Release Phase 15.1 desktop package" (`c62019f7`, 25/06). Hoje `develop` está em `0.4.0-redesenho` (com o app do jogo 0.4.1), e o pedido 38 em `0.5.0-radio-e-replay`.

### As branches locais
- **37 `etapa/*` e as 2 `feature/*` estão contidas em `develop`.** Isso inclui `etapa/limpeza-e-app-do-jogo`, do pedido 40, já com merge. Nenhuma está no remoto.
- **Fora de `develop`, só as dos pedidos em andamento:**
  - `etapa/modelo2-erro-tecnica-e-estilo` (pedido 38): 16 commits, ponta `4de43780`. Não está no remoto;
  - `etapa/m1-modelo-do-carro` (pedido 39): 17 commits, ponta `73565e79`. Está no remoto, **igual**.

  As duas ficam.

### As branches que só existem no remoto
Nenhuma tem ancestral comum com `develop`. Todas têm commits que `develop` não tem, mas de outro histórico:
| remota | ponta | commits | o que é |
|---|---|---|---|
| `telemetria-ai` | `eaecc36c` (20/04) | 20 | o começo do TCC, de 22/03 a 20/04 |
| `master` | `9e492e93` (24/04) | 4 | a "versão 0.2 com interface web e IA de raceline"; o 1º commit trouxe um `.venv` inteiro |
| `feat/analise-comparativa` | `a8c0a64f` (02/06) | 11 | o histórico **de antes do filter-repo** (raiz `8e349b02`). A tag local `archive/feat-analise-comparativa` é a versão reescrita, e vai mais longe (até 05/06) |
| `recovery/restore-pre-cache-rollback` | `bafe1f70` (21/05) | 9 | também de antes do filter-repo. A tag local `archive/recovery-restore-pre-cache-rollback` é a versão reescrita, com a mesma mensagem no topo |

- O remoto tem ainda `refs/pull/1/head` (`121bbd38`) e `refs/pull/2/head` (`35a0befa`), de dois pull requests antigos de `feat/analise-comparativa`. **Essas refs não podem ser apagadas por você nem por mim; só o suporte do GitHub apaga.** Elas mantêm público o histórico de antes do filter-repo mesmo que a branch seja apagada.

### O stash e as tags
- **`stash@{0}`** (19/08): "Organização das 3 visões (descartada; refeita na sessão do mapa)". Mexe em 10 arquivos do frontend (`App.css`, `Dashboard.tsx`, painéis e `TrackRenderer.tsx`). A base dele está em `develop`. O próprio nome diz que foi descartado e refeito. Stash não vai ao remoto.
- **Nenhuma das 14 tags está no remoto.**
  - **Contidas em `develop` (8):** as 6 `handoff/*`, `backup/raceline-codex-integracao-20260613` e `v0.1.2-phase-12-laps`.
  - **Fora de `develop` (6, todas `archive/*`, de experimentos de maio e junho):** `backup-pitlane-experiments-before-main-rollback` (6 commits), `codex-pitlane-v2-safety-20260521-0115` (3), `feat-analise-comparativa` (2), `feature-kn5-track-geometry-provider` (1), `feature-phase-14-real-session-audit` (1) e `recovery-restore-pre-cache-rollback` (5). Quatro delas têm o `frontend/.env.local` inofensivo.

## Parte C — Envios

Na primeira etapa, não enviei nada, porque o repositório é público. Os envios foram feitos depois do seu "Pode enviar público".

### Antes de enviar
- As três sessões dos pedidos 38, 39 e 40 estavam paradas (`idle`), e não havia trava do git.
- Um novo `git fetch origin --prune` confirmou que `origin/develop` continuava em `b1dc2502`, ancestral de `develop`, e que o remoto não tinha nenhuma tag.

### O que foi enviado
Comandos: `git push origin refs/heads/develop:… refs/heads/etapa/modelo2-erro-tecnica-e-estilo:…` e depois `git push origin refs/tags/<cada tag>:…`. Nenhum usou `--force` nem `--force-with-lease`; o git recusaria sozinho um envio que não fosse avanço. Nenhum dos dois configurou upstream (sem `-u`).

Conferido com `git ls-remote origin` depois do envio. Nas tags anotadas, o hash é o do objeto da tag, nos dois lados.

| ref | hash local | hash no remoto depois | como foi |
|---|---|---|---|
| `refs/heads/develop` | `770881b8` | `770881b8` | avanço `b1dc2502..770881b8` |
| `refs/heads/etapa/modelo2-erro-tecnica-e-estilo` | `4de43780` | `4de43780` | branch nova |
| `refs/heads/etapa/m1-modelo-do-carro` | `73565e79` | `73565e79` | já estava igual; não reenviada |
| `refs/tags/archive/backup-pitlane-experiments-before-main-rollback` | `3998d582` | `3998d582` | tag nova |
| `refs/tags/archive/codex-pitlane-v2-safety-20260521-0115` | `46b1f172` | `46b1f172` | tag nova |
| `refs/tags/archive/feat-analise-comparativa` | `7634f9ca` | `7634f9ca` | tag nova |
| `refs/tags/archive/feature-kn5-track-geometry-provider` | `c5294f1e` | `c5294f1e` | tag nova |
| `refs/tags/archive/feature-phase-14-real-session-audit` | `66c21f5b` | `66c21f5b` | tag nova |
| `refs/tags/archive/recovery-restore-pre-cache-rollback` | `eff99a6e` | `eff99a6e` | tag nova |
| `refs/tags/backup/raceline-codex-integracao-20260613` | `13243539` | `13243539` | tag nova |
| `refs/tags/handoff/coach-aprendizado` | `83b0ab88` | `83b0ab88` | tag nova |
| `refs/tags/handoff/coach-mapeamento` | `75fea2a7` | `75fea2a7` | tag nova |
| `refs/tags/handoff/coach-referencia-real` | `75d19705` | `75d19705` | tag nova |
| `refs/tags/handoff/fase1` | `8a4b8d97` | `8a4b8d97` | tag nova |
| `refs/tags/handoff/fase2b` | `e3ffd2f8` | `e3ffd2f8` | tag nova |
| `refs/tags/handoff/fase2c-ferramentas` | `b5ef1225` | `b5ef1225` | tag nova |
| `refs/tags/v0.1.2-phase-12-laps` | `d94fe98b` | `d94fe98b` | tag nova |

O remoto agora tem 36 refs: as 8 branches, as 14 tags (mais as linhas `^{}` das anotadas), o `HEAD` e os 2 `refs/pull`.

### O que não foi enviado
- **As 39 branches locais já contidas em `develop`** (37 `etapa/*`, 2 `feature/*`): o conteúdo delas foi junto com `develop`.
- **`main`:** diverge de `origin/main`, e o único commit próprio dela não tem conteúdo. Enviar exigiria forçar, o que o pedido proíbe. Veja a Parte D.

## Parte D — Propostas (nada executado)

### 0. A visibilidade (decidida: você mandou enviar com o repositório público)
- **a) Tornar o repositório privado** (GitHub, Settings → General → Danger Zone → Change visibility; você faz). Depois disso, os envios da tabela acima podem ser feitos como o pedido aprovou.
  - Risco: nenhum para o código.
  - O que já foi público pode ter sido copiado ou indexado nesse tempo: a branch do pedido 39 e as branches antigas.
- **b) Manter público e enviar mesmo assim.** Precisa do seu ok explícito, porque o pedido manda parar.
  - Risco: tudo que for enviado fica público, inclusive os pedidos, handoffs e relatórios em `docs/`. As conferências não acharam segredo nem gravação.

### 1. As branches locais já contidas em `develop` (37 `etapa/*` e 2 `feature/*`)
- **Proposta:** apagar com `git branch -d`, que recusa apagar o que não está em `develop`.
- **Motivo:** o conteúdo inteiro delas está em `develop`. Os nomes servem só como marcador de onde cada pedido terminou.
- **Risco:** baixo. Se quiser guardar os marcadores, crio antes uma tag `etapa/<nome>` para cada uma.
- **Deixar fora por agora:** `etapa/limpeza-e-app-do-jogo`, até a sessão do pedido 40 ser arquivada.

### 2. As branches remotas antigas
| remota | proposta | motivo | risco |
|---|---|---|---|
| `telemetria-ai`, `master` | guardar como tag local (`archive/telemetria-ai`, `archive/master`) e depois decidir se apaga no remoto | é o começo do projeto, sem nada local equivalente | apagar no remoto sem a tag local perde esse histórico. Com a tag, nada se perde |
| `feat/analise-comparativa`, `recovery/restore-pre-cache-rollback` | apagar no remoto (só com seu ok) | já há versões reescritas nas tags `archive/*`, e a de `feat/analise-comparativa` vai até mais longe | quase nenhum para o conteúdo. **Mas o histórico antigo continua acessível pelos `refs/pull/1` e `refs/pull/2`**, que só o suporte do GitHub remove |
| as quatro | deixar como estão | se o repositório ficar privado, elas não atrapalham | confusão de nomes; ficam fora de qualquer envio |

### 3. Se `develop` ou `main` divergirem do remoto
- **`develop`** não diverge: é um avanço simples. Nada a fazer além de enviar.
- **`main`** diverge. Caminhos:
  - **a) Recomendado:** guardar a `main` local numa tag (`archive/main-local-2026-06-20`, em `44f6d9d0`). Depois apontar a `main` local para `origin/main`, ou direto para `develop` (item 5).
    - Perde-se só o merge `44f6d9d0`, que fica na tag e não tem conteúdo.
    - **Nada se reescreve no remoto,** porque `origin/main` é ancestral de `develop`.
  - **b) Deixar a `main` local como está** e nunca enviá-la.
    - Não perde nada, mas a `main` local fica parada em 20/06 e confunde.
  - **c) Enviar a `main` local à força.** Não recomendo.
    - Apaga do remoto os 68 commits de `origin/main`. Eles estão em `develop`, mas `main` no GitHub voltaria a junho.

### 4. O `stash@{0}`
- **Proposta:** apagar (`git stash drop`).
  - Motivo: a mensagem diz que foi descartado e refeito na sessão do mapa, e a base dele já está em `develop`.
  - Risco: baixo.
- **Alternativa sem risco:** guardar antes como tag (`archive/stash-organizacao-3-visoes`, em `872e4bba`) e depois apagar.

### 5. O que fazer com `main`
- **Proposta:** quando o pedido 38 (0.5.0) entrar em `develop`, levar `main` ao commit desse merge.
  - **No remoto, é um avanço simples:** `origin/main` (`dd9ba8d0`) está dentro de `develop`. Basta `git push origin <commit>:main`, sem forçar.
  - **Na `main` local,** vale o item 3a: a tag primeiro, e depois mover a branch para o mesmo commit.
- Daí em diante, `main` recebe só versões entregues (0.5.0, 0.6.0…), sempre por avanço a partir de `develop`.
- Isso é reescrever a ref local `main` (de `44f6d9d0` para outro commit), então fica para o seu ok.

## O que falta e o que precisa da sua decisão
1. ~~A visibilidade~~: decidida (público), e os envios da Parte C estão feitos e conferidos.
2. As propostas de D1 a D5. Nenhuma foi executada.
3. O commit deste relatório e do CSV, pela próxima sessão de implementação (o pedido manda deixar sem commit). Atenção: a branch do pedido 38 já está no remoto; os próximos commits dela também podem ir por avanço simples.
