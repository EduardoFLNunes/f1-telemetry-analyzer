# Pedido 47 — A linha gerada no jogo: a IA do Assetto Corsa dirige a linha do Modelo 1

**De:** Eduardo. **Data:** 07/11/2026 (atualizado em 07/11: começa já, numa pasta separada, e a Parte A ganhou o que se sabe do formato).
**Tipo:** Modelo 1 (`backend/ml/optimization/` e scripts), ferramentas em `tools/pista_teste/`, documentação e testes. O coach, o rádio, o app, o store v2, a M1 e o Modelo 2 não mudam.

**Quando começar: agora, numa pasta separada (minha decisão de 07/11).** A pasta principal (`C:\Users\Dokas\Desktop\f1-telemetry-analyzer`) fica na branch do pedido 45, que ainda espera mudanças e um teste no jogo. **Ela nunca troca de branch por causa deste pedido.** No pedido 46, a pasta trocou de branch no meio do teste do 45, e o app do jogo foi instalado da branch errada.

### Parte 0 — A pasta separada

1. **Crie a pasta com `git worktree`,** a partir da principal, sem trocar a branch dela:
   ```powershell
   git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer worktree add C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47 -b etapa/linha-gerada-no-jogo develop
   ```
   Todo o trabalho deste pedido acontece em `f1-telemetry-analyzer-47`.
2. **O texto deste pedido** está sem commit na pasta principal. Copie-o para a pasta separada e faça dele o primeiro commit da branch. Depois de conferir que os dois são iguais (sha256), apague a cópia da pasta principal, e só ela. É a única coisa que este pedido faz na pasta principal.
3. **Os imports:** confira que os testes e os scripts rodados na pasta separada usam o código dela, e não o da pasta principal (por exemplo, por instalação editável no `.venv`). Pode usar o `.venv` da principal, se os imports forem resolvidos para a pasta separada (por exemplo, com `PYTHONPATH`). Se não der sem instalar nada, pare.
4. **Os dados:** as gravações e `data/ml` são lidos da pasta principal, só para leitura, por caminho absoluto, variável de ambiente ou junção de pasta. **Nunca copie gravações.** O que este pedido gera vai para `data/pista_teste/` da pasta separada.
5. **O processador:** antes de rodar algo pesado (a suíte inteira, a busca), confira se o jogo (`acs.exe`) está aberto. Se estiver, espere ou pare: pode ser o teste do 45.
6. **Uma sessão por pasta** (ADR 0008). Escreva uma linha de atualização no ADR 0008: "pastas separadas por `git worktree` são permitidas, com uma sessão em cada; decisão de 07/11, pedido 47".
7. **Relate** o comando usado, como os imports e os dados foram resolvidos e o que foi apagado na pasta principal.

## Contexto

1. **O resultado do Modelo 1 no pedido 46** (ADR 0028, `data/ml/modelo1_final/`):
   - as linhas geradas ficam abaixo da volta da IA no medidor do tempo: 1:22,898 sem a LSTM e 1:23,481 com ela, contra 1:26,284 da volta da IA (`2026-10-04_03-42-10#0013`, 1:24,829 no cronômetro);
   - **mas o medidor não ordena as voltas reais:** correlação de 0,36 com o cronômetro, e ele põe a minha melhor (1:24,048 no medidor, 1:26,568 no cronômetro) à frente da IA. Ele supõe o carro sempre no limite do envelope: mede a linha, não a execução;
   - a codificação da busca custa de 1,4 a 1,7 s às voltas reais no medidor;
   - o ganho se concentra em três microssetores: o 36, perto da C10, e o 0 e o 1, depois da linha.
