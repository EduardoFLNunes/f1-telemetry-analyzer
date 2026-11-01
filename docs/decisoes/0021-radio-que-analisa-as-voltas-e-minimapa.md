# 0021 — O rádio analisa as voltas e diz onde e por que o piloto perde tempo; o app do jogo ganha um minimapa

- **Status:** aceita
- **Data:** 2026-10-18
- **Decisor:** Eduardo
- **Refina:** 0020 (item 4, "quanto", e a consequência sobre cada uso novo do app)

## Contexto

1. **O teste do rádio de 18/10** (`data/radio/2026-10-18_12-38-44_vhe_interlagos.jsonl`), em 15 voltas:
   - 13 mensagens foram o resumo na linha, só com o tempo da volta e a diferença para a IA;
   - só 2 foram frases do coach (C11 na volta 4 e C08 na volta 10);
   - a fala da frase do coach não diz o porquê. O cartão tinha "mínima da IA 94 km/h, a sua 64 km/h", mas a voz disse só "Curva 11, esquerda: 1,25 atrás da IA".
2. **O que o piloto pediu depois do teste:**
   - que o rádio analise algumas voltas e diga onde ele perde tempo e o que faz diferente da IA, em voz e na tela;
   - um minimapa dentro do jogo, comparando a volta dele com a volta da IA.
3. **O ADR 0020 limita o rádio** às 3 frases por volta do coach mais o resumo na linha, e deixa cada uso novo do app do jogo para um pedido próprio.
4. **O coach já mede o que a análise precisa:** o tempo por microssetor contra a referência, o ponto de freada e a mínima (o `evidence` de cada frase). A grade do store tem também o acelerador e a posição lateral.

## Decisão

1. **Um tipo novo de mensagem: a análise das voltas.**
   - **Quando:** a cada 3 voltas válidas da sessão, sobre essas 3 voltas.
   - **O que diz:**
     - até 2 curvas (C01 a C14) com a maior perda mediana contra a referência escolhida;
     - só entra uma curva perdida em pelo menos 2 das 3 voltas;
     - para cada curva, as diferenças medidas que mais pesam: o ponto de freada (m), a mínima (km/h), a volta ao acelerador cheio (m) e o traçado (a posição lateral, em metros e com o lado por extenso, ADR 0003).
   - **Como diz:**
     - a diferença medida contra uma volta real, nunca um ganho prometido (ADR 0012);
     - na voz, até cerca de 8 s;
     - no cartão, as curvas com os números.
   - **Onde:** numa janela de rádio, nunca dentro das 14 curvas.
2. **A frase do coach passa a dizer a causa principal na voz:** a freada ou a mínima, quando o `evidence` tiver. A frase continua curta, de até cerca de 6 s.
3. **O resumo na linha passa a dizer a curva em que a volta mais perdeu,** além do tempo e da diferença.
4. **O que não muda:**
   - o coach decide as frases: o foco, o limiar e no máximo 3 por volta (ADR 0012 e 0016);
   - a análise é no máximo uma a cada 3 voltas válidas.
5. **O minimapa no jogo:**
   - é uma janela 2D do app do jogo, num canto, sem cobrir o centro da tela;
   - mostra a pista, o carro, o fantasma da referência escolhida e a diferença ao vivo;
   - a posição do carro vem do próprio jogo, a cada quadro;
   - a volta de referência é baixada do backend uma vez, quando o app abre ou a referência muda;
   - não desenha na pista: o desenho 3D continua fora (ADR 0020).
6. **A voz no jogo:** se o áudio não tocar pela URL do backend, o app do jogo pode guardar o áudio baixado **só dentro da sua própria pasta** (`apps\lua\<nome do app>\`), numa subpasta que ele mesmo limpa. Nenhum outro lugar do jogo é tocado.
7. **O registro:** cada análise vai para `data/radio/<sessão>.jsonl`, com as curvas, a perda em cada uma das 3 voltas, as diferenças ditas e a referência. Isso permite medir depois se a curva citada melhorou nas voltas seguintes, que é a avaliação do Modelo 2.

## Consequências

- **As sessões passam a ter três estados para a avaliação do Modelo 2:**
  - sem rádio no jogo (até 18/10; nessa data, o app do jogo estava calado por um defeito, corrigido depois);
  - com o rádio do pedido 31;
  - com o rádio desta decisão.
- **O piloto ouve mais:** até 3 frases por volta, o resumo e uma análise a cada 3 voltas válidas. Se incomodar, a cadência da análise é o primeiro ajuste.
- **O minimapa custa processamento dentro do jogo.** O custo é medido no teste no jogo, com o app ligado e desligado.
- **A exceção do ADR 0020 continua do mesmo tamanho:** só a pasta do app, só pelos scripts. A única gravação nova é a do próprio app, dentro dessa pasta.

## Atualizações

- **22/10/2026 (pedido 36), a volta com rodada:** a volta em que uma curva perde mais de 5 s contra a referência (uma rodada ou uma saída de pista) não conta para a análise das voltas, e o resumo dela não cita a curva. É uma regra só do rádio: o coach, o store e as regras de volta válida do store não mudam.
- **22/10/2026 (pedido 36), a voz:** a 1,4x, aprovada pelo Eduardo (era 1,25x no pedido 31).
- **22/10/2026 (pedido 36), o replay da curva e as marcas de freada:** o app do jogo ganha uma quarta janela, "Replay da curva": a curva de que o rádio fala (a análise ou a frase do coach com causa), vista de cima, com a sua linha e a da referência, os dois carros cada um no seu tempo, as freadas, as mínimas, o traçado e o tempo perdido. Aparece na reta junto com a fala e some quando a janela de rádio acaba; nos boxes ou pausado, mostra a última análise em repetição. Os dados vêm de `/api/radio/replay/<id>`, só com as grades que o rádio já tem. Os dois mapas marcam a freada da IA pela regra do relatório de evolução: o minimapa só a da próxima curva, o mapa aproximado todas as da janela, com o rótulo. A gravação do app continua só dentro da pasta dele.
- **29/10/2026 (pedido 43), os números da voz no replay e os 4 visuais:** no replay de uma frase do coach, todo número escrito é o da voz, arredondado como no cartão (a freada, as mínimas e o tempo), e as marcas ficam onde o coach mediu: as freadas nos inícios de frenagem que o coach guardou e as mínimas no ponto mais lento do microssetor da fala. O microssetor aparece como "trecho da fala". O coach não mede o traçado, e o replay da frase não tem traçado. As linhas e os carros continuam os da curva inteira; a janela só cresce para conter o trecho da fala. Na análise das voltas, nada muda. Sob a animação, no jogo e na tela Ao vivo, entram a faixa do pedal, a diferença acumulada e a velocidade pela distância, com os dados da mesma rota do replay. A grade da sessão (a perda por curva das voltas válidas, a mesma da análise, com as curvas citadas) entra na tela Ao vivo e, nos boxes ou pausado, na janela grande do jogo (`GET /api/radio/grade`). Nenhum modelo, store ou critério do coach muda.
