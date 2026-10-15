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
7. **O pedido 30** (complemento, que passa as telas Volta, Evolução e Sessões para o protótipo A) foi feito depois, nesta mesma branch: está na seção "Complemento: pedido 30", no fim deste relatório.

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

- **O pedido 30** (`docs/prompts/2026-10-14_30_complemento-prototipo-a.md`) foi feito: veja a seção "Complemento: pedido 30", logo abaixo.
- **A Parte G do pedido 28** continua esperando o seu aviso. Pelo log, o app instalado de hoje já é a 0.3.0 (backend `--onedir`).
- **Decisões suas:**
  - **o texto:** fica com a Instrument Sans, ou quer também a IBM Plex Sans do protótipo (precisaria baixar)?
  - **o achado 1** (o gravador junta passagens): proponho um pedido próprio.
- **O canvas** foi atualizado depois do merge (versão 8): os títulos e números grandes estão na Barlow Condensed, e "parado" e "taxa baixa" têm as cores do código (parado vermelho, taxa baixa âmbar).

## Complemento: pedido 30 (as telas do protótipo A)

- **Pedido:** `docs/prompts/2026-10-14_30_complemento-prototipo-a.md`
- **Branch:** `etapa/redesenho-base`, a mesma do pedido 29, com merge em `develop`. Nada foi enviado ao remoto.
- **Commits e merge:**
  - `9c5db42f` docs: pedido 30 (complemento do pedido 29: as telas do protótipo A agora), arquivo do Cowork
  - `30985f8e` Rotas de leitura para Sessões, Volta e Evolução: relatório de evolução, linhas de uma volta do store v2, referências do coach e geometria oficial, só lendo os arquivos do repositório configurado (seção 5)
  - `a3d1e694` Medidas da tela Volta no método do relatório de evolução (porte de `evolution.py` e `microsectors.py`), com as curvas do `sessao_*.json` encaixadas na grade, e o script que confere a tela contra o protótipo A e o `por_volta` oficial (seções 3 e 6)
  - `9b4926f2` Telas Volta e Evolução do protótipo A (seção 3)
  - `f3356b10` Tela Sessões do protótipo A (seção 3); atalho "Última volta" para a tela Volta e o nome completo do produto na navegação
  - `c21621d9` Leituras das telas Sessões, Volta e Evolução tentam de novo enquanto o backend não responde, com o erro em português
  - `30b4808d` Sessões: a tendência da mediana por sessão no texto do gráfico
  - `ee3721e4` Tabelas por curva de Volta e Evolução com o nome da curva em destaque
  - `7dde6cdd` Merge etapa/redesenho-base (pedido 30: as telas Sessões, Volta e Evolução do protótipo A, com as rotas de leitura)
  - o commit deste relatório, com o handoff e o inventário: "Relatório do pedido 30: as telas do protótipo A"; `develop` avança até ele
- **Arquivos de handoff** (sha256, 12 primeiros dígitos):
  - `docs/handoff/2026-10-14_30_complemento-prototipo-a_relatorio.md` (este)
  - a seção "Complemento: pedido 30" em `docs/handoff/2026-10-14_29_redesenho-base_relatorio.md`, com o mesmo conteúdo
  - `docs/handoff/2026-10-14_30_complemento-prototipo-a.patch`: de `9c5db42f` até `ee3721e4`, só `backend` e `frontend` (`06530806bdec`)
  - `docs/handoff/2026-10-14_30_complemento-prototipo-a_testes.txt`: `tsc --noEmit`, `vitest run`, o build e o `pytest` do backend (`7ccd11609f52`)
  - `docs/handoff/2026-10-14_30_complemento-prototipo-a_conferencia.json`: a conferência da volta 8 contra a IA, curva a curva e microssetor a microssetor (`bb6b64cdafc1`)
  - `docs/handoff/2026-10-14_30_complemento-prototipo-a_lado-a-lado_*`: 5 telas em 1920×1080 e 2560×1440 (10 arquivos; lista em "Capturas lado a lado")

