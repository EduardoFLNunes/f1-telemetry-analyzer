# Pedido 28 — Reempacotar o app instalado com o código atual e criar a aba "Coleta de dados"

**De:** Eduardo. **Data:** 11/10/2026.
**Tipo:** engenharia (empacotamento, gravador, backend e front) e documentação. Nenhum modelo, critério, store ou regra do coach muda.

**Este pedido autoriza gerar um instalador novo do app.** Instalar continua sendo comigo (Parte F). Você não instala, não desinstala, não abre o app instalado e não grava nada em `%APPDATA%\Automobilista Telemetria`.

## Contexto

1. **O app instalado é antigo.** O instalador mais recente em `desktop/dist` é o `0.1.7-phase-16`, do commit `b1dc250`, de 25/08. Ele é anterior aos pedidos 10 a 27. Por isso:
   - não grava o indicador de IA nem o `carModel`, e as sessões precisaram de anotação à mão;
   - não grava os canais do pedido 18: guinada, velocidades no referencial do carro, temperatura e distribuição dos freios, temperaturas da superfície do pneu e a embreagem certa.
2. **As 3 sessões que gravei nele depois do pedido 18** (05/10 20:33, 08/10 23:56 e 10/10 09:57) não contam para a M1. Pela regra da seção 6 de `docs/modelo_fisico_m0.md`, só contam sessões humanas com `yaw_rate`, `velocity_long` e `velocity_lat`. Hoje são 0 de 5.
3. **Depois deste pedido, vou gravar as sessões de treino pelo app instalado.** Quero ver, antes, durante e depois de cada sessão, se a gravação tem o que os modelos precisam.
4. **O que já existe e deve ser reaproveitado:**
   - `/api/runtime/status`, `/api/recording/status`, o cartão "Estado da coleta" da `HomePage` e a `LiveSessionStrip`;
   - o painel de versão (`desktop/version-service.js` e `build-info.json`);
   - o inventário de canais do pedido 18 (`ml.scripts.inventario_canais`) e as faixas que ele mediu (`docs/handoff/2026-10-04_canais-fisicos_inventario.json`);
   - os portões de qualidade (`backend/ml/preprocessing/quality.py`) e os canais de cada volta no meta do store v2 (`canais_por_volta`).
5. **Fatos do empacotamento que já conheço:**
   - **O backend é um `--onefile` do PyInstaller** e se extrai a cada abertura em `%TEMP%`, cerca de 0,37 GB. Em 08/10, com 1,84 GB livres no C:, a extração falhou e a sessão não foi gravada (relatório de 10/10, `docs/handoff/2026-10-10_chat_anotacao-sessoes-08-10-e-10-10_relatorio.md`).
   - **O coach empacotado não acharia o modelo.** No app empacotado, o backend procura os modelos na pasta de recursos do Electron, e o `extraResources` só leva `*.optimal.json`. O coach atual usa `data/reference_models/vhe_interlagos.json` e `vhe_interlagos.geometry.json` (seção 8 de `docs/coach_aprendizado.md`).
   - **A referência do coach é escolhida pela variável `AT_COACH_REFERENCE`,** que o app instalado não tem.
   - **A pasta de dados** (`%APPDATA%\Automobilista Telemetria`) vem do `productName`, e o ML lê as gravações de lá.

## Princípios

- **O app instalado roda o mesmo código de `develop`.** O que muda no pacote são só caminhos.
- **Nada muda no lugar dos dados.** O `productName`, o `appId` e a pasta de dados ficam como estão, e as gravações continuam na mesma pasta. A troca do nome do produto fica para o redesenho do dashboard.
- **Uma lista só do que os modelos precisam** (Parte B). A aba, a conferência depois da sessão e os testes leem dessa lista. Nada é copiado à mão no front.
- **A aba só lê:** não muda gravação, store, modelo nem critério.

## Parte A — Conferências antes do código

Pare e registre no relatório se alguma destas não bater:

