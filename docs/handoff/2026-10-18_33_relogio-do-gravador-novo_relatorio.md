# Relatório do pedido 33: o relógio do gravador novo (parado no diagnóstico: a causa não é defeito de código)

- **Pedido:** `docs/prompts/2026-10-18_33_relogio-do-gravador-novo.md`.
  - **Feitas:** a Parte A (diagnóstico) e a Parte C (cuidados de processo).
  - **A Parte B não se aplica:** a causa não está no gravador, no corte em voltas nem na interpolação na linha. Parei aqui, como o pedido manda.
- **Branch:** `etapa/relogio-do-gravador`, criada de `develop` (`1c53807b`), com merge em `develop`. Nada foi enviado ao remoto.
- **Commits e merge:**
  - `567dfb0e` docs: pedido 33
  - `f394bbcf` Parte C: a janela de teste com "[teste]" no título
  - o commit deste relatório, com o handoff: "Relatório do pedido 33"
  - o merge em `develop`: "Merge etapa/relogio-do-gravador (pedido 33)"
- **Fora deste pedido, no meio dele:** você testou o rádio no jogo (pedido 31, Parte F), e o app do jogo ficou calado. Corrigi o app na branch do pedido 31, com `develop` avançando até ela:
  - `7904758f`: a conferência da API calava o app;
  - `416ae3f7`: o aviso de API faltando nunca aparecia.

  Isso vai para o relatório do pedido 31 quando ele fechar.
- **Arquivos de handoff** (`docs/handoff/2026-10-18_33_relogio-do-gravador-novo_*`):
  - `_relatorio.md` (este arquivo);
  - `_amostras_perto_da_linha.txt`: amostra a amostra, perto da linha, as voltas acima de 5 ms e voltas boas das mesmas sessões;
  - `_periodo_por_volta.csv`: as 676 voltas do store. Para cada uma: a diferença, a velocidade na linha nas duas pontas, a parte explicada pela travessia e o resto;
  - `_intervalos_por_sessao.csv`: o intervalo entre amostras e a coerência entre tempo e posição, sessão a sessão;
  - `_diagnostico.json`: os números principais;
  - `_scripts/`: os seis scripts do diagnóstico, que só leem as gravações e o store;
  - `_testes.txt`;
  - `.patch`: de `1c53807b` até o merge, só o `desktop`.

## Em resumo

1. **A causa não é o gravador.** Também não é o corte em voltas, a interpolação na linha nem o cronômetro do jogo.
   - **É a régua da checagem:** os dois lados medem a volta em linhas diferentes.
     - **O período** vai de s = 0 a s = 0 da geometria oficial.
     - **O tempo do jogo** vai de linha do jogo a linha do jogo, e a linha do jogo fica **1,46 m depois do s = 0** (medido em 138 voltas, com desvio de 0,07 m).
   - **As duas medidas só batem** quando o carro passa pela linha na mesma velocidade no começo e no fim da volta.
2. **As 5 voltas novas acima de 5 ms começaram logo depois de uma passagem lenta pela linha:** de 162 a 211 km/h, contra 255 a 265 km/h nas outras.
   - **Na `2026-10-17_16-17-08#0007`:**
     - o carro passou a 166 km/h no começo e a 257 km/h no fim;
     - atravessar os 1,46 m leva 31,7 ms numa ponta e 20,5 ms na outra;
     - a diferença prevista é de 11,2 ms, e a medida foi de 11,74 ms.
   - **As duas piores voltas antigas** (−21,5 e −20,1 ms) são o caso oposto: terminam a 138 e a 127 km/h.
3. **Tirando a travessia, o store passa com folga.**
   - **As 676 voltas:** o p99 fica em **3,56 ms**, contra o limite de 5 ms.
   - **As voltas do app novo:** o p99 fica em 2,69 ms (0.3.0) e 3,05 ms (0.4.0), sem nenhuma volta acima de 5 ms.
   - **A sua sessão de hoje,** fora do store: as 13 voltas passaram pela linha entre 249 e 256 km/h, e a pior fechou a 3,24 ms do jogo.
4. **O gravador está certo:** o tempo e a posição de cada amostra vêm do mesmo passo de física do jogo (veja A.1).
5. **Não mudei nada na checagem.** Mudar a régua é mudar o critério, e isso é decisão sua.
   - **Minha proposta:** medir o tempo do jogo na mesma linha do período, somando a travessia dos 1,46 m nas duas pontas.
   - **O limite de 5 ms continua.**
   - Veja "O que precisa de decisão".
