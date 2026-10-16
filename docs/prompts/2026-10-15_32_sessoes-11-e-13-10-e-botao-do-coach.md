# Pedido 32 — As sessões de 11/10 e 13/10 no coach e na evolução, e um botão no app para atualizar o coach

**De:** Eduardo. **Data:** 15/10/2026.
**Tipo:** uma rodada do `atualizar_coach` (Parte A), e um botão no app que faz a mesma coisa (Parte B). Nenhum critério, regra do coach ou do store muda.

**Ordem:** este pedido vem antes do pedido 31. Só um chat trabalha por vez na pasta (ADR 0008).

## Contexto

1. **As anotações já foram feitas,** em 14/10, no commit `b359fd99` (relatório do pedido 28, seção "Pergunta no chat"):
   - `2026-10-11_14-16-34`, `2026-10-11_14-19-52` e `2026-10-13_19-24-10`;
   - como `humano` e `rss_formula_rss_3_v6_2026`.
2. **Confirmo o carro:** as três sessões foram com o `rss_formula_rss_3_v6_2026`.
3. **Ainda faltava rodar o `atualizar_coach`.** Por isso as sessões aparecem em "Gravações fora do relatório", na tela Sessões, e não estão no coach.
4. **O que a conferência da Coleta já mostrou:**
   - `2026-10-11_14-19-52`: 16 voltas válidas, melhor 1:27,594;
   - `2026-10-13_19-24-10`: 9 voltas válidas, melhor 1:29,768.

   A volta de 1:27,594 é mais rápida que a referência `minha_melhor` atual (1:29,389) e deve virar a referência.
5. **Por que o botão:** quero subir as sessões para o coach pelo próprio app, sem abrir o terminal. É o mesmo comando que hoje eu rodo à mão (seção 10 de `docs/coach_aprendizado.md`).

## Parte A — Rodada agora

1. **Antes de rodar:**
   - guarde a cópia de antes, fora do git, como no pedido 26;
   - confirme que o app instalado está fechado e que nenhuma sessão está sendo gravada.
2. **A volta de 1:27,594, antes de ela virar referência.** Relate:
   - o `tyres_out` e o `off_track` dela, ponto a ponto, e onde ficaram altos;
   - a diferença para a volta da IA por curva.

   Se houver sinal de corte de pista, relate e siga. Nenhuma regra muda; a decisão é minha depois.
3. **Rode o `atualizar_coach` padrão (incremental).**
4. **Relate o antes e depois,** como no pedido 26:
   - **as sessões novas:**
     - as voltas válidas, as que entram no coach e a mais rápida, por sessão;
     - o nome que cada uma ganha no relatório de evolução. O esperado é `2026-10-11` e `2026-10-13`;
   - **o coach:**
     - as duas referências;
     - quantas voltas suas;
     - o limiar;
     - o foco de cada modo;
   - **o store v2:** as voltas por origem;
   - **o critério do ADR 0015:** as três últimas sessões e a amplitude;
   - **a contagem oficial da M1:** continua 0 de 5, porque essas sessões foram gravadas pelo app antigo.
5. **Confira na tela Sessões** que as duas sessões saíram de "Gravações fora do relatório" e entraram em "Sessões no relatório".

## Parte B — O botão no app

**Onde:** na tela Sessões, na seção "Gravações fora do relatório".

1. **Para cada gravação fora do relatório, a origem:**
   - **"indicador de IA gravado"** (app 0.3.0 em diante): não precisa de anotação;
   - **"sem indicador":** precisa da minha confirmação de que todas as voltas foram minhas.
2. **Botão "Todas as voltas foram minhas",** só nas gravações sem indicador:
   - **antes de gravar,** abre uma confirmação com:
     - a sessão, a data e as voltas válidas pela conferência;
     - o carro: o gravado ou, quando não houver, o `rss_formula_rss_3_v6_2026` com o aviso "confirme o carro";
   - **ao confirmar,** acrescenta a linha em `docs/experimentos/anotacoes_de_sessao.csv` do repositório configurado:
     - no mesmo formato e com o fim de linha CRLF do arquivo;
     - com a observação "anotada pelo app em AAAA-MM-DD";
   - **depois,** mostra a linha gravada;
   - **sessão com voltas da IA ou misturada:** não tem botão de anotação. Ela fica como está.
   - **O commit da anotação** fica para o próximo pedido. O app avisa "anotação gravada, ainda sem commit".
3. **Botão "Atualizar coach e relatório":**
   - **o comando:** roda o mesmo `tools/atualizar_coach.py`, incremental, com o Python e a pasta do repositório configurado. O backend empacotado não tem tudo o que o comando usa, e o código continua num caminho só;
   - **quando fica ligado:**
     - o repositório está configurado;
     - nenhuma sessão está sendo gravada;
     - nenhuma outra rodada está em andamento. Use uma trava de execução que valha também para quem roda o comando à mão; se o comando não tiver uma, crie-a sem mudar o resultado;
   - **durante a rodada:** mostra os 7 passos, um a um, e guarda o log;
   - **no fim, um resumo:**
     - as sessões lidas;
     - as voltas que entraram, por sessão;
     - as referências antes e depois;
     - a contagem oficial da M1;
   - **depois:** o coach ao vivo recarrega o modelo (`reload_coach`), e as telas Sessões, Volta e Evolução leem de novo;
   - **se o comando parar numa trava,** a tela mostra a mensagem dele em português e não tenta de novo sozinha.
4. **Só o que já existe:** o botão não muda o comando, os critérios nem as travas.

## Parte C — Testes

- **o botão desligado:** com gravação em andamento, sem repositório ou com outra rodada;
- **a linha da anotação:** formato, CRLF e observação;
- **a rodada:** com um comando falso, o progresso, o resumo, a parada numa trava e a trava de execução;
- **o recarregamento do coach** depois da rodada;
- **as suítes:** a do backend e os testes do front continuam passando.

## Regras gerais

- **Nenhum critério, regra do coach, detector ou store muda.** Só entram as anotações e as saídas da rodada.
- **Não mexa no app instalado nem em arquivos do jogo.** Os testes da Parte B usam a pasta isolada, como nos pedidos 28 a 30.
- **Não instale nem atualize pacotes.**
- **Não gere instalador.** O botão entra no próximo instalador.
- **Não contorne nenhuma trava:** se algo parar, pare também e registre o motivo.
- **Branch e commits:** branch `etapa/sessoes-11-13-e-botao-do-coach`, commits por parte, merge em `develop`. Sem push.
- **Uma sessão de implementação por vez** (ADR 0008).
- **Relatório** em `docs/handoff/2026-10-15_32_sessoes-11-e-13-10-e-botao-do-coach_relatorio.md`, como manda o CLAUDE.md, com:
  - a checagem da volta de 1:27,594;
  - o antes e depois da Parte A;
  - as capturas do botão e da confirmação;
  - a saída dos testes e os commits.
- Se algo do contexto não bater com o repositório, pare e registre no relatório.
