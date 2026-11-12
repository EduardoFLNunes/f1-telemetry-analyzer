# 0031 — A linha do projeto

- **Status:** aceita (pedido 50). Registrada antes de qualquer busca, calibração ou arquivo de linha; o resultado entra no fim, sem mudar o registro
- **Data:** 2026-11-12
- **Decisor:** Eduardo
- **Refina:** 0029 (o teste no jogo como medidor) e 0030 (o Modelo 1 por trecho). **Mantém:** 0009 até o resultado (a referência do coach só muda pela regra do item 11), o corredor do 0025 e a geometria do 0002. **Usa:** a busca do 0028, item 10

## Contexto

1. **A decisão do Eduardo de 12/11:** o TCC precisa da sua própria linha, gerada pelos algoritmos do projeto, e o app vai usar essa linha. A linha da IA do jogo (o `fast_lane.ai`) é o adversário a igualar, e não a saída. **A meta é a volta mais rápida da IA.** Os algoritmos reprovados (a LSTM geradora e a M1 v2) entram para tentar chegar lá.
2. **O teste no jogo do pedido 47** (a mesma IA em cada linha, na cópia da pista, com o preset "pedido 47 [teste]"): melhor volta do C0 1:25,353 (mediana 1:25,438); C4 1:25,787; C3 1:25,849; C2 1:26,923; C1 1:27,329. A volta mais rápida da IA nas gravações é a `#0013` de 04/10, com 1:24,829, na pista original e com outro preset.
3. **Por que a linha gerada ainda não chegou** (pedidos 47 e 49):
   - **a codificação:** pontos de controle a cada 25 m. Até a volta da IA, codificada (C1), perdeu 2,1 s; 41% disso vem de um ponto de raio 85 a 90 m na subida dos boxes, onde a IA freia;
   - **o medidor foi explorado pela busca:** ele errou a linha da IA por 0,12 s, mas previu a C3 3,1 s mais rápida do que ela foi no jogo;
   - **por trecho, as linhas do projeto já chegam lá:** escolhendo em cada trecho a mais rápida entre C2, C3 e C4, a soma das diferenças é −0,46 s contra a linha da IA. É um teto.
4. **Medido antes deste registro (pedido 50, só a geometria, sem nenhuma linha nova):**
   - **a grade de 2 m sozinha estraga o raio do arquivo.** A linha da IA (C0), projetada na grade e escrita de volta pelo escritor do pedido 47 (`linha_nova.montar`, com interpolação linear entre os pontos da grade), cai de 37,7 m para 19,9 m de menor raio na C01, e de 226,5 m para 190,4 m no trecho C14→linha. O raio do arquivo é o do círculo por três pontos vizinhos (1,57 m entre eles), e cada quina da interpolação linear vira um raio fechado. **É a mesma causa provável do raio de 85 a 90 m da C1 e da C2;**
   - **a linha central do projeto ondula na subida dos boxes:** a curvatura dela vai de −0,011 a +0,013 1/m entre 3.860 e 3.940 m. Uma lateral suave em relação a ela leva essa ondulação para a linha no mundo;
   - **a volta `#0013` não fecha na linha de chegada:** o raio estimado perto de s = 0 cai para 3 a 15 m, um artefato da emenda entre o fim e o começo da volta, e não da linha.

## Decisão

### 1. O que é a linha do projeto

- **Uma linha produzida pelos algoritmos do projeto:** a busca genética, a LSTM geradora e a montagem por trecho de linhas do projeto.
- **Guardada no formato do projeto:** a lateral na grade de 2 m da geometria oficial, com o `geometry_id` (`0ed16f0dd2225990`) e o `corridor_id` (`707d07029036abd6`), mais os genes da codificação do item 4.
- **Ela pode usar voltas gravadas como dado e como semente,** da IA e do Eduardo. **Ela nunca copia o `fast_lane.ai`:** a linha da IA (C0) entra só como adversária, como medida de distância (B.3) e na conferência da codificação (item 4.5), e nunca como semente, base de coordenadas ou parte da linha.
- **O relatório mostra a distância da linha do projeto à linha da IA** em cada trecho do ADR 0030: a mediana e o máximo de |lateral da linha − lateral do C0| nos pontos da grade do trecho.

### 2. A meta e o veredito (Parte E)

