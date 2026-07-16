[CmdletBinding()]
param(
  [switch]$Install,
  [switch]$IncludeVisualStudioBuildTools
)

$ErrorActionPreference = 'Stop'
$packages = @(
  @{ Id = 'Git.Git'; Name = 'Git' },
  @{ Id = 'Kitware.CMake'; Name = 'CMake' },
  @{ Id = 'Ninja-build.Ninja'; Name = 'Ninja' },
  @{ Id = 'Python.Python.3.12'; Name = 'Python 3.12' },
  @{ Id = 'RedHat.Podman'; Name = 'Podman' },
  @{ Id = 'astral-sh.uv'; Name = 'uv' }
)
if ($IncludeVisualStudioBuildTools) {
  $packages += @{ Id = 'Microsoft.VisualStudio.2022.BuildTools'; Name = 'Visual Studio 2022 Build Tools' }
}

function Test-Command($Name) {
  return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

Write-Host 'Windows prerequisite check for n64recomp-companion'
Write-Host 'Install mode:' ($(if ($Install) { 'enabled' } else { 'disabled' }))

if (-not (Test-Command winget)) {
  Write-Warning 'winget was not found. Install prerequisites manually or run this on a current Windows 10/11 installation with App Installer.'
} else {
  foreach ($pkg in $packages) {
    Write-Host "Checking $($pkg.Name) [$($pkg.Id)]"
    if ($Install) {
      winget install --id $pkg.Id -e --accept-package-agreements --accept-source-agreements
    }
  }
}

$commands = @('git', 'cmake', 'ninja', 'python', 'py', 'uv', 'podman', 'cl', 'cdb')
foreach ($cmd in $commands) {
  $found = Get-Command $cmd -ErrorAction SilentlyContinue
  if ($found) {
    Write-Host ("{0,-8} {1}" -f $cmd, $found.Source)
  } else {
    Write-Host ("{0,-8} not found" -f $cmd)
  }
}

Write-Host 'For cdb.exe, install Microsoft Debugging Tools for Windows from the Windows SDK feature list.'
Write-Host 'For MSVC builds, run the N64Recomp bootstrap from an x64 Native Tools PowerShell or Developer PowerShell.'
