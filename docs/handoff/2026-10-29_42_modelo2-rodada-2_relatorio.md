# Pedido 42 — relatório parcial de 20/11: os rótulos pelos critérios da literatura e a concordância com as quatro rodadas; parado

- **Pedido:** `docs/prompts/2026-10-29_42_modelo2-rodada-2.md`, com a "Atualização de 20/11" (itens 3 a 5; depois, gravar o relatório parcial e parar).
- **Data:** 20/11/2026.
- **Pasta:** `C:\Users\Dokas\Desktop\f1-telemetry-analyzer-48`. A atualização estava só nela, sem commit, e foi commitada antes de tudo (`8d067698`). A pasta principal (pedido 52) estava limpa e não foi tocada.
- **Branch:** `etapa/modelo2-rodada-2`. O remoto estava em `51b987db`: você enviou a etapa anterior.
- **Commits desta etapa:**
  - `8d067698` — o texto da atualização de 20/11;
  - `844c7197` — os critérios registrados antes de rodar (seção 7 de `docs/modelo2_tecnica_e_estilo.md` e linha no ADR 0023);
  - `efac71ba` — o código, antes de rodar: o módulo dos rótulos (`backend/ml/modelo2/rotulos_literatura.py`), quem o chama (`literatura_execucao.py` e `ml/scripts/modelo2_literatura.py`) e os testes;
  - o commit das saídas, da concordância, da galeria, da H.4 do 38 e deste relatório (o hash está no chat e na nota da sessão).
- **Merges:** nenhum.
- **Arquivos de handoff gerados nesta etapa (`docs/handoff/2026-10-29_42_modelo2-rodada-2_*`):**
  - `2026-11-20_42_rotulos_literatura.csv`: os 120 rótulos;
  - `literatura_e3_saidas_de_0111.json`: o teste do E3 nas 7 saídas;
  - `literatura_rotulos_resumo.json`;
  - `literatura_concordancia.json`: as tabelas 2×2 das quatro rodadas;
  - `galeria_rodada4.html`;
  - `pytest.txt`, atualizado;
  - este relatório.

  Fora do handoff: a seção da H.4 em `docs/handoff/2026-10-24_38_modelo2-erro-tecnica-e-estilo_relatorio.md`.

## Resumo

1. **Os 5 critérios** foram registrados antes de qualquer conta (seção 7), com as margens, o porquê e as fontes.
   - O módulo do rótulo não importa os detectores nem a calibração, e não lê estados nem gabaritos.
   - Isso é conferido por um teste e nas duas rodadas do script: `detectores_carregados: false`.
2. **O teste do E3 nas 7 saídas de traseira de 01/11:** o critério diz "aplica" nas **7**, incluindo as duas da C06 (com 81° e 83° de deriva). Por isso não parei.
3. **Os 120 rótulos estão no CSV.**

   | pergunta | aplica | nao aplica | nao sei |
   |---|---|---|---|
   | F4 | 8 | 4 | 12 |
   | F5 | 3 | 14 | 7 |
   | M6 | 8 | 6 | 10 |
   | E2 | 16 | 3 | 5 |
   | E3 | 9 | 0 | 15 |

4. **A concordância com a rodada 4** (a que vale), nas passagens em que o critério e o detector decidem:
   - E2: acordo de 0,857 e kappa de 0,659;
   - F4: 0,833 e 0,571;
   - M6: 0,769 e 0,552;
   - F5: 0,688 e 0,375;
   - E3: 0,571 e 0,000.

   As amostras são pequenas: de 7 a 16 passagens por pergunta.
5. **O que a concordância mostra entre as rodadas:**
   - o M6 melhora da rodada 1 (kappa 0,000) para a 2 (0,552);
   - o F5 piora na rodada 2 (−0,085) e volta na 3 e na 4 (0,375), o que confirma o defeito da entrada da rodada 2;
   - o F4 e o E3 não mudam entre as rodadas;
   - o E2 fica entre 0,659 e 0,800.
6. **A galeria da rodada 4** está gerada. **A seção da H.4** foi escrita no relatório do 38, com os nomes novos.

## Os dados e o jogo

- **Os vínculos:** os 3 de `data/reference_models` continuam iguais aos da pasta principal, conferidos de novo pelo SHA-256 em 20/11 (`811da4c9…`, `f8e61864…` e `e8651d45…`).
- **O store:** é o mesmo das rodadas 2 a 4 (meta de 17/11, 21:31, `aprovado: true`).
- **O jogo:** o `acs.exe` estava fechado antes de cada conta (o E3, os rótulos e a galeria).
- **As voltas:** as 144 da rodada 1, lidas sem gravar nada (o `carregar` sem pasta de saída).

## Item 3: o registro, antes de rodar (`844c7197`)

**A seção 7 de `docs/modelo2_tecnica_e_estilo.md`** tem:

- o nome novo do resultado;
- a independência;
- os três resultados;
- os 5 critérios, com os números da literatura e as margens escolhidas pelo projeto, cada uma com o porquê;
- a ordem dos passos;
- as fontes do item 6.

**As coincidências com os limiares dos detectores, ditas na seção:** só o 5% de freio do F5. Ele vem da Virtual Racing School, e o detector usa 0,05 como "pedal acionado", com outro sentido. As outras margens foram escolhidas diferentes das dos detectores:

- 0,25 do volante para "começa a virar", contra o 0,15 do detector;
- 0,08 e 0,20 na queda do acelerador, contra o 0,05 e o 0,15 do M8;
- 0,04 na gagueira;
- 0,35 g e 0,5 g no E2, contra o 0,4 g do detector.

**A linha no ADR 0023** foi no mesmo commit. **A seção 3.3** do documento também passou a usar o nome novo.

## A referência do próprio carro (E2 e E3)

Das 130 voltas do Eduardo, nos 47.192 pontos com 0,10 g ≤ |a_y| ≤ 0,35 g e v ≥ 50 km/h:

| medida | valor |
|---|---|
| L (pedido 39) | 2,9636 m |
| k_δ (pedido 39) | 0,30396 rad |
| gradiente de subesterço K_us | 0,00143 rad/g (0,08°/g: o carro é quase neutro na faixa linear) |
| intercepto | −0,00017 rad |
| μ (o percentil 99 de \|a_y\|) | 2,74 g |

## Item 5.2: o E3 da literatura nas 7 saídas de traseira de 01/11

| volta relatada | curva | volta na gravação | rótulo | o sinal que disparou | contraesterço | maior \|β\| | guinada acima da referência |
|---|---|---|---|---|---|---|---|
| 3 | C05 | #0002 | aplica | guinada acima da referência | 0,00 s | 1,9° | 0,54 rad/s, por 1,0 s |
| 3 | C06 | #0002 | aplica | deriva ≥ 10° + guinada | 0,00 s | 81,3° (≥ 10° por 2,5 s) | 1,78 rad/s |
| 3 | C13 | #0002 | aplica | guinada acima da referência | 0,12 s | 9,1° | 3,42 rad/s |
| 4 | C02 | #0003 | aplica | guinada acima da referência | 0,00 s | 3,1° | 0,21 rad/s, por 0,49 s |
| 4 | C06 | #0003 | aplica | contraesterço + deriva ≥ 10° + guinada | 0,15 s | 82,8° (≥ 10° por 2,8 s) | 0,95 rad/s |
| 10 | C05 | #0009 | aplica | contraesterço + guinada | 0,22 s | 3,3° | 0,49 rad/s, por 1,6 s |
| 11 | C01 | #0010 | aplica | contraesterço + deriva ≥ 10° + guinada | 0,41 s | 20,2° (≥ 10° por 0,9 s) | 3,09 rad/s |

- **As duas da C06** (as rodadas, com mais de 59° no E3 do detector) são pegas pela deriva de 10° ou mais.
- **O detector E3 disse "aplica" em 5 das 7** nas rodadas 1 e 2 (relatório de 17/11); as emendas das rodadas 3 e 4 não tocam o E3. As duas da C05 o detector não pegou. O critério pega as duas: uma pela guinada acima da referência e a outra pelo contraesterço e pela guinada.
- **Um cuidado:** nas voltas 3 e 4, o carro ficou parado em 41% a 49% das amostras. A janela do E3 pega o carro parado ou girando devagar, e por isso o tempo "acima da referência" passa de 24 s na C13 e na C06. O rótulo continua certo (as duas são saídas relatadas), mas o número de segundos não deve ser lido como duração de uma saída.
- **Também uma revocação só sobre os casos relatados:** a lista não tem "não aplica".

## Item 5.3: os rótulos das 120 passagens

- **O CSV:** `data/ml/modelo2/rotulagem/2026-11-20_42_rotulos_literatura.csv` (sha256 `ce22d4d7…`), com cópia em `docs/handoff/2026-10-29_42_modelo2-rodada-2_2026-11-20_42_rotulos_literatura.csv`.
- **As colunas:** o id do kit, a pergunta, a curva, o rótulo, o critério que decidiu, o valor medido e a margem.
- **O CSV do 38** continua vazio.
- **O que chama a atenção:**
  - **E3:** o critério nunca diz "nao aplica" nessas 120. A regra de "nao aplica" exige a guinada sempre dentro da referência (até 0,05 rad/s) e a deriva abaixo de 5°, e passagens normais de corrida passam disso. São 9 "aplica" e 15 "nao sei";
  - **F4:** 12 "nao sei", a metade. Neles, a última parte da soltura fica entre a rampa e o degrau, perto de uma descida reta;
  - **F5:** 14 "nao aplica", quase sempre com freio abaixo de 4% quando o volante passa de 25% do maior.

  Nada disso muda: os critérios ficam como foram registrados.

## Item 5.4: a concordância com as quatro rodadas

- **A tabela 2×2:** o rótulo nas linhas e o detector nas colunas.
  - aa: os dois dizem aplica;
  - an: o rótulo diz aplica e o detector, não aplica;
  - na: o rótulo diz não aplica e o detector, aplica;
  - nn: os dois dizem não aplica.
- **O que entra:** só as passagens em que os dois decidem. Os "nao sei" do critério e os "não conclusivos" do detector ficam à parte.

| pergunta | rodada | usadas | aa | an | na | nn | acordo | kappa | rótulo nao sei | detector não conclusivo |
|---|---|---|---|---|---|---|---|---|---|---|
| F4 | 1 | 12 | 8 | 0 | 2 | 2 | 0,833 | 0,571 | 12 | 0 |
| F4 | 2 | 12 | 8 | 0 | 2 | 2 | 0,833 | 0,571 | 12 | 0 |
| F4 | 3 | 12 | 8 | 0 | 2 | 2 | 0,833 | 0,571 | 12 | 0 |
| F4 | 4 | 12 | 8 | 0 | 2 | 2 | 0,833 | 0,571 | 12 | 0 |
| F5 | 1 | 16 | 3 | 0 | 5 | 8 | 0,688 | 0,375 | 7 | 1 |
| F5 | 2 | 16 | 1 | 2 | 6 | 7 | 0,500 | -0,085 | 7 | 1 |
| F5 | 3 | 16 | 3 | 0 | 5 | 8 | 0,688 | 0,375 | 7 | 1 |
| F5 | 4 | 16 | 3 | 0 | 5 | 8 | 0,688 | 0,375 | 7 | 1 |
| M6 | 1 | 12 | 0 | 6 | 0 | 6 | 0,500 | 0,000 | 10 | 2 |
| M6 | 2 | 13 | 4 | 3 | 0 | 6 | 0,769 | 0,552 | 10 | 1 |
| M6 | 3 | 13 | 4 | 3 | 0 | 6 | 0,769 | 0,552 | 10 | 1 |
| M6 | 4 | 13 | 4 | 3 | 0 | 6 | 0,769 | 0,552 | 10 | 1 |
| E2 | 1 | 12 | 8 | 1 | 0 | 3 | 0,917 | 0,800 | 5 | 7 |
| E2 | 2 | 14 | 9 | 2 | 0 | 3 | 0,857 | 0,659 | 5 | 5 |
| E2 | 3 | 14 | 9 | 2 | 0 | 3 | 0,857 | 0,659 | 5 | 5 |
| E2 | 4 | 14 | 9 | 2 | 0 | 3 | 0,857 | 0,659 | 5 | 5 |
| E3 | 1 | 7 | 4 | 3 | 0 | 0 | 0,571 | 0,000 | 15 | 2 |
| E3 | 2 | 7 | 4 | 3 | 0 | 0 | 0,571 | 0,000 | 15 | 2 |
| E3 | 3 | 7 | 4 | 3 | 0 | 0 | 0,571 | 0,000 | 15 | 2 |
| E3 | 4 | 7 | 4 | 3 | 0 | 0 | 0,571 | 0,000 | 15 | 2 |

**A leitura:**

- **A rodada 4 é a que vale.** Nela, o E2 e o F4 têm concordância moderada a boa (kappa 0,66 e 0,57). O M6 tem 0,55, e o F5 0,38.
- **O E3 tem kappa zero** em todas as rodadas, porque o critério nunca diz "nao aplica". O acordo de 0,571 vem só das passagens que os dois chamam de "aplica" (4 de 7).
- **O caminho até a rodada 4 aparece na concordância:**
  - o M6 da rodada 1 nunca dizia "aplica" (kappa 0), e a retomada nova o faz concordar;
  - o F5 da rodada 2 piorou (o defeito da entrada) e voltou nas rodadas 3 e 4.
- **O M6 é o rótulo menos independente** (seção 7.4): desde a rodada 2, a regra do detector já mede a subida contínua. A concordância dele tem de ser lida com isso.
- **As amostras são pequenas:** de 7 a 16 passagens por pergunta, depois de tirar os "nao sei" e os "não conclusivos". Os kappas têm incerteza grande e não foram dados com intervalo.
- **Nenhuma regra muda por causa disso,** como manda o item 2 de 18/11, à tarde.

**Um detalhe técnico dos gabaritos:** nos gabaritos do kit 2 das rodadas 3 e 4 (`rodada3/kit2_gabarito.json` e `rodada4/kit2_gabarito.json`), o campo com o estado se chama `estado_rodada2`, mas guarda o estado da rodada da pasta. O nome veio do código da rodada 2. A concordância lê esse campo em cada pasta, e o comentário no código diz isso.

## Item 5.5: a galeria da rodada 4

- **Os arquivos:** `data/ml/modelo2/literatura/galeria_rodada4.html`, com cópia em `docs/handoff/2026-10-29_42_modelo2-rodada-2_galeria_rodada4.html`.
- **O conteúdo:** para cada pergunta, a página da literatura e até 3 passagens "aplica" e 3 "não aplica" da rodada 4 (semente 42). Elas trazem a Volta de referência e a Sua melhor volta, como no kit 2. Aqui o estado e a origem aparecem, porque a galeria não é para rotular.
- **O que foi sorteado:**

  | pergunta | aplica: eu | aplica: IA | não aplica: eu | não aplica: IA |
  |---|---|---|---|---|
  | F4 | 2 | 1 | 0 | 1 |
  | F5 | 2 | 1 | 2 | 1 |
  | M6 | 2 | 1 | 2 | 1 |
  | E2 | 3 | 0 | 2 | 1 |
  | E3 | 3 | 0 | 2 | 1 |

