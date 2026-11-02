# Relatório do pedido 44: corredor pela borda da superfície e retreino da LSTM geradora (parado na Parte D.5)

- **Pedido:** `docs/prompts/2026-10-29_44_corredor-e-retreino-da-lstm.md`
- **Branch:** `etapa/corredor-e-retreino-lstm`, a partir de `develop` em `9a460bdc`. **Sem merge:** o pedido parou antes do retreino.
- **Commits:**
  - `7e933a7c` Pedido 44, Parte A: ADRs 0025 (corredor pela borda da superficie e corridor_id) e 0026 (regua do retreino da LSTM geradora), antes de rodar
  - `d772253b` Pedido 44, Partes B e C: corredor pela borda da superficie, corridor_id, conferencias, criterio da F1 e outside_corridor_fraction
  - `c9dc90b0` Pedido 44, Parte D: voltas das fontes, regua do ADR 0026 em codigo, entrada da F1 so pela posicao, testes e a estimativa de tempo
  - o commit deste relatório: "Relatorio do pedido 44 ate a parada da Parte D.5 (tempo acima de 6 horas)"
- **Arquivos de handoff:**
  - `docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_relatorio.md` (este)
  - `docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_corredor_figura.png` (os 8 trechos do pedido 27, com as bordas novas)
  - `docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_corredor_resumo.json` (Partes B e C)
  - `docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_fontes.json` (as voltas, por fonte e por sessão, com os hashes dos dados)
  - `docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_estimativa.json` (as medidas de tempo)
  - `docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_testes.txt` (suíte `backend/tests`)

## Em resumo

1. **Partes A, B e C prontas; Parte D pronta até a estimativa.** O retreino (Parte E) e a documentação (Parte F) não começaram.
2. **Parei pela regra da Parte D.5:** o treino completo leva de 8 a 14 horas, e o limite é 6. A proposta está na seção "O que precisa de decisão".
3. **O corredor novo faz o que o pedido 27 previu:** contra o sinal do jogo, 6.764 e 411, os mesmos números. O `geometry_id` não mudou, e o `s` e o `lateral` ficaram iguais ponto a ponto.
4. **Coach, rádio, app, store v2, Modelo 2 e M1 não mudaram de comportamento,** então não houve a parada da Parte B.1. A suíte passou: 899 testes.
5. **Um achado que vale olhar antes de rodar:** a regra da opção 3 abre trechos de até 28,2 m de largura, e parte deles passa sobre o que o cache marca como buraco no asfalto (Parte B.3).
6. **Nada foi enviado ao GitHub.** O controle de permissões desta sessão recusou o envio. Os três commits estão só na pasta local.

Nenhum número da régua foi visto: nenhuma rodada real rodou, e os treinos curtos de medida só imprimiram o tempo, com os erros descartados sem leitura. O modelo em `data/ml/models/` ainda é o de agosto.

## Parte A: os ADRs

Registrados no commit `7e933a7c`, antes de qualquer outra parte, com a linha de cada um no índice e a atualização no ADR 0002.

- **`docs/decisoes/0025-corredor-pela-borda-da-superficie.md`**
- **`docs/decisoes/0026-retreino-da-lstm-geradora.md`**

O ADR 0026 traz o texto do pedido e fixa o que o pedido deixava aberto, tudo antes de rodar:

| ponto | o que ficou fixado |
|---|---|
| sessão | a de `group_sessions`, a mesma da evolução e do Modelo 2: pausa de mais de 3 h |
| erro de uma volta | média de \|previsto − real\| na grade; volta inteira, com o aquecimento de `generate`; saída crua da rede |
| erro agregado | cada volta de teste pesa igual |
| IC 95% | 10.000 reamostragens das sessões, semente 44 |
| parada | a sessão seguinte sem voltas `ia`, em ordem cronológica e fechando o ciclo, até somar 15% das voltas de treino |
| F1, alvo e condicionamento | só a lateral, com os outros canais fora da perda; perda 0; contexto médio do treino da rodada |
| F1, microssetores pouco confiáveis | a lateral dela fica ausente em MS04 a MS09, MS19 e MS46 a MS48 |
| F1, peso | a linha repetida até pesar uma sessão típica (a mediana de voltas por sessão de treino) |
| F1, o que ela não toca | normalização, perdas de condicionamento, validação de parada e referência ingênua |
| modelo final | treina pela mediana da melhor época das rodadas; se a régua reprovar, é salvo marcado como reprovado |

