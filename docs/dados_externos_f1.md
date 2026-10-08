# Dados externos da F1 no Modelo 1

Terceira fonte do Modelo 1 ([ADR 0018](decisoes/0018-dois-modelos-e-fontes-de-treino.md)), como traçado de referência único da época 2023–25 ([ADR 0019](decisoes/0019-f1-tracado-de-referencia-2023-25.md)). Relatórios: [pedido 22](handoff/2026-10-05_22_fontes-e-alinhamento-f1_relatorio.md), uma volta; [pedido 23](handoff/2026-10-05_23_voltas-secas-f1_relatorio.md), a faixa; [pedido 24](handoff/2026-10-08_24_f1-referencia-2023-25_relatorio.md), a referência e a classificação de 2024.

## Decisão (ADR 0019)

- **A F1 entra como uma trajetória de referência única:** a mediana, ponto a ponto da grade, das voltas secas aceitas das sessões de 2023 a 2025. Ela não é a linha de um piloto nem uma faixa de variação.
- **Por quê:** a posição do FastF1 se comporta como um traçado de referência por época, e não como a linha de cada carro (ver "Limites"). A largura da faixa do pedido 23 mede a diferença entre épocas, e por isso não é usada como variação entre pilotos.
- **O que fica fora:**
  - 2019 e 2021–22, que são outras épocas do traçado. Continuam registradas no manifesto do pedido 23;
  - 2018, porque o filtro de pneu não aceita `SUPERSOFT` e a sessão teve chuva em 33 dos 78 registros;
  - a volta de chuva de 2024.
- **Os 10 microssetores "pouco confiáveis" do pedido 23** seguem marcados na referência, para o retreino decidir como tratá-los.

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
  - `backend/ml/scripts/faixa_f1_secas.py` roda tudo;
  - `backend/ml/external/f1_reference.py` e `backend/ml/scripts/referencia_f1.py` formam a referência da época 2023–25 (pedido 24).
- **Saídas:** em `data/ml/externo/f1_faixa/` e `data/ml/externo/f1_referencia/`, fora do git.
- **Classificação de 2024:** o FastF1 3.4.0 monta o caminho pela data atual do calendário (03/11). Ela é carregada pelo caminho em que foi publicada (`2024-11-02_Qualifying`), só nessa sessão, por `use_published_path` em `f1_dry_laps.py`, sem editar o FastF1 (ADR 0019, item 5).

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
  - A classificação de 2024 não carregou no pedido 23. O FastF1 3.4.0 monta o caminho pela data atual do calendário (03/11), e a sessão está publicada em `2024-11-02_Qualifying`. No pedido 24, carregada pelo caminho publicado, ela não deu nenhuma volta seca (seção seguinte).
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

## Classificação de 2024 (pedido 24)

- **Carregou pelo caminho publicado.** O cache tinha a pasta de junho, mas o FastF1 3.4.0 não aceitou os arquivos dela (checagem de versão do cache) e baixou a sessão de novo.
- **As 425 voltas são `WET` (263) ou `INTERMEDIATE` (162).** Todas caem no filtro de pneu, então a sessão não dá nenhuma volta seca, e a faixa do pedido 23 não muda: `faixa.csv` e os 64 CSVs por volta ficaram idênticos byte a byte.
- **Volta 32 de Norris: `INTERMEDIATE`, 83,405 s.**
- **Conferência com o pedido 22:** a mesma volta, com a posição crua (307 amostras) no lugar do `get_telemetry` (633 amostras).

  | | pedido 22 | posição crua |
  |---|---|---|
  | fora do corredor | 2,03% | 2,12% |
  | p95 do excesso | 0 m | 0 m |
  | escala sobre o decímetro | 0,9981 | 0,9981 |
  | rotação | 0,552° | 0,553° |

  O lateral, ponto a ponto, difere 0,019 m na mediana, 0,21 m no p95 e 1,01 m no máximo.
