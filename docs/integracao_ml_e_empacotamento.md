# Integração do modelo ao software, empacotamento e versionamento

**Data:** 25/08/2026 – 02/09/2026 · **Escopo:** `backend/ml/export/`, `backend/core/assisted_analysis/`, `frontend/src/store/`, `desktop/`, empacotamento

> Regra deste documento, herdada de [`auditoria_ml.md`](auditoria_ml.md): nenhum
> número aqui vem de leitura de código. Cada um saiu de uma execução — endpoint
> HTTP, saída de teste, listagem do pacote ou do executável instalado. Onde algo
> **não** foi medido, está escrito que não foi.

O que a auditoria deixou em aberto na §6.2 era o caminho entre o laboratório e o
software: a LSTM, a busca evolutiva e o simulador quase-estacionário produziam um
traçado ótimo que nada fora de `backend/ml/` lia. Este documento registra o
fechamento desse caminho, os quatro defeitos encontrados no percurso e o estado
final verificado.

## Resumo das alterações

| Commit | Assunto | Arquivos |
|---|---|---:|
| `43326fe` | Segundo alvo do coach, exportado do ML | 17 |
| `dd9ba8d` | Feed do replay parava de duplicar eventos | 2 |
| `3ba0244` | Traçado passa a ser embarcado onde o backend procura | 2 |
| `ed38b18` | Painel de versão e botão de atualizar | 9 |
| `b1dc250` | Módulo faltante no pacote | 1 |

Fora de commit: correção do refspec do `origin` e vínculo de upstream da branch
`develop` (§7), por serem configuração local do repositório.

---

## 1. Ponto de partida

O coach ao vivo media cada microsetor contra o modelo de referência do piloto —
"quão rápido *você* já foi aqui". A pergunta "quão rápido esta curva *é*" já
tinha resposta, produzida offline pela busca evolutiva, mas ela morria em
`backend/ml/`: nenhum módulo do app importava aquele resultado.

## 2. O segundo alvo do coach — `43326fe`

O desenho da integração está documentado em detalhe na §6.1 da auditoria,
incluindo as três decisões que a sustentam: o que embarca é aritmética e não a
rede; o alvo do ML não substitui o do piloto; e a conversão entre o eixo de metros
do ML e o eixo de progresso do coach usa o vetor `p` gravado no cache, porque os
dois eixos divergem em até 25 m.

O que este documento acrescenta é a verificação ponta a ponta, feita depois:

| | |
|---|---|
| Volta testada | L10, `vhe_interlagos`, 1:24.861 |
| Eventos gerados | 6 |
| Eventos com alvo do ML | **6 / 6** |
| Rádio de fim de volta | traz a comparação contra o traçado |

Duas correções entraram junto:

**Teto de épocas.** Era 60, e a geradora terminava na época 60 com a melhor
validação sendo a última — quem parava o treino era o orçamento, não o sinal.
Passou para 200, com `patience` decidindo.

**Legibilidade do feed.** O painel despejava o JSON cru do evento. Passou a
mostrar `VOCE / MELHOR / OTIMO` e o número do microsetor. `finiteOrNull` existe
porque `Number(null)` é `0`, e um alvo ausente virava um `0.00s` convincente na
tela.

### 2.1 O que a verificação mostrou sobre o alvo

Os seis eventos da volta L10, como aparecem no painel:

| Setor | Distância | Você | Melhor | Ótimo |
|---:|---:|---:|---:|---:|
| 5 | 434 m | 2,02 s | 1,95 s | 2,08 s |
| 6 | 508 m | 1,44 s | 1,29 s | 1,77 s |
| 17 | 1301 m | 1,19 s | 1,11 s | **1,49 s** |
| 19 | 1445 m | 1,85 s | 1,78 s | **1,60 s** |
| 31 | 2312 m | 2,41 s | 2,34 s | 2,45 s |
| 33 | 2456 m | 2,35 s | 2,23 s | 2,17 s |

Em **4 dos 6 eventos o alvo do ML é mais lento que o piloto já andou**. No setor
17 ele pede 0,30 s a mais que o melhor do piloto. Apenas os setores 19 e 33 têm o
ótimo à frente — e no 19 a diferença é real: 1,60 s contra 1,78 s.

Isso não é defeito da integração; é a §4.1 da auditoria aparecendo na tela. O
artefato usado nesta verificação foi gerado com `--force`, contornando a recusa
do exportador, e simula 85,109 s — mais lento que **40 das 113 voltas gravadas**.
O caminho está correto; o conteúdo que trafega por ele, não.

## 3. O feed que repetia a volta — `dd9ba8d`

Reassistir a mesma volta empilhava uma segunda cópia dos eventos: seis viravam
doze, depois dezoito.

`coachEventsUpTo` reconta do início da volta a cada movimento do relógio, então
rebobinar zera a contagem e a volta fala tudo de novo — o que é o comportamento
certo. O feed é que nunca era limpo.

