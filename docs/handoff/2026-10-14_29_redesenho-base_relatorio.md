# Relatório do pedido 29: redesenho, etapa 1 (sistema visual, hero, base do app, casca da tela Ao vivo e leitura do CSP)

- **Pedido:** `docs/prompts/2026-10-14_29_redesenho-base.md`
- **Branch:** `etapa/redesenho-base`, criada de `develop` (`adff57cd`), com merge em `develop`. Nada foi enviado ao remoto.
- **Commits e merge:**
  - `54c071a6` docs: pedido 29 (redesenho, etapa 1), skill frontend-design e as decisoes de 14/10 no inventario (arquivos do Cowork)
  - `d73e08d5` Sistema visual (em andamento): fontes OFL locais, variaveis de tema, classes dos componentes base e Tailwind apontando para as variaveis; index.html em pt-BR com o nome do produto e sem fontes da internet (pedido 29, Parte B)
  - `af585633` Relatório parcial do pedido 29: leitura do CSP (Parte A) e sistema visual em andamento (parado na Parte B por limite de uso)
  - `23d0dcd2` Sistema visual: Barlow Condensed no lugar da Big Shoulders, variaveis de tema ligadas ao app, componentes base em React, mensagem de radio montada do evidence do coach, contraste WCAG por script e teste, guia visual (pedido 29, Parte B)
  - `26504bee` Base do app: roteador por hash, navegacao de vidro com as seis telas, hero no topo de Sessoes, casca da tela Ao vivo, Sistema com diagnostico, depuracao e guia visual; retirada dos dados fixos; depuracao do mapa e dos paineis so em Sistema; mapa principal no sentido anti-horario (pedido 29, Parte C)
  - `af9126f9` Handoff do pedido 29 (Parte D): saida do tsc e do vitest (161 testes), capturas da janela real em 1920x1080 e 2560x1440, espelhamento antes e depois com uma volta real, tabela de contraste e quadros por segundo com e sem vidro
  - `11078f69` docs: sistema visual (paleta e o porque de cada cor, fontes e licencas, regras do vidro, componentes) e, no inventario, o que o pedido 29 entregou de cada item da secao 7 (pedido 29, Parte E)
  - `5d408bb1` Merge etapa/redesenho-base (pedido 29: sistema visual, hero, base do app, casca da tela Ao vivo e leitura do CSP para a realidade aumentada)
  - o commit deste relatório, com o patch: "Relatório do pedido 29: redesenho, etapa 1"
- **Arquivos de handoff** (sha256, 12 primeiros dígitos):
  - `docs/handoff/2026-10-14_29_redesenho-base_relatorio.md` (este)
  - `docs/handoff/2026-10-14_29_redesenho-base.patch`: de `adff57cd` até o merge, só `frontend`, `desktop` e `.claude/skills`, sem os arquivos do Cowork nem as capturas (`11f2c7e8dc6e`)
  - `docs/handoff/2026-10-14_29_redesenho-base_testes.txt`: `tsc --noEmit` e `vitest run` (`9e9ec584a923`)
  - `docs/handoff/2026-10-14_29_redesenho-base_contraste.json` (`fa57ee4f30c9`)
  - `docs/handoff/2026-10-14_29_redesenho-base_medidas.json`: quadros por segundo e sentido de giro antes e depois (`1a7cce93c674`)
  - `docs/handoff/2026-10-14_29_redesenho-base_espelhamento_antes.png` (`25fa5c4bc390`) e `…_espelhamento_depois.png` (`acae022f0d54`)
  - `docs/handoff/2026-10-14_29_redesenho-base_captura_01` a `_10`, cada uma em 1920×1080 e 2560×1440 (20 arquivos; lista na Parte D)
- **Canvas de design:** https://claude.ai/artifact/7LhHGi98Yjh18S3hFNQheV, com as pranchas do sistema visual, dos componentes, de Sessões com o hero, do hero subindo e do Ao vivo. É privado: só abre para quem você compartilhar.

**O que não mudou:**
- Nenhum arquivo do backend: `git diff --stat adff57cd 5d408bb1 -- backend` sai vazio. Por isso a suíte do backend não muda.
- Nenhum modelo, critério, store ou regra do coach.
- O `productName` do instalador, o `appId` e a pasta de dados.
- Não instalei nem atualizei pacotes (npm ou pip). A única coisa baixada foi a fonte Barlow Condensed, com a sua autorização no chat.
- Não gerei instalador.
- Não mexi no app instalado nem nos arquivos do jogo: a Parte A só leu.

