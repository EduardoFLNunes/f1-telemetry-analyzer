Eduardo aqui. Este pedido foi escrito junto com o Claude (Cowork), que faz a revisão e a arquitetura do projeto, e eu aprovo. O plano é meu. Pode executar.

O pedido 17 está aprovado. Três coisas foram ótimas:

- o diagnóstico da C10, relatado fora da regra e sem mudar a regra;
- a conferência de que perda e situação ficaram iguais em todas as curvas depois da emenda;
- o painel saindo a cada atualização.

A emenda de 05/10 (sessão separada por pausa de mais de 3 h e sessão anotada inteira) também está aprovada. Antes de começar, duas correções no relatório da atualização de 05/10:

- **"Você melhorou: a melhor fica 0,8 s abaixo" está errado.** 90,19 s é 0,80 s **mais lenta** que 89,389 s. O que melhorou foi a mediana das voltas válidas. Corrija a frase onde ela tiver ido parar (relatório, painel ou documentos).
- **O store recebeu 7 voltas da sessão nova, mas o relatório lista 8 válidas.** Diga qual ficou de fora e por quê.
- Confirme também que as voltas da sessão anotada ficam com uma `origem_fonte` própria (por exemplo `anotacao_sessao`), e não `indicador` nem `detector`.

Enquanto faço as sessões de treino, começa a etapa M0 do modelo físico do carro. Leia `docs/decisoes/0017-modelo-fisico-do-carro.md`. A ideia é que as voltas que estou gravando agora já guardem os canais físicos, para o modelo do carro (M1) usar depois sem regravar nada. Nada aqui muda o coach nem os critérios do relatório.

## Parte A: documentação

Em `develop`:

1. Substitua `docs/backlog.md` por `docs/prompts/anexos-18/backlog.md`.
2. Substitua `docs/decisoes/README.md` por `docs/prompts/anexos-18/README.md`.
3. Apague a pasta `docs/prompts/anexos-18/`.
4. Commite junto o pedido 18 e o ADR 0017. Mensagem: `docs: ADR 0017 (modelo físico do carro), backlog e pedido 18`.

## Parte B: inventário dos canais físicos

Branch `etapa/canais-fisicos`, a partir de `develop`.

### 1. O que as gravações têm

Nas gravações das sessões `2026-10-04` (7 gravações, app de desenvolvimento) e `2026-10-05` (1 gravação, app instalado), relatando cada app separado, para cada campo abaixo, relate: se existe, a fração de amostras preenchidas, a faixa (p1, p50 e p99) e a unidade provável.

- **Pneus:** `tyreCoreTemperature[4]`, temperatura interna, central e externa (se houver), `tyrePressure[4]`, `tyreWear[4]`, `wheelSlip[4]` e `wheelLoad[4]`.
- **Freios:** `brakeTemp[4]` e a distribuição de frenagem (se houver).
- **Movimento:** as velocidades longitudinal e lateral (se houver), a velocidade angular (guinada), `accG[3]` e `heading`.
- **Suspensão:** `suspensionTravel[4]` e `rideHeight`.
- **Comandos:** `steerAngle` bruto, acelerador, freio, embreagem e marcha.

Confira também no código do gravador quais desses campos são lidos da memória compartilhada mas não são gravados.

### 2. O que falta gravar

Se um campo da lista existe na estrutura que o gravador já lê e não é gravado, acrescente-o ao gravador do repositório, com teste. Não mexa no app instalado. Relate o que entrou e lembre que só as sessões gravadas depois disso terão o campo.

### 3. A unidade do volante

O `steerAngle` gravado não tem unidade documentada; a limpeza aceita ±1,5. Relate:

- a faixa observada nas minhas voltas e nas da IA;
- se os arquivos do carro (`rss_formula_rss_3_v6_2026`) estão abertos e dão o ângulo máximo do volante e a relação de direção. **Se estiverem criptografados, relate e não tente abrir.**
- uma estimativa empírica: abaixo de 80 km/h, nas curvas mais fechadas, a relação entre o `steerAngle` e a curvatura da trajetória. Relate o número e a dispersão; não adote nada ainda.

## Parte C: canais físicos no store v2

Na mesma branch.

### 1. Antes de construir

Registre num commit próprio, em `docs/modelo_fisico_m0.md`:

- **As colunas novas,** reamostradas na grade de 2 m como as outras, uma por roda (FL, FR, RL, RR) quando for o caso:
  - temperatura do núcleo do pneu, carga, escorregamento e pressão;
  - temperatura do freio, se existir;
  - `steerAngle` bruto;
  - guinada e as velocidades longitudinal e lateral, se existirem.
- **Volta sem o campo:** fica com o valor vazio (NaN), e o meta lista os canais de cada volta.
- **O esquema** sobe de versão no meta (por exemplo `esquema: 2.1`). O nome do arquivo continua o mesmo.