**Meta atingida,** para cada linha L (L1 e L2): a melhor volta válida de L é **igual ou menor** que a melhor volta válida do bloco de C0 logo antes dela **e** que a do bloco de C0 logo depois dela.
- As voltas válidas são as do item 3, entre as 7 que contam em cada bloco. Os três blocos de cada comparação têm o mesmo número de voltas (9, com 7 que contam).
- **Se algum dos três blocos tiver menos de 5 voltas válidas** (o mínimo do ADR 0029, item 7), o veredito da linha é "não conclusivo (voltas válidas insuficientes)", com o motivo.
- **Se a troca não pegou no bloco da linha** (item 3), a linha fica fora do veredito.
- O tempo é o do cronômetro do jogo na grade (`lap_time_from_grid`), como no 47, em M:SS,mmm.

**Só relatados, fora do veredito:**
- **a diferença das medianas** de L contra os dois blocos vizinhos de C0, juntos (14 voltas que contam), com o IC de 95% por bootstrap: 10.000 reamostragens, cada grupo sorteado com reposição, um gerador novo por comparação, `numpy.random.default_rng(50)`;
- **a regra de não inferioridade do ADR 0029** (item 7) nessa diferença: o limite superior até +0,10 s;
- **a comparação com a `#0013`** (1:24,829), numa tabela lado a lado com as condições de 04/10 (a pista original, o preset daquele dia) e do teste (a cópia, o preset "pedido 47 [teste]").

### 3. O teste no jogo

- **Cinco blocos:** `C0, L?, C0, L?, C0`.
- **A ordem de L1 e L2, sorteada com a semente 50:** `numpy.random.default_rng(50).permutation(["L1", "L2"])`, com o numpy 1.26.3, dá **L1, L2**. A ordem completa é **C0, L1, C0, L2, C0**.
- **Cada bloco tem 9 voltas:** a de saída dos boxes e a primeira lançada ficam fora, e as 7 seguintes contam (ADR 0029, item 4). Voltas além dessas são ignoradas.
- **A volta válida** segue o ADR 0029, item 5 (o pedido cita o item 4, que é o das voltas; a regra da volta válida é a do item 5): completa (cobertura ≥ 95%), dentro do corredor (até 1,0 m, sem `offTrack`), sem rodada, sem entrada nos boxes e com a IA dirigindo a volta inteira.
- **Cada bloco é uma sessão do jogo.** O jogo é fechado antes de cada troca, e o `trocar_linha.ps1` registra a troca no `registro.csv`.
- **Os blocos do pedido 50** são as trocas do `registro.csv` com hora depois do commit deste ADR, na ordem da hora. Uma gravação pertence ao bloco da última troca antes do início dela (como no ADR 0029, item 6), e o sha256 da troca tem de ser o da condição.
- **A troca pegou num bloco** quando a mediana da distância das posições gravadas (das voltas que contam) até a linha da condição é menor que até a linha original (ADR 0029, item 9). Nos blocos de C0, a linha da condição é a própria original.
- **A deriva** é medida pelos três blocos de C0 (a diferença das medianas do segundo e do terceiro contra o primeiro, com o IC do item 2) e **não decide o veredito**, porque a meta compara cada linha com os dois blocos vizinhos.
- **O preset** é o "pedido 47 [teste]", sem mudança. O app instalado grava, e ninguém aperta "Atualizar coach" nem roda o `atualizar_coach` com as gravações da cópia.

### 4. A codificação nova

**4.1. Os pontos de controle,** mais densos nas curvas:
- **a janela de cada curva:** das 14 curvas de `ml.track.corners.detect_corners` (as mesmas do ADR 0030), de 40 m antes do início até 40 m depois do fim. Janelas que se tocam viram uma só;
- **o espaçamento:** dentro das janelas, o primeiro par da escada do item 4.6 (10 m na primeira tentativa); fora delas, o segundo (25 m). Cada intervalo (janela ou trecho entre janelas) é dividido em partes iguais, com o número de partes arredondado para cima;
- **o gene** é a lateral da linha no ponto de controle.

