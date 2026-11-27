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

## Atualização de 16/11 — as minhas decisões depois do relatório da parada na Parte E

Li o relatório (`docs/handoff/2026-11-15_52_engenheiro-que-acompanha-a-volta_relatorio.md`). Aplique estas decisões **antes do meu teste no jogo**, registre cada uma no ADR 0033 numa seção "Decisões do Eduardo de 16/11" (como emenda, sem mudar o texto acima dela) e só depois mude o código.

1. **O feedback espera a reta longa com a causa.** A frase do coach, o resumo e a análise esperam o bloco em que cabe a variante mais completa com a causa, depois da reserva dos avisos. Na prática, a reta dos boxes ou a reta oposta. Se a variante com a causa não couber nem na primeira reta longa depois de a mensagem nascer, sai nessa reta a variante mais completa que couber, como o rádio do 45 fazia. A mensagem nunca espera mais do que até essa reta longa. Os limites de 7,3, 8,0 e 8,8 s e a ordem do corte não mudam. O aviso de freada continua com a prioridade.
2. **O molde curto do aviso:** a voz diz só a frase, sem "Curva N:" e sem a vinheta, por exemplo "Freie 10 metros depois da placa de 100.". O cartão e a janela continuam escrevendo "Curva N:". Meça de novo a duração de cada aviso possível dos 15 trechos com a voz do projeto e refaça a tabela da B.4: quais cabem na voz agora.
3. **"Sem tirar o pé":** em todo trecho em que a referência não freia nem alivia (o acelerador fica em 0,90 ou mais do começo ao fim do trecho), a frase é "sem tirar o pé", sem marco e sem metros. Vale para todos os trechos nessa condição, e não só para a C13. O relatório diz quais trechos mudaram.
4. **A freada só depois da saída do trecho anterior:** a busca do ponto de freada de cada trecho começa na saída do trecho anterior (`pontos_de_linha_s`, saída), e não no ápice anterior. Vale para todos os trechos. Na C09, o toque de freio na saída da C08 deixa de ser a freada da C09. O relatório diz quais trechos mudaram.
5. **A C02 e a C08 ficam como estão:** a referência freia já mudando de direção, e a frase "freie no começo da zebra" está certa.
6. **"Freada leve" e "marcha acima" ficam para uma versão futura.** O ideal é o coach ler a pressão aplicada no freio e a marcha usada na curva. Liste no backlog: a volta ao vivo guardar a marcha e a força do freio; e a força do freio comparada com a minha melhor passagem, nunca com o pedal da volta do modelo (ADR 0032, item 5).
7. **Refaça a D.1** nas 4 sessões com as decisões 1 a 4 e traga a tabela de novo: os avisos pela voz e só na janela, a folga até a freada, o feedback com a causa na voz (sem e com o engenheiro) e as mensagens que mudaram de bloco. Depois, siga para a Parte E, o meu teste no jogo, como está acima.
8. **A marca no asfalto** fica como está para o teste: eu digo no jogo se ela aparece a tempo.

## Atualização de 20/11 — as minhas decisões depois do teste no jogo (a leitura E.3)

Li a leitura da sessão de 20/11 no relatório (Parte E, E.3). Escolhi a opção H (juntar o aviso com o da curva anterior, com a fala curta) mais o bipe (G) e a janela com as duas próximas dicas, com uma folga mínima de 3,0 s. Aplique estas decisões antes de um novo teste no jogo. Registre cada uma no ADR 0033 numa seção "Decisões do Eduardo de 20/11" (como emenda, sem mudar o texto acima dela), commite o ADR e só depois mude o código. Os números da E.3 são o motivo das decisões: nenhuma regra abaixo muda depois de ver os números da D.1 nova.

Tudo abaixo vale para qualquer pista e qualquer trecho. Interlagos e os trechos citados são só o exemplo desta sessão.

### As correções (valem para todo aviso)

