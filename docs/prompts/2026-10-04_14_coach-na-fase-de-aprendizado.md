Eduardo aqui. Este pedido foi escrito junto com o Claude (Cowork), que faz a revisão e a arquitetura do projeto, e eu aprovo. O plano é meu. Pode executar.

O pedido 13 está aprovado. Três coisas foram ótimas:

- descobrir que o indicador do jogo só liga;
- conferir o detector calibrando numa parte da sessão e testando na outra;
- deixar 467 voltas antigas indefinidas em vez de afrouxar a regra registrada.

Decisões:

- **Voltas antigas: opção (1).** Ficam como estão, nada é promovido. Pelo ADR 0015, só as voltas novas falam de mim, e a referência da IA vai sair de sessões novas.
- **O experimento controlado com piloto está suspenso.** Com o meu desvio de 0,91 s, ele não tem como funcionar.
- **O coach passa a ser a ferramenta desta fase.** Leia `docs/decisoes/0016-coach-na-fase-de-aprendizado.md`.

## Parte A: merge e documentação

1. Em `develop`, faça `git merge --no-ff etapa/detector-ia` e rode a suíte.
2. Ainda em `develop`, atualize os documentos:
   - substitua `docs/backlog.md` por `docs/prompts/anexos-14/backlog.md`;
   - substitua `docs/experimentos/protocolo_sessao_controlada.md` por `docs/prompts/anexos-14/protocolo_sessao_controlada.md`, mantendo o "Como desligar" que você escreveu;
   - substitua `docs/decisoes/README.md` por `docs/prompts/anexos-14/README.md`;
   - apague a pasta `docs/prompts/anexos-14/`.
3. Commite junto o pedido 14 e o ADR 0016. Mensagem: `docs: ADR 0016 (coach na fase de aprendizado), backlog, protocolo e pedido 14`.

## Parte B: corrigir o critério (c) do pedido 11

Na branch `etapa/coach-geometria-oficial`.

1. Traga `develop` para a branch com `git merge develop`. Se houver conflito que não seja simples, pare e me relate.
2. **Antes de mudar o código**, registre os critérios num commit próprio:
   - os critérios de a até d do pedido 11, com os mesmos limites;
   - um critério novo, (e): nas voltas limpas, nenhum salto de projeção, ou seja, \|Δs\| máximo de até 2 m contra `TrackGeometry.project_sequence`.
3. **Linha de chegada:** o microsetor 0 e a virada de volta do coach passam a seguir a convenção do ML, que é o `s = 0` da geometria oficial, interpolado. Confira se o viés de −0,034 s do relógio no microsetor 0 tem a mesma causa e relate.
4. **Continuidade:** na instância do `MapMatchingEngine` usada pelo coach, acrescente a opção de um limite rígido de avanço por amostra, calculado pela velocidade e pelo intervalo entre amostras, com folga, como a regra de 60 m do ML. A opção fica desligada por padrão, para mapa e painel continuarem iguais.
5. Rode de novo os critérios de a até e. Se algum falhar, pare, não faça merge e me relate.

## Parte C: as duas referências (ADR 0016)

Na mesma branch.

### 1. Modos de referência

- **`volta_ia`, o padrão:** a melhor volta limpa com origem `ia`, de sessões gravadas a partir de 04/10 (gravador novo), com o mesmo `carModel` e a geometria oficial. Hoje são as 13 voltas limpas da IA da sessão rotulada.
- **`minha_melhor`:** a melhor volta limpa com origem `humano` e equipamento `atual`.
- O modo antigo `best_per_microsector` continua desligado.
- O modo é escolhido por configuração. Não precisa trocar pela interface.

### 2. Frases

- **Cada frase diz qual referência usa.** Exemplo: "Setor 22: 0.60s atras da volta da IA neste trecho (1.98s contra 1.38s). A IA freia 12 m depois de voce; minima da IA 110 km/h, a sua 98 km/h."
- **A freada aparece em relação à referência** ("antes" ou "depois", em metros), e não mais como posição absoluta.
- **Siga o estilo das frases atuais** (sem acentos, decimal com ponto).
- **Nunca** "ganh", "ideal" ou "otimo".

### 3. Quando falar

- O limiar continua sendo duas vezes a minha oscilação, calculada só com voltas `humano` de equipamento `atual`, pelos filtros do pedido 12.
- No máximo 3 frases por volta: as primeiras que passarem do limiar.
- No fim da volta, um resumo com os 3 trechos de maior diferença para a referência.

### 4. Interface

- Troque o rótulo do `CoachingFeed` para mostrar qual referência está em uso.
- Faça a menor mudança possível e liste cada texto alterado, com arquivo e linha.
- Não mude o layout.

## Parte D: testes e ensaio

### 1. Testes

- `volta_ia` escolhe só voltas da IA de sessões novas, nunca as antigas.
- `minha_melhor` escolhe só voltas `humano` com equipamento `atual`.
- O teto de 3 frases por volta é respeitado.
- O sinal de "antes" e "depois" da freada está certo.
- As frases citam a referência e não contêm "ganh", "ideal" nem "otimo".

### 2. Ensaio

- Rode o coach novo, amostra por amostra, sobre as minhas voltas da sessão de 04/10, nos dois modos.
- Salve todas as frases no handoff.
- Relate quantas frases por volta e quais trechos aparecem mais.

## Merge e modelo

Só se os critérios de a até e e as suítes passarem:

1. Faça `git merge --no-ff etapa/coach-geometria-oficial` em `develop`.
2. Faça um backup do modelo do repositório (`data/reference_models/vhe_interlagos.json`), que é o lido pelo app de desenvolvimento.
3. Treine esse modelo com o código de `develop`.
4. Carregue o modelo pelo leitor do app e repita o ensaio em uma volta minha.
5. Crie a tag `handoff/coach-aprendizado`.

O modelo do app instalado fica como está até o app ser reempacotado.

## Restrições

- Mapa e painel ao vivo continuam com o comportamento de hoje.
- Não altere o modelo do app instalado e não promova rótulos de voltas antigas.
- Não contorne nenhuma trava: se algo bloquear, pare e me avise.
- Não envie nada ao remoto.

## Entrega

- Em `docs/handoff/`: o patch contra `develop`, as saídas do pytest e do vitest, um JSON com os critérios de a até e, e as frases do ensaio.
- `docs/coach_aprendizado.md`, em português simples: o que mudou, as medições e as limitações.
- No fim desse documento, um passo a passo de como eu abro o app de desenvolvimento para treinar com o coach ligado.

No relatório, apresente a Parte A, os critérios de a até e com os números, a Parte C, o ensaio e o merge.
