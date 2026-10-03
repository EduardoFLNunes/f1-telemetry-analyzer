# Coach com volta de referência real (ADR 0012)

Relatório de 2026-10-03. Branch `etapa/coach-referencia-real`, a partir de
`develop` (`45d45c8e`). Sem merge.

---

## 1. O problema

O coach ao vivo guardava, para cada um dos 60 microsetores, o mais rápido que o
piloto já tinha sido ali. Com isso ele dizia "X s atrás do seu melhor" em cada
trecho e, no fim da volta, falava em "volta ideal" (a soma desses 60 melhores) e
no que "sobrava" contra o traçado otimizado.

A soma dos melhores trechos é otimista por construção. O melhor de 100
tentativas com ruído é sempre mais baixo do que o piloto consegue repetir, mesmo
sem nenhuma melhora real. E costurar trechos ignora que um trecho rápido pode ter
custado o seguinte.

## 2. A medição (só com dados já gravados)

Script: `backend/tools/measure_reference_optimism.py`.

Para cada sessão com pelo menos 20 voltas válidas, as voltas foram divididas em
duas metades, na ordem em que foram feitas. O "melhor de todos" de cada
microsetor foi montado só com a primeira metade. A pergunta foi: e na segunda
metade?

| sessão | régua | volta ideal (1ª metade) | melhor volta (1ª) | "na mesa" | melhor volta (2ª) | ganho realizado | voltas que igualam o "melhor" do microsetor |
|---|---|---:|---:|---:|---:|---:|---:|
| 2026-06-20_13-13-02 (39 voltas) | coach | 83,928 s | 85,441 s | 1,513 s | 85,576 s | **−0,135 s** | 4,9 % |
| 2026-06-20_13-13-02 | grade do ML | 83,912 s | 85,441 s | 1,530 s | 85,576 s | −0,135 s | 4,2 % |
| 2026-08-09_19-20-59 (52 voltas) | grade do ML | 84,627 s | 85,472 s | 0,844 s | 85,533 s | **−0,061 s** | 3,4 % |

- **Nada do "ganho na mesa" se realizou.** Nas duas sessões, a melhor volta da
  segunda metade foi até mais lenta que a da primeira.
- **Cada "melhor do microsetor" só foi igualado em 3–5 % das voltas
  seguintes.** Não é um alvo que o piloto repete.
- **A volta ideal da primeira metade ficou 1,65 s e 0,91 s abaixo da melhor
  volta real da segunda.**

**Duas réguas.** A régua do coach usa o próprio código do app
(`build_reference_model` e `microsector_splits`, sobre o progresso `p`). Ela só
funciona na sessão de junho: **as gravações de 2026-08-09 não têm progresso**
(`p` ausente e `s` = 0). O coach não consegue recortar essas voltas em
microsetores, então elas nunca entram no modelo dele (veja o item 6). A grade do
ML (60 microsetores de mesma distância, tempos do store) mede as duas sessões. Na
sessão de junho, as duas réguas dão a mesma resposta.

## 3. A mudança

### Modelo (`core/assisted_analysis/reference_model.py`)

- **Modo novo, padrão: `reference_lap`.** A volta de referência é a melhor volta
  válida e **completa**. Completa quer dizer todos os 60 microsetores medidos e
  nenhum buraco de gravação maior que meio microsetor (~36 m). O
  `microsector_splits` interpola as fronteiras mesmo dentro de um buraco, então
  "60 tempos" sozinho não garantia isso; um teste pegou o caso. Outra volta pode
  ser escolhida pelo `lap_id`, e ela também precisa ser válida e completa.
- **Para cada microsetor, a referência guarda:** o tempo, o ponto de frenagem
  (em `p` e em metros do `s` do runtime), a velocidade mínima e o ponto de
  retomada do acelerador.
- **O modo antigo (`best_per_microsector`) continua no código,** desligado por
  padrão.
