# Pedido 51: relatório

- **Pedido:** `docs/prompts/2026-11-15_51_volta-de-referencia-do-modelo.md`, continuado em 15/11 à tarde pelos itens 1 a 6 do relatório parcial (`263c5fd6`), com a sua instrução: o instalador só depois das conferências da Parte D, e a instalação só com o seu "pode instalar". Às 17:10, a sua decisão sobre a trava do store v2: "Siga sem resolver: gere o instalador e faça o merge".
- **Pasta e branch:** `C:\Users\Dokas\Desktop\f1-telemetry-analyzer`, `etapa/volta-do-modelo` (a partir de `develop` em `51ad8cde`).
- **Situação:** **feito.** O instalador `0.8.0-volta-do-modelo` foi gerado, conferido e **instalado** com o seu "pode instalar" (15/11, 17:23). O merge está em `develop` (`c4869295`), e a pasta principal ficou em `develop`. A trava do store v2 fica para um pedido próprio, por sua decisão de 15/11 às 17:10. O envio foi feito por você e conferido (17:38).
- **Commits:**
  - `88bcdcdd` Pedido 51: o texto do pedido
  - `79990728` Parte A: o ADR 0032, antes do código
  - `567e1796` Parte B: a volta do modelo como arquivo do app e a conferência
  - `3f55ada3` Parte C: as duas referências, os textos, a versão 0.8.0 e o app do jogo 0.6.0
  - `263c5fd6` o relatório parcial (parado por limite de uso)
  - `5dbe4fa8` Parte D: os testes do backend, o teste novo, o rádio fora do tempo real, as prévias e as capturas
  - `a168e41f` Parte F: a documentação e a conferência do Lua
  - `3707c48d` Parte D.5: a suíte (1043 passando), o front, o desktop e o Lua
  - `46e8db8f` o relatório, parado na trava (o commit de onde o instalador foi gerado)
  - `dcabd0fc` Parte E: o instalador no índice das versões (`versoes/LEIA-ME.md`)
  - em `develop`, depois do merge: `b1442d42` o relatório com o instalador e o merge, e o commit deste relatório com a instalação
- **Merge:** `c4869295` Merge do pedido 51 em `develop` (`--no-ff`, sem conflito). **Envio:** nenhum (os comandos estão no fim).
- **Arquivos de handoff** (`docs/handoff/2026-11-15_51_volta-de-referencia-do-modelo_…`):
  - `_relatorio.md` (este);
  - `_conferencia.json` (a Parte B: a pista, o tempo, os trechos, a distância e os microssetores lado a lado);
  - `_radio_offline.py`, `_radio_contar.py` e `_radio_antes_e_depois.json` (a D.1);
  - `_minimapa_previa.py`, `_minimapa_boxes.png`, `_aproximado_previa.py` e `_aproximado_c04.png` (a D.3);
  - `_tela_coleta.png`, `_tela_ao-vivo.png` e `_tela_volta.png` (a D.4, em 1920 × 1080);
  - `_conferir_lua.txt` e `_testes.txt` (a D.5);
  - `_relatorio.md` substitui o relatório parcial de `263c5fd6`.

## Parte 0: a pasta e o envio do 50

- A pasta principal estava em `etapa/replay-e-radio-que-ensina`, limpa (só o texto do pedido sem commit). O app do repositório não estava aberto, e o `acs.exe` não estava aberto em nenhuma das contas pesadas.
- **O envio do pedido 50 não tinha sido feito:** `origin/develop` em `4c7bcbae`, `develop` local em `51ad8cde`. **O envio de `develop` deste pedido leva o 50 junto** (e os 2 commits só locais do 45).
- **O contexto confere com o repositório:**
  - o modelo da pasta principal estava em `volta_ia`, na `2026-10-04_03-42-10_vhe_interlagos#0013` (84,828 s), construído em 22/10;
  - o app instalado está com `"referenciaCoach": "minha_melhor"`;
  - a referência por trecho com a L2 está só na pasta do 47, e o coach não a lê.

## Parte A: o ADR 0032

`docs/decisoes/0032-referencia-do-app-e-a-volta-do-modelo.md`, com a linha no índice, no commit **`79990728`**, antes de qualquer código. O número 0032 era o próximo livre.

## Parte B: a volta do modelo como arquivo do app

