# Pedido 39 — M1: medir a geometria do carro pela telemetria do jogo e retomar o pedido 37

**De:** Eduardo. **Data:** 25/10/2026.
**Tipo:** ML offline (`backend/ml/`), uma ferramenta que só lê a memória compartilhada do jogo, e documentação. Nada do app, do gravador, do rádio, do coach, do store v2 ou do relatório de evolução muda.

**Ao mandar executar este pedido, eu aprovo:**
1. **o ADR 0024** (`docs/prompts/anexos-39/0024-m1-geometria-medida-pela-telemetria.md`): `L`, `b`, `h`, `k_δ` e o ponto da velocidade gravada passam a ser medidos pela telemetria do jogo, e não ajustados;
2. **a conferência da guinada pela leitura do texto registrado** (correlação em todas as amostras e o mesmo sinal nos dois lados). A guinada bate.

**Quando começar:** agora, no chat dos modelos, na branch do pedido 37 (`etapa/m1-modelo-do-carro`), que continua sem merge. O pedido 38 vem depois deste.

## Contexto

1. **O relatório do pedido 37** (`docs/handoff/2026-10-24_37_m1-modelo-do-carro_relatorio.md`):
   - as Partes A e B estão feitas e commitadas;
   - a Parte C parou: a regra registrada deu `L` negativo ou menor que 1,1 m nas 5 rodadas;
   - nenhum número de teste foi calculado;
   - o código da física, da correção, da malha aberta e das métricas está pronto e testado.
2. **O que o ADR 0024 decide e por quê:** está no anexo. Em resumo: a página de física do jogo já tem o ponto de contato de cada pneu (`tyreContactPoint`), a direção de cada pneu (`tyreContactHeading`) e a altura do centro de massa (`cgHeight`). Com eles, a geometria é medida diretamente, sem regressão e sem abrir arquivo do carro.
3. **O retrato da memória que já existe** (`data/debug/ac_shared_memory_full_inventory.csv`, de maio de 2026) dá cerca de 2,96 m de entre-eixos, bitolas de 1,58 m e 1,52 m, 0,263 m de altura do centro de massa e cerca de 15° de roda por unidade de volante. **Não se sabe com que carro ele foi tirado.** Serve como primeira olhada, não como medida.
4. **Dois cuidados com os campos:**
   - **a ordem dos números:** no adaptador (`backend/core/assetto_adapter.py`), `c_float * 4 * 3` é, no ctypes, um vetor de 3 por 4. Na memória do jogo, o campo é de 4 por 3: 4 rodas (dianteira esquerda, dianteira direita, traseira esquerda, traseira direita), com 3 coordenadas cada. Leia o campo achatado: a roda `w`, coordenada `c`, fica no índice `3·w + c`. O retrato confirma essa leitura (as bitolas e o entre-eixos só fazem sentido assim);
   - **o sentido de `tyreContactHeading`:** no retrato, os vetores apontam para trás em relação ao eixo do carro (traseiro para dianteiro). Confira o sentido contra os pontos de contato antes de medir o ângulo.

## Parte A — Registrar antes de medir

Num commit próprio:

1. **O ADR 0024:**
   - copie o anexo para `docs/decisoes/`;
   - acrescente a linha em `docs/decisoes/README.md`;
   - apague `docs/prompts/anexos-39/`.
2. **`docs/modelo_fisico_m1.md`:** uma seção nova, "1.9 Emenda de 25/10 (ADR 0024)", com:
   - como cada parâmetro é medido;
   - os portões;
   - o que acontece se um portão falhar.

   **Não apague nem reescreva a seção 1.4.** Acrescente nela só uma linha apontando para a 1.9.
3. **A conferência da guinada:** registre na seção 3 que vale a leitura do texto registrado, por decisão minha de 25/10.

## Parte B — A primeira olhada no retrato

1. **Leia os campos do retrato** com a ordem certa e relate:
   - o entre-eixos e as bitolas;
   - a posição de `carCoordinates` ao longo do carro e a altura dela;
   - o ângulo entre os pneus dianteiros e os traseiros, e o `steerAngle` no mesmo instante.
2. **Compare** com a reportagem (2,943 m; 1,552 m e 1,502 m) e com a razão volante ÷ curvatura da M0 (cerca de 10,6 em baixa velocidade, que deve ficar perto de `L/k_δ`).
3. **É só uma olhada:** nenhum desses números entra na M1.

## Parte C — A ferramenta de medição (parada)