### Em resumo

1. **As telas Sessões, Volta e Evolução seguem o protótipo A** (opção A, escura e densa), com as cores, as fontes e o vidro do pedido 29. Todos os números vêm das rotas do app; sem dado, a tela diz "Sem dados" e por quê.
2. **Pista e Análise deixaram de ser telas.** O que sobrou delas foi para onde a seção 6 do inventário manda; as frases do coach ficaram embaixo do replay da Volta e marcadas no mapa.
3. **Cinco rotas novas, só de leitura**, com 7 testes. Nenhuma calcula nada; nenhuma tela precisou da projeção do runtime.
4. **A conferência bate.** Na volta 8 de 05/10 (20:33) contra a volta da IA:
   - o tempo (1:30,629) e a diferença (+5,800 s) são iguais no app, no protótipo e no relatório;
   - a perda por curva bate com o `por_volta` oficial (diferença 0) e com o protótipo (no máximo 0,001 s);
   - a diferença por microssetor bate com o protótipo (no máximo 0,0005 s, arredondamento);
   - a diferença no modo por curva bate com o protótipo (no máximo 0,002 s, porque o protótipo usa uma grade de 8 m).
5. **Capturas lado a lado** (app à esquerda, protótipo A à direita) de Sessões, Volta, Evolução, Coleta de dados e Sistema, em 1920×1080 e 2560×1440, da janela real do Electron, isolada.
6. **Testes:** o `tsc` passa; o `vitest` passa com **173 testes em 14 arquivos** (eram 161; entraram 12); o `pytest` do backend dá **743 passando e 1 falha**. A falha é `backend/test_ws_client.py`, um script antigo solto na raiz do backend (de `5eb00c71`, sem mudança neste pedido): ele é `async` e precisa de um plugin que não está instalado. As 7 rotas novas passam.
7. **Achados fora do pedido:** o coach conta os microssetores a partir de 0, a rota das frases do coach só procura gravações em duas pastas, e o hero e o relatório diferem em 1 ms nos tempos das referências.

### O que mudou, por parte

#### Rotas novas (seção 5)

Ficam em `backend/routers/leitura.py`, com a leitura em `backend/core/leitura/arquivos.py`. Todas leem a pasta do repositório configurada na Coleta de dados (pedido 28), por `main.app_config.coach_root()`, e rodam fora do laço do servidor (`asyncio.to_thread`).

| Rota | O que lê | O que devolve |
|---|---|---|
| `GET /api/evolucao/resumo` | `data/ml/evolucao/resumo.json` | o JSON como está, e a lista dos `sessao_*.json` |
| `GET /api/evolucao/sessoes/{sessao}` | `data/ml/evolucao/sessao_{sessao}.json` | o JSON como está; o nome é validado (`AAAA-MM-DD` ou `AAAA-MM-DD-N`) |
| `GET /api/coach/referencias` | `data/reference_models/vhe_interlagos.json` | qual volta é a `volta_ia` e qual é a `minha_melhor`, com tempo e carro |
| `GET /api/store/voltas/{lap_id}` | `data/ml/laps_grid_v2.parquet`, filtrado pela volta | as linhas da volta na ordem da grade: `elapsed_s`, velocidade, acelerador, freio e `lateral_m`, mais o `replayLapId` |
| `GET /api/geometria/oficial` | a geometria oficial exportada e o cache da pista | a linha central, as normais, as bordas dos 60 microssetores e, quando o `geometry_id` bate, a altitude e as larguras |

