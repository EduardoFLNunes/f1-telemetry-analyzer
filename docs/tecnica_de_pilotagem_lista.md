# Lista de requisitos: técnica de pilotagem no Modelo 2

- **Dono da lista:** Eduardo. Quem mantém: o Claude (Cowork).
- **Criada em:** 24/10/2026. **Última validação:** 25/10/2026.
- **Pesquisas de base, com as fontes:**
  - `docs/tecnica_de_pilotagem_pesquisa.md`: técnica, ensino, estilos e feedback (24/10);
  - `docs/tecnica_de_pilotagem_datasets.md`: datasets de outras categorias, medidas comparáveis entre carros, KNN de estilo e a IA do Assetto Corsa (24/10).

## Como esta lista funciona

1. **A cada pedido sobre este tema,** o Claude (Cowork) relê a lista inteira, confere cada item contra o que existe (pesquisa, pedidos, relatórios do Claude Code e código) e atualiza o estado e o histórico.
2. **Um item só fica ✅ quando o critério de "preenchido" dele é atendido,** com o lugar onde isso está escrito.
3. **Exemplos dados pelo Eduardo são contexto, não escopo.** Quando ele cita um caso (por exemplo, corrigir uma saída de traseira), o item cobre a família inteira (saída de frente, travamento de roda, freio com o volante virado, trail braking e o que mais houver), e não só o exemplo.
4. **Estados:** ✅ preenchido · 🟡 parcial ou só desenhado · ⬜ pendente · ⛔ bloqueado por outra coisa.

## O problema, nas palavras do Eduardo (24/10)

> Ensinar onde e quando frear não basta: sem os conceitos técnicos, o piloto continua perdendo tempo. O Modelo 2 precisa identificar o erro que levou à perda de tempo, identificar se o piloto aplica as técnicas de pilotagem e catalogar o estilo do piloto, para saber se aquela técnica faz sentido para o estilo dele.

---

## A. Pesquisa (pedido de 24/10)

| # | Requisito | Preenchido quando | Estado | Onde está | O que falta |
|---|---|---|---|---|---|
| A1 | Fontes de ensino do iniciante (kart) às categorias mais altas (F1, Hypercar, Le Mans) | Há fontes para cada degrau, com o que se ensina e como se verifica a progressão | ✅ | Pesquisa: "Do kart ao Hypercar" (tabela de 5 níveis) e "Escolas, treinadores e ferramentas" | — |
| A2 | Pilotagem real **e** virtual | Escolas e treinadores reais e ferramentas e cursos de simulador, com a transferência entre os dois | ✅ | Pesquisa: tabela das ferramentas (Trophi, Track Titan, Coach Dave Delta, hotlap.ai, Garmin Catalyst, Apex Pro) e "entre a pista real e a virtual" | — |
| A3 | Livros clássicos de técnica | Taruffi, *Going Faster!*, *Drive to Win*, Milliken e Haney consultados | 🟡 | A pesquisa registra que não estavam acessíveis online | Consultar a versão impressa, se o Eduardo tiver acesso. *Going Faster!* é o mais útil (tipos de curva) |
| A4 | Catálogo **amplo** de técnicas, sem se prender a um exemplo | Todas as famílias do item A5 cobertas com o mesmo peso | ✅ | Pesquisa: seção "Os erros que custam tempo…" e subseções | — |
| A5 | Famílias de técnica cobertas | Cada família com definição, erro típico e correção | ✅ | Ver a lista abaixo | Posição de pilotagem e pegada do volante: só citadas (🟡) |
| A6 | Erros que custam tempo e progressão por nível | Lista de erros por fase da curva e ordem de ensino por nível | ✅ | Pesquisa: "três transições" e tabela de níveis | — |
| A7 | Como cada técnica e cada erro aparece na telemetria do Assetto Corsa | Indicador calculável com os canais gravados, para cada técnica e cada erro | ✅ | Pesquisa: duas tabelas ("Frenagem e entrada" e "Meio de curva, saída e volta") | Três canais a confirmar: ver o item D4 |
| A8 | Catálogo de estilos de pilotos (pesquisa) | Dimensões de estilo e pilotos catalogados com fonte e tipo de evidência | 🟡 | Pesquisa: tabela de cerca de 10 dimensões e mais de 20 pilotos (F1, IndyCar, endurance e Hypercar) | **Pilotos virtuais:** não há documentação confiável por piloto. Os rótulos de estilo mudam com o carro e o regulamento |
| A9 | Avaliar se o cluster é a melhor opção | Comparação do cluster com as alternativas, com prós, contras e recomendação | ✅ | Pesquisa: "Clusterizar o tipo de habilidade…" (tabela de 7 abordagens) | Decisão do Eduardo: item C1 |
| A10 | Como ensinar: quando e quanto corrigir | Evidência sobre o momento, a frequência e o foco do retorno | ✅ | Pesquisa: "A ciência do feedback…" | Nenhum estudo com teste de retenção em sim racing: o projeto pode ser o primeiro (item B9) |

