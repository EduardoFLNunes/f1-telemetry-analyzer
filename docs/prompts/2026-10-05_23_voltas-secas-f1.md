# Pedido 23 — Faixa de linhas reais da F1 em Interlagos: voltas secas de várias classificações

**De:** Eduardo (o plano é meu). **Data:** 05/10/2026.
**Tipo:** documentação, coleta de dados externos e medição. Nenhum modelo é treinado.

## Contexto

1. **O pedido 22 aceitou o alinhamento de uma volta da F1:** a volta 32 de Norris na classificação de 2024. Ficaram 2,03% dos pontos fora do corredor, e o p95 do excesso foi de 0 m.
2. **Fato novo: essa classificação foi com pista molhada.** A classificação do GP de São Paulo de 2024 teve chuva, cinco bandeiras vermelhas e pole de Norris em 1:23,405, com pneus de chuva e intermediários. Na chuva, os pilotos costumam fugir da linha seca. Isso é uma hipótese, que este pedido mede. Portanto a tabela "F1 − IA" do pedido 22 comparou a IA com uma linha de chuva.
   - Confira na coluna `Compound` do próprio FastF1 qual pneu essa volta usou e registre no relatório.
3. **Uma volta só não separa duas coisas:** o que "a F1 faz assim" e o que "esse piloto fez nessa volta". O Modelo 1 precisa de uma **faixa**, ou seja, de onde passam várias voltas reais secas em cada trecho.
4. **A limitação registrada no pedido 22 continua.** Ajustar contra a linha central confunde um deslocamento lateral uniforme com a escala. Este pedido mede esse efeito com duas variantes (Parte C, item 4).

**O que a faixa é e o que não é:** ela mostra onde carros reais passam. Ela **não** é o alvo do Modelo 1, porque é outro carro, em outra velocidade (ADR 0018). Se ela ajuda o modelo, só o retreino com as três fontes vai dizer, na régua do ADR 0006.

## Parte A — Documentação (antes do código)

Em `docs/backlog.md`:

1. Na linha **"Dados externos no treino do Modelo 1"**:
   - acrescente ao Impacto: "A volta alinhada no pedido 22 é da classificação de 2024, com chuva";
   - troque o Quando "A definir" por "Em andamento: alinhamento de uma volta aceito no pedido 22; faixa de voltas secas no pedido 23. Entra no treino junto com o retreino das três fontes".
2. Na linha **"Retreinar a LSTM geradora com as três fontes"**, troque "(pedido 22, Parte B)" por "(pedidos 22 e 23)".

## Parte B — Coletar voltas secas de classificação

**Escopo:**

- **Pista:** Interlagos.
- **Anos:** 2018, 2019, 2021, 2022, 2023, 2024 e 2025. Em 2020 não houve GP.
- **Sessões:**
  - a classificação (`Q`) de cada ano;
  - a sessão classificatória da sprint, nos anos em que o calendário do FastF1 tiver: Sprint Shootout (2023) e Sprint Qualifying (2024 em diante).
  - **Cuidado:** no FastF1, `SQ` também nomeia a "Sprint Qualifying" de 2021 e 2022, que era a corrida sprint. Confirme cada sessão pelo nome e pela data no calendário. Corrida sprint não entra.

**Carregamento:** `session.load(laps=True, telemetry=True, weather=True, messages=True)`. As mensagens de direção de prova são necessárias porque a coluna `Deleted` só existe com elas.

**Filtros por volta**, nesta ordem. Conte quantas voltas caem em cada etapa, por sessão:

1. `Compound` em SOFT, MEDIUM ou HARD;
2. `IsAccurate` verdadeiro;
3. volta não apagada (`Deleted` falso). Se a sessão não tiver a informação de volta apagada, a sessão inteira fica fora, registrada com o motivo. Uma volta apagada costuma ser justamente a que passou do limite da pista, e isso empurraria a faixa para fora;
4. bandeira verde a volta inteira (`TrackStatus` igual a `'1'`);
5. sem entrada nem saída de box;
6. sem chuva: nenhum registro de `Rainfall` verdadeiro em `weather_data` entre o início e o fim da volta.

**Escolha das voltas:**

