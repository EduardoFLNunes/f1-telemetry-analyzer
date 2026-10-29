# Pedido 37 — M1: o primeiro modelo do carro para a frente (física simples e correção aprendida)

**De:** Eduardo. **Data:** 24/10/2026.
**Tipo:** ML offline (`backend/ml/`) e documentação. Nada do app, do rádio, do coach, do store v2 ou do relatório de evolução muda.

**Ao mandar executar este pedido, eu aprovo o ADR 0022** (`docs/prompts/anexos-37/0022-validacao-da-m1-modelo-do-carro.md`): os dados, o relógio, a divisão, as referências, a métrica e os critérios da M1.

**Quando começar:** agora, num chat novo, só para os modelos.
- **Uma sessão de implementação por vez** (ADR 0008): enquanto este pedido roda, o chat do rádio fica parado.
- O teste no jogo do pedido 36 continua pendente, mas não depende deste pedido.
- Os cuidados de processo do pedido 33 (Parte C) valem aqui: nenhuma trava do git é apagada sem me perguntar, e uma janela de teste, se houver, leva "[teste]" no título.

## Contexto

1. **O que é a M1** (ADR 0017, etapa M1): o modelo do carro "para a frente".
   - **Entra:** o estado do carro agora e o que o piloto faz (volante, acelerador e freio).
   - **Sai:** o estado do carro depois de Δt.
   - **Forma:** uma física simples, com poucos parâmetros e explicável, mais uma correção aprendida dos dados para o que essa física erra. É o desenho de Kabzan et al. 2019 (física e Processo Gaussiano no resíduo) e do BayesRace 2021.
   - **Por que importa:** é a base da peça D (etapa M4) e, depois, do cálculo do tempo de volta da busca evolutiva do Modelo 1 (ADR 0018). Hoje esse cálculo é o simulador quase-estacionário, que não recebe as entradas do piloto nem tem estado.
2. **A coleta terminou:** 5 de 5 sessões humanas com a guinada (`yaw_rate`) e as velocidades no referencial do carro (`velocity_long` e `velocity_lat`), em pelo menos 95% da grade (pedido 36, Parte A, `_m1.json`):
   - `2026-10-15_23-24-50_vhe_interlagos`;
   - `2026-10-17_01-02-22_vhe_interlagos`;
   - `2026-10-17_16-17-08_vhe_interlagos`;
   - `2026-10-18_12-38-44_vhe_interlagos`;
   - `2026-10-21_20-30-54_vhe_interlagos`.
3. **O que já existe e pode ser usado:**
   - os canais gravados (`docs/modelo_fisico_m0.md`, seções 1 e 2): `localVelocity`, `localAngularVelocity`, `steerAngle`, acelerador, freio, marcha, `wheelLoad`, `wheelSlip`, `accG`, `heading` e a posição;
   - o envelope do carro ajustado na telemetria (`ml/optimization/vehicle_model.py`): os limites de tração, de freada e lateral por velocidade, com a aerodinâmica em v²;
   - as funções de corte e de validade de volta do store v2 (`ml/data/store_v2.py`);
   - os pacotes já instalados: numpy, scipy, pandas, scikit-learn 1.6.1 e torch.
4. **O que está em aberto:**
   - **a unidade do volante** (`docs/modelo_fisico_m0.md`, seção 3). A razão volante ÷ curvatura sugere fração do curso, com a roda a cerca de 15° no fim, mas só a guinada gravada fecha a questão;
   - **o entre-eixos, a massa e a distribuição de peso:** o `data.acd` é criptografado e não é aberto. Tudo sai dos dados, como o ADR 0017 manda;
   - **as convenções de sinal:** o volante positivo é à direita, e a aceleração lateral positiva é à esquerda (M0, seção 3). O sinal da velocidade lateral do referencial do carro precisa ser conferido.
5. **O que aprendemos com os artigos e os pedidos anteriores:**
   - **modelo pequeno:** redes grandes decoram as voltas e erram fora delas (identificação de sistemas na pista, 2025, com 58 parâmetros). Fora do que o piloto já fez, a resposta certa é "não conclusivo";
   - **"demanda não é capacidade"** (`vehicle_model.py`): o que o piloto pediu numa faixa de velocidade não é o limite do carro nessa faixa.

## Parte A — Registrar antes de construir

Antes de treinar qualquer coisa, num commit próprio:

1. **O ADR 0022:**
   - copie o anexo para `docs/decisoes/`;
   - acrescente a linha em `docs/decisoes/README.md`;
   - apague `docs/prompts/anexos-37/`.
2. **`docs/modelo_fisico_m1.md`, seção 1, "Registrado antes de construir":**
   - os dados: as 5 sessões e as voltas válidas de cada uma;
   - o relógio e o passo Δt escolhido, com o porquê (o gravador anda em cerca de 15 ms);
   - o estado e as entradas, com as unidades e os sinais;
   - a forma da física, com a lista dos parâmetros e a faixa plausível de cada um;
   - a forma da correção aprendida e as variáveis que ela recebe;
   - o corte de "não conclusivo": como ele é fixado nas sessões de treino;
   - as referências R0 e R1, os horizontes e os critérios, copiados do ADR 0022;
   - **o que se espera,** em uma frase, antes de ver qualquer número.
3. **Nada disso muda depois de ver o teste.** Se algo tiver de mudar, pare e me pergunte; a mudança vira um ADR antes de rodar de novo.

## Parte B — Os dados da M1

1. **De onde:** as gravações cruas (`player.jsonl`) das 5 sessões, só dentro das voltas válidas do store v2. As gravações são só lidas.
2. **Como:**
   - o relógio é o cronômetro do jogo;
   - as amostras repetidas são descartadas;
   - os trechos são cortados nos buracos de 50 ms ou mais;
   - os dados são reamostrados no passo Δt dentro de cada trecho.
3. **As conferências de convenção,** antes de qualquer ajuste:
   - a guinada gravada contra a derivada do `heading`;
   - o sinal da velocidade lateral do referencial do carro numa curva à esquerda e numa à direita;
   - a velocidade longitudinal contra a velocidade do mundo;
   - o sinal do volante contra o da guinada.

   Se alguma não bater, pare e relate.
4. **Relate:** as amostras e os trechos por sessão, quanto foi descartado e por quê, e a faixa de cada canal.
5. **Onde fica:** `data/ml/modelo_carro/`, fora do git, com o hash e o tamanho de cada arquivo lido e escrito (ADR 0007).

## Parte C — A física simples (a referência R1)

1. **A forma:** um modelo de bicicleta dinâmico, com:
   - **o estado:** a velocidade longitudinal, a velocidade lateral e a guinada, mais a posição e o rumo para andar no horizonte;
   - **a força longitudinal** pelo acelerador e pelo freio, limitada pelo envelope;
   - **as forças laterais** na frente e atrás, lineares no ângulo de deriva e saturadas pela elipse de atrito;
   - **a aerodinâmica** em v² (carga e arrasto);
   - **a transferência de carga** só se as cargas gravadas nas rodas mostrarem que ela muda o resultado.

   Se outra forma simples explicar melhor os dados, proponha e justifique na Parte A, antes de rodar.
2. **Os parâmetros:**
   - poucos, com unidade e faixa plausível;
   - ajustados por mínimos quadrados (scipy), só nas 4 sessões de treino de cada rodada;
   - relatados por rodada, para mostrar se ficam estáveis entre as rodadas.
3. **A unidade do volante:** identifique a razão entre o ângulo da roda e o `steerAngle` com a guinada gravada, nos trechos de pouca aceleração lateral. Feche a questão da seção 3 de `docs/modelo_fisico_m0.md`.
4. **O entre-eixos e a distribuição de peso:** estimados dos dados (as cargas nas rodas em baixa velocidade e a relação entre guinada, velocidade e volante). Relate o valor e o quanto ele é incerto.

## Parte D — A correção aprendida (a M1)

1. **O que aprende:** o resíduo da física, isto é, a diferença entre a variação medida do estado em Δt e a que a física prevê. Ela aprende para a velocidade longitudinal, a velocidade lateral e a guinada.
2. **O modelo:**
   - um Processo Gaussiano (scikit-learn), como no ADR 0017;
   - **as variáveis de entrada:** o estado e as entradas do piloto, e nada que identifique a volta, a sessão ou o ponto da pista. O modelo do carro não pode decorar Interlagos nem o piloto (ADR 0017, item 1);
   - **para caber na memória,** um subconjunto das amostras de treino, escolhido por regime (freada, curva, tração, freio e volante juntos, reta). Relate quantas amostras e como foram escolhidas;
   - os hiperparâmetros pela verossimilhança, só nas sessões de treino.
