[CmdletBinding()]
param(
  [string]$WorkDir = (Get-Location).Path,
  [string]$Image = 'n64recomp-companion:latest'
)

$ErrorActionPreference = 'Stop'
if (-not (Get-Command podman -ErrorAction SilentlyContinue)) {
  throw 'podman was not found on PATH.'
}
$resolved = (Resolve-Path $WorkDir).Path
podman run --rm -it -v "${resolved}:/work" -w /work $Image bash
