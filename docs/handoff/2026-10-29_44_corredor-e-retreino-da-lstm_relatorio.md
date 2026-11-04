# Relatório do pedido 44: corredor pela borda da superfície e retreino da LSTM geradora

- **Pedido:** `docs/prompts/2026-10-29_44_corredor-e-retreino-da-lstm.md`, com as decisões do Eduardo de 02/11.
- **Branch:** `etapa/corredor-e-retreino-lstm`, a partir de `develop` em `9a460bdc`, **com merge em `develop`**.
- **Commits e merge:**
  - `7e933a7c` Pedido 44, Parte A: ADRs 0025 (corredor pela borda da superficie e corridor_id) e 0026 (regua do retreino da LSTM geradora), antes de rodar
  - `d772253b` Pedido 44, Partes B e C: corredor pela borda da superficie, corridor_id, conferencias, criterio da F1 e outside_corridor_fraction
  - `c9dc90b0` Pedido 44, Parte D: voltas das fontes, regua do ADR 0026 em codigo, entrada da F1 so pela posicao, testes e a estimativa de tempo
  - `68f2b070` Relatorio do pedido 44 ate a parada da Parte D.5 (tempo acima de 6 horas)
  - `c74b1417` Relatorio do pedido 44: tres frases corrigidas contra o que foi feito
  - `fca94a96` Pedido 44: leitura dos buracos internos do asfalto (o menor anel decide), corridor_id 707d07029036abd6, retomada do modelo final e tools/retreino_lstm.ps1
  - `ec06b0f1` Relatorio do pedido 44: buracos internos corrigidos e o retreino pronto para rodar a noite (o retreino rodou neste commit)
  - `2c650142` Pedido 44, Parte E: o retreino rodado (45 rodadas, modelos finais e linha de referencia): reprovado na regua, sem a F1
  - `0d710231` Pedido 44, Parte F: documentacao do corredor novo e do resultado do retreino; linhas nos ADRs 0018, 0019 e 0026
  - `5fc393d6` Pedido 44: a saida da suite com os modelos finais no lugar
  - `41efd098` Merge etapa/corredor-e-retreino-lstm (pedido 44: corredor pela borda da superficie e retreino da LSTM geradora, reprovado na regua, sem a F1)
  - o commit deste relatório, em `develop`: "Relatorio do pedido 44: o retreino, a regua, o merge e os comandos de envio"
- **Arquivos de handoff:**
  - `docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_relatorio.md` (este)
  - `docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_resultados.json` (a régua inteira, com os hashes dos dados)
  - `docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_linha_de_referencia.json` (as conferências da linha, com os 60 microssetores)
  - `docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_erros_por_volta.csv` (o erro de cada volta de teste, com e sem a F1)
  - `docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_log_do_retreino.txt` (o log da corrida de 04/11)
  - `docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_corredor_figura.png` (os 8 trechos do pedido 27, com as bordas corrigidas)
  - `docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_corredor_resumo.json` (Partes B e C, gerado em `fca94a96`)
  - `docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_fontes.json` (as voltas, por fonte e por sessão, com os hashes dos dados)
  - `docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_estimativa.json` (as medidas de tempo antes de rodar)
  - `docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_testes.txt` (suíte `backend/tests`)
  - `docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm.patch` (de `9a460bdc` até o merge; sha256 `35bb2d4b…4d4807`)

## Em resumo

1. **O retreino foi feito e reprovou na régua, nas duas versões.** O melhor skill é 0,042, contra o mínimo de 0,20. A geradora quase não prevê a lateral melhor que a lateral mediana do treino: 1,474 m contra 1,540 m. É um resultado negativo, e os ADRs 0006, 0022 e 0026 mandam aceitá-lo e registrá-lo. Nenhum critério mudou.
2. **A F1 ficou fora do modelo final.** Com ela, o skill cai para −0,003. A diferença é −0,045, com IC 95% de −0,093 a +0,001.
3. **O modelo final é o sem a F1, salvo e marcado como reprovado.** Nada o consome hoje: o coach, o rádio, o app, o store v2, o Modelo 2 e a M1 não mudaram.
4. **Uma conferência da linha de referência não passou:** antes do corte, há pontos fora do corredor útil (Parte E.4).
5. **Errei a estimativa de tempo.** Previ de 8 a 14 h, e a corrida levou **5,3 h**, dentro do limite original de 6 h. As rodadas pararam muito mais cedo do que supus (Parte D.5).
6. **Merge feito em `develop`, sem envio ao GitHub.** Os comandos estão logo abaixo, para você rodar. A branch ainda não existe no remoto.

