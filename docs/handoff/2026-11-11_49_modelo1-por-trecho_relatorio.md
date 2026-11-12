# Relatório do pedido 49: o Modelo 1 por trecho

- **Pedido:** `docs/prompts/2026-11-11_49_modelo1-por-trecho.md`.
- **Situação:** **parado antes da Parte A, esperando uma decisão sua sobre a regra da A.3** (veja "A decisão que falta"). Nenhuma conta foi feita nas gravações.
- **Pasta:** `C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47`.
- **Branch:** `etapa/modelo1-por-trecho`, a partir de `develop` em `bbff5c97` (com os pedidos 47 e 48).
- **Commits:**
  - `63ad8c91` Pedido 49: o texto do pedido (o Modelo 1 por trecho);
  - `c9daed61` Pedido 49, Parte 0: data/modelo1_por_trecho/ no .gitignore;
  - o commit deste relatório (o hash fica no chat).
- **Merges:** nenhum.
- **Arquivos de handoff:** `docs/handoff/2026-11-11_49_modelo1-por-trecho_relatorio.md` (este).

## Parte 0: a pasta

1. **A pasta do 47** estava na branch `etapa/linha-gerada-no-jogo`, sem mudança sem commit e já juntada a `develop`.
   - `develop` local e `origin/develop` estavam em `bbff5c97`.
   - Nenhuma pasta tinha `develop` aberta: a principal está em `etapa/replay-e-radio-que-ensina`, a do 47 estava na branch dela e a do 48 em `etapa/diagnostico-m1`.
2. **O texto do pedido:**
   - copiado para a pasta do 47 e commitado (`63ad8c91`). O commit guarda o texto com fim de linha LF (`core.autocrlf=true`);
   - **na pasta principal havia duas cópias do mesmo texto:**
     - `2026-11-11_49_modelo1-por-trecho.md`, com CRLF (sha256 `c1c544de…4cb8`). Ele é igual ao texto do commit com CRLF e à cópia de trabalho da pasta do 47;
     - `2026-11-11_49_modelo1-por-trecho-1.md`, com LF (sha256 `14115b89…5d85`). Ele é igual, byte a byte, ao texto guardado no commit.
   - **Apaguei as duas, e só elas,** depois de conferir os dois sha256. As duas voltam do commit, e nada se perdeu. A principal ficou limpa, na branch `etapa/replay-e-radio-que-ensina`.