2. **O objetivo do TCC:** uma volta gerada pelo menos tão rápida quanto a da IA. Falta um medidor que segure a execução constante e mude só a linha.
3. **A proposta:** a IA do jogo dirige a linha gerada. Mesmo piloto (a IA do Assetto Corsa), mesmo carro, mesmas condições; só a linha muda, e o tempo vem do cronômetro do jogo. A IA segue a linha do arquivo `ai\fast_lane.ai` da pista.
4. **A exceção autorizada por mim em 07/11, e só ela:** uma cópia da pista `vhe_interlagos`, com outro nome, para trocar a linha da IA na cópia.
   - **Ler:** a lista de arquivos e tamanhos da pasta da pista original; o conteúdo só dos arquivos de `ai\`, do nome em `ui\` e de `data\ai_hints.ini`, se existir.
   - **Escrever:** só na cópia, e só por scripts que eu rodo. Na cópia mudam apenas a linha da IA (e os arquivos derivados dela em `ai\`, se existirem) e o nome que aparece no jogo.
   - **A pasta da pista original nunca é escrita.** O sha256 do `fast_lane.ai` original é registrado antes e conferido depois do teste.
   - **O `data.acd` nunca é aberto,** nem outro arquivo do carro. Os outros arquivos da pista são copiados sem ser abertos.
5. **O que o Cowork achou sobre o formato** (ponto de partida, a confirmar no arquivo):
   - **o leitor do addon de Blender `io_import_accsv`** (`import_ai.py`, no GitHub) lê um cabeçalho de 4 inteiros de 32 bits, com o número de pontos no segundo. Em seguida vêm, por ponto, 4 floats e 1 inteiro (posição em 3D, com a altura no segundo float, a distância e o índice). Depois, um bloco de 18 floats por ponto, com os nomes que o addon dá: velocidade, acelerador, freio, `obsoleteLatG`, raio, lateral esquerda, lateral direita, cambagem, direção, normal (3), comprimento, vetor para a frente (3) e marca;
   - **o mesmo addon só sobrescreve uma linha com outra do mesmo número de pontos;**
   - **as laterais** (os limites da pista) ficam como distâncias a partir da linha. O jogo as junta à linha ao carregar a pista;
   - **as fontes não concordam sobre as velocidades e os pedais.** Um guia diz que a IA lê os pedais gravados na linha. Outro diz que a velocidade da gravação pouco importa, e que o que importa é a linha ser fluida. O `data\ai_hints.ini` muda o ataque, a freada e o limite de velocidade da IA por trecho;
   - **a linha ideal que o jogo mostra** vem de outro arquivo (`data\ideal_line.ai`), e não do `fast_lane.ai`. Ela não serve para conferir a troca;
   - outra fonte citada pela comunidade é a pasta `AiFile` do projeto aberto `gro-ove/actools` (do Content Manager).

## Parte A — Dá para fazer? (só leitura e contas, sem tocar no jogo)

1. **A pasta do jogo e a pista:** onde fica `content\tracks\vhe_interlagos`, se há layouts, a lista de arquivos de `ai\` com os tamanhos, o tamanho total da pasta e o espaço livre no disco. Um nome livre para a cópia (por exemplo `vhe_interlagos_teste_m1`) e o nome no jogo: "Interlagos [teste]".
2. **O formato do `fast_lane.ai`:** o cabeçalho, o número de pontos, os campos de cada ponto, o bloco de 18 floats e o que vier depois dele, conferidos contra o contexto, item 5, e citando as fontes. **Um leitor e um escritor, com um teste de ida e volta:** ler o original e escrever de novo dá um arquivo byte a byte igual.
3. **O referencial:** os pontos do `fast_lane.ai` contra as posições gravadas da volta `#0013`. Relate a distância mediana e o p95. Se não estiverem no mesmo referencial, ou a mediana passar de 2 m, pare.
4. **Os campos além da posição:** o que cada um guarda no arquivo original (confira os nomes do item 5 do contexto pelos valores: a velocidade da linha da IA, o raio contra a curvatura, as laterais contra as bordas do corredor) e o que se sabe sobre o jogo recalcular ou usar cada um. **Para uma linha nova, a regra de cada campo, e por quê:**
   - **as laterais** são recalculadas a partir das bordas da pista, para a linha nova: a borda fica no mesmo lugar e a distância muda;
   - **a geometria** (raio, direção, normal, vetor para a frente, comprimento) sai da linha nova;
   - **a velocidade e os pedais:** a mesma regra para C1 a C4, registrada no ADR 0029 com o porquê. Assim, C1 contra C0 mede o custo da regra e da codificação juntas;
   - **as dicas da IA** (`ai_hints.ini`): se elas forem indexadas pela posição na linha, a linha nova mantém a mesma parametrização.

   Se não houver como preencher um campo de forma defensável, pare.
