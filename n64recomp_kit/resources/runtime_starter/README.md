# {{PROJECT_NAME}} runtime starter

This generated project is a Windows-first **host scaffold**. It creates an SDL2 window and wires CMake dependencies for RT64, RmlUi, LunaSVG, and FreeType. It is not a finished N64 port and does not execute recompiled game code by itself.

## Build

```powershell
.\scripts\Configure-Windows.ps1
.\scripts\Build-Windows.ps1
.\scripts\Run-Windows.ps1
```

Use `-DisableRT64` with the configure script to verify the SDL/RmlUi dependency layer without fetching RT64.

## Integration checklist

The project owner must implement each applicable layer:

1. Add N64ModernRuntime or another compatible runtime implementation.
2. Add generated `RecompiledFuncs` sources and required recompilation macros.
3. Initialize RT64 and pass display-list/runtime data to it.
4. Implement RmlUi system, render, and file interfaces.
5. Create an RmlUi context, load the included RML documents, and render it each frame.
6. Route SDL input events to RmlUi and game input translation.
7. Implement audio, saves, DMA, overlays, timing, and game-specific host glue.
8. Add evidence-driven tests for boot, input, rendering, menus, and saves.

The files in `assets/ui` are usable menu assets, but the starter does not load them until the RmlUi integration layer is implemented.

See `docs/runtime-template.md` for file ownership and extension points.
