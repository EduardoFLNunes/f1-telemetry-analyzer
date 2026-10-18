# Pedido 33 — Relógio do gravador novo: por que algumas voltas fecham 10 a 12 ms longe do cronômetro do jogo

**De:** Eduardo. **Data:** 18/10/2026.
**Tipo:** diagnóstico e, só se a causa for um defeito de código, a correção. Nenhum critério muda: o limite de 5 ms da checagem continua, e nenhuma volta sai do store.

**Ordem:** este pedido vem antes do pedido 31 (ADR 0008).

## Contexto

Está no fim do relatório do pedido 32 (seção "Parte G com o pacote instalado"):

1. **A rodada de 18/10 parou no passo 6.** A checagem `store_checks.check_period` pede que o p99 de |período de s = 0 a s = 0 − tempo do jogo| fique em até 5 ms. Antes era 4,60 ms, em 648 voltas; agora é **7,63 ms**, em 676. O store ficou gravado com `aprovado: false`, e o relatório de evolução continua o de 16/10.
2. **As voltas do app antigo fecham perto do cronômetro do jogo:** mediana de cerca de 1,2 ms e pior de 2,7 ms.
3. **As voltas do gravador novo (0.3.0 e 0.4.0)** têm mediana boa, de 0,8 a 1,1 ms, mas 5 de 39 ficam entre 10 e 12 ms. Uma delas é a `2026-10-17_16-17-08#0007`, com 11,74 ms.
4. **Por que isso importa além da checagem:** a M1 é um modelo do carro para a frente, do estado agora para o estado daqui a Δt (ADR 0017). Se o tempo e a posição de uma amostra às vezes vêm de instantes diferentes, o erro entra no dado de treino da M1. Por isso quero a causa, e não uma mudança no limite.
5. **A contagem oficial da M1 dá 3 de 5,** lida de um store com `aprovado: false`. Trate esse número como provisório até a checagem passar.

## Princípio, fixado antes de olhar mais dados

- **O limite de 5 ms e as checagens não mudam.** Nenhuma volta é tirada do store.
- **Só se corrige o que for defeito de código** (gravador, corte em voltas ou interpolação na linha), com o antes e depois nas mesmas gravações.
- **Se a causa for o próprio jogo,** pare e relate. Mudar o critério é decisão minha, e só depois do diagnóstico.

## Parte A — Diagnóstico (só lendo as gravações)

1. **As voltas acima de 5 ms** e algumas boas das mesmas sessões, perto da passagem pela linha. Mostre, amostra a amostra:
   - o cronômetro do jogo;
   - o horário do gravador;
   - o contador de voltas;
   - a distância na volta e a posição;
   - o intervalo entre amostras.

   Diga se o tempo e a posição de cada amostra vêm do mesmo passo de física do jogo. Se o gravador guarda o `packetId` das páginas da memória compartilhada, use-o.
2. **O que mudou no gravador** entre o 0.1.7 e o 0.3.0 em diante, no laço de leitura e escrita. Por exemplo:
   - os campos novos do pedido 18;
   - a ordem de leitura das páginas;
   - a conferência incremental da Coleta, que lê o arquivo a cada 5 s;
   - a identidade do app no metadado.

   Diga o que pode atrasar uma leitura ou separar o tempo da posição.
3. **O intervalo entre amostras,** sessão a sessão, no app antigo e no novo: a distribuição, as amostras repetidas e as que faltam.
4. **A causa,** numa destas classes, com a evidência:
   - **gravação:** a amostra gravada mistura instantes, e o erro fica no arquivo;
   - **processamento:** o corte em voltas ou a interpolação na linha erram, e o arquivo está certo;
   - **o jogo:** o próprio cronômetro do jogo varia.
5. **O efeito na M1:** a fração de amostras com Δt irregular nas sessões novas e nas antigas, e o tamanho do erro de estado que isso produz.

## Parte B — Correção (só se a Parte A achar um defeito de código)

1. **Se for processamento:**
   - corrija o corte ou a interpolação;
   - rode o `atualizar_coach`. A checagem tem de passar com o limite de 5 ms;
   - compare o período de todas as voltas antigas, antes e depois. Nenhuma pode piorar.
2. **Se for gravação:**
   - corrija o gravador para as sessões futuras, por exemplo lendo o tempo e a posição do mesmo retrato da memória compartilhada;
   - diga se as gravações que já existem podem ser corrigidas no processamento, sem tirar volta;
   - se puderem, faça isso e rode o `atualizar_coach`;
   - se não puderem, pare e relate as opções;
   - **gere o instalador `0.4.1`** com o gravador corrigido e pare para eu instalar, porque gravo pelo app instalado.
3. **Se for o jogo:** pare e relate. Não mude nada.

## Parte C — Cuidados de processo

Valem a partir deste pedido:

1. **Janelas de teste:**
   - toda janela do app aberta para teste ou captura tem "[teste]" no título;
   - toda janela de teste é fechada ao fim de cada pedido.

   Em 15/10 e 17/10, gravei em janelas de teste que ficaram abertas e tinham o mesmo título do app instalado.
2. **Travas do git:** um `index.lock` ou outra trava não é apagado. Pare e me pergunte, como manda o CLAUDE.md. No instalador 0.4.0, a trava foi removida sem perguntar.

## Testes

- **se houver correção no processamento:** o caso de uma volta com a passagem pela linha entre duas amostras com Δt irregular;
- **se houver correção no gravador:** o tempo e a posição saem do mesmo passo de física;
- **as suítes:** a do backend e os testes do front continuam passando.

## Regras gerais

- **Nenhum critério muda:** limite da checagem, portões, regras do coach e do store ficam como estão. Nenhuma volta sai do store.
- **As gravações são só lidas.** Nenhuma é mudada, movida ou apagada.
- **Não mexa no app instalado nem em arquivos do jogo.**
- **Não instale nem atualize pacotes.**
- **Não contorne nenhuma trava:** se algo parar, pare também e registre o motivo.
- **Branch e commits:** branch `etapa/relogio-do-gravador`, commits por parte, merge em `develop`. Sem push.
- **Uma sessão de implementação por vez** (ADR 0008).
- **Relatório** em `docs/handoff/2026-10-18_33_relogio-do-gravador-novo_relatorio.md`, como manda o CLAUDE.md, com:
  - as amostras perto da linha nas voltas ruins e nas boas;
  - a causa, com a evidência;
  - o efeito na M1;
  - a correção e o antes e depois, se houver;
  - a saída dos testes e os commits.
- Se algo do contexto não bater com o repositório, pare e registre no relatório.
