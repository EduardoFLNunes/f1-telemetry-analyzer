# Pedido 52: proposta do engenheiro que ensina (os três níveis, a análise depois da curva, o escopo e o treino)

- **Origem:** os pedidos do Eduardo no chat de 22/11, às 22h30 e às 22h47. Esta proposta é para virar um pedido novo (ou uma atualização do 52); **nenhum código mudou.**
- **Branch:** `etapa/engenheiro`. O pedido 52 ainda tem pendentes o teste no jogo com o app 0.9.1, o merge em `develop` e o instalador 0.9.0.

## O que o Eduardo pediu

1. **Três níveis de explicação, à escolha do piloto:**
   - **iniciante:** a frase longa e detalhada, como a da C04;
   - **amador:** mais resumida;
   - **pro:** técnica.
2. **Depois da curva,** o engenheiro analisa como o piloto fez e diz onde ele errou, comparado com o que foi dito.
3. **Chaves:** uma para ligar o engenheiro e outra para o escopo: uma curva, algumas curvas ou a volta inteira.
4. **O treino:**
   - o piloto dá X voltas, e o Modelo 2 analisa cada uma;
   - no fim, o engenheiro manda: volta lenta e boxes, voltas lentas ou uma volta lenta;
   - a escolha depende do volume do relatório.
5. **A frase se adapta:** se a volta de referência mudar, a frase da curva muda junto. Ela é montada pelos dados, nunca escrita à mão.

## Como isso encaixa no que já existe

- **A ficha de 21/11** (`core/engenheiro/ficha.py`) já monta a frase da curva pelos dados.
- **Os três níveis** são três moldes do mesmo conjunto de medidas. Cada pedaço da frase sai de uma medida da volta de referência:
  - o lado da chegada;
  - o ponto de frenagem entre as placas;
  - se a frenagem é reta;
  - o ponto de virar pela zebra;
  - o trecho sem pedal;
  - a mínima;
  - a distância até a borda no ápice;
  - onde volta ao acelerador;
  - o lado da saída;
  - a curva seguinte.

  Se a referência mudar, as medidas mudam e a frase também.
- **A conferência de 21/11** já mede uma coisa depois da volta: a frenagem, o pé embaixo ou a mínima. A análise depois da curva estende isso às mesmas medidas da ficha, fase por fase, e compara com o que foi dito.
- **O Modelo 2** (ADR 0023) é quem diz o erro: a comparação por fase da curva, os detectores de técnica e o tempo que cada diferença custou. O engenheiro é o caminho dele até o piloto (ADR 0033).
- **A volta lenta** (ADR 0033, item 6) e a **janela dos boxes** com o replay (pedido 45) já existem. O fim do treino usa as duas.

## Um exemplo real: a C04 nos três níveis

As medidas da volta de referência (a IA na linha do projeto, 1:24,552):

| fase | o que a referência faz |
|---|---|
| chegada | 3 m à direita do meio, a 270 km/h |
| frenagem | a 1.216 m, 11 m antes da placa de 100; reta; de 270 para 180 km/h em 70 m |
| virar | a 1.310 m, no começo da zebra da esquerda |
| sem pedal | uns 30 m |
| mínima | 133 km/h, perto do ápice, a 2,6 m da borda de dentro |
| acelerador cheio | a 1.390 m |
| saída | a 1,3 m da borda direita |
| C05 | de pé embaixo, a 190 km/h |

**Antes da curva, o que o engenheiro diz:**
- **Iniciante:** "Curva quatro. Venha pelo lado direito. Freie forte e reto quase na placa de 100. Solte o freio e vire no começo da zebra da esquerda. Deixe o carro rolar sem acelerar até uns 135 por hora, perto da borda de dentro. Acelere cedo e use a pista toda na saída, porque a cinco é de pé embaixo."
- **Amador:** "Quatro: pela direita, freie forte quase no 100, vire no começo da zebra, mínima de 135, acelere cedo e abra na saída."
- **Pro:** "Quatro: frenagem a 10 do 100, reta, de 270 para 180 em 70 metros. Entrada na zebra, um segundo de rolagem, mínima 133 a dois e meio da borda. Gás cheio 10 metros depois do ápice, saída na borda."

**Depois da curva, o que ele diria:** uma passagem sua real, a volta 7 de 12/11 (1:27,96), comparada com a referência:

| fase | referência | você | a diferença |
|---|---|---|---|
| frenagem | 1.216 m, a 270 km/h | 1.170 m, a 255 km/h | 46 m antes, 15 km/h mais devagar |
| virar | 1.310 m | 1.320 m | 10 m depois |
| mínima | 133 km/h, a 1.380 m | 111 km/h, a 1.330 m | 22 km/h a menos, 50 m antes |
| ápice | 2,6 m da borda | em cima da zebra (0 m) | por dentro demais |
| acelerador cheio | 1.390 m | 1.388 m | igual |
| saída | 1,3 m da borda direita | 3,9 m da borda | não usou a pista toda |

Com essa passagem, a fala seria:
- **Iniciante:** "Na quatro você freou cedo, uns 45 metros antes do ponto, e por isso chegou devagar: a sua mínima foi 111, a da referência é 135. Você também subiu na zebra de dentro e não usou a pista toda na saída. Na próxima, segure o freio até quase a placa de 100."
- **Amador:** "Quatro: freou 45 metros cedo, mínima 111 contra 135, saída sem usar a pista."
- **Pro:** "Quatro: freio menos 46 metros, mínima menos 22 a menos 50 metros, ápice na zebra, saída 2,6 metros por dentro."

## O que precisa de decisão (com a minha recomendação)

1. **Onde fica cada nível de fala:** a explicação longa do iniciante (10 a 30 s por curva) não cabe dentro da volta.
   - **Recomendo:**
     - iniciante: a explicação longa na volta lenta ou nos boxes, e na volta rápida só o lembrete curto e os bipes;
     - amador: a frase resumida na reta longa, como a ficha de hoje;
     - pro: a frase técnica na reta longa, mais curta.
2. **Quando a análise depois da curva é dita:**
   - **Recomendo:**
     - amador e pro: no primeiro pedaço livre depois da curva, com uma frase curta (3 a 5 s), se couber;
     - senão, no resumo da linha;
     - iniciante: na volta lenta ou nos boxes, com a explicação inteira.
   - Isso respeita a folga de 3,0 s antes da próxima ação.
3. **"Onde errou" mede o quê:** as seis fases da tabela acima, com o tempo que cada uma custou (Modelo 2). A fala cita só as diferenças acima do ruído, no máximo duas por curva no amador e no pro, e sempre a maior primeiro.
4. **O escopo:**
   - **uma curva:** a curva de foco de hoje, com a troca por aplicar ou por 3 voltas;
   - **algumas curvas:** o piloto escolhe a lista;
   - **a volta inteira:** todas as curvas.

     Para não voltar o "muita informação", recomendo: na volta rápida, só o lembrete e os bipes de cada curva; a frase completa vai para a volta lenta.
5. **As chaves:**
   - **Recomendo:** na janela "Engenheiro" do jogo, botões para:
     - ligar e desligar o engenheiro;
     - o nível;
     - o escopo, com a lista das curvas;
     - o treino, com o número de voltas.
   - A escolha fica guardada no backend e também aparece no app do Windows.
6. **O treino:**
   - **as voltas:** X voltas, com o padrão de 5;
   - **a análise:** o Modelo 2 analisa cada uma, com as mesmas medidas e o tempo perdido por fase;
   - **o volume do relatório** é o tempo de fala para explicar o que achou, no nível escolhido;
   - **a regra do fim** (os limites são para você fixar):
     - cabe numa volta lenta (até uns 60 s de fala): "dê uma volta lenta";
     - cabe em duas ou três: "dê N voltas lentas";
     - passa disso: "volta lenta e boxes", e a explicação vai para a janela dos boxes com o replay de cada curva.
7. **A frase que se adapta:**
   - Cada pedaço da frase precisa de um limite fixado no ADR antes do código:
     - "quase na placa": até quantos metros antes dela;
     - "acelere cedo": até quantos metros depois do ápice;
     - "perto da borda" e "use a pista toda": a que distância da borda.
   - Com eles, a mesma regra vale para qualquer curva e qualquer pista, e uma volta de referência nova muda as frases sozinha.
   - Continuam de fora:
     - a dosagem dos pedais da IA (ADR 0032);
     - a marcha, até ser conferida.
8. **A ordem:**
   - **Recomendo:** terminar o 52 primeiro: o teste da 0.9.1, a leitura, o merge e o instalador.
   - Depois, um pedido 53 com estas decisões, porque é uma sessão de implementação por vez (ADR 0008).
