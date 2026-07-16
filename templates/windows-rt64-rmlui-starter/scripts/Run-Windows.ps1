[CmdletBinding()]
param(
    [string]$Preset = "windows-msvc-vcpkg"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
$BuildRoot = Join-Path $RepoRoot "build\$Preset"
$Exe = Get-ChildItem -Path $BuildRoot -Filter "n64_runtime_starter.exe" -Recurse | Select-Object -First 1
if ($null -eq $Exe) {
    throw "Executable not found under $BuildRoot. Run scripts\Build-Windows.ps1 first."
}
& $Exe.FullName