1. **O aviso nunca espera na fila do app do jogo.** Hoje ele espera o cartão anterior (`CARTAO_MINIMO_S` e `FOLGA_DEPOIS_DA_VOZ_S`), como na C04, com 2,06 s de atraso. Com a mudança:
   - o cartão que estiver na tela sai quando o aviso chega;
   - uma fala de feedback em andamento é cortada, e o corte fica no registro do engenheiro;
   - o feedback cortado não volta a tocar na mesma reta; ele segue a regra da decisão 1 de 16/11 na reta longa seguinte.
2. **O aviso é disparado no próprio jogo, pelo `s` do carro, com o áudio já baixado** (a opção B). O backend manda ao app do jogo a lista dos avisos da volta com o áudio de cada um, antes de o carro chegar ao primeiro `s_fala`. O app do jogo toca cada aviso quando o carro passa o `s_fala`, sem esperar a rede. A latência de 0,1 s é uma estimativa: meça a real (do `s_fala` ao começo do som) na D.1, se der, e no teste no jogo.
3. **A reserva de fala usa o tempo da minha volta até o ponto, e não a velocidade do momento.** O tempo que o carro leva de um `s` a outro vem do perfil de tempo da volta usada no item 5. Isso evita o "outra fala em andamento" do segundo aviso da C04.

### As regras novas do aviso

4. **Todo aviso pode ir para a voz:** "freie", "vire", "acelere" e "sem tirar o pé". A regra "a voz só onde a referência freia" sai. A janela e o cartão continuam para todos os avisos.
5. **O aviso é calculado contra a minha ação, e não contra a da referência.**
   - **A minha ação de cada trecho** segue a regra da E.3: para "freie", a minha frenagem; para "vire", a minha primeira frenagem ou o primeiro alívio (acelerador abaixo de 0,90); sem nenhum dos dois, e para "sem tirar o pé", a entrada da curva. Para "acelere", o ponto em que eu volto ao acelerador. Em todos, a busca começa na saída do trecho anterior (decisão 4 de 16/11).
   - **De qual volta:** a última volta completa e sem rodada desta sessão. Antes de haver uma, vale a "Sua melhor volta" guardada da pista. Sem ela, vale a volta de referência.
   - **Depois de cada volta** que valer, o backend refaz os `s_fala` e manda a lista nova ao app do jogo. O pedaço livre que atravessa a linha de chegada usa a volta anterior.
6. **A folga mínima: 3,0 s.** A fala acaba pelo menos 3,0 s antes do mais cedo destes dois pontos: a minha ação esperada e o ponto dito no aviso. A conta inclui a latência do disparo no jogo (item 2). Essa é a regra que ficou faltando no ADR: quanto tempo antes da ação o aviso tem de terminar.
7. **Onde a fala acontece (a opção H):**
   - **O pedaço livre** é o da E.3.2: de quando a ação anterior acaba (acelerador em 0,90 ou mais e sem freio) até a ação seguinte, na volta do item 5.
   - **A fala começa e acaba dentro de um pedaço livre,** nunca dentro de uma curva nem durante outra ação. Ela não passa por cima de outro aviso.
   - **Cada aviso é dito no pedaço livre mais perto antes da ação dele em que a fala caiba com a folga do item 6.** Se não couber nesse, vai para o segundo mais perto. Nunca antes disso.
   - **Se dois avisos caem no mesmo pedaço livre, eles vão juntos numa fala só,** cada um com o número da curva ("Seis: vire na zebra. Sete: freie na zebra."). No máximo dois avisos por fala. Um aviso sozinho continua sem o número (decisão 2 de 16/11).
   - **O aviso que não couber em nenhum dos dois** fica só na janela e no bipe, com o motivo no registro.
   - **Dentro do pedaço livre,** a fala começa o mais tarde possível que ainda respeite a folga do item 6 e não colida com outra fala. Assim o aviso fica perto da ação, sem chegar em cima dela.