- **Testes** (`backend/tests/test_leitura.py`, 7): os arquivos voltam como estão; sem arquivo ou com nome inválido, a rota diz por quê; as referências do modelo do coach; a volta do store na ordem da grade, sem conta; volta desconhecida ou id inválido; a geometria sem o cache fica sem relevo; e a volta da conferência nos arquivos reais (2.167 pontos, 90,6288 s).
- **O que já existia continua:** as camadas da pista vêm de `/api/track/geometry`, as gravações de `/api/sessions` e as frases do coach de `/api/analysis/coach/lap/{id}`.
- **Projeção:** nenhuma tela precisou da projeção do runtime. A posição do carro e do fantasma é a linha central oficial mais o `lateral_m` do store v2. As frases do coach trazem o `s` do próprio coach, que projeta na geometria oficial desde o ADR 0013.

#### Sessões

- **O hero** do pedido 29, sem mudança, a não ser o atalho "Última volta", que agora abre `#/volta/ultima`.
- **As sessões do relatório de evolução,** a mais nova em cima. Cada uma tem os números da sessão (voltas, melhor, mediana, desvio, mediana contra a IA, curvas com diferença consistente), **uma marca por volta válida** numa faixa de tempo, com a linha da IA, e o botão "Ver a melhor volta".
- **Mediana e melhor volta por sessão,** com a tendência da mediana e o critério do ADR 0015 (hoje: ainda variando, amplitude 0,643 s, limite 0,5 s).
- **As gravações fora do relatório:** o que `/api/sessions` tem e os JSONs de sessão ainda não. A conferência da Coleta continua dando as voltas válidas e a melhor volta, como no pedido 29.

#### Volta (opção A)

- **A barra de contexto:** sessão, volta, tempo em M:SS,mmm e a diferença para a referência.
- **A escolha:** os chips de sessão (abrem a melhor volta da sessão), os de volta e os de referência (volta da IA ou sua melhor). O endereço guarda a volta (`#/volta/<lapId>`); `#/volta/ultima` abre a última volta do relatório; sem volta, abre a melhor da sessão mais recente.
- **A volta com fantasma** (`frontend/src/volta/Fantasma.tsx`):
  - câmera de 80, 150 ou 400 m (a roda do mouse aproxima entre 40 e 1.200 m), com a opção de girar com o carro;
  - a pista são as camadas do cache (`drawTrackSurface`: asfalto, pintura classificada e zebras), no sentido anti-horário;
  - o traçado desde o início da volta, colorido pelo pedal (freio a partir de 0,15, acelerador a partir de 0,9, o resto parcial);
  - o fantasma da referência posicionado pelo tempo, por curva (recomeça junto no início de cada curva) ou na volta inteira; fora da tela, uma seta com a distância;
  - o relevo no canto superior direito, com a altitude e a inclinação no ponto do carro, e a pista inteira no inferior direito;
  - a leitura dos dois carros (pedal, velocidade, tempo) e a diferença no centro;
  - o replay: tocar, 0,5× a 4×, a barra de posição e a leitura no cursor;
  - **o rádio nesta volta:** as frases do coach, no ponto em que saíram; clicar leva o cursor até lá, e a última frase já dita fica destacada durante o replay.
- **O mapa dos 60 microssetores,** colorido pela diferença, com o nome das curvas (clicar escolhe a curva) e as frases do coach marcadas.
- **A tabela das 14 curvas:** perda, mediana da sessão (só contra a volta da IA, que é a referência do relatório), início da freada, velocidade mínima e posição no ápice, com a soma.
- **Os traços:** diferença acumulada por distância em metros, velocidade, acelerador e freio, com as faixas das curvas e um cursor compartilhado com o mapa, o fantasma e o replay.
- **As medidas** repetem o método do relatório de evolução (`frontend/src/volta/medidas.ts`, porte de `evolution.py` e `microsectors.py`, com 8 testes). As curvas do `sessao_*.json` vêm arredondadas a 0,1 m e são encaixadas na grade antes da conta, senão a C01 a C09 mediam o ponto vizinho.

#### Evolução

