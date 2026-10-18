# Realidade aumentada: o rádio do engenheiro (pedido 31, ADR 0020)

O rádio leva o que o coach já decide até o piloto, durante a volta, com o jogo em tela cheia: uma mensagem curta, num cartão dentro do jogo e em voz, no momento em que dá para ouvir. É o jeito de o Modelo 2 chegar ao piloto (ADR 0018). O rádio não decide nada: quais frases saem, o limite de 3 por volta, o foco e o limiar continuam no coach.

## 1. Como funciona

1. **O coach ao vivo** mede a volta na geometria oficial e, quando um microssetor de foco passa o limiar, publica uma frase (`coaching_event`).
2. **O backend monta a mensagem uma vez** (`backend/core/radio/texto.py`):
   - **o cartão:** a curva e o lado ("C01, esquerda"), a diferença ("+0,74 s para a volta da IA no microssetor 3") e o detalhe (os dois tempos, a freada e a mínima);
   - **a fala:** curta, cerca de 4 a 6 s ("Curva 1, esquerda: 0,74 atrás da IA.");
   - **as regras da escrita:** português com acento, número com vírgula, microssetor contado a partir de 1 (o índice 2 do coach é o microssetor 3) e curva pelo nome técnico, com o lado por extenso (ADR 0003).
3. **Ela espera uma janela de rádio** (seção 2) e é entregue com o carro numa reta. Sai uma por vez: a seguinte espera o áudio da anterior acabar.
4. **Na linha de chegada,** o rádio dá o resumo da volta: o tempo (o período de s = 0 a s = 0, que o coach mede como o store v2) e a diferença para a referência escolhida, com o tempo do store v2. O que sobrou da volta sai junto, antes do resumo.
5. **O app do jogo e a tela Ao vivo** leem as mensagens entregues em `/api/radio/mensagens` e mostram o mesmo texto. A tela Volta usa a mesma escrita nas frases de uma volta gravada.

As mensagens de uma volta gravada de 13/10, pelo mesmo caminho (fora do tempo real, com o cronômetro do jogo):

| quando | cartão | fala |
|---|---|---|
| na reta dos boxes (3.698 m) | C11, esquerda · +1,14 s para a volta da IA no microssetor 39 | "Curva 11, esquerda: 1,14 atrás da IA." |
| logo depois (4.032 m) | C12, esquerda · +1,87 s para a volta da IA no microssetor 44 | "Curva 12, esquerda: 1,87 atrás da IA." |
| na linha (58 m) | Volta 4: 2:08,163 · +43,334 s para a volta da IA (1:24,829) | "Volta 4, 2 minutos e 8,2. 43,33 atrás da IA." |

## 2. As janelas de rádio

Uma janela é um trecho da geometria oficial fora das 14 curvas (`backend/core/radio/janelas.py`):

- **a curva:** o trecho em que a pista curva (`ml.track.corners.detect_corners`, como o relatório de evolução);
- **as margens:** 120 m antes de cada curva (a freada) e 30 m depois (a saída);
- **o tamanho mínimo:** 80 m.

Em Interlagos, isso dá três janelas:

| janela | onde |
|---|---|
| 723 a 1.192 m | a reta oposta, depois do S do Senna |
| 1.637 a 1.818 m | entre a C05 e a C06 |
| 3.697 a 104 m | a reta dos boxes, que cruza a linha |

Uma frase do miolo (C06 a C14) espera a reta dos boxes. A posição do carro é a projeção na geometria oficial que o coach já faz (`LiveDrivingCoach.posicao_oficial`), sem cálculo novo.

## 3. A voz

- **A escolhida:** **Microsoft Daniel (OneCore, pt-BR), a 1,25x.**
- **Como é gerada:** pelo `backend/core/radio/voz.ps1`, com o PowerShell do Windows, sem instalar nada.
- **As três vozes pt-BR deste Windows,** testadas com a mesma frase ("Curva 1, esquerda: 0,74 atrás da IA."):

| voz | interface | gera em | dura (com a vinheta) |
|---|---|---|---|
| Microsoft Daniel | OneCore (`Windows.Media.SpeechSynthesis`) | 1,5 s | 4,5 s |
| Microsoft Maria | OneCore | 0,8 s | 4,8 s |
| Microsoft Maria Desktop | SAPI 5 (`System.Speech`) | 1,0 s | 4,8 s |

- **Por que a Daniel:**
  - as vozes OneCore são as mais novas do Windows;
  - a Daniel foi a mais curta das três (cabe melhor numa reta);
  - uma voz masculina grave se separa melhor do ronco do motor.