**O arquivo:** `data/reference_models/vhe_interlagos.volta_do_modelo.json` (125.708 bytes).
- Fica **fora do git**, pela regra que já existia (`data/reference_models/*.json`), ao lado do modelo do coach.
- **O instalador o leva:** o `extraResources` lê da pasta do repositório no disco, e não do git. Bastou acrescentar o filtro `*.volta_do_modelo.json` ao lado do `*.optimal.json`. Por isso não precisei parar para perguntar.
- **O backend o procura** na pasta do repositório, na pasta de dados e na de recursos, nessa ordem.
- **O comando:** `python -m ml.scripts.volta_do_modelo --linhas <pasta do 47>\data\pista_teste\linhas --resultado docs/handoff/2026-11-12_50_linha-do-projeto_resultado.json`. A pasta do 47 só foi lida.

**O que o arquivo guarda** (só o que foi derivado da gravação):
- a grade de 2 m: 2.167 pontos com o tempo, a lateral, a posição (x, z), a velocidade, a marcha e os pedais, pelo mesmo caminho do store v2;
- os 60 alvos por microssetor, pelo mesmo caminho das referências do coach;
- a origem: a sessão `2026-11-15_02-47-12_vhe_interlagos_teste_m1`, a sequência 8, a volta 9 do jogo, e o sha256 dos 3 arquivos da gravação (`metadata.json`, `opponents.jsonl`, `player.jsonl` de 197 MB). **A gravação não foi copiada;**
- a linha L2 e o sha256 do `fast_lane.ai` dela (`4e9f1250…`), o `geometry_id` (`0ed16f0dd2225990`), o `corridor_id` (`707d07029036abd6`), o carro (`rss_formula_rss_3_v6_2026`), o preset ("pedido 47 [teste]"), a marca "linha do projeto, meta atingida em 2026-11-15", "executada pela IA do jogo na linha do projeto" e a pista (`vhe_interlagos`).

### A conferência (B.3 e B.5)

| conferência | resultado |
|---|---|
| a cópia e a original | os 19 arquivos que a geometria lê (a origem do cache da pista) têm o mesmo sha256 nas duas; o kn5 da pista é `ce1f3bb2…` nas duas. O `fast_lane.ai` da cópia está hoje igual ao original, porque o bloco 5 voltou o C0. A gravação usou o cache da pista original, e as voltas foram medidas no `geometry_id` `0ed16f0dd2225990`, o mesmo da original. **A mesma geometria** |
| o tempo refeito na grade | **1:24,552** (84,55158 s): 0,0 ms do `_resultado.json` do 50 e −0,42 ms de 1:24,552 (até 5 ms). O cronômetro do jogo deu 84,55064 s, e a soma dos 60 microssetores do coach, 84,550 s |
| os 15 trechos | iguais aos do `_resultado.json` do 50 para essa volta (diferença máxima de 0,0 ms) |
| a distância à linha | até a L2: mediana **0,27 m**, p95 0,84 m. Até a linha da IA: mediana **0,92 m**, p95 6,83 m. **É a L2** |

### Os alvos por microssetor: a volta do modelo e a `#0013`, lado a lado

O tempo é o do microssetor, a mínima é a velocidade mínima nele, e a freada é onde o freio passa de 0,15 dentro dele (em metros, na geometria oficial; "—" quando a volta não freia ali). Os pedais da volta do modelo são o comando da IA (ADR 0032, item 5): a freada vale como ponto, e não como técnica.

**Soma:** a volta do modelo dá 84,550 s, contra 84,828 s da `#0013`. **Ela ganha em 15 microssetores e perde em 45, e fecha 0,278 s mais rápida.**

