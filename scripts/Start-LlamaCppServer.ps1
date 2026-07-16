<#
Starts a local OpenAI-compatible llama.cpp server using either llama-cpp-python or llama-server.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Model,
  [ValidateSet('llama-cpp-python','llama-server')][string]$Mode = 'llama-cpp-python',
  [string]$HostAddress = '127.0.0.1',
  [int]$Port = 8080,
  [int]$ContextSize = 8192,
  [string]$ServerExe,
  [switch]$NoNewWindow
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Model)) { throw "Model file not found: $Model" }
if ($Mode -eq 'llama-cpp-python') {
  $python = Get-Command 'python' -ErrorAction Stop
  $argsList = @('-m','llama_cpp.server','--model',$Model,'--host',$HostAddress,'--port',[string]$Port,'--n_ctx',[string]$ContextSize)
  Write-Host "Starting llama-cpp-python server at http://$HostAddress`:$Port/v1"
  Start-Process -FilePath $python.Source -ArgumentList $argsList -NoNewWindow:$NoNewWindow
} else {
  if (-not $ServerExe) {
    $cmd = Get-Command 'llama-server' -ErrorAction SilentlyContinue
    if (-not $cmd) { throw 'llama-server was not found on PATH. Pass -ServerExe or use -Mode llama-cpp-python.' }
    $ServerExe = $cmd.Source
  }
  $argsList = @('--model',$Model,'--host',$HostAddress,'--port',[string]$Port,'--ctx-size',[string]$ContextSize)
  Write-Host "Starting llama-server at http://$HostAddress`:$Port/v1"
  Start-Process -FilePath $ServerExe -ArgumentList $argsList -NoNewWindow:$NoNewWindow
}