6. **A Parte C está feita:**
   - a janela de teste tem "[teste]" no título;
   - as duas regras estão guardadas para os próximos pedidos;
   - nenhuma trava do git apareceu neste pedido.
7. **Testes:**
   - **backend:** a suíte passa com **768 testes**, os mesmos de antes;
   - **front:** o `tsc` passa, e o `vitest` passa com 182 testes;
   - **o código do gravador, do corte e da checagem** não mudou.

## Parte A: diagnóstico

### A.1 As amostras perto da linha

**Como ler as tabelas** (completas em `_amostras_perto_da_linha.txt`):

- **as fontes de cada dado:**
  - o cronômetro (`iCurrentTime`) e a posição (`carCoordinates`) vêm da página gráfica do jogo;
  - a velocidade vem da página de física;
  - o horário do gravador é o relógio do Windows na hora da leitura;
- **o que cada coluna mostra:**
  - `d_cron` é o intervalo pelo cronômetro do jogo;
  - `d_s` é o quanto o carro andou na geometria oficial;
  - `v pelo cron` é `d_s / d_cron`, a velocidade que sai só da posição e do cronômetro.

**A volta ruim `2026-10-17_16-17-08#0007` (+11,74 ms), no fim e no começo dela:**

| ponta | cronômetro (ms) | contador | s (m) | v (km/h) | d_cron (ms) | d_s (m) | v pelo cron |
|---|---|---|---|---|---|---|---|
| começo (fim da anterior) | 103.713 | 7 | 4.334,01 | 165,75 | 15 | 0,70 | 166,86 |
| | 103.731 | 7 | 0,77 | 165,75 | 18 | 0,83 | 166,87 |
| | 12 | 8 | 2,02 | 165,76 | — | — | — |
| | 30 | 8 | 2,85 | 165,77 | 18 | 0,83 | 166,88 |
| fim | 92.112 | 8 | 4.333,20 | 256,85 | 18 | 1,29 | 258,60 |
| | 92.130 | 8 | 0,42 | 256,88 | 18 | 1,29 | 258,63 |
| | 12 (volta seguinte) | 9 | 2,36 | 256,91 | — | — | — |
| | 30 | 9 | 3,65 | 256,92 | 18 | 1,29 | 258,70 |

- **O cronômetro zera entre s = 0,77 e 2,02 m no começo, e entre s = 1,06 e 2,36 m no fim.** As duas vezes, o zero cai em 1,46 m.
- **A diferença está na velocidade:**
  - a 166 km/h, o carro leva 31,7 ms entre o s = 0 e a linha do jogo;
  - a 257 km/h, leva 20,5 ms.
- **A passagem por s = 0 é bem medida:** as estimativas das 14 a 18 amostras na janela ficam a menos de 1 ms da mediana, nas duas pontas.

**Uma volta boa da mesma sessão, a `#0010` (+0,22 ms):** passou a 256,0 km/h no começo e a 256,9 km/h no fim. A travessia é igual nas duas pontas, e as duas medidas batem.

**A pior volta antiga, a `2026-10-05_20-33-47#0013` (−21,46 ms):**
- começou a 256,7 km/h e terminou freando, a 138 km/h;
- a travessia do fim é a mais longa, e a diferença sai negativa.

**O tempo e a posição vêm do mesmo passo de física?** Sim:

1. **O cronômetro anda em passos de 3 ms,** que são os passos de física do jogo. Isso vale para 100% dos intervalos, nas 9 sessões.
2. **A posição anda junto com o cronômetro:**
   - a `v pelo cron` sobe suave, de 258,41 a 258,70 km/h;
   - se a posição de uma amostra fosse de outro passo, ela pularia uns 20% (3 ms num intervalo de 15 ms).
