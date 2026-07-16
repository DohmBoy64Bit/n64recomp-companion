# RT64/RmlUi host scaffold generator

`n64recomp-kit new-runtime-project` emits a Windows-first CMake/vcpkg project. Its verified generated capability is an SDL2 window/event loop plus dependency discovery and assets for RT64, RmlUi, LunaSVG, and FreeType.

It is deliberately a **host scaffold**, not a complete N64 port. The generated executable does not initialize RT64, create an RmlUi context, implement RmlUi render/system/file interfaces, load an RML document, connect N64ModernRuntime, compile `RecompiledFuncs`, or provide game audio/input/saves/DMA/timing glue.

## Generate

```powershell
python -m n64recomp_kit new-runtime-project --output runtime\Starfall64 --name Starfall64 --window-title "Starfall 64 Recompiled" --overwrite
```

The generator has one canonical source under `n64recomp_kit/resources/runtime_starter`. Generated output is checked for unresolved template tokens, and package tests generate from the installed package resource path.

## Included files

- `CMakeLists.txt`, Visual Studio 2022 `CMakePresets.json`, and a convenience `Makefile`.
- `vcpkg.json` with the locked baseline from `dependencies.lock.json`.
- RmlUi requested with its `svg` feature, plus LunaSVG and FreeType.
- `cmake/Dependencies.cmake` with RT64 pinned to the recorded commit and recursive submodules enabled.
- `src/main.cpp` with a resizable SDL2 event loop.
- small source modules that expose dependency/asset status without pretending to implement renderer or UI runtime glue.
- `assets/ui/*.rml`, RCSS, and SVG launcher/menu examples.
- PowerShell configure/build/run scripts.
- `.n64recomp-runtime`, which lets workspace scanning recognize the project as a host runtime.

## Build the scaffold

```powershell
cd runtime\Starfall64
.\scripts\Configure-Windows.ps1
.\scripts\Build-Windows.ps1
.\scripts\Run-Windows.ps1
```

Use `-DisableRT64` with the configure script to test the SDL/RmlUi/vcpkg layer without fetching RT64.

## Required project-owned implementation

1. Add N64ModernRuntime or a compatible runtime implementation.
2. Compile/link generated N64Recomp sources and provide required macros.
3. Initialize RT64 and feed it the display-list/runtime data expected by the chosen integration.
4. Implement RmlUi system, render, and file interfaces.
5. Create an RmlUi context, load the included launcher/menu documents, process SDL input, update, and render.
6. Register fonts through the FreeType-backed RmlUi font engine.
7. Add audio, input translation, saves, DMA, overlays, timing, and game-specific entrypoint glue.
8. Add boot, input, rendering, menu, and save evidence tests.

A window opening proves only that the host scaffold and dependency layer built and ran.
