# Relatório parcial do pedido 31: o rádio do engenheiro no jogo e a tela Ao vivo completa (parado na Parte F)

- **Pedido:** `docs/prompts/2026-10-15_31_radio-realidade-aumentada.md`, Partes A, B, C, D, E e G. A Parte F, o teste no jogo com você, é a parada que o pedido manda fazer.
- **Branch:** `etapa/radio-realidade-aumentada`, criada de `develop` (`2c4d56d0`), com merge em `develop`. Nada foi enviado ao remoto.
- **Commits e merge:**
  - `16cd0ec8` docs: pedido 31
  - `ccf81fac` Parte A: o ADR 0020 aceito, o microssetor a partir de 1, o hero com os tempos do store v2 e as 5 linhas do backlog
  - `7da83d88` Parte B: o rádio no backend
  - `0f44b56f` Parte D: a tela Ao vivo completa
  - `1477ce0a` Parte C: o app Lua do CSP, os scripts de instalar e remover e o `conferir_lua.py`
  - `32007655` achado 1: o barramento de eventos dava erro a cada quadro (com teste)
  - `50fc6ab2` achado 2: o coach ao vivo ficava sem o modelo, porque o quadro não traz a pista
  - `9b5dda36` Parte G: `docs/realidade_aumentada.md` e o inventário
  - `4d40f8c2` Merge etapa/radio-realidade-aumentada
  - o commit deste relatório, com o handoff: "Relatório parcial do pedido 31". `develop` avança até ele.
- **Arquivos de handoff** (`docs/handoff/2026-10-15_31_radio-realidade-aumentada_*`):
  - `_relatorio.md` (este arquivo);
  - `_conferencia_13-10.json`: a sessão de 13/10 passada pelo coach fora do tempo real, com as frases do coach e as 18 mensagens que o rádio daria;
  - `_voz_OneCore_Daniel.wav`, `_voz_OneCore_Maria.wav` e `_voz_SAPI_Maria.wav`: as três vozes pt-BR, todas com a mesma frase;
  - `_mensagem_de_teste.wav`: o áudio da mensagem de teste, gerado pelo backend;
  - `_captura_1_ao_vivo_1920x1080.png`, `_captura_1_ao_vivo_2560x1440.png` e `_captura_2_sistema_radio.png`;
  - `_testes.txt`;
  - `.patch`: de `2c4d56d0` até o merge, com o backend, o frontend e o `tools`. São 33 arquivos, com 2.204 linhas a mais e 63 a menos.

## Em resumo

1. **O rádio está pronto até onde dá para testar sem o jogo:**
   - **o backend:** a mensagem, a janela de rádio, a voz, as rotas e o registro;
   - **o app Lua do CSP,** com os scripts de instalar e remover;
   - **a tela Ao vivo,** com o fantasma ao vivo e o rádio;
   - **a mensagem de teste,** na tela Sistema;
   - **a documentação.**
2. **Nenhuma regra do coach mudou.** O coach ganhou só duas leituras, sem mudar o que ele decide: a posição na geometria oficial e o tempo da última volta.
3. **Dois defeitos antigos do caminho ao vivo** apareceram no teste e foram corrigidos (veja os "Achados"):
   - o barramento de eventos dava erro a cada quadro;
   - o coach ao vivo ficava sem o modelo.
4. **A voz escolhida é a Microsoft Daniel (OneCore), a 1,25x.**
5. **Parei na Parte F,** como o pedido manda. Os passos estão em "Parte F: o que você faz".
6. **Testes:**
   - **backend:** a suíte passa com **768 testes**, 12 deles do rádio;
   - **front:** o `vitest` passa com **182 testes**, e o `tsc` e o build também passam;
   - **app Lua:** o léxico e os blocos estão ok, e as 12 chamadas existem no SDK do CSP;
   - **scripts PowerShell:** o analisador do próprio PowerShell não acusou erro nos três.

## Parte A

1. **O ADR 0020:**
   - foi copiado para `docs/decisoes/0020-realidade-aumentada-app-lua-do-csp.md`;
   - ganhou a linha dele em `docs/decisoes/README.md`, como "aceita (pedido 31)";
   - a pasta `docs/prompts/anexos-31/` foi apagada.
