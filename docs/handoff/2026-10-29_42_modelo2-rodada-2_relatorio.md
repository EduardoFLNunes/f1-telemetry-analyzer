# Pedido 42 — relatório parcial: parado na Parte 0, item 5 (o store v2 reprovado)

- **Pedido:** `docs/prompts/2026-10-29_42_modelo2-rodada-2.md`, versão atualizada em 17/11/2026 (as Partes 0, A, C, D, E.1 e F.1 antes da parada).
- **Data:** 17/11/2026.
- **Pasta:** `C:\Users\Dokas\Desktop\f1-telemetry-analyzer-48`. A pasta principal (pedido 52, `etapa/engenheiro`) não foi tocada: nenhuma troca de branch, nenhum commit, nenhuma escrita.
- **Branch:** `etapa/modelo2-rodada-2`, criada a partir de `develop` (`14fe1ca0`).
- **Commits:**
  - `dc405d6a` — Pedido 42, atualizacao de 17/11: o texto do pedido (a volta do modelo como referencia, a pasta do 48, o store v2 reprovado);
  - o commit deste relatório (o hash está no chat e na nota da sessão, porque um arquivo não guarda o hash do próprio commit).
- **Merges:** nenhum.
- **Arquivos de handoff gerados:** só este relatório, `docs/handoff/2026-10-29_42_modelo2-rodada-2_relatorio.md`.

## Resumo

O Modelo 2 recusa o store v2 reprovado. O carregador (`backend/ml/modelo2/dados.py`, `carregar`) para com `PARADO: store v2 ausente ou nao aprovado.`, e o store está com `aprovado: false` desde 15/11. O pedido manda parar e avisar nesse caso (Parte 0, item 5), sem contornar. Então parei na Parte 0.

Feito: os itens 0.1 a 0.4 e a conferência do jogo (0.7). Não feito: a rodada 1 refeita (0.6) e as Partes A, C, D, E.1 e F.1. Nada foi escrito em `data/ml/modelo2/` nem em `data/reference_models`.

## Parte 0

### 0.1 A pasta

- Nenhuma outra sessão está ativa na pasta do 48. O `list_sessions` mostra todas paradas, e o `git worktree list` mostra a do 48 em `etapa/diagnostico-m1` (`bbff5c97`), antes da troca.
- O 52 está na pasta principal, em `etapa/engenheiro` (`1edbebf3`). Não foi tocado.

### 0.2 A branch

- **Antes:** a pasta do 48 estava em `etapa/diagnostico-m1`, limpa, salvo o texto do pedido 42 modificado (a versão de 17/11, sem commit, como diz o pedido).
- **A troca:** o texto do pedido é igual em `etapa/diagnostico-m1` e em `develop`. Por isso o `git switch -c etapa/modelo2-rodada-2 develop` levou a modificação sem recusar.
- **O commit:** o texto foi commitado primeiro, em `dc405d6a`.
- **Uma diferença com o contexto (só informação):** o pedido diz que `develop` está "no GitHub em `36152415`". O `develop` local está em `14fe1ca0`, dois commits à frente (`99004b42` e `14fe1ca0`, relatórios do 51). A referência local `origin/develop` também aponta para `14fe1ca0`. Não muda nada aqui.

### 0.3 O que fica fora do git, e os links

O que o Modelo 2 lê fora do git:

| O quê | Onde o código procura (pasta do 48) | Situação |
|---|---|---|
| store v2, caches do Modelo 2, saídas da rodada 1 | `data/ml` | junção já existente → `...\f1-telemetry-analyzer\data\ml` (conferido) |
| gravações | `data/recordings` | junção já existente → `...\f1-telemetry-analyzer\data\recordings` (conferido) |
| geometria da grade (`vhe_interlagos_gp_kn5_surface_interval_geometry.json`) | `data/cache/tracks` | junção já existente → `...\f1-telemetry-analyzer\data\cache` (conferido) |
| gravações do app instalado | `%APPDATA%\Automobilista Telemetria\data\recordings` | fora do repositório, lido direto |
| `data/feature_store` | `data/feature_store` | **faltava.** Junção criada → `...\f1-telemetry-analyzer\data\feature_store`. Nenhum código de `backend/ml` ou `backend/core` lê essa pasta; ela foi ligada porque o pedido a lista. |
| a geometria oficial (`vhe_interlagos.geometry.json`) | `data/reference_models` | **faltava.** Vínculo real (hard link) criado |
| a volta do modelo (`vhe_interlagos.volta_do_modelo.json`) | `data/reference_models` | **faltava.** Vínculo real criado |
| o modelo do coach (`vhe_interlagos.json`) | `data/reference_models` | **faltava, e não estava na lista do pedido.** O `modelo2 todos` lê esse arquivo (`model_path`) para achar o id da volta de referência. Vínculo real criado |

