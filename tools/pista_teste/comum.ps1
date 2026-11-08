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

$PASTAS_DE_CACHE_DO_CSP = @('ai_grids', 'ai_payloads', 'ai_alt_lanes')

function Apagar-CachesDaCopia([object]$pastas) {
    # Emenda do ADR 0029 (item 15, autorizada pelo Eduardo em 08/11): apaga, nas tres pastas de cache do CSP,
    # so os arquivos cujo nome comeca com "vhe_interlagos_teste_m1_". Nenhum outro arquivo dessas pastas.
    $prefixo = $PISTA_COPIA + '_'
    $cache = Caminho-Completo (Join-Path $pastas.Jogo 'cache')
    $apagados = @()
    if (-not (Test-Path -LiteralPath $cache -PathType Container)) { return , $apagados }
    if ((Get-Item -LiteralPath $cache -Force).Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
        Parar "recusado: $cache e uma juncao ou um link"
    }
    foreach ($sub in $PASTAS_DE_CACHE_DO_CSP) {
        $pasta = Caminho-Completo (Join-Path $cache $sub)
        if (-not (Test-Path -LiteralPath $pasta -PathType Container)) { continue }
        if ((Get-Item -LiteralPath $pasta -Force).Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
            Parar "recusado: $pasta e uma juncao ou um link"
        }
        $alvos = @(Get-ChildItem -LiteralPath $pasta -File -Force | Where-Object { $_.Name.StartsWith($prefixo, [System.StringComparison]::Ordinal) })
        foreach ($arquivo in $alvos) {
            $cheio = Caminho-Completo $arquivo.FullName
            if ((Caminho-Completo $arquivo.DirectoryName) -ne $pasta) { Parar "recusado: $cheio fora de $pasta" }
            if (-not $arquivo.Name.StartsWith($prefixo, [System.StringComparison]::Ordinal)) { Parar "recusado: $cheio nao e da copia" }
            if ($arquivo.Attributes -band [System.IO.FileAttributes]::ReparsePoint) { Parar "recusado: $cheio e um link" }
            $linha = "$sub\$($arquivo.Name) $($arquivo.Length) $($arquivo.LastWriteTime.ToString('s'))"
            Remove-Item -LiteralPath $cheio -Force
            if (Test-Path -LiteralPath $cheio) { Parar "nao consegui apagar $cheio" }
            $apagados += $linha
        }
    }
    return , $apagados
}

function Conferir-OriginalIntacta([object]$pastas, [object]$copiaJson) {
    $agora = Sha256 (Join-Path $pastas.Original "$LAYOUT\ai\fast_lane.ai")
    if ($agora -ne $copiaJson.sha256_fast_lane_original) {
        Parar "o fast_lane.ai ORIGINAL mudou: era $($copiaJson.sha256_fast_lane_original), agora $agora"
    }
    return $agora
}