| ms | modelo (s) | #0013 (s) | dif. (s) | mín. modelo (km/h) | mín. #0013 (km/h) | freada modelo (m) | freada #0013 (m) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0,942 | 0,925 | +0,017 | 273 | 278 | — | — |
| 2 | 0,945 | 0,924 | +0,021 | 252 | 263 | 122 | 127 |
| 3 | 1,315 | 1,249 | +0,066 | 151 | 157 | — | — |
| 4 | 2,029 | 2,033 | −0,004 | 113 | 104 | 230 | 249 |
| 5 | 2,088 | 2,068 | +0,020 | 107 | 104 | — | 359 |
| 6 | 1,927 | 1,996 | −0,070 | 117 | 116 | 365 | — |
| 7 | 1,588 | 1,598 | −0,010 | 140 | 136 | — | — |
| 8 | 1,371 | 1,359 | +0,013 | 171 | 171 | — | — |
| 9 | 1,284 | 1,256 | +0,028 | 190 | 191 | — | — |
| 10 | 1,223 | 1,210 | +0,013 | 203 | 206 | — | — |
| 11 | 1,165 | 1,148 | +0,017 | 216 | 219 | — | — |
| 12 | 1,108 | 1,089 | +0,019 | 228 | 232 | — | — |
| 13 | 1,062 | 1,042 | +0,019 | 239 | 243 | — | — |
| 14 | 1,025 | 1,008 | +0,018 | 248 | 253 | — | — |
| 15 | 1,000 | 0,983 | +0,017 | 255 | 259 | — | — |
| 16 | 0,978 | 0,961 | +0,017 | 261 | 266 | — | — |
| 17 | 0,962 | 0,957 | +0,005 | 263 | 252 | 1216 | 1206 |
| 18 | 1,195 | 1,320 | −0,125 | 174 | 162 | 1230 | — |
| 19 | 1,621 | 1,780 | −0,159 | 134 | 128 | 1305 | 1301 |
| 20 | 1,792 | 1,791 | +0,001 | 133 | 129 | — | — |
| 21 | 1,473 | 1,464 | +0,009 | 163 | 163 | — | — |
| 22 | 1,282 | 1,258 | +0,023 | 187 | 189 | — | — |
| 23 | 1,245 | 1,218 | +0,027 | 201 | 204 | — | — |
| 24 | 1,182 | 1,163 | +0,019 | 214 | 217 | — | — |
| 25 | 1,142 | 1,123 | +0,019 | 223 | 227 | — | — |
| 26 | 1,112 | 1,093 | +0,019 | 230 | 234 | — | — |
| 27 | 1,202 | 1,235 | −0,033 | 189 | 187 | 1904 | 1891 |
| 28 | 1,392 | 1,359 | +0,034 | 175 | 180 | 1951 | 2015 |
| 29 | 1,406 | 1,652 | −0,246 | 177 | 152 | 2076 | 2042 |
| 30 | 1,420 | 1,583 | −0,163 | 176 | 155 | — | — |
| 31 | 1,574 | 1,639 | −0,065 | 115 | 112 | 2195 | 2199 |
| 32 | 2,314 | 2,461 | −0,146 | 92 | 86 | 2254 | 2250 |
| 33 | 2,309 | 2,291 | +0,018 | 95 | 90 | 2356 | 2359 |
| 34 | 2,162 | 2,311 | −0,149 | 97 | 92 | 2453 | — |
| 35 | 1,921 | 2,003 | −0,082 | 121 | 110 | — | — |
| 36 | 1,567 | 1,601 | −0,034 | 149 | 145 | — | — |
| 37 | 1,810 | 1,706 | +0,104 | 105 | 115 | 2622 | 2622 |
| 38 | 2,620 | 2,567 | +0,053 | 83 | 81 | 2679 | — |
| 39 | 2,156 | 2,086 | +0,070 | 90 | 94 | — | — |
| 40 | 1,574 | 1,527 | +0,046 | 149 | 153 | — | — |
| 41 | 1,338 | 1,278 | +0,060 | 177 | 182 | — | — |
| 42 | 1,270 | 1,264 | +0,006 | 193 | 198 | — | — |
| 43 | 1,216 | 1,197 | +0,019 | 206 | 210 | — | — |
| 44 | 1,355 | 1,353 | +0,002 | 141 | 145 | 3124 | 3122 |
| 45 | 2,055 | 2,189 | −0,133 | 112 | 98 | 3196 | 3215 |
| 46 | 1,946 | 1,995 | −0,049 | 114 | 104 | — | — |
| 47 | 1,564 | 1,532 | +0,031 | 154 | 153 | — | — |
| 48 | 1,407 | 1,371 | +0,037 | 179 | 180 | — | — |
| 49 | 1,311 | 1,270 | +0,040 | 194 | 197 | — | — |
| 50 | 1,215 | 1,177 | +0,038 | 205 | 209 | — | — |
| 51 | 1,150 | 1,129 | +0,021 | 215 | 219 | — | — |
| 52 | 1,144 | 1,126 | +0,018 | 223 | 226 | — | — |
| 53 | 1,100 | 1,080 | +0,020 | 231 | 235 | — | — |
| 54 | 1,064 | 1,047 | +0,018 | 239 | 243 | — | — |
| 55 | 1,035 | 1,012 | +0,023 | 246 | 250 | — | — |
| 56 | 1,011 | 0,971 | +0,040 | 252 | 257 | — | — |
| 57 | 0,997 | 0,968 | +0,029 | 258 | 263 | — | — |
| 58 | 0,976 | 0,957 | +0,019 | 263 | 268 | — | — |
| 59 | 0,962 | 0,943 | +0,019 | 267 | 272 | — | — |
| 60 | 0,951 | 0,932 | +0,019 | 270 | 276 | — | — |