**4.2. A curva, com a curvatura contínua:**
- cada gene vira um ponto no plano X/Z: `P_j = c(s_j) + n(s_j) · g_j`, com a linha central `c` e a normal `n` da geometria;
- **a linha é uma spline cúbica periódica no plano X/Z,** com o parâmetro `u = s` e os nós nos pontos de controle. Ela tem a segunda derivada contínua, então a curvatura é contínua;
- **por quê:** a codificação do pedido 46 era uma spline na lateral. A lateral suave, somada a uma linha central que ondula (Contexto, item 4), dá uma linha que ondula no mundo. E a interpolação linear do escritor do 47 criava quinas a cada 2 m. Uma spline no próprio plano X/Z não herda nenhuma das duas;
- **a lateral na grade** (o formato do projeto, item 1) é a projeção da curva em cada ponto da grade: `L_i = (Q(s_i) − c(s_i)) · n(s_i)`;
- **o arquivo do jogo** é a curva avaliada direto na estação de cada ponto do arquivo original (`linha_nova.estacoes`), sem passar pela grade. O resto do arquivo segue o escritor do pedido 47 (`montar_por_posicoes`): a altura, a normal, as laterais, a grade de vizinhos e os campos de geometria pelas fórmulas conferidas.

**4.3. O ajuste (codificar uma linha):** mínimos quadrados dos genes contra os pontos da linha no plano X/Z, sem regularização. A curva é linear nos genes, então o ajuste é um `lstsq`. Os alvos são:
- para a linha da IA (C0), só na conferência: os 2.680 pontos do próprio arquivo, na estação de cada um;
- para as outras linhas (as voltas gravadas, a C2, a C3, a C4, a LSTM e a montagem da L1): os pontos da grade, `c(s_i) + n(s_i) · L_i`.

Os genes ficam nos limites do corredor do pedido 44, como na codificação do 46 (o limite mais apertado da vizinhança de cada gene).

**4.4. As restrições, por trecho do ADR 0030:**
- **a curvatura de uma linha na grade** é a do projeto: `ml.track.trajectory.curvature`, com a janela de 12 m (`CURVATURE_SMOOTHING_M`). A **taxa de variação** é `|dκ/ds|`, pela derivada da mesma janela (`_closed_derivative`, ordem 3, como em `fitness.shape_metrics`);
- **as voltas de onde saem os limites:** as 150 voltas rotuladas do pedido 44 (`humano` e `ia`) com a lateral completa na grade;
- **a emenda da volta fica fora:** os pontos a menos de 30 m da linha de chegada (s < 30 m ou s > comprimento − 30 m) não entram nos limites nem na conferência da `#0013`;
- **o raio mínimo do trecho:** 90% do menor raio que as voltas usam no trecho (o menor, entre as voltas, do menor raio de cada volta no trecho);
- **a taxa máxima do trecho:** 110% da maior taxa que as voltas usam no trecho (a maior, entre as voltas, da maior taxa de cada volta no trecho);
- **onde valem:** na L1 (conferido; se a L1 passar de um limite, a conta para e é relatada) e na busca da L2 (penalização do item 7).

**4.5. A conferência, antes de qualquer linha nova:**
- **a linha da IA (C0):** codificada pelos pontos do arquivo e avaliada nas mesmas estações:
  - a distância de cada ponto codificado até a polilinha do arquivo original fica **em até 0,10 m em 95% dos 2.680 pontos;**
  - **o menor raio de cada trecho** (o raio de três pontos do arquivo, a fórmula de `linha_nova.geometria`, sobre os pontos codificados) fica **a até 5% do menor raio do arquivo original** no mesmo trecho (o campo `raio`), nos 15 trechos;
- **a volta `#0013`:** codificada pela lateral na grade:
  - |lateral codificada − lateral gravada| fica **em até 0,10 m em 95% dos pontos da grade,** fora da emenda;
  - **o menor raio de cada trecho,** pela curvatura do item 4.4 (12 m), fora da emenda, fica **a até 5% do da volta gravada,** nos 15 trechos.

**4.6. A escada do espaçamento, registrada antes:** (dentro das janelas / fora delas) **10/25 m, 8/20 m, 6/15 m e 5/12,5 m,** nesta ordem. Vale o primeiro par em que a conferência do item 4.5 passa para as duas linhas. **Se nenhum passar, a conta para e é relatada.** Por quê: o pedido dá 10/25 m como exemplo, e a curva mais curta de Interlagos tem uns 44 m de arco. Um espaçamento mais fino segue melhor um pico de curvatura, ao custo de mais genes na busca.

