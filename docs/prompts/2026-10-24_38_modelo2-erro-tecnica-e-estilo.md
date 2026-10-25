# Pedido 38 — Modelo 2: o erro que custou tempo, as técnicas e o estilo, nas voltas da IA e do piloto

**De:** Eduardo. **Data:** 24/10/2026.
**Tipo:** ML offline (`backend/ml/`) e documentação. Nada do app, do rádio, do coach, do store v2 ou do relatório de evolução muda.

**Ao mandar executar este pedido, eu aprovo o ADR 0023** (`docs/prompts/anexos-38/0023-modelo-2-quatro-pecas-ia-e-piloto.md`): as quatro peças do Modelo 2, aplicadas às voltas da IA e às do piloto.

**Quando começar:** no chat dos modelos, **depois que o pedido 37 (M1) fechar** (ADR 0008). O ângulo de subesterço usa a unidade do volante e o entre-eixos que a M1 identifica. Os cuidados de processo do pedido 33 (Parte C) valem aqui.

## Contexto

1. **O problema:** ensinar onde e quando frear não basta. Sem os conceitos técnicos, eu continuo perdendo tempo. O Modelo 2 precisa achar o erro, ver que técnica eu aplico e qual eu não aplico, e conhecer o meu estilo.
2. **A pesquisa de 24/10** (`docs/tecnica_de_pilotagem_pesquisa.md`) tem:
   - o catálogo de técnicas e erros;
   - **duas tabelas que ligam cada técnica e cada erro a um indicador** calculável com os canais do Assetto Corsa (seção "Cada técnica deixa uma assinatura mensurável…");
   - as dimensões de estilo (seção "O estilo de um piloto…");
   - o desenho do Modelo 2 em 8 etapas (seção "Desenho do Modelo 2").

   **Leia essas seções antes de começar.** Este pedido implementa as etapas 0 a 5 sobre as voltas já gravadas, sem falar com o piloto.

   A pesquisa de datasets de 24/10 (`docs/tecnica_de_pilotagem_datasets.md`) completa a de técnica: que medidas são comparáveis entre carros, como a IA do Assetto Corsa funciona e o que medir nela.
3. **A lista viva do tema** (`docs/tecnica_de_pilotagem_lista.md`) tem os objetivos que este pedido cobre:
   - **E1:** o erro que me fez perder tempo contra a IA;
   - **E2:** as técnicas que a IA usa e as que eu uso;
   - **E3, parte (a):** a assinatura de estilo da IA e a minha, no nosso dado.

   O estilo com dados externos e o KNN (E3, partes b a d, e E4) ficam para um pedido próprio, depois da pesquisa de datasets.
4. **Os dados:**
   - **as minhas voltas:** as voltas `humano` com o equipamento atual, no store v2 e nas gravações. As 5 sessões da M1 têm todos os canais;
   - **as voltas da IA:** as 13 voltas `ia` rotuladas, de 04/10. **Elas não têm a guinada, as velocidades no referencial do carro nem a temperatura dos freios**, porque foram gravadas antes do pedido 18 (`docs/modelo_fisico_m0.md`, seção 4);
   - **a sessão da IA de 22/10** (`2026-10-22_09-46-01`) tem uma volta completa da IA com todos os canais, mas é uma volta só.
5. **Cuidados que a pesquisa registrou:**
   - freio e acelerador vão de 0 a 1, então limiares publicados em pressão não se transferem;
   - o escorregamento das rodas do jogo mistura os componentes longitudinal e lateral;
   - a presença de ABS no carro não está confirmada;
   - as taxas (aplicação do freio, velocidade do volante, reversões) são calculadas nos dados originais, com o cronômetro do jogo (ADR 0022), e só depois levadas à grade de 2 m;
   - a IA não é ótima nem humana: uma diferença contra ela é uma diferença, não um defeito.

## Parte A — Registrar antes de construir

Num commit próprio, antes de rodar qualquer coisa nas voltas:

1. **O ADR 0023:**
   - copie o anexo para `docs/decisoes/`;
   - acrescente a linha em `docs/decisoes/README.md`;
   - apague `docs/prompts/anexos-38/`.