8. **A fala curta: eu escolho o molde ouvindo.** A fala curta sem "metros" não foi testada para ver se eu entendo. Implemente o molde como parâmetro, com três variantes:
   - **(a)** o molde curto de 16/11, por exemplo "Freie 10 metros depois da placa de 100.";
   - **(b)** o verbo, a distância e o marco, sem "metros" e sem "placa", por exemplo "Freie dez depois do cem.";
   - **(c)** o verbo e o marco com a correção no fim, como na E.3.3, por exemplo "Freie no cem, mais dez.".

   "Sem tirar o pé." é igual nas três. A velocidade da voz não muda. A escolha entra no ADR como a decisão de 20/11 sobre o molde, antes do teste no jogo.
9. **O bipe (a opção G):**
   - **Um bipe curto** (uns 0,25 s), tocado pelo app do jogo pelo `s` do carro, com o arquivo de som instalado junto com o app. Ele tem de ser diferente de qualquer som do rádio.
   - **Ele soa no ponto em que o aviso manda agir** (o ponto dito, o mesmo da marca na pista), antecipado do tempo de reação. Ele marca o ponto dito, e não a minha ação de costume: é ele que corrige a minha ação.
   - **O tempo de reação** é um parâmetro do ADR. O valor inicial vem de uma fonte citada no ADR. Se nenhuma fonte confirmar um valor para um sinal sonoro esperado ao volante, registre "não confirmado", use 0 s e me diga no relatório.
   - **Vale para "freie", "vire" e "acelere".** Para "sem tirar o pé" não há bipe, porque não há ação para marcar.
   - **Uma chave desliga o bipe,** no mesmo padrão de `AT_ENGENHEIRO`. O padrão é ligado.
   - **O bipe é a única exceção** ao "nunca dentro de uma curva" do ADR 0033: ele não é uma fala.
10. **A janela:** mostra sempre os dois próximos avisos, cada um desde o fim da ação anterior a ele (e não mais desde o `s_fala`). O da vez fica em destaque e sai depois da ação. Os textos da janela e do cartão continuam com "Curva N:".
11. **O feedback continua como na decisão 1 de 16/11.** A reserva das retas longas é feita primeiro para os avisos (agora de todos os tipos), e o feedback usa o que sobrar.

### A ordem

12. **O ADR 0033 com as decisões de 20/11, commitado antes do código.** Depois:
    - o código no backend e no app do jogo, cuja versão sobe para 0.8.0;
    - **os testes,** com dados sintéticos:
      - o pedaço livre;
      - a minha ação e as três voltas de onde ela pode vir;
      - a folga de 3,0 s contra o mais cedo dos dois pontos;
      - o primeiro e o segundo pedaço livre, e o aviso que não cabe;
      - a junção de no máximo dois avisos;
      - a fala o mais tarde possível;
      - o ponto do bipe e a ausência dele em "sem tirar o pé";
      - o aviso que não espera o cartão e o corte do feedback;
      - a reserva pelo tempo da volta;
      - a lista refeita depois de cada volta;
    - **a D.1 de novo,** nas 4 sessões de antes e na de 20/11 (`2026-11-20_19-06-14_vhe_interlagos`), com cada uma das três variantes do molde. Por sessão e por variante:
      - os trechos com aviso que têm voz, por volta, e o motivo de cada um que não tem;
      - a folga do fim da fala até a minha ação e até o ponto dito (mínimo, mediana e máximo);
      - as falas com dois avisos;
      - a distância e o tempo entre o bipe e a minha ação;
      - o feedback que mudou de bloco ou foi cortado;
    - **a D.2:** a prévia da janela com as duas próximas dicas. Também os arquivos de áudio de cada variante, com a voz do projeto, numa pasta "[teste]" fora da pasta do jogo: as falas sozinhas dos 15 trechos e as falas com dois avisos que a D.1 encontrou, cada uma com a duração;
    - **as suítes,** o `tsc` e o `conferir_lua.py`.

    **Pare antes do teste no jogo.** Eu escuto as três variantes e escolho o molde. Depois, rodo o `instalar.ps1` do app do jogo 0.8.0 com o meu "pode instalar".
