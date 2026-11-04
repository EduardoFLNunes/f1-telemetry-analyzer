# Relatório do pedido 44: corredor pela borda da superfície e retreino da LSTM geradora (parado à espera do retreino noturno)

- **Pedido:** `docs/prompts/2026-10-29_44_corredor-e-retreino-da-lstm.md`, com as decisões do Eduardo de 02/11.
- **Branch:** `etapa/corredor-e-retreino-lstm`, a partir de `develop` em `9a460bdc`. **Sem merge:** ele vem depois do retreino.
- **Commits:**
  - `7e933a7c` Pedido 44, Parte A: ADRs 0025 (corredor pela borda da superficie e corridor_id) e 0026 (regua do retreino da LSTM geradora), antes de rodar
  - `d772253b` Pedido 44, Partes B e C: corredor pela borda da superficie, corridor_id, conferencias, criterio da F1 e outside_corridor_fraction
  - `c9dc90b0` Pedido 44, Parte D: voltas das fontes, regua do ADR 0026 em codigo, entrada da F1 so pela posicao, testes e a estimativa de tempo
  - `68f2b070` Relatorio do pedido 44 ate a parada da Parte D.5 (tempo acima de 6 horas)
  - `c74b1417` Relatorio do pedido 44: tres frases corrigidas contra o que foi feito
  - `fca94a96` Pedido 44: leitura dos buracos internos do asfalto (o menor anel decide), corridor_id 707d07029036abd6, retomada do modelo final e tools/retreino_lstm.ps1
  - o commit deste relatório: "Relatorio do pedido 44: buracos internos corrigidos e o retreino pronto para rodar a noite"
- **Arquivos de handoff:**
  - `docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_relatorio.md` (este)
  - `docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_corredor_figura.png` (os 8 trechos do pedido 27, com as bordas corrigidas)
  - `docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_corredor_resumo.json` (Partes B e C, gerado em `fca94a96`)
  - `docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_fontes.json` (as voltas, por fonte e por sessão, com os hashes dos dados)
  - `docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_estimativa.json` (as medidas de tempo)
  - `docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_testes.txt` (suíte `backend/tests`)

## Em resumo

1. **Pronto para você rodar à noite.** As decisões de 02/11 estão feitas e commitadas. O comando está logo abaixo.
2. **A causa dos trechos largos foi confirmada anel por anel, em duas formas:** um `internal_hole` fora de qualquer anel externo, ou um `internal_hole` dentro de outro buraco. Os dois davam contagem ímpar e viravam superfície. Agora o menor anel que contém o ponto decide.
3. **O `corridor_id` passou a `707d07029036abd6`,** e o `geometry_id` continua `0ed16f0dd2225990`. Contra o sinal do jogo, os 6.764 e 411 passam a **6.802 e 257**.
4. **Nenhum veredito da F1 mudou** na C.1, então não houve parada.
5. **Nenhum critério nem configuração do treino mudou.** O ADR 0026 é o mesmo de `7e933a7c`.
6. **Testei a cadeia inteira antes de deixar para você,** numa pasta temporária: `regua`, `final` e `linha` nunca tinham rodado com dados reais. A suíte passa com 905 testes.

## Para rodar o retreino

**O comando.** Abra uma janela do PowerShell fora desta sessão:

```powershell
cd C:\Users\Dokas\Desktop\f1-telemetry-analyzer
powershell -NoProfile -ExecutionPolicy Bypass -File tools\retreino_lstm.ps1
```

Ele roda em sequência `todas --paralelo 8 --threads 1`, `regua`, `final --threads 8` e `linha`, e grava o log em `logs\retreino_lstm_AAAA-MM-DD_HH-mm-ss.log`.

**Quanto esperar: de 8 a 14 horas.** A conta está na Parte D.5. As primeiras rodadas só terminam depois de 1 h 30 a 3 h, porque as 8 primeiras começam juntas. Até lá, a janela fica sem linha nova, e isso é normal.

**Como conferir se terminou:**

```powershell
Get-Content (Get-ChildItem logs\retreino_lstm_*.log | Sort-Object LastWriteTime | Select-Object -Last 1) -Tail 5
```

- A última linha diz `RETREINO CONCLUIDO.` ou `RETREINO PARADO.`
- Para ver o andamento, conte as rodadas prontas. O total é 45:

