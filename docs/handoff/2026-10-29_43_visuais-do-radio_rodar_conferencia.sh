#!/bin/bash
# Pedido 43: as 3 sessoes, antes e depois
S="$1"; R=/c/Users/Dokas/Desktop/f1-telemetry-analyzer; PY=$R/.venv/Scripts/python.exe; H=$R/docs/handoff/2026-10-29_43_visuais-do-radio
cd $R/backend
for par in "13-10 $R/recordings/2026-10-13_19-24-10_vhe_interlagos" "18-10 $R/data/recordings/2026-10-18_12-38-44_vhe_interlagos" "21-10 $R/data/recordings/2026-10-21_20-30-54_vhe_interlagos"; do
  set -- $par
  ANTIGO="$S/antigo" $PY "${H}_radio_offline_antes.py" "$2" "$S/antes_$1.json" > "$S/antes_$1.txt" 2>&1
  $PY "${H}_radio_offline.py" "$2" "$S/depois_$1.json" > "$S/depois_$1.txt" 2>&1
  echo "$1 pronto"
done
