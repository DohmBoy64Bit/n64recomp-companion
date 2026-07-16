# Verified external facts and release pins

Checked on 2026-07-10. This file records facts used by the implementation; it does not claim that every external integration was executed in the release environment.

## N64Recomp

- N64Recomp statically recompiles N64 binaries into C and requires a separate host/runtime implementation for a complete port.
- Upstream build instructions require CMake 3.20 or newer, C++20 support, and recursive submodules.
- This release pins source builds to `ffb39cdad1da5de07eaaa48bd1db4a89a7986771`.

Source: https://github.com/N64Recomp/N64Recomp

## Splat

- The current PyPI release used here is `splat64` 0.41.0.
- The N64 workflow requires the `mips` extra.
- The current CLI uses the action form `splat split <config>`.
- Child output paths are interpreted relative to `options.base_path`.

Sources: https://pypi.org/project/splat64/ and https://github.com/ethteck/splat

## RT64

- RT64 is published as a renderer implementation intended for native-port integration.
- This release pins FetchContent to `f0728a2520d5aa735886240de3fee75cc805f6d6` and requests recursive submodules.

Source: https://github.com/rt64/rt64

## RmlUi, LunaSVG, and FreeType

- RmlUi can use FreeType as its font engine.
- RmlUi’s SVG plugin uses LunaSVG.
- In vcpkg, SVG support must be requested through the RmlUi `svg` feature; merely installing LunaSVG separately does not enable the plugin in an already-built RmlUi package.
- The generated runtime manifest uses vcpkg baseline `cd61e1e26a038e82d6550a3ebbe0fbbfe7da78e3` and requests `rmlui[svg]`.

Source: https://mikke89.github.io/RmlUiDoc/pages/cpp_manual/building_with_cmake.html

## Podman on Windows

- Podman uses a managed Linux machine for Linux containers on Windows.
- The workflow uses `podman machine init`, `podman machine start`, and a `Containerfile`.
- The Ubuntu 24.04 base is digest-locked in `Containerfile`.

Source: https://podman.io/docs/installation

## Mupen64MCP and local servers

- The optional workflow uses the `n64-debug-mcp` server and Mupen64MCP daemon/tool names from its current repository.
- Real Rice video and RSP-HLE plugins are used by the rendered daemon mode for framebuffer evidence; dummy graphics remains a CPU/debug option.
- LM Studio and llama.cpp expose OpenAI-compatible local endpoints, but tool calling depends on the selected model and server template. `local-llm-doctor --model` performs an explicit tool-call probe.
- Mupen64MCP source reference recorded for this release: `9fa441d4c603efc47b570d021c767f93b6625cbd`.

Sources: https://github.com/DohmBoy64Bit/Mupen64MCP, https://lmstudio.ai/docs/app, and https://github.com/ggml-org/llama.cpp/tree/master/tools/server

## Verification boundary

The repository test suite exercises Python logic, generated files, mocked non-dry-run control flow, and a fake MCP stdio server. A release made outside Windows/Podman cannot honestly claim that Visual Studio, Podman, real Splat projects, real MIPS tools, N64Recomp, RT64, RmlUi, Mupen64MCP, LM Studio, or llama.cpp were executed unless the release record states that separately.

## MCP protocol and CI action pins

- The stdio client prefers MCP protocol `2025-11-25`, the current published protocol version on the verification date, and accepts the two prior protocol versions recorded in `dependencies.lock.json` when a server negotiates one of them.
- The client validates the negotiated version before sending `notifications/initialized`.
- GitHub Actions references are commit-pinned. The corresponding release labels and full revisions are recorded in `dependencies.lock.json`.

Sources: https://modelcontextprotocol.io/docs/learn/versioning, https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle, https://github.com/actions/checkout, and https://github.com/actions/setup-python

## Release verification

The exact checks performed for a release are separate from the CI jobs defined by the repository. See [`release-verification.md`](release-verification.md). A source-tree pass does not imply Windows, Podman, RT64, Mupen64MCP, or local-model execution.
