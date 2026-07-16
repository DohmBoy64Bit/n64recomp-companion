[CmdletBinding()]
param(
  [string]$Image = 'n64recomp-companion:latest',
  [string]$N64RecompRef = 'ffb39cdad1da5de07eaaa48bd1db4a89a7986771'
)

$ErrorActionPreference = 'Stop'
if (-not (Get-Command podman -ErrorAction SilentlyContinue)) {
  throw 'podman was not found on PATH.'
}
podman build --build-arg "N64RECOMP_REF=$N64RecompRef" -t $Image -f Containerfile .
