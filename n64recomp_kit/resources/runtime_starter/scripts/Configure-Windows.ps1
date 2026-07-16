[CmdletBinding()]
param(
    [string]$Preset = "windows-msvc-vcpkg",
    [string]$VcpkgRoot = $env:VCPKG_ROOT,
    [string]$VcpkgRef = "cd61e1e26a038e82d6550a3ebbe0fbbfe7da78e3",
    [switch]$DisableRT64
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if ($DisableRT64) { $Preset = "windows-msvc-no-rt64" }
if ([string]::IsNullOrWhiteSpace($VcpkgRoot)) {
    $VcpkgRoot = Join-Path $RepoRoot ".deps\vcpkg"
}

if (!(Test-Path (Join-Path $VcpkgRoot ".git"))) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $VcpkgRoot) | Out-Null
    git clone https://github.com/microsoft/vcpkg.git $VcpkgRoot
}

Push-Location $VcpkgRoot
try {
    git fetch --tags --force
    git checkout --detach $VcpkgRef
    if ((git rev-parse HEAD).Trim() -ne $VcpkgRef) { throw "vcpkg checkout did not resolve to $VcpkgRef" }
} finally { Pop-Location }

$Bootstrap = Join-Path $VcpkgRoot "bootstrap-vcpkg.bat"
if (!(Test-Path (Join-Path $VcpkgRoot "vcpkg.exe"))) {
    & $Bootstrap -disableMetrics
}

$env:VCPKG_ROOT = (Resolve-Path $VcpkgRoot).Path
cmake --preset $Preset
