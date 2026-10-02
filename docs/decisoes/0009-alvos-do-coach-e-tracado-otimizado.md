# 0009 — O traçado otimizado não vira alvo do coach enquanto for mais lento que voltas reais

- **Status:** aceita
- **Data:** 2026-10-02
- **Decisor:** Eduardo

## Contexto

Ao regravar `data/reference_models/vhe_interlagos.optimal.json` com o novo mapeamento do coach, o `export_coaching` recusou a gravação. Ele só grava quando o traçado otimizado é mais rápido que todas as voltas gravadas, comparando tudo no mesmo simulador:

| | store atual (122 voltas) | store anterior à Fase 1 (113 voltas) |
|---|---|---|
| traçado otimizado | 85,109 s | 85,109 s |
| volta gravada mais rápida | 84,822 s | 84,822 s |
| voltas mais rápidas que o traçado | 43 | 40 |

- A recusa não vem da Fase 1: com as 113 voltas antigas o resultado é o mesmo. O `optimal.json` de 25/08 foi gravado com `--force` ou antes de essa checagem existir.
- O arquivo atual ainda usa o mapeamento antigo, com bordas de trecho deslocadas cerca de 14 m na mediana.
- Ferramentas comerciais de coaching (Coach Dave Delta, Garage 61) comparam o piloto com voltas reais. No artigo de Shehadeh et al. (2026), a trajetória real de especialista foi o melhor ponto de partida para o otimizador.

## Decisão

1. Não usar `--force`. O `optimal.json` atual fica como está, com backup em `data/ml/_backup_pre_coach_mapeamento/`.
2. Registrar como limitação conhecida: até a próxima etapa do coach, os alvos de posição exibidos no app seguem o mapeamento antigo.
3. Na próxima etapa do coach, os alvos (ponto de frenagem e velocidade mínima por trecho) passam a vir das **voltas reais mais rápidas do próprio piloto**, e não do traçado otimizado. Os alvos usam voltas completas, nunca a soma dos melhores trechos (ADR 0005), e continuam sem segundos por trecho (ADR 0004).
4. A busca evolutiva só volta a gerar alvos depois que o simulador corrigido por dados passar no teste de "prever zero". Quando voltar, ela começa a partir das voltas reais mais rápidas.

## Consequências

- O app continua com alvos deslocados até a próxima etapa do coach. A alternativa (`--force`) corrigiria as posições, mas manteria um alvo que o piloto já superou em 43 voltas e contornaria uma trava de segurança.
- O otimizador deixa de ser a fonte de "verdade" do coach. Ele passa a ser uma ferramenta de refinamento, como nos artigos.