## Parte B: o corredor novo

### B.1: quem lê as larguras

O desenho que evita mudar o resto: `load_geometry` continua igual e devolve as larguras de antes. O Modelo 1 passa a usar `load_corridor_geometry`, que devolve a mesma grade com as larguras novas.

| quem lê | onde | o que mudou |
|---|---|---|
| geradora: `track_width` e o corte da linha | `features/engineering.py`, `models/reference_line.py` | passa a receber o corredor novo; o modelo salvo recusa outro `corridor_id` |
| substituta: distâncias até as bordas | `features/engineering.py`, `optimization/surrogate.py` | corredor novo |
| evolutivo: corte, limites dos genes, penalidade | `optimization/representation.py`, `seed.py`, `fitness.py`, `validation/search.py` | corredor novo quando rodar; o código não mudou, ele recebe a pista |
| critério da F1 | `external/f1_line.py`, `f1_band.py`, `scripts/alinhar_fastf1.py`, `faixa_f1_secas.py`, `referencia_f1.py` | corredor novo, e a saída registra o `corridor_id` |
| scripts do Modelo 1 | `train_models.py`, `optimize_line.py`, `run_pipeline.py`, `compare_lap.py`, `plot_comparison.py`, `validate.py` | corredor novo; os que gravam resultado registram o `corridor_id` |
| `outside_corridor_fraction` | `preprocessing/quality.py`, chamado pelo inventário, pelo store e pelo Modelo 2 | **nada:** eles passam a pista de `load_geometry`, e o inventário fica como está. O valor novo foi calculado à parte (Parte C) |
| Modelo 2 e M1 | `modelo2/dados.py`, `modelo_carro/dados.py` | **nada:** nenhum dos dois lê as larguras; o Modelo 2 usa o `evaluate_lap` só pelo portão, que não olha o corredor |
| rádio: rótulos do minimapa | `core/radio/minimapa.py` | **nada:** larguras de antes |
| app e tela Volta | `core/leitura/arquivos.py` (`larguraEsquerdaM` e `larguraDireitaM`) | **nada:** larguras de antes |
| mapa do app | `routers/legacy.py` e o front, pelo `boundsLeft` e `boundsRight` do cache | **nada** |
| coach | só confere o `geometry_id` | **nada** |
| `service.py` e `export_coaching.py` | usam o `optimised_lateral.npy` | **nada:** continuam em `load_geometry` |

Duas consequências:

- **O ML e o app passam a ver corredores diferentes.** O minimapa e a tela Volta seguem com as larguras de antes. É o que o pedido manda, mas fica registrado.
- **A próxima rodada do `atualizar_coach` lê tudo de novo, uma vez.** `ml/track/geometry.py` entra na chave do cache de sessão, e foi nele que o pedido pôs o `corridor_id`. O resultado não muda, só o tempo: cerca de 25 min, pela medida do pedido 27.

### B.3: as conferências

| conferência | resultado |
|---|---|
| `geometry_id` | continua `0ed16f0dd2225990` |
| `corridor_id` | de antes `2a6912207d9cbc87`; **novo `56f5356b141982c2`** |
| linha central, normais, curvatura e `s` da grade | iguais, comparados byte a byte |
| `s` e `lateral` de uma sessão | iguais ponto a ponto em `2026-10-10_09-57-09`: 21 voltas e 141.884 amostras. Contra o store, a maior diferença é 0,0 m |
| coach | fala: a geometria exportada e o modelo estão em `0ed16f0dd2225990`, e os dois arquivos não foram tocados |
| pontos que ficaram com a borda de antes | 1 à esquerda, 0 à direita, como no pedido 27 |

**Contra o sinal do jogo:**

| voltas | corredor | estreito demais | largo demais |
|---|---|---|---|
| as 58 do pedido 27 | de antes | 15.338 | 548 |
| as 58 do pedido 27 | **novo** | **6.764** | **411** |
| as 150 do treino | de antes | 40.732 | 1.333 |
| as 150 do treino | novo | 12.814 | 1.236 |

Os 6.764 e 411 se repetem exatamente, sem nada a explicar.

**As larguras:**

| lado | corredor | mediana | p10 | p90 | mínimo | máximo |
|---|---|---|---|---|---|---|
| esquerda | de antes | 6,91 m | 4,94 m | 8,88 m | 1,85 m | 11,60 m |
| esquerda | novo | 8,60 m | 5,40 m | 11,10 m | 4,60 m | **28,20 m** |
| direita | de antes | 7,33 m | 5,28 m | 9,98 m | 2,86 m | 12,66 m |
| direita | novo | 7,55 m | 5,45 m | 10,80 m | 3,05 m | **25,55 m** |

