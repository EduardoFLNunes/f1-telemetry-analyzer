# Relatório do pedido 19: relatório em arquivo e tempos de referência

- **Pedido:** `docs/prompts/2026-10-05_19_relatorio-em-arquivo-e-tempos.md`
- **Branch:** `develop` (o pedido não muda código, store, modelo nem critério)
- **Commits:**
  - `4e854ac8` docs: CLAUDE.md com a regra do relatório em arquivo
  - o commit deste relatório, com o pedido 19 e a tabela: "Relatório do pedido 19: relatório em arquivo, estado do repositório e tempos de referência"
- **Merges:** nenhum.
- **Arquivos de handoff:**
  - `docs/handoff/2026-10-05_19_relatorio-em-arquivo-e-tempos_relatorio.md` (este)
  - `docs/handoff/2026-10-05_19_tempos_tabela.json`: a tabela completa, com volta, fonte e valores

Nada foi enviado ao remoto. O app instalado não foi tocado.

## Parte A: `CLAUDE.md`

Commitado em `develop` (`4e854ac8`), com a mensagem pedida. Daqui em diante, cada pedido termina com o relatório completo em `docs/handoff/AAAA-MM-DD_NN_<assunto>_relatorio.md`, commitado junto com o handoff.

## Parte B: estado do repositório

Conferido às 12:25 e de novo agora, com o mesmo resultado:

- **`git status`:** `develop` limpo e 85 commits à frente de `origin/develop`; nada foi enviado. Fora do git estão:
  - `docs/estudos/`;
  - os dois documentos antigos do backlog (`docs/integracao_ml_e_empacotamento.md` e `docs/phase16_dashboard_3_visoes.md`);
  - o arquivo deste pedido, que entra no commit do relatório.
- **`git worktree list`:** só a worktree principal. **`.claude/worktrees/`** está vazia; a pasta é de 02/10.
- **`git stash list`:** só o `stash@{0}` "Organizacao das 3 visoes", de 19/08, que já está no backlog.
- **`git branch -a`:** as `etapa/*` desta série de pedidos, as duas `feature/phase-15*`, `main` e as remotas antigas. Nenhuma branch nova.
- **Commits:** nenhum commit de hoje fora de `develop`. O reflog de hoje só tem o trabalho desta sessão.

**A sessão separada da tarefa "Fix flaky WindowTest" não deixou branch, worktree, stash nem commit.** Não há nada para apagar e nada foi juntado dela. A correção que vale é a desta sessão (merge `9c1846b6`).

## Parte C: tempos de referência

### As fontes

- **Tempo oficial:** o `lap_time_s` do store v2, o período de s = 0 a s = 0.
- **Cronômetro do jogo:** o `tempo_jogo_s` do store v2, o cronômetro do jogo costurado na troca de volta. Bate com o oficial em 1 ms, exceto nas gravações a 31 Hz, onde chega a 8 ms.
- **`duration_s`:** do inventário. Mede do primeiro ao último ponto gravado da volta, sem os trechos até a linha, e fica de 13 a 43 ms curto. **Não é tempo de volta.**
  - O resumo do inventário (`ml/data/inventory.py::summarise`, linhas 211 e 228 a 231) publica esse valor com o nome `lap_time_s`. É daí que a confusão se espalhou.

### Os números do ADR 0016

| número | volta | fonte | oficial | jogo |
|---|---|---|---:|---:|
| 89,379 s (sua melhor) | `2026-10-04_02-24-04#0018` (parte 2, volta 5) | `duration_s` | **89,390 s** | 89,389 s |
| 84,816 s (volta da IA) | `2026-10-04_03-42-10#0013` (parte 2, volta 26) | `duration_s`; com ele, a `#0012` empata em 84,816 | **84,829 s** | 84,829 s |

- **Os dois números do ADR 0016 vieram do `duration_s`.** A decisão não depende deles.
- **As referências do coach estão certas.** O 89,389 s e o 84,828 s saem da medida do próprio coach (s = 0 interpolado e relógio da física), que bate com o jogo em 1 ms.
- **Pelo tempo oficial, a melhor volta da IA é a `#0013`,** e é ela que o coach usa. A `#0012` tem 84,835 s.

### Onde mais aparecem tempos que não são o oficial

**Nos documentos:**