## Parte C: o que mudou no app

**As referências** (`core/assisted_analysis/reference_model.py`, `core/coleta/configuracao.py`):
- `volta_do_modelo` ("Volta de referência", a padrão) e `minha_melhor` ("Sua melhor volta"). O tipo `volta_ia` saiu do app: não é escolhido, não é padrão e não aparece na rota `/api/coach/referencias` nem no `/api/coleta/antes`, mesmo num modelo antigo que ainda o tenha.
- **A configuração antiga** `"volta_ia"` vira `"volta_do_modelo"` ao abrir, e o arquivo é regravado; `"minha_melhor"` e `"desligado"` ficam. O `AT_COACH_REFERENCE=volta_ia` também vale como `volta_do_modelo`.
- **Sem o arquivo da volta do modelo:** as opções são só "Sua melhor volta" e "coach desligado", com a frase "A volta de referência desta pista ainda não foi gerada pelo modelo", e o coach usa a "Sua melhor volta".
- **O construtor** (`tools/train_reference_model.py`, chamado pelo `atualizar_coach`) lê o arquivo da volta do modelo e não procura mais voltas da IA. Ele só usa o arquivo se a geometria e o carro forem os do modelo.
- **Um modelo gravado antes da 0.8.0** ganha a volta do modelo do arquivo ao abrir (`volta_do_modelo.anexar`), na mesma geometria. Assim o app instalado, que lê o modelo da pasta do repositório, já usa a volta do modelo.

**O fantasma, o rádio e as telas:**
- a grade da volta do modelo vem do arquivo, pela mesma rota da volta do store (`/api/store/voltas/{lap}`), no mesmo formato, com a marcha a mais. O minimapa, o mapa aproximado, o replay e a tela Volta a desenham como as outras;
- **o relatório de evolução** usa a volta do modelo como régua. A coluna da técnica da referência (a freada emendada) fica "não julgada", porque os pedais dela são o comando da IA (ADR 0032, item 5). As chaves dos JSONs (`perda_para_ia_s`, `volta_da_ia_s`) não mudaram de nome;
- os scripts do Modelo 2 e do retreino da LSTM, que não mudam, seguem na `#0013` pelo identificador `VOLTA_IA` (ADR 0032, item 6).

**Os textos:**

| onde | antes | depois |
|---|---|---|
| voz e cartão | "atrás da IA", "freou 34 metros antes da IA", "mínima 30 quilômetros por hora abaixo da IA" | "atrás da referência", "freou 34 metros antes da referência", "abaixo da referência" |
| voz e cartão | "Melhor volta da sessão" | "Melhor da sessão" |
| cartão do coach | "a IA freia 12 m depois de você", "mínima da IA 104 km/h" | "a referência freia 12 m depois de você", "mínima na referência 104 km/h" |
| replay (backend, front e jogo) | "IA (referência)", faixa do pedal "IA" | "Referência", faixa "ref." |
| app do jogo, minimapa e mapa aproximado | "para a volta da IA", "freada da IA", fantasma "IA" | "para a referência", "freada da referência", fantasma "Referência" |
| Coleta de dados | "Volta da IA", "Minha melhor" | "Volta de referência", "Sua melhor volta", com o tempo e a marca da volta do modelo |
| Volta | "Volta da IA · 1:24,828", "contra a volta da IA", HUD "Volta da IA" | "Volta de referência · 1:24,552", "contra a volta de referência", HUD "Referência" |
| Evolução e Sessões | "referência: volta da IA", "IA (g)", "IA (m)", "(IA: …)", "s da IA" | "volta de referência", "Referência (g)", "Referência (m)", "(referência: …)", "s da referência" |
| Sessões (cartão) | "Volta da IA" | "Volta de referência" |

"Do seu recorde" e "da melhor da sessão" ficaram. **Ficaram também os "IA" que falam de quem dirigiu,** e não da referência: o indicador de IA, "IA no volante", as voltas da IA fora da estatística e da grade, e o rádio calado nas voltas da IA.

