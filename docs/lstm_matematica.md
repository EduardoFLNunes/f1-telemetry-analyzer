# Formulação matemática das redes LSTM

Descrição formal das duas redes de [`backend/ml/models/`](../backend/ml/models/),
exatamente como estão implementadas. As equações desta página foram
reimplementadas em NumPy e comparadas com a passagem à frente do PyTorch sobre
os pesos treinados: a diferença máxima é de $4{,}3 \times 10^{-7}$, que é a
precisão do `float32`. A contagem de parâmetros derivada abaixo também confere
com o modelo salvo, elemento a elemento.

---

## 1. Notação

| símbolo | significado | valor |
|---|---|---|
| $s$ | distância percorrida na pista, em metros | $0 \le s < L$ |
| $L$ | comprimento da pista | $4334{,}08$ m |
| $N$ | pontos da grade espacial | $2167$ |
| $\Delta s$ | passo da grade | $2{,}00$ m |
| $T$ | comprimento da janela de treino, em passos | $128$ ($256$ m) |
| $d$ | dimensão da entrada | $12$ (geradora), $15$ (substituta) |
| $q$ | dimensão da saída | $4$ (geradora), $1$ (substituta) |
| $H$ | unidades ocultas por direção | $96$ |
| $\Lambda$ | camadas LSTM empilhadas | $2$ |
| $p$ | probabilidade de dropout | $0{,}15$ |
| $\odot$ | produto de Hadamard (elemento a elemento) | |
| $\sigma(\cdot)$ | função logística, $\sigma(z) = (1+e^{-z})^{-1}$ | |

O índice temporal das equações é **espacial**: $t$ percorre pontos da grade da
pista, não instantes. É a consequência direta do alinhamento por distância — o
que a rede vê como sequência é o percurso, não o relógio.

---

## 2. As duas tarefas

Ambas as redes são funções que mapeiam uma sequência em outra do mesmo
comprimento,

$$
f_\theta : \mathbb{R}^{T \times d} \longrightarrow \mathbb{R}^{T \times q},
$$

e diferem no que ocupa a entrada e a saída.

### 2.1 Rede geradora

$$
\underbrace{\big(\mathbf{k}_t,\ \boldsymbol{\ell}_t,\ \mathbf{c}_t\big)}_{d\,=\,12}
\;\longmapsto\;
\underbrace{\big(L_t,\ v_t,\ b_t,\ a_t\big)}_{q\,=\,4}
$$

com

- $\mathbf{k}_t \in \mathbb{R}^7$ — descritores da pista no ponto $t$: curvatura
  $\kappa$, seu módulo $|\kappa|$, sua taxa $\mathrm{d}\kappa/\mathrm{d}s$,
  largura $w$, inclinação de elevação, indicador de curva e distância até o
  ápice seguinte;
- $\boldsymbol{\ell}_t \in \mathbb{R}^2$ — **condicionamento por desempenho**:
  a perda da volta para a melhor do piloto no microsetor que contém $t$, e a
  perda da volta inteira;
- $\mathbf{c}_t \in \mathbb{R}^3$ — contexto: combustível, desgaste de pneu e
  índice de aderência;
- a saída é a pilotagem: deslocamento lateral $L$, velocidade $v$, freio $b$ e
  acelerador $a$.

A pilotagem **não entra**. Se entrasse, prever $v_t$ a partir de $v_t$ seria
copiar. O que a rede aprende é a distribuição condicional

$$
p\big(\text{pilotagem} \mid \text{pista},\ \text{perda},\ \text{contexto}\big),
$$

e a trajetória de referência é essa distribuição avaliada em perda nula:
$\boldsymbol{\ell}_t = \mathbf{0}$. Sem o termo $\boldsymbol{\ell}$, a única
forma de a rede minimizar o erro sobre todas as voltas ao mesmo tempo seria
responder $\mathbb{E}[\text{pilotagem} \mid \text{pista}]$ — a média — que é
precisamente o que se quer evitar.

### 2.2 Rede substituta

$$
\underbrace{\big(\mathbf{k}_t,\ \mathbf{m}_t,\ \mathbf{c}_t\big)}_{d\,=\,15}
\;\longmapsto\;
\underbrace{\Delta t_t}_{q\,=\,1}
$$