**As famílias de técnica (item A5):**

| Família | O que entra | Estado |
|---|---|---|
| Frenagem | Ponto de frenagem; frenagem no limiar; perfil com carga aerodinâmica (pico cedo e pressão caindo com a velocidade); soltura progressiva; trail braking e a controvérsia da profundidade; travamento de roda; repartição de frenagem; freio com pé esquerdo; ABS; referências de frenagem | ✅ |
| Controle do carro | Subesterço na entrada, no meio e na saída; sobresterço por alívio, por frenagem e de potência; contraesterço; sobresterço súbito; rotação pelos comandos combinados | ✅ |
| Transferência de peso e aderência | Transferência longitudinal e lateral; círculo de atrito (diagrama g-g); ângulo de deriva | ✅ |
| Traçado | Ápice geométrico e tardio; forma em V e em U; uso da largura da pista; prioridade entre curvas; sequências de curvas | ✅ |
| Aceleração e tração | Retomada do acelerador; acelerador cedo e tarde; fase sem pedal; acelerador de manutenção; patinação | ✅ |
| Marchas | Reduções durante a frenagem; toque de acelerador na redução; troca antecipada | ✅ |
| Visão e referências | Olhar um passo à frente; ligar os pontos; marcos fixos | ✅ (sem canal direto: só por sintomas) |
| Consistência | Dispersão do tempo de volta e do ponto de frenagem; uma variável por vez | ✅ |
| Pneus | Janela de temperatura; aquecimento; superaquecimento por escorregamento | ✅ |
| Chuva | Linha de chuva; frenagem fora da trajetória | ✅ (fora da referência de pista seca) |
| Disputa e tráfego | Ultrapassagem e defesa; tráfego multiclasse | ✅ (fora da telemetria de um carro só) |
| Gestão de energia e combustível | Alívio antes da frenagem; ritmo de stint | ✅ (nível profissional) |
| Posição de pilotagem e pegada | Pegada às 9h15; posição no kart | 🟡 só citadas |
| Acerto contra técnica | Problema que muda volta a volta é do piloto; problema igual em todas pode ser do carro | ✅ |

---

## B. Desenho no Modelo 2 (o próximo passo: "vamos desenhar")