**Os degraus:**

| | de antes, esquerda | novo, esquerda | de antes, direita | novo, direita |
|---|---|---|---|---|
| acima de 0,3 m | 85 | 163 | 107 | 88 |
| acima de 1 m | 0 | 43 | 1 | 38 |
| acima de 3 m | 0 | 7 | 0 | 10 |
| maior | 0,65 m | 20,20 m (3.560 m) | 1,64 m | 19,95 m (2.784 m) |
| no fechamento do laço | 0,08 m | 0,00 m | 1,64 m | 0,00 m |

- **O degrau de 1,64 m no fechamento do laço some do corredor novo,** mas continua nas larguras de antes, que o app ainda lê. Ele vem do cache: a largura direita é 7,36 m no primeiro vértice e 9,01 m no último, 1,65 m de diferença antes do reamostrador.
- **Os degraus de até 0,81 m também somem naquele ponto,** porque eram das larguras de antes (o maior, em 290 m à direita).
- **O corredor novo tem degraus bem maiores, e de outra origem.** O raio segue até o fim da superfície, e, onde há asfalto ligado à pista (acessos, áreas de escape, entradas de box), a largura salta. O pedido 27 não mostrava isso porque comparava contagens, e não a forma da borda.

**O achado:** a regra abre trechos muito largos, e parte deles não é pista de verdade.

| lado | pontos acima de 15 m | onde (máximo) |
|---|---|---|
| esquerda | 48 | 436–472 m (16,7 m), 3.476–3.484 m (28,2 m), 3.516–3.526 m (16,0 m), 3.562–3.596 m (28,1 m) |
| direita | 103 | 178–192 m (17,1 m), 732–826 m (18,1 m), 2.620–2.626 m (18,1 m), 2.786–2.790 m (25,6 m), 3.094–3.172 m (20,0 m) |

- Em 41 pontos à direita, mais de 0,5 m do raio passa por um anel `internal_hole` do cache, sem zebra nem pintura. O pior é 3.094–3.172 m, com até 11,4 m. À esquerda são 22 pontos, com até 3,3 m (em 3.512–3.528 m).
- Na figura, é o quadro de s = 3.056 a 3.166 m: a borda laranja sai da zebra e atravessa o que está pintado de grama.
- A causa provável é a leitura par-ímpar, herdada do pedido 27: um buraco que não está dentro de um anel externo conta como superfície. **Não confirmei isso anel por anel.**
- **Não mudei a regra.** Ela é a que o ADR 0025 registra, e foi com ela que saíram os 6.764 e 411.
- **O efeito hoje é pequeno, e o risco é para depois.** O retreino vê isso só no atributo `track_width` e no corte da linha. A próxima busca evolutiva poderia usar esses trechos, porque o corredor é o limite dela. Convém corrigir antes da busca.

A figura está em `docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_corredor_figura.png`.

### B.4: o que foi guardado antes

Em `data/ml/_backup_pre_pedido44/`, com `SHA256SUMS.txt`: `models/` (geradora, substituta e `metrics.json`), `optimization/` (`optimised_lateral.npy`, `optimised_speed_mps.npy` e `result.json`) e `corredor/` (as saídas do pedido 27).

## Parte C: o que depende do corredor

**C.1: o critério da F1 não muda nenhum veredito.**

- **Voltas da faixa:** 80 escolhidas; **0 mudam de aceita para recusada e 0 de recusada para aceita.** As 64 aceitas foram recalculadas. As 16 recusadas caíram por cobertura ou por buraco de amostragem, que não dependem do corredor, então não têm como virar aceitas.
- **A referência 2023–25** não muda de voltas, e por isso não foi regravada.

| | corredor | pontos fora | fração fora | p95 | máximo | veredito |
|---|---|---|---|---|---|---|
| alinhamento do pedido 22 | de antes | 44 | 2,03% | 0 m | 2,26 m | aceito |
| alinhamento do pedido 22 | novo | 8 | 0,37% | 0 m | 0,40 m | aceito |
| referência 2023–25 | de antes | 41 | 1,89% | 0 m | 2,06 m | — |
| referência 2023–25 | novo | 4 | 0,18% | 0 m | 0,18 m | — |

**C.2: `outside_corridor_fraction` nas 150 voltas do treino.**

