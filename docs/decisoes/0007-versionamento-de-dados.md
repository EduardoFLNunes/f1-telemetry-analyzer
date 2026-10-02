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
