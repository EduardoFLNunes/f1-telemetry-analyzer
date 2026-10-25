# Ensinar pilotagem medindo um erro por vez

Do kart à Fórmula 1 e ao Hypercar, escolas, treinadores e ferramentas ensinam técnica de pilotagem na mesma ordem. Primeiro vêm segurança, visão, referências e consistência. Depois vêm a frenagem no limiar de travamento e, principalmente, a soltura progressiva do freio. Em seguida, aceleração progressiva, rotação controlada e leitura do círculo de atrito. Só nos níveis altos entram ajustes finos como trail braking profundo, sobreposição de pedais, gestão de pneus, gestão de energia e tráfego. Os erros que mais custam tempo se concentram em três transições: do fim da frenagem para o esterçamento, no meio da curva e na retomada do acelerador. Cada técnica e cada erro deixa uma assinatura calculável com os canais que o Assetto Corsa já grava. Dois exemplos são o tempo até o pico de freio (**0,38 s em pilotos de corrida contra 1,12 s em não pilotos**, num estudo em simulador) e a comparação entre ângulo de volante e velocidade de guinada, que separa subesterço de sobresterço ([van Leeuwen et al. 2017](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0186871); [US 10293852](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10293852)). Clusterizar o "tipo de habilidade" do piloto é a opção mais fraca. Os estudos revisados por pares que agruparam voltas de simulador encontraram **níveis de tempo de volta e estágios de aprendizagem, não estilos** ([Remonda et al. 2021](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0245320); [Hojaji et al. 2026](https://www.scitepress.org/Papers/2026/146096/146096.pdf)). Além disso, a análise de poder estatístico recomenda **20 a 30 casos por grupo, com separação grande** entre os grupos ([Dalmaijer et al.](https://arxiv.org/abs/2003.00381v3)). A recomendação é combinar quatro peças: comparação com uma volta real de referência, detectores de técnica por regras físicas calibrados nessas voltas, dimensões contínuas de estilo e um modelo supervisionado pelo tempo de cada segmento da pista. O clustering fica como análise exploratória. A ciência da aprendizagem motora apoia o rádio curto que o projeto já tem, mas pede quatro ajustes: uma correção por vez, foco de atenção externo (marcos da pista e posição do carro), aviso só quando a métrica sai de uma faixa e retirada progressiva da ajuda. O motivo é que **feedback frequente melhora a prática e pode piorar a retenção** ([Chua et al. 2021](https://oasis.library.unlv.edu/kns_fac_articles/424/); [Anderson et al. 2005](https://pmc.ncbi.nlm.nih.gov/articles/PMC1780106)). No Modelo 2, tudo isso vira um ciclo de passos:

1. localizar o microssetor que perdeu tempo;
2. voltar até a fase da curva que originou a perda;
3. verificar se a técnica correspondente aparece numa volta real mais rápida e se combina com a assinatura do piloto;
4. dizer a diferença medida;
5. conferir na passagem seguinte.

## Os erros que custam tempo se concentram em três transições da curva

Os treinadores descrevem a curva como uma sequência: ponto de frenagem, ponto de entrada (turn-in), ápice e saída. Eles localizam os erros onde um comando passa o controle para outro ([Driver61](https://driver61.com/uni/racing-line/)). Segundo Ross Bentley, a lista de erros típicos de amadores nos dados é curta e se repete. Ela inclui fase sem pedal antes da frenagem e falta de compromisso com o acelerador. Inclui também pouca frenagem prolongada para dentro da curva, que aparece como um traço de velocidade "quadrado", sem mudança na taxa de desaceleração. Completam a lista a redução excessiva de velocidade, a velocidade mínima baixa que compromete a saída e o acelerador não pleno entre curvas ([Bentley 2020](https://speedsecrets.com/wp-content/uploads/2020/01/COACHING-WITH-DATA.pdf)). Um caso documentado mostra a escala. Um amador num BMW M3 GT ex-IMSA ficou **cerca de 3,9 s atrás do piloto de fábrica Bill Auberlen**. Ele frenou antes, reduziu demais a velocidade em várias curvas e manteve velocidades mínimas semelhantes por muito mais tempo ([Road & Track via Yahoo](https://autos.yahoo.com/data-instruction-close-speed-gap-162600048.html)). O treinador Jono Lester resume a consequência para quem projeta um sistema de correção: "a maioria dos pilotos não perde tempo onde pensa que perde" ([Jono Lester](https://jonolester.com/?p=9490)). O catálogo abaixo dá o mesmo peso a todas as famílias de técnica, porque o erro que mais custa tempo numa curva raramente é o mesmo da curva seguinte.

### Frenagem: o ponto importa, mas a soltura decide a entrada

No traço de pressão, a frenagem tem quatro fases. A primeira é a transição do acelerador para o freio, em que cada fração de segundo de atraso custa tempo. Depois vêm a aplicação até o máximo sem desestabilizar o carro, a modulação em torno do limiar de aderência e a soltura progressiva até o ponto de entrada ([Driver61](https://driver61.com/uni/braking/)). A frenagem no limiar (threshold braking) é a pressão que leva os pneus à beira do travamento, e nada além disso. Em carros sem pressão aerodinâmica, essa pressão é praticamente constante e pode virar memória motora. Em carros com downforce, que é o caso do Fórmula 3 do projeto, o piloto deve chegar ao pico rapidamente e reduzir a pressão no mesmo ritmo em que caem a velocidade e a carga aerodinâmica. **O erro comum em carros com downforce é não frear forte o bastante no início.** Isso desperdiça a aderência disponível e provoca travamento no fim da zona de frenagem ([VRS 3.4](https://virtualracingschool.com/academy/iracing-career-guide/second-season/braking-technique/)). Há uma divergência sobre o primeiro toque no pedal. O engenheiro Jürgen Zürn, citado pela Blayze, ensina uma aplicação inicial de cerca de 50%, com pausa de aproximadamente 0,1 s antes do limiar, para não sobrecarregar molas e pneus dianteiros ([Blayze](https://blayze.io/blog/car-racing/is-left-foot-braking-faster)). A VRS, ao contrário, diz para não ter medo de frear forte demais no primeiro toque em alta velocidade, quando o risco de travamento é menor. A diferença provavelmente se explica pelo tipo de carro. Os números práticos dão a escala do erro de iniciante. Pilotos não profissionais frenam **20% a 50% cedo demais** em zonas grandes de frenagem. Numa comparação da Driver61, **frear 10 m mais tarde rendeu 0,2 s**. A janela de escorregamento longitudinal de máxima aderência fica entre **3% e 10%** ([Driver61, prioridades](https://driver61.com/uni/prioritising-corners/); [Driver61, frenagem](https://driver61.com/uni/braking/)).

Treinadores experientes localizam na soltura do freio a diferença entre pilotos rápidos e lentos. Bryan Van Noy afirma que a entrada mais rápida não vem de frear mais forte ou mais tarde, e sim do modo de soltar o pedal. O piloto mantém pressão suficiente para conservar carga no eixo dianteiro, o que também ajuda o carro a girar. O perfil muda com a curva:

- em grampos, a pressão é mantida mais fundo e solta aos poucos até perto do ápice;
- em curvas médias, a soltura é mais rápida, mas progressiva;
- em curvas de alta velocidade, a frenagem é leve e longa, seguida de acelerador de manutenção.

([NASA Speed News](https://nasaspeed.news/columns/driver-instruction/the-art-of-releasing-the-brakes/))

O trail braking é a frenagem que continua, cada vez mais leve, durante o esterçamento. Mais freio significa mais aderência na dianteira e menos na traseira. Quanto maior o ângulo de volante, menos freio cabe, até sobrarem os últimos 10% a 15% de pressão, que já só controlam a arfagem. Mesmo assim, a maior parte da desaceleração ainda acontece em linha reta ([Driver61](https://driver61.com/uni/trail-braking/)).

A profundidade do trail braking é a principal controvérsia do catálogo. As fontes discordam:

- a Driver61 manda estar fora do freio pouco antes do ápice;
- a Blayze manda frear até o ápice, para evitar subesterço na entrada ([Blayze](https://blayze.io/blog/car-racing/what-is-understeer-and-how-to-correct-it));
- a VRS descreve uma forma avançada em que **5% a 10% de pressão são mantidos até o acelerador**, para controlar o equilíbrio e não para desacelerar ([VRS 3.4](https://virtualracingschool.com/academy/iracing-career-guide/second-season/braking-technique/));
- Ross Bentley lembra que a soltura pode terminar poucos centímetros depois do ponto de entrada. Para ele, mandar um piloto "fazer mais trail braking" costuma levá-lo a reduzir demais a velocidade, e por isso ele reescreve a instrução como "faça menos trail braking" ([Speed Secrets](https://speedsecrets.com/trail-braking-explained/); [Bentley Substack](https://rossbentley.substack.com/p/speed-secrets-dont-trail-brake-more)).

Há dois pontos em comum. A profundidade depende do carro e da curva: mais em curvas lentas e fechadas, menos em curvas rápidas. E o erro típico do iniciante é a **soltura abrupta**. Uma aluna de Bentley tirava o pé de uma vez, descarregava a dianteira, o carro não respondia e ela perdia os ápices. O problema se resolveu quando ela aprendeu a soltar o pedal aos poucos ([Winding Road](https://windingroad.com/articles/features/speed-secrets-to-trail-brake-or-not-to-trail-brake-that-is-the-question/)).

O travamento das rodas dianteiras tira a capacidade de esterçar. O iniciante costuma entrar em pânico, em vez de aliviar um pouco a pressão. Se o mesmo eixo trava sempre primeiro, a repartição de frenagem precisa de ajuste ([Driver61](https://driver61.com/uni/braking/)). Bentley descreve os sintomas da repartição. Com freio demais na dianteira, a direção fica "dormente" e o carro não muda de direção. Com freio demais na traseira, a traseira fica instável na entrada. No ideal, as quatro rodas travariam ao mesmo tempo se o piloto exagerasse ([Speed Secrets](https://speedsecrets.com/q-should-i-adjust-brake-bias-during-a-race-how-do-i-know-when-to-adjust-brake-bias/)). Outros dois erros também travam rodas:

- acrescentar esterçamento sem reduzir a pressão, quando o carro já está no limite de frenagem, trava as dianteiras e faz o carro escapar para fora ([VRS 3.1](https://virtualracingschool.com/academy/tag/theory/));
- reduções de marcha mal sincronizadas travam as traseiras, cerca de **três vezes mais quando o piloto pula marchas**, segundo observação de treinadores da Blayze ([Blayze](https://blayze.io/blog/heel-and-toe-downshifting)).

Com ABS, a recomendação é ficar logo abaixo da ativação, sentindo só uma leve vibração no force feedback, porque o ciclo do ABS é menos eficiente e aquece os pneus ([VRS 3.4](https://virtualracingschool.com/academy/iracing-career-guide/second-season/braking-technique/)).

A frenagem com o pé esquerdo (left-foot braking) não é sinônimo de trail braking ([Speed Secrets](https://speedsecrets.com/trail-braking-explained/)). Ela tem usos claros:

- encurtar a transição entre os pedais;
- em carros de tração dianteira, manter um pouco de acelerador enquanto o freio é solto.

Ela também tem limites. O pé esquerdo começa pouco sensível e tende a exagerar a aplicação inicial. A Blayze afirma que, na maioria das zonas de frenagem, ela não é mais rápida que a técnica de punta-tacco. Afirma também que é incorreto achar que um piloto é mais rápido só por usá-la ([Blayze](https://blayze.io/blog/car-racing/is-left-foot-braking-faster)). Hábitos de frenagem com o pé esquerdo aparecem até entre as causas de redução excessiva de velocidade ([Speed Secrets vMin](https://speedsecrets.com/wp-content/uploads/2025/08/4-vMin.pdf)).

Para as referências de frenagem, a prática ensinada é partir de um marco que pareça cedo demais e aproximá-lo **um ou dois metros por volta**, sempre usando marcos permanentes ([Driver61](https://driver61.com/uni/prioritising-corners/)). No kart, os treinadores colocam um cone cerca de 25 pés (≈7,6 m) antes do ponto ideal e o aproximam a cada volta ([KartPulse](https://forums.kartpulse.com/t/when-and-how-to-introduce-braking/2086)).

### Transferência de peso e círculo de atrito explicam subesterço, sobresterço e rotação

Equilibrar um carro é controlar a transferência de peso com freio, acelerador e volante. A transferência longitudinal segue a fórmula **ΔW = (h/L)·m·a**: altura do centro de gravidade dividida pelo entre-eixos, vezes massa e aceleração. Assim:

- frear carrega a dianteira e pode induzir sobresterço;
- acelerar carrega a traseira e pode induzir subesterço;
- curvar carrega os pneus externos.

No exemplo de Brian Beckman, frear a 1 g um carro de 3.200 lb leva 640 lb para a frente ([Beckman](https://gamedev.net/tutorials/programming/math-and-physics/the-physics-of-racing-part-1-weight-transfer-r1610)).

O círculo de atrito (diagrama g-g) traduz isso em geometria. Existe um limite finito de força em qualquer direção. Atingir esse limite na direção longitudinal significa travamento ou patinação. Atingi-lo na direção lateral significa escorregamento. Iniciantes separam os comandos e não usam a parte combinada do círculo. Pilotos experientes soltam o freio à medida que o volante entra e aplicam acelerador progressivo até o pleno ([VRS 3.1](https://virtualracingschool.com/academy/tag/theory/)). Numa comparação da Driver61, o profissional usa perto de 100% da aderência disponível ao longo da curva, e o amador não ([Driver61](https://driver61.com/uni/trail-braking/)). O ângulo de deriva do pneu é a diferença entre para onde o pneu aponta e para onde o carro vai. É ele que produz a sensação de limite: a aderência cresce com o ângulo, atinge um pico e depois cai aos poucos. O objetivo é manter os quatro pneus perto desse pico ([Speed Secrets](https://speedsecrets.com/q-what-is-slip-angle-and-how-do-i-use-it-to-drive-faster/)).

O subesterço ocorre quando a aderência disponível na dianteira é menor que na traseira ([VRS 3.3](https://virtualracingschool.com/academy/tag/car/)). Cada fase da curva tem uma causa típica:

- **Entrada.** O diagnóstico mais comum é falta de trail braking. A correção é manter um toque leve de freio depois do ponto de entrada.
- **Saída.** A causa é acelerar cedo demais. O sintoma é simples: "se você precisa esterçar mais depois de aplicar o acelerador, aplicou cedo demais" ([Blayze](https://blayze.io/blog/car-racing/what-is-understeer-and-how-to-correct-it)).
- **Excesso de trail braking.** Prolongar demais a frenagem também pode sobrecarregar a dianteira e gerar subesterço ([Speed Secrets](https://speedsecrets.com/q-how-can-i-make-my-car-rotate-more-into-a-corner/)), algo que a Blayze considera raro.

A correção é reduzir primeiro o acelerador e, se necessário, frear suavemente. **Acrescentar volante é o erro mais comum**, porque reduz ainda mais a aderência da dianteira ([VRS 3.3](https://virtualracingschool.com/academy/tag/car/)). Precisar de mais volante do que a pegada às 9h15 permite indica linha errada ou olhar curto demais ([Winding Road](https://windingroad.com/articles/features/three-common-methods-of-steering-wheel-control-but-which-makes-you-faster/)). Um exercício útil é provocar o subesterço de propósito numa curva longa, para perder os últimos km/h e ainda atingir o ápice ([Blayze](https://blayze.io/blog/car-racing/drills/understeer-scrub-speed-drill)).

O sobresterço é a perda de aderência do eixo traseiro antes do dianteiro, e tem três famílias. Na entrada e no meio da curva aparecem três formas: o sobresterço por alívio do acelerador (lift-off), o escorregamento controlado e o sobresterço induzido por frenagem. Na saída aparece o sobresterço de potência, quando o acelerador cresce mais rápido do que a aderência traseira permite ([Blayze](https://blayze.io/blog/car-racing/oversteer-masterclass-for-racecar-drivers)). Aliviar o acelerador no meio de uma curva rápida transfere carga para a frente e descarrega as traseiras. Carros de motor central giram mais rápido porque têm menor inércia de guinada ([Wikipedia](https://en.wikipedia.org/wiki/Lift-off_oversteer)). A correção é reaplicar acelerador de manutenção. Acionar o freio piora a situação ([VRS 3.3](https://virtualracingschool.com/academy/tag/car/)). O contraesterço deve ser imediato, na quantidade certa e desfeito a tempo. Corrigir tarde ou demais produz o sobresterço súbito (snap oversteer): quando o piloto desfaz a correção, a aderência volta à dianteira e lança o carro para o lado oposto ([VRS 3.3](https://virtualracingschool.com/academy/tag/car/)). A Skip Barber ensina, numa pista de derrapagem, a sequência corrigir, pausar e recuperar ([Motor Sport](https://www.motorsportmagazine.com/archive/article/december-2022/122/skip-barber-the-school-that-breeds-racing-champions%ef%bf%bc/)).

A rotação desejada nasce da combinação dos comandos, não do volante sozinho. Bentley ensina que um esterçamento inicial mais rápido, junto com uma boa soltura do freio, inicia a rotação. Ensina também que acelerar cedo carrega a traseira e interrompe a rotação: "não é o que você faz, é o que você não faz" ([Speed Secrets](https://speedsecrets.com/q-how-can-i-make-my-car-rotate-more-into-a-corner/)). O treinador Rob Wilson fala de uma "taxa ideal de comando" de mãos e pés e de uma rotação obtida com freio e acelerador, em vez de mais volante ([AA Directions](https://www.aa.co.nz/membership/aa-directions/driver/q-and-a-rob-wilson-legendary-f1-motorsport-coach/)). Antes de culpar o acerto, a regra de Ken Hill é corrigir o piloto:

- problemas que variam de uma volta para outra são do piloto;
- problemas que se repetem igualmente podem ser do carro;
- segundos de diferença são técnica, e décimos podem ser carro.

([Blayze](https://blayze.io/blog/car-racing/what-to-work-on-next-for-on-track-improvement))

### Traçado: ápice tardio, forma em V ou U e prioridade às curvas que alimentam retas

Entrar cedo demais na curva compromete muito a velocidade de saída, e entrar tarde demais reduz a velocidade possível. A maioria dos pilotos, por impaciência, tenta ganhar demais na entrada e destrói a saída ([Driver61](https://driver61.com/uni/racing-line/)). O ápice geométrico corresponde ao arco mais aberto. A linha ideal entra um pouco mais tarde e mais fechada para abrir a saída. Em curvas rápidas o ápice vem mais cedo; em curvas lentas e grampos, mais tarde ([Driver61](https://driver61.com/uni/racing-line/)).

Adam Brouillard, da Paradigm Shift Racing, define o ápice como o ponto mais limitante do lado interno da curva. Num exemplo medido, ele mostra por que a velocidade mínima não é a meta:

- a linha geométrica teve mínima de 46 mph e foi **cerca de 0,2 s mais lenta**;
- a linha ideal teve mínima de 42 mph e fez **8,831 s** no setor;
- o ápice tardio demais teve mínima de 41 mph e acelerou antes em posição, mas fez **9,2 s**.

([PSR](https://paradigmshiftracing.com/racing-basics/the-racing-line-four-elements-of-a-perfect-corner))

Ele também ordena os elementos de uma curva perfeita, do menos para o mais importante:

1. a espiral de entrada: uma entrada a velocidade constante custa no máximo cerca de 0,1 s por curva, se a saída for ideal;
2. a aceleração máxima a partir do ápice certo;
3. o uso de toda a largura da pista;
4. acima de tudo, encontrar o limite.

([PSR](https://paradigmshiftracing.com/racing-basics/the-racing-line-four-elements-of-a-perfect-corner))

A forma da curva admite duas soluções. As duas são ferramentas para trechos diferentes, não escolas rivais ([Fanatec, blog de fabricante](https://fanatec.com/explorer/games/gaming-tips/driving-style-v-shape-vs-u-shape-corners)):

- **Forma em V.** O piloto freia tarde e forte, ainda freia na entrada, aponta para o ápice e gira o carro, sacrificando velocidade mínima. Depois acelera cedo e com firmeza. Serve a curvas fechadas antes de retas longas.
- **Forma em U.** O piloto freia antes e de forma progressiva, descreve um arco arredondado com ápice tardio, mantém velocidade mínima alta e acelera aos poucos. Serve a curvas rápidas.

Krause e Bentley dão um limiar prático para o traço de velocidade. **Acima de cerca de 105 km/h, espera-se a forma em U; abaixo, a forma em V.** A exceção são carros com downforce acima de cerca de 120 km/h ([Speed Secrets, Data for Drivers](https://speedsecrets.com/wp-content/uploads/2018/01/Data-for-Drivers-PRINT-Full.pdf)).

A regra "entrar devagar para sair rápido" funciona "mais vezes do que não funciona", diz Bentley ([Speed Secrets](https://speedsecrets.com/q-does-slow-in-fast-out-always-work/)). Mas o próprio material do Speed Secrets sobre velocidade mínima aponta a ênfase exagerada nessa regra como uma das causas de redução excessiva de velocidade. As outras causas são a atenção à troca de marchas, os hábitos de frenagem com o pé esquerdo e o medo de não conseguir recuperar o carro. O exercício "terceira marcha sem freio" (3GNB) isola quatro pontos: o ponto de alívio, o ponto de entrada, a taxa de esterçamento e a retomada. **Num curso da UC Davis, todos os alunos foram mais rápidos nesse exercício do que numa sessão livre de 30 minutos** ([Speed Secrets vMin](https://speedsecrets.com/wp-content/uploads/2025/08/4-vMin.pdf)). Brouillard concorda com entrar devagar, mas ataca o mito do ápice tardíssimo para acelerar mais cedo. Numa linha mais longa, o ponto de aceleração chega quase no mesmo instante, e a volta piora ([PSR, mitos](https://www.paradigmshiftracing.com/racing-basics/the-5-biggest-driving-technique-myths)).

A prioridade entre as curvas é o que transforma técnica em tempo de volta. A Driver61 propõe esta ordem ([Driver61](https://driver61.com/?p=964078); [Driver61, prioridades](https://driver61.com/uni/prioritising-corners/)):

1. a curva mais rápida que alimenta a reta mais longa;
2. as curvas depois de retas, ou seja, as zonas de frenagem;
3. as curvas que levam a outras curvas.

Antes de uma reta longa, o piloto freia relativamente cedo, entra tarde e faz o ápice a dois terços ou três quartos da curva, porque cada 1 mph a mais na saída se carrega pela reta inteira. Em sequências de curvas, trabalha-se de trás para frente a partir da última curva antes da reta, aceitando compromissos nas anteriores.

A Paradigm Shift discorda no caso de curvas isoladas. Para ela, uma curva isolada se otimiza da mesma forma, seja qual for a reta seguinte, e enviesar a linha para acelerar antes cria um "falso ápice". Ela também critica medir a velocidade de saída num ponto fixo, em vez de medir o tempo desde o ponto de frenagem ([PSR, mitos](https://www.paradigmshiftracing.com/racing-basics/the-5-biggest-driving-technique-myths)). A divergência é em boa parte de definição, porque a Driver61 fala de curvas encadeadas. Em combinações de curvas, o olhar vai para a saída da sequência inteira ([Winding Road](https://windingroad.com/articles/features/speed-secrets-connect-the-dots/)).

Aplicada a Interlagos (inferência deste relatório, não das fontes), a regra da Driver61 dá peso máximo a dois trechos:

- a sequência S do Senna–Curva do Sol, que alimenta a Reta Oposta;
- a Junção, que alimenta a subida dos boxes e a reta principal.

O miolo do circuito deve ser analisado como uma sequência encadeada, de trás para frente a partir da sua saída.

### Aceleração, tração e marchas: retomar cedo sem precisar aliviar depois

No acelerador, os erros têm desenho reconhecível no traço ([Coach Dave Academy](https://coachdaveacademy.com/tutorials/a-delta-guide-how-to-use-throttle-traces-to-improve/)):

- **Acelerar cedo demais.** O traço sobe com o volante ainda esterçado e depois "sobe, cai e sobe de novo", sinal de potência na fase errada.
- **Acelerar tarde.** A volta de referência chega ao acelerador pleno muito antes.
- **Aliviar antes da frenagem.** Uma queda gradual do acelerador antes do freio indica fase sem pedal longa demais.
- **Oscilações no meio da curva.** Pequenas variações indicam incerteza sobre o equilíbrio do carro.
- **Pedal mal calibrado (no simulador).** Um pedal que não chega a 100% ou não volta a 0% custa tempo.

A Racers360 lembra a ordem causal. Acelerar cedo costuma ser uma compensação para a redução excessiva de velocidade, e não a corrige. Por isso, primeiro se corrigem a zona de frenagem e o trail braking ([Mazda/Racers360](https://www.mazdamotorsports.com/2020/02/25/driving-tip-1-the-top-mistakes-grassroots-race-car-drivers-make/)). A mesma fonte chama de "largamente incorreta" a regra de estar sempre no freio ou no acelerador, porque profissionais passam por uma breve fase sem pedal no meio da curva. Van Noy também trata essa fase como "uma forma leve de frenagem" ([NASA Speed News](https://nasaspeed.news/columns/driver-instruction/the-art-of-releasing-the-brakes/)). Já a fase sem pedal antes da zona de frenagem é um erro para Bentley ([Bentley 2020](https://speedsecrets.com/wp-content/uploads/2020/01/COACHING-WITH-DATA.pdf)). As fontes falam de fases diferentes da curva e não se contradizem.

A tração se administra pela posição do carro na pista. Se o acelerador pleno no ápice provoca patinação, a aplicação deve ser progressiva, à medida que o volante abre. A aceleração máxima começa assim que for capaz de levar o carro até a borda externa na saída ([PSR](https://paradigmshiftracing.com/racing-basics/the-racing-line-four-elements-of-a-perfect-corner)). Em carros com mais potência do que aderência, o exercício é manter o ponto de retomada e construir a pressão no pedal devagar, até o limite de tração ([Blayze](https://blayze.io/blog/car-racing/drills/high-horsepower-throttle-control)). Em curvas de alta velocidade, o acelerador de manutenção mantém a traseira estável ([NASA Speed News](https://nasaspeed.news/columns/driver-instruction/the-art-of-releasing-the-brakes/)).

Nas marchas, a regra é concluir as reduções ainda durante a frenagem, antes do ponto de entrada, sem alterar a pressão no pedal de freio. O toque de acelerador na redução (blip), de cerca de 10%, deve vir colado ao acionamento da embreagem, porque alguns décimos de segundo de atraso custam mais de 2.000 rpm. Sem blip, a embreagem precisa ser solta devagar, o que leva a reduzir demais a velocidade na entrada ([Blayze](https://blayze.io/blog/heel-and-toe-downshifting)). A troca antecipada de marcha (short-shift) serve em três situações: curvas em que tirar a mão do volante é inconveniente, trechos em descida e casos em que a curva de potência do motor pede a troca ([Speed Secrets](https://speedsecrets.com/short-shift-explained/)). Num monoposto com câmbio sequencial por borboletas e blip automático, configuração comum no simulador, a técnica de punta-tacco perde importância. O momento das reduções e o excesso de reduções, porém, continuam mensuráveis.

### Visão, consistência, pneus e chuva sustentam as demais técnicas

A visão é apontada como causa raiz de muitos erros técnicos: frenagem tarde ou cedo, ápices perdidos e volante em excesso ([Driver61](https://driver61.com/uni/braking/)). Ken Hill a chama de "a habilidade mais subestimada do automobilismo" e ensina o olhar sempre um passo à frente ([Blayze](https://blayze.io/blog/car-racing/what-to-work-on-next-for-on-track-improvement)):

- durante a frenagem, olhar para o ponto de entrada;
- durante o esterçamento, olhar para o ápice;
- no ápice, olhar para a saída.

O método de "ligar os pontos" encadeia ponto de entrada, ápice e saída num arco contínuo, com a visão periférica como fonte principal de informação. O erro típico é fixar o olhar no ápice e perder o ângulo de saída ([Winding Road](https://windingroad.com/articles/features/speed-secrets-connect-the-dots/)). A antecipação do olhar deve ser medida em tempo, não em distância ([Driver61](https://driver61.com/uni/prioritising-corners/)).

A consistência vem antes do ritmo: "não aumente o ritmo até ser consistente no ritmo atual". E muda-se uma variável por vez, porque não se resolve uma equação com mais de uma incógnita ([Winding Road/Dev Clough](https://windingroad.com/articles/features/speed-secrets-consistency/)). As metas citadas pelas fontes são:

- **voltas dentro de 0,3 a 0,5 s** e **dispersão de 3 a 5 pés (≈1 a 1,5 m) no ponto de frenagem** ([Blayze](https://blayze.io/blog/car-racing/what-to-work-on-next-for-on-track-improvement));
- ficar a cerca de 0,25 s da melhor volta contínua e a cerca de 0,5 s da volta teórica ([Grassroots Motorsports](https://grassrootsmotorsports.com/articles/10-ways-move-beyond-lap-times)).

A gestão de pneus é ensinada como evitar travamentos, escorregamentos e rodadas e manter o pneu na janela de temperatura. Sobre o aquecimento dos pneus, há uma contradição documentada. O zigue-zague é o método mais popular ([Fanatec, blog](https://www.fanatec.com/uk/en/explorer/games/gaming-tips/tire-management-in-endurance-sim-racing/)). Porém, um teste de pequena amostra no iRacing, com um GT3, encontrou **+10 °C freando forte contra +3,9 °C em zigue-zague**. O mesmo teste associou escorregamentos grandes e subesterço prolongado ao superaquecimento ([simracingcockpit, blog](https://simracingcockpit.gg/the-science-of-tyre-warming-in-iracing-testing-shows-braking-beats-weaving/)).

Na chuva, a trajetória seca, coberta de borracha, fica escorregadia. As fontes recomendam ([Driver61](https://driver61.com/uni/secrets-to-winning-in-the-wet/); [HP Academy](https://www.hpacademy.com/courses/race-driving-fundamentals/wet-vs-dry-lines-wet-vs-dry-lines/)):

- frear a três metros ou mais da linha habitual, ou a uma largura de carro dela;
- fazer a curva mais "quadrada", com ápice tardio;
- não aceitar escorregamentos nem patinação, que custam mais tempo do que no seco.

Por isso, voltas na chuva devem ficar fora de uma referência de pista seca. As técnicas de disputa completam o catálogo ([Driver61](https://driver61.com/uni/how-to-overtake-in-motorsport/); [Blayze](https://blayze.io/blog/car-racing/defend-your-position-on-track)):

- ultrapassagem por dentro na frenagem, ultrapassagem por fora e cruzamento de trajetória;
- defesa com um único movimento e prioridade à boa saída de curva.

Essas técnicas, porém, estão fora do alcance de uma telemetria de carro único.

### Do kart ao Hypercar, a progressão acrescenta camadas sobre a mesma base

No kart, a ordem de ensino é bastante estável:

1. segurança e controle do kart;
2. visão;
3. traçado;
4. ponto de frenagem no limiar;
5. trail braking;
6. administração da rotação do motor;
7. disputa.

Treinadores experientes ensinam traçado antes de frenagem: "acertado o traçado, frenagem e acelerador tendem a se resolver". Eles também lembram que karts de baixa potência permitem adiar o aprendizado da frenagem. Isso cria hábitos que precisam ser desfeitos em máquinas mais rápidas ([KartPulse](https://forums.kartpulse.com/t/when-and-how-to-introduce-braking/2086)). O programa para iniciantes da Kartclass ensina ([Kartclass](https://kartclass.com/blogs/beginner-guides/basic-karting-tips)):

- empurrar o volante, com cerca de 70% do esforço vindo da mão externa;
- manter a cabeça reta;
- olhar em sequência (ponto de frenagem, ápice, saída);
- fazer trail braking com pressão inicial firme e soltura até o ápice;
- manter a rotação do motor na faixa de potência;
- buscar o limite volta a volta.

Os critérios formais de progressão medem segurança e experiência, não velocidade. No Reino Unido, o curso ARKS tem prova teórica e avaliação prática. Depois, um comissário assina a licença após cada evento, confirmando que o piloto "pilotou com segurança e em controle" ([Motorsport UK](https://getstarted.motorsportuk.org/karting/)). As licenças internacionais de kart (ITG, ITF e ITE) exigem acúmulo de competições, não um teste de desempenho ([FIA Anexo L 2026](https://api.fia.com/system/files/documents/appendix_l_2026_publie_le_24_juin_2026.pdf)).

As escolas e os programas de fabricantes seguem a mesma escada:

1. controle e segurança: pista de derrapagem, frenagem no limiar e visão;
2. traçado e frenagem no circuito, com coaching individual;
3. análise de dados com engenheiro, só nos níveis intermediários e avançados;
4. por fim, o carro de corrida e a disputa.

No Porsche Track Experience australiano, o nível 3 introduz linhas, trail braking e coaching individual. Só o nível 4 acrescenta análise de dados com engenheiro ([Porsche](https://newsroom.porsche.com/en_AU/2020/sport-lifestyle/porsche-track-experience-explained-22262.html)). Na Ferrari, o Corso Pilota Evoluzione+ acrescenta telemetria, e o nível Race prepara o aluno para o Ferrari Challenge ([Ferrari of San Francisco](https://www.ferrarisanfrancisco.com/corso-pilota.htm)).

Na escada dos monopostos, o Anexo L da FIA associa cada grau de licença a uma faixa de relação peso-potência: ITC-C de 2 a 3 kg/hp, ITB de 1 a 2 kg/hp e ITA até 1 kg/hp. A Superlicença exige 40 pontos em três temporadas ([FIA Anexo L 2026](https://api.fia.com/system/files/documents/appendix_l_2026_publie_le_24_juin_2026.pdf)). Na prática, cada degrau acrescenta uma classe de potência.

As academias de Fórmula 1 treinam além da velocidade. George Russell descreveu sessões de simulador em que engenheiros propunham problemas a resolver, com foco em consistência e retorno técnico, não em tempo de volta. Dan Ticktum disse que é preciso aprender a dar um retorno estruturado aos engenheiros ([Autosport](https://www.autosport.com/general/news/whats-the-point-of-an-f1-junior-5111182/5111182/)). A Ferrari Driver Academy avaliava as reações dos pilotos a sucesso e derrota e julgava o desempenho por valores médios ([Motorsport.com](https://www.motorsport.com/f1/news/how-ferrari-is-preparing-its-future-f1-stars-1000784/)). Rob Wilson acrescenta um motivo para ensinar os fundamentos em carros com menos aderência: **muita aderência e downforce mascaram os comandos do piloto** ([AA Directions](https://www.aa.co.nz/membership/aa-directions/driver/q-and-a-rob-wilson-legendary-f1-motorsport-coach/)). Isso pesa para um iniciante num Fórmula 3 com downforce.

No endurance, a habilidade dominante deixa de ser a volta única e passa a ser o ritmo repetível:

- **Tristan Nunez** chama a consistência, com voltas dentro de cerca de três décimos, de "a maior habilidade que um piloto pode aprender". **Oliver Jarvis** diz que a classificação "não tem reflexo no resultado" da corrida e que o que conta é ser rápido no tráfego e ter bom ritmo médio ([RACER](https://racer.com/2019/05/27/masters-of-endurance/)).
- A **equipe Alpine de endurance** pede que o piloto poupe os freios para o colega, administre o combustível e aceite pneus usados e acertos compartilhados ([Renault Group](https://www.renaultgroup.com/en/magazine/our-group-news/alpine-endurance-team-the-ideal-driver-line-up/)).
- **Nick Tandy** explica que, em Le Mans, um protótipo precisa completar a ultrapassagem de um GT3 nos primeiros 20% da frenagem, porque fora da trajetória a pista está suja ([CAR Magazine](https://carmagazine.co.uk/features/car-culture/le-mans-2024-traffic)).

A Categorização de Pilotos da FIA formaliza esse critério. As revisões usam o **ritmo médio das 10 voltas mais rápidas em provas de até 2 h e das 20 mais rápidas em provas mais longas**, descartando classificação e treinos ([FIA Categorização 2025](https://api.fia.com/sites/default/files/driver_categorisation_regulations_2025_0.pdf)). No WEC, a classe Hypercar não admite pilotos Bronze ([FIA WEC](https://www.fiawec.com/en/news/fia-driver-categorisation/8258)).

| Nível | Onde aparece | Foco técnico ensinado | Como a progressão é verificada |
|---|---|---|---|
| 1. Iniciante | Kart de aluguel, primeiro dia de escola, primeiras sessões no simulador | Posição de pilotagem, segurança, visão em sequência, referências fixas, traçado de borda a borda, frenagem em linha reta, ponto de frenagem que avança a cada volta | "Pilotou com segurança e em controle" ([Motorsport UK](https://getstarted.motorsportuk.org/karting/)); consistência antes de ritmo ([Winding Road](https://windingroad.com/articles/features/speed-secrets-consistency/)) |
| 2. Básico | Kart de clube, escola de três dias, Porsche nível 1–2 | Frenagem no limiar, soltura progressiva, ápice tardio em curvas lentas, acelerador progressivo com o volante abrindo, correção de sobresterço | Retorno em paradas no box e voltas seguindo o instrutor ([Skip Barber](https://skipbarber.motorsportreg.com/events/3-day-racing-school-formula-car-njmp-skip-barber-855142)); dispersão de ≈1–1,5 m no ponto de frenagem ([Blayze](https://blayze.io/blog/car-racing/what-to-work-on-next-for-on-track-improvement)) |
| 3. Intermediário | F4, Fórmula Regional, Porsche nível 3–4 | Trail braking ajustado por curva, rotação com freio e acelerador, prioridade entre curvas e sequências, forma V ou U por curva, frenagem com downforce | Análise de dados com engenheiro ([Porsche](https://newsroom.porsche.com/en_AU/2020/sport-lifestyle/porsche-track-experience-explained-22262.html)); voltas numa janela de 0,3–0,5 s |
| 4. Avançado | F3, F2, GT3 | Trail braking como ajuste de equilíbrio (5–10% até o acelerador), sobreposição de pedais, gestão de pneus no stint, retorno técnico estruturado | Consistência no simulador e reuniões técnicas com engenheiros ([Autosport](https://www.autosport.com/general/news/whats-the-point-of-an-f1-junior-5111182/5111182/)) |
| 5. Profissional | F1, Hypercar, LMGT3 | Adaptação a carro e regulamento, gestão de energia e combustível, tráfego multiclasse, acerto compartilhado | Ritmo médio de corrida contra a média da categoria ([FIA Categorização 2025](https://api.fia.com/sites/default/files/driver_categorisation_regulations_2025_0.pdf)) |

## Escolas, treinadores e ferramentas ensinam em degraus e corrigem uma ou duas coisas por sessão

As escolas ensinam por exposição graduada e retorno imediato do instrutor. O curso de três dias da Skip Barber tem três etapas ([Skip Barber](https://skipbarber.motorsportreg.com/events/3-day-racing-school-formula-car-njmp-skip-barber-855142)):

1. sala de aula e autocross, com traçado, reduções de marcha e frenagem no limiar;
2. voltas seguindo o instrutor, voltas com parada no box para retorno em tempo real e exercícios dedicados de frenagem;
3. largadas, ultrapassagens e uso do vácuo.

O instrutor Gerardo Bonilla resume a filosofia da escola: "se você está tentando andar rápido, já está cometendo um erro" ([Motor Sport](https://www.motorsportmagazine.com/archive/article/december-2022/122/skip-barber-the-school-that-breeds-racing-champions%ef%bf%bc/)). A Allen Berg usa monopostos Tatuus com aquisição de dados MoTeC como "salas de aula sobre rodas". O aluno recebe acesso posterior aos próprios dados e vídeos ([ABRS](https://www.allenbergracingschools.com/?p=372)). A Bertil Roos usa carros que simulam perda de tração para treinar o controle e o olhar ([Bertil Roos](https://www.motorsportreg.com/events/bertil-roos-3-day-road-racing-school-dominion-raceway-066703)). Nenhuma dessas escolas publica critérios de aprovação: a progressão depende do julgamento do instrutor, e o resultado é uma recomendação de licença. A Winfield, escola por onde passaram Prost, Alesi e Hadjar, seleciona seus vencedores por uma seletiva final. Desde 2015, essa escolha é feita por um júri que também avalia apresentação e comunicação ([Wikipedia](https://en.wikipedia.org/wiki/Winfield_Racing_School)).

Os treinadores profissionais combinam observação, cronômetro, vídeo e dados:

- **Rob Wilson**, que diz ter trabalhado com cerca de metade do grid da F1, treina num carro de rua de dois lugares contra o cronômetro, que ele chama de "um ótimo detector de mentiras". Ele afirma identificar onde há margem de melhora em três minutos ([AA Directions](https://www.aa.co.nz/membership/aa-directions/driver/q-and-a-rob-wilson-legendary-f1-motorsport-coach/)).
- **Ross Bentley** lê primeiro o traço de velocidade, confirma com as acelerações e só então olha acelerador, freio e volante. Ele compara a volta mais rápida com as três ou quatro seguintes, para achar tendências. Limita o foco a **cerca de duas mudanças por sessão**. Dá metas mensuráveis, como "passar 3% a mais da volta com acelerador pleno", sem prescrever a técnica, para que o piloto descubra o como. E desaconselha copiar os dados de outro piloto, o que traz velocidade rápida e pouco aprendizado ([Bentley 2020](https://speedsecrets.com/wp-content/uploads/2020/01/COACHING-WITH-DATA.pdf)).
- **A Blayze** ordena seis fundamentos: posicionamento do carro, visão, controles motores, ajuste da frenagem, ponto e taxa de entrada e posição do corpo. Corrige primeiro o mais fraco, porque erros no topo da lista causam os de baixo. Trabalha com no máximo dois focos por sessão e explica "o quê, por quê e como" ([Blayze](https://blayze.io/blog/car-racing/blayze-motorsports-coaching-methodology)).
- **Os engenheiros da HP Academy** analisam o piloto antes do chassi e sobrepõem no máximo duas voltas. Procuram os "degraus" no canal de diferença de tempo e limitam o retorno a dois ou três pontos ([HP Academy](https://www.hpacademy.com/courses/professional-motorsport-data-analysis/aim-dash-logger-vw-tcr-step-4-analyse-driver)).

Os exercícios mais citados podem ser codificados num sistema de dados:

- marco de frenagem que avança a cada volta ([Driver61](https://driver61.com/uni/are-you-braking-too-early/));
- 3GNB, a terceira marcha sem freio ([Speed Secrets vMin](https://speedsecrets.com/wp-content/uploads/2025/08/4-vMin.pdf));
- subesterço proposital em curva longa ([Blayze](https://blayze.io/blog/car-racing/drills/understeer-scrub-speed-drill));
- construção lenta da pressão no acelerador ([Blayze](https://blayze.io/blog/car-racing/drills/high-horsepower-throttle-control));
- prática deliberada de diferentes tempos de soltura do freio ([Winding Road](https://windingroad.com/articles/features/speed-secrets-to-trail-brake-or-not-to-trail-brake-that-is-the-question/)).

Os livros clássicos não estavam acessíveis online e ficaram fora desta síntese: Taruffi, Going Faster! da Skip Barber, Alan Johnson, Drive to Win de Carroll Smith, Milliken e Haney. O conteúdo de livro efetivamente usado vem de três fontes. A primeira é o material de Ross Bentley e Peter Krause: o Speed Secrets e o manual Data for Drivers. A segunda é o livro de Jorge Segers sobre aquisição de dados, por meio dos indicadores que um estudo da TUM operacionalizou ([Speed Secrets, Data for Drivers](https://speedsecrets.com/wp-content/uploads/2018/01/Data-for-Drivers-PRINT-Full.pdf); [Betz et al.](https://arxiv.org/pdf/2005.10044)). A terceira é a série de Brian Beckman sobre física de corrida ([Beckman](https://gamedev.net/tutorials/programming/math-and-physics/the-physics-of-racing-part-1-weight-transfer-r1610)). Esse é o principal ponto fraco bibliográfico do relatório. O Going Faster!, com sua classificação de tipos de curva, merece consulta na versão impressa.

As ferramentas virtuais convergiram para o mesmo núcleo do projeto: comparar com uma volta de referência, dividir a curva em fases e ranquear a perda de tempo por trecho ([SimRacingManual](https://simracingmanual.com/resources/ai-driving-coaches/)). A diferença está na forma de entregar o retorno:

- **Trophi.ai.** Construída com a Driver61, fala no fone durante a volta. Ao sair de uma curva, nomeia a maior perda e dá a correção antes da próxima passagem. Limita-se a **uma ou duas mensagens por volta** e deixa o resto para um relatório depois da sessão ([Trophi](https://www.trophi.ai/sim-racing-coaching); [HOTLAP](https://hotlap.cc/en/trophi-ai-review/)). Não suporta o Assetto Corsa original.
- **Track Titan.** Aposta na causa raiz: os "Coaching Flows" procuram o erro anterior ao sintoma (por exemplo, uma entrada errada que força aceleração tardia) e o maior erro geral da volta. Suporta o Assetto Corsa ([Track Titan](https://www.tracktitan.io/post/november-2025-update-coaching-flows); [SimRacingManual](https://simracingmanual.com/resources/ai-driving-coaches/)).
- **Coach Dave Delta.** Divide cada curva em frenagem, entrada, ápice e saída, marcadas por cores. Recomenda focar uma ou duas curvas a cada saída para a pista e usar uma referência **0,5 a 1,5 s mais rápida** ([Coach Dave](https://coachdaveacademy.com/documentation/how-to-use-auto-insights-ai-coaching-in-delta/)).
- **hotlap.ai.** É o único que declara detectar a forma do trail braking, a sobreposição de comandos, o subesterço e o sobresterço e atribuir um "arquétipo" de estilo, mas sem publicar o método ([hotlap.ai](https://www.hotlap.ai/)).
- **Classificações em jogos.** A Driving Academy do Assetto Corsa EVO avalia por estrelas contra tempos-alvo, com pouca explicação ([Traxion](https://traxion.gg/everything-you-need-to-know-about-assetto-corsa-evos-driving-academy/)). O Safety Rating do iRacing se baseia em incidentes ([SimRacingCockpit](https://simracingcockpit.gg/iracing-safety-rating-explained/)). As duas são classificações de jogo, não avaliações de técnica.
- **Garmin Catalyst (pista real).** Fala antes e depois das curvas. Recusa a soma dos melhores setores, porque ela produz tempos "impossíveis de pilotar", e monta uma volta ótima só nos pontos em que trechos realmente pilotados se emendam ([Garmin](https://garmin.com/en-US/newsroom/?p=811)).
- **Apex Pro (pista real).** Não usa tempo. Mostra, com LEDs na visão periférica, o percentual da aderência estimada que o piloto está usando ([Apex Pro](https://apextrackcoach.com/product/apex-pro-gen-2/)).

| Ferramenta | Domínio | O que declara detectar | Como e quando fala | Referência usada |
|---|---|---|---|---|
| Trophi.ai | Simulador (sem Assetto Corsa original) | Ponto e pico de frenagem, consistência do trail braking, aceleração, sobresterço, perda por curva | Voz durante a volta, 1–2 mensagens, antes da curva na volta seguinte; relatório depois da sessão | Volta de especialista, da comunidade ou "do seu nível" |
| Track Titan | Simulador (inclui Assetto Corsa) | Causa raiz anterior ao sintoma, maior erro geral | Fluxos depois da sessão; pedais da referência sobrepostos ao vivo | Voltas profissionais; melhor volta própria |
| Coach Dave Delta | Simulador | Frenagem, entrada, ápice e saída por cores | Depois da sessão; 1–2 curvas a cada saída para a pista | Volta 0,5–1,5 s mais rápida |
| hotlap.ai | iRacing | Forma do trail braking, sobreposição de comandos, subesterço e sobresterço, marcha | Depois da volta; notas de S a F; "arquétipo" | Volta própria, teórica ou da comunidade |
| Garmin Catalyst | Pista real | Frenagem, linha, aceleração | Áudio antes e depois das curvas; aviso de "novo melhor" | Volta ótima emendada de trechos reais |
| Apex Pro | Pista real | Uso da aderência estimada | LEDs na visão periférica | Limite estimado do carro, sem tempo |

Nenhum fabricante publica regras de detecção, limiares ou validação. Os ganhos anunciados vêm do próprio fornecedor ou de revisores isolados ([SimRacingManual](https://simracingmanual.com/resources/ai-driving-coaches/)). As críticas recorrentes interessam diretamente ao projeto:

- o conselho se reduz a **"frear 8 m mais tarde"**, sem ensinar como;
- só algumas curvas são apontadas;
- a referência pode ser lenta ou de estilo diferente do piloto;
- a voz ao vivo distrai no começo: um revisor passou cerca de cinco minutos errando porque prestava atenção demais ao áudio ([SimRacingCockpit](https://simracingcockpit.gg/i-got-an-ai-sim-racing-coach-and-found-2-seconds-a-lap/)).

A única avaliação acadêmica de produto encontrada é do Toyota Research Institute, com 16 participantes. Nela, o retorno verbal entre voltas, gerado por um modelo de linguagem, melhorou no curto prazo o tempo de volta, a velocidade média e o controle de volante em comparação com um painel de dados. Houve um pouco mais de nervosismo, e o estudo não testou a retenção do aprendizado ([TRI](https://www.tri.global/research/dashboards-dialogue-evaluating-conversational-ai-coach-performance-driving-skill)).

Entre a pista real e a virtual, a técnica se transfere, mas as sensações não. As fontes registram isto:

- **Adam Brouillard** diz que o simulador reproduz muito bem as referências visuais. Ele trata a ausência de forças g como "treinamento com sensação reduzida" e valoriza a liberdade de experimentar sem consequência. Aponta os pneus como o mais difícil de simular ([Paradigm Shift](https://www.paradigmshiftracing.com/racing-basics/how-real-is-sim-racing)).
- **Pilotos de F1.** Verstappen cita as forças g como a maior diferença ([boxthislap](https://boxthislap.org/simracing-to-real-driving-differences/)). Norris cita a sensação de velocidade, e Alonso, o perigo e a adrenalina ([Formula1.com](https://www.formula1.com/en/latest/article/how-f1-drivers-used-the-virtual-world-to-prepare-for-the-brand-new-madring.368imxGahpd93RPYxOFdYv)).
- **James Baldwin**, piloto que veio do simulador, achou o comportamento no seco "muito comparável". Mas teve de aprender a chuva na pista real, porque os simuladores dão aderência demais no molhado ([The Race](https://www.the-race.com/gaming/baldwin-on-the-toughest-gamer-to-racer-challenges/)).
- **Gabriel Bortoleto** faz 400 a 500 voltas em casa para cada circuito novo, inclusive no Assetto Corsa com zebras modificadas, antes de usar o simulador da equipe ([boxthislap](https://boxthislap.org/gabriel-bortoletos-simrig-how-to-use-the-simracing-as-a-tool/)).

Para ensinar no simulador, a VRS substitui a sensação do corpo por outras pistas. O som é a principal: o arrasto dos pneus logo abaixo do limite é audível. Para travamentos, também servem a vibração do volante e a variação da rotação do motor ([VRS 3.3](https://virtualracingschool.com/academy/tag/car/); [VRS 3.4](https://virtualracingschool.com/academy/iracing-career-guide/second-season/braking-technique/)). Para o projeto, a consequência prática é dupla. As técnicas baseadas em referências visuais e no tempo de pedal e volante são as mais transferíveis. E os pedais load cell tornam a força de frenagem um canal repetível, o que os deixa ideais para ensinar o perfil de frenagem.

## Cada técnica deixa uma assinatura mensurável nos canais do Assetto Corsa

O fluxo padrão de análise tem seis passos ([Speed Secrets, Data for Drivers](https://speedsecrets.com/wp-content/uploads/2018/01/Data-for-Drivers-PRINT-Full.pdf)):

1. olhar a visão geral da volta;
2. encontrar incongruências;
3. perguntar por quê;
4. confirmar em outros canais;
5. comparar com outras voltas;
6. definir objetivos.

O canal de diferença de tempo acumulada (variance ou time slip) localiza a perda. Uma subida íngreme no canal mostra onde mais se perde tempo, e os três ou quatro trechos mais íngremes são o ponto de partida da análise. Há uma armadilha clássica: **um ganho com frenagem tardia seguido de uma perda maior na entrada, no ápice e na saída** ([HP Academy](https://www.hpacademy.com/courses/data-analysis-fundamentals/the-data-analysis-tool-box-variance-channel/)). Na grade de 2 m do projeto, a taxa de perda por metro é aproximadamente 1/v_volta − 1/v_ref, o que o coach de microssetores atual já calcula.

Para segmentar as curvas, um sistema especialista feito para engenheiros usou regras simples ([CEUR-WS](https://ceur-ws.org/Vol-2260/51_454-458.pdf)):

- a curva começa quando o freio passa de 30%, quando o acelerador cai mais de 30% do máximo ou quando o volante passa de 20%;
- cada curva é dividida em entrada, frenagem ativa e aceleração;
- a importância de cada curva é o comprimento da reta seguinte dividido pelo comprimento da volta.

Esse estudo registra que a análise manual de uma sessão de 15 minutos leva pelo menos uma hora, o que justifica automatizar.

Cinco cuidados vêm antes de qualquer indicador:

1. **Escala dos pedais.** Freio e acelerador no Assetto Corsa são frações de 0 a 1, não pressão em bar, então valores publicados em bar/s não se transferem. A referência é sempre a volta da IA ou a melhor volta do próprio piloto, porque cada simulador trata a frenagem máxima de um jeito ([Coach Dave](https://coachdaveacademy.com/tutorials/a-delta-guide-understanding-brake-traces-to-be-faster)).
2. **Escorregamento misto.** O canal de escorregamento das rodas do jogo mistura os componentes longitudinal e lateral. Para isolar travamento ou patinação, é preciso um cálculo longitudinal separado ou limitar a leitura a trechos de linha reta ([SimHub](https://simhubdash.com/community-2/dashboard-templates/plugin-calculate-longitudinal-wheel-slip)).
3. **Canais e unidades não confirmados.** Canais derivados exportados por jogos podem estar errados: o wiki do Automobilista 2 registra um canal de ângulo de roda incorreto ([AMS2 wiki](https://automobilista2.wiki.gg/wiki/Telemetry_analysis)). As notas também não confirmaram a unidade do canal de volante do AC (normalizado, graus de volante ou radianos de roda) nem a presença de ABS no carro do projeto. Um teste de desvio (a média do volante com |a_y| < 0,05 g deve ficar perto de zero) e uma curva conhecida para cada lado resolvem sinais e unidades ([HP Academy](https://www.hpacademy.com/courses/professional-motorsport-data-analysis/math-channels-advanced-math-channel-uses)).
4. **Base de tempo para derivadas.** Taxas como aplicação do freio, velocidade de esterçamento e reversões devem ser calculadas na base de tempo original, de cerca de 60 Hz, e só depois projetadas na grade de 2 m. A grade espacial distorce taxas temporais (inferência de engenharia deste relatório). O estudo de Nunes et al. trabalhou com iRacing também a 60 Hz ([Nunes et al. 2026](https://www.mdpi.com/1099-4300/28/9/960)).
5. **A IA não é ótima nem humana.** Num simulador profissional, o agente de IA frenava de modo diferente dos humanos por causa da forma como foi treinado ([Remonda et al. 2021](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0245320)). Diferenças contra a IA são diferenças, não necessariamente erros, e passagens em que o piloto é mais rápido que a IA não podem contar como erro.

As duas tabelas abaixo usam a notação dos canais do projeto:

- s: distância na volta;
- v, v_x, v_y: velocidade total e velocidades longitudinal e lateral no referencial do carro;
- r: velocidade de guinada;
- δ: ângulo de volante;
- a_x, a_y: acelerações longitudinal e lateral;
- Fz: carga de cada roda;
- β: ângulo de deriva do veículo;
- L: entre-eixos;
- s_b: ponto de frenagem;
- s_ti: ponto de entrada;
- s_vmin: ponto de velocidade mínima;
- s_pu: ponto de retomada do acelerador.

Os limiares numéricos são pontos de partida tirados das fontes. Todos devem ser recalibrados pela distribuição das voltas de referência em cada curva.

**Frenagem e entrada de curva**

| Técnica ou erro | Indicador | Cálculo com os canais do AC | Leitura | Fonte |
|---|---|---|---|---|
| Ponto de frenagem | Δs_b e dispersão | s_b = primeiro s com freio > 0,05 depois de acelerador < 0,05; diferença contra a referência; desvio-padrão entre voltas | Negativo = frenagem antecipada; dispersão alta = falta de referência | [Driver61](https://driver61.com/uni/prioritising-corners/); [Blayze](https://blayze.io/blog/car-racing/what-to-work-on-next-for-on-track-improvement) |
| Aplicação no limiar | Tempo até o pico; agressividade | Do início da frenagem ao primeiro mínimo de a_x; máximo de d(freio)/dt | Pilotos de corrida 0,38 s, não pilotos 1,12 s | [van Leeuwen et al.](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0186871); [Betz et al.](https://arxiv.org/pdf/2005.10044) |
| Perfil com downforce | Forma do pico | Pico cedo e pressão decrescente com v | Platô ou subida até o fim = início fraco | [VRS 3.4](https://virtualracingschool.com/academy/iracing-career-guide/second-season/braking-technique/) |
| Soltura abrupta | Taxa de soltura e carga dianteira | Mínimo de d(freio)/dt no último terço da soltura; queda de Fz_dianteira/ΣFz | Degrau = dianteira descarregada, ápice perdido | [Coach Dave](https://coachdaveacademy.com/tutorials/a-delta-guide-understanding-brake-traces-to-be-faster); [Winding Road](https://windingroad.com/articles/features/speed-secrets-to-trail-brake-or-not-to-trail-brake-that-is-the-question/) |
| Trail braking | Retenção, sobreposição, coordenação | freio(s_ti)/pico; duração com freio > ε e abs(δ) acima do limiar; correlação negativa entre d(freio)/ds e d abs(δ)/ds; fim da soltura em relação a s_vmin | Freio decresce de forma contínua enquanto o volante entra | [Speed Secrets](https://speedsecrets.com/wp-content/uploads/2018/01/Data-for-Drivers-PRINT-Full.pdf); [HP Academy g-g](https://www.hpacademy.com/courses/professional-motorsport-data-analysis/cornering-performance-gg-diagram/) |
| Travamento de roda | Pico de escorregamento | Escorregamento dianteiro em frenagem com volante perto de zero, contra a distribuição da referência; a_x estagnado com o freio subindo | Pico isolado = travamento; sempre o mesmo eixo = repartição de frenagem | [HP Academy, fórum](https://www.hpacademy.com/forum/professional-motorsport-data-analysis/show/brake-locking-maths-channel-formula-motorcycles/); [SimHub](https://simhubdash.com/community-2/dashboard-templates/plugin-calculate-longitudinal-wheel-slip); [Driver61](https://driver61.com/uni/braking/) |
| Pé esquerdo e sobreposição | Cruzamento de pedais | Freio > ε e acelerador > ε ao mesmo tempo; se coincide com redução de marcha, é blip | Sobreposição longa = técnica de pé esquerdo; curta na redução = blip | [HP Academy](https://www.hpacademy.com/courses/professional-motorsport-data-analysis/aim-dash-logger-vw-tcr-step-4-analyse-driver); [CEUR-WS](https://ceur-ws.org/Vol-2260/51_454-458.pdf) |
| Redução de marcha | Escorregamento traseiro na troca | Pico de escorregamento traseiro ou de β no instante em que a marcha cai | Redução cedo demais ou excessiva | [Blayze](https://blayze.io/blog/heel-and-toe-downshifting); [AMS2 wiki](https://automobilista2.wiki.gg/wiki/Telemetry_analysis) |
| Ponto e taxa de entrada | s_ti e máximo de dδ/dt | Primeiro s com abs(δ) > 10–20% do pico da curva; taxa nos 0,5 s seguintes | Entrada cedo com mais volante = ápice antecipado | [CEUR-WS](https://ceur-ws.org/Vol-2260/51_454-458.pdf); [Driver61](https://driver61.com/uni/racing-line/) |

**Meio de curva, saída e volta inteira**

| Técnica ou erro | Indicador | Cálculo com os canais do AC | Leitura | Fonte |
|---|---|---|---|---|
| Subesterço | Ângulo de subesterço | UA = sinal(r)·(δ_roda − L·r/v_x), só com abs(a_y) > 0,3–0,5 g; integral do volante contra a referência | UA > 0 = subesterço | [US 10293852](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10293852); [HP Academy](https://www.hpacademy.com/courses/professional-motorsport-data-analysis/math-channels-advanced-math-channel-uses) |
| Sobresterço e rotação | Deriva do veículo | β = atan2(v_y, v_x) e sua taxa; r − a_y/v_x; diferença entre os ângulos de deriva dianteiro e traseiro | β crescendo no sentido da rotação = traseira escapando | [Betz et al.](https://arxiv.org/pdf/2005.10044); [Binetti et al.](https://www.research.unipd.it/bitstream/11577/3514061/1/SAE_WCX_Drifting_Binetti.pdf) |
| Contraesterço e correções | Sinal oposto e reversões | sinal(δ)·sinal(r) = −1 por mais de 0,1–0,2 s; contagem de reversões de volante depois de filtrar o sinal | Correção de escorregamento; reversões frequentes = carro instável ou técnica | [Binetti et al.](https://www.research.unipd.it/bitstream/11577/3514061/1/SAE_WCX_Drifting_Binetti.pdf); [Markkula & Engström](https://eprints.whiterose.ac.uk/131534/); [Hojaji et al.](https://www.scitepress.org/Papers/2026/146096/146096.pdf) |
| Saída de pista por perda de controle | Guinada na saída | Velocidade de guinada durante a saída de pista | 124 °/s em pilotos de corrida contra 272 °/s em não pilotos | [van Leeuwen et al.](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0186871) |
| Suavidade do volante | Irregularidade | abs(δ − média móvel de 0,5 s de δ) | Maior = comandos bruscos | [HP Academy](https://www.hpacademy.com/courses/professional-motorsport-data-analysis/math-channels-advanced-math-channel-uses); [Betz et al.](https://arxiv.org/pdf/2005.10044) |
| Uso do círculo de atrito | Fração da aderência | √(a_x² + a_y²) dividido pelo envelope por faixa de velocidade e direção (percentis 95–99 de todas as voltas) | Região diagonal vazia = comandos separados | [HP Academy g-g](https://www.hpacademy.com/courses/professional-motorsport-data-analysis/cornering-performance-gg-diagram/); [Speed Secrets](https://speedsecrets.com/wp-content/uploads/2018/01/Data-for-Drivers-PRINT-Full.pdf) |
| Traçado e ápice | Desvio lateral e ápice | e(s) contra a linha de referência; ápice = máximo de r/v ou s_vmin | Ápice cedo + volante crescendo depois + alívio na saída = ápice antecipado | [Betz et al.](https://arxiv.org/pdf/2005.10044); [PSR](https://paradigmshiftracing.com/racing-basics/the-racing-line-four-elements-of-a-perfect-corner) |
| Forma V ou U | Profundidade e posição da mínima | v_min em relação às velocidades de entrada e saída; tempo com abs(a_y) baixo | Acima de ~105 km/h espera-se U; abaixo, V | [Speed Secrets](https://speedsecrets.com/wp-content/uploads/2018/01/Data-for-Drivers-PRINT-Full.pdf) |
| Largura da pista | Afastamento na saída | Máximo de abs(e) contra as bordas reconstruídas | Não chegar à borda = ápice tardio ou velocidade de ápice baixa | [PSR](https://paradigmshiftracing.com/racing-basics/the-racing-line-four-elements-of-a-perfect-corner) |
| Fase sem pedal | Tempo sem pedal | Acelerador < 0,05 e freio < 0,05 com v > 5 m/s por mais de 0,1 s; separar antes da frenagem e meio da curva | Profissional 1,99 s por volta, software autônomo 3,65 s | [Betz et al.](https://arxiv.org/pdf/2005.10044) |
| Retomada do acelerador | Ponto e aceitação | s_pu − s_vmin; ponto de pleno; aceitação = abs(a_y no pleno)/máximo abs(a_y) | Piloto humano 75% contra software autônomo 33% | [Betz et al.](https://arxiv.org/pdf/2005.10044) |
| Acelerador cedo | Volante crescendo depois da retomada | d abs(δ)/ds > 0 depois de s_pu | Subesterço de saída | [Blayze](https://blayze.io/blog/car-racing/what-is-understeer-and-how-to-correct-it) |
| Alívio depois da retomada | Reversões do acelerador | Quedas de 0,1–0,2 ou mais entre a retomada e o pleno | "Sobe, cai e sobe" | [Coach Dave](https://coachdaveacademy.com/tutorials/a-delta-guide-how-to-use-throttle-traces-to-improve/) |
| Patinação e sobresterço de potência | Escorregamento traseiro com acelerador | Pico de escorregamento traseiro com o acelerador subindo; β crescendo | Acelerador mais rápido que a aderência | [SimHub](https://simhubdash.com/community-2/dashboard-templates/plugin-calculate-longitudinal-wheel-slip); [HP Academy](https://www.hpacademy.com/courses/professional-motorsport-data-analysis/math-channels-advanced-math-channel-uses) |
| Distribuição do acelerador | Histograma | Fração do tempo em 0%, em 100% e entre 20% e 60% | Pilotos de corrida passam mais tempo em 0% e 100% | [van Leeuwen et al.](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0186871) |
| Troca de marcha | Rotação de troca | rpm antes de cada troca para cima contra a referência; tempo no limitador | Troca cedo ou tarde; excesso de rotação | [AMS2 wiki](https://automobilista2.wiki.gg/wiki/Telemetry_analysis) |
| Transferência de peso | Fração de carga | Fz dianteira/ΣFz e Fz externa/ΣFz ao longo da curva | Degraus = comandos bruscos | [Beckman](https://gamedev.net/tutorials/programming/math-and-physics/the-physics-of-racing-part-1-weight-transfer-r1610) |
| Pneus | Tendência térmica | Temperatura volta a volta contra a referência; eventos de escorregamento | Aquecimento por escorregamento | [simracingcockpit](https://simracingcockpit.gg/the-science-of-tyre-warming-in-iracing-testing-shows-braking-beats-weaving/) |
| Consistência | Dispersão | Desvio-padrão de s_b, pico de freio, v_min, s_pu e tempo da curva nas voltas válidas | Meta indicativa de 0,25–0,5 s na volta | [Grassroots Motorsports](https://grassrootsmotorsports.com/articles/10-ways-move-beyond-lap-times) |

A lógica dos indicadores de equilíbrio cabe numa frase: compara-se o que o piloto pede com o que o carro faz. Se o carro não escorregasse, o ângulo de roda necessário para produzir a guinada medida seria L·r/v, ou seja, entre-eixos vezes velocidade de guinada, dividido pela velocidade. Se o piloto está esterçando mais do que isso, a dianteira está escorregando, o que é subesterço. Se está esterçando menos, ou com sinal oposto, a traseira está escorregando, o que é sobresterço ([US 10293852](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10293852)). A patente que formaliza esse cálculo não divulga limiares, porque eles são ajustados em teste para cada carro. Ela também usa filtros de persistência para evitar alarmes falsos causados pelo ruído das derivadas. O estudo da TUM que aplicou os indicadores de Segers concluiu que esses índices de estabilidade dão **"tendência correta", não valor absoluto confiável** ([Betz et al.](https://arxiv.org/pdf/2005.10044)). Por isso, todo limiar deste catálogo deve ser calibrado pela distribuição das voltas de referência na mesma curva, e nenhum deve ser tratado como verdade física.

Algumas famílias do catálogo não têm um canal direto:

- **A visão** não pode ser medida sem rastreamento ocular. Ela só aparece por sintomas: dispersão do ponto de frenagem, entrada variável e volante em excesso.
- **A disputa e o tráfego** dependem de outros carros.
- **A gestão de pneus** só pode ser interpretada se as voltas comparadas tiverem estado térmico semelhante. Caso contrário, um "erro" pode ser apenas pneu frio.

## O estilo de um piloto é um conjunto de dimensões contínuas, e o carro decide qual estilo é premiado

No paddock, o vocabulário de estilo converge para cerca de dez dimensões, quase todas observáveis nos pedais, no volante e na velocidade. A tabela resume cada dimensão, os seus extremos e o indicador correspondente no AC.

| Dimensão | Extremos | Indicador no AC | Fonte |
|---|---|---|---|
| Forma da curva | V (frenagem tardia, rotação, aceleração cedo) ↔ U (frenagem progressiva, velocidade mínima alta) | Posição e profundidade de v_min; tempo com abs(a_y) baixo | [The Race 2024](https://www.the-race.com/formula-1/lewis-hamilton-f1-ground-effect-cars-driving-style-clash) |
| Resposta da dianteira na entrada | Precisa de rotação inicial forte ↔ precisa de traseira estável | Razão entre guinada e volante na entrada; β na entrada; eventos de contraesterço | [The Race, Gary Anderson](https://www.the-race.com/formula-1/gary-anderson-what-red-bulls-changed-to-give-verstappen-what-he-needs/) |
| Perfil de frenagem | Pico alto e curto ↔ pico menor e zona longa | Pico, tempo até o pico, taxa de soltura | [The Race, México 2025](https://www.the-race.com/formula-1/why-oscar-piastri-so-far-off-lando-norris-mexico-f1-2025) |
| Uso dos pedais | Binário ↔ sobreposto (acelerador parcial durante a frenagem) | Acelerador mínimo entre o alívio e a frenagem | [The Race, Hughes](https://www.the-race.com/formula-1/mark-hughes-charles-leclerc-key-skill-f1-azerbaijan-gp-qualifying) |
| Aplicação do volante | Agressiva ↔ progressiva; muito ↔ pouco volante | Taxa de esterçamento, pico de volante, reversões | [Motor Sport 2015](https://motorsportmagazine.com/articles/single-seaters/f1/kimis-struggles) |
| Perfil do acelerador | Binário ↔ modulado; cedo ↔ tarde | Tempo do ápice até o pleno; histograma do acelerador | [Honda Global](https://global.honda/en/mansell/Telemetry/) |
| Regime de aderência | Rápido com muita aderência ↔ rápido com pouca aderência | Desempenho relativo com pneu novo e com pneu usado no stint | [The Race, México 2025](https://www.the-race.com/formula-1/why-oscar-piastri-so-far-off-lando-norris-mexico-f1-2025) |
| Canal de sensibilidade | Sente o carro pela dianteira ↔ pela traseira | Sem indicador direto | [The Race 2026](https://www.the-race.com/formula-1/alonsos-ludicrous-f1-driving-style-explained/) |
| Adaptabilidade | Adapta-se ao carro ↔ depende do carro | Variação da assinatura entre carros e acertos | [Motor Sport 2015](https://motorsportmagazine.com/articles/single-seaters/f1/kimis-struggles) |
| Gestão de pneus e energia | Conservador ↔ agressivo | Perda de tempo ao longo do stint; alívio antes da frenagem | [Motor Sport (Prost)](https://www.motorsportmagazine.com/articles/single-seaters/f1/the-reason-for-alain-prosts-smooth-driving-style-i-couldnt-afford-a-mechanic/); [Autosport (Dixon)](https://www.autosport.com/indycar/news/indycar-fuel-save-secrets-explained-the-science-behind-dixons-magic/10513669/) |
| Condições de pista | Forte com aderência variável ↔ não | Fora do escopo em pista seca controlada | [The Race (Button)](https://www.the-race.com/formula-1/the-hidden-technique-behind-buttons-extraordinary-feel-for-conditions/) |

O catálogo de pilotos reais foi montado a partir de engenheiros, pilotos e jornalistas técnicos. Ele mostra um espectro com dois extremos. De um lado ficam pilotos que exigem rotação forte na entrada e toleram uma traseira solta. Do outro, pilotos que precisam de traseira estável ou de dianteira previsível para atacar a curva. A coluna de evidência indica o tipo de fonte, porque números de telemetria são raros.

| Piloto (período) | Traços documentados | Evidência | Fonte |
|---|---|---|---|
| Max Verstappen (2015–) | Dianteira muito responsiva; tolerância alta a traseira nervosa em curva rápida; precisa de rotação inicial e de "um toque de subesterço que diminui com o volante"; nega ter um estilo fixo | Jornalista técnico, ex-projetista e o próprio piloto | [The Race](https://the-race.com/formula-1/what-is-a-pointy-front-end-max-verstappen-f1-preference); [The Race, G. Anderson](https://www.the-race.com/formula-1/gary-anderson-what-red-bulls-changed-to-give-verstappen-what-he-needs/); [F1.com](https://www.formula1.com/en/latest/article/verstappen-dispels-popular-driving-style-myth-after-first-laps-in-red-bulls.3Iu22u4oZbq0QpZo6sKYS2) |
| Sergio Pérez (2021–24) | Precisa de estabilidade traseira na frenagem para entrar com o carro; não sobrecarrega a dianteira; acelera forte e cedo | Piloto e jornalista | [Pit Debrief](https://www.pitdebrief.com/?p=27601); [The Race](https://www.the-race.com/formula-1/mark-hughes-charles-leclerc-key-skill-f1-azerbaijan-gp-qualifying) |
| Alex Albon | Prefere muita dianteira, mais que Russell e Leclerc nas categorias de base | Piloto | [The Race](https://the-race.com/formula-1/what-is-a-pointy-front-end-max-verstappen-f1-preference) |
| Lewis Hamilton (2007–) | Forma em V; entra antes, com mais volante, e acelera mais tarde; freia de forma reativa, passando do limite e depois modulando; em 2024 perdeu mais de 0,1 s em curvas isoladas para Russell em cinco classificações | Jornalista, engenheiro e dados de tempo | [The Race 2024](https://www.the-race.com/formula-1/lewis-hamilton-f1-ground-effect-cars-driving-style-clash); [The Race 2025](https://www.the-race.com/formula-1/whats-behind-hamiltons-ferrari-brake-struggle-and-how-to-fix-it) |
| George Russell | Freia um pouco antes, entra mais tarde e carrega mais velocidade (mais próximo do U) | Jornalista | [The Race 2024](https://www.the-race.com/formula-1/lewis-hamilton-f1-ground-effect-cars-driving-style-clash) |
| Charles Leclerc | Sobrepõe alívio e frenagem; freia mais cedo mantendo **7–11% de acelerador** (Baku 2024), enquanto os rivais vão a 0%; aceita traseira viva | Dados divulgados por jornalista | [The Race, Hughes](https://www.the-race.com/formula-1/mark-hughes-charles-leclerc-key-skill-f1-azerbaijan-gp-qualifying) |
| Carlos Sainz | Analítico; forte em curvas rápidas e em condições imprevisíveis; teve de mudar entrada, frenagem e velocidade de curva na Ferrari | Jornalista e piloto | [The Race](https://the-race.com/formula-1/why-ferraris-leclerc-sainz-pairing-is-the-best-in-f1/); [Motorsport.com](https://www.motorsport.com/f1/news/sainz-pushing-adapt-ferrari-car/6525116/) |
| Lando Norris | Forma em U, entrada progressiva; rápido com pouca aderência e forte no fim do stint; "desafia a frenagem e o escorregamento traseiro" | Engenheiro e dados | [The Race, abr. 2025](https://www.the-race.com/formula-1/why-mclaren-weakness-hurting-lando-norris-more-than-oscar-piastr/); [The Race, out. 2025](https://www.the-race.com/formula-1/why-oscar-piastri-so-far-off-lando-norris-mexico-f1-2025) |
| Oscar Piastri | Forma em V em grampos; rápido com muita aderência; troca pico de freio por zona de frenagem mais longa | Engenheiro e dados | [The Race, out. 2025](https://www.the-race.com/formula-1/why-oscar-piastri-so-far-off-lando-norris-mexico-f1-2025) |
| Daniel Ricciardo (McLaren 2021) | Freia antes e carrega velocidade num carro que pedia frenagem tardia e volante progressivo; **50 pontos contra 113 de Norris** depois de 11 provas | Engenheiro e dados | [The Race 2021](https://the-race.com/formula-1/what-makes-peculiar-mclaren-so-hard-for-ricciardo-to-master/) |
| Fernando Alonso | Coordenação fina entre volante e acelerador; sente o carro pela dianteira; adapta-se ao carro | Jornalista e engenheiro | [The Race 2026](https://www.the-race.com/formula-1/alonsos-ludicrous-f1-driving-style-explained/); [Motor Sport 2015](https://motorsportmagazine.com/articles/single-seaters/f1/kimis-struggles) |
| Kimi Räikkönen | Muito sensível à dianteira; em curvas lentas entra hesitante, esperando a dianteira responder | Engenheiro e jornalista | [Motor Sport 2015](https://motorsportmagazine.com/articles/single-seaters/f1/kimis-struggles) |
| Sebastian Vettel (2009–12) | Mantinha o acelerador com a traseira escapando, para aumentar o fluxo de escape no difusor e ganhar aderência traseira | Jornalista | [The Race 2026](https://www.the-race.com/formula-1/the-traits-that-explain-vettels-lopsided-f1-career/) |
| Jenson Button | Forma em U; pouco volante; curso longo do acelerador; "os pés fazem o trabalho"; sensível a traseira instável | Engenheiro e jornalista | [The Race 2026](https://www.the-race.com/formula-1/the-hidden-technique-behind-buttons-extraordinary-feel-for-conditions/) |
| Alain Prost | Pilotava a 90–95% do limite; suave com freios e combustível | Piloto e equipe | [Motor Sport 2025](https://www.motorsportmagazine.com/articles/single-seaters/f1/the-reason-for-alain-prosts-smooth-driving-style-i-couldnt-afford-a-mechanic/) |
| Nigel Mansell | Uso binário dos pedais: acelerador pleno, frenagem forte, acelerador pleno; único que não aliviava na saída do túnel em Mônaco | Engenheiros da Honda | [Honda Global](https://global.honda/en/mansell/Telemetry/) |
| Ayrton Senna | Acelerador pulsado no meio da curva; não há dados públicos, só hipóteses | Treinador; experimento de 2026 | [Speed Secrets](https://speedsecrets.com/q-do-you-have-any-insights-into-ayrton-sennas-throttle-use/); [The Drive](https://www.thedrive.com/news/we-tested-sennas-wild-throttle-technique-loafers-and-all) |
| Scott Dixon (IndyCar) | Economia de combustível com alívio antes da frenagem e ajuste dos pontos de frenagem volta a volta | Piloto e engenheiro | [Autosport](https://www.autosport.com/indycar/news/indycar-fuel-save-secrets-explained-the-science-behind-dixons-magic/10513669/) |
| Fässler, Lotterer e Tréluyer (Audi, endurance) | Estilos quase iguais e cerca de 95% de acerto em comum; para eles, "não há mil maneiras" de fazer um carro rápido | Pilotos | [Motorsport.com](https://us.motorsport.com/wec/news/audi-co-drivers-reveal-how-they-work-together-as-a-coherent-whole/2830286/) |
| Hartley e Conway (Toyota GR010, Hypercar) | A potência constante do Hypercar mudou a aceleração e o tráfego em relação ao LMP1 | Pilotos | [Motorsport Week](https://motorsportweek.com/2021/08/18/traffic-management-different-for-toyota-drivers-due-to-hypercar-characteristics/) |
| James Baldwin (do simulador ao GT3 real) | Comportamento no seco comparável ao ACC; chuva e consequência dos erros aprendidas na pista | Piloto | [The Race 2020](https://www.the-race.com/gaming/baldwin-on-the-toughest-gamer-to-racer-challenges/) |

O catálogo deixa três lições:

1. **O rótulo de estilo depende do carro e do regulamento.** Norris e Piastri trocaram de rótulo entre abril e outubro de 2025 ([The Race](https://www.the-race.com/formula-1/why-mclaren-weakness-hurting-lando-norris-more-than-oscar-piastr/)). O V de Hamilton servia aos Mercedes de 2014–21, mas entrou em choque com os carros de efeito solo de 2022–24, que premiam frenagem anterior e velocidade carregada pela curva ([The Race](https://www.the-race.com/formula-1/lewis-hamilton-f1-ground-effect-cars-driving-style-clash)). A vantagem de Vettel dependia do difusor soprado pelo escape.
2. **Rótulos populares são contestados.** Verstappen diz que não sabe nomear o próprio estilo e que se adapta ao carro ([F1.com](https://www.formula1.com/en/latest/article/verstappen-dispels-popular-driving-style-myth-after-first-laps-in-red-bulls.3Iu22u4oZbq0QpZo6sKYS2)). Gary Anderson descreve a preferência dele como necessidade de rotação inicial, não como gosto por sobresterço ([The Race](https://www.the-race.com/formula-1/gary-anderson-what-red-bulls-changed-to-give-verstappen-what-he-needs/)). A própria Mercedes atribuiu uma diferença de treino entre Hamilton e Russell a composto de pneu e acerto, não a estilo ([GPBlog](https://www.gpblog.com/en/news/114162/shovlin-explains-big-difference-between-russell-and-hamilton-in-fp2.html)).
3. **Impor a técnica de outro piloto pode piorar o desempenho.** Ricciardo foi incentivado a copiar Norris e nunca se adaptou naturalmente ([The Race](https://www.the-race.com/formula-1/lewis-hamilton-f1-ground-effect-cars-driving-style-clash)). Button não conseguia usar a técnica de Barrichello de acrescentar volante contra o sobresterço, porque "perdia toda a referência do carro" ([The Race](https://www.the-race.com/formula-1/the-hidden-technique-behind-buttons-extraordinary-feel-for-conditions/)). Há um contraponto. Lotterer diz que "não há mil maneiras" de fazer um carro rápido ([Motorsport.com](https://us.motorsport.com/wec/news/audi-co-drivers-reveal-how-they-work-together-as-a-coherent-whole/2830286/)). Bentley, por outro lado, diz que "há mais de uma maneira de andar rápido" ([Speed Secrets](https://speedsecrets.com/q-do-you-have-any-insights-into-ayrton-sennas-throttle-use/)).

Sobre estilos de pilotos virtuais, a pesquisa não encontrou documentação confiável por piloto, com telemetria. O mais próximo é o "arquétipo" atribuído pelo hotlap.ai, sem método publicado ([hotlap.ai](https://www.hotlap.ai/)). O único estudo acadêmico de clustering de estilo na F1 usa médias por volta: tempo relativo, consistência, degradação e ultrapassagens. Ele chega a quatro grupos, e um classificador identifica o piloto em 78,3% dos casos. Mesmo assim, o carro domina o tempo de volta ([Taylor & Secco 2026](https://hira.hope.ac.uk/id/eprint/4949/)).

Não há uma tabela publicada por engenheiros que ligue estilo a técnica. Mesmo assim, as fontes sustentam uma regra com três entradas:

- **A assinatura do piloto** nas dimensões acima.
- **O estilo que o carro e a curva premiam.** Andrea Stella resumiu isso ao falar do McLaren de 2021: "esta é a ferramenta, ela é rápida, mas precisa ser pilotada de certa maneira" ([The Race](https://the-race.com/formula-1/what-makes-peculiar-mclaren-so-hard-for-ricciardo-to-master/)).
- **O custo medido** em tempo.

Para um piloto que tende ao V, as ferramentas são frenagem tardia e forte, freio mantido na entrada e dianteira que responde rápido. Para quem tende ao U, são a combinação progressiva entre soltura do freio e esterçamento e uma dianteira com aderência no ápice ([Fanatec](https://fanatec.com/eu-en/explorer/games/gaming-tips/driving-style-v-shape-vs-u-shape-corners/); [The Race](https://www.the-race.com/formula-1/why-mclaren-weakness-hurting-lando-norris-more-than-oscar-piastr/)). As duas formas envolvem sobreposição de freio e volante. Por isso, a diferença entre elas está na taxa de soltura e no pico de freio, não na presença ou ausência de trail braking.

## Clusterizar o tipo de habilidade de um iniciante redescobre o cronômetro

Os dois estudos revisados por pares que aplicaram k-means a voltas de simulador chegaram ao mesmo resultado: **níveis de desempenho ordenados por tempo, não estilos**.

- **Remonda, Veas e Luzhnica.** Agruparam 258 voltas de 13 pessoas (2 pilotos com experiência de Fórmula 3 e 11 estudantes) num Dallara F312 em Barcelona e obtiveram seis níveis, do pior ao excelente. O grupo pior apareceu nas primeiras sessões e **desapareceu nas sessões 4 e 5**. Ou seja, os grupos mediam estágio de aprendizagem. As variáveis de volante não mostraram tendência clara entre os níveis ([Remonda et al. 2021](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0245320)).
- **Hojaji, Toth e Campbell.** Agruparam 865 voltas de 135 participantes no Assetto Corsa Competizione e obtiveram três grupos, com **tempos médios de 86,4, 91,2 e 96,8 s**. Um classificador XGBoost acertou o grupo de cada volta com acurácia de 0,87 e AUC de 0,90. Entre as variáveis mais importantes estavam a taxa de reversão de volante, o desvio de trajetória, o sobresterço e a duração do trail braking ([Hojaji et al. 2026](https://www.scitepress.org/Papers/2026/146096/146096.pdf)).

O estudo de Hojaji também ilustra o risco de prometer ganho. A volta "otimizada" de 81–82 s saiu de um modelo linear de previsão, não de uma volta pilotada. A melhor volta humana medida foi de 86 s.

A análise de poder estatístico de Dalmaijer, Nord e Astle recomenda **20 a 30 casos por subgrupo**. Também recomenda usar clustering só quando se espera separação grande entre os grupos e, se os grupos se sobrepõem, preferir c-means ou modelos de mistura ([Dalmaijer et al.](https://arxiv.org/abs/2003.00381v3)). Um piloto com poucas dezenas de voltas válidas, dividido em três grupos, fica abaixo desse patamar. Além disso, as voltas não são independentes, porque há aprendizagem entre as sessões. Todos os grupos melhoraram de uma sessão para outra, tanto em van Leeuwen et al. quanto em Remonda et al. ([van Leeuwen et al. 2017](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0186871)). O resultado previsível é um agrupamento que separa sessões iniciais de sessões finais e voltas com erro grande das demais. Nada disso merece o nome de tipo de habilidade.

Trocar a unidade de análise por passagens em cada curva multiplica o número de casos. Isso pode revelar "modos de execução" de uma técnica, como frenagem tardia com trail braking, frenagem antecipada sem trail braking ou erro. Mas continuam sendo medidas repetidas de um único piloto, que precisam ser validadas por reamostragem (bootstrap) e conferidas contra a variável sessão.

Agrupar o piloto contra dados externos de corridas reais, como F1, GT3 ou IndyCar, tem um problema a mais:

- os dados públicos têm canais e resoluções diferentes dos do projeto;
- o estudo de F1 que encontrou quatro grupos trabalhou com médias por volta e precisou de diferenças entre companheiros de equipe para tentar cancelar o efeito do carro ([Taylor & Secco 2026](https://hira.hope.ac.uk/id/eprint/4949/));
- o catálogo da seção anterior mostra que o rótulo de estilo muda com carro, pneu e regulamento.

Um iniciante num Fórmula 3 do Assetto Corsa em Interlagos não é comparável, em pedais e volante, a um piloto de F1 em outra pista e com outro carro.

| Abordagem | Pergunta que responde | Prós | Contras | Papel no Modelo 2 |
|---|---|---|---|---|
| Clustering de voltas (k-means) | Quais voltas se parecem? | Simples; bom para exploração | Redescobre rápido–lento e sessão; exige 20–30 voltas por grupo; grupos sem significado | Não usar como resultado |
| Clustering de passagens por curva (modelo de mistura gaussiana ou c-means) | Que modos de execução existem nesta curva? | Mais casos; dá a incerteza de pertença a cada grupo | Medidas repetidas; confusão com a sessão; grupos instáveis | Só exploratório, validado por reamostragem |
| Detectores por regras físicas | O piloto aplica a técnica X? Que erro ocorreu? | Transparente; funciona com um só piloto; explicável no rádio | Limiares calibrados à mão e específicos de carro e pista | Núcleo da detecção |
| Comparação com referência (diferença de tempo; distâncias entre distribuições por setor) | Onde e quanto o piloto difere de uma volta real? | Mede em tempo; respeita a regra do projeto | Depende da qualidade da referência; a IA não pilota como humano | Núcleo da localização |
| Modelo supervisionado com o tempo do segmento como alvo (regressão, efeitos mistos, XGBoost) | Que variáveis explicam o tempo nesta curva? | Alvo objetivo; mostra a importância de cada variável | Mostra correlação, não causa; poucos dados por curva | Confirmar quais detectores importam |
| Dimensões contínuas de estilo (escores-z, análise de componentes principais) | Como este piloto executa, em relação à referência? | Não força categorias; mostra a evolução | O estilo de um iniciante ainda é instável | Assinatura atual para a decisão de compatibilidade |
| Ratings e rastreamento de domínio (TrueSkill, Bayesian Knowledge Tracing) | Qual é o nível? A habilidade foi dominada? | Modelam incerteza e evolução | TrueSkill exige partidas entre muitos jogadores; o BKT só tem um relatório técnico com 18 participantes | Opcional: acompanhar o domínio de cada técnica |

O TrueSkill modela a habilidade como uma distribuição atualizada pelos resultados de partidas entre vários jogadores ([Herbrich et al. 2006](https://papers.nips.cc/paper_files/paper/2006/file/f44ee263952e65b3610b8ba51229d1f9-Paper.pdf)), e aqui não há partidas. O Bayesian Knowledge Tracing aplicado a habilidades motoras em realidade virtual tem apenas um relatório técnico com 18 participantes ([Kim et al. 2023](https://www2.eecs.berkeley.edu/Pubs/TechRpts/2023/EECS-2023-17.html)).

A recomendação, portanto, é **não clusterizar o tipo de habilidade como resultado principal**. Cada peça da arquitetura tem um papel:

- **A comparação com a referência** localiza a perda.
- **Os detectores por regras** dizem se a técnica foi aplicada. É o mesmo princípio do motor heurístico de Nunes et al., que compara contra uma referência de nível semelhante: início da frenagem, pico de freio, velocidade mínima, momento da rotação, amplitude do volante, suavidade do acelerador e sobreposição entre acelerador e volante ([Nunes et al. 2026](https://www.mdpi.com/1099-4300/28/9/960)).
- **Um modelo supervisionado leve**, com o tempo do segmento como alvo, confirma quais variáveis explicam o tempo naquele carro e naquela pista.
- **As dimensões contínuas** descrevem o estilo.
- **O nível de habilidade** deve seguir o precedente da FIA: ritmo médio das melhores voltas e dispersão, não a melhor volta isolada ([FIA Categorização 2025](https://api.fia.com/sites/default/files/driver_categorisation_regulations_2025_0.pdf)).

Bailey sustenta que, para acompanhar atletas individuais, desenhos de sujeito único são mais apropriados do que a estatística de grupo ([Bailey 2019](https://journal.hep.com.cn/josisae/EN/10.1007/s42978-019-00042-4)). O clustering continua útil como análise exploratória por curva. Também rende um bom capítulo de discussão na monografia, justamente por mostrar com dados próprios o que a literatura previu.

## A ciência do feedback manda corrigir pouco, entre as curvas e com foco externo

O princípio mais robusto é o **foco de atenção externo**: o aprendiz presta atenção no efeito do movimento, não no próprio corpo. A meta-análise de Chua et al. reuniu dois conjuntos de estudos:

- 73 estudos de desempenho, com 1.824 participantes, em que o foco externo superou o interno com **g = 0,26**;
- 40 estudos de aprendizagem, com 1.274 participantes, em que a vantagem foi de **g ≈ 0,58 na retenção e na transferência**.

Idade e nível de habilidade não alteraram significativamente o efeito. Além disso, o foco externo distante superou o foco externo próximo, com g = 0,22 ([Chua et al. 2021](https://oasis.library.unlv.edu/kns_fac_articles/424/)). Na pilotagem, os três tipos de instrução ficam assim:

- **Foco interno:** "pressione o pedal mais rápido" ou "relaxe as mãos".
- **Foco externo próximo:** o volante.
- **Foco externo distante:** "frear na placa de 100 m", "carro na zebra externa na saída" ou "fim do freio na altura da zebra interna".

A frase do rádio deve usar sempre o último tipo.

O segundo princípio é que **ajudar demais pode atrapalhar a aprendizagem**. A hipótese da orientação, de Salmoni, Schmidt e Walter (1984), prevê que o aprendiz passe a depender da informação externa ([van Leeuwen, tese TU Delft](https://repository.tudelft.nl/file/File_9cfdd806-5311-40a7-8942-e79a08bd5bc7)). Anderson et al. descrevem três mecanismos para isso:

- dependência da informação sobre o resultado;
- excesso de correções de curto prazo;
- abandono da percepção própria do movimento.

Num experimento com 56 universitários, atrasar o retorno em duas tentativas piorou a precisão durante a prática, mas **reduziu a queda no teste de retenção**. Esse grupo também passou a usar mais fontes próprias de informação ([Anderson et al. 2005](https://pmc.ncbi.nlm.nih.gov/articles/PMC1780106)). Os autores citam ainda Winstein e Schmidt (1990), em que o retorno após todas as tentativas levou a uma retenção pior do que o retorno menos frequente. Schmidt e Shapiro resumem o tema central: condições que melhoram a prática muitas vezes não produzem a melhor retenção. Eles registram, porém, que esses efeitos nem sempre se repetiram em outros experimentos ([Schmidt & Shapiro 1988](https://apps.dtic.mil/sti/pdfs/ADA191559.pdf)). O mecanismo do excesso de correções tem consequência direta para o projeto. Corrigir o piloto a cada volta por uma variação que é só ruído ensina o piloto a perseguir ruído.

O terceiro princípio modula o segundo: **quanto ajudar depende do aprendiz**. Num simulador de direção, uma orientação pelo tato, adaptativa e retirada aos poucos, melhorou a retenção em jovens. Ela beneficiou mais os participantes com menor habilidade inicial. Os autores concluíram que a hipótese da orientação precisa ser ajustada conforme a tarefa, a forma de orientação e o aprendiz ([Marchal-Crespo et al. 2010](https://link.springer.com/article/10.1007/s00221-009-2026-8)). Existe também o feedback em faixa (bandwidth), que só avisa quando o desempenho sai de uma faixa-alvo. De Groot et al. o usaram em manutenção de faixa na direção, e os avisos dados fora do alvo distraíram menos e criaram menos dependência ([Wijewickrema et al.](https://arxiv.org/pdf/1705.04683)). Para um iniciante, isso justifica mais orientação nas primeiras sessões e a retirada dessa orientação à medida que cada técnica entra na faixa.

O quarto princípio trata do momento e do canal. A revisão de feedback em simuladores aponta três achados ([Wijewickrema et al.](https://arxiv.org/pdf/1705.04683)):

- o retorno dado no meio da tarefa aumenta a carga mental e pode piorar o desempenho;
- o retorno dado ao fim da tarefa, com algum atraso, é eficaz em tarefas complexas e em tempo real;
- especialistas precisam de pouco retorno, enquanto iniciantes se beneficiam de orientação passo a passo.

O único estudo randomizado de coaching de pilotagem em simulador encontrado é um preprint com 41 novatos e cerca de 8 minutos de instrução. Nele:

- o grupo que recebeu "o quê" e "por quê" só por áudio não melhorou significativamente a distância à linha ideal; os autores atribuem isso à imprecisão de indicações espaciais dadas por som e à sobrecarga de informação;
- o grupo que recebeu "o quê" pela tela e "por quê" por áudio melhorou a posição na pista sem perder velocidade;
- o ganho geral de tempo de volta não pôde ser separado do simples efeito da prática.

([Kaufman et al. 2024](https://arxiv.org/html/2401.04206v2))

Os produtos e treinadores convergiram para a mesma prática:

- uma ou duas mensagens por volta na Trophi ([Trophi](https://www.trophi.ai/sim-racing-coaching));
- falas antes e depois das curvas no Garmin ([Garmin](https://garmin.com/en-US/newsroom/?p=811));
- uma ou duas curvas a cada saída para a pista no Delta ([Coach Dave](https://coachdaveacademy.com/documentation/how-to-use-auto-insights-ai-coaching-in-delta/));
- dois focos por sessão com Bentley ([Bentley 2020](https://speedsecrets.com/wp-content/uploads/2020/01/COACHING-WITH-DATA.pdf)) e na Blayze;
- dois ou três pontos na HP Academy ([HP Academy](https://www.hpacademy.com/courses/professional-motorsport-data-analysis/aim-dash-logger-vw-tcr-step-4-analyse-driver));
- a regra de Ken Hill de anotar três coisas bem feitas, duas a melhorar e um único foco ([Blayze](https://blayze.io/blog/car-racing/what-to-work-on-next-for-on-track-improvement)).

Para o rádio do projeto, a evidência vira regras concretas, com uma ressalva: nenhuma delas foi testada com retenção em sim racing.

- **Durante a volta**, o rádio informa "o quê" e "onde": um único item, sobre uma única curva, com foco externo distante. A fala vai na reta anterior à curva-alvo, para que a próxima passagem possa mudar o resultado.
- **Depois da sessão**, o relatório traz o "por quê" e o "como", com os traços e um exercício.
- **A análise a cada três voltas válidas** funciona como um retorno resumido e evita corrigir ruído.
- **A eficácia só se prova com um teste de retenção**: uma sessão sem rádio, depois de um intervalo. Melhorar com o rádio ligado é desempenho durante a prática, não aprendizagem ([Anderson et al. 2005](https://pmc.ncbi.nlm.nih.gov/articles/PMC1780106); [Schmidt & Shapiro 1988](https://apps.dtic.mil/sti/pdfs/ADA191559.pdf)).

## Desenho do Modelo 2: do microssetor que perdeu tempo à frase no rádio

O projeto já tem as peças de base:

- a perda por microssetor contra uma volta de referência;
- o relatório de evolução por curva (frenagem, ápice, velocidade mínima, diferença consistente);
- o rádio com até três frases por volta, só nas retas;
- a análise a cada três voltas válidas.

O Modelo 2 acrescenta três camadas entre a medição e a fala: a cadeia causal, os detectores de técnica e a compatibilidade com o estilo. A tabela resume o fluxo, e as subseções detalham cada etapa.

| Etapa | Pergunta | Método | Saída |
|---|---|---|---|
| 0. Preparação | As voltas são comparáveis? | Filtros de validade, autoria, equipamento, estado dos pneus e chuva; validação dos canais | Conjunto de voltas válidas e de referências |
| 1. Localização | Onde o tempo foi perdido? | Diferença de tempo na grade de 2 m somada por fase da curva; repetição nas últimas 3 voltas; peso pela reta seguinte | Ranking de (curva, fase) com a perda medida |
| 2. Causa | Que fase originou a perda? | Cadeia entrada → meio → saída; teste do falso ganho da frenagem tardia | Fase de origem |
| 3. Técnica | O piloto aplica a técnica dessa fase? | Detectores por regras calibrados nas referências; estado aplica, não aplica ou não conclusivo; domínio por janela de passagens | Técnica-alvo e o seu estado |
| 4. Estilo | Como o piloto executa? | Escores-z nas dimensões contínuas, por tipo de curva | Assinatura atual, com incerteza |
| 5. Compatibilidade | A técnica faz sentido para ele? | Regras: aparece numa volta real, o nível permite, o passo combina com a assinatura, não é problema de acerto | Recomendação ou silêncio |
| 6. Comunicação | O que dizer e quando? | Uma correção, foco externo, diferença medida, confirmação, retirada | Frases do rádio e relatório depois da sessão |
| 7. Avaliação | O piloto aprendeu? | Desenho de sujeito único com linha de base, intervenção e retenção | Evidência para a monografia |

### Preparar os dados para que a comparação seja justa

Antes de comparar, o Modelo 2 precisa garantir que cada volta seja do piloto e possa ser comparada com as outras. Isso exige:

- marcar a autoria de cada volta, porque voltas pilotadas pela IA do jogo não podem entrar como voltas do piloto;
- separar os dados anteriores a 01/10/2026, quando o equipamento mudou para o volante RS50 e os pedais load cell;
- excluir voltas de saída do box, saídas de pista e voltas inválidas;
- controlar o estado térmico dos pneus nas primeiras voltas;
- excluir voltas na chuva.

As saídas de pista devem ser classificadas pela velocidade de guinada. No estudo de van Leeuwen et al., não pilotos saíram da pista com guinada média de 272 °/s, contra 124 °/s dos pilotos de corrida. Esse número ajuda a distinguir perda de controle de erro de trajetória ([van Leeuwen et al. 2017](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0186871)). A validação dos canais vem antes de qualquer detector: desvio do volante em linha reta, sinais em curvas à esquerda e à direita, natureza do canal de escorregamento e presença de ABS.

### Localizar a perda e subir a cadeia causal

A etapa 1 reaproveita o coach atual, mas muda a unidade de análise. Em vez de só microssetores, ela soma a perda por fase de curva: frenagem, entrada, meio, saída e reta seguinte. A segmentação pode usar a curvatura da linha de referência ou as regras de pedal e volante do sistema especialista ([CEUR-WS](https://ceur-ws.org/Vol-2260/51_454-458.pdf)). O ranking segue três regras:

- **Exigir repetição.** A perda deve aparecer em pelo menos duas das últimas três voltas válidas. Isso é coerente com a prática de Bentley de comparar a melhor volta com as três ou quatro seguintes ([Bentley 2020](https://speedsecrets.com/wp-content/uploads/2020/01/COACHING-WITH-DATA.pdf)).
- **Ponderar pela importância da curva**, medida pelo comprimento da reta seguinte ([CEUR-WS](https://ceur-ws.org/Vol-2260/51_454-458.pdf); [Driver61](https://driver61.com/uni/prioritising-corners/)).
- **Consistência primeiro.** Se a dispersão do tempo de volta ou do ponto de frenagem estiver alta, o tema da vez é consistência, não velocidade, como mandam Clough e a Blayze ([Winding Road](https://windingroad.com/articles/features/speed-secrets-consistency/); [Blayze](https://blayze.io/blog/car-racing/what-to-work-on-next-for-on-track-improvement)).

A etapa 2 volta pela cadeia causal. Uma perda na saída, com retomada tardia e velocidade mínima baixa, tem origem na entrada. Corrigir o acelerador antes da frenagem repete o erro descrito pela Racers360 ([Mazda/Racers360](https://www.mazdamotorsports.com/2020/02/25/driving-tip-1-the-top-mistakes-grassroots-race-car-drivers-make/)). A Track Titan usa a mesma ideia de procurar a causa antes do sintoma ([Track Titan](https://www.tracktitan.io/post/november-2025-update-coaching-flows)). Um ganho com frenagem tardia seguido de uma perda maior na entrada é classificado como falso ganho, não como melhora ([HP Academy](https://www.hpacademy.com/courses/data-analysis-fundamentals/the-data-analysis-tool-box-variance-channel/)).

### Detectar se o piloto aplica cada técnica

Cada técnica do catálogo vira um detector com três estados: aplica, não aplica e não conclusivo. O detector é calculado a cada passagem pela curva e calibrado pela distribuição das voltas de referência na mesma curva. A calibração é necessária porque os limiares de Nunes et al. foram ajustados à mão e valem só para o carro e a pista daquele estudo ([Nunes et al. 2026](https://www.mdpi.com/1099-4300/28/9/960)). O estado "não conclusivo" é obrigatório em três situações:

- a diferença está dentro da dispersão do próprio piloto;
- a volta da IA e a melhor volta do piloto discordam;
- o canal não é confiável naquele trecho.

O domínio de cada técnica é acompanhado por uma janela de passagens recentes. Por exemplo, a técnica conta como dominada se foi aplicada em pelo menos quatro das últimas seis passagens. Essa é uma versão simples e transparente do rastreamento de domínio citado na seção anterior. A tabela mostra os detectores prioritários para um iniciante, na ordem da progressão.

| Ordem | Técnica | Detector principal | Considera aplicada quando |
|---|---|---|---|
| 1 | Consistência | Desvio-padrão de s_b, v_min e s_pu; desvio-padrão do tempo de volta | Dentro de uma faixa definida pela própria evolução do piloto (meta indicativa de 0,3–0,5 s na volta) |
| 2 | Referência de frenagem | Δs_b contra a referência | Δs_b dentro da dispersão da referência |
| 3 | Frenagem no limiar | Tempo até o pico; pico relativo | Tempo até o pico e pico próximos aos da referência na curva |
| 4 | Soltura progressiva | Mínimo de d(freio)/dt no fim da soltura; queda da carga dianteira | Nenhum degrau na soltura |
| 5 | Trail braking | Fração de freio retida na entrada; sobreposição com o volante; coordenação | Freio acima de ε depois de s_ti, diminuindo enquanto o volante aumenta |
| 6 | Retomada do acelerador | s_pu − s_vmin; volante abrindo; reversões do acelerador | Retomada depois de v_min, sem aumento do volante e sem alívio |
| 7 | Uso da pista e ápice | e(s) na saída; posição do ápice | O carro chega à borda na saída sem precisar aliviar |
| 8 | Rotação e equilíbrio | Ângulo de subesterço; β; contraesterço | Sem subesterço persistente nem correções repetidas |
| 9 | Sobreposição de pedais e pé esquerdo | Cruzamento de pedais fora das reduções de marcha | Só é sugerida se a referência mostra a técnica e o tempo melhora |

Para a monografia, uma amostra de passagens rotuladas à mão, pelo próprio piloto revendo vídeo e traços, permite medir a precisão e a revocação de cada detector. Nenhum produto comercial publica esses números ([SimRacingManual](https://simracingmanual.com/resources/ai-driving-coaches/)).

### Catalogar a assinatura de estilo e decidir se a técnica combina

A assinatura de estilo é um vetor de escores-z nas dimensões da seção sobre estilo:

- forma V ou U;
- perfil de frenagem;
- uso binário ou sobreposto dos pedais;
- resposta do carro na entrada;
- aplicação do volante;
- perfil do acelerador;
- consistência.

O vetor é calculado por tipo de curva (lenta, média ou rápida). Como ponto de partida, valem os limiares de Krause e Bentley: cerca de 105 km/h, ou 120 km/h em carros com downforce ([Speed Secrets, Data for Drivers](https://speedsecrets.com/wp-content/uploads/2018/01/Data-for-Drivers-PRINT-Full.pdf)). A comparação é feita contra as voltas de referência e contra o histórico do próprio piloto. Para um iniciante, esse vetor deve se chamar **assinatura atual**. Remonda et al. mostram que, nas primeiras sessões, a maior parte da variação vem da aprendizagem ([Remonda et al. 2021](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0245320)). Por isso, a decisão de compatibilidade não pode tratar o vetor como um traço fixo.

A decisão de compatibilidade aplica regras explícitas:

1. **A técnica aparece numa volta real mais rápida.** Essa é a regra do projeto: a técnica só é sugerida se aparece numa volta real mais rápida naquela curva. A preferência é pela melhor volta do próprio piloto, que por construção já segue o estilo dele. A volta da IA entra para técnicas que o piloto nunca mostrou, com a ressalva de que a IA não pilota como humano.
2. **O nível do piloto permite.** Técnicas avançadas, como trail braking profundo e sobreposição de pedais, ficam bloqueadas até que consistência, referência de frenagem e soltura estejam dominadas. Essa ordem segue o kart, as escolas e a Blayze ([KartPulse](https://forums.kartpulse.com/t/when-and-how-to-introduce-braking/2086); [Blayze](https://blayze.io/blog/car-racing/blayze-motorsports-coaching-methodology)).
3. **O passo é compatível com a assinatura.** Se a técnica empurra o piloto contra a própria assinatura, sugere-se o menor passo possível e verifica-se o resultado. Um exemplo é um piloto que tende ao U numa curva que a referência faz em V. O caso Ricciardo serve de alerta ([The Race](https://the-race.com/formula-1/what-makes-peculiar-mclaren-so-hard-for-ricciardo-to-master/)). Nunca se sugere "frear mais tarde" isoladamente. A sugestão é sempre o par ponto de frenagem e soltura, movendo a referência um ou dois metros por volta ([Driver61](https://driver61.com/uni/prioritising-corners/)).
4. **O problema é do piloto, não do carro.** Um problema idêntico em todas as voltas, como o mesmo eixo travando sempre, é marcado como possível questão de repartição de frenagem ou de acerto, não como erro técnico ([Blayze](https://blayze.io/blog/car-racing/what-to-work-on-next-for-on-track-improvement); [Speed Secrets](https://speedsecrets.com/q-should-i-adjust-brake-bias-during-a-race-how-do-i-know-when-to-adjust-brake-bias/)).

Se nenhuma recomendação passa por todas as regras, a saída é o silêncio.

### Falar uma coisa, verificar e retirar a ajuda

Com até três frases por volta, a estrutura recomendada é:

1. **Onde e quanto**, medido contra uma volta real.
2. **O que a volta real fez**, com um marco externo.
3. **Confirmação do item anterior**, usada só quando há algo a confirmar.

Um exemplo, que mostra o formato e não valores reais:

- "Junção: mais 0,15 s em relação à sua melhor volta, nas últimas três passagens."
- "Na melhor volta, o freio terminou na altura da zebra interna."
- Numa volta posterior: "Junção, última passagem: diferença de 0,04 s."

O ciclo da correção tem quatro regras:

- a fala vai na reta anterior à curva-alvo, como na Trophi ([Trophi](https://www.trophi.ai/sim-racing-coaching));
- o item se mantém até entrar na faixa, ou até três tentativas sem mudança, e então o rádio passa ao próximo item;
- quando o item fica dentro da faixa por várias voltas, o rádio deixa de falar dele, aplicando o retorno em faixa e a retirada da ajuda ([Wijewickrema et al.](https://arxiv.org/pdf/1705.04683); [Marchal-Crespo et al. 2010](https://link.springer.com/article/10.1007/s00221-009-2026-8));
- o "por quê" e o "como" ficam no relatório depois da sessão: traços sobrepostos, a explicação da técnica e um exercício, como o marco de frenagem que avança ou uma variação do 3GNB.

A regra de nunca prometer ganho tem respaldo direto. A volta "ótima" de Hojaji et al. era uma previsão de modelo ([Hojaji et al. 2026](https://www.scitepress.org/Papers/2026/146096/146096.pdf)). O Garmin recusa a soma dos melhores setores porque ela gera voltas impossíveis de pilotar ([Garmin](https://garmin.com/en-US/newsroom/?p=811)). E os produtos que quantificam cada erro "até o milésimo" não publicam validação ([Track Titan](https://www.tracktitan.io/post/november-2025-update-coaching-flows)).

### Avaliar com desenho de sujeito único

Com um único piloto, a evidência defensável vem de um desenho de sujeito único ([Bailey 2019](https://journal.hep.com.cn/josisae/EN/10.1007/s42978-019-00042-4)). Há duas formas de montá-lo:

- **Por fases:** sessões de linha de base sem rádio, depois sessões com rádio e, por fim, uma sessão de retenção sem rádio, depois de pelo menos um dia.
- **Por curvas:** uma curva-alvo recebe correção e uma curva de controle não recebe.

A alternância por curvas separa o efeito do coaching do efeito da simples prática. Esse efeito contaminou o ganho geral de Kaufman et al. e não foi estimado por Nunes et al., como eles mesmos declaram ([Kaufman et al. 2024](https://arxiv.org/html/2401.04206v2); [Nunes et al. 2026](https://www.mdpi.com/1099-4300/28/9/960)). As medidas são três: o tempo na fase-alvo, o estado do detector da técnica e a dispersão. Um questionário NASA-TLX, usado por Remonda et al. e por Kaufman et al., mede a carga mental que o rádio impõe ([Remonda et al. 2021](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0245320)).

## Conclusão

A pesquisa muda a pergunta do Modelo 2. A pergunta deixa de ser "em que grupo de habilidade está este piloto". A pergunta útil passa a ser: que técnica, em que curva, uma volta real mais rápida já mostra e as outras voltas do piloto não mostram, e quanto essa diferença custou. A melhor volta do próprio piloto é a referência mais compatível com o estilo dele, porque foi ele quem a pilotou. A volta da IA serve para técnicas que ele ainda não executou, sempre limitada pela progressão por nível. Assim, a compatibilidade entre técnica e estilo, que parecia exigir uma classificação de estilos montada com dados externos, vira uma comparação com dados que o projeto já tem, e a regra de falar só diferença medida se mantém.

A segunda implicação é metodológica. Nenhuma ferramenta comercial publica regras de detecção, limiares, validação ou teste de retenção, e a literatura acadêmica de sim racing tem amostras pequenas e nenhum ensaio com retenção. Um TCC pode cobrir exatamente o que falta ao mercado e à literatura se fizer quatro coisas:

- definir detectores transparentes;
- validá-los contra passagens rotuladas à mão;
- tratar o rádio como um experimento: hipótese, uma correção, verificação na passagem seguinte e retirada;
- medir a retenção sem rádio.

Isso pode ser feito com um único piloto, porque o desenho de sujeito único é o adequado para esse caso. Já o clustering, rebaixado a análise exploratória, deixa de ser um risco e vira um resultado: mostrar com dados próprios que os grupos acompanham o cronômetro e a sessão confirma a escolha da arquitetura.