- **Um achado da galeria:** o F4 da rodada 4 **nunca diz "não aplica" numa passagem minha.** São 0 de 1.820; só 6 passagens da IA. Por isso a galeria do F4 tem só 1 "não aplica".
  - O limiar do F4 (a taxa de soltura ≤ 3,0/s menos a faixa) quase sempre é cumprido por mim.
  - No critério da literatura, o F4 tem 4 "nao aplica" nas 120 (penhasco ou gagueira).
  - Fica registrado como trabalho futuro, sem mudança de regra.
- **O E2 e o E3 da IA** só têm "aplica" ou "não aplica" na volta com a guinada (22/10). A galeria pegou 1 "não aplica" dela em cada.

## Item 5.6: a H.4 no relatório do 38

Uma seção nova no fim de `docs/handoff/2026-10-24_38_modelo2-erro-tecnica-e-estilo_relatorio.md`. Ela diz que a H.4 virou "concordância com um critério independente da literatura" e dá a tabela da rodada 1 (as regras do 38). Para as outras rodadas, ela aponta para este relatório.

## Os testes

- **`backend/tests/test_modelo2_literatura.py`,** 6 testes com traços sintéticos:
  - **a independência:** o módulo do rótulo e quem o chama não importam os detectores, a calibração nem a rotulagem;
  - **F4:** a rampa, o degrau, o penhasco, a gagueira e "sem frenagem";
  - **F5:** com e sem trail braking;
  - **M6:** a subida contínua e o alívio;
  - **E2 e E3:** neutro, subesterço de 2°, deriva e "sem guinada";
  - **a reta do carro:** acha o gradiente.
- **A suíte do backend:** 1.070 passam, nenhuma falha (8 min 42 s); eram 1.064.

## O que falta

- **As gravações da IA em níveis,** e depois a Parte B.
- **As voltas de teste** na cópia da pista ("Interlagos [teste]"), pela folha, e depois a Parte F.2. É a medida contra a verdade.
- **A Parte G** (a documentação final da rodada 2 em diante), **o merge e o envio de `develop`.**
- **Se um piloto mais experiente rotular 20 ou 30 passagens no kit 2,** compare com o critério e com a rodada 4 (item 7 de 20/11).

## O envio

Não tentei: o controle de permissões recusou nas outras vezes. O remoto tem a branch em `51b987db`; faltam os commits desta etapa (de `8d067698` em diante). Rode pelo terminal:

```bash
git -C C:/Users/Dokas/Desktop/f1-telemetry-analyzer-48 push origin etapa/modelo2-rodada-2
```

```bash
git -C C:/Users/Dokas/Desktop/f1-telemetry-analyzer-48 ls-remote origin refs/heads/etapa/modelo2-rodada-2
```

**A conferência antes do envio:**

- os commits mudam `backend/` e `docs/`;
- o maior arquivo novo é a galeria (1,5 MB);
- nenhuma gravação, nenhum arquivo de `data/` e nenhum segredo;
- os gabaritos ficam fora do git.

---

# A etapa de 18/11, à tarde (a rodada 4), como foi relatada


## Pedido 42 — relatório parcial de 18/11, à tarde: a rodada 4 (a entrada a partir de b_k); parado

- **Pedido:** `docs/prompts/2026-10-29_42_modelo2-rodada-2.md`, com a "Atualização de 18/11, à tarde" (item 1; depois, gravar o relatório parcial e parar).
- **Data:** 18/11/2026.
- **Pasta:** `C:\Users\Dokas\Desktop\f1-telemetry-analyzer-48`. A atualização estava só nela, sem commit, e foi commitada antes de tudo (`e567e694`). A pasta principal não foi tocada.
- **As duas mensagens:** a primeira mensagem ("Pode fazer a rodada 4 na C04") chegou antes da instrução completa. A rodada 4 já foi feita pelo item 1 da atualização da tarde, que estava commitado antes do código. Conferi o item 1 de novo depois da segunda mensagem: o texto do pedido não mudou depois de `e567e694`, e a regra, as saídas, o relato e os testes seguem o item. Nada foi refeito.
- **Branch:** `etapa/modelo2-rodada-2`.
- **Commits desta etapa:**
  - `e567e694` — o texto da atualização de 18/11, à tarde;
  - `4cc7e3f8` — a rodada 4 registrada antes de rodar (seção 6 de `docs/modelo2_tecnica_e_estilo.md` e linha no ADR 0023);
  - `435e017f` — o código da rodada 4, os testes e a comparação com a rodada anterior;
  - o commit das saídas e deste relatório (o hash está no chat e na nota da sessão).
- **Merges:** nenhum.
- **Arquivos de handoff gerados nesta etapa:**
  - `docs/handoff/2026-10-29_42_modelo2-rodada-2_comparacao_rodada4.json`: a rodada 4 ao lado da rodada 3. Nas chaves, `r2` é a rodada 3 e `r3` é a rodada 4, como diz a nota do arquivo;
  - `docs/handoff/2026-10-29_42_modelo2-rodada-2_pytest.txt`, atualizado;
  - este relatório.

  A rodada 4 grava em `data/ml/modelo2/rodada4/` (fora do git), com o próprio gabarito do kit 2 (`kit2_gabarito.json`).

## Resumo

1. **A rodada 4 resolve o segundo defeito da entrada:**
   - na C04 e na C06, o recuo da entrada ficou em zero na mediana e no p10;
   - na C04, o E1 voltou a 0,03 e o F5 a 0,85 (eram 0,01 e 0,84 na rodada 1).
2. **A regra também cortou uniões que começavam antes de b_k em outras curvas,** como manda a seção 6.2. São a C01 (14 passagens), a C11 (12), a C14 (8), a C05 (2) e a C12 (1). Todas voltaram à entrada da rodada 1.
   - A C11, a C14 e a C05 não têm frenagem, então b_k = a_k nelas.
   - Na C11, o E1 da IA voltou de 0,21 para 0,00, como na rodada 1.
3. **Nada mais mudou:**
   - o E4 é igual nas 2.016 passagens;
   - os 3 maiores erros por sessão são iguais nas 13 sessões;
   - o fechamento das fases é de 0,000 s.
4. **Nenhum defeito novo apareceu** nos números pedidos. A rodada 4 é a última mudança de regra antes dos rótulos e é a que vale para o TCC.
5. **A suíte do backend:** 1.064 passam, nenhuma falha (8 min 52 s); eram 1.062.

## Os dados

- **Os vínculos:** os 3 de `data/reference_models` batem pelo SHA-256 com a pasta principal.
- **O store:** é o mesmo das rodadas 2 e 3 (meta de 17/11, 21:31, `aprovado: true`).
- **O jogo:** o `acs.exe` estava fechado antes da rodada 4.

## O registro, antes de rodar (`4cc7e3f8`)

**A seção 6** registra:

- a união dos trechos na troca de sinal só vale a partir de b_k até o ápice (a mesma janela do E4). Nas curvas sem frenagem, b_k = a_k;
- os dois trechos têm de estar nesse intervalo, e um trecho que começa antes de b_k nunca é unido;
- como b_k fica sempre entre e_(k−1) e a_k, a rodada 4 só pode unir menos que a 3;
- o que não muda, as saídas e o relato;
- se a rodada 4 mostrar outro defeito, ele fica relatado como trabalho futuro;
- a E.2 julga as quatro rodadas, e a que vale é a 4.

**A linha no ADR 0023** foi acrescentada no mesmo commit.

## O comando

`python -m ml.scripts.modelo2 todos --saida rodada4 --rodada 4` (5 min 26 s), e depois `python -m ml.scripts.modelo2 comparar3 --saida rodada4 --anterior rodada3 --rodada1 rodada1_refeita --handoff docs/handoff/2026-10-29_42_modelo2-rodada-2`.

## A rodada 4 ao lado da rodada 3

### O recuo da entrada por curva

É o s_ti menos o da rodada 1, nas 144 voltas, em metros.

| curva | rodada 3: mediana | p10 | p90 | rodada 4: mediana | p10 | p90 | mudaram da 3 para a 4 | voltaram à rodada 1 |
|---|---|---|---|---|---|---|---|---|
| C01 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 14 | 14 |
| C02 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0 | 0 |
| C03 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0 | 0 |
| C04 | 0,0 | −545,0 | 0,0 | 0,0 | 0,0 | 0,0 | 25 | 25 |
| C05 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 2 | 2 |
| C06 | 0,0 | −44,0 | 0,0 | 0,0 | 0,0 | 0,0 | 5 | 4 |
| C07 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0 | 0 |
| C08 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0 | 0 |
| C09 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0 | 0 |
| C10 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0 | 0 |
| C11 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 12 | 12 |
| C12 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 1 | 1 |
| C13 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0 | 0 |
| C14 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 8 | 8 |

- **Na C04 e na C06,** o recuo ficou em zero, como se esperava.
- **Na C06,** 5 passagens mudaram: 4 voltaram à rodada 1, e 1 ficou numa união que começa depois de b_k (dentro da regra).
- **Nas outras curvas,** só mudaram as uniões que começavam antes de b_k. Todas voltaram à entrada da rodada 1:
  - C01, com frenagem: uniões que começavam na reta dos boxes, antes do início da frenagem;
  - C11, C14 e C05, sem frenagem, onde b_k = a_k: uniões que começavam antes do começo geométrico da curva;
  - C12: 1 passagem.

### E1, F5, E5, E6 e E4 por curva, eu e a IA

Fração de "aplica" nas passagens conclusivas, rodada 3 → rodada 4.

| curva | E1 eu | E1 IA | F5 eu | F5 IA | E5 eu | E5 IA | E6 eu | E6 IA | E4 eu |
|---|---|---|---|---|---|---|---|---|---|
| C01 | 0,33 → 0,28 | 0,00 → 0,00 | 0,85 → 0,86 | 1,00 → 1,00 | 0,08 → 0,01 | 0,00 → 0,00 | 1,00 → 1,00 | 1,00 → 1,00 | 0,02 → 0,02 |
| C02 | 0,00 → 0,00 | 0,00 → 0,00 | 0,17 → 0,17 | 0,00 → 0,00 | 0,05 → 0,05 | 0,00 → 0,00 | 1,00 → 1,00 | 1,00 → 1,00 | 0,03 → 0,03 |
| C03 | 0,00 → 0,00 | 0,00 → 0,00 | — → — | — → — | 0,00 → 0,00 | 0,08 → 0,08 | 1,00 → 1,00 | 1,00 → 1,00 | 0,00 → 0,00 |
| C04 | 0,22 → 0,03 | 0,00 → 0,00 | 0,66 → 0,85 | 0,00 → 0,00 | 0,24 → 0,11 | 0,00 → 0,00 | 1,00 → 1,00 | 1,00 → 1,00 | 0,02 → 0,02 |
| C05 | 0,00 → 0,00 | 0,00 → 0,00 | 0,50 → 0,50 | — → — | 0,00 → 0,00 | 0,00 → 0,00 | 1,00 → 1,00 | 1,00 → 1,00 | 0,00 → 0,00 |
| C06 | 0,75 → 0,75 | 0,00 → 0,00 | 0,46 → 0,56 | 0,07 → 0,07 | 0,02 → 0,01 | 0,00 → 0,00 | 1,00 → 1,00 | 1,00 → 1,00 | 0,00 → 0,00 |
| C07 | 0,09 → 0,09 | 0,07 → 0,07 | 0,91 → 0,91 | 0,93 → 0,93 | 0,02 → 0,02 | 0,00 → 0,00 | 0,99 → 0,99 | 0,92 → 0,92 | 0,08 → 0,08 |
| C08 | 0,00 → 0,00 | 0,00 → 0,00 | 0,10 → 0,10 | 0,00 → 0,00 | 0,02 → 0,02 | 0,08 → 0,08 | 1,00 → 1,00 | 1,00 → 1,00 | 0,06 → 0,06 |
| C09 | 0,96 → 0,96 | 0,00 → 0,00 | 0,05 → 0,05 | 0,00 → 0,00 | 0,45 → 0,45 | 0,00 → 0,00 | 0,98 → 0,98 | 1,00 → 1,00 | 0,04 → 0,04 |
| C10 | 0,81 → 0,81 | 0,00 → 0,00 | 0,98 → 0,98 | 1,00 → 1,00 | 0,21 → 0,21 | 0,00 → 0,00 | 0,99 → 0,99 | 1,00 → 1,00 | 0,00 → 0,00 |
| C11 | 0,14 → 0,08 | 0,21 → 0,00 | — → — | — → — | 0,47 → 0,46 | 0,22 → 0,20 | 0,99 → 0,99 | 1,00 → 1,00 | 0,02 → 0,02 |
| C12 | 0,27 → 0,27 | 0,00 → 0,00 | 0,78 → 0,79 | 1,00 → 1,00 | 0,00 → 0,00 | 0,27 → 0,27 | 1,00 → 1,00 | 1,00 → 1,00 | 0,00 → 0,00 |
| C13 | 0,00 → 0,00 | 0,00 → 0,00 | — → — | — → — | 0,10 → 0,10 | 0,00 → 0,00 | 0,99 → 0,99 | 1,00 → 1,00 | 0,00 → 0,00 |
| C14 | 0,35 → 0,32 | 0,00 → 0,00 | — → — | — → — | 0,04 → 0,04 | 0,00 → 0,00 | 1,00 → 1,00 | 1,00 → 1,00 | 0,00 → 0,00 |

**A leitura:**

- **C04:**
  - o E1 meu vai de 0,22 para 0,03, e o F5 de 0,66 para 0,85, de volta aos números da rodada 1 (0,01 e 0,84);
  - o E5 meu cai de 0,24 para 0,11;
  - o E6 não muda.
- **C01:**
  - o E1 meu vai de 0,33 para 0,28, o mesmo da rodada 1;
  - o E5 vai de 0,08 para 0,01.
- **C11:**
  - o E1 meu vai de 0,14 para 0,08;
  - o da IA vai de 0,21 para 0,00, o mesmo da rodada 1. Na rodada 3, uma união antes do começo da curva puxava a entrada da IA.
- **C06:** o F5 meu vai de 0,46 para 0,56.
- **Estados que mudaram da rodada 3 para a 4,** 125 no total:
  - nas 5 curvas da rodada 3: E1, 35; F5, 36; E5, 29; E6, 6;
  - nas outras: na C06, E1 1, E5 1 e F5 3; na C11, E1 11, E5 2 e E6 1.
- **O E4 não mudou em nenhuma passagem,** como se esperava: a janela dele é a mesma (desde b_k).

### O modelo leve

O R² é deixando uma sessão de fora.