- Mediana e melhor volta por sessão, com o critério do ADR 0015.
- Perda por curva entre sessões: ponto na perda mediana para a IA, traço na faixa de 90% de confiança, ponto vazio sem diferença consistente.
- Técnica de pilotagem por curva (bloco `tecnica`), com a escolha da sessão: uso da aderência, freio e volante juntos e freada emendada, cada um com o número da IA ao lado.

#### O resto

- **A navegação** mostra o nome do produto inteiro: "Sistema de Telemetria e Otimização de Trajetórias".
- **Trocar de tela começa do topo;** trocar de volta na mesma tela mantém a rolagem, como no protótipo.
- **As leituras tentam de novo** a cada 3 s enquanto o backend não responde. Achei isso nas capturas: o Electron abre a janela antes de o backend subir, e a tela ficava parada em "Network Error". Os erros agora saem em português.
- **Coleta de dados, Ao vivo e Sistema** ficaram como no pedido 29.
- **`Dashboard.tsx` e `AnalysisPage.tsx`** saíram das rotas, mas continuam no código, junto com os componentes que só eles usavam. Pela seção 6 do inventário, saem no pedido de limpeza.
- **`docs/dashboard_inventario.md`:** no fim da seção 7, "O que o pedido 30 entregou".

### Conferência contra o protótipo (seção 6)

**A volta:** `2026-10-05_20-33-47_vhe_interlagos#0008` (volta 8 de 05/10, 20:33) contra a volta da IA, `2026-10-04_03-42-10_vhe_interlagos#0013`. O script `frontend/scripts/conferencia_prototipo.ts` lê as rotas do app (backend isolado), os dados embutidos no protótipo e o `por_volta` oficial de `sessao_2026-10-05-2.json`. A saída inteira está em `…_conferencia.json`.

| Número | App | Protótipo A | Relatório oficial | Maior diferença |
|---|---|---|---|---|
| Tempo da volta | 1:30,629 (90,6288 s) | 1:30,629 | 1:30,629 | 0 |
| Tempo da volta da IA | 1:24,829 (84,8292 s) | 1:24,829 | 1:24,829 | 0 |
| Diferença da volta | +5,800 s | +5,800 s | +5,800 s | 0 |
| Soma das 14 curvas | +5,800 s | +5,800 s | | 0 |
| Perda por curva (14) | | | | 0,001 s contra o protótipo; 0 contra o oficial |
| Início da freada | | | | 0 m contra o oficial |
| Velocidade mínima e posição no ápice | | | | 0,001 contra o oficial |
| Diferença por microssetor (60) | | | | 0,0005 s contra o protótipo |
| Diferença no modo por curva, no fim de cada curva | | | | 0,002 s contra o protótipo |

| Curva | Perda: app | Protótipo | `por_volta` oficial | Modo por curva, no fim da curva: app | Protótipo |
|---|---|---|---|---|---|
| C01 | +1,221 | +1,221 | +1,221 | +1,029 | +1,029 |
| C02 | +0,091 | +0,091 | +0,091 | +0,091 | +0,090 |
| C03 | +0,475 | +0,475 | +0,475 | +0,475 | +0,475 |
| C04 | +0,492 | +0,492 | +0,492 | +0,492 | +0,493 |
| C05 | +0,348 | +0,348 | +0,348 | +0,348 | +0,347 |
| C06 | +0,328 | +0,328 | +0,328 | +0,328 | +0,328 |
| C07 | +0,378 | +0,378 | +0,378 | +0,378 | +0,379 |
| C08 | −0,098 | −0,098 | −0,098 | −0,098 | −0,099 |
| C09 | +0,348 | +0,347 | +0,348 | +0,347 | +0,348 |
| C10 | +0,895 | +0,895 | +0,895 | +0,895 | +0,893 |
| C11 | +0,525 | +0,525 | +0,525 | +0,525 | +0,526 |
| C12 | +0,237 | +0,237 | +0,237 | +0,237 | +0,237 |
| C13 | +0,146 | +0,146 | +0,146 | +0,146 | +0,147 |
| C14 | +0,415 | +0,415 | +0,415 | +0,415 | +0,415 |

