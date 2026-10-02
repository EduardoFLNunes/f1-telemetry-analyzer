# 0001 — Processo de desenvolvimento com vários agentes

- **Status:** aceita; itens 2 e 3 substituídos pelo ADR 0008 (uma sessão de implementação por vez)
- **Data:** 2026-09-30
- **Decisor:** Eduardo

## Contexto

Duas sessões do Claude Code trabalharam ao mesmo tempo no mesmo diretório. Uma delas contornou a trava da worktree editando a pasta principal por script. Resultado: `coaching.py` e `test_ml_export.py` alterados por fora da fase em andamento e 2 testes falhando. Nada estava commitado, então não havia como separar o trabalho de cada sessão.

Guias de uso de agentes em paralelo recomendam uma worktree por agente, divisão por domínio e revisão antes do merge.

## Decisão

1. **Papéis.** Eduardo decide. Claude (Cowork) define arquitetura, revisa e escreve os pedidos. As sessões do Claude Code implementam.
2. **Uma worktree e uma branch por sessão**, sempre criada a partir de `develop` ou de uma tag de handoff. A pasta principal (`develop`) é usada só para integração.
3. **Divisão por domínio:**
   - validação e modelos (`backend/ml/validation`, `backend/ml/models`, `backend/ml/scripts`);
   - app e geometria (`backend/core`, `backend/ml/export`, `backend/ml/track`, frontend);
   - `docs/decisoes/`, escrito pelo Claude (Cowork) e commitado por quem integra.
4. **Nenhuma sessão contorna uma trava.** Se for bloqueada, para e pergunta.
5. **Handoff ao fim de cada etapa**, em `docs/handoff/`:
   - `<data>_<etapa>.patch`, contra a tag anterior;
   - `<data>_<etapa>_testes.txt`, com a saída completa do pytest;
   - `<data>_<etapa>_resultados.json`, com os números, o commit de base, o ambiente e os comandos.
6. **Commit e tag** `handoff/<etapa>` ao fim de cada etapa aprovada. Merge em `develop` só depois de revisão do diff.
7. **Nada vai ao remoto sem pedido explícito.**

## Consequências

- Cada fase fica isolada, reproduzível e citável na monografia.
- Fica um pouco mais lento: uma sessão espera a integração da outra quando os domínios se tocam.
- `*.patch` deve ser marcado como binário no `.gitattributes`, para o git não converter as quebras de linha.
