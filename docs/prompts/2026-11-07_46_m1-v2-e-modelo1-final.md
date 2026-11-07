# Pedido 46 — M1 v2: o pneu com sensibilidade à carga e pico, a transferência lateral, e o resultado final do Modelo 1

**De:** Eduardo. **Data:** 07/11/2026.
**Tipo:** M1 (`backend/ml/modelo_carro/`), Modelo 1 (`backend/ml/optimization/` e scripts), documentação e testes. O coach, o rádio, o app, o store v2 e o Modelo 2 não mudam.

**Quando começar:** depois do merge do pedido 45 em `develop`. O teste do 45 no jogo roda o app a partir desta pasta, na branch dele: enquanto ele não fechar, nenhuma sessão mexe na pasta nem pesa no processador. Antes de criar a branch, confira que nenhuma outra sessão está ativa na pasta (ADR 0008).

## Contexto

1. **A M1 v1 não foi aprovada** (pedido 39, `docs/modelo_fisico_m1.md`, seção 6):
   - em 0,5 s, skill de 0,202 contra a persistência (o critério 1 pede 0,50) e de 0,174 contra a física sozinha (o critério 2 pede 0,20). Os critérios 3 a 7 passaram;
   - **ela falha nas curvas,** que são 65% dos casos: skill de 0,13 contra a persistência, e a pior faixa é a de 160 a 220 km/h. Fora das curvas, a física sozinha já passa a persistência com folga;
   - **o retrato da falha** é a C10 a 76 km/h, com o volante perto do batente: a física prevê que o carro escorrega para fora (`vy` sobe a 1,5 m/s em 0,5 s), e o carro do jogo faz a curva com `vy` perto de zero;
   - **a correção aprendida** (um Processo Gaussiano por grandeza) treinou com 2.000 passos, 400 de cada regime, então as curvas tiveram o mesmo peso das retas;
   - **o "não conclusivo" não funcionou:** o corte saiu 1,000 nas 5 rodadas e nenhum caso foi marcado.
2. **A minha decisão (07/11), que revê a de 29/10:** a M1 volta. O TCC tem de apresentar modelos de algoritmo e de IA funcionando. A M1 v1 continua registrada como resultado negativo, e a M1 v2 é uma segunda tentativa, registrada antes de rodar, com os mesmos critérios.
3. **O carro é de fórmula** (`rss_formula_rss_3_v6_2026`): downforce alto e pneus largos e aderentes. A física da v1 já tem o downforce (carga por eixo com `κ_L·vx²`, cerca de 1,7 vez o peso a 270 km/h) e a elipse de atrito. **Faltam três efeitos que pesam justamente nesse tipo de carro:**
   - **a sensibilidade do pneu à carga:** o coeficiente de atrito cai quando a carga sobe, e a força máxima cresce com a carga elevada a cerca de 0,7 a 0,9, e não na mesma proporção. Na v1, `F_max = μ·n`, linear na carga;
   - **o pico do pneu:** depois de um ângulo de deriva, a força lateral cai. Na v1, o pneu satura (`tanh`) e fica no máximo;
   - **a transferência de carga lateral:** a v1 é um modelo de bicicleta, e as rodas de dentro e de fora de cada eixo viram uma só. Somada à sensibilidade à carga, a transferência lateral tira aderência do eixo.
4. **O pneu do Assetto Corsa tem esses três parâmetros,** pelo que as discussões públicas de modding descrevem: uma carga de referência, um expoente de sensibilidade à carga menor que 1, o ângulo de deriva do pico e o nível de queda depois dele. **Os arquivos do carro não são abertos** (o `data.acd` nunca é aberto): os parâmetros saem da telemetria, como a geometria saiu no ADR 0024.
5. **Os canais que já existem** nas 5 sessões da M1:
   - a carga de cada roda (`wheel_load_fl` a `_rr`, em N), a altura do carro (`rideHeight`), as temperaturas e o `wheelSlip` de cada roda;
   - as velocidades no referencial do carro e a guinada;
   - a geometria medida no pedido 39: entre-eixos de 2,964 m, bitolas de 1,588 m na frente e 1,509 m atrás, `cgHeight` de 0,271 m e `k_δ` de 0,304 rad.
