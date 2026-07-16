[CmdletBinding()]
param(
    [string]$Preset = "windows-msvc-vcpkg"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
cmake --build --preset $Preset
