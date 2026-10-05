# Regras do projeto para o Claude Code

Este repositório é trabalhado em duas frentes: o Claude Code implementa e o Claude (Cowork) revisa e escreve os pedidos. O Cowork lê os arquivos do repositório direto, mas não vê o chat do Code. Por isso, tudo que o Code relata precisa estar num arquivo.

## Pedidos

- Os pedidos ficam em `docs/prompts/AAAA-MM-DD_NN_<assunto>.md`.
- Quando o Eduardo disser "Execute o pedido em <arquivo>", leia o arquivo inteiro e siga-o.
- Perguntas e confirmações de acompanhamento também chegam como pedido numerado, mesmo quando são curtas.

## Relatório em arquivo

- Ao terminar um pedido, grave o relatório completo, com o mesmo texto que você mostra no chat, em `docs/handoff/AAAA-MM-DD_NN_<assunto>_relatorio.md`. O `NN` é o número do pedido.
- No começo do arquivo, coloque:
  - o pedido que ele responde;
  - a branch e os commits e merges, com o hash curto e a mensagem;
  - a lista dos arquivos de handoff gerados.
- Se parar no meio (por uma trava, uma dúvida ou uma decisão do Eduardo), grave o relatório do que foi feito até ali e termine dizendo o que falta e o que precisa de decisão.
- Commite o relatório junto com o handoff. Se o commit não for possível, deixe o arquivo mesmo assim e diga isso no chat.
- No chat, mostre o relatório como sempre e termine com o caminho do arquivo.

## Sempre

- Responda em português.
- Não envie nada ao remoto sem pedido explícito.
- Uma sessão de implementação por vez (ADR 0008).
- Não contorne nenhuma trava: se algo bloquear, pare e avise.
