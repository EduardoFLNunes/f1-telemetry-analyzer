# Protocolo da sessão controlada (Fase 2c)

Rascunho para aprovação do Eduardo antes de pilotar. Escrito pelo Claude (Cowork) em 2026-10-02.

> **Suspenso (ADR 0016).** A sessão rotulada de 04/10 mediu a variação real do Eduardo no Bico de Pato: 0,91 s entre voltas, contra 0,012 s da IA. Os 14 a 35 ms usados neste protocolo vinham da IA. Com a variação real, detectar 30 ms exigiria 5.862 voltas por condição, e 8 voltas só detectam efeitos a partir de 0,81 s. A pergunta deste protocolo passa para o caminho em que o próprio jogo executa as variações (ADR 0017, a escrever). O texto abaixo fica como registro.

## Por que esta sessão existe

Nas suas voltas normais, você freia quase sempre no mesmo lugar (a menos de 5 m) e faz quase sempre a mesma linha (a menos de 0,5 m no ápice). Por isso os dados não mostram quanto vale frear antes ou depois, nem mudar a linha: é como tentar descobrir o efeito do sal numa receita em que você sempre usou a mesma quantidade. A solução é variar de propósito, de forma organizada, e medir.

## A curva

**Proposta: Bico de Pato.** É a curva com o tempo mais estável entre voltas nos seus dados, e uma frenagem forte, onde o efeito do ponto de frenagem aparece com clareza.

Variação do tempo do trecho entre voltas, medida pelo Claude (Cowork) em `laps_grid.parquet`. As janelas vão do início de uma frenagem ao início da seguinte, na volta mais rápida, e podem diferir um pouco das janelas da Fase 2b.

| Trecho | Comprimento | Desvio entre voltas, sessão 09/08 (40 voltas) | Sessão 20/06 (22 voltas) |
|---|---|---|---|
| Bico de Pato | 500 m | 14 ms | 35 ms |
| Ferradura | 310 m | 20 ms | 19 ms |
| S do Senna (1º toque) | 228 m | 24 ms | 169 ms |
| Laranjinha | 156 m | 73 ms | 42 ms |

Alternativa: Ferradura, mais estável entre as duas sessões.

## As quatro condições (2 × 2)

| Condição | Ponto de frenagem | Linha de entrada |
|---|---|---|
| A | o seu habitual | a sua habitual |
| B | 10 m mais cedo | a sua habitual |
| C | o seu habitual | cerca de 2 m deslocada para dentro |
| D | 10 m mais cedo | cerca de 2 m deslocada para dentro |

- A mudança de linha é de 2 m porque a referência do modelo tem incerteza de 1,5 a 2,9 m. Uma mudança menor que isso não seria útil para o coach.
- Frear mais cedo, e não mais tarde, mantém a sessão segura e ainda mostra quanto custa cada metro de frenagem antecipada.
- Antes de pilotar, escolha uma referência visual fixa para cada ponto (placa, começo da zebra, uma marca no asfalto) e anote.

## Quantas voltas

- 4 a 6 voltas de aquecimento, que não entram na análise.
- 8 voltas válidas por condição: 32 voltas no total.
- Cada efeito principal (frenagem ou linha) compara 16 voltas contra 16. Com o desvio medido no Bico de Pato (14 a 35 ms), isso detecta diferenças a partir de cerca de 15 a 35 ms, com 80 % de chance. Comparar uma condição isolada com outra (8 contra 8) detecta a partir de cerca de 20 a 50 ms.
- Total: cerca de 40 voltas, algo como uma hora.

## Ordem sorteada

As voltas são feitas em blocos de 4, e cada bloco tem as quatro condições em ordem sorteada (por exemplo: B, D, A, C | C, A, D, B | …). Assim, pneu, combustível e cansaço afetam todas as condições por igual. O plano com a ordem é gerado por script antes da sessão, e você segue a lista.

## Durante a sessão

- Se errar a volta (passar reto, rodar, frear muito fora do ponto), anote o **número da volta mostrado no jogo** como inválida e repita a mesma condição na volta seguinte.
- **Não entre no box durante as voltas do plano.** No box, o contador de voltas do jogo trava e repete números, e aí uma volta anotada como inválida fica ambígua. Se precisar parar, encerre a gravação e comece uma nova quando voltar.
- Faça cerca de 5 voltas de aquecimento além da volta de saída dos boxes. O número exato não importa: o que importa é **anotar o número no jogo da primeira volta do bloco 1**. A análise começa a contar a partir dela.
- **A conferir no Assetto Corsa:** se dá para desligar o consumo de combustível e o desgaste de pneu nas opções de realismo. Se não der, faça a sessão em blocos curtos e reabasteça sempre com a mesma quantidade.
- Grave a sessão normalmente pelo app. Nada muda na gravação.
- **Não use a IA do jogo durante a sessão.** Todas as voltas do plano precisam ser suas.
- **Deixe o coach desligado durante a sessão.** Ele comenta freadas e trechos, e isso pode mudar o jeito como você executa as condições. Como desligar:
  1. Feche o app por completo, inclusive na bandeja do Windows. O app só lê o modelo do coach ao abrir.
  2. Renomeie o arquivo `C:\Users\Dokas\AppData\Roaming\Automobilista Telemetria\data\reference_models\vhe_interlagos.json` (o mesmo que `%APPDATA%\Automobilista Telemetria\data\reference_models\vhe_interlagos.json`) para `vhe_interlagos.json.desligado`. Não apague e não edite o arquivo.
  3. Abra o app e grave a sessão. Sem o modelo, o coach fica calado: o painel continua na tela, mas vazio. A gravação não muda. A análise da volta no app também perde a parte "quanto ainda dá para ganhar", que vem do mesmo arquivo.
  4. Depois da sessão, feche o app de novo e devolva o nome original, `vhe_interlagos.json`.

  O app instalado não traz outra cópia desse arquivo. Ele só traz a linha otimizada (`*.optimal.json`), e por isso não volta a ligar o coach sozinho.

## O que a análise vai responder

1. **Você conseguiu executar as condições?** O script mede o ponto de frenagem e a linha reais de cada volta. Se a diferença real não for perto de 10 m e 2 m, a condição não valeu.
2. **Quanto custa frear 10 m mais cedo** nesse trecho, com faixa de incerteza.
3. **Quanto vale a mudança de linha**, e se os dois efeitos se somam ou interagem (a pergunta da dupla contagem).
4. **Os estimadores da Fase 2b acertam?** Comparamos o efeito medido com o que E1 a E4 teriam previsto para as mesmas mudanças. É a primeira validação real de um ganho contrafactual no projeto.
