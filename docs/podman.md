# Podman workflow

The repository uses Podman and a `Containerfile` for a repeatable Linux tool environment on Windows. The image contains Splat 0.41.0, GNU big-endian-capable MIPS tools, and the pinned N64Recomp revision from `dependencies.lock.json`.

## Initialize on Windows

```powershell
.\scripts\Initialize-PodmanMachine.ps1
.\scripts\Build-PodmanImage.ps1
.\scripts\Enter-PodmanShell.ps1 -WorkDir .
```

The build script defaults to the pinned N64Recomp commit. Override `-N64RecompRef` only for an intentional compatibility experiment and record that revision in the project state file.

## Build directly

```powershell
podman build -t n64recomp-companion:1.10 -f Containerfile .
```

The base image is digest-locked. The lock improves reproducibility but does not replace routine image/package security review.

## Mounted workspace

`Enter-PodmanShell.ps1` bind-mounts the selected Windows project directory to `/work`. Keep ROMs outside source control even when they are visible through the mount.

Inside the container:

```bash
n64recomp-kit doctor --root /work
splat --help
n64recomp-kit toolchain-info
n64recomp-kit mips-smoke --output-dir /work/build/mips-smoke
```

## Release verification

The repository CI contains a container-build job definition. A release summary must state whether that job actually ran and passed; the presence of the definition alone is not execution evidence.