**4.7. O corredor na L1:** se a L1 codificada sair do corredor do pedido 44 em algum ponto da grade, os genes cuja vizinhança cobre esses pontos são trazidos para dentro pelo tamanho da saída, e o ajuste se repete, até 20 vezes. Se ainda sair, a conta para e é relatada.

### 5. O medidor

**5.1. Os três candidatos:**
- **M-real:** o simulador quase-estacionário (`ml/optimization/lap_time_model.py`) com o envelope das voltas reais (`data/ml/vehicle_envelope.json`), o de hoje;
- **M-cal:** o M-real com uma correção por trecho (item 5.2);
- **M-v2:** o simulador com o envelope tirado da M1 v2 pelo método do ADR 0028, item 10 (a mediana dos parâmetros das 5 rodadas, `modelo1_final.medidor("m1v2")`), sem novo ajuste.

**5.2. A calibração do M-cal:**
- **os dados:** as linhas do pedido 47 na lateral que o 47 usou (`condicoes.linhas`) e os tempos do jogo das voltas que contam e são válidas. As 6 linhas da tabela do 47 são 5 traçados: o C0 e o C0 final são o mesmo arquivo. **O C0 do primeiro bloco é a base** (7 voltas), e o C0 final só é relatado, porque o medidor prevê para ele a mesma coisa que para o C0;
- **a diferença no jogo** de uma linha X num trecho k: `ΔJ_k(X) = mediana_k(X) − mediana_k(C0)`, com os tempos por trecho do pedido 49 (`_conta.json`);
- **a diferença no medidor:** `ΔS_k(X) = S_k(X) − S_k(C0)`, a soma dos tempos por passo do M-real nos pontos da grade do trecho;
- **a correção é uma escala por trecho, pela origem:** `β_k = Σ_X ΔJ_k(X)·ΔS_k(X) / Σ_X ΔS_k(X)²`, limitada a `[0, 2]`. Com `Σ ΔS² < 10⁻⁹`, `β_k = 1`. Por quê pela origem: o C0 contra ele mesmo vale 0 nos dois. Por quê o limite: com 3 linhas por ajuste, uma escala negativa inverteria a física com pouco dado. Com 0, o medidor deixa de usar aquele trecho para ordenar;
- **o tempo previsto pelo M-cal:** `T(X) = J(C0) + Σ_k β_k · ΔS_k(X)`, com `J(C0)` a mediana do C0 no jogo. Por passo, cada passo da grade pesa o `β` do seu trecho;
- **com uma linha de fora de cada vez:** para cada X em C1, C2, C3 e C4, os `β` são ajustados com as outras três e testados em X. **O M-cal da busca** usa os `β` ajustados com as quatro.

**5.3. A escolha:** a correlação de Spearman (`scipy.stats.spearmanr`) entre a diferença prevista e a do jogo, contra o C0, **por microssetor** (os 60 de `build_microsectors`), nas linhas deixadas de fora: os 4 × 60 pares juntos.
- **A diferença do jogo por microssetor:** a mediana dos tempos da linha no microssetor menos a do C0. Os tempos por microssetor saem das gravações da cópia, refeitas pelo caminho do 49 (`carregar_voltas_do_teste`) e cortadas por `etapas.tempos_por_microssetor`.
- **A diferença prevista:** a soma, nos passos do microssetor, do tempo por passo da linha menos o do C0, pesada pelo `β` do trecho de cada passo (o M-real e o M-v2 com `β = 1`).
- **Por que a diferença e não o tempo:** o tempo absoluto de um microssetor depende sobretudo do comprimento dele, e qualquer medidor daria ρ perto de 1.
- **Vale o candidato de maior ρ.** No M-real e no M-v2, "deixar de fora" não muda nada, porque eles não ajustam nada. Os três são relatados, com o ρ por linha.

### 6. A região de confiança da busca

A lateral da linha não se afasta mais que **1,0 m** da lateral da L1, em nenhum ponto da grade.
- **Por quê:** fora das linhas do pedido 47, o medidor não foi conferido no jogo.
- **Como:** os genes ficam entre os genes da L1 −1,0 m e +1,0 m (e dentro do corredor); o que a spline passar de 1,0 m entre os genes é penalizado (item 7).

