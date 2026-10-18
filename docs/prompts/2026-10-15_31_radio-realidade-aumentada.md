# Pedido 31 — Realidade aumentada: o rádio do engenheiro dentro do jogo e a tela Ao vivo completa

**De:** Eduardo. **Data:** 15/10/2026.
**Tipo:** backend (rádio e voz), app Lua do CSP, front (tela Ao vivo) e documentação. Nenhum modelo, critério, store ou regra do coach muda.

**Ao mandar executar este pedido, eu aprovo o ADR 0020** (`docs/prompts/anexos-31/0020-realidade-aumentada-app-lua-do-csp.md`) e as decisões da Parte A.

**Quando começar:** depois que a Parte G do pedido 28 fechar. Os dois chats usam a mesma pasta, e só um trabalha por vez (ADR 0008).

## Contexto

1. **O plano:** a realidade aumentada é como o rádio dos engenheiros da F1. É uma mensagem curta, em voz e num cartão na tela do jogo, no momento em que dá para ouvir. É o jeito de o Modelo 2 chegar ao piloto durante a volta (ADR 0018), com o jogo em tela cheia no monitor de 27".
2. **O que o pedido 29 leu (Parte A do relatório):**
   - **versões:** CSP 0.2.11 (build 3465) e Content Manager 0.8.2895.40668;
   - **a API Lua** (`extension\internal\lua-sdk\ac_apps\lib.lua`):
     - `ui.transparentWindow`;
     - `web.get`, `web.post` e `web.request`, com no máximo duas requisições ao mesmo tempo;
     - `ac.AudioEvent.fromFile` e `ui.MediaPlayer`;
     - `ac.getCar(0)`;
     - `render.*`;
   - **sem síntese de fala no CSP.** O Windows tem as vozes pt-BR Maria (SAPI 5), Maria e Daniel (OneCore).
3. **O que o backend já entrega:**
   - `/api/live/coach`, com as 20 frases mais recentes, só `coaching_event`;
   - `MAX_PHRASES_PER_LAP = 3`, com pelo menos 3 s entre frases;
   - o resumo de fim de volta (`engineer_speech`), só pelo WebSocket;
   - o `evidence` de cada frase: microssetor, os dois tempos, a perda, a freada e a mínima.
4. **O que a tela Ao vivo já tem** (pedido 29): a gravação, os canais e as frases como mensagens de rádio, montadas no front a partir do `evidence` (`utils/radio.ts`).

## Parte A — ADR 0020 e as decisões dos relatórios 29 e 30

1. **O ADR 0020:**
   - copie `docs/prompts/anexos-31/0020-realidade-aumentada-app-lua-do-csp.md` para `docs/decisoes/`;
   - acrescente a linha dele em `docs/decisoes/README.md`;
   - apague a pasta `docs/prompts/anexos-31/`.
2. **Microssetor contado a partir de 1** em todo texto que o piloto vê (rádio, tela Ao vivo e tela Volta), como no mapa e no relatório de evolução. O índice interno do coach continua como está.
3. **Hero com os tempos do store v2:** o hero passa a usar os tempos do store v2 e do relatório (hoje, 1:29,390 e 1:24,829, no lugar de 1:29,389 e 1:24,828 do modelo do coach), para bater com a tela Volta. A regra é uma fonte para cada número.
4. **Fonte do texto:** fica a Instrument Sans.
5. **No `docs/backlog.md`, cada um como linha nova, sem pedido ainda:**
   - o gravador junta duas passagens na mesma volta quando o contador do jogo volta (pedido 29, achado 1);
   - a rota das frases do coach só procura gravações em duas pastas (pedido 30, achado 2);
   - o cache da pista é refeito a cada abertura do backend, cerca de 36 s (pedido 28, achado 1);
   - `backend/test_ws_client.py` falha na suíte: é um script antigo, assíncrono, que precisa de um plugin que não está instalado (pedido 30);
   - a lista de sessões e a conferência medem as voltas de jeitos diferentes (pedido 29, achado 2).

## Parte B — O rádio no backend