| curva | rodada 1 | rodada 3 | rodada 4 |
|---|---|---|---|
| C01 | 0,318 | 0,020 | 0,034 |
| C02 | 0,014 | 0,214 | 0,214 |
| C03 | 0,157 | 0,467 | 0,467 |
| C04 | 0,262 | 0,113 | 0,062 |
| C05 | 0,355 | 0,286 | 0,322 |
| C06 | −0,044 | −0,035 | 0,028 |
| C07 | −0,187 | −0,301 | −0,301 |
| C08 | 0,161 | 0,137 | 0,137 |
| C09 | 0,676 | 0,620 | 0,620 |
| C10 | 0,257 | 0,276 | 0,276 |
| C11 | −0,294 | −0,290 | −0,313 |
| C12 | 0,501 | 0,250 | 0,235 |
| C13 | −0,134 | 0,128 | 0,128 |
| C14 | 0,251 | −0,042 | −0,048 |

- As mudanças da rodada 3 para a 4 são pequenas e só nas curvas em que a entrada mudou.
- A distância para a rodada 1 vem da retomada nova (relatório de 18/11).

### Os 3 maiores erros por sessão e o fechamento

- **Os 3 maiores erros:** iguais aos das rodadas 2 e 3 nas 13 sessões.
- **O fechamento:** a soma das 70 fases fecha em 0,000 s, cobrindo os 4.334,08 m.

### Outro defeito?

Nos números pedidos (a entrada, os quatro detectores, o E4, o modelo leve, o ranking e o fechamento), nenhum. Duas observações, só registradas, sem mudança, como manda o item 2:

- **O E6 (suavidade do volante)** dá "aplica" em quase todas as passagens, minhas e da IA, em todas as rodadas (0,92 a 1,00). Ele separa pouco. É trabalho futuro, e os rótulos não incluem o E6.
- **O M7 na IA** continua como limitação registrada (rodada 2).

## Os testes

Novos em `backend/tests/test_modelo2.py`:

- **uma correção de volante na reta antes de b_k,** seguida de uma troca de sinal: na rodada 3, ela vira a entrada; na rodada 4, a entrada fica no começo da curva;
- **o contraesterço depois de b_k e antes do ápice:** continua unido (a entrada da rodada 4 fica antes da da rodada 1) e visto pelo E4.

O arquivo do Modelo 2 tem 55 testes.

**A suíte do backend:** 1.064 passam, nenhuma falha (8 min 52 s); eram 1.062.

## O que falta

- **Os seus rótulos:** o kit 2 e, pelo menos 3 dias depois, a consistência. Depois, a E.2 para as quatro rodadas, com os mesmos rótulos. Os gabaritos estão em `data/ml/modelo2/rodada2/`, `rodada3/` e `rodada4/` (`kit2_gabarito.json`), e o da rodada 1 em `data/ml/modelo2/rotulagem_gabarito.json`.
- **As voltas de teste,** na cópia da pista ("Interlagos [teste]"), pela folha. Depois, a F.2.
- **As gravações da IA em níveis.** Depois, a Parte B.
- **A Parte G, o merge e o envio.**

## O envio

Não tentei: o controle de permissões recusou nas outras vezes. O remoto tem a branch em `13f332ba` (você enviou a etapa anterior); faltam os commits desta etapa (de `e567e694` em diante). Rode pelo terminal:

```bash
git -C C:/Users/Dokas/Desktop/f1-telemetry-analyzer-48 push origin etapa/modelo2-rodada-2
```

```bash
git -C C:/Users/Dokas/Desktop/f1-telemetry-analyzer-48 ls-remote origin refs/heads/etapa/modelo2-rodada-2
```

**A conferência antes do envio:** os commits mudam só `backend/` e `docs/`. Nada passa de 50 MB, e não há gravações, `data/` nem segredos.

---

# A etapa de 18/11 (a rodada 3 e a cópia da pista), como foi relatada


## Pedido 42 — relatório parcial de 18/11: a rodada 3 (a emenda da entrada) e as voltas de teste na cópia da pista; parado

- **Pedido:** `docs/prompts/2026-10-29_42_modelo2-rodada-2.md`, com a "Atualização de 18/11" (itens 1 e 2; depois, gravar o relatório parcial e parar).
- **Data:** 18/11/2026.
- **Pasta:** `C:\Users\Dokas\Desktop\f1-telemetry-analyzer-48`. A atualização de 18/11 estava só nela, sem commit; a pasta principal (pedido 52) estava limpa e não foi tocada.
- **Branch:** `etapa/modelo2-rodada-2`.
- **Commits desta etapa:**
  - `4b0d6686` — o texto da atualização de 18/11;
  - `f47f0b3f` — a rodada 3 registrada antes de rodar (seção 5 e linha no ADR 0023);
  - `ba488f69` — o código da rodada 3, a correção de redação da seção 5.2 (antes de rodar), os testes e a comparação;
  - `5a35cb2f` — o item 2: o roteiro, a folha, o CSV e o esperado na cópia da pista, com a conferência, antes de qualquer sessão;
  - o commit das saídas e deste relatório (o hash está no chat e na nota da sessão).
- **Merges:** nenhum. O `develop` andou com o 54 (até `2d0c8327`) e só vem para a branch antes do merge, como mandam as regras.
- **Arquivos de handoff gerados nesta etapa:**
  - `docs/handoff/2026-10-29_42_modelo2-rodada-2_comparacao_rodada3.json`: a rodada 3 ao lado da rodada 2;
  - `docs/handoff/2026-10-29_42_modelo2-rodada-2_pytest.txt`, atualizado;
  - este relatório, atualizado.

  A rodada 3 grava em `data/ml/modelo2/rodada3/` (fora do git), com o próprio gabarito do kit 2 (`kit2_gabarito.json`, com os estados da rodada 3).

## Resumo de 18/11

1. **A rodada 3 resolve o defeito da entrada em quatro das cinco curvas:** C01, C07, C12 e C14 voltam ao comportamento da rodada 1, e a C04 em grande parte.
   - **Na C04, sobra um segundo defeito, relatado e não corrigido:** em 29 passagens minhas, o volante passa do limiar na própria reta oposta, depois do fim da C03. A regra da rodada 3 deixa unir esse trecho, porque ele está entre e_(k−1) e o ápice. A entrada fica a uns 576 m antes da C04 (mediana dessas 29).
   - Proponho uma emenda para uma rodada 4.
2. **Nada mais mudou:**
   - os 3 maiores erros por sessão são os mesmos da rodada 2 nas 13 sessões;
   - o fechamento das fases é de 0,000 s;
   - nas outras 9 curvas, só mudou o que a regra nova manda: na C05 e na C13, a entrada volta à da rodada 1 (as duas vêm depois de curvas para o mesmo lado).
3. **A cópia da pista serve para as voltas de teste:**
   - pelo código, uma sessão minha nela fica fora do store, do coach, da "Sua melhor volta", da evolução, dos treinos e da avaliação do aprendizado;
   - o Modelo 2 só a lê pedindo;
   - o engenheiro cala nela, por falta do modelo da pista e, com ele, da posição do carro. Isso não foi testado no jogo;
   - o roteiro, a folha e o CSV dizem "Interlagos [teste]" e estão commitados.

## Item 3: os dados

- **Os vínculos:** os 3 de `data/reference_models` batem pelo SHA-256 com a pasta principal (`811da4c9…`, `f8e61864…` e `e8651d45…`).
- **O store:** é o mesmo da rodada 2 (meta de 18/11, 00:31 UTC, `aprovado: true`, commit `ff0ce3ed`, 721 voltas). A rodada 3 e a rodada 2 usam os mesmos dados.
- **O jogo:** o `acs.exe` estava fechado antes da rodada 3.

## Item 1: a rodada 3

### O registro, antes de rodar

**A seção 5 de `docs/modelo2_tecnica_e_estilo.md`** registra:

- a regra: a união dos trechos na troca de sinal só vale entre o fim da curva anterior, e_(k−1), e o ápice;
- a C01, depois da C14: a janela atravessa o s = 0, e vale a mesma definição das fases (`ahead` e `window`, com o módulo do comprimento da volta);
- o que não muda, a família e a calibração;
- as saídas;
- o M7 da IA, registrado como limitação.

**A linha no ADR 0023** foi acrescentada no mesmo commit (`f47f0b3f`).

**Uma correção de redação antes de rodar.**

- **A primeira redação** deixava unir um trecho que começava antes de e_(k−1) e acabava depois, com a sequência começando em e_(k−1).
- **O teste sintético** (duas curvas para o mesmo lado, com o volante passando levemente para o outro lado na reta) mostrou que isso ainda levava a entrada até o fim da curva anterior, a 620 m. Isso contraria a sua regra.
- **A redação corrigida:** os dois trechos têm de estar entre e_(k−1) e o ápice, e um trecho que começa antes de e_(k−1) nunca é unido.
- A correção foi feita e commitada (`ba488f69`) antes de qualquer conta da rodada 3, com uma nota na seção 5.2.

### O comando

`python -m ml.scripts.modelo2 todos --saida rodada3 --rodada 3` (5 min 45 s), e depois `python -m ml.scripts.modelo2 comparar3 --saida rodada3 --rodada1 rodada1_refeita --handoff docs/handoff/2026-10-29_42_modelo2-rodada-2`.

### O recuo da entrada por curva

É o s_ti de cada rodada menos o da rodada 1, nas 144 voltas, em metros.

| curva | rodada 2: mediana | p10 | p90 | rodada 3: mediana | p10 | p90 | mudaram da 2 para a 3 | voltaram à rodada 1 |
|---|---|---|---|---|---|---|---|---|
| C01 | 0,0 | −895,8 | 0,0 | 0,0 | 0,0 | 0,0 | 17 | 15 |
| C02 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0 | 0 |
| C03 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0 | 0 |
| C04 | −531,0 | −799,4 | 0,0 | 0,0 | −545,0 | 0,0 | 56 | 50 |
| C05 | 0,0 | −77,2 | 0,0 | 0,0 | 0,0 | 0,0 | 19 | 17 |
| C06 | 0,0 | −44,0 | 0,0 | 0,0 | −44,0 | 0,0 | 0 | 0 |
| C07 | 0,0 | −132,0 | 0,0 | 0,0 | 0,0 | 0,0 | 45 | 43 |
| C08 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 1 | 1 |
| C09 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 2 | 1 |
| C10 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 4 | 4 |
| C11 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0 | 0 |
| C12 | 0,0 | −280,0 | 0,0 | 0,0 | 0,0 | 0,0 | 42 | 41 |
| C13 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 13 | 13 |
| C14 | 0,0 | −59,0 | 0,0 | 0,0 | 0,0 | 0,0 | 10 | 10 |

### Nas 5 curvas: E1, F5, E5, E6 e o estilo da entrada

Fração de "aplica", eu: rodada 1 → rodada 2 → rodada 3.

| curva | E1 | F5 | E5 | E6 |
|---|---|---|---|---|
| C01 | 0,28 → 0,43 → 0,33 | 0,86 → 0,83 → 0,85 | — → 0,16 → 0,08 | — → 1,00 → 1,00 |
| C04 | 0,01 → 0,60 → 0,22 | 0,84 → 0,30 → 0,66 | — → 0,57 → 0,24 | — → 1,00 → 1,00 |
| C07 | 0,09 → 0,44 → 0,09 | 0,87 → 0,56 → 0,91 | — → 0,04 → 0,02 | — → 0,99 → 0,99 |
| C12 | 0,22 → 0,53 → 0,27 | 0,81 → 0,47 → 0,78 | — → 0,09 → 0,00 | — → 1,00 → 1,00 |
| C14 | 0,32 → 0,42 → 0,35 | — (sem frenagem) | — → 0,05 → 0,04 | — → 1,00 → 1,00 |

- **A IA** não muda em nenhum dos quatro detectores nessas curvas, da rodada 2 para a 3.
- **O E5 e o E6 da rodada 1** não estão na tabela da comparação, que tem só a rodada 2 e a 3. Eles estão em `rodada1_refeita/tecnicas.json`.
- **Os estados que mudaram da rodada 2 para a 3** nessas 5 curvas: E1, 146; F5, 137; E5, 80; E6, 12.
- **A leitura:** na C07 e na C12, os números voltam para perto da rodada 1. Na C01 e na C14, ficam um pouco acima. Na C04, ficam no meio do caminho, por causa do segundo defeito (abaixo).

**O estilo da entrada** (o z de todas as passagens, por tipo de curva) muda pouco:

- na IA, nas lentas, a `taxa_entrada` vai de 0,70 para 0,66;
- na IA, nas médias, as `reversoes` vão de 0,67 para 1,08;
- em mim, todas as dimensões mudam 0,05 ou menos, salvo as `reversoes` nas médias (de −0,22 para 0,00) e nas rápidas (de −0,23 para −0,11).

**As medidas da entrada nas 5 curvas** (mediana das passagens, rodada 2 → rodada 3):

| curva | taxa de entrada | guinada por roda |
|---|---|---|
| C01 | 0,547 → 0,553 | 11,89 → 11,88 |
| C04 | 0,850 → 0,913 | 10,90 → 12,21 |
| C07 | 0,687 → 0,797 | 9,31 → 9,65 |
| C12 | 0,715 → 0,809 | 9,58 → 10,13 |
| C14 | 1,720 → 1,747 | 12,35 → 12,49 |

A `beta_entrada` não mudou em nenhuma das 5 curvas.

### Nas outras 9 curvas

O que mudou foi só o que a regra nova manda:

- **a entrada:**
  - na C05, depois da C04 para o mesmo lado, 19 passagens, das quais 17 voltam à rodada 1;
  - na C13, depois da C12, 13 passagens, todas de volta à rodada 1;
  - na C10, 4; na C09, 2; na C08, 1.

  Em todas, era uma união que começava antes do fim da curva anterior, e a rodada 3 corta;
- **os estados que mudaram, por causa dessas entradas:**
  - C05: F5, 1;
  - C08: E1, 1;
  - C09: E6, 2;
  - C10: E5, 3; F5, 4;
  - C13: E5, 2; E6, 1.
- **a C06 não mudou:** o recuo de 44 m no p10 já estava na rodada 2 e continua na 3. A C05, antes dela, vira para o outro lado, então a regra nova não se aplica.

No total, 389 estados mudaram da rodada 2 para a 3, quase todos nas 5 curvas.

### O modelo leve

O R² é deixando uma sessão de fora.

| curva | rodada 1 | rodada 2 | rodada 3 |
|---|---|---|---|
| C01 | 0,318 | 0,040 | 0,020 |
| C02 | 0,014 | 0,214 | 0,214 |
| C03 | 0,157 | 0,467 | 0,467 |
| C04 | 0,262 | 0,093 | 0,113 |
| C05 | 0,355 | 0,208 | 0,286 |
| C06 | −0,044 | −0,035 | −0,035 |
| C07 | −0,187 | −0,283 | −0,301 |
| C08 | 0,161 | 0,140 | 0,137 |
| C09 | 0,676 | 0,624 | 0,620 |
| C10 | 0,257 | 0,274 | 0,276 |
| C11 | −0,294 | −0,290 | −0,290 |
| C12 | 0,501 | 0,238 | 0,250 |
| C13 | −0,134 | 0,208 | 0,128 |
| C14 | 0,251 | −0,040 | −0,042 |