| | mediana antes | mediana depois | média antes | média depois |
|---|---|---|---|---|
| todas | 5,14% | 1,59% | 5,45% | 1,92% |
| `humano` (136) | 5,19% | 1,69% | — | — |
| `ia` (14) | 3,43% | 1,54% | — | — |

O valor por volta está no resumo. A coluna do inventário segue com o corredor de antes, porque o inventário não muda.

**C.3: o evolutivo não rodou.** O `optimised_lateral.npy` de 24/08 ficou como está, e `data/ml/optimization/PROVENIENCIA_pedido44.json` o marca como de outra geometria.

## Parte D: os dados do retreino

**D.1 e D.2: 150 voltas em 15 sessões.** São 136 `humano` do equipamento atual e 14 `ia` rotuladas. Os rótulos vêm do indicador (94), da anotação de sessão (55) e da anotação (1), nenhum do detector. As voltas de origem `desconhecida` ficaram fora. A terceira fonte é a linha da F1, que entra no treino e não é volta de teste.

| sessão | `humano` | `ia` | `fora_do_store` | melhor | mediana |
|---|---|---|---|---|---|
| 2026-10-04 | 11 | 13 | 0 | 1:24,829 | 1:25,185 |
| 2026-10-05 | 7 | 0 | 0 | 1:30,218 | 1:31,396 |
| 2026-10-05-2 | 10 | 0 | 0 | 1:30,629 | 1:32,596 |
| 2026-10-09 | 4 | 0 | 0 | 1:30,614 | 1:32,849 |
| 2026-10-10 | 11 | 0 | 0 | 1:30,313 | 1:32,206 |
| 2026-10-11 | 16 | 0 | 0 | 1:27,594 | 1:29,547 |
| 2026-10-13 | 7 | 0 | 0 | 1:29,768 | 1:30,365 |
| 2026-10-16 | 11 | 0 | 0 | 1:27,014 | 1:30,861 |
| 2026-10-17 | 11 | 0 | 0 | 1:27,619 | 1:31,200 |
| 2026-10-17-2 | 15 | 0 | 0 | 1:28,132 | 1:31,750 |
| 2026-10-18 | 9 | 0 | 0 | 1:29,061 | 1:30,271 |
| 2026-10-21 | 9 | 0 | 0 | 1:26,876 | 1:29,520 |
| 2026-10-22 | 0 | 1 | 1 | 1:29,106 | 1:29,106 |
| 2026-10-24 | 9 | 0 | 9 | 1:26,568 | 1:28,841 |
| 2026-11-01 | 6 | 0 | 6 | 1:29,433 | 1:31,635 |

- **Fora do store:** 16 voltas de 4 gravações, lidas com as funções do store, sem gravar nele. Entrou a de 01/11, que é posterior ao pedido 38.
- **IA em níveis:** `docs/experimentos/ia_niveis.csv` ainda não existe. A única volta `ia` recente é a de 22/10, com 1:29,106.
- **Uma limitação que a régua vai mostrar:** 13 das 14 voltas `ia` estão na sessão de 04/10. Quando ela sai para teste, o treino fica com uma só volta da IA.

**D.3: nenhuma sessão depende do `off_track = False` do leitor.** Nas 18 gravações, nenhuma amostra tem o bloco `environment` sem o campo `offTrack`. Nada precisou ser tratado como desconhecido.

**D.4: a F1 está registrada no ADR 0026** (tabela da Parte A), e o código só lê as colunas `lateral` e `pouco_confiavel`. O erro de alinhamento registrado: ICP de 3,28 m até a linha central, escala de 0,0998 m por unidade, comprimento 2,54% menor, e o excesso sobre o corredor novo da tabela C.1.

**D.5: a estimativa de tempo.** Medi treinos reais de 3 épocas, com a F1, rodando vários processos juntos (na primeira rodada medida: 14.280 janelas de treino, 2.856 de validação e 1.170 da F1).

| arranjo | segundos por época em cada processo | segundos por época equivalente |
|---|---|---|
| **8 processos, 1 thread** | 131,9 | **16,5** |
| 4 processos, 2 threads | 77,4 | 19,4 |
| 2 processos, 4 threads | 48,0 | 24,0 |

Faltam 45 rodadas (15 sem a F1, 15 com a F1 e 15 da substituta) e os 2 modelos finais. Quantas épocas cada rodada leva só se sabe rodando. A referência é o treino de agosto: 80 épocas na geradora e 26 na substituta, com menos dados.

