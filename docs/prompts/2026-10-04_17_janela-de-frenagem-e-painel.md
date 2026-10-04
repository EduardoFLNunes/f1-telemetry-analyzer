Eduardo aqui. Este pedido foi escrito junto com o Claude (Cowork), que faz a revisão e a arquitetura do projeto, e eu aprovo. O plano é meu. Pode executar.

O pedido 16 está aprovado. Três coisas foram ótimas:

- a checagem do período contra o cronômetro do jogo;
- o controle mostrando que o store antigo falharia nela;
- não mudar a regra da frenagem depois de ver o resultado.

Também aceito as suas três decisões: sessão é o dia de gravação, o trecho de cada curva vai do meio da reta anterior ao meio da seguinte, e o `atualizar_coach.py` refaz o store v2 (26 minutos, por enquanto).

São duas coisas pequenas: corrigir a janela de frenagem e gerar o painel da evolução a cada atualização.

## Parte A: documentação

Em `develop`, commite o pedido 17 e a pasta `docs/prompts/anexos-17/`. Mensagem: `docs: pedido 17`.

## Parte B: janela de frenagem

Branch `etapa/painel-evolucao`, a partir de `develop`.

1. A busca do início da frenagem de uma curva passa a ir do **ápice da curva anterior** até o ápice da curva. O trecho usado para o tempo de cada curva não muda.
2. Registre isso no `docs/store_v2_e_evolucao.md` como emenda, com data. É uma definição de medida decidida depois de ver a falha na C10, e não um limite de decisão. Os critérios de "diferença consistente" não mudam.
3. Rode de novo a linha de base de 04/10. Relate, antes e depois, a frenagem da C01, C02, C07, C08, C10 e C12: mediana e em quantas voltas há ponto de frenagem.

## Parte C: painel local

O Claude (Cowork) desenhou um painel e o publicou com os dados de 04/10. O modelo está em `docs/prompts/anexos-17/painel_evolucao.html`.

1. Mova o modelo para um lugar adequado do código, por exemplo junto do `relatorio_evolucao.py`, e apague a pasta de anexos.
2. O `relatorio_evolucao.py` passa a gravar `data/ml/evolucao/painel.html`, trocando o marcador `/*DADOS*/` por um JSON com:
   - `resumo`: o JSON de resumo;
   - `sessoes`: um objeto em que cada chave é a data da sessão e o valor é o JSON daquela sessão;
   - `pista`: `x` e `z` da linha central da geometria oficial exportada, `ds` (o passo da grade, em metros) e `L` (o comprimento da pista);
   - `carro`: o `carModel` das sessões;
   - `pista_nome`: "Interlagos".
3. Não mude o desenho do painel. Se precisar mudar algo para os dados caberem, relate o que foi mudado.
4. Teste que o marcador foi trocado, que o JSON é válido e que as chaves acima existem.
5. O `atualizar_coach.py` imprime no fim o caminho do painel.

## Restrições

- Não mexa no app instalado nem no store antigo.
- Não contorne nenhuma trava: se algo bloquear, pare e me avise.
- Não envie nada ao remoto.

## Merge e entrega

- Se a suíte passar, faça o merge de `etapa/painel-evolucao` em `develop` e rode `relatorio_evolucao.py` uma vez.
- Em `docs/handoff/`: o patch, as saídas das suítes, o antes e depois da frenagem e uma cópia do `painel.html` gerado.
- No relatório: a Parte A, a frenagem antes e depois, o painel e o merge.
