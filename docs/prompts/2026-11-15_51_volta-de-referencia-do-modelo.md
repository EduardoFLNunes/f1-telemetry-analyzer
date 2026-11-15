# Pedido 51 — A volta de referência do app é a volta do nosso modelo

**De:** Eduardo. **Data:** 15/11/2026.
**Tipo:** coach, rádio, app do Windows, app do jogo, construtor da referência (`atualizar_coach`), documentação, testes e o instalador. O Modelo 1 (a busca, a codificação, o medidor), o Modelo 2 e o store v2 não mudam.

**Quando começar: agora, na pasta principal** (`C:\Users\Dokas\Desktop\f1-telemetry-analyzer`), numa branch nova a partir de `develop`. A pasta do 47 e a do 48 não são tocadas. O pedido 42 espera este terminar. Temos pouco tempo: siga as partes sem parar, salvo onde este pedido manda parar. **Este pedido não precisa de sessão minha no jogo:** tudo é conferido com as gravações que já existem.

### Parte 0 — A pasta

1. **Confira a pasta principal:** a branch `etapa/replay-e-radio-que-ensina`, sem mudança sem commit. Confira se o envio do pedido 50 já foi feito (`git ls-remote origin refs/heads/develop` igual ao `develop` local). Se não foi, siga e avise no relatório: o envio de `develop` deste pedido leva o 50 junto.
2. **A branch nova, a partir de `develop`** (que já tem o merge do 50, `b969a7df`):
   ```powershell
   git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer switch -c etapa/volta-do-modelo develop
   ```
3. **O texto deste pedido** está sem commit na pasta principal: faça dele o primeiro commit.
4. **O app aberto pelo repositório:** se estiver aberto, me peça para fechar antes de trocar de branch.
5. **O processador:** antes de cada conta pesada (a suíte, o instalador), confira se o `acs.exe` está aberto. Se estiver, espere.

## Contexto

1. **A minha decisão de 15/11: o app não usa a volta da IA do Assetto Corsa.** Por causa da licença e da liberdade de levar o app a outros simuladores, o app tem só duas referências:
   - **"Volta de referência":** a volta do nosso modelo (Modelo 1), a padrão;
   - **"Sua melhor volta":** como hoje.

   **A volta da IA só entra no app se o algoritmo genético chegar a ela:** aí ela é a saída do modelo e entra como volta do modelo, nunca como "volta da IA". A linha da IA continua só como régua de desenvolvimento, nos testes no jogo dos ADRs 0029 e 0031.
2. **A volta do modelo existe desde 15/11** (pedido 50, ADR 0031): a **L2**, gerada pelo algoritmo genético a partir da montagem por trecho, atingiu a meta. A melhor volta válida dela foi **1:24,552**, no bloco 4 do teste (gravação `2026-11-15_02-47-12`, na cópia `vhe_interlagos_teste_m1`, com o `fast_lane.ai` de sha256 `4e9f1250…`), contra 1:24,766 e 1:24,670 dos blocos vizinhos da linha da IA.
3. **O que o app usa hoje** (confira e relate se não bater):
   - o modelo de referência da pasta principal (`data\reference_models\vhe_interlagos.json`) está com `reference_kind` "volta_ia", na volta `#0013` de 04/10 (1:24,828);
   - o fantasma, a marca "freada da IA" nos mapas e o "atrás da IA" nas falas vêm dessa volta;
   - o app instalado (0.7.0) está com `"referenciaCoach": "minha_melhor"` desde 14/10;
   - a referência por trecho com a L2 está em `data\modelo1_por_trecho\referencia_por_trecho.json`, **na pasta do 47**, e o coach não lê esse arquivo (backlog do 50, item 1).
4. **A volta do modelo foi dirigida pela IA do jogo, na linha do projeto.** É o único motorista constante para medir uma linha. Por isso, dela valem a linha, os pontos de freada, as velocidades, as marchas e o tempo. O formato dos pedais é o comando do controlador da IA, não a técnica de um piloto: nenhum detector de técnica do Modelo 2 lê o formato do pedal dessa volta como técnica.
5. **A decisão do pedido 45 de 13/11:** "Melhor volta da sessão" vira "Melhor da sessão" no próximo pedido do app. É este.
6. **As gravações da cópia** ficam na pasta do app instalado, a mesma que o pedido 50 leu. Elas só são lidas.

## Parte A — Registrar antes (ADR 0032)

Escreva o **ADR 0032, "A referência do app é a volta do modelo"** (confira o número) e commite-o antes de mudar o código. Ele fixa:

1. **As referências do app:** "Volta de referência" (a volta do Modelo 1, a padrão) e "Sua melhor volta". A volta da IA do jogo nunca é referência do app, nem opção na tela.
2. **O que é a volta do modelo:** a melhor volta válida de uma linha do projeto que atingiu a meta do ADR 0031, dirigida no jogo, guardada como um arquivo derivado (Parte B) com a origem, os sha256 e a marca "linha do projeto, meta atingida em <data>". Quando uma linha nova atingir a meta com uma volta melhor, ela substitui a anterior, que fica guardada.
3. **Se o algoritmo genético chegar à linha da IA,** a saída continua sendo a volta do modelo, com a distância à linha da IA relatada (como no ADR 0031).
4. **Sem volta do modelo** para uma pista ou um carro: o app oferece só "Sua melhor volta", com a frase "A volta de referência desta pista ainda não foi gerada pelo modelo".
5. **O que vale da volta do modelo** (contexto, item 4): a linha, as freadas, as velocidades, as marchas e o tempo. O formato dos pedais só é desenhado, nunca julgado.
6. **A linha da IA** fica só nos testes de desenvolvimento (ADRs 0029 e 0031) e no campo `referencia_anterior` da referência por trecho.

## Parte B — A volta do modelo como arquivo do app

