# 0029 — A linha gerada dirigida pela IA do jogo

- **Status:** aceita (pedido 47). Registrada antes de qualquer sessão no jogo; o resultado entra no fim, sem mudar o registro
- **Data:** 2026-11-07
- **Decisor:** Eduardo
- **Refina:** 0028 (o medidor do Modelo 1). **Mantém:** 0009 (a linha não vai para o coach), o corredor do 0025 e o 0008 (com a atualização de 07/11: uma sessão por pasta)

## Contexto

1. **No pedido 46,** as duas linhas geradas pelo Modelo 1 ficaram abaixo da volta da IA no medidor do tempo: 1:22,898 sem a LSTM e 1:23,481 com ela, contra 1:26,284 da volta da IA `2026-10-04_03-42-10#0013` (1:24,829 no cronômetro).
2. **Mas o medidor não ordena as voltas reais:** a correlação com o cronômetro é de 0,36 nas 150 voltas rotuladas, e ele põe a melhor volta do Eduardo à frente da IA. Ele supõe o carro sempre no limite do envelope: mede a linha, e não a execução.
3. **O objetivo do TCC** é uma volta gerada pelo menos tão rápida quanto a da IA. Falta um medidor que segure a execução constante e mude só a linha.
4. **A proposta:** a IA do Assetto Corsa dirige a linha gerada. O piloto é o mesmo (a IA), assim como o carro e as condições. Só a linha muda, e o tempo vem do cronômetro do jogo. A IA segue a linha do arquivo `ai\fast_lane.ai` da pista.
5. **A exceção autorizada pelo Eduardo em 07/11:** uma cópia da pista `vhe_interlagos` com outro nome (`vhe_interlagos_teste_m1`, "Interlagos [teste]" no jogo), para trocar a linha da IA só na cópia. A pasta original nunca é escrita, e o `data.acd` nunca é aberto.

### O que a Parte A do pedido 47 achou (a base deste registro)

- **A pista** tem dois layouts, `gp` e `norm`. Os dois têm o mesmo `fast_lane.ai` (1.274.780 bytes, sha256 `36b57fd8d259755d…`). As gravações são do `gp`, e não há `data\ai_hints.ini`.
- **O formato** é a versão 7, com 2.680 pontos (detalhes em `docs/handoff/2026-11-07_47_linha-gerada-no-jogo_relatorio.md`, Parte A):
  - o cabeçalho e os pontos;
  - os 18 floats por ponto;
  - uma grade de vizinhos de 135 × 173 células de 10 m.

  O leitor e o escritor (`backend/ml/pista_teste/ai_spline.py`) refazem o arquivo byte a byte.
- **O referencial é o mesmo das gravações.** Os pontos do `fast_lane.ai` ficam a 0,21 m da volta `#0013` (mediana; p95 de 0,94 m). **A IA segue a linha do arquivo de perto.**
- **A velocidade gravada na linha dá uma volta de 95,1 s,** e a IA faz 84,8 s com o carro do TCC. A IA não usa essa velocidade como teto.
- **As bordas da IA são outras.** A largura entre as laterais é 3,0 m menor que a do corredor do pedido 44 (mediana). As bordas ficam a 1,4 m e a 1,6 m das bordas do corredor (mediana).

## Decisão

### 1. As condições

Todas rodam na cópia, com o mesmo carro, o mesmo preset (item 2) e a IA dirigindo pelo Ctrl+C.

