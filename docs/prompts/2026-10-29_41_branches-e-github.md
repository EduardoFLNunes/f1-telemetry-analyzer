# Pedido 41 — Inventário das branches e cópia do projeto no GitHub

**De:** Eduardo. **Data:** 29/10/2026.
**Tipo:** manutenção do git. Nenhum código, documento de projeto ou regra muda.

**Ao mandar executar este pedido, eu aprovo:**
1. enviar ao GitHub (`origin`, `https://github.com/EduardoFLNunes/f1-telemetry-analyzer.git`) as branches e tags da Parte C, **só quando o envio não reescreve nada no remoto**: uma branch ou tag nova, ou um avanço simples (fast-forward);
2. nada além disso: nenhum push forçado, nenhuma branch apagada (local ou remota), nenhum histórico reescrito. O que precisar disso fica como proposta na Parte D, e eu decido.

**Quando começar:** num chat novo, com as sessões dos pedidos 38 e 39 paradas (sem turno em andamento). Nenhuma outra ferramenta trabalha na pasta enquanto este pedido roda.

## Contexto

1. **O remoto já existe** (`origin`). Até 28/10, ele só tinha código antigo:
   - `develop` em `b1dc250` (25/08) e `main` em `dd9ba8d`;
   - `master`, `telemetria-ai`, `feat/analise-comparativa` e `recovery/restore-pre-cache-rollback`, que não existem como branch local.

   Em 28/10, `etapa/m1-modelo-do-carro` foi enviada (`73565e79`).
2. **No computador:**
   - `develop`, com os pedidos até o 40 (`770881b8`), e `main`;
   - cerca de 37 branches `etapa/*` e 2 `feature/*`;
   - as tags `handoff/*`, `archive/*`, `backup/*` e `v0.1.2-phase-12-laps`;
   - um `stash@{0}`.
3. **Existe `.git/filter-repo`:** o histórico já foi reescrito alguma vez. Pode ser que `develop` e `main` locais não descendam das remotas.
4. **O que nunca vai para o git:** `data/recordings`, `data/ml`, a pasta `recordings/` da raiz e os instaladores em `versoes/` (só o `LEIA-ME.md` é rastreado).
5. **Os pedidos 38 e 39 estão em andamento,** sem merge: `etapa/modelo2-erro-tecnica-e-estilo` e `etapa/m1-modelo-do-carro`.

## Parte A — Conferir antes de enviar (só leitura)

1. **A pasta:**
   - confira que as sessões 38 e 39 estão paradas e que não há trava do git. Uma trava não é apagada sem me perguntar;
   - não troque de branch, não faça commit e não mexa na árvore de trabalho;
   - use `git --no-optional-locks` em `status` e `diff`, para não prender o índice.
2. **A visibilidade do repositório no GitHub:**
   - se o `gh` estiver instalado e autenticado: `gh repo view EduardoFLNunes/f1-telemetry-analyzer --json visibility`;
   - se não estiver, pergunte. Não instale nada;
   - **se o repositório for público, pare antes de qualquer envio** e me diga.
3. **A autenticação:** use a que o git já tem (o Git Credential Manager do Windows). Se pedir login ou token, pare e me avise; eu faço o login. Nenhum token ou senha é digitado no chat nem gravado em arquivo.
4. **Atualize as referências remotas:** `git fetch origin --prune`.
5. **Arquivos grandes:** em todo o histórico das refs da Parte C, liste os arquivos acima de 50 MB (por exemplo, `git rev-list --objects <refs> | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)'`). Acima de 100 MB, o GitHub recusa o envio. Se houver, pare e relate; não reescreva o histórico.
6. **Segredos:** procure, em todas as refs que vão ser enviadas (`git grep` nas refs), chaves de API, tokens e senhas:
   - `api_key`, `apikey`, `token`, `secret`, `password`, `senha`;
   - `ghp_`, `github_pat_`, `sk-`, `AKIA`, `BEGIN` seguido de `PRIVATE KEY`;
   - arquivos `.env`.

   Se achar algo que pareça um segredo de verdade, pare e relate o arquivo e a linha, **sem copiar o valor**.
