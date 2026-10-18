# 0020 — Realidade aumentada no Assetto Corsa: um app Lua do CSP, numa pasta própria do jogo

- **Status:** aceita
- **Data:** 2026-10-15
- **Decisor:** Eduardo

## Contexto

1. **O Modelo 2 precisa chegar ao piloto durante a volta** (ADR 0018). Com um monitor só de 27", o jogo ocupa a tela inteira enquanto o piloto anda, e o app no Windows não é visto. Hoje as frases do coach só aparecem no app e no replay.
2. **O plano do Eduardo (14/10):** a realidade aumentada é como o rádio dos engenheiros da F1. Uma mensagem curta, em voz e na tela, no momento em que o piloto pode ouvir.
3. **A regra do projeto** desde o começo é não mexer nos arquivos do jogo. Um app dentro do jogo exige uma exceção, e ela precisa ter limite claro.
4. **O que o jogo oferece,** lido no pedido 29 (Parte A), sem instalar nada:
   - **as versões:** Custom Shaders Patch (CSP) 0.2.11, build 3465, instalado pelo Content Manager 0.8.2895.40668;
   - **a pasta `apps\lua`:** existe e já tem seis apps de terceiros;
   - **a API Lua do CSP** (`extension\internal\lua-sdk\ac_apps\lib.lua`):
     - janela transparente na tela;
     - HTTP para `127.0.0.1:8000`, no máximo duas requisições ao mesmo tempo;
     - som a partir de um arquivo;
     - o estado do carro;
     - desenho 3D na pista;
   - **voz:** o CSP não tem síntese de fala. O Windows tem vozes em pt-BR (Maria, SAPI 5; Maria e Daniel, OneCore).
5. **O que o backend já entrega:**
   - as frases do coach em `/api/live/coach`, até 3 por volta;
   - o resumo de fim de volta, só pelo WebSocket.

## Decisão

1. **A realidade aumentada é um app Lua do CSP,** com o código versionado no repositório, em `tools/csp_app/`.
2. **A exceção à regra do jogo tem este limite:**
   - **só uma pasta:** só é criada ou mudada a pasta do app, `<pasta do jogo>\apps\lua\<nome do app>\`;
   - **por script:** a instalação e a remoção são feitas por dois scripts do repositório, que só tocam nessa pasta, e quem os roda é o Eduardo;
   - **nada mais:** nenhum outro arquivo do jogo, nenhuma configuração do CSP e nenhum outro app é tocado;
   - **o Claude Code** escreve o app e os scripts, mas não grava na pasta do jogo.
3. **O app só lê e só conversa com o backend local:**
   - lê o estado do carro e fala com `127.0.0.1:8000`, respeitando o limite de duas requisições;
   - não muda o carro, os controles nem o comportamento do jogo;
   - é para treino fora do modo online.
4. **O rádio segue as regras do coach** (ADR 0012 e 0016):
   - **o que diz:** diferença medida contra uma volta real, nunca ganho prometido;
   - **quanto:** no máximo as 3 frases por volta que o coach já gera, mais o resumo na linha de chegada;
   - **quando:** só em trechos de reta, fora das curvas, como um engenheiro que não fala na freada.
5. **A mensagem é montada uma vez, no backend:**
   - o texto vai em português, com acento, nomes técnicos e lado por extenso (ADR 0003);
   - o áudio é gerado pela voz pt-BR do Windows;
   - o app do jogo e a tela Ao vivo mostram a mesma mensagem.
6. **Cada mensagem entregue fica registrada,** com a hora, a volta e o ponto da pista, fora da pasta de gravações. Isso permite medir depois se a volta seguinte melhorou no trecho citado, que é a avaliação do Modelo 2.
7. **Versão do CSP testada:** 0.2.11. Se a API mudar numa atualização, o app avisa e fica calado.

## Consequências

- **A regra "não mexa nos arquivos do jogo" ganha uma exceção,** só para a pasta do app e só pelos scripts. Ela é reversível: o script de remoção apaga só essa pasta.
- **O Eduardo precisa:**
  - rodar o script de instalação;
  - ligar o app uma vez dentro do jogo;
  - abrir o backend antes do jogo.
- **Nenhum canal novo de dado é necessário.** O rádio usa o que o coach já calcula.
- **Desenho 3D na pista** (marcas de freada, a linha de referência) fica possível com a mesma exceção, mas não entra agora. Cada uso novo do app vai para um pedido próprio.