| condição | linha | sha256 da linha lateral (`float64`, na grade de 2 m) |
|---|---|---|
| **C0** | a linha original (o arquivo da cópia sem mudança) | `de35389123c878fe…` |
| **C1** | a volta da IA `2026-10-04_03-42-10_vhe_interlagos#0013`, codificada como as linhas da busca do pedido 46 (`encoding.decode(encoding.encode(lateral))`, pontos de controle a cada 25 m) | `3a6df338cfd6bd79…` |
| **C2** | a melhor volta do Eduardo, `2026-10-24_13-43-32_vhe_interlagos#0003`, codificada do mesmo jeito | `bad8b3cc61964ed8…` |
| **C3** | a linha gerada sem a LSTM (`data/ml/modelo1_final/linha_sem_lstm.npy`) | `fd8ae1097ddd7548…` |
| **C4** | a linha gerada com a LSTM (`data/ml/modelo1_final/linha_com_lstm.npy`) | `7374a6b5e7d4d040…` |
| **C0 final** | a linha original de novo, no fim, para medir a deriva das condições | — |

**De C1 a C4, a mesma regra de preenchimento dos campos** (`backend/ml/pista_teste/linha_nova.py`):

- **os pontos:** o mesmo número do original (2.680). O ponto `i` fica na mesma estação da pista que o ponto `i` original, ou seja, no mesmo `s` da geometria do projeto (`geometry_id 0ed16f0dd2225990`). Assim, o ponto 0, o sentido e o fechamento ficam iguais;
- **a altura e a normal da superfície:** as do ponto mais próximo da linha original, projetado no segmento e interpolado;
- **a distância:** o comprimento 3D acumulado;
- **a geometria** sai da linha nova, pelas fórmulas que reproduzem o arquivo original:
  - o vetor para a frente é a direção a partir do ponto anterior, e a inclinação é o Y dele;
  - o comprimento é o segmento 3D até o ponto anterior;
  - o raio é o do círculo pelos pontos `i−1`, `i` e `i+1` em X/Z, com o erro relativo mediano de 0,1% no original;
  - a direção é o lado da curva;
  - a cambagem é `direção × (normal · esquerda)`;
- **as laterais:** as bordas ficam no mesmo lugar (as do arquivo original) e a distância muda. **Onde a linha passa da borda da IA, a lateral fica em 0:** a borda vira a própria linha. Isso acontece em 8 pontos da C2 (no máximo 8 cm) e em 4 da C4 (no máximo 1,4 cm). O corredor do pedido 44 é mais largo que as bordas da IA;
- **a velocidade, o acelerador e o freio:** os do ponto original da mesma estação. **Por quê:** as fontes não concordam sobre o uso desses campos pela IA, e a velocidade gravada (95,1 s) não limita a IA (84,8 s). Mantê-los iguais faz a linha ser a única coisa que muda. Assim, C1 contra C0 mede o custo desta regra e da codificação juntas;
- **`ObsoleteLatG` e a marca:** 0, como no original;
- **a grade:** recalculada para a linha nova, com os mesmos parâmetros (10 vizinhos, 10 m, folga de 350 m). No original, o recálculo dá a mesma grade em 23.326 das 23.355 células; nas outras 29, os pontos empatam em menos de 0,05 mm;
- **as dicas da IA:** não há `ai_hints.ini` em Interlagos, e nada muda.

**Só o `gp\ai\fast_lane.ai` da cópia muda.** O `pit_lane.ai`, o layout `norm` e o resto da pasta ficam como na original.

### 2. O preset

O mesmo em todas as sessões; o Eduardo o grava no Content Manager como "pedido 47 [teste]" antes da primeira.

| item | valor |
|---|---|
| carro | `rss_formula_rss_3_v6_2026` (Formula RSS 3 2026 V6), o da volta `#0013` |
| acerto | o padrão do carro, sem acerto carregado |
| modo | prática, sozinho na pista, largando dos boxes |
| combustível | 30 L, com o consumo desligado (0×) |
| pneu | o composto padrão do carro, com o desgaste desligado (0×) |
| temperatura | ar a 25 °C; o asfalto pelo clima "Clear" |
| aderência da pista | fixa em 100% ("Optimum"), sem evolução da pista |
| horário | 14:00, com o tempo parado (0×) |
| IA | nível 100%, agressividade 0% (as opções do Ctrl+C) |
| ajudas | as mesmas em todas as sessões (as do CM no dia), e anotadas na primeira |

