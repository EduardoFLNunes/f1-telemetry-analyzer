#!/bin/bash
# Pedido 36 (fechamento): as 3 sessoes, com o texto de antes das unidades e com o atual (limite de 7,3 s), e a de hoje.
W="$1"; R=/c/Users/Dokas/Desktop/f1-telemetry-analyzer; PY=$R/.venv/Scripts/python.exe
cd $R/backend
for par in "13-10 $R/recordings/2026-10-13_19-24-10_vhe_interlagos" "18-10 $R/data/recordings/2026-10-18_12-38-44_vhe_interlagos" "21-10 $R/data/recordings/2026-10-21_20-30-54_vhe_interlagos"; do
  set -- $par
  TEXTO_ANTIGO="$W/texto_antes.py" $PY "$W/radio_offline.py" "$2" "$W/radio_antes2_$1.json" > "$W/radio_antes2_$1.txt" 2>&1
  $PY "$W/radio_offline.py" "$2" "$W/radio_depois2_$1.json" > "$W/radio_depois2_$1.txt" 2>&1
  echo "$1 pronto"
done
$PY "$W/radio_offline.py" $R/data/recordings/2026-10-22_09-46-01_vhe_interlagos "$W/radio_depois2_22-10.json" > "$W/radio_depois2_22-10.txt" 2>&1
echo "22-10 pronto"