2. **O microssetor é contado a partir de 1** em todo texto que o piloto vê:
   - no rádio, no backend;
   - na tela Ao vivo e na tela Volta (`microssetorParaOPiloto` em `utils/radio.ts`).

   O índice interno do coach continua de 0 a 59. A frase interna "Setor 38" vira "microssetor 39" no rádio.
3. **O hero usa os tempos do store v2:**
   - o backend lê `data/ml/laps_grid_v2_meta.json` (`tempos_do_store`, em `core/coleta/estado.py`) e manda `tempoStoreS` junto de cada referência;
   - o hero usa esse tempo e só cai no tempo do modelo do coach se o store não tiver a volta.

   O número de hoje não é o que o pedido citou (veja "O que não bateu com o contexto").
4. **A fonte fica a Instrument Sans.** Não precisou mudar nada.
5. **O `docs/backlog.md` ganhou as 5 linhas,** sem pedido ainda:
   - o gravador junta duas passagens;
   - a rota das frases do coach só procura em duas pastas;
   - o cache da pista é refeito a cada abertura;
   - o `test_ws_client.py` falha;
   - a lista de sessões e a conferência medem as voltas de jeitos diferentes.

## Parte B: as regras da mensagem e da janela de rádio

### A mensagem

- **Montada uma vez, no backend** (`backend/core/radio/texto.py`). A tela Ao vivo, a tela Volta e o app do jogo usam o texto pronto, então os três não divergem.
- **Duas origens:**
  - **a frase do coach** (`coaching_event`);
  - **o resumo na linha de chegada.**
- **Cada mensagem tem cinco partes:**
  - um título;
  - um texto;
  - um detalhe;
  - a fala, que é o texto da voz, curto, para caber em até uns 6 s;
  - os dados: o `s` oficial, o microssetor, a curva, a perda e a volta.
- **A escrita:**
  - português com acento;
  - número com vírgula;
  - microssetor a partir de 1;
  - curva pelo nome técnico (C01 a C14), com o lado por extenso (ADR 0003);
  - tempo de volta em M:SS,mmm.
- **Exemplos reais,** tirados da sessão de 13/10:

| origem | título | texto | detalhe | fala |
|---|---|---|---|---|
| coach | C11, esquerda | +1,14 s para a volta da IA no microssetor 39 | 3,23 s contra 2,09 s · mínima da IA 94 km/h, a sua 80 km/h | "Curva 11, esquerda: 1,14 atrás da IA." |
| coach | C12, esquerda | +1,87 s para a volta da IA no microssetor 44 | 3,22 s contra 1,35 s · a IA freia 54 m depois de você · mínima da IA 145 km/h, a sua 80 km/h | "Curva 12, esquerda: 1,87 atrás da IA." |
| resumo | Volta 7: 1:30,363 | +5,534 s para a volta da IA (1:24,829) | — | "Volta 7, 1 minuto e 30,4. 5,53 atrás da IA." |
| teste | Rádio de teste | Se você está vendo e ouvindo isto no jogo, o rádio funciona. | mensagem mandada pela tela Sistema | "Teste do rádio. Se você me ouve, está tudo certo." |

- **As regras do coach não mudam:**
  - o rádio só escreve o que o coach já decidiu;
  - continuam valendo o limite de 3 frases por volta, os 3 s entre frases, o foco e o limiar;
  - um evento sem os números do `evidence` não vira rádio.

### A janela de rádio

- **O que é:** um trecho da geometria oficial fora das 14 curvas (`backend/core/radio/janelas.py`):
  - as curvas vêm de `detect_corners`, a mesma regra do relatório de evolução;
  - cada curva ganha uma margem de 120 m antes (a freada) e de 30 m depois (a saída);
  - uma janela tem no mínimo 80 m.
- **Em Interlagos, são três janelas:**
  - de **723 a 1.192 m**, a reta oposta;
  - de **1.637 a 1.818 m**, entre a C05 e a C06;
  - de **3.697 a 104 m**, a reta dos boxes, que cruza a linha.
- **A posição do carro:** é a projeção na geometria oficial que o coach já faz (`LiveDrivingCoach.posicao_oficial`). Não há cálculo novo de posição.

### Quando a mensagem é entregue

