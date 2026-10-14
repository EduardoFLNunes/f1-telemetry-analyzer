# Relatório do pedido 29: redesenho, etapa 1 (parcial, parado na Parte B por limite de uso)

- **Pedido:** `docs/prompts/2026-10-14_29_redesenho-base.md`
- **Branch:** `etapa/redesenho-base`, criada a partir de `develop` (`adff57cd`). Sem merge ainda. Nada foi enviado ao remoto.
- **Commits:**
  - `54c071a6` docs: pedido 29 (redesenho, etapa 1), skill frontend-design e as decisões de 14/10 no inventário (arquivos do Cowork)
  - `d73e08d5` Sistema visual (em andamento): fontes OFL locais, variáveis de tema, classes dos componentes base e Tailwind apontando para as variáveis; index.html em pt-BR com o nome do produto e sem fontes da internet (pedido 29, Parte B)
  - o commit deste relatório
- **Arquivos de handoff:** `docs/handoff/2026-10-14_29_redesenho-base_relatorio.md` (este).
- **Canvas de design (pranchas):** https://claude.ai/artifact/7LhHGi98Yjh18S3hFNQheV (privado: só abre para quem você compartilhar).

## Antes de começar

- **A Parte G do pedido 28 não tinha fechado** (a 0.3.0 não está instalada e não há sessão gravada depois de 13/10). Você decidiu no chat seguir agora: o pedido 29 não mexe no backend, no store nem no coach. A Parte G continua esperando o seu aviso "instalei e gravei a sessão de teste".
- **A skill veio em outro lugar:** estava em `docs/prompts/anexos-29/frontend-design/SKILL.md`, não em `.claude/skills/frontend-design/SKILL.md`. Copiei para o caminho do pedido e commitei as duas cópias (`54c071a6`).

## Parte A — Leitura para a realidade aumentada (feita, só leitura)

Nada foi instalado, copiado ou mudado na pasta do jogo.

1. **Custom Shaders Patch:** instalado em `D:\SteamLibrary\steamapps\common\assettocorsa`.
   - **Versão 0.2.11, build 3465.** Lida em `extension\installed.log` (`version: 0.2.11`, `build: 3465`, instalado pelo Content Manager) e confirmada em `extension\config\data_manifest.ini` (`[VERSION] SHADERS_PATCH=0.2.11`, `SHADERS_PATCH_BUILD=3465`).
   - **`apps\lua` existe**, com 6 apps: `CMRT-Essential-HUD` (1.0.13), `PureConfig` (1.80), `PurePP` (0.52), `PurePlanner` (1.78), `TrafficTool` (só a pasta `data`) e `vrc_advanced_setup` (1.5.1).
2. **Content Manager:** `C:\Users\Dokas\Desktop\latest\Content Manager.exe`, versão do arquivo **0.8.2895.40668** (lida das propriedades do executável, sem abrir). Dados em `%LOCALAPPDATA%\AcTools Content Manager`.
3. **API Lua do CSP nesta versão** (definições em `extension\internal\lua-sdk\ac_apps\lib.lua`; os números são linhas desse arquivo):
   - **janela ou painel na tela:** `ui.transparentWindow` (15802), `ui.toolWindow` (15815), `ui.beginTransparentWindow` (12045); texto com `ui.dwriteDrawText` (12450) e retângulos com `ui.drawRectFilled` (12372). As apps declaram janelas no `manifest.ini` com `FUNCTION_MAIN` (exemplo: `apps\lua\CMRT-Essential-HUD\manifest.ini`).
   - **HTTP para `127.0.0.1:8000`:** `web.get` (6925), `web.post` (6936) e `web.request` (6948), "HTTP or HTTPS". **Limite: só duas requisições ao mesmo tempo** (comentário das três funções). Tempos de espera em `web.timeouts` (6914).
   - **som:** `ac.AudioEvent.fromFile({filename=…, use3D=false, loop=false})` (15224) e `ui.MediaPlayer(source, audioParams)` (16026), que toca um arquivo de áudio fora da tela. **Não há síntese de fala no SDK** (nenhuma ocorrência de speech ou tts): o áudio do rádio teria de vir pronto como arquivo.
   - **estado do carro:** `ac.getCar(index)` (6597) devolve `ac.StateCar` com `splinePosition` (4092, 0 a 1 na volta), `speedKmh` (4073), `gas` (4062), `brake` (4063), `clutch` (4064), `steer` (4065), `lapTimeMs` (4189), `isAIControlled` (4113) e `position` (4050).
   - **desenho no mundo 3D:** `render.debugLine` (11972), `render.quad` (11933), `render.circle` (11916), `render.rectangle` (11924), `render.glBegin`/`glVertex` (11896/11899). Numa app, o desenho 3D entra pelo `manifest.ini` com `[RENDER_CALLBACKS] TRANSPARENT = Draw3D` (exemplo: `apps\lua\PureConfig\manifest.ini`, linhas 10–11).
