<#
Checks script presence, optional Mupen64MCP paths, and optionally local OpenAI-compatible API endpoints.
#>
[CmdletBinding()]
param(
  [string]$MupenRoot,
  [string]$LMStudioBaseUrl = 'http://127.0.0.1:1234/v1',
  [string]$LlamaCppBaseUrl = 'http://127.0.0.1:8080/v1',
  [switch]$SkipServerProbes
)
$ErrorActionPreference = 'Stop'
$argsList = @('local-llm-doctor','--lmstudio-base-url',$LMStudioBaseUrl,'--llama-cpp-base-url',$LlamaCppBaseUrl)
if ($MupenRoot) { $argsList += @('--mupen-root',$MupenRoot) }
if ($SkipServerProbes) { $argsList += '--skip-server-probes' }
python -m n64recomp_kit @argsList
exit $LASTEXITCODE