3. **A incerteza e o "não conclusivo":** a incerteza do Processo Gaussiano dá o intervalo de 90% e marca os casos "não conclusivo", com o corte fixado na Parte A.
4. **Sem pacote novo.** Se o Processo Gaussiano não couber com o que está instalado, pare e relate as opções. Não troque de modelo por conta própria.

## Parte E — A validação (ADR 0022)

1. **As 5 rodadas,** cada uma com uma sessão de fora.
2. **Os inícios da previsão:** a partir de instantes espalhados pelos trechos da sessão de teste, a cada 0,1 s, por exemplo. Em cada um, o modelo anda em malha aberta com as entradas gravadas até 1,0 s, sem atravessar buraco.
3. **As referências:** R0 (persistência) e R1 (só a física).
4. **A tabela do veredito:** os 7 critérios do ADR 0022, cada um com o valor medido e "passa" ou "não passa".
5. **O que mais relatar:**
   - os horizontes de 0,25 s e 1,0 s;
   - o erro de posição em metros;
   - cada grandeza separada;
   - por sessão, por regime e por faixa de velocidade;
   - a fração de "não conclusivo";
   - **figuras:** o previsto contra o gravado numa freada (a da C01) e numa curva lenta (a C10), com a faixa de incerteza.
6. **Uma indicação para a M2,** sem entrar no modelo: o resíduo da M1 correlaciona com a temperatura dos pneus? Relate só a correlação.
7. **Se um critério não passar,** relate e pare. Nenhum ajuste depois de ver o teste.

## Parte F — Documentação

- **`docs/modelo_fisico_m1.md`:** a seção 1 (Parte A) e as seções com os dados, a física, a correção, a validação e o veredito, com as figuras. Escreva para quem não é da área: o que o modelo faz, como foi testado e o que o resultado quer dizer.
- **`docs/modelo_fisico_m0.md`:** feche as pendências da unidade do volante (seção 3) e do relógio (seção 6), apontando para a M1.
- **`docs/arquitetura_ml.md`:** na tabela das peças, a situação do cálculo do tempo de volta (a M1 feita, aprovada ou não).
- **`docs/integracao_ml_e_empacotamento.md` e `docs/backlog.md`:** o que muda com o resultado.
- **ADR 0004:** diga se o resultado muda algo nele, mas não o mude: prever o movimento do carro não é estimar ganho de tempo, e essa revisão é da M4.

## Testes

- **os dados:** o descarte das amostras repetidas, o corte nos buracos e a reamostragem;
- **as convenções:** os sinais numa curva à esquerda e numa à direita;
- **a física:** uma curva em regime permanente e uma freada em linha reta dão o que a conta manda;
- **a malha aberta:** o passo a passo não atravessa buraco;
- **as métricas:** o skill contra uma referência conhecida;
- **o "não conclusivo":** um ponto fora dos dados de treino é marcado;
- **as suítes:** a do backend continua passando.

## Regras gerais

- **Nada do app, do rádio, do coach, do store v2 ou do relatório de evolução muda.** A M1 é um módulo novo em `backend/ml/`, fora do executável empacotado, como o resto do `ml/`.
- **As gravações são só lidas.**
- **Os critérios são os do ADR 0022,** fixados antes de rodar. Resultado negativo é aceito e documentado.
- **Não instale nem atualize pacotes.** Se algo pedir pacote novo, pare e relate.
- **Não mexa no app instalado nem em arquivos do jogo.**
- **Não gere instalador.**
- **Não contorne nenhuma trava:** se algo parar, pare também e registre o motivo.
- **Branch e commits:** branch `etapa/m1-modelo-do-carro`, a partir de `develop`, commits por parte (a Parte A antes de qualquer treino), merge em `develop`. Sem push.
- **Uma sessão de implementação por vez** (ADR 0008).
- **Relatório** em `docs/handoff/2026-10-24_37_m1-modelo-do-carro_relatorio.md`, como manda o CLAUDE.md, com:
  - a Parte A e o commit dela;
  - os dados e as conferências de convenção;
  - os parâmetros da física por rodada, com a unidade do volante e o entre-eixos;
  - a correção aprendida: as amostras usadas e os hiperparâmetros por rodada;
  - a tabela do veredito e as tabelas por sessão, por regime e por velocidade;
  - as figuras;
  - um `resultados.json` com o commit, o `geometry_id`, o ambiente, os comandos e os hashes dos arquivos lidos (ADR 0007);
  - a saída dos testes, os commits e o tempo de cada etapa.
- Se algo do contexto não bater com o repositório, pare e registre no relatório.
