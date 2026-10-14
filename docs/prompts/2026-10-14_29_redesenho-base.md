# Pedido 29 — Redesenho, etapa 1: sistema visual, hero, base do app e leitura do CSP para a realidade aumentada

**De:** Eduardo. **Data:** 14/10/2026.
**Tipo:** front (design) e uma leitura, sem instalar nada, do que o jogo oferece para a realidade aumentada. Nenhum modelo, critério, store, rota do backend ou regra do coach muda.

**Quando começar:** depois que o pedido 28 fechar (Parte G). Este chat de design passa a ser a sessão de implementação (ADR 0008). Enquanto ele trabalha, nenhum outro chat implementa.

## Contexto

1. **Minhas decisões (14/10):**
   - o redesenho segue a **opção A** do protótipo, a escura e densa;
   - **paleta inspirada nas transmissões da F1.** Escolhi a F1, e não o WEC, porque a realidade aumentada vai ser o rádio do engenheiro;
   - **visual de vidro (glassmorphism)** nas visões do app;
   - um **hero** ao entrar no app;
   - uma **visão ao vivo** da sessão no Assetto Corsa, ligada à realidade aumentada;
   - a **realidade aumentada dentro do jogo** como o rádio dos engenheiros da F1, passando feedback ao piloto. Ela é o próximo pedido; aqui entra só a leitura da Parte A;
   - **usar a skill `frontend-design`.**
2. **Referências do redesenho:**
   - o protótipo navegável `frontend/mockups/prototipo_dashboard.html`, opção A;
   - `docs/dashboard_inventario.md`: problemas, premissas, estrutura das telas e destino de cada parte atual;
   - `docs/dashboard_visoes.md`: as 38 visões (V01 a V38) e o destino de cada uma;
   - a aba "Coleta de dados" do pedido 28.
3. **Regras que continuam valendo** (`docs/dashboard_inventario.md`, seção 4):
   - **uma fonte para cada número:** `geometry_id`, `lap_time_s` do store v2, 60 microssetores, 14 curvas (C01 a C14) e referência `volta_ia` ou `minha_melhor`;
   - **diferença medida, nunca ganho prometido** (ADR 0012);
   - **depuração só na tela Sistema;**
   - **português com acento e nomes técnicos,** o nome do produto do TCC ("Sistema de Telemetria e Otimização de Trajetórias"), tempos em M:SS,mmm e lado por extenso (ADR 0003);
   - **monitor único de 27":** durante a volta o jogo ocupa a tela. Por isso a ajuda durante a volta vai para dentro do jogo;
   - **reaproveitar o que já existe e não construir backend.** As exceções são a coleta (pedido 28) e a realidade aumentada (próximo pedido).
4. **Ordem das etapas do redesenho:**
   1. este pedido: sistema visual, hero, base e a casca da tela Ao vivo;
   2. realidade aumentada (o rádio no jogo) e a tela Ao vivo completa, depois do ADR 0020;
   3. Volta;
   4. Evolução;
   5. Sessões;
   6. limpeza do que ficar sem uso.

## Parte A — Leitura para a realidade aumentada (só leitura)

Nada é instalado, copiado ou mudado na pasta do jogo. O Cowork escreve o ADR 0020 e o pedido da realidade aumentada a partir do que você relatar.

1. **O Custom Shaders Patch (CSP):**
   - está instalado na pasta do jogo (`D:\SteamLibrary\steamapps\common\assettocorsa`)?
   - qual é a versão, e de onde ela foi lida?
   - existe a pasta `apps\lua`, e quais apps Lua já estão lá?
2. **O Content Manager:** está instalado, e em qual versão? Se não der para saber sem abri-lo, diga e eu informo.
3. **O que a API Lua do CSP oferece nesta versão.** Leia as definições que vêm com o CSP (por exemplo, o SDK Lua dentro de `extension`) e cite o arquivo de cada resposta:
   - desenhar uma janela ou um painel na tela do jogo;
   - fazer uma requisição HTTP para `127.0.0.1:8000`;
   - tocar um som ou um arquivo de áudio;
   - ler o estado do carro (posição na volta, velocidade, pedais);
   - desenhar no mundo 3D (linhas ou marcas na pista).