### 3. A ordem

- **C0 primeiro, e o C0 final por último.**
- **C1 a C4 em ordem sorteada com a semente 47:** `numpy.random.default_rng(47).permutation(["C1", "C2", "C3", "C4"])`, com o numpy 1.26.3, dá **C1, C4, C2, C3**.
- **A ordem completa:** C0, C1, C4, C2, C3 e C0 final.
- **Cada condição é uma sessão do jogo.** O jogo é fechado antes de cada troca de linha.

### 4. As voltas

- **9 voltas por condição** (6 no C0 final).
- **A volta de saída dos boxes e a primeira lançada ficam fora;** as 7 seguintes contam (4 no C0 final). Voltas além dessas são ignoradas.

### 5. A volta válida, e como cada coisa é medida

Cada volta passa pelo mesmo caminho do store v2 (`iter_laps`, `clean_lap`, `align_lap`, `resample_lap`), na geometria `0ed16f0dd2225990`. Uma volta é válida quando cumpre todas as condições abaixo:

- **com o tempo do jogo:** o tempo é o do cronômetro do jogo (`lap_time_from_grid`, como no store). A volta precisa estar completa: cobertura do alinhamento de 95% ou mais;
- **dentro do corredor do pedido 44** (`corridor_id 707d07029036abd6`):
  - a medida é a maior saída do corredor útil (`corridor_violation`, a mesma das linhas do pedido 46), e ela tem de ficar em **1,0 m ou menos**;
  - o jogo não pode marcar `offTrack` em nenhuma amostra;
  - **o 1,0 m saiu das 14 voltas da IA entre as 150 rotuladas,** antes do jogo: a maior saída delas fica entre 0,63 e 0,84 m, e nenhuma tem `offTrack`;
- **sem rodada:** em nenhuma amostra acima de 30 km/h o ângulo entre a velocidade do carro (X/Z) e a tangente da pista no ponto projetado passa de **45°**;
- **sem entrada nos boxes:** nenhuma amostra fica a 3 m ou menos da linha do `pit_lane.ai` estando, ao mesmo tempo, mais de 1 m fora do corredor útil;
- **com a IA dirigindo:** `isAIControlled` verdadeiro em todas as amostras da volta.

Volta que falha é descartada com o motivo.

### 6. Cada volta numa condição

- **O `trocar_linha.ps1` escreve uma linha** em `data/pista_teste/registro.csv` a cada troca, com a hora, a condição e o sha256.
- **Uma gravação pertence à condição** da última troca registrada antes do início dela (`startedAt` do `metadata.json`). Se o sha256 da troca não for o da condição, a gravação fica fora.
- **As voltas de uma condição** seguem a ordem do tempo, entre as gravações dela.
- **Volta sem condição clara fica fora,** com o motivo: por exemplo, uma gravação que começou antes da primeira troca.

### 7. O veredito de C3 e C4 contra C0

- **A medida:** a diferença das medianas dos tempos das voltas válidas, Cx − C0, com o C0 do começo.
- **O intervalo de 95%:** bootstrap com 10.000 reamostragens e semente 47 (`numpy.random.default_rng(47)`). Em cada reamostragem, as voltas de cada condição são sorteadas com reposição, e o intervalo vai dos percentis 2,5 a 97,5.

| veredito | regra |
|---|---|
| **mais rápida que a linha da IA** | o limite superior fica abaixo de 0 |
| **tão rápida quanto (não inferior)** | o limite superior fica em até +0,10 s, e a regra de cima não vale |
| **mais lenta** | o limite inferior passa de +0,10 s |
| **não conclusivo** | o resto |
| **não dirigível pela IA** | menos de 5 voltas válidas entre as 7 que contam. Vale antes das outras regras. Se a sessão acabou antes das 7 por um motivo que não é a IA (o tempo, o jogo travou), a condição fica **incompleta**, sai do veredito e é relatada |

### 8. A deriva