6. **O Modelo 1 hoje:**
   - em agosto, a linha do algoritmo genético ficou 0,29 s atrás da volta da IA, no mesmo simulador (85,109 s contra 84,822 s, ADR 0009). Isso foi com o corredor errado e a LSTM treinada quase só com voltas da IA;
   - o corredor foi corrigido no pedido 44 (`corridor_id` `707d07029036abd6`);
   - a LSTM geradora retreinada foi reprovada (skill 0,042), e hoje `optimize_line.py` a usa como semente se o modelo existir, salvo com `--no-lstm`;
   - **o ADR 0009 continua valendo:** a linha gerada não vira alvo do coach sem um medidor do tempo aprovado. Ele não impede rodar a busca e relatar a comparação no mesmo medidor, como resultado do TCC.

## Parte A — Registrar antes de rodar (ADR 0028)

Escreva o **ADR 0028, "M1 v2"** (ou o próximo número livre), e a seção "M1 v2" em `docs/modelo_fisico_m1.md`, antes de rodar qualquer coisa. Tudo o que for fixado aqui sai da física e das definições, nunca de olhar o teste.

1. **A carga de cada roda:**
   - o peso parado, o downforce e a transferência longitudinal, como na v1, separados por roda;
   - **a transferência lateral:** em cada eixo, uma parcela de `m·a_y·h/t` (com `t` a bitola do eixo), com a divisão entre a frente e a traseira como parâmetro;
   - **os parâmetros da carga** são medidos por regressão contra `wheel_load_*` nas 4 sessões de treino de cada rodada, como `κ_L` na v1. Registre as amostras usadas, as faixas plausíveis e o que acontece se um parâmetro sair da faixa.
2. **O modelo de quatro rodas:** cada roda com o seu ângulo de deriva, a sua carga e a sua força. O momento de guinada inclui os lados. Com a bitola em zero, ele tem de voltar a ser a bicicleta da v1 (teste da Parte E).
3. **O pneu lateral, por roda:**
   - **sensibilidade à carga:** `μ(n) = μ_ref · (n / n_ref)^(q − 1)`, com `n_ref` fixo (registre qual e por quê) e o expoente `q` ajustado entre 0,6 e 1,0;
   - **o pico:** uma curva com o máximo no ângulo `α_pico` e queda até uma fração `f` da força máxima depois dele, com `α_pico` entre 3° e 12° e `f` entre 0,7 e 1,0. Registre a forma da curva (uma fórmula de Pacejka simplificada, ou outra com esses dois parâmetros) e o porquê;
   - **a rigidez de deriva** cresce com a carga, como na v1;
   - **a elipse de atrito** continua, por roda, com a força longitudinal da v1.
4. **O ajuste:** como na v1, por mínimos quadrados no estado depois de um passo, nas 4 sessões de treino, com as faixas plausíveis como limite. Parâmetro no limite é relatado.
5. **A correção aprendida:**
   - continua um Processo Gaussiano por grandeza, com o mesmo núcleo e as mesmas entradas;
   - **a amostra de treino segue a proporção de cada regime nas sessões de treino,** e não mais 400 por regime. Registre o tamanho total (o maior que couber em memória e em tempo) e a semente (46).
6. **O "não conclusivo":** uma regra nova, registrada aqui com o porquê, tirada da definição. Ele continua fora dos critérios de aprovação, como no ADR 0022.
7. **Os critérios: os 7 do ADR 0022, sem mudança.** As mesmas 5 sessões, as mesmas 5 rodadas, os mesmos casos, as mesmas referências R0 e R1 (com R1 sendo a física v2 sozinha) e o horizonte de 0,5 s.
8. **A física v1 entra como terceira referência, só relatada:** a v2 é comparada também com a v1, nas mesmas contas.
9. **O que se espera,** escrito antes de rodar: onde a v2 deve ganhar (as curvas, a faixa de 160 a 220 km/h, a velocidade lateral) e onde não deve mudar.
10. **A honestidade da tentativa:**
    - a v2 foi desenhada depois de ver o teste da v1, com o diagnóstico dela. Isso é escrito no ADR;
    - **a v2 é a última tentativa neste TCC.** Se ela não passar, o resultado é relatado e não há v3 ajustada nas mesmas sessões de teste;
    - a v1 e a v2 aparecem lado a lado.
