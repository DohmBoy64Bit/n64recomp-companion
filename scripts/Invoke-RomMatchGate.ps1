param(
  [Parameter(Mandatory=$true)][string]$Expected,
  [Parameter(Mandatory=$true)][string]$Actual,
  [string]$Report = "build/rom-match-report.json"
)
$ErrorActionPreference = "Stop"
python -m n64recomp_kit rom-match-check --expected $Expected --actual $Actual --report $Report
