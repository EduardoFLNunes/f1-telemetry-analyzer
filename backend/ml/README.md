# Aprendizado de traçado — Interlagos

Subsistema que aprende, das voltas gravadas do piloto, a relação entre pilotagem
e tempo de volta, e usa isso para produzir um traçado de referência otimizado —
e para dizer, volta a volta, onde o piloto se afasta dele e quanto isso custa.

Roda **offline**, a partir das sessões já gravadas em `data/recordings/`. Não
participa do runtime do aplicativo e não entra no executável empacotado.

```
data/recordings/*/player.jsonl
        │
        ▼  ml/data/          leitura, identidade de volta, inventário
        ▼  ml/preprocessing/ limpeza, alinhamento por distância, reamostragem, splits
        ▼  ml/track/         geometria, microsetores, curvas, corredor
        ▼  ml/features/      atributos + referência do piloto por microsetor
        ▼  ml/models/        LSTM geradora + LSTM substituta
        ▼  ml/optimization/  envelope do carro, simulador, algoritmo evolutivo
        ▼  ml/comparison/    volta do piloto × traçado
        ▼  ml/visualization/ mapa, telemetria, delta, evolução
```

Os diagramas da arquitetura estão em
[docs/arquitetura_ml.md](../../docs/arquitetura_ml.md); a formulação matemática
das redes, em [docs/lstm_matematica.md](../../docs/lstm_matematica.md). O que foi
medido — e não apenas escrito — está em
[docs/auditoria_ml.md](../../docs/auditoria_ml.md).

Para reproduzir as medições:

```
python -m ml.scripts.run_pipeline   # o fluxo inteiro, dataset -> traçado
python -m ml.scripts.validate       # as evidências de aprendizado e de busca
```

## O dataset real

58 sessões de Interlagos, 11 GB, ~1,9 milhão de amostras, **um piloto**
(`player_1`). O enunciado do trabalho fala em "voltas realizadas por pilotos";
o que existe é um piloto e muitas voltas, então o sistema aprende variação entre
voltas do mesmo piloto. `driver_id` atravessa o pipeline inteiro para quando
houver mais de um.

| medida | valor |
|---|---|
| voltas brutas detectadas | 1009 |
| voltas que passam nos gates | **113**, em 10 sessões |
| melhor volta | 84,848 s |
| mediana das válidas | 85,97 s |
| taxa de amostragem (p10 / mediana / p90) | 20 / 31 / 58 Hz |
| grade espacial | 2167 pontos de 2,00 m |
| divisão treino / validação / teste | 60 / 39 / 14 voltas, por sessão |

O que o gate rejeita, e por quê, está em `preprocessing/quality.py` — cada
limiar tem, no comentário, a volta concreta do dataset que passaria sem ele.

## As decisões que definem o sistema

**A distância é recalculada, nunca lida.** Seis sessões gravaram
`distanceAlongTrack` como `null`, e as que gravaram usaram versões diferentes da
geometria. A projeção é refeita aqui contra o cache atual, e bate com o que o
runtime gravou dentro de 0,15 m (p95).

**Os canais de pilotagem estão aninhados.** `throttle`, `brake` e `steerAngle`
vivem em `sample.carPhysics.controls`, e não no topo da amostra. O caminho que o
resto do backend usa (`core.assisted_analysis.utils.normalize_lap_dataframe`)
procura no topo e devolve zeros, sem erro. `ml/data/samples.py` existe por isso.

**A identidade da volta é a ordem no arquivo, não o número do jogo.** O contador
de voltas do Assetto Corsa trava durante a parada de box: a sessão
`2026-08-16_03-30-14` tem quatro trechos distintos gravados como volta 6, três
deles com o carro parado.

**Duas redes, não uma.** Uma rede só, treinada para prever "a linha ideal",
aprende a linha *típica* — a média das voltas boas e ruins, que é o que o
enunciado proíbe.

