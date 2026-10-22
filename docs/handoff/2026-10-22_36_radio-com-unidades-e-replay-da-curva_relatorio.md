# Relatório do pedido 36 (parado na Parte G): o rádio com as unidades, a freada da IA nos mapas e o replay da curva

- **Pedido:** `docs/prompts/2026-10-22_36_radio-com-unidades-e-replay-da-curva.md`, retomado pelo pedido de continuar "da Parte C até a parada da Parte G". **Parado na Parte G, como o pedido manda:** o teste no jogo é seu.
- **Branch:** `etapa/radio-unidades-e-replay`, criada de `develop` (`5bb9f257`). Nada foi enviado ao remoto.
- **Commits:**
  - `eb60d8d7` Pedido 36, Parte B: as decisões do pedido 35;
  - `de1b5af4` Relatório parcial do pedido 36 (parado pelo limite de uso);
  - `6086fdeb` docs: pedido 36;
  - `33198247` Pedido 36, Parte C: todo número falado com a sua unidade;
  - `11ab0ea0` Pedido 36, Parte D: o minimapa na parte visível da janela e a freada da IA nos mapas;
  - `2d1b5d81` Pedido 36, Parte E no backend: o replay da curva;
  - `19282168` Pedido 36, Parte E no front e no jogo: o replay da curva;
  - `4d625418` Pedido 36, Parte H: a documentação;
  - o commit deste relatório e do handoff, e o merge em `develop` (os hashes estão no fim do chat e no `git log`).
- **Arquivos de handoff** (`docs/handoff/2026-10-22_36_radio-com-unidades-e-replay-da-curva_*`):
  - `_relatorio.md` (este arquivo) e `_patch.diff` (a branch inteira contra `develop`);
  - **Parte A:** `_m1.json`;
  - **Parte B:** `_log_antes.json`, `_log_depois.json`, `_medir_log.py`, `_log_compactado.txt`;
  - **o log de 3,8 GB:** `_log_varredura.json` e `_varrer_log.py`;
  - **Parte C:** `_radio_antes_{13-10,18-10,21-10}.json`, `_radio_depois_{...}.json`, `_causas_antes_depois.json`, `_radio_offline.py` e `_texto_antes.py` (o texto de antes das unidades, para a rodada "antes");
  - **Parte D:** `_minimapa_folha.png`, `_minimapa_com_freadas.json`, `_minimapa_previa.py`, `_aproximado_c04.png`, `_aproximado_previa.py`;
  - **Parte E:** `_radio_replay_21-10.json`, `_replay_folha.png`, `_replay_previa.py`, `_replay_tempos.json`, `_medir_replay.py`.

## 1. O git status ao retomar

Além do `backend/core/radio/texto.py` (o texto novo), estavam fora do git:

- o próprio pedido 36 (`docs/prompts/...`), que commitei em `6086fdeb`;
- a pasta `recordings/` na raiz, que não é deste pedido e ficou como estava.

Em `develop` há um stash antigo ("Organização das 3 visões"), que não mexi.

## 2. O `logs\backend.log` de 3,8 GB

**O que o ocupa** (varredura completa, 38,6 milhões de linhas, `_log_varredura.json`):

- **95% (cerca de 3,6 GB) é um único erro do asyncio, em 04/10, das 02:24 às 13:51.** São 4,8 milhões de repetições de `NameError: free variable 'outer' referenced before assignment in enclosing scope`, no `gather._done_callback`, cada uma com o traceback de 7 linhas. É o laço de um `asyncio.gather` que se repetiu a cada poucos milissegundos durante 11 horas. Ele não voltou depois de 04/10;
- o log de acesso das duas rotas frequentes é cerca de 0,3% (o de `/api/live/volta/novos` só existe desde 21/10);
- o resto: o receptor de oponentes (0,2%), os outros registros e os tracebacks esparsos;
- **por dia:** 04/10, 3.601 MB; 21/10, o dia do teste no jogo, 10,7 MB.