- **Volta de chuva com posição crua:** dentro da faixa seca em 55 dos 60 microssetores, contra 53 com a linha do pedido 22. Ela fica a 5,5 a 6,9 cm, na mediana, das cinco sessões de 2023–25. A distância continua de centímetros, e a hipótese da chuva continua sem poder ser medida.
- **Mensagens de volta apagada:** 6 das 35 mensagens com "DELETED" vêm no formato "LAP DELETED", sem tempo de volta, e o FastF1 3.4.0 não as reconhece. As outras 29 marcam 28 voltas (uma mensagem se repete), e as voltas daquelas 6 ficam sem marca. Não muda nada aqui, porque todas as voltas caem no filtro de pneu. Nas sessões do pedido 23, as contagens batiam.

## Referência da época 2023–25 (pedido 24)

- **Voltas:** 37 voltas secas aceitas de 5 sessões: 2023 Q (7), 2023 Sprint Shootout (9), 2024 Sprint Qualifying (8), 2025 Sprint Qualifying (5) e 2025 Q (8). A classificação de 2024 não tem voltas secas.
- **Coerência, fixada antes de rodar** (|sessão − referência das outras|: mediana ≤ 0,10 m e p90 ≤ 0,30 m). As cinco passam:

  | sessão | mediana | p90 | máximo |
  |---|---|---|---|
  | 2023 Q | 0,019 m | 0,060 m | 0,36 m |
  | 2023 Sprint Shootout | 0,017 m | 0,057 m | 0,26 m |
  | 2024 Sprint Qualifying | 0,018 m | 0,058 m | 0,27 m |
  | 2025 Sprint Qualifying | 0,030 m | 0,097 m | 0,41 m |
  | 2025 Q | 0,019 m | 0,061 m | 0,26 m |

- **Referência:** mediana por ponto das 37 voltas. A amplitude entre as medianas das sessões tem mediana de 0,06 m, p90 de 0,15 m e máximo de 0,51 m. Contra a mediana da faixa do pedido 23, a referência difere 0,02 m na mediana e 0,34 m no máximo.
- **Comparação, só para leitura** (referência − mediana das voltas, por microssetor):
  - com a IA (13 voltas): |Δ| com mediana 1,86 m, p90 3,34 m e máximo 5,06 m (MS48);
  - com o piloto (18 voltas): mediana 1,53 m, p90 3,08 m e máximo 3,82 m (MS35).

  Contra a tabela do pedido 23, a diferença por microssetor tem mediana de 0,03 m e máximo de 0,17 m (MS45).

## Limites

- **A posição do FastF1 não parece ser a linha de cada carro.**
  - Dentro de uma sessão, 5 a 10 carros diferentes ficam a 3 a 8 cm uns dos outros (desvio-padrão mediano por ponto).
  - As medianas das cinco sessões de 2023 a 2025 ficam a 3 a 4 cm da mediana geral, na mediana dos pontos.
  - A volta de chuva de 2024, com pneu `INTERMEDIATE` (conferido no pedido 24), passa a 6 cm da mediana seca da Sprint Qualifying de 2024. Com a posição crua, a 5,7 cm.
  - Já 2019 se afasta até 8,3 m das outras, e 2021–22 até 2,7 m.

  O padrão é de um traçado de referência por época (2019, 2021–22 e 2023–25), e não da linha que cada piloto fez. Por isso, a largura da faixa mede sobretudo a diferença entre épocas, e não a variação entre pilotos. Também não se pode dizer, com estes dados, se a linha de chuva difere da seca. É uma leitura dos números, não um fato documentado pelo FastF1.
- **Escala e lateral se confundem.** Contra a linha central, um deslocamento lateral uniforme se confunde com a escala. A V1 mostra que essa confusão vale até cerca de 1 m nos 10 microsetores marcados.
- **A faixa é de outro carro, em outra velocidade.** Que ela ajude o Modelo 1 é uma hipótese, que só o retreino com as três fontes testa, na régua do ADR 0006 (ADR 0018).