**As versões:** o app do Windows `0.8.0-volta-do-modelo` nos três pontos (`desktop/package.json`, `desktop/main.js` e `backend/main.py`); o app do jogo 0.6.0.

## Parte D: as conferências, sem jogo

### D.1, o rádio fora do tempo real

**Como:** cada sessão passou, amostra a amostra, pelo coach, pela volta ao vivo e pelo rádio, com a voz de verdade e o relógio do gravador (o script do pedido 43, adaptado: `_radio_offline.py`). Três rodadas por sessão:
- **antes:** o texto de `develop` e a `#0013`, como o app estava;
- **palavras:** o texto novo e a mesma `#0013`. **Só as palavras mudam** contra o "antes", então é aqui que se conta a causa perdida;
- **depois:** o app novo, com a volta do modelo.

A melhor do store é a das sessões anteriores, no mesmo carro. Os limites (7,3, 8,0 e 8,8 s) e a ordem do corte não mudaram.

| sessão | entregues (antes / palavras / depois) | com a causa na voz (antes / palavras / depois) | perderam a causa | ganharam a causa | perderam o "contra quem" | acima do limite | "IA" (antes / depois) |
|---|---|---|---:|---:|---:|---:|---|
| 13/10 | 20 / 21 / 23 | 13 / 14 / 15 | 0 | 0 | 2 | 0 | 20 / 0 |
| 18/10 | 20 / 19 / 19 | 12 / 12 / 12 | 0 | 1 | 2 | 0 | 19 / 0 |
| 21/10 | 34 / 34 / 34 | 22 / 23 / 24 | 0 | 1 | 1 | 0 | 34 / 0 |
| 12/11 | 13 / 12 / 13 | 6 / 6 / 7 | 0 | 1 | 0 | 0 | 13 / 0 |

- **Nenhuma mensagem perdeu a causa** com "referência" no lugar de "IA".
- **Três ganharam a causa,** porque "Melhor da sessão" é mais curto que "Melhor volta da sessão". Por exemplo, 21/10, volta 11:
  - antes: "Melhor volta da sessão, 1,4 segundo mais rápida. Curva 1: 9 décimos.";
  - agora: "Melhor da sessão, 1,4 segundo mais rápida. Curva 1: 9 décimos, freou 42 metros antes."
- **Em 5 mensagens, a causa ficou, mas o "contra quem" saiu,** porque "da referência" é mais longo que "da IA". Pela ordem do corte (ADR 0027), as palavras que dizem contra quem saem antes da unidade. Exemplos:
  - 13/10, análise: "… Freou 24 metros antes da IA." virou "… Freou 24 metros antes.";
  - 18/10, resumo: "Curva 4: 1,1 segundo, freou 54 metros antes da IA." virou "… freou 54 metros antes.".
- **As falas ficaram mais longas, dentro do limite.** Por exemplo, 21/10, volta 1: "Curva 12, esquerda: 7 décimos atrás da IA. Freou 16 metros antes da IA." levava 6,08 s; "… atrás da referência. Freou 16 metros antes da referência." leva 6,87 s.
- **Nenhuma fala passou do limite** nas 12 rodadas, e as maiores ficaram em 7,30 s (coach), 7,98 s (resumo) e 8,79 s (análise).
- **"IA" sumiu** de todas as falas, textos e detalhes das rodadas novas.
- **O número de mensagens muda um pouco entre as rodadas** (por exemplo, 20, 21 e 23 em 13/10): a duração de cada fala muda a janela em que a seguinte cabe, e a volta do modelo muda as perdas e o foco.
- **O rótulo do replay** não ficou guardado nas rodadas (o script olhou o lugar errado). Ele é conferido pelo teste `test_o_rotulo_do_replay_e_referencia`.

### D.2, os testes de texto

- `test_todo_numero_falado_tem_a_unidade_em_todos_os_tipos_de_mensagem` passa com o texto novo.
- **O teste novo** `backend/tests/test_referencia_do_app.py` (10 testes) acusa "IA" em qualquer fala, cartão ou linha das mensagens da referência (diferença, resumo, curva e análise), nas frases do coach, no rótulo do replay e nos textos do app do jogo. Ele também cobre "Melhor da sessão", a conversão do `volta_ia`, a frase sem a volta do modelo e a leitura do arquivo.
- No front, o teste das mensagens de rádio também acusa "IA" na frase e no detalhe.

### D.3, as prévias