**Quem escreve:** o `desktop/main.js` (linha 742) acrescenta a saída do backend em `logs/backend.log` com `createWriteStream` em modo de acréscimo, sem girar nunca. Um dia de erro em laço basta para encher o disco.

**Proposta de rotação** (não implementada, sem pedido):

- no arranque do app, e depois a cada hora, se `backend.log` passar de **20 MB**, ele vira `backend.1.log`, o `.1` vira `.2`, e assim até **5 arquivos** (`backend.1.log` a `backend.5.log`). O mais velho sai;
- o máximo no disco: cerca de 120 MB (o atual mais 5 × 20 MB);
- com o registro de acesso calado (Parte B), 20 MB são cerca de 2 dias de uso normal; um erro em laço como o de 04/10 encheria os 20 MB em minutos, mas o disco ficaria nos 120 MB;
- o arquivo de 3,8 GB não foi apagado nem compactado. Compactado (gzip, nível 6), ocuparia 31,5 MiB. A decisão é sua.

## Parte A: as conferências rápidas (feita)

1. **A M1 está em 5 de 5.** A sessão `2026-10-21_20-30-54` é a 5ª: 9 voltas, todas suas no store, com a guinada e as velocidades em 100% da grade. As outras são 15/10 23:24, 17/10 01:02, 17/10 16:17 e 18/10 12:38.
2. **A volta de 1:26,875** (`2026-10-21_20-30-54#0017`) não tem sinal de corte de pista: nenhuma amostra com 2 ou mais pneus fora, nenhum `off_track` e 2,8% fora do corredor útil (a volta limpa de referência do portão tem 4,7%). A conferência completa está em `docs/handoff/2026-10-22_35_rodada-do-coach_relatorio.md`.

## Parte B: as decisões do pedido 35 (feita, `eb60d8d7`)

1. **A voz a 1,4x, aprovada:** registrada em `docs/realidade_aumentada.md`, no relatório do pedido 35 ("Desvios") e no ADR 0021 ("Atualizações").
2. **A volta com rodada:** a volta em que uma curva perde mais de 5 s contra a referência não conta para a análise, e o resumo dela não cita a curva. É uma regra só do rádio (`PERDA_DE_RODADA_S`, `core/radio/analise.py`). Em 21/10, a volta 5 (26,54 s na C12) sai, e a primeira análise passa a usar as voltas 9, 11 e 13.
3. **O log de acesso:** o filtro (`core/registro_de_acesso.py`) tira do log os pedidos bem-sucedidos de `/api/live/volta/novos` e `/api/radio/mensagens`. Numa reprodução de 21/10 (porta 8011, pastas isoladas): **antes, 6,25 MB por hora** (cerca de 15 pedidos de pontos novos e 5,4 de mensagens por segundo); **depois, 0** nessas rotas. Os erros e as outras rotas continuam.
4. **O CSV de anotações:** no git, já estava todo em LF; a cópia de trabalho (5 linhas CRLF, 3 LF) foi normalizada para CRLF. Os dois leitores leem as mesmas 7 linhas, e o git não vê diferença de conteúdo.

## Parte C: as unidades (feita, `33198247`)

1. **O texto** (`backend/core/radio/texto.py`):

   | o quê | antes | agora |
   |---|---|---|
   | tempo abaixo de 1 s | "0,7" | "7 décimos" |
   | tempo de 1 s para cima | "1,25 atrás" | "1,3 segundo atrás da IA" |
   | tempo da volta | "1 minuto e 40,1" | "1 minuto e 40,1 segundos" |
   | distância | "Freia 46 metros antes." | "Freia 46 metros antes da IA." |
   | traçado | "8 metros mais à direita" | "8 metros mais à direita que a IA"; abaixo de 2 m, "1,8 metro" |
   | mínima | "Mínima 102 contra 128." | "Mínima de 102 contra 128 quilômetros por hora." |

   **A unidade nunca sai.** Quando a fala não cabe, saem, em ordem: o lado da curva (na frase do coach), a segunda curva e a abertura (na análise), a segunda causa, o "contra quem" e, por último, a primeira causa.