- **Fora de uma janela, a frase espera a próxima janela.** Uma frase da C06 à C14 espera a reta dos boxes.
- **Uma mensagem por vez:**
  - a entrega só acontece quando o áudio está pronto, ou passados 4 s;
  - a mensagem precisa estar numa janela.
- **O resumo sai 0,6 s depois da linha.** Se a volta acaba com uma frase ainda esperando, ela vai junto com o resumo.
- **O quadro do jogo nunca espera o rádio:** a voz é gerada em segundo plano.

### O registro

- **Onde fica:** cada mensagem entregue vai para `data/radio/<sessão>.jsonl`. Sem gravação aberta, o nome é `sem-gravacao_<data>.jsonl`.
- **O que cada linha tem:**
  - o id, a hora e a volta;
  - o `s` do carro na entrega e o `s` oficial do que foi medido;
  - o microssetor e a curva;
  - o texto, a fala e a origem.
- **Nenhum leitor do ML confunde essa pasta com uma sessão:**
  - as varreduras do inventário e do store procuram `player.jsonl` dentro de `data/recordings`;
  - `data/radio` fica fora dela e não tem `player.jsonl`.

### As rotas

| rota | o que faz |
|---|---|
| `GET /api/radio/mensagens?desde=<id>&instancia=<inst>` | as mensagens entregues depois do id; se o backend reiniciou (outra instância), devolve todas |
| `GET /api/radio/audio/{id}` | o WAV da mensagem |
| `POST /api/radio/teste` | a mensagem de teste, entregue na hora; só a tela Sistema chama |
| `GET /api/radio/estado` | as janelas, a voz e quantas mensagens estão esperando |
| `GET /api/live/volta` | a volta em andamento na grade oficial, para o fantasma ao vivo |

## A voz escolhida e o porquê

- **A escolhida:** a **Microsoft Daniel (OneCore, pt-BR), a 1,25x.**
- **Como é gerada:** pelo `backend/core/radio/voz.ps1`, com o PowerShell do Windows, sem instalar nada.
- **As três vozes, com a mesma frase** ("Curva 1, esquerda: 0,74 atrás da IA."):

| voz | interface | gera em | dura, com a vinheta |
|---|---|---|---|
| Microsoft Daniel | OneCore (`Windows.Media.SpeechSynthesis`) | 1,5 s | 4,5 s |
| Microsoft Maria | OneCore | 0,8 s | 4,8 s |
| Microsoft Maria Desktop | SAPI 5 (`System.Speech`) | 1,0 s | 4,8 s |

- **Por que a Daniel:**
  - **as vozes OneCore** são as mais novas do Windows;
  - **a Daniel foi a mais curta das três,** então cabe melhor numa reta;
  - **uma voz grave** se separa melhor do ronco do motor.
- **Ouça as três** nos WAV do handoff. Trocar de voz é mudar uma linha (`VOZ_PADRAO`, em `core/radio/audio.py`).
- **A vinheta:**
  - é gerada pelo próprio código: um estalo curto de ruído e dois bipes descendo, de 1.400 e 1.050 Hz;
  - não usa nenhum som copiado de transmissão.
- **O arquivo:** um WAV por mensagem, em `data/radio/audio/`, mono, 16 bits, sem o silêncio das pontas.

## Parte C: o app Lua e o que foi conferido

- **Onde fica:** `tools/csp_app/radio_engenheiro/`.
- **O nome:**
  - o nome técnico é "radio_engenheiro";
  - a janela se chama "Rádio · Sistema de Telemetria e Otimização de Trajetórias";
  - não há marca alheia.
- **O que faz:**
  - **pede as mensagens novas a cada 0,3 s,** com uma requisição por vez (o CSP permite no máximo duas);
  - **ao abrir, descarta o que já tinha sido dito;**
  - **mostra o cartão** numa janela transparente de 560 × 150, com fundo carbono e a faixa vermelha;
    - o cartão traz a tag (RÁDIO, VOLTA ou TESTE), o título, o texto e o detalhe;
    - ele fica na tela por 5 s, ou pela duração da voz mais 2,5 s, o que for maior, e some aos poucos;
  - **toca a vinheta e a voz;**
  - **com o backend fora do ar,** mostra um ponto apagado e "rádio sem backend" no rodapé da janela, e registra o aviso no log uma vez só;
  - **se faltar algo na API do CSP,** avisa uma vez, por 10 s, e fica calado.