**Uma correção do relatório anterior:** lá eu atribuí a queda do R² da C01, da C04, da C12 e da C14 ao defeito da entrada. A rodada 3 mostra que não:

- a entrada dessas curvas volta ao normal (salvo as 29 passagens da C04), e o R² continua baixo;
- então a queda vem das outras emendas (a retomada, que muda o M6, o M7, o M8 e o `retomada_s`), e não da entrada.

### Os 3 maiores erros por sessão e o fechamento

- **Os 3 maiores erros:** iguais aos da rodada 2 nas 13 sessões. A entrada não mexe na perda.
- **O fechamento:** a soma das 70 fases fecha em 0,000 s; as fases cobrem os 4.334,08 m.

### O segundo defeito, na C04 (relatado, não corrigido)

- **O que acontece:** em 29 passagens minhas da C04 (nenhuma da IA), a entrada da rodada 3 fica de 36 a 618 m antes do começo da curva (mediana de 576 m).
  - Nessas voltas, o volante passa de 0,15·δ_pk da C04 em algum ponto da reta oposta, depois do fim da C03: uma correção ou uma troca de faixa.
  - Depois, ele troca de sinal, e a regra une esse trecho à entrada.
  - A união é permitida, porque os dois trechos estão entre e_(k−1) e o ápice.
- **A C06** tem o mesmo fenômeno em 17 passagens (mediana de 84 m antes da curva), desde a rodada 2.
- **O efeito:** o E1 da C04 fica em 0,22 (era 0,01 na rodada 1), e o F5 em 0,66 (era 0,84). Nas outras curvas, o efeito é pequeno.
- **A emenda que proponho para uma rodada 4,** registrada antes de rodar: a união só vale a partir do início da fase de frenagem, b_k, e não de e_(k−1). Nas curvas sem frenagem, b_k = a_k. Assim, uma correção de volante na reta nunca vira a entrada da curva.
- **Até a decisão,** o E1, o F5 e o E5 da C04 na rodada 3 não devem ser usados. O resto da rodada 3 vale.

### O teste

Novos em `backend/tests/test_modelo2.py`:

- **duas curvas para o mesmo lado,** com o volante passando levemente para o outro lado na reta entre elas: na rodada 2, a entrada da segunda recua até a primeira; na rodada 3, fica no começo da segunda;
- **o contraesterço antes do ápice:** dentro da curva, a união vale como na rodada 2, e o E4 da rodada 3 continua vendo o contraesterço;
- **a regra no índice:** um trecho que começa antes de e_(k−1) nunca é unido, e dois trechos depois dele são unidos.

**A suíte do backend:** 1.062 passam, nenhuma falha (9 min 21 s); eram 1.059. A saída está em `docs/handoff/2026-10-29_42_modelo2-rodada-2_pytest.txt`. O arquivo do Modelo 2 tem 53 testes.

## Item 2: as voltas de teste na cópia da pista

### A cópia instalada

- **A pasta:** `D:\SteamLibrary\steamapps\common\assettocorsa\content\tracks\vhe_interlagos_teste_m1`. O Content Manager mostra "Interlagos [teste]", layout `gp`.
- **A superfície:** o `vhe_interlagos.kn5` (sha256 `ce1f3bb2…`) e o `gp/data/surfaces.ini` (`4520b16b…`) são iguais aos da original.
- **A geometria** é a mesma (`0ed16f0dd2225990`, pelo ADR 0032, item 2). A pasta do jogo só foi lida.

### A conferência

Pelo código de `develop` e da branch do pedido 52, sem rodar nada no jogo.

| o quê | resultado | por quê |
|---|---|---|
| o store v2 | fora | o construtor usa `list_all_sessions()`, que deixa as pistas de teste (`config.TEST_TRACK_NAMES`) fora, salvo `incluir_pistas_de_teste=True` |
| o coach (as duas referências e a seleção das minhas voltas) | fora | o `atualizar_coach`, o construtor do modelo (`backend/tools/train_reference_model.py`) e o inventário usam a mesma lista. A volta do modelo vem do arquivo dela (`vhe_interlagos`) |
| a "Sua melhor volta" | fora | é a `minha_melhor` do modelo do coach; o "recorde pessoal" do rádio vem do store |
| o relatório de evolução | fora | é feito do store v2 |
| os treinos (a LSTM incluída) | fora | o `retreino_lstm.py` usa `list_all_sessions()`; o Modelo 1 e a validação usam o store v1 (`lap_store.py`, a mesma lista) |
| a avaliação do aprendizado | fora | a validação (`ml/scripts/validate.py`) lê o store |
| o Modelo 2 | só pedindo | o `carregar` usa o store e a lista sem as pistas de teste. A F.2 vai pedir com `incluir_pistas_de_teste=True`, pela sessão do roteiro, só com as minhas voltas (pelo `isAIControlled`) |
| o engenheiro (o app do jogo) | **cala, pelo código** | o coach ao vivo procura o modelo pelo nome da pista do jogo (`vhe_interlagos_teste_m1.json`), que não existe. Sem modelo, não há a projeção na geometria oficial nem a `posicao_oficial`, de onde o rádio e o engenheiro tiram a posição do carro |

- **Nenhum ponto falhou,** e nenhum código fora do Modelo 2 mudou.
- **O que não foi testado:** o engenheiro calado é uma leitura do código. As sessões dos pedidos 47 e 50 na cópia eram da IA, e o rádio já cala com a IA.
- **As únicas listagens das gravações sem o filtro** são as do app que acham uma volta pelo id (a tela Volta e as frases de uma volta já gravada). Elas não medem nada.

### O roteiro, a folha e o CSV (`5a35cb2f`, antes de qualquer sessão)

- **A folha** diz, no topo: escolha "Interlagos [teste]" (a cópia) no Content Manager, com o preset de sempre.
- **O CSV de marcação** ganhou a coluna `pista`, com `vhe_interlagos_teste_m1 (Interlagos [teste] no Content Manager)` em cada linha.
- **O roteiro:**
  - a seção 2 diz a pista e a conferência da superfície;
  - a seção 3 agora tem a sua decisão, a tabela da conferência, o engenheiro e como a F.2 lê as sessões. A proposta da coluna `finalidade` ficou sem efeito.
- **O esperado** (`…_esperado.json`) ganhou a pista e a decisão.
- **Os comportamentos, as curvas e o plano volta a volta não mudaram.**

## O que precisa de decisão (18/11)

1. **O segundo defeito da entrada, na C04 (e na C06):** a emenda proposta é unir só a partir de b_k. Se aprovar, é uma rodada 4, registrada antes de rodar. Até lá, não use o E1, o F5 e o E5 da C04 na rodada 3.

## O que falta

- **A Parte B:** quando as gravações da IA em níveis estiverem anotadas.
- **A Parte E.2,** quando os rótulos chegarem: a precisão e a revocação das três rodadas, com os mesmos rótulos, o kappa e a galeria. O gabarito da rodada 3 está em `data/ml/modelo2/rodada3/kit2_gabarito.json`.
- **As sessões de teste,** na cópia, pela folha. Depois, a Parte F.2.
- **A Parte G, o merge e o envio.**

## O envio

Não tentei: o controle de permissões recusou nas outras vezes. O remoto tem a branch em `a3287e40`. Rode pelo terminal, um comando por vez:

```bash
git -C C:/Users/Dokas/Desktop/f1-telemetry-analyzer-48 push origin etapa/modelo2-rodada-2
```

```bash
git -C C:/Users/Dokas/Desktop/f1-telemetry-analyzer-48 ls-remote origin refs/heads/etapa/modelo2-rodada-2
```

**A conferência antes do envio:** os commits de 18/11 mudam `backend/` (o código e os testes), `docs/` e os arquivos de `docs/experimentos/` e `docs/handoff/` listados acima. Nada passa de 50 MB, e não há gravações, `data/` nem segredos.

---

# A etapa de 17 e 18/11 (Partes 0, A, C, D, E.1 e F.1), como foi relatada


## Pedido 42 — relatório parcial: Partes 0, A, C, D, E.1 e F.1 feitas; parado na parada do pedido (o kit 2, as voltas de teste e a IA em níveis)

- **Pedido:** `docs/prompts/2026-10-29_42_modelo2-rodada-2.md`, versão de 17/11/2026, com a "Atualização de 17/11, à tarde".
- **Datas:** de 17 a 18/11/2026.
- **Pasta:** `C:\Users\Dokas\Desktop\f1-telemetry-analyzer-48`. A pasta principal (pedido 52, `etapa/engenheiro`) não foi tocada: nenhuma troca de branch, nenhum commit e nenhuma escrita fora de `data/` pelos links. As saídas das rodadas vão para `data/ml/modelo2/rodada1_refeita/` e `data/ml/modelo2/rodada2/`, pela junção `data/ml`, e ficam na pasta principal.
- **Branch:** `etapa/modelo2-rodada-2`, criada a partir de `develop` (`14fe1ca0`).
- **Commits deste pedido:**
  - `dc405d6a` — o texto do pedido (17/11);
  - `e1151879` e `a8e7a518` — o relatório parcial da manhã (parado na Parte 0, item 5) e o envio recusado;
  - `46066db8` — as decisões da tarde no texto do pedido;
  - `ba776e82` — a Parte A, registrada antes de rodar;
  - `9b6f56b9` — as pastas de saída, os 144 `lap_id` e a margem de 2 ms;
  - `1e1ea229` — o relatório parcial da tarde;
  - `13797174` — o código das Partes C, D e E.1, antes de rodar. Inclui a correção de redação da seção 4.4 e a seção 4.6.1 (o E2 com a geometria medida);
  - `552e892d` — a Parte F.1: o roteiro, a folha, o CSV e o esperado, antes de qualquer sessão;
  - o commit das saídas e deste relatório (o hash está no chat e na nota da sessão).
- **Merges:** nenhum.
- **Arquivos de handoff gerados (`docs/handoff/2026-10-29_42_modelo2-rodada-2_*`):**
  - `relatorio.md` (este) e `pytest.txt`;
  - `conferencia_rodada1.json`: a rodada 1 refeita contra a guardada;
  - `comparacao.json`: a rodada 2 ao lado da rodada 1, o E2 antes e depois e o E3 de 01/11;
  - da rodada 2:
    - `resultados.json`, `fases.json`, `canais_e_conferencias.json` e `estilo.json`;
    - `erros_por_sessao.json` e `erros_por_sessao_so_comparacao_0013.json`;
    - `erros_depois_do_kit.json` e `e3_saidas_de_traseira.json`;
    - `tecnicas.json` (sem os estados de cada passagem) e `modelo_leve.json`;
  - o kit 2: `kit2_rotulagem.html`, `kit2_consistencia.html` e `kit2_consistencia.csv`;
  - em `docs/experimentos/`: o roteiro, a folha, o CSV de marcação e o esperado das voltas de teste.

## Resumo

1. **Os dados:** o store foi reaprovado pelo pedido 54 às 21:31 de 17/11. Esperei a reaprovação aparecer no meta antes de ler. Os 3 vínculos de `data/reference_models` batem pelo SHA-256 com a pasta principal.
2. **A rodada 1 refeita reproduz a guardada** nas passagens, nos estados, nas fases, no ranking, no fechamento e no modelo leve. Só o sorteio do kit refeito difere, porque depende da ordem das linhas. O kit 2 usa o gabarito guardado.
3. **A rodada 2 rodou** com as emendas, a volta do modelo como referência, o E2 com a geometria do pedido 39 e a margem de ±2 ms.
   - **Um defeito da regra registrada da entrada:** a regra de "não cortar na troca de sinal" junta, nas curvas que vêm depois de outra curva para o mesmo lado, o volante da curva anterior. Nesses casos, a entrada recua centenas de metros: C01, C04, C07, C12 e C14.
   - O E1, o F5, o E5, o E6 e a parte da entrada do estilo dessas curvas ficam contaminados.
   - Não mudei a regra, porque o pedido proíbe mudar critério depois de ver os números. Proponho a emenda para uma rodada 3.
4. **O kit 2** (as mesmas 120 passagens, com as duas referências do app e as páginas da literatura) e **o CSV da consistência** (30 passagens) estão prontos. O CSV dos rótulos continua vazio.
5. **O roteiro das voltas de teste está pronto e commitado.** O item 4 parou: não há como deixar as sessões de teste fora de tudo sem código novo. A proposta está no roteiro.
6. **A suíte do backend:** veja a seção "Testes".

## Retomada de 17/11, à noite: o store reaprovado, a Parte 0 (itens 5 e 6) e as Partes C, D, E.1 e F.1

O Eduardo avisou que o store estava reaprovado e que a leitura da seção 4.3 estava certa: só os detectores cujo indicador mudou com as emendas são recalibrados, pela mesma regra e nas mesmas passagens da IA, e os outros ficam iguais.

**Antes de ler qualquer coisa, conferi duas coisas:**

- **O store ainda não estava reaprovado** quando o aviso chegou (21:15). O meta ainda era o de 15/11, com `aprovado: false`, e o pedido 54 estava regravando o store (a sessão dele estava ativa, e a cópia `_backup_antes_pedido54` era de 20:35). Então esperei: um laço só de leitura olhou o meta a cada 30 s.
- **O meta virou `aprovado: true` às 21:31.** Ele foi construído em 18/11, 00:31 UTC, com o commit `ff0ce3ed` (branch do 54) e 721 voltas. Todas as checagens passam.
  - As 3 sessões estão em `sessoes_aceitas_com_margem`, com efeito de 1,98, 1,643 e 1,59 ms;
  - `margem_linha_do_jogo_ms` = 2,0.
  - Só comecei depois disso.
- **O `develop` local continua em `14fe1ca0`:** o merge do 54 não estava lá até o fim deste trabalho. Este pedido não precisa dele, porque o Modelo 2 lê só o meta e o store.

### Os 3 vínculos de `data/reference_models` (pelo SHA-256, antes de ler)

| arquivo | pasta do 48 | pasta principal |
|---|---|---|
| `vhe_interlagos.geometry.json` | `811da4c9…` | `811da4c9…` |
| `vhe_interlagos.json` | `f8e61864…` | `f8e61864…` |
| `vhe_interlagos.volta_do_modelo.json` | `e8651d45…` | `e8651d45…` |

Os três são iguais, e nenhum vínculo precisou ser refeito.

### 0.5 A trava do store v2

- O Modelo 2 lê o store reaprovado: a trava `aprovado` do código não mudou, e passou.
- As 3 sessões aceitas com margem têm 15 voltas `humano` (6 + 5 + 4), até 210 passagens. Nenhuma está nas 144 voltas da comparação.
- Elas entram só na tabela à parte da Parte D.3 e no E3 das saídas de traseira (D.6), marcadas `sessao_com_margem`.
- A outra sessão depois de 24/10 (`2026-11-07_19-52-33`, 2 voltas) passa na checagem sem margem.

### 0.6 A rodada 1 refeita: **reproduz**

