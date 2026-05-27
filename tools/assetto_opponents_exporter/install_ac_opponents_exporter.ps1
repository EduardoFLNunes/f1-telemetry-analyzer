param(
    [string]$AssettoRoot
)

$ErrorActionPreference = "Stop"

function Find-AssettoRoot {
    $candidates = @()

    $steamPaths = @(
        "HKLM:\SOFTWARE\WOW6432Node\Valve\Steam",
        "HKLM:\SOFTWARE\Valve\Steam",
        "HKCU:\SOFTWARE\Valve\Steam"
    )

    foreach ($path in $steamPaths) {
        try {
            $steamPath = (Get-ItemProperty -Path $path -ErrorAction Stop).InstallPath
            if ($steamPath) {
                $candidates += Join-Path $steamPath "steamapps\common\assettocorsa"
            }
        } catch {
        }
    }

    $candidates += @(
        "C:\Program Files (x86)\Steam\steamapps\common\assettocorsa",
        "C:\Program Files\Steam\steamapps\common\assettocorsa",
        "D:\SteamLibrary\steamapps\common\assettocorsa",
        "D:\Steam\steamapps\common\assettocorsa",
        "E:\SteamLibrary\steamapps\common\assettocorsa",
        "E:\Steam\steamapps\common\assettocorsa"
    )

    foreach ($candidate in $candidates | Select-Object -Unique) {
        if (-not (Test-Path -LiteralPath $candidate)) {
            continue
        }
        if (Test-Path -LiteralPath (Join-Path $candidate "acs.exe")) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    return $null
}

$source = Join-Path $PSScriptRoot "ac_opponents_exporter.py"
if (-not (Test-Path -LiteralPath $source)) {
    throw "Exporter source not found: $source"
}

if (-not $AssettoRoot) {
    $AssettoRoot = Find-AssettoRoot
}

if (-not $AssettoRoot) {
    throw "Assetto Corsa folder not found automatically. Run again with -AssettoRoot 'C:\path\to\Steam\steamapps\common\assettocorsa'"
}

$AssettoRoot = (Resolve-Path -LiteralPath $AssettoRoot).Path
$acsExe = Join-Path $AssettoRoot "acs.exe"
if (-not (Test-Path -LiteralPath $acsExe)) {
    throw "Invalid Assetto Corsa folder, acs.exe not found: $AssettoRoot"
}

$targetDir = Join-Path $AssettoRoot "apps\python\ac_opponents_exporter"
$target = Join-Path $targetDir "ac_opponents_exporter.py"

New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
Copy-Item -LiteralPath $source -Destination $target -Force

$icon = Join-Path $PSScriptRoot "icon.png"
if (Test-Path -LiteralPath $icon) {
    Copy-Item -LiteralPath $icon -Destination (Join-Path $targetDir "icon.png") -Force
}

$simhubDir = Join-Path $AssettoRoot "apps\python\SimHub"
$runtimeCopies = @(
    @{ Source = Join-Path $simhubDir "stdlib\_ctypes.pyd"; TargetDir = Join-Path $targetDir "stdlib" },
    @{ Source = Join-Path $simhubDir "stdlib64\_ctypes.pyd"; TargetDir = Join-Path $targetDir "stdlib64" }
)

foreach ($runtime in $runtimeCopies) {
    if (Test-Path -LiteralPath $runtime.Source) {
        New-Item -ItemType Directory -Force -Path $runtime.TargetDir | Out-Null
        $runtimeTarget = Join-Path $runtime.TargetDir "_ctypes.pyd"
        try {
            Copy-Item -LiteralPath $runtime.Source -Destination $runtimeTarget -Force
        } catch {
            if (Test-Path -LiteralPath $runtimeTarget) {
                Write-Warning "Runtime file is already present but locked, keeping existing: $runtimeTarget"
            } else {
                throw
            }
        }
    }
}

Write-Host "Installed Opponents Exporter:"
Write-Host "  $target"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Open Assetto Corsa or Content Manager."
Write-Host "  2. Enable the Python app/module named ac_opponents_exporter or Opponents Exporter."
Write-Host "  3. In a session, open the right-side app bar and select Opponents Exporter."
