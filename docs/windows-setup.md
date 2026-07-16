# Windows setup

This repo is Windows-first. The recommended setup is:

1. Native PowerShell for Python CLI, workspace triage, config validation, CDB evidence notes, and native N64Recomp builds.
2. Podman for the repeatable Linux MIPS/Splat/N64Recomp tool container.
3. Microsoft Debugging Tools for Windows when debugging a native host executable produced by a recompilation project.

## Check tools

```powershell
python -m n64recomp_kit doctor --root .
```

The doctor checks Git, CMake, Ninja, Python, uv, Podman, MSVC `cl`, CDB, Splat, N64Recomp, and MIPS cross tools.

## Install common prerequisites

Dry-run style check:

```powershell
.\scripts\Install-WindowsPrereqs.ps1
```

Install common tools with winget:

```powershell
.\scripts\Install-WindowsPrereqs.ps1 -Install -IncludeVisualStudioBuildTools
```

After Visual Studio Build Tools are installed, launch an x64 Developer PowerShell before running `Bootstrap-N64Recomp-Windows.ps1`.

## Python decomp tools

```powershell
.\scripts\Bootstrap-DecompTools.ps1
. .\.deps\decomp-tools\env.ps1
python -m n64recomp_kit doctor --root .
```

The script installs `splat64[mips]` into `.deps\decomp-tools\.venv` and writes an activation helper at `.deps\decomp-tools\env.ps1`.

## Native N64Recomp build

```powershell
.\scripts\Bootstrap-N64Recomp-Windows.ps1 -Prefix .deps\N64Recomp
```

The script performs a recursive clone, checks out the requested ref, updates submodules, configures with CMake, and builds. With the default Ninja generator, the executable is `.deps\N64Recomp\build\N64Recomp.exe`; multi-configuration generators place it under a configuration subdirectory such as `Release`.

## CDB host debugging

Install Debugging Tools for Windows from the Windows SDK feature list, then check discovery:

```powershell
python -m n64recomp_kit cdb-info --root .
```

Use project-specific `tools\*cdb*.ps1` wrappers for real runs. The helper `New-CdbTraceEvidence.ps1` records conclusions after a wrapper produces a trace.