- **O comando:** `python -m ml.scripts.modelo2 todos --saida rodada1_refeita --rodada 1`, com o jogo fechado. Levou 4 min 52 s.
- **A conferência:** `python -m ml.scripts.modelo2 conferir --saida rodada1_refeita`, contra os arquivos guardados da rodada 1 em `data/ml/modelo2/`. Saída em `docs/handoff/2026-10-29_42_modelo2-rodada-2_conferencia_rodada1.json`.

| o quê | guardada | refeita | resultado |
|---|---|---|---|
| passagens (`passagens.parquet`) | 2.016 | 2.016 | iguais, coluna a coluna (tolerância 1e-6), nenhuma diferente |
| estados de cada detector | 48.384 | 48.384 | nenhum diferente, nenhum sem par |
| as 70 fases | — | — | iguais |
| os 3 maiores erros por sessão | 13 sessões | 13 sessões | as 13 iguais |
| o fechamento da soma das fases | 0,000 s | 0,000 s | igual |
| o R² do modelo leve | — | — | iguais |

- **Quatro colunas novas** na refeita, só relatadas: `contra_antes_apice_s`, `freio_emendado`, `s_pu_rel` e `sessao_com_margem`.
- **Uma diferença fora das regras: o sorteio do kit.** O kit refeito (`rodada1_refeita/rotulagem_gabarito.json`) tem só 41 das 120 passagens do kit guardado.
  - **A causa:** o sorteio (`pandas.sample` com a semente 38) depende da ordem das linhas na memória, e o store de 15/11 traz as voltas em outra ordem. Os estados são os mesmos, linha a linha.
  - **O efeito:** nenhum na comparação. O kit 2 (Parte E.1) usa o gabarito guardado da rodada 1, com as mesmas 120 passagens e os mesmos ids, como o pedido manda.
- **O jogo:** o `acs.exe` estava fechado antes desta conta e antes da Parte D.


### Parte B — a IA em níveis: fica para depois

`docs/experimentos/ia_niveis.csv` e `data/ml/modelo2/ia_niveis.csv` não existem: as gravações da IA em níveis ainda não chegaram. Como o pedido manda, a Parte B fica para depois da sua parada.

### Parte C — o E2 com a geometria medida

- **De onde vêm os valores:** `L` e `k_δ` são lidos de onde o pedido 39 os registrou, em `docs/handoff/2026-10-25_39_m1-geometria-medida_geometria.json`, chave `usados`: `L` = 2,9636 m e `k_δ` = 0,30396 rad. O código lê o arquivo (`dados.geometria_medida`).
- **Na rodada 1 refeita** ficou a medida substituta: `L` = 2,955 m e `k_δ` = 0,267 rad.
- **O registro, antes de rodar,** está na seção 4.6.1.
- **A fração de "aplica" do E2, por curva** (eu; a IA tem só uma volta com a guinada):

  | curva | eu, antes → depois | IA, antes → depois |
  |---|---|---|
  | C01 | 0,10 → 0,11 | 0,00 → 0,00 |
  | C02 | 0,85 → 0,87 | 0,00 → 0,00 |
  | C03 | 0,02 → 0,03 | 0,00 → 0,00 |
  | C04 | 0,02 → 0,02 | 0,00 → 0,00 |
  | C05 | 0,00 → 0,00 | 0,00 → 0,00 |
  | C06 | 0,08 → 0,09 | 0,00 → 0,00 |
  | C07 | 0,03 → 0,03 | 0,00 → 0,00 |
  | C08 | 0,91 → 0,92 | 0,00 → 0,00 |
  | C09 | 0,00 → 0,02 | 0,00 → 0,00 |
  | C10 | 0,02 → 0,02 | 0,00 → 0,00 |
  | C11 | 0,12 → 0,14 | 0,00 → 0,00 |
  | C12 | 0,66 → 0,68 | 0,00 → 0,00 |
  | C13 | 0,00 → 0,00 | 0,00 → 0,00 |
  | C14 | 0,00 → 0,00 | 0,00 → 0,00 |

- **O que mudou:** quase nada. 24 das 2.016 passagens mudaram de estado.
  - O E2 compara o ângulo de subesterço com a mediana da IA, e a geometria nova desloca os dois juntos.
  - O E2 continua dizendo "aplica" na C02, na C08 e na C12, e quase nunca nas outras.
- **A IA tem uma passagem com a guinada por curva** (a volta de 22/10). A referência do E2 é essa passagem só, como na rodada 1.

### Parte D — a rodada 2

- **O comando:** `python -m ml.scripts.modelo2 todos --saida rodada2 --rodada 2 --handoff docs/handoff/2026-10-29_42_modelo2-rodada-2`, com o jogo fechado. Levou 7 min 11 s.
- **A comparação:** `python -m ml.scripts.modelo2 comparar --saida rodada2 --rodada1 rodada1_refeita --handoff …`.
- **As voltas:** as mesmas 144 da rodada 1 (130 minhas e 14 da IA). As fases, o envelope e a calibração saem só delas.
- **A volta do modelo:** `2026-11-15_02-47-12_vhe_interlagos_teste_m1#0008`, com 1:24,552, lida do arquivo da pasta principal pelo vínculo.
- **A "Sua melhor volta":** `2026-10-24_13-43-32#0003`, com 1:26,568 na grade. A segunda melhor, usada quando a melhor está entre as voltas comparadas, é a `2026-10-21_20-30-54#0017`.

#### D.4 Os 3 maiores erros por sessão, lado a lado

**O que mudou:**

- **Na rodada 1, as duas retas pesavam mais que tudo:** a C14 (reta dos boxes) e a C03 (reta oposta) ficavam em 2º e 3º lugar em todas as 13 sessões.
- **Sem o peso e contra a volta do modelo, as frenagens e os meios das curvas lentas sobem:**
  - a frenagem da C12, em 7 sessões;
  - a da C01, em 4 (e o meio da C01, em mais 1);
  - a da C04, em 4;
  - o meio da C08, em 4;
  - a frenagem da C07, em 2.
- **A coluna "só comparação" separa os dois efeitos:** com a `#0013` como referência e as regras novas, a C14 ainda aparece em 6 sessões. Então tirar o peso tira a C03 de quase todas, e trocar a referência tira boa parte da C14.

| sessão | rodada 1 (contra a `#0013`, com peso) | rodada 2 (contra a volta do modelo, sem peso) | rodada 2, só comparação (contra a `#0013`) | entrou | saiu |
|---|---|---|---|---|---|
| 2026-10-04 | consistencia; C14-esq reta (+0.623 s); C03-esq reta (+0.230 s) | consistencia; C12-esq frenagem (+0.528 s); C08-esq meio (+0.496 s) | consistencia; C14-esq reta (+0.623 s); C01-esq frenagem (+0.567 s) | C08-esq meio, C12-esq frenagem | C03-esq reta, C14-esq reta |
| 2026-10-05 | consistencia; C14-esq reta (+0.269 s); C03-esq reta (+0.194 s) | consistencia; C07-dir frenagem (+0.543 s); C08-esq meio (+0.505 s) | consistencia; C01-esq frenagem (+0.463 s); C07-dir frenagem (+0.452 s) | C07-dir frenagem, C08-esq meio | C03-esq reta, C14-esq reta |
| 2026-10-05-2 | consistencia; C14-esq reta (+0.619 s); C03-esq reta (+0.396 s) | consistencia; C12-esq frenagem (+0.823 s); C01-esq frenagem (+0.693 s) | consistencia; C12-esq frenagem (+0.843 s); C01-esq frenagem (+0.788 s) | C01-esq frenagem, C12-esq frenagem | C03-esq reta, C14-esq reta |
| 2026-10-09 | consistencia; C14-esq reta (+0.241 s); C03-esq reta (+0.181 s) | consistencia; C01-esq frenagem (+0.654 s); C08-esq meio (+0.652 s) | consistencia; C01-esq frenagem (+0.750 s); C12-esq frenagem (+0.661 s) | C01-esq frenagem, C08-esq meio | C03-esq reta, C14-esq reta |
| 2026-10-10 | consistencia; C14-esq reta (+0.627 s); C03-esq reta (+0.373 s) | consistencia; C01-esq frenagem (+0.679 s); C12-esq frenagem (+0.667 s) | consistencia; C01-esq frenagem (+0.774 s); C12-esq frenagem (+0.687 s) | C01-esq frenagem, C12-esq frenagem | C03-esq reta, C14-esq reta |
| 2026-10-11 | consistencia; C14-esq reta (+0.686 s); C03-esq reta (+0.196 s) | consistencia; C14-esq reta (+0.468 s); C12-esq frenagem (+0.464 s) | consistencia; C14-esq reta (+0.686 s); C12-esq frenagem (+0.484 s) | C12-esq frenagem | C03-esq reta |
| 2026-10-13 | consistencia; C14-esq reta (+0.667 s); C03-esq reta (+0.347 s) | consistencia; C01-esq frenagem (+0.628 s); C12-esq frenagem (+0.522 s) | consistencia; C01-esq frenagem (+0.724 s); C14-esq reta (+0.667 s) | C01-esq frenagem, C12-esq frenagem | C03-esq reta, C14-esq reta |
| 2026-10-16 | consistencia; C14-esq reta (+0.251 s); C03-esq reta (+0.139 s) | consistencia; C04-esq frenagem (+0.463 s); C10-dir reta (+0.426 s) | consistencia; C10-dir reta (+0.481 s); C12-esq frenagem (+0.435 s) | C04-esq frenagem, C10-dir reta | C03-esq reta, C14-esq reta |
| 2026-10-17 | consistencia; C14-esq reta (+0.248 s); C03-esq reta (+0.310 s) | consistencia; C04-esq frenagem (+0.658 s); C12-esq frenagem (+0.529 s) | consistencia; C12-esq frenagem (+0.549 s); C04-esq frenagem (+0.518 s) | C04-esq frenagem, C12-esq frenagem | C03-esq reta, C14-esq reta |
| 2026-10-17-2 | consistencia; C14-esq reta (+0.672 s); C03-esq reta (+0.529 s) | consistencia; C12-esq frenagem (+0.565 s); C04-esq frenagem (+0.511 s) | consistencia; C14-esq reta (+0.672 s); C12-esq frenagem (+0.584 s) | C04-esq frenagem, C12-esq frenagem | C03-esq reta, C14-esq reta |
| 2026-10-18 | consistencia; C14-esq reta (+0.631 s); C03-esq reta (+0.368 s) | consistencia; C07-dir frenagem (+0.441 s); C14-esq reta (+0.414 s) | consistencia; C14-esq reta (+0.631 s); C12-esq frenagem (+0.410 s) | C07-dir frenagem | C03-esq reta |
| 2026-10-21 | consistencia; C14-esq reta (+0.282 s); C03-esq reta (+0.187 s) | consistencia; C01-esq meio (+0.894 s); C08-esq meio (+0.452 s) | consistencia; C01-esq meio (+0.816 s); C12-esq frenagem (+0.413 s) | C01-esq meio, C08-esq meio | C03-esq reta, C14-esq reta |
| 2026-10-24 | consistencia; C14-esq reta (+0.483 s); C03-esq reta (+0.487 s) | consistencia; C03-esq reta (+0.381 s); C04-esq frenagem (+0.294 s) | consistencia; C03-esq reta (+0.487 s); C14-esq reta (+0.483 s) | C04-esq frenagem | C14-esq reta |

**O fechamento das fases:** a soma das 70 continua fechando o tempo da volta: 0,000 s contra a volta do modelo, contra a `#0013` e nas voltas depois do kit. As 70 fases cobrem os 4.334,08 m.

#### M6, M7 e M8 por curva (fração de "aplica" nas passagens conclusivas, rodada 1 → rodada 2)

| curva | M6 eu | M6 IA | M7 eu | M7 IA | M8 eu | M8 IA |
|---|---|---|---|---|---|---|
| C01-esq | 0,00 → 0,06 | 0,00 → 0,00 | 0,69 → 0,36 | 1,00 → 1,00 | 0,92 → 0,88 | 1,00 → 1,00 |
| C02-dir | 0,00 → 0,26 | 0,00 → 0,00 | 1,00 → 0,26 | 1,00 → 1,00 | 0,80 → 0,13 | 1,00 → 0,00 |
| C03-esq | 0,00 → 0,02 | 0,00 → 0,00 | 1,00 → 0,96 | 1,00 → 1,00 | 0,03 → 0,02 | 0,00 → 0,00 |
| C04-esq | 0,00 → 0,45 | 0,00 → 1,00 | 0,77 → 0,36 | 1,00 → 0,00 | 0,54 → 0,14 | 1,00 → 0,00 |
| C05-esq | 0,00 → 0,02 | 0,00 → 0,00 | 0,55 → 0,97 | 0,07 → 1,00 | 0,07 → 0,00 | 0,00 → 0,00 |
| C06-dir | 0,00 → 0,00 | 0,00 → 0,00 | 0,81 → 1,00 | 1,00 → 1,00 | 0,94 → 0,67 | 0,60 → 0,43 |
| C07-dir | 0,00 → 0,05 | 0,00 → 0,93 | 0,53 → 0,22 | 1,00 → 0,07 | 0,94 → 0,93 | 1,00 → 0,07 |
| C08-esq | 0,00 → 0,30 | 0,00 → 0,00 | 0,95 → 0,31 | 1,00 → 1,00 | 0,97 → 0,52 | 0,29 → 0,14 |
| C09-dir | 0,01 → 0,12 | 0,00 → 0,00 | 0,86 → 0,54 | 1,00 → 1,00 | 0,69 → 0,73 | 0,00 → 0,00 |
| C10-dir | 0,00 → 0,50 | 0,00 → 1,00 | 0,52 → 0,13 | 1,00 → 0,00 | 0,66 → 0,38 | 1,00 → 0,00 |
| C11-esq | 0,00 → 0,02 | 0,00 → 0,00 | 1,00 → 0,86 | 1,00 → 1,00 | 0,24 → 0,27 | 0,00 → 0,00 |
| C12-esq | 0,00 → 0,75 | 0,00 → 0,00 | 0,78 → 0,15 | 1,00 → 1,00 | 0,61 → 0,12 | 1,00 → 0,00 |
| C13-esq | 0,00 → 0,33 | 0,00 → 1,00 | 1,00 → 0,65 | 1,00 → 0,00 | 0,17 → 0,02 | 0,00 → 0,00 |
| C14-esq | 0,00 → 0,07 | 0,00 → 0,00 | 0,98 → 0,92 | 1,00 → 1,00 | 0,02 → 0,01 | 0,00 → 0,00 |

**A leitura:**

- **A retomada nova faz o M6 informar:** na rodada 1, ele dava "aplica" em 1 de 2.016 passagens.
  - **Eu:** a fração sobe nas curvas lentas: C12, 0,75; C10, 0,50; C04, 0,45; C13, 0,33; C08, 0,30.
  - **A IA:** passa a "aplicar" na C04, na C07, na C10 e na C13.
- **O M7 da IA ainda dá "aplica" em 9 das 14 curvas.** Isso ocorre mesmo com a retomada depois da mínima: o volante dela continua crescendo depois da subida do acelerador.
  - O M7 continua pouco informativo na IA.
  - É uma limitação para uma rodada 3, e não muda nada agora.
