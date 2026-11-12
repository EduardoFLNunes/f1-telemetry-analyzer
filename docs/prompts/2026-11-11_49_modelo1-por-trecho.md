# Pedido 49 — O Modelo 1 por trecho: onde a linha gerada ganha e perde, e a referência de cada trecho (sem jogo)

**De:** Eduardo. **Data:** 11/11/2026.
**Tipo:** análise das gravações do pedido 47, uma referência por trecho salva num arquivo, documentação e testes. **Sem jogo, sem busca nova e sem modelo novo.** O coach, o rádio, o app, o app do jogo, o store v2, a M1 e o Modelo 2 não mudam.

**Quando começar: agora, na pasta do pedido 47** (`C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47`), numa branch nova. A pasta principal fica na branch do pedido 45, e a do 48 na branch dele. **Nenhuma das duas troca de branch nem é tocada por este pedido,** salvo o item 0.2.

### Parte 0 — A pasta

1. **Confira a pasta do 47:** a branch `etapa/linha-gerada-no-jogo`, sem mudança sem commit, e já juntada a `develop`. Se houver mudança sem commit, pare e me avise.
2. **O texto deste pedido** está sem commit na pasta principal. Copie-o para a pasta do 47 depois de criar a branch (item 3), faça dele o primeiro commit e, conferido o sha256, apague a cópia da pasta principal, e só ela.
3. **A branch nova, a partir de `develop` atual** (com os pedidos 47 e 48), sem abrir `develop` na pasta:
   ```powershell
   git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47 switch -c etapa/modelo1-por-trecho develop
   ```
   Se `develop` estiver aberta em outra pasta ou o comando recusar, pare e me avise.
4. **Os imports e os dados,** como no pedido 47: o `.venv` da principal com os imports resolvidos para a pasta do 47, e as junções só para leitura (`data\recordings`, `data\ml`, `data\cache`). **Nada é escrito através de uma junção.** As gravações da cópia da pista ficam na pasta do app instalado e só são lidas. O que este pedido gera vai para `data\modelo1_por_trecho\`, uma pasta de verdade, fora dos commits (confira o `.gitignore`). Tire a foto de `data\ml` da principal antes e compare no fim.
5. **A cópia da pista continua instalada,** e nenhum script de `tools\pista_teste\` é rodado. A pasta do jogo não é tocada.
6. **O processador:** antes de cada conta pesada, confira se o `acs.exe` está aberto. Se estiver, espere.

## Contexto

1. **O resultado do pedido 47** (ADR 0029; `_resultado.json`), com a IA do jogo dirigindo cada linha, 7 voltas que contam por condição (4 no C0 final):

   | condição | o que é | mediana | contra o C0 |
   |---|---|---:|---:|
   | C0 | a linha da IA (o `fast_lane.ai` original) | 1:25,438 | — |
   | C4 | a linha gerada com a LSTM | 1:25,920 | +0,482 s |
   | C3 | a linha gerada sem a LSTM | 1:26,015 | +0,576 s |
   | C2 | a minha melhor volta, codificada como a busca codifica | 1:27,014 | +1,575 s |
   | C1 | a volta da IA `#0013`, codificada do mesmo jeito | 1:27,517 | +2,078 s |
   | C0 final | a linha da IA de novo, no fim do dia | 1:25,667 | +0,229 s (a deriva) |

   - o veredito de C3 e C4 é "não conclusivo (deriva)"; sem a deriva, seria "mais lenta";
   - com a mesma codificação, as linhas geradas ganham 1,5 a 1,6 s da C1 e 1,0 a 1,1 s da minha linha (C2);
   - o simulador do Modelo 1 não previu o jogo por microssetor (correlação de 0,09 a 0,17).
