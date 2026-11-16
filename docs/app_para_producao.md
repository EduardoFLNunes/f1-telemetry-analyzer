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
| **Engenheiro** (0.9.0) | a lista dos trechos com perda contra a volta do modelo e, antes da curva, o aviso pelo marco da pista ("Curva 1: freie 10 metros depois da placa de 100"), na voz (C01, C04 e C06) e na janela do jogo, com a conferência da dica (ADR 0033) |
| **Replay da curva** | mostra a curva citada pelo rádio, com a sua linha e a da referência, as freadas, as mínimas e o tempo |
| **Tela Sessões** | as sessões, a tendência e as gravações que ainda não entraram no relatório |
| **Tela Ao vivo** | o rádio, a volta com o fantasma e o estado dos canais |
| **Tela Volta** | uma volta gravada com a referência, na geometria oficial |
| **Tela Evolução** | a tendência e a perda e a técnica por curva entre as sessões |
| **Tela Coleta de dados** | a coleta, o store e a rodada do coach |
| **Tela Sistema** | a mensagem de teste do rádio, a depuração e o guia visual |
| **App do jogo** (`Rádio do engenheiro`) | 5 janelas no jogo: o rádio, o minimapa, o mapa aproximado, o replay e, desde o 0.7.0, o engenheiro, com a marca do ponto da ação no asfalto. Só lê o jogo e o backend, e só grava na própria pasta |

**Fora do app, só em scripts:** o Modelo 2 (`backend/ml/modelo2/`) e a M1 (`backend/ml/modelo_carro/`). Nenhuma tela, rota ou serviço do app usa os dois em execução. A M1 não foi aprovada.

## 2. Onde está cada alteração

| alteração | 0.7.0 (`60d3f9e7`, 07/11) | 0.8.0 instalada (`46e8db8`, 15/11) | `etapa/engenheiro` (a 0.9.0, pedido 52, antes do merge) |
|---|---|---|---|
| Rádio com análise, voz com unidades e replay da curva (pedidos 33 a 36) | sim | sim | sim |
| Limpeza do código sem uso e defeitos do backlog (pedido 40), como o corte no reinício e o cache da pista | sim | sim | sim |
| M1, fora do app (pedidos 37 e 39) | sim | sim | sim |
| Números da voz, 4 visuais e grade da sessão (pedido 43) | sim | sim | sim |
| O rádio que diz onde e por quê, o replay de perto, os boxes e o botão "Abrir no app" (pedido 45) | sim, sem as decisões de 12/11 (o resumo em 8,0 s e "contra quem") | sim | sim |
| A voz no app instalado (o `voz.ps1` no pacote, pedido 45) | sim | sim | sim |
| Modelo 2, fora do app (pedido 38, sem a H.4) | sim | sim | sim |
| A volta de referência do app é a volta do modelo; a volta da IA sai do app; "da referência" e "Melhor da sessão" (pedido 51, ADR 0032) | não | sim | sim |
| O engenheiro: a lista, o aviso antes da curva pelo marco, os blocos de voz, a janela "Engenheiro" e a marca na pista (pedido 52, ADR 0033) | não | não | sim |
| Número da versão do app do Windows | `0.7.0-radio-que-ensina` | `0.8.0-volta-do-modelo` | `0.9.0-engenheiro` |
| App do jogo que acompanha | 0.5.0 | 0.6.0 | 0.7.0 |

**Em 15/11/2026, 17:23, a 0.8.0 (`46e8db8`) foi instalada por cima da 0.7.0** (pedido 51): a coluna da 0.7.0 fica como histórico.

**`develop` tem tudo o que a 0.7.0 instalada tem e mais.** O que os pedidos 46 a 49 fizeram (a M1 v2 e o Modelo 1) fica fora do app. As alterações estão centralizadas desde 01/11.

## 3. O que falta para a próxima versão

1. **Olhar no jogo o que ficou sem confirmação:** a grade nos boxes, o cartão da mensagem de teste e os visuais na tela. O teste de 01/11, no CSP 0.3.1, não teve erro de Lua, e os números do replay batem com a voz e com o cartão.
2. **Gerar o instalador,** só quando o Eduardo pedir, com `npm run dist:win` na pasta `desktop`. O pacote não leva o app do jogo: o `instalar.ps1` é rodado à parte.

**Numa próxima versão,** troque o número nos 3 pontos, juntos: `desktop/package.json` (`version`), `backend/main.py` (`BACKEND_PHASE_VERSION`) e `desktop/main.js` (`EXPECTED_BACKEND_VERSION`). Os dois últimos têm de ser iguais.

## 4. Riscos conhecidos

- **O engenheiro precisa de três arquivos fora do git** (pedido 52): a volta do modelo, `vhe_interlagos.marcos.json` (gere com `python -m core.engenheiro.marcos <pasta da pista>`, só leitura) e `vhe_interlagos.ruido_por_trecho.json` (`python -m core.engenheiro.preparar ruido <resultado do 50>`). Sem um deles, o engenheiro fica calado e o rádio é o da 0.8.0. O instalador os leva pelos filtros do `extraResources`.
- **O app do jogo 0.6.0 com o backend 0.9.0** funciona, sem a janela do engenheiro; os avisos pela voz chegam pelo rádio. O 0.7.0 com o backend 0.8.0 mostra "Engenheiro: lendo a lista" (a rota não existe).
- **A volta do modelo é um arquivo fora do git** (`data/reference_models/vhe_interlagos.volta_do_modelo.json`). O instalador o leva da pasta do repositório; sem ele, o pacote sai sem a volta de referência, e o app oferece só "Sua melhor volta". Gere de novo com `python -m ml.scripts.volta_do_modelo` (pedido 51).

- **O app do jogo 0.4.1 ou mais antigo com o backend novo dá erro na janela do replay** nas frases do coach, que vêm sem o traçado. Instale o 0.4.2 junto.
- **O app do jogo 0.4.2 com o backend da 0.5.0** funciona, sem os visuais e sem a grade.
- **Os detectores do Modelo 2 não foram validados:** o merge do pedido 38 saiu sem a H.4, por decisão do Eduardo, e a precisão e a revocação ficam para a Parte E do pedido 42. Nada do app os usa em execução.
- **No backlog, sem pedido ainda:** a grade e os visuais sem confirmação no jogo, as voltas de tempo normal marcadas como incompletas (9 das 19 em 21/10), os buracos na numeração das voltas e o erro "attached to a different loop" do WebSocket, que também aparece no app instalado.