- **Um modelo salvo antes desta mudança ainda carrega,** mas sem volta de
  referência. Nesse caso o coach fica em silêncio e registra no log que é
  preciso retreinar. Ele **não** volta ao modo antigo sem pedido, porque isso
  traria de volta a "volta ideal". O leitor também passou a ignorar campos
  desconhecidos, para um arquivo mais novo não derrubar uma versão mais velha.

### O que o coach diz (`core/live/driving_coach.py`)

| quando | antes (exemplo) | agora, modo padrão (exemplo) |
|---|---|---|
| microsetor (linha 271) | "Setor 22: 0.60s atras do seu melhor (1.98s contra 1.38s). No melhor, minima de 95 km/h. O tracado otimo faz em 1.25s." | "Setor 22: 0.60s atras da sua volta de referencia neste trecho (1.98s contra 1.38s)." |
| meta, quando houver (linha 280) | — | " Na referencia: freada em 1578 m, minima de 110 km/h." |
| fim da volta (linhas 358–365) | "Volta fechada. 1.88s acima do seu ideal, a maior perda no setor 22 (0.60s). Ideal 83.54s, seu melhor 84.86s. Contra o tracado otimo, X s. Mesmo no seu ideal sobrariam Y s." | "Volta fechada. 1.88s somando os trechos em que ficou atras da sua volta de referencia; a maior diferenca no setor 22 (0.60s). Volta de referencia: 85.00s." |

- **Nada de "ganhar", "ideal" ou traçado ótimo no modo padrão.** Os segundos do
  traçado ótimo vêm do simulador, e o ADR 0004 os mantém fora do que o piloto
  ouve.
- **O limiar de fala não mudou.** Continua sendo duas vezes a oscilação do
  próprio piloto no microsetor (mediana − melhor de todos), medida sobre todas
  as voltas do modelo, nos dois modos.
- **A evidência do evento** traz `referenceSeconds`, `referenceLapId`,
  `referenceBrakePointM` e `referenceMinSpeedKmh`. Ela não traz mais
  `bestSeconds` nem `optimalSeconds`.

### API

| arquivo | modo padrão |
|---|---|
| `core/assisted_analysis/service.py:369–370` (contexto do modelo na análise assistida) | `referenceLapId`, `referenceLapSeconds`, `deltaToReferenceS`, `worstMicrosectors[].behindReferenceS`. Sem `idealLapSeconds`, `gapBestToIdeal`, `lapLossAgainstIdeal` nem `optimalLine`. |
| `routers/assisted_analysis.py:187` (coach do replay) | `model` traz `mode`, `referenceLapId`, `referenceLapSeconds`. O `idealLapSeconds` só aparece no modo antigo. |

Nenhum desses campos antigos era lido pelo frontend (conferido por busca).

### Interface (menor mudança possível, sem mexer no layout)

| arquivo e linha | antes | agora |
|---|---|---|
| `frontend/src/components/CoachingFeed.tsx:69` | `MELHOR 1.38s` (e `OTIMO 1.25s` quando havia traçado) | `REFERENCIA 1.38s`. Sem `OTIMO`, porque o backend não manda mais `optimalSeconds` no modo padrão. |

O modo antigo continua mostrando `MELHOR` e `OTIMO`.

Busquei no frontend "ideal", "na mesa" e "ganho" vindos **deste modelo** e não
achei outros. Os "GANHOS" de `LiveComparisonPanel.tsx:226` e
`RacingLineAnalysisPanel.tsx:306`, e o "Voce ganha aproximadamente" de
`utils/comparisonAnalysis.ts:504`, não vêm do modelo do coach. Eles saem da
comparação ao vivo do frontend (`buildComparisonAnalysisFromStore`) e listam
trechos em que o piloto **já foi** mais rápido que a referência: é diferença
medida, e não ganho prometido. Ficaram como estão. O "Ganho estimado" do
`core/assisted_analysis/feedback_generator.py`, que vem da análise assistida por
curva, foi registrado como pendência para conferir contra o ADR 0012.