2. **O cartão:** já tinha as unidades; as perdas das linhas da análise ganharam o "s" ("1,04 s · 1,06 s · 0,22 s").
3. **Quantas mensagens perderam a causa por causa das unidades** (as 3 sessões passadas de novo pelo rádio, com o texto de antes e o de agora; `_causas_antes_depois.json`). Contam as mensagens com causa: a frase do coach com causa, o resumo com a curva que mais perdeu e a análise.

   | sessão | antes | depois |
   |---|---|---|
   | 13/10 | 0 de 12 | 2 de 12 |
   | 18/10 | 0 de 13 | 2 de 13 |
   | 21/10 | 0 de 18 | 6 de 18 |

   **Todas as 10 são frases do coach da C11 com a mínima.** "Curva 11: 1,3 segundo atrás. Mínima de 64 contra 94 quilômetros por hora." dura de 6,8 a 7,2 s, e o limite da frase do coach é 6,6 s. A voz diz só "Curva 11, esquerda: 1,3 segundo atrás da IA.". Os resumos e as análises não perderam nada.

   **Proposta (decisão sua):** subir o limite da frase do coach de 6,6 para cerca de 7,3 s. As 10 voltariam com a causa; a entrega continua só quando a fala inteira cabe no que resta da janela.
4. **As falas novas** nas 3 sessões estão em `_radio_depois_*.json`. Exemplos:
   - "Curva 12: 1,9 segundo atrás da IA. Freia 54 metros antes da IA." (6,2 s);
   - "Volta 8: 4,2 segundos atrás da IA. Mais perdeu na curva 1: 7 décimos." (6,7 s);
   - "Análise das voltas 9, 12 e 13. Curva 1: perde 9 décimos por volta. Freia 46 metros antes da IA." (8,7 s);
   - "Voltas 16 a 18. Curva 1: perde 1,2 segundo por volta. Passa 8 metros mais à direita que a IA." (8,3 s).
5. **Os testes:** os 7 que esperavam o texto antigo foram atualizados, e o teste novo (`test_todo_numero_falado_tem_a_unidade_em_todos_os_tipos_de_mensagem`) passa todas as variantes de todos os tipos por um leitor que acusa número sem unidade.

## Parte D: o minimapa e a freada da IA (feita, `11ab0ea0`)

1. **O corte à direita:** fora do jogo, não se reproduz. As causas possíveis:
   - a janela passando da borda da tela;
   - o recorte padrão do ImGui;
   - o espaçamento interno da janela.

   **A correção cobre as três:** os mapas (e o replay) se encaixam na parte visível da janela (`ui.windowPos` e o tamanho da tela do jogo) e desenham com o recorte da janela inteira (`ui.pushClipRect`). Cada janela escreve uma vez as suas medidas no log do CSP (`[radio_engenheiro] minimapa: janela 300 x 300 em ...; tela ...; visível de ... a ...`), para confirmar a causa no jogo.

   **As prévias** (`_minimapa_folha.png`): 200 × 200, 300 × 300, 640 × 640, 480 × 300, 300 × 480 e 300 × 300 com 40 px fora da tela. A pista cabe inteira em todas.
2. **A freada da IA** pela regra do relatório de evolução (`braking_point`):
   - **no minimapa,** só a da próxima curva: uma marca curta atravessando a pista, na cor do fantasma;
   - **no mapa aproximado,** todas as da janela, com o rótulo "freada da IA" (`_aproximado_c04.png`, na C04);
   - **a conferência:** a IA freia nas mesmas 8 curvas do relatório de evolução (C01, C02, C04, C06, C07, C08, C10 e C12), nos mesmos pontos (`lap_corner_features` do relatório; os dados das marcas estão em `_minimapa_com_freadas.json`).

## Parte E: o replay da curva (feita, `2d1b5d81` e `19282168`)

