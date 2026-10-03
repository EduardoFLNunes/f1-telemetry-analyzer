# Fase 2c — Ferramentas da sessão controlada

Relatório de 2026-10-02. Segue o ADR 0011 e o
[protocolo](experimentos/protocolo_sessao_controlada.md). Branch
`etapa/fase2c-ferramentas-experimento`, a partir de `handoff/fase2b`.

Ainda não existe sessão gravada com o protocolo. Esta etapa só prepara as
ferramentas e as testa com dados sintéticos e com dois ensaios em sessões reais
já existentes.

---

## 1. Antes da sessão: o plano

```bash
cd backend && python -m ml.scripts.plan_controlled_session --semente 2026
```

Opções: `--curva` (padrão "Bico de Pato"), `--condicoes` (padrão `A,B,C,D`),
`--voltas-por-condicao` (padrão 8), `--aquecimento` (padrão 5) e `--data`.

O comando grava dois arquivos em `docs/experimentos/`:

- `<data>_plano.csv`, com as colunas `ordem`, `bloco`, `condicao`, `freada` e
  `linha`, mais `curva` e `semente` em todas as linhas. Com a mesma semente, o
  plano sai idêntico.
- `<data>_plano.txt`, para imprimir ou deixar na tela.

O aquecimento entra no plano como bloco 0, com a condição `AQ`. Depois vêm 8
blocos, cada um com A, B, C e D numa ordem sorteada.

**Plano de exemplo** (semente 2026, para você conferir):
[`2026-10-02_plano.txt`](experimentos/2026-10-02_plano.txt). São 37 voltas:
5 de aquecimento e 32 medidas, em 8 blocos. Os blocos têm 6 ordens distintas
(DBAC, ABCD, ABCD, BCDA, DBCA, DABC, ADCB, BCDA). Repetir uma ordem é normal num
sorteio entre 24 possíveis, e não prejudica nada: o que o desenho exige é cada
condição uma vez por bloco.

## 2. Depois da sessão: a análise

```bash
cd backend && python -m ml.scripts.analyze_controlled_session --sessao <id> --plano ../docs/experimentos/<data>_plano.csv --invalidas 7,19
```

`--invalidas` recebe os números de volta **do jogo** que você anotou como
inválidos.

O que a análise faz, em ordem:

1. **Lê a sessão pelo pipeline existente.** `scan_sessions` aplica os gates de
   qualidade e `build_store` faz o alinhamento na grade de 2 m. Nenhum leitor
   novo.
2. **Casa as voltas com o plano, em ordem.** Volta aproveitável = passou nos
   gates e não foi anotada como inválida. A volta de saída dos boxes cai nos
   gates sozinha. **Se a contagem não bater, a análise para** e lista cada volta
   gravada com o motivo de ela ter sido usada ou não. Nunca adivinha.
3. **Janela de curva da Fase 2b,** com as zonas de frenagem tiradas das outras
   sessões. O Bico de Pato é a janela da curva C10, de 2590 a 3080 m.
4. **Conferência da execução,** a parte mais importante. Para cada volta, mede o
   ponto de frenagem e a posição lateral na entrada, no ápice e na saída. Por
   condição, relata a diferença real contra A. A linha aparece como "para dentro
   da curva": no Bico de Pato, que é à direita, para dentro é lateral negativo.
   Se a média da condição errar o pedido por mais de 5 m na frenagem ou mais de
   1 m na linha de entrada, o relatório diz **"longe do pedido"** e explica o que
   foi executado.
5. **Efeitos com IC 95 %** (ver seção 3):
   - frenagem = média(B, D) − média(A, C);
   - linha = média(C, D) − média(A, B);
   - interação = (D − C) − (B − A);
   - e também B − A, C − A e D − A.
6. **Comparação com os estimadores.** E1 a E4 da Fase 2b são treinados com todas
   as outras sessões, sem a controlada. Cada um recebe as diferenças **reais**
   medidas no passo 4: as médias de B, C e D menos as de A, nas 5 entradas
   acionáveis. Para cada X − A, o relatório dá o erro e se o efeito medido cai
   dentro da faixa de 95 % do estimador. Também marca quando a entrada está fora
   da faixa de treino. Para os efeitos principais e a interação, as previsões
   são combinadas da mesma forma e comparadas com o IC medido.
7. **Saída:** `docs/experimentos/<data>_resultado.json` e `<data>_resultado.md`.
   A data padrão é a do id da sessão.

## 3. Por que modelo linear com efeito de bloco, e não bootstrap

