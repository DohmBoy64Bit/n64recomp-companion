[CmdletBinding()]
param(
  [string]$Prefix = '.deps\decomp-tools',
  [string]$Python = 'python'
)

$ErrorActionPreference = 'Stop'
$prefixItem = New-Item -ItemType Directory -Force -Path $Prefix
$prefixPath = $prefixItem.FullName
$venv = Join-Path $prefixPath '.venv'
& $Python -m venv $venv
$py = Join-Path $venv 'Scripts\python.exe'
& $py -m pip install --upgrade pip
& $py -m pip install -r requirements-decomp.txt
$envFile = Join-Path $prefixPath 'env.ps1'
@"
`$env:PATH = '$venv\Scripts;' + `$env:PATH
"@ | Set-Content -Encoding UTF8 $envFile
Write-Host "Installed decomp tools at $prefixPath"
Write-Host "Run: . $envFile"
