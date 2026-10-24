# Registro de decisões (ADR)

Formato de Michael Nygard: **Título, Status, Contexto, Decisão, Consequências.** Uma decisão por arquivo, numerada. Uma decisão nunca é apagada. Quando muda, um novo ADR a substitui e o antigo recebe o status "substituída por NNNN".

| nº | decisão | status |
|---|---|---|
| [0001](0001-processo-de-desenvolvimento.md) | Processo de desenvolvimento com vários agentes | aceita; itens 2 e 3 substituídos por 0008 |
| [0002](0002-geometria-unica.md) | Uma única geometria oficial da pista | aceita; implementação em andamento, começando pelo coach (0013) |
| [0003](0003-convencao-sinal-lateral.md) | Convenção de sinal do deslocamento lateral | aceita; implementada |
| [0004](0004-simulador-nao-estima-ganho-local.md) | O simulador não estima ganho de tempo local | aceita; o caminho para um modelo físico novo está no 0017 |
| [0005](0005-estimador-empirico-e-predicao-seletiva.md) | Estimador empírico de ganho e predição seletiva | aceita; Fase 2b |
| [0006](0006-protocolo-de-validacao.md) | Protocolo de validação dos estimadores | aceita |
| [0007](0007-versionamento-de-dados.md) | Versionamento de dados sem DVC, por enquanto | aceita |
| [0008](0008-uma-sessao-de-implementacao.md) | Uma única sessão de implementação por vez | aceita |
| [0009](0009-alvos-do-coach-e-tracado-otimizado.md) | O traçado otimizado não vira alvo do coach enquanto for mais lento que voltas reais | aceita |
| [0010](0010-fase-2b-ajustada-pelos-artigos.md) | Fase 2b ajustada pela leitura dos artigos | aceita; complementa 0005 |
| [0011](0011-resultado-fase-2b-e-experimento-controlado.md) | Dados observacionais não medem o efeito das instruções de controle; próximo passo é o experimento controlado | aceita |
| [0012](0012-coach-diferenca-medida-nao-ganho-prometido.md) | O coach mostra diferença medida contra uma volta real, não "ganho possível" pela soma dos melhores trechos | aceita; refina 0004; referência padrão refinada por 0016 |
| [0013](0013-coach-primeiro-na-geometria-oficial.md) | O coach é o primeiro a usar a geometria oficial, e o modelo dele sai da posição no mundo | aceita; implementa parte do 0002 |
| [0014](0014-origem-das-voltas-humano-ou-ia.md) | Toda volta tem origem: humano, IA ou desconhecida | aceita |
| [0015](0015-equipamento-atual-do-piloto.md) | O modelo do piloto usa só voltas com o equipamento atual | aceita; complementa 0014 |
| [0016](0016-coach-na-fase-de-aprendizado.md) | Na fase de aprendizado, a referência padrão do coach é a volta da IA | aceita; refina 0012; enquadrada por 0018 |
| [0017](0017-modelo-fisico-do-carro.md) | Modelo físico do carro: carro e piloto separados, construído por etapas junto do que já roda | aceita |
| [0018](0018-dois-modelos-e-fontes-de-treino.md) | Dois modelos, previsão e correção; a volta da IA é uma fonte de treino, não o alvo | aceita; item 3 refinado por 0019 |
| [0019](0019-f1-tracado-de-referencia-2023-25.md) | A F1 entra no Modelo 1 como um traçado de referência único da época 2023–25 | aceita; refina 0018 |
| [0020](0020-realidade-aumentada-app-lua-do-csp.md) | Realidade aumentada no Assetto Corsa: um app Lua do CSP, numa pasta própria do jogo | aceita (pedido 31); item 4 refinado por 0021 |
| [0021](0021-radio-que-analisa-as-voltas-e-minimapa.md) | O rádio analisa as voltas e diz onde e por que o piloto perde tempo; o app do jogo ganha um minimapa | aceita (pedido 35); refina 0020 |
| [0022](0022-validacao-da-m1-modelo-do-carro.md) | Validação da M1: como o modelo do carro para a frente é aprovado, e com que relógio | aceita (pedido 37); complementa 0006 e 0017 |