13. **O teste no jogo, de novo,** com o roteiro da Parte E, item 1 (pelo menos 10 voltas, até 45 minutos, na pista original). Se eu rodar, continuo a sessão.
    - **Antes,** deixe no relatório um cartão curto para eu preencher depois da sessão: por trecho, "ouvi", "entendi" e "deu tempo".
    - **A leitura** repete as tabelas da E.3.1 e da E.3.2 com o que mudou:
      - por aviso, se foi para a voz, a latência medida, o fim da fala até a minha ação e até o ponto dito, e o bipe até a minha ação;
      - se a minha ação se moveu na direção do ponto dito nas voltas seguintes (só relatado: o veredito é do protocolo de avaliação);
      - o FPS;
      - os logs do CSP;
      - o meu cartão.
14. **O merge em `develop` e o instalador 0.9.0** continuam parados até depois desse teste e da conferência, como na Parte F.
15. **No relatório,** uma seção "Atualização de 20/11" com o commit do ADR, os testes, a D.1 por variante, a D.2, as suítes e o cartão. Depois do teste, a leitura.

## Atualização de 21/11 — as minhas decisões depois do segundo teste no jogo (a curva de foco)

Li no relatório as seções do teste de 21/11 (sessão `2026-11-21_18-10-46`) e "A ficha da curva". A parte técnica funcionou, mas o engenheiro fala de curvas demais, cedo demais, e o bipe marca coisas diferentes. Decidi trocar a entrega de 20/11 pela curva de foco, com a ficha que eu pedi.

Faça como uma atualização deste pedido, e não como um pedido novo. Registre cada decisão no ADR 0033 numa seção "Decisões do Eduardo de 21/11" (como emenda, sem mudar o texto acima dela), commite o ADR e só depois mude o código. Nenhuma regra abaixo muda depois de ver os números da D.1 nova. Tudo vale para qualquer pista e qualquer trecho: Interlagos e as curvas citadas são só o exemplo.

### O que sai e o que fica da emenda de 20/11

1. **Sai:**
   - o aviso de voz para toda curva (item 4);
   - as falas com dois avisos e o segundo pedaço livre (item 7);
   - o bipe em todo aviso de "freie", "vire" e "acelere" (item 9).
2. **Fica:**
   - o aviso que não espera a fila do app do jogo (item 1);
   - o disparo no jogo pelo `s` do carro, com o áudio já baixado (item 2);
   - a reserva pelo tempo do perfil (item 3);
   - a ação contra a minha volta e o perfil (item 5);
   - a folga mínima de 3,0 s (item 6);
   - o molde (b) do lembrete;
   - a conferência depois da curva, como já existe.

### A curva de foco

3. **Uma curva de foco por vez:** a curva em que eu mais perco, com a perda acima do ruído do trecho (ADR 0033, item 1), nas voltas que contam desta sessão. O engenheiro só fala da curva de foco. As outras ficam caladas na voz e no bipe até virarem o foco.
4. **A troca do foco** acontece em dois casos:
   - quando a conferência mostra que apliquei a instrução;
   - depois de 3 voltas que contam com a mesma curva em foco sem aplicar.

   Aí vem a curva seguinte em perda. Uma curva que saiu do foco sem ser aplicada pode voltar mais tarde. Registre no ADR o que conta como "aplicou", com a mesma medida da conferência.
5. **Antes da primeira volta que conta:**
   - **O foco** vem da minha última sessão nesta pista que tenha volta que conta. Sem ela, não há foco até a primeira volta que conta.
   - **A janela nunca fica vazia sem explicação.** Enquanto não houver foco, ela mostra "Esperando uma volta que conte" e o motivo da última volta descartada (por exemplo, "volta 3: rodada"). No teste de 21/11, eu achei que o engenheiro estava quebrado.

### A ficha da curva de foco

