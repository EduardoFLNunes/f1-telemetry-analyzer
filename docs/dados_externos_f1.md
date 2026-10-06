# Dados externos da F1 no Modelo 1

Terceira fonte do Modelo 1 ([ADR 0018](decisoes/0018-dois-modelos-e-fontes-de-treino.md)). Relatórios: [pedido 22](handoff/2026-10-05_22_fontes-e-alinhamento-f1_relatorio.md), uma volta, e [pedido 23](handoff/2026-10-05_23_voltas-secas-f1_relatorio.md), a faixa.

## O que entra

**Só a forma da linha:** `X` e `Y` dos dados de posição da volta (`Lap.get_pos_data()` do FastF1), levados à grade de 2 m da geometria oficial `0ed16f0dd2225990` como `lateral(s)`, positivo à esquerda (ADR 0003).

Nada mais da F1 é lido nem salvo: velocidade, pedais, marcha, rotação, DRS, distância e ponto de frenagem ficam de fora. O tempo de volta só escolhe e identifica a volta. `get_telemetry()` não é usado, porque interpola a posição nos instantes dos dados do carro.

## Fonte, sessões e anos

- **Fonte:** FastF1 3.4.0, fixado em `backend/requirements.txt`, com o cache em `data/fastf1_cache/`, fora do git.
- **Pista:** Interlagos.
- **Sessões:** a classificação de 2018, 2019 e 2021 a 2025, mais as classificatórias da sprint: Sprint Shootout em 2023 e Sprint Qualifying em 2024 e 2025. A corrida sprint não entra. No FastF1 3.4.0, a sessão de 2021 e 2022 aparece como "Sprint", com data posterior à classificação, e fica fora.
- **Código:**
  - `backend/ml/external/f1_dry_laps.py` faz a coleta;
  - `backend/ml/external/f1_line.py` e `f1_band.py` fazem o alinhamento e a faixa;
  - `backend/ml/scripts/faixa_f1_secas.py` roda tudo.
- **Saídas:** em `data/ml/externo/f1_faixa/`, fora do git.

## Método

1. **Filtros, nesta ordem:**
   - pneu SOFT, MEDIUM ou HARD;
   - `IsAccurate`;
   - volta não apagada (`Deleted`). A sessão sem essa informação fica inteira fora;
   - bandeira verde a volta toda (`TrackStatus == '1'`);
   - sem box;
   - nenhum `Rainfall` verdadeiro durante a volta.

   Depois, de cada piloto a volta mais rápida, e de cada sessão os 10 pilotos mais rápidos.
2. **Alinhamento**, o do pedido 22: Procrustes e ICP contra a linha central, com uma escala livre e espelho permitido, depois projeção na grade e excesso sobre o corredor de `ml.track`.
3. **Critério por volta, fixado antes de rodar:**
   - cobertura ≥ 0,99;
   - maior buraco entre amostras ≤ 80 m;
   - fração da grade fora do corredor ≤ 10%;
   - p95 do excesso ≤ 1 m.
4. **Incerteza do alinhamento:** V1 prende a escala em 0,1 m por unidade; V2 usa uma transformação por sessão. Um microsetor com p90 de |variante − principal| acima de 1 m é "faixa pouco confiável".
5. **Faixa:** por ponto da grade, p10, p50 e p90 do lateral, com cada volta pesando igual. Mínimo de 20 voltas de 3 sessões.

## Resultados (pedido 23)

- **Funil:** 80 voltas escolhidas em 8 sessões.
  - 2018 ficou sem nenhuma volta: 284 das 300 estão como `SUPERSOFT`, nome de composto da época, e as 4 que sobraram tinham chuva.
  - A classificação de 2024 não carregou. O FastF1 3.4.0 monta o caminho pela data atual do calendário (03/11), e a sessão está publicada em `2024-11-02_Qualifying`.
- **Critério:** 64 voltas aceitas, de 8 sessões, e 16 recusadas: 9 por buraco acima de 80 m e 7 por cobertura abaixo de 0,99. Nas aceitas, a fração fora do corredor vai de 1,0% a 2,9%, e o p95 do excesso é 0 m em todas.
- **Incerteza:**
  - V2 muda o lateral em menos de 7 cm (p90 por microsetor). As transformações por volta dentro de uma sessão variam no máximo 0,02° e 9 cm no centróide, então cada sessão está num sistema de coordenadas só.
  - V1 muda até 1,27 m (p90). A escala livre sai 0,9977 a 0,9982 do decímetro.
  - 10 microsetores ficam "pouco confiáveis": MS04 a MS09, MS19 e MS46 a MS48.
- **Faixa formada com 64 voltas de 8 sessões.** A largura p10–p90 tem mediana de 2,71 m. A amplitude entre as medianas das sessões tem mediana de 2,67 m e máximo de 6,89 m (MS56).
- **Comparação, só para leitura:**
  - a mediana das 13 voltas `ia` fica dentro da faixa em 16 dos 60 microsetores;
  - a das 18 voltas `humano` atuais, em 17;
  - a volta de chuva de 2024, a linha do pedido 22, em 53;
  - |mediana da F1 − IA| por microsetor: mediana 1,85 m, p90 3,36 m, máximo 5,00 m;
  - |mediana da F1 − piloto|: mediana 1,48 m, p90 3,02 m, máximo 3,82 m.

## Limites

- **A posição do FastF1 não parece ser a linha de cada carro.**
  - Dentro de uma sessão, 5 a 10 carros diferentes ficam a 3 a 8 cm uns dos outros (desvio-padrão mediano por ponto).
  - As medianas das cinco sessões de 2023 a 2025 ficam a 3 a 4 cm da mediana geral, na mediana dos pontos.
  - A volta de chuva de 2024 passa a 6 cm da mediana seca da Sprint Qualifying de 2024. O contexto do pedido 23 a descreve como de chuva, mas o pneu não pôde ser conferido no FastF1, porque a sessão não carregou.
  - Já 2019 se afasta até 8,3 m das outras, e 2021–22 até 2,7 m.

  O padrão é de um traçado de referência por época (2019, 2021–22 e 2023–25), e não da linha que cada piloto fez. Por isso, a largura da faixa mede sobretudo a diferença entre épocas, e não a variação entre pilotos. Também não se pode dizer, com estes dados, se a linha de chuva difere da seca. É uma leitura dos números, não um fato documentado pelo FastF1.
- **Escala e lateral se confundem.** Contra a linha central, um deslocamento lateral uniforme se confunde com a escala. A V1 mostra que essa confusão vale até cerca de 1 m nos 10 microsetores marcados.
- **A faixa é de outro carro, em outra velocidade.** Que ela ajude o Modelo 1 é uma hipótese, que só o retreino com as três fontes testa, na régua do ADR 0006 (ADR 0018).