- **Geradora** (`REFERENCE_TASK`): entra a pista mais **quanto a volta perdeu**
  para a melhor do piloto naquele microsetor; sai trajetória, velocidade e
  pedais. Consultada com perda zero, ela responde como se dirige quando se está
  no próprio recorde em todos os trechos ao mesmo tempo — uma volta que o piloto
  nunca deu.
- **Substituta** (`SURROGATE_TASK`): entra a forma da trajetória; sai o tempo.
  É o termo com que o algoritmo evolutivo corrige a física.

**O fitness não é só a rede.** Uma rede treinada nas voltas do piloto só premia
o que já viu, e nunca apontaria nada melhor que a melhor volta dele. O custo é
`(1−α)·tempo_físico + α·tempo_da_rede + penalizações`, com a física por padrão
pesando mais.

**O envelope do carro mede capacidade, não demanda.** Tomar o percentil 98 do g
lateral por faixa de velocidade mede o que o piloto *pediu*: a 272 km/h ele está
em reta, e o envelope saía com 0,41 g. O simulador lia isso como limite e
devolvia voltas de 131 s onde o piloto faz 88. Lateral e frenagem são medidos só
onde estão sendo exigidos, e ajustados por `a = a₀ + k·v²` — a forma que a carga
aerodinâmica impõe.

**Uma sessão inteira foi gravada sem os pedais.** `2026-06-14_12-23-46` tem 12
voltas com posição e velocidade perfeitas e nenhum bloco `carPhysics`. Elas
passavam por todos os outros gates, e nove delas caíam no conjunto de teste —
que assim media a rede contra um alvo que não existia.

**A geometria de pista precisou de conserto, em duas camadas.** A centerline
reconstruída por raycast tem 10 regiões (108 m, 2,5% da pista) em que o ponto
médio salta vários metros de lado: depois de duas derivadas isso vira uma curva
de raio 0,4 m, e o simulador freava até 22 km/h numa reta a 230 km/h. Fora os
degraus, sobram ondulações de centímetros por toda a pista — e essas importam
porque a trajetória é medida *contra* a centerline: onde a referência ondula, o
`lateral` de uma volta real ondula ao contrário para compensar, e nenhuma
representação suave reproduz essa compensação.

`track/geometry.py` resolve as duas: conserto cirúrgico das regiões defeituosas
(interpolação monótona a partir da geometria boa em volta) e passa-baixo de 60 m
na linha de referência, com as larguras remedidas contra as bordas reais para o
corredor não se mover junto. O histórico das três abordagens que falharam antes
está nos docstrings, para ninguém tentar de novo.

**O simulador e a geometria usam janelas de curvatura diferentes**, e não por
descuido: 12 m descreve a pista, 30 m descreve o raio que o carro percorre. Uma
ondulação de 20 cm a cada 25 m — que toda volta real tem — é raio de 79 m no
papel e 6 g a 250 km/h. Com 30 m o simulador fica sem viés (−0,3 s) contra as
113 voltas reais, com erro médio de 1,4 s e correlação de 0,93.

## O que saiu

Modelos (janela de 128 passos = 256 m; erro nas unidades originais):

| rede | alvo | treino | validação | teste |
|---|---|---|---|---|
| geradora | posição lateral | 0,19 m | 0,56 m | 1,59 m |
| geradora | velocidade | 0,67 km/h | 1,93 km/h | 6,23 km/h |
| substituta | tempo por passo | 0,0006 s | 0,0013 s | 0,0022 s |

O condicionamento por desempenho funciona: pedindo à geradora a pilotagem de
perda 0,0 s ela responde 199 km/h de mediana; pedindo perda 0,5 s, 134 km/h — e
a linha se desloca 3,4 m em média. Se ela tivesse aprendido a média das voltas,
as duas respostas seriam iguais.

Simulador de tempo de volta, contra as 113 voltas reais: viés **−0,22 s**, erro
médio **1,36 s**, correlação **0,93**.

Algoritmo evolutivo (361 pontos de controle, 100 indivíduos, parada por
estagnação na geração 163):

