# Pendências do projeto

Lista viva de problemas conhecidos e tarefas adiadas, mantida pelo Claude (Cowork). Quando um item vira etapa, ganha um pedido em `docs/prompts/` e sai daqui ao ser concluído.

| Item | Origem | Impacto | Quando |
|---|---|---|---|
| Geometria única no runtime: a linha central crua do app tem dois trechos deslocados ~11 m (463–500 m e 751–807 m) | ADR 0002, etapa do coach (30/09) | Projeção ao vivo erra em ~30 de 19 802 amostras | Em andamento: o coach migra primeiro (ADR 0013, pedido 11); depois mapa, painel e replay, cada um numa etapa |
| Alvos do `optimal.json` ainda no mapeamento antigo (~14 m de deslocamento) | ADR 0009 | Só o modo antigo do coach usa esse arquivo; o modo padrão da Parte C não usa | Some do caminho padrão com o merge do pedido 11 |
| Gravador: horário 3 h adiantado (provável UTC contra UTC−3) | Fase 2c, ajustes (02/10) | Só a exibição da hora. O registro do carro e da IA no controle foi para o pedido 12 | Baixa prioridade |
| Peça A: retreinar LSTMs, envelope e traçado com voltas rotuladas e criar a faixa de incerteza σ(s). Peça B, parte estatística: desvios contra a referência, sem prometer segundos | Fase 1; revisão da arquitetura (03/10) | Referência e incerteza desatualizadas; B ainda não existe | Pedido 13, depois da rotulagem (ADR 0014) |
| Simulador + corretor aprendido (proposta 1 do documento dos artigos) | ADR 0010 | Possível volta do simulador ao projeto | Depois do experimento controlado |
| `stash@{0}` "Organizacao das 3 visoes (descartada; refeita na sessao do mapa)", de 19/08 | Relatório de 02/10 | Nenhum | Decidir se apaga |
| Dois documentos antigos fora do git: `docs/integracao_ml_e_empacotamento.md` e `docs/phase16_dashboard_3_visoes.md` | Relatório de 30/09 | Nenhum | Decidir se commita |
| `develop`, `main` e as tags só existem no PC | Desde 30/09 | Sem backup remoto | Quando o Eduardo autorizar o push |
| Duas projeções ao vivo durante a transição (runtime para mapa e painel, geometria oficial para o coach) | ADR 0013 | Temporário; o mesmo carro pode cair em trechos com números um pouco diferentes em telas diferentes | Some quando mapa, painel e replay migrarem |
| Coach: dizer a freada em relação à referência ("freou 12 m antes da referência") em vez da posição absoluta em metros | Revisão da Parte C (03/10) | O piloto não enxerga "1 578 m" na pista; a diferença é medida e mais útil ao vivo | Depois do pedido 11 |
| Voltas gravadas com a IA do AC misturadas às do piloto, inclusive dentro da mesma sessão | Eduardo (03/10); ADR 0014 | Conclusões sobre "o piloto", referência do coach e tamanho do experimento podem estar vindo da IA | Pedido 12 |
| Corrigir textos publicados que dizem "você" sobre voltas que podem ser da IA: vídeo "Modelo em Movimento", apresentação, aula, documento "Dados de corrida e estilos" e ADR 0011 | ADR 0014 | Afirmações como "você freia no mesmo ponto em 99 % dos pares" podem estar erradas | Depois da rotulagem, com os números por origem |
| Decidir se o Assetto Corsa vira o simulador do ganho (AssettoCorsaGym ou a própria IA do jogo) | Conversa de 03/10 | Caminho para a peça D depois da reprovação do simulador atual (ADR 0004) | ADR 0015, depois da rotulagem |