## Em resumo

1. **Parte A:**
   - **CSP:** 0.2.11 (build 3465). A API Lua dele tem janela na tela, HTTP para `127.0.0.1:8000` (no máximo duas requisições ao mesmo tempo), som a partir de um arquivo, o estado do carro e desenho 3D na pista. **Não tem síntese de fala.**
   - **Content Manager:** 0.8.2895.40668.
   - **Vozes em português no Windows:** Maria (SAPI 5), e Maria e Daniel (OneCore).
2. **Parte B:**
   - **paleta:** carbono `#08090B` e vermelho de transmissão `#E10600`; as cores de dado do protótipo continuam;
   - **fontes:** Barlow Condensed, Instrument Sans e IBM Plex Mono, como arquivos locais com a licença OFL;
   - **vidro:** só nos recipientes, com fallback sem transparência;
   - **contraste:** todo texto passa no AA. O pior caso é o branco no botão vermelho, com 4,97:1;
   - **desempenho:** 75 quadros por segundo com e sem vidro (o teto do monitor), em 1920×1080 e 2560×1440.
3. **Parte C:**
   - **casca e navegação:** a casca nova tem as seis telas, com navegação por endereço (`#/tela`);
   - **hero:** fica no topo de Sessões, mostra o backend subindo pelo estado real (46 s na primeira abertura isolada) e só números reais;
   - **Ao vivo:** a casca, com a gravação, os canais e o rádio;
   - **limpeza:** saíram os dados fixos e a depuração das telas do piloto;
   - **espelhamento:** o mapa principal agora gira no anti-horário. Foi conferido com uma volta real, antes e depois;
   - **Electron:** a janela abre antes de o backend responder.
4. **Parte D:**
   - **testes:** o `tsc` passa, e o `vitest` passa com **161 testes** (eram 145; entraram 16);
   - **capturas:** saíram da janela real do Electron, isolada (`AT_DESKTOP_USER_DATA_DIR`).
5. **Parte E:** `docs/sistema_visual.md` e o fim da seção 7 do inventário.
6. **Achados fora do pedido:**
   - o gravador junta duas passagens na mesma volta;
   - a lista de sessões e a conferência medem as voltas de jeitos diferentes;
   - as frases do coach saem sem acento.
7. **O pedido 30** (complemento, que passa as telas Volta, Evolução e Sessões para o protótipo A) apareceu durante o trabalho. Não comecei: ele espera o seu "Execute".

## Antes de começar

- **A Parte G do pedido 28 não tinha fechado.** O pedido 29 diz para começar depois dela. Você decidiu no chat seguir agora: o pedido 29 não toca no backend, no store nem no coach.
- **A skill estava em outro lugar:** veio em `docs/prompts/anexos-29/frontend-design/SKILL.md`, e não em `.claude/skills/frontend-design/SKILL.md`. Commitei as duas cópias em `54c071a6`.
- **O app instalado, para a Parte G:** às 10:48 de hoje ele estava aberto com o backend em `--onedir`, que é o formato da 0.3.0. O caminho era `resources\backend\automobilista-backend\automobilista-backend.exe`. Pelo log dele, o app foi fechado às 15:31. O `versoes\LEIA-ME.md` das 10:43 ainda dizia 0.1.7: parece que você instalou a 0.3.0 depois disso. Confira na Parte G.

## Parte A: leitura para a realidade aumentada (só leitura)

Nada foi instalado, copiado ou mudado na pasta do jogo.

1. **Custom Shaders Patch:** instalado em `D:\SteamLibrary\steamapps\common\assettocorsa`.
   - **Versão 0.2.11, build 3465:**
     - lida em `extension\installed.log` (`version: 0.2.11`, `build: 3465`; o arquivo diz que a instalação foi pelo Content Manager);
     - confirmada em `extension\config\data_manifest.ini` (`[VERSION] SHADERS_PATCH=0.2.11`, `SHADERS_PATCH_BUILD=3465`).
   - **A pasta `apps\lua` existe**, com seis apps:
     - `CMRT-Essential-HUD` (1.0.13);
     - `PureConfig` (1.80);
     - `PurePP` (0.52);
     - `PurePlanner` (1.78);
     - `TrafficTool` (só a pasta `data`);
     - `vrc_advanced_setup` (1.5.1).
