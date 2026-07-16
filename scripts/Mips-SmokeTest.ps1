[CmdletBinding()]
param(
  [string]$Prefix = '',
  [string]$OutputDir = 'build\mips-smoke'
)

$ErrorActionPreference = 'Stop'
$argsList = @('mips-smoke', '--output-dir', $OutputDir)
if ($Prefix.Length -gt 0) {
  $argsList += @('--prefix', $Prefix)
}
python -m n64recomp_kit @argsList