3. **Nas 9 sessões,** o cronômetro fica parado com o carro andando em 0 a 0,002% das amostras.
4. **O erro entre o tempo e a posição** tem p99 de 0,24 a 0,46 ms nas sessões novas.
5. **Uma exceção pequena:**
   - em cerca de 0,4% das amostras, esse erro passa de 3 ms;
   - na sessão do 0.4.0, olhei essas amostras uma a uma: o erro mediano é de 3,0 ms, um passo de física, quase sempre com a posição atrás do cronômetro;
   - a proporção é parecida no app antigo (0,38 a 0,73%) e no novo (0,38 a 0,46%), então não vem da mudança do gravador;
   - a mediana de 12 a 24 amostras na passagem pela linha absorve isso.

**O `packetId`:** o gravador não guarda nenhum.
- O leitor usa o `packetId` da página de física só para descartar uma leitura repetida.
- A página gráfica, de onde vêm o cronômetro e a posição, tem o seu próprio `packetId`, que não é lido.

A prova acima não precisou dele.

### A.2 O que mudou no gravador entre o 0.1.7 e o 0.3.0 em diante

- **As versões:**
  - o 0.1.7 é o commit `b1dc2502`, de 25/08;
  - o 0.3.0 é o `e0f64ece`;
  - o 0.4.0 é o `429a5c47`.
- **Não mudou nada:**
  - no laço de leitura (`core/live/telemetry_runtime.py`);
  - no gravador (`core/recording/`);
  - no estado do quadro (`runtime_state.py`);
  - no barramento.
- **O que mudou:**
  1. **A página de física** (pedido 18, `e1407224`):
     - o layout foi corrigido, e a página ganhou canais novos;
     - a ordem de leitura não mudou: física, gráfica e estática, cada página copiada inteira;
     - o cronômetro e a posição continuam vindo da mesma cópia da página gráfica.
  2. **O indicador de IA** (pedido 12, `15b0e268`): é um campo a mais da página de física.
  3. **A identidade do app no metadado** (pedido 28): é escrita uma vez, no começo da sessão.
  4. **A Coleta** (pedido 28, `8aae52da`) e o coach ao vivo, mais pesado:
     - o monitor da Coleta roda a cada quadro;
     - a conferência relê o arquivo a cada 5 s, numa thread;
     - o coach projeta o carro na geometria oficial a cada quadro.
- **O que isso pode e o que não pode fazer:**
  - os itens do item 4 disputam o processador com o laço de leitura, então **podem atrasar uma leitura**;
  - **não podem separar o tempo da posição,** que saem da mesma cópia da página gráfica.
- **O que se mede (A.3):** as duas sessões mais recentes têm mais amostras repetidas e mais buracos. Isso não move o período, porque o período usa o cronômetro do jogo.

### A.3 O intervalo entre amostras, sessão a sessão

Pelo cronômetro do jogo, com o carro acima de 30 km/h:

| sessão | app | intervalo mediano | p1 / p99 | repetidas* | buracos ≥ 50 ms | maior buraco | relógio do gravador − cronômetro, p99 |
|---|---|---|---|---|---|---|---|
| 14/06 12:23 | junho (0.1.x) | 33 ms | 21 / 48 | 0,10% | 0,90% | 885 ms | 10,1 ms |
| 19/08 20:58 | 0.1.7 | 15 ms | 9 / 33 | 2,30% | 0,36% | 1.170 ms | 13,9 ms |
| 05/10 20:33 | 0.1.7 | 15 ms | 6 / 48 | 1,67% | 0,97% | 360 ms | 9,9 ms |
| 11/10 14:19 | 0.1.7 | 15 ms | 9 / 36 | 1,53% | 0,06% | 354 ms | 8,4 ms |
| 13/10 19:24 | 0.1.7 | 15 ms | 6 / 36 | 1,86% | 0,03% | 345 ms | 9,2 ms |
| 15/10 23:24 | 0.3.0 (repositório) | 15 ms | 9 / 36 | 1,54% | 0,28% | 351 ms | 8,0 ms |
| 17/10 01:02 | 0.3.0 (repositório) | 18 ms | 9 / 36 | 1,52% | 0,28% | 387 ms | 6,8 ms |
| 17/10 16:17 | **0.4.0 (pacote)** | 15 ms | 6 / 48 | **5,20%** | 0,76% | 456 ms | **29,4 ms** |
| 18/10 12:38 | develop com o rádio (repositório) | 15 ms | 6 / 48 | 3,98% | 0,84% | 288 ms | 13,4 ms |

\* As **repetidas** têm o mesmo cronômetro e o mesmo lugar da anterior, mas a página de física já mudou. O leitor só descarta a leitura quando a física também é igual.

