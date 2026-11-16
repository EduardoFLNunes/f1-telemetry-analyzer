# 0032 — A referência do app é a volta do modelo

- **Status:** aceita (pedido 51). Registrada antes de qualquer mudança no código e antes de gerar o arquivo da volta do modelo
- **Data:** 2026-11-15
- **Decisor:** Eduardo
- **Atualização (15/11, pedido 52):** o engenheiro (ADR 0033) usa a volta do modelo como referência de cada trecho, salvo onde a melhor passagem do piloto é mais rápida; os pontos de freada, de entrada e de retomada dela viram o ponto da ação das frases. O freio dela continua só como ponto, e nunca como força ("freada leve" ficou fora).
- **Substitui:** a `volta_ia` como referência do app (ADR 0016, item da referência padrão; ADR 0009, a referência do coach). **Usa:** a meta e o teste no jogo do ADR 0031 e o medidor do ADR 0029. **Mantém:** a geometria do 0002, o detector de origem do 0014, o equipamento do 0015 e as regras do rádio do 0027 (os limites de 7,3, 8,0 e 8,8 s e a ordem do corte)

## Contexto

1. **A decisão do Eduardo de 15/11:** o app não usa a volta da IA do Assetto Corsa. Por causa da licença e da liberdade de levar o app a outros simuladores, o app tem só duas referências.
2. **A volta do modelo existe desde 15/11** (pedido 50, ADR 0031): a L2, gerada pelo algoritmo genético a partir da montagem por trecho, atingiu a meta. A melhor volta válida dela foi 1:24,552, no bloco 4 do teste (gravação `2026-11-15_02-47-12_vhe_interlagos_teste_m1`, na cópia `vhe_interlagos_teste_m1`, com o `fast_lane.ai` de sha256 `4e9f1250…`), contra 1:24,766 e 1:24,670 dos blocos vizinhos da linha da IA.
3. **Até aqui,** o modelo do coach tinha a `volta_ia` (a `#0013` de 04/10, 1:24,828) como referência padrão, e o fantasma, a marca "freada da IA" e o "atrás da IA" das falas vinham dela.
4. **A volta do modelo foi dirigida pela IA do jogo, na linha do projeto.** É o único motorista constante para medir uma linha. Os pedais dela são o comando do controlador da IA, e não a técnica de um piloto.

## Decisão

### 1. As referências do app

- **"Volta de referência"** (`volta_do_modelo`): a volta do Modelo 1. É a padrão.
- **"Sua melhor volta"** (`minha_melhor`): como hoje (a melhor volta limpa `humano` com o equipamento atual, ADR 0015).
- **A volta da IA do jogo nunca é referência do app,** nem opção na tela, nem padrão, nem item da rota das referências. O tipo `volta_ia` sai do app.
- **A configuração antiga** `"volta_ia"` vira `"volta_do_modelo"` ao abrir. `"minha_melhor"` e `"desligado"` continuam como estão. A variável `AT_COACH_REFERENCE=volta_ia` também vale como `volta_do_modelo`.

### 2. O que é a volta do modelo

- **A melhor volta válida** (a regra de volta válida do ADR 0029, item 5) **de uma linha do projeto que atingiu a meta do ADR 0031,** dirigida no jogo.
- **Guardada como um arquivo derivado,** e não como a gravação: os pontos da grade de 2 m da geometria oficial (a posição, o tempo, a velocidade, a marcha e os pedais) e os alvos por microssetor, no mesmo formato que o fantasma e o coach já leem. O arquivo leva:
  - a origem: o nome da sessão, a sequência e o número da volta no jogo, e o sha256 dos arquivos de origem;
  - a linha (o nome e o sha256 do `fast_lane.ai` dela), o `geometry_id`, o `corridor_id`, o carro e o preset do teste;
  - a marca "linha do projeto, meta atingida em <data>" e "executada pela IA do jogo na linha do projeto";
  - a pista a que vale.
