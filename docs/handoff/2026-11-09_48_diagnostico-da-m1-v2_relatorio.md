# Relatório do pedido 48: diagnóstico da M1 v2 (só análise)

- **Pedido:** `docs/prompts/2026-11-09_48_diagnostico-da-m1-v2.md`.
- **Pasta:** `C:\Users\Dokas\Desktop\f1-telemetry-analyzer-48` (pasta separada, por `git worktree`).
- **Branch:** `etapa/diagnostico-m1`, a partir de `develop` em `a780c9d1`.
- **Commits na branch:**
  - `2b29b381` Pedido 48: o texto do pedido (diagnostico da M1 v2);
  - `6b538659` Pedido 48, Parte 0: data/diagnostico_m1/ no .gitignore;
  - `9b963db3` Pedido 48, Parte A: secao 7.5 da M1 (hipoteses, regras e o que se espera), registrada antes das contas;
  - `420f3d94` Pedido 48, Parte A: emenda antes das contas (a entrada media do passo atrasa uma dinamica rapida na grade; a regra da H2 nao muda);
  - `7f5a1d76` Pedido 48, Parte B: o script do diagnostico (canais extras, a reproducao do 46 conferida em 515 numeros com diferenca 0) e as contas;
  - `ae788ec5` Pedido 48, Parte C: as analises (C.1 a C.9), o JSON e as figuras;
  - `5844ab49` Pedido 48, Parte E: testes do diagnostico e a suite;
  - `50d8ef07` Pedido 48, Partes D e F: secao 7.5 da M1 com o resultado, o quadro das causas e os trabalhos futuros; linhas no ADR 0028 e na arquitetura;
  - `7fa1a245` Merge develop em etapa/diagnostico-m1 (o pedido 47) antes do merge do pedido 48;
  - o commit deste relatório (veja "O envio").
- **Merge em `develop`:** veja "O merge e o envio".
- **Arquivos de handoff** (`docs/handoff/2026-11-09_48_diagnostico-da-m1-v2…`):
  - `_relatorio.md` (este);
  - `.json` (todos os números da Parte C e a conferência da reprodução);
  - `_mapa_do_erro.png`, `_deriva.png`, `_atraso.png`, `_wheelslip.png`, `_episodios.png` e `_episodios_vx10.png` (as figuras);
  - `_testes.txt` (a suíte do backend).

## Em uma frase

**A M1 v2 erra nas curvas, na velocidade lateral, quando o pneu da frente trabalha torcido e o carro passa de 2 g.** Três causas foram apoiadas pelas regras registradas antes: o pico do pneu (H1), a direção com muito volante (H3) e a carga (H4). Elas se misturam nos mesmos casos. A memória (H6) é apoiada pela regra, mas fraca. O acúmulo no horizonte (H5) não é apoiado. A relaxação (H2) ficou sem dados, e 01/11 (H7) ficou inconclusivo. O veredito da M1 v2 não muda.

## Parte 0: a pasta separada

- **O comando** (rodado pelo Eduardo): `git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer worktree add C:\Users\Dokas\Desktop\f1-telemetry-analyzer-48 -b etapa/diagnostico-m1 develop`. `develop` tinha o merge do 46 (`1124b163`), e o ADR 0028 tinha a seção "Resultado".
- **Uma trava, resolvida pelo Eduardo:** o comando tinha rodado como administrador, e o git recusava a pasta ("dubious ownership").
  - O Eduardo devolveu a pasta e três itens do `.git` da principal ao usuário Dokas com o `icacls`: `worktrees\f1-telemetry-analyzer-48`, `refs\heads\etapa\diagnostico-m1` e o log dela.
  - Nenhuma trava foi contornada: sem `safe.directory`, e sem mudar dono por conta própria.