2. **Content Manager:** `C:\Users\Dokas\Desktop\latest\Content Manager.exe`, **versão 0.8.2895.40668**. Lida nas propriedades do executável, sem abrir o programa. Os dados dele ficam em `%LOCALAPPDATA%\AcTools Content Manager`.
3. **O que a API Lua do CSP oferece nesta versão.** As definições estão em `extension\internal\lua-sdk\ac_apps\lib.lua`; os números são linhas desse arquivo.
   - **Janela ou painel na tela:**
     - `ui.transparentWindow` (15802), `ui.toolWindow` (15815) e `ui.beginTransparentWindow` (12045);
     - texto com `ui.dwriteDrawText` (12450) e retângulos com `ui.drawRectFilled` (12372);
     - a janela é declarada no `manifest.ini` com `FUNCTION_MAIN` (exemplo: `apps\lua\CMRT-Essential-HUD\manifest.ini`).
   - **HTTP para `127.0.0.1:8000`:**
     - `web.get` (6925), `web.post` (6936) e `web.request` (6948), que aceitam HTTP e HTTPS;
     - **limite: duas requisições ao mesmo tempo**, como diz o comentário das três funções;
     - os tempos de espera ficam em `web.timeouts` (6914).
   - **Som:**
     - `ac.AudioEvent.fromFile({ filename = …, use3D = false, loop = false })` (15224);
     - `ui.MediaPlayer(source, audioParams)` (16026), que toca um arquivo de áudio fora da tela;
     - **não há síntese de fala no SDK** (nenhuma ocorrência de "speech" ou "tts"). O áudio do rádio teria de chegar pronto, como arquivo.
   - **Estado do carro:** `ac.getCar(index)` (6597) devolve `ac.StateCar`, com:
     - `splinePosition` (4092), de 0 a 1 na volta;
     - `speedKmh` (4073);
     - os pedais e o volante: `gas` (4062), `brake` (4063), `clutch` (4064) e `steer` (4065);
     - `lapTimeMs` (4189), `isAIControlled` (4113) e `position` (4050).
   - **Desenho no mundo 3D:**
     - `render.debugLine` (11972), `render.quad` (11933), `render.circle` (11916), `render.rectangle` (11924) e `render.glBegin`/`glVertex` (11896/11899);
     - numa app, o desenho entra pelo `manifest.ini` com `[RENDER_CALLBACKS] TRANSPARENT = Draw3D` (exemplo: `apps\lua\PureConfig\manifest.ini`, linhas 10–11).
4. **O que o backend já entrega para o rádio:**
   - **`GET /api/live/coach`** (`backend/routers/live.py:209`):
     - devolve `{status, source: "event_bus", eventCount, events}`, com **as 20 mais recentes, a mais nova primeiro**, de uma fila de 50 (`main.py:155-157`);
     - não tem frequência própria: é lida quando alguém pede;
     - **só entram nela os `coaching_event`** (`main.py:920`). O resumo de fim de volta sai como `engineer_speech` e **vai só pelo WebSocket**.
   - **`MAX_PHRASES_PER_LAP = 3`** (`core/live/driving_coach.py:90`): uma frase por microssetor de foco (`FOCUS_SECTORS = 3`), com pelo menos 3 s entre frases.
   - **Quando cada frase nasce:**
     - **a frase de diferença:** quando um microssetor de foco fecha e a perda passa o limite (`_close_sector`, linhas 440–478; montada em `_emit_reference_event`, 593–644). O `evidence` traz o microssetor, o seu tempo, o da referência, a perda, a freada e a mínima;
     - **o foco:** quando os microssetores de foco mudam (`_emit_focus_event`, 389–407);
     - **o resumo:** na linha de chegada (`_speak_lap_summary`, 703–755), só pelo WebSocket.
5. **Vozes em português** (consultadas pelo `System.Speech` e pelo registro, só leitura):
   - SAPI 5: **Microsoft Maria Desktop (pt-BR)** e Microsoft Zira Desktop (en-US);
   - vozes modernas (`Speech_OneCore`): **Microsoft Daniel (pt-BR)** e **Microsoft Maria (pt-BR)**.
   - **Há voz pt-BR instalada.**

