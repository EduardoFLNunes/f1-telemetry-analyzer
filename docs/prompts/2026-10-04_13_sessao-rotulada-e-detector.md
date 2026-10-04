Eduardo aqui. Este pedido foi escrito junto com o Claude (Cowork), que faz a revisão e a arquitetura do projeto, e eu aprovo. O plano é meu. Pode executar.

O pedido 12 está aprovado. Três coisas foram ótimas:

- achar as voltas gravadas duas vezes por dois backends abertos;
- fixar o limite do relógio no documento antes de aplicá-lo;
- fazer o store e o treino do coach pararem com mensagem clara quando nenhuma volta passa no filtro.

Os sinais deixam pouca dúvida: em 27 de 32 sessões, o ápice varia até 6 cm entre voltas. Isso é a IA. Agora precisamos de voltas rotuladas de verdade, e o gravador novo resolve isso.

Este pedido tem uma parada no meio, porque eu vou pilotar.

## Parte A: documentação

Em `develop`, commite o pedido 13 e o `docs/backlog.md`.

Mensagem: `docs: backlog e pedido 13`.

## Parte B: preparar a sessão rotulada

1. Abra o app a partir de `develop`, do jeito que você indicou, para gravar com o indicador de IA.
2. Deixe o coach calado nessa versão do app. Se ela ler um modelo diferente do app instalado, renomeie esse arquivo e volte o nome no fim. Diga qual arquivo foi.
3. Escreva para mim, em poucas linhas, o que fazer. O plano da sessão está abaixo.
4. **Pare e espere** eu avisar que terminei a primeira parte.

### Plano da sessão (Interlagos, com o mesmo carro de sempre)

**Primeira parte, teste (cerca de 5 voltas):**

- 2 voltas minhas;
- 2 voltas com a IA;
- 1 volta em que eu ligo a IA no meio e desligo antes do fim.

Eu anoto o número no jogo de cada volta e o momento em que liguei e desliguei a IA.

**Você confere:**

- se o indicador muda quando a IA assume e quando solta;
- se o `carModel` aparece no `metadata.json`.

Se der certo, me avise para seguir. Se não der, pare e me relate.

**Segunda parte, rotulada (cerca de 30 voltas):**

- 20 voltas minhas;
- 10 voltas com a IA, em blocos de 5, intercaladas com as minhas.

Eu continuo anotando o número no jogo das voltas com IA, como reserva caso o indicador falhe.

## Parte C: depois da sessão

Branch `etapa/detector-ia`, a partir de `develop`.

### 1. Rótulos da sessão nova

- Cada volta recebe `origem` pelo indicador: `humano`, `ia` ou `misturada`.
- Compare com as minhas anotações e relate qualquer diferença.

### 2. A minha variação de verdade

- Nas minhas voltas limpas: o desvio entre voltas no Bico de Pato (2.590 a 3.080 m), a dispersão do ponto de frenagem e do ápice, e a melhor volta.
- O mesmo para as voltas da IA, para comparar.
- Com o meu desvio, recalcule quantas voltas por condição o experimento controlado precisa para detectar 15, 30 e 50 ms com 80 % de chance, no desenho em blocos.
- Use a ferramenta de plano que já existe.

### 3. Detector para as voltas antigas

- **A referência da IA** é a linha das voltas de IA da sessão nova. Calcule a mediana por ponto da grade.
- **Por microsetor, calcule:**
  - a distância lateral até a linha da IA;
  - a distância entre o ponto de frenagem e o da IA.
- **Antes de olhar as voltas antigas**, escolha os limites só com as voltas rotuladas da sessão nova e escreva-os no documento da etapa, num commit próprio. A meta é acertar pelo menos 95 % das voltas de cada origem. O que ficar entre os dois grupos vira `desconhecida`.
- **Uma volta é:**
  - `ia`, quando todos os microsetores parecem IA;
  - `humano`, quando nenhum parece;
  - `misturada`, quando há dos dois.
- **Aplique às 688 voltas válidas e únicas** das duas pastas. Relate, por sessão: quantas voltas de cada origem.
- **Confira com o que eu lembro:** IA em 14/06 a 19/06, em 20/06 e em 09/08, alternando dentro das sessões. Confira também com os sinais do pedido 12 (as 4 sessões que variam mais). Relate onde o detector discorda.
- **Se a separação não for clara**, não force: relate as distribuições e pare.

### 4. Inventário

- Grave os rótulos no inventário novo (`data/ml/origem/`), com a fonte de cada um: `indicador` ou `detector`.
- O inventário e o store em uso continuam como estão.

### Restrições

- Só leia as pastas de gravações e os arquivos do jogo.
- Não treine nem altere o modelo do coach. Não faça merge da branch do pedido 11.
- Não contorne nenhuma trava: se algo bloquear, pare e me avise.
- Não envie nada ao remoto.

### Merge e entrega

- Se a suíte passar, faça o merge de `etapa/detector-ia` em `develop`.
- Em `docs/handoff/`: o patch, a saída do pytest e um JSON com os números das partes 2 e 3.
- `docs/detector_ia.md`, em português simples: a sessão, a minha variação contra a da IA, o novo tamanho do experimento, como o detector funciona, quanto ele acerta e quantas voltas antigas são minhas.

No relatório, apresente as Partes A e B, a conferência da primeira parte da sessão e depois a Parte C, item por item.
