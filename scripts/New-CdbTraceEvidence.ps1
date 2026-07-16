[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Output,
  [Parameter(Mandatory=$true)][string]$Wrapper,
  [Parameter(Mandatory=$true)][string]$Target,
  [ValidateSet('HIT','BYPASS','ABORT','INCONCLUSIVE')][string]$Result = 'INCONCLUSIVE',
  [string[]]$Breakpoint = @(),
  [Parameter(Mandatory=$true)][string]$Summary,
  [switch]$Overwrite
)

$ErrorActionPreference = 'Stop'
$argsList = @('cdb-evidence', '--output', $Output, '--wrapper', $Wrapper, '--target', $Target, '--result', $Result, '--summary', $Summary)
foreach ($bp in $Breakpoint) {
  $argsList += @('--breakpoint', $bp)
}
if ($Overwrite) {
  $argsList += '--overwrite'
}
python -m n64recomp_kit @argsList
