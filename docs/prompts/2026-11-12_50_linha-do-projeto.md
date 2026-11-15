# Pedido 50 — A linha do projeto: uma linha dos algoritmos do TCC com o tempo da volta mais rápida da IA

**De:** Eduardo. **Data:** 12/11/2026.
**Tipo:** Modelo 1 (`backend/ml/optimization/`, scripts), a codificação da linha, a calibração do medidor, ferramentas em `tools/pista_teste/`, documentação e testes, com um teste no jogo comigo. O coach, o rádio, o app, o app do jogo, o store v2 e o Modelo 2 não mudam.

**Quando começar: agora, na pasta do pedido 47** (`C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47`), numa branch nova. A pasta principal fica com o pedido 45, e a do 48 na branch dela. **Nenhuma das duas troca de branch nem é tocada por este pedido,** salvo o item 0.2. Temos pouco tempo: siga as partes sem parar, salvo onde este pedido manda parar.

### Parte 0 — A pasta

1. **Confira a pasta do 47:** a branch `etapa/modelo1-por-trecho`, sem mudança sem commit, já juntada a `develop`. Confira também se o envio do pedido 49 já foi feito (`git ls-remote origin refs/heads/develop` igual ao `develop` local). Se não foi, siga sem enviar nada até eu enviar, e avise no relatório.
2. **O texto deste pedido** está sem commit na pasta principal. Copie-o para a pasta do 47 depois de criar a branch (item 3), faça dele o primeiro commit e, conferido o sha256, apague a cópia da pasta principal, e só ela.
3. **A branch nova, a partir de `develop`:**
   ```powershell
   git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47 switch -c etapa/linha-do-projeto develop
   ```
4. **Os imports e os dados,** como nos pedidos 47 e 49: o `.venv` da principal, os imports resolvidos para a pasta do 47 e as junções só para leitura. **Nada é escrito através de uma junção.** As gravações da cópia da pista ficam na pasta do app instalado e só são lidas. O que este pedido gera vai para `data\linha_do_projeto\` (fora dos commits) e para `data\pista_teste\linhas\` (os arquivos da linha da IA, fora dos commits). Tire a foto de `data\ml` da principal antes e compare no fim.
5. **O processador:** antes de cada conta pesada (a busca, a suíte), confira se o `acs.exe` está aberto. Se estiver, espere.

## Contexto

1. **A minha decisão de 12/11:** o TCC precisa da **sua própria linha**, gerada pelos algoritmos do projeto, e o app vai usar essa linha. A linha da IA do jogo (o `fast_lane.ai`) é o adversário a igualar, e não a saída. **A meta é a volta mais rápida da IA.** Os algoritmos reprovados (a LSTM geradora e a M1 v2) entram para tentar chegar a essa meta.
2. **Os tempos do teste no jogo do pedido 47** (a mesma IA dirigindo cada linha, na cópia da pista, com o preset "pedido 47 [teste]"):

   | linha | melhor | mediana | pior |
   |---|---:|---:|---:|
   | C0, a linha da IA | **1:25,353** | 1:25,438 | 1:25,583 |
   | C0 final | 1:25,438 | 1:25,667 | 1:25,724 |
   | C4, gerada com a LSTM | 1:25,787 | 1:25,920 | 1:26,129 |
   | C3, gerada sem a LSTM | 1:25,849 | 1:26,015 | 1:26,206 |
   | C2, a minha linha, codificada | 1:26,923 | 1:27,014 | 1:27,340 |
   | C1, a volta da IA `#0013`, codificada | 1:27,329 | 1:27,517 | 1:27,636 |

   A volta mais rápida da IA nas gravações é a `#0013` de 04/10, com 1:24,829, na pista original e com outro preset.
3. **Por que a linha gerada ainda não chegou** (pedidos 47 e 49):
   - **a codificação:** pontos de controle a cada 25 m. Até a volta da IA, codificada (C1), perdeu 2,1 s. 41% disso vem de um ponto com o raio fechado na subida dos boxes (85 a 90 m, contra 226 m na linha original), onde a IA freia;
   - **o medidor foi explorado pela busca:** ele errou a linha da IA por 0,12 s (85,316 s contra 85,438 s), mas previu a C3 3,1 s mais rápida do que ela foi no jogo. A busca foi para onde o medidor mais erra;
   - **por trecho, as linhas do projeto já chegam lá.** Escolhendo em cada trecho a mais rápida entre a C2, a C3 e a C4 (nenhuma delas vem do `fast_lane.ai`), a soma das diferenças é −0,46 s contra a linha da IA. É um teto: um trecho muda a entrada do seguinte, e a escolha foi feita depois de ver os tempos.
