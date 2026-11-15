# Pedido 51: relatório (PARADO no meio da Parte C, por limite de uso da sessão)

- **Pedido:** `docs/prompts/2026-11-15_51_volta-de-referencia-do-modelo.md`
- **Pasta e branch:** `C:\Users\Dokas\Desktop\f1-telemetry-analyzer`, `etapa/volta-do-modelo` (a partir de `develop` em `51ad8cde`)
- **Commits:**
  - `88bcdcdd` Pedido 51: o texto do pedido
  - `79990728` Parte A: o ADR 0032, antes do código
  - `567e1796` Parte B: a volta do modelo como arquivo do app e a conferência
  - `3f55ada3` Parte C (em andamento): as duas referências, os textos e as versões; testes do backend por ajustar
  - (este relatório, no commit seguinte)
- **Merges:** nenhum. **Envio ao GitHub:** nenhum.
- **Arquivos de handoff:** `docs/handoff/2026-11-15_51_volta-de-referencia-do-modelo_conferencia.json` e este relatório.

## Parte 0

- A pasta principal estava em `etapa/replay-e-radio-que-ensina`, limpa (só o texto do pedido sem commit). O app do repositório não estava aberto. O `acs.exe` não estava aberto.
- **O envio do pedido 50 não foi feito:** `origin/develop` está em `4c7bcbae`, e o `develop` local em `51ad8cde`. O envio de `develop` deste pedido levará o 50 junto.
- O contexto confere: o modelo da pasta principal está em `volta_ia` (`2026-10-04_03-42-10_vhe_interlagos#0013`, 84,828 s, construído em 22/10); o app instalado está com `"referenciaCoach": "minha_melhor"`.

## Parte A

ADR 0032 (`docs/decisoes/0032-referencia-do-app-e-a-volta-do-modelo.md`) e a linha no índice, no commit `79990728`, antes de qualquer código.

## Parte B: a volta do modelo

- **O arquivo:** `data/reference_models/vhe_interlagos.volta_do_modelo.json` (125.708 bytes; fora do git pela regra `data/reference_models/*.json`). O instalador o leva pelo filtro novo `*.volta_do_modelo.json` no `extraResources` (como o `*.optimal.json`). O backend o procura no repositório, na pasta de dados e na de recursos.
- **A volta:** `2026-11-15_02-47-12_vhe_interlagos_teste_m1#0008` (sequência 8, volta 9 do jogo), gravação do app instalado, só lida (sha256 de `metadata.json`, `opponents.jsonl` e `player.jsonl` no arquivo).
- **O comando:** `python -m ml.scripts.volta_do_modelo --linhas <pasta do 47>\data\pista_teste\linhas --resultado docs/handoff/2026-11-12_50_linha-do-projeto_resultado.json --handoff …`
- **A conferência:**
  - a pista: os 19 arquivos da origem do cache da pista têm o mesmo sha256 na cópia e na original, incluindo o `vhe_interlagos.kn5` (`ce1f3bb2…`); o `fast_lane.ai` da cópia está hoje igual ao original (o bloco 5 voltou o C0). A gravação usou o cache `vhe_interlagos_gp_kn5_surface_interval_geometry` e o `geometry_id` `0ed16f0dd2225990`, o mesmo da original;
  - o tempo refeito na grade: **1:24,552** (84,55158 s), 0,0 ms do `_resultado.json` e −0,42 ms de 1:24,552; o cronômetro do jogo, 84,55064 s; a soma dos 60 microssetores do coach, 84,550 s;
  - os 15 trechos: iguais aos do `_resultado.json` (diferença máxima 0,0 ms);
  - a distância: até a L2, mediana 0,27 m e p95 0,84 m; até a linha da IA, mediana 0,92 m e p95 6,83 m. **É a L2;**
  - os alvos por microssetor, lado a lado com os da `#0013`: no `_conferencia.json` (`microssetores_lado_a_lado`). **Ainda não passados para tabela neste relatório.**

## Parte C (feita em código, não conferida)

- `volta_do_modelo` e `minha_melhor` são os tipos; a padrão é `volta_do_modelo`; `volta_ia` na configuração e no `AT_COACH_REFERENCE` vira `volta_do_modelo` (e o arquivo é regravado ao abrir).
- Sem o arquivo: só "Sua melhor volta", com a frase do ADR 0032, item 4, e o coach usa a `minha_melhor`.
- O construtor (`train_reference_model`) lê o arquivo e não procura mais voltas da IA; o relatório de evolução usa a volta do modelo como régua e marca a técnica da referência como "não julgada".
- O rádio, o fantasma e a tela Volta leem a grade da volta do modelo do arquivo (a rota `/api/store/voltas/{lap}` responde por ela).
- Textos: "da referência", "a referência freia…", "Melhor da sessão", "Referência" no fantasma e no replay, "freada da referência" no app do jogo; as telas Ao vivo, Volta, Evolução e Sessões.
- Versões: `0.8.0-volta-do-modelo` (`desktop/package.json`, `desktop/main.js`, `backend/main.py`); app do jogo 0.6.0.
- Os scripts do Modelo 2 e do retreino da LSTM seguem na `#0013` pela constante `VOLTA_IA`.
- Front: `tsc` ok e 180 testes passando (com o teste novo que acusa "IA" na frase e no detalhe da referência).

## O que falta

1. **Ajustar os testes do backend** que usam `REFERENCE_AI`/`volta_ia` (primeiro: `tests/test_coach_learning_phase.py`; depois `test_radio.py`, `test_radio_voltas_45.py`, `test_coleta.py`, `test_leitura.py`, `test_atualizar_coach.py`) e escrever o teste novo do backend que acusa "IA" em fala, cartão ou rótulo da referência.
2. Rodar o construtor (`atualizar_coach`) para o modelo do repositório ganhar a `volta_do_modelo` (sem ele, o app anexa a volta do arquivo ao carregar).
3. Parte D: o rádio fora do tempo real (13/10, 18/10, 21/10 e 12/11), as prévias HTML, as capturas, a suíte, o `conferir_lua.py`.
4. Parte E: o instalador (só depois das conferências) e o "pode instalar".
5. Parte F: a documentação; o merge em `develop`; o envio (comandos para o Eduardo).
6. Tabela dos microssetores lado a lado e itens para o backlog (as chaves `*_ia_*` dos JSONs da evolução, que agora medem contra a volta do modelo).
