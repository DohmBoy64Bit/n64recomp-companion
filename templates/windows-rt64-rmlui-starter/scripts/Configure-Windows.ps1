[CmdletBinding()]
param(
    [string]$Preset = "windows-msvc-vcpkg",
    [string]$VcpkgRoot = $env:VCPKG_ROOT
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if ([string]::IsNullOrWhiteSpace($VcpkgRoot)) {
    $VcpkgRoot = Join-Path $RepoRoot ".deps\vcpkg"
}

if (!(Test-Path $VcpkgRoot)) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $VcpkgRoot) | Out-Null
    git clone https://github.com/microsoft/vcpkg.git $VcpkgRoot
}

$Bootstrap = Join-Path $VcpkgRoot "bootstrap-vcpkg.bat"
if (!(Test-Path (Join-Path $VcpkgRoot "vcpkg.exe"))) {
    & $Bootstrap -disableMetrics
}

$env:VCPKG_ROOT = (Resolve-Path $VcpkgRoot).Path
cmake --preset $Preset
