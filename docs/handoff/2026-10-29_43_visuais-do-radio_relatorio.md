# Relatório do pedido 43: os 4 visuais do rádio e os números da voz no replay

- **Pedido:** `docs/prompts/2026-10-29_43_visuais-do-radio.md`.
- **Situação (01/11):** **parado na Parte E, como o pedido manda,** esperando o seu teste no jogo. As Partes A a D estão feitas, e a Parte F está feita até onde dá sem o jogo. Sem merge em `develop`.
- **Branch:** `etapa/visuais-do-radio`, a partir de `develop` (`4ac3d7af`).
- **Commits:**
  - `df26996f` Partes B e C no backend: os números da voz, os dados dos visuais na rota e a grade da sessão
  - `2ff1e92a` Parte C na tela Ao vivo
  - `920d5d83` Parte C no jogo: o app do jogo 0.4.2
  - `ab2d718d` Parte C: a faixa do trecho da fala mais forte sobre a pista; o replay de cada mensagem só pede a rota uma vez
  - `70d59270` Partes D e F: as prévias, a conferência dos rótulos e dos visuais, os limites do LuaJIT e a documentação
  - `f6de673a` C.4: a grade também lista a volta que o rádio não viu fechar na linha
  - `5c5e1bcb` o relatório, com a ponta a ponta e as saídas
  - o commit deste registro do envio (ver "O envio ao GitHub")
- **Arquivos de handoff** (`docs/handoff/`, prefixo `2026-10-29_43_visuais-do-radio_`):
  - `relatorio.md` (este), `patch.diff` e `pytest.txt`;
  - **as prévias:** `previas.png` (a folha com as 8), `c12_v2_antes.png`, `c12_v2_depois.png`, `boxes_com_a_grade.png` e `janela_com_o_backend_050.png`;
  - **a tela Ao vivo:** `ao_vivo_c12_v2.jpg`, `ao_vivo_c01_v13.jpg` e `ao_vivo_grade.jpg`;
  - **a conferência:** `rotulos_antes.json`, `rotulos_depois.json`, `visuais.json`, `radio_antes_21-10.json` e `radio_depois_13-10.json`, `_18-10.json` e `_21-10.json`;
  - **os scripts:** `radio_offline.py`, `radio_offline_antes.py`, `rodar_conferencia.sh`, `conferir_rotulos.py`, `medir_visuais.py`, `contar_locais.py`, `previa.py`, `fotografar.sh` e `folha.py`.

## Resumo

1. **Os números da voz estão no replay da frase do coach.** Na C12 da volta 2 de 21/10, o replay agora diz o que a voz disse: 16 m, 101 e 145 km/h e 0,64 s.
2. **O teste da Parte B.5:** os replays de frases do coach com um rótulo de outro número caíram de **15 em 15 para 0 em 14**. Uma frase ficou sem replay (a C11 da volta 15 de 21/10; ver a Parte B).
3. **Nas análises, continuam 5 em 5.** O pedido manda não mexer (B.4), mas o motivo não é o que o contexto supunha. Precisa de decisão sua (decisão 2).
4. **Os 4 visuais estão prontos** na tela Ao vivo e na janela do jogo. A tela Ao vivo foi conferida ponta a ponta. **A janela do jogo só foi vista por prévias:** o Lua ainda não rodou de verdade.
5. **A rota continua longe dos 60 KB:** no máximo 11,4 KB numa frase e 22,8 KB numa análise. O tempo de montar quase não mudou.
6. **Um requisito não foi cumprido como pedido:** na análise, o fim da diferença acumulada não é o "perde X s nesta curva". A diferença chega a 0,35 s. Não ajustei o número; precisa de decisão sua (decisão 1).
7. **Dois defeitos achados e corrigidos na conferência:** a tela Ao vivo pedia cada replay de novo a cada mensagem nova (40 vezes o mesmo replay numa sessão), e a grade escondia as voltas que o rádio não viu fechar.
8. **Suítes:** backend com 836 testes passando, front com 173 passando, `tsc` e build sem erro.

## O que precisa de você

**Primeiro, o teste no jogo:** os passos estão em "Parte E". **Depois, 4 decisões** (as razões estão nas Partes B e C):

