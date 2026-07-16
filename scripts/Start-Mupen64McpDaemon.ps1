<#
Starts the Mupen64MCP native daemon on Windows.
Real Rice + RSP-HLE plugins are selected in Rendered mode so framebuffer tools can capture pixels.
Dummy graphics remains available for CPU/debug sessions where a black framebuffer is acceptable.
#>
[CmdletBinding()]
param(
  [string]$MupenRoot = $env:MUPEN64MCP_ROOT,
  [Parameter(Mandatory=$true)][string]$Rom,
  [ValidateSet('Rendered','Headless')][string]$Mode = 'Rendered',
  [int]$Port = 9876,
  [switch]$AllowWriteMemory,
  [string]$DaemonExe,
  [string]$Core,
  [string]$DataDir,
  [string]$ConfigDir,
  [string]$Gfx,
  [string]$Rsp,
  [string]$Audio = 'dummy',
  [string]$InputPlugin,
  [string]$Msys2Bin = 'C:\msys64\mingw64\bin',
  [string]$WinLibsBin = '',
  [switch]$NoStopExisting
)

$ErrorActionPreference = 'Stop'
$rootInput = $MupenRoot
if (-not $rootInput) { throw 'Pass -MupenRoot or set MUPEN64MCP_ROOT.' }
$root = (Resolve-Path -LiteralPath $rootInput).Path
if (-not $DaemonExe) { $DaemonExe = Join-Path $root 'native\n64_debug_daemon\build\n64-debug-daemon.exe' }
if (-not $Core) { $Core = Join-Path $root 'build\mupen64plus\lib\mupen64plus.dll' }
if (-not $DataDir) { $DataDir = Join-Path $root 'build\mupen64plus\share' }
if (-not $ConfigDir) { $ConfigDir = Join-Path $root 'build\mupen64plus\config' }
if (-not $InputPlugin) { $InputPlugin = Join-Path $root 'native\n64_debug_daemon\build\mupen64plus-input-inject.dll' }
if (-not $Gfx) {
  if ($Mode -eq 'Rendered') { $Gfx = Join-Path $root 'plugins\mupen64plus-video-rice.dll' } else { $Gfx = 'dummy' }
}
if (-not $Rsp) {
  if ($Mode -eq 'Rendered') { $Rsp = Join-Path $root 'plugins\mupen64plus-rsp-hle.dll' } else { $Rsp = 'dummy' }
}

$required = @($DaemonExe, $Core, $Rom, $DataDir, $ConfigDir, $InputPlugin)
if ($Gfx -ne 'dummy') { $required += $Gfx }
if ($Rsp -ne 'dummy') { $required += $Rsp }
foreach ($path in $required) {
  if (-not (Test-Path -LiteralPath $path)) { throw "Required path not found: $path" }
}

# PATH ORDER CRITICAL for this workflow: MSYS2 -> WinLibs -> Mupen64Plus core lib -> existing system PATH.
$pathParts = @()
if ($Msys2Bin -and (Test-Path -LiteralPath $Msys2Bin)) { $pathParts += $Msys2Bin }
if ($WinLibsBin -and (Test-Path -LiteralPath $WinLibsBin)) { $pathParts += $WinLibsBin }
$pathParts += (Split-Path -Parent $Core)
$env:Path = (($pathParts + @($env:Path)) -join ';')

if (-not $NoStopExisting) {
  Get-Process 'n64-debug-daemon' -ErrorAction SilentlyContinue | Stop-Process -Force
  Start-Sleep -Seconds 1
}

$argsList = @(
  '--core', $Core,
  '--rom', $Rom,
  '--datadir', $DataDir,
  '--configdir', $ConfigDir,
  '--gfx', $Gfx,
  '--rsp', $Rsp,
  '--audio', $Audio,
  '--input', $InputPlugin,
  '--port', [string]$Port
)
if ($AllowWriteMemory) { $argsList += '--allow-write-memory' }

Write-Host "Starting n64-debug-daemon on port $Port"
Write-Host "Mode: $Mode"
if ($Mode -eq 'Rendered') {
  Write-Host 'Rendered mode uses real Rice video and RSP-HLE plugins so framebuffer capture can return pixels.'
}
Start-Process -FilePath $DaemonExe -ArgumentList $argsList -NoNewWindow
Write-Host 'Daemon launch requested.'
Write-Host 'For games that need START on boot, call the MCP tool n64_set_controller with buttons="START" and sticky=true before resume.'