1. **O gravador do repositório grava** os campos do pedido 18 (seção 2 de `docs/modelo_fisico_m0.md`), o indicador de IA e o `carModel`. Diga em que teste isso está coberto.
2. **Como o backend empacotado acha o modelo e a geometria do coach:** a raiz de recursos, a raiz de dados e a ordem de busca. Relate.
3. **Onde o Electron e o backend gravam** quando empacotados: dados, logs, configuração e a pasta de usuário do Electron. Isso é a base do teste da Parte E.3.
4. **O build-info** marca a árvore como suja quando há arquivo não rastreado? Se marcar, relate quais arquivos são e siga. O build não depende deles.

## Parte B — Registro do que os modelos precisam

Crie um módulo com a lista do que os modelos precisam. Por exemplo, `backend/core/coleta/requisitos.py`, ou outro lugar que faça sentido no código. Para cada item:

- o nome técnico e o campo na amostra gravada (por exemplo, `carPhysics.motion.localAngularVelocity.y`);
- a coluna do store v2, quando houver (por exemplo, `yaw_rate`);
- quem usa: coach, store v2 e LSTM, origem da volta, limites de pista, modelo do carro (M1) e bloco `tecnica` do relatório de evolução;
- a unidade, a faixa plausível, o preenchimento mínimo e se o item é obrigatório na regra da M1. As faixas saem do inventário do pedido 18, com uma margem documentada.

**Grupos, no mínimo** (os campos exatos saem do gravador e do store):

1. **Base:** cronômetro do jogo, número da volta, distância na volta, posição x e z, velocidade, acelerador, freio, volante, marcha e rotação.
2. **Origem da volta:** o indicador de IA, o `carModel` e a pista.
3. **Limites de pista:** `tyresOut` e `offTrack`.
4. **Modelo do carro (M1):**
   - **obrigatórios na regra da contagem:** `yaw_rate`, `velocity_long` e `velocity_lat`;
   - **os outros:** temperatura e distribuição dos freios, temperaturas do núcleo e da superfície do pneu, carga, escorregamento, pressão, curso da suspensão, `accG` e embreagem.

**Teste:** toda coluna que o store v2 materializa e todo canal da regra da M1 estão no registro, e todo item do registro aponta para um campo que o gravador grava. Um não pode sair do lugar sem o teste quebrar.

## Parte C — Reempacotamento

1. **Versão** maior que todas as de `desktop/dist`. Sugestão: `0.3.0-coleta-modelos`. Atualize também o rótulo de branch do `main.js` (`AT_DESKTOP_BRANCH_NAME`, hoje "Phase 16").
2. **Backend em `--onedir`,** para não haver extração a cada abertura.
   - Atualize o `.spec`, o `build_backend.ps1`, o `extraResources` e a busca do executável no `main.js`. A ordem de busca continua a mesma, com o caminho novo.
   - Se o `--onedir` quebrar algo que não dá para resolver neste pedido, mantenha o `--onefile` e relate o motivo.
3. **Coach no app instalado:**
   - **o modelo e a geometria:** o coach lê `vhe_interlagos.json` e `vhe_interlagos.geometry.json` da pasta `data/reference_models` do repositório, só lendo. O caminho fica numa configuração do app, editável na aba. O padrão é o repositório, se ele for encontrado (`AT_REPO_PATH` já existe no `main.js`).
   - **por que não copiar:** o modelo não é copiado para dentro do pacote nem para `%APPDATA%`, porque ele muda a cada `atualizar_coach`.
   - **sem os arquivos ou com outro `geometry_id`:** o coach fica calado, como hoje, e a aba diz por quê.
   - **a referência:** a escolha entre `volta_ia`, `minha_melhor` e coach desligado vira uma configuração na aba. Ela substitui a variável `AT_COACH_REFERENCE` e o "renomeie o arquivo para treinar sem o coach" (item 7 da seção 8). A variável continua valendo no app de desenvolvimento.
4. **Origem do dado:** o `metadata.json` de cada sessão nova passa a ter a versão e o commit do app, sem mudar os campos que já existem. Confirme que o inventário e o store v2 continuam lendo.
5. **O build sai de `develop`,** depois do merge da branch deste pedido.

## Parte D — Aba "Coleta de dados"

