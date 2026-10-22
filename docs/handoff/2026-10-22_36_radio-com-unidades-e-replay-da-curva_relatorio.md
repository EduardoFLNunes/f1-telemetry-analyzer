# Relatório parcial do pedido 36: o rádio com as unidades, a freada da IA nos mapas e o replay da curva

- **Pedido:** `docs/prompts/2026-10-22_36_radio-com-unidades-e-replay-da-curva.md`. **Parcial:** parei no meio da Parte C, porque o limite de uso acabou.
- **Branch:** `etapa/radio-unidades-e-replay`, criada de `develop` (`5bb9f257`). Ainda sem merge em `develop`, e nada foi enviado ao remoto.
- **Commits:**
  - `eb60d8d7` Parte B: as decisões do pedido 35;
  - o commit deste relatório: "Relatório parcial do pedido 36".
- **Arquivos de handoff** (`docs/handoff/2026-10-22_36_radio-com-unidades-e-replay-da-curva_*`):
  - `_relatorio.md` (este arquivo);
  - `_m1.json`: a contagem oficial da M1;
  - `_log_antes.json`, `_log_depois.json` e `_medir_log.py`: o crescimento do log de acesso.

## Parte A: as conferências rápidas (feita)

1. **A M1 está em 5 de 5.** A sessão `2026-10-21_20-30-54` é a 5ª: ela tem 9 voltas, todas suas no store, e a guinada e as velocidades estão em 100% da grade. As outras quatro são 15/10 23:24, 17/10 01:02, 17/10 16:17 e 18/10 12:38.
2. **A volta de 1:26,875** (`2026-10-21_20-30-54#0017`) não tem sinal de corte de pista:
   - nenhuma amostra com 2 ou mais pneus fora;
   - nenhum `off_track`;
   - 2,8% fora do corredor útil. A volta limpa de referência do portão tem 4,7%;
   - a conferência completa, comparada com as voltas de 1:27,594 e 1:27,014, está em `docs/handoff/2026-10-22_35_rodada-do-coach_relatorio.md` (commit `5bb9f257`).

## Parte B: as decisões do pedido 35 (feita, `eb60d8d7`)

1. **A voz a 1,4x, aprovada:** a decisão está registrada em `docs/realidade_aumentada.md`, no relatório do pedido 35 (seção "Desvios") e numa seção nova, "Atualizações", no ADR 0021.
2. **A volta com rodada:**
   - a volta em que uma curva perde mais de 5 s contra a referência não conta para a análise, e o resumo dela não cita a curva;
   - é uma regra só do rádio (`PERDA_DE_RODADA_S`, em `core/radio/analise.py`);
   - o teste repete o caso de 21/10: a volta 5 (26,54 s na C12) sai da análise, e a análise passa a usar as voltas 9, 11 e 12.
3. **O log de acesso:**
   - o filtro está em `core/registro_de_acesso.py` e é ligado no arranque do backend. Ele tira do log os pedidos bem-sucedidos de `/api/live/volta/novos` e `/api/radio/mensagens`; os erros e as outras rotas continuam;
   - **a medida,** numa reprodução da gravação de 21/10 (backend na porta 8011, pastas isoladas):
     - antes, o log crescia **6,25 MB por hora**, com cerca de 15 pedidos de pontos novos por segundo e 5,4 de mensagens;
     - depois, essas duas rotas não escrevem nada (0 bytes por hora no mesmo teste);
   - **o log existente:** 3,53 GiB (3,8 GB). Compactado com gzip, nível 6, ocuparia **31,5 MiB** (0,9%). Não apaguei nem compactei nada; a decisão é sua.
4. **O CSV de anotações:**
   - no git, o arquivo já estava todo em LF;
   - a cópia de trabalho tinha 5 linhas com CRLF e 3 com LF. Normalizei para CRLF, a maioria;
   - o leitor do `atualizar_coach` e o do botão do app leem as mesmas 7 linhas antes e depois, e os testes que usam o arquivo passam;
   - o git não vê diferença de conteúdo, então não houve o que commitar. O CSV também não entra na chave do cache da rodada.

## Parte C: as unidades (começada, sem commit)

- **O texto novo está escrito** em `backend/core/radio/texto.py`, mas não foi commitado:
  - o tempo em décimos abaixo de 1 s e em segundos acima;
  - a volta como "1 minuto e 29,1 segundos";
  - a distância como "46 metros" ou "1,8 metro";
  - a velocidade como "mínima de 102 contra 128 quilômetros por hora".
- **Sete testes do rádio** ainda esperam o texto antigo e falham:
  - `test_frase_de_diferenca...`;
  - `test_frase_contra_a_sua_melhor...`;
  - `test_resumo_na_linha`;
  - `test_a_causa_principal...`;
  - `test_resumo_com_a_curva_de_maior_perda`;
  - `test_a_analise_so_curvas...`;
  - `test_a_voz_fica_com_a_primeira_fala_que_cabe`.

  É preciso atualizá-los e escrever o teste novo, de que todo número da fala tem a sua unidade.

## O que falta

- **Parte C:**
  - os testes;
  - a conferência de 13/10, 18/10 e 21/10: quantas mensagens perderam a causa por causa das unidades, antes e depois;
  - o cartão com as unidades. Os números das perdas na análise já ganharam o "s".
- **Parte D:** o minimapa que corta à direita (achar a causa) e a freada da IA nos dois mapas.
- **Parte E:** o replay da curva (a rota, a janela do jogo e a animação na tela Ao vivo) e as propostas de outras representações visuais.
- **Partes F, H e G:** os testes e as prévias, a documentação e a parada para o teste no jogo.

Nada precisa de decisão agora.
