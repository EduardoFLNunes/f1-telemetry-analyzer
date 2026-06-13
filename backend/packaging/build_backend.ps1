param(
  [switch]$InstallPyInstaller
)

$ErrorActionPreference = "Stop"

$PackagingDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Resolve-Path (Join-Path $PackagingDir "..")
$RepoRoot = Resolve-Path (Join-Path $BackendDir "..")
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Runner = Join-Path $BackendDir "desktop_backend_runner.py"
$DistDir = Join-Path $BackendDir "dist"
$BuildDir = Join-Path $BackendDir "build"

if (-not (Test-Path $Python)) {
  throw "Python virtualenv was not found at $Python"
}

if (-not (Test-Path $Runner)) {
  throw "Desktop backend runner was not found at $Runner"
}

if ($InstallPyInstaller) {
  & $Python -m pip install pyinstaller
}

& $Python -m PyInstaller --version | Out-Null
if ($LASTEXITCODE -ne 0) {
  throw "PyInstaller is not installed. Run: .venv\Scripts\python.exe -m pip install pyinstaller"
}

Push-Location $RepoRoot
try {
  & $Python -m PyInstaller `
    --clean `
    --noconfirm `
    --onefile `
    --name automobilista-backend `
    --distpath $DistDir `
    --workpath $BuildDir `
    --specpath $PackagingDir `
    --paths $BackendDir `
    --collect-all uvicorn `
    --collect-all fastapi `
    --collect-all starlette `
    --collect-all pandas `
    --collect-all numpy `
    --collect-all scipy `
    --collect-all pyarrow `
    --collect-all duckdb `
    --exclude-module pandas.tests `
    --exclude-module scipy.tests `
    --exclude-module pyarrow.tests `
    --hidden-import uvicorn.loops.auto `
    --hidden-import uvicorn.protocols.http.auto `
    --hidden-import uvicorn.protocols.websockets.auto `
    $Runner
} finally {
  Pop-Location
}

if ($LASTEXITCODE -ne 0) {
  throw "PyInstaller build failed with exit code $LASTEXITCODE"
}

$Exe = Join-Path $DistDir "automobilista-backend.exe"
if (-not (Test-Path $Exe)) {
  throw "Expected backend executable was not generated at $Exe"
}

Write-Output "Backend executable generated: $Exe"
