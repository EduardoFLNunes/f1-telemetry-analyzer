# A rodada do coach com o teste no jogo de 21/10

- **Pedido:** no chat, depois do fechamento do pedido 35 ("realizei a última sessão, treine o coach"). A última sessão é a do teste no jogo, `2026-10-21_20-30-54` (21 voltas). Não há sessão mais nova, nem no repositório nem fora dele.
- **Branch:** `develop`. Só este relatório e a saída da rodada foram commitados; a rodada grava em `data/`, que fica fora do git. Nada foi enviado ao remoto.
- **Commit:** o deste relatório, "A rodada do coach com o teste no jogo de 21/10".
- **Arquivos de handoff** (`docs/handoff/2026-10-22_35_rodada-do-coach_*`):
  - `_relatorio.md` (este arquivo);
  - `_rodada.txt`: a saída inteira do `atualizar_coach`.

## Em resumo

1. **A rodada terminou com código 0,** das 00:16:50 às 00:34:41 (17,7 min). Comando, na pasta `backend`: `..\.venv\Scripts\python.exe tools\atualizar_coach.py` (o padrão, incremental, como no pedido 34).
2. **A sessão de 21/10 entrou:**
   - as 21 voltas foram rotuladas como suas pelo indicador do jogo;
   - 9 delas são válidas e entraram no store v2 e no relatório de evolução. As outras ficaram de fora pelas regras de sempre: o box, a volta incompleta ou a volta de saída;
   - as sessões de 10:51 (1 volta, parada nos boxes) e de 11:44 (2 voltas) também foram lidas, mas não têm voltas válidas para o coach.
3. **O coach treinado de novo:**
   - **121 voltas suas** no modelo (limpas, com o equipamento atual), nenhuma recusada;
   - **a sua melhor volta mudou:** 1:26,875 (`2026-10-21_20-30-54#0017`), contra 1:27,013 de 15/10. É o seu novo recorde;
   - **a volta da IA continua a mesma:** 1:24,828 (`2026-10-04_03-42-10#0013`), e é a referência padrão do app;
   - **o limiar:** mediana de 0,19 s por microssetor (de 0,06 a 0,85 s);
   - **o foco inicial contra a IA continua o mesmo:** os microssetores 3 (C01), 39 (C11) e 44 (C12). Contra a sua melhor, passou a ser 31, 33 e 37;
   - o modelo anterior ficou guardado em `data/reference_models/backup/vhe_interlagos.2026-10-22_00-18-09.antes-de-atualizar.json`.
4. **O store v2 passou em todas as checagens:**
   - 694 voltas (eram 685);
   - o período contra o cronômetro do jogo tem p99 de 3,33 ms;
   - a linha do jogo continua onde foi medida (pedido 34);
   - nenhuma volta passa pelo box nem aparece duas vezes, e há uma geometria só.
5. **A evolução:**

   | sessão | voltas | melhor | mediana | mediana menos a IA |
   |---|---|---|---|---|
   | 11/10 | 16 | 1:27,594 | 1:29,547 | 4,718 s |
   | 18/10 | 9 | 1:29,061 | 1:30,271 | 5,442 s |
   | **21/10** | **9** | **1:26,876** | **1:29,520** | **4,691 s** |

   - **21/10 é a sua melhor sessão até aqui:** a melhor volta e a menor distância mediana para a IA.
   - **A tendência da mediana** é de 0,248 s mais rápido por sessão.
   - **As 3 curvas em que você mais perde para a IA** são a C01 (0,83 s em 21/10), a C10 (0,57 s) e a C11 (0,56 s). A C14 caiu de 0,57 s em 18/10 para 0,17 s em 21/10, e a C05, de 0,50 para 0,16 s.
   - **O critério do ADR 0015** continua "ainda variando".

## O que muda no app

- **Se o app do repositório estiver aberto, feche e abra de novo,** para ele carregar o modelo novo com certeza.
- **O fantasma "Sua melhor"** (na tela Volta, na tela Ao vivo e nos mapas do jogo, quando a referência escolhida na Coleta é a sua melhor) passa a ser a volta de 1:26,875. Com a volta da IA, que é a padrão, nada muda.

## Para você decidir

- **A decisão aberta sobre a referência de 1:27,014** (ela tem 9,2% fora do corredor) perdeu o objeto: a sua melhor agora é a de 1:26,875. Não conferi o corredor da volta nova, porque a rodada não faz isso. Se quiser, confiro.
- **As outras decisões do pedido 35 continuam abertas:**
  - a voz a 1,4x;
  - a volta com rodada na análise do rádio;
  - o log de acesso do backend;
  - a pasta `recordings/` no `.gitignore`.