6. **O texto da ficha** é o da tabela "As 14 fichas" do relatório: a curva e o lado, onde frear, a técnica, a linha e a velocidade.
   - **A marcha fica fora da fala e da janela** até alguém conferir que a marcha gravada é a marcha real do carro. Esse item vai para o backlog.
   - **Sem placa no trecho,** entra o marco mais perto, no molde (b), como está no relatório.
7. **A técnica:**
   - **"De pé embaixo" e "só um alívio"** vêm da volta de referência, porque dependem só de onde ela freia ou alivia.
   - **"Com trail braking" ou "frenagem em linha reta"** vêm da minha melhor passagem naquela curva, nunca do pedal da IA (ADR 0032, item 5). Use as mesmas regras do relatório: freio pisado 10 m ou mais depois da entrada, ou solto antes dela.
   - **Sem uma passagem minha naquela curva,** a técnica fica fora da fala.
8. **O alívio só conta com 10 m ou mais de acelerador abaixo de 0,90.** Isso evita que a queda de 2 a 4 m na troca de marcha vire "só um alívio". A mesma regra vale para o "sem tirar o pé" do engenheiro. O relatório diz quais trechos mudam com isso.
9. **Quando a ficha é dita:** uma vez por volta, enquanto a curva for o foco, na reta longa antes dela, que é a reta dos boxes ou a oposta, a que vier primeiro antes da curva.
   - A ficha tem prioridade sobre o feedback nessa reta. O feedback usa a outra reta longa e o que sobrar.
   - A janela mostra a ficha escrita da curva de foco a volta toda.
10. **O lembrete curto,** no molde (b) e com o número da curva ("Um: entre o 100 e o 50."), é dito no pedaço livre logo antes da curva de foco, com a folga mínima de 3,0 s.
    - Se não couber, não há lembrete: fica a contagem de bipes.
    - Se a ficha e o lembrete caírem no mesmo pedaço livre, fica só a ficha, também com a folga de 3,0 s.

### A contagem de bipes

11. **Três bipes em ritmo fixo, com o último no ponto de frenagem da referência** na curva de foco. Ele é o mesmo ponto da marca no asfalto.
    - **O som:** os dois primeiros bipes são iguais, e o último é mais agudo.
    - **O intervalo** é um parâmetro do ADR. Diga no relatório de onde tirou o valor, ou registre "não confirmado".
    - **Só nas curvas em que a referência freia.** As de pé embaixo e as de só um alívio não têm bipe.
    - **A chave que desliga o bipe continua,** e o padrão é ligado.
12. **A marca no asfalto** fica só na curva de foco.

### A ordem

13. **O ADR 0033 com as decisões de 21/11, commitado antes do código.** Depois:
    - **o código** no backend e no app do jogo, cuja versão sobe;
    - **os testes,** com dados sintéticos:
      - a escolha do foco e as duas regras de troca;
      - o foco que vem da sessão anterior e a janela "Esperando uma volta que conte";
      - a técnica da minha melhor passagem e a ausência dela;
      - o filtro de 10 m do alívio;
      - a ficha uma vez por volta na reta longa, com prioridade sobre o feedback;
      - o lembrete com a folga e o lembrete que não cabe;
      - a contagem de três bipes e a ausência dela nas curvas sem frenagem;
      - a marca só na curva de foco;
    - **a D.1 de novo,** nas 4 sessões de antes e nas de 20/11 e 21/11. Por sessão:
      - a curva de foco de cada volta, quando ela mudou e por quê;
      - a ficha e o lembrete, com o ponto em que foram ditos e a folga até a minha ação e até o ponto dito;
      - o último bipe contra o ponto de frenagem e contra a minha frenagem;
      - as conferências;
      - o feedback que mudou de bloco;
      - **os segundos de fala por volta, antes e depois desta emenda.** É a medida do "muita informação";
    - **a D.2:** as fichas refeitas com a técnica da minha melhor passagem, em áudio, numa pasta "[teste]" fora da pasta do jogo, e a prévia da janela com a ficha e com "Esperando uma volta que conte";
    - **as suítes,** o `tsc` e o `conferir_lua.py`.
