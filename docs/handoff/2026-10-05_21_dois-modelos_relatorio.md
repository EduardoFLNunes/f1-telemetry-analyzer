# Relatório do pedido 21: dois modelos, a IA como uma fonte, fontes externas

- **Pedido:** `docs/prompts/2026-10-05_21_dois-modelos-e-fontes.md`
- **Branch:** `etapa/adr-0018-dois-modelos`, com merge em `develop`
- **Commits e merge:**
  - `a93ae916` docs: ADR 0018 (dois modelos e fontes de treino), indice, backlog e pedido 21
  - `2824e502` Merge etapa/adr-0018-dois-modelos (ADR 0018: dois modelos e fontes de treino)
  - o commit deste relatório, com o patch: "Relatório do pedido 21: ADR 0018, dois modelos e fontes de treino"
- **Arquivos de handoff:**
  - `docs/handoff/2026-10-05_21_dois-modelos_relatorio.md` (este)
  - `docs/handoff/2026-10-05_21_dois-modelos.patch` (de `b6ff9b38` até o merge `2824e502`; sha256 `c7b98f1a…85ddb57`)

Nada foi enviado ao remoto. O app instalado e os arquivos do jogo não foram tocados. O pedido é só documentação: nenhum código, modelo, store ou critério mudou. Por isso a suíte de testes não foi rodada.

## Conferência dos fatos do contexto

Os quatro fatos batem com o repositório. Não precisei parar.

| fato do pedido | onde está | o que o repositório diz | bate? |
|---|---|---|---|
| 552 voltas antigas a 0,031 m da linha da IA de hoje, na mediana | `docs/detector_ia.md`, linha 166 | 552 voltas antigas **sem box**, nos **40 microsetores que contam**: 0,031 m (p10 0,023 m, p90 0,044 m) | sim |
| LSTM geradora: 0,53 m abaixo de 88 s e 2,90 m acima; o erro acompanha o tempo | `docs/auditoria_ml.md`, seção 3 (linhas 267 a 280) e 8.6 (linha 649) | MAE lateral no teste: **0,528 m** abaixo de 88 s e **2,898 m** acima; correlação de **0,914** entre erro por volta e tempo de volta | sim (o pedido arredondou; no ADR usei os números da fonte) |
| Traçado otimizado mais lento que 43 voltas gravadas, no mesmo simulador | ADR 0009, tabela | 85,109 s contra 84,822 s; **43 das 122** voltas do store atual simulam mais rápido (40 das 113 no store anterior) | sim |
| Importador FastF1 em `backend/core/external_references/`, só contexto por curva, fora de treino | código | Só `backend/core/assisted_analysis/service.py` o usa, e só quando a análise pede referência externa. Ele devolve `macroCornerContext` por curva, com `speedComparison: relative_profile_shape` e `absoluteTimeComparison: disabled`. Nenhum arquivo de `backend/ml/` importa o módulo ou o FastF1 | sim |

## Parte A: ADR 0018

Criado em `docs/decisoes/0018-dois-modelos-e-fontes-de-treino.md`, no formato dos outros. A decisão segue a ordem do pedido (1 a 4), e as consequências listam os três itens novos do backlog. Acrescentei ao fim das consequências os ADRs que continuam valendo (0016, 0009 e 0004), todos já citados pelo pedido ou pelo ADR 0017.

Texto final:

