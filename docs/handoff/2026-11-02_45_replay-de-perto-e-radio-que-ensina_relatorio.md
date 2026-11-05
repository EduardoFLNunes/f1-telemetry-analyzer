# Relatório parcial do pedido 45: o replay de perto, as voltas nos boxes e o rádio que diz onde e por quê

- **Pedido:** `docs/prompts/2026-11-02_45_replay-de-perto-e-radio-que-ensina.md`.
- **Situação:** **parado antes de fechar a Parte F, porque o limite de uso da sessão acabou.** A Parte G (o teste no jogo) ainda não foi liberada, e não há merge nem envio.
- **Branch:** `etapa/replay-e-radio-que-ensina`, a partir de `develop` em `bd04b93e`.
- **Commits:**
  - em `develop`: `bd04b93e` Pedido 45: texto do pedido, atualizacao de 04/11 do pedido 42 e backlog;
  - `29dec5ba` Parte B: um numero so para cada volta, a primeira volta com as medidas e o erro do WebSocket;
  - `460acdc9` Parte C: os cortes novos, antes de rodar as sessoes;
  - `e2ebc931` Parte C e rotas da Parte E;
  - `7c9d2d5e` Partes C.4, D e E;
  - `3fc07fa0` Parte H e E.3: documentacao, ADR 0027, versao 0.7.0 e as voltas que nao comecam na linha;
  - o commit deste relatório.
- **Arquivos de handoff** (`docs/handoff/2026-11-02_45_replay-de-perto-e-radio-que-ensina…`):
  - `_relatorio.md` (este);
  - `.c6.json` (o rádio antes e depois, fala a fala; **gerado antes de as voltas que não começam na linha entrarem na lista**);
  - `_incompletas.py` e `_incompletas.json` (B.1, hoje e com a proposta);
  - `_duracao_das_falas.json` (a voz de verdade, variante a variante);
  - `_conferir_lua.txt`;
  - `_previa.py`, `_previa_camera_c01.png`, `_c06.png` e `_c12.png`;
  - `_abrir_no_app_v7_c01.jpg` e `_abrir_no_app_v7_inteira.jpg`.

## O que falta e o que precisa de você

**Falta conferir ou fazer (nesta ordem):**

1. **A suíte inteira do backend não terminou de rodar.** Só `test_radio.py` e `test_radio_voltas_45.py` têm resultado: 56 passando. Mudei `driving_coach.py`, `main.py` e `core/coleta/estado.py`, então a suíte precisa passar antes do teste no jogo.
2. **Refazer o C.6 com o código final.** O rádio com a voz de verdade foi repetido, mas 21/10 não tinha terminado quando parei. As tabelas abaixo são da passagem anterior; a fala não deveria mudar, só a lista dos boxes.
3. **A prévia da lista e da grade de 01/11, com as voltas com rodada:** o script está pronto (`_previa.py voltas`), a imagem não foi gerada. **A janela dos boxes em Lua nunca foi desenhada** fora do jogo.
4. **Corrigir uma tabela da documentação:** em `docs/realidade_aumentada.md`, seção 2.2, o cartão da volta 7 e a linha da volta 11 têm números que escrevi como exemplo, sem conferir (`+0,44 s`, `7,5 m`, e "5,5 s (estimado)"). Os exemplos das seções 2.1, 2.3 e 2.6 ainda têm as palavras antigas ("Freia", "Mínima de").
5. **A Parte G:** os passos e a tabela de anotação ainda precisam entrar neste relatório, depois dos itens acima. Por isso **não teste no jogo ainda.**

**Processos meus que ficaram abertos: feche antes de abrir o jogo.** Duas instâncias do backend de teste continuam vivas, nas portas 8021 e 8022 (pastas isoladas no rascunho). Meu script não as encerrou, e o controle de permissões recusou o meu `Stop-Process`; não contornei. Se o jogo abrir com elas vivas, **elas podem começar a gravar a sessão na pasta isolada,** porque estão esperando o processo do jogo. Rode:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'uvicorn main:app --port (8021|8022|8011)' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

Uma contagem do WebSocket na porta 8011 também estava rodando quando parei, e ela encerra o próprio backend. O resultado dela não vale, porque fechei a aba da tela no meio.

**Decisões suas:**

1. **O critério das voltas que contam (B.1).** Ver a Parte B.
2. **O limite do resumo.** Ver a Parte C.
3. **A volta da IA continua calada.** A C.1 diz "o tempo e a diferença para a melhor, como hoje", mas hoje ela não tem resumo, e a G.8 diz que o rádio se cala. Deixei calada.

## Parte A: as conferências

1. **Os caminhos do contexto:** todos onde o contexto diz.
2. **O antes:** ver a tabela da Parte C.
3. **O que o backend guardava:** só a última volta fechada e as válidas da análise. Agora toda volta fica guardada em 5 linhas float32, cerca de 43 KB por volta, sem ler a gravação.
4. **O que a análise mede:** a freada, a mínima, o acelerador, o traçado e a perda. Entraram a velocidade no fim da curva e as partes da perda.
5. **O app do Windows:** ele ouve o WebSocket, e o aviso novo passa por ali. A tela Volta abre numa volta (`#/volta/<lapId>`), mas **só nas voltas do store,** e a sessão ao vivo não está nele. Por isso, fiz o replay grande na tela Ao vivo.
6. **As placas de freada:** o projeto não tem. Registrei no backlog.