1. **Na análise, o fim da diferença acumulada.** Recomendo a linha da análise cobrir o trecho inteiro da curva, começando em zero na entrada do trecho, com a animação como está. O fim da linha passa a ser exatamente o "perde X s". A alternativa é esticar a animação até o trecho, o que acrescenta cerca de 4 s na C01 e 5 s na C14, e o replay pode não caber na janela de rádio.
2. **Na análise, os rótulos do replay.** O cartão diz "freada 42 m antes" e o replay diz "você freia 76 m antes", porque um é a mediana das 3 voltas e o outro é uma volta só. Recomendo aplicar a sua regra de 29/10 aqui também: os rótulos com os números do cartão, e as linhas continuando as da volta mais perto da mediana.
3. **Na frase do coach, o traçado.** O coach não mede o lado, então o replay da frase não tem a seta nem o número. Recomendo deixar assim. A alternativa seria o coach passar a medir, o que muda critério do coach.
4. **Na grade, as frases do coach em voltas de fora.** Só 1 das 18 frases caiu numa volta da grade, então quase nenhuma aparece marcada. Recomendo listar as curvas citadas na linha de cada volta de fora ("volta 12: ... citada: C11").

## Parte A: as conferências

1. **Os caminhos do contexto batem:**
   - `backend/core/radio/replay.py` e a rota `GET /api/radio/replay/{id}` em `backend/routers/radio.py`;
   - a janela em `tools/csp_app/radio_engenheiro/radio_engenheiro.lua`;
   - a tela em `frontend/src/aoVivo/ReplayDaCurva.tsx`, e o `QuadroDeRotulos` em `frontend/src/aoVivo/replay.ts`.
2. **O antes:** reproduzi, com o código de `develop`, a frase da C12 da volta 2 de 21/10. Os números são os da tabela do contexto: 16 m contra 56 m, 101 e 145 contra 90 e 98 km/h, 0,64 s contra 0,92 s.
3. **O que a frase do coach carrega:**

   | medida | o número | o ponto da pista |
   |---|---|---|
   | a freada | `brakeDeltaM` | **guardado:** `yourBrakeOnsetM` e `referenceBrakeOnsetM` |
   | as mínimas | `yourMinSpeedKmh` e `referenceMinSpeedKmh` | **não guardado:** achado pela regra do coach, a menor velocidade dentro do microssetor, em cada grade |
   | o tempo | `lossSeconds` | o microssetor (`microsector`) |
   | o traçado | **o coach não mede** | não há |

4. **As grades:** a volta ao vivo e a referência têm relógio, velocidade, freio, acelerador e lateral na grade oficial. Não faltou nenhuma; nada de física nova e nada de modelo.

## Parte B: os números da voz

**A C12 da volta 2 de 21/10, antes e depois** (`c12_v2_antes.png` e `c12_v2_depois.png`). A fala é "Curva 12, esquerda: 6 décimos atrás da IA. Freia 16 metros antes da IA."

| | antes | depois |
|---|---|---|
| o alto | perde 0,92 s nesta curva | perde 0,64 s no trecho da fala |
| a freada | você freia 56 m antes da IA | você freia 16 m antes da IA |
| as mínimas | 90 e 98 km/h | 101 e 145 km/h |
| o traçado | você passa 0,5 m mais à esquerda | não aparece |
| o trecho da fala | não existia | faixa clara, com o rótulo |
| as linhas e os carros | a curva inteira | a curva inteira |

**A contagem da Parte B.5** (replays com algum rótulo cujo número não está na mensagem, antes → depois):

| sessão | frases do coach | análises |
|---|---|---|
| 13/10 | 5 de 5 → 0 de 5 | 1 de 1 → 1 de 1 |
| 18/10 | 3 de 3 → 0 de 3 | 2 de 2 → 2 de 2 |
| 21/10 | 7 de 7 → 0 de 6 | 2 de 2 → 2 de 2 |
| **total** | **15 de 15 → 0 de 14** | **5 de 5 → 5 de 5** |

- **"Na fala" é o cartão ou a voz.** O pedido pede o arredondamento do cartão (B.1) e a conferência contra a fala (B.5), e os dois não coincidem: o cartão diz "+0,64 s", e a voz diz "6 décimos". Contando só a voz, 13 das 14 frases têm algum número que só está no cartão: esse tempo, e as mínimas quando a voz fala da freada. Os números vêm todos do coach.
- **Na análise, o contexto não bate por inteiro.** A medida é a mesma, mas o valor pode não ser: o replay mostra a volta mais perto da mediana, e o cartão mostra a mediana de cada medida. Os 7,9 m da C01 batiam porque a mediana caiu nessa volta. Na análise das voltas 9, 11 e 13 de 21/10, o cartão diz "freada 42 m antes", e o replay, "você freia 76 m antes". Não mudei nada (B.4); é a decisão 2.