11. **Uma linha de atualização** nos ADRs 0017 e 0022 apontando para o 0028.
12. **Commite a Parte A antes de rodar.**

## Parte B — Medir a carga e o pneu

1. **A carga:** os parâmetros da carga por rodada, com a incerteza (bootstrap agrupado por volta, 200 reamostragens, como na v1), e a conferência contra `wheel_load_*`: o erro da carga prevista, por roda e por regime.
2. **O pneu:** os parâmetros ajustados por rodada (`μ_ref`, `q`, `α_pico`, `f` e a rigidez), com a variação entre as rodadas.
3. **A curva do pneu** numa figura: a força lateral por carga contra o ângulo de deriva, com os pontos das sessões de treino.
4. **A física v2 sozinha** contra a persistência e contra a física v1, nas sessões de treino, antes de qualquer teste.
5. **Se a carga não for identificável** (parâmetro fora da faixa em todas as rodadas, ou intervalo que passa de zero), pare e relate, como na Parte C do pedido 37.

## Parte C — A validação (ADR 0022)

1. **Rode a validação** com a fase de treino commitada antes da fase de teste, como no pedido 39.
2. **Relate, lado a lado com a v1:**
   - a tabela dos 7 critérios e o veredito;
   - os horizontes de 0,25 s, 0,5 s e 1,0 s;
   - cada grandeza, com a velocidade lateral em destaque;
   - por sessão, por regime e por faixa de velocidade;
   - o "não conclusivo": quantos casos foram marcados, por regime e por sessão.
3. **As mesmas figuras da v1:** a freada da C01 e a curva lenta da C10, com a v1, a v2, R0 e o gravado.
4. **Só para informação, fora do veredito:** a v2 nas sessões gravadas depois de 21/10 que tenham os canais (por exemplo, 24/10 e 01/11).

## Parte D — O resultado final do Modelo 1, com dois caminhos

### D.1 Registrar antes de rodar (no ADR 0028 ou num ADR próprio)

1. **O medidor do tempo:**
   - **se a M1 v2 for aprovada:** o simulador quase-estacionário com o envelope de aceleração tirado da M1 v2 (a maior aceleração lateral e longitudinal que ela permite em cada velocidade, em regime permanente). Registre como o envelope é calculado;
   - **se não for aprovada:** o simulador quase-estacionário como está, com o envelope das voltas reais.
2. **A comparação,** sempre no mesmo medidor:
   - a volta da IA (`2026-10-04_03-42-10#0013`, 1:24,829);
   - a sua melhor volta (1:26,568);
   - a linha gerada.
3. **O critério:** a linha gerada aprova se o tempo dela no medidor for igual ou menor que o da volta da IA no mesmo medidor, dentro do corredor do pedido 44, e com o serpenteio e a variação de curvatura dentro dos limites que a função de aptidão já usa.
4. **A busca:** o algoritmo genético como está registrado (100 indivíduos, até 250 gerações ou estagnação), com o corredor do pedido 44 e sementes das voltas reais (`humano` e `ia` rotuladas), em duas versões:
   - **sem a LSTM geradora** (`--no-lstm`);
   - **com a LSTM geradora** nas sementes. É o teste dela no papel de semente: a busca chega a uma linha melhor, ou mais cedo, com ela?

   Registre as sementes aleatórias.

### D.2 Rodar e relatar

1. **Os tempos no medidor:** a volta da IA, a sua melhor e as duas linhas geradas, com a diferença por microssetor.
2. **A incerteza:** é tempo simulado, não tempo de pista. Relate o erro conhecido do medidor (o do simulador: 1,36 s em média por volta, ADR 0017) e diga o que a comparação relativa mede e o que não mede.
3. **As duas versões da busca:** o tempo final, o número de gerações até estagnar e a distância entre as duas linhas.
4. **As figuras:** a linha gerada sobre a pista, ao lado da linha da IA e da sua melhor, e a diferença de tempo acumulada contra a IA.
5. **A linha gerada não vai para o coach** (ADR 0009). Ela é salva com o `geometry_id`, o `corridor_id`, o medidor usado e o commit.
6. **Se a busca passar de 6 h,** pare e relate a estimativa.