4. **O que o backend já entrega para o rádio:** o formato e a frequência de `/api/live/coach`, o limite de frases por volta (`MAX_PHRASES_PER_LAP`) e em que momento da volta cada frase é gerada.
5. **Voz em português:** liste as vozes de síntese de fala instaladas no Windows (por exemplo, pelo `System.Speech`, só consultando) e diga se há alguma em pt-BR.

## Parte B — Sistema visual

1. **A skill `frontend-design`:**
   - ela está em `.claude/skills/frontend-design/SKILL.md`, posta pelo Cowork; commite o arquivo neste pedido;
   - leia a skill antes de desenhar;
   - quando ela conflitar com as regras deste pedido (legibilidade, nomes técnicos, português, uma fonte por número), as regras deste pedido valem.
2. **Paleta inspirada nas transmissões da F1, sem a identidade oficial:**
   - **proibido:** logotipos, marcas, a fonte proprietária da F1 e cores de equipe. Nada que imite a F1, o WEC ou a FIA;
   - **ponto de partida,** que a skill pode refinar:
     - fundo em carbono, quase preto;
     - vermelho de destaque no tom das transmissões (por exemplo, `#E10600`);
     - branco e cinzas para texto;
   - **cores de dado do protótipo, que continuam:** freio em vermelho, acelerador em verde, parcial em amarelo, perda e ganho;
   - **cores de cronometragem** (roxo, verde e amarelo): se usar, só com o significado da F1 (roxo é a melhor de todas, verde é a sua melhor e amarelo é sem melhora), e só onde esse significado vale;
   - **perda e ganho nunca só pela cor:** sempre com o sinal e o número;
   - **tudo em variáveis de tema** (CSS e configuração do Tailwind), sem cor solta nos componentes.
3. **Tipografia:**
   - distinta e legível, com números tabulares nas tabelas e nos tempos;
   - as fontes vão como arquivos locais, com a licença junto (OFL ou equivalente), porque o app instalado funciona sem internet. As do protótipo (Barlow Condensed, IBM Plex Sans e IBM Plex Mono) servem de ponto de partida.
4. **Vidro (glassmorphism):**
   - **onde entra:** recipientes, como a navegação, o hero, os cartões, os painéis laterais, o HUD da visão de perseguição e as dicas;
   - **legibilidade:** gráficos, tabelas e mapas ficam sobre uma superfície opaca ou quase opaca dentro do vidro, para os números não perderem contraste;
   - **fundo:** com profundidade, para o vidro ter o que desfocar;
   - **acessibilidade:** respeite `prefers-reduced-transparency` e `prefers-reduced-motion`;
   - **contraste:** o texto passa no WCAG AA (4,5:1) sobre o vidro. Relate as razões;
   - **desempenho:** meça os quadros por segundo de um mapa animado com e sem o vidro e limite as camadas com desfoque.
5. **Componentes base:**
   - painel de vidro;
   - cartão de número;
   - chips e botões segmentados;
   - tabela;
   - etiqueta de estado, com os estados da Coleta (ok, ausente, parado, fora da faixa, taxa baixa);
   - dica;
   - **mensagem de rádio,** já preparada para a tela Ao vivo e para a realidade aumentada.
6. **Guia visual:** uma página dentro de Sistema com as cores, as fontes e os componentes, para revisão e para o documento do TCC.

## Parte C — Base do app

1. **Navegação e telas:**
   - **as telas:** Sessões (início, com o hero), Ao vivo, Volta, Evolução, Coleta de dados e Sistema;
   - **o que entra agora:** Volta e Evolução recebem por enquanto o conteúdo atual (Pista e Análise) dentro da casca nova. O redesenho delas vem nos pedidos seguintes;
   - **o que fica igual:** a Coleta de dados mantém o conteúdo e o comportamento, só com o visual novo.
2. **Primeiro passo do inventário** (`docs/dashboard_inventario.md`, seção 7, item 1):
   - `lang="pt-BR"` e o nome do produto no título da janela;
   - retirada dos dados fixos ou falsos da tela (inventário, problema B);
   - a depuração vai para Sistema.
