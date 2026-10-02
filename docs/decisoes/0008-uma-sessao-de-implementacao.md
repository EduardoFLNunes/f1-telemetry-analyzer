# 0008 — Uma única sessão de implementação por vez

- **Status:** aceita; substitui os itens 2 e 3 do ADR 0001
- **Data:** 2026-10-02
- **Decisor:** Eduardo

## Contexto

O ADR 0001 previa uma worktree por sessão e uma divisão de domínios entre duas sessões do Claude Code. Na prática, coordenar duas sessões custou mais do que rendeu:

- pedidos chegaram fora de ordem;
- uma sessão parou esperando commits da outra;
- o trabalho da correção do coach ficou sem commit numa worktree separada.

## Decisão

1. Só existe uma sessão de implementação ativa: a sessão da pasta principal.
2. Ela trabalha numa branch por etapa, criada a partir de `develop` ou da última tag de handoff, e faz merge em `develop` depois da revisão.
3. Worktrees só são usadas se o Eduardo pedir explicitamente.
4. O restante do ADR 0001 continua valendo: papéis, handoff verificável, tags, nenhuma trava contornada e nada enviado ao remoto sem pedido.

## Consequências

- Não há mais conflito de arquivos entre sessões nem dependência de ordem entre pedidos.
- O trabalho fica sequencial. Uma tarefa de app (como a geometria única, ADR 0002) espera a etapa científica em andamento, ou o contrário.
- O trabalho da worktree `elastic-kepler-a8182e` é trazido para `develop` pelo patch já revisado (`2026-09-30_coach_mapeamento.patch`). Depois disso, a worktree é removida.