2. **`docs/modelo2_tecnica_e_estilo.md`, seção 1, "Registrado antes de construir":**
   - **as fases de cada curva** e como as fronteiras são definidas;
   - **cada detector:** a técnica ou o erro, o indicador, a regra de "aplica", "não aplica" e "não conclusivo", os limiares iniciais com a fonte e **como eles são calibrados** nas voltas de referência da mesma curva;
   - **a regra de atribuição do erro** (Parte D);
   - **as dimensões de estilo,** com a definição de cada uma e quais canais ela usa;
   - **o modelo supervisionado leve:** a forma, as entradas e a validação;
   - **o que se espera,** em uma frase, antes de ver qualquer número.
3. **Nada disso muda depois de ver os resultados.** Se algo tiver de mudar, registre o motivo numa seção nova, com a data, sem apagar a original.

## Parte B — Os dados e uma sessão nova da IA

1. **As voltas:** as minhas (`humano`, equipamento atual) e as da IA (`ia`, rotuladas pelo indicador ou por anotação). As de origem `desconhecida` ou `misturada` ficam fora (ADR 0014 e 0018).
2. **Para cada volta, relate** quais canais ela tem: guinada, velocidades no referencial do carro, cargas e escorregamento das rodas, temperatura de pneus e freios, volante, pedais e marcha.
3. **A conferência dos canais,** antes de qualquer detector:
   - o desvio do volante em linha reta;
   - os sinais numa curva à esquerda e numa à direita;
   - a unidade do volante e o entre-eixos: use o resultado da M1 (pedido 37). Uma reportagem dá 2.943 mm de entre-eixos para este carro, sem confirmação do fabricante; compare com o valor da M1 e relate;
   - **o escorregamento das rodas:** se é longitudinal, lateral ou combinado, olhando trechos de frenagem em linha reta e trechos de curva sem pedal;
   - **o ABS:** se há sinais de ABS no carro (ciclos de pressão ou de escorregamento na frenagem forte).
4. **A sessão nova da IA:** escreva no relatório os passos para eu gravar, com o app do repositório, a IA dirigindo sozinha na pista, no mesmo carro, para ter as voltas da IA com todos os canais:
   - **em 2 ou 3 níveis de força** (por exemplo, 100%, 95% e 90%), com 6 a 8 voltas em cada um;
   - **com a agressividade e a variação fixas** e anotadas;
   - **o nível, a agressividade e a variação de cada bloco** anotados num arquivo que o código lê.

   **Por que os níveis:** a IA em níveis diferentes é o mesmo "piloto", com a mesma linha e os mesmos coeficientes, em ritmos diferentes. Se uma medida de estilo muda só com o nível, ela mede ritmo, não estilo (o teste do nível de força da pesquisa de datasets, `docs/tecnica_de_pilotagem_datasets.md`).

   Se essa sessão já existir quando você chegar aqui, use-a. Se não, siga com o que há e marque "não conclusivo" onde faltar canal na IA.
5. **Os coeficientes da IA:** se o `ai.ini` do carro existir em texto em `content/cars/rss_formula_rss_3_v6_2026/data/`, só leia e registre os valores (entre eles o TRAIL_HINT, a tendência a fazer trail braking). **Não abra nem desempacote o `data.acd`.** Se o arquivo só existir dentro dele, registre isso e siga.

## Parte C — As fases das curvas

1. **As 14 curvas** (C01 a C14, os trechos que o rádio e o relatório de evolução já usam) divididas em fases: frenagem, entrada, meio, saída e reta seguinte.
2. **As fronteiras** são definidas uma vez, na geometria oficial, e valem para todas as voltas: pela curvatura da linha de referência, pelas regras de pedal e volante da pesquisa (seção "Cada técnica…", o sistema especialista), ou pelas duas. Justifique a escolha.
3. **Relate** as fronteiras de cada curva em metros.

## Parte D — 1º objetivo: o erro que me fez perder tempo contra a IA

1. **A perda por curva e por fase,** contra a volta da IA de referência do coach, somada na grade de 2 m. Também contra a minha melhor volta, ao lado.
2. **As regras do ranking:**
   - a perda conta quando aparece em pelo menos 2 das últimas 3 voltas válidas da sessão;
   - o peso da curva é o comprimento da reta seguinte;
   - se a dispersão das minhas voltas ou do meu ponto de frenagem estiver alta, o primeiro item é a consistência.