## Parte B: sistema visual

O sistema completo, com o porquê de cada cor, está em `docs/sistema_visual.md`. Também dá para vê-lo na tela Sistema › Guia visual (captura 10) e no canvas.

- **A direção:** "carbono, vidro e rádio", a partir da opção A do protótipo e da skill `frontend-design`.
  - **O fundo:** carbono quase preto com profundidade, com um brilho vermelho, um brilho frio e uma trama de carbono, numa camada parada.
  - **O vermelho:** um só, de destaque, para o que está acontecendo: a tela ativa, a gravação e o rádio.
  - **A marca:** um traço de pista com um ponto. Nada imita a F1, o WEC ou a FIA.
- **A paleta:**
  - **as cores:**
    - fundo `#08090B`, superfície opaca `#0E1013`;
    - texto `#F2F4F5`, `#B4BCC4` e `#8E98A2`;
    - vermelho `#E10600`, e `#FF4A3D` quando o vermelho é texto;
  - **as cores de dado do protótipo continuam:** freio, acelerador, parcial, perda e ganho;
  - **"Você" e a referência:** "Você" em branco e a referência em cinza azulado;
  - **cronometragem:** roxo, verde e amarelo, só em tempos e com o significado da F1. Neste pedido, só a "sua melhor volta" do hero aparece em verde;
  - **cor solta:** nenhuma nos componentes novos. Os nomes antigos (`--bg-core`, `--text-1`…) apontam para a paleta nova.
- **As fontes**, como arquivos locais em `frontend/src/assets/fonts`, com a licença OFL 1.1 ao lado:
  - **Barlow Condensed** (títulos e números grandes): a do protótipo, com `tnum`. Baixada de `google/fonts` (pasta `ofl/barlowcondensed`) com a sua autorização. **Substituiu a Big Shoulders** da primeira tentativa, que não tinha `tnum`;
  - **Instrument Sans** (texto): no lugar da IBM Plex Sans, que não estava no computador; a autorização foi só para a Barlow;
  - **IBM Plex Mono** (dados).
  - Conferi as três com o fontTools: todos os acentos, o menos (−) e o ponto médio (·).
  - O `index.html` e o `App.css` não buscam mais fontes no Google Fonts.
- **O vidro:**
  - **como é:** `rgba(22,25,29,0,55)` com desfoque de 18 px, borda e filete de luz;
  - **o número nunca fica sobre vidro puro:** gráficos, tabelas, mapas e cartões ficam numa superfície opaca dentro dele;
  - **uma camada de desfoque por região:**
    - Volta: 1 (a navegação);
    - Sessões: 3;
    - Sistema › Depuração: 5;
  - **sem transparência:** com `prefers-reduced-transparency` ou pelo botão "Sem transparência" em Sistema › Depuração;
  - **sem movimento:** com `prefers-reduced-motion`, a volta do hero aparece inteira e nada pulsa.
- **Os componentes base** (`components/ui/base.tsx` e `theme/componentes.css`):
  - painel de vidro, cartão de número, chip e segmentado, tabela, dica e botões;
  - etiqueta de estado, com os estados da Coleta: ok, ausente, parado, fora da faixa, taxa baixa e sem dados. Cada um tem desenho e texto, além da cor;
  - **mensagem de rádio:** a frase é montada em português a partir do `evidence` do coach (`utils/radio.ts`): "+0,31 s para a volta da IA neste trecho · 3,12 s contra 2,81 s · a IA freia 12 m depois de você". Os números e a regra são os do coach; só a escrita muda. "Setor N" vira microssetor.

**Contraste** (WCAG 2.1; texto sobre o vidro composto no pior caso do fundo):
- **Como é calculado:** a tabela sai de `node frontend/scripts/contraste.ts` e é conferida pelo teste `src/theme/contraste.test.ts`.
- **As superfícies:** `vidro` `#251316` sobre o brilho vermelho; `vidro-frio` `#161c23`; `opaca-no-vidro` `#101013`; `dica` `#231a1d`; `superficie` `#0e1013`; `sem-transparencia` `#14171b`.

