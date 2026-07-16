[CmdletBinding()]
param(
  [string]$Name = 'podman-machine-default',
  [int]$Cpus = 4,
  [int]$MemoryMb = 8192,
  [int]$DiskSizeGb = 80
)

$ErrorActionPreference = 'Stop'
if (-not (Get-Command podman -ErrorAction SilentlyContinue)) {
  throw 'podman was not found on PATH. Install Podman Desktop or Podman CLI first.'
}

$machineList = podman machine list --format json 2>$null | ConvertFrom-Json
$existing = @($machineList | Where-Object { $_.Name -eq $Name })
if ($existing.Count -eq 0) {
  podman machine init --cpus $Cpus --memory $MemoryMb --disk-size $DiskSizeGb $Name
}

$machineList = podman machine list --format json | ConvertFrom-Json
$current = @($machineList | Where-Object { $_.Name -eq $Name })[0]
if (-not $current.Running) {
  podman machine start $Name
}

podman info