5. **O app com outro nome de pista:** o que o gravador e o backend fazem com `vhe_interlagos_teste_m1` (lendo o código e com um teste sintético). As sessões da cópia ficam **fora** da evolução, do coach, do treino e do store; se algum caminho as incluir, ponha a exclusão explícita.
6. **A linha nova em 3D:** a altura de cada ponto (do ponto mais próximo da linha original), **o mesmo número de pontos do original**, o espaçamento, o fechamento na linha de chegada e o sentido.
7. **Os arquivos derivados:** o que o jogo e o CSP geram a partir da linha (na pasta da pista e nas pastas do CSP), e o que precisa ser apagado na cópia a cada troca para o jogo ler a linha nova.
8. **Se qualquer item parar,** relate o que faltou e estime o plano B: calibrar o medidor do tempo até ele ordenar as voltas reais (correlação alta e a IA à frente da minha melhor) e rodar a comparação de novo. Não comece o plano B.

## Parte B — Registrar antes de rodar (ADR 0029)

Escreva o **ADR 0029, "A linha gerada dirigida pela IA do jogo"** (ou o próximo número livre), antes de qualquer sessão no jogo. Tudo o que for fixado aqui sai das definições, nunca de olhar voltas da cópia.

1. **As condições,** todas na cópia, com o mesmo carro, o mesmo preset (acerto, combustível, pneu, temperatura, aderência da pista fixa, horário) e a IA dirigindo pelo Ctrl+C. C1 a C4 seguem a mesma regra de preenchimento dos campos (A.4):
   - **C0:** a linha original (o arquivo da cópia sem mudança);
   - **C1:** a volta da IA `#0013`, codificada como as linhas da busca do pedido 46;
   - **C2:** a minha melhor volta (`2026-10-24_13-43-32#0003`), codificada do mesmo jeito;
   - **C3:** a linha gerada sem a LSTM (`linha_sem_lstm.npy`);
   - **C4:** a linha gerada com a LSTM (`linha_com_lstm.npy`);
   - **C0 final:** a linha original de novo, no fim, para medir a deriva das condições.
2. **A ordem:** C0 primeiro; C1 a C4 em ordem sorteada com a semente 47; C0 final por último. Registre a ordem.
3. **As voltas:** 9 por condição (6 no C0 final). A volta de saída e a primeira lançada ficam fora; as 7 seguintes contam (4 no C0 final).
4. **A volta válida:** dentro do corredor do pedido 44 (`707d07029036abd6`), sem rodada, sem entrada nos boxes, com o tempo do jogo. Registre como cada coisa é medida.
5. **O veredito de C3 e C4 contra C0,** pela diferença das medianas, com intervalo de 95% por bootstrap (10.000 reamostragens, semente 47):
   - **mais rápida que a linha da IA:** o limite superior fica abaixo de 0;
   - **tão rápida quanto (não inferior):** o limite superior fica em até +0,10 s;
   - **mais lenta:** o limite inferior passa de +0,10 s;
   - **não conclusivo:** o resto;
   - **não dirigível pela IA:** menos de 5 voltas válidas das 7.
6. **A deriva:** se as medianas do C0 e do C0 final diferirem em mais de 0,15 s, os vereditos viram "não conclusivo (deriva)".
7. **Só relatados, fora do veredito:** C1 contra C0 (o custo da codificação no jogo), C2 contra C0 (a minha linha com a execução da IA) e C3 e C4 contra C1 (mesma codificação).
8. **O medidor do tempo** de cada condição, calculado agora, antes do jogo, para comparar depois a ordem do medidor com a do jogo.
9. **O que se espera,** escrito antes de rodar, com o porquê.
10. **A linha não vai para o coach** neste pedido (ADR 0009). Se ela passar, a decisão de usá-la é minha, num pedido próprio.
11. **Commite a Parte B antes de gerar os arquivos da Parte C.**