**O que decidi e você pode querer rever:**

- **A janela cresce na frase do coach,** para conter o microssetor e as freadas do coach. É necessário: o microssetor 39, que o coach chama de "Curva 11", vai de 2.745 a 2.817 m, quase todo na saída da C10, e a janela da C11 começa em 2.800 m. As linhas continuam cobrindo a curva inteira.
- **Sem a freada na voz, sem marca de freada,** como nas frases da C11. Marcar a freada ali mostraria um ponto que a voz não citou.
- **O traçado saiu da frase do coach,** pelo item B.2 ("não invente um ponto"). É a decisão 3.
- **O relógio tem de cobrir a janela crescida.** Na C11 da volta 15 de 21/10, a grade só tinha pontos a partir de 38 m dentro do trecho, e a linha saía errada (−0,23 s, com a voz dizendo 0,68 s). Essa frase agora fica sem replay, como já acontecia com uma curva sem relógio medido.

**As mínimas da grade contra as da voz:** a marca fica no ponto mais lento da grade, e o rótulo é o número do coach. Os dois diferem pouco: até 2,3 km/h na sua volta (mediana de 0,6) e até 1,2 km/h na referência. O coach mede nos quadros, e a grade é a projeção deles.

## Parte C: os visuais

As prévias estão em `previas.png`. Sob a animação, de cima para baixo: o pedal, a diferença acumulada e a velocidade, com um cursor de cada cor onde cada carro está.

### C.1 e C.3: a velocidade e o pedal

- **Os dados vêm da rota do replay.** O tempo e o pedal já vinham; entraram a velocidade em cada ponto, o passo da grade e a distância de cada marca.
- **As cores do pedal** são as do mapa aproximado, sem limiar novo: freio a partir de 0,15, acelerador cheio a partir de 0,9.
- **Os eixos não têm número,** só a unidade: "velocidade (km/h) pela distância (m)". Na frase do coach, um número no eixo quebraria a regra de só escrever o número da voz. Na análise, segui igual para os visuais serem os mesmos.

### C.2: a diferença acumulada

**Na frase do coach, a subida dentro do trecho da fala contra o tempo da voz:**

| sessão | msg. | curva e volta | microssetor | a voz e o cartão (s) | a subida no trecho (s) | diferença (s) | dentro de 0,05 s |
|---|---|---|---|---|---|---|---|
| 13/10 | 3 | C11, v4 | 39 | 1,138 | 1,159 | +0,021 | sim |
| 13/10 | 5 | C12, v4 | 44 | 1,869 | 1,860 | −0,009 | sim |
| 13/10 | 7 | C12, v5 | 44 | 0,734 | 0,740 | +0,006 | sim |
| 13/10 | 13 | C11, v9 | 39 | 0,503 | 0,442 | −0,061 | **não** |
| 13/10 | 15 | C12, v11 | 44 | 4,387 | 4,371 | −0,016 | sim |
| 18/10 | 3 | C11, v4 | 39 | 1,253 | 1,210 | −0,043 | sim |
| 18/10 | 10 | C11, v9 | 39 | 0,456 | 0,425 | −0,031 | sim |
| 18/10 | 11 | C08, v10 | 33 | 0,848 | 0,864 | +0,016 | sim |
| 21/10 | 3 | C12, v2 | 44 | 0,635 | 0,645 | +0,010 | sim |
| 21/10 | 7 | C11, v5 | 39 | 0,647 | 0,592 | −0,055 | **não** |
| 21/10 | 15 | C11, v12 | 39 | 0,488 | 0,448 | −0,040 | sim |
| 21/10 | 20 | C12, v15 | 44 | 0,716 | 0,725 | +0,009 | sim |
| 21/10 | 26 | C11, v19 | 39 | 0,484 | 0,454 | −0,030 | sim |
| 21/10 | 27 | C12, v19 | 44 | 1,034 | 1,063 | +0,029 | sim |

