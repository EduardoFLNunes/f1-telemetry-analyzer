# Sessão rotulada e detector da IA (pedido 13, ADR 0014 e 0015)

Datas: 2026-10-04. Branch: `etapa/detector-ia`.

> **Nota de 05/10/2026 sobre os JSONs deste pedido (pedidos 19 e 20).** Os campos `tempo_s` de `docs/handoff/2026-10-04_detector-ia_resultados.json` e de `data/ml/origem/detector_aplicar.json` são o `duration_s` do inventário, e não o tempo de volta. Os JSONs ficam como foram gravados. Os tempos oficiais estão no store v2 (`lap_time_s`). Ver a errata na seção 2.

## 1. A sessão rotulada

- **Pista e carro:** Interlagos, com o carro `rss_formula_rss_3_v6_2026`. Esse valor aparece no `metadata.json` de todas as gravações da sessão (campo novo do pedido 12) e é o mesmo carro das sessões antigas que o registravam.
- **Equipamento:** volante RS50 e pedais com célula de carga, em uso desde 01/10/2026 (ADR 0015).
- **Gravação:** feita com o app aberto a partir do repositório (`develop`), com o backend em Python, porque o executável empacotado ainda não grava o indicador. O coach ficou calado durante toda a sessão: o modelo do repositório, `data/reference_models/vhe_interlagos.json`, foi renomeado antes e voltou ao nome original no fim, com o mesmo hash (`9d08d705…`).
- **Sessões desde 01/10:** só esta. Ela ficou em sete arquivos em `data/recordings`, porque a gravação se divide quando o jogo pausa ou vai ao menu:

| arquivo | o que tem |
|---|---|
| `2026-10-04_02-24-04` | parte 1 (voltas 1 a 14 do jogo); depois do reinício da sessão do jogo, voltas 1 a 6 da parte 2 |
| `2026-10-04_03-21-52` | parte 2, voltas 6 a 13 |
| `2026-10-04_03-35-57`, `03-36-35`, `03-40-32` | carro parado (pausa na volta 13) |
| `2026-10-04_03-42-10` | parte 2, voltas 13 a 33 |
| `2026-10-04_04-22-39` | parte 2, voltas 33 e 34 (box). A gravação foi parada pela API depois do fim da sessão |

- **O que foi pilotado** (anotações do Eduardo, em `docs/experimentos/2026-10-04_sessao_rotulada_anotacoes.csv`):

| parte | voltas | quem |
|---|---|---|
| 1 | 1 a 3 | piloto (a 1 sai do box) |
| 1 | 4 e 7 | volta ao box pelo menu e saída com a IA |
| 1 | 5, 6, 11 a 14 | IA |
| 1 | 8 | IA nos setores 1 e 2, piloto no setor 3 |
| 1 | 9 e 10 | piloto, com erros (na 9 o carro voltou ao box) |
| 2 | 1 a 20 | piloto, sem box (várias voltas com erros) |
| 2 | 21 | piloto entra no box, a IA sai |
| 2 | 22 a 31 | IA (nas 27 e 28 ela mesma parou no box) |
| 2 | 32 | IA até o setor 3, depois o piloto |
| 2 | 33 e 34 | piloto (a 34 entra no box) |

São 53 voltas no inventário, das quais 28 são válidas. Muitas voltas do piloto têm erros e não passam nos portões de qualidade.

### O indicador do jogo contra as anotações

O indicador `isAIControlled` **liga quando a IA assume, mas não desliga quando o piloto retoma**. Depois do primeiro Ctrl+C ele fica em "IA" até a sessão do jogo ser reiniciada. Ele só sai de "IA" por uma amostra, às vezes, com o carro parado.

| volta | anotação | indicador |
|---|---|---|
| parte 1, volta 8 | misturada | ia |
| parte 1, volta 9 | humano | misturada (piscadas de uma amostra com o carro parado) |
| parte 1, volta 10 | humano | ia |
| parte 2, volta 32 | misturada | ia |
| parte 2, volta 33 | humano | ia / misturada |

Todas as outras voltas concordam. Por isso **o rótulo da sessão vem das anotações**. Na coluna `origem_fonte`, a volta fica `indicador` quando o indicador concorda com a anotação e `anotacao` quando não concorda. O indicador continua útil de uma forma: em "piloto" a sessão toda, ele prova que a IA nunca foi ligada.

## 2. A variação do piloto e a da IA

Contam só as voltas limpas da sessão rotulada (válidas, únicas, com o relógio conferido e sem box): 11 voltas suas e 13 da IA. As janelas são as da Fase 2b.

