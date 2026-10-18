# Instala o "Rádio do engenheiro" no Assetto Corsa (pedido 31, ADR 0020).
#
# Copia tools\csp_app\radio_engenheiro\ para <pasta do jogo>\apps\lua\radio_engenheiro\
# e não toca em mais nada do jogo. Quem roda é o Eduardo:
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\csp_app\instalar.ps1
#
# (O -ExecutionPolicy Bypass vale só para este comando; não muda a configuração do Windows.)
param([string]$PastaDoJogo)
$ErrorActionPreference = 'Stop'

$nome = 'radio_engenheiro'
$origem = Join-Path $PSScriptRoot $nome
if (-not (Test-Path (Join-Path $origem 'manifest.ini'))) {
  Write-Host "Não achei o app em $origem." -ForegroundColor Red
  exit 1
}

if (-not $PastaDoJogo) {
  $sugestao = 'D:\SteamLibrary\steamapps\common\assettocorsa'
  $PastaDoJogo = Read-Host "Pasta do Assetto Corsa (Enter para $sugestao)"
  if (-not $PastaDoJogo) { $PastaDoJogo = $sugestao }
}
$PastaDoJogo = $PastaDoJogo.Trim('"').TrimEnd('\')

# A pasta tem de ser a do jogo, com o Custom Shaders Patch instalado.
$log = Join-Path $PastaDoJogo 'extension\installed.log'
if (-not (Test-Path (Join-Path $PastaDoJogo 'acs.exe'))) {
  Write-Host "Esta pasta não é a do Assetto Corsa (não tem acs.exe): $PastaDoJogo" -ForegroundColor Red
  exit 2
}
if (-not (Test-Path $log)) {
  Write-Host "Não achei o Custom Shaders Patch: falta $log" -ForegroundColor Red
  exit 3
}
$csp = (Get-Content $log -TotalCount 40 | Select-String -Pattern '^\s*version:\s*(.+)$' | Select-Object -First 1)
$versao = if ($csp) { $csp.Matches[0].Groups[1].Value.Trim() } else { 'desconhecida' }

$destinoLua = Join-Path $PastaDoJogo 'apps\lua'
$destino = Join-Path $destinoLua $nome
Write-Host "Custom Shaders Patch: versão $versao (o app foi feito para a 0.2.11)."
Write-Host "Vou copiar:"
Write-Host "  de   $origem"
Write-Host "  para $destino"
Write-Host "Nada mais do jogo é tocado."
$ok = Read-Host "Continuar? (s/n)"
if ($ok -notin @('s', 'S', 'sim', 'Sim')) {
  Write-Host 'Nada foi feito.'
  exit 0
}

if (-not (Test-Path $destinoLua)) { New-Item -ItemType Directory -Path $destinoLua | Out-Null }
if (Test-Path $destino) { Remove-Item -Recurse -Force $destino }
Copy-Item -Recurse $origem $destino
Get-ChildItem $destino | ForEach-Object { Write-Host "  copiado: $($_.Name)" }
Write-Host ''
Write-Host 'Pronto. No jogo, abra a barra de apps (lado direito da tela) e ligue "Rádio do engenheiro".' -ForegroundColor Green
Write-Host 'Abra o app do repositório (o backend com o rádio) antes do jogo.'