| texto | cor | uso | vidro | vidro-frio | opaca-no-vidro | dica | superficie | sem-transparencia | pior | AA |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `--texto-1` | #f2f4f5 | títulos, números e corpo | 16,07 | 15,61 | 17,20 | 15,39 | 17,27 | 16,29 | 15,39 | passa |
| `--texto-2` | #b4bcc4 | texto de apoio | 9,23 | 8,96 | 9,87 | 8,84 | 9,92 | 9,36 | 8,84 | passa |
| `--texto-3` | #8e98a2 | rótulos e legendas | 6,05 | 5,87 | 6,47 | 5,79 | 6,50 | 6,13 | 5,79 | passa |
| `--vermelho-claro` | #ff4a3d | vermelho como texto | 5,32 | 5,16 | 5,69 | 5,09 | 5,71 | 5,39 | 5,09 | passa |
| `--perda` | #ffa24a | perda (+ e o número) | 8,88 | 8,62 | 9,50 | 8,50 | 9,54 | 9,01 | 8,50 | passa |
| `--ganho` | #6f9bff | ganho (− e o número) | 6,59 | 6,40 | 7,05 | 6,31 | 7,08 | 6,68 | 6,31 | passa |
| `--tempo-verde` | #2bd67b | a sua melhor | 9,30 | 9,02 | 9,94 | 8,90 | 9,99 | 9,42 | 8,90 | passa |
| `--tempo-roxo` | #b266ff | a melhor de todas | 5,27 | 5,11 | 5,63 | 5,04 | 5,66 | 5,34 | 5,04 | passa |
| `--tempo-amarelo` | #f5c542 | sem melhora | 10,93 | 10,62 | 11,70 | 10,47 | 11,75 | 11,08 | 10,47 | passa |
| `--estado-ok` | #4cc38a | etiqueta ok | 8,01 | 7,77 | 8,56 | 7,66 | 8,60 | 8,12 | 7,66 | passa |
| `--estado-aviso` | #f2c14e | etiqueta de aviso | 10,57 | 10,26 | 11,30 | 10,12 | 11,35 | 10,71 | 10,12 | passa |
| `--estado-erro` | #ff7a6b | etiqueta de erro | 6,97 | 6,76 | 7,45 | 6,67 | 7,48 | 7,06 | 6,67 | passa |
| `--texto-sobre-vermelho` | #ffffff | texto do botão vermelho | 4,97 (sobre `--vermelho`) | — | — | — | — | — | 4,97 | passa |

**Desempenho** (`…_medidas.json`):
- **Como medi:**
  - quadros por segundo por `requestAnimationFrame`, durante 10 s, na janela real do Electron;
  - o mapa estava animado, com a última volta de 13/10 tocando no replay a 0,5x;
  - o vidro foi ligado e desligado duas vezes em cada caso.

| tela | viewport | camadas com desfoque | vidro ligado (quadros/s; p95) | sem transparência (quadros/s; p95) |
|---|---|---:|---|---|
| Volta (mapa animado) | 1920×1080 | 1 | 75; 75 (13,4 ms) | 75; 75 (13,4 ms) |
| Sistema › Depuração (mapa animado dentro do vidro) | 1920×1080 | 5 | 75; 75 (13,4 ms) | 75; 75 (13,4 ms) |
| Volta | 2560×1440 | 1 | 73,5; 74,6 (13,4 ms) | 68,7; 75 (26,7 e 13,4 ms) |
| Sistema › Depuração | 2560×1440 | 5 | 75; 75 (13,4 ms) | 75; 75 (13,4 ms) |

- **O resultado:** 75 quadros/s é o teto do monitor (vsync), e **o vidro não custou quadros em nenhum caso.**
- **As quedas:** as duas em 2560×1440 (73,5 e 68,7) foram uma com e uma sem vidro. São ruído, não o desfoque.
- **O limite de camadas** ficou nas regras: uma por região, sem vidro dentro de vidro e com o fundo parado.

## Parte C: base do app