- **A gravação não é copiada.** O arquivo guarda só o que foi derivado dela.
- **A pista da gravação:** quando a volta foi gravada numa cópia da pista, ela só vale na original se as duas tiverem a mesma geometria: o mesmo `geometry_id` na projeção das voltas e o mesmo sha256 dos arquivos que definem a superfície (o kn5 da pista e os arquivos de dados do layout). Se não tiverem, a volta não é usada.
- **Quando uma linha nova atingir a meta com uma volta melhor,** ela substitui a anterior. O arquivo anterior fica guardado ao lado, com a data no nome.

### 3. Se o algoritmo genético chegar à linha da IA

A saída continua sendo a volta do modelo, com a distância à linha da IA relatada (como no ADR 0031, item 1). Ela nunca é chamada de "volta da IA".

### 4. Sem volta do modelo

Para uma pista ou um carro sem volta do modelo, o app oferece só "Sua melhor volta", com a frase **"A volta de referência desta pista ainda não foi gerada pelo modelo"**. O coach usa a "Sua melhor volta" nesse caso.

### 5. O que vale da volta do modelo

- **Valem:** a linha, os pontos de freada, as velocidades, as marchas e o tempo.
- **O formato dos pedais só é desenhado, nunca julgado.** Nenhum detector de técnica (Modelo 2, a "freada emendada" do relatório de evolução) lê o formato do pedal dessa volta como técnica. Onde um relatório comparava a técnica do piloto com a da referência, a coluna da referência fica "não julgada".

### 6. A linha da IA

Fica só nos testes de desenvolvimento (ADRs 0029 e 0031: a régua no jogo, os blocos de C0) e no campo `referencia_anterior` da referência por trecho. Os scripts de desenvolvimento que precisam da `#0013` usam o identificador da volta (`ml.pista_teste.condicoes.VOLTA_IA`), e não um tipo de referência do app.

### 7. Os textos

Em todo lugar em que a referência é a volta do modelo:

- na voz: "atrás da IA" vira "atrás da referência"; "freou 34 metros antes da IA" vira "antes da referência"; "da IA" vira "da referência". "Do seu recorde" e "da melhor da sessão" ficam;
- "Melhor volta da sessão" vira "Melhor da sessão" (decisão do pedido 45 de 13/11);
- nos mapas do app do jogo: "freada da IA" vira "freada da referência"; o rótulo do fantasma "IA" vira "Referência";
- nas telas do app do Windows (Ao vivo, Volta, Evolução e Sessões): os rótulos de "IA" que se referem à referência viram "Referência". Os que falam da origem das voltas (o indicador de IA, "voltas da IA" fora da estatística) continuam, porque falam de quem dirigiu, e não da referência.

### 8. O que não muda

- O detector de origem continua tirando as voltas da IA de "Sua melhor volta" e das estatísticas.
- O rádio continua calado nas voltas da IA.
- A volta do modelo não entra em "Sua melhor volta" nem na evolução do piloto como volta dele. Ela é a régua da evolução no lugar da `volta_ia` (a seção 1.4 de `docs/store_v2_e_evolucao.md`, "referência").
- Os limites do rádio (7,3, 8,0 e 8,8 s) e a ordem do corte.
- O Modelo 1 (a busca, a codificação, o medidor), o Modelo 2 e o store v2.

## Consequências

- O construtor da referência (`tools/train_reference_model.py`, pelo `atualizar_coach`) lê o arquivo da volta do modelo e grava a referência `volta_do_modelo` no modelo do coach. Ele não procura mais voltas da IA.
- O instalador leva o arquivo da volta do modelo, como leva o traçado ótimo. O backend o procura na pasta do repositório, na pasta de dados e na pasta de recursos do app instalado, nessa ordem.
- O fantasma, o rádio, o minimapa e a tela Volta leem a grade da volta do modelo do arquivo, e não do store v2.
- Os relatórios e as comparações antigas que citam a `volta_ia` ficam como estavam: eram a referência da época.