| # | Requisito | Preenchido quando | Estado | Onde está | O que falta |
|---|---|---|---|---|---|
| B1 | **Identificar o erro que levou à perda de tempo** | Regra para ir do microssetor que perdeu tempo até a fase da curva e o comando que originaram a perda, com teste em sessões reais | 🟡 | Implementado offline (pedido 38, Parte D): `backend/ml/modelo2/perda.py`; regras em `docs/modelo2_tecnica_e_estilo.md`, 1.6 e 2; saída por sessão em `docs/handoff/2026-10-24_38_modelo2-erro-tecnica-e-estilo_erros_por_sessao.json` | Validar os detectores (B10) antes de qualquer frase. Decidir se o peso pela reta seguinte fica: ele põe as duas retas longas à frente de tudo e zera C01, C07, C08 e C09 (emenda 2.3) |
| B2 | **Identificar se o piloto aplica cada técnica** | Um detector por técnica, com os estados "aplica", "não aplica" e "não conclusivo", calibrado nas voltas de referência e validado (B10) | 🟡 | 27 detectores com três estados, calibrados nas passagens da IA da mesma curva (pedido 38, Parte E): `backend/ml/modelo2/detectores.py`; regras em `docs/modelo2_tecnica_e_estilo.md`, 1.5 | A validação (B10). Limitações já vistas: a retomada (s_pu) e o ponto de entrada (s_ti), na seção 2 do documento |
| B3 | **Catalogar o estilo do piloto** | Assinatura atual em dimensões contínuas, por tipo de curva, com incerteza, comparada com o histórico dele | 🟡 | Assinatura atual da IA e minha por tipo de curva, com intervalo de bootstrap, e a minha sessão a sessão (pedido 38, Parte F): `backend/ml/modelo2/estilo.py`, `docs/handoff/2026-10-24_38_modelo2-erro-tecnica-e-estilo_estilo.json` | Separar estilo de habilidade com a população externa (E3, partes b a d). Para um iniciante, a assinatura muda depressa: tratar como "assinatura atual", não como traço fixo |
| B4 | **Decidir se a técnica faz sentido para o estilo** | Regras explícitas de compatibilidade, com o silêncio como resposta quando nenhuma passa | 🟡 | Pesquisa: desenho, etapa 5 (aparece numa volta real mais rápida; o nível permite; o passo combina com a assinatura; não é problema de acerto) | Decisão (C2) |
| B5 | **Ensinar os conceitos técnicos, e não só onde e quando frear** | Para cada técnica: o que é, por que funciona (física em linguagem simples), como se executa, o erro típico, um exercício e como medir se deu certo | ⬜ | A pesquisa tem o conteúdo de base e cinco exercícios codificáveis (marco de frenagem que avança, terceira marcha sem freio, subesterço proposital, construção lenta do acelerador, tempos de soltura do freio) | **Montar a biblioteca de técnicas e exercícios** e decidir onde ela aparece (relatório depois da sessão, tela do app) |
| B6 | Progressão por nível | As técnicas avançadas ficam bloqueadas até as básicas estarem dominadas, com um critério de domínio | 🟡 | Pesquisa: ordem dos detectores e regra "4 das últimas 6 passagens" | Decisão do critério de domínio |
| B7 | Comunicação: rádio e relatório | O rádio diz "o quê" e "onde" (um item, foco externo, diferença medida, confirmação, retirada); o relatório diz "por quê" e "como" | 🟡 | Pesquisa: "Falar uma coisa, verificar e retirar a ajuda" | Decisão (C3): muda o rádio de hoje (até 3 frases por volta e a análise a cada 3 voltas válidas) |
| B8 | Nível do piloto | Nível pelo ritmo médio das melhores voltas e pela dispersão, não pela melhor volta isolada (critério da FIA) | 🟡 | Pesquisa: recomendação final da seção do cluster | Implementação |
| B9 | Avaliação: o piloto aprendeu? | Desenho de sujeito único, com linha de base, intervenção e retenção sem rádio, ou alternância entre curva-alvo e curva de controle | ⬜ | Pesquisa: "Avaliar com desenho de sujeito único" | Decisão (C4): muda o plano de sessões |
| B10 | Validação dos detectores | Precisão e revocação de cada detector contra passagens rotuladas à mão pelo Eduardo | 🟡 | Kit de 120 passagens (5 detectores × 24), sem o estado do detector e sem a origem: `docs/handoff/2026-10-24_38_modelo2-erro-tecnica-e-estilo_kit_rotulagem.html` e `docs/handoff/2026-10-24_38_modelo2-erro-tecnica-e-estilo_rotulagem.csv` | A rotulagem do Eduardo; depois, a precisão e a revocação, com as duas rodadas juntas (pedido 42, Parte E) |
| B11 | Regra do projeto mantida | Toda fala é diferença medida contra uma volta real, nunca ganho prometido (ADR 0012) | ✅ | O desenho inteiro segue a regra | — |

---

## C. Decisões que são do Eduardo

| # | Decisão | Recomendação da pesquisa | Estado |
|---|---|---|---|
| C1 | Cluster como resultado principal, ou a arquitetura combinada | Não usar o cluster como resultado principal: os estudos que agruparam voltas encontraram níveis de tempo e estágios de aprendizagem, não estilos, e o método pede 20 a 30 casos por grupo. Usar quatro peças: comparação com uma volta real, detectores por regras, dimensões contínuas de estilo e um modelo supervisionado pelo tempo de cada trecho. O cluster fica como análise exploratória | ✅ **Decidido em 24/10: seguir com as 4 peças.** O Eduardo acrescentou um caminho próprio para o estilo: um cluster com dados externos e o KNN contra pilotos de estilo definido (itens E3 e E4) |
| C2 | Qual volta serve de referência para sugerir uma técnica | Primeiro a melhor volta do próprio piloto, que já respeita o estilo dele; a volta da IA só para técnicas que ele nunca mostrou, lembrando que a IA não pilota como humano | ⬜ |
| C3 | Mudar o rádio para "uma correção por vez, confirmação e retirada" | Sim, com o "por quê" e o "como" no relatório depois da sessão. Altera o comportamento do ADR 0021 | ⬜ |
| C4 | Avaliar com retenção (uma sessão sem rádio depois de um intervalo) | Sim: melhorar com o rádio ligado é desempenho na prática, não aprendizagem | ⬜ |