## Para enviar ao GitHub

O controle de permissões desta sessão recusa o envio, então é com você, pelo terminal:

```powershell
cd C:\Users\Dokas\Desktop\f1-telemetry-analyzer
git push -u origin etapa/corredor-e-retreino-lstm
git push origin develop
git rev-parse etapa/corredor-e-retreino-lstm develop
git ls-remote origin refs/heads/etapa/corredor-e-retreino-lstm refs/heads/develop
```

Os hashes de cada ref têm de ser iguais nas duas últimas saídas. Quando você avisar, eu confiro também. Os dois envios são só de avanço; `main` e as tags não vão.

| ref | hash local | hash no remoto (conferido antes do envio) |
|---|---|---|
| `etapa/corredor-e-retreino-lstm` | `5fc393d6` | não existe |
| `develop` | o do commit deste relatório (`git rev-parse develop`) | `9a460bdc` |

**Conferido, de `9a460bdc` até o merge:** nenhum arquivo acima de 50 MB, nenhum segredo e nada de `recordings/`, `data/recordings` ou `data/ml`. Os modelos ficam em `data/ml`, fora do git.

## Parte E: o retreino e a régua

A corrida foi em 04/11, das 14:04 às 19:25, no commit `ec06b0f1`, com o `corridor_id` `707d07029036abd6`. As 45 rodadas terminaram sem falha nem retomada.

**Conferi por fora do código da régua:** as 45 rodadas têm o mesmo corredor e o mesmo commit; nenhuma sessão de fora entrou na validação; cada rodada soma as 150 voltas; os dados têm os mesmos hashes de agora. Um recálculo do skill e do bootstrap, com outra semente, dá os mesmos números (IC sem a F1: +0,001 a +0,088).

### E.2: a tabela dos critérios

| critério | exigido | sem a F1 | com a F1 |
|---|---|---|---|
| skill | ≥ 0,20 | **0,042: não** | **−0,003: não** |
| limite inferior do IC 95% | > 0 | +0,001: sim (IC até +0,089) | **−0,067: não** (IC até +0,066) |
| sessões com skill positivo | ≥ 70% | **66,7%, 10 de 15: não** | **66,7%, 10 de 15: não** |
| sessões testáveis | ≥ 5 | 15: sim | 15: sim |
| **veredito** | | **reprovada** | **reprovada** |

**A F1 fica?** Não. Era preciso skill maior com ela e limite inferior do IC da diferença acima de 0. A diferença é −0,045, com IC 95% de −0,093 a +0,001. Pela regra do ADR 0026, o modelo final é o sem a F1.

### Os números que o ADR manda relatar

| | sem a F1: erro / ingênua / skill | com a F1: erro / ingênua / skill |
|---|---|---|
| lateral (m) | 1,474 / 1,540 / 0,042 | 1,544 / 1,540 / −0,003 |
| velocidade (km/h) | 3,320 / 8,165 / 0,593 | 3,441 / 8,165 / 0,579 |
| freio (0–1) | 0,028 / 0,033 / 0,146 | 0,029 / 0,033 / 0,121 |
| acelerador (0–1) | 0,074 / 0,090 / 0,174 | 0,076 / 0,090 / 0,159 |
| lateral, voltas abaixo de 88 s (23 voltas) | 1,379 / 1,557 / 0,114 | 1,652 / 1,557 / −0,061 |
| lateral, voltas a partir de 88 s (127) | 1,492 / 1,536 / 0,029 | 1,524 / 1,536 / 0,008 |
| lateral, voltas do Eduardo (136) | 1,480 / 1,534 / 0,035 | 1,512 / 1,534 / 0,014 |
| lateral, voltas da IA (14) | 1,422 / 1,594 / 0,108 | 1,850 / 1,594 / −0,161 |

