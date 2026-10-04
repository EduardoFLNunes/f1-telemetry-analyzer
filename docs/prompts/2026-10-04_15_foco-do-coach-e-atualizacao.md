Eduardo aqui. Este pedido foi escrito junto com o Claude (Cowork), que faz a revisão e a arquitetura do projeto, e eu aprovo. O plano é meu. Pode executar.

O pedido 14 está aprovado. Três coisas foram ótimas:

- usar o cronômetro do jogo quando o timestamp engasga;
- tirar das comparações o box e o carro parado ("a sua 0 km/h");
- apontar sozinho a limitação das 3 primeiras frases, com o exemplo da volta de 91,74 s.

O ADR 0016 pedia falar "nos trechos de maior diferença". O jeito atual fala nos primeiros que passam do limiar, e isso este pedido corrige. Também quero que atualizar o coach depois de cada sessão seja um comando só.

## Parte A: documentação

1. Em `develop`, commite o pedido 15.
2. No `docs/backlog.md`, tire os itens que o pedido 14 fechou: o critério (c) do coach (o resto dele já está na "Reconstrução do store"), qual modelo treinar e o limiar de fala.
3. Mensagem: `docs: backlog e pedido 15`.

## Parte B: trechos de foco

Branch `etapa/coach-foco`, a partir de `develop`.

### 1. Escolha dos trechos

- Antes de cada volta, o coach escolhe 3 trechos de foco: os 3 microsetores com a maior diferença mediana para a referência ativa, nas últimas 5 voltas válidas da sessão.
- Enquanto a sessão ainda não tiver 5 voltas válidas, use as minhas voltas do modelo treinado.
- Os trechos excluídos hoje (box, carro parado, primeiro trecho depois de começar a contar) continuam fora.

### 2. Durante a volta

- O coach só fala nos trechos de foco, quando a diferença passa do limiar.
- No máximo uma frase por trecho, então no máximo 3 por volta.

### 3. No fim da volta

- O resumo dos 3 trechos de maior diferença continua igual.
- Quando o foco mudar, o coach manda uma mensagem curta no próprio feed, por exemplo "Foco nas proximas voltas: setores 32, 38 e 43".
- Nada de componente novo na interface.

### 4. Ensaio

- Repita o ensaio nas minhas voltas de 04/10, nos dois modos.
- Relate onde as frases caem agora, comparando com o pedido 14.
- Na volta de 91,74 s, elas devem ir para os trechos de maior diferença.

### 5. Testes

- O foco escolhe os 3 maiores pela mediana das últimas 5 voltas válidas.
- Antes de 5 voltas, o foco vem do modelo.
- Fora do foco, o coach não fala.
- Continua no máximo 3 frases por volta.

## Parte C: atualizar o coach com um comando

1. Guarde as anotações da sessão de 04/10 num arquivo pequeno e versionado. Elas são a verdade de campo daquela sessão.
2. Crie um comando, por exemplo `python tools/atualizar_coach.py`, que faça em ordem:
   1. refazer o inventário novo (`data/ml/origem/`);
   2. aplicar as anotações versionadas;
   3. rotular as sessões novas sem anotação pela regra abaixo;
   4. fazer o backup do modelo do repositório e treiná-lo;
   5. imprimir um resumo: as duas referências escolhidas, quantas voltas de cada origem, o limiar e o foco inicial.
3. **Regra para sessões sem anotação:**
   - antes da primeira vez que a IA liga na sessão do jogo, as voltas são `humano`, pelo indicador;
   - a volta em que a IA liga é `misturada`;
   - depois disso, como o indicador fica travado, quem decide é o detector pela linha da IA, já validado; o que ele não resolver fica `desconhecida`.
4. No `docs/coach_aprendizado.md`, troque os passos manuais de depois da sessão por esse comando.

## Restrições

- Não reconstrua o store do ML. Isso fica para o pedido próprio da reconstrução.
- Não mexa no app instalado.
- Não contorne nenhuma trava: se algo bloquear, pare e me avise.
- Não envie nada ao remoto.

## Merge e entrega

- Se a suíte passar, faça o merge de `etapa/coach-foco` em `develop`, rode o comando novo uma vez e confira o resumo.
- Em `docs/handoff/`: o patch, as saídas das suítes, as frases do ensaio e o resumo do comando.
- No relatório: a Parte A, o foco com o ensaio (antes e depois), o comando com a saída dele e o merge.