2. **O que o Cowork achou, somando os microssetores do `_resultado.json`** em 13 trechos pela curvatura da geometria oficial (aproximado; este pedido usa as janelas oficiais das curvas):
   - as duas linhas geradas ganham na saída da C06 (−0,32 s na C3 e −0,24 s na C4), onde o simulador também previa ganho, e na C08 (−0,05 e −0,09 s);
   - elas perdem no S do Senna (até +0,39 s na C4), na C03 (+0,15 a +0,16 s), na C07 (+0,16 s na C3) e na C10 (+0,14 a +0,17 s). Na C10, o simulador previa −1,2 s;
   - o `_resultado.json` só tem a conta por microssetor da C3 e da C4. A C1, a C2 e o C0 final não têm.
3. **As minhas decisões de 11/11** (desenho "Modelo 1 no aprendizado do piloto", decisões 1 e 2):
   - **o Modelo 1 entrega ao coach uma referência por trecho:** em cada trecho, a linha que ganhou no jogo com o mesmo piloto. Uma linha gerada só vira referência num trecho depois de vencer num teste novo no jogo; até lá, ela é "candidata";
   - **a próxima rodada é só a conta por trecho,** com os dados do 47. A busca por trecho e um teste novo no jogo ficam como trabalho futuro.
4. **O que o Modelo 1 decide:** só a linha. No teste do 47, o ponto de frenagem, a marcha e os pedais foram da IA. Para as linhas novas, a velocidade e os pedais gravados no arquivo foram copiados da linha original na mesma estação (pedido 47, A.4).
5. **Duas hipóteses para os 2,1 s da codificação** (C1 contra C0), a medir aqui:
   - **as dicas da linha:** a velocidade e os pedais copiados não acompanham a linha nova, e a IA freia ou acelera fora do lugar;
   - **a curvatura:** o raio de cada ponto foi recalculado da linha codificada, e uma curvatura serrilhada faz a IA tirar velocidade.
6. **As propostas do desenho para as decisões 3 e 5,** que eu ainda não confirmei. Elas entram aqui como provisórias, e o coach não as usa sem a minha confirmação:
   - **a tradução da frenagem:** o ponto de frenagem da IA, antecipado pela distância que o carro anda enquanto o meu freio sobe (a minha rampa, medida nas minhas voltas);
   - **a perda "de linha":** a minha posição lateral longe da linha de referência mais do que a minha própria repetibilidade.

## Parte A — Registrar antes de calcular (ADR 0030)

Escreva o **ADR 0030, "O Modelo 1 por trecho"** (confira o número: o 0027 pode estar na branch do 45; use o próximo livre). Commite-o antes de qualquer conta nas gravações. Ele fixa:

1. **Os trechos:** um por curva oficial (C01 a C14, as janelas da geometria do store v2 que o coach usa), do fim da curva anterior ao fim da curva, mais o trecho do fim da C14 até a linha de chegada. **Eles cobrem a volta inteira, sem buraco e sem sobreposição.** O tempo de cada trecho sai do cronômetro de cada volta, pela distância na geometria oficial. Em cada volta, a soma dos trechos bate com o tempo da volta em até 5 ms.
2. **As voltas:** as que contam no pedido 47, sem mudar a atribuição nem a validade.
3. **A regra do ganho por trecho,** para cada condição contra o C0:
   - a diferença das medianas das voltas no trecho, com IC de 95% por bootstrap (10.000 reamostragens, semente 49) e o p-valor por permutação;
   - a correção de Holm a 5% entre os trechos de cada comparação;
   - **ganho:** diferença negativa e significativa depois de Holm, **contra o C0 e contra o C0 final**; **perda:** o mesmo com diferença positiva; **empate:** o resto.
4. **A linha "candidata"** num trecho: a C3 ou a C4 com ganho pela regra. Nenhuma vira referência neste pedido.
5. **As medidas da execução da IA,** por trecho e por volta, com as definições:
   - o início da frenagem (freio ≥ 0,10), o freio máximo e a distância até o ápice;
   - a velocidade mínima e onde ela acontece;
   - a marcha mínima e o ponto de cada troca de marcha;
   - a retomada (acelerador ≥ 0,90 até o fim do trecho).
