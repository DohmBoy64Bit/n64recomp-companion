[CmdletBinding()]
param(
  [string]$Config = 'decomp\splat.yaml',
  [string]$Root = '.',
  [string]$Prefix = '',
  [ValidateSet('asm-only','gnu-c')]
  [string]$Profile = 'asm-only',
  [switch]$Clean,
  [switch]$DryRun,
  [string]$Report = 'build\elf-build-report.json'
)

$ErrorActionPreference = 'Stop'
$argsList = @('build-elf', '--config', $Config, '--root', $Root, '--profile', $Profile, '--report', $Report)
if ($Prefix -ne '') { $argsList += @('--prefix', $Prefix) }
if ($Clean) { $argsList += '--clean' }
if ($DryRun) { $argsList += '--dry-run' }
python -m n64recomp_kit @argsList