1. **Uma mensagem de rádio por evento,** montada uma vez, no backend:
   - **origem:**
     - as frases de diferença do coach (`coaching_event`);
     - o resumo na linha de chegada: o tempo da volta em M:SS,mmm e a diferença para a referência escolhida;
   - **o texto:**
     - português com acento, número com vírgula e nomes técnicos;
     - microssetor contado a partir de 1, curva pelo nome técnico (C01 a C14) e lado por extenso (ADR 0003);
     - curto, para caber em até cerca de 6 s de fala;
   - **use a mesma escrita de `utils/radio.ts`:** traga a regra para o backend e faça o front usar o texto pronto, para os dois não divergirem;
   - **as regras do coach não mudam:** quais frases saem, o limite de 3 por volta, o foco e o limiar.
2. **Quando a mensagem é entregue:**
   - só numa janela de rádio, que é um trecho da geometria oficial fora do trecho das 14 curvas;
   - a mensagem espera a próxima janela; se a volta acabar antes, ela vai junto com o resumo;
   - a posição do carro é a projeção na geometria oficial que o coach já faz. Nenhum cálculo novo de posição.
3. **A voz:**
   - gere o áudio de cada mensagem com uma voz pt-BR do Windows, sem instalar pacote, por exemplo pelo `System.Speech` ou pelo `Windows.Media.SpeechSynthesis` do PowerShell;
   - teste as três vozes e relate a escolha;
   - o arquivo fica na pasta de dados do backend (por exemplo, `data/radio/audio/`), com um id por mensagem;
   - **uma vinheta curta antes da voz,** como o clique do rádio, gerada pelo próprio código. Nenhum som copiado de transmissão.
4. **Rotas:**
   - as mensagens novas desde um id, para o app do jogo e a tela Ao vivo;
   - o áudio de uma mensagem;
   - uma mensagem de teste, só pela tela Sistema, para conferir o rádio sem andar no jogo.
5. **Registro:** cada mensagem entregue vai para `data/radio/<sessão>.jsonl`, fora da pasta de gravações, com:
   - o id, a hora e a volta;
   - o `s` da geometria oficial e o microssetor;
   - o texto e a origem.

   Confirme que nenhum leitor do ML confunde essa pasta com uma sessão, como no pedido 28.

## Parte C — O app Lua do CSP

1. **Onde fica:** `tools/csp_app/<nome do app>/`. O nome é técnico e o título da janela traz o nome do produto, sem marca alheia.
2. **O que faz:**
   - **a cada 300 ms, mais ou menos,** pede ao backend as mensagens novas, sem passar de duas requisições ao mesmo tempo;
   - **mostra um cartão de rádio** numa janela transparente, por alguns segundos, com o visual do `docs/sistema_visual.md` (carbono e vermelho), legível no jogo e sem cobrir o centro da tela;
   - **toca a vinheta e a voz** da mensagem. Antes, confira na API se o `ac.AudioEvent.fromFile` ou o `ui.MediaPlayer` toca um arquivo fora da pasta do app. Se não tocar, relate e proponha o caminho;
   - **com o backend fora do ar,** mostra um indicador discreto e não repete aviso;
   - **se a API do CSP não tiver o que o app usa,** o app avisa uma vez e fica calado.
3. **O que não faz:**
   - não muda o carro, os controles nem nada do jogo;
   - não desenha na pista neste pedido (ADR 0020, consequências).