6. **As hipóteses dos 2,1 s** (contexto, item 5), só relatadas, com o que se espera escrito antes:
   - as dicas da linha: em cada trecho, o início da frenagem e a mínima da IA na C1 contra o C0, ao lado do que os campos copiados dizem;
   - a curvatura: uma medida de rugosidade da curvatura de cada linha (definida aqui, por exemplo a raiz da média do quadrado da segunda diferença da curvatura numa janela de 20 m) e a correlação de Spearman, entre os 60 microssetores, da perda da C1 com a diferença de rugosidade e com o afastamento lateral da linha original.
7. **As regras provisórias** (contexto, item 6):
   - **a minha rampa de freio:** em cada trecho, a distância percorrida entre o freio passar de 0,10 e chegar a 90% do máximo daquela frenagem, a mediana das minhas voltas;
   - **o limite "de linha":** o percentil 90 da distância das minhas voltas à mediana delas, na entrada, no ápice e na saída de cada trecho (a minha repetibilidade).
8. **O que se espera,** escrito antes, com o porquê.
9. **Nenhuma regra muda depois de ver os números.**

## Parte B — A conta por trecho

1. **O tempo por trecho das 6 condições:** a mediana, a dispersão e a regra da A.3, contra o C0 e contra o C0 final. Uma tabela e uma figura (cada trecho contra o C0, com o intervalo, na ordem da pista).
2. **A deriva por trecho:** o C0 final contra o C0, para ver onde os 0,23 s apareceram.
3. **A minha linha:**
   - a C2 (a IA na minha linha) por trecho, contra o C0 e contra a C3 e a C4;
   - **as minhas voltas reais** (as `humano` do pedido 44, `data/ml/retreino_lstm/voltas.parquet`, e as de 24/10), por trecho: a mediana, a melhor e a diferença para o C0;
   - **a minha diferença em cada trecho, dividida em linha e execução:** a distância lateral à linha do C0 na entrada, no ápice e na saída, e as medidas da A.5 (frenagem, mínima, marcha, retomada) contra as da IA. Quanto de cada trecho fica acima do limite "de linha" da A.7.
4. **A execução da IA** (A.5) por trecho e por condição, com destaque na C06 (a marcha e a retomada) e na C10.
5. **As hipóteses dos 2,1 s** (A.6), só relatadas.
6. **A conta de quanto a referência por trecho daria,** só relatada e marcada como teto: a linha mais rápida de cada trecho entre as que contam, juntas. O ganho de um trecho muda a entrada do seguinte, e escolher depois de ver favorece o acaso.

## Parte C — A referência por trecho

Um script (`ml/scripts/referencia_por_trecho.py`) gera `data/modelo1_por_trecho/referencia_por_trecho.json`, fora dos commits, porque deriva do arquivo da pista. Por trecho:

- os limites (a distância na geometria oficial);
- **a linha de referência: a linha da IA (C0)** em todos os trechos, como a lateral na grade de 2 m;
- **a execução da IA nessa linha** (A.5, a mediana e a dispersão das 7 voltas do C0);
- **a candidata,** quando houver (B.1): qual linha, a lateral e o ganho medido, com a marca "a validar no jogo";
- **as propostas provisórias** (A.7): o ponto de frenagem traduzido pela minha rampa e o limite "de linha", com a marca "provisório, sem confirmação";
- o `geometry_id`, o `corridor_id`, o commit e o sha256 das gravações usadas.

Um resumo legível vai para `docs/handoff/2026-11-11_49_modelo1-por-trecho_referencia.json`, sem a lateral ponto a ponto. **O coach não lê esse arquivo neste pedido.**

## Parte D — Testes

Em `tests/`, com dados sintéticos:

- os trechos cobrem a volta, sem buraco e sem sobreposição, e a soma bate com o tempo da volta;
- a regra da A.3 (o bootstrap, a permutação e a correção de Holm) num caso conhecido;
- as medidas da A.5 em traços sintéticos (frenagem, mínima, troca de marcha, retomada);
- a rampa e o limite da A.7;
- a rugosidade da curvatura: zero numa curva de raio constante e maior numa curva serrilhada;
- o formato do JSON da Parte C.