1. **Navegação e telas:**
   - **a navegação:** uma barra de vidro no topo, no lugar do trilho lateral, com as seis telas: Sessões, Ao vivo, Volta, Evolução, Coleta de dados e Sistema;
   - **o endereço:** fica no hash (`#/volta`, `#/sistema/guia`…). Recarregar volta para a mesma tela; o hash é o que funciona com o `file://` do Electron;
   - **as telas antigas:** Volta recebe a antiga Pista (`Dashboard`), e Evolução recebe a antiga Análise, com as quatro abas acentuadas;
   - **Coleta de dados:** mesmo conteúdo e comportamento, com o visual novo. Corrigi também as bordas coloridas: elas usavam `var(--x)55`, que não é CSS válido, e não apareciam;
   - **Sistema:** Diagnóstico (os painéis da antiga `DiagnosticsPage`), Depuração e Guia visual.
2. **Primeiro passo do inventário:**
   - **idioma e título:** `lang="pt-BR"`. O título da página e o da janela do Electron (`desktop/main.js`) são "Sistema de Telemetria e Otimização de Trajetórias";
   - **nomes antigos que saíram:** "Motorsport Intelligence Workstation" (o cabeçalho da Volta virou "Volta · ao vivo e replay"), "AT TELEM" e "Telemetria Assistida para Simulacao Automobilistica";
   - **tempos e diferenças:** em M:SS,mmm, com vírgula e sinal, também nas telas antigas (`formatLapTime` e `formatDelta`);
   - **retirada dos dados fixos (problema B):**
     - as três "AI RECOMMENDATIONS" fixas;
     - "SPATIAL" e "AI_CORE" sempre acesos;
     - "BUILD v13.0";
     - a fonte "F1-25 UDP" e "IRACING SDK", com o Start e o Stop que chamavam `/api/streaming/*`, rota que não existe;
     - "Neural-linked coaching // Priority enabled".

     O "GRAVAÇÃO 60 HZ" já era a taxa real desde o pedido 28.
   - **depuração para Sistema (problema C):**
     - **no mapa:** o `TrackRenderer` ganhou a opção `depuracao`, desligada na Volta e ligada só em Sistema › Depuração. Com ela desligada somem o PERF, os modos DIAG, RAW, PTS, SEGS, SMTH e SPEED (ficam LINE e PEDAL), a legenda "VIS/RAW/MICRO", o HUD "N m | N pts | fonte" e o "World X/Y/Z" dos oponentes;
     - **nos painéis:** o "LAP DBG" dos traços foi para "Estado da volta" em Sistema, o JSON do `evidence` para "Eventos crus do coach" em Sistema, e o "P n / REF n" saiu. "Phase 13" virou "portões de qualidade".
3. **Espelhamento do mapa principal:**
   - **a correção:** `applyCameraTransform` (`CameraController.tsx`) usa `scale(s, −s)` (constante `SENTIDO_DO_EIXO_Y`), como o minimapa e o relevo;
   - **o que vem junto:**
     - a projeção mundo→tela dos oponentes (`worldToScreen`) acompanha a inversão;
     - os textos desenhados no espaço do mundo (o rótulo dos oponentes e o número dos segmentos) ficam em pé;
     - o carro gira certo sem mudança, porque a pista e o nariz giram juntos.
   - **conferido com uma volta real:** a volta 14 de 13/10, pausada em 0:25,005, no replay da tela Volta, com a visão geral do circuito:
     - **antes** (`…_espelhamento_antes.png`): build com o sinal antigo (`+1`), gerado só para a conferência e fora do repositório. O mapa principal é o reflexo vertical do minimapa, e o carro aparece na metade de baixo da reta oposta;
     - **depois** (`…_espelhamento_depois.png`): o mapa principal tem o mesmo desenho do minimapa, e o carro está no mesmo lugar dos dois;
     - **o número** (`frontend/scripts/sentido_do_mapa.ts`, área com sinal do traçado na tela, 2.690 amostras): antes **+397.682 m², sentido horário**; depois **−397.682 m², sentido anti-horário**, como Interlagos.
