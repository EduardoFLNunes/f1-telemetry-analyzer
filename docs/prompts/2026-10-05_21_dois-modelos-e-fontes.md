# Pedido 21 — Registrar a decisão: dois modelos, a IA como uma fonte, fontes externas

**De:** Eduardo (o plano é meu). **Data:** 05/10/2026.
**Tipo:** só documentação. Nenhum código, nenhum modelo treinado, nenhum dado regravado.

## Contexto

Na conversa de 05/10, deixei claro o objetivo do TCC:

1. **Modelo 1, previsão:** um modelo treinado que encontra a melhor volta possível com este carro em Interlagos.
2. **Modelo 2, correção:** um modelo que mede o erro do piloto e o ensina a chegar mais perto dessa volta.

As voltas da IA do Assetto Corsa foram gravadas para testar se o software coletava e guardava os dados certo, e não para treinar o piloto. Elas são úteis, porque são limpas e consistentes, e podem entrar no treino. Mas não podem ser a única fonte, e nada garante que a volta da IA seja a melhor volta possível. Precisa haver outras fontes, inclusive dados de fora do jogo.

Fatos que já estão no repositório e sustentam a decisão (confira e cite no ADR):

- as 552 voltas antigas passam, na mediana, a 0,031 m da linha da IA de hoje (`docs/detector_ia.md`);
- a LSTM geradora erra 0,53 m nas voltas abaixo de 88 s e 2,90 m nas acima, e o erro por volta acompanha o tempo da volta (`docs/auditoria_ml.md`);
- o traçado otimizado ficou mais lento que 43 voltas gravadas, no mesmo simulador (ADR 0009);
- existe um importador FastF1 (`backend/core/external_references/`), usado hoje só como contexto por curva, fora de qualquer treino.

## Parte A — ADR 0018

Crie `docs/decisoes/0018-dois-modelos-e-fontes-de-treino.md`, no formato dos outros (Status, Data, Decisor, Contexto, Decisão, Consequências). Decisor: Eduardo. Status: aceita.

A decisão deve dizer, nesta ordem:

1. **O objetivo são dois modelos.**
   - Modelo 1, previsão: LSTM geradora + busca evolutiva + juiz do tempo.
   - Modelo 2, correção: peças B, C e D.
   - A peça E avalia os dois.
   - O juiz do tempo é compartilhado: hoje o simulador quase-estacionário, depois o modelo do carro (ADR 0017).
2. **A volta da IA é uma fonte de treino e a referência provisória do coach, não o alvo.** O ADR 0016 continua valendo para o coach nesta fase.
3. **O Modelo 1 não treina só com voltas da IA.** As fontes são:
   - voltas `humano` com equipamento `atual` (ADR 0015);
   - voltas `ia` rotuladas;
   - dados externos. No caso da F1 real via FastF1, só a forma da linha entra, nunca velocidade ou ponto de frenagem de outro carro. O erro de alinhamento à geometria oficial é medido e registrado.
4. **Quando a volta do Modelo 1 vira referência do coach:** só depois de passar na régua do ADR 0006 com o juiz novo (M1) e de ser mais rápida que as voltas reais no mesmo juiz. O ADR 0009 continua valendo até lá.

Nas consequências, liste os três itens novos de backlog da Parte B.

## Parte B — Índice e backlog

1. Em `docs/decisoes/README.md`, acrescente a linha do 0018 e, na linha do 0016, o status "aceita; refina 0012; enquadrada por 0018".
2. Em `docs/backlog.md`, acrescente três linhas:
   - **Dados externos no treino do Modelo 1:** importar a forma da linha da F1 real (FastF1), alinhar à geometria oficial e medir o erro de alinhamento.
   - **Retreinar a LSTM geradora com as três fontes:** testar na régua do ADR 0006.
   - **Busca evolutiva de novo:** recomeçar das voltas reais mais rápidas, só depois da M1 aprovada.

## Regras

- Branch `etapa/adr-0018-dois-modelos`, commit, merge em `develop`. Sem push.
- Não mexa no app instalado nem em arquivos do jogo.
- Uma sessão de implementação por vez (ADR 0008).
- Relatório completo em `docs/handoff/2026-10-05_21_dois-modelos_relatorio.md`, como manda o CLAUDE.md. Inclua o texto final do ADR 0018 e os commits.
- Se algum fato do contexto não bater com o repositório, pare e registre no relatório em vez de ajustar o texto.
