# 0017 — Modelo físico do carro: carro e piloto separados, construído por etapas junto do que já roda

- **Status:** aceita
- **Data:** 2026-10-04
- **Decisor:** Eduardo

## Contexto

O único modelo físico do projeto é o simulador quase-estacionário (`ml/optimization/lap_time_model.py`):

- Ele recebe uma linha e devolve o perfil de velocidade mais rápido que o envelope do carro, ajustado na telemetria, permite nela. A elipse de atrito entra como limite.
- **Medido:** erro médio de 1,36 s no tempo de volta, viés de −0,22 s e correlação de 0,93 nas 113 voltas do primeiro store. Na Fase 2, nenhuma variante passou de skill zero na estimativa de ganho por trecho (ADR 0004).
- **Limites já registrados:** não tem transferência de carga, mapa de motor nem pneu com temperatura, e assume execução perfeita (`docs/correcao_trajetoria_auditoria.md`, risco 3).

O Eduardo apontou o que falta (conversa de 04/10):

1. **Entradas combinadas.** Frear e esterçar ao mesmo tempo divide a aderência do pneu e, dependendo da velocidade, o carro não vira. O simulador atual conhece a elipse só como limite: ele nunca recebe volante e pedal, então não responde o que o carro faz com as entradas do piloto.
2. **Estado.** A temperatura dos pneus e dos freios muda a aderência e se acumula ao longo da volta. Um modelo quase-estacionário não tem memória.
3. **Estilo.** O modelo precisa levar em conta como este piloto pilota.

Dois fatos tornam este o momento de começar:

- **O "e se?" precisava de variação provocada (ADR 0011).** Um modelo de entradas para movimento não precisa: cada volta tem milhares de pares "o que o piloto fez, o que o carro fez", e o modelo pode ser testado prevendo os próximos segundos em sessões que não viu.
- **As sessões de treino do Eduardo já estão sendo gravadas** (ADR 0015). Se os canais físicos entrarem agora no store, essas voltas servem depois sem regravar nada.

## Decisão

### 1. Dois modelos, separados

| | Modelo do carro | Modelo do piloto |
|---|---|---|
| Responde | o que o carro faz com estas entradas, neste estado | como este piloto usa o carro |
| Muda com o piloto? | **não**: as regras da física são as mesmas para qualquer um | sim: é aqui que o estilo entra |
| Muda com o estado? | sim: pneu, freio, combustível | — |
| Lugar na arquitetura | motor da peça D | parte da peça B |

Se o modelo do carro se adaptasse ao piloto, aprenderia os erros do piloto como se fossem limites do carro. Foi o problema das voltas da IA, ao contrário. O estilo entra no modelo do carro só pelo estado que ele produz: quem freia mais forte esquenta mais os freios.

### 2. O modelo do carro é híbrido

- Uma física simples e explicável (massa, transferência de carga, elipse de atrito, pneu e freio com temperatura quando os dados mostrarem que importa) e uma correção aprendida dos dados para o que essa física erra.
- É o desenho de Kabzan et al. (já citado no ADR 0004) e do BayesRace (ADR 0010): física com poucos parâmetros mais um Processo Gaussiano no resíduo.
- A forma é "para a frente": estado e entradas agora, estado depois de Δt.

### 3. O Assetto Corsa é a referência física

- O jogo já simula este carro com pneu, temperatura e transferência de carga. Os dados do modelo vêm da telemetria dele.
- Como o jogo vai executar variações controladas (IA em outros níveis, entradas roteirizadas, AssettoCorsaGym) fica para decidir antes da etapa M4.
- Os arquivos do carro só são lidos se estiverem abertos. Arquivo criptografado não é contornado: os parâmetros saem da telemetria.

### 4. Etapas, cada uma presa a uma parte que já existe

| Etapa | O que é | Junto de | Quando |
|---|---|---|---|
| **M0** | Canais físicos no store v2, unidade do volante e medidas descritivas de técnica no relatório de evolução | `atualizar_coach` e a peça B, versão 1 | Agora, pedido 18 |
| **M1** | Modelo do carro para a frente, sem temperatura, com critérios fixados antes de rodar e a régua do ADR 0006 | peça D | Quando houver 5 sessões humanas com canais físicos (o mínimo do ADR 0006) |
| **M2** | Temperatura de pneu e freio no modelo | M1 | Só se a M0 mostrar efeito |
| **M3** | Modelo do piloto: uso da aderência, freio e volante juntos, pontos de frenagem | peça B, versão 2 | Depois da M1 |
| **M4** | Peça D refeita sobre o modelo do carro | peça D | Depois da M1 aprovada |

A peça C continua por último. O simulador quase-estacionário fica como linha de base e o ADR 0004 continua valendo até a M1 passar na régua.

## Consequências

- **A M0 não muda nenhuma regra de decisão.** As medidas de técnica são descritivas, e o coach e a "diferença consistente" ficam como estão.
- **As 20 a 30 voltas de treino passam a carregar os canais físicos.** Campos que o gravador ainda não grava só aparecem nas sessões gravadas depois da mudança.
- **O store fica maior e o `atualizar_coach` mais lento.** O modo incremental, já no backlog, fica mais urgente.
- **Riscos conhecidos:** a unidade do volante gravado não está documentada; a temperatura dos freios pode não estar sendo gravada; e os parâmetros do carro podem não ser acessíveis.
- **O item do backlog "decidir se o AC vira o simulador do ganho",** que apontava para este ADR, fica coberto aqui, menos a escolha de como o jogo executa as variações, que vai para antes da M4. O item "simulador + corretor aprendido" vira a M1.
