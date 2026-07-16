<#
Starts or verifies the LM Studio local API server.
LM Studio can also be started from the app Developer tab.
#>
[CmdletBinding()]
param(
  [string]$BaseUrl = 'http://127.0.0.1:1234/v1',
  [switch]$StartWithLmsCli,
  [switch]$VerifyOnly
)
$ErrorActionPreference = 'Stop'
if ($StartWithLmsCli -and -not $VerifyOnly) {
  $lms = Get-Command 'lms' -ErrorAction SilentlyContinue
  if (-not $lms) { throw 'LM Studio CLI `lms` was not found on PATH. Start the server from the LM Studio Developer tab or install/enable the CLI.' }
  & $lms.Source server start
}
$modelsUrl = ($BaseUrl.TrimEnd('/')) + '/models'
try {
  $models = Invoke-RestMethod -Uri $modelsUrl -Headers @{ Authorization = 'Bearer lm-studio' } -TimeoutSec 5
  Write-Host "LM Studio API reachable at $BaseUrl"
  if ($models.data) { $models.data | Select-Object -First 20 id | Format-Table -AutoSize }
}
catch {
  throw "LM Studio API not reachable at $BaseUrl. Start it from the Developer tab, or run this script with -StartWithLmsCli if lms is installed. $($_.Exception.Message)"
}
