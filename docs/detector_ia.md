# Sessão rotulada e detector da IA (pedido 13, ADR 0014 e 0015)

Datas: 2026-10-04. Branch: `etapa/detector-ia`.

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

*(preenchido depois de calcular)*

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

## 4. As voltas antigas

*(preenchido depois de aplicar)*
