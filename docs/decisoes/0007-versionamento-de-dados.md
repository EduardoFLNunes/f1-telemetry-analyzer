# 0007 — Versionamento de dados sem DVC, por enquanto

- **Status:** aceita
- **Data:** 2026-09-30
- **Decisor:** Eduardo

## Contexto

As gravações somam ~12 GB e os artefatos derivados (store, modelos, resultados) ficam fora do git. A ferramenta padrão para versionar dados em projetos de ML é o DVC. Para um trabalho acadêmico com um único usuário, ele acrescenta configuração e armazenamento extras.

## Decisão

- Não adotar DVC agora.
- Todo `resultados.json` de handoff registra:
  - o commit de base e o `geometry_id`;
  - o ambiente e os comandos usados;
  - o hash e o tamanho dos arquivos de dados lidos (store, inventário, modelos).
- Artefatos substituídos são guardados antes de serem regravados, como em `data/ml/_backup_pre_fase1/`.

## Consequências

- Os resultados são reproduzíveis e verificáveis pelo hash, sem infraestrutura nova.
- Reavaliar se o volume de dados ou o número de pessoas no projeto crescer.

## Atualizações

- **17/11/2026 (pedido 54), decisão do Eduardo:** as sessões em que a linha do jogo fica fora da tolerância de 0,10 m em torno de 1,463 m, mas com o efeito no tempo em até 2,0 ms em módulo, são **aceitas com margem** e não reprovam o store v2.
  - O efeito é a mediana, volta a volta, de (mediana da sessão − 1,463 m) / velocidade na passagem do começo da volta.
  - O meta do store guarda a lista em `sessoes_aceitas_com_margem` e a margem em `margem_linha_do_jogo_ms`.
  - Acima de 2,0 ms, a sessão continua reprovando o store.
  - A regra está em `docs/store_v2_e_evolucao.md`, seção 1.3, na emenda de 17/11. Os 1,463 m, a tolerância e as outras checagens não mudam.
