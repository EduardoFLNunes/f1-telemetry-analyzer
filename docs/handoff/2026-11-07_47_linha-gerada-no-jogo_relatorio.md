# Relatório do pedido 47: a linha gerada dirigida pela IA do jogo

- **Pedido:** `docs/prompts/2026-11-07_47_linha-gerada-no-jogo.md`.
- **Situação:** **parado na Parte D,** esperando o teste no jogo, como o pedido manda. As Partes 0, A, B e C estão feitas e conferidas, e os testes passam. As Partes E (o resultado) e F (a documentação com o resultado), o merge e o envio de `develop` ficam para depois do seu aviso "rodei a IA nas linhas".
- **Pasta:** `C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47` (a pasta separada, por `git worktree`).
- **Branch:** `etapa/linha-gerada-no-jogo`, a partir de `develop` em `a780c9d1`. **Ela fica nesta branch durante a parada.**
- **Commits** (todos na branch, nenhum merge ainda):
  - `61fbe559` Pedido 47: o texto do pedido (a linha gerada dirigida pela IA do jogo);
  - `c0bbe9fd` Pedido 47, Parte 0: linha no ADR 0008 (pastas por git worktree) e data/pista_teste/ e *.ai no .gitignore;
  - `fbec60a4` Pedido 47, Parte A: leitor e escritor do fast_lane.ai (ida e volta byte a byte), as regras da linha nova, o referencial e a exclusao das sessoes da pista de teste;
  - `9544ff0b` Pedido 47, Parte B: ADR 0029 (a linha gerada dirigida pela IA do jogo), registrado antes do jogo, com o medidor de cada condicao;
  - `15b46894` Pedido 47, Parte C: as linhas C1 a C4 (fora do git, com o sha256), os scripts da copia da pista, a figura, o resultado e os testes;
  - `3e48e0d7` Pedido 47, parada da Parte D: emenda do ADR 0029 antes do jogo, o roteiro, a tabela das anotacoes, a suite e o relatorio;
  - `afe690ef` Relatorio do pedido 47: o envio da parada conferido;
  - o commit das duas mudanças de 08/11 (os caches do CSP e a conferência entre as sessões; veja "Atualização de 08/11").
- **Arquivos de handoff** (`docs/handoff/2026-11-07_47_linha-gerada-no-jogo…`):
  - `_relatorio.md` (este);
  - `_parte_a.json` (Parte A: a pasta, o formato, o referencial, os campos, a linha nova em 3D e os caches do CSP);
  - `_medidor.json` (B.8: o medidor de cada condição, por microssetor);
  - `_linhas.json` (Parte C: os arquivos e os sha256);
  - `_linhas_na_pista.png` (C.3: as 5 linhas, com a C10 e a saída da linha de chegada);
  - `_anotacoes.csv` (D.3: a tabela para as suas anotações);
  - `_testes.txt` (a suíte do backend).

## Em uma frase

**Dá para fazer, e está pronto para o jogo.** O `fast_lane.ai` foi decifrado inteiro, e o leitor e o escritor refazem o arquivo byte a byte. A IA de 04/10 seguiu essa linha a 0,21 m (mediana). Cada campo de uma linha nova tem uma regra conferida no próprio original. As quatro linhas estão gravadas fora do git, e os três scripts estão prontos e testados numa pasta falsa. O ADR 0029 foi commitado antes de qualquer arquivo de linha.

## Parte 0: a pasta separada

- **O comando** (você rodou, depois do meu primeiro aviso de que a pasta não existia):
  `git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer worktree add C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47 -b etapa/linha-gerada-no-jogo develop`
- **0.2, o texto do pedido:**
  - copiado para a pasta separada e commitado (`61fbe559`);
  - as duas cópias de trabalho tinham o mesmo sha256 (`f4cb1e4a…686b`). O commit guarda o texto com fim de linha LF (`core.autocrlf=true`); com CRLF, ele dá o mesmo sha256;
  - **na pasta principal, apaguei só `docs/prompts/2026-11-07_47_linha-gerada-no-jogo.md`.** Ela ficou limpa, na branch `etapa/replay-e-radio-que-ensina`, sem commit.
