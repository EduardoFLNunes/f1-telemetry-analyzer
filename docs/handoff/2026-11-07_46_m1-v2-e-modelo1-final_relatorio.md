# Relatório do pedido 46: M1 v2 e o resultado final do Modelo 1

- **Pedido:** `docs/prompts/2026-11-07_46_m1-v2-e-modelo1-final.md`.
- **Situação:** **feito e conferido,** com o merge em `develop`. **Falta o envio ao GitHub,** que é você quem faz: os comandos estão no fim.
- **Branch:** `etapa/m1-v2-e-modelo1`, a partir de `develop` em `587d0992`. **Ela não parte do merge do pedido 45,** que ainda não existe (veja "A largada").
- **Commits e merges:**
  - em `develop`: `587d0992` Pedido 46: texto do pedido (M1 v2 e resultado final do Modelo 1);
  - `b61a6fe1` Pedido 46, Parte A: ADR 0028 (M1 v2 e o resultado final do Modelo 1), registrado antes de rodar;
  - `89fcd796` Pedido 46, D.1: emenda do ADR 0028 antes da fase de teste (os parâmetros do envelope da M1 v2);
  - `28e70156` Pedido 46, Parte B: a fase de treino da M1 v2 (cargas, pneu e física v2 nas sessões de treino), antes do teste;
  - `1b3f8d2a` Pedido 46, Parte C: a validação da M1 v2 (não aprovada: skill contra R0 0,487 < 0,50; os outros 6 critérios passam);
  - `e264f39e` Pedido 46, Partes D, E e F: o resultado final do Modelo 1, os testes do medidor e a documentação;
  - **merge em `develop`:** `1124b163` Merge etapa/m1-v2-e-modelo1;
  - o commit deste relatório, em `develop`.
- **Arquivos de handoff** (`docs/handoff/2026-11-07_46_m1-v2-e-modelo1-final…`):
  - `_relatorio.md` (este);
  - `_fisica_treino_v2.json` (Parte B: as cargas, o pneu e a física v2 nas sessões de treino);
  - `_curva_do_pneu.png` (B.3);
  - `_validacao_v2.json` (Parte C: o veredito e todas as tabelas, com a v1 ao lado);
  - `_figura_c01_v2.png` e `_figura_c10_v2.png` (C.3);
  - `_modelo1.json` (Parte D: os tempos no medidor, por microssetor, a busca e o critério);
  - `_linhas.png`, `_diferenca_acumulada.png` e `_evolucao.png` (D.2.4);
  - `_testes.txt` (a suíte do backend: 921 passam).

## Em uma frase

**A M1 v2 não foi aprovada, por pouco.** Em 0,5 s, ela corta 48,7% do erro da persistência, e o critério 1 pede 50%. Os outros 6 critérios passam, inclusive o 2, que a v1 não passava. Ela é bem melhor que a v1 nas curvas e na velocidade lateral. **No Modelo 1,** as duas linhas geradas ficam abaixo da volta da IA no medidor e aprovam pelo critério registrado. **Mas o medidor só vê a linha, e não a volta,** e tem correlação de 0,36 com o cronômetro. A linha não vai para o coach.

## A largada

- **Às 11:05, parei antes de começar.** O pedido manda começar depois do merge do pedido 45 em `develop`, e esse merge não existe: o 45 está parado na Parte G. Além disso, o app de desenvolvimento desta pasta estava aberto desde as 10:46 (Electron e backend pelo `.venv`).
- **Às 11:22, você respondeu "Não, pode começar"** à pergunta "O app aberto às 10:46 é o teste do pedido 45?". Com isso, comecei a partir de `develop`, ainda sem o 45.
- **Antes de criar a branch,** commitei o texto do pedido em `develop` (`587d0992`), como você pediu.
- **O que isso deixa para o merge do 45:** os dois pedidos acrescentam uma linha no fim de `docs/decisoes/README.md` (o 45 com a 0027, este com a 0028). É um conflito simples, de juntar as duas linhas.
- **Nenhum arquivo do coach, do rádio, do app, do store v2 ou do Modelo 2 mudou.** Os processos do app aberto às 10:46 não são meus e não foram tocados.

