Eduardo aqui. Este pedido foi escrito junto com o Claude (Cowork), que faz a revisão e a arquitetura do projeto, e eu aprovo. O plano é meu. Pode executar.

O pedido 11 está aprovado como está, sem merge. O critério (c) falhou, e o diagnóstico (fronteira da linha de chegada e saltos de projeção) foi exatamente o que precisávamos. Reaproveitar o `MapMatchingEngine` foi a escolha certa. A branch `etapa/coach-geometria-oficial` fica parada; as correções vêm no pedido 13, depois deste.

Descobrimos um problema maior nos dados: muitas sessões foram gravadas com a **IA do Assetto Corsa pilotando**, ligada por um botão no jogo. Eu lembro de ter usado a IA nas sessões de 14/06 a 19/06, de 20/06 e de 09/08, e às vezes alternava entre a IA e eu dentro da mesma sessão. Por isso, o rótulo precisa ser por volta.

Leia antes de começar: `docs/decisoes/0014-origem-das-voltas-humano-ou-ia.md`.

## Parte A: documentação

1. Não mexa na branch do pedido 11.
2. Em `develop`, o backlog, o protocolo e o índice dos ADRs já devem estar na versão deste pedido: o índice lista o ADR 0014 e o protocolo começa com o aviso "Em espera". Se a pasta `docs/prompts/anexos-12/` existir, copie os arquivos dela para os lugares certos e apague a pasta.
3. No protocolo, troque "Como desligar: (a preencher)" pela sua opção (a), com o caminho exato do arquivo do modelo no app instalado: renomear o arquivo com o app fechado e voltar o nome depois da sessão.
4. Commite tudo junto com o pedido 12 e o ADR 0014.

   Mensagem: `docs: ADR 0014 (origem das voltas), backlog, protocolo e pedido 12`.

## Parte B: origem e confiabilidade das voltas

Branch `etapa/origem-das-voltas`, a partir de `develop`.

### 1. As duas pastas de gravações

Compare `data/recordings` do repositório com `%APPDATA%\Automobilista Telemetria\data\recordings` do app instalado. Relate:

- quantas sessões existem em cada uma;
- quantas estão nas duas, com o mesmo id e o mesmo conteúdo (pelo hash);
- quantas só existem em uma;
- quantas são de Interlagos.

Daqui em diante, considere as sessões de Interlagos das duas pastas, sem repetir as que forem iguais.

### 2. As gravações já dizem quem pilotava?

- Até onde sabemos, a memória compartilhada do Assetto Corsa tem um campo que indica se a IA está no controle (`isAIControlled`, na página de física). Confirme isso na documentação ou na estrutura usada pelo gravador.
- Procure esse campo, ou qualquer equivalente, nas gravações, inclusive em `availability` e `inferred`.
- Relate, por sessão: se o campo existe e em que fração das amostras ele indica IA.

### 3. O gravador passa a registrar

- O indicador de IA no controle, em cada amostra.
- O modelo do carro (`carModel`, na página estática), nos metadados da sessão.
- Faça a menor mudança possível, com testes.
- Se o campo de IA não existir nesta versão do AC, pare esse item e me relate. Não invente um indicador.

### 4. Relógio plausível

O pedido 11 achou tempos impossíveis por microsetor: a soma dos melhores trechos deu 78,16 s, com 3 voltas dentro da pista.

- Para cada microsetor de cada volta, compare o tempo pelo relógio gravado com o tempo calculado pela velocidade ao longo da grade de 2 m (a soma de distância dividida por velocidade).
- Mostre a distribuição dessa diferença e proponha um limite antes de aplicá-lo. Escreva o limite no documento da etapa.
- Voltas com algum microsetor acima do limite recebem a marca `relogio_suspeito`.
- Relate o que aparece nas 3 voltas do pedido 11.

### 5. Coluna `origem` no inventário

- Cada volta recebe `origem`:
  - `humano` ou `ia`, quando o campo existir e for constante na volta;
  - `misturada`, quando mudar dentro da volta;
  - `desconhecida`, quando não houver campo.
- Registre também de qual pasta a volta veio.
- O store e o treino do coach aceitam filtrar por origem e pela marca de relógio. Para tudo que fala do piloto, o padrão é `humano` sem `relogio_suspeito`.
- Não reconstrua o store do ML nem recalcule resultados antigos nesta etapa.

### 6. Se as gravações antigas não tiverem o campo

- Não treine nenhum detector ainda.
- Liste sinais candidatos para separar IA de humano e mostre a distribuição deles por sessão. Exemplos: mudanças rápidas de volante, forma das curvas de pedal, dispersão do ponto de frenagem entre voltas, momento das trocas de marcha.
- O detector será treinado depois, com sessões novas já rotuladas pelo gravador.

### 7. Números por origem (só se houver rótulos)

Para cada origem, relate:

- quantas voltas há;
- a dispersão do ponto de frenagem e do ápice entre voltas, como na Fase 2b;
- o desvio entre voltas do tempo no Bico de Pato (2.590 a 3.080 m);
- a melhor volta válida e completa.

### Restrições

- Só leia as duas pastas de gravações: não copie, mova nem apague nada nelas.
- Não altere o modelo do coach do app instalado nem o do repositório.
- Não faça merge da branch do pedido 11 e não treine modelos.
- Não altere os documentos de resultado das Fases 2 e 2b.
- Não contorne nenhuma trava: se algo bloquear, pare e me avise.
- Não envie nada ao remoto.

### Merge

- Se a suíte passar, faça o merge de `etapa/origem-das-voltas` em `develop`.
- Depois eu faço uma gravação curta de teste, alternando IA e eu, para confirmar que o indicador muda.

### Entrega

- Em `docs/handoff/`: o patch, a saída do pytest e um JSON com a tabela por sessão.
- `docs/origem_das_voltas.md`, em português simples: o que foi encontrado, o que mudou no gravador e o que falta.

No relatório, apresente a Parte A e depois a Parte B, item por item.