| | suas voltas (equipamento atual) | IA |
|---|---:|---:|
| Bico de Pato (2.590 a 3.080 m), tempo médio | 13,54 s | 11,43 s |
| desvio entre voltas no Bico de Pato | **0,91 s** (robusto 0,62 s) | **0,012 s** |
| o mesmo, sem a tendência da sessão (diferenças sucessivas) | 0,82 s | 0,010 s |
| dispersão do ponto de frenagem (mediana das janelas) | 14,7 m | 1,0 m |
| dispersão da lateral no ápice (mediana das janelas) | 1,84 m | 0,04 m |
| tempo de volta: média e desvio | 93,58 s ± 2,40 s | 84,99 s ± 0,13 s |
| melhor volta válida e completa | 89,379 s (parte 2, volta 5) | 84,816 s (parte 2, volta 25) |

> **Errata de 05/10/2026 (pedidos 19 e 20).** As linhas "tempo de volta: média e desvio" e "melhor volta válida e completa" vieram do `duration_s` do inventário, que não é o tempo de volta. Os tempos oficiais (`lap_time_s` do store v2), nas mesmas 11 voltas suas e 13 da IA, são:
>
> | | suas voltas | IA |
> |---|---:|---:|
> | tempo de volta: média e desvio | 93,60 s ± 2,40 s | 85,02 s ± 0,13 s |
> | melhor volta válida e completa | 89,390 s (`2026-10-04_02-24-04#0018`, parte 2, volta 5) | 84,829 s (`2026-10-04_03-42-10#0013`, parte 2, **volta 26**) |
>
> - **A melhor volta da IA é a 26 (`#0013`), não a 25.** Pelo `duration_s`, as voltas 25 e 26 empatavam em 84,816 s; pelo tempo oficial, a 25 (`#0012`) tem 84,835 s.
> - **As faixas com uma casa decimal mais abaixo** (seções 3 e 4) também vieram do `duration_s`, mas coincidem com o oficial nessa precisão.
> - **O resto da seção não muda.**

Nas janelas da Fase 2b, a sua dispersão da frenagem vai de 7,0 m (Bico de Pato) a 50,3 m (Ferradura), e a do ápice vai de 1,1 m a 7,9 m. No Pinheirinho, menos de 3 das suas voltas tiveram início de frenagem detectado.

**A sua variação é de outra ordem que a usada até agora.** O cálculo do experimento usava de 14 a 35 ms no Bico de Pato, números que vinham das sessões de 09/08 e 20/06, ou seja, da IA (ADR 0014). A sua variação, com o equipamento novo e no começo da curva de aprendizado (ADR 0015), é cerca de 0,8 a 0,9 s: umas 60 vezes maior.

### Tamanho do experimento controlado

Voltas por condição para detectar o efeito com 80 % de chance, no desenho em blocos de 4 do protocolo. A fórmula é a do protocolo; usando o próprio plano (`make_plan`) analisado por `estimate_effects`, o poder simulado dá de 76 a 79 % no efeito previsto.

| efeito | efeito principal (frenagem ou linha) | uma condição contra outra |
|---|---:|---:|
| 15 ms | 23.448 | 46.895 |
| 30 ms | 5.862 | 11.724 |
| 50 ms | 2.111 | 4.221 |

O desvio usado é 0,82 s, sem a tendência da sessão. Com o desvio simples (0,91 s), os números crescem cerca de 22 %.

Ao contrário: com as 8 voltas por condição do protocolo, o experimento só detecta um efeito principal a partir de 0,81 s, ou uma diferença entre duas condições a partir de 1,15 s. Com 32 voltas por condição, a partir de 0,41 s e 0,57 s.

**Com a variação de hoje, o experimento não mede efeitos de 15 a 50 ms.** Isso combina com o ADR 0015: o experimento espera a curva de aprendizado estabilizar. Quando a mediana do tempo de volta das últimas 3 sessões variar menos de 0,5 s, a variação no Bico de Pato deve ser medida de novo e o cálculo refeito. Não gerei um plano novo, porque nenhum tamanho viável chega lá hoje.

## 3. O detector (registrado antes de olhar as voltas antigas)

### Como funciona

As voltas antigas não têm indicador. A origem delas sai de três sinais, calibrados **só** com as voltas limpas da sessão rotulada (válidas, únicas, com o relógio conferido e sem box): 13 voltas da IA, 11 do piloto e 2 misturadas (a 8 da parte 1 e a 32 da parte 2).

1. **Linha.** A referência é a mediana, ponto a ponto da grade de 2 m, da lateral das 13 voltas da IA. Em cada um dos 60 microsetores mede-se a distância lateral mediana até ela.
   - **Microsetores que contam:** só aqueles em que a própria IA se repete. São 40 dos 60, onde as 13 voltas da IA ficam a até 0,25 m da referência feita sem cada uma delas. Ficam fora as retas e a região do box, onde a IA varia até 2,5 m e a linha não diz nada. Os que contam são 3–10, 16–23, 26–28, 30–47 e 49–51.
   - **Estado de cada microsetor:** até 0,25 m, **parece IA**; a partir de 0,30 m, **parece piloto**; entre os dois, **indefinido**.
