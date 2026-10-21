# Phase 16 — Dashboard em 3 visões

Registro técnico da reorganização do dashboard ao vivo em três colunas. Cobre a
especificação, a maquete, os defeitos encontrados no caminho, a verificação por
voltas de teste e o que efetivamente entrou no código.

O trabalho começou numa sessão separada, foi descartado dela e reimplementado na
sessão da reformulação do mapa. Os commits que valem são `6973e314` e
`eb428d7e`, ambos de 19/08. Este documento existe porque o valor da sessão
descartada não estava no código: estava nos defeitos que ela encontrou.

## Contexto

O dashboard ao vivo tinha três colunas com proporções `minmax(230px, 0.82fr)
minmax(480px, 2.15fr) minmax(300px, 1.05fr)`, um mapa follow recém-reformulado, e
espaço morto no rodapé das colunas laterais. O pedido foi dividir a tela em três
visões de proporção fixa e reorganizar o conteúdo de cada uma.

Base: `72d59dc` (*Move the readout out of the car's way and ramp the pedal
colours*), último commit da reformulação do mapa.

## Especificação

Foi ditada em cinco mensagens, uma seção por vez, e mudou durante o processo. A
ordem final da coluna esquerda é o resultado de duas correções sucessivas
(setores subiram acima do Vehicle State; depois o Lap Timing subiu também).

### Proporções

Pedido: **15% / 60% / 15%**, que soma 90%. Os 10% restantes nunca foram
fechados pelo autor da especificação. A maquete aprovada fecha em **20/60/20**,
mantendo o centro nos 60% pedidos e dividindo o resto igualmente. É o que a
implementação usa.

### Esquerda

De cima para baixo: comparação por setor (amarelo/verde/roxo) → Lap Timing
(apenas LAP TIME e DELTA) → Vehicle State (Speed, Gear, Throttle, Brake, Steer).

O Vehicle State "deve compor verticalmente todo o espaço da esquerda": os dois
blocos de tempo acima têm altura fixa e ele absorve a sobra. O requisito real
por trás disso era o espaço morto marcado em vermelho no rodapé das colunas
laterais.

Saíram do dashboard: G-G Diagram, Stability e Cognitive Dashboard. A
especificação lista três painéis à esquerda e a implementação segue isso. Os
componentes continuam no código, apenas não montados.

### Centro

Mapa follow, com quatro cantos:

| Canto | Conteúdo |
| --- | --- |
| Superior esquerdo | Relevo e inclinação (sai da aba própria, entra no lugar do card de replay, que foi removido) |
| Superior direito | Cards de opções da pista (mantidos) |
| Inferior esquerdo | Minimapa, ampliado |
| Inferior direito | Estado do pedal → velocidade → KM/H → tempo de volta |

Requisito explícito sobre o canto inferior direito: *"nenhuma informação deve
estar ocupando o espaço ou sobrepondo a outra, tome cuidado altura dos itens"*.

Lap Comparison mantido abaixo do mapa.

### Direita

Conteúdo inalterado (abas Compare / Linha / Engineer / Debrief). O único pedido
foi tipografia: *"a fonte é extremamente pequena"*.

## Maquete

`frontend/mockups/dashboard-3-visoes.html` — 520 linhas, estática, sem
dependências além das fontes do Google. Reusa os tokens de `App.css`
(`--cyan`, `.panel`, `.label`, `.num`, JetBrains Mono / Inter) para que a
tradução seja mover markup, nunca recalibrar cor ou tipografia.

Foi iterada em quatro rodadas com o autor da especificação antes de virar
código, e é a referência de composição. Está versionada no repositório.

## Achados técnicos

Esta é a parte que justifica o documento. Sete defeitos, quatro deles
silenciosos.

### 1. Percentual circular em CSS — três ocorrências

O padrão: um filho se mede em porcentagem contra um pai cuja medida vem do
conteúdo. O pai pergunta a dimensão ao filho, que a pergunta de volta.

| Onde | Sintoma |
| --- | --- |
| Minimapa `height: max(124px, min(212px, 40%))` numa linha de altura automática | A linha inflou para 316px com 126px de conteúdo, jogando minimapa e readout 133px para fora do painel |
| Painel de relevo `width: min(300px, 34%)` numa coluna de grade `auto` | Colapsou de 300px para 109px |
| Painel de relevo `height: min(100%, 216px)` numa coluna flex de altura automática | Colapsou para o próprio `min-height` de 96px |