- **0.3, os imports:** uso o `.venv` da pasta principal, rodando de dentro de `f1-telemetry-analyzer-47\backend`. Com isso, `core` e `ml` vêm da pasta separada: conferi `core.__file__` e `ml.__file__`. Nada foi instalado.
- **0.4, os dados:** três junções de pasta, só para leitura, da pasta separada para a principal: `data\recordings`, `data\ml` e `data\cache`. O git as ignora.
  - **Nada foi escrito nos dados da principal.** Tirei uma foto dos 932 arquivos (nome, tamanho e data) antes de começar e comparei depois da suíte de testes: zero diferenças (veja "Testes");
  - o que este pedido gera vai para `data\pista_teste\` da pasta separada (no `.gitignore`, junto com `*.ai`). Nenhuma gravação foi copiada.
- **0.5, o processador:** o `acs.exe` estava fechado antes de cada conta pesada e da suíte.
- **0.6:** uma linha de atualização no ADR 0008 (`c0bbe9fd`).

## Parte A: dá para fazer? Sim

### A.1, a pasta da pista

- **O jogo** está em `D:\SteamLibrary\steamapps\common\assettocorsa`. A pista fica em `content\tracks\vhe_interlagos`: 157 arquivos, 1,53 GB.
- **Layouts:** `gp` e `norm`, cada um com `ai\fast_lane.ai` (1.274.780 bytes) e `ai\pit_lane.ai` (125.236 bytes). Os dois `fast_lane.ai` são iguais (sha256 `36b57fd8d259755d9b25ffdc1f61e328479045fc275e554b7b7e3de7eb3d8342`). **As gravações são do `gp`** (o `trackCache` delas é `vhe_interlagos_gp_…`).
- **Não há `data\ai_hints.ini`** em nenhum layout.
- **O espaço livre:** 126,6 GB no D: (onde a cópia fica) e 24,7 GB no C:.
- **O nome da cópia:** `vhe_interlagos_teste_m1`, que está livre. No jogo, o `gp` vira "Interlagos [teste]" e o `norm`, "Interlagos National [teste]" (o `ui_track.json` original diz "Interlagos - GP" e "Interlagos - National").
- **Uma pasta `_obj_export`** de 877 MB está dentro da pista. Ela não é do jogo, mas é copiada junto, sem ser aberta.

### A.2, o formato do `fast_lane.ai` (versão 7, 2.680 pontos)

| bloco | conteúdo | conferido |
|---|---|---|
| cabeçalho | 4 inteiros: versão 7, 2.680 pontos, tempo de volta 0, amostras 0 | o arquivo e o `AiSpline.cs` |
| pontos | por ponto: x, altura, z, a distância acumulada (floats) e o índice (inteiro), de 0 a 2.679 | idem; o leitor que o repositório já tinha (`core/kn5/track_edges_from_surface.py`) |
| extras | um inteiro (2.680) e 18 floats por ponto: velocidade, acelerador, freio, `ObsoleteLatG`, raio, lateral esquerda, lateral direita, cambagem, direção, normal (3), comprimento, vetor para a frente (3), marca e inclinação (`Grade`) | o `AiPointExtra.cs` |
| grade | `HasGrid` (1), o máximo e o mínimo (3 floats cada), 10 vizinhos, a densidade de 10 m, 135 colunas; por coluna, 173 células; por célula, a contagem (10) e 10 índices | o `AiSplineGrid.cs` e o arquivo |

- **O item 5 do contexto confere,** com duas correções:
  - **o addon lê o bloco de 18 floats sem pular o inteiro da contagem.** Por isso, os rótulos dele ficam deslocados: o "unknown" do índice 0 é o 18º campo (`Grade`, a inclinação), e a velocidade vem no índice 1. Pelos valores, a ordem do `AiPointExtra.cs` é a certa (a velocidade, de 19 a 72 m/s, é o primeiro float depois da contagem);
  - **depois dos extras vem a grade de vizinhos,** que o addon não lê.
- **A grade é recalculável:**
  - os extremos são os dos pontos, com 350 m de folga;
  - colunas e linhas são o piso de extensão / 10 m;
  - cada célula guarda os 10 pontos mais próximos do centro dela, em X/Z, do mais perto ao mais longe.

  Recalculada, ela fica igual em 23.326 das 23.355 células, e os extremos são iguais. Nas outras 29, os pontos empatam em menos de 0,05 mm: 28 têm o mesmo conjunto e 1 troca o 10º vizinho.
- **O leitor e o escritor** estão em `backend/ml/pista_teste/ai_spline.py`. **Ler o original e escrever de novo dá o arquivo byte a byte igual.** Não há bytes depois da grade.
- **As fontes:**
  - `gro-ove/actools`, pasta `AcTools/AiFile` (`AiSpline.cs`, `AiPointExtra.cs`, `AiSplineGrid.cs`): https://github.com/gro-ove/actools/tree/master/AcTools/AiFile;
  - o addon `io_import_accsv` (`import_ai.py`): https://github.com/leBluem/io_import_accsv;
  - a regra do addon de sobrescrever só uma linha com o mesmo número de pontos: https://www.modland.net/assetto-corsa-mods/other/blender-addon-importexport-aicsvini-files.html.

### A.3, o referencial

| medida | mediana | p95 | máximo |
|---|---:|---:|---:|
| pontos do `fast_lane.ai` até a volta `#0013` gravada | **0,21 m** | 0,94 m | 1,33 m |
| volta `#0013` até o `fast_lane.ai` | 0,21 m | 0,95 m | — |
| o mesmo, com o `z` invertido | 49,2 m | — | — |

**É o mesmo referencial** (`x` e `z` do mundo, como as gravações), e a mediana fica bem abaixo dos 2 m. **A IA de 04/10 segue a linha do arquivo de perto.**

### A.4, os campos e a regra de cada um para uma linha nova

| campo | o que guarda no original (pelos valores) | regra para a linha nova | erro da regra aplicada ao próprio original |
|---|---|---|---|
| posição | x, altura, z | o ponto `i` na mesma estação `s` da pista que o ponto `i` original | — |
| distância | o comprimento 3D acumulado (1 mm por passo) | o mesmo, da linha nova | até 0,69 m de deriva acumulada em 4,2 km |
| velocidade | de 19,3 a 71,9 m/s; dá uma volta de **95,1 s**, e a IA faz 84,8 s | a do ponto original da mesma estação | — |
| acelerador, freio | os pedais gravados (778 pontos com acelerador abaixo de 1; 795 com freio) | os do ponto original da mesma estação | — |
| `ObsoleteLatG`, marca | sempre 0 | 0 | — |
| raio | o raio do círculo pelos pontos `i−1`, `i` e `i+1`, em X/Z | o mesmo, da linha nova | 0,1% (mediana), 1,4% (p95) |
| direção | o lado da curva (±1) | o mesmo, da linha nova | igual em 100% |
| vetor para a frente | a direção a partir do ponto anterior | o mesmo, da linha nova | exato |
| inclinação | o Y do vetor para a frente | o mesmo | 1e-5 (mediana) |
| comprimento | o segmento 3D até o ponto anterior | o mesmo | 1,5 cm no máximo |
| normal | a normal da superfície | a do ponto mais próximo da linha original (interpolada) | exata |
| cambagem | `direção × (normal · esquerda)` | a mesma fórmula, com a normal e a direção da linha nova | 3e-4 (mediana); erro maior que 0,01 em 105 pontos (3,9%) |
| laterais | as distâncias até as bordas, na esquerda `(fz, −fx)` do ponto | **a borda fica no mesmo lugar e a distância muda.** Onde a linha passa da borda da IA, a lateral fica em 0 | exatas |