- **12 das 14 ficam dentro do arredondamento da voz, que fala em décimos** (0,05 s). **As outras 2 passam por pouco (−0,061 e −0,055 s).** Pelo arredondamento do cartão (0,005 s), só 1 das 14 bate.
- **Por que não bate exatamente:** os dois medem diferente. O coach usa os quadros, com a passagem interpolada, e a referência do modelo; o replay usa a grade da volta ao vivo e a volta do store. Na C11, a diferença é para menos em 6 das 7 frases, o que sugere um desvio na referência desse microssetor. Não investiguei a causa e não ajustei nenhum número.

**Na análise, o fim da linha contra o "perde X s nesta curva":**

| sessão | msg. | curva e volta | fim da linha (s) | perde X s nesta curva | diferença (s) |
|---|---|---|---|---|---|
| 13/10 | 11 | C01, v7 | 0,950 | 1,090 | −0,140 |
| 13/10 | 11 | C11, v6 | 0,648 | 0,703 | −0,055 |
| 18/10 | 8 | C04, v3 | 1,116 | 1,040 | +0,076 |
| 18/10 | 8 | C01, v3 | 0,709 | 0,951 | −0,242 |
| 18/10 | 16 | C01, v12 | 0,554 | 0,864 | −0,310 |
| 18/10 | 16 | C05, v12 | 0,353 | 0,550 | −0,197 |
| 21/10 | 18 | C01, v13 | 0,505 | 0,805 | −0,300 |
| 21/10 | 18 | C12, v11 | 0,644 | 0,507 | +0,137 |
| 21/10 | 25 | C01, v17 | 1,044 | 1,209 | −0,165 |
| 21/10 | 25 | C10, v16 | 0,808 | 0,457 | +0,351 |

**Este requisito não foi cumprido como pedido.** A linha vai da entrada à saída do replay, e a perda é a do trecho da curva, do meio da reta anterior ao meio da seguinte. Os dois não coincidem: o trecho da C01 começa 300 m antes da entrada do replay, e o da C14 termina 386 m depois da saída. Para a linha terminar na perda, ela tem de cobrir outro pedaço da pista, e não ajustei o número. A linha não escreve valor nenhum, para não mostrar dois números diferentes na mesma tela. É a decisão 1.

### C.4: a grade da sessão

- **A perda é a da análise.** Nas 10 curvas citadas pelas 5 análises das 3 sessões, a célula da curva, na volta citada, tem exatamente o número que a análise usou.
- **A cor:** laranja quando você perde, azul quando ganha, mais forte até 1 s. O valor de 1 s é escolha minha.
- **As curvas citadas** ficam com o contorno vermelho: a análise, na volta da mediana (a do replay); a frase do coach, na volta dela. **O resumo na linha ("mais perdeu na curva 12") não marca:** é só a maior célula da linha.
- **As voltas de fora,** com o motivo: a IA, a volta incompleta, a rodada, a volta sem as medidas e a que o rádio não viu fechar na linha.
- **Quase nenhuma frase do coach aparece marcada:** das 18 frases das 3 sessões, só 1 caiu numa volta da grade (0 de 5, 1 de 3 e 0 de 10). É a decisão 4.

**Duas coisas que vi e não investiguei:**

- **Voltas de tempo normal saem como incompletas,** como a volta 10 de 21/10 (1:29,518), e por isso ficam fora da análise e da grade. Em 21/10, são 9 das 19 voltas que o rádio viu fechar. A regra é do coach, e não mexi nela. Isso reduz bastante o que a análise e a grade enxergam, e vale um pedido próprio.
- **A numeração das voltas tem buracos.** Em 13/10, o número 10 aparece duas vezes e o 9 não aparece, porque a passagem saiu com o contador do jogo já adiantado. A grade mostra o que o rádio recebeu.

### A janela pequena (a minha proposta, na sua ordem de importância)

O replay fica com pelo menos 150 px. Sai primeiro a velocidade, depois a diferença e por último o pedal.

| janela | o que entra |
|---|---|
| 300 × 300 e 420 × 300 (a de abertura) | o replay, o pedal e a diferença |
| 314 px de altura ou mais | os três visuais |
| boxes, 672 × 480, com a grade de 6 voltas | os três visuais e a grade (`boxes_com_a_grade.png`) |
| boxes, 672 × 480, com a grade de 8 voltas | o replay, o pedal, a diferença e a grade |

**Na janela de abertura, a velocidade não aparece.** Para vê-la, é preciso esticar a janela. Se você a deixar em 420 × 480, tudo entra também nos boxes.