- de cada piloto, a volta mais rápida que sobrou dos filtros;
- de cada sessão, os 10 pilotos mais rápidos.
- O tempo da volta serve só para escolher e identificar. Nunca entra como dado.

**A volta de chuva de 2024** (Norris, volta 32) fica registrada à parte, como "volta de chuva", fora da faixa seca. Ela entra só na comparação da Parte C, item 6.

**O que ler:**

- **Só `X` e `Y`, dos dados de posição da volta** (`get_pos_data()`; confira o nome na versão 3.4.0). Não use `get_telemetry()`: ele interpola a posição nos instantes dos dados do carro.
- **Não leia nem salve** velocidade, pedais, marcha, rotação, DRS nem distância (ADR 0018).

**Onde fica o código:**

- Escreva a coleta em `backend/ml/external/`.
- Não altere o importador do app (`backend/core/external_references/`), que dá o contexto por curva ao coach.
- Use o mesmo cache, `data/fastf1_cache/`, que já fica fora do git. Relate o tamanho final do cache e o tempo de download.

**Rede e versão:**

- O FastF1 está fixado em 3.4.0 no `backend/requirements.txt`, que vai para o app empacotado. **Não atualize nem instale pacotes.**
- Se uma sessão não carregar, registre o erro e siga com as outras.
- Se nenhuma sessão carregar (sem internet ou bloqueio), pare e relate.
- Não busque esses dados em nenhuma outra fonte.

## Parte C — Alinhar, aceitar e formar a faixa

1. **Alinhamento de cada volta:** o mesmo método do pedido 22 (`ml/external/f1_line.py`):
   - Procrustes e ICP com uma escala só, livre, e espelho permitido, contra a linha central da geometria `0ed16f0dd2225990`;
   - projeção na grade de 2.167 pontos;
   - excesso sobre o corredor.
2. **Conferência com o pedido 22.** Passe a volta de Norris de 2024 pelo caminho novo, com os dados de posição crus. Compare com os números do pedido 22:
   - a fração fora do corredor, o p95 do excesso, a escala e a rotação;
   - a diferença de lateral ponto a ponto, com mediana e p95.

   Só relate: isso não muda nada.
3. **Critério de aceite por volta, fixado antes de rodar.** A volta entra na faixa só se:
   - a cobertura for de pelo menos 0,99 da volta, e o maior buraco entre amostras for de no máximo 80 m;
   - no máximo 10% dos pontos da grade ficarem fora do corredor, e o p95 do excesso for de no máximo 1 m. É o mesmo critério do pedido 22.

   A volta que não passa fica fora, listada com os números. Nada é ajustado depois de ver o resultado.
4. **Incerteza do alinhamento.** Calcule duas variantes para toda volta aceita. Elas nunca servem para escolher voltas.
   - **V1, escala fixa:** o decímetro nominal (0,1 m por unidade), com só rotação, translação e espelho.
   - **V2, uma transformação por sessão:** ajustada com todas as voltas aceitas da sessão juntas. A ideia supõe que as posições de uma sessão estão no mesmo sistema de coordenadas. Confira isso pela dispersão das transformações por volta dentro da sessão, com escala, rotação e translação medida no centróide.

   Por microsetor, relate a mediana e o p90 de |lateral da variante − lateral do método principal|. Marque como "faixa pouco confiável" os microsetores com p90 acima de 1 m.
5. **Faixa**, só com as voltas aceitas, pelo método principal:
   - **Mínimo fixado antes de rodar:** 20 voltas aceitas de pelo menos 3 sessões. Abaixo disso, o relatório diz "faixa não formada" e traz os números por volta.
   - **Por ponto da grade:** mediana, p10 e p90 do lateral e o número de voltas. Cada volta pesa igual.
   - **Por microsetor (60):** a mediana desses valores.
   - **Dispersão entre sessões:** por microsetor, a amplitude entre as medianas das sessões. Ela mostra se a linha mudou de um ano para outro.