14. **Pare antes do teste no jogo.** O instalador do app do jogo só roda com o meu "pode instalar", e quem roda sou eu.
15. **O teste no jogo, de novo,** com o roteiro da Parte E: pelo menos 10 voltas, até 45 minutos, na pista original.
    - **Antes,** deixe no relatório um cartão novo, com uma linha por volta: qual foi a curva de foco, "entendi a ficha", "o lembrete chegou a tempo", "a contagem me ajudou a frear no ponto" e uma anotação.
    - **A leitura** repete as tabelas da D.1 nesta sessão, com a latência, o FPS, os logs do CSP e o meu cartão. Se a minha frenagem na curva de foco se moveu na direção do ponto, entra só relatado: o veredito é do protocolo de avaliação.
16. **O merge em `develop` e o instalador 0.9.0** continuam parados até depois desse teste e da conferência, como na Parte F.
17. **No relatório,** uma seção "Atualização de 21/11" com o commit do ADR, os testes, a D.1, a D.2, as suítes e o cartão. Depois do teste, a leitura.

## Atualização de 26/11 — as minhas decisões depois do teste do engenheiro que ensina

Testei no jogo o app do jogo 0.10.0, com as chaves, os níveis, a análise e o treino que pedi em 22/11. Achei cinco problemas, e as decisões abaixo resolvem cada um.

Registre as decisões no ADR 0033 numa seção "Decisões do Eduardo de 26/11, depois do teste no jogo", como emenda, sem mudar o texto acima dela. Commite o ADR e só depois mude o código. Tudo vale para qualquer pista, qualquer nível e qualquer escopo (uma curva, algumas curvas ou a volta inteira). Interlagos e as curvas citadas são só o exemplo.

### Antes do código: a leitura do meu teste

1. **Leia a sessão do meu teste de 26/11** (a primeira gravada depois da instalação do 0.10.0) e registre no relatório, com o foco nos cinco problemas abaixo:
   - **cada fala do engenheiro:** o tipo, a curva de que ela fala, o `s` em que começou e quantos segundos e metros antes da ação dessa curva ela acabou;
   - **o que foi dito depois de cada curva** e o que ficou na fila sem ser dito;
   - **de onde veio o limite de 3 curvas** que eu ouvi (uma regra, o escopo ou outra coisa).

   Essa leitura não muda nenhuma das decisões abaixo: ela só mostra o antes.

### 1. O engenheiro fala de uma curva logo antes dela

No teste, ele falou da C12 na saída do S do Senna. Isso está errado.

2. **Toda fala sobre uma curva acontece só no trecho logo antes dela.**
   - **Que falas:** o texto do nível, o lembrete e a ficha.
   - **Onde começa o trecho:** na retomada da curva anterior (ADR 0030), quando o acelerador volta a subir. Ele passa por qualquer trecho de velocidade constante, sempre sem freio, e acaba na ação da curva.
   - **Onde a fala nunca acontece:** antes da curva anterior, nem na reta longa de outra curva.
   - **O que deixa de valer:** a "reta longa antes" (item 9 de 21/11) e o "pedaço logo antes" com o acelerador em 0,90 ou mais (item 10 de 21/11). O lugar da fala passa a ser este trecho.
3. **A folga mínima continua 3,0 s** até o mais cedo destes dois pontos: a ação esperada e o ponto dito.
4. **O que cabe no trecho, nesta ordem:**
   - o texto do nível;
   - se ele não couber, o lembrete;
   - se nada couber, só a contagem de bipes e a janela.

   A explicação completa vai para o debriefing (item 7), e o motivo fica no registro.
5. **O iniciante continua sem o texto longo na volta rápida.** O texto dele (14 a 25 s) vai só para o debriefing.

### 2. As orientações: a volta de delta e os boxes

