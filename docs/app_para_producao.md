# O app para produção: o que ele faz e onde está cada alteração

- **Data:** 01/11/2026. **Fonte:** o código e os commits das branches citadas. O que depende do jogo está marcado como não testado.
- **Para que serve:** dizer o que o app faz hoje, em que versão está cada alteração e o que falta para gerar a próxima versão.

## 1. O que o app faz

O **Automobilista Telemetria** é um app de Windows (Electron e backend em Python, tudo local, em `127.0.0.1`) para o Assetto Corsa com o Custom Shaders Patch. Ele tem duas partes, instaladas separadamente: o app do Windows e o app do jogo.

| parte | o que faz |
|---|---|
| **Gravação** | grava as voltas do jogo, com o piloto e a IA separados, na pasta de dados |
| **Coach ao vivo** | mede a volta na geometria oficial contra uma volta real de referência e, nos microssetores de foco, publica no máximo 3 frases por volta |
| **Rádio** | leva ao piloto a frase do coach, o resumo na linha e, a cada 3 voltas válidas, a análise, em cartão e em voz, só nas retas |
| **Replay da curva** | mostra a curva citada pelo rádio, com a sua linha e a da referência, as freadas, as mínimas e o tempo |
| **Tela Sessões** | as sessões, a tendência e as gravações que ainda não entraram no relatório |
| **Tela Ao vivo** | o rádio, a volta com o fantasma e o estado dos canais |
| **Tela Volta** | uma volta gravada com a referência, na geometria oficial |
| **Tela Evolução** | a tendência e a perda e a técnica por curva entre as sessões |
| **Tela Coleta de dados** | a coleta, o store e a rodada do coach |
| **Tela Sistema** | a mensagem de teste do rádio, a depuração e o guia visual |
| **App do jogo** (`Rádio do engenheiro`) | 4 janelas no jogo: o rádio, o minimapa, o mapa aproximado e o replay. Só lê o jogo e o backend, e só grava na própria pasta |

**Fora do app, só em scripts:** o Modelo 2 (`backend/ml/modelo2/`) e a M1 (`backend/ml/modelo_carro/`). Nenhuma tela, rota ou serviço do app usa os dois em execução. A M1 não foi aprovada.

## 2. Onde está cada alteração

| alteração | 0.5.0 instalada (`825ef60d`, 25/10) | `develop` (`4b6ca40c`) | `etapa/visuais-do-radio` |
|---|---|---|---|
| Rádio com análise, voz com unidades e replay da curva (pedidos 33 a 36) | sim | sim | sim |
| Limpeza do código sem uso e defeitos do backlog (pedido 40), como o corte no reinício e o cache da pista | **não** | sim | sim |
| M1, fora do app (pedidos 37 e 39) | **não** | sim | sim |
| Números da voz, 4 visuais e grade da sessão (pedido 43) | **não** | **não** | sim, sem teste no jogo |
| Modelo 2, fora do app (pedido 38, sem a H.4) | sim | sim | sim |
| Número da versão do app do Windows | `0.5.0-radio-e-replay` | `0.5.0-radio-e-replay` | `0.5.0-radio-e-replay` |
| App do jogo que acompanha | 0.4.0 | 0.4.1 | 0.4.2 |

**`etapa/visuais-do-radio` tem tudo** desde 01/11, quando o pedido 38 entrou em `develop` e `develop` entrou nela. **O número não acompanha:** os três mostram `0.5.0-radio-e-replay`, com conteúdos diferentes.

## 3. O que falta para a próxima versão

1. **Testar o pedido 43 no jogo.** O código Lua novo nunca rodou, e o FPS não foi medido. Esta também é a primeira vez do app no CSP 0.3.1.
2. **Fazer o merge do pedido 43 em `develop`.**
3. **Trocar o número da versão nos 3 pontos, juntos:** `desktop/package.json` (`version`), `backend/main.py` (`BACKEND_PHASE_VERSION`) e `desktop/main.js` (`EXPECTED_BACKEND_VERSION`). Os dois últimos têm de ser iguais. A próxima é a 0.6.0.
4. **Gerar o instalador,** só quando o Eduardo pedir, com `npm run dist:win` na pasta `desktop`. O pacote não leva o app do jogo: o `instalar.ps1` é rodado à parte.

## 4. Riscos conhecidos

- **O app do jogo 0.4.1 ou mais antigo com o backend novo dá erro na janela do replay** nas frases do coach, que vêm sem o traçado. Instale o 0.4.2 junto.
- **O app do jogo 0.4.2 com o backend da 0.5.0** funciona, sem os visuais e sem a grade.
- **Os detectores do Modelo 2 não foram validados:** o merge do pedido 38 saiu sem a H.4, por decisão do Eduardo, e a precisão e a revocação ficam para a Parte E do pedido 42. Nada do app os usa em execução.
- **No backlog, sem pedido ainda:** as voltas de tempo normal marcadas como incompletas (9 das 19 em 21/10), os buracos na numeração das voltas e o erro "attached to a different loop" do WebSocket, que também aparece no app instalado.