**As diferenças e as causas:**
- **Perda da C09, 0,001 s:** o protótipo guarda 3 casas; o valor do app é 0,3475, que arredonda para 0,348, como o oficial.
- **Microssetores, até 0,0005 s:** o mesmo arredondamento em 3 casas no protótipo. Os maiores são o 37 (+0,577 s), o 4 (+0,369 s) e o 39 (+0,342 s); o de maior ganho é o 34 (−0,142 s).
- **Modo por curva, até 0,002 s:** o protótipo guarda as voltas numa grade de 8 m e interpola; o app usa a grade do store, de 2 m. Pelo mesmo motivo, a leitura da velocidade no cursor pode diferir em 1 km/h (nos 300 m: 112 contra 113 km/h da IA).
- **Por que a C01 dá +1,029 no modo por curva e +1,221 na perda:** a C01 começa antes da linha (4.112 m) e termina depois dela (346 m). No modo por curva, o fantasma recomeça na linha, como no protótipo; a perda do relatório conta o trecho inteiro.

### Capturas lado a lado

App à esquerda (o build do repositório na janela do Electron), protótipo A à direita, cada um com a página inteira. A Volta está com o cursor nos 300 m (ápice da C01), igual nos dois.

- **Sessões:** `docs/handoff/2026-10-14_30_complemento-prototipo-a_lado-a-lado_1_sessoes_1920x1080.png` (`e37712d7118d`) e `…_1_sessoes_2560x1440.png` (`31cbe5499ed7`)
- **Volta, com o cursor nos 300 m:** `docs/handoff/2026-10-14_30_complemento-prototipo-a_lado-a-lado_2_volta_1920x1080.png` (`358fc6350c5a`) e `…_2_volta_2560x1440.png` (`b6e52c4fb759`)
- **Evolução:** `docs/handoff/2026-10-14_30_complemento-prototipo-a_lado-a-lado_3_evolucao_1920x1080.png` (`10739f922d4b`) e `…_3_evolucao_2560x1440.png` (`c4e8ea2e6e36`)
- **Coleta de dados (no protótipo, "Antes de pilotar"):** `docs/handoff/2026-10-14_30_complemento-prototipo-a_lado-a-lado_4_coleta_1920x1080.png` (`76440ad11756`) e `…_4_coleta_2560x1440.png` (`ca83e9c9fdf8`)
- **Sistema:** `docs/handoff/2026-10-14_30_complemento-prototipo-a_lado-a-lado_5_sistema_1920x1080.png` (`9dd00582a4a2`) e `…_5_sistema_2560x1440.png` (`ae9af1acb9f4`)

**Como foram tiradas:** o Electron do repositório com o front construído (`AT_DESKTOP_MODE=production`), comandado pelo DevTools Protocol, com viewport emulado. O perfil (`AT_DESKTOP_USER_DATA_DIR`), o backend (porta 8011, raiz no scratchpad) e as gravações (links físicos) ficaram no scratchpad, como no pedido 29. O protótipo abriu na mesma janela, por `file://`, na opção A. Não mexi no app instalado (porta 8000) nem nos arquivos do jogo.

### O que ficou diferente do protótipo, e por quê