- **O M8 cai bastante:** o alívio contado a partir do começo da subida contínua pega menos quedas.
- **Estados que mudaram, nas 2.016 passagens:** M6, 616; M7, 983; M8, 574.

#### E4, a entrada, E1 e F5

- **E4:** 11 passagens ganharam "aplica" (9 minhas e 2 da IA). Em 10 delas, o contraesterço está antes do ápice (`contra_antes_apice_s` ≥ 0,10 s), ou seja, na parte que a janela da rodada 1 cortava. 82 passagens mudaram de estado no total.
- **A entrada e a retomada** (rodada 2 menos rodada 1, nas 144 voltas):

| curva | passagens | mudaram | mediana | p10 | p90 | retomada: mediana | p10 | p90 |
|---|---|---|---|---|---|---|---|---|
| C01-esq | 144 | 29 | 0,0 m | -895,8 m | 0,0 m | 0,21 s | 0,00 s | 2,45 s |
| C02-dir | 144 | 0 | 0,0 m | 0,0 m | 0,0 m | 0,98 s | 0,43 s | 1,88 s |
| C03-esq | 144 | 1 | 0,0 m | 0,0 m | 0,0 m | -0,15 s | -0,42 s | 0,00 s |
| C04-esq | 144 | 79 | -531,0 m | -799,4 m | 0,0 m | 0,57 s | 0,07 s | 1,92 s |
| C05-esq | 143 | 20 | 0,0 m | -77,2 m | 0,0 m | 2,55 s | 0,36 s | 2,73 s |
| C06-dir | 142 | 17 | 0,0 m | -44,0 m | 0,0 m | 2,91 s | 0,41 s | 4,30 s |
| C07-dir | 143 | 50 | 0,0 m | -132,0 m | 0,0 m | 0,24 s | 0,00 s | 2,08 s |
| C08-esq | 142 | 1 | 0,0 m | 0,0 m | 0,0 m | 1,78 s | 0,08 s | 2,83 s |
| C09-dir | 123 | 3 | 0,0 m | 0,0 m | 0,0 m | 0,60 s | -0,13 s | 2,35 s |
| C10-dir | 144 | 9 | 0,0 m | 0,0 m | 0,0 m | 0,30 s | 0,00 s | 1,85 s |
| C11-esq | 144 | 12 | 0,0 m | 0,0 m | 0,0 m | 1,23 s | 0,84 s | 2,36 s |
| C12-esq | 144 | 47 | 0,0 m | -280,0 m | 0,0 m | 0,91 s | 0,14 s | 1,88 s |
| C13-esq | 144 | 13 | 0,0 m | 0,0 m | 0,0 m | 3,06 s | 0,87 s | 3,31 s |
| C14-esq | 144 | 18 | 0,0 m | -59,0 m | 0,0 m | 1,91 s | 0,45 s | 4,30 s |

**Um defeito da regra registrada da entrada.** A regra de "não cortar na troca de sinal" junta dois trechos quando, entre eles, o volante passa para o outro lado além de 0,05·δ_pk.

- **Onde a entrada recua:** nas curvas que vêm depois de outra curva para o mesmo lado. São a C01 (depois da C14), a C04 (depois da C03), a C07 (depois da C06), a C12 (depois da C11) e a C14 (depois da C13).
- **Por quê:** na reta entre as duas curvas, o volante passa levemente para o outro lado, e a regra une o volante da curva anterior ao desta. A entrada recua até a curva anterior, a centenas de metros. Na C04, a mediana do recuo é de −531 m, e 56 passagens têm a entrada antes do fim da C03.
- **Os detectores contaminados nessas curvas:**
  - E1: na C04, o "aplica" vai de 0,01 a 0,60; na C07, de 0,09 a 0,44; na C12, de 0,22 a 0,53;
  - F5: na C04, de 0,84 a 0,30; na C12, de 0,81 a 0,47; na C07, de 0,87 a 0,56;
  - E5, E6, a taxa de entrada e a resposta na entrada do estilo.
- **Nas outras 9 curvas,** a regra se comporta como o esperado: o recuo é zero na mediana.
- **Não mudei a regra:** o pedido proíbe mudar critério depois de ver os números. Os números do E1 e do F5 dessas 5 curvas não devem ser usados.
- **A emenda que proponho para uma rodada 3,** registrada antes de rodar: a união dos trechos só vale dentro da curva, entre o fim da curva anterior (e_(k−1)) e o ápice. Fora disso, a sequência é cortada como na rodada 1.

**E1 e F5 por curva** (eu e a IA), **o E4 meu** e **o E2 meu**, rodada 1 → rodada 2:

| curva | E1 eu | E1 IA | F5 eu | F5 IA | E4 eu | E2 eu (antes → depois) |
|---|---|---|---|---|---|---|
| C01-esq | 0,28 → 0,43 | 0,00 → 0,00 | 0,86 → 0,83 | 1,00 → 1,00 | 0,02 → 0,02 | 0,10 → 0,11 |
| C02-dir | 0,00 → 0,00 | 0,00 → 0,00 | 0,17 → 0,17 | 0,00 → 0,00 | 0,02 → 0,03 | 0,85 → 0,87 |
| C03-esq | 0,00 → 0,00 | 0,00 → 0,00 | — → — | — → — | 0,02 → 0,00 | 0,02 → 0,03 |
| C04-esq | 0,01 → 0,60 | 0,00 → 0,00 | 0,84 → 0,30 | 0,00 → 0,00 | 0,00 → 0,02 | 0,02 → 0,02 |
| C05-esq | 0,00 → 0,00 | 0,00 → 0,00 | 0,50 → 0,75 | — → — | 0,00 → 0,00 | 0,00 → 0,00 |
| C06-dir | 0,67 → 0,75 | 0,00 → 0,00 | 0,50 → 0,46 | 0,07 → 0,07 | 0,00 → 0,00 | 0,08 → 0,09 |
| C07-dir | 0,09 → 0,44 | 0,00 → 0,07 | 0,87 → 0,56 | 1,00 → 0,93 | 0,02 → 0,08 | 0,03 → 0,03 |
| C08-esq | 0,00 → 0,01 | 0,00 → 0,00 | 0,00 → 0,10 | 0,00 → 0,00 | 0,02 → 0,06 | 0,91 → 0,92 |
| C09-dir | 0,95 → 0,96 | 0,00 → 0,00 | 0,05 → 0,05 | 0,00 → 0,00 | 0,00 → 0,04 | 0,00 → 0,02 |
| C10-dir | 0,77 → 0,81 | 0,00 → 0,00 | 0,97 → 0,98 | 1,00 → 1,00 | 0,00 → 0,00 | 0,02 → 0,02 |
| C11-esq | 0,08 → 0,14 | 0,00 → 0,21 | — → — | — → — | 0,02 → 0,02 | 0,12 → 0,14 |
| C12-esq | 0,22 → 0,53 | 0,00 → 0,00 | 0,81 → 0,47 | 1,00 → 1,00 | 0,00 → 0,00 | 0,66 → 0,68 |
| C13-esq | 0,00 → 0,00 | 0,00 → 0,00 | — → — | — → — | 0,02 → 0,00 | 0,00 → 0,00 |
| C14-esq | 0,32 → 0,42 | 0,00 → 0,00 | — → — | — → — | 0,02 → 0,00 | 0,00 → 0,00 |

#### O modelo leve

O R² é deixando uma sessão de fora; os coeficientes estáveis são os da rodada 2.

| curva | R² rodada 1 | R² rodada 2 | coeficientes estáveis na rodada 2 |
|---|---|---|---|
| C01-esq | 0,318 | 0,040 | pedais_juntos_s, s_vmin_rel, sem_pedal_s, uso_aderencia, volante_depois |
| C02-dir | 0,014 | 0,214 | afastamento_m, escorr_traseiro, plato_s, s_ti_rel, sem_pedal_s, taxa_carga, uso_aderencia, volante_depois |
| C03-esq | 0,157 | 0,467 | alivio, sem_pedal_s, taxa_carga, uso_aderencia |
| C04-esq | 0,262 | 0,093 | afastamento_m, s_b_rel, sem_pedal_s, taxa_carga |
| C05-esq | 0,355 | 0,208 | alivio, plato_s, retomada_s, s_ti_rel, sobreposicao_s, taxa_carga, uso_aderencia, volante_depois |
| C06-dir | -0,044 | -0,035 | afastamento_m, s_ti_rel, uso_aderencia |
| C07-dir | -0,187 | -0,283 | escorr_traseiro, pico_fracao, s_b_rel, sem_pedal_s, t_pico, taxa_carga, uso_aderencia |
| C08-esq | 0,161 | 0,140 | afastamento_m, retomada_s, reversoes, sem_pedal_s, taxa_carga, uso_aderencia, volante_depois |
| C09-dir | 0,676 | 0,624 | alivio, sem_pedal_s |
| C10-dir | 0,257 | 0,274 | alivio, escorr_traseiro, sem_pedal_s, taxa_carga, uso_aderencia |
| C11-esq | -0,294 | -0,290 | afastamento_m, alivio, irregularidade, plato_s, reversoes, sem_pedal_s, uso_aderencia |
| C12-esq | 0,501 | 0,238 | s_vmin_rel, sem_pedal_s, taxa_carga, uso_aderencia |
| C13-esq | -0,134 | 0,208 | alivio, irregularidade, retomada_s, uso_aderencia |
| C14-esq | 0,251 | -0,040 | alivio, irregularidade, retomada_s, s_ti_rel, uso_aderencia |

O R² cai justamente nas curvas afetadas pelo defeito da entrada (C01, de 0,318 para 0,040; C04, de 0,262 para 0,093; C12, de 0,501 para 0,238; C14, de 0,251 para −0,040), porque o indicador `s_ti_rel` delas mudou de sentido. Nas outras, ele fica parecido ou sobe (C02, C03 e C13).

#### A frenagem emendada (o freio desde o ápice anterior)

| curva | passagens |
|---|---|
| C10 | 78 |
| C08 | 6 |
| C02 | 5 |
| C05 | 4 |
| C09 | 1 |
| as outras | 0 |

É a mesma nas duas rodadas: a regra não mudou. A C10, depois da C09, concentra quase todas, como a seção 2 já dizia.

#### D.3 As minhas sessões depois de 24/10 (tabela à parte, só na rodada 2)

- **As voltas:** 17, todas do piloto, na pista original. Nenhuma ficou fora da seleção.
  - 15 são das sessões aceitas com margem (01/11, 07/11 18:46 e 12/11);
  - 2 são de `2026-11-07_19-52-33`, que a regra de sessão do relatório de evolução junta à de 07/11 18:46.
- **Como foram medidas:** com as fases, o envelope e a calibração das 144. A soma das fases fecha em 0,000 s.
- **A margem de ±2 ms** ficou marcada (`sessao_com_margem`). Nenhuma das perdas dos 3 maiores erros fica perto da margem.

| sessão | os 3 maiores erros, contra a volta do modelo | com margem |
|---|---|---|
| 2026-11-01 | consistencia; C12-esq frenagem (+0.438 s); C03-esq meio (+0.437 s) | sim |
| 2026-11-07 | consistencia; C12-esq frenagem (+0.605 s); C11-esq meio (+0.470 s) | sim |
| 2026-11-12 | consistencia; C04-esq frenagem (+0.498 s); C14-esq reta (+0.409 s) | sim |

#### D.6 O E3 nas saídas de traseira de 01/11

- **Como as voltas foram achadas:**
  - pelo número do relato, conferido pelo tempo do `session-index.json`: 4:45,743, 3:44,219, 2:25,948 e 2:39,678;
  - a volta 10 foi achada pelo tempo das amostras, porque o número da gravação não bateu.
- **O portão:** as 4 voltas são recusadas pelo portão do Modelo 2 (volta longa demais, carro parado, fora de pista; a volta 11 passa pelo box). O portão não mudou: o E3 rodou só nas 7 passagens citadas.
- **O resultado:** o E3 diz "aplica" em **5 das 7**, igual nas duas rodadas (o E3 não mudou e a calibração é a mesma).

| volta relatada | curva | volta na gravação | E3 rodada 1 | E3 rodada 2 | x = p95 de \|β\| − mediana da IA | p95 de \|β\| | portão |
|---|---|---|---|---|---|---|---|
| 3 | C05-esq | 0002 | nao_aplica | nao_aplica | -4,35° | 1,85° | recusada: volta longa demais (285.7s > 200s); carro parado em 48.9% das amostras; fora de pista em 9.1% das amostras |
| 3 | C06-dir | 0002 | aplica | aplica | 56,07° | 59,11° | recusada: volta longa demais (285.7s > 200s); carro parado em 48.9% das amostras; fora de pista em 9.1% das amostras |
| 3 | C13-esq | 0002 | aplica | aplica | 7,01° | 8,17° | recusada: volta longa demais (285.7s > 200s); carro parado em 48.9% das amostras; fora de pista em 9.1% das amostras |
| 4 | C02-dir | 0003 | aplica | aplica | 1,30° | 2,98° | recusada: volta longa demais (224.2s > 200s); carro parado em 41.5% das amostras |
| 4 | C06-dir | 0003 | aplica | aplica | 64,62° | 67,67° | recusada: volta longa demais (224.2s > 200s); carro parado em 41.5% das amostras |
| 10 | C05-esq | 0009 | nao_aplica | nao_aplica | -3,11° | 3,09° | recusada: carro parado em 23.2% das amostras |
| 11 | C01-esq | 0010 | aplica | aplica | 12,77° | 17,26° | recusada: carro parado em 32.9% das amostras; box |

- **As duas da C05 que não aplicam:** o p95 de |β| delas (1,85° e 3,09°) fica abaixo da mediana da IA na C05, que é cerca de 6,2°.
  - Ou a referência da IA na C05 é alta (é uma passagem só, a de 22/10);
  - ou a saída de traseira não chegou à deriva que o E3 mede.

  É uma revocação só sobre os casos relatados: a lista não tem "não aplica" e não dá precisão.
- **As 5 que aplicam** vão de 2,98° (C02, volta 4) a 67,67° (C06, volta 4). As duas da C06 passam de 59°: são as rodadas.

#### D.5 Os testes

Novos em `backend/tests/test_modelo2.py`, numa volta sintética:

- **a retomada com acelerador parcial na entrada:** na rodada 1, ela fica 0,3 s antes da mínima; na rodada 2, depois;
- **as regras fixas da retomada:** a subida que volta abaixo do começo antes de 0,5 s é descartada; o pleno na mínima; sem subida de 0,10, não há retomada;
- **a entrada com um contraesterço antes do ápice:** a sequência não é cortada, e o E4 da rodada 2 o vê. Sem troca de sinal, ela continua cortando;
- **o ranking da rodada 2 sem o peso**, e o ponderado como informativo;
- **a perda contra a volta do modelo:** a soma fecha a diferença de tempo de volta;
- **a forma do pedal nunca é comparada com a volta do modelo:**
  - o F4 explica contra a "Sua melhor volta";
  - o F1 é comparado com a volta do modelo, como ponto;
  - sem a melhor volta diferente, nenhum detector de forma explica;