1. **Uma ferramenta que só lê a memória compartilhada,** por exemplo `backend/ml/scripts/medir_geometria.py`:
   - usa o adaptador que já existe;
   - lê a cerca de 60 Hz, com o cronômetro do jogo;
   - grava, sem descartar nada: o cronômetro, o `steerAngle`, o `heading`, a `localVelocity`, a `localAngularVelocity`, as cargas das rodas, a velocidade, o `cgHeight`, os 4 pontos de contato e as 4 direções dos pneus, e a posição do carro (`carCoordinates`);
   - salva em `data/ml/modelo_carro/geometria_<data>.parquet`, fora do git;
   - não escreve na memória do jogo, não muda o app nem o gravador, e não lê nenhum arquivo do carro.
2. **Testes** com uma memória simulada: a ordem 4 por 3 dos campos, o cronômetro e a gravação do arquivo.
3. **Pare aqui** e grave o relatório parcial com os passos para mim, com os comandos exatos:
   - abrir o Assetto Corsa com o `rss_formula_rss_3_v6_2026` em Interlagos;
   - rodar a ferramenta;
   - **parado no box,** girar o volante devagar de um batente ao outro, duas vezes (o ângulo da roda em toda a faixa do volante, sem escorregamento);
   - andar 3 voltas normais;
   - encerrar a ferramenta e avisar: "medi a geometria".

## Parte D — A geometria medida

Depois do meu aviso:

1. **Meça,** pela seção 1.9:
   - `L`;
   - `b = w_f · L`;
   - `h` pelo `cgHeight`;
   - `k_δ`, com o lado esquerdo e o direito à parte e a média;
   - o ponto `x_v` da velocidade gravada.
2. **Aplique os portões** e relate cada um com o valor, a faixa e "passa" ou "não passa". Se um portão falhar, use o caminho que o ADR 0024 manda e diga isso.
3. **Relate também:**
   - `h/L` pelo `cgHeight` contra o valor das cargas (0,135 a 0,163 no pedido 37);
   - `L/k_δ` contra a razão da M0;
   - se a curva do ângulo da roda contra o volante é linear em toda a faixa, ou se a razão muda perto dos batentes.

## Parte E — Retomar o pedido 37

Com a geometria medida, siga as Partes C a F do pedido 37, sem mudar nenhuma outra regra:

1. **A física (R1):** a geometria fica fixa, a velocidade lateral é levada ao centro de massa pelo `x_v`, e os outros 7 parâmetros são ajustados nas 4 sessões de treino de cada rodada, como registrado. Relate os parâmetros por rodada e quais ficaram no limite.
2. **Antes da sessão de teste,** relate o erro da física contra a persistência nas próprias sessões de treino, como no relatório do pedido 37, para comparar com a regra antiga.
3. **A correção (M1) e a validação,** como registradas: as 5 rodadas, a tabela do veredito com os 7 critérios, as tabelas por sessão, regime e velocidade, as figuras da C01 e da C10, e a correlação com a temperatura dos pneus.
4. **Se um critério não passar,** relate e pare. Nenhum ajuste depois de ver o teste.
5. **A Parte F do pedido 37:** a documentação, com o resultado.
6. **O merge em `develop`,** no fim.

## Regras gerais

- **Os critérios do ADR 0022 não mudam.** Resultado negativo é aceito e documentado.
- **A ferramenta só lê a memória compartilhada.** Nada do app, do gravador ou do jogo muda, e nenhum arquivo do carro é lido. O `data.acd` nunca é aberto.
- **As gravações são só lidas.**
- **Não instale nem atualize pacotes.** Se algo pedir pacote novo, pare e relate.
- **Não gere instalador.**
- **Não contorne nenhuma trava:** se algo parar, pare também e registre o motivo. Uma trava do git não é apagada sem me perguntar.
- **Branch e commits:** a mesma branch do pedido 37 (`etapa/m1-modelo-do-carro`), commits por parte (a Parte A antes de medir), merge em `develop` no fim. Sem push.
- **Uma sessão de implementação por vez** (ADR 0008).
- **Relatório** em `docs/handoff/2026-10-25_39_m1-geometria-medida_relatorio.md`, como manda o CLAUDE.md, com:
  - a Parte A e o commit dela;
  - a primeira olhada no retrato (Parte B);
  - na parada da Parte C, os passos para mim;
  - a geometria medida e os portões (Parte D);
  - a física nas sessões de treino, antes e depois da geometria medida;
  - a tabela do veredito da M1 e as demais tabelas e figuras;
  - um `resultados.json` com o commit, o `geometry_id`, os comandos e os hashes dos arquivos lidos (ADR 0007);
  - a saída dos testes e os commits.
- **Complete também o relatório do pedido 37,** com uma linha apontando para este.
- Se algo do contexto não bater com o repositório, pare e registre no relatório.