A suíte do backend continua passando (a falha conhecida do `test_leitura` na pasta separada é relatada, não corrigida).

## Parte E — Documentação

- **ADR 0030,** com o registro e o resultado; uma linha no índice.
- **`docs/arquitetura_ml.md`:** uma seção "O Modelo 1 por trecho (pedido 49; ADR 0030)", depois da do teste no jogo.
- **ADR 0029:** uma linha de atualização apontando para o 0030.
- **ADR 0009:** não muda; a linha gerada não vai para o coach.
- **`docs/backlog.md`:** não edite; liste os itens no relatório.

## Regras gerais

- **Só análise e o arquivo da referência.** Nenhuma busca, nenhum modelo novo, nenhuma linha nova para o jogo.
- **Nenhuma regra muda depois de ver os números.** A Parte A é commitada antes das contas.
- **Não invente resultados.** Um canal que falta é "não gravado"; uma medida sem dados é "sem dados".
- **Da pista, nada.** Nenhum arquivo da pista nem do jogo é aberto ou escrito; o `fast_lane.ai` original e as linhas do 47 em `data\pista_teste\linhas\` só são lidos. O `data.acd` nunca é aberto, nem outro arquivo do carro.
- **As gravações só são lidas.** Não apague, não mova e não copie nenhuma, nem entre a pasta do app instalado e o repositório.
- **Não instale nem atualize pacotes.** Se algo pedir pacote novo, pare e relate.
- **Não contorne nenhuma trava:** se algo parar, pare também e registre o motivo.
- **Branch e commits:** `etapa/modelo1-por-trecho`, a partir de `develop`, na pasta do 47; o texto deste pedido é o primeiro commit; a Parte A antes das contas; commits por parte.
- **O merge, depois da Parte E, na pasta do 47:**
  - se `develop` tiver andado (por exemplo, com o merge do 45), traga `develop` para a branch antes, resolvendo os conflitos simples;
  - se `develop` estiver aberta em outra pasta, pare e me avise;
  - depois do merge e do envio, volte a pasta do 47 para a branch do pedido;
  - não apague a pasta: eu decido quando.
- **A pasta principal, a pasta do 48 e as branches de outros pedidos não são tocadas,** salvo o item 0.2.
- **Cópia no GitHub (vale para todo pedido):**
  - depois dos commits de cada parte, envie a branch do pedido ao `origin`; depois do merge, envie `develop`;
  - só envios que não reescrevem o remoto (branch nova ou avanço simples). Nunca `--force` nem `--force-with-lease`;
  - `main` e as tags não vão neste pedido;
  - antes do primeiro envio, confira que nada acima de 50 MB, nenhum segredo, nenhuma gravação (`recordings/`, `data/recordings`, `data/ml`), nenhum `.ai` e nada de `data/modelo1_por_trecho` entrou nos commits;
  - depois de cada envio, confira com `git ls-remote origin` que o hash remoto é o mesmo do local;
  - se o controle de permissões da sessão recusar o envio, deixe no relatório os comandos para eu rodar pelo terminal;
  - se pedir login, se o envio for recusado pelo GitHub ou se o remoto tiver divergido, pare e me avise. Nenhum token ou senha no chat, nos arquivos ou no relatório.
- **Nomes técnicos** nos textos, sem apelidos. **Os tempos de volta** no formato M:SS,mmm.
- **Relatório** em `docs/handoff/2026-11-11_49_modelo1-por-trecho_relatorio.md`, na pasta do 47, com:
  - a Parte 0: a branch, os imports, os dados, o que foi apagado na principal e a comparação da foto de `data\ml`;
  - o commit do ADR 0030;
  - a conta por trecho (Parte B), com a tabela, a figura e as candidatas;
  - a minha diferença por trecho, em linha e execução;
  - as hipóteses dos 2,1 s;
  - o arquivo da referência (Parte C);
  - a saída dos testes e os commits;
  - o que foi enviado ao GitHub: a ref, o hash local e o hash no remoto;
  - os itens para o backlog.
- Se algo do contexto não bater com o repositório, pare e registre no relatório.