- **0.2, o texto do pedido:** copiado e commitado (`2b29b381`), com o mesmo sha256 nas duas cópias (`ced7e756…9794`). **Na pasta principal, foi apagado só `docs/prompts/2026-11-09_48_diagnostico-da-m1-v2.md`.** Ela ficou limpa, em `etapa/replay-e-radio-que-ensina`, sem troca de branch.
- **0.3, os imports:** o `.venv` da principal, rodando de dentro de `f1-telemetry-analyzer-48\backend`. `core.__file__` e `ml.__file__` apontam para a pasta do 48. Nada foi instalado.
- **0.3, os dados:**
  - junções só para leitura em `data\recordings`, `data\ml` e `data\cache`, apontando para a principal;
  - a sessão `2026-10-17_16-17-08` foi lida da pasta do app instalado, só lida;
  - o que este pedido gera foi para `data\diagnostico_m1\`, uma pasta de verdade, no `.gitignore` (`6b538659`). Ela tem cerca de 4,4 GB, quase tudo nos 5 Processos Gaussianos salvos (865 MB cada);
  - **as fotos antes e depois:** `data\ml` da principal tinha 616 arquivos (nome, tamanho e data) antes e tem os mesmos 616 depois, com **zero diferenças**. `data\cache` (3 arquivos) e `data\recordings` (313) também não mudaram com a suíte.
- **0.4, o processador:** o `acs.exe` abriu duas vezes durante o pedido (09/11, por volta de 14:40 e 15:01). As contas pararam e só voltaram com o jogo fechado; o script confere o jogo antes de cada rodada.
- **0.5:** o ADR 0008 não foi tocado.

## Parte A: o registro antes das contas

- **`9b963db3`:** a seção 7.5.1 de `docs/modelo_fisico_m1.md`, com as hipóteses, as regras com as faixas, as definições, como cada regra é medida e o que se espera. Ela foi commitada antes de qualquer conta nas sessões.
- **`420f3d94`, uma emenda antes das contas:**
  - O teste sintético da Parte E mostrou que a frase "a entrada média do passo não atrasa a resposta" estava errada para dinâmicas rápidas. Rodado na grade de 50 ms, um sistema de primeira ordem atrasa 16 ms com τ = 10 ms, 5,6 ms com τ = 40 ms e menos de 3 ms com τ ≥ 80 ms.
  - A frase foi corrigida e a tabela registrada. A regra da H2 não mudou.
  - Isso foi achado e commitado antes de qualquer conta nas sessões.

## Parte B: os dados e a reprodução

- **Os canais extras:** `rideHeight`, `wheelSlip`, `suspensionTravel`, DRS, combustível, ar, pista e `isAIControlled`.
  - Saíram das gravações com o mesmo corte (`iter_voltas_m1`, linha a linha) e a mesma reamostragem do 46.
  - **A grade refeita é igual à do 46 chave a chave e coluna a coluna** nas 5 sessões e nas 3 de depois. Os canais estão preenchidos em 100% dos passos.
- **De onde vieram os modelos:**
  - os parâmetros da física de cada rodada vêm de `rodadas_treino_v2.json`;
  - os Processos Gaussianos não tinham sido salvos pelo 46. Foram reajustados pela própria `experimento_v2.fase_teste`, sem mudança: mesmo código, mesma amostra de 6.000 passos e semente 46. Levou de 725 a 1.031 s por rodada;
  - eles ficaram salvos em `data\diagnostico_m1\modelos_*.pkl`.
- **A conferência:**
  - o erro quadrático dos 39.142 casos é igual ao do 46 em cada modelo (M1 v2, física v2, R0 e física v1), **com diferença 0,0**;
  - os **515 números** da seção 7.3 (os 7 critérios, os horizontes, as tabelas por sessão, regime e faixa e o "não conclusivo") se repetem com diferença máxima de 0,0. O critério 1 dá 0,4868, e o 2, 0,2069.
- **Os casos** estão em `data/diagnostico_m1/casos.parquet`. Cada um tem:
  - a rodada, a sessão, a volta, o instante, a curva e a fase;
  - o estado e as entradas no início, e a deriva de cada roda;
  - a carga gravada e a prevista, `rideHeight` e `wheelSlip`;
  - os erros normalizados de cada grandeza em 1, 2, 5, 10 e 20 passos (M1 v2, física v2, R0 e a soma dos incrementos) e o índice do "não conclusivo".

  Os passos das sessões de teste estão em `passos.parquet`.
- **Os arquivos `_v2` do 46 não foram reescritos:** a foto de `data\ml` confere.
- **Uma diferença com o contexto, sem consequência:** a volta de 2:25,948 (a 10 do `session-index.json` de 01/11) aparece nas amostras com `lap_number` 9. Ela foi achada pelo tempo, como o pedido manda.

## Parte C: as análises

Os números completos estão no JSON e na seção 7.5.3 de `docs/modelo_fisico_m1.md`. O resumo:

- **C.1, o acaso:**
  - o IC 95% do skill do critério 1 vai de **0,447 a 0,523** (0,50 está dentro);
  - nas curvas, vai de 0,409 a 0,501;
  - por sessão, 0,50 fica fora só em 17/10 16:17 (acima) e em 21/10 (abaixo).

  O veredito não muda: o critério é o valor pontual.
- **C.2, onde está o erro das curvas:**
  - a velocidade lateral tem 76% do erro;
  - acima de 2 g estão 21% dos casos e 50% do erro;
  - a deriva dianteira acima de 6° tem 12% dos casos e 48% do erro (skill 0,24, contra 0,67 abaixo de 3°);
  - \|`steer`\| de 0,1 a 0,4 tem 69% do erro;
  - com o volante parado (tercil de baixo), o skill é 0,30;
  - a C06 tem 20% do erro, e a C02, 11% (skill −0,05);
  - **as curvas precisariam de 0,475, e têm 0,458.**
- **C.3, o atraso: sem dados pela regra.**
  - De 16% a 30% dos intervalos das amostras cruas passam de 20 ms. O trecho mais longo só com intervalos de até 20 ms dura de 0,22 a 0,29 s, e nenhuma entrada cabe.
  - Só para informação, com os trechos da seção 1.2 (412 entradas), **o jogo responde de 30 a 36 ms antes da física v2**, o contrário da relaxação.
- **C.4, a direção:**
  - nas 9.985 amostras quase estacionárias, o ganho cai de 0,300 (\|`steer`\| < 0,1, igual ao `k_δ`) para 0,215 (0,4 a 0,6), **28% a menos**;
  - o erro de `r` com \|`steer`\| ≥ 0,4 é 2,8 vezes a mediana das curvas;
  - por faixa de velocidade, a regressão não identifica o ganho (`a_y ≈ vx·r` dentro da faixa).
- **C.5, a carga:**
  - a altura e a velocidade explicam 57% e 61% do resíduo da carga, e só `vx²` explica 3%;
  - o skill cai de 0,62 para 0,33 do quartil de menor para o de maior erro de carga;
  - **a massa pela soma das cargas, com o carro quase parado, é de 735 a 752 kg**, contra 578 a 653 kg das regressões da v1;
  - o DRS foi gravado e ficou sempre desligado;
  - a altura também é efeito da carga, o que limita a leitura.
- **C.6, a cobertura:**
  - a deriva dianteira passa de 6° em 8% dos passos, e de 10° em menos de 1%;
  - a traseira passa de 6° em 2%;
  - 01/11 tem menos deriva alta que 24/10 (5% contra 13% na frente);
  - o `wheelSlip` cresce com a deriva e com a força por carga (Spearman de 0,92 a 0,98), e a força não para de crescer dentro dos dados.
- **C.7, o acúmulo e a memória:**
  - **a razão de acúmulo nas curvas é 0,76:** o erro em malha aberta é menor que o da soma dos incrementos de um passo;
  - a autocorrelação do resíduo de um passo no atraso 1 é 0,51 em `vy` e 0,16 em `r` nas curvas, contra 0,85 e 0,52 na reta;
  - a parcial com o volante de antes fica abaixo de 0,05.
- **C.8, 01/11:**
  - o skill é 0,12, contra 0,42 e 0,41 em 24/10, reproduzindo a C.4 do 46;
  - com deriva abaixo de 3°, dá 0,58 contra 0,75: diferença de 0,17;
  - pneus a 58 °C, contra 86 e 89 °C; ar e pista gravados em 0 °C, como nas outras sessões da noite;
  - CSP 0.3.1 pela informação do Eduardo; nas outras sessões, "não registrada";
  - **os 7 episódios:** pela regra, os 7 picos caem com o carro já girado, parado ou de ré (β de ±156° a ±180°), e a contagem (M1 v2 em 4 de 7) não fala da escapada. Só para informação, com `vx` ≥ 10 m/s, a M1 v2 acompanha em 2 de 7 e a física v2 em 3;
  - o início é "não conclusivo" em 38 dos 42 casos.
- **C.9, o que o jogo expõe:**
  - a memória compartilhada que o repositório lê não tem a deriva, a razão de escorregamento nem as forças do pneu;
  - ela tem `wheelAngularSpeed` e `tyreContactHeading`, que o gravador não grava;
  - a telemetria por UDP (`RTCarInfo`) tem `slipAngle`, `slipRatio`, `load`, `Dy` e `Mz` por roda (fonte: https://docs.google.com/document/d/1KfkZiIluXZ6mMhLWfDX1qAGbvhGRC3ZUzjVIt5FQpp4/pub);
  - no SDK de Lua do CSP (https://github.com/ac-custom-shaders-patch/acc-lua-sdk), a definição dos campos da roda não foi confirmada.

## Parte D: o quadro das causas

| | hipótese | o número que decidiu | rótulo |
|---|---|---|---|
| H1 | o pico do pneu | dianteira: 0,67 contra 0,24 (diferença 0,43) e 48,1% do erro acima de 6° | **apoiada** |
| H2 | a relaxação | nenhuma entrada nos trechos de até 20 ms | **sem dados** |
| H3 | a direção | ganho 28% menor; erro de `r` 2,8 vezes | **apoiada** |
| H4 | a carga | R² de 0,57 e 0,61; diferença de skill de 0,29 | **apoiada** (a altura também é efeito da carga) |
| H5 | o acúmulo | razão de 0,76 | **não apoiada** |
| H6 | a memória | 0,51 em `vy` no atraso 1 (na reta, 0,85) | **apoiada pela regra**, leitura fraca |
| H7a | 01/11, a pilotagem | diferença de 0,17 | **inconclusiva** |
| H7b | 01/11, o carro ou o jogo | diferença de 0,17 | **inconclusiva** |

- **A ordem,** pela parte do erro das curvas: H1 (48,1%), H4 (50,0% no quartil de maior erro de carga) e H3 (13,5%). As partes se sobrepõem: 63% dos casos com muito volante têm a deriva dianteira acima de 6°, e a união das três tem 77,6%.
- **A deriva estimada usa `k_δ` linear,** então a H1 e a H3 se confundem. A rampa de volante dos dados de manobra as separaria.

**Os trabalhos futuros** estão na seção 7.5.4, com as citações:
- **os dados de manobra:** o círculo com a velocidade subindo, a rampa de volante e o seno de volante, este com o gravador sem cair para 20 Hz;
- **um modelo novo, só depois do 42 e em sessões novas.** A prioridade é o pneu identificado até o pico, a direção não linear e a carga com a altura e a massa medida. Ficam "a testar" o histórico, a relaxação e a inércia, e o ajuste em vários passos.

## Parte E: os testes

- **`backend/tests/test_m1_diagnostico.py`: 22 testes, todos passam.** Eles cobrem:
  - o bootstrap por volta (largura zero com razão constante, e o intervalo do método delta);
  - a deriva numa curva em regime permanente, com os sinais;
  - o atraso de um sistema de primeira ordem em 3 velocidades (erro de até 2,3 ms, com limite de 5 ms);
  - o efeito da grade de 50 ms;
  - o ganho não linear da direção;
  - as partes do erro e o skill necessário, contra a conta à mão;
  - a razão de acúmulo igual a 1 sem realimentação;
  - a autocorrelação por pares;
  - a correlação parcial e o pico de um episódio.
- **A suíte do backend:** 941 passam e 1 falha (`docs/handoff/..._testes.txt`, 8 min 56 s). A falha é `test_leitura::test_volta_da_conferencia_nos_arquivos_reais`. É a mesma falha de ambiente que o pedido 47 relatou: a pasta separada não tem o `data/reference_models/vhe_interlagos.geometry.json`, que o git ignora.
- **A suíte depois do merge com `develop`:** veja "O merge e o envio".

## Parte F: a documentação

- **`docs/modelo_fisico_m1.md`, seção 7.5:** o registro (7.5.1), a reprodução (7.5.2), o resultado (7.5.3), o quadro e os trabalhos futuros (7.5.4) e o parágrafo para quem não é da área (7.5.5).
- **ADR 0028:** a linha de atualização.
- **`docs/arquitetura_ml.md`:** uma linha na parte da M1.
- **`docs/backlog.md`:** não editado; os itens estão abaixo.

## Desvios e escolhas, todos registrados

1. **A H2 ficou "sem dados" pela regra.** A C.3 também foi rodada com os trechos de menos de 50 ms, marcada como informativa e sem decidir.
2. **Na C.3, a taxa do volante é a de `−steer`.** A roda vira `−k_δ·steer`, e com `steer` puro a correlação sai negativa. É um sinal da convenção, não uma regra nova.
3. **A massa da C.5 lê todas as amostras da gravação,** porque nas voltas válidas o carro quase nunca anda abaixo de 15 m/s. O pedido não restringe às válidas. Entram só amostras com as 4 cargas acima de zero.
4. **Os 7 episódios:** a regra do pico pega o carro já girado. O resultado pela regra é relatado, e ao lado vai uma versão informativa com `vx` ≥ 10 m/s.
5. **Os 3 casos com a soma das cargas em zero** ficam fora dos quartis de carga.

## O merge e o envio

- **`develop` tinha andado,** com o merge do pedido 47 (`545f6c8d`). Ela não estava aberta em nenhuma pasta: a do 47 está na branch dele.
- **`7fa1a245`:** `develop` trazida para a branch. O único conflito foi no `.gitignore` (as linhas do 47 e do 48), e as duas ficaram.
- **A suíte depois desse merge:** 965 passam e 1 falha, a mesma de ambiente (`_testes_pos_merge.txt`).
- **`1781c10f`:** Merge do pedido 48 em `develop` (pai 1: `545f6c8d`, que era o `develop` do remoto; pai 2: `7fa1a245`).
- **Este relatório** foi commitado em `develop`, logo depois do merge, e `etapa/diagnostico-m1` foi avançada até ele (avanço simples). A pasta do 48 voltou para `etapa/diagnostico-m1`.
- **Antes do primeiro envio,** os commits foram conferidos: nada acima de 50 MB (o maior é o JSON, com 248 KB), nenhum segredo, nenhuma gravação e nada de `data/ml` ou `data/diagnostico_m1`.
- **Os envios** (só avanço simples, sem `--force`):
  - `etapa/diagnostico-m1`: enviada depois da Parte A (`9b963db3`), da Parte B (`7f5a1d76`) e das Partes C a F (`50d8ef07`). Em cada uma, o hash do remoto conferiu com o local;
  - o envio final de `develop` e da branch, com os hashes conferidos, está no fim deste relatório.
- **`main` e as tags** não foram enviadas.
- **A pasta separada fica,** para o Eduardo decidir quando apagar.

## Itens para o backlog (não editado)

1. **Uma sessão de dados de manobra** (o círculo com a velocidade subindo, a rampa de volante e o seno de volante), com o gravador sem cair para 20 Hz. Ela é a base de qualquer v3, e só depois do 42.
2. **Gravar `wheelAngularSpeed` e `tyreContactHeading`,** que o adaptador já lê, ou ler a telemetria por UDP (`RTCarInfo`) para ter `slipAngle` e `slipRatio` do jogo.
3. **Conferir os campos de ar e de pista à noite:** eles valem 0 °C nas 4 sessões da noite.
4. **A massa da física da M1 pela soma das cargas parado** (735 a 752 kg), no lugar da regressão (578 a 653 kg), se houver um modelo novo.
5. **Gravar a versão do CSP** no `metadata.json` da sessão.
6. **O `geometry.json` de `data/reference_models`** falta nas pastas separadas, e o `test_leitura` falha nelas: copiar ou pular o teste com uma razão clara.
7. **Apagar a pasta do 48 e os 4,4 GB de `data\diagnostico_m1`** quando o Eduardo decidir.

## O envio conferido (11/11)

| ref | hash local | hash no remoto (`git ls-remote origin`) |
|---|---|---|
| `refs/heads/develop` | `3a3aed00fceb1ff81cd769c2dcaa228056436eb2` | `3a3aed00fceb1ff81cd769c2dcaa228056436eb2` |
| `refs/heads/etapa/diagnostico-m1` | `3a3aed00fceb1ff81cd769c2dcaa228056436eb2` | `3a3aed00fceb1ff81cd769c2dcaa228056436eb2` |

O commit que acrescenta esta tabela vai nas duas refs pelo mesmo caminho: commit em `develop`, avanço simples da branch e envio das duas, com o hash conferido no chat. Nada pediu login, nada foi recusado, e o remoto não tinha divergido (`develop` estava em `545f6c8d` nos dois lados antes do merge).
