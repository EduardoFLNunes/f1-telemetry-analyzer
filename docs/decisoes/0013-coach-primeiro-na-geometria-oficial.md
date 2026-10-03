# 0013 — O coach é o primeiro a usar a geometria oficial, e o modelo dele sai da posição no mundo

- **Status:** aceita; implementa parte do ADR 0002
- **Data:** 2026-10-03
- **Decisor:** Eduardo

## Contexto

O relatório da Parte C (coach honesto, `docs/coach_referencia_real.md`) mostrou que o modelo do coach depende do progresso `p` gravado pelo runtime, e isso causa três problemas medidos:

1. **O modelo em uso mistura três réguas.** Dos 60 alvos mais a melhor volta, 34 vêm de sessões gravadas com o cache atual do app, 9 do `InterlagosPitAccessAsphaltMergeFix` e 18 de sessões sem cache registrado. Na Fase 1, o `s` gravado nesses grupos divergiu até ~31 m.
2. **As 56 voltas de 09/08 nunca entraram no coach.** Essas gravações não têm `p`, e o coach só sabe recortar microsetores por `p`.
3. **Escolher um cache só deixaria quase tudo de fora.** Das sessões de Interlagos, 60 foram gravadas com o `MergeFix`, só 7 com o cache que o app usa hoje e 3 sem registro. O coach compara o `p` ao vivo, calculado com o cache atual, então só essas 7 seriam comparáveis.

O ADR 0002 já decidiu que existe uma geometria oficial, a de `ml.track.geometry.load_geometry`, e que runtime, coach, replay e ML devem projetar nela. Faltava decidir por onde começar.

## Decisão

- **O coach migra primeiro.** Ele calcula `s` e `d` a partir da posição no mundo (`world_x`, `world_z`) na geometria oficial, tanto ao vivo quanto no treino do modelo. Ele deixa de usar o `p` gravado ou o `p` do runtime.
- **Os microsetores do coach passam a ser os mesmos do ML:** 60 trechos de mesma distância na geometria oficial. O "setor 22" do coach e o microsetor 22 da análise passam a ser o mesmo trecho.
- **O app não importa o pacote `ml`.** O `ml` exporta a geometria oficial (grade, normais e fronteiras dos microsetores) num JSON com o `geometry_id`, e o backend só lê esse arquivo. É o mesmo padrão do traçado exportado.
- **O modelo do coach registra o `geometry_id`.** Se a geometria carregada for diferente da do modelo, o coach fica em silêncio e avisa no log, como já faz com um modelo antigo.
- **Todas as voltas válidas entram no modelo,** de qualquer cache, porque a posição no mundo vale para todas.
- Mapa, painel ao vivo e replay continuam como estão por enquanto. Cada um migra numa etapa própria.

## Consequências

- As voltas de 09/08 passam a valer para o coach, inclusive para escolher a volta de referência.
- A freada "em metros" dita pelo coach passa a usar a mesma régua da análise do experimento controlado.
- Durante a transição existem duas projeções ao vivo: a do runtime, para mapa e painel, e a do coach. Isso é temporário e fica registrado no backlog.
- A migração precisa de validação com voltas gravadas antes de ir para o app, como o ADR 0002 exige: fidelidade da projeção, tempo de cálculo por amostra e um ensaio do coach sobre sessões inteiras.