---

## E. Os objetivos do Eduardo de 24/10: nas voltas gravadas da IA e do piloto

> "Precisamos conseguir identificar nas voltas gravadas, tanto da IA quanto do piloto real." Principal: seguir com a combinação das 4 peças.

| # | Objetivo | Preenchido quando | Estado | Onde está | O que falta |
|---|---|---|---|---|---|
| E1 | **Qual erro o piloto cometeu que o fez perder tempo contra a IA** | Em cada sessão, por curva e por fase da curva: a perda medida contra a volta da IA e a diferença de técnica que a explica, ou "não conclusivo" | 🟡 | Pedido 38, Parte D: os 3 maiores erros por sessão, com a curva, a fase, o tempo e o detector que explica, ou "não conclusivo" (`docs/handoff/2026-10-24_38_modelo2-erro-tecnica-e-estilo_erros_por_sessao.json`) | Validar os detectores (B10). A volta da IA com todos os canais é uma só (22/10, 89,1 s, mais lenta que as de 04/10) |
| E2 | **Quais técnicas a IA usa e quais o piloto usa** | Os detectores rodam nas voltas da IA e nas do piloto, e há, por curva, a fração das passagens em que cada um aplica cada técnica | 🟡 | Pedido 38, Parte E: a fração das passagens em que a IA e eu aplicamos cada técnica, por curva, e a minha evolução por sessão (`docs/handoff/2026-10-24_38_modelo2-erro-tecnica-e-estilo_tecnicas.json`) | Os detectores de equilíbrio (subesterço, sobresterço, contraesterço) têm uma só volta da IA com a guinada. Falta a sessão da IA em níveis de força (F3), com os passos no relatório do pedido 38 |
| E3 | **Estilos por datasets e um cluster de estilo; o estilo da IA e o do piloto catalogados** | (a) a assinatura de estilo da IA e a do piloto no nosso dado; (b) um dataset externo com pilotos identificados e canais comparáveis; (c) um espaço de estilo construído sobre o resíduo contra o tempo (sem o eixo de habilidade) e validado pelos seis testes da pesquisa; (d) a IA e o piloto posicionados nele, com a distância e a incerteza | 🟡 | (a) feita: pedido 38, Parte F (`docs/handoff/2026-10-24_38_modelo2-erro-tecnica-e-estilo_estilo.json`). (b) a (d) desenhados: pesquisa de datasets, "Pergunta 3". **O dataset é o Assetto Corsa Gym** (NeurIPS 2024, CC BY 4.0): 15 pilotos (1 profissional de esports, 4 especialistas, 5 casuais e 5 iniciantes), 927 voltas, Dallara F317, GT3 e Miata, praticamente os mesmos canais do projeto, sem Interlagos | As ações F1 a F5. As 10 medidas adimensionais e os canais de cada uma estão no relatório do pedido 38 (Parte F.4) |
| E4 | **A biblioteca de estilos de referência, com KNN:** pilotos de estilo bem definido como referência e a busca dos "vizinhos" com padrão parecido; a busca vai além da F3, porque há pouca informação desse carro | (a) as âncoras de referência; (b) a telemetria delas num dataset; (c) as medidas comparáveis entre carros (no máximo 10, adimensionais, por fase da curva); (d) o KNN validado deixando um piloto de fora e trocando o carro; (e) a IA e o piloto posicionados, com "não conclusivo" quando nenhuma âncora fica perto | 🟡 | Desenhado: pesquisa de datasets, "Pergunta 4". **Três achados mudam o desenho:** (1) não existe biblioteca pública de estilos em nenhuma categoria, e pilotos com estilo "bem definido" não existem como verdade de referência (na F1, os rótulos são jornalísticos e mudam com o carro); as âncoras passam a ser **grupos** (por experiência ou por arquétipo extraído dos dados); (2) com medidas absolutas, o KNN acha **carros** parecidos, não estilos (na F1, o construtor explica cerca de 88% da variância dos resultados); (3) a busca se amplia por **semelhança de condição**, não por categoria: em vez de trazer pilotos de outras categorias até Interlagos, **levar o piloto e a IA até o F317 numa pista do Assetto Corsa Gym**. A F1 em Interlagos (FastF1) entra só com o traço de velocidade, como contexto de forma de curva | As ações F1 a F5 |
| E5 | **As duas bibliotecas são diferentes e as duas fazem falta** | A biblioteca de estilos (E4) diz com quem o piloto se parece; a biblioteca de conceitos (B5) diz o que é cada técnica, por que funciona, como se treina e como medir. A primeira escolhe a técnica que combina; a segunda ensina | 🟡 | Esta lista | O Eduardo confirmar que as duas entram |