6. **Comparação descritiva, só para leitura.** Nada disso muda coach, store ou critério.
   - Por microsetor, calcule a fração dos pontos em que a mediana de cada linha fica dentro de [p10, p90] da faixa. As linhas são:
     - as 13 voltas `ia` rotuladas de 04/10;
     - as voltas `humano` com equipamento `atual`.

     Use os mesmos filtros do pedido 22 e relate o número de voltas.
   - Um microsetor conta como "dentro" se pelo menos 50% dos seus pontos estão dentro.
   - Relate quantos microsetores ficam dentro, para a IA e para o piloto. Liste os 5 mais fora de cada um, com o lado (positivo à esquerda, ADR 0003) e a distância até a borda da faixa.
   - Faça o mesmo cálculo com a volta de chuva de 2024 contra a faixa seca. Ele mostra quanto a linha de chuva difere da seca.
   - Refaça a tabela "F1 − IA" e "F1 − piloto" do pedido 22 com a mediana da faixa no lugar da volta única: mediana, p90 e máximo de |Δ| por microsetor.
7. **Figuras:**
   - **A pista:**
     - a faixa p10–p90 sombreada;
     - a mediana da F1, a mediana da IA e a mediana do piloto;
     - zoom no S do Senna, no Bico de Pato e na Junção, onde o pedido 22 achou o maior excesso.
   - **Lateral × s:** a faixa, a mediana da F1, a IA, o piloto e a volta de chuva.

   Copie as duas para `docs/handoff/`.

**Testes**, sintéticos, sem internet, com um módulo FastF1 falso, como o provedor atual já permite:

- **Filtros:**
  - uma tabela falsa com uma volta de cada caso: intermediário, imprecisa, apagada, bandeira amarela, saída do box e chuva. Só a volta limpa sobra;
  - a melhor volta por piloto e o corte nos 10 mais rápidos;
  - a sessão sem a informação de volta apagada fica fora.
- **Leitura:** só `X` e `Y`.
- **V1:** recupera uma rotação e uma translação conhecidas com a escala fixa.
- **V2:** recupera uma transformação conhecida aplicada a várias linhas da mesma sessão.
- **Faixa:** p10, p50 e p90 conhecidos, e a regra de "dentro" do microsetor.
- **Critério por volta:** cobertura, buraco e corredor.

**Saídas**, fora do git, em `data/ml/externo/f1_faixa/`:

- `manifesto.json`. Para cada sessão e cada volta considerada, registre:
  - ano, sessão, piloto, número da volta, tempo e pneu;
  - a etapa do funil em que caiu;
  - os números do critério e o veredito.
- Um CSV por volta aceita, com `s`, lateral e excesso. Sem velocidade.
- `faixa.csv`, com `s`, p10, p50, p90, n e a incerteza V1 e V2.
- `resumo.json` e as figuras.

Copie `resumo.json` e as figuras para `docs/handoff/`, com o prefixo `2026-10-05_23_voltas-secas-f1_`.

**Documento novo, `docs/dados_externos_f1.md`, curto.** Ele deve dizer:

- o que entra: só a forma da linha;
- a fonte, as sessões e os anos;
- os filtros, o alinhamento, o critério e a faixa;
- os resultados, com os números;
- os limites:
  - a confusão entre escala e lateral;
  - a faixa é de outro carro, então que ela ajude o Modelo 1 é uma hipótese, testada só no retreino.

Inclua links para o ADR 0018 e para os relatórios 22 e 23. No backlog, atualize o Quando da linha "Dados externos" com o resultado ("faixa formada com N voltas de M sessões" ou "faixa não formada").

## Regras gerais

- **Nada é treinado.** Coach, store e critérios não mudam.
- **Nada da F1 além da posição:** sem velocidade, pedal ou ponto de frenagem (ADR 0018).
- Branch `etapa/f1-voltas-secas`, commits por parte, merge em `develop`. Sem push.
- Não mexa no app instalado nem em arquivos do jogo.
- Uma sessão de implementação por vez (ADR 0008).
- **Relatório** em `docs/handoff/2026-10-05_23_voltas-secas-f1_relatorio.md`, como manda o CLAUDE.md, com:
  - o pneu da volta de 2024;
  - o funil por sessão, numa tabela, com os erros de carregamento, se houver;
  - o veredito por volta;
  - a conferência com o pedido 22;
  - a incerteza V1 e V2 e os microsetores pouco confiáveis;
  - a faixa, ou o motivo de não ter sido formada;
  - a comparação do item 6;
  - os caminhos das figuras, o tamanho do cache, a saída da suíte de testes e os commits.
- Se algo do contexto não bater com o repositório, pare e registre no relatório.