Pela conta do app do jogo, num canvas, com a volta do modelo e um instante real da sessão de 12/11:
- **o minimapa na saída dos boxes** (`_minimapa_boxes.png`): a volta de saída, com o cronômetro em 30 s; o fantasma "Referência" 26,56 s à frente;
- **o mapa aproximado na freada da C04** (`_aproximado_c04.png`): a volta 8 (1:27,947), a 1.230 m; o fantasma "Referência" 0,58 s à frente e a marca "freada da referência".

O Edge sem janela gerou as imagens desta vez.

### D.4, as capturas

As telas Coleta de dados, Ao vivo e Volta, em 1920 × 1080:
- **como:** o front de teste (`frontend-teste-8011`) e um backend de teste na porta 8011, com a pasta de dados no scratchpad (`AT_BACKEND_RUNTIME_ROOT`) e o repositório como fonte do coach. O cache da pista do repositório não mudou;
- **a Coleta** mostra "Volta de referência", "Sua melhor volta" e "coach desligado", com "Volta de referência: 1:24,552 (linha do projeto, meta atingida em 2026-11-15; executada pela IA do jogo na linha do projeto)";
- **a Volta** compara a volta 18 de 21/10 com "Volta de referência · 1:24,552" (+2,324 s), com o fantasma "Referência";
- **o Ao vivo,** sem o jogo, mostra o estado vazio. O fantasma ao vivo fica para o teste no jogo.

O backend e o front de teste foram encerrados (`taskkill /T`).

### D.5, os testes

- **backend, a suíte inteira:** **1043 passando**. A rodada inteira deu 1042 e 1 falha minha: o teste do construtor que exigia a busca das voltas da IA. Ele foi corrigido para a regra do ADR 0032 e passa (`test_lap_origin.py`, 36 passando). A falha de ambiente conhecida (`test_leitura`, por falta do `geometry.json`) não aparece na pasta principal, que tem o arquivo.
- **front:** 180 testes passando; `tsc` sem erro.
- **desktop:** 4 testes passando.
- **Lua** (`conferir_lua.py` contra o `lib.lua` do SDK do CSP): 34.612 tokens, nenhum erro de léxico, os blocos ok, toda a API e todos os métodos existem.

Saída em `_testes.txt` e `_conferir_lua.txt`.

## O construtor rodado (item 2) e a trava do store v2

**O `atualizar_coach`** rodou na pasta principal às 15:56, com o `acs.exe` fechado. Ele levou 48 min, porque a chave global do cache mudou (o código do `ml` mudou nos pedidos 47 a 50) e os passos 1 e 6 leram tudo.

**O que deu certo (passos 1 a 5):**
- o inventário leu as 155 sessões de Interlagos das duas pastas; as 15 sessões novas sem anotação foram rotuladas pelo indicador (de 15/10 a 12/11);
- **o modelo do coach foi refeito** (o anterior está em `data/reference_models/backup/vhe_interlagos.2026-11-15_16-05-27.antes-de-atualizar.json`):

| referência | volta | tempo |
|---|---|---|
| `volta_do_modelo` (a padrão) | `2026-11-15_02-47-12_vhe_interlagos_teste_m1#0008` | 84,550 s pelos microssetores do coach (1:24,552 na grade) |
| `minha_melhor` | `2026-10-24_13-43-32_vhe_interlagos#0003` (antes era a `#0017` de 21/10, 1:26,875) | 1:26,566 |

- 146 voltas suas no modelo; o limiar com a mediana de 0,188 s;
- o foco inicial contra a volta do modelo: os microssetores 30, 38 e 43.

**A trava, no passo 6 (store v2):**
- a checagem "a linha do jogo fica onde foi medida (pedido 34)" **falhou**;
- o store v2 ficou gravado com `aprovado: false`;
- o passo 7 (o relatório de evolução) **não rodou**.

**O que a checagem mostra:** as 3 sessões mais novas, que entraram no store agora, têm a linha do jogo mais longe do s = 0 do que o registrado (1,463 m, com tolerância de 0,10 m):

| sessão | voltas medidas | mediana | desvio |
|---|---:|---:|---:|
| `2026-11-01_19-47-03` | 6 | 1,606 m | 0,018 m |
| `2026-11-07_18-46-00` | 5 | 1,581 m | 0,080 m |
| `2026-11-12_22-57-03` | 4 | 1,573 m | 0,023 m |

