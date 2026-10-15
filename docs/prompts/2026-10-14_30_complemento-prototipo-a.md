# Pedido 30 — Complemento do pedido 29: implementar as telas do protótipo A agora

**De:** Eduardo. **Data:** 14/10/2026.
**Tipo:** complemento do pedido 29, que está em andamento. Continue na mesma branch (`etapa/redesenho-base`) e no mesmo relatório.

## Por que este complemento

A minha intenção era implementar o protótipo A junto com o sistema visual. O pedido 29 deixou a organização das telas Volta, Evolução e Sessões para pedidos seguintes, e isso fica corrigido aqui. O resto do pedido 29 continua valendo:

- a paleta e o vidro;
- o hero;
- a casca da tela Ao vivo;
- a leitura do CSP;
- o espelhamento do mapa;
- as regras gerais.

A realidade aumentada passa a ser o pedido 31.

## 1. O protótipo A é a referência de cada tela

- **A referência:** `frontend/mockups/prototipo_dashboard.html`, opção A (escura e densa).
- **Prevalece o protótipo:** na organização, na densidade, no conteúdo e no comportamento de cada tela.
- **Prevalece o pedido 29:** nas cores, nas fontes e no vidro.
- **Os dados:** os números vêm das rotas do app, nunca do JSON embutido no protótipo. Sem dado, a tela diz "sem dados".

## 2. Textos

- Todo texto visível fica em português, com acento e nomes técnicos.
- O cabeçalho mostra o nome do produto ("Sistema de Telemetria e Otimização de Trajetórias"). Saem "MOTORSPORT INTELLIGENCE WORKSTATION" e os rótulos em inglês da tela Pista, como "LAP TIMING", "VEHICLE STATE", "COMPARE", "AI COACHING" e "LAP COMPARISON".
- O menu fica com as telas do pedido 29: Sessões, Ao vivo, Volta, Evolução, Coleta de dados e Sistema. Pista e Análise deixam de existir como telas. O que sobra delas segue o destino da seção 6 de `docs/dashboard_inventario.md`.

## 3. As telas

1. **Sessões:**
   - o hero do pedido 29;
   - a lista de sessões, com uma faixa de pontos por sessão (uma marca por volta válida);
   - o gráfico da mediana e da melhor volta por sessão, com o critério do ADR 0015.
2. **Volta,** como na opção A do protótipo:
   - **a barra de contexto:** sessão, volta, tempo em M:SS,mmm e a diferença para a referência;
   - **a escolha** da sessão, da volta e da referência (`volta_ia` ou `minha_melhor`);
   - **a "Volta com fantasma"**, descrita na seção 8 de `docs/dashboard_visoes.md`:
     - câmera próxima de 80, 150 ou 400 m, com a opção de girar com o carro;
     - o traçado colorido pelo pedal;
     - o fantasma posicionado pelo tempo, por curva ou na volta inteira;
     - o relevo no canto superior direito e a pista inteira no inferior direito;
     - a leitura dos dois carros e o replay;
   - **o mapa dos 60 microssetores,** colorido pela diferença;
   - **a tabela das 14 curvas;**
   - **os traços:** diferença acumulada por distância em metros, mais velocidade, acelerador e freio.
3. **Evolução:**
   - a mediana e a melhor volta por sessão;
   - a perda por curva entre sessões, com a faixa de confiança;
   - a técnica de pilotagem por curva (bloco `tecnica`).
4. **Coleta de dados:** fica como no pedido 28, com o visual novo.
5. **Ao vivo:** fica como no pedido 29.
6. **Sistema:** a `DiagnosticsPage`, a depuração do mapa e o guia visual.

## 4. A pista e as posições

Estes cuidados já foram acertados no protótipo em 10/10:

- **A pista desenhada** são as camadas tratadas que o mapa do app já usa, vindas do cache: asfalto, pintura classificada e zebras. Nunca a borda montada com a linha central e a largura do modelo.
- **O sentido** é o anti-horário, o mesmo do minimapa e do relevo, na projeção certa.
- **A posição do carro e do fantasma** é a da geometria oficial: a linha central oficial mais o deslocamento lateral do store v2. A distância `s`, as 14 curvas e os 60 microssetores também são os da geometria oficial.

## 5. De onde vêm os dados

Esta é a exceção à regra de não construir backend, e só para leitura. Os números já são calculados pelo `atualizar_coach`; o backend só os entrega.

- **Só leitura:** nenhuma rota nova calcula nada. Elas leem arquivos que já existem, na pasta do repositório configurada na Coleta de dados (pedido 28):
  - os JSONs de `data/ml/evolucao/` (`resumo.json` e `sessao_*.json`);
  - as linhas de uma volta no store v2 (`laps_grid_v2.parquet`), com `s`, `lateral`, `elapsed_s`, velocidade, acelerador e freio;
  - o modelo do coach, para saber qual volta é cada referência.
- **O que já existe continua:** onde uma rota existente já entrega o dado (pista, sessões, replay e frases do coach), use-a.
- **Projeção:** se alguma tela precisar de dado na projeção do runtime, e não na geometria oficial, pare e relate.

## 6. Conferência contra o protótipo

1. **A mesma volta nos dois:** use a volta 8 da sessão de 05/10 às 20:33 contra a volta da IA. Tire capturas lado a lado, app e protótipo A, de cada tela.
2. **Os números da tela Volta batem com os do protótipo,** porque vêm das mesmas fontes:
   - o tempo e a diferença;
   - a perda por curva;
   - a diferença por microssetor;
   - a diferença no modo por curva.

   Relate qualquer diferença e a causa.
3. **As capturas** vão em 1920×1080 e 2560×1440, como no pedido 29.

## Regras

- **As do pedido 29 continuam,** com uma mudança: as rotas de leitura da seção 5 passam a ser permitidas, com teste.
- **Nenhum modelo, critério, store ou regra do coach muda.**
- **Não gere instalador.** Ele vem quando as telas estiverem aprovadas.
- **No relatório do pedido 29,** uma seção própria para este complemento, com:
  - as capturas lado a lado;
  - a tabela de conferência dos números;
  - as rotas novas;
  - o que ficou diferente do protótipo, e por quê.