```powershell
(Get-ChildItem data\ml\retreino_lstm\rodadas -Recurse -Filter *.json).Count
```

**O que você não pode fazer enquanto ele roda:**

- **Desligar, reiniciar, suspender ou hibernar o computador, nem fechar a janela.** O script pede ao Windows para não suspender sozinho enquanto roda, sem mudar nenhuma configuração de energia. Ele não segura uma reinicialização do Windows Update nem a tampa fechada de um notebook.
- **Trocar de branch, dar `pull` ou `merge`, ou editar `backend/`.** Cada rodada nova lê o código de novo. Isso vale também para outra sessão de implementação nesta pasta (ADR 0008), então o pedido 45 espera.
- **Subir o backend de desenvolvimento com a raiz no repositório.** Ele regrava `data/cache/tracks`, de onde saem as larguras, e o `corridor_id` pode mudar no meio.
- **Rodar `atualizar_coach` ou qualquer coisa que regrave `data/ml`, e apagar `data/ml/retreino_lstm`.**
- **Jogar.** Os 8 núcleos ficam ocupados: o jogo engasga, a gravação sai ruim e o treino atrasa. Navegador e tarefas leves podem.

**Se parar no meio:** rode o mesmo comando de novo.

- As rodadas e os modelos finais já terminados ficam. Só o que estava em andamento recomeça do zero.
- Se uma rodada falhar, o script para tudo e diz no log. O log de cada rodada fica em `data\ml\retreino_lstm\logs\`.
- Se a janela for fechada, os processos podem continuar vivos, e o script se recusa a rodar junto com eles. Para encerrá-los:

```powershell
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -like '*ml.scripts.retreino_lstm*' } | ForEach-Object { Stop-Process -Id $_.ProcessId }
```

Quando terminar, é só avisar "terminou o retreino". Eu leio o log e faço a Parte E, a Parte F, o merge e os envios.

## Para enviar ao GitHub

O controle de permissões desta sessão recusa o envio, então nada foi enviado. Pelo terminal:

```powershell
cd C:\Users\Dokas\Desktop\f1-telemetry-analyzer
git push -u origin etapa/corredor-e-retreino-lstm
git rev-parse HEAD
git ls-remote origin refs/heads/etapa/corredor-e-retreino-lstm
```

Os dois hashes têm de ser iguais. Quando você avisar, eu confiro também. Pode enviar com o retreino rodando: o envio não troca a branch nem mexe no código.

| ref | hash local | hash no remoto |
|---|---|---|
| `etapa/corredor-e-retreino-lstm` | o do commit deste relatório (`git rev-parse HEAD`) | ainda não existe |

**Conferido antes do envio, de `9a460bdc` até aqui:** nenhum arquivo acima de 50 MB, nenhum segredo e nada de `recordings/`, `data/recordings` ou `data/ml`. Os modelos ficam em `data/ml`, fora do git, e `logs/` também está fora.

## Parte A: os ADRs

- **`docs/decisoes/0025-corredor-pela-borda-da-superficie.md`:** registrado em `7e933a7c`, com a linha de atualização de 04/11 (`fca94a96`) sobre os buracos e o `corridor_id` novo.
- **`docs/decisoes/0026-retreino-da-lstm-geradora.md`:** registrado em `7e933a7c`, e não mudou desde então.
- **O ADR 0002** ganhou a linha de atualização, e o índice tem as linhas dos dois.

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

`load_geometry` continua igual e devolve as larguras de antes. O Modelo 1 passa a usar `load_corridor_geometry`, que devolve a mesma grade com as larguras novas.

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

### Os buracos internos: a causa, anel por anel

O asfalto do cache tem 60 anéis: 14 `external` e 46 `internal_hole`. Comparei, a cada 0,05 m de cada raio até a borda de antes, a contagem par-ímpar com a classificação dos anéis:

| caso | amostras em que a leitura muda |
|---|---|
| buraco fora de qualquer anel externo (1 anel: conta como dentro) | 12.149 |
| buraco dentro de outro buraco, dentro de um anel externo (3 anéis: conta como dentro) | 5.194 |
| anéis externos sobrepostos | 0 |
| outros | 0 |

- **O que muda a sua descrição:** o pior caso não é um buraco *dentro* do asfalto. É um buraco que fica *fora* dele. O anel 3 tem 0% dos vértices em anel externo, embora o cache o marque como `internal_hole` do componente 0. Dos 46 buracos, 19 têm vértices fora de anel externo. A conclusão é a mesma: não é superfície.
- **Por que não usei "qualquer buraco tira":** há anéis externos dentro de buracos (por exemplo, os anéis 45, 49 e 53 dentro do anel 1). Por isso, o menor anel que contém o ponto decide.
- **Nenhum caso caiu fora dessas duas formas,** então a correção não mexe em mais nada.

Os anéis que mais pesam, de 29 (a tabela inteira está em `parte_b.aneis.por_anel` do resumo):

| anel | área | vértices em anel externo | amostras | lado | trecho |
|---|---|---|---|---|---|
| 3 | 3.194 m² | 0% | 8.699 | direita | 3.094 a 3.172 m |
| 15 | 195 m² | 100% (85% em buraco maior) | 1.639 | esquerda | 2.802 a 3.488 m |
| 7 | 1.217 m² | 100% (82% em buraco maior) | 626 | esquerda | 468 a 766 m |
| 27 | 81 m² | 3% | 619 | direita | 2.346 a 2.626 m |
| 28 | 67 m² | 100% (94% em buraco maior) | 522 | esquerda | 2.358 a 2.616 m |
| 21 | 108 m² | 7% | 494 | direita | 2.786 a 3.032 m |

**A mudança é pequena na maioria dos pontos.** São faixas finas junto à borda, e os trechos grandes são poucos.

| lado | pontos que mudam | mediana | p90 | acima de 0,5 m | acima de 1 m | acima de 3 m | maior |
|---|---|---|---|---|---|---|---|
| esquerda | 1.092 | 0,25 m | 0,40 m | 20 | 12 | 9 | 8,30 m |
| direita | 752 | 0,25 m | 0,40 m | 44 | 41 | 40 | 11,45 m |

Todos estreitam: nenhum ponto ficou mais largo. A linha central continua 100% sobre a superfície.

A zebra e a pintura seguem na leitura par-ímpar: não têm classificação de anel, e o pedido é sobre o asfalto. Não conferi se têm defeito parecido.

### B.3: as conferências, refeitas

| conferência | resultado |
|---|---|
| `geometry_id` | continua `0ed16f0dd2225990` |
| `corridor_id` | de antes `2a6912207d9cbc87`; com a par-ímpar `56f5356b141982c2`; **agora `707d07029036abd6`** |
| linha central, normais, curvatura e `s` da grade | iguais, comparados byte a byte |
| `s` e `lateral` de uma sessão | iguais ponto a ponto em `2026-10-10_09-57-09`: 21 voltas e 141.884 amostras. Contra o store, a maior diferença é 0,0 m |
| coach | fala: a geometria exportada e o modelo estão em `0ed16f0dd2225990`, e os dois arquivos não foram tocados |
| pontos que ficaram com a borda de antes | 1 à esquerda, 0 à direita |

**Contra o sinal do jogo.** A linha da par-ímpar foi medida de novo na mesma rodada e repete os 6.764 e 411 do pedido 27. É o controle de que só a leitura mudou.

| voltas | corredor | estreito demais | largo demais |
|---|---|---|---|
| as 58 do pedido 27 | de antes | 15.338 | 548 |
| as 58 do pedido 27 | par-ímpar | 6.764 | 411 |
| as 58 do pedido 27 | **corrigido** | **6.802** | **257** |
| as 150 do treino | de antes | 40.732 | 1.333 |
| as 150 do treino | par-ímpar | 12.814 | 1.236 |
| as 150 do treino | corrigido | 12.912 | 821 |

A correção melhora o resultado: o "largo demais" cai 37% nas 58 voltas, e o "estreito demais" sobe 0,6%.

**As larguras:**

| lado | corredor | mediana | p10 | p90 | mínimo | máximo |
|---|---|---|---|---|---|---|
| esquerda | de antes | 6,91 m | 4,94 m | 8,88 m | 1,85 m | 11,60 m |
| esquerda | corrigido | 8,50 m | 5,35 m | 11,05 m | 4,40 m | 28,20 m |
| direita | de antes | 7,33 m | 5,28 m | 9,98 m | 2,86 m | 12,66 m |
| direita | corrigido | 7,40 m | 5,45 m | 10,65 m | 2,80 m | 23,85 m |

**Os degraus:**

| | esquerda: de antes | par-ímpar | corrigido | direita: de antes | par-ímpar | corrigido |
|---|---|---|---|---|---|---|
| acima de 0,3 m | 85 | 163 | 131 | 107 | 88 | 70 |
| acima de 1 m | 0 | 43 | 41 | 1 | 38 | 36 |
| acima de 3 m | 0 | 7 | 9 | 0 | 10 | 9 |
| maior | 0,65 m | 20,20 m | 20,20 m (3.560 m) | 1,64 m | 19,95 m | 18,25 m (2.784 m) |
| no fechamento do laço | 0,08 m | 0,00 m | 0,00 m | 1,64 m | 0,00 m | 0,00 m |

- **O degrau de 1,64 m no fechamento do laço some do corredor novo,** mas continua nas larguras de antes, que o app ainda lê. Ele vem do cache: a largura direita é 7,36 m no primeiro vértice e 9,01 m no último, 1,65 m de diferença antes do reamostrador.
- **Os degraus de até 0,81 m também somem naquele ponto,** porque eram das larguras de antes (o maior, em 290 m à direita).
- **Os degraus grandes que ficam são acessos e áreas de escape** ligados à pista, onde a largura salta. É o que você decidiu manter.

**Os pontos acima de 15 m:** caem de 151 para 104.

| lado | par-ímpar | corrigido | onde ficam (máximo) |
|---|---|---|---|
| esquerda | 48 | 41 | 436–470 m (16,65 m), 3.476–3.484 m (28,20 m), 3.562–3.596 m (28,10 m) |
| direita | 103 | 63 | 178–192 m (17,10 m), 732–826 m (18,05 m), 2.620–2.626 m (17,60 m), 2.786–2.790 m (23,85 m) |

- **Saíram por completo:** 3.094–3.172 m à direita (o anel 3, com 19,95 m) e 3.516–3.526 m à esquerda.
- **Na figura,** o quadro de s = 3.056 a 3.166 m não atravessa mais a grama: a borda agora acompanha a zebra.

A figura está em `docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_corredor_figura.png`.

### B.4: o que foi guardado antes

Em `data/ml/_backup_pre_pedido44/`, com `SHA256SUMS.txt`: `models/` (geradora, substituta e `metrics.json`), `optimization/` (`optimised_lateral.npy`, `optimised_speed_mps.npy` e `result.json`) e `corredor/` (as saídas do pedido 27). As saídas da leitura par-ímpar ficam em `data/ml/corredor/novo_antes_dos_buracos/`.

## Parte C: o que depende do corredor

**C.1: refeita com o corredor corrigido, e nenhum veredito da F1 muda.**

- **Voltas da faixa:** 80 escolhidas; **0 mudam de aceita para recusada e 0 de recusada para aceita.** As 64 aceitas foram recalculadas. As 16 recusadas caíram por cobertura ou por buraco de amostragem, que não dependem do corredor, então não têm como virar aceitas.
- **A referência 2023–25** não muda de voltas, e por isso não foi regravada.

| | corredor | pontos fora | fração fora | p95 | máximo | veredito |
|---|---|---|---|---|---|---|
| alinhamento do pedido 22 | de antes | 44 | 2,03% | 0 m | 2,26 m | aceito |
| alinhamento do pedido 22 | corrigido | 11 | 0,51% | 0 m | 0,78 m | aceito |
| referência 2023–25 | de antes | 41 | 1,89% | 0 m | 2,06 m | — |
| referência 2023–25 | corrigido | 10 | 0,46% | 0 m | 0,51 m | — |

**C.2: `outside_corridor_fraction` nas 150 voltas do treino.**

| | mediana antes | mediana depois |
|---|---|---|
| todas | 5,14% | 1,60% |
| `humano` (136) | 5,19% | 1,69% |
| `ia` (14) | 3,43% | 1,54% |

A média vai de 5,45% para 1,99%. O valor por volta está no resumo. A coluna do inventário segue com o corredor de antes, porque o inventário não muda.

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

**D.4: a F1 está registrada no ADR 0026** (tabela da Parte A), e o código só lê as colunas `lateral` e `pouco_confiavel`. O erro de alinhamento registrado: ICP de 3,28 m até a linha central, escala de 0,0998 m por unidade, comprimento 2,54% menor, e o excesso sobre o corredor da tabela C.1.

**D.5: a estimativa de tempo.** Medi treinos reais de 3 épocas, com a F1, rodando vários processos juntos (na primeira rodada medida: 14.280 janelas de treino, 2.856 de validação e 1.170 da F1). A correção dos buracos não muda o número de janelas.

| arranjo | segundos por época em cada processo | segundos por época equivalente |
|---|---|---|
| **8 processos, 1 thread** | 131,9 | **16,5** |
| 4 processos, 2 threads | 77,4 | 19,4 |
| 2 processos, 4 threads | 48,0 | 24,0 |

São 45 rodadas (15 sem a F1, 15 com a F1 e 15 da substituta) e os 2 modelos finais. Quantas épocas cada rodada leva só se sabe rodando. A referência é o treino de agosto: 80 épocas na geradora e 26 na substituta, com menos dados.

| épocas por rodada da geradora | 30 rodadas | substituta (26 épocas) | modelos finais | **total** |
|---|---|---|---|---|
| 40 | 5,5 h | 1,8 h | 0,6 h | **7,9 h** |
| 60 | 8,3 h | 1,8 h | 0,8 h | **10,9 h** |
| 80 | 11,0 h | 1,8 h | 1,1 h | **13,9 h** |

Pela sua decisão de 02/11, o limite de 6 h fica suspenso só para este retreino, sem mudar o passo da janela nem pôr teto de épocas.

## Testes

- **`backend/tests/test_corredor_e_retreino.py`:** 33 testes sintéticos, que cobrem:
  - as bordas novas e a borda de hoje onde a nova falta;
  - os buracos: fora do anel externo, dentro de outro buraco, anel externo dentro de buraco, zebra sobre buraco e acesso ligado à pista;
  - o caso pedido: mudar `CAR_HALF_WIDTH_M` muda o `corridor_id` e não muda o `geometry_id`;
  - a divisão por sessão sem vazamento;
  - a entrada da F1 sem velocidade nem pedal, inclusive num arquivo que traga esses canais;
  - a perda que ignora alvos ausentes e a F1 fora da normalização;
  - os critérios, um a um, e o bootstrap pareado;
  - o modelo que recusa outro corredor.
- **Suíte `backend/tests`:** 905 passando, com 37 avisos, em 12 min 43 s (com a CPU dividida com as conferências). A saída está no arquivo `_testes.txt`.
- **Ensaio da cadeia inteira,** numa pasta temporária, com 4 sessões e 1 época, sem tocar em `data/ml`:
  - `todas`, com os processos paralelos; apaguei uma rodada, e só ela rodou de novo;
  - `regua`, `final` nas duas versões (com e sem a F1; na segunda vez, a substituta pronta não rodou de novo) e `linha`;
  - os modelos saem com o `corridor_id`, o commit e os hashes dos dados.
  - Os números de 1 época não significam nada. Só olhei se a estrutura saiu completa.
- **`tools/retreino_lstm.ps1`, testado com um python simulado:** a sequência completa termina em `RETREINO CONCLUIDO`; uma falha em `regua` para em `RETREINO PARADO`, com saída 1; ele se recusa a rodar com outro processo do retreino vivo e com mudança sem commit em `backend/`. Os logs desses testes foram apagados.

**O que o ensaio não cobre:** o tempo real, o comportamento em 8 a 14 h seguidas e o script completo com o python de verdade. As peças foram testadas separadamente, não juntas.

Nenhum número da régua foi visto: nenhuma rodada real rodou, e o modelo em `data/ml/models/` ainda é o de agosto.

## O que falta

Depois que você avisar "terminou o retreino":

- **Parte E:** a tabela dos critérios com e sem a F1, o veredito, as conferências da linha de referência e a substituta.
- **Parte F:** `docs/arquitetura_ml.md`, `backend/ml/README.md`, a nota em `docs/auditoria_ml.md` e as linhas de atualização nos ADRs 0018 e 0019.
- **O merge em `develop`,** com os comandos de envio para você rodar.

**Nada precisa de decisão agora.** A pasta fica na branch `etapa/corredor-e-retreino-lstm`. O `docs/prompts/2026-11-02_45_replay-de-perto-e-radio-que-ensina.md` continua sem commit, como estava. As gravações só foram lidas, o `data.acd` não foi aberto, e nenhum pacote foi instalado.

`docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_relatorio.md`