3. **A cadeia causal:** uma perda na saída com a retomada tardia e a mínima baixa é procurada na entrada. Um ganho com a frenagem tardia seguido de uma perda maior na entrada é classificado como **falso ganho**, não como melhora.
4. **A atribuição do erro:** para cada (curva, fase) com perda, que detector da Parte E difere entre mim e a IA, com o tamanho da diferença. Se nenhum explicar, a saída é "não conclusivo".
5. **A saída,** por sessão: os 3 maiores erros, cada um com a curva, a fase, o tempo perdido, a diferença de técnica que o explica e a referência usada.

## Parte E — 2º objetivo: as técnicas que a IA usa e as que eu uso

1. **Os detectores,** um por técnica ou erro, das duas tabelas da pesquisa. No mínimo:

   | família | detectores |
   |---|---|
   | frenagem | ponto de frenagem e dispersão; frenagem no limiar (tempo até o pico, pico relativo); perfil com carga aerodinâmica (pico cedo e pressão caindo); soltura (taxa no fim da soltura, queda da carga dianteira); trail braking (retenção, sobreposição com o volante, coordenação); travamento de roda; sobreposição de pedais e pé esquerdo; reduções de marcha |
   | entrada e equilíbrio | ponto e taxa de entrada; subesterço (ângulo de subesterço); sobresterço (ângulo de deriva do veículo); contraesterço e reversões do volante; suavidade do volante |
   | meio e saída | uso do círculo de atrito; traçado e ápice; forma em V ou U; uso da largura da pista; fase sem pedal; retomada do acelerador; acelerador cedo (volante crescendo depois da retomada); alívio depois da retomada; patinação e sobresterço de potência |
   | volta | distribuição do acelerador; rotação da troca de marcha; transferência de carga; tendência térmica dos pneus; consistência |

2. **Cada detector, a cada passagem pela curva,** dá "aplica", "não aplica" ou "não conclusivo". É "não conclusivo" quando falta canal, quando o canal não é confiável naquele trecho ou quando a diferença fica dentro da dispersão.
3. **Rode nas voltas da IA e nas minhas,** com as mesmas regras.
4. **A saída:**
   - por curva, a fração das passagens em que a IA aplica cada técnica e a fração em que eu aplico;
   - as técnicas que a IA aplica e eu não, e as que eu aplico e a IA não;
   - a evolução da minha fração sessão a sessão.
5. **As verificações próprias da IA** (pesquisa de datasets, seção sobre a IA do Assetto Corsa):
   - a fração das amostras de pedal com valores intermediários, que separa comandos binários de modulados;
   - a duração da sobreposição de freio e volante em cada curva, confrontada com o TRAIL_HINT, se ele for legível;
   - a dispersão volta a volta do ponto de frenagem, da mínima e da retomada;
   - se a IA muda a técnica de uma curva para outra;
   - **com os níveis de força:** se os pedais se repetem e só mudam de escala com o nível, ou se a forma muda.

   O rótulo esperado é "referência consistente, que segue uma linha gravada". A consistência da IA fica fora do vetor de estilo, porque, senão, ela se separa de todos os humanos por isso.

## Parte F — A assinatura de estilo da IA e a minha (E3, parte a)

1. **As dimensões de estilo** da pesquisa: forma em V ou U, perfil de frenagem, uso dos pedais (binário ou sobreposto), resposta do carro na entrada, aplicação do volante, perfil do acelerador e consistência.
2. **Calculadas por tipo de curva** (lenta, média e rápida), para a IA e para mim, com a incerteza.
3. **A minha assinatura sessão a sessão,** para ver o quanto ela muda. Para um iniciante, ela é a "assinatura atual", não um traço fixo.
4. **Prepare o pedido seguinte,** o do estilo com dados externos (`docs/tecnica_de_pilotagem_datasets.md`, seção "Razões adimensionais por fase de curva…"):
   - **no máximo 10 medidas,** todas da primeira classe da pesquisa: razões adimensionais por fase da curva (a posição da mínima na curva e a razão entre a mínima e a velocidade de entrada; a retomada do acelerador em relação ao ápice; o tempo até o pico de freio dividido pela duração da frenagem; a aceitação do acelerador; a fração sem pedal; e outras do mesmo tipo);
   - **por faixa de velocidade e raio,** não pelo nome da curva;
   - **sem valores absolutos** (metros, km/h, g, ângulo do volante sem conversão), que representam o carro e a pista, não o piloto;
   - **o uso da aderência, a consistência e o tempo** ficam fora do vetor de estilo e são relatados à parte, porque medem habilidade;
   - **para cada medida, os canais que ela exige.** Os dados públicos da F1 não têm volante nem pressão de freio, e o freio deles é ligado ou desligado.