4. **Hero no topo de Sessões** (capturas 01 a 03):
   - **na abertura:**
     - a janela agora abre antes de o backend responder; antes, o Electron esperava o `/api/health` e só então abria;
     - o hero consulta o `/api/health` a cada segundo e mostra a espera real: "/api/health ainda não respondeu · 12 s desde a abertura · 6 tentativas";
     - não há barra de progresso. Na abertura isolada, com o cache da pista refeito, o backend respondeu em **46 s**.
   - **os números, todos de dado real e cada um de uma fonte:**
     - **última sessão:** a data vem de `/api/sessions`; as voltas válidas e a melhor volta vêm da **conferência da Coleta**, a régua do store v2. Na captura: **13/10 · 19:24, 9 voltas válidas, melhor 1:29,768**, como no pedido 28. Se a sessão ainda não foi conferida, o hero oferece "Conferir voltas e melhor volta", que chama a rota da Coleta;
     - **sua melhor volta e volta da IA:** as referências do modelo do coach (`/api/coleta/antes`): **1:29,389** (04/10, volta 18, coach de 10/10) e **1:24,828**, com "sua melhor +4,561 s";
     - **M1:** **0 de 5**, de `/api/coleta/m1/oficial`;
     - **pronto para gravar:** "não grava ainda: o Assetto Corsa está fechado", pelo portão de captura.
   - **a pista:**
     - Interlagos desenhada com `drawTrackSurface` (asfalto, pintura classificada e zebras do cache, as mesmas camadas do mapa do app), no sentido anti-horário;
     - por cima, a sua melhor volta, animada uma vez e com cabeça vermelha. Com `prefers-reduced-motion`, aparece inteira.
   - **como a volta é achada:**
     - **pelo tempo:** o número da volta no store v2 (`#0018`) não é o número da volta no jogo. Fica a volta gravada cuja duração está a menos de 0,05 s do tempo da referência, e só se for única. Em 04/10, `#0018` é a volta 5 do jogo (89,388 s contra 89,389 s);
     - **o trecho:** dessa volta, só o trecho cujo relógio fecha no tempo da referência (ver achado 1).
   - **sem dado:** "sem dados". Enquanto o backend sobe: "aguardando o backend". Nada é inventado.
   - **"IA"** no texto é só a IA do jogo.
   - **os atalhos:** Coleta de dados, Última volta e Evolução. "Última volta" abre a última volta válida da sessão mais recente no replay e leva para a tela Volta. Isso também resolve o problema E do inventário: o replay começava na Análise e o app não trocava de tela.
5. **A casca da tela Ao vivo** (captura 04):
   - **a gravação e os canais:** vêm de `/api/coleta/ao-vivo` a cada 2 s, com taxa, amostras, descartadas, fila, quem pilota e os cinco grupos com a etiqueta de estado;
   - **o rádio:** `/api/live/coach` a cada 2 s, a mais nova em cima, com as frases em português montadas do `evidence`;
   - **o que vem depois:** um aviso diz que o mapa ao vivo, o fantasma e o rádio no jogo chegam no próximo pedido.
6. **Só rotas que já existem.** No cliente entraram apenas `getLiveCoach` (a rota já existia) e um tempo de espera no `getHealth`.

## Parte D: testes e capturas

1. **Testes** (`…_testes.txt`):
   - **`tsc --noEmit`:** passa;
   - **`vitest run`:** **161 testes em 12 arquivos**, todos passando. Eram 145; os 16 novos cobrem:
     - as rotas;
     - a mensagem de rádio;
     - os números do hero: a conferência, a volta pelo tempo e o trecho da volta;
     - o contraste;
     - o sentido do eixo da câmera.
   - **O backend não mudou:** o diff dele é vazio.
