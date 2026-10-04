Eduardo aqui. Este pedido foi escrito junto com o Claude (Cowork), que faz a revisão e a arquitetura do projeto, e eu aprovo. O plano é meu. Pode executar.

O pedido 15 está aprovado, incluindo a sua decisão do piso de 0,005 s para o foco. Três coisas foram ótimas:

- o arquivo de rótulos versionado, que para o comando quando não bate;
- a proteção contra gravar no modelo do app instalado;
- a medida de quantas frases caem nos 3 maiores trechos da volta (de 21 % para 85 %).

O caso do setor 32 está certo como ficou. O foco mira as perdas que se repetem, e um erro isolado aparece no resumo.

Agora são duas coisas: reconstruir o store uma vez só, com todas as correções juntas, e criar o relatório da minha evolução. Esse relatório é a primeira versão da peça B, estatística.

## Parte A: documentação

Em `develop`, commite o pedido 16. Mensagem: `docs: pedido 16`.

## Parte B: store v2

Branch `etapa/store-v2`, a partir de `develop`.

### 1. Antes de construir

Registre no documento da etapa, num commit próprio, os efeitos esperados e as checagens:

- toda volta e o microsetor 0 sobem ~26 ms;
- as voltas com box saem;
- as duplicatas saem;
- **checagem principal:** em toda volta válida, o período de `s = 0` a `s = 0` bate com o cronômetro do jogo em até ±5 ms (p99);
- nenhuma volta válida passa pelo box;
- nenhuma volta aparece duas vezes;
- uma única geometria (`geometry_id`).

### 2. O que entra

- **Correção do período da volta:** o relógio passa a ser zerado na linha com o período verdadeiro.
- **Portão do box:** voltas com passagem pelo box deixam de ser válidas. Use a detecção do pedido 12.
- **As duas pastas** de gravações, sem as voltas marcadas com `duplicada_de`.
- **As colunas** `origem`, `origem_fonte`, `equipamento`, `relogio_suspeito`, `pasta` e `carModel` (quando houver), levadas para o store.
- **Os hashes** da geometria e das entradas no meta, como no ADR 0007.

### 3. Como guardar

- O store novo é uma versão nova (por exemplo `laps_grid_v2.parquet`, com o meta dele).
- O store antigo fica intacto, para os resultados das Fases 1, 2 e 2b continuarem reproduzíveis.
- Os scripts dessas fases continuam lendo o store antigo.

### 4. Relatório

- Quantas voltas por origem, equipamento e pasta.
- O resultado de cada checagem.
- Se a checagem principal falhar, pare e me relate.

## Parte C: relatório de evolução (peça B, primeira versão)

Na mesma branch.

### 1. Regras, registradas antes de rodar

- Só voltas `humano`, equipamento `atual`, válidas e com o relógio conferido.
- A referência é a volta da IA do coach (`volta_ia`).
- As unidades são as 14 curvas de `detect_corners`, que eu entendo melhor que microsetores. Os microsetores ficam como detalhe.
- **Uma curva é "diferença consistente"** quando o intervalo de 90 % (bootstrap) da perda mediana para a IA não inclui zero.
- **Com menos de 5 voltas** na sessão, a curva fica "poucos dados".

### 2. Por sessão

- Número de voltas válidas, melhor volta, mediana e desvio.
- Diferença total para a volta da IA.

### 3. Por curva, em cada sessão

- Perda mediana para a IA e a dispersão (intervalo interquartil).
- Ponto de frenagem em relação ao da IA: mediana e dispersão.
- Posição lateral no ápice em relação à linha da IA: mediana e dispersão.
- Velocidade mínima em relação à da IA: mediana.

### 4. Entre sessões

- A tendência da mediana de volta e das 3 curvas de maior perda.
- A situação do critério de estabilização do ADR 0015: a mediana das últimas 3 sessões varia menos de 0,5 s?

### 5. Saída

- Um JSON por sessão e um JSON de resumo, numa pasta de dados fora do git (por exemplo `data/ml/evolucao/`).
- Documente o formato dos campos. O Claude (Cowork) vai montar um painel interativo a partir desses arquivos.

### 6. Comando

- `python tools/relatorio_evolucao.py`, que roda tudo para todas as sessões.
- O `atualizar_coach.py` passa a chamar esse comando no fim.

### 7. Primeira rodada

Rode com a sessão de 04/10. Ela vira a linha de base.

## Parte D: testes e entrega

- **Testes:**
  - a checagem do período;
  - o portão do box;
  - a remoção de duplicatas;
  - a regra de "diferença consistente";
  - "poucos dados" abaixo de 5 voltas;
  - o filtro de origem e equipamento.
- **Merge:** se a suíte e as checagens passarem, faça o merge de `etapa/store-v2` em `develop`.
- **Em `docs/handoff/`:** o patch, as saídas das suítes, os resultados das checagens e uma cópia dos JSONs da sessão de 04/10.
- **`docs/store_v2_e_evolucao.md`,** em português simples: o que mudou no store, as checagens, como ler o relatório e o formato dos JSONs.
- **No backlog:** tire a "Reconstrução do store" e o item das voltas com box. Acrescente "atualizar_coach leva ~16 min; criar um modo incremental".

## Restrições

- O store antigo e os documentos de resultado das Fases 1, 2 e 2b ficam como estão.
- Não mexa no app instalado nem no modelo dele.
- Não contorne nenhuma trava: se algo bloquear, pare e me avise.
- Não envie nada ao remoto.

No relatório, apresente a Parte A, o store v2 com as checagens, o relatório de evolução da sessão de 04/10 e o merge.