Se as medianas do C0 e do C0 final diferirem em mais de **0,15 s**, os vereditos viram "não conclusivo (deriva)". O C0 final também precisa de pelo menos 3 voltas válidas das 4 que contam. Sem elas, a deriva fica sem medida e os vereditos ficam como estão, com a nota.

### 9. Só relatados, fora do veredito

- **C1 contra C0:** o custo da codificação e da regra no jogo;
- **C2 contra C0:** a linha do Eduardo com a execução da IA;
- **C3 e C4 contra C1:** a mesma codificação;
- **a conferência da troca (pedido 47, E.1):** a distância mediana das posições gravadas até a linha da condição tem de ser menor que até a linha original, salvo no C0. **Se não for, a troca não pegou,** e a condição sai do veredito, com o motivo.

### 10. O medidor do tempo, calculado antes do jogo

O mesmo medidor do pedido 46: o simulador quase-estacionário, com o envelope das voltas reais (`data/ml/vehicle_envelope.json`, sha256 `3e31fd30e528281b…`). Arquivo: `data/pista_teste/medidor.json` e `docs/handoff/2026-11-07_47_linha-gerada-no-jogo_medidor.json`.

| condição | medidor | contra C0 | microssetor 36 | microssetor 0 | microssetor 1 |
|---|---:|---:|---:|---:|---:|
| C0 | 1:25,316 | — | — | — | — |
| C1 | 1:27,955 | +2,638 | −0,119 | +0,029 | +0,014 |
| C2 | 1:27,679 | +2,363 | −0,414 | +0,025 | +0,011 |
| C3 | 1:22,898 | −2,419 | −1,001 | 0,000 | −0,013 |
| C4 | 1:23,481 | −1,835 | −1,013 | 0,000 | −0,009 |

**A ordem no medidor:** C3, C4, C0, C2, C1. Ela é comparada com a do jogo depois, só para relatar.

O C0 é a linha do arquivo original, projetada na grade da geometria, e não a volta `#0013`. Por isso, ele dá 1:25,316, e não o 1:26,284 da volta.

### 11. O que se espera, escrito antes de rodar

- **C0:** perto das voltas da IA do pedido 46 com o mesmo carro (1:24,8 a 1:25,2). Um preset diferente do de 04/10 pode mudar o nível, mas o C0 é a referência dele mesmo.
- **C1 contra C0:** dentro de ±0,3 s. A codificação alisa a linha da IA em no máximo 1,4 m (mediana de 0,3 m), e a IA planeja a velocidade pelo raio dela. Uma linha mais lisa não deve custar muito. **O medidor prevê +2,6 s;** se o jogo der perto de zero, isso confirma que o custo da codificação no medidor vem do próprio medidor.
- **C3 e C4 contra C0:** o mais provável é "tão rápida quanto" ou "não conclusivo", entre −0,3 e +0,5 s. "Mais rápida" é possível, mas não é o que espero. **Por quê:**
  - o ganho no medidor se concentra no microssetor 36, perto da C10 (−1,0 s). O medidor supõe o carro no limite, e a IA não anda no limite do envelope;
  - a IA planeja a velocidade pelo raio da linha, e a linha gerada foi otimizada para outro modelo de carro;
  - a velocidade e os pedais gravados ficam os da linha original.
- **"Não dirigível"** é um risco nos trechos onde a linha nova chega a 10 m da original (C3: no máximo 10,8 m), se a IA frear tarde para um raio que ela não esperava.
- **C2:** mais lenta que C0. É uma volta humana 1,7 s mais lenta no cronômetro, e a linha dela passa 8 cm da borda da IA em 8 pontos.

### 12. A linha não vai para o coach

Neste pedido, a linha não vai para o coach (ADR 0009). Se ela passar, a decisão de usá-la é do Eduardo, num pedido próprio.

### 13. As sessões da cópia ficam fora do ML