4. **O que o backend já entrega para o rádio:**
   - **`GET /api/live/coach`** (`backend/routers/live.py:209`): `{status, source: "event_bus", eventCount, events}`, com **as 20 mais recentes** (a mais nova primeiro) de uma fila de 50 (`main.py:155-157`). Não tem frequência própria: é lida quando alguém pede. Hoje **o front não lê esta rota**; ele recebe as frases pelo WebSocket.
   - **Só entram em `/api/live/coach` os eventos `coaching_event`** (`main.py:920`). O resumo da volta ("Volta fechada…") sai como `engineer_speech` e **só vai pelo WebSocket**.
   - **`MAX_PHRASES_PER_LAP = 3`** (`core/live/driving_coach.py:90`), uma frase por microssetor de foco (`FOCUS_SECTORS = 3`), com pelo menos 3 s entre frases (`MIN_SECONDS_BETWEEN_EVENTS`).
   - **Quando cada frase nasce:**
     - **frase de diferença:** ao **fechar um microssetor de foco** cuja perda passa o limite (`_close_sector`, linhas 440–478; montada em `_emit_reference_event`, 593–644). O evento traz `evidence` com `microsector`, `yourSeconds`, `referenceSeconds`, `lossSeconds`, `referenceLabel`, freada e mínima;
     - **foco:** quando os microssetores de foco mudam, antes das voltas (`_emit_focus_event`, 389–407);
     - **resumo:** na linha de chegada (`_speak_lap_summary`, 703–755), só pelo WebSocket.
   - **Achado:** as frases saem **sem acento e com ponto decimal** ("0.31s atras … voce"). Mudar isso é mudar o backend. Na tela Ao vivo, a proposta é montar a frase em português a partir do `evidence`, que já tem todos os números.
5. **Vozes em português** (consulta pelo `System.Speech` e pelo registro, só leitura):
   - SAPI 5: **Microsoft Maria Desktop (pt-BR, feminina)** e Microsoft Zira Desktop (en-US);
   - vozes modernas (`Speech_OneCore`): **Microsoft Daniel (pt-BR)** e **Microsoft Maria (pt-BR)**.
   - **Há voz pt-BR instalada.**

## Parte B — Sistema visual (em andamento)

**Feito:**
- **Pranchas no canvas** (o "HTML antes do React"): sistema visual, componentes base, Sessões com o hero pronto, hero enquanto o backend sobe e a casca do Ao vivo. O hero usa números reais: última sessão 13/10 19:24 (9 voltas válidas, melhor 1:29,768), sua melhor 1:29,389 (referência do coach, modelo de 10/10), volta da IA 1:24,828 e M1 "0 de 5".
- **Paleta** em `frontend/src/theme/tokens.css`:
  - fundo em carbono `#08090B`;
  - vermelho de destaque `#E10600`, e `#FF4A3D` quando o vermelho é texto;
  - texto `#F2F4F5`, `#B4BCC4` e `#8E98A2`;
  - cores de dado do protótipo (freio, acelerador, parcial, perda e ganho);
  - cronometragem roxo, verde e amarelo, só em tempos;
  - estados da coleta;
  - variáveis do vidro, com `prefers-reduced-transparency` e `data-vidro="desligado"`;
  - os nomes antigos (`--bg-core`, `--text-1`…) apontam para a paleta nova.
