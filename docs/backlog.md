# Pendências do projeto

Lista viva de problemas conhecidos e tarefas adiadas, mantida pelo Claude (Cowork). Quando um item vira etapa, ganha um pedido em `docs/prompts/` e sai daqui ao ser concluído.

| Item | Origem | Impacto | Quando |
|---|---|---|---|
| Geometria única no runtime: a linha central crua do app tem dois trechos deslocados ~11 m (463–500 m e 751–807 m) | ADR 0002, etapa do coach (30/09) | Projeção ao vivo erra em ~30 de 19 802 amostras; a divisa entre os trechos 10 e 11 do coach cai na região | Antes de integrar o modelo à interface |
| Alvos do `optimal.json` ainda no mapeamento antigo (~14 m de deslocamento) | ADR 0009 | Coach ao vivo, enquanto usar esse arquivo | Resolvido quando o coach usar a volta de referência real (ADR 0012) |
| Horário gravado 3 h adiantado em relação ao relógio do PC (5 sessões, maio a agosto) | Fase 2c, ajustes (02/10) | Só a exibição da hora. Provável confusão entre UTC e o fuso de São Paulo (UTC−3) no gravador | Baixa prioridade; investigar junto com a próxima mudança no gravador |
| LSTMs, envelope e traçado otimizado não foram retreinados com as 122 voltas | Fase 1 | Referência e incerteza desatualizadas | Antes da Fase 3 |
| Simulador + corretor aprendido (proposta 1 do documento dos artigos) | ADR 0010 | Possível volta do simulador ao projeto | Depois do experimento controlado |
| `stash@{0}` "Organizacao das 3 visoes (descartada; refeita na sessao do mapa)", de 19/08 | Relatório de 02/10 | Nenhum | Decidir se apaga |
| Dois documentos antigos fora do git: `docs/integracao_ml_e_empacotamento.md` e `docs/phase16_dashboard_3_visoes.md` | Relatório de 30/09 | Nenhum | Decidir se commita |
| `develop`, `main` e as tags só existem no PC | Desde 30/09 | Sem backup remoto | Quando o Eduardo autorizar o push |
