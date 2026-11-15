# Pedido 52 — O engenheiro que acompanha a volta

**De:** Eduardo. **Data:** 15/11/2026.
**Tipo:** rádio, coach ao vivo, app do jogo (realidade aumentada), registro das dicas, leitura (só leitura) dos arquivos da pista, documentação e testes, com uma sessão minha no jogo no fim. O Modelo 1, o Modelo 2 (os detectores e o modelo leve), o store v2 e a volta do modelo não mudam.

**Quando começar: agora, na pasta principal** (`C:\Users\Dokas\Desktop\f1-telemetry-analyzer`), numa branch nova a partir de `develop`. A pasta do 47 e a do 48 não são tocadas. Temos pouco tempo: siga as partes sem parar, salvo onde este pedido manda parar.

### Parte 0 — A pasta

1. **Confira a pasta principal:** em `develop`, com o merge do 51 (`c4869295`), sem mudança sem commit (só o texto deste pedido). O app do repositório e o `acs.exe` fechados.
2. **A branch nova:**
   ```powershell
   git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer switch -c etapa/engenheiro develop
   ```
3. **O texto deste pedido** é o primeiro commit.
4. **O processador:** antes de cada conta pesada, confira se o `acs.exe` está aberto. Se estiver, espere.

## Contexto

1. **O que é o engenheiro:** a parte do Modelo 2 que leva o diagnóstico ao piloto durante a volta (ADR 0018: o rádio é o caminho do Modelo 2 até o piloto). O Modelo 1 diz onde e quanto (a volta do modelo, ADR 0032); o Modelo 2 diz por quê (as causas que o rádio do 45 já mede); o engenheiro diz o que fazer, antes da curva, por um marco que se vê na pista.
2. **As minhas decisões de 14/11 e 15/11:**
   - **toda curva com perda é avisada,** sem limite de quantidade;
   - **a referência é a volta do modelo** (o arquivo `data\reference_models\vhe_interlagos.volta_do_modelo.json`, do pedido 51). Num trecho em que eu for mais rápido que ela, a referência daquele trecho é a minha melhor passagem. A volta da IA do jogo nunca é referência;
   - **o aviso vem durante a volta, antes da curva, pelo marco da pista e depois os metros.** Exemplo: "Curva 1: freie 10 metros depois da placa de 100". Não tenho trena no carro: metros só contados a partir de um marco, nunca "xx metros antes da curva";
   - **a voz faz duas coisas:** o aviso de onde frear, antes da curva, e o feedback das curvas, nas retas;
   - **o bipe fica para a versão 2;**
   - **a janela durante a volta é a realidade aumentada** (o app do jogo);
   - **na volta lenta, a janela mostra a lista inteira.** Volta lenta: 5,0 s ou mais atrás da melhor da sessão naquele ponto, ou com rodada, incompleta, de saída ou de entrada nos boxes;
   - **os marcos vêm dos arquivos da pista,** sem sessão de marcação. Eu só vou ao jogo para o teste do fim.
3. **A exceção da pista neste pedido:** os arquivos de `D:\SteamLibrary\steamapps\common\assettocorsa\content\tracks\vhe_interlagos` podem ser **lidos** (o `vhe_interlagos.kn5` e o `obj_extra.kn5`). Nada é escrito na pasta da pista nem na do jogo. O `data.acd` e os arquivos do carro nunca são abertos.
4. **Os marcos que o Cowork leu em 15/11** (para a sua conferência; s na geometria oficial `0ed16f0dd2225990`; lado pelo vetor normal, que aponta para dentro do circuito, ou seja, positivo é a esquerda):
   - **as placas de freada** (o número vem da coluna da textura que a face usa: `DISTMARKERB.DDS` e a metade de baixo de `DISTMARKER.DDS` têm 50, 100 e 200 em colunas de 1/4 da largura): 200, 100 e 50 em s 16, 114 e 156 (direita, C01); 200, 100 e 50 em 1.141, 1.227 e 1.273 (direita, C04); 100 e 50 em 1.858 e 1.903 (esquerda, C06); 100 e 50 em 3.109 e 3.154 (esquerda, C12);
   - **as placas do DRS** (`DISTMARKERDRS.DDS`): 741 e 3.890, à direita;
   - **as passarelas** (`ads_brg*`, `ADVERT_OV01/02` e `OVERHEADAD_DETAILS`, de um lado ao outro da pista): 940 e 3.782; **o pórtico da largada** (`STARTLIGHT_POLES`): 3;
   - **os postos de bandeira** (`marshall01` a `marshall20`, no `obj_extra.kn5`): só os 8 a até 14 m da linha central (175, 865, 1.201, 3.513, 3.647, 3.789, 3.993 e 4.327); os outros 12 ficam de fora;
   - **as zebras** (materiais `RMB*`): 31 na pista, com começo, fim e lado.