- **Por que vínculo real:** a junção só serve para pastas. A `data/reference_models` da pasta do 48 já existe e tem um arquivo versionado (`vhe_interlagos.optimal.json`), então ela não pode virar uma junção sem apagar esse arquivo. Para os três arquivos, usei `mklink /H`, que não copia nada: é o mesmo arquivo nas duas pastas.
- **A conferência:** o `fsutil hardlink list` mostra os dois caminhos de cada arquivo, e o SHA-256 é igual nas duas pastas: geometria `811da4c9…`, modelo do coach `f8e61864…`, volta do modelo `e8651d45…`.
- **O cuidado:** qualquer escrita nesses três caminhos da pasta do 48 muda o arquivo da principal. O pedido não escreve em `data/reference_models`. Para desfazer, basta apagar os três vínculos e a junção na pasta do 48: os originais ficam.
- **O git:** os quatro caminhos são ignorados pelo `.gitignore` (linhas 40 e 73). O `git status` continua limpo.

### 0.4 O que é escrito

Nada até agora. Nenhum arquivo em `data/ml/modelo2/`, nem em `data/reference_models`, nem em `docs/`, salvo este relatório.

### 0.5 A trava do store v2: o Modelo 2 recusa → PARADO

- **O meta do store** (`data/ml/laps_grid_v2_meta.json`): `aprovado: false`, construído em 15/11 às 19:34 UTC, commit `a168e41f`, 721 voltas.
- **A checagem que falha:** "a linha do jogo fica onde foi medida (pedido 34)": registrada a 1,463 m, tolerância de 0,10 m, mediana de 1,4972 m. As sessões fora:

  | Sessão | Voltas | Mediana | Desvio |
  |---|---|---|---|
  | `2026-11-01_19-47-03` | 6 | 1,606 m | 0,018 m |
  | `2026-11-07_18-46-00` | 5 | 1,581 m | 0,080 m |
  | `2026-11-12_22-57-03` | 4 | 1,573 m | 0,023 m |

  As outras checagens passam: o período contra o cronômetro, sem box, sem duplicatas e uma geometria só.
- **O que o Modelo 2 faz:** `backend/ml/modelo2/dados.py`, linha 302, logo no começo de `carregar`:

  ```python
  if not meta or not meta.get("aprovado"):
      raise SystemExit("PARADO: store v2 ausente ou nao aprovado.")
  ```

  Rodei só essa chamada (`carregar(None)`, que para nessa linha antes de ler qualquer dado). A saída foi `SystemExit: PARADO: store v2 ausente ou nao aprovado.` Não rodei o `modelo2 todos`.
- **As passagens das 3 sessões reprovadas:** pelo meta, são 15 voltas `humano` (6 + 5 + 4), ou seja, até 210 passagens (15 × 14 curvas), antes do portão do Modelo 2. Todas são posteriores ao kit de 24/10, então nenhuma está nas 120 passagens nem na rodada 1. Elas só entrariam na tabela à parte da Parte D.3 e no E3 das saídas de traseira (D.6, a sessão de 01/11).
- **Não contornei:** não mudei o portão, não passei `aprovado` à força e não li o store por outro caminho.

### 0.6 A rodada 1 refeita: não rodou (depende do store)

O que encontrei ao preparar, para quando houver decisão:

1. **O `modelo2 todos` sobrescreve a rodada 1.** O `run()` grava direto em `data/ml/modelo2/` (`resultados.json`, `erros_por_sessao.json`, `passagens.parquet`, `tecnicas.json` e outros). O `build_kit` regrava o `rotulagem_gabarito.json`, e o cache `derivados.parquet` também é regravado. Antes de refazer a rodada 1, o script precisa de uma pasta de saída própria (por exemplo, `data/ml/modelo2/rodada1_refeita/`), com os caches lidos e não regravados. É uma mudança de código pequena, ainda não feita.
2. **O store novo tem voltas que a rodada 1 não tinha.** A rodada 1 tem 144 voltas (130 do piloto e 14 da IA; 10 de fora do store), do store de 22/10 (commit `2b16db32`). O store de 15/11 traz:
   - as sessões de 24/10 (`13-26-12`, 3 voltas `humano`; `13-43-32`, 6 voltas `humano`), que na rodada 1 eram lidas "de fora do store" (`FORA_DO_STORE`). A de 22/10 (`09-46-01`) aparece no store como `misturada` (1 volta);
   - 17 voltas `humano` posteriores a 24/10: as 15 das sessões reprovadas e 2 de `2026-11-07_19-52-33`.

   Para reproduzir a rodada 1, a seleção precisa ser restrita aos 144 `lap_id` dela. O `store_selection` do 38 pega tudo do store pelo filtro da evolução.
3. **O id da referência:** o `run()` procura a volta da IA no modelo do coach (`LEGACY_AI_KIND`) e, se não houver, usa a `#0013` (`VOLTA_IA` de `ml.pista_teste.condicoes`, pedido 51). Isso reproduz a referência da rodada 1, se a `#0013` for a mesma volta.

### 0.7 O jogo

O `acs.exe` estava fechado na conferência (17/11, ~15:10). Nenhuma conta pesada foi rodada.

## Partes A, C, D, E.1 e F.1

Não começaram. A Parte A só registra regras e não lê o store. Mesmo assim, o pedido manda parar na Parte 0 quando o Modelo 2 recusa o store. E a ordem do pedido põe a conferência da rodada 1 (0.6) antes de tudo que a compara.

## O que precisa de decisão

1. **O store v2 reprovado.** Os caminhos que vejo, para você escolher:
   - **(a) esperar** o pedido próprio da causa da linha do jogo (1,57 a 1,61 m contra 1,463 m), que reaprova o store, e então retomar daqui;
   - **(b) autorizar, por escrito num pedido, uma exceção registrada para o Modelo 2:** ele lê o store reprovado, as voltas das 3 sessões reprovadas ficam marcadas, e o portão continua no código, com a exceção explícita. O pedido já diz que a diferença de cerca de 0,14 m no s = 0 não muda a curva de uma passagem. Isso é decisão sua: eu não faço;
   - **(c) seguir só com a Parte A** (registrar as regras, sem ler o store) e parar de novo antes da 0.6.
2. **A rodada 1 refeita (para quando o store for liberado):** confirmar o que encontrei na 0.6, ou seja, uma pasta de saída própria e a seleção restrita aos 144 `lap_id` da rodada 1. Sem isso, a comparação mistura dados novos com as emendas, que é o que a 0.6 quer evitar.
3. **O modelo do coach** (`vhe_interlagos.json`) também é lido pelo Modelo 2 e não estava na lista da 0.3. Ficou ligado por vínculo real, como os outros. Confirme se está bem assim.

## O que falta

- A Parte 0, itens 5 (depois da decisão) e 6;
- as Partes A, C, D, E.1 e F.1, e o relatório parcial delas;
- depois da sua parada: as Partes B, E.2, F.2 e G, o merge e o envio de `develop`.

## Testes

Nenhum código mudou, então a suíte não foi rodada.

## Envio ao GitHub

Tentei o envio da branch uma vez, depois do commit deste relatório. O resultado está no chat e na nota da sessão. Se o controle de permissões recusar, rode pelo terminal, um comando por vez:

```bash
git -C C:/Users/Dokas/Desktop/f1-telemetry-analyzer-48 push -u origin etapa/modelo2-rodada-2
```

```bash
git -C C:/Users/Dokas/Desktop/f1-telemetry-analyzer-48 ls-remote origin refs/heads/etapa/modelo2-rodada-2
```

O hash do `ls-remote` deve ser o mesmo de `git -C C:/Users/Dokas/Desktop/f1-telemetry-analyzer-48 rev-parse etapa/modelo2-rodada-2`.

**A conferência antes do envio:** os commits da branch sobre `develop` mudam só dois arquivos, ambos em `docs/` (o texto do pedido e este relatório). Nenhum passa de 50 MB, nenhum é gravação ou dado de `data/` e nenhum tem segredo.