O skill médio por sessão é 0,035 sem a F1 e 0,021 com ela. A sessão maior é 2026-10-04, com 16% das voltas, e, sem ela, o skill fica em 0,048 e 0,030: não é ela que decide. Nenhuma volta teve lateral incompleta.

**Por sessão** (erro de lateral em metros; a referência ingênua é a mesma nas duas versões):

| sessão | voltas | ingênua | sem a F1: erro | skill | melhor época | com a F1: erro | skill | melhor época |
|---|---|---|---|---|---|---|---|---|
| 2026-10-04 | 24 | 1,612 | 1,586 | 0,016 | 10 | 1,877 | −0,165 | 6 |
| 2026-10-05 | 7 | 1,600 | 1,700 | −0,062 | 18 | 1,605 | −0,003 | 8 |
| 2026-10-05-2 | 10 | 1,488 | 1,617 | −0,086 | 15 | 1,574 | −0,058 | 9 |
| 2026-10-09 | 4 | 1,596 | 1,595 | 0,000 | 16 | 1,599 | −0,002 | 17 |
| 2026-10-10 | 11 | 1,699 | 1,663 | 0,021 | 12 | 1,686 | 0,008 | 7 |
| 2026-10-11 | 16 | 1,498 | 1,233 | 0,177 | 12 | 1,261 | 0,158 | 13 |
| 2026-10-13 | 7 | 1,494 | 1,226 | 0,179 | 7 | 1,344 | 0,101 | 5 |
| 2026-10-16 | 11 | 1,721 | 1,632 | 0,052 | 7 | 1,642 | 0,046 | 2 |
| 2026-10-17 | 11 | 1,401 | 1,443 | −0,030 | 6 | 1,359 | 0,030 | 5 |
| 2026-10-17-2 | 15 | 1,299 | 1,348 | −0,038 | 14 | 1,491 | −0,148 | 9 |
| 2026-10-18 | 9 | 1,382 | 1,312 | 0,051 | 9 | 1,373 | 0,006 | 7 |
| 2026-10-21 | 9 | 1,680 | 1,502 | 0,106 | 6 | 1,578 | 0,061 | 11 |
| 2026-10-22 | 1 | 1,326 | 1,422 | −0,072 | 12 | 1,140 | 0,140 | 11 |
| 2026-10-24 | 9 | 1,564 | 1,332 | 0,149 | 6 | 1,360 | 0,131 | 7 |
| 2026-11-01 | 6 | 1,649 | 1,544 | 0,063 | 5 | 1,620 | 0,017 | 8 |

Em 2026-10-09, o skill sem a F1 é +0,0004 e conta como positivo. Faltou uma sessão para os 70%, mas o skill está longe do mínimo de qualquer forma.

**Como eu leio isso.** O que segue é leitura, não medida de causa:

- **A velocidade sai bem, a lateral não.** A perda da volta diz o ritmo, e o ritmo explica a velocidade. Ela diz pouco sobre por onde o carro passa.
- **A referência ingênua já é boa.** As voltas passam perto umas das outras, e a mediana delas erra só 1,54 m.
- **As rodadas param cedo:** melhor época mediana de 10 sem a F1 e de 8 com ela. A validação é de outras sessões, e ela para de melhorar logo.
- **Comparar com a auditoria não vale diretamente.** Os 0,528 m e 2,898 m de agosto são de outro modelo, outra divisão e outras voltas. A distância entre os dois ritmos sumiu (1,379 m e 1,492 m), mas a rede nova também quase não ganha da mediana.
- **Com a F1, o que piora mais são as voltas rápidas e as da IA.** Isso é coerente com ensinar à rede, em perda 0, uma linha diferente da que as voltas rápidas deste carro fazem.

### E.3: os modelos finais

Treinados nas 150 voltas e salvos em `data/ml/models/`, com o `corridor_id`, o commit e os hashes dos dados no `model.json`. Os de agosto estão em `data/ml/_backup_pre_pedido44/`.

| modelo | versão | épocas | tempo | sha256 dos pesos | régua |
|---|---|---|---|---|---|
| geradora (`reference`) | sem a F1 | 10 | 345 s | `d7622dca…931bd66` | **reprovada** (`aprovado_na_regua: false`) |
| substituta (`surrogate`) | sem a F1 | 25 | 1.167 s | `dd8024fe…761d799` | sem critério |

