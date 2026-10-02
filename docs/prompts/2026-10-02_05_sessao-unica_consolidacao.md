Eduardo aqui. Este pedido foi escrito junto com o Claude (Cowork), que faz a revisão e a arquitetura do projeto, e eu aprovo. O plano é meu. Pode executar.

A partir de hoje existe uma única sessão de implementação: você, na pasta principal. A outra sessão foi encerrada e não vai mais mexer no repositório. Leia o novo `docs/decisoes/0008-uma-sessao-de-implementacao.md` antes de começar. Os pedidos anteriores (Parte A, Parte B e o sinal de integração) ficam substituídos por este.

Eu autorizo você a trazer para `develop` o trabalho que ficou na worktree `.claude/worktrees/elastic-kepler-a8182e`. Esse trabalho já foi revisado pelo Claude (Cowork). Faça isso pelo patch, sem commitar nada dentro da worktree.

## Passos

1. **Estado inicial.** Mande a saída de `git status`, `git log --oneline -3` e `git stash list`. Se houver stash, diga o que ele contém (`git stash show --stat`), mas não aplique nem apague.

2. **ADRs.** Commite a pasta `docs/decisoes/` (ADRs 0001 a 0008 e o índice) em `develop`, com a mensagem `docs: registro de decisoes (ADR 0001-0008)`.

3. **Correção do coach**, numa branch `etapa/coach-mapeamento` criada a partir de `develop`:
   - rode `git apply --check` e depois `git apply` com `.claude/worktrees/elastic-kepler-a8182e/docs/handoff/2026-09-30_coach_mapeamento.patch`;
   - confira com `diff` que `backend/ml/export/coaching.py` e `backend/tests/test_ml_export.py` ficaram idênticos aos da worktree;
   - copie para `docs/handoff/` os outros três arquivos dessa pasta da worktree: o próprio `.patch`, o `_pytest.txt` e o `_resultados.json`;
   - crie um `.gitattributes` com a linha `*.patch binary`;
   - rode a suíte completa com pytest;
   - commite com a mensagem `Coach: alvos no eixo de progresso do runtime e na grade do ML`.

4. **Integração.** Se a suíte passar, faça `git merge --no-ff etapa/coach-mapeamento` em `develop`.

5. **optimal.json.** Faça backup de `data/reference_models/vhe_interlagos.optimal.json`. Regrave o arquivo com o novo mapeamento e confira que o tempo de volta continua 85,109 s. Registre o hash do arquivo antigo e do novo.

6. **Tag.** Crie a tag `handoff/coach-mapeamento` no merge.

7. **Pare e mande o relatório:**
   - `git log --oneline -6`, `git status` e o resultado do pytest;
   - os hashes do `optimal.json`;
   - o resultado do `diff` do passo 3.

## Não faça ainda

- Não remova a worktree nem as branches `fix/coach-mapeamento-s` e `claude/elastic-kepler-a8182e`. Isso será feito no próximo pedido, depois da conferência.
- Não comece a Fase 2b.
- Não envie nada ao repositório remoto.
- Não contorne nenhuma trava: se algo bloquear, pare e me avise.