2. **Frenagem.** São 8 zonas em que a IA repete o início de frenagem a até 4 m em pelo menos 90 % das voltas: 126, 248, 1.206, 2.016, 2.200, 2.360, 2.622 e 3.122 m. Para cada volta, mede-se a distância do início de frenagem mais próximo de cada zona, limitada a 60 m, e toma-se a mediana entre as zonas.
3. **Tempo de volta.** Abaixo de 88 s, o tempo vota IA ou misturada. Acima de 92 s, vota piloto ou misturada. Entre 88 e 92 s ele não vota, e a linha decide.

### Regra da volta

Pela linha, contando **trechos**, isto é, sequências de microsetores que contam:

| volta | quando |
|---|---|
| `ia` | todos os 40 microsetores parecem IA |
| `humano` | nenhum trecho de 3 ou mais microsetores seguidos parece IA, e há um trecho de 2 ou mais que parece piloto |
| `misturada` | há um trecho de 3 ou mais que parece IA e um de 2 ou mais que parece piloto |
| `desconhecida` | qualquer outro caso |

Os trechos são necessários pelo que se mediu. As voltas do piloto passam às vezes a poucos centímetros da linha da IA, mas em no máximo 2 microsetores seguidos (de 0 a 4 microsetores na volta). Já a IA, quando pilota, ocupa trechos de 20 a 40 microsetores. Se um único microsetor bastasse, 8 das 11 voltas do piloto virariam `misturada`.

A volta recebe o rótulo só se os sinais concordarem:

- **frenagem:** uma volta `ia` precisa de mediana até 4 m, e uma volta `humano` precisa de mediana a partir de 8 m;
- **tempo:** o tempo tem de votar no mesmo rótulo da linha;
- **caso contrário:** a volta fica `desconhecida`, com o motivo registrado.

Voltas com passagem pelo box ficam sem rótulo (motivo `box`). Elas saem da pista e ficam abaixo de 90 km/h perto da linha de chegada.

Os limites estão em `backend/ml/data/ai_detector.py` (`LIMITS`). O comando `python -m ml.scripts.detector_ia aplicar` para se os microsetores e as zonas registrados não baterem com os que a sessão rotulada dá.

### Quanto acerta na sessão rotulada

Cada volta da IA é medida contra a referência feita sem ela.

| origem | voltas | acertos | desconhecidas | erradas |
|---|---:|---:|---:|---:|
| ia | 13 | 13 | 0 | 0 |
| humano | 11 | 11 | 0 | 0 |
| misturada | 2 | 2 | 0 | 0 |

- **Fora da amostra:** calibrando só com a parte 2 (8 voltas da IA) e testando na parte 1, o detector acerta 5 de 5 voltas da IA, 3 de 3 do piloto e a misturada.
- **Margem:** as voltas da IA têm mediana de frenagem de 0 a 2 m; as do piloto, de 44 a 60 m.
- **Tempo:** as voltas da IA fecham em 84,8 a 85,2 s, e as do piloto em 89,4 a 98,8 s. As duas misturadas (86,1 s e 85,6 s) são rápidas, porque o piloto fez só o fim da volta. Elas recebem o rótulo porque o tempo rápido é compatível com `misturada`.

Os limites cumprem a meta do pedido: pelo menos 95 % de acerto em cada origem. A amostra, porém, é de um dia, um carro e uma configuração da IA. A prova de verdade vem nas voltas antigas, conferidas abaixo com as datas lembradas e com as sessões mais variáveis do pedido 12.

## 4. As voltas antigas: parei aqui

A regra registrada foi aplicada, depois do commit `0fe5471a`, às 688 voltas antigas válidas e únicas das duas pastas:

| resultado | voltas |
|---|---:|
| box (ficam sem rótulo) | 136 |
| linha indefinida | 467 |
| linha diz `ia`, frenagem discorda | 10 |
| rotuladas | **75**: 35 `ia`, 8 `humano`, 32 `misturada` |

**89 % das voltas antigas ficaram `desconhecida`.** Pelo pedido, quando a separação não é clara, eu não forço: relato as distribuições e paro. Por isso nada foi promovido. As voltas antigas continuam com `origem = desconhecida` no inventário novo, e o que o detector disse está só nas colunas `origem_detector`, `motivo_detector` e `linha_detector`. Também não fiz o merge.

### Por que a regra se absteve

