[CmdletBinding()]
param(
  [string]$Prefix = '.deps\N64Recomp',
  [string]$Ref = 'ffb39cdad1da5de07eaaa48bd1db4a89a7986771',
  [string]$Generator = 'Ninja',
  [string]$BuildType = 'Release',
  [int]$Jobs = [Environment]::ProcessorCount
)

$ErrorActionPreference = 'Stop'
foreach ($cmd in @('git', 'cmake')) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
    throw "$cmd was not found on PATH."
  }
}
if ($Generator -eq 'Ninja' -and -not (Get-Command ninja -ErrorAction SilentlyContinue)) {
  throw 'ninja was not found on PATH. Install Ninja or pass a different CMake generator.'
}

$parent = Split-Path $Prefix -Parent
if ([string]::IsNullOrWhiteSpace($parent)) { $parent = '.' }
$prefixItem = New-Item -ItemType Directory -Force -Path $parent
$prefixPath = $prefixItem.FullName
$repoPath = Join-Path $prefixPath (Split-Path $Prefix -Leaf)
if (-not (Test-Path (Join-Path $repoPath '.git'))) {
  git clone --recurse-submodules https://github.com/N64Recomp/N64Recomp.git $repoPath
}
Push-Location $repoPath
try {
  git fetch --tags --prune
  git checkout --detach $Ref
  if ($Ref -match '^[0-9a-fA-F]{40}$' -and (git rev-parse HEAD).Trim().ToLowerInvariant() -ne $Ref.ToLowerInvariant()) { throw "N64Recomp checkout did not resolve to $Ref" }
  git submodule update --init --recursive
  cmake -S . -B build -G $Generator -DCMAKE_BUILD_TYPE=$BuildType
  cmake --build build --parallel $Jobs
  Write-Host "Built N64Recomp under $repoPath\build"
} finally {
  Pop-Location
}
