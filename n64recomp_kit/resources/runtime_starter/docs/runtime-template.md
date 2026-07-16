# Runtime template ownership

## Present in the scaffold

- SDL2 window and event loop.
- CMake/vcpkg dependency discovery.
- RT64 source fetch pinned to a reviewed commit with recursive submodules.
- RmlUi package with its vcpkg `svg` feature.
- LunaSVG and FreeType dependencies.
- RML, RCSS, SVG, and font asset directories.
- Windows configure, build, and run scripts.

## Project-specific work

- N64ModernRuntime integration or an equivalent runtime.
- Recompiled function compilation and macro implementations.
- RT64 initialization and display-list submission.
- RmlUi interfaces, context creation, document loading, input routing, and rendering.
- Audio, saves, DMA, overlays, timing, and game-specific state.

Keep generated game code, runtime glue, renderer integration, and UI code in separate CMake targets so failures have a clear owner.