- **O último ponto do original** traz um comprimento de 8,3 m e uma direção de 0,1, que não saem da geometria (sobra da gravação). A regra recalcula esse ponto como os outros.
- **As bordas da IA são outras.** A largura entre as laterais é 3,0 m menor que a do corredor do pedido 44 (mediana; p5 de −9,3 m). As bordas ficam a 1,4 m (esquerda) e a 1,6 m (direita) das bordas do corredor (mediana). **Por isso, onde uma linha do corredor passa da borda da IA, a lateral fica em 0:** isso acontece em 8 pontos da C2 (até 8 cm) e em 4 da C4 (até 1,4 cm).
- **A velocidade e os pedais:** as fontes não concordam, e a velocidade gravada não é o teto da IA (95,1 s contra 84,8 s). **A regra é manter os do original na mesma estação,** igual para C1 a C4, e está registrada no ADR 0029 com o porquê. Assim, C1 contra C0 mede o custo da regra e da codificação juntas.
- **As dicas da IA:** não há `ai_hints.ini`, e nada muda.

**Todos os campos têm uma regra defensável.** Não parei.

### A.5, o app com outro nome de pista

- **O gravador** grava qualquer pista: a aba Coleta só avisa quando a pista não é `vhe_interlagos` (`core/coleta/requisitos.py`). A pasta da gravação leva o nome da pista (`<data>_vhe_interlagos_teste_m1`).
- **O backend** resolve a pasta da pista pelo nome exato (`core/track_file_resolver.py`): a cópia vira ela mesma, e a original continua ela mesma. O cache de geometria que ele monta para a cópia tem o nome dela, num arquivo à parte.
- **O ML incluiria as sessões da cópia.** O filtro de `ml.data.recordings.list_sessions` é o prefixo `vhe_interlagos`, e `vhe_interlagos_teste_m1` começa com ele. Todos os caminhos do inventário, do store v2, do treino do coach (`train_reference_model`), da evolução (que lê o store), do Modelo 2 e do retreino passam por essa função.
- **A exclusão explícita:** `config.TEST_TRACK_NAMES = ("vhe_interlagos_teste_m1",)`. O `list_sessions` sempre a exclui, salvo com `incluir_pistas_de_teste=True`, que só o resultado deste pedido usa. **Testado:** com sessões sintéticas, e com uma varredura do código que confere que só `ml/pista_teste/etapas.py` pede as sessões da cópia.
- **O cuidado até o merge:** o app instalado (0.7.0) e a pasta principal não têm essa exclusão. O botão "Atualizar coach e relatório" roda o `atualizar_coach` da pasta principal. **Até o merge do 47, ele não pode ser apertado** com as gravações da cópia na pasta do app (está no roteiro).

### A.6, a linha nova em 3D

| | pontos | espaçamento (mín. / mediana / máx.) | fechamento | comprimento | maior distância do original | laterais no piso de 0 |
|---|---:|---|---:|---:|---:|---|
| original | 2.680 | 1,50 / 1,568 / 5,03 m | 1,76 m | 4.224,9 m | — | — |
| C1 | 2.680 | 1,26 / 1,575 / 5,04 m | 1,76 m | 4.226,3 m | 1,37 m (mediana 0,32) | nenhuma |
| C2 | 2.680 | 1,18 / 1,582 / 5,04 m | 1,76 m | 4.246,2 m | 11,29 m (mediana 1,31) | 8 pontos, até 8 cm |
| C3 | 2.680 | 1,14 / 1,579 / 5,04 m | 1,76 m | 4.239,9 m | 10,76 m (mediana 0,99) | nenhuma |
| C4 | 2.680 | 1,12 / 1,578 / 5,04 m | 1,76 m | 4.232,2 m | 10,07 m (mediana 1,06) | 4 pontos, até 1,4 cm |

- **O mesmo número de pontos do original** (2.680), cada um na mesma estação do ponto original. O ponto 0 fica no mesmo lugar ao longo da pista.
- **O sentido** é o mesmo: as estações crescem sempre.
- **A linha fecha:** o último ponto antecede o primeiro, a 1,76 m.
- **A altura** é a do ponto mais próximo da linha original, projetada no segmento. O espaço de 5 m que já existe no original aparece também nas linhas novas.

### A.7, os arquivos derivados