onde $\mathbf{m}_t \in \mathbb{R}^5$ descreve a **forma** da trajetória —
$L$, $\mathrm{d}L/\mathrm{d}s$, curvatura da linha percorrida e distância até
cada borda — e $\Delta t_t$ é o tempo gasto no passo $t$.

A velocidade não entra, e por outra razão: como $\Delta t = \Delta \ell / v$,
uma rede que recebe $v$ resolve a tarefa por aritmética e não aprende nada sobre
traçado. Recebendo apenas a forma, ela aprende quanto *este piloto neste carro*
faz por aqui passando por ali. O tempo de volta estimado é

$$
\hat{T} = \sum_{t=1}^{N} \Delta t_t ,
$$

que é o termo com que a rede entra na função de aptidão do algoritmo evolutivo.

---

## 3. Normalização

### 3.1 Entrada

Cada canal $j$ é padronizado com a média e o desvio calculados **apenas nas
janelas de treino**:

$$
\tilde{x}_{t,j} = \frac{x_{t,j} - \mu_j}{\varsigma_j},
\qquad
\varsigma_j = \max\big(\hat{\sigma}_j,\ 10^{-6}\big).
$$

O piso em $\varsigma_j$ trata canais constantes: dentro de uma sessão o desgaste
de pneu praticamente não varia, e dividir por zero produziria $\infty$. Com o
piso, o canal vira a diferença para a média, que é o comportamento correto — um
canal sem variação não carrega informação a escalar.

Ajustar $\mu$ e $\hat\sigma$ sobre o conjunto completo vazaria a distribuição do
teste para dentro do treino. É um vazamento pequeno e gratuito de evitar.

### 3.2 Saída

Cada canal de saída recebe um de três tratamentos, conforme sua natureza:

$$
\phi_j(y) =
\begin{cases}
y, & \text{se } j \in \mathcal{U} \quad (\text{unitário}) \\[4pt]
\dfrac{\log\max(y,\,10^{-6}) - \mu^{\log}_j}{\varsigma^{\log}_j}, & \text{se } j \in \mathcal{L} \quad (\text{logarítmico}) \\[8pt]
\dfrac{y - \mu_j}{\varsigma_j}, & \text{caso contrário} \quad (\text{padrão})
\end{cases}
$$

com $\mathcal{U} = \{\texttt{brake}, \texttt{throttle}\}$ e
$\mathcal{L} = \{\texttt{step\_time\_s}\}$. A previsão em unidades físicas é
$\phi_j^{-1}$.

As três existem por motivos distintos:

- **unitário** — $b$ e $a$ já vivem em $[0,1]$ e a arquitetura garante esse
  intervalo na saída (§6); transformá-los seria desfazer essa garantia;
- **logarítmico** — $\Delta t$ vai de $\sim\!0{,}025$ s numa reta a
  $\sim\!0{,}09$ s numa curva lenta. Em log, errar 10% custa o mesmo nos dois
  casos; em escala linear a perda enxergaria apenas as curvas;
- **padrão** — sem normalizar, uma perda quadrática somaria metros de
  deslocamento lateral com quilômetros por hora, e o canal de maior variância
  treinaria sozinho.

---

## 4. A célula LSTM

Para uma direção de uma camada, com entrada $\mathbf{x}_t \in \mathbb{R}^{d_\text{in}}$,
estado oculto $\mathbf{h}_t \in \mathbb{R}^H$ e estado de célula
$\mathbf{c}_t \in \mathbb{R}^H$:

$$
\begin{aligned}
\mathbf{i}_t &= \sigma\big(W_{ii}\mathbf{x}_t + \mathbf{b}_{ii} + W_{hi}\mathbf{h}_{t-1} + \mathbf{b}_{hi}\big) && \text{(porta de entrada)}\\
\mathbf{f}_t &= \sigma\big(W_{if}\mathbf{x}_t + \mathbf{b}_{if} + W_{hf}\mathbf{h}_{t-1} + \mathbf{b}_{hf}\big) && \text{(porta de esquecimento)}\\
\mathbf{g}_t &= \tanh\big(W_{ig}\mathbf{x}_t + \mathbf{b}_{ig} + W_{hg}\mathbf{h}_{t-1} + \mathbf{b}_{hg}\big) && \text{(candidato a célula)}\\
\mathbf{o}_t &= \sigma\big(W_{io}\mathbf{x}_t + \mathbf{b}_{io} + W_{ho}\mathbf{h}_{t-1} + \mathbf{b}_{ho}\big) && \text{(porta de saída)}\\[4pt]
\mathbf{c}_t &= \mathbf{f}_t \odot \mathbf{c}_{t-1} + \mathbf{i}_t \odot \mathbf{g}_t && \text{(estado de célula)}\\
\mathbf{h}_t &= \mathbf{o}_t \odot \tanh(\mathbf{c}_t) && \text{(estado oculto)}
\end{aligned}
$$

com $\mathbf{h}_0 = \mathbf{c}_0 = \mathbf{0}$.

Duas convenções da implementação (PyTorch) que a formulação precisa respeitar,
sob pena de os pesos salvos não fazerem sentido:

1. **Dois vetores de viés.** $\mathbf{b}_{i\bullet}$ e $\mathbf{b}_{h\bullet}$
   são parâmetros separados, e não um só. São matematicamente redundantes — a
   soma dos dois seria suficiente — mas é assim que estão armazenados.
2. **Portas empilhadas numa matriz.** Os pesos vêm como
   $W_{ih} = [\,W_{ii};\,W_{if};\,W_{ig};\,W_{io}\,] \in \mathbb{R}^{4H \times d_\text{in}}$,
   nesta ordem. Ler as fatias fora de ordem troca a porta de esquecimento pelo
   candidato, o que não gera erro nenhum e produz uma rede que não é a treinada.

O termo que dá o nome à arquitetura é $\mathbf{c}_t = \mathbf{f}_t \odot \mathbf{c}_{t-1} + \dots$:
com $\mathbf{f}_t \approx \mathbf{1}$, a derivada de $\mathbf{c}_t$ em relação a
$\mathbf{c}_{t-1}$ é próxima da identidade, e o gradiente atravessa muitos
passos sem desaparecer. Aqui esses passos são metros de pista — é o que permite
a rede relacionar a frenagem a uma curva que ainda está 200 m à frente.

---

## 5. Bidirecionalidade e empilhamento

Cada camada roda duas vezes sobre a mesma sequência, com parâmetros
independentes:

$$
\overrightarrow{\mathbf{h}}_t = \text{LSTM}^{\rightarrow}\big(\mathbf{x}_t, \overrightarrow{\mathbf{h}}_{t-1}\big),
\qquad
\overleftarrow{\mathbf{h}}_t = \text{LSTM}^{\leftarrow}\big(\mathbf{x}_t, \overleftarrow{\mathbf{h}}_{t+1}\big),
$$

e a saída da camada é a concatenação

$$
\mathbf{h}_t = \big[\;\overrightarrow{\mathbf{h}}_t \;;\; \overleftarrow{\mathbf{h}}_t\;\big] \in \mathbb{R}^{2H}.
$$

**Por que bidirecional.** O traçado ideal num ponto depende do que vem *depois*
dele: onde frear é função da curva que ainda não chegou. Uma rede causal não tem
essa informação e produz uma referência que freia tarde de forma sistemática.
Isso só é admissível porque a inferência é feita sobre uma volta inteira já
conhecida, e não em tempo real — se o sistema fosse rodar durante a volta, esta
seria a primeira escolha a cair.

O empilhamento passa a saída de uma camada como entrada da seguinte,

$$
\mathbf{x}^{(\lambda+1)}_t = \mathcal{D}_p\big(\mathbf{h}^{(\lambda)}_t\big),
\qquad \lambda = 1,\dots,\Lambda-1,
$$

onde $\mathcal{D}_p$ é dropout com probabilidade $p = 0{,}15$, aplicado **entre**
camadas e **apenas em treino**; na inferência $\mathcal{D}_p$ é a identidade.
Não há dropout depois da última camada — ali ele seria ruído somado ao próprio
alvo.

Assim $d^{(1)}_\text{in} = d$ e $d^{(\lambda)}_\text{in} = 2H$ para
$\lambda \ge 2$.

---

## 6. Cabeça de saída e ativações por canal