A cura é sempre a mesma: dar medida definida ao pai. Faixa de grade em `1fr`,
ou `height: 100%` herdado de algo com altura real — nunca `max-height` sozinho,
que não torna a medida definida.

### 2. `Number(null)` é `0`, não `NaN`

O defeito mais caro da sessão, e o único que só apareceu rodando telemetria.

Os frames chegam com `lap_time: null` **explícito**. Um helper escrito como

```ts
const numeric = (v: unknown) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;   // Number(null) === 0
};
```

lê esse `null` como o relógio tendo marcado **zero**. Todos os cruzamentos de
setor viraram zero, os três setores ficaram permanentemente em branco, e nada
no console indicou problema: o valor parecia dado, não lacuna.

Os testes passavam porque a fixture **omitia** a chave (`undefined` → `NaN` →
nulo corretamente), enquanto o frame real a manda presente e nula. A correção
rejeita `null`, `undefined` e `''` antes de converter.

O store escapa da mesma armadilha por acidente: `frameLapTimeSeconds` testa
`> 0` em vez de `>= 0`.

### 3. O relógio de fallback não zera na linha

A fonte de replay não preenche `lap_time`; só manda `sessionTime`, que corre
pela sessão inteira. Tratar o primeiro cruzamento como valor absoluto
transformaria toda a sessão até ali no setor 1.

Os splits precisam ser diferenças a partir da primeira amostra da própria
volta. Assim a origem do relógio não chega ao resultado, e o cálculo serve tanto
para relógio por volta quanto de sessão.

### 4. Não existe fonte de tempo de setor

`SectorData` está declarado no store, mas `setSectors` nunca é chamado por
ninguém. O backend informa **em qual** setor o carro está e nunca **quanto
durou** o anterior.

`frontend/src/utils/sectorTimes.ts` (187 linhas) deriva os splits do relógio da
volta ao cruzar cada terço de `lapProgress`. Terços de progresso, não os
marcadores do jogo: progresso é a única medida de posição que toda amostra
carrega, e é a que o coletor de voltas já usa para detectar a virada.

Cores: **roxo** = melhor da sessão, **verde** = bateu a mesma volta anterior sem
ser o melhor da sessão, **amarelo** = não bateu. Um setor ainda sendo percorrido
mostra traços.

A leitura é tomada na primeira amostra depois da fronteira, sem interpolação —
interpolar sobre uma amostra perdida inventaria um cruzamento que o carro pode
não ter feito. O custo é atrasar o split em no máximo um intervalo de amostra,
nunca adiantá-lo, e há teste fixando esse limite.

### 5. As fontes da direita são inline, fora do alcance do CSS

Os painéis definem tamanho em `style={{ fontSize: 8 }}`. Estilo inline vence
qualquer folha de estilo, então nenhuma regra `.col-right` os alcança. Os
tamanhos subiram na origem, em cinco componentes: escala 6→9, 7→10, 8→11, 9→12,
10→13 px.

### 6. `1fr` é `minmax(auto, 1fr)`

Com a tipografia maior, os três cards de setor estouraram a coluna de 244px: a
faixa cresce até caber o conteúdo em vez de dividir o espaço. `minmax(0, 1fr)`
deixa a faixa encolher, e aí o texto precisa poder cortar com reticências.

A implementação final estendeu isso às próprias colunas do dashboard: usa
`minmax(0, Nfr)` em vez de porcentagens, porque `20% + 60% + 20%` mais dois
`gap` de 6px ultrapassa a largura disponível em 12px — um estouro que o
`overflow: hidden` do container esconde, recortando a coluna direita.

### 7. Media query desfazendo a proporção

`@media (max-width: 1180px)` trocava as colunas do dashboard por pixels fixos
(`220px minmax(430px,1fr) 285px`), desfazendo a proporção exatamente nos
notebooks mais prováveis de rodar a aplicação. Removida.

## Verificação por voltas de teste

Dá para exercitar o dashboard sem o Assetto Corsa aberto.