**O que não bate com o pedido:** não existe o estado "inválida". As gravações e o quadro não trazem esse sinal. A lista tem válida, com rodada, da IA e incompleta. Registrei no backlog.

## Parte B: as voltas que o rádio não vê

### B.1 As voltas incompletas: **parei neste item, a decisão é sua**

**A causa não é um buraco na amostragem.** É a regra "boxes" do coach: um microssetor com a lateral acima de 10 m e abaixo de 90 km/h não é comparado, **em qualquer ponto da pista.** A volta 10 de 21/10 (1:29,518) caiu nela por um microssetor, o 38, com 11,0 m e 81,9 km/h.

| sessão | voltas que fecham | completas hoje | com a proposta |
|---|---:|---:|---:|
| 13/10 | 13 | 7 | 8 |
| 18/10 | 13 | 9 | 10 |
| 21/10 | 17 | 7 | 9 |
| 01/11 | 9 | 6 | 7 |

**Proposta, não aplicada:** a regra vale só onde existe pit lane (microssetores 54 a 59 e 0 a 10). Ela ganha 5 voltas nas 4 sessões: 1:33,120 (13/10), 1:40,073 (18/10), 1:34,494 e 1:29,518 (21/10) e 2:17,368 (01/11). A de 2:17,368 ainda cai na regra da rodada, se perder mais de 5 s numa curva. **Só 1 das 5 tem tempo realmente bom.** A maioria das incompletas é parada de verdade ou saída de pista, e continua incompleta.

**Um defeito de verdade, corrigido:** o rádio só lia a geometria na primeira frase do coach ou na primeira janela. A primeira volta que fechava antes disso saía "sem as medidas" (a volta 2 de 13/10 e de 18/10).

### B.2 A numeração

**De onde vinham os buracos:**

- **no coach:** o contador do jogo muda cerca de 1 a 2 m depois do s = 0, mas em 2 passagens ele mudou antes (13/10, a volta 9; 21/10, a 14). A volta saía com o número seguinte, e perdia as medidas, porque o número não batia com o da volta ao vivo;
- **voltas que não começam na linha:** a saída dos boxes ou o carro movido (21/10, a 8 e a 15; 01/11, a 3, a 4 e a 9). A sua observação de que a 14 não fecha era esse número errado: quem não fecha é a 15.

**Qual vence: o contador do jogo no meio da volta.** É o número que você vê no jogo, ele existe ao vivo e é igual ao `game_lap_number` do store (conferi 13/10 e 21/10). O `#NNNN` é a ordem no arquivo. A tela Volta passou a mostrar o número do jogo.

**Números repetidos, depois:** 0 nas 4 sessões (antes, 1 em 13/10).

### B.3 O erro "attached to a different loop"

**A causa:** no Python 3.9, `asyncio.Lock()` guarda o laço em que nasce, e o gerente nasce ao importar o módulo, antes do laço do servidor. Só dá erro quando dois envios disputam a trava. **A correção:** a trava nasce no laço que envia.

**O que está provado:** com o módulo antigo e 3 envios ao mesmo tempo, 2 falham com esse erro; com o novo, nenhum. Há um teste para isso.

**O que não está provado: a contagem numa reprodução de gravação não distingue os dois.** Deu **0 antes e 0 depois,** com clientes lentos e travados e com adversários falsos a 40 Hz (75 resumos de adversários no log). As 9 do pedido 43 foram com a tela aberta, e a repetição nessa montagem ficou sem resultado. **Depois do teste no jogo, é preciso contar o erro no log.**

### Antes e depois (as 4 sessões)

| | 13/10 | 18/10 | 21/10 | 01/11 |
|---|---:|---:|---:|---:|
| voltas na grade, antes | 6 | 8 | 6 | 6 |
| voltas na grade, depois | 7 | 9 | 6 | 6 |
| erros do WebSocket | ver B.3 | | | |

## Parte C: o rádio

**Os cortes novos** (`460acdc9`, antes de rodar): a velocidade no fim da curva usa o corte da mínima, 8 km/h, porque é a mesma grandeza, medida do mesmo jeito. O traçado usa o que a análise já tinha, 1,8 m. Abaixo de 1 décimo, nenhuma curva é citada.

**Uma escolha minha, para você conferir:** as separações do pedido 43 são 3 marcas, então a perda ficou em 4 partes. A parte antes da primeira freada (`reta`) não conta como causa, porque veio da curva anterior. As outras são freada (da freada à mínima da referência), mínima (dali ao fim da curva) e saída.

### C.6 Antes e depois (passagem anterior ao código final)