| arquivo | número antigo | oficial | volta | fonte do antigo |
|---|---|---|---|---|
| `docs/decisoes/0016-coach-na-fase-de-aprendizado.md`, linha 16 | 89,379 s | 89,390 s | `02-24-04#0018` | `duration_s` |
| `docs/decisoes/0016-coach-na-fase-de-aprendizado.md`, linha 16 | 84,816 s | 84,829 s | `03-42-10#0013` | `duration_s` |
| `docs/detector_ia.md`, linha 63 | 89,379 s (parte 2, volta 5) | 89,390 s | `02-24-04#0018` | `duration_s` |
| `docs/detector_ia.md`, linha 63 | 84,816 s (parte 2, **volta 25**) | 84,829 s, na **volta 26** | `03-42-10#0013`; a volta 25 (`#0012`) tem 84,835 s | `duration_s` |
| `docs/detector_ia.md`, linha 62 | 93,58 ± 2,40 s (11 suas); 84,99 ± 0,13 s (13 da IA) | 93,60 ± 2,40 s; 85,02 ± 0,13 s | as voltas limpas de 04/10 | `duration_s` |
| `docs/backlog.md`, linha 16 | 89,379 s e 84,816 s | 89,390 s e 84,829 s | as do ADR 0016 | cópia do ADR 0016 |
| `docs/backlog.md` (linha 18), `docs/coach_geometria_oficial.md` (172), `docs/origem_das_voltas.md` (219) | 84,663 s | 84,672 s | `rec__2026-08-19_22-23-14__32` = `2026-08-19_22-23-14#0004` | coach antigo (modelo de teste do pedido 11); não é `duration_s`, que dá 84,654 |
| `docs/coach_aprendizado.md`, tabela do pedido 14, coluna "jogo ~" | ~84,873; ~85,293; ~85,467; ~85,494; ~85,557 | 84,875; 85,323; 85,468; 85,500; 85,565 | as 5 voltas do critério (c) | cronômetro do jogo na última amostra, sem costura |

- **Na mesma tabela do pedido 14,** a coluna "período verdadeiro" difere do oficial em 1 a 4 ms. Ela usava a extrapolação por uma amostra só.

**Nos JSONs de resultado:**

| arquivo | campos | fonte | melhor oficial |
|---|---|---|---|
| `docs/handoff/2026-10-04_detector-ia_resultados.json` (pedido 13) | `tempo_s` de todas as voltas (43, 21 e 7), as melhores (89,379 e 84,816) e a média e o desvio do tempo de volta | `duration_s` | 89,390 s e 84,829 s |
| `data/ml/origem/detector_aplicar.json` | `sessao_rotulada.voltas[].tempo_s` (21) | `duration_s` | — |
| `docs/handoff/2026-10-04_origem-das-voltas_resultados.json` (pedido 12) | `item5_inventario.lap_time_s` (mín. e melhor 84,654, mediana 86,031, máx. 135,738), `sessoes[].melhor_volta_s` e `tempo_volta_mediana_s` | `duration_s` (chamado de `lap_time_s` no resumo) | 84,672 s (`2026-08-19_22-23-14#0004`) |
| `data/ml/origem/lap_inventory_summary.json` e a cópia em `pedido12/` | `lap_time_s` e `best_lap` (84,654) | `duration_s` | 84,672 s |
| `data/ml/lap_inventory_summary.json` (inventário antigo, 30/09) | `lap_time_s` e `best_lap` (84,84, `2026-08-16_03-30-14#0017`) | `duration_s` | 84,878 s |

**Onde não há `duration_s`:**

- **O painel e os JSONs da evolução** (`data/ml/evolucao/`): todos os tempos saem do store v2.
- **ADR 0015** ("93,0 e 95,3 s; 85,0 e 85,1 s"): veio do `duration_s`, mas com uma casa decimal fica igual ao oficial.
- **Fases 1, 2 e 2b, ADR 0009 (84,822 s) e `coach_referencia_real.md`:** vêm do store antigo, com o período um passo da grade curto. São registro pelo pedido 16. Bateram com o `duration_s` de voltas de outubro só por coincidência, assim como os custos do simulador, as janelas em metros e os números de volta que a varredura achou.

### Como foi procurado

- **Documentos:** todo número com três casas decimais entre 60 e 400 s, em `docs/` (fora os pedidos) e no painel. Cada um foi comparado com o `duration_s` e com o oficial de todas as voltas, e cada coincidência foi conferida no contexto. Também foram procurados números com duas casas que batessem com o `duration_s` das voltas de outubro: nenhum.
- **JSONs:** os 53 de `docs/handoff/` e de `data/ml/`, valor a valor, do mesmo jeito.

### O que proponho (nada foi mudado)

1. **ADR 0016:** nota de errata datada abaixo da tabela, sem reescrever a decisão: os tempos vieram do `duration_s`, e os oficiais são 89,390 s e 84,829 s. Pelo pedido, ela fica para depois.
2. **`docs/detector_ia.md`:** a mesma errata para as linhas 62 e 63, apontando que a melhor da IA é a volta 26.
3. **`docs/backlog.md`:** trocar os números das linhas 16 e 18 pelos oficiais. O backlog é um documento vivo.
4. **`docs/coach_geometria_oficial.md` e `docs/origem_das_voltas.md`:** nota de que 84,663 s foi o tempo do coach antigo e de que o oficial é 84,672 s.
5. **`docs/coach_aprendizado.md`:** nota na tabela do pedido 14 de que "jogo ~" é o cronômetro na última amostra, com o costurado e o oficial ao lado.
6. **JSONs de resultado dos pedidos 12 e 13:** são registro e ficam como estão. Proponho só uma nota no `docs/origem_das_voltas.md` e no `docs/detector_ia.md` dizendo que os `tempo_s` deles são `duration_s`.
7. **Código, num pedido próprio:** trocar o nome `lap_time_s` por `duration_s` no resumo do inventário, para a confusão não voltar.

**O que precisa de decisão sua:** quais dessas correções entram, e em que pedido.
