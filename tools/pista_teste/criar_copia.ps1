<#
.SYNOPSIS
  Cria a copia vhe_interlagos_teste_m1 da pista (pedido 47, ADR 0029).

.DESCRIPTION
  - Recusa rodar com o jogo aberto e se a copia ja existir.
  - Registra o sha256 do fast_lane.ai original em data\pista_teste\copia.json, antes de copiar.
  - Copia a pasta inteira da pista sem abrir os arquivos (Copy-Item).
  - Na copia, troca so o nome em ui\<layout>\ui_track.json ("Interlagos [teste]").
  - Confere que a original nao mudou e que a linha da copia e igual a original.
  - Nunca escreve na pasta da pista original.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File tools\pista_teste\criar_copia.ps1
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
if (Test-Path -LiteralPath $p.Copia) { Parar "a copia ja existe: $($p.Copia). Para recriar, rode o remover_copia.ps1 antes." }
Conferir-DentroDaCopia $p $p.Copia

$linhaOriginal = Join-Path $p.Original "$LAYOUT\ai\fast_lane.ai"
$shaAntes = Sha256 $linhaOriginal
$shaNorm = $null
$norm = Join-Path $p.Original 'norm\ai\fast_lane.ai'
if (Test-Path -LiteralPath $norm) { $shaNorm = Sha256 $norm }

New-Item -ItemType Directory -Force -Path $p.Saida | Out-Null
$registro = [ordered]@{
    criada_em = Hora-Local
    original = $p.Original
    copia = $p.Copia
    sha256_fast_lane_original = $shaAntes
    sha256_fast_lane_original_norm = $shaNorm
}
$registro | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $p.Saida 'copia.json') -Encoding UTF8
Write-Host "sha256 do fast_lane.ai original ($LAYOUT): $shaAntes"

Write-Host "copiando $($p.Original) -> $($p.Copia) ..."
Copy-Item -LiteralPath $p.Original -Destination $p.Copia -Recurse

# O nome no jogo, so na copia.
foreach ($layout in $NOMES_NO_JOGO.Keys) {
    $ui = Join-Path $p.Copia "ui\$layout\ui_track.json"
    if (-not (Test-Path -LiteralPath $ui)) { continue }
    Conferir-DentroDaCopia $p $ui
    $texto = [System.IO.File]::ReadAllText($ui, $UTF8)
    $novo = [regex]::Replace($texto, '("name"\s*:\s*")[^"]*(")', ('${1}' + $NOMES_NO_JOGO[$layout] + '${2}'), 1)
    if ($novo -eq $texto) { Parar "nao achei o nome em $ui" }
    [System.IO.File]::WriteAllText($ui, $novo, $UTF8)
    Write-Host "nome no jogo ($layout): $($NOMES_NO_JOGO[$layout])"
}

$shaDepois = Sha256 $linhaOriginal
if ($shaDepois -ne $shaAntes) { Parar "o fast_lane.ai ORIGINAL mudou durante a copia: $shaAntes -> $shaDepois" }
$shaCopia = Sha256 (Join-Path $p.Copia "$LAYOUT\ai\fast_lane.ai")
if ($shaCopia -ne $shaAntes) { Parar "a linha da copia nao e igual a original: $shaCopia" }
Write-Host "pronto: copia criada em $($p.Copia); a original continua com sha256 $shaDepois"
Write-Host "proximo passo: trocar_linha.ps1 -Condicao C0"
exit 0