---

## F. Ações para destravar E3 e E4 (da pesquisa de datasets)

| # | Ação | Quem | Estado |
|---|---|---|---|
| F1 | **Conferir o Assetto Corsa Gym:** baixar a base (Hugging Face), ver o formato dos arquivos e se cada volta traz o identificador do piloto. Sem ele, a base perde metade do valor | Claude Code, num pedido próprio, com o seu ok para o download | ⬜ |
| F2 | **Ver se o Dallara F317 e uma pista da base** (Monza, Barcelona, Red Bull Ring ou Indianápolis) estão instalados no seu Assetto Corsa, para gravar você e a IA na mesma condição dos 15 pilotos | Eduardo | ⬜ |
| F3 | **Gravar a IA em 2 ou 3 níveis de força** no nosso carro, em Interlagos (o teste que separa ritmo de estilo) | Eduardo, com os passos do pedido 38 | ⬜ |
| F4 | **Permissão da Kunos:** o artigo do Assetto Corsa Gym diz que publicar pesquisa com o Assetto Corsa exige permissão da Kunos Simulazioni. Ler a licença do jogo e, se confirmar, pedir autorização por escrito antes da defesa | Eduardo, com o orientador | ⬜ |
| F5 | **Licenças das bases menores:** Remonda et al. 2021 (Zenodo; F312, com 2 profissionais de F3) e van Leeuwen et al. 2017 (4TU; Formula Renault 2.0) estão sem licença confirmada | Claude Code, no pedido próprio | ⬜ |
| F6 | **Âncoras próprias:** voluntários com experiência conhecida, gravados no mesmo mod em Interlagos, com termo de consentimento. É a única âncora com o mesmo carro e a mesma pista | Eduardo, se quiser | ⬜ opcional |

---

## D. Ligações com o que o projeto já tem

| # | Ligação | Estado |
|---|---|---|
| D1 | O coach já mede a perda por microssetor contra uma volta real: é a base da localização (B1) | ✅ existe |
| D2 | O relatório de evolução já mede, por curva, a freada, o ápice, a mínima e a "diferença consistente". Desde o pedido 18, também tem medidas descritivas de técnica: uso da aderência, freio e volante juntos, freada emendada e pneus (`docs/modelo_fisico_m0.md`, seção 5). São os primeiros detectores | ✅ existe |
| D3 | O rádio e o replay da curva (pedidos 31 a 36) já entregam "onde" e "quanto", com unidades e visual | ✅ existe |
| D4 | **Canais a confirmar antes dos detectores:** a unidade do volante e o entre-eixos (o ângulo de subesterço precisa dos dois); a presença de ABS no carro; o escorregamento das rodas, que mistura os componentes longitudinal e lateral | ⛔ A M1 (pedido 37) parou: as regressões não identificaram o entre-eixos. **Pelo ADR 0024, o volante e o entre-eixos passam a ser medidos pelos pontos de contato e pela direção dos pneus na memória do jogo (pedido 39).** Um retrato antigo da memória já dá cerca de 2,96 m e 15° de roda por unidade de volante. O ABS e o escorregamento ainda não têm pedido |
| D5 | As taxas (aplicação do freio, velocidade do volante, reversões) são calculadas nos cerca de 60 Hz originais, com o cronômetro do jogo (ADR 0022), e só depois projetadas na grade de 2 m | ⬜ regra para os pedidos de implementação |
| D6 | Separar as voltas da IA (indicador do jogo) e as anteriores a 01/10/2026 (o equipamento novo) | ✅ já é regra do store (ADR 0014 e 0015) |
| D7 | **O cluster no projeto hoje:** não há cluster de estilo nem de habilidade no código. A palavra aparece em dois sentidos que não têm relação com estilo: o bootstrap agrupado por sessão, que dá o intervalo de confiança (`ml/validation/counterfactual.py`), e o agrupamento de pontos de frenagem em zonas de 30 m (`ml/validation/empirical.py`). O que existe é plano: os clusters de estilo com dados externos (F1, GT3, DTM e IndyCar), a regra do ADR 0014 de que "clusters de estilo" só usam voltas `humano` e o documento "Dados de corrida e estilos", que está no backlog para correção | ✅ conferido em 24/10; o rumo depende da decisão C1 |

