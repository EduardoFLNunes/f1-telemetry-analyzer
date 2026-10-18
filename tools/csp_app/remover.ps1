# Remove o "Rádio do engenheiro" do Assetto Corsa (pedido 31, ADR 0020).
#
# Apaga só <pasta do jogo>\apps\lua\radio_engenheiro\. Quem roda é o Eduardo:
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\csp_app\remover.ps1
param([string]$PastaDoJogo)
$ErrorActionPreference = 'Stop'

$nome = 'radio_engenheiro'
if (-not $PastaDoJogo) {
  $sugestao = 'D:\SteamLibrary\steamapps\common\assettocorsa'
  $PastaDoJogo = Read-Host "Pasta do Assetto Corsa (Enter para $sugestao)"
  if (-not $PastaDoJogo) { $PastaDoJogo = $sugestao }
}
$PastaDoJogo = $PastaDoJogo.Trim('"').TrimEnd('\')

if (-not (Test-Path (Join-Path $PastaDoJogo 'acs.exe'))) {
  Write-Host "Esta pasta não é a do Assetto Corsa (não tem acs.exe): $PastaDoJogo" -ForegroundColor Red
  exit 2
}
if (-not (Test-Path (Join-Path $PastaDoJogo 'extension\installed.log'))) {
  Write-Host "Não achei o Custom Shaders Patch nesta pasta: $PastaDoJogo" -ForegroundColor Red
  exit 3
}

$destino = Join-Path $PastaDoJogo "apps\lua\$nome"
if (-not (Test-Path $destino)) {
  Write-Host "O app não está instalado: $destino não existe. Nada foi feito."
  exit 0
}
# Só a pasta do app, e só se ela for mesmo a dele.
if (-not (Test-Path (Join-Path $destino "$nome.lua"))) {
  Write-Host "A pasta $destino não parece ser a do rádio (falta $nome.lua). Nada foi feito." -ForegroundColor Red
  exit 4
}
Write-Host "Vou apagar só esta pasta: $destino"
$ok = Read-Host "Continuar? (s/n)"
if ($ok -notin @('s', 'S', 'sim', 'Sim')) {
  Write-Host 'Nada foi feito.'
  exit 0
}
Remove-Item -Recurse -Force $destino
Write-Host 'Removido.' -ForegroundColor Green