## Parte C — Os arquivos e os scripts

1. **As linhas:** os `fast_lane.ai` de C1 a C4 em `data/pista_teste/linhas/`, com o sha256 de cada um. **Eles ficam fora dos commits,** porque derivam de um arquivo da pista. Confira que `data/pista_teste/` está no `.gitignore`.
2. **Os scripts, em `tools/pista_teste/`, que eu rodo:**
   - `criar_copia.ps1`: copia a pista para a cópia, troca o nome no jogo e registra o sha256 do `fast_lane.ai` original;
   - `trocar_linha.ps1 -Condicao C0|C1|C2|C3|C4`: põe a linha na cópia, apaga só na cópia os arquivos derivados da linha, e escreve uma linha em `data/pista_teste/registro.csv` (hora, condição, sha256);
   - `remover_copia.ps1`: apaga a cópia, e só ela.

   Os três se recusam a rodar com o jogo aberto, nunca escrevem fora da cópia e conferem o caminho antes de escrever ou apagar.
3. **Uma figura:** as 5 linhas sobre a pista, com destaque na C10 e na saída da linha de chegada.
4. **Os testes** (Parte E) passando antes da parada.

## Parte D — Parada: o teste no jogo, comigo

Envie a branch antes de parar. **Durante a parada, a pasta separada fica nesta branch, e nenhuma sessão troca a branch dela até o meu aviso.**

Deixe no relatório:

1. **O roteiro passo a passo:** os comandos dos scripts (pelo caminho da pasta separada), com qual app gravar (o instalado ou o da pasta separada, e por quê), o preset, a ordem das condições, quantas voltas e quando fechar o jogo e trocar a linha. A linha ideal do jogo não mostra a troca (contexto, item 5); a conferência é a da E.1.
2. **No máximo 2 sessões de 45 minutos.** O rádio pode ficar desligado.
3. **Uma tabela para as minhas anotações** (`_anotacoes.csv`): condição, hora, voltas, se a IA saiu da pista ou rodou, e o que mais eu notar.
4. **Ao terminar, eu aviso: "rodei a IA nas linhas".**

## Parte E — Depois do meu aviso: o resultado

1. **Confira que o teste aconteceu:** as gravações com o nome da cópia, o `registro.csv` e o sha256 do `fast_lane.ai` original, igual ao de antes. **Confira também que a IA seguiu a linha de cada condição:** a distância mediana das posições gravadas à linha da condição tem de ser menor que à linha original (salvo no C0). Se não for, a troca não pegou: a condição sai do veredito, com o motivo.
2. **Cada volta numa condição,** pelo horário do `registro.csv`. Volta sem condição clara fica fora, com o motivo.
3. **As voltas válidas** e as descartadas, por condição, com o motivo.
4. **Os tempos:** a mediana e a dispersão de cada condição e os vereditos da Parte B, sem mudar nada do registro.
5. **Onde a linha ganha ou perde no jogo:** a diferença por microssetor de C3 contra C0, ao lado do que o medidor previa (os microssetores 36, 0 e 1 em destaque).
6. **O medidor contra o jogo:** a ordem das 5 linhas nos dois, só relatada.
7. **Testes,** em `tests/`, com dados sintéticos:
   - a ida e volta do leitor e do escritor, byte a byte;
   - a linha nova fechada, no sentido certo, com o espaçamento do original e as alturas;
   - os scripts recusando com o jogo aberto, recusando caminho fora da cópia e nunca escrevendo na original (numa pasta falsa "[teste]", apagada no fim);
   - a exclusão das sessões da cópia da evolução, do coach, do treino e do store;
   - a atribuição das voltas às condições pelo `registro.csv`.

   A suíte do backend continua passando.

## Parte F — Documentação