### 7. As duas linhas a testar

**L1, a montagem por trecho:**
- **em cada trecho do ADR 0030, a linha mais rápida no jogo entre a C2, a C3 e a C4:** a de menor mediana do tempo do trecho no `_conta.json` do pedido 49 (a tabela B.1). Nenhuma delas vem do `fast_lane.ai`;
- **a emenda** entre o trecho k (linha A) e o trecho k+1 (linha B), quando A ≠ B, fica na reta do trecho k+1, do início dele ao início da curva dele (no trecho C14→linha, até o fim):
  - o centro da emenda é o ponto da grade dessa reta, a pelo menos meia janela das pontas, onde |lateral de A − lateral de B| é a menor (onde as linhas se encontram);
  - a janela é de 40 m, ou o comprimento da reta se ela for menor (com o mínimo de 10 m);
  - na janela, a lateral é `(1 − w)·A + w·B`, com `w` o polinômio de grau 5 que vai de 0 a 1 com a primeira e a segunda derivadas nulas nas pontas;
- **depois, a codificação nova** (item 4), o corredor (item 4.7) e a conferência das restrições (item 4.4).

**L2, a busca nova:** o algoritmo genético do ADR 0028, item 10, com:
- **a codificação nova** (item 4) e **o medidor escolhido** (item 5.3);
- **a região de confiança** do item 6;
- **as sementes, nesta ordem:** a L1; a composição dos melhores trechos das 150 voltas (`composite_best_segments`); **a linha da LSTM geradora** (`data/ml/models/reference`, como no pedido 46); e as 150 voltas rotuladas, da mais rápida para a mais lenta. Cada uma é codificada e trazida para a região de confiança (os genes cortados em L1 ± 1,0 m). Os 10% finais da população são aleatórios dentro da região;
- **a aptidão:** o tempo do medidor escolhido, mais:
  - as penalizações de forma e de corredor do pedido 46 (`FitnessWeights(surrogate_weight=0)`: 30 s por metro médio fora do corredor; o serpenteio e a variação de curvatura acima do percentil 95 das voltas);
  - **as restrições do item 4.4 e a região do item 6, como barreira:** 5 s por trecho que passa de um limite, mais 100 s vezes o excesso relativo (`κ/κ_lim − 1` e `taxa/taxa_lim − 1`); 5 s mais 100 s por metro além de 1,0 m na região;
- **o resto como no ADR 0028, item 10:** 100 indivíduos, até 250 gerações ou 25 sem melhora de 1 ms, elitismo de 4, torneio de 3, cruzamento 0,9, mutação 0,3 com amplitude de 0,6 m a 0,15 m. **A semente aleatória é 50.** Se a busca passar de 6 h, ela para e a melhor até ali é a L2;
- **a L2 tem de ficar sem nenhuma penalização** (corredor, forma, restrições e região). Se a melhor da busca tiver alguma, a conta para e é relatada.

### 8. A velocidade e os pedais dos arquivos

A regra do pedido 47 (ADR 0029, item 1): a velocidade, o acelerador e o freio do arquivo original na mesma estação, nos arquivos da L1 e da L2. Assim os resultados ficam comparáveis com os do 47 e do 49.

### 9. Os arquivos e os scripts

- **Os `fast_lane.ai` da L1 e da L2** vão para `data/pista_teste/linhas/L1/` e `L2/`, fora dos commits, com o sha256 num manifesto à parte (`data/pista_teste/linhas/linha_do_projeto.json`). O `linhas.json` do 47 não muda.
- **O que este pedido gera** fica em `data/linha_do_projeto/` (fora dos commits): as laterais, os genes, as contas e as figuras.
- **O `trocar_linha.ps1`** aceita `-Condicao L1` e `-Condicao L2`, com as mesmas travas do 47. O `registro.py` passa a aceitar L1 e L2.

### 10. O que se espera (escrito antes de rodar)

1. **A conferência passa no primeiro ou no segundo par da escada** (10/25 m ou 8/20 m).
   - **Por quê:** o raio do arquivo da IA é suave (rugosidade de 0,31 × 10⁻³ 1/m no pedido 49), e o menor raio dela por trecho fica entre 22 e 226 m. Uma spline com nós a cada 8 a 10 m nas curvas segue picos de curvatura de 20 m ou mais.
