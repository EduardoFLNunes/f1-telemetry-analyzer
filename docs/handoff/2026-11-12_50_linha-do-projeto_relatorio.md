# Relatório do pedido 50: a linha do projeto (parado na conferência da codificação, A.4)

- **Pedido:** `docs/prompts/2026-11-12_50_linha-do-projeto.md`.
- **Situação:** **parado na conferência da codificação nova (ADR 0031, itens 4.5 e 4.6),** como o pedido manda ("Se não ficarem, pare e relate"). Falta uma decisão do Eduardo. A sessão também chegou ao limite de uso.
- **Pasta:** `C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47`.
- **Branch:** `etapa/linha-do-projeto`, a partir de `develop` em `e873d6a6`.
- **Commits:**
  - `2bf248c1` Pedido 50: o texto do pedido (a linha do projeto);
  - `3f777af4` Pedido 50, Parte A: ADR 0031 (a linha do projeto), registrado antes de qualquer busca, calibração ou arquivo de linha;
  - o commit deste relatório, com o código da Parte B até aqui (o hash está no chat).
- **Merges:** nenhum.
- **Arquivos de handoff:** este relatório. As saídas das contas estão em `data/linha_do_projeto/` (`conferencia.json`, `medidor.json`, `beta_todas.npy`), fora do git.

## Parte 0: a pasta

1. **A pasta do 47** estava em `etapa/modelo1-por-trecho`, sem mudança sem commit e já juntada a `develop` (as duas em `e873d6a6`). A principal está em `etapa/replay-e-radio-que-ensina`, e a do 48 em `etapa/diagnostico-m1`. Nenhuma pasta tem `develop` aberta.
2. **O envio do 49 não foi feito:** `origin/develop` está em `bbff5c97`, e o local em `e873d6a6`, 13 commits à frente. O remoto é ancestral do local, então não divergiu. **Nada foi enviado neste pedido.**
3. **O texto do pedido:** copiado e commitado (`2bf248c1`). O commit guarda LF. Com CRLF, o sha256 bate com o da principal (`dda355a7…6a01a36`). **Apaguei só esse arquivo na principal,** que ficou limpa, na mesma branch.
4. **Os imports e os dados:**
   - o `.venv` da principal, rodando de dentro de `f1-telemetry-analyzer-47\backend`;
   - as junções (`data\ml`, `data\recordings`, `data\cache`) só foram lidas;
   - as gravações da cópia só foram lidas, pelo `carregar_voltas_do_teste` do 49 (via `etapas.sessoes_da_copia`);
   - `data/linha_do_projeto/` entrou no `.gitignore`.
   - **A foto de `data\ml` da principal não foi tirada** antes do trabalho. Nada foi escrito por junção, mas a comparação do fim fica para quando o pedido seguir.
5. **O `acs.exe`** estava fechado antes de cada conta.

## Parte A: o ADR 0031 (`3f777af4`)

- **Commitado antes de qualquer busca, calibração ou arquivo de linha.** O número estava livre em todas as branches, locais e remotas. Uma linha no índice entrou no mesmo commit.
- **Medido antes do registro, só a geometria** (Contexto, item 4 do ADR):
  - a grade de 2 m com o escritor do 47 fecha o raio do arquivo (C01: de 37,7 m para 19,9 m). As quinas da interpolação linear viram raios fechados. É a causa provável dos 85 a 90 m da C1 e da C2;
  - a linha central ondula na subida dos boxes;
  - a `#0013` não fecha na linha de chegada.
- **A codificação registrada:**
  - uma spline cúbica periódica no plano X/Z, que tem a curvatura contínua;
  - os pontos de controle mais densos nas janelas das curvas (40 m antes e depois);
  - uma escada de espaçamento registrada antes: 10/25, 8/20, 6/15 e 5/12,5 m;
  - as restrições por trecho: 90% do menor raio e 110% da maior taxa das 150 voltas, sem os 30 m da emenda da volta;
  - o arquivo do jogo é a curva avaliada direto nas estações do original.
- **O sorteio da ordem** (semente 50): **C0, L1, C0, L2, C0.**
- **Uma diferença do pedido:** ele cita o item 4 do ADR 0029 para a volta válida, mas a regra está no item 5 (o item 4 é o das voltas). O ADR 0031 segue o item 5 e registra isso.

## Parte B.1: a codificação nova e a conferência. **NÃO PASSOU**

O comando: `python -m ml.scripts.linha_do_projeto conferencia`.

| par (m) | genes | C0: p95 da distância | C0: pior raio por trecho | `#0013`: p95 | `#0013`: pior raio |
|---|---:|---:|---|---:|---|
| 10/25 | 331 | 0,013 m | +15,1% (C14) | 0,026 m | +31,5% (C06) |
| 8/20 | 412 | 0,009 m | −8,1% (C04) | 0,017 m | +19,5% (C06) |
| 6/15 | 546 | 0,007 m | −17,6% (C01) | 0,012 m | +6,6% (C13) |
| 5/12,5 | 652 | 0,008 m | −17,9% (C01) | 0,009 m | +5,0% (C02) |

