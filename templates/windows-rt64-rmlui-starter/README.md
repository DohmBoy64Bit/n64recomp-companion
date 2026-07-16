# N64 Runtime Starter runtime starter

This generated project is a Windows-first CMake starter for a native N64Recomp host application. It opens a basic SDL2 game window, links RT64 when enabled, and ships RmlUi launcher/menu assets with SVG and FreeType dependencies wired through CMake.

## What this project builds

- `n64_runtime_starter.exe`, a basic resizable game window.
- RT64 linked as a static CMake dependency when `N64_STARTER_ENABLE_RT64=ON`.
- RmlUi, LunaSVG, and FreeType dependencies available to the host application.
- Launcher and menu RML/CSS/SVG assets copied beside the executable.

The application does not contain any ROM data or proprietary game code. Recompiled game functions produced by N64Recomp should be added as normal CMake sources or as a library target after they exist.

## Windows build

Open an x64 Developer PowerShell for Visual Studio.

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\scripts\Configure-Windows.ps1
.\scripts\Build-Windows.ps1
.\scripts\Run-Windows.ps1
```

The configure script expects `VCPKG_ROOT` to point at a bootstrapped vcpkg checkout. If it is not set, the script installs vcpkg under `.deps\vcpkg` and uses that local copy.

## RT64 switch

RT64 is enabled by default. The configure step fetches `https://github.com/rt64/rt64.git` and links the `rt64` target. To build the starter window while isolating local dependency problems, use the no-RT64 preset:

```powershell
cmake --preset windows-msvc-no-rt64
cmake --build --preset windows-msvc-no-rt64
```

## Menu and launcher assets

RmlUi assets live in `assets/ui` and `assets/ui/styles`:

- `launcher.rml` for pre-game ROM/profile selection UI.
- `pause_menu.rml` for in-game pause settings.
- `settings.rml` for graphics, input, audio, and save-path settings.
- `styles/main.rcss` for the shared menu look.
- `svg/logo.svg` for LunaSVG-backed vector rendering.

`src/rmlui_manifest.cpp` lists these files so the host can validate them before creating actual RmlUi contexts and render interfaces.

## Adding N64Recomp output

After N64Recomp has emitted host C/C++ sources, add them in `CMakeLists.txt` with either `target_sources(n64_runtime_starter PRIVATE ...)` or a separate static library linked to `n64_runtime_starter`. Runtime glue should connect generated functions to N64ModernRuntime, input, audio, saves, DMA, overlays, and the RT64 renderer.