- **A pista `vhe_interlagos_teste_m1`** começa com o prefixo de Interlagos. Por isso, `ml.data.recordings.list_sessions` a exclui explicitamente (`config.TEST_TRACK_NAMES`).
- **Com a exclusão,** as sessões da cópia ficam fora do inventário, do store v2, do treino do coach, da evolução e do Modelo 2. Só o resultado deste pedido as lê, pedindo explicitamente (`incluir_pistas_de_teste=True`).
- **O app instalado** foi gerado antes desta exclusão. Até o merge do pedido 47, o botão "Atualizar coach e relatório" e o `atualizar_coach` da pasta principal **não podem rodar** com as gravações da cópia na pasta do app.

### 14. Emenda antes do jogo (07/11, pedido 47, Parte C)

Escrita ao implementar a Parte E, **antes de qualquer sessão na cópia.** Ela não muda nenhum valor dos itens 1 a 13: só diz como cada um é aplicado.

- **O tempo da volta** (item 5) é o `lap_time_s` do store v2: `lap_time_from_grid` com `resample_lap(..., line_clock=True)`, o mesmo que dá 1:24,829 para a `#0013`. O `tempo_jogo_s` do store (`game_lap_time`, o cronômetro costurado na troca de volta) vai ao lado, só relatado. Na gravação de 04/10, os dois concordam em 3 ms ou menos nas 9 voltas da IA, e em até 0,06 s nas outras, salvo a volta de saída dos boxes.
- **Os boxes** (item 5): a volta também é inválida quando a marca de box do store (`pit_lap`) a acusa.
- **A volta de saída** (item 4) é a primeira volta de cada gravação. Se uma condição tiver duas gravações (o jogo reaberto), a primeira volta de cada uma fica fora. A primeira lançada fica fora uma vez só, por condição.
- **A última volta de uma gravação,** quando não está completa (cobertura abaixo de 95%), é a volta interrompida pelo fim da sessão. Ela não ocupa lugar entre as que contam.
- **O bootstrap** (item 7) usa um gerador novo, `numpy.random.default_rng(47)`, em cada comparação. Em cada reamostragem, ele sorteia primeiro as voltas da condição e depois as do C0.
- **"Incompleta"** (item 7): quando há menos de 5 válidas e menos de 7 voltas no lugar das que contam, o resultado marca "incompleta" para conferir nas anotações do Eduardo. Com as 7 voltas lá e menos de 5 válidas, é "não dirigível pela IA".
- **A conferência das medidas, em voltas antigas** (não da cópia): na gravação de 04/10, as 9 voltas da IA saem válidas (saída máxima do corredor de 0,84 m, ângulo máximo de 22°). As voltas humanas e as que passam pelos boxes saem inválidas, com o motivo.
- **Os caches do CSP** com o nome da cópia (`cache\ai_grids`, `ai_payloads`, `ai_alt_lanes`, na pasta do jogo) ficam fora da cópia. Os scripts não os apagam: o `trocar_linha.ps1` só os lista em `data/pista_teste/caches_csp.log`, a cada troca, e põe a data de agora no arquivo novo. Se o CSP reusar um cache velho, a conferência da troca (item 9) mostra.

## Consequências

- **O resultado vem do cronômetro do jogo, com a mesma execução.** É o medidor que faltava no pedido 46, mas mede só uma execução: a da IA do Assetto Corsa, com o planejamento de velocidade dela.
- **O teste custa no máximo 2 sessões de 45 minutos** do Eduardo, e a cópia ocupa 1,5 GB no disco do jogo até o `remover_copia.ps1`.
- **Um veredito "mais rápida" ou "tão rápida quanto"** cumpre o objetivo do TCC, para a IA do jogo. Ele não diz que um piloto humano faria a volta mais rápida com a linha.
- **Se o CSP guardar um cache da linha** que não muda com a troca, a conferência da troca (item 9) mostra isso, e a condição sai do veredito.

## Resultado

(preenchido depois do teste no jogo, sem mudar nada acima)
