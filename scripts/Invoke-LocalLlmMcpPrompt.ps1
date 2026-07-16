<#
Runs one local LLM prompt through n64recomp-kit. When -MupenRoot is supplied, the command also exposes Mupen64MCP tools to the model.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Prompt,
  [Parameter(Mandatory=$true)][string]$Model,
  [ValidateSet('LMStudio','LlamaCpp')][string]$Provider = 'LMStudio',
  [string]$BaseUrl,
  [string]$ApiKey = 'local',
  [string]$MupenRoot,
  [int]$MaxToolRounds = 8,
  [ValidateSet('deny','prompt','allow')][string]$MutationPolicy = 'deny',
  [string[]]$AllowTool = @()
)
$ErrorActionPreference = 'Stop'
if (-not $BaseUrl) {
  if ($Provider -eq 'LMStudio') { $BaseUrl = 'http://127.0.0.1:1234/v1'; $ApiKey = 'lm-studio' }
  else { $BaseUrl = 'http://127.0.0.1:8080/v1' }
}
$providerArg = if ($Provider -eq 'LMStudio') { 'lmstudio' } else { 'llama-cpp' }
$argsList = @('local-llm-ask','--prompt',$Prompt,'--model',$Model,'--provider',$providerArg,'--base-url',$BaseUrl,'--api-key',$ApiKey,'--max-tool-rounds',[string]$MaxToolRounds,'--mutation-policy',$MutationPolicy)
foreach ($tool in $AllowTool) { $argsList += @('--allow-tool',$tool) }
if ($MupenRoot) {
  $argsList += @('--mupen-root',(Resolve-Path -LiteralPath $MupenRoot).Path)
}
python -m n64recomp_kit @argsList
exit $LASTEXITCODE