| trajetória | tempo simulado |
|---|---|
| melhor volta real do treino | 85,095 s (medida: 85,300 s) |
| a mesma, dentro da representação do otimizador | 87,213 s |
| melhores trechos costurados (a "volta ideal" como trajetória) | 92,754 s |
| **traçado otimizado** | **85,862 s** |

Duas leituras, e as duas importam:

**O otimizador ganha 1,35 s sobre a linha de base na mesma representação**, e
termina 0,77 s atrás da linha real do piloto — dentro do erro do próprio
simulador (1,36 s). A conclusão honesta é que **a melhor volta do piloto já está
no ótimo deste modelo**: não há traçado alternativo que o modelo consiga apontar
como mais rápido. O que sobra para ganhar não está na linha, está na execução —
que é o que a comparação por microsetor mede.

**Costurar os melhores microsetores não produz a melhor trajetória.** A "volta
ideal" do enunciado é 1,25 s mais rápida que a melhor volta *no tempo*, e a
trajetória correspondente é 7,7 s **mais lenta**: as transições entre trechos de
voltas diferentes custam mais do que os trechos ganham. É exatamente por isso
que o algoritmo evolutivo existe no desenho.

### Gráficos de comparação

`python -m ml.scripts.plot_comparison` põe as três trajetórias lado a lado —
volta real, volta prevista pela LSTM e traçado otimizado — no mapa XY de
Interlagos com recortes ampliados nas curvas em que mais divergem, mais os
perfis de velocidade e posição lateral, o afastamento em metros e a diferença de
tempo por microsetor. As três passam pelo **mesmo simulador**, senão a
comparação misturaria tempo medido, previsto e simulado.

Na mesma física, contra a melhor volta real (84,848 s medidos, 85,525 s
simulados): a volta prevista fica +3,44 s e o traçado otimizado +0,34 s.

## Limitações conhecidas

- **Um piloto só.** O que o sistema aprende é variação entre voltas do mesmo
  piloto, não entre estilos.
- **Custo de representação.** Uma trajetória expressa em pontos de controle
  perde ~2 s contra a mesma trajetória ponto a ponto (medido com 361 genes;
  com 173, ~3,5 s). É o piso do que o otimizador pode alcançar, e por isso o
  resultado é reportado nas duas escalas.
- **O simulador é quase-estacionário.** Sem transferência de carga, sem mapa de
  motor por marcha, sem degradação de pneu. Serve para ordenar trajetórias
  (correlação 0,93), não para prever tempo absoluto.
- **Recompensa de velocidade de saída desligada por padrão.** Ela existe em
  `FitnessWeights.exit_speed`, mas o termo de tempo de volta já a contabiliza;
  ligada junto, conta o mesmo ganho duas vezes.

## Como rodar

Da pasta `backend/`, com a venv de análise (o PyTorch não entra no backend
empacotado — veja `ml/requirements.txt`):

```bash
python -m ml.scripts.build_inventory
```

```bash
python -m ml.scripts.build_lap_store
```

```bash
python -m ml.scripts.fit_envelope
```

```bash
python -m ml.scripts.train_models --epochs 40
```

```bash
python -m ml.scripts.optimize_line --generations 120
```

```bash
python -m ml.scripts.compare_lap
```

Os dois primeiros varrem os 11 GB e levam ~3 e ~1,5 minutos; depois deles nada
mais abre um `player.jsonl`. Tudo é escrito em `data/ml/` (fora do
versionamento).

## Testes

```bash
python -m unittest tests.test_ml_pipeline
```

40 testes, nenhum dependendo das gravações nem do cache de geometria — os dois
estão fora do versionamento. A pista usada é um círculo sintético, onde toda
grandeza que o pipeline calcula tem valor fechado conhecido: o comprimento de
uma trajetória deslocada de `L` é `2π(R+L)`, a curvatura dela é `−1/(R+L)`, e é
contra isso que os módulos são verificados.