- **O que não faz:**
  - não muda o carro, os controles nem o jogo;
  - não desenha na pista.
- **O áudio fora da pasta do app:**
  - conferi no SDK do CSP 0.2.11 (`extension\internal\lua-sdk\ac_apps\lib.lua`, só leitura);
  - lá, o `ui.MediaPlayer(source)` aceita "URL or a filename", e o `ac.AudioEvent.fromFile` aceita só arquivo;
  - por isso, o app toca o WAV direto da URL do backend (`http://127.0.0.1:8000/api/radio/audio/<id>`) e não lê nem grava arquivo fora da pasta dele;
  - **o que só o jogo confirma** é se o Media Foundation toca o WAV por HTTP. Se não tocar, proponho duas saídas, nesta ordem:
    1. o backend manda também o caminho do WAV em `data/radio/audio/`, e o app toca pelo arquivo;
    2. se o CSP não ler fora da pasta do jogo, o app baixa o WAV com `web.get` e grava na pasta temporária do Windows (`ac.FolderID.AppDataTemp`), sem tocar na pasta do jogo.
- **Instalar e remover:**
  - `tools/csp_app/instalar.ps1`:
    - pede a pasta do jogo;
    - confere o `acs.exe` e o `extension\installed.log` do CSP;
    - mostra o que vai copiar e pede confirmação;
    - copia só para `apps\lua\radio_engenheiro\`;
  - `remover.ps1`: apaga só essa pasta, depois de conferir que ela tem o `radio_engenheiro.lua`.

  **Eu não rodei nenhum dos dois.**
- **O que foi conferido sem o jogo,** sem instalar nada. Não há interpretador de Lua neste computador, então usei o `tools/csp_app/conferir_lua.py`:
  - **o léxico,** pelo lexer de Lua do `pygments`, que já está no `.venv`: 0 erros;
  - **os blocos,** com cada `function`, `if`, `for` e `do` fechando no `end` certo: ok;
  - **a API usada:**
    - são 12 chamadas: `JSON.parse`, `ac.log`, `os.preciseClock`, `rgbm`, `setInterval`, `ui.MediaPlayer`, `ui.drawRectFilled`, `ui.dwriteDrawText`, `ui.windowSize`, `vec2`, `web.get` e `web.timeouts`;
    - todas existem no `lib.lua` do CSP instalado;
  - **a prova de que a conferência pega erro:** um `end` faltando, uma aspa sem fechar e uma função que não existe, colocados de propósito numa cópia. Os três foram acusados.
  - **os três `.ps1`:** passaram pelo analisador do próprio PowerShell (`Parser::ParseFile`, sem executar), com 0 erros.

  O que essa conferência não pega é uma expressão malformada dentro de um bloco bem fechado. O teste de verdade é o da Parte F.

## Parte D: a tela Ao vivo

1. **A "Volta com fantasma" ao vivo** usa o mesmo componente da tela Volta (`volta/Fantasma.tsx`, com a prop `aoVivo`):
   - **a volta em andamento:** vem de `GET /api/live/volta` (`core/live/volta_ao_vivo.py`):
     - a cada quadro, guarda no ponto da grade oficial o tempo, a velocidade, o acelerador, o freio e a lateral;
     - usa a projeção que o coach já faz, sem cálculo novo;
     - zera na linha;
   - **o fantasma:** é a referência escolhida na Coleta, pelo tempo;
   - **o traçado:** vem colorido pelo pedal;
   - **o título:** é "Ao vivo: volta N", com o número da volta do jogo, e o botão de replay fica escondido.
2. **O rádio** (`aoVivo/RadioAoVivo.tsx`):
   - lê as mensagens a cada 1 s e mostra as 20 mais recentes;
   - cada uma traz o texto pronto, a hora, o ponto da pista (curva · microssetor · metros) e o botão "Ouvir".
3. **A gravação e os canais** continuam como no pedido 29.
4. **A tela Sistema** ganhou o painel "Rádio do engenheiro" (aba Diagnóstico):
   - mostra a voz, as janelas e quantas mensagens foram entregues e quantas esperam;
   - tem o botão "Mandar mensagem de teste".
5. **A tela Volta** usa o mesmo texto pronto do backend e o `s` oficial (veja o achado 3).

## Parte E: testes, conferência e capturas

### E.1 Testes do backend (`backend/tests/test_radio.py`, 12 testes)

1. a frase com vírgula, o microssetor a partir de 1 e o lado por extenso;
2. a frase contra a sua melhor volta, numa curva à direita;
3. um evento sem os números não vira rádio;
4. o resumo na linha;
5. as janelas ficam fora das curvas, com as margens;
6. **uma mensagem gerada dentro da curva espera a reta;**
7. uma mensagem por vez, e o resto vai com o resumo;
8. **o rádio não cria frases:** o limite do coach continua em 3 por volta;
9. o registro fica fora da pasta de gravações;
10. **a voz gera um WAV tocável** (pulado fora do Windows, com o motivo);
11. as rotas. Elas são chamadas direto, porque o `TestClient` precisa do `httpx`, que não está instalado;
12. o barramento com assinantes síncronos e assíncronos (o achado 1).

### E.2 Conferência numa gravação real de 13/10

- **Como fiz:** a sessão `2026-10-13_19-24-10` (13 voltas, 81.670 quadros) passou por um `LiveDrivingCoach` igual ao do app, fora do tempo real.
  - Só no script, o relógio do coach foi trocado pelo cronômetro do jogo. O código do coach não mudou.
  - A referência foi a volta da IA, `2026-10-04_03-42-10#0013` (1:24,829).
