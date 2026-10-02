# 0002 — Uma única geometria oficial da pista

- **Status:** aceita; implementação pendente
- **Data:** 2026-09-30
- **Decisor:** Eduardo

## Contexto

O app ao vivo e o pipeline de ML usam versões diferentes da pista. Isso apareceu de três formas:

1. **Réguas de distância diferentes.** O `s` gravado pelo app e o `s` do ML divergem até ~31 m. O ML usa a linha central suavizada; o app usa o polígono cru.
2. **Eixos de progresso diferentes.** O runtime calcula `p = distância / total` incluindo o segmento que fecha a volta. O vetor `p` do cache conta vértices. A diferença chega a 25 m.
3. **Linhas centrais diferentes.** A linha central crua do cache, usada pelo runtime, está deslocada ~11 m em 463–500 m e em 751–807 m. O `load_geometry` corrige isso, o runtime não. A divisa entre os trechos 10 e 11 do coach cai dentro dessa região.

O time da TUM na Indy Autonomous Challenge usa um único mapa (bordas, inclinação e linha de referência) compartilhado por localização, planejamento, controle e simulação, todos em coordenadas de Frenet (s, d).

## Decisão

- A geometria oficial é a carregada por `ml.track.geometry.load_geometry`, identificada por `geometry_id`.
- Runtime, coach, replay e ML passam a projetar posições nessa mesma geometria.
- Toda saída que contém `s` ou `p` registra o `geometry_id` usado.
- Dados de geometrias diferentes não são comparados (P2, já implementado no store).

## Consequências

- Muda o comportamento do runtime. Precisa de validação com voltas reais antes de ir para o app.
- As gravações antigas mantêm o `s` e o `p` originais. Quando necessário, são reprojetadas pela posição no mundo, o que a sessão 2 mostrou ser fiel: 0,0 m em 266 amostras nativas.
- É pré-requisito para integrar o modelo à interface.
