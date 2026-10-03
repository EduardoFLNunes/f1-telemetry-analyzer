Eduardo aqui. Este pedido foi escrito junto com o Claude (Cowork), que faz a revisão e a arquitetura do projeto, e eu aprovo. O plano é meu. Pode executar.

Os itens 1 e 3 e a Parte C estão aprovados. Três coisas foram ótimas:

- a medição da primeira contra a segunda metade, que mostrou que nada do "ganho na mesa" se realizou;
- o teste que pegou a volta com buraco contando como completa;
- não regravar o modelo do app antes do merge, para não calar o coach em `develop`.

Sobre a geometria: a escolha já estava feita no ADR 0002 (a geometria oficial é a do `load_geometry`). O ADR 0013 decide por onde começar: pelo coach, com o modelo saindo da posição no mundo e não do `p` gravado. Isso resolve de uma vez a mistura de três réguas e a falta das 56 voltas de 09/08.

Leia antes de começar:

- `docs/decisoes/0002-geometria-unica.md`;
- `docs/decisoes/0013-coach-primeiro-na-geometria-oficial.md`.

## Parte A: tag e documentação

1. Crie a tag `handoff/coach-referencia-real` no commit `a2f4d143`.
2. Em `develop`, commite:
   - `docs/prompts/` (pedido 11);
   - `docs/decisoes/` (ADR 0013 e o índice);
   - `docs/backlog.md`;
   - o protocolo da sessão controlada.

   Mensagem: `docs: ADR 0013, backlog, protocolo (coach desligado) e pedido 11`.

## Parte B: coach na geometria oficial (ADR 0013)

Branch `etapa/coach-geometria-oficial`, a partir de `etapa/coach-referencia-real` (ela já contém a Parte C).

### 1. Exportar a geometria oficial

- O `ml` exporta, a partir de `load_geometry`, um JSON com a grade (x, z, s), as normais, as 60 fronteiras dos microsetores, o comprimento da pista e o `geometry_id`.
- O arquivo fica junto dos outros modelos do app, fora do git, como o traçado exportado.
- O backend só lê esse arquivo e não importa o pacote `ml`.

### 2. Projetar no coach

- O coach calcula `s` e `d` a partir de `world_x` e `world_z`, na grade exportada, ao vivo e no treino.
- **Reaproveite o projetor que já existe** em `core/projection/` ou `core/spatial_engine.py`, trocando só a geometria, se ele permitir. Escreva um novo só se o existente não servir, e explique por quê no relatório.
- A projeção precisa de desempate por continuidade, como no `ml` (o carro não avança mais de 60 m entre amostras), por causa da reta dos boxes ao lado do retorno, e precisa tratar a passagem pela linha de chegada.
- Use os leitores de campos que já existem. Nada de leitor novo.

### 3. Treino do modelo

- Entram todas as voltas válidas e completas, de qualquer cache, inclusive as de 09/08.
- Os microsetores são as 60 fronteiras exportadas.
- O modelo grava o `geometry_id`. A lógica de "geometria da maioria" sai.
- No relatório, mostre a volta de referência escolhida e as 5 voltas válidas mais rápidas, com o motivo de cada uma ter sido escolhida ou não.

### 4. Ao vivo

- Se o arquivo de geometria faltar, ou se o `geometry_id` dele for diferente do modelo, o coach fica em silêncio e avisa no log, como já faz com um modelo antigo.
- Mapa, painel ao vivo e replay continuam com a projeção atual do runtime.

### 5. O "Ganho estimado" do `feedback_generator.py`

- Descubra de onde vem esse número.
- Se vier do simulador, da soma dos melhores trechos ou de qualquer previsão, troque pela diferença medida contra a volta de referência ou remova o número (ADR 0012).
- Se for diferença medida, mantenha e explique no relatório.
- Liste cada texto alterado, com arquivo e linha.

### 6. Coach desligado na sessão controlada

- No protocolo da sessão controlada, há uma linha nova pedindo o coach desligado durante a sessão, com o trecho "Como desligar: (a preencher)".
- Descubra se já existe um jeito de desligar ou esconder o coach. Se existir, escreva o passo a passo no lugar do "(a preencher)".
- Se não existir, não crie nada na interface. Relate e proponha a opção mais simples.

### 7. Validação: critérios fixados antes de rodar

Se algum critério falhar, pare, não faça merge e me relate.

| | o que medir | critério |
|---|---|---|
| a | Fidelidade: projeção do coach contra `TrackGeometry.project_sequence` nas mesmas amostras, com pelo menos uma sessão de cada origem (`MergeFix`, cache atual, sem cache) | p99 de \|Δs\| ≤ 0,5 m e p99 de \|Δd\| ≤ 0,2 m; relate também o máximo |
| b | Tempo de projeção por amostra, neste PC | p99 ≤ 1 ms |
| c | Tempos por microsetor do coach contra os do store, nas mesmas fronteiras, em 5 voltas de sessões diferentes | diferença máxima ≤ 0,02 s por microsetor; a soma bate com o tempo de volta em ±0,02 s |
| d | Ensaio: o coach novo roda, amostra por amostra e na ordem gravada, sobre duas sessões inteiras (uma de 20/06 e uma de 09/08) | todas as frases salvas no handoff; nenhuma contém "ganh", "ideal" ou "otimo"; relate quantas frases por volta |

### 8. Testes

- Projetor na pista circular sintética, como os testes que já existem.
- Volta sem `p`, no formato de 09/08, entra no modelo.
- Sessões de caches diferentes entram no mesmo modelo.
- `geometry_id` diferente ou arquivo ausente deixam o coach em silêncio.

### 9. Merge e modelo do app

Só se os critérios de a até d e as suítes passarem:

1. Faça `git merge --no-ff etapa/coach-geometria-oficial` em `develop`. Isso traz junto a Parte C.
2. Copie `data/reference_models/vhe_interlagos.json` para `vhe_interlagos.json.bak-2026-10-03`. Não apague o original antes da cópia.
3. Com o código de `develop`, exporte a geometria e treine o modelo do app.
4. Carregue o modelo novo pelo leitor do app e repita o ensaio (d) em uma sessão, para confirmar que o coach fala.
5. Crie a tag `handoff/coach-geometria-oficial`.

Se algo falhar nesses passos, não mexa no arquivo do modelo e me relate.

### Restrições

- Não mexa no mapa, no painel ao vivo, no replay, no `optimal.json` nem nas LSTMs.
- Não contorne nenhuma trava: se algo bloquear, pare e me avise.
- Não envie nada ao remoto.

### Entrega

Em `docs/handoff/`:

- o patch contra `develop`;
- a saída completa do pytest do backend e do frontend;
- um JSON com os números dos critérios de a até d;
- as frases do ensaio.

Escreva também `docs/coach_geometria_oficial.md`, em português simples: o problema, a mudança, as medições e as limitações.

No relatório, apresente a Parte A, depois os critérios de a até d com os números, e por último o merge.