3. **Espelhamento do mapa principal:**
   - corrija para o mesmo sentido do minimapa e do relevo;
   - Interlagos corre no sentido anti-horário;
   - confira com uma volta real e relate antes e depois.
4. **Hero ao entrar no app:**
   - **onde fica:** é o topo da tela Sessões, não uma tela de abertura que bloqueia o uso;
   - **na abertura:** enquanto o backend sobe (até cerca de 40 s na primeira abertura, achado 1 do pedido 28), o hero mostra o estado real pelo `/api/health`, sem barra de progresso inventada;
   - **o conteúdo:**
     - o nome do produto;
     - a pista de Interlagos desenhada com as camadas tratadas (asfalto, pintura e zebras do cache, como o mapa do app), no sentido certo;
     - a sua melhor volta traçada, com animação que respeita `prefers-reduced-motion`;
     - **os números, todos de dado real:**
       - a última sessão: data, voltas e melhor volta;
       - a sua melhor volta e a volta da IA;
       - as sessões da M1 ("n de 5", de `/api/coleta/m1/oficial`);
       - se o app está pronto para gravar;
     - **os atalhos:** Coleta de dados, Última volta e Evolução;
   - **sem dado:** o hero mostra "sem dados" e não inventa números;
   - **"IA" no texto** é só a IA do jogo.
5. **A casca da tela Ao vivo:**
   - o estado da gravação e dos canais, pelo `/api/coleta/ao-vivo`;
   - a sequência das frases do coach como mensagens de rádio, lidas de `/api/live/coach`;
   - o resto (mapa ao vivo, fantasma e rádio no jogo) vem no próximo pedido.
6. **Só rotas que já existem.** Se alguma parte precisar de rota nova, pare e relate.

## Parte D — Testes e capturas

1. **Os testes do front** (`vitest` e `tsc --noEmit`) passam. A suíte do backend não muda, porque nenhum arquivo do backend muda.
2. **Capturas da janela real do app,** sem tocar na pasta de dados real (use `AT_DESKTOP_USER_DATA_DIR`, como no pedido 28), em 1920×1080 e 2560×1440:
   - o hero subindo e o hero pronto;
   - cada tela;
   - o guia visual.

   Grave em `docs/handoff/`.
3. **A tabela de contraste** do texto sobre o vidro e o fundo, e a medida de quadros por segundo da Parte B.4.

## Parte E — Documentação

- **`docs/sistema_visual.md`:** a paleta e o porquê de cada cor, as fontes e as licenças, as regras do vidro e os componentes.
- **`docs/dashboard_inventario.md`:** acrescente, ao fim da seção 7, o que este pedido entregou de cada item.

## Regras gerais

- **Nenhum modelo, critério, store, rota do backend ou regra do coach muda.**
- **Não instale nem atualize pacotes** (npm ou pip). As fontes entram como arquivos, com a licença. Se algo pedir um pacote novo, pare e relate.
- **Não mexa no app instalado nem em arquivos do jogo.** A Parte A só lê.
- **Não gere instalador neste pedido.** O instalador do redesenho vem quando as telas estiverem prontas.
- **Nada de marca alheia:** sem logotipos, marcas ou fontes proprietárias da F1, do WEC, da FIA ou de equipes. A paleta é inspirada, não copiada.
- **Não contorne nenhuma trava:** se algo parar, pare também e registre o motivo.
- **Branch e commits:** branch `etapa/redesenho-base`, commits por parte, merge em `develop`. Sem push.
- **Uma sessão de implementação por vez** (ADR 0008).
- **Relatório** em `docs/handoff/2026-10-14_29_redesenho-base_relatorio.md`, como manda o CLAUDE.md, com:
  - a leitura da Parte A, com o arquivo de cada resposta;
  - as escolhas da Parte B (paleta, fontes e vidro), com o porquê;
  - o espelhamento antes e depois;
  - as capturas, a tabela de contraste e a medida de desempenho;
  - a saída dos testes e os commits.
- Se algo do contexto não bater com o repositório, pare e registre no relatório.