- **Como trocar:** a voz fica em `core/radio/audio.py` (`VOZ_PADRAO`). As três amostras estão no handoff do pedido 31.
- **A vinheta antes da voz:** gerada pelo próprio código, sem som copiado de transmissão. É um estalo curto de ruído e dois bipes descendo (1.400 e 1.050 Hz).
- **O arquivo:** um WAV por mensagem em `<pasta de dados>/data/radio/audio/`, mono, 16 bits, com o silêncio das pontas cortado.

## 4. O app do jogo

- **Onde fica:** `tools/csp_app/radio_engenheiro/` (`manifest.ini` e `radio_engenheiro.lua`).
- **A janela:** transparente, com o título "Rádio · Sistema de Telemetria e Otimização de Trajetórias".
- **O que faz:**
  - a cada 0,3 s, pede as mensagens novas ao backend (`http://127.0.0.1:8000`), uma requisição por vez (o CSP permite duas);
  - mostra o cartão (carbono e vermelho) por pelo menos 5 s;
  - toca a vinheta e a voz direto da URL do backend (`ui.MediaPlayer` aceita URL), sem ler nem gravar arquivo fora da pasta do app;
  - **com o backend fora do ar:** mostra um ponto apagado e "rádio sem backend" no rodapé da janela, e registra o aviso uma vez no log do CSP;
  - **se a API do CSP não tiver o que o app usa:** avisa uma vez e fica calado.
- **O que não faz:** não muda o carro, os controles nem nada do jogo, e não desenha na pista.
- **Onde pôr a janela:** num canto, sem cobrir o centro da tela. A posição é a do modo de mover apps do jogo.

### Instalar, ligar e remover

O Eduardo roda os scripts; o Claude Code não grava na pasta do jogo (ADR 0020).

1. **Instalar,** com o jogo fechado:
   ```
   powershell -NoProfile -ExecutionPolicy Bypass -File tools\csp_app\instalar.ps1
   ```
   O script:
   - pede a pasta do jogo, com `D:\SteamLibrary\steamapps\common\assettocorsa` como sugestão;
   - confere que ela tem o `acs.exe` e o `extension\installed.log` do CSP;
   - mostra o que vai copiar e pede confirmação;
   - copia o app só para `apps\lua\radio_engenheiro\`.

   O `-ExecutionPolicy Bypass` vale só para esse comando e não muda a configuração do Windows.
2. **Ligar:**
   - abra o app do repositório (o backend com o rádio) antes do jogo;
   - no jogo, abra a barra de apps, no lado direito da tela, e ligue "Rádio do engenheiro".
3. **Conferir:** na tela Sistema, "Mandar mensagem de teste". O cartão aparece no jogo e a voz toca.
4. **Remover:**
   ```
   powershell -NoProfile -ExecutionPolicy Bypass -File tools\csp_app\remover.ps1
   ```
   Apaga só `apps\lua\radio_engenheiro\`, depois de conferir que a pasta é mesmo a do rádio.

## 5. O registro e a avaliação do Modelo 2

- **Onde fica:** cada mensagem entregue vai para `<pasta de dados>/data/radio/<sessão>.jsonl`, fora da pasta de gravações.
- **O que tem cada linha:**
  - o id, a hora e a volta;
  - o `s` do carro na entrega e o `s` da geometria oficial do que foi medido (o fim do microssetor);
  - o microssetor (a partir de 1) e a curva;
  - o texto, a fala e a origem (`coach`, `resumo` ou `teste`).
- **Nenhum leitor do ML confunde essa pasta com uma sessão:** as varreduras do inventário e do store procuram `player.jsonl` dentro das pastas de gravação (`data/recordings`), e `data/radio` não tem nenhum.
- **Para avaliar o Modelo 2** (ADR 0020, decisão 6): o registro diz o que foi dito, onde e em que volta. Cruzando com o store v2, dá para medir se a volta seguinte melhorou no microssetor e na curva citados. O próximo pedido do Modelo 2 pode montar essa conta.

## 6. As rotas

| rota | o que faz |
|---|---|
| `GET /api/radio/mensagens?desde=<id>&instancia=<inst>` | as mensagens entregues depois do id; outra instância (o backend reiniciou) devolve todas |
| `GET /api/radio/audio/{id}` | o WAV da mensagem |
| `POST /api/radio/teste` | a mensagem de teste, entregue na hora (só pela tela Sistema) |
| `GET /api/radio/estado` | as janelas, a voz e o que está esperando |
| `GET /api/live/volta` | a volta em andamento na grade oficial, para o fantasma da tela Ao vivo |