## Parte D: os testes e as conferências

- **Backend:** `pytest tests`, **836 testes, todos passando** (10 min), no código final (`f6de673a`). Entraram 4 em `test_radio.py`.
- **Front:** `vitest run`, **173 testes, todos passando** (entraram 9); `tsc` sem erro; `vite build` sem erro.
- **Lua:**
  - **`conferir_lua.py`:** 0 erros de léxico, blocos fechados, 47 chamadas da API (entraram `ui.drawQuadFilled` e `ui.drawRect`) e 12 métodos, todos no SDK instalado;
  - **os limites do LuaJIT (`contar_locais.py`):** 141 locais no nível de cima, de 200, e no máximo 23 upvalues, de 60. O script é uma conta aproximada. Passar de um limite calaria o app inteiro, e o `conferir_lua.py` não vê isso;
  - **o caminho sem os campos novos:** a prévia com a rota de antes (`janela_com_o_backend_050.png`) saiu igual ao replay de antes, sem visuais. No código, a grade trata o 404 da rota: fica sem ela e registra uma vez no log.
- **O que não foi testado:** não há interpretador de Lua neste computador, então o código Lua novo **nunca rodou.** As prévias repetem as contas num HTML, mas não executam o Lua. O teste é o seu.

**O tamanho da rota e o tempo para montar** (as 3 sessões, com a voz de verdade):

| | frase do coach, antes | frase do coach, depois | análise, antes | análise, depois |
|---|---|---|---|---|
| o tamanho | 6,7 a 8,2 KB | 8,3 a 11,4 KB | 15,7 a 18,3 KB | 19,6 a 22,8 KB |
| o tempo (mediana) | 3,4 ms | 3,8 ms | 3,9 ms | 4,0 ms |

Nenhuma análise chegou perto dos 60 KB, então não precisei propor uma grade mais grossa.

**A tela Ao vivo, ponta a ponta** (01/11):

- **Como:** o backend do repositório na porta 8011, com as pastas isoladas no rascunho, o reprodutor tocando 21/10 desde a volta 1 e a tela numa aba "[teste]". No fim, parei a reprodução, o backend e o front, e fechei a aba.
- **A primeira passagem, de 29/10, se perdeu:** o backend foi encerrado junto com o app às 18:25, sem erro no log. O `exit code 4` veio daí, e não do código. Foi essa passagem que mostrou os pedidos repetidos. Repeti tudo, depois do seu "tente novamente".
- **O resultado:**
  - a frase da C12 da volta 2 saiu com o replay, os números da voz, o trecho da fala e os visuais (`ao_vivo_c12_v2.jpg`);
  - o replay da análise das voltas 9, 11 e 13 saiu com os visuais (`ao_vivo_c01_v13.jpg`);
  - a grade mostrou as voltas 9, 11 e 13, com o contorno na C12 da volta 11 e na C01 da volta 13, e as voltas de fora com o motivo, sem rolagem lateral (`ao_vivo_grade.jpg`).
- **Os pedidos do replay:** o mesmo replay era pedido até 40 vezes na passagem de 29/10. Agora, são 2 pedidos a cada abertura da tela: o modo estrito do front de desenvolvimento monta o componente duas vezes. A causa era a chave do cartão, que dependia da posição na lista, e o defeito vinha do pedido 36.
- **O que esta passagem não cobre:** o backend dela subiu antes de `f6de673a`, então as voltas 8 e 14 ainda não apareceram entre as de fora na tela. A correção foi conferida pelo teste e pelas passagens fora do tempo real.
- **O console:** 57 erros de conexão recusada, do front que abriu antes de o backend responder. Recarregando com o backend no ar, não surgiu nenhum novo. Na primeira passagem, o log do backend também teve o erro "attached to a different loop" do envio por WebSocket; não investiguei se é só do reprodutor. Não olhei esse erro na segunda passagem.

**Não apaguei nenhuma gravação nem copiei gravações. Não gravei na pasta do jogo, não instalei pacote e não gerei instalador.** O coach, os modelos, o store e os critérios não mudaram.

## Parte E: o teste no jogo (é com você)

**Antes de começar, duas coisas mudaram:**