| resumos | 13/10 | 18/10 | 21/10 | 01/11 |
|---|---:|---:|---:|---:|
| total | 13 | 13 | 17 | 8 |
| **antes:** com a curva | 6 | 8 | 6 | 6 |
| **antes:** só a diferença para a IA | 7 | 5 | 11 | 2 |
| **depois:** com a diferença para a melhor | 13 | 13 | 11 | 8 |
| **depois:** com a diferença para a IA | 2 | 0 | 8 | 0 |
| **depois:** com a curva | 7 | 9 | 6 | 6 |
| **depois:** com a curva e a causa | 6 | 6 | 3 | 3 |
| curva que foi para mensagem própria | 1 | 3 | 3 | 3 |
| dessas, saíram da fila | 0 | 2 | 0 | 1 |

- **O motivo no antes:** incompleta (5, 4, 9 e 2), sem as medidas (2, 1, 1 e 0) e rodada (0, 0, 1 e 0).
- **A causa, por trecho:** freada 17, mínima 9, saída 2. Por medida: freada 17, mínima 8, saída 2, traçado 1. Nenhuma curva ficou sem trecho.
- **As durações:** nenhuma passou do limite do tipo: resumo até 7,69 s (limite 7,7), coach até 7,18 s (7,3), análise até 8,73 s (8,8) e curva até 5,70 s (7,3).
- **Os números do replay na fala:** 50 de 58 curvas. As outras 8 são a segunda curva de uma análise, que a voz não citou: não têm número falado, e o replay mostra o do cartão.

### Decisão: o limite do resumo

**O que você quer ouvir nem sempre cabe em 7,7 s.** Medido com a voz de verdade:

| fala | dura |
|---|---:|
| "3 décimos atrás da sua melhor, 4,2 segundos atrás da IA. Curva 1: 7 décimos, freou 15 metros antes da IA." | **8,73 s** |
| "Melhor volta, 2 décimos mais rápida. Curva 12: 4 décimos, saiu 8 quilômetros por hora mais lento." | **7,72 s** |
| "1,1 segundo atrás da sua melhor. Curva 6: 5 décimos, passou 3 metros por fora no ápice." | 7,48 s |
| "Volta com rodada: 1 minuto e 36,4 segundos, 7,0 segundos atrás da sua melhor." | 7,13 s |

Pela sua ordem, a IA sai antes da curva. Por isso **a diferença para a IA quase sumiu da voz** (10 de 51 resumos); no cartão ela continua. As janelas têm de 7,8 a 8,7 s, então subir o limite para cerca de 8,7 s faria o seu primeiro exemplo caber só na janela mais longa. A alternativa é aceitar a IA só no cartão. **Não mudei o limite.**

## Partes D e E: o que foi feito

- **A câmera:** 80 m no lado menor; a curva inteira por 1 s e 0,8 s de aproximação; os dois carros sempre na tela; o trecho em câmera lenta; a roda do mouse; os números da voz no alto. A mesma conta no Lua e na tela. Prévias de C01, C06 e C12 nos 3 tamanhos, feitas na volta 6 de 01/11.
- **Os boxes:** a janela abre sozinha e cresce 2 vezes (eram 1,6, para caber a lista). Lista, grade clicável, aviso de rodada e o botão. **As voltas que não começam na linha também tocam,** como a 3 e a 4 de 01/11 que você citou, com o tempo corrido do jogo e fora da análise.
- **O tamanho das rotas (01/11, volta 7, no backend de teste):** a volta inteira, 138 KB em 43 ms, abaixo dos 500 KB; uma curva, 11 KB em 11 ms; a melhor, 17 KB; a lista, 830 bytes com 3 voltas.
- **Ponta a ponta:** com o reprodutor e a pasta isolada, o pedido ao backend abriu a volta 7 na C01 e a volta inteira, na aba "[teste]" (já fechada). O pedido com a aba fechada respondeu "o app do Windows está fechado". **O teste achou um defeito, já corrigido:** repetir o mesmo pedido não relia o replay.
- **O que não foi visto:** o clique no botão dentro do jogo (o pedido foi feito direto à rota) e o que o Windows faz com a janela, que só o teste no jogo mostra.
- **O caminho sem as rotas novas:** um 404 em `/api/radio/voltas` deixa a janela como antes. Conferido só lendo o código: não há Lua neste computador.

## Os testes

- **Front:** 180 passando, `tsc` e build sem erro.
- **Lua:** `conferir_lua.py` contra o SDK do CSP: 0 erros de léxico, blocos fechados, API e métodos no SDK.
- **Backend:** `test_radio.py` e `test_radio_voltas_45.py`, 56 passando. **A suíte inteira não terminou.**

## O envio ao GitHub

**Nada foi enviado.** O `develop` remoto está em `aa576597`; o local, em `bd04b93e`. Conferi nos commits que nenhuma gravação entrou (`recordings/` e `data/` não foram tocados). Quando quiser uma cópia do que está aqui, rode no terminal:

```powershell
git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer push -u origin etapa/replay-e-radio-que-ensina
```

```powershell
git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer ls-remote origin refs/heads/etapa/replay-e-radio-que-ensina
```

Sem `--force`. O `develop`, `main` e as tags não vão agora.