2. **A L1 codificada fica sem raio fechado na subida dos boxes:** o menor raio do arquivo no trecho C14→linha passa de 200 m.
   - **Por quê:** a spline no plano X/Z não leva a ondulação da linha central nem as quinas da grade.
3. **O M-cal é o escolhido,** com ρ acima do M-real; o M-v2 fica perto do M-real.
   - **Por quê:** a perda grande do medidor é a C10 (−1,0 s previstos, +0,3 s no jogo), e a escala por trecho tira o peso dela. O envelope da M1 v2 muda pouco o formato do perfil de velocidade.
4. **O medidor escolhido prevê a L2 de 0,1 a 0,3 s mais rápida que a L1,** e a L2 fica perto do limite de 1,0 m em poucos trechos.
5. **No jogo, a L1 fica entre −0,3 s e +0,2 s da mediana dos C0 vizinhos.**
   - **Por quê:** o teto por trecho é −0,46 s, mas um trecho muda a entrada do seguinte, e a escolha foi feita depois de ver os tempos. Em compensação, a codificação nova tira a frenagem na subida dos boxes, que custou de 0,03 a 0,10 s na C3 e na C4.
6. **A meta (a melhor volta igual ou menor que a dos dois C0 vizinhos):** a chance é perto de meio a meio para a L1; para a L2, um pouco menor, porque o medidor ainda não foi conferido fora das linhas do 47.
7. **A `#0013` (1:24,829) fica fora de alcance neste teste:** a melhor do C0 no 47 foi 1:25,353, com outra pista e outro preset na `#0013`.

### 11. A referência do coach (Parte E)

- **Se uma linha atingir a meta,** ela vira a linha de referência de `data/modelo1_por_trecho/referencia_por_trecho.json` em todos os trechos, com a marca "linha do projeto, meta atingida em <data>", e a execução da IA nela (as medidas do ADR 0030, item 5), medida nas 7 voltas do bloco dela.
- **Se as duas atingirem,** vai a de melhor volta.
- **Se nenhuma atingir,** a referência não muda, e o relatório diz quanto faltou e onde (por trecho, contra os C0 vizinhos).

### 12. Nenhuma regra muda depois de ver os números

Este registro é commitado antes de qualquer busca, calibração ou arquivo de linha. O resultado entra numa seção no fim, sem mudar nada acima dela.

### 13. Emenda à conferência (12/11, decisão do Eduardo, opção "a")

**Por quê:** a conferência do item 4.5 não passou em nenhum degrau da escada (commit `02f6fd8e`).
- A distância passou folgada: p95 de 0,007 a 0,026 m.
- O menor raio por trecho não ficou a 5%. A `#0013` convergiu com o espaçamento fino (5,0% em 5/12,5 m). O C0 piorou (−18% na C01): sem regularização, a spline fina segue o ruído dos pontos do próprio arquivo, e o raio de três pontos é um valor extremo, decidido por um ponto só.

**O que muda, só no item 4.5 (antes de qualquer linha nova, busca ou arquivo):**
- **o menor raio do C0** passa a ser medido como o da `#0013`: pela curvatura de 12 m do item 4.4, na lateral da grade, fora da emenda da volta. São comparados o C0 codificado pelos pontos do arquivo e decodificado na grade, e a lateral do arquivo na grade (`condicoes.lateral_da_linha`). O raio de três pontos do arquivo continua relatado, fora da conferência;
- **a tolerância do raio** passa de 5% para **10%**, nas duas linhas;
- **a distância** continua como estava (0,10 m em 95% dos pontos);
- a escada e a ordem dela (item 4.6) não mudam: vale o primeiro par que passar.

**Calculado antes desta emenda, depois da falha, só para a decisão:** com esta regra, o primeiro par que passa é 6/15 m (C0 9,1%, `#0013` 6,6%).

## Consequências

- **A linha do projeto só vai para o coach pela regra do item 11.** Até lá, o ADR 0009 vale como está.
- **O escritor do pedido 47 (`linha_nova.montar`) continua como está,** para os arquivos C1 a C4 continuarem os mesmos. A codificação nova usa só a parte dele que recebe as posições (`montar_por_posicoes`).
- **As sessões da cópia continuam fora do ML** (ADR 0029, item 13).