6. **Depois de cada bloco de voltas rápidas, o engenheiro orienta na linha.**
   - **O bloco** tem as x voltas que contam da chave de treino. Com x = 1, a orientação vem depois de cada volta rápida.
   - **A orientação é uma de duas:**
     - **"Mantenha o delta nesta volta":** a volta de delta é uma volta lenta, pela regra da volta lenta (5,0 s ou mais acima da volta que contou). Nela, o engenheiro faz o debriefing. A janela mostra o delta ao vivo contra o alvo, para eu manter o ritmo. O alvo é um parâmetro do ADR.
     - **"Box, box, venha para os boxes para a análise":** vale quando o debriefing não cabe numa volta de delta, pelo volume medido com a regra de 22/11. Nos boxes, com o carro parado, ele fala o debriefing inteiro, e a janela oferece o "Abrir no app" daquela volta.
   - **Se eu não obedecer** e continuar em volta rápida, o debriefing não é dito durante ela. A orientação se repete uma vez na linha seguinte.
   - **A orientação passa à frente de tudo na fila,** como já decidido.

### 3. As curvas de maior perda, sem um número fixo

7. **No debriefing, o engenheiro diz todas as curvas com perda acima do ruído do trecho,** na ordem do tempo perdido, com quanto cada uma custou no bloco.
   - **O limite é só o tempo:** o que não couber na volta de delta vai para os boxes, ou fica na janela e no app.
   - **A janela e o app mostram a lista inteira.**
   - **Não há mais limite de 3 curvas,** nem de outro número fixo.

### 4. O retorno sobre o que foi pedido

8. **Para cada curva que recebeu uma instrução no bloco, o engenheiro compara o que eu fiz com o que ele pediu** e me diz o resultado.
   - **A medida** é a mesma da conferência de 21/11: se apliquei, quanto falta e em que direção.
   - **Onde ele diz:** logo depois da curva, se couber pela regra do item 2, e de novo no debriefing, com o resumo do bloco.
   - **A fala antes da próxima curva tem prioridade.** Se o retorno não couber junto com ela, ele vai só para o debriefing.
9. **O retorno da curva instruída vem antes da análise da curva que mais custou.** Isso muda a decisão (A) de 26/11:
   - a fala da linha é o retorno da curva instruída;
   - a curva que mais custou entra na lista do debriefing.
10. **Nenhum retorno sai da fila sem ter sido dito.** Em 13/10, nenhuma análise chegou a ser dita, porque a regra do pedido 45 tirava da fila a análise da curva por onde o carro ia passar de novo.
    - **O retorno depois da curva** é dito no trecho depois dela, sem passar pela fila da linha.
    - **No debriefing,** na volta de delta ou nos boxes, essa regra do pedido 45 não vale.
11. **Quando uma volta não basta, ele pede mais voltas** ("Me dê mais três voltas nessa frenagem"). Isso vale em dois casos:
    - a diferença entre o que fiz e o que ele pediu está dentro do ruído do trecho;
    - apliquei numa volta e não na outra.

    O número de voltas é um parâmetro do ADR, com 3 no começo. A regra da troca do foco (3 voltas sem aplicar) continua.

### 5. Uma voz melhor

12. **Teste a voz neural da Microsoft e a do Piper contra a Daniel de hoje,** e pare para eu escolher ouvindo.
    - **A Microsoft:** a pt-BR-AntonioNeural (a do vídeo do TCC de 08/11) e mais uma voz pt-BR da mesma família, pela API oficial da Azure AI Speech. Não use o serviço de leitura do Edge por fora da API.
      - Eu crio a conta e a chave e ponho a chave em variáveis de ambiente (`AZURE_SPEECH_KEY` e `AZURE_SPEECH_REGION`).
      - A sessão nunca pede a chave no chat e nunca a escreve em arquivo, log, commit ou relatório.
      - Se a chave não estiver lá, pare e me avise.
    - **O Piper:** as vozes pt_BR disponíveis, sem internet.
      - **Autorizo instalar neste pedido** só o pacote `piper-tts`, com o que ele exigir, no ambiente do backend. Para a Azure, use a API REST com o que o projeto já tem; se ela pedir um pacote novo, pare e me avise.
      - Os modelos de voz ficam em `data/`, fora do git.
      - Registre no ADR a licença de cada voz, pelo cartão do modelo.
    - **As falas do teste,** iguais em todas as vozes:
      - a C04 nos três níveis;
      - um lembrete;
      - um retorno com números;
      - "Mantenha o delta nesta volta";
      - "Box, box, venha para os boxes para a análise".

      Use cada voz na velocidade normal, e também a 1,2x se a normal ficar longa. Deixe tudo numa pasta "[teste]" fora da pasta do jogo, com a duração de cada arquivo.
