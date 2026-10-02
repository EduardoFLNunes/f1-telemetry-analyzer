Eduardo aqui. Este pedido foi escrito junto com o Claude (Cowork), que faz a revisão e a arquitetura do projeto, e eu aprovo. O plano é meu. Pode executar.

Você fez certo em parar: a condição era diferente da que eu tinha autorizado. As três respostas estão abaixo.

## 1. Limpeza

1. **Worktree:** autorizado `git worktree remove --force .claude/worktrees/elastic-kepler-a8182e`. Você já conferiu que os 6 arquivos alterados ou não rastreados estão em `develop` (5 idênticos e 1 diferente só no CR). As cópias de `data/` e o `settings.local.json` daquela worktree podem ir embora.
2. **Branch `fix/coach-mapeamento-s`:** depois que a worktree sair, apague com `git branch -d`.
3. **Branch `claude/elastic-kepler-a8182e`:** o commit `44f6d9d0` continua guardado na branch `main` local, então apagar essa branch não perde nada. Apague com `git branch -D claude/elastic-kepler-a8182e`. Depois rode de novo `git branch -a --contains 44f6d9d0` e confirme que `main` ainda aparece.
4. Mande a saída de `git worktree list` e `git branch -a`.

## 2. scikit-learn

Opção (a) aprovada: use uma biblioteca padrão, não código próprio.

1. Instale com `pip install scikit-learn` no `.venv` da raiz e deixe o pip escolher a versão compatível com Python 3.9 e numpy 1.26.3.
2. Fixe a versão instalada em `backend/ml/requirements.txt`, que é a lista do módulo offline. Não coloque em `backend/requirements.txt`, que vai para o executável do app. Escreva uma linha de comentário explicando para que serve (E2, E3 e E4 da Fase 2b).
3. Registre a versão no `resultados.json` da Fase 2b.
4. Rode a suíte completa depois da instalação para confirmar que nada quebrou.

## 3. Fase 2b

Siga a Parte B do pedido `docs/prompts/2026-10-02_06_fechamento-coach-e-fase2b.md`, sem mudanças, na branch `etapa/fase2b-estimador-empirico` criada a partir de `handoff/coach-mapeamento`.

- A mudança no `ml/requirements.txt` entra num commit separado nessa mesma branch, antes do código da Fase 2b.
- No relatório final, comece pela limpeza, depois a instalação (versão instalada e resultado do pytest) e por fim os resultados da Fase 2b.
- Não envie nada ao remoto.
