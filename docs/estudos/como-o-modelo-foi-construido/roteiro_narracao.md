# Roteiro de narração: "Como o modelo foi construído"

Vídeo de 3:15, sem áudio. As legendas abaixo estão gravadas no vídeo e podem ser lidas como narração. Os tempos são do início de cada frase.

## 0:00 · A pergunta

- **0:03** Em roxo, a IA do próprio jogo. Em laranja, o piloto. Mesmo carro, mesma pista.
- **0:09** A diferença é de 4,6 s por volta. O projeto quer entender de onde ela vem.

## 0:15 · Os dados

- **0:15** O jogo é lido dezenas de vezes por segundo. Mas as amostras caem em lugares diferentes a cada volta.
- **0:21** Então cada volta vira uma régua: um ponto a cada 2 metros, sempre 2.167 pontos por volta.
- **0:27** O ponto 500 é o mesmo lugar da pista em qualquer volta. Agora dá para comparar ponto a ponto.

## 0:32 · A pista

- **0:32** A pista é cortada em 60 pedaços de uns 72 metros. Eles dizem onde o tempo foi perdido.
- **0:39** E em 14 curvas, que ajudam a explicar por quê: onde freou, por onde passou e com que velocidade.

## 0:46 · Peça a

- **0:46** A peça A é uma rede neural do tipo LSTM. Ela lê a pista ponto a ponto e guarda uma memória do que já viu.
- **0:52** Pedindo “perda zero”, ela desenha uma volta de referência: onde estar e quanto frear em cada ponto.
- **0:57** No teste, ela erra 1,5 m em média. Erra pouco nas voltas rápidas e muito nas lentas.

## 1:05 · Peça d

- **1:05** A peça D tenta responder uma pergunta difícil: e se eu frear 10 metros depois?
- **1:12** Essa volta nunca aconteceu. D precisa estimar o tempo dela, sempre com margem de erro.
- **1:17** A conta vale para a curva inteira, da frenagem ao fim da reta: frear tarde pode ganhar na entrada e perder na saída.

## 1:23 · A régua

- **1:23** Antes de cada teste, as regras são escritas e travadas. Ninguém muda a régua depois de ver o resultado.
- **1:29** A nota compara cada modelo com um chute ingênuo: dizer que nada muda. Abaixo de zero, o modelo atrapalha.
- **1:34** Dois testes, oito tentativas. Nenhuma chegou à meta de 0,20.
- **1:40** Resultado negativo também é resultado: ele foi registrado e explicado.

## 1:45 · A virada

- **1:45** Então veio a virada: muitas sessões antigas foram gravadas com o carro entregue à IA do jogo.
- **1:51** A IA freia sempre no mesmo lugar: varia 1 metro. O piloto varia quase 15 metros.
- **2:00** Aquela consistência que travava os testes era da IA. Os dados precisavam dizer quem pilotava.

## 2:07 · Arrumando os dados

- **2:07** Agora cada volta tem origem: piloto, IA, misturada ou desconhecida.
- **2:13** Um detector usa três sinais: a linha, os pontos de frenagem e o tempo. Só rotula quando os três concordam.
- **2:18** E só contam as voltas humanas com o equipamento atual: volante e pedais novos, desde 01/10.

## 2:24 · O coach de hoje

- **2:24** Hoje, a ferramenta desta fase é o coach. Ele compara a volta com uma volta real da IA.
- **2:30** Fala só nos 3 trechos onde o piloto mais perde, no máximo 3 frases por volta.
- **2:36** E nunca promete ganho: diz apenas o que foi medido.

## 2:42 · Peça c

- **2:42** A autocorreção vem por último, porque depende da peça D.
- **2:48** Ela propõe ajustes pequenos, suaves e locais: uma curva por vez.
- **2:53** E só aceita quando o ganho estimado é maior que a incerteza. Se não, responde: não conclusivo.

## 2:59 · Resumo

- **2:59** Resumo: medir, o sistema já mede bem. Prever quanto se ganharia ainda não passou na régua.
- **3:05** Próximos passos: treinar até o tempo estabilizar, retreinar a peça A com voltas humanas e refazer o “e se?”.