A projeção final é afim, aplicada em cada passo:

$$
\mathbf{z}_t = W_o\,\mathbf{h}^{(\Lambda)}_t + \mathbf{b}_o,
\qquad W_o \in \mathbb{R}^{q \times 2H},
$$

seguida de uma ativação escolhida por canal através de uma máscara fixa
$\mathbf{u} \in \{0,1\}^q$, com $u_j = 1$ se o canal $j$ é unitário:

$$
\hat{y}_{t,j} = (1-u_j)\,z_{t,j} + u_j\,\sigma(z_{t,j}).
$$

Ou seja, $b$ e $a$ saem por sigmoide e portanto em $(0,1)$ por construção; $L$,
$v$ e $\Delta t$ saem lineares, no espaço normalizado de §3.2. Pôr o limite na
arquitetura em vez de esperar que a perda o descubra é o que impede a rede de
prever freio $-0{,}2$ ou acelerador $1{,}3$.

Uma variante que **não** deu certo, e que vale registrar: forçar positividade em
$v$ com `softplus`. A função começa em $\log 2 \approx 0{,}69$, e a rede gastava
épocas apenas para alcançar a ordem de grandeza de uma velocidade em km/h. Quem
cuida da escala é a normalização, não a ativação.

---

## 7. Contagem de parâmetros

Uma direção de uma camada tem $4H(d_\text{in} + H)$ pesos e $8H$ vieses (dois
vetores de $4H$). Com $\Lambda$ camadas bidirecionais e cabeça linear:

$$
|\theta| =
\underbrace{2\big[4H(d + H) + 8H\big]}_{\text{camada 1, duas direções}}
+ \underbrace{2(\Lambda-1)\big[4H(3H) + 8H\big]}_{\text{camadas seguintes}}
+ \underbrace{2Hq + q}_{\text{cabeça}}
$$

onde o $3H$ vem de $d_\text{in} + H = 2H + H$ nas camadas a partir da segunda.

Com $H = 96$, $\Lambda = 2$:

| rede | $d$ | $q$ | camada 1 | camada 2 | cabeça | **total** |
|---|---|---|---|---|---|---|
| geradora | 12 | 4 | 84 480 | 222 720 | 772 | **307 972** |
| substituta | 15 | 1 | 86 784 | 222 720 | 193 | **309 697** |

Ambos conferem exatamente com os tensores salvos em `weights.pt`.

Note que a segunda camada tem **2,6 vezes** mais parâmetros que a primeira, e
pela mesma razão nas duas redes: ela recebe $2H = 192$ entradas contra $d \le 15$
da primeira. A capacidade do modelo está quase toda no empilhamento, não na
largura da entrada.

---

## 8. Função de perda

Erro de Huber (`SmoothL1`) com $\beta = 0{,}5$, no espaço normalizado, mediado
sobre passos, canais e janelas do lote:

$$
\mathcal{L}(\theta) = \frac{1}{|\mathcal{B}|\,T\,q}
\sum_{n \in \mathcal{B}} \sum_{t=1}^{T} \sum_{j=1}^{q} \rho_\beta\big(\hat{y}^{(n)}_{t,j} - \phi_j(y^{(n)}_{t,j})\big),
$$

$$
\rho_\beta(e) =
\begin{cases}
\dfrac{e^2}{2\beta}, & |e| < \beta \\[8pt]
|e| - \dfrac{\beta}{2}, & |e| \ge \beta
\end{cases}
$$

**Por que Huber e não erro quadrático.** A telemetria tem trechos com buraco de
amostragem que a interpolação alisa. Sob erro quadrático, o gradiente cresce
linearmente com o resíduo e esses pontos dominam o treino. $\rho_\beta$ é
quadrática perto do acerto — onde essa curvatura ajuda a convergir — e linear
longe dele, que é o tratamento correto para um outlier. A função é $C^1$: as
duas peças coincidem em valor e derivada em $|e| = \beta$.

---

## 9. Otimização

**AdamW**, com decaimento de peso desacoplado. Para cada parâmetro:

$$
\begin{aligned}
\mathbf{m}_k &= \beta_1 \mathbf{m}_{k-1} + (1-\beta_1)\,\mathbf{g}_k, &
\hat{\mathbf{m}}_k &= \frac{\mathbf{m}_k}{1-\beta_1^{\,k}} \\
\mathbf{v}_k &= \beta_2 \mathbf{v}_{k-1} + (1-\beta_2)\,\mathbf{g}_k^{\odot 2}, &
\hat{\mathbf{v}}_k &= \frac{\mathbf{v}_k}{1-\beta_2^{\,k}} \\[4pt]
\theta_k &= \theta_{k-1} - \eta_k\left(\frac{\hat{\mathbf{m}}_k}{\sqrt{\hat{\mathbf{v}}_k} + \epsilon} + \lambda\,\theta_{k-1}\right)
\end{aligned}
$$

com $\beta_1 = 0{,}9$, $\beta_2 = 0{,}999$, $\epsilon = 10^{-8}$,
$\lambda = 10^{-4}$ e $\eta_0 = 2\times10^{-3}$.

O gradiente é o do lote **após recorte de norma**:

$$
\mathbf{g}_k \leftarrow \mathbf{g}_k \cdot \min\!\left(1,\ \frac{c}{\|\mathbf{g}_k\|_2}\right),
\qquad c = 1{,}0 ,
$$

recorte que é praticamente obrigatório em redes recorrentes: o produto de
jacobianas ao longo de $T = 128$ passos ocasionalmente explode, e sem o teto um
único lote destrói pesos que levaram dezenas de épocas para se formar.

**Agenda da taxa de aprendizado.** $\eta$ é dividido por 2 quando a perda de
validação não melhora por 3 épocas consecutivas. Nas execuções registradas, a
geradora usou $\{2, 1, 0{,}5\}\times10^{-3}$ e a substituta chegou a
$1{,}25\times10^{-4}$ — sinal de que ela precisou refinar bem mais que a outra.

**Parada.** O treino para após 10 épocas sem melhora na validação, e o modelo
devolvido é o do melhor epoch, não o do último. Com 60 voltas de treino a rede
decora rápido: a geradora parou o melhor estado no epoch 38 de 40 e a substituta
no 27, interrompendo no 37.

---

## 10. Construção das janelas

O conjunto de treino não é a volta inteira, mas janelas de comprimento $T$
recortadas com passo $\tau = 16$ pontos ($32$ m). Para uma volta $\ell$, os
índices da $n$-ésima janela são

$$
\mathcal{I}_n = \big\{\, (n\tau + r) \bmod N \;:\; r = 0,\dots,T-1 \,\big\},
\qquad n = 0,\dots,\left\lceil \tfrac{N}{\tau} \right\rceil - 1 ,
$$

o que dá $\lceil 2167/16 \rceil = 136$ janelas por volta.

O módulo $N$ não é detalhe de implementação: ele faz as janelas **darem a volta
na pista**. Sem ele, o trecho que atravessa a linha de chegada — saída da última
curva e entrada da primeira — seria o único que nenhuma janela cobriria inteiro,
justamente onde o carro está mais rápido.

Uma janela é descartada se algum alvo dentro dela não for finito. Depois desse
filtro:

| tarefa | treino | validação | teste |
|---|---|---|---|
| geradora | 8160 | 5304 | 1904 |
| substituta | 7620 | 4953 | 1778 |

A divisão é **por sessão** (60 / 39 / 14 voltas), nunca por ponto nem por volta
solta: pontos da mesma volta distam 2 m e são quase idênticos, e voltas da mesma
sessão compartilham setup, pneu, combustível e temperatura de pista.

**Inferência usa a volta inteira.** A rede treinada em janelas de 128 passos é
avaliada sobre os $N = 2167$ pontos de uma vez. Isso é legítimo porque uma RNN
não tem comprimento fixo: os mesmos $\theta$ se aplicam a qualquer $T$. O que
muda é que o estado inicial $\mathbf{h}_0 = \mathbf{0}$ é pago uma vez em vez de
136 vezes, e a referência sai contínua em vez de costurada.

---

## 11. Métricas e resultados

Avaliação em **unidades físicas**, após $\phi^{-1}$ — a perda de treino vive no
espaço normalizado e não diz nada a ninguém. Para cada canal $j$:

$$
\text{MAE}_j = \frac{1}{M}\sum_{i=1}^{M} \big|\hat{y}_{i,j} - y_{i,j}\big|,
\qquad
\text{RMSE}_j = \sqrt{\frac{1}{M}\sum_{i=1}^{M} \big(\hat{y}_{i,j} - y_{i,j}\big)^2},
$$

$$
\text{skill}_j = 1 - \frac{\text{RMSE}_j}{\hat\sigma_j},
$$

onde $\hat\sigma_j$ é o desvio-padrão do alvo no conjunto avaliado. A perícia
compara o modelo com o preditor trivial "sempre a média": $\text{skill} = 1$ é
acerto perfeito, $\text{skill} = 0$ significa empatar com a média, e valores
negativos, perder para ela.

### Rede geradora

| canal | treino | validação | teste | perícia (teste) |
|---|---|---|---|---|
| posição lateral | 0,186 m | 0,558 m | 1,591 m | 0,11 |
| velocidade | 0,674 km/h | 1,929 km/h | 6,230 km/h | 0,79 |
| freio | 0,009 | 0,022 | 0,055 | 0,29 |
| acelerador | 0,023 | 0,041 | 0,094 | 0,44 |

### Rede substituta

| canal | treino | validação | teste | perícia (teste) |
|---|---|---|---|---|
| tempo por passo | 0,0006 s | 0,0014 s | 0,0022 s | 0,62 |

### O que os números dizem, incluindo o desconfortável

A degradação de treino para teste é grande e sistemática nas duas redes, e a
causa é conhecida: o teste são **sessões inteiras que a rede nunca viu**, com
outro setup, outra carga de combustível e outra condição de pista. É a medida
honesta de generalização; um corte por volta em vez de por sessão daria números
muito melhores e sem significado.

O caso a olhar com atenção é a **posição lateral no teste: perícia 0,11**. A
rede mal supera prever a posição média em sessões novas. A velocidade generaliza
bem (0,79), os pedais razoavelmente (0,29 e 0,44), mas a trajetória em si é o
alvo mais difícil — e é justamente o que a rede geradora existe para produzir.

Isso tem consequência prática, e ela já é tratada no sistema: a linha da rede é
usada como **semente** do algoritmo evolutivo, não como resposta. Projetada no
espaço de trajetórias do otimizador, ela simula em $90{,}3$ s contra $92{,}9$ s
de dirigir pelo meio da pista — melhor que o trivial, pior que a melhor volta
real. É contribuição útil para a busca, não um traçado pronto.

---

## 12. Verificação desta página

As equações das seções 4 a 7 foram reimplementadas em NumPy, a partir do texto
acima e não do código-fonte, e comparadas com a passagem à frente do PyTorch
sobre os pesos treinados, para uma entrada aleatória de 128 passos:

| rede | diferença máxima | parâmetros pela fórmula | parâmetros no arquivo |
|---|---|---|---|
| geradora | $4{,}3\times10^{-7}$ | 307 972 | 307 972 |
| substituta | $2{,}5\times10^{-7}$ | 309 697 | 309 697 |

A diferença é o arredondamento de `float32`. Se alguma equação aqui divergisse
da implementação — uma porta trocada de ordem, um viés esquecido, a
concatenação bidirecional na ordem errada — a comparação acusaria.

---

## Onde cada coisa vive no código

| seção | arquivo |
|---|---|
| 2 — as duas tarefas | [`models/sequences.py`](../backend/ml/models/sequences.py) |
| 3 — normalização | [`features/scaling.py`](../backend/ml/features/scaling.py) |
| 4 a 7 — arquitetura | [`models/lstm.py`](../backend/ml/models/lstm.py) |
| 8 e 9 — perda e otimização | [`models/training.py`](../backend/ml/models/training.py) |
| 10 — janelas e divisão | [`models/sequences.py`](../backend/ml/models/sequences.py) · [`preprocessing/splits.py`](../backend/ml/preprocessing/splits.py) |
| 11 — métricas | [`models/training.py`](../backend/ml/models/training.py) |

Os diagramas da arquitetura estão em
[`arquitetura_ml.md`](arquitetura_ml.md); os resultados do sistema completo, em
[`backend/ml/README.md`](../backend/ml/README.md).