## Parte A: os valores fixos, registrados antes de rodar

**ADR 0028**, commitado em `b61a6fe1`, antes de qualquer conta nas sessões. A emenda da D.1 foi commitada em `89fcd796`, antes da fase de teste.

| o quê | valor | commit |
|---|---|---|
| carga por roda | peso parado, downforce e transferência longitudinal (sempre, `h/L = 0,0915` do `cgHeight`), mais a lateral `λ·h_y·a_y/t` por eixo; bitolas de 1,588 e 1,509 m | `b61a6fe1` |
| medida da carga lateral | regressão de `(fr − fl)/m` e `(rr − rl)/m` contra `a_y`, com \|a_x\| < 0,1 g e `vx` ≥ 10 m/s; bootstrap por volta (200, semente 46) | `b61a6fe1` |
| faixas da carga | `λ` de 0,30 a 0,70; `h_y` de 0,15 a 0,45 m. Fora da faixa numa rodada: usa o limite. Fora em todas, ou intervalo que passa de zero: para (B.5) | `b61a6fe1` |
| quatro rodas | cada roda com o seu ângulo de deriva, a sua carga, a sua força e a sua elipse; o momento de guinada inclui os lados; com a bitola em zero e o pneu da v1, vira a bicicleta da v1 | `b61a6fe1` |
| pneu | `μ(n) = μ_ref·(n/n_ref)^(q−1)`, com `n_ref = g/4`; Fórmula Mágica de Pacejka com `B`, `C`, `D` e `E` tirados de `C_α·n`, `μ(n)·n`, `α_pico` e `f` | `b61a6fe1` |
| faixas do ajuste | `C_α` de 5 a 60; `μ_ref` de 1,0 a 2,5; `q` de 0,6 a 1,0; `α_pico` de 3° a 12°; `f` de 0,7 a 1,0; e os outros 5 como na v1 (10 parâmetros) | `b61a6fe1` |
| correção | Processo Gaussiano da v1, com **6.000 passos** na proporção dos regimes, semente 46. O 6.000 saiu de uma sonda em dados sintéticos: 28 s com 2.000, 102 s com 4.000 e 292 s com 6.000 | `b61a6fe1` |
| "não conclusivo" | distância média aos 10 vizinhos de treino nas 6 entradas padronizadas; corte no percentil 99 dos casos de treino, sem os vizinhos da mesma volta | `b61a6fe1` |
| critérios | os 7 do ADR 0022, sem mudança; R1 é a física v2; a física v1 é só relatada | `b61a6fe1` |
| o que se espera | ganho nas curvas, na faixa de 160 a 220 km/h e em `vy`; nada na reta, na freada e na tração; o critério 1 é o mais difícil | `b61a6fe1` |
| medidor (D.1) | com a v2 aprovada, o envelope da M1 v2 (lateral por saturação dos eixos, frenagem e tração com a transferência); senão, o envelope das voltas reais como está | `b61a6fe1` |
| parâmetros do envelope da v2 | a mediana das 5 rodadas; `A_env` e a grade de velocidades do envelope real | `89fcd796` |
| comparação e critério (D.1) | a volta da IA `#0013` (1:24,829) e a melhor do Eduardo `2026-10-24_13-43-32#0003` (1:26,568), no mesmo medidor. A linha gerada aprova se o tempo dela for ≤ ao da IA, se ficar dentro do corredor do pedido 44 e se a forma ficar ≤ ao p95 das 150 voltas | `b61a6fe1` |
| busca | 100 indivíduos, até 250 gerações ou estagnação, semente 46, sementes das 150 voltas rotuladas e a composição, aptidão só física, sem e com a LSTM como semente | `b61a6fe1` |

**Duas coisas do contexto não batiam com o repositório, e estão registradas no ADR:**