4. **As definições de 12/11:**
   - **os dados:** as voltas gravadas da IA podem servir como dado de treino e como semente da busca, como as minhas. O `fast_lane.ai` nunca é a saída, e o relatório mostra a distância da linha do projeto à linha da IA em cada trecho;
   - **a M1 v2 como medidor:** só um teste relatado, com uma linha de atualização no ADR 0028. O veredito dela não muda.
5. **A exceção da pista** é a mesma do pedido 47 (contexto, item 4 de lá), na mesma cópia (`vhe_interlagos_teste_m1`), só por scripts que eu rodo. **O `data.acd` nunca é aberto,** nem outro arquivo do carro. A pasta da pista original nunca é escrita.

## Parte A — Registrar antes de rodar (ADR 0031)

Escreva o **ADR 0031, "A linha do projeto"** (confira o número), e commite-o antes de qualquer busca, calibração ou arquivo de linha. Ele fixa:

1. **O que é a linha do projeto:** uma linha produzida pelos algoritmos do projeto (a busca genética, a LSTM geradora, a montagem por trecho de linhas do projeto), guardada no formato do projeto (a lateral na grade de 2 m da geometria oficial, com o `geometry_id` e o `corridor_id`). Ela pode usar voltas gravadas como dado e como semente, e nunca copia o `fast_lane.ai`.
2. **A meta e o veredito,** no teste no jogo da Parte D:
   - **meta atingida:** a melhor volta válida da linha do projeto é igual ou menor que a melhor volta válida do bloco da linha da IA logo antes dela **e** do bloco logo depois dela (mesmo número de voltas em cada bloco);
   - **só relatados:** a diferença das medianas contra o C0, com o IC de 95% (bootstrap, 10.000, semente 50), e a regra de não inferioridade do ADR 0029 (o limite superior até +0,10 s); a comparação com a `#0013` (1:24,829), lado a lado com as condições de 04/10 e do teste.
3. **O teste no jogo:** cinco blocos, `C0, L?, C0, L?, C0`. As duas linhas (L1 e L2) entram em ordem sorteada com a semente 50. Cada bloco tem 9 voltas: a de saída e a primeira lançada ficam fora, e as 7 seguintes contam. A volta válida segue o ADR 0029, item 4. **A deriva** é medida pelos três blocos de C0, e não decide o veredito, porque a meta compara cada linha com os dois blocos vizinhos.
4. **A codificação nova,** com o porquê:
   - os pontos de controle mais densos nas curvas e mais esparsos nas retas (por exemplo, 10 m nas janelas das curvas e 25 m fora delas);
   - uma curva com a curvatura contínua;
   - **um raio mínimo e uma taxa máxima de variação da curvatura, em cada trecho,** tirados das voltas gravadas (por exemplo, 90% do menor raio que as voltas válidas usam naquele trecho);
   - **a conferência:** a linha da IA (C0) e a volta `#0013`, passadas pela codificação nova, ficam a até 0,10 m da original em 95% dos pontos, e o menor raio de cada trecho fica a até 5% do original. Se não ficarem, pare e relate.
5. **O medidor:**
   - **os candidatos:** o simulador quase-estacionário com o envelope das voltas reais (o de hoje); o mesmo, calibrado com os tempos por microssetor das 6 linhas do pedido 47; e o envelope tirado da M1 v2 (o método do ADR 0028, item 10), sem novo ajuste;
   - **a calibração:** uma correção por trecho (ou por microssetor), ajustada com uma linha de fora de cada vez, e testada nela;
   - **a escolha:** o candidato com a maior correlação de Spearman entre o tempo previsto e o do jogo, por microssetor, nas linhas deixadas de fora. Esse é o medidor da busca. Os três são relatados.
6. **A região de confiança da busca:** a lateral da linha não se afasta mais que um limite (por exemplo, 1,0 m) da linha de partida (L1), porque fora das linhas do pedido 47 o medidor não foi conferido no jogo.
7. **As duas linhas a testar:**
   - **L1, a montagem por trecho:** em cada trecho do ADR 0030, a linha mais rápida no jogo entre a C2, a C3 e a C4 (a tabela B.1 do pedido 49), emendada nas retas, onde as linhas se encontram, e passada pela codificação nova;
   - **L2, a busca nova:** o algoritmo genético partindo da L1, com a codificação nova, o medidor escolhido no item 5, a região de confiança do item 6 e a LSTM geradora como semente (como no pedido 46). As outras regras da busca são as do ADR 0028, item 10.