```markdown
# 0018 — Dois modelos, previsão e correção; a volta da IA é uma fonte de treino, não o alvo

- **Status:** aceita
- **Data:** 2026-10-05
- **Decisor:** Eduardo

## Contexto

Na conversa de 05/10, o Eduardo deixou claro o objetivo do TCC:

1. **Modelo 1, previsão:** um modelo treinado que encontra a melhor volta possível com este carro em Interlagos.
2. **Modelo 2, correção:** um modelo que mede o erro do piloto e o ensina a chegar mais perto dessa volta.

As voltas da IA do Assetto Corsa foram gravadas para testar se o software coletava e guardava os dados certo, e não para treinar o piloto. Elas são úteis, porque são limpas e consistentes, e podem entrar no treino. Mas não podem ser a única fonte, e nada garante que a volta da IA seja a melhor volta possível.

Quatro fatos já registrados no repositório sustentam a decisão:

- **As voltas antigas são, na prática, a linha da IA.** As 552 voltas antigas sem box passam, na mediana, a **0,031 m** da linha da IA de hoje, nos 40 microsetores que contam (p10 0,023 m, p90 0,044 m). É o mesmo que as voltas da IA de hoje têm entre si (`docs/detector_ia.md`).
- **A LSTM geradora acerta o regime rápido e erra no lento.** No teste, ela erra **0,528 m** de lateral nas voltas abaixo de 88 s e **2,898 m** nas acima, e o erro por volta correlaciona 0,914 com o tempo da volta (`docs/auditoria_ml.md`, seção 3). A melhor volta do piloto na sessão rotulada de 04/10 é 89,390 s (ADR 0016), no regime em que a rede erra. O backlog já registra que as LSTMs aprenderam sobretudo voltas da IA.
- **Nem o otimizador garantiu a melhor volta.** O traçado otimizado simula em 85,109 s, e 43 das 122 voltas gravadas simulam mais rápido no mesmo simulador (ADR 0009).
- **Já existe um importador de dados de fora do jogo.** O importador FastF1 (`backend/core/external_references/`) é usado hoje só como contexto por curva na análise assistida: compara a forma do perfil de velocidade, sem tempo absoluto. Nenhum código de `backend/ml/` o usa, e ele não entra em nenhum treino.

## Decisão

### 1. O objetivo são dois modelos

| | Modelo 1, previsão | Modelo 2, correção |
|---|---|---|
| O que faz | encontra a melhor volta possível com este carro em Interlagos | mede o erro do piloto e o ensina a chegar mais perto dessa volta |
| Peças | LSTM geradora + busca evolutiva + juiz do tempo | peças B, C e D |

- **A peça E avalia os dois.**
- **O juiz do tempo é compartilhado.** Hoje é o simulador quase-estacionário (`backend/ml/optimization/lap_time_model.py`); depois, o modelo do carro (ADR 0017).

### 2. A volta da IA é uma fonte de treino e a referência provisória do coach, não o alvo

- O alvo do Modelo 1 é a melhor volta possível. A volta da IA é uma das fontes para chegar lá.
- O ADR 0016 continua valendo para o coach nesta fase: a `volta_ia` é a referência padrão e a `minha_melhor` é a outra.

### 3. O Modelo 1 não treina só com voltas da IA

As fontes são:

- voltas `humano` com equipamento `atual` (ADR 0015);
- voltas `ia` rotuladas (ADR 0014);
- dados externos.

No caso da F1 real via FastF1, **só a forma da linha entra**, nunca velocidade ou ponto de frenagem de outro carro. O erro de alinhamento à geometria oficial (ADR 0002) é medido e registrado.

### 4. Quando a volta do Modelo 1 vira referência do coach

Só depois de:

- passar na régua do ADR 0006 com o juiz novo (a M1 do ADR 0017);
- ser mais rápida que as voltas reais no mesmo juiz.

O ADR 0009 continua valendo até lá.

## Consequências

Três itens novos no backlog:

- **Dados externos no treino do Modelo 1:** importar a forma da linha da F1 real (FastF1), alinhar à geometria oficial e medir o erro de alinhamento.
- **Retreinar a LSTM geradora com as três fontes:** testar na régua do ADR 0006.
- **Busca evolutiva de novo:** recomeçar das voltas reais mais rápidas, só depois da M1 aprovada.

Continuam valendo:

- o ADR 0016, para a referência do coach nesta fase;
- o ADR 0009, até a volta do Modelo 1 cumprir o item 4;
- o ADR 0004, até a M1 passar na régua (ADR 0017).
```

## Parte B: índice e backlog

**`docs/decisoes/README.md`:**