5. **Os blocos de voz que o Cowork mediu** pela volta de referência (o tempo entre a retomada do trecho anterior e 1,0 s antes da primeira ação do trecho): reta dos boxes, de 3.660 a 44 m (10,0 s); reta oposta, de 556 a 1.141 m (8,9 s); antes da C06, de 1.540 a 1.848 m (5,0 s); antes da C12, de 2.928 a 3.071 m (2,5 s); antes da C14, de 3.376 a 3.517 m (2,6 s). No miolo, da C07 à C13, nenhum intervalo passa de 1,5 s. Refaça a conta com a volta do modelo.
6. **O que o rádio já tem e continua** (pedidos 31 a 45, ADRs 0021 e 0027): as frases do coach depois da curva, o resumo e a análise, com as causas, as unidades, "contra quem", os limites de 7,3, 8,0 e 8,8 s, a ordem do corte, a fila de uma fala por vez, o rádio calado nas voltas da IA, a voz Microsoft Daniel a 1,4x e as janelas do app do jogo.

## Parte A — Registrar antes (ADR 0033)

Escreva o **ADR 0033, "O engenheiro que acompanha a volta"** (confira o número) e commite-o antes do código. Ele fixa:

1. **A lista da volta:** ao cruzar a linha, os 15 trechos do ADR 0030 são comparados com a referência; entra na lista todo trecho com perda acima do ruído do trecho (o desvio dos tempos daquele trecho nas 7 voltas do bloco 4 do pedido 50, calculado e gravado antes de o rádio ser ligado). Cada trecho leva a causa principal (as medidas do 45: freada cedo, freada leve, mínima baixa, acelerador tarde, marcha acima, traçado aberto) e o ponto da dica. Trechos sem medida (volta incompleta, com rodada) ficam fora. Uma dica não aplicada continua na lista até ser aplicada.
2. **Os pontos da referência,** tirados da volta do modelo: a freada (o freio passa de 0,15, a regra do relatório de evolução), a entrada (`pontos_de_linha_s` do ADR 0030) e a retomada. Num trecho em que a minha melhor passagem for mais rápida, os pontos vêm dela.
3. **Os marcos:** a tabela da Parte B, com tipo, s, lado e, nas placas, o valor.
4. **A frase:** a ação pela causa (freada cedo ou leve: "freie"; mínima baixa ou traçado: "vire"; acelerador tarde: "acelere"; marcha: a marcha da referência no fim, "em segunda"), e o ponto pelo marco de menor custo:
   - **a janela:** para frear, o marco serve se estiver até 150 m antes do ponto ou até 60 m depois; para virar e acelerar, 80 m antes ou 40 m depois;
   - **o custo:** `d` (o ponto menos o marco, em metros) quando o marco vem antes; `1,5 × |d|` quando vem depois;
   - **o bônus:** uma placa de freada vale 15 m a menos para frear; o começo ou o fim de uma zebra, 10 m a menos para virar e acelerar;
   - **o empate:** o marco de menor s;
   - **o texto:** com `|d| < 5 m`, "freie na placa de 100"; senão, `|d|` arredondado a 5 m: "freie 10 metros depois da placa de 100", "vire 15 metros antes do começo da zebra à direita". Zebras e postos levam o lado;
   - **sem marco na janela:** a frase fica só na janela, com a marca desenhada (item 7).
5. **A voz** (decisão de 15/11):
   - **o aviso de freada:** só nos trechos da lista em que a referência freia. Ele começa em `s_fala = s_freada − v × (t_frase + 1,0 s)` e acaba pelo menos 1,0 s antes da freada. Os trechos sem bloco que caiba a frase ficam só na janela;
   - **o feedback das curvas nas retas:** a frase do coach, o resumo e a análise do 45 usam o começo de cada bloco, na variante que couber antes da reserva dos avisos, e esperam o bloco seguinte se nenhuma couber. Os limites e a ordem do corte não mudam;
   - **a prioridade:** o aviso de freada nunca é cortado nem adiado pelo feedback;
   - nunca dentro de uma curva, nunca por cima de outra fala, nunca na volta de saída dos boxes.
