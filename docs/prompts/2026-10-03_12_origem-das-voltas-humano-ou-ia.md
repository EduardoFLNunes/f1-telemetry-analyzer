Eduardo aqui. Este pedido foi escrito junto com o Claude (Cowork), que faz a revisão e a arquitetura do projeto, e eu aprovo. O plano é meu. Pode executar.

Descobrimos um problema nos dados: muitas sessões foram gravadas com a **IA do Assetto Corsa pilotando**, ligada por um botão no jogo. Eu lembro de ter usado a IA nas sessões de 14/06 a 19/06, de 20/06 e de 09/08, e às vezes alternava entre a IA e eu dentro da mesma sessão. Por isso, o rótulo precisa ser por volta.

Leia antes de começar: `docs/decisoes/0014-origem-das-voltas-humano-ou-ia.md`.

## Parte A: pedido 11 e documentação

1. Do pedido 11, termine e relate os passos 1 a 8. **Não faça o passo 9** (merge e treino do modelo do app). A branch `etapa/coach-geometria-oficial` fica esperando a rotulagem.
2. O Claude escreveu os documentos como arquivos novos, para não sujar a sua branch. Em `develop`:
   - substitua `docs/backlog.md` por `docs/prompts/anexos-12/backlog.md`;
   - substitua `docs/experimentos/protocolo_sessao_controlada.md` por `docs/prompts/anexos-12/protocolo_sessao_controlada.md`;
   - substitua `docs/decisoes/README.md` por `docs/prompts/anexos-12/README.md`;
   - apague a pasta `docs/prompts/anexos-12/`;
   - commite junto o pedido 12 e o ADR 0014 (`docs/decisoes/0014-origem-das-voltas-humano-ou-ia.md`).

   Mensagem: `docs: ADR 0014 (origem das voltas), backlog, protocolo e pedido 12`.

   Se o passo 6 do pedido 11 já tiver preenchido o "Como desligar" do protocolo, mantenha esse texto na versão nova.

## Parte B: origem das voltas

Branch `etapa/origem-das-voltas`, a partir de `develop`.

### 1. As gravações já dizem quem pilotava?

- Até onde sabemos, a memória compartilhada do Assetto Corsa tem um campo que indica se a IA está no controle (`isAIControlled`, na página de física). Confirme na documentação ou na estrutura usada pelo gravador.
- Procure esse campo, ou qualquer equivalente, em todas as gravações de Interlagos, inclusive em `availability` e `inferred`.
- Relate, por sessão: se o campo existe e em que fração das amostras ele indica IA.

### 2. O gravador passa a registrar

- O indicador de IA no controle, em cada amostra.
- O modelo do carro (`carModel`, na página estática), nos metadados da sessão.
- Faça a menor mudança possível, com testes.
- Se o campo de IA não existir nesta versão do AC, pare esse item e me relate. Não invente um indicador.

### 3. Coluna `origem` no inventário

- Cada volta recebe `origem`: `humano` ou `ia`, quando o campo existir e for constante na volta; `misturada`, quando mudar dentro da volta; `desconhecida`, quando não houver campo.
- O store e o treino do coach aceitam filtrar por origem. Para tudo que fala do piloto, o padrão é só `humano`.
- Não recalcule resultados antigos nesta etapa.

### 4. Se as gravações antigas não tiverem o campo

- Não treine nenhum detector ainda.
- Liste sinais candidatos para separar IA de humano e mostre a distribuição deles por sessão. Exemplos: mudanças rápidas de volante, forma das curvas de pedal, dispersão do ponto de frenagem entre voltas, momento das trocas de marcha.
- O detector será treinado depois, com sessões novas já rotuladas pelo gravador.

### 5. Números por origem (só se houver rótulos)

Para cada origem, relate:

- quantas voltas há;
- a dispersão do ponto de frenagem e do ápice entre voltas, como na Fase 2b;
- o desvio entre voltas do tempo no Bico de Pato (2.590 a 3.080 m);
- a melhor volta válida e completa.

### Restrições

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