Com a pista de `load_geometry`, `generate` recusa o modelo; testei isso com o modelo real. Com a de `load_corridor_geometry`, a linha sai finita e dentro do corredor.

**A substituta, deixando uma sessão de fora** (sem critério de aprovação, ADR 0026):

| | modelo | mediana do treino |
|---|---:|---:|
| erro por passo | 0,00177 s | 0,00257 s |
| erro por volta | 1,679 s | 2,768 s |
| viés por volta | +0,035 s | — |

O pior erro por volta é o da sessão 2026-10-04, com 2,937 s, a que tem as voltas da IA. O melhor é o da 2026-10-22, com 0,593 s, numa volta só. A tabela inteira está em `substituta.por_sessao` dos resultados.

### E.4: as conferências da linha de referência

**Nenhum ponto fora do corredor útil antes do corte: não passou.**

| etapa | pontos fora | maior excesso | onde |
|---|---:|---:|---|
| saída crua da rede | 49 | 0,52 m | 1.428–1.450 m e 1.838–1.892 m ou mais |
| depois da projeção em splines | 17 | 0,23 m | 1.432–1.444 m e 1.884–1.902 m |
| linha final, com o corte | 0 | 0 m | — |

O corte resolve, e o excesso é pequeno. Mas a rede não aprendeu esse limite por conta própria. A lista da saída crua mostra só os 40 primeiros pontos, e o resto do segundo trecho não foi listado. Isso não é critério de aprovação, e não parei por causa disso.

**A resposta com perda 0 e com perda 0,5 s:**

| | perda 0 | perda 0,5 s | na `docs/arquitetura_ml.md` (agosto) |
|---|---:|---:|---:|
| velocidade mediana | 206,9 km/h | 148,1 km/h | 199 e 134 km/h |
| quanto a linha se desloca | | mediana de 3,12 m, p90 de 9,21 m, máximo de 14,32 m | 3,4 m em média |

- **O condicionamento faz efeito,** e a rede não virou uma média.
- **As duas consultas ficam fora do real.** A mediana de velocidade de uma volta real vai de 154,5 a 201,6 km/h (IA: 200,9; Eduardo: 188,2). A perda 0 passa disso, e a de 0,5 s fica abaixo.
- **A consulta de 0,5 s é contraditória:** 0,5 s em cada um dos 60 microssetores somam 30 s, com a perda da volta pedida em 0,5 s. Por isso a queda de velocidade não é uma medida física.

**A distância até a linha nova, por microssetor (mediana de |diferença|):**

| comparada com | mediana dos 60 | maior | onde estão as maiores |
|---|---:|---:|---|
| IA do coach (`2026-10-04_03-42-10#0013`) | 0,528 m | 4,320 m | MS29, MS46, MS30 |
| minha melhor (`2026-10-21_20-30-54#0017`) | 1,355 m | 7,873 m | MS53, MS52, MS34 |
| F1 2023–25 | 1,363 m | 4,641 m | MS48, MS34, MS49 |

A linha nova fica mais perto da IA em 39 dos 60 microssetores, da melhor volta do Eduardo em 11 e da F1 em 10. **A linha de perda 0 é, na prática, a da IA.** A melhor volta do treino é da IA (1:24,829), então perda 0 tende a pedir o que a IA faz. É exatamente o que o ADR 0018 queria evitar, mesmo com só 14 voltas da IA em 150. A F1 não entrou neste modelo: a distância até ela é só comparação.

### E.5: os testes

Na seção "Testes", abaixo. A suíte passa com os modelos finais no lugar.

## O script do retreino

Rodou como planejado: `powershell -NoProfile -ExecutionPolicy Bypass -File tools\retreino_lstm.ps1`. Ele continua servindo para refazer o retreino, e retoma de onde parou. O log da corrida está em `logs\retreino_lstm_2026-11-04_14-04-22.log` e copiado no handoff.

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

Pela sua decisão de 02/11, o limite de 6 h ficou suspenso só para este retreino, sem mudar o passo da janela nem pôr teto de épocas.

