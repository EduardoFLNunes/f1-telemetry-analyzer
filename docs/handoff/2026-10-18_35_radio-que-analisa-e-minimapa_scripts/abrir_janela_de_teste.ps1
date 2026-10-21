# Pedido 35: abre o app do repositorio isolado, com o reprodutor de gravacoes, para medir
# o mapa ao vivo (medir_mapa.mjs) e para a captura da tela Ao vivo (cdp.mjs).
# A pasta de dados isolada (AT_DESKTOP_USER_DATA_DIR) poe "[teste]" no titulo
# (pedido 33, Parte C). Backend na 8011, raiz e gravacoes no scratchpad.
$repo = 'C:\Users\Dokas\Desktop\f1-telemetry-analyzer'
$s = 'C:\Users\Dokas\AppData\Local\Temp\claude\C--Users-Dokas-Desktop-f1-telemetry-analyzer\6d2869f6-db96-4d2e-b3f2-ef87109c70b2\scratchpad'
$env:AT_DESKTOP_USER_DATA_DIR = "$s\p35\electron-userdata"
$env:AT_DESKTOP_MODE = 'production'
$env:AT_TESTE_REPRODUTOR = '1'
$env:AT_DESKTOP_AUTOSTART_BACKEND = 'true'
$env:AT_BACKEND_RUNNER = 'python'
$env:AT_BACKEND_URL = 'http://127.0.0.1:8011'
$env:AT_BACKEND_PORT = '8011'
$env:AT_BACKEND_RUNTIME_ROOT = "$s\runtime-electron"
$env:TELEMETRY_RECORDING_DIR = "$s\runtime\data\recordings"
$env:AT_DESKTOP_LOG_DIR = "$s\p35\electron-logs"
$p = Start-Process -FilePath "$repo\desktop\node_modules\electron\dist\electron.exe" `
  -ArgumentList '.', '--remote-debugging-port=9229', '--disable-backgrounding-occluded-windows', '--disable-renderer-backgrounding', '--disable-background-timer-throttling' `
  -WorkingDirectory "$repo\desktop" -PassThru
"electron pid $($p.Id)"
