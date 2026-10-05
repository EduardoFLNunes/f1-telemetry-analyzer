Eduardo aqui. Este pedido foi escrito junto com o Claude (Cowork), que faz a revisão e a arquitetura do projeto, e eu aprovo. O plano é meu. Pode executar.

O pedido 19 está aprovado. A tabela dos tempos foi exatamente o que faltava: a causa (o `duration_s` publicado com o nome `lap_time_s`) e cada lugar onde ele aparece. Aceito as sete propostas, com o formato abaixo. A apresentação do TCC já foi corrigida pelo Claude (Cowork) com os tempos oficiais.

## Parte A: erratas nos documentos

Em `develop`, num commit só. A regra é: **documento de decisão e de resultado recebe nota de errata datada, sem reescrever o texto original. Documento vivo é corrigido direto.**

1. **`docs/decisoes/0016-coach-na-fase-de-aprendizado.md`:** nota de errata de 05/10, logo abaixo da tabela. Diga que os tempos da tabela vieram do `duration_s` e que os oficiais são 89,390 s (`2026-10-04_02-24-04#0018`) e 84,829 s (`2026-10-04_03-42-10#0013`). Diga também que a decisão não muda.
2. **`docs/detector_ia.md`, linhas 62 e 63:** a mesma nota. Inclua as médias oficiais (93,60 ± 2,40 s e 85,02 ± 0,13 s) e diga que a melhor volta da IA é a 26 (`#0013`), não a 25.
3. **`docs/backlog.md`, linhas 16 e 18:** troque pelos números oficiais. É documento vivo.
4. **`docs/coach_geometria_oficial.md` e `docs/origem_das_voltas.md`:** nota de que 84,663 s foi o tempo do coach antigo e de que o oficial é 84,672 s (`2026-08-19_22-23-14#0004`).
5. **`docs/coach_aprendizado.md`:** nota na tabela do pedido 14. A coluna "jogo ~" é o cronômetro na última amostra; ponha o costurado e o oficial ao lado.
6. **JSONs de resultado dos pedidos 12 e 13:** ficam como estão. Acrescente no `docs/origem_das_voltas.md` e no `docs/detector_ia.md` uma nota dizendo que os `tempo_s` e `lap_time_s` desses JSONs são `duration_s`.

Mensagem: `docs: erratas dos tempos de volta que vieram do duration_s (pedido 19)`.

## Parte B: o nome no resumo do inventário

Branch `etapa/inventario-duration`, a partir de `develop`.

1. **Antes de mudar,** liste quem lê o resumo do inventário e o campo `lap_time_s` dele: código do ML, testes, scripts, o app e o frontend. Se algo fora do ML (o app ou o frontend) ler esse campo, pare e me relate.
2. **A mudança:** em `ml/data/inventory.py::summarise`, o campo publicado passa a se chamar `duration_s`, e o melhor tempo do resumo passa a ser `best_duration_s` (ou outro nome que deixe claro que não é tempo de volta). Atualize quem lê.
3. **O que não muda:** o store v2, o tempo oficial (`lap_time_s` do store), os portões e os JSONs de resultado já gravados.
4. **Testes:** o resumo não publica mais nenhum campo `lap_time_s`, e o `duration_s` continua com o mesmo valor de antes.
5. **Merge:** se a suíte passar, faça o merge em `develop`.

## Restrições

- Nenhum critério, número de resultado, store ou modelo muda neste pedido.
- Não mexa no app instalado.
- Não contorne nenhuma trava: se algo bloquear, pare e me avise.
- Não envie nada ao remoto.

No relatório (regra do `CLAUDE.md`), apresente as erratas com o arquivo e a linha de cada uma, a lista de quem lia o campo, a mudança e o merge.