2. **Capturas da janela real do app:**
   - **o app:** Electron do repositório com o front construído (`AT_DESKTOP_MODE=production`), comandado pelo DevTools Protocol (`--remote-debugging-port=9229`), com viewport emulado em 1920×1080 e 2560×1440;
   - **o isolamento:**
     - **perfil do Electron:** `AT_DESKTOP_USER_DATA_DIR` no scratchpad;
     - **backend:** o próprio Electron o subiu (`AT_BACKEND_RUNNER=python`, porta 8011), com a raiz de dados no scratchpad. O cache da pista foi refeito lá, não no repositório;
     - **gravações:** uma pasta no scratchpad com links físicos para as sessões de outubro do repositório. Os índices que o backend grava ao ler ficaram só lá;
     - **app instalado:** a porta 8000 estava com ele aberto, e não mexi.
   - **`%APPDATA%\Automobilista Telemetria`:**
     - comparei um retrato antes e depois (nome, tamanho e data de 390 a 392 arquivos);
     - **as diferenças são todas do app instalado:** o log dele registra "Backend process stopped" às 15:31:08, quando ele foi fechado, e mudaram os logs, o `Session Storage` e o `DIPS` nesse horário;
     - o Electron de teste gravou só no scratchpad.
   - **As capturas** (`docs/handoff/2026-10-14_29_redesenho-base_captura_*`):
     - `01_hero-subindo_1920x1080` e `02_hero-subindo_2560x1440`: o backend subindo (12 e 20 s);
     - `03_sessoes-hero-pronto`: o hero pronto e as sessões gravadas;
     - `04_ao-vivo`, com o jogo fechado e os canais "sem dados";
     - `05_volta`, a antiga Pista na casca nova;
     - `06_evolucao`, a antiga Análise na casca nova;
     - `07_coleta`, página inteira;
     - `08_sistema-diagnostico`, página inteira;
     - `09_sistema-depuracao`;
     - `10_guia-visual`, página inteira.

     Da 03 em diante, cada captura tem as duas resoluções.
   - **o espelhamento antes e depois:** está na Parte C.3.
3. **A tabela de contraste e os quadros por segundo:** estão na Parte B.

## Parte E: documentação

- **`docs/sistema_visual.md`:** a paleta e o porquê de cada cor, as fontes e as licenças, as regras do vidro, os componentes e o movimento.
- **`docs/dashboard_inventario.md`:** no fim da seção 7, "O que o pedido 29 entregou", item por item.

## Achados fora do pedido

1. **O gravador junta duas passagens na mesma volta.**
   - **O caso:** em `2026-10-04_02-24-04`, a "volta 5" do gravador (`/api/sessions/{id}/laps` e `/api/laps/{id}/replay`) tem 9.797 amostras de duas passagens: uma de 85,107 s e outra, 46 min depois, de 89,388 s.
   - **A causa:** o contador de voltas do jogo voltou a 5 quando a sessão recomeçou, e o gravador agrupa pelo número da volta.
   - **O que fiz:** o hero traça só o trecho que fecha no tempo da referência.
   - **O que não fiz:** o replay da tela Volta e a análise que usam essa volta ainda recebem as duas passagens. Não mexi no gravador (é backend). Proponho um pedido próprio, com o mesmo critério da conferência: a volta começa quando o relógio zera.
2. **A lista de sessões e a conferência dão números diferentes.** Em 13/10, `/api/sessions` dá 13 voltas válidas e melhor 1:29,757; a conferência dá 9 e 1:29,768, que são a régua do store v2. O hero e a lista de Sessões usam a conferência. A tela Evolução (antiga Análise) ainda mostra os tempos do gravador.
3. **As frases do coach saem sem acento e com ponto decimal** ("0.31s atras … voce"). A tela monta a frase em português a partir do `evidence`, sem mudar o coach. O resumo de fim de volta não tem `evidence` e vai só pelo WebSocket; no rádio do jogo, ele vai precisar do mesmo tratamento.
4. **Com o backend ocupado lendo uma gravação grande,** o `/api/health` passou de 2,5 s. Agora o limite é de 8 s depois que o backend já respondeu, e o hero não recomeça a contagem depois de uma queda.

## O que falta e o que precisa de decisão

- **O pedido 30** (`docs/prompts/2026-10-14_30_complemento-prototipo-a.md`) apareceu durante este pedido. Ele leva Volta, Evolução e Sessões para o protótipo A, com rotas novas só de leitura, nesta mesma branch e neste mesmo relatório. **Não comecei; espera o seu "Execute o pedido em …".** O merge deste pedido já está em `develop`, e a branch continua para o 30.
- **A Parte G do pedido 28** continua esperando o seu aviso. Pelo log, o app instalado de hoje já é a 0.3.0 (backend `--onedir`).
- **Decisões suas:**
  - **o texto:** fica com a Instrument Sans, ou quer também a IBM Plex Sans do protótipo (precisaria baixar)?
  - **o achado 1** (o gravador junta passagens): proponho um pedido próprio.
- **O canvas** ainda mostra a Big Shoulders e as cores de "parado" e "taxa baixa" trocadas em relação ao código (no código, parado é vermelho e taxa baixa é âmbar). Vale o código e `docs/sistema_visual.md`; atualizo o canvas em seguida.