- **Fontes locais com licença OFL** em `frontend/src/assets/fonts`: Big Shoulders (títulos), Instrument Sans (texto) e IBM Plex Mono (tempos e números).
  - As do protótipo (Barlow Condensed e IBM Plex Sans) **não estão no computador**, e baixá-las seria um download novo. Usei fontes OFL que já estavam no disco.
  - A Big Shoulders não tem algarismos de largura igual, por isso nunca mostra número; os tempos ficam na Plex Mono.
- **Componentes base em CSS** (`frontend/src/theme/componentes.css`): casca, navegação, painel de vidro, cartão de número, chips e segmentados, tabela, etiqueta de estado, dica, mensagem de rádio e hero. Nenhuma cor solta.
- **Tailwind** apontando para as variáveis; **`index.html`** com `lang="pt-BR"`, o nome do produto no título e sem as fontes da internet.

**Achados para as próximas partes:**
- **Espelhamento:** confirmado. Com x para a direita e z para baixo (o minimapa), a volta gira no anti-horário. O mapa principal desenha (x, −z) sem inverter e gira no horário (`CameraController.tsx`, `applyCameraTransform`).
- **Coordenadas:** no cache da pista, o asfalto, as zebras e a pintura estão em (x, −z); a linha central e as voltas do store v2 estão em (x, z).
- **Duas cores do canvas a acertar:** na prancha de componentes, "parado" e "taxa baixa" estão trocadas em relação ao código (`utils/coleta.ts`: parado é vermelho e taxa baixa é âmbar). O app segue o código.

## O que falta

1. **Parte B:**
   - ligar `src/theme/*.css` no `main.tsx`;
   - trocar `JetBrains Mono` e `Inter` pelas fontes novas (48 usos no `App.css` e strings de canvas nos `.tsx`) e tirar o `@import` do Google Fonts do `App.css`;
   - passar para o `App.css` as classes que só existiam no `index.html` antigo e ainda são usadas (`status-live`, `corner-accent`, `slide-in`, `blink`, `font-eng`, `panel-hover`; o `App.css` já tem versões delas, falta conferir);
   - componentes React (`MensagemRadio`, `EtiquetaEstado`, `CartaoNumero`…);
   - guia visual em Sistema;
   - tabela de contraste por script;
   - medida de quadros por segundo com e sem vidro.
2. **Parte C:**
   - roteador por hash e navegação no topo;
   - telas Sessões (com o hero), Ao vivo, Volta (Pista atual), Evolução (Análise atual), Coleta (visual novo) e Sistema;
   - `formatLapTime` com vírgula;
   - retirada dos dados fixos (problema B) e depuração para Sistema;
   - correção do espelhamento, com antes e depois numa volta real;
   - título da janela no `desktop/main.js`.
3. **Parte D:** `vitest` e `tsc --noEmit`; capturas da janela real em 1920×1080 e 2560×1440 (com `AT_DESKTOP_USER_DATA_DIR` e `AT_BACKEND_RUNTIME_ROOT` no scratchpad, para não regravar o cache da pista no repositório).
4. **Parte E:** `docs/sistema_visual.md` e o fim da seção 7 do inventário.
5. Merge em `develop` e relatório final.

**Decisões suas:**
- **As fontes:** fico com Big Shoulders, Instrument Sans e Plex Mono, ou você autoriza baixar Barlow Condensed e IBM Plex Sans (Google Fonts, OFL)?
- **A paleta e o vidro das pranchas:** aprova antes de eu levar para todas as telas?