13. **A voz vira uma chave da configuração,** com a Daniel como reserva.
    - **O áudio gerado** fica num cache, pelo texto e pela voz.
    - **Se a voz escolhida falhar** (sem internet ou sem chave), a fala sai na Daniel, e a troca fica no registro.
    - **A mesma voz vale para todo o rádio:** o engenheiro, o resumo e o coach.
    - **As durações das regras** (folga, trecho e blocos) passam a ser as medidas com a voz escolhida.

### A ordem

14. **Primeiro a leitura do item 1, depois o ADR 0033 com as decisões de 26/11,** commitado antes do código. Em seguida:
    - **o código** no backend e no app do jogo, cuja versão sobe;
    - **os testes,** com dados sintéticos:
      - o trecho que começa na retomada da curva anterior e a fala que nunca vem antes dela;
      - o texto do nível, o lembrete e "só bipes", nessa ordem;
      - a orientação de delta e a de boxes, pelo volume, e a orientação repetida;
      - o debriefing com todas as curvas acima do ruído, em ordem;
      - o retorno depois da curva, a prioridade da fala da curva seguinte e o retorno que vai para o debriefing;
      - o retorno que não sai da fila sem ser dito;
      - o pedido de mais voltas;
      - a chave da voz, o cache e a reserva na Daniel;
    - **a D.1 de novo,** nas sessões de antes e na do meu teste de 26/11, com o nível amador e a volta inteira, e com o treino de 1 e de 5 voltas. Por sessão:
      - quantos segundos e metros antes da ação cada fala acabou (nenhuma antes da curva anterior);
      - quantas curvas tiveram o texto do nível, o lembrete ou só os bipes;
      - as orientações e o tempo do debriefing;
      - quantas curvas o debriefing citou;
      - os retornos ditos depois da curva e os que foram para o debriefing;
      - os pedidos de mais voltas;
      - os segundos de fala por volta, antes e depois desta emenda;
    - **a D.2:**
      - os áudios do item 12;
      - a prévia da janela com o delta ao vivo e com a lista do debriefing;
    - **as suítes,** o `tsc` e o `conferir_lua.py`, com o limite das variáveis locais do Lua.
15. **Pare antes do teste no jogo.** Eu ouço as vozes e escolho uma, e a escolha entra no ADR. Depois, o instalador do app do jogo só roda com o meu "pode instalar", e quem roda sou eu.
16. **O teste no jogo, de novo,** com o roteiro da Parte E: pelo menos 10 voltas, até 45 minutos, na pista original.
    - **Antes,** deixe no relatório um cartão com uma linha por volta:
      - a fala veio antes da curva certa;
      - entendi;
      - deu tempo;
      - o retorno depois da curva;
      - a orientação (delta ou boxes) fez sentido;
      - uma anotação.
    - **A leitura** repete as medidas da D.1 nesta sessão, com a latência, o FPS e os logs do CSP.
17. **O merge em `develop` e o instalador 0.9.0** continuam parados até depois desse teste e da conferência, como na Parte F.
18. **No relatório,** uma seção "Atualização de 26/11" com a leitura do item 1, o commit do ADR, os testes, a D.1, a D.2, as suítes e o cartão. Depois do teste, a leitura dele.