- **As outras sessões passam** (de junho a 24/10), e a mediana de todas fica em 1,497 m, dentro da tolerância. O período de s = 0 a s = 0 contra o cronômetro do jogo passa (mediana 0,78 ms).
- **Não vem do pedido 51:** o código do store e da checagem não mudou. As 3 sessões foram gravadas pelo app do repositório (`data/recordings`, `appPackaged: false`), a de 01/11 na 0.5.0 e as de 07/11 e 12/11 na 0.7.0, e entraram no store pela primeira vez agora. **A causa não foi confirmada:** pode ser uma atualização do jogo ou do CSP, ou o gravador dessas versões.
- **Não contornei a trava:** não mudei a tolerância nem tirei as sessões.

**O que isso deixa como está:**
- **o store v2** foi regravado (721 voltas) e está marcado como reprovado. O app lê as voltas dele mesmo assim: a tela Volta funciona;
- **o relatório de evolução continua o de 22/10, contra a `#0013`.** Com os rótulos novos, a tela Evolução vai mostrar "volta de referência 1:24,828" até o passo 7 rodar. **É um rótulo errado enquanto a trava não for resolvida;**
- **o modelo do coach já está com a volta do modelo:** o coach e o rádio do app de desenvolvimento e do instalado (que lê o modelo do repositório) já usam a volta do modelo.

## Parte E: o instalador

**Gerado** com `npm run dist:win` na pasta `desktop`, às 17:10, com a árvore limpa, o jogo e o app fechados:
- **o arquivo:** `versoes\0.8.0-volta-do-modelo\Automobilista-Telemetria-Setup-0.8.0-volta-do-modelo.exe` (229 MB);
- **o sha256:** `573c110ef7789d162c574955596754c6e672299720cc62097613376d8b880342`;
- **o carimbo:** o commit `46e8db8`, a branch `etapa/volta-do-modelo`, `dirty: false`. O código é o mesmo do merge: depois dele, só entraram o índice das versões e este relatório.

**O que ele leva, conferido no pacote:**
- **a volta do modelo:** `resources\data\reference_models\vhe_interlagos.volta_do_modelo.json`, igual byte a byte ao do repositório, ao lado do `vhe_interlagos.optimal.json`;
- **o `voz.ps1`**, em `resources\backend\automobilista-backend\_internal\core\radio\`;
- **o front novo:** "Volta de referência" está no pacote. O único "Volta da IA" que sobrou é o da origem ("IA no volante: Volta da IA: não conta como sua"), de propósito.

**A instalação** (15/11, 17:23, depois do seu "pode instalar"):
- **antes:** o jogo e o app fechados, nenhum processo do app aberto, e a configuração em `"minha_melhor"`;
- **o comando:** o instalador com `/S /allusers /D=C:\Users\Dokas\AppData\Local\Programs\Automobilista Telemetria`, por cima da 0.7.0, como ela estava instalada (para todos os usuários, na mesma pasta). O sha256 foi conferido antes de rodar. Saída 0;
- **depois:**
  - o registro do Windows mostra `0.8.0-volta-do-modelo`;
  - a pasta tem o `vhe_interlagos.volta_do_modelo.json`, igual ao do repositório pelo sha256, e o `voz.ps1`;
  - **a configuração continua `"minha_melhor"`;**
  - o app não ficou aberto;
- **o índice das versões** (`versoes/LEIA-ME.md`) diz que a instalada é a mais atual.

**Para ver a volta do modelo no app instalado,** escolha "Volta de referência" na tela Coleta de dados. Ele está em "Sua melhor volta", como você deixou em 14/10.

**O app do jogo 0.6.0** vai pelo `instalar.ps1`, que você roda (de preferência junto com o app do Windows 0.8.0):

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Dokas\Desktop\f1-telemetry-analyzer\tools\csp_app\instalar.ps1
```

### No jogo, numa próxima sessão sua (não espera por ela)

1. **O fantasma** do minimapa e do mapa aproximado com o rótulo "Referência", e a diferença "para a referência" (com "Volta de referência" escolhida na Coleta; o app instalado está em "Sua melhor volta", que mostra "Sua melhor").
2. **A marca "freada da referência"** no mapa aproximado, antes das curvas.
3. **Uma fala com "atrás da referência"** (a frase do coach ou o resumo), e "Melhor da sessão" na melhor volta.
4. **O replay da curva** com "Referência" e a faixa do pedal "ref.".
5. **Na tela Volta,** "Volta de referência · 1:24,552" e o fantasma "Referência".

## Parte F: a documentação