1. **As cores** são as do pedido 29, como o pedido 30 manda: você em branco, a referência em cinza tracejado, a perda em laranja, o ganho em azul e o vermelho do produto nos chips escolhidos. No protótipo, você é laranja.
2. **Cinco sessões em vez de três:** o protótipo tem os dados embutidos até 05/10 (2); o app lê o relatório de hoje, que já tem 09/10 e 10/10. Pelo mesmo motivo, o critério do ADR 0015 dá amplitude 0,643 s no app e 2,062 s no protótipo.
3. **Sessões começa pelo hero,** como o pedido manda, e não pela fileira de cartões do protótipo. O que os cartões tinham e o hero não tem (a tendência da mediana e o critério do ADR 0015) está no texto do gráfico de tendência.
4. **Sem o chip "Outra volta…":** no protótipo ele aparece desligado ("No app: qualquer volta gravada"). O pedido limita a referência à volta da IA e à sua melhor, e um botão que não faz nada não entra.
5. **O rádio nesta volta e as marcas no mapa** não existem no protótipo. Entraram pela seção 6 do inventário ("as frases ficam no replay da Volta, marcadas no mapa").
6. **Os traços de acelerador e freio parecem mais densos:** o app desenha a grade de 2 m do store; o protótipo, a de 8 m.
7. **A tabela das curvas** pinta a perda de laranja; o protótipo deixa a perda na cor do texto. É a regra de cor de dado do pedido 29.
8. **Coleta de dados e Sistema** são as do pedido 28 e do pedido 29, como o pedido 30 manda. O protótipo tem "Antes de pilotar" e uma lista de cartões no lugar delas; as capturas mostram os dois lado a lado mesmo assim.
9. **O sentido e a projeção** são os mesmos do protótipo: `base(x, z) = [z, −x]`, uma rotação, no anti-horário. Os desenhos da pista, do relevo e do minimapa conferem nas capturas.

### Achados fora do pedido

1. **O coach conta os microssetores a partir de 0.** O índice vem de `int(progresso × 60)` (`driving_coach.py`). O resumo de fim da volta 8 fala em "setor 36 (0.58s), setor 3 (0.37s) e setor 38 (0.34s)", e no mapa da tela Volta (que conta de 1, como o relatório) esses são os microssetores 37, 4 e 39, com os mesmos números. Na tela Volta a frase não mostra o número, então não há conflito ali; no rádio da tela Ao vivo (pedido 29), "microssetor 2" é o terceiro de 60. Não mexi no coach. **Decisão sua:** somar 1 na escrita do rádio, ou deixar.
2. **A rota das frases do coach só procura gravações em duas pastas:** `data/recordings` do repositório e da raiz do backend (`AssistedAnalysisService`), e não na pasta de gravação configurada (`TELEMETRY_RECORDING_DIR`). Achei nas capturas: o backend do Electron de teste tinha outra raiz e respondia 404. Resolvi no teste com uma junção no scratchpad, e a tela agora diz "a gravação desta volta não está na pasta de gravações do backend" em vez da frase em inglês. Se o app instalado gravar fora da raiz dele, o rádio da Volta vai dizer isso. Não mexi (seria backend fora das rotas de leitura).
3. **O hero e o relatório diferem em 1 ms nos tempos das referências.** O hero (pedido 29) lê o modelo do coach: 1:29,389 e 1:24,828. O relatório e o store dão 89,3898 e 84,8292 s, que arredondam para 1:29,390 e 1:24,829. A diferença vem das fontes, não da tela. **Decisão sua:** o hero passa a usar o store, para os números baterem na mesma tela?
4. **O achado 2 do pedido 29 ficou resolvido na Evolução:** ela agora mostra os números do relatório de evolução, e não mais os tempos do gravador.

### O que não mudou

- Nenhum modelo, critério, store, regra do coach ou rota de cálculo. No backend, só entraram as rotas de leitura e o teste delas (`git diff --stat 9c5db42f HEAD -- backend`: 5 arquivos, todos de leitura, mais duas linhas em `main.py` para registrar o router).
- Não instalei nem atualizei pacotes. Não gerei instalador. Não mexi no app instalado nem nos arquivos do jogo.
- Nada de marca alheia: as fontes são as do pedido 29 (OFL), e a pista é o desenho do cache.
- Nada foi enviado ao remoto.