### 2. Checagens

| Checagem | Passa quando |
|---|---|
| Nada do que já existe muda | as mesmas voltas do store no início desta etapa (585 no relatório de 05/10), com o mesmo `lap_id`, o mesmo `lap_time_s` e as colunas antigas idênticas |
| Canais novos preenchidos | pelo menos 95% de preenchimento nas voltas da sessão `2026-10-04`, em cada campo que existe na gravação; a sessão `2026-10-05`, do app instalado, é relatada à parte |
| Store íntegro | as checagens do pedido 16 continuam passando |

Se alguma coluna antiga mudar, pare e me relate.

### 3. Custo

Relate o tamanho do store e o tempo do `atualizar_coach`, antes e depois. Se o comando passar de 35 minutos, relate; o modo incremental continua sendo um pedido próprio.

## Parte D: técnica de pilotagem no relatório de evolução

Na mesma branch. É uma medida **descritiva**: não entra em nenhum critério, não muda a "diferença consistente" e não muda o coach.

### 1. Definições, registradas antes de rodar

Registre as definições numa seção nova e datada de `docs/store_v2_e_evolucao.md`, num commit próprio, antes da primeira rodada:

- **Uso da aderência.** Em cada curva e volta, o p95 da aceleração combinada, √(g lateral² + g longitudinal²), no trecho da curva. Por sessão: a mediana e a razão contra a volta da IA.
- **Freio e volante juntos.** Em cada curva e volta, os metros em que o freio está em 0,15 ou mais **e** o volante está em pelo menos 25% do maior volante daquela volta naquela curva. A busca usa a janela de frenagem do pedido 17, do ápice anterior ao ápice da curva. Por sessão: a mediana, e o mesmo número na volta da IA.
- **Freada emendada.** Na curva k, pegue a sequência contínua de freio em 0,15 ou mais que contém o maior freio entre o ápice da curva anterior e o ápice de k. A volta conta como emendada quando essa sequência começa antes do ápice da curva anterior. Por sessão: quantas voltas, de quantas, e o que a IA faz.
- **Temperatura dos pneus.**
  - Por volta: a média dos 4 pneus em s = 0 e ao longo da volta, e a média da dianteira e da traseira.
  - Por sessão: a série volta a volta e a correlação de Spearman entre a temperatura média da volta e o tempo da volta.
  - O relatório escreve, junto da correlação, que ela não separa causa: o pneu esquenta e o piloto melhora ao mesmo tempo.
- **Temperatura dos freios:** só se o campo existir. Por curva e volta, a máxima na frenagem.
- **Volta sem o canal:** fica sem número, contada à parte.

### 2. Saída

- Um bloco `tecnica` no JSON de cada sessão, com o formato documentado.
- **Não mude o painel.** O Claude (Cowork) vai incluir esse bloco nele depois.

### 3. Primeira rodada

Rode nas sessões `2026-10-04` e `2026-10-05` e relate, para cada uma, a C01 (S do Senna), a C10 (Bico de Pato) e um resumo das 14 curvas. Onde a sessão não tiver o canal, a medida fica sem número, como na regra acima.

## Parte E: testes e entrega

- **Testes:**
  - as colunas antigas do store não mudam;
  - as colunas novas existem, e a volta sem o campo fica vazia com o meta certo;
  - freio e volante juntos, numa volta sintética;
  - a freada emendada, numa volta sintética com o começo antes e depois do ápice anterior;
  - a aceleração combinada e a média de temperatura;
  - o bloco `tecnica` não altera a situação de nenhuma curva (regressão nos JSONs das duas sessões).
- **Merge:** se a suíte e as checagens passarem, faça o merge de `etapa/canais-fisicos` em `develop` e rode o `atualizar_coach` uma vez.
- **Em `docs/handoff/`:** o patch, as saídas das suítes, o inventário dos canais em JSON, o relatório do volante, as checagens do store e o bloco `tecnica` das duas sessões.
- **`docs/modelo_fisico_m0.md`,** em português simples:
  - o que é gravado;
  - o que entrou no store;
  - o que se descobriu sobre o volante;
  - como ler as medidas de técnica;
  - o que ainda falta para a M1.

## Restrições

- Não mexa no app instalado nem no store antigo.
- Não abra nem tente abrir arquivos protegidos do carro ou do jogo.
- Nenhum critério de decisão muda neste pedido.
- Não contorne nenhuma trava: se algo bloquear, pare e me avise.
- Não envie nada ao remoto.

No relatório, apresente as duas correções e a fonte das voltas anotadas, a Parte A, o inventário e o que foi acrescentado ao gravador, o volante, o store com as checagens e o tempo, as medidas de técnica das duas sessões e o merge.