1. **Os dados** (`backend/core/radio/replay.py`, rota `GET /api/radio/replay/{id}`): as duas linhas ("você" e "IA (referência)") com o tempo de cada carro desde a mesma entrada, as freadas com a distância, as mínimas em km/h, o traçado com a distância e o lado, e a perda na curva. Só as grades que o rádio já tem.
2. **Qual volta:**
   - **na análise,** a das 3 com a perda na curva mais perto da mediana. Em 21/10: a primeira análise (voltas 9, 11 e 13) mostra a volta 13 na C01 e a 11 na C12; a segunda (16, 17 e 18) mostra a 17 na C01 e a 16 na C10;
   - **na frase do coach,** a volta em que ela saiu (a ao vivo, ou a que acabou de fechar, se a entrega já passou da linha).
3. **A janela no jogo, "Replay da curva"** (versão 0.4.0 do app):
   - **na reta,** junto com a fala; some quando a janela de rádio acaba (o backend manda o `restaS`, o que resta da janela na entrega);
   - **nos boxes ou com o jogo pausado,** a última análise, em repetição, com a janela 1,6 vez maior;
   - o desenho sobre a `pista_detalhada.png`, com a mesma câmera da tela Ao vivo (a entrada para cima).
4. **Na tela Ao vivo:** a mesma animação sob o cartão da análise e da frase do coach com causa, com o botão "Repetir o replay".
5. **Os rótulos não se cobrem:** na primeira prévia, os rótulos do ápice se amontoavam, e o da freada da C12 saía pela direita. Agora cada rótulo procura um lugar livre em volta do seu ponto, sem cobrir outro rótulo, os carros e as marcas, e, se precisar ir mais longe, ganha um fio até o ponto. A mesma regra no Lua e no front (`QuadroDeRotulos`, com teste).
6. **As prévias** (`_replay_folha.png`): 3 curvas reais de 21/10, desenhadas por um HTML que repete as contas da janela do jogo:
   - a C01 da segunda análise (volta 17), no começo e no meio da animação;
   - a C10 da segunda análise (volta 16);
   - a C12 da primeira análise (volta 11).
7. **Os 7,9 m da C01 da segunda análise batem:** a seta vai de um ponto a outro com 7,941 m, e cada ponto está a 0,0 m da sua linha. É o mesmo "Passa 8 metros mais à direita que a IA." da fala.
8. **O custo:**
   - **no backend:** montar o replay leva de 0,9 a 1,4 ms numa frase do coach e de 2,7 a 3,3 ms numa análise com 2 curvas (os 9 replays de 21/10, `_replay_tempos.json`), uma vez por mensagem. A rota entrega cerca de 8 KB (frase) e 20 KB (análise);
   - **no jogo:** o FPS entra no registro de 10 s, com "replay ligado" ou "desligado". A medida é da Parte G.
9. **O que não fiz:** a conferência ponta a ponta numa janela de teste do app (a tela Ao vivo com o replay de verdade). O front passa no `tsc` e nos testes, mas o desenho no canvas só foi visto pelas prévias. O teste da Parte G vai mostrá-lo.

### Outras representações visuais (propostas, nada implementado)

1. **A velocidade ao longo da curva:** as duas curvas de velocidade pela distância, com a freada e a mínima marcadas. Mostra de uma vez se o tempo vai embora na freada, no ápice ou na saída.
   ```
   km/h
   250 ─╲__                        __╱─  IA
        ╲ ╲__      ____        __╱
   150   ╲   ╲____╱    ╲______╱        você
          ↑freada   ↑mínima 102 / 128
   ```
2. **A diferença acumulada dentro da curva:** uma linha que sobe quando você perde e desce quando ganha, do começo ao fim do trecho. A perda de 1,21 s da C01 ficaria dividida entre a freada (antes do ápice) e a saída.
   ```
   +1,2 s ┤                   ______
          ┤          ________╱
      0   ┼─────────╱
            freada   ápice   saída
   ```
3. **A faixa do pedal sincronizada:** sob o replay, duas faixas (você e IA) com o freio em vermelho, o parcial em amarelo e o acelerador cheio em verde, andando com os carros. Mostra o "acelera 14 metros depois" sem número.
   ```
   você │████▓▓▓▓░░░░░░░░▒▒▒▒████████│
   IA   │███████▓▓░░░░░▒▒██████████████│
   ```