- **O coach falou 6 vezes em 13 voltas,** com no máximo 2 por volta. O limite de 3 nunca chegou.
- **O rádio deu 18 mensagens:** as 6 frases e 12 resumos. Nenhuma ficou esperando no fim.
- **As 6 frases, com o ponto da pista:**

| volta | frase do coach (índice interno) | mensagem do rádio | medido em | entregue em |
|---|---|---|---|---|
| 4 | Setor 38: 1.14s atrás | C11, esquerda · +1,14 s para a volta da IA no microssetor 39 | 2.817 m | 3.698 m, reta dos boxes |
| 4 | Setor 43: 1.87s atrás | C12, esquerda · +1,87 s para a volta da IA no microssetor 44 | 3.178 m | 4.032 m, reta dos boxes |
| 5 | Setor 43: 0.73s atrás | C12, esquerda · +0,73 s … microssetor 44 | 3.178 m | 3.698 m, reta dos boxes |
| 9 | Setor 38: 0.50s atrás | C11, esquerda · +0,50 s … microssetor 39 | 2.817 m | 3.698 m, reta dos boxes |
| 11 | Setor 43: 4.39s atrás | C12, esquerda · +4,39 s … microssetor 44 | 3.178 m | 3.697 m, reta dos boxes |
| 12 | Setor 38: 0.53s atrás | C11, esquerda · +0,53 s … microssetor 39 | 2.817 m | 3.697 m, reta dos boxes |

- **As frases:**
  - todas são do miolo (C11 e C12);
  - por isso, todas esperaram a reta dos boxes;
  - todas saíram antes do resumo da mesma volta.
- **Os resumos:**
  - saíram na linha, entre 0,5 e 58 m depois do `s = 0`;
  - um exemplo: "Volta 7: 1:30,363 · +5,534 s para a volta da IA (1:24,829)".
- **O número da volta nos resumos repete o defeito do gravador:**
  - aparece "Volta 10" duas vezes e não aparece "Volta 9";
  - o número é o do contador do jogo no quadro da passagem, e nessa sessão o contador saltou;
  - é o defeito do gravador que já está no backlog (pedido 29, achado 1). O rádio não corrige o contador.

### E.3 App Lua

Está na Parte C: o léxico, os blocos e a API contra o SDK, mais a prova com erros de propósito.

### E.4 Suítes (saída completa em `_testes.txt`)

- **backend:** `pytest tests`: **768 passaram**, em 9 min 46 s;
- **front:**
  - `tsc --noEmit`: sem erros;
  - `vitest`: **182 testes em 16 arquivos,** todos passando;
  - `npm run build`: ok.

### E.5 Capturas

Feitas no app do repositório isolado (Electron com a pasta de dados no meu scratchpad e o backend na porta 8011), como nos pedidos 28 a 30:

- **`_captura_1_ao_vivo_1920x1080.png` e `_2560x1440.png`:**
  - mostram a tela Ao vivo com a mensagem de teste no painel "Rádio": a tag TESTE, a hora e o botão "Ouvir";
  - a "Volta com fantasma" diz "sem dados", porque sem o jogo não há projeção;
  - o selo do topo, "há memória do jogo aberta sem o jogo", descreve o computador na hora da captura e não vem do rádio.
- **`_captura_2_sistema_radio.png`:** a tela Sistema com o painel do rádio, a voz, as três janelas e a mensagem de teste.
- **A voz da mensagem de teste** está em `_mensagem_de_teste.wav`, com 144 KB. Ela foi gerada pelo botão, e o registro foi gravado em `sem-gravacao_2026-10-18.jsonl`, na pasta isolada.
- **O que não deu para capturar:** o fantasma ao vivo com dados. Sem o jogo, a pista da sessão não é conhecida e o coach não projeta o carro, então isso fica para a Parte F. A montagem da volta no front está coberta pelos testes de `aoVivo/voltaAoVivo.test.ts`.

## Achados

1. **O barramento de eventos dava erro a cada quadro.** Corrigido no `32007655`, com teste.
   - **O defeito:** o `emit` fazia `gather` também do retorno dos assinantes síncronos, e isso dava TypeError.
   - **O efeito:** os assinantes assíncronos registrados depois de um síncrono não rodavam. O log do app instalado mostra isso:
     - o arquivo é `%APPDATA%\Automobilista Telemetria\logs\backend.log`;
     - ele tem **958 MB**, com cerca de 1,9 milhão de linhas "free variable 'outer'".
   - **O que proponho:** apagar esse log, ou guardá-lo compactado. Eu não mexi no app instalado.
   - **A correção só chega ao app instalado com o próximo instalador.**
2. **O coach ao vivo ficava sem o modelo.** Corrigido no `50fc6ab2`.
   - **O defeito:** o quadro ao vivo não traz o nome da pista. O coach pedia o modelo da pista "unknown" e ficava calado.
   - **A correção:** o coach completa com a pista do jogo, a mesma que o gravador escreve no `metadata.json`. Nenhuma regra mudou.
   - **O que eu não sei dizer sem o jogo:** quanto isso calou o coach nas sessões gravadas. A Parte F mostra: se as frases chegarem no jogo, está resolvido.
3. **Correção do pedido 30:** o `s` das frases na tela Volta era a projeção do runtime, e não a oficial. Agora é a oficial.
4. **O número da volta do coach fica uma volta atrás do número do jogo:**
   - **por quê:** o `s = 0` da geometria oficial fica antes da linha do jogo;
   - **o que fiz:** o rádio e a tela Ao vivo usam o número do jogo, e o contador interno do coach não mudou.
5. **Sobrou uma pasta vazia, `C:\c`:**
   - **como apareceu:** gravei as amostras de voz por um caminho mal convertido;
   - **o que já fiz:** movi os arquivos para o handoff;
   - **por que ela ficou:** a checagem de segurança barrou o `rm` da pasta, e eu não contornei;
   - **o que falta:** ela só tem pastas vazias e pode ser apagada por você.

## O que não bateu com o contexto

1. **O hero.** O pedido cita "1:29,390 e 1:24,829", mas desde o pedido 32 a sua melhor volta é outra, a `2026-10-15_23-24-50#0008`.
   - Com a regra de uma fonte para cada número, o hero mostra agora **1:27,014** (store v2) e **1:24,829**.
   - O modelo do coach dá 1:27,013.
   - Não é motivo de parada: a regra vale do mesmo jeito.
2. **A precondição "depois que a Parte G do pedido 28 fechar":**
   - a Parte G passou nas conferências do pedido 32 (M1 em 1 de 5);
   - a rodada de 18/10 parou na checagem do período do store v2 (p99 de 7,63 ms contra o limite de 5 ms), e essa decisão continua com você;
   - segui com o pedido 31 porque você mandou executá-lo depois disso, e porque ele não toca no store.

## Parte F: o que você faz

**Antes:**

- **O backend com o rádio ainda não está no app instalado.** O teste é com o app do repositório.
- **O front já está construído** com o código deste pedido (`frontend/dist`, de 18/10 às 10:00). Não precisa rodar o build.
- **Abrir o app do repositório regrava o cache da pista** (`data/cache/tracks/vhe_interlagos_gp_kn5_surface_interval_geometry.json`), como no pedido 28:
  - já guardei uma cópia;
  - o hash de agora é `bd40200a…8e3f8d`;
  - depois do teste eu comparo e, se mudar, restauro.

