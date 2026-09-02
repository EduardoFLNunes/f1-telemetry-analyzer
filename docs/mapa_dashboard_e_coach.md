# Mapa, dashboard e coach — o que foi feito e o que se mediu

Documentação técnica do trabalho da sessão de **19/08/2026**: nove commits,
`f71fef3` a `5a5fbc4`, 44 arquivos, +5.589 / −337 linhas.

> **Escopo.** Este documento cobre apenas essa sessão. Os commits de 23 a 25/08
> (subsistema de ML, linha ótima, painel de versão — `a7ac938`..`b1dc250`) vieram
> de outras sessões e não são descritos aqui.

Cada seção segue a mesma forma: **o que estava errado**, **o que mudou**, e **como
se sabe que funcionou**. Onde há número, ele foi medido nesta máquina, com estes
dados — não estimado.

---

## Sumário

| # | Commit | Assunto | Resultado |
|---|---|---|---|
| 1 | `f71fef3` | Testes de frontend do zero | 51 testes; 4 regressões reais reproduzidas e detectadas |
| 2 | `99f6262` | Mapa follow em padrão de transmissão | Câmera sem rotação, asfalto/zebras/rastro redesenhados |
| 3 | `d977782` | Backend escrevia na pasta de instalação | App deixou de morrer no boot sob `Program Files` |
| 4 | `72d59dc` | Leitura no canto e rampa de cor | + correção de densidade de tela (dpr) |
| 5 | `6973e31` | Dashboard em três visões | 20/60/20 medido; zero sobreposição nos 4 cantos |
| 6 | `eb428d7` | Proporções do relevo e da comparação | Relevo 180×96 → 255×255; comparação −40% |
| 7 | — | Análise do travamento da coleta | 4,6% da sessão perdida; causa isolada |
| 8 | `4568d59` | Modelo de referência + coach ao vivo | Produtor que faltava para os painéis de IA |
| 9 | `7e3320f` | Coach sobre volta gravada (replay) | Eventos no instante certo da volta |
| 10 | `5a5fbc4` | Bordas da volta e limiar adaptativo | Ideal 82,40 → 83,542 s (o primeiro era ficção) |

Estado ao fim da sessão: **277 testes de backend, 123 de frontend**, todos
passando. (Hoje, com o trabalho posterior de outras sessões: 368 e 135.)

---

## 1. Testes de frontend, do zero — `f71fef3`

**O que estava errado.** Não existia nenhum teste de frontend. O README e o
ARCHITECTURE registravam isso como débito. As duas regressões visuais que
tinham chegado ao usuário naquele mês eram de matemática de desenho — o tipo de
erro que `build` e `tsc` não enxergam.

**O que mudou.** Vitest instalado, `npm test`, e 51 testes rodando em Node
contra um canvas que **registra as chamadas em vez de desenhar**
([`src/test/fakeCanvas.ts`](../frontend/src/test/fakeCanvas.ts)). Assim se afirma
ordem, largura, cor e regra de preenchimento sem depender de rasterização.

Para tornar isso testável, a projeção e a suavização de guinada saíram de dentro
do `useEffect` de desenho e viraram funções exportadas (`makeProjector`,
`yawTarget`, `advanceYaw`) — a matemática é a mesma.

**Como se sabe que funcionou.** Reintroduzi cada defeito e rodei a suíte:

| Defeito reintroduzido | Testes que quebraram |
|---|---|
| altura subtraída (pista invertida) | 4 |
| projeção oblíqua de volta (pista inclinada) | 2 |
| limite de pista deixa de ficar por cima | 2 |
| asfalto preenchido loop a loop (miolo manchado) | 1 |

---

## 2. Mapa follow no padrão de transmissão — `99f6262`

**O que mudou.** O mapa passou a abrir seguindo o carro, e o desenho seguiu a
gramática de uma transmissão de TV:

- **Câmera sem rotação.** Girar o mapa para manter o bico do carro para cima faz
  o mundo inteiro rodar em volta de um carro que nunca parece virar, e nenhuma
  curva fica reconhecível. Parado, o S do Senna continua com cara de S do Senna.