**O que aconteceu de verdade: 5,3 h.** As rodadas da geradora levaram de 12 a 28 épocas (mediana de 20 sem a F1 e de 18 com ela), e as da substituta, de 23 a 59 (mediana de 35). Minha conta supunha de 40 a 80 épocas na geradora, a partir do treino de agosto, e eu disse que parar em até 27 épocas era improvável. **Errei:** a maioria parou antes disso, e a corrida coube no limite original. A substituta foi a parte mais cara. A parada que propus não era necessária, embora só rodando desse para saber.

## Parte F: a documentação

- **ADRs:** linhas de atualização no 0002 (Parte A), no 0025 (os buracos), no 0018 e no 0019; seção "Resultado" no 0026; a linha dele no índice.
- **`docs/arquitetura_ml.md`:** o corredor novo, as fontes da geradora, a peça A na tabela e uma nota na Figura 4, sem apagar os números de agosto.
- **`backend/ml/README.md`:** os resultados medidos e as limitações.
- **`docs/auditoria_ml.md`:** uma nota na seção 3 apontando para o resultado novo, sem apagar o antigo.

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
- **Suíte `backend/tests`:** 905 passando, com 37 avisos, em 12 min 55 s, com os modelos finais no lugar. A saída está no arquivo `_testes.txt`.
- **Ensaio da cadeia inteira, antes de rodar:** numa pasta temporária, com 4 sessões e 1 época, incluindo a retomada. Os números de 1 época não significam nada, e só olhei se a estrutura saiu completa.
- **`tools/retreino_lstm.ps1`:** testado com um python simulado em sucesso, falha, processo duplicado e mudança sem commit, e depois na corrida real de 04/11.

## O que não mudou

- **Coach:** `vhe_interlagos.json` e `vhe_interlagos.geometry.json` têm os mesmos hashes (`df5a763f…` e `811da4c9…`).
- **Store v2 e inventário:** continuam com as datas de antes (22/10 e 30/09), e o hash do store é o que os modelos registram.
- **Cache da pista:** o hash não mudou (`44ae485c…`), e o `geometry_id` continua `0ed16f0dd2225990`.
- **Rádio, app, Modelo 2 e M1:** nenhum arquivo deles foi tocado. Fora de `backend/ml/` e `docs/`, o merge só traz `backend/core/geometry/surface_edge.py`, o teste novo e o script.
- **Gravações:** só foram lidas. O `data.acd` não foi aberto, e nenhum pacote foi instalado.

**Uma consequência que continua valendo:** a próxima rodada do `atualizar_coach` lê tudo de novo uma vez, cerca de 25 min, porque `ml/track/geometry.py` entra na chave do cache de sessão. O resultado não muda.

## Para decidir e para o backlog

Nada aqui trava o pedido. O backlog é mantido pelo Cowork, então não o editei. Estes são os itens para ele:

1. **A linha "Retreinar a LSTM geradora":** feito no pedido 44, reprovado, sem a F1.
2. **O que fazer com a reprovação:** o que os números apontam é que a perda da volta não diz por onde o carro passa, e que perda 0 pede a linha da IA. Mudar isso é outro experimento, com outro ADR antes de rodar.
3. **Antes da nova busca evolutiva:**
   - decidir se a semente usa esta geradora: `optimize_line.py` a usa se o modelo existir, salvo com `--no-lstm`, e ela agora está reprovada;
   - rever o corredor nos acessos e áreas de escape: 104 pontos acima de 15 m, até 28,2 m. Hoje isso quase não pesa, mas o corredor é o limite da busca.
4. **Zebra e pintura:** seguem na leitura par-ímpar, e não conferi se têm defeito parecido com o dos buracos.
5. **ML e app com corredores diferentes:** o minimapa e a tela Volta seguem com as larguras de antes, incluindo o degrau de 1,64 m no fechamento do laço.
6. **Voltas da IA:** 13 das 14 estão em 04/10. Sessões novas da IA melhorariam o teste por fonte.

## O que falta

Só o envio ao GitHub, pelos comandos do começo deste relatório, e a conferência dos hashes quando você avisar. A pasta está em `develop`, e o pedido 45 continua sem commit, como estava.

`docs/handoff/2026-10-29_44_corredor-e-retreino-da-lstm_relatorio.md`