8. **A velocidade e os pedais dos arquivos de L1 e L2:** a regra do pedido 47 (os do original na mesma estação), para os resultados ficarem comparáveis com os do 47 e do 49.
9. **O que se espera,** escrito antes, com o porquê.
10. **Nenhuma regra muda depois de ver os números.**

## Parte B — Construir (sem jogo)

1. **A codificação nova,** com a conferência da A.4.
2. **O medidor:** a calibração, a escolha e a tabela dos três candidatos (A.5).
3. **A L1 e a L2,** com, para cada uma:
   - o tempo previsto pelos três medidores;
   - a distância à linha da IA por trecho (a mediana e o máximo);
   - o corredor do pedido 44 (sem penalização), o menor raio e a maior variação da curvatura de cada trecho;
   - a figura das linhas sobre a pista, com a C06, a C09, a C10 e a subida dos boxes em destaque.
4. **Os arquivos para o jogo:** os `fast_lane.ai` da L1 e da L2, pelo escritor e pelas regras do pedido 47, em `data\pista_teste\linhas\`, com o sha256. **Eles ficam fora dos commits.**
5. **O `trocar_linha.ps1`** passa a aceitar `-Condicao L1` e `-Condicao L2`, com as mesmas travas (o jogo fechado, só a cópia, os caches do CSP da cópia apagados a cada troca, a linha no `registro.csv`). Os testes do 47 continuam passando.
6. **Commite as Partes A e B** e envie a branch antes da parada (se o envio do 49 já tiver sido feito).

## Parte C — Mais carros da IA na pista: o que dá para gravar (só leitura e relatório)

**Eu quero aumentar os dados para treinar os modelos** com vários carros da IA na pista ao mesmo tempo. **Este pedido não muda o gravador nem o app do jogo,** porque o código do app do jogo está mudando no pedido 45. Relate:

1. **o que cada carro da IA expõe** pela memória compartilhada, pela telemetria por UDP e pela API do CSP (`ac.getCar` e as rodas): a posição, a velocidade, o volante, o acelerador, o freio, a marcha, as cargas e o escorregamento, com a fonte de cada um (link) e o que não foi confirmado;
2. **o modo do jogo** que põe vários carros da IA no mesmo carro e na mesma pista, sem largada de corrida (por exemplo, o "Track Day" do Content Manager), e o que se sabe sobre a IA mudar a linha no tráfego;
3. **a regra para uma volta com tráfego** ficar fora (por exemplo, outro carro a menos de 2 s à frente);
4. **um plano para um pedido próprio, depois do merge do 45:** o que mudaria no gravador ou no app do jogo, quantos carros, quantas voltas e quanto disco.

## Parte D — Parada: o teste no jogo, comigo

Deixe no relatório:

1. **O roteiro:** os comandos (`trocar_linha.ps1` com `C0`, `L1` e `L2`), a ordem sorteada dos 5 blocos, as 9 voltas por bloco, quando fechar o jogo e trocar a linha, e o preset "pedido 47 [teste]" sem mudança. O app instalado grava, e eu não aperto "Atualizar coach".
2. **Duas sessões de até 45 minutos:** a primeira com `C0, L?, C0`, a segunda com `L?, C0`.
3. **A conferência da troca entre as sessões, sem tempos,** como no pedido 47.
4. **Ao terminar, eu aviso: "rodei a linha do projeto".**

## Parte E — Depois do meu aviso: o resultado

1. **A conferência:** as gravações, o `registro.csv`, a troca que pegou em cada bloco (a linha gravada mais perto da linha da condição do que da original) e o sha256 do `fast_lane.ai` original igual ao de antes.
2. **As voltas válidas e os tempos** de cada bloco, e **o veredito da A.2** para L1 e L2.
3. **Por trecho:** cada linha contra os blocos vizinhos de C0, pela regra do ADR 0030.
4. **Os medidores contra o jogo:** o que cada um previa para L1 e L2.
5. **A referência para o app:** se uma linha atingir a meta, ela vira a linha de referência de `data\modelo1_por_trecho\referencia_por_trecho.json` em todos os trechos, com a marca "linha do projeto, meta atingida em <data>", e a execução da IA nela, medida nos 7 blocos. Se as duas atingirem, vai a de melhor volta. Se nenhuma atingir, a referência não muda, e o relatório diz quanto faltou e onde.
6. **Testes,** em `tests/`, com dados sintéticos:
   - a codificação nova: a curvatura contínua, o raio mínimo, a taxa de variação e a conferência da A.4;
   - a calibração do medidor com uma linha de fora;
   - a região de confiança;
   - a montagem por trecho e as emendas;
   - o veredito da A.2 com os blocos vizinhos;
   - o `trocar_linha.ps1` com `L1` e `L2`, nas travas do 47.

   A suíte do backend continua passando (a falha de ambiente do `test_leitura` é relatada, não corrigida).

## Parte F — Documentação

- **ADR 0031,** com o registro e o resultado; uma linha no índice.
- **ADR 0028:** uma linha de atualização: "a M1 v2 testada como medidor no pedido 50, só relatado; o veredito não muda".
- **ADR 0009:** uma linha de atualização: "a linha do projeto vai para a referência do coach se atingir a meta do ADR 0031".
- **ADRs 0029 e 0030:** uma linha de atualização cada, apontando para o 0031.
- **`docs/arquitetura_ml.md`:** uma seção "A linha do projeto (pedido 50; ADR 0031)".
- **`docs/backlog.md`:** não edite; liste os itens no relatório.
- **A cópia da pista continua instalada** até eu rodar o `remover_copia.ps1`.

## Regras gerais

- **Nenhuma regra muda depois de ver os números.** O ADR 0031 é commitado antes de qualquer busca e de qualquer arquivo de linha.
- **Não invente resultados.** Um canal que falta é "não gravado"; o que uma fonte não confirma é "não confirmado".
- **Da pista, só a exceção do contexto, item 5.** Não toque na pasta do jogo: quem roda os scripts sou eu (ADR 0020).
- **As gravações só são lidas.** Não apague, não mova e não copie nenhuma, nem entre a pasta do app instalado e o repositório.
- **Não instale nem atualize pacotes.** Se algo pedir pacote novo, pare e relate.
- **Não contorne nenhuma trava:** se algo parar, pare também e registre o motivo.
- **Branch e commits:** `etapa/linha-do-projeto`, a partir de `develop`, na pasta do 47; o texto deste pedido é o primeiro commit; o ADR 0031 antes da busca; commits por parte.
- **O merge, depois da Parte F, na pasta do 47:**
  - se `develop` tiver andado (por exemplo, com o merge do 45), traga `develop` para a branch antes, resolvendo os conflitos simples (como as linhas do índice dos ADRs);
  - se `develop` estiver aberta em outra pasta, pare e me avise;
  - depois do merge e do envio, volte a pasta do 47 para a branch do pedido;
  - não apague a pasta: eu decido quando.
- **A pasta principal, a pasta do 48 e as branches de outros pedidos não são tocadas,** salvo o item 0.2.
- **Cópia no GitHub (vale para todo pedido):**
  - depois dos commits de cada parte e antes da parada, envie a branch do pedido ao `origin`; depois do merge, envie `develop`;
  - só envios que não reescrevem o remoto (branch nova ou avanço simples). Nunca `--force` nem `--force-with-lease`;
  - `main` e as tags não vão neste pedido;
  - antes do primeiro envio, confira que nada acima de 50 MB, nenhum segredo, nenhuma gravação (`recordings/`, `data/recordings`, `data/ml`), nenhum `.ai` e nada de `data/linha_do_projeto` entrou nos commits;
  - depois de cada envio, confira com `git ls-remote origin` que o hash remoto é o mesmo do local;
  - se o controle de permissões da sessão recusar o envio, deixe no relatório os comandos para eu rodar pelo terminal;
  - se pedir login, se o envio for recusado pelo GitHub ou se o remoto tiver divergido, pare e me avise. Nenhum token ou senha no chat, nos arquivos ou no relatório.
- **Janelas e pastas de teste** levam "[teste]" e são fechadas ou apagadas no fim.
- **Nomes técnicos** nos textos, sem apelidos. **Os tempos de volta** no formato M:SS,mmm.
- **Relatório** em `docs/handoff/2026-11-12_50_linha-do-projeto_relatorio.md`, na pasta do 47, com:
  - a Parte 0: a branch, os imports, os dados, o envio do 49 e o que foi apagado na principal;
  - o commit do ADR 0031;
  - a codificação nova e a conferência dela;
  - os três medidores e o escolhido;
  - a L1 e a L2 (Parte B), com a figura e os sha256;
  - o que dá para gravar com vários carros da IA (Parte C);
  - o roteiro (Parte D) e, depois do teste, o resultado (Parte E) e o veredito;
  - a saída dos testes e os commits;
  - o que foi enviado ao GitHub: a ref, o hash local e o hash no remoto;
  - os itens para o backlog.
- Se algo do contexto não bater com o repositório, pare e registre no relatório.
