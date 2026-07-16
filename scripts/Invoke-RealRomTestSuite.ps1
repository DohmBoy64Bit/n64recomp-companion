<#
Runs the real-ROM local suite. The default path is non-destructive and does not launch external tools unless -Execute is supplied.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Rom,
  [string]$ProjectRoot = '.',
  [string]$SourceRoot,
  [string]$Output = 'build\real-rom-test',
  [string]$CodeStart = '0x1000',
  [string]$Vram = '0x80000400',
  [ValidateSet('unit-tests','release-check','splat','mips','matching','elf','recomp','runtime','mcp','llm','podman','all')]
  [string[]]$Execute = @(),
  [string]$SplatConfig,
  [string]$Elf,
  [string]$RecompConfig,
  [string]$N64Recomp,
  [string]$MatchingRoot,
  [string]$RuntimeProject,
  [string]$MipsPrefix,
  [string]$MupenRoot,
  [ValidateSet('lmstudio','llama-cpp')][string]$Provider = 'lmstudio',
  [string]$Model,
  [string]$BaseUrl,
  [string]$ApiKey = 'local',
  [ValidateRange(1,86400)][int]$Timeout = 120,
  [string]$PodmanImage = 'n64recomp-companion:real-rom-test',
  [switch]$AllowGeneratedSplat,
  [switch]$Strict,
  [switch]$Overwrite,
  [switch]$Json
)

$ErrorActionPreference = 'Stop'
$argsList = @('real-rom-test','--rom',$Rom,'--project-root',$ProjectRoot,'--output',$Output,'--code-start',$CodeStart,'--vram',$Vram,'--api-key',$ApiKey,'--timeout',[string]$Timeout,'--podman-image',$PodmanImage)
if ($SourceRoot) { $argsList += @('--source-root',$SourceRoot) }
foreach ($stage in $Execute) { $argsList += @('--execute',$stage) }
if ($SplatConfig) { $argsList += @('--splat-config',$SplatConfig) }
if ($Elf) { $argsList += @('--elf',$Elf) }
if ($RecompConfig) { $argsList += @('--recomp-config',$RecompConfig) }
if ($N64Recomp) { $argsList += @('--n64recomp',$N64Recomp) }
if ($MatchingRoot) { $argsList += @('--matching-root',$MatchingRoot) }
if ($RuntimeProject) { $argsList += @('--runtime-project',$RuntimeProject) }
if ($MipsPrefix) { $argsList += @('--mips-prefix',$MipsPrefix) }
if ($MupenRoot) { $argsList += @('--mupen-root',$MupenRoot) }
if ($Model) { $argsList += @('--model',$Model) }
if ($BaseUrl) { $argsList += @('--base-url',$BaseUrl) }
$argsList += @('--provider',$Provider)
if ($AllowGeneratedSplat) { $argsList += '--allow-generated-splat' }
if ($Strict) { $argsList += '--strict' }
if ($Overwrite) { $argsList += '--overwrite' }
if ($Json) { $argsList += '--json' }
python -m n64recomp_kit @argsList
exit $LASTEXITCODE