- **Asfalto cinza `#2c2c2c`**, linha branca de limite mais grossa (0,22 m),
  **zebras como dentes brancos** sobre base escura.
- **Carro como disco**, não silhueta: nesse zoom uma silhueta é um borrão e um
  disco é uma posição.
- **Rastro dos últimos 14 s**, colorido pelo que o piloto fazia e apagando para
  trás — o mapa vira memória curta, não diagrama.

**Decisão registrada.** A referência (Formulytics) escreve DEPLOY/REGEN no
rastro. Não modelamos ERS, e inventar um em cima de acelerador e freio seria um
gráfico que mente — então o rótulo diz o que os pedais fizeram.

---

## 3. O backend escrevia dentro da própria instalação — `d977782`

**O sintoma.** Instalado em `C:\Program Files`, o app abria sem backend. Três
tentativas, o mesmo erro:

```
PermissionError: [WinError 5] Acesso negado:
'...\resources\data\external_references'
```

**A causa.** `ExternalReferenceRepository` criava esse diretório **no import**, a
partir do *resource root* — que é a pasta de instalação. O cache do FastF1 fazia
o mesmo. Funcionava por acidente: o instalador sempre caía em
`AppData\Local\Programs`, onde o usuário pode escrever.

**O que mudou.** Ambos passaram a usar o **runtime root**
(`AppData\Roaming\...`), onde o cache de pista e as gravações já iam. E criar o
diretório deixou de ser fatal: um diretório que não dá para criar é uma
funcionalidade a menos, não motivo para o app se recusar a subir.

**Como se sabe que funcionou.** O backend novo foi executado com o resource root
apontado para `Program Files` — o cenário exato que matava — e chegou a
`health 200`, gravando o cache em `AppData\Roaming`.

**O teste que importa** sobe o `main` num subprocesso com os dois roots
separados. A primeira versão do teste passava *com o bug de volta*, porque em
desenvolvimento os dois roots são a mesma pasta — que é precisamente por que
isso passou batido até virar instalador.

---

## 4. Leitura no canto, rampa de cor e densidade de tela — `72d59dc`

- **A leitura saiu do centro.** Uma transmissão pode centralizar porque a câmera
  dela mantém o carro fora do meio do quadro; a nossa põe o carro exatamente no
  centro, então o número ficava em cima do que descreve. Foi para o canto
  inferior direito.
- **A cor virou rampa contínua.** Três cores fixas desenhavam uma emenda dura a
  cada alívio do acelerador. Os pedais viram um número só, de −1 (freio a fundo)
  a +1 (acelerador a fundo), e a cor é lida numa rampa de cinco paradas. Onde os
  pedais mudam entre duas amostras, o segmento carrega a mudança ao longo do
  próprio comprimento — a 20 Hz, trocar no vértice aparece como degrau.
- **Bug de densidade de tela.** Todos os elementos em espaço de tela chamavam
  `resetTransform()`, que descarta a escala do `devicePixelRatio` junto com a
  câmera. Em 1× parece certo; em 2× a leitura, o mini-mapa e as legendas caem no
  quadrante superior esquerdo. Passaram a restaurar a transformação base
  (`screenSpace()`).

---

## 5. Dashboard em três visões — `6973e31`

**Proporção 20/60/20**, em `minmax(0, Nfr)` e não porcentagem: porcentagem
ignora o `gap` e estoura, e um `1fr` cru é `minmax(auto, 1fr)`, que deixa o
conteúdo empurrar a coluna. Havia um `@media (max-width:1180px)` que trocava as
colunas por pixels fixos, desfazendo o desenho justamente nos notebooks onde o
app mais roda — removido.

**Os quatro cantos do mapa viraram uma grade de quadrantes**, não itens
posicionados por cima uns dos outros: relevo em cima à esquerda, controles à
direita, mini-mapa embaixo à esquerda, leitura embaixo à direita. Nenhum pode
crescer para dentro do outro — garantia estrutural, não ajuste de altura que a
próxima mudança desfaz. Por isso a leitura e o mini-mapa saíram do canvas para o
DOM: medidos por cursor manual, eram exatamente onde as alturas colidiam.

