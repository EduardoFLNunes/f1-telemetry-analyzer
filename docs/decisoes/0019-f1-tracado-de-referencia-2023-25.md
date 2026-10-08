# 0019 — A F1 entra no Modelo 1 como um traçado de referência único da época 2023–25

- **Status:** aceita
- **Data:** 2026-10-08
- **Decisor:** Eduardo

## Contexto

O ADR 0018 pôs a F1 real como terceira fonte do Modelo 1, só com a forma da linha. O pedido 23 formou a faixa com 64 voltas secas de 8 sessões e mostrou que a posição pública do FastF1 não se comporta como a linha de cada carro:

- dentro de uma sessão, 5 a 10 carros de equipes diferentes ficam a 3 a 8 cm uns dos outros (desvio-padrão mediano por ponto);
- as sessões de 2023 a 2025 ficam a 3 a 4 cm da mediana geral;
- a volta da classificação de 2024, descrita como de chuva, passa a 6 cm da linha seca;
- 2019 se afasta até 8,3 m, e 2021–22 até 2,7 m.

A leitura é de um traçado de referência por época (2019, 2021–22 e 2023–25). A documentação do FastF1 não confirma nem nega: é uma hipótese apoiada pelos números (`docs/dados_externos_f1.md`). Por isso, a largura da faixa (mediana de 2,71 m) mede a diferença entre épocas, e não a variação entre pilotos.

## Decisão

1. **A F1 entra como uma trajetória de referência única:** a mediana, ponto a ponto da grade de 2.167 pontos, das voltas secas aceitas das sessões de 2023 a 2025. Ela não representa a linha de um piloto nem uma faixa de variação.
2. **2019 e 2021–22 ficam fora do treino.** São outras épocas do traçado de referência. Continuam registradas no manifesto do pedido 23.
3. **A largura p10–p90 da faixa não é usada como variação entre pilotos** em nenhum modelo.
4. **2018 continua fora.** O filtro de pneu (SOFT, MEDIUM e HARD) não muda para aceitar `SUPERSOFT`: a sessão teve chuva em 33 dos 78 registros e daria poucas voltas.
5. **A classificação de 2024 é carregada pelo caminho em que foi publicada** (`2024-11-02_Qualifying`), só para essa sessão, sem atualizar nem editar o FastF1. Ela completa as conferências do pedido 23 e, se tiver voltas secas aceitas, entra na época 2023–25 pelas mesmas regras.
6. **O ADR 0018 continua valendo:** só a posição da F1 entra, nunca velocidade, pedal ou ponto de frenagem. Se a referência ajuda o Modelo 1, só o retreino com as três fontes dirá, comparando com e sem ela na régua do ADR 0006.
7. **Os microssetores marcados como "faixa pouco confiável" no pedido 23** (MS04 a MS09, MS19 e MS46 a MS48) seguem marcados na referência, para o retreino decidir como tratá-los.

## Consequências

- O item 3 do ADR 0018 fica refinado: "forma da linha da F1" passa a ser "traçado de referência da F1 na época 2023–25".
- O retreino da LSTM geradora usa essa referência como a fonte externa.
- Se outra fonte mostrar que a posição do FastF1 é a linha real de cada carro, este ADR é revisto.
- A hipótese "na chuva os pilotos fogem da linha seca" não pode ser medida com estes dados.