Uma aba nova no menu do app atual. No redesenho, ela ocupa o lugar da tela "Antes de pilotar" (`docs/dashboard_inventario.md`, seção 5). É a única exceção à regra de não construir backend do redesenho, porque conferir a gravação exige ler a gravação.

**1. Antes de pilotar:**

- a versão e o commit do app;
- a pasta onde ele grava e o espaço livre nesse disco, em amarelo abaixo de 5 GB e em vermelho abaixo de 2 GB. A sessão de 41 min de 10/10 ocupou 0,53 GB;
- o estado do backend e da conexão com o jogo, mais o carro e a pista detectados, com aviso se não forem `rss_formula_rss_3_v6_2026` e `vhe_interlagos`;
- o coach: a referência escolhida, se o modelo foi achado, se o `geometry_id` bate, a data do modelo e quantas voltas minhas ele tem.

**2. Durante a sessão,** ao vivo, numa janela de alguns segundos:

- uma tabela por grupo da Parte B, com o estado (ok, ausente, parado ou fora da faixa), a taxa real em Hz e o último valor com a unidade. "Parado" é um valor que não muda com o carro andando, como a embreagem em 0 das gravações antigas;
- o indicador de IA em destaque, porque ele decide a origem da volta.

**3. Depois de cada volta e no fim da sessão:**

- **por volta:**
  - o tempo, em M:SS,mmm;
  - se ela passaria nos portões de qualidade, pelas mesmas funções do pipeline (`quality.py`), e o motivo quando não passar;
  - o preenchimento de cada grupo;
- **no fim da sessão:** "esta sessão conta para a M1?", pela regra da seção 6 de `docs/modelo_fisico_m0.md`, e o que falta quando não conta. Para esta prévia:
  - sessão humana é a que tem o indicador de IA desligado em todas as voltas;
  - os canais obrigatórios precisam estar preenchidos em pelo menos 95% dos pontos das voltas válidas, o limiar das checagens do pedido 18;
- **o veredito é uma prévia.** A contagem oficial continua no `atualizar_coach` (store v2). Quando o caminho do repositório estiver configurado, a aba mostra também a contagem oficial, lida do store v2 ("n de 5");
- **onde fica o resultado:** a conferência de cada sessão é gravada pelo app fora da pasta de gravações, por exemplo em `verificacoes/` dentro da pasta de dados. Confirme que nenhum leitor do ML a confunde com uma sessão.

**4. Backend:** um grupo de rotas (por exemplo, `/api/coleta/...`) lendo o registro da Parte B. Onde uma rota existente já dá a informação, use-a.

**5. Textos** em português com acento, nomes técnicos e tempos em M:SS,mmm.

## Parte E — Testes e conferência sem o jogo

1. **Testes sintéticos:**
   - o registro contra o store v2 e a regra da M1 (Parte B);
   - o estado de cada canal: ausente, parado, fora da faixa e taxa baixa;
   - o veredito da volta pelos portões;
   - o veredito da sessão: humana e com os canais conta; com volta da IA, não conta; sem a guinada, não conta.
2. **Conferência nas gravações reais,** só lendo: rode a conferência de fim de sessão em `2026-10-10_09-57-09` (app instalado) e numa sessão do repositório de 04/10. O esperado é "não conta para a M1: faltam a guinada e as velocidades no referencial do carro". Relate a tabela completa.
3. **Teste do pacote sem instalar:**
   - rode o app a partir de `desktop/dist/win-unpacked`, ou o backend empacotado, com o app instalado fechado (porta 8000);
   - redirecione dados, logs e a pasta de usuário do Electron para uma pasta temporária do repositório, para nada ser gravado em `%APPDATA%\Automobilista Telemetria`. Se não der para isolar tudo, pare e relate antes de rodar;
   - confirme:
     - o `/api/health` e a aba abrindo;
     - o coach achando o modelo pelo caminho configurado;
     - o tempo de abertura;
     - nenhuma extração em `%TEMP%`, se o `--onedir` entrou.
   - Capturas da aba: com uma gravação real em modo de reprodução, se o app já tiver esse modo; se não tiver, só da parte "Antes de pilotar" e do resultado da conferência da E.2.
4. **A suíte `backend/tests` e os testes do front** continuam passando.