**Tempos de setor: medidos, não recebidos.** Nada os envia — o backend informa em
que setor o carro está e nunca quanto durou o anterior; `setSectors` não tem
chamador. [`sectorTimes.ts`](../frontend/src/utils/sectorTimes.ts) os deriva do
relógio da volta a cada terço, com duas armadilhas cobertas por teste:

1. os quadros trazem `lap_time: null` explícito, e `Number(null)` é `0`, não
   `NaN` — uma checagem de "número finito" escrita do jeito óbvio transforma cada
   lacuna numa volta que começou em zero;
2. o relógio de reserva, `sessionTime`, não zera na linha — só diferenças a
   partir da primeira amostra da volta significam algo.

**Medido na tela:** proporção 19,6 / 58,8 / 19,6 (o resto são os vãos), mantida a
1100 px de largura; **zero sobreposição** entre os quatro cantos; espaço morto no
rodapé das três colunas: **0 px**.

**Saíram da tela** (a maquete aprovada tem três painéis à esquerda): G-G Diagram,
Stability e Cognitive Dashboard.

---

## 6. Proporções do relevo e da comparação — `eb428d7`

| | antes | depois |
|---|---|---|
| Lap Comparison (altura) | ~267 px | **162 px** (−40%) |
| Relevo a 1280×860 | 180×96 | **255×255** |
| Relevo a 1280×660 | 180×96 | **178×178** |

O relevo virou quadro porque um retângulo baixo cortava justamente a altura, que
é o que a fita tem a dizer. É dimensionado pelo próprio quadrante, então encolhe
sozinho numa janela baixa em vez de invadir o canto de baixo.

---

## 7. Análise do travamento da coleta (sem alteração de código)

Diagnóstico feito com o Assetto Corsa rodando. **Duas causas independentes, e
nenhuma delas era o jogo.**

### 7.1 Perda periódica de 0,31 s a cada 6,0 s

Medindo o arquivo da sessão (19,3 min, 65.530 amostras, 56,7 Hz médio):

| | |
|---|---|
| buracos > 0,2 s | 167 |
| duração de cada | mediana 0,312 s |
| intervalo entre eles | **6,0 s em 136 dos 166 casos** |
| total perdido | **53 s de 1155 s — 4,6%** |

O período de 6,0 s é o do `RACING_LINE_POLL_MS` do mapa. Cronometrado com o
carro na pista:

```
racing-line: 1,08 / 1,24 / 1,84 / 1,34 / 1,54 s   (~340 KB por resposta)
health:      0,003 s
```

O handler é `async def` chamando `live_racing_line_payload()` de forma síncrona —
roda no event loop e o congela por 1 a 1,8 s a cada 6 s.

**Discriminador decisivo:** comparar o relógio do jogo com o relógio real através
de cada buraco. Em **160 de 164**, o jogo continuou andando (perda nossa); nos 3
maiores (3,58 s, 1,64 s, 1,17 s) o relógio do Assetto avançou 0,06 / 0,07 /
0,02 s — o jogo estava pausado, e o software acertou em não gravar.

### 7.2 A sessão de gravação morria por falha do `tasklist`

```
20:58:18  capture gate closed: stale_assetto_corsa_shared_memory_without_process
20:58:18  Session recording stopped
20:58:36  Session recording started      ← sessão nova, do zero
```

`assetto_corsa_process_running()` roda `tasklist` num subprocesso com
`timeout=2.0` e `except Exception: continue` — **qualquer falha ou lentidão da
listagem é lida como "o jogo não está rodando"**, e a gravação é encerrada.
Ocorreu no mesmo segundo em que a frequência caiu para 28 Hz, o que é coerente:
é quando a máquina está mais ocupada que o `tasklist` demora mais.

### 7.3 Custo por amostra

3,6 KB por amostra (`carPhysics` 53%, `projectionDebug` 10% — dado de depuração
sendo persistido), 207 KB/s, 185 MB em 15 min, 12,4 GB acumulados em 88 sessões.
`persistenceAvg` = 50 ms; `loopTick.max` = 308 ms. Arredondar floats para 4 casas
e não gravar `projectionDebug` reduziria a amostra em **34%** (medido).