- **o kit 2:** as páginas da literatura têm "aplica", "não aplica", "nao sei" e a fonte, e não escrevem "IA".

**Os testes do 38 continuam passando sem mudança.** A rodada 1 é o padrão (`rodada=1`) de todas as funções.

### Parte E.1 — o kit 2 (antes da parada)

**Os arquivos:**

| o quê | onde |
|---|---|
| o kit 2 | `data/ml/modelo2/rodada2/rotulagem/kit2_rotulagem.html` (6,6 MB, sha256 `56aad227…`, também em `resultados.json`); cópia em `docs/handoff/2026-10-29_42_modelo2-rodada-2_kit2_rotulagem.html` |
| o CSV dos rótulos | o mesmo do 38: `data/ml/modelo2/rotulagem/2026-10-24_38_modelo2-erro-tecnica-e-estilo_rotulagem.csv`. Conferido em 18/11: 120 linhas, nenhum rótulo e nenhuma observação. Continua vazio |
| a consistência | `data/ml/modelo2/rodada2/rotulagem/kit2_consistencia.html` e `kit2_consistencia.csv`: 30 das 120 passagens (semente 42), com os ids R-01 a R-30 e em outra ordem. Cópias em `docs/handoff/` |
| o gabarito do kit 2 | `data/ml/modelo2/rodada2/kit2_gabarito.json`, fora do git: os estados das duas rodadas, a origem, a melhor volta usada e o de-para da consistência |

**O kit do 38** e o gabarito dele ficaram como estavam.

**O que o kit 2 mostra em cada passagem:**

- **o mapa e cinco traços:** os pedais, o volante, a velocidade, a guinada e a linha (o afastamento do centro para fora da curva);
- **a "Volta de referência" (cinza):** na velocidade e na linha. Nos pedais, só os pontos "freia (referência)" e "retoma (referência)";
- **os canais que a Volta de referência não tem:** no volante e na guinada, o kit escreve que ela não tem o canal;
- **a "Sua melhor volta" (tracejada):** em todos os canais;
- **sem a palavra "IA":** conferi no HTML que ela não aparece.

**A segunda melhor volta:** a melhor volta não é a volta de nenhuma das 120 passagens, então a segunda melhor não foi usada.

**Antes das passagens de cada pergunta, uma página** com:

- o desenho esquemático do "aplica" e do "não aplica", feito pelo código;
- a assinatura e a fonte da tabela da pesquisa;
- onde olhar e o que comparar com as duas referências;
- a regra "na dúvida, nao sei".

**O que continua escondido:** o estado do detector e a origem. **Só para o relatório, pelo gabarito,** as passagens da IA por pergunta são: F4, 7; F5, 6; M6, 3; E2, 2; E3, 2.

**O que você faz:**

1. Abra o `kit2_rotulagem.html` e preencha a coluna `rotulo` do CSV do 38 com `aplica`, `nao aplica` ou `nao sei`.
2. **Pelo menos 3 dias depois,** abra o `kit2_consistencia.html` e preencha o `kit2_consistencia.csv`, sem olhar os rótulos de antes.
3. Se houver uma segunda pessoa, ela usa o mesmo kit e um CSV próprio, sem ver os seus rótulos.


### F.1 O roteiro das voltas de teste (`552e892d`, antes de qualquer sessão)

**Os arquivos, em `docs/experimentos/`:**

- `2026-11-17_42_voltas_de_teste_roteiro.md`: os comportamentos, a sessão, o plano volta a volta e o item 4;
- `2026-11-17_42_voltas_de_teste_folha.html`: a folha para imprimir, uma tabela por sessão, com a frase de cada volta e a caixa do resultado;
- `2026-11-17_42_voltas_de_teste_marcacao.csv`: uma linha por comportamento e volta, mais as voltas normais. Você marca `consegui`, `nao consegui` ou `nao sei`;
- `2026-11-17_42_voltas_de_teste_esperado.json`: o que se espera de cada comportamento (os detectores que devem dizer "aplica" ou "não aplica" e os que não devem mudar), legível pela Parte F.2.

**O conteúdo:**

- **Os comportamentos provocados:** 21, que cobrem todos os detectores menos dois: F1 a F8, E1 a E6, M1 a M9, V1, V2 e V3.
- **Os que ficam de fora,** com o motivo:
  - **V4**, a temperatura dos pneus: acompanha o ritmo de várias voltas;
  - **V5**, a consistência: precisa de 5 voltas iguais, e uma sessão de provocações é inconsistente por construção.
- **O F6 (travar a roda)** entra como tentativa: com ABS, a roda pode não travar.
- **As curvas** foram escolhidas pela física de cada uma:
  - as frenagens fortes depois de reta longa (C01, C04);
  - as lentas e médias com frenagem (C06, C09, C10, C12);
  - as saídas em marcha baixa (C08, C12);
  - as médias sem frenagem (C03, C11).

  A C13 e a C14 ficam fora de propósito, por segurança.
- **As passagens:** em cada comportamento, 3 provocadas, alternando as duas curvas. Os controles são as passagens normais nas mesmas curvas, das voltas normais entre os blocos.
- **As sessões:** duas, com 25 e 21 voltas (cerca de 37 e 31 minutos):
  - no máximo dois comportamentos por volta, em curvas a 3 ou mais curvas de distância;
  - uma volta normal depois de cada bloco;
  - os comportamentos de risco na sessão 2, com o sobresterço de potência no último bloco.

**O item 4, as sessões de teste fora de tudo:** não há jeito limpo com o que já existe. Parei neste item, como manda o pedido.

- **A anotação de sessão** (`docs/experimentos/anotacoes_de_sessao.csv`) só marca a origem.
  - Marcar a sessão de teste como `desconhecida` seria uma origem falsa.
  - E tiraria as voltas também do Modelo 2, que precisa delas na F.2.
- **O engenheiro do pedido 52 é ao vivo:** nenhuma marca depois da sessão tira as voltas da "melhor da sessão" e da "volta lenta" dele.
- **A proposta,** no roteiro, seção 3:
  - uma coluna `finalidade` = `teste_provocado` na anotação de sessão, sem mudar a origem;
  - a seleção das voltas do piloto, os treinos (a LSTM incluída) e a avaliação do aprendizado deixam essas sessões de fora;
  - o Modelo 2 lê essas sessões só pedindo, como faz com a cópia da pista;
  - no engenheiro ao vivo, você desliga o coach no app antes de sair dos boxes (já existe). Como alternativa, um botão "sessão de teste".

  **Até a decisão, as sessões de teste não devem ser gravadas.**

### O que precisa de decisão

1. **O defeito da regra da entrada (seção "E4, a entrada, E1 e F5").** A emenda proposta: a união dos trechos só vale entre o fim da curva anterior e o ápice.
   - Se você aprovar, ela entra como rodada 3, registrada antes de rodar.
   - Até lá, o E1, o F5, o E5, o E6 e a parte de entrada do estilo da C01, da C04, da C07, da C12 e da C14 da rodada 2 não devem ser usados.
   - Os rótulos do kit 2 servem para as duas rodadas e para uma rodada 3, porque o kit não depende da regra.
2. **O item 4 da Parte F.1:** como deixar as sessões de teste fora de tudo. A proposta está no roteiro, seção 3. **Até a decisão, as sessões de teste não devem ser gravadas.**
3. **O M7 na IA** ainda dá "aplica" em 9 das 14 curvas, mesmo com a retomada nova. É uma limitação para uma rodada 3. Não proponho nada agora, porque os rótulos do kit não incluem o M7.

### O que falta (depois da parada)

- **A Parte B**, quando as gravações da IA em níveis estiverem anotadas (`docs/experimentos/ia_niveis.csv`).
- **A Parte E.2**, quando os rótulos do kit 2 e da consistência chegarem:
  - a precisão e a revocação das duas rodadas;
  - o kappa;
  - a galeria;
  - a seção da H.4 no relatório do 38.
- **A Parte F.2**, depois da decisão do item 4 e das sessões de teste.
- **A Parte G:**
  - a seção da rodada 2 com os resultados e a validação, em `docs/modelo2_tecnica_e_estilo.md`;
  - as linhas da lista viva;
  - a arquitetura, se mudar.
- **O merge em `develop` e o envio.**

### Testes

**A suíte do backend, na pasta do 48, depois de todo o código desta etapa:** 1.059 passam, nenhuma falha (10 min 0 s). Antes do código das Partes C e D eram 1.051. A saída está em `docs/handoff/2026-10-29_42_modelo2-rodada-2_pytest.txt`, que substitui a da tarde.

O arquivo do Modelo 2 (`tests/test_modelo2.py`) tem 50 testes: os do 38, os 7 do item 6 e os 8 da Parte D.5, todos passando.

### O envio

O controle de permissões recusou o `push` neste pedido, então não tentei de novo. O remoto tem a branch em `1e1ea229`. Rode pelo terminal, um comando por vez:

```bash
git -C C:/Users/Dokas/Desktop/f1-telemetry-analyzer-48 push origin etapa/modelo2-rodada-2
```

```bash
git -C C:/Users/Dokas/Desktop/f1-telemetry-analyzer-48 ls-remote origin refs/heads/etapa/modelo2-rodada-2
```

O hash do `ls-remote` deve ser o de `git -C C:/Users/Dokas/Desktop/f1-telemetry-analyzer-48 rev-parse etapa/modelo2-rodada-2`.

**A conferência antes do envio:**

- os commits desta etapa mudam `backend/`, `docs/` e os arquivos de `docs/handoff/` e `docs/experimentos/` listados no começo;
- o maior é o kit 2 (6,6 MB). Nada passa de 50 MB;
- nenhuma gravação, nenhum arquivo de `data/` e nenhum segredo;
- os gabaritos (`kit2_gabarito.json` e o do 38) ficam fora do git.

---

# Os relatórios anteriores deste pedido, como foram gravados


## A tarde de 17/11: a Parte A e o código do item 6: a Parte A e o código do item 6

O Eduardo decidiu na "Atualização de 17/11, à tarde" do pedido:

- as 3 sessões são aceitas, com uma margem de ±2 ms;
- quem reaprova o store é o pedido 54;
- o que achei na 0.6 está aprovado;
- agora, só a Parte A e o código, sem ler o store.

Fiz isso e parei. **Nada leu o store, e nenhuma conta das voltas rodou.** O `acs.exe` estava fechado.

### O texto do pedido

A seção nova (itens 1 a 8) estava modificada na pasta, sem commit. Foi commitada primeiro, em `46066db8`.

### A Parte A (`ba776e82`, antes de qualquer código)

A seção 4 de `docs/modelo2_tecnica_e_estilo.md`, "Rodada 2: as emendas de 29/10 e a referência de 15/11", tem os valores fixos:

- **A retomada (s_pu):**
  - a busca vai de s_vmin até e_k + 50 m;
  - o começo é o último ponto no menor acelerador visto desde a mínima, com tolerância de 0,02;
  - a subida é de pelo menos 0,10 acima do começo;
  - é **"contínua"** quando, nos 0,5 s seguintes, o acelerador não fica abaixo do começo menos 0,02;
  - com o acelerador ≥ 0,90 na mínima, s_pu = s_vmin (`retomada_no_pleno`);
  - s_full não muda.
- **A entrada (s_ti):**
  - o limiar continua 0,15·δ_pk, o mesmo do F5. O porquê, tirado da definição, está no documento;
  - dois trechos acima do limiar são unidos quando, no buraco entre eles, o volante passa para o outro lado além de 0,05·δ_pk (o ruído do E4). Um buraco sem troca de sinal continua cortando.
- **O E4:** a janela vai de b_k a e_k. Nas curvas sem frenagem, b_k = a_k. Conferi que são a C03, a C05, a C11, a C13 e a C14, nas fases da rodada 1, como diz o pedido.
- **O ranking:** a pontuação é a perda mediana, sem o peso. O ranking ponderado fica como informativo.
- **A família das emendas:**
  - pela retomada: M6, M7, M8, `retoma`, `apice_ao_pleno_s`, a consistência do estilo e a cadeia causal;
  - pela entrada: E1, F5, E5, E6, a taxa de entrada, `guinada_por_roda` e `beta_entrada`;
  - pela janela: E4.
- **A referência:** uma tabela com os 12 lugares do Modelo 2 que usam uma volta de referência, com o que muda em cada um. Também está registrada a regra da atribuição: os detectores "de ponto" são comparados com a volta do modelo, e os "de forma" com a "Sua melhor volta". Se nenhum explicar, o resultado é "não conclusivo".
- **A margem de ±2 ms:**
  - a lista vem do meta, pelas chaves que o pedido 54 registrou em `docs/store_v2_e_evolucao.md` (`76f1c21e`, na pasta do 47): `sessoes_aceitas_com_margem` e `margem_linha_do_jogo_ms`;
  - nenhum detector depende de tempo nessa escala: o menor limiar é de 0,03 s, 15 vezes a margem.
- **A honestidade da rodada:** a rodada 2 também é calculada contra a `#0013`, marcada "só comparação". Também estão registradas as pastas de saída, os 144 `lap_id`, a frenagem emendada e o que se espera da validação (o kit 2, o kappa ≥ 0,6, a galeria e as voltas de teste).
- **Os ADRs:** uma linha de atualização no ADR 0023 (as emendas e a validação) e uma no ADR 0032 (o item 6 muda para o Modelo 2; a LSTM fica na `#0013`).

### O código (`9b6f56b9`)

- **`backend/ml/modelo2/dados.py`:**
  - `pasta_da_rodada(nome)`: uma pasta dentro de `data/ml/modelo2/`. Ela recusa o nome vazio, um caminho e o nome de um arquivo da rodada 1;
  - `voltas_da_rodada1()`: os 144 `lap_id`, da lista versionada no git (`docs/handoff/2026-10-24_38_..._canais_e_conferencias.json`). Ela confere que são 144 e únicos;
  - `sessoes_com_margem(meta)`: a lista e a margem tiradas do meta. Sem a chave da margem, vale 2,0 ms;
  - o `carregar(track, saida, so_ids, mais_ids)`:
    - lê os caches da rodada 1 (`derivados.parquet` e `fora_do_store.*`) e não os regrava;
    - grava só em `saida`, e só as taxas que faltam. Sem `saida`, não grava nada;
    - restringe às voltas pedidas e para se faltar alguma;
    - marca `com_margem` nas voltas das sessões da lista;
    - as 10 voltas de fora do store continuam vindo do cache da rodada 1;
    - **a trava do store (`aprovado`) continua igual.**
- **`backend/ml/modelo2/perda.py`:**
  - a tabela das perdas ganha `sessao_com_margem`, `dentro_da_margem` e `dentro_da_margem_vs_melhor`;
  - no ranking, uma perda dentro da margem conta como zero, ou seja, não é perda nem ganho;
  - a sessão leva a marca `sessao_com_margem`.