O pedido deixou escolher entre bootstrap dentro dos blocos e modelo linear com
efeito de bloco. Escolhi o **modelo linear**:

`tempo da janela = média da condição + efeito do bloco + erro`

- **É o modelo do delineamento.** A sessão é um experimento em blocos
  casualizados: toda condição aparece em todo bloco, em ordem sorteada. O efeito
  do bloco absorve o que muda ao longo da sessão (pneu, combustível, cansaço), e
  os contrastes entre condições saem livres dele.
- **Aguenta um bloco incompleto.** Se uma volta se perder e não for repetida, o
  modelo continua valendo. O bootstrap dentro dos blocos precisa de blocos
  completos.
- **Com 8 blocos, o bootstrap é instável.** Reamostrar 8 grupos dá poucas
  combinações distintas, e o intervalo fica irregular. O IC do modelo usa a
  distribuição t com os graus de liberdade do resíduo (32 voltas − 4 condições
  − 7 blocos = 21).
- **A premissa foi testada.** O modelo supõe erro aproximadamente normal e com a
  mesma dispersão nas condições. No teste com 300 sessões sintéticas, o IC de
  95 % conteve o efeito verdadeiro em 90–99 % delas, dentro do esperado. Se uma
  sessão real mostrar voltas muito discrepantes, isso aparece no desvio do
  resíduo, que vai para o JSON.

## 4. Testes (sintéticos)

18 testes em `backend/tests/test_ml_controlled.py`. A sessão sintética tem
efeitos conhecidos: frear 10 m antes custa 40 ms, mudar a linha custa 20 ms, sem
interação, e cada volta tem 20 ms de ruído.

| o que | resultado |
|---|---|
| plano reproduzível pela semente; outra semente muda a ordem | passa |
| cada bloco tem as 4 condições uma vez; 37 linhas, ordem 1..37 | passa |
| efeitos conhecidos dentro do IC; frenagem de 40 ms com IC que exclui zero | passa |
| cobertura do IC em 300 sessões sintéticas entre 90 % e 99 % | passa |
| interação de 80 ms detectada | passa |
| bloco incompleto (última volta perdida) ainda estima | passa |
| conferência: executado como pedido não é marcado; −3 m e 0,5 m são marcados "longe do pedido" | passa |
| "para dentro" segue o lado da curva | passa |
| contagem diferente do plano: para e lista as voltas com o motivo | passa |
| volta anotada como inválida é retirada e o resto casa | passa |
| volta inválida com número do jogo repetido: para e pede o `lap_id` | passa |
| contrastes previstos a partir de previsões por condição | passa |

## 5. Ensaios com sessões reais (não são resultados)

Os dois ensaios só verificam que as ferramentas rodam com dados reais. Nada
neles mede efeito, porque nenhuma das sessões foi pilotada com o protocolo.

1. **Parada.** O plano de exemplo (37 voltas) contra a sessão
   `2026-08-16_03-30-14`, que tem 7 voltas aproveitáveis de 16. A análise
   **parou** e listou as 16 voltas com o motivo de cada exclusão. Ela também
   mostrou que o **número de volta do jogo se repete**: há duas voltas 4 e duas
   10, ambas aproveitáveis. Por isso a anotação de inválidas pelo número do jogo
   pode ser ambígua, e nesse caso a análise para e pede o `lap_id`.
2. **Caminho completo.** Um plano fabricado de 52 voltas (13 por condição, sem
   aquecimento), com rótulos sorteados, contra as 52 voltas aproveitáveis de
   `2026-08-09_19-20-59`. O piloto não mudou nada, e é isso que a análise
   mostra:
   - a conferência marca B, C e D como "longe do pedido" (frenagem +1,1 m em vez
     de −10 m; linha 0,0 m em vez de 2 m para dentro);
   - os efeitos ficam com IC que inclui zero (frenagem −12 ms [−30; +6]);
   - os quatro estimadores rodaram.

## 6. O que vale saber antes da sessão

- **A linha pedida está fora do que os dados já viram.** Na janela do Bico de
  Pato, a diferença de posição lateral **na entrada** entre voltas de treino vai
  de −0,7 a +1,5 m (2,5 % a 97,5 %). Os 2 m para dentro pedidos ficam fora disso.
  A frenagem de 10 m mais cedo fica dentro (faixa de −18 a +24 m). Os
  estimadores vão extrapolar na linha, como o ADR 0011 previa, e o relatório
  marca isso.