- **ADR 0029**, com o registro e o resultado; uma linha no índice.
- **`docs/arquitetura_ml.md`:** o teste no jogo como medidor da linha, e o resultado.
- **ADR 0009:** uma linha de atualização, se o resultado mudar o que ele diz.
- **`docs/backlog.md`:** não edite; liste os itens no relatório.
- **A cópia fica instalada** até eu rodar o `remover_copia.ps1`. O comando vai no relatório.

## Regras gerais

- **O coach, o rádio, o app, o store v2, a M1 e o Modelo 2 não mudam,** salvo a exclusão da A.5.
- **Nenhum critério muda depois de ver os números.** Os valores da Parte B são commitados antes do jogo.
- **Da pista, só a exceção do contexto, item 4.** O `data.acd` nunca é aberto, nem outro arquivo do carro.
- **Não toque na pasta do jogo:** quem roda os scripts sou eu (como o `instalar.ps1`, ADR 0020).
- **As gravações só são lidas.** Não apague, não mova e não copie nenhuma entre a pasta do app instalado e o repositório.
- **Não instale nem atualize pacotes.** Se algo pedir pacote novo, pare e relate.
- **Não contorne nenhuma trava:** se algo parar, pare também e registre o motivo.
- **Branch e commits:** branch `etapa/linha-gerada-no-jogo`, a partir de `develop`, na pasta separada (Parte 0); o texto deste pedido é o primeiro commit; commits por parte.
- **O merge, depois da Parte F, na pasta separada:**
  - se `develop` tiver andado (por exemplo, com o merge do 45), traga `develop` para a branch antes, resolvendo os conflitos simples (como as linhas do índice dos ADRs);
  - se a pasta principal estiver com `develop` aberta, pare e me avise: uma branch só pode estar aberta numa pasta;
  - depois do merge e do envio, volte a pasta separada para a branch do pedido, para `develop` ficar livre para a pasta principal;
  - não apague a pasta separada: eu decido quando.
- **A pasta principal e a branch do 45 não são tocadas,** salvo o item 0.2. As branches de outros pedidos também não.
- **Cópia no GitHub (vale para todo pedido):**
  - depois dos commits de cada parte e antes de cada parada, envie a branch do pedido ao `origin`; depois do merge, envie `develop`;
  - só envios que não reescrevem o remoto (branch nova ou avanço simples). Nunca `--force` nem `--force-with-lease`;
  - `main` e as tags não vão neste pedido;
  - antes do primeiro envio, confira que nada acima de 50 MB, nenhum segredo, nenhuma gravação (`recordings/`, `data/recordings`, `data/ml`) e nenhum arquivo `.ai` entrou nos commits;
  - depois de cada envio, confira com `git ls-remote origin` que o hash remoto é o mesmo do local;
  - se o controle de permissões da sessão recusar o envio, deixe no relatório os comandos para eu rodar pelo terminal;
  - se pedir login, se o envio for recusado pelo GitHub ou se o remoto tiver divergido, pare e me avise. Nenhum token ou senha no chat, nos arquivos ou no relatório.
- **Janelas e pastas de teste** levam "[teste]" e são fechadas ou apagadas no fim.
- **Os tempos de volta** no formato M:SS,mmm.
- **Relatório** em `docs/handoff/2026-11-07_47_linha-gerada-no-jogo_relatorio.md`, na pasta separada, com:
  - a Parte 0: a pasta, os imports, os dados e o que foi apagado na principal;
  - o que a Parte A achou (o formato, o referencial, os campos, as fontes) e se deu para seguir;
  - os valores fixos da Parte B e o commit em que foram registrados;
  - os arquivos, os sha256 e os scripts (Parte C);
  - o roteiro e a tabela (Parte D);
  - depois do teste, o resultado (Parte E) e os vereditos;
  - a saída dos testes e os commits;
  - o que foi enviado ao GitHub: a ref, o hash local e o hash no remoto;
  - os itens para o backlog.
- Se algo do contexto não bater com o repositório, pare e registre no relatório.