3. **A branch:** `git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47 switch -c etapa/modelo1-por-trecho develop`, sem recusa.
4. **Os imports e os dados:**
   - uso o `.venv` da principal, rodando de dentro de `f1-telemetry-analyzer-47\backend`. `core` e `ml` vêm da pasta do 47 (conferi `core.__file__` e `ml.__file__`), e `config.repo_root()` é a pasta do 47. Nada foi instalado;
   - as três junções do pedido 47 continuam lá, só para leitura: `data\recordings`, `data\ml` e `data\cache`;
   - **a saída deste pedido** vai para `data\modelo1_por_trecho\`, uma pasta de verdade. Ela entrou no `.gitignore` (`c9daed61`), e o `git check-ignore` confere;
   - **a foto antes:** 932 arquivos (nome, tamanho e data) da principal, em `data\modelo1_por_trecho\foto_antes.tsv`: 616 em `data\ml`, 3 em `data\cache` e 313 em `data\recordings`. A comparação fica para o fim.
5. **A cópia da pista** continua instalada. Nenhum script de `tools\pista_teste\` foi rodado, e a pasta do jogo não foi tocada.
6. **O processador:** o `acs.exe` estava fechado.

## O envio ao GitHub

**O controle de permissões da sessão recusou o envio** da branch depois da Parte 0. Antes, conferi o que iria:
- só o texto do pedido e duas linhas no `.gitignore`;
- nada acima de 50 MB, nenhum segredo, nenhuma gravação, nenhum `.ai` e nada de `data/modelo1_por_trecho`.

**Os comandos para você rodar pelo terminal:**

```powershell
git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47 push -u origin etapa/modelo1-por-trecho
git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47 rev-parse HEAD
git -C C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47 ls-remote origin refs/heads/etapa/modelo1-por-trecho
```

O hash do `rev-parse` e o do `ls-remote` têm de ser iguais. É uma branch nova, então o envio não reescreve nada.

## A decisão que falta: o p-valor por permutação da A.3

**O que a A.3 pede:** em cada trecho, a diferença das medianas, com o IC por bootstrap e "o p-valor por permutação"; depois, Holm a 5% entre os 15 trechos de cada comparação.

**O problema, achado antes de qualquer conta nas gravações:** se a estatística da permutação for a própria diferença das medianas, **nenhum trecho pode sair como ganho ou perda**, em nenhuma comparação.
- A mediana só depende dos valores do meio. Muitas divisões das voltas entre os dois grupos dão a mesma diferença das medianas, então o p-valor tem um piso.
- **Com separação completa** (todas as voltas de um grupo mais rápidas que todas as do outro), o menor p-valor exato fica em:
  - **0,0117 com 7 contra 7 voltas** (40 das 3.432 divisões empatam ou passam);
  - **0,0121 com 7 contra 4** (o C0 final; 4 das 330 divisões).
- **Pelo Holm com 15 trechos, o primeiro limite é 0,05 / 15 = 0,0033.** Como o menor p-valor possível passa disso, o Holm para no primeiro trecho, e tudo vira "empate".
- **Com a diferença das médias como estatística da permutação,** o piso cai para:
  - **0,0006 com 7 contra 7** (2 das 3.432 divisões);
  - **0,0030 com 7 contra 4** (1 das 330).

  Com ela, o teste consegue separar, mas contra o C0 final só passa um trecho com separação completa, porque 0,0030 fica logo abaixo de 0,0033.

**A conta** (dados sintéticos, sem nenhuma gravação), para conferir:

```python
import itertools, numpy as np
def p_exato(a, b, estat):
    x = np.r_[a, b]; obs = estat(a, b); n = len(a); cont = tot = 0
    for idx in itertools.combinations(range(len(x)), n):
        m = np.zeros(len(x), bool); m[list(idx)] = True
        cont += abs(estat(x[m], x[~m])) >= abs(obs) - 1e-12; tot += 1
    return cont / tot
rng = np.random.default_rng(0)
a, b = rng.normal(1, 0.01, 7), rng.normal(0, 0.01, 4)   # separacao completa
print(p_exato(a, b, lambda a, b: np.median(a) - np.median(b)))  # 0,0121
print(p_exato(a, b, lambda a, b: np.mean(a) - np.mean(b)))      # 0,0030
a, b = rng.normal(1, 0.01, 7), rng.normal(0, 0.01, 7)   # 7 contra 7
print(p_exato(a, b, lambda a, b: np.median(a) - np.median(b)))  # 0,0117
print(p_exato(a, b, lambda a, b: np.mean(a) - np.mean(b)))      # 0,0006
```

**As opções:**
1. **A permutação usa a diferença das médias** (exata, todas as divisões). A diferença das medianas continua sendo o efeito, o sinal da regra e o IC por bootstrap. É a que eu recomendo: o teste de permutação vale para qualquer estatística, e esta é a que consegue separar com 7 e 4 voltas.
2. **A permutação usa a diferença das medianas,** como está escrito. Por construção, não há ganho, perda nem candidata, e a Parte C fica toda com a linha da IA. Eu registraria isso no ADR antes das contas.
3. Outra regra que você preferir.

Nenhuma regra foi escrita nem commitada ainda. O ADR 0030 (o número está livre: o 0027 está na branch do 45, e nenhuma branch tem um 0030) sai com a sua resposta, antes de qualquer conta.

## O que falta

- **A sua decisão** sobre o p-valor da A.3.
- Depois dela: o ADR 0030 (Parte A, commitado antes das contas), a conta por trecho (Parte B), a referência por trecho (Parte C), os testes (Parte D), a documentação (Parte E), o merge em `develop` e o envio.
- O envio da branch depois da Parte 0 (os comandos acima).