---

## Histórico

| Data | O que mudou |
|---|---|
| 24/10/2026 | Lista criada a partir do pedido do Eduardo e validada contra a pesquisa de 24/10. Pesquisa: A1, A2, A4 a A7, A9 e A10 preenchidos; A3 e A8 parciais. Desenho: B1 a B4 e B6 a B8 desenhados; B5, B9 e B10 pendentes. Quatro decisões abertas (C1 a C4). Dependência da M1 (pedido 37) registrada em D4 |
| 24/10/2026 | Pergunta do Eduardo sobre o cluster. Conferido o código e os documentos: nenhum cluster de estilo implementado, só planos (item D7). A decisão C1 continua aberta. |
| 24/10/2026 | **Decisão C1: seguir com as 4 peças.** Entraram os objetivos E1 a E5 (nas voltas da IA e do piloto). E1, E2 e a parte (a) de E3 vão para o pedido 38. A parte externa de E3 e o E4 dependem da pesquisa de datasets. Encontrada uma lacuna de dados: as voltas da IA de 04/10 não têm a guinada nem as velocidades no referencial do carro |
| 24/10/2026 | Validada contra a pesquisa de datasets. E3 e E4 passam a 🟡 (desenhados): o dataset externo é o Assetto Corsa Gym, as âncoras são grupos e não pilotos nomeados, e a busca se amplia por semelhança de condição. Entrou a seção F (ações F1 a F6). O pedido 38 ganhou a IA em níveis de força, as verificações da IA e as medidas adimensionais |
| 25/10/2026 | A M1 parou na Parte C (entre-eixos não identificado). D4 atualizado: a geometria será medida pela telemetria do jogo (ADR 0024, pedido 39). O pedido 38 continua depois do 39 |
| 25/10/2026 | O pedido 39 parou na Parte C, esperando a sessão de medição (o retrato confirma L = 2,955 m e k_δ = 0,267 rad, deste carro). O pedido 38 foi aberto ao mesmo tempo na mesma pasta e parou antes da Parte A; o commit dos documentos dele (`f38f89a5`) ficou na branch do 37/39 e entra em `develop` com o merge do 39. O pedido 38 recomeça de `develop`, depois do merge |
| 25/10/2026 | **Pedido 38 executado até a Parte H (parado para a rotulagem).** B1, B2, B3, E1, E2 e E3(a) implementados offline em `backend/ml/modelo2/`, nas 130 voltas minhas e 14 da IA; B10 com o kit de rotulagem pronto. O subesterço usa o entre-eixos e a unidade do volante do retrato do pedido 39, como medida substituta, até a M1 medir |
| 25/10/2026 | Validada contra o relatório do pedido 38: as linhas B1, B2, B3, B10, E1, E2 e E3 conferem com o que foi entregue. Recomendação do Cowork para a ordem: rotular o kit antes (os rótulos são da passagem e continuam valendo quando o subesterço for recalculado com a geometria medida); a sessão da IA em níveis de força (F3) vai na mesma ida ao jogo da medição do pedido 39. Cuidado registrado para a B10: no subesterço (E2), o kit não mostra quanto volante a curva pede, então "nao sei" é uma resposta válida e esperada |
| 01/11/2026 | **Decisão do Eduardo: o merge do pedido 38 em `develop` sai sem a H.4.** O Modelo 2 continua offline, e nada do app o usa. A precisão e a revocação (B10) saem quando os rótulos chegarem, com as duas rodadas juntas, na Parte E do pedido 42 |