A minha primeira hipótese era que a IA antiga andasse por outra linha. As distribuições mostram o contrário:

- **Linha:** nas 552 voltas antigas sem box, a distância lateral mediana até a linha da IA de hoje, nos 40 microsetores que contam, é **0,031 m** (p10 0,023 m, p90 0,044 m). É o mesmo que as voltas da IA de hoje têm entre si (cerca de 0,03 m), e muito longe das suas voltas de hoje (1,1 a 2,1 m).
- **Sessões de 07/08, 08/08 e 09/08:** todas as voltas ficam a 2,5–4,4 cm da IA de hoje e a 0,5–2 cm das outras voltas da mesma sessão. Fecham em 85,8 a 86,3 s (medianas por sessão) e ficam perto da IA em 39 dos 40 microsetores.
- **O que falha:**
  - o **microsetor 41** (2.962 a 3.034 m) fica a mais de 0,25 m da IA de hoje em 469 das 534 voltas antigas rápidas. A IA de hoje se repete ali a até 0,024 m;
  - nas zonas de frenagem de **126 m e 1.206 m**, as voltas antigas freiam a 8 m e 6 m da IA de hoje (medianas). Por isso a mediana da volta fica em 2 a 5 m, em torno do limite de 4 m.

Ou seja, essas voltas antigas se comportam como a IA, a 3 cm da linha dela. Mas num lugar da pista e em duas freadas a IA daquela época fazia um pouco diferente, talvez por acerto, combustível, pneu ou configuração da IA. A regra registrada exige os 40 microsetores e frenagem até 4 m, então ela se abstém. Afrouxá-la agora, depois de ver as voltas antigas, seria forçar.

### O que o detector disse (registrado, não promovido)

| grupo | voltas | ia | humano | misturada | desconhecida (box) |
|---|---:|---:|---:|---:|---:|
| datas que você lembra (14/06 a 20/06 e 09/08) | 428 | 11 | 0 | 29 | 388 (86) |
| outras datas | 260 | 24 | 8 | 3 | 225 (50) |

As 4 sessões que mais variavam no pedido 12:

| sessão | ia | humano | misturada | desconhecida (box) |
|---|---:|---:|---:|---:|
| `2026-06-19_23-24-46` | 0 | 0 | 3 | 1 (0) |
| `2026-06-20_13-13-02` | 0 | 0 | 22 | 17 (8) |
| `2026-08-16_03-30-14` | 3 | 3 | 1 | 0 (0) |
| `2026-08-19_20-58-36` | 2 | 5 | 0 | 3 (3) |

O que bate com o que você lembra e com o pedido 12:

- As 8 voltas `humano` estão todas nas sessões variáveis de 16/08 e 19/08. Nenhuma está nas datas que você lembra como IA.
- As `misturada` se concentram em 18/06, 19/06 e 20/06, datas em que você lembra de alternar.

O que não bate:

- **07/08 e 08/08**, que você não lembra como IA, são iguais às de 09/08 em todas as medidas: 2,5–3,1 cm da IA de hoje, 39 de 40 microsetores e 85,8–86,0 s. O detector se absteve nelas pelo mesmo motivo, mas as distribuições apontam IA.
- **`2026-08-19_22-23-14`**, também fora das datas lembradas, tem 14 voltas `ia`. É dela a volta de referência do modelo de ensaio do pedido 11.

Quantas voltas antigas são suas: pelo detector, 8 com certeza e talvez parte das 32 misturadas. Pelo ADR 0015, elas são do equipamento anterior e não entram nos números sobre você de qualquer jeito.

### Para decidir

1. **Deixar como está.** As voltas antigas ficam `desconhecida`; para o piloto valem só as voltas novas (ADR 0015); a referência da IA é a sessão de hoje. É o que o inventário novo tem agora.
2. **Promover os 75 rótulos atuais** (`python -m ml.scripts.detector_ia aplicar --promover`). As 35 `ia` são as mais sólidas, porque batem com a IA de hoje em todos os 40 microsetores e nas freadas. As `misturada` de 20/06 são as mais incertas.
3. **Uma regra nova para as voltas antigas**, por exemplo aceitando 1 microsetor fora e frenagem até 8 m. Como seria desenhada depois de ver as voltas antigas, precisaria ser validada numa sessão rotulada nova antes de ser aplicada.

## O que falta

- A sua decisão sobre as voltas antigas (acima) e sobre o merge desta branch.
- **Medir de novo a variação no Bico de Pato** quando a curva de aprendizado estabilizar (ADR 0015), e refazer o tamanho do experimento.
- **Reempacotar o app instalado** com o gravador novo. Lembrando que o indicador do jogo só prova que a IA nunca foi ligada; depois do primeiro Ctrl+C, quem pilota sai da linha e das anotações.