- **ADR 0032**, com a linha no índice (`79990728`);
- **ADR 0009:** "a referência do coach é a volta do modelo (ADR 0032)";
- **ADRs 0021, 0027 e 0031:** uma linha de atualização cada, sobre os textos e a referência;
- **`docs/realidade_aumentada.md`:** o rádio (seção 2), as unidades (2.6), o minimapa (5.2) e o mapa aproximado (5.3);
- **`docs/app_para_producao.md`:** a 0.8.0, o app do jogo 0.6.0 e o risco do arquivo fora do git;
- **`docs/dashboard_inventario.md`:** o que o pedido 51 entregou;
- **além do pedido:** `docs/store_v2_e_evolucao.md` (a referência da evolução, seção 1.4) e as linhas da referência em `desktop/README.md` e `backend/packaging/README.md`;
- **`docs/backlog.md`** não foi editado (os itens estão abaixo).

## O que foi enviado ao GitHub

**Enviado por você em 15/11** (o `git push` é recusado pelo controle de permissões desta sessão), conferido com `git ls-remote origin`:

| ref | hash local | no remoto (15/11, 17:38) |
|---|---|---|
| `etapa/volta-do-modelo` | `dcabd0fc` | `dcabd0fc` ✔ |
| `develop` | `36152415` | `36152415` ✔ (antes `4c7bcbae`: o envio levou os pedidos 50 e 51 e os 2 commits só locais do 45) |

Os dois envios foram avanços simples, sem reescrever o remoto. Depois deles, só este registro ficou local, em `develop` (envio pequeno, quando quiser).

**O que estava antes do envio:**

**A conferência antes do primeiro envio** (os arquivos dos commits do pedido contra o `develop` de antes):
- nenhum arquivo acima de 50 MB;
- nenhuma gravação (`recordings/`, `data/recordings`, `data/ml`), nenhum `.ai` e nenhum segredo;
- o arquivo da volta do modelo e o instalador ficam fora do git.

| ref | hash local | no remoto (15/11, 17:20) |
|---|---|---|
| `etapa/volta-do-modelo` | `dcabd0fc` | não existe |
| `develop` | `c4869295` + o commit deste relatório | `4c7bcbae` (sem os pedidos 50 e 51 e sem 2 commits do 45) |

**Os comandos** (envios que não reescrevem o remoto: uma branch nova e um avanço simples):

```bash
git -C C:/Users/Dokas/Desktop/f1-telemetry-analyzer push origin etapa/volta-do-modelo
```

```bash
git -C C:/Users/Dokas/Desktop/f1-telemetry-analyzer push origin develop
```

Quando você avisar, confiro com `git ls-remote origin` que os hashes remotos são os locais.

## Itens para o backlog

1. **A linha do jogo nas sessões desde 01/11** (a trava acima): descobrir por que ela foi de 1,46 para 1,57–1,61 m, antes de mudar a checagem.
2. **"da referência" é mais longo que "da IA":** em 5 mensagens das 4 sessões, a causa ficou, mas o "contra quem" saiu. Se quiser que ele caiba, há duas opções: uma palavra mais curta ou o limite. As duas mudam a regra.
3. **As chaves dos JSONs da evolução com `ia` no nome** (`perda_para_ia_s`, `volta_da_ia_s`, `mediana_menos_ia_s`, `ia_g`): agora medem contra a volta do modelo. Renomear muda o formato `evolucao-sessao/1` e o front.
4. **O coach ainda não lê a referência por trecho** do pedido 50 (`referencia_por_trecho.json`, na pasta do 47).
5. **O `atualizar_coach` levou 48 min** porque a chave global do cache muda com qualquer mudança no `ml`.
6. **O script do rádio fora do tempo real** não guardou o rótulo do replay (olhou o lugar errado); ele é conferido pelo teste.
7. **A cópia da pista** (`vhe_interlagos_teste_m1`) continua instalada; o resultado do 50 já está gravado, e a volta do modelo já foi derivada.

## O que falta

1. ~~A instalação da 0.8.0~~: feita em 15/11, 17:23.
2. **O app do jogo 0.6.0,** pelo `instalar.ps1`, que você roda (o comando está na Parte E).
3. ~~O envio~~: feito e conferido em 15/11, 17:38.
4. **A trava do store v2,** num pedido próprio (backlog, item 1). Até lá, a tela Evolução mostra o relatório de 22/10, contra a `#0013`, com o rótulo "volta de referência".