### Treino do modelo (`tools/train_reference_model.py`)

- Novas opções `--modo`, `--volta-referencia`, `--saida` e `--geometria`.
- Só entram voltas gravadas com **um** cache de geometria (`trackCache` da
  sessão). Sem `--geometria`, o script lista as geometrias encontradas, usa a da
  maioria e avisa que isso deve ser escolhido de propósito (ver item 6).
- No terminal, a soma dos melhores trechos passa a aparecer como "limite
  otimista, nao meta".

## 4. Testes

- **`backend/tests/test_coach_reference_lap.py` (12 testes):**
  - escolhe a melhor volta válida **completa**, ignorando uma mais rápida com
    buraco e outra gravada a 13 Hz;
  - aceita outra volta pelo `lap_id` e recusa uma incompleta ou inexistente;
  - as diferenças por microsetor somam a diferença de tempo de volta (±0,02 s);
  - as frases novas não contêm "ganh", "ideal" nem "otimo", e trazem a meta da
    referência;
  - o limiar é igual nos dois modos;
  - um modelo antigo carrega e deixa o coach em silêncio;
  - um arquivo com campos desconhecidos carrega;
  - o modo antigo funciona quando ligado;
  - o replay usa as mesmas regras.
- **Testes do modo antigo:** os de `test_driving_coach.py` e `test_optimal_line.py`
  que verificam o "seu melhor", o "ideal" e o traçado ótimo agora ligam o modo
  antigo explicitamente. Um teste novo garante que o modo padrão nunca cita o
  traçado.
- **Frontend:** `CoachingFeed.test.ts` (10 testes, um novo) e `tsc --noEmit`
  sem erros.

## 5. O que não foi feito nesta branch

- **O arquivo do modelo usado pelo app** (`data/reference_models/vhe_interlagos.json`,
  fora do git) **não foi regravado.** O código de `develop` não lê o formato
  novo, então regravar agora calaria o coach em `develop`. Depois do merge, é
  preciso rodar `python tools/train_reference_model.py`. Até lá, com o código
  novo, o coach fica em silêncio e avisa no log.
- O `optimal.json`, as LSTMs e a geometria do runtime não foram tocados.

## 6. Limitações

- **As sessões de 2026-08-09 não entram no modelo do coach.** São 56 das 122
  voltas válidas, e não têm progresso gravado. Isso já acontecia antes desta
  mudança. A causa é a mesma da geometria única (ADR 0002): o coach depende do
  `p` do runtime, e não da posição no mundo.
- **Qual geometria usar é uma decisão pendente.** O coach compara o progresso
  ao vivo, calculado com a geometria atual do app, com o progresso do modelo.
  Contando as sessões de Interlagos pelo `trackCache` gravado: 60 usam
  `vhe_interlagos_gp_InterlagosPitAccessAsphaltMergeFix`, só 7 usam
  `vhe_interlagos_gp_kn5_surface_interval_geometry` (o cache atual do app) e 3
  não registram nenhum (as de 09/08). Na Fase 1, o `s` gravado seguiu réguas
  diferentes nesses dois grupos. **O modelo em uso (25/08) mistura as três
  origens:** dos 60 alvos mais a melhor volta, 34 vêm de sessões com o cache
  atual, 9 do `InterlagosPitAccessAsphaltMergeFix` e 18 de sessões sem cache
  registrado. Isso é parte do ADR 0002 (geometria única).
- **O carro não é registrado nas gravações.** O filtro "mesma pista, carro e
  geometria" fica, na prática, mesma pista e mesmo nome de cache de geometria.
- **A medição tem duas sessões.** Ela mostra o problema com clareza, mas não
  mede quanto ele cresce com o tamanho do histórico.
- **"Atrás da referência" é um fato medido, não uma promessa.** Fazer o trecho
  como na referência não garante o mesmo tempo na volta inteira.