```bash
TELEMETRY_SOURCE=replay python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Rodar `python main.py` diretamente falha com import circular:
`routers/assisted_analysis.py` faz `import main`, e como `main` é `__main__` o
módulo é carregado duas vezes. Via uvicorn não acontece.

A fonte `mock` não serve para isso: `MockTelemetryReader` herda um
`read_sample()` que retorna `None`. É fonte nula, não gerador.

### Resultado

Quatro voltas fechadas em Interlagos, splits derivados do fluxo real:

| Volta | S1 | S2 | S3 | Total |
| --- | --- | --- | --- | --- |
| 1 | 21.618 | 29.744 | 21.583 | 72.94 |
| 2 | 21.565 | 29.641 | 21.657 | 72.86 |
| 3 | 21.631 | 29.643 | 21.622 | 72.90 |
| 4 | 21.598 | 29.587 | 21.689 | 72.87 |

Os splits somam a duração da volta e os tempos são compatíveis com o circuito.
Melhores da sessão: 21.565 / 29.587 / 21.583. Na tela, S1 marcou 21.619 em
amarelo — mais lento que o melhor da sessão e que a volta anterior, que é a cor
correta.

### Limite conhecido desta fixture

O replay reconstrói a pista a partir da telemetria, e essa geometria sai com
**zero features de traçado** e sem altura por borda. Consequências:

- o minimapa não tem contorno para desenhar;
- o relevo cai no fallback *"esta pista ainda não tem altura extraída das duas
  bordas"*.

Nenhum dos dois é defeito de layout. Com a geometria KN5 real do Interlagos os
dois desenham.

Também nesta fixture o Lap Time exibe o relógio de sessão (minutos acumulados) e
o Delta fica em `N/A`, porque `frameLapTimeSeconds` cai para `sessionTime` na
ausência de `lap_time`. É comportamento pré-existente do store e não aparece com
o jogo real, que preenche `lap_time`.

### Geometria do layout medida

| Medida | Valor |
| --- | --- |
| Colunas em 1300×730 | 19.8 / 59.4 / 19.8 % |
| Colunas em 1920×1080 | 19.9 / 59.6 / 19.9 % |
| Espaço morto no rodapé esquerdo | 0 px |
| Overlay do mapa | contido na metade superior |
| Minimapa | 85 px → 149 px no mesmo painel |
| Sobreposições entre as quatro zonas | nenhuma, de 1100×640 a 1920×1080 |

## O que entrou no código

### `6973e314` — *Split the dashboard into three views*

19 arquivos, +1521 / −438.

Adicionados:

- `frontend/src/utils/sectorTimes.ts` (187) e `sectorTimes.test.ts` (120)
- `frontend/src/components/SectorComparison.tsx` (90)
- `frontend/src/components/map/MapOverlay.tsx` (103)
- `frontend/mockups/dashboard-3-visoes.html` (520)

Removidos:

- `drawBroadcastHud` de `BroadcastOverlay.ts` (−87) e seus testes (−99)

Alterados: `App.css` (+227), `Dashboard.tsx`, `TrackRenderer.tsx`,
`LiveTelemetryPanels.tsx`, os quatro painéis da direita, `CoachingFeed.tsx`,
`ARCHITECTURE.md`, `README.md`.

116 testes de frontend.

### `eb428d7e` — *Give the relief a square and take the height back for the map*

Ajuste de `App.css`: o painel de relevo ganha proporção quadrada e devolve
altura ao mapa.

### Onde a implementação final divergiu da maquete

Dois pontos, ambos melhorias sobre o que a sessão descartada tinha feito:

**Quadrantes de grade em vez de metades.** A sessão descartada dividia o mapa em
duas metades — overlay DOM em cima, canvas embaixo — para tornar a sobreposição
estruturalmente impossível preservando os testes do HUD em canvas. A versão
final foi além: os quatro cantos viraram quadrantes de uma grade, e o readout e
o minimapa saíram do canvas para o DOM. Isso custou a remoção de
`drawBroadcastHud` e dos seus 99 linhas de teste, mas eliminou o cursor manual
que era exatamente onde as alturas colidiam.

**`minmax(0, Nfr)` em vez de porcentagens.** Ver achado 6. A maquete usava
`20% 60% 20%`, que com os `gap` estoura por 12px e é recortado em silêncio pelo
`overflow: hidden`.

## Estado atual

A divisão em três visões está em `develop` desde 19/08, com mais de uma semana de
desenvolvimento assentado por cima (até `b1dc2502`, 25/08). A maquete continua
versionada como referência de composição. As correções de `sectorTimes.ts`,
incluindo a guarda contra `Number(null)`, sobreviveram intactas.