6. **A realidade aumentada:** a janela do engenheiro, no app do jogo, mostra a frase de cada trecho da lista (os de voz e os sem voz) de `s_fala` até o ponto da ação.
7. **A marca na pista:** onde a API do CSP permitir, a marca do ponto da ação desenhada no asfalto, em 3D, na cor do fantasma, nos trechos da lista. Se a API instalada não tiver o que é preciso, a janela mostra a contagem 3-2-1 até o ponto, pela distância e pela velocidade. O app do jogo passa a desenhar na pista: o ADR 0021 ganha uma linha por isso.
8. **A conferência da dica:** aplicada se a freada ficou a ±10 m do ponto dito, a mínima a ±5 km/h, a retomada a ±10 m. Na volta rápida, a janela mostra só o sinal por trecho ("C01 aplicada", "C04 não"); na volta lenta, a lista inteira com os valores ("C01: freou a 98 m do marco, dito 100").
9. **A acurácia da volta:** "2 de 3 avisos aplicados", na janela, e no resumo quando couber.
10. **O que o engenheiro nunca diz:** nada sem medida (ADR 0012); nenhum conselho de setup; a volta da IA do jogo nunca é referência (ADR 0032).

## Parte B — Os marcos da pista (só leitura)

1. **A leitura:** com o leitor de kn5 que o projeto já tem (o do cache da superfície), leia o `vhe_interlagos.kn5` e o `obj_extra.kn5` **sem escrever nada** na pasta da pista. Separe cada placa pelas faces ligadas dentro da malha (as placas estão juntas numa malha por material) e leia o valor pela coluna da textura da face da frente. Projete o centro de cada marco na geometria oficial (s e lado).
2. **A tabela** vai para um arquivo do projeto, ao lado dos outros da pista, com o sha256 dos kn5 lidos e o `geometry_id`. Siga a regra de dados do 51: o que fica fora do git vai para o instalador pelo mesmo filtro do `extraResources`.
3. **A conferência, sem jogo:**
   - os marcos do contexto, item 4, a até 2 m em s; um que faltar ou sobrar é relatado;
   - cada conjunto de placas em ordem decrescente antes de uma freada da volta do modelo;
   - as placas e as passarelas desenhadas sobre o `map.png` da pista, numa figura do handoff.
4. **A frase de cada trecho:** a tabela dos 15 trechos com a frase de freie, de vire e de acelere, pela regra da A.4, contra a volta do modelo. As frases que soarem estranhas para um piloto (por exemplo, acelerar antes de virar) são marcadas no relatório, e eu decido.

## Parte C — O engenheiro no rádio e no app do jogo

1. **A lista da volta, os pontos, as frases e a conferência,** pela Parte A.
2. **Os blocos de voz** refeitos com a volta do modelo; a reserva dos avisos no fim de cada bloco; o feedback no começo.
3. **O molde da frase de aviso:** "Curva N: <frase>.", com a duração medida com a voz do projeto (Microsoft Daniel a 1,4x) antes de entrar no código. O relatório traz a duração de cada aviso possível dos 15 trechos e quais cabem no bloco.
4. **A janela do engenheiro** no app do jogo (uma janela nova, ligada e desligada na barra de apps, como as outras quatro), e a marca na pista ou a contagem (A.7), conferida pelo `conferir_lua.py` contra o `lib.lua` do SDK.
5. **O registro:** cada aviso grava a volta, o trecho, a causa, a frase, o `s_fala`, se foi pela voz ou só pela janela, se foi aplicado, e a perda daquele trecho nas voltas seguintes. Esse registro é a entrada do protocolo de avaliação e da tela Volta (pedido 53).
6. **As versões:** o app do Windows `0.9.0-engenheiro`; o app do jogo 0.7.0.

## Parte D — As conferências, sem jogo