> Estes três itens foram **diagnosticados e não corrigidos** nesta sessão.

---

## 8. Modelo de referência e coach ao vivo — `4568d59`

### 8.1 Por que os painéis de IA estavam vazios

Não era bug de exibição. `COACHING_EVENT` e `ENGINEER_SPEECH` são declarados,
três consumidores os assinam, o store normaliza, os painéis renderizam — e
**ninguém publicava**. Em todo o backend só dois tópicos eram emitidos:
`processed_frame` e `opponents_frame`. O socket nem assinava `engineer_speech`.
Por isso `/api/live/coach` respondia `eventCount: 0` e o status era
`INSUFFICIENT_DATA` para sempre.

### 8.2 Não havia rede para treinar

Não existe sklearn, torch, tensorflow ou modelo algum no código do projeto. O que
existe é `core/assisted_analysis/` — 12 módulos de análise física/por regras, e
ele funciona: na volta 349 identificou 12 curvas, 18 erros, confiança 0,97,
*"Maior oportunidade em T7: Liberação brusca do freio"*.

### 8.3 O número dele era inútil, e por quê

```
volta analisada : 349  —  85,740 s
referência usada: 348  —  85,845 s   "mode": "previous_lap"
ganho total estimado: 0,011 s
```

A volta foi medida contra a **anterior, que era mais lenta**. `service.py`
preferia a volta anterior incondicionalmente. Onze milésimos em 85 segundos não
é resultado, é artefato da referência errada.

### 8.4 O que foi construído

**[`reference_model.py`](../backend/core/assisted_analysis/reference_model.py)** —
a volta é cortada em 60 microsetores, cada volta utilizável é cronometrada em
cada um, e o modelo guarda **o mais rápido que o piloto já foi** ali, mais como
ele fez (velocidade mínima, ponto de freio, ponto de acelerador).

Duas propriedades, ambas vindas dos dados:

- todo alvo é um tempo que o piloto **realmente já fez** — "dá para ganhar 0,4 s
  em T4" significa "você já fez T4 0,4 s mais rápido que isto";
- a volta ideal é a soma desses alvos: mais rápida que a melhor volta dele, e que
  ele nunca fez de ponta a ponta.

**Filtro de sanidade.** Uma volta de 937 amostras em 74 s é 13 Hz de um sinal de
57 Hz — e era a "melhor volta" do histórico. Arquivo corrompido não é recorde.

**[`driving_coach.py`](../backend/core/live/driving_coach.py)** — o produtor que
faltava. Percorre o modelo enquanto o piloto anda e fala quando um microsetor
custa tempo real. Faz quase nada por quadro: este backend já perdeu 4,6% de uma
sessão para um endpoint no event loop, e um coach a 57 Hz não podia ser o
segundo.

**[`train_reference_model.py`](../backend/tools/train_reference_model.py)** — o
treinador, com filtro rápido antes de carregar (não adianta ler uma volta que o
modelo vai recusar) e relatório do que aprendeu e do que descartou.

**Interpolação da travessia**, no modelo e no coach: a 57 Hz, tomar o quadro
seguinte à linha cobra até 17 ms por microsetor — 60 microsetores por volta, ou
seja **um segundo de perda por volta que o piloto nunca teve**, sobre o qual o
coach reclamaria.

---

## 9. Coach sobre volta gravada — `7e3320f`

O replay toca **inteiramente no navegador**: as amostras nunca chegam ao backend,
`processed_frame` nunca é publicado, e o coach ao vivo não enxerga uma volta
gravada. Em vez de escrever um segundo coach em TypeScript que divergiria do
primeiro, a volta é percorrida pelo **mesmo objeto** no servidor.

`GET /api/analysis/coach/lap/{lapId}` devolve tudo o que ele diria, cada evento
marcado com o instante da volta a que pertence; o player solta cada um quando o
carro chega ali.

Três armadilhas, todas fixadas por teste:

1. o coach ao vivo espera 3 s entre falas; uma volta reproduzida em 20 ms
   dispararia isso uma vez e emudeceria o resto — no caminho gravado o portão
   fica desligado;
2. cada movimento do relógio reconta a volta do zero — sem filtro, o feed
   repetiria tudo a cada tick, 60 vezes por segundo;
