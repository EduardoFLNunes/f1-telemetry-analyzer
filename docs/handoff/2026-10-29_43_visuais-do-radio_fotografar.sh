#!/bin/bash
# Pedido 43, Parte D.4: cada previa HTML vira um PNG pelo Edge sem janela (headless), com um
# perfil temporario proprio (nada do perfil do Eduardo), e a folha junta as imagens.
# Uso: fotografar.sh <pasta de trabalho> <pasta do handoff>
W="$1"; H="$2"; R=/c/Users/Dokas/Desktop/f1-telemetry-analyzer; PY=$R/.venv/Scripts/python.exe
PREVIA=$R/docs/handoff/2026-10-29_43_visuais-do-radio_previa.py
EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
PERFIL="$W/perfil_edge"
mkdir -p "$W/html" "$W/png" "$PERFIL"
foto() {  # nome passagem id curva fracao largura altura boxes
  $PY "$PREVIA" "$2" "$3" "$4" "$5" "$6" "$7" "$8" "$W/html/$1.html"
  # um perfil por foto: o Edge sem janela pode demorar a soltar o perfil da anterior
  "$EDGE" --headless=new --disable-gpu --user-data-dir="$(cygpath -w "$PERFIL/$1")" --hide-scrollbars \
    --allow-file-access-from-files --window-size="$6,$7" --screenshot="$(cygpath -w "$W/png/$1.png")" \
    "file:///$(cygpath -m "$W/html/$1.html")" > /dev/null 2>&1
}
A=$W/antes_21-10.json; D=$W/depois_21-10.json
# a C12 da volta 2 de 21/10 (a frase do coach, mensagem 3), antes e depois
$PY $R/docs/handoff/2026-10-22_36_radio-com-unidades-e-replay-da-curva_replay_previa.py "$A" 3 C12 0.55 "$W/html/c12_v2_antes.html"
"$EDGE" --headless=new --disable-gpu --user-data-dir="$(cygpath -w "$PERFIL/antes")" --hide-scrollbars --allow-file-access-from-files \
  --window-size=420,300 --screenshot="$(cygpath -w "$W/png/c12_v2_antes.png")" "file:///$(cygpath -m "$W/html/c12_v2_antes.html")" > /dev/null 2>&1
foto c12_v2_depois_420x480 "$D" 3 C12 0.55 420 480 0
# a segunda analise de 21/10 (mensagem 25): a C01 da volta 17 e a C10 da volta 16
foto c01_v17_420x480 "$D" 25 C01 0.6 420 480 0
foto c10_v16_420x480 "$D" 25 C10 0.6 420 480 0
# a janela do jogo: 300 x 300, o tamanho de abertura 420 x 300 e a grande dos boxes (1,6 vez), com a grade
foto c12_v2_300x300 "$D" 3 C12 0.55 300 300 0
foto c12_v2_420x300 "$D" 3 C12 0.55 420 300 0
foto c01_v17_boxes_672x480 "$D" 25 C01 0.6 672 480 1
foto c01_v17_boxes_480x480 "$D" 25 C01 0.6 480 480 1
rm -rf "$PERFIL"
ls -la "$W/png"
