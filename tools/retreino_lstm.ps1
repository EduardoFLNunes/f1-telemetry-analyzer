# Retreino da LSTM geradora (pedido 44; ADR 0026).
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\retreino_lstm.ps1
#
# Roda em sequencia `todas --paralelo 8 --threads 1`, `regua`, `final` e `linha`.
# Rodado de novo, retoma: as rodadas e os modelos finais ja terminados nao rodam
# de novo. O log fica em logs\retreino_lstm_AAAA-MM-DD_HH-mm-ss.log, e a ultima
# linha diz como terminou: RETREINO CONCLUIDO ou RETREINO PARADO.

param(
    # So para testar o script: outro python, ou so conferir o que rodaria.
    [string]$Python = "",
    [switch]$Conferir
)

$ErrorActionPreference = "Stop"

$raiz = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $raiz "backend"
if (-not $Python) { $Python = Join-Path $raiz ".venv\Scripts\python.exe" }
$logs = Join-Path $raiz "logs"
New-Item -ItemType Directory -Force $logs | Out-Null
$log = Join-Path $logs ("retreino_lstm_{0}.log" -f (Get-Date -Format "yyyy-MM-dd_HH-mm-ss"))

function Escreva([string]$texto) {
    $linha = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $texto
    Write-Host $linha
    Add-Content -Path $log -Value $linha -Encoding UTF8
}

function Pare([string]$motivo) {
    Escreva $motivo
    Escreva "RETREINO PARADO. Rode o mesmo comando de novo para retomar de onde parou."
    exit 1
}

# O ambiente do backend: a raiz de sempre, sem desvio de runtime, e cada processo
# com uma thread so. As threads do numpy nao mudam o treino, so evitam disputa.
Remove-Item Env:AT_BACKEND_RUNTIME_ROOT -ErrorAction SilentlyContinue
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"
$env:OMP_NUM_THREADS = "1"
$env:MKL_NUM_THREADS = "1"

if (-not (Test-Path $Python)) { Pare "Nao achei o python em $Python." }

# Duas execucoes juntas gravariam as mesmas rodadas.
$outros = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
    Where-Object { $_.CommandLine -like "*ml.scripts.retreino_lstm*" })
if ($outros.Count -gt 0) {
    Pare ("Ja ha {0} processo(s) do retreino rodando (PID {1}). Espere terminar ou encerre antes de rodar de novo." -f $outros.Count, ($outros.ProcessId -join ", "))
}

$etapas = @(
    @{ Nome = "as 45 rodadas"; Args = @("todas", "--paralelo", "8", "--threads", "1") },
    @{ Nome = "a regua"; Args = @("regua") },
    @{ Nome = "os modelos finais"; Args = @("final", "--threads", "8") },
    @{ Nome = "a linha de referencia"; Args = @("linha") }
)

$commit = & git -C $raiz rev-parse --short HEAD
$sujo = & git -C $raiz status --porcelain -- backend
Escreva "Retreino da LSTM no commit $commit, branch $(& git -C $raiz branch --show-current). Log: $log"
if ($sujo) { Pare "Ha mudancas sem commit em backend/. O resultado nao teria um commit que o explique." }

if ($Conferir) {
    foreach ($etapa in $etapas) { Escreva ("Rodaria: {0} -m ml.scripts.retreino_lstm {1}" -f $Python, ($etapa.Args -join " ")) }
    Escreva "RETREINO NAO RODOU (so conferencia)."
    exit 0
}

# Sem isto, o Windows pode suspender o computador durante a noite. Vale so enquanto
# este script roda, e nao muda nenhuma configuracao de energia.
Add-Type -Namespace Retreino -Name Energia -MemberDefinition @"
[System.Runtime.InteropServices.DllImport("kernel32.dll")]
public static extern uint SetThreadExecutionState(uint flags);
"@
[void][Retreino.Energia]::SetThreadExecutionState([uint32]"0x80000001")

Set-Location $backend
$inicio = Get-Date
try {
    foreach ($etapa in $etapas) {
        Escreva "Comecando: $($etapa.Nome)."
        $comando = '"{0}" -u -m ml.scripts.retreino_lstm {1} 2>&1' -f $Python, ($etapa.Args -join " ")
        & cmd /c $comando | ForEach-Object {
            Write-Host $_
            Add-Content -Path $log -Value $_ -Encoding UTF8
        }
        if ($LASTEXITCODE -ne 0) { Pare "A etapa '$($etapa.Nome)' terminou com a saida $LASTEXITCODE." }
        Escreva "Terminou: $($etapa.Nome)."
    }
}
finally {
    [void][Retreino.Energia]::SetThreadExecutionState([uint32]"0x80000000")
}

Escreva ("Tempo desta execucao: {0:N1} h." -f ((Get-Date) - $inicio).TotalHours)
Escreva "RETREINO CONCLUIDO."
exit 0
