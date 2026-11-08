# Partes comuns dos scripts da pista de teste (pedido 47, ADR 0029).
# Carregado com ". comum.ps1" pelos tres scripts; nao roda sozinho.
#
# As regras, nos tres:
#   - recusam rodar com o jogo aberto;
#   - nunca escrevem fora da copia (vhe_interlagos_teste_m1), salvo em data\pista_teste do repositorio;
#   - conferem o caminho antes de escrever ou apagar;
#   - usam -LiteralPath em tudo (as pastas de teste levam colchetes no nome).

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2

$PISTA_ORIGINAL = 'vhe_interlagos'
$PISTA_COPIA = 'vhe_interlagos_teste_m1'
$LAYOUT = 'gp'
$NOMES_NO_JOGO = @{ 'gp' = 'Interlagos [teste]'; 'norm' = 'Interlagos National [teste]' }
$JOGO_PADRAO = 'D:\SteamLibrary\steamapps\common\assettocorsa'
$PROCESSOS_PADRAO = @('acs', 'acs_x86', 'AssettoCorsa')
$UTF8 = New-Object System.Text.UTF8Encoding($false)

function Parar([string]$motivo) {
    Write-Host "PARADO: $motivo"
    exit 1
}

function Conferir-JogoFechado([string[]]$processos) {
    foreach ($nome in $processos) {
        $p = Get-Process -Name $nome -ErrorAction SilentlyContinue
        if ($p) { Parar "o jogo esta aberto ($nome, pid $($p[0].Id)). Feche o jogo e rode de novo." }
    }
}

function Caminho-Completo([string]$caminho) {
    return [System.IO.Path]::GetFullPath($caminho).TrimEnd('\')
}

function Resolver-Pastas([string]$jogoRaiz, [string]$repoRaiz) {
    if (-not $jogoRaiz) { $jogoRaiz = $JOGO_PADRAO }
    if (-not $repoRaiz) { $repoRaiz = Join-Path $PSScriptRoot '..\..' }
    $jogo = Caminho-Completo $jogoRaiz
    $tracks = Join-Path $jogo 'content\tracks'
    $original = Join-Path $tracks $PISTA_ORIGINAL
    $copia = Join-Path $tracks $PISTA_COPIA
    if (-not (Test-Path -LiteralPath $original -PathType Container)) { Parar "a pista original nao esta em $original" }
    $repo = Caminho-Completo $repoRaiz
    $saida = Join-Path $repo 'data\pista_teste'
    return [pscustomobject]@{ Jogo = $jogo; Tracks = $tracks; Original = $original; Copia = $copia; Repo = $repo; Saida = $saida }
}

function Conferir-DentroDaCopia([object]$pastas, [string]$caminho) {
    # O caminho tem de ficar dentro da copia, e a copia tem de ser a pasta com o nome dela em content\tracks.
    $copia = Caminho-Completo $pastas.Copia
    $original = Caminho-Completo $pastas.Original
    $alvo = Caminho-Completo $caminho
    if ((Split-Path -Leaf $copia) -ne $PISTA_COPIA) { Parar "a copia nao tem o nome esperado: $copia" }
    if ((Caminho-Completo (Split-Path -Parent $copia)) -ne (Caminho-Completo $pastas.Tracks)) { Parar "a copia nao esta em content\tracks: $copia" }
    if ($copia -ieq $original) { Parar "a copia e a original sao a mesma pasta: $copia" }
    if (-not ($alvo -ieq $copia -or $alvo.StartsWith($copia + '\', [System.StringComparison]::OrdinalIgnoreCase))) {
        Parar "recusado: $alvo fica fora da copia ($copia)"
    }
    if ($alvo -ieq $original -or $alvo.StartsWith($original + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        Parar "recusado: $alvo fica dentro da pista original"
    }
    # Uma juncao ou um link no caminho levaria a escrita para outro lugar (por exemplo, para a original).
    $atual = $alvo
    while ($atual.Length -ge $copia.Length) {
        if (Test-Path -LiteralPath $atual) {
            $item = Get-Item -LiteralPath $atual -Force
            if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) { Parar "recusado: $atual e uma juncao ou um link" }
        }
        if ($atual -ieq $copia) { break }
        $atual = Caminho-Completo (Split-Path -Parent $atual)
    }
}

function Sha256([string]$arquivo) {
    return (Get-FileHash -LiteralPath $arquivo -Algorithm SHA256).Hash.ToLower()
}

function Hora-Local {
    return (Get-Date).ToString('yyyy-MM-ddTHH:mm:ss')
}

function Ler-ShaOriginal([object]$pastas) {
    $arquivo = Join-Path $pastas.Saida 'copia.json'
    if (-not (Test-Path -LiteralPath $arquivo)) { Parar "falta ${arquivo}: rode o criar_copia.ps1 primeiro" }
    return (Get-Content -LiteralPath $arquivo -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Conferir-OriginalIntacta([object]$pastas, [object]$copiaJson) {
    $agora = Sha256 (Join-Path $pastas.Original "$LAYOUT\ai\fast_lane.ai")
    if ($agora -ne $copiaJson.sha256_fast_lane_original) {
        Parar "o fast_lane.ai ORIGINAL mudou: era $($copiaJson.sha256_fast_lane_original), agora $agora"
    }
    return $agora
}