`feedAfterRelease` decide entre acrescentar e reconstruir pelo único sinal que
distingue os dois casos: contagem menor do que já foi dito significa que o
relógio andou para trás por cima de eventos já falados.

```js
if (release.count < alreadySaid) {
  return events.slice(0, release.count).map(normalizeCoachingEvent).reverse();
}
```

Limpar de vez estaria errado para o scrub: arrastar para o meio da volta ainda
precisa mostrar as curvas já passadas. O primeiro corte desta correção esvaziava
o feed e foi reprovado por um teste antes de sair.

Um replay novo também passou a começar com o painel vazio, em vez de herdar o que
a sessão ao vivo — ou o replay anterior — tinha dito.

**Um teste pré-existente afirmava o bug.** `says them again after the slider goes
back` exigia dois eventos depois do rewind: são o mesmo evento duas vezes. A
intenção registrada pelo autor ("a segunda passagem não pode ficar mais silenciosa
que a primeira") continua valendo e continua testada — o evento é re-emitido,
`coachEmittedCount` volta a subir — mas sem cópia empilhada.

| | |
|---|---|
| Testes de frontend | 135 passando |
| Testes novos | 4 |
| Teste com asserção corrigida | 1 |

Verificado também na interface: 6 eventos ao fim da primeira volta → **0 ao
rebobinar** → 6 ao fim da segunda.

## 4. O traçado que viajava e não era lido — `3ba0244`

O traçado estava sendo embarcado no executável do backend via `--add-data` do
PyInstaller. **O executável nunca o lia.**

O PyInstaller põe o arquivo em `_MEIPASS`. Mas `desktop_backend_runner.py:40`
monta a raiz de recursos a partir do diretório de trabalho quando congelado, e o
app empacotado a sobrescreve com `AT_BACKEND_RESOURCE_ROOT`, apontando para a
pasta `resources` do Electron. Nenhum dos dois é `_MEIPASS`.

Medido, não deduzido — rodando o exe de um diretório vazio:

```
_MEI308002/data/reference_models/vhe_interlagos.optimal.json   presente
vazio/data/reference_models                                    não existe
exe_runtime/data/reference_models                              não existe
→ coach não encontrou nada
```

A correção move o embarque para o `extraResources` do electron-builder, que põe o
arquivo ao lado do exe:

```json
{ "from": "../data/reference_models",
  "to": "data/reference_models",
  "filter": ["*.optimal.json"] }
```

O filtro faz a mesma separação que o `.gitignore` já fazia: leva o traçado ótimo,
deixa o modelo do piloto, que é dado de execução e vive no `userData`.

Verificado depois, com o backend empacotado rodando sobre
`win-unpacked/resources`: **6/6 eventos com `optimalSeconds`**, números idênticos
aos do backend de desenvolvimento.

### 4.1 O `.spec` é saída, não fonte

`build_backend.ps1` chama o PyInstaller com flags e `--specpath`, o que
**regenera** `automobilista-backend.spec` a cada build. Qualquer edição manual
naquele arquivo é perdida — e é por isso que `*.spec` está no `.gitignore`. O
comentário que ficou no lugar do `--add-data` guarda esse motivo, porque a
diferença entre "entrou no pacote" e "é lido" não se vê olhando o build passar.

## 5. Versionamento e atualização — `ed38b18`

Duas coisas se movem separadas neste projeto: o aplicativo sai de um commit; o
traçado sai de uma busca offline e viaja como arquivo. Reconstruir o app não
regenera o traçado, e regenerar o traçado não reconstrói o app. Um número único
de versão seria mentira sobre um dos dois.

### 5.1 Carimbo de build

`desktop/scripts/stamp-build-info.js` grava commit, branch, data e estado da
árvore no momento do build. O arquivo viaja dentro do asar, que é o que o torna
confiável: não consegue divergir do código ao lado do qual foi carimbado. Build de
árvore suja diz isso — "três commits atrás" é útil; "três commits atrás mais o que
estava sem commitar" é a versão honesta.

`desktop/build-info.json` está no `.gitignore`: é gerado a cada build e datado.

### 5.2 Serviço de versão

`desktop/version-service.js` reúne três coisas e degrada para "desconhecido" em
vez de lançar exceção:

| Fonte | O que responde |
|---|---|
| `build-info.json` (asar) | qual commit o app instalado carrega |
| `resources/data/reference_models/*.optimal.json` | qual traçado o coach usa |
| repositório, quando existe | a régua para os dois |

O traçado é comparado **por conteúdo** (digest SHA-256 truncado), não por data: um
traçado regerado de uma busca idêntica é o mesmo alvo mesmo com timestamp novo, e
um copiado sem ser regerado tem data velha e pode estar em dia.

Duas distâncias distintas são calculadas:

- `repo.behind` — a cópia de trabalho contra seu upstream;
- `buildBehind` — o **build instalado** contra a cópia de trabalho. Quem puxou e
  não reconstruiu está atrás por este número mesmo com o repositório em dia.

### 5.3 Botão de atualizar

`update:run` faz `pull --ff-only` e reconstrói frontend e backend, reportando cada
passo por `update:progress`. Recusa começar com árvore suja — rebasear por cima de
trabalho não commitado é como se perde trabalho — e para no primeiro erro, porque
código puxado sem backend reconstruído é pior que nenhuma atualização.

**Limite conhecido:** depende do repositório clonado e do toolchain (git, Node,
Python, PyInstaller). Em qualquer outra máquina o painel diz isso em vez de fingir
que poderia atualizar. E ele atualiza o repositório e reconstrói — **não substitui
a instalação**; esse passo permanece manual.

## 6. O módulo que não entrou no pacote — `b1dc250`

`electron-builder` só leva o que está em `build.files`, e `version-service.js` não
estava. `main.js` faria `require` dele e quebraria na inicialização do app
instalado — o painel de versão nunca abriria.

Não aparece em teste algum nem no app de desenvolvimento, onde o `require` resolve
pelo disco. Só se vê listando o conteúdo do asar depois do empacotamento.

Foi o **segundo** defeito da sessão que existe apenas no empacotamento — o
primeiro foi o traçado da §4. Ambos passaram por build verde.

## 7. Configuração do git

Ao verificar se o software estava atualizado, o painel reportou "sem upstream".
A causa não era a branch nunca ter sido enviada: `origin/develop` **existe** no
GitHub, em `dd9ba8d`. O refspec do clone é que a escondia.

```
antes:  +refs/heads/main:refs/remotes/origin/main
depois: +refs/heads/*:refs/remotes/origin/*
```

O `git fetch` retornava "ok" e mesmo assim `git branch -r` conhecia apenas
`origin/main`. Restaurado o refspec padrão, o fetch trouxe cinco branches que o
clone ignorava, e `develop` foi vinculada a `origin/develop`.

Estado resultante: **3 commits à frente** do remoto — `3ba0244`, `ed38b18` e
`b1dc250`. O push não foi executado.

## 8. Build e instalação

| | |
|---|---|
| Instalador | `Automobilista-Telemetria-Setup-0.1.7-phase-16.exe` · 248 MB |
| Backend empacotado | 152 MB, **sem torch** |
| Traçado nos recursos | 2736 bytes |
| Modelo do piloto | fora do pacote (vai para `userData`) |

A ausência do torch foi verificada no TOC do PyInstaller: as duas ocorrências que
casam com "torch" são `sympy.printing.pytorch`, não o PyTorch.

A instalação anterior era de **19/08** e não tinha sequer a pasta
`data/reference_models` — o coach ali rodava só com o melhor do próprio piloto.
Construir não instala: o instalador foi executado (`/S`) e a instalação
substituída.

## 9. Estado final verificado

| | |
|---|---|
| App instalado | `0.1.7-phase-16` @ `b1dc250`, árvore limpa |
| Carimbo no asar instalado | confere com o HEAD |
| `version-service.js` no asar | presente |
| Traçado instalado | `vhe_interlagos`, 2736 bytes |
| Atrás do repositório local | 0 commits |
| Contra `origin/develop` | 3 à frente |
| Testes de frontend | 135 passando |
| Typecheck | limpo |

O caminho completo foi exercitado num executável real:
`resources/data/reference_models/vhe_interlagos.optimal.json` →
`find_optimal_line` → `attach` → coach → API, com os mesmos números do backend de
desenvolvimento.

## 10. O que continua aberto

**O traçado embarcado é o forçado.** 85,109 s, mais lento que 40 das 113 voltas
gravadas. O instalador atual entrega um alvo de coaching que o piloto já bate na
maioria dos microsetores. O painel de versão dirá corretamente "em dia", porque a
versão confere — o que não presta é o conteúdo. Ver auditoria §4.1.

**O artefato forçado está versionado.** `data/reference_models/vhe_interlagos.optimal.json`
está rastreado, e o `.gitignore` foi escrito para mantê-lo:

```
data/reference_models/*.json
!data/reference_models/*.optimal.json
```

A política está certa — modelo do piloto é dado de execução, traçado é artefato de
distribuição. O conteúdo específico é que não deveria estar ali enquanto não
superar o piloto.

**A severidade ainda vem do alvo do piloto.** A barra de cada evento mede a perda
contra o melhor dele, não contra o ótimo — decisão deliberada, para o limiar
continuar adaptativo. Por isso o setor 17 aparece com severidade baixa mesmo com
0,30 s de diferença para o traçado.

**O rádio fica mudo no replay.** O endpoint devolve a fala de fim de volta, mas
`SessionLapsPanel` só repassa `coachEvents` ao replay e descarta `speech`.
Anterior a este trabalho; ao vivo a fala aparece normalmente.

**O "3,56 s contra o traçado ótimo" é enganoso.** Soma apenas as perdas positivas
e ignora os microsetores em que o piloto está à frente do traçado.

**Os 3 commits não foram enviados** ao `origin/develop`.