- **a sua melhor volta (1:26,568) não está no store v2.** Ela é de 24/10, e o store é de 22/10, com a melhor humana em 1:26,876. Ela está entre as 150 voltas rotuladas que o pedido 44 preparou (`data/ml/retreino_lstm/`), e foi delas que saíram a comparação e as sementes;
- **o pedido nomeia o relatório `…_m1-v2-e-modelo1_relatorio.md`.** Usei `…_m1-v2-e-modelo1-final_relatorio.md`, que é o assunto do arquivo do pedido (`CLAUDE.md`) e o nome da sua instrução de hoje.

## Parte B: a carga e o pneu medidos

Comando: `validar-v2 --fase treino` (1 h 35 min), só com as sessões de treino. As tabelas completas estão em `docs/modelo_fisico_m1.md`, 7.2.

- **A carga lateral é identificável nas 5 rodadas:**
  - `λ` fica entre 0,645 e 0,651, com intervalo de cerca de ±0,005;
  - `h_y` fica entre 0,322 e 0,363 m;
  - nenhum intervalo passa de zero.

  Cerca de 65% da transferência lateral vai para a frente. `h_y` sai de 19% a 34% acima do `cgHeight` (0,271 m), em parte porque a massa das regressões (578 a 653 kg) está abaixo da real.
- **O erro da carga prevista** contra `wheel_load_*` fica entre 18% e 24% da carga média de cada roda (16% a 17% na reta, 26% a 28% na dianteira esquerda nas curvas). O modelo de carga não tem suspensão nem zebras.
- **O pneu:**
  - entre as rodadas, `C_α` fica entre 30,4 e 34,8, e `μ_ref` entre 2,10 e 2,23;
  - **`q` (0,6), `α_pico` (12°) e `f` (0,7) ficam no limite nas 5 rodadas**, e `κ_D` e `c0` ficam no limite como na v1;
  - a figura mostra o porquê: os pontos de treino quase não passam de 6° de deriva. O pico foi para fora dos dados, e a queda ficou sem efeito;
  - o que pesa é a sensibilidade à carga: com `q = 0,6`, o atrito cai de 2,2 parado para cerca de 1,5 a 270 km/h.
- **A física v2 sozinha nas sessões de treino,** antes do teste:
  - contra a persistência em 0,5 s, o skill fica entre 0,21 e 0,39 (a v1 ficava entre −0,06 e 0,18);
  - contra a física v1, ela corta de 25% a 36% do erro.

## Parte C: a validação, lado a lado com a v1

Comando: `validar-v2 --fase teste` (1 h 34 min), depois do commit da fase de treino. São os mesmos 39.142 casos da v1, conferidos caso a caso.

| nº | critério | v1 | **v2** | v2 |
|---|---|---|---|---|
| 1 | skill contra R0 ≥ 0,50 | 0,202 | **0,487** | **não passa** |
| 2 | skill contra R1 ≥ 0,20 | 0,174 | **0,207** | passa |
| 3 | IC 95% do skill contra R1 > 0 | 0,159 | 0,172 (até 0,245) | passa |
| 4 | positivo em ≥ 4 de 5 sessões | 5 | 5 | passa |
| 5 | \|viés\| ≤ 25% do erro de R1 | 3,9 / 2,2 / 3,3% | 1,9 / 0,4 / 2,8% | passa |
| 6 | cobertura de 80% a 97% | 85,7% | 89,6% | passa |
| 7 | ≥ 5 sessões testáveis | 5 | 5 | passa |

**Veredito: não aprovada.** Nenhum critério, corte ou parâmetro foi mudado depois de ver o teste, e não há v3.

| horizonte | M1 v2 | física v2 | M1 v1 | física v1 | R0 |
|---|---:|---:|---:|---:|---:|
| 0,25 s | 0,153 | 0,178 | 0,189 | 0,212 | 0,270 |
| **0,5 s** | **0,226** | **0,285** | **0,351** | **0,425** | **0,440** |
| 1,0 s | 0,378 | 0,500 | 0,849 | 1,059 | 0,666 |

