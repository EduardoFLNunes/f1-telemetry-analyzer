Eduardo aqui. Este pedido foi escrito junto com o Claude (Cowork), que faz a revisão e a arquitetura do projeto, e eu aprovo. O plano é meu. Pode executar.

As confirmações sobre o pedido 18 e a correção das janelas da Fase 2b (merge 9c1846b6) estão aprovadas.

## Parte A: relatório em arquivo

A partir de agora, o Claude (Cowork) lê o seu relatório direto no repositório, e eu paro de copiar o texto do chat.

1. Em `develop`, commite o `CLAUDE.md` da raiz, que já está na pasta. Mensagem: `docs: CLAUDE.md com a regra do relatório em arquivo`.
2. Neste pedido e em todos os próximos, siga a regra dele: o relatório completo vai para `docs/handoff/`, com o número do pedido no nome.

## Parte B: estado do repositório

Rode `git status`, `git branch -a`, `git worktree list` e `git stash list`, e confira também `.claude/worktrees/`. Relate se a sessão separada da tarefa "Fix flaky WindowTest" deixou branch, worktree, stash ou commit.

- Não faça merge de nada dela.
- Se houver algo para apagar, relate antes e espere.

## Parte C: tempos de referência do ADR 0016

Os tempos do ADR 0016 (pedido 13) não batem com os oficiais:

| | ADR 0016 | store v2 / coach |
|---|---|---|
| minha melhor | 89,379 s | 89,390 s no store, 89,389 s no jogo |
| volta da IA | 84,816 s | 84,828 s, na referência do coach (03-42-10#0013) |

1. Diga, para cada número, de que volta e de que fonte ele veio: tempo oficial, cronômetro do jogo ou `duration_s`.
2. Procure nos outros documentos, nos JSONs de resultado e no painel algum tempo de volta que tenha vindo do `duration_s`.
3. Monte uma tabela com o número antigo, o oficial, a volta e o arquivo onde ele aparece. Relate antes de mudar qualquer coisa.
4. Se o ADR 0016 estiver errado, a correção entra depois como nota de errata no próprio ADR, sem reescrever a decisão. Não faça a errata neste pedido.

Se você já respondeu às Partes B ou C nesta sessão, não refaça: só grave a resposta no relatório.

## Restrições

- Este pedido não muda código, store, modelo nem critério.
- Não mexa no app instalado.
- Não contorne nenhuma trava: se algo bloquear, pare e me avise.
- Não envie nada ao remoto.

No relatório, apresente o commit do `CLAUDE.md`, o estado do repositório e a tabela dos tempos.