3. arrastar o slider para trás rebobina o marcador, então assistir de novo fala
   de novo.

O endpoint roda **fora do event loop** (`asyncio.to_thread`), pela lição da
seção 7.

---

## 10. Bordas da volta e limiar adaptativo — `5a5fbc4`

Treinar em 150 voltas reais expôs dois artefatos de borda e uma premissa errada.

**O último microsetor nunca fechava.** Uma volta gravada termina alguns quadros
*depois* da linha, com `lapProgress` já de volta a ~0,0002; `progresso ≥ 1,0`
nunca era verdade. A volta ideal era a soma de **59 fatias de 60**.

**O primeiro microsetor era pior:** seu alvo era definido por qualquer volta que
tivesse começado a gravar mais tarde. O setor 0 carregava **8× a dispersão** de
qualquer outro (0,263 s contra 0,034 s típica) — e era a única coisa que o coach
achava para dizer sobre uma volta limpa.

**Resultado da correção:**

| | primeiro modelo | corrigido |
|---|---|---|
| setores com alvo | 59/60 | **60/60** |
| volta ideal | 82,400 s | **83,542 s** |
| na mesa | 2,461 s | **1,319 s** |

Verificado em voltas reais: os 60 setores fecham e somam a **4 ms** (L19) e
**7 ms** (L20) do tempo gravado, onde antes faltavam 934 ms.

**O limiar.** Um valor fixo de 0,15 s pressupõe que erro vem em bloco. Um piloto
consistente perde a volta em fatias: a melhor volta da biblioteca está 1,47 s
acima do próprio ideal sem nenhum microsetor pior que 0,14 s — o coach não
reportava **nada** numa volta que tinha um segundo e meio dentro. O limiar passou
a ser **duas vezes a oscilação do próprio piloto** naquele microsetor (que o
modelo já mede como mediana − melhor), com piso.

---

## Resultado final

### O modelo treinado

```
voltas no modelo   : 150        (das 563 utilizáveis; nenhuma descartada nesta seleção)
microsetores       : 60
melhor volta real  : 84,861 s
volta ideal        : 83,542 s
na mesa            : 1,319 s
```

Material disponível: **563 voltas utilizáveis** (densidade 40–70 Hz),
~2,78 milhões de amostras; 137 descartadas por dados ralos ou corrompidos.

### O coach na melhor volta (L19, 85,059 s)

```
 10,72s | setor  6 | perdeu 0,14s (1,44 vs 1,29)   mínima do seu melhor: 137 km/h
 22,81s | setor 17 | perdeu 0,09s (1,20 vs 1,11)   189 km/h
 38,16s | setor 28 | perdeu 0,08s (1,64 vs 1,55)   157 km/h
 43,77s | setor 31 | perdeu 0,09s (2,42 vs 2,34)    90 km/h
 48,45s | setor 33 | perdeu 0,12s (2,35 vs 2,23)    99 km/h
 56,33s | setor 37 | perdeu 0,07s (2,54 vs 2,47)    82 km/h

RADIO: Volta fechada. 1,47s acima do seu ideal, a maior perda no setor 6 (0,14s).
```

**O achado que vale mais que os números:** a volta seguinte perde nos **mesmos
setores** — 6, 17, 28, 31. Não é ruído, é padrão.

### Testes

| | ao fim desta sessão | hoje |
|---|---|---|
| backend (unittest) | 277 | 368 |
| frontend (Vitest) | 123 | 135 |

O frontend não tinha nenhum teste no início da sessão.

---

## O que ficou pendente

1. **Os três itens da seção 7** — o endpoint da racing line no event loop, o
   `tasklist` que mata a sessão, e os 3,6 KB por amostra. Diagnosticados, não
   corrigidos.
2. **O app instalado** (backend de 25/08 08:38) já é posterior a estas
   correções — a pendência que existia ao fim da sessão foi resolvida por um
   build posterior. O modelo treinado vive no runtime root
   (`AppData\Roaming\...\dataeference_modelshe_interlagos.json`) e é lido
   sem reinstalar.
3. **Sem CI** — as duas suítes rodam na mão.