- **Na pasta da pista** não há nada derivado da linha além do próprio `fast_lane.ai`. O `ai\` tem só o `fast_lane.ai` e o `pit_lane.ai`.
  - O `data\ideal_line.ai` tem o mesmo tamanho do `fast_lane.ai`, mas é outro arquivo (a linha que o jogo mostra), e o conteúdo dele não foi lido;
  - o `data\side_l.csv` e o `data\side_r.csv` não foram abertos.
- **O CSP guarda caches da linha da IA fora da pasta da pista,** em `cache\ai_grids`, `cache\ai_payloads` e `cache\ai_alt_lanes`, com o nome da pista e um hash: hoje há 4 arquivos de `vhe_interlagos_gp` em cada uma das duas primeiras pastas. **A cópia terá caches próprios,** porque o nome entra na chave. Eu não sei se o hash muda com o conteúdo da linha.
  - **O que os scripts fazem:**
    - a cada troca, o `trocar_linha.ps1` apaga na cópia o `gp\ai\fast_lane.aip`, se existir;
    - ele põe a data de agora no arquivo novo;
    - ele lista, sem apagar, os caches da cópia em `data\pista_teste\caches_csp.log`;
  - **apagar os caches seria escrever fora da cópia,** o que o pedido não permite. Se o CSP reusar um cache velho, a conferência E.1 mostra, e a condição sai do veredito.

### A.8

Nenhum item parou. O plano B não foi necessário.

## Parte B: os valores fixos (ADR 0029)

**Registrado em `9544ff0b`, antes de gerar qualquer arquivo de linha e antes de qualquer sessão no jogo.** Depois, uma **emenda antes do jogo** (item 14) diz como cada valor é aplicado, sem mudar nenhum; ela vai no commit deste relatório, também antes do jogo.

| o quê | valor |
|---|---|
| condições | C0 a linha original; C1 a volta da IA `#0013` codificada; C2 a sua `2026-10-24_13-43-32#0003` codificada; C3 `linha_sem_lstm.npy`; C4 `linha_com_lstm.npy`; C0 final |
| preset | Formula RSS 3 2026 V6, acerto padrão, prática sozinho, 30 L sem consumo, composto padrão sem desgaste, ar a 25 °C ("Clear"), aderência fixa em 100%, 14:00 com o tempo parado, IA a 100% e agressividade 0% |
| ordem | `numpy.random.default_rng(47).permutation(["C1","C2","C3","C4"])` = C1, C4, C2, C3. **Ordem completa: C0, C1, C4, C2, C3, C0 final** |
| voltas | 9 por condição (6 no C0 final); a de saída e a primeira lançada ficam fora; contam 7 (4 no C0 final) |
| volta válida | completa (cobertura ≥ 95%); saída do corredor útil ≤ 1,0 m e sem `offTrack`; sem rodada (ângulo > 45° acima de 30 km/h); sem boxes (a 3 m do `pit_lane.ai` e 1 m fora do corredor, ou `pit_lap` do store); `isAIControlled` em todas as amostras |
| atribuição | a gravação pertence à condição da última troca do `registro.csv` antes do `startedAt` dela; com o sha256 conferido |
| veredito | diferença das medianas contra C0, IC 95% por bootstrap (10.000, semente 47): mais rápida (sup. < 0); tão rápida (sup. ≤ +0,10 s); mais lenta (inf. > +0,10 s); não conclusivo; não dirigível (< 5 válidas das 7) |
| deriva | C0 final contra C0 > 0,15 s: "não conclusivo (deriva)" |
| só relatados | C1 contra C0, C2 contra C0, C3 e C4 contra C1, e a conferência da troca |

**O medidor de cada condição (B.8), calculado antes do jogo:**

| condição | medidor | contra C0 | microssetor 36 | microssetor 0 | microssetor 1 |
|---|---:|---:|---:|---:|---:|
| C0 | 1:25,316 | — | — | — | — |
| C1 | 1:27,955 | +2,638 | −0,119 | +0,029 | +0,014 |
| C2 | 1:27,679 | +2,363 | −0,414 | +0,025 | +0,011 |
| C3 | 1:22,898 | −2,419 | −1,001 | 0,000 | −0,013 |
| C4 | 1:23,481 | −1,835 | −1,013 | 0,000 | −0,009 |

- **A ordem no medidor:** C3, C4, C0, C2, C1.
- **O C0 do medidor** é a linha do arquivo, projetada na grade, e dá 1:25,316. A volta `#0013`, que fica a 0,21 m dessa linha, dá 1:26,284 no mesmo medidor. Uma diferença de 1 s por 0,2 m de linha reforça o que o pedido 46 achou: o medidor é sensível ao ruído da linha.

**O que se espera (B.9, no ADR):**
- C0 perto de 1:24,8 a 1:25,2;
- C1 a ±0,3 s de C0 (o medidor prevê +2,6 s);
- **C3 e C4 entre −0,3 e +0,5 s de C0,** com "tão rápida quanto" ou "não conclusivo" como o mais provável. Por quê:
  - o ganho do medidor está quase todo no microssetor 36;
  - a IA não anda no limite do envelope;
  - a velocidade e os pedais ficam os da linha original;
- C2 mais lenta.

## Parte C: os arquivos e os scripts

### As linhas (em `data\pista_teste\linhas\`, fora do git)

| condição | arquivo | bytes | sha256 |
|---|---|---:|---|
| C0 | `C0\fast_lane.ai` (cópia do original) | 1.274.780 | `36b57fd8d259755d9b25ffdc1f61e328479045fc275e554b7b7e3de7eb3d8342` |
| C1 | `C1\fast_lane.ai` | 1.274.780 | `9fc17f49070aa68908908e971c9d8a571ece6be4f4d3843cf37270c2cd5381d4` |
| C2 | `C2\fast_lane.ai` | 1.282.396 | `015d939eaa852f634bced7e6424c2a45e434170b44dd797f0a539764415ca7c1` |
| C3 | `C3\fast_lane.ai` | 1.282.396 | `85e94218c6a353c1d5f194aac197be26701be2c0d0980adc87234ecc4bb50c10` |
| C4 | `C4\fast_lane.ai` | 1.282.396 | `0f747583c8b6d3ee7a7e87d83d32ee778438cce3ac7cb41dc1149bf82ee2f5d5` |