## Parte G — O modelo supervisionado leve

1. **Por curva:** o tempo do trecho como alvo e as medidas dos detectores como entrada, com um modelo simples e regularizado, ou de efeitos mistos com a sessão como efeito aleatório.
2. **Validado deixando uma sessão de fora.**
3. **A saída:** que medidas explicam o tempo em cada curva, com o sinal e a incerteza. Isso confirma quais detectores importam neste carro e nesta pista.
4. **É descritivo:** mostra associação, não causa, e não vira ganho estimado (ADR 0004).

## Parte H — O kit de rotulagem para validar os detectores (parada)

1. **Monte o kit:** para 5 detectores (soltura do freio, trail braking, retomada do acelerador, subesterço e sobresterço), separe de 20 a 30 passagens por detector, misturando IA e minhas, com os traços de pedal, volante, velocidade e guinada e a posição na pista, **sem mostrar o estado que o detector deu**.
2. **Escreva as instruções** para eu rotular cada passagem ("aplica", "não aplica" ou "não sei") e onde gravar a resposta.
3. **Pare aqui** e grave o relatório parcial.
4. **Depois que eu rotular,** calcule a precisão e a revocação de cada detector e complete o relatório.

## Parte I — Documentação

- **`docs/modelo2_tecnica_e_estilo.md`:** a seção 1 (Parte A) e as seções com as fases, a localização, os detectores, a assinatura de estilo, o modelo supervisionado e a validação. Escreva para quem não é da área.
- **`docs/tecnica_de_pilotagem_lista.md`:** atualize os itens B1, B2, B3, B10, E1, E2 e E3, com o estado e onde está cada coisa, e uma linha no histórico.
- **`docs/arquitetura_ml.md`:** a situação das peças B e C do Modelo 2.

## Testes

- **as fases:** as fronteiras são as mesmas em todas as voltas;
- **cada detector:** um caso sintético que aplica, um que não aplica e um sem canal (dá "não conclusivo");
- **a atribuição do erro:** o falso ganho da frenagem tardia é classificado como tal;
- **a regra de repetição:** uma perda numa volta só não entra no ranking;
- **as suítes:** a do backend continua passando.

## Regras gerais

- **Nada do app, do rádio, do coach, do store v2 ou do relatório de evolução muda.** É um módulo novo em `backend/ml/`.
- **As gravações são só lidas.**
- **Só voltas de origem rotulada** (ADR 0014 e 0018).
- **"Erro" é diferença medida contra uma volta real**, com o tempo que custou (ADR 0012). Nada de ganho prometido.
- **Não instale nem atualize pacotes.** Se algo pedir pacote novo, pare e relate.
- **Não mexa no app instalado nem em arquivos do jogo.**
- **Não gere instalador.**
- **Não contorne nenhuma trava:** se algo parar, pare também e registre o motivo. Uma trava do git não é apagada sem me perguntar.
- **Branch e commits:** branch `etapa/modelo2-erro-tecnica-e-estilo`, a partir de `develop`, commits por parte (a Parte A antes de rodar nas voltas), merge em `develop`. Sem push.
- **Uma sessão de implementação por vez** (ADR 0008).
- **Relatório** em `docs/handoff/2026-10-24_38_modelo2-erro-tecnica-e-estilo_relatorio.md`, como manda o CLAUDE.md, com:
  - a Parte A e o commit dela;
  - os canais por volta e as conferências;
  - os passos para eu gravar a sessão da IA;
  - as fases de cada curva;
  - os 3 maiores erros por sessão (Parte D);
  - a tabela de técnicas da IA e minhas por curva (Parte E);
  - as assinaturas de estilo (Parte F);
  - o modelo supervisionado (Parte G);
  - o kit de rotulagem e, depois, a precisão e a revocação (Parte H);
  - um `resultados.json` com o commit, o `geometry_id`, os comandos e os hashes dos arquivos lidos (ADR 0007);
  - a saída dos testes e os commits.
- Se algo do contexto não bater com o repositório, pare e registre no relatório.