- **A distância passa folgada em todos os degraus:** o limite é 0,10 m em 95% dos pontos.
- **O menor raio por trecho não fica a 5% em nenhum degrau.**
  - A `#0013` converge com o espaçamento mais fino.
  - O C0 piora com o espaçamento fino: sem regularização, a spline passa a seguir o ruído dos pontos do próprio arquivo, e o raio de 3 pontos cai (C01: 37,7 → 30,9 m).
  - O menor raio de um trecho é um valor extremo, decidido por um ponto só.
- **Calculado depois da falha, só para a decisão:** medindo o C0 também pela curvatura de 12 m (o estimador da `#0013` e das restrições), o pior trecho fica em 17,8%, 13,5%, 9,1% e 5,8% nos quatro degraus. Também não passa nos 5%.

### A decisão pedida ao Eduardo (enviada à sessão que me abriu)

- **(a), a minha recomendação:** uma emenda que mede o C0 pela curvatura de 12 m e põe a tolerância do raio em 10%. O primeiro degrau que passa é **6/15 m** (C0 9,1%, `#0013` 6,6%; 546 genes).
- **(b):** outra regra, definida pelo Eduardo.
- **(c):** parar o pedido.

**L1, L2 e os arquivos do jogo não foram feitos,** porque dependem da codificação. Nenhum `fast_lane.ai` novo foi escrito, e nenhuma busca rodou.

## Parte B.2: os três medidores (feito, não depende da codificação)

O comando: `python -m ml.scripts.linha_do_projeto medidor`.

**A conferência:** o M-real dá 85,316 s no C0 e 82,898 s na C3, os mesmos números do pedido 47.

**Spearman da diferença contra o C0, por microssetor,** nas linhas deixadas de fora (4 × 60 pares):

| medidor | ρ juntos | C1 | C2 | C3 | C4 |
|---|---:|---:|---:|---:|---:|
| M-real | 0,458 | 0,54 | 0,73 | 0,26 | 0,21 |
| M-cal | 0,469 | 0,56 | 0,70 | 0,31 | 0,21 |
| **M-v2 (escolhido)** | **0,484** | 0,53 | 0,72 | 0,29 | 0,29 |

- **O esperado (item 10.3, o M-cal escolhido) não se confirmou.** O M-v2 ganhou por pouco.
- **Na volta inteira, a calibração acerta muito mais:** com a linha de fora, o M-cal prevê a C3 0,58 s mais rápida que o C0 (o M-real previa 2,42 s), e no jogo ela foi 0,58 s mais lenta. Mas a regra registrada é o Spearman por microssetor.
- O `medidor.json` traz os `β` por trecho, as previsões e os tempos.

## Parte B.5: o `trocar_linha.ps1` (feito)

- **O script aceita `-Condicao L1` e `-Condicao L2`,** com o manifesto à parte `data\pista_teste\linhas\linha_do_projeto.json`. Ele recusa a condição que não estiver no manifesto. O `linhas.json` do 47 não muda.
- **As mesmas travas:** o jogo fechado, só a cópia, os caches do CSP da cópia apagados e a linha no `registro.csv`.
- **O `registro.py`** aceita L1 e L2 e ganhou os blocos do pedido 50 (`blocos`, `atribuir_aos_blocos`, `vizinhos_de_c0`).

## O código já pronto para quando o pedido seguir (escrito, não rodado nas linhas reais)

- `ml/optimization/codificacao_nova.py`: a codificação, as restrições, a conferência e o reparo do corredor;
- `ml/optimization/medidor_calibrado.py`: os `β`, a linha de fora e o Spearman;
- `ml/optimization/montagem.py`: a montagem por trecho com as emendas de grau 5;
- `ml/optimization/aptidao_do_projeto.py`: a aptidão da L2, com as restrições e a região de confiança como barreira;
- `ml/pista_teste/linha_do_projeto.py`: o escritor pela curva e o veredito da A.2.

**Os testes:** `tests/test_linha_do_projeto.py`, 17 testes sintéticos. Com `test_pista_teste.py`: **43 passam**. A suíte inteira do backend não rodou.

## O que falta

1. **A decisão do Eduardo sobre a conferência** (a, b ou c, acima). Com a emenda (a), ela precisa ser commitada no ADR 0031 antes de seguir.
2. **Depois da decisão:**
   - a L1 e a L2 (B.3), com as figuras;
   - os arquivos e os sha256 (B.4);
   - a Parte C (o que dá para gravar com vários carros da IA), que não foi feita;
   - o roteiro da Parte D: os blocos C0, L1, C0, L2, C0, com a primeira sessão C0, L1, C0 e a segunda L2, C0;
   - a suíte do backend e a foto de `data\ml`.
3. **O envio:** nada foi enviado. O envio do 49 continua pendente (os comandos estão no relatório do 49). Depois dele, os deste pedido:

```powershell
git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47 push -u origin etapa/linha-do-projeto
```

```powershell
git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47 ls-remote origin refs/heads/etapa/linha-do-projeto
```

## Itens para o backlog

1. **O raio de 3 pontos do `fast_lane.ai` é muito sensível ao ruído dos pontos.** Qualquer escritor de linha precisa de uma curva suave no plano X/Z, e não da grade de 2 m interpolada em linha reta.
2. **A linha central do projeto ondula na subida dos boxes** (curvatura de ±0,013 1/m entre 3.860 e 3.940 m).
3. **A conferência por "menor raio do trecho" é um valor extremo.** Um percentil, ou o raio numa janela fixa, seria mais estável.