- **O Custom Shaders Patch instalado agora é o 0.3.1,** atualizado em 31/10. O app foi feito para a 0.2.11. A conferência passa contra o SDK novo, mas esta é a primeira vez que o app roda nessa versão. Se algo do app falhar sem motivo aparente, olhe primeiro para isso.
- **A versão nova do app do jogo é a 0.4.2.** Escolhi esse número para não confundir com o app 0.5.0-radio-e-replay do Windows.

**Os passos:**

1. **Feche o jogo e o app instalado, inclusive o ícone na bandeja.**
2. **Instale o app do jogo 0.4.2.** A pasta tem de estar na branch `etapa/visuais-do-radio`:
   ```powershell
   git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer branch --show-current
   ```
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Dokas\Desktop\f1-telemetry-analyzer\tools\csp_app\instalar.ps1
   ```
3. **Abra o app pelo repositório.** Ele grava em `C:\Users\Dokas\Desktop\f1-telemetry-analyzer\data\recordings`, e não na pasta do app instalado:
   ```powershell
   $env:AT_BACKEND_USE_PYTHON_RUNNER='true'; cd C:\Users\Dokas\Desktop\f1-telemetry-analyzer\desktop; npm.cmd run desktop:prod:autostart
   ```
4. **No jogo, ligue as 4 janelas** na barra de apps: "Rádio", "Minimapa", "Mapa aproximado" e "Replay da curva". Ponha o replay num canto, sem cobrir o centro, e **estique-o para 420 × 480**, para os três visuais aparecerem.
5. **Na tela Sistema, clique em "Mandar mensagem de teste".** O cartão e a voz têm de sair no jogo.
6. **Ande pelo menos 8 voltas, você mesmo, e vá aos boxes depois da 3ª volta válida,** para ver a grade. Ela só aparece nos boxes ou com o jogo pausado, embaixo da janela grande.
7. **Nunca aperte Ctrl+C:** ele passa o carro para a IA, e o rádio se cala.
8. **Desligue o replay por 2 ou 3 voltas e ligue de novo,** para a medida do FPS. Deixe a tela Ao vivo aberta no app.
9. **Em cada fala, anote** se os números do replay são os que você ouviu e se os visuais mostram a curva certa.
10. **Avise: "testei os visuais no jogo".**

**Depois do teste, o app do jogo 0.4.2 fica instalado.** Ele funciona com o app 0.5.0 instalado: sem os campos novos, a janela mostra o replay como hoje, sem visuais e sem a grade. **O contrário não funciona:** o app do jogo 0.4.1 com o backend novo daria erro na janela do replay nas frases do coach, que vêm sem o traçado. Por isso o passo 2 não pode ser pulado.

**Depois do seu aviso, eu:**

- confiro o registro do rádio e os replays entregues;
- leio, sem mudar nada, as linhas `[radio_engenheiro]` do log do CSP;
- meço o FPS com o replay ligado e desligado;
- completo este relatório e a documentação, com as suas 4 decisões;
- faço o merge em `develop` e o envio.

## Parte F: a documentação

Feita, faltando o FPS no jogo e as decisões:

- **`docs/realidade_aumentada.md`:** seção 5.4.1, com a regra dos números da voz, o trecho da fala, os 4 visuais, de onde vem cada dado, onde aparecem e o custo; e a rota nova;
- **ADR 0021:** a linha de atualização;
- **`docs/dashboard_inventario.md`:** "O que o pedido 43 entregou";
- **`docs/tecnica_de_pilotagem_lista.md`:** a linha D3 e o histórico.

## O envio ao GitHub

- **Antes do envio, conferi nos commits:** o maior arquivo tem 420 KB (nada acima de 50 MB); nenhum arquivo em `recordings/`, `data/recordings` ou `data/ml`; nenhum segredo.
- **O envio:** `etapa/visuais-do-radio`, branch nova, sem forçar. `develop`, `main` e as tags não foram.

  | ref | hash local | hash no remoto (`git ls-remote origin`) |
  |---|---|---|
  | `refs/heads/etapa/visuais-do-radio` | `5c5e1bcb7abcbc8becdfd09b0ae814f25a2a34b6` | `5c5e1bcb7abcbc8becdfd09b0ae814f25a2a34b6` |

- **O commit deste registro** foi enviado em seguida. O hash final da branch está no chat.

## O que falta

- **De você:** o teste no jogo (os passos na Parte E) e as 4 decisões ("O que precisa de você").
- **De mim, depois do seu aviso:** a conferência do registro e do log do CSP, o FPS, o fechamento da documentação, o merge em `develop` e o envio.