- **Anote as voltas inválidas pelo número do jogo, e se possível também pela
  ordem no plano.** O número do jogo pode se repetir.
- **Repita a condição depois de uma volta inválida.** Senão a contagem não bate
  e a análise para.
- **A análise exige as quatro condições,** com A como referência.

## 7. Arquivos

| arquivo | conteúdo |
|---|---|
| `backend/ml/validation/controlled.py` | condições, plano, casamento de voltas, conferência, efeitos, comparação |
| `backend/ml/scripts/plan_controlled_session.py` | gerador do plano |
| `backend/ml/scripts/analyze_controlled_session.py` | análise da sessão |
| `backend/tests/test_ml_controlled.py` | 18 testes sintéticos |
| `docs/experimentos/2026-10-02_plano.csv` e `.txt` | plano de exemplo, semente 2026 |

Reutilizado sem duplicar:

- leitor, gates e store (`scan_sessions`, `build_store`);
- janelas, entradas e estimadores da Fase 2b (`empirical.py`);
- envelope, simulador e filtros (`counterfactual.py`).

O preparo dos dados de treino dos estimadores (pares, entradas, envelope) repete
em ~15 linhas o que `validate_empirical.py` faz dentro de cada rodada. Preferi
isso a mexer no código de uma fase já entregue.

Nada da interface, do `optimal.json` ou das LSTMs foi tocado.

---

## 8. Ajustes de 2026-10-02 (branch `etapa/fase2c-ajustes`)

**Intervalo de confiança.** Conferido: o IC já usava a distribuição t com os
graus de liberdade do resíduo. Com 8 blocos são 32 voltas − 4 condições −
7 blocos = 21, e não a normal. Os "90 % a 99 %" citados antes eram só a
tolerância folgada do teste com 300 sessões, não a cobertura medida. Medida com
4000 sessões sintéticas (erro-padrão de ±0,3 ponto), a cobertura ficou em:

| contraste | cobertura do IC 95 % |
|---|---:|
| frenagem | 95,3 % |
| linha | 94,8 % |
| interação | 95,2 % |
| B − A | 95,1 % |
| C − A | 94,9 % |
| D − A | 94,9 % |

O teste passou a usar 1000 sessões, os três efeitos principais e tolerância de
93 % a 97 %.

**Lista de voltas.** Quando a análise para, cada volta gravada aparece com o
número da volta no jogo, o tempo de volta (o cronômetro do jogo) e a hora. Por
exemplo: `(volta 4 no jogo, tempo 1:34.290, as 03:36:10)`. A lista também vai
para o JSON do resultado (`voltas_gravadas`).

A hora vem do `startedAt` do `metadata.json`, que é o relógio do PC, somado ao
tempo decorrido desde a primeira amostra. Ela **não** vem direto do `timestamp`
gravado: nas 5 sessões conferidas (maio a agosto), converter o `timestamp` pelo
fuso local dá sempre 3 h a mais que o `startedAt`. A causa no gravador não foi
investigada nesta etapa.

---

## 9. Início pela volta anotada (2026-10-03, branch `etapa/fase2c-inicio-por-volta`)

Contar de cabeça as voltas de aquecimento é fácil de errar, e um erro de uma
volta desalinharia o plano inteiro. Por isso:

- **O plano impresso pede uma anotação.** Logo no início do bloco 1 aparece a
  linha `ANOTE o numero no jogo desta volta (primeira do bloco 1): ____`.
- **A análise ganha `--inicio <numero no jogo>`.** A partir dessa volta, as
  voltas aproveitáveis são casadas com os blocos, em ordem. Tudo antes dela é
  ignorado, seja quantas voltas forem.
- **As voltas medidas continuam conferidas de forma estrita:** 32, mais as
  repetidas por invalidez. Se a conta não bater, a análise para e lista as
  voltas a partir do início.
- **Também para com mensagem clara** se o número dado em `--inicio` não existir
  na gravação, ou se aparecer mais de uma vez (contador travado no box).
- **Uma volta inválida anotada antes do início é ignorada.**
- **Sem `--inicio`,** o comportamento é o anterior (contagem pelo plano). A
  mensagem de parada passa a sugerir `--inicio`.

Testado: com 4, 5 e 7 voltas de aquecimento e `--inicio`, o casamento, os
efeitos e a conferência da execução saem idênticos.

```bash
cd backend && python -m ml.scripts.analyze_controlled_session --sessao <id> --plano ../docs/experimentos/<data>_plano.csv --inicio 9 --invalidas 14
```
