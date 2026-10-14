# Sistema visual

- **Data:** 14/10/2026. **Pedido:** 29 (redesenho, etapa 1).
- **Onde está no código:**
  - variáveis: `frontend/src/theme/tokens.css`;
  - fontes: `frontend/src/theme/fontes.css`;
  - casca e componentes: `frontend/src/theme/componentes.css` e `frontend/src/components/ui/base.tsx`;
  - Tailwind: `frontend/tailwind.config.js`, que aponta para as mesmas variáveis.
- **Onde se vê:** tela Sistema › Guia visual (`#/sistema/guia`), que lê as cores das variáveis em uso, e o canvas de design do pedido 29.
- **Ponto de partida:** a opção A do protótipo (`frontend/mockups/prototipo_dashboard.html`), escura e densa, e a skill `frontend-design` (`.claude/skills/frontend-design/SKILL.md`). Onde a skill e as regras do projeto conflitam (legibilidade, nomes técnicos, português, uma fonte por número), valem as regras do projeto.

## 1. A ideia

**Carbono, vidro e rádio.**
- O fundo é carbono quase preto, com profundidade. O vidro dos recipientes tem o que desfocar.
- Um único vermelho de destaque, no tom das transmissões, marca o que está acontecendo: a tela ativa, a gravação e o rádio.
- Os números ficam numa superfície opaca dentro do vidro, para não perderem contraste.
- **A paleta é inspirada, não copiada.** Não há logotipo, marca, fonte proprietária nem cor de equipe da F1, do WEC ou da FIA. A marca do app é um traço de pista com um ponto, desenhado para ele.

## 2. Paleta

Toda cor dos componentes novos é uma variável de `tokens.css`. Os componentes antigos (Volta e Evolução, ainda com o conteúdo de antes) usam os nomes antigos (`--bg-core`, `--text-1`…), que agora apontam para a paleta nova.

| grupo | variável | cor | por quê |
|---|---|---|---|
| fundo | `--fundo` | `#08090B` | carbono quase preto: o jogo e as transmissões são escuros, e o app fica ao lado do jogo no mesmo monitor |
| | `--superficie` | `#0E1013` | superfície opaca para gráficos, tabelas e mapas: o número não fica sobre vidro |
| | `--superficie-2` | `#15181C` | o vidro quando a transparência está desligada; botões |
| | `--linha`, `--linha-fraca` | `#262B31`, `#1B1F24` | divisórias que separam sem desenhar caixa |
| texto | `--texto-1` | `#F2F4F5` | branco levemente frio, para títulos, números e corpo |
| | `--texto-2` | `#B4BCC4` | texto de apoio |
| | `--texto-3` | `#8E98A2` | rótulos. O antigo `#475569` não passava no AA; este passa com 5,79:1 no pior caso |
| destaque | `--vermelho` | `#E10600` | o vermelho de transmissão. É o fundo do botão principal (texto branco, 4,97:1), a marca da tela ativa e da gravação, e a etiqueta do rádio |
| | `--vermelho-claro` | `#FF4A3D` | o vermelho quando ele é texto: o `#E10600` como texto sobre o carbono não passa no AA (cerca de 4:1) |
| dados | `--freio`, `--acelerador`, `--parcial` | `#FF5A5F`, `#3DDC84`, `#F5C542` | as cores dos pedais do protótipo, que continuam |
| | `--perda`, `--ganho` | `#FFA24A`, `#6F9BFF` | laranja e azul do protótipo: um par que daltônicos também distinguem. **Perda e ganho nunca só pela cor:** sempre com o sinal (+ ou −) e o número |
| | `--voce`, `--referencia` | `#FFFFFF`, `#7F93A6` | a sua volta em branco (a mais visível no mapa) e a referência num cinza azulado |
| cronometragem | `--tempo-roxo`, `--tempo-verde`, `--tempo-amarelo` | `#B266FF`, `#2BD67B`, `#F5C542` | **só em tempos e só com o significado da F1:** roxo é a melhor de todas, verde é a sua melhor e amarelo é sem melhora. Neste pedido, o verde aparece só na "sua melhor volta" do hero |
| estados | `--estado-ok`, `--estado-aviso`, `--estado-erro` | `#4CC38A`, `#F2C14E`, `#FF7A6B` | os estados da Coleta e do backend. Cada etiqueta tem desenho e texto, além da cor |

## 3. Tipografia

As três fontes são arquivos locais em `frontend/src/assets/fonts`, com a licença (SIL Open Font License 1.1) ao lado. O app instalado funciona sem internet. O `index.html` e o `App.css` não buscam mais fontes no Google Fonts.