- **A velocidade lateral, em 0,5 s:**
  - no geral, 0,42 m/s na M1 v2, contra 0,68 na M1 v1 e 0,70 na persistência;
  - nas curvas, 0,48 contra 0,81 e 0,78.

  A longitudinal fica igual nas duas versões (0,39 e 0,40 m/s), e na guinada a v2 também ganha (0,070 contra 0,094 rad/s).
- **Por regime** (skill da M1 v2 contra a persistência; entre parênteses, a M1 v1): curva 0,46 (0,13); freio e volante juntos 0,45 (0,25); reta 0,68 (0,66); freada 0,71 (0,68); tração 0,73 (0,71).
- **Por faixa:** de 160 a 220 km/h, 0,49 (0,08); de 100 a 160, 0,49 (0,24); abaixo de 100, 0,44 (0,22); acima de 220, 0,58 (0,55).
- **Por sessão:** de 0,41 (21/10) a 0,55 (17/10 16:17). Duas sessões passam de 0,50 sozinhas.
- **O que se esperava se confirmou** (curvas, 160 a 220 km/h, velocidade lateral; nada na reta, na freada e na tração). O que faltou foi pouco, e está nas curvas: 0,46 nelas, que são 65% dos casos.
- **O "não conclusivo" funcionou.** Foram marcados 443 casos (1,1%):
  - por regime: 0,3% na reta, 0,6% na freada, 0,5% na tração, 1,2% nas curvas e 4,5% com freio e volante juntos;
  - por sessão: de 0,6% a 2,3%;
  - o corte ficou entre 0,79 e 0,87.
- **A C10:** a v2 escorrega bem menos que a v1. Em 0,5 s, `vy` sai 0,62 m/s acima do gravado, contra 1,47 na v1; em 1,0 s, 1,4 m/s contra 3,5. O carro do jogo ainda faz a curva com `vy` perto de zero. **A C01:** em 0,5 s, a M1 v2 erra a velocidade em 0,14 m/s, e a persistência, em 7,2.
- **Só para informação (C.4),** com os modelos da rodada sem 21/10:
  - em 24/10, o skill contra a persistência é de 0,42 e 0,41, como no teste;
  - em 01/11 cai a 0,12, e a persistência prevê a velocidade lateral melhor que a M1 v2 nessa sessão.
- **A temperatura dos pneus (M2):** o Spearman é de −0,22 na longitudinal e de cerca de zero na lateral e na guinada, como na v1.

## Parte D: o medidor e o resultado final do Modelo 1

- **O medidor:** como a M1 v2 não foi aprovada, é o simulador quase-estacionário com o envelope das voltas reais (`data/ml/vehicle_envelope.json`, sha256 começando por `3e31fd30e528281b`). Ele dá o mesmo tempo para a mesma linha nas duas chamadas.
- **A busca:** levou 3 min e 40 s no total, longe das 6 h.

| linha | medidor | contra a IA | cronômetro |
|---|---:|---:|---:|
| volta da IA | 1:26,284 | — | 1:24,829 |
| a mesma, codificada | 1:27,955 | +1,671 | — |
| sua melhor volta | 1:24,048 | −2,236 | 1:26,568 |
| a mesma, codificada | 1:27,679 | +1,395 | — |
| linha da LSTM geradora | 1:28,244 | +1,960 | — |
| **linha gerada sem a LSTM** | **1:22,898** | **−3,386** | — |
| **linha gerada com a LSTM** | **1:23,481** | **−2,803** | — |

- **Pelo critério registrado, as duas linhas aprovam:** ficam abaixo da IA no medidor, dentro do corredor do pedido 44, e com o serpenteio e a variação de curvatura abaixo do p95.
- **As duas versões da busca:**
  - as duas rodaram as 250 gerações, sem estagnar (25.100 avaliações cada);
  - passaram a IA na geração 4 (sem a LSTM) e na 3 (com ela);
  - a distância entre as duas linhas é de 0,94 m em média, e de 3,96 m no máximo;
  - **a LSTM como semente não ajudou:** com ela, a busca terminou 0,58 s mais lenta.