4. **A grade da sessão:** uma tabela de curvas por volta, colorida pela perda, na tela Ao vivo ou na Sessões. Mostra se a curva citada melhorou nas voltas seguintes (a avaliação do Modelo 2).
   ```
          C01  C04  C10  C11  C12
   V16    ██   ░░   ▓▓   ░░   ░░
   V17    ██   ░░   ░░   ▓▓   ░░
   V18    ▓▓   ░░   ▓▓   ░░   ░░
   ```

## Parte F: os testes e as conferências

- **Backend:** `pytest tests` (na pasta `backend`): **794 testes, todos passando** (em 8 min 9 s; eram 786 antes do pedido). O `test_radio.py` tem 29 testes; os novos cobrem a volta com rodada, o log de acesso, as unidades, a freada da IA, os dados do replay, a volta mais perto da mediana e a rota.
- **Front:** `vitest run`: **189 testes em 17 arquivos, todos passando** (os 5 do replay, com o encaixe dos rótulos). `tsc --noEmit`: sem erro.
- **A conferência do Lua** (`tools/csp_app/conferir_lua.py`): 0 erros de léxico, os blocos fechados, 45 chamadas da API e 11 métodos, todos no `lib.lua` do SDK do CSP instalado.
- **O build do front** (`frontend/dist`) foi refeito, para o app do repositório mostrar o replay na tela Ao vivo no teste da Parte G.

## Parte H: a documentação (feita, `4d625418`)

- `docs/realidade_aumentada.md`: as unidades com os exemplos e a ordem do corte (seção 2.6), as causas perdidas, os exemplos das seções 2.1 a 2.3 com as falas novas, o encaixe na janela, a freada da IA nos dois mapas, o replay da curva (seção 5.4: o que mostra, de onde vem cada dado, quando aparece e o custo medido no backend), a rota nova e o registro;
- ADR 0021: a linha de atualização com o replay e as marcas de freada (a da rodada já estava, da Parte B);
- `docs/dashboard_inventario.md`: "O que o pedido 36 entregou", no fim da seção 7.

## Parte G: o teste no jogo (parado aqui; é com você)

1. **Feche o jogo e o app instalado.**
2. **Instale o app do jogo** (versão 0.4.0, com a janela nova):
   ```
   powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Dokas\Desktop\f1-telemetry-analyzer\tools\csp_app\instalar.ps1
   ```
3. **Abra o app pelo repositório** (o backend com o código novo), num PowerShell:
   ```
   $env:AT_BACKEND_USE_PYTHON_RUNNER='true'; cd C:\Users\Dokas\Desktop\f1-telemetry-analyzer\desktop; npm.cmd run desktop:prod:autostart
   ```
4. **No jogo, ligue as 4 janelas** na barra de apps: "Rádio", "Minimapa", "Mapa aproximado" e "Replay da curva". Ponha o replay num canto, sem cobrir o centro.
5. **Na tela Sistema, "Mandar mensagem de teste":** o cartão e a voz no jogo.
6. **Pelo menos 8 voltas sem a IA, com uma ida aos boxes** depois da primeira análise (a 3ª volta válida). Para o FPS de cada janela, desligue o replay por 2 ou 3 voltas e ligue de novo, e deixe a tela Ao vivo aberta no app.
7. **Avise "testei o rádio com o replay no jogo".** Eu leio, sem mudar nada, o registro do rádio, as linhas `[radio_engenheiro]` do log do CSP (a voz, as medidas das janelas e o FPS com cada uma ligada e desligada) e os replays entregues, e completo este relatório e `docs/realidade_aumentada.md`.

## O que precisa de decisão sua

1. **O limite da frase do coach:** subir de 6,6 para cerca de 7,3 s, para a causa da C11 voltar (Parte C.3).
2. **O log de 3,8 GB:** apagar, compactar ou guardar; e se a rotação proposta (20 MB, 5 arquivos) entra num pedido.
