# Protocolo da sessão controlada (Fase 2c)

Rascunho para aprovação do Eduardo antes de pilotar. Escrito pelo Claude (Cowork) em 2026-10-02.

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

## O que a análise vai responder

1. **Você conseguiu executar as condições?** O script mede o ponto de frenagem e a linha reais de cada volta. Se a diferença real não for perto de 10 m e 2 m, a condição não valeu.
2. **Quanto custa frear 10 m mais cedo** nesse trecho, com faixa de incerteza.
3. **Quanto vale a mudança de linha**, e se os dois efeitos se somam ou interagem (a pergunta da dupla contagem).
4. **Os estimadores da Fase 2b acertam?** Comparamos o efeito medido com o que E1 a E4 teriam previsto para as mesmas mudanças. É a primeira validação real de um ganho contrafactual no projeto.
