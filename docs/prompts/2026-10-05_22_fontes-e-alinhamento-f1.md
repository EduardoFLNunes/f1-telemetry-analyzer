# Pedido 22 — Ajustes do ADR 0018 e alinhamento da volta da F1 à pista oficial

**De:** Eduardo (o plano é meu). **Data:** 05/10/2026.
**Parte A:** só documentação. **Parte B:** código novo e medição, sem treinar nenhum modelo.

## Respostas aos pontos do relatório do pedido 21

1. **Peças A a E.** Elas estão definidas em `docs/correcao_trajetoria_auditoria.md`, "Parte 2 — Arquitetura proposta", seção 1:
   - A: previsão de trajetória;
   - B: erro do piloto;
   - C: autocorreção;
   - D: tempo contrafactual;
   - E: avaliação.

   Falta só ligar esse texto aos documentos de hoje (Parte A, item 3).
2. **Duas linhas de retreino no backlog:** decidi juntar numa linha só (Parte A, item 1).
3. **Voltas `ia` antigas no treino:** decidi que só entram as rotuladas (Parte A, item 2).
   - Correção de número: o detector rotulou **75 voltas antigas** (35 `ia`, 8 `humano` e 32 `misturada`), e nada foi promovido (`docs/detector_ia.md`). Não foram 75 `ia`.
4. **A volta FastF1 já importada** é o ponto de partida da Parte B.

## Parte A — Documentação

1. **`docs/backlog.md`:** junte as duas linhas de retreino da LSTM (a antiga, da peça A, e a nova, do ADR 0018) numa linha só:
   - **Item:** "Retreinar a LSTM geradora com as três fontes (voltas `humano` com equipamento `atual`, voltas `ia` rotuladas e forma da linha da F1), testada na régua do ADR 0006".
   - **Quando:** "depois das 5 sessões de treino e do alinhamento da F1 (Parte B deste pedido)".
   - Mantenha na coluna Origem as duas origens.
2. **`docs/decisoes/0018-dois-modelos-e-fontes-de-treino.md`:** acrescente ao fim uma seção "Esclarecimento (05/10, pedido 22)" dizendo:
   - "voltas `ia` rotuladas" são só as de sessões com rótulo pelo indicador do jogo ou por anotação;
   - as voltas antigas ficam fora do treino do Modelo 1. Isso vale para as de origem `desconhecida`, inclusive as que o detector marcou sem promover;
   - elas podem entrar depois num teste à parte, com e sem elas, na régua do ADR 0006. Crie a linha correspondente no backlog.
3. **`docs/arquitetura_ml.md`:** acrescente uma seção curta, "As peças A a E e os dois modelos", com:
   - uma tabela peça × modelo × situação: A, a busca evolutiva e o juiz no Modelo 1; B, C e D no Modelo 2; E avalia os dois;
   - um link para a seção 1 da Parte 2 de `docs/correcao_trajetoria_auditoria.md` e para o ADR 0018.

   Situação só com o que está registrado:
   - existe: LSTM geradora e busca evolutiva;
   - em uso: B versão 1 e E;
   - planejado: C;
   - não passou: D;
   - em construção: o juiz novo, etapa M0 feita.

## Parte B — Alinhar a volta da F1 à geometria oficial e medir o erro

**Objetivo:** ter a forma da linha da F1 real como lateral(s) na mesma grade de 2 m das nossas voltas, com o erro de alinhamento medido. Nenhum modelo é treinado nesta parte.

**Entrada:** `data/external_references/fastf1__2024__Brazil__Q__NOR__32__093bbee0.json`, que tem 633 amostras com `x` e `y` nas coordenadas do FastF1, marcada `UNCALIBRATED`.

**Passos:**

1. **Unidades e amostragem.** Descubra a unidade de `x`/`y` pelos próprios dados: compare o perímetro da volta com o comprimento da geometria oficial (4.334 m). Relate também o espaçamento entre amostras em metros (mediana e p95).
2. **Alinhamento rígido com escala única.** Use rotação, translação, uma escala só e, se precisar, espelhamento. Nada de deformar a linha: deformar esconderia o erro. Ajuste contra a linha central da geometria oficial (hash `0ed16f0dd2225990`). Pode ser ICP ou Procrustes com correspondência por distância. Relate:
   - a escala ajustada e o comprimento resultante contra os 4.334 m;
   - a rotação e se houve espelhamento.
3. **Projeção na grade.** Projete a linha alinhada em s e lateral, com a mesma convenção (ADR 0003, positivo à esquerda) e a mesma grade de 2.167 pontos das voltas do store v2. Interpole entre as amostras, já que a F1 tem poucas.
4. **Erro de alinhamento.** Uma linha de corrida real fica dentro da pista. Por isso o erro é o excesso: quanto cada ponto alinhado fica fora do corredor oficial (largura medida + zebra, como em `ml/track`), valendo 0 se está dentro. Relate:
   - a fração de pontos fora do corredor;
   - a mediana, o p95 e o máximo do excesso;
   - os 5 microsetores com maior excesso.
5. **Comparação descritiva, só para leitura.** Por microsetor, compare a diferença lateral mediana entre:
   - a linha da F1 e a mediana das 13 voltas `ia` rotuladas de 04/10;
   - a linha da F1 e a mediana das voltas `humano` com equipamento `atual`.

   Nada disso muda coach, store ou critério.
6. **Figura.** Gere um PNG com a pista oficial, a linha da F1 alinhada e a linha mediana da IA, com zoom no S do Senna e no Bico de Pato. Coloque uma cópia em `docs/handoff/`.

**Regras da Parte B:**

- **Não use velocidade, pedal nem ponto de frenagem da F1:** é outro carro (ADR 0018).
- **Critério fixado antes de rodar:** o alinhamento só é aceito para uso futuro se a fração de pontos fora do corredor for de no máximo 10% e o p95 do excesso for de no máximo 1 m. Senão, o relatório diz "não aceito", com os números, e nada é ajustado depois de ver o resultado.
- **Saídas:** em `data/ml/externo/`, que fica fora do git. O resumo JSON e a figura vão também para `docs/handoff/`.
- **Testes:** um caso sintético em que uma linha conhecida passa por uma transformação conhecida e o alinhamento recupera escala, rotação e translação dentro de tolerância; e a convenção de sinal do lateral.

## Regras gerais

- Branch `etapa/fastf1-alinhamento`, commits por parte, merge em `develop`. Sem push.
- Não mexa no app instalado nem em arquivos do jogo.
- Uma sessão de implementação por vez (ADR 0008).
- Relatório em `docs/handoff/2026-10-05_22_fontes-e-alinhamento-f1_relatorio.md`, como manda o CLAUDE.md, com:
  - os números das etapas 1 a 5;
  - o veredito do critério;
  - o caminho da figura;
  - os commits.
- Se algo do contexto não bater com o repositório, pare e registre no relatório.