## Parte E — Testes

Em `tests/`, com dados sintéticos:

- a carga de cada roda: a transferência lateral com o sinal certo nas curvas à esquerda e à direita, e a soma das 4 cargas igual ao peso mais o downforce;
- o pneu: o pico no `α_pico`, a queda até `f`, e a força máxima crescendo menos que a carga quando `q < 1`;
- o modelo de quatro rodas com a bitola em zero igual à bicicleta da v1;
- a amostra da correção na proporção dos regimes;
- o envelope tirado da M1 v2: cresce com a velocidade enquanto o downforce domina e respeita a elipse;
- o medidor dá o mesmo tempo para a mesma linha nas duas chamadas;
- os testes da v1 continuam passando, ou o relatório diz qual mudou e por quê.

A suíte do backend continua passando.

## Parte F — Documentação

- **`docs/modelo_fisico_m1.md`:** a seção "M1 v2", com o registro, os resultados e a comparação com a v1.
- **ADR 0028**, e as linhas de atualização nos ADRs 0017 e 0022 (Parte A) e no 0009, se o medidor mudar.
- **`docs/arquitetura_ml.md`:** o medidor do tempo e o resultado final do Modelo 1.
- **`docs/backlog.md`:** não edite; ele é mantido pelo Cowork. Liste no relatório os itens para ele.
- **`docs/tecnica_de_pilotagem_lista.md`:** uma linha no histórico, se algo da técnica mudar.

## Regras gerais

- **O coach, o rádio, o app, o store v2 e o Modelo 2 não mudam.**
- **Nenhum critério muda depois de ver os números.** Os valores fixos da Parte A e da D.1 são registrados e commitados antes de rodar.
- **O `data.acd` nunca é aberto,** nem outro arquivo do carro ou da pista.
- **As gravações só são lidas.** Não apague nem mova nenhuma.
- **Não instale nem atualize pacotes.** Se algo pedir pacote novo, pare e relate.
- **Não contorne nenhuma trava:** se algo parar, pare também e registre o motivo.
- **Branch e commits:** branch `etapa/m1-v2-e-modelo1`, a partir de `develop` depois do merge do pedido 45, commits por parte, merge em `develop`. As branches de outros pedidos não são tocadas.
- **Cópia no GitHub (vale para todo pedido):**
  - depois dos commits de cada parte e antes de cada parada, envie a branch do pedido ao `origin`; depois do merge, envie `develop`;
  - só envios que não reescrevem o remoto (branch nova ou avanço simples). Nunca `--force` nem `--force-with-lease`;
  - `main` e as tags não vão neste pedido;
  - antes do primeiro envio, confira que nada acima de 50 MB, nenhum segredo e nenhuma gravação (`recordings/`, `data/recordings`, `data/ml`) entrou nos commits;
  - depois de cada envio, confira com `git ls-remote origin` que o hash remoto é o mesmo do local;
  - se o controle de permissões da sessão recusar o envio, deixe no relatório os comandos para eu rodar pelo terminal;
  - se pedir login, se o envio for recusado pelo GitHub ou se o remoto tiver divergido, pare e me avise. Nenhum token ou senha no chat, nos arquivos ou no relatório.
- **Uma sessão de implementação por vez** (ADR 0008). Antes de trocar de branch, confira se outra sessão está ativa.
- **Os tempos de volta** no formato M:SS,mmm.
- **Relatório** em `docs/handoff/2026-11-07_46_m1-v2-e-modelo1_relatorio.md`, como manda o CLAUDE.md, com:
  - os valores fixos da Parte A e da D.1 e os commits em que foram registrados;
  - a carga e o pneu medidos (Parte B);
  - a validação da v2 ao lado da v1, com o veredito (Parte C);
  - o medidor usado e o resultado final do Modelo 1 (Parte D);
  - a saída dos testes e os commits;
  - o que foi enviado ao GitHub: a ref, o hash local e o hash no remoto;
  - os itens para o backlog.
- Se algo do contexto não bater com o repositório, pare e registre no relatório.