- **Por microssetor:** a linha sem a LSTM ganha da IA em 24 microssetores e perde em 22. O ganho se concentra no 36, perto da C10 (−0,92 s), e no 0 e no 1, depois da linha (−0,62 e −0,37 s).
- **A incerteza: o que a comparação mede e o que não mede.**
  - o erro conhecido do simulador era de 1,36 s por volta (ADR 0017, no store antigo);
  - nas 150 voltas rotuladas, com esta configuração, o erro médio é de 5,0 s, e a correlação com o cronômetro é de 0,36 (Spearman 0,23);
  - **as voltas da IA e as suas saem com quase o mesmo tempo simulado** (86,2 e 86,1 s), embora no cronômetro estejam a 6 s uma da outra. O medidor supõe o carro sempre no limite do envelope: ele mede a linha, não a execução;
  - **ele chega a inverter a ordem da volta da IA e da sua.**

  A comparação diz que, com o carro no limite do mesmo envelope, a linha gerada dá menos tempo que a da IA. Ela não diz que um piloto faria uma volta mais rápida com ela.
- **A linha gerada não vai para o coach** (ADR 0009). Ela está salva em `data/ml/modelo1_final/` (`linha_sem_lstm.npy`, `linha_com_lstm.npy` e `resultado.json`, com o `geometry_id` `0ed16f0dd2225990`, o `corridor_id` `707d07029036abd6`, o medidor e o commit).

## Parte E: testes

- **`backend/tests/test_m1_v2.py`, 15 testes, todos com dados sintéticos:**
  - a transferência lateral com o sinal certo nas curvas à esquerda e à direita;
  - a soma das 4 cargas igual ao peso mais o downforce;
  - sem bitola, sem transferência lateral;
  - `λ` e `h_y` recuperados de cargas sintéticas;
  - o pneu com o pico no `α_pico`, a queda até `f`, a rigidez `C_α·n` na origem e a curva ímpar;
  - a força máxima crescendo como `carga^q`;
  - **as quatro rodas sem bitola, com o pneu da v1, iguais à bicicleta da v1** (derivadas e passo, com tolerância de 1e-9);
  - o momento de guinada com os lados;
  - a simetria entre a esquerda e a direita;
  - a amostra na proporção dos regimes, com os maiores restos e a mesma semente dando a mesma amostra;
  - a vizinhança do "não conclusivo";
  - o envelope da M1 v2 crescendo com a velocidade e respeitando a aderência e a elipse;
  - o medidor dando o mesmo tempo para a mesma linha nas duas chamadas (com o envelope real e com o da v2).
- **Os testes da v1 continuam passando,** sem mudança.
- **A suíte do backend:** `921 passed, 37 warnings in 701.45s`, a saída completa em `_testes.txt`.

## Parte F: documentação

- **`docs/decisoes/0028-m1-v2.md`:** o registro, a emenda da D.1 e o resultado; uma linha no índice (`README.md`).
- **Linhas de atualização** nos ADRs 0017 e 0022. O 0009 não mudou, porque o medidor não mudou.
- **`docs/modelo_fisico_m1.md`:** a seção 7, "M1 v2" (7.1 o registro, 7.2 a carga e o pneu, 7.3 a validação lado a lado com a v1, 7.4 o ponteiro para o Modelo 1).
- **`docs/arquitetura_ml.md`:** a seção "O medidor do tempo e o resultado final do Modelo 1".
- **`docs/tecnica_de_pilotagem_lista.md`:** sem linha, porque nada da técnica mudou.
- **`docs/backlog.md`:** não editado. Os itens estão abaixo.

## O código novo

- `backend/ml/modelo_carro/fisica_v2.py`: as quatro rodas, a carga, o pneu, o ajuste e o envelope da D.1;
- `backend/ml/modelo_carro/cargas_v2.py`: a medida da carga lateral e o erro da carga;
- `backend/ml/modelo_carro/correcao_v2.py`: a amostra proporcional e a vizinhança;
- `backend/ml/modelo_carro/experimento_v2.py`: as duas fases, o lado a lado e a C.4;
- `backend/ml/modelo_carro/figuras_v2.py`: a curva do pneu, a C01 e a C10;
- `backend/ml/scripts/m1_modelo_carro.py`: o comando `validar-v2`;
- `backend/ml/scripts/modelo1_final.py`: a Parte D.

