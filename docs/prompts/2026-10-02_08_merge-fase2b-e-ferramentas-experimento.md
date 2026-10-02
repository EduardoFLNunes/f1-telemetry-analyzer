Eduardo aqui. Este pedido foi escrito junto com o Claude (Cowork), que faz a revisão e a arquitetura do projeto, e eu aprovo. O plano é meu. Pode executar.

Ótimo trabalho na Fase 2b, em especial o pré-registro da regra de decisão antes de rodar. O resultado negativo é aceito. Leia antes de começar:

- `docs/decisoes/0011-resultado-fase-2b-e-experimento-controlado.md`;
- `docs/experimentos/protocolo_sessao_controlada.md`.

## Parte A: incorporar a Fase 2b

1. Em `develop`, faça `git merge --no-ff etapa/fase2b-estimador-empirico` e rode a suíte completa.
2. Commite em `develop`:
   - `docs/prompts/` (pedidos 07 e 08);
   - `docs/decisoes/` (ADR 0011 e o índice);
   - `docs/experimentos/`.

   Mensagem: `docs: ADR 0011, protocolo da sessao controlada e pedidos 07-08`.
3. Crie a tag `handoff/fase2b` nesse commit.

## Parte B: ferramentas da sessão controlada (Fase 2c)

Branch `etapa/fase2c-ferramentas-experimento`, criada a partir de `handoff/fase2b`. Pode commitar nela; não faça merge.

Ainda não existe sessão gravada com o protocolo. Esta etapa só prepara as ferramentas e as testa com dados sintéticos.

### 1. Gerador do plano: `backend/ml/scripts/plan_controlled_session.py`

- **Entradas:** curva (padrão: Bico de Pato), condições (padrão: A, B, C e D do protocolo), voltas válidas por condição (padrão 8), voltas de aquecimento (padrão 5) e semente.
- **Saída:** blocos de 4 voltas, cada bloco com as quatro condições em ordem sorteada.
- **Arquivos:** grave `docs/experimentos/<data>_plano.csv`, com as colunas `ordem`, `bloco`, `condicao`, `freada` e `linha`, e uma versão em texto simples para imprimir ou deixar na tela durante a sessão.
- Registre a semente no CSV, para o plano poder ser refeito igual.

### 2. Análise: `backend/ml/scripts/analyze_controlled_session.py`

**Entradas:**

- o id da sessão gravada;
- o CSV do plano;
- uma lista opcional de voltas inválidas, anotadas pelo piloto.

**Passos:**

1. Leia a sessão pelo pipeline que já existe (leitor, store e alinhamento na grade de 2 m). Não crie leitor novo.
2. Case as voltas válidas com o plano, em ordem. Se o número de voltas não bater, pare e explique por quê, sem adivinhar.
3. Use a mesma definição de janela de curva da Fase 2b.
4. **Conferência da execução**, a parte mais importante. Para cada volta, meça o ponto de frenagem e a posição lateral na entrada, no ápice e na saída. Relate, por condição, a diferença real em relação à condição A. Se a diferença real ficar longe do pedido (10 m e 2 m), diga isso claramente.
5. **Efeitos medidos,** com IC 95 %:
   - efeito principal da frenagem: média de B e D menos média de A e C;
   - efeito principal da linha: média de C e D menos média de A e B;
   - interação: (D − C) − (B − A).

   Use bootstrap dentro dos blocos ou um modelo linear com efeito de bloco. Justifique a escolha no documento.
6. **Comparação com os estimadores.** Treine E1 a E4 da Fase 2b com todas as outras sessões, sem a sessão controlada. Peça a cada um a previsão para as diferenças reais medidas no passo 4 e compare com o efeito medido. Relate o erro de cada estimador e se o efeito medido cai dentro da faixa de 95 % de cada um.
7. **Saída:** `docs/experimentos/<data>_resultado.json` e `docs/experimentos/<data>_resultado.md`, em português simples.

### 3. Testes

Crie uma sessão sintética com efeitos conhecidos (por exemplo, frear 10 m antes custa 40 ms e mudar a linha custa 20 ms, sem interação) e com ruído de 20 ms por volta. Teste que:

- o gerador de plano é reproduzível pela semente e equilibrado: cada bloco tem as 4 condições;
- a análise recupera os efeitos conhecidos dentro do IC;
- a análise para com uma mensagem clara quando o número de voltas não bate com o plano.

### Restrições

- Só mexa em `backend/ml/scripts`, `backend/ml/validation`, `backend/tests` e `docs/`.
- Não mexa na interface, no `optimal.json` nem nas LSTMs.
- Não contorne nenhuma trava: se algo bloquear, pare e me avise.

### Entrega

Em `docs/handoff/`:

- o patch contra `handoff/fase2b`;
- a saída completa do pytest;
- um JSON com o que foi testado.

Gere também um plano de exemplo com a semente 2026 e deixe em `docs/experimentos/`, para eu conferir antes da sessão. No relatório, comece pela Parte A (`git log --oneline -5`, `git status`) e depois apresente a Parte B. Não envie nada ao remoto.
