<#
.SYNOPSIS
  Poe a linha de uma condicao na copia vhe_interlagos_teste_m1 (pedido 47, ADR 0029; L1 e L2: pedido 50, ADR 0031).

.DESCRIPTION
  - Recusa rodar com o jogo aberto, sem a copia ou com um arquivo de linha que nao bate com o manifesto:
    o linhas.json (C0 a C4, pedido 47) ou o linha_do_projeto.json (L1 e L2, pedido 50).
  - Copia data\pista_teste\linhas\<Condicao>\fast_lane.ai para <copia>\gp\ai\fast_lane.ai, com a data de agora.
  - Apaga so na copia o que deriva da linha (gp\ai\fast_lane.aip, se existir).
  - Escreve uma linha em data\pista_teste\registro.csv (hora, condicao, sha256, arquivo).
  - Apaga, nas pastas de cache do CSP (cache\ai_grids, cache\ai_payloads, cache\ai_alt_lanes), so os
    arquivos cujo nome comeca com "vhe_interlagos_teste_m1_", e lista o que apagou em
    data\pista_teste\caches_csp.log (ADR 0029, item 15; autorizado pelo Eduardo em 08/11).
  - Confere que o fast_lane.ai original nao mudou.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File tools\pista_teste\trocar_linha.ps1 -Condicao C1
  powershell -ExecutionPolicy Bypass -File tools\pista_teste\trocar_linha.ps1 -Condicao L1
#>
param(
    [Parameter(Mandatory = $true)][ValidateSet('C0', 'C1', 'C2', 'C3', 'C4', 'L1', 'L2')][string]$Condicao,
    [string]$JogoRaiz = '',
    [string]$RepoRaiz = '',
    [string[]]$ProcessosDoJogo = @()
)
. (Join-Path $PSScriptRoot 'comum.ps1')
if (-not $ProcessosDoJogo -or $ProcessosDoJogo.Count -eq 0) { $ProcessosDoJogo = $PROCESSOS_PADRAO }

Conferir-JogoFechado $ProcessosDoJogo
$p = Resolver-Pastas $JogoRaiz $RepoRaiz
if (-not (Test-Path -LiteralPath $p.Copia -PathType Container)) { Parar "a copia nao existe: $($p.Copia). Rode o criar_copia.ps1." }
$copiaJson = Ler-ShaOriginal $p
Conferir-OriginalIntacta $p $copiaJson | Out-Null

# C0 a C4: o manifesto do pedido 47. L1 e L2: o do pedido 50 (ADR 0031, item 9), a parte.
$nomeDoManifesto = 'linhas.json'
if ($Condicao -eq 'L1' -or $Condicao -eq 'L2') { $nomeDoManifesto = 'linha_do_projeto.json' }
$manifesto = Join-Path $p.Saida "linhas\$nomeDoManifesto"
if (-not (Test-Path -LiteralPath $manifesto)) { Parar "falta $manifesto" }
$linhas = Get-Content -LiteralPath $manifesto -Raw -Encoding UTF8 | ConvertFrom-Json
$esperado = $null
if ($linhas.condicoes.PSObject.Properties.Name -contains $Condicao) { $esperado = $linhas.condicoes.$Condicao.sha256 }
if (-not $esperado) { Parar "o manifesto $manifesto nao tem a condicao $Condicao" }
if ($Condicao -eq 'C0' -and $esperado -ne $copiaJson.sha256_fast_lane_original) { Parar "o C0 do linhas.json nao e o original" }
$fonte = Join-Path $p.Saida "linhas\$Condicao\fast_lane.ai"
if (-not (Test-Path -LiteralPath $fonte)) { Parar "falta $fonte" }
$shaFonte = Sha256 $fonte
if ($shaFonte -ne $esperado) { Parar "o arquivo de $Condicao nao bate com o ${nomeDoManifesto}: $shaFonte, esperado $esperado" }

$destino = Join-Path $p.Copia "$LAYOUT\ai\fast_lane.ai"
Conferir-DentroDaCopia $p $destino
foreach ($derivado in @("$LAYOUT\ai\fast_lane.aip")) {
    $alvo = Join-Path $p.Copia $derivado
    Conferir-DentroDaCopia $p $alvo
    if (Test-Path -LiteralPath $alvo) { Remove-Item -LiteralPath $alvo -Force; Write-Host "apagado na copia: $alvo" }
}
$apagados = Apagar-CachesDaCopia $p
foreach ($a in $apagados) { Write-Host "cache do CSP apagado: $a" }
Copy-Item -LiteralPath $fonte -Destination $destino -Force
(Get-Item -LiteralPath $destino).LastWriteTime = Get-Date
$shaDestino = Sha256 $destino
if ($shaDestino -ne $esperado) { Parar "a linha na copia nao ficou igual a de ${Condicao}: $shaDestino" }

$registro = Join-Path $p.Saida 'registro.csv'
if (-not (Test-Path -LiteralPath $registro)) {
    [System.IO.File]::WriteAllText($registro, "hora,condicao,sha256,arquivo`r`n", $UTF8)
}
$hora = Hora-Local
[System.IO.File]::AppendAllText($registro, "$hora,$Condicao,$shaDestino,$destino`r`n", $UTF8)

$log = Join-Path $p.Saida 'caches_csp.log'
$texto = "$hora ${Condicao}: $($apagados.Count) cache(s) do CSP apagado(s)`r`n"
foreach ($a in $apagados) { $texto += "  apagado $a`r`n" }
[System.IO.File]::AppendAllText($log, $texto, $UTF8)

Conferir-OriginalIntacta $p $copiaJson | Out-Null
Write-Host "pronto: $Condicao na copia ($shaDestino), registrado em $registro as $hora"
exit 0