| papel | fonte | arquivos | licença | por quê |
|---|---|---|---|---|
| títulos e números grandes | **Barlow Condensed** (500, 600, 700) | `BarlowCondensed-*.ttf` | OFL 1.1, `BarlowCondensed-OFL.txt` | a do protótipo. É condensada, de quadro de cronometragem, e tem `tnum`: os algarismos têm a mesma largura e o tempo não "dança" quando muda. Baixada do repositório do Google Fonts (`google/fonts`, pasta `ofl/barlowcondensed`) com a autorização do Eduardo em 14/10 |
| texto | **Instrument Sans** (400, 700, itálico) | `InstrumentSans-*.ttf` | OFL 1.1, `InstrumentSans-OFL.txt` | sem serifa de desenho próprio, fora das genéricas (Inter, Roboto, Arial). Tem `tnum`. Substitui a IBM Plex Sans do protótipo, que não estava no computador e não foi baixada |
| dados | **IBM Plex Mono** (400, 700) | `IBMPlexMono-*.ttf` | OFL 1.1, `IBMPlexMono-OFL.txt` | a do protótipo. Monoespaçada: tempos em tabela, diferenças, `geometry_id` e rótulos de dado |

- **Acentos:** as três têm todos os acentos do português, o sinal de menos (−) e o ponto médio (·), conferidos nos arquivos com o fontTools.
- **Tempos** em M:SS,mmm, com vírgula. Isso vale também no `formatLapTime` das telas antigas.

## 4. Vidro

- **Onde entra:** só nos recipientes, que são a navegação, o hero, os painéis, os cartões, as dicas e o HUD.
- **Como é:**
  - `rgba(22, 25, 29, 0,55)` com `backdrop-filter: blur(18px) saturate(1,3)`;
  - borda de 1 px a 9% de branco, um filete de luz no topo e uma sombra;
  - a dica usa um vidro mais forte (72%) com desfoque de 12 px.
- **O número nunca fica sobre vidro puro.** Gráficos, tabelas, mapas e cartões de número ficam numa superfície opaca dentro do vidro: `--superficie-no-vidro` a 92%, ou `--superficie`.
- **O fundo:** uma camada parada atrás de tudo (`.casca-fundo`), com três elementos:
  - um brilho vermelho no alto, à direita;
  - um brilho frio embaixo, à esquerda;
  - uma trama diagonal de carbono a 1,6% de branco.
- **Camadas de desfoque:** uma por região, e nunca vidro dentro de vidro. Na tela Sessões são três (a navegação, o hero e o painel das sessões gravadas). O desfoque é estático: o fundo não anima, então o navegador não refaz o desfoque a cada quadro.
- **Acessibilidade:**
  - **`prefers-reduced-transparency`:** o vidro vira `#14171B` opaco, sem desfoque;
  - **manual:** a tela Sistema › Depuração tem o botão "Sem transparência" (`data-vidro="desligado"`), lembrado neste computador;
  - **`prefers-reduced-motion`:** a volta do hero aparece inteira, sem animar, e os pontos de "gravando" e "ligando" não pulsam.
- **Contraste:** pela fórmula do WCAG 2.1, no pior caso do fundo (o centro do brilho vermelho, com a trama). Todo texto passa no AA (4,5:1). A tabela completa sai de `node frontend/scripts/contraste.ts` e é conferida pelo teste `frontend/src/theme/contraste.test.ts`.

## 5. Componentes base

| componente | onde | o que faz |
|---|---|---|
| painel de vidro | `PainelVidro`, `.vidro.painel` | recipiente com título (Barlow Condensed, caixa alta) e nota à direita |
| cartão de número | `CartaoNumero` | rótulo, número grande (Barlow Condensed, `tnum`) e detalhe; sem dado mostra "—" e diz "sem dados" |
| chips e segmentado | `Chip`, `Segmentado`, `.segmentado-link` | escolha de volta (chip com `aria-pressed`) e de referência; as abas da tela Sistema são links com o mesmo desenho |
| tabela | `.tabela` | números alinhados à direita em IBM Plex Mono, linhas finas |
| etiqueta de estado | `EtiquetaEstado` | os estados da Coleta: ok, ausente, parado, fora da faixa, taxa baixa e sem dados. Cada um com desenho próprio e texto |
| dica | `Dica` | vidro forte que segue o mouse |
| mensagem de rádio | `MensagemRadioCartao` e `utils/radio.ts` | etiqueta "Rádio" (vermelha) ou "Foco" (neutra), volta e microssetor, hora, a frase e os números. A frase é montada em português a partir do `evidence` do coach (ver abaixo) |
| botões | `.botao`, `.botao--primario` | 44 px de altura; o principal é vermelho com texto branco |

**A mensagem de rádio:**
- **De onde vem a frase:** o coach manda a frase sem acento e com ponto decimal ("0.31s atras da volta da IA"). Mudar isso seria mudar o coach. Os números estão todos no `evidence` do evento, e a tela monta a frase com eles: "+0,31 s para a volta da IA neste trecho · 3,12 s contra 2,81 s · a IA freia 12 m depois de você". **Os números e a regra são os do coach; só a escrita muda.**
- **"Setor N" do coach** é o microssetor N de 60, e na mensagem se chama microssetor.
- **Evento sem esses números:** aparece a frase do backend como veio.
- **Para a realidade aumentada:** a mesma peça serve para o rádio dentro do jogo no próximo pedido.

## 6. Movimento

- **A volta do hero** é traçada uma vez, em cerca de 5,5 s, com a cabeça vermelha.
- **Os pontos de "gravando" e "ligando o backend"** pulsam.
- **Fora isso, nada anima.** Com `prefers-reduced-motion`, nada anima.