- **Os arquivos de C2 a C4 têm 7.616 bytes a mais,** porque a grade recalculada ganhou uma coluna: as linhas se afastam até 11 m do original, e os extremos mudam. A grade descreve o próprio tamanho, então o jogo lê as contagens do arquivo.
- **Cada arquivo foi relido** e volta igual, byte a byte, com 2.680 pontos.
- **O comando:** `python -m ml.scripts.pista_teste linhas` (de `backend\`). O `data\pista_teste\` está no `.gitignore`, e nenhum `.ai` entrou nos commits (conferido).

### Os scripts (`tools\pista_teste\`, você roda)

| script | o que faz |
|---|---|
| `criar_copia.ps1` | registra o sha256 do `fast_lane.ai` original em `data\pista_teste\copia.json`, copia a pista inteira para `vhe_interlagos_teste_m1` sem abrir os arquivos, troca o nome em `ui\gp` e `ui\norm` (UTF-8 sem BOM, só a linha do nome) e confere a original depois |
| `trocar_linha.ps1 -Condicao C0\|C1\|C2\|C3\|C4` | confere o arquivo da condição contra o `linhas.json`, apaga na cópia o `gp\ai\fast_lane.aip` (se existir), apaga os caches do CSP da cópia (só `cache\ai_grids`, `ai_payloads` e `ai_alt_lanes`, só nomes que começam com `vhe_interlagos_teste_m1_`; desde 08/11), copia a linha com a data de agora, escreve no `registro.csv` (hora, condição, sha256, arquivo) e no `caches_csp.log` (o que apagou), e confere a original antes e depois |
| `remover_copia.ps1` | apaga a cópia, e só ela, conferindo a original antes e depois |

**Os três:**
- recusam rodar com o jogo aberto (`acs`, `acs_x86`, `AssettoCorsa`);
- conferem o caminho antes de escrever ou apagar: tem de ficar dentro de `content\tracks\vhe_interlagos_teste_m1`, nunca dentro da original e sem junção ou link no caminho;
- usam `-LiteralPath` em tudo.

O `.ps1` só tem ASCII, para o PowerShell 5.1.

### A figura

`_linhas_na_pista.png`: as 5 linhas sobre a pista inteira, com o detalhe da C10 (e o microssetor 36, na freada dela) e da saída da linha de chegada (microssetores 0 e 1).

### O código

- `backend/ml/pista_teste/ai_spline.py`: o leitor, o escritor e a grade;
- `backend/ml/pista_teste/linha_nova.py`: as regras de cada campo e a conferência delas no original;
- `backend/ml/pista_teste/condicoes.py`: as condições e as linhas laterais;
- `backend/ml/pista_teste/registro.py`: o `registro.csv`, a atribuição e os papéis das voltas;
- `backend/ml/pista_teste/etapas.py`: a Parte C e o resultado da Parte E (pronto, ainda sem dados);
- `backend/ml/scripts/pista_teste.py`: os comandos `parte-a`, `medidor`, `linhas` e `resultado`;
- `backend/ml/config.py` e `backend/ml/data/recordings.py`: a exclusão da A.5.

**O coach, o rádio, o app, o store v2, a M1 e o Modelo 2 não mudaram,** salvo a exclusão da A.5.

**Antes da parada, testei as medidas da Parte E numa gravação antiga** (04/10, não da cópia). As 9 voltas da IA saem válidas: saída máxima do corredor de 0,84 m e ângulo máximo de 22°. As voltas humanas e as que passam pelos boxes saem inválidas, com o motivo. O tempo do store bate com o cronômetro do jogo em até 3 ms nas voltas da IA.

## Parte D: o teste no jogo, com você

### O roteiro

**Antes de começar:**

1. **Não aperte "Atualizar coach e relatório"** no app nem rode o `atualizar_coach` na pasta principal até o merge do 47. O código deles ainda não exclui a cópia.
2. **Não traga as gravações da cópia** para `data\recordings`: elas ficam na pasta do app instalado e só são lidas.
3. **Grave com o app instalado** (0.7.0, o de hoje). **Por quê:**
   - ele grava em `%APPDATA%\Automobilista Telemetria`, fora dos dois repositórios;
   - o app de desenvolvimento da pasta separada leria e escreveria `data\` pelas junções, ou seja, na pasta principal. O backend de desenvolvimento regrava `data\cache\tracks`.

   A aba Coleta vai avisar que a pista não é a esperada: é só um aviso, e a gravação segue. O rádio pode ficar desligado.
4. **No Content Manager,** grave o preset "pedido 47 [teste]":
   - carro: Formula RSS 3 2026 V6, com o acerto padrão;
   - pista: "Interlagos [teste]", layout GP;
   - modo: prática, sozinho, largando dos boxes;
   - combustível: 30 L, com o consumo em 0×;
   - pneus: o composto padrão, com o desgaste em 0×;
   - clima: "Clear", com o ar a 25 °C;
   - pista: 100% ("Optimum"), sem evolução;
   - horário: 14:00, com o tempo em 0×;
   - ajudas: as de sempre, anotadas na primeira linha das anotações.

   Na primeira vez, a cópia só aparece depois do passo 5.

**A cópia e as trocas** (PowerShell, com o jogo fechado; o Content Manager pode ficar aberto):

5. Uma vez só, no começo:
   ```powershell
   cd C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47
   powershell -ExecutionPolicy Bypass -File tools\pista_teste\criar_copia.ps1
   ```
6. **Para cada condição, nesta ordem: C0, C1, C4, C2, C3 e C0 de novo** (o C0 final):
   ```powershell
   powershell -ExecutionPolicy Bypass -File tools\pista_teste\trocar_linha.ps1 -Condicao C0
   ```
   (troque `C0` pela condição da vez). Depois:
   - abra o jogo pelo preset;
   - nos boxes, aperte **Ctrl+C** para a IA dirigir, com nível 100% e agressividade 0%, e deixe-a sair dos boxes;
   - **deixe a IA completar 9 voltas** (6 no C0 final). A 1ª é a de saída e a 2ª, a primeira lançada; as outras contam. **Espere a IA cruzar a linha ao fim da última volta antes de sair**, para o tempo dela ficar completo;
   - **feche o jogo** (sair do jogo, até o `acs.exe` fechar) antes da próxima troca;
   - anote a linha da condição no `_anotacoes.csv`.
7. **Duas sessões de no máximo 45 minutos.** Uma condição de 9 voltas leva cerca de 14 minutos (13 de voltas e 1 de troca).
   - **Sessão 1:** C0, C1 e C4 (cerca de 42 min).
   - **Sessão 2:** C2, C3 e C0 final (cerca de 38 min).
   - **Entre as duas** (mudança de 08/11): ao fim da sessão 1, com o jogo fechado, avise "terminei a sessão 1". Eu faço só a conferência da troca (sem nenhum tempo) e digo se você pode seguir. Até lá, não rode nenhum script. A cópia fica instalada.
8. **Se a IA rodar ou sair da pista,** deixe seguir: a volta é descartada pelo resultado. Se ela não conseguir andar (presa, rodando a cada volta), feche o jogo, anote e passe para a próxima condição.
9. **Se algum script parar** com "PARADO: …", não contorne: anote a mensagem e me avise.

**A linha ideal do jogo não mostra a troca** (ela vem do `data\ideal_line.ai`). A conferência é a da E.1: as posições gravadas têm de ficar mais perto da linha da condição do que da original.

**Ao terminar, avise: "rodei a IA nas linhas".** Eu confiro o teste (E.1 a E.6), gravo o resultado, faço a Parte F, o merge e o envio. A cópia fica instalada até você rodar o `remover_copia.ps1`:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47\tools\pista_teste\remover_copia.ps1
```

### A tabela das anotações

`docs/handoff/2026-11-07_47_linha-gerada-no-jogo_anotacoes.csv`:

| ordem | condicao | hora_inicio | hora_fim | voltas_completas | ia_saiu_da_pista | ia_rodou | entrou_nos_boxes | jogo_travou_ou_fechou | observacoes |
|---|---|---|---|---|---|---|---|---|---|
| 1 | C0 | | | | | | | | |
| 2 | C1 | | | | | | | | |
| 3 | C4 | | | | | | | | |
| 4 | C2 | | | | | | | | |
| 5 | C3 | | | | | | | | |
| 6 | C0 final | | | | | | | | |

## Testes

**`backend/tests/test_pista_teste.py`: 20 testes, todos com dados sintéticos, todos passando:**

- **a ida e volta,** byte a byte: o arquivo inteiro, os campos, a grade, o tamanho esperado de cada bloco, um cabeçalho com tempo e amostras e bytes depois da grade. O leitor recusa outra versão;
- **a grade recalculada:** a mesma nas duas chamadas, com a folga de 350 m e as células ordenadas pela distância;
- **as regras reproduzem um original sintético** (a linha da IA num círculo);
- **a linha nova,** 1 m para fora no círculo:
  - o mesmo número de pontos, no raio certo, fechada;
  - no sentido certo, com o ponto 0 na mesma estação;
  - com o espaçamento do original na proporção do raio e as alturas do original;
  - laterais de 4 e 6 m (a borda fica no lugar);
  - a velocidade do original e o raio da linha nova;
- **a lateral além da borda fica em 0**, e uma linha da grade errada é recusada;
- **os scripts, numa pasta falsa `[teste] pista falsa` (apagada no fim, com isso conferido):**
  - o `criar_copia`, o `trocar_linha` (C0, C3, C0) e o `remover_copia` funcionam, com o nome trocado em UTF-8 e o "São Paulo" intacto;
  - o `registro.csv` sai como `C0, C3, C0 final`;
  - **o hash de todos os arquivos da pista original é o mesmo antes e depois;**
  - **com o jogo "aberto"** (o nome do processo do próprio PowerShell), os três recusam e nada muda;
  - **um caminho fora da cópia** (dentro da original, em outra pista, fora do jogo) é recusado;
  - **uma cópia que é uma junção para a original é recusada,** e a original não muda;
  - um arquivo de linha que não bate com o `linhas.json` é recusado;
- **a exclusão:**
  - com sessões sintéticas, a da cópia fica fora do `list_sessions` e do `list_all_sessions`, e só entra com a opção;
  - uma varredura do código confere que só `ml/pista_teste/etapas.py` pede a opção;
  - o inventário, o store, o treino do coach, o Modelo 2 e a M1 listam sem ela;
- **a atribuição pelo `registro.csv`:**
  - a última troca antes do início, o C0 final, a recusa por sha256 errado e a gravação anterior à primeira troca;
  - o CSV real com BOM e maiúsculas;
  - os papéis das voltas (saída, primeira lançada, as 7 que contam, as além delas, duas gravações na mesma condição);
- **o veredito e o bootstrap:** as 5 saídas, a deriva, a semente fixa e o formato M:SS,mmm.

**A suíte do backend:** `1 failed, 939 passed, 37 warnings in 943.15s` (a saída inteira em `_testes.txt`). A falha é `test_leitura.py::test_volta_da_conferencia_nos_arquivos_reais`, e **é do ambiente, não do código:**

- o teste lê `data/reference_models/vhe_interlagos.geometry.json`, que o git ignora;
- o arquivo existe na pasta principal, e a pasta separada não tem junção para `data/reference_models` (a pasta é versionada em parte, com os `*.optimal.json`);
- com o código da pasta separada lendo esse arquivo da principal, as mesmas asserções passam (conferido).

Nenhum arquivo deste pedido toca em `core/leitura`.

**Os dados da pasta principal ficaram intactos:** a foto de `data\ml` (616 arquivos), `data\cache` (3) e `data\recordings` (313) é a mesma antes de tudo e depois da suíte, sem nenhuma diferença de nome, tamanho ou data.

## O envio ao GitHub

**Antes do primeiro envio, conferi:**
- nenhum arquivo passa de 50 MB (o maior é a figura, com menos de 1 MB);
- nada de `recordings/`, `data/recordings` ou `data/ml`, e nenhum `.ai`;
- nenhum segredo, por busca no diff.

**Só a branch do pedido vai, como avanço simples e sem `--force`.** `develop`, `main` e as tags não vão antes do merge.

| envio | ref | hash local | hash no remoto (`git ls-remote origin`) | confere |
|---|---|---|---|---|
| depois da Parte 0 | `etapa/linha-gerada-no-jogo` (nova) | `c0bbe9fde5fc0d65aab305bf1957fb6d2bf0a665` | `c0bbe9fde5fc0d65aab305bf1957fb6d2bf0a665` | sim |
| depois das Partes A e B | `etapa/linha-gerada-no-jogo` | `9544ff0bb02282ba0b794b23cf940a65537693fe` | `9544ff0bb02282ba0b794b23cf940a65537693fe` | sim |
| antes da parada (Parte C, a emenda e este relatório) | `etapa/linha-gerada-no-jogo` | `3e48e0d724813dec6651ac1f1c7057e68e58d2f7` | `3e48e0d724813dec6651ac1f1c7057e68e58d2f7` | sim |

Este registro vai num commit à parte (`Relatorio do pedido 47: o envio da parada conferido`), também enviado; o hash dele está no chat.

## Atualização de 08/11: as duas mudanças de mecânica, antes do teste

Você pediu, antes do teste (nenhum critério muda):

1. **O `trocar_linha.ps1` apaga os caches do CSP da cópia.** A cada troca, ele apaga, nas pastas `cache\ai_grids`, `cache\ai_payloads` e `cache\ai_alt_lanes`, só os arquivos cujo nome começa com `vhe_interlagos_teste_m1_`, e lista o que apagou em `data\pista_teste\caches_csp.log`.
   - **Testado na pasta falsa "[teste]":**
     - os três caches da cópia somem;
     - oito arquivos parecidos ficam: os da original, os de `vhe_interlagos40`, um nome sem o `_` depois de `teste_m1`, um em maiúsculas, um em `tracks_data`, um solto em `cache\` e um dentro de uma subpasta;
     - uma troca sem caches registra zero;
     - uma pasta de cache que é junção é recusada, sem apagar nada e sem trocar a linha.
   - **A emenda está no ADR 0029, item 15,** antes de qualquer gravação na cópia.
   - **A troca do C0 que você já fez** (08/11, 00:13:08, com a versão anterior do script) vale como está. Ainda não havia cache da cópia, porque o jogo não tinha aberto a cópia, e nenhuma gravação da cópia existe. **Não precisa rodar o C0 de novo:** a próxima troca (C1) já apaga os caches que a sessão do C0 criar.
2. **A conferência entre as sessões:** o comando novo `python -m ml.scripts.pista_teste conferencia --rotulo sessao1` faz só a E.1:
   - a atribuição das gravações;
   - as voltas por papel e quantas a IA dirigiu;
   - a distância mediana das posições das voltas que contam até a linha da condição e até a original;
   - "a troca pegou?".

   **Ele não mede nem mostra nenhum tempo.** O cronômetro só separa as voltas, como no store. Testado com dados sintéticos. Quando você avisar "terminei a sessão 1", eu rodo o comando e digo se você pode seguir.

**Testes:** `test_pista_teste.py` agora tem 23 testes, todos passando. Os três novos são a limpeza dos caches, a junção na pasta de cache e a conferência da troca.

## Conferência de 08/11, 13:40: os caches do CSP depois da troca para C1

Você perguntou por que a troca para C1 (08/11 às 02:00:28) registrou "0 cache(s) do CSP apagado(s)". Conferi só nomes, tamanhos e datas, sem nenhum tempo de volta:

1. **Nenhum arquivo de `cache\ai_grids`, `cache\ai_payloads` ou `cache\ai_alt_lanes` foi criado ou modificado depois de 08/11 00:13.** Nenhum arquivo de nenhuma outra pasta de `cache\` do jogo mudou depois disso.
2. **Não existe gravação da cópia** no app instalado, nem no repositório. A última gravação do app é `2026-11-07_19-52-33_vhe_interlagos` (o teste do pedido 45).
3. **O jogo não rodou desde 07/11 às 20:15:**
   - o `Documents\Assetto Corsa\logs\log.txt` (reescrito a cada vez que o jogo abre) e o `custom_shaders_patch.log` são de 07/11 20:15:38;
   - o `cfg\race.ini`, que o Content Manager escreve a cada largada, aponta para `TRACK=vhe_interlagos` (a original), e não para a cópia;
   - nenhum processo do jogo estava aberto.
4. **Então o CSP não gravou nenhum cache da cópia, com nenhum nome.** Ele nunca carregou a cópia. Não há o que ajustar no padrão `vhe_interlagos_teste_m1_` por enquanto. Ele só pode ser conferido depois da primeira sessão na cópia: a troca seguinte lista no `caches_csp.log` o que apagou.

**A consequência: a sessão do C0 não aconteceu.**
- O `registro.csv` tem a troca do C0 (00:13:08) e logo depois a do C1 (02:00:28), sem nenhuma gravação entre elas. A cópia está hoje com a linha da C1 (sha256 `9fc17f49…`).
- **Para seguir a ordem do ADR (C0 primeiro),** o próximo passo é trocar de novo para C0 e rodar a sessão dele.
- **Mas o código daquele momento leria esse C0 novo como "C0 final",** porque ele vem depois de uma troca para C1 no registro. Propus uma correção só de mecânica: uma troca seguida de outra antes de qualquer gravação não conta.

### A correção, aprovada por você às 13:48 ("Sim, corrija")

- **A regra (ADR 0029, item 16):**
  - uma gravação continua pertencendo à última troca antes do início dela;
  - **o C0 final é só um C0 que vem depois de uma condição que teve gravação;**
  - as trocas sem gravação aparecem no resultado e na conferência com a nota "sem gravação".
- **O código:** `backend/ml/pista_teste/registro.py`:
  - o `ler` devolve as condições como estão escritas;
  - o `atribuir` decide o C0 final depois de saber quais trocas tiveram gravação;
  - o `trocas_rotuladas` mostra cada troca com o rótulo e as gravações dela.
- **Testado** com a sequência de 08/11 e a ordem completa depois dela: C0 e C1 sem gravação, e depois C0, C1, C4, C2, C3 e C0 final, todos com gravação. Saem C0, C1, C4, C2, C3 e "C0 final". `test_pista_teste.py` tem 24 testes, todos passando.
- **O registro real,** lido com a correção:
  - a troca do C0 de 00:13:08 e a do C1 de 02:00:28 ficam "sem gravação";
  - **você já trocou para o C0 de novo às 13:48:25.** A cópia está com a linha original (sha256 `36b57fd8…`), sem nenhum cache do CSP, e não há gravação da cópia;
  - **uma sessão que comece agora conta como C0.**
- **Você pode começar a sessão 1** (C0, C1 e C4), pelo roteiro.

## O que falta (depois do seu aviso "rodei a IA nas linhas")

1. **A Parte E:** `python -m ml.scripts.pista_teste resultado`, com as conferências E.1 a E.6 e os vereditos do ADR 0029, sem mudar nada do registro.
2. **A Parte F:**
   - o resultado no ADR 0029 e no índice;
   - a seção do teste no jogo em `docs/arquitetura_ml.md`;
   - uma linha no ADR 0009, se o resultado mudar o que ele diz;
   - os itens do backlog.
3. **O merge em `develop`, na pasta separada.**
   - Se `develop` tiver andado (o merge do 45), trago `develop` antes. O conflito esperado é a linha do índice dos ADRs.
   - **Se a pasta principal estiver com `develop` aberta, eu paro e aviso.**
   - Depois do merge e do envio, a pasta separada volta para a branch do pedido.
4. **A cópia fica instalada** até você rodar o `remover_copia.ps1`. A pasta separada não é apagada.

**Nada aqui precisa de decisão sua agora.** Só o teste no jogo.

## Itens para o backlog (para o Cowork)

1. **O cache do CSP para a linha da IA** (`cache\ai_grids`, `ai_payloads`, na pasta do jogo) tem uma chave que eu não conheço. Se a E.1 mostrar que uma troca não pegou, limpar esses caches pede um pedido próprio, porque eles ficam fora da cópia.
2. **O app instalado precisa ser refeito depois do merge do 47,** para ganhar a exclusão das sessões da cópia. Até lá, vale a regra do roteiro: nada de "Atualizar coach" com as gravações da cópia na pasta do app.
3. **`vhe_interlagos40`** também passa no filtro de prefixo do ML. Vale conferir se as sessões dessa outra pista deveriam entrar (hoje entram, se existirem).
4. **O medidor dá 1 s de diferença entre a linha do `fast_lane.ai` e a volta `#0013`,** que fica a 0,21 m dela. Isso reforça o item 2 do backlog do pedido 46: o medidor é sensível ao ruído da linha.
5. **A pasta `_obj_export`** (877 MB) dentro da pista não é do jogo. Ela vai junto na cópia. Vale saber de onde veio.
6. **A regra de memória "toda sessão com mais de 5 voltas entra no coach e vai para `data\recordings`"** não vale para as sessões da cópia. Vale registrar essa exceção onde a regra estiver escrita.
7. **A cambagem** da regra difere do original em 3,9% dos pontos (erro acima de 0,01). A fórmula pode ter mais um termo; o efeito no teste é desconhecido e igual para C1 a C4.
