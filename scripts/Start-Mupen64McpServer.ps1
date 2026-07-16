<#
Starts the Python Mupen64MCP server from the repository checkout.
#>
[CmdletBinding()]
param(
  [string]$MupenRoot = $env:MUPEN64MCP_ROOT,
  [switch]$UseInstalledCommand
)
$ErrorActionPreference = 'Stop'
$rootInput = $MupenRoot
if (-not $rootInput) { throw 'Pass -MupenRoot or set MUPEN64MCP_ROOT.' }
$mcpPython = Join-Path (Resolve-Path -LiteralPath $rootInput).Path 'mcp\python'
if (-not (Test-Path -LiteralPath $mcpPython)) { throw "Mupen64MCP Python server directory not found: $mcpPython" }
if ($UseInstalledCommand) {
  $cmd = Get-Command 'n64-debug-mcp' -ErrorAction Stop
  & $cmd.Source
  exit $LASTEXITCODE
}
$uv = Get-Command 'uv' -ErrorAction SilentlyContinue
if ($uv) {
  & $uv.Source --directory $mcpPython run n64-debug-mcp
  exit $LASTEXITCODE
}
Push-Location $mcpPython
try {
  python -m pip install -e .
  n64-debug-mcp
  exit $LASTEXITCODE
}
finally { Pop-Location }