- **Do 0.1.7 ao 0.3.0, a leitura é igual.**
- **No 0.4.0 e na sessão de hoje há mais irregularidade:**
  - mais repetidas;
  - mais buracos;
  - o relógio do gravador mais solto, com p99 de 29 ms no 0.4.0.
- **A causa disso não ficou estabelecida.** Pode ser a taxa de quadros do jogo nesses dias ou a carga da máquina.
- **O que isso não afeta:** o período e a checagem, que usam o cronômetro do jogo. Para a M1, veja A.5.

### A.4 A causa, com a evidência

| classe | é a causa? | por quê |
|---|---|---|
| **gravação** | não | o tempo e a posição de cada amostra vêm do mesmo passo de física (A.1) |
| **processamento** | não | o corte e a interpolação acham a passagem por s = 0 a menos de 1 ms entre as amostras; sem a travessia, o p99 do store é de 3,56 ms |
| **o jogo** | não | o cronômetro anda em passos de 3 ms, e a costura do tempo do jogo na troca de volta está certa |

**O que é:** a régua da checagem compara duas linhas diferentes.

- **O modelo:** período − tempo do jogo = 1,463 m × (1/v na linha no começo − 1/v na linha no fim).
- **Nas 90 voltas das 8 sessões lidas,** com a velocidade das amostras cruas:
  - a correlação com a diferença medida é de 0,90;
  - nas 5 voltas novas, o resto fica entre 0,1 e 2,9 ms.
- **Nas 676 voltas do store:**
  - a correlação é de 0,72;
  - o p99 vai de 7,63 ms para **3,56 ms**;
  - as voltas acima de 5 ms caem de 10 para 3.

**Por que só agora:**
- nas sessões antigas, quase toda passagem pela linha é a mais de 250 km/h;
- nas novas, 5 de 39 voltas começam logo depois de uma passagem a 162–211 km/h, quando a volta anterior terminou devagar.

É a pilotagem, e não o gravador.

**O que sobra sem explicação pela travessia são 3 voltas antigas de 14/06**, do app de junho, com 31 amostras por segundo:
- nelas, a diferença fica entre 5,5 e 8,2 ms mesmo sem a travessia;
- na que olhei amostra a amostra (`2026-06-14_12-23-46#0005`), o gravador de junho parou cerca de 0,8 s logo depois da linha;
- e a primeira amostra da volta tem a posição adiantada sobre o cronômetro (velocidade implícita de 352 km/h com o carro a 272 km/h);
- é um defeito antigo, de um gravador que não é mais usado;
- essas voltas já estavam no store quando o p99 era de 4,60 ms.

### A.5 O efeito na M1

**A fração de amostras com Δt irregular** (repetidas mais buracos ≥ 50 ms):
- **antigas:** de 1,0 a 2,7%;
- **0.3.0:** 1,8%;
- **0.4.0:** 6,0%;
- **hoje:** 4,8%.

**O tamanho do erro de estado,** numa freada forte deste carro (25 m/s², o p0,1 da sessão do 0.4.0):

- **com o Δt pelo cronômetro do jogo** (o que o store v2 usa):
  - **a posição:** com o tempo e a posição do mesmo passo, o erro fica abaixo de 0,5 ms, menos de 4 cm a 280 km/h;
  - **a página de física** (velocidade, pedais e cargas):
    - ela chega de 0 a 3 ms adiantada sobre o cronômetro, em todas as sessões, antigas e novas;
    - isso dá até 0,08 m/s (0,3 km/h).
- **com o Δt pelo relógio do gravador:**
  - o p99 da diferença fica entre 7 e 14 ms nas sessões normais, o que dá de 0,2 a 0,35 m/s (até 1,3 km/h);
  - no 0.4.0, fica em 29 ms, o que dá 0,73 m/s (2,6 km/h).
- **as amostras repetidas:**
  - têm Δt = 0 pelo cronômetro, mas a física mudou;
  - para a M1, precisam ser descartadas, ou juntadas à anterior.

**Para a M1** (recomendação, sem mudança agora): usar o cronômetro do jogo como relógio e descartar as amostras repetidas. O store v2 já usa o cronômetro.

## Parte B: correção

**Não se aplica.** O pedido só autoriza corrigir defeito no gravador, no corte em voltas ou na interpolação na linha, e a Parte A não achou nenhum.