1. **O rádio fora do tempo real** (o script do 51) nas sessões de 13/10, 18/10, 21/10 e 12/11, com o engenheiro ligado. Por sessão: os avisos planejados e entregues (voz e janela), a folga de cada aviso até a freada, o feedback entregue antes e depois, as falas que mudaram de bloco, nenhuma acima do limite.
2. **As prévias em HTML** da janela do engenheiro e da marca na pista, na C01 e na C06.
3. **Os testes,** com dados sintéticos: a separação das placas e o valor pela textura; a projeção e o lado; a regra da frase (a janela, o custo, o bônus, o arredondamento); a reserva dos blocos; a conferência da dica; a volta lenta (5,0 s); a troca da referência do trecho pela minha melhor passagem.
4. **A suíte do backend, os testes do front, o `tsc` e o `conferir_lua.py`.**

## Parte E — O teste no jogo, comigo

1. **O roteiro:** uma sessão de até 45 minutos, eu dirigindo, com o app do repositório aberto (backend na porta 8000) e o app do jogo 0.7.0 instalado pelo `instalar.ps1`, que eu rodo. Pelo menos 10 voltas, na pista original, com o preset de sempre.
2. **Eu aviso: "rodei o engenheiro".**
3. **Depois:** os avisos dados e entregues, a folga até a freada, os aplicados, a perda nos trechos avisados nas voltas seguintes (só relatada: o veredito é do protocolo de avaliação), o FPS com a janela e a marca ligadas, os logs do CSP e as minhas anotações.

## Parte F — Documentação e merge

- **ADR 0033,** com a linha no índice; **ADRs 0021, 0027 e 0032:** uma linha de atualização cada.
- **`docs/realidade_aumentada.md`:** uma seção "O engenheiro que acompanha a volta"; **`docs/app_para_producao.md`:** a 0.9.0.
- **`docs/backlog.md`:** não edite; liste os itens no relatório.
- **O merge em `develop`** depois do teste no jogo e da conferência. **O instalador 0.9.0** depois do merge, e a instalação só com o meu "pode instalar".

## Regras gerais

- **Nenhuma regra muda depois de ver os números.** O ADR 0033 é commitado antes do código.
- **Não invente resultados.** O que uma fonte não confirma é "não confirmado".
- **Da pista, só a leitura do contexto, item 3.** Não escreva na pasta do jogo: quem roda os scripts sou eu (ADR 0020).
- **As gravações só são lidas.** Não apague, não mova e não copie nenhuma, nem entre a pasta do app instalado e o repositório.
- **Não instale nem atualize pacotes.** Se algo pedir pacote novo, pare e relate.
- **Não contorne nenhuma trava:** se algo parar, pare também e registre o motivo. A trava do store v2 do pedido 51 não é deste pedido.
- **Branch e commits:** `etapa/engenheiro`, a partir de `develop`, na pasta principal; o texto deste pedido é o primeiro commit; o ADR 0033 antes do código; commits por parte.
- **Cópia no GitHub (vale para todo pedido):**
  - depois dos commits de cada parte, envie a branch do pedido ao `origin`; depois do merge, envie `develop`;
  - só envios que não reescrevem o remoto (branch nova ou avanço simples). Nunca `--force` nem `--force-with-lease`;
  - `main` e as tags não vão neste pedido;
  - antes do primeiro envio, confira que nada acima de 50 MB, nenhum segredo, nenhuma gravação (`recordings/`, `data/recordings`, `data/ml`), nenhum `.ai` e nenhum arquivo da pista entrou nos commits;
  - depois de cada envio, confira com `git ls-remote origin` que o hash remoto é o mesmo do local;
  - se o controle de permissões da sessão recusar o envio, deixe no relatório os comandos para eu rodar pelo terminal;
  - se pedir login, se o envio for recusado pelo GitHub ou se o remoto tiver divergido, pare e me avise. Nenhum token ou senha no chat, nos arquivos ou no relatório.
- **Janelas e pastas de teste** levam "[teste]" e são fechadas ou apagadas no fim.
- **Nomes técnicos** nos textos, sem apelidos. **Os tempos de volta** no formato M:SS,mmm.
- **Relatório** em `docs/handoff/2026-11-15_52_engenheiro-que-acompanha-a-volta_relatorio.md`, com:
  - o commit do ADR 0033;
  - a tabela dos marcos, a conferência e a figura;
  - a tabela das frases dos 15 trechos, a duração de cada aviso e os blocos de voz;
  - as conferências da Parte D e, depois do teste, a Parte E;
  - a saída dos testes e os commits;
  - o que foi enviado ao GitHub: a ref, o hash local e o hash no remoto;
  - os itens para o backlog.
- Se algo do contexto não bater com o repositório, pare e registre no relatório.