- linha do 0016: status agora é "aceita; refina 0012; enquadrada por 0018";
- linha nova: `| [0018](0018-dois-modelos-e-fontes-de-treino.md) | Dois modelos, previsão e correção; a volta da IA é uma fonte de treino, não o alvo | aceita |`.

O status dentro do próprio arquivo do 0016 ficou como estava ("aceita; refina o ADR 0012"). O pedido só falava do índice, e é o mesmo que já acontece com o 0012 e o 0002, cujo status no índice é mais completo que no arquivo.

**`docs/backlog.md`:** três linhas novas no fim da tabela. O texto do item é o do pedido. As colunas "Impacto" e "Quando" são minhas, tiradas do ADR 0018 e dos ADRs 0009 e 0017. Vale o Cowork revisar.

| Item | Origem | Impacto | Quando |
|---|---|---|---|
| **Dados externos no treino do Modelo 1:** importar a forma da linha da F1 real (FastF1), alinhar à geometria oficial e medir o erro de alinhamento | ADR 0018; pedido 21 (05/10) | Terceira fonte do Modelo 1. Só a forma da linha entra, nunca velocidade ou ponto de frenagem de outro carro. Hoje o importador só dá contexto por curva e não entra em nenhum treino | A definir |
| **Retreinar a LSTM geradora com as três fontes:** testar na régua do ADR 0006 | ADR 0018; pedido 21 (05/10) | Hoje a rede erra 0,528 m de lateral abaixo de 88 s e 2,898 m acima, onde está o piloto. As três fontes são voltas `humano` com equipamento `atual`, voltas `ia` rotuladas e dados externos | Depois dos dados externos no treino |
| **Busca evolutiva de novo:** recomeçar das voltas reais mais rápidas, só depois da M1 aprovada | ADR 0018; ADR 0009, item 4 | Gera a volta do Modelo 1. Ela só vira referência do coach quando passar na régua do ADR 0006 com o juiz novo e for mais rápida que as voltas reais no mesmo juiz | Depois da M1 aprovada (ADR 0017) |

## Pontos para o Cowork e decisões do Eduardo

Nada disto bloqueou o pedido nem mudou o texto do plano. São coisas que encontrei ao conferir o repositório:

1. **A peça E não tem definição anterior no repositório.** O ADR 0018 é o primeiro arquivo que a cita. A peça C também não é descrita em nenhum lugar: o ADR 0017 só diz que ela "continua por último". As peças vêm da "revisão da arquitetura (03/10)", citada como origem no backlog, que não é um arquivo do repositório. Talvez valha registrar as peças A a E num documento (por exemplo, `docs/arquitetura_ml.md`).
2. **O item antigo da peça A no backlog se sobrepõe ao item novo de retreino.** A linha "Peça A: retreinar LSTMs, envelope e traçado com voltas rotuladas…" marca o retreino para "depois que o piloto estabilizar (ADR 0015), com voltas humanas". O item novo manda retreinar com as três fontes. Não mexi na linha antiga: falta decidir se elas viram uma linha só e qual "Quando" vale.
3. **Voltas `ia` antigas no treino.** O ADR 0018 aceita "voltas `ia` rotuladas" sem restrição de data. Entre as voltas antigas, o detector rotulou 75 como `ia`. A IA de agosto fazia diferente no microsetor 41 e freava 6 a 8 m longe em duas zonas, e o ADR 0016 já tirou essas voltas da referência do coach. Falta decidir se elas entram no treino do Modelo 1 ou só as das sessões novas.
4. **Já existe uma volta FastF1 importada:** `data/external_references/fastf1__2024__Brazil__Q__NOR__32__093bbee0.json` (classificação de 2024, Norris, volta 32, 83,405 s). Ela tem 633 amostras, todas com `x` e `y` nas coordenadas do FastF1, e está marcada como `UNCALIBRATED`. A pasta está no `.gitignore`. É o ponto de partida natural do primeiro item novo do backlog: as posições existem, falta alinhá-las à geometria oficial.

## O que falta

Nada deste pedido. Os três itens novos estão no backlog e esperam pedido próprio.

`docs/handoff/2026-10-05_21_dois-modelos_relatorio.md`