4. **Instalação e remoção:**
   - `tools/csp_app/instalar.ps1` copia a pasta do app para `<pasta do jogo>\apps\lua\<nome do app>\`, e `remover.ps1` apaga só essa pasta;
   - os dois pedem a pasta do jogo e conferem que ela tem `extension\installed.log` com o CSP antes de gravar;
   - **você não roda os scripts.** Eu rodo.

## Parte D — A tela Ao vivo completa

1. **A "Volta com fantasma" ao vivo,** com o mesmo componente da tela Volta:
   - o carro na posição atual, sobre a pista tratada;
   - o traçado da volta em andamento, colorido pelo pedal;
   - o fantasma da referência escolhida, pelo tempo.

   Se o carro ao vivo precisar de dado que o backend ainda não expõe, use a projeção que o coach já calcula. Se exigir cálculo novo, pare e relate.
2. **O rádio:** as mensagens da Parte B, com o texto pronto, a hora, o ponto da pista e um botão para ouvir o áudio.
3. **A gravação e os canais,** como no pedido 29.

## Parte E — Testes e conferência sem o jogo

1. **Testes do backend:**
   - o texto de cada tipo de mensagem: número com vírgula, microssetor a partir de 1 e lado por extenso;
   - a janela de rádio: uma mensagem gerada dentro de uma curva espera a reta;
   - o limite do coach continua em 3 frases por volta;
   - a voz gera um arquivo tocável (com o Windows; sem a voz, o teste é pulado com o motivo);
   - as rotas e o registro.
2. **Conferência numa gravação real:**
   - passe uma sessão de 13/10 pelo coach, fora do tempo real, se houver como fazer isso sem mudar o coach;
   - relate as mensagens que o rádio daria, com o ponto da pista em que cada uma seria entregue;
   - se não houver como, relate.
3. **App Lua:** sem o jogo não dá para rodar. Confira a sintaxe com o que houver no computador, sem instalar nada, e diga o que foi conferido.
4. **Os testes do front e a suíte do backend** continuam passando.
5. **Capturas da tela Ao vivo** com a mensagem de teste.

## Parte F — Teste no jogo (comigo)

Pare aqui. Grave o relatório parcial com estes passos para mim:

1. Fechar o jogo.
2. Rodar `tools/csp_app/instalar.ps1`.
3. Abrir o app pelo repositório (o backend com o rádio ainda não está no instalador).
4. Abrir o Assetto Corsa em Interlagos e ligar o app do rádio na barra de apps do jogo.
5. Na tela Sistema, mandar a mensagem de teste: o cartão aparece no jogo e a voz toca.
6. Andar 3 a 5 voltas sem a IA. As mensagens do coach chegam nas retas, e o resumo chega na linha.
7. Fechar e avisar: "testei o rádio no jogo".

Depois do aviso, confira o registro da sessão (`data/radio/<sessão>.jsonl`) contra as frases do coach e complete o relatório.

## Parte G — Documentação

- **`docs/realidade_aumentada.md`:**
  - como o rádio funciona;
  - as janelas de rádio;
  - a voz escolhida;
  - como instalar, ligar e remover o app;
  - o registro e como ele serve para avaliar o Modelo 2.
- **`docs/dashboard_inventario.md`:** o que este pedido entregou, no fim da seção 7.

## Regras gerais

- **Nenhum modelo, critério, store ou regra do coach muda.** O rádio só escreve e entrega o que o coach já decide.
- **Não grave na pasta do jogo.** Os scripts da Parte C são rodados por mim (ADR 0020).
- **Não instale nem atualize pacotes** (npm, pip ou Lua). A voz é a do Windows. Se algo pedir pacote novo, pare e relate.
- **Não mexa no app instalado.** O teste da Parte E usa a pasta isolada, como nos pedidos 28 a 30.
- **Não gere instalador.** Ele vem quando as telas e o rádio estiverem aprovados.
- **Nada de marca alheia:** sem logotipo, som ou fonte da F1, do WEC, da FIA ou de equipes.
- **Não contorne nenhuma trava:** se algo parar, pare também e registre o motivo.
- **Branch e commits:** branch `etapa/radio-realidade-aumentada`, commits por parte, merge em `develop`. Sem push.
- **Uma sessão de implementação por vez** (ADR 0008).
- **Relatório** em `docs/handoff/2026-10-15_31_radio-realidade-aumentada_relatorio.md`, como manda o CLAUDE.md, com:
  - a Parte A;
  - as regras da mensagem e da janela de rádio, com exemplos reais de texto;
  - a voz escolhida e o porquê;
  - o que foi conferido do app Lua;
  - as capturas e a saída dos testes;
  - na parada da Parte F, os passos para mim.
- Se algo do contexto não bater com o repositório, pare e registre no relatório.
