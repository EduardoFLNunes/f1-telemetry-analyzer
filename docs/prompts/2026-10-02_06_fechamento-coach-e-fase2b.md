Eduardo aqui. Este pedido foi escrito junto com o Claude (Cowork), que faz a revisão e a arquitetura do projeto, e eu aprovo. O plano é meu. Pode executar.

Obrigado pelo relatório. Você fez certo em parar no passo 5. Antes de começar, leia os dois ADRs novos: `docs/decisoes/0009-alvos-do-coach-e-tracado-otimizado.md` e `docs/decisoes/0010-fase-2b-ajustada-pelos-artigos.md`.

## Parte A: fechar a etapa do coach (em `develop`)

1. **Passo 5: opção (b).** Não use `--force` e não regrave o `optimal.json`. O motivo está no ADR 0009.
2. **Handoff.** Salve a saída completa do pytest da etapa em `docs/handoff/2026-10-02_coach_integracao_pytest.txt`.
3. **.gitignore.** Acrescente a linha `docs/estudos/*.mp4`. O vídeo de estudo que está nessa pasta não deve entrar no git.
4. **Commit.** Commite em `develop`:
   - `docs/prompts/`;
   - `docs/decisoes/` (ADRs 0009 e 0010 e o índice atualizado);
   - o pytest do passo 2;
   - o `.gitignore`.

   Mensagem: `docs: ADR 0009-0010, pedidos e handoff da integracao do coach`.
5. **Tag.** Crie a tag `handoff/coach-mapeamento` nesse commit.
6. **Limpeza da worktree antiga:**
   - remova a worktree `.claude/worktrees/elastic-kepler-a8182e` com `git worktree remove` (as alterações dela já estão em `develop`, conferidas por SHA-256). Se o git pedir `--force` só por causa dos arquivos ignorados que foram copiados para lá (`data/ml`, `data/cache/tracks`), pode usar;
   - apague a branch `fix/coach-mapeamento-s`, que não tem commits próprios;
   - sobre a branch `claude/elastic-kepler-a8182e` (aponta para `44f6d9d0`): rode `git branch -a --contains 44f6d9d0`. Se o commit estiver contido em `develop` ou em alguma branch remota, apague a branch local. Se não estiver, não apague e me avise.
7. **Stash.** Deixe o `stash@{0}` como está.

## Parte B: Fase 2b, estimador empírico (ADRs 0005, 0006 e 0010)

**Onde trabalhar:** branch `etapa/fase2b-estimador-empirico`, criada a partir de `handoff/coach-mapeamento`, na pasta principal (ADR 0008). Pode commitar nessa branch; não faça merge em `develop`.

**Pergunta:** usando só as voltas do próprio piloto, sem depender do simulador, dá para prever a diferença de tempo de uma correção local melhor do que "prever ganho zero"?

**Unidade de análise:**

- Janela de curva: do início da frenagem até o fim da reta seguinte, ou seja, o próximo ponto de frenagem. Use as curvas de `ml/track/corners.py`.
- Relate quantas janelas existem por volta e o comprimento de cada uma.

**Pares:** os mesmos filtros de comparabilidade da Fase 2:

- mesma sessão;
- combustível com até 5 L de diferença;
- velocidade de entrada na janela com até 3 km/h de diferença;
- sem incidente.

**Alvo:** ΔT na janela = tempo da volta B − tempo da volta A naquela janela.

**Entradas (diferenças acionáveis entre B e A na janela):**

- ponto de frenagem (m);
- posição lateral na entrada, no ápice e na saída (m), na convenção do ML (positivo à esquerda; use `to_left_positive` onde precisar);
- ponto de retomada do acelerador (m).

**Estimadores:**

| | Estimador | Incerteza |
|---|---|---|
| E0 | prever zero | — |
| E1 | simulador calibrado na janela | — |
| E2 | regressão linear regularizada (ridge); o efeito pode variar por curva | quantis dos resíduos nas sessões de treino |
| E3 | KNN de regressão, com k escolhido só nas sessões de treino | quantis dos resíduos nas sessões de treino |
| E4 | Processo Gaussiano (kernel RBF, entradas padronizadas) | desvio previsto pelo modelo |
| E2-teto | E2 + velocidades mínima e de saída | só como teto, nunca candidato |

- Sem redes neurais nesta fase.
- Use `scikit-learn` se já estiver no ambiente. Se não estiver, me avise antes de instalar.

**Abstenção ("não conclusivo"):**

- quando a faixa de 95 % do estimador inclui zero;
- quando alguma entrada do par de teste está fora da faixa de 2,5 % a 97,5 % das diferenças vistas nas sessões de treino para aquela curva (fora da distribuição). Conte esses casos à parte.

**Validação (ADR 0006):**

- uma sessão inteira fora a cada rodada; todos os ajustes (incluindo k, regularização e hiperparâmetros do GP) só com as sessões de treino;
- critérios de aprovação exatamente como no ADR 0006, fixados antes de rodar;
- MAE, RMSE, viés, Spearman, concordância de sinal, skill contra prever zero com IC 95 % por bootstrap agrupado por sessão;
- resultados também sem as duas sessões dominantes (2026-08-09_19-20-59 e 2026-06-20_13-13-02);
- curva risco × cobertura de cada estimador com incerteza;
- calibração: fração dos ΔT reais dentro da faixa de 95 % de cada estimador.

**Restrições:**

- Só mexa em `backend/ml/validation`, `backend/ml/scripts`, `backend/tests` e `docs/`.
- Não retreine as LSTMs, não mexa na interface, não toque no `optimal.json` e não use soma dos melhores trechos.
- Se nenhum estimador passar nos critérios, isso é um resultado válido: relate e pare.
- Não contorne nenhuma trava: se algo bloquear, pare e me avise.

**Entrega em `docs/handoff/`:**

- `2026-10-0X_fase2b.patch`, contra `handoff/coach-mapeamento`;
- `2026-10-0X_fase2b_testes.txt`, com a saída completa do pytest;
- `2026-10-0X_fase2b_resultados.json`, com os hashes dos dados usados (ADR 0007).

Escreva também `docs/fase2b_estimador_empirico.md` em português simples: o que foi feito, como, resultados e limitações.

**Relatório final:** comece pela Parte A (`git log --oneline -5`, `git status`, o que aconteceu na limpeza) e depois apresente a Parte B. Não envie nada ao remoto.
