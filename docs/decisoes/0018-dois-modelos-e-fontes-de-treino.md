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

## Esclarecimento (05/10, pedido 22)

- **"Voltas `ia` rotuladas" (item 3 da decisão) são só as de sessões com rótulo pelo indicador do jogo ou por anotação** (ADR 0014): `origem_fonte` igual a `indicador`, `anotacao` ou `anotacao_sessao`, nunca `detector`.
- **As voltas antigas ficam fora do treino do Modelo 1.** Isso vale para as de origem `desconhecida`, inclusive as que o detector marcou sem promover: 75 voltas, sendo 35 `ia`, 8 `humano` e 32 `misturada` (`docs/detector_ia.md`).
- **Elas podem entrar depois num teste à parte**, treinando com e sem elas e comparando na régua do ADR 0006. O teste está no backlog.

**Refinado por [0019](0019-f1-tracado-de-referencia-2023-25.md)** (08/10): a F1 entra como traçado de referência único da época 2023–25.