7. **Gravações:** confirme que nenhum arquivo de `recordings/`, `data/recordings` ou `data/ml` está rastreado em alguma das refs.

## Parte B — Inventário das branches e tags (só leitura)

Grave a tabela em `docs/handoff/2026-10-29_41_branches-e-github_inventario.csv`. Uma linha por branch, local ou remota, com:
- o último commit: data, hash e mensagem;
- se está contida em `develop` (`git branch --merged develop`) ou quantos e quais commits ela tem que `develop` não tem;
- se existe no remoto, e como está a local contra a remota: igual, à frente, atrás, divergente ou sem histórico comum;
- a recomendação: enviar, não precisa (já está em `develop`), guardar como tag, ou apagar (só depois do meu ok).

**Atenção especial a:**
1. `develop` e `main` locais contra `origin/develop` e `origin/main`: têm ancestral comum (`git merge-base`)? Se não tiverem, ou se divergirem, não force: relate.
2. `main` contra `develop`: até onde `main` vai, e qual foi a última versão que entrou nela.
3. as remotas que não existem no computador (`master`, `telemetria-ai`, `feat/analise-comparativa`, `recovery/restore-pre-cache-rollback`): têm algo que `develop` não tem?
4. as branches dos pedidos 38 e 39: em andamento, ficam.
5. o `stash@{0}` e as tags: o que são e se já estão no remoto.

## Parte C — Enviar o que é seguro

1. **Só envios que não reescrevem o remoto:** branch ou tag nova, ou avanço simples. Nunca `--force` nem `--force-with-lease`.
2. **O que enviar:**
   - `develop`, se for um avanço sobre `origin/develop`;
   - `etapa/modelo2-erro-tecnica-e-estilo` e `etapa/m1-modelo-do-carro`, como cópia de segurança do trabalho em andamento;
   - as branches `etapa/*` e `feature/*` que tiverem commits fora de `develop`;
   - as tags.

   As branches já contidas em `develop` não precisam ir: o conteúdo delas vai com `develop`.
3. **`main`:** envie só se for um avanço e se `main` local tiver algo que a remota não tem. Não mova `main` para outro commit.
4. **Depois de enviar:** confira com `git ls-remote origin` que cada ref enviada tem o mesmo hash da local.

## Parte D — Propor, sem executar

Liste, com o motivo e o risco de cada um, para eu decidir:
- as branches locais que podem ser apagadas, porque já estão em `develop`;
- as branches remotas antigas: apagar, guardar como tag ou deixar;
- o caminho, se `develop` ou `main` divergirem do remoto (por exemplo, guardar a remota antiga numa tag e depois enviar a local), com o que se perde em cada opção;
- o `stash@{0}`;
- o que fazer com `main` (por exemplo, levá-la à versão 0.5.0 quando o pedido 38 entrar em `develop`).

## Regras gerais

- **Não instale nem atualize nada.** Se faltar uma ferramenta, pergunte.
- **Não reescreva histórico, não force envio e não apague nada,** local ou remoto.
- **Não troque de branch nem faça commit.** Este pedido, o relatório e o CSV ficam sem commit; a próxima sessão de implementação commita.
- **Nenhum token ou senha** no chat, nos arquivos ou no relatório.
- **Não contorne nenhuma trava:** se algo parar, pare também e registre o motivo.
- **Uma sessão de implementação por vez** (ADR 0008).
- **Relatório** em `docs/handoff/2026-10-29_41_branches-e-github_relatorio.md`, com:
  - a visibilidade do repositório e como foi conferida;
  - as conferências da Parte A (arquivos grandes, segredos, gravações), com o resultado de cada uma;
  - um resumo da tabela da Parte B;
  - o que foi enviado: a ref, o hash local e o hash no remoto depois;
  - o que não foi enviado e por quê;
  - as propostas da Parte D.