- **Não mudei** a checagem, o limite, nenhuma volta nem nenhuma gravação.
- **Não rodei** o `atualizar_coach`.
- **Não gerei instalador.**

## Parte C: cuidados de processo

1. **Janelas de teste:**
   - **a regra no código:** o `desktop/main.js` (`f394bbcf`) põe "[teste] " no começo do título quando o app abre com a pasta de dados isolada (`AT_DESKTOP_USER_DATA_DIR`, como em todos os testes que eu abro) ou com `AT_DESKTOP_TESTE=1`;
   - **a conferência:** abri uma janela assim, ela mostrou "[teste] Sistema de Telemetria e Otimização de Trajetórias", e eu a fechei;
   - **no fim do pedido:** nenhum `electron.exe` do repositório ficou aberto.
2. **Travas do git:** nenhuma apareceu neste pedido. A regra de parar e perguntar está guardada para os próximos.

## O que não bateu com o contexto

1. **A ordem:** o pedido diz que vem antes do pedido 31.
   - O pedido 31 já estava feito até a Parte F quando este chegou.
   - No meio deste, você testou o rádio no jogo, e eu corrigi o app do jogo a seu pedido (os dois commits no começo deste relatório).
2. **"5 de 39 ficam entre 10 e 12 ms":** são 4 entre 10 e 12 ms e uma com 7,17 ms (`2026-10-17_16-17-08#0012`).
3. **"As voltas do app antigo fecham perto do cronômetro do jogo":** isso vale para as sessões de 11/10 e 13/10.
   - No conjunto do app antigo, há 5 voltas acima de 5 ms, incluindo as duas piores do store, de −21 e −20 ms.
   - Duas delas são explicadas pela travessia, e as outras três pelo gravador de junho (A.4).

**Observação:** o app do repositório que você abriu às 12:38 escreveu o `session-index.json` dentro da sessão de 15/10. É o comportamento conhecido do backend, que indexa a sessão ao ler. Eu não mudei nenhuma gravação.

## O que precisa de decisão

**A checagem principal do store continua reprovada** (p99 de 7,63 ms). Por isso:
- o relatório de evolução não atualiza;
- o botão "Atualizar coach e relatório" para no mesmo lugar;
- a contagem da M1 (3 de 5) segue provisória.

**As opções:**

1. **Medir o tempo do jogo na mesma linha** (proposta minha):
   - **como:** somar ao tempo do jogo a travessia dos 1,463 m nas duas pontas, 1,463 × (1/v no começo − 1/v no fim), com a velocidade gravada na passagem;
   - **o que não muda:** o limite (5 ms) e o que a checagem quer provar, que é "o período de s = 0 a s = 0 bate com o cronômetro do jogo";
   - **o que muda:** só a régua passa a medir na mesma linha;
   - **o resultado nas 676 voltas:** p99 de 3,56 ms, passando;
   - **o controle do pedido 16** (o store antigo dá cerca de −26 ms) continua valendo, porque o erro que ele mostra é de outro tamanho;
   - **depois:** registro a emenda em `docs/store_v2_e_evolucao.md` (1.3), com os testes, e rodo o `atualizar_coach`.
2. **Manter a checagem como está:** o store fica reprovado toda vez que uma volta começar ou terminar com uma passagem lenta pela linha. Isso acontece com pilotagem normal.
3. **Mudar o limite:** não recomendo, porque esconderia a causa em vez de medi-la direito.

**Também está pendente** (fora deste pedido): a sua sessão de hoje (`2026-10-18_12-38-44`, 15 voltas) entra no coach na próxima rodada do `atualizar_coach`, pela regra das sessões com mais de 5 voltas.

## Testes

- **backend:** `pytest tests`: **768 passaram**, em 9 min 37 s (saída em `_testes.txt`).
- **front:**
  - `tsc --noEmit`: sem erros;
  - `vitest`: 182 testes em 16 arquivos, todos passando.
- **Os testes que o pedido pede para uma correção** (a passagem entre duas amostras com Δt irregular, e o tempo e a posição do mesmo passo) não foram escritos, porque não houve correção no processamento nem no gravador.
- **A prova de que o gravador está certo** é medida nas gravações reais (A.1, A.3 e `_intervalos_por_sessao.csv`).