1. **O arquivo derivado:** leia (sem copiar) a gravação da melhor volta válida da L2 (a de 1:24,552) e gere a referência no formato que o fantasma e o coach já usam: os 2.167 pontos da grade de 2 m da geometria oficial, com a posição, o tempo, a velocidade, a marcha e os pedais, mais os alvos por microssetor do modelo de referência. **A gravação não é copiada:** o arquivo guarda só o que foi derivado dela, com o nome da sessão, o número da volta e o sha256 dos arquivos de origem.
2. **Os metadados:** `geometry_id`, `corridor_id`, a linha (L2) e o sha256 do `fast_lane.ai` dela, o carro, o preset do teste, a marca do ADR 0031, "executada pela IA do jogo na linha do projeto" e a pista a que vale (`vhe_interlagos`).
3. **A pista da gravação:** a volta foi gravada na cópia `vhe_interlagos_teste_m1`. Confira que a cópia e a original têm a mesma geometria (o mesmo `geometry_id` e o kn5 da pista com o mesmo sha256) antes de usar a volta na original. Se não tiverem, pare e relate.
4. **Onde o arquivo fica:** ele precisa estar no app do repositório e no app instalado (o instalador o leva). Proponha o caminho pelas convenções do projeto (os dados de `data\` ficam fora do git). Se a regra de dados fora do git impedir o instalador de levar o arquivo, pare e me pergunte antes de escolher.
5. **A conferência, sem jogo:**
   - o tempo da volta refeito na grade fica a até 5 ms de 1:24,552;
   - os tempos dos 15 trechos batem com os do `_resultado.json` do pedido 50 para essa volta;
   - a distância da volta à linha da L2 (mediana e p95) mostra que é a L2, e não a linha da IA;
   - o relatório mostra, lado a lado, os alvos por microssetor da volta do modelo e os da `#0013`.

## Parte C — O app só com as duas referências

1. **O construtor da referência** (`atualizar_coach` e o modelo de referência): o tipo novo "volta_do_modelo" lê o arquivo da Parte B, e a padrão passa a ser ele. O tipo "volta_ia" sai do app: não é escolhido, não é padrão e não aparece na rota. Se os scripts de desenvolvimento dos ADRs 0029 e 0031 precisarem dele, ele fica só neles.
2. **A tela Coleta de dados:** as opções são "Volta de referência" e "Sua melhor volta". A configuração antiga `"volta_ia"` vira `"volta_do_modelo"` ao abrir; `"minha_melhor"` continua como está.
3. **O coach e o rádio** comparam com a volta do modelo. **Os textos,** em todo lugar em que a referência é a volta do modelo:
   - na voz: "atrás da IA" vira "atrás da referência"; "freou 34 metros antes da IA" vira "antes da referência"; "da IA" vira "da referência". "Do seu recorde" e "da melhor da sessão" ficam;
   - "Melhor volta da sessão" vira "Melhor da sessão" (decisão do 45);
   - nos mapas do app do jogo: "freada da IA" vira "freada da referência"; o rótulo do fantasma "IA" vira "Referência";
   - nas telas do app do Windows (Ao vivo, Volta, Evolução, Sessões): os rótulos de "IA" que se referem à referência viram "Referência".
4. **O que não muda:** o detector de origem continua tirando as voltas da IA de "Sua melhor volta" e das estatísticas; o rádio continua calado nas voltas da IA; a volta do modelo não entra em "Sua melhor volta" nem na evolução do piloto.
5. **As versões:** o app do Windows passa a `0.8.0-volta-do-modelo` nos três pontos de sempre; o app do jogo passa a 0.6.0.

## Parte D — As conferências, sem jogo

1. **O rádio fora do tempo real** nas sessões de 13/10, 18/10, 21/10 e 12/11 (como nos pedidos 36 e 45): as falas antes e depois, quantas mensagens perderam a causa com "referência" no lugar de "IA" e quantas foram entregues. **Os limites de 7,3, 8,0 e 8,8 s não mudam.** Se alguma causa sair, relate quantas e onde; não mude a ordem do corte.
2. **O teste de unidades** (`test_todo_numero_falado_tem_a_unidade...`) e um teste novo que acusa "IA" em qualquer fala, cartão ou rótulo ligado à referência.
3. **As prévias em HTML** do minimapa e do mapa aproximado com o fantasma da volta do modelo, na saída dos boxes e na freada da C04, como no pedido 36.
4. **As capturas** das telas Coleta de dados, Ao vivo e Volta, em 1920 × 1080.
5. **A suíte do backend, os testes do front, o `tsc` e o `conferir_lua.py`.** A falha de ambiente conhecida é relatada, não corrigida.

## Parte E — O instalador

1. **Gere o instalador `0.8.0-volta-do-modelo`** (`npm run dist:win`, na pasta `desktop`), com a árvore limpa, e confira que ele leva o arquivo da volta do modelo e o `voz.ps1`.
2. **Instale só depois do meu "pode instalar" no chat,** sem perguntas (`/S`), com o jogo e o app fechados, por cima da 0.7.0. Confira depois a configuração: `"minha_melhor"` continua `"minha_melhor"`.
3. **O app do jogo 0.6.0** vai pelo `instalar.ps1`, que eu rodo. Deixe o comando no relatório.
4. **No jogo, numa próxima sessão minha** (não espera por ela): o fantasma com "Referência", a marca "freada da referência" e uma fala com "atrás da referência". Deixe no relatório o que olhar, em até 5 itens.

## Parte F — Documentação

- **ADR 0032,** com uma linha no índice.
- **ADR 0009:** uma linha de atualização: "a referência do coach é a volta do modelo (ADR 0032)".
- **ADRs 0021, 0027 e 0031:** uma linha de atualização cada, sobre os textos e a referência.
- **`docs/realidade_aumentada.md`** (as seções do rádio, dos mapas e das unidades), **`docs/app_para_producao.md`** (a versão 0.8.0) e **`docs/dashboard_inventario.md`**.
- **`docs/backlog.md`:** não edite; liste os itens no relatório.

## Regras gerais

- **Nenhuma regra muda depois de ver os números.** O ADR 0032 é commitado antes do código.
- **Não invente resultados.** O que uma fonte não confirma é "não confirmado".
- **Não toque na pasta do jogo nem na pasta da pista:** quem roda os scripts sou eu (ADR 0020). O `data.acd` nunca é aberto.
- **As gravações só são lidas.** Não apague, não mova e não copie nenhuma, nem entre a pasta do app instalado e o repositório. O arquivo da Parte B guarda só o que foi derivado.
- **Não instale nem atualize pacotes.** Se algo pedir pacote novo, pare e relate.
- **Não contorne nenhuma trava:** se algo parar, pare também e registre o motivo.
- **Branch e commits:** `etapa/volta-do-modelo`, a partir de `develop`, na pasta principal; o texto deste pedido é o primeiro commit; o ADR 0032 antes do código; commits por parte.
- **O merge, depois da Parte F e das conferências da Parte D,** na pasta principal: se `develop` estiver aberta em outra pasta, pare e me avise. Depois do merge, a pasta principal fica em `develop`, para o pedido 42 abrir a branch dele.
- **Cópia no GitHub (vale para todo pedido):**
  - depois dos commits de cada parte, envie a branch do pedido ao `origin`; depois do merge, envie `develop`;
  - só envios que não reescrevem o remoto (branch nova ou avanço simples). Nunca `--force` nem `--force-with-lease`;
  - `main` e as tags não vão neste pedido;
  - antes do primeiro envio, confira que nada acima de 50 MB, nenhum segredo, nenhuma gravação (`recordings/`, `data/recordings`, `data/ml`) e nenhum `.ai` entrou nos commits;
  - depois de cada envio, confira com `git ls-remote origin` que o hash remoto é o mesmo do local;
  - se o controle de permissões da sessão recusar o envio, deixe no relatório os comandos para eu rodar pelo terminal;
  - se pedir login, se o envio for recusado pelo GitHub ou se o remoto tiver divergido, pare e me avise. Nenhum token ou senha no chat, nos arquivos ou no relatório.
- **Janelas e pastas de teste** levam "[teste]" e são fechadas ou apagadas no fim.
- **Nomes técnicos** nos textos, sem apelidos. **Os tempos de volta** no formato M:SS,mmm.
- **Relatório** em `docs/handoff/2026-11-15_51_volta-de-referencia-do-modelo_relatorio.md`, com:
  - a Parte 0: a branch e o estado do envio do 50;
  - o commit do ADR 0032;
  - o arquivo da volta do modelo, onde ficou, e a conferência da Parte B;
  - o que mudou no app (as telas, os textos, as versões);
  - as conferências da Parte D, com as falas antes e depois;
  - o instalador e o que olhar no jogo;
  - a saída dos testes e os commits;
  - o que foi enviado ao GitHub: a ref, o hash local e o hash no remoto;
  - os itens para o backlog.
- Se algo do contexto não bater com o repositório, pare e registre no relatório.