Os arquivos da v1 em `data/ml/modelo_carro/` não foram sobrescritos: os da v2 levam `_v2`. As gravações só foram lidas, e o `data.acd` não foi aberto. Nenhum pacote foi instalado.

## Itens para o backlog (para o Cowork)

1. **O medidor do Modelo 1 não ordena as voltas reais.** Nas 150 voltas rotuladas, a correlação é de 0,36, e ele não separa a IA do Eduardo. Qualquer "linha mais rápida" do Modelo 1 precisa de um medidor que olhe a execução (o ADR 0009 continua valendo).
2. **A codificação da busca custa de 1,4 a 1,7 s** às voltas reais no medidor. Vale medir de onde vem esse custo (o espaçamento dos pontos de controle) antes de comparar linhas codificadas com voltas cruas.
3. **O ganho da linha gerada se concentra em três microssetores** (o 36, perto da C10, e o 0 e o 1, depois da linha). Vale conferir se é traçado ou se é como o medidor trata a lateral crua nesses pontos.
4. **A M1 fica encerrada neste TCC** (ADR 0028), com a v1 e a v2 registradas. A v2 é o resultado a apresentar: 0,487 contra 0,50.
5. **O pneu da v2 ficou com o pico fora dos dados** (12°, com os dados até 6°). Se um dia houver outra etapa do modelo do carro, ela precisa de voltas no limite da aderência, com deriva acima do pico, para medir `α_pico` e `f`.
6. **A sessão de 01/11 piora a M1 v2** (skill de 0,12): vale olhar o que mudou nela (o equipamento, a forma de pilotar).
7. **A LSTM geradora como semente não ajudou a busca** (−0,58 s em relação a sem ela). Ela continua reprovada também nesse papel.
8. **O merge do pedido 45** vai ter um conflito simples em `docs/decisoes/README.md`, porque os dois pedidos acrescentam uma linha no fim.

## O envio ao GitHub (você roda pelo terminal)

**O que já conferi antes do envio:**

- nenhum arquivo acima de 5 MB entrou nos commits;
- nada de `recordings/`, `data/recordings` ou `data/ml`;
- nenhum segredo, conferido por busca no diff.

**O que vai:**

- **`develop`** é um avanço simples sobre `origin/develop` (`aa576597`), com 8 commits a mais, incluindo o `bd04b93e` do pedido 45 e o commit deste relatório;
- **a branch** é nova no remoto;
- `main` e as tags não vão. Sem `--force`.

```bash
git push origin etapa/m1-v2-e-modelo1
```

```bash
git push origin develop
```

**Quando você avisar que enviou,** eu confiro com `git ls-remote origin` se o hash remoto é igual ao local e registro aqui. Os hashes locais esperados são:

- `etapa/m1-v2-e-modelo1` em `e264f39e3c69d88a6fd62ab88e58df7c1c5f5d0c`;
- `develop` no commit deste relatório, depois de `1124b16325839aee9451564312e8ddb6d357d77f`.

## O envio, conferido (07/11, 14:25)

Você avisou que enviou. Conferi com `git ls-remote origin`:

| ref | hash local | hash no remoto | confere |
|---|---|---|---|
| `etapa/m1-v2-e-modelo1` | `e264f39e3c69d88a6fd62ab88e58df7c1c5f5d0c` | `e264f39e3c69d88a6fd62ab88e58df7c1c5f5d0c` | sim |
| `develop` | `0d2ca732cc7bbf16af7efee4d4e466eb98b70f01` | `0d2ca732cc7bbf16af7efee4d4e466eb98b70f01` | sim |

Este registro do envio fica num commit local em `develop`, que vai no próximo envio.