- **`backend/ml/scripts/modelo2.py`:**
  - o `todos` passou a exigir `--saida`;
  - tudo vai para `data/ml/modelo2/<saida>/`, inclusive o kit e o gabarito, e só com os 144 `lap_id`;
  - as passagens levam `sessao_com_margem`, e a perda usa a margem do meta;
  - o `resultados.json` traz a pasta, a fonte da lista e as sessões com margem.
- **O que este item não faz** (fica para a Parte D, como diz o pedido): o código das emendas (a retomada, a entrada, o E4 e o ranking sem peso), a volta do modelo como referência e a tabela das voltas depois de 24/10.

### Os testes

Sete testes novos em `backend/tests/test_modelo2.py`:

- a lista das 144 voltas: 14 da IA e 10 de fora do store;
- `pasta_da_rodada` recusa a raiz e os nomes da rodada 1;
- as sessões com margem vêm do meta, e a margem padrão é 2,0 ms;
- numa volta sintética 1 ms mais lenta, a perda fica marcada "dentro da margem" só na sessão aceita com margem;
- um ganho de 1 ms na frenagem deixa de virar "falso ganho" com a margem: sem a margem, ele vira;
- o `carregar` com um store e um cache falsos:
  - os arquivos da rodada 1 ficam iguais, byte a byte e na data;
  - só a volta nova tem as taxas calculadas, e elas vão só para a pasta da rodada;
  - sem `saida`, nada é gravado;
- o `carregar` para quando falta uma volta pedida, quando a saída é a própria raiz e quando o store está reprovado.

**A suíte do backend, na pasta do 48:** 1051 passam, nenhuma falha (8 min 55 s). A saída está em `docs/handoff/2026-10-29_42_modelo2-rodada-2_pytest.txt`. O `test_leitura`, que falhava na pasta separada (os pedidos 47 a 50), agora passa, porque a geometria oficial ficou ligada na 0.3.

### Um ponto para você conferir antes de rodar

**"Os limiares calibrados na rodada 1 não mudam" (Parte A.3).** Li assim:

- a regra de calibração não muda;
- os detectores cujo indicador mudou com as emendas são recalibrados pela mesma regra, nas mesmas passagens da IA, porque o número antigo media outra coisa;
- os outros ficam com os mesmos valores.

Isso está escrito na seção 4.3. Se a sua intenção era outra, é o momento de dizer, antes de qualquer conta.

### O que falta

- **Quando o pedido 54 reaprovar o store:**
  - a Parte 0, itens 5 e 6. Antes de ler, confiro pelo SHA-256 os 3 vínculos de `data/reference_models` contra a pasta principal, e refaço o vínculo se o arquivo tiver sido regravado;
  - as Partes C, D, E.1 e F.1, e o relatório parcial delas.
- **Depois da sua parada:** as Partes B, E.2, F.2 e G, o merge e o envio de `develop`.

### O envio

O remoto tem a branch em `a8e7a518`: você enviou. Faltam os commits da tarde. Rode pelo terminal, um comando por vez:

```bash
git -C C:/Users/Dokas/Desktop/f1-telemetry-analyzer-48 push origin etapa/modelo2-rodada-2
```

```bash
git -C C:/Users/Dokas/Desktop/f1-telemetry-analyzer-48 ls-remote origin refs/heads/etapa/modelo2-rodada-2
```

O hash do `ls-remote` deve ser o de `git -C C:/Users/Dokas/Desktop/f1-telemetry-analyzer-48 rev-parse etapa/modelo2-rodada-2`.

**A conferência antes do envio:** os commits da tarde mudam só `docs/` e `backend/` (código, testes e a saída do pytest, com 9 KB). Nada passa de 50 MB, e não há gravações, `data/` nem segredos.

---

# A parada da manhã (Parte 0, item 5), como foi relatada

## Resumo

O Modelo 2 recusa o store v2 reprovado. O carregador (`backend/ml/modelo2/dados.py`, `carregar`) para com `PARADO: store v2 ausente ou nao aprovado.`, e o store está com `aprovado: false` desde 15/11. O pedido manda parar e avisar nesse caso (Parte 0, item 5), sem contornar. Então parei na Parte 0.

Feito: os itens 0.1 a 0.4 e a conferência do jogo (0.7). Não feito: a rodada 1 refeita (0.6) e as Partes A, C, D, E.1 e F.1. Nada foi escrito em `data/ml/modelo2/` nem em `data/reference_models`.

## Parte 0

### 0.1 A pasta

- Nenhuma outra sessão está ativa na pasta do 48. O `list_sessions` mostra todas paradas, e o `git worktree list` mostra a do 48 em `etapa/diagnostico-m1` (`bbff5c97`), antes da troca.
- O 52 está na pasta principal, em `etapa/engenheiro` (`1edbebf3`). Não foi tocado.

### 0.2 A branch

- **Antes:** a pasta do 48 estava em `etapa/diagnostico-m1`, limpa, salvo o texto do pedido 42 modificado (a versão de 17/11, sem commit, como diz o pedido).
- **A troca:** o texto do pedido é igual em `etapa/diagnostico-m1` e em `develop`. Por isso o `git switch -c etapa/modelo2-rodada-2 develop` levou a modificação sem recusar.
- **O commit:** o texto foi commitado primeiro, em `dc405d6a`.
- **Uma diferença com o contexto (só informação):** o pedido diz que `develop` está "no GitHub em `36152415`". O `develop` local está em `14fe1ca0`, dois commits à frente (`99004b42` e `14fe1ca0`, relatórios do 51). A referência local `origin/develop` também aponta para `14fe1ca0`. Não muda nada aqui.

### 0.3 O que fica fora do git, e os links

O que o Modelo 2 lê fora do git:

| O quê | Onde o código procura (pasta do 48) | Situação |
|---|---|---|
| store v2, caches do Modelo 2, saídas da rodada 1 | `data/ml` | junção já existente → `...\f1-telemetry-analyzer\data\ml` (conferido) |
| gravações | `data/recordings` | junção já existente → `...\f1-telemetry-analyzer\data\recordings` (conferido) |
| geometria da grade (`vhe_interlagos_gp_kn5_surface_interval_geometry.json`) | `data/cache/tracks` | junção já existente → `...\f1-telemetry-analyzer\data\cache` (conferido) |
| gravações do app instalado | `%APPDATA%\Automobilista Telemetria\data\recordings` | fora do repositório, lido direto |
| `data/feature_store` | `data/feature_store` | **faltava.** Junção criada → `...\f1-telemetry-analyzer\data\feature_store`. Nenhum código de `backend/ml` ou `backend/core` lê essa pasta; ela foi ligada porque o pedido a lista. |
| a geometria oficial (`vhe_interlagos.geometry.json`) | `data/reference_models` | **faltava.** Vínculo real (hard link) criado |
| a volta do modelo (`vhe_interlagos.volta_do_modelo.json`) | `data/reference_models` | **faltava.** Vínculo real criado |
| o modelo do coach (`vhe_interlagos.json`) | `data/reference_models` | **faltava, e não estava na lista do pedido.** O `modelo2 todos` lê esse arquivo (`model_path`) para achar o id da volta de referência. Vínculo real criado |

- **Por que vínculo real:** a junção só serve para pastas. A `data/reference_models` da pasta do 48 já existe e tem um arquivo versionado (`vhe_interlagos.optimal.json`), então ela não pode virar uma junção sem apagar esse arquivo. Para os três arquivos, usei `mklink /H`, que não copia nada: é o mesmo arquivo nas duas pastas.
- **A conferência:** o `fsutil hardlink list` mostra os dois caminhos de cada arquivo, e o SHA-256 é igual nas duas pastas: geometria `811da4c9…`, modelo do coach `f8e61864…`, volta do modelo `e8651d45…`.
- **O cuidado:** qualquer escrita nesses três caminhos da pasta do 48 muda o arquivo da principal. O pedido não escreve em `data/reference_models`. Para desfazer, basta apagar os três vínculos e a junção na pasta do 48: os originais ficam.
- **O git:** os quatro caminhos são ignorados pelo `.gitignore` (linhas 40 e 73). O `git status` continua limpo.

### 0.4 O que é escrito

Nada até agora. Nenhum arquivo em `data/ml/modelo2/`, nem em `data/reference_models`, nem em `docs/`, salvo este relatório.

### 0.5 A trava do store v2: o Modelo 2 recusa → PARADO

- **O meta do store** (`data/ml/laps_grid_v2_meta.json`): `aprovado: false`, construído em 15/11 às 19:34 UTC, commit `a168e41f`, 721 voltas.
- **A checagem que falha:** "a linha do jogo fica onde foi medida (pedido 34)": registrada a 1,463 m, tolerância de 0,10 m, mediana de 1,4972 m. As sessões fora:

  | Sessão | Voltas | Mediana | Desvio |
  |---|---|---|---|
  | `2026-11-01_19-47-03` | 6 | 1,606 m | 0,018 m |
  | `2026-11-07_18-46-00` | 5 | 1,581 m | 0,080 m |
  | `2026-11-12_22-57-03` | 4 | 1,573 m | 0,023 m |

  As outras checagens passam: o período contra o cronômetro, sem box, sem duplicatas e uma geometria só.
- **O que o Modelo 2 faz:** `backend/ml/modelo2/dados.py`, linha 302, logo no começo de `carregar`:

  ```python
  if not meta or not meta.get("aprovado"):
      raise SystemExit("PARADO: store v2 ausente ou nao aprovado.")
  ```

  Rodei só essa chamada (`carregar(None)`, que para nessa linha antes de ler qualquer dado). A saída foi `SystemExit: PARADO: store v2 ausente ou nao aprovado.` Não rodei o `modelo2 todos`.
- **As passagens das 3 sessões reprovadas:** pelo meta, são 15 voltas `humano` (6 + 5 + 4), ou seja, até 210 passagens (15 × 14 curvas), antes do portão do Modelo 2. Todas são posteriores ao kit de 24/10, então nenhuma está nas 120 passagens nem na rodada 1. Elas só entrariam na tabela à parte da Parte D.3 e no E3 das saídas de traseira (D.6, a sessão de 01/11).
- **Não contornei:** não mudei o portão, não passei `aprovado` à força e não li o store por outro caminho.

### 0.6 A rodada 1 refeita: não rodou (depende do store)

O que encontrei ao preparar, para quando houver decisão:

1. **O `modelo2 todos` sobrescreve a rodada 1.** O `run()` grava direto em `data/ml/modelo2/` (`resultados.json`, `erros_por_sessao.json`, `passagens.parquet`, `tecnicas.json` e outros). O `build_kit` regrava o `rotulagem_gabarito.json`, e o cache `derivados.parquet` também é regravado. Antes de refazer a rodada 1, o script precisa de uma pasta de saída própria (por exemplo, `data/ml/modelo2/rodada1_refeita/`), com os caches lidos e não regravados. É uma mudança de código pequena, ainda não feita.
2. **O store novo tem voltas que a rodada 1 não tinha.** A rodada 1 tem 144 voltas (130 do piloto e 14 da IA; 10 de fora do store), do store de 22/10 (commit `2b16db32`). O store de 15/11 traz:
   - as sessões de 24/10 (`13-26-12`, 3 voltas `humano`; `13-43-32`, 6 voltas `humano`), que na rodada 1 eram lidas "de fora do store" (`FORA_DO_STORE`). A de 22/10 (`09-46-01`) aparece no store como `misturada` (1 volta);
   - 17 voltas `humano` posteriores a 24/10: as 15 das sessões reprovadas e 2 de `2026-11-07_19-52-33`.

   Para reproduzir a rodada 1, a seleção precisa ser restrita aos 144 `lap_id` dela. O `store_selection` do 38 pega tudo do store pelo filtro da evolução.
3. **O id da referência:** o `run()` procura a volta da IA no modelo do coach (`LEGACY_AI_KIND`) e, se não houver, usa a `#0013` (`VOLTA_IA` de `ml.pista_teste.condicoes`, pedido 51). Isso reproduz a referência da rodada 1, se a `#0013` for a mesma volta.

### 0.7 O jogo

O `acs.exe` estava fechado na conferência (17/11, ~15:10). Nenhuma conta pesada foi rodada.

## Partes A, C, D, E.1 e F.1

Não começaram. A Parte A só registra regras e não lê o store. Mesmo assim, o pedido manda parar na Parte 0 quando o Modelo 2 recusa o store. E a ordem do pedido põe a conferência da rodada 1 (0.6) antes de tudo que a compara.

## O que precisa de decisão

1. **O store v2 reprovado.** Os caminhos que vejo, para você escolher:
   - **(a) esperar** o pedido próprio da causa da linha do jogo (1,57 a 1,61 m contra 1,463 m), que reaprova o store, e então retomar daqui;
   - **(b) autorizar, por escrito num pedido, uma exceção registrada para o Modelo 2:** ele lê o store reprovado, as voltas das 3 sessões reprovadas ficam marcadas, e o portão continua no código, com a exceção explícita. O pedido já diz que a diferença de cerca de 0,14 m no s = 0 não muda a curva de uma passagem. Isso é decisão sua: eu não faço;
   - **(c) seguir só com a Parte A** (registrar as regras, sem ler o store) e parar de novo antes da 0.6.
2. **A rodada 1 refeita (para quando o store for liberado):** confirmar o que encontrei na 0.6, ou seja, uma pasta de saída própria e a seleção restrita aos 144 `lap_id` da rodada 1. Sem isso, a comparação mistura dados novos com as emendas, que é o que a 0.6 quer evitar.
3. **O modelo do coach** (`vhe_interlagos.json`) também é lido pelo Modelo 2 e não estava na lista da 0.3. Ficou ligado por vínculo real, como os outros. Confirme se está bem assim.

## O que falta

- A Parte 0, itens 5 (depois da decisão) e 6;
- as Partes A, C, D, E.1 e F.1, e o relatório parcial delas;
- depois da sua parada: as Partes B, E.2, F.2 e G, o merge e o envio de `develop`.

## Testes

Nenhum código mudou, então a suíte não foi rodada.

## Envio ao GitHub

Tentei o envio da branch uma vez, depois do commit `e1151879`, e o controle de permissões recusou. Não insisti. Nada foi enviado: a branch só existe no local. Rode pelo terminal, um comando por vez:

```bash
git -C C:/Users/Dokas/Desktop/f1-telemetry-analyzer-48 push -u origin etapa/modelo2-rodada-2
```

```bash
git -C C:/Users/Dokas/Desktop/f1-telemetry-analyzer-48 ls-remote origin refs/heads/etapa/modelo2-rodada-2
```

O hash do `ls-remote` deve ser o mesmo de `git -C C:/Users/Dokas/Desktop/f1-telemetry-analyzer-48 rev-parse etapa/modelo2-rodada-2`.

**A conferência antes do envio:** os commits da branch sobre `develop` mudam só dois arquivos, ambos em `docs/` (o texto do pedido e este relatório). Nenhum passa de 50 MB, nenhum é gravação ou dado de `data/` e nenhum tem segredo.