**Os passos:**

1. **Feche o jogo.** Feche também o app instalado, inclusive na bandeja do Windows: os dois usam a porta 8000, e o app do jogo fala com a 8000.
2. **Instale o app do rádio.** Num PowerShell, na pasta do projeto:
   ```
   powershell -NoProfile -ExecutionPolicy Bypass -File tools\csp_app\instalar.ps1
   ```
   - aceite a pasta sugerida (`D:\SteamLibrary\steamapps\common\assettocorsa`) com Enter;
   - confira o que ele vai copiar;
   - responda `s`.

   O `-ExecutionPolicy Bypass` vale só para esse comando e não muda a configuração do Windows.
3. **Abra o app pelo repositório,** no mesmo PowerShell:
   ```
   $env:AT_BACKEND_USE_PYTHON_RUNNER = 'true'
   cd desktop
   npm.cmd run desktop:prod:autostart
   ```
   Espere o "backend pronto" no topo da tela.
4. **Abra o Assetto Corsa** em Interlagos, com o `rss_formula_rss_3_v6_2026`.
   - Abra a barra de apps, no lado direito da tela, e ligue **"Rádio do engenheiro"**.
   - A janela não tem fundo e só aparece quando chega uma mensagem.
   - Se ela abrir no meio da tela, tente arrastá-la para um canto. Se não der, me diga onde ela ficou.
5. **No app, mande a mensagem de teste:** tela **Sistema**, aba Diagnóstico, botão **"Mandar mensagem de teste"**.
   - No jogo, deve aparecer o cartão "TESTE · Rádio de teste", e a voz deve dizer "Teste do rádio. Se você me ouve, está tudo certo."
   - Repare em três coisas:
     - se o cartão aparece;
     - se a voz toca;
     - se dá para ler o cartão sem tirar o olho da pista.
6. **Ande de 3 a 5 voltas sem a IA:**
   - **as frases do coach** chegam nas retas: a reta oposta, o trecho entre a C05 e a C06 e a reta dos boxes;
   - **o resumo** chega logo depois da linha, a partir da segunda passagem;
   - **na tela Ao vivo,** o fantasma deve acompanhar a volta.

   Com até 5 voltas, a sessão não entra no coach (a regra é mais de 5). Se você andar mais, ela entra na próxima rodada.
7. **Feche o jogo e o app** e me avise: **"testei o rádio no jogo"**.

**Se algo não funcionar:**

- **o app do jogo** escreve as linhas `[radio_engenheiro]` no log do CSP (`C:\Users\Dokas\Documents\Assetto Corsa\logs\custom_shaders_patch.log`);
- **o backend** escreve em `logs\backend.log` do repositório.

Não precisa copiar nada: eu leio os dois.

**Para remover o app do jogo,** quando quiser:

```
powershell -NoProfile -ExecutionPolicy Bypass -File tools\csp_app\remover.ps1
```

**Depois do seu aviso, eu:**

- confiro o registro `data/radio/<sessão>.jsonl` contra as frases do coach da gravação;
- confiro o cache da pista;
- completo este relatório.

## O que falta e o que precisa de decisão

**Falta, deste pedido:**

- a Parte F, o teste no jogo, com você;
- depois dela:
  - a conferência do registro;
  - a conferência do cache da pista;
  - a conclusão do relatório.
- **um ponto de atenção:** se o WAV não tocar pela URL, a proposta está na Parte C, e o caminho é decisão sua.

**Decisões suas que continuam abertas, de antes:**

1. **O limite da checagem do período do store v2:** o p99 deu 7,63 ms, contra o limite de 5 ms. O pedido 33 (`docs/prompts/2026-10-18_33_relogio-do-gravador-novo.md`) está na pasta, sem commit, e não foi mandado executar.
2. **O CSV de anotações:** normalizar o fim de linha, que está misturado.
3. **A referência de 1:27,014:** manter ou não, já que tem 9,2% fora do corredor.

**Para você apagar, se quiser:**

- o `backend.log` de 958 MB do app instalado (achado 1);
- a pasta vazia `C:\c` (achado 5).
