<#
.SYNOPSIS
  Apaga a copia vhe_interlagos_teste_m1, e so ela (pedido 47, ADR 0029).

.DESCRIPTION
  - Recusa rodar com o jogo aberto.
  - Confere que o alvo e a pasta vhe_interlagos_teste_m1 em content\tracks e que nao e a original.
  - Confere o sha256 do fast_lane.ai original antes e depois.
  - Os caches do CSP com o nome da copia (pasta cache do jogo) ficam: so sao listados.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File tools\pista_teste\remover_copia.ps1
#>
param(
    [string]$JogoRaiz = '',
    [string]$RepoRaiz = '',
    [string[]]$ProcessosDoJogo = @()
)
. (Join-Path $PSScriptRoot 'comum.ps1')
if (-not $ProcessosDoJogo -or $ProcessosDoJogo.Count -eq 0) { $ProcessosDoJogo = $PROCESSOS_PADRAO }

Conferir-JogoFechado $ProcessosDoJogo
$p = Resolver-Pastas $JogoRaiz $RepoRaiz
if (-not (Test-Path -LiteralPath $p.Copia -PathType Container)) { Parar "a copia nao existe: $($p.Copia)" }
Conferir-DentroDaCopia $p $p.Copia
$antes = Sha256 (Join-Path $p.Original "$LAYOUT\ai\fast_lane.ai")
$copiaJson = $null
$arquivo = Join-Path $p.Saida 'copia.json'
if (Test-Path -LiteralPath $arquivo) {
    $copiaJson = Get-Content -LiteralPath $arquivo -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($antes -ne $copiaJson.sha256_fast_lane_original) { Parar "o fast_lane.ai ORIGINAL mudou desde a copia: $antes" }
}
Remove-Item -LiteralPath $p.Copia -Recurse -Force
$depois = Sha256 (Join-Path $p.Original "$LAYOUT\ai\fast_lane.ai")
if ($depois -ne $antes) { Parar "o fast_lane.ai ORIGINAL mudou: $antes -> $depois" }
$cache = Join-Path $p.Jogo 'cache'
foreach ($sub in @('ai_grids', 'ai_payloads', 'ai_alt_lanes')) {
    $pasta = Join-Path $cache $sub
    if (Test-Path -LiteralPath $pasta) {
        Get-ChildItem -LiteralPath $pasta -File | Where-Object { $_.Name.StartsWith($PISTA_COPIA) } |
            ForEach-Object { Write-Host "cache do CSP com o nome da copia (ficou): $sub\$($_.Name)" }
    }
}
Write-Host "pronto: a copia $($p.Copia) foi apagada; a original continua com sha256 $depois"
exit 0
