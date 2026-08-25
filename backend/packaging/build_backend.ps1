param(
  [switch]$InstallPyInstaller,
  [string]$PythonExecutable = $env:AT_PACKAGING_PYTHON
)

$ErrorActionPreference = "Stop"

$PackagingDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Resolve-Path (Join-Path $PackagingDir "..")
$RepoRoot = Resolve-Path (Join-Path $BackendDir "..")
$DefaultPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Python = if ($PythonExecutable) { $PythonExecutable } else { $DefaultPython }
$SitePackages = Join-Path $RepoRoot ".venv\Lib\site-packages"
$Runner = Join-Path $BackendDir "desktop_backend_runner.py"
$DistDir = Join-Path $BackendDir "dist"
$BuildDir = Join-Path $BackendDir "build"

if (-not (Test-Path $Python)) {
  throw "Python virtualenv was not found at $Python"
}

if ($PythonExecutable -and (Test-Path $SitePackages)) {
  $FallbackPythonPaths = @(
    $SitePackages,
    (Join-Path $SitePackages "win32"),
    (Join-Path $SitePackages "win32\lib"),
    (Join-Path $SitePackages "Pythonwin"),
    (Join-Path $SitePackages "pywin32_system32")
  ) | Where-Object { Test-Path $_ }
  if ($env:PYTHONPATH) {
    $FallbackPythonPaths += $env:PYTHONPATH
  }
  $env:PYTHONPATH = $FallbackPythonPaths -join ";"

  $PyWin32System32 = Join-Path $SitePackages "pywin32_system32"
  if (Test-Path $PyWin32System32) {
    $env:PATH = "$PyWin32System32;$env:PATH"
  }
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

# The optimised racing lines do NOT belong in this bundle, and the reason is
# worth writing down because it is not obvious.
#
# `--add-data` puts a file inside the executable, where it lands in `_MEIPASS`
# at run time. But `desktop_backend_runner` sets the resource root from the
# working directory when frozen, and the packaged app overrides it with
# `AT_BACKEND_RESOURCE_ROOT` pointing at Electron's resources folder. Neither is
# `_MEIPASS`, so a file embedded here is carried around and never read --
# verified by running this exe from an empty directory: the copy was present in
# `_MEIPASS\data\reference_models` and the coach still found nothing.
#
# The lines ship through electron-builder's `extraResources` instead, which puts
# them where the backend actually looks. See desktop/package.json.

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