| épocas por rodada da geradora | 30 rodadas | substituta (26 épocas) | modelos finais | **total** |
|---|---|---|---|---|
| 40 | 5,5 h | 1,8 h | 0,6 h | **7,9 h** |
| 60 | 8,3 h | 1,8 h | 0,8 h | **10,9 h** |
| 80 | 11,0 h | 1,8 h | 1,1 h | **13,9 h** |

Para ficar abaixo de 6 h, cada rodada da geradora teria de parar em cerca de 27 épocas. Com paciência de 10, isso é improvável. **Por isso parei, como a Parte D.5 manda.**

## Testes

- **`backend/tests/test_corredor_e_retreino.py`:** 27 testes sintéticos, que cobrem:
  - as bordas novas e a borda de hoje onde a nova falta;
  - o caso pedido: mudar `CAR_HALF_WIDTH_M` muda o `corridor_id` e não muda o `geometry_id`;
  - a divisão por sessão sem vazamento;
  - a entrada da F1 sem velocidade nem pedal, inclusive num arquivo que traga esses canais;
  - a perda que ignora alvos ausentes e a F1 fora da normalização;
  - os critérios, um a um, e o bootstrap pareado;
  - o modelo que recusa outro corredor.
- **Suíte `backend/tests`:** 899 passando, em 8 min 47 s, com 37 avisos. A saída está no arquivo `_testes.txt`.
- A refatoração de `conferir_corredor.py` não mudou nada: os 15 testes dele passam, e a conferência repete os números do pedido 27.

## O que foi enviado ao GitHub

**Nada.** O único envio tentado, `git push -u origin etapa/corredor-e-retreino-lstm`, foi recusado pelo controle de permissões desta sessão antes de sair da máquina, com o motivo "Git Destructive". O envio não chegou ao GitHub. Não tentei de outro jeito.

| ref | hash local | hash no remoto |
|---|---|---|
| `etapa/corredor-e-retreino-lstm` | `c9dc90b0`, mais o commit deste relatório | não existe |

As conferências de antes do envio estão feitas nos commits desta branch: nenhum arquivo acima de 50 MB, nenhum segredo e nada de `recordings/`, `data/recordings` ou `data/ml`.

## O que precisa de decisão

1. **O tempo do retreino.** Os critérios não mudam em nenhuma das duas opções.
   - **Reduzir (minha proposta, porque respeita o seu limite):** passo da janela de 16 para 32 e teto de 60 épocas, em vez de 200.
     - Teto de cerca de 5,4 h para as rodadas da geradora, a substituta e os modelos finais, contando que a substituta pare perto das 26 épocas de agosto. Esse custo vem das medidas acima, dividindo por dois. Não medi com o passo 32.
     - Cada ponto ainda aparece em 4 janelas, em vez de 8.
     - **O custo:** se o teto parar uma rodada antes da paciência, um resultado ruim fica menos conclusivo. O relatório diria quantas rodadas pararam no teto.
     - Isso muda "o treino de hoje" no ADR 0026, então registro uma linha nele antes de rodar.
   - **Rodar como está:** de 8 a 14 h, com o computador ocupado. Nada do treino muda, e a rodada pode parar e continuar, porque cada sessão terminada fica gravada.
2. **O envio ao GitHub.** Ele depende de você: liberar o envio nesta sessão ou enviar pelo terminal.
3. **Os trechos largos do corredor (Parte B.3).** Sigo com a regra do ADR 0025 e deixo a correção para antes da nova busca, a não ser que você diga outra coisa. Corrigir agora muda o `corridor_id` e os 6.764 e 411, e precisaria vir antes de rodar.

## O que falta

- **Parte E:** as rodadas, a tabela dos critérios com e sem a F1, o modelo final e a substituta, as conferências da linha de referência e os resultados dela nos testes.
- **Parte F:** `docs/arquitetura_ml.md`, `backend/ml/README.md`, a nota em `docs/auditoria_ml.md` e as linhas de atualização nos ADRs 0018 e 0019.
- **O merge em `develop` e os envios.**

O código para isso já está pronto: `python -m ml.scripts.retreino_lstm todas --paralelo 8 --threads 1`, depois `regua`, `final` e `linha`.

**A pasta ficou na branch `etapa/corredor-e-retreino-lstm`.** O `docs/prompts/2026-11-02_45_replay-de-perto-e-radio-que-ensina.md` continua sem commit, como estava. As gravações só foram lidas, o `data.acd` não foi aberto, e nenhum pacote foi instalado.

`docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_relatorio.md`