## Parte F — Instalação e sessão de teste (comigo)

Pare aqui. Grave o relatório parcial com o caminho, a versão, o tamanho e o sha256 do instalador, e estes passos para mim:

1. Fechar o jogo e o app instalado, inclusive na bandeja.
2. **Recomendado:** copiar `%APPDATA%\Automobilista Telemetria\data\recordings` para outro disco antes de instalar.
3. Rodar o instalador novo por cima do atual, na mesma pasta. A fase 12.6 mostrou que a instalação preserva `%APPDATA%`.
4. Abrir o app, ir à aba "Coleta de dados", conferir o caminho do repositório e escolher a referência do coach.
5. Abrir o Assetto Corsa em Interlagos com o `rss_formula_rss_3_v6_2026` e fazer de 3 a 5 voltas sem a IA, olhando a aba antes e depois.
6. Fechar o app e avisar: "instalei e gravei a sessão de teste".

## Parte G — Conferência da sessão de teste (depois do meu aviso)

1. Rode o `atualizar_coach` padrão (incremental), com o app fechado.
2. **Confirme no store v2** que a sessão nova tem:
   - `yaw_rate`, `velocity_long`, `velocity_lat` e a temperatura dos freios em pelo menos 95% dos pontos das voltas válidas;
   - o `carModel`, o indicador de IA, a versão e o commit no `metadata.json`;
   - a origem pelo indicador (`origem_fonte` igual a `indicador`), sem precisar de anotação.
3. **A contagem oficial da M1** vai para 1 de 5, se a sessão for humana e passar.
4. **Compare o veredito da aba com o do store.** Se não baterem, relate e pare.
5. Complete o relatório.

## Parte H — Documentação

- **`docs/coach_aprendizado.md`, seção 8:** vira "Como gravar uma sessão de treino", pelo app instalado. O caminho do app de desenvolvimento fica como alternativa.
- **`desktop/README.md` e `backend/packaging/README.md`:** o `--onedir` (ou por que não entrou), o caminho do modelo do coach e a versão.
- **`docs/modelo_fisico_m0.md`, seção 6:** o app instalado foi reempacotado, e como a contagem é conferida agora.
- **`docs/backlog.md`:** se a Parte G passar, tire a linha "O app instalado não grava o indicador de IA e não vai gravar os canais físicos do pedido 18 até ser reempacotado".
- **Commit só de documentação** com os arquivos do Cowork que estão fora do git: `docs/dashboard_inventario.md`, `docs/dashboard_visoes.md`, `docs/imagens/visoes/` e `frontend/mockups/prototipo_dashboard.html`. Os outros não rastreados ficam como estão.

## Regras gerais

- **Não mexa no app instalado nem em arquivos do jogo.** Gerar o instalador é permitido; instalar é comigo. O teste do pacote usa uma pasta temporária.
- **Não mude o `productName`, o `appId` nem a pasta de dados.**
- **As gravações são só lidas,** nas duas pastas.
- **Nenhum modelo, critério, store ou regra do coach muda.** No coach, muda só de onde ele lê o modelo e como a referência é escolhida.
- **Não instale nem atualize pacotes.** Se o build pedir, pare e relate.
- **Não contorne nenhuma trava:** se algo parar, pare também e registre o motivo.
- **Branch e commits:** branch `etapa/reempacotamento-e-coleta`, commits por parte, merge em `develop` e build a partir de `develop`. Sem push.
- **Uma sessão de implementação por vez** (ADR 0008).
- **Relatório** em `docs/handoff/2026-10-11_28_reempacotamento-e-coleta_relatorio.md`, como manda o CLAUDE.md, com:
  - as conferências da Parte A;
  - a tabela do registro da Parte B;
  - as mudanças do empacotamento, com o `--onedir` ou o motivo de ele não ter entrado;
  - o caminho, a versão, o tamanho e o sha256 do instalador;
  - os resultados da Parte E, com as capturas;
  - a saída das suítes e os commits;
  - na parada da Parte F, os passos para mim; depois da Parte G, o resultado da sessão de teste.
- Se algo do contexto não bater com o repositório, pare e registre no relatório.
